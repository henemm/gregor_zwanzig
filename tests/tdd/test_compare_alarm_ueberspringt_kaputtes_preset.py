"""Ortsvergleich-Alarmlauf ueberspringt ein strukturell kaputtes Preset
(Fix #2286, Adversary-Finding F004).

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (AC-5, toleranter Lader)

Seit Fix #2286 ueberspringt `load_compare_presets` im toleranten Default-Modus
auch ein LESBARES, aber strukturell kaputtes Vergleichs-Preset
(`compare_preset_from_dict` wirft) mit WARNING. Alle drei Ortsvergleich-Alarm-
pfade laden ueber `compare_preset_access.load_compare_alert_presets` (Default-
Modus) — die Nebenwirkung: ein einziges kaputtes Preset kippt den Alarmlauf
des Nutzers nicht mehr, die gueltigen Presets werden weiter geprueft.

Kein Mock-Theater: Orte/Presets liegen als echte Dateien im isolierten
Datenordner (autouse `tests/conftest.py::_isolate_data_root`), Wetter-/Radar-
Quellen sind die zaehlenden Seams aus
`test_compare_alert_paused_archived_silent.py`, Versand nur in `mail_sink`.
"""
from __future__ import annotations

import json
import logging
import uuid

from tests.tdd.test_compare_alert_paused_archived_silent import (
    _clean_user,
    _data_root_users,
    _preset,
    _run_deviation,
    _run_radar,
    _setup_deviation_case,
    _setup_radar_case,
)

KAPUTT_DATEI = "aaa-kaputtes-vergleichs-preset.json"


def _uid(prefix: str) -> str:
    return f"tdd-2286-f004-{prefix}-{uuid.uuid4().hex[:6]}"


def _write_struktur_kaputt(uid: str) -> None:
    """Lesbares JSON, `kind: vergleich`, aber `location_ids` ist keine Liste
    -> `compare_preset_from_dict` scheitert. Bewusst per Hand geschrieben
    (nicht `write_compare_briefings`: dessen Zonen-Aufloesung iteriert
    `location_ids` und wuerde schon im Testaufbau werfen). Der Name sortiert
    VOR dem gueltigen Preset."""
    bdir = _data_root_users() / uid / "briefings"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / KAPUTT_DATEI).write_text(json.dumps({
        "id": "aaa-kaputt", "name": "Kaputt", "kind": "vergleich",
        "location_ids": 42, "schedule": "daily", "created_at": "2026-07-01T00:00:00Z",
    }), encoding="utf-8")


def _warnings_naming_file(caplog) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if r.levelno == logging.WARNING and KAPUTT_DATEI in r.getMessage()
    ]


def test_premise_broken_preset_fails_structure_parser():
    """Praemisse: das Fixture scheitert wirklich am echten Struktur-Parser."""
    import pytest

    from app.loader import compare_preset_from_dict

    with pytest.raises(Exception):
        compare_preset_from_dict({
            "id": "aaa-kaputt", "name": "Kaputt", "kind": "vergleich",
            "location_ids": 42, "schedule": "daily", "created_at": "2026-07-01T00:00:00Z",
        })


def test_deviation_alarm_skips_broken_preset_and_checks_valid_one(caplog):
    """GIVEN ein Nutzer mit einem gueltigen Vergleichs-Preset (ausloesendes
    Δ=28) und einem strukturell kaputten Vergleichs-Preset /
    WHEN `CompareAlertService.check_all_compare_presets()` laeuft /
    THEN wirft der Lauf nicht, das gueltige Preset wird geprueft (Wetterabruf
    1, Zustellung 1) und eine WARNING nennt die kaputte Datei."""
    caplog.set_level(logging.WARNING)
    uid = _uid("dev")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(uid, _preset("cp-f004-dev", ["loc-1"], schedule="daily"))
        _write_struktur_kaputt(uid)

        sent, subjects = _run_deviation(uid, ws)

        assert ws.call_count == 1, (
            f"gueltiges Preset muss trotz kaputtem Nachbarn geprueft werden, fetch()={ws.call_count}"
        )
        assert sent == 1 and len(subjects) == 1, f"erwartet 1 Zustellung, kam {sent}/{subjects!r}"
        assert _warnings_naming_file(caplog), (
            "WARNING muss die kaputte Datei nennen, Logs: "
            f"{[r.getMessage() for r in caplog.records]!r}"
        )
    finally:
        _clean_user(uid)


def test_radar_alarm_skips_broken_preset_and_checks_valid_one(caplog):
    """Zweiter Alarmpfad (Nowcast), gleiche Zusicherung: gueltiges Preset mit
    ausloesendem Onset wird zugestellt, das kaputte nur mit WARNING
    uebersprungen."""
    caplog.set_level(logging.WARNING)
    uid = _uid("radar")
    _clean_user(uid)
    try:
        fs = _setup_radar_case(uid, _preset(
            "cp-f004-radar", ["loc-r"], schedule="daily", radar_alert_enabled=True,
        ))
        _write_struktur_kaputt(uid)

        sent, mail_calls = _run_radar(uid, fs)

        assert fs.call_count >= 1, "gueltiges Preset muss den Nowcast holen"
        assert sent == 1 and len(mail_calls) == 1, f"erwartet 1 Zustellung, kam {sent}"
        assert _warnings_naming_file(caplog), (
            "WARNING muss die kaputte Datei nennen, Logs: "
            f"{[r.getMessage() for r in caplog.records]!r}"
        )
    finally:
        _clean_user(uid)
