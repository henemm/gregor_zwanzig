"""TDD RED — Feature #1260 (Scheibe S1): Persistenz des neuen Config-Feldes
``TripReportConfig.telegram_style`` ("rich" | "kurzform") über den ECHTEN
Loader/Store-Pfad (``save_trip`` / ``load_trip`` + RMW-Merge
``_deep_merge_preserve_unknown``).

Deckt AC-8 ab: Ein aktivierter Kurzstil-Schalter überlebt einen Teil-
Speichervorgang, der ein ANDERES Feld ändert und ``telegram_style`` NICHT im
Payload trägt.

KEINE Mocks: echte JSON-Datei unter ``tmp_path/users/<user_id>/`` (Pfad
path-agnostisch per rglob lokalisiert -- #1250 S7a hat den Trip-Speicherpfad
``trips/`` -> ``briefings/`` verschoben), echter Loader-Roundtrip, echte
RMW-Merge-Funktion aus ``app.loader``.

RED-Ursache (vor der Implementierung):
- ``TripReportConfig`` hat das Feld ``telegram_style`` noch nicht → das
  Konstruieren mit ``telegram_style="kurzform"`` wirft ``TypeError``.
- selbst mit Feld würde ``save_trip`` es nicht in die JSON schreiben und
  ``load_trip`` es nicht zurücklesen → der Roundtrip verlöre den Wert.
"""
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

from app.loader import (
    _deep_merge_preserve_unknown, load_compare_presets, load_trip, save_trip,
)
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services.scheduler_dispatch_service import save_compare_preset_status
from tests.helpers.compare_briefings import write_compare_briefings


def _make_trip(trip_id: str, telegram_style: str) -> Trip:
    """Minimaler, aber echt-persistierbarer Trip mit gesetztem telegram_style."""
    stage = Stage(
        id="S1", name="Etappe 1", date=date(2026, 9, 1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id=trip_id, name=f"Test1260 {trip_id}", stages=[stage],
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=False, send_sms=False, send_telegram=True,
            telegram_style=telegram_style,
        ),
    )


class TestAC8TripTelegramStyleSurvivesPartialUpdate:
    """
    GIVEN: Ein Trip mit report_config.telegram_style="kurzform" ist gespeichert
    WHEN:  Ein Teil-Speichervorgang nur die Sende-Uhrzeit (evening_time) ändert
           und ``telegram_style`` NICHT im Payload enthält (echter RMW-Merge)
    THEN:  Nach erneutem Laden ist ``telegram_style`` weiterhin "kurzform"
    """

    def test_telegram_style_kurzform_survives_partial_update(self, tmp_path: Path) -> None:
        user_id = "tdd-1260-rmw-a"
        trip_id = "trip-1260-a"

        # 1. Kurzstil-Trip persistieren (ECHTER save_trip-Pfad).
        #    RED: TripReportConfig(telegram_style=...) wirft hier TypeError,
        #    weil das Feld noch nicht existiert.
        trip = _make_trip(trip_id, telegram_style="kurzform")
        save_trip(trip, user_id=user_id, data_dir=tmp_path)

        # 1b. SAVE muss das Feld tatsächlich persistiert haben — path-agnostisch
        #     über den ECHTEN load_trip-Pfad geprüft (nicht über einen fest
        #     verdrahteten Ordner; #1250 S7a hat trips/ -> briefings/ verschoben).
        saved = load_trip(trip_id, data_dir=tmp_path, user_id=user_id)
        assert saved is not None and saved.report_config is not None
        assert saved.report_config.telegram_style == "kurzform", (
            "RED: save_trip schreibt telegram_style nicht in die persistierte "
            "JSON — der Report-Config-Block in _trip_to_dict muss das Feld "
            "emittieren (analog email_format)."
        )

        # 2. Persistierte JSON-Datei path-agnostisch lokalisieren (rglob), damit
        #    der Test robust gegen künftige Pfad-Cutover bleibt.
        matches = list((tmp_path / "users" / user_id).rglob(f"{trip_id}.json"))
        assert len(matches) == 1, f"erwarte genau eine persistierte Datei, fand {matches}"
        path = matches[0]
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["report_config"]["telegram_style"] == "kurzform"

        # 3. Teil-Speichervorgang: nur evening_time ändern, KEIN telegram_style
        #    im Payload — gemergt über die ECHTE RMW-Funktion, die save_trip nutzt.
        partial_payload = {"report_config": {"evening_time": "19:30:00"}}
        merged = _deep_merge_preserve_unknown(raw, partial_payload)
        path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

        # 4. Erneut laden (ECHTER load_trip-Pfad) — Feld muss erhalten sein.
        reloaded = load_trip(trip_id, data_dir=tmp_path, user_id=user_id)
        assert reloaded is not None
        assert reloaded.report_config is not None
        assert reloaded.report_config.telegram_style == "kurzform", (
            "RED: telegram_style ging beim Teil-Speichern verloren oder wird von "
            "load_trip nicht zurückgelesen (#102-Datenverlust-Regel). "
            "load_trip_from_dict muss telegram_style aus report_config parsen."
        )
        # Regression: das tatsächlich geänderte Feld ist übernommen.
        assert reloaded.report_config.evening_time == time(19, 30)

    def test_default_telegram_style_is_rich(self, tmp_path: Path) -> None:
        """Guard: ohne explizite Angabe ist der Default 'rich' (reiche Bubbles).

        RED: TripReportConfig() kennt das Attribut telegram_style noch nicht,
        der Zugriff wirft AttributeError.
        """
        cfg = TripReportConfig(trip_id="t-default")
        assert cfg.telegram_style == "rich", (
            "RED: neues Feld telegram_style fehlt oder hat nicht den Default 'rich'."
        )


