"""TDD RED — #1727 S5b: die Versandpfade folgen dem ORTSTAG der Tour.

SPEC: docs/specs/modules/fix_1727_s5b_versandpfade_ortstag.md (AC-1 bis AC-9)
KONTEXT: docs/context/fix-1727-s5b-versandpfade.md (neun Fundstellen, gemessen)
ADR-0044 (Kalendertage folgen der Ortszeit), ADR-0051 Regel 3 (keine
Umgebungsuhr — „jetzt“ kommt vom Aufrufer).

Neun Fundstellen bestimmen „welcher Kalendertag ist gemeint“ über die
Serveruhr (``date.today()``) statt über den Ortstag der Tour bzw. des ersten
auflösbaren Preset-Orts. Anders als in der Vorgängerscheibe S5a wirken sie auf
VERSENDETE Inhalte — Etappenwahl, Wetter-Input, Ausblick, Gewitter-Ausblick,
Verfall eines Nachliefer-Vermerks, Auto-Pause eines Presets, Datum im
Mail-/SMS-/Telegram-Präfix und Zieltag des Ortsvergleich-Einzelversands:

    1 ``select_test_stage``                (trip_report_scheduler.py:871)
    2 ``_send_trip_report_outcome``        (trip_report_scheduler.py:1103)
    3 ``_clamp_segments_to_today``         (trip_report_scheduler.py:1708)
    4 ``_build_stage_trend``               (trip_report_scheduler.py:2023)
    5 ``_collect_future_stage_weather``    (trip_report_scheduler.py:2416)
    6 ``briefing_target_day_is_current``   (alert_briefing_anchor.py:169)
    7 ``_auto_pause_expired_presets``      (scheduler_dispatch_service.py:79)
    8 ``_target_date_from_report``         (notification_service.py:1717)
    9 ``send_one_compare_preset``          (scheduler_dispatch_service.py:369)

ZWEI NACHWEISFORMEN, BEIDE PFLICHT WO ANWENDBAR
═══════════════════════════════════════════════════════════════════════════
(a) **Ortstag ≠ Servertag** — für alle neun. ``freeze_time`` in ein Fenster
    setzen, in dem beide auseinanderfallen; jeder Test beginnt mit dem
    Vorbedingungs-Anker ``_anker`` aus ``tests/tdd/conftest.py`` (AC-9), ohne
    den die Hauptzusicherung strukturell nie fehlschlagen könnte (#1726 F002).

(b) **Parameter gegen Systemuhr** — für die Fundstellen 1, 3, 4, 5, 6, 7,
    also überall dort, wo ein Pflichtparameter entsteht. ``freeze_time(X)``
    setzen, ``now_utc=Y`` übergeben, X und Y auf VERSCHIEDENE Ortstage
    derselben Zone. Nur diese Form fängt „Parameter entgegengenommen, im Rumpf
    ignoriert“ — in S5a waren fünf von sechs Aufrufstellen dagegen blind
    (Adversary F001). Sie steht unten in einer eigenen, parametrisierten
    Familie, deren Erwartungswerte literal nebeneinander stehen.
    An den Fundstellen 2, 8, 9 ist sie strukturell unmöglich (dort bleibt
    „jetzt“ funktionsintern, s. Spec „Known Limitations“) — nur (a).

RED-GRÜNDE (gemessen, nicht vermutet)
═══════════════════════════════════════════════════════════════════════════
* Fundstellen 1, 3, 4, 5, 7: der Pflichtparameter existiert noch nicht — die
  Aufrufe scheitern mit ``TypeError``. Alle neuen Parameter werden deshalb
  als KEYWORD übergeben: ein positionsweise durchgereichtes ``now_utc`` landete
  bei ``_build_stage_trend`` sonst still im ``tz``-Parameter.
* Fundstelle 6: ``briefing_target_day_is_current`` trägt heute den
  Systemuhr-Rückfall ``today or date.today()``; der Aufrufer im Scheduler
  übergibt gar nichts. Beides fachlich rot, kein ``TypeError``.
* Fundstellen 2, 8, 9: fachlich rot — geklemmte Segmentzeiten, falsches
  Präfix-Datum, Servertag als Zieltag des Ortsvergleichs.

TESTPOLITIK (CLAUDE.md „Test-Politik: Zwei Schichten“): Kern-Schicht, kein
Netz. Echte ``Trip``/``Stage``/``Waypoint``/``SavedLocation``-Objekte, echte
Preset-Dateien, echter Loader (die autouse-Fixtur ``_isolate_data_root`` hält
``data/`` isoliert). Kein ``Mock()``/``patch()``/``MagicMock``. Die
Netz-Nähte laufen über eine echte Unterklasse
(:class:`_AufzeichnenderScheduler`, DI-Naht am Wetterabruf) bzw. eine
aufzeichnende Sonde vor der Vergleichs-Engine — beide zeichnen auf, WAS der
Prüfling entschieden hat, statt eine Annahme zurückzuspiegeln.

Pfadregel #1409: diese Datei liest nichts von der Platte des Hauptrepos.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.loader import load_all_trips, save_trip
from app.models import TripReport
from app.trip import Trip
from app.user import SavedLocation
from services.alert_briefing_anchor import briefing_target_day_is_current
from services.notification_service import NotificationService, TripReportRequest
from services.scheduler_dispatch_service import (
    _auto_pause_expired_presets,
    send_one_compare_preset,
)
from services.trip_report_scheduler import TripReportSchedulerService
from services.trip_segments import convert_trip_to_segments
from tests.helpers.compare_briefings import (
    read_compare_briefings,
    write_compare_briefings,
)
from tests.helpers.nowcast_gate_fixtures import (
    settings_email_only,
    settings_no_channel_reachable,
    trip_stage,
)
from tests.tdd.conftest import WP_KORSIKA, WP_NZ, _anker

# ═══════════════════════════ Zonen und Koordinaten ═══════════════════════════
# Mitteleuropäische Fixturen (Versatz 2 h) können den Fehler strukturell nicht
# zeigen — deshalb durchgehend Zonen mit deutlichem Versatz.

KORSIKA_ZONE = "Europe/Paris"          # im August UTC+2
WELLINGTON_ZONE = "Pacific/Auckland"   # im August UTC+12
LA_ZONE = "America/Los_Angeles"        # im August UTC-7
WP_LA = (34.05, -118.24)               # Los Angeles

D18, D19, D20, D21, D22, D23 = (date(2026, 8, d) for d in (18, 19, 20, 21, 22, 23))

# ── Die beiden Mismatch-Fenster (a) ──────────────────────────────────────────
# 14:00 UTC am 20.08. = 02:00 Ortszeit am 21.08. in Wellington: der Ortstag ist
# dem Servertag VORAUS (positiver Versatz).
MITTAGS_UTC = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)
# 03:00 UTC am 21.08. = 20:00 Ortszeit am 20.08. in Los Angeles: der Ortstag
# hinkt dem Servertag HINTERHER (negativer Versatz). Genau die Lage, in der
# `target_date < date.today()` fälschlich wahr wird (AC-2).
WESTKUESTE_UTC = datetime(2026, 8, 21, 3, 0, tzinfo=timezone.utc)

# ── Vorhersage-Horizont ──────────────────────────────────────────────────────
# `is_within_forecast_horizon(stage_date, today)` ist
# `(stage_date - today).days <= 15`. Eine Etappe GENAU auf der Grenze des
# Ortstages liegt einen Tag JENSEITS der Grenze des Servertages — damit
# entscheidet allein der benutzte Tagesbegriff, ob der Ausblick sie abruft.
HORIZON_NZ = D21 + timedelta(days=15)        # 05.09.2026 — Ortstag 21.08. + 15


def _zone(coords: tuple[float, float]) -> str:
    return {WP_NZ: WELLINGTON_ZONE, WP_KORSIKA: KORSIKA_ZONE, WP_LA: LA_ZONE}[coords]


def _trip(trip_id: str, tage: list[date], coords: tuple[float, float]) -> Trip:
    """Tour mit je einer Zwei-Wegpunkt-Etappe pro Tag, alle in DERSELBEN Zone.

    ``trip_stage`` ist der geteilte Etappen-Baustein (``tests/helpers/
    nowcast_gate_fixtures``) — zwei Wegpunkte mit Ankunftszeiten sind Pflicht,
    ``convert_trip_to_segments`` liefert unterhalb davon eine leere Liste.
    """
    return Trip(
        id=trip_id,
        name=trip_id,
        stages=[
            trip_stage(f"S{i}", tag, coords[0], coords[1], wp_prefix=f"W{i}-")
            for i, tag in enumerate(tage)
        ],
        official_alerts_enabled=False,  # strukturell kein Warnungs-Abruf
    )


def _ort(loc_id: str, coords: tuple[float, float] | None) -> SavedLocation:
    """Gespeicherter Ort; ``coords=None`` = Ort OHNE auflösbare Zone."""
    lat, lon = (None, None) if coords is None else coords
    return SavedLocation(id=loc_id, name=loc_id, lat=lat, lon=lon, elevation_m=500)


def _uhr_eingefroren(now_utc: datetime) -> None:
    """Zweiter Teil des Vorbedingungs-Ankers (AC-9): belegt, dass
    ``freeze_time`` im PRÜFPROZESS wirklich greift.

    ``_anker`` allein zeigt das NICHT — er vergleicht den Ortstag gegen
    ``date.today()``, und die echte Systemuhr steht ohnehin auf einem anderen
    Tag als die Fixtur. Ohne diese Prüfung wäre ein grüner Lauf kein Beweis,
    sondern ein Zufall.
    """
    assert datetime.now(tz=timezone.utc) == now_utc, (
        "Testaufbau: freeze_time greift nicht, die Systemuhr steht auf "
        f"{datetime.now(tz=timezone.utc).isoformat()} statt auf "
        f"{now_utc.isoformat()}"
    )
    assert date.today() == now_utc.date(), (
        f"Testaufbau: date.today() liefert {date.today()}, erwartet den "
        f"eingefrorenen Weltzeit-Tag {now_utc.date()} — genau diesen Aufruf "
        "prüft der Test am Prüfling"
    )


def _ortstage(segmente) -> list[date]:
    """Die ORTSTAGE, auf denen die Segmente beginnen — die fachliche Größe.

    ``TripSegment.start_time`` ist UTC: eine Etappe, die um 00:00 Ortszeit in
    Neuseeland beginnt, trägt dort den UTC-Vortag, und das Ziel-Segment einer
    Westküsten-Etappe fällt in UTC auf den Folgetag. Ein Vergleich auf
    ``start_time.date()`` verwechselte diese Zonenverschiebung mit der
    Tages-Klemme, um die es hier geht.
    """
    from utils.timezone import local_dt, tz_for_coords

    return sorted({
        local_dt(
            seg.start_time, tz_for_coords(seg.start_point.lat, seg.start_point.lon),
        ).date()
        for seg in segmente
    })


class _AufzeichnenderScheduler(TripReportSchedulerService):
    """Echte Unterklasse als DI-Naht am EINZIGEN Netzabruf des Prüflings.

    Sie zeichnet auf, für WELCHE Kalendertage der Produktivcode Wetter holen
    wollte, und liefert nichts zurück. Kein Mock: die Zusicherung hängt an der
    Entscheidung des echten Prüflings, nicht an einer zurückgespiegelten
    Annahme. ``[]`` als Rückgabe ist der ehrliche Ausfall-Fall, den der
    Produktivcode ohnehin kennt (Ausblick: ``UNAVAILABLE``; Briefing:
    ``no_weather``).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.abgerufen: list[date] = []

    def _fetch_weather(self, segments, provider=None):
        self.abgerufen.extend(_ortstage(segments))
        return []


