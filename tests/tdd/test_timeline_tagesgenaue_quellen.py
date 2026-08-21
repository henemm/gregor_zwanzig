"""TDD RED — #1818: Timeline/Glance/Gewitter loesen Wetterdaten TAGESGENAU auf.

SPEC:    docs/specs/modules/fix_1818_timeline_tagesaufloesung.md (AC-1 bis AC-8)
KONTEXT: docs/context/fix-1818-timeline-zweitagesanker.md

Der undatierte Wetter-Anker ``{trip_id}.json`` traegt strukturell nur EINEN
Tag: ``_write_briefing_anchor`` (``trip_report_scheduler.py:1505-1512``) ruft
``WeatherSnapshotService.save()`` je Briefing-Lauf mit genau einem
``target_date`` auf und ueberschreibt die Datei dabei vollstaendig. Die vier
Formatierer in ``trip_command_processor.py`` (``_fmt_timeline:1007``,
``_fmt_glance:929/:933``, ``_fmt_gewitter:944``) melden den dadurch fehlenden
Tag als **„Keine Etappe geplant"** — eine Aussage ueber die TOURPLANUNG,
obwohl das System nur etwas ueber den DATENBESTAND weiss.

🔴 Warum diese Datei NEBEN den Bestandstests noetig ist
--------------------------------------------------------
``tests/tdd/test_timeline_folgt_der_ortszeit.py:95-101`` und
``tests/tdd/test_issue_651_telegram_query_glance.py:108-119`` bauen ihren
Anker **kuenstlich mit beiden Tagen in EINEM ``save()``-Aufruf** auf. Genau
deshalb hat keiner von ihnen den Bug gesehen. Diese Datei baut den Anker ueber
``_briefing_lauf()`` — ZWEI aufeinanderfolgende, einander **ueberschreibende**
``save()``/``save_dated()``-Vorgaenge, also den Produktionspfad. Ein Test, der
beide Tage in einem Aufruf schreibt, ist trivial gruen und wertlos.

Testpolitik (CLAUDE.md „Test-Politik: Zwei Schichten"): Kern-Schicht, kein
Netz. Echte ``Trip``/``Stage``/``Waypoint``-Objekte, echte Snapshot-Dateien
ueber ``WeatherSnapshotService``, echter ``TripCommandProcessor`` ueber den
produktiven Eintrittspunkt ``process()``. Kein ``Mock()``/``patch()``, keine
Rueckspiegelung eigener Annahmen. Die Datenwurzel isoliert die projektweite
autouse-Fixtur ``_isolate_data_root`` (``tests/conftest.py:122``) nach
``tmp_path`` — der Isolationsnachweis unten belegt das je Test.

Pfadregel #1409: der Pruefling wird relativ zur eigenen Testdatei aufgeloest
(Wachposten ``_PRUEFLING`` unten), nie ueber den festen Hauptrepo-Pfad — sonst
kaeme aus dem Worktree falsches Gruen.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

import services.trip_command_processor as _tcp
from app.loader import get_snapshots_dir, save_trip
from app.models import (
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from services.trip_report_scheduler import TripReportSchedulerService
from services.weather_snapshot import WeatherSnapshotService

# ---------------------------------------------------------------------------
# Pfadregel #1409 — der Pruefling MUSS aus demselben Baum stammen wie diese
# Testdatei. Laeuft die Suite im Worktree, der Import kaeme aber aus dem
# Hauptrepo, waere jedes Gruen wertlos.
# ---------------------------------------------------------------------------
_BAUM = Path(__file__).resolve().parents[2]
_PRUEFLING = Path(_tcp.__file__).resolve()
assert _PRUEFLING.is_relative_to(_BAUM), (
    f"Pfadregel #1409 verletzt: der Pruefling liegt unter {_PRUEFLING}, "
    f"diese Testdatei aber unter {_BAUM}."
)

# ---------------------------------------------------------------------------
# Fixe Tour-Daten. Vizzavona/Korsika (Europe/Paris, im August UTC+2); die
# Uhrzeiten liegen bewusst AUSSERHALB des Ortstag-Mismatch-Fensters, damit
# diese Suite ausschliesslich die QUELLENAUFLOESUNG prueft und nicht
# versehentlich die Ortszeit-Umrechnung aus #1795.
# ---------------------------------------------------------------------------
KORSIKA = (42.10, 9.00)
HEUTE = date(2026, 8, 20)
MORGEN = date(2026, 8, 21)
EMPFANGEN_UTC = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)  # 14:00 Ortszeit

# Der Spec-Wortlaut der ehrlichen Fehlanzeige (Implementation Details:
# „noch keine Wetterdaten fuer {label} ({datum})").
LUECKE = "noch keine Wetterdaten"
# Die Falschaussage, die dieser Fix beseitigt.
FALSCHAUSSAGE = "Keine Etappe geplant"


# ---------------------------------------------------------------------------
# Isolationsnachweis — belegt je Test, dass wirklich in einen temporaeren Baum
# geschrieben wird und nicht in das echte ``data/`` des Repos.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolationsnachweis():
    verzeichnis = get_snapshots_dir("default").resolve()
    assert not str(verzeichnis).startswith(str(_BAUM / "data")), (
        "Testaufbau: die Snapshot-Ablage zeigt auf den echten Datenbaum "
        f"({verzeichnis}) — die Isolation aus tests/conftest.py greift nicht."
    )
    yield


# ---------------------------------------------------------------------------
# Helfer — echte Tourdaten
# ---------------------------------------------------------------------------

def _stage(stage_id: str, tag: date) -> Stage:
    """Etappe mit ZWEI Wegpunkten — ``convert_trip_to_segments()`` verwirft
    Etappen mit weniger (``trip_segments.py``), sie waeren fuer die Frage
    „existiert an diesem Tag ueberhaupt eine Etappe?" unsichtbar."""
    lat, lon = KORSIKA
    return Stage(
        id=stage_id, name=f"Etappe {tag:%d.%m.}", date=tag,
        waypoints=[
            Waypoint(id=f"{stage_id}-A", name="Start", lat=lat, lon=lon,
                     elevation_m=500),
            Waypoint(id=f"{stage_id}-B", name="Ziel", lat=lat + 0.05,
                     lon=lon + 0.05, elevation_m=800),
        ],
    )


