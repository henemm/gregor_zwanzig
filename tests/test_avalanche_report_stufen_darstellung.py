"""Stille Default-Zweige der Stufen-Renderstellen fuer die Lagebericht-Gefahrenart (Risiken der Spec).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- Abschnitt 7 ("jede Stufen-Renderstelle bekommt
eine explizite Zuordnung fuer 1 und 5"), Risiken, AC-14, AC-15, AC-18
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 4

Diese Datei nutzt NUR bestehende Felder von `OfficialAlert` und bestehende Renderer -- sie importiert
nichts Neues. Damit scheitern die Tests im RED an der ASSERTION ("Warnstufe 0/3", Default-Zweig `info`,
Buchstabe statt Ziffer) und nicht an einem fehlenden Modul. `level` ist hier das abgeleitete Farblevel
(Stufe 1 -> 1, Stufe 5 -> 4); die Originalstufe (`native_level`) pruefen die uebrigen Dateien.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.helpers.avalanche_report_support import embedded_block, notice, wb_count_texts

UTC = timezone.utc


def _lagebericht(level: int):
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(
        source="avalanche_report:AT-07", hazard="avalanche_bulletin", level=level,
        label=f"Lawinenstufe {level}",
        valid_from=datetime(2026, 2, 19, 16, 0, tzinfo=UTC), valid_to=datetime(2026, 2, 20, 16, 0, tzinfo=UTC),
        region_label="Lasörlinggruppe", dedup_id="avalanche_bulletin:AT-07-25",
        url="https://avalanche.report/bulletin/2026-02-20?region=AT-07-25",
    )


@pytest.mark.parametrize("level", [1, 2, 3, 4], ids=["stufe-1", "stufe-2", "stufe-3", "stufe-4-und-5"])
def test_warn_block_zeigt_fuer_den_lagebericht_keine_warnstufen_leiter(level):
    """Stufe 1 liefe sonst in "Stufe GRUEN (0/3)", Stufe 4/5 in "(3/3)" -- die Leiter der
    Awareness-Skala gilt fuer die EAWS-Skala nicht."""
    html = embedded_block([_lagebericht(level)])

    for zeile in wb_count_texts(html):
        assert not re.search(r"\d/3", zeile), f"Leiter im Warn-Block fuer level={level}: {zeile!r}"


def test_ortsvergleich_chip_der_hoechsten_lagebericht_stufe_ist_danger():
    from output.renderers.email.compare_html import _warn_short

    _text, schwere = _warn_short(_lagebericht(4))

    assert schwere == "danger", f"hoechste Lagebericht-Stufen duerfen nicht im Default-Zweig landen: {schwere!r}"


def test_ortsvergleich_chip_nennt_lawine_mit_stufe_und_nicht_den_rohen_label():
    """Ohne `native_level` (hier nicht gesetzt) faellt die Ziffer auf das Level zurueck (Vertrag)."""
    from output.renderers.email.compare_html import _warn_short

    text, _schwere = _warn_short(_lagebericht(3))

    assert text == "Lawine 3", text


def test_alarm_sms_zeigt_die_stufe_als_ziffer_ohne_buchstaben():
    """Alarm-/Premium-SMS: `AV<Ziffer>` -- nicht `AV:H` (L/M/H-Umdeutung) und kein Notbehelf-Kuerzel."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    sms = render_official_alert_sms([notice(_lagebericht(4))], tz=ZoneInfo("UTC"))

    assert re.search(r"(?<![A-Za-z])AV(?![A-Za-z:])", sms), f"kein AV<Ziffer>-Token: {sms!r}"
    assert not re.search(r"AV\d?:[LMH]", sms), f"L/M/H-Umdeutung: {sms!r}"


def test_wortlaut_der_gefahrenart_ist_lawinenstufe_und_nicht_der_rohe_quell_label():
    from output.renderers.alert.official_alerts import _hazard_display

    label, kuerzel = _hazard_display(_lagebericht(3))

    assert label == "Lawinenstufe"
    assert kuerzel == "AV"
