from aiogram import types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from handlers import registration_router
from database import get_user, add_user, update_labs, accept_user_agreement
from handlers.user import get_main_menu_keyboard

class RegState(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_oaip = State()
    waiting_for_siap = State()
    waiting_for_structures = State()

def get_agreement_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Соглашаюсь", callback_data="agreement_accept")
    builder.button(text="❌ Отклоняю", callback_data="agreement_decline")
    builder.adjust(2)
    return builder.as_markup()

@registration_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(
            f"Привет, {user['first_name']}! Ты уже зарегистрирован.\n\n📚 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(message.from_user.id)
        )
        return

    await message.answer("Привет! Добро пожаловать в бота-очередь для сдачи лаб. Давай зарегистрируемся.\n\nВведи свое <b>имя</b>:")
    await state.set_state(RegState.waiting_for_first_name)

@registration_router.message(RegState.waiting_for_first_name)
async def process_first_name(message: types.Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Отлично. А теперь введи свою <b>фамилию</b>:")
    await state.set_state(RegState.waiting_for_last_name)

@registration_router.message(RegState.waiting_for_last_name)
async def process_last_name(message: types.Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("Сколько лабораторных по предмету <b>ОАиП</b> у тебя уже сдано? (введи число)")
    await state.set_state(RegState.waiting_for_oaip)

@registration_router.message(RegState.waiting_for_oaip)
async def process_oaip(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введи число.")
        return
    await state.update_data(oaip=int(message.text))
    await message.answer("Хорошо. Сколько лабораторных по предмету <b>СЯП</b> у тебя уже сдано? (введи число)")
    await state.set_state(RegState.waiting_for_siap)

@registration_router.message(RegState.waiting_for_siap)
async def process_siap(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введи число.")
        return
    await state.update_data(siap=int(message.text))
    await message.answer("Сколько лабораторных по предмету <b>Структуры</b> у тебя уже сдано? (введи число)")
    await state.set_state(RegState.waiting_for_structures)

@registration_router.message(RegState.waiting_for_structures)
async def process_structures(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введи число.")
        return

    data = await state.get_data()
    first_name = data['first_name']
    last_name = data['last_name']
    oaip = data['oaip']
    siap = data['siap']
    structures = int(message.text)
    username = message.from_user.username or "unknown"

    await add_user(message.from_user.id, username, first_name, last_name)
    await update_labs(message.from_user.id, 'oaip', oaip)
    await update_labs(message.from_user.id, 'siap', siap)
    await update_labs(message.from_user.id, 'structures', structures)

    await state.clear()

    agreement_text = (
        "📜 <b>Пользовательское Соглашение</b>\n\n"
        "Регистрируясь в данном боте, вы соглашаетесь с тем, что:\n"
        "1. Бот обрабатывает ваши данные (Имя, Фамилия, Телеграм ID) для составления очереди.\n"
        "2. Вы обязуетесь честно указывать количество сданных лабораторных работ.\n"
        "3. Администратор имеет право изменять вашу позицию в случае выявления неточностей.\n"
        "4. Вы не будете злоупотреблять функциями бота.\n\n"
        "Пожалуйста, подтвердите своё согласие для завершения регистрации."
    )

    await message.answer(agreement_text, reply_markup=get_agreement_keyboard())
