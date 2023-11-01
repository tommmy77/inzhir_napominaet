#!/usr/bin/env python3
from flask import Flask, request
from flask_restful import Resource, Api
from marshmallow import Schema, fields
from datetime import datetime
from ast import literal_eval
import time
import requests
import psycopg2

app = Flask(__name__)
api = Api(app)

bot_token = ''
user_id_to_name = {"471115888": "имя1", "284798792": "имя2"}

dankhaiaa_id = '471115888'
alex_id = '284798792'
# default_chat_id = '-4029358124'


def user_name(user_id):
    return user_id_to_name[user_id]


def utc_unix():
    utc_unix_millis = round(round(time.time(), 3) * 1000)
    return utc_unix_millis


def utc_date_time():
    utc_datetime = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    utc_date = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d')
    return [utc_datetime, utc_date]


def time_diff(start, finish):
    took_time = round((finish - start) / 1000)
    return took_time


def parse_message(update):
    bot_cmds = [
        '/new_task@inzhir_napominaet_bot',
        '/resolve_task@inzhir_napominaet_bot',
        '/show_tasks@inzhir_napominaet_bot',
        '/new_task',
        '/resolve_task',
        '/show_tasks'
    ]
    # expected_msg_type_list = ['bot_command', 'text', 'inline_keyboard_reply']
    try:  # filtering edited message updates
        if update['edited_message']:
            return False
    except KeyError:
        pass

    try:  # parsing inline keyboard interaction
        update = update['callback_query']
        msg_type = 'inline_keyboard_input'
        user_id = str(update['from']['id'])
        chat_id = str(update['message']['chat']['id'])
        text = ''
        callback_data = update['data']

    except KeyError:  # parsing text message
        user_id = str(update['message']['from']['id'])
        chat_id = str(update['message']['chat']['id'])
        callback_data = ''
        try:
            text = update['message']['text']
            if text in bot_cmds:
                msg_type = 'bot_command'
            else:
                msg_type = 'text'
        except KeyError:
            return False

    return [msg_type, user_id, chat_id, text, callback_data]


def sql_execute(query):
    conn = psycopg2.connect(dbname="inzhir", user="postgres")
    cursor = conn.cursor()
    conn.autocommit = True
    cursor.execute(query)
    try:
        query_output = cursor.fetchall()
    except psycopg2.ProgrammingError:
        query_output = []
    conn.close()

    if len(query_output) != 0:
        return query_output
    else:
        return []


def user_status(user_id):
    query = "SELECT status FROM user_status WHERE user_id = '%s'" % (user_id,)
    return sql_execute(query)[0][0]


def new_task(chat_id, task_text, added_by):
    task_id = utc_unix()
    # task_id bigint, task varchar, added_by varchar, owner varchar, priority varchar, status varchar, finished_at_unix bigint
    query = "INSERT INTO tasks VALUES (%s, '%s', '%s', '%s', '1', 'open', 0)" % (task_id, task_text, user_name(added_by), user_name(added_by))
    print(query)
    sql_execute(query)
    ask_priority_and_owner(chat_id, task_id)


def ask_priority_and_owner(chat_id, task_id):
    priority_0 = "priority::%s::0" % (task_id,)
    priority_1 = "priority::%s::1" % (task_id,)
    priority_2 = "priority::%s::2" % (task_id,)
    owner_dankhaiaa = "owner::%s::471115888" % (task_id,)
    owner_alex = "owner::%s::284798792" % (task_id,)
    priority_owner_keyboard = [
        [
            {"text": "Низкий", "callback_data": priority_0},
            {"text": "Средний", "callback_data": priority_1},
            {"text": "Высокий", "callback_data": priority_2}
        ],
        [
            {"text": "Данхаяа", "callback_data": owner_dankhaiaa},
            {"text": "Саша", "callback_data": owner_alex}
        ]
    ]

    send_message(chat_id, "Все записал. Теперь укажи: какой приоритет у этой задачи и кто ей займется?", priority_owner_keyboard)


def update_task_priority(task_id, new_priority, chat_id):
    query = "UPDATE tasks SET priority = '%s' WHERE task_id = %s" % (new_priority, task_id)
    print(query)
    sql_execute(query)
    send_message(chat_id, "Поменял приоритет.")


def update_task_owner(task_id, new_owner, chat_id):
    query = "UPDATE tasks SET owner = '%s' WHERE task_id = %s" % (new_owner, task_id)
    print(query)
    sql_execute(query)
    send_message(chat_id, "Поменял владельца задачи.")


