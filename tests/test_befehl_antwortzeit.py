"""TDD RED -- #2439: Antwortzeit der Befehle (Zielgroesse, Vorwaermen, parallele Segmente).

Spec: docs/specs/modules/feat_2439_befehle_antwortzeit.md (AC-1, AC-2, AC-6 .. AC-11, AC-13)
Live-Gegenstuecke (AC-3/4/5/12/14): tests/e2e/test_push_eingang_befehle_staging.py
Doku-Pruefung (AC-17): tests/test_runbook_inbound_webhooks_eventname.py

Testart: Kern-Schicht, deterministisch, KEIN Netz ausser localhost (laeuft auch mit
``--disable-socket --allow-hosts=127.0.0.1,localhost``). Wetter kommt aus dem
``FixtureProvider`` (autouse-Naht aus tests/conftest.py); die DWD-Gewitterraster liefert
ein echter lokaler ``ThreadingHTTPServer`` (Bausteine aus
tests/tdd/test_dwd_thunder_parallel_fetch.py: ``_dwd_server`` zaehlt JEDEN Abruf).
Versand: die vier Kanal-Ausgaenge sind durch echte Aufzeichner-Klassen ersetzt
(tests/helpers/transport_mitschrift.py) -- kein ``Mock()``/``patch()``/``MagicMock``.
Nutzerkennungen tragen bewusst KEIN "test"/"tdd" (``is_test_user_id``).

=============================================================================
SCHNITTSTELLEN-VERTRAG FUER /50-implement (die Tests legen ihn fest)
=============================================================================
A. Journal-Zeilen (Python ``logging``; ``propagate`` bleibt True, damit ``caplog`` sie sieht):

  1. Dauer-Zeile, Logger ``befehl_dauer``, Level INFO, GENAU EINE je verarbeitetem Befehl,
     geschrieben am Ende von ``TripCommandProcessor.process`` (Eingang beim Core bis
     Ergebnis/Uebergabe an den Versand):
         befehl=<NAME> kanal=<email|telegram|sms|premium_sms> trip=<trip.id|-> dauer_ms=<int>
     <NAME> = HELP | CODES | STATUS | HEUTE | MORGEN | ... (Grossschreibung; ``hilfe`` -> HELP,
     ``kuerzel`` -> CODES). ``trip=-`` wenn kein Trip aufgeloest wurde. KEIN Nachrichtentext,
     KEINE Adresse/Nummer/Chat-ID in der Zeile. ``trip`` ist die Trip-ID (nicht der Name);
     fuer HELP/STATUS wird der Trip dazu per Name+user_id aufgeloest.

  2. Phasen-Zeile, Logger ``befehl_dauer``, Level INFO, je Phase des Briefing-Baus in
     ``TripReportSchedulerService._send_trip_report_outcome`` (gilt fuer geplanten Versand,
     On-Demand, Test-Versand gleichermassen):
         phase=<name> trip=<trip.id> dauer_ms=<int>
     <name> in {vorwaermen, zieltag, nacht, ausblick, gewitter_vorschau, ensemble, warnungen,
     rendern, versand}. Phasen sind DISJUNKT und nacheinander (keine verschachtelte
     Doppelzaehlung). Pflicht bei HEUTE: vorwaermen, zieltag, rendern, versand; die uebrigen
     nur, wenn die Phase laeuft.

  3. DWD-Fenster-Abschlusszeile, Logger ``dwd``, Level INFO, am Ende JEDES Aufrufs von
     ``DwdDirectProvider.fetch_thunder_signals_named``:
         dwd_fenster fenster_s=<float> downloads=<int> cache_treffer=<int>
     ``downloads`` = Anzahl tatsaechlicher Netz-Abrufe (``_thunder_request``), ``cache_treffer`` =
     Treffer im Punkt-Fenster-Cache.

  4. Fehlschlag des Vorwaermens: WARNING mit dem Text ``Vorwärmen fehlgeschlagen`` (mit
     Umlaut), Logger ``dwd`` (aus ``prewarm_windows``) bzw. ``trip_report_scheduler`` (falls
     der Aufrufer selbst eine Ausnahme fangen musste).

B. DWD-Vorwaermen (``src/providers/dwd.py``):
     DwdDirectProvider.prewarm_windows(location, windows, *, max_parallel=2) -> None
   ``windows`` = Sequenz von ``(start, end)`` (aware UTC) -- GENAU die Argumente, mit denen der
   spaetere Hauptabruf ``fetch_thunder_signals_named(location, start, end)`` ruft. Laedt die
   Fenster mit hoechstens ``max_parallel`` gleichzeitigen FENSTERN (jedes Fenster darf intern
   seine bestehenden ``THUNDER_PARALLEL_DOWNLOADS`` nutzen), verwirft das Ergebnis, BLOCKIERT
   bis alle Fenster fertig sind (Join, AC-8), dedupliziert/joint ueberlappende Schluessel
   (keine Datei zweimal laden) und WIRFT NIE. Ein Fenster gilt als fehlgeschlagen, wenn
   ``fetch_thunder_signals_named`` wirft ODER weder ein Download noch ein Cache-Treffer
   zustande kam -> Journal-Zeile A.4. Konstanten (monkeypatch-bar, ``raising=False``):
   ``dwd.THUNDER_PREWARM_PARALLEL_WINDOWS = 2``, ``dwd.THUNDER_PREWARM_DEADLINE_SECONDS``
   (Gesamtfrist des Vorwaermens; Ueberschreitung = Fehlschlag, Bericht laeuft weiter).
   ``dwd._RASTER_CACHE_MAX_URLS`` (und damit der globale ``dwd._RASTER_CACHE``) = 2048.

C. Scheduler (``src/services/trip_report_scheduler.py``):
     thunder_prewarm_windows(segments) -> list[tuple[datetime, datetime]]      # Modulfunktion
   Fuer jeden von den Segmenten beruehrten UTC-Kalendertag D ein Fenster mit DEMSELBEN Zuschnitt,
   den ``thunder_enrichment._fetch_lightning_density`` fuer eine Open-Meteo-Reihe bildet, die den
   GANZEN Tag D (00:00..23:00 UTC) enthaelt (auch bei einem 2-h-Segment!): von =
   ``max(D 00:00, volle aktuelle Stunde) - 1 h``, bis = ``D 23:00``. Der Hauptabruf trifft dann
   ausschliesslich Cache.
   ``_send_trip_report_outcome`` ruft VOR ``_fetch_weather`` das Vorwaermen (Phase ``vorwaermen``),
   UNABHAENGIG davon, welcher Wetteranbieter (Open-Meteo oder Fixture) den Hauptabruf bedient,
   und nur fuer Orte mit ``thunder_provider_for(lat, lon) == "de_direct"``. Ausnahmen im
   Vorwaermen werden gefangen (Zeile A.4) -- der Bericht laeuft weiter wie ohne Vorwaermen.
   TEST-NAHT (PFLICHT, sonst geht die ganze Kernsuite ans echte DWD): ist ``GZ_TEST_FIXTURE_DIR``
   gesetzt UND ``dwd.BASE_URL`` noch der Produktionswert (``https://opendata.dwd.de/...``),
   laeuft das Vorwaermen NICHT (Muster #346: kein Netz in der Kernsuite). Jede Umlenkung von
   ``dwd.BASE_URL`` (lokaler Testserver, wie in dieser Datei) schaltet es ein. Ohne diese Naht
   zoege jeder bestehende Kerntest mit Innsbruck-/Stubai-Briefing (kanaltreue,
   abruf_jede_metrik, ...) nach /50 ~250 MB echte GRIB-Dateien; ein toter Port waere ebenfalls
   keine Loesung (ConnectError wird mit >= 2 s Backoff je Datei wiederholt, gemessen ~20 s je
   10 Dateien). Bewacht von ``test_vorwaermen_laeuft_in_der_kernsuite_nicht_gegen_das_echte_dwd``.

D. Segmentschleife: ``TripReportSchedulerService._fetch_weather`` nutzt
   ``services.parallel_fetch.fetch_ordered(..., provider="open_meteo", ...)``; Ergebnisreihenfolge =
   Segmentreihenfolge; Retry/Backoff je Segment wie bisher.
   ENTSCHEIDUNG Worker-Thread (AC-10): ``fetch_ordered`` laeuft aus einem eigenen Pool-Worker INLINE
   seriell (Baustein bleibt unveraendert, Spec Out-of-Scope). Das ist akzeptiert, solange kein
   Deadlock entsteht und Reihenfolge/Vollstaendigkeit stimmen
   (``test_ac10_aufruf_aus_dem_parallel_pool_bleibt_korrekt_ohne_deadlock``). VERPFLICHTEND
   parallel muss der Aufruf aus einem normalen Thread laufen (so ruft ihn der API-Request-Thread)
   (``test_ac10_aufruf_aus_normalem_thread_laeuft_parallel``).

E. Prinzipien der Testwerte: Verzoegerungen 0,15-0,4 s je Datei/Segment, Verhaeltnis-Schranken
   (< 0,75 x serielle Summe) statt absoluter Zeiten.

=============================================================================
RED-STATUS (vor /50)
=============================================================================
 ROT:   AC-1 (11 Faelle), AC-2, AC-6, AC-7 (4), AC-8, AC-9 (3), AC-10 (parallel), AC-11 (Verdraengung)
 GRUEN (legitim, Regressionsschutz): AC-13 Golden (friert den ALTSTAND ein; muss nach /50
        unveraendert gruen bleiben), AC-10 Pool-Worker-Entscheidung.
 (AC-11 Speicher < 40 MB ist heute ROT, weil dieselbe Funktion auch die Kapazitaet >= 830
 verlangt; die 40-MB-Zusicherung allein bewacht gegen eine ueberdimensionierte Kapazitaet.)
 Das Golden deckt NUR den Open-Meteo-Fixture-Inhalt des Berichts ab (keine DWD-Rasterwerte;
 die fliessen im Fixture-Pfad nicht ein).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import re
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.config import Location  # noqa: E402
from app.loader import load_all_trips, save_trip  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    TripReportConfig, TripSegment,
)
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from providers import dwd  # noqa: E402
from services import parallel_fetch  # noqa: E402
from services import trip_report_scheduler as scheduler_mod  # noqa: E402
from services.trip_command_processor import InboundMessage, TripCommandProcessor  # noqa: E402
from services.trip_report_scheduler import TripReportSchedulerService  # noqa: E402
from tests.helpers.transport_mitschrift import aufzeichner_installieren  # noqa: E402
from tests.tdd.test_dwd_thunder_parallel_fetch import _dwd_server, _raster  # noqa: E402
from tests.tdd.test_kanaltreue_adhoc_antwort import (  # noqa: E402
    _TRANSPORT_ENV, _kennung, _nutzer_anlegen, _trip_anlegen,
)
from utils.timezone import tz_for_coords  # noqa: E402

_PROD_BASE_URL = dwd.BASE_URL  # VOR jedem Patch festgehalten (Produktionswert)
LOGGER_DAUER = "befehl_dauer"
VORWAERMEN_FEHLT = "Vorwärmen fehlgeschlagen"
_RE_DAUER = re.compile(r"befehl=(\S+) kanal=(\S+) trip=(\S+) dauer_ms=(\d+)")
_RE_PHASE = re.compile(r"phase=(\w+) trip=(\S+) dauer_ms=(\d+)")
_RE_FENSTER = re.compile(r"fenster_s=(\d+(?:\.\d+)?) downloads=(\d+) cache_treffer=(\d+)")
_PHASEN = {"vorwaermen", "zieltag", "nacht", "ausblick", "gewitter_vorschau",
           "ensemble", "warnungen", "rendern", "versand"}
_PFLICHT_PHASEN_HEUTE = {"vorwaermen", "zieltag", "rendern", "versand"}

INNSBRUCK = (47.2692, 11.4041)
REYKJAVIK = (64.14, -21.90)  # keine Sommerzeit -> Golden driftet nicht mit der Zeitumstellung
KARNISCH = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")
GOLDEN = ROOT / "tests" / "fixtures" / "befehl_antwortzeit" / "golden_berichte.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _sauberer_zustand(monkeypatch):
    """Eigener autouse-Zustand (NICHT aus der DWD-Testdatei importiert: ein importierter
    autouse-Fixture wuerde sonst in dieses Modul wirken)."""
    dwd._RASTER_CACHE.clear()
    parallel_fetch._reset_for_tests()
    # Default: DWD zeigt auf einen lokalen Server, der SOFORT 404 liefert -- nichts geht je ins
    # Internet. Bewusst KEIN toter Port: ``ConnectError`` ist in ``_thunder_request`` retrybar
    # (Backoff >= 2 s je Datei, gemessen ~20 s fuer 10 Dateien); 404 wird nicht wiederholt.
    with _dwd_server(monkeypatch, regel=lambda _p, _l, _t: ("status", 404)):
        yield
    dwd._RASTER_CACHE.clear()
    parallel_fetch._reset_for_tests()


@pytest.fixture
def mitschrift(monkeypatch):
    for name, wert in _TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    return aufzeichner_installieren(monkeypatch)


# ---------------------------------------------------------------------------
# Hilfen: Journal, Befehl-Draht, Einstiege
# ---------------------------------------------------------------------------

def _zeilen(caplog, logger_name: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == logger_name]


def _dauer_zeilen(caplog) -> list[tuple[str, str, str, int]]:
    treffer = []
    for text in _zeilen(caplog, LOGGER_DAUER):
        m = _RE_DAUER.search(text)
        if m:
            treffer.append((m.group(1), m.group(2), m.group(3), int(m.group(4))))
    return treffer


def _phasen(caplog) -> list[tuple[str, str, int]]:
    treffer = []
    for text in _zeilen(caplog, LOGGER_DAUER):
        m = _RE_PHASE.search(text)
        if m:
            treffer.append((m.group(1), m.group(2), int(m.group(3))))
    return treffer


def _dwd_fenster(caplog) -> list[tuple[float, int, int]]:
    return [(float(m.group(1)), int(m.group(2)), int(m.group(3)))
            for t in _zeilen(caplog, "dwd") if (m := _RE_FENSTER.search(t))]


def _befehl(trip_name: str, body: str, *, kanal: str, uid: str, absender: str):
    t0 = time.monotonic()
    ergebnis = TripCommandProcessor().process(InboundMessage(
        trip_name=trip_name, body=body, sender=absender, channel=kanal,
        received_at=datetime.now(timezone.utc), user_id=uid,
    ))
    return ergebnis, (time.monotonic() - t0) * 1000.0


def _vorwaermen_einstieg(provider):
    einstieg = getattr(provider, "prewarm_windows", None)
    if not callable(einstieg):
        pytest.fail("DwdDirectProvider.prewarm_windows fehlt (Vertrag B) -- das Vorwaermen "
                    "der DWD-Tagesfenster ist noch nicht gebaut")
    return einstieg


def _prewarm_fenster(einstieg, location, windows, **kw):
    return einstieg(location, windows, **kw)


def _lauf(now=None) -> datetime:
    return dwd._latest_run(now or datetime.now(timezone.utc))


def _fenster(i: int, *, laenge_h: int = 5, versatz_h: int = 6) -> tuple[datetime, datetime]:
    """Fenster i: Offsets (bezogen auf den Lauf) ``6i+2 .. 6i+1+laenge`` -- disjunkt zu den
    anderen, alle weit unter THUNDER_MAX_TIMESTEP (48), damit nie ein Fenster still leer bleibt."""
    start = _lauf() + timedelta(hours=versatz_h * i + 1)
    return start, start + timedelta(hours=laenge_h)


def _fenster_index(ttt: int, versatz_h: int = 6) -> int:
    return (ttt - 1) // versatz_h


# ---------------------------------------------------------------------------
# AC-1: Dauer-Zeile je Befehl, ohne personenbezogene Inhalte, Multi-User
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["email", "telegram", "sms", "premium_sms"])
@pytest.mark.parametrize("body,erwartet", [("### hilfe", "HELP"), ("### status", "STATUS")])
def test_ac1_jeder_befehl_schreibt_genau_eine_dauer_zeile(
    caplog, mitschrift, kanal, body, erwartet,
):
    """AC-1: genau eine Zeile mit Befehl, Kanal, Trip-ID und Dauer in ms -- je Kanal."""
    caplog.set_level(logging.INFO)
    uid = _kennung("dz1")
    _nutzer_anlegen(uid, mail="dz1@example.invalid", chat_id="chat-dz1")
    trip = _trip_anlegen(uid, name="Dauer Zeile Eins")

    ergebnis, wand_ms = _befehl(trip.name, body, kanal=kanal, uid=uid,
                                absender="dz1@example.invalid")

    zeilen = _dauer_zeilen(caplog)
    assert len(zeilen) == 1, (
        f"AC-1: erwartet GENAU EINE Dauer-Zeile (Logger {LOGGER_DAUER!r}, Format "
        f"'befehl=.. kanal=.. trip=.. dauer_ms=..'), gefunden {len(zeilen)}; "
        f"Journal dieses Loggers: {_zeilen(caplog, LOGGER_DAUER)}"
    )
    befehl, zeile_kanal, zeile_trip, dauer_ms = zeilen[0]
    assert (befehl, zeile_kanal, zeile_trip) == (erwartet, kanal, trip.id), (
        f"AC-1: Befehl/Kanal/Trip-ID falsch: {zeilen[0]} (erwartet {erwartet}/{kanal}/{trip.id})"
    )
    assert 0 <= dauer_ms <= wand_ms + 50, (
        f"AC-1: dauer_ms={dauer_ms} passt nicht zur gemessenen Wanduhr {wand_ms:.0f} ms"
    )
    assert ergebnis.command != "error", f"Vorbedingung: Befehl lief durch: {ergebnis}"


def test_ac1_zwei_nutzer_jede_zeile_traegt_die_eigene_trip_id(caplog, mitschrift):
    """AC-1 Multi-User: zwei Nutzer, je eigener Trip -> jede Zeile die EIGENE Trip-ID
    (nie die des anderen, nie ein 'default'-Rueckfall)."""
    caplog.set_level(logging.INFO)
    uid_a, uid_b = _kennung("dza"), _kennung("dzb")
    _nutzer_anlegen(uid_a, mail="dza@example.invalid", chat_id="chat-dza")
    _nutzer_anlegen(uid_b, mail="dzb@example.invalid", chat_id="chat-dzb")
    trip_a = _trip_anlegen(uid_a, name="Dauer Nutzer A")
    trip_b = _trip_anlegen(uid_b, name="Dauer Nutzer B")
    assert trip_a.id != trip_b.id

    _befehl(trip_a.name, "### hilfe", kanal="email", uid=uid_a, absender="dza@example.invalid")
    _befehl(trip_b.name, "### hilfe", kanal="telegram", uid=uid_b, absender="chat-dzb")

    zeilen = _dauer_zeilen(caplog)
    assert [(z[1], z[2]) for z in zeilen] == [("email", trip_a.id), ("telegram", trip_b.id)], (
        f"AC-1: jede Zeile muss die Trip-ID ihres Nutzers tragen, gefunden {zeilen}"
    )


def test_ac1_zeile_enthaelt_weder_nachrichtentext_noch_adresse_noch_nummer(
    caplog, mitschrift,
):
    """AC-1 Gegenprobe: im Journal des Dauer-Loggers steht nichts Personenbezogenes."""
    caplog.set_level(logging.INFO)
    uid = _kennung("dzg")
    _nutzer_anlegen(uid, mail="dzg@example.invalid", chat_id="chat-dzg")
    trip = _trip_anlegen(uid, name="Dauer Gegenprobe")
    absender = "geheimer.absender@example.invalid"

    _befehl(trip.name, "### status\nGEHEIMTEXT4711", kanal="email", uid=uid, absender=absender)
    _befehl(trip.name, "### hilfe", kanal="premium_sms", uid=uid, absender="+490000000002")

    zeilen = _zeilen(caplog, LOGGER_DAUER)
    assert len(_dauer_zeilen(caplog)) == 2, f"Vorbedingung: zwei Dauer-Zeilen, Journal: {zeilen}"
    gesamt = "\n".join(zeilen)
    for verboten in (absender, "GEHEIMTEXT4711", "@", "+49", "chat-dzg", "example.invalid"):
        assert verboten not in gesamt, (
            f"AC-1: {verboten!r} darf nicht im Dauer-Journal stehen: {zeilen}"
        )


def test_ac1_heute_mit_wetterabruf_misst_die_echte_rechenzeit(caplog, mitschrift):
    """AC-1: auch der Wetter-Befehl schreibt die Zeile -- und dauer_ms ist die gemessene
    Rechenzeit (kein konstanter Platzhalter): zwischen 70 % und 100 % der Wanduhr."""
    caplog.set_level(logging.INFO)
    uid = _kennung("dzh")
    _nutzer_anlegen(uid, mail="dzh@example.invalid", chat_id="chat-dzh")
    trip = _trip_anlegen(uid, name="Dauer Heute")

    ergebnis, wand_ms = _befehl(trip.name, "### query: heute", kanal="email", uid=uid,
                                absender="dzh@example.invalid")

    assert ergebnis.success, f"Vorbedingung: HEUTE lief durch: {ergebnis}"
    zeilen = _dauer_zeilen(caplog)
    assert len(zeilen) == 1 and zeilen[0][:3] == ("HEUTE", "email", trip.id), (
        f"AC-1: erwartet eine HEUTE-Zeile fuer {trip.id}, gefunden {zeilen}"
    )
    assert 0.7 * wand_ms <= zeilen[0][3] <= wand_ms + 50, (
        f"AC-1: dauer_ms={zeilen[0][3]} vs Wanduhr {wand_ms:.0f} ms -- die Zeile muss die "
        f"Rechenzeit des Befehls messen"
    )


# ---------------------------------------------------------------------------
# AC-2: Phasenzeiten + DWD-Fensterzeile
# ---------------------------------------------------------------------------

def test_ac2_heute_gibt_phasenzeiten_und_dwd_fenster_aus_summe_nahe_gesamtdauer(
    caplog, mitschrift, monkeypatch,
):
    """AC-2: je Phase eine Zeile, je DWD-Tagesfenster fenster_s/downloads/cache_treffer;
    Summe der Phasen liegt innerhalb 10 % (mindestens 0,25 s Spielraum gegen CI-Jitter) der
    Gesamtdauer-Zeile."""
    caplog.set_level(logging.INFO)
    uid = _kennung("dzp")
    _nutzer_anlegen(uid, mail="dzp@example.invalid", chat_id="chat-dzp")
    trip = _trip_anlegen(uid, name="Dauer Phasen")

    with _dwd_server(monkeypatch, verzoegerung_s=0.02) as server:
        ergebnis, _ = _befehl(trip.name, "### query: heute", kanal="email", uid=uid,
                              absender="dzp@example.invalid")
        abrufe = len(server.kopie())

    assert ergebnis.success, f"Vorbedingung: HEUTE lief durch: {ergebnis}"
    phasen = _phasen(caplog)
    namen = {p[0] for p in phasen}
    assert _PFLICHT_PHASEN_HEUTE <= namen, (
        f"AC-2: Pflicht-Phasen {sorted(_PFLICHT_PHASEN_HEUTE)} fehlen im Journal "
        f"(Format 'phase=<name> trip=<id> dauer_ms=<n>' auf Logger {LOGGER_DAUER!r}); "
        f"gefunden: {sorted(namen)}"
    )
    assert namen <= _PHASEN, f"AC-2: unbekannte Phasennamen {sorted(namen - _PHASEN)}"
    assert {p[1] for p in phasen} == {trip.id}, f"Phasen tragen nicht die Trip-ID: {phasen}"

    dauer = _dauer_zeilen(caplog)
    assert len(dauer) == 1, f"Vorbedingung: eine Gesamtdauer-Zeile, gefunden {dauer}"
    gesamt_ms, summe_ms = dauer[0][3], sum(p[2] for p in phasen)
    assert abs(summe_ms - gesamt_ms) <= max(0.10 * gesamt_ms, 250), (
        f"AC-2: Summe der Phasen {summe_ms} ms weicht von der Gesamtdauer {gesamt_ms} ms "
        f"um mehr als 10 % ab: {phasen}"
    )

    fenster = _dwd_fenster(caplog)
    assert abrufe > 0, "Vorbedingung: das Vorwaermen hat den lokalen Raster-Server abgefragt"
    assert fenster, (
        "AC-2: keine DWD-Fensterzeile 'dwd_fenster fenster_s=.. downloads=.. cache_treffer=..' "
        "auf Logger 'dwd'"
    )
    assert sum(f[1] for f in fenster) > 0 and all(f[0] >= 0 for f in fenster)


# ---------------------------------------------------------------------------
# AC-6: Vorwaermen -- hoechstens 2 Fenster gleichzeitig, Gesamtzeit << Summe
# ---------------------------------------------------------------------------

def _aktive_fenster_spitze(abrufe: list, versatz_h: int = 6) -> tuple[int, dict]:
    """Spitze gleichzeitig AKTIVER FENSTER (nicht Verbindungen): Aktivitaetsspanne eines
    Fensters = erste bis letzte Ankunft; Zuordnung ueber den Zeitschritt (ttt)."""
    spannen: dict[int, list] = {}
    for ankunft, _param, _lauf_str, ttt, _status in abrufe:
        spanne = spannen.setdefault(_fenster_index(ttt, versatz_h), [ankunft, ankunft])
        spanne[0], spanne[1] = min(spanne[0], ankunft), max(spanne[1], ankunft)
    ereignisse = sorted([(s[0], 1) for s in spannen.values()] + [(s[1] + 1e-6, -1)
                                                                  for s in spannen.values()])
    aktiv = spitze = 0
    for _zeit, delta in ereignisse:
        aktiv += delta
        spitze = max(spitze, aktiv)
    return spitze, spannen


def test_ac6_vorwaermen_laedt_hoechstens_zwei_fenster_gleichzeitig_und_ueberlappt_wartezeit(
    monkeypatch,
):
    """AC-6: vier disjunkte Fenster -> Spitze der gleichzeitig aktiven Fenster == 2 und
    Gesamtzeit < 0,75 x (4 x Einzelzeit eines Fensters)."""
    provider = dwd.DwdDirectProvider()
    einstieg = _vorwaermen_einstieg(provider)
    with _dwd_server(monkeypatch, verzoegerung_s=0.15) as server:
        t0 = time.monotonic()
        _prewarm_fenster(einstieg, KARNISCH, [_fenster(0)])
        einzel_s = time.monotonic() - t0
        dwd._RASTER_CACHE.clear()
        server.abrufe.clear()

        fenster = [_fenster(i) for i in range(4)]
        t0 = time.monotonic()
        _prewarm_fenster(einstieg, KARNISCH, fenster)
        gesamt_s = time.monotonic() - t0
        abrufe = server.kopie()

    spitze, spannen = _aktive_fenster_spitze(abrufe)
    assert sorted(spannen) == [0, 1, 2, 3], (
        f"Vorbedingung: alle vier Fenster haben Dateien geladen, Fenster mit Abrufen: "
        f"{sorted(spannen)} (sonst waere der Vergleich leer)"
    )
    assert spitze == 2, (
        f"AC-6: erwartet GENAU 2 gleichzeitig aktive Fenster (Pool 2), gemessen {spitze}"
    )
    assert gesamt_s < 0.75 * 4 * einzel_s, (
        f"AC-6: Gesamtzeit {gesamt_s:.2f} s ist nicht < 0,75 x Summe der Einzelzeiten "
        f"({4 * einzel_s:.2f} s) -- Wartezeiten ueberlappen nicht"
    )


# ---------------------------------------------------------------------------
# AC-7: nach dem Vorwaermen 0 Downloads im Hauptabruf (Schluesselgleichheit)
# ---------------------------------------------------------------------------

def _segment(tag: date, h0: int, h1: int, *, lat: float, lon: float, nr: int = 1) -> TripSegment:
    start = datetime(tag.year, tag.month, tag.day, tzinfo=timezone.utc) + timedelta(hours=h0)
    ende = datetime(tag.year, tag.month, tag.day, tzinfo=timezone.utc) + timedelta(hours=h1)
    return TripSegment(
        segment_id=nr,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=800.0),
        end_point=GPXPoint(lat=lat + 0.01, lon=lon + 0.01, elevation_m=900.0),
        start_time=start, end_time=ende, duration_hours=float(h1 - h0),
        distance_km=4.0, ascent_m=100.0, descent_m=0.0,
    )


def _om_tagesreihe(tag: date) -> NormalizedTimeseries:
    """So liefert Open-Meteo einen Abruf mit start_date == end_date == tag: 24 volle Stunden,
    UNABHAENGIG von der Segmentlaenge (openmeteo.py:1112-1114)."""
    anfang = datetime(tag.year, tag.month, tag.day, tzinfo=timezone.utc)
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.0)
    return NormalizedTimeseries(meta=meta, data=[
        ForecastDataPoint(ts=anfang + timedelta(hours=h), t2m_c=5.0) for h in range(24)])


@pytest.mark.parametrize("tag_versatz", [0, 1], ids=["heute", "morgen"])
@pytest.mark.parametrize("segment_h", [(10, 12), (5, 21)], ids=["segment_2h", "segment_ganztaegig"])
def test_ac7_hauptabruf_nach_dem_vorwaermen_macht_null_downloads(
    monkeypatch, tag_versatz, segment_h,
):
    """AC-7: das vorgewaermte Fenster ist SCHLUESSELGLEICH mit dem, das der echte Hauptabruf
    (``thunder_enrichment.enrich_thunder`` auf der Open-Meteo-Tagesreihe) bildet -- auch fuer
    ein 2-h-Segment. Gemessen wird der Download-Zaehler des Servers, nicht die Zeit.
    Das Fenster kommt aus ``thunder_prewarm_windows`` (Vertrag C), NICHT aus einer vom Test
    gewaehlten Zuschneidung."""
    from providers.thunder_enrichment import enrich_thunder

    zuschnitt = getattr(scheduler_mod, "thunder_prewarm_windows", None)
    if not callable(zuschnitt):
        pytest.fail("trip_report_scheduler.thunder_prewarm_windows fehlt (Vertrag C)")
    einstieg = _vorwaermen_einstieg(dwd.DwdDirectProvider())
    tag = datetime.now(timezone.utc).date() + timedelta(days=tag_versatz)
    segment = _segment(tag, *segment_h, lat=KARNISCH.latitude, lon=KARNISCH.longitude)

    with _dwd_server(monkeypatch, verzoegerung_s=0.0) as server:
        fenster = zuschnitt([segment])
        assert fenster, "thunder_prewarm_windows lieferte keine Fenster"
        _prewarm_fenster(einstieg, KARNISCH, fenster)
        nach_vorwaermen = len(server.kopie())
        assert nach_vorwaermen > 0, "Vorbedingung: das Vorwaermen hat Dateien geladen"

        # geosphere als "bereits befragt": die additive Zusatzquelle bliebe sonst im Internet.
        enrich_thunder(_om_tagesreihe(tag), KARNISCH, bereits_befragt="geosphere")
        zusaetzlich = len(server.kopie()) - nach_vorwaermen

    assert zusaetzlich == 0, (
        f"AC-7: der Hauptabruf lud noch {zusaetzlich} Datei(en) nach -- vorgewaermtes Fenster "
        f"und Hauptabruf sind nicht schluesselgleich (Segment {segment_h[0]}-{segment_h[1]} h, "
        f"Tag {tag}); Fenster waren {fenster}"
    )


# ---------------------------------------------------------------------------
# AC-8: Join -- keine Datei doppelt, Vorwaermen blockiert bis zum Ende
# ---------------------------------------------------------------------------

def test_ac8_ueberlappende_fenster_laden_jede_datei_hoechstens_einmal_und_blockieren(
    monkeypatch,
):
    """AC-8: Fenster A und B starten gleichzeitig und ueberlappen (B Teilmenge von A):
    ohne Join/Dedup liefen die ueberlappenden Dateien doppelt. Dazu: nach der Rueckkehr von
    ``prewarm_windows`` kommt kein Nachzuegler mehr (Hauptabruf startet erst nach Ende)."""
    einstieg = _vorwaermen_einstieg(dwd.DwdDirectProvider())
    start = _lauf() + timedelta(hours=1)
    a = (start, start + timedelta(hours=5))
    b = (start, start + timedelta(hours=3))
    verzoegerung = 0.2

    with _dwd_server(monkeypatch, verzoegerung_s=verzoegerung) as server:
        _prewarm_fenster(einstieg, KARNISCH, [a, b])
        rueckkehr = time.monotonic()
        zahl_bei_rueckkehr = len(server.kopie())
        time.sleep(0.8)
        abrufe = server.kopie()

    assert len(abrufe) == zahl_bei_rueckkehr > 0, (
        f"AC-8: nach der Rueckkehr liefen noch Abrufe weiter ({zahl_bei_rueckkehr} -> "
        f"{len(abrufe)}) -- das Vorwaermen blockiert nicht bis zum Ende (Join)"
    )
    schluessel = [(param, lauf, ttt) for _t, param, lauf, ttt, status in abrufe if status == 200]
    doppelt = sorted({s for s in schluessel if schluessel.count(s) > 1})
    assert not doppelt, (
        f"AC-8: {len(doppelt)} Datei(en) wurden mehrfach geladen, z.B. {doppelt[:3]} "
        f"(Rueckkehr {rueckkehr:.2f})"
    )
    assert len(schluessel) == len(set(schluessel))


# ---------------------------------------------------------------------------
# AC-9: Vorwaermen scheitert -> Bericht kommt trotzdem, Journal vermerkt es
# ---------------------------------------------------------------------------

def test_ac9_prewarm_windows_wirft_nie_und_vermerkt_den_fehlschlag(monkeypatch, caplog):
    """AC-9 (DWD-Ebene): Server antwortet auf alles mit 404 -> kein Wurf, Zeile
    'Vorwärmen fehlgeschlagen' auf dem Logger 'dwd'."""
    caplog.set_level(logging.INFO)
    einstieg = _vorwaermen_einstieg(dwd.DwdDirectProvider())

    with _dwd_server(monkeypatch, regel=lambda p, l, t: ("status", 404)):
        _prewarm_fenster(einstieg, KARNISCH, [_fenster(0), _fenster(1)])

    treffer = [r for r in caplog.records
               if r.name == "dwd" and VORWAERMEN_FEHLT in r.getMessage()
               and r.levelno >= logging.WARNING]
    assert treffer, (
        f"AC-9: keine WARNING {VORWAERMEN_FEHLT!r} auf dem Logger 'dwd'; "
        f"dwd-Journal: {_zeilen(caplog, 'dwd')[-5:]}"
    )


def _golden_trip(uid: str, lat: float, lon: float, *, tage: int = 4) -> Trip:
    """Fester Trip (feste IDs/Namen, Etappen gestern..uebermorgen, Ortstag) -- fuer Golden
    und Vorwaermen-Vergleiche. 4 Etappen: die Fixture traegt nur 72 h ab heute 00:00 UTC,
    weitere Tage waeren leer (Fehlerpfad statt Normalfall)."""
    heute = datetime.now(timezone.utc).astimezone(tz_for_coords(lat, lon)).date()
    stages = [
        Stage(id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
              waypoints=[Waypoint(id=f"G{i}a", name="Start", lat=lat, lon=lon, elevation_m=600),
                         Waypoint(id=f"G{i}b", name="Ziel", lat=lat + 0.02, lon=lon + 0.02,
                                  elevation_m=900)])
        for i in range(tage)
    ]
    trip = Trip(id="golden-2439", name="Golden Trip", stages=stages,
                official_alerts_enabled=False,
                report_config=TripReportConfig(
                    trip_id="golden-2439", send_email=True, send_sms=True,
                    send_premium_sms=True, send_telegram=True))
    save_trip(trip, uid)
    return next(t for t in load_all_trips(uid) if t.id == "golden-2439")


def _normalisiere(text: str, *uids: str) -> str:
    """Entfernt NUR Tages-/Uhrzeit-Anteile, die mit dem Kalender wandern (Datum, Wochentag,
    Erstellstempel, Nutzerkennung). Werte, Reihenfolge und Struktur bleiben bit-genau."""
    for uid in uids:
        text = text.replace(uid, "<UID>")
    text = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", "<STEMPEL-UTC>", text)
    text = re.sub(r"\b(?:Mo|Di|Mi|Do|Fr|Sa|So)\b", "<WT>", text)
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}", "<DATUM>", text)
    text = re.sub(r"(<WT> · (?:<DATUM> · )?)\d{2}:\d{2}(?: [A-Z]{3,4})?", r"\1<UHR>", text)
    return text


def _unnormalisiert_uebrig(text: str) -> list[str]:
    """Stichproben-Waechter: kein Kalenderrest (dd.mm. der naechsten Tage) darf uebrig sein."""
    heute = datetime.now(timezone.utc).date()
    reste = [f"{(heute + timedelta(days=d)):%d.%m.}" for d in range(-2, 6)]
    return [r for r in reste if r in text]


def _bericht_aufnehmen(mitschrift, uid: str, lat: float, lon: float) -> dict:
    """Test-Versand 'evening' ueber alle vier Kanaele (derselbe ``_send_trip_report_outcome``-
    Pfad wie On-Demand/Slot), Ausgabe normalisiert."""
    _nutzer_anlegen(uid, mail="golden@example.invalid", chat_id="chat-golden")
    trip = _golden_trip(uid, lat, lon)
    mitschrift.leeren()
    ausgang = TripReportSchedulerService(user_id=uid).send_test_report_outcome(trip, "evening")
    ergebnis: dict = {"ausgang": ausgang}
    for kanal in mitschrift.kanaele:
        sendungen = mitschrift.sendungen(kanal)
        ergebnis[kanal] = [{
            "subject": _normalisiere(s["subject"] or "", uid),
            "body": _normalisiere(s["body"] or "", uid),
            "plain_text_body": _normalisiere(s["plain_text_body"] or "", uid),
        } for s in sendungen]
    return ergebnis


def test_ac9_bericht_kommt_trotz_fehlgeschlagenem_vorwaermen_inhaltsgleich(
    mitschrift, monkeypatch, caplog,
):
    """AC-9 (Bericht): Vorwaermen scheitert (404 bzw. Haenger) -> Bericht wird trotzdem
    erzeugt/versendet, Inhalt == Inhalt bei FUNKTIONIERENDEM Vorwaermen, Journal vermerkt es."""
    caplog.set_level(logging.INFO)
    with _dwd_server(monkeypatch, verzoegerung_s=0.0):
        gut = _bericht_aufnehmen(mitschrift, "befehlzeit-g1", *INNSBRUCK)

    caplog.clear()
    monkeypatch.setattr(dwd, "THUNDER_REQUEST_TIMEOUT", 0.3, raising=True)
    monkeypatch.setattr(dwd, "THUNDER_FETCH_DEADLINE_SECONDS", 1.5, raising=True)
    monkeypatch.setattr(dwd, "THUNDER_PREWARM_DEADLINE_SECONDS", 3.0, raising=False)
    with _dwd_server(monkeypatch, regel=lambda p, l, t: ("hang", 30)):
        schlecht = _bericht_aufnehmen(mitschrift, "befehlzeit-g2", *INNSBRUCK)

    assert schlecht["ausgang"] == "sent" and "email" in schlecht, (
        f"AC-9: der Bericht muss trotz Haenger versendet werden: {list(schlecht)}"
    )
    assert schlecht == gut, "AC-9: Inhalt weicht ab, sobald das Vorwaermen scheitert"
    meldungen = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(VORWAERMEN_FEHLT in m for m in meldungen), (
        f"AC-9: keine Journal-Zeile {VORWAERMEN_FEHLT!r} (WARNING) -- gefunden: "
        f"{[m[:90] for m in meldungen][-6:]}"
    )


def test_ac9_befehl_heute_wird_beantwortet_wenn_der_dwd_nur_404_liefert(
    mitschrift, monkeypatch, caplog,
):
    """AC-9 ueber den echten Befehlsweg (HEUTE, E-Mail): Antwort geht raus, Fehlschlag steht im
    Journal."""
    caplog.set_level(logging.INFO)
    uid = _kennung("dz9")
    _nutzer_anlegen(uid, mail="dz9@example.invalid", chat_id="chat-dz9")
    trip = _trip_anlegen(uid, name="Dauer Fehlschlag")

    with _dwd_server(monkeypatch, regel=lambda p, l, t: ("status", 404)):
        ergebnis, _ = _befehl(trip.name, "### query: heute", kanal="email", uid=uid,
                              absender="dz9@example.invalid")

    assert ergebnis.success and mitschrift.kanaele == ["email"], (
        f"AC-9: HEUTE muss trotz DWD-Ausfall beantwortet werden, "
        f"success={ergebnis.success}, Kanaele={mitschrift.kanaele}"
    )
    assert any(VORWAERMEN_FEHLT in r.getMessage() for r in caplog.records
               if r.levelno >= logging.WARNING), (
        f"AC-9: Journal-Zeile {VORWAERMEN_FEHLT!r} fehlt"
    )


def test_vorwaermen_laeuft_in_der_kernsuite_nicht_gegen_das_echte_dwd(
    mitschrift, monkeypatch, caplog,
):
    """Test-Naht (Vertrag C): im Kerntestlauf (``GZ_TEST_FIXTURE_DIR`` gesetzt) mit dem
    PRODUKTIONS-``BASE_URL`` versucht das Vorwaermen gar kein Netz -- Sockets sind hier hart
    gesperrt, ein Versuch endete als 'Vorwärmen fehlgeschlagen'. Schuetzt die uebrige Kernsuite
    (Innsbruck-Briefings in kanaltreue, abruf_jede_metrik, ...) davor, nach /50 echte GRIB-
    Dateien zu laden. LEGITIM GRUEN im RED-Stand (es gibt noch kein Vorwaermen)."""
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(dwd, "BASE_URL", _PROD_BASE_URL, raising=True)
    uid = _kennung("dzn")
    _nutzer_anlegen(uid, mail="dzn@example.invalid", chat_id="chat-dzn")
    trip = _trip_anlegen(uid, name="Dauer Naht")

    # Sockets erst NACH dem Aufbau sperren (der lokale 404-Server aus dem autouse-Fixture steht
    # schon) und exakt auf den vorherigen Zustand zuruecksetzen -- gleich ob die Suite selbst
    # mit --disable-socket laeuft.
    import socket
    import pytest_socket
    vorher = socket.socket
    pytest_socket.disable_socket(allow_unix_socket=True)
    try:
        ergebnis, _ = _befehl(trip.name, "### query: heute", kanal="email", uid=uid,
                              absender="dzn@example.invalid")
    finally:
        socket.socket = vorher

    assert ergebnis.success and mitschrift.kanaele == ["email"], (
        f"Vorbedingung: HEUTE lief offline durch: success={ergebnis.success}, "
        f"Kanaele={mitschrift.kanaele}"
    )
    schlecht = [r.getMessage()[:120] for r in caplog.records
                if r.levelno >= logging.WARNING and r.name in ("dwd", "trip_report_scheduler")
                and ("Vorwärmen" in r.getMessage() or "Socket" in r.getMessage())]
    assert not schlecht, f"Das Vorwaermen hat in der Kernsuite Netz versucht: {schlecht}"


# ---------------------------------------------------------------------------
# AC-10: Segmentschleife parallel, geordnet, mit Retry; Worker-Thread-Entscheidung
# ---------------------------------------------------------------------------

class _VerzoegerungsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr):
        super().__init__(addr, _VerzoegerungsHandler)
        self.sperre = threading.Lock()
        self.aktiv = 0
        self.spitze = 0
        self.aufrufe = 0


class _VerzoegerungsHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        verzoegerung = float(parse_qs(urlparse(self.path).query).get("d", ["0"])[0])
        srv = self.server
        with srv.sperre:
            srv.aktiv += 1
            srv.aufrufe += 1
            srv.spitze = max(srv.spitze, srv.aktiv)
        time.sleep(verzoegerung)
        with srv.sperre:
            srv.aktiv -= 1
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


class _ServerAnbieter:
    """Echter Wetteranbieter (kein Mock): pro Segment ein HTTP-Abruf gegen den lokalen,
    verzoegernden Server, dann die Fixture-Reihe. Fehlerplan: Breitengrad -> verbleibende
    transiente Fehler (``httpx.ReadTimeout``, vom Scheduler als transient erkannt)."""

    name = "openmeteo"

    def __init__(self, url: str, verzoegerung: dict, fehler: dict | None = None):
        from providers.fixture import FixtureProvider
        import os
        self._url, self._verzoegerung = url, verzoegerung
        self._fehler = dict(fehler or {})
        self._fixture = FixtureProvider(os.environ["GZ_TEST_FIXTURE_DIR"])
        self._sperre = threading.Lock()
        self.aufrufe: dict[float, int] = {}

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True,
                       enrich_snow=True):
        schluessel = location.latitude
        with self._sperre:
            self.aufrufe[schluessel] = self.aufrufe.get(schluessel, 0) + 1
            offen = self._fehler.get(schluessel, 0)
            if offen > 0:
                self._fehler[schluessel] = offen - 1
        if offen > 0:
            raise httpx.ReadTimeout("timed out (simulierter transienter Ausfall)")
        antwort = httpx.get(f"{self._url}/seg?d={self._verzoegerung[schluessel]}", timeout=10)
        antwort.raise_for_status()
        return self._fixture.fetch_forecast(location, start, end, enrich_ensemble, enrich_snow)


@pytest.fixture
def segment_server():
    server = _VerzoegerungsServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _segmente(anzahl: int) -> list[TripSegment]:
    """Je Segment EIGENE Koordinaten (Segment-Cache/Single-Flight sollen die Zeitmessung nicht
    leer laufen lassen) und Zufallsanteil (Cache ueberlebt Testlaeufe, TTL 600 s)."""
    jitter = (uuid.uuid4().int % 900) / 100000.0
    tag = datetime.now(timezone.utc).date() + timedelta(days=1)
    return [_segment(tag, 6, 8, lat=47.10 + 0.05 * i + jitter, lon=11.30 + jitter, nr=i + 1)
            for i in range(anzahl)]


def _plan(segmente: list[TripSegment], delays: list[float]) -> dict:
    return {s.start_point.lat: d for s, d in zip(segmente, delays)}


def test_ac10_segmente_laufen_parallel_geordnet_und_ein_fehlschlag_wird_wiederholt(
    segment_server, monkeypatch,
):
    """AC-10: 6 Segmente, absteigende Antwortzeiten (spaete Segmente fertig zuerst) ->
    Ergebnis in Segmentreihenfolge; Gesamtzeit < 0,75 x serielle Summe; Segment 3 scheitert
    zweimal transient und liefert danach sein Ergebnis (3 Provider-Aufrufe), ohne die uebrigen
    zu blockieren."""
    monkeypatch.setattr(scheduler_mod, "FETCH_RETRY_BACKOFF_SECONDS", 0.2, raising=True)
    uid = _kennung("dz10")
    segmente = _segmente(6)
    delays = [0.4 - 0.05 * i for i in range(6)]
    fehler_lat = segmente[2].start_point.lat
    anbieter = _ServerAnbieter(f"http://127.0.0.1:{segment_server.server_address[1]}",
                               _plan(segmente, delays), {fehler_lat: 2})
    serielle_summe = sum(delays) + 0.2 * 1 + 0.2 * 2  # Abrufe + Backoff 1 + Backoff 2

    t0 = time.monotonic()
    ergebnis = TripReportSchedulerService(user_id=uid)._fetch_weather(segmente, provider=anbieter)
    gesamt = time.monotonic() - t0

    assert [d.segment.segment_id for d in ergebnis] == [1, 2, 3, 4, 5, 6], (
        "AC-10: Ergebnisreihenfolge muss die Segmentreihenfolge sein"
    )
    assert not any(d.has_error for d in ergebnis), (
        f"AC-10: kein Segment darf fehlerhaft sein: {[d.error_message for d in ergebnis]}"
    )
    assert anbieter.aufrufe[fehler_lat] == 3, (
        f"AC-10: das Fehler-Segment braucht genau 3 Anbieter-Aufrufe (2 Fehler + Erfolg), "
        f"gezaehlt {anbieter.aufrufe[fehler_lat]}"
    )
    assert segment_server.spitze >= 2, (
        f"AC-10: es lief nie mehr als ein Abruf gleichzeitig (Spitze {segment_server.spitze}) "
        f"-- die Segmentschleife ist seriell"
    )
    assert gesamt < 0.75 * serielle_summe, (
        f"AC-10: Gesamtzeit {gesamt:.2f} s ist nicht < 0,75 x serielle Summe "
        f"({serielle_summe:.2f} s)"
    )


def test_ac10_aufruf_aus_normalem_thread_laeuft_parallel(segment_server):
    """AC-10 Worker-Thread (a): ein normaler Thread -- so ruft ihn der API-Request-Thread -- darf
    NICHT still auf seriell zurueckfallen."""
    uid = _kennung("dz10t")
    segmente = _segmente(3)  # <= 3 Slots des Anbieters: eine Runde
    delays = [0.5] * 3
    anbieter = _ServerAnbieter(f"http://127.0.0.1:{segment_server.server_address[1]}",
                               _plan(segmente, delays))
    ablage: dict = {}

    def arbeit():
        t0 = time.monotonic()
        ablage["daten"] = TripReportSchedulerService(user_id=uid)._fetch_weather(
            segmente, provider=anbieter)
        ablage["dauer"] = time.monotonic() - t0

    thread = threading.Thread(target=arbeit)
    thread.start()
    thread.join(timeout=30)
    assert "daten" in ablage, "AC-10: Abruf aus dem Thread kam nicht zurueck (Deadlock?)"
    assert [d.segment.segment_id for d in ablage["daten"]] == [1, 2, 3]
    assert ablage["dauer"] < 0.75 * sum(delays), (
        f"AC-10: Aufruf aus normalem Thread dauerte {ablage['dauer']:.2f} s, serielle Summe "
        f"{sum(delays):.2f} s -- stilles Zurueckfallen auf seriell"
    )


def test_ac10_aufruf_aus_dem_parallel_pool_bleibt_korrekt_ohne_deadlock(segment_server):
    """AC-10 Worker-Thread (b), DOKUMENTIERTE ENTSCHEIDUNG: aus einem Worker des gemeinsamen
    ``parallel_fetch``-Pools laeuft ``fetch_ordered`` inline seriell (Baustein unveraendert).
    Akzeptiert -- verlangt werden hier nur Vollstaendigkeit, Reihenfolge und KEIN Deadlock.
    Legitim GRUEN schon im RED-Stand (Regressionsschutz); es wird bewusst NICHT verlangt, dass
    es langsam ist."""
    uid = _kennung("dz10p")
    segmente = _segmente(3)
    anbieter = _ServerAnbieter(f"http://127.0.0.1:{segment_server.server_address[1]}",
                               _plan(segmente, [0.1] * 3))
    service = TripReportSchedulerService(user_id=uid)

    ausgang = parallel_fetch.fetch_ordered(
        ["aussen"], lambda _x: service._fetch_weather(segmente, provider=anbieter),
        provider="aussen_test_pool", deadline_at=time.monotonic() + 30,
    )

    assert ausgang[0].skipped is None and ausgang[0].error is None, (
        f"AC-10: Aufruf aus dem Pool-Worker scheiterte: {ausgang[0]}"
    )
    assert [d.segment.segment_id for d in ausgang[0].value] == [1, 2, 3]


# ---------------------------------------------------------------------------
# AC-11: Cache-Kapazitaet 2048 -- Vorwaerm-Bestand wird nicht verdraengt, < 40 MB
# ---------------------------------------------------------------------------

def _echtes_fenster(lat: float, lon: float):
    fenster = dwd._decode_window(_raster(7.0), lat, lon)
    assert fenster is not None, "Vorbedingung: Rasterfenster dekodierbar"
    return fenster


def _kopie(fenster):
    return dataclasses.replace(fenster, array=fenster.array.copy())


def test_ac11_trip_bestand_ueberlebt_einen_zweiten_lauf_gleicher_groesse():
    """AC-11: ~415 Trip-Dateien, danach ~415 fremde (Alarm/Ortsvergleich) -> ALLE Trip-Eintraege
    sind noch im globalen Cache (bei 512 waeren die ersten verdraengt)."""
    lat, lon = KARNISCH.latitude, KARNISCH.longitude
    vorlage = _echtes_fenster(lat, lon)
    trip_urls = [f"http://trip.invalid/{i}" for i in range(415)]
    fremd_urls = [f"http://fremd.invalid/{i}" for i in range(415)]

    for url in trip_urls:
        dwd._RASTER_CACHE.put(url, _kopie(vorlage))
    for url in fremd_urls:
        dwd._RASTER_CACHE.put(url, _kopie(vorlage))

    fehlen = [u for u in trip_urls if dwd._RASTER_CACHE.find(u, lat, lon) is None]
    assert not fehlen, (
        f"AC-11: {len(fehlen)} von {len(trip_urls)} Trip-Eintraegen wurden verdraengt "
        f"(Cache-Obergrenze {dwd._RASTER_CACHE._max_urls} URLs reicht nicht fuer Trip + Alarm)"
    )


def test_ac11_gefuellter_cache_bleibt_unter_40_mb():
    """AC-11: bis ueber die Kapazitaet gefuellt (2 x Kapazitaet + 10 Eintraege) belegt der
    Cache < 40 MB Arrayspeicher (2048 x ~13,5 kB ~ 27,6 MB; 4096 waeren ~55 MB)."""
    lat, lon = KARNISCH.latitude, KARNISCH.longitude
    vorlage = _echtes_fenster(lat, lon)
    kapazitaet = dwd._RASTER_CACHE._max_urls

    for i in range(2 * kapazitaet + 10):
        dwd._RASTER_CACHE.put(f"http://fuell.invalid/{i}", _kopie(vorlage))

    bytes_gesamt = sum(w.array.nbytes
                       for fenster in dwd._RASTER_CACHE._data.values() for w in fenster)
    assert bytes_gesamt < 40 * 1024 * 1024, (
        f"AC-11: gefuellter Cache belegt {bytes_gesamt / 1e6:.1f} MB (>= 40 MB)"
    )
    assert len(dwd._RASTER_CACHE) >= 830, (
        f"AC-11: Cache haelt nur {len(dwd._RASTER_CACHE)} URLs (< 830 = 2 x 415)"
    )


# ---------------------------------------------------------------------------
# AC-13: Golden -- Berichte bit-identisch zum eingefrorenen Altstand
# ---------------------------------------------------------------------------

def test_ac13_berichte_sind_bit_identisch_zum_eingefrorenen_altstand(mitschrift, monkeypatch):
    """AC-13: E-Mail-HTML/Text, Telegram-Bubbles, SMS- und Premium-SMS-Kurzform eines
    4-Etappen-Trips (Nacht, Ausblick, Gewitter +1/+2 und Ensemble-Abschnitte enthalten) sind
    BIT-IDENTISCH zur Referenz, die VOR der Aenderung (seriell, ohne Vorwaermen) aus den
    aufgezeichneten Open-Meteo-Fixture-Rohdaten eingefroren wurde
    (tests/fixtures/befehl_antwortzeit/golden_berichte.json).

    LEGITIM GRUEN im RED-Stand: der Test friert den Altstand ein und muss nach /50 UNVERAENDERT
    gruen bleiben (Regressionswaechter fuer Inhaltsparitaet, Entscheidung 7).
    Geographie Reykjavik (keine Sommerzeit) haelt das Golden stabil ueber die Zeitumstellung;
    ``_normalisiere`` entfernt NUR Datum/Wochentag/Stempel. Deckt nur den Fixture-Inhalt ab,
    keine DWD-Rasterwerte. Die Gleichheit mit aktivem Vorwaermen (Innsbruck, DE/Alpen) sichert
    ``test_ac9_bericht_kommt_trotz_fehlgeschlagenem_vorwaermen_inhaltsgleich``."""
    assert GOLDEN.is_file(), f"Golden-Fixture fehlt: {GOLDEN}"
    referenz = json.loads(GOLDEN.read_text(encoding="utf-8"))
    referenz.pop("_hinweis", None)

    with _dwd_server(monkeypatch, verzoegerung_s=0.0):
        aktuell = _bericht_aufnehmen(mitschrift, "befehlzeit-golden", *REYKJAVIK)

    rest = _unnormalisiert_uebrig(json.dumps(aktuell, ensure_ascii=False))
    assert not rest, f"Normalisierung unvollstaendig, Kalenderreste: {rest}"
    assert set(aktuell) == set(referenz), (
        f"AC-13: bediente Kanaele weichen ab: {sorted(aktuell)} vs Referenz {sorted(referenz)}"
    )
    for schluessel in referenz:
        assert aktuell[schluessel] == referenz[schluessel], (
            f"AC-13: Ausgabe von {schluessel!r} weicht vom eingefrorenen Altstand ab"
        )
