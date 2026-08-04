"""TDD RED -- Issue #1434 Scheibe S1: Zonen-Drift beim italienischen
Zivilschutz (DPC) sichtbar machen.

SPEC: docs/specs/modules/fix_1434_dpc_zonen_drift.md, AC-1 bis AC-4 (Scheibe S1).
Kontext: docs/context/fix-1434-dpc-zonen-sichtbarkeit.md

Zwei Drift-Richtungen (s. Spec):
- **Pfad B** (``dpc.py:227-229``, ``fetch()``): die eingecheckte Geometrie
  kennt eine Zone, die das tagesaktuelle Bulletin nicht mehr fuehrt --
  ``row is None`` -> heute STUMM ``[]``. Muss ``unavailable=True`` ausloesen
  (AC-1), darf aber den Normalfall "Zone im Bulletin, keine Warnung" nicht
  veraendern (AC-2, Gegenprobe).
- **Pfad A** (``dpc.py:114-119``, ``_records_by_zone()``): das Bulletin
  fuehrt einen Zonencode, den die Geometrie nicht kennt -- heute nur
  ``logger.warning``. Muss danach getrennt werden, ob die Zeile eine echte
  Warnstufe traegt (echter Verlust) oder nur NESSUNA (harmlos) (AC-3).

AC-4 ist eine Invarianten-Gegenprobe: Beobachtung darf den Abruf NIE
beeintraechtigen, auch wenn das Schreiben der Betriebsdaten fehlschlaegt.

Angenommene Schnittstelle (RED-Phase-Designentscheidung, da S1 noch nicht
implementiert ist -- zu bestaetigen/anzupassen in Phase 6):
- Pfad B nutzt den BEREITS VORHANDENEN oeffentlichen Haken
  ``warn_egress.mark_fetch_incomplete()`` (kein neuer Mechanismus, s. Spec
  Dependencies) an der ``row is None``-Stelle in ``dpc.fetch()``.
- Pfad A schreibt additiv eine EIGENE Ereigniszeile in dieselbe Datei
  ``warn_egress.WARN_CALLS_PATH`` (``data/diagnostics/warn_service_calls.jsonl``),
  OHNE das Feld ``ok`` (damit die bestehende Go-Aggregation
  ``entry.Ok == nil -> continue`` sie automatisch ueberspringt). Angenommene
  Feldnamen: ``service="dpc"``, ``zone_code=<Code>``, ``has_warning=<bool>``
  (Kennzeichen "traegt Warnung"). Der Test prueft nur, dass diese drei
  Informationen fuer BEIDE Faelle (mit/ohne Warnung) unterscheidbar in der
  Datei landen -- nicht die exakten Feldnamen als Vertrag.

KEINE Mocks (Projektkonvention): das DPC-Bulletin-Zip wird als ECHTES
dBase-III-Byte-Layout (fester Satzbreite, exakt passend zu
``dpc._parse_dbf``) im Testcode konstruiert und ueber einen echten lokalen
``http.server``-Socket ausgeliefert (Muster analog ``test_dpc_bulletin_
source.py``/``_BrokenJSONHandler``). Kein ``Mock()``/``patch()``/``MagicMock``.
Ein echter Zonen-Neuschnitt ist nicht herbeifuehrbar (Known Limitations der
Spec) -- die Fixtures sind deshalb bewusst konstruiert, nicht aufgezeichnet,
genau wie ``synthetic_unknown_zone_code.zip`` bei #1427 S2.

Koordinaten/Zonencodes: ``KHW_TREN_A``/``ABRU_A_QUIET`` sind aus
``test_dpc_bulletin_source.py`` uebernommen (dort bereits als "trifft GENAU
eine Zone" verifiziert) -- Gegenprobe hier per Einzeiler wiederholt:
``_zone_at(*KHW_TREN_A) == "Tren-A"``, ``_zone_at(*ABRU_A_QUIET) == "Abru-A"``.
``Zzzz-1``/``Zzzz-2`` sind ausserhalb jeder Geometrie liegende Phantasie-Codes,
per Einzeiler bestaetigt: NICHT in ``dpc._KNOWN_ZONE_CODES`` enthalten.
"""
from __future__ import annotations

import http.server
import io
import json
import struct
import threading
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pytest


# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "dpc"

