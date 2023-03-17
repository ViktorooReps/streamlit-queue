import threading
from concurrent.futures import ThreadPoolExecutor, Future
from os import environ

from pandas import DataFrame
from streamlit_option_menu import option_menu

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread import Spreadsheet, Client
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from streamlit_autorefresh import st_autorefresh
from trycourier import Courier
from validate_email import validate_email


accounts_spreadsheet = 'https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=0'
queue_spreadsheet = 'https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=1804024586'
time_fmt = '%Y-%m-%d %X'


def load_data(sheets_url):
    csv_url = sheets_url.replace("/edit#gid=", "/export?format=csv&gid=")
    return pd.read_csv(csv_url)


@st.cache_resource()
def get_client() -> Client:
    credentials = Credentials.from_service_account_info(info=st.secrets, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(credentials)


def maybe_send_notification(q: DataFrame):
    if st.session_state['NOTIFY'] and not q.empty and q['Name'][0] == st.session_state['USERNAME']:
        client = Courier(auth_token=environ['COURIER_AUTH_TOKEN'])
        client.send_message(
            message={
                "to": {
                    "email": st.session_state['EMAIL']
                },
                "template": "MY7YWVJR5XMKHBN48W1HSPC7K45M"
            }
        )
        st.session_state['NOTIFY'] = False


def waiter(future: Future, f):
    f(future.result())


def thread_context_wrapper(f, ctx, *args, **kwargs):
    add_script_run_ctx(threading.currentThread(), ctx)
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


executor = ThreadPoolExecutor(max_workers=3)


if __name__ == '__main__':
    st_autorefresh(interval=30000, limit=100, key="chatgpt-queue-refresh-counter")
    thread_ctx = get_script_run_ctx()
    future_accounts = executor.submit(thread_context_wrapper, load_data, thread_ctx, accounts_spreadsheet)
    future_queue = executor.submit(thread_context_wrapper, load_data, thread_ctx, queue_spreadsheet)
    future_cached_client = executor.submit(thread_context_wrapper, get_client, thread_ctx)

    if 'LOGGED_IN' not in st.session_state:
        st.session_state['LOGGED_IN'] = False

    if 'USERNAME' not in st.session_state:
        st.session_state['USERNAME'] = 'Anonim'

    if 'NOTIFY' not in st.session_state:
        st.session_state['NOTIFY'] = False

    executor.submit(waiter, future_queue, maybe_send_notification)

    del_login = st.empty()
    if not st.session_state['LOGGED_IN']:
        accounts = future_accounts.result()

        names, tg = list(accounts['Name']), list(accounts['Tg'])
        names_to_tg = dict(zip(names, tg))

        with del_login.form("Login Form"):
            form_names = ['Anonim'] + names
            option = st.selectbox('Who are you?', form_names, index=form_names.index(st.session_state['USERNAME']))

            st.markdown("###")
            login_submit_button = st.form_submit_button(label='Login')

            if login_submit_button:
                if option in names_to_tg:
                    del_login.empty()

                    st.session_state['LOGGED_IN'] = True
                    st.session_state['USERNAME'] = option
                    st.session_state['TELEGRAM'] = names_to_tg[option]
                    st.session_state['USERNAMES'] = tuple(names)
                    st.session_state['TELEGRAMS'] = tuple(tg)
                    st.experimental_rerun()
                else:
                    st.error("Invalid Username!")

    if st.session_state['LOGGED_IN']:
        selected_tab = option_menu(
            None, ["Queue", "Notify", 'Settings'],
            icons=['house', 'envelope', 'gear'],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal"
        )

        if selected_tab == 'Queue':
            queue = future_queue.result()
            queue['In queue'] = (pd.Timestamp.now() - pd.to_datetime(queue['Time'], format=time_fmt)).apply(format_interval).astype(str)
            queue = queue.drop(['Time'], axis=1)
            st.table(queue)

            if not queue.empty:
                mask = (queue['Name'] == st.session_state['USERNAME'])
                in_queue = mask.any() # noqa
            else:
                in_queue = False

            col1, col2 = st.columns(2, gap='large')

            with col1:
                if not in_queue:
                    if st.button('Get in queue', use_container_width=True):
                        future_cached_client.result()
                        get_in_queue()
                        st.experimental_rerun()
                else:
                    if st.button('Get out', use_container_width=True):
                        future_cached_client.result()
                        pop_queue(get_position(queue))
                        st.experimental_rerun()

            with col2:
                if st.button('Refresh', use_container_width=True):
                    st.experimental_rerun()

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


