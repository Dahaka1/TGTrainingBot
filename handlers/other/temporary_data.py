from pickle import *
from typing import Optional
import os


def temporary_dict(new_dct=None, update=False) -> Optional[dict]:
	file_path = 'data/temp_data/temp_dict.pickle'
	if not os.path.exists(file_path):
		new_file = open(file_path, 'wb')
		new_file.close()
	if os.stat(file_path).st_size != 0:
		if not update:
			try:
				with open(file_path, 'rb') as f:
					dct = load(f)
			except FileNotFoundError:
				dct = None
			if not dct is None:
				return dct
		else:
			with open(file_path, 'wb') as f:
				dump(new_dct, f)


def general_dict(new_dct=None, update=False) -> Optional[dict]:
	file_path = 'data/temp_data/general_dict.pickle'
	if not os.path.exists(file_path):
		new_file = open(file_path, 'wb')
		new_file.close()
	if os.stat(file_path).st_size != 0:
		if not update:
			try:
				with open(file_path, 'rb') as f:
					dct = load(f)
			except FileNotFoundError:
				dct = None
			if not dct is None:
				return dct
		else:
			with open(file_path, 'wb') as f:
				dump(new_dct, f)