def _trip(trip_id: str, tage: list[date]) -> Trip:
    trip = Trip(
        id=trip_id, name=trip_id,
        stages=[_stage(f"S{i}", tag) for i, tag in enumerate(tage)],
    )
    save_trip(trip, "default")
    return trip


def _seg(
    ankunft_utc: datetime,
    *,
    seg_id: int,
    temp_min: float,
    temp_max: float,
    thunder: ThunderLevel = ThunderLevel.NONE,
) -> SegmentWeatherData:
    """Ein Wetter-Wegpunkt mit kontrollierter Ankunftszeit und eindeutigem
    Temperaturpaar — das Paar ist der Fingerabdruck, an dem die Tests die
    HERKUNFT der angezeigten Werte unterscheiden (AC-4)."""
    lat, lon = KORSIKA
    segment = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1400.0),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=1500.0),
        start_time=ankunft_utc - timedelta(hours=2),
        end_time=ankunft_utc,
        duration_hours=2.0, distance_km=5.0, ascent_m=100.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(
            temp_min_c=temp_min, temp_max_c=temp_max, wind_max_kmh=20.0,
            thunder_level_max=thunder,
        ),
        fetched_at=ankunft_utc,
        provider="test",
    )


def _tages_segmente(tag: date, *, seg_id: int, temp_min: float,
                    temp_max: float,
                    thunder: ThunderLevel = ThunderLevel.NONE,
                    ) -> list[SegmentWeatherData]:
    """Die Wetterdaten EINES Briefing-Laufs — genau ein Tag, so wie
    ``_fetch_weather`` sie fuer ``_get_target_date()`` liefert."""
    return [_seg(
        datetime(tag.year, tag.month, tag.day, 8, 0, tzinfo=timezone.utc),
        seg_id=seg_id, temp_min=temp_min, temp_max=temp_max, thunder=thunder,
    )]


