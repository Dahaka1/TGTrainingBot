from datetime import date
from typing import Union
from datetime import datetime

days_of_week = {
   1: "понедельник",
    2: "вторник",
    3: "среда",
    4: "четверг",
    5: "пятница",
    6: "суббота",
    7: "воскресенье"
}

months = [
        'январь',
        'февраль',
        'март',
        'апрель',
        'май',
        'июнь',
        'июль',
        'август',
        'сентябрь',
        'октябрь',
        'ноябрь',
        'декабрь']


def fullname_of_date(day_of_week: Union[date, str]) -> str:
    if isinstance(day_of_week, str):
        day_of_week = date.fromisoformat(day_of_week)
    if day_of_week.isoweekday() == 1:
        return f'Пн {date.strftime(day_of_week, "%d.%m.%Y")}'
    elif day_of_week.isoweekday() == 2:
        return f'Вт {date.strftime(day_of_week, "%d.%m.%Y")}'
    elif day_of_week.isoweekday() == 3:
        return f'Ср {date.strftime(day_of_week, "%d.%m.%Y")}'
    elif day_of_week.isoweekday() == 4:
        return f'Чт {date.strftime(day_of_week, "%d.%m.%Y")}'
    elif day_of_week.isoweekday() == 5:
        return f'Пт {date.strftime(day_of_week, "%d.%m.%Y")}'
    elif day_of_week.isoweekday() == 6:
        return f'Сб {date.strftime(day_of_week, "%d.%m.%Y")}'
    elif day_of_week.isoweekday() == 7:
        return f'Вс {date.strftime(day_of_week, "%d.%m.%Y")}'

def name_of_day(day_of_week):
    if day_of_week.isoweekday() == 1:
        return 'Пн'
    elif day_of_week.isoweekday() == 2:
        return 'Вт'
    elif day_of_week.isoweekday() == 3:
        return 'Ср'
    elif day_of_week.isoweekday() == 4:
        return 'Чт'
    elif day_of_week.isoweekday() == 5:
        return 'Пт'
    elif day_of_week.isoweekday() == 6:
        return 'Сб'
    elif day_of_week.isoweekday() == 7:
        return 'Вс'

def current_time(time_iso: [str,datetime]) -> str:
    if isinstance(time_iso, str):
        try:
            time_iso = datetime.fromisoformat(time_iso)
        except:
            return time_iso
    result = time_iso.strftime('%d.%m.%Y, %H:%M')
    return result