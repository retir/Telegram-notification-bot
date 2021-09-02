import telebot
from telebot import types
from datetime import datetime
from RBTree import RedBlackTree
import threading
import json


try:
    with open('data.txt') as json_database:
        database = json.load(json_database)
except json.JSONDecodeError:
    database = {}
    with open('data.txt', 'w') as json_database:
        json.dump(database, json_database)

notifications_count = len(database)


class Notification:
    def __init__(self, time, body, date, user_id, time_interval, time_int=0, notif_id=None):
        if notif_id is None:
            global notifications_count
            self.notif_id = notifications_count
            notifications_count += 1
        else:
            self.notif_id = notif_id

        if time_int == 0:
            self.time = datetime.strptime(
                date + " " + time, "%d.%m.%Y %H:%M"
            ).timestamp()
        else:
            self.time = time_int

        self.user_id = user_id
        self.body = body
        self.time_interval = time_interval

    def __lt__(self, other):
        return self.time < other.time

    def __gt__(self, other):
        return self.time > other.time

    def __le__(self, other):
        return self.time <= other.time

    def __ge__(self, other):
        return self.time >= other.time

    def __eq__(self, other):
        return self.time == other.time

    def __ne__(self, other):
        return self.time != other.time


notifications = RedBlackTree()
for notif_id in database:
    notif = database[notif_id]
    notification = notifications.insert(Notification(
        time=notif['time'],
        date=notif['date'],
        body=notif['body'],
        user_id=int(notif['user_id']),
        time_interval=int(notif['time_interval']),
        time_int=int(notif['time_int']),
        notif_id=int(notif_id)
    ))
bot = telebot.TeleBot("key")
event = threading.Event()
notifications_lock = threading.Lock()
event_lock = threading.Lock()


def database_update():
    global database
    with open('data.txt', 'w') as json_database:
        json.dump(database, json_database)


def notif_handler():
    global notifications
    global event

    while True:
        if notifications.get_min() is None:
            event.wait()
            event_lock.acquire()
            event = threading.Event()  # mutex?
            event_lock.release()

        notifications_lock.acquire()
        curr_request = notifications.get_min()
        curr_request_time = int(curr_request.time)
        curr_time = int(datetime.now().timestamp()) + 1

        while curr_request_time <= curr_time:
            bot.send_message(curr_request.user_id, curr_request.body)
            database.pop(curr_request.notif_id)
            database_update()
            notifications = notifications.remove(curr_request)
            next_notif_time = curr_request_time + curr_request.time_interval
            if curr_request.time_interval != 0 and next_notif_time < curr_time:
                next_notif_time += (
                    (curr_time - next_notif_time) // curr_request.time_interval + 1
                ) * curr_request.time_interval

            if curr_request.time_interval != 0:
                curr_request.time = next_notif_time
                notifications = notifications.insert(curr_request)
                database[curr_request.notif_id] = {'time': '',
                                                   'date': '',
                                                   'time_int': curr_request.time,
                                                   'body': curr_request.body,
                                                   'user_id': curr_request.user_id,
                                                   'time_interval': curr_request.time_interval}
                database_update()

            if notifications.get_min() is None:
                break
            curr_request = notifications.get_min()
            curr_request_time = int(curr_request.time)
            curr_time = int(datetime.now().timestamp()) + 1

        if notifications.get_min() is not None:
            wait_time = curr_request_time - curr_time
            notifications_lock.release()
            event.wait(wait_time)
            event_lock.acquire()
            event = threading.Event()  # mutex?
            event_lock.release()
        else:
            notifications_lock.release()


t1 = threading.Thread(name="handler", target=notif_handler)
t1.start()


