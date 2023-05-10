import datetime
from handlers.general import *
from handlers.other.additional_funcs import *
from classes.signing_up import *
from handlers.other.config import *
from telebot.types import ReplyKeyboardRemove
from classes.errors import *
from non_public.bot import developer_id
import os
from classes.training import *
from handlers.dates_additional import *
from handlers.other.menu import *
from handlers.other.config import forbidden_status


def training_types(user=None, tariff=None):
	types = {'personal': 'персонально', 'split': 'сплит', 'group': 'группа', 'personal_online': 'персонально онлайн', 'free': 'бесплатно (пробно)'}
	types_for_user = {'personal': 'персональные', 'split': 'сплит', 'group': 'групповые', 'personal_online': 'персональные онлайн', 'free': 'бесплатные (пробные)'}
	if user:
		sessions = user.subscription_plan['sessions_count']
		if sessions:
			result = ', '.join([' — '.join([f'{types_for_user[i]}', str(sessions[i])]) for i in sessions if sessions[i]])
			return result
	if tariff:
		return '\n'.join([f'- _{types[i]}_: *{j}*' for i, j in tariff.sessions.items() if j])
	return types

# процесс для проверки состояний каждый час
def checking_every_hour(bot):
	while True:
		# ____________________________________________________________________________________________
		try:
			if datetime.now().hour == 9:
				with database() as connection:
					with connection.cursor() as db:
						db.execute(f"SELECT id FROM coachs")
						coachs_list = db.fetchall()

				if coachs_list:
					for c in coachs_list:
						try:
							coach = Coach(coach_id=c['id'])
						except:
							coach = None

						if coach:
							check_period = coach.period_check()
							if not check_period is None and check_period[1] is False and coach.status != 'indebted_coach': # если истек период действия тарифа тренера
								coach.status = 'indebted_coach'
								with database() as connection: # пишу вручную, чтобы не останавливалась функция из-за ошибки в методе Coach.set_coach()
									with connection.cursor() as db:
										db.execute(f"UPDATE users SET status='indebted_coach' WHERE id = {coach.user_id}")
									connection.commit()
								bot.send_message(coach.chat_id, f'Период действия вашего тарифа закончился.\n'
																f'Ваш долг по оплате работы сервиса на сегодня: {check_period[0]}₽.\n\n'
																f"Для оплаты просто перейдите по ссылке: <a href='https://google.com'>тестовая ссылка</a>.", parse_mode='HTML',
												 reply_markup=ReplyKeyboardRemove())
							settings = coach.extra()
							if settings and not forbidden_status(coach):
								settings = settings['bot_checking_funcs']
								# coach_tasks_reminding - напоминание тренеру о его текущих и просроченных задачах
								if settings['coach_tasks_reminding']:
									if coach.tasks:
										out = coach.tasks_description()
										bot.send_message(coach.chat_id, f'❗️ Текущие _незавершенные задачи_:\n\n{out}.\n\nВовремя проверяйте их в меню *"Общее"* 👉 *"Текущие задачи"* и выполняйте!\n'
														 f'Это влияет на ваш рейтинг среди клиентов.')
								if coach.tasks:
									late_tasks = [task for task in coach.tasks if not task.check_period()]
									if late_tasks:
										for task in late_tasks:
											task.delete(coach)
											if settings['coach_tasks_reminding']:
												bot.send_message(coach.chat_id, f'Очень плохо! Задача от *{task.start_date()}* _("{task.description}")_ была просрочена и больше недоступна для выполнения.')
								with database() as connection:
									with connection.cursor() as db:
										db.execute(f"SELECT chat_id FROM users WHERE current_coach_id = {coach.id}")
										data = db.fetchall()
								if data:
									for u in data:
										user = User(u['chat_id'])
										user_settings = user.notifications()
										# user_tariff_ended_reminding - напоминание клиентам об окончании периода действия тарифа
										if user.subscription_plan['period'] and user.subscription_plan['period'] < date.today() and not user.subscription_plan['tariff_id'] is None:
											user.subscription_plan['sessions_count'] = {i: None for i in user.subscription_plan['sessions_count']}
											user.subscription_plan['tariff_id'] = None
											user.subscription_plan['period'] = None
											user.subscription_plan['start_timestamp'] = None
											user.set_user(subscription_plan=True)
											if settings['user_tariff_ended_reminding']:
												try:
													bot.send_message(user.chat_id, '🥲 К сожалению, срок действия вашего тарифа истек сегодня.\n\n'
																		  '🙂 Воспользуйтесь меню "Оплата", чтобы продлить его.', reply_markup=keyboard(user))
												except:
													pass

										# user_today_session_reminding - напоминание клиентам о том, что сегодня состоится тренировка (если она есть в расписании)
										if user_settings and user_settings['reminding_today_session']:
											if not user_settings['reminded_today_session'] or user_settings['reminded_today_session'] != date.today():
												with database() as connection:
													with connection.cursor() as db:
														db.execute(f"SELECT time FROM schedules WHERE coachs_id = {coach.id} AND users_id = {user.id} AND date = CURDATE()")
														data = db.fetchone()
														if data:
															today = date.today()
															time_checking = datetime(today.year, today.month, today.day, int(str(data['time'])[:2].replace(':', ''))) - datetime.now() > timedelta(hours=2)
															if time_checking:
																hour = data['time']
																bot.send_message(user.chat_id, f'😀 *Доброе утро*!\nСегодня у вас тренировка с тренером *{coach.fullname}* в _{str(hour)[:-3]}_.\n\n'
																							   f'Настроить напоминания всегда можно в меню *"Мои тренировки"* 👉 *"Настройки бота"*.', reply_markup=keyboard(user))
																user_settings['reminded_today_session'] = date.today().isoformat()
																user.notifications(set=True, updated_notifications=user_settings)


										# напоминание (только по будням) клиентам о том, что у них есть оплаченные тренировки, но нет записи (настройка на стороне клиента)
										if user_settings and user_settings['reminding_left_sessions']:
											if not datetime.today().isoweekday() in [6, 7]:
												if user.sessions_left() and not user.upcoming_sessions():
													bot.send_message(user.chat_id, '😀 *Доброе утро*!\n' +\
																			  'У вас нет предстоящих тренировок. Не забывайте записываться на них через меню *Записаться на тренировку*!\n\n' +\
																			  f'☑️ Сейчас у вас занятий на балансе: *{training_types(user)}*\n' +\
																			  (f'❗️ Их срок действия: *до {user.subscription_plan["period"]}*.\n' if not user.subscription_plan["period"] is None else '') + '\n' +\
																				   f'Настроить напоминания всегда можно в меню *"Мои тренировки"* 👉 *"Настройки бота"*.', reply_markup=keyboard(user))

										# user_current_tasks_reminding - напоминание клиентам, выполняющим полученное задание от тренера и имеющим текущие задачи, о, непосредственно, задачах
										# + автоудаление просроченных задач
										tasks = user.tasks
										if tasks:
											for task in tasks:
												if not task.check_period():
													task.delete(user)
													if user_settings['reminding_current_tasks'] and not user.subscription_plan['tariff_id'] is None:
														bot.send_message(user.chat_id,
																		 f'Задача от _{task.start_date()}_ (тип задачи: _"{task.type}"_, описание: _{task.description}_) была просрочена!\n\n'
																		 f'Она больше недоступна для выполнения.\n\n'
																		 'Напоминание об этом всегда можно настроить в меню *"Мои тренировки"* 👉 *"Настройки бота"*.',
																		 reply_markup=keyboard(user))
											if tasks:
												if user_settings['reminding_current_tasks'] and not user.subscription_plan['tariff_id'] is None:
													bot.send_message(user.chat_id,
																	 'У вас есть текущие незавершенные задачи!\n'
																	 'Вовремя проверяйте их и выполняйте в меню *"Мои тренировки"* 👉 *"Текущие задачи"*.\n\n'
																	 'Напоминание об этом всегда можно настроить в меню *"Мои тренировки"* 👉 *"Настройки бота"*.',
																	 reply_markup=keyboard(user))

										# user_online_training_reports_reminding - напоминание клиентам об отправке отчетов по индивидуальным тренировкам
										if settings['user_online_training_reports_reminding']:
											tasks = user.tasks
											if tasks:
												flag = False
												for task in tasks:
													days_check = abs((datetime.today() - (task.date + task.period)).days)
													if task.type_number == 1 and days_check < 3:
														if user.check_period():
															user_perms = user.permissions
															if 'individual_trainings' in user_perms:
																flag = True
												if flag is True:
													bot.send_message(user.chat_id,
																	 '❕ Проверьте, отправлены ли все нужные *видео-отчеты* по индивидуальным заданиям от тренера через меню *"Мои тренировки"* 👉 *"Индивидуальные занятия"*.', reply_markup=keyboard(user))



			# today_coach_schedule - расписание для тренера с утра на текущий день
			if datetime.now().hour == 7:
				with database() as connection:
					with connection.cursor() as db:
						db.execute(f"SELECT id FROM coachs")
						coachs_list = db.fetchall()
				if coachs_list:
					for c in coachs_list:
						try:
							coach = Coach(coach_id=c['id'])
							settings = coach.extra()
						except:
							coach = None
							settings = None
					if coach and not forbidden_status(coach) and settings:
						settings = settings['bot_checking_funcs']
					if settings['today_coach_schedule']:
						today_schedule = ScheduleDay(coach, date.today()).get_schedule()
						if today_schedule:
							types = {'personal': 'персонально', 'split': 'сплит', 'group': 'группа',
									 'personal_online': 'персонально онлайн', 'free': 'бесплатно (пробно)'}
							lst = []
							for hour in today_schedule:
								clients = [i['user'].fullname + (f' (комментарий: _"{i["comment"]}"_)' if i['comment'] else '') + f' - _{types[hour.session_type]}_' for i in hour.clients]
								lst.append(f"- *{hour.time}:00* : " + ', '.join(clients))
							bot.send_message(coach.chat_id, '😃 *С добрым утром! Ваше расписание на сегодня*.\n\n' + '\n'.join(sorted(set(lst), key=lambda string: int(string[3:5]) if not ':' in string[3:5] else int(string[3:4]))))
						else:
							bot.send_message(coach.chat_id, '😇 *Доброго утра!* Расписание на сегодня пусто!',
											 parse_mode='Markdown')


			# очистка сообщений ночью, чтобы не засорялся чат
			if datetime.now().hour == 4:
				with database() as connection:
					with connection.cursor() as db:
						db.execute('SELECT * FROM temp_messages')
						messages = db.fetchall()
						for m in messages:
							try:
								bot.delete_message(m['chat_id'], m['message_id'])
							except:
								continue
						db.execute('TRUNCATE TABLE temp_messages')
						# statuses from handlers.other.config
						checking_statuses = ', '.join(["'" + i + "'" for i in statuses])
						db.execute(f"UPDATE users SET status = 'registered' WHERE status NOT IN ({checking_statuses})")
					connection.commit()
				if os.path.exists('data/temp_data/temp_dict.pickle'):
					os.remove('data/temp_data/temp_dict.pickle')
				if os.path.exists('data/temp_data/general_dict.pickle'):
					os.remove('data/temp_data/general_dict.pickle')
		except:
			bot.send_message(developer_id, f'Произошла ошибка: checking.py, {datetime.now().isoformat()}.\n'
									   f'Добавлена в лог-файл.')
			Error().log()
		finally:
			sleep(3600)


