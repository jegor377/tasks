import os
import json
import sys
import readline
import time
import emoji
import sys, tempfile
from subprocess import call
import datetime
import atexit


TODO_STATE = 'todo'
IN_PROGRESS_STATE = 'progr'
DONE_STATE = 'done'


TODO_STATE_SYMBOL = ':eight_o’clock:'
IN_PROGRESS_STATE_SYMBOL = ':wrench:'
DONE_STATE_SYMBOL = ':check_mark:'

TASKS_DIR = '.tasks'
EDITOR = os.environ.get('EDITOR', 'vim')


commands = {}


def command(name, params, describtion):
    def command_decorator(fnc):
        if params is not None:
            params_text = ' '.join(params) if isinstance(params, list) else params
            help_msg = f'{name} {params_text} - {describtion}'
        else:
            help_msg = f'{name} - {describtion}'
        commands[name] = {
            'help_msg': emoji.emojize(help_msg),
            'fnc': fnc
        }
        return fnc
    return command_decorator


def is_initialized():
    return os.path.isdir(TASKS_DIR)


def perror(err):
    print(err, file=sys.stderr)


def err_die(err):
    perror(err)
    exit(1)


def get_task_path(task_id):
    return os.path.join(TASKS_DIR, f'{task_id}.json')


def get_all_tasks():
    return [int(task_id.split('.')[0]) for task_id in os.listdir(TASKS_DIR)]


def read_task(task_id):
    with open(get_task_path(task_id), 'r', encoding='utf-8') as file:
        return json.loads(file.read())


def write_task(task_id, task):
    with open(get_task_path(task_id), 'w', encoding='utf-8') as file:
        file.write(json.dumps(task))


def task_exists(task_id):
    return os.path.isfile(get_task_path(task_id))


def empty_task(name):
    return {
        'name': name,
        'state': TODO_STATE,
        'tasks': []
    }

def init():
    os.mkdir(TASKS_DIR)
    write_task(0, empty_task('root'))


def init_config(config):
    config['current'] = read_task(0)
    config['history'] = [0]
    config['name_history'] = ['root']


def available_id():
    ids = [int(os.path.basename(id_name).split('.')[0]) for id_name in os.listdir(TASKS_DIR)]
    ids.sort()
    for new_id in range(max(ids) + 2):
        if new_id not in ids:
            return new_id


def is_task_id(params):
    return len(params) == 1 and params[0].isnumeric()


def task_state_symbol(state) :
    if state == TODO_STATE:
        return TODO_STATE_SYMBOL
    elif state == IN_PROGRESS_STATE:
        return IN_PROGRESS_STATE_SYMBOL
    elif state == DONE_STATE:
        return DONE_STATE_SYMBOL


def current(config):
    return config['history'][-1]


def id_from(params):
    return int(params[0])


@command('exit', None, 'Exit program')
def exit_cmd(params, config):
    exit(0)


@command('see', '[id]', 'List subtasks')
def see(params, config):
    task_id = current(config)
    if params:
        if is_task_id(params):
            task_id = id_from(params)
        else:
            perror('Id parameter is wrong!')
            return

    if task_exists(task_id):
        task = read_task(task_id)

        for subtask_id in task['tasks']:
            subtask = read_task(subtask_id)
            print_task(subtask_id, subtask)
    else:
        perror(f'Task {task_id} does not exist!')


def print_task(task_id, task):
    state_symbol = task_state_symbol(task['state'])
    task_count = len(task['tasks'])
    name = task['name']
    print(emoji.emojize(f'#{task_id} {state_symbol} ({task_count}) {name}'))


def get_id_error_msg(params, config) :
    if not params:
        return 'Missing task id parameter!'
    if not is_task_id(params):
        return 'Id parameter is wrong!'
    task_id = id_from(params)
    if not task_exists(task_id):
        return f'Task {task_id} does not exist!'
    if task_id not in config['current']['tasks']:
        return f'Task {task_id} is not a child of current task!'
    return None


@command('in', 'id', 'Make subtask current task')
def go_in(params, config, print_see=True):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    
    task = read_task(task_id)
    config['current'] = task
    config['history'].append(task_id)
    config['name_history'].append(task['name'])
    if print_see:
        see([], config)


@command('out', None, 'Make parent current task')
def go_out(params, config, print_see=True):
    if len(config['history']) > 1:
        config['history'].pop()
        config['name_history'].pop()
        config['current'] = read_task(current(config))
    else:
        perror('Cannot out of root task!')
    if print_see:
        see([], config)


@command('new', 'name', 'Create new task')
def new_task(params, config):
    if not params:
        perror('Missing name parameter!')
        return

    task_id = available_id()
    task = empty_task(' '.join(params))
    config['current']['tasks'].append(task_id)
    write_task(task_id, task)
    write_task(current(config), config['current'])
    start_state_propagation(config)
    see([], config)


