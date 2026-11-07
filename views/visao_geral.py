"""Página 1 - Visão geral dos desfechos."""
import pandas as pd
import streamlit as st

from core import charts, data, filters, metrics, ui
from core.data import ESPECIES, OUTCOME_GROUPS, WEEKDAYS
from core.ui import fmt_int, fmt_pct

df_all = data.load_data()
meta = data.get_meta(df_all)
f = filters.get_filters(df_all, meta)
df = filters.apply_filters(df_all, f)

st.title("Visão geral dos desfechos")
st.markdown("**Pergunta central:** como os animais estão deixando o abrigo e como esse cenário evoluiu?")
ui.stop_if_empty(df)

# ------------------------------- KPIs ------------------------------------- #
k = metrics.kpis_geral(df)
ui.kpi_row([
    ("Total de animais", fmt_int(k["animais"]),
     f"Animais distintos. Um mesmo animal pode ter mais de um desfecho: são {fmt_int(k['desfechos'])} desfechos registrados."),
    ("Total de adoções", fmt_int(k["adocoes"]), "Desfechos do tipo Adoção."),
    ("Taxa de adoção", fmt_pct(k["taxa_adocao"]), "Adoções ÷ total de desfechos do período filtrado."),
    ("Total de transferências", fmt_int(k["transferencias"]), "Desfechos do tipo Transferência (ex.: para parceiros e programas de adoção)."),
    ("Óbitos e eutanásias", fmt_int(k["obitos_euta"]),
     f"Óbitos: {fmt_int(k['obitos'])} · Eutanásias: {fmt_int(k['eutanasias'])}."),
])

# --------------------- Opções de exibição (uma linha) ---------------------- #
c1, c2, c3 = st.columns([1, 1, 1])
gran = c1.radio("Evolução e comparativo: granularidade", ["Mensal", "Anual"], horizontal=True)
split = c2.radio("Evolução dos desfechos", ["Total", "Por tipo de desfecho"], horizontal=True) == "Por tipo de desfecho"
dow_mode = c3.radio("Desfechos por dia da semana", ["Quantidade", "Proporção (%)"], horizontal=True)

months = filters.displayed_months(f, meta)
years, year_lbl = filters.year_labels(f, meta)
partial_note = None
if gran == "Anual" and any(lbl.endswith("*") for lbl in year_lbl):
    partial_note = ("\\* Ano parcial: a base cobre apenas parte dos meses (ou o filtro de período recorta o ano). "
                    "Não compare diretamente com anos completos.")

# ---------------------- 1) Distribuição dos desfechos ---------------------- #
dist = df["desfecho_grupo"].value_counts().reindex(OUTCOME_GROUPS, fill_value=0)
dist = dist[dist > 0].sort_values(ascending=False)
share = dist / dist.sum()
fig_dist = charts.hbar(
    labels=list(dist.index), values=dist.values,
    hover=[f"<b>{l}</b><br>{fmt_int(v)} desfechos ({fmt_pct(s)})" for l, v, s in zip(dist.index, dist.values, share)],
    texts=[f"{fmt_int(v)} · {fmt_pct(s)}" for v, s in zip(dist.values, share)],
    colors=[charts.entity_color(l) for l in dist.index], height=330)
full = df["desfecho"].value_counts().rename_axis("Desfecho").reset_index(name="Quantidade")
full["% do total"] = full["Quantidade"] / full["Quantidade"].sum() * 100

top2 = share.reindex(["Adoção", "Transferência"]).fillna(0).sum()

# ----------------------- 2) Evolução mensal / anual ------------------------ #
if gran == "Mensal":
    if split:
        wide = metrics.monthly(df, months, by="desfecho_grupo").reindex(columns=OUTCOME_GROUPS, fill_value=0)
        series = {g: wide[g] for g in OUTCOME_GROUPS if wide[g].sum() > 0}
        colors = {g: charts.entity_color(g) for g in series}
    else:
        series = {"Total de desfechos": metrics.monthly(df, months)}
        colors = {"Total de desfechos": charts.series_color(0)}
    fig_evo = charts.lines(months, series, colors)
    table_evo = pd.DataFrame(series).rename_axis("Mês").reset_index()
    table_evo["Mês"] = table_evo["Mês"].dt.strftime("%m/%Y")
else:
    if split:
        wide = metrics.yearly(df, years, by="desfecho_grupo").reindex(columns=OUTCOME_GROUPS, fill_value=0)
        wide.index = year_lbl
        fig_evo = charts.stacked(wide, normalize=False, height=340)
        table_evo = wide.rename_axis("Ano").reset_index()
    else:
        tot = metrics.yearly(df, years)
        fig_evo = charts.columns(
            year_lbl, tot.values,
            hover=[f"<b>{l}</b><br>{fmt_int(v)} desfechos" for l, v in zip(year_lbl, tot.values)],
            texts=[fmt_int(v) for v in tot.values])
        table_evo = pd.DataFrame({"Ano": year_lbl, "Desfechos": tot.values})

