"""Geteilte Schreibfunktion fuer das Alarm-Protokoll (`alert_log.json`).

Issue #1459, Epic #1458 Scheibe 1.
SPEC: docs/specs/modules/feat_1459_alert_protokoll.md

Das Protokoll haelt jetzt zusaetzlich fest, WORUM es ging: die Wettergroesse
als **Register-Paar** (`metric_id` + Auswertung aus `app.metric_catalog`, O1),
die Gefahrenart amtlicher Warnungen als eigenes Feld `hazards`, den Ausloese-
Grund `reason` und die Kanal-Aufschluesselung (zugestellt / nicht zugestellt
mit Begruendung).

Seit #1954 traegt jedes Register-Paar zusaetzlich den gemeldeten WERT:
`value` (neu) und `previous_value` (alt). Beide Schluessel sind optional und
fehlen vollstaendig, wo es keinen Messwert gibt (Radar-Nowcast) bzw. keinen
Vorwert (Grenzwert-Treffer) -- eine `0` waere dort eine erfundene Zahl. Die
Leseseite (`read_undelivered()`) bleibt bewusst zweigliedrig: der Wert
erreicht den Mail-Renderer nicht (#1503/#1474).

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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
# Issue #1461 S3b-2a: Kanal war eingeschaltet, die Meldung lag aber unter der
# dort eingestellten Dringlichkeits-Schwelle.
REASON_BELOW_THRESHOLD = "below_channel_threshold"
# Issue #1467 S4b-1: quellenuebergreifende Ereignis-Identitaet
# (`services.alert_gate.check_event_identity_gate`) hat dieselbe Meldung
# bereits ueber eine ANDERE Quelle gesehen (Nowcast <-> amtlich).
REASON_EVENT_DUPLICATE = "event_duplicate"

# Ausloeser der Meldung selbst (`reason` des Eintrags).
REASON_FORECAST_CHANGE = "forecast_change"
REASON_NOWCAST = "nowcast"
REASON_OFFICIAL_ALERT = "official_alert"

_ALL_CHANNELS = ("email", "telegram", "sms", "premium_sms")


class MetricValue(tuple):
    """Register-Paar `(metric_id, aggregation)` mit dem gemeldeten Wert (#1954).

    Bleibt ein reines 2-Tupel: Gleichheit, Hash und Sortierung richten sich
    ausschliesslich nach dem Paar. Der Wert haengt daran, gehoert aber
    ausdruecklich NICHT zum Dedupe-Schluessel (E3) -- sonst zerfiele eine
    Groesse an Fliesskomma-Rauschen (59.9 vs. 60.1) in mehrere
    Register-Eintraege.

    `rank` ist der Betrag der Aenderung und entscheidet bei mehreren Treffern
    derselben Groesse, welcher Wert ins Protokoll kommt; `segment_id` loest
    Gleichstand auf. Ein Wert von `None` bedeutet "nicht erhebbar" -- der
    Schluessel fehlt dann im JSON vollstaendig (E2), er wird nicht auf `null`
    gesetzt.
    """

    def __new__(cls, metric_id, aggregation, *, value=None,
                previous_value=None, rank=None, segment_id=""):
        paar = tuple.__new__(cls, (metric_id, aggregation))
        paar.value = value
        paar.previous_value = previous_value
        paar.rank = rank
        paar.segment_id = segment_id
        return paar


def _mit_werten(pair, **werte) -> "MetricValue | None":
    """Aufloesungs-Ergebnis (2-Tupel oder `None`) um die Werte anreichern."""
    return None if pair is None else MetricValue(pair[0], pair[1], **werte)


def _ist_extremer(neu, alt) -> bool:
    """Groesserer Betrag der Aenderung gewinnt; bei GLEICHEM Betrag entscheidet
    die kleinere `segment_id` als Textvergleich (E3).

    Das gilt auch beim Betrag 0: ein Paar ohne Wert traegt 0 und verliert
    deshalb NICHT grundsaetzlich gegen ein Paar mit Wert -- gegen ein
    wertloses Paar (Nowcast) entscheidet dann allein die `segment_id`, und die
    ist dort leer. Folgenlos ist das nur, weil wertlose und werttragende Paare
    an keiner der vier Produktiv-Aufrufstellen in DERSELBEN `metrics`-Liste
    landen (Vorhersage-Aenderung und Nowcast sind getrennte
    `append_entry()`-Aufrufe). Wer das aendert, muss diese Regel zuerst
    schaerfen."""
    r_neu = getattr(neu, "rank", None) or 0.0
    r_alt = getattr(alt, "rank", None) or 0.0
    if r_neu != r_alt:
        return r_neu > r_alt
    return str(getattr(neu, "segment_id", "")) < str(getattr(alt, "segment_id", ""))


def _norm_pairs(pairs: Iterable) -> list[tuple[str, str]]:
    """Register-Paare dedupliziert und stabil sortiert; `None` faellt weg
    (fail-soft: eine nicht aufloesbare Groesse laesst den Alarm-Lauf laufen).

    Dedupliziert wird ueber das Paar allein -- mehrere Treffer derselben
    Groesse ergeben EINEN Eintrag (AC-7), der den Wert des extremsten
    Treffers traegt (AC-18).
    """
    besten: dict[tuple[str, str], tuple] = {}
    for p in pairs or ():
        if p is None:
            continue
        schluessel = (p[0], p[1])
        vorhanden = besten.get(schluessel)
        if vorhanden is None or _ist_extremer(p, vorhanden):
            besten[schluessel] = p
    return [besten[schluessel] for schluessel in sorted(besten)]


def _metric_dict(pair) -> dict:
    """Ein Register-Paar als JSON-Dict; Wert-Schluessel nur, wenn erhebbar.

    Absenz heisst "nicht erhebbar" (E2) -- ein Radar-Nowcast hat keinen
    Messwert, ein Grenzwert-Treffer keinen Vorwert. `None` waere hier falsch:
    `json.dumps` schriebe daraus `null`, also eine Aussage ueber einen Wert,
    den es nicht gibt.
    """
    eintrag = {"metric_id": pair[0], "aggregation": pair[1]}
    for schluessel in ("value", "previous_value"):
        wert = getattr(pair, schluessel, None)
        if wert is not None:
            eintrag[schluessel] = wert
    return eintrag


def register_pairs_from_changes(changes) -> list[tuple[str, str]]:
    """Vorhersage-Aenderungen -> Register-Paare MIT neuem und altem Wert.

    `WeatherChange.metric` ist an allen erzeugenden Stellen bereits ein
    `SegmentWeatherSummary`-Feldname (O1, gemessen in
    `weather_change_detection.py`) -- eine einzige Aufloesungsregel genuegt.
    """
    return _norm_pairs(
        _mit_werten(
            metric_and_aggregation_for_field(c.metric),
            value=c.new_value,
            previous_value=c.old_value,
            rank=abs(c.delta or 0.0),
            segment_id=c.segment_id,
        )
        for c in changes or []
    )


def register_pairs_from_corridor_hits(hits) -> list[tuple[str, str]]:
    """Grenzwert-Treffer -> Register-Paare, ueber BEIDE Korridor-Namensraeume.

    `CorridorHit.metric` kann aus dem alten `AlertMetric`-Namensraum oder aus
    dem Compare-Katalog stammen; `resolve_corridor_summary_field()` (S2a-
    Baustein) vereinheitlicht beide auf den Summary-Feldnamen.

    Der gerissene Wert kommt mit (E4), ein Vorwert NICHT: ein Korridor-Treffer
    hat keinen -- und die Schwelle (`bound`) ist Konfiguration, kein Messwert.
    """
    from services.corridor_threshold import resolve_corridor_summary_field

    felder = [(h, resolve_corridor_summary_field(h.metric)) for h in hits or []]
    return _norm_pairs(
        _mit_werten(
            metric_and_aggregation_for_field(f),
            value=h.value,
            rank=abs(h.value or 0.0),
            segment_id=h.segment_id,
        )
        for h, f in felder if f
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


def _channels_not_sent(
    effective: set[str], delivered: list[str], below_threshold: "set[str] | None" = None,
    blocked_reason_codes: "dict[str, str] | None" = None,
) -> list[dict]:
    """Je nicht zugestelltem Kanal ein Grund: ein spezifischer, gebuchter
    Sperrgrund (D5, #1701) geht VOR der Kanal-Schwelle (#1461 S3b-2a), die
    wiederum VOR technisch gescheitert geht, sonst wie bisher: eingeschaltet
    und weder below-threshold noch zugestellt -> technisch gescheitert; war
    er aus, hat der Nutzer ihn abgeschaltet."""
    below_threshold = below_threshold or set()
    blocked_reason_codes = blocked_reason_codes or {}
    result = []
    for channel in _ALL_CHANNELS:
        if channel in delivered:
            continue
        if channel in blocked_reason_codes:
            reason = blocked_reason_codes[channel]
        elif channel in below_threshold:
            reason = REASON_BELOW_THRESHOLD
        elif channel in effective:
            reason = REASON_DELIVERY_FAILED
        else:
            reason = REASON_CHANNEL_DISABLED
        result.append({"channel": channel, "reason": reason})
    return result


def capture_kwargs_from_alerts(alerts: Iterable) -> dict:
    """Herkunfts-Argumente fuer ``append_entry()`` aus den TATSAECHLICH
    versendeten amtlichen Warnungen (Issue #1944) -- geteilter Baustein
    beider Flaechen (Trip und Ortsvergleich, Paritaet #1533).

    Regel ueber den entdoppelten ``capture_id``-Werten:

    * keine Kennung -> ``{}`` (Bestandsverhalten, kein Herkunfts-Feld),
    * genau eine -> ``{"capture_id": ...}`` (bestehendes skalares Feld),
    * mehrere -> ``{"capture_ids": [...]}`` sortiert; das skalare Feld bleibt
      BEWUSST ungesetzt. Eine willkuerliche Auswahl wuerde genau die Frage
      wieder verschliessen, die dieses Ticket beantworten soll (#1929).

    Fail-open (AC-7): laesst sich die Herkunft nicht auswerten, entsteht kein
    Feld -- ein Fehler in der Beweisaufnahme darf den Alarm nie verhindern."""
    try:
        ids = {a.capture_id for a in alerts if a.capture_id is not None}
        if len(ids) == 1:
            return {"capture_id": ids.pop()}
        if ids:
            return {"capture_ids": sorted(ids)}
    except Exception as e:
        logger.warning(
            "alert_log: Herkunfts-Kennungen nicht auswertbar (%s) -- der "
            "Eintrag entsteht ohne Herkunfts-Feld.", e,
        )
    return {}


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
    below_threshold_channels: Optional[Iterable[str]] = None,
    blocked_reason_codes: Optional[dict[str, str]] = None,
    capture_id: Optional[str] = None,
    capture_ids: Optional[Iterable[str]] = None,
    is_addendum: bool = False,
    addendum_reported_at: Optional[str] = None,
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

    `below_threshold_channels` (#1461 S3b-2a): Teilmenge von
    `effective_channels`, die wegen der Kanal-Schwelle NICHT angesteuert
    wurde. `effective_channels` bleibt dabei das ROHE, unveraenderte Opt-in
    des Nutzers -- die Schwelle filtert nur den tatsaechlichen Versand
    (Aufrufer), nie das, was hier protokolliert wird (rote Linie #638).

    `is_addendum`/`addendum_reported_at` (#2018): Markierung einer Meldung,
    die als NACHTRAG zu einer bereits zugestellten amtlichen Warnung
    zugestellt wurde, plus deren Meldezeitpunkt (ISO-String). Beide Felder
    entstehen NUR bei `is_addendum=True` -- Normalfaelle und Alt-Eintraege
    bleiben schema-identisch (Muster `capture_id`).

    `blocked_reason_codes` (D5, #1701): Kanal -> spezifische Sperr-Kennung
    (z.B. `premium_sms_no_reply_address`), aus
    `NotificationResult.blocked_reason_codes` durchgereicht. Ersetzt fuer den
    betroffenen Kanal den generischen `REASON_DELIVERY_FAILED` in
    `channels_not_sent` -- ein Kanal OHNE eigenen Eintrag bleibt unveraendert
    beim generischen Grund (Bestandsinvariante).

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
        "metrics": [_metric_dict(pair) for pair in _norm_pairs(metrics)],
        "hazards": sorted(set(hazards or ())),
        "reason": reason,
        "channels_sent": delivered,
        "channels_not_sent": _channels_not_sent(
            effective, delivered, set(below_threshold_channels or ()),
            blocked_reason_codes,
        ),
    }
    if capture_id is not None:  # additiv (#1948), Alt-Eintraege unveraendert
        entry["capture_id"] = capture_id
    if capture_ids:  # additiv (#1944): Versand aus MEHREREN Mitschnitten
        entry["capture_ids"] = sorted(set(capture_ids))
    if is_addendum:  # additiv (#2018): Nachtrag statt zweitem Voll-Alarm
        entry["is_addendum"] = True
        entry["addendum_reported_at"] = addendum_reported_at

    _append(user_id, "entries" if reachable else "not_delivered", entry)


def _append(user_id: str, target: str, entry: dict) -> None:
    """Read-Modify-Write der ganzen Datei; Alt-Eintraege bleiben unangetastet."""
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


def append_suppressed_entry(
    user_id: str,
    *,
    entity_id: str,
    entity_type: str,
    reason: str,
    gate_reason: str,
    effective_channels: Iterable[str],
    capture_id: Optional[str] = None,
) -> None:
    """Haengt GENAU EINEN Eintrag fuer eine VOR dem Versand abgewiesene
    Meldung an (#1467 S3, Aenderung (d)).

    Zweiter, schlanker Schreibpfad neben `append_entry()`: der ist auf
    tatsaechliche Zustellversuche zugeschnitten (`changes_count`, `severity`,
    Kanal-Aufschluesselung NACH dem Versand). Bei einer Abweisung durch die
    Freigabe-Steuerung ist zu diesem Zeitpunkt strukturell noch nichts davon
    bekannt — die Erkennung laeuft erst nach dem Gate.

    Ziel-Liste ist immer `not_delivered`: kein Kanal wurde erreicht. Go liest
    diese Liste nicht (D4), Cockpit-Kachel und Archiv-Statistik aendern sich
    dadurch um keine Zahl. Jeder eingeschaltete Kanal bekommt denselben
    `gate_reason` als Nicht-Zustellungs-Grund; `reason` bleibt der AUSLOESER
    der Meldung (`REASON_NOWCAST`), damit die beiden Angaben nicht
    verschmelzen.

    Ohne eingeschalteten Kanal entsteht — wie in `append_entry()` — gar kein
    Eintrag: der Nutzer hat Alarme dort bewusst abgeschaltet.

    Geltungsbereich sind ausschliesslich die beiden Nowcast-Pfade. Der
    Vorhersage-Aenderungsalarm und die amtliche Warnung protokollieren ihre
    Unterdrueckungen weiterhin NICHT (offene Luecke O3 in
    `feat_1459_alert_protokoll.md`).

    `gate_reason` ist PFLICHT und muss gefuellt sein: ein leerer Wert wuerde
    von `_missed_channels()` beim LESEN still zu `REASON_DELIVERY_FAILED`
    umgedeutet — das Protokoll behauptete dann "Zustellung fehlgeschlagen", wo
    in Wahrheit gar keine Sperre vorlag. Genau das hebt den Zweck dieser
    Aenderung auf (das Protokoll soll wahrheitsgemaess beantworten, WARUM kein
    Alarm kam), deshalb scheitert die Funktion hier laut statt still etwas
    Falsches zu schreiben. Der Fall ist heute unerreichbar — beide Aufrufer
    rufen nur bei `GateResult.allowed is False`, und dann traegt `reason`
    immer eine der drei Konstanten; die Zusicherung steht an der Stelle, an
    der sie WIRKT, nicht nur dort, wo sie heute zufaellig eingehalten wird.
    Ein lautes Scheitern ist an dieser Stelle vertretbar: sie wird
    ausschliesslich betreten, wenn ohnehin kein Alarm rausgeht.
    """
    if not gate_reason or not str(gate_reason).strip():
        raise ValueError(
            "append_suppressed_entry: gate_reason ist leer "
            f"({gate_reason!r}) — ein Unterdrueckungs-Eintrag ohne Grund wird "
            "beim Lesen still als 'Zustellung fehlgeschlagen' gedeutet und "
            f"wuerde das Protokoll fuer {entity_type}/{entity_id} verfaelschen."
        )
    effective = set(effective_channels or ())
    if not effective:
        return
    entry = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        # Zum Gate-Zeitpunkt ist noch nichts erkannt: keine Aenderungszahl,
        # kein Schweregrad, keine Groesse. Die Felder bleiben im Schema
        # (einheitlicher Aufbau), aber leer statt erfunden.
        "changes_count": 0,
        "severity": "",
        "metrics": [],
        "hazards": [],
        "reason": reason,
        "channels_sent": [],
        "channels_not_sent": [
            {"channel": channel, "reason": gate_reason}
            for channel in _ALL_CHANNELS if channel in effective
        ],
    }
    if capture_id is not None:  # additiv (#1948), siehe append_entry()
        entry["capture_id"] = capture_id
    _append(user_id, "not_delivered", entry)


# ---------------------------------------------------------------------------
# Lesen: was hat einen Kanal NICHT erreicht (#1461 S3b-1)
# ---------------------------------------------------------------------------

# Ein Alarm-Lauf erzeugt bis zu drei Eintraege (Vorhersage-Aenderung, Radar,
# amtliche Warnung sind drei getrennte `append_entry`-Aufrufe, Millisekunden
# auseinander). Fuer den Nutzer ist das EIN Vorfall -- zusammengefasst wird
# beim LESEN, nie im Protokoll (sonst kippt D4).
DEDUP_WINDOW = timedelta(minutes=2)


@dataclass(frozen=True)
class UndeliveredIncident:
    """Eine Nutzer-Meldung, die mindestens einen Kanal nicht erreicht hat."""
    at: datetime
    channels: tuple[str, ...]
    reasons: tuple[str, ...]
    metrics: tuple[tuple[str, str], ...]
    hazards: tuple[str, ...]
    trigger: str


def _parse_ts(raw: object) -> Optional[datetime]:
    try:
        ts = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _missed_channels(entry: dict) -> tuple[list[str], set[str]]:
    """Kanaele + Gruende, die als Vorfall zaehlen.

    `channel_disabled` faellt heraus: ein vom Nutzer ABGESCHALTETER Kanal ist
    keine fehlgeschlagene Zustellung. `_channels_not_sent()` schreibt ihn bei
    JEDEM erfolgreichen Alarm mit; wer ihn mitzaehlt, zeigt jedem
    Ein-Kanal-Nutzer in JEDEM Briefing einen Abschnitt (Spec v1.1, AC-3).
    Alle uebrigen Gruende -- auch die spaeter hinzukommenden (`quiet_hours`,
    `daily_limit`, `cooldown`, "unter der Kanal-Schwelle" aus S3b-2) -- sind
    ausdruecklich Vorfaelle.
    """
    channels, reasons = [], set()
    for item in entry.get("channels_not_sent") or []:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason")
        channel = item.get("channel")
        if not channel or reason == REASON_CHANNEL_DISABLED:
            continue
        channels.append(channel)
        reasons.add(reason or REASON_DELIVERY_FAILED)
    return channels, reasons


def read_undelivered(
    user_id: str,
    *,
    entity_id: str,
    entity_type: str,
    since: Optional[datetime] = None,
) -> list[UndeliveredIncident]:
    """Meldungen EINER Kennung, die seit `since` einen Kanal nicht erreichten.

    Reine Lesefunktion -- an `entries`/`not_delivered` wird nichts geschrieben
    (Zusicherung D4: Cockpit-Kachel und Archiv-Statistik bleiben zahlgleich).
    Beide Quellen: `entries[*].channels_not_sent` (Teilausfall) und die ganzen
    Eintraege unter `not_delivered` (Totalausfall).

    Fail-soft wie die Schreibseite: unlesbare Datei ⇒ leeres Ergebnis plus
    Warnung, nie eine Ausnahme ins Briefing. `since=None` liest ohne
    Zeitgrenze; die Entscheidung "ohne Anker gar nichts" trifft der Aufrufer
    (`alert_briefing_anchor.undelivered_since_last_briefing`).

    Rueckgabe: juengster Vorfall zuerst.
    """
    path = get_data_dir(user_id) / "alert_log.json"
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError) as e:
        logger.warning("alert_log: %s nicht lesbar (%s) -- kein Briefing-Hinweis", path, e)
        return []
    if not isinstance(data, dict):
        return []

    roh: list[tuple[datetime, list[str], set[str], dict]] = []
    for key in ("entries", "not_delivered"):
        for entry in data.get(key) or []:
            if not isinstance(entry, dict):
                continue
            # Alt-Eintraege ohne die #1467-S1-Felder wie Go lesen
            # (`internal/store/log.go LoadAlertLog()`).
            if (entry.get("entity_id") or entry.get("trip_id")) != entity_id:
                continue
            if (entry.get("entity_type") or "trip") != entity_type:
                continue
            at = _parse_ts(entry.get("sent_at"))
            if at is None or (since is not None and at < since):
                continue
            channels, reasons = _missed_channels(entry)
            if channels:
                roh.append((at, channels, reasons, entry))

    roh.sort(key=lambda r: r[0], reverse=True)

    vorfaelle: list[UndeliveredIncident] = []
    gruppen: list[dict] = []
    for at, channels, reasons, entry in roh:
        if gruppen and gruppen[-1]["at"] - at <= DEDUP_WINDOW:
            g = gruppen[-1]
        else:
            g = {"at": at, "channels": [], "reasons": set(),
                 "metrics": [], "hazards": [], "trigger": entry.get("reason") or ""}
            gruppen.append(g)
        g["channels"] += [c for c in channels if c not in g["channels"]]
        g["reasons"] |= reasons
        g["metrics"] += [
            (m.get("metric_id"), m.get("aggregation"))
            for m in entry.get("metrics") or []
            if (m.get("metric_id"), m.get("aggregation")) not in g["metrics"]
        ]
        g["hazards"] += [h for h in entry.get("hazards") or [] if h not in g["hazards"]]

    for g in gruppen:
        vorfaelle.append(UndeliveredIncident(
            at=g["at"],
            channels=tuple(c for c in _ALL_CHANNELS if c in g["channels"]),
            reasons=tuple(sorted(g["reasons"])),
            metrics=tuple(g["metrics"]),
            hazards=tuple(g["hazards"]),
            trigger=g["trigger"],
        ))
    return vorfaelle
