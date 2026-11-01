"""Drift-Schutz Hilfeseite <-> Antwort-Befehle (Onboarding S3, Issue #2521, AC-17).

Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md

Die Hilfeseite ``/hilfe`` fuehrt die Antwort-Befehle als statische Kopie im
Textkatalog ``frontend/src/lib/i18n/messages/de/hilfe.json`` (seit #2647). Einzige Quelle der
Befehle ist ``_COMMAND_SPECS`` in ``src/services/trip_command_processor.py``.
Dieser Test ruft ``command_rows()`` ECHT auf (Import, kein Quelltext-Lesen) und
vergleicht die Befehle samt Argumentform mit den Katalogeintraegen. Kommt ein
Befehl hinzu, faellt einer weg oder heisst einer anders, ohne dass der Katalog
nachgezogen wird, ist der Test rot.

Katalog-Vertrag (flache Schluessel, de.json ist ``Record<string, string>``):
    hilfe.befehle.<wort>.befehl   z. B. "PAUSE [2d / 12h]"  (= erste Spalte von command_rows())
    hilfe.befehle.<wort>.text     Beschreibung (nicht leer; Wortlaut frei, die Seite
                                  ist eine kurze Uebersicht, keine Referenz)

``de.json`` wird als DATEN gelesen (json.load), relativ zu dieser Testdatei —
nie ueber einen festen Hauptrepo-Pfad.

    uv run pytest tests/test_hilfe_befehle_drift.py --disable-socket -v -rA
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.services.trip_command_processor import command_rows

KATALOG_DATEI = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "src"
    / "lib"
    / "i18n"
    / "messages"
    / "de"
    / "hilfe.json"
)
_BEFEHL_KEY = re.compile(r"^hilfe\.befehle\.([^.]+)\.befehl$")


def _katalog() -> dict[str, str]:
    with KATALOG_DATEI.open(encoding="utf-8") as f:
        return json.load(f)


def katalog_befehle(katalog: dict[str, str]) -> dict[str, str]:
    """``{<wort>: <Befehl inkl. Argumentform>}`` aus den Katalogeintraegen."""
    return {m.group(1): wert for key, wert in katalog.items() if (m := _BEFEHL_KEY.match(key))}


def drift(quelle: list[tuple[str, str]], katalog: dict[str, str]) -> dict[str, list[str]]:
    """Unterschiede Quelle <-> Katalog; leere Listen = kein Drift."""
    soll = {befehl for befehl, _ in quelle}
    ist = set(katalog_befehle(katalog).values())
    return {"fehlt_im_katalog": sorted(soll - ist), "nur_im_katalog": sorted(ist - soll)}


def test_quelle_liefert_befehle():
    """Messaufbau: command_rows() ist die echte, nicht leere Befehlsquelle."""
    rows = command_rows()
    assert len(rows) >= 5
    assert all(befehl and beschreibung for befehl, beschreibung in rows)


def test_katalog_hat_befehlseintraege():
    assert katalog_befehle(_katalog()), (
        "de.json enthaelt keine Eintraege hilfe.befehle.<wort>.befehl — "
        "die Hilfeseite hat keinen Abschnitt Antwort-Befehle"
    )


def test_katalog_und_command_rows_stimmen_ueberein():
    """AC-17: jeder Befehl aus command_rows() steht genau so im Katalog, und umgekehrt."""
    assert drift(command_rows(), _katalog()) == {"fehlt_im_katalog": [], "nur_im_katalog": []}


def test_jeder_katalogbefehl_hat_eine_beschreibung():
    katalog = _katalog()
    ohne = [
        wort
        for wort in katalog_befehle(katalog)
        if not str(katalog.get(f"hilfe.befehle.{wort}.text", "")).strip()
    ]
    assert ohne == []


def test_schluesselwort_passt_zum_befehl():
    """``hilfe.befehle.<wort>`` traegt das kleingeschriebene erste Wort des Befehls."""
    falsch = {
        wort: befehl
        for wort, befehl in katalog_befehle(_katalog()).items()
        if befehl.split()[0].lower() != wort
    }
    assert falsch == {}


# ── Gegenproben: der Vergleich erkennt jede Drift-Art ────────────────────────
def _katalog_aus(rows: list[tuple[str, str]]) -> dict[str, str]:
    kat: dict[str, str] = {}
    for befehl, text in rows:
        wort = befehl.split()[0].lower()
        kat[f"hilfe.befehle.{wort}.befehl"] = befehl
        kat[f"hilfe.befehle.{wort}.text"] = text
    return kat


@pytest.mark.parametrize("art", ["geloescht", "hinzu", "umbenannt"])
def test_gegenprobe_drift_wird_erkannt(art: str):
    rows = command_rows()
    kat = _katalog_aus(rows)
    assert drift(rows, kat) == {"fehlt_im_katalog": [], "nur_im_katalog": []}
    if art == "geloescht":
        wort = rows[0][0].split()[0].lower()
        del kat[f"hilfe.befehle.{wort}.befehl"]
    elif art == "hinzu":
        kat["hilfe.befehle.erfunden.befehl"] = "ERFUNDEN"
    else:
        wort = rows[0][0].split()[0].lower()
        kat[f"hilfe.befehle.{wort}.befehl"] = rows[0][0] + "X"
    d = drift(rows, kat)
    assert d["fehlt_im_katalog"] or d["nur_im_katalog"]


# ── #2420 (Epic #2506): STARTDATUM und REPORT werden angeboten ───────────────
# Harte Literale (nicht aus command_rows() abgeleitet): ein fehlender Eintrag
# soll den Test rot machen, nicht aus der Erwartung verschwinden.

def test_zaehler_fuenfzehn_befehle_inkl_startdatum_und_report():
    """Spec feat_2420_befehle_anzeigen AC-14/AC-15: 13 -> 15 Befehle."""
    befehle = [befehl for befehl, _ in command_rows()]
    assert len(befehle) == 15, f"{len(befehle)} statt 15 Befehlen: {befehle!r}"
    assert "STARTDATUM JJJJ-MM-TT" in befehle
    assert "REPORT [morning / evening]" in befehle
    assert command_rows() == command_rows("route"), (
        "command_rows() ohne Argument muss der Trip-Liste (kind='route') entsprechen"
    )


def test_katalog_fuehrt_startdatum_und_report_mit_beschreibung():
    katalog = _katalog()
    befehle = katalog_befehle(katalog)
    assert befehle.get("startdatum") == "STARTDATUM JJJJ-MM-TT"
    assert befehle.get("report") == "REPORT [morning / evening]"
    for wort in ("startdatum", "report"):
        assert str(katalog.get(f"hilfe.befehle.{wort}.text", "")).strip(), wort


def test_stop_beschreibung_nennt_abbruch_in_quelle_und_katalog():
    """ABBRUCH ist kein eigener Befehl, sondern Alias von STOP (Spec-Entscheidung)."""
    quelle = dict(command_rows())
    assert "auch ABBRUCH" in quelle["STOP"], quelle["STOP"]
    assert "ABBRUCH" in _katalog()["hilfe.befehle.stop.text"]
    assert not [b for b, _ in command_rows() if b.split()[0] in ("ABBRUCH", "COLUMNS")]


def test_ortsvergleich_liste_hat_die_vergleichs_befehle_ohne_pause_dauer_und_ohne_etappe():
    """AC-10 / #2282 S2: die Vergleichs-Liste ist command_rows('vergleich') --
    HEUTE/MORGEN/REPORT mit eigenem Vergleichs-Wortlaut, ohne Argumentform."""
    rows = command_rows("vergleich")
    assert [b for b, _ in rows] == [
        "HEUTE", "MORGEN", "PAUSE", "WEITER", "HILFE", "KUERZEL", "REPORT",
    ], rows
    assert all(beschreibung for _, beschreibung in rows)
    assert not [b for b, t in rows if "Etappe" in t or "morning" in t], rows


def test_bot_commands_enthalten_startdatum_startdate_report_und_halten_bot_api_regeln():
    from src.output.channels.telegram import BOT_COMMANDS

    eintraege = {c["command"]: c["description"] for c in BOT_COMMANDS}
    for name in ("startdatum", "startdate", "report"):
        assert name in eintraege, f"BOT_COMMANDS ohne {name!r}"
    for name, beschreibung in eintraege.items():
        assert re.fullmatch(r"[a-z0-9_]{1,32}", name), name
        assert 0 < len(beschreibung) <= 256, name
    assert len(eintraege) < 100


# ── #2651 (i18n F2, AC-4): englische Befehlstabelle der Hilfeseite ───────────
# ``messages/en/hilfe.json`` zeigt die Befehlswoerter, die der Bot auf Englisch
# versteht (``wort_en`` aus ``_COMMAND_SPECS``, #2417). Echter Aufruf von
# ``command_rows()`` und ``bare_keywords()``; ``_COMMAND_SPECS`` nur gelesen.
# Spec: docs/specs/modules/i18n_f2_hilfe_infobox_2651.md

from src.services.trip_command_processor import _COMMAND_SPECS, bare_keywords  # noqa: E402

KATALOG_DATEI_EN = KATALOG_DATEI.parent.parent / "en" / "hilfe.json"


def _katalog_en() -> dict[str, str]:
    with KATALOG_DATEI_EN.open(encoding="utf-8") as f:
        return json.load(f)


def englisch_soll() -> dict[str, str]:
    """``{<wort>: <englischer Befehl>}`` aus ``_COMMAND_SPECS`` fuer die Trip-Befehle:
    ``wort_en`` in Grossschrift plus die Argumentform von ``command_rows()``
    (``JJJJ-MM-TT`` <-> ``YYYY-MM-DD``)."""
    de_arg = {befehl.split()[0]: befehl.partition(" ")[2] for befehl, _ in command_rows()}
    soll = {}
    for s in _COMMAND_SPECS:
        if "route" not in s.kinds:
            continue
        arg = de_arg[s.wort.upper()].replace("JJJJ-MM-TT", "YYYY-MM-DD")
        soll[s.wort] = f"{s.wort_en.upper()} {arg}".strip()
    return soll


def drift_en(katalog_en: dict[str, str]) -> list[str]:
    """Fehler der englischen Befehlstabelle; leer = kein Drift."""
    fehler = []
    ist = katalog_befehle(katalog_en)
    soll = englisch_soll()
    if set(ist) != set(soll):
        fehler.append(f"Schluessel: nur Katalog {sorted(set(ist) - set(soll))}, nur Quelle {sorted(set(soll) - set(ist))}")
    erkannt = bare_keywords()
    for wort, befehl in ist.items():
        if soll.get(wort) != befehl:
            fehler.append(f"{wort}: Katalog {befehl!r} != Quelle {soll.get(wort)!r}")
        if befehl.split()[0].lower() not in erkannt:
            fehler.append(f"{wort}: {befehl.split()[0]!r} ist kein vom Bot erkanntes Alleinwort")
    return fehler


def test_englische_befehle_entsprechen_wort_en_und_sind_erkannt():
    """AC-4: jeder englische Befehl = wort_en.upper() + Argumentform, erkanntes Alleinwort."""
    assert drift_en(_katalog_en()) == []


def test_englische_befehle_gleich_command_rows_en():
    """Gleiche Tabelle wie die englische Langform-Hilfe des Bots (#2673)."""
    ist = set(katalog_befehle(_katalog_en()).values())
    assert ist == {befehl for befehl, _ in command_rows("route", lang="en")}


def test_englische_befehle_harte_literale():
    """Spec-Tabelle als harte Literale (nicht aus der Quelle abgeleitet)."""
    befehle = katalog_befehle(_katalog_en())
    assert befehle["startdatum"] == "STARTDATE YYYY-MM-DD"
    assert befehle["ruhetag"] == "RESTDAY [N]"
    assert befehle["weiter"] == "RESUME"
    assert befehle["gewitter"] == "STORMS"
    assert befehle["report"] == "REPORT [morning / evening]"


def test_deutsche_tabelle_unveraendert_gleich_command_rows():
    """AC-4: die deutsche Tabelle bleibt exakt command_rows() (de)."""
    assert set(katalog_befehle(_katalog()).values()) == {befehl for befehl, _ in command_rows()}


def test_englische_texte_nennen_keinen_alias():
    """ABBRUCH/NOW/HELP/CODES-Hinweise entfallen in en; CANCEL wird nicht beworben."""
    katalog = _katalog_en()
    texte = [katalog[f"hilfe.befehle.{w}.text"] for w in katalog_befehle(katalog)]
    assert [t for t in texte if re.search(r"ABBRUCH|CANCEL|\(also ", t)] == []


@pytest.mark.parametrize("art", ["erfunden", "deutsch", "argument", "fehlt"])
def test_gegenprobe_englischer_drift_wird_erkannt(art: str):
    """Negativfall: ein erfundener, deutscher oder falsch argumentierter Befehl ist rot."""
    kat = {f"hilfe.befehle.{w}.befehl": b for w, b in englisch_soll().items()}
    assert drift_en(kat) == []
    if art == "erfunden":
        kat["hilfe.befehle.heute.befehl"] = "NOWADAYS"
    elif art == "deutsch":
        kat["hilfe.befehle.heute.befehl"] = "HEUTE"
    elif art == "argument":
        kat["hilfe.befehle.startdatum.befehl"] = "STARTDATE JJJJ-MM-TT"
    else:
        del kat["hilfe.befehle.heute.befehl"]
    assert drift_en(kat)
