"""#2988 S4 (AC-18): die alten Paritaets-Fixtures laufen als Regressionsfixtures gegen den Endpunkt.

SPEC: docs/specs/modules/rework_2988_ampel_ableitung.md, AC-18 und Abschnitt „S4 – Uebersichten".

Nach S4 gibt es im Frontend keinen Spiegel der Aufloesung mehr; ``ampel_deviation_cases.json`` und
``ampel_auswahl_paritaet.json`` pruefen deshalb nicht mehr „Python gleich Frontend", sondern den einzigen
Ort der Aufloesung: ``POST /api/ampel/aufloesung`` (echter Router, FastAPI-TestClient, kein Mock, ohne Netz).

- ``ampel_deviation_cases.json``: je Fall die Zahl der Metriken (plus Gewitter einmal), deren aufgeloeste
  Zeile von der Vorlagen-Zeile aus ``GET /api/templates`` abweicht, gleich ``expected``.
- ``ampel_auswahl_paritaet.json``: Vorlagen-Ampel und Menge aktiver Metriken je Vorlage und je Fall.
- Metadaten beider Fixtures nennen nur Leser, die es gibt und die die Fixture wirklich lesen, und nur
  Python-Funktionen, die es gibt (heute: ``test_2794_ac28_abweichungszaehler.py`` und
  ``app.ampel.deviation_count`` gibt es nicht; ``ampelModell.ts`` liest die Fixture nicht).

    uv run pytest tests/tdd/test_2988_s4_regressionsfixtures.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.ampel as ampel_modul
from app.ampel import resolve_ampel

PFAD = "/api/ampel/aufloesung"
NUTZER = "p2988-s4"
REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
DIESE_DATEI = "tests/tdd/test_2988_s4_regressionsfixtures.py"

ABWEICHUNG = json.loads((FIXTURES / "ampel_deviation_cases.json").read_text(encoding="utf-8"))
AUSWAHL = json.loads((FIXTURES / "ampel_auswahl_paritaet.json").read_text(encoding="utf-8"))

#: Zeile ohne Vorlagen-Eintrag (so legt die Aufloesung sie an).
_LEER = {"enabled": False, "lower": {}, "upper": {}, "alarm_ab": "never"}


@pytest.fixture
def client():
    from api.routers import ampel_aufloesung

    anwendung = FastAPI()
    anwendung.include_router(ampel_aufloesung.router)
    return TestClient(anwendung, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def vorlagen() -> dict:
    from api.routers.config import get_templates

    return {t["id"]: t["ampel"] for t in get_templates()}


def _loese(client, eintraege: list[dict]) -> list[dict]:
    antwort = client.post(PFAD, params={"user_id": NUTZER}, json={"eintraege": eintraege})
    assert antwort.status_code == 200, antwort.text
    ergebnisse = antwort.json()["ergebnisse"]
    assert len(ergebnisse) == len(eintraege)
    return ergebnisse


def _zeile(z: dict | None) -> tuple:
    """Vergleichsform einer Zeile: offene (null) Grenzen zaehlen nicht, fehlender Modus = „aus"."""
    z = {**_LEER, **(z or {})}
    seite = lambda s: {k: v for k, v in (s or {}).items() if v is not None}  # noqa: E731
    return (bool(z.get("enabled")), seite(z.get("lower")), seite(z.get("upper")),
            z.get("alarm_ab") or "never", z.get("modus") or "aus", sorted(z.get("sektoren") or []))


def _abweichende(vorlage: dict, aufgeloest: dict) -> int:
    ids = set(vorlage["metrics"]) | set(aufgeloest["metrics"])
    n = sum(1 for i in ids if _zeile(vorlage["metrics"].get(i)) != _zeile(aufgeloest["metrics"].get(i)))
    return n + (1 if (vorlage.get("thunder") or {}) != (aufgeloest.get("thunder") or {}) else 0)


def _aktiv(ampel: dict) -> set[str]:
    return {mid for mid, e in ampel["metrics"].items() if e.get("enabled")}


# --- ampel_deviation_cases.json ---------------------------------------------------------------


