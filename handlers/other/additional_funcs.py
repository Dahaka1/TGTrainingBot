# доп функции для импорта
import time
from classes.general import *
from store import *
from telebot.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
from handlers.other.config import statuses
from non_public.bot import *
from typing import NoReturn, Any, Union
from telebot import util

# функция для проверки бан-листа: возвращает True, если пользователь прошел проверку (не в бане)
# user = callback/message
def blacklist_checking(user, callback=False):
	with database() as connection:
		with connection.cursor() as db:
			if not callback:
				db.execute(f"SELECT users_chat_id FROM blacklist WHERE users_chat_id = '{user.chat.id}'")
				check_lst = db.fetchall()
			else:
				db.execute(f"SELECT users_chat_id FROM blacklist WHERE users_chat_id = '{user.message.chat.id}'")
				check_lst = db.fetchall()
			return True if not check_lst else False

def telebutton(text: str, callback_data: str) -> InlineKeyboardButton:
	return InlineKeyboardButton(text=text, callback_data=callback_data)

def telebot_splitted_text_send_message(text:str, user: Union[User, Coach], messages_thread:str,  menu: InlineKeyboardMarkup=None) -> NoReturn:
	if len(text) > 3500:
		text = util.smart_split(text, 3500)
		for message in text:
			msg = bot.send_message(user.chat_id, message, reply_markup=menu) if text[-1] == message and menu else bot.send_message(user.chat_id, message)
			temp_msgs(messages_thread, user, msg)
	else:
		msg = bot.send_message(user.chat_id, text, reply_markup=menu) if menu else bot.send_message(
			user.chat_id, text)
		temp_msgs(messages_thread, user, msg)
	return msg

def test(item: Any) -> NoReturn:
	bot.send_message(developer_id, f'{item}', parse_mode='HTML')

def coach_check(user):
	try:
		user = User(user.chat.id)
		if user.is_coach:
			Coach(user.chat_id)
			return True
	except TypeError:
		return False


# функция для проверки, отправляет ли пользователь видео-отчет в данный момент,
# чтобы не прерывать процесс при нажатии кнопок меню
def check_status(message):
	user = User(message.chat.id)
	try:
		return all([not user.status.startswith(i) for i in statuses])
	except:
		return True

def del_msgs(process_name, user):
	with database() as connection:
		with connection.cursor() as db:
			db.execute(
				f"SELECT * FROM temp_messages WHERE chat_id = '{user.chat_id}' and message_thread = '{process_name}'")
			messages = db.fetchall()
			if messages:
				for msg in messages:
					try:
						bot.delete_message(user.chat_id, msg['message_id'])
					except:
						continue
				db.execute(
					f"DELETE FROM temp_messages WHERE chat_id = '{user.chat_id}' AND message_thread = '{process_name}'")
				connection.commit()

def temp_msgs(process_name, usr, msg):
	if msg:
		with database() as connection:
			with connection.cursor() as db:
				try:
					db.execute(f"INSERT INTO temp_messages (chat_id, message_thread, message_id) VALUES ('{usr.chat_id}', '{process_name}', '{msg.message_id}')")
				except pymysql.err.IntegrityError:
					db.execute(f"SET FOREIGN_KEY_CHECKS = 0")
					db.execute(f"INSERT INTO temp_messages (chat_id, message_thread, message_id) VALUES ('{usr.chat_id}', '{process_name}', '{msg.message_id}')")
					db.execute(f"SET FOREIGN_KEY_CHECKS = 1")
				connection.commit()


spams = {}

def anti_spam(message, callback=False):
	if not callback:
		try:
			spams[message.chat.id]
		except KeyError:
			spams[message.chat.id] = []
		user = spams[message.chat.id]
		user.append(int(time.time()))
	else:
		try:
			spams[message.message.chat.id]
		except KeyError:
			spams[message.message.chat.id] = []
		user = spams[message.message.chat.id]
		user.append(int(time.time()))
	if len(user) == 10:
		if not callback:
			spams[message.chat.id] = user[1:]
		else:
			spams[message.message.chat.id] = user[1:]
		if user[-1] - user[0] < 10:
			if not callback:
				usr = User(message.chat.id)
			else:
				usr = User(message.message.chat.id)
			if not usr.is_coach:
				usr.block()
				bot.send_message(usr.chat_id, f'Вы забанены за спам.\nВы будете разблокированы *{(datetime.today() + timedelta(days=1)).strftime("%d.%m.%Y в %H:%M")}*.', reply_markup=ReplyKeyboardRemove())