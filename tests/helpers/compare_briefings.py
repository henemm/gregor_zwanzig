"""Gemeinsamer Test-Fixture-Helfer fuer den ComparePreset-Persistenz-Cutover
(Issue #1250 Scheibe 7b).

Nach dem Cutover leben ComparePresets per-Datei unter
``<user_dir>/briefings/<id>.json`` (``kind="vergleich"``) statt in der einen
Array-Datei ``compare_presets.json``. Dieser Helfer konsolidiert die
Array->per-Datei-Umschreibung, die sonst in ~14 Test-Dateien einzeln
dupliziert werden muesste (statt N lokaler ``_write_presets``-Kopien).

``write_compare_briefings`` schreibt jedes Preset als eigene
``briefings/<id>.json`` (kind wird auf "vergleich" gesetzt, damit der
inverse kind-Filter des Loaders sie sieht). ``read_compare_briefings`` liest
den Bestand wieder als Liste ein (sortiert nach Dateiname) — ein
Drop-in-Ersatz fuer das fruehere ``json.loads(compare_presets.json)``, damit
Bestandstests, die die Array-Form zurueckgelesen haben, minimal umgestellt
werden koennen.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def _zone_des_presets(user_dir: Path, preset: dict):
    """Die Zone, in der der Pruefling die Faelligkeit dieses Presets
    auswertet — ueber DIESELBE Aufloesung wie ``presets_due_for_hour``:
    ``first_resolvable_tz`` ueber die Orte in ``location_ids``, sonst UTC.

    Gelesen wird der Ortsbestand, der zum Zeitpunkt des Schreibens auf Platte
    liegt (``<user_dir>/locations/*.json``, geschrieben von
    ``app.loader.save_location``). Alle Aufrufer legen die Orte vor dem Preset
    an — ein Preset verweist ja auf sie. Faellt das doch einmal andersherum,
    ist die Zone hier UTC und die berechnete Stunde kann daneben liegen; das
    faellt dann als roter Test auf, nicht still.

    🔴 Bewusst ``resolve_location_tz`` in der Schleife statt
    ``first_resolvable_tz``: letzteres PROTOKOLLIERT den Fehlschlag als
    Warnung des Prueflings. Ein Testaufbau darf keine Produktiv-Warnung
    erzeugen — ``test_issue_461_...::test_manual_presets_are_always_skipped``
    prueft genau, dass fuer ein uebersprungenes Preset NICHTS protokolliert
    wird, und ging daran kaputt. Die Auswahlregel („erster AUFLOESBARER Ort,
    sonst UTC") ist dieselbe.
    """
    from utils.timezone import UTC, resolve_location_tz

    orte: dict[str, SimpleNamespace] = {}
    ordner = Path(user_dir) / "locations"
    if ordner.exists():
        for pfad in ordner.glob("*.json"):
            try:
                daten = json.loads(pfad.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(daten, dict) and daten.get("id"):
                orte[daten["id"]] = SimpleNamespace(**daten)
    for lid in preset.get("location_ids") or []:
        ort = orte.get(lid)
        if ort is None:
            continue
        zone = resolve_location_tz(ort)
        if zone is not None:
            return zone
    return UTC


def write_compare_briefings(
    user_dir: Path, presets: list[dict], *, briefing_stunde_setzen: bool = True,
) -> Path:
    """Schreibt jedes Preset per-Datei nach ``<user_dir>/briefings/<id>.json``
    mit ``kind="vergleich"``. Gibt das ``briefings/``-Verzeichnis zurueck.

    ``user_dir`` ist das Nutzerverzeichnis (z.B. ``tmp_path/users/<uid>`` bzw.
    ``DATA_ROOT/<uid>``). Presets ohne ``id`` erhalten einen stabilen
    Positions-Fallback, damit der Helfer nie still Dateien ueberschreibt.

    **Issue #1594 — Briefing-Stunde:** ein Preset OHNE ``morning_time`` faellt
    im Pruefling auf den Migrations-Rueckfall „Morgen-Slot aktiv um 06:00
    Ortszeit" (``compare_slot_scheduler.resolve_preset_slots``). Es ist damit
    taeglich 60 Minuten lang „Briefing steht unmittelbar bevor" — und die neue
    Vorlauf-Sperre unterdrueckt in diesem Fenster jeden Vergleichs-Alarm.
    Bestandstests, die einen Alarm erwarten, messen dann die Sperre statt ihrer
    eigenen Zusicherung (gemessen: 57 Faelle in 14 Dateien, taeglich zwei
    Stunden rot).

    Deshalb bekommt ein solches Preset hier eine ausdrueckliche Morgen-Stunde
    ausserhalb des Vorlaufs. Semantisch bleibt alles gleich: der Rueckfall
    liefert ``(morning_enabled=True, 06:00, evening_enabled=False, 18:00)``,
    der gesetzte Wert ``(True, <sichere Stunde>, False, 18:00)`` — nur die
    Stunde wandert. Presets, die ihre Zeiten SELBST setzen, bleiben unberuehrt;
    wer eine bestimmte Stunde braucht, bekommt sie.

    ``briefing_stunde_setzen=False`` schaltet das ab — fuer Tests, die den
    Migrations-Rueckfall selbst pruefen wollen.

    Bewusste Grenze: ``schedule="daily_evening"`` ohne Slot-Felder (Rueckfall
    auf den ABEND-Slot) wird nicht angefasst — kein Aufrufer benutzt das, und
    ein halb verstandener Umbau waere schlimmer als der bekannte Rest.
    """
    briefings = Path(user_dir) / "briefings"
    briefings.mkdir(parents=True, exist_ok=True)
    for i, preset in enumerate(presets):
        entry = dict(preset)
        entry["kind"] = "vergleich"
        if (
            briefing_stunde_setzen
            and entry.get("morning_time") is None
            and entry.get("schedule") != "daily_evening"
        ):
            from tests.helpers.briefing_zeiten import briefing_zeiten_iso

            entry["morning_time"], _ = briefing_zeiten_iso(
                _zone_des_presets(user_dir, entry)
            )
        preset_id = entry.get("id") or f"preset-{i}"
        (briefings / f"{preset_id}.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return briefings


def read_compare_briefings(user_dir: Path) -> list[dict]:
    """Liest den vergleich-Bestand aus ``<user_dir>/briefings/`` als Liste
    (sortiert nach Dateiname) — Drop-in fuer das fruehere Array-Rueckle­sen
    von ``compare_presets.json``."""
    briefings = Path(user_dir) / "briefings"
    if not briefings.exists():
        return []
    out: list[dict] = []
    for path in sorted(briefings.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("kind") == "vergleich":
            out.append(data)
    return out