def main_menu(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    key_new_notif = types.KeyboardButton(text="Создать напоминалку")
    keyboard.add(key_new_notif)

    key_del_notif = types.KeyboardButton(text="Удалить напоминалку")
    keyboard.add(key_del_notif)

    key_change_notif = types.KeyboardButton(text="Изменить напоминалку")
    keyboard.add(key_change_notif)

    key_my_notif = types.KeyboardButton(text="Мои напоминалки")
    keyboard.add(key_my_notif)

    bot.send_message(user_id, text="Что вам угодно, повелитель?", reply_markup=keyboard)


def show_notifications(chat_id, callback=""):
    notifications_lock.acquire()
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    if notifications.get_min() is None:
        none_notifications(chat_id)
        return False

    finded_notif = False
    for notif in notifications.inorder_traverse():
        if notif.user_id == chat_id:
            finded_notif = True
            format_ = f"%d.%m.%Y %H:%M "
            key_button = types.InlineKeyboardButton(
                text=datetime.fromtimestamp(notif.time).strftime(format_) + notif.body,
                callback_data=callback + str(notif.notif_id),
            )
            keyboard.add(key_button)

    if finded_notif is False:
        none_notifications(chat_id)
        return False

    notifications_lock.release()
    bot.send_message(chat_id, "Выбери напоминкалку", reply_markup=keyboard)
    return True


@bot.message_handler(content_types=["text"])
def message_handler(message):
    if message.text == "/start":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

        key_new_notif = types.KeyboardButton(text="Создать напоминалку")
        keyboard.add(key_new_notif)

        bot.send_message(
            message.from_user.id,
            text="Привет, можешь создать свою первую напоминалку!",
            reply_markup=keyboard,
        )

    elif message.text == "Создать напоминалку":
        bot.send_message(
            message.chat.id,
            "Напиши время, когда должно придти уведомление (в формате чч:мм)",
        )
        bot.register_next_step_handler(message, get_time)

    elif message.text == "Удалить напоминалку":
        show_notifications(message.chat.id, "delete")

    elif message.text == "Изменить напоминалку":
        if not show_notifications(message.chat.id, "change"):
            return

    elif message.text == "Мои напоминалки":
        show_notifications(message.chat.id, "my")
    else:
        main_menu(message.from_user.id)


def get_time(message, change=False, prev_notif_numb=0):
    # проверить на корректность
    if message.text is None:
        bot.send_message(
            message.from_user.id,
            "Нам нужен текст! Без него некуда...\n" "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(message, get_time, change, prev_notif_numb)
        return
    time_row = message.text[:5]
    time = time_row[:2] + ":" + time_row[3:5]
    try:
        assert 0 <= int(time[0:2]) <= 23
        assert 0 <= int(time[3:5]) <= 59
    except AssertionError:
        bot.send_message(
            message.from_user.id,
            "Неверный формат времени!\n"
            "Время должно быть формата чч:мм\n"
            "Попробуй ещё раз",
        )
        bot.register_next_step_handler(message, get_time, change, prev_notif_numb)
        return

    if not change:
        bot.send_message(
            message.from_user.id,
            "Когда должно придти первое уведомление?\n"
            "Напиши дату в формате дд.мм.гггг в пределах одного "
            "месяца",
        )
    else:
        bot.send_message(
            message.from_user.id,
            "Когда должно придти следующее уведомление?\n"
            "Напиши дату в формате дд.мм.гггг в пределах одного "
            "месяца",
        )
    bot.register_next_step_handler(message, get_date, time, change, prev_notif_numb)


def get_body(message, time, date, time_interval, change, prev_notif_numb):
    if message.text is None:
        bot.send_message(
            message.from_user.id,
            "Нам нужен текст! Без него некуда...\n" "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(
            message, get_body, time, date, time_interval, change, prev_notif_numb
        )
        return

    body = message.text
    user_id = message.from_user.id

    if not change:
        create_new_notification(time, body, date, user_id, time_interval)
        bot.send_message(user_id, "Напоминалка создана!")
        main_menu(user_id)
    else:
        deleted_notif = find_notif(str(prev_notif_numb))
        if deleted_notif is None:
            bot.send_message(
                user_id,
                "Кажется, напоминалка уже была удалена...\n" "Попробуйте ещё раз!",
            )
            main_menu(user_id)
        else:
            notificaion_remove(deleted_notif, user_id)
            create_new_notification(time, body, date, user_id, time_interval)
            bot.send_message(user_id, "Напоминалка изменена!")
            main_menu(user_id)


def get_date(message, time, change, prev_notif_numb):
    if message.text is None:
        bot.send_message(
            message.from_user.id,
            "Нам нужен текст! Без него некуда...\n" "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(message, get_date, time, change, prev_notif_numb)
        return

    date_row = message.text[:10]
    date = date_row[:2] + "." + date_row[3:5] + "." + date_row[6:10]
    try:
        date_time = datetime.strptime(date, "%d.%m.%Y").timestamp()
        now = datetime.now().timestamp()
        assert abs(now - date_time) // (60 * 60 * 24) <= 31
    except ValueError:
        bot.send_message(
            message.from_user.id,
            "Неверный формат даты либо выбрана слишком ранняя дата!\n"
            "Дата должна быть формата дд.мм.гггг\n"
            "Попробуй ещё раз",
        )
        bot.register_next_step_handler(message, get_date, time, change, prev_notif_numb)
        return
    except AssertionError:
        bot.send_message(
            message.from_user.id,
            "Выбрана слишком далёкая дата!\n"
            "Дата должна быть в пределах одного месяца, куда уж больше?!\n"
            "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(message, get_date, time, change, prev_notif_numb)
        return

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    key_per_day = types.KeyboardButton(text="Раз в день")
    keyboard.add(key_per_day)

    key_per_week = types.KeyboardButton(text="Раз в неделю")
    keyboard.add(key_per_week)

    key_per_month = types.KeyboardButton(text="Раз в месяц")
    keyboard.add(key_per_month)

    key_several_days = types.KeyboardButton(text="Раз в несколько дней")
    keyboard.add(key_several_days)

    key_several_hours = types.KeyboardButton(text="Раз в несколько часов")
    keyboard.add(key_several_hours)

    key_one_time = types.KeyboardButton(text="Один раз")
    keyboard.add(key_one_time)

    bot.send_message(
        message.from_user.id,
        "Как часто должны приходить уведомления?",
        reply_markup=keyboard,
    )
    bot.register_next_step_handler(
        message, get_interval, time, date, message.from_user.id, change, prev_notif_numb
    )


def get_interval(message, time, date, user_id, change, prev_notif_numb):
    if message.text is None:
        bot.send_message(
            message.from_user.id,
            "Нам нужен текст! Без него некуда...\n" "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(
            message, get_interval, time, date, user_id, change, prev_notif_numb
        )
        return

    per_type = message.text
    if per_type == "Раз в день":
        time_interval = 60 * 60 * 24
    elif per_type == "Раз в неделю":
        time_interval = 60 * 60 * 24 * 7
    elif per_type == "Раз в месяц":
        time_interval = 60 * 60 * 24 * 30
    elif per_type == "Раз в несколько дней":
        bot.send_message(
            user_id, "Раз в какое количество дней бот будет посылать сообщения?"
        )
        bot.register_next_step_handler(
            message, get_user_interval, time, date, per_type, change, prev_notif_numb
        )
        return
    elif per_type == "Раз в несколько часов":
        bot.send_message(
            user_id, "Раз в какое количество часов бот будет посылать сообщения?"
        )
        bot.register_next_step_handler(
            message, get_user_interval, time, date, per_type, change, prev_notif_numb
        )
        return
    elif per_type == "Один раз":
        time_interval = 0
    else:
        bot.send_message(user_id, "Не понимаю (\nПопробуй ещё раз!")
        bot.register_next_step_handler(
            message, get_interval, time, date, user_id, change, prev_notif_numb
        )
        return

    bot.send_message(user_id, "Какое сообщение должен присылать бот?")
    bot.register_next_step_handler(
        message, get_body, time, date, time_interval, change, prev_notif_numb
    )


def find_notif(str_id):
    notif_id = int(str_id)
    notifications_lock.acquire()

    for notif in notifications.inorder_traverse():
        print(type(notif.notif_id), type(notif_id))
        if notif.notif_id == notif_id:
            print('FIND')
            delete_notif = notif
            notifications_lock.release()
            return delete_notif
    notifications_lock.release()
    return None


def none_notifications(user_id):
    global notifications
    bot.send_message(user_id, "У вас нет напоминалок(")
    notifications_lock.release()
    main_menu(user_id)


# def change_body(message, new_time, new_time_int, current_notif):
#     if message.text == '-':
#         new_body = current_notif.body
#     else:
#         new_body = message.text
#     notificaion_remove(current_notif, message.from_user.id)
#     create_new_notification(new_time, new_body, message.from_user.id, 0,
#                             new_time_int)
#
#     bot.send_message(message.from_user.id, 'Напоминалка изменена!')
#     main_menu(message.from_user.id)
#     main_menu(message.from_user.id)


def create_new_notification(
    time, body, date, user_id, time_interval, prev_mess_id=0, new_time_int=0
):
    global notifications
    global notifications_count
    notifications_lock.acquire()
    notifications = notifications.insert(
        Notification(time, body, date, user_id, time_interval, new_time_int)
    )
    database[notifications_count - 1] = {'time': time,
                                         'date': date,
                                         'time_int': new_time_int,
                                         'body': body,
                                         'user_id': user_id,
                                         'time_interval': time_interval}
    database_update()

    notifications_lock.release()
    event_lock.acquire()
    event.set()
    event_lock.release()

    if prev_mess_id != 0:
        keyboard = types.InlineKeyboardMarkup()
        bot.edit_message_reply_markup(
            chat_id=user_id, message_id=prev_mess_id, reply_markup=keyboard
        )


def notificaion_remove(notification, chat_id):
    global notifications

    if notification is None:
        bot.send_message(chat_id, "BRUUH, напоминалка не найдена(")
        main_menu(chat_id)
        return False

    notifications_lock.acquire()

    database.pop(str(notification.notif_id))
    database_update()
    notifications = notifications.remove(notification)
    print('REMOVE')

    event_lock.acquire()
    event.set()
    event_lock.release()

    notifications_lock.release()
    return True


@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    print(call.data)
    global notifications

    if call.data[:14] == "del_notif_conf":
        _, notif_numb = call.data.split("#")
        keyboard = types.InlineKeyboardMarkup()
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=keyboard,
        )
        notif_to_delete = find_notif(notif_numb)
        if notif_to_delete is None:
            bot.send_message(call.message.chat.id, "Напоминалка уже была удалена :(")
            main_menu(call.message.chat.id)
            return
        notificaion_remove(notif_to_delete, call.message.chat.id)
        bot.send_message(call.message.chat.id, "Напоминалка успешно удалена !")
        main_menu(call.message.chat.id)

    elif call.data[:14] == "del_notif_deny":
        _, user_id = call.data.split("#")
        keyboard = types.InlineKeyboardMarkup()
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=keyboard,
        )
        main_menu(user_id)

    elif call.data[:6] == "delete":
        delete_notif = find_notif(call.data[6:])
        if delete_notif is None:
            print('deleted notif is none WTFFF')
        keyboard = types.InlineKeyboardMarkup()
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=keyboard,
        )

        key_yes = types.InlineKeyboardButton(
            text="Да", callback_data="del_notif_conf#" + call.data[6:]
        )
        keyboard.add(key_yes)

        key_no = types.InlineKeyboardButton(
            text="Нет", callback_data="del_notif_deny#" + str(delete_notif.user_id)
        )
        keyboard.add(key_no)

        format1 = "%d.%m.%Y"
        format2 = "%H:%M"
        bot.send_message(
            delete_notif.user_id,
            "Вы дествительно хотите удалить напоминалку, которая сработает\n"
            + f"{datetime.fromtimestamp(delete_notif.time).strftime(format1)} в "
            f"{datetime.fromtimestamp(delete_notif.time).strftime(format2)}?\n"
            f"Текст напоминалки:\n{delete_notif.body}",
            reply_markup=keyboard,
        )

    elif call.data[:6] == "change":
        keyboard = types.InlineKeyboardMarkup()
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=keyboard,
        )

        bot.send_message(call.message.chat.id, "Введите новое время в формате чч:мм")
        bot.register_next_step_handler(call.message, get_time, True, int(call.data[6:]))
    elif call.data[:2] == "my":
        keyboard = types.InlineKeyboardMarkup()
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=keyboard,
        )

        notif = find_notif(call.data[2:])
        if notif is None:
            bot.send_message(
                call.message.chat.id, "Ой упс ахааха, что-то пошло не так :("
            )
            main_menu(call.message.chat.id)
            return

        if notif.time_interval % (60 * 60 * 24) == 0:
            repeat = "дней"
            time = notif.time_interval // (60 * 60 * 24)
        else:
            repeat = "часов"
            time = notif.time_interval // (60 * 60)

        format1 = "%d.%m.%Y"
        format2 = "%H:%M"
        bot.send_message(
            call.message.chat.id,
            f"Ближайшее сообщение придёт "
            f"{datetime.fromtimestamp(notif.time).strftime(format1)} в "
            f"{datetime.fromtimestamp(notif.time).strftime(format2)}\n\n"
            f"Количество {repeat} через которые бот будет слать сообщения:\n"
            f"{time}\n\n"
            f"Текст сообщения:\n{notif.body}",
        )