def _scheduler() -> _AufzeichnenderScheduler:
    """Settings IMMER explizit (#1477): ein blankes ``Settings()`` fällt bei
    fehlenden Feldern still auf die Produktiv-``.env`` zurück."""
    return _AufzeichnenderScheduler(settings_email_only(), "default")


# ══════════════ AC-1: Test-Fallback wählt und klemmt nach dem Ortstag ══════════════


def test_ac1_test_fallback_waehlt_und_klemmt_nach_dem_ortstag():
    """AC-1 — Fundstellen 1 (``select_test_stage``) und 3
    (``_clamp_segments_to_today``), die zusammen EINE Kette bilden.

    GIVEN eine Neuseeland-Tour (UTC+12) mit Etappen am 18.08. und 20.08., und
          ein Zeitpunkt 14:00 UTC am 20.08. — ortszeitlich ist bereits der
          21.08., auf dem Server noch der 20.08.,
    WHEN  der Test-Versand über ``select_test_stage`` seine Ersatz-Etappe wählt
          und ``_clamp_segments_to_today`` deren Segmentzeiten für den
          Wetterabruf klemmt,
    THEN  zählt die Etappe vom 20.08. NICHT mehr als „kommend“ — sie ist
          ortszeitlich vergangen, der Rückfall greift auf die chronologisch
          früheste Etappe (18.08.) —, und die Klemme verschiebt um
          ``Ortstag − from_date`` (3 Tage) statt um ``Servertag − from_date``
          (2 Tage).

    Vor dem Fix trug ``today`` an beiden Stellen den Servertag: ``s.date >=
    today`` hielt die 20.08.-Etappe fälschlich für aktuell, und die Klemme
    schob die Segmentzeiten einen Tag zu wenig weit.
    """
    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        trip = _trip("test-fallback-nz", [D18, D20], WP_NZ)

        gewaehlt = _scheduler().select_test_stage(trip, "morning", now_utc=MITTAGS_UTC)

        segmente = convert_trip_to_segments(trip, D18)
        assert segmente, "Testaufbau: die Etappe vom 18.08. muss Segmente liefern"
        geklemmt = _scheduler()._clamp_segments_to_today(segmente, D18, today=D21)

    assert gewaehlt is not None and gewaehlt.date == D18, (
        f"AC-1: select_test_stage wählte die Etappe vom "
        f"{getattr(gewaehlt, 'date', None)}, erwartet {D18}. "
        f"{D20} heißt: der Prüfling hat den Servertag ({servertag}) benutzt und "
        f"die ortszeitlich bereits vergangene Etappe noch als „kommend“ gezählt "
        f"(Ortstag {D21})."
    )
    verschoben = _ortstage(geklemmt)
    assert verschoben == [D21], (
        f"AC-1: _clamp_segments_to_today verschob auf {verschoben}, erwartet "
        f"[{D21}] (Ortstag). {[D20]} heißt: geklemmt wurde um "
        f"{(servertag - D18).days} Tage (Servertag − from_date) statt um "
        f"{(D21 - D18).days} Tage (Ortstag − from_date) — der Wetterabruf liefe "
        f"dann auf dem falschen Kalendertag."
    )