class TestAC9CompareTelegramStyleSurvivesPartialUpdate:
    """
    GIVEN: Ein Compare-Preset mit display_config.telegram_style="kurzform" ist
           gespeichert (Feature #1260 S4).
    WHEN:  Ein Teil-Speichervorgang nur Status-Felder (letzter_versand /
           top_ort_letzter_versand) über den ECHTEN RMW-Store-Pfad
           (``save_compare_preset_status``) ändert und den Style-Key NICHT
           anfasst.
    THEN:  Nach erneutem Laden über ``load_compare_presets`` ist der Key
           weiterhin "kurzform" (BUG-DATALOSS-GR221 / #102).

    KEINE Mocks: echte compare_presets.json unter tmp_path, echter Loader-
    Roundtrip, echter RMW-Schreibpfad.
    """

    def _write_preset_file(self, tmp_path: Path, user_id: str) -> str:
        preset_id = "cmp-1260-a"
        user_dir = tmp_path / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        presets = [{
            "id": preset_id,
            "name": "Korsika-Vergleich",
            "user_id": user_id,
            "location_ids": ["loc-a", "loc-b"],
            "schedule": "daily",
            "empfaenger": ["a@example.com"],
            "display_config": {
                "telegram_style": "kurzform",
                "channels": ["temperature", "wind"],
            },
        }]
        # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
        write_compare_briefings(user_dir, presets)
        return preset_id

    def test_compare_telegram_style_survives_status_update(self, tmp_path: Path) -> None:
        user_id = "tdd-1260-cmp-rmw"
        preset_id = self._write_preset_file(tmp_path, user_id)

        # 1. Laden über den ECHTEN Compare-Loader — Key muss da sein.
        loaded = load_compare_presets(user_id=user_id, data_root=tmp_path)
        assert len(loaded) == 1
        assert loaded[0].display_config is not None
        assert loaded[0].display_config.get("telegram_style") == "kurzform", (
            "Setup/RED: display_config.telegram_style muss vom Compare-Loader "
            "durchgereicht werden."
        )

        # 2. Teil-Speichervorgang über den ECHTEN RMW-Store-Pfad: ändert nur
        #    Status-Felder, KEIN telegram_style im Update.
        save_compare_preset_status(user_id, preset_id, "Calenzana", data_root=str(tmp_path))

        # 3. Erneut laden — der Style-Key muss erhalten sein.
        reloaded = load_compare_presets(user_id=user_id, data_root=tmp_path)
        assert len(reloaded) == 1
        assert reloaded[0].display_config is not None
        assert reloaded[0].display_config.get("telegram_style") == "kurzform", (
            "RED: display_config.telegram_style ging beim Teil-Speichern verloren "
            "(#102-Datenverlust-Regel — RMW muss unbekannte Sub-Keys erhalten)."
        )
        # Regression: das tatsächlich geänderte Statusfeld ist übernommen.
        assert reloaded[0].raw.get("top_ort_letzter_versand") == "Calenzana"
