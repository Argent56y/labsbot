from aiogram import types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SUBJECTS, ADMIN_ID
from database import get_queue, get_all_users_labs, is_admin
from handlers import admin_router

def get_is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def get_buyout_keyboard(subject: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Выкупить очередь (Сдвиг вверх)", callback_data=f"buyout_{subject}")
    return builder.as_markup()

def get_admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Все студенты", callback_data="admin_all_users")
    builder.button(text="📋 Очередь ОАиП", callback_data="admin_queue_oaip")
    builder.button(text="📋 Очередь СИАП", callback_data="admin_queue_siap")
    builder.button(text="📋 Очередь Структуры", callback_data="admin_queue_structures")
    builder.button(text="⬅️ Назад в главное меню", callback_data="menu_back")
    builder.adjust(1)
    return builder.as_markup()

@admin_router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not get_is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await message.answer("👑 <b>Админ Панель</b>\n\nВыберите действие:", reply_markup=get_admin_menu_keyboard())

@admin_router.callback_query(F.data == "admin_all_users")
async def cb_all_users(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    users = await get_all_users_labs()
    if not users:
        await callback.message.edit_text("В базе нет пользователей.", reply_markup=get_admin_menu_keyboard())
        return

    lines = ["<b>Список студентов:</b>"]
    for idx, u in enumerate(users, 1):
        lines.append(f"{idx}. {u['last_name']} {u['first_name']} | ОАиП: {u['oaip']}, СИАП: {u['siap']}, Стр: {u['structures']}")

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_back")
    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: types.CallbackQuery):
    await callback.message.edit_text("👑 <b>Админ Панель</b>\n\nВыберите действие:", reply_markup=get_admin_menu_keyboard())
    await callback.answer()

@admin_router.callback_query(F.data.startswith("admin_queue_"))
async def cb_admin_queue(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    subject = callback.data.replace("admin_queue_", "")
    text, kb = await generate_queue_text(subject)
    # Add back button
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Выкупить очередь (Сдвиг вверх)", callback_data=f"buyout_{subject}")
    builder.button(text="⬅️ Назад", callback_data="admin_back")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

async def generate_queue_text(subject_key: str):
    subject_name = SUBJECTS.get(subject_key, subject_key)
    queue = await get_queue(subject_key)
    if not queue:
        return f"Нет данных для очереди по предмету {subject_name}.", None

    lines = [f"📋 <b>Очередь на сдачу лабораторных | {subject_name}</b>\n<i>(Приоритет: чем меньше сдано, тем выше в списке)</i>\n"]
    for idx, u in enumerate(queue, 1):
        lines.append(f"{idx}. {u['last_name']} {u['first_name']} — Сдано лаб: {u[subject_key]}")

    kb = await get_buyout_keyboard(subject_key)
    return "\n".join(lines), kb
