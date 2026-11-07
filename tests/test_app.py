"""Testes: a base está íntegra, cada página roda sem exceções e o filtro de espécie bate com a base."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "aac_shelter_outcomes_clean.csv"
PAGES = ["views/visao_geral.py", "views/perfil_adocao.py", "views/sazonalidade.py"]


@pytest.fixture(scope="module")
def base() -> pd.DataFrame:
    return pd.read_csv(CSV, encoding="utf-8-sig", keep_default_na=False, low_memory=False)


def test_base_integra(base):
    assert len(base) == 78246
    assert base["outcome_type"].ne("").all()
    assert not base.duplicated(["animal_id", "datetime"]).any()
    assert base["animal_type"].value_counts().to_dict() == {
        "Dog": 44240, "Cat": 29415, "Other": 4248, "Bird": 334, "Livestock": 9}


def _run(page: str | None = None) -> AppTest:
    at = AppTest.from_file(str(ROOT / (page or "app.py")), default_timeout=120)
    at.run()
    return at


def test_app_inicial_sem_excecoes():
    assert not _run().exception


@pytest.mark.parametrize("page", PAGES)
def test_paginas_sem_excecoes(page):
    assert not _run(page).exception


@pytest.mark.parametrize("especies", [["Gatos"], ["Cães"], ["Aves"], ["Gatos", "Cães"], ["Animais de fazenda"]])
def test_filtro_especie_sem_excecoes(especies):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.sidebar.multiselect[0].set_value(especies).run()
    assert not at.exception


def test_filtro_gatos_confere_com_a_base(base):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.sidebar.multiselect[0].set_value(["Gatos"]).run()
    gatos = base[base["animal_type"] == "Cat"]
    texto = " ".join(c.value for c in at.sidebar.caption)
    esperado = f"{len(gatos):,}".replace(",", ".")
    assert esperado in texto
    # o KPI "Total de adoções" da página 1 deve ser o número de adoções de gatos
    adocoes = int((gatos["outcome_type"] == "Adoption").sum())
    valores = [m.value for m in at.metric]
    assert f"{adocoes:,}".replace(",", ".") in valores
