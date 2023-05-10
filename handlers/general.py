import random
import re
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from classes.general import *
from classes.users_tasks import *
from classes.training import *
from handlers.payment_funcs import *
from handlers.dates_additional import *
from os import remove
import os.path
from telebot import util
from store import *
from handlers.admin_funcs import *
from json import loads, dump, dumps, load
from handlers.other.additional_funcs import *
from handlers.other.config import *
from classes.signing_up import *
from functools import reduce
from handlers.other.menu import *
from threading import Thread
from handlers.other.temporary_data import *
from time import sleep
from typing import NoReturn
from classes.errors import *
from non_public.bot import developer_id

temp_dct = temporary_dict() or {'users': {},
								'coaches': {}}
general_dct = general_dict() or {}

def dct_updating() -> NoReturn:
	while True:
		"""
		Needed to store temporary data in saved file, cause sometimes happens auto- or error-reboots of bot
		"""
		try:
			dct = temporary_dict()
			if dct is None or dct != temp_dct:
				temporary_dict(update=True, new_dct=temp_dct)
			dct = general_dict()
			if dct is None or dct != general_dct:
				general_dict(update=True, new_dct=general_dct)
		except:
			pass
		sleep(60)

def main(bot):
	dct_checking = Thread(target=dct_updating)
	dct_checking.start()

	# регистрация нового тренера (доступна только после регистрации в качестве обычного пользователя)
	@bot.message_handler(commands=['start_coach'], func=lambda msg: not User(msg.chat.id).id is None and blacklist_checking(msg))
	def start_coach(message):
		try:
			usr = User(message.chat.id)
		except:
			usr = None
		try:
			coach = Coach(message.chat.id)
		except TypeError:
			coach = None
		if not forbidden_status(User(message.chat.id)):
			if not coach:
				if usr and usr.is_coach:
					msg = bot.send_message(message.chat.id,
										   'Доброго времени суток! Для начала работы с ботом в качестве тренера нужно пройти полную процедуру регистрации. '
										   'Напишите свои *Имя (полное) и Фамилию*.')
					temp_msgs('coach_register', usr, msg)
					bot.register_next_step_handler(msg, register_coach)
				else:
					bot.send_message(message.chat.id, 'Вы не можете зарегистрироваться в качестве тренера.')
			else:
				bot.send_message(message.chat.id, 'Вы уже зарегистрированы в качестве тренера.')
		else:
			pass

	def register_coach(msg):
		while True:
			with database() as connection:
				with connection.cursor() as db:
					usr = User(msg.chat.id)
					try:
						coach = Coach(msg.chat.id)
					except TypeError:
						db.execute(f"INSERT INTO coachs (users_id) VALUES ({usr.id})")
						connection.commit()
						coach = Coach(msg.chat.id)

					if not coach.tags:
						coach_skills = [InlineKeyboardButton(text=f'{i.title() if i == i.lower() else i}', callback_data=f'coach_skill {i}') for
										i in coaches_disciplines()]
						coach_skills = InlineKeyboardMarkup(row_width=2).add(*coach_skills)
						msg = bot.send_message(msg.chat.id,
											   '*Выберите 5 тегов*, наиболее точно определяющих направления вашей работы с клиентами.\n\n',
											   parse_mode='Markdown', reply_markup=coach_skills)
						del_msgs('coach_register', usr)
						temp_msgs('coach_register', usr, msg)
						break

					if not coach.id in temp_dct['coaches'] or any([not temp_dct['coaches'][coach.id]['registering']['description'][i] for i in temp_dct['coaches'][coach.id]['registering']['description']]):
						try:
							form = temp_dct['coaches'][coach.id]['registering']['description']
						except KeyError:
							temp_dct['coaches'][coach.id] = {'registering': {'description': {i: None for i in coach_description()}}}
							form = temp_dct['coaches'][coach.id]['registering']['description']

						quests = {
							'*Специализация в тренерской деятельности*': 'Какая у вас специализация в вашей работе? Можно указать несколько направлений.\n'
																	   'Например: "Работаю с патологиями опорно-двигательного аппарата, а также профессионально помогаю корректировать фигуру".',
							'*Сертификаты*': 'Какие сертификаты онлайн-курсов/курсов повышения квалификации у вас есть?\n'
										   'Например: "Сертификат от 2018 г: Колледж Бена Вейдера".',
							'*Достижения*': 'Какие профессиональные достижения в спорте/науке и т.д. у вас имеются?\n'
										  'Например: "Мастер спорта по плаванию, аспирант физической культуры".',
							'*Стаж/история работы*': 'В течение какого срока уже работаете? Есть интересные подробности об опыте работы?\n'
												   'Например: "Работаю в профессии уже 5 лет. Последний год преподаю физкультуру в университете".',
							'*Преимущества*': 'Коротко, но искреннее напишите, почему клиенты должны пользоваться именно вашими услугами?\n'
											'Например: "Я помог более чем 100 людям избавиться от ожирения и проблем со здоровьем!"',
							'*Соцсети*': 'Напишите ссылки (достаточно одной) на ваши соцсети.\n'
									   'Например: "Instagram: _ссылка_, Facebook: _ссылка_ ..."'
						}
						def questions():
							lst = [i for i in form if not form[i]]
							if lst:
								q = lst[0]
								return q
						if questions():
							q = questions()
							form[q] = msg.text
							temp_dct['coaches'][coach.id]['registering']['description'] = form
							q = questions()
							if q:
								msg = bot.send_message(coach.chat_id, quests[q])
								bot.register_next_step_handler(msg, register_coach)
								del_msgs('coach_register', usr)
								temp_msgs('coach_register', usr, msg)
							else:
								result = '\n'.join([f'{i}: _{form[i]}_' for i in form])
								db.execute(f"UPDATE coachs SET description = '{result}' WHERE users_id = {usr.id}")
								if coach.id:
									temp_dct['coaches'].pop(coach.id, None)
								db.execute(f"UPDATE users SET status = 'sending_coach_photo' WHERE id = {usr.id}")
								connection.commit()
								msg = bot.send_message(msg.chat.id, 'Отправьте свое фото.\n\n'
															  '*Рекомендации* о формате и содержании фото:\n'
															  '- <b>Спортивный характер</b> фото. Подберите <i>презентабельное</i> фото из своего архива или сделайте новое, на котором изображены вы в процессе работы/тренировки/выступления на соревнованиях по вашему виду спортивной деятельности.\n'
															  '- <b>Формат 9:16</b> - такой формат изображения позволит нам красиво и уместно разместить его на нашем сайте. <i>Для вашего понимания</i>: это базовый формат, например, при пользовании <i>"stories" в Instagram</i>.\n'
															  '- <b>Если вы хотите</b> использовать фотографию другого формата или содержания, просто <i>используйте (отправьте) ее</i>, а далее мы согласуем ее использование с вами после проверки.\n'
															  '<a href="https://ibb.co/GMcNY26">Примеры формата и содержания фото</a>.\n\n'
															  'После проверки вашего фото со стороны администрации может быть запрошена повторная отправка.', parse_mode='HTML', disable_web_page_preview=True)
								del_msgs('coach_register', usr)
								temp_msgs('coach_register', usr, msg)
						break


	# обновление/открытие меню для зарегистрированного пользователя, а для нового - регистрация (по команде /start)
	@bot.message_handler(commands=['start'], func=lambda msg: blacklist_checking(msg) and check_status(msg) and not coach_check(msg))
	def start(message):
		user = User(message.chat.id)
		test(user.id)
		if not user.id:
			msg = bot.send_message(message.chat.id, 'Доброго времени суток! Для начала вам нужно зарегистрироваться. '
													'Напишите свои *Имя (полное) и Фамилию*.')
			bot.register_next_step_handler(msg, register)
			temp_msgs('register', User(message.chat.id), msg)
		else:
			if not forbidden_status(user):
				user = User(message.chat.id)
				if user.status != 'registered':
					user.status = 'registered'
					user.set_user()
				if user.current_coach_id:
					bot.send_message(user.chat_id, f'Доброго времени суток, *{user.fullname.split()[0]}*! 😃\n\n' + \
									 (f'Сейчас количество тренировок у Вас:\n*{training_types(user=user)}*.' if user.sessions_left() else ""), reply_markup=keyboard(user))
				else:
					bot.send_message(user.chat_id, f'Доброго времени суток, *{user.fullname.split()[0]}*! 😃\n\n'
												   f'Вы можете получить услуги онлайн-тренинга бесплатно или выбрать настоящего тренера и начать с ним работу (_включая одну бесплатную пробную тренировку_) в меню *"Мои тренировки"*.\n'
													   f'Если будут беспокоить вопросы - смело обращайтесь в меню *"Помощь"*.', reply_markup=keyboard(user))
			else:
				pass

	def register(msg):
		while True:
			if not User(msg.chat.id).id:
				if re.fullmatch(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?', msg.text):
					names = list(map(lambda i: str(i).rstrip() , open('data/specs/names.txt', encoding='utf-8').readlines()))
					user = User(msg.chat.id)
					if msg.text.split()[0] in names:
						user.fullname = msg.text
					else:
						if not msg.text.split()[1] in names:

							msg = bot.send_message(msg.chat.id, 'Неверные данные! Введите заново.\n'
																'Прим.: имя должно быть *полным*.')
							bot.register_next_step_handler(msg, register)
							break
						else:
							user.fullname = msg.text.split()[1] + ' ' + msg.text.split()[0]
					if msg.from_user.username:
						user.username = msg.from_user.username
					user.is_coach = False
					user.status = 'registered'
					user.new_user()
					user = User(msg.chat.id)
					user.new_user_additional_step(user)

					bot.send_message(user.chat_id, f'Добро пожаловать, *{user.fullname.split()[0]}*! 😃\n'
												  f'Теперь Вы можете получить услуги онлайн-тренинга бесплатно или выбрать настоящего тренера и начать с ним работу (_включая одну бесплатную пробную тренировку_) в меню *"Мои тренировки"*.\n'
												   f'Если будут беспокоить вопросы - смело обращайтесь в меню *"Помощь"*.\n\n'
												  f'❓ *Если меню не отображается*, кнопка для его вызова *"Меню"* доступна справа от поля для ввода сообщения.', reply_markup=keyboard(user))
					break

				else:
					anti_spam(msg)
					if blacklist_checking(msg):
						msg = bot.send_message(msg.chat.id, 'Неверные данные! Введите заново.')
						bot.register_next_step_handler(msg, register)
					break

	# меню оплаты
	@bot.message_handler(func=lambda message: message.text in ['Оплата', '💸 Оплата'] and blacklist_checking(message) and check_status(message))
	def paying(message):
		user = User(message.chat.id)
		def general_msg():
			button_1 = InlineKeyboardButton(text='📜 Тарифы', callback_data=f'available_tariffs')
			button_2 = InlineKeyboardButton(text='🎁 Акции', callback_data='available_promotions')
			pay_menu = InlineKeyboardMarkup(row_width=1).add(button_1, button_2)
			if user.current_coach_id:
				return bot.send_message(user.chat_id, '*Тарифы*: просмотреть доступные для покупки тарифы вашего тренера и их условия.\n'
												 '*Акции*: проверить доступные акции и условия участия в них и получения наград.', reply_markup=pay_menu)
			else:
				return bot.send_message(user.chat_id, 'У вас нет текущего тренера.\n'
													 'Исправьте это в меню "Мои тренировки"!')

		msg = general_msg()
		temp_msgs('paying', user, msg)

		try:
			general_dct['users'][user.id]['messages']['paying'] = general_msg
		except KeyError:
			try:
				general_dct['users'][user.id]['messages'] = {'paying': general_msg}
			except KeyError:
				try:
					general_dct['users'][user.id] = {'messages': {'paying': general_msg}}
				except KeyError:
					general_dct['users'] = {user.id: {'messages': {'paying': general_msg}}}

		question = user.current_question()
		if question:
			msg = bot.send_message(user.chat_id, question)
			temp_msgs('user_form', user, msg)
			try:
				temp_dct['users'][user.id]['question'] = {question: datetime.now()}
			except KeyError:
				temp_dct['users'][user.id] = {'question': {question: datetime.now()}}
			temp_dct['users'][user.id]['question']['menu'] = 'paying'
			bot.register_next_step_handler(msg, user_questions_form)

		anti_spam(message)

	# меню записи на тренировку
	# если у пользователя не было ни одной оплаты, но есть/была/отсутствует запись на занятия - с ним ведется работа по бесплатной тренировке
	@bot.message_handler(func=lambda message: message.text in ['🗓 Запись'] and blacklist_checking(message) and check_status(message))
	def sign_up(message):
		user = User(message.chat.id)
		del_msgs('signup', user)

		def general_msg():
			upcoming_sessions = user.upcoming_sessions()
			out = '\n'.join([f'⏳ _{fullname_of_date(i["date"])}_, _{str(i["time"])[:-3]}_, _{training_types()[i["session_type"]]}_' + (f', *ваш комментарий*: _{i["details"]}_' if i['details'] else '') for i in upcoming_sessions]) if upcoming_sessions else None
			buttons = [
				InlineKeyboardButton(text='🗓 Записаться на тренировку', callback_data='my_signup'),
				InlineKeyboardButton(text='❌ Отменить запись', callback_data='my_signup_cancel'),
				InlineKeyboardButton(text='📜 История посещений', callback_data='my_signup_history'),
				InlineKeyboardButton(text='🆓 Бесплатная тренировка', callback_data='my_signup'),
				InlineKeyboardButton(text='❔ О бесплатной тренировке', callback_data='what_is_free_session')
			]
			menu = InlineKeyboardMarkup(row_width=1)
			tariff, sessions = user.subscription_plan['tariff_id'], user.sessions_left() or []

			if not tariff or not sessions:
				if not upcoming_sessions:
					if 'free' in sessions:
						text = 'К сожалению, у вас нет оплаченного тарифа 😔\n' \
							   'Вы можете перейти в меню *Оплата*, чтобы исправить это и записаться на занятие!\n\n' \
							   f'👇 Или *запишитесь на бесплатную тренировку* к тренеру *{user.coach().fullname}*, нажав на кнопку.'
						menu.add(*buttons[3:])
					else:
						text = 'К сожалению, у вас нет оплаченного тарифа 😔\nВы можете перейти в меню *Оплата*, чтобы исправить это и записаться на занятие!'
				else:
					text = 'К сожалению, у вас нет оплаченного тарифа 😔\nВы можете перейти в меню *Оплата*, чтобы исправить это и записаться на занятие!\n\n' \
						   'Ваша текущая запись:\n' + out
			elif tariff and sessions and user.check_period():
				menu.add(buttons[0])
				if out:
					if user.canceling_sessions_check():
						menu.add(buttons[1])
				text = f'Нажмите *"Записаться на тренировку"*, чтобы записаться на занятие к тренеру *{user.coach().fullname}*.\n' + \
					   ('Или *"Отменить'
						' запись"*, чтобы отменить предстоящую запись (в рамках условий вашего тарифа).\n' if out and user.canceling_sessions_check() else '') + '\n📜*Текущая запись*:' + ('\n' + out if out else " _отсутствует_")
			if user.past_sessions():
				menu.add(buttons[2])

			if menu.keyboard:
				return bot.send_message(user.chat_id, text, reply_markup=menu)
			else:
				return bot.send_message(user.chat_id, text)

		try:
			general_dct['users'][user.id]['messages']['signup'] = general_msg
		except KeyError:
			try:
				general_dct['users'][user.id]['messages'] = {'signup': general_msg}
			except KeyError:
				try:
					general_dct['users'][user.id] = {'messages': {'signup': general_msg}}
				except KeyError:
					general_dct['users'] = {user.id: {'messages': {'signup': general_msg}}}

		msg = general_msg()
		temp_msgs('signup', user, msg)

		question = user.current_question()
		if question:
			msg = bot.send_message(user.chat_id, question)
			temp_msgs('user_form', user, msg)
			try:
				temp_dct['users'][user.id]['question'] = {question: datetime.now()}
			except KeyError:
				temp_dct['users'][user.id] = {'question': {question: datetime.now()}}
			temp_dct['users'][user.id]['question']['menu'] = 'signup'
			bot.register_next_step_handler(msg, user_questions_form)

		anti_spam(message)


	@bot.message_handler(func=lambda message: message.text in ['Мои тренировки', '🏃 Мои тренировки'] and blacklist_checking(message) and check_status(message))
	def my_training(message):
		user = User(message.chat.id)
		tariff = user.tariff()
		period = datetime.strftime(user.subscription_plan['period'], '%d.%m.%Y') if user.subscription_plan['period'] else None
		def general_msg():
			if user.current_coach_id:
				if tariff:
					if user.check_period():
						level = user.level()
						text = f'👤 *{user.fullname}*\n\n💷 *Название тарифа*: _{tariff.name or "нет"}_\n' \
							   f'🔃 *Количество тренировок*: _{training_types(user) or "нет"}_\n' \
							   f'⏳ *Срок действия тарифа до*: _{(period if user.check_period() else period + " (истёк)") or "нет"}_\n\n' \
							   f'️‍🏋️‍♀️ *Уровень тренировок*: _{level.name if level else "🥲 пока не определён"}_'

					else:
						text = 'К сожалению, у вас закончился период действия тарифа.\n\n*Оплатите* любой тариф вашего тренера, чтобы получить доступ к этому меню!'
				else:
						text = f'К сожалению, у вас еще нет действующего тарифа, и это меню недоступно.\n\n*Оплатите* любой тариф вашего тренера, чтобы получить доступ к этому меню!',

			else:
				text = '😎 *Воспользуйтесь уникальной* возможностью получить полностью бесплатный курс тренировок и программу питания!\n' \
					   '*Заполнив короткую анкету*, вы получите исключительно индивидуальные рекомендации с учетом ваших потребностей и возможностей.\n\n' \
					   '😃💪 Или нажмите *"Выбрать тренера"*, чтобы ознакомиться с доступными тренерами и наконец начать действовать решительно в режиме онлайн или лично!'

			return bot.send_message(user.chat_id, text, reply_markup=my_training_menu(user))

		try:
			general_dct['users'][user.id]['messages']['my_training'] = general_msg
		except KeyError:
			try:
				general_dct['users'][user.id]['messages'] = {'my_training': general_msg}
			except KeyError:
				try:
					general_dct['users'][user.id] = {'messages': {'my_training': general_msg}}
				except KeyError:
					general_dct['users'] = {user.id: {'messages': {'my_training': general_msg}}}

		msg = general_msg()
		temp_msgs('my_trainings', user, msg)

		question = user.current_question()
		if question:
			msg = bot.send_message(user.chat_id, question)
			temp_msgs('user_form', user, msg)
			try:
				temp_dct['users'][user.id]['question'] = {question: datetime.now()}
			except KeyError:
				temp_dct['users'][user.id] = {'question': {question: datetime.now()}}
			temp_dct['users'][user.id]['question']['menu'] = 'my_training'
			bot.register_next_step_handler(msg, user_questions_form)

		anti_spam(message)

	@bot.message_handler(func=lambda message: message.text in ['🥇 Результаты'] and blacklist_checking(message) and check_status(message))
	def leaderboard(message):
		user = User(message.chat.id)
		coach = Coach(user.chat_id) if user.is_coach else user.coach()
		all_reports = coach.clients_training_reports()
		all_reports = set([i['users_id'] for i in all_reports if i['report_type'] == 'video' and i['credited']]) if all_reports else []
		if all_reports:
			text = (f'*Всего тренирующихся у тренера, зафиксировавших результаты*: _{len(all_reports)}_' if user.is_coach else '🤓 В этом меню можно '
																														 'ознакомиться с результатами клиентов вашего тренера в различных упражнениях.') + \
				   f'\n\n🏋️‍♀️ Выберите *Все результаты*, чтобы просмотреть все лучшие результаты без сортировки по упражнениям.\n' \
				   f'📜 Выберите *По категориям*, чтобы выбрать категорию упражнений для просмотра лучших результатов.\n\n' \
				   f'🎥 При просмотре результатов по категориям можно просмотреть видео выполнения каждого!'
		else:
			text = 'Пока нет зафиксированных результатов.'
		menu = InlineKeyboardMarkup(row_width=1).add(
			InlineKeyboardButton(text='🏋️‍♀️ Все результаты', callback_data='coach_leaderboard'),
			InlineKeyboardButton(text="📜 По категориям", callback_data='coach_leaderboard_categories')
		)
		try:
			general_dct['leaderboard'][coach.id] = {'msg': text}
		except KeyError:
			general_dct['leaderboard'] = {coach.id: {'msg': text}}
		general_dct['leaderboard']['menu'] = menu
		msg = bot.send_message(user.chat_id, text, reply_markup=menu) if all_reports else bot.send_message(user.chat_id, text)
		del_msgs('leaderboard', user)
		temp_msgs('leaderboard', user, msg)

	@bot.message_handler(func=lambda message: message.text == '❔ Помощь' and blacklist_checking(message) and check_status(message))
	def user_help(message):
		anti_spam(message)
		user = User(message.chat.id)
		def general_msg():
			help_menu = InlineKeyboardMarkup(row_width=1)
			buttons = [
				InlineKeyboardButton(text='WhatsApp', url='https://wa.me/79241419949')
			]
			help_menu.add(*buttons)
			return bot.send_message(user.chat_id, '😀 *Добро пожаловать*! \n😇 *Скоро* здесь можно получить помощь по наиболее частым вопросам от пользователей бота.\n\n'
									  '❕ *Для взаимодействия с ботом* вам нужно использовать _главное и побочные меню_. \n'
									  '🔘 *Для пользователей с разными действующими тарифами* (в т.ч. с отсутствующим тарифом) действуют разные *правила допуска* в те или иные разделы меню, то есть к функциям бота.\n\n'									  
									  '😎 *Данный бот очень полезен* для автоматизации процесса работы спортивного или фитнес-тренера и его подопечных. Он позволяет исключить излишнее и требующее внимания и времени обеих сторон взаимодействие.\n'
									  '🤩 *Взаимодействие между тренерами и их подопечными* бывает разного рода: это и оплата услуг тренера клиентом, и запись на занятия согласно графику и возможностям тренера, и проведение спортивных и фитнес-тренировок без контроля тренера, но с необходимой минимальной отчетностью перед ним, и так далее...\n\n'
									  '🤪 *Чтобы не отставать от современных возможностей автоматизации* хотя бы простых взаимодействий между людьми в сфере фитнеса и спорта, был создан этот бот! Надеемся, вам понравится опыт его использования.\n\n'
									  '🤓 Если обнаружили ошибку в работе бота или остались другие вопросы, пожалуйста, выберите удобный способ связи и нажмите на соответствующую кнопку и задайте свой вопрос, отправив также вспомогательную информацию о проблеме в виде скриншотов/записи экрана и т.д.\n\n'
												  'А также будем рады, если поделитесь новыми идеями, которые стоит внедрить в работу бота!', disable_web_page_preview=True, reply_markup=help_menu)

		try:
			general_dct['users'][user.id]['messages']['help'] = general_msg
		except KeyError:
			try:
				general_dct['users'][user.id]['messages'] = {'help': general_msg}
			except KeyError:
				try:
					general_dct['users'][user.id] = {'messages': {'help': general_msg}}
				except KeyError:
					general_dct['users'] = {user.id: {'messages': {'help': general_msg}}}

		msg = general_msg()

		del_msgs('help', user)
		temp_msgs('help', user, msg)

		question = user.current_question()
		if question:
			msg = bot.send_message(user.chat_id, question)
			temp_msgs('user_form', user, msg)
			try:
				temp_dct['users'][user.id]['question'] = {question: datetime.now()}
			except KeyError:
				temp_dct['users'][user.id] = {'question': {question: datetime.now()}}
			temp_dct['users'][user.id]['question']['menu'] = 'help'
			bot.register_next_step_handler(msg, user_questions_form)

		anti_spam(message)

	@bot.callback_query_handler(func=lambda callback: callback.data and blacklist_checking(callback, callback=True))
	def training_packages(callback):
		user = User(callback.message.chat.id)
		if user.is_coach:
			coach = Coach(user.chat_id)
		anti_spam(callback, callback=True)
		
		query = callback.data
		user.set_last_callback(callback)
		
		# ____________________________________________
		# ADMIN FUNCS
		if query == 'my_mailing':
			msg = bot.send_message(coach.chat_id, 'Write an needed text for sending to all users (only to non-blocked users).\n\n'
												  'OR write "Q" for cancel sending mails.')
			from scripts.mailing import get_mailing_text
			bot.register_next_step_handler(msg, get_mailing_text)

		if query == 'coach_help':
			text = 'Скоро здесь будет подробная помощь по каждой из функций бота.\n\n' \
				   'А пока для связи с командой поддержки бота и решения возможных проблем с ним (' \
				   'например, если встретились с ошибкой или не до конца разобрались с какой-либо функцией) вы можете отправить письмо на нашу электронную' \
				   ' почту: <a href="mailto:ijoech@gmail.com">Отправить</a>.\n\n' \
				   'В письме укажите суть проблемы/вопроса, приложите вспомогательные скриншоты/запись экрана, чтобы мы лучше могли понять вашу проблему и помочь ' \
				   'определить ее решение.\n\nСпасибо за понимание!'
			msg = bot.send_message(coach.chat_id, text)
			temp_msgs('main_admin', coach, msg)

		if query == 'my_mailing':
			pass


		if query.startswith('my_commerce'):
			menu = InlineKeyboardMarkup(row_width=1)
			if query == 'my_commerce':
				coach_form = coach.form()
				buttons = [
					InlineKeyboardButton(text='💰 Тарифы', callback_data='my_tariffs'),
					InlineKeyboardButton(text='🤑 Акции', callback_data='my_promotions'),
					InlineKeyboardButton(text='📈 Доходы', callback_data='my_commerce_salary'),
					InlineKeyboardButton(text='💷 Транзакции', callback_data='my_commerce_transactions')
				]
				text = '*Тарифы* - доступные тарифы, их редактирование и конструктор для создания новых.\n\n' +\
					   '*Акции* - доступные акции и конструктор для создания новых.\n\n' +\
					   '*Доходы по месяцам* - количество и детализация доходов.\n\n'
				menu.add(*buttons[:-1])
				if coach_form['paying_type'] == 'freelancer':
					if not coach_form['paying_link'] and any(filter(lambda x: x.type == 5, coach.tasks)):
						menu.add(buttons[-1])
						text += '*Транзакции* - выполнить нужные операции по фиксации оплаты от клиентов.'
						
				msg = bot.send_message(coach.chat_id, text, reply_markup=menu)
			
			elif query.startswith('my_commerce_transactions'):
				step = len(query.split())
				tasks = [task for task in coach.tasks if task.type_number == 5]
				if step == 1:
					if tasks:
						text = '\n\n'.join([f"💰 *Транзакция №{tasks.index(task) + 1}*\n"
											f"- Клиент: {User(user_id=task.additional_info[0]).fullname}\n"
											f"- Тариф: {Tariff(task.additional_info[1]).name}\n"
											f"- Сумма: {task.additional_info[2]}₽s" for task in sorted(tasks, key=lambda x: x.date)]) + '\n\n' \
																																		'Нажмите на имя клиента, чтобы отправить ему чек об оплате тарифа.'
						buttons = [telebutton(f'💰 {User(user_id=task.additional_info[0]).fullname}', f'my_commerce_transactions {tasks.index(task)}')]

				elif step == 2:
					task_idx = query.split()[1]
					task = tasks[task_idx]
					usr, tariff, payment_amount = User(user_id=task.additional_info[0]), Tariff(task.additional_info[1]), task.additional_info[2]

					text = f'- Клиент: {usr.fullname}\n' \
						   f'- Тариф: {tariff.name}\n' \
						   f'- Сумма: {payment_amount}₽\n\n' \
						   f'Просто отправьте сюда чек о фиксации оплаты в качестве самозанятого лица (оформить можно через приложение *"Мой налог"* или другое приложение, ' \
						   f'обеспечивающее вашу работу юридически).'
					coach.status = f'sending_receipt {user.id} {tariff.id} {payment_amount}'
					coach.set_coach()
					buttons = []
				msg = bot.send_message(coach.chat_id, text, reply_markup=menu.add(*buttons)) if buttons else bot.send_message(coach.chat_id, text)

			elif query.startswith('my_commerce_salary'):
				len_cb, splitted = len(query.split()), query.split()
				salary = coach.salary()
				menu = InlineKeyboardMarkup(row_width=1)
				if salary:
					if len_cb == 1:
						buttons = [InlineKeyboardButton(text=i, callback_data=f'my_commerce_salary {i}') for i in set(sorted([j['payment_date'].year for j in salary]))]
						text = 'Выберите год получения платежей.'
						menu.add(*buttons, InlineKeyboardButton(text='👈 Назад', callback_data='my_commerce'))
					elif len_cb == 2:
						year = int(splitted[1])
						buttons = [InlineKeyboardButton(text=months[i - 1].title(), callback_data=f'my_commerce_salary {year} {i}') for i in set([j['payment_date'].month for j in salary if j['payment_date'].year == year])]
						text = f'Выберите месяц получения платежей ({year} год).'
						menu.add(*buttons, InlineKeyboardButton(text='👈 Назад', callback_data='my_commerce_salary'))
						menu.row_width=2
					elif len_cb == 3:
						year, month = int(splitted[1]), int(splitted[2])
						salary = sorted(filter(lambda x: x['payment_date'].year == year and x['payment_date'].month == month, salary), key=lambda x: x['payment_date'])
						text = f'*{months[month - 1].title()} {year}*\n\n' + '\n\n'.join([f'💰 *Платеж от {i["payment_date"]}*\n'
										   f'- Клиент: *{User(user_id=i["users_id"]).fullname}*\n'
										   f'- Тариф: *"{Tariff(i["tariff_id"]).name}"*\n'
										   f'- Сумма: *{i["payment_amount"]}*₽' for i in salary])
						menu.add(InlineKeyboardButton(text='👈 Назад', callback_data=f'my_commerce_salary {year}'))
				else:
					text = 'История платежей пока пуста.'
					menu.add(InlineKeyboardButton(text='👈 Назад', callback_data='my_commerce'))
				msg = bot.send_message(coach.chat_id, text, reply_markup=menu)
			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)


		if query == 'my_promotions':
			bot.send_message(coach.chat_id, 'Скоро здесь будут доступные акции и конструктор акций.')
			del_msgs('main_admin', coach)

		if query == 'my_clients_training':
			buttons = [InlineKeyboardButton(text='💪 Уровни тренировок', callback_data='training_levels'),
					   InlineKeyboardButton(text='🏋️ Тренировочные планы', callback_data='training_plans')]
			msg = bot.send_message(coach.chat_id, 'Вы можете управлять доступными уровнями сложности тренировок для своих клиентов, чтобы поддерживать их интерес к самостоятельным тренировкам по мере развития физической формы.\n\n'
												  'А также непосредственно придумывать тренировочные планы для каждого уровня тренирующихся в неограниченном количестве в предложенном конструкторе.',
								   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons))
			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)

		if query.startswith('training_levels'):
			levels = coach.levels()
			levels = sorted(levels, key=lambda x: x['id']) if levels else None
			if query == 'training_levels':
				if levels:
					msg = bot.send_message(coach.chat_id, f'Доступные для клиентов уровни сложностей:\n\n' + '\n\n'.join([f'*Номер уровня* (в развитии физподготовки клиентов): _{levels.index(i) + 1}_\n*Название*: "{i["level_name"]}"\n*Количество тренировок*: _{i["level_sessions_amount"] if i["level_sessions_amount"] != 0 else "не назначено"}_\n*Описание*: "_{i["level_description"]}_"' for i in levels]) + '\n\n*Нажмите на название* уровня сложности, чтобы _изменить его_ или _удалить_.\n'
																																																												   'Или нажмите *"Добавить"*, чтобы добавить новый.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(
											   *[InlineKeyboardButton(text=f'"{i["level_name"]}"', callback_data=f'training_levels {i["id"]}') for i in levels],
											   InlineKeyboardButton(text='Добавить', callback_data='training_levels_add'),
											   InlineKeyboardButton(text='👈 Назад', callback_data='my_clients_training')
										   ))
				else:
					msg = bot.send_message(coach.chat_id, f'Уровней сложности тренировок пока нет.\n\nДобавьте новые, нажав *"Добавить"*.',
									 reply_markup=InlineKeyboardMarkup(row_width=1).add(
										 InlineKeyboardButton(text='Добавить', callback_data='training_levels_add')
									 ))

			elif query.startswith('training_levels '):
				level = coach.levels(level_id=query.split()[1])
				msg = bot.send_message(coach.chat_id, f'Выберите, что нужно сделать с уровнем сложности "*{level["level_name"]}*"', parse_mode="Markdown",
								 reply_markup=InlineKeyboardMarkup(row_width=1).add(
									 InlineKeyboardButton(text='Изменить количество тренировок', callback_data=f'training_levels_change {level["id"]}'),
									 InlineKeyboardButton(text='Удалить', callback_data=f'training_levels_delete {level["id"]}')
								 ))

			elif query.startswith('training_levels_add'):
				if len(query.split()) == 1:
					msg = bot.send_message(coach.chat_id, '*Определите* название для нового уровня сложности _(например "продвинутый")_. Напишите его.\n\n'
														  'Или введите *"Q"*, чтобы отменить создание уровня.', parse_mode="Markdown")
					bot.register_next_step_handler(msg, new_training_self_level)
				else:
					level_name = ' '.join(query.split()[1:-1])
					sessions_amount = int(query.split()[-1])
					temp_dct['coaches'][f'creating_level {coach.id}'] = {'name': level_name,
															  'sessions_amount': sessions_amount}

					msg = bot.send_message(coach.chat_id, f'Опишите уровень подготовки, чтобы клиенты хотя бы косвенно понимали его суть и степень своего развития.\n'
														  f'Например, "уровень для только начинающих свой путь в мире фитнеса".')
					bot.register_next_step_handler(msg, new_training_self_level)
			elif query.startswith('training_levels_change'):
				if not query.startswith('training_levels_change_to '):
					level = coach.levels(level_id=query.split()[1])
					msg = bot.send_message(coach.chat_id, f'Выберите новое количество тренировок, необходимое для продвижения через уровень "*{level["level_name"]}*" к следующему\n\n'
														  f'Или нажмите "*Не назначать*", чтобы не ограничивать уровень количеством тренировок (например, если данный уровень подготовки будет максимально возможным или единственным).',
										   reply_markup=InlineKeyboardMarkup(row_width=4).add(
											   *[InlineKeyboardButton(text=i, callback_data=f'training_levels_change_to {level["id"]} {i}') for i in [3, 5, 7, 10, 15, 20, 25, 30]],
										   InlineKeyboardButton(text='Не назначать', callback_data=f'training_levels_change_to {level["id"]} 0')))
				else:
					level = coach.levels(level_id=query.split()[1])
					sessions_amount = int(query.split()[-1])
					coach.levels(update=True, level_id=level['id'], level_sessions_amount=sessions_amount)
					msg = bot.send_message(coach.chat_id, f'Количество тренировок на уровне "*{level["level_name"]}*", необходимое для выполнения клиентам для продвижения к следующему уровню, успешно изменено на _{sessions_amount if sessions_amount != 0 else "не назначено"}_!',
										   reply_markup=admin_keyboard())
			elif query.startswith('training_levels_delete '):
				level = coach.levels(level_id=query.split()[1])
				with database() as connection:
					with connection.cursor() as db:
						db.execute(f"SELECT chat_id FROM users WHERE training_levels_id = {level['id']}")
						users_lst = db.fetchall()
						db.execute(f"DELETE FROM coachs_levels WHERE id = {level['id']}")
						connection.commit()
						msg = bot.send_message(coach.chat_id,
											   f'Уровень подготовки (сложности тренировок) *{level["level_name"]}* был успешно удален!',
											   parse_mode='Markdown', reply_markup=admin_keyboard())
						if users_lst:
							users_lst = [User(i['chat_id']) for i in users_lst]
							for u in users_lst:
								# потестить
								u.training_levels_id = None
								u.set_user()
								bot.send_message(u.chat_id, f'😔 *К сожалению*, ваш тренер удалил уровень подготовки (самостоятельные тренировки) под названием *{level_name}*.\n'
															  f'Но вся ваша статистика и история тренировок по нему _сохранилась_!\n\n'
															  f'*Чтобы продолжать* самостоятельные тренировки, придется перейти на другой уровень (автоматически при получении плана самостоятельных тренировок).')

			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)


		if query.startswith('coach_leaderboard'):
			splitted = query.split()
			coach = Coach(callback.message.chat.id) if user.is_coach else user.coach()
			leaders = coach.leaderboard()
			menu = InlineKeyboardMarkup(row_width=1)
			buttons = []
			leaders_reps, leaders_weight = leaders['repeats'], leaders['weight']
			out = {'repeats': [], 'weight': []}
			text = ''
			msg = None
			if query == 'coach_leaderboard':
				for ex in leaders_reps:
					ex_obj = Exercise(ex, coach=False)
					params = leaders_reps[ex]
					out['repeats'].append((ex_obj.name, *params))
				for ex in leaders_weight:
					ex_obj = Exercise(ex, coach=False)
					params = leaders_weight[ex]
					out['weight'].append((ex_obj.name, *params))
			elif query == 'coach_leaderboard_main':
				text = general_dct['leaderboard'][coach.id]['msg']
				menu = general_dct['leaderboard']['menu']
			elif query.startswith('coach_leaderboard_categories'):
				if len(splitted) == 1:
					categories = []
					for ex in list(leaders_reps) + list(leaders_weight):
						ex_obj= Exercise(ex, coach=False)
						categories.append((ex_obj.category, ex_obj.category_id))
					buttons = [InlineKeyboardButton(text=i[0][0].upper() + i[0][1:], callback_data=f'coach_leaderboard_categories {i[1]}') for i in sorted(set(categories), key=lambda x: x[0])]
				elif len(splitted) == 2:
					category = int(splitted[1])
					buttons = []
					for ex in leaders_reps:
						ex_obj = Exercise(ex, coach=False)
						if ex_obj.category_id == category:
							params = leaders_reps[ex]
							out['repeats'].append((ex_obj.name, *params))
							name = ex_obj.name[0].upper() + ex_obj.name[1:]
							buttons.append(InlineKeyboardButton(text=name, callback_data=f'coach_leaderboard_categories video {ex}'))
					for ex in leaders_weight:
						ex_obj = Exercise(ex, coach=False)
						if ex_obj.category_id == category:
							params = leaders_weight[ex]
							out['weight'].append((ex_obj.name, *params))
							name = ex_obj.name[0].upper() + ex_obj.name[1:]
							buttons.append(InlineKeyboardButton(text=name, callback_data=f'coach_leaderboard_categories video {ex}'))
					buttons = sorted(buttons, key=lambda x: x.text)
				elif len(splitted) == 3:
					ex_id = int(splitted[2])
					for ex in leaders_reps:
						if ex_id == ex:
							video_id = leaders_reps[ex][2]
					for ex in leaders_weight:
						if ex_id == ex:
							video_id = leaders_weight[ex][2]
					msg_2 = bot.send_video(user.chat_id, video_id)
					temp_msgs('leaders_video', user, msg)

			if len(splitted) == 1 or len(splitted) > 1 and splitted[1] != 'video':
				if out['repeats']:
					out['repeats'] = sorted(out['repeats'], key=lambda x: x[0])
					text += '💪🏃 Лидеры по повторениям\n\n' + '\n---\n'.join(
						[f'🥇 Упражнение: _{i[0]}_\n- Результат: _{i[1]} повторений_\n'
						 f'- Выполнил: _{User(user_id=i[2]).fullname}_' for i in out['repeats']])
				if out['weight']:
					out['weight'] = sorted(out['weight'], key=lambda x: x[0])
					text += '\n\n🏋️‍♀️🏃 Лидеры по отягощению\n\n' + '\n---\n'.join(
						[f'🥇 Упражнение: _{i[0]}_\n- Результат: _{i[1]}_ кг\n'
						 f'- Выполнил: _{User(user_id=i[2]).fullname}_' for i in out['weight']])
			if query.startswith('coach_leaderboard_categories'):
				if len(splitted) == 1:
					text = 'Выберите категорию упражнений для просмотра зафиксированных результатов по ней.'
				elif len(splitted) == 2:
					text += '\n\nВыберите название упражнения, чтобы просмотреть видео по нему.'
			if buttons:
				menu.add(*buttons)
			if text:
				if query.startswith('coach_leaderboard_categories'):
					if len(splitted) > 1:
						menu.add(InlineKeyboardButton(text='👈 Назад', callback_data='coach_leaderboard_categories'))
					else:
						menu.add(InlineKeyboardButton(text='👈 Назад', callback_data='coach_leaderboard_main'))
				elif query == 'coach_leaderboard':
					menu.add(InlineKeyboardButton(text='👈 Назад', callback_data='coach_leaderboard_main'))
				msg = bot.send_message(user.chat_id, text, reply_markup=menu)
			if msg:
				del_msgs('leaderboard', user)
				temp_msgs('leaderboard', user, msg)



		if query.startswith('training_plan'):
			levels = coach.levels()
			exs_info = exercise_info()
			if query.startswith('training_plans'):
				if len(query.split()) == 1:
					if levels:
						buttons = [InlineKeyboardButton(text=f'Ур. "{i["level_name"]}"', callback_data=f'training_plans {i["id"]}') for i in sorted(levels, key=lambda x: x['level_name'])]
						msg = bot.send_message(coach.chat_id, '*Чтобы создать* план _самостоятельной_ тренировки для определенного уровня тренирующихся клиентов, нажмите *"Новый план"*.\n\n'
															  '*Чтобы просмотреть* _текущие доступные планы_ или удалить их, нажмите на название уровня сложности из имеющихся, содержащего в себе тренировочные планы.\n\n'
															  '*Чтобы создать* и отправить _индивидуальный_ план конкретному клиенту, нужно выбрать его в меню *"Клиенты"* и перейти в *"Отправить задание"*.',
											   reply_markup=InlineKeyboardMarkup(row_width=1).add(
												   *buttons,
												   InlineKeyboardButton(text='🟢 Новый план', callback_data='training_plan_create'),
												   InlineKeyboardButton(text='👈 Назад',
																		callback_data='my_clients_training')
											   ))
					else:
						msg = bot.send_message(coach.chat_id, 'У вас еще нет ни одного уровня развития физической формы для клиентов!\n\n'
															  'Создайте их в меню *"Тренировки клиентов"* 👉 *"Уровни"*, а затем сможете сформировать свой первый тренировочный план.')
				elif len(query.split()) == 2:
					training_plans = coach.training_plans(level_id=query.split()[1])
					if training_plans:
						import json
						plans = [i for i in sorted(training_plans, key=lambda x: (x['session_rate'], len(json.loads(x['session_exercises']))))]
						lvl_name = [i["level_name"] for i in levels if i["id"] == int(query.split()[1])][0]
						lst = [f'🏋️‍♀️ Тренировочный план *№{plans.index(i) + 1}*\n\n*Сложность тренировки*: _{i["session_rate"]} из 10_\n*Максимальная длительность*: _{i["session_duration"]} мин_\n' \
							   f'*Дополнительные условия*: _{i["session_terms"] if i["session_terms"] else "нет"}_\n' \
							   '*Вспомогательные медиа*: ' + ', '.join(["видео - да" if i["informational_video"] else "видео - нет", "аудио - да" if i["informational_audio"] else "аудио - нет", "изображение - да" if i["informational_image"] else "изображение - нет"]) + '\n\n*Упражнения:*\n' + '\n--------------\n'.join([f'— *{j.name}*\n\tусловия: _{j.terms if j.terms else "нет"}_\n\tотягощение: _{j.weight if j.weight else ("нет" if not j.unit else "на усмотрение")}_\n'
																																																										f'\tподходов: _{j.sets if j.sets else "не указано"}_\n'
																																																										f'\tповторений: _{j.repeats if not j.repeats is None else "максимум"}_\n'
																																																										f'\tвспомогательные медиа: _{"да" if any([j.video, j.audio, j.image]) else "нет"}_' for j in coach.training_plans(plan_id=i["id"], exercises=True)]) for i in plans]
						text = util.smart_split('\n\n'.join(lst), 3000)
						buttons = [*[InlineKeyboardButton(text=f'❌{i}',
														callback_data=f'training_plans_delete_session {query.split()[1]} {i}')
								   for i in [plans.index(j) + 1 for j in plans]],
								   InlineKeyboardButton(text='👈 Назад', callback_data='training_plans')]
						if len(text) > 1:
							for txt in text:
								if txt == text[0]:
									msg = bot.send_message(coach.chat_id, f'Уровень *"{lvl_name}"*\n\n{txt}')
								elif txt != text[0] and txt != text[-1]:
									msg = bot.send_message(coach.chat_id, txt)
								elif text == text[-1]:
									msg = bot.send_message(coach.chat_id, txt + '\n\n❌ *Нажмите на кнопку* с номером тренировочного плана, чтобы удалить его.\n\n'
																				'‼️ Важно! Клиенты получают тренировки в том порядке, в котором вы их видите.\nСортировка производится по _сложности тренировки_ и по _количеству упражнений_.', reply_markup=InlineKeyboardMarkup(row_width=5).add(*buttons))
						elif len(text) == 1:
							msg = bot.send_message(coach.chat_id, text[0] + '\n\n❌ *Нажмите на кнопку* с номером тренировочного плана, чтобы удалить его.\n\n'
																			'‼️ *Важно!* Клиенты получают тренировки в том порядке, в котором вы их видите.\nСортировка производится по _сложности тренировки_ и по _количеству упражнений_.', reply_markup=InlineKeyboardMarkup(row_width=5).add(*buttons))
					else:
						msg = bot.send_message(coach.chat_id, 'Пока нет ни одного тренировочного плана для данного уровня.')

				elif len(query.split()) == 3:
					if query.split()[0] == 'training_plans_delete_session':
						level_id = int(query.split()[1])
						plans = [i for i in sorted(coach.training_plans(level_id=query.split()[1]), key=lambda x: x['id']) if i["session_type"] == 'self']
						plan = plans[int(query.split()[2]) - 1]
						with database() as connection:
							with connection.cursor() as db:
								db.execute(f"DELETE FROM coachs_training_plans WHERE coachs_levels_id = {level_id} AND id = {plan['id']}")
								connection.commit()
						msg = bot.send_message(coach.chat_id, f'Тренировочный план *№{query.split()[2]}* успешно удален из уровня *{[i["level_name"] for i in levels if i["id"] == level_id][0]}*!',
											   reply_markup=admin_keyboard())


			elif query.startswith('training_plan_create'):
				if len(query.split()) == 1:
					if query == 'training_plan_create':
						buttons = [InlineKeyboardButton(text=f'"{i["level_name"]}"', callback_data=f'training_plan_create {i["id"]}')
								   for i in sorted(levels, key=lambda x: x['level_name'])]
						msg = bot.send_message(coach.chat_id, 'Выберите уровень, для которого хотите создать тренировочный план.',
											   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons))
					elif query == 'training_plan_create_stop':
						temp_dct['coaches'].pop(coach.id, None)
						msg = bot.send_message(coach.chat_id, 'Создание тренировочного плана отменено.', reply_markup=admin_keyboard())
					elif query == 'training_plan_create_end':
						exs = temp_dct['coaches'][coach.id]['creating_plan']['exercises']
						coach_exs = []
						for ex_id in exs:
							current_ex = Exercise(ex_id, coach=False)
							repeats = exs[ex_id]['repeats']
							sets = exs[ex_id]['sets']
							terms = exs[ex_id]['terms']
							video, audio, image = exs[ex_id]['video'], exs[ex_id]['audio'], exs[ex_id]['image']
							coach_exs.append(Exercise.new_coach_exercise(coach, current_ex, repeats, sets=sets, terms=terms, video=video, audio=audio, image=image))

						training_plan = TrainingPlan(coach=coach)
						training_plan.exercises = {i: False for i in coach_exs}
						training_plan.duration = temp_dct['coaches'][coach.id]['creating_plan']['session_duration']
						training_plan.levels_id = int(temp_dct['coaches'][coach.id]['creating_plan']['level_id'])
						training_plan.video = temp_dct['coaches'][coach.id]['creating_plan']['video']
						training_plan.audio = temp_dct['coaches'][coach.id]['creating_plan']['audio']
						training_plan.image = temp_dct['coaches'][coach.id]['creating_plan']['image']
						training_plan.rate = temp_dct['coaches'][coach.id]['creating_plan']['session_rate']
						training_plan.type = 'self'
						training_plan.terms = temp_dct['coaches'][coach.id]['creating_plan']['session_terms']
						training_plan.new()
						plan_number = len(coach.training_plans(level_id=training_plan.levels_id))
						temp_dct['coaches'].pop(coach.id, None)

						try:
							level = Level(level_id=training_plan.levels_id)
							if not coach.tasks is None:
								for task in coach.tasks:
									if task.type_number == 4:
										if task.additional_info[0] == 'create_training_plans' and level.name == task.additional_info[1]:
											task.delete(coach)
						finally:
							msg = bot.send_message(coach.chat_id, f'Тренировочный план *№{plan_number}* для уровня *"{[i["level_name"] for i in levels if i["id"] == training_plan.levels_id][0]}"* успешно сохранен!\n\n', reply_markup=admin_keyboard())


				elif len(query.split()) == 2:
					level_id = query.split()[1]
					plans = coach.training_plans(level_id=level_id)
					plan_number = len(plans) + 1 if plans else 1
					def msg():
						try:
							plan_exercises = [Exercise(i, coach=False) for i in temp_dct['coaches'][coach.id]['creating_plan']['exercises'].keys()]
							coach_exercises = temp_dct['coaches'][coach.id]['creating_plan']['exercises']
						except KeyError:
							if not coach.id in temp_dct['coaches']:
								temp_dct['coaches'][coach.id] = {'creating_plan': {'exercises': {},
																		 'level_id': level_id,
																		'session_duration': None,
																		'session_rate': None,
																		'session_terms': None,
																		'video': None,
																		'audio': None,
																		'image': None}}
							else:
								temp_dct['coaches'][coach.id]['creating_plan']['exercises'] =  {}
								temp_dct['coaches'][coach.id]['creating_plan']['level_id'] = level_id
								temp_dct['coaches'][coach.id]['creating_plan']['session_duration'] = None
								temp_dct['coaches'][coach.id]['creating_plan']['session_rate'] = None
								temp_dct['coaches'][coach.id]['creating_plan']['video'] = None
								temp_dct['coaches'][coach.id]['creating_plan']['audio'] = None
								temp_dct['coaches'][coach.id]['creating_plan']['image'] = None
								temp_dct['coaches'][coach.id]['creating_plan']['session_terms'] = None
							plan_exercises = {}
							coach_exercises = {}
						plan_general = temp_dct['coaches'][coach.id]['creating_plan']

						if not plan_exercises:
							buttons = [
								InlineKeyboardButton(text='Добавить упражнение', callback_data='training_plan_add_exercise'),
													 InlineKeyboardButton(text='Отменить и выйти', callback_data='training_plan_create_stop')
							]
						else:
							buttons = [
								InlineKeyboardButton(text='Максимальная длительность',
													 callback_data='training_plan_add_params session_duration'),
								InlineKeyboardButton(text='Рейтинг (сложность)',
													 callback_data='training_plan_add_params session_rate'),
								InlineKeyboardButton(text='Общие условия',
													 callback_data='training_plan_add_params session_terms'),
								InlineKeyboardButton(text='Вспомогательные медиа',
													 callback_data='training_plan_add_params media'),
								InlineKeyboardButton(text='Добавить упражнение', callback_data='training_plan_add_exercise'),
								InlineKeyboardButton(text='Отменить и выйти', callback_data='training_plan_create_stop')
							]
						if plan_general['session_duration'] and plan_general['session_rate'] and plan_general['exercises']:
							menu = InlineKeyboardMarkup(row_width=1).add(*buttons, InlineKeyboardButton(text='Закончить и сохранить', callback_data=f'training_plan_create_end'))
						else:
							menu = InlineKeyboardMarkup(row_width=1).add(*buttons)
						current_exercises = '\n------------\n'.join([f'- {i.name}:\n _подходов_: {coach_exercises[i.exercises_id]["sets"] if coach_exercises[i.exercises_id]["sets"] else "не указано"}\n _повторений_: {coach_exercises[i.exercises_id]["repeats"] if not coach_exercises[i.exercises_id]["repeats"] is None else "максимум"}\n _отягощение_: на усмотрение' for i in plan_exercises]) if plan_exercises else "пусто"
						return bot.send_message(coach.chat_id, f'План *№{plan_number}* для уровня *"{[i["level_name"] for i in levels if i["id"] == int(level_id)][0]}"*.\n\n'
															  f'*Сейчас он содержит упражнения*:\n'
															  f'{current_exercises}\n\n'
															  f'*Максимальная длительность тренировки*: _{plan_general["session_duration"] + " мин" if plan_general["session_duration"] else "не указана (обязательный параметр)"}_\n\n'
															  f'*Сложность*: _{plan_general["session_rate"] + " из 10" if plan_general["session_rate"] else "не указана (обязательный параметр)"}_\n\n'
															  f"*Дополнительные условия тренировки*:\n_{plan_general['session_terms'] if plan_general['session_terms'] else 'не указаны'}_\n\n"
															  f"*Вспомогательные медиа*:\n" + ', '.join([f'_{exs_info[i].lower()} - {"да" if plan_general[i] else "нет"}_' for i in plan_general if i in ['video', 'audio', 'image']]), reply_markup=menu)
					try:
						temp_dct['coaches'][coach.id]['creating_plan']['msg'] = msg
					except KeyError:
						temp_dct['coaches'][coach.id] = {'creating_plan': {'msg': msg}}
					msg = temp_dct['coaches'][coach.id]['creating_plan']['msg']()

			elif query.startswith('training_plan_add_params'):
				if len(query.split()) == 2:
					param = query.split()[1]
					if param == 'session_duration':
						d = {10: '10 мин', 20: "20 мин", 30: "30 мин", 40: "40 мин", 50: "50 мин", 60: "1 ч", 90: "1.5 ч", 120: "2 ч", 180: "3 ч"}
						buttons = [InlineKeyboardButton(text=d[i], callback_data=f'training_plan_add_params {param} {i}') for i in [10,20,30,40,50,60,90,120,180]]
						msg = bot.send_message(coach.chat_id, 'Выберите длительность тренировки.', reply_markup=InlineKeyboardMarkup(row_width=4).add(*buttons))

					elif param == 'session_rate':
						buttons = [
							InlineKeyboardButton(text=i, callback_data=f'training_plan_add_params {param} {i}') for i
							in range(1,11)]
						msg = bot.send_message(coach.chat_id, 'Укажите сложность тренировки (примерно) по шкале от 1 до 10.',
											   reply_markup=InlineKeyboardMarkup(row_width=4).add(*buttons))

					elif param == 'session_terms':
						msg = bot.send_message(coach.chat_id, 'Напишите, какие дополнительные условия по выполнению тренировки нужно указать для клиентов.')
						bot.register_next_step_handler(msg, training_plan_add_info)

					elif param == 'media':
						coach.status = f'creating_plan media'
						try:
							coach.set_coach()
						finally:
							msg = bot.send_message(coach.chat_id, 'Отправьте любой медиа-файл из следующих форматов: видео (сжатое), изображение (сжатое), голосовое сообщение.\n\n'
																	  'Он будет добавлен в качестве вспомогательной информации для тренировочного плана.')


				elif len(query.split()) == 3:
					param = query.split()[1]
					val = query.split()[2]
					temp_dct['coaches'][coach.id]['creating_plan'][param] = val
					msg = temp_dct['coaches'][coach.id]['creating_plan']['msg']()

			elif query.startswith('training_plan_add_exercise'):
				if len(query.split()) == 1:
					buttons = [InlineKeyboardButton(text=i['category_name'].title(), callback_data=f'training_plan_add_exercise {i["id"]}') for i in sorted(coach.exercises_categories(), key=lambda x: x['category_name'])]
					msg = bot.send_message(coach.chat_id, f'Выберите нужную категорию упражнений.\n'
														  f'Вам предлагаются категории упражнений исходя из специфики вашей работы.\n\n'
														  f'Или нажмите *"Отменить и выйти"*, чтобы прекратить создание тренировочного плана.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																							  InlineKeyboardButton(text='Отменить и выйти', callback_data='training_plan_create_stop')))
				elif len(query.split()) == 2:
					category_id = query.split()[1]
					level_id = temp_dct['coaches'][coach.id]['creating_plan']['level_id']
					with database() as connection:
						with connection.cursor() as db:
							db.execute(f"SELECT * FROM exercises WHERE exercises_category_id = {category_id}")
							exercises = sorted(db.fetchall(), key=lambda x: x['exercise_name'])
					buttons = [InlineKeyboardButton(text=i['exercise_name'], callback_data=f'training_plan_add_exercise {level_id} {i["exercise_id"]}') for i in exercises]
					msg = bot.send_message(coach.chat_id, 'Выберите нужное упражнение или нажмите "Назад", чтобы вернуться к выбору категории.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(
											   *buttons,
											   InlineKeyboardButton(text='👈 Назад', callback_data=f'training_plan_add_exercise')
										   ))
				elif len(query.split()) == 3:
					exercise = Exercise(query.split()[2], coach=False)
					level_id = query.split()[1]
					try:
						params = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]
					except KeyError:
						params = {
							'terms': None, 'sets': None, 'repeats': None, 'video': None,
							'image': None, 'audio': None, 'check_exercise': False
						}
						temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id] = params

					def msg(level_id=level_id, exercise=exercise):
						params = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]
						buttons = [InlineKeyboardButton(text=exs_info[i],
														callback_data=f'training_plan_add_exercise set {i} {exercise.exercises_id}')
								   for i in sorted(
								{i: j for i, j in params.items() if not i in ['msg', 'level_id', 'menu', 'check_exercise']}, key=lambda x: exs_info[x])]
						menu = InlineKeyboardMarkup(row_width=1)
						if not params['repeats'] is None or params['repeats'] is None and params['check_exercise'] is True:
							menu.add(*buttons, InlineKeyboardButton(text='Закончить',
																	callback_data=f'training_plan_create {level_id}'))
						else:
							menu.add(*buttons)
						temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['menu'] = menu


						return bot.send_message(coach.chat_id, f'Категория упражнения: *{exercise.category}*\n'
														f'Название упражнения: *{exercise.name}*\n'
														f'Инвентарь: *{exercise.inventory_name if exercise.inventory_name else "не требуется"}*\n'
														f'Целевая мышечная группа: *{exs_info[exercise.muscles_group]}*\n'
														f'Сложность: *{exs_info[exercise.difficulty]}*\n'
														f'Тип: *{exs_info[exercise.type]}*\n'
														f'Единица измерения (отягощения, объема): *{exs_info[exercise.unit] if exercise.unit else "отсутствует"}*\n\n'
														f'Текущие указанные параметры:\n- ' + '\n- '.join(
							[f'_{exs_info[i]}_: {(params[i] if not i in ["audio", "video", "image", "repeats"] else ("да" if i in ["audio", "image", "video"] else (params[i] if not i == "weight" and not params[i] is None else "максимум"))) if params[i] else (("не указано" if not i in ["audio", "video", "image", "terms"] else "нет"))}' for i in [j for j in params if not j in ["msg", "level_id", "menu", 'check_exercise']]]) +
										 f'\n\nОбязательный параметр для упражнения: *"Количество повторений"*. ‼️ Указать отягощение нельзя - клиент всегда будет использовать отягощение на свое усмотрение (чтобы не возникало сложных ситуаций с невыполнимыми упражнениями).\nОстальные параметры можно указать по желанию.\n\n'
										 f'Выберите нужный параметр, чтобы задать его. Нажмите *"Закончить"*, чтобы сохранить изменения и перейти к редактированию тренировочного плана.', reply_markup=menu)

					temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['msg'] = msg
					msg = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['msg']()

				elif len(query.split()) == 4:
					if query.split()[1] == 'set':
						param = query.split()[2]
						exercise = Exercise(query.split()[3], coach=False)

						if param == 'terms':
							msg = bot.send_message(coach.chat_id, 'Напишите дополнительные условия для упражнения, которые нужно будет соблюсти при его выполнении клиентами.')
							temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['terms'] = 'setting'
							bot.register_next_step_handler(msg, exercise_add_info)
						elif param == 'sets':
							buttons = [InlineKeyboardButton(text=i, callback_data=f'training_plan_add_exercise sets {i} {exercise.exercises_id}') for i in range(1, 26)]
							msg = bot.send_message(coach.chat_id, 'Выберите необходимое количество подходов для упражнения.', reply_markup=InlineKeyboardMarkup(row_width=5).add(*buttons))
						elif param == 'repeats':
							buttons = [*[InlineKeyboardButton(text=i,
															callback_data=f'training_plan_add_exercise repeats {i} {exercise.exercises_id}')
									   for i in [1,2,3,4,5,6,7,8,9,10,12,15,20,30,40,50,100,150,200,250,300]],
									   InlineKeyboardButton(text='max', callback_data=f'training_plan_add_exercise repeats None {exercise.exercises_id}')]
							msg = bot.send_message(coach.chat_id,
												   'Выберите необходимое количество повторений для упражнения.',
												   reply_markup=InlineKeyboardMarkup(row_width=5).add(*buttons))
						elif param in ['video', 'image', 'audio']:
							coach.status = f'creating_exercise {param} {exercise.exercises_id}'
							try:
								coach.set_coach()
							finally:
								d = {'video': 'Отправьте вспомогательное видео (не в виде документа, то есть сжатое).',
									 'image': "Отправьте вспомогательное изображение (не в виде документа, то есть сжатое).",
									 'audio': "Отправьте голосовое сообщение."}
								msg = bot.send_message(coach.chat_id, d[param])


					elif query.split()[1] == 'sets':
						amount = query.split()[2]
						exercise = Exercise(query.split()[3], coach=False)
						temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['sets'] = amount
						msg = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['msg']()

					elif query.split()[1] == 'repeats':
						amount = query.split()[2]
						exercise = Exercise(query.split()[3], coach=False)
						temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['repeats'] = amount if amount != 'None' else None
						if amount == 'None':
							temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id][
								'check_exercise'] = True
						msg = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['msg']()

			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)


		if query.startswith('my_schedule'):
			buttons = []
			def hours_lst(hours:list, today:bool=False) -> set[tuple[str, int]]:
				if not today:
					return set([(hour.time, ', '.join([j[0].fullname + (f' (комментарий: "{j[1]}")' if j[1] else '') +  f' — {training_types()[hour.session_type]}' for j in [(i['user'], i['comment']) for i in hour.clients]])) for hour in hours])
				else:
					return set([(hour.time, ', '.join([j[0].fullname + (
						f' (комментарий: "{j[1]}")' if j[1] else '') + f' — {training_types()[hour.session_type]}' for j in [(i['user'], i['comment']) for i in hour.clients]])) for hour in hours if hour.time > datetime.now().hour])

			if query == 'my_schedule':
				temp_dct['coaches'].pop(coach.id, None)
				today, tomorrow = ScheduleDay(coach, date.today()).get_schedule(), ScheduleDay(coach, date.today() + timedelta(days=1)).get_schedule()
				out_1, out_2 = None, None
				if today:
					lst = sorted(hours_lst(today, today=True), key=lambda x: x[0])
					if lst:
						out_1 = f'📜 *Расписание на сегодня, {fullname_of_date(date.today())}*\n\n' + '\n'.join([f'  ⏳ *{i[0]}:00* 👤 _{i[1]}_' for i in lst])
				if tomorrow:
					lst = sorted(hours_lst(tomorrow), key=lambda x: x[0])
					if lst:
						out_2 = f'📜 *Расписание на завтра, {fullname_of_date(date.today() + timedelta(days=1))}*\n\n' + '\n'.join([f'  ⏳ *{i[0]}:00* 👤 _{i[1]}_' for i in lst])
				text = (out_1 or '') + ('\n\n' + out_2 if out_2 else '')

				buttons = [
					InlineKeyboardButton(text=fullname_of_date(i), callback_data=f'my_schedule {i.isoformat()}') for i in [date.today() + timedelta(days=j) for j in range(2, 11)]
					if ScheduleDay(coach, i).schedule
				] + [InlineKeyboardButton(text='Редактировать расписание', callback_data='my_schedule_edit')]
				if buttons:
					if not text:
						text = 'Расписание на сегодня и завтра пусто.\n\nПо умолчанию вы видите расписание на сегодняшний и завтрашний дни.\n' \
								'Чтобы просмотреть расписание на более поздний день, нажмите кнопку с соответствующим числом.'
					else:
						text += '\n\nПо умолчанию вы видите расписание на сегодняшний и завтрашний дни.\n' \
								'Чтобы просмотреть расписание на более поздний день, нажмите кнопку с соответствующим числом.'

			elif query.startswith('my_schedule '):
				day = ScheduleDay(coach, date.fromisoformat(query.split()[1])).get_schedule()
				lst = hours_lst(day)
				text = f'📜 *Расписание на {fullname_of_date(query.split()[1])}*\n\n' + '\n'.join([f'  ⏳ *{i[0]}:00* 👤 _{i[1]}_' for i in lst])
				buttons = [
					InlineKeyboardButton(text='👈 Назад', callback_data='my_schedule')
				]
			elif query.startswith('my_schedule_edit'):
				if query == 'my_schedule_edit':
					buttons = [InlineKeyboardButton(text=f'{days_of_week[int(i)].title()}', callback_data=f'coach_schedule_day {i}') for i in range(1, 8)] + \
						   [InlineKeyboardButton(text='👈 Отменить и выйти', callback_data='my_schedule')]
					try:
						schedule = temp_dct['coaches'][coach.id]['schedule_editing']
					except KeyError:
						schedule = coach.extra()['working_schedule']
					free_count = 0
					for i in schedule:
						for j in schedule[i]:
							if list(j.values())[0] == 'free':
								free_count += 1
					if free_count >= 2:
						buttons += [InlineKeyboardButton(text='☑️ Сохранить и выйти', callback_data='my_schedule_edit_end')]
					text = 'Выберите день недели, чтобы определить рабочие часы.\n\n' + \
					   '*Они будут* _доступны клиентам_ для записи. Оставьте *пустыми* день/время, чтобы они были _недоступными_ для записи.\n' + \
					   '❗️ *Необходимо* выбрать как минимум два часа в неделю, которые смогут использовать для записи новые клиенты, желающие получить ознакомительное занятие.\n\n' + \
					   'Чтобы закончить изменение графика, нажмите *"Сохранить и выйти"*.\n\n' + \
					   '*Текущий выбор по дням*:\n' + '\n'.join([f'*{days_of_week[int(i)]}*' + ': ' +
																 (', '.join(sorted([f'_{list(i.keys())[0]}_' + ' (_' + training_types()[list(i.values())[0]] +
																					'_)' for i in schedule[i]], key=lambda x: int(x.split(':')[0][1:]))) if schedule[i] else "пусто") for i in schedule])
				elif query == 'my_schedule_edit_end':
					try:
						schedule = temp_dct['coaches'][coach.id]['schedule_editing']
					except KeyError:
						schedule = None
					if schedule:
						extra = coach.extra()
						previous_schedule = extra['working_schedule']
						new_schedule = schedule
						notification_dct = {}
						for d in previous_schedule:
							for t in previous_schedule[d]:
								hour = next(iter(t.keys()))
								if not hour in [next(iter(i.keys())) for i in new_schedule[d]]:
									notification_dct[int(d)] = t
						needed_types = False
						if not coach.tasks is None:
							for task in coach.tasks:
								if task.type_number == 3:
									needed_types = True
						if needed_types is True:
							previous_training_types_amount = coach.working_schedule_training_types()
						extra['working_schedule'] = schedule
						coach.extra(set=True, updated_extra=extra)
						if needed_types is True:
							new_training_types_amount = coach.working_schedule_training_types()
							new_types = list({i: j - previous_training_types_amount[i] for i, j in new_training_types_amount.items() if j - previous_training_types_amount[i] >= 1})
							if not coach.tasks is None:
								for task in coach.tasks:
									if task.type_number == 3:
										if all([tr_type in new_types for tr_type in task.additional_info]):
											task.delete(coach)
						text = 'Расписание успешно изменено!'
						temp_dct['coaches'].pop(coach.id)
						# если тренер убирает из расписания рабочие часы, по которым уже есть запись - запись для всех клиентов на это время отменяется
						if notification_dct:
							weekdays = list(notification_dct)
							with database() as connection:
								with connection.cursor() as db:
									db.execute(f"SELECT * FROM schedules WHERE coachs_id = {coach.id} AND date >= CURDATE()")
									current_schedule = db.fetchall()
									if current_schedule:
										current_schedule = filter(lambda x: x['date'].isoweekday() in weekdays, current_schedule)
										for i in current_schedule:
											day = i['date'].isoweekday()
											hour = str(i['time'])[:-3]
											session_type = i['session_type']
											current_user = User(user_id=i['users_id'])
											if hour in notification_dct[day]:
												db.execute(f"DELETE FROM schedules WHERE users_id = {current_user.id} AND "
														   f"date = '{i['date'].isoformat()}' AND time = '{str(i['time'])}'")
												current_user.subscription_plan['sessions_count'][session_type] += 1
												current_user.set_user(subscription_plan=True)
												bot.send_message(current_user.chat_id, f'К сожалению, ваша запись на *{fullname_of_date(i["date"])}, {hour}* '
																					   f'отменена - тренер изменил свое рабочее расписание.\n\n'
																					   f'Но баланс тренировок типа _{training_types()[session_type]}_ '
																					   f'восстановлен! И вы можете заново записаться на занятие.')
								connection.commit()

					else:
						text = 'Изменение расписания отменено.'

			msg = bot.send_message(coach.chat_id, (text or 'Расписание пусто.') + ('\n\nНажмите *Редактировать расписание*, чтобы изменить текущее рабочее расписание (дни, часы, типы тренировок).' if not text in ['Расписание успешно изменено!', 'Изменение расписания отменено.'] else ''), reply_markup=InlineKeyboardMarkup(row_width=2).add(*buttons) if buttons else None)

			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)


		if query.startswith('set_my_bot'):
			menu = InlineKeyboardMarkup(row_width=1)
			text = ''
			if user.is_coach:
				dct = {'user_tariff_ended_reminding': 'Окончание периода', 'coach_tasks_reminding': 'Мои задачи',
					   'user_online_training_reports_reminding': 'День для отчетов',
					   'today_coach_schedule': 'Мое расписание'}
			else:
				dct = {'reminding_today_session': 'Сегодня тренировка',
					   "reminding_before_sessions": "Тренировка через...",
					   "reminding_left_sessions": "Запишитесь!",
					   "reminding_current_tasks": "Текущие задачи"}
			try:
				bot_settings = \
				temp_dct['coaches' if user.is_coach else 'users'][coach.id if user.is_coach else user.id][
					'bot_settings']
			except KeyError:
				bot_settings = coach.extra()['bot_checking_funcs'] if user.is_coach else user.notifications()
				try:
					temp_dct['coaches' if user.is_coach else 'users'][coach.id if user.is_coach else user.id][
						'bot_settings'] = bot_settings
				except KeyError:
					temp_dct['coaches' if user.is_coach else 'users'][coach.id if user.is_coach else user.id] = {
						'bot_settings': bot_settings}
			def bot_settings_buttons():
				return [*[InlineKeyboardButton(
				text=f'{dct[i]} - {("да" if bot_settings[i] else "нет") if i != "reminding_before_sessions" else ("за " + str(bot_settings[i]) + (" часа" if bot_settings[i] in [2, 3] else " час") if bot_settings[i] != 0 else "нет")}',
				callback_data=f'set_my_bot {i}') for i in sorted(dct, key=lambda x: dct[x])],
					   InlineKeyboardButton(text='❓ Подробно', callback_data='set_my_bot_info'),
					   InlineKeyboardButton(text='✔️ Сохранить и выйти', callback_data='set_my_bot_end')]
			buttons = bot_settings_buttons()
			if len(query.split()) in [2,3]:
				param = query.split()[1]
				if len(query.split()) == 2:
					if param != 'reminding_before_sessions':
						bot_settings[param] = True if not bot_settings[param] else False
						text += f'Параметр "_{dct[param]}_" успешно изменен!\n\n'
						buttons = bot_settings_buttons()
					else:
						text = 'Выберите, за сколько часов до тренировки хотите получать напоминание от бота.\n\n' \
							   'Нажмите *"Не напоминать"*, чтобы отключить напоминание.'
						buttons = [*[InlineKeyboardButton(text=f'За {i + 1} {"час" if i+1 == 1 else "часа"} до тренировки',
														  callback_data = f'set_my_bot reminding_before_sessions {i + 1}') for i in range(3)],
								   InlineKeyboardButton(text='Не напоминать', callback_data='set_my_bot reminding_before_sessions 0')]
				elif len(query.split()) == 3:
					value = int(query.split()[2])
					bot_settings[param] = value
					text += f'Параметр "_{dct[param]}_" успешно изменен!\n\n'
					buttons = bot_settings_buttons()
			if query == 'set_my_bot_end':
				if user.is_coach:
					coach_extra = coach.extra()
					coach_extra['bot_checking_funcs'] = bot_settings
					coach.extra(set=True, updated_extra=coach_extra)
				else:
					user.notifications(set=True, updated_notifications=bot_settings)
				temp_dct['coaches' if user.is_coach else 'users'].pop(coach.id if user.is_coach else user.id, None)
				text = 'Настройки успешно сохранены.'
				buttons = []
				del_msgs('set_my_bot_info', user)

			elif query == 'set_my_bot_info':
				text = None
				if user.is_coach:
					text_2 = '- *День для отчетов*.\nДля клиентов, у которых есть текущие задачи по отправке отчетов по индивидуальным заданиям, бот присылает напоминание о сроке отчетности в последний день срока.\n\n'\
						'- *Мое расписание*.\nКаждый день в 7:00 бот отправляет вам расписание на текущий день. Если расписание пусто, уведомляет об этом.\n\n'\
						'- *Мои задачи*.\nЕсли у вас есть текущие незавершенные задачи, бот напоминает о них. Если срок выполнения задачи истек - уведомляет об этом.\n\n'\
						'- *Окончание периода*.\nПри завершении срока действия тарифа количество тренировок клиента всегда обнуляется. Бот дополнительно уведомляет об этом и предлагает продлить тариф, если функция включена.'
				else:
					text_2 = '- *Сегодня тренировка*.\nБот напоминает вам утром о том, что сегодня состоится тренировка с тренером, а также сообщает время тренировки.\n\n' \
							 '- *Тренировка через...*\nБот напоминает вам о тренировке за то количество часов, которое вы укажете при настройке этой функции (нажмите на кнопку для настройки).\n\n' \
							 '- *Запишитесь!*\nБот напоминает вам утром (в будние дни) о том, что необходимо записаться на занятия, если текущей записи нет, а на вашем балансе есть тренировки с тренером.'
				msg_2 = bot.send_message(user.chat_id, text_2)
				temp_msgs('set_my_bot_info', user, msg_2)
			else:
				if len(query.split()) == 1 or query.split()[1] != 'reminding_before_sessions':
					text += '*Вы можете индивидуально* настроить бота под свои нужды.\n' + \
												f'*По умолчанию* все функции взаимодействия бота с {"клиентами" if user.is_coach else "вами"} _включены_. Нажмите на *название параметра* (кнопку), чтобы _включить/выключить_ его.'
			if buttons:
				menu.add(*buttons)
			msg = (bot.send_message(user.chat_id, text, reply_markup=menu) if menu.keyboard else bot.send_message(user.chat_id, text)) if text else None
			if msg:
				del_msgs('set_my_bot', user)
				del_msgs(('my_trainings' if not user.is_coach else 'main_admin'), user)
				temp_msgs('set_my_bot', user, msg)

		if query.startswith('coach_skill '):
			discipline = ' '.join(query.split()[1:])
			disciplines = coaches_disciplines()
			coach = Coach(callback.message.chat.id)
			if not os.path.exists(f'coach_register {coach.id}.txt'):
				open(f'coach_register {coach.id}.txt', 'w', encoding='utf-8').write(discipline + ',')
			else:
				open(f'coach_register {coach.id}.txt', 'a', encoding='utf-8').write(discipline + ',')
			amount = len(open(f'coach_register {coach.id}.txt', encoding='utf-8').read().rstrip(',').split(','))
			for i in [j.rstrip() for j in open(f'coach_register {coach.id}.txt',encoding='utf-8').read().split(',') if j in disciplines]:
				disciplines.remove(i)
			if amount < 5:
				coach_skills = [InlineKeyboardButton(text=f'{i.title() if i == i.lower() else i}', callback_data=f'coach_skill {i}') for i in disciplines]
				msg = bot.send_message(callback.message.chat.id, f'Дисциплина успешно сохранена! Выберите еще *{5 - amount}*.', reply_markup=InlineKeyboardMarkup(row_width=2).add(*coach_skills))
				del_msgs('coach_register', user)
				temp_msgs('coach_register', user, msg)
			else:
				tags = open(f'coach_register {coach.id}.txt', encoding='utf-8').read().rstrip(',')
				with database() as connection:
					with connection.cursor() as db:
						db.execute(f"UPDATE coachs SET tags = '{tags}' WHERE id = {coach.id}")
						connection.commit()
				remove(f'coach_register {coach.id}.txt')
				msg = bot.send_message(callback.message.chat.id, 'Напишите, пожалуйста, какое у вас образование?\n\n'
																 'Пример: "МГАФК - Физическая культура".')
				bot.register_next_step_handler(msg, register_coach)
				del_msgs('coach_register', user)
				temp_msgs('coach_register', user, msg)


			temp_msgs('coach_register', user, msg)


		if query.startswith('coach_schedule_day '):
			import json
			day = int(query.split()[1])
			action = 'register'
			try:
				schedule = json.load(open(f'coach_register {coach.id}.json', encoding='utf-8'))
			except FileNotFoundError:
				# так, если не регистрация, а редактирование расписания для уже существующего тренера
				try:
					schedule = temp_dct['coaches'][coach.id]['schedule_editing']
				except KeyError:
					schedule = coach.extra()['working_schedule']
					action = 'edit'
					try:
						temp_dct['coaches'][coach.id]['schedule_editing'] = schedule
					except KeyError:
						temp_dct['coaches'][coach.id] = {'schedule_editing': schedule}
			if action == 'register':
				available_hours = [InlineKeyboardButton(text=f'{i}:00', callback_data=f'coach_schedule {day} {i}:00') for i in range(7,24) if not str(i) + ':00' in [list(i.keys())[0] for i in schedule[str(day)]]]
			else:
				available_hours = [InlineKeyboardButton(text=f'{i}:00', callback_data=f'coach_schedule {day} {i}:00')
								   for i in range(7, 24)]
			available_hours_menu = InlineKeyboardMarkup(row_width=4).add(*available_hours, InlineKeyboardButton(text='👈 Назад', callback_data='coach_schedule' if action == 'register' else 'my_schedule_edit'))

			msg = bot.send_message(callback.message.chat.id, f'Выбран день недели: *{days_of_week[day]}*.\n'
													   f'Выберите час, который нужно сохранить, как рабочий, или нажмите "Назад".' + (f'\n\n*Текущее расписание* по данному дню:\n' +
													   ', '.join(sorted([f'_{list(i.keys())[0]}_' + ' (_' + training_types()[list(i.values())[0]] + '_)' for i in schedule[str(day)]], key=lambda x: int(x.split(':')[0][1:]))) if
																																	  action == 'edit' else ''), reply_markup=available_hours_menu)
			if action == 'register':
				del_msgs('coach_register', user)
				temp_msgs('coach_register', user, msg)
			else:
				del_msgs('main_admin', coach)
				temp_msgs('main_admin', coach, msg)

		if query.startswith('coach_schedule '):
			import json
			try:
				schedule = json.load(open(f'coach_register {coach.id}.json', encoding='utf-8'))
				action = 'register'
			except FileNotFoundError:
				# так, если не регистрация, а редактирование расписания для уже существующего тренера
				schedule = temp_dct['coaches'][coach.id]['schedule_editing']
				action = 'edit'
			day = int(query.split()[1])
			hour = query.split()[2]
			persons_count = InlineKeyboardMarkup(row_width=3).add(*[InlineKeyboardButton(text=training_types()[i], callback_data=f'c_s {day} {hour} {i}') for i in training_types()])

			text = f'Выберите тип услуги, проводимой в *{days_of_week[day]}*, {hour}.\n\n' +\
													   f'Это определит максимально допустимое количество клиентов для записи на данное время.\n\n'+\
													   f'- *Персональная тренировка* (онлайн/очная) — только один клиент в час.\n'+\
													   f'- *Сплит-тренировка* — до 3 клиентов в час.\n'+\
													   f'- *Групповая тренировка* — неограниченное количество клиентов в час.\n'+\
															 f'- *Персональная онлайн-тренировка* — только один клиент в час в режиме онлайн (видеосвязь).\n'+\
															 f'- *Бесплатная пробная тренировка* — время, которое смогут использовать для записи новые клиенты, желающие впервые ознакомиться с вашими услугами.\n'

			if hour in [next(iter(i.keys())) for i in schedule[str(day)]]:
				persons_count.add(InlineKeyboardButton(text='❌ Очистить', callback_data=f'c_s {day} {hour} None'))
				text += f'- ❌ *Очистить* - очистить рабочий час (убрать из расписания).'
			msg = bot.send_message(callback.message.chat.id, text, reply_markup=persons_count)
			if action == 'register':
				del_msgs('coach_register', user)
				temp_msgs('coach_register', user, msg)
			else:
				del_msgs('main_admin', coach)
				temp_msgs('main_admin', coach, msg)


		if query.startswith('c_s '):
			import json
			try:
				schedule = json.load(open(f'coach_register {coach.id}.json', encoding='utf-8'))
				action = 'register'
			except FileNotFoundError:
				# так, если не регистрация, а редактирование расписания для уже существующего тренера
				schedule = temp_dct['coaches'][coach.id]['schedule_editing']
				action = 'edit'
			day = int(query.split()[1])
			hour = query.split()[2]
			training_session_type = ' '.join(query.split()[3:])
			if action == 'register':
				if training_session_type != 'None':
					schedule[str(day)].append({hour: training_session_type})
				else:
					for i in schedule[str(day)]:
						if next(iter(i.keys())) == hour:
							schedule[str(day)].remove(i)
			else:
				flag = False
				curday = schedule[str(day)]
				for i in curday:
					if next(iter(i.keys())) == hour:
						curday.remove(i)
						if training_session_type != 'None':
							curday.append({hour: training_session_type})
						flag = True
						break
				if flag is False:
					curday.append({hour: training_session_type})

			if action == 'register':
				json.dump(schedule, open(f'coach_register {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
			available_hours = [InlineKeyboardButton(text=f'{i}:00', callback_data=f'coach_schedule {day} {i}:00')
							   for i in range(7, 24)]
			available_hours_menu = InlineKeyboardMarkup(row_width=4).add(*available_hours,
																		 InlineKeyboardButton(text='👈 Назад',
																							  callback_data='coach_schedule' if action == 'register' else 'my_schedule_edit'))

			msg = bot.send_message(callback.message.chat.id, f'Выбран день недели: *{days_of_week[day]}*.\n'
													   f'Выберите час, который нужно сохранить, как рабочий, или нажмите "Назад".\n\n'
													   f'*Текущий выбор* по данному дню:\n' +
													   ', '.join(sorted([f'_{list(i.keys())[0]}_' + ' (_' + training_types()[list(i.values())[0]] + '_)' for i in schedule[str(day)]], key=lambda x: int(x.split(':')[0][1:]))),
							 parse_mode='Markdown', reply_markup=available_hours_menu)
			if action == 'register':
				del_msgs('coach_register', user)
				temp_msgs('coach_register', user, msg)
			else:
				del_msgs('main_admin', coach)
				temp_msgs('main_admin', coach, msg)

		if query == 'coach_schedule':
			import json
			schedule = json.load(open(f'coach_register {coach.id}.json', encoding='utf-8'))

			days = [InlineKeyboardButton(text=f'{days_of_week[int(i)].title()}', callback_data=f'coach_schedule_day {i}') for i in
					range(1, 8)]
			coach_schedule_days_menu = InlineKeyboardMarkup(row_width=1).add(*days)

			free_count = 0
			for i in schedule:
				for j in schedule[i]:
					if list(j.values())[0] == 'free':
						free_count += 1
			if free_count >= 2:
				coach_schedule_days_menu.add(InlineKeyboardButton(text='Закончить', callback_data='end_coach_register'))

			msg = bot.send_message(callback.message.chat.id,
							 'Выберите день недели, чтобы выбрать рабочие часы.\n\n'
							 '*Они будут* _доступны клиентам_ для записи. Оставьте *без изменений* день/время, чтобы они были _недоступными_ для записи.\n'
							 '❗️ *Необходимо* выбрать как минимум два часа в неделю, которые смогут использовать для записи новые клиенты, желающие получить ознакомительное занятие.\n\n'
							 'Чтобы закончить составление графика и процесс регистрации, нажмите *"Закончить"*.\n\n' +
			'*Текущий выбор по дням*:\n' +
			'\n'.join([f'*{days_of_week[int(i)]}*' + ': ' + (', '.join(sorted([f'_{list(i.keys())[0]}_' + ' (_' + training_types()[list(i.values())[0]] + '_)' for i in schedule[i]], key=lambda x: int(x.split(':')[0][1:]))) if schedule[i] else "пусто") for i in schedule]),
							 reply_markup=coach_schedule_days_menu)
			del_msgs('coach_register', user)
			temp_msgs('coach_register', user, msg)


		if query == 'end_coach_register':
			import json
			schedule = json.dumps(json.load(open(f'coach_register {coach.id}.json', encoding='utf-8')), ensure_ascii=False)
			remove(f'coach_register {coach.id}.json')

			bot_checking_funcs = json.dumps({
										'user_tariff_ended_reminding': True,
										'coach_tasks_reminding': True,
										'user_online_training_reports_reminding': True,
										'today_coach_schedule': True
										})

			with database() as connection:
				with connection.cursor() as db:
					db.execute(f"INSERT INTO coachs_extra (coachs_id, working_schedule, bot_checking_funcs) VALUES ({coach.id},'{schedule}', '{bot_checking_funcs}')")
					connection.commit()

			msg = bot.send_message(callback.message.chat.id, 'Остался еще один небольшой шаг. Для начала работы нужно также заполнить стартовую анкету тренера.\n\n'
													"Перейдите по ссылке и сделайте это на нашем сайте: <a href='https://google.ru'>тестовая ссылка</a>.\n\n"
													"После этого меню будет доступно для вас в полной мере.\n\n"
													"Когда заполните форму, отправьте боту команду: /start.", parse_mode='HTML', reply_markup=ReplyKeyboardRemove())

			del_msgs('coach_register', coach)
			temp_msgs('coach_register', coach, msg)

			bot.send_message(developer_id, f'Зарегистрирован новый тренер *{coach.fullname}*!\n\n'
									   f'*Описание*: \n\n'
									   f'{coach.description}.')

			bot.send_photo(developer_id, coach.photo, caption='Фото тренера')


		if query == 'admin_help':
			msg = bot.send_message(callback.message.chat.id, 'Скоро здесь будет помощь.')
			temp_msgs('main_admin', coach, msg)


		if query.startswith('users_reports'):
			splitted = query.split()
			item = splitted[0]
			coach = coach if user.is_coach else user.coach()
			reports = coach.clients_training_reports(objects=True)
			menu = InlineKeyboardMarkup(row_width=1)
			def reports_menu():
				buttons = [
					InlineKeyboardButton(text='Все отчеты', callback_data='users_reports_all'),
					InlineKeyboardButton(text='Непроверенные', callback_data='users_reports_new')
				]
				if not reports is None:
					menu.add(buttons[0])
					text = '*Все отчеты* - просмотреть все доступные отчеты (проверенные) от клиентов (историю) _по индивидуальным и самостоятельным заданиям_.'
					# refreshing reports
					if [report for report in coach.clients_training_reports(objects=True) if not report.checked and report.training_plan.type == 'individual' and report.type == 'video']:
						menu.add(buttons[1])
						text += '\n\n*Непроверенные* - просмотреть новые, непроверенные отчеты от клиентов, оценить качество выполнения упражнений' \
								' _по индивидуальным заданиям_.'
				else:
					text = 'Отчетов по тренировкам еще не было.'
				return menu, text
			if item == 'users_reports':
				menu, text = reports_menu()
			elif item == 'users_reports_all':
				users_reports = dict()
				for report in sorted(reports, key=lambda x: x.datetime):
					user = report.user_id
					try:
						users_reports[user].append(report)
					except KeyError:
						users_reports[user] = []
						users_reports[user].append(report)
				users_reports = sorted([[User(user_id=i), j] for i, j in users_reports.items()], key=lambda x: x[0].fullname)
				text = ''
				for user in users_reports:
					reports = user[1]
					user = user[0]
					text += f'👤 *{user.fullname}*\n' \
							f'*Количество видео-отчетов*: {len([i for i in reports if i.type == "video"])}\n' \
							f'*Из них зачтено:* {len([i for i in reports if i.credited])}\n' \
							f'*Текстовых отчетов:* {len([i for i in reports if i.type == "text"])}\n'  \
							f'*Всего отчетов за последний месяц*: {len([i for i in reports if datetime.now() - i.datetime < timedelta(days=30)])}\n' \
							f'*Последний отчет*: {reports[-1].datetime}\n' \
							f'*Всего отчетов по индивидуальным тренировкам*: {len([i for i in reports if i.training_plan.type == "individual"])}\n' \
							f'*Всего отчетов по самостоятельным тренировкам*: {len([i for i in reports if i.training_plan.type == "self"])}\n\n'
				buttons = [InlineKeyboardButton(text='👈 Назад', callback_data=f'users_reports')]
				menu.add(*buttons)
			elif item == 'users_reports_new_cancel':
				temp_dct['coaches'].pop(coach.id, None)
				text = 'Обработка отчета отменена.'
			elif item == 'users_reports_new':
				if len(splitted) == 1:
					reports = list(filter(lambda rep: not rep.checked and rep.type == 'video' and rep.training_plan.type == 'individual', reports))
					users_list = sorted([User(user_id=i.user_id) for i in reports], key=lambda x: x.fullname)
					users_list = set([(i.fullname, i.id) for i in users_list])
					buttons = [InlineKeyboardButton(text=i[0], callback_data=f'users_reports_new {i[1]}') for i in users_list]
					menu.add(*buttons, InlineKeyboardButton(text='👈 Назад', callback_data='users_reports'))
					text = 'Выберите клиента, видео-отчеты которого нужно просмотреть и оценить.'
				elif len(splitted) >= 2:
					def general_msg(user):
						reports = [i for i in sorted(user.training_reports(objects=True, reports_type='individual'), key=lambda rep: rep.datetime)
								   if not i.checked and i.type == 'video']
						text = ''
						for report in reports:
							text += f'❗️ *Отчет №{reports.index(report) + 1}*\n' + report.description() + '\n\n'
						text += 'Нажмите на кнопку с номером отчета по упражнению, чтобы проверить и оценить его.'
						menu.row_width = 5
						buttons = [InlineKeyboardButton(text=f'📍 {reports.index(i) + 1}',
														callback_data=f'users_reports_new {user.id} {reports.index(i)}')
								   for i in reports]
						menu.add(*buttons, InlineKeyboardButton(text='👈 Назад', callback_data=f'users_reports_new'))
						return menu, text
					if len(splitted) == 2:
						user = User(user_id=splitted[1])
						menu, text = general_msg(user)
					elif len(splitted) == 3:
						user = User(user_id=splitted[1])
						reports = [i for i in sorted(user.training_reports(objects=True, reports_type='individual'), key=lambda rep: rep.datetime) if not i.checked and i.type == 'video']
						report = reports[int(splitted[2])]
						msg = bot.send_video(coach.chat_id, report.content)
						temp_msgs('report_check', coach, msg)
						temp_dct['coaches'][coach.id] = {'reports': {f'comment {user.id} {report.exercise.coachs_exercises_id}': None}}
						text = f'{report.exercise.description()}\n\nНапишите комментарий по упражнению. Постарайтесь объективно и справедливо оценить достоинства и недостатки выполнения упражнения клиентом.\n\n' \
							   'Если все сделано достойно и без нареканий - так и напишите.\n\n' \
							   'На основе вашего мнения клиент сделает для себя полезные выводы на будущее, а вы сможете решить, засчитать это упражнение для рекордов или нет.'
						temp_dct['coaches'][coach.id]['reports']['text'] = report.description() + '\n\nНажмите *"Засчитано"*, если упражнение выполнено честно и достаточно качественно.\n' \
													  'Нажмите *"Не засчитано"* в противном случае.\n\n'
						temp_dct['coaches'][coach.id]['reports']['buttons'] = [InlineKeyboardButton(text='Засчитано', callback_data=f'users_reports_new True {user.id} {splitted[2]}'),
								   InlineKeyboardButton(text='Не засчитано', callback_data=f'users_reports_new False {user.id} {splitted[2]}')]
					elif len(splitted) in [4,5]:
						if not splitted[1] in ['video', 'text_report_comment']:
							result = True if splitted[1] == 'True' else False
							user = User(user_id=splitted[2])
							def user_reports():
								return [i for i in sorted(user.training_reports(objects=True, reports_type='individual'), key=lambda rep: rep.datetime) if not i.checked and i.type == 'video']
							report = user_reports()[int(splitted[3])]
							try:
								report.coach_comment = temp_dct['coaches'][coach.id]['reports'][f'comment {user.id} {report.exercise.coachs_exercises_id}']
							except KeyError:
								report.coach_comment = None
							report.update(result=result)
							temp_dct['coaches'].pop(coach.id, None)
							if user_reports():
								menu, text = general_msg(user)
							else:
								if not coach.tasks is None:
									for task in coach.tasks:
										if task.type_number == 2 and task.additional_info[0] == 'check_report' and task.additional_info[1] == user.id:
											task.delete(coach)
								menu, text = reports_menu()
								text += f'\n\nВсе отчеты клиента *{user.fullname}* были проверены.'
							dt = report.datetime.isoformat().replace('T', ', ')[:-3]
							button = InlineKeyboardButton(text='Видео-отчет', callback_data=f'users_reports_new video {user.id} {report.exercise.coachs_exercises_id}')
							menu_2 = InlineKeyboardMarkup(row_width=1)
							if result:
								text += f'\n\n‼️ Отчет по упражнению _{report.exercise.name}_ от клиента *{user.fullname}* успешно зачтен! ‼️'
								bot.send_message(user.chat_id, f'😃 Ваш видео-отчет по упражнению _{report.exercise.name}_ от {dt} был зачтен тренером!\n\n'
															   f'❗️ Комментарий по упражнению от тренера:\n'
															   f'- _{report.coach_comment}_\n\n'
															   f'При успешном выполнении упражнений ваши личные рекорды и меню *"Результаты"* обновляются автоматически.',
												 reply_markup=menu_2.add(button))
								if len([i for i in user.training_reports() if
										i['report_type'] == 'video' and i['credited']]) == 1 and user.records():
									bot.send_message(user.chat_id,
													 '🤓 Проверен и подтвержден ваш первый видео-отчет по тренировке - теперь доступно меню 📍 *"Мои рекорды"* в *"Моих тренировках"*!\n\n'
													 '💪 Все ваши новые лучшие результаты будут автоматически фиксироваться в этом меню. Проверьте его.')
							else:
								text += f'\n\n‼️ Отчет по упражнению _{report.exercise.name}_ от клиента *{user.fullname}* не был зачтен. ‼️'
								bot.send_message(user.chat_id, f'😔 К сожалению, ваш видео-отчет по упражнению _{report.exercise.name}_ от {dt} не был зачтен тренером\n\n'
															   f'❗️ Комментарий по упражнению от тренера:\n'
															   f'- _{report.coach_comment}_\n\n',
												 reply_markup=menu_2.add(button))
							try:
								text_report = next(filter(lambda x: x.training_plan.id == report.training_plan.id and x.type == 'text' and not x.checked, user.training_reports(reports_type='individual', objects=True))).content
							except StopIteration:
								text_report = None
								msg_2 = None
							if text_report:
								text_2 = f'Проверьте также текстовый отчет клиента по тренировке в целом:\n- _{text_report}_\n\n' \
										f'Нажмите *"Отправить комментарий"*, если нужно сообщить клиенту дополнительную информацию, помочь с вопросами и так далее.\n' \
										f'Нажмите *"Комментарий не требуется"*, чтобы просто пометить отчет проверенным, но не отправлять доп. информацию.'
								buttons_2 = [
									InlineKeyboardButton(text='Отправить комментарий', callback_data=f'users_reports_new text_report_comment send {user.id} {report.training_plan.id}'),
									InlineKeyboardButton(text='Комментарий не требуется', callback_data=f'users_reports_new text_report_comment not_send {user.id} {report.training_plan.id}')
								]
								msg_2 = bot.send_message(coach.chat_id, text_2, reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons_2))
								text = ''
								del_msgs('main_admin', coach)
							del_msgs('report_check', coach)
							if msg_2:
								temp_msgs('report_check', coach, msg_2)
						else:
							text = ''
							if splitted[1] == 'video':
								ex = int(splitted[3])
								user = User(user_id=splitted[2])
								report = next(filter(lambda x: x.type == 'video' and x.exercise.coachs_exercises_id == ex, reversed(user.training_reports(objects=True, reports_type='individual'))))
								bot.send_video(user.chat_id, report.content)
							elif splitted[1] == 'text_report_comment':
								training_plan_id = int(splitted[4])
								user = User(user_id=splitted[3])
								report = next(filter(lambda x: x.training_plan.id == training_plan_id and x.type == 'text' and not x.checked, user.training_reports(reports_type='individual', objects=True)))
								if splitted[2] == 'send':
									temp_dct['coaches'][coach.id] = {'send_training_individual_comment': {'plan_id': training_plan_id,
																										  'user_id': user.id}}
									if [i for i in sorted(user.training_reports(objects=True, reports_type='individual'), key=lambda rep: rep.datetime)
								   if not i.checked and i.type == 'video']:
										menu_3, text_3 = general_msg(user)
										d = temp_dct['coaches'][coach.id]['send_training_individual_comment']
										d['menu'] = menu_3
										d['text'] = text_3
									text_report = report.content
									msg_2 = bot.send_message(coach.chat_id, 'Отчет клиента:\n- _' + text_report + '_\n\n*Напишите необходимый комментарий*.', reply_markup=ReplyKeyboardRemove())
									bot.register_next_step_handler(msg_2, individual_training_text_report_send_comment)
								elif splitted[2] == 'not_send':
									report.update()
									def user_reports():
										return [i for i in
												sorted(user.training_reports(objects=True, reports_type='individual'),
													   key=lambda rep: rep.datetime) if
												not i.checked and i.type == 'video']
									if user_reports():
										menu, text_2 = general_msg(user)
									else:
										if not coach.tasks is None:
											for task in coach.tasks:
												if task.type_number == 2 and task.additional_info[
													0] == 'check_report' and task.additional_info[1] == user.id:
													task.delete(coach)
										menu, text_2 = reports_menu()
										text_2 += f'\n\nВсе отчеты клиента *{user.fullname}* были проверены.'
									msg_2 = bot.send_message(coach.chat_id, f"Отправка комментария по текстовому тренировочному отчету клиента *{user.fullname}* от *{report.datetime.date()}* отменена.", reply_markup=admin_keyboard())
								del_msgs('report_check', coach)
								temp_msgs('report_check', coach, msg_2)
								msg_2 = bot.send_message(coach.chat_id, text_2, reply_markup=menu)
								temp_msgs('report_check', coach, msg_2)

			if text:
				del_msgs('main_admin', coach)
				msg = telebot_splitted_text_send_message(text, coach, 'main_admin', (menu if menu.keyboard else None) if not text.startswith('Все отчеты клиента') else admin_keyboard())
				if 'Напишите комментарий по упражнению' in msg.text:
					bot.register_next_step_handler(msg, send_exercise_comment)


		if query == 'admin_all_users':
			clients = coach.clients()
			if clients:
				text = '\n\n'.join([str(usr) for usr in clients])
			else:
				text = "Клиентов пока нет."
			del_msgs('main_admin', coach)
			telebot_splitted_text_send_message(text, coach, 'main_admin')



		if query == 'admin_choose_user':
			clients = coach.clients_for_menu()
			if clients:
				choose_user_menu = InlineKeyboardMarkup(row_width=3).add(*[InlineKeyboardButton(text=i[0], callback_data=f'client {i[1]}') for i in sorted(clients, key=lambda x: x[0])])
				msg = bot.send_message(callback.message.chat.id, 'Выберите клиента для взаимодействия с ним.', reply_markup=choose_user_menu)
			else:
				msg = bot.send_message(callback.message.chat.id, 'Клиентов пока нет.')
			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)

		if query.startswith('client'):
			item = query.split()[0]
			user = User(user_id=query.split()[-1])
			menu = InlineKeyboardMarkup(row_width=1) # for submenu
			if item == 'client':
				tariff = user.tariff()
				t_info = f'"*{tariff.name}*"\n- *Количество тренировок*: {training_types(user)}\n' \
							  f'- *Срок действия до*: _{datetime.strftime(user.subscription_plan["period"], "%d.%m.%Y")}_\n' \
							  f'- *Дата покупки*: _{datetime.strftime(user.subscription_plan["start_timestamp"], "%d.%m.%Y") if user.subscription_plan["start_timestamp"] else "нет"}_' if tariff else "_отсутствует_"

				level = Level(user=user)
				if not level.id is None and not user.training_self() is None:
					training_self_history = [i for i in user.training_self() if i['training_type'] == 'self'] or []
					level_training_self_history = level.user_training_self or []
					amount = level.sessions_amount - len(level_training_self_history)
					# добавить больше инфы
					training_self_info = f'_уровень_ "*{level.name}*"\n' \
										 f'- _всего самостоятельных тренировок_: *{len(training_self_history)}*\n' \
										 f'- _тренировок до следующего уровня_: *{amount if amount > 0 else 0}*\n' \
										 f'- _тренировок на текущем уровне_: *{len(level_training_self_history)}*\n' \
										 f'- _тренировок за последний месяц_: *{len([i for i in training_self_history if not i["training_started_at"] is None and datetime.now() - i["training_started_at"] <= timedelta(days=30)])}*'
				else:
					training_self_info = "_не тренируется самостоятельно_"


				user_actions_menu = InlineKeyboardMarkup(row_width=1)
				buttons = [
					InlineKeyboardButton(text='❔ Запись', callback_data=f'client_signing_up {user.id}'),
				InlineKeyboardButton(text='💴 Коммерция', callback_data=f'client_commercial {user.id}')
				]
				user_actions_menu.add(buttons[1])

				if user.past_sessions() or user.upcoming_sessions():
					user_actions_menu.add(buttons[0])

				if user.forms():
					user_actions_menu.add(InlineKeyboardButton(text='📍 Опросы', callback_data=f'client_form {user.id}'))

				if user.permissions:
					if 'individual_trainings' in user.permissions or 'self_trainings' in user.permissions or user.training_reports():
						user_actions_menu.add(InlineKeyboardButton(text='🏋️ Тренировки', callback_data=f'client_trainings {user.id}'))

				username = '@' + user.username if user.username and not '_' in user.username else "не указано" # проблема в том, что parse_mode в ТГ не принимает экранирование в виде \
				text = f'👤 *{user.fullname}*\n' +\
					 f'*Никнейм Telegram*: _{username}_\n' +\
					 f'*Последняя активность*: _{datetime.strftime(user.last_callback, "%d.%m.%Y, %H:%M")}_.\n\n' +\
					 f'*Тариф*: {t_info}\n\n' +\
					 f'*Самостоятельные тренировки*: {training_self_info}'

				msg = bot.send_message(callback.message.chat.id, text, reply_markup=user_actions_menu.add(telebutton('👈 Назад', 'admin_choose_user')))

			elif item.startswith('client_signing_up'):
				buttons = []
				if item == 'client_signing_up':
					text = ''
					if user.past_sessions():
						buttons.append(InlineKeyboardButton(text='📜 История посещений', callback_data=f'client_signing_up_history {user.id}'))
						text += '*История посещений* - просмотреть историю посещений клиентом очных тренировок.\n'
					if user.upcoming_sessions():
						buttons.append(InlineKeyboardButton(text='❌ Отменить запись', callback_data=f'client_signing_up_cancel {user.id}'))
						text += '*Отменить запись* - отменить предстоящую запись клиента на тренировку с вами.'
					buttons.append(InlineKeyboardButton(text='👈 Назад', callback_data=f'client {user.id}'))
				elif item == 'client_signing_up_history':
					splitted = query.split()
					history = user.past_sessions()
					if len(splitted) == 2:
						buttons = [
							InlineKeyboardButton(text=i, callback_data=f'client_signing_up_history {i} {user.id}')
							for i in set([i.year for i in [j['date'] for j in history]])] + [
									  InlineKeyboardButton(text='👈 Назад', callback_data=f'client_signing_up {user.id}')]
						text = 'Выберите год тренировок.'
					elif len(splitted) == 3:
						year = splitted[1]
						history = [i['date'].month for i in history if
								   i['date'].year == int(year)]
						buttons = [InlineKeyboardButton(text=months[i].title(),
														callback_data=f'client_signing_up_history {year} {i + 1} {user.id}')
								   for i in range(12) if i + 1 in history] + [
									  InlineKeyboardButton(text='👈 Назад', callback_data=f'client_signing_up_history {user.id}')]
						menu.row_width = 5
						text = f'Выберите месяц тренировок ({year} год).'
					elif len(splitted) == 4:
						year, month = int(splitted[1]), int(splitted[2])
						history = [f'🗓 Дата и время: *{i["date"].isoformat()}, {str(i["time"])[:-3]}*\n' \
								   f'- Тип тренировки: *{training_types()[i["session_type"]]}*' + \
								   (f'\n- Комментарий клиента: _{i["details"]}_' if i["details"] else '') for i in
								   [j for j in history if
									j['date'].year == year and j['date'].month == month]]
						text = f'⏳ *{months[month - 1].title()} {year}*\n' + '\n'.join(history)
						buttons = [InlineKeyboardButton(text='👈 Назад', callback_data=f'client_signing_up_history {year} {user.id}')]

				elif item == 'client_signing_up_cancel':
					c_len = len(query.split())
					upcoming_sessions = user.upcoming_sessions()
					schedule = sorted(list(reduce(lambda x, y: x + y,
												  [ScheduleDay(coach, i).user_signed_up_hours(user) for i in
												   [j['date'] for j in upcoming_sessions]], [])),
									  key=lambda x: (x.date, x.time))
					if c_len == 2:
						out = '\n'.join([f'⏳ _{fullname_of_date(i["date"])}_, _{str(i["time"])[:-3]}_, _{training_types()[i["session_type"]]}_' + (
												f', *комментарий*: _{i["details"]}_' if i['details'] else '') for i
											in upcoming_sessions])
						text = f'📜 *Предстоящие тренировки* клиента {user.fullname}:\n{out}\n\nВыберите дату и время тренировки клиента *{user.fullname}*, которую хотите отменить.'

						buttons = [InlineKeyboardButton(text=f'❌ {h.date}, {h.time}:00',
														callback_data=f'client_signing_up_cancel {h.date} {h.time}:00 {user.id}') for h in
								   schedule] + [InlineKeyboardButton(text='👈 Назад', callback_data=f'client_signing_up {user.id}')]
					elif c_len == 4:
						splitted = query.split()
						signup_date = datetime.fromisoformat(splitted[1]).date()
						time = int(splitted[2].split(':')[0])
						for h in schedule:
							if h.date == signup_date and h.time == time:
								h.cancel(user, canceling_type='coach')
								training_type = training_types()[h.session_type]
								break
						text = f'Запись клиента *{user.fullname}* на *{signup_date}, {time}:00* (тип тренировки _{training_type}_) успешно отменена!'
						bot.send_message(user.chat_id,
										 f'Тренер *{coach.fullname}* отменил вашу запись на тренировку на *{signup_date}, {time}:00* (тип тренировки _{training_type}_).\n'
										 f'Извините, если это доставило вам неудобства.\n\n'
										 f'Для дополнительной информации можете связаться с ним по телефону: _{coach.form()["phone_number"]}_.')

				msg = bot.send_message(coach.chat_id, text, reply_markup=menu.add(*buttons)) if buttons else bot.send_message(coach.chat_id, text)
				del_msgs('signup', coach)
				temp_msgs('signup', coach, msg)

			elif item.startswith('client_commercial'):
				if item == 'client_commercial':
					buttons = [
						InlineKeyboardButton(text='Начислить тариф', callback_data=f'client_commercial_set_tariff {user.id}'),
						InlineKeyboardButton(text='История оплат', callback_data=f'client_commercial_paying_history {user.id}'),
						InlineKeyboardButton(text='👈 Назад', callback_data=f'client {user.id}')
					]
					msg = bot.send_message(coach.chat_id, '*"Начислить тариф"* - начислить любой из доступных клиентам тарифов.\n\n'
														  '*"История оплат"* - история платежей, полученных от клиента.',
										   reply_markup=menu.add(*buttons))


				elif item == 'client_commercial_set_tariff':
					if len(query.split()) == 2:
						tariffs = coach.tariffs
						if tariffs:
							lst = '\n--------------\n'.join([
								f'*Название тарифа*: "_{i.name}_"\n'
								f'*Период действия, дней*: _{i.period}_\n'
								f'*Количество отмен*: _{(i.canceling_amount if i.canceling_amount != 100 else "не ограничено") if i.canceling_amount else 0}_\n'
								f'*Количество тренировок*:\n{training_types(tariff=i)}\n'
								f'*Уровень доступа*:\n{tariff_permissions(tariff=i)}'
							for i in tariffs])
							buttons = [InlineKeyboardButton(text=i.name, callback_data=f'client_commercial_set_tariff {i.id} {user.id}') for i in tariffs]
							msg = bot.send_message(coach.chat_id, f'{lst}\n\nВыберите, какой тариф нужно начислить клиенту *{user.fullname}*.\n\n'
																  f'_Оплата будет зафиксирована!_',
												   reply_markup=menu.add(*buttons))
						else:
							msg = bot.send_message(coach.chat_id, 'У вас нет доступных тарифов.\n\n'
																  'Создайте их в меню *"Общее"* 👉 *"Коммерция"* 👉 *"Тарифы"*.')

					elif len(query.split()) == 3:
						tariff = Tariff(tariff_id=query.split()[1])
						user.pay_tariff(tariff)
						msg = bot.send_message(coach.chat_id, f'Клиенту *{user.fullname}* успешно начислен тариф "*{tariff.name}*"')

				elif item == 'client_commercial_paying_history':
					payments = user.payments()
					if payments:
						text = '\n'.join([f'💰 *Дата платежа*: _{i["payment_date"].date()}_\n'
										  f'- *Тариф*: _"{Tariff(i["tariff_id"]).name}"_\n'
										  f'- *Сумма*: _{i["payment_amount"]}₽_' for i in payments])
					else:
						text = f'История платежей от клиента *{user.fullname}* пока пуста!'
					msg = bot.send_message(coach.chat_id, text, reply_markup=menu.add(
						InlineKeyboardButton(text='👈 Назад', callback_data=f'client_commercial {user.id}')
					))

			elif item == 'client_form':
				form = user.forms()
				lst = '\n\n'.join([f'❓ *Вопрос*: _{i["questions"]}_\n📜 *Ответ*: _{i["answers"]}_\n⏳ *Дата ответа*: _{i["answer_timestamp"]}_' for i in form])
				msg = bot.send_message(coach.chat_id, lst, reply_markup=menu.add(
					InlineKeyboardButton(text='👈 Назад', callback_data=f'client {user.id}')
				))

			elif item == 'client_trainings':
				buttons = [
					InlineKeyboardButton(text='🏋️‍♀️ Индивидуальные', callback_data=f'client_trainings_individual {user.id}'),
					InlineKeyboardButton(text='🏃 Самостоятельные', callback_data=f'client_trainings_self {user.id}'),
					InlineKeyboardButton(text='💪 Рекорды', callback_data=f'client_trainings_records {user.id}')
				]

				desc_1, desc_2, desc_3 = '', '', ''
				if 'individual_trainings' in user.permissions:
					menu.add(buttons[0])
					desc_1 = '*Индивидуальные тренировки* - отправка индивидуальных заданий, просмотр истории их выполнения, отчетов по ним.\n\n'
				if 'self_trainings' in user.permissions:
					menu.add(buttons[1])
					desc_2 =  '*Самостоятельные тренировки* - просмотр истории выполнения самостоятельных тренировок, отчетов по ним.\n\n'
				if not user.records() is None:
					menu.add(buttons[2])
					desc_3 = '*Рекорды* - просмотр рекордов клиента, выполненных по самостоятельным/индивидуальным тренировкам.'

				menu.add(InlineKeyboardButton(text='👈 Назад', callback_data=f'client {user.id}'))

				text = desc_1 + desc_2 + desc_3

				msg = bot.send_message(coach.chat_id, text, reply_markup=menu)

			elif query.startswith('client_trainings_self'):
				splitted = query.split()
				if splitted[0] == 'client_trainings_self':
					buttons = [InlineKeyboardButton(text='📜 Просмотреть историю', callback_data=f'client_trainings_self_history {user.id}'),
							   InlineKeyboardButton(text='🟢 Просмотреть отчеты', callback_data=f'client_trainings_self_reports {user.id}')]
					text = ''
					if user.training_reports(reports_type='self'):
						menu.add(buttons[1])
						text += '🟢 *Просмотреть отчеты* - просмотр всех отчетов клиента по самостоятельным тренировкам.\n\n'
					user_self_trainings = [i for i in user.training_self() if i['training_type'] == 'self' and i['training_started_at']]
					if user_self_trainings:
						menu.add(buttons[0])
						text += '📜 *Просмотреть историю* - просмотр истории всех самостоятельных тренировок клиента, в том числе без отчетности.'
					if not menu.keyboard:
						text = f'История самостоятельных тренировок и отчетов по ним у клиента *{user.fullname}* пуста.'
					else:
						text += f'\n\nВсего выполнено самостоятельных тренировок: *{len(user_self_trainings)}*.'
						menu.add(InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings {user.id}'))
					msg = bot.send_message(coach.chat_id, text, reply_markup=menu) if menu.keyboard else bot.send_message(coach.chat_id, text)
				elif splitted[0] == 'client_trainings_self_history':
					history = user.self_trainings_history('self', 'coach')
					if history:
						with open(f'История тренировок {user.fullname}.xlsx', 'rb') as file:
							msg_2 = bot.send_document(coach.chat_id, file)
							msg = None
							temp_msgs('training_self_history', coach, msg_2)
						remove(f'История тренировок {user.fullname}.xlsx')

				elif splitted[0] == 'client_trainings_self_reports':
					if len(splitted) == 2:
						reports = user.training_reports(reports_type='self')
						buttons = [InlineKeyboardButton(text=i, callback_data=f'client_trainings_self_reports {user.id} {i}') for i in set([i.year for i in [j['report_date'] for j in reports]])] + \
							[InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings_self {user.id}')]
						msg = bot.send_message(coach.chat_id, 'Выберите год тренировок', reply_markup=menu.add(*buttons))
					elif len(splitted) == 3:
						user = User(user_id=splitted[1])
						print(splitted[1])
						year = splitted[2]
						reports = [i['report_date'].month for i in user.training_reports(reports_type='self') if i['report_date'].year == int(year)]
						buttons = [InlineKeyboardButton(text=months[i].title(),
														callback_data=f'client_trainings_self_reports {user.id} {year} {i + 1}')
								   for i in range(12) if i + 1 in reports] + \
								  [InlineKeyboardButton(text='👈 Назад',
														callback_data=f'client_trainings_self_reports {user.id}')]
						menu.row_width = 5
						msg = bot.send_message(coach.chat_id, f'Выберите месяц тренировок ({year} год).',
											   reply_markup=menu.add(*buttons))
					elif len(splitted) == 4:
						user = User(user_id=splitted[1])
						year, month = int(splitted[2]), int(splitted[3])
						reports = [TrainingReport(user, i) for i in [j['report_date'] for j in user.training_reports(reports_type='self') if j['report_date'].year == year and j['report_date'].month == month]]
						text = '\n\n'.join([report.description() for report in reports]) + '\n\nНажмите на кнопку с датой отчета, чтобы просмотреть отчетное видео.'
						buttons = [InlineKeyboardButton(text=f'🎥 {str(i.datetime)[:-3]}', callback_data=f'client_trainings_self_reports {user.id} {year} {month} {reports.index(i)}') for i in reports] + \
								  [InlineKeyboardButton(text='👈 Назад',
														callback_data=f'client_trainings_self_reports {user.id} {year}')]
						menu.row_width=3
						msg = None
						msg_2 = bot.send_message(coach.chat_id, text, reply_markup=menu.add(*buttons))
						temp_msgs('report_view', coach, msg_2)
					elif len(splitted) == 5:
						user = User(user_id=splitted[1])
						year, month, idx = int(splitted[2]), int(splitted[3]), int(splitted[4])
						reports = [TrainingReport(user, i) for i in
								   [j['report_date'] for j in user.training_reports(reports_type='self') if
									j['report_date'].year == year and j['report_date'].month == month]]
						report_video_id = reports[idx].content
						msg = None
						msg_2 = bot.send_video(coach.chat_id, report_video_id)
						temp_msgs('report_view', coach, msg_2)
			elif item.startswith('client_trainings_records'):
				usr = User(callback.message.chat.id) # т.к. общая ветка для тренеров и для клиентов
				buttons = []
				if item == 'client_trainings_records':
					buttons = [
						InlineKeyboardButton(text='Все рекорды', callback_data=f'client_trainings_records_all {user.id}'),
						InlineKeyboardButton(text='По категориям', callback_data=f'client_trainings_records_categories {user.id}')
					]
					if usr.is_coach:
						buttons.append(InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings {user.id}'))
					text = f'*Все рекорды* - просмотреть все выполненные рекорды клиента *{user.fullname}*.\n\n' \
						   f'*По категориям* - просмотреть рекорды по определенным категориям упражнений.' if usr.is_coach else \
							f'*Все рекорды* - просмотреть все личные зафиксированные рекорды.\n\n' \
							f'*По категориям* - просмотреть личные рекорды по определенным категориям упражнений.'
				elif item == 'client_trainings_records_all':
					records = user.records()
					menu.row_width = 5
					buttons = [
						InlineKeyboardButton(text=f'💪 {records.index(i) + 1}', callback_data=f'client_trainings_records_video {records.index(i)} {user.id}')
						for i in records
					] + [InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings_records {user.id}')]
					text = '\n\n'.join([f'💪 Рекорд №{records.index(i) + 1}\n{i.record_description()}' for i in records]) + '\n\nНажмите на кнопку с номером рекорда, ' \
																														   'чтобы просмотреть его видео.'
				elif item == 'client_trainings_records_video':
					if len(query.split()) == 3:
						records = user.records()
						record_idx = int(query.split()[1])
					elif len(query.split()) == 4:
						category_id = int(query.split()[1])
						records = [i for i in user.records() if Exercise(i.exercise.exercises_id, coach=False).category_id == category_id]
						record_idx = int(query.split()[2])
					record_video = records[record_idx].content
					text = None
					msg = None
					msg_2 = bot.send_video((coach if usr.is_coach else user).chat_id, record_video)
					temp_msgs('user_records', coach if usr.is_coach else user, msg_2)

				elif item == 'client_trainings_records_categories':
					if len(query.split()) == 2:
						categories = set(sorted([(i.category, i.category_id) for i in [Exercise(j.exercise.exercises_id, coach=False) for j in user.records()]], key=lambda x: x[0]))
						buttons = [
							InlineKeyboardButton(text=i[0].title(), callback_data=f'client_trainings_records_categories {i[1]} {user.id}')
							for i in categories
						] + [InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings_records {user.id}')]
						text = f'Выберите категорию упражнений, чтобы просмотреть рекорды клиента *{user.fullname}* по ней.' if usr.is_coach else \
							'Выберите категорию упражнений.'
					elif len(query.split()) == 3:
						category_id = int(query.split()[1])
						records = ([i for i in user.records() if Exercise(i.exercise.exercises_id, coach=False).category_id == category_id])
						menu.row_width = 5
						buttons = [
									  InlineKeyboardButton(text=f'💪 {records.index(i) + 1}',
														   callback_data=f'client_trainings_records_video {category_id} {records.index(i)} {user.id}')
									  for i in records
								  ] + [InlineKeyboardButton(text='👈 Назад',
															callback_data=f'client_trainings_records_categories {user.id}')]
						text = '\n\n'.join([f'💪 Рекорд №{records.index(i) + 1}\n{i.record_description()}' for i in
											records]) + '\n\nНажмите на кнопку с номером рекорда, ' \
														'чтобы просмотреть его видео.'
				if buttons:
					menu.add(*buttons)
				if not text is None:
					msg = bot.send_message((coach if usr.is_coach else user).chat_id, text, reply_markup=menu) if menu.keyboard else bot.send_message((coach if usr.is_coach else user).chat_id, text)


			elif item.startswith('client_trainings_individual'):
				if item == 'client_trainings_individual':
					buttons = [
						InlineKeyboardButton(text='📍 Отправить задание',
											 callback_data=f'client_trainings_individual_send {user.id}'),
						InlineKeyboardButton(text='📜 Просмотреть историю',
											 callback_data=f'client_trainings_individual_history {user.id}'),
						InlineKeyboardButton(text='🟢 Просмотреть отчеты',
											 callback_data=f'client_trainings_individual_reports {user.id}')
					]

					desc = ''
					training_self = user.training_self()
					training_history = [i for i in training_self if i['training_type'] == 'individual' and i['training_started_at']] if training_self else None
					if training_history:
						training_history = [TrainingPlan(i['training_plans_id']) for i in training_history]
						if training_history:
							menu.add(*buttons[1:])
							desc = f'Всего выполнено тренировок по индивидуальным планам: *{len(training_history)}*.'
					menu.add(buttons[0], InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings {user.id}'))
					msg = bot.send_message(coach.chat_id, f'Выберите, какое действие хотите совершить.\n\n{desc}', reply_markup=menu)
					del_msgs('send_plan', coach)

				elif item.startswith('client_trainings_individual_reports'):
					splitted = query.split()
					menu = InlineKeyboardMarkup(row_width=1)
					user = User(user_id=splitted[1])
					dct = {'video': 'Видео', 'text': 'Текстовые'}
					if len(splitted) == 2:
						reports_types = set(sorted([i['report_type'] for i in user.training_reports(reports_type='individual')]))
						buttons = [InlineKeyboardButton(text=dct[i], callback_data=f'client_trainings_individual_reports {user.id} {i}') for i in reports_types] + \
						[InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings {user.id}')]
						msg = bot.send_message(coach.chat_id, 'Выберите тип отчетов.', reply_markup=menu.add(*buttons))
						del_msgs('report_view', coach)
					if len(splitted) == 3:
						reports_type = splitted[2]
						reports = filter(lambda x: x['report_type'] == reports_type, user.training_reports(reports_type='individual'))
						buttons = [InlineKeyboardButton(text=i, callback_data=f'client_trainings_individual_reports {user.id} {reports_type} {i}') for i in set([i.year for i in [j['report_date'] for j in reports]])] + \
								  [InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings_individual_reports {user.id}')]
						msg = bot.send_message(coach.chat_id, f'Выберите год тренировок (тип отчетов _{dct[reports_type].lower()}_)', reply_markup=menu.add(*buttons))
						del_msgs('report_view', coach)
					elif len(splitted) == 4:
						year, reports_type = splitted[3], splitted[2]
						reports = [i['report_date'].month for i in user.training_reports(reports_type='individual') if i['report_date'].year == int(year) and
								   i["report_type"] == reports_type]
						buttons = [InlineKeyboardButton(text=months[i].title(),
														callback_data=f'client_trainings_individual_reports {user.id} {reports_type} {year} {i + 1}')
								   for i in range(12) if i + 1 in reports] + \
								  [InlineKeyboardButton(text='👈 Назад',
														callback_data=f'client_trainings_individual_reports {user.id} {reports_type}')]
						menu.row_width = 5
						msg = bot.send_message(coach.chat_id, f'Выберите месяц тренировок ({year} год, тип отчетов _{dct[reports_type].lower()}_).',
											   reply_markup=menu.add(*buttons))
						del_msgs('report_view', coach)
					elif len(splitted) == 5:
						year, month, reports_type = int(splitted[3]), int(splitted[4]), splitted[2]
						reports = [TrainingReport(user, i) for i in [j['report_date'] for j in user.training_reports(reports_type='individual') if j['report_date'].year == year and j['report_date'].month == month and j['report_type'] == reports_type]]
						text = f"*Отчеты типа _{dct[reports_type].lower()}_, {months[month-1].title()} {year}*\n\n" + '\n\n'.join([report.description() for report in reports]) +\
							   ('\n\nНажмите на кнопку с датой отчета, чтобы просмотреть отчетное видео.' if reports_type == 'video' else '')
						if reports_type == 'video':
							buttons = [InlineKeyboardButton(text=f'🎥 {str(i.datetime)[:-3]}', callback_data=f'client_trainings_individual_reports {user.id} {reports_type} {year} {month} {reports.index(i)}') for i in reports] + \
									  [InlineKeyboardButton(text='👈 Назад',
															callback_data=f'client_trainings_individual_reports {user.id} {reports_type} {year}')]
							menu.row_width=3
						msg = None

						if len(text) < 3500:
							msg_2 = bot.send_message(coach.chat_id, text, reply_markup=menu.add(*buttons)) if reports_type == 'video' else bot.send_message(coach.chat_id, text)
							temp_msgs('report_view', coach, msg_2)
						else:
							splitted_text = util.smart_split(text, 3500)
							for i in splitted_text:
								if i != splitted_text[-1]:
									msg_2 = bot.send_message(coach.chat_id, i)
								else:
									msg_2 = bot.send_message(coach.chat_id, i, reply_markup=menu.add(
										*buttons)) if reports_type == 'video' else bot.send_message(coach.chat_id, i)
								temp_msgs('report_view', coach, msg_2)

					elif len(splitted) == 6:
						year, month, idx, reports_type = int(splitted[3]), int(splitted[4]), int(splitted[5]), splitted[2]
						reports = [TrainingReport(user, i) for i in
								   [j['report_date'] for j in user.training_reports(reports_type='individual') if
									j['report_date'].year == year and j['report_date'].month == month] and j['report_type'] == reports_type]
						report_video_id = reports[idx].content
						msg = None
						msg_2 = bot.send_video(coach.chat_id, report_video_id)
						temp_msgs('report_view', coach, msg_2)

				elif item == 'client_trainings_individual_history':
					history = user.self_trainings_history('individual', 'coach')
					if history:
						with open(f'История тренировок {user.fullname}.xlsx', 'rb') as file:
							msg_2 = bot.send_document(coach.chat_id, file)
							msg = None
							temp_msgs('training_self_history', coach, msg_2)
						remove(f'История тренировок {user.fullname}.xlsx')

				elif item == 'client_trainings_individual_send':
					if len(query.split()) == 2:
						excel_form_write(coach, user)
						buttons = [
							InlineKeyboardButton(text='Готово', callback_data=f'client_trainings_individual_send {True} {user.id}'),
							InlineKeyboardButton(text='Настроить форму', callback_data=f'client_trainings_individual_set_excel {user.id}'),
							InlineKeyboardButton(text='👈 Назад', callback_data=f'client_trainings_individual {user.id}')
						]
						if not coach.special_excel_form(user):
							text = f'Заполните таблицу Excel. Нажмите *"Готово"*, когда все будет готово для отправки задания клиенту *{user.fullname}*.\n\n'+\
																  f'P.S. В столбце *"Повторения"* не указывайте ничего, чтобы дать задание клиенту выполнить _максимально возможное_ количество повторений (если при этом не указать количество подходов, их количество установится в размере 1).\n'+\
																  f'В столбце *"Видео-отчет"* укажите число _1_, чтобы видео-отчет по упражнению был обязательным. Если вы не выберите ни одного упражнения для видео-отчета, '+\
																  f'обязательными для отчетности _автоматически_ будут назначены *от 1 до 2 упражнений*.\n\n'+\
																  f'Воспользуйтесь стандартной формой для отправки задания или нажмите *"Настроить форму"*, чтобы настроить продвинутую форму с определенными базовым упражнениями.'
						else:
							text = f'Заполните таблицу Excel. Нажмите *"Готово"*, когда все будет готово для отправки задания клиенту *{user.fullname}*.\n\n'+\
								'Вы используете расширенную форму отправки задания данному клиенту. Чтобы сбросить ее до стандартной, зайдите в меню *"Настроить форму"*.\n' \
								'В данной форме все упражнения из раздела *"Базовые упражнения"* после отправки автоматически становятся обязательными для видео-отчета.\n\n' \
								'Выбор и настройка дополнительных упражнений происходят аналогично стандартной форме отправки.'
						msg = bot.send_message(coach.chat_id, text, reply_markup=menu.add(*buttons))
						temp_msgs('send_plan', coach, msg)
						msg = bot.send_document(coach.chat_id, open(f'План тренировки ({user.fullname}).xlsx', 'rb'))
						remove(f'План тренировки ({user.fullname}).xlsx')

					elif len(query.split()) == 3:
						param = query.split()[1]
						if param == 'True':
							coach.status = f'client_trainings_individual_send {user.id}'
							try:
								coach.set_coach()
							finally:
								msg = bot.send_message(coach.chat_id, 'Отправьте заполненную таблицу с заданиями прямо сейчас.')
								del_msgs('send_plan', coach)
				elif item == 'client_trainings_individual_set_excel':
					menu.row_width = 2
					del_msgs('send_plan', coach)
					exs = coach.raw_exercises()
					step = len(query.split()) - 1
					def general_msg():
						text = f'Выберите категорию упражнений, чтобы добавить его в список для включения в форму отправки задания для клиента {user.fullname}\n'
						categories = sorted(set([(i['category_name'], i['category_id']) for i in exs]), key=lambda x: x[0])
						buttons = [telebutton(i[0][0].upper() + i[0][1:],
											  f"client_trainings_individual_set_excel {i[1]} {user.id}") for i in
								   categories] + [telebutton('👈 Назад', f'client_trainings_individual_send {user.id}')]
						if not coach.special_excel_form(user) is None:
							text += '\nИли нажмите *"Очистить выбор"*, чтобы вернуться к стандартному варианту формы для отправки задания данному клиенту.'
							buttons.insert(-2, telebutton('❌ Отменить выбор', f'client_trainings_individual_set_excel cancel {user.id}'))
						return text, buttons
					if step == 1:
						text, buttons = general_msg()
						temp_dct['coaches'].pop(coach.id, None)
					elif step == 2:
						if not query.split()[1] in ['done', 'cancel']:
							category_id = int(query.split()[1])
							exs = sorted(map(lambda x: Exercise(x['exercise_id'], coach=False), filter(lambda x: x['category_id'] == category_id, exs)), key=lambda x: x.name)
							text = f'Выберите упражнение для включения его в форму для отправки задания.'
							buttons = [telebutton(i.name[0].upper() + i.name[1:], f"client_trainings_individual_set_excel {i.category_id} {i.exercises_id} {user.id}") for i in exs] + \
								[telebutton('👈 Назад', f'client_trainings_individual_set_excel {user.id}')]
						else:
							if query.split()[1] == 'done':
								lst = map(str, temp_dct['coaches'][coach.id]['exercises_to_excel'][user.id])
								coach.special_excel_form(user, update=True, lst=lst)
								text = f'Настройки формы для отправки задания клиенту {user.fullname} успешно сохранены!'
								temp_dct['coaches'].pop(coach.id, None)
							elif query.split()[1] == 'cancel':
								coach.special_excel_form(user, delete=True)
								text = f'Форма отправки задания для клиента *{user.fullname}* успешно сброшена!'
							buttons = [telebutton('📍 Отправить клиенту задание', f'client_trainings_individual_send {user.id}'),
									   telebutton('👈 Назад', f'client_trainings_individual {user.id}')]
					elif step == 3:
						ex = Exercise(int(query.split()[2]), coach=False)
						try:
							lst = temp_dct['coaches'][coach.id]['exercises_to_excel'][user.id]
							if len(lst) < 4:
								lst.append(ex.exercises_id)
						except KeyError:
							temp_dct['coaches'][coach.id] = {'exercises_to_excel': {user.id: [ex.exercises_id]}}
							lst = temp_dct['coaches'][coach.id]['exercises_to_excel'][user.id]
						text, buttons = general_msg()
						if len(lst) < 4:
							text += (f'\nУпражнение *{ex.name}* успешно добавлено в форму для отправки задания клиенту _{user.fullname}_!\n' if len(lst) == 1 else
									 f'Текущие упражнения для добавления в форму для отправки задания клиенту _{user.fullname}_: ' +
									 ', '.join([f'_{Exercise(i, coach=False).name}_' for i in lst])) +\
									f'\nМаксимум можно выбрать 4 упражнения.\n\nНажмите *"Готово"*, чтобы сохранить настройки.'
						else:
							text += '\nНельзя добавить больше 4-х упражнений в список! Чтобы начать сначала, зайдите в меню настройки таблицы заново.'
						buttons.append(telebutton('Готово', f'client_trainings_individual_set_excel done {user.id}'))
					msg = bot.send_message(coach.chat_id, text, reply_markup=menu.add(*buttons))


			elif item.startswith('client_trainings_plan'):
				plans = temp_dct['coaches'][coach.id]['individual_plan']
				if item == 'client_trainings_plan':
					param = query.split()[1]
					training_plan_number = int(query.split()[-2])
					training_plan = plans[training_plan_number]
					d = {10: '10 мин', 20: "20 мин", 30: "30 мин", 40: "40 мин", 50: "50 мин", 60: "1 ч", 90: "1.5 ч", 120: "2 ч", 180: "3 ч"}
					def msg():
						return ('\n' + '-'*15 + '\n').join([f'🏋️‍♀️ План тренировки №{i}\n' + '\n---\n'.join([f'▫️ *Упражнение №{plans[i]["exercises"].index(j) + 1}*\n' + j[0].description() + f'\n*Видео-отчет*: {"да" if j[1] else "нет"}' for j in plans[i]['exercises']]) + f'\n\n'
																																																						  f'*Сложность тренировки:* _{str(plans[i]["rating"]) + " из 10" if plans[i]["rating"] else "не указана"}_\n'
																																																						  f'*Длительность тренировки*: _{d[plans[i]["duration"]] if plans[i]["duration"] else "не указана"}_' for i in plans if not i in ['message', 'buttons']])
					temp_dct['coaches'][coach.id]['individual_plan']['message'] = msg
					if param in ['rate', 'dur', 'rate_set', 'dur_set']:
						if item == 'client_trainings_plan':
							if param == 'rate':
								buttons = [InlineKeyboardButton(text=i, callback_data=f'client_trainings_plan rate_set {i} {training_plan_number} {user.id}') for i in range(1, 11)]
								text = 'Укажите сложность тренировки от 1 до 10.\n\nСложность постарайтесь определить относительно умений и уровня развития клиента.'
							elif param == 'dur':
								buttons = [InlineKeyboardButton(text=d[i], callback_data=f'client_trainings_plan dur_set {i} {training_plan_number} {user.id}') for i in [10, 20, 30, 40, 50, 60, 90, 120, 180]]
								text = 'Укажите максимальную длительность тренировки.\n\nПостарайтесь определить ее относительно умений и уровня развития клиента (и того, ' \
									   'за какое время он реально сможет справиться с планом.'
							elif param in ['rate_set', 'dur_set']:
								val = query.split()[2]
								txt = {'rate_set': 'сложность', 'dur_set': 'длительность'}
								if param == 'rate_set':
									training_plan['rating'] = int(val)
								elif param == 'dur_set':
									training_plan['duration'] = int(val)
								text = f'*Параметр "{txt[param]}" успешно изменен!*'
								buttons = temp_dct['coaches'][coach.id]['individual_plan']['buttons']
								if all(i['rating'] and i['duration'] for i in [plans[j] for j in plans if isinstance(j, int)]):
									menu.add(InlineKeyboardButton(text='☑️ Отправить', callback_data=f'client_trainings_plan_send {user.id}'))
							for b in buttons:
								menu.add(*b) if isinstance(b, list) else menu.add(b)

							msg = bot.send_message(coach.chat_id, temp_dct['coaches'][coach.id]['individual_plan']['message']() + '\n\n' + text, reply_markup=menu)

				elif item == 'client_trainings_plan_send':
					plans_objs = []
					for item in plans:
						if isinstance(item, int):
							plan = plans[item]
							exs = {i[0].coachs_exercises_id: (True if i[1] else False) for i in plan['exercises']}
							individual_plan = TrainingPlan()
							individual_plan.coachs_id = coach.id
							individual_plan.exercises = exs
							individual_plan.duration = plan['duration']
							individual_plan.rate = plan['rating']
							individual_plan.type = 'individual'
							individual_plan.users_id = user.id
							plan_id = individual_plan.new()
							individual_plan.id = plan_id
							plan_obj = individual_plan.new_training_self(user)
							plans_objs.append(plan_obj)

					individual_training_plan(user, plans_objs)
					text = f'💪 *Ваше новое задание от тренера!*\n\n' + plans['message']() + '\n\nКогда будете готовы выполнять тренировки - смело заходите в меню *"Мои тренировки"* 👉 *"Индивидуальные занятия"*.'
					if len(text) < 3500:
						msg_2 = bot.send_message(user.chat_id, text)
						temp_msgs('training_self', user, msg_2)
					else:
						splitted_text = util.smart_split(text, 3500)
						for i in splitted_text:
							msg_2 = bot.send_message(user.chat_id, i)
							temp_msgs('training_self', user, msg_2)
					msg = bot.send_message(coach.chat_id, f'Задание успешно отправлено клиенту *{user.fullname}*!\n\nОжидайте отчеты по выполненным тренировкам от него.')
					temp_dct['coaches'].pop(coach.id, None)
			if msg:
				usr = User(callback.message.chat.id)
				if usr.is_coach:
					del_msgs('main_admin', coach)
					temp_msgs('main_admin', coach, msg)
				else:
					del_msgs('my_trainings', usr)
					temp_msgs('my_trainings', usr, msg)



		if query.startswith('my_forms'):
			if query == 'my_forms':
				menu = InlineKeyboardMarkup(row_width=1).add(
					InlineKeyboardButton(text='Мои вопросы', callback_data='my_forms_questions'),
					InlineKeyboardButton(text='Ответы клиентов', callback_data='my_forms_answers')
				)
				msg = bot.send_message(coach.chat_id, '*Мои вопросы* - список текущих вопросов для сбора анкет с клиентов. В этом подменю вы можете также добавить новые вопросы.\n\n'
													  '*Ответы клиентов* - имеющиеся ответы на вопросы от клиентов.', reply_markup=menu)
			elif query.split()[0] in ['my_forms_questions', 'my_forms_add', "my_forms_delete"]:
				questions = coach.extra()['questions_for_users']
				menu = InlineKeyboardMarkup(row_width=5).add(InlineKeyboardButton(text='Добавить вопрос', callback_data='my_forms_add'))
				if query == 'my_forms_questions':
					if not questions:
						text = 'Вы пока не установили вопросы для своих клиентов.\n\n' \
							   'Бот будет собирать данные от них по мере использования клиентами функций бота.\n\n' \
							   'Нажмите *"Добавить вопрос"*, чтобы создать свой первый вопрос!'
					else:
						questions = list(enumerate(questions, 1))
						menu.add(*[InlineKeyboardButton(text=f'❌{i[0]}', callback_data=f'my_forms_delete {i[0]}') for i in questions],
								 InlineKeyboardButton(text='👈 Назад', callback_data='my_forms'))
						text = '*Ваши текущие вопросы:*\n' + '\n\n'.join([f'❓ Вопрос №{i[0]}:\n- _"{i[1]}"_' for i in questions]) + '\n\nЧтобы добавить новый вопрос, нажмите *"Добавить вопрос"*.\n' \
																																  'Чтобы удалить текущий вопрос, нажмите на кнопку *с его номером*.'
					msg = bot.send_message(coach.chat_id, text, reply_markup=menu)
				elif query == 'my_forms_add':
					msg = bot.send_message(coach.chat_id, 'Напишите новый вопрос для опроса ваших клиентов.\n\n'
														  'Постарайтесь выразить его корректно и не спрашивать слишком интимную информацию.')
					bot.register_next_step_handler(msg, new_forms_question)
				elif query.startswith('my_forms_delete '):
					number = int(query.split()[1])
					coach.delete_question_for_forms(number)
					msg = bot.send_message(coach.chat_id, f'Вопрос №{number} был успешно удален!')
			elif query.startswith('my_forms_answers'):
				menu = InlineKeyboardMarkup(row_width=2)
				answered_questions = coach.questions_form_answered()
				if query == 'my_forms_answers':
					if answered_questions:
						answers = set([(i['users_id']) for i in answered_questions])
						buttons = sorted([InlineKeyboardButton(text=f'👤 {User(user_id=i).fullname}', callback_data=f'my_forms_answers {i}') for i in answers], key=lambda x: x.text)
						menu.add(*buttons, InlineKeyboardButton(text='👈 Назад', callback_data='my_forms'))
						msg = bot.send_message(coach.chat_id, 'Выберите клиента из ответивших на вопрос, чтобы просмотреть ответы.', reply_markup=menu)
					else:
						msg = bot.send_message(coach.chat_id, 'Ответов на вопросы пока не было.')
				elif query.startswith('my_forms_answers '):
					user = User(user_id=query.split()[1])
					form = user.forms()
					lst = '\n\n'.join([f'❓ *Вопрос*: _{i["questions"]}_\n📜 *Ответ*: _{i["answers"]}_\n⏳ *Дата ответа*: _{i["answer_timestamp"]}_' for i in form])
					msg = bot.send_message(coach.chat_id, lst, reply_markup=menu.add(
						InlineKeyboardButton(text='👈 Назад', callback_data='my_forms_answers')
					))


			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)


		if query == 'my_tariffs':
			if not coach.tariffs:
				msg = bot.send_message(coach.chat_id, '☹️ У вас нет ни одного действующего тарифа.\n\n'
												'😃 Нажмите *Конструктор тарифов*, чтобы создать новый!', reply_markup=InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(text='Конструктор тарифов', callback_data='create_tariff')))
				temp_msgs('my_tariffs', coach, msg)
			else:
				msg = bot.send_message(coach.chat_id, '💰 Доступные для клиентов тарифы:\n\n' + '\n\n'.join([f'*{coach.tariffs.index(i) + 1}. {i.name}*:\n- Количество тренировок (всех типов): _{sum([j if j else 0 for j in i.sessions.values()])}_;\n- Срок действия, дней: _{i.period if i.period != 1825 else "бессрочно"}_;\n- Доступное количество отмен: _{i.canceling_amount if i.canceling_amount != 100 else "неограниченное"}_;\n- Стоимость: _{i.cost}₽_.' for i in coach.tariffs])
									   + '\n\n✔️ *Просто щелкните* по названию тарифа, чтобы _просмотреть_ подробную информацию о нем или _внести в него изменения_ (удалить тариф), или нажмите *"Конструктор тарифов"*, чтобы создать новый.',
									   parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(row_width=1).add(*[InlineKeyboardButton(text=i.name, callback_data=f'my_tariff {i.id}') for i in coach.tariffs], InlineKeyboardButton(text='Конструктор тарифов', callback_data='create_tariff')))
				temp_msgs('my_tariffs', coach, msg)
			del_msgs('main_admin', coach)

		if query.startswith('my_tariff') and query != 'my_tariffs':
			tariff = Tariff(tariff_id=query.split()[-1])
			if not query.startswith('my_tariff_change') and not query.startswith('my_tariff_delete'):
				msg = bot.send_message(coach.chat_id, f'📍 *Тариф "{tariff.name}"*\n\n'
													  f'📜 *Описание*:\n_{tariff.description}_\n\n'
													  f'⏳ *Период действия, дней*: _{tariff.period if tariff.period != 1825 else "бессрочно"}_\n\n'
													  f'❌ *Количество отмен*: _{tariff.canceling_amount if tariff.canceling_amount != 100 else "неограниченное"}_\n\n'
													  '🏋️‍♀️ *Тип и количество тренировок*:\n- ' + '\n- '.join([f'{tariff_info()[i]}: _{j}_' for i, j in tariff.sessions.items() if j]) + '\n\n'
														f'👤 *Уровень доступа*:\n- ' + '\n- '.join([f'{tariff_info()[i]}: _{"да" if j else "нет"}_' for i, j in tariff.users_permissions.items()]) + '\n\n'
														f'💰 *Стоимость, рублей*: _{tariff.cost}_',
									   reply_markup=InlineKeyboardMarkup(row_width=1).add(
										   InlineKeyboardButton(text='Изменить тариф', callback_data=f"my_tariff_change {tariff.id}"),
										   InlineKeyboardButton(text='Удалить тариф', callback_data=f"my_tariff_delete {tariff.id}")
									   ))

			elif query.startswith('my_tariff_change'):
				main_buttons = [
					InlineKeyboardButton(text=tariff_info()[i], callback_data=f'my_tariff_change {i} {tariff.id}') for i
					in [j for j in tariff.__dict__ if not j in ['id', 'coachs_id']]]

				current_settings = temp_dct['coaches'][coach.id][
					f"changing_tariff {tariff.id}"] if coach.id in temp_dct['coaches'] and f"changing_tariff {tariff.id}" in \
													   temp_dct['coaches'][coach.id] else tariff.__dict__
				name = current_settings['name'] if 'name' in current_settings else tariff.name
				description = current_settings[
					'description'] if 'description' in current_settings else tariff.description
				period = current_settings['period'] if 'period' in current_settings else tariff.period
				canceling_amount = current_settings[
					'canceling_amount'] if 'canceling_amount' in current_settings else tariff.canceling_amount
				sessions = '\n'.join([f'- {training_types()[i]}: _{j if j else 0}_' for i, j in current_settings[
					'sessions'].items()]) if 'sessions' in current_settings else '\n'.join(
					[f'- {training_types()[i]}: _{j if j else 0}_' for i, j in tariff.sessions.items()])
				users_permissions = '\n'.join([f'- {tariff_info()[i]}: _{"да" if j else "нет"}_' for i, j in
											   current_settings[
												   'users_permissions'].items()]) if 'users_permissions' in current_settings else '\n'.join(
					[f'- {tariff_info()[i]}: _{"да" if j else "нет"}_' for i, j in tariff.users_permissions.items()])
				cost = current_settings['cost'] if 'cost' in current_settings else tariff.cost


				if not query.startswith('my_tariff_change_end '):
					if len(query.split()) == 2:
						msg = bot.send_message(coach.chat_id, 'Выберите параметр, чтобы изменить его.',
											   reply_markup=InlineKeyboardMarkup(row_width=1).add(*main_buttons,
																								  InlineKeyboardButton(text='Завершить', callback_data=f'my_tariff_change_end {tariff.id}')))
					elif len(query.split()) == 3:
						param = query.split()[1]
						dct = {'name': f'Напишите новое название для тарифа *{tariff.name}*.\n\n'
									   f'Текущее название: *"{name}"*.', 'description': f'Напишите новое описание для тарифа *{tariff.name}*.\n\n'
																						f'Текущее описание:\n_{description}_.',
							   'cost': f'Напишите новую стоимость для тарифа *{tariff.name}* в виде _числа_.\n\n'
									   f'Текущая стоимость: *{cost}*.'}
						if not coach.id in temp_dct['coaches']:
							temp_dct['coaches'][coach.id] = {f'changing_tariff {tariff.id}': {param: None}}
						else:
							if not param in temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']:
								temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}'][param] = None
							else:
								if param in ['name', 'description', 'cost']:
									temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}'][param] = None
						if param in dct:
							msg = bot.send_message(coach.chat_id, dct[param])
							bot.register_next_step_handler(msg, change_tariff)
						else:
							if param == 'users_permissions':
								if 'users_permissions' in temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}'] and temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']['users_permissions']:
									perms = temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']['users_permissions']
								else:
									temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']['users_permissions'] = tariff.users_permissions
									perms = tariff.users_permissions
								buttons = [InlineKeyboardButton(text=f'{tariff_info()[i]}: {"да" if perms[i] else "нет"}', callback_data=f'my_tariff_change users_perms {i} {tariff.id}') for i in perms]
								msg = bot.send_message(coach.chat_id, 'Нажмите на пункт меню для клиентов, чтобы разрешить/запретить доступ к нему.',
													   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																										  InlineKeyboardButton(text='Сохранить', callback_data=f'my_tariff_change {tariff.id}')))

							elif param == 'period':
								buttons = [InlineKeyboardButton(text=i, callback_data=f'my_tariff_change period {i} {tariff.id}') for i in [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60]]
								msg = bot.send_message(coach.chat_id,
													   'Выберите срок действия тарифа в количестве дней.\n\n'
													   'Или нажмите *"Бессрочно"*, чтобы установить условный срок действия тарифа величиной в 5 лет.\n\n'
													   f'Текущий срок действия: _{period if period != 1825 else "бессрочно"}_',
													   reply_markup=InlineKeyboardMarkup(row_width=4).add(*buttons,
																										  InlineKeyboardButton(text='Бессрочно', callback_data=f'my_tariff_change period 1825 {tariff.id}')))

							elif param == 'canceling_amount':
								buttons = [InlineKeyboardButton(text=i, callback_data=f'my_tariff_change canceling_amount {i} {tariff.id}') for i in [1,2,3,5,10,15,20]]
								msg = bot.send_message(coach.chat_id, 'Выберите, сколько раз в течение периода тарифа клиент сможет отменить занятие.\n\n'
																	  f'Текущее количество отмен: _{canceling_amount if canceling_amount != 100 else "неограниченное"}_.',
													   reply_markup=InlineKeyboardMarkup(row_width=4).add(*buttons,
																										  InlineKeyboardButton(text='Не ограничивать', callback_data=f'my_tariff_change canceling_amount 100 {tariff.id}'),
																										  InlineKeyboardButton(
																											  text='Без отмены',
																											  callback_data=f'my_tariff_change canceling_amount 0 {tariff.id}')))
							elif param == 'sessions':
								if not 'sessions' in temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"] or not temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions']:
									temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions'] = tariff.sessions
									params = tariff.sessions
								else:
									params = temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions']
								buttons = [InlineKeyboardButton(text=f'{training_types()[i]}: {params[i] if params[i] else 0}', callback_data=f'my_tariff_change sessions {i} {tariff.id}') for i in params]
								msg = bot.send_message(coach.chat_id, f'Выберите тип тренировок, чтобы определить их количество, которое предоставляет тариф *{tariff.name}*.\n\n'
																	  f'Или нажмите "Сохранить", чтобы сохранить изменения.\n\n', parse_mode="Markdown",
													   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons, InlineKeyboardButton(text='Сохранить', callback_data=f'my_tariff_change {tariff.id}')))

					elif len(query.split()) == 4:
						param = query.split()[1]
						if param == 'users_perms':
							perms_param = query.split()[2]
							perms = temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']['users_permissions']
							perms[perms_param] = True if not perms[perms_param] else False
							temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']['users_permissions'] = perms
							buttons = [InlineKeyboardButton(text=f'{tariff_info()[i]}: {"да" if perms[i] else "нет"}',
															callback_data=f'my_tariff_change users_perms {i} {tariff.id}')
									   for i in perms]
							msg = bot.send_message(coach.chat_id,
												   'Нажмите на пункт меню для клиентов, чтобы разрешить/запретить доступ к нему.',
												   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																									  InlineKeyboardButton(
																										  text='Сохранить',
																										  callback_data=f'my_tariff_change {tariff.id}')))

						elif param == 'period':
							period = query.split()[2]
							temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['period'] = period
							msg = bot.send_message(coach.chat_id,
												   f'Параметр *{tariff_info()["period"]}* успешно изменен!',
												   parse_mode='Markdown',
												   reply_markup=InlineKeyboardMarkup(row_width=1).add(*main_buttons,
																									  InlineKeyboardButton(
																										  text='Завершить',
																										  callback_data=f'my_tariff_change_end {tariff.id}')))

						elif param == 'canceling_amount':
							amount = query.split()[2]
							temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['canceling_amount'] = amount
							msg = bot.send_message(coach.chat_id, f'Параметр *{tariff_info()["canceling_amount"]}* успешно изменен!',
											   reply_markup=InlineKeyboardMarkup(row_width=1).add(*main_buttons,
																								  InlineKeyboardButton(text='Завершить', callback_data=f'my_tariff_change_end {tariff.id}')))

						elif param == 'sessions':
							param = query.split()[2]
							if param[-1] == '+':
								if temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions'][param[:-1]]:
									temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions'][param[:-1]] += 1
								else:
									temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions'][param[:-1]] = 1
							elif param[-1] == '-' and amount >= 1:
								temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions'][param[:-1]] -= 1
							param = param[:-1] if param[-1] in ['+', '-'] else param
							amount = temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]['sessions'][param]
							buttons = [InlineKeyboardButton(text=f'{i}1', callback_data=f'my_tariff_change sessions {param}{i} {tariff.id}') for i in ['+', '-']]
							msg = bot.send_message(coach.chat_id, f'Сейчас тренировок типа _{training_types()[param]}_ у тарифа "*{tariff.name}*": _{amount if amount else 0}_\n\n'
																  f'Нажмите *"Сохранить"*, чтобы вернуться к выбору типа тренировок или к редактированию тарифа.', parse_mode="Markdown",
												   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																									  InlineKeyboardButton(text='Сохранить', callback_data=f'my_tariff_change sessions {tariff.id}')))

				else:
					if coach.id in temp_dct['coaches'] and f'changing_tariff {tariff.id}' in temp_dct['coaches'][coach.id]:
						changes = temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"]
						for i in changes:
							if changes[i]:
								if i == 'name':
									tariff.name = changes[i]
								elif i == 'description':
									tariff.description = changes[i]
								elif i == 'cost':
									tariff.cost = changes[i]
								elif i == 'users_permissions':
									tariff.users_permissions = changes[i]
								elif i == 'period':
									tariff.period = changes[i]
								elif i == 'sessions':
									tariff.sessions = changes[i]
								elif i == 'canceling_amount':
									tariff.canceling_amount = changes[i]
						tariff.set()
						temp_dct['coaches'].pop(coach.id, None)
						msg = bot.send_message(coach.chat_id, f'Тариф *{tariff.name}* был успешно изменен!', reply_markup=admin_keyboard())
					else:
						msg = bot.send_message(coach.chat_id, 'Редактирование тарифа отменено.')

			elif query.startswith('my_tariff_delete'):
				tariff = Tariff(query.split()[1])
				if not query.split()[0] in ['my_tariff_delete_exactly', 'my_tariff_delete_no']:
					msg = bot.send_message(coach.chat_id, f'Вы уверены, что хотите удалить тариф *"{tariff.name}"*?\n\n'
														  f'Оплаченное количество тренировок у клиентов сохранится, как и все остальные условия.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(
											   InlineKeyboardButton(text='Да', callback_data=f'my_tariff_delete_exactly {tariff.id}'),
											   InlineKeyboardButton(text='Нет', callback_data=f'my_tariff_delete_no {tariff.id}')
										   ))
				elif query.split()[0] == 'my_tariff_delete_exactly':
					users = tariff.find_users()
					if users:
						for u in users:
							bot.send_message(u.chat_id, f'К сожалению, ваш тариф *{tariff.name}* был удален тренером.\n\n'
														f'Но все его условия, в том числе оплаченные тренировки, продолжают действие!')
					msg = bot.send_message(coach.chat_id, f'Тариф *"{tariff.name}"* успешно удален и более недоступен для приобретения клиентам.')
					tariff.delete()
				elif query.split()[0] == 'my_tariff_delete_no':
					msg = bot.send_message(coach.chat_id, 'Удаление тарифа отменено.')

			del_msgs('my_tariffs', coach)
			temp_msgs('my_tariffs', coach, msg)




		if query == 'create_tariff':
			coach = Coach(callback.message.chat.id)
			if os.path.exists(f'create_tariff {coach.id}.json'):
				remove(f'create_tariff {coach.id}.json')
			msg = bot.send_message(coach.chat_id, '*Введите название* нового тарифа. Оно _должно отражать суть_ его условий (хотя бы косвенно), чтобы сделать ассоциацию для клиента более доступной.\n\nДля отмены ввода введите *"Q"*.')
			bot.register_next_step_handler(msg, create_tariff)
			del_msgs('my_tariffs', coach)
			temp_msgs('my_tariffs', coach, msg)

		if query.startswith('new_t'):
			sessions_types = {'personal': 'персональные', 'split': 'сплит', 'group': 'групповые', 'personal_online': 'персональные онлайн', 'free': 'бесплатные (пробные)'}
			coach = Coach(callback.message.chat.id)
			new_tariff = load(open(f'create_tariff {coach.id}.json', encoding='utf-8'))
			users_permissions = {
				"individual_trainings": 'Индивидуальные тренировки',
				"self_trainings": "Самостоятельные тренировки",
				"my_diet": "Моя диета"
			}

			if query.startswith('new_t_sessions'):
				sessions_type = query.split()[1]
				if coach.working_schedule_training_types()[sessions_type] > 0:
					buttons = InlineKeyboardMarkup(row_width=1).add(*[InlineKeyboardButton(text=f'{sessions_types[sessions_type]} +', callback_data=f'set_new_t_sessions {sessions_type} +'), InlineKeyboardButton(text=f'{sessions_types[sessions_type]} -', callback_data=f'set_new_t_sessions {sessions_type} -')],
																	InlineKeyboardButton(text='👈 Назад', callback_data='set_new_t_sessions'))

					msg = bot.send_message(coach.chat_id, f'Сейчас тариф "*{new_tariff["name"]}*" включает в себя тренировки типа *{sessions_types[sessions_type].lower()}* в количестве: _{new_tariff["sessions"][sessions_type] if new_tariff["sessions"][sessions_type] else 0}_.\n\n'
													f'Выберите, прибавить или отнять одну тренировку или нажмите *"Назад"* для выбора типа занятий или продолжения составления тарифа.', reply_markup=buttons)
					del_msgs('my_tariffs', coach)
				else:
					msg = bot.send_message(coach.chat_id, f'Тариф не может включать тренировки типа _{sessions_types[sessions_type]}_ - у вас нет свободных часов для этого типа в рабочем расписании!\n'
														  f'Сначала обновите расписание, а затем возвращайтесь к созданию тарифа.')

				temp_msgs('my_tariffs', coach, msg)

			elif query.startswith('new_t_period '):
				if query.split()[1] == 'alltime':
					new_tariff['period'] = 1825
				else:
					period_amount = int(query.split()[1])
					new_tariff['period'] = period_amount
				dump(new_tariff, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)

				msg = bot.send_message(coach.chat_id,
									   '*Какова будет стоимость* нового тарифа в рублях? Введите в виде _числа_.',
									   parse_mode='Markdown')
				bot.register_next_step_handler(msg, create_tariff)
				del_msgs('my_tariffs', coach)
				temp_msgs('my_tariffs', coach, msg)

			elif query.startswith('new_t_canceling '):
				if query.split()[1] == 'infinity':
					new_tariff['canceling_amount'] = 100
				elif query.split()[1] == 'is_none':
					new_tariff['canceling_amount'] = 0
				else:
					canceling_amount = int(query.split()[1])
					new_tariff['canceling_amount'] = canceling_amount
				dump(new_tariff, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
				new_tariff = load(open(f'create_tariff {coach.id}.json', encoding='utf-8'))  # refreshing
				buttons = InlineKeyboardMarkup(row_width=1).add(*[InlineKeyboardButton(
					text=f'{users_permissions[i]}: {"да" if new_tariff["users_permissions"][i] else "нет"}',
					callback_data=f'new_t_permissions {i}') for i in new_tariff['users_permissions']], InlineKeyboardButton(text='Подробная информация', callback_data='new_t_permissions_info'))

				msg = bot.send_message(coach.chat_id, '*Определите уровень доступа* для пользователя к основным функциям меню *"Мои тренировки"*, которые будут предоставляться клиенту _после оплаты тарифа_.\n\n'
												'Чтобы подробнее узнать про каждый из пунктов меню с точки зрения пользователя, нажмите *"Подробная информация"*.', reply_markup=buttons)
				del_msgs('my_tariffs', coach)
				temp_msgs('my_tariffs', coach, msg)

			elif query.startswith('new_t_permissions'):
				new_tariff = load(open(f'create_tariff {coach.id}.json', encoding='utf-8')) # refreshing

				if query == 'new_t_permissions_info':
					buttons = InlineKeyboardMarkup(row_width=1).add(*[InlineKeyboardButton(
						text=f'{users_permissions[i]}: {"да" if new_tariff["users_permissions"][i] else "нет"}',
						callback_data=f'new_t_permissions {i}') for i in new_tariff['users_permissions']],
																	InlineKeyboardButton(text='Подробная информация',
																						 callback_data='new_t_permissions_info'),
																	InlineKeyboardButton(text='Закончить',
																						 callback_data=f'new_t_permissions_end'))
					splitted_text = util.smart_split(open('data/specs/help/online_training/my_training.txt', encoding='utf-8').read(), 4000)
					for i in splitted_text:
						msg = bot.send_message(coach.chat_id, i)
						temp_msgs('my_tariffs', coach, msg)

					msg = bot.send_message(coach.chat_id,
									 '*Определите уровень доступа* для пользователя к основным функциям меню *"Мои тренировки"*, который будет предоставляться клиенту _после оплаты тарифа_.\n\n',
									 parse_mode='Markdown', reply_markup=buttons)
					del_msgs('my_tariffs', coach)
					temp_msgs('my_tariffs', coach, msg)
				elif query == 'new_t_permissions_end':

					msg = bot.send_message(coach.chat_id, 'Коротко, но емко опишите условия созданного тарифа. Просто отправьте их в виде сообщения.\n'
													'Они должны быть понятны клиенту, а также содержать в себе прямую или косвенную информацию о тарифе.\n\n'
													'Все выбранные до текущего шага параметры тарифа перечислять не нужно - бот сообщит их самостоятельно при покупке тарифа клиентом.')
					bot.register_next_step_handler(msg, create_tariff)
					del_msgs('my_tariffs', coach)
					temp_msgs('my_tariffs', coach, msg)
				else:
					new_tariff = load(open(f'create_tariff {coach.id}.json', encoding='utf-8'))  # refreshing
					permission = query.split()[1]
					new_tariff['users_permissions'][permission] = True if not new_tariff['users_permissions'][permission] else False
					dump(new_tariff, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
					buttons = InlineKeyboardMarkup(row_width=1).add(*[InlineKeyboardButton(
						text=f'{users_permissions[i]}: {"да" if new_tariff["users_permissions"][i] else "нет"}',
						callback_data=f'new_t_permissions {i}') for i in new_tariff['users_permissions']],
																	InlineKeyboardButton(text='Подробная информация',
																						 callback_data='new_t_permissions_info'),
																	InlineKeyboardButton(text='Закончить',
																						 callback_data=f'new_t_permissions_end'))

					msg = bot.send_message(coach.chat_id,
									 '*Определите уровень доступа* для пользователя к основным функциям меню *"Мои тренировки"*, которые будут предоставляться клиенту _после оплаты тарифа_.\n\n'
									 'Чтобы подробнее узнать про каждый из пунктов меню с точки зрения пользователя, нажмите *"Подробная информация"*.',
									 parse_mode='Markdown', reply_markup=buttons)
					del_msgs('my_tariffs', coach)
					temp_msgs('my_tariffs', coach, msg)


		if query.startswith('set_new_t_sessions'):
			coach = Coach(callback.message.chat.id)
			new_tariff = load(open(f'create_tariff {coach.id}.json', encoding='utf-8'))
			sessions_types = {'personal': 'Персональные тренировки', 'split': 'Сплит-тренировки',
							  'group': 'Групповые тренировки',
							  'personal_online': 'Персональные онлайн-тренировки'}
			if query == 'set_new_t_sessions':
				buttons = [InlineKeyboardButton(
					text=f'{sessions_types[i]}: {new_tariff["sessions"][i] if new_tariff["sessions"][i] else 0}',
					callback_data=f'new_t_sessions {i}') for i in new_tariff['sessions']]

				msg = bot.send_message(coach.chat_id,
								 '*Выберите*, _какие тренировки и в каком количестве_ будет предоставлять клиенту оплаченный тариф.\n'
								 '*Чтобы тариф не включал* в себя тренировки (например, для исключительно онлайн-работы с клиентом посредством функций бота), вы можете *оставить* количество тренировок каждого типа _в размере 0_.\n'
								 'Когда все будет готово, нажмите *"Закончить"*.\n\n'
								 f'- *Персональные тренировки*: 1 клиент в час;\n'
								 f'- *Сплит-тренировки*: до 3 клиентов в час;\n'
								 f'- *Групповые тренировки*: неограниченное количество клиентов в час;\n'
								 f'- *Персональные онлайн-тренировки*: один человек в час в режиме онлайн (видеосвязь).\n\n',
								 parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons, InlineKeyboardButton(text='Закончить', callback_data='set_new_t_sessions_end')))
				del_msgs('my_tariffs', coach)
				temp_msgs('my_tariffs', coach, msg)
			elif query.startswith('set_new_t_sessions '):
				operation = query.split()[-1]
				sessions_type = query.split()[1]
				if operation == '+':
					try:
						new_tariff['sessions'][sessions_type] += 1
					except TypeError:
						new_tariff['sessions'][sessions_type] = 1
				elif operation == '-' and new_tariff['sessions'][sessions_type] and new_tariff['sessions'][sessions_type] >= 1:
					new_tariff['sessions'][sessions_type] -= 1
				dump(new_tariff, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
				buttons = InlineKeyboardMarkup(row_width=1).add(*[
					InlineKeyboardButton(text=f'{sessions_types[sessions_type]} +',
										 callback_data=f'set_new_t_sessions {sessions_type} +'),
					InlineKeyboardButton(text=f'{sessions_types[sessions_type]} -',
										 callback_data=f'set_new_t_sessions {sessions_type} -')],
																InlineKeyboardButton(text='👈 Назад', callback_data='set_new_t_sessions'))

				msg = bot.send_message(coach.chat_id,
								 f'Сейчас тариф "*{new_tariff["name"]}*" включает в себя тренировки типа *{sessions_types[sessions_type].lower()}* в количестве: _{new_tariff["sessions"][sessions_type] if new_tariff["sessions"][sessions_type] else 0}_.\n\n'
								 f'Выберите, прибавить или отнять одну тренировку или нажмите *"Назад"* для выбора типа занятий или продолжения составления тарифа.',
								 parse_mode='Markdown', reply_markup=buttons)
				del_msgs('my_tariffs', coach)
				temp_msgs('my_tariffs', coach, msg)

			if query == 'set_new_t_sessions_end':
				coach = Coach(callback.message.chat.id)
				buttons = InlineKeyboardMarkup(row_width=5).add(*[InlineKeyboardButton(text=i, callback_data=f'new_t_period {i}') for i in [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60]], InlineKeyboardButton(text='Бессрочно', callback_data='new_t_period alltime'))

				msg = bot.send_message(coach.chat_id, '*Сколько дней* будет длиться новый тариф? *Выберите* количество дней или нажмите *"Бессрочно"*, чтобы тариф имел условно неограниченную продолжительность величиной в год (оплаченные занятия, вероятнее всего, закончатся раньше).\n\n'
						  'Если у клиента уже _есть действующий_ период данного тарифа, _он будет увеличиваться_ на срок вновь оплаченного.\n'
						  'Если у клиента _уже действует период другого тарифа_, он будет _обнулен_ после оплаты нового.', reply_markup=buttons)
				del_msgs('my_tariffs', coach)
				temp_msgs('my_tariffs', coach, msg)


		if query == 'coach_tasks':
			if coach.tasks:
				text = coach.tasks_description()
			else:
				text = 'Нет текущих задач.'

			msg = bot.send_message(coach.chat_id, text)

			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)

		# _____________________________________________________
		# USER FUNCS

		if query.startswith('free_trainings'):
			bot.send_message(user.chat_id, 'К сожалению, этот раздел еще в разработке.')
			del_msgs('my_trainings', user)


		if query.startswith('my_coach'):
			current_coach = user.coach()
			if query == 'my_coach':
				td = user.total_time_with_coach()
				# оценить тренера можно только спустя 30 дней работы с ним
				total_time_check = td > timedelta(days=30)
				text = current_coach.working_description() + f'\n\n💪 Вы с тренером уже ' + (f'*{round(td.days / 30)} мес., {round(td.days % 30)} дн.*' if td.days/30 > 0 else f'*{td.days} дн.*') + '\n\n' + \
															('❗️ Оценить тренера можно будет только после работы с ним в течение 30 дней!' if not total_time_check else '')
				msg = bot.send_photo(user.chat_id, current_coach.photo, caption=f'Тренер: {current_coach.fullname}')
				temp_msgs('choose_coach_photo', user, msg)
				menu = InlineKeyboardMarkup(row_width=1)
				try:
					coach_rating_from_user = next(filter(lambda x: x['users_id'] == user.id and all([x['rating'],
																					  x['work_results'],
																					  x['responsibility']]), current_coach.rating(raw=True)))
				except StopIteration:
					coach_rating_from_user = None

				if coach_rating_from_user is None and total_time_check:
					menu.add(InlineKeyboardButton(text='Оценить тренера', callback_data='my_coach_rate'))
				msg = bot.send_message(user.chat_id, text,
									 reply_markup=menu.add(
										 InlineKeyboardButton(text='Сменить тренера', callback_data='choose_coach')
									 ))
			elif query.startswith('my_coach_rate'):
				try:
					if len(query.split()) == 2:
						score = query.split()[1]
						params = temp_dct['users'][user.id]['coach_rating']
						for i in params:
							if not params[i]:
								params[i] = score
								break
						temp_dct['users'][user.id]['coach_rating'] = params
					params = temp_dct['users'][user.id]['coach_rating']
				except KeyError:
					temp_dct['users'][user.id] = {'coach_rating': {
						'rating': None,
						'work_results': None,
						'responsibility': None
					}}
					params = temp_dct['users'][user.id]['coach_rating']

				param = None
				for i in params:
					if not params[i]:
						param = i
						break


				types = {
					"rating": f"Сделайте общую оценку для тренера *{current_coach.fullname}* от 1 до 5.",
					"work_results": f"Оцените результаты работы с тренером.\n\nНасколько по шкале от 1 до 5 он помог/помогает достичь ваших целей?",
					"responsibility": f"Оцените ответственность тренера по отношению к его работе (насколько быстро выполняет задачи, отправляет задания, опаздывает ли...)."
				}

				if param:
					menu = InlineKeyboardMarkup(row_width=5).add(*[InlineKeyboardButton(text=i, callback_data=f'my_coach_rate {i}') for i in range(1, 6)])
					msg = bot.send_message(user.chat_id, types[param], reply_markup=menu)
				else:
					current_coach.rating(user=user, dct=temp_dct['users'][user.id]['coach_rating'])
					temp_dct['users'].pop(user.id, None)
					msg = bot.send_message(user.chat_id, 'Спасибо за оценку! Она была успешно сохранена.')

			del_msgs('choosing_coach', user)
			temp_msgs('choosing_coach', user, msg)


		if query.startswith('choose_coach'):
			if user.current_coach_id:
				current_coach = user.coach()
				try:
					coach_rating_from_user = next(filter(lambda x: x['users_id'] == user.id and all([x['rating'],
																					  x['work_results'],
																					  x['responsibility']]), current_coach.rating(raw=True)))
				except StopIteration:
					coach_rating_from_user = None
				# оценить тренера можно только спустя 30 дней работы с ним
				total_time_check = user.total_time_with_coach() > timedelta(days=30)
				if coach_rating_from_user is None and total_time_check:
					msg = bot.send_message(user.chat_id, "Чтобы выбрать нового тренера, нужно сначала оценить текущего.",
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(
											   InlineKeyboardButton(text='Оценить тренера', callback_data='my_coach_rate')
										   ))
				else:
					user.subscription_plan = {
						'tariff_id': None,
						'sessions_count': {
											'personal': None,
											'split': None,
											'group': None,
											'personal_online': None,
											'free': None
										},
						'canceled_sessions': None,
						'period': None,
						'start_timestamp': None
					}

					if user.upcoming_sessions():
						user.cancel_all_sessions()
					user_coach = user.coach()
					user.current_coach_id = None
					user.training_levels_id = None
					user.tasks = None
					user.set_user(subscription_plan=True)
					with database() as connection:
						with connection.cursor() as db:
							db.execute(f"UPDATE coachs_feedbacks SET cooperation_end_day = CURDATE() WHERE coachs_id = {user_coach.id} AND users_id = {user.id}")
						connection.commit()

					bot.send_message(user_coach.chat_id,
									 f'К сожалению, клиент *{user.fullname}* прекратил работу с вами.')
					msg = bot.send_message(user.chat_id, "Текущий тренер был сброшен.\n"
														 'Нажмите *"Выбрать тренера"*, чтобы выбрать нового.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(
											   InlineKeyboardButton(text='Выбрать тренера', callback_data='choose_coach')
										   ))
				del_msgs('choosing_coach', user)
				temp_msgs('choosing_coach', user, msg)

			else:
				forms = Coach.get_all_coaches(forms=True)
				additional_params = {'sex': {'vars': {'male': 'Мужчина', 'female': "Женщина"},
											 'msg': 'Выберите желаемый пол тренера.'},
									 'city': {'vars': set(sorted([i['city'] for i in forms])),
											  'msg': 'Выберите предпочитаемый город из доступных'},
									 'age': {'vars': {i: range(int(i[:2]), int(i[-2:]) + 1) for i in ['18-25', '25-30', '30-35', '35-40', '40-65']},
											 'msg': 'Выберите примерный предпочитаемый возраст тренера.'}}
				try:
					general_msg = temp_dct['users'][user.id]['choosing_coach']['msg']
				except KeyError:
					pass
				types = {'online': 'Онлайн', 'offline': 'Оффлайн (очно)',
						 'sex': 'Пол', 'city': 'Город', 'male': 'Мужчина', 'female': 'Женщина',
						 'age': 'Возраст'}
				if query == 'choose_coach':
					del_msgs('my_trainings', user)
					buttons = [InlineKeyboardButton(text=types[i], callback_data=f'choose_coach_type {i}') for i in ['online', 'offline']]
					msg = bot.send_message(user.chat_id, f'Выберите предпочитаемый режим работы с тренером.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons))

				elif query.startswith('choose_coach_type '):
					item = query.split()[1]
					temp_dct['users'][user.id] = {'choosing_coach': {'type': item,
															'tags': [],
															'city': None,
															'age': None,
															'sex': None}}
					buttons = [InlineKeyboardButton(text=i, callback_data=f'choose_coach_t {i}') for i in coaches_disciplines() if not i in temp_dct['users'][user.id]['choosing_coach']['tags']]
					msg = bot.send_message(user.chat_id, '*Выберите направление* работы тренера, которое вас интересует.\n\n'
														 'Выбрать можно до *5 направлений одновременно*, минимум - *3*.', reply_markup=InlineKeyboardMarkup(row_width=3).add(*buttons))

				elif query.startswith('choose_coach_t'):
					tag = ' '.join(query.split()[1:])
					current_tags = temp_dct['users'][user.id]['choosing_coach']['tags']
					temp_dct['users'][user.id]['choosing_coach']['tags'].append(tag)
					menu = InlineKeyboardMarkup(row_width=3).add(*[InlineKeyboardButton(text=i, callback_data=f'choose_coach_t {i}') for i in
									   coaches_disciplines() if not i in current_tags])
					if len(current_tags) < 5:
						if len(current_tags) >= 3:
							menu.add(InlineKeyboardButton(text='Продолжить', callback_data='choose_coach_additional_params'))
						msg = bot.send_message(user.chat_id,
											   '*Выберите направление* работы тренера, которое вас интересует.\n\n'
											   'Выбрать можно до *5 направлений одновременно*, минимум - *3*.\n\n' + 'Нажмите *"Продолжить"*, если хотите закончить выбор тегов.',
											   reply_markup=menu)
						def msg_func():
							tags = temp_dct['users'][user.id]['choosing_coach']['tags']
							type = temp_dct['users'][user.id]['choosing_coach']['type']
							sex, age, city = temp_dct['users'][user.id]['choosing_coach']['sex'], temp_dct['users'][user.id]['choosing_coach']['age'], temp_dct['users'][user.id]['choosing_coach']['city']
							buttons = [InlineKeyboardButton(text=types[i], callback_data=f'choose_coach {i}') for i in additional_params]
							return bot.send_message(user.chat_id, '*Текущие выбранные параметры*\n\n' + f'*Режим работы тренера*: _{types[type].lower()}_\n'
																																		  f'*Направления работы*: _{", ".join(sorted(tags))}_\n'
																																		  f'*Город*: _{city if city else "не выбран"}_\n'
																																		  f'*Пол*: _{types[sex] if sex else "не выбран"}_\n'
																																		  f'*Возраст*: _{[i for i in additional_params["age"]["vars"] if additional_params["age"]["vars"][i] == age][0] if age else "не выбран"}_\n\n'
																																		  f'*Выберите дополнительный параметр* для уточнения, если нужно. Если выбор будет закончен, нажмите *"Готово"*.',
													reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																									   InlineKeyboardButton(text='Готово', callback_data='choose_coach_end')))
						temp_dct['users'][user.id]['choosing_coach']['msg'] = msg_func
					else:
						msg = general_msg()

				elif query.startswith('choose_coach_additional_params'):
					msg = general_msg()

				# additional params
				elif len(query.split()) in [2, 3] and query.split()[1] in additional_params:
					param = query.split()[1]
					if len(query.split()) == 2:
						if param != 'age':
							msg = bot.send_message(user.chat_id, additional_params[param]['msg'], reply_markup=InlineKeyboardMarkup(row_width=1).add(
								*[InlineKeyboardButton(text=types[i] if i in types else i, callback_data=f'choose_coach {param} {i}') for i in additional_params[param]['vars']]
							))
						elif param == 'age':
							today = date.today()
							lst = set([(today.year - i['birthday'].year) - ((today.month, today.day) < (i['birthday'].month, i['birthday'].day)) for i in forms])
							result = []
							base = additional_params[param]['vars']
							for i in base:
								for j in lst:
									if j in base[i]:
										result.append({i: base[i]})
							buttons = [InlineKeyboardButton(text=list(i.keys())[0], callback_data=f'choose_coach {param} {list(i.keys())[0]}') for i in sorted(result, key=lambda x: int(list(x.keys())[0][:2]))]
							msg = bot.send_message(user.chat_id, additional_params[param]['msg'], reply_markup=InlineKeyboardMarkup(row_width=1).add(*set(buttons)))

					if len(query.split()) == 3:
						item = query.split()[2]
						temp_dct['users'][user.id]['choosing_coach'][param] = item if param != 'age' else additional_params['age']['vars'][item]
						msg = general_msg()

				elif query == 'choose_coach_main_page':
					msg = general_msg()


				elif query == 'choose_coach_end':
					coaches = Coach.get_all_coaches()
					tags = temp_dct['users'][user.id]['choosing_coach']['tags']
					type = temp_dct['users'][user.id]['choosing_coach']['type']
					sex, age, city = temp_dct['users'][user.id]['choosing_coach']['sex'], temp_dct['users'][user.id]['choosing_coach'][
						'age'], temp_dct['users'][user.id]['choosing_coach']['city']

					lst = []

					for c in coaches:
						tags_flag, type_flag = False, False
						form = c.form()
						for j in tags:
							if j in c.tags:
								tags_flag = True
								break
						if type in form['working_type'].split(';'):
							type_flag = True

						if tags_flag and type_flag:
							lst.append(c)

					if sex:
						for c in lst:
							form = c.form()
							if form['sex'] == sex:
								continue
							else:
								lst.remove(c)
					if age:
						for c in lst:
							birthday = c.form()['birthday']
							today = date.today()
							current_age = (today.year - birthday.year) - ((today.month, today.day) < (birthday.month, birthday.day))
							if current_age in age:
								continue
							else:
								lst.remove(c)

					if city:
						for c in lst:
							form = c.form()
							if form['city'] == city:
								continue
							else:
								lst.remove(c)

					result = []

					if lst:
						for c in sorted(lst, key=lambda x: x.fullname):
							form = c.form()
							result.append(f'👤 *{c.fullname}*\n*Режим работы*: _{", ".join([types[i].lower() for i in form["working_type"].split(";")])}_\n*Направления работы*: _{", ".join(sorted(c.tags))}_\n*Город*: _{form["city"]}_\n*Рейтинг*:\n{c.rating(output=True)}')
						text = '\n---------------'.join(result) + '\n\nВыберите нужного тренера, чтобы просмотреть подробную информацию по нему. Или нажмите *"👈 Параметры поиска"*, чтобы изменить параметры.'
					if not lst:
						for c in coaches:
							form = c.form()
							if type in form['working_type'].split(';'):
								lst.append(c)
								for j in tags:
									if j in c.tags:
										lst.append(c)
						lst = set(lst)
						for c in sorted(lst, key=lambda x: x.fullname):
							form = c.form()
							result.append(f'👤 *{c.fullname}*\n*Режим работы*: _{", ".join([types[i].lower() for i in form["working_type"].split(";")])}_\n*Направления работы*: _{", ".join(sorted(c.tags))}_\n*Город*: _{form["city"]}_\n*Рейтинг*:\n{c.rating(output=True)}')
						text = '\n---------------'.join(result) + '\n\nК сожалению, по выбранным параметрам тренеры не найдены.\n' \
																  'Вам представлены тренеры по указанным параметрам *"Направления работы"*/*"Режим работы"*.\n\n' \
																  'Выберите нужного тренера, чтобы просмотреть подробную информацию по нему. Или нажмите *"👈 Параметры поиска"*, чтобы изменить параметры.'

					buttons = [InlineKeyboardButton(text=i.fullname, callback_data=f'choose_coach current_coach {i.id}') for i in sorted(lst, key=lambda x: x.fullname)]
					msg = bot.send_message(user.chat_id, text,
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																							  InlineKeyboardButton(text='👈 Параметры поиска', callback_data='choose_coach_main_page')))

				elif query.startswith('choose_coach current_coach'):
					if query.split()[2] != 'confirm':
						c_coach = Coach(coach_id=query.split()[2])
						form = c_coach.form()
						buttons = [InlineKeyboardButton(text='✔️ Выбор сделан!', callback_data=f'choose_coach current_coach confirm {c_coach.id}'),
								   InlineKeyboardButton(text='👈 Назад к списку', callback_data=f'choose_coach_end')]
						msg = bot.send_photo(user.chat_id, c_coach.photo, caption=f'Тренер: {c_coach.fullname}')
						temp_msgs('choosing_coach_photo', user, msg)
						msg = bot.send_message(user.chat_id, c_coach.working_description(), reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons))
					else:
						c_coach = Coach(coach_id=query.split()[3])
						user.current_coach_id = c_coach.id
						user.subscription_plan['sessions_count']['free'] = 1
						user.set_user(subscription_plan=True)
						with database() as connection:
							with connection.cursor() as db:
								db.execute(f"INSERT INTO coachs_feedbacks (coachs_id, users_id, cooperation_start_day) VALUES ({c_coach.id}, {user.id}, '{datetime.strftime(datetime.today(), '%Y-%m-%d')}')")
								connection.commit()
								if not user.notifications():
									db.execute(f"INSERT INTO bot_funcs (users_id, reminding_before_sessions, reminding_left_sessions, "
											   f"reminding_today_session, reminding_current_tasks) VALUES ({user.id}, 1, {True}, {True}, {True})")
									connection.commit()
						msg = bot.send_message(user.chat_id, f'Поздравляем! Вы успешно выбрали тренера *{c_coach.fullname}*.\n\n'
															 f'Теперь вы можете:\n'
															 f'- Записаться на первую бесплатную пробную тренировку к тренеру (если есть возможность посетить и желание) через меню *"Запись"*.'
															 f'- Оплатить тренировки с тренером в меню *"Оплата"*;\n'
															 f'- Организовать полноценный тренировочный процесс под контролем данного специалиста через меню *"Мои тренировки"*;\n'
															 f'- Ознакомиться с результатами других подопечных тренера в меню *"Результаты"*.', reply_markup=keyboard(user))
						del_msgs('choosing_coach_photo', user)

						bot.send_message(c_coach.chat_id, f'Поздравляем! У вас новый клиент!\n\n'
														  f'*Полное имя*: _{user.fullname}_\n\n'
														  f'*Интересы*: _{", ".join(sorted(temp_dct["users"][user.id]["choosing_coach"]["tags"]))}_\n\n'
														  f'*Предпочитаемый режим работы с тренером*: _{types[temp_dct["users"][user.id]["choosing_coach"]["type"]].lower()}_\n\n'
														  f'Теперь он добавлен в список ваших клиентов в меню *"Клиенты"* и может использовать весь функционал бота, включая оплату тарифов, запись на занятия и организацию тренировочного процесса под вашим контролем!\n\n'
														  f'Также клиенту доступна одна бесплатная пробная тренировка с вами, на которую он запишется, если собирается посещать очные тренировки.')
						temp_dct['users'].pop(user.id, None)

				del_msgs('choosing_coach', user)
				temp_msgs('choosing_coach', user, msg)



		if query.startswith('individual_trainings'):
			menu = InlineKeyboardMarkup(row_width=1)
			current_tasks = [task for task in user.tasks if not user.tasks is None and task.type_number == 1]
			if query == 'individual_trainings':
				buttons = [
					InlineKeyboardButton(text='📍 История тренировок', callback_data='individual_trainings_history')
				]
				text = '*История тренировок* - просмотреть историю индивидуальных тренировок по полученным заданиям от тренера.'

				if not current_tasks is None and current_tasks:
					buttons.append(InlineKeyboardButton(text='🏃 Текущие задания', callback_data='individual_trainings_tasks'))
					text += '\n\n*Текущие задания* - просмотреть текущие задания, выполнить их, отчитаться после.'

				if current_tasks is None or not current_tasks:
					buttons.append(InlineKeyboardButton(text='❔ Запросить задание', callback_data=f'individual_trainings_request'))
					text += '\n\n*Запросить задание* - запросить новое индивидуальное задание от тренера (функция доступна только когда нет текущих заданий без отчета!).'

				if user.training_reports(reports_type='individual'):
					buttons.append(InlineKeyboardButton(text='📜 Мои отчеты', callback_data=f'individual_trainings_reports'))
					text += f'\n\n*Мои отчеты* - просмотреть историю ваших отчетов по выполнению индивидуальных заданий от тренера.'

				menu.add(*buttons)

				msg = bot.send_message(user.chat_id, text, reply_markup=menu)
				del_msgs('my_trainings', user)
				temp_msgs('my_trainings', user, msg)

			elif query.startswith('individual_trainings_reports'):
				splitted = query.split()
				menu = InlineKeyboardMarkup(row_width=1)
				dct = {'video': 'Видео', 'text': 'Текстовые'}
				if len(splitted) == 1:
					reports_types = set([i['report_type'] for i in user.training_reports(reports_type='individual')])
					buttons = sorted([InlineKeyboardButton(text=dct[i],
													callback_data=f'individual_trainings_reports {i}')
							   for i in reports_types], key=lambda buttn: buttn.text) + \
							  [InlineKeyboardButton(text='👈 Назад', callback_data=f'individual_trainings')]
					msg = bot.send_message(user.chat_id, 'Выберите тип отчетов.', reply_markup=menu.add(*buttons))
					del_msgs('report_view', user)
					del_msgs('my_trainings', user)
					temp_msgs('my_trainings', user, msg)
				elif len(splitted) == 2:
					reports_type = splitted[1]
					reports = filter(lambda x: x['report_type'] == reports_type,
									 user.training_reports(reports_type='individual'))
					buttons = [InlineKeyboardButton(text=i,
													callback_data=f'individual_trainings_reports {reports_type} {i}')
							   for i in set([i.year for i in [j['report_date'] for j in reports]])] + \
							  [InlineKeyboardButton(text='👈 Назад',
													callback_data=f'individual_trainings_reports')]
					msg = bot.send_message(user.chat_id,
										   f'Выберите год тренировок (тип отчетов _{dct[reports_type].lower()}_)',
										   reply_markup=menu.add(*buttons))
					del_msgs('report_view', user)
					del_msgs('my_trainings', user)
					temp_msgs('my_trainings', user, msg)
				elif len(splitted) == 3:
					year, reports_type = splitted[2], splitted[1]
					reports = [i['report_date'].month for i in user.training_reports(reports_type='individual') if
							   i['report_date'].year == int(year) and
							   i["report_type"] == reports_type]
					buttons = [InlineKeyboardButton(text=months[i].title(),
													callback_data=f'individual_trainings_reports {reports_type} {year} {i + 1}')
							   for i in range(12) if i + 1 in reports] + \
							  [InlineKeyboardButton(text='👈 Назад',
													callback_data=f'individual_trainings_reports {reports_type}')]
					menu.row_width = 5
					msg = bot.send_message(user.chat_id,
										   f'Выберите месяц тренировок ({year} год, тип отчетов _{dct[reports_type].lower()}_).',
										   reply_markup=menu.add(*buttons))
					del_msgs('report_view', user)
					del_msgs('my_trainings', user)
					temp_msgs('my_trainings', user, msg)
				elif len(splitted) == 4:
					year, month, reports_type = int(splitted[2]), int(splitted[3]), splitted[1]
					reports = [TrainingReport(user, i) for i in
							   [j['report_date'] for j in user.training_reports(reports_type='individual') if
								j['report_date'].year == year and j['report_date'].month == month and j[
									'report_type'] == reports_type]]
					text = f"*Отчеты типа* _{dct[reports_type].lower()}_, *{months[month - 1].title()} {year}*\n\n" + '\n\n'.join(
						[report.description() for report in reports]) + \
						   (
							   '\n\nНажмите на кнопку с датой отчета, чтобы просмотреть отчетное видео.' if reports_type == 'video' else '')
					if reports_type == 'video':
						buttons = [InlineKeyboardButton(text=f'🎥 {str(i.datetime)[:-3]}',
														callback_data=f'individual_trainings_reports {reports_type} {year} {month} {reports.index(i)}')
								   for i in reports] + \
								  [InlineKeyboardButton(text='👈 Назад',
														callback_data=f'individual_trainings_reports {reports_type} {year}')]
						menu.row_width = 3

					msg = None
					del_msgs('my_trainings', user)
					if len(text) < 3500:
						msg_2 = bot.send_message(user.chat_id, text, reply_markup=menu.add(
							*buttons)) if reports_type == 'video' else bot.send_message(user.chat_id, text, reply_markup=
																						menu.add(
																							InlineKeyboardButton(
																								text='👈 Назад',
																								callback_data=f'individual_trainings_reports {reports_type} {year}')
																						))
						temp_msgs('report_view', user, msg_2)
					else:
						splitted_text = util.smart_split(text, 3500)
						for i in splitted_text:
							if i != splitted_text[-1]:
								msg_2 = bot.send_message(user.chat_id, i)
							else:
								msg_2 = bot.send_message(user.chat_id, i, reply_markup=menu.add(
									*buttons)) if reports_type == 'video' else bot.send_message(user.chat_id, i, InlineKeyboardButton(text='👈 Назад',
														callback_data=f'individual_trainings_reports {reports_type} {year}'))
							temp_msgs('report_view', user, msg_2)

					temp_msgs('report_view', user, msg_2)
				elif len(splitted) == 5:
					year, month, idx, reports_type = int(splitted[2]), int(splitted[3]), int(splitted[4]), splitted[1]
					reports = [TrainingReport(user, i) for i in
							   [j['report_date'] for j in user.training_reports(reports_type='individual') if
								j['report_date'].year == year and j['report_date'].month == month and j['report_type'] == reports_type]]
					report_video_id = reports[idx].content
					msg = None
					msg_2 = bot.send_video(user.chat_id, report_video_id)
					temp_msgs('report_view', user, msg_2)

			elif query == 'individual_trainings_request':
				coach = user.coach()
				individual_training_plan_coach(coach, user, 'send_plan')
				bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* нуждается в индивидуальном задании для проведения тренировок!\n'
												f'Отправьте задание как можно скорее.\n\n'
												f'Ваши текущие задачи были обновлены.')
				msg = bot.send_message(user.chat_id, f'Индивидуальный план для занятий успешно запрошен!\n\n'
													 f'Ожидайте его получения.')
				del_msgs('my_trainings', user)
				temp_msgs('my_trainings', user, msg)

			elif query == 'individual_trainings_history':
				history = user.self_trainings_history('individual', 'user')
				if history:
					with open(f'История тренировок {user.fullname}.xlsx', 'rb') as file:
						msg_2 = bot.send_document(user.chat_id, file)
						msg = None
						temp_msgs('training_self_history', user, msg_2)
					remove(f'История тренировок {user.fullname}.xlsx')
				else:
					msg = bot.send_message(user.chat_id, 'История пока пуста.')
					temp_msgs('my_trainings', user, msg)


			elif query.startswith('individual_trainings_tasks'):
				plans = [TrainingSelfPlan(user, int(t.additional_info[0])) for t in current_tasks]
				splitted = query.split()
				if query == 'individual_trainings_tasks':
					buttons = [InlineKeyboardButton(text=f'🏋️ Тренировка №{plans.index(i) + 1}', callback_data=f'individual_trainings_tasks {i.id}') for i in plans]
					text = ('\n' + '-' * 15).join([f'🏋️‍ Тренировка №{plans.index(i) + 1}\n' + '\n---\n'.join([f'▫️ *Упражнение №{list(i.exercises).index(j) + 1}*\n' + Exercise(j).description() + f'\n*Видео-отчет*: {"да" if i.exercises[j] else "нет"}' for j in i.exercises]) + f'\n\n' f'*Сложность тренировки:* _{i.rate} из 10_\n'f'*Длительность тренировки*: _{i.duration} мин_\n' f'Доп. условия: _{i.terms if i.terms else "нет"}_' for i in plans]) + \
						'\n\n‼️ Нажмите на кнопку с номером тренировки, чтобы начать ее выполнение!'
					menu.add(*buttons,
							 InlineKeyboardButton(text='👈 Назад', callback_data='individual_trainings'))
					del_msgs('my_trainings', user)
					telebot_splitted_text_send_message(text, user, 'my_trainings', menu)
				elif query.startswith('individual_trainings_tasks'):
					if splitted[1] != 'exercise_info':
						plan = next(filter(lambda x: x.id == int(splitted[1]), plans))
						report_exs = sorted([Exercise(i) for i in list(map(lambda x: x.additional_info[1], filter(lambda x: x.additional_info[0] == plan.id, current_tasks)))[0]], key=lambda x: x.name)
						report_exs_text = '\n'.join([f'- *{i.name}*' + (f' - {int(i.weight) if str(i.weight).endswith(".0") else i.weight} ({exercise_info()[i.unit]})' if i.weight else ('' if not i.unit else " (отягощение на усмотрение)")) for i in report_exs])
					if len(splitted) in [2, 3]:
						if splitted[0] != 'individual_trainings_tasks_end' and splitted[1] != 'exercise_info':
							plan.start(user)
							buttons = [
								InlineKeyboardButton(text='✔️ Завершить', callback_data=f'individual_trainings_tasks_end {plan.id}'),
								*[InlineKeyboardButton(text=i.name[0].upper() + i.name[1:], callback_data=f'individual_trainings_tasks exercise_info {i.exercises_id}') for i in [Exercise(j) for j in plan.exercises]]
							]
							text = '\n---\n'.join([Exercise(i).description() for i in plan.exercises]) + (f'\n\nДополнительные условия: _{plan.terms}_' if plan.terms else '') + \
																										 f'\n\n‼️ Длительность тренировки ограничена. Успейте справиться до *{(datetime.today() + timedelta(minutes=plan.duration)).isoformat().split("T")[1][:-10]}*!\n\n' \
																										 f'‼️ Запишите на видео один подход для отправки отчета по {"каждому из следующих упражнений" if len(report_exs) > 1 else "упражнению"}: _{", ".join(i.name for i in report_exs)}_.\n\n' \
																										 f'Когда закончите задания, нажмите *"Завершить"*.\n\n' \
																										 f'Чтобы просмотреть вспомогательную информацию по упражнению, нажмите на _кнопку с его названием_.'
							media = plan.media(f'individual_trainings_tasks {plan.id}')
							if media:
								buttons.append(*media)
								text += '\n\nВы также можете просмотреть вспомогательное медиа от тренера, нажав на нужную кнопку.'
							menu.add(*buttons)
							user.status = f'individual_training'
							user.set_user()
							del_msgs('my_trainings', user)
							msg = bot.send_message(user.chat_id, text, reply_markup=menu)
							temp_msgs('training_plan', user, msg)
							msg = bot.send_message(user.chat_id, "Пока тренировка не будет завершена, меню будет недоступно!", reply_markup=ReplyKeyboardRemove())
							temp_msgs('training_plan', user, msg)

						elif splitted[1] == 'exercise_info':
							exercise = Exercise(int(splitted[-1]), coach=False)
							dct = exercise_info()
							text = f'*Упражнение "{exercise.name[0].upper() + exercise.name[1:]}"*\n*Тип*: _{dct[exercise.type]}_\n*Мышечная группа*: _{dct[exercise.muscles_group]}_\n*Сложность*: _{dct[exercise.difficulty]}_\n' \
								   f'*Инвентарь*: _{exercise.inventory_name if exercise.inventory_name else "не требуется"}_\n'
							msg = bot.send_message(user.chat_id, text,
												   reply_markup=InlineKeyboardMarkup(row_width=1).add(
													   InlineKeyboardButton(text='🎥 Видео-урок',
																			url=exercise.video_tutorial)
												   ))
							temp_msgs('individual_training_exercise_info', user, msg)


						elif splitted[0] == 'individual_trainings_tasks_end':
							if len(splitted) == 2:
								duration_checking = datetime.now() - plan.training_started_at < timedelta(minutes=plan.duration)
								if duration_checking:
									buttons = [InlineKeyboardButton(text=i.name, callback_data=f'individual_trainings_tasks_end {plan.id} {i.coachs_exercises_id}') for i in report_exs]
									text = 'Отличная работа!\n\nДля завершения тренировки и для того, чтобы она была зачтена, вам нужно предоставить видео-отчет по следующим упражнениям:\n\n' \
										   + report_exs_text + '\n\nНажмите на кнопку с названием упражнения, чтобы отправить видео по нему.'
									menu.add(*buttons)
									user.status = 'sending_individual_plan_report'
									user.set_user()
									msg = bot.send_message(user.chat_id, text, reply_markup=menu)
									del_msgs('training_plan', user)
									temp_msgs('training_plan', user, msg)
									try:
										temp_dct['users'][user.id]['individual_plan'] = {'message': text,
																				'buttons': buttons,
																				'plan': plan,
																				'report_exs': [i.coachs_exercises_id for i in report_exs]}
									except KeyError:
										temp_dct['users'][user.id] = {'individual_plan': {'message': text,
																				'buttons': buttons,
																				 'plan': plan,
																				 'report_exs': [i.coachs_exercises_id for i in report_exs]}}
								else:
									text = f'К сожалению, вы не успели справиться с тренировкой. Время было ограничено, и вы опоздали на *{(datetime.now() - (plan.training_started_at + timedelta(minutes=plan.duration))).minute} минут.*\n\n' \
										   f'В следующий раз точно получится!'
									for task in current_tasks:
										if task.additional_info[0] == plan.id:
											task.delete(user=user)
									msg = bot.send_message(user.chat_id, text, reply_markup=keyboard(user))
									del_msgs('training_plan', user)
									temp_msgs('training_plan', user, msg)
							elif len(splitted) == 3:
								if splitted[2] != 'done':
									ex = Exercise(splitted[2])
									user.status = f'sending_individual_plan_report {ex.coachs_exercises_id}'
									user.set_user()
									text = f'Отправьте видео с одним подходом из упражнения: *{ex.name}*' + (f' ({int(ex.weight) if not str(ex.weight).endswith(".0") else ex.weight} {exercise_info()[ex.unit]})' if ex.weight else "")
									msg = bot.send_message(user.chat_id, text)
									del_msgs('training_plan', user)
									temp_msgs('training_plan', user, msg)

								elif splitted[-1] in ['video', 'audio', 'image']:
									param = splitted[-1]
									if param == 'video':
										msg = bot.send_video(user.chat_id, plan.video)
									elif param == 'image':
										msg = bot.send_photo(user.chat_id, plan.image)
									elif param == 'audio':
										msg = bot.send_voice(user.chat_id, plan.audio)
									temp_msgs('training_plan', user, msg)

								else:
									reports = temp_dct['users'][user.id]['individual_plan']['reports']
									dt = datetime.now()
									for report in reports:
										ex = Exercise(report)
										video_id = reports[report]
										dt += timedelta(seconds=list(reports).index(report))
										user.new_training_report(plan, 'video', video_id, dt, ex)

									user.status = 'registered'
									user.set_user()

									temp_dct['users'].pop(user.id)
									for task in current_tasks:
										if task.additional_info[0] == plan.id:
											task.delete(user=user)

									text = '🖍 Опишите (хотя бы коротко), как прошла ваша тренировка.\n\n' \
										   'Если появились новые неразрешенные вопросы - укажите их. Если беспокоили болевые ощущения или другой дискомфорт - расскажите, какие.\n' \
										   '😇 Все понравилось и ничего не беспокоило? - Можете так и написать!'
									msg = bot.send_message(user.chat_id, text)
									bot.register_next_step_handler(msg, individual_training_text_report)
									del_msgs('training_plan', user)
									temp_msgs('training_plan', user, msg)

							del_msgs('individual_training_exercise_info', user)

		if query.startswith('my_tasks'):
			tasks = user.tasks
			if tasks:
				text = '\n\n'.join([f'❗️ *Задача №{tasks.index(task) + 1}*\n'
								   f'Тип: *{task.type}*\n' \
					   f'Получено: *{task.start_date()}*\n' \
					   f'Срок выполнения до: *{task.end_date()}*\n' \
					   f'Описание: {task.description}' for task in tasks])
			else:
				text = 'Нет текущих задач.'

			msg = bot.send_message(user.chat_id, text)
			del_msgs('my_trainings', user)
			temp_msgs('my_trainings', user, msg)

		if query.startswith('my_signup'):
			menu = InlineKeyboardMarkup(row_width=2)
			coach = user.coach()
			item = query.split()[0]
			if item in ['my_signup', 'my_signup_details']:
				def training_types_checking(dates_list):
					lst = []
					if dates_list:
						schedule_types_amount = coach.working_schedule_training_types()
						week_types = []
						for signup_day in dates_list:
							sessions_types = ScheduleDay(coach, signup_day).sessions_types(user)
							for session_type in sessions_types:
								week_types.append(session_type)
						for tr_type in user.sessions_left():
							if schedule_types_amount[tr_type] == 0:
								lst.append(tr_type)
							if not tr_type in week_types:
								lst.append(tr_type)
					return lst
				if query == 'my_signup':
					# запись только на ближайшие 10 дней
					dates = [day for day in [date.today() + timedelta(days=i) for i in range(1, 11)] if ScheduleDay(coach, day).free_hours(user)]
					if dates:
						buttons = [
							InlineKeyboardButton(text=f'🗓 {fullname_of_date(day)}', callback_data=f'my_signup {day.isoformat()}') for day in dates
						]
						menu.add(*buttons)
						lst = training_types_checking(dates)
						if lst:
							lst = set(lst)
							working_schedule_coach(coach, user, current_types=list(lst))
							out = ', '.join(sorted([training_types()[i] for i in lst]))
							bot.send_message(coach.chat_id, f'Срочно добавьте больше тренировок следующих типов: _{out}_.\n\n'
															f'У клиента *{user.fullname}* они есть на балансе, но в расписании не хватает свободных часов для их проведения!')
						text = 'Выберите нужную дату для записи.' + ('\n\nК сожалению, сейчас для записи недоступны следующие типы тренировок, которые есть у вас на балансе:\n'
																	 f'- _{out}_.\n\nМы уже уведомили тренера о срочной необходимости добавить больше часов для работы с этими типами занятий в расписание!'
																	 if any(lst) else '')
					else:
						working_schedule = list(coach.extra()['working_schedule'])
						def session_types_checking(d:ScheduleDay, u:User) -> bool:
							return any([i in d.sessions_types(user, all_types=True) for i in u.sessions_left()])
						period_checking = any([day for day in [date.today() + timedelta(days=i) for i in range(1, 11)] if str(day.isoweekday()) in working_schedule and
											   session_types_checking(ScheduleDay(coach, day), user) and day <= user.subscription_plan['period']])
						if not 'free' in user.sessions_left():
							period_date = user.subscription_plan['period']
							text = 'К сожалению, свободного времени для записи по доступным вам типам тренировок не найдено.\n\n' +\
								('Мы уже уведомили тренера о том, что нужно позаботиться об увеличении количества свободных часов для доступных вам типов тренировок!\n' +
								 'Попробуйте записаться немного позднее.' if period_checking else f'Так произошло потому, что период действия вашего тарифа истекает ' +
																								  ('*сегодня*.' if period_date == date.today() else f'в *{fullname_of_date(period_date)}.'))
						else:
							text = 'К сожалению, свободного времени для записи на бесплатную тренировку сейчас не найдено.\n\n' \
								   'Мы уже уведомили тренера о том, что нужно позаботиться об увеличении количества свободных часов для бесплатных тренировок!\n' \
								   'Попробуйте записаться немного позднее.'


						if period_checking:
							working_schedule_coach(coach, user)
							msg_2 = bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* не смог записаться на тренировку - нет свободного времени в расписании!\n\n'
																	'Добавьте больше свободных часов для типов тренировок: _' + ', '.join([training_types()[i] for i in user.sessions_left()]) + '_\n\nВаши текущие задачи были обновлены.')
						msg = bot.send_message(user.chat_id, text)
						del_msgs('signup', user)
						temp_msgs('signup', user, msg)


				elif query.startswith('my_signup '):
					chosen_date = date.fromisoformat(query.split()[1])
					if len(query.split()) == 2:
						free_hours = sorted(ScheduleDay(coach, chosen_date).free_hours(user), key=lambda x: x.time)
						user_t_types = ', '.join(f'- *{i.time}:00*: _{training_types()[i.session_type]}_' for i in free_hours)
						buttons = [
							InlineKeyboardButton(text=f'🕘 {i.time}:00', callback_data=f'my_signup {query.split()[1]} {i.time}') for i in free_hours
						]
						menu.add(*buttons, InlineKeyboardButton(text='👈 Назад', callback_data=f'my_signup'))
						text = '📜 Выберите желаемый час посещения.\n\n' \
							   '❗️ При выборе обязательно учтите тип тренировки:\n' \
							   f'{user_t_types}'

					elif len(query.split()) == 3:
						chosen_time = int(query.split()[2])
						chosen_date = ScheduleDay(coach, date.fromisoformat(query.split()[1]))
						current_hour = ScheduleHour(chosen_date, chosen_time)
						try:
							temp_dct['coaches'][coach.id]['signup'] = current_hour
						except KeyError:
							temp_dct['coaches'][coach.id] = {'signup': current_hour}

						current_hour.set(user)

						buttons = [
							InlineKeyboardButton(text=f'📍 Оставить комментарий к записи', callback_data=f'my_signup_details {chosen_date.isoformat()} {chosen_time}')
						]
						menu.add(*buttons)
						reminding = user.notifications()['reminding_before_sessions']
						reminding_text = f'Бот напомнит вам о предстоящей тренировке за {reminding} {"час" if reminding == 1 else "часа"}.\nНапоминания настраиваются в меню *"Мои тренировки"* 👉 *"Настройки бота"*.' if reminding else \
							'Сейчас напоминания о тренировке отключены. Вы можете исправить это в меню *"Мои тренировки"* 👉 *"Настройки бота"*.'

						text = f'🤓 Вы успешно записаны на тренировку к тренеру *{coach.fullname}*!\n\n' \
							   f'🏋️‍♀️ Тип тренировки: _{training_types()[current_hour.session_type]}_\n' \
							   f'🗓 Дата тренировки: _{fullname_of_date(chosen_date.date)}_\n' \
							   f'⏳ Время: _{chosen_time}:00_\n\n' \
							   f'❗️ {reminding_text}\n\n' \
							   f'Нажмите *"📍 Оставить комментарий к записи"*, если хотите сообщить тренеру дополнительную информацию о тренировке.'

				elif query.startswith('my_signup_details '):
					chosen_time = int(query.split()[2])
					chosen_date = ScheduleDay(coach, date.fromisoformat(query.split()[1]))
					try:
						temp_dct['users'][user.id]['signup'] = {'comment': [chosen_date, chosen_time]}
					except KeyError:
						temp_dct['users'][user.id] = {'signup': {'comment': [chosen_date, chosen_time]}}

					text = 'Напишите необходимый комментарий.'

				msg = bot.send_message(user.chat_id, text, reply_markup=menu) if menu.keyboard else bot.send_message(user.chat_id, text)
				if text == 'Напишите необходимый комментарий.':
					bot.register_next_step_handler(msg, send_details)
				elif text.startswith('🤓 Вы успешно записаны на тренировку к тренеру'):
					current_hour = temp_dct['coaches'][coach.id]['signup']
					temp_dct['coaches'][coach.id].pop('signup')
					msg_2 = bot.send_message(coach.chat_id, f'🤓 Новая запись на тренировку от *{user.fullname}*!\n\n'
															f'🏋️‍♀️ Тип тренировки: _{training_types()[current_hour.session_type]}_\n'
															f'🗓 Дата тренировки: _{fullname_of_date(current_hour.date)}_\n'
															f'⏳ Время: _{current_hour.time}:00_\n\n'
															f'Проверить текущее расписание всегда можно в меню *"Общее"* 👉 *"Расписание"*')

				del_msgs('signup', user)
				temp_msgs('signup', user, msg)

			elif item == 'my_signup_history':
				splitted = query.split()
				history = user.past_sessions()
				if len(splitted) == 1:
					buttons = [
						InlineKeyboardButton(text=i, callback_data=f'my_signup_history {i}')
						for i in set([i.year for i in [j['date'] for j in history]])]
					text = 'Выберите год тренировок.'
				elif len(splitted) == 2:
					year = splitted[1]
					history = [i['date'].month for i in history if
							   i['date'].year == int(year)]
					buttons = [InlineKeyboardButton(text=months[i].title(),
													callback_data=f'my_signup_history {year} {i + 1}')
							   for i in range(12) if i + 1 in history] + [InlineKeyboardButton(text='👈 Назад', callback_data='my_signup_history')]
					menu.row_width = 5
					text = f'Выберите месяц тренировок ({year} год).'
				elif len(splitted) == 3:
					year, month = int(splitted[1]), int(splitted[2])
					history = [f'- Дата и время: *{i["date"].isoformat()}, {str(i["time"])[:-3]}*\n' \
							   f'- Тип тренировки: *{training_types()[i["session_type"]]}*' + \
							   (f'\n- Ваш комментарий: _{i["details"]}_' if i["details"] else '') for i in
							   [j for j in history if
								j['date'].year == year and j['date'].month == month]]
					text = f'⏳ *{months[month - 1].title()} {year}* (тренер *{coach.fullname}*)\n' + '\n'.join(history)
					buttons = [InlineKeyboardButton(text='👈 Назад', callback_data=f'my_signup_history {year}')]
				msg = bot.send_message(user.chat_id, text, reply_markup=menu.add(*buttons))
				del_msgs('signup', user)
				temp_msgs('signup', user, msg)

			elif item == 'my_signup_cancel':
				menu = InlineKeyboardMarkup(row_width=3)
				c_len = len(query.split())
				upcoming_sessions = user.upcoming_sessions()
				coach = user.coach()
				schedule = sorted(list(reduce(lambda x, y: x + y, [ScheduleDay(coach, i).user_signed_up_hours(user) for i in [j['date'] for j in upcoming_sessions]], [])), key=lambda x: (x.date, x.time))
				if c_len == 1:
					counter = user.subscription_plan['canceled_sessions']
					period = user.subscription_plan['period'].isoformat()
					canceling_amount = user.tariff().canceling_amount
					if not counter is None:
						if period in counter:
							canceling_amount -= counter[period]
					text = 'Выберите дату и время тренировки, которую хотите отменить.\n\n' + f'Текущее доступное количество отмен: *{canceling_amount}*'

					buttons = [InlineKeyboardButton(text=f'❌ {h.date}, {h.time}:00', callback_data=f'my_signup_cancel {h.date} {h.time}:00') for h in schedule]
					menu.add(*buttons)
				elif c_len == 3:
					splitted = query.split()
					signup_date = datetime.fromisoformat(splitted[1]).date()
					time = int(splitted[2].split(':')[0])
					for h in schedule:
						if h.date == signup_date and h.time == time:
							h.cancel(user, canceling_type='user')
							training_type = training_types()[h.session_type]
							break
					text = f'Ваша запись к тренеру *{coach.fullname}* на *{signup_date}, {time}:00* (тип тренировки _{training_type}_) успешно отменена!'
					bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* отменил свою запись на тренировку на *{signup_date}, {time}:00* (тип тренировки _{training_type}_).')
				msg = bot.send_message(user.chat_id, text, reply_markup=menu) if menu.keyboard else bot.send_message(user.chat_id, text)
				del_msgs('signup', user)
				temp_msgs('signup', user, msg)

		if query == 'available_tariffs':
			user_coach = user.coach()
			if user_coach.tariffs:
				tariffs = user_coach.tariffs
				buttons = [InlineKeyboardButton(text=i.name, callback_data=f'user_pay {i.id}') for i in tariffs]
				msg = bot.send_message(user.chat_id, f'Доступные тарифы тренера *{user_coach.fullname}*:\n\n' + '\n\n'.join([f'📍 Тариф "*{i.name}*"\n🏋️ _Количество тренировок_:\n {training_types(tariff=i)}\n🕔 _Период действия_, дней: {i.period if i.period != 1825 else "бессрочно"}\n❌ _Количество отмен_: {i.canceling_amount if i.canceling_amount != 100 else "неограниченное"}\n💰 _Стоимость_: {i.cost} рублей\n\n'
																													   f'Чтобы просмотреть подробную информацию о тарифе, нажмите на кнопку с его названием.' for i in tariffs]), reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons))

			else:
				msg = bot.send_message(user.chat_id, '😕 К сожалению, у вашего тренера еще нет действующих тарифов.\n\n'
								 'Чтобы оплатить и начать занятия под его руководством, дождитесь появления новых тарифов или попросите ускорить этот процесс сами.')
			del_msgs('paying', user)
			temp_msgs('paying', user, msg)

		if query.startswith('user_pay'):
			tariff = Tariff(query.split()[-1])
			if not user.is_coach:
				discount = user.discount(tariff)
				tariff.cost = tariff.cost if not discount else tariff.cost * (100 - discount)/100
			if query.startswith('user_pay '):
				msg = bot.send_message(user.chat_id, f'📍 *Тариф "{tariff.name}"*\n\n'
											   f'📜 *Описание тарифа:*\n_{tariff.description}_\n\n'
											   f'🏋️ *Количество тренировок:*\n{training_types(tariff=tariff)}\n\n'
											   f'🕔 *Период действия*, дней: {tariff.period if tariff.period != 1825 else "бессрочно"}\n\n'
											   f'❌ *Доступное количество отмен:* {tariff.canceling_amount if tariff.canceling_amount != 100 else "неограниченное"}\n\n'
											   f'😎 *Доступ к меню:*\n{tariff_permissions(tariff)}\n\n'
											   f'💰 *Стоимость:* {str(tariff.cost) + "₽" if not discount else str(tariff.cost) + "₽ (🎁 для вас действует скидка " + str(discount) + "%)"}.',
									   reply_markup=InlineKeyboardMarkup(row_width=1).add(
										   InlineKeyboardButton(text='Расписание тренировок', callback_data=f'user_pay_schedule {tariff.id}'),
										   InlineKeyboardButton(text='Оплатить тариф', callback_data=f'user_pay_process {tariff.id}'),
									   		InlineKeyboardButton(text='👈 Назад', callback_data=f'available_tariffs'))
									   )
				del_msgs('paying', user)
			elif query.startswith('user_pay_schedule '):
				schedule = tariff.schedule()
				schedule = [f"- *{days_of_week[int(i)]}*: " + ', '.join(sorted([' '.join([f'_{k} ({training_types()[l]})_' for k, l in m.items()]) for m in j], key=lambda x: int(x[1:3]) if not ':' in x[1:3] else int(x[1]))) for i, j in schedule.items()]
				msg = bot.send_message(user.chat_id, f'🤓 Тариф "*{tariff.name}*" предоставляет тренировки следующих типов и количества:\n\n{training_types(tariff=tariff)}.\n\n'
													 f'📜 Ваш тренер проводит тренировки, входящие в данный тариф, по следующему расписанию:\n' + '\n'.join(schedule))

			elif query.startswith('user_pay_process'):
				if len(query.split()) == 2:
					coach = user.coach()
					coach_form = coach.form()
					text = f'Для оплаты и получения тарифа "*{tariff.name}*" (тренер *{coach.fullname}*) проделайте следующую инструкцию и нажмите кнопку "*Готово*".'
					menu = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(text='👈 Назад', callback_data=f'user_pay {tariff.id}'))
					paying_type = coach_form['paying_type']
					if paying_type in ['freelancer', 'physical']:
						phone_number = coach_form['phone_number']
						payment_details = coach_form['payment_details']
						paying_link = coach_form['paying_link']
						if not paying_link:
							text +=       f'\n\n🤓 Переведите сумму *{tariff.cost}₽* по следующим реквизитам:\n' \
										  f'📞 {phone_number} _({payment_details})_.\n\n' +\
										  (f'После подтверждения платежа получателем вы получите чек о совершенной покупке _(налогообложение: НПД)_, ' +\
										  f'а также уведомление о начислении тарифа.' if paying_type == 'freelancer' else
										   f'После подтверждения платежа получателем вы получите уведомление о начислении тарифа.')
						else:
							text += f'\n\n🤓  Переведите сумму <b>{tariff.cost}₽</b>, просто перейдя по ссылке для оплаты: <a href="{paying_link}">Оплата</a>.\n\n' +\
									f'После подтверждения платежа получателем вы получите уведомление о начислении тарифа' + (", а также чек о совершенной покупке" if
																															  paying_type == 'freelancer' else ".")
						menu.add(InlineKeyboardButton(text='Готово', callback_data=f'user_pay_process {True} {tariff.id}'))
						msg = bot.send_message(user.chat_id, text, reply_markup=menu, parse_mode='Markdown' if paying_link is None else 'HTML')

				elif len(query.split()) == 3:
					msg = bot.send_message(user.chat_id, 'Спасибо за следование инструкции.\n\n'
														 'Ожидайте уведомление о приеме платежа и начисление тарифа.')
					coach = user.coach()
					buttons = [
						InlineKeyboardButton(text='Да', callback_data=f'user_pay_process {True} {user.id} {tariff.id}'),
						InlineKeyboardButton(text='Нет', callback_data=f'user_pay_process {False} {user.id} {tariff.id}')
					]
					msg_2 = bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* совершил оплату по тарифу *"{tariff.name}"* в размере *{str(tariff.cost) + "₽" if not discount else str(tariff.cost) + "₽ (скидка " + str(discount) + "%)"}* по вашим реквизитам.\n\n'
															f'Проверьте, произошла ли она?', reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons))
					temp_msgs('payment', coach, msg_2)

				elif len(query.split()) == 4:
					params = query.split()
					result = params[1]
					user = User(user_id=params[2])
					# переопределяю, т.к. здесь callback от тренера
					discount = user.discount(tariff)
					tariff.cost = tariff.cost if not discount else tariff.cost * (100 - discount) / 100
					paying_type = coach.form()['paying_type']

					if result == 'True':
						if paying_type == 'freelancer':
							freelancer_sending_receipt(coach, user, tariff)
							msg_2 = bot.send_message(coach.chat_id, f'Отлично! Так как вы самозанятый, для фиксации платежа и начисления тарифа клиенту нужно <i>сформировать и отправить ему чек о покупке</i>.\n\n'
																	"Сделайте это в приложении \"<b>Мой налог</b>\" (<a href='https://faq.selfwork.ru/how-start-work/kak-sozdat-chek'>инструкция</a>).\n\n"
																	'Затем отправьте чек через меню "<b>Общее</b>" 👉 "<b>Коммерция</b>" 👉 "<b>Транзакции</b>"', parse_mode='HTML')
						elif paying_type == 'physical':
							user.pay_tariff(tariff)
							bot.send_message(user.chat_id, f'Вам был успешно начислен тариф *"{tariff.name}"*.\n\nТренер: *{coach.fullname}*.')
							msg_2 = bot.send_message(coach.chat_id, f'Тариф *"{tariff.name}"* по стоимости *{tariff.cost}₽* успешно начислен клиенту *{user.fullname}*.')
						msg = None


					elif result == 'False':
						msg_2 = bot.send_message(coach.chat_id, f'Платеж от клиента *{user.fullname}* не был принят.')
						msg = bot.send_message(user.chat_id, f'К сожалению, ваш платеж по тарифу "*{tariff.name}*" _(тренер {coach.fullname})_ в размере *{tariff.cost}₽* не был принят.\n\n'
															 f'Если у вас есть возражения или вопросы, свяжитесь с тренером по телефону: *{coach.form()["phone_number"]}*.')

					del_msgs('payment', coach)
					temp_msgs('payment', coach, msg_2)

				del_msgs('paying', user)


			temp_msgs('paying', user, msg)

		if query == 'available_promotions':
			promotions = user.coach().promotions()
			if promotions:
				# ПОСЛЕ СОЗДАНИЯ КОНСТРУКТОРА АКЦИЙ ДОПИСАТЬ
				msg = bot.send_message(user.chat_id, 'Доступные акции:')
			else:
				msg = bot.send_message(user.chat_id, '😞 Доступных акций пока нет.')

			del_msgs('paying', user)
			temp_msgs('paying', user, msg)

		# проверка на отправку видео
		if query and user.status and user.status.startswith('sending_self_training_video_report '):
			bot.send_message(user.chat_id,
							 '😊 *Сначала вам нужно отправить видео-отчет* о законченной самостоятельной тренировке!\n'
							 '*Просто следуйте* инструкции выше.\n\n'
							 '❌ _Или введите_ *"Q"*, чтобы прекратить отправку отчета. Выполненное задание не будет зачтено.',
							 parse_mode='Markdown')

		if query.startswith('my_diet'):
			msg = bot.send_message(user.chat_id, 'К сожалению, этот раздел еще в разработке.')
			del_msgs('my_trainings', user)
			temp_msgs('my_diet', user, msg)


		if query.startswith('self_trainings'):
			if user.current_coach_id:
				coach = user.coach()
			coach_levels = coach.levels()
			coach_all_training_plans = coach.training_plans()
			if coach_levels:
				if not user.training_levels_id:
					user.training_levels_id = coach_levels[0]['id']
					user.set_user()
				level = Level(user.training_levels_id)
				if query == 'self_trainings':
					training_history = user.training_self(objects=True)
					amount = level.sessions_amount - len(list(filter(lambda t: t.levels_id == level.id and t.training_plan_is_done, training_history))) if training_history else level.sessions_amount
					text = f'Ваш текущий уровень подготовки: "*{level.name}*"\n' \
						   f'Количество тренировок для перехода на следующий уровень: _{(amount if amount else "выполнено") if level.sessions_amount else "не определено"}_\n' \
						   f'Выполнено самостоятельных тренировок:\n- всего: _{len([i for i in training_history if i.training_plan_is_done]) if training_history else 0}{" из " + str(len(coach_all_training_plans)) if coach_all_training_plans else " "}_;\n' \
						   f'- за последний месяц: {len(list(filter(lambda x: x.training_started_at and datetime.today() - x.training_started_at <= timedelta(days=30) and x.training_plan_is_done, training_history))) if training_history else 0}\n\n' \
						   f'*Если получаете тренировку*, не забывайте сделать ее в текущий день и отчитаться о выполнении!\n'

					buttons = [
						InlineKeyboardButton(text='Получить тренировку', callback_data='self_trainings_get'),
						InlineKeyboardButton(text='Перейти на следующий уровень',
											 callback_data='self_trainings_next_level'),
						InlineKeyboardButton(text='История тренировок', callback_data='self_trainings_history')
					]
					if amount <= 0:
						menu = InlineKeyboardMarkup(row_width=1).add(*buttons)
						text += '\n*Получить тренировку* - получить и выполнить новый тренировочный план для текущего уровня подготовки.\n' \
								'*Перейти на следующий уровень* - перейти на следующий заслуженный уровень подготовки.\n' \
								'*История тренировок* - просмотреть историю всех самостоятельных тренировок.\n'
					else:
						menu = InlineKeyboardMarkup(row_width=1).add(buttons[0], buttons[2])
					
					if user.training_reports(reports_type='self'):
						menu.add(InlineKeyboardButton(text='Мои отчеты', callback_data='self_trainings_reports'))
						text += '*Мои отчеты* - просмотреть видео-отчеты по самостоятельным тренировкам.'

					msg = bot.send_message(user.chat_id, text, reply_markup=menu)
					del_msgs('my_trainings', user)
					temp_msgs('training_self', user, msg)

				elif query == 'self_trainings_get':
					training_plan = user.level(training_plan=True)
					training_self_history = user.training_self()
					if not training_self_history or training_self_history[-1]['training_plan_is_done'] or not training_self_history[-1]['training_plan_is_done'] and datetime.now() - training_self_history[-1]['plan_received_at'] >= timedelta(days=3):
						if training_plan:
							exercises = [Exercise(j) for j in training_plan.exercises]
							current_exercises = '\n------------\n'.join([f'*№{exercises.index(i) + 1}. {i.name[0].upper() + i.name[1:]}*:\n'
																		 f'-  _подходов_: {i.sets if i.sets else "на усмотрение"}\n'
																		 f'-  _повторений_: {i.repeats if not i.repeats is None or i.repeats != 0 else "максимум (сколько возможно подряд)"}\n'
																		 f'-  _отягощение_: {i.weight if i.weight else ("на усмотрение" if i.unit else "не требуется")}' for i in exercises])
							media = list(filter(lambda item: item, ['видео' if training_plan.video else None, 'аудио' if training_plan.audio else None, 'изображение' if training_plan.image else None]))
							media = ', '.join(media) if media else None
							code_words = open('data/specs/russian_nouns.txt', encoding='utf-8').readlines()
							code_word = code_words[randrange(0, len(code_words))].rstrip()
							text = f'💪 *Уровень подготовки*: "*{level.name}*"\n' \
								   f'💯 *Сложность тренировки*: _{training_plan.rate} из 10_\n' \
								   f'⏳ *Максимальная длительность*: _{training_plan.duration} мин (минимальная - 15 мин)_\n' \
								   f'📜 *Дополнительные условия*: _{training_plan.terms if training_plan.terms else "нет"}_\n' \
								   f"📹 *Вспомогательные медиа от тренера*: _{media + ' (нажмите Медиа, чтобы просмотреть)' if media else 'нет'}_\n\n" \
								   f'‼️ *Упражнения*:\n' \
								   f'{current_exercises}\n\n' \
								   f'❕ *Нажмите на номер упражнения*, чтобы просмотреть подробную информацию о нем (в т.ч. об используемом инвентаре и вспомогательные видео-уроки).\n\n' \
								   f'🏃 Нажмите *"Начать"*, чтобы начать тренировку.\n‼️Не забудьте снимать на видео один подход из каждого упражнения для отчета по выполнению этого плана тренировки.\n' \
								   f'㊙️ Кодовое слово для проверки в этот раз - ❗️*"{code_word}"*❗️ (его нужно произнести в *каждом* из видео).'

							training_plan.new_training_self(user, code_word)

							buttons = [
								InlineKeyboardButton(text='Начать', callback_data=f'self_trainings_start {training_plan.id}'),
								InlineKeyboardButton(text='Медиа', callback_data=f'self_trainings_media {training_plan.id}'),
								*[InlineKeyboardButton(text='❓ Упражнение №' + str(exercises.index(i) + 1), callback_data=f'self_trainings_exercise_info {training_plan.id} {i.exercises_id}') for i in exercises]
							]
							menu = InlineKeyboardMarkup(row_width=1)
							if not media:
								menu.add(buttons[0], *buttons[2:])
							else:
								menu.add(*buttons)
							msg = bot.send_message(user.chat_id, text, reply_markup=menu)
							del_msgs('training_self', user)
							temp_msgs('training_self', user, msg)
						else:
							training_self_coach(coach, level, 'create_training_plans')
							bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* с уровнем тренировок "*{level.name}*" срочно нуждается в новых тренировочных планах!\n\n'
															f'Ваши текущие задачи были обновлены.')
							msg = bot.send_message(user.chat_id, f'К сожалению, в данный момент нет доступных тренировок для уровня подготовки "*{level.name}*".\n\n'
																 f'Попробуйте немного позже - _мы уже уведомили тренера_ о необходимости создания новых тренировочных планов!')
							del_msgs('training_self', user)
							temp_msgs('training_self', user, msg)
					else:
						if not training_self_history[-1]['training_plan_is_done'] and datetime.now() - training_self_history[-1]['plan_received_at'] < timedelta(days=3):
							msg = bot.send_message(user.chat_id, 'К сожалению, ваша прошлая тренировка была не зачтена (или еще не проверена) тренером.\n\n'
																 f'Следующий тренировочный план можно будет получить начиная с *{datetime.strftime(training_self_history[-1]["plan_received_at"] + timedelta(days=3), "%d.%m.%Y, %H:%M")}*.')
							del_msgs('training_self', user)
							temp_msgs('training_self', user, msg)

				elif query.startswith('self_trainings_start '):
					training_plan = TrainingSelfPlan(user=user, plan_id=query.split()[1])
					training_plan.start(user)
					user.status = 'self_training'
					user.set_user()
					msg = bot.send_message(user.chat_id, f'Время на выполнение тренировки: *{training_plan.duration}* минут. Успейте справиться до *{datetime.strftime(datetime.now() + timedelta(minutes=training_plan.duration), "%H:%M")}*.\n\n'
														 f'Когда закончите тренировку и запись всех видео для отчета, нажмите *"Закончить"*.',
										   reply_markup=InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(text='Закончить', callback_data=f'self_trainings_end {training_plan.id}')
										   ))
					temp_msgs('training_self', user, msg)
					msg = bot.send_message(user.chat_id, 'Пока тренировка не будет завершена, меню будет недоступно!', reply_markup=ReplyKeyboardRemove())
					temp_msgs('training_self', user, msg)

				elif query.startswith('self_trainings_end'):
					training_plan = TrainingPlan(plan_id=query.split()[1])
					training_self_start = user.training_self()[-1]['training_started_at']
					duration_checking = datetime.now() - training_self_start < timedelta(minutes=training_plan.duration)
					if duration_checking:
						checking_exercise = Exercise(list(training_plan.exercises.keys())[random.randrange(0, len(training_plan.exercises))])
						user.status = f'sending_self_training_video_report {checking_exercise.coachs_exercises_id} {datetime.now().timestamp()}'
						user.set_user()
						code_word = user.training_self()[-1]['code_word']
						msg = bot.send_message(user.chat_id, f'Отлично! Вы успели справиться.\n\n'
											   f'Теперь просто отправьте прямо сюда видео с отчетом по следующему упражнению: "_{checking_exercise.name}_".\n\n'
											   f'Кодовое слово, которое должно быть на видео: "_{code_word}_".')
						del_msgs('training_self', user)
						temp_msgs('training_self', user, msg)
					else:
						msg = bot.send_message(user.chat_id, 'К сожалению, вы не уложились во временные ограничения по выполнению этой тренировки.\n\n'
															 'Она не будет зафиксирована в вашей истории, и вам придется сделать ее заново для продвижения по уровням тренировок.', reply_markup=keyboard(user))
						user.status = 'registered'
						user.set_user()
						del_msgs('training_self', user)
						temp_msgs('training_self', user, msg)

				elif query.startswith('self_trainings_credited '):
					user = User(user_id=query.split()[1])
					training_plan = TrainingPlan(plan_id=query.split()[2])
					for i in reversed(user.training_reports()):
						if i['training_plans_id'] == int(training_plan.id) and i['report_type'] == 'video':
							dt = i['report_date']
							break
					report = TrainingReport(user, dt)
					report.update(True)

					msg = bot.send_message(user.chat_id, f'Поздравляем! Отчет по вашей самостоятельной тренировке от *{datetime.strftime(report.datetime, "%d.%m.%Y")}* '
														 f'по упражнению _{report.exercise.name}_ был зачтен тренером!\n\n'
														 f'Ограничение на получение тренировочных планов было снято, и вы уже можете получить следующую тренировку.')
					if len([i for i in user.training_reports() if i['report_type'] == 'video' and i['credited']]) == 1 and user.records():
						bot.send_message(user.chat_id,
										 '🤓 Проверен и подтвержден ваш первый видео-отчет по тренировке - теперь доступно меню 📍 *"Мои рекорды"* в *"Моих тренировках"*!\n\n'
										 '💪 Все ваши новые лучшие результаты будут автоматически фиксироваться в этом меню. Проверьте его.')
					bot.send_message(coach.chat_id, f'Тренировка клиента *{user.fullname}* от *{datetime.strftime(report.datetime, "%d.%m.%Y")}* была успешно зачтена!')

					del_msgs('training_self', user)
					del_msgs('training_self_check', coach)
					temp_msgs('training_self', user, msg)


				elif query.startswith('self_trainings_not_credited '):
					user = User(user_id=query.split()[1])
					training_plan = TrainingPlan(query.split()[2])
					for i in reversed(user.training_reports()):
						if i['training_plans_id'] == int(training_plan.id) and i['report_type'] == 'video':
							dt = i['report_date']
							break
					report = TrainingReport(user, dt)
					report.update(False)
					msg = bot.send_message(user.chat_id, f'К сожалению, ваш отчет по тренировке от *{datetime.strftime(dt, "%d.%m.%Y")}* по упражнению '
														 f'_{report.exercise.name}_ не был зачтен тренером.\n\n'
										   f'В следующий раз точно получится!')
					bot.send_message(coach.chat_id, f'Тренировка клиента *{user.fullname}* от *{datetime.strftime(dt, "%d.%m.%Y")}* не была зачтена.')

					del_msgs('training_self', user)
					del_msgs('training_self_check', coach)
					temp_msgs('training_self', user, msg)


				elif query == 'self_trainings_next_level':
					level = Level(user.training_levels_id)
					idx = coach_levels.index([i for i in coach_levels if i['id'] == level.id][0])
					try:
						new_level = coach_levels[idx + 1]
					except IndexError:
						msg = bot.send_message(user.chat_id, 'Пожалуйста, попробуйте перейти на новый уровень через некоторое время.\n\n'
															 'Следующих уровней пока нет. Мы уже отправили тренеру уведомление о вашем желании. Извините за неудобства.')
						training_self_coach(coach, user, 'create_levels')
						bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* пытался перейти на новый уровень после выполнения нужного количества тренировок для продвижения на уровне "*{level.name}*", но не смог.\n'
														f'Срочно добавьте новые уровни!\n\n'
												f'Ваши текущие задачи были обновлены.')
					else:
						user.training_levels_id = new_level['id']
						user.set_user()
						msg = bot.send_message(user.chat_id, f'Ура! Вы справились с нужным количеством тренировок и перешли на новый уровень *{new_level["level_name"]}*\n'
															 f'Теперь вам доступны тренировки из этого уровня.')

					del_msgs('training_self', user)
					temp_msgs('training_self', user, msg)
				
				elif query.startswith('self_trainings_reports'):
					splitted = query.split()
					training_self_reports = user.training_reports(reports_type='self')
					menu = InlineKeyboardMarkup(row_width=1)
					if len(splitted) == 1:
						reports = training_self_reports
						buttons = [InlineKeyboardButton(text=i, callback_data=f'self_trainings_reports {i}') for i in set([i.year for i in [j['report_date'] for j in reports]])] + \
							[InlineKeyboardButton(text='👈 Назад', callback_data=f'self_trainings')]
						msg = bot.send_message(user.chat_id, 'Выберите год тренировок', reply_markup=menu.add(*buttons))
						del_msgs('report_view', user)
					elif len(splitted) == 2:
						year = splitted[1]
						reports = [i['report_date'].month for i in training_self_reports if i['report_date'].year == int(year)]
						buttons = [InlineKeyboardButton(text=months[i].title(),
														callback_data=f'self_trainings_reports {year} {i + 1}')
								   for i in range(12) if i + 1 in reports] + \
								  [InlineKeyboardButton(text='👈 Назад',
														callback_data=f'self_trainings_reports')]
						menu.row_width = 5
						msg = bot.send_message(user.chat_id, f'Выберите месяц тренировок ({year} год).',
											   reply_markup=menu.add(*buttons))
						del_msgs('report_view', user)
					elif len(splitted) == 3:
						year, month = int(splitted[1]), int(splitted[2])
						reports = [TrainingReport(user, i) for i in [j['report_date'] for j in training_self_reports if j['report_date'].year == year and j['report_date'].month == month]]
						text = '\n\n'.join([report.description() for report in reports]) + '\n\nНажмите на кнопку с датой отчета, чтобы просмотреть отчетное видео.'
						buttons = [InlineKeyboardButton(text=f'🎥 {str(i.datetime)[:-3]}', callback_data=f'self_trainings_reports {year} {month} {reports.index(i)}') for i in reports] + \
								  [InlineKeyboardButton(text='👈 Назад',
														callback_data=f'self_trainings_reports {year}')]
						menu.row_width=3
						msg = None
						msg_2 = bot.send_message(user.chat_id, text, reply_markup=menu.add(*buttons))
						temp_msgs('report_view', user, msg_2)
					elif len(splitted) == 4:
						year, month, idx = int(splitted[1]), int(splitted[2]), int(splitted[3])
						reports = [TrainingReport(user, i) for i in
								   [j['report_date'] for j in training_self_reports if
									j['report_date'].year == year and j['report_date'].month == month]]
						report_video_id = reports[idx].content
						msg = None
						msg_2 = bot.send_video(user.chat_id, report_video_id)
						temp_msgs('report_view', user, msg_2)
					del_msgs('training_self', user)
					temp_msgs('training_self', user, msg)
					
				
				elif query == 'self_trainings_history':
					history = user.self_trainings_history('self', 'user')
					if history:
						with open(f'История тренировок {user.fullname}.xlsx', 'rb') as file:
							msg_2 = bot.send_document(user.chat_id, file)
							msg = None
							temp_msgs('training_self_history', user, msg_2)
						remove(f'История тренировок {user.fullname}.xlsx')
					else:
						msg = bot.send_message(user.chat_id, 'История пока пуста.')
						temp_msgs('training_self', user, msg)

				elif query.startswith('self_trainings_media '):
					training_plan = TrainingPlan(query.split()[1])
					if training_plan.video:
						msg = bot.send_video(user.chat_id, training_plan.video)
					if training_plan.image:
						msg = bot.send_video(user.chat_id, training_plan.image)
					if training_plan.audio:
						msg = bot.send_voice(user.chat_id, training_plan.audio)
					temp_msgs('training_self', user, msg)

				elif query.startswith('self_trainings_exercise_info '):
					exercise = Exercise(query.split()[-1], coach=False)
					dct = exercise_info()
					text = f'*Упражнение "{exercise.name[0].upper() + exercise.name[1:]}"*\n*Тип*: _{dct[exercise.type]}_\n*Мышечная группа*: _{dct[exercise.muscles_group]}_\n*Сложность*: _{dct[exercise.difficulty]}_\n' \
						   f'*Инвентарь*: _{exercise.inventory_name if exercise.inventory_name else "не требуется"}_\n'
					msg = bot.send_message(user.chat_id, text, reply_markup=InlineKeyboardMarkup(row_width=1).add(
						InlineKeyboardButton(text='🎥 Видео-урок', url=exercise.video_tutorial)
					))
					temp_msgs('training_self', user, msg)

			else:
				training_self_coach(coach, user, 'create_levels')
				bot.send_message(coach.chat_id, f'Клиент *{user.fullname}* пытался получить самостоятельные тренировки, но не смог, потому что еще нет уровней подготовки и тренировочных планов!\n\n'
								 f'Получение самостоятельных тренировок входит в его тарифный план, поэтому, пожалуйста, исправьте недоразумение как можно скорее.\n\n'
												f'Ваши текущие задачи были обновлены.')
				msg = bot.send_message(user.chat_id, f'К сожалению, в данный момент еще нет доступных тренировочных уровней и планов для самостоятельного выполнения.\n\n'
									   f'Попробуйте немного позже - _мы уже уведомили тренера_ об этой проблеме в срочном порядке! Извините за неудобства.')
				temp_msgs('training_self', user, msg)


		if query == 'what_is_free_session':

			msg = bot.send_message(user.chat_id, open('data/specs/free_session.txt', encoding='utf-8').read())
			temp_msgs('signup', user, msg)

	def individual_training_text_report(message):
		user = User(message.chat.id)
		coach = user.coach()
		if re.match(r'\w+', message.text):
			training_plan = user.training_reports(reports_type='individual', objects=True)[-1].training_plan
			user.new_training_report(training_plan, 'text', message.text)
			msg = bot.send_message(user.chat_id,
								   'Ваши видео- и текстовый отчеты успешно приняты! Ожидайте проверки и оценки их тренером.',
								   reply_markup=keyboard(user))
			bot.send_message(coach.chat_id,
							 f'Клиент *{user.fullname}* прислал новый отчет (видео и текст) по индивидуальной тренировке!\n\n'
							 f'Как можно скорее проверьте его в меню *"Клиенты"* 👉 *"Отчеты по тренировкам"*\n\n'
							 f'Ваши текущие задачи были обновлены.')
			individual_training_plan_coach(coach, user, 'check_report')
		else:
			msg = bot.send_message(user.chat_id, 'Неверный формат отчета! Попробуйте еще раз.')
			bot.register_next_step_handler(msg, individual_training_text_report)
		del_msgs('training_plan', user)
		temp_msgs('training_plan', user, msg)


	def individual_training_text_report_send_comment(message):
		coach = Coach(message.chat.id)
		params = temp_dct['coaches'][coach.id]['send_training_individual_comment']
		user = User(user_id=params['user_id'])
		training_plan = TrainingSelfPlan(user, int(params['plan_id']))
		menu, text = None, None
		if 'menu' in params and 'text' in params:
			menu, text = params['menu'], params['text']
		temp_dct['coaches'].pop(coach.id)
		report = next(filter(lambda x: x.training_plan.id == training_plan.id and x.type == 'text' and not x.checked,
							 user.training_reports(reports_type='individual', objects=True)))
		if re.match(r'\w+', message.text):
			report.coach_comment = message.text
			report.update()
			del_msgs('report_check', coach)
			bot.send_message(user.chat_id,
							 f'Тренер отправляет комментарий по вашему текстовому отчету по тренировке от *{training_plan.training_started_at.date()}*'
							 f' (упражнений: *{len(training_plan.exercises)}*).\n\n'
							 f'Ваш отчет:\n_{report.content}_\n\n'
							 f'Комментарий тренера:\n_{report.coach_comment}_\n\n'
							 f'Просмотр истории отчетов всегда доступен в меню *"Мои тренировки"* 👉 *"Индивидуальные занятия"*!')
			msg = bot.send_message(coach.chat_id,
								   f"Комментарий по текстовому отчету клиента *{user.fullname}* по тренировке от *{training_plan.training_started_at.date()}* "
								   f"успешно отправлен!", reply_markup=admin_keyboard())
			temp_msgs('main_admin', coach, msg)
			if menu and text:
				msg = bot.send_message(coach.chat_id, text, reply_markup=menu)
				temp_msgs('main_admin', coach, msg)
		else:
			msg = bot.send_message(user.chat_id, 'Неверный формат комментария! Попробуйте еще раз.')
			bot.register_next_step_handler(msg, individual_training_text_report_send_comment)
			temp_msgs('report_check', coach, msg)


	def send_details(message):
		user = User(message.chat.id)
		coach = user.coach()
		dt = temp_dct['users'][user.id]['signup']['comment']
		chosen_date, chosen_time = dt[0], dt[1]
		signup = ScheduleHour(chosen_date, chosen_time)
		signup.send_details(user, message.text)
		msg = bot.send_message(user.chat_id, f'Спасибо за дополнительную информацию! Тренер ее получит и обработает.\n\n'
											 f'🏃 Тренер: _{coach.fullname}_\n'
											 f'🏋️‍♀️ Тип тренировки: _{training_types()[signup.session_type]}_\n'
											 f'🗓 Дата тренировки: _{fullname_of_date(chosen_date.isoformat())}_\n'
											 f'⏳ Время: _{chosen_time}:00_\n\n'
											 f'📍 Ваш комментарий: _{message.text}_')
		msg_2 = bot.send_message(coach.chat_id,
								 f'Клиент _{user.fullname}_ отправляет комментарий по своей записи на тренировку.\n\n'
								 f'🏋️‍♀️ Тип тренировки: _{training_types()[signup.session_type]}_\n'
								 f'🗓 Дата тренировки: _{fullname_of_date(chosen_date.isoformat())}_\n'
								 f'⏳ Время: _{chosen_time}:00_\n\n'
								 f'📍 Комментарий: _{message.text}_')
		del_msgs('signup', user)
		temp_msgs('signup', user, msg)
		temp_msgs('signup', coach, msg_2)


	def create_tariff(message):
		coach = Coach(message.chat.id)
		if message.text.rstrip() == 'Q':
			bot.send_message(coach.chat_id, 'Создание тарифа отменено.')
			del_msgs('my_tariffs', coach)
			if os.path.exists(f'create_tariff {coach.id}.json'):
				remove(f'create_tariff {coach.id}.json')
		else:
			if not os.path.exists(f'create_tariff {coach.id}.json'):
				dump({
					'name': None,
					'sessions': {
						'personal': None,
						'split': None,
						'group': None,
						'personal_online': None
					},
					'period': None,
					'cost': None,
					'canceling_amount': None,
					'users_permissions': {
						'individual_trainings': None,
						'self_trainings': None,
						'my_diet': None
					},
					'description': None
				}, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
			new_tariff = load(open(f'create_tariff {coach.id}.json', encoding='utf-8'))
			params = {
				'canceling_amount': '*Сколько раз* в течение действия периода тарифа клиент может *отменить* занятие? Выберите количество или *"Не ограничивать"*, чтобы клиент мог отменять любое количество тренировок.\n'
									'Или выберите *"Без отмены"*, чтобы клиент _не имел_ возможности отменить тренировку.\n\n'
									'Отмена происходит только по правилам отмены: _отменить тренировку в день ее посещения нельзя_.',
				'sessions_types': {'personal': 'Персональные тренировки', 'split': 'Сплит-тренировки',
								   'group': 'Групповые тренировки',
								   'personal_online': 'Персональные онлайн-тренировки'}
			}

			if not new_tariff['name']:
				new_tariff['name'] = message.text
				dump(new_tariff, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
				buttons = [InlineKeyboardButton(
					text=f'{params["sessions_types"][i]}: {new_tariff["sessions"][i] if new_tariff["sessions"][i] else 0}',
					callback_data=f'new_t_sessions {i}') for i in new_tariff['sessions']]

				msg = bot.send_message(coach.chat_id,
									   '*Выберите*, _какие тренировки и в каком количестве_ будет предоставлять клиенту оплаченный тариф.\n'
									   'Если в тарифе не требуются совместные тренировки (например, для исключительно онлайн-сопровождения клиентов посредством функционала бота), нажмите *"Пропустить"*.\n\n'
									   '- *Персональные тренировки*: 1 клиент в час;\n'
									   '- *Сплит-тренировки*: до 3 клиентов в час;\n'
									   '- *Групповые тренировки*: неограниченное количество клиентов в час;\n'
									   '- *Персональные онлайн-тренировки*: один человек в час в режиме онлайн (видеосвязь).',
									   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons, InlineKeyboardButton(
										   text='Пропустить', callback_data='set_new_t_sessions_end')))
				del_msgs('my_tariffs', coach)
				temp_msgs('my_tariffs', coach, msg)
			elif not new_tariff['cost']:
				if message.text.isdigit():
					new_tariff['cost'] = int(message.text)
					dump(new_tariff, open(f'create_tariff {coach.id}.json', 'w', encoding='utf-8'), ensure_ascii=False)
					buttons = InlineKeyboardMarkup(row_width=5).add(
						*[InlineKeyboardButton(text=i, callback_data=f'new_t_canceling {i}') for i in
						  [1, 2, 3, 5, 10, 15, 20]],
						InlineKeyboardButton(text='Не ограничивать', callback_data='new_t_canceling infinity'),
						InlineKeyboardButton(text='Без отмены', callback_data='new_t_canceling is_none'))

					msg = bot.send_message(coach.chat_id, params['canceling_amount'], reply_markup=buttons)
					del_msgs('my_tariffs', coach)
					temp_msgs('my_tariffs', coach, msg)

			elif not new_tariff['description']:
				new_tariff['description'] = message.text
				try:
					coach.set_coach_tariff(coach, new_tariff['name'], new_tariff['description'], new_tariff['sessions'],
										   new_tariff['period'], new_tariff['canceling_amount'], new_tariff['cost'],
										   new_tariff['users_permissions'])
					remove(f'create_tariff {coach.id}.json')
					bot.send_message(coach.chat_id, f'Тариф *{new_tariff["name"]}* успешно создан!')
					del_msgs('my_tariffs', coach)
				except:
					bot.send_message(coach.chat_id, 'Ошибка создания тарифа. Попробуйте еще раз.')
					bot.send_message(developer_id, f'Произошла ошибка: handlers/general.py, {datetime.now().isoformat()}.\n'
											   f'Добавлена в лог-файл.')
					Error().log()
					del_msgs('my_tariffs', coach)
					remove(f'create_tariff {coach.id}.json')
					print(e)


	def change_tariff(message):
		coach = Coach(message.chat.id)
		tariff = Tariff(tariff_id=list(temp_dct['coaches'][coach.id].keys())[0].split()[-1])
		params = temp_dct['coaches'][coach.id][f'changing_tariff {tariff.id}']
		for i in params:
			if not params[i]:
				param = i
				break
		if param in ['name'] and all([i.isalpha() or i == ' ' for i in message.text.split()]) or param in ['cost'] and all(
			[i.isdigit() for i in message.text.split()]) or param == 'description' and message.text:
			temp_dct['coaches'][coach.id][f"changing_tariff {tariff.id}"][param] = int(
				message.text) if message.text.isdigit() else message.text
			buttons = [InlineKeyboardButton(text=tariff_info()[i], callback_data=f'my_tariff_change {i} {tariff.id}')
					   for i in [j for j in tariff.__dict__ if not j in ['id', 'coachs_id']]]

			msg = bot.send_message(coach.chat_id,
								   f'Параметр *{tariff_info()[param]}* для тарифа *{tariff.name}* успешно изменен!',
								   parse_mode='Markdown',
								   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																					  InlineKeyboardButton(
																						  text='Завершить',
																						  callback_data=f'my_tariff_change_end {tariff.id}')))
			del_msgs('my_tariffs', coach)
			temp_msgs('my_tariffs', coach, msg)
		else:
			msg = bot.send_message(coach.chat_id, 'Неверные данные. Попробуйте еще раз.')
			bot.register_next_step_handler(msg, change_tariff)
			del_msgs('my_tariffs', coach)


	def new_training_self_level(message):
		coach = Coach(message.chat.id)
		if message.text != 'Q':
			if not f'creating_level {coach.id}' in temp_dct['coaches']:
				level_name = message.text.title()
				msg = bot.send_message(coach.chat_id,
									   '*Выберите*, какое количество тренировок будет _нужно сделать клиентам_ в рамках данного уровня для _получения возможности_ перейти на следующий, более сложный уровень подготовки.\n\n'
									   '*Вы также* можете нажать *"Не назначать"*, чтобы уровень не ограничивался количеством тренировок (например, если он будет максимально возможным или единственным).',
									   reply_markup=InlineKeyboardMarkup(row_width=4).add(
										   *[InlineKeyboardButton(text=i,
																  callback_data=f'training_levels_add {level_name} {i}') for
											 i in [3, 5, 7, 10, 15, 20, 25, 30]],
										   InlineKeyboardButton(text='Не назначать',
																callback_data=f'training_levels_add {level_name} 0')
									   ))
			else:
				level_description = message.text
				level_name, sessions_amount = temp_dct['coaches'][f'creating_level {coach.id}']['name'], \
				temp_dct['coaches'][f'creating_level {coach.id}']['sessions_amount']
				temp_dct['coaches'].pop(f'creating_level {coach.id}', None)
				coach.levels(new=True, level_name=level_name, level_description=level_description,
							 level_sessions_amount=sessions_amount)
				levels = coach.levels()
				number = levels.index([i for i in levels if i["level_name"] == level_name][0])
				if not coach.tasks is None:
					for task in coach.tasks:
						if task.type_number == 4:
							if task.additional_info == level_name:
								task.delete(coach)
				msg = bot.send_message(coach.chat_id, f'Новый уровень подготовки успешно создан!\n\n'
													  f'В списке ваших уровней он имеет номер: _{number + 1}_.\n'
													  f'Его название: _{level_name}_.\n'
													  f'Количество тренировок, необходимое для выполнения для перехода на следующий уровень: _{sessions_amount if sessions_amount != 0 else "не назначено"}_.\n'
													  f'Следующий уровень подготовки: _{levels[number + 1] if number < len(levels) - 1 else "отсутствует"}_.')

		else:
			msg = bot.send_message(coach.chat_id, 'Создание нового уровня отменено.')
			temp_dct['coaches'].pop(f'creating_level {coach.id}', None)
		del_msgs('main_admin', coach)
		temp_msgs('main_admin', coach, msg)


	def exercise_add_info(message):
		coach = Coach(message.chat.id)
		exs_info = exercise_info()
		p = {'terms': 'условий'}

		for i in temp_dct['coaches'][coach.id]['creating_plan']['exercises']:
			if temp_dct['coaches'][coach.id]['creating_plan']['exercises'][i]['terms'] == 'setting':
				exercise = Exercise(i, coach=False)
				param = 'terms'

		if param == 'terms' and re.match('\w+', message.text):
			temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id][param] = message.text

			menu = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['menu']

			params = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]

			text = f'Категория упражнения: *{exercise.category}*\n' f'Название упражнения: *{exercise.name}*\n' f'Инвентарь: *{exercise.inventory_name if exercise.inventory_name else "не требуется"}*\n' f'Целевая мышечная группа: *{exs_info[exercise.muscles_group]}*\n' f'Сложность: *{exs_info[exercise.difficulty]}*\n' f'Тип: *{exs_info[exercise.type]}*\n' f'Единица измерения (отягощения, объема): *{exs_info[exercise.unit] if exercise.unit else "отсутствует"}*\n\n' f'Текущие указанные параметры:\n- ' + '\n- '.join(
				[f'_{exs_info[i]}_: {params[i] if params[i] else "не указано"}' for i in
				 [j for j in params if not j in ["msg", "menu",
												 "level_id", 'check_exercise']]]) + f'\n\nОбязательный параметр для упражнения: *"Количество повторений"*. Остальные параметры можно указать по желанию.\n\n' f'Выберите нужный параметр, чтобы задать его. Нажмите *"Закончить"*, чтобы сохранить изменения и перейти к редактированию тренировочного плана.'

			msg = bot.send_message(coach.chat_id, text,
								   parse_mode='Markdown',
								   reply_markup=menu)
			del_msgs('main_admin', coach)

		else:
			msg = bot.send_message(coach.chat_id, f'Неверный формат {p[param]}. Попробуйте заново.')
			bot.register_next_step_handler(msg, exercise_add_info)

		temp_msgs('main_admin', coach, msg)


	def training_plan_add_info(message):
		coach = Coach(message.chat.id)
		if re.match(r'\w+', message.text):
			temp_dct['coaches'][coach.id]['creating_plan']['session_terms'] = message.text
			msg = temp_dct['coaches'][coach.id]['creating_plan']['msg']()
			del_msgs('main_admin', coach)
		else:
			msg = bot.send_message(coach.chat_id, 'Неверный формат условий. Попробуйте заново.')
			bot.register_next_step_handler(msg, training_plan_add_info)
		temp_msgs('main_admin', coach, msg)


	def new_forms_question(message):
		coach = Coach(message.chat.id)
		if re.match(r'\w+', message.text):
			coach.new_question_for_forms(message.text)
			msg = bot.send_message(coach.chat_id, f'Вопрос был успешно добавлен!\n'
												  f'Теперь у вас вопросов для анкетирования клиентов: {len(coach.extra()["questions_for_users"])}.')
			del_msgs('main_admin', coach)

		else:
			msg = bot.send_message(coach.chat_id, 'Неправильный формат вопроса! Попробуйте еще раз.')

		temp_msgs('main_admin', coach, msg)


	# потом переписать, запутался, кучу времени потратил на пустом месте (
	def user_questions_form(message):
		user = User(message.chat.id)
		question = list(temp_dct['users'][user.id]['question'].keys())[0]
		dt = list(temp_dct['users'][user.id]['question'].values())[0]
		if datetime.now() - dt < timedelta(minutes=5):
			lst = []
			for i in [[j['text'] for j in i] for i in keyboard(user).keyboard]:
				for j in i:
					lst.append(j)
			if not message.text in lst and not message.text[0] == '/':
				user.new_answer(question, message.text)
				msg = bot.send_message(user.chat_id, 'Спасибо за ответ! Отличного вам настроения.')
				del_msgs('user_form', user)
				temp_msgs('user_form', user, msg)
			else:
				current_menu = temp_dct['users'][user.id]['question']['menu']
				msg = general_dct['users'][user.id]['messages'][current_menu]()
				temp_msgs(current_menu, user, msg)
		else:
			current_menu = temp_dct['users'][user.id]['question']['menu']
			msg = general_dct['users'][user.id]['messages'][current_menu]()
			temp_msgs(current_menu, user, msg)

		temp_dct['users'].pop(user.id, None)


	def send_exercise_comment(message):
		coach = Coach(message.chat.id)
		if re.match(r'\w+', message.text):
			dct = temp_dct['coaches'][coach.id]['reports']
			text = dct['text']
			buttons = dct['buttons']
			for i in dct:
				if i.startswith('comment'):
					ex = Exercise(i.split()[1])
					dct[i] = message.text
			msg = bot.send_message(coach.chat_id, f'Комментарий по упражнению _{ex.name}_ успешно принят!\n\n' + text,
								   reply_markup=InlineKeyboardMarkup(row_width=1).add(*buttons,
																					  InlineKeyboardButton(
																						  text='Отменить и выйти',
																						  callback_data='users_reports_new_cancel')))
			del_msgs('main_admin', coach)
		else:
			msg = bot.send_message(coach.chat_id, 'Неверный формат комментария! Попробуйте заново.')
			bot.register_next_step_handler(msg, send_exercise_comment)
		temp_msgs('main_admin', coach, msg)

	@bot.message_handler(content_types=['photo', 'video', 'voice', 'document'], func=lambda message: coach_check(message))
	def receive_photo_from_coach(message):
		coach = Coach(message.chat.id)
		if coach.status.startswith('client_trainings_individual_send '):
			user = User(user_id=coach.status.split()[1])
			coach.status = 'registered'
			try:
				coach.set_coach()
			finally:
				file_name = message.document.file_name
				file_info = bot.get_file(message.document.file_id)
				downloaded_file = bot.download_file(file_info.file_path)
				with open(file_name, 'wb') as new_file:
					new_file.write(downloaded_file)
				plans, checking = excel_form_read(coach, user, file_name)
				if plans and checking:
					plans = {i: j for i, j in plans.items() if j and any(j)}
					text = ('\n' + '-' * 15 + '\n').join([f'🏋️‍♀️ План тренировки №{i}\n' + '\n---\n'.join(
						[f'▫️ *Упражнение №{plans[i].index(j) + 1}*\n' + j[0].description() + f"\n*Видео-отчет*: _{'да' if j[1] else 'нет'}_" for j in plans[i]]) for i in plans]) + \
						   '\n\nДля окончательной отправки задания укажите обязательные параметры: *сложность* и *длительность* тренировки, нажав на соответствующие кнопки.'
					temp_dct['coaches'][coach.id] = {'individual_plan': {int(i): {'exercises': plans[i],
																				  'duration': None,
																				  'rating': None} for i in
																		 plans.keys()}}
					buttons = [[InlineKeyboardButton(text=f'Тренировка №{int(i)} - сложность',
													 callback_data=f'client_trainings_plan rate {int(i)} {user.id}'),
								InlineKeyboardButton(text=f'Тренировка №{int(i)} - длительность',
													 callback_data=f'client_trainings_plan dur {int(i)} {user.id}')]
							   for i in plans]
					temp_dct['coaches'][coach.id]['individual_plan']['buttons'] = buttons
					menu = InlineKeyboardMarkup(row_width=1)
					for b in buttons:
						menu.add(*b)
					if len(text) < 3500:
						msg = bot.send_message(coach.chat_id, text, reply_markup=menu)
					else:
						splitted_text = util.smart_split(text, 3500)
						for i in splitted_text:
							msg_2 = bot.send_message(coach.chat_id, i, reply_markup=menu) if i == splitted_text[-1] else bot.send_message(coach.chat_id, i)
							temp_msgs('main_admin', coach, msg_2)
						msg = None

					if msg:
						del_msgs('main_admin', coach)
						temp_msgs('main_admin', coach, msg)
					if coach.tasks:
						for task in coach.tasks:
							if task.type_number == 2 and task.additional_info[0] == 'send_plan' and \
								task.additional_info[1] == user.id:
								task.delete(coach)
				else:
					msg = bot.send_message(coach.chat_id, 'Вы ошиблись при заполнении плана.\n'
														  'Попробуйте еще раз.')
					del_msgs('main_admin', coach)
					temp_msgs('main_admin', coach, msg)

		if coach.status.startswith('sending_receipt'):
			if message.content_type == 'photo':
				user = User(user_id=coach.status.split()[1])
				tariff = Tariff(coach.status.split()[2])
				payment_amount = int(coach.status.split()[3])
				coach.status = 'registered'
				receipt_image_id = message.photo[0].file_id
				try:
					coach.set_coach()
				finally:
					for task in coach.tasks:
						params = task.additional_info
						if task.type_number == 5 and int(params[0]) == int(user.id) and int(params[1]) == int(tariff.id):
							task.delete()
					user.pay_tariff(tariff)
					msg = bot.send_photo(user.chat_id, receipt_image_id, caption=f'Чек об оплате тарифа "{tariff.name}" на сумму {payment_amount}₽.')
					bot.send_message(user.chat_id,
									 f'Вам успешно начислен тариф *"{tariff.name}"*.\n\nТренер: *{coach.fullname}*.')
					bot.send_message(coach.chat_id, f'Тариф *"{tariff.name}"* успешно начислен клиенту *{user.fullname}*.')

					del_msgs('main_admin', coach)
					del_msgs('paying', user)
					temp_msgs('paying', user, msg)

		if coach.status == 'creating_plan media':
			coach.status = 'registered'
			try:
				coach.set_coach()
			finally:
				msg_type = message.content_type
				if msg_type == 'video':
					temp_dct['coaches'][coach.id]['creating_plan']['video'] = message.video[0].file_id
				elif msg_type == 'voice':
					temp_dct['coaches'][coach.id]['creating_plan']['audio'] = message.voice[0].file_id
				elif msg_type == 'photo':
					temp_dct['coaches'][coach.id]['creating_plan']['image'] = message.photo[0].file_id
				msg = temp_dct['coaches'][coach.id]['creating_plan']['msg']()
				del_msgs('main_admin', coach)
				temp_msgs('main_admin', coach, msg)

		if coach.status.startswith('creating_exercise'):
			item = coach.status.split()[1]
			exercise = Exercise(coach.status.split()[2], coach=False)
			coach.status = 'registered'
			try:
				coach.set_coach()
			finally:
				if item == 'video':
					temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['video'] = \
					message.video[0].file_id
				elif item == 'image':
					temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['image'] = \
					message.photo[0].file_id
				elif item == 'audio':
					temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['audio'] = \
					message.voice[0].file_id
				msg = temp_dct['coaches'][coach.id]['creating_plan']['exercises'][exercise.exercises_id]['msg']()
				del_msgs('main_admin', coach)
				temp_msgs('main_admin', coach, msg)

		elif coach.status == 'sending_coach_photo':
			if message.content_type == 'photo':
				with database() as connection:
					with connection.cursor() as db:
						db.execute(f"UPDATE coachs SET photo = '{message.photo[0].file_id}' WHERE id = {coach.id}")
						connection.commit()
				coach.status = 'registered'
				try:
					coach.set_coach()
				finally:
					days = [InlineKeyboardButton(text=f'{days_of_week[i].title()}', callback_data=f'coach_schedule_day {i}')
							for i in days_of_week]
					coach_schedule_days_menu = InlineKeyboardMarkup(row_width=1).add(*days)
					import json
					json.dump({i: [] for i in days_of_week}, open(f'coach_register {coach.id}.json', 'w', encoding='utf-8'),
						 ensure_ascii=False)
					msg = bot.send_message(message.chat.id,
										   '*Теперь вам нужно* составить свое расписание. Выберите день недели, чтобы выбрать рабочие часы.\n\n'
										   '*Они будут* _доступны клиентам_ для записи. Оставьте *без изменений* день/время, чтобы они были _недоступными_ для записи.\n\n',
										   reply_markup=coach_schedule_days_menu)
					del_msgs('coach_register', coach)
					temp_msgs('coach_register', coach, msg)


	@bot.message_handler(content_types=['video'], func=lambda message: blacklist_checking(message))
	def save_video(message):
		user = User(message.chat.id)
		if message.video:

			if user.status.startswith('sending_individual_plan_report'):
				ex = Exercise(user.status.split()[1])
				video_id = message.video.file_id
				dct = temp_dct['users'][user.id]['individual_plan']
				try:
					dct['reports'][ex.coachs_exercises_id] = video_id
				except KeyError:
					dct['reports'] = {ex.coachs_exercises_id: video_id}
				text = dct['message']
				buttons = dct['buttons']
				plan = dct['plan']
				report_exs = dct['report_exs']
				uploaded_videos = ', '.join([Exercise(i).name for i in dct['reports']])
				if len(dct['reports']) != len(report_exs):
					text += f'\n\n‼️ *Видео по упражнению* _{ex.name}_ *успешно принято!*\n\n' \
							f'Видео загружены по упражнениям: *{uploaded_videos}*'
				else:
					buttons.append(InlineKeyboardButton(text='✔️ Отправить!',
														callback_data=f'individual_trainings_tasks_end {plan.id} done'))
					text += '\n\nНажмите *"Отправить"*, чтобы отправить видео-отчет. Или отправьте видео по любому из упражнений заново.'
				menu = InlineKeyboardMarkup(row_width=1).add(*buttons)
				msg = bot.send_message(user.chat_id, text, reply_markup=menu)
				del_msgs('training_plan', user)
				temp_msgs('training_plan', user, msg)

			if user.status.startswith('sending_self_training_video_report '):
				exercise = Exercise(user.status.split()[1])
				video_id = message.video.file_id
				dt = datetime.fromtimestamp(float(user.status.split()[-1]))
				user.status = 'registered'
				user.set_user()
				coach = user.coach()
				training_self = user.training_self()[-1]
				training_plan = TrainingSelfPlan(user, training_self['training_plans_id'])
				time_checking = datetime.now() -  dt <= timedelta(minutes=10)
				if time_checking:
					user.new_training_report(training_plan, 'video', video_id, exercise=exercise)

					msg = bot.send_message(user.chat_id,
										   'Спасибо за отчет! Когда тренер проверит и подтвердит выполнение упражнения, тренировка будет зачтена.\n\n'
										   'Ожидайте.', reply_markup=keyboard(user))

					msg_2 = bot.send_video(coach.chat_id, video_id)
					msg_3 = bot.send_message(coach.chat_id,
											 f'Клиент *{user.fullname}* отправляет видео-отчет по тренировке из уровня подготовки "*{Level(training_plan.levels_id).name}*".\n\n'
											 f'Упражнение: "*{exercise.name}*".\n'
											 f'Кодовое слово: *{user.training_self()[-1]["code_word"]}* (должно быть произнесено на видео).\n\n'
											 f'*Зачтено ли* упражнение? Если да - клиенту зачтется самостоятельная тренировка, как выполненная.',
											 reply_markup=InlineKeyboardMarkup(row_width=1).add(
												 InlineKeyboardButton(text='Да',
																	  callback_data=f"self_trainings_credited {user.id} {training_plan.id} {exercise.coachs_exercises_id}"),
												 InlineKeyboardButton(text='Нет',
																	  callback_data=f"self_trainings_not_credited {user.id} {training_plan.id} {exercise.coachs_exercises_id}")
											 ))
					temp_msgs('training_self_check', coach, msg_2)
					temp_msgs('training_self_check', coach, msg_3)
				else:
					msg = bot.send_message(user.chat_id,
										   'К сожалению вы не успели отправить видео-отчет вовремя. После завершения тренировки на это дается 10 минут. В следующий раз точно успеете!')
				del_msgs('training_self', user)
				temp_msgs('training_self', user, msg)
