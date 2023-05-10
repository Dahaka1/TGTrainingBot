import pandas as pd
from csv import DictReader
import pymysql
from pymysql.cursors import DictCursor
from mysql_config import *


#######################################
# CONNECTION FUNC
def database():
	try:
		connection = pymysql.connect(
			host=host,
			user=user,
			password=password,
			cursorclass=DictCursor,
			database=db_name
		)
		return connection
	except Exception as e:
		print('connection to database error ', e)


exercises = pd.read_excel('Упражнения.xlsx', sheet_name=0).to_csv('exercises.csv', index=None)
categories = pd.read_excel('Упражнения.xlsx', sheet_name=1).to_csv('categories.csv', index=None)
groups = exercises = pd.read_excel('Упражнения.xlsx', sheet_name=2).to_csv('groups.csv', index=None)
inventory = pd.read_excel('Упражнения.xlsx', sheet_name=3).to_csv('inventory.csv', index=None)


categories = list(DictReader(open('categories.csv', encoding='utf-8')))
exercises = list(DictReader(open('exercises.csv', encoding='utf-8')))
groups = list(DictReader(open('groups.csv', encoding='utf-8')))
inventory = list(DictReader(open('inventory.csv', encoding='utf-8')))



with database() as connection:
	with connection.cursor() as db:
		db.execute('SET FOREIGN_KEY_CHECKS = 0')
		db.execute(f"TRUNCATE TABLE inventory")
		db.execute(f"TRUNCATE TABLE exercises")
		db.execute(f"TRUNCATE TABLE exercises_categories")
		db.execute(f"TRUNCATE TABLE exercises_groups")
		db.execute('SET FOREIGN_KEY_CHECKS = 1')
		for i in inventory:
			if i['Название']:
				db.execute(f"INSERT INTO inventory (name, muscles_group, location) VALUES ('{i['Название']}', '{i['Мышечная группа']}', '{i['Расположение']}')")


		for i in groups:
			if i['Название']:
				db.execute(f"INSERT INTO exercises_groups (group_name, group_tags) VALUES ('{i['Название']}', '{i['Теги']}')")

		for i in categories:
			db.execute(f"INSERT INTO exercises_categories (exercises_group_id, category_name) VALUES (1, '{i['Название']}')")


		for i in exercises:
			if i['Название']:
				for j in categories:
					if j['Название'] == i['Категория']:
						category_id = j['№']
				for j in inventory:
					if j['Название'] == i['Инвентарь']:
						inventory_id = j['№']
				if i['Единица измерения'] and i['Инвентарь']:
					db.execute(f"INSERT INTO exercises (exercises_category_id, exercise_name, exercise_inventory_id, exercise_muscles_group, exercise_difficulty, exercise_type, exercise_unit, "
							   f"exercise_video_tutorial)"
							   f"VALUES ({category_id}, '{i['Название']}', {inventory_id}, '{i['Мышечная группа']}', '{i['Сложность']}', '{i['Тип']}', '{i['Единица измерения']}', '{i['Ссылка на видео-урок']}')")
				elif i['Инвентарь'] and not i['Единица измерения']:
					db.execute(
						f"INSERT INTO exercises (exercises_category_id, exercise_name, exercise_inventory_id, exercise_muscles_group, exercise_difficulty, exercise_type, exercise_video_tutorial)"
						f"VALUES ({category_id}, '{i['Название']}', {inventory_id}, '{i['Мышечная группа']}', '{i['Сложность']}', '{i['Тип']}', '{i['Ссылка на видео-урок']}')")
				elif i['Единица измерения'] and not i['Инвентарь']:
					db.execute(
						f"INSERT INTO exercises (exercises_category_id, exercise_name, exercise_muscles_group, exercise_difficulty, exercise_type, exercise_unit, exercise_video_tutorial)"
						f"VALUES ({category_id}, '{i['Название']}', '{i['Мышечная группа']}', '{i['Сложность']}', '{i['Тип']}', '{i['Единица измерения']}', '{i['Ссылка на видео-урок']}')")
				else:
					db.execute(
						f"INSERT INTO exercises (exercises_category_id, exercise_name, exercise_muscles_group, exercise_difficulty, exercise_type, exercise_video_tutorial)"
						f"VALUES ({category_id}, '{i['Название']}', '{i['Мышечная группа']}', '{i['Сложность']}', '{i['Тип']}', '{i['Ссылка на видео-урок']}')")


		connection.commit()

print('its ok')

