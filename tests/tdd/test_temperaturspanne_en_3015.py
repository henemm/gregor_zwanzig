"""#3015: Temperaturspanne bei Minusgraden sprachneutral ("-3 – 0°C").

SPEC: docs/specs/modules/fix_3015_temp_spanne_en.md

PO-Entscheidung 2026-11-15: Spanne mit mindestens einem negativen ANGEZEIGTEN
Wert in beiden Sprachen als Gedankenstrich mit je einem Leerzeichen
("-12 – -4°C"), kein Bindewort ("bis"/"to") mehr. Die Lufttemperatur der
Kurzzusammenfassung nutzt dieselbe geteilte Formel wie Kachel und gefuehlte
Temperatur (#1410, kein Nachbau).

Alle Tests rufen die echten Renderer auf (``TripReportFormatter.format_email``,
``render_compare_email``), netzfrei, kein Mock.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from output.renderers.email.helpers import _aggregation_pill_text
from tests.tdd._hiking_window_fixtures import (
    STAGE_NAME, TRIP_NAME, TZ, build_segments, dc,
)

_BINDEWORT = re.compile(r"\b(bis|to)\b")


def _report(lang: str, temps: dict[int, float], felt: dict[int, float] | None = None):
    """Echter Briefing-Lauf (Morgen), Etappe 08-12 Uhr, Temperatur + gefuehlt."""
    from output.renderers.trip_report import TripReportFormatter

    stunden = range(24)
    t = {h: temps.get(h, temps[min(temps)]) for h in stunden}
    f = felt or {h: v - 3.0 for h, v in t.items()}
    segments = build_segments([(8, 12)], t, {h: f.get(h, f[min(f)]) for h in stunden})
    return TripReportFormatter().format_email(
        segments, trip_name=TRIP_NAME, report_type="morning",
        display_config=dc("temperature", "wind_chill"), stage_name=STAGE_NAME,
        tz=TZ, lang=lang,
    )


def _wechsel(lo: float, hi: float) -> dict[int, float]:
    """Gehzeit 08-12: Tiefstwert ``lo`` um 8 Uhr, Hoechstwert ``hi`` um 11 Uhr."""
    return {h: (hi if h == 11 else lo) for h in range(24)}


def _kachel(report) -> str:
    """Gemessene Temperatur-Kachelzeile ("... °C · Max HH:00", ohne gef.)."""
    treffer = [
        z.strip() for z in report.email_plain.splitlines()
        if "°C · Max" in z and "gef." not in z and "felt" not in z.lower()
    ]
    assert treffer, f"keine Temperatur-Kachelzeile in der Mail:\n{report.email_plain}"
    return treffer[0]


def _kurz(report) -> str:
    """Kurzzusammenfassungssatz der echten Mail ("E7: ...")."""
    for z in report.email_plain.splitlines():
        if z.startswith(f"{STAGE_NAME}: "):
            return z
    raise AssertionError(f"keine Kurzzusammenfassung:\n{report.email_plain}")


def _kachel_direkt(lo: float, hi: float) -> str:
    ts = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
    vals = [(lo, ts), (hi, ts.replace(hour=12))]
    return _aggregation_pill_text(
        vals, ["min", "max"], tz=ZoneInfo("Europe/Berlin"), prefix="", decimals=0,
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-3: Kachelzeile Trip-Briefing, englisch und deutsch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "de"])
def test_ac1_ac3_kachel_minus_spanne_mit_gedankenstrich(lang):
    """AC-1 (en) / AC-3 (de): "-3 – 0°C", weder "bis" noch "to"."""
    kachel = _kachel(_report(lang, _wechsel(-3.0, 0.0)))
    assert kachel.split(" · ")[0].endswith("-3 – 0°C"), kachel
    assert not _BINDEWORT.search(kachel), kachel


def test_ac1_englische_mail_ohne_deutsches_bindewort_in_der_spanne():
    """AC-1: nirgends in der englischen Mail eine Spanne mit "bis"."""
    report = _report("en", _wechsel(-3.0, 0.0))
    for teil in (report.email_plain, report.email_html):
        assert not re.search(r"-?\d+(?:\.\d)? bis -?\d+", teil), teil


# ---------------------------------------------------------------------------
# AC-2: Ortsvergleich (englisch) -- keine deutsche Spanne
# ---------------------------------------------------------------------------

def test_ac2_ortsvergleich_en_ohne_deutsches_bindewort():
    """AC-2: die englische Vergleichs-Mail mit -3/0 Grad enthaelt keine
    Temperaturspanne mit deutschem Bindewort und keine Folge "–-".

    Befund in Phase 5: die Vergleichs-Mail baut KEINE Kachelzeile ueber
    ``format_temp_span`` (Tiefst-/Hoechstwert stehen als eigene Zeilen,
    der Ausblick als "-3/0°C"). Der Test sichert den Ist-Zustand als
    Regression ab (Spec-Vermerk).
    """
    from tests.helpers import vergleichs_mail_fixture as f

    r = f.build_result(mit_fehlerort=False)
    orte = []
    for o in r.locations:
        stunden = [dataclasses.replace(dp, t2m_c=-3.0 if dp.ts.hour % 2 else 0.0)
                   for dp in o.hourly_data]
        ausblick = [dataclasses.replace(dp, t2m_c=-3.0 if dp.ts.hour % 2 else 0.0)
                    for dp in o.outlook_hourly_data]
        orte.append(dataclasses.replace(o, temp_min=-3.0, temp_max=0.0,
                                        hourly_data=stunden, outlook_hourly_data=ausblick))
    html, text = f.render_mail("en", dataclasses.replace(r, locations=orte))
    for teil in (html, text):
        assert not re.search(r"-?\d+ bis -?\d+", teil)
        assert "–-" not in teil
    assert "-3°C" in text


# ---------------------------------------------------------------------------
# AC-4: Kurzzusammenfassung, Lufttemperatur und gefuehlt, beide Sprachen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac4_kurzzusammenfassung_minus_spannen(lang):
    """AC-4: "-12 – -4°C" (Luft) und "-15 – -8°C" (gefuehlt), nie "–-"."""
    temps = _wechsel(-12.0, -4.0)
    felt = _wechsel(-15.0, -8.0)
    report = _report(lang, temps, felt)
    satz = _kurz(report)
    assert "-12 – -4°C" in satz, satz
    assert "-15 – -8°C" in satz, satz
    assert not _BINDEWORT.search(satz.split(": ", 1)[1]), satz
    for teil in (report.email_plain, report.email_html):
        assert "–-" not in teil, "Gedankenstrich und Minus laufen zusammen"


# ---------------------------------------------------------------------------
# AC-5: Plusgrade zeichengleich "8–14°C"
# ---------------------------------------------------------------------------

def test_ac5_plusgrade_kachel_und_kurzzusammenfassung_ohne_leerzeichen():
    report = _report("de", _wechsel(8.0, 14.0))
    assert _kachel(report).split(" · ")[0].endswith("8–14°C"), _kachel(report)
    assert "8–14°C" in _kurz(report), _kurz(report)
    assert " – " not in _kurz(report)


# ---------------------------------------------------------------------------
# AC-6: gerundet gleich -> Einzelwert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac6_kurzzusammenfassung_gerundet_gleich_einzelwert(lang):
    """AC-6: Lufttemperatur 4,6/5,2 -> "5°C" statt "5–5°C"."""
    satz = _kurz(_report(lang, _wechsel(4.6, 5.2)))
    assert "5–5°C" not in satz, satz
    teile = satz.split(": ", 1)[1].split(", ")
    assert "5°C" in teile, satz


def test_ac6_kachel_gerundet_gleich_einzelwert():
    """AC-6: Kachel 4,6/5,2 -> "5°C"; -0,2/0,2 -> Einzelwert "0°C", kein "-0–0"."""
    assert _kachel_direkt(4.6, 5.2).startswith("5°C"), _kachel_direkt(4.6, 5.2)
    um_null = _kachel_direkt(-0.2, 0.2)
    assert um_null.startswith("0°C"), um_null
    assert "-0" not in um_null, um_null


def test_ac6_kurzzusammenfassung_um_null_einzelwert():
    """AC-6: Lufttemperatur -0,2/0,2 -> "0°C" (kein "-0", kein "0–0")."""
    satz = _kurz(_report("de", _wechsel(-0.2, 0.2)))
    teile = satz.split(": ", 1)[1].split(", ")
    assert "0°C" in teile, satz
    assert "0–0°C" not in satz and "-0" not in satz, satz
