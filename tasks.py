import os
import json
import sys
import emoji
import sys, tempfile, os
from subprocess import call


TODO_STATE = 'todo'
IN_PROGRESS_STATE = 'progr'
DONE_STATE = 'done'


TODO_STATE_SYMBOL = ':eight_o’clock:'
IN_PROGRESS_STATE_SYMBOL = ':wrench:'
DONE_STATE_SYMBOL = ':check_mark:'

TASKS_DIR = '.tasks'
EDITOR = os.environ.get('EDITOR','vim')


def is_initialized():
    return os.path.isdir(TASKS_DIR)


def perror(err):
    print(err, file=sys.stderr)


def err_die(err):
    perror(err)
    exit(1)


def get_task_path(task_id) :
    return os.path.join(TASKS_DIR, f'{task_id}.json')


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
            state_symbol = task_state_symbol(subtask['state'])
            task_count = len(subtask['tasks'])
            name = subtask['name']
            print(emoji.emojize(f'#{subtask_id} {state_symbol} ({task_count}) {name}'))
    else:
        perror(f'Task {task_id} does not exist!')


def go_in(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    
    task = read_task(task_id)
    config['current'] = task
    config['history'].append(task_id)
    config['name_history'].append(task['name'])


def go_out(config):
    if len(config['history']) > 1:
        config['history'].pop()
        config['name_history'].pop()
        config['current'] = read_task(current(config))
    else:
        perror('Cannot out of root task!')


def new_task(params, config):
    if not params:
        perror('Missing name parameter!')
        return

    task_id = available_id()
    task = empty_task(' '.join(params))
    config['current']['tasks'].append(task_id)
    write_task(task_id, task)
    write_task(current(config), config['current'])
    fix_ancestors_state(len(config['history']) - 1)


def rm_task(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    if task_id == 0:
        perror('Cannot remove root task!')
        return
    
    is_sure = input('Are you sure (Y/N)? ')
    if is_sure.lower() == 'y':
        rm_subtask(task_id, current(config))


def rm_subtask(subtask_id, parent_id):
    subtask = read_task(subtask_id)

    for subsubtask_id in subtask['tasks']:
        rm_subtask(subsubtask_id, subtask_id)
    
    parent = read_task(parent_id)
    parent['tasks'].remove(subtask_id)
    write_task(parent_id, parent)

    os.remove(get_task_path(subtask_id))


def set_task_state(task_id, state):
    task = read_task(task_id)

    if task['tasks']:
        perror(f'Cannot change state of task with subtasks!')
        return

    task['state'] = state
    write_task(task_id, task)
    start_fixing_ancestors_state()


def start_fixing_ancestors_state():
    fix_ancestors_state(len(config['history']) - 1)


def fix_ancestors_state(history_id = None):
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
        task['state'] = curr_state
        write_task(task_id, task)
        fix_ancestors_state(history_id - 1)


def set_in_progr(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    
    set_task_state(task_id, IN_PROGRESS_STATE)


def set_done(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return
    task_id = id_from(params)
    
    set_task_state(task_id, DONE_STATE)


def reset(params, config):
    error_msg = get_id_error_msg(params, config)
    if error_msg is not None:
        perror(error_msg)
        return

    is_sure = input('Are you sure (Y/N)? ')
    if is_sure.lower() == 'y':
        task_id = id_from(params)
        reset_task(task_id)
        start_fixing_ancestors_state()


def reset_task(task_id):
    task = read_task(task_id)
    for subtask_id in task['tasks']:
        reset_task(subtask_id)
    task['state'] = TODO_STATE
    write_task(task_id, task)


def descr(params, config):
    task_id = current(config)
    if params:
        if is_task_id(params):
            task_id = id_from(params)
        else:
            perror('Id parameter is wrong!')
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


def info(params, config):
    task_id = current(config)
    if params:
        if is_task_id(params):
            task_id = id_from(params)
        else:
            perror('Id parameter is wrong!')
            return
    task = read_task(task_id)
    if 'descr' in task:
        print(task['descr'])


def do_cmd(cmd, params, config):
    if cmd == 'see':
        see(params, config)
    elif cmd == 'in':
        go_in(params, config)
        see([], config)
    elif cmd == 'out':
        go_out(config)
        see([], config)
    elif cmd == 'new':
        new_task(params, config)
        see([], config)
    elif cmd == 'rm':
        rm_task(params, config)
        see([], config)
    elif cmd == 'progr':
        set_in_progr(params, config)
        see([], config)
    elif cmd == 'done':
        set_done(params, config)
        see([], config)
    elif cmd == 'reset':
        reset(params, config)
        see([], config)
    elif cmd == 'descr':
        descr(params, config)
    elif cmd == 'info':
        info(params, config)
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

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'init':
        init()
    if not is_initialized():
        err_die('Not initialized!')

    config = {
        'current': read_task(0),
        'history': [0],
        'name_history': ['root']
    }

    see([], config)
    
    while True:
        curr_path = '/'.join(config['name_history'])
        cmd, *params = input(emoji.emojize(f'{curr_path}> ')).split(' ')

        if cmd == 'exit':
            exit(0)
        else:
            do_cmd(cmd, params, config)
