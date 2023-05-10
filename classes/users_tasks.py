from datetime import timedelta
from random import randrange, randint
from typing import Optional, Union, Any
from classes.training import *

tasks_types = {
	1:
		{
			'type': 'Индивидуальные тренировки',  # user
			'period': timedelta(days=10)
		},
	2:
		{
			'type': 'Индивидуальные планы',  # coach
			'period': timedelta(days=3)
		},
	3:
		{
			'type': 'Рабочее расписание',  # coach
			'period': timedelta(days=3)
		},
	4:
		{
			'type': 'Самостоятельные тренировки',  # coach
			'period': timedelta(days=3)
		},
	5:
		{
			'type': 'Подтверждение транзакции',  # coach
			'period': timedelta(days=1)
		}
}


class Task:
	def __init__(self, type_num: int):
		params = tasks_types[int(type_num)]
		self.type_number: int = int(type_num)
		self.type: str = params['type']
		self.date: Optional[datetime] = None
		self.period: timedelta = params['period']
		self.description: Optional[str] = None
		self.additional_info: Optional[str, int, dict] = None

	def new(self, user: Any, text: str, additional_info: Union[tuple, list, str, int, None] = None) -> NoReturn:
		"""
		Создание новой задачи для клиента
		"""
		self.description = text
		self.additional_info = additional_info
		if user.current_coach_id and user.check_period():
			tasks = user.tasks or []
			if not self.date:
				self.date = datetime.today()
			if any(filter(lambda x: x.type_number == self.type_number and x.date == self.date, tasks)):
				self.date += timedelta(seconds=1)
			tasks.append(self)
			user.tasks = tasks
			user.set_user()
		else:
			raise AttributeError("Creating tasks is not available for users haven't current coach.")

	def new_coach_task(self, coach: Any, text: str,
					   additional_info: Union[tuple, list, str, int, None] = None) -> NoReturn:
		"""
		Создание новой задачи для тренера.
		Сделал эту функцию отдельно для тренера, ибо импортировать из пакета classes классы User/Coach не получается
		"""
		self.description = text
		self.additional_info = additional_info
		if coach.period_check()[1]:
			tasks = coach.tasks or []
			if not self.date:
				self.date = datetime.today()
			tasks.append(self)
			coach.tasks = tasks
			coach.set_tasks()

	def delete(self, user: Any) -> NoReturn:
		"""
		Удаление/снятие задачи
		"""
		user.tasks.remove(self)
		try:
			user.set_user()
		except:
			user.set_tasks()

	def check_period(self) -> bool:
		return True if self.date and self.date + self.period > datetime.now() else False

	def end_date(self) -> str:
		if self.date:
			return datetime.strftime(self.date + self.period, '%d.%m.%Y, %H:%M')

	def start_date(self) -> str:
		if self.date:
			return datetime.strftime(self.date, '%d.%m.%Y, %H:%M')


def individual_training_plan(user: Any, training_plans: list[Any]) -> NoReturn:
	"""
	Создание задачи для клиента при получении им индивидуального тренировочного плана
	для последующего отчета по тренировке
	"""
	for plan in training_plans:
		if not any(plan.exercises.values()):
			amount = randint(1, 2)
			for i in range(amount):
				plan.exercises[list(plan.exercises)[randrange(len(plan.exercises))]] = True
		report_exs = ', '.join([i.name + (
			f' ({i.sets}/{i.repeats if i.repeats else "максимум"})' if i.sets else f' ({"x " + str(i.repeats) if i.repeats else "/максимум повторений"})')
								for i in map(lambda ex: Exercise(ex),
											 filter(lambda ex: plan.exercises[ex] is True, plan.exercises))])
		text = f'Отчитаться по выполнению индивидуального тренировочного плана (_{len(plan.exercises)}_ упражнений, сложность тренировки: _{plan.rate} из 10_).\n' \
			   f'*Упражнение(-я) для отчета*: _{report_exs}_.'
		task = Task(1)
		task.new(user, text, (plan.id, list(filter(lambda ex: plan.exercises[ex] is True, plan.exercises))))


def individual_training_plan_coach(coach: Any, user: Any, task_type: str = None) -> NoReturn:
	"""
	Задача для тренера по отправке индивидуального плана тренировок
	"""
	if task_type:
		if task_type == 'send_plan':
			text = f'Отправить индивидуальное задание для клиента {user.fullname}!'
		elif task_type == 'check_report':
			text = f'Просмотреть и оценить видео-отчеты по индивидуальным тренировкам от клиента {user.fullname}!'
		task = Task(2)
		task.new_coach_task(coach, text, (task_type, user.id))
	else:
		raise ValueError("Argument 'task_type' must be string, not NoneType")


def working_schedule_coach(coach: Any, user: Any, current_types: list = None):
	"""
	Задача для тренера по добавлению больше часов для нужных клиенту типов тренировок в расписание
	"""
	training_types = {'personal': 'персонально', 'split': 'сплит', 'group': 'группа',
					  'personal_online': 'персонально онлайн', 'free': 'бесплатно (пробно)'}
	if not current_types:
		tr_types = '_' + ', '.join([training_types[i] for i in user.sessions_left()]) + '_'
	else:
		tr_types = '_' + ', '.join([training_types[i] for i in current_types]) + '_'
	text = 'Добавить в расписание больше часов для типов тренировок: ' + tr_types
	task = Task(3)
	task.new_coach_task(coach, text, user.sessions_left() if not current_types else current_types)


def training_self_coach(coach: Any, arg: Optional[Any] = None, task_type: str = None):
	if task_type:
		add_info = None
		if task_type == 'create_levels':
			text = 'Создать тренировочные уровни!'  # протестить
		elif task_type == 'create_training_plans':
			if isinstance(arg, Level):
				text = f'Создать новые тренировочные планы для уровня тренировок "{arg.name}".'
				add_info = arg.name
	else:
		raise ValueError("Argument 'task_type' must be string, not NoneType")
	task = Task(4)
	task.new_coach_task(coach, text, (task_type, add_info))


def freelancer_sending_receipt(coach: Any, user: Any, tariff: Any) -> NoReturn:
	"""
	:param coach: coach obj
	:param user: user obj
	:param tariff: tariff for finding tariff name and payment amount
	"""
	text = f'Отправить чек об оплате тарифа "{tariff.name}" клиенту {user.fullname}.\n' \
		   f'Сумма: {tariff.cost} рублей.'
	task = Task(5)
	task.new_coach_task(coach, text, (user.id, tariff.id, tariff.cost))