def _briefing_lauf(trip_id: str, segmente: list[SegmentWeatherData],
                   target_date: date, user_id: str = "default") -> None:
    """EIN Briefing-Lauf — Nachbau von ``_write_briefing_anchor``
    (``trip_report_scheduler.py:1505-1512``): ``save()`` **ueberschreibt** den
    undatierten Anker vollstaendig, ``save_dated()`` legt zusaetzlich
    ``{trip_id}_{YYYY-MM-DD}.json`` ab.

    🔴 Der Aufbau ueber MEHRERE solcher Laeufe ist der Kern dieser Suite: der
    zweite Lauf loescht die Segmente des ersten aus dem undatierten Anker. Die
    Bestandsfixturen schreiben stattdessen beide Tage in EINEM ``save()`` und
    verdecken den Bug damit vollstaendig.
    """
    svc = WeatherSnapshotService(user_id)
    svc.save(trip_id, segmente, target_date)
    svc.save_dated(trip_id, target_date, segmente)


def _briefing_lauf_ohne_datierten(trip_id: str,
                                  segmente: list[SegmentWeatherData],
                                  target_date: date,
                                  user_id: str = "default") -> None:
    """Ein Schreibvorgang, der NUR den undatierten Anker setzt — wie
    ``_fetch_and_save_snapshot`` (``trip_command_processor.py:278-316``) es aus
    dem Abfragepfad tut. Erzeugt die Lage „Anker traegt Tag X, aber es gibt
    keinen datierten Rueckfall fuer Tag Y"."""
    WeatherSnapshotService(user_id).save(trip_id, segmente, target_date)


def _befehl(trip: Trip, body: str) -> CommandResult:
    """Befehl ueber den ECHTEN Eintrittspunkt ``process()``."""
    return TripCommandProcessor().process(InboundMessage(
        channel="telegram", trip_name=trip.name, body=body, sender="4711",
        received_at=EMPFANGEN_UTC, user_id="default",
    ))


def _zeile(body: str, praefix: str) -> str:
    """Die eine Zeile der Antwort, die mit ``praefix`` beginnt."""
    treffer = [z for z in body.splitlines() if z.startswith(praefix)]
    assert len(treffer) == 1, (
        f"Testaufbau: erwartete genau EINE Zeile mit Praefix {praefix!r}, "
        f"gefunden {len(treffer)}:\n{body}"
    )
    return treffer[0]


def _schnappschuss_zustand() -> dict[str, tuple[int, bytes]]:
    """Byte-Inhalt UND Aenderungszeitstempel jeder Snapshot-Datei — die
    Beobachtung, mit der AC-7 einen Schreibvorgang nachweist (hier ist der
    Dateizustand SELBST das geprueft Verhalten, kein Inhalts-Surrogat)."""
    verzeichnis = get_snapshots_dir("default")
    if not verzeichnis.exists():
        return {}
    return {
        p.name: (p.stat().st_mtime_ns, p.read_bytes())
        for p in sorted(verzeichnis.iterdir()) if p.is_file()
    }


# ---------------------------------------------------------------------------
# Aufbauten — je Szenario EIN Anker, gebaut aus mehreren Briefing-Laeufen
# ---------------------------------------------------------------------------

def _anker_traegt_nur_heute(trip_id: str, tage: list[date]) -> Trip:
    """Lauf 1 schreibt MORGEN in den Anker, Lauf 2 ueberschreibt ihn mit
    HEUTE — der morgige Tag ist danach aus dem Anker verschwunden, und einen
    datierten Rueckfall ``{trip}_{morgen}.json`` gibt es nicht (er entstuende
    erst im heutigen Abend-Briefing, Kontext-Tabelle „Kostenloser
    Teil-Rueckfall")."""
    trip = _trip(trip_id, tage)
    _briefing_lauf_ohne_datierten(
        trip.id,
        _tages_segmente(MORGEN, seg_id=2, temp_min=12.0, temp_max=19.0),
        MORGEN,
    )
    _briefing_lauf(
        trip.id,
        _tages_segmente(HEUTE, seg_id=1, temp_min=10.0, temp_max=18.0),
        HEUTE,
    )
    return trip


