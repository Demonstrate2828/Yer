#!/usr/bin/env python3
"""
PutinZov Casino Bot - Discord бот с казино-играми и экономикой

Этот бот предоставляет игрокам на сервере "PutinZov and Casino" возможность играть 
в различные азартные игры, используя виртуальную валюту. Реализованы следующие функции:
- Система экономики: начальный баланс 10,000 монет, ежедневные бонусы, переводы между игроками
- Казино-игры: рулетка, блэкджек, слоты
- Таблица лидеров и статистика
- Административные команды для управления экономикой сервера

Автор: Replit AI
Версия: 1.0.0
Дата: 25.04.2025
"""

import os
import json
import random
import asyncio
import datetime
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
from collections import deque
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands, tasks

# Загрузка переменных окружения из .env файла
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Настройка интентов Discord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Создание экземпляра бота
bot = commands.Bot(command_prefix='/', intents=intents)

#########################
# СИСТЕМА ХРАНЕНИЯ ДАННЫХ
#########################

class GameType(Enum):
    """Типы игр в казино"""
    ROULETTE = "roulette"
    BLACKJACK = "blackjack"
    SLOTS = "slots"

class GameOutcome(Enum):
    """Результаты игр"""
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    BLACKJACK = "blackjack"
    NO_MATCH = "no_match"
    SMALL_WIN = "small_win"
    MEDIUM_WIN = "medium_win"
    BIG_WIN = "big_win"
    JACKPOT = "jackpot"

class User:
    """Класс пользователя с балансом и статистикой"""
    def __init__(self, user_id: str, username: str, discriminator: str = "", 
                balance: int = 10000, is_admin: bool = False):
        self.id = random.randint(1, 1000000)  # Уникальный ID в системе
        self.user_id = user_id                # Discord ID
        self.username = username              # Имя пользователя
        self.discriminator = discriminator    # Дискриминатор
        self.balance = balance                # Баланс
        self.is_admin = is_admin              # Админ ли пользователь
        self.last_daily = None                # Дата последнего ежедневного бонуса
        self.games_played = 0                 # Сыгранные игры
        self.games_won = 0                    # Выигранные игры

class GameHistory:
    """Запись истории игры"""
    def __init__(self, user_id: str, game_type: GameType, bet_amount: int, 
                outcome: GameOutcome, win_amount: int = 0):
        self.id = random.randint(1, 1000000)  # Уникальный ID
        self.user_id = user_id                # Discord ID пользователя
        self.game_type = game_type            # Тип игры
        self.bet_amount = bet_amount          # Сумма ставки
        self.outcome = outcome                # Результат
        self.win_amount = win_amount          # Сумма выигрыша
        self.timestamp = datetime.datetime.now()  # Время игры

class Storage:
    """Класс хранения данных в памяти"""
    def __init__(self):
        self.users = {}                       # Словарь пользователей: {user_id: User}
        self.game_history = []                # Список истории игр
    
    # Методы для работы с пользователями
    def get_user(self, user_id: str) -> Optional[User]:
        """Получить пользователя по ID"""
        return self.users.get(user_id)
    
    def create_user(self, user_id: str, username: str, discriminator: str = "", 
                   balance: int = 10000, is_admin: bool = False) -> User:
        """Создать нового пользователя"""
        user = User(user_id, username, discriminator, balance, is_admin)
        self.users[user_id] = user
        return user
    
    def update_user_balance(self, user_id: str, new_balance: int) -> Optional[User]:
        """Обновить баланс пользователя"""
        user = self.get_user(user_id)
        if user:
            user.balance = new_balance
            return user
        return None
    
    def get_users_by_balance_desc(self, limit: int = 10) -> List[User]:
        """Получить пользователей по убыванию баланса"""
        sorted_users = sorted(self.users.values(), key=lambda u: u.balance, reverse=True)
        return sorted_users[:limit]
    
    # Методы для работы с историей игр
    def add_game_history(self, user_id: str, game_type: GameType, bet_amount: int,
                         outcome: GameOutcome, win_amount: int = 0) -> GameHistory:
        """Добавить запись в историю игр"""
        history = GameHistory(user_id, game_type, bet_amount, outcome, win_amount)
        self.game_history.append(history)
        
        # Обновление статистики пользователя
        user = self.get_user(user_id)
        if user:
            user.games_played += 1
            if outcome in [GameOutcome.WIN, GameOutcome.BLACKJACK, 
                         GameOutcome.SMALL_WIN, GameOutcome.MEDIUM_WIN, 
                         GameOutcome.BIG_WIN, GameOutcome.JACKPOT]:
                user.games_won += 1
        
        return history
    
    def get_game_history_by_user_id(self, user_id: str, limit: int = 10) -> List[GameHistory]:
        """Получить историю игр пользователя"""
        user_history = [h for h in self.game_history if h.user_id == user_id]
        return sorted(user_history, key=lambda h: h.timestamp, reverse=True)[:limit]
    
    # Админские методы
    def reset_user_balance(self, user_id: str, amount: int = 10000) -> Optional[User]:
        """Сбросить баланс пользователя"""
        user = self.get_user(user_id)
        if user:
            user.balance = amount
            return user
        return None
    
    def set_user_admin(self, user_id: str, is_admin: bool) -> Optional[User]:
        """Установить статус админа"""
        user = self.get_user(user_id)
        if user:
            user.is_admin = is_admin
            return user
        return None
    
    # Статистика
    def get_total_users(self) -> int:
        """Получить общее количество пользователей"""
        return len(self.users)
    
    def get_total_coins(self) -> int:
        """Получить общее количество монет"""
        return sum(user.balance for user in self.users.values())
    
    def get_games_played_today(self) -> int:
        """Получить количество игр за сегодня"""
        today = datetime.datetime.now().date()
        return sum(1 for h in self.game_history 
                 if h.timestamp.date() == today)

# Создаем глобальный экземпляр хранилища
storage = Storage()

#########################
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
#########################

def create_embed(title: str = None, description: str = None, color: int = 0xFFD700,
                fields: List[Dict[str, Union[str, bool]]] = None, 
                thumbnail: str = None, footer: str = None) -> discord.Embed:
    """Создать Discord Embed с заданными параметрами"""
    embed = discord.Embed(color=color)
    
    if title:
        embed.title = title
    if description:
        embed.description = description
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if footer:
        embed.set_footer(text=footer)
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
    
    return embed

def get_random_int(min_val: int, max_val: int) -> int:
    """Получить случайное целое число от min до max включительно"""
    return random.randint(min_val, max_val)

def shuffle(array: List[Any]) -> List[Any]:
    """Перемешать массив с использованием алгоритма Фишера-Йейтса"""
    result = array.copy()
    random.shuffle(result)
    return result

def format_number(num: int) -> str:
    """Форматировать число с разделителями тысяч"""
    return "{:,}".format(num)

def calculate_win_rate(wins: int, total: int) -> str:
    """Вычислить процент побед"""
    if total == 0:
        return "0%"
    return f"{(wins / total * 100):.1f}%"

#########################
# СЛУЖЕБНЫЕ ОБРАБОТЧИКИ
#########################

