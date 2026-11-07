"""Página 2 - Perfil e adoção."""
import pandas as pd
import streamlit as st

from core import charts, data, filters, metrics, ui
from core.filters import CAST_OPTS, NOME_OPTS, SEXO_OPTS
from core.ui import fmt_dec, fmt_int, fmt_pct

df_all = data.load_data()
meta = data.get_meta(df_all)
f = filters.get_filters(df_all, meta)
df = filters.apply_filters(df_all, f)

st.title("Perfil e adoção")
st.markdown("**Pergunta central:** quais características estão associadas aos melhores resultados de adoção?")
ui.stop_if_empty(df)

# ------------------------------- KPIs ------------------------------------- #
p = metrics.kpis_perfil(df)
ui.kpi_row([
    ("Percentual de filhotes", fmt_pct(p["pct_filhotes"]),
     "Filhotes ÷ desfechos com idade conhecida. Filhote = até 182 dias (~6 meses) de idade, para todas as espécies."),
    ("Percentual de castração", fmt_pct(p["pct_castracao"]),
     f"Castrados ÷ desfechos com situação conhecida (exclui {fmt_int(p['n_cast_desconhecido'])} com situação desconhecida). "
     "A situação é a registrada no momento do desfecho."),
    ("Idade média", f"{fmt_dec(p['idade_media'])} anos",
     f"Mediana: {fmt_dec(p['idade_mediana'] * 12)} meses. A média é puxada por poucos animais idosos; "
     "a mediana descreve melhor o animal típico."),
])

# --------------------- Opções de exibição (uma linha) ---------------------- #
c1, c2, c3 = st.columns([1.3, 1, 1])
mode = c1.radio("Medida nos gráficos de adoção", ["Quantidade de adoções", "Taxa de adoção"], horizontal=True, index=1,
                help="Taxa = adoções ÷ desfechos do grupo: permite comparar grupos de tamanhos diferentes e é a melhor medida "
                     "para ver quais perfis têm melhores resultados. Quantidade mostra o volume, dominado pelos grupos maiores.")
min_n = c2.slider("Mínimo de desfechos por grupo (taxa)", 10, 300, 50, step=10,
                  help="Em raça e pelagem, esconde grupos pequenos cuja taxa é instável.")
top_n = c3.slider("Itens exibidos em raça e pelagem", 5, 20, 10)
rate = mode == "Taxa de adoção"
overall = metrics.safe_div(int(df["is_adocao"].sum()), len(df))

ADOCAO_COLOR = charts.entity_color("Adoção")
TABLE_CFG = {"Taxa de adoção": st.column_config.NumberColumn(format="%.1f%%")}


def rates_table(tab: pd.DataFrame, label: str) -> pd.DataFrame:
    return pd.DataFrame({label: tab.iloc[:, 0], "Desfechos": tab["desfechos"], "Adoções": tab["adocoes"],
                         "Taxa de adoção": tab["taxa_adocao"] * 100})


def values_and_text(tab: pd.DataFrame):
    if rate:
        return tab["taxa_adocao"], [f"{fmt_pct(t)}" for t in tab["taxa_adocao"]]
    return tab["adocoes"], [fmt_int(a) for a in tab["adocoes"]]


def hovers(tab: pd.DataFrame):
    label = tab.columns[0]
    return [f"<b>{r[label]}</b><br>Adoções: {fmt_int(r['adocoes'])}<br>Desfechos: {fmt_int(r['desfechos'])}"
            f"<br>Taxa de adoção: {fmt_pct(r['taxa_adocao'])}" for _, r in tab.iterrows()]


def adoption_columns(col, label, order=None, exclude=()):
    tab = metrics.group_rates(df, col, order)
    tab = tab[~tab[col].isin(exclude)].reset_index(drop=True)
    vals, texts = values_and_text(tab)
    fig = charts.columns(
        tab[col], vals, hovers(tab), texts, color=ADOCAO_COLOR,
        yfmt=".0%" if rate else ",d", ref=overall if rate else None,
        ref_text=f"Média geral {fmt_pct(overall)}")
    return fig, tab, rates_table(tab, label)


def adoption_hbar(col, label):
    tab = metrics.group_rates(df, col)
    if rate:
        tab = tab[tab["desfechos"] >= min_n].sort_values("taxa_adocao", ascending=False)
    else:
        tab = tab.sort_values("adocoes", ascending=False)
    tab = tab.head(top_n).reset_index(drop=True)
    if tab.empty:
        return None, tab, None
    vals, texts = values_and_text(tab)
    if rate:
        texts = [f"{t}  (n={fmt_int(n)})" for t, n in zip(texts, tab["desfechos"])]
    fig = charts.hbar(tab[col], vals, hovers(tab), texts, colors=ADOCAO_COLOR,
                      xfmt=".0%" if rate else ",d", ref=overall if rate else None,
                      ref_text=f"Média geral {fmt_pct(overall)}")
    return fig, tab, rates_table(tab, label)