def _anker_traegt_nur_morgen(trip_id: str, tage: list[date]) -> Trip:
    """Lauf 1 (Morgen-Briefing) schreibt HEUTE ohne datierten Rueckfall,
    Lauf 2 (Abend-Briefing) ueberschreibt den Anker mit MORGEN — fuer HEUTE
    existiert danach WEDER im Anker noch datiert etwas."""
    trip = _trip(trip_id, tage)
    _briefing_lauf_ohne_datierten(
        trip.id,
        _tages_segmente(HEUTE, seg_id=1, temp_min=10.0, temp_max=18.0),
        HEUTE,
    )
    _briefing_lauf(
        trip.id,
        _tages_segmente(MORGEN, seg_id=2, temp_min=12.0, temp_max=19.0,
                        thunder=ThunderLevel.MED),
        MORGEN,
    )
    return trip


# ══════════════════════ AC-1 ══════════════════════

def test_fehlender_folgetag_meldet_datenluecke_statt_fehlender_etappe():
    """AC-1.

    GIVEN der Trip hat morgen eine Etappe, der undatierte Anker traegt nach
          zwei einander ueberschreibenden Briefing-Laeufen nur HEUTE und ein
          datierter Snapshot fuer morgen existiert nicht,
    WHEN  der Nutzer ``timeline_morgen`` abfragt,
    THEN  meldet die Antwort fehlende Wetterdaten — und behauptet NICHT
          „Keine Etappe geplant".
    """
    with freeze_time(EMPFANGEN_UTC):
        trip = _anker_traegt_nur_heute("ac1-luecke-morgen", [HEUTE, MORGEN])
        assert not (get_snapshots_dir("default") / f"{trip.id}_{MORGEN}.json").exists(), (
            "Testaufbau: es darf KEINEN datierten Snapshot fuer morgen geben, "
            "sonst prueft AC-1 den Rueckfall statt der Datenluecke."
        )
        ergebnis = _befehl(trip, "### query: timeline_morgen")

    body = ergebnis.confirmation_body
    assert ergebnis.success is True, body
    assert FALSCHAUSSAGE not in body, (
        f"AC-1: die Antwort behauptet etwas ueber die TOURPLANUNG "
        f"({FALSCHAUSSAGE!r}), obwohl fuer morgen eine Etappe existiert und "
        f"nur die Wetterdaten fehlen:\n{body}"
    )
    assert LUECKE in body, (
        f"AC-1: erwartete ehrliche Fehlanzeige {LUECKE!r} fehlt:\n{body}"
    )


# ══════════════════════ AC-2 (Gegenfall) ══════════════════════