@bot.event
async def on_ready():
    """Вызывается при успешном подключении бота к Discord"""
    print(f"Bot is ready! Logged in as {bot.user.display_name}")
    
    # Синхронизация команд
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_member_join(member):
    """Обработчик события присоединения нового участника к серверу"""
    try:
        # Проверяем, существует ли пользователь в системе
        user_id = str(member.id)
        user = storage.get_user(user_id)
        
        # Если пользователя нет, создаем его с начальным балансом
        if not user:
            user = storage.create_user(
                user_id=user_id,
                username=member.name,
                discriminator=member.discriminator or "",
                balance=10000,
                is_admin=False
            )
            print(f"Created new user: {user.username} with initial balance: {user.balance}")
    except Exception as e:
        print(f"Error creating user on guild join: {e}")

#########################
# ЭКОНОМИЧЕСКИЕ КОМАНДЫ
#########################

@bot.tree.command(name="balance", description="Проверить свой баланс или баланс другого пользователя")
async def balance(interaction: discord.Interaction, user: Optional[discord.User] = None):
    """Команда для проверки баланса"""
    try:
        target_user = user or interaction.user
        user_id = str(target_user.id)
        
        # Получаем пользователя из хранилища
        db_user = storage.get_user(user_id)
        
        if not db_user:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Пользователь не найден",
                    description="Этот пользователь еще не играл в игры.",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Экономика"
                ),
                ephemeral=True
            )
            return
        
        # Отправляем информацию о балансе
        await interaction.response.send_message(
            embed=create_embed(
                title=f"Баланс {target_user.display_name}",
                description=f"Текущий баланс: **{format_number(db_user.balance)}** монет",
                color=0xFFD700,  # Золотой
                thumbnail=target_user.display_avatar.url,
                fields=[
                    {"name": "Игр сыграно", "value": str(db_user.games_played), "inline": True},
                    {"name": "Игр выиграно", "value": str(db_user.games_won), "inline": True},
                    {"name": "Процент побед", "value": calculate_win_rate(db_user.games_won, db_user.games_played), "inline": True}
                ],
                footer="PutinZov Casino | Экономика"
            )
        )
    except Exception as e:
        print(f"Error executing balance command: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при проверке баланса!",
            ephemeral=True
        )

@bot.tree.command(name="daily", description="Получить ежедневный бонус монет")
async def daily(interaction: discord.Interaction):
    """Команда для получения ежедневного бонуса"""
    try:
        user_id = str(interaction.user.id)
        
        # Получаем пользователя из хранилища
        user = storage.get_user(user_id)
        
        if not user:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Пользователь не найден",
                    description="Вам нужно сыграть в игру, прежде чем получать ежедневные награды.",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Ежедневный бонус"
                ),
                ephemeral=True
            )
            return
        
        now = datetime.datetime.now()
        today = datetime.datetime(now.year, now.month, now.day)
        
        # Проверяем, получал ли пользователь уже бонус сегодня
        if user.last_daily and user.last_daily.date() == today.date():
            next_reset = today + datetime.timedelta(days=1)
            hours_remaining = int((next_reset - now).total_seconds() / 3600)
            
            await interaction.response.send_message(
                embed=create_embed(
                    title="Бонус уже получен",
                    description=f"Вы уже получили ежедневный бонус сегодня.\nВозвращайтесь через **{hours_remaining}** часов.",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Ежедневный бонус"
                ),
                ephemeral=True
            )
            return
        
        # Выдаем ежедневный бонус (1000 монет)
        DAILY_REWARD = 1000
        new_balance = user.balance + DAILY_REWARD
        storage.update_user_balance(user_id, new_balance)
        
        # Обновляем время получения бонуса
        user.last_daily = now
        
        await interaction.response.send_message(
            embed=create_embed(
                title="Ежедневный бонус получен!",
                description=f"Вы получили **{format_number(DAILY_REWARD)}** монет!\nВаш новый баланс: **{format_number(new_balance)}** монет.",
                color=0x57F287,  # Зеленый
                thumbnail=interaction.user.display_avatar.url,
                footer="PutinZov Casino | Ежедневный бонус"
            )
        )
    except Exception as e:
        print(f"Error executing daily command: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при получении ежедневного бонуса!",
            ephemeral=True
        )

@bot.tree.command(name="transfer", description="Перевести монеты другому пользователю")
async def transfer(interaction: discord.Interaction, user: discord.User, amount: int):
    """Команда для перевода монет другому пользователю"""
    try:
        if amount < 1:
            await interaction.response.send_message(
                content="Сумма перевода должна быть больше 0!",
                ephemeral=True
            )
            return
        
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Ошибка перевода",
                    description="Вы не можете перевести монеты самому себе!",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Перевод"
                ),
                ephemeral=True
            )
            return
        
        sender_id = str(interaction.user.id)
        recipient_id = str(user.id)
        
        # Получаем отправителя из хранилища
        sender = storage.get_user(sender_id)
        
        if not sender:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Пользователь не найден",
                    description="Вам нужно сыграть в игру, прежде чем совершать переводы.",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Перевод"
                ),
                ephemeral=True
            )
            return
        
        # Проверяем, достаточно ли средств у отправителя
        if sender.balance < amount:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Недостаточно средств",
                    description=f"У вас только **{format_number(sender.balance)}** монет, но вы пытаетесь перевести **{format_number(amount)}** монет.",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Перевод"
                ),
                ephemeral=True
            )
            return
        
        # Получаем получателя из хранилища
        recipient = storage.get_user(recipient_id)
        
        # Создаем получателя, если его нет
        if not recipient:
            recipient = storage.create_user(
                user_id=recipient_id,
                username=user.display_name,
                discriminator=user.discriminator or "",
                balance=10000,
                is_admin=False
            )
        
        # Обновляем балансы
        sender_new_balance = sender.balance - amount
        recipient_new_balance = recipient.balance + amount
        
        storage.update_user_balance(sender_id, sender_new_balance)
        storage.update_user_balance(recipient_id, recipient_new_balance)
        
        await interaction.response.send_message(
            embed=create_embed(
                title="Перевод выполнен",
                description=f"Вы перевели **{format_number(amount)}** монет пользователю **{user.display_name}**!\nВаш новый баланс: **{format_number(sender_new_balance)}** монет.",
                color=0x57F287,  # Зеленый
                thumbnail=user.display_avatar.url,
                footer="PutinZov Casino | Перевод"
            )
        )
    except Exception as e:
        print(f"Error executing transfer command: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при переводе монет!",
            ephemeral=True
        )

#########################
# КОМАНДЫ РУЛЕТКИ
#########################

class RouletteBetType(Enum):
    """Типы ставок в рулетке"""
    NUMBER = "number"         # Конкретное число
    RED = "red"               # Красное
    BLACK = "black"           # Черное
    EVEN = "even"             # Четное
    ODD = "odd"               # Нечетное
    LOW = "1-18"              # Числа 1-18
    HIGH = "19-36"            # Числа 19-36
    FIRST_DOZEN = "1st dozen" # Первая дюжина (1-12)
    SECOND_DOZEN = "2nd dozen" # Вторая дюжина (13-24)
    THIRD_DOZEN = "3rd dozen" # Третья дюжина (25-36)
    FIRST_COLUMN = "1st column" # Первая колонка (1,4,7...)
    SECOND_COLUMN = "2nd column" # Вторая колонка (2,5,8...)
    THIRD_COLUMN = "3rd column" # Третья колонка (3,6,9...)