# ══════════════ AC-2: der Klemm-Zweig vergleicht zwei gleiche Tagesbegriffe ══════════════


def test_ac2_klemm_zweig_greift_nicht_am_eigenen_ortstag():
    """AC-2 — Fundstelle 2 (``_send_trip_report_outcome``, Zeile 1103).

    GIVEN eine Tour an der US-Westküste (UTC−7) mit Etappe am 20.08., ein
          Zeitpunkt 03:00 UTC am 21.08. — ortszeitlich noch der 20.08., auf dem
          Server bereits der 21.08. — und ein ``target_date``, das (wie aus
          ``_get_target_date`` → ``trip_local_today``) bereits ortsrichtig den
          20.08. trägt,
    WHEN  der Test-Versand prüft, ob die Segmentzeiten für den Wetterabruf auf
          „heute“ geklemmt werden,
    THEN  greift der Klemm-Zweig NICHT — obwohl ``date.today()`` (21.08.)
          größer ist als ``target_date`` (20.08.). Der Wetterabruf läuft auf
          dem 20.08.

    Vor dem Fix verglich ``target_date < date.today()`` einen bereits
    ortsrichtigen Tag gegen den rohen Servertag: zwei verschiedene
    Tagesbegriffe im selben ``<``-Vergleich, und der Wetterabruf lief einen Tag
    zu weit vorne.

    Gemessen wird an der Naht, an der es WIRKT: welche Segmentzeiten der
    Prüfling tatsächlich in den Wetterabruf gibt.
    """
    with freeze_time(WESTKUESTE_UTC):
        _anker(WESTKUESTE_UTC, LA_ZONE, D20)
        _uhr_eingefroren(WESTKUESTE_UTC)
        servertag = date.today()
        assert servertag > D20, (
            "Testaufbau nicht diskriminierend: der Servertag muss dem Ortstag "
            f"VORAUS sein (Servertag {servertag}, Ortstag {D20})"
        )
        trip = _trip("klemme-westkueste", [D20], WP_LA)
        scheduler = _scheduler()

        ergebnis = scheduler._send_trip_report_outcome(
            trip, "morning", allow_test_fallback=True, on_demand=True,
            target_date=D20,
        )

    assert ergebnis == "no_weather", (
        f"Testaufbau: der Prüfling muss bis zum Wetterabruf gekommen sein, "
        f"lieferte aber {ergebnis!r} — ohne Abruf belegt der Test nichts"
    )
    assert scheduler.abgerufen == [D20], (
        f"AC-2: der Wetterabruf lief auf {scheduler.abgerufen}, erwartet "
        f"[{D20}] (der ortsrichtige Zieltag). {[D21]} heißt: der Klemm-Zweig "
        f"hat gegriffen, weil er den ortsrichtigen target_date ({D20}) gegen "
        f"den Servertag ({servertag}) verglichen hat — zwei Tagesbegriffe in "
        f"einem Vergleich."
    )


