from __future__ import annotations

from store import *
from classes.general import *
from json import loads, dumps
from datetime import datetime
from typing import Optional, NoReturn
from telebot.types import InlineKeyboardButton

class Exercise:
	def __init__(self, exercise_id:[int,str], coach=True):
		with database() as connection:
			with connection.cursor() as db:
				if coach:
					db.execute(f"SELECT e.exercise_id, c.coachs_id, c.exercise_terms, c.exercise_weight, c.exercise_sets, c.exercise_repeats, c.exercise_info_video,"
							   f"c.exercise_info_image, c.exercise_info_audio, e.exercises_category_id, e.exercise_name,"
							   f"e.exercise_inventory_id, e.exercise_muscles_group, e.exercise_difficulty, e.exercise_type,"
							   f"e.exercise_unit, e.exercise_video_tutorial FROM exercises AS e LEFT JOIN coachs_exercises AS c ON "
							   f"e.exercise_id = c.exercises_id WHERE c.id = {exercise_id}")
					dct = db.fetchall()
					if dct and any(dct):
						dct = dct[0]
						self.exercises_id = dct['exercise_id']
						self.coachs_exercises_id = exercise_id
						self.name = dct['exercise_name']
						self.coach_id = dct['coachs_id']
						self.muscles_group = dct['exercise_muscles_group']
						self.difficulty = dct['exercise_difficulty']
						self.type = dct['exercise_type']
						self.unit = dct['exercise_unit'] if dct['exercise_unit'] else None
						self.video_tutorial = dct['exercise_video_tutorial'] if dct['exercise_video_tutorial'] else None
						self.terms = dct['exercise_terms'] if dct['exercise_terms'] else None
						self.weight = dct['exercise_weight'] if dct['exercise_weight'] else None
						self.sets = dct['exercise_sets'] if dct['exercise_sets'] else None
						self.repeats = dct['exercise_repeats']
						self.video = dct['exercise_info_video'] if dct['exercise_info_video'] else None
						self.image = dct['exercise_info_image'] if dct['exercise_info_image'] else None
						self.audio = dct['exercise_info_audio'] if dct['exercise_info_audio'] else None
				else:
					db.execute(f"SELECT e.exercises_category_id, e.exercise_name, e.exercise_muscles_group,"
							   f"e.exercise_difficulty, e.exercise_type, e.exercise_unit, e.exercise_video_tutorial,"
							   f"i.name, i.description, i.photo, i.video, i.location FROM exercises AS e LEFT JOIN inventory AS i ON e.exercise_inventory_id = "
							   f"i.id WHERE e.exercise_id = {exercise_id}")
					dct = db.fetchall()
					if dct:
						dct = dct[0]
						self.exercises_id: int = exercise_id
						self.name: str = dct['exercise_name']
						db.execute(f"SELECT category_name FROM exercises_categories WHERE id = {dct['exercises_category_id']}")
						self.category_id: int = dct['exercises_category_id']
						self.category: str = db.fetchall()[0]['category_name']
						self.difficulty: int = dct['exercise_difficulty']
						self.type: str = dct['exercise_type']
						self.unit: [str, None] = dct['exercise_unit'] if dct['exercise_unit'] else None
						self.video_tutorial: [str, None] = dct['exercise_video_tutorial'] if dct['exercise_video_tutorial'] else None
						self.muscles_group: str = dct['exercise_muscles_group']
						self.inventory_name: str = dct['name']
						self.inventory_description: [str, None] = dct['description'] if dct['description'] else None
						self.inventory_photo: [str, None] = dct['photo'] if dct['photo'] else None
						self.inventory_video: [str, None] = dct['video'] if dct['video'] else None
						self.inventory_location: str = dct['location']


	def description(self):
		if self.coach_id:
			d =  {'kg': 'кг',
					  'minutes': 'мин',
					  'hours': 'ч',
					  'cantimeters': 'см',
					  'meters': 'м'}
			raw = Exercise(self.exercises_id, coach=False)
			if self.unit == 'kg':
				physical_desc = f'*Отягощение*: _{str(int(self.weight) if str(self.weight).endswith(".0") else float(self.weight)) + f" ({d[self.unit]})" if self.weight else ("отсутствует" if self.unit is None else "на усмотрение")}_\n' \
				   f'*Подходов*: _{self.sets if self.sets else "на усмотрение"}_\n' \
				   f'*Повторений*: _{self.repeats if not self.repeats in ["None", None, 0, "0"] else "максимум"}_\n'
			elif self.unit is None:
				physical_desc =  f'*Подходов*: _{self.sets if self.sets else "на усмотрение"}_\n' \
				   f'*Повторений*: _{self.repeats if not self.repeats in ["None", None, 0, "0"] else "максимум"}_'
			elif self.unit == 'meters':
				physical_desc = f'*Интервалов* (подходов): _{self.sets if self.sets else "на усмотрение"}_\n' \
								f'*Объем нагрузки*: _{str(self.repeats) + " (метры)" if not self.repeats in ["None", None, 0, "0"] else "максимум"}_'

			text = f'*Название упражнения*: _{self.name}_\n' \
				   f'*Инвентарь*: _{raw.inventory_name if raw.inventory_name else "не требуется"}_\n' +\
					physical_desc +\
				   f'\n*Доп. условия*: _{self.terms if self.terms else "отсутствуют"}_'
			return text

	@staticmethod
	def get_self_by_name(name:str) -> Optional[Exercise]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM exercises WHERE exercise_name = '{name}'")
				ex = db.fetchone()
				if ex:
					return Exercise(ex['exercise_id'], coach=False)


	def set(self):
		with database() as connection:
			with connection.cursor() as db:
				if self.sets:
					db.execute(f"UPDATE coachs_exercises SET exercise_sets = {self.sets} WHERE id = {self.coachs_exercises_id}")
				if self.weight:
					db.execute(f"UPDATE coachs_exercises SET exercise_weight = {float(self.weight)} WHERE id = {self.coachs_exercises_id}")
				if self.terms:
					db.execute(f"UPDATE coachs_exercises SET exercise_terms = '{self.terms}' WHERE id = {self.coachs_exercises_id}")
				if self.video:
					db.execute(f"UPDATE coachs_exercises SET exercise_info_video = '{self.video}' WHERE id = {self.coachs_exercises_id}")
				if self.audio:
					db.execute(f"UPDATE coachs_exercises SET exercise_info_audio = '{self.audio} 'WHERE id = {self.coachs_exercises_id}")
				if self.image:
					db.execute(f"UPDATE coachs_exercises SET exercise_info_image = '{self.image}' WHERE id = {self.coachs_exercises_id}")
				connection.commit()

	@staticmethod
	def new_coach_exercise(coach, exercise, repeats, sets=None, weight=None, terms=None, video=None, audio=None, image=None):
		if repeats is None:
			repeats = "'NULL'"
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"INSERT INTO coachs_exercises (coachs_id, exercises_id, exercise_repeats) VALUES "
						   f"({coach.id}, {exercise.exercises_id}, {repeats})")
				connection.commit()
				db.execute(f"SELECT id FROM coachs_exercises WHERE coachs_id={coach.id} AND exercises_id={exercise.exercises_id} ORDER BY id DESC LIMIT 1")
				current_ex = Exercise(db.fetchall()[0]['id'])
				if sets:
					current_ex.sets = sets
				if weight:
					current_ex.weight = float(weight)
				if terms:
					current_ex.terms = terms
				if video:
					current_ex.video = video
				if audio:
					current_ex.audio = audio
				if image:
					current_ex.image = image

				current_ex.set()

				return current_ex.coachs_exercises_id

	def leaderboard(self) -> [list, None]:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM leaderboards WHERE coachs_id = {self.coach_id}")
				leaderboard = db.fetchall()
		if leaderboard:
			try:
				return next(filter(lambda item: item['exercises_id'] == self.coachs_exercises_id, leaderboard))
			except StopIteration:
				pass