# s. Docstring -- aus test_dpc_bulletin_source.py uebernommen, dort bereits
# als "trifft GENAU eine Zone" verifiziert.
KHW_TREN_A = (46.7248, 12.2254)  # Zone "Tren-A"
ABRU_A_QUIET = (42.638137, 13.724605)  # Zone "Abru-A"

# Zonencodes, die in der eingecheckten Geometrie NICHT existieren
# (verifiziert: nicht in dpc._KNOWN_ZONE_CODES).
UNKNOWN_ZONE_WITH_WARNING = "Zzzz-1"
UNKNOWN_ZONE_QUIET = "Zzzz-2"

# Feldbreiten fuer das synthetische DBF -- reichen fuer alle hier
# verwendeten Codes/Freitexte (laengster Text "Ordinaria / ALLERTA GIALLA").
_FIELDS: list[tuple[str, int]] = [
    ("Zona_all", 10),
    ("Nome_zona", 40),
    ("Temporali", 40),
    ("Idrogeo", 40),
    ("Idraulico", 40),
]

_NESSUNA = "NESSUNA ALLERTA"
_GIALLA = "Ordinaria / ALLERTA GIALLA"


# ---------------------------------------------------------------------------
# Synthetischer DBF-/Zip-Baukasten -- echtes Binaerformat, kein Mock.
# ---------------------------------------------------------------------------

def _dbf_field_descriptor(name: str, length: int) -> bytes:
    """Ein 32-Byte-Feld-Deskriptor, exakt passend zu ``dpc._parse_dbf``
    (Name 11 Byte, Laenge an Offset 16)."""
    name_bytes = name.encode("latin-1")[:10]
    name_bytes = name_bytes + b"\x00" * (11 - len(name_bytes))
    desc = bytearray(32)
    desc[0:11] = name_bytes
    desc[11] = ord("C")  # Feldtyp "Character" -- vom Parser nicht ausgewertet
    desc[16] = length
    return bytes(desc)


def _build_dbf(rows: list[dict], fields: list[tuple[str, int]] = _FIELDS) -> bytes:
    """Baut ein minimales dBase-III-Byte-Layout: 32-Byte-Header, 32-Byte-
    Feld-Deskriptoren, 0x0D-Terminator, satzweise feste Breite -- reiner
    ``struct``-Nachbau exakt spiegelbildlich zu ``dpc._parse_dbf`` (kein
    externes DBF-Werkzeug, kein Mock)."""
    header_len = 32 + len(fields) * 32 + 1
    record_len = 1 + sum(length for _, length in fields)

    header = bytearray(32)
    header[0] = 0x03
    struct.pack_into("<I", header, 4, len(rows))
    struct.pack_into("<H", header, 8, header_len)
    struct.pack_into("<H", header, 10, record_len)

    field_descs = b"".join(_dbf_field_descriptor(name, length) for name, length in fields)

    records = bytearray()
    for row in rows:
        records += b" "  # Loeschmarke: nicht geloescht
        for name, length in fields:
            value = str(row.get(name, "")).encode("latin-1")[:length]
            records += value.ljust(length, b" ")

    return bytes(header) + field_descs + b"\x0d" + bytes(records)


