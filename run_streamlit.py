import json
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from os import environ
from pprint import pprint
from typing import Tuple, Optional, Any, Dict

from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx


def add_context(ctx):
    add_script_run_ctx(threading.currentThread(), ctx)


# for some reason only separate executors for each task + before most of the imports work without strange errors
login_executor = ThreadPoolExecutor(max_workers=1, initializer=partial(add_context, ctx=get_script_run_ctx()))
queue_executor = ThreadPoolExecutor(max_workers=1, initializer=partial(add_context, ctx=get_script_run_ctx()))
notifications_executor = ThreadPoolExecutor(max_workers=1, initializer=partial(add_context, ctx=get_script_run_ctx()))


import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread import Client, Spreadsheet
from pandas import DataFrame
from streamlit_autorefresh import st_autorefresh
from streamlit_option_menu import option_menu
from trycourier import Courier
from validate_email import validate_email

time_fmt = '%Y-%m-%d %X'


USER_VARIABLES = {'NOTIFY', 'LOGGED_IN', 'EMAIL', 'NOTIFICATION_SENT'}
accounts_spreadsheet = 'https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=0'
queue_spreadsheet = 'https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=1804024586'


def load_data(sheets_url):
    csv_url = sheets_url.replace('/edit#gid=', '/export?format=csv&gid=')
    return pd.read_csv(csv_url)


@st.cache_resource()
def get_client() -> Client:
    credentials = Credentials.from_service_account_info(info=st.secrets, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(credentials)


def get_id(user: str) -> Tuple[int, int]:
    local_id = st.session_state['USERNAMES'].index(user)
    remote_id = local_id + 2  # 1 for header and 1 for indexation
    return local_id, remote_id


def filter_user_variables(state: Dict[str, Any]) -> Dict[str, Any]:
    return {name: value for name, value in state.items() if name in USER_VARIABLES}


def update_remote_state(user: str, state: Dict[str, Any]) -> str:
    spreadsheet = connect_to_spreadsheet('13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M')

    local_id, remote_id = get_id(user)
    variables = filter_user_variables(state)
    sync_time = pd.Timestamp.now().strftime(time_fmt)

    spreadsheet.values_update(
        f'Accounts!C{remote_id}:D{remote_id}',
        {'valueInputOption': 'RAW'},
        {'values': [[json.dumps(variables, ensure_ascii=False), sync_time]]}
    )

    return sync_time


def update_session_state(remote_accounts: DataFrame, new_variables: Optional[Dict[str, Any]] = None):
    if 'USERNAME' in new_variables:
        st.session_state['USERNAME'] = new_variables['USERNAME']

    if 'USERNAME' not in st.session_state:
        return

    st.session_state['LAST_SYNC'] = pd.Timestamp.now().strftime(time_fmt)
    st.session_state['USERNAMES'] = list(remote_accounts['Name'])
    st.session_state['TELEGRAMS'] = list(remote_accounts['Tg'])

    local_id, remote_id = get_id(st.session_state['USERNAME'])

    st.session_state['TELEGRAM'] = st.session_state['TELEGRAMS'][local_id]

    user_state = remote_accounts['State'][local_id]

    if not pd.isna(user_state):
        st.session_state.update(json.loads(user_state))

    if new_variables is not None:
        st.session_state.update(new_variables)


def fill_in_defaults(state: Dict[str, Any]):
    if 'LOGGED_IN' not in state:
        state['LOGGED_IN'] = False

    if 'NOTIFY' not in state:
        state['NOTIFY'] = False

    if 'NOTIFICATION_SENT' not in state:
        state['NOTIFICATION_SENT'] = False


def sync_with_remote(remote_accounts: DataFrame):
    if 'LAST_SYNC' not in st.session_state:
        return  # update_session_state was not called

    fill_in_defaults(st.session_state)

    local_id, remote_id = get_id(st.session_state['USERNAME'])
    remote_state = remote_accounts['State'][local_id]
    last_update = remote_accounts['Last state update'][local_id]

    remote_state = json.loads(remote_state) if not pd.isna(remote_state) else {}
    fill_in_defaults(remote_state)

    if last_update != st.session_state['LAST_SYNC']:
        # someone modified remote state, resolve conflicts

        if st.session_state['NOTIFICATION_SENT'] != remote_state['NOTIFICATION_SENT']:
            last_update_time = pd.to_datetime(last_update, format=time_fmt)
            if st.session_state['QUEUEING_TIME'] is not None and st.session_state['QUEUEING_TIME'] < last_update_time:
                st.session_state['NOTIFICATION_SENT'] = remote_state['NOTIFICATION_SENT']

        # other fields cannot be updated in remote

    if remote_state == filter_user_variables(st.session_state):
        return  # nothing to update

    st.session_state['LAST_SYNC'] = update_remote_state(st.session_state['USERNAME'], st.session_state)


def maybe_send_notification(queue_state: DataFrame, remote_accounts: DataFrame):
    if queue_state.empty or 'USERNAMES' not in st.session_state:
        return

    top_user = queue_state['Name'][0]
    local_id, remote_id = get_id(top_user)

    user_state = remote_accounts['State'][local_id]
    if pd.isna(user_state):
        return

    user_state = json.loads(user_state)
    if 'EMAIL' not in user_state or 'NOTIFY' not in user_state or 'NOTIFICATION_SENT' not in user_state:
        return

    if not user_state['NOTIFY'] or user_state['NOTIFICATION_SENT']:
        return

    # update user state to avoid multiple notifications
    user_state['NOTIFICATION_SENT'] = True
    update_remote_state(top_user, user_state)

    client = Courier(auth_token=environ['COURIER_AUTH_TOKEN'])
    client.send_message(
        message={
            'to': {
                'email': user_state['EMAIL']
            },
            'template': 'MY7YWVJR5XMKHBN48W1HSPC7K45M'
        }
    )


def waiter(f, *futures):
    results = [future.result() for future in futures]
    f(*results)


def thread_context_wrapper(f, ctx, *args, **kwargs):
    add_context(ctx)
    return f(*args, **kwargs)


@st.cache_resource()
def connect_to_spreadsheet(key: st) -> Spreadsheet:
    return get_client().open_by_key(key)


def get_in_queue():
    spreadsheet = connect_to_spreadsheet('13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M')

    data = pd.DataFrame(
        {
            'Name': [st.session_state['USERNAME']],
            'Tg': [st.session_state['TELEGRAM']],
            'Time': [pd.Timestamp.now().strftime(time_fmt)]
        }
    )
    spreadsheet.values_append('Queue', {'valueInputOption': 'RAW'}, {'values': data.values.tolist()})


def get_position(q) -> int:
    return (q['Name'] == st.session_state['USERNAME']).idxmax()  # noqa


def pop_queue(pos: int):
    spreadsheet = connect_to_spreadsheet('13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M')
    spreadsheet.worksheet('Queue').delete_rows(pos + 2)


def format_interval(x):
    ts = x.total_seconds()
    hours, remainder = divmod(ts, 3600)
    minutes, seconds = divmod(remainder, 60)

    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)

    if hours > 0:
        return f'{hours}h {minutes}m {seconds}s'
    if minutes > 0:
        return f'{minutes}m {seconds}s'
    return f'{seconds}s'


