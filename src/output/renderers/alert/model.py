"""Kanonisches Alert-Datenmodell + reine Helfer (Issue #917, ADR-0011).

`AlertMessage` ist kanonisch: das reservierte `source`-Feld erlaubt dem
Radar-Pfad (#919) ohne Modell-Bruch zu konvergieren.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertEvent:
    """Ein einzelnes Abweichungs-Ereignis (Deviation-Art in #917)."""
    metric_id: str           # catalog metric_id (NICHT summary_field)
    value_from: float
    value_to: float
    threshold: float
    cmp: str                 # "über" | "unter" — aus Katalog je metric_id
    occurred_at: str | None  # "HH:MM"
    km_from: float
    km_to: float
    # Issue #1170: additiv, optional. Gesetzt nur bei gebündelten Mehr-Orte-
    # Alarmen (to_multi_point_alert_message) — trägt den Ortsnamen DIESES
    # Events, damit der Renderer je Datenblock den richtigen Ort zeigt statt
    # nur den kollektiven `AlertMessage.location_label`. Trip-Pfad und
    # Einzel-Ort-Pfad setzen es nie (Regressions-Invariante, AC-7).
    location_label: str | None = None
    # Issue #1744 A1: additiv, optional, Muster `location_label`. Kennung der
    # betroffenen Etappe ("1".."N" oder "Ziel") — Quelle der gemeinsamen
    # Ortssprache aller Alarmarten (`segments.format_alert_location`). Gesetzt
    # vom Trip-Abweichungspfad (`project.to_alert_message`); der Ortsvergleich
    # setzt sie nie (ein Vergleichs-Ort hat keine Etappen). `None` -> Rueckfall
    # auf die km-Spanne (AC-7).
    segment_id: str | None = None


@dataclass(frozen=True)
class OnsetEvent:
    """Ein Radar-Onset-Ereignis (Niederschlag oder Gewitter im Anmarsch)."""
    onset_minutes: int
    onset_time: str           # "HH:MM"
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    briefing_context: str | None = None  # Issue #952: 4. Datenblock-Zeile (E-Mail only)
    # Issue #1041 Slice 1a: additiv, optional, analog AlertEvent.location_label
    # (Zeile 27). Gesetzt nur bei gebündelten Mehr-Orte-Onset-Alarmen
    # (to_multi_location_onset_alert_message) — trägt den Ortsnamen DIESES
    # Events. Trip-Radar-Pfad setzt es nie (Regressions-Invariante, AC-2/AC-3).
    location_label: str | None = None
    # Issue #1744 A1: additiv, optional, analog `AlertEvent.segment_id` (o.).
    # Gesetzt vom Trip-Radar-Pfad (`RadarAlertRequest` -> `send_radar_alert`);
    # der Ortsvergleich-Radar setzt sie nie. `None` -> km-Spanne (AC-7).
    segment_id: str | None = None
    # Issue #2009: additiv, defaultet. 0 = onset_time liegt am selben
    # Kalendertag wie "jetzt", 1 = am naechsten Tag (Mitternachts-Ueberlauf
    # der ohne Datum mehrdeutigen "HH:MM"-Angabe). Byte-identisch im
    # unveraenderten Normalfall (0). Beide Onset-Pfade setzen es (Trip UND
    # Ortsvergleich-Buendel, ADR-0021).
    onset_day_offset: int = 0


@dataclass(frozen=True)
class OnsetShiftEvent:
    """Eine Beginn-Verschiebung (Issue #1468) -- eigener Render-Vertrag nach
    dem Vorbild von `CorridorEvent` (ADR-0013).

    Bewusst KEIN `AlertEvent`: dessen Werte laufen durch den Zahlen-
    Formatierer (`render._val`/`_num`, Katalog-Einheit angehaengt, Vorzeichen
    statt Richtungswort). Eine Uhrzeit erschiene dort als "15 h" und eine
    Verschiebung als "-2 h" -- beides Unfug. Die Uhrzeiten sind hier bereits
    ORTSZEIT-formatiert ("HH:MM"), die Verschiebung ist bereits Text
    ("2 h frueher"/"2 h spaeter"): die Umrechnung passiert in der
    Projektionsschicht, wo die Koordinaten bekannt sind.
    """
    metric_id: str            # catalog metric_id (NICHT summary_field)
    from_time: str            # "HH:MM" Ortszeit -- Beginn im letzten Stand
    to_time: str              # "HH:MM" Ortszeit -- Beginn im frischen Stand
    shift_text: str           # "2 h früher" | "2 h später"
    km_from: float
    km_to: float
    segment_id: str | None = None
    location_label: str | None = None


@dataclass(frozen=True)
class CorridorEvent:
    """Ein Schwellen-Treffer (Issue #1444 S1) -- eigener Render-Vertrag
    (ADR-0013): KEIN `WeatherChange`-Missbrauch mit erfundenem
    `old_value=0.0`. Kennt bewusst KEIN "vorher" -- nur den Ist-Wert gegen
    die vom Nutzer gesetzte Grenze."""
    metric_id: str           # catalog metric_id (NICHT summary_field)
    value: float              # Ist-Wert
    bound: float               # die TATSAECHLICH gerissene Grenze
    direction: str            # "above" | "below"
    occurred_at: str | None   # "HH:MM"
    km_from: float
    km_to: float
    location_label: str | None = None


@dataclass(frozen=True)
class AlertMessage:
    """Kanonische Alert-Nachricht über alle vier Kanäle."""
    trip_short: str
    stand_at: str                              # "HH:MM"
    events: tuple[AlertEvent | OnsetEvent, ...]  # ≥1 bei Deviation ODER Onset;
    # leer, wenn ausschliesslich Korridor-Treffer vorliegen (s.u.)
    source: str | None = None                  # Radar (#919): source != None → Onset-Zweig; Deviation → None
    cooldown_display: str | None = None        # Radar (#919): Pflichttext Cooldown-Hinweis
    # Issue #1169: additiv, optional. Gesetzt nur vom Compare-Punkt-Pfad
    # (to_point_alert_message) — zeigt Ortsname statt km-Spanne. Trip-Pfad
    # (to_alert_message) setzt dieses Feld NIE (Regressions-Invariante, AC-7).
    location_label: str | None = None
    # Issue #1444 S1: additiv, optional. Schwellen-Treffer desselben Laufs --
    # werden zusaetzlich zu (oder anstelle von) `events` in dieselbe Nachricht
    # gebuendelt (Muster #1088). Bestehende Aufrufer setzen dieses Feld nie
    # (Default leer, Regressions-Invariante).
    corridor_events: tuple[CorridorEvent, ...] = ()
    # Issue #1468: additiv, optional. Beginn-Verschiebungen desselben Laufs --
    # in DERSELBE Nachricht wie die Stufen-/Wert-Aenderungen (PO-Entscheid:
    # beide melden, im Text zusammenfassen, nicht zwei getrennte Nachrichten).
    # Bestehende Aufrufer setzen dieses Feld nie (Regressions-Invariante).
    onset_shift_events: tuple[OnsetShiftEvent, ...] = ()
    # Issue #1916 (AC-1..AC-4): additiv, optional. Referenz-Zeitpunkt der
    # tatsaechlich verglichenen Vergleichsbasis (Ortszeit, ggf. mit Tagesbezug
    # wie "gestern 18:03 Uhr"), NICHT der aktuelle Abrufzeitpunkt (`stand_at`).
    # `None` -> Renderer behalten den generischen Text "verglichen mit dem
    # letzten Briefing" (Regressions-Invariante, AC-5).
    reference_at: str | None = None


def direction(e: AlertEvent) -> str:
    return "up" if e.value_to >= e.value_from else "down"


def arrow(e: AlertEvent) -> str:
    return "↑" if direction(e) == "up" else "↓"


def delta_pct(e: AlertEvent) -> int | None:
    """Prozentuale Änderung. value_from==0 → definierter Sonderfall (None)."""
    if e.value_from == 0:
        return None
    return round((e.value_to - e.value_from) / e.value_from * 100)


def over_thr(e: AlertEvent) -> bool:
    # Issue #958: `threshold` ist IMMER die Δ-Auslöseschwelle (nie ein
    # Absolutwert-Referenzwert). Ein Event liegt „über Schwelle", wenn der
    # BETRAG der Änderung die Schwelle erreicht — unabhängig von `cmp` und
    # von der Richtung (siehe WeatherChange.threshold-Docstring, ADR-0013).
    return abs(e.value_to - e.value_from) >= e.threshold


def side_label(e: AlertEvent) -> str:
    return "über" if over_thr(e) else "unter"


def severity(e: AlertEvent) -> float:
    """Relative Schwellüberschreitung. threshold==0 → Sonderfall (kein Crash).

    Bei threshold==0 fehlt ein sinnvoller Schwell-Nenner; die Distanz wird daher
    durch die Werte-Magnitude normiert, damit ein 0-Schwellen-Ereignis ein echtes
    Über-Schwelle-Ereignis nicht künstlich überholt.
    """
    if e.threshold == 0:
        scale = max(abs(e.value_to), abs(e.value_from), 1.0)
        dist = (e.threshold - e.value_to) if e.cmp == "unter" else (e.value_to - e.threshold)
        return dist / scale
    if e.cmp == "über":
        return (e.value_to - e.threshold) / e.threshold
    return (e.threshold - e.value_to) / e.threshold


def km_span(events: tuple) -> tuple[float, float]:
    return (min(e.km_from for e in events), max(e.km_to for e in events))
