"""Fix-Loop 1 (#3128): Testluecken aus dem Adversary-Protokoll schliessen.

SPEC: docs/specs/modules/trip_briefing_aufbau.md (AC-1, AC-2, AC-6, AC-7)
Protokoll: docs/artifacts/feat-3128-trip-gemeinsamer-berichtsaufbau/adversary-dialog.md

Je Finding ein Nachweis dort, wo die Zusicherung WIRKT:

* F001 (AC-2): Demo-Vorschau holt das Hauptwetter ueber den Fixture-Provider
  -- beobachtbar am Ergebnis (bei totalem Ausfall des Normalabrufs gibt es
  trotzdem einen Bericht).
* F002 (AC-7): die Phasenuhr des Versands misst Nacht, Ausblick und
  Gewitter-Vorschau -- beobachtbar an den ``befehl_dauer``-Phasenzeilen.
* F003 (AC-1): Starkregen-Hinweis, Nicht-Zugestelltes, Kurzkennung, exponierte
  Abschnitte und Datenluecke kommen im Versand an (Golden + sichtbar).
* F004 (AC-1/AC-2): Wetterlage-Label und Ausblick-Spalten des Morgenberichts.
* F005 (AC-2/AC-6): die Vorschau schreibt keine nachgetragenen Kilometer in
  den Trip-Bestand (Trip-Datei byte-gleich).

Golden-Werte (``tests/golden/trip_briefing_aufbau/luecke_*``) wurden mit dem
Code VOR dem Umbau erzeugt (Stand ``HEAD`` vor #3128-Implementierung, per
``git archive`` in ein Scratch-Verzeichnis exportiert und dort mit
``GZ_GOLDEN_ERZEUGEN=3128`` gefahren). Bestehende Golden bleiben unberuehrt.

KEINE Mocks. Naehte wie in ``test_trip_briefing_aufbau.py``: feste Uhr,
Fixture-Wetter, Transport-Mitschrift. Zusaetzlich:
* ergaenzende Huelle um ``NotificationService.send_trip_report``, die dem
  echten Scheduler-Auftrag Felder hinzufuegt, die offline keine Quelle haben
  (Radar-Starkregen, Grat-Abschnitte, Kurzkennung, Nachtreihe) und dann das
  Original ruft -- gerendert und zugestellt wird echt;
* Nicht-Zugestelltes ueber den echten Protokoll-Schreibweg ``alert_log``;
* Ensemble-Konfidenz (offline nicht vorhanden) wird nach dem echten Abruf auf
  die Datenpunkte geschrieben, wie es ``_enrich_ensemble_for_trip`` tut;
* kurz schlafende Huellen um die echten Phasen-Methoden (Muster
  ``tests/test_preview_trend_laeuft_nebenlaeufig.py``).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.tdd.test_trip_briefing_aufbau import (
    ETAPPE_A,
    FIXTURES,
    INNSBRUCK,
    NUTZER_A,
    STUBAI,
    TAG,
    TRIP_A,
    TRIP_NAME_A,
    _golden_pfad,
    _golden_pruefen,
    _trip,
    _trip_anlegen,
    _tupel_inhalt,
    _versand,
    _vorschau_bericht,
)
from tests.tdd import test_trip_briefing_aufbau as _basis

# Fixture aus der Basisdatei uebernehmen (Zuweisung statt Import, sonst F811).
env = _basis.env

# ---------------------------------------------------------------------------
# F001 (AC-2): Demo-Vorschau nutzt im Hauptabruf den Fixture-Provider
# ---------------------------------------------------------------------------


def test_f001_demo_vorschau_holt_hauptwetter_ueber_fixture_provider(env, monkeypatch, tmp_path):
    """AC-2 (Demo-Daten, #483): Given der normale Wetterweg liefert nichts
    (leeres Fixture-Verzeichnis = Totalausfall) / When die Vorschau ohne Demo
    laeuft / Then hat jedes Segment nur einen Fehler-Platzhalter; When dieselbe
    Vorschau mit ``demo=True`` laeuft / Then liefert sie einen Bericht mit
    Wetter fuer jedes Segment -- der Hauptabruf lief ueber den Demo-Provider.

    Faengt: ``trip_wetter_laden`` ignoriert ``provider`` (Live-Abruf statt Demo)."""
    from services.preview_service import PreviewService
    from services.weather_cache import reset_shared_weather_cache_for_tests

    leer = tmp_path / "fixtures-leer"
    leer.mkdir()
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(leer))
    reset_shared_weather_cache_for_tests()

    svc = PreviewService()
    trip = svc._load_trip(TRIP_A, NUTZER_A)
    jetzt = datetime.now(timezone.utc)

    _r, ohne_demo, _s, _t = svc._build_report(trip, TAG, "morning", now_utc=jetzt,
                                               user_id=NUTZER_A)
    assert ohne_demo and all(s.has_error for s in ohne_demo), (
        "Vorbedingung: ohne Demo faellt der Hauptabruf fuer jedes Segment aus"
    )

    reset_shared_weather_cache_for_tests()
    report, segment_weather, stage_name, _tz = svc._build_report(
        trip, TAG, "morning", now_utc=jetzt, demo=True, user_id=NUTZER_A,
    )
    assert segment_weather and not any(s.has_error for s in segment_weather), (
        "AC-2: Demo-Vorschau hat das Hauptwetter nicht ueber den Demo-Provider geholt"
    )
    assert report.sms_text and ETAPPE_A in (stage_name or ""), report.sms_text


# ---------------------------------------------------------------------------
# F002 (AC-7): Phasenuhr misst jede Phase des Versands
# ---------------------------------------------------------------------------

_RE_PHASE = re.compile(r"phase=(\w+) trip=(\S+) dauer_ms=(\d+)")
#: Dauer, die jede beobachtete Phase auf der (eingefrorenen) Uhr verbraucht.
_SCHLAF = timedelta(milliseconds=150)


def _phasen(caplog, trip_id: str) -> dict[str, int]:
    phasen: dict[str, int] = {}
    for r in caplog.records:
        if r.name != "befehl_dauer":
            continue
        m = _RE_PHASE.search(r.getMessage())
        if m and m.group(2) == trip_id:
            phasen[m.group(1)] = int(m.group(3))
    return phasen


def _schlafend(monkeypatch, cls, name: str) -> None:
    """Echte Methode, die vorher ``_SCHLAF`` auf der Uhr verbraucht (macht die
    Phase messbar). Die Uhr ist per ``freezegun`` eingefroren (auch
    ``time.monotonic`` der Phasenuhr), darum wird sie vorgerueckt statt zu
    schlafen."""
    import freezegun.api

    original = getattr(cls, name)

    def _langsam(self, *a, **k):
        freezegun.api.freeze_factories[-1].tick(_SCHLAF)
        return original(self, *a, **k)

    monkeypatch.setattr(cls, name, _langsam)


@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_f002_phasenuhr_misst_nacht_ausblick_und_gewitter(env, monkeypatch, caplog, report_type):
    """AC-7: Given ein regulaerer Versand, dessen Nachtabruf, Ausblick und
    Gewitter-Vorschau je messbar Zeit brauchen / When er laeuft / Then
    schreibt die Phasenuhr je eine Phasenzeile ``nacht``, ``gewitter_vorschau``
    und (nur abends, Ausblick an) ``ausblick`` mit mindestens dieser Dauer --
    die Zeit landet in der richtigen Phase, nicht im Rest.

    Faengt: Phasen-Rueckruf ``phase=uhr.wechsel`` entfernt, einzelne
    ``phase(...)``-Aufrufe im Baustein entfernt."""
    from services.trip_report_scheduler import TripReportSchedulerService as S

    for name in ("_fetch_night_weather", "_build_stage_trend",
                 "_build_thunder_forecast_from_trend_or_fetch"):
        _schlafend(monkeypatch, S, name)
    caplog.set_level(logging.INFO, logger="befehl_dauer")

    _versand(env, NUTZER_A, TRIP_A, report_type)
    phasen = _phasen(caplog, TRIP_A)

    erwartet = ["nacht", "gewitter_vorschau"] + (["ausblick"] if report_type == "evening" else [])
    for name in erwartet:
        assert name in phasen, f"AC-7: Phase {name!r} nicht gemessen: {phasen}"
        assert phasen[name] >= _SCHLAF.total_seconds() * 1000 * 0.9, (
            f"AC-7: Phase {name!r} misst nicht ihre Arbeit ({phasen[name]} ms): {phasen}"
        )
    if report_type == "morning":
        assert "ausblick" not in phasen, f"Ausblick morgens aus, trotzdem gemessen: {phasen}"
    for name in ("zieltag", "rendern", "versand"):
        assert name in phasen, f"Vorbedingung: Phase {name!r} fehlt: {phasen}"


# ---------------------------------------------------------------------------
# F003 (AC-1): Zusatzbloecke des Versands kommen byte-gleich an
# ---------------------------------------------------------------------------


def _anfrage_ergaenzen(monkeypatch, **felder) -> None:
    """Huelle um den echten Versand: ergaenzt den vom Scheduler gebauten
    Auftrag um Felder ohne Offline-Quelle und ruft dann das Original."""
    import services.notification_service as ns

    original = ns.NotificationService.send_trip_report

    def _ergaenzt(self, request):
        return original(self, dataclasses.replace(request, **felder))

    monkeypatch.setattr(ns.NotificationService, "send_trip_report", _ergaenzt)


def _undelivered_anlegen(uid: str, trip_id: str) -> None:
    """Echter Protokoll-Eintrag: ein Alarm ohne Vergleichsbasis erreichte
    E-Mail und Telegram nicht (``undelivered_since_last_briefing`` liest ihn
    auch ohne Anker, #2050 Sz.12)."""
    from services import alert_log

    alert_log.append_suppressed_entry(
        uid, entity_id=trip_id, entity_type="trip",
        reason=alert_log.REASON_NOWCAST,
        gate_reason=alert_log.REASON_NO_REFERENCE_BASIS,
        effective_channels=["email", "telegram"],
    )


def _grat():
    from app.models import ExposedSection

    return [ExposedSection(start_km=0.0, end_km=30.0, max_elevation_m=2400.0,
                           exposition_type="GRAT")]


def _fixtures_abwandeln(ziel: Path, *, ohne=()) -> Path:
    """Kopie der Fixture-Reihen ohne die Reihen in ``ohne`` (Teilausfall)."""
    ziel.mkdir(parents=True, exist_ok=True)
    for name in ("innsbruck.json", "stubai.json", "zillertal.json"):
        if name not in ohne:
            (ziel / name).write_text((FIXTURES / name).read_text())
    return ziel


def _wetter_setzen(monkeypatch, ordner: Path) -> None:
    from services.weather_cache import reset_shared_weather_cache_for_tests

    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(ordner))
    reset_shared_weather_cache_for_tests()


#: fall -> (Wetter-Abwandlung oder None, Ergaenzung des Auftrags oder None)
_F003_FAELLE = {
    # Radar-Rohdaten wie vom Scheduler: (Label, Beginn, Ende, R4, laeuft, Reichweite)
    "starkregen": (None, lambda mp: _anfrage_ergaenzen(
        mp, starkregen_nowcast=("starker Regen", 25, 70, False, False, 90))),
    "undelivered": (None, lambda mp: _undelivered_anlegen(NUTZER_A, TRIP_A)),
    "shortcode": (None, lambda mp: _anfrage_ergaenzen(mp, shortcode="HN7")),
    # Teilausfall: das Segment ab Stubai hat kein Wetter -> Stundenluecke im
    # Tagesfenster, ``has_gap`` True (echt berechnet, keine Ergaenzung).
    "has_gap": (dict(ohne=("stubai.json",)), None),
}


@pytest.mark.parametrize("fall", list(_F003_FAELLE))
def test_f003_zusatzbloecke_kommen_im_versand_byte_gleich_an(env, monkeypatch, tmp_path, fall):
    """AC-1: Given der regulaere Abendversand mit einem Zusatzblock
    (Starkregen-Hinweis, nicht zugestellte Meldung, Kurzkennung, exponierter
    Grat-Abschnitt bei Wind bzw. Datenluecke ``has_gap`` bei Teilausfall) /
    When er laeuft / Then weichen die zugestellten Inhalte sichtbar vom
    Versand ohne Zusatzblock ab und sind byte-gleich zum Stand vor dem Umbau.

    Faengt: ein Durchreich-Parameter (``starkregen``, ``undelivered``,
    ``shortcode``, ``exposed_sections``, ``has_gap``) wird im Render-Weg
    abgehaengt."""
    wetter, ergaenzen = _F003_FAELLE[fall]
    ohne = None
    if wetter is None:
        ohne = {k: _golden_pfad("versand_evening_langform", k).read_text(encoding="utf-8")
                for k in ("subject", "email_html", "email_text", "sms", "premium_sms",
                          "telegram")}
    else:
        # has_gap: anderes Wetter als der Vergleichs-Golden; dass die Luecke
        # selbst sichtbar ist, belegt die Mutations-Gegenprobe (Protokoll).
        _wetter_setzen(monkeypatch, _fixtures_abwandeln(tmp_path / "fx", **wetter))
    if ergaenzen is not None:
        ergaenzen(monkeypatch)
    luecke = _has_gap_beobachten(monkeypatch)
    ist = _versand(env, NUTZER_A, TRIP_A, "evening")
    # Vorbedingung: nur der has_gap-Fall hat eine Luecke (sonst bewiese der
    # Golden fuer ``has_gap`` nichts, und die anderen Faelle waeren vermengt).
    assert luecke == [fall == "has_gap"], f"Vorbedingung has_gap fuer {fall!r}: {luecke}"

    if ohne is not None:
        abweichend = [k for k in ist if ist[k] != ohne[k]]
        assert abweichend, f"AC-1: Zusatzblock {fall!r} ist in keinem Kanal sichtbar"
    _golden_pruefen(f"luecke_versand_{fall}", ist, "AC-1")


def test_f003_exponierte_abschnitte_erreichen_den_formatter(env, monkeypatch):
    """AC-1: Given der Scheduler-Auftrag traegt exponierte Grat-Abschnitte /
    When der Abendversand rendert / Then bekommt der Formatter genau diese
    Abschnitte (Aufzeichnung an ``TripReportFormatter.format_email``).

    Beobachtet am Formatter-Eingang statt an der Ausgabe, weil die Abschnitte
    heute in KEINEM Kanal sichtbar werden: ``format_email`` reicht sie an
    ``render_email`` weiter, das sie nicht an HTML/Text gibt, und die SMS baut
    ``SMSTripFormatter()`` ohne sie (vor und nach #3128 gleich). Ein Golden
    koennte das Abhaengen also nicht zeigen.

    Faengt: ``exposed_sections`` wird im Render-Weg abgehaengt."""
    grat = _grat()
    _anfrage_ergaenzen(monkeypatch, exposed_sections=grat)
    _versand(env, NUTZER_A, TRIP_A, "evening")
    aufrufe = env["beob"].format_email
    assert len(aufrufe) == 1, f"Vorbedingung: genau ein Render: {len(aufrufe)}"
    assert aufrufe[0].get("exposed_sections") == grat, (
        f"AC-1: Grat-Abschnitte kommen nicht beim Formatter an: "
        f"{aufrufe[0].get('exposed_sections')!r}"
    )


def _has_gap_beobachten(monkeypatch) -> list[bool]:
    """Aufzeichnende Huelle um die echte ``compute_has_gap``."""
    import services.notification_service as ns

    gesehen: list[bool] = []
    original = ns.compute_has_gap

    def _zaehlend(*a, **k):
        wert = original(*a, **k)
        gesehen.append(wert)
        return wert

    monkeypatch.setattr(ns, "compute_has_gap", _zaehlend)
    return gesehen


# ---------------------------------------------------------------------------
# F004 (AC-1/AC-2): Wetterlage-Label und Morgen-Ausblick
# ---------------------------------------------------------------------------


def _konfidenz_nach_abruf(monkeypatch, wert: int = 35) -> None:
    """Offline fehlt die Ensemble-Konfidenz; nach dem echten Abruf traegt
    jeder Datenpunkt sie wie nach ``_enrich_ensemble_for_trip``."""
    import services.segment_weather as sw_mod

    original = sw_mod.SegmentWeatherService.fetch_segment_weather

    def _mit_konfidenz(self, segment, *a, **k):
        daten = original(self, segment, *a, **k)
        ts = getattr(daten, "timeseries", None)
        for dp in (ts.data if ts is not None else []):
            dp.confidence_pct = wert
        return daten

    monkeypatch.setattr(sw_mod.SegmentWeatherService, "fetch_segment_weather", _mit_konfidenz)


def test_f004_wetterlage_label_in_versand_und_vorschau(env, monkeypatch):
    """AC-1/AC-2: Given Segmentwetter mit geringer Ensemble-Konfidenz fuer die
    Folgetage / When Abendversand und Abendvorschau laufen / Then traegt der
    Bericht das Wetterlage-Label (anders als ohne Konfidenz) und ist
    byte-gleich zum Stand vor dem Umbau.

    Faengt: ``stability_result`` wird nicht berechnet oder nicht gerendert."""
    from services.weather_pattern import WeatherPatternService

    _konfidenz_nach_abruf(monkeypatch)
    gesehen: list = []
    original = WeatherPatternService.compute_for_trip

    def _beobachtet(self, *a, **k):
        ergebnis = original(self, *a, **k)
        gesehen.append(ergebnis)
        return ergebnis

    monkeypatch.setattr(WeatherPatternService, "compute_for_trip", _beobachtet)

    versand = _versand(env, NUTZER_A, TRIP_A, "evening")
    assert gesehen and gesehen[-1] is not None, f"Vorbedingung: Wetterlage berechnet: {gesehen}"
    ohne = _golden_pfad("versand_evening_langform", "email_html").read_text(encoding="utf-8")
    assert versand["email_html"] != ohne, "AC-1: Wetterlage-Label erscheint nicht in der Mail"
    _golden_pruefen("luecke_versand_wetterlage", versand, "AC-1")

    vorschau = _tupel_inhalt(_vorschau_bericht(NUTZER_A, TRIP_A, "evening"))
    ohne_v = _golden_pfad("vorschau_evening", "email_html").read_text(encoding="utf-8")
    assert vorschau["email_html"] != ohne_v, "AC-2: Wetterlage-Label fehlt in der Vorschau"
    _golden_pruefen("luecke_vorschau_wetterlage", vorschau, "AC-2")


def test_f004_wetterlage_fehler_bricht_versand_nicht_ab(env, monkeypatch, caplog):
    """AC-1: Given die Wetterlage-Berechnung wirft / When der Abendversand
    laeuft / Then geht der Bericht trotzdem hinaus, byte-gleich zum Versand
    ohne Wetterlage, und der Fehler steht als Warnung im Log (nicht still).

    Faengt: Ausnahme steigt auf (kein Versand) bzw. wird still verschluckt."""
    from services.weather_pattern import WeatherPatternService

    def _kaputt(self, *a, **k):
        raise RuntimeError("wetterlage kaputt 3128")

    monkeypatch.setattr(WeatherPatternService, "compute_for_trip", _kaputt)
    caplog.set_level(logging.WARNING)

    ist = _versand(env, NUTZER_A, TRIP_A, "evening")
    _golden_pruefen("versand_evening_langform", ist, "AC-1")
    assert any("wetterlage kaputt 3128" in r.getMessage() and r.levelno >= logging.WARNING
               for r in caplog.records), "AC-1: Wetterlage-Fehler still verschluckt"


TRIP_A_MORGENAUSBLICK = "aufbau3128-trip-a-morgenausblick"


def _morgenausblick_trip_anlegen() -> None:
    """Ausblick auch morgens, Wind morgens abgewaehlt (abends an): die
    Ausblick-Spalten des Morgenberichts unterscheiden sich vom Abend-Default
    (#1720 S1)."""
    from app.loader import save_trip

    _trip_anlegen(NUTZER_A, TRIP_A_MORGENAUSBLICK, TRIP_NAME_A, ETAPPE_A)
    trip = _trip(NUTZER_A, TRIP_A_MORGENAUSBLICK)
    trip.report_config.multi_day_trend_reports = ["morning", "evening"]
    treffer = [mc for mc in trip.display_config.metrics if mc.metric_id == "wind"]
    assert treffer, "Vorbedingung: Wind-Metrik vorhanden"
    for mc in treffer:
        mc.morning_enabled = False
        mc.evening_enabled = True
    save_trip(trip, user_id=NUTZER_A)


def test_f004_morgen_ausblick_im_versand_nutzt_morgen_spalten(env):
    """AC-1: Given ein Trip mit Ausblick auch morgens und morgens abgewaehltem
    Wind / When der Morgenversand laeuft / Then enthaelt er den Ausblick mit
    den Morgen-Spalten (ohne Wind), byte-gleich zum Stand vor dem Umbau.

    Faengt: ``report_type`` wird dem Ausblick des Versands nicht mehr
    mitgegeben (Spalten nach Abend-Default, #1720 S1)."""
    _morgenausblick_trip_anlegen()
    versand = _versand(env, NUTZER_A, TRIP_A_MORGENAUSBLICK, "morning")
    zeilen = [z for z in versand["email_text"].splitlines() if z.startswith(("Fr  ", "Sa  "))]
    assert zeilen and all("Gust " in z and "Wind " not in z for z in zeilen), (
        f"Vorbedingung: Ausblick-Zeilen mit Morgen-Spalten: {zeilen}"
    )
    _golden_pruefen("luecke_versand_morgenausblick", versand, "AC-1")


def test_f004_morgen_ausblick_in_der_vorschau_nutzt_morgen_spalten(monkeypatch):
    """AC-2: Given ein Trip mit Ausblick morgens und abends, Wind morgens
    abgewaehlt / When die (Demo-)Vorschau morgens und abends gebaut wird /
    Then hat jede Ausblick-Zeile morgens genau eine Spalte weniger als abends
    (Wind fehlt) -- der Ausblick der Vorschau loest die Spalten nach dem
    Berichtstyp auf (#1720 S1).

    Ohne eingefrorene Uhr: unter ``freezegun`` laeuft der nebenlaeufige
    Vorschau-Trend (#1839) in seine Abruf-Frist (gemischte echte/eingefrorene
    ``monotonic``-Werte im Worker-Thread), dann gibt es gar keinen Ausblick.
    Beobachtet an den Zeilen, die der echte Formatter bekommt.

    Faengt: ``report_type`` wird dem Ausblick der Vorschau nicht mehr
    mitgegeben (Spalten nach Abend-Default)."""
    from output.renderers.trip_report import TripReportFormatter
    from services.preview_service import PreviewService
    from tests.test_preview_trend_laeuft_nebenlaeufig import _TRIP_JSON

    from app.loader import load_trip_from_dict

    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(FIXTURES))
    heute = datetime.now(timezone.utc).date()
    trip = load_trip_from_dict(json.loads(_TRIP_JSON.read_text(encoding="utf-8")))
    etappen = [dataclasses.replace(s, date=heute + timedelta(days=i))
               for i, s in enumerate(trip.stages[:4])]
    trip = dataclasses.replace(trip, stages=etappen)
    trip.report_config.multi_day_trend_reports = ["morning", "evening"]
    for mc in trip.display_config.metrics:
        if mc.metric_id == "wind":
            mc.morning_enabled, mc.evening_enabled = False, True

    gesehen: list[dict] = []
    original = TripReportFormatter.format_email

    def _aufzeichnend(self, *a, **k):
        gesehen.append(k)
        return original(self, *a, **k)

    monkeypatch.setattr(TripReportFormatter, "format_email", _aufzeichnend)

    spalten = {}
    for report_type in ("morning", "evening"):
        PreviewService()._build_report(trip, heute, report_type,
                                       now_utc=datetime.now(timezone.utc),
                                       demo=True, user_id="aufbau3128-vorschau")
        zeilen = gesehen[-1].get("multi_day_trend") or []
        assert zeilen, f"Vorbedingung: Vorschau-Ausblick {report_type} gebaut"
        spalten[report_type] = {len(z["cells"]) for z in zeilen}
    assert len(spalten["morning"]) == 1 and len(spalten["evening"]) == 1, spalten
    assert spalten["morning"].pop() == spalten["evening"].pop() - 1, (
        f"AC-2: Vorschau-Ausblick morgens nicht mit Morgen-Spalten: {spalten}"
    )