def change_user_status(user_id, new_status):
    query = "UPDATE user_status SET status = %s WHERE user_id = '%s'" % (new_status, user_id)
    sql_execute(query)


def resolve_task(task_id, chat_id):
    query = "UPDATE tasks SET status = 'resolved' WHERE task_id = %s" % (task_id,)
    sql_execute(query)
    send_message(chat_id, "Отметил, так держать!")


def update_finish_time(task_id):
    query = "UPDATE tasks SET finished_at_unix = %s WHERE task_id = %s" % (utc_unix(), task_id)
    sql_execute(query)


def send_message(chat_id, text, keyboard='none', markdown=True):
    if markdown:
        if keyboard == "none":
            reply_json = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        else:
            reply_json = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": keyboard}}
    else:
        reply_json = {"chat_id": chat_id, "text": text}
    print(reply_json)
    send_m = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=reply_json)
    print(send_m.status_code)
    print(send_m.text)


def get_tasks_old():
    # tasks with high priority (priority='2')
    query = """SELECT owner, task FROM tasks WHERE status = 'open' AND priority = '2' ORDER BY task_id, owner"""
    high_tasks = sql_execute(query)
    high_tasks_list = ''
    if len(high_tasks) != 0:
        for i in range(len(high_tasks)):
            task_row = '*%s - %s:* %s\n\n' % (str(i+1), high_tasks[i][0], high_tasks[i][1])
            high_tasks_list = high_tasks_list + task_row
    else:
        high_tasks_list = 'Тут пока пусто :)\n\n'

    # tasks with medium priority (priority='1')
    query = """SELECT owner, task FROM tasks WHERE status = 'open' AND priority = '1' ORDER BY task_id, owner"""
    medium_tasks = sql_execute(query)
    medium_tasks_list = ''
    if len(medium_tasks) != 0:
        for i in range(len(medium_tasks)):
            task_row = '*%s - %s:* %s\n\n' % (str(i+1), medium_tasks[i][0], medium_tasks[i][1])
            medium_tasks_list = medium_tasks_list + task_row
    else:
        medium_tasks_list = 'Тут пока пусто :)\n\n'

    # tasks with low priority (priority='0')
    query = """SELECT owner, task FROM tasks WHERE status = 'open' AND priority = '0' ORDER BY task_id, owner"""
    low_tasks = sql_execute(query)
    low_tasks_list = ''
    if len(low_tasks) != 0:
        for i in range(len(low_tasks)):
            task_row = '*%s - %s:* %s\n\n' % (str(i + 1), low_tasks[i][0], low_tasks[i][1])
            low_tasks_list = low_tasks_list + task_row
    else:
        low_tasks_list = 'Тут пока пусто :)\n\n'

    tasks_payload = '\n``` Задачи с высоким приоритетом:```\n' \
                    + high_tasks_list + '``` Задачи со средним приоритетом:```\n' \
                    + medium_tasks_list + '``` Задачи с низким приоритетом:```\n' + low_tasks_list

    return tasks_payload


def get_tasks():
    # tasks for Dankhaiaa
    query = """SELECT task, priority, status FROM tasks 
               WHERE owner = 'Данхаяа'
               AND (status = 'open' 
               OR (status = 'resolved' AND extract(epoch from now())::integer - finished_at_unix < 432000))
               ORDER BY status ASC, priority DESC, task_id ASC"""
    dankhaiaa_tasks = sql_execute(query)
    dankhaiaa_tasks_list = ''
    if len(dankhaiaa_tasks) != 0:
        for i in range(len(dankhaiaa_tasks)):
            if dankhaiaa_tasks[i][2] == 'resolved':
                task_row = '*✔️ %s.* %s\n\n' % (str(i + 1), dankhaiaa_tasks[i][0])
            elif dankhaiaa_tasks[i][1] == '2':
                task_row = '*⚠️ %s.* %s\n\n' % (str(i + 1), dankhaiaa_tasks[i][0])
            elif dankhaiaa_tasks[i][1] == '1':
                task_row = '🐈 *%s.* %s\n\n' % (str(i + 1), dankhaiaa_tasks[i][0])
            else:
                task_row = '🐌 *%s.* %s\n\n' % (str(i + 1), dankhaiaa_tasks[i][0])

            dankhaiaa_tasks_list = dankhaiaa_tasks_list + task_row
    else:
        dankhaiaa_tasks_list = 'Тут пока пусто, отличная работа :)\n\n'

    # tasks for Alex
    query = """SELECT task, priority, status FROM tasks 
               WHERE owner = 'Саша'
               AND (status = 'open' 
               OR (status = 'resolved' AND extract(epoch from now())::integer - finished_at_unix < 432000))
               ORDER BY status ASC, priority DESC, task_id ASC"""
    alex_tasks = sql_execute(query)
    alex_tasks_list = ''
    if len(alex_tasks) != 0:
        for i in range(len(alex_tasks)):
            if alex_tasks[i][2] == 'resolved':
                task_row = '*✔️ %s.* %s\n\n' % (str(i + 1), alex_tasks[i][0])
            elif alex_tasks[i][1] == '2':
                task_row = '*⚠️ %s.* %s\n\n' % (str(i + 1), alex_tasks[i][0])
            elif alex_tasks[i][1] == '1':
                task_row = '🐈 *%s.* %s\n\n' % (str(i + 1), alex_tasks[i][0])
            else:
                task_row = '🐌 *%s.* %s\n\n' % (str(i + 1), alex_tasks[i][0])

            alex_tasks_list = alex_tasks_list + task_row
    else:
        alex_tasks_list = 'Тут пока пусто, отличная работа :)\n\n'

    tasks_payload = '*ДАНХАЯА:*\n' + dankhaiaa_tasks_list + '*САША:*\n' + alex_tasks_list

    return tasks_payload