@command('rm', 'id', 'Remove task')
def rm_task(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    if task_id == 0:
        perror('Cannot remove root task!')
        return
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    
    is_sure = input('Are you sure (Y/N)? ')
    if is_sure.lower() == 'y':
        rm_subtask(task_id, current(config))
        config['current']['tasks'].remove(task_id)
    see([], config)


def rm_subtask(subtask_id, parent_id):
    subtask = read_task(subtask_id)

    for subsubtask_id in subtask['tasks']:
        rm_subtask(subsubtask_id, subtask_id)
    
    parent = read_task(parent_id)
    parent['tasks'].remove(subtask_id)
    write_task(parent_id, parent)

    os.remove(get_task_path(subtask_id))


def set_task_state(task_id, state, config):
    task = read_task(task_id)

    if task['tasks']:
        perror(f'Cannot change state of task with subtasks!')
        return

    task['state'] = state
    write_task(task_id, task)
    start_state_propagation(config)


def start_state_propagation(config):
    propagate_state(len(config['history']) - 1, config)


def propagate_state(history_id, config):
    if history_id >= 0:
        task_id = config['history'][history_id]
        curr_state = DONE_STATE
        task = read_task(task_id)
        for subtask_id in task['tasks']:
            subtask = read_task(subtask_id)
            if subtask['state'] == IN_PROGRESS_STATE:
                curr_state = IN_PROGRESS_STATE
            elif subtask['state'] == TODO_STATE and curr_state != IN_PROGRESS_STATE:
                curr_state = TODO_STATE
            elif subtask['state'] == DONE_STATE and curr_state != DONE_STATE:
                curr_state = IN_PROGRESS_STATE
        task['state'] = curr_state
        write_task(task_id, task)
        propagate_state(history_id - 1, config)


@command('progr', 'id', f'Set task state to IN PROGRESS {IN_PROGRESS_STATE_SYMBOL}')
def set_in_progr(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    
    set_task_state(task_id, IN_PROGRESS_STATE, config)
    see([], config)


@command('done', 'id', f'Set task state to DONE {DONE_STATE_SYMBOL}')
def set_done(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    
    set_task_state(task_id, DONE_STATE, config)
    see([], config)


@command('reset', 'id', f'Reset task and its children state to TODO {TODO_STATE_SYMBOL}')
def reset(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return

    is_sure = input('Are you sure (Y/N)? ')
    if is_sure.lower() == 'y':
        reset_task(task_id)
        start_state_propagation(config)
    see([], config)


def reset_task(task_id):
    task = read_task(task_id)
    for subtask_id in task['tasks']:
        reset_task(subtask_id)
    task['state'] = TODO_STATE
    write_task(task_id, task)


@command('descr', '[id]', 'Write description for task')
def descr(params, config):
    task_id = current(config)
    if params:
        if is_task_id(params):
            task_id = id_from(params)
        else:
            perror('Id parameter is wrong!')
            return
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    task = read_task(task_id)
    with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
        tf.write(task['descr'].encode('utf-8') if 'descr' in task else b'')
        tf.flush()
        call([EDITOR, tf.name])
        tf.seek(0)
        describtion = tf.read().decode('utf-8')
        if describtion == '':
            task.pop('descr', None)
        else:
            task['descr'] = describtion
        write_task(task_id, task)


@command('info', '[id]', 'Read description for task')
def info(params, config):
    task_id = current(config)
    if params:
        if is_task_id(params):
            task_id = id_from(params)
        else:
            perror('Id parameter is wrong!')
            return
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    task = read_task(task_id)
    print_info(task)


def print_info(task, divider=None):
    if 'descr' in task:
        if divider is not None:
            print(divider)
        print(emoji.emojize(task['descr']))


@command('pull', 'id', 'Pulls task from this task to outer task')
def pull(params, config):
    curr = current(config)
    if curr == 0:
        perror("Cannot pull from root task!")
        return

    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)

    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    
    parent = config['current']

    grand_parent_id = config['history'][-2]
    grand_parent = read_task(config['history'][-2])

    parent['tasks'].remove(task_id)
    grand_parent['tasks'].append(task_id)

    write_task(curr, parent)
    write_task(grand_parent_id, grand_parent)

    start_state_propagation(config)
    see([], config)


def are_params_ids(params):
    for param in params:
        if not param.isnumeric():
            return False
    return True


@command('push', ['id1', 'id2'], 'Pushes task with id1 from current task to task with id2')
def push(params, config):
    if len(params) != 2:
        perror('Wrong number of parameters!')
        return
    if not are_params_ids(params):
        perror('Params are not ids!')
        return

    task1_id = int(params[0])
    task2_id = int(params[1])

    if task1_id not in config['current']['tasks']:
        perror(f'Task {task1_id} is not a child of current task!')
        return
    if task2_id not in config['current']['tasks']:
        perror(f'Task {task2_id} is not a child of current task!')
        return
    if not task_exists(task1_id):
        perror(f'Task {task1_id} does not exist!')
        return
    if not task_exists(task2_id):
        perror(f'Task {task2_id} does not exist!')
        return

    config['current']['tasks'].remove(task1_id)

    dest = read_task(task2_id)
    dest['tasks'].append(task1_id)

    write_task(current(config), config['current'])
    write_task(task2_id, dest)

    go_in([str(task2_id)], config, False)
    start_state_propagation(config)
    go_out(params, config, False)
    see([], config)


@command('todo', None, f'Print first task todo ({TODO_STATE_SYMBOL} or {IN_PROGRESS_STATE_SYMBOL} state)')
def todo(params, config):
    todo_id = -1
    id_history = [0]
    history = [read_task(0)]
    names_history = ['root']
    while history:
        task = history.pop()
        if not task['tasks']:
            if task['state'] != DONE_STATE:
                todo_id = id_history[-1]
            break
        for subtask_id in task['tasks']:
            subtask = read_task(subtask_id)
            if subtask['state'] == TODO_STATE or subtask['state'] == IN_PROGRESS_STATE:
                id_history.append(subtask_id)
                history.append(subtask)
                names_history.append(subtask['name'])
                break
    
    if todo_id != -1:
        todo_path = '/'.join([name for name in names_history])
        id_path = ' '.join([str(id) for id in id_history])
        todo_task = read_task(todo_id)
        print(todo_path)
        print(f'ids path: {id_path}')
        print_info(todo_task, '---')
    else:
        print(emoji.emojize('There is no task todo... :grinning_face:'))


@command('edit', 'id', 'Edit task name')
def edit(params, config):
    if not params:
        perror('Missing id and new name parameters!')
        return
    if len(params) == 1:
        perror('Missing new name parameter!')
        return
    if not params[0].isnumeric():
        perror(f'{params[0]} is not and id!')
        return
    task_id = int(params[0])
    if not task_exists(task_id):
        perror(f'Task {task_id} does not exist!')
        return
    if task_id not in config['current']['tasks']:
        perror(f'Task {task_id} is not a child of current task!')
        return
    task = read_task(task_id)
    task['name'] = ' '.join(params[1:])
    write_task(task_id, task)
    see([], config)


@command('up', 'id', 'Move task up :up_arrow:')
def move_up(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)

    curr_index = config['current']['tasks'].index(task_id)
    new_index = max(0, curr_index - 1)

    config['current']['tasks'][curr_index], config['current']['tasks'][new_index] = config['current']['tasks'][new_index], config['current']['tasks'][curr_index]
    write_task(current(config), config['current'])
    see([], config)


@command('down', 'id', 'Move task down :down_arrow:')
def move_down(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)

    curr_index = config['current']['tasks'].index(task_id)
    new_index = min(len(config['current']['tasks']) - 1, curr_index + 1)

    config['current']['tasks'][curr_index], config['current']['tasks'][new_index] = config['current']['tasks'][new_index], config['current']['tasks'][curr_index]
    write_task(current(config), config['current'])
    see([], config)


@command('froot', ['[id1]', '[id2]', '[id3]', '...'], 'The same as `in` but you can specify whole path')
def from_root(params, config):
    init_config(config)
    if are_params_ids(params):
        for id in params:
            task_id = int(id)
            if task_id == 0:
                continue
            if not task_exists(task_id):
                perror(f'Task {task_id} does not exist!')
                return
            if task_id not in config['current']['tasks']:
                perror(f'Task {task_id} is not a child of current task!')
                return
            task = read_task(task_id)
            config['current'] = task
            config['history'].append(task_id)
            config['name_history'].append(task['name'])
    else:
        perror('Params are not ids!')
    see([], config)


def is_float(str):
    try:
        float(str)
        return True
    except ValueError:
        return False


@command('eval', ['[id]', 'cost'], 'Lets you evaluate cost of a task')
def eval_cost(params, config):
    if not params:
        perror('Missing id and cost parameters!')
        return
    if len(params) == 1:
        if current(config) == 0:
            perror('Cannot evaluate cost of root task!')
            return
        if not is_float(params[0]):
            perror(f'Parameter {params[0]} is not a floating point number!')
            return
        cost = float(params[0])
        if cost == 0:
            config['current'].pop('time_cost', None)
        else:
            config['current']['time_cost'] = cost
        write_task(current(config), config['current'])
    elif len(params) == 2:
        if not params[0].isnumeric():
            perror(f'Parameter {params[0]} is not an id!')
            return
        task_id = int(params[0])
        if not task_exists(task_id):
            perror(f'Task {task_id} does not exist!')
            return
        if task_id not in config['current']['tasks']:
            perror(f'Task {task_id} is not a child of current task!')
            return
        if not is_float(params[1]):
            perror(f'Parameter {params[1]} is not a floating point number!')
            return
        task = read_task(task_id)
        cost = float(params[1])
        if cost == 0:
            task.pop('time_cost', None)
        else:
            task['time_cost'] = cost
        write_task(task_id, task)
    else:
        perror('Wrong number of parameters!')
        return


@command('cost', '[id]', 'Lets you see cumulative cost of a task')
def see_cost(params, config):
    if not params:
        task = config['current']
    else:
        error_msg = get_id_error_msg(params, config)
        if error_msg is not None:
            perror(error_msg)
            return
        task_id = id_from(params)
        task = read_task(task_id)
    print('Time cost:', sum_cost(task))


def sum_cost(task):
    sum = 0
    if 'time_cost' in task and not task['tasks']:
        sum = task['time_cost']
    for subtask_id in task['tasks']:
        subtask = read_task(subtask_id)
        sum += sum_cost(subtask)
    return sum


@command('sort', None, 'Prints tasks sorted in order in the tree')
def sort_tasks(params, config, task_id = 0, history = []):
    task = read_task(task_id)
    if not task['tasks'] and task['state'] in [TODO_STATE, IN_PROGRESS_STATE]:
        tmp = task['name']
        task['name'] = '/'.join(history) + f'/{tmp}'
        print_task(task_id, task)
        task['name'] = tmp
    for subtask_id in task['tasks']:
        sort_tasks(params, config, subtask_id, history + [task['name']])


@command('bwork', 'id', 'Begins to record working time')
def begin_work(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    task = read_task(task_id)
    if task['tasks']:
        perror('Cannot to begin recording working time on task that has subtasks!')
        return
    if 'work_time_start' in task:
        task['worked_time'] = task.get('worked_time', 0) + get_last_work_time(task)
    task['work_time_start'] = datetime.datetime.now().isoformat()
    write_task(task_id, task)


@command('ework', 'id', 'Ends recording working time')
def end_work(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    task = read_task(task_id)
    if task['tasks']:
        perror('Cannot to end recording working time on task that has subtasks!')
        return
    end_work_task(task)
    write_task(task_id, task)


def end_work_task(task):
    task['worked_time'] = task.get('worked_time', 0) + get_last_work_time(task)
    task.pop('work_time_start', None)


def get_last_work_time(task):
    now = datetime.datetime.now()
    if 'work_time_start' in task:
        then = datetime.datetime.fromisoformat(task['work_time_start'])
        return (now - then).total_seconds()
    return 0


def end_work_in_all_tasks():
    for task_id in get_all_tasks():
        task = read_task(task_id)
        if not task['tasks']:
            end_work_task(task)
            write_task(task_id, task)


@command('wtime', '[id]', 'See time spent in working on task')
def working_time(params, config):
    if params:
        error_msg = get_id_error_msg(params, config)
        if error_msg is not None:
            perror(error_msg)
            return
        task_id = id_from(params)
        task = read_task(task_id)
    else:
        task_id = current(config)
        task = config['current']
    if not task['tasks']:
        working_time_val = task.get('worked_time', 0) + get_last_work_time(task)
    else:
        working_time_val = sum_working_time(task_id)
    formatted_time = time.strftime('%H:%M:%S', time.gmtime(working_time_val))
    print(f'Time spent working: {formatted_time}')


def sum_working_time(task_id):
    task = read_task(task_id)

    sum = 0
    if task['tasks']:
        for subtask_id in task['tasks']:
            sum += sum_working_time(subtask_id)
        return sum
    else:
        return task.get('worked_time', 0) + get_last_work_time(task)


@command('wreset', 'id', 'Reset worked time in task')
def work_time_reset(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    task = read_task(task_id)
    if task['tasks']:
        perror('Cannot to worked time on task that has subtasks!')
        return
    task.pop('worked_time', None)
    write_task(task_id, task)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'init':
        init()
    if not is_initialized():
        err_die('Not initialized!\nTry: tasks init')

    atexit.register(end_work_in_all_tasks)
    config = {}
    init_config(config)

    see([], config)

    while True:
        curr_path = '/'.join(config['name_history'])
        cmd, *params = input(emoji.emojize(f'{curr_path}> ')).split(' ')

        if cmd in commands:
            commands[cmd]['fnc'](params, config)
        else:
            print(emoji.emojize('Author: Igor Santarek :Poland:'))
            print('\nAvailable commands:')
            for name in commands:
                print(commands[name]['help_msg'])
            print('\n[id] - optional with braces. Without the number is required.')
