import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread import Spreadsheet, Client


def load_data(sheets_url):
    csv_url = sheets_url.replace("/edit#gid=", "/export?format=csv&gid=")
    return pd.read_csv(csv_url)


@st.cache_resource()
def get_client() -> Client:
    credentials = Credentials.from_service_account_info(info=st.secrets, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(credentials)


@st.cache_resource()
def connect_to_spreadsheet(key: st) -> Spreadsheet:
    return get_client().open_by_key(key)


def get_in_queue():
    spreadsheet = connect_to_spreadsheet('13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M')

    data = pd.DataFrame(
        {
            'Name': [st.session_state['USERNAME']],
            'Tg': [st.session_state['TELEGRAM']],
            'Time': [pd.Timestamp.now().strftime('%Y-%m-%d %X')]
        }
    )
    spreadsheet.values_append('Queue', {'valueInputOption': 'RAW'}, {'values': data.values.tolist()})


def pop_queue(pos: int):
    spreadsheet = connect_to_spreadsheet('13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M')
    spreadsheet.worksheet('Queue').delete_rows(pos + 2)


if __name__ == '__main__':
    queue_spreadsheet_key = '13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M'

    if 'LOGGED_IN' not in st.session_state:
        st.session_state['LOGGED_IN'] = False

    if 'USERNAME' not in st.session_state:
        st.session_state['USERNAME'] = 'Anonim'

    logged_in = False
    del_login = st.empty()
    if not st.session_state['LOGGED_IN']:
        df = load_data('https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=0')

        names, tg = df['Name'], df['Tg']
        names_to_tg = dict(zip(names, tg))

        with del_login.form("Login Form"):
            option = st.selectbox('Who are you?', ['Anonim'] + list(names_to_tg.keys()))

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
        df = load_data('https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=1804024586')
        st.table(df)

        if not df.empty:
            mask = (df['Name'] == st.session_state['USERNAME'])
            in_queue = mask.any() # noqa
            position = mask.idxmax()  # noqa
        else:
            position = 0
            in_queue = False

        col1, col2 = st.columns(2, gap='large')

        with col1:
            if not in_queue:
                if st.button('Get in queue', use_container_width=True):
                    get_in_queue()
                    st.experimental_rerun()
            else:
                if st.button('Get out', use_container_width=True):
                    pop_queue(position)
                    st.experimental_rerun()

        with col2:
            if st.button('Refresh', use_container_width=True):
                st.experimental_rerun()
