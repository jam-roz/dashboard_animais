#!/usr/bin/env python3
"""
clean_dataset.py (v2) - Limpeza dos desfechos de animais do Austin Animal Center (AAC), todas as espécies.

Uso:
    python3 -I clean_dataset.py ENTRADA.csv [-o SAIDA.csv] [--report RELATORIO.md]

Entrada: CSV com as 12 colunas brutas do AAC
    age_upon_outcome, animal_id, animal_type, breed, color, date_of_birth, datetime,
    monthyear, name, outcome_subtype, outcome_type, sex_upon_outcome
(colunas extras, como as derivadas do dataset de gatos, são ignoradas e recalculadas aqui,
 com a mesma regra para todas as espécies.)

Gera:
    * um CSV limpo (UTF-8 com BOM, pronto para Excel / Power BI / dashboard)
    * um relatório em Markdown com tudo que foi encontrado e corrigido

Todas as correções são registradas com a contagem de linhas afetadas.
O script falha (exit code 1) se alguma validação final não passar.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
UNKNOWN = "Unknown"
NOT_SPECIFIED = "Not specified"
PLACEHOLDER_TIMES = {"00:00:00", "09:00:00"}  # volume anômalo (lote/placeholder)
YOUNG_MAX_DAYS = 182                          # filhote = até ~6 meses (mesma regra da base de gatos)

BASE_COLS = ["age_upon_outcome", "animal_id", "animal_type", "breed", "color", "date_of_birth",
             "datetime", "monthyear", "name", "outcome_subtype", "outcome_type", "sex_upon_outcome"]
ANIMAL_TYPES = {"Cat", "Dog", "Other", "Bird", "Livestock"}

SEX_MAP = {"Spayed Female": "Female", "Intact Female": "Female",
           "Neutered Male": "Male", "Intact Male": "Male", "Unknown": UNKNOWN}
SPAY_MAP = {"Spayed Female": "Yes", "Neutered Male": "Yes",
            "Intact Female": "No", "Intact Male": "No", "Unknown": UNKNOWN}

# Termos de padrão de pelagem separados da cor-base (o restante fica na cor: 'blue merle', 'lynx'...)
COAT_PATTERNS = ["tabby", "tortie", "torbie", "calico", "point", "smoke", "brindle", "tick"]

FINAL_COLUMNS = [
    "animal_id", "animal_type", "name", "has_name", "name_assigned_by_shelter",
    "datetime", "outcome_date", "monthyear", "outcome_year", "outcome_month",
    "outcome_weekday", "outcome_hour", "outcome_time_unreliable", "outcome_type", "outcome_subtype",
    "date_of_birth", "dob_year", "dob_month", "dob_monthyear", "dob_invalid",
    "age_upon_outcome", "age_days", "age_years", "age_group", "age_group_order", "life_stage",
    "sex_upon_outcome", "sex", "spay_neuter",
    "breed", "breed1", "breed2", "is_mix",
    "color", "color1", "color2", "coat", "coat_pattern",
]
DOB_DEPENDENT = ["date_of_birth", "age_upon_outcome", "age_days", "age_years",
                 "dob_year", "dob_month", "dob_monthyear", "age_group_order"]

LOG = []  # (verificação, linhas afetadas, ação)


def log(check, rows, action):
    LOG.append((check, int(rows), action))


# --------------------------------------------------------------------------- #
# Limpeza
# --------------------------------------------------------------------------- #
def clean(raw):
    missing = [c for c in BASE_COLS if c not in raw.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")
    extra = [c for c in raw.columns if c not in BASE_COLS]
    if extra:
        log("Colunas extras na entrada (derivadas do dataset original)", len(extra),
            "ignoradas; tudo é recalculado a partir das 12 colunas brutas, com a mesma regra para todas as espécies")
    df = raw[BASE_COLS].copy()
    n_raw = len(df)

    # 1. Texto: espaços, vazios e a string 'NULL' ----------------------------------
    for col in df.columns:
        s = df[col].astype("string")
        after = s.str.strip().str.replace(r"\s+", " ", regex=True)
        n_space = int((s.notna() & (s != after)).sum())
        if n_space:
            log(f"Espaços sobrando em `{col}`", n_space, "strip + colapso de espaços")
        n_null = int((after == "NULL").sum())
        if n_null:
            log(f"Texto 'NULL' em `{col}`", n_null, "convertido para nulo de verdade")
        after = after.mask((after == "") | (after == "NULL"))
        df[col] = after.astype(object).where(after.notna(), np.nan)

    # 2. Duplicatas exatas -----------------------------------------------------------
    dups = df.duplicated(keep="first")
    if dups.any():
        log("Linhas 100% duplicadas", dups.sum(), "removidas (mantida a primeira ocorrência)")
        df = df.loc[~dups].reset_index(drop=True)

    # 3. Espécie ---------------------------------------------------------------------
    bad_type = ~df["animal_type"].isin(ANIMAL_TYPES)
    if bad_type.any():
        raise ValueError(f"animal_type inesperado: {sorted(df.loc[bad_type, 'animal_type'].dropna().unique())}")

    # 4. Datas ----------------------------------------------------------------------
    dt = pd.to_datetime(df["datetime"], errors="coerce")
    if dt.isna().any():
        raise ValueError(f"{int(dt.isna().sum())} valores de `datetime` inválidos - não é possível continuar")
    dob = pd.to_datetime(df["date_of_birth"], errors="coerce")
    bad_dob = dob.isna() | (dob > dt.dt.normalize())
    df["dob_invalid"] = bad_dob
    if bad_dob.any():
        log("Data de nascimento ausente/posterior ao desfecho", bad_dob.sum(),
            "nascimento e tudo que deriva dele (idade, faixa etária, filhote/adulto) viram nulo/Unknown; linha mantida e marcada em `dob_invalid`")
    dob = dob.mask(bad_dob)

    df["dob_year"] = dob.dt.year.astype("Int64")
    df["dob_month"] = dob.dt.month.astype("Int64")
    df["dob_monthyear"] = dob.dt.strftime("%Y-%m")
    df["outcome_year"] = dt.dt.year.astype("Int64")
    df["outcome_month"] = dt.dt.month.astype("Int64")
    df["outcome_hour"] = dt.dt.hour.astype("Int64")
    df["outcome_weekday"] = dt.dt.day_name()
    df["outcome_date"] = dt.dt.strftime("%Y-%m-%d")
    if (raw["monthyear"].astype(str).str.strip() == raw["datetime"].astype(str).str.strip()).all():
        log("`monthyear` era um duplicado do datetime completo", len(df),
            "agora é o 1º dia do mês (AAAA-MM-01) - agrega corretamente por mês")
    df["monthyear"] = dt.dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-%d")
    df["datetime"] = dt.dt.strftime("%Y-%m-%d %H:%M:%S")
    df["date_of_birth"] = dob.dt.strftime("%Y-%m-%d")

    df["outcome_time_unreliable"] = dt.dt.strftime("%H:%M:%S").isin(PLACEHOLDER_TIMES)
    log("Horário do desfecho exatamente 00:00:00 ou 09:00:00 (volume anômalo)", df["outcome_time_unreliable"].sum(),
        "mantido, mas marcado em `outcome_time_unreliable` - filtre ao analisar por hora do dia")

    # 5. Idade -----------------------------------------------------------------------
    days = (dt.dt.normalize() - dob).dt.days
    df["age_days"] = days.astype("Int64")
    df["age_years"] = (days / 365.25).round(2)

    label = df["age_upon_outcome"]
    fixed = label.str.replace(r"^1 (\w+?)s$", r"1 \1", regex=True)
    n = int((label.notna() & (label != fixed)).sum())
    if n:
        log("Plural errado em `age_upon_outcome` ('1 weeks')", n, "corrigido para singular")
    label = fixed
    zero_years = (label == "0 years") & ~bad_dob
    if zero_years.any():
        log("'0 years' em `age_upon_outcome` (animais com 0 dias)", zero_years.sum(), "rótulo -> '0 days'")
        label = label.mask(zero_years, "0 days")
    n_nolabel = int((label.isna() & ~bad_dob).sum())
    if n_nolabel:
        log("`age_upon_outcome` nulo com nascimento válido", n_nolabel,
            "rótulo mantido nulo; a idade exata está em `age_days` / `age_years`")
    df["age_upon_outcome"] = label

    # faixa etária de 2 em 2 anos (a base de gatos usava intervalos ilegíveis, ex.: '(-0.022, 2.2]')
    g = (np.floor(df["age_years"] / 2) * 2)
    df["age_group"] = g.map(lambda v: UNKNOWN if pd.isna(v) else f"{int(v)}-{int(v) + 1} yrs")
    df["age_group_order"] = (g // 2 + 1).astype("Int64")
    df["life_stage"] = np.where(df["age_days"].isna(), UNKNOWN,
                                np.where(df["age_days"].fillna(0) <= YOUNG_MAX_DAYS, "Young", "Adult"))
    log("Faixa etária e filhote/adulto derivados da idade exata", len(df),
        f"`age_group` em faixas de 2 anos ('0-1 yrs'...) + `age_group_order`; `life_stage` = Young se idade <= {YOUNG_MAX_DAYS} dias")

    for col in DOB_DEPENDENT:
        df[col] = df[col].mask(bad_dob)
    df["age_group"] = df["age_group"].mask(bad_dob, UNKNOWN)
    df["life_stage"] = df["life_stage"].mask(bad_dob, UNKNOWN)
    for col in ["age_days", "dob_year", "dob_month", "age_group_order"]:
        df[col] = df[col].astype("Int64")

    # 6. Sexo / castração -------------------------------------------------------------
    sex_up = df["sex_upon_outcome"]
    n_null = int(sex_up.isna().sum())
    if n_null:
        log("`sex_upon_outcome` nulo ('NULL')", n_null, "preenchido com 'Unknown'")
    sex_up = sex_up.fillna(UNKNOWN)
    unexpected = ~sex_up.isin(SEX_MAP)
    if unexpected.any():
        raise ValueError(f"Valores inesperados em sex_upon_outcome: {sorted(sex_up[unexpected].unique())}")
    df["sex_upon_outcome"] = sex_up
    df["sex"], df["spay_neuter"] = sex_up.map(SEX_MAP), sex_up.map(SPAY_MAP)
    log("`sex` e `spay_neuter` derivados de `sex_upon_outcome`", len(df), "Female/Male e Yes/No; Unknown permanece Unknown")

    # 7. Desfecho ---------------------------------------------------------------------
    ot = df["outcome_type"].replace({"Rto-Adopt": "RTO-Adopt"})
    n = int((df["outcome_type"] == "Rto-Adopt").sum())
    if n:
        log("Capitalização inconsistente: 'Rto-Adopt' (sigla)", n, "padronizado para 'RTO-Adopt'")
    n_ot_null = int(ot.isna().sum())
    if n_ot_null:
        log("`outcome_type` nulo", n_ot_null, "preenchido com 'Unknown' (lote sem desfecho registrado)")
    df["outcome_type"] = ot.fillna(UNKNOWN)

    sub = df["outcome_subtype"].replace({"Snr": "SNR"})
    log("`outcome_subtype` nulo (sem subtipo)", sub.isna().sum(), f"preenchido com '{NOT_SPECIFIED}' (facilita filtros)")
    df["outcome_subtype"] = sub.fillna(NOT_SPECIFIED)

    # 8. Nome ---------------------------------------------------------------------------
    name = df["name"]
    star = name.str.startswith("*").fillna(False).astype(bool)
    name = name.str.lstrip("*").str.strip().mask(lambda s: s == "")
    placeholder = name.str.fullmatch(r"[A-Za-z]").fillna(False).astype(bool) | \
        name.str.lower().isin(["no name", "unknown", "unnamed", "noname"])
    if placeholder.any():
        log("Nomes placeholder ('X', 'U', 'No Name')", placeholder.sum(), "convertidos para nulo")
    name = name.mask(placeholder)
    allcaps = name.str.isupper().fillna(False).astype(bool) & (name.str.len() > 3)
    if allcaps.any():
        log("Nomes em CAIXA ALTA", allcaps.sum(), "convertidos para Title Case")
        name = name.mask(allcaps, name.str.title())
    star &= name.notna()
    log("Prefixo '*' no nome (convenção do AAC: nome dado pelo abrigo)", star.sum(),
        "asterisco removido; informação preservada em `name_assigned_by_shelter`")
    df["name"], df["name_assigned_by_shelter"], df["has_name"] = name, star, name.notna()

    # 9. Raça -----------------------------------------------------------------------------
    b = df["breed"].str.lower().str.replace("black/tan hound", "black-tan hound", regex=False)  # '/' faz parte do nome
    is_mix = b.str.endswith(" mix") | b.str.contains("/")
    core = b.str.replace(r" mix$", "", regex=True).str.split("/", n=1, expand=True)
    b1, b2 = core[0], (core[1] if core.shape[1] > 1 else pd.Series(np.nan, index=df.index))
    same = b2.notna() & (b1 == b2)
    if same.any():
        log("Raça mista com a mesma raça nas duas posições (ex.: 'x/x')", same.sum(), "breed2 -> nulo")
    b2 = b2.mask(same)
    fix = lambda s: s.str.replace("black-tan hound", "black/tan hound", regex=False)
    b1, b2 = fix(b1), fix(b2)
    df["breed1"], df["breed2"] = b1, b2
    df["breed"] = b1.where(b2.isna(), b1 + "/" + b2)
    df["is_mix"] = is_mix
    log("Raça normalizada", len(df),
        "minúsculas, sufixo 'Mix' removido e guardado em `is_mix`, mistura 'a/b' separada em `breed1`/`breed2`")

    # 10. Cor / pelagem ---------------------------------------------------------------------
    color = df["color"].str.lower().str.replace(r"\s*/\s*", "/", regex=True)
    parts = color.str.split("/", n=1, expand=True)
    c1, c2 = parts[0], (parts[1] if parts.shape[1] > 1 else pd.Series(np.nan, index=df.index))
    df["color"], df["color1"], df["color2"] = color, c1, c2

    pat_re = "|".join(COAT_PATTERNS)
    first_pat = color.str.extract(rf"\b({pat_re})\b", expand=False)
    base = c1.str.replace(rf"\b({pat_re})\b", "", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    c1_pat = c1.str.extract(rf"\b({pat_re})\b", expand=False)
    df["coat"] = base.mask(base == "", c1_pat)
    df["coat_pattern"] = first_pat.fillna(NOT_SPECIFIED)
    log("Cor separada em cor-base e padrão", len(df),
        "`color1`/`color2` (antes/depois da '/'), `coat` (cor-base: 'brown tabby' -> 'brown') e `coat_pattern` ('tabby', 'brindle'...)")

    return df[FINAL_COLUMNS], n_raw


# --------------------------------------------------------------------------- #
# Validação final
# --------------------------------------------------------------------------- #
def validate(df, n_raw, n_dups):
    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    check(len(df) == n_raw - n_dups, "contagem de linhas inesperada")
    check(not df.duplicated().any(), "ainda há linhas duplicadas")
    check(not df.duplicated(["animal_id", "datetime"]).any(), "animal_id + datetime não é único")
    check(df["animal_id"].str.fullmatch(r"A\d{6}").all(), "animal_id fora do padrão A######")
    check((df.groupby("animal_id")["animal_type"].nunique() == 1).all(), "animal_id com mais de uma espécie")
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            s = df[col].dropna().astype(str)
            check((s == s.str.strip()).all(), f"espaços nas pontas em {col}")
            check(not s.str.contains(r"\s{2,}").any(), f"espaços duplicados em {col}")
            check(not (s == "NULL").any(), f"'NULL' em {col}")
    dtc, dobc = pd.to_datetime(df["datetime"]), pd.to_datetime(df["date_of_birth"])
    check((dobc.dropna() <= dtc[dobc.notna()].dt.normalize()).all(), "nascimento posterior ao desfecho")
    check((df["age_days"].dropna() >= 0).all(), "idade negativa")
    check(df["age_years"].dropna().between(0, 30).all(), "idade fora de 0-30 anos")
    check((df["sex"] == df["sex_upon_outcome"].map(SEX_MAP)).all(), "sex inconsistente")
    check((df["spay_neuter"] == df["sex_upon_outcome"].map(SPAY_MAP)).all(), "spay_neuter inconsistente")
    check(df["outcome_type"].notna().all() and df["outcome_subtype"].notna().all(), "nulos em outcome_type/subtype")
    check((df["dob_invalid"] == df["date_of_birth"].isna()).all(), "dob_invalid inconsistente")
    check((df["life_stage"].eq(UNKNOWN) == df["dob_invalid"]).all(), "life_stage inconsistente com dob_invalid")
    check(((df["life_stage"] == "Young") == (df["age_days"] <= YOUNG_MAX_DAYS).fillna(False)).all(), "life_stage x age_days")
    check(df["breed1"].notna().all(), "breed1 nulo")
    check((df["breed1"] != df["breed2"]).all(), "breed1 == breed2")
    check(df["color1"].notna().all() and df["coat"].notna().all(), "cor/pelagem nula")
    check(not df["color"].str.contains(r"^/|/$|\s/|/\s").any(), "color mal formatada")
    check(df["age_group"].eq(UNKNOWN).sum() == df["dob_invalid"].sum(), "age_group inconsistente")
    return errors


# --------------------------------------------------------------------------- #
# Relatório
# --------------------------------------------------------------------------- #
def write_report(path, raw, df, n_dups, errors):
    L = ["# Relatório de qualidade e limpeza - AAC Shelter Outcomes (todas as espécies)", ""]
    L += ["## Resumo", "",
          f"- Linhas de entrada: **{len(raw):,}** -> saída: **{len(df):,}** ({n_dups} duplicatas removidas)",
          f"- Colunas de entrada: **{raw.shape[1]}** -> saída: **{df.shape[1]}**",
          f"- Período dos desfechos: **{df['datetime'].min()[:10]}** a **{df['datetime'].max()[:10]}**",
          f"- Animais distintos: **{df['animal_id'].nunique():,}** (um mesmo animal pode ter mais de um desfecho)",
          f"- Validações finais: **{'todas OK' if not errors else 'FALHARAM: ' + '; '.join(errors)}**", ""]
    L += ["## Linhas por espécie", "", "| Espécie | Desfechos | % |", "|---|---:|---:|"]
    for sp, n in df["animal_type"].value_counts().items():
        L.append(f"| {sp} | {n:,} | {n / len(df) * 100:.1f}% |")
    L.append("")
    L += ["## Problemas encontrados e ações", "", "| # | Problema | Linhas afetadas | Ação |", "|---|---|---:|---|"]
    for i, (chk, n, act) in enumerate(LOG, 1):
        L.append(f"| {i} | {chk} | {n:,} | {act} |")
    L.append("")
    L += ["## Nulos restantes (todos esperados)", "", "| Coluna | Nulos | % | Motivo |", "|---|---:|---:|---|"]
    reasons = {"name": "animais sem nome registrado (use `has_name`)", "breed2": "só existe em raças mistas 'a/b'",
               "color2": "animais de uma cor só", "age_upon_outcome": "rótulo ausente na origem ('NULL') ou nascimento inválido; use `age_days`"}
    nulls = df.isna().sum()
    for col, n in nulls[nulls > 0].items():
        L.append(f"| `{col}` | {n:,} | {n / len(df) * 100:.2f}% | {reasons.get(col, 'consequência de nascimento inválido (`dob_invalid`)')} |")
    L.append("")
    L += ["## Pontos de atenção para o dashboard", "",
          "- **Último mês incompleto:** a base termina no início de fevereiro/2018 - o mês tem poucos registros e distorce séries temporais.",
          "- **Hora do dia:** use `outcome_time_unreliable = False` em gráficos por hora (00:00 e 09:00 aparecem em volume anômalo).",
          "- **Granularidade:** cada linha é um *desfecho*, não um animal. Para contar animais use `COUNT DISTINCT animal_id`.",
          "- **Espécies não são comparáveis sem cuidado:** sexo 'Unknown' é raro em cães (~0,5%) e comum em gatos (~9%) e outros animais (~85%); transferências e devoluções ao tutor têm pesos muito diferentes entre espécies.",
          "- **Filhote:** `life_stage = Young` = até 182 dias (~6 meses), regra herdada da base de gatos; para cães, muitos filhotes de 6 a 12 meses contam como adultos.",
          "- **Idade:** use `age_days` / `age_years` (exatas); `age_group` tem faixas de 2 anos e `age_group_order` dá a ordem.", ""]
    L += ["## Dicionário das colunas derivadas", "", "| Coluna | Descrição |", "|---|---|",
          "| `has_name`, `name_assigned_by_shelter` | tem nome; nome começava com `*` (dado pelo abrigo) |",
          "| `outcome_date`, `monthyear` | data do desfecho; 1º dia do mês do desfecho |",
          "| `outcome_time_unreliable` | horário 00:00:00 ou 09:00:00 exato |",
          "| `dob_year`, `dob_month`, `dob_monthyear`, `dob_invalid` | partes do nascimento; nascimento ausente ou posterior ao desfecho |",
          "| `age_days`, `age_years` | idade exata no desfecho |",
          "| `age_group`, `age_group_order`, `life_stage` | faixa etária (2 anos), ordem e filhote (Young) / adulto (Adult) |",
          "| `sex`, `spay_neuter` | derivados de `sex_upon_outcome` |",
          "| `breed1`, `breed2`, `is_mix` | raças separadas (minúsculas) e indicador de mistura |",
          "| `color1`, `color2`, `coat`, `coat_pattern` | cores, cor-base e padrão (tabby, brindle, ...) |", ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Limpeza dos desfechos do AAC (todas as espécies)")
    ap.add_argument("input", help="CSV de entrada")
    ap.add_argument("-o", "--output", help="CSV de saída (padrão: <entrada>_clean.csv)")
    ap.add_argument("--report", help="Relatório .md (padrão: <entrada>_quality_report.md)")
    args = ap.parse_args()

    src = Path(args.input)
    out = Path(args.output) if args.output else src.with_name(src.stem + "_clean.csv")
    rep = Path(args.report) if args.report else src.with_name(src.stem + "_quality_report.md")

    raw = pd.read_csv(src, keep_default_na=False, na_values=[""], low_memory=False)
    base = raw[[c for c in BASE_COLS if c in raw.columns]].apply(
        lambda s: s.astype("string").str.strip().replace({"": pd.NA, "NULL": pd.NA}))
    n_dups = int(base.duplicated().sum())
    df, n_raw = clean(raw)
    errors = validate(df, n_raw, n_dups)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    write_report(rep, raw, df, n_dups, errors)

    print(f"Entrada : {len(raw):,} linhas x {raw.shape[1]} colunas")
    print(f"Saída   : {len(df):,} linhas x {df.shape[1]} colunas -> {out}")
    print(f"Relatório: {rep}\n")
    for chk, n, act in LOG:
        print(f"  [{n:>6,}] {chk}")
    if errors:
        print("\nVALIDAÇÕES FALHARAM:", *errors, sep="\n  - ")
        sys.exit(1)
    print("\nTodas as validações finais passaram.")


if __name__ == "__main__":
    main()
