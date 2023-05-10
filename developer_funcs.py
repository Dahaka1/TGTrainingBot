import sys
sys.path.extend(['C:\\Users\\Yaroslav\\PycharmProjects\\my_learning\\TGTrainingBot'])
from classes.general import User
from store import database
from typing import NoReturn

def change_sessions_amount(user_fullname: str, training_type: str, sessions_amount: int) -> NoReturn:
	"""
	:param user_fullname: fullname of user from DB
	:param training_type: split/personal/personal_online/group/free
	:param sessions_amount: needed amount of sessions to set
	:return: nothing
	"""
	with database() as connection:
		with connection.cursor() as d:
			d.execute(f"SELECT chat_id FROM users WHERE fullname = '{user_fullname}'")
			r = d.fetchone()
			if r:
				user = User(r['chat_id'])
				user.subscription_plan['sessions_count'][training_type] = sessions_amount
				user.set_user(subscription_plan=True)
				connection.commit()
				print(f'Sessions amount for user {user.fullname} was changed: {training_type} -> {sessions_amount}')
			else:
				raise Exception("User was not found in DB.")

if __name__ == '__main__':
	func_num = int(input())
	def start():
		if func_num == 1:
			name = input('Write an user fullname: ')
			tr_type = 'split'
			sessions_amount = int(input('Write a sessions amount: '))
			change_sessions_amount(name, tr_type, sessions_amount)
	while True:
		start()