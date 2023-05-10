from store import *


def new_payment(user, tariff, payment_sum, payment_date):
	with database() as connection:
		with connection.cursor() as db:
			db.execute(f"INSERT INTO payments (coachs_id, users_id, tariff, payment_amount, payment_date) VALUES ({user.current_coach_id}, {user.id}, '{tariff}', {payment_sum}, {payment_date})")
			connection.commit()