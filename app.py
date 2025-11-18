import telebot
from telebot import types
from flask import Flask, request
import json
import os

# Отримай змінні оточення
BOT_TOKEN = os.getenv("BOT_TOKEN")
MODERATOR_CHAT_ID = int(os.getenv("MODERATOR_CHAT_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Не обов'язково

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

pending_posts = {}

@app.route('/tilda-webhook', methods=['POST'])
def tilda_webhook():
    data = request.json
    if not data:
        return "No data", 400

    post_id = len(pending_posts) + 1
    pending_posts[post_id] = data

    formatted_text = format_post(data)

    bot.send_message(MODERATOR_CHAT_ID, f"Нове оголошення:\n\n{formatted_text}")

    return "OK", 200

def format_post(data):
    text = f"""
{name}: {data.get('name', 'Не вказано')}
Стать: {data.get('gender', 'Не вказано')}
Вік: {data.get('old', 'Не вказано')}
Хто цікавить: {data.get('interesting', 'Не вказано')}
Оголошення: {data.get('message', 'Немає тексту')}
"""
    if data.get('telegram'):
        text += f"\nКонтакт: {data['telegram']}"
    else:
        text += f"\nКонтакт: анонімно"
    return text

@bot.message_handler(commands=['approve'])
def approve_post(message):
    # Тут ми будемо шукати останнє оголошення і публікувати його
    if pending_posts:
        post_id = max(pending_posts.keys())
        data = pending_posts[post_id]
        formatted_text = format_post(data)

        if CHANNEL_ID:
            bot.send_message(CHANNEL_ID, formatted_text)
        else:
            bot.send_message(MODERATOR_CHAT_ID, f"Опубліковано:\n\n{formatted_text}")

        del pending_posts[post_id]
        bot.reply_to(message, "✅ Оголошення опубліковано!")
    else:
        bot.reply_to(message, "❌ Немає оголошень для підтвердження.")

@bot.message_handler(commands=['reject'])
def reject_post(message):
    if pending_posts:
        post_id = max(pending_posts.keys())
        del pending_posts[post_id]
        bot.reply_to(message, "❌ Оголошення видалено.")
    else:
        bot.reply_to(message, "❌ Немає оголошень для відхилення.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
