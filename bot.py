import os
import psycopg2

def init_db():
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL") + "?sslmode=require")
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    subscribed BOOLEAN DEFAULT FALSE,
                    promo_code VARCHAR(20),
                    promo_issued TIMESTAMP
                )
            ''')
        conn.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()
    # Остальной код вашего бота
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
CHANNEL_ID = os.getenv('CHANNEL_ID')  # ID вашего канала
ADMIN_ID = os.getenv('ADMIN_ID')  # Ваш ID в Telegram
GROUP_ID = os.getenv('GROUP_ID')

# Проверка переменных окружения
required_env_vars = ['BOT_TOKEN', 'CHANNEL_ID', 'ADMIN_ID', 'DATABASE_URL']
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing environment variable: {var}")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Подключение к БД
def get_db_connection():
    return psycopg2.connect(os.getenv('DATABASE_URL') + "?sslmode=require")

# Создание таблицы
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    subscribed BOOLEAN DEFAULT FALSE,
                    promo_code VARCHAR(20),
                    promo_issued TIMESTAMP
                )
            ''')
            conn.commit()

init_db()

# Генерация уникального промокода
def generate_unique_promo_code(cursor):
    while True:
        promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute("SELECT COUNT(*) FROM users WHERE promo_code = %s", (promo_code,))
        if not cursor.fetchone()[0]:
            return promo_code

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING', (user_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")

    keyboard = [[InlineKeyboardButton("Я подписался! Получить промокод", callback_data='check_sub')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📢 Подпишись на наш канал: {os.getenv('CHANNEL_LINK')}\n"
        "🎁 И получи промокод на бесплатное посещение!",
        reply_markup=reply_markup
    )

# Обработка кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Проверка подписки
                member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                subscribed = member.status in ['member', 'administrator', 'creator']

                # Проверка наличия промокода
                cursor.execute('SELECT promo_code FROM users WHERE user_id = %s', (user_id,))
                promo_data = cursor.fetchone()

                if promo_data and promo_data[0]:
                    await query.edit_message_text("⚠ Вы уже получали промокод. Проверьте предыдущие сообщения.")
                    return

                if subscribed:
                    # Генерация промокода
                    promo_code = generate_unique_promo_code(cursor)
                    cursor.execute('''
                        UPDATE users 
                        SET subscribed = TRUE, promo_code = %s, promo_issued = %s 
                        WHERE user_id = %s
                    ''', (promo_code, datetime.now(), user_id))
                    conn.commit()
                    await query.edit_message_text(f"🎉 Ваш промокод: {promo_code}\n\nСохраните его!")
                     # Отправляем информацию в группу
                    group_message = f"-New Promo Code Issued-\n\n" \
                                    f"👤 Пользователь: `{user_id}`\n" \
                                    f"🎁 Промокод: `{promo_code}`"
                    try:
                        await context.bot.send_message(
                            chat_id=GROUP_ID,
                            text=group_message,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send promo code to group: {e}")
                else:
                    await query.edit_message_text("❌ Вы не подписаны на канал. Подпишитесь и попробуйте снова.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text("⚠ Произошла ошибка. Попробуйте позже.")

# Рассылка сообщений
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Использование: /broadcast Ваше сообщение")
        return

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()

    success_count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send to {user[0]}: {e}")

    await update.message.reply_text(f"✅ Рассылка отправлена {success_count} пользователям")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.run_polling()
