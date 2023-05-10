from telebot.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

def keyboard(user):
	menu = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
	button_1 = KeyboardButton(text='🗓 Запись')
	button_2 = KeyboardButton(text='💸 Оплата')
	button_3 = KeyboardButton(text='🏃 Мои тренировки')
	button_4 = KeyboardButton(text='🥇 Результаты')
	button_5 = KeyboardButton(text='❔ Помощь')
	if user.current_coach_id:
		menu.add(button_1, button_2, button_3, button_4, button_5)
	else:
		menu.add(button_3, button_5)
	return menu


# кнопки меню для раздела "Мои тренировки" в меню клиентов
def my_training_menu(user):
	menu = InlineKeyboardMarkup(row_width=1)
	buttons_with_coach = [
		InlineKeyboardButton(text='🏋️ Индивидуальные занятия', callback_data='individual_trainings'),
		InlineKeyboardButton(text='😎 Самостоятельные занятия', callback_data='self_trainings'),
		InlineKeyboardButton(text='☝️ Текущие задачи', callback_data='my_tasks'),
		InlineKeyboardButton(text='🍔 Моя диета', callback_data='my_diet'),
		InlineKeyboardButton(text='❗️ Настройки бота', callback_data='set_my_bot'),
		InlineKeyboardButton(text='👤 Мой тренер', callback_data='my_coach')
	]
	buttons_without_coach = [
		InlineKeyboardButton(text='🏋️‍♀️ Бесплатный курс тренировок', callback_data='free_trainings'),
		InlineKeyboardButton(text='🍔 Бесплатная диета', callback_data='my_diet'),
		InlineKeyboardButton(text='👤 Выбрать тренера', callback_data='choose_coach')
	]
	if user.current_coach_id:
		if user.tariff() and user.check_period():
			# если есть тренер и купленный тариф (тариф определяет уровень доступа)
			if user.permissions:
				buttons = [*filter(lambda button: button.callback_data in user.permissions, buttons_with_coach), buttons_with_coach[2], *buttons_with_coach[-2:]]
				if any([i in user.permissions for i in ['individual_trainings', 'self_trainings']]) and user.records():
					buttons.insert(-3, InlineKeyboardButton(text='📍 Мои рекорды',
														  callback_data=f'client_trainings_records {user.id}'))
				return menu.add(*buttons)
			else:
				return menu.add(buttons_without_coach[-1])
		else:
			return menu.add(buttons_with_coach[-1])
	else:
		return menu.add(*buttons_without_coach)

def admin_keyboard():
	admin_menu = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
	button_1 = KeyboardButton(text='📃 Общее')
	button_2 = KeyboardButton(text='👨‍🦲 Клиенты')
	button_3 = KeyboardButton(text='🥇 Результаты')
	admin_menu.add(button_1, button_2, button_3)
	return admin_menu