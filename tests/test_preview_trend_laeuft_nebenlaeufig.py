"""Kern-Schicht: in der Trip-Vorschau laeuft der Etappen-Trend gleichzeitig zu
Hauptabruf plus Nachtwetter (#1839, Epic #2733 Strang C).

Spec: docs/specs/modules/fix_1839_trip_vorschau_kalt.md (AC-3, AC-4, AC-5)

Defekt: ``PreviewService._build_report`` ruft ``_fetch_weather``,
``fetch_night_weather`` und ``_build_stage_trend`` nacheinander auf. Der Trend
ist von beidem unabhaengig; kalt addieren sich die Wartezeiten (502 nach 30 s).

Kein Mock der eigenen Annahme: die Abrufe werden durch ECHTE, kurz schlafende
Funktionen ersetzt (je ``_DAUER`` s), die danach das Original aufrufen
(Demo-Modus, netzfrei). Gemessen werden Gesamtzeit und Zeitstempel.
"""
from __future__ import annotations

import contextvars
import dataclasses
import json
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.loader import load_trip_from_dict
from services import segment_weather as sw
from services.preview_service import PreviewService
from services.trip_report_scheduler import TripReportSchedulerService

_DAUER = 0.3
_TRIP_JSON = (
    Path(__file__).resolve().parent / "fixtures" / "data_root" / "users" / "default"
    / "trips" / "gr221-mallorca.json"
)
_PROBE: contextvars.ContextVar[str] = contextvars.ContextVar("probe_1839", default="LEER")


def _trip(name_suffix: str = ""):
    trip = load_trip_from_dict(json.loads(_TRIP_JSON.read_text(encoding="utf-8")))
    heute = datetime.now(timezone.utc).date()
    stage1 = dataclasses.replace(
        trip.stages[0], date=heute,
        name=(trip.stages[0].name + name_suffix),
    )
    return dataclasses.replace(trip, stages=[stage1] + list(trip.stages[1:])), heute


def _bau(trip, heute: date, user_id: str = "nutzer-a"):
    return PreviewService()._build_report(
        trip, heute, "evening", now_utc=datetime.now(timezone.utc),
        demo=True, user_id=user_id,
    )


class _Spur:
    def __init__(self):
        self.iv: dict[str, tuple[float, float]] = {}
        self.probe: dict[str, str] = {}
        self.user: dict[str, str | None] = {}


@pytest.fixture
def spur(monkeypatch):
    s = _Spur()
    monkeypatch.setattr(sw, "night_weather_needed", lambda dc: True)

    orig_fetch = TripReportSchedulerService._fetch_weather
    orig_trend = TripReportSchedulerService._build_stage_trend
    orig_night = sw.fetch_night_weather

    def fetch(self, segments, provider=None):
        t0 = time.monotonic()
        time.sleep(_DAUER)
        try:
            return orig_fetch(self, segments, provider=provider)
        finally:
            s.iv["fetch"] = (t0, time.monotonic())
            s.user["fetch"] = self._user_id

    def trend(self, *a, **kw):
        t0 = time.monotonic()
        time.sleep(_DAUER)
        s.probe["trend"] = _PROBE.get()
        try:
            return orig_trend(self, *a, **kw)
        finally:
            s.iv["trend"] = (t0, time.monotonic())
            s.user["trend"] = self._user_id

    def night(*a, **kw):
        t0 = time.monotonic()
        time.sleep(_DAUER)
        try:
            return orig_night(*a, **kw)
        finally:
            s.iv["night"] = (t0, time.monotonic())

    monkeypatch.setattr(TripReportSchedulerService, "_fetch_weather", fetch)
    monkeypatch.setattr(TripReportSchedulerService, "_build_stage_trend", trend)
    monkeypatch.setattr(sw, "fetch_night_weather", night)
    return s


def test_ac3_trend_laeuft_gleichzeitig_zu_hauptabruf_und_nachtwetter(spur):
    """AC-3: Gesamtzeit nahe am laengeren Teil (2 x 0,3 s), nicht an der Summe (0,9 s)."""
    trip, heute = _trip()
    _PROBE.set("kontext-wert")
    t0 = time.monotonic()
    _bau(trip, heute)
    gesamt = time.monotonic() - t0

    assert set(spur.iv) == {"fetch", "night", "trend"}, f"Testaufbau: Zweige fehlen {spur.iv}"
    t_start, t_ende = spur.iv["trend"]
    haupt_start, haupt_ende = spur.iv["fetch"][0], spur.iv["night"][1]
    ueberlappung = min(t_ende, haupt_ende) - max(t_start, haupt_start)
    assert ueberlappung >= _DAUER, (
        f"AC-3: Trend und Hauptabruf+Nachtwetter ueberlappen nur {ueberlappung:.2f}s "
        f"(erwartet >= {_DAUER}s) -- der Trend laeuft noch hinter dem Nachtwetter "
        f"(Gesamtzeit {gesamt:.2f}s)"
    )
    # Der Nachtabruf haengt vom Hauptabruf ab und bleibt danach.
    assert spur.iv["night"][0] >= spur.iv["fetch"][1] - 0.01