# Константы рулетки
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
BLACK_NUMBERS = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]

# Коэффициенты выплат
ROULETTE_PAYOUTS = {
    RouletteBetType.NUMBER: 35,        # 35:1
    RouletteBetType.RED: 1,            # 1:1
    RouletteBetType.BLACK: 1,          # 1:1
    RouletteBetType.EVEN: 1,           # 1:1
    RouletteBetType.ODD: 1,            # 1:1
    RouletteBetType.LOW: 1,            # 1:1
    RouletteBetType.HIGH: 1,           # 1:1
    RouletteBetType.FIRST_DOZEN: 2,    # 2:1
    RouletteBetType.SECOND_DOZEN: 2,   # 2:1
    RouletteBetType.THIRD_DOZEN: 2,    # 2:1
    RouletteBetType.FIRST_COLUMN: 2,   # 2:1
    RouletteBetType.SECOND_COLUMN: 2,  # 2:1
    RouletteBetType.THIRD_COLUMN: 2,   # 2:1
}

class RouletteBet(discord.app_commands.Group):
    """Группа команд для игры в рулетку"""
    
    @app_commands.command(name="bet", description="Сделать ставку в рулетке")
    @app_commands.describe(
        amount="Размер ставки (мин. 10)",
        bet_type="Тип ставки",
        number="Если ставка на конкретное число (0-36)"
    )
    @app_commands.choices(bet_type=[
        app_commands.Choice(name="Красное", value="red"),
        app_commands.Choice(name="Черное", value="black"),
        app_commands.Choice(name="Четное", value="even"),
        app_commands.Choice(name="Нечетное", value="odd"),
        app_commands.Choice(name="1-18 (Низкие)", value="1-18"),
        app_commands.Choice(name="19-36 (Высокие)", value="19-36"),
        app_commands.Choice(name="1-я дюжина (1-12)", value="1st dozen"),
        app_commands.Choice(name="2-я дюжина (13-24)", value="2nd dozen"),
        app_commands.Choice(name="3-я дюжина (25-36)", value="3rd dozen"),
        app_commands.Choice(name="1-я колонка (1,4,7,...)", value="1st column"),
        app_commands.Choice(name="2-я колонка (2,5,8,...)", value="2nd column"),
        app_commands.Choice(name="3-я колонка (3,6,9,...)", value="3rd column"),
        app_commands.Choice(name="Число", value="number"),
    ])
    async def roulette_bet(self, interaction: discord.Interaction, amount: int, 
                          bet_type: str, number: Optional[int] = None):
        """Сделать ставку в рулетке"""
        try:
            if amount < 10:
                await interaction.response.send_message(
                    content="Минимальная ставка - 10 монет!",
                    ephemeral=True
                )
                return
            
            # Проверяем валидность ставки
            bet_type_enum = RouletteBetType(bet_type)
            if bet_type_enum == RouletteBetType.NUMBER and number is None:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Неверная ставка",
                        description="При ставке на число вы должны указать номер.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            if number is not None and (number < 0 or number > 36):
                await interaction.response.send_message(
                    content="Номер должен быть от 0 до 36!",
                    ephemeral=True
                )
                return
            
            user_id = str(interaction.user.id)
            
            # Получаем пользователя из хранилища
            user = storage.get_user(user_id)
            
            if not user:
                # Создаем нового пользователя
                user = storage.create_user(
                    user_id=user_id,
                    username=interaction.user.display_name,
                    discriminator=interaction.user.discriminator or "",
                    balance=10000,
                    is_admin=False
                )
            
            # Проверяем, достаточно ли средств
            if user.balance < amount:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Недостаточно средств",
                        description=f"У вас только **{format_number(user.balance)}** монет, но вы ставите **{format_number(amount)}** монет.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            # Вращаем рулетку (0-36)
            result_number = get_random_int(0, 36)
            
            # Определяем цвет выпавшего числа (0 - зеленый)
            result_color = "green"
            if result_number in RED_NUMBERS:
                result_color = "red"
            elif result_number in BLACK_NUMBERS:
                result_color = "black"
            
            # Проверяем выигрыш
            is_win = False
            
            if bet_type_enum == RouletteBetType.NUMBER:
                is_win = result_number == number
            elif bet_type_enum == RouletteBetType.RED:
                is_win = result_color == "red"
            elif bet_type_enum == RouletteBetType.BLACK:
                is_win = result_color == "black"
            elif bet_type_enum == RouletteBetType.EVEN:
                is_win = result_number != 0 and result_number % 2 == 0
            elif bet_type_enum == RouletteBetType.ODD:
                is_win = result_number % 2 == 1
            elif bet_type_enum == RouletteBetType.LOW:
                is_win = result_number >= 1 and result_number <= 18
            elif bet_type_enum == RouletteBetType.HIGH:
                is_win = result_number >= 19 and result_number <= 36
            elif bet_type_enum == RouletteBetType.FIRST_DOZEN:
                is_win = result_number >= 1 and result_number <= 12
            elif bet_type_enum == RouletteBetType.SECOND_DOZEN:
                is_win = result_number >= 13 and result_number <= 24
            elif bet_type_enum == RouletteBetType.THIRD_DOZEN:
                is_win = result_number >= 25 and result_number <= 36
            elif bet_type_enum == RouletteBetType.FIRST_COLUMN:
                is_win = result_number % 3 == 1
            elif bet_type_enum == RouletteBetType.SECOND_COLUMN:
                is_win = result_number % 3 == 2
            elif bet_type_enum == RouletteBetType.THIRD_COLUMN:
                is_win = result_number % 3 == 0 and result_number != 0
            
            # Рассчитываем выигрыш
            win_amount = 0
            new_balance = user.balance - amount  # Вычитаем ставку
            
            if is_win:
                multiplier = ROULETTE_PAYOUTS[bet_type_enum]
                win_amount = amount * multiplier + amount  # Выигрыш + первоначальная ставка
                new_balance += win_amount
            
            # Обновляем баланс пользователя
            storage.update_user_balance(user_id, new_balance)
            
            # Добавляем запись в историю игр
            storage.add_game_history(
                user_id=user_id,
                game_type=GameType.ROULETTE,
                bet_amount=amount,
                outcome=GameOutcome.WIN if is_win else GameOutcome.LOSS,
                win_amount=win_amount - amount if is_win else 0  # Записываем только чистый выигрыш
            )
            
            # Создаем сообщение о результате
            result_emoji = "🔴" if result_color == "red" else "⚫" if result_color == "black" else "🟢"
            result_text = f"{result_emoji} **{result_number}** {result_emoji}"
            
            bet_display_name = bet_type
            if bet_type_enum == RouletteBetType.NUMBER:
                bet_display_name = f"Число {number}"
            
            await interaction.response.send_message(
                embed=create_embed(
                    title="Результаты рулетки",
                    description=f"Шарик остановился на: {result_text}",
                    color=0x57F287 if is_win else 0xED4245,  # Зеленый если выигрыш, красный если проигрыш
                    fields=[
                        {"name": "Ваша ставка", "value": f"**{format_number(amount)}** монет на **{bet_display_name}**", "inline": True},
                        {"name": "Результат", "value": f"{'Выигрыш! +' if is_win else 'Проигрыш! -'}**{format_number(win_amount if is_win else amount)}** монет", "inline": True},
                        {"name": "Новый баланс", "value": f"**{format_number(new_balance)}** монет", "inline": False}
                    ],
                    footer="PutinZov Casino | Рулетка"
                )
            )
        except Exception as e:
            print(f"Error executing roulette bet command: {e}")
            await interaction.response.send_message(
                content="Произошла ошибка при обработке ставки!",
                ephemeral=True
            )
    
    @app_commands.command(name="help", description="Узнать правила игры в рулетку")
    async def roulette_help(self, interaction: discord.Interaction):
        """Показать помощь по рулетке"""
        await interaction.response.send_message(
            embed=create_embed(
                title="Рулетка - Правила игры",
                description="Рулетка - это игра, где шарик вращается по колесу с пронумерованными ячейками от 0 до 36.",
                color=0xFFD700,  # Золотой
                fields=[
                    {
                        "name": "Варианты ставок",
                        "value": 
                            "**Число**: Ставка на конкретное число (0-36). Выплата 35:1\n" +
                            "**Красное/Черное**: Ставка на цвет. Выплата 1:1\n" +
                            "**Четное/Нечетное**: Ставка на четные или нечетные числа. Выплата 1:1\n" +
                            "**1-18/19-36**: Ставка на низкие или высокие числа. Выплата 1:1\n" +
                            "**Дюжины**: Ставка на 1-12, 13-24 или 25-36. Выплата 2:1\n" +
                            "**Колонки**: Ставка на колонку. Выплата 2:1"
                    },
                    {
                        "name": "Команда",
                        "value": "`/roulette bet <сумма> <тип_ставки> [номер]`"
                    },
                    {
                        "name": "Примеры",
                        "value": 
                            "`/roulette bet 100 red` - Ставка 100 на красное\n" +
                            "`/roulette bet 500 1st dozen` - Ставка 500 на 1-ю дюжину (1-12)"
                    }
                ],
                footer="PutinZov Casino | Рулетка"
            )
        )

