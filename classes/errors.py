from datetime import datetime
from sys import argv, exc_info
from traceback import format_exc
class Error:
	"""
	Добавил простое логирование, а то устал вручную искать ошибки в консоли
	"""
	def __init__(self):
		self.datetime = datetime.now()
		self.filename = argv[0]
		self.error_type, self.error = exc_info()[0], exc_info()[1]
		self.traceback = format_exc()

	def __str__(self):
		splitting = '*' * 50 + '\n' + '*' * 50
		text = f'Raised error type {self.error_type}:\n' + \
			    '- CONTENT: ' + \
				f'"{self.error}"\n' + \
				 '- TRACEBACK:' + '\n' + \
				f'"{self.traceback.rstrip()}"\n' + \
			    '- DATETIME: ' + \
				self.datetime.isoformat() + f'\n\n{splitting}\n\n'
		return text

	def log(self):
		try:
			log_file = open('non_public/errors_log.txt', 'a', encoding='utf-8')
		except FileNotFoundError:
			log_file = open('non_public/errors_log.txt', 'w', encoding='utf-8')
		log_file.write(str(self))
		log_file.close()