# процесс для проверки состояний каждую минуту
def checking_every_minute(bot):
	while True:
		try:
			with database() as connection:
				with connection.cursor() as db:
					db.execute("SELECT * FROM blacklist")
					blocked_list = db.fetchall()
					if blocked_list:
						blocked_list = [f"'{i['users_chat_id']}'" for i in filter(lambda x: x['blocked_datetime'] + timedelta(days=1) < datetime.now(), blocked_list)]
						if blocked_list:
							db.execute(f"DELETE FROM blacklist WHERE users_chat_id IN ({', '.join(blocked_list)})")
							connection.commit()
							for chat_id in blocked_list:
								chat_id = int(chat_id[1:-1])
								bot.send_message(chat_id, 'Вы были разблокированы.\n\n'
														  'Ведите себя хорошо!')
								sleep(1)
					forbidden_statuses = statuses
					users_with_forbidden_statuses = []
					db.execute(f"SELECT chat_id, status FROM users WHERE status != 'registered'")
					users_to_list = db.fetchall()
					if users_to_list:
						users_to_list = [(i['chat_id'], i['status']) for i in users_to_list]
						for chat_id, status in users_to_list:
							if any([status.startswith(forbidden_status) for forbidden_status in forbidden_statuses]):
								users_with_forbidden_statuses.append(chat_id)
					if users_with_forbidden_statuses:
						users_with_forbidden_statuses = [User(i) for i in users_with_forbidden_statuses]
						for u in users_with_forbidden_statuses:
							if u.status in ['individual_training', 'self_training']:
								user_training_self = sorted([i for i in u.training_self() if not i["training_started_at"] is None], key=lambda x: x['training_started_at'], reverse=True)[0]
								training_plan = TrainingSelfPlan(u, user_training_self['training_plans_id'])
								if datetime.now() - training_plan.training_started_at > timedelta(minutes=training_plan.duration):
									u.status = 'registered'
									u.set_user()
									del_msgs('training_plan', u)
									del_msgs('training_self', u)
									del_msgs('my_trainings', u)
									del_msgs('individual_training_exercise_info', u)
									bot.send_message(u.chat_id, f'К сожалению, вы не успели справиться с {"индивидуальным" if training_plan.type == "individual" else "самостоятельным"} заданием.\n'
																f'Время выполнения было ограничено до _{current_time(training_plan.training_started_at + timedelta(minutes=training_plan.duration))}_.\n\n'
																f'Тренировка не будет засчитана.')
									tasks = u.tasks
									for task in tasks:
										if task.additional_info[0] == training_plan.id:
											task.delete()
							if any([u.status.startswith('sending_individual_plan_report'), u.status.startswith('sending_self_training_video_report')]):
								if datetime.now() - u.last_callback > timedelta(hours=2):
									user_training_self = \
									sorted([i for i in u.training_self() if not i["training_started_at"] is None],
										   key=lambda x: x['training_started_at'], reverse=True)[0]
									training_plan = TrainingSelfPlan(u, user_training_self['training_plans_id'])
									u.status = 'registered'
									u.set_user()
									del_msgs('training_self', u)
									del_msgs('training_plan', u)
									del_msgs('individual_training_exercise_info', u)
									del_msgs('my_trainings', u)
									bot.send_message(u.chat_id, 'Вы слишком долго пытались отправить видео по тренировке.\n'
																'Если нужно, попробуйте заново.')
									tasks = u.tasks
									for task in tasks:
										if task.additional_info[0] == training_plan.id:
											task.delete()
					db.execute(f"SELECT chat_id FROM users WHERE is_coach = {True}")
					coachs_list = db.fetchall()
					db.execute(f"SELECT chat_id FROM users WHERE is_coach = {False}")
					users_list = db.fetchall()
			if coachs_list:
				for c in coachs_list:
					try:
						coach = Coach(c['chat_id'])
						settings = coach.extra()
					except:
						coach = None
						settings = None

					if coach and not forbidden_status(coach) and settings:
						settings = settings['bot_checking_funcs']# если будут нужны настройки
						data = coach.clients()
						if data:
							for user in data:
								user_reminding = user.notifications()
								if not user_reminding is None and user_reminding['reminding_before_sessions']:
									if user.current_coach_id:
										today_schedule = ScheduleDay(coach, date.today()).get_schedule()
									# напоминание перед тренировкой (настройка на стороне клиента)
									# 0 - не напоминать, 1/2/3 - за сколько часов до тренировки напоминать
									# reminding_before_sessions
									if today_schedule:
										for hour in today_schedule:
											if hour.clients:
												if user.id in [i['user'].id for i in hour.clients]:
													if not user_reminding['reminded_before_session'] or user_reminding['reminded_before_session'] != date.today():
														if hour.time - datetime.today().hour == user_reminding['reminding_before_sessions']:
																bot.send_message(user.chat_id, f'😀 Напоминаем!\n\n'
																								f'Сегодня у вас тренировка в *{hour.time}:00*.\n\n'
																							   f'Настроить напоминания всегда можно в меню *"Мои тренировки"* 👉 *"Настройки бота"*.', reply_markup=keyboard(user))
																user_reminding['reminded_before_session'] = date.today().isoformat()
																user.notifications(set=True, updated_notifications=user_reminding)
		except:
			bot.send_message(developer_id, f'Произошла ошибка: checking.py, {datetime.now().isoformat()}.\n'
									   f'Добавлена в лог-файл.')
			Error().log()
		finally:
			sleep(60)

spams = {}

def spams(bot):
	### anti-spam func for messages from user
	@bot.message_handler(func=lambda message: blacklist_checking(message))
	def is_spam(msg):
		anti_spam(msg)