#########################
# КОМАНДЫ БЛЭКДЖЕКА
#########################

# Типы карт
SUITS = ['♥', '♦', '♣', '♠']  # Масти
CARD_VALUES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']  # Значения карт

class Card:
    """Класс карты"""
    def __init__(self, suit, value):
        self.suit = suit
        self.value = value
        # Определяем числовое значение карты
        if value == 'A':
            self.numeric_value = 11  # Туз изначально имеет значение 11
        elif value in ['J', 'Q', 'K']:
            self.numeric_value = 10  # Фигурные карты имеют значение 10
        else:
            self.numeric_value = int(value)  # Числовые карты имеют соответствующее значение
    
    def __str__(self):
        return f"[{self.value}{self.suit}]"

class BlackjackHand:
    """Рука в блэкджеке"""
    def __init__(self, cards=None):
        self.cards = cards or []
        self.value = 0
        self.is_soft = False  # True, если туз считается за 11
        self.update_value()
    
    def add_card(self, card):
        """Добавить карту в руку"""
        self.cards.append(card)
        self.update_value()
    
    def update_value(self):
        """Обновить значение руки"""
        value = 0
        aces = 0
        
        # Подсчитываем значение всех карт
        for card in self.cards:
            value += card.numeric_value
            if card.value == 'A':
                aces += 1
        
        # Корректируем для тузов, если необходимо
        while value > 21 and aces > 0:
            value -= 10  # Меняем значение туза с 11 на 1
            aces -= 1
        
        # Определяем, является ли рука "мягкой" (есть туз со значением 11)
        self.is_soft = aces > 0 and value <= 21
        
        self.value = value
    
    def format(self, hide_first_card=False):
        """Форматировать руку для отображения"""
        if hide_first_card and len(self.cards) > 0:
            return f"[?] {' '.join(str(card) for card in self.cards[1:])}"
        
        cards_display = ' '.join(str(card) for card in self.cards)
        value_display = f"{self.value} (Soft)" if self.is_soft else str(self.value)
        
        return f"{cards_display} = {value_display}"

class BlackjackGame:
    """Игра в блэкджек"""
    def __init__(self, user_id, bet_amount):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.deck = self.create_deck()
        self.player = BlackjackHand()
        self.dealer = BlackjackHand()
        self.game_over = False
        self.outcome = None
    
    @staticmethod
    def create_deck():
        """Создать колоду карт"""
        deck = [Card(suit, value) for suit in SUITS for value in CARD_VALUES]
        random.shuffle(deck)
        return deck
    
    def deal_initial_cards(self):
        """Раздать начальные карты"""
        self.player.add_card(self.deck.pop())
        self.dealer.add_card(self.deck.pop())
        self.player.add_card(self.deck.pop())
        self.dealer.add_card(self.deck.pop())
        
        # Проверяем на натуральный блэкджек
        if self.player.value == 21:
            if self.dealer.value == 21:
                self.game_over = True
                self.outcome = GameOutcome.PUSH
            else:
                self.game_over = True
                self.outcome = GameOutcome.BLACKJACK
        
        return self.game_over
    
    def player_hit(self):
        """Игрок берет еще карту"""
        card = self.deck.pop()
        self.player.add_card(card)
        
        if self.player.value > 21:
            self.game_over = True
            self.outcome = GameOutcome.LOSS
        
        return self.game_over
    
    def dealer_play(self):
        """Ход дилера (берет карты до 17 или больше)"""
        while self.dealer.value < 17:
            self.dealer.add_card(self.deck.pop())
        
        # Определяем результат
        if self.dealer.value > 21:
            self.outcome = GameOutcome.WIN
        elif self.dealer.value > self.player.value:
            self.outcome = GameOutcome.LOSS
        elif self.dealer.value < self.player.value:
            self.outcome = GameOutcome.WIN
        else:
            self.outcome = GameOutcome.PUSH
        
        self.game_over = True
        return self.outcome

# Хранение активных игр в блэкджек
active_blackjack_games = {}

