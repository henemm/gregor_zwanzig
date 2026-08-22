"""Diagnose-Spur gescheiterter Track-Aufloesungen (Issue #2073 Scheibe 2).

Bis hierher scheiterte die Track-Aufloesung geraeuschlos: die Etappe blieb
unvermessen, die Ortsangabe fiel auf ``Segment N`` zurueck, und den Grund --
den ``resolve_stage_track_km`` sehr wohl kennt -- warf sie weg. Bei #2070
brauchte es eine eigens beauftragte Messung, um 3 von 13 betroffenen Etappen
ueberhaupt zu finden.

Dieses Modul ist die Schreibseite des nutzerbezogenen Journals
``data/users/<user_id>/diagnostics/track_resolution_failures.jsonl`` -- eine
JSON-Zeile je Fehlschlag. Leser ist ``analyzeTrackResolutionFailures``
(``internal/scheduler/briefing_health.go``), das daraus das mit der
Ausfalldauer WACHSENDE Betreiber-Signal am Status-Endpunkt bildet
(ADR-0018: nicht kaschieren).

Bauart-Zwilling zu ``alert_briefing_anchor.record_alert_anchor_rejected``
(#1661): nutzerbezogene Ablage ueber ``get_data_dir(user_id)`` (ADR-0003,
nie global, nie ``"default"``), Pfad bei JEDEM Aufruf frisch ueber den Loader
aufgeloest (ein fest verdrahteter ``data/``-Pfad hat zuletzt die gesamte
Ueberwachung blind gemacht, #1633), und fail-soft: eine Diagnose darf den
Alarmlauf nie gefaehrden.

Das bestehende GLOBALE Journal ``enrichment_calls.jsonl`` wurde bewusst nicht
wiederverwendet -- es kennt nur systemweite Pfadnamen, nicht die einzelne
betroffene Etappe, und ein beliebiger erfolgreicher Lauf irgendeines Nutzers
haette das Signal fuer alle ueberdeckt (Spec, Abschnitt "Rationale").

SPEC: docs/specs/modules/fix_2073_s2_sichtbarer_fehlschlag.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("track_resolution_health")

_FAILURE_FILE = "track_resolution_failures.jsonl"

# Meldegrenze auf dem Abstand des BESTEN Kandidaten: nur wenn die naechstbeste
# GPX jeden Wegpunkt bis auf hoechstens 1 km trifft, gehoert sie plausibel zu
# dieser Route -- dann ist ihr Scheitern eine Nachricht. Liegt sie weiter weg,
# hat der Trip schlicht keine passende Aufzeichnung, und ein Eintrag waere
# Rauschen.
#
# Die Zahl ist gemessen, nicht geschaetzt (#2070/#2073): ein echter
# Beinahe-Treffer liegt bei 111 m, der naechste UNBETEILIGTE Kandidat im
# selben Bestand bei 4.673 m, ein fremder Trip bei > 600 km. 1 km liegt mit
# Faktor 9 ueber dem Beinahe-Treffer und Faktor 4,7 unter dem naechsten
# unbeteiligten Kandidaten sicher in der Luecke dazwischen.
FAILURE_REPORT_TOLERANCE_KM = 1.0


def fehlschlag_ist_meldewuerdig(bester_abstand_km: float) -> bool:
    """Ist ein Fehlschlag mit diesem besten Kandidatenabstand meldewuerdig?

    Die Grenze ist INKLUSIV: genau ``FAILURE_REPORT_TOLERANCE_KM`` zaehlt noch
    als "gehoert plausibel zu dieser Route". Eigene Funktion, damit der
    Grenzfall ohne Geometrie pruefbar ist (AC-14) und Regel und Aufrufpfad
    nicht zwei Fassungen derselben Schwelle tragen.
    """
    return bester_abstand_km <= FAILURE_REPORT_TOLERANCE_KM


def record_track_resolution_failure(
    *, user_id: str, trip_id: str, stage_id: str, reason: str, detail: object,
) -> None:
    """Haelt einen gescheiterten Auflösungsversuch als Diagnose-Spur fest.

    Args:
        user_id: echte Nutzer-Kennung (Mandantentrennung, nie ``"default"``).
        trip_id: Kennung des betroffenen Trips.
        stage_id: Kennung der betroffenen Etappe.
        reason: ``"no_candidate_within_tolerance"`` (bester Kandidat gehoert
            plausibel zur Route, verfehlt aber mindestens einen Wegpunkt),
            ``"ambiguous_result"`` (mehrere Kandidaten passen, liefern aber
            widerspruechliche Wegstrecken) oder ``"implausible_measurement"``
            (bereits gespeicherte Werte, aber unplausibel).
        detail: bei den ersten beiden Gruenden der gemessene Abstand bzw. die
            maximale Abweichung in METERN, sonst ein Grund-Freitext.

    Fail-soft: JEDE Ausnahme wird hier gefangen und nur geloggt. Der Fehler
    darf nicht bis zum aeusseren Faenger von ``backfill_stage_distances``
    durchschlagen -- der wuerde denselben Rueckgabewert liefern, aber die
    Ursache unter "Etappe bleibt unvermessen" begraben (AC-8).
    """
    try:
        from app.loader import get_data_dir

        path = get_data_dir(user_id) / "diagnostics" / _FAILURE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "trip_id": trip_id,
            "stage_id": stage_id,
            "reason": reason,
            "detail": detail,
        }, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as e:  # noqa: BLE001 — fail-soft, AC-8
        logger.warning(
            "Diagnose-Spur %s zur gescheiterten Track-Aufloesung (%s/%s, %s) "
            "nicht schreibbar: %s: %s",
            _FAILURE_FILE, trip_id, stage_id, reason, type(e).__name__, e,
        )
