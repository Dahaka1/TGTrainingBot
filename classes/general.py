from __future__ import annotations

import random
from json import dumps, loads
from typing import NoReturn, Optional, Union
from store import *
from datetime import datetime, date, timedelta
from statistics import mean
from classes.training import *
from classes.users_tasks import *
import re
import pandas as pd


class Coach:
	def __init__(self, chat_id:Optional[str,int]=None, coach_id:Optional[str,int]=None):
		"""
		Не сделал наследование от Users - когда делал классы с нуля, еще не знал про такую возможность.
		В идеале потом надо переписать
		"""
		with database() as connection:
			with connection.cursor() as db:
				if chat_id:
					db.execute("SELECT coachs.id AS coachs_id, coachs.users_id, users.chat_id, users.username, users.fullname, users.status, "
							   f"coachs.tasks, coachs.tags, coachs.photo, coachs.description FROM users JOIN coachs ON coachs.users_id = users.id WHERE users.chat_id = '{chat_id}'")
				if coach_id:
					db.execute(
						"SELECT coachs.id AS coachs_id, coachs.users_id, users.chat_id, users.username, users.fullname, users.status, "
						f"coachs.tasks, coachs.tags, coachs.photo, coachs.description FROM users JOIN coachs ON coachs.users_id = users.id WHERE coachs.id = '{coach_id}'")
				data = db.fetchall() if chat_id or coach_id else None
				data = data[0] if data else None
				self.id = data['coachs_id']
				self.user_id = data['users_id']
				self.chat_id = data['chat_id']
				self.username = data['username']
				self.fullname = data['fullname']
				self.status = data['status']
				self.tags = data['tags'].split(',') if data['tags'] else None
				self.photo = data['photo']
				self.description = data['description']
				tasks = loads(data['tasks']) if data['tasks'] else None
				if tasks:
					self.tasks = []
					for num in tasks:
						t = Task(num)
						t.date = datetime.fromisoformat(next(iter(tasks[num].keys())))
						t.description = next(iter(next(iter(tasks[num].values())).keys()))
						t.additional_info = next(iter(next(iter(tasks[num].values())).values()))
						self.tasks.append(t)
				else:
					self.tasks = None

				db.execute(f"SELECT id FROM coachs_tariffs WHERE coachs_id = {self.id}")
				current_tariffs = db.fetchall()
				self.tariffs = [Tariff(tariff_id=i['id']) for i in current_tariffs] if current_tariffs else None

	def set_tasks(self) -> NoReturn:
		"""
		Сделал дополнительно для задач, чтоб не париться постоянно про ошибку хотя бы при их обновлении
		"""
		with database() as connection:
			with connection.cursor() as db:
				tasks = {}
				if self.tasks:
					for t in self.tasks:
						tasks[t.type_number] = {t.date.isoformat(): {t.description: t.additional_info}}
				db.execute("SET @@sql_mode = 'NO_BACKSLASH_ESCAPES'")
				db.execute(f"UPDATE coachs SET tasks = '{dumps(tasks, ensure_ascii=False) if self.tasks else dumps({})}' WHERE id = '{self.id}'")
			connection.commit()

	def tasks_description(self) -> Optional[str]:
		if self.tasks:
			return '\n\n'.join([f'❕ *Задача от {task.start_date()}*:\n- {task.type}: _{task.description}_\nСрок действия до: _{task.end_date()}_.' for task in self.tasks])

	def set_coach(self) -> NoReturn:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"UPDATE users SET status = '{self.status}' WHERE id = {self.user_id}")
				# непонятная ошибка, не записывает данные в БД, если после коммита не вызвать close, но на close ругается тоже, якобы соединение уже закрыто
				connection.commit()
				connection.close()

	def period_check(self) -> Optional[tuple[bool, int]]:
		"""
		По умолчанию, в базовом тарифе, период действия тарифа тренера будет 30 дней
		:return: размер задолженности, проверка на период действия тарифа
		"""
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_subscription_plan WHERE coachs_id = {self.id}")
				plan = db.fetchone()
				if plan:
					return plan['debt'], plan['end_date'] > date.today()


	def salary(self) -> Optional[list[dict]]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM payments WHERE coachs_id = {self.id}")
				payments = db.fetchall()
				if payments:
					return payments

	def working_description(self):
		form = self.form()
		def tariff_training_types(tariff):
			types = {'personal': 'персонально', 'split': 'сплит', 'group': 'группа',
					 'personal_online': 'персонально онлайн', 'free': 'бесплатно (пробно)'}
			return '\n'.join([f'- _{types[i]}_: *{j}*' for i, j in tariff.sessions.items() if j])
		types = {'online': 'Онлайн', 'offline': 'Оффлайн (очно)',
				 'sex': 'Пол', 'city': 'Город', 'male': 'Мужчина', 'female': 'Женщина',
				 'age': 'Возраст'}
		tariffs = '\n----------\n'.join(
			[f'💰 Тариф "*{i.name}*"\n- *Количество тренировок*:\n{tariff_training_types(tariff=i)}\n- *Стоимость*: _{i.cost}_' for i in
			 self.tariffs]) if self.tariffs else '_пока нет_'
		text = f'🏃 *{self.fullname}*\n*Режим работы*: _{", ".join([types[i].lower() for i in form["working_type"].split(";")])}_\n*Направления работы*: _{", ".join(self.tags)}_\n\n*Описание*: _{self.description}_\n\n*Город*: _{form["city"]}_\n' \
			   f'*Адрес места работы:* _{form["gym_address"]}_\n*Телефон для связи:* _{form["phone_number"]}_\n\n*Доступные тарифы*:\n{tariffs}\n\n' \
			   f'*Рейтинг тренера*:\n{self.rating(output=True)}'
		return text


	def rating(self, output=False, raw=False, user=None, dct=None):
		with database() as connection:
			with connection.cursor() as db:
				if user and dct:
					db.execute(f"UPDATE coachs_feedbacks SET rating = {dct['rating']}, work_results = {dct['work_results']}, responsibility = {dct['responsibility']} WHERE coachs_id = {self.id} AND users_id = {user.id}")
					connection.commit()
					return True
				else:
					db.execute(f"SELECT * FROM coachs_feedbacks WHERE coachs_id = {self.id}")
					feedbacks = db.fetchall()
					if raw:
						return feedbacks
		if feedbacks and any([i['rating'] for i in feedbacks]):
			# коэффициент объективности придумал такой - 60 дней работы с тренером нужно для 100% объективного результата от клиента
			ratio = [(date.today() - i['cooperation_start_day']).days/60 for i in feedbacks if any([i['rating'], i['work_results'], i['responsibility']])]
			result = {"rating": round(mean([i['rating'] for i in feedbacks if i['rating']])),
					"work_results": round(mean([i['work_results'] for i in feedbacks if i['work_results']])),
					"responsibility": round(mean([i['responsibility'] for i in feedbacks if i['responsibility']])),
					"objectivity_ratio": mean([i if i <= 1 else 1 for i in ratio])}
			if not output:
				return result
			else:
				return f'- *Общий рейтинг*: _{result["rating"]}_\n- *Результаты клиентов*: _{result["work_results"]}_\n- *Ответственность*: _{result["responsibility"]}_\n- *Объективность отзывов*: {int(result["objectivity_ratio"] * 100)}%\n\n' \
					   f'- _примечание_: если _объективность отзывов_ небольшая - не пугайтесь, скорее всего тренер просто работает недавно (она, в частности, зависит от среднего срока работы клиентов с тренером).'
		else:
			if output:
				return '_оценок тренера пока нет_'

	def form(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_forms WHERE coachs_id = {self.id}")
				form = db.fetchall()
				if form:
					form = form[0]
					form['phone_number'] = (re.sub(r'\+?[78](\d{3})(\d{3})(\d\d)(\d\d)', r'+7 (\1) \2-\3-\4', str(form['phone_number']))) if str(form["phone_number"]).startswith("7") else form["phone_number"]
					return form


	def clients(self) -> Optional[list[User]]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM users WHERE current_coach_id = {self.id}")
				clients = db.fetchall()
		if clients:
			return sorted([User(i) for i in [j['chat_id'] for j in clients]], key=lambda x: x.fullname)

	def clients_for_menu(self) -> Optional[list[tuple]]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT fullname, id, last_callback FROM users WHERE current_coach_id = {self.id}")
				clients = db.fetchall()
				if clients:
					return [(i['fullname'], i['id'], i['last_callback']) for i in clients]

	def clients_training_reports(self, objects:bool=False) -> Optional[list[TrainingReport], dict]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM training_reports WHERE coachs_id = {self.id} ORDER BY report_date DESC")
				reports = db.fetchall()
				if reports:
					if not objects:
						return reports
					else:
						return [TrainingReport(User(user_id=i['users_id']), i['report_date']) for i in reports]


	def subscription_plan(self, updated_dct: dict = None) -> Optional[dict]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_subscription_plan WHERE coachs_id = {self.id}")
				subscription_plan = db.fetchall()
				if subscription_plan:
					if not updated_dct:
						return subscription_plan[0]
					else:
						db.execute(f"UPDATE coachs_subscription_plan SET debt = {updated_dct['debt']}, "
								   f"purchase_date = '{updated_dct['purchase_date']}', end_date = '{updated_dct['end_date']}'"
								   f" WHERE coachs_id = {self.id}")
						connection.commit()

	def payments(self, updated_dct: dict = None):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_payments WHERE coachs_id = {self.id}")
				payments = db.fetchall()
				if payments:
					if not updated_dct:
						return payments[0]

	def new_payment(self, amount: int):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"INSERT INTO coachs_payments (coachs_id, payment_amount, payment_type) VALUES "
						   f"({self.id}, {amount}, 'prolongation')")
				connection.commit()


	def extra(self, set=False, updated_extra=None):
		with database() as connection:
			with connection.cursor() as db:
				if not set:
					db.execute(f"SELECT working_schedule, bot_checking_funcs, questions_for_users FROM coachs_extra WHERE coachs_id = {self.id}")
					dct = db.fetchall()
					if dct:
						dct = dct[0]
						for i in dct:
							if dct[i]:
								if i != 'questions_for_users':
									dct[i] = loads(dct[i])
								else:
									dct[i] = dct[i].split(';')
						return dct
				else:
					for item in updated_extra:
						if type(updated_extra[item]) == dict:
							updated_extra[item] = dumps(updated_extra[item], ensure_ascii=False)
						updated_extra['questions_for_users'] = ';'.join(updated_extra['questions_for_users']) if updated_extra['questions_for_users'] else None
					# одним запросом не получается, не могу убрать экранирование в строке :(
					for i in updated_extra:
						item = f"'{updated_extra[i]}'" if updated_extra[i] else 'NULL'
						db.execute(f"UPDATE coachs_extra SET {i} = {item} WHERE coachs_id = {self.id}")

					connection.commit()

	def working_schedule_training_types(self):
		session_types_amount = {
			'split': 0,
			'group': 0,
			'personal': 0,
			'personal_online': 0,
			'free': 0
		}
		schedule = self.extra()['working_schedule']
		for day in schedule:
			hours = schedule[day]
			for hour in hours:
				training_type = next(iter(hour.values()))
				session_types_amount[training_type] += 1
		return session_types_amount


	def questions_form(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT questions_for_users FROM coachs_extra WHERE coachs_id = {self.id}")
				lst = db.fetchall()
				if lst and lst[0]['questions_for_users']:
					return lst[0]['questions_for_users'].split(';')


	def questions_form_answered(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM users_forms WHERE coachs_id = {self.id}")
				answers = db.fetchall()
				if answers:
					return answers


	def new_question_for_forms(self, text:str) -> bool:
		questions = self.extra()['questions_for_users'] or []
		if not text in questions:
			questions.append(text)
			questions = ';'.join(questions)
			with database() as connection:
				with connection.cursor() as db:
					db.execute(f"UPDATE coachs_extra SET questions_for_users = '{questions}' WHERE coachs_id = {self.id}")
					connection.commit()
					return True
		return False

	def delete_question_for_forms(self, number:int) -> None:
		questions = list(enumerate(self.extra()['questions_for_users'], 1))
		for i in questions:
			if i[0] == number:
				questions.remove(i)
		with database() as connection:
			with connection.cursor() as db:
				questions = "'" + ';'.join([i[1] for i in questions]) + "'" if questions else "NULL"
				db.execute(f"UPDATE coachs_extra SET questions_for_users = {questions} WHERE coachs_id = {self.id}")
				connection.commit()


	def promotions(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_promotions WHERE coachs_id = {self.id}")
				promotions = db.fetchall()
				if promotions and any(promotions):
					return promotions

	def levels(self, new=False, update=False, level_id=None, level_name=None, level_sessions_amount=None, level_description=None):
		with database() as connection:
			with connection.cursor() as db:
				if not new:
					if not update:
						if not level_id:
							db.execute(f"SELECT * FROM coachs_levels WHERE coachs_id = {self.id} ORDER BY id")
							levels = db.fetchall()
							if levels and any(levels):
								return levels
						else:
							db.execute(f"SELECT * FROM coachs_levels WHERE coachs_id = {self.id} AND id = {level_id}")
							level = db.fetchall()
							if level and any(level):
								return level[0]
					else:
						print(level_id)
						print(level_sessions_amount)
						db.execute(f"UPDATE coachs_levels SET "
								   f"level_sessions_amount = {level_sessions_amount} "
								   f"WHERE id = {level_id}")
						connection.commit()
				else:
					db.execute(f"INSERT INTO coachs_levels (coachs_id, level_name, level_sessions_amount, level_description) "
							   f"VALUES ({self.id}, '{level_name}', {level_sessions_amount}, '{level_description}')")
					connection.commit()

	def training_plans(self, new=False, level_id=None, plan_id=None, exercises=False, new_plan_dct=None):
		with database() as connection:
			with connection.cursor() as db:
				if level_id:
					db.execute(f"SELECT * FROM coachs_training_plans WHERE coachs_id = {self.id} AND coachs_levels_id = {level_id}")
					plans = db.fetchall()
					if plans and any(plans):
						return plans
				if plan_id:
					db.execute(f"SELECT * FROM coachs_training_plans WHERE id = {plan_id}")
					plan = db.fetchall()
					if plan and any(plan):
						if not exercises:
							return plan[0]
						else:
							plan = plan[0]
							return [Exercise(i) for i in loads(plan["session_exercises"])]
				if not plan_id and not level_id:
					db.execute(f"SELECT * FROM coachs_training_plans WHERE coachs_id = {self.id} AND session_type = 'self'")
					plans = db.fetchall()
					if plans and any(plans):
						return plans
				if new:
					db.execute(f"INSERT INTO coachs_training_plans (coachs_id, coachs_levels_id, session_exercises, session_duration, session_rate, session_type)"
							   f"VALUES ({self.id}, {new_plan_dct['coachs_levels_id']}, '{dumps(new_plan_dct['session_exercises'], ensure_ascii=False)}', "
							   f"{new_plan_dct['session_duration']}, {new_plan_dct['session_rate']}, '{new_plan_dct['session_type']}')")
					connection.commit()
					optional = {i: j for i, j in new_plan_dct.items() if i in ['informational_video', 'informational_image', 'informational_audio', 'session_terms']}
					if any(optional.values()):
						db.execute(f"SELECT id FROM coachs_training_plans WHERE coachs_id = {self.id} ORDER BY id DESC LIMIT 1")
						current_id = db.fetchall()[0]['id']
						for i in optional:
							if optional[i]:
								db.execute(f"UPDATE coachs_training_plans SET {i} = '{optional[i]}' WHERE id = {current_id}")
						connection.commit()


	def exercises(self, new=False, exercise_id=None, new_exercise_dct=None):
		with database() as connection:
			with connection.cursor() as db:
				if not exercise_id and not new:
					db.execute(f"SELECT * FROM coachs_exercises WHERE coachs_id = {self.id}")
					exercises = db.fetchall()
					if exercises and any(exercises):
						return exercises
				if exercise_id:
					db.execute(f"SELECT * FROM coachs_exercises WHERE coachs_id = {self.id} AND id = {exercise_id}")
					exercise = db.fetchall()
					if exercise and any(exercise):
						return exercise[0]
				if new:
					db.execute(f"INSERT INTO coachs_exercises (coachs_id, exercises_id, exercise_repeats) VALUES ({self.id}, {new_exercise_dct['exercises_id']}, {new_exercise_dct['exercise_repeats']})")
					connection.commit()
				optional = {i: j for i, j in new_exercise_dct.items() if i in ['exercise_terms', 'exercise_weight', 'exercise_sets', 'exercise_info_video', 'exercise_info_image', 'exercise_info_audio']}
				if any(optional):
					db.execute(f"SELECT id FROM coachs_exercises WHERE coachs_id = {self.id} ORDER BY id DESC LIMIT 1")
					current_id = db.fetchall()[0]['id']
					for i in optional:
						if optional[i]:
							if i in ['weight', 'sets']:
								db.execute(f"UPDATE coachs_exercises SET {i} = {optional[i]} WHERE id = {current_id}")
							else:
								db.execute(f"UPDATE coachs_exercises SET {i} = '{optional[i]}' WHERE id = {current_id}")
					connection.commit()

	def exercises_categories(self):
		with database() as connection:
			with connection.cursor() as db:
				tags = self.tags
				db.execute(f"SELECT * FROM exercises_groups")
				groups = db.fetchall()
				lst = []
				for i in groups:
					for j in tags:
						if j in i['group_tags'] and not i['id'] in lst:
							lst.append(i['id'])
				categories = []
				for i in lst:
					db.execute(f"SELECT id, category_name FROM exercises_categories WHERE exercises_group_id = {i}")
					c = db.fetchall()
					categories.append(c)
				return categories[0]

	def raw_exercises(self):
		categories = ', '.join(["'" + str(i) + "'" for i in [j['id'] for j in self.exercises_categories()]])
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT e.exercise_id, e.exercise_unit, e.exercise_name, c.category_name, c.id AS category_id FROM exercises AS e JOIN "
						   f"exercises_categories AS c ON e.exercises_category_id = c.id WHERE c.id IN ({categories}) ORDER BY exercise_name")
				exercises = db.fetchall()
				if exercises:
					return exercises

	def special_excel_form(self, user: User, update:bool=False, lst:list=None, delete=False) -> Optional[list]:
		with database() as connection:
			with connection.cursor() as db:
				if not delete:
					if not update:
						db.execute(f"SELECT base_exs FROM coachs_excel_forms WHERE coachs_id = {self.id} AND users_id = {user.id}")
						lst = db.fetchone()
						if lst:
							return lst['base_exs'].split(';')
					else:
						result = ';'.join(lst)
						if not self.special_excel_form(user):
							db.execute(f"INSERT INTO coachs_excel_forms (coachs_id, users_id, base_exs) VALUES ("
									   f"{self.id}, {user.id}, '{result}')")
						else:
							db.execute(f"UPDATE coachs_excel_forms SET base_exs = '{result}' WHERE coachs_id = {self.id} AND users_id = {user.id}")
						connection.commit()
				else:
					db.execute(f"DELETE FROM coachs_excel_forms WHERE coachs_id = {self.id} AND users_id = {user.id}")
					connection.commit()

	def leaderboard(self):
		all_reports = list(filter(lambda x: x.type == 'video' and x.credited, self.clients_training_reports(objects=True)))
		dct = {
			'weight': {},
			'repeats': {}
		}
		for rep in all_reports:
			ex = rep.exercise
			result = None
			if ex.unit and ex.weight:
				result = int(ex.weight) if str(ex.weight).endswith('.0') else ex.weight
				dct_2 = dct['weight']
			elif not ex.unit and not ex.repeats is None and not ex.sets is None and ex.sets != 0:
				result = ex.repeats
				dct_2 = dct['repeats']
			if not result is None:
				try:
					dct_2[ex.exercises_id].append((result, rep.user_id, rep.content))
				except KeyError:
					dct_2[ex.exercises_id] = [(result, rep.user_id, rep.content)]
		for ex in dct['weight']:
			lst = dct['weight'][ex]
			dct['weight'][ex] = max(lst, key=lambda x: x[0])
		for ex in dct['repeats']:
			lst = dct['repeats'][ex]
			dct['repeats'][ex] = max(lst, key=lambda x: x[0])
		return dct


	@staticmethod
	def set_coach_tariff(coach, tariff_name, description, sessions, period, canceling_amount, cost, users_permissions, update=False, current_tariff_id=None):
		if type(sessions) == dict:
			sessions = dumps(sessions, ensure_ascii=False)
		if type(users_permissions) == dict:
			users_permissions = dumps(users_permissions, ensure_ascii=False)
		with database() as connection:
			with connection.cursor() as db:
				if not update:
					db.execute(f"INSERT INTO coachs_tariffs (coachs_id, name, description, sessions, period, canceling_amount, cost, users_permissions) VALUES ({coach.id}, '{tariff_name}', '{description}', "
							   f"'{sessions}', {period}, {canceling_amount}, {cost}, '{users_permissions}')")
					connection.commit()
				else:
					db.execute(f"UPDATE coachs_tariffs SET name = '{tariff_name}', description = '{description}', sessions = '{sessions}', period = {period}, canceling_amount = {canceling_amount}, cost = {cost}, users_permissions = '{users_permissions}' WHERE coachs_id = {coach.id} AND id = '{current_tariff_id}'")
					connection.commit()

	@staticmethod
	def get_coach_tariff(coach, tariff_name):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT name, description, sessions, period, canceling_amount, cost, users_permissions FROM coachs_tariffs WHERE coachs_id = {coach.id} AND name = '{tariff_name}'")
				coach_tariffs = db.fetchall()
				return coach_tariffs[0] if coach_tariffs else None

	@staticmethod
	def get_all_coaches(with_forms=True, forms=False):
		with database() as connection:
			with connection.cursor() as db:
				if not forms:
					if with_forms:
						db.execute(f"SELECT coachs_forms.coachs_id FROM coachs_forms LEFT JOIN coachs ON coachs.id = coachs_forms.coachs_id")
						lst = db.fetchall()
						return [Coach(coach_id=i) for i in [i['coachs_id'] for i in lst]]
					else:
						db.execute(f"SELECT * FROM coachs")
						lst = db.fetchall()
						return [Coach(coach_id=i) for i in [i['id'] for i in lst]]
				elif forms:
					db.execute(f"SELECT * FROM coachs_forms")
					return db.fetchall()

class User:
	def __init__(self, chat_id:[str, int]=None, user_id:[str, int]=None):
		with database() as connection:
			with connection.cursor() as db:
				if user_id or chat_id:
					if chat_id:
						db.execute(f"SELECT * FROM users LEFT JOIN subscription_plan ON users.id = subscription_plan.users_id WHERE users.chat_id = '{chat_id}'")
					elif user_id:
						db.execute(
							f"SELECT * FROM users LEFT JOIN subscription_plan ON users.id = subscription_plan.users_id WHERE users.id = '{user_id}'")
					data = db.fetchall()
				else:
					data = None
				if data:
					if chat_id or user_id:
						data = data[0]
						self.id = data['id']
						self.chat_id = data['chat_id']
						self.fullname = data['fullname']
						self.username = data['username']
						self.registration_date = data['registration_date']
						self.is_coach = data['is_coach']
						self.status = data['status']
						self.last_callback = data['last_callback']
						self.current_coach_id = data['current_coach_id']
						self.subscription_plan: dict = {
							'tariff_id': data['tariff_id'],
							'sessions_count': loads(data['sessions_count']) if data['sessions_count'] else None,
							'canceled_sessions': loads(data['canceled_sessions']) if data['canceled_sessions'] else None,
							'period': data['period'],
							'start_timestamp': data['start_timestamp']
							}
						tasks = data['tasks']
						if tasks:
							tasks = loads(tasks)
							self.tasks = []
							for num in tasks:
								for dt in tasks[num]:
									t = Task(num)
									t.date = datetime.fromisoformat(dt)
									content = tasks[num][dt]
									t.description = next(iter(content.keys()))
									t.additional_info = next(iter(content.values()))
									self.tasks.append(t)
						else:
							self.tasks = None
						self.training_levels_id = data['training_levels_id']
						if self.subscription_plan['tariff_id']:
							perms = Tariff(tariff_id=self.subscription_plan['tariff_id']).users_permissions
							self.permissions = [i for i in perms if perms[i]]
						else:
							self.permissions = None
				else:
					self.id = None
					self.chat_id = chat_id
					self.fullname = None
					self.username = None
					self.registration_date = None
					self.is_coach = False
					self.status = None
					self.last_callback = None
					self.current_coach_id = None
					self.subscription_plan = {
						'tariff_id': None,
						'sessions_count': None,
						'canceled_sessions': None,
						'period': None,
						'start_timestamp': None
					}
					self.tasks = None
					self.training_levels_id = None
					self.permissions = None

	def __str__(self) -> Optional[str]:
		"""
		:return: returns description about subscription plan of user having current coach
		"""
		params = self.subscription_plan
		tariff = self.tariff()
		sessions = params['sessions_count']
		types = {'personal': 'персонально', 'split': 'сплит', 'group': 'группа',
				 'personal_online': 'персонально онлайн', 'free': 'бесплатно (пробно)'}
		sessions_out = ', '.join(
			[' — '.join([f'{types[i]}', str(sessions[i])]) for i in sessions if sessions[i]]) if any(
			sessions.values()) else 'нет'
		text = f'👤 *{self.fullname}*\n' \
			   f'- Текущий тариф: _"{tariff.name if tariff.name else "нет"}"_\n' \
			   f'- Дата покупки: _{params["start_timestamp"].strftime("%d.%m.%Y, %H:%M") if not params["start_timestamp"] is None else "нет"}_\n' \
			   f'- Период действия до: _{params["period"].strftime("%d.%m.%Y") if not params["period"] is None else "нет"}_\n' \
			   f'- Количество тренировок: _{sessions_out}_'
		if self.current_coach_id:
			return text


	def new_user(self) -> None:
		with database() as connection:
			with connection.cursor() as db:
				if self.username:
					db.execute(f"INSERT INTO users (chat_id, fullname, username, is_coach, status) VALUES ('{self.chat_id}', '{self.fullname}', '{self.username}', {self.is_coach}, '{self.status}')")
				else:
					db.execute(f"INSERT INTO users (chat_id, fullname, is_coach, status) VALUES ('{self.chat_id}', '{self.fullname}', {self.is_coach}, '{self.status}')")
				connection.commit()

	def coach(self) -> Coach:
		if self.current_coach_id:
			return Coach(coach_id=self.current_coach_id)

	def tariff(self) -> Tariff:
		if self.subscription_plan['tariff_id']:
			return Tariff(tariff_id=self.subscription_plan['tariff_id'])

	def block(self) -> NoReturn:
		self.id = self.id if self.id else 'NULL'
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"INSERT INTO blacklist (users_chat_id, users_id) VALUES ({self.chat_id}, {self.id})")
			connection.commit()

	def canceling_sessions_check(self) -> bool:
		counter = self.subscription_plan['canceled_sessions']
		period = self.subscription_plan['period'].isoformat()
		if not counter is None:
			if period in counter:
				return counter[period] < self.tariff().canceling_amount
		return True

	def past_sessions(self) -> Optional[list]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM schedules WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id} AND date < CURDATE()")
				past_sessions = db.fetchall()
				if past_sessions:
					return past_sessions

	def upcoming_sessions(self) -> Optional[list]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM schedules WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id} AND date >= CURDATE()")
				upcoming_sessions = db.fetchall()
				if upcoming_sessions:
					return upcoming_sessions

	def cancel_all_sessions(self) -> NoReturn:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"DELETE FROM schedules WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id}")
				connection.commit()

	def total_time_with_coach(self) -> Optional[timedelta]:
		if self.current_coach_id:
			start_date: date = next(filter(lambda x: x['users_id'] == self.id, self.coach().rating(raw=True)))['cooperation_start_day']
			td = date.today() - start_date
			return td

	def current_question(self) -> Optional[str]:
		chance = random.randint(1, 5)
		if chance in [1, 3]:
			if self.current_coach_id:
				coach = self.coach()
				questions = coach.questions_form()
				if questions:
					answers = list(filter(lambda i: i['users_id'] == self.id, coach.questions_form_answered() or []))
					answers_questions = [j['questions'] for j in answers]
					if not all([i in answers_questions for i in questions]):
						q = [i for i in questions if not i in answers_questions][0]
						return q + '\n\n🙂 Пожалуйста, напишите ответ прямо сейчас!'

	def new_answer(self, question:str, answer:str) -> None:
		with database() as connection:
			with connection.cursor() as db:
				question = question.split('\n\n')[0]
				db.execute(f"INSERT INTO users_forms (coachs_id, users_id, questions, answers) VALUES ({self.current_coach_id}, {self.id}, '{question}', '{answer}')")
				connection.commit()


	def level(self, training_plan:bool = False, last_training_session:bool = False) -> Optional[TrainingPlan, Level, dict]:
		if self.training_levels_id:
			if not training_plan and not last_training_session:
				level = Level(self.training_levels_id)
				if level.id:
					return level
			elif last_training_session:
				try:
					last_session = Level(self.training_levels_id(user=self)).user_training_self[-1]
				except:
					return None
				else:
					return last_session
			elif training_plan:
				level = Level(level_id=self.training_levels_id, user=self)
				trainings_history = self.training_self()
				level_plans = level.training_plans()
				if level_plans:
					try:
						return TrainingPlan([i['id'] for i in level_plans if not i['id'] in [j['training_plans_id'] for j in trainings_history]][0]) if trainings_history else TrainingPlan(level_plans[0]['id'])
					except IndexError:
						return None


	def discount(self, tariff: Tariff) -> Optional[int]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM users_discounts WHERE users_id = {self.id} AND coachs_id = {self.current_coach_id}")
				discount = db.fetchall()
				if discount:
					for i in discount:
						if i['tariff_id'] == tariff.id:
							if i['discount_period'] > datetime.now():
								return i['discount_amount']

	def new_global_form(self, data:UserGlobalPolling) -> NoReturn:
		with database() as connection:
			with connection.cursor() as db:
				db.execute()


	def self_trainings_history(self, training_type: str, history_type:str='coach') -> bool:
		"""
		:param history_type: coach/user (для user в будущем сделать просмотр истории тренировок со всеми тренерами, если уже нет текущего тренера)
		:param training_type: individual/self
		:return: Excel file for sending - creating successful or not
		"""
		history = sorted([i for i in (self.training_self(objects=True) if training_type == 'self' else self.training_self(objects=True, individual=True)) if i.type == training_type and
						  i.training_started_at],
						 key=lambda x: (x.levels_id, x.rate, len(x.exercises))) if self.training_self() else None
		if history:
			history = [i for i in history if i.coachs_id == self.current_coach_id]
			d = {'video': "видео", 'text': "текстовый", 'kg': 'кг', 'minutes': 'мин', 'hours': 'ч', 'cantimeters': 'см', 'meters': 'м',}
			df = pd.DataFrame(
				{'№': [history.index(i) + 1 for i in history],
				 'Дата тренировки': [datetime.strftime(i.training_started_at, '%d.%m.%Y') for i in history],
				 'Дата получения плана': [datetime.strftime(i.plan_received_at, '%d.%m.%Y') for i in
										  history],
				 'Тренировка зачтена': ["да" if i.training_plan_is_done else "нет" for i in history],
				 'Сложность': [str(i.rate) + '/10' for i in history],
				 "Длительность": [str(i.duration) + ' мин' for i in history],
				 'Упражнения': [', '.join([i.name[0].upper() + i.name[
															   1:] + f' {str(i.weight) + " (" + d[i.unit] + ") " if i.weight else ""}{str(i.sets) + "/" if i.sets else "/"}{i.repeats if not i.repeats is None else "максимум"}'
										   for i in [Exercise(l) for l in j.exercises]]) for j in history],
				 'Доп. условия': [i.terms if i.terms else "нет" for i in history],
				 'Отчеты': [', '.join([d[j.type] for j in i.reports() if any(i.reports_datetime)]) for i in
							history]
				 }
			)
			with pd.ExcelWriter(f'История тренировок {self.fullname}.xlsx') as writer:
				def align_center(x):
					return ['text-align: center' for i in x]

				df.style.apply(align_center, axis=0).to_excel(writer,
															  sheet_name='Самостоятельные тренировки',
															  index=False)

				# Auto-adjust columns' width
				for column in df:
					column_width = max(df[column].astype(str).map(len).max(), len(column))
					col_idx = df.columns.get_loc(column)
					if col_idx in [7, 8]:
						writer.sheets['Самостоятельные тренировки'].set_column(col_idx, col_idx,
																			   column_width + 15,
																			   cell_format=writer.book.add_format(
																				   {'text_wrap': True}))
					else:
						writer.sheets['Самостоятельные тренировки'].set_column(col_idx, col_idx,
																			   column_width + 5,
																			   cell_format=writer.book.add_format(
																				   {'text_wrap': True}))
			return True
		return False


	def pay_tariff(self, tariff: Tariff) -> NoReturn:
		default_sessions_count = {
			'personal': None,
			'split': None,
			'group': None,
			'personal_online': None,
			'free': None
		}
		self.subscription_plan['tariff_id'] = tariff.id
		if self.subscription_plan['period']:
			self.subscription_plan['period'] += timedelta(days=tariff.period)
		else:
			self.subscription_plan['period'] = date.today() + timedelta(days=tariff.period)
		self.subscription_plan['canceled_sessions'] = dumps({})
		self.subscription_plan['start_timestamp'] = date.today()
		sessions = self.subscription_plan['sessions_count'] or default_sessions_count
		for i in sessions:
			if i != 'free':
				if sessions[i]:
					sessions[i] += tariff.sessions[i]
				else:
					sessions[i] = tariff.sessions[i]
			else:
				sessions[i] = None
		self.subscription_plan['sessions_count'] = sessions
		self.set_user(subscription_plan=True)

		coach = self.coach()

		with database() as connection:
			with connection.cursor() as db:
				discount = self.discount(tariff)
				payment_amount = tariff.cost if not discount else tariff.cost * (100-discount)/100
				db.execute(f"INSERT INTO payments (coachs_id, users_id, tariff_id, payment_amount) VALUES "
						   f"({coach.id}, {self.id}, {tariff.id}, {payment_amount})")
				connection.commit()
				coach_plan = coach.subscription_plan()
				if coach_plan['debt']:
					coach_plan['debt'] += payment_amount * 0.05
				else:
					coach_plan['debt'] = payment_amount * 0.05
				coach.subscription_plan(updated_dct=coach_plan)


	@staticmethod
	def new_user_additional_step(user):
		default_sessions_count = {
			'personal': None,
			'split': None,
			'group': None,
			'personal_online': None,
			'free': None
		}

		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"INSERT INTO subscription_plan (users_id, sessions_count) VALUES ({user.id}, '{dumps(default_sessions_count)}')")
				connection.commit()