class TrainingPlan:
	def __init__(self, plan_id:[str,int]=None, coach:Coach=None):
		if not plan_id:
			self.id = None
			self.coachs_id = coach.id if coach else None
			self.levels_id = None
			self.exercises = None
			self.duration = None
			self.video = None
			self.image = None
			self.audio = None
			self.rate = None
			self.type = None
			self.terms = None
			self.users_id = None

		else:
			self.id:int = int(plan_id)
			with database() as connection:
				with connection.cursor() as db:
					db.execute(f"SELECT * FROM coachs_training_plans WHERE id = {plan_id}")
					current_plan = db.fetchall()
			if current_plan:
				current_plan = current_plan[0]
				self.coachs_id = current_plan['coachs_id']
				self.levels_id = current_plan['coachs_levels_id'] if current_plan['coachs_levels_id'] else None
				self.exercises = loads(current_plan['session_exercises'])
				self.duration = current_plan['session_duration']
				self.video = current_plan['informational_video'] if current_plan['informational_video'] else None
				self.image = current_plan['informational_image'] if current_plan['informational_image'] else None
				self.audio = current_plan['informational_audio'] if current_plan['informational_audio'] else None
				self.rate = current_plan['session_rate']
				self.type = current_plan['session_type']
				self.terms = current_plan['session_terms'] if current_plan['session_terms'] else None
				self.users_id = current_plan['users_id'] if current_plan['users_id'] else None


	def media(self, callback_data: str) -> Optional[list[InlineKeyboardButton]]:
		out = []
		if self.video:
			out.append(InlineKeyboardButton(text='Видео', callback_data=callback_data + ' video'))
		if self.audio:
			out.append(InlineKeyboardButton(text='Аудио', callback_data=callback_data + ' audio'))
		if self.image:
			out.append(InlineKeyboardButton(text='Изображение', callback_data=callback_data + ' image'))
		if out:
			return out

	def new_training_self(self, user:User, code_word:Optional[str]=None) -> TrainingPlan:
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM training_self WHERE users_id = {user.id} AND "
						   f"training_plans_id = {self.id}")
				checking = db.fetchall()
				if not checking or not any(checking):
					if code_word:
						db.execute(f"INSERT INTO training_self (users_id, coachs_levels_id, training_plans_id, "
								   f"plan_received_at, training_type, training_plan_is_done, code_word) "
								   f"VALUES ({user.id}, {self.levels_id}, {self.id}, '{datetime.today().isoformat()}', "
								   f"'self', false, '{code_word}')")
					else:
						db.execute(f"INSERT INTO training_self (users_id, training_plans_id, "
								   f"plan_received_at, training_type, training_plan_is_done) "
								   f"VALUES ({user.id}, {self.id}, '{datetime.today().isoformat()}', "
								   f"'individual', false)")
				else:
					db.execute(f"UPDATE training_self SET plan_received_at='{datetime.today().isoformat()}', training_type='self', "
							   f"training_plan_is_done=false, code_word='{code_word}' WHERE users_id = {user.id} AND "
							   f"coachs_levels_id = {user.training_levels_id} AND training_plans_id = {self.id}")
				connection.commit()
				return self


	def new(self) -> int:
		if self.exercises and self.duration and self.rate and self.type:
			with database() as connection:
				with connection.cursor() as db:
					db.execute(f"INSERT INTO coachs_training_plans (coachs_id, session_exercises, session_duration, session_type, "
							   f"session_rate) VALUES ({self.coachs_id}, '{dumps(self.exercises)}', {self.duration}, '{self.type}', {self.rate})")
					connection.commit()

					db.execute(f"SELECT id FROM coachs_training_plans WHERE coachs_id = {self.coachs_id} ORDER BY id DESC LIMIT 1")
					current_plan_id = db.fetchall()[0]['id']
					if self.levels_id:
						db.execute(f"UPDATE coachs_training_plans SET coachs_levels_id = {self.levels_id} WHERE id = {current_plan_id}")
					if self.video:
						db.execute(f"UPDATE coachs_training_plans SET informational_video = '{self.video}' WHERE id = {current_plan_id}")
					if self.image:
						db.execute(f"UPDATE coachs_training_plans SET informational_image = '{self.image}' WHERE id = {current_plan_id}")
					if self.audio:
						db.execute(f"UPDATE coachs_training_plans SET informational_audio = '{self.audio}' WHERE id = {current_plan_id}")
					if self.terms:
						db.execute(f"UPDATE coachs_training_plans SET session_terms = '{self.terms}' WHERE id = {current_plan_id}")
					if self.users_id:
						db.execute(f"UPDATE coachs_training_plans SET users_id = {self.users_id} WHERE id = {current_plan_id}")
					connection.commit()
					return current_plan_id


