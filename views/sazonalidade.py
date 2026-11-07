"""Página 3 - Sazonalidade e oportunidades."""
import numpy as np
import pandas as pd
import streamlit as st

from core import charts, data, filters, metrics, ui
from core.data import MONTHS, OUTCOME_GROUPS
from core.filters import CAST_OPTS, FASE_OPTS, NOME_OPTS, SEXO_OPTS
from core.ui import fmt_dec, fmt_int, fmt_pct

df_all = data.load_data()
meta = data.get_meta(df_all)
f = filters.get_filters(df_all, meta)
df = filters.apply_filters(df_all, f)

st.title("Sazonalidade e oportunidades")
st.markdown("**Pergunta central:** quando ocorrem os maiores volumes de adoção e quais grupos precisam de maior atenção?")
ui.stop_if_empty(df)

months = filters.displayed_months(f, meta)
years, year_lbl = filters.year_labels(f, meta)

# --------------------- Opções de exibição (uma linha) ---------------------- #
c1, c2, c3 = st.columns(3)
heat_mode = c1.radio("Mapa de calor de adoções", ["Quantidade", "Taxa de adoção"], horizontal=True)
death_mode = c2.radio("Evolução de óbitos e eutanásias", ["Quantidade", "% dos desfechos"], horizontal=True)
age_outcome = c3.selectbox("Desfecho no mapa por faixa etária e ano", OUTCOME_GROUPS, index=0)

c4, c5 = st.columns([2, 1])
char_choice = c4.selectbox(
    "Comparar resultados por característica",
    ["Faixa etária", "Sexo", "Situação de castração", "Filhote ou adulto", "Com ou sem nome", "Raça", "Pelagem"])
min_n = c5.slider("Mínimo de desfechos por grupo", 10, 300, 50, step=10,
                  help="Grupos menores são ocultados nos comparativos por característica: a taxa deles é instável.")

# ------------- 1) Mapa de calor de adoções por mês e ano ------------------ #
rate_heat = heat_mode == "Taxa de adoção"
grid, tot_grid = metrics.month_year_grid(df, months, years, "is_adocao", rate=rate_heat)
hover = [[("" if np.isnan(grid.loc[y, m]) else
           f"<b>{MONTHS[m - 1]}/{y}</b><br>" +
           (f"Taxa de adoção: {fmt_pct(grid.loc[y, m])}<br>Desfechos: {fmt_int(tot_grid.loc[y, m])}" if rate_heat
            else f"Adoções: {fmt_int(grid.loc[y, m])}<br>Desfechos: {fmt_int(tot_grid.loc[y, m])}"))
          for m in range(1, 13)] for y in grid.index]
fig_heat = charts.heatmap(grid.to_numpy(), MONTHS, [str(y) for y in grid.index], hover,
                          cbar_title="Taxa" if rate_heat else "Adoções",
                          zfmt=".0%" if rate_heat else ",d", height=300)
table_heat = grid.copy()
table_heat.columns = MONTHS
if rate_heat:
    table_heat = table_heat * 100
table_heat = table_heat.rename_axis("Ano").reset_index()

# ------------- 2) Comparativo mensal: adoções x transferências ------------- #
# média por mês do ano, só com meses completos (evita viés de anos/meses parciais)
full_months = pd.date_range(f.start, f.end, freq="MS")
full_months = full_months[~full_months.isin(list(meta.partial_months))]
wide_m = metrics.monthly(df, full_months, by="desfecho_grupo").reindex(columns=OUTCOME_GROUPS, fill_value=0)
avg = wide_m.groupby(wide_m.index.month).mean()
n_obs = wide_m.groupby(wide_m.index.month).size()
x_months = [MONTHS[m - 1] for m in avg.index]
ad_tr = {g: avg[g] for g in ("Adoção", "Transferência")}
fig_season = charts.grouped_columns(x_months, ad_tr, {g: charts.entity_color(g) for g in ad_tr})
table_season = pd.DataFrame({"Mês": x_months, "Adoções (média/mês)": avg["Adoção"].round(1).values,
                             "Transferências (média/mês)": avg["Transferência"].round(1).values,
                             "Meses na média": n_obs.values})