def get_user_interval(message, time, date, time_type, change, prev_notif_numb):
    try:
        time_interval = int(message.text)
        if time_type == "Раз в несколько дней":
            assert 0 < time_interval <= 31  # максимальный интервал - месяц
        elif time_type == "Раз в несколько часов":
            assert 0 < time_interval <= 24 * 31
    except TypeError:
        bot.send_message(
            message.from_user.id,
            "Интервал должен быть целым положительным числом!\n" "Попробуйте ещё раз.",
        )
        bot.register_next_step_handler(
            message, get_user_interval, time, date, time_type, change, prev_notif_numb
        )
        return
    except ValueError:
        bot.send_message(
            message.from_user.id,
            "А где текст?? Нам нужен текст :(\n"
            "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(
            message, get_user_interval, time, date, time_type, change, prev_notif_numb
        )
        return
    except AssertionError:
        bot.send_message(
            message.from_user.id,
            "Интервал либо слишком большой, либо слишком маленький :(\n"
            "Попробуй ещё раз.",
        )
        bot.register_next_step_handler(
            message, get_user_interval, time, date, time_type, change, prev_notif_numb
        )
        return

    if time_type == "Раз в несколько дней":
        time_interval *= 60 * 60 * 24
    elif time_type == "Раз в несколько часов":
        time_interval *= 60 * 60

    if not change:
        bot.send_message(message.from_user.id, "Какое сообщение должен присылать бот?")
    else:
        bot.send_message(
            message.from_user.id, "Какое новое сообщение должен присылать бот?"
        )

    bot.register_next_step_handler(
        message, get_body, time, date, time_interval, change, prev_notif_numb
    )


bot.polling(none_stop=True, interval=0)
