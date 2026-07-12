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
from app.loader import _parse_activity_profile, load_all_locations
from services.compare_slot_scheduler import presets_due_for_hour

logger = logging.getLogger("scheduler.dispatch")


def run_compare_presets_daily(
    user_id: str = "default",
    data_root: str | None = None,
    hour: int | None = None,
) -> int:
    """Verarbeitet alle faelligen Compare-Presets fuer den gegebenen User.

    #1232 Scheibe 2a: Laedt compare_presets.json (direktes Array), ermittelt
    ueber `presets_due_for_hour` (Morgen-/Abend-Slot, Pause-/Archiv-/Laufzeit-
    Guards, Migrations-Fallback fuer Altdaten) die zur gegebenen Stunde
    faelligen Presets samt Zieldatum, fuehrt ComparisonEngine aus, sendet
    E-Mail, persistiert Lauf-Status. Gibt Anzahl erfolgreich versendeter
    Presets zurueck.
    """
    if data_root is None:
        data_root = "data"

    preset_path = Path(data_root) / "users" / user_id / "compare_presets.json"
    if not preset_path.exists():
        logger.info("No compare_presets.json for user %s — skipping", user_id)
        return 0

    try:
        presets = _json.loads(preset_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to load compare_presets.json for %s: %s", user_id, e)
        return 0

    if hour is None:
        from zoneinfo import ZoneInfo

        hour = _datetime.now(ZoneInfo("Europe/Vienna")).hour

    due = presets_due_for_hour(presets, hour, date.today())

    settings = Settings().with_user_profile(user_id)
    success_count = 0
    all_locations = None  # lazy: only load when a faellige preset with location_ids is found

    for preset, target_date in due:
        preset_id = preset.get("id", "")

        # Lazy: erst laden, wenn ein faelliges Preset zu verarbeiten ist (#649).
        if all_locations is None:
            all_locations = load_all_locations(user_id=user_id)

        try:
            send_one_compare_preset(
                preset,
                settings,
                user_id,
                data_root,
                all_locations_cache=all_locations,
                target_date=target_date,
            )
            success_count += 1
        except ValueError as e:
            # Helper-Skip-Pfade: kein Empfaenger / Orte nicht aufloesbar → ueberspringen.
            logger.warning("%s", e)
        except Exception as e:
            logger.error("Compare preset %s failed: %s", preset_id, e)

    return success_count


def send_subscription_email(sub, subject: str, html_body: str, text_body: str, settings: Settings) -> None:
    """Send a subscription result via email if configured."""
    from output.channels.email import EmailOutput

    # Issue #252: per-Subscription recipients override settings.mail_to
    to_list = list(sub.recipients) if getattr(sub, "recipients", None) else None
    EmailOutput(settings).send(
        subject,
        html_body,
        plain_text_body=text_body,
        to=to_list,
    )
    logger.info(f"Email sent for: {sub.name}")


def send_subscription_telegram(sub, subject: str, text_body: str, settings: Settings) -> None:
    """Send a subscription result via Telegram if configured."""
    from output.channels.telegram import TelegramOutput

    TelegramOutput(settings).send(subject, text_body)
    logger.info(f"Telegram sent for: {sub.name}")


def save_subscription_status(user_id: str, sub, data_root: str | None = None) -> None:
    """Read-modify-write last_run/last_status for a single subscription.

    Issue #252 — Scheduler persists run-status directly in the JSON store
    (no HTTP call to the Go API, because the Go endpoint requires cookie-auth
    that the scheduler doesn't have).

    Only `last_run` and `last_status` are overwritten; every other field of the
    existing JSON entry is preserved (Read-Modify-Write per
    BUG-DATALOSS-GR221 / data_schema_backup contract).

    Args:
        user_id: User identifier (subscription file is per-user).
        sub: CompareSubscription whose last_run / last_status will be written.
        data_root: Optional override of the data root for tests
            (`{data_root}/users/{user_id}/compare_subscriptions.json`).
            Default `None` resolves to `data/users/{user_id}/...`.
    """
    base = data_root if data_root else "data"
    path = Path(base) / "users" / user_id / "compare_subscriptions.json"
    if not path.exists():
        logger.warning("Subscription file not found, cannot persist status: %s", path)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = _json.load(f)
    except (OSError, _json.JSONDecodeError) as e:
        logger.error("Failed to read subscription file %s: %s", path, e)
        return

    subs = payload.get("subscriptions", [])
    updated = False
    for entry in subs:
        if entry.get("id") == sub.id:
            if sub.last_run is not None:
                entry["last_run"] = sub.last_run
            if sub.last_status is not None:
                entry["last_status"] = sub.last_status
            # Issue #456 — Top-Ort nur schreiben, wenn nicht None (None loescht NICHT)
            top_ort = getattr(sub, "top_ort_letzter_versand", None)
            if top_ort is not None:
                entry["top_ort_letzter_versand"] = top_ort
            updated = True
            break

    if not updated:
        logger.warning("Subscription id %r not found in %s", sub.id, path)
        return

    try:
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to write subscription file %s: %s", path, e)


def save_compare_preset_status(
    user_id: str,
    preset_id: str,
    top_ort: str | None,
    data_root: str | None = None,
) -> None:
    """Read-Modify-Write: schreibt letzter_versand + top_ort_letzter_versand.

    Alle anderen Felder bleiben erhalten (BUG-DATALOSS-GR221).
    """
    if data_root is None:
        data_root = "data"

    path = Path(data_root) / "users" / user_id / "compare_presets.json"
    if not path.exists():
        return

    try:
        presets = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read compare_presets.json for status update: %s", e)
        return

    for entry in presets:
        if entry.get("id") == preset_id:
            entry["letzter_versand"] = _datetime.utcnow().isoformat() + "Z"
            entry["top_ort_letzter_versand"] = top_ort
            break

    try:
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(presets, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to write compare_presets.json %s: %s", path, e)


def build_compare_preset_subject(name: str, target_date: date) -> str:
    """Baut den Mail-Betreff fuer einen Compare-Preset-Versand (pure Funktion).

    Adversary-Fund F001 (#1232 Scheibe 2a): Das Betreff-Datum MUSS
    `target_date` widerspiegeln, nicht den Sende-Zeitpunkt — sonst
    widerspricht der Betreff beim Abend-Slot (target=morgen) dem Mail-Body
    ("Datum: morgen"). Als eigene pure Funktion extrahiert, damit sie ohne
    Netz/Mail-Versand deterministisch testbar ist.
    """
    return f"Wetter-Vergleich: {name} ({target_date.strftime('%d.%m.%Y')})"


def send_one_compare_preset(
    preset: dict,
    settings: Settings,
    user_id: str,
    data_root: str,
    all_locations_cache=None,
    target_date: date | None = None,
) -> tuple:
    """Fuehrt den Versand fuer ein einzelnes Compare-Preset durch.

    Gemeinsame Versandlogik fuer Daily-Loop und Einzelversand (#627).
    `target_date` (#1232 Scheibe 2a): Default `date.today()` fuer
    Rueckwaertskompatibilitaet mit dem Einzelversand-Pfad
    (`send_compare_preset`, ignoriert `schedule`); der Abend-Slot des
    Daily-Loops uebergibt heute+1.
    Gibt (top_ort, empfaenger) zurueck. Wirft ValueError wenn kein Empfaenger konfiguriert.
    """
    if target_date is None:
        target_date = date.today()
    from output.renderers.comparison import render_compare_email
    from output.channels.email import EmailOutput
    from services.comparison_engine import ComparisonEngine
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
    hour_from = preset.get("hour_from", 9)
    hour_to = preset.get("hour_to", 16)

    result = ComparisonEngine.run(
        locations=locations,
        time_window=(hour_from, hour_to),
        target_date=target_date,
        forecast_hours=preset.get("forecast_hours") or 48,  # Issue #764/#781: gespeicherten Horizont nutzen, 0 → 48
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
    )
    EmailOutput(settings).send(
        subject,
        html_body,
        plain_text_body=text_body,
        to=empfaenger,
        compare_hourly_enabled=opts.hourly_enabled,
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

    preset_path = Path(data_root) / "users" / user_id / "compare_presets.json"
    if not preset_path.exists():
        raise KeyError(f"Compare-Preset {preset_id} nicht gefunden")

    try:
        presets = _json.loads(preset_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise KeyError(f"Compare-Preset {preset_id} nicht ladbar: {e}") from e

    preset = next((p for p in presets if p.get("id") == preset_id), None)
    if preset is None:
        raise KeyError(f"Compare-Preset {preset_id} nicht gefunden")

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