def test_ac3_trend_zweig_sieht_dieselben_contextvar_werte(spur):
    """AC-3: ContextVar-Werte (z. B. call_log-Quelle) kommen im Trend-Zweig an."""
    trip, heute = _trip()
    _PROBE.set("kontext-wert-1839")
    _bau(trip, heute)
    assert spur.probe["trend"] == "kontext-wert-1839"


def test_ac3_ergebnis_identisch_zur_referenz(monkeypatch):
    """AC-3: zwei Laeufe mit gleichem Zeitpunkt liefern denselben Bericht (Regressionswache)."""
    monkeypatch.setattr(sw, "night_weather_needed", lambda dc: True)
    trip, heute = _trip()
    jetzt = datetime.now(timezone.utc)
    ref, *_ = PreviewService()._build_report(
        trip, heute, "evening", now_utc=jetzt, demo=True, user_id="nutzer-a")
    neu, *_ = PreviewService()._build_report(
        trip, heute, "evening", now_utc=jetzt, demo=True, user_id="nutzer-a")
    assert neu.sms_text == ref.sms_text
    assert neu.email_subject == ref.email_subject
    assert neu.telegram_bubbles == ref.telegram_bubbles


def test_ac4_trend_wirft_gleiche_ausnahme_kein_verwaister_thread(monkeypatch, spur):
    """AC-4 (Trend): dieselbe Ausnahme-Art wie im seriellen Aufruf; keine Rest-Threads."""
    def kaputt(self, *a, **kw):
        raise ValueError("trend kaputt 1839")
    trip, heute = _trip()
    _bau(trip, heute)  # Aufwaermlauf: gemeinsamer Pool legt seine Worker an
    monkeypatch.setattr(TripReportSchedulerService, "_build_stage_trend", kaputt)
    vorher = threading.active_count()
    with pytest.raises(ValueError, match="trend kaputt 1839"):
        _bau(trip, heute)
    time.sleep(0.05)
    assert threading.active_count() <= vorher, "AC-4: verwaister Thread nach Trend-Fehler"


def test_ac4_hauptabruf_wirft_trend_thread_wird_nicht_verwaist(monkeypatch, spur):
    """AC-4 (Hauptabruf): Ausnahme steigt wie heute auf; Trend-Thread ist danach beendet."""
    def kaputt(self, segments, provider=None):
        raise RuntimeError("abruf kaputt 1839")
    trip, heute = _trip()
    _bau(trip, heute)  # Aufwaermlauf: gemeinsamer Pool legt seine Worker an
    monkeypatch.setattr(TripReportSchedulerService, "_fetch_weather", kaputt)
    vorher = threading.active_count()
    with pytest.raises(RuntimeError, match="abruf kaputt 1839"):
        _bau(trip, heute)
    time.sleep(0.05)
    assert threading.active_count() <= vorher, "AC-4: verwaister Trend-Thread nach Hauptabruf-Fehler"


def test_ac5_zwei_nutzer_parallel_jeder_nur_eigene_daten(spur):
    """AC-5: zwei Nutzer rufen gleichzeitig; Bericht traegt nur die eigene Kennung."""
    trip_a, heute = _trip(" ALPHA1839")
    trip_b, _ = _trip(" BETA1839")
    ergebnis: dict[str, tuple] = {}

    def lauf(uid, trip):
        ergebnis[uid] = _bau(trip, heute, user_id=uid)

    ts = [threading.Thread(target=lauf, args=(u, t)) for u, t in
          (("nutzer-a", trip_a), ("nutzer-b", trip_b))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    for uid, eigen, fremd in (("nutzer-a", "ALPHA1839", "BETA1839"),
                              ("nutzer-b", "BETA1839", "ALPHA1839")):
        report, _sw, stage_name, _tz = ergebnis[uid]
        assert eigen in (stage_name or ""), f"{uid}: eigene Etappe fehlt ({stage_name})"
        assert fremd not in (stage_name or "") and fremd not in (report.email_plain or "")
