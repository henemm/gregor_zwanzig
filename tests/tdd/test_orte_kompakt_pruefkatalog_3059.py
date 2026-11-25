"""TDD RED -- Issue #3059, AC-15: Pruefkatalog "Einstellung = Mail" kennt Kompakt fuer Orte.

SPEC: docs/specs/modules/feat_3059_orte_kompakt_mail.md (AC-15)

Fordert:

1. ``tests/fixtures/einstellung_gleich_mail/fallliste_orte.json`` fuehrt ``kompakt``
   als Format-Dimension und enthaelt Faelle mit Format ``kompakt`` fuer die
   Orte-Listen (Vergleichstabelle und Ausblick je ``auswahl`` und ``reihenfolge``;
   der Stundenverlauf mindestens einen Fall -- analog Trip, dort ``ausnahme``
   mit Verweis #722, weil Kompakt keinen Stundenverlauf zeigt).
2. Die Abdeckungsmatrix ``ABDECKUNG_SOLL`` des Fallliste-Waechters
   (``tests/tdd/test_einstellung_gleich_mail_fallliste.py``) verlangt fuer alle
   drei ``orte_*``-Listen ``kompakt`` -- wie fuer die drei ``trip_*``-Listen.
3. ``orte_soll`` (``.claude/hooks/_soll_aus_konfiguration.py``) liefert
   ``"email_format"`` genau wie ``trip_soll``: Wert aus
   ``display_config.email_format`` des Presets, fehlend = ``"full"``. Ein Feld
   an falscher Stelle (oberste Ebene, ``report_config``) wirkt nicht.

Kein Mock; reine Datenpruefung der Fallliste und Aufruf der echten Soll-Funktion.

    uv run pytest tests/tdd/test_orte_kompakt_pruefkatalog_3059.py -v
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FALLLISTE_ORTE = _ROOT / "tests" / "fixtures" / "einstellung_gleich_mail" / "fallliste_orte.json"
_ORTSNAMEN = {"golden-0": "Innsbruck", "golden-1": "Lienz", "golden-2": "Kufstein"}


def _modul(pfad: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def soll():
    return _modul(_ROOT / ".claude" / "hooks" / "_soll_aus_konfiguration.py", "_soll_aus_konfiguration_3059")


@pytest.fixture(scope="module")
def faelle_orte() -> dict:
    return json.loads(_FALLLISTE_ORTE.read_text(encoding="utf-8"))


def _formate(fall: dict) -> set[str]:
    return set(str(fall.get("format", "")).split("+"))


# --------------------------------------------------------------------------- #
# 1. Fallliste Orte
# --------------------------------------------------------------------------- #
def test_fallliste_orte_format_dimension_kennt_kompakt(faelle_orte):
    assert "kompakt" in faelle_orte["dimensionen"]["format"], (
        "fallliste_orte.json: Dimension 'format' ohne 'kompakt' -- Orte kennen seit #3059 die Kompakt-Mail"
    )


@pytest.mark.parametrize("liste", ["orte_vergleichstabelle", "orte_ausblick"])
@pytest.mark.parametrize("pruefung", ["auswahl", "reihenfolge"])
def test_fallliste_orte_kompakt_faelle_je_liste_und_pruefung(faelle_orte, liste, pruefung):
    treffer = [f for f in faelle_orte["faelle"]
               if f.get("kontext") == "orte" and f.get("liste") == liste
               and f.get("pruefung") == pruefung and "kompakt" in _formate(f)]
    assert treffer, f"fallliste_orte.json: kein Fall {liste} x kompakt x {pruefung}"


def test_fallliste_orte_kompakt_vergleichstabelle_mindestens_ein_gruener_fall(faelle_orte):
    """Die Ortszeile der Kompakt-Mail traegt die E-Mail-Auswahl: mindestens
    ein Kompakt-Fall der Vergleichstabelle ist ``gruen`` (keine Ausnahme)."""
    gruen = [f for f in faelle_orte["faelle"]
             if f.get("liste") == "orte_vergleichstabelle" and "kompakt" in _formate(f)
             and f.get("status") == "gruen"]
    assert gruen, "fallliste_orte.json: kein gruener Kompakt-Fall der Vergleichstabelle"


def test_fallliste_orte_stundenverlauf_kompakt_fall_vorhanden(faelle_orte):
    """Kompakt zeigt keinen Stundenverlauf (#722, PO #3160): mindestens ein
    Kompakt-Fall des Stundenverlaufs belegt das (Status frei, z. B. ``ausnahme``
    mit Verweis wie beim Trip)."""
    treffer = [f for f in faelle_orte["faelle"]
               if f.get("liste") == "orte_stundenverlauf" and "kompakt" in _formate(f)]
    assert treffer, "fallliste_orte.json: kein Kompakt-Fall fuer orte_stundenverlauf"


# --------------------------------------------------------------------------- #
# 2. Abdeckungsmatrix des Fallliste-Waechters
# --------------------------------------------------------------------------- #
def test_abdeckung_soll_orte_listen_mit_kompakt():
    waechter = _modul(_ROOT / "tests" / "tdd" / "test_einstellung_gleich_mail_fallliste.py",
                      "_fallliste_waechter_3059")
    for liste in ("orte_vergleichstabelle", "orte_stundenverlauf", "orte_ausblick"):
        assert "kompakt" in waechter.ABDECKUNG_SOLL[liste], (
            f"ABDECKUNG_SOLL[{liste!r}] = {waechter.ABDECKUNG_SOLL[liste]} ohne 'kompakt'"
        )


# --------------------------------------------------------------------------- #
# 3. Soll-Ermittlung orte_soll
# --------------------------------------------------------------------------- #
def _preset(**extra) -> dict:
    preset = {
        "id": "p-3059", "name": "Kompakt Orte", "kind": "vergleich",
        "location_ids": ["golden-2", "golden-0", "golden-1"],
        "display_config": {"telegram_style": "kurzform"},
    }
    preset.update(extra)
    return preset


def test_orte_soll_email_format_compact_aus_display_config(soll):
    preset = _preset(display_config={"email_format": "compact", "telegram_style": "kurzform"})
    s = soll.orte_soll(preset, "de", _ORTSNAMEN)
    assert s.get("email_format") == "compact", s.get("email_format")


def test_orte_soll_email_format_full_ausdruecklich(soll):
    s = soll.orte_soll(_preset(display_config={"email_format": "full"}), "de", _ORTSNAMEN)
    assert s.get("email_format") == "full", s.get("email_format")


def test_orte_soll_email_format_fehlt_ist_full(soll):
    """Bestand ohne Feld: ausfuehrlich (wie ``trip_soll``: ``rc.get('email_format', 'full')``)."""
    s = soll.orte_soll(_preset(), "de", _ORTSNAMEN)
    assert s.get("email_format") == "full", s.get("email_format")


@pytest.mark.parametrize("falsche_stelle", [
    {"email_format": "compact"},
    {"report_config": {"email_format": "compact"}},
])
def test_orte_soll_email_format_nur_aus_display_config(soll, falsche_stelle):
    """Orte tragen das Feld in ``display_config`` (wie ``telegram_style``); an
    anderer Stelle wirkt es nicht."""
    s = soll.orte_soll(_preset(**falsche_stelle), "de", _ORTSNAMEN)
    assert s.get("email_format") == "full", s.get("email_format")


def test_orte_soll_email_format_ueber_soll_aus_daten_huelle(soll):
    """Die Validatoren rufen ``soll_aus_daten`` mit der Huelle ``{preset, orte}``;
    auch dort kommt das Format an."""
    preset = _preset(display_config={"email_format": "compact"})
    s = soll.soll_aus_daten({"preset": preset, "orte": _ORTSNAMEN}, "de")
    assert s.get("kontext") == "orte"
    assert s.get("email_format") == "compact", s.get("email_format")
