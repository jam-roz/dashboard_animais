"""Agregações e KPIs (funções puras sobre DataFrames já filtrados)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import OUTCOME_GROUPS


def safe_div(a, b) -> float:
    return a / b if b else float("nan")


def kpis_geral(df: pd.DataFrame) -> dict:
    n = len(df)
    adocoes = int(df["is_adocao"].sum())
    return {
        "desfechos": n,
        "animais": int(df["animal_id"].nunique()),
        "adocoes": adocoes,
        "taxa_adocao": safe_div(adocoes, n),
        "transferencias": int(df["is_transferencia"].sum()),
        "obitos": int((df["desfecho"] == "Óbito").sum()),
        "eutanasias": int((df["desfecho"] == "Eutanásia").sum()),
        "obitos_euta": int(df["is_obito_euta"].sum()),
    }


def kpis_perfil(df: pd.DataFrame) -> dict:
    fase_ok = df[df["fase"] != "Desconhecido"]
    cast_ok = df[df["castracao"] != "Desconhecido"]
    idade = df["age_years"].dropna()
    return {
        "pct_filhotes": safe_div((fase_ok["fase"] == "Filhote").sum(), len(fase_ok)),
        "pct_castracao": safe_div((cast_ok["castracao"] == "Castrado(a)").sum(), len(cast_ok)),
        "n_cast_desconhecido": int((df["castracao"] == "Desconhecido").sum()),
        "idade_media": float(idade.mean()) if len(idade) else float("nan"),
        "idade_mediana": float(idade.median()) if len(idade) else float("nan"),
    }


def outcome_wide(df: pd.DataFrame, col: str, order: list | None = None) -> pd.DataFrame:
    """Contagem de desfechos (colunas = grupos de desfecho) por categoria de `col`."""
    wide = df.groupby([col, "desfecho_grupo"], observed=True).size().unstack(fill_value=0)
    wide = wide.reindex(columns=OUTCOME_GROUPS, fill_value=0)
    if order is not None:
        wide = wide.reindex(order, fill_value=0)
    wide.index = wide.index.astype(str)
    return wide


def group_rates(df: pd.DataFrame, col: str, order: list | None = None) -> pd.DataFrame:
    """Volume, adoções, óbitos+eutanásias e taxas por categoria de `col`."""
    g = df.groupby(col, observed=True)
    out = pd.DataFrame({
        "desfechos": g.size(),
        "adocoes": g["is_adocao"].sum(),
        "obitos_euta": g["is_obito_euta"].sum(),
    })
    out["taxa_adocao"] = out["adocoes"] / out["desfechos"]
    out["taxa_obito_euta"] = out["obitos_euta"] / out["desfechos"]
    if order is not None:
        out = out.reindex([o for o in order if o in out.index])
    out.index = out.index.astype(str)
    return out.rename_axis(col).reset_index()


def monthly(df: pd.DataFrame, months: pd.DatetimeIndex, by: str | None = None):
    """Série mensal completa (meses sem registro = 0)."""
    if by is None:
        return df.groupby("mes_ano").size().reindex(months, fill_value=0)
    wide = df.groupby(["mes_ano", by], observed=True).size().unstack(fill_value=0)
    return wide.reindex(months, fill_value=0)


def yearly(df: pd.DataFrame, years: list[int], by: str | None = None):
    if by is None:
        return df.groupby("ano").size().reindex(years, fill_value=0)
    wide = df.groupby(["ano", by], observed=True).size().unstack(fill_value=0)
    return wide.reindex(years, fill_value=0)


def month_year_grid(df: pd.DataFrame, months: pd.DatetimeIndex, years: list[int],
                    numerator: str | None, rate: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Grade ano x mês. Meses fora de `months` ficam NaN.
    numerator: coluna booleana a contar (None = todos os desfechos).
    Retorna (valores, totais) — valores = contagem ou taxa (numerador / total do mês)."""
    sel = df if numerator is None else df[df[numerator]]
    num = sel.groupby("mes_ano").size().reindex(months, fill_value=0)
    tot = df.groupby("mes_ano").size().reindex(months, fill_value=0)
    val = (num / tot.replace(0, np.nan)) if rate else num.astype(float)

    def to_grid(s: pd.Series) -> pd.DataFrame:
        g = pd.DataFrame(index=years, columns=range(1, 13), dtype=float)
        for ts, v in s.items():
            g.loc[ts.year, ts.month] = v
        return g

    return to_grid(val), to_grid(tot.astype(float))