def card_or_info(title, fig, table, **kw):
    if fig is None:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.info("Nenhum grupo atende ao mínimo de desfechos. Reduza o mínimo ou amplie o período.")
    else:
        ui.chart_card(title, fig, table, table_config=TABLE_CFG, **kw)


# ------------------------------- Gráficos --------------------------------- #
# 1) Faixa etária (agrupamento escolhido na barra lateral)
age_col, age_order = data.age_scheme(df, f.age_scheme)
fig_age, tab_age, t_age = adoption_columns(age_col, "Faixa etária", age_order, exclude=("Desconhecida",))
reliable = tab_age[tab_age["desfechos"] >= 30]
cap_age = None
if not reliable.empty:
    best = reliable.sort_values("taxa_adocao", ascending=False).iloc[0]
    cap_age = (f"Maior taxa de adoção (grupos com 30+ desfechos): **{best[age_col]}** "
               f"({fmt_pct(best['taxa_adocao'])}). Faixas: {f.age_scheme.lower()}.")

# 2) Sexo (desfechos empilhados)
wide_sex = metrics.outcome_wide(df, "sexo", SEXO_OPTS)
fig_sex = charts.stacked(wide_sex, normalize=rate, height=340)
sex_rates = metrics.group_rates(df, "sexo").set_index("sexo")["taxa_adocao"]
cap_sex = " · ".join(f"{s}: **{fmt_pct(sex_rates[s])}**" for s in SEXO_OPTS if s in sex_rates.index)
cap_sex = f"Taxa de adoção — {cap_sex}. “Desconhecido” vem sobretudo de animais silvestres (outros) e de gatos transferidos, por isso os desfechos são bem diferentes."

# 3) Castração
fig_cast, tab_cast, t_cast = adoption_columns("castracao", "Situação de castração", CAST_OPTS)
adopted = df[df["is_adocao"]]
cap_cast = (f"**{fmt_pct(metrics.safe_div((adopted['castracao'] == 'Castrado(a)').sum(), len(adopted)))}** das adoções são de animais castrados. "
            "A castração costuma ocorrer antes da saída do abrigo e está ligada à idade (filhotes não são castrados): "
            "leia como associação, não como causa.") if len(adopted) else None

# 4) Com e sem nome
wide_nome = metrics.outcome_wide(df, "nome", NOME_OPTS)
fig_nome = charts.stacked(wide_nome, normalize=rate, height=340)
nome_rates = metrics.group_rates(df, "nome").set_index("nome")["taxa_adocao"]
cap_nome = " · ".join(f"{n}: **{fmt_pct(nome_rates[n])}**" for n in NOME_OPTS if n in nome_rates.index)
cap_nome = f"Taxa de adoção — {cap_nome}."

# 5) Raça e pelagem
fig_breed, tab_breed, t_breed = adoption_hbar("raca", "Raça (principal)")
fig_coat, tab_coat, t_coat = adoption_hbar("pelagem", "Pelagem")
note_rank = (f"Ranking por taxa de adoção entre grupos com {min_n}+ desfechos." if rate
             else "Ranking por quantidade de adoções.")

# ------------------------------- Layout ----------------------------------- #
left, right = st.columns(2)
with left:
    ui.chart_card("Adoções por faixa etária", fig_age, t_age, caption=cap_age, table_config=TABLE_CFG)
with right:
    ui.chart_card("Desfechos por sexo", fig_sex, wide_sex.rename_axis("Sexo").reset_index(), caption=cap_sex)

left, right = st.columns(2)
with left:
    ui.chart_card("Adoções por situação de castração", fig_cast, t_cast, caption=cap_cast, table_config=TABLE_CFG)
with right:
    ui.chart_card("Comparativo de animais com e sem nome", fig_nome,
                  wide_nome.rename_axis("Nome").reset_index(), caption=cap_nome)

left, right = st.columns(2)
with left:
    card_or_info("Adoções por raça", fig_breed, t_breed, note=note_rank,
                 caption="Raça principal registrada. Raças mistas contam pela primeira raça. “SRD” = sem raça definida (a grande maioria dos gatos).")
with right:
    card_or_info("Adoções por pelagem", fig_coat, t_coat, note=note_rank,
                 caption="Pelagem = cor ou padrão registrado no abrigo.")

with st.expander("Como interpretar (leia antes de concluir)"):
    st.markdown(
        "- **Associação não é causalidade.** Idade, castração, raça e nome se misturam: filhotes não são castrados, "
        "muitos animais sem nome são transferidos logo na entrada, etc.\n"
        "- **Grupos pequenos são instáveis.** Use o controle de mínimo de desfechos ao comparar taxas.\n"
        "- **Cada linha é um desfecho**, não um animal; a taxa de adoção é adoções ÷ desfechos do grupo.\n"
        "- Perguntas respondidas aqui: 3 (idade), 4 (castração), 5 (macho × fêmea) e 7 (com nome × sem nome).")
