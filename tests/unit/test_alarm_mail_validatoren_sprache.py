"""Alarm-Validatoren sprechen die Sprache des Kopfes ``X-GZ-Lang``
(Issue #2663, AC-5).

Kern-Schicht: echte Fixtures ``official_alert_de.eml`` (``render_warn_block`` +
``render_official_alert_mail_plain``) und ``radar_alert_de.eml``
(``alert.render.render_email``) ueber ``build_mime_message``; englische Fassung
per ``als_englisch`` aus dem Katalog. Validatoren als Prozess (``--eml``).

SPEC: docs/specs/modules/i18n_pv_mail_validatoren_2663.md
"""
from __future__ import annotations

from datetime import date

import pytest

from i18n import fmt_date
from tests.helpers.mail_lang_fixture import (
    als_englisch, bearbeite, entwarnungen, gewitter_alarm, lade, lawinen_alarm, mailtext,
    mit_kopf, validator_lauf, warn_mail_de,
)

WARNUNG = [
    "warnung.verdict.one", "warnung.verdict.other", "warnung.gueltig", "warnung.quelle",
    "warnung.abgerufen_bei", "warnung.stufe.gelb", "warnung.stufe.orange", "warnung.stufe.rot",
    "warnung.gefahr.wind_gust", "warnung.gefahr.thunderstorm",
]
RADAR = [
    "alarm.radar.intensitaet.leicht", "alarm.radar.intensitaet.maessig",
    "alarm.radar.intensitaet.stark", "alarm.radar.intensitaet.hagel",
    "alarm.radar.intensitaet.gewitter", "alarm.radar.intensitaet.regen",
    "alarm.radar.cooldown_praefix", "alarm.segment.etappe", "alarm.segment.ziel",
]
_TAG = date(2026, 10, 29)
# Gueltig-Zeitraum: Datumsform kommt aus fmt_date (Formatquelle der Renderer).
DATUM = {fmt_date(_TAG, "de"): fmt_date(_TAG, "en")}

FAELLE = {
    "official_alert_mail_validator": ("official_alert_de.eml", WARNUNG, DATUM),
    "radar_alert_mail_validator": ("radar_alert_de.eml", RADAR, {}),
}


def _englisch(validator: str) -> bytes:
    fixture, schluessel, zusatz = FAELLE[validator]
    return als_englisch(lade(fixture), schluessel, zusatz)