@bot.tree.command(name="blackjack", description="Сыграть в блэкджек")
@app_commands.describe(amount="Размер ставки (мин. 10)")
async def blackjack(interaction: discord.Interaction, amount: int):
    """Команда для игры в блэкджек"""
    try:
        if amount < 10:
            await interaction.response.send_message(
                content="Минимальная ставка - 10 монет!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        # Проверяем, не играет ли уже пользователь
        if user_id in active_blackjack_games:
            await interaction.response.send_message(
                content="У вас уже есть активная игра в блэкджек!",
                ephemeral=True
            )
            return
        
        # Получаем пользователя из хранилища
        user = storage.get_user(user_id)
        
        if not user:
            # Создаем нового пользователя
            user = storage.create_user(
                user_id=user_id,
                username=interaction.user.display_name,
                discriminator=interaction.user.discriminator or "",
                balance=10000,
                is_admin=False
            )
        
        # Проверяем, достаточно ли средств
        if user.balance < amount:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Недостаточно средств",
                    description=f"У вас только **{format_number(user.balance)}** монет, но вы ставите **{format_number(amount)}** монет.",
                    color=0xED4245  # Красный
                ),
                ephemeral=True
            )
            return
        
        # Создаем игру
        game = BlackjackGame(user_id, amount)
        active_blackjack_games[user_id] = game
        
        # Раздаем начальные карты
        initial_result = game.deal_initial_cards()
        
        # Если игра завершилась сразу (натуральный блэкджек)
        if initial_result:
            await handle_blackjack_end(interaction, game)
            return
        
        # Создаем кнопки для хода и стойки
        hit_button = discord.ui.Button(style=discord.ButtonStyle.primary, label="Еще карту", custom_id="hit")
        stand_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Хватит", custom_id="stand")
        
        view = discord.ui.View()
        view.add_item(hit_button)
        view.add_item(stand_button)
        
        # Отправляем начальное состояние игры
        embed = create_embed(
            title="Блэкджек",
            description=f"Вы поставили **{format_number(amount)}** монет.",
            color=0xFFD700,  # Золотой
            fields=[
                {"name": "Рука дилера", "value": game.dealer.format(hide_first_card=True), "inline": False},
                {"name": "Ваша рука", "value": game.player.format(), "inline": False}
            ],
            footer="PutinZov Casino | Блэкджек - Еще карту или хватит?"
        )
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # Ожидаем взаимодействия с кнопками
        def check(interaction_check):
            return interaction_check.user.id == interaction.user.id and \
                   interaction_check.data.get("custom_id") in ["hit", "stand"]
        
        try:
            # Ожидаем действие пользователя (60 секунд таймаут)
            button_interaction = await bot.wait_for("interaction", check=check, timeout=60.0)
            
            # Обрабатываем ход
            if button_interaction.data.get("custom_id") == "hit":
                await handle_blackjack_hit(button_interaction, game, view)
            elif button_interaction.data.get("custom_id") == "stand":
                await handle_blackjack_stand(button_interaction, game)
        
        except asyncio.TimeoutError:
            # Если пользователь не ответил вовремя
            if user_id in active_blackjack_games:
                del active_blackjack_games[user_id]
                
            await interaction.followup.send(
                embed=create_embed(
                    title="Время вышло",
                    description="Вы слишком долго думали над ходом. Игра отменена, ставка возвращена.",
                    color=0xED4245  # Красный
                )
            )
    
    except Exception as e:
        print(f"Error executing blackjack command: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при запуске игры в блэкджек!",
            ephemeral=True
        )

