"""Dashboard - Desfechos de animais no Austin Animal Center (AAC).

Execução local:  streamlit run app.py
"""
import streamlit as st

from core import data, filters, ui

st.set_page_config(
    page_title="Desfechos de animais no abrigo",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()

df = data.load_data()
meta = data.get_meta(df)
filters.render_sidebar(df, meta)  # filtros globais, válidos para todas as páginas

pages = [
    st.Page("views/visao_geral.py", title="Visão geral", icon=":material/dashboard:", default=True),
    st.Page("views/perfil_adocao.py", title="Perfil e adoção", icon=":material/pets:"),
    st.Page("views/sazonalidade.py", title="Sazonalidade e oportunidades", icon=":material/calendar_month:"),
]
st.navigation(pages).run()