cap_season = None
if len(avg):
    top_m, low_m = avg["Adoção"].idxmax(), avg["Adoção"].idxmin()
    cap_season = (f"Maior média de adoções: **{MONTHS[top_m - 1]}** (≈ {fmt_int(avg['Adoção'].max())}/mês). "
                  f"Menor: **{MONTHS[low_m - 1]}** (≈ {fmt_int(avg['Adoção'].min())}/mês). "
                  "Média por mês do ano considerando apenas meses completos.")

# ------------- 3) Evolução de óbitos e eutanásias -------------------------- #
rate_death = death_mode != "Quantidade"
wide_d = metrics.monthly(df, months, by="desfecho_grupo").reindex(columns=OUTCOME_GROUPS, fill_value=0)
tot_d = wide_d.sum(axis=1).replace(0, np.nan)
death_series = {g: (wide_d[g] / tot_d).fillna(0) if rate_death else wide_d[g] for g in ("Óbito", "Eutanásia")}
fig_death = charts.lines(months, death_series, {g: charts.entity_color(g) for g in death_series},
                         yfmt=".1%" if rate_death else ",d")
table_death = pd.DataFrame({g: (v * 100 if rate_death else v) for g, v in death_series.items()}).rename_axis("Mês").reset_index()
table_death["Mês"] = table_death["Mês"].dt.strftime("%m/%Y")
k = metrics.kpis_geral(df)
cap_death = (f"No período: **{fmt_int(k['eutanasias'])}** eutanásias e **{fmt_int(k['obitos'])}** óbitos "
             f"({fmt_pct(metrics.safe_div(k['obitos_euta'], k['desfechos']))} dos desfechos).")

# ------------- 4) Desfechos por faixa etária e período --------------------- #
age_col, faixas = data.age_scheme(df, f.age_scheme)
base = df[df[age_col].isin(faixas)]


def _grid(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame.groupby([age_col, "ano"]).size().unstack(fill_value=0)
            .reindex(index=faixas, columns=years, fill_value=0))


tot_age = _grid(base)
num_age = _grid(base[base["desfecho_grupo"] == age_outcome])
MIN_CELL = 10
val_age = (num_age / tot_age.replace(0, np.nan)).where(tot_age >= MIN_CELL)
hover_age = [[("" if np.isnan(val_age.loc[fx, y]) else
               f"<b>{fx} · {y}</b><br>{age_outcome}: {fmt_pct(val_age.loc[fx, y])}"
               f"<br>({fmt_int(num_age.loc[fx, y])} de {fmt_int(tot_age.loc[fx, y])} desfechos)")
              for y in years] for fx in faixas]
fig_age = charts.heatmap(val_age.to_numpy(), year_lbl, faixas, hover_age,
                         cbar_title=f"% {age_outcome}", zfmt=".0%", height=max(300, 34 * len(faixas) + 70))
table_age = (val_age * 100).round(1)
table_age.columns = year_lbl
table_age = table_age.rename_axis("Faixa etária").reset_index()
any_partial = any(lbl.endswith("*") for lbl in year_lbl)
cap_age = (f"Cada célula mostra a % de desfechos “{age_outcome}” dentro da faixa e do ano. "
           f"Células com menos de {MIN_CELL} desfechos ficam em branco."
           + (" \\* Ano parcial." if any_partial else ""))

# ------------- 5) Comparativo por característica + grupos de atenção ------- #
CHARS = {
    "Faixa etária": (age_col, faixas),
    "Sexo": ("sexo", SEXO_OPTS),
    "Situação de castração": ("castracao", CAST_OPTS),
    "Filhote ou adulto": ("fase", FASE_OPTS),
    "Com ou sem nome": ("nome", NOME_OPTS),
    "Raça": ("raca", None),
    "Pelagem": ("pelagem", None),
}
col, order = CHARS[char_choice]
tab = metrics.group_rates(df, col, order)
n_groups = len(tab)
tab = tab[tab["desfechos"] >= min_n]
if order is None:
    tab = tab.sort_values("desfechos", ascending=False).head(10)
