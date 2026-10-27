"""
TDD Tests für Issue #393 — Cockpit-Kacheln: Alarm-Historie.

Testet die Schreibfunktion des Alarm-Protokolls. Issue #1459 hat sie aus
`TripAlertService._append_alert_log()` in das geteilte Modul
`services.alert_log.append_entry()` gezogen (der Ortsvergleich schreibt jetzt
in dieselbe Datei) — der geprüfte Vertrag (Datei anlegen, Read-Modify-Write,
kein Purge, die vier Altfelder) ist unverändert.

Spec: docs/specs/modules/issue_393_cockpit_kacheln.md (AC-2, AC-9)
Test-Manifest: docs/specs/tests/issue_393_cockpit_kacheln_tests.md

Ausführung:
    cd /home/hem/gregor_zwanzig && uv run pytest tests/tdd/test_alert_log.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone



def _append(trip_id: str, changes_count: int, severity: str, user_id: str = "test-user"):
    """Issue #1459: derselbe Schreibvorgang wie früher `_append_alert_log()`.

    Ein erfolgreich zugestellter Kanal ⇒ der Eintrag landet in `entries`,
    genau wie im bisherigen Verhalten.
    """
    from services import alert_log

    alert_log.append_entry(
        user_id, entity_id=trip_id, entity_type="trip",
        changes_count=changes_count, severity=severity,
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"email"}, sent_channels=["email"],
    )


# --- AC-2: _append_alert_log schreibt Eintrag in alert_log.json ---

def test_append_alert_log_creates_file_with_entry():
    """
    GIVEN: Kein alert_log.json existiert
    WHEN: append_entry(entity_id="trip-123", entity_type="trip", changes_count=2, …)
    THEN: alert_log.json wird erstellt mit entity_id, sent_at, changes_count, severity

    Issue #1133-Fixture-Kollision: append_entry() schreibt ueber
    get_data_dir(), das von der autouse-Isolationsfixture auf einen
    eigenen isolierten Root umgebogen wird -- der Test muss denselben
    Pfad benutzen statt einen eigenen tmp_path-Baum zu bauen.
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    _append("trip-123", 2, "MODERATE")

    log_file = user_dir / "alert_log.json"
    assert log_file.exists(), "alert_log.json wurde nicht erstellt"

    data = json.loads(log_file.read_text())
    assert "entries" in data
    assert len(data["entries"]) == 1

    entry = data["entries"][0]
    assert entry["entity_id"] == "trip-123"
    assert entry["changes_count"] == 2
    assert entry["severity"] == "MODERATE"
    assert "sent_at" in entry

    parsed = datetime.fromisoformat(entry["sent_at"])
    assert parsed.tzinfo is not None, "sent_at muss timezone-aware sein"


def test_append_alert_log_appends_to_existing():
    """
    GIVEN: alert_log.json existiert mit einem Eintrag
    WHEN: _append_alert_log ein zweites Mal aufgerufen
    THEN: Neuer Eintrag wird angehängt, alter Eintrag bleibt erhalten
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "sent_at": now.isoformat(),
                "changes_count": 1,
                "severity": "LOW",
            }
        ]
    }
    (user_dir / "alert_log.json").write_text(json.dumps(existing))

    _append("trip-abc", 3, "HIGH")

    data = json.loads((user_dir / "alert_log.json").read_text())
    assert len(data["entries"]) == 2
    assert data["entries"][0]["severity"] == "LOW"
    assert data["entries"][1]["severity"] == "HIGH"
    assert data["entries"][1]["changes_count"] == 3


def test_append_alert_log_purges_entries_older_than_48h():
    """
    GIVEN: alert_log.json enthält Einträge, darunter einen älter als 48h
    WHEN: _append_alert_log aufgerufen
    THEN: Alle Einträge bleiben erhalten (kein Purge seit #396)
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=49)).isoformat()
    fresh_ts = (now - timedelta(hours=1)).isoformat()

    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "sent_at": old_ts,
                "changes_count": 1,
                "severity": "LOW",
            },
            {
                "trip_id": "trip-abc",
                "sent_at": fresh_ts,
                "changes_count": 2,
                "severity": "MODERATE",
            },
        ]
    }
    (user_dir / "alert_log.json").write_text(json.dumps(existing))

    _append("trip-abc", 3, "HIGH")

    data = json.loads((user_dir / "alert_log.json").read_text())
    # Kein Purge mehr seit #396 — alle Einträge bleiben erhalten
    assert len(data["entries"]) == 3
    severities = [e["severity"] for e in data["entries"]]
    assert "LOW" in severities    # alter Eintrag bleibt
    assert "MODERATE" in severities
    assert "HIGH" in severities