def test_tag_ohne_etappe_bleibt_bei_keine_etappe_geplant():
    """AC-2 — der Gegenfall zu AC-1.

    GIVEN der Trip endet HEUTE, fuer morgen existiert keine Etappe (und
          folglich auch kein Wetterdatensatz),
    WHEN  der Nutzer ``timeline_morgen`` abfragt,
    THEN  bleibt die Aussage „Keine Etappe geplant" — sie ist hier
          zutreffend — und es erscheint KEINE Datenluecken-Meldung.

    Existiert, um eine Bedingungs-Inversion („Etappe vorhanden?" verdreht)
    fangbar zu machen: ohne diesen Test bliebe sie unsichtbar.
    """
    with freeze_time(EMPFANGEN_UTC):
        trip = _trip("ac2-tourende-heute", [HEUTE - timedelta(days=1), HEUTE])
        _briefing_lauf_ohne_datierten(
            trip.id,
            _tages_segmente(HEUTE - timedelta(days=1), seg_id=0,
                            temp_min=8.0, temp_max=16.0),
            HEUTE - timedelta(days=1),
        )
        _briefing_lauf(
            trip.id,
            _tages_segmente(HEUTE, seg_id=1, temp_min=10.0, temp_max=18.0),
            HEUTE,
        )
        ergebnis = _befehl(trip, "### query: timeline_morgen")

    body = ergebnis.confirmation_body
    assert ergebnis.success is True, body
    assert FALSCHAUSSAGE in body, (
        f"AC-2: morgen existiert wirklich keine Etappe — die Antwort muss das "
        f"weiterhin sagen ({FALSCHAUSSAGE!r}):\n{body}"
    )
    assert LUECKE not in body, (
        f"AC-2: eine Datenluecken-Meldung waere hier falsch, es gibt an diesem "
        f"Tag keine Etappe:\n{body}"
    )


# ══════════════════════ AC-3 ══════════════════════

def test_datierter_snapshot_deckt_den_tag_den_der_anker_verloren_hat():
    """AC-3.

    GIVEN das Abend-Briefing lief zuletzt (der Anker traegt MORGEN) und der
          datierte Snapshot ``{trip}_{heute}.json`` aus dem Morgen-Briefing
          liegt noch vor,
    WHEN  der Nutzer ``timeline_heute`` abfragt,
    THEN  zeigt das System die Stundenwerte des heutigen Tages aus dem
          datierten Snapshot — konkrete Uhrzeit UND konkrete Messwerte.
    """
    with freeze_time(EMPFANGEN_UTC):
        trip = _trip("ac3-abendbriefing", [HEUTE, MORGEN])
        # Lauf 1 — Morgen-Briefing: Anker + datierter Snapshot fuer HEUTE.
        _briefing_lauf(
            trip.id,
            _tages_segmente(HEUTE, seg_id=1, temp_min=10.0, temp_max=18.0),
            HEUTE,
        )
        # Lauf 2 — Abend-Briefing: ueberschreibt den Anker mit MORGEN.
        _briefing_lauf(
            trip.id,
            _tages_segmente(MORGEN, seg_id=2, temp_min=12.0, temp_max=19.0),
            MORGEN,
        )
        assert (get_snapshots_dir("default") / f"{trip.id}_{HEUTE}.json").exists(), (
            "Testaufbau: der datierte Snapshot fuer heute muss vorliegen, "
            "sonst prueft AC-3 nicht den Rueckfall."
        )
        ergebnis = _befehl(trip, "### query: timeline_heute")

    body = ergebnis.confirmation_body
    assert ergebnis.success is True, body
    assert FALSCHAUSSAGE not in body, (
        f"AC-3: der Anker hat heute verloren, der datierte Snapshot traegt ihn "
        f"aber noch — statt der Werte kommt eine Tourplanungs-Aussage:\n{body}"
    )
    assert "🕐 10:00" in body, (
        "AC-3: erwartete Stundenzeile '🕐 10:00' (Ankunft 08:00 UTC, Korsika "
        f"UTC+2) fehlt — die heutigen Werte werden nicht gezeigt:\n{body}"
    )
    assert "🌡 10–18 °C" in body, (
        f"AC-3: die heutigen Messwerte '🌡 10–18 °C' aus dem datierten "
        f"Snapshot fehlen:\n{body}"
    )


# ══════════════════════ AC-4 (Reihenfolge) ══════════════════════

