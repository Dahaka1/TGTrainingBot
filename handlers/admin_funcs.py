from __future__ import annotations

from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from store import *
from classes.general import *
from classes.training import *
from handlers.other.config import *
from handlers.other.additional_funcs import *
from handlers.other.menu import *
from non_public.bot import developer_id
from typing import NoReturn
import pandas as pd
from classes.training import Exercise
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from shutil import copy
import json
import os
import re

def excel_form_write(coach: Coach, user: User) -> NoReturn:
	form_params = coach.special_excel_form(user)
	if not form_params:
		exercises = coach.raw_exercises()
		dct = {
			i: [j['exercise_name'] if j['exercise_unit'] is None else j['exercise_name'] +
				f' ({exercise_info()[j["exercise_unit"]]})' for j in exercises if j['category_name'] == i] for i in
			set(sorted([k['category_name'] for k in exercises]))
		}
		df1 = pd.DataFrame.from_dict(dct, orient='index').transpose()

		dct1 = {
			'Тренировка №': ['1' for i in range(12)] + ['2' for i in range(12)] + ['3' for i in range(12)],
			'Упражнение №': list(range(1, 13)) * 3,
			'Категория': [],
			'Название упражнения': [],
			'Отягощение': [],
			'Подходы': [],
			'Повторения': [],
			'Доп. условия': [],
			'Видео-отчет': []
		}
		df = pd.DataFrame.from_dict(dct1, orient='index').transpose()

		with pd.ExcelWriter(f'План тренировки ({user.fullname}).xlsx', mode='w', engine='xlsxwriter') as writer:

			df.style.set_properties(**{'text-align': 'center'}).to_excel(writer, sheet_name='Plan', index=False)
			workbook = writer.book
			worksheet = writer.sheets['Plan']
			merge_format = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
			for num in df['Тренировка №'].unique():
				u = df.loc[df['Тренировка №'] == num].index.values + 1
				if len(u) < 2:
					pass
				else:
					worksheet.merge_range(u[0], 0, u[-1], 0, df.loc[u[0], 'Тренировка №'], merge_format)
			for column in df:
				column_length = max(df[column].astype(str).map(len).max(), len(column))
				col_idx = df.columns.get_loc(column)
				writer.sheets['Plan'].set_column(col_idx, col_idx, column_length + 20)
			for num in range(2, 38):
				worksheet.data_validation(f'C{num}', {'validate': 'list',
													  'source': '=Exercises!$A$1:$Z$1'})
				worksheet.data_validation(f'D{num}', {'validate': 'list',
													  'source': f"=OFFSET(Exercises!$A$1,1,MATCH($C${num},Exercises!$A$1:$Z$1,0)-1,"
																f"COUNTA(OFFSET(Exercises!$A$1,1,MATCH($C${num},Exercises!$A$1:$Z$1,0)-1,100,1)),1)"})
				worksheet.data_validation(f'E{num}', {'validate': 'decimal',
													  'criteria': '>',
													  'value': 0})
				worksheet.data_validation(f'F{num}', {'validate': 'integer',
													  'criteria': '>',
													  'value': 0})
				worksheet.data_validation(f'G{num}', {'validate': 'integer',
													  'criteria': '>',
													  'value': 0})
				worksheet.data_validation(f'I{num}', {'validate': 'integer',
													  'criteria': 'between',
													  'minimum': 0,
													  'maximum': 1})

			df1.to_excel(writer, sheet_name='Exercises', index=False)
	else:
		base_exercises = [Exercise(i, coach=False).name for i in form_params]
		exercises = coach.raw_exercises()
		dct = {
			i: [j['exercise_name'] if j['exercise_unit'] is None else
				j['exercise_name'] + f' ({exercise_info()[j["exercise_unit"]]})' for j in exercises if j['category_name'] == i] for i in
			set(sorted([k['category_name'] for k in exercises]))
		}
		copy('data/specs/exercises/advanced_template.xlsx', f'План тренировки ({user.fullname}).xlsx')
		df1 = pd.DataFrame.from_dict(dct, orient='index').transpose()
		with pd.ExcelWriter(f'План тренировки ({user.fullname}).xlsx', mode='a', engine='openpyxl') as writer:
			df1.to_excel(writer, sheet_name='Exercises', index=False)
		wb = openpyxl.load_workbook(f'План тренировки ({user.fullname}).xlsx')
		worksheet = wb['Plan']
		exs_without_unit = []
		exs_with_non_kg_unit = []
		for ex in base_exercises:
			letter = ['B', 'C', 'D', 'E'][base_exercises.index(ex)]
			for num in [2, 8, 14]:
				cell = f'{letter}{num}'
				worksheet[cell] = ex
				ex_obj = Exercise.get_self_by_name(ex)
				if ex_obj.unit is None:
					exs_without_unit.append(cell)
				if not ex_obj.unit is None and ex_obj.unit != 'kg':
					exs_with_non_kg_unit.append({cell: ex_obj.unit})
		if len(base_exercises) < 4:
			letters = ['B', 'C', 'D', 'E'][len(base_exercises):]
			for letter in letters:
				for num in [2, 8, 14]:
					cell = f'{letter}{num}'
					worksheet[cell] = 'пусто'

		# data validation below
		edited_cells = []
		exs_non_weight_dv = DataValidation(type='textLength', operator='lessThan', formula1=1, showErrorMessage=True)
		exs_non_weight_dv.error = 'Нельзя указать отягощение для упражнения, в котором оно не используется!'
		exs_non_weight_dv.errorTitle = 'Ошибка: тип упражнения'
		exs_non_weight_dv.prompt = 'Упражнение без отягощения'
		exs_non_weight_dv.promptTitle = 'Отягощение'
		if any(exs_without_unit):
			for cell in exs_without_unit:
				letter, num = cell[0], int(cell[1])
				exs_non_weight_dv.add(worksheet[f"{letter}{num + 1}"])
				edited_cells.append(f'{letter}{num + 1}')

		exs_non_kg_unit_dv = DataValidation(showErrorMessage=True)
		if any(exs_with_non_kg_unit):
			for ex in exs_with_non_kg_unit:
				cell = next(iter(ex.keys()))
				letter, num = cell[0], int(cell[1])
				unit = next(iter(ex.values()))
				if unit == 'meters':
					worksheet[f'{letter}{num + 2}'] = 'интервалы/метры'
					exs_non_kg_unit_dv.type = 'textLength'
					exs_non_kg_unit_dv.operator = 'lessThan'
					exs_non_kg_unit_dv.formula1 = 1
					exs_non_kg_unit_dv.error = 'Нельзя указать отягощение для упражнения с единицей измерения "метры"!'
					exs_non_kg_unit_dv.errorTitle = 'Ошибка: тип упражнения'
					exs_non_kg_unit_dv.prompt = "Единица измерения упражнения: метры"
					exs_non_kg_unit_dv.promptTitle = 'Упражнение с нестандартной единицей измерения'
					exs_non_kg_unit_dv.add(worksheet[f'{letter}{num + 1}'])
					exs_non_kg_unit_dv.formula1 = 8
					exs_non_kg_unit_dv.error = 'Подходы и повторения должны быть в формате: 2/2000.'
					exs_non_kg_unit_dv.errorTitle = 'Ошибка: тип данных'
					exs_non_kg_unit_dv.add(worksheet[f"{letter}{num + 2}"])
					edited_cells.append(cell)

		weight_dv = DataValidation(type='decimal', operator='greaterThan', formula1=0, showErrorMessage=True)
		weight_dv.error = 'Отягощение должно указываться в виде целого или дробного числа!'
		weight_dv.errorTitle = 'Ошибка: тип данных'
		weight_dv.prompt = 'Единица измерения: кг'
		weight_dv.promptTitle = 'Отягощение'
		for row in [3, 9, 15]:
			for col in ['B', 'C', 'D', 'E']:
				if not f'{col}{row}' in edited_cells:
					weight_dv.add(worksheet[f'{col}{row}'])
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			weight_dv.add(worksheet[f'H{row}'])

		# --------
		sets_repeats_dv = DataValidation(type='textLength', operator='lessThan', formula1=6, showErrorMessage=True)
		sets_repeats_dv.prompt = 'Укажите повторения и подходы в нужном формате по примерам: 5/6, 4/12, /50 (' \
								 'если не определено количество подходов), 5/ (если не определено количество повторений).'
		sets_repeats_dv.promptTitle = 'Подходы/повторения'
		sets_repeats_dv.error = 'Количество знаков не может быть больше 6!'
		sets_repeats_dv.errorTitle = 'Ошибка: кол-во знаков'
		for row in [4, 10, 16]:
			for col in ['B', 'C', 'D', 'E']:
				sets_repeats_dv.add(worksheet[f'{col}{row}'])
				worksheet[f'{col}{row}'].data_type = 's'
		# --------
		terms_dv = DataValidation(type='textLength', operator='lessThan', formula1=150, showErrorMessage=True)
		terms_dv.prompt = 'Опишите необходимые условия по выполнению упражнения.'
		terms_dv.promptTitle = 'Условия упражнения'
		terms_dv.error = 'Условия не могут быть длиной более 150 символов!'
		terms_dv.errorTitle = 'Ошибка: кол-во знаков'
		for row in [5, 11, 17]:
			for col in ['B', 'C', 'D', 'E']:
				terms_dv.add(worksheet[f'{col}{row}'])
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			terms_dv.add(worksheet[f'K{row}'])
		# --------
		exs_category_dv = DataValidation(type='list', formula1='=Exercises!$A$1:$Z$1', showErrorMessage=True)
		exs_category_dv.error = 'Нужно выбрать категорию упражнений из списка!'
		exs_category_dv.errorTitle = "Ошибка: ввод данных"
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			exs_category_dv.add(worksheet[f"F{row}"])
		# --------
		exs_dvs = []
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			formula_exs = f"=OFFSET(Exercises!$A$1,1,MATCH($F${row},Exercises!$A$1:$Z$1,0)-1," +\
						f"COUNTA(OFFSET(Exercises!$A$1,1,MATCH($F${row},Exercises!$A$1:$Z$1,0)-1,100,1)),1)"
			exs_name_dv = DataValidation(type='list', formula1=formula_exs, showErrorMessage=True)
			exs_name_dv.error = 'Нужно выбрать упражнение из списка!'
			exs_name_dv.errorTitle = 'Ошибка: ввод данных'
			exs_name_dv.add(worksheet[f"G{row}"])
			exs_dvs.append(exs_name_dv)
		# --------
		sets_dv = DataValidation(type='decimal', operator='greaterThan', formula1=0, showErrorMessage=True)
		sets_dv.error = 'Количество подходов должно указываться в виде целого числа!'
		sets_dv.errorTitle = 'Ошибка: тип данных'
		sets_dv.prompt = 'Целое число'
		sets_dv.promptTitle = 'Количество подходов'
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			sets_dv.add(worksheet[f'I{row}'])
		# --------
		repeats_dv = DataValidation(type='decimal', operator='greaterThan', formula1=0, showErrorMessage=True)
		repeats_dv.error = 'Количество повторений должно указываться в виде целого числа!'
		repeats_dv.errorTitle = 'Ошибка: тип данных'
		repeats_dv.prompt = 'Целое число'
		repeats_dv.promptTitle = 'Количество повторений'
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			repeats_dv.add(worksheet[f'J{row}'])
		# --------
		video_report_dv = DataValidation(type='decimal', operator='equal', formula1=1, showErrorMessage=True)
		video_report_dv.error = 'Если хотите сделать видео-отчет по упражнению обязательным, укажите число 1.\n' \
								'Если нет - оставьте поле пустым!'
		video_report_dv.errorTitle = "Ошибка: ввод данных"
		video_report_dv.prompt = 'Оставьте поле пустым, если видео-отчет не нужен. Если нужен - укажите число 1.'
		video_report_dv.promptTitle = "Видео-отчет"
		for row in [*range(3, 7), *range(9, 13), *range(15, 19)]:
			video_report_dv.add(worksheet[f'L{row}'])

		dvs_list = [sets_repeats_dv, terms_dv, weight_dv, exs_category_dv, *exs_dvs,
					sets_dv, repeats_dv, video_report_dv, exs_non_kg_unit_dv, exs_non_weight_dv]
		for dv in dvs_list:
			worksheet.add_data_validation(dv)
		wb.save(f'План тренировки ({user.fullname}).xlsx')
		wb.close()