# ══════════════ AC-3: Ausblick und Gewitter-Ausblick am Ortstag ══════════════


def test_ac3_ausblick_misst_den_horizont_am_ortstag():
    """AC-3, erste Hälfte — Fundstelle 4 (``_build_stage_trend``).

    GIVEN eine Neuseeland-Tour (UTC+12) mit Zieltag 20.08. und einer künftigen
          Etappe GENAU auf der Horizont-Grenze des Ortstages (21.08. + 15 Tage
          = 05.09.), und ein Zeitpunkt 14:00 UTC am 20.08.,
    WHEN  der Ausblick prüft, welche künftigen Etappen im Vorhersage-Horizont
          liegen,
    THEN  liegt die 05.09.-Etappe INNERHALB — gemessen am Ortstag 21.08. —, der
          Ausblick ruft für sie Wetter ab und die Trendzeile geht in die Mail.

    Vor dem Fix maß ``is_within_forecast_horizon(stage.date, date.today())``
    gegen den Servertag 20.08.; die Etappe fiel um genau einen Tag aus dem
    Horizont und der Ausblick blieb leer (``BEYOND_HORIZON``).
    """
    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        assert (HORIZON_NZ - D21).days == 15 and (HORIZON_NZ - servertag).days == 16, (
            "Testaufbau nicht diskriminierend: die Etappe muss am Ortstag genau "
            "IM und am Servertag genau AUSSERHALB des Horizonts liegen "
            f"(Etappe {HORIZON_NZ}, Ortstag {D21}, Servertag {servertag})"
        )
        trip = _trip("ausblick-nz", [D20, HORIZON_NZ], WP_NZ)
        scheduler = _scheduler()

        ergebnis = scheduler._build_stage_trend(trip, D20, now_utc=MITTAGS_UTC)

    assert scheduler.abgerufen == [HORIZON_NZ], (
        f"AC-3: der Ausblick rief Wetter für {scheduler.abgerufen} ab, erwartet "
        f"[{HORIZON_NZ}]. Eine leere Liste heißt: der Horizont wurde gegen den "
        f"Servertag ({servertag}) gemessen statt gegen den Ortstag ({D21}) — "
        f"die Etappe fiel um genau einen Tag heraus (Zustand "
        f"{getattr(ergebnis, 'state', None)})."
    )


def test_ac3_gewitter_ausblick_misst_den_horizont_am_ortstag():
    """AC-3, zweite Hälfte — Fundstelle 5 (``_collect_future_stage_weather``).

    GIVEN dieselbe Lage wie oben, aber der Rückfall-Pfad des Gewitter-Ausblicks
          (er greift, wenn der Trend den gebrauchten Versatz nicht abdeckt),
    WHEN  er für die ausdrücklich gewünschte Etappe vom 05.09. Wetter sammelt,
    THEN  gilt sie am Ortstag 21.08. als im Horizont und wird abgerufen.

    Eigener Test statt einer Parametrisierung mit dem Ausblick oben: es sind
    zwei getrennte Rechenwege mit je eigener ``date.today()``-Auflösung — eine
    Verfälschung, die nur einen von beiden hebt, ließe den anderen grün.
    """
    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        trip = _trip("gewitter-ausblick-nz", [D20, HORIZON_NZ], WP_NZ)
        scheduler = _scheduler()

        scheduler._collect_future_stage_weather(
            trip, D20, now_utc=MITTAGS_UTC, wanted_dates={HORIZON_NZ},
        )

    assert scheduler.abgerufen == [HORIZON_NZ], (
        f"AC-3: der Gewitter-Ausblick rief Wetter für {scheduler.abgerufen} ab, "
        f"erwartet [{HORIZON_NZ}]. Eine leere Liste heißt: der Horizont wurde "
        f"gegen den Servertag ({servertag}) gemessen statt gegen den Ortstag "
        f"({D21}) — die Gewitter-Ausblickszeile fehlt dann in Mail und SMS."
    )


# ══════════════ AC-4: Verfall des Versandfehler-Vermerks am Ortstag ══════════════


def _vermerk_schreiben(scheduler: TripReportSchedulerService, trip: Trip,
                       tag: date) -> Path:
    """Schreibt EINEN Versandfehler-Vermerk über den echten Schreibweg des
    Prüflings (``_write_pending_marker``) — keine handgebaute JSON-Attrappe."""
    scheduler._write_pending_marker(
        trip, "morning", tag, failed_segment_ids=[], reason="dispatch_error",
    )
    from app.loader import get_data_dir

    return get_data_dir(scheduler._user_id) / "pending_briefings.json"


def _offene_vermerke(pfad: Path) -> list[str]:
    return [e["date"] for e in json.loads(pfad.read_text()).get("entries", [])]


