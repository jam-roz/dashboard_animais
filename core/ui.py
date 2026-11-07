"""Utilitários de interface: formatação pt-BR, cartões de gráfico e KPIs."""
from __future__ import annotations

import inspect
import re

import streamlit as st

PLOT_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


# ----------------------------- formatação pt-BR ----------------------------- #
def fmt_int(n) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def fmt_dec(x, d: int = 1) -> str:
    return f"{x:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_pct(x, d: int = 1) -> str:
    """x em fração (0.25 -> 25,0%)."""
    return f"{x * 100:.{d}f}".replace(".", ",") + "%"


# --------------------------------- layout ----------------------------------- #
def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px;}
        [data-testid="stMetricValue"] {font-size: 1.9rem; font-weight: 600;}
        [data-testid="stMetricLabel"] p {font-size: .85rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _stretch(fn) -> dict:
    """Compatível com versões novas (width='stretch') e antigas (use_container_width)."""
    params = inspect.signature(fn).parameters
    return {"width": "stretch"} if "width" in params else {"use_container_width": True}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def stop_if_empty(df) -> None:
    if df.empty:
        st.warning("Nenhum registro com os filtros atuais. Ajuste os filtros na barra lateral.")
        st.stop()


def kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    """items: (rótulo, valor já formatado, texto de ajuda)."""
    for col, (label, value, help_) in zip(st.columns(len(items)), items):
        with col:
            st.metric(label, value, help=help_, border=True)


def chart_card(title, fig, table=None, caption=None, note=None, table_config=None):
    """Gráfico + legenda interpretativa + tabela equivalente (acessibilidade)."""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if note:
            st.caption(note)
        st.plotly_chart(fig, key=f"fig-{slug(title)}", config=PLOT_CONFIG,
                        **_stretch(st.plotly_chart))
        if caption:
            st.caption(caption)
        if table is not None:
            with st.expander("Ver tabela de dados"):
                st.dataframe(table, hide_index=True, column_config=table_config,
                             key=f"tbl-{slug(title)}", **_stretch(st.dataframe))