def test_append_alert_log_retains_fresh_entries():
    """
    GIVEN: alert_log.json enthält ausschließlich frische Einträge (< 48h)
    WHEN: _append_alert_log aufgerufen
    THEN: Alle frischen Einträge bleiben erhalten
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "sent_at": (now - timedelta(hours=12)).isoformat(),
                "changes_count": 1,
                "severity": "LOW",
            },
            {
                "trip_id": "trip-abc",
                "sent_at": (now - timedelta(hours=6)).isoformat(),
                "changes_count": 2,
                "severity": "MODERATE",
            },
        ]
    }
    (user_dir / "alert_log.json").write_text(json.dumps(existing))

    _append("trip-abc", 3, "HIGH")

    data = json.loads((user_dir / "alert_log.json").read_text())
    assert len(data["entries"]) == 3, "Alle frischen Einträge + neuer Eintrag sollen vorhanden sein"


# --- AC-B13 (Issue #2018): Nachtrags-Markierung im Protokoll, rein additiv ---

# Das Schema eines zugestellten Eintrags im Bestand, also VOR dieser Scheibe
# (`alert_log.py::append_entry`). Die optionalen Herkunfts-Felder
# (`capture_id`/`capture_ids`) sind bewusst NICHT dabei — sie entstehen nur
# bei gesetztem Argument, nach demselben Muster wie die Nachtrags-Felder.
BESTANDS_SCHEMA = {
    "entity_id", "entity_type", "sent_at", "changes_count", "severity",
    "metrics", "hazards", "reason", "channels_sent", "channels_not_sent",
}


def _entries(user_id: str) -> list:
    from app.loader import get_data_dir

    return json.loads(
        (get_data_dir(user_id) / "alert_log.json").read_text()
    )["entries"]


def _append_nowcast(user_id: str, entity_id: str, **extra):
    """Ein zugestellter Nowcast-Alarm — derselbe Aufruf wie am Trip-Pfad;
    `extra` trägt die (heute noch nicht existierenden) Nachtrags-Parameter."""
    from services import alert_log

    alert_log.append_entry(
        user_id, entity_id=entity_id, entity_type="trip",
        changes_count=1, severity="HIGH",
        reason=alert_log.REASON_NOWCAST,
        effective_channels={"email"}, sent_channels=["email"],
        **extra,
    )


def test_nachtrag_schreibt_die_markierung_in_den_protokolleintrag():
    """
    GIVEN: Eine per Nachtrag zugestellte Nowcast-Meldung, die sich auf eine
           bereits gemeldete amtliche Warnung von 14:05 UTC bezieht
    WHEN:  `append_entry(..., is_addendum=True, addendum_reported_at=…)`
    THEN:  Der Protokolleintrag trägt die Nachtrags-Markierung UND den
           referenzierten Meldezeitpunkt — rein additiv zum Bestandsschema,
           kein Bestandsfeld fällt weg.

    AC-B13 (Issue #2018). RED heute: `append_entry` kennt die Parameter nicht.
    """
    from app.loader import get_data_dir

    uid = "test-user-b13-nachtrag"
    get_data_dir(uid).mkdir(parents=True, exist_ok=True)
    bezug = datetime(2026, 8, 21, 14, 5, tzinfo=timezone.utc).isoformat()

    _append_nowcast(uid, "trip-b13", is_addendum=True, addendum_reported_at=bezug)

    entry = _entries(uid)[-1]
    assert entry.get("is_addendum") is True, (
        f"Nachtrags-Markierung fehlt im Protokolleintrag: {entry!r}"
    )
    assert entry.get("addendum_reported_at") == bezug, (
        f"Der referenzierte Meldezeitpunkt fehlt/weicht ab: {entry!r}"
    )
    assert BESTANDS_SCHEMA <= set(entry), (
        f"Bestandsfelder dürfen nicht wegfallen, fehlend: "
        f"{sorted(BESTANDS_SCHEMA - set(entry))!r}"
    )
    assert set(entry) - BESTANDS_SCHEMA == {"is_addendum", "addendum_reported_at"}, (
        f"Der Nachtrag darf GENAU die zwei additiven Felder ergänzen, "
        f"gefunden: {sorted(set(entry) - BESTANDS_SCHEMA)!r}"
    )


def test_normalfall_bleibt_schema_identisch_zum_bestand():
    """
    GIVEN: Ein gewöhnlicher Alarm ohne Nachtrag
    WHEN:  `append_entry(...)` ohne Nachtrags-Argumente
    THEN:  Die JSON-Struktur des Eintrags ist schema-identisch zum Bestand —
           kein `is_addendum`, kein `addendum_reported_at`, überhaupt kein
           neuer Schlüssel.

    AC-B13 (Issue #2018), Bestandsinvariante. Heute grün; fällt, sobald
    jemand die Nachtrags-Felder bedingungslos schreibt.
    """
    from app.loader import get_data_dir

    uid = "test-user-b13-normal"
    get_data_dir(uid).mkdir(parents=True, exist_ok=True)

    _append_nowcast(uid, "trip-b13-normal")

    entry = _entries(uid)[-1]
    assert set(entry) == BESTANDS_SCHEMA, (
        f"Der Normalfall muss schema-identisch zum Bestand bleiben. "
        f"Zuviel: {sorted(set(entry) - BESTANDS_SCHEMA)!r}, "
        f"fehlend: {sorted(BESTANDS_SCHEMA - set(entry))!r}"
    )
    assert not [k for k in entry if "addendum" in k], (
        f"Kein Nachtrags-Feld im Normalfall erlaubt: {entry!r}"
    )
