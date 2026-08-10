"""Vergleichs-Bezugspunkt (Δ-Anker) und Melde-Gedächtnis — EIN geteilter
Baustein für Trip UND Ortsvergleich (Issue #1467 Scheibe S2, AG5).

PO wörtlich: „Beide Dienste sollen sich natürlich gleich verhalten. Verwende
zwingend den gleichen Code."

Warum ein gemeinsamer Baustein und nicht zwei `if`-Zweige: Δ-Anker und
Melde-Gedächtnis MÜSSEN immer zusammen und unter DERSELBEN Bedingung behandelt
werden. Ein frischer Anker ohne Gedächtnis-Reset ist die gefährlichste
Kombination — `DeviationAlertEngine._filter_against_alert_state`
(`app/deviation_alert_engine.py`) vergleicht gegen den ABSOLUTEN
`last_reported_value` des Gedächtnisses; steht dort noch der alte Wert, während
der Anker schon der neue ist, verschwinden Änderungen gegenüber dem — jetzt
überschriebenen — Vergleichspunkt für immer (stiller ausbleibender Alarm).

Reihenfolge: erst Anker schreiben, dann Gedächtnis leeren.

`AlertStateService.reset()` schont `official_alert:`-Schlüssel bereits selbst
(#1460 P2) — hier wird nichts nachgebaut.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt „AG5",
AC-14..AC-19 und AC-27.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

logger = logging.getLogger("alert_briefing_anchor")

# Eigene Ablage, bewusst NICHT als weiterer Top-Level-Schluessel in
# `alert_log.json`: die Protokolldatei wird von `append_entry()` per
# Read-Modify-Write ueber die volle Datei geschrieben, und Go liest sie
# (`internal/store/log.go`). Ein zusaetzlicher Schluessel dort waere ein
# Fremdkoerper im geteilten Schema — hier ist er strukturell folgenlos (D4).
_BRIEFING_ANCHOR_FILE = "briefing_anchor.json"


# Diagnose-Spur gescheiterter Briefing-Versände (#1629). Eine Zeile je
# Fehlschlag, JSONL wie `openmeteo_calls.jsonl` — Leser ist
# `analyzeBriefingDispatchErrors` (internal/scheduler/briefing_health.go), das
# daraus das mit der Ausfalldauer wachsende Signal am Status-Endpunkt bildet.
_DISPATCH_FAILURE_FILE = "briefing_dispatch_failures.jsonl"


def _anchor_path(user_id: str):
    from app.loader import get_data_dir

    return get_data_dir(user_id) / _BRIEFING_ANCHOR_FILE


def record_briefing_dispatch_failure(
    *, user_id: str, kind: str, entity_id: str, error: object,
) -> None:
    """Hält einen gescheiterten Briefing-Versand als Diagnose-Spur fest (#1629).

    Args:
        user_id: echte Nutzer-Kennung (Mandantentrennung, nie `"default"`).
        kind: `"route"` (Trip) oder `"vergleich"` (Ortsvergleich).
        entity_id: Trip- bzw. Preset-Kennung.
        error: die gefangene Ausnahme (als Freitext festgehalten).

    Der Pfad wird über die zentrale Datenwurzel aufgelöst (`get_data_dir`),
    nie repo-relativ — ein fest verdrahteter `data/`-Pfad hat zuletzt die
    gesamte Überwachung blind gemacht (#1633).

    Fail-soft (AC-7): ein Fehler hier darf die eigentliche Versandausnahme
    weder verhindern noch überdecken — deshalb wird JEDE Ausnahme gefangen und
    nur geloggt.
    """
    try:
        from app.loader import get_data_dir

        path = get_data_dir(user_id) / "diagnostics" / _DISPATCH_FAILURE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "entity_id": entity_id,
            "error": str(error),
        }, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as e:  # noqa: BLE001 — fail-soft, AC-7
        logger.warning(
            "Diagnose-Spur zum gescheiterten Versand (%s) nicht schreibbar: %s: %s",
            entity_id, type(e).__name__, e,
        )


def record_briefing_sent(
    *, user_id: str, entity_id: str, entity_type: str,
    at: Optional[datetime] = None,
) -> None:
    """Haelt fest, WANN zuletzt ein Briefing dieser Kennung rausging (#1461).

    🔴 `entity_id` MUSS die **Protokoll**-Kennung sein — Trip: `trip.id`;
    Ortsvergleich: `preset_id` (so schreibt `compare_alert.py` das Protokoll),
    NICHT die Anker-Kennungen `f"{preset_id}:{loc.id}"`. Unter denen faende
    `read_undelivered()` nie einen Treffer und der Hinweis bliebe beim
    Ortsvergleich dauerhaft leer.

    Fail-soft: ein Schreibfehler darf einen bereits versandten Report nicht
    rueckwirkend zum Fehler machen.
    """
    moment = (at or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    path = _anchor_path(user_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault(entity_type, {})[entity_id] = moment.isoformat()
        path.write_text(json.dumps(data, indent=2))
    except (OSError, ValueError, AttributeError) as e:
        logger.warning("Briefing-Zeitstempel fuer %s nicht schreibbar: %s", entity_id, e)


def last_briefing_at(
    *, user_id: str, entity_id: str, entity_type: str,
) -> Optional[datetime]:
    """Zeitpunkt des letzten Briefings dieser Kennung — `None`, wenn es noch
    keins gab (Bestandsnutzer, erstes Briefing nach der Auslieferung)."""
    path = _anchor_path(user_id)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
        raw = (data.get(entity_type) or {}).get(entity_id)
        if not raw:
            return None
        ts = datetime.fromisoformat(str(raw))
    except (OSError, ValueError, AttributeError) as e:
        logger.warning("Briefing-Zeitstempel fuer %s nicht lesbar: %s", entity_id, e)
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def undelivered_since_last_briefing(
    *, user_id: str, entity_id: str, entity_type: str,
) -> list:
    """DIE Naht, aus der beide Briefing-Pfade den Hinweis speisen (#1461).

    Ohne gespeicherten Zeitpunkt beginnt der Rueckblick **ab jetzt** — sonst
    kippte beim ersten Briefing nach der Auslieferung die gesamte Historie in
    die Mail (AC-7).
    """
    from services.alert_log import read_undelivered

    since = last_briefing_at(
        user_id=user_id, entity_id=entity_id, entity_type=entity_type,
    )
    if since is None:
        return []
    return read_undelivered(
        user_id, entity_id=entity_id, entity_type=entity_type, since=since,
    )


def write_anchor_and_reset_memory(
    *,
    user_id: str,
    entity_ids: Iterable[str],
    write_anchor: Callable[[], None],
    on_demand: bool = False,
    reset_memory: Optional[Callable[[str], None]] = None,
    briefing_entity_id: Optional[str] = None,
    briefing_entity_type: Optional[str] = None,
) -> None:
    """Schreibt den Δ-Anker und leert danach das Melde-Gedächtnis.

    Args:
        user_id: echte Nutzer-Kennung (Mandantentrennung, nie `"default"`).
        entity_ids: ALLE betroffenen Kennungen — Trip: `[trip.id]`;
            Ortsvergleich: `[f"{preset_id}:{loc.id}" for loc in locations]`
            über alle Orte des Presets, nicht nur die getriggerten (Risiko R3:
            ein still übersprungener Ort behielte sein altes Gedächtnis und
            würde nach dem nächsten Briefing nie wieder melden).
        write_anchor: schreibt den Δ-Anker. Die Fehlerbehandlung liegt beim
            Aufrufer — beide Bestandspfade sind dort bereits fail-soft.
        on_demand: True ⇒ es passiert NICHTS, weder Anker noch Reset
            (Ad-hoc-Abruf/Handversand ist gegenüber beiden Zuständen
            read-only, Issue #1007).
        reset_memory: optionaler Haken für Aufrufer, die den Reset über eine
            eigene, überschreibbare Naht führen — genau ein Fall: der Trip mit
            `TripReportSchedulerService._reset_alert_state_after_briefing`
            (seit #816 (B) Bestandsverhalten, das AC-27 unverändert lassen
            muss). Diese Naht delegiert ihrerseits an `reset_alert_memory()`,
            es gibt also nur EINE Reset-Fassung. Ohne Angabe wird
            `reset_alert_memory()` direkt gerufen.
        briefing_entity_id/briefing_entity_type: Kennung, unter der der
            Briefing-Zeitstempel fortgeschrieben wird (#1461 S3b-1). Das ist
            die PROTOKOLL-Kennung, die im Compare-Fall von `entity_ids`
            abweicht (dort `preset_id` statt `f"{preset_id}:{loc.id}"`).
            Ohne Angabe wird nichts fortgeschrieben (Bestandsaufrufer).
    """
    if on_demand:
        return

    # Vor dem Anker: ein fehlgeschlagener Snapshot-Write darf den Zeitpunkt
    # nicht verschlucken — sonst zeigte das naechste Briefing dieselben
    # Vorfaelle erneut.
    if briefing_entity_id and briefing_entity_type:
        record_briefing_sent(
            user_id=user_id, entity_id=briefing_entity_id,
            entity_type=briefing_entity_type,
        )

    write_anchor()

    for entity_id in entity_ids:
        if reset_memory is not None:
            reset_memory(entity_id)
        else:
            reset_alert_memory(user_id=user_id, entity_id=entity_id)


def record_official_alerts_reported(
    *, user_id: str, entity_id: str, alerts: list,
) -> None:
    """Vermerkt amtliche Warnungen als 'im Briefing gemeldet' — DIE geteilte
    Schreib-Logik fürs Melde-Gedächtnis (`official_alert:`-Namensraum).

    Issue #1614 Teil 1: verhindert, dass eine bereits im Trip-Briefing
    gezeigte, unveränderte amtliche Warnung bis zu 15 Minuten später vom
    unabhängigen Alarm-Checker nochmal als eigene Nachricht verschickt wird.

    Übernommen aus `TripAlertService._record_official_alert_state` — DIE
    geteilte Fassung, `_record_official_alert_state` delegiert seit dem
    Refactor hierher (Verhalten unverändert, siehe AC-5).

    Fail-soft bei leerer `alerts`-Liste: No-Op.
    """
    if not alerts:
        return
    from output.renderers.alert.official_alerts import official_alert_state_key
    from services.alert_state import AlertStateService

    state_svc = AlertStateService(user_id=user_id)
    state = state_svc.load(entity_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    for a in alerts:
        key = official_alert_state_key(a)
        state[key] = {"last_reported_value": float(a.level), "reported_at": now_iso}
    state_svc.save(entity_id, state)


def reset_alert_memory(*, user_id: str, entity_id: str) -> None:
    """DER Reset-Weg für das Melde-Gedächtnis — Trip UND Ortsvergleich.

    Einzige Fassung im Repo (Issue #1467 S2 AG5, PO: „Verwende zwingend den
    gleichen Code"). `TripReportSchedulerService._reset_alert_state_after_briefing`
    ist nur noch eine überschreibbare Naht, die hierher delegiert.

    Fail-soft je Kennung: ein Fehler bei EINER Kennung darf die übrigen nicht
    verhindern (Risiko R3 — ein still übersprungener Ort behielte sein altes
    Gedächtnis und würde nach dem nächsten Briefing nie wieder melden). Die
    Warnung nennt Kennung UND Ausnahmetyp, damit ein echter Programmfehler
    auffindbar bleibt, statt still als „nichts zu tun" durchzugehen.
    """
    from services.alert_state import AlertStateService

    try:
        AlertStateService(user_id=user_id).reset(entity_id)
    except Exception as e:
        logger.warning(
            "Failed to reset alert_state for %s: %s: %s", entity_id, type(e).__name__, e
        )
