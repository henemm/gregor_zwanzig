"""TDD RED #2982 -- EIN Baustein fuer den Alarm-Beginn (OnsetEvent).

SPEC: docs/specs/modules/fix_2982_onset_event_baustein.md -- AC-4 bis AC-8.

Heute wird ``OnsetEvent`` an vier Stellen getrennt gebaut (Trip-Versand,
Ortsvergleich-Buendel, Vorschau/Replay, Altform). Neue Felder fehlten dadurch
immer wieder still auf einem Pfad (#2009, #2046, #2050, #2051, #2054).

Geprueft wird hier:
- ``project.onset_event_from_nowcast`` (NowcastResult -> OnsetEvent) mit
  laufendem Regen, Beginn ueber Mitternacht, zwei Zeitzonen (AC-4, AC-5);
- ``project.onset_event_from_fields`` (Objekt mit gleichnamigen Feldern ->
  OnsetEvent) generisch ueber ALLE Dataclass-Felder (AC-6-Grundlage);
- der Ortsvergleich-Pfad baut seine Events ueber den Baustein (AC-2/AC-4);
- Ratsche Feldsatz: jedes ``OnsetEvent``-Feld steht im Trip-Versandbuendel
  ``RadarAlertRequest`` oder in der Ausnahmeliste (AC-6), samt Mutationsprobe;
- Ratsche Bau: ``OnsetEvent(`` wird in ``src/`` und ``api/`` nur in
  ``project.py`` gebaut (AC-7);
- die Altform ``build_onset_alert_message`` ist entfernt (AC-8).

Die byte-identischen Texte (AC-1 bis AC-3) bewacht
``tests/tdd/test_onset_golden_master_2982.py``.

Kein Mock: echte ``NowcastResult``-Objekte, echte Zeit-Helfer, AST des
echten Quelltexts.
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
BERLIN = ZoneInfo("Europe/Berlin")
LISSABON = ZoneInfo("Europe/Lisbon")
UTC = ZoneInfo("UTC")
# Fr 13.11.2026 22:30 UTC = 23:30 Berlin = 22:30 Lissabon (Winterzeit).
JETZT = datetime(2026, 11, 13, 22, 30, tzinfo=timezone.utc)

# Felder, die bewusst NICHT im Trip-Versandbuendel stehen (Spec, Variante ii-b):
# `location_label` gibt es nur im Ortsvergleich, `stage_number` leitet der
# Versand aus `segment_date` ab.
AUSNAHMEN_TRIP_BUENDEL = frozenset({"location_label", "stage_number"})


def _nc(**kw):
    from services.radar_service import NowcastResult

    basis = dict(onset_minutes=45, intensity_label="Mäßiger Regen", source="radar")
    basis.update(kw)
    return NowcastResult(**basis)


# ─────────────────────── onset_event_from_nowcast ─────────────────────────


class TestBausteinAusNowcast:
    def test_ac4_laufender_regen_beginn_ist_jetzt(self):
        """AC-4: laeuft der Regen bereits, ist der Beginn JETZT, `onset_minutes`
        0, kein Tagesbezug -- unabhaengig von einem gesetzten Folge-Frame."""
        from output.renderers.alert.project import onset_event_from_nowcast

        nc = _nc(onset_minutes=None, already_running=True, event_end_minutes=30)
        ev = onset_event_from_nowcast(
            nc, now_utc=JETZT, tz=BERLIN, intensity_label="leichter Regen",
            source_label="Radar (DWD)",
        )
        assert ev.already_running is True
        assert ev.onset_minutes == 0
        assert ev.onset_time == "23:30"
        assert ev.onset_day_offset == 0
        assert ev.onset_weekday is None

    def test_ac4_laufend_mit_folgeframe_bleibt_jetzt(self):
        """AC-4: Trip-Regel `nowcast_onset_at` -- auch wenn `onset_minutes` auf
        den naechsten Frame zeigt, ist der Beginn bei laufendem Regen JETZT."""
        from output.renderers.alert.project import onset_event_from_nowcast

        nc = _nc(onset_minutes=10, already_running=True)
        ev = onset_event_from_nowcast(
            nc, now_utc=JETZT, tz=BERLIN, intensity_label="x", source_label="y",
        )
        assert ev.already_running is True
        assert ev.onset_time == "23:30"

    def test_ac5_beginn_nach_mitternacht_berlin(self):
        """AC-5: 22:30 UTC + 45 Min = 00:15 Berlin am Samstag -> Versatz 1,
        Kuerzel `Sa`. Ende +95 Min = 01:05 Berlin, eigener Tagesbezug."""
        from output.renderers.alert.project import onset_event_from_nowcast

        nc = _nc(onset_minutes=45, event_end_minutes=95)
        ev = onset_event_from_nowcast(
            nc, now_utc=JETZT, tz=BERLIN, intensity_label="mäßiger Regen",
            source_label="Radar (DWD)",
        )
        assert (ev.onset_time, ev.onset_day_offset, ev.onset_weekday) == ("00:15", 1, "Sa")
        assert (ev.event_end_time, ev.event_end_day_offset, ev.event_end_weekday) == (
            "01:05", 1, "Sa",
        )
        assert ev.onset_minutes == 45
        assert ev.already_running is False

    def test_ac5_selber_zeitpunkt_in_lissabon_ohne_tageswechsel(self):
        """AC-5 Gegenprobe: derselbe Zeitpunkt liegt in Lissabon (UTC+0 im
        November) noch am Freitag -> 23:15, Versatz 0, kein Kuerzel."""
        from output.renderers.alert.project import onset_event_from_nowcast

        ev = onset_event_from_nowcast(
            _nc(onset_minutes=45), now_utc=JETZT, tz=LISSABON,
            intensity_label="x", source_label="y",
        )
        assert (ev.onset_time, ev.onset_day_offset, ev.onset_weekday) == ("23:15", 0, None)

    def test_reichweite_und_ortsschaerfe_ueber_die_geteilten_fassungen(self):
        """Reichweite und Ortsschaerfe stimmen mit den geteilten Fassungen
        ueberein, die schon alle drei Pfade benutzen (ADR-0021)."""
        from output.renderers.alert.project import (
            location_sharpness_display, onset_event_from_nowcast, source_reach_display,
        )

        nc = _nc(onset_minutes=45, event_end_minutes=95, source_reach_minutes=120)
        ev = onset_event_from_nowcast(
            nc, now_utc=JETZT, tz=BERLIN, intensity_label="x", source_label="y",
        )
        assert (ev.source_reach_time, ev.source_reach_day_offset) == (
            source_reach_display(JETZT, nc, BERLIN)
        )
        assert ev.source_reach_time == "01:30"
        assert (ev.location_sharpness_limit_time, ev.location_sharpness_limit_day_offset) == (
            location_sharpness_display(JETZT, 45, 95, BERLIN)
        )

    def test_eigenschaften_des_ereignisses_kommen_aus_dem_nowcast(self):
        """Menge, Gewitter, Gewitterpruefung und R4-Waechter kommen 1:1 aus
        dem NowcastResult; Labels und Ortskontext sind EINGABEN des Aufrufers
        (bewusste Pfad-Unterschiede, nicht vereinheitlichen)."""
        from output.renderers.alert.project import onset_event_from_nowcast
        from services.rain_extent import RainZone

        zone = RainZone(km_from=1.0, km_to=2.0, onset_minutes=45, event_end_minutes=90)
        nc = _nc(
            onset_minutes=45, is_convective=True, convective_checked=False,
            onset_precip_mm=4.2, event_end_minutes=200,
            event_ongoing_beyond_horizon=True,
        )
        ev = onset_event_from_nowcast(
            nc, now_utc=JETZT, tz=BERLIN, intensity_label="starker Regen",
            source_label="Radar (DWD)", km_from=5.0, km_to=18.0,
            segment_id="2", km_measured=True, rain_zones=(zone,), gap_km=(7.5,),
            briefing_context="angekündigt",
        )
        assert ev.is_convective is True
        assert ev.convective_checked is False
        assert ev.onset_precip_mm == 4.2
        assert ev.event_ongoing_beyond_horizon is True
        assert ev.intensity_label == "starker Regen"
        assert ev.source_label == "Radar (DWD)"
        assert (ev.km_from, ev.km_to, ev.segment_id) == (5.0, 18.0, "2")
        assert ev.km_measured is True
        assert ev.rain_zones == (zone,)
        assert ev.gap_km == (7.5,)
        assert ev.briefing_context == "angekündigt"
        assert ev.location_label is None

    def test_ortsvergleich_ortskontext(self):
        """AC-2: im Ortsvergleich traegt das Event km 0 und sein Ortslabel."""
        from output.renderers.alert.project import onset_event_from_nowcast

        ev = onset_event_from_nowcast(
            _nc(), now_utc=JETZT, tz=LISSABON, intensity_label="Mäßiger Regen",
            source_label="radar", location_label="Lissabon",
        )
        assert (ev.km_from, ev.km_to) == (0.0, 0.0)
        assert ev.location_label == "Lissabon"


# ─────────────────────── onset_event_from_fields ──────────────────────────


def _werte_ungleich_default() -> dict:
    """Fuer JEDES OnsetEvent-Feld ein Wert, der sich vom Default unterscheidet
    -- generisch, damit ein kuenftiges Feld automatisch mitgeprueft wird."""
    from output.renderers.alert.model import OnsetEvent
    from services.rain_extent import RainZone

    sonder = {
        "onset_minutes": 33, "onset_time": "00:05", "km_from": 1.5, "km_to": 9.0,
        "is_convective": True, "intensity_label": "starker Regen",
        "source_label": "Radar (DWD)",
        "rain_zones": (RainZone(km_from=1.5, km_to=3.0, onset_minutes=33,
                                event_end_minutes=70),),
        "gap_km": (2.5, 4.0),
    }
    werte = {}
    for f in dataclasses.fields(OnsetEvent):
        if f.name in sonder:
            werte[f.name] = sonder[f.name]
            continue
        default = f.default
        if isinstance(default, bool):
            werte[f.name] = not default
        elif isinstance(default, int):
            werte[f.name] = default + 1
        else:  # None-Defaults: Text bzw. Zahl je nach Feldtyp
            werte[f.name] = 7 if "int" in str(f.type) or "float" in str(f.type) else f"w-{f.name}"
    return werte


class TestBausteinAusFeldern:
    def test_jedes_feld_wird_uebernommen(self):
        """Generisch: ein Objekt mit ALLEN OnsetEvent-Feldern ergibt ein Event,
        in dem jedes Feld 1:1 steht -- auch kuenftige Felder."""
        from output.renderers.alert.project import onset_event_from_fields

        werte = _werte_ungleich_default()
        ev = onset_event_from_fields(SimpleNamespace(**werte))
        for name, wert in werte.items():
            assert getattr(ev, name) == wert, name

    def test_fehlende_felder_haben_die_defaults(self):
        from output.renderers.alert.model import OnsetEvent
        from output.renderers.alert.project import onset_event_from_fields

        pflicht = dict(onset_minutes=12, onset_time="10:12", km_from=0.0, km_to=1.0,
                       is_convective=False, intensity_label="x", source_label="y")
        ev = onset_event_from_fields(SimpleNamespace(**pflicht))
        assert ev == OnsetEvent(**pflicht)

    def test_override_und_unhashbare_folgen(self):
        """Versand: `stage_number` kommt als Override; Listen aus dem Request
        werden zu Tupeln (das Event ist frozen und muss hashbar bleiben)."""
        from output.renderers.alert.project import onset_event_from_fields
        from services.rain_extent import RainZone

        zone = RainZone(km_from=1.0, km_to=2.0, onset_minutes=5, event_end_minutes=None)
        quelle = SimpleNamespace(
            onset_minutes=5, onset_time="10:05", km_from=0.0, km_to=2.0,
            is_convective=False, intensity_label="x", source_label="y",
            rain_zones=[zone], gap_km=[1.5], stage_number=None,
        )
        ev = onset_event_from_fields(quelle, stage_number=4)
        assert ev.stage_number == 4
        assert ev.rain_zones == (zone,)
        assert ev.gap_km == (1.5,)
        hash(ev)

    def test_laufend_ohne_beginn_wird_null_minuten(self):
        """Request bei laufendem Regen ohne kuenftigen Beginn traegt
        `onset_minutes=None`; der Renderer-Vertrag verlangt eine Zahl."""
        from output.renderers.alert.project import onset_event_from_fields

        quelle = SimpleNamespace(
            onset_minutes=None, already_running=True, onset_time="22:30",
            km_from=0.0, km_to=2.0, is_convective=False, intensity_label="x",
            source_label="y",
        )
        assert onset_event_from_fields(quelle).onset_minutes == 0

    def test_echter_radar_alert_request(self):
        """Der echte Trip-Versandbuendel geht 1:1 hinein (Request-eigene
        Felder wie `tz` oder `segment_date` werden ignoriert)."""
        from output.renderers.alert.project import onset_event_from_fields
        from services.notification_service import RadarAlertRequest

        req = RadarAlertRequest(
            onset_minutes=20, onset_time="12:20", km_from=3.0, km_to=8.0,
            is_convective=False, intensity_label="leichter Regen",
            source_label="Radar (DWD)", tz=BERLIN, segment_id="3",
            onset_precip_mm=1.1, event_end_time="13:00", km_measured=True,
            convective_checked=False,
        )
        ev = onset_event_from_fields(req, stage_number=2)
        assert (ev.segment_id, ev.onset_precip_mm, ev.event_end_time) == ("3", 1.1, "13:00")
        assert ev.km_measured is True and ev.convective_checked is False
        assert ev.stage_number == 2


# ─────────────────────── Ortsvergleich nutzt den Baustein ─────────────────


def test_ac2_ortsvergleich_events_entsprechen_dem_baustein():
    """AC-2: jedes Event des Ortsvergleich-Buendels ist genau das, was der
    Baustein mit den Vergleichs-Eingaben (roh `intensity_label`/`source`,
    Ortszeitzone, Ortslabel) baut -- es gibt keine zweite Herleitung mehr."""
    from freezegun import freeze_time

    from app.ampel import resolve_ampel
    from output.renderers.alert.project import (
        onset_event_from_nowcast, to_multi_location_onset_alert_message,
    )

    orte = [
        ("Hütte Berlin", SimpleNamespace(lat=52.52, lon=13.40, timezone="Europe/Berlin"),
         _nc(onset_minutes=45, event_end_minutes=95, onset_precip_mm=2.4)),
        ("Lissabon", SimpleNamespace(lat=38.72, lon=-9.14, timezone="Europe/Lisbon"),
         _nc(onset_minutes=None, already_running=True, event_end_minutes=30)),
    ]
    with freeze_time(JETZT):
        msg = to_multi_location_onset_alert_message(
            orte, tz=UTC, stand_at="22:30", ampel=resolve_ampel(None),
        )
    erwartet = {
        name: onset_event_from_nowcast(
            nc, now_utc=JETZT, tz=ZoneInfo(loc.timezone),
            intensity_label=nc.intensity_label, source_label=nc.source,
            location_label=name,
        )
        for name, loc, nc in orte
    }
    assert [e.location_label for e in msg.events] == ["Lissabon", "Hütte Berlin"]
    for ev in msg.events:
        assert ev == erwartet[ev.location_label]


# ─────────────────────── Ratsche Feldsatz (AC-6) ──────────────────────────


def fehlende_felder_im_trip_buendel(event_cls, request_cls, ausnahmen) -> set[str]:
    """Felder des Events, die weder im Versandbuendel noch in der
    Ausnahmeliste stehen -- dort fehlten sie still auf dem Trip-Pfad."""
    event = {f.name for f in dataclasses.fields(event_cls)}
    request = {f.name for f in dataclasses.fields(request_cls)}
    return event - request - set(ausnahmen)


def test_ac6_ratsche_jedes_eventfeld_reist_im_trip_buendel():
    from output.renderers.alert.model import OnsetEvent
    from services.notification_service import RadarAlertRequest

    assert fehlende_felder_im_trip_buendel(
        OnsetEvent, RadarAlertRequest, AUSNAHMEN_TRIP_BUENDEL,
    ) == set()
    # Die Ausnahmeliste ist kein Abstellgleis: jeder Eintrag ist ein echtes Feld.
    namen = {f.name for f in dataclasses.fields(OnsetEvent)}
    assert AUSNAHMEN_TRIP_BUENDEL <= namen


def test_ac6_mutationsprobe_neues_feld_macht_die_ratsche_rot():
    """AC-6 Mutationsprobe: ein neues OnsetEvent-Feld ohne Gegenstueck im
    Buendel und ohne Ausnahme-Eintrag wird gemeldet."""
    from output.renderers.alert.model import OnsetEvent
    from services.notification_service import RadarAlertRequest

    erweitert = dataclasses.make_dataclass(
        "OnsetEventMitNeuemFeld", [("neues_feld_2982", int, dataclasses.field(default=0))],
        bases=(OnsetEvent,), frozen=True,
    )
    assert fehlende_felder_im_trip_buendel(
        erweitert, RadarAlertRequest, AUSNAHMEN_TRIP_BUENDEL,
    ) == {"neues_feld_2982"}


# ─────────────────────── Ratsche Bau (AC-7) ───────────────────────────────

ERLAUBTER_BAUORT = Path("src/output/renderers/alert/project.py")


def _onset_event_bauorte(wurzeln) -> list[str]:
    funde = []
    for wurzel in wurzeln:
        for pfad in sorted((ROOT / wurzel).rglob("*.py")):
            baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Call):
                    continue
                f = knoten.func
                name = f.id if isinstance(f, ast.Name) else (
                    f.attr if isinstance(f, ast.Attribute) else None
                )
                if name == "OnsetEvent":
                    funde.append(f"{pfad.relative_to(ROOT)}:{knoten.lineno}")
    return funde


def test_ac7_onset_event_wird_nur_im_baustein_gebaut():
    funde = _onset_event_bauorte(["src", "api"])
    fremd = [f for f in funde if not f.startswith(str(ERLAUBTER_BAUORT) + ":")]
    assert fremd == [], f"OnsetEvent( ausserhalb von project.py gebaut: {fremd}"
    assert funde, "Voraussetzung: der Baustein selbst baut OnsetEvent"


def test_ac7_testmail_fixture_baut_ueber_den_baustein():
    """AC-7: das Test-Mail-Werkzeug geht ueber den Baustein statt eine
    eigene Feldliste zu pflegen."""
    assert _onset_event_bauorte(["scripts"]) == []


# ─────────────────────── Altform entfernt (AC-8) ──────────────────────────


def test_ac8_altform_ist_entfernt():
    import services.radar_alert_service as ras

    assert not hasattr(ras, "build_onset_alert_message")