def excel_form_read(coach, user, filename):
	reading_type = 'standard' if not coach.special_excel_form(user) else 'advanced'
	exercises = list(map(lambda x: Exercise(x['exercise_id'], coach=False), coach.raw_exercises()))
	exercises_names = [i.name for i in exercises]
	from non_public.bot import bot
	checking = True
	if reading_type == 'standard':
		plan = json.loads(pd.read_excel(filename).to_json(orient='records', force_ascii=False))
		os.remove(filename)
		out = list(filter(lambda x: not x['Название упражнения'] is None, plan))
		if out:
			if all([(i['Название упражнения'] if not any(['(кг)' in i['Название упражнения'], "(м)" in
														  i['Название упражнения']]) else
					' '.join(i['Название упражнения'].split(' (')[:-1])) in exercises_names for i in out]):
				plans = {}
				for number in [1.0, 2.0, 3.0]:
					for i in out:
						if not i['Тренировка №']:
							for j in out:
								if j['Тренировка №'] and out.index(j) < out.index(i):
									i['Тренировка №'] = j['Тренировка №']
					plan = [i for i in out if i['Тренировка №'] == number]
					exs = []
					for ex in plan:
						if any(['(кг)' in ex['Название упражнения'], '(м)' in ex['Название упражнения']]):
							ex['Название упражнения'] = ' '.join(ex['Название упражнения'].split(' (')[:-1])
						if ex['Название упражнения'] in map(lambda x: x.name, exercises):
							raw_ex = Exercise(
								[i.exercises_id for i in exercises if i.name == ex['Название упражнения']][0],
								coach=False)
							repeats = ex['Повторения'] if ex['Повторения'] else "NULL"
							sets = ex['Подходы']
							if sets is None and repeats is None:
								sets = 1
							weight = ex['Отягощение']
							if not raw_ex.unit and not weight is None:
								msg = bot.send_message(coach.chat_id, 'Упражнение, которое выполняется без инвентаря, не может выполняться с отягощением.')
								del_msgs('main_admin', coach)
								temp_msgs('main_admin', coach, msg)
								return None, False
							terms = ex['Доп. условия']
							new_coach_ex = Exercise.new_coach_exercise(coach, raw_ex, repeats, sets, weight, terms)
							exs.append((Exercise(new_coach_ex), ex['Видео-отчет']))
					plans[int(number)] = exs
				return plans, checking
			else:
				msg = bot.send_message(coach.chat_id,
									   'Некоторые из упражнений отсутствуют в базе данных. Попробуйте еще раз.')
				del_msgs('main_admin', coach)
				temp_msgs('main_admin', coach, msg)
				return None, False
		else:
			msg = bot.send_message(coach.chat_id, 'Вы не заполнили таблицу! Попробуйте заново.')
			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)
			return None, False
	elif reading_type == 'advanced':
		workbook = openpyxl.load_workbook(filename)
		os.remove(filename)
		worksheet = workbook.active
		letters, nums = ['B', 'C', 'D', 'E'], [2, 8, 14]
		base_exs_cells = []
		for letter in letters:
			for num in nums:
				cell = worksheet[f'{letter}{num}']
				if cell.value in exercises_names:
					weight, sets_repeats, terms = worksheet[f'{letter}{num + 1}'].value, worksheet[f'{letter}{num + 2}'].value, \
						worksheet[f'{letter}{num + 3}'].value
					if any([weight, sets_repeats, terms]):
						base_exs_cells.append((letter, num))
		if not any(base_exs_cells):
			msg = bot.send_message(coach.chat_id, 'Вы не внесли базовые упражнения! Попробуйте заново.')
			del_msgs('main_admin', coach)
			temp_msgs('main_admin', coach, msg)
			return None, False
		else:
			exs_for_plan = {1: [],
							2: [],
							3: []}
			d = {2: 1, 8: 2, 14: 3}
			for letter, num in base_exs_cells:
				training_plan_number = d[num]
				ex = Exercise.get_self_by_name(worksheet[f'{letter}{num}'].value)
				weight = worksheet[f'{letter}{num + 1}'].value
				if not weight is None:
					if ex.unit != 'kg':
						msg = bot.send_message(coach.chat_id, 'Упражнение, которое выполняется без инвентаря, не может выполняться с отягощением.')
						del_msgs('main_admin', coach)
						temp_msgs('main_admin', coach, msg)
						return None, False
				amount = worksheet[f'{letter}{num + 2}'].value
				terms = worksheet[f'{letter}{num + 3}'].value
				if re.fullmatch(r'\d+/\d+', amount):
					amount = amount.split('/')
					sets, repeats = int(amount[0]), int(amount[1])
				elif re.fullmatch(r'\d+/', amount):
					amount = amount.replace('/', '')
					sets, repeats = int(amount), None
				elif re.fullmatch(r'/\d+', amount):
					amount = amount.replace('/', '')
					sets, repeats = None, int(amount)
				else:
					msg = bot.send_message(coach.chat_id, 'Неправильный формат поля "Подходы/повторения".\n'
														  'Попробуйте заново.')
					del_msgs('main_admin', coach)
					temp_msgs('main_admin', coach, msg)
					return None, False
				new_coach_ex = Exercise.new_coach_exercise(coach, ex, repeats, sets, weight, terms)
				exs_for_plan[training_plan_number].append((Exercise(new_coach_ex), True))
			additional_exs_rows = [*range(3,7), *range(9, 13), *range(15, 19)]
			d = {range(3,7): 1,
				 range(9, 13): 2,
				 range(15,19): 3}
			for row in additional_exs_rows:
				if not worksheet[f'G{row}'].value is None:
					for rng, number in d.items():
						if row in rng:
							training_plan_number = number
							break
					ex_name = worksheet[f'G{row}'].value if not any(['(кг)' in worksheet[f'G{row}'].value, "(метры)" in
																	 worksheet[f'G{row}'].value]) else ' '.join(worksheet[f'G{row}'].value.split(' (')[:-1])
					if ex_name in exercises_names:
						ex = Exercise.get_self_by_name(ex_name)
						weight = worksheet[f'H{row}'].value
						sets = worksheet[f'I{row}'].value
						repeats = worksheet[f'J{row}'].value
						terms = worksheet[f'K{row}'].value
						video_report = True if worksheet[f'L{row}'].value == 1 else False
						new_coach_ex = Exercise.new_coach_exercise(coach, ex, repeats, sets, weight, terms)
						exs_for_plan[training_plan_number].append((Exercise(new_coach_ex), video_report))
					else:
						msg = bot.send_message(coach.chat_id, f'Упражнение "{ex_name}" отсутствует в базе данных.\n'
															  f'Попробуйте еще раз.')
						del_msgs('main_admin', coach)
						temp_msgs('main_admin', coach, msg)
						return None, False
			return exs_for_plan, checking