@pytest.mark.parametrize("validator", list(FAELLE))
def test_ac5_englische_mail_mit_kopf_en_besteht(tmp_path, validator):
    eml = _englisch(validator)
    lauf, _ = validator_lauf(tmp_path, validator, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "uebersprungen" not in lauf.stdout


@pytest.mark.parametrize("validator", list(FAELLE))
def test_ac5_englischer_inhalt_mit_kopf_de_faellt(tmp_path, validator):
    lauf, _ = validator_lauf(tmp_path, validator, mit_kopf(_englisch(validator), "de"))
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "X-GZ-Lang: de widerspricht dem Inhalt" in lauf.stdout + lauf.stderr


@pytest.mark.parametrize("validator", list(FAELLE))
def test_ac7_deutsche_fixture_besteht(tmp_path, validator):
    lauf, _ = validator_lauf(tmp_path, validator, lade(FAELLE[validator][0]))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "WARNUNG" not in lauf.stderr


def test_ac5_englische_inhalte_stehen_wirklich_in_der_mail():
    """Testaufbau: die AC-5-Woerter stehen in den englischen Fassungen."""
    warn = mailtext(_englisch("official_alert_mail_validator"))
    radar = mailtext(_englisch("radar_alert_mail_validator"))
    for wort in ("2 official warnings", "Valid:", "Source:", "retrieved from"):
        assert wort in warn
    for wort in ("Heavy rain", "Destination", "at most once in"):
        assert wort in radar


def test_ac5_englische_gueltig_zeile_braucht_einen_zeitraum(tmp_path):
    """Gegenprobe P-3 in en: 'Valid:' ohne Zeitraum faellt -- die englische
    Zeile wird geprueft, nicht nur geduldet."""
    eml = als_englisch(lade("official_alert_de.eml"), WARNUNG, {fmt_date(_TAG, "de"): "unknown"})
    lauf, _ = validator_lauf(tmp_path, "official_alert_mail_validator", eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "P-3" in lauf.stdout + lauf.stderr


def _modul(name: str):
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_2663", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac7_deutsche_erwartungen_aus_dem_katalog_gleichen_den_bestandskonstanten():
    """Golden de: die aus dem Katalog gebildeten deutschen Erwartungen sind
    wortgleich zu den bisherigen Literalen (die Bestandstests lesen diese)."""
    warn = _modul("official_alert_mail_validator")
    w = warn._lang_patterns("de")
    assert w["other_hazard"].pattern == warn._OTHER_HAZARD_RE.pattern
    assert w["level_word"].pattern == warn._LEVEL_WORD_RE.pattern
    assert w["validity"].pattern == warn._VALIDITY_RE.pattern
    assert w["eaws"] == warn._EAWS_WORDS

    radar = _modul("radar_alert_mail_validator")
    r = radar._lang_patterns("de")
    assert set(r["intensity"]) == set(radar._INTENSITY_LABELS)
    assert r["segment"].pattern == radar._SEGMENT_RE.pattern


# ---------------------------------------------------------------------------
# Adversary F001/F005: jede sprachabhaengige Erwartung wird in einer
# englischen Mail einzeln wirksam -- Lawinen-Lagebericht, gemischte Mail,
# Entwarnung (Stufe 3 -> 1, -> beendet), Radar mit Etappen-Bezug.
# ---------------------------------------------------------------------------
LAWINE = [*WARNUNG, "warnung.lawine.stufe", *(f"warnung.eaws.{i}" for i in range(1, 6))]
ENTWARNUNG = ["warnung.entwarnung.wort", "warnung.entwarnung.uebergang",
              "warnung.entwarnung.beendet", "warnung.gefahr.extreme_heat", *WARNUNG]
DATEN = {fmt_date(date(2026, m, t), "de"): fmt_date(date(2026, m, t), "en")
         for m, t in ((2, 19), (2, 20), (10, 29))}
OFFICIAL = "official_alert_mail_validator"


def _ohne_stufen_traeger(text: str) -> str:
    """Leiter/Meter und Farbwoerter entfernen (Muster F012 im Bestandstest)."""
    text = (text.replace('class="warn stacked"', 'class="warn"').replace('class="meter ', 'class="x ')
            .replace('class="stufe-line"', 'class="x"'))
    for wort in ("YELLOW", "ORANGE", "RED"):
        text = text.replace(wort, "")
    return text


def test_f001_englischer_lawinen_lagebericht_besteht(tmp_path):
    """'Avalanche level 4 (high)': Stufen-Wortlaut und EAWS-Wort in en. Faellt
    die Erwartung auf de zurueck, fehlt der Lagebericht (S-2/P-2) bzw. passt
    das EAWS-Wort nicht (P-2b)."""
    eml = als_englisch(warn_mail_de([lawinen_alarm()]), LAWINE, DATEN)
    assert "Avalanche level 4 (high)" in mailtext(eml)
    lauf, _ = validator_lauf(tmp_path, OFFICIAL, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_f001_falsches_englisches_eaws_wort_faellt(tmp_path):
    eml = als_englisch(warn_mail_de([lawinen_alarm()]), LAWINE, DATEN)
    eml = bearbeite(eml, lambda t: t.replace("Avalanche level 4 (high)", "Avalanche level 4 (moderate)"))
    lauf, _ = validator_lauf(tmp_path, OFFICIAL, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "P-2b" in lauf.stdout + lauf.stderr


def test_f001_gemischte_englische_mail_besteht_ueber_englisches_farbwort(tmp_path):
    """Gewitter (YELLOW) + Lawine: P-2 findet die Warnstufe nur als 'YELLOW'."""
    eml = als_englisch(warn_mail_de([gewitter_alarm(), lawinen_alarm()]), LAWINE, DATEN)
    text = mailtext(eml)
    assert "YELLOW" in text and "GELB" not in text and "ORANGE" not in text
    lauf, _ = validator_lauf(tmp_path, OFFICIAL, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_f001_gemischte_englische_mail_ohne_stufentraeger_faellt(tmp_path):
    """F012 in en: das Typ-Wort 'Thunderstorm' verhindert die Lawinen-Lockerung."""
    eml = als_englisch(warn_mail_de([gewitter_alarm(), lawinen_alarm()]), LAWINE, DATEN)
    eml = bearbeite(eml, _ohne_stufen_traeger)
    assert "Thunderstorm" in mailtext(eml)
    lauf, _ = validator_lauf(tmp_path, OFFICIAL, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "S-2" in lauf.stdout + lauf.stderr


def test_f001_englische_entwarnung_besteht(tmp_path):
    """'All clear', 'Level 3 → 1' und 'Level 3 → ended' in Text und Betreff."""
    eml = als_englisch(warn_mail_de([], entwarnungen()), ENTWARNUNG, DATEN)
    text = mailtext(eml)
    assert "All clear" in text and "Level 3 → 1" in text and "Level 3 → ended" in text
    lauf, _ = validator_lauf(tmp_path, OFFICIAL, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_f001_englische_entwarnung_ohne_absenkung_faellt(tmp_path):
    eml = als_englisch(warn_mail_de([], entwarnungen()), ENTWARNUNG, DATEN)
    eml = bearbeite(eml, lambda t: t.replace("Level 3 → 1", "Level 3 → 3"))
    lauf, _ = validator_lauf(tmp_path, OFFICIAL, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "E-3" in lauf.stdout + lauf.stderr


def test_f005_radar_mit_englischem_etappen_bezug_besteht(tmp_path):
    """Ortsangabe 'Stage 3' (Katalog alarm.segment.etappe) ist der EINZIGE
    Ortsbezug der Mail -- P-1 muss sie in en erkennen. (Der Renderer schreibt
    heute 'Segment N'/'🏁 Ziel'; die Etappen-Form ist Bestand des Musters und
    wird hier per String-Ersetzung am echten Output eingesetzt.)"""
    eml = als_englisch(lade("radar_alert_de.eml"), RADAR, {"🏁 Ziel": "Stage 3"})
    text = mailtext(eml)
    assert "Stage 3" in text and "Destination" not in text and "Segment" not in text
    lauf, _ = validator_lauf(tmp_path, "radar_alert_mail_validator", eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
