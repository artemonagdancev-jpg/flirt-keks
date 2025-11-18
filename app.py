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

@app.route('/')
def home():
    return "Server is running! Use /tilda-webhook for webhooks.", 200

@app.route('/tilda-webhook', methods=['GET', 'POST', 'HEAD', 'OPTIONS'])
def tilda_webhook():
    if request.method in ['GET', 'HEAD', 'OPTIONS']:
        return "", 200  # Відповідаємо порожнім тілом і статусом 200 — Tilda буде задоволена

    elif request.method == 'POST':
        data = request.json
        if not data:
            return "No data", 400

        post_id = len(pending_posts) + 1
        pending_posts[post_id] = data

        formatted_text = format_post(data)

        markup = types.InlineKeyboardMarkup()
        approve_btn = types.InlineKeyboardButton("✅ Підтвердити", callback_data=f"approve_{post_id}")
        reject_btn = types.InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{post_id}")
        markup.add(approve_btn, reject_btn)

        bot.send_message(MODERATOR_CHAT_ID, f"Нове оголошення:\n\n{formatted_text}", reply_markup=markup)

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

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve_post(call):
    post_id = int(call.data.split("_")[1])
    data = pending_posts[post_id]
    formatted_text = format_post(data)

    if CHANNEL_ID:
        bot.send_message(CHANNEL_ID, formatted_text)
    else:
        bot.send_message(MODERATOR_CHAT_ID, f"Опубліковано:\n\n{formatted_text}")

    bot.edit_message_text("✅ Підтверджено та опубліковано", call.message.chat.id, call.message.message_id)
    del pending_posts[post_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def reject_post(call):
    post_id = int(call.data.split("_")[1])
    bot.edit_message_text("❌ Відхилено", call.message.chat.id, call.message.message_id)
    del pending_posts[post_id]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