def test_undatierter_anker_schlaegt_den_datierten_snapshot():
    """AC-4.

    GIVEN fuer HEUTE tragen undatierter Anker (10–18 °C) und datierter
          Snapshot (25–33 °C) BEWUSST unterschiedliche Werte, und fuer MORGEN
          existiert nur der datierte Snapshot (15–25 °C),
    WHEN  beide Tage abgefragt werden,
    THEN  stammt der heutige Wert aus dem ANKER (nicht aus dem datierten
          Snapshot) und der morgige aus dem datierten Rueckfall.

    Faengt die Vertauschung der Quellen-Reihenfolge: laese die Implementierung
    zuerst den datierten Snapshot, zeigte heute 25–33 °C.
    """
    with freeze_time(EMPFANGEN_UTC):
        trip = _trip("ac4-reihenfolge", [HEUTE, MORGEN])
        # Lauf 1 — Morgen-Briefing mit den urspruenglichen (heissen) Werten.
        _briefing_lauf(
            trip.id,
            _tages_segmente(HEUTE, seg_id=1, temp_min=25.0, temp_max=33.0),
            HEUTE,
        )
        # Lauf 2 — Abend-Briefing: der datierte Snapshot fuer MORGEN entsteht.
        _briefing_lauf(
            trip.id,
            _tages_segmente(MORGEN, seg_id=2, temp_min=15.0, temp_max=25.0),
            MORGEN,
        )
        # Lauf 3 — Abfragepfad-Nachladung: setzt NUR den undatierten Anker
        # (``_fetch_and_save_snapshot``) und traegt fuer HEUTE frischere,
        # abweichende Werte. Der datierte Snapshot fuer heute bleibt heiss.
        _briefing_lauf_ohne_datierten(
            trip.id,
            _tages_segmente(HEUTE, seg_id=1, temp_min=10.0, temp_max=18.0),
            HEUTE,
        )
        heute_body = _befehl(trip, "### query: timeline_heute").confirmation_body
        morgen_body = _befehl(trip, "### query: timeline_morgen").confirmation_body

    assert "🌡 10–18 °C" in heute_body, (
        f"AC-4: erwartet wird der Wert aus dem UNDATIERTEN Anker "
        f"('🌡 10–18 °C'):\n{heute_body}"
    )
    assert "🌡 25–33 °C" not in heute_body, (
        f"AC-4: angezeigt wird der Wert aus dem DATIERTEN Snapshot "
        f"('🌡 25–33 °C') — die Quellen-Reihenfolge ist vertauscht:\n{heute_body}"
    )
    assert "🌡 15–25 °C" in morgen_body, (
        f"AC-4: fuer morgen traegt nur der datierte Snapshot Daten "
        f"('🌡 15–25 °C') — der Rueckfall greift nicht:\n{morgen_body}"
    )


# ══════════════════════ AC-5 ══════════════════════

def test_glance_meldet_nur_den_fehlenden_tag_als_luecke():
    """AC-5.

    GIVEN der Trip hat an beiden Tagen Etappen, der Anker traegt nach zwei
          einander ueberschreibenden Laeufen nur HEUTE, und fuer MORGEN
          existiert kein datierter Snapshot,
    WHEN  der Nutzer ``glance`` abfragt,
    THEN  meldet die MORGEN-Zeile fehlende Wetterdaten, waehrend die
          HEUTE-Zeile unveraendert aggregiert bleibt.

    Beide Zeilen werden geprueft: ein pauschales „alles ist eine Luecke" faellt
    hier ebenso durch wie das unveraenderte Bestandsverhalten.
    """
    with freeze_time(EMPFANGEN_UTC):
        trip = _anker_traegt_nur_heute("ac5-glance", [HEUTE, MORGEN])
        ergebnis = _befehl(trip, "### query: glance")

    body = ergebnis.confirmation_body
    assert ergebnis.success is True, body
    zeile_heute = _zeile(body, f"heute ({HEUTE:%d.%m})")
    zeile_morgen = _zeile(body, f"morgen ({MORGEN:%d.%m})")

    assert "🌡 10–18°C" in zeile_heute, (
        f"AC-5: die heutige Zeile muss unveraendert aggregiert bleiben "
        f"('🌡 10–18°C'):\n{zeile_heute}"
    )
    assert LUECKE not in zeile_heute, (
        f"AC-5: fuer heute liegen Daten vor — keine Luecken-Meldung "
        f"erwartet:\n{zeile_heute}"
    )
    assert FALSCHAUSSAGE not in zeile_morgen, (
        f"AC-5: die morgige Zeile behauptet {FALSCHAUSSAGE!r}, obwohl morgen "
        f"eine Etappe existiert:\n{zeile_morgen}"
    )
    assert LUECKE in zeile_morgen, (
        f"AC-5: die morgige Zeile muss fehlende Wetterdaten melden:\n{zeile_morgen}"
    )


