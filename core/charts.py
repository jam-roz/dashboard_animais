"""Paleta validada (claro/escuro) e fábrica de gráficos Plotly.

Regras aplicadas: cor segue a entidade (cada desfecho tem cor fixa), sem eixo duplo,
marcas finas, grade discreta, vão de 2px entre segmentos, rótulos seletivos.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from .data import MONTHS, OUTCOME_GROUPS, OUTCOME_MAIN
from .ui import fmt_int, fmt_pct

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# Ordem categórica fixa e validada (scripts/validate_palette.js: ΔE adjacente CVD ≥ 8, visão normal ≥ 15)
LIGHT = dict(
    mode="light", bg="#ffffff", surface="#fcfcfb", text="#0b0b0b", text2="#52514e", muted="#898781",
    grid="#e1e0d9", axis="#c3c2b7", other="#b4b2aa",
    cat=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
)
DARK = dict(
    mode="dark", bg="#171614", surface="#1f1e1c", text="#f0efec", text2="#c3c2b7", muted="#898781",
    grid="#2c2c2a", axis="#383835", other="#6b6a65",
    cat=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
)
# Rampa sequencial de um só matiz (azul), do claro ao escuro
_SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
        "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def theme_mode() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # fora do navegador (testes) ou versão sem st.context.theme
        return "light"


def pal() -> dict:
    return DARK if theme_mode() == "dark" else LIGHT


def entity_color(name: str) -> str:
    p = pal()
    return p["cat"][OUTCOME_MAIN.index(name)] if name in OUTCOME_MAIN else p["other"]


def series_color(i: int = 0) -> str:
    return pal()["cat"][i]


def _seq_scale() -> list:
    steps = _SEQ if theme_mode() == "light" else list(reversed(_SEQ))
    return [[i / (len(steps) - 1), c] for i, c in enumerate(steps)]


def _label_color(fill: str) -> str:
    return "#0b0b0b" if fill.lower() in (LIGHT["cat"][3], LIGHT["other"]) else "#ffffff"


# --------------------------------------------------------------------------- #
# Base visual
# --------------------------------------------------------------------------- #
def _style(fig: go.Figure, height: int, legend: bool, hovermode: str = "closest") -> go.Figure:
    p = pal()
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=12, t=30 if legend else 10, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=p["text2"]),
        hovermode=hovermode,
        hoverlabel=dict(bgcolor=p["surface"], bordercolor=p["axis"],
                        font=dict(family=FONT, size=12, color=p["text"])),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, traceorder="normal",
                    title_text="", font=dict(color=p["text2"], size=12)),
        separators=",.", bargap=0.35,
    )
    fig.update_xaxes(zeroline=False, linecolor=p["axis"], tickfont=dict(color=p["muted"]), automargin=True)
    fig.update_yaxes(zeroline=False, linecolor=p["axis"], tickfont=dict(color=p["muted"]), automargin=True)
    return fig


def _ref_line(fig: go.Figure, value: float, text: str, horizontal: bool) -> None:
    p = pal()
    kw = dict(line=dict(color=p["muted"], width=1, dash="dot"), annotation_text=text,
              annotation_font=dict(size=11, color=p["text2"]))
    if horizontal:
        fig.add_hline(y=value, annotation_position="top left", **kw)
    else:
        fig.add_vline(x=value, annotation_position="top", **kw)


# --------------------------------------------------------------------------- #
# Barras
# --------------------------------------------------------------------------- #
def hbar(labels, values, hover, texts, colors, xfmt=None, ref=None, ref_text=None, height=None) -> go.Figure:
    """Barras horizontais ranqueadas (o primeiro item fica no topo)."""
    p = pal()
    values = [float(v) for v in values]
    fig = go.Figure(go.Bar(
        y=list(labels), x=values, orientation="h",
        marker=dict(color=colors, cornerradius=4),
        text=texts, textposition="outside", cliponaxis=False,
        textfont=dict(color=p["text2"], size=12), hovertext=hover, hoverinfo="text"))
    _style(fig, height or max(230, 34 * len(labels) + 50), legend=False)
    # margem direita proporcional ao maior rótulo, para o texto fora da barra nunca ser cortado
    longest = max((len(str(t)) for t in (texts or [])), default=0)
    fig.update_layout(margin=dict(r=min(240, 16 + 7 * longest), t=40 if ref is not None else 10))
    top = max(values + [ref or 0]) if values else 1
    fig.update_xaxes(showgrid=True, gridcolor=p["grid"], tickformat=xfmt, range=[0, top * 1.05 or 1])
    fig.update_yaxes(autorange="reversed", showgrid=False, ticks="")
    if ref is not None:
        _ref_line(fig, ref, ref_text or "", horizontal=False)
    return fig


def columns(x, y, hover, texts=None, color=None, yfmt=None, height=340, ref=None, ref_text=None) -> go.Figure:
    """Colunas de uma série só (uma cor para todas as barras)."""
    p = pal()
    y = [float(v) for v in y]
    fig = go.Figure(go.Bar(
        x=list(x), y=y, marker=dict(color=color or series_color(0), cornerradius=4),
        text=texts, textposition="outside", cliponaxis=False, showlegend=False,
        textfont=dict(color=p["text2"], size=12), hovertext=hover, hoverinfo="text"))
    _style(fig, height, legend=False)
    top = max(y + [ref or 0]) if y else 1
    fig.update_yaxes(showgrid=True, gridcolor=p["grid"], tickformat=yfmt, range=[0, top * 1.18 or 1])
    fig.update_xaxes(showgrid=False, type="category")
    if ref is not None:
        # a referência vai para a legenda (um rótulo sobre o gráfico colidiria com as barras)
        ref_style = dict(color=p["muted"], width=1.5, dash="dot")
        fig.add_hline(y=ref, line=dict(color=p["muted"], width=1, dash="dot"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=ref_text or "Referência",
                                 line=ref_style, hoverinfo="skip"))
        fig.update_layout(showlegend=True, margin=dict(t=30))
    return fig


def grouped_columns(x, series: dict, colors: dict, height=340) -> go.Figure:
    fig = go.Figure()
    for name, vals in series.items():
        fig.add_trace(go.Bar(
            x=list(x), y=[float(v) for v in vals], name=name,
            marker=dict(color=colors[name], cornerradius=4),
            hovertext=[f"<b>{xi}</b><br>{name}: {fmt_int(v)}" for xi, v in zip(x, vals)], hoverinfo="text"))
    _style(fig, height, legend=len(series) > 1)
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(showgrid=True, gridcolor=pal()["grid"], tickformat=",d")
    fig.update_xaxes(showgrid=False, type="category")
    return fig


def stacked(wide, normalize: bool = False, horizontal: bool = False, height: int = 360) -> go.Figure:
    """Barras empilhadas por grupo de desfecho. `wide`: índice = categorias, colunas = OUTCOME_GROUPS."""
    p = pal()
    totals = wide.sum(axis=1)
    safe_tot = totals.replace(0, np.nan)
    cats = list(wide.index)
    fig = go.Figure()
    for g in [c for c in OUTCOME_GROUPS if c in wide.columns and wide[c].sum() > 0]:
        vals = wide[g]
        share = (vals / safe_tot).fillna(0)
        measure = (share * 100) if normalize else vals
        fill = entity_color(g)
        hover = [f"<b>{c}</b><br>{g}: {fmt_int(v)} ({fmt_pct(s)})<br>Total: {fmt_int(t)}"
                 for c, v, s, t in zip(cats, vals, share, totals)]
        text = [f"{s * 100:.0f}%" if (normalize and s >= 0.08) else "" for s in share]
        kw = dict(name=g, marker=dict(color=fill, line=dict(color=p["bg"], width=2)),
                  text=text, textposition="inside", insidetextanchor="middle",
                  textfont=dict(color=_label_color(fill), size=12), hovertext=hover, hoverinfo="text")
        if horizontal:
            fig.add_trace(go.Bar(y=cats, x=[float(m) for m in measure], orientation="h", **kw))
        else:
            fig.add_trace(go.Bar(x=cats, y=[float(m) for m in measure], **kw))
    _style(fig, height, legend=True)
    # legenda com 4+ itens quebra em 2 linhas: reserva espaço para ela não invadir o gráfico
    fig.update_layout(barmode="stack", margin=dict(t=64 if len(fig.data) > 3 else 34))
    val_axis = dict(showgrid=True, gridcolor=p["grid"],
                    **(dict(ticksuffix="%", range=[0, 100]) if normalize else dict(tickformat=",d")))
    if horizontal:
        fig.update_xaxes(**val_axis)
        fig.update_yaxes(autorange="reversed", showgrid=False, ticks="")
    else:
        fig.update_yaxes(**val_axis)
        fig.update_xaxes(showgrid=False, type="category")
    return fig


# --------------------------------------------------------------------------- #
# Linhas
# --------------------------------------------------------------------------- #
def lines(x, series: dict, colors: dict, yfmt: str = ",d", height: int = 340,
          date_axis: bool = True, markers: bool = False) -> go.Figure:
    """Linhas com tooltip unificado; último ponto destacado."""
    p = pal()
    fig = go.Figure()
    for name, vals in series.items():
        vals = [float(v) for v in vals]
        fig.add_trace(go.Scatter(
            x=list(x), y=vals, name=name, mode="lines+markers" if markers else "lines",
            line=dict(color=colors[name], width=2),
            marker=dict(size=8, color=colors[name], line=dict(color=p["bg"], width=2)),
            hovertemplate="%{y:" + yfmt + "}"))
        fig.add_trace(go.Scatter(
            x=[list(x)[-1]], y=[vals[-1]], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(size=9, color=colors[name], line=dict(color=p["bg"], width=2))))
    _style(fig, height, legend=len(series) > 1, hovermode="x unified")
    if len(series) > 3:
        fig.update_layout(margin=dict(t=64))
    fig.update_yaxes(showgrid=True, gridcolor=p["grid"], tickformat=yfmt, rangemode="tozero")
    if date_axis:
        fig.update_xaxes(showgrid=False, tickformat="%m/%Y", hoverformat="%m/%Y")
    else:
        fig.update_xaxes(showgrid=False, type="category")
    return fig


# --------------------------------------------------------------------------- #
# Mapa de calor
# --------------------------------------------------------------------------- #
def heatmap(z, xlabels, ylabels, hover, cbar_title: str, zfmt: str | None = None, height: int = 340) -> go.Figure:
    p = pal()
    fig = go.Figure(go.Heatmap(
        z=z, x=list(xlabels), y=list(ylabels), colorscale=_seq_scale(), xgap=2, ygap=2,
        hoverongaps=False, hovertext=hover, hoverinfo="text",
        colorbar=dict(thickness=10, len=0.9, outlinewidth=0, tickformat=zfmt,
                      tickfont=dict(color=p["muted"], size=11),
                      title=dict(text=cbar_title, font=dict(color=p["text2"], size=11)))))
    _style(fig, height, legend=False)
    fig.update_xaxes(type="category", showgrid=False, side="bottom")
    fig.update_yaxes(type="category", autorange="reversed", showgrid=False)
    return fig
