"""Kern-Schicht: in der Trip-Vorschau laeuft der Etappen-Trend gleichzeitig zu
Hauptabruf plus Nachtwetter (#1839, Epic #2733 Strang C).

Spec: docs/specs/modules/fix_1839_trip_vorschau_kalt.md (AC-3, AC-4, AC-5)

Defekt: ``PreviewService._build_report`` ruft ``_fetch_weather``,
``fetch_night_weather`` und ``_build_stage_trend`` nacheinander auf. Der Trend
ist von beidem unabhaengig; kalt addieren sich die Wartezeiten (502 nach 30 s).

Kein Mock der eigenen Annahme: die Abrufe werden durch ECHTE, kurz schlafende
Funktionen ersetzt (je ``_DAUER`` s), die danach das Original aufrufen
(Demo-Modus, netzfrei). Die Gleichzeitigkeit (AC-3) wird ueber Ereignisse
geprueft, nicht ueber Wanduhr-Ueberlappung (#3248: unter CI-Last kippte die
Messung an der Grenze 0,30 s).
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


#: Namenspraefix des Trend-Pools der Vorschau (``ThreadPoolExecutor(
#: thread_name_prefix="preview-trend")`` in ``services.trip_briefing_aufbau``).
#: Gezaehlt werden NUR diese Threads -- der globale ``threading.active_count()``
#: schwankte durch unbeteiligte Pools (Cache, Abruf-Pool) und machte den Test
#: flaky (#3128 Adversary F006).
_TREND_PRAEFIX = "preview-trend"


def _trend_threads() -> list[str]:
    return [t.name for t in threading.enumerate()
            if t.name.startswith(_TREND_PRAEFIX) and t.is_alive()]


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


#: Wartegrenze je Treffpunkt. Im nebenlaeufigen Ablauf kommt jedes Ereignis
#: sofort; nur ein SERIELLER Ablauf laeuft hier hinein (dann ist der Test rot).
#: Einmal 10 s bleibt unter dem globalen ``timeout = 30``.
_TREFF_FRIST = 10.0


@pytest.fixture
def treffpunkt(monkeypatch):
    """AC-3 ohne Wanduhr (#3248): die drei Zweige verabreden sich ueber Ereignisse.

    Der Trend kehrt erst zurueck, wenn das Nachtwetter FERTIG ist; der
    Hauptabruf beginnt erst, wenn der Trend LAEUFT. Gleichzeitig heisst damit:
    der Trend ist beim Start des Hauptabrufs und beim Start des Nachtwetters
    noch nicht fertig und erlebt das Ende des Nachtwetters -- er umspannt
    Hauptabruf plus Nachtwetter ganz. Seriell (Trend davor oder dahinter)
    wartet ein Zweig vergeblich bis ``_TREFF_FRIST``, der Befund wird rot.
    """
    ev = {n: threading.Event() for n in
          ("trend_start", "trend_ende", "fetch_ende", "night_ende")}
    befund: dict[str, object] = {"aufrufe": []}
    monkeypatch.setattr(sw, "night_weather_needed", lambda dc: True)
    orig_fetch = TripReportSchedulerService._fetch_weather
    orig_trend = TripReportSchedulerService._build_stage_trend
    orig_night = sw.fetch_night_weather

    def trend(self, *a, **kw):
        befund["aufrufe"].append("trend")
        ev["trend_start"].set()
        try:
            befund["trend_erlebt_nacht_ende"] = ev["night_ende"].wait(_TREFF_FRIST)
            return orig_trend(self, *a, **kw)
        finally:
            ev["trend_ende"].set()

    def fetch(self, segments, provider=None):
        befund["aufrufe"].append("fetch")
        gestartet = ev["trend_start"].wait(_TREFF_FRIST)
        befund["trend_laeuft_bei_fetch"] = gestartet and not ev["trend_ende"].is_set()
        try:
            return orig_fetch(self, segments, provider=provider)
        finally:
            ev["fetch_ende"].set()

    def night(*a, **kw):
        befund["aufrufe"].append("night")
        befund["nacht_nach_fetch"] = ev["fetch_ende"].is_set()
        befund["trend_laeuft_bei_nacht"] = (
            ev["trend_start"].is_set() and not ev["trend_ende"].is_set())
        try:
            return orig_night(*a, **kw)
        finally:
            ev["night_ende"].set()

    monkeypatch.setattr(TripReportSchedulerService, "_fetch_weather", fetch)
    monkeypatch.setattr(TripReportSchedulerService, "_build_stage_trend", trend)
    monkeypatch.setattr(sw, "fetch_night_weather", night)
    return befund


def test_ac3_trend_laeuft_gleichzeitig_zu_hauptabruf_und_nachtwetter(treffpunkt):
    """AC-3: der Trend laeuft waehrend Hauptabruf UND Nachtwetter (Ereignisse, keine Wanduhr)."""
    trip, heute = _trip()
    _bau(trip, heute)

    assert sorted(treffpunkt["aufrufe"]) == ["fetch", "night", "trend"], (
        f"Testaufbau: jeder Zweig genau einmal erwartet, war {treffpunkt['aufrufe']}")
    assert treffpunkt["trend_laeuft_bei_fetch"], (
        "AC-3: beim Start des Hauptabrufs lief der Trend nicht (noch nicht gestartet "
        f"binnen {_TREFF_FRIST}s oder schon fertig) -- seriell statt gleichzeitig")
    assert treffpunkt["trend_laeuft_bei_nacht"], (
        "AC-3: beim Start des Nachtwetters lief der Trend nicht -- seriell statt gleichzeitig")
    assert treffpunkt["trend_erlebt_nacht_ende"], (
        f"AC-3: der Trend wartete {_TREFF_FRIST}s vergeblich auf das Ende des "
        "Nachtwetters -- Nachtwetter laeuft erst hinter dem Trend (seriell)")
    # Der Nachtabruf haengt vom Hauptabruf ab und bleibt danach.
    assert treffpunkt["nacht_nach_fetch"], "Nachtwetter begann vor Ende des Hauptabrufs"


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
    with pytest.raises(ValueError, match="trend kaputt 1839"):
        _bau(trip, heute)
    time.sleep(0.05)
    assert _trend_threads() == [], "AC-4: verwaister Thread nach Trend-Fehler"


def test_ac4_hauptabruf_wirft_trend_thread_wird_nicht_verwaist(monkeypatch, spur):
    """AC-4 (Hauptabruf): Ausnahme steigt wie heute auf; Trend-Thread ist danach beendet."""
    def kaputt(self, segments, provider=None):
        raise RuntimeError("abruf kaputt 1839")
    trip, heute = _trip()
    _bau(trip, heute)  # Aufwaermlauf: gemeinsamer Pool legt seine Worker an
    monkeypatch.setattr(TripReportSchedulerService, "_fetch_weather", kaputt)
    with pytest.raises(RuntimeError, match="abruf kaputt 1839"):
        _bau(trip, heute)
    time.sleep(0.05)
    assert _trend_threads() == [], "AC-4: verwaister Trend-Thread nach Hauptabruf-Fehler"


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