def _tour_ist_auffindbar(trip: Trip) -> None:
    """Vorbedingung, ohne die „Vermerk entfernt" mehrdeutig wäre: der Scheduler
    räumt einen Vermerk AUCH weg, wenn er die zugehörige Tour nicht findet
    (``trip is None``). Ohne diesen Anker wäre der Test in beide Richtungen aus
    dem falschen Grund grün bzw. rot."""
    gefunden = [t.id for t in load_all_trips()]
    assert trip.id in gefunden, (
        f"Testaufbau: der Scheduler findet die Tour {trip.id!r} nicht "
        f"(geladen: {gefunden}) — er entfernte den Vermerk dann mangels Tour, "
        "nicht wegen des Zieltages"
    )


def test_ac4_versandfehler_vermerk_verfaellt_nach_dem_ortstag():
    """AC-4 — Fundstelle 6 (``briefing_target_day_is_current`` und ihr
    Aufrufer in ``_process_pending_markers``).

    GIVEN ein Versandfehler-Vermerk mit Zieltag 20.08. für eine Tour an der
          US-Westküste (UTC−7) und ein Zeitpunkt 03:00 UTC am 21.08. —
          ortszeitlich ist noch der 20.08., auf dem Server schon der 21.08.,
    WHEN  der Scheduler prüft, ob der Vermerk noch aktuell ist,
    THEN  bleibt er stehen: sein Zieltag IST der laufende Ortstag.

    Vor dem Fix löste die Funktion ``heute = today or date.today()`` intern auf
    und verglich gegen den Servertag 21.08. — der Vermerk verfiel einen Tag zu
    früh und das fehlgeschlagene Briefing wurde nie nachgeliefert. Genau diese
    Stelle entscheidet, ob überhaupt etwas zugestellt wird.

    Der Trip steht in ``due_trip_ids_now``: dann ist der Verfallsprüfung der
    EINZIGE Weg, den Vermerk zu entfernen — jede andere Entfernung wäre kein
    Beleg für diese Zusicherung.
    """
    with freeze_time(WESTKUESTE_UTC):
        _anker(WESTKUESTE_UTC, LA_ZONE, D20)
        _uhr_eingefroren(WESTKUESTE_UTC)
        servertag = date.today()
        trip = _trip("vermerk-westkueste", [D20], WP_LA)
        save_trip(trip)
        _tour_ist_auffindbar(trip)
        scheduler = _scheduler()
        pfad = _vermerk_schreiben(scheduler, trip, D20)

        scheduler._process_pending_markers(WESTKUESTE_UTC, {trip.id})

    assert _offene_vermerke(pfad) == [D20.isoformat()], (
        f"AC-4: der Vermerk vom {D20} wurde entfernt, obwohl sein Zieltag der "
        f"laufende ORTSTAG ist. Das heißt: verglichen wurde gegen den Servertag "
        f"({servertag}) — das Briefing, dessen Zustellung fehlschlug, wird nie "
        f"nachgeliefert. Offene Vermerke: {_offene_vermerke(pfad)}"
    )


def test_ac4_briefing_target_day_is_current_hat_keinen_systemuhr_rueckfall():
    """AC-4 / ADR-0051 Regel 3 — ``today`` ist Pflicht, kein Default.

    GIVEN die reine Entscheidungsfunktion ``briefing_target_day_is_current``,
    WHEN  sie OHNE ``today`` aufgerufen wird,
    THEN  scheitert sie laut mit ``TypeError``, statt still auf die
          Umgebungsuhr zurückzufallen.

    Warum das eine eigene Zusicherung ist: ein Rückfall-Default macht den
    Aufruf-Fehler „Tag vergessen“ unsichtbar — die Funktion liefert dann eine
    plausible Antwort zum falschen Tagesbegriff. Genau dieser Default steht
    heute im Code (``heute = today or date.today()``), weshalb dieser Test rot
    ist: der Aufruf gelingt.
    """
    with pytest.raises(TypeError):
        briefing_target_day_is_current(D20)


# ══════════════ AC-5: Auto-Pause eines Presets am Ortstag ══════════════


def _preset(preset_id: str, location_ids: list[str], end_date: date) -> dict:
    return {
        "id": preset_id,
        "name": preset_id,
        "location_ids": location_ids,
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "end_date": end_date.isoformat(),
    }


def _preset_ablage(tmp_path: Path, presets: list[dict],
                   user_id: str = "default") -> str:
    """Legt die Presets als echte ``briefings/<id>.json`` an (geteilter
    Helfer) und gibt den ``data_root`` zurück."""
    write_compare_briefings(tmp_path / "users" / user_id, presets)
    return str(tmp_path)


def _pausiert(tmp_path: Path, preset_id: str, user_id: str = "default") -> bool:
    eintraege = read_compare_briefings(tmp_path / "users" / user_id)
    treffer = [e for e in eintraege if e.get("id") == preset_id]
    assert treffer, f"Testaufbau: Preset {preset_id} nicht in der Ablage"
    return bool(treffer[0].get("paused_at"))


