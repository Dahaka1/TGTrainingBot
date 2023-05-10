from handlers.general import *
from handlers.admin_funcs import admin
from handlers.checking import *
from threading import Thread
from non_public.bot import *
from datetime import datetime


def handlers():
	try:
		main(bot)
		admin(bot)
		th_2 = Thread(target=checking_every_hour, args=(bot,))
		th_2.start()
		th_3 = Thread(target=checking_every_minute, args=(bot,))
		th_3.start()
		th_4 = Thread(target=spams, args=(bot,))
		th_4.start()
		bot.send_message(developer_id, f'Bot was started at {datetime.today().isoformat()}')

	except Exception as e:
		print(e)
		bot.send_message(developer_id, f'<b>Ошибка запуска!</b>\n\n{e}', parse_mode='HTML')


if __name__ == '__main__':
	handlers()
	bot.infinity_polling(timeout=10, long_polling_timeout=5)