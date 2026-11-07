"""Carga do CSV limpo e preparação das colunas de exibição (rótulos em português)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "aac_shelter_outcomes_clean.csv"

# --------------------------------------------------------------------------- #
# Dicionários de tradução
# --------------------------------------------------------------------------- #
OUTCOME_PT = {
    "Adoption": "Adoção",
    "Transfer": "Transferência",
    "Return to Owner": "Devolução ao tutor",
    "Euthanasia": "Eutanásia",
    "Died": "Óbito",
    "RTO-Adopt": "RTO-Adopt",
    "Missing": "Desaparecimento",
    "Disposal": "Descarte",
    "Relocate": "Realocação",
    "Unknown": "Não informado",
}
# Os 5 desfechos principais ganham cor própria; o restante é agrupado em "Outros"
OUTCOME_MAIN = ["Adoção", "Transferência", "Devolução ao tutor", "Eutanásia", "Óbito"]
OUTCOME_GROUPS = OUTCOME_MAIN + ["Outros"]

SEX_PT = {"Female": "Fêmea", "Male": "Macho", "Unknown": "Desconhecido"}
SPAY_PT = {"Yes": "Castrado(a)", "No": "Não castrado(a)", "Unknown": "Desconhecido"}
FASE_PT = {"Young": "Filhote", "Adult": "Adulto", "Unknown": "Desconhecido"}

# Espécie (animal_type) -> rótulo no plural, na ordem de volume
ESPECIE_PT = {"Dog": "Cães", "Cat": "Gatos", "Other": "Outros animais", "Bird": "Aves", "Livestock": "Animais de fazenda"}
ESPECIES = list(ESPECIE_PT.values())

WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
WEEKDAY_PT = dict(zip(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], WEEKDAYS))
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

BREED_PT = {
    "domestic shorthair": "SRD (pelo curto)",
    "domestic mediumhair": "SRD (pelo médio)",
    "domestic medium hair": "SRD (pelo médio)",
    "domestic longhair": "SRD (pelo longo)",
    "siamese": "Siamês",
    "american shorthair": "American Shorthair",
    "snowshoe": "Snowshoe",
    "maine coon": "Maine Coon",
    "manx": "Manx",
    "russian blue": "Azul Russo",
    "himalayan": "Himalaio",
    "persian": "Persa",
    "ragdoll": "Ragdoll",
    "bengal": "Bengal",
    "angora": "Angorá",
    "american curl shorthair": "American Curl (pelo curto)",
    "japanese bobtail": "Bobtail Japonês",
    "balinese": "Balinês",
    "british shorthair": "British Shorthair",
    "tonkinese": "Tonquinês",
    "bombay": "Bombay",
    "devon rex": "Devon Rex",
    "cymric": "Cymric",
    "turkish angora": "Angorá Turco",
    "abyssinian": "Abissínio",
    "norwegian forest cat": "Floresta da Noruega",
    "pixiebob shorthair": "Pixiebob (pelo curto)",
    "sphynx": "Sphynx",
    "exotic shorthair": "Exótico (pelo curto)",
    "cornish rex": "Cornish Rex",
    "oriental sh": "Oriental (pelo curto)",
    "munchkin shorthair": "Munchkin (pelo curto)",
    "burmese": "Birmanês",
    "turkish van": "Van Turco",
    "birman": "Sagrado da Birmânia",
    "munchkin longhair": "Munchkin (pelo longo)",
    "scottish fold": "Scottish Fold",
    "chartreux": "Chartreux",
    "javanese": "Javanês",
    "havana brown": "Havana Brown",
    "american wirehair": "American Wirehair",
    "ocicat": "Ocicat",
}

BREED_PT.update({
    # cães
    "pit bull": "Pit Bull", "chihuahua shorthair": "Chihuahua (pelo curto)", "chihuahua longhair": "Chihuahua (pelo longo)",
    "german shepherd": "Pastor Alemão", "australian cattle dog": "Cão de Gado Australiano",
    "dachshund": "Dachshund (salsicha)", "miniature poodle": "Poodle Miniatura", "siberian husky": "Husky Siberiano",
    "australian shepherd": "Pastor Australiano", "miniature schnauzer": "Schnauzer Miniatura",
    "great pyrenees": "Pastor dos Pireneus", "maltese": "Maltês", "american bulldog": "Bulldog Americano",
    "anatol shepherd": "Pastor da Anatólia", "plott hound": "Plott Hound", "black mouth cur": "Black Mouth Cur",
    # outros animais e aves
    "bat": "Morcego", "raccoon": "Guaxinim", "rabbit sh": "Coelho (pelo curto)", "rabbit lh": "Coelho (pelo longo)",
    "opossum": "Gambá", "guinea pig": "Porquinho-da-índia", "skunk": "Cangambá", "squirrel": "Esquilo", "fox": "Raposa",
    "rat": "Rato", "ferret": "Furão", "turtle": "Tartaruga", "snake": "Cobra", "lizard": "Lagarto",
    "chicken": "Galinha", "duck": "Pato", "pigeon": "Pombo", "dove": "Pomba", "parakeet": "Periquito",
})

COAT_PT = {
    "black": "Preto",
    "brown": "Marrom",
    "blue": "Azul (cinza)",
    "orange": "Laranja",
    "white": "Branco",
    "tortie": "Tartaruga (tortie)",
    "calico": "Tricolor (calico)",
    "torbie": "Torbie (tartaruga rajado)",
    "cream": "Creme",
    "lynx": "Lynx point",
    "gray": "Cinza",
    "seal": "Seal",
    "flame": "Flame",
    "silver": "Prata",
    "chocolate": "Chocolate",
    "lilac": "Lilás",
    "blue cream": "Blue cream",
    "silver lynx": "Prata lynx",
    "buff": "Bege (buff)",
    "yellow": "Amarelo",
    "brown tiger": "Marrom tigrado",
    "agouti": "Agouti",
    "tan": "Castanho-claro",
    "tricolor": "Tricolor",
    "sable": "Sable",
    "pink": "Rosa",
    "brown merle": "Marrom merle",
    "apricot": "Damasco",
    "black tiger": "Preto tigrado",
    "orange tiger": "Laranja tigrado",
    "fawn": "Fulvo",
    "red": "Vermelho",
    "gold": "Dourado",
    "liver": "Marrom-fígado",
    "blue merle": "Azul merle",
    "red merle": "Vermelho merle",
    "blue tiger": "Azul tigrado",
    "green": "Verde",
}

USECOLS = [
    "animal_id", "datetime", "monthyear", "outcome_year", "outcome_month", "outcome_weekday",
    "outcome_type", "age_years", "age_days", "age_group", "age_group_order", "life_stage",
    "sex", "spay_neuter", "has_name", "breed1", "coat", "animal_type",
]

# Faixas etárias detalhadas (a partir da idade exata em dias). As faixas originais do dataset
# de 2 em 2 anos concentram ~60% dos registros em "0-1 anos".
FAIXA_DET = ["< 2 meses", "2 a 5 meses", "6 a 11 meses", "1 a 2 anos", "3 a 5 anos", "6 a 10 anos", "11+ anos"]
_FAIXA_DET_BINS = [0, 60, 180, 365, 1095, 2190, 4018, np.inf]
AGE_SCHEMES = ["Detalhadas", "Em anos (de 2 em 2)"]


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Carregando dados…")
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, usecols=USECOLS, encoding="utf-8-sig",
                     parse_dates=["datetime", "monthyear"])

    df["mes_ano"] = df["monthyear"]
    df["ano"] = df["outcome_year"].astype(int)
    df["mes"] = df["outcome_month"].astype(int)

    df["desfecho"] = df["outcome_type"].map(OUTCOME_PT).fillna(df["outcome_type"])
    df["desfecho_grupo"] = df["desfecho"].where(df["desfecho"].isin(OUTCOME_MAIN), "Outros")
    df["is_adocao"] = df["outcome_type"].eq("Adoption")
    df["is_transferencia"] = df["outcome_type"].eq("Transfer")
    df["is_obito_euta"] = df["outcome_type"].isin(["Died", "Euthanasia"])

    df["sexo"] = df["sex"].map(SEX_PT)
    df["castracao"] = df["spay_neuter"].map(SPAY_PT)
    df["fase"] = df["life_stage"].map(FASE_PT)
    df["especie"] = df["animal_type"].map(ESPECIE_PT)
    df["nome"] = np.where(df["has_name"], "Com nome", "Sem nome")

    faixa = df["age_group"].str.replace(" yrs", " anos", regex=False)
    df["faixa_etaria"] = faixa.where(df["age_group"] != "Unknown", "Desconhecida")

    det = pd.cut(df["age_days"], bins=_FAIXA_DET_BINS, right=False, labels=FAIXA_DET)
    df["faixa_det"] = det.astype(object).fillna("Desconhecida")

    df["raca"] = df["breed1"].map(BREED_PT).fillna(df["breed1"].str.title())
    df["pelagem"] = df["coat"].map(COAT_PT).fillna(df["coat"].str.title())

    df["dia_semana"] = pd.Categorical(
        df["outcome_weekday"].map(WEEKDAY_PT), categories=WEEKDAYS, ordered=True)

    return df.drop(columns=["monthyear", "outcome_year", "outcome_month", "outcome_weekday",
                            "outcome_type", "sex", "spay_neuter", "life_stage", "animal_type",
                            "age_group", "age_days", "breed1", "coat", "has_name"])


@dataclass(frozen=True)
class Meta:
    first_month: pd.Timestamp
    last_month: pd.Timestamp
    partial_months: tuple  # meses cujo período não está completo na base
    n_rows: int


def get_meta(df: pd.DataFrame) -> Meta:
    first, last = df["datetime"].min(), df["datetime"].max()
    first_month = first.to_period("M").to_timestamp()
    last_month = last.to_period("M").to_timestamp()
    partial = []
    if first.day > 1:
        partial.append(first_month)
    month_end = last_month + pd.offsets.MonthEnd(0)
    if last.normalize() < month_end.normalize():
        partial.append(last_month)
    return Meta(first_month, last_month, tuple(partial), len(df))


def age_scheme(df: pd.DataFrame, scheme: str) -> tuple[str, list[str]]:
    """(coluna, ordem das categorias) conforme o agrupamento de idade escolhido na barra lateral."""
    if scheme == AGE_SCHEMES[1]:
        return "faixa_etaria", ordered_faixas(df)
    return "faixa_det", FAIXA_DET


def ordered_faixas(df: pd.DataFrame) -> list[str]:
    """Faixas etárias na ordem natural (0-1, 2-3, ... 24-25), sem 'Desconhecida'."""
    t = df.dropna(subset=["age_group_order"]).drop_duplicates("faixa_etaria")
    return t.sort_values("age_group_order")["faixa_etaria"].tolist()
