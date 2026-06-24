# -*- coding: utf-8 -*-
import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from groq import Groq
from system_prompt import SYSTEM_PROMPT
from dewu import find_dewu_url, get_dewu_image

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

conversations = {}


def get_ai_response(user_id: int, user_message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": user_message})
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
        conversations[user_id].append({"role": "assistant", "content": assistant_message})
        return assistant_message
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "Извините, произошла техническая ошибка. Пожалуйста, попробуйте снова или напишите нам напрямую."


@dp.message(CommandStart())
async def start_handler(message: Message):
    conversations.pop(message.from_user.id, None)
    await message.answer("Здравствуйте! Добро пожаловать в BAZE. — магазин оригинальных кроссовок.\n\nЧем могу помочь?")


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

    # Если в сообщении есть ссылка Dewu — пробуем достать и отправить фото товара.
    dewu_url = find_dewu_url(user_text)
    if dewu_url:
        await bot.send_chat_action(message.chat.id, "upload_photo")
        image_url = await get_dewu_image(dewu_url)
        if image_url:
            try:
                await message.answer_photo(
                    photo=image_url,
                    caption="Вот фото товара с Dewu. Хотите узнать цену, размеры или оформить заказ?",
                )
                return
            except Exception as e:
                logger.error(f"Не удалось отправить фото в Telegram: {e}")
                await message.answer(
                    "Я нашёл товар, но не смог загрузить фото. "
                    "Опишите модель словами — подберу и проконсультирую."
                )
                return
        else:
            await message.answer(
                "Не получилось открыть эту ссылку Dewu автоматически. "
                "Напишите название модели — и я всё подскажу по наличию, размерам и цене."
            )
            return

    # Обычный ответ ИИ-консультанта.
    await bot.send_chat_action(message.chat.id, "typing")
    response = get_ai_response(user_id, user_text)
    await message.answer(response)


async def main():
    logger.info("BAZE bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
