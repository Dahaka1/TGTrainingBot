from __future__ import annotations

from store import *
from datetime import date
from classes.general import *
from typing import NoReturn


class ScheduleDay:
	def __init__(self, coach: Coach, curdate: date):
		self.coach = coach
		self.coach_id: int = coach.id
		self.date: date = curdate
		self.schedule: list = []
		day_hours = [list(i.keys())[0].split(':')[0] for i in coach.extra()['working_schedule'][str(curdate.isoweekday())]] if coach.extra()['working_schedule'][str(curdate.isoweekday())] else None
		if day_hours:
			with database() as connection:
				with connection.cursor() as db:
					day_hours = ', '.join(["'" + i + ':00:00' + "'" for i in day_hours])
					db.execute(f"SELECT * FROM schedules WHERE coachs_id = {coach.id} AND date = '{curdate.isoformat()}' AND time IN ({day_hours})")
					signup = db.fetchall()
					if signup:
						self.schedule = sorted(signup, key=lambda x: x['time'])

	def get_schedule(self):
		if self.schedule:
			return [ScheduleHour(self, i) for i in [j['time'].seconds/3600 for j in self.schedule]]

	def isoformat(self):
		return self.date.isoformat()

	def free_hours(self, user: User) -> list[ScheduleHour]:
		limits = {
			'personal': 1,
			'split': 3,
			'group': 100,
			'personal_online': 1,
			'free': 1
		}
		if user.sessions_left():
			working_schedule = [int(list(i.keys())[0].split(':')[0]) for i in self.coach.extra()['working_schedule'][str(self.date.isoweekday())]]
			free_hours = [ScheduleHour(self, hour) for hour in working_schedule]
			if free_hours:
				if user.subscription_plan['tariff_id']:
					return [i for i in filter(lambda hour: hour.session_type in user.sessions_left() and len(hour.clients) < limits[hour.session_type] and hour.date <= user.subscription_plan['period'], free_hours) if i]
				else:
					return [i for i in filter(lambda hour: hour.session_type in user.sessions_left() and len(hour.clients) < limits[hour.session_type], free_hours) if i]

	def sessions_types(self, user: User, all_types:bool=False) -> set[str]:
		if all_types is False:
			free_hours = self.free_hours(user)
			return set([i.session_type for i in free_hours])
		else:
			working_schedule = [next(iter(i.values())) for i in self.coach.extra()['working_schedule'][str(self.date.isoweekday())]]
			return set(working_schedule)

	def user_signed_up_hours(self, user: User):
		return [h for h in self.get_schedule() if h.user_signed_up_check(user)]


class ScheduleHour(ScheduleDay):
	def __init__(self, day: ScheduleDay, hour: int):
		super().__init__(day.coach, day.date)
		self.time: int = int(hour)
		self.clients: list = [{'user': User(user_id=i['users_id']), 'comment': i['details']} for i in self.schedule if i['time'].seconds/3600 == self.time] if self.schedule else []
		hours = filter(lambda h: self.time in [int(i.split(':')[0]) for i in h.keys()], self.coach.extra()['working_schedule'][str(self.date.isoweekday())])
		self.session_type: str = list(list(hours)[0].values())[0]

	def set(self, user: User) -> NoReturn:
		with database() as connection:
			with connection.cursor() as db:
				self.date = self.date.isoformat()
				db.execute(f"INSERT INTO schedules (coachs_id, users_id, date, time, session_type) VALUES ({self.coach_id}, {user.id}, '{self.date}', "
						   f"'{self.time}:00:00', '{self.session_type}')")
				connection.commit()
		user.subscription_plan['sessions_count'][self.session_type] -= 1
		user.set_user(subscription_plan=True)


	def send_details(self, user: User, text: str) -> NoReturn:
		with database() as connection:
			with connection.cursor() as db:
				self.date = self.date.isoformat()
				db.execute(f"UPDATE schedules SET details = '{text}' WHERE coachs_id = {self.coach_id} AND users_id = {user.id} AND date = '{self.date}' AND time = '{self.time}:00:00'")
				connection.commit()

	def user_signed_up_check(self, user: User) -> bool:
		return user.id in [i['user'].id for i in self.clients]


	def cancel(self, user: User, canceling_type:str) -> NoReturn:
		"""
		:param canceling_type: coach, user
		"""
		with database() as connection:
			with connection.cursor() as db:
				db.execute(f"DELETE FROM schedules WHERE coachs_id = {user.current_coach_id} AND users_id = {user.id} AND "
						   f"date = '{self.date.isoformat()}' AND time = '{self.time}:00:00'")
			connection.commit()
		if canceling_type == 'user':
			counter, period = user.subscription_plan['canceled_sessions'], user.subscription_plan['period'].isoformat()
			if period in counter:
				counter[period] += 1
			else:
				counter[period] = 1
		training_type = self.session_type
		user.subscription_plan['sessions_count'][training_type] += 1
		user.set_user(subscription_plan=True)