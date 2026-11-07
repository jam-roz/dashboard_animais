"""Filtros globais (barra lateral) aplicados a todas as páginas."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from .data import AGE_SCHEMES, ESPECIES, Meta
from .ui import fmt_int

SEXO_OPTS = ["Fêmea", "Macho", "Desconhecido"]
FASE_OPTS = ["Filhote", "Adulto", "Desconhecido"]
CAST_OPTS = ["Castrado(a)", "Não castrado(a)", "Desconhecido"]
NOME_OPTS = ["Com nome", "Sem nome"]

_KEYS = {"periodo": "f_periodo", "esp": "f_esp", "fase": "f_fase", "sexo": "f_sexo",
         "cast": "f_cast", "nome": "f_nome", "parcial": "f_parcial", "faixa": "f_faixa"}


@dataclass
class Filters:
    start: pd.Timestamp
    end: pd.Timestamp
    especies: list = field(default_factory=list)
    fases: list = field(default_factory=list)
    sexos: list = field(default_factory=list)
    castracoes: list = field(default_factory=list)
    nomes: list = field(default_factory=list)
    show_partial: bool = False
    age_scheme: str = AGE_SCHEMES[0]


def _month_label(t: pd.Timestamp) -> str:
    return t.strftime("%m/%Y")


def _bump_version() -> None:
    """'Limpar filtros': troca a versão das chaves, e os widgets são recriados com o padrão.
    (Alterar o estado dos widgets por código faz o Streamlit exibir um aviso na tela.)"""
    st.session_state["_f_ver"] = st.session_state.get("_f_ver", 0) + 1


def _key(name: str) -> str:
    return f"{_KEYS[name]}_{st.session_state.get('_f_ver', 0)}"


def render_sidebar(df: pd.DataFrame, meta: Meta) -> Filters:
    """Desenha os filtros, guarda o resultado na sessão e o devolve."""
    months = list(pd.date_range(meta.first_month, meta.last_month, freq="MS"))

    with st.sidebar:
        st.header("Filtros")
        start, end = st.select_slider(
            "Período (mês/ano)", options=months, value=(months[0], months[-1]),
            format_func=_month_label, key=_key("periodo"))
        especies = st.multiselect("Espécie", ESPECIES, placeholder="Todas", key=_key("esp"),
                                  help="Vazio = todas as espécies. Selecione, por exemplo, só Gatos ou só Cães.")
        fases = st.multiselect("Filhote ou adulto", FASE_OPTS, placeholder="Todos", key=_key("fase"))
        sexos = st.multiselect("Sexo", SEXO_OPTS, placeholder="Todos", key=_key("sexo"))
        castr = st.multiselect("Situação de castração", CAST_OPTS, placeholder="Todas", key=_key("cast"))
        nomes = st.multiselect("Nome", NOME_OPTS, placeholder="Todos", key=_key("nome"))

        partial_txt = ", ".join(f"{MONTH_PT[m.month - 1]}/{m.year}" for m in meta.partial_months)
        show_partial = st.checkbox(
            "Mostrar mês parcial nos gráficos mensais",
            key=_key("parcial"),
            help=(f"A base termina no meio de um mês ({partial_txt}); mostrá-lo faz as séries "
                  "mensais parecerem despencar. Os KPIs e totais sempre incluem esses registros."
                  ) if partial_txt else "Não há mês parcial na base.",
            disabled=not meta.partial_months)

        st.button("Limpar filtros", on_click=_bump_version, width="stretch")

        st.divider()
        age_scheme = st.radio(
            "Faixas etárias", AGE_SCHEMES, key=_key("faixa"),
            help=("Detalhadas: < 2 meses, 2 a 5 meses, 6 a 11 meses, 1 a 2 anos… (calculadas pela idade exata). "
                  "Em anos: faixas fixas de 2 em 2 anos (0-1, 2-3…); a primeira concentra ~60% dos registros."))

    f = Filters(start, end, list(especies), list(fases), list(sexos), list(castr), list(nomes), bool(show_partial), age_scheme)
    st.session_state["_filters"] = f

    filtered = apply_filters(df, f)
    st.sidebar.caption(f"Exibindo **{fmt_int(len(filtered))}** de {fmt_int(len(df))} desfechos")
    st.sidebar.caption("Fonte: Austin Animal Center (dados abertos). Base tratada com `clean_dataset.py`.")
    return f


MONTH_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def get_filters(df: pd.DataFrame, meta: Meta) -> Filters:
    f = st.session_state.get("_filters")
    return f if f is not None else Filters(meta.first_month, meta.last_month)


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    m = (df["mes_ano"] >= f.start) & (df["mes_ano"] <= f.end)
    if f.especies:
        m &= df["especie"].isin(f.especies)
    if f.fases:
        m &= df["fase"].isin(f.fases)
    if f.sexos:
        m &= df["sexo"].isin(f.sexos)
    if f.castracoes:
        m &= df["castracao"].isin(f.castracoes)
    if f.nomes:
        m &= df["nome"].isin(f.nomes)
    return df[m]


# ----------------------- eixos de tempo respeitando filtros ----------------------- #
def displayed_months(f: Filters, meta: Meta) -> pd.DatetimeIndex:
    """Meses exibidos nos gráficos mensais (esconde o mês parcial, salvo se o usuário pedir)."""
    months = pd.date_range(f.start, f.end, freq="MS")
    if not f.show_partial:
        months = months[~months.isin(list(meta.partial_months))]
    return months


def partial_years(f: Filters, meta: Meta) -> set[int]:
    """Anos cuja janela exibida não cobre os 12 meses completos."""
    out = set()
    for y in range(f.start.year, f.end.year + 1):
        window = pd.date_range(max(f.start, pd.Timestamp(y, 1, 1)), min(f.end, pd.Timestamp(y, 12, 1)), freq="MS")
        covered = window[(window >= meta.first_month) & (window <= meta.last_month)]
        has_partial_month = any(m in covered for m in meta.partial_months)
        if len(covered) < 12 or has_partial_month:
            out.add(y)
    return out


def year_labels(f: Filters, meta: Meta) -> tuple[list[int], list[str]]:
    years = list(range(f.start.year, f.end.year + 1))
    partial = partial_years(f, meta)
    return years, [f"{y}*" if y in partial else str(y) for y in years]
