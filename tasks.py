from asyncio import tasks
import json
from os import path
import sys
from tkinter import E
import emoji

TODO_STATE_SYMBOL = ':eight_o’clock:'
IN_PROGRESS_STATE_SYMBOL = ':wrench:'
DONE_STATE_SYMBOL = ':check_mark:'

TREE_TASK_TYPE_SYMBOL = ':deciduous_tree:'
LEAF_TASK_TYPE_SYMBOL = ':fallen_leaf:'


def print_err(err):
    print(err, file=sys.stderr)

def init_tasks():
    save_tasks({'root': {'_state': 'todo'}})

def load_tasks():
    with open('.tasks.json', 'r', encoding='utf-8') as tasks_file:
        tasks = json.loads(tasks_file.read())
    return tasks

def save_tasks(tasks):
    with open('.tasks.json', 'w', encoding='utf-8') as tasks_file:
        tasks_file.write(json.dumps(tasks))

def task_is_property(task):
    return task == '_state' or task == '_descr'

def print_subtasks(tasks):
    for task in tasks.keys():
        if task_is_property(task):
            continue

        if tasks[task]['_state'] == 'todo':
            emoji_symbol = TODO_STATE_SYMBOL
        elif tasks[task]['_state'] == 'progr':
            emoji_symbol = IN_PROGRESS_STATE_SYMBOL
        elif tasks[task]['_state'] == 'done':
            emoji_symbol = DONE_STATE_SYMBOL
        
        size = tasks_len(tasks[task])

        if size > 0:
            task_type = TREE_TASK_TYPE_SYMBOL
        else:
            task_type = LEAF_TASK_TYPE_SYMBOL

        num = num_by_name(task, tasks)

        print(emoji.emojize(f'#{num} {emoji_symbol} {task_type} ({size}) {task}'))

def text_from(params):
    return ' '.join(params)

def has_subtasks(tasks):
    tasks_inside = [task for task in tasks.keys() if not task_is_property(task)]
    return bool(tasks_inside)

def tasks_len(tasks):
    return len([task for task in tasks.keys() if not task_is_property(task)])

def can_done(tasks):
    return not has_subtasks(tasks)

def complete_state(tasks):
    state = 'done'
    if has_subtasks(tasks):
        for task in tasks.keys():
            if task_is_property(task):
                continue
            if tasks[task]['_state'] == 'progr':
                state = 'progr'
            elif tasks[task]['_state'] == 'todo' and state != 'progr':
                state = 'todo'
    return state

def change_parent_stack_state(history):
    for tasks in history[::-1]:
        proper_state = complete_state(tasks)
        if tasks['_state'] != proper_state:
            tasks['_state'] = proper_state
        else:
            break

def recursive_reset(tasks):
    tasks['_state'] = 'todo'
    for task in tasks.keys():
        if not task_is_property(task):
            recursive_reset(tasks[task])

def name_by_num(num, tasks):
    curr = 0
    for task in tasks.keys():
        if not task_is_property(task):
            if curr == num:
                return task
            curr += 1
    return None

def num_by_name(name, tasks):
    curr = 0
    for task in tasks.keys():
        if not task_is_property(task):
            if task == name:
                return curr
            curr += 1
    return curr

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'init':
        init_tasks()
    if not path.isfile('.tasks.json'):
        print_err("Cannot find .tasks.json file!")
        exit(1)
    tasks = load_tasks()
    history = [tasks['root']]
    history_names = ['root']
    current = tasks['root']
    while True:
        current_path = '/'.join(history_names)
        cmd, *params = input(f'{current_path}> ').split(' ')
        num_or_name = text_from(params)
        name = name_by_num(int(num_or_name), current) if num_or_name.isnumeric() else None
        if name is None and num_or_name != '' and cmd != 'new':
            print(f"Cannot find subtask number {num_or_name}")
        if num_or_name == '_state' and cmd != 'exit':
            print_err('Name cannot be _state!')
            continue

        if cmd == 'exit':
            exit(0)
        elif cmd == 'see':
            to_print = current[name] if name is not None else current
            print_subtasks(to_print)
        elif cmd == 'in':
            if name is not None:
                current = current[name]
                history_names.append(name)
                history.append(current)
            else:
                print_err(f"{num_or_name} number doesn't exist!")
        elif cmd == 'out':
            if current_path != 'root':
                history.pop()
                current = history[-1]
                history_names.pop()
            else:
                print_err(f"Cannot out of root!")
        elif cmd == 'new':
            if num_or_name not in current:
                current[num_or_name] = {
                    '_state': 'todo'
                }
                change_parent_stack_state(history)
                save_tasks(tasks)
            else:
                print_err(f'{num_or_name} already exists!')
        elif cmd == 'progr' or cmd == 'done':
            if name is None:
                print_err(f'{num_or_name} does not exist!')
            elif not can_done(current[name]):
                print_err(f'Cannot change state of {num_or_name} because it has subtasks!')
            else:
                current[name]['_state'] = cmd
                change_parent_stack_state(history)
                save_tasks(tasks)
        elif cmd == 'rm':
            if name is not None:
                current.pop(name, None)
                save_tasks(tasks)
            else:
                print_err(f'{num_or_name} does not exist!')
        elif cmd == 'reset':
            to_reset = current[name] if name is not None else current
            is_user_sure = input('Are you sure that you want to reset (Y/N)? ')
            if is_user_sure.lower() == 'y':
                recursive_reset(to_reset)
                change_parent_stack_state(history)
                save_tasks(tasks)
        elif cmd == 'descr':
            to_descr = current[name] if name is not None else current
            describtion = ''
            line = ''
            while line != 'END':
                line = input('# ')
                if line != 'END':
                    describtion += f'{line}\n'
            to_descr['_descr'] = describtion
            save_tasks(tasks)
        elif cmd == 'info':
            to_info = current[name] if name is not None else current
            if '_descr' in to_info:
                print(to_info['_descr'])
        else:
            print(emoji.emojize('Author: Igor Santarek :Poland:'))
            print('\nAvailable commands:')
            print('exit - Exit program')
            print('see [num] - List subtasks')
            print('in num - Make subtask current task')
            print('out - Make parent current task')
            print('new name - Create new task')
            print(emoji.emojize(f'progr num - Set task state to IN PROGRESS {IN_PROGRESS_STATE_SYMBOL}'))
            print(emoji.emojize(f'done num - Set task state to DONE {DONE_STATE_SYMBOL}'))
            print(emoji.emojize(f'reset num - Reset task and its children state to TODO {TODO_STATE_SYMBOL}'))
            print('rm num - Remove task')
            print('descr [num] - Write description for task')
            print('info [num] - Read description for task\n')

            print('[num] - optional with braces. Without the number is required.')