# без промо
	def set_user(self, subscription_plan: bool = False):
		with database() as connection:
			with connection.cursor() as db:
				if subscription_plan:
					dct = {i: dumps(self.subscription_plan[i], ensure_ascii=False) if type(self.subscription_plan[i]) == dict else self.subscription_plan[i] for i in self.subscription_plan}
					db.execute(f"UPDATE subscription_plan SET tariff_id = {dct['tariff_id'] if dct['tariff_id'] else 'NULL'} WHERE users_id = {self.id}")
					dct.pop('tariff_id')
					db.execute(f"UPDATE subscription_plan SET " + ', '.join([f'{i} = ' + "'" + (str(dct[i]) if not i in ['period', 'start_timestamp'] else datetime.strftime(dct[i], ('%Y-%m-%d' if i == 'period' else '%Y-%m-%d %H:%M:%S'))) + "'" if dct[i] else f'{i} = NULL' for i in dct]) + f' WHERE users_id = {self.id}')
				tasks = {}
				if self.tasks:
					for t in self.tasks:
						if not t.type_number in tasks:
							tasks[t.type_number] = {t.date.isoformat(): {t.description: t.additional_info}}
						else:
							tasks[t.type_number][t.date.isoformat()] = {t.description: t.additional_info}
				db.execute("SET @@sql_mode = 'NO_BACKSLASH_ESCAPES'")
				db.execute(f"UPDATE users SET is_coach = {self.is_coach}, status = '{self.status}', tasks = '{dumps(tasks, ensure_ascii=False)}', current_coach_id = {self.current_coach_id if self.current_coach_id else 'NULL'}, training_levels_id = {self.training_levels_id if self.training_levels_id else 'NULL'} WHERE id = {self.id}")
				connection.commit()

	def set_last_callback(self, callback) -> NoReturn:
		"""
		:param callback: buttons callback obj
		"""
		self.last_callback = datetime.fromtimestamp(callback.message.date).isoformat()
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"UPDATE users SET last_callback = '{self.last_callback}' WHERE id = {self.id}")
			connection.commit()

	def check_period(self):
		return True if self.subscription_plan['period'] and self.subscription_plan['period'] >= datetime.now().date() else False

	def sessions_left(self) -> Optional[list]:
		out = [i for i in self.subscription_plan['sessions_count'] if self.subscription_plan['sessions_count'][i] and self.subscription_plan['sessions_count'][i] > 0]
		if out:
			return out

	def notifications(self, set=False, updated_notifications=None):
		with database() as connection:
			with connection.cursor() as db:
				if not set:
					db.execute(f"SELECT * FROM bot_funcs WHERE users_id = {self.id}")
					notifications = db.fetchall()
					if notifications:
						return notifications[0]
				else:
					for i in updated_notifications:
						if i in ['reminded_today_session', 'reminded_before_session']:
							if updated_notifications[i]:
								db.execute(f"UPDATE bot_funcs set {i} = '{updated_notifications[i]}' WHERE users_id={self.id}")
							else:
								db.execute(f"UPDATE bot_funcs set {i} = NULL WHERE users_id={self.id}")
						else:
							db.execute(f"UPDATE bot_funcs set {i} = {updated_notifications[i]} WHERE users_id={self.id}")
					connection.commit()

	def records(self):
		reports = self.training_reports(objects=True)
		if reports:
			reports = [i for i in reports if i.credited and i.type == 'video']
			result = []
			if reports:
				for rep in reports:
					max_result = None
					lst = [i for i in reports if i.exercise.exercises_id == rep.exercise.exercises_id]
					if not rep.exercise.unit is None:
						if not rep.exercise.weight is None:
							max_result = max(lst, key=lambda x: (x.exercise.weight, x.exercise.repeats) if not x.exercise.repeats is None else x.exercise.weight)
					else:
						if not rep.exercise.repeats in [None, 0] and not rep.exercise.sets is None:
							max_result = max(lst, key=lambda x: x.exercise.repeats)
					if max_result:
						result.append(max_result)
				if result:
					return sorted(set([max([j for j in result if j.exercise.exercises_id == i.exercise.exercises_id], key=lambda x: (x.exercise.weight, x.exercise.repeats) if x.exercise.weight else x.exercise.repeats) for i in result]), key=lambda x: x.exercise.name)


	def training_self(self, objects:bool=False, individual:bool=False) -> Union[dict, list[TrainingSelfPlan]]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM training_self WHERE users_id = {self.id}")
				training_self_history = db.fetchall()
		if training_self_history:
			if not objects:
				return training_self_history
			else:
				if not individual:
					return sorted([TrainingSelfPlan(self, i['training_plans_id']) for i in training_self_history if i['training_type'] == 'self'], key=lambda x: (x.levels_id, x.rate, len(x.exercises)))
				else:
					return [TrainingSelfPlan(self, i['training_plans_id']) for i in training_self_history if i['training_type'] == 'individual']



	def forms(self) -> Optional[dict]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT questions, answers, answer_timestamp FROM users_forms WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id} ORDER BY answer_timestamp")
				forms = db.fetchall()
				if forms:
					return forms

	def training_reports(self, report_date:date=None, objects:bool=False, reports_type:str='all') -> Optional[list[dict], dict, list[TrainingReport]]:
		"""
		:param reports_type: all, individual, self
		"""
		with database() as connection:
			with connection.cursor() as db:
				if not report_date:
					if reports_type == 'all':
						db.execute(f"SELECT * FROM training_reports WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id} ORDER BY report_date")
					else:
						db.execute(f"SELECT * FROM training_reports AS t LEFT JOIN coachs_training_plans AS c "
								   f"ON t.training_plans_id = c.id WHERE c.session_type = '{reports_type}' AND t.coachs_id = {self.current_coach_id} AND t.users_id = {self.id} ORDER BY t.report_date")
					reports = db.fetchall()
					# report_checking = reports.copy()
					# for report in reports:
					# 	dt = report['report_date']
					# 	checking_dates_list = [i['report_date'] for i in reports]
					# 	if checking_dates_list.count(dt) > 1:
					# 		for incorrect_report in reports:
					# 			if incorrect_report['exercises_id'] != report['exercises_id']:
					# 				incorrect_report['report_date'] += timedelta(seconds=1)
					# if reports != report_checking:
					# 	for report in reports:
					# 		db.execute(f"UPDATE training_reports SET report_date = '{report['report_date'].isoformat()}' WHERE users_id = {self.id} AND "
					# 				   f"exercises_id = {report['exercises_id']} AND training_plans_id = {report['training_plans_id']}")
					# 	connection.commit()
					if reports:
						if not objects:
							return reports
						else:
							return [TrainingReport(self, i['report_date']) for i in reports]
				else:
					db.execute(f"SELECT * FROM training_reports WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id} AND report_date = '{report_date.isoformat()}'")
					report = db.fetchall()
					return report[0] if report and any(report) else None

	def new_training_report(self, training_plan:TrainingSelfPlan, report_type:str, report:str, report_date:datetime=datetime.today(), exercise:Optional[Exercise]=None) -> int:
		"""
		:param report_date: using another reports dates for avoid crossing
		:param report_type: video/text
		:param exercise: needed if report_type is video
		"""
		if self.current_coach_id:
			with database() as connection:
				with connection.cursor() as db:
					if report_type == 'video':
						db.execute(f"INSERT INTO training_reports (coachs_id, users_id, report_date, content, training_plans_id, exercises_id, report_type) VALUES "
								   f"({self.current_coach_id}, {self.id}, '{report_date.isoformat()}', '{report}', {training_plan.id}, {exercise.coachs_exercises_id}, "
								   f"'{report_type}')")
						connection.commit()
						return exercise.coachs_exercises_id
					elif report_type == 'text':
						db.execute(f"INSERT INTO training_reports (coachs_id, users_id, report_date, content, training_plans_id, report_type) VALUES "
							f"({self.current_coach_id}, {self.id}, '{datetime.today().isoformat()}', '{report}', {training_plan.id}, "
							f"'{report_type}')")
						connection.commit()

	def payments(self) -> Optional[list]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT tariff_id, payment_amount, payment_date FROM payments WHERE coachs_id = {self.current_coach_id} AND users_id = {self.id}")
				payments = db.fetchall()
				if payments:
					return payments