class TrainingSelfPlan(TrainingPlan):
	def __init__(self, user:User, plan_id:[str, int]):
		super().__init__(plan_id)
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT t.training_started_at, t.plan_received_at, t.training_plan_is_done, r.report_date"
						   f" FROM training_self AS t LEFT JOIN training_reports AS r ON t.training_plans_id = "
						   f"r.training_plans_id WHERE t.users_id = {user.id} AND t.training_plans_id = {self.id} ORDER BY t.training_started_at DESC")
				plan = db.fetchall()
				if plan:
					self.training_started_at = plan[0]['training_started_at']
					self.plan_received_at = plan[0]['plan_received_at']
					self.training_plan_is_done = plan[0]['training_plan_is_done']
					self.reports_datetime = [i['report_date'] for i in plan]
					self.user = user

	def start(self, user: User):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"UPDATE training_self SET training_started_at = '{datetime.now().isoformat()}' WHERE users_id = {user.id} AND training_plans_id = {self.id}")
			connection.commit()

	def reports(self):
		return [TrainingReport(self.user, i) for i in self.reports_datetime]

	def description(self):
		text = f'Тренировочный план:\n_- сложность: {self.rate} из 10\n' \
			   f'- тип тренировки: {d_training_types[self.type]}\n' \
			   f'- максимальная длительность: {d_dur[self.duration]}\n' \
			   f'- упражнений: {len(self.exercises)}\n' \
			   f'- получен/выполнен: {self.plan_received_at.date()} / {self.training_started_at.date()}_'
		return text


