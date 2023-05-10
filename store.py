import pymysql
from pymysql.cursors import DictCursor
from non_public.mysql_config import *

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