async def handle_blackjack_hit(interaction: discord.Interaction, game: BlackjackGame, view: discord.ui.View):
    """Обработчик нажатия кнопки 'Еще карту'"""
    try:
        # Игрок берет еще карту
        result = game.player_hit()
        
        # Если игрок перебрал (bust)
        if result:
            await handle_blackjack_end(interaction, game)
            return
        
        # Обновляем информацию о игре
        embed = create_embed(
            title="Блэкджек",
            description=f"Вы поставили **{format_number(game.bet_amount)}** монет.",
            color=0xFFD700,  # Золотой
            fields=[
                {"name": "Рука дилера", "value": game.dealer.format(hide_first_card=True), "inline": False},
                {"name": "Ваша рука", "value": game.player.format(), "inline": False}
            ],
            footer="PutinZov Casino | Блэкджек - Еще карту или хватит?"
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
        
        # Ожидаем следующее взаимодействие с кнопками
        def check(interaction_check):
            return interaction_check.user.id == interaction.user.id and \
                   interaction_check.data.get("custom_id") in ["hit", "stand"]
        
        try:
            # Ожидаем действие пользователя (60 секунд таймаут)
            button_interaction = await bot.wait_for("interaction", check=check, timeout=60.0)
            
            # Обрабатываем ход
            if button_interaction.data.get("custom_id") == "hit":
                await handle_blackjack_hit(button_interaction, game, view)
            elif button_interaction.data.get("custom_id") == "stand":
                await handle_blackjack_stand(button_interaction, game)
        
        except asyncio.TimeoutError:
            # Если пользователь не ответил вовремя
            if game.user_id in active_blackjack_games:
                del active_blackjack_games[game.user_id]
                
            await interaction.followup.send(
                embed=create_embed(
                    title="Время вышло",
                    description="Вы слишком долго думали над ходом. Игра отменена, ставка возвращена.",
                    color=0xED4245  # Красный
                )
            )
    
    except Exception as e:
        print(f"Error in handle_blackjack_hit: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при обработке хода!",
            ephemeral=True
        )

async def handle_blackjack_stand(interaction: discord.Interaction, game: BlackjackGame):
    """Обработчик нажатия кнопки 'Хватит'"""
    try:
        # Отправляем сообщение о том, что игрок решил остановиться
        embed = create_embed(
            title="Блэкджек",
            description=f"Вы поставили **{format_number(game.bet_amount)}** монет и решили остановиться.",
            color=0xFFD700,  # Золотой
            fields=[
                {"name": "Рука дилера", "value": game.dealer.format(), "inline": False},
                {"name": "Ваша рука", "value": game.player.format(), "inline": False}
            ],
            footer="PutinZov Casino | Блэкджек - Ход дилера"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Ход дилера
        await asyncio.sleep(1)  # Пауза для драматического эффекта
        game.dealer_play()
        
        # Завершаем игру
        await handle_blackjack_end(interaction, game)
    
    except Exception as e:
        print(f"Error in handle_blackjack_stand: {e}")
        await interaction.followup.send(
            content="Произошла ошибка при обработке хода дилера!",
            ephemeral=True
        )

async def handle_blackjack_end(interaction: discord.Interaction, game: BlackjackGame):
    """Обработчик завершения игры в блэкджек"""
    try:
        user_id = game.user_id
        
        # Удаляем игру из активных
        if user_id in active_blackjack_games:
            del active_blackjack_games[user_id]
        
        # Получаем пользователя из хранилища
        user = storage.get_user(user_id)
        
        if not user:
            await interaction.followup.send(
                content="Ошибка: пользователь не найден!",
                ephemeral=True
            )
            return
        
        # Подготавливаем результаты
        result_title = ""
        result_description = ""
        result_color = 0
        win_amount = 0
        
        # Вычитаем ставку из баланса пользователя
        new_balance = user.balance - game.bet_amount
        
        # Рассчитываем выигрыш в зависимости от результата
        if game.outcome == GameOutcome.WIN:
            win_amount = game.bet_amount * 2  # Ставка + 100% выигрыш
            new_balance += win_amount
            result_title = "Вы выиграли!"
            result_description = f"Вы выиграли **{format_number(game.bet_amount)}** монет!"
            result_color = 0x57F287  # Зеленый
        
        elif game.outcome == GameOutcome.BLACKJACK:
            win_amount = int(game.bet_amount * 2.5)  # Ставка + 150% выигрыш
            new_balance += win_amount
            result_title = "Блэкджек!"
            result_description = f"У вас блэкджек! Вы выиграли **{format_number(win_amount - game.bet_amount)}** монет!"
            result_color = 0x5865F2  # Синий Discord
        
        elif game.outcome == GameOutcome.PUSH:
            win_amount = game.bet_amount  # Возврат ставки
            new_balance += win_amount
            result_title = "Ничья"
            result_description = "Ничья! Ваша ставка возвращена."
            result_color = 0xFFD700  # Золотой
        
        elif game.outcome == GameOutcome.LOSS:
            result_title = "Вы проиграли"
            result_description = f"Вы проиграли **{format_number(game.bet_amount)}** монет."
            result_color = 0xED4245  # Красный
        
        # Обновляем баланс пользователя
        storage.update_user_balance(user_id, new_balance)
        
        # Добавляем запись в историю игр
        storage.add_game_history(
            user_id=user_id,
            game_type=GameType.BLACKJACK,
            bet_amount=game.bet_amount,
            outcome=game.outcome,
            win_amount=0 if win_amount == 0 else win_amount - game.bet_amount  # Записываем только чистый выигрыш
        )
        
        # Создаем embed с результатом
        embed = create_embed(
            title=result_title,
            description=f"{result_description}\nВаш новый баланс: **{format_number(new_balance)}** монет.",
            color=result_color,
            fields=[
                {"name": "Рука дилера", "value": game.dealer.format(), "inline": False},
                {"name": "Ваша рука", "value": game.player.format(), "inline": False}
            ],
            footer="PutinZov Casino | Блэкджек"
        )
        
        # Отправляем результат
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed)
    
    except Exception as e:
        print(f"Error in handle_blackjack_end: {e}")
        await interaction.followup.send(
            content="Произошла ошибка при обработке результатов игры!",
            ephemeral=True
        )

#########################
# КОМАНДЫ СЛОТОВ
#########################

# Определение символов слотов и их значений
SLOT_SYMBOLS = [
    {"name": "🍒", "value": 1},   # Вишня
    {"name": "🍋", "value": 2},   # Лимон
    {"name": "🍊", "value": 3},   # Апельсин
    {"name": "🍇", "value": 4},   # Виноград
    {"name": "🔔", "value": 5},   # Колокольчик
    {"name": "💎", "value": 6},   # Бриллиант
    {"name": "7️⃣", "value": 7}    # Семерка
]

# Таблица выплат
SLOTS_PAYOUTS = {
    "🍒🍒🍒": {"multiplier": 5, "outcome": GameOutcome.SMALL_WIN},
    "🍋🍋🍋": {"multiplier": 8, "outcome": GameOutcome.SMALL_WIN},
    "🍊🍊🍊": {"multiplier": 10, "outcome": GameOutcome.MEDIUM_WIN},
    "🍇🍇🍇": {"multiplier": 15, "outcome": GameOutcome.MEDIUM_WIN},
    "🔔🔔🔔": {"multiplier": 20, "outcome": GameOutcome.BIG_WIN},
    "💎💎💎": {"multiplier": 30, "outcome": GameOutcome.BIG_WIN},
    "7️⃣7️⃣7️⃣": {"multiplier": 50, "outcome": GameOutcome.JACKPOT},
}

@bot.tree.command(name="slots", description="Сыграть в слоты")
@app_commands.describe(amount="Размер ставки (мин. 10)")
async def slots(interaction: discord.Interaction, amount: int):
    """Команда для игры в слоты"""
    try:
        if amount < 10:
            await interaction.response.send_message(
                content="Минимальная ставка - 10 монет!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        # Получаем пользователя из хранилища
        user = storage.get_user(user_id)
        
        if not user:
            # Создаем нового пользователя
            user = storage.create_user(
                user_id=user_id,
                username=interaction.user.display_name,
                discriminator=interaction.user.discriminator or "",
                balance=10000,
                is_admin=False
            )
        
        # Проверяем, достаточно ли средств
        if user.balance < amount:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Недостаточно средств",
                    description=f"У вас только **{format_number(user.balance)}** монет, но вы ставите **{format_number(amount)}** монет.",
                    color=0xED4245  # Красный
                ),
                ephemeral=True
            )
            return
        
        # Откладываем ответ, чтобы показать "бот думает" во время вращения
        await interaction.response.defer()
        
        # Имитируем вращение слотов
        await asyncio.sleep(1.5)
        
        # Генерируем результат
        reels = []
        for _ in range(3):
            symbol_index = get_random_int(0, len(SLOT_SYMBOLS) - 1)
            reels.append(SLOT_SYMBOLS[symbol_index]["name"])
        
        # Проверяем выигрыш
        reel_string = "".join(reels)
        win_data = SLOTS_PAYOUTS.get(reel_string)
        
        is_win = win_data is not None
        win_amount = 0
        outcome = GameOutcome.NO_MATCH
        
        # Вычитаем ставку из баланса
        new_balance = user.balance - amount
        
        if is_win:
            win_amount = amount * win_data["multiplier"]
            outcome = win_data["outcome"]
            new_balance += win_amount
        
        # Обновляем баланс пользователя
        storage.update_user_balance(user_id, new_balance)
        
        # Добавляем запись в историю игр
        storage.add_game_history(
            user_id=user_id,
            game_type=GameType.SLOTS,
            bet_amount=amount,
            outcome=outcome,
            win_amount=win_amount - amount if is_win else 0  # Записываем только чистый выигрыш
        )
        
        # Создаем визуальное отображение слотов
        slot_display = f"""
╔═════╦═════╦═════╗
║  {reels[0]}  ║  {reels[1]}  ║  {reels[2]}  ║
╚═════╩═════╩═════╝"""
        
        # Определяем заголовок и цвет в зависимости от результата
        result_title = ""
        result_color = 0
        
        if is_win:
            if outcome == GameOutcome.SMALL_WIN:
                result_title = "Небольшой выигрыш!"
                result_color = 0x3498DB  # Голубой
            elif outcome == GameOutcome.MEDIUM_WIN:
                result_title = "Средний выигрыш!"
                result_color = 0x2ECC71  # Зеленый
            elif outcome == GameOutcome.BIG_WIN:
                result_title = "Крупный выигрыш!"
                result_color = 0xF1C40F  # Желтый
            elif outcome == GameOutcome.JACKPOT:
                result_title = "🎉 ДЖЕКПОТ! 🎉"
                result_color = 0xE74C3C  # Красный
            else:
                result_title = "Вы выиграли!"
                result_color = 0x57F287  # Зеленый
        else:
            result_title = "Нет совпадений"
            result_color = 0xED4245  # Красный
        
        # Создаем embed с результатом
        embed = create_embed(
            title=f"Слоты - {result_title}",
            description=f"{slot_display}\n\nВы поставили **{format_number(amount)}** монет.",
            color=result_color,
            fields=[
                {
                    "name": "Результат",
                    "value": "🎉 Вы выиграли " + f"**{format_number(win_amount)}** монет! ({win_data['multiplier']}x множитель)" if is_win else f"❌ Вы проиграли **{format_number(amount)}** монет.",
                    "inline": False
                },
                {"name": "Новый баланс", "value": f"**{format_number(new_balance)}** монет", "inline": False}
            ],
            footer="PutinZov Casino | Слоты"
        )
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        print(f"Error executing slots command: {e}")
        await interaction.followup.send(
            content="Произошла ошибка при обработке игры в слоты!",
            ephemeral=True
        )

#########################
# КОМАНДА ТАБЛИЦЫ ЛИДЕРОВ
#########################