def _build_bulletin_zip(
    *,
    timestamp: str,
    today_rows: Optional[list[dict]] = None,
    tomorrow_rows: Optional[list[dict]] = None,
) -> bytes:
    """Verpackt die synthetischen DBFs als echtes Zip, Dateinamen exakt nach
    ``dpc._FILENAME_RE`` (``<YYYYMMDD>_<HHMM>_today.dbf``/``_tomorrow.dbf``)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if today_rows is not None:
            zf.writestr(f"{timestamp}_today.dbf", _build_dbf(today_rows))
        if tomorrow_rows is not None:
            zf.writestr(f"{timestamp}_tomorrow.dbf", _build_dbf(tomorrow_rows))
    return buf.getvalue()


class _ZipBytesHandler(http.server.BaseHTTPRequestHandler):
    """Echter lokaler HTTP-Server (kein Mock): liefert fuer JEDEN Pfad
    dieselben festen Bytes (Muster identisch zu
    ``test_dpc_bulletin_source.py::_ZipBytesHandler``)."""

    payload: bytes = b""

    def do_GET(self):  # noqa: N802 - stdlib-Signatur
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
        pass


@contextmanager
def _serve_bytes(payload: bytes):
    """Startet einen echten lokalen HTTP-Server, der ``payload`` fuer jeden
    GET liefert, und liefert die Basis-URL."""
    handler_cls = type("_Handler", (_ZipBytesHandler,), {"payload": payload})
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/latest_all.zip"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _reset_dpc_module_caches(dpc_module) -> None:
    """NUR das modul-eigene ``_cache``-Attribut leeren (s. ausfuehrliche
    Begruendung in ``test_dpc_bulletin_source.py`` -- ein generischer
    ``vars(modul)``-Sweep reisst Built-ins/fachliche Konstanten mit)."""
    cache = getattr(dpc_module, "_cache", None)
    if isinstance(cache, dict):
        cache.clear()


def _set_now(monkeypatch, dpc_module, when: datetime) -> None:
    """Injiziert eine feste 'jetzt'-Zeit ueber ``_NOW_FN`` (Konvention analog
    ``meteoalarm._WALL_CLOCK_FN``)."""
    monkeypatch.setattr(dpc_module, "_NOW_FN", lambda: when)


@contextmanager
def _isolated_registry_with_dpc_only():
    """Registriert AUSSCHLIESSLICH ``DpcSource`` in der Official-Alerts-
    Registry (Muster identisch zu ``test_ac6_...``/``test_ac7_...`` in
    ``test_dpc_bulletin_source.py``) -- verhindert, dass andere echte
    Quellen (MeteoAlarm etc.) waehrend des Tests echte Netzabrufe versuchen
    und ``covering``/``failed`` verfaelschen."""
    import services.official_alerts.base as oa_base
    from services.official_alerts.dpc import DpcSource

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(DpcSource())
        yield
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-1: Geometrie kennt eine Zone, die das Bulletin nicht mehr fuehrt
# ---------------------------------------------------------------------------

def test_ac1_zone_fehlt_im_bulletin_meldet_nicht_abrufbar_statt_stiller_leere(monkeypatch):
    """AC-1: GIVEN ein beobachteter Ort (KHW_TREN_A, Zone 'Tren-A') liegt in
    einem Warngebiet, das die eingecheckte Geometrie kennt, das
    tagesaktuelle Bulletin aber NICHT mehr fuehrt (Bulletin enthaelt nur
    'Abru-A', 'Tren-A' fehlt komplett -- Pfad B), WHEN die amtlichen
    Warnungen ueber den ECHTEN Ermittlungsweg
    ``get_official_alerts_with_status()`` ermittelt werden, THEN meldet das
    Ergebnis ``unavailable=True`` -- NICHT stillschweigend 'keine Warnung'.

    Geprueft wird der ``unavailable``-Status des echten Wegs (nicht
    ``DpcSource.fetch()`` isoliert, nicht ein Log-Text)."""
    from services.official_alerts import get_official_alerts_with_status
    import services.official_alerts.dpc as dpc_module

    # Bulletin fuehrt NUR Abru-A -- Tren-A (die Zone von KHW_TREN_A) fehlt
    # komplett, obwohl die Geometrie sie kennt.
    today_rows = [
        {"Zona_all": "Abru-A", "Nome_zona": "Bacini Tordino Vomano",
         "Temporali": _NESSUNA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
    ]
    payload = _build_bulletin_zip(timestamp="20260730_1511", today_rows=today_rows)

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url, _isolated_registry_with_dpc_only():
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts, unavailable = get_official_alerts_with_status(*KHW_TREN_A)

    assert unavailable is True, (
        "Tren-A ist in der Geometrie bekannt, fehlt aber im Bulletin -- muss "
        f"unavailable=True ausloesen, erhalten: unavailable={unavailable}, "
        f"alerts={alerts}"
    )


# ---------------------------------------------------------------------------
# AC-2: Gegenprobe -- Zone IM Bulletin, aber ohne Warnung (NESSUNA)
# ---------------------------------------------------------------------------

def test_ac2_zone_im_bulletin_ohne_warnung_bleibt_unauffaellig(monkeypatch):
    """AC-2 (Gegenprobe zu AC-1, gleicher Aufbau): GIVEN ein beobachteter Ort
    (ABRU_A_QUIET, Zone 'Abru-A') liegt in einem Warngebiet, das das
    Bulletin fuehrt und dort NESSUNA ALLERTA traegt, WHEN die amtlichen
    Warnungen ueber ``get_official_alerts_with_status()`` ermittelt werden,
    THEN bleibt das Ergebnis unauffaellig: leere Warnliste UND
    ``unavailable=False`` -- kein Dauerrauschen im Normalfall.

    Dieser Test ist eine Invarianten-Wache: darf nach der Implementierung
    von AC-1 NICHT kippen."""
    from services.official_alerts import get_official_alerts_with_status
    import services.official_alerts.dpc as dpc_module

    today_rows = [
        {"Zona_all": "Abru-A", "Nome_zona": "Bacini Tordino Vomano",
         "Temporali": _NESSUNA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
    ]
    payload = _build_bulletin_zip(timestamp="20260730_1511", today_rows=today_rows)

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url, _isolated_registry_with_dpc_only():
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts, unavailable = get_official_alerts_with_status(*ABRU_A_QUIET)

    assert alerts == [], (
        f"Abru-A ist NESSUNA -- erwartet keine Warnungen, erhalten: {alerts}"
    )
    assert unavailable is False, (
        "Abru-A ist im Bulletin gefuehrt (nur ohne Warnung) -- darf KEIN "
        f"'nicht abrufbar' ausloesen, erhalten: unavailable={unavailable}"
    )


# ---------------------------------------------------------------------------
# AC-3: Bulletin fuehrt zwei der Geometrie unbekannte Zonencodes
# ---------------------------------------------------------------------------

def test_ac3_unbekannter_zonencode_mit_warnung_unterscheidbar_von_ohne_warnung(monkeypatch, tmp_path):
    """AC-3: GIVEN das Bulletin fuehrt ZWEI Zonencodes, die die Geometrie
    nicht kennt -- 'Zzzz-1' mit echter Warnstufe (Temporali GIALLA, echter
    Verlust) und 'Zzzz-2' mit NESSUNA (harmlos) -- WHEN das Bulletin
    verarbeitet wird (ausgeloest durch einen Abruf fuer einen beliebigen,
    gueltig zugeordneten Ort), THEN ist der Fall MIT Warnung in den
    Betriebsdaten (``warn_egress.WARN_CALLS_PATH``) als tatsaechlicher
    Verlust erkennbar und vom Fall OHNE Warnung unterscheidbar.

    Geprueft wird die GESCHRIEBENE Journal-Zeile, nicht der Logger."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module
    from services.official_alerts import warn_egress

    journal_path = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", journal_path)

    today_rows = [
        {"Zona_all": "Abru-A", "Nome_zona": "Bacini Tordino Vomano",
         "Temporali": _NESSUNA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
        {"Zona_all": UNKNOWN_ZONE_WITH_WARNING, "Nome_zona": "Unbekannt mit Warnung",
         "Temporali": _GIALLA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
        {"Zona_all": UNKNOWN_ZONE_QUIET, "Nome_zona": "Unbekannt ohne Warnung",
         "Temporali": _NESSUNA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
    ]
    payload = _build_bulletin_zip(timestamp="20260730_1511", today_rows=today_rows)

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        DpcSource().fetch(*ABRU_A_QUIET)  # loest die Bulletin-Verarbeitung aus

    lines = [json.loads(line) for line in journal_path.read_text().splitlines() if line.strip()] \
        if journal_path.exists() else []

    # Additive Ereigniszeilen tragen bewusst KEIN "ok"-Feld (s. Docstring),
    # damit die bestehende Go-Aggregation sie ueberspringt -- das grenzt sie
    # von den regulaeren cached_fetch-Egress-Zeilen ab.
    drift_entries = {
        entry.get("zone_code"): entry for entry in lines
        if entry.get("service") == "dpc" and "ok" not in entry
        and entry.get("zone_code") in (UNKNOWN_ZONE_WITH_WARNING, UNKNOWN_ZONE_QUIET)
    }

    assert set(drift_entries) == {UNKNOWN_ZONE_WITH_WARNING, UNKNOWN_ZONE_QUIET}, (
        "Beide unbekannten Zonencodes muessen als eigene Ereigniszeile im "
        f"Diagnose-Journal ({journal_path}) erscheinen, gefunden: "
        f"{sorted(drift_entries)}. Alle Zeilen: {lines}"
    )
    assert drift_entries[UNKNOWN_ZONE_WITH_WARNING].get("has_warning") is True, (
        f"{UNKNOWN_ZONE_WITH_WARNING} traegt eine echte Warnstufe (GIALLA) -- "
        f"muss als tatsaechlicher Verlust markiert sein, erhalten: "
        f"{drift_entries[UNKNOWN_ZONE_WITH_WARNING]}"
    )
    assert drift_entries[UNKNOWN_ZONE_QUIET].get("has_warning") is False, (
        f"{UNKNOWN_ZONE_QUIET} traegt NESSUNA -- darf NICHT als Verlust "
        f"markiert sein, erhalten: {drift_entries[UNKNOWN_ZONE_QUIET]}"
    )


# ---------------------------------------------------------------------------
# AC-4: Schreiben der Betriebsdaten schlaegt fehl -- Abruf bleibt unberuehrt
# ---------------------------------------------------------------------------

def test_ac4_journal_schreibfehler_beeintraechtigt_abruf_nicht(monkeypatch, tmp_path):
    """AC-4: GIVEN das Schreiben der Betriebsdaten schlaegt fehl (Ziel-
    'Verzeichnis' ist tatsaechlich eine Datei, ``mkdir`` schlaegt fehl),
    WHEN ein Ort mit GUELTIGER Zuordnung UND echter Warnung abgefragt wird
    (KHW_TREN_A, Zone 'Tren-A', Temporali GIALLA), THEN liefert die Quelle
    ihre amtlichen Warnungen unveraendert vollstaendig -- die Beobachtung
    darf den Abruf unter keinen Umstaenden beeintraechtigen.

    Invarianten-Wache: ``log_warn_service_call()`` faengt bereits heute
    jeden Schreibfehler in einem breiten ``except Exception: pass`` ab
    (``warn_egress.py``) -- dieser Test darf schon VOR der S1-Implementierung
    gruen sein."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module
    from services.official_alerts import warn_egress

    # Zielverzeichnis ist eine DATEI -- path.parent.mkdir(parents=True,
    # exist_ok=True) schlaegt darauf fehl (kein beschreibbares Verzeichnis).
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("blockiert das Diagnose-Verzeichnis")
    unwritable_journal = blocking_file / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", unwritable_journal)

    today_rows = [
        {"Zona_all": "Tren-A", "Nome_zona": "Alto Adige",
         "Temporali": _GIALLA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
    ]
    payload = _build_bulletin_zip(timestamp="20260730_1511", today_rows=today_rows)

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts = DpcSource().fetch(*KHW_TREN_A)

    thunder = [a for a in alerts if a.hazard == "thunderstorm"]
    assert len(thunder) == 1 and thunder[0].level == 2, (
        "Tren-A ist GIALLA bei Temporali -- der Abruf muss trotz "
        f"fehlgeschlagenem Journal-Schreiben vollstaendig bleiben, erhalten: "
        f"{alerts}"
    )


# ---------------------------------------------------------------------------
# AC-4b: Praezisierung von AC-4 -- Journal-Schreibfehler UND Drift-Fall
# gleichzeitig, BEIDE neuen Schreibwege laufen im selben Lauf ins Leere
# ---------------------------------------------------------------------------

def test_ac4b_journal_schreibfehler_im_driftfall_bricht_nichts_ab(monkeypatch, tmp_path):
    """AC-4b (Praezisierung von AC-4): GIVEN das Schreiben der Betriebsdaten
    schlaegt fehl (Ziel-'Verzeichnis' ist tatsaechlich eine Datei, ``mkdir``
    schlaegt fehl) UND GLEICHZEITIG liegt ein Drift-Fall vor -- Pfad B
    (Tren-A, die Zone von KHW_TREN_A, fehlt komplett im Bulletin) UND Pfad A
    (das Bulletin fuehrt zusaetzlich den der Geometrie unbekannten Zonencode
    Zzzz-1) treten im SELBEN Abruf auf --, WHEN die amtlichen Warnungen ueber
    den echten Ermittlungsweg ``get_official_alerts_with_status()`` ermittelt
    werden, THEN bricht der Abruf nicht ab und liefert fuer KHW_TREN_A
    weiterhin korrekt ``unavailable=True``.

    Der urspruengliche AC-4-Test durchlaeuft ausschliesslich den BESTEHENDEN
    Schreibweg (``log_warn_service_call()``, der bei jedem echten HTTP-Abruf
    innerhalb von ``cached_fetch()`` laeuft) -- nicht den mit S1 NEU gebauten
    ``warn_egress.log_zone_drift()``. Dieser Aufbau zwingt BEIDE
    ``log_zone_drift()``-Aufrufe (Pfad A in ``_records_by_zone()`` UND Pfad B
    in ``DpcSource.fetch()``) auf denselben unbeschreibbaren Pfad -- gerade
    der Drift-Fall, in dem die Beobachtung laeuft, darf die Lage nicht
    verschlimmern.

    Adversary-Befund F001 (bestaetigt per Mutationstest): ``unavailable is
    True`` fuer Tren-A ist unter ZWEI Erklaerungen wahr -- (1) SOLL:
    ``log_zone_drift()`` schluckt den Schreibfehler lokal; (2) BRUCH: der
    Schreibfehler propagiert durch ``_records_by_zone()`` ->
    ``_parse_bulletin_zip()`` und wird stattdessen von ``cached_fetch()``s
    EIGENEM Parse-``except`` aufgefangen -- dann gilt das GESAMTE Bulletin
    als Fehlschlag und JEDE italienische Zone waere "nicht abrufbar", nicht
    nur die driftende. Deshalb zusaetzlich eine Kontroll-Abfrage einer
    NICHT-driftenden Zone (``ABRU_A_QUIET``/'Abru-A', regulaer im Bulletin
    mit NESSUNA ALLERTA) IM SELBEN Testlauf, OHNE den Bulletin-Cache
    dazwischen zu leeren -- nur Fall (1) laesst Abru-A unauffaellig, Fall
    (2) faerbt sie ueber den gemeinsamen Cache-Fehlschlag mit ein."""
    from services.official_alerts import get_official_alerts_with_status
    import services.official_alerts.dpc as dpc_module
    from services.official_alerts import warn_egress

    # Zielverzeichnis ist eine DATEI -- identische Technik wie im
    # bestehenden AC-4-Test: path.parent.mkdir(parents=True, exist_ok=True)
    # schlaegt darauf fehl (kein beschreibbares Verzeichnis).
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("blockiert das Diagnose-Verzeichnis")
    unwritable_journal = blocking_file / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", unwritable_journal)

    # Bulletin fuehrt Abru-A (ruhig, NICHT-driftende Kontroll-Zone) und den
    # unbekannten Zonencode Zzzz-1 (Pfad A, GIALLA -- has_warning=True) --
    # Tren-A (die Zone von KHW_TREN_A) fehlt komplett (Pfad B).
    today_rows = [
        {"Zona_all": "Abru-A", "Nome_zona": "Bacini Tordino Vomano",
         "Temporali": _NESSUNA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
        {"Zona_all": UNKNOWN_ZONE_WITH_WARNING, "Nome_zona": "Unbekannt mit Warnung",
         "Temporali": _GIALLA, "Idrogeo": _NESSUNA, "Idraulico": _NESSUNA},
    ]
    payload = _build_bulletin_zip(timestamp="20260730_1511", today_rows=today_rows)

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url, _isolated_registry_with_dpc_only():
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        # Beide Abfragen teilen bewusst DENSELBEN Bulletin-Cache-Zustand --
        # kein erneutes _reset_dpc_module_caches() dazwischen, sonst wuerde
        # die Kontroll-Abfrage einen frischen (und damit erfolgreichen)
        # Cache-Eintrag sehen und den Adversary-Fund nicht mehr aufdecken.
        alerts, unavailable = get_official_alerts_with_status(*KHW_TREN_A)
        alerts_quiet, unavailable_quiet = get_official_alerts_with_status(*ABRU_A_QUIET)

    assert unavailable is True, (
        "Tren-A fehlt im Bulletin (Pfad B) -- trotz GLEICHZEITIGEM "
        "Journal-Schreibfehler UND Pfad-A-Drift (Zzzz-1 im selben Bulletin) "
        f"muss der Abruf durchlaufen und unavailable=True liefern, erhalten: "
        f"unavailable={unavailable}, alerts={alerts}"
    )
    assert unavailable_quiet is False, (
        "Abru-A ist regulaer im Bulletin gefuehrt (NESSUNA ALLERTA, keine "
        "Drift) -- muss trotz des Schreibfehlers und der Tren-A-Drift im "
        "selben Cache-Zustand unauffaellig bleiben (unavailable=False). Ein "
        f"unavailable=True hier zeigt, dass der Schreibfehler NICHT lokal "
        "geschluckt wurde, sondern das gesamte Bulletin als Fehlschlag "
        f"gecacht hat (Adversary-Befund F001), erhalten: "
        f"unavailable_quiet={unavailable_quiet}, alerts_quiet={alerts_quiet}"
    )