hidden = n_groups - len(tab)
overall_death = metrics.safe_div(k["obitos_euta"], k["desfechos"])
note_hidden = f"{hidden} grupo(s) ocultado(s) por terem menos de {min_n} desfechos (ou fora do top 10)." if hidden > 0 else None

# ------------------------------- Layout ----------------------------------- #
ui.chart_card("Mapa de calor de adoções por mês e ano", fig_heat, table_heat,
              caption="Células em branco = fora do período filtrado, sem dados na base ou mês parcial oculto.",
              table_config=None if not rate_heat else {m: st.column_config.NumberColumn(format="%.1f%%") for m in MONTHS})

left, right = st.columns(2)
with left:
    ui.chart_card("Comparativo mensal: adoções e transferências", fig_season, table_season, caption=cap_season)
with right:
    ui.chart_card("Evolução de óbitos e eutanásias", fig_death, table_death, caption=cap_death,
                  table_config={g: st.column_config.NumberColumn(format="%.1f%%" if rate_death else "%d") for g in death_series})

ui.chart_card(f"Desfechos por faixa etária e período — {age_outcome}", fig_age, table_age, caption=cap_age)

st.subheader("Comparativo de resultados por característica")
st.caption(f"Característica selecionada: **{char_choice}**." + (f" {note_hidden}" if note_hidden else ""))
if tab.empty:
    st.info("Nenhum grupo atende ao mínimo de desfechos. Reduza o mínimo ou amplie o período.")
else:
    left, right = st.columns(2)
    wide_c = metrics.outcome_wide(df, col, list(tab[col]))
    with left:
        ui.chart_card("Distribuição dos desfechos por grupo", charts.stacked(wide_c, normalize=True, horizontal=True,
                      height=max(280, 46 * len(wide_c) + 90)), wide_c.rename_axis(char_choice).reset_index())
    rank = tab.sort_values("taxa_obito_euta", ascending=False).reset_index(drop=True)
    fig_rank = charts.hbar(
        rank[col], rank["taxa_obito_euta"],
        [f"<b>{r[col]}</b><br>Óbitos + eutanásias: {fmt_int(r['obitos_euta'])} de {fmt_int(r['desfechos'])}"
         f"<br>Incidência: {fmt_pct(r['taxa_obito_euta'])}" for _, r in rank.iterrows()],
        [f"{fmt_pct(t)}  (n={fmt_int(n)})" for t, n in zip(rank["taxa_obito_euta"], rank["desfechos"])],
        colors=charts.entity_color("Eutanásia"), xfmt=".0%", ref=overall_death,
        ref_text=f"Média geral {fmt_pct(overall_death)}", height=max(280, 46 * len(rank) + 90))
    worst = rank.iloc[0]
    ratio = metrics.safe_div(worst["taxa_obito_euta"], overall_death)
    cap_rank = (f"Maior incidência: **{worst[col]}** — {fmt_pct(worst['taxa_obito_euta'])} "
                f"({fmt_dec(ratio)}× a média geral).") if ratio == ratio else None
    with right:
        ui.chart_card("Grupos com maior incidência de óbitos e eutanásias", fig_rank,
                      pd.DataFrame({char_choice: rank[col], "Desfechos": rank["desfechos"],
                                    "Óbitos + eutanásias": rank["obitos_euta"],
                                    "Incidência": rank["taxa_obito_euta"] * 100}),
                      caption=cap_rank, table_config={"Incidência": st.column_config.NumberColumn(format="%.1f%%")})

with st.expander("Perguntas de negócio respondidas nesta página"):
    st.markdown(
        "6. Quais meses apresentam maior volume de adoções? → *Mapa de calor* e *Comparativo mensal*\n"
        "3. Como a idade influencia os resultados? → *Desfechos por faixa etária e período*\n"
        "8. Quais grupos apresentam maior incidência de óbitos e eutanásias? → *Grupos com maior incidência*\n\n"
        "**Atenção:** a incidência alta pode refletir a condição em que o animal chega (filhotes sem mãe, animais idosos ou "
        "doentes), e não a atuação do abrigo; use como pista de onde olhar, não como veredito.")