class TrainingReport:
	def __init__(self, user: User, report_date: datetime):
		reports = user.training_reports()
		if reports:
			try:
				report = next(filter(lambda rep: rep['report_date'] == report_date, reports))
			except StopIteration:
				pass
			else:
				self.user_id = report['users_id']
				self.coach_id = report['coachs_id']
				self.training_plan = TrainingSelfPlan(user, report['training_plans_id'])
				self.datetime = report['report_date']
				self.type = report['report_type']
				self.exercise = Exercise(report['exercises_id']) if report['exercises_id'] else None
				self.content = report['content']
				self.checked = bool(report['checked'])
				self.credited = bool(report['credited'])
				self.coach_comment = report['coach_comment']

	def description(self):
		d_dur = {10: '10 мин', 20: "20 мин", 30: "30 мин", 40: "40 мин", 50: "50 мин", 60: "1 ч", 90: "1.5 ч", 120: "2 ч",
			 180: "3 ч"}
		d_type = {'video': 'видео', "text": 'текстовый'}
		d_training_types = {'self': "самостоятельная", "individual": 'индивидуальная'}
		units = {'kg': "кг"}
		bools  = {True: "да", False: "нет"}
		text = f'📍 *Отчет от {self.datetime.isoformat().replace("T", ", ")[:-3]}*\n' +\
			   f'Тренировочный план:\n_- сложность: {self.training_plan.rate} из 10\n' +\
			   f'- тип тренировки: {d_training_types[self.training_plan.type]}\n' +\
			   f'- максимальная длительность: {d_dur[self.training_plan.duration]}\n'+ \
			   f'- упражнений: {len(self.training_plan.exercises)}_\n' +\
			   f'Тип: {d_type[self.type]}\n' +\
			  (f'Упражнение:\n_- название: {self.exercise.name}\n' +\
			   f'- отягощение: {(str(int(self.exercise.weight)) if str(self.exercise.weight).endswith(".0") else str(self.exercise.weight)) + (f" {units[self.exercise.unit]}" if self.exercise.unit else "") if self.exercise.weight else ("нет" if not self.exercise.unit else "на усмотрение")}\n' +\
			   f'- повторений: {self.exercise.repeats if self.exercise.sets else "на усмотрение"}\n' if self.type == 'video' else f'Отчет:\n- содержание: "_{self.content}_"') +\
			   (f'- проверено/зачтено: {bools[self.checked]}/{bools[self.credited]}_.' if self.type == 'video' else f'\n- проверено: _{bools[self.checked]}_') +\
			(f'\nКомментарий тренера:\n- _{self.coach_comment}_' if self.coach_comment else '')
		return text

	def record_description(self):
		units = {'kg': "кг"}
		text = f'Упражнение:\n_- название: {self.exercise.name}\n' \
			   f'- отягощение: {(str(int(self.exercise.weight)) if str(self.exercise.weight).endswith(".0") else str(self.exercise.weight)) + (f" {units[self.exercise.unit]}" if self.exercise.unit else "") if self.exercise.weight else ("нет" if not self.exercise.unit else "на усмотрение")}\n' \
			   f'- повторений: {self.exercise.repeats if self.exercise.sets else "на усмотрение"}_'
		return text

	def update(self, result:Optional[bool]=None) -> NoReturn:
		"""
		:param result: needed if report type is video, not text
		"""
		if result is True:
			if self.type == 'video':
				self.credited = True
		self.checked = True
		self.set()

	def set(self) -> NoReturn:
		with database() as connection:
			with connection.cursor() as db:
				comment = "'" + self.coach_comment + "'" if not self.coach_comment is None else "NULL"
				if not self.exercise is None:
					db.execute(f"UPDATE training_reports SET checked = {self.checked}, credited = {self.credited}, coach_comment = {comment} WHERE users_id = {self.user_id} AND "
							   f"report_date = '{self.datetime.isoformat()}' AND report_type = '{self.type}' AND exercises_id = {self.exercise.coachs_exercises_id}")
				else:
					db.execute(
						f"UPDATE training_reports SET checked = {self.checked}, coach_comment = {comment} WHERE users_id = {self.user_id} AND "
						f"report_date = '{self.datetime.isoformat()}' AND report_type = '{self.type}'")
				if self.credited:
					db.execute(f"UPDATE training_self SET training_plan_is_done = true WHERE training_plans_id = {self.training_plan.id} AND users_id = {self.user_id}")
			connection.commit()