def test_ac5_preset_pausiert_nach_dem_ortstag_seines_ersten_orts(tmp_path):
    """AC-5 — Fundstelle 7 (``_auto_pause_expired_presets``).

    GIVEN ein Ortsvergleich-Preset, dessen ``end_date`` auf dem 20.08. liegt
          und dessen erster auflösbarer Ort in Neuseeland (UTC+12) steht, und
          ein Zeitpunkt 14:00 UTC am 20.08. — ortszeitlich ist dort bereits der
          21.08.,
    WHEN  der Versandlauf prüft, ob das Preset automatisch zu pausieren ist,
    THEN  wird es pausiert: an SEINEM Ort ist der letzte Tag vorbei.

    Vor dem Fix verglich ``date.fromisoformat(end_date) < date.today()`` gegen
    den Servertag 20.08. — das Preset blieb einen Tag zu lange aktiv und
    verschickte einen Vergleich, den der Nutzer abbestellt hatte.

    Geprüft wird am Wirkort: dem ``paused_at`` in der geschriebenen
    ``briefings/<id>.json`` (Read-Modify-Write mit Merge, unverändert).
    """
    presets = [_preset("preset-nz", ["ort-nz"], D20)]
    data_root = _preset_ablage(tmp_path, presets)
    orte = [_ort("ort-nz", WP_NZ)]

    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        _auto_pause_expired_presets(
            presets, "default", data_root,
            now_utc=MITTAGS_UTC, all_locations=orte,
        )

    assert _pausiert(tmp_path, "preset-nz"), (
        f"AC-5: das Preset mit end_date {D20} wurde NICHT pausiert, obwohl an "
        f"seinem Ort (Neuseeland) bereits der {D21} läuft. Das heißt: verglichen "
        f"wurde gegen den Servertag ({servertag}) — das Preset verschickt einen "
        f"weiteren Vergleich nach seinem eigenen Ende."
    )


# ══════════════ AC-6: Datum im Präfix-Text aus der Zone des Trips ══════════════


def _report(trip: Trip) -> TripReport:
    """Echter ``TripReport`` OHNE verwertbare Segmente — der Fallback-Fall, in
    dem ``_target_date_from_report`` den Tag selbst bestimmen muss."""
    return TripReport(
        trip_id=trip.id,
        trip_name=trip.name,
        report_type="morning",
        generated_at=datetime.now(timezone.utc),
        segments=[],
        email_subject=f"[{trip.name}] Morgen",
        email_html="",
        email_plain="Wetterbericht",
    )


def test_ac6_praefix_datum_folgt_der_zone_des_trips():
    """AC-6 — Fundstelle 8 (``_target_date_from_report``), gemessen an
    ``_apply_prefixes``, wo der Tag als TEXT beim Nutzer ankommt.

    GIVEN ein Trip-Report ohne verwertbare Segmente (reiner Fallback-Fall) für
          eine Neuseeland-Tour, dessen Anfrage die Zone bereits als
          ``trip_tz`` trägt, und ein Zeitpunkt 14:00 UTC am 20.08. —
          ortszeitlich der 21.08.,
    WHEN  der Test-Präfix („Test-Vorschau für … am …“) gesetzt wird,
    THEN  trägt er das Datum 21.08.2026 — den Ortstag der Tour.

    Vor dem Fix lieferte ``_target_date_from_report`` ``date.today()``: der
    Nutzer las im Mail-/SMS-/Telegram-Präfix ein Datum, das einen Tag neben dem
    Tag lag, für den das Briefing gilt.
    """
    trip = _trip("praefix-nz", [D21], WP_NZ)
    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        anfrage = TripReportRequest(
            trip=trip,
            report_type="morning",
            segment_weather=[],
            trip_tz=ZoneInfo(WELLINGTON_ZONE),
            stage_name="Etappe 1",
            test_prefix=True,
        )
        report = _report(trip)
        NotificationService(settings_email_only(), "default")._apply_prefixes(
            report, anfrage,
        )

    assert f"{D21:%d.%m.%Y}" in report.email_plain, (
        f"AC-6: der Präfix-Text nennt nicht den Ortstag {D21:%d.%m.%Y}.\n"
        f"  Text:      {report.email_plain.splitlines()[0]!r}\n"
        f"  Servertag: {servertag:%d.%m.%Y} — steht er dort, hat der Prüfling "
        f"date.today() benutzt statt der bereits aufgelösten Zone am DTO "
        f"(request.trip_tz)."
    )


# ══════════════ AC-7: Zieltag des Ortsvergleich-Einzelversands ══════════════


class _ZieltagGesehen(Exception):
    """Sonde vor der Vergleichs-Engine: hält den Zieltag fest, mit dem der
    Prüfling sie ruft, und bricht dann ab — der Rest der Kette (Wetterabruf,
    Rendering, Versand) trägt für DIESE Zusicherung nichts bei."""

    def __init__(self, target_date: date) -> None:
        super().__init__(str(target_date))
        self.target_date = target_date


def _engine_sonde(monkeypatch) -> None:
    from services.comparison_engine import ComparisonEngine

    def _aufzeichnen(*, target_date, **_rest):
        raise _ZieltagGesehen(target_date)

    monkeypatch.setattr(ComparisonEngine, "run", _aufzeichnen)


