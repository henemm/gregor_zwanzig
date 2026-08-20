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
    get_data_root,
    load_all_locations,
    load_compare_presets,
)
from services.alert_briefing_anchor import (
    record_briefing_dispatch_failure,
    undelivered_since_last_briefing,
    write_anchor_and_reset_memory,
)
from services.compare_alert_channels import effective_compare_channels

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


def _auto_pause_expired_presets(
    presets: list,
    user_id: str,
    data_root: str,
    now_utc: _datetime,
    all_locations: list,
) -> None:
    """Pausiert Presets mit ueberschrittenem `end_date` (Issue #1250 Scheibe 3).

    Issue #1207: Extrahiert aus `run_compare_presets_daily` fuer Delegation
    durch `CompareDispatchStrategy.pre_pass()`. `presets_due_for_hour`
    VERBIRGT abgelaufene Presets bereits (compare_slot_scheduler.py Guard) --
    dieser Durchlauf laeuft unabhaengig davon ueber ALLE geladenen Presets,
    um den Pause-Zustand persistent + sichtbar (UI) zu machen.

    Issue #1727 S5b (ADR-0044): `end_date` wird gegen den ORTSTAG des ersten
    aufloesbaren Preset-Orts geprueft (`first_resolvable_tz`, dasselbe Muster
    wie die Faelligkeit seit #1726) -- nicht gegen den Servertag. Sonst blieb
    ein Preset im Mismatch-Fenster einen Tag zu lange aktiv (und verschickte
    einen abbestellten Vergleich) oder pausierte einen Tag zu frueh.
    `now_utc` und die Ortsliste kommen vom Aufrufer (`pre_pass`), der beide
    bereits hat -- ADR-0051 Regel 3, ohne zusaetzliche Zeitabfrage oder
    zweiten Ladevorgang.

    Der Zeitstempel `now_iso` stammt jetzt aus DERSELBEN Zeitabfrage wie die
    Ablauf-Pruefung (vorher `datetime.utcnow()`: naiv, ohne Zone, veraltet --
    und fuer Muster A des Zeitzonen-Waechters unsichtbar).
    """
    from services.compare_preview_service import order_locations_by_ids
    from utils.timezone import first_resolvable_tz, local_dt

    now_iso = now_utc.isoformat()
    for preset in presets:
        if preset.get("archived_at"):
            continue
        if preset.get("paused_at") or preset.get("schedule") == "manual":
            continue  # bereits pausiert -> idempotent, kein erneutes Schreiben
        end_date_str = preset.get("end_date")
        if not end_date_str:
            continue
        locations = order_locations_by_ids(
            all_locations, preset.get("location_ids") or [],
        )
        zone = first_resolvable_tz(
            locations, context_label=f"Preset {preset.get('id', '?')}",
        )
        try:
            expired = date.fromisoformat(end_date_str) < local_dt(now_utc, zone).date()
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
    *,
    tage_ab_ortstag: int,
) -> bool:
    """Sendet EIN faelliges Compare-Preset; liefert True bei Erfolg.

    Issue #1207: Extrahiert aus `run_compare_presets_daily` fuer Delegation
    durch `CompareDispatchStrategy.dispatch_one()` -- Fehler-Isolation
    unveraendert (ValueError -> Warn-Log + Skip, sonstige Exception ->
    Error-Log + Skip, kein Abbruch der uebrigen Presets).

    Issue #1661 (Adversary-Finding F003): `tage_ab_ortstag` ist PFLICHT und
    keyword-only, ohne Default. Beide Tagesformen stammen aus DERSELBEN
    Zeitabfrage im Slot-Scheduler (`DuePreset`); ein vergessenes Argument
    scheitert hier sofort mit `TypeError`, statt still auf eine zweite
    `date.today()`-Auswertung zurueckzufallen.
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
            tage_ab_ortstag=tage_ab_ortstag,
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
        data_root = str(get_data_root())

    from datetime import timezone as _timezone

    from services.dispatch_orchestrator import CompareDispatchStrategy, run_briefing_dispatch
    from utils.timezone import to_utc

    # Issue #1724: der Orchestrator nimmt einen ZEITPUNKT statt einer Stunde.
    # Issue #1726: die Faelligkeit haengt jetzt je Preset an der Ortszone
    # seines ersten Orts; nur der manuelle `?hour=`-Testausloeser bleibt an
    # einer festen Referenz-Zone verankert -- "Stunde X" hat sonst keine EINE
    # Bedeutung mehr. Verhalten des Endpunkts unveraendert.
    if hour is None:
        now_utc = _datetime.now(_timezone.utc)
    else:
        # Manuelles Ausloesen mit ausdruecklicher Stunde: Zeitpunkt bilden,
        # dessen Stunde in der Referenz-Zone genau `hour` ist -- damit bleibt
        # der bestehende Endpunkt-Vertrag (`?hour=`) erhalten.
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(CompareDispatchStrategy.MANUAL_TRIGGER_REFERENCE_ZONE)
        now_utc = to_utc(_datetime.now(zone).replace(
            hour=hour, minute=0, second=0, microsecond=0,
        ))

    return run_briefing_dispatch("vergleich", user_id, now_utc, data_root=data_root)


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
        data_root = str(get_data_root())

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
        data_root = str(get_data_root())
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
    """Duenner Wrapper (Issue #1467 S2 AG1) — delegiert an den geteilten
    Resolver `services.compare_alert_channels.effective_compare_channels`
    (identisches Muster wie `compare_official_alert._effective_channels`,
    Alarm-Pfad, jetzt auch fuer den Briefing-Pfad, Issue #1270 KB-3). Aufruf
    ueber den Modul-Namensraum, damit Tests das importierte Symbol im
    VERBRAUCHENDEN Modul patchen koennen (AC-3b).

    `send_email` ist auf Preset-Ebene bewusst NICHT beruecksichtigt: es wird gar
    nicht persistiert (vorbestehende Altlast, `versand_tab_vergleich.md` KL-6) —
    E-Mail bleibt daher wie bisher immer aktiv.
    """
    return effective_compare_channels(preset, settings, user_id)


def send_one_compare_preset(
    preset: dict,
    settings: Settings,
    user_id: str,
    data_root: str,
    all_locations_cache=None,
    target_date: date | None = None,
    tage_ab_ortstag: int | None = None,
    mail_sink=None,
    sms_sink=None,
    telegram_sink=None,
    on_demand: bool = False,
) -> tuple:
    """Fuehrt den Versand fuer ein einzelnes Compare-Preset durch.

    Gemeinsame Versandlogik fuer Daily-Loop und Einzelversand (#627).
    `target_date` (#1232 Scheibe 2a): der absolute Zieltag (Betreff,
    Vergleichs-Engine). `tage_ab_ortstag` (#1661, Adversary-Finding F003):
    DERSELBE Tag als Versatz gegen den Ortstag, fuer den Δ-Anker. Beide kommen
    aus derselben Zeitabfrage im Slot-Scheduler (`DuePreset`) und muessen
    deshalb GEMEINSAM uebergeben werden — nur eines von beiden ist ein
    Programmierfehler und scheitert laut mit `ValueError`, statt den anderen
    Wert aus einer zweiten `date.today()`-Auswertung zu rekonstruieren (genau
    daran lag der Anker nach einem Tagessprung still um einen Tag daneben).
    Ohne beides (Einzelversand-Pfad `send_compare_preset`, der `schedule`
    ignoriert) gilt „heute, Versatz 0" — EINE Zeitabfrage, kein Auseinander-
    laufen moeglich.
    `mail_sink`/`sms_sink`/`telegram_sink` (#1270): deterministische
    Transport-Naht, 1:1 durchgereicht an `NotificationService.send_compare_report`.
    `on_demand` (#1467 S2 AG5): Handversand — dann bleiben Δ-Anker UND
    Melde-Gedaechtnis unangetastet, genau wie beim Trip-Ad-hoc-Abruf (#1007).
    Gibt (top_ort, empfaenger) zurueck. Wirft ValueError wenn kein Empfaenger konfiguriert.
    """
    if (target_date is None) != (tage_ab_ortstag is None):
        raise ValueError(
            "send_one_compare_preset: `target_date` (absoluter Zieltag) und "
            "`tage_ab_ortstag` (Versatz gegen den Ortstag) gehoeren zusammen "
            "und muessen aus DERSELBEN Zeitabfrage stammen — entweder beide "
            "oder keines von beiden. Das fehlende aus `date.today()` "
            "nachzurechnen laege nach einem Tagessprung zwischen Sammel- und "
            "Schreibzeitpunkt still um einen Tag daneben (Preset "
            f"{preset.get('id', '?')}, target_date={target_date}, "
            f"tage_ab_ortstag={tage_ab_ortstag})."
        )
    from output.renderers.comparison import (
        render_compare_email, render_compare_sms, render_compare_telegram,
    )
    from services.compare_preview_service import order_locations_by_ids
    from services.comparison_engine import COMPARE_FORECAST_HOURS
    from services.comparison_parallel import run_comparison_parallel
    from services.notification_service import NotificationService
    from services.report_config_resolver import (
        resolve_compare_render_options, resolve_compare_time_window,
    )

    preset_id = preset.get("id", "")
    location_ids = preset.get("location_ids") or []

    # Empfaenger-Check: Issue #1452 — ausschliesslich die Konto-Settings des
    # Nutzers, `preset.empfaenger` ist inert (kein Preset-Override mehr).
    # Fehlerverhalten bewusst unveraendert laut (KL-3): ValueError statt Skip.
    default_to = getattr(settings, "mail_to", None)
    if not default_to:
        raise ValueError(
            f"Preset {preset_id}: kein Empfaenger — mail_to fehlt in den Konto-Settings"
        )
    empfaenger = [default_to]

    if all_locations_cache is None:
        all_locations_cache = load_all_locations(user_id=user_id)
    # Issue #1359 Scheibe 2: reihenfolge-erhaltend über location_ids filtern
    # (konfigurierte Orts-Reihenfolge), nicht über die Cache-Reihenfolge.
    locations = order_locations_by_ids(all_locations_cache, location_ids)
    if not locations:
        raise ValueError(f"Preset {preset_id}: Orte {location_ids} nicht aufloesbar")

    if target_date is None:
        # Kein Slot-Kontext (Einzelversand): EINE Zeitabfrage, aus der beide
        # Formen ohne Differenzbildung hervorgehen.
        # Issue #1727 S5b (ADR-0044): dieser Block steht jetzt HINTER der
        # Ortsaufloesung, weil sie die Zone liefert — „heute" ist der Ortstag
        # des ERSTEN AUFLOESBAREN Orts (`first_resolvable_tz`, Muster #1726),
        # nicht der Servertag. Vorher behauptete das daneben gesetzte
        # `tage_ab_ortstag = 0` einen Versatz gegen den ORTSTAG, waehrend
        # `target_date` vom Server kam — genau die zwei Tagesbegriffe, die der
        # Kontrakt aus #1661 F003 zusammenhalten sollte.
        # Der Empfaenger-Check bleibt VOR der Ortspruefung: die Reihenfolge der
        # beiden ValueError-Pfade zueinander ist unveraendert.
        from datetime import timezone as _timezone

        from utils.timezone import first_resolvable_tz, local_dt

        zone = first_resolvable_tz(locations, context_label=f"Preset {preset_id}")
        target_date = local_dt(_datetime.now(_timezone.utc), zone).date()
        tage_ab_ortstag = 0

    profil_str = preset.get("profil", "").lower()
    profile = _parse_activity_profile(profil_str)
    # Issue #1361/#1372 S1b: der Dispatch liest das Tagesfenster ueber
    # dieselbe Quelle wie der Trip-Zweig (day_window.resolve_configured_window).
    # Die deprecateten Preset-Werte hour_from/hour_to bleiben wirkungslos —
    # nur noch zur Bestandswahrung persistiert (#1361 Befund 1).
    # Issue #1765 Scheibe B1b: die Orte werden gleichzeitig statt nacheinander
    # gerechnet (ein Engine-Lauf JE ORT) -- sonst riss der Versand ab drei Orten
    # die 60-Sekunden-Grenze zwischen Go-API und nginx. Alle uebrigen Parameter
    # unveraendert; ``comparison_engine.py`` bleibt unangetastet.
    # ``call_source`` MUSS ausdruecklich gesetzt werden: ein ThreadPoolExecutor
    # reicht den ContextVar-Kontext nicht an seine Arbeiter weiter, die
    # Stack-Marker des Aufruf-Journals liefen im Worker-Thread ins Leere.
    result = run_comparison_parallel(
        locations=locations,
        time_window=resolve_compare_time_window(preset),
        target_date=target_date,
        forecast_hours=COMPARE_FORECAST_HOURS,  # Issue #1305: geteilte Konstante statt 48 fest
        profile=profile,
        official_alerts_enabled=preset.get("official_alerts_enabled", True),  # Issue #1040
        call_source="vergleich",
    )

    top_ort = result.locations[0].location.name if result.locations else None

    name = preset.get("name", preset_id)
    subject = build_compare_preset_subject(name, target_date)
    # Issue #1209 (Scheibe B): Render-Optionen ausschliesslich ueber den
    # Resolver aufloesen, statt inline aus dem rohen Preset-Dict zu lesen.
    opts = resolve_compare_render_options(preset)
    # Issue #1110: Abo-Footer-Metadaten (Preset-Name/Schedule/Weekday) zusaetzlich
    # zu den #1104-Parametern durchreichen (Merge beider Feature-Branches).
    # Issue #1461 S3b-1: die Vorfaelle haengen an der PROTOKOLL-Kennung
    # (`preset_id`, so schreiben compare_alert.py/compare_official_alert.py) --
    # NICHT an den Anker-Kennungen f"{preset_id}:{loc.id}" weiter unten.
    undelivered = undelivered_since_last_briefing(
        user_id=user_id, entity_id=preset_id, entity_type="compare",
    )
    html_body, text_body = render_compare_email(
        result,
        undelivered=undelivered,
        profile=profile,
        # Issue #1703 S8: kanal-eigene Uebersichts-Auswahl (bereits gegen die
        # Grundauswahl geschnitten). NICHT `opts.enabled_metrics` -- das ist die
        # gemeinsame Liste, mit der alle drei Kanaele dasselbe zeigten.
        enabled_metrics=opts.enabled_metrics_by_channel["email"],
        hourly_metrics=opts.hourly_metrics,
        hourly_enabled=opts.hourly_enabled,
        preset_name=name,
        preset_schedule=preset.get("schedule"),
        preset_weekday=preset.get("weekday"),
        corridors=opts.corridors,
        outlook_enabled=opts.outlook_enabled,
        outlook_metrics=opts.outlook_metrics,
    )
    # Issue #1169: Δ-Anker je Ort schreiben (ADR-0009 — Abweichung vom zuletzt
    # gemeldeten Stand). Best-effort: ein fehlgeschlagener Snapshot-Write darf
    # den bereits erfolgten Report-Versand nicht rückwirkend als Fehler zaehlen.
    # Issue #1467 S2 AG5: Anker und Melde-Gedaechtnis haengen an EINER Bedingung,
    # im selben geteilten Baustein, den auch der Trip benutzt. Der Reset laeuft
    # ueber ALLE Orte des Presets (R3), nicht nur die getriggerten.
    # Issue #1629: steht VOR dem Versand, weil dessen Fehlerpfad exakt denselben
    # Aufruf braucht — zwei Fassungen duerften auseinanderlaufen.
    # Issue #1661 (F002): der Δ-Anker bekommt den Slot-Tag RELATIV, nicht
    # absolut. Gegen den ORTSTAG aufgeloest wird er erst in `fetch()`; wuerde
    # der absolute (auf dem Server UTC-)Tag durchgereicht, traefe er fuer Orte
    # ab UTC+6 oestlich bzw. UTC-7 westlich den falschen Ortstag.
    #
    # Issue #1661 (F003): der Versatz wird NICHT mehr hier errechnet. Bis
    # Runde 2 stand hier `(target_date - date.today()).days` — eine Differenz
    # aus ZWEI `date.today()`-Auswertungen zu zwei verschiedenen
    # Realzeitpunkten (Sammeln im Orchestrator, Schreiben hier, dazwischen
    # Wetterabruf, Rendering und 2s je vorangehendem Preset). Fiel dazwischen
    # Mitternacht, lag der Versatz still um einen Tag daneben. Er kommt
    # deshalb jetzt von der Stelle, die ihn KENNT: `presets_due_for_hour`
    # (Morgen-Slot 0, Abend-Slot +1), durchgereicht ueber `DuePreset`.

    def _anchor_and_reset() -> None:
        write_anchor_and_reset_memory(
            user_id=user_id,
            entity_ids=[f"{preset_id}:{loc.id}" for loc in locations],
            write_anchor=lambda: _write_compare_alert_snapshots(
                preset_id, locations, user_id, preset, tage_ab_ortstag,
            ),
            on_demand=on_demand,
            # Issue #1461 S3b-1: der Briefing-Zeitstempel gehoert unter die
            # Protokoll-Kennung `preset_id` — unter den Anker-Kennungen oben
            # faende `read_undelivered()` nie einen Treffer.
            briefing_entity_id=preset_id,
            briefing_entity_type="compare",
        )

    # TODO(#1207): wird durch den Versand-Orchestrator generalisiert
    # Issue #1270 (KB-3): Kanal-Fan-out ueber den geteilten NotificationService
    # statt EmailOutput direkt — die gespeicherten Opt-ins send_telegram/
    # send_sms wirken damit endlich auch im Briefing-Pfad.
    # Issue #1629: dieselbe Bruchstelle wie beim Trip — wirft der Versand, fiel
    # der Anker fuer JEDEN Ort des Presets aus. Der Block umschliesst
    # ausschliesslich den Versandaufruf (AC-10), danach fliegt die Ausnahme
    # unveraendert weiter.
    try:
        send_result = NotificationService(settings, user_id).send_compare_report(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            # Issue #1703 S8: je Kanal die dort eingestellte Auswahl (s. oben).
            # Beide Render-Aufrufe bleiben bewusst INNERHALB des try-Blocks --
            # ihr Fehlerpfad gehoert wie bisher zu `record_briefing_dispatch_
            # failure` + `_anchor_and_reset()` (#1629).
            telegram_text=render_compare_telegram(
                result,
                enabled_metrics=opts.enabled_metrics_by_channel["telegram"],
                preset_name=name,
            ),
            sms_text=render_compare_sms(
                result, enabled_metrics=opts.enabled_metrics_by_channel["sms"],
            ),
            recipients=empfaenger,
            effective_channels=_effective_compare_channels(preset, settings, user_id),
            compare_hourly_enabled=opts.hourly_enabled,
            mail_sink=mail_sink,
            sms_sink=sms_sink,
            telegram_sink=telegram_sink,
        )
    except Exception as exc:
        record_briefing_dispatch_failure(
            user_id=user_id, kind="vergleich", entity_id=preset_id, error=exc,
        )
        _anchor_and_reset()
        raise

    # Issue #1714: im Briefing gezeigte amtliche Warnungen als „gemeldet"
    # vermerken, damit der unabhaengige Checker sie nicht kurz darauf erneut
    # als eigenen Alarm verschickt (Trip-Gegenstueck seit #1614 Teil 1).
    if send_result.sent and not on_demand:
        from services import alert_briefing_anchor

        for loc_result in result.locations:
            if loc_result.official_alerts:
                alert_briefing_anchor.record_official_alerts_reported(
                    user_id=user_id,
                    entity_id=f"{preset_id}:{loc_result.location.id}",
                    alerts=loc_result.official_alerts,
                )

    _anchor_and_reset()

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

    Issue #1467 S2 AG5: Handversand ⇒ `on_demand=True` — weder Δ-Anker noch
    Melde-Gedaechtnis werden angefasst. Sonst verschoebe ein Handversand den
    Vergleichspunkt und der naechste echte Ausschlag ginge still verloren.
    """
    if data_root is None:
        data_root = str(get_data_root())

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
    top_ort, actual_empfaenger = send_one_compare_preset(
        preset, settings, user_id, data_root, on_demand=True,
    )
    return {"status": "ok", "winner": top_ort or "", "empfaenger_count": len(actual_empfaenger)}


def _write_compare_alert_snapshots(
    preset_id: str, locations: list, user_id: str, preset: dict,
    tage_ab_ortstag: int,
) -> None:
    """Issue #1169 (A1/B1): schreibt je Ort den Δ-Anker-Snapshot über denselben
    `CompareLocationWeatherSource`-Impl, der auch der 15-Min-Alert-Check fuer
    das fresh-Wetter nutzt (Form-/Provider-Mismatch strukturell ausgeschlossen).
    Fail-soft je Ort — ein einzelner Fetch-Fehler darf die anderen Orte nicht
    verhindern und den bereits erfolgten Report-Versand nicht beeintraechtigen.

    Issue #1584 Scheibe C: das Tagesfenster des Presets wird durchgereicht,
    damit Anker und Frisch-Abruf (`compare_alert.py`) DENSELBEN Zuschnitt
    haben — sonst vergleicht der Alarm zwei verschiedene Tageszeiten. Quelle
    ist derselbe Aufloeser wie fuer Versand und Vorschau (ADR-0035).

    `preset` ist bewusst PFLICHT ohne Default (Adversary-Finding F001): mit
    `= None` waere ein vergessenes Argument still auf den Default 4/19
    zurueckgefallen und haette den Anker wieder im falschen Fenster
    geschrieben — dieselbe Fehlerklasse wie der stille Parameter-Rueckfall.
    Jetzt ist es ein sofortiger `TypeError`.

    Issue #1661 (Teil B): `tage_ab_ortstag` ist aus DEMSELBEN Grund PFLICHT
    ohne Default. Es traegt den VERSATZ zu dem Tag, ueber den das Briefing
    tatsaechlich informiert (Morgen-Slot 0, Abend-Slot +1,
    `compare_slot_scheduler.DuePreset`); ein stiller `= None`-Rueckfall wuerde
    den Abendanker wieder mit dem Schreibtag statt dem gebriefeten Tag
    beschriften — exakt der Fehler, den diese Scheibe behebt.

    Der Wert wird DURCHGEREICHT, nie berechnet (Adversary-Finding F003):
    Quelle ist die einzige Stelle, die den Slot kennt, und deren einmalige
    Zeitabfrage. Jede Rekonstruktion aus einem spaeteren `date.today()` liegt
    nach einem Tagessprung still um einen Tag daneben.

    Bewusst ein VERSATZ und kein absoluter Tag (Adversary-Finding F002): den
    Kalendertag bildet `fetch()` weiterhin aus der ORTSZEIT am jeweiligen Ort.
    Der absolute Tag des Dispatch-Loops stammt aus `date.today()`
    (Systemzeit = UTC auf dem Server) und zeigt zur Slot-Zeit fuer Orte ab
    UTC+6 oestlich bzw. UTC-7 westlich auf einen anderen Ortstag.
    """
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.report_config_resolver import resolve_compare_time_window

    start_hour, end_hour = resolve_compare_time_window(preset)
    source = CompareLocationWeatherSource()
    snapshot_service = CompareWeatherSnapshotService(user_id=user_id)
    for loc in locations:
        try:
            # Issue #1991 (AC-6, N2-Nachbesserung): `elevation_m` wird
            # BEDINGUNGSLOS uebergeben -- das `LocationWeatherSource.fetch`-
            # Protocol (services/point_weather.py:84) traegt den Parameter
            # ohnehin. Eine konditionale Weitergabe wuerde eine
            # Implementierung ohne den Parameter still ohne Hoehe
            # weiterlaufen lassen -- genau der Fehler, den dieses Ticket
            # beseitigt.
            zusatz = {
                "tage_ab_ortstag": tage_ab_ortstag,
                "elevation_m": loc.elevation_m,
            }
            point = source.fetch(
                loc.id, loc.lat, loc.lon, start_hour, end_hour, **zusatz
            )
            snapshot_service.save(preset_id, loc.id, point)
        except Exception as e:
            logger.warning(
                "Compare-Alert-Snapshot fuer Preset %s / Ort %s fehlgeschlagen: %s",
                preset_id, loc.id, e,
            )