class Level:
	def __init__(self, level_id=None, user: User=None):
		self.id = None
		self.coach_id = None
		self.name = None
		self.description = None
		self.sessions_amount = None
		self.user_training_self = None
		with database() as connection:
			with connection.cursor() as db:
				if level_id or user and user.training_levels_id:
					if level_id:
						db.execute(f"SELECT * FROM coachs_levels WHERE id = {level_id}")
					elif user and user.training_levels_id:
						db.execute(f"SELECT * FROM coachs_levels WHERE id = {user.training_levels_id}")
					level = db.fetchall()
					if level:
						level = level[0]
						self.id = level['id']
						self.coach_id = level['coachs_id']
						self.name = level['level_name']
						self.description = level['level_description']
						self.sessions_amount = level['level_sessions_amount']
						self.user_training_self = None
						if user:
							db.execute(f"SELECT training_plans_id, training_started_at, plan_received_at, training_plan_is_done FROM training_self WHERE coachs_levels_id = {self.id} AND users_id = {user.id} AND training_type = 'self' ORDER BY training_started_at")
							training_self = db.fetchall()
							if training_self:
								self.user_training_self = [{'training_plans_id': i["training_plans_id"],
															'training_started_at': i["training_started_at"],
															'plan_received_at': i["plan_received_at"],
															'training_plan_is_done': i['training_plan_is_done']} for i in training_self]


	def training_plans(self):
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"SELECT * FROM coachs_training_plans WHERE coachs_id = {self.coach_id} AND coachs_levels_id = {self.id}")
				plans = db.fetchall()
				if plans:
					return sorted(plans, key=lambda x: (x['session_rate'], len(loads(x['session_exercises']))))