class Tariff:
	def __init__(self, tariff_id=None, user=None):
		if tariff_id or user:
			with database() as connection:
				with connection.cursor() as db:
					if tariff_id:
						db.execute(f"SELECT * FROM coachs_tariffs WHERE id = {tariff_id}")
						tariff = db.fetchall()
					elif user:
						db.execute(f"SELECT * FROM coachs_tariffs WHERE id = {user.subscription_plan['tariff_id']}")
						tariff = db.fetchall()
			if tariff and any(tariff):
				tariff = tariff[0]
				self.id: int = int(tariff_id)
				self.name = tariff['name']
				self.description = tariff['description']
				self.period = tariff['period']
				self.cost = tariff['cost']
				self.users_permissions = loads(tariff['users_permissions'])
				self.sessions = loads(tariff['sessions'])
				self.canceling_amount = tariff['canceling_amount']
				self.coachs_id = tariff['coachs_id']

		else:
			self.id = None
			self.name = None
			self.description = None
			self.period = None
			self.cost = None
			self.users_permissions = None
			self.sessions = None
			self.canceling_amount = None
			self.coachs_id = None

	def set(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_tariffs WHERE id = {self.id}")
				tariff = db.fetchall()[0]
				data = {i: j for i, j in self.__dict__.items() if not i in ['id', 'coachs_id']}
				for i in data:
					if data[i] != tariff[i]:
						if type(data[i]) == dict:
							data[i] = dumps(data[i], ensure_ascii=False)
						if i in ['period', 'cost', 'canceling_amount']:
							db.execute("UPDATE coachs_tariffs SET " + i + ' = ' + str(data[i]) + f' WHERE id = {self.id}')
						else:
							db.execute("UPDATE coachs_tariffs SET " + i + " = '" + str(data[i]) + f"' WHERE id = {self.id}")
				connection.commit()


	def find_users(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT users.chat_id FROM subscription_plan JOIN users ON subscription_plan.users_id = users.id WHERE subscription_plan.tariff_id = {self.id}")
				users_lst = db.fetchall()
				if users_lst:
					users_lst = [User(i) for i in [j['chat_id'] for j in users_lst]]
					return users_lst

	def schedule(self):
		coach = Coach(coach_id=self.coachs_id)
		schedule = coach.extra()['working_schedule']
		sessions = [i for i in self.sessions if self.sessions[i] and self.sessions[i] > 0]
		dct = {}
		for day in schedule:
			for hour in schedule[day]:
				available_hour = list(hour.keys())[0]
				training_type = list(hour.values())[0]
				if training_type in sessions:
					if not day in dct:
						dct[day] = [{available_hour: training_type}]
					else:
						dct[day].append({available_hour: training_type})
		return dct


	def delete(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"DELETE FROM coachs_tariffs WHERE id = {self.id}")
				connection.commit()