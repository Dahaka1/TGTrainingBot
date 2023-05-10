from non_public.bot import *
from telebot.types import InlineKeyboardMarkup
from handlers.other.additional_funcs import telebutton
from typing import NoReturn
from collections import namedtuple




menu = InlineKeyboardMarkup(row_width=2)

def start_polling(message, user, polling_type:str) -> NoReturn:
	usr = user.chat_id

