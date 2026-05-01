"""
TDD RED tests for #98: ActivityProfile-Harmonisierung.

Spec: docs/specs/modules/activity_profile.md

Drei Test-Gruppen, die ALLE vor PR 1 fehlschlagen müssen:

1. TestCanonicalActivityProfile  — neuer Enum in src/app/profile.py mit 4 Werten
2. TestBackwardCompatAliases     — PR 1 Aliase: alte Importe bleiben funktional
3. TestVerificationScript        — scripts/verify_activity_profile_migration.py

Alle Tests sind RED weil:
- src/app/profile.py existiert noch nicht
- scripts/verify_activity_profile_migration.py existiert noch nicht
- LocationActivityProfile.SUMMER_TREKKING (über Alias) existiert noch nicht
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# Test 1: Kanonischer Enum in src/app/profile.py
# =============================================================================

class TestCanonicalActivityProfile:
    """Kanonischer ActivityProfile-Enum mit genau 4 Werten in profile.py."""

    def test_module_importable(self):
        """
        GIVEN: src/app/profile.py
        WHEN: importing ActivityProfile from app.profile
        THEN: import succeeds (modul existiert)
        """
        from app.profile import ActivityProfile
        assert ActivityProfile is not None

    def test_has_all_four_values(self):
        """
        GIVEN: ActivityProfile in app.profile
        WHEN: accessing canonical values
        THEN: WINTERSPORT, WANDERN, SUMMER_TREKKING, ALLGEMEIN existieren
        """
        from app.profile import ActivityProfile

        assert ActivityProfile.WINTERSPORT.value == "wintersport"
        assert ActivityProfile.WANDERN.value == "wandern"
        assert ActivityProfile.SUMMER_TREKKING.value == "summer_trekking"
        assert ActivityProfile.ALLGEMEIN.value == "allgemein"

    def test_exactly_four_members(self):
        """
        GIVEN: ActivityProfile
        WHEN: counting members
        THEN: genau 4 Werte (kein CUSTOM, kein zusätzlicher Wert)
        """
        from app.profile import ActivityProfile

        assert len(list(ActivityProfile)) == 4

    def test_no_custom_value(self):
        """
        GIVEN: kanonischer Enum hat kein CUSTOM
        WHEN: ActivityProfile("custom") aufgerufen
        THEN: ValueError (Wert ist nicht mehr gültig)
        """
        from app.profile import ActivityProfile

        with pytest.raises(ValueError):
            ActivityProfile("custom")

    def test_string_mixin(self):
        """
        GIVEN: ActivityProfile ist (str, Enum) für JSON-Serialisierung
        WHEN: Wert in str-Vergleich verwendet
        THEN: gleichgesetzt mit String-Wert
        """
        from app.profile import ActivityProfile

        assert ActivityProfile.WINTERSPORT == "wintersport"
        assert ActivityProfile.WANDERN == "wandern"


# =============================================================================
# Test 2: Backward-Compat (PR 1)
# =============================================================================

class TestBackwardCompatAliases:
    """PR 1: alte Importe funktionieren weiter, sind aber Aliase auf den Canonical."""

    def test_trip_activity_profile_is_canonical(self):
        """
        GIVEN: src/app/trip.py
        WHEN: ActivityProfile aus app.trip importiert
        THEN: ist exakt dieselbe Klasse wie app.profile.ActivityProfile
        """
        from app.profile import ActivityProfile as Canonical
        from app.trip import ActivityProfile as TripAlias

        assert TripAlias is Canonical

    def test_location_activity_profile_alias(self):
        """
        GIVEN: src/app/user.py
        WHEN: LocationActivityProfile aus app.user importiert (PR 1 Alias)
        THEN: ist exakt dieselbe Klasse wie ActivityProfile
        """
        from app.profile import ActivityProfile as Canonical
        from app.user import LocationActivityProfile

        assert LocationActivityProfile is Canonical

    def test_existing_location_test_imports_still_work(self):
        """
        GIVEN: bestehende Tests importieren LocationActivityProfile.WINTERSPORT etc.
        WHEN: Werte werden via Alias zugegriffen
        THEN: liefern dieselben Enum-Member wie der Canonical
        """
        from app.profile import ActivityProfile
        from app.user import LocationActivityProfile

        assert LocationActivityProfile.WINTERSPORT is ActivityProfile.WINTERSPORT
        assert LocationActivityProfile.WANDERN is ActivityProfile.WANDERN
        assert LocationActivityProfile.ALLGEMEIN is ActivityProfile.ALLGEMEIN

    def test_existing_trip_test_imports_still_work(self):
        """
        GIVEN: bestehende Tests importieren ActivityProfile.SUMMER_TREKKING aus app.trip
        WHEN: Wert via Alias zugegriffen
        THEN: liefert denselben Enum-Member wie Canonical
        """
        from app.profile import ActivityProfile
        from app.trip import ActivityProfile as TripActivityProfile

        assert TripActivityProfile.SUMMER_TREKKING is ActivityProfile.SUMMER_TREKKING
        assert TripActivityProfile.WINTERSPORT is ActivityProfile.WINTERSPORT


# =============================================================================
# Test 3: Verifikations-Skript
# =============================================================================

class TestVerificationScript:
    """scripts/verify_activity_profile_migration.py existiert und prüft Persistenz."""

    SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_activity_profile_migration.py"

    def test_script_file_exists(self):
        """
        GIVEN: Spec §6.3 fordert scripts/verify_activity_profile_migration.py
        WHEN: Datei geprüft
        THEN: existiert
        """
        assert self.SCRIPT_PATH.exists(), (
            f"Verifikations-Skript fehlt: {self.SCRIPT_PATH}"
        )

    def test_script_runs_clean_on_real_data(self):
        """
        GIVEN: data/users/default/ enthält nur valide Profile-Werte (wintersport)
        WHEN: Verifikations-Skript läuft
        THEN: Exit 0, kein Fehler
        """
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Skript-Fehler:\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_script_rejects_unknown_value(self, tmp_path, monkeypatch):
        """
        GIVEN: Test-Verzeichnis mit Trip-JSON, das einen unbekannten Profile-Wert hat
        WHEN: Verifikations-Skript läuft (gegen Test-Verzeichnis)
        THEN: Exit != 0, Fehler mit Dateipfad in Output
        """
        users_dir = tmp_path / "data" / "users" / "default" / "trips"
        users_dir.mkdir(parents=True)
        bad_trip = users_dir / "bad-trip.json"
        bad_trip.write_text(json.dumps({
            "id": "bad",
            "name": "Bad Trip",
            "stages": [],
            "aggregation": {"profile": "klettern"},
        }))

        env_data_dir = tmp_path / "data" / "users"
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH), "--data-dir", str(env_data_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode != 0, (
            f"Erwartet Exit != 0 bei unbekanntem Wert. "
            f"Stattdessen: {result.returncode}\nstdout={result.stdout}"
        )
        combined = result.stdout + result.stderr
        assert "klettern" in combined or "bad-trip" in combined, (
            f"Erwartet Hinweis auf Wert/Pfad in Output:\n{combined}"
        )