def test_ac7_einzelversand_nimmt_den_ortstag_des_ersten_aufloesbaren_orts(
    monkeypatch,
):
    """AC-7 — Fundstelle 9 (``send_one_compare_preset``, Einzelversand-Zweig).

    GIVEN ein Ortsvergleich-Preset mit zwei Orten — der erste ohne auflösbare
          Zone (Ort ohne Koordinaten), der zweite in Neuseeland (UTC+12) —, ein
          Handversand OHNE Slot-Kontext (``target_date=None``,
          ``tage_ab_ortstag=None``) und ein Zeitpunkt 14:00 UTC am 20.08.,
    WHEN  der Einzelversand seinen Zieltag bestimmt,
    THEN  ist es der 21.08. — der Ortstag des ERSTEN AUFLÖSBAREN Orts; der
          unauflösbare erste wird übersprungen, nicht auf UTC zurückgefallen.

    Vor dem Fix stand dort ``target_date = date.today()``: der Vergleich lief
    auf dem Servertag, während der daneben gesetzte ``tage_ab_ortstag = 0``
    einen Versatz gegen den ORTSTAG behauptet — zwei Tagesbegriffe, die genau
    hier auseinanderlaufen.
    """
    _engine_sonde(monkeypatch)
    orte = [_ort("ohne-zone", None), _ort("ort-nz", WP_NZ)]
    preset = _preset("preset-handversand", ["ohne-zone", "ort-nz"], D23)

    from utils.timezone import resolve_location_tz

    assert resolve_location_tz(orte[0]) is None, (
        "Testaufbau nicht diskriminierend: der erste Ort muss UNAUFLÖSBAR sein, "
        "sonst belegt der Test nicht, dass übersprungen statt zurückgefallen wird"
    )

    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        with pytest.raises(_ZieltagGesehen) as gesehen:
            send_one_compare_preset(
                preset, settings_email_only(), "default", str(Path("/nicht/benutzt")),
                all_locations_cache=orte,
            )

    assert gesehen.value.target_date == D21, (
        f"AC-7: der Einzelversand lief auf den Zieltag "
        f"{gesehen.value.target_date}, erwartet {D21} (Ortstag des ersten "
        f"auflösbaren Orts). {servertag} heißt: date.today() — der Betreff, die "
        f"Vergleichs-Engine und der Δ-Anker-Versatz stehen dann auf zwei "
        f"verschiedenen Tagesbegriffen."
    )


def test_ac7_beide_fehlerpfade_behalten_ihre_reihenfolge(monkeypatch):
    """AC-7, Invariante — der externe Vertrag bleibt unverändert.

    GIVEN ein Preset mit unauflösbaren Orten UND fehlendem Empfänger,
    WHEN  der Einzelversand aufgerufen wird,
    THEN  meldet er ZUERST den fehlenden Empfänger; die Orte-Prüfung kommt
          danach. Die Ortsauflösung wandert für diesen Fix zwar VOR die
          Zieltag-Bestimmung, darf die beiden Fehlerpfade aber nicht
          umsortieren.

    Dieser Test ist HEUTE GRÜN — er ist bewusst ein Regressions-Riegel für die
    Umstellung, kein Bug-Nachweis (die Reihenfolge ist heute richtig und soll
    es bleiben).
    """
    _engine_sonde(monkeypatch)
    preset = _preset("preset-ohne-empfaenger", ["gibt-es-nicht"], D23)

    with pytest.raises(ValueError) as fehler:
        send_one_compare_preset(
            preset, settings_no_channel_reachable(), "default",
            str(Path("/nicht/benutzt")), all_locations_cache=[],
        )

    assert "mail_to" in str(fehler.value), (
        f"AC-7 (Invariante): gemeldet wurde {str(fehler.value)!r}. Erwartet war "
        "zuerst der fehlende Empfänger (mail_to) — die vorgezogene "
        "Ortsauflösung hat die Reihenfolge der beiden Fehlerpfade verschoben."
    )


# ═════════ AC-3/AC-9: der Parameter schlägt die Umgebungsuhr ═════════
#
# Alle Tests oben frieren die Uhr auf DENSELBEN Zeitpunkt ein, den sie als
# `now_utc` hereinreichen. `freeze_time` patcht `datetime.now()`/`date.today()`
# global — damit sind Parameterwert und Systemuhr dort IMMER identisch, und die
# zweite Hälfte von ADR-0051 Regel 3 („jetzt kommt vom Aufrufer“) ist
# strukturell nicht falsifizierbar. Eine Verfälschung, die den Pflichtparameter
# STEHEN lässt und im Rumpf trotzdem `date.today()` benutzt, bliebe ungefangen —
# genau die Lücke, an der in S5a fünf von sechs Aufrufstellen blind waren
# (Adversary F001). Die Fälle unten ziehen die beiden Zeitpunkte auseinander.
#
# Fachlich trägt diese Familie AC-3: zwischen der Zeitbindung in
# `_send_trip_report_outcome` und den Ausblicks-Funktionen liegt ein echter
# Wetterabruf mit Retry-Backoff — dort kann eine Mitternacht liegen (gemessener
# Präzedenzfall: dispatch_orchestrator.py:157-163). Nur ein durchgereichter
# Zeitpunkt hält den ganzen Briefing-Aufbau auf EINEM Tagesbegriff.

FROST_UTC = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)   # Uhr: Ortstag 20.08.
PARAM_UTC = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)   # Parameter: Ortstag 22.08.
# Horizont-Grenze des PARAMETER-Ortstages: am 22.08. + 15 Tage gerade noch
# drin, am 20.08. + 15 Tage schon draußen.
HORIZON_PARAM = D22 + timedelta(days=15)                        # 06.09.2026


def _fall_select_test_stage(tmp_path):
    """Fundstelle 1 — welche Ersatz-Etappe wählt der Test-Versand?"""
    trip = _trip("param-fallback", [D19, D21], WP_KORSIKA)
    gewaehlt = _scheduler().select_test_stage(trip, "morning", now_utc=PARAM_UTC)
    return getattr(gewaehlt, "date", None)


def _fall_clamp_segments(tmp_path):
    """Fundstelle 3 — um wie viele Tage wandern die Segmentzeiten?"""
    trip = _trip("param-klemme", [D19], WP_KORSIKA)
    segmente = convert_trip_to_segments(trip, D19)
    ortstag = PARAM_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
    geklemmt = _scheduler()._clamp_segments_to_today(segmente, D19, today=ortstag)
    return tuple(_ortstage(geklemmt))


def _fall_stage_trend(tmp_path):
    """Fundstelle 4 — welche künftige Etappe liegt im Vorhersage-Horizont?"""
    trip = _trip("param-ausblick", [D20, HORIZON_PARAM], WP_KORSIKA)
    scheduler = _scheduler()
    scheduler._build_stage_trend(trip, D20, now_utc=PARAM_UTC)
    return tuple(scheduler.abgerufen)


