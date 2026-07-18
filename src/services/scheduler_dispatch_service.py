"""Scheduler dispatch service.

Encapsulates channel-specific sending and compare-preset rendering used by
the scheduler router so that api/routers/scheduler.py does not import
outputs.* or output.renderers.* directly.
"""
from __future__ import annotations

import json as _json
import logging
from datetime import date, datetime as _datetime
from pathlib import Path

from app.config import Settings
from app.loader import (
    LoaderError,
    _parse_activity_profile,
    compare_preset_to_dict,
    load_all_locations,
    load_compare_presets,
)

logger = logging.getLogger("scheduler.dispatch")


def _load_presets_for_dispatch(user_id: str, data_root: str) -> list | None:
    """Laedt die Compare-Presets eines Users fuer den Dispatch.

    Issue #1207: Extrahiert aus `run_compare_presets_daily` fuer Delegation
    durch `CompareDispatchStrategy.collect_due()`. `None` signalisiert "kein
    Versand" (fehlendes `briefings/`-Verzeichnis oder Ladefehler, jeweils
    bereits geloggt) -- der Aufrufer behandelt das wie eine leere
    Faelligkeits-Liste.
    """
    # Issue #1250 Scheibe 7b: Existenz-Check gegen das briefings/-Verzeichnis
    # (Cutover-Lesepfad), strict=True bewahrt die alte ERROR-Diagnose bei
    # Korruption statt sie unter dem Skip-INFO-Log zu verstecken.
    briefings_dir = Path(data_root) / "users" / user_id / "briefings"
    if not briefings_dir.exists():
        logger.info("No briefings/ dir for user %s — skipping", user_id)
        return None

    try:
        return [
            compare_preset_to_dict(p)
            for p in load_compare_presets(user_id=user_id, data_root=data_root, strict=True)
        ]
    except LoaderError as e:
        logger.error("Failed to load compare presets for %s: %s", user_id, e)
        return None


def _auto_pause_expired_presets(presets: list, user_id: str, data_root: str) -> None:
    """Pausiert Presets mit ueberschrittenem `end_date` (Issue #1250 Scheibe 3).

    Issue #1207: Extrahiert aus `run_compare_presets_daily` fuer Delegation
    durch `CompareDispatchStrategy.pre_pass()`. `presets_due_for_hour`
    VERBIRGT abgelaufene Presets bereits (compare_slot_scheduler.py Guard) --
    dieser Durchlauf laeuft unabhaengig davon ueber ALLE geladenen Presets,
    um den Pause-Zustand persistent + sichtbar (UI) zu machen.
    """
    now_iso = _datetime.utcnow().isoformat() + "Z"
    for preset in presets:
        if preset.get("archived_at"):
            continue
        if preset.get("paused_at") or preset.get("schedule") == "manual":
            continue  # bereits pausiert -> idempotent, kein erneutes Schreiben
        end_date_str = preset.get("end_date")
        if not end_date_str:
            continue
        try:
            expired = date.fromisoformat(end_date_str) < date.today()
        except (ValueError, TypeError) as e:
            logger.warning(
                "Preset %s: korruptes end_date bei Auto-Pause-Pruefung, "
                "wird uebersprungen: %s",
                preset.get("id", "?"),
                e,
            )
            continue
        if expired:
            save_compare_preset_pause(user_id, preset.get("id", ""), data_root, now_iso)


def _dispatch_due_preset(
    preset: dict,
    target_date: date,
    settings: Settings,
    user_id: str,
    data_root: str,
    all_locations_cache: list,
) -> bool:
    """Sendet EIN faelliges Compare-Preset; liefert True bei Erfolg.

    Issue #1207: Extrahiert aus `run_compare_presets_daily` fuer Delegation
    durch `CompareDispatchStrategy.dispatch_one()` -- Fehler-Isolation
    unveraendert (ValueError -> Warn-Log + Skip, sonstige Exception ->
    Error-Log + Skip, kein Abbruch der uebrigen Presets).
    """
    preset_id = preset.get("id", "")
    try:
        send_one_compare_preset(
            preset,
            settings,
            user_id,
            data_root,
            all_locations_cache=all_locations_cache,
            target_date=target_date,
        )
        return True
    except ValueError as e:
        # Helper-Skip-Pfade: kein Empfaenger / Orte nicht aufloesbar → ueberspringen.
        logger.warning("%s", e)
        return False
    except Exception as e:
        logger.error("Compare preset %s failed: %s", preset_id, e)
        return False