def test_abweichungsfaelle_vorhanden():
    assert len(ABWEICHUNG["cases"]) >= 22, "Fixture verloren (Spec AC-2: 22 Faelle)"


@pytest.mark.parametrize("fall", ABWEICHUNG["cases"], ids=lambda f: f["name"])
def test_abweichungsfall_am_endpunkt(client, vorlagen, fall):
    """Die Aufloesung des Endpunkts weicht in genau ``expected`` Metriken (Gewitter einmal) von ihrer
    Vorlage ab und ist gleich der Aufloesung der vier Kanaele (``resolve_ampel``)."""
    e = _loese(client, [{"ampel": fall["ampel"]}])[0]
    assert e["ampel"] == resolve_ampel({"display_config": {"ampel": fall["ampel"]}})
    vorlage = (fall["ampel"] or {}).get("template") or "allgemein"
    assert e["vorlage_id"] == vorlage
    assert _abweichende(vorlagen[vorlage], e["ampel"]) == fall["expected"]


def test_abweichungsfaelle_in_einem_aufruf(client, vorlagen):
    """Bis 32 Faelle in einem Aufruf: dieselben Zahlen, Reihenfolge erhalten."""
    faelle = ABWEICHUNG["cases"][:32]
    ergebnisse = _loese(client, [{"ampel": f["ampel"]} for f in faelle])
    assert [_abweichende(vorlagen[e["vorlage_id"]], e["ampel"]) for e in ergebnisse] == [
        f["expected"] for f in faelle]


# --- ampel_auswahl_paritaet.json --------------------------------------------------------------


@pytest.mark.parametrize("tid", sorted(AUSWAHL["vorlagen"]))
def test_auswahl_je_vorlage_am_endpunkt(client, vorlagen, tid):
    e = _loese(client, [{"ampel": {"template": tid}}])[0]
    assert e["vorlage_id"] == tid
    assert e["ampel"] == AUSWAHL["vorlagen"][tid]["ampel"] == vorlagen[tid]
    assert _aktiv(e["ampel"]) == set(AUSWAHL["vorlagen"][tid]["aktiv"])


@pytest.mark.parametrize("fall", AUSWAHL["faelle"], ids=lambda f: f["name"])
def test_auswahl_je_fall_am_endpunkt(client, fall):
    e = _loese(client, [{"ampel": fall["ampel"]}])[0]
    assert _aktiv(e["ampel"]) == set(fall["aktiv"])


# --- Metadaten der Fixtures (doc-compliance-test: Leser in den Metadaten, Ausnahme vom
# Dateiinhalt-Verbot wie der Vertragswaechter) ---------------------------------------------


_DATEI = re.compile(r"[\w./-]+\.(?:py|ts)\b")
_FUNKTION = re.compile(r"app\.ampel\.(\w+)")


def _finde(name: str) -> Path | None:
    if (REPO / name).is_file():
        return REPO / name
    treffer = [p for p in REPO.glob(f"**/{Path(name).name}")
               if "node_modules" not in p.parts and p.as_posix().endswith(name)]
    return treffer[0] if treffer else None


@pytest.mark.parametrize(("fixture", "schluessel"), [
    ("ampel_deviation_cases.json", "_issue"),
    ("ampel_auswahl_paritaet.json", "_format"),
])
def test_metadaten_nennen_echte_leser(fixture, schluessel):  # doc-compliance-test
    """Jede genannte Datei gibt es und liest die Fixture; jede genannte ``app.ampel``-Funktion gibt es;
    dieser Regressionstest ist als Leser genannt."""
    text = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))[schluessel]
    genannt = _DATEI.findall(text)
    assert DIESE_DATEI in genannt, f"{fixture}: {DIESE_DATEI} fehlt als Leser in {schluessel}"
    for name in genannt:
        pfad = _finde(name)
        assert pfad is not None, f"{fixture}: genannter Leser {name} existiert nicht"
        assert fixture in pfad.read_text(encoding="utf-8"), f"{fixture}: {name} liest die Fixture nicht"
    for funktion in _FUNKTION.findall(text):
        assert hasattr(ampel_modul, funktion), f"{fixture}: app.ampel.{funktion} gibt es nicht"
