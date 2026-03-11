import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import init_db
from handlers import registration_router, admin_router, user_router, callback_router
from scheduler import setup_scheduler
from aiogram.client.default import DefaultBotProperties

# Setup logging
logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(registration_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(callback_router)
    
    setup_scheduler(bot)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Set BOT_TOKEN in .env")
    else:
        asyncio.run(main())