# ---------------------------------------------------------------------------
# F005 (AC-2/AC-6): Vorschau persistiert keinen Kilometer-Nachtrag
# ---------------------------------------------------------------------------

TRIP_A_GPX = "aufbau3128-trip-a-gpx"


def _gpx_ablegen(uid: str) -> None:
    """GPX-Track durch alle drei Wegpunkte jeder Etappe (Innsbruck -> Stubai
    -> Innsbruck+0.02): die Etappen ohne Kilometrierung sind daraus
    aufloesbar, der Versand traegt sie nach (#2036)."""
    from app.loader import get_data_dir

    stuetz = [INNSBRUCK, STUBAI, (INNSBRUCK[0] + 0.02, INNSBRUCK[1] + 0.02)]
    punkte = []
    for (a_lat, a_lon), (b_lat, b_lon) in zip(stuetz, stuetz[1:]):
        for i in range(40):
            f = i / 40
            punkte.append((a_lat + (b_lat - a_lat) * f, a_lon + (b_lon - a_lon) * f))
    punkte.append(stuetz[-1])
    trkpts = "\n".join(
        f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{600 + i}</ele></trkpt>'
        for i, (lat, lon) in enumerate(punkte)
    )
    gpx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="test-3128" xmlns="http://www.topografix.com/GPX/1/1">\n'
        '  <trk><name>aufbau3128</name><trkseg>\n'
        f'{trkpts}\n'
        '  </trkseg></trk>\n</gpx>\n'
    )
    ordner = get_data_dir(uid) / "gpx"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "aufbau3128.gpx").write_text(gpx, encoding="utf-8")