def blacklist_checking(user, callback=False):
	with database() as connection:
		with connection.cursor() as db:
			if not callback:
				db.execute(f"SELECT users_chat_id FROM blacklist WHERE users_chat_id = '{user.chat.id}'")
				check_lst = db.fetchall()
			else:
				db.execute(f"SELECT users_chat_id FROM blacklist WHERE users_chat_id = '{user.chat.id}'")
				check_lst = db.fetchall()
			return True if not check_lst else False

def training_types(user=None, tariff=None):
	types = {'personal': 'персонально', 'split': 'сплит', 'group': 'группа', 'personal_online': 'персонально онлайн', 'free': 'бесплатно (пробно)'}
	types_for_user = {'personal': 'персональные', 'split': 'сплит', 'group': 'групповые', 'personal_online': 'персональные онлайн', 'free': 'бесплатные (пробные)'}
	if user:
		sessions = user.subscription_plan['sessions_count']
		if sessions:
			result = ', '.join([' — '.join([f'{types_for_user[i]}', str(sessions[i])]) for i in sessions if sessions[i]]) if any(sessions.values()) else 'нет'
			return result
	if tariff:
		return '\n'.join([f'- _{types[i]}_: *{j}*' for i, j in tariff.sessions.items() if j])
	return types

def tariff_info():
	tariff_words = {'name': '📜 Название тарифа', 'description': '❓ Описание тарифа',
						   'sessions': '📍 Тип и количество тренировок', 'group': 'групповые',
						   'personal': 'персональные', 'personal_online': 'персональные онлайн', 'split': 'сплит',
						   'period': '🕘 Период действия', 'canceling_amount': '❌ Доступные отмены записей на занятия',
						   'cost': '💷 Стоимость (рублей)', 'users_permissions': '😎 Уровень доступа',
						   'my_records': 'Мои рекорды', 'individual_trainings': 'Индивидуальные тренировки',
							'self_trainings': 'Самостоятельные тренировки', 'my_diet': 'Контролирование диеты'}
	return tariff_words