# --------------------- 3) Adoções versus transferências -------------------- #
ad_tr_colors = {"Adoção": charts.entity_color("Adoção"), "Transferência": charts.entity_color("Transferência")}
if gran == "Mensal":
    wide = metrics.monthly(df, months, by="desfecho_grupo")
    series = {g: wide.get(g, pd.Series(0, index=months)) for g in ad_tr_colors}
    fig_vs = charts.lines(months, series, ad_tr_colors)
    table_vs = pd.DataFrame(series).rename_axis("Mês").reset_index()
    table_vs["Mês"] = table_vs["Mês"].dt.strftime("%m/%Y")
else:
    wide = metrics.yearly(df, years, by="desfecho_grupo")
    series = {g: wide.get(g, pd.Series(0, index=years)) for g in ad_tr_colors}
    fig_vs = charts.grouped_columns(year_lbl, series, ad_tr_colors)
    table_vs = pd.DataFrame({"Ano": year_lbl, **{g: v.values for g, v in series.items()}})
adocoes, transf = k["adocoes"], k["transferencias"]
cap_vs = (f"No período filtrado: **{fmt_pct(metrics.safe_div(adocoes, adocoes + transf))}** das saídas por adoção ou transferência "
          f"foram adoções — {fmt_int(metrics.safe_div(adocoes, transf) * 100)} adoções para cada 100 transferências.") if (adocoes + transf) else None

# --------------------------- 4) Dia da semana ------------------------------ #
wide_dow = metrics.outcome_wide(df, "dia_semana", WEEKDAYS)
fig_dow = charts.stacked(wide_dow, normalize=(dow_mode != "Quantidade"), height=340)
busiest = wide_dow.sum(axis=1).idxmax()
best_adopt = wide_dow["Adoção"].idxmax()
cap_dow = f"Dia com mais desfechos: **{busiest}**. Dia com mais adoções: **{best_adopt}**."

# ------------------------------- Layout ----------------------------------- #
left, right = st.columns(2)
with left:
    ui.chart_card("Distribuição dos desfechos", fig_dist, full,
                  caption=f"Adoção e transferência somam **{fmt_pct(top2)}** dos desfechos. “Outros” agrupa desfechos raros (veja a tabela).",
                  table_config={"% do total": st.column_config.NumberColumn(format="%.1f%%")})
with right:
    tot_series = metrics.monthly(df, months) if gran == "Mensal" else metrics.yearly(df, years)
    peak = tot_series.idxmax()
    peak_lbl = peak.strftime("%m/%Y") if gran == "Mensal" else year_lbl[years.index(peak)]
    cap_evo = f"Pico do período: **{peak_lbl}** ({fmt_int(tot_series.max())} desfechos)."
    ui.chart_card(f"Evolução {gran.lower()} dos desfechos", fig_evo, table_evo,
                  caption=" ".join(x for x in [cap_evo, partial_note] if x))

left, right = st.columns(2)
with left:
    ui.chart_card(f"Adoções versus transferências ({gran.lower()})", fig_vs, table_vs,
                  caption=" ".join(x for x in [cap_vs, partial_note] if x) or None)
with right:
    ui.chart_card("Desfechos por dia da semana", fig_dow,
                  wide_dow.rename_axis("Dia").reset_index(), caption=cap_dow)

# ------------------------ 5) Desfechos por espécie ------------------------- #
if df["especie"].nunique() > 1:
    sp_order = [e for e in ESPECIES if e in set(df["especie"])]
    wide_sp = metrics.outcome_wide(df, "especie", sp_order)
    sp_rates = metrics.group_rates(df, "especie", sp_order).set_index("especie")["taxa_adocao"]
    top_sp = sp_rates.drop(labels=[e for e in sp_rates.index if wide_sp.loc[e].sum() < 100]).sort_values(ascending=False)
    cap_sp = (f"Maior taxa de adoção (espécies com 100+ desfechos): **{top_sp.index[0]}** ({fmt_pct(top_sp.iloc[0])}). "
              "Os perfis de desfecho são muito diferentes: compare proporções, não volumes.") if len(top_sp) else None
    ui.chart_card("Desfechos por espécie (proporção)",
                  charts.stacked(wide_sp, normalize=True, horizontal=True, height=max(260, 56 * len(wide_sp) + 90)),
                  wide_sp.rename_axis("Espécie").reset_index(), caption=cap_sp)

with st.expander("Perguntas de negócio respondidas nesta página"):
    st.markdown(
        "1. Como os desfechos evoluíram ao longo dos anos? → *Evolução mensal e anual*\n"
        "2. Qual a proporção de adoções em relação às transferências? → *Adoções versus transferências*\n"
        "8. Quais grupos têm maior incidência de óbitos e eutanásias? → página *Sazonalidade e oportunidades*")