def _trip_datei(uid: str, trip_id: str) -> Path:
    from app.loader import get_data_dir

    # save_trip schreibt nach users/<uid>/briefings/<id>.json
    treffer = [p for p in (get_data_dir(uid) / "briefings").glob("*.json")
               if json.loads(p.read_text(encoding="utf-8")).get("id") == trip_id]
    assert len(treffer) == 1, f"Vorbedingung: Trip-Datei {trip_id!r}: {treffer}"
    return treffer[0]


def _kilometer_je_etappe(pfad: Path) -> dict[str, list]:
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return {s["id"]: [w.get("distance_from_start_km") for w in s.get("waypoints", [])]
            for s in daten.get("stages", [])}


@pytest.fixture
def gpx_trip(env):
    _trip_anlegen(NUTZER_A, TRIP_A_GPX, TRIP_NAME_A, ETAPPE_A)
    _gpx_ablegen(NUTZER_A)
    pfad = _trip_datei(NUTZER_A, TRIP_A_GPX)
    assert all(km is None for kms in _kilometer_je_etappe(pfad).values() for km in kms), (
        "Vorbedingung: Etappen ohne Kilometrierung"
    )
    return pfad


@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_f005_vorschau_laesst_trip_datei_unveraendert(env, gpx_trip, report_type):
    """AC-2/AC-6: Given ein Trip ohne Kilometrierung, die aus dem GPX-Bestand
    des Nutzers aufloesbar ist / When die Vorschau laeuft (abends mit Ausblick
    ueber die Folgeetappen) / Then ist die Trip-Datei danach byte-gleich --
    die Vorschau traegt nichts in den Bestand nach. Gegenprobe: der Versand
    desselben Trips traegt die Kilometer nach (Aufbau wirksam).

    Faengt: ``scheduler.persist_backfill = False`` der Vorschau entfernt."""
    vorher = gpx_trip.read_bytes()
    report, *_ = _vorschau_bericht(NUTZER_A, TRIP_A_GPX, report_type)
    assert report.sms_text, "Vorbedingung: Vorschau liefert einen Bericht"
    assert gpx_trip.read_bytes() == vorher, (
        f"AC-6: Vorschau hat den Trip-Bestand veraendert: {_kilometer_je_etappe(gpx_trip)}"
    )

    _versand(env, NUTZER_A, TRIP_A_GPX, report_type)
    km = _kilometer_je_etappe(gpx_trip)
    assert any(v is not None for kms in km.values() for v in kms), (
        f"Gegenprobe: Versand traegt aus dem GPX keine Kilometer nach: {km}"
    )


