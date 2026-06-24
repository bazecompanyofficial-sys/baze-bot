# -*- coding: utf-8 -*-
import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from groq import Groq
from system_prompt import SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

# Store conversation history per user
conversations = {}

def get_ai_response(user_id: int, user_message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []
    
    conversations[user_id].append({
        "role": "user",
        "content": user_message
    })
    
    # Keep last 20 messages to avoid token limits
    history = conversations[user_id][-20:]
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        assistant_message = response.choices[0].message.content
        conversations[user_id].append({
            "role": "assistant",
            "content": assistant_message
        })
        return assistant_message
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "Извините, произошла техническая ошибка. Пожалуйста, попробуйте снова или напишите нам напрямую."

@dp.message(CommandStart())
async def start_handler(message: Message):
    conversations.pop(message.from_user.id, None)
    await message.answer(
        "Здравствуйте! Добро пожаловать в BAZE. — магазин оригинальных кроссовок.\n\n"
        "Чем могу помочь? Расскажите, какая пара Вас интересует, или задайте любой вопрос."
    )

@dp.message(Command("reset"))
async def reset_handler(message: Message):
    conversations.pop(message.from_user.id, None)
    await message.answer("Диалог сброшен. Начинаем заново! Чем могу помочь?")

@dp.message()
async def message_handler(message: Message):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return
    
    user_id = message.from_user.id
    user_text = message.text
    
    # Show typing indicator
    await bot.send_chat_action(message.chat.id, "typing")
    
    response = get_ai_response(user_id, user_text)
    await message.answer(response)

async def main():
    logger.info("BAZE bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