# ══════════════════════ AC-6 ══════════════════════

def test_gewitterabfrage_meldet_datenluecke_statt_fehlender_etappe():
    """AC-6.

    GIVEN der Trip hat heute eine Etappe, der Anker traegt nur MORGEN und fuer
          HEUTE existiert kein datierter Snapshot,
    WHEN  der Nutzer ``heute_gewitter`` abfragt,
    THEN  meldet die Antwort fehlende Wetterdaten statt „Keine Etappe geplant
          — kein Gewitter-Status".
    """
    with freeze_time(EMPFANGEN_UTC):
        trip = _anker_traegt_nur_morgen("ac6-gewitter", [HEUTE, MORGEN])
        assert not (get_snapshots_dir("default") / f"{trip.id}_{HEUTE}.json").exists(), (
            "Testaufbau: es darf KEINEN datierten Snapshot fuer heute geben."
        )
        ergebnis = _befehl(trip, "### query: heute_gewitter")

    body = ergebnis.confirmation_body
    assert ergebnis.success is True, body
    assert FALSCHAUSSAGE not in body, (
        f"AC-6: die Gewitter-Antwort behauptet {FALSCHAUSSAGE!r}, obwohl heute "
        f"eine Etappe existiert und nur die Daten fehlen:\n{body}"
    )
    assert LUECKE in body, (
        f"AC-6: erwartete ehrliche Fehlanzeige {LUECKE!r} fehlt:\n{body}"
    )


# ══════════════════════ AC-7 ══════════════════════

def test_datenluecken_antwort_schreibt_nichts_und_ruft_nichts_ab(monkeypatch):
    """AC-7.

    GIVEN eine Abfrage wird bei fehlenden Daten beantwortet,
    WHEN  die Antwort erzeugt wird,
    THEN  loest sie keinen Wetter-Abruf aus und veraendert KEINE
          Snapshot-Datei — insbesondere bleibt ``briefing_backed`` des
          vorhandenen Ankers unveraendert.

    Nachweis ohne Mock-Rueckspiegelung: der Netzpfad
    (``TripReportSchedulerService._fetch_weather``) wird durch eine FALLE
    ersetzt, die den Aufruf protokolliert und zusaetzlich hart scheitert; der
    Dateizustand wird ueber Aenderungszeitstempel UND Byte-Inhalt aller
    Snapshot-Dateien vorher/nachher verglichen. Hier ist der Dateizustand
    selbst das geprueft Verhalten (Ausnahme zur Dateiinhalt-Regel).
    """
    abrufe: list[int] = []

    def _falle(self, segments):  # noqa: ANN001 — Signatur des Prueflings
        abrufe.append(len(segments))
        raise AssertionError(
            "AC-7: der Abfragepfad hat einen Wetter-Abruf ausgeloest."
        )

    monkeypatch.setattr(TripReportSchedulerService, "_fetch_weather", _falle)

    with freeze_time(EMPFANGEN_UTC):
        trip = _anker_traegt_nur_heute("ac7-keine-seiteneffekte", [HEUTE, MORGEN])
        anker = get_snapshots_dir("default") / f"{trip.id}.json"
        vorher = _schnappschuss_zustand()
        backed_vorher = json.loads(anker.read_text())["briefing_backed"]

        ergebnis = _befehl(trip, "### query: timeline_morgen")

        nachher = _schnappschuss_zustand()
        backed_nachher = json.loads(anker.read_text())["briefing_backed"]

    body = ergebnis.confirmation_body
    assert abrufe == [], (
        f"AC-7: der Abfragepfad hat {len(abrufe)} Wetter-Abruf(e) ausgeloest."
    )
    assert set(nachher) == set(vorher), (
        "AC-7: der Dateibestand im Snapshot-Verzeichnis hat sich geaendert — "
        f"neu/entfernt: {set(nachher) ^ set(vorher)}"
    )
    for name, (mtime, inhalt) in vorher.items():
        assert nachher[name][1] == inhalt, (
            f"AC-7: der Inhalt von {name} wurde durch die Abfrage veraendert."
        )
        assert nachher[name][0] == mtime, (
            f"AC-7: {name} wurde durch die Abfrage neu geschrieben "
            f"(Aenderungszeitstempel {mtime} -> {nachher[name][0]})."
        )
    assert backed_nachher == backed_vorher is True, (
        f"AC-7: `briefing_backed` des Ankers wurde veraendert "
        f"({backed_vorher} -> {backed_nachher}) — die Alarm-Vergleichsbasis "
        f"(ADR-0009) waere zerstoert."
    )
    assert LUECKE in body, (
        f"AC-7: Vorbedingung nicht erfuellt — die Abfrage hat gar keine "
        f"Datenluecken-Antwort erzeugt:\n{body}"
    )


