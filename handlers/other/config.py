from typing import Any

statuses = [
		'individual_training',
		'sending_individual_plan',
		'self_training',
		'sending_self_training_video_report',
		'indebted_coach'
	]

def forbidden_status(user: Any) -> bool:
	"""
	Проверяет статус юзера на статусы, при которых нельзя использовать меню, команду /start ...
	:param: user: classes.general.User/Coach
	"""

	status = user.status
	for item in statuses:
		if status.startswith(item):
			return True

	return False