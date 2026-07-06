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

logger = logging.getLogger("scheduler.dispatch")


def run_compare_presets_daily(user_id: str = "default", data_root: str | None = None) -> int:
    """Verarbeitet alle Compare-Presets mit schedule='daily' fuer den gegebenen User.

    Laedt compare_presets.json (direktes Array), filtert auf schedule='daily'
    bzw. 'weekly' wenn heute der konfigurierte Wochentag ist, fuehrt
    ComparisonEngine aus, sendet E-Mail, persistiert Lauf-Status.
    Gibt Anzahl erfolgreich versendeter Presets zurueck.
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

    settings = Settings().with_user_profile(user_id)
    success_count = 0
    all_locations = None  # lazy: only load when a daily preset with location_ids is found

    for preset in presets:
        schedule = preset.get("schedule", "")
        if schedule == "daily":
            pass  # wie bisher
        elif schedule == "weekly":
            today_weekday = date.today().weekday()  # 0=Montag … 6=Sonntag
            preset_weekday = preset.get("weekday", 4)
            if preset_weekday != today_weekday:
                continue  # nicht fällig heute
        else:
            continue  # manual und unbekannte Typen überspringen

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
    from outputs.email import EmailOutput

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
    from outputs.telegram import TelegramOutput

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


def send_one_compare_preset(
    preset: dict,
    settings: Settings,
    user_id: str,
    data_root: str,
    all_locations_cache=None,
) -> tuple:
    """Fuehrt den Versand fuer ein einzelnes Compare-Preset durch.

    Gemeinsame Versandlogik fuer Daily-Loop und Einzelversand (#627).
    Gibt (top_ort, empfaenger) zurueck. Wirft ValueError wenn kein Empfaenger konfiguriert.
    """
    from output.renderers.email.compare_html import render_compare_html
    from outputs.email import EmailOutput
    from services.comparison_engine import ComparisonEngine
    from services.comparison_renderers import render_comparison_text

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
        target_date=date.today(),
        forecast_hours=preset.get("forecast_hours", 48),  # Issue #764: gespeicherten Horizont nutzen
        profile=profile,
    )

    top_ort = result.locations[0].location.name if result.locations else None

    name = preset.get("name", preset_id)
    subject = f"Wetter-Vergleich: {name} ({_datetime.now().strftime('%d.%m.%Y')})"
    html_body = render_compare_html(result, profile=profile)
    text_body = render_comparison_text(result, profile=profile)
    EmailOutput(settings).send(
        subject,
        html_body,
        plain_text_body=text_body,
        to=empfaenger,
    )

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
