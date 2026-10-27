"""TDD RED — Issue #2286 AC-5: eine kaputte Datei legt nicht mehr alle Vergleiche still.

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (Implementierungsdetail 3, AC-5)

Trips und Vergleiche liegen im selben Ordner `briefings/`. Heute laedt der
Compare-Dispatch (`_load_presets_for_dispatch`) mit `strict=True`; EINE
unlesbare Datei -- auch ein Trip -- laesst ihn `None` liefern, der Lauf endet
mit `(0, 0)` und Go sieht "ok", obwohl kein einziger Vergleich rausging.

Geprueft ueber den ECHTEN Cron-Einstieg `run_compare_presets_daily` (nicht
ueber einen erfundenen Lader-Parameter): Nutzer A hat drei gueltige, faellige
Vergleiche und eine unlesbare JSON-Datei, die alphabetisch MITTEN zwischen
ihnen liegt (eine "bis zum ersten Fehler"-Variante faellt so auf). Nutzer B
hat keine kaputte Datei und darf in keiner Weise betroffen sein.

Naehte wie `test_compare_dispatch_failed_tally.py` (echte Engine-Subklasse,
smtplib-Boundary-Sink, Snapshot-Neutralisierung) -- kein Mock-Theater.
"""
from __future__ import annotations

import logging
import uuid

import pytest

from tests.tdd.test_compare_dispatch_failed_tally import (
    _install_engine_and_snapshot_seams,
    _install_smtp_sink,
    _preset,
    _set_smtp_env,
    _write_location,
    _write_presets,
)

#: Unlesbare Datei, einmal Trip-artig, einmal Vergleich-artig (AC-5: "egal ob
#: Trip oder Vergleich"). Abgeschnitten -> json.loads scheitert.
KAPUTT_VARIANTEN = {
    "trip-artig": '{"id": "cp-b-kaputt", "kind": "route", "name": "Kaputter Trip", "stages": [',
    "vergleich-artig": '{"id": "cp-b-kaputt", "kind": "vergleich", "name": "Kaputt", "location_ids": [',
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app import loader as app_loader
    import services.dispatch_orchestrator as orch_mod

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)
    _install_engine_and_snapshot_seams(monkeypatch)
    _set_smtp_env(monkeypatch)
    smtp_sent = _install_smtp_sink(monkeypatch)
    suffix = uuid.uuid4().hex[:8]
    # `tdd-`-Praefix: Settings leitet Test-Nutzer auf den Stalwart-Test-Host.
    return data_root, smtp_sent, f"tdd-2286-a-{suffix}", f"tdd-2286-b-{suffix}"


def _setup_user(data_root, user_id: str, preset_ids: list[str]) -> None:
    _write_location(data_root, user_id, "loc-ibk", "Innsbruck")
    _write_presets(data_root, user_id, [_preset(pid, ["loc-ibk"]) for pid in preset_ids])


@pytest.mark.parametrize("variante", sorted(KAPUTT_VARIANTEN))
def test_corrupt_file_skipped_three_valid_presets_sent(env, caplog, variante):
    """Given Nutzer A mit drei gueltigen faelligen Vergleichen + einer
    unlesbaren JSON-Datei (Variante: Trip- oder Vergleich-artig) / When der
    Cron-Lauf fuer A laeuft / Then werden alle drei versendet, `failed == 0`
    (das Ueberspringen zaehlt NICHT als Fehlschlag) und ein WARNING nennt den
    Dateinamen der kaputten Datei.

    RED: heute `(0, 0)`, keine einzige Mail."""
    from services.scheduler_dispatch_service import run_compare_presets_daily

    data_root, smtp_sent, user_a, _ = env
    _setup_user(data_root, user_a, ["cp-a-ok", "cp-c-ok", "cp-d-ok"])
    kaputt = data_root / "users" / user_a / "briefings" / "cp-b-kaputt.json"
    kaputt.write_text(KAPUTT_VARIANTEN[variante], encoding="utf-8")

    caplog.set_level(logging.WARNING)
    result = run_compare_presets_daily(user_id=user_a, data_root=str(data_root), hour=6)

    assert len(smtp_sent) == 3, (
        f"AC-5 ({variante}): alle drei gueltigen Vergleiche muessen trotz "
        f"kaputter Datei versendet werden, waren {len(smtp_sent)}"
    )
    assert result == (3, 0), (
        f"AC-5 ({variante}): erwartet (sent=3, failed=0) -- die kaputte Datei "
        f"zaehlt nicht als failed, kam {result!r}"
    )
    assert any(
        r.levelno == logging.WARNING and "cp-b-kaputt.json" in r.getMessage()
        for r in caplog.records
    ), f"AC-5 ({variante}): Ueberspringen muss als WARNING mit Dateinamen geloggt werden"


def test_second_user_without_corrupt_file_unaffected(env):
    """AC-5 (Mandantentrennung, zwei Nutzer): Nutzer A hat eine kaputte Datei,
    Nutzer B nicht. Gemessen wird je Nutzer der Mail-Zuwachs am Boundary-Sink,
    nicht die Gesamtzahl. B muss genau seine zwei Vergleiche bekommen und
    A seine drei; A's kaputte Datei darf B weder blockieren noch zaehlen."""
    from services.scheduler_dispatch_service import run_compare_presets_daily

    data_root, smtp_sent, user_a, user_b = env
    _setup_user(data_root, user_a, ["cp-a-ok", "cp-c-ok", "cp-d-ok"])
    (data_root / "users" / user_a / "briefings" / "cp-b-kaputt.json").write_text(
        "{not valid json", encoding="utf-8",
    )
    _setup_user(data_root, user_b, ["cp-b1", "cp-b2"])

    before_b = len(smtp_sent)
    result_b = run_compare_presets_daily(user_id=user_b, data_root=str(data_root), hour=6)
    mails_b = len(smtp_sent) - before_b

    before_a = len(smtp_sent)
    result_a = run_compare_presets_daily(user_id=user_a, data_root=str(data_root), hour=6)
    mails_a = len(smtp_sent) - before_a

    assert (result_b, mails_b) == ((2, 0), 2), (
        "AC-5: Nutzer B (ohne kaputte Datei) muss unberuehrt versenden, "
        f"kam {result_b!r} mit {mails_b} Mails"
    )
    assert (result_a, mails_a) == ((3, 0), 3), (
        "AC-5: Nutzer A muss seine drei gueltigen Vergleiche trotz kaputter "
        f"Datei versenden, kam {result_a!r} mit {mails_a} Mails"
    )