def exercise_info():
	exercise_words = {'zero': 'нулевая',
					  'low': 'низкая',
					  'medium': 'средняя',
					  'high': 'высокая',
					  'athlete': 'атлет',
					  'kg': 'кг',
					  'minutes': 'мин',
					  'hours': 'ч',
					  'cantimeters': 'см',
					  'meters': 'м',
					  'strength': 'силовое',
					  'balance': 'баланс',
					  'cardio': 'кардио',
					  'stretch': 'растяжка',
					  'chest': 'грудь','back': "спина",'legs': "ноги",'pelvis': "таз",'shoulders': "плечи",'arms': "руки",'abs': "пресс", 'fullbody': "все тело",
					  'gym': "в спортзале",'sports_ground': "на спортивной площадке",'home': "дома", 'everywhere': "в спортзале, дома, на спортивной площадке",
					  'terms': 'Условия', 'sets': 'Количество подходов', 'repeats': 'Количество повторений', 'weight': 'Величина отягощения',
					  'video': 'Видео', 'image': 'Изображение', 'audio': 'Аудио'}
	return exercise_words

def coaches_disciplines():
	return sorted(['пауэрлифтинг', "бокс", "фитнес", "йога", "пилатес", "бодибилдинг", 'похудение',
				   'набор мышечной массы', 'стретчинг', 'айкидо', 'карате', 'групповые тренировки', 'ОФП',
				   'легкая атлетика', 'тяжелая атлетика', 'гиревой спорт', 'фитнес-бикини', 'бодифитнес', 'кроссфит',
				   'функционал', 'воркаут', 'спортивное ориентирование', 'скалолазание', 'паркур', 'велосипед', 'триатлон'])