def test_f005_baustein_baut_zieltag_ohne_nachtrag_auch_bei_scharfem_scheduler(env, gpx_trip):
    """AC-6: Given ein Scheduler, dessen eigenes Nachtragen AN ist
    (``persist_backfill`` Default) / When der Baustein ``trip_briefing_bauen``
    die Vorschau des Zieltags baut / Then bleibt die Etappe des Zieltags in
    der Trip-Datei ohne Kilometer -- der Baustein selbst schaltet das
    Nachtragen fuer die Zieltag-Segmente ab (``persist=False``), unabhaengig
    vom Aufrufer.

    Faengt: ``persist=False`` im Segmentbau der Vorschau entfernt."""
    from services import trip_briefing_aufbau as aufbau
    from services.trip_report_scheduler import TripReportSchedulerService

    scheduler = TripReportSchedulerService(user_id=NUTZER_A)
    assert getattr(scheduler, "persist_backfill", True) is True, "Vorbedingung: Nachtragen an"
    trip = _trip(NUTZER_A, TRIP_A_GPX)
    ziel_etappe = trip.get_stage_for_date(TAG).id

    report, *_ = aufbau.trip_briefing_bauen(
        scheduler, trip, TAG, "morning", now_utc=datetime.now(timezone.utc), user_id=NUTZER_A,
    )
    assert report.sms_text, "Vorbedingung: Bericht gebaut"
    km = _kilometer_je_etappe(gpx_trip)
    assert all(v is None for v in km[ziel_etappe]), (
        f"AC-6: Zieltag-Etappe {ziel_etappe} wurde nachgetragen: {km[ziel_etappe]}"
    )


