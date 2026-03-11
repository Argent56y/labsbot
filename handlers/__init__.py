from aiogram import Router

registration_router = Router()
admin_router = Router()
user_router = Router()
callback_router = Router()

from . import registration, admin, user, callbacks
