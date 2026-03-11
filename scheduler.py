from config import SUBJECTS
from database import get_all_users_labs, add_pending_confirmation, get_unresolved_confirmations_older_than, resolve_pending_confirmation
from handlers.callbacks import get_lab_poll_keyboard
from handlers.admin import generate_queue_text
from aiogram import Bot
import datetime
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def is_week_1():
    return datetime.date.today().isocalendar()[1] % 2 == 0

def is_week_2():
    return datetime.date.today().isocalendar()[1] % 2 != 0

async def broadcast_queue(bot: Bot, subject: str):
    logging.info(f"Broadcasting queue for {subject}")
    text = await generate_queue_text(subject)
    users = await get_all_users_labs()
    # Also we could broadcast to a specific group, but since it's a bot, we send to all registered users
    for u in users:
        try:
            await bot.send_message(u['user_id'], text)
        except Exception as e:
            logging.error(f"Failed to send queue to {u['user_id']}: {e}")

async def send_daily_polls(bot: Bot, subject: str):
    logging.info(f"Sending daily poll for {subject}")
    users = await get_all_users_labs()
    subject_name = SUBJECTS.get(subject, subject)
    for u in users:
        try:
            user_id = u['user_id']
            await add_pending_confirmation(user_id, subject)
            keyboard = get_lab_poll_keyboard(subject)
            text = f"Занятие по **{subject_name}** закончилось. Ты защитил(а) сегодня лабу?\n(Если да, твое количество сданных лаб увеличится на 1)"
            await bot.send_message(user_id, text, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Failed to send poll to {u['user_id']}: {e}")

async def check_24h_warnings(bot: Bot):
    logging.info("Checking for 24h unresolved warnings")
    unresolved = await get_unresolved_confirmations_older_than(24)
    for row in unresolved:
        user_id = row['user_id']
        subject = row['subject']
        subject_name = SUBJECTS.get(subject, subject)
        
        try:
            await bot.send_message(
                user_id, 
                f"⚠️ **Внимание!** Прошли сутки с момента занятия по **{subject_name}**. Ты так и не отметил, сдал(а) ли ты лабу.\n\n"
                f"Твоя позиция в очереди может пострадать. Пожалуйста, зайди в /profile и при необходимости обнови количество вручную "
                f"командой /update_{subject} [число]."
            )
            # Resolve it so we don't spam them every hour
            await resolve_pending_confirmation(user_id, subject)
        except Exception as e:
            logging.error(f"Failed to send warning to {user_id}: {e}")

# APScheduler wrapper jobs (to check the week dynamically)
async def job_fri_queue(bot: Bot):
    if is_week_1(): await broadcast_queue(bot, 'oaip')
    else: await broadcast_queue(bot, 'siap')

async def job_fri_poll(bot: Bot):
    if is_week_1(): await send_daily_polls(bot, 'oaip')
    else: await send_daily_polls(bot, 'siap')

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone='Europe/Minsk')

    # Queues: 15 mins before class
    scheduler.add_job(broadcast_queue, 'cron', day_of_week='tue', hour=11, minute=10, args=[bot, 'structures'])
    scheduler.add_job(broadcast_queue, 'cron', day_of_week='wed', hour=11, minute=10, args=[bot, 'siap'])
    scheduler.add_job(broadcast_queue, 'cron', day_of_week='thu', hour=11, minute=10, args=[bot, 'oaip'])
    scheduler.add_job(job_fri_queue, 'cron', day_of_week='fri', hour=7, minute=45, args=[bot])

    # Polls: right after class ends
    scheduler.add_job(send_daily_polls, 'cron', day_of_week='tue', hour=12, minute=50, args=[bot, 'structures'])
    scheduler.add_job(send_daily_polls, 'cron', day_of_week='wed', hour=12, minute=50, args=[bot, 'siap'])
    scheduler.add_job(send_daily_polls, 'cron', day_of_week='thu', hour=12, minute=50, args=[bot, 'oaip'])
    scheduler.add_job(job_fri_poll, 'cron', day_of_week='fri', hour=9, minute=25, args=[bot])

    # 24h warning check runs every hour
    scheduler.add_job(check_24h_warnings, 'interval', hours=1, args=[bot])

    # Reset modifiers daily at midnight so queues restore their real state
    from database import reset_modifiers
    scheduler.add_job(reset_modifiers, 'cron', hour=0, minute=0, args=['oaip'])
    scheduler.add_job(reset_modifiers, 'cron', hour=0, minute=0, args=['siap'])
    scheduler.add_job(reset_modifiers, 'cron', hour=0, minute=0, args=['structures'])

    scheduler.start()