@bot.tree.command(name="leaderboard", description="Посмотреть список богатейших игроков")
@app_commands.describe(scope="Масштаб таблицы лидеров")
@app_commands.choices(scope=[
    app_commands.Choice(name="Глобальная", value="global"),
    app_commands.Choice(name="Сервер", value="server")
])
async def leaderboard(interaction: discord.Interaction, scope: str = "server"):
    """Команда для отображения таблицы лидеров"""
    try:
        # Получаем топ-10 пользователей
        top_users = storage.get_users_by_balance_desc(10)
        
        if not top_users:
            await interaction.response.send_message(
                embed=create_embed(
                    title="Таблица лидеров пуста",
                    description="Еще никто не играл в игры.",
                    color=0xED4245,  # Красный
                    footer="PutinZov Casino | Таблица лидеров"
                ),
                ephemeral=True
            )
            return
        
        # В реальной имплементации здесь можно фильтровать пользователей по серверу
        # для "server" scope, но в демо мы показываем всех пользователей
        
        # Форматируем таблицу лидеров
        leaderboard_text = ""
        
        for i, user in enumerate(top_users):
            medal = ""
            if i == 0:
                medal = "🥇 "
            elif i == 1:
                medal = "🥈 "
            elif i == 2:
                medal = "🥉 "
            else:
                medal = f"{i + 1}. "
            
            leaderboard_text += f"{medal}**{user.username}** - {format_number(user.balance)} монет"
            
            # Добавляем статистику
            if user.games_played > 0:
                win_rate = calculate_win_rate(user.games_won, user.games_played)
                leaderboard_text += f" ({user.games_won}/{user.games_played} игр, {win_rate} побед)"
            
            leaderboard_text += "\n"
        
        scope_name = "Глобальная" if scope == "global" else "Серверная"
        
        embed = create_embed(
            title=f"{scope_name} таблица лидеров",
            description="Самые богатые игроки казино:",
            color=0xFFD700,  # Золотой
            fields=[
                {"name": "Лучшие игроки", "value": leaderboard_text, "inline": False}
            ],
            footer="PutinZov Casino | Таблица лидеров"
        )
        
        await interaction.response.send_message(embed=embed)
    
    except Exception as e:
        print(f"Error executing leaderboard command: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при отображении таблицы лидеров!",
            ephemeral=True
        )

#########################
# АДМИНИСТРАТИВНЫЕ КОМАНДЫ
#########################

class AdminCommands(discord.app_commands.Group):
    """Группа административных команд"""
    
    def __init__(self):
        super().__init__(name="admin", description="Административные команды для управления казино")
    
    @app_commands.command(name="give", description="Выдать монеты пользователю")
    @app_commands.describe(user="Пользователь, которому выдать монеты",
                         amount="Количество монет для выдачи")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_give(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Команда для выдачи монет пользователю"""
        try:
            # Проверка прав администратора
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Доступ запрещен",
                        description="Для использования этой команды необходимы права администратора.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            if amount < 1:
                await interaction.response.send_message(
                    content="Количество монет должно быть больше 0!",
                    ephemeral=True
                )
                return
            
            user_id = str(user.id)
            
            # Получаем пользователя из хранилища или создаем нового
            db_user = storage.get_user(user_id)
            
            if not db_user:
                db_user = storage.create_user(
                    user_id=user_id,
                    username=user.display_name,
                    discriminator=user.discriminator or "",
                    balance=10000,
                    is_admin=False
                )
            
            # Обновляем баланс
            new_balance = db_user.balance + amount
            storage.update_user_balance(user_id, new_balance)
            
            await interaction.response.send_message(
                embed=create_embed(
                    title="Монеты добавлены",
                    description=f"Вы выдали **{format_number(amount)}** монет пользователю **{user.display_name}**.\nЕго новый баланс: **{format_number(new_balance)}** монет.",
                    color=0x57F287,  # Зеленый
                    thumbnail=user.display_avatar.url,
                    footer="PutinZov Casino | Админ-команда"
                )
            )
        
        except Exception as e:
            print(f"Error executing admin give command: {e}")
            await interaction.response.send_message(
                content="Произошла ошибка при выдаче монет!",
                ephemeral=True
            )
    
    @app_commands.command(name="take", description="Забрать монеты у пользователя")
    @app_commands.describe(user="Пользователь, у которого забрать монеты",
                         amount="Количество монет для изъятия")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_take(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Команда для изъятия монет у пользователя"""
        try:
            # Проверка прав администратора
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Доступ запрещен",
                        description="Для использования этой команды необходимы права администратора.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            if amount < 1:
                await interaction.response.send_message(
                    content="Количество монет должно быть больше 0!",
                    ephemeral=True
                )
                return
            
            user_id = str(user.id)
            
            # Получаем пользователя из хранилища
            db_user = storage.get_user(user_id)
            
            if not db_user:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Пользователь не найден",
                        description=f"**{user.display_name}** еще не имеет аккаунта.",
                        color=0xED4245,  # Красный
                        footer="PutinZov Casino | Админ-команда"
                    ),
                    ephemeral=True
                )
                return
            
            # Проверяем, достаточно ли монет у пользователя
            if db_user.balance < amount:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Недостаточно средств",
                        description=f"У **{user.display_name}** только **{format_number(db_user.balance)}** монет, но вы пытаетесь забрать **{format_number(amount)}** монет.",
                        color=0xED4245,  # Красный
                        footer="PutinZov Casino | Админ-команда"
                    ),
                    ephemeral=True
                )
                return
            
            # Обновляем баланс
            new_balance = db_user.balance - amount
            storage.update_user_balance(user_id, new_balance)
            
            await interaction.response.send_message(
                embed=create_embed(
                    title="Монеты изъяты",
                    description=f"Вы забрали **{format_number(amount)}** монет у пользователя **{user.display_name}**.\nЕго новый баланс: **{format_number(new_balance)}** монет.",
                    color=0xED4245,  # Красный
                    thumbnail=user.display_avatar.url,
                    footer="PutinZov Casino | Админ-команда"
                )
            )
        
        except Exception as e:
            print(f"Error executing admin take command: {e}")
            await interaction.response.send_message(
                content="Произошла ошибка при изъятии монет!",
                ephemeral=True
            )
    
    @app_commands.command(name="reset", description="Сбросить баланс пользователя до указанной суммы")
    @app_commands.describe(user="Пользователь, чей баланс нужно сбросить",
                         amount="Сумма для сброса (по умолчанию: 10,000)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_reset(self, interaction: discord.Interaction, user: discord.User, amount: int = 10000):
        """Команда для сброса баланса пользователя"""
        try:
            # Проверка прав администратора
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Доступ запрещен",
                        description="Для использования этой команды необходимы права администратора.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            if amount < 0:
                await interaction.response.send_message(
                    content="Сумма не может быть отрицательной!",
                    ephemeral=True
                )
                return
            
            user_id = str(user.id)
            
            # Сбрасываем баланс пользователя
            db_user = storage.reset_user_balance(user_id, amount)
            
            if not db_user:
                # Создаем нового пользователя с указанным балансом
                db_user = storage.create_user(
                    user_id=user_id,
                    username=user.display_name,
                    discriminator=user.discriminator or "",
                    balance=amount,
                    is_admin=False
                )
            
            await interaction.response.send_message(
                embed=create_embed(
                    title="Баланс сброшен",
                    description=f"Баланс пользователя **{user.display_name}** был сброшен до **{format_number(amount)}** монет.",
                    color=0x5865F2,  # Синий Discord
                    thumbnail=user.display_avatar.url,
                    footer="PutinZov Casino | Админ-команда"
                )
            )
        
        except Exception as e:
            print(f"Error executing admin reset command: {e}")
            await interaction.response.send_message(
                content="Произошла ошибка при сбросе баланса!",
                ephemeral=True
            )
    
    @app_commands.command(name="stats", description="Просмотреть статистику экономики сервера")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_stats(self, interaction: discord.Interaction):
        """Команда для просмотра статистики экономики"""
        try:
            # Проверка прав администратора
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Доступ запрещен",
                        description="Для использования этой команды необходимы права администратора.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            # Получаем статистику
            total_users = storage.get_total_users()
            total_coins = storage.get_total_coins()
            games_played_today = storage.get_games_played_today()
            
            # Получаем топ-5 пользователей
            top_users = storage.get_users_by_balance_desc(5)
            
            # Форматируем список топ-пользователей
            top_users_list = ""
            for i, user in enumerate(top_users):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i + 1}."
                top_users_list += f"{medal} **{user.username}**: {format_number(user.balance)} монет\n"
            
            if not top_users_list:
                top_users_list = "Пользователей пока нет"
            
            await interaction.response.send_message(
                embed=create_embed(
                    title="Статистика экономики казино",
                    description="Текущая статистика экономики PutinZov Casino",
                    color=0xFFD700,  # Золотой
                    fields=[
                        {"name": "Всего пользователей", "value": str(total_users), "inline": True},
                        {"name": "Всего монет", "value": format_number(total_coins), "inline": True},
                        {"name": "Игр сегодня", "value": str(games_played_today), "inline": True},
                        {"name": "Топ-5 богатейших пользователей", "value": top_users_list, "inline": False}
                    ],
                    footer="PutinZov Casino | Админ-статистика"
                )
            )
        
        except Exception as e:
            print(f"Error executing admin stats command: {e}")
            await interaction.response.send_message(
                content="Произошла ошибка при получении статистики!",
                ephemeral=True
            )

