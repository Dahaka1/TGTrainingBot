from non_public.bot import *
from store import *
from time import sleep
from classes.general import User
from datetime import datetime

def mailing_send(txt: str):
	with database() as c:
		with c.cursor() as db:
			db.execute('SELECT users.chat_id FROM users LEFT JOIN blacklist ON '
					   'users.chat_id = blacklist.users_chat_id WHERE blacklist.users_chat_id IS NULL')
			users = db.fetchall()
			if users:
				users = [user['chat_id'] for user in users]
				for user in users:
					bot.send_message(user, txt)
					sleep(1)
				return users

def log(users_list: list, txt: str):
	text = f'Successfully sended mailing messages!\n' \
		   f'Mailing date: {datetime.now().isoformat()}\n' \
		   f'Content: "{txt}"'
	bot.send_message(developer_id, text + '\nMailing will be logged.')
	try:
		log_file = open('scripts/mailings_log.txt', 'a', encoding='utf-8')
	except FileNotFoundError:
		log_file = open('scripts/mailings_log.txt', 'w', encoding='utf-8')
	users_list = ', '.join(': '.join(user) for user in sorted(users_list, key=lambda u: u[0]))
	log_file.write(f'{text}\nSended for users: {users_list}\n\n\n')
	log_file.close()

def get_mailing_text(msg):
	text = msg.text
	if text != 'Q':
		users_list = mailing_send(text)
		if users_list:
			users_list = map(User, users_list)
			list_for_logging = [(user.fullname, user.chat_id) for user in users_list]
			log(list_for_logging, text)
	else:
		bot.send_message(developer_id, 'Mailing sending was canceled.')