def run_compare_presets_daily(
    user_id: str = "default",
    data_root: str | None = None,
    hour: int | None = None,
) -> tuple[int, int]:
    """Verarbeitet alle faelligen Compare-Presets fuer den gegebenen User.

    #1232 Scheibe 2a / #1250 S7b: Laedt ComparePresets ueber load_compare_presets
    (per-Datei briefings/, kind="vergleich"), ermittelt
    ueber `presets_due_for_hour` (Morgen-/Abend-Slot, Pause-/Archiv-/Laufzeit-
    Guards, Migrations-Fallback fuer Altdaten) die zur gegebenen Stunde
    faelligen Presets samt Zieldatum, fuehrt ComparisonEngine aus, sendet
    E-Mail, persistiert Lauf-Status. Gibt `(sent, failed)` zurueck --
    Anzahl erfolgreich versendeter bzw. gescheiterter faelliger Presets
    (Issue #1290, E1: vormals nur `sent` als `int`, ein 100%-Ausfall war von
    einem leeren Lauf nicht unterscheidbar).

    Issue #1207: Thin-Wrapper -- delegiert an den geteilten
    Versand-Orchestrator (`run_briefing_dispatch`), der das Skelett mit dem
    Trip-Versandweg teilt. `data_root`-/`hour`-Defaulting bleibt hier (der
    Orchestrator selbst kennt keinen Compare-spezifischen Default), Verhalten
    unveraendert (AC-3).
    """
    if data_root is None:
        data_root = "data"
    if hour is None:
        from zoneinfo import ZoneInfo

        hour = _datetime.now(ZoneInfo("Europe/Vienna")).hour

    from services.dispatch_orchestrator import run_briefing_dispatch

    return run_briefing_dispatch("vergleich", user_id, hour, data_root=data_root)


