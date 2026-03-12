from aiogram import F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import update_labs, get_user_labs, resolve_pending_confirmation, accept_user_agreement, delete_user, buyout_queue, get_user
from handlers import callback_router
from handlers.admin import generate_queue_text
from handlers.user import get_main_menu_keyboard
import logging

def get_lab_poll_keyboard(subject: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, сдал", callback_data=f"poll_yes_{subject}")
    builder.button(text="❌ Нет, не сдал", callback_data=f"poll_no_{subject}")
    return builder.as_markup()

@callback_router.callback_query(F.data == "agreement_accept")
async def process_agreement_accept(callback: types.CallbackQuery):
    await accept_user_agreement(callback.from_user.id)
    await callback.message.edit_text(
        "✅ Вы успешно приняли пользовательское соглашение!\n\n📚 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard(callback.from_user.id)
    )
    await callback.answer()

@callback_router.callback_query(F.data == "agreement_decline")
async def process_agreement_decline(callback: types.CallbackQuery):
    await delete_user(callback.from_user.id)
    await callback.message.edit_text("❌ Вы отклонили соглашение. Ваши данные были удалены.\nЕсли передумаете — нажмите /start снова.")
    await callback.answer()

@callback_router.callback_query(F.data.startswith("poll_yes_"))
async def process_poll_yes(callback: types.CallbackQuery):
    subject = callback.data.split("_")[2]
    user_id = callback.from_user.id

    await resolve_pending_confirmation(user_id, subject)

    labs = await get_user_labs(user_id)
    if labs:
        current_count = labs[subject]
        await update_labs(user_id, subject, current_count + 1)
        await callback.message.edit_text(f"✅ Отлично! Количество сданных лаб обновлено. (Теперь: {current_count + 1})")
    else:
        await callback.message.edit_text("Ошибка: профиль не найден.")

    await callback.answer()

@callback_router.callback_query(F.data.startswith("poll_no_"))
async def process_poll_no(callback: types.CallbackQuery):
    subject = callback.data.split("_")[2]
    user_id = callback.from_user.id

    await resolve_pending_confirmation(user_id, subject)

    await callback.message.edit_text("Понял. Количество лаб не изменилось. Не забывай сдавать!")
    await callback.answer()

@callback_router.callback_query(F.data.startswith("buyout_"))
async def process_buyout(callback: types.CallbackQuery):
    subject = callback.data.split("_")[1]
    user_id = callback.from_user.id

    await buyout_queue(user_id, subject)

    result = await generate_queue_text(subject)
    if isinstance(result, tuple):
        text, _ = result
    else:
        text = result
    
    builder = InlineKeyboardBuilder()
    # builder.button(text="⭐ Выкупить очередь (Сдвиг вверх)", callback_data=f"buyout_{subject}")
    builder.button(text="⬅️ Назад в меню", callback_data="menu_back")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer("⭐ Позиция повышена!")
