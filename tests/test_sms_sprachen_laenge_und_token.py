"""SMS in beiden Sprachen: Token byte-identisch, Laengen-Grenzen gehalten (Issue #2670).

SPEC: docs/specs/modules/i18n_p8_sms_freitext_2670.md AC-1, AC-2, AC-5, AC-6
(plus Ratsche als Verhaltenstest, Known Limitations).

Wer unterwegs nur eine SMS empfaengt, bekommt in beiden Sprachen dieselben
Zahlen an derselben Stelle; nur das Etappen-Rueckfallwort (``Etappe``/``Stage``)
folgt der Sprache. Echte Renderer, feste Fixture, kein Mock.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.models import ChangeSeverity, WeatherChange
from i18n import t
from output.renderers.alert.render import render_sms as render_alert_sms
from output.renderers.channel_layout import CHANNEL_LIMITS
from output.renderers.comparison import render_compare_sms
from output.renderers.sms_trip import SMSTripFormatter
from tests.golden.test_sms_golden import GOLDENS
from tests.helpers.sms_sprachen_fixture import (
    abweichungs_alarm, golden, mit_sprache, regen_alarm_morgen, segmente, trip_sms,
    vergleich_zwoelf_orte,
)
from tests.helpers.telegram_briefing_fixture import TZ

REPO = Path(__file__).resolve().parents[1]
KATALOG = REPO / "src" / "i18n" / "messages"
ALLOWLIST = REPO / "tests" / "fixtures" / "i18n_python_allowlist.json"
BRIEFING_LIMIT = 160
ALARM_LIMIT = 140
VERGLEICH_LIMIT = CHANNEL_LIMITS["sms"]["max_chars"]

_STAGE_NAMES = sorted({m["stage_name"] for m in GOLDENS.values()} | {"Etappe 1: Calenzana"})


def _sms_texte(lang: str) -> list[str]:
    """Alle Katalogtexte mit Namenssegment ``sms`` (``sms.*``, ``alarm.sms.*`` ...)."""
    texte = []
    for datei in sorted((KATALOG / lang).glob("*.json")):
        for key, wert in json.loads(datei.read_text(encoding="utf-8")).items():
            if "sms" in key.split("."):
                texte.append(wert)
    return texte


# ---------------------------------------------------------------------------
# AC-1 — Etappenname vorhanden: en == de, byte fuer byte
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage_name", _STAGE_NAMES)
@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_ac1_trip_sms_mit_etappenname_ist_in_beiden_sprachen_gleich(stage_name, report_type):
    de = trip_sms("de", stage_name, report_type)
    en = trip_sms("en", stage_name, report_type)
    assert en == de
    assert len(en) <= BRIEFING_LIMIT


def test_ac1_etappe_n_wird_in_beiden_sprachen_zu_e_n():
    assert trip_sms("en", "Etappe 1: Calenzana").startswith("E1: ")
    assert trip_sms("de", "Etappe 1: Calenzana").startswith("E1: ")


# ---------------------------------------------------------------------------
# AC-2 — ohne Etappenname: Stage statt Etappe, Rest identisch
# ---------------------------------------------------------------------------


def test_ac2_de_ohne_etappenname_bleibt_byte_gleich_zum_altstand():
    assert trip_sms("de") == golden("etappe_rueckfall", "de")


def test_ac2_en_ohne_etappenname_beginnt_mit_stage_und_traegt_dieselben_token():
    de, en = trip_sms("de"), trip_sms("en")
    wort = t("sms.etappe.rueckfall", "en")
    assert wort == "Stage"
    assert en.startswith("Stage: ")
    assert en[len("Stage"):] == de[len("Etappe"):]
    assert en == golden("etappe_rueckfall", "en")
    assert len(en) <= BRIEFING_LIMIT


def test_ac2_standard_sprache_ist_deutsch():
    ohne = SMSTripFormatter().format_sms(segmente(), tz=TZ)
    assert ohne == golden("etappe_rueckfall", "de")


def test_alarm_aenderungs_sms_traegt_in_beiden_sprachen_dieselben_token():
    changes = [WeatherChange(metric="wind_max_kmh", old_value=20.0, new_value=55.0,
                             delta=35.0, threshold=10.0,
                             severity=ChangeSeverity.MAJOR, direction="increase")]
    fmt = SMSTripFormatter()
    de = fmt.format_alert_sms(changes, "GR20", lang="de")
    assert fmt.format_alert_sms(changes, "GR20", lang="en") == de
    assert de.startswith("[GR20] ALERT:")


# ---------------------------------------------------------------------------
# AC-5 — Alarm- und Ortsvergleich-SMS: Grenze und Differenz nur im Klartext
# ---------------------------------------------------------------------------

_ERZEUGER = {
    "abweichung": (render_alert_sms, abweichungs_alarm, ALARM_LIMIT),
    "regen_morgen": (render_alert_sms, regen_alarm_morgen, ALARM_LIMIT),
    "vergleich_12": (render_compare_sms, vergleich_zwoelf_orte, VERGLEICH_LIMIT),
}


def _render(name: str, lang: str) -> tuple[str, bool]:
    fn, daten, _ = _ERZEUGER[name]
    return mit_sprache(fn, daten(), lang=lang)


def _ohne_klartext(text: str, lang: str) -> str:
    for wert in sorted(_sms_texte(lang), key=len, reverse=True):
        muster = r".+?".join(re.escape(teil) for teil in re.split(r"\{[a-z_0-9]+\}", wert))
        if muster.strip():
            text = re.sub(muster, "§", text)
    return re.sub(r"(?<![A-Za-z])(Mo|Di|Mi|Do|Fr|Sa|So|Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?=\d)",
                  "§", text)


@pytest.mark.parametrize("name", sorted(_ERZEUGER))
@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac5_sms_haelt_ihre_grenze(name, lang):
    text, angekommen = _render(name, lang)
    if not angekommen:
        pytest.skip(f"{name}: Erzeuger kennt lang noch nicht (P4 #2666 / P5 #2667)")
    assert 0 < len(text) <= _ERZEUGER[name][2], text


@pytest.mark.parametrize("name", sorted(_ERZEUGER))
def test_ac5_de_und_en_unterscheiden_sich_nur_im_klartext(name):
    de, _ = _render(name, "de")
    en, angekommen = _render(name, "en")
    if not angekommen:
        pytest.skip(f"{name}: Erzeuger kennt lang noch nicht (P4 #2666 / P5 #2667)")
    assert _ohne_klartext(en, "en") == _ohne_klartext(de, "de")


def test_ac5_regen_alarm_traegt_tagesversatz():
    de, _ = _render("regen_morgen", "de")
    assert "@Do15" in de


def test_ac5_differenz_analyse_erkennt_echte_token_abweichung():
    """Selbsttest: ein geaendertes Token bleibt nach dem Entfernen sichtbar."""
    de, _ = _render("abweichung", "de")
    assert _ohne_klartext(de.replace("55", "56"), "de") != _ohne_klartext(de, "de")


# ---------------------------------------------------------------------------
# AC-6 — zwei Nutzer nacheinander: en, de, en ohne Zustand dazwischen
# ---------------------------------------------------------------------------


def test_ac6_reihenfolge_en_de_en_ohne_zustand():
    fmt = SMSTripFormatter()  # dieselbe Instanz fuer beide Nutzer
    nutzer_a_en = trip_sms("en", formatter=fmt)
    nutzer_b_de = trip_sms("de", formatter=fmt)
    nutzer_a_en_wieder = trip_sms("en", formatter=fmt)
    assert nutzer_b_de == golden("etappe_rueckfall", "de")
    assert nutzer_a_en == nutzer_a_en_wieder == golden("etappe_rueckfall", "en")


# ---------------------------------------------------------------------------
# Ratsche P8 als Verhalten: englische Trip-SMS ohne deutschen Katalogtext
# ---------------------------------------------------------------------------


def _deutsche_fragmente() -> set[str]:
    en = set(_sms_texte("en"))
    return {w.strip() for w in _sms_texte("de") if len(w.strip()) >= 3 and w not in en}


def _treffer(texte: list[str]) -> list[str]:
    frags = _deutsche_fragmente()
    return [s for s in texte if re.search(r"[äöüÄÖÜß]", s) or any(f in s for f in frags)]


def test_englische_trip_sms_ohne_deutsche_klartexte():
    texte = [trip_sms("en", n, rt) for n in [None, *_STAGE_NAMES]
             for rt in ("morning", "evening")]
    assert _treffer(texte) == []


def test_deutsche_gegenprobe_wird_erkannt():
    assert _treffer([trip_sms("de")]) == [trip_sms("de")]


def test_kein_allowlist_eintrag_fuer_sms_trip_py():
    if not ALLOWLIST.exists():
        return  # P11 legt die Allowlist an; Treffer-Freiheit prueft der Test oben
    eintraege = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert not any("src/output/renderers/sms_trip.py" in str(e) for e in eintraege)


def test_mit_sprache_helfer_meldet_fehlende_sprache():
    """Der Helfer darf ein fehlendes ``lang`` nie als angekommen ausgeben."""
    _, angekommen = mit_sprache(lambda: "x", lang="en")
    assert angekommen is False