def coach_description():
	return [
		'*Образование*',
		'*Специализация в тренерской деятельности*',
		'*Сертификаты*',
		'*Достижения*',
		'*Стаж/история работы*',
		'*Преимущества*',
		'*Соцсети*'
	]


def tariff_permissions(tariff):
	dct = {
		'self_trainings': '"Самостоятельные тренировки"',
		'individual_trainings': '"Индивидуальные тренировки"',
		'my_records': '"Мои рекорды"',
		'my_diet': '"Моя диета"',
	}
	return ';\n'.join([f'- _{dct[i]}_' for i in tariff.users_permissions if tariff.users_permissions[i]])


def admin(bot):
	@bot.message_handler(commands=['start'], func=lambda user: coach_check(user) and blacklist_checking(user))
	def admin_main_menu(message):
		coach = Coach(message.chat.id)
		if not forbidden_status(coach):
			with database() as connection:
				with connection.cursor() as db:
					db.execute(f"SELECT users.id FROM users JOIN coachs ON users.id = coachs.users_id WHERE chat_id = '{message.chat.id}'")
					coachs_checking = db.fetchall()
			if coachs_checking:
				form = coach.form()
				if form:
					if not form['registering_finished']:
						with database() as connection:
							with connection.cursor() as db:
								db.execute(f"UPDATE coachs_forms SET registering_finished = {True} WHERE coachs_id = {coach.id}")
								connection.commit()
						bot.send_message(coach.chat_id, '*Поздравляем с окончанием регистрации*! Теперь для вас доступно меню тренера.\n\n'
																   'Рекомендуем поскорее сформировать свой первый тариф для клиентов в меню *"Общее"* 👉 *"Тарифы"* 👉 *"Конструктор тарифов"*.\n'
																   'До этого клиенты _не смогут_ оплатить занятия и записаться на них!\n\n'
																   'А также уже можно придумать уровни физподготовки для своих клиентов, по которым вы будете создавать тренировочные планы для самостоятельного выполнения.\n'
																   'Это можно сделать в меню *"Общее"* 👉 *"Тренировки клиентов"* 👉 *"Уровни тренировок"*.', reply_markup=admin_keyboard(), parse_mode='Markdown')
					else:
						bot.send_message(message.chat.id, 'Доброго времени суток. Используйте меню строго по назначению 😃\n\n'
														  '🤪 Приятного пользования!', reply_markup=admin_keyboard())
				else:
					msg = bot.send_message(message.chat.id, 'Для начала работы нужно заполнить стартовую анкету тренера.\n\n'
															"Перейдите по ссылке и сделайте это на нашем сайте: <a href='https://google.ru'>тестовая ссылка</a>.\n\n"
															"После этого меню будет разблокировано.\n\n"
									 "Когда заполните форму, отправьте боту команду: /start.", parse_mode='HTML')
					temp_msgs('main_admin', coach, msg)
			else:
				msg = bot.send_message(message.chat.id, 'Вы еще не прошли процесс регистрации в качестве тренера!\n'
												  'Нажмите, чтобы начать заново: /start_coach.')
				temp_msgs('main_admin', coach, msg)
		else:
			pass


	@bot.message_handler(func=lambda message: coach_check(message) and message.text == '📃 Общее' and blacklist_checking(message))
	def admin_others(message):
		coach = Coach(message.chat.id)
		general_menu = InlineKeyboardMarkup(row_width=1)
		button_1 = InlineKeyboardButton(text='‼️ Текущие задачи', callback_data='coach_tasks')
		button_2 = InlineKeyboardButton(text='📜 Расписание', callback_data='my_schedule')
		button_3 = InlineKeyboardButton(text='💲 Коммерция', callback_data='my_commerce')
		button_4 = InlineKeyboardButton(text='❔ Опросы', callback_data='my_forms')
		button_5 = InlineKeyboardButton(text='🏋️ Тренировки клиентов', callback_data='my_clients_training')
		button_6 = InlineKeyboardButton(text='🔌 Настройки бота', callback_data='set_my_bot')
		button_7 = InlineKeyboardButton(text='❓ Помощь', callback_data='coach_help')
		button_8 = InlineKeyboardButton(text='📝 Рассылки', callback_data='my_mailing')
		general_menu.add(button_1, button_2, button_3, button_4, button_5, button_6, button_7)
		if int(coach.chat_id )== developer_id:
			general_menu.add(button_8)
		msg = bot.send_message(message.chat.id, '🙂 Выберите нужный раздел.', reply_markup=general_menu)
		del_msgs('main_admin', coach)
		temp_msgs('main_admin', coach, msg)

	@bot.message_handler(func=lambda message: coach_check(message) and message.text == '👨‍🦲 Клиенты' and blacklist_checking(message))
	def admin_clients(message):
		coach = Coach(message.chat.id)
		others_menu = InlineKeyboardMarkup(row_width=1)
		button_1 = InlineKeyboardButton(text='📜 Список всех клиентов', callback_data='admin_all_users')
		button_2 = InlineKeyboardButton(text='👉 Выбрать клиента', callback_data='admin_choose_user')
		button_3 = InlineKeyboardButton(text='📍 Отчеты по тренировкам', callback_data='users_reports')
		others_menu.add(button_1, button_2, button_3)

		lst = coach.clients_for_menu()
		if lst:
			msg = bot.send_message(message.chat.id, f'📋 *Активных клиентов/всего клиентов*: {len([i for i in lst if datetime.today() - i[2] <= timedelta(days=7)])}/{len(lst)}\n'
													f'*Выберите* нужное действие.', reply_markup=others_menu, parse_mode='Markdown')
		else:
			msg = bot.send_message(message.chat.id, 'Клиентов пока нет.')
		del_msgs('main_admin', coach)
		temp_msgs('main_admin', coach, msg)