def save_compare_preset_status(
    user_id: str,
    preset_id: str,
    top_ort: str | None,
    data_root: str | None = None,
) -> None:
    """Read-Modify-Write: schreibt letzter_versand + top_ort_letzter_versand.

    Issue #1250 Scheibe 7b Cutover: per-Datei-RMW auf briefings/<id>.json
    (kind="vergleich") statt Array-RMW auf compare_presets.json. Alle anderen
    Felder bleiben erhalten (BUG-DATALOSS-GR221); `kind="vergleich"` wird
    sichergestellt, damit die Datei fuer den Go-Loader (inverser kind-Filter)
    und load_compare_presets sichtbar bleibt.
    """
    if data_root is None:
        data_root = "data"

    path = Path(data_root) / "users" / user_id / "briefings" / f"{preset_id}.json"
    if not path.exists():
        return

    try:
        entry = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read briefing %s for status update: %s", path, e)
        return
    if not isinstance(entry, dict):
        return

    # Issue #1250 S7b (Adversary Fix-Loop F002): kind-Guard symmetrisch zu Gos
    # DeleteComparePreset (internal/store/compare_preset.go). Bei ID-Kollision
    # darf ein Trip (kind="route") NIE still in ein Fake-vergleich korrumpiert
    # werden -- nur echte/neue vergleich-Eintraege (oder kind-leer) duerfen ueber
    # diesen Pfad geschrieben werden.
    if entry.get("kind") not in (None, "", "vergleich"):
        logger.warning(
            "briefing %s traegt kind=%r (kein vergleich) -- Status-Write "
            "uebersprungen (F002, keine Trip-Korruption)",
            path, entry.get("kind"),
        )
        return

    entry["letzter_versand"] = _datetime.utcnow().isoformat() + "Z"
    entry["top_ort_letzter_versand"] = top_ort
    entry["kind"] = "vergleich"

    try:
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(entry, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to write briefing %s: %s", path, e)


def save_compare_preset_pause(
    user_id: str,
    preset_id: str,
    data_root: str | None = None,
    now_iso: str | None = None,
) -> None:
    """Read-Modify-Write: schreibt den Auto-Pause-Zustand (Issue #1250 Scheibe 3).

    Self-konsistente Pause-Repraesentation identisch zur manuellen Pause
    (`schedule="manual"` + `previous_schedule`), damit sie die Go-
    Normalisierung (`NormalizeComparePreset`) uebersteht. Merge, kein
    Replace (BUG-DATALOSS-GR221) — alle anderen Felder bleiben erhalten.
    """
    if data_root is None:
        data_root = "data"
    if now_iso is None:
        now_iso = _datetime.utcnow().isoformat() + "Z"

    path = Path(data_root) / "users" / user_id / "briefings" / f"{preset_id}.json"
    if not path.exists():
        return

    try:
        entry = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read briefing %s for pause update: %s", path, e)
        return
    if not isinstance(entry, dict):
        return

    # Issue #1250 S7b (Adversary Fix-Loop F002): kind-Guard symmetrisch zu Gos
    # DeleteComparePreset -- bei ID-Kollision einen Trip (kind="route") NIE
    # still in ein Fake-vergleich pausieren/korrumpieren.
    if entry.get("kind") not in (None, "", "vergleich"):
        logger.warning(
            "briefing %s traegt kind=%r (kein vergleich) -- Pause-Write "
            "uebersprungen (F002, keine Trip-Korruption)",
            path, entry.get("kind"),
        )
        return

    if entry.get("schedule") != "manual":
        entry["previous_schedule"] = entry.get("schedule", "")
        entry["schedule"] = "manual"
    if not entry.get("paused_at"):
        entry["paused_at"] = now_iso
    entry["kind"] = "vergleich"

    try:
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(entry, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to write briefing %s: %s", path, e)


def build_compare_preset_subject(name: str, target_date: date) -> str:
    """Baut den Mail-Betreff fuer einen Compare-Preset-Versand (pure Funktion).

    Adversary-Fund F001 (#1232 Scheibe 2a): Das Betreff-Datum MUSS
    `target_date` widerspiegeln, nicht den Sende-Zeitpunkt — sonst
    widerspricht der Betreff beim Abend-Slot (target=morgen) dem Mail-Body
    ("Datum: morgen"). Als eigene pure Funktion extrahiert, damit sie ohne
    Netz/Mail-Versand deterministisch testbar ist.
    """
    return f"Wetter-Vergleich: {name} ({target_date.strftime('%d.%m.%Y')})"


def _effective_compare_channels(preset: dict, settings: Settings, user_id: str) -> set[str]:
    """E-Mail immer; Telegram/SMS nur bei Preset-Opt-in UND globaler
    User-Faehigkeit (bei SMS zusaetzlich Tier-Gate) — identisches Muster wie
    `compare_official_alert._effective_channels` (Alarm-Pfad), jetzt auch fuer
    den Briefing-Pfad (Issue #1270, KB-3).

    `send_email` ist auf Preset-Ebene bewusst NICHT beruecksichtigt: es wird gar
    nicht persistiert (vorbestehende Altlast, `versand_tab_vergleich.md` KL-6) —
    E-Mail bleibt daher wie bisher immer aktiv.
    """
    from services.user_tier import sms_allowed

    channels = {"email"}
    if preset.get("send_telegram") and settings.can_send_telegram():
        channels.add("telegram")
    if preset.get("send_sms") and settings.can_send_sms() and sms_allowed(user_id):
        channels.add("sms")
    return channels


def send_one_compare_preset(
    preset: dict,
    settings: Settings,
    user_id: str,
    data_root: str,
    all_locations_cache=None,
    target_date: date | None = None,
    mail_sink=None,
    sms_sink=None,
    telegram_sink=None,
) -> tuple:
    """Fuehrt den Versand fuer ein einzelnes Compare-Preset durch.

    Gemeinsame Versandlogik fuer Daily-Loop und Einzelversand (#627).
    `target_date` (#1232 Scheibe 2a): Default `date.today()` fuer
    Rueckwaertskompatibilitaet mit dem Einzelversand-Pfad
    (`send_compare_preset`, ignoriert `schedule`); der Abend-Slot des
    Daily-Loops uebergibt heute+1.
    `mail_sink`/`sms_sink`/`telegram_sink` (#1270): deterministische
    Transport-Naht, 1:1 durchgereicht an `NotificationService.send_compare_report`.
    Gibt (top_ort, empfaenger) zurueck. Wirft ValueError wenn kein Empfaenger konfiguriert.
    """
    if target_date is None:
        target_date = date.today()
    from output.renderers.comparison import (
        render_compare_email, render_compare_sms, render_compare_telegram,
    )
    from services.comparison_engine import COMPARE_FORECAST_HOURS, ComparisonEngine
    from services.notification_service import NotificationService
    from services.report_config_resolver import resolve_compare_render_options

    preset_id = preset.get("id", "")
    location_ids = preset.get("location_ids") or []

    # Empfaenger-Check + mail_to-Fallback
    empfaenger = preset.get("empfaenger") or []
    if not empfaenger:
        default_to = getattr(settings, "mail_to", None)
        if not default_to:
            raise ValueError(f"Preset {preset_id}: keine empfaenger und kein mail_to-Fallback")
        empfaenger = [default_to]
        logger.info("Preset %s: empfaenger leer, nutze mail_to=%s", preset_id, default_to)

    if all_locations_cache is None:
        all_locations_cache = load_all_locations(user_id=user_id)
    locations = [loc for loc in all_locations_cache if loc.id in location_ids]
    if not locations:
        raise ValueError(f"Preset {preset_id}: Orte {location_ids} nicht aufloesbar")

    profil_str = preset.get("profil", "").lower()
    profile = _parse_activity_profile(profil_str)
    # Issue #1268: Zeitfenster und Horizont sind keine Editor-Felder mehr.
    # Der Dispatch liest die (deprecateten) Preset-Werte hour_from/hour_to/
    # forecast_hours nicht mehr — sie bleiben nur zur Bestandswahrung persistiert.
    result = ComparisonEngine.run(
        locations=locations,
        time_window=(0, 23),  # Issue #1268: ganzer Tag, kein Editor-Feld mehr
        target_date=target_date,
        forecast_hours=COMPARE_FORECAST_HOURS,  # Issue #1305: geteilte Konstante statt 48 fest
        profile=profile,
        official_alerts_enabled=preset.get("official_alerts_enabled", True),  # Issue #1040
    )

    top_ort = result.locations[0].location.name if result.locations else None

    name = preset.get("name", preset_id)
    subject = build_compare_preset_subject(name, target_date)
    # Issue #1209 (Scheibe B): Render-Optionen ausschliesslich ueber den
    # Resolver aufloesen, statt inline aus dem rohen Preset-Dict zu lesen.
    opts = resolve_compare_render_options(preset)
    # Issue #1110: Abo-Footer-Metadaten (Preset-Name/Schedule/Weekday) zusaetzlich
    # zu den #1104-Parametern durchreichen (Merge beider Feature-Branches).
    html_body, text_body = render_compare_email(
        result,
        profile=profile,
        top_n_details=opts.top_n_details,
        enabled_metrics=opts.enabled_metrics,
        hourly_metrics=opts.hourly_metrics,
        hourly_enabled=opts.hourly_enabled,
        preset_name=name,
        preset_schedule=preset.get("schedule"),
        preset_weekday=preset.get("weekday"),
        corridors=opts.corridors,
        outlook_enabled=opts.outlook_enabled,
    )
    # TODO(#1207): wird durch den Versand-Orchestrator generalisiert
    # Issue #1270 (KB-3): Kanal-Fan-out ueber den geteilten NotificationService
    # statt EmailOutput direkt — die gespeicherten Opt-ins send_telegram/
    # send_sms wirken damit endlich auch im Briefing-Pfad.
    NotificationService(settings, user_id).send_compare_report(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        telegram_text=render_compare_telegram(
            result, enabled_metrics=opts.enabled_metrics, preset_name=name,
        ),
        sms_text=render_compare_sms(result, enabled_metrics=opts.enabled_metrics),
        recipients=empfaenger,
        effective_channels=_effective_compare_channels(preset, settings, user_id),
        compare_hourly_enabled=opts.hourly_enabled,
        mail_sink=mail_sink,
        sms_sink=sms_sink,
        telegram_sink=telegram_sink,
    )

    # Issue #1169: Δ-Anker je Ort schreiben (ADR-0009 — Abweichung vom zuletzt
    # gemeldeten Stand). Best-effort: ein fehlgeschlagener Snapshot-Write darf
    # den bereits erfolgten Report-Versand nicht rückwirkend als Fehler zaehlen.
    _write_compare_alert_snapshots(preset_id, locations, user_id)

    save_compare_preset_status(user_id, preset_id, top_ort, data_root=data_root)
    logger.info("Compare preset %s sent to %s (top_ort=%s)", preset_id, empfaenger, top_ort)
    return top_ort, empfaenger


def send_compare_preset(
    user_id: str,
    preset_id: str,
    data_root: str | None = None,
) -> dict:
    """Einzelversand fuer ein Compare-Preset — ignoriert schedule.

    Endpoint: POST /api/scheduler/compare-presets/{id}/send (#627).
    Wirft KeyError wenn Preset nicht gefunden, ValueError wenn kein Empfaenger.
    """
    if data_root is None:
        data_root = "data"

    # Issue #1250 Scheibe 1 (Adversary-Fix F001): strict=True, damit korrupte
    # Dateien wie vor der Umstellung als KeyError mit Original-Parse-Fehler
    # durchschlagen (API-404-Detail), statt fail-soft als "nicht gefunden".
    try:
        presets = load_compare_presets(user_id=user_id, data_root=data_root, strict=True)
    except LoaderError as e:
        raise KeyError(f"Compare-Preset {preset_id} nicht ladbar: {e}") from e
    preset_obj = next((p for p in presets if p.id == preset_id), None)
    if preset_obj is None:
        raise KeyError(f"Compare-Preset {preset_id} nicht gefunden")
    preset = compare_preset_to_dict(preset_obj)

    settings = Settings().with_user_profile(user_id)
    top_ort, actual_empfaenger = send_one_compare_preset(preset, settings, user_id, data_root)
    return {"status": "ok", "winner": top_ort or "", "empfaenger_count": len(actual_empfaenger)}


def _write_compare_alert_snapshots(preset_id: str, locations: list, user_id: str) -> None:
    """Issue #1169 (A1/B1): schreibt je Ort den Δ-Anker-Snapshot über denselben
    `CompareLocationWeatherSource`-Impl, der auch der 15-Min-Alert-Check fuer
    das fresh-Wetter nutzt (Form-/Provider-Mismatch strukturell ausgeschlossen).
    Fail-soft je Ort — ein einzelner Fetch-Fehler darf die anderen Orte nicht
    verhindern und den bereits erfolgten Report-Versand nicht beeintraechtigen.
    """
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    source = CompareLocationWeatherSource()
    snapshot_service = CompareWeatherSnapshotService(user_id=user_id)
    for loc in locations:
        try:
            point = source.fetch(loc.id, loc.lat, loc.lon)
            snapshot_service.save(preset_id, loc.id, point)
        except Exception as e:
            logger.warning(
                "Compare-Alert-Snapshot fuer Preset %s / Ort %s fehlgeschlagen: %s",
                preset_id, loc.id, e,
            )
