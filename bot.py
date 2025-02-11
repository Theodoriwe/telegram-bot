import os
import logging
from datetime import datetime
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import psycopg2

# Настройки
TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')  # ID вашего канала (пока оставьте пустым)
ADMIN_ID = os.getenv('ADMIN_ID')  # Ваш ID в Telegram
DATABASE_URL = os.getenv('DATABASE_URL')

# Подключение к БД
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Создание таблицы
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        subscribed BOOLEAN DEFAULT FALSE,
        promo_code VARCHAR(20),
        promo_issued TIMESTAMP
    )
''')
conn.commit()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        cursor.execute('INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING', (user_id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Database error: {e}")

    keyboard = [[InlineKeyboardButton("Я подписался! Получить промокод", callback_data='check_sub')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📢 Подпишись на наш канал: {os.getenv('CHANNEL_LINK')}\n"
        "🎁 И получи промокод на бесплатное посещение!",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    try:
        # Проверка подписки
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        subscribed = member.status not in ['left', 'kicked']

        # Проверка наличия промокода
        cursor.execute('SELECT promo_code FROM users WHERE user_id = %s', (user_id,))
        promo_data = cursor.fetchone()

        if promo_data and promo_data[0]:
            await query.edit_message_text("⚠ Вы уже получали промокод. Проверьте предыдущие сообщения.")
            return

        if subscribed:
            # Генерация промокода
            promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            cursor.execute('''
                UPDATE users 
                SET subscribed = TRUE, promo_code = %s, promo_issued = %s 
                WHERE user_id = %s
            ''', (promo_code, datetime.now(), user_id))
            conn.commit()

            await query.edit_message_text(f"🎉 Ваш промокод: {promo_code}\n\nСохраните его!")
        else:
            await query.edit_message_text("❌ Вы не подписаны на канал. Подпишитесь и попробуйте снова.")

    except Exception as e:
        logging.error(f"Error: {e}")
        await query.edit_message_text("⚠ Произошла ошибка. Попробуйте позже.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Использование: /broadcast Ваше сообщение")
        return

    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message)
        except Exception as e:
            logging.error(f"Failed to send to {user[0]}: {e}")

    await update.message.reply_text(f"✅ Рассылка отправлена {len(users)} пользователям")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler('broadcast', broadcast))

    application.run_polling()