if __name__ == '__main__':
    future_accounts = login_executor.submit(load_data, accounts_spreadsheet)
    future_queue = queue_executor.submit(load_data, queue_spreadsheet)
    notifications_executor.submit(waiter, maybe_send_notification, future_queue, future_accounts)

    if 'USERNAME' not in st.session_state:
        st.session_state['USERNAME'] = 'Anonim'
    else:
        notifications_executor.submit(waiter, sync_with_remote, future_accounts)

    fill_in_defaults(st.session_state)

    st_autorefresh(interval=10000, limit=100, key="chatgpt-queue-refresh-counter")

    if not st.session_state['LOGGED_IN']:
        accounts = future_accounts.result()

        names, tg = list(accounts['Name']), list(accounts['Tg'])

        with st.form('Login Form'):
            form_names = ['Anonim'] + names
            option = st.selectbox('Who are you?', form_names, index=form_names.index(st.session_state['USERNAME']))

            login_submit_button = st.form_submit_button(label='Login')

            if login_submit_button:
                if option in names:
                    update_session_state(accounts, {'LOGGED_IN': True, 'USERNAME': option})
                    st.experimental_rerun()
                else:
                    st.error('Invalid Username!')

    if st.session_state['LOGGED_IN']:
        selected_tab = option_menu(
            None, ['Queue', 'Notify', 'Settings'],
            icons=['house', 'envelope', 'gear'],
            menu_icon="cast",
            default_index=0,
            orientation='horizontal'
        )

        if selected_tab == 'Queue':
            queue = future_queue.result()
            queue['In queue'] = (pd.Timestamp.now() - pd.to_datetime(queue['Time'], format=time_fmt)).apply(format_interval).astype(str)
            st.table(queue.drop(['Time'], axis=1))

            queue_names = list(queue['Name'])
            in_queue = (st.session_state['USERNAME'] in queue_names)

            if in_queue:
                queue_position = queue_names.index(st.session_state['USERNAME'])
                st.session_state['QUEUEING_TIME'] = pd.to_datetime(queue['Time'][queue_position])
            else:
                queue_position = None
                st.session_state['QUEUEING_TIME'] = None

            col1, col2 = st.columns(2, gap='large')

            with col1:
                if not in_queue:
                    if st.button('Get in queue', use_container_width=True):
                        st.session_state['NOTIFICATION_SENT'] = False
                        get_in_queue()
                        st.experimental_rerun()
                else:
                    if st.button('Get out', use_container_width=True):
                        pop_queue(queue_position)
                        st.experimental_rerun()

            with col2:
                if st.button('Refresh', use_container_width=True):
                    st.experimental_rerun()

            if in_queue:
                st.caption('Please refresh the queue before getting out')

        if selected_tab == 'Notify':
            if 'EMAIL' in st.session_state:
                col1, col2 = st.columns(2, gap='large')

                with col1:
                    notify = st.selectbox(
                        'We can notify you once it is your turn',
                        ['Do not send notifications', 'Send notifications'],
                        index=int(st.session_state['NOTIFY'])
                    )
                    st.session_state['NOTIFY'] = (notify == 'Send notifications')

                with col2:
                    st.caption(f'Your email: {st.session_state["EMAIL"]}')

                form_key, form_label = 'change_email', 'Change email'
            else:
                form_key, form_label = 'add_email', 'Add email'

            with st.form(form_key):
                email = st.text_input(form_label)
                if st.form_submit_button('Submit'):
                    if validate_email(email, check_format=True, check_dns=True, dns_timeout=10, check_smtp=True, smtp_timeout=10):
                        st.session_state['EMAIL'] = email
                        st.experimental_rerun()
                    else:
                        st.error(f'{email} is incorrect email address!')

        if selected_tab == 'Settings':
            if st.button('Logout'):
                st.session_state['LOGGED_IN'] = False
                st.experimental_rerun()