def _fall_future_stage_weather(tmp_path):
    """Fundstelle 5 — dasselbe für den Rückfall des Gewitter-Ausblicks."""
    trip = _trip("param-gewitter", [D20, HORIZON_PARAM], WP_KORSIKA)
    scheduler = _scheduler()
    scheduler._collect_future_stage_weather(
        trip, D20, now_utc=PARAM_UTC, wanted_dates={HORIZON_PARAM},
    )
    return tuple(scheduler.abgerufen)


def _fall_pending_marker(tmp_path):
    """Fundstelle 6 — verfällt der Versandfehler-Vermerk vom 20.08.?

    Der Trip steht in ``due_trip_ids_now``; die Verfallsprüfung ist damit der
    einzige Weg, den Vermerk zu entfernen.
    """
    trip = _trip("param-vermerk", [D20], WP_KORSIKA)
    save_trip(trip)
    _tour_ist_auffindbar(trip)
    scheduler = _scheduler()
    pfad = _vermerk_schreiben(scheduler, trip, D20)
    scheduler._process_pending_markers(PARAM_UTC, {trip.id})
    return tuple(_offene_vermerke(pfad))


def _fall_auto_pause(tmp_path):
    """Fundstelle 7 — wird das am 20.08. endende Preset pausiert?"""
    presets = [_preset("param-preset", ["ort-korsika"], D20)]
    data_root = _preset_ablage(tmp_path, presets)
    _auto_pause_expired_presets(
        presets, "default", data_root,
        now_utc=PARAM_UTC, all_locations=[_ort("ort-korsika", WP_KORSIKA)],
    )
    return "pausiert" if _pausiert(tmp_path, "param-preset") else "aktiv"


@pytest.mark.parametrize("fall, erwartet_parameter, erwartet_systemuhr", [
    pytest.param(_fall_select_test_stage, D19, D21, id="select-test-stage"),
    pytest.param(_fall_clamp_segments, (D22,), (D20,), id="clamp-segments"),
    pytest.param(_fall_stage_trend, (HORIZON_PARAM,), (), id="stage-trend"),
    pytest.param(_fall_future_stage_weather, (HORIZON_PARAM,), (),
                 id="future-stage-weather"),
    pytest.param(_fall_pending_marker, (), ("2026-08-20",), id="pending-marker"),
    pytest.param(_fall_auto_pause, "pausiert", "aktiv", id="auto-pause"),
])
def test_versandpfade_folgen_dem_parameter_nicht_der_systemuhr(
    fall, erwartet_parameter, erwartet_systemuhr, tmp_path,
):
    """AC-3 und AC-9 — die sechs Fundstellen mit Pflichtparameter müssen dem
    ÜBERGEBENEN Zeitpunkt folgen, nicht der Uhr des Rechners.

    GIVEN die Systemuhr steht auf dem 20.08. (Ortstag 20.08. auf Korsika),
    WHEN  derselbe Aufruf ``now_utc`` = 22.08. hereinreicht (Ortstag 22.08.),
    THEN  entspricht das Ergebnis dem 22.08. Ein Prüfling, der den
          Pflichtparameter zwar entgegennimmt, im Rumpf aber ``date.today()``
          benutzt, liefert stattdessen das Ergebnis zum 20.08.

    Die beiden Erwartungswerte stehen literal nebeneinander und müssen
    verschieden sein: das ist die Selbstprüfung, dass der Fall überhaupt
    zwischen Parameter und Uhr unterscheiden KANN.

    An den Fundstellen 2, 8 und 9 ist diese Probe strukturell unmöglich — dort
    bleibt „jetzt“ bewusst funktionsintern (Spec „Known Limitations“); für sie
    gilt allein die (a)-Prüfung weiter oben.
    """
    assert erwartet_parameter != erwartet_systemuhr, (
        f"Testaufbau nicht diskriminierend: Parameter- und Systemuhr-Erwartung "
        f"sind beide {erwartet_parameter!r} — der Fall kann nichts belegen"
    )

    with freeze_time(FROST_UTC):
        tag_uhr = FROST_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
        tag_param = PARAM_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
        assert tag_uhr != tag_param, (
            f"Testaufbau: Uhr ({tag_uhr}) und Parameter ({tag_param}) müssen "
            "auf verschiedene ORTSTAGE fallen, nicht nur auf verschiedene "
            "Uhrzeiten"
        )
        # Belegt, dass die eingefrorene Uhr im Prüfprozess wirklich greift —
        # sonst wäre ein grüner Lauf kein Beweis, sondern ein Zufall.
        _uhr_eingefroren(FROST_UTC)
        beobachtet = fall(tmp_path)

    hinweis = ""
    if beobachtet == erwartet_systemuhr:
        hinweis = (
            f"\n  Das ist GENAU das Ergebnis zum {tag_uhr:%d.%m.%Y} — der "
            "Prüfling hat den übergebenen Zeitpunkt ignoriert und die "
            "Systemuhr benutzt (ADR-0051 Regel 3)."
        )
    assert beobachtet == erwartet_parameter, (
        f"Der Versandpfad folgte nicht dem übergebenen Zeitpunkt.\n"
        f"  übergeben:   {PARAM_UTC.isoformat()} (Ortstag {tag_param:%d.%m.%Y})\n"
        f"  Systemuhr:   {FROST_UTC.isoformat()} (Ortstag {tag_uhr:%d.%m.%Y})\n"
        f"  erwartet:    {erwartet_parameter!r}\n"
        f"  beobachtet:  {beobachtet!r}{hinweis}"
    )