# ══════════════════════ AC-8 ══════════════════════

def test_hinweistext_nennt_das_briefing_kommando_ohne_falsches_versprechen():
    """AC-8.

    GIVEN die ehrliche Fehlanzeige erscheint,
    WHEN  der Nutzer sie liest,
    THEN  verweist sie auf das Kommando, das FUER DIESEN TAG ein Briefing
          ausloest (``/m`` fuer morgen, ``/h`` fuer heute), und sagt
          ausschliesslich die ZUSTELLUNG des Briefings zu — sie verspricht
          NICHT, dass sich die Timeline-Ansicht danach fuellt.

    Begruendung des Verbots (Kontext, Risiko 5): ``morgen``/``heute``
    versenden ein volles Briefing, schreiben aber KEINEN Anker
    (``trip_report_scheduler.py:1495-1501``, #1007). Ein Text der Form „dann
    fuellt sich die Timeline" erzeugte eine Frustschleife.
    """
    zusagen = ("zugestellt", "zustellen", "gesendet", "sendet", "schickt",
               "verschickt", "verschicken")

    with freeze_time(EMPFANGEN_UTC):
        trip_morgen = _anker_traegt_nur_heute("ac8-morgen", [HEUTE, MORGEN])
        body_morgen = _befehl(
            trip_morgen, "### query: timeline_morgen").confirmation_body
        trip_heute = _anker_traegt_nur_morgen("ac8-heute", [HEUTE, MORGEN])
        body_heute = _befehl(
            trip_heute, "### query: heute_gewitter").confirmation_body

    for kommando, body, tag in (("/m", body_morgen, "morgen"),
                                ("/h", body_heute, "heute")):
        assert LUECKE in body, (
            f"AC-8: Vorbedingung nicht erfuellt — keine Datenluecken-Meldung "
            f"fuer {tag}:\n{body}"
        )
        assert kommando in body, (
            f"AC-8: der Hinweis fuer {tag} nennt das briefing-ausloesende "
            f"Kommando {kommando!r} nicht:\n{body}"
        )
        assert "Briefing" in body, (
            f"AC-8: der Hinweis fuer {tag} sagt nicht, dass ein Briefing "
            f"folgt:\n{body}"
        )
        assert any(w in body for w in zusagen), (
            f"AC-8: der Hinweis fuer {tag} sagt die ZUSTELLUNG des Briefings "
            f"nicht zu (erwartet eines von {zusagen}):\n{body}"
        )
        assert "füll" not in body.lower(), (
            f"AC-8: der Hinweis fuer {tag} verspricht, dass sich die Timeline "
            f"fuellt — das tut sie nicht, `morgen`/`heute` schreiben keinen "
            f"Anker (#1007):\n{body}"
        )
