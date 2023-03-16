from os import environ

import streamlit as st
from streamlit_login_auth_ui.widgets import __login__


if __name__ == '__main__':
    __login__obj = __login__(
        auth_token=environ['COURIER_AUTH_TOKEN'],
        company_name=environ.get('COMPANY_NAME', 'Company Name'),
        width=200,
        height=250,
        logout_button_name='Logout',
        hide_menu_bool=False,
        hide_footer_bool=False,
        lottie_url=environ.get('LOTTIE_JSON_LINK', 'https://assets3.lottiefiles.com/packages/lf20_uzvwjpkq.json')
    )

    LOGGED_IN = __login__obj.build_login_ui()

    if LOGGED_IN:
        st.markdown("Your Streamlit Application Begins here!")
