from os import environ

import pandas as pd
import streamlit as st


@st.cache_data()
def load_data(sheets_url):
    csv_url = sheets_url.replace("/edit#gid=", "/export?format=csv&gid=")
    return pd.read_csv(csv_url)


if __name__ == '__main__':
    df = load_data('https://docs.google.com/spreadsheets/d/13rT_tVMi_GItPLF3gqNE9V011qRYCteAHiwGLW-No4M/edit#gid=0')

    if 'LOGGED_IN' not in st.session_state:
        st.session_state['LOGGED_IN'] = False

    if 'USERNAME' not in st.session_state:
        st.session_state['USERNAME'] = 'Anonim'

    names, tg = df['Name'], df['Tg']
    names_to_tg = dict(zip(names, tg))

    logged_in = False
    del_login = st.empty()
    if not st.session_state['LOGGED_IN']:
        with del_login.form("Login Form"):
            option = st.selectbox('Who are you?', ['Anonim'] + list(names_to_tg.keys()))

            st.markdown("###")
            login_submit_button = st.form_submit_button(label='Login')

            if login_submit_button:
                if option in names_to_tg:
                    del_login.empty()

                    st.session_state['LOGGED_IN'] = True
                    st.session_state['USERNAME'] = option
                    st.experimental_rerun()
                else:
                    st.error("Invalid Username or Password!")

    if st.session_state['LOGGED_IN']:
        st.write('You are:', st.session_state['USERNAME'])
        st.write('Your Tg:', names_to_tg[st.session_state['USERNAME']])
        st.write(st.secrets.credentials)