def get_tasks_to_resolve():
    # tasks with high priority (priority='2')
    query = """SELECT owner, task, task_id FROM tasks WHERE status = 'open' ORDER BY owner, task_id"""
    tasks = sql_execute(query)
    tasks_list = ''
    resolve_keyboard = '[['

    if len(tasks) != 0:
        for i in range(len(tasks)):
            task_row = '*%s - %s:* %s\n\n' % (str(i + 1), tasks[i][0], tasks[i][1])
            tasks_list = tasks_list + task_row
            # form keyboard
            block = '{"text": "%s", "callback_data": "resolve::%s::resolved"}' % (str(i + 1), tasks[i][2])
            resolve_keyboard = resolve_keyboard + block
            if i != len(tasks):
                if (i+1) % 5 == 0:
                    resolve_keyboard = resolve_keyboard + '],['
                else:
                    resolve_keyboard = resolve_keyboard + ','
        resolve_keyboard = resolve_keyboard + ']]'
        return tasks_list, resolve_keyboard
    else:
        return False


class TgEndpointSchema(Schema):
    text = fields.Str(required=False)


job_status_schema = TgEndpointSchema()


# noinspection PyMethodMayBeStatic
class TgEndpoint(Resource):
    def get(self):
        incoming_data = request.args
        if incoming_data:
            print(incoming_data)
        return {'status': 'ok', 'data': incoming_data}, 200  # return 200 OK code

    def post(self):
        incoming_data = request.get_json()
        if parse_message(incoming_data):
            print(incoming_data)
            print(parse_message(incoming_data))
            msg_type, user_id, chat_id, text, callback_data = parse_message(incoming_data)
            print(user_status(user_id))
            print("---------------------------")
            if msg_type == 'bot_command':
                if '/new_task' in text:
                    change_user_status(user_id, '1')
                    send_message(chat_id, "Слушаю, следующее сообщение запишу как задачу.")
                elif '/show_tasks' in text:
                    send_message(chat_id, get_tasks())
                elif '/resolve_task' in text:
                    if get_tasks_to_resolve():
                        task_list, resolve_keyboard = get_tasks_to_resolve()
                        send_message(chat_id, task_list, literal_eval(resolve_keyboard))
                else:
                    send_message(chat_id, "Что-то сломалось :(")

            elif msg_type == 'text':
                if user_status(user_id) == 1:
                    print("task found")
                    new_task(chat_id, text, user_id)
                    change_user_status(user_id, '0')

            elif msg_type == 'inline_keyboard_input':
                input_type, input_task_id, input_value = callback_data.split("::")
                print(callback_data)
                print(input_type)
                print(input_task_id)
                print(input_value)
                if input_type == 'priority':
                    update_task_priority(input_task_id, input_value, chat_id)
                elif input_type == 'owner':
                    update_task_owner(input_task_id, user_name(input_value), chat_id)
                elif input_type == 'resolve':
                    resolve_task(input_task_id, chat_id)
                    update_finish_time(input_task_id)
                else:
                    pass

        return {'status': 'ok', 'data': incoming_data}, 200
    pass


api.add_resource(TgEndpoint, '/', methods=['POST', 'GET'])  # /new_job is the endpoint to add new job to the queue

if __name__ == '__main__':
    app.run(host='localhost', port=9500)  # run the service
