"""TDD RED — Alarm-Protokoll: eine Kennung statt zwei Feldern.

Issue #1467 Scheibe S1, Epic #1458.
Spec: docs/specs/modules/rework_1467_s1_alarm_kennung.md (AC-1, AC-2, AC-3)

Der Bestand schreibt `trip_id` UND `preset_id` — immer ist eins leer. Diese
Tests verlangen die zusammengelegte Form `entity_id` + `entity_type` und
sichern zugleich, dass die 79 echten Alt-Einträge der Fixture beim Anhängen
Feld für Feld unangetastet bleiben.

Ausführung:
    uv run pytest tests/tdd/test_alert_log_entity_key.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Echte, aufgezeichnete Produktivdatei im Altformat (79 Einträge, vier Felder).
LEGACY_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "alert_log_legacy_default.json"


def _log_path(user_id: str) -> Path:
    from app.loader import get_data_dir

    user_dir = get_data_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "alert_log.json"


def _entries(user_id: str) -> list[dict]:
    return json.loads(_log_path(user_id).read_text())["entries"]


# --- AC-1: Tour-Alarm trägt Kennung + Typ, keine Altfelder mehr --------------

def test_trip_alert_writes_entity_id_and_type():
    """
    GIVEN: kein Protokoll vorhanden
    WHEN:  ein Tour-Alarm protokolliert wird
    THEN:  der Eintrag trägt `entity_id` = Tour-Kennung und `entity_type` = "trip";
           `trip_id` und `preset_id` kommen nicht mehr vor
    """
    from services import alert_log

    _log_path("entity-key-user")  # legt das Verzeichnis an

    alert_log.append_entry(
        "entity-key-user",
        entity_id="trip-123",
        entity_type="trip",
        changes_count=2,
        severity="MODERATE",
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"email"},
        sent_channels=["email"],
    )

    entry = _entries("entity-key-user")[-1]
    assert entry["entity_id"] == "trip-123"
    assert entry["entity_type"] == "trip"
    assert "trip_id" not in entry, "Altfeld trip_id darf nicht mehr geschrieben werden"
    assert "preset_id" not in entry, "Altfeld preset_id darf nicht mehr geschrieben werden"


# --- AC-2: Ortsvergleichs-Alarm trägt Typ "compare" -------------------------

def test_compare_alert_writes_compare_entity_type():
    """
    GIVEN: kein Protokoll vorhanden
    WHEN:  ein Ortsvergleichs-Alarm protokolliert wird
    THEN:  der Eintrag trägt `entity_id` = Preset-Kennung und `entity_type` = "compare"
    """
    from services import alert_log

    _log_path("entity-key-compare")

    alert_log.append_entry(
        "entity-key-compare",
        entity_id="preset-abc",
        entity_type="compare",
        changes_count=1,
        severity="HIGH",
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"email", "telegram"},
        sent_channels=["email", "telegram"],
    )

    entry = _entries("entity-key-compare")[-1]
    assert entry["entity_id"] == "preset-abc"
    assert entry["entity_type"] == "compare"
    assert "trip_id" not in entry
    assert "preset_id" not in entry


# --- AC-3: Bestand bleibt feldweise unverändert -----------------------------

def test_legacy_entries_survive_append_byte_for_field():
    """
    GIVEN: eine echte Bestands-Protokolldatei im Altformat (79 Einträge)
    WHEN:  ein neuer Eintrag im neuen Format angehängt wird
    THEN:  die 79 Alt-Einträge sind danach Element für Element identisch —
           keiner wird um `entity_id`/`entity_type` ergänzt oder umgeschrieben,
           und die Datei enthält genau einen Eintrag mehr
    """
    from services import alert_log

    path = _log_path("entity-key-legacy")
    original = json.loads(LEGACY_FIXTURE.read_text())
    path.write_text(json.dumps(original, indent=2))
    before = original["entries"]
    assert len(before) == 79, "Fixture unerwartet verändert"

    alert_log.append_entry(
        "entity-key-legacy",
        entity_id="trip-neu",
        entity_type="trip",
        changes_count=1,
        severity="LOW",
        reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels={"email"},
        sent_channels=["email"],
    )

    after = _entries("entity-key-legacy")
    assert len(after) == len(before) + 1, "genau ein Eintrag mehr erwartet"
    for i, (alt, neu) in enumerate(zip(before, after)):
        assert alt == neu, f"Alt-Eintrag {i} wurde verändert: {alt} -> {neu}"
    assert after[-1]["entity_type"] == "trip"


# --- Regressionsschutz: die Altsignatur darf es nicht mehr geben ------------

def test_old_signature_is_gone():
    """
    GIVEN: der Umbau ist erfolgt
    WHEN:  jemand `append_entry()` noch mit `trip_id=`/`preset_id=` aufruft
    THEN:  schlägt der Aufruf fehl, statt still einen Eintrag ohne Kennung zu
           erzeugen — sonst schreiben übersehene Aufrufstellen unbemerkt Müll
    """
    from services import alert_log

    _log_path("entity-key-oldsig")

    with pytest.raises(TypeError):
        alert_log.append_entry(
            "entity-key-oldsig",
            trip_id="trip-123",
            changes_count=1,
            severity="LOW",
            reason=alert_log.REASON_FORECAST_CHANGE,
            effective_channels={"email"},
            sent_channels=["email"],
        )
