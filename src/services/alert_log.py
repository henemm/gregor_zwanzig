"""Geteilte Schreibfunktion fuer das Alarm-Protokoll (`alert_log.json`).

Issue #1459, Epic #1458 Scheibe 1.
SPEC: docs/specs/modules/feat_1459_alert_protokoll.md

Das Protokoll haelt jetzt zusaetzlich fest, WORUM es ging: die Wettergroesse
als **Register-Paar** (`metric_id` + Auswertung aus `app.metric_catalog`, O1),
die Gefahrenart amtlicher Warnungen als eigenes Feld `hazards`, den Ausloese-
Grund `reason` und die Kanal-Aufschluesselung (zugestellt / nicht zugestellt
mit Begruendung).

Seit #1467 S1 traegt jeder Eintrag GENAU EINE Kennung: `entity_id` plus das
Typfeld `entity_type` (`"trip"` | `"compare"`). Die frueheren Doppelfelder
`trip_id`/`preset_id` — von denen immer eins leer war — werden nicht mehr
geschrieben. Bestandsdateien bleiben unangetastet; Go setzt beim LESEN
`entity_id := trip_id` und `entity_type := "trip"`, wenn die neuen Felder
fehlen (`internal/store/log.go LoadAlertLog()`).

Zwei harte Nebenbedingungen bestimmen den Aufbau:

* **D1** — EIN Eintrag je Meldung, Kanaele als Listen INNERHALB des Eintrags.
  `internal/store/log.go AlertCountByEntity()` zaehlt Eintraege, nicht Kanaele.
* **D4** — komplett fehlgeschlagene Zustellungen landen im zweiten Top-Level-
  Schluessel `not_delivered`, den Go nie liest. Cockpit-Kachel und
  Archiv-Statistik aendern sich fuer Bestandstouren dadurch um keine Zahl.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.loader import get_data_dir
from app.metric_catalog import metric_and_aggregation_for_field

logger = logging.getLogger(__name__)

# O2 -- Gruende einer Nicht-Zustellung. Im JSON bewusst freie Strings statt
# eines geschlossenen Enums: der kuenftige Grund "unter der Kanal-Schwelle"
# (#1461) kommt additiv dazu, ohne Schema-Migration. QUIET_HOURS/DAILY_LIMIT/
# COOLDOWN sind in dieser Scheibe dokumentiert, aber noch von keinem Aufrufer
# gesetzt (O3: der Ausloeser ist zum Gate-Zeitpunkt noch nicht bekannt).
REASON_CHANNEL_DISABLED = "channel_disabled"
REASON_DELIVERY_FAILED = "delivery_failed"
REASON_QUIET_HOURS = "quiet_hours"
REASON_DAILY_LIMIT = "daily_limit"
REASON_COOLDOWN = "cooldown"

# Ausloeser der Meldung selbst (`reason` des Eintrags).
REASON_FORECAST_CHANGE = "forecast_change"
REASON_NOWCAST = "nowcast"
REASON_OFFICIAL_ALERT = "official_alert"

_ALL_CHANNELS = ("email", "telegram", "sms")


def _norm_pairs(pairs: Iterable) -> list[tuple[str, str]]:
    """Register-Paare dedupliziert und stabil sortiert; `None` faellt weg
    (fail-soft: eine nicht aufloesbare Groesse laesst den Alarm-Lauf laufen)."""
    return sorted({tuple(p) for p in pairs if p is not None})


def register_pairs_from_changes(changes) -> list[tuple[str, str]]:
    """Vorhersage-Aenderungen -> Register-Paare.

    `WeatherChange.metric` ist an allen erzeugenden Stellen bereits ein
    `SegmentWeatherSummary`-Feldname (O1, gemessen in
    `weather_change_detection.py`) -- eine einzige Aufloesungsregel genuegt.
    """
    return _norm_pairs(
        metric_and_aggregation_for_field(c.metric) for c in changes or []
    )


def register_pairs_from_corridor_hits(hits) -> list[tuple[str, str]]:
    """Grenzwert-Treffer -> Register-Paare, ueber BEIDE Korridor-Namensraeume.

    `CorridorHit.metric` kann aus dem alten `AlertMetric`-Namensraum oder aus
    dem Compare-Katalog stammen; `resolve_corridor_summary_field()` (S2a-
    Baustein) vereinheitlicht beide auf den Summary-Feldnamen.
    """
    from services.corridor_threshold import resolve_corridor_summary_field

    fields = [resolve_corridor_summary_field(h.metric) for h in hits or []]
    return _norm_pairs(
        metric_and_aggregation_for_field(f) for f in fields if f
    )


def register_pairs_for_nowcast(is_convective) -> list[tuple[str, str]]:
    """Radar-Nowcast -> Register-Paar; kein Feldname noetig (O1).

    Nimmt einen einzelnen Wahrheitswert (Tour-Radar) ODER eine Folge davon
    (Vergleichs-Radar, mehrere Orte gleichzeitig -- gemischt konvektiv/nicht
    ergibt dann BEIDE Paare).
    """
    flags = [is_convective] if isinstance(is_convective, bool) else list(is_convective)
    return _norm_pairs(
        ("thunder", "max") if flag else ("precipitation", "sum") for flag in flags
    )


def hazards_from_official_alerts(alerts) -> list[str]:
    """Amtliche Warnungen -> Gefahrenarten (eigenes Vokabular, s. O1)."""
    return sorted({a.hazard for a in alerts or [] if a.hazard})


def _channels_not_sent(effective: set[str], delivered: list[str]) -> list[dict]:
    """Je nicht zugestelltem Kanal ein Grund: war er eingeschaltet, ist er
    technisch gescheitert; war er aus, hat der Nutzer ihn abgeschaltet."""
    return [
        {
            "channel": channel,
            "reason": (
                REASON_DELIVERY_FAILED if channel in effective
                else REASON_CHANNEL_DISABLED
            ),
        }
        for channel in _ALL_CHANNELS if channel not in delivered
    ]


def append_entry(
    user_id: str,
    *,
    entity_id: str,
    entity_type: str,
    changes_count: int,
    severity: str,
    metrics: Iterable = (),
    hazards: Iterable = (),
    reason: str,
    effective_channels: Iterable[str],
    sent_channels: Iterable[str],
    reachable_channels: Optional[Iterable[str]] = None,
) -> None:
    """Haengt GENAU EINEN Eintrag an das Alarm-Protokoll des Nutzers an.

    `entity_id` + `entity_type` sind PFLICHT und ohne Vorgabewert (#1467 S1):
    eine vergessene Aufrufstelle soll knallen statt still einen Eintrag ohne
    Kennung zu schreiben.

    Wird an jeder Aufrufstelle einmal nach dem Versandversuch gerufen -- egal
    ob er gelang. Die Ziel-Liste entscheidet diese Funktion selbst (O3/D4):

    * `effective_channels` leer -> gar kein Eintrag (der Nutzer hat Alarme
      bewusst abgeschaltet; ein Eintrag waere Rauschen ohne Erkenntniswert).
    * mindestens ein Kanal ERREICHBAR -> `entries`.
    * kein Kanal erreichbar -> `not_delivered` (fuer Go unsichtbar, veraendert
      also weder Cockpit-Kachel noch Archiv-Statistik).

    Massgeblich fuer die Ziel-Liste ist damit EXAKT das heutige Kriterium des
    Bestands (`NotificationResult.sent`: mindestens ein konfigurierter Kanal
    war erreichbar), NICHT der Zustellerfolg -- der Bestand loggt nach
    Best-Effort-Semantik ausdruecklich auch dann, wenn der Transport auf einem
    erreichbaren Kanal scheitert (Anti-Pattern #656). `entries` bleibt fuer
    Bestandstouren dadurch bit-identisch: wo heute geschrieben wird, wird
    weiter geschrieben; `not_delivered` faengt nur die Faelle, die heute
    SPURLOS verschwinden.

    `reachable_channels` traegt diese Erreichbarkeit (`result.sent_channels`);
    `sent_channels` traegt den tatsaechlichen Zustellerfolg und fuellt
    `channels_sent`/`channels_not_sent`. Ohne `reachable_channels` gilt
    `sent_channels` auch als Erreichbarkeits-Angabe (Direktaufrufer).

    Read-Modify-Write ueber die volle Datei: Alt-Eintraege ohne die neuen
    Felder bleiben unveraendert erhalten (AC-14). `metrics` und `hazards`
    werden IMMER beide serialisiert (leer, wenn nicht zutreffend) -- ein
    einheitliches Schema, in dem genau eines von beiden gefuellt ist.
    """
    effective = set(effective_channels or ())
    if not effective:
        return

    delivered = sorted({c for c in (sent_channels or ()) if c in effective})
    reachable = {
        c for c in
        (sent_channels if reachable_channels is None else reachable_channels)
        if c in effective
    }
    entry = {
        # EINE Kennung plus Typ (#1467 S1). Kein Doppelschreiben: `trip_id` und
        # `preset_id` kommen in neuen Eintraegen nicht mehr vor -- sonst erbten
        # die Folge-Scheiben genau den Zustand, den S1 beseitigt.
        "entity_id": entity_id,
        "entity_type": entity_type,
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        "changes_count": changes_count,
        "severity": severity,
        "metrics": [
            {"metric_id": metric_id, "aggregation": aggregation}
            for metric_id, aggregation in _norm_pairs(metrics)
        ],
        "hazards": sorted(set(hazards or ())),
        "reason": reason,
        "channels_sent": delivered,
        "channels_not_sent": _channels_not_sent(effective, delivered),
    }

    target = "entries" if reachable else "not_delivered"
    path = get_data_dir(user_id) / "alert_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError) as e:  # kaputte Datei darf keinen Alarm killen
        logger.warning("alert_log: %s nicht lesbar (%s) -- neu angelegt", path, e)
        data = {}
    data.setdefault("entries", [])
    data.setdefault(target, [])
    data[target].append(entry)
    path.write_text(json.dumps(data, indent=2))
