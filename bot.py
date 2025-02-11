import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import filters
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import os

API_TOKEN = os.getenv("BOT_TOKEN")  # Токен берем из переменной окружения
CHANNEL_ID = os.getenv("CHANNEL_ID")  # ID канала берем из переменной окружения

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

users_received_promo = set()  # Храним пользователей, которые получили промокод

# Главное меню с кнопкой "Я подписался"
def main_keyboard():
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton("✅ Я подписался, получить промокод", callback_data="check_subscription")
    keyboard.add(button)
    return keyboard

# Команда /start
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.answer(
        f"Привет! Подпишись на наш канал и получи промокод 🎁\n\n👉 [Подписаться](https://t.me/{CHANNEL_ID})",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# Проверка подписки
@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    # Проверяем, получал ли он уже промокод
    if user_id in users_received_promo:
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(user_id, "❌ Вы уже получали промокод. Смотрите сообщения выше!")
        return

    # Проверяем подписку
    chat_member = await bot.get_chat_member(f"@{CHANNEL_ID}", user_id)
    if chat_member.status in ["member", "administrator", "creator"]:
        users_received_promo.add(user_id)  # Добавляем в список получивших промокод
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(user_id, "✅ Спасибо за подписку! Вот ваш промокод: **PROMO2024**", parse_mode="Markdown")
    else:
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(user_id, "❌ Вы не подписаны на канал. Подпишитесь и попробуйте снова!")

# Функция для рассылки сообщений
async def broadcast_message(text):
    for user_id in users_received_promo:
        try:
            await bot.send_message(user_id, text)
        except Exception as e:
            logging.error(f"Ошибка отправки {user_id}: {e}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
@dp.message_handler(commands=["broadcast"])
async def send_broadcast(message: types.Message):
    if message.from_user.id != 755781875:  # Замени на свой Telegram ID
        return
    
    text = message.text.replace("/broadcast ", "")
    await broadcast_message(text)
    await message.answer("✅ Рассылка отправлена!")
