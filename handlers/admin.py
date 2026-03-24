from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SUBJECTS, ADMIN_ID
from database import get_queue, get_all_users_labs, is_admin, admin_update_labs, set_modifier, get_user_labs
from handlers import admin_router


class AdminEditState(StatesGroup):
    waiting_for_lab_count = State()


def get_is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def get_buyout_keyboard(subject: str):
    builder = InlineKeyboardBuilder()
    return builder.as_markup()

def get_admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Все студенты", callback_data="admin_all_users")
    builder.button(text="📋 Очередь ОАиП", callback_data="admin_queue_oaip")
    builder.button(text="📋 Очередь СЯП", callback_data="admin_queue_siap")
    builder.button(text="📋 Очередь Структуры", callback_data="admin_queue_structures")
    builder.button(text="✏️ Изменить очередь", callback_data="admin_edit_queue")
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
        lines.append(f"{idx}. {u['last_name']} {u['first_name']} | ОАиП: {u['oaip']}, СЯП: {u['siap']}, Стр: {u['structures']}")

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_back")
    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👑 <b>Админ Панель</b>\n\nВыберите действие:", reply_markup=get_admin_menu_keyboard())
    await callback.answer()

@admin_router.callback_query(F.data.startswith("admin_queue_"))
async def cb_admin_queue(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    subject = callback.data.replace("admin_queue_", "")
    text, kb = await generate_queue_text(subject)
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_back")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ====== Queue Editing Flow ======

@admin_router.callback_query(F.data == "admin_edit_queue")
async def cb_edit_queue_choose_subject(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="ОАиП", callback_data="aedit_subj_oaip")
    builder.button(text="СЯП", callback_data="aedit_subj_siap")
    builder.button(text="Структуры", callback_data="aedit_subj_structures")
    builder.button(text="⬅️ Назад", callback_data="admin_back")
    builder.adjust(3, 1)
    await callback.message.edit_text("✏️ <b>Изменение очереди</b>\n\nВыберите предмет:", reply_markup=builder.as_markup())
    await callback.answer()


@admin_router.callback_query(F.data.startswith("aedit_subj_"))
async def cb_edit_queue_choose_student(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    subject = callback.data.replace("aedit_subj_", "")
    subject_name = SUBJECTS.get(subject, subject)
    queue = await get_queue(subject)

    if not queue:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="admin_edit_queue")
        await callback.message.edit_text(f"Нет данных для {subject_name}.", reply_markup=builder.as_markup())
        await callback.answer()
        return

    lines = [f"✏️ <b>Очередь {subject_name}</b>\n\nВыберите студента для изменения:"]
    builder = InlineKeyboardBuilder()
    for idx, u in enumerate(queue, 1):
        modifier = u[f'{subject}_modifier']
        mod_str = f" (мод: {modifier:+.1f})" if modifier != 0 else ""
        lines.append(f"{idx}. {u['last_name']} {u['first_name']} — Лаб: {u[subject]}{mod_str}")
        btn_text = f"{idx}. {u['last_name']} {u['first_name']}"
        builder.button(text=btn_text, callback_data=f"aedit_user_{subject}_{u['user_id']}")

    builder.button(text="⬅️ Назад", callback_data="admin_edit_queue")
    builder.adjust(1)
    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()


@admin_router.callback_query(F.data.startswith("aedit_user_"))
async def cb_edit_queue_user_actions(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    parts = callback.data.replace("aedit_user_", "").split("_", 1)
    subject = parts[0]
    target_user_id = int(parts[1])
    subject_name = SUBJECTS.get(subject, subject)

    labs = await get_user_labs(target_user_id)
    if not labs:
        await callback.answer("Пользователь не найден.")
        return

    lab_count = labs[subject]
    modifier = labs[f'{subject}_modifier']

    text = (
        f"✏️ <b>Редактирование | {subject_name}</b>\n\n"
        f"Текущее количество лаб: <b>{lab_count}</b>\n"
        f"Модификатор позиции: <b>{modifier:+.1f}</b>\n\n"
        f"Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Изменить кол-во лаб", callback_data=f"aedit_labs_{subject}_{target_user_id}")
    builder.button(text="⬆️ Поднять в очереди", callback_data=f"aedit_up_{subject}_{target_user_id}")
    builder.button(text="⬇️ Опустить в очереди", callback_data=f"aedit_down_{subject}_{target_user_id}")
    builder.button(text="🔄 Сбросить модификатор", callback_data=f"aedit_reset_{subject}_{target_user_id}")
    builder.button(text="⬅️ Назад", callback_data=f"aedit_subj_{subject}")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@admin_router.callback_query(F.data.startswith("aedit_up_"))
async def cb_edit_move_up(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    parts = callback.data.replace("aedit_up_", "").split("_", 1)
    subject = parts[0]
    target_user_id = int(parts[1])

    labs = await get_user_labs(target_user_id)
    new_mod = labs[f'{subject}_modifier'] - 0.1
    await set_modifier(target_user_id, subject, new_mod)
    await callback.answer("⬆️ Студент поднят на 1 позицию!")

    # Refresh: go back to user actions screen
    callback.data = f"aedit_user_{subject}_{target_user_id}"
    await cb_edit_queue_user_actions(callback)


@admin_router.callback_query(F.data.startswith("aedit_down_"))
async def cb_edit_move_down(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    parts = callback.data.replace("aedit_down_", "").split("_", 1)
    subject = parts[0]
    target_user_id = int(parts[1])

    labs = await get_user_labs(target_user_id)
    new_mod = labs[f'{subject}_modifier'] + 0.1
    await set_modifier(target_user_id, subject, new_mod)
    await callback.answer("⬇️ Студент опущен на 1 позицию!")

    callback.data = f"aedit_user_{subject}_{target_user_id}"
    await cb_edit_queue_user_actions(callback)


@admin_router.callback_query(F.data.startswith("aedit_reset_"))
async def cb_edit_reset_modifier(callback: types.CallbackQuery):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    parts = callback.data.replace("aedit_reset_", "").split("_", 1)
    subject = parts[0]
    target_user_id = int(parts[1])

    await set_modifier(target_user_id, subject, 0.0)
    await callback.answer("🔄 Модификатор сброшен!")

    callback.data = f"aedit_user_{subject}_{target_user_id}"
    await cb_edit_queue_user_actions(callback)


@admin_router.callback_query(F.data.startswith("aedit_labs_"))
async def cb_edit_labs_prompt(callback: types.CallbackQuery, state: FSMContext):
    if not get_is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    parts = callback.data.replace("aedit_labs_", "").split("_", 1)
    subject = parts[0]
    target_user_id = int(parts[1])
    subject_name = SUBJECTS.get(subject, subject)

    await state.update_data(admin_edit_subject=subject, admin_edit_user_id=target_user_id)
    await state.set_state(AdminEditState.waiting_for_lab_count)

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Отмена", callback_data=f"aedit_user_{subject}_{target_user_id}")
    await callback.message.edit_text(
        f"📝 Введите новое количество сданных лаб по <b>{subject_name}</b> для этого студента:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@admin_router.message(AdminEditState.waiting_for_lab_count)
async def process_admin_lab_count(message: types.Message, state: FSMContext):
    if not get_is_admin(message.from_user.id):
        return

    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return

    count = int(message.text)
    data = await state.get_data()
    subject = data['admin_edit_subject']
    target_user_id = data['admin_edit_user_id']
    subject_name = SUBJECTS.get(subject, subject)

    await admin_update_labs(target_user_id, subject, count)
    await state.clear()
    await message.answer(
        f"✅ Обновлено! У студента теперь <b>{count}</b> лаб по {subject_name}.",
        reply_markup=get_admin_menu_keyboard()
    )


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