# ---------------------------------------------------------------------------
# AC-5 (Spec "Zirkelimport": kein Alt-Name wird entfernt):
# ``PreviewService._fetch_main_and_night`` bleibt aufrufbar
# ---------------------------------------------------------------------------


class _StubScheduler:
    """Echte kleine Klasse statt Mock: liefert ein festes Wetterergebnis und
    merkt sich, womit der Hauptabruf gerufen wurde."""

    def __init__(self, ergebnis: list):
        self._ergebnis = ergebnis
        self.aufrufe: list = []

    def _fetch_weather(self, segments, provider=None):
        self.aufrufe.append((list(segments), provider))
        return list(self._ergebnis)


def test_ac5_alt_name_fetch_main_and_night_delegiert_an_baustein(env):
    """AC-5: Given ein Trip ohne Nachtbedarf und ein Scheduler mit Wetter /
    When der Alt-Name ``PreviewService._fetch_main_and_night`` gerufen wird /
    Then liefert er dasselbe wie ``_vorschau_haupt_und_nacht``; bei leerem
    Wetter den Fehlercode ``vorschau_wetter_fehlt``.

    Faengt: Alt-Name entfernt (AttributeError) oder anders verdrahtet."""
    from services import trip_briefing_aufbau as aufbau
    from services.preview_service import PreviewService
    from services.segment_weather import night_weather_needed
    from tests.tdd.test_trip_briefing_aufbau import (
        TRIP_A_OHNE_NACHT,
        _ohne_nacht_display_config,
    )

    _trip_anlegen(NUTZER_A, TRIP_A_OHNE_NACHT, TRIP_NAME_A, ETAPPE_A,
                  display_config=_ohne_nacht_display_config(TRIP_A_OHNE_NACHT))
    trip = _trip(NUTZER_A, TRIP_A_OHNE_NACHT)
    assert not night_weather_needed(trip.display_config), "Vorbedingung: kein Nachtbedarf"

    segmente = ["seg-1", "seg-2"]
    wetter = ["wetter-1", "wetter-2"]
    alt = _StubScheduler(wetter)
    neu = _StubScheduler(wetter)

    ergebnis_alt = PreviewService._fetch_main_and_night(
        alt, segmente, trip, TAG, None, NUTZER_A,
    )
    ergebnis_neu = aufbau._vorschau_haupt_und_nacht(
        neu, segmente, trip, TAG, None, NUTZER_A,
    )
    assert ergebnis_alt == ergebnis_neu == (wetter, None)
    assert alt.aufrufe == neu.aufrufe == [(segmente, None)]

    with pytest.raises(RuntimeError) as fehler:
        PreviewService._fetch_main_and_night(
            _StubScheduler([]), segmente, trip, TAG, None, NUTZER_A,
        )
    assert getattr(fehler.value, "code", None) == "vorschau_wetter_fehlt"
