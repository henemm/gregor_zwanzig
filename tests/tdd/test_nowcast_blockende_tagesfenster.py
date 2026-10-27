"""TDD RED — Issue #2051 S1: das Ende wird NICHT am Tagesfenster gekappt.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-7 (Entscheid E2).

Fachlicher Kern: der Nowcast-Pfad spricht heute schon ausserhalb des
konfigurierten Tagesfensters — `onset_time` wird nirgends gekappt. Nur das
ENDE zu kappen waere in sich unstimmig, und ein still auf 20:00 gekapptes
"letzter Regen gegen 20:00" bei Regen bis 22:15 waere eine FALSCHE Aussage
(dieselbe Fehlerklasse wie R4, nur selbst verursacht).

Aufbau: jetzt ist 19:45 Ortszeit (Wien), der Regen beginnt 20:05 und endet
22:15 — beides jenseits eines Tagesfenster-Endes von 20:00, beides innerhalb
des 180-Minuten-Nowcast-Horizonts.

RED heute: `NowcastResult` kennt `event_end_minutes` nicht (`AttributeError`
bzw. `TypeError` beim Konstruktor).

Mock-frei: echte `RadarFrame`/`NowcastResult`-Objekte durch die echten
Renderer; Uhr per `now=` bzw. `freeze_time` festgestellt.
"""
from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_sms
from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import NowcastResult, RadarNowcastService

# 19:45 Ortszeit Wien am 2026-08-21 (CEST = UTC+2) -> 17:45 UTC.
_TZ = ZoneInfo("Europe/Vienna")
_NOW = datetime(2026, 8, 21, 17, 45, tzinfo=timezone.utc)
_FROZEN_UTC = "2026-08-21 17:45:00+00:00"

# Bezugsgroesse der Zusicherung: ein typisches Tagesfenster-Ende, hinter dem
# das echte Ende (22:15) liegt. Die Ableitung darf diese Grenze gar nicht
# kennen.
_TAGESFENSTER_ENDE = "20:00"

_UNSET = object()


def _frames(raster: dict[int, float]) -> list[RadarFrame]:
    return [
        RadarFrame(timestamp=_NOW + timedelta(minutes=minute), precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]


def _result(raster: dict[int, float]):
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(_frames(raster), "radar", now=_NOW)


def _nowcast(*, event_end_minutes: object = _UNSET) -> NowcastResult:
    """Beginn in 20 Minuten (20:05 Ortszeit)."""
    fields = dict(
        onset_minutes=20, intensity_label="Starker Regen", source="radar",
        is_convective=False,
    )
    if event_end_minutes is not _UNSET:
        fields["event_end_minutes"] = event_end_minutes
    return NowcastResult(**fields)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Nowcast-Dienst und Alarm-Renderer werden
    RELATIV ZU DIESER Testdatei aufgeloest."""
    from output.renderers.alert import render as render_module
    from services import radar_service as radar_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (radar_module, render_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


def test_ac7_ableitung_reicht_ueber_das_tagesfenster_hinaus():
    """AC-7 (Vorstufe) GIVEN eine Frame-Zeitreihe mit nassem Block von
    Minute 20 (20:05 Ortszeit) bis Minute 150 (22:15 Ortszeit), also weit
    ueber ein Tagesfenster-Ende von 20:00 hinaus
    WHEN das Ende abgeleitet wird
    THEN steht `event_end_minutes` bei 150 — die Ableitung kennt das
    Tagesfenster nicht und kappt nichts.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    raster = {m: (1.0 if 20 <= m <= 150 else 0.0) for m in range(0, 181, 5)}

    result = _result(raster)

    assert result.onset_minutes == 20, (
        f"Vorbedingung: Beginn bei Minute 20, bekam {result.onset_minutes}"
    )
    assert result.event_end_minutes == 150, (
        f"RED: ungekapptes Ende bei Minute 150 erwartet, bekam "
        f"{result.event_end_minutes!r}"
    )
    assert result.event_ongoing_beyond_horizon is False, (
        "Der Block endet an einem Trockenframe innerhalb des Fensters — das "
        "Ende ist bekannt, der Horizont-Waechter darf nicht anschlagen."
    )


@freeze_time(_FROZEN_UTC)
def test_ac7_langform_nennt_das_echte_ende_ohne_kappung():
    """AC-7 GIVEN einen Onset-Alarm, dessen Ende (22:15 Ortszeit) ueber das
    konfigurierte Tagesfenster-Ende (20:00) hinausreicht
    WHEN die Langform-E-Mail gerendert wird
    THEN nennt der Text das ECHTE Ende (22:15), OHNE es auf das Tagesfenster
    zu kappen und ohne es zu unterdruecken.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht (`TypeError`)."""
    msg = to_multi_location_onset_alert_message(
        [("Sillian", _nowcast(event_end_minutes=150))],
        tz=_TZ, stand_at="19:45",
    )

    _, plain = render_email(msg)

    assert "letzter Regen gegen 22:15" in plain, (
        f"RED: das ungekappte Ende 22:15 fehlt im Langform-Text: {plain!r}"
    )
    assert f"letzter Regen gegen {_TAGESFENSTER_ENDE}" not in plain, (
        f"Das Ende wurde still auf das Tagesfenster-Ende "
        f"{_TAGESFENSTER_ENDE} gekappt — das waere eine falsche Aussage: "
        f"{plain!r}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac7_kurzform_nennt_das_echte_ende_ohne_kappung():
    """AC-7 (Kurzform) GIVEN denselben Aufbau
    WHEN die Kurznachricht gerendert wird
    THEN nennt auch sie die Stunde des echten Endes (22), nicht die des
    Tagesfenster-Endes (20) — geprueft ueber die Stunden der beiden
    Zeit-Token, damit die Zusicherung unabhaengig davon haelt, ob die
    Kurzform `@HH:MM` oder `@HH` schreibt.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht (`TypeError`)."""
    msg = to_multi_location_onset_alert_message(
        [("Sillian", _nowcast(event_end_minutes=150))],
        tz=_TZ, stand_at="19:45",
    )

    sms = render_sms(msg)
    stunden = re.findall(r"@(\d{1,2})", sms)

    assert len(stunden) == 2, (
        f"RED: erwartet zwei Zeit-Token (Beginn und Ende) in der "
        f"Kurznachricht, bekam {stunden!r}: {sms!r}"
    )
    assert stunden[0] == "20", (
        f"Vorbedingung: das Beginn-Token gehoert zur Stunde 20: {sms!r}"
    )
    assert stunden[1] == "22", (
        f"Das Ende-Token nennt nicht die echte Ende-Stunde 22 — offenbar auf "
        f"das Tagesfenster gekappt: {sms!r}"
    )