#########################
# КОМАНДЫ ПОМОЩИ
#########################

@bot.tree.command(name="help", description="Получить помощь по командам казино")
@app_commands.describe(category="Категория команд")
@app_commands.choices(category=[
    app_commands.Choice(name="Экономика", value="economy"),
    app_commands.Choice(name="Игры", value="games"),
    app_commands.Choice(name="Администрирование", value="admin")
])
async def help_command(interaction: discord.Interaction, category: str = None):
    """Команда помощи"""
    try:
        if not category:
            # Общая помощь
            embed = create_embed(
                title="PutinZov Casino - Помощь",
                description="Добро пожаловать в PutinZov Casino! Доступные категории команд:",
                color=0x5865F2,  # Синий Discord
                fields=[
                    {
                        "name": "Команды экономики",
                        "value": "Команды для управления монетами и экономикой\nИспользуйте `/help economy` для подробностей",
                        "inline": False
                    },
                    {
                        "name": "Игровые команды",
                        "value": "Играйте в казино-игры и выигрывайте монеты\nИспользуйте `/help games` для подробностей",
                        "inline": False
                    },
                    {
                        "name": "Административные команды",
                        "value": "Команды для администраторов сервера\nИспользуйте `/help admin` для подробностей",
                        "inline": False
                    },
                    {
                        "name": "Начало работы",
                        "value": "Каждый пользователь начинает с 10,000 монет! Используйте их для игры и попробуйте стать самым богатым игроком.",
                        "inline": False
                    }
                ],
                footer="PutinZov Casino | Помощь"
            )
            
            await interaction.response.send_message(embed=embed)
        
        elif category == "economy":
            # Помощь по экономике
            embed = create_embed(
                title="Команды экономики",
                description="Команды для управления монетами и экономикой:",
                color=0xFFD700,  # Золотой
                fields=[
                    {
                        "name": "/balance [пользователь]",
                        "value": "Проверить свой баланс или баланс другого пользователя",
                        "inline": False
                    },
                    {
                        "name": "/daily",
                        "value": "Получить ежедневный бонус в 1,000 монет (раз в день)",
                        "inline": False
                    },
                    {
                        "name": "/transfer <пользователь> <сумма>",
                        "value": "Перевести монеты другому пользователю",
                        "inline": False
                    },
                    {
                        "name": "/leaderboard [global|server]",
                        "value": "Посмотреть самых богатых игроков на сервере или глобально",
                        "inline": False
                    }
                ],
                footer="PutinZov Casino | Команды экономики"
            )
            
            await interaction.response.send_message(embed=embed)
        
        elif category == "games":
            # Помощь по играм
            embed = create_embed(
                title="Игровые команды",
                description="Попробуйте свою удачу в этих захватывающих казино-играх:",
                color=0x57F287,  # Зеленый
                fields=[
                    {
                        "name": "Рулетка",
                        "value":
                            "`/roulette bet <сумма> <тип_ставки> [номер]` - Сделать ставку в рулетке\n" +
                            "`/roulette help` - Узнать правила рулетки",
                        "inline": False
                    },
                    {
                        "name": "Блэкджек",
                        "value": "`/blackjack <сумма>` - Сыграть в блэкджек",
                        "inline": False
                    },
                    {
                        "name": "Слоты",
                        "value": "`/slots <сумма>` - Сыграть в слоты",
                        "inline": False
                    },
                    {
                        "name": "Выплаты",
                        "value":
                            "**Рулетка**: До 35:1 (ставка на точное число)\n" +
                            "**Блэкджек**: 1:1 (победа), 3:2 (блэкджек)\n" +
                            "**Слоты**: До 50:1 (джекпот)",
                        "inline": False
                    }
                ],
                footer="PutinZov Casino | Игровые команды"
            )
            
            await interaction.response.send_message(embed=embed)
        
        elif category == "admin":
            # Помощь по админ-командам
            # Проверяем, является ли пользователь администратором
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    embed=create_embed(
                        title="Доступ запрещен",
                        description="Для просмотра административных команд необходимы права администратора.",
                        color=0xED4245  # Красный
                    ),
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="Административные команды",
                description="Команды для администраторов сервера по управлению экономикой казино:",
                color=0xED4245,  # Красный
                fields=[
                    {
                        "name": "/admin give <пользователь> <сумма>",
                        "value": "Выдать монеты пользователю",
                        "inline": False
                    },
                    {
                        "name": "/admin take <пользователь> <сумма>",
                        "value": "Забрать монеты у пользователя",
                        "inline": False
                    },
                    {
                        "name": "/admin reset <пользователь> [сумма]",
                        "value": "Сбросить баланс пользователя до 10,000 монет (или указанной суммы)",
                        "inline": False
                    },
                    {
                        "name": "/admin stats",
                        "value": "Просмотреть статистику экономики сервера",
                        "inline": False
                    }
                ],
                footer="PutinZov Casino | Административные команды"
            )
            
            await interaction.response.send_message(embed=embed)
    
    except Exception as e:
        print(f"Error executing help command: {e}")
        await interaction.response.send_message(
            content="Произошла ошибка при отображении справки!",
            ephemeral=True
        )

#########################
# РЕГИСТРАЦИЯ КОМАНД
#########################

# Регистрация групп команд
bot.tree.add_command(RouletteBet(name="roulette", description="Сыграть в рулетку"))
bot.tree.add_command(AdminCommands())

#########################
# ЗАПУСК БОТА
#########################

if __name__ == "__main__":
    if not TOKEN:
        print("ОШИБКА: Токен Discord не указан в переменных окружения.")
        print("Создайте файл .env и добавьте строку DISCORD_TOKEN=ваш_токен")
        exit(1)
    
    # Запуск бота
    bot.run(TOKEN)