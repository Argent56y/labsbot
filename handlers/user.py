from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SUBJECTS, ADMIN_ID
from database import get_user, get_user_labs, update_labs
from handlers import user_router
from handlers.admin import generate_queue_text

# ====== Main Menu Keyboard ======
def get_main_menu_keyboard(user_id: int = 0):
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Мой профиль", callback_data="menu_profile")
    builder.button(text="📋 Очередь ОАиП", callback_data="menu_queue_oaip")
    builder.button(text="📋 Очередь СЯП", callback_data="menu_queue_siap")
    builder.button(text="📋 Очередь Структуры", callback_data="menu_queue_structures")
    builder.button(text="✏️ Обновить лабы", callback_data="menu_update")
    if user_id == ADMIN_ID:
        builder.button(text="👑 Админ панель", callback_data="menu_admin")
    builder.adjust(1)
    return builder.as_markup()

def get_update_subject_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="ОАиП", callback_data="update_subject_oaip")
    builder.button(text="СЯП", callback_data="update_subject_siap")
    builder.button(text="Структуры", callback_data="update_subject_structures")
    builder.button(text="⬅️ Назад", callback_data="menu_back")
    builder.adjust(3, 1)
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="menu_back")
    return builder.as_markup()

def get_role_text(user_id: int) -> str:
    return "👑 Админ" if user_id == ADMIN_ID else "👤 Пользователь"

# ====== /help → Main menu ======
@user_router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )

@user_router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Ты не зарегистрирован. Напиши /start")
        return
    labs = await get_user_labs(message.from_user.id)
    role = get_role_text(message.from_user.id)
    text = (
        f"👤 <b>Твой профиль:</b>\n"
        f"Имя: {user['first_name']} {user['last_name']}\n"
        f"Статус: {role}\n\n"
        f"<b>Сданные лабораторные:</b>\n"
        f"ОАиП: {labs['oaip']}\n"
        f"СЯП: {labs['siap']}\n"
        f"Структуры: {labs['structures']}"
    )
    await message.answer(text, reply_markup=get_back_keyboard())

# ====== Callbacks ======
@user_router.callback_query(F.data == "menu_back")
async def cb_menu_back(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📚 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard(callback.from_user.id)
    )
    await callback.answer()

@user_router.callback_query(F.data == "menu_profile")
async def cb_profile(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Ты не зарегистрирован. Напиши /start")
        await callback.answer()
        return
    labs = await get_user_labs(callback.from_user.id)
    role = get_role_text(callback.from_user.id)
    text = (
        f"👤 <b>Твой профиль:</b>\n"
        f"Имя: {user['first_name']} {user['last_name']}\n"
        f"Статус: {role}\n\n"
        f"<b>Сданные лабораторные:</b>\n"
        f"ОАиП: {labs['oaip']}\n"
        f"СЯП: {labs['siap']}\n"
        f"Структуры: {labs['structures']}"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@user_router.callback_query(F.data.startswith("menu_queue_"))
async def cb_queue(callback: types.CallbackQuery):
    subject = callback.data.replace("menu_queue_", "")
    result = await generate_queue_text(subject)
    if isinstance(result, tuple):
        text, _ = result
    else:
        text = result
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Выкупить очередь (Сдвиг вверх)", callback_data=f"buyout_{subject}")
    builder.button(text="⬅️ Назад в меню", callback_data="menu_back")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@user_router.callback_query(F.data == "menu_update")
async def cb_update_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери предмет для обновления:", reply_markup=get_update_subject_keyboard())
    await callback.answer()

# ====== Admin panel entry from main menu ======
@user_router.callback_query(F.data == "menu_admin")
async def cb_menu_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.")
        return
    from handlers.admin import get_admin_menu_keyboard
    await callback.message.edit_text("👑 <b>Админ Панель</b>\n\nВыберите действие:", reply_markup=get_admin_menu_keyboard())
    await callback.answer()

# ====== Update Flow (FSM) ======
class UpdateLabState(StatesGroup):
    waiting_for_count = State()

@user_router.callback_query(F.data.startswith("update_subject_"))
async def cb_update_subject(callback: types.CallbackQuery, state: FSMContext):
    subject = callback.data.replace("update_subject_", "")
    subject_name = SUBJECTS.get(subject, subject)
    await state.update_data(update_subject=subject)
    await state.set_state(UpdateLabState.waiting_for_count)
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Отмена", callback_data="menu_back")
    await callback.message.edit_text(f"Введи новое количество сданных лаб по <b>{subject_name}</b>:", reply_markup=builder.as_markup())
    await callback.answer()

@user_router.message(UpdateLabState.waiting_for_count)
async def process_update_count(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введи число.")
        return
    count = int(message.text)
    data = await state.get_data()
    subject = data['update_subject']
    subject_name = SUBJECTS.get(subject, subject)
    await update_labs(message.from_user.id, subject, count)
    await state.clear()
    await message.answer(
        f"✅ Обновлено! Теперь у тебя сдано {count} лаб по {subject_name}.",
        reply_markup=get_main_menu_keyboard(message.from_user.id)
    )
