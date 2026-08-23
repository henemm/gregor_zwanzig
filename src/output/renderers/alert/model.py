"""Kanonisches Alert-Datenmodell + reine Helfer (Issue #917, ADR-0011).

`AlertMessage` ist kanonisch: das reservierte `source`-Feld erlaubt dem
Radar-Pfad (#919) ohne Modell-Bruch zu konvergieren.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — nur fuer Typpruefung
    from services.rain_extent import RainZone


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
    # Issue #2036: additiv, Default aus. `True` NUR, wenn `km_from`/`km_to`
    # aus echter GPX-Wegstrecke stammen (`TripSegment.distance_measured`).
    # Erst dann darf die Ortsangabe die km-Spanne statt der Segmentnummer
    # zeigen -- eine aus Luftlinie geschaetzte Zahl nie (AC-13).
    km_measured: bool = False
    # --- Issue #2020 Scheibe 2: Zeitangaben tragen ihren Tag ---------------
    # Alle additiv und defaultet -> im unveraenderten Normalfall (Versandtag,
    # bevorstehender Zeitpunkt, Nicht-Niederschlags-Metrik) byte-identisch.
    # GERECHNET wird in der Projektion aus der Referenzzeit `now_utc`
    # (`day_offset()`), der Renderer setzt nur die Worte -- Muster #2009.
    # Kalendertage zwischen Versandtag und `occurred_at` (0 = selber Tag,
    # -1 = gestern, +1 = morgen).
    occurred_day_offset: int = 0
    # Liegt `occurred_at` zum Versandzeitpunkt bereits hinter uns?
    occurred_is_past: bool = False
    # DE-Wochentagskuerzel von `occurred_at` fuer die Kurzform ("Do15" statt
    # des verworfenen Zahlensuffix "15-1"); nur bei Versatz != 0 gelesen.
    occurred_weekday: str | None = None
    # --- Niederschlags-Summen-Ereignisse: die Blickrichtung nach vorn -------
    # Menge (mm), die ab dem Versandzeitpunkt im Tagesfenster noch faellt.
    # `None` = diese Metrik kennt keine Restmenge (Wind, Temperatur, ...) ->
    # der Renderer bleibt beim "staerkste Stunde"-Kopf.
    remaining_mm: float | None = None
    # "HH:MM" Ortszeit der letzten noch bevorstehenden Regenstunde des
    # Fensters; `None` = es kommt nichts mehr (ausdrueckliche Meldung, KEINE
    # Unterdrueckung -- PO-Entscheid).
    remaining_until_time: str | None = None
    remaining_until_day_offset: int = 0
    remaining_until_weekday: str | None = None
    # "HH:MM" Ortszeit des effektiven Tagesfenster-Endes (`end_hour` zaehlt
    # voll mit, ADR-0035) -- die Grenze, bis zu der die Restmenge ueberhaupt
    # blickt. Steht im "kein weiterer Regen"-Satz, damit die Aussage ihre
    # Reichweite nennt statt sie zu verschweigen.
    window_end_time: str | None = None
    window_end_day_offset: int = 0


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
    # Issue #2054: drittes Glied der Tripel-Konvention (`<name>_time` +
    # `<name>_day_offset` + `<name>_weekday`, wie `AlertEvent.occurred_*`) --
    # das DE-Wochentagskuerzel des Beginn-Zeitpunkts in ORTSZEIT, gebildet
    # dort, wo auch der Versatz entsteht. Gelesen AUSSCHLIESSLICH von der
    # Kurzform, die damit dieselbe Schreibweise fuehrt wie Abweichungsalarm
    # (#2020 S2) und amtliche Warnung (#1948 S5). `None` bei Versatz 0.
    onset_weekday: str | None = None
    # Issue #2046: additiv, optional (Muster `onset_day_offset` o.). Erwartete
    # Niederschlagsmenge (mm) der STUNDE AB DEM BEGINN — Quelle
    # `NowcastResult.onset_precip_mm`. Gelesen AUSSCHLIESSLICH vom
    # Kurznachrichten-Renderer (`_render_sms_onset`); E-Mail und
    # Telegram-Langform bleiben bei `intensity_label` als Wort. `None` (oder
    # unterhalb der Trockenschwelle) → zahlenlose Alt-Form `R@HH:MM`.
    onset_precip_mm: float | None = None
    # Issue #2036: additiv, Default aus. `True` NUR, wenn `km_from`/`km_to`
    # aus echter GPX-Wegstrecke stammen (`TripSegment.distance_measured`).
    # Erst dann darf die Ortsangabe die km-Spanne statt der Segmentnummer
    # zeigen -- eine aus Luftlinie geschaetzte Zahl nie (AC-13).
    km_measured: bool = False
    # Issue #2051 S1: additiv, optional (Muster `onset_precip_mm`/
    # `onset_day_offset` o.). Ende desselben Ereignisses als reines "HH:MM"
    # — Quelle `NowcastResult.event_end_minutes`. `None` heisst "es gibt
    # keines" (kein Beginn erkannt, keine Frames); die Ende-Angabe entfaellt
    # dann ersatzlos. Gesetzt von den BEIDEN Onset-Pfaden (Trip UND
    # Ortsvergleich-Buendel, ADR-0021) ueber die geteilte Fassung
    # `project.event_end_display`.
    event_end_time: str | None = None
    # Issue #2051 S1: Tagesbezug des Endes, analog `onset_day_offset` — aber
    # BEWUSST eigenstaendig aus dem Ende-Zeitpunkt abgeleitet und nicht vom
    # Beginn kopiert: Beginn 23:50 (Versatz 0) und Ende 00:40 (Versatz 1)
    # liegen an verschiedenen Kalendertagen.
    event_end_day_offset: int = 0
    # Issue #2054: Wochentagskuerzel des ENDE-Zeitpunkts, analog
    # `onset_weekday` -- und aus demselben Grund eigenstaendig: Beginn und
    # Ende koennen an verschiedenen Kalendertagen liegen (23:50 -> 00:40).
    event_end_weekday: str | None = None
    # Issue #2051 S1 (Spec v1.1, PO-Entscheid 2026-08-22): der R4-Waechter
    # `NowcastResult.event_ongoing_beyond_horizon` — die Frames bzw. der
    # 180-Min-Horizont sind ausgegangen, waehrend der letzte bekannte Frame
    # noch nass war. `event_end_time` traegt dann trotzdem eine BELEGTE Zahl;
    # dieses Feld waehlt nur ihre Textform: `True` → Untergrenze
    # ("Regen mindestens bis HH:MM" / " >@HH:MM"), `False` → bekanntes Ende
    # ("letzter Regen gegen HH:MM" / "@HH:MM"). Die beiden Formen sagen
    # Gegensaetzliches und duerfen nie ineinander rutschen (AC-20); deshalb
    # entscheidet AUSSCHLIESSLICH dieses Feld darueber, an EINER Stelle je
    # Textform (`_onset_end_suffix` / `_sms_onset_ende`).
    event_ongoing_beyond_horizon: bool = False
    # Issue #2050 S2b: das Ereignis laeuft zum Meldezeitpunkt BEREITS. Additiv,
    # Default aus -> der Normalfall (Ereignis liegt in der Zukunft) bleibt
    # byte-identisch. Ersetzt in jeder Textform die BEGINN-Angabe ("in 8 Min"
    # / "ab 12:15" / das `@HH:MM`-Zeittoken) durch den Zustand; die
    # ENDE-Angabe kommt unveraendert aus den `event_end_*`-Feldern oben --
    # bewusst KEIN zweites Ende-Feld daneben, sonst gaebe es zwei Wahrheiten
    # ueber denselben Zeitpunkt.
    already_running: bool = False
    # Issue #2051 S3: additiv, optional (Muster `event_end_time`/
    # `event_end_day_offset` o.). Reichweite der Quelle als reines "HH:MM"
    # -- Quelle `NowcastResult.source_reach_minutes`. `None` heisst "keine
    # Beobachtung im Fenster ODER `event_ongoing_beyond_horizon` gesetzt"
    # (E5) -- die Entscheidung ist bereits in `project.source_reach_display`
    # getroffen, der Renderer prueft nur noch auf `None`.
    source_reach_time: str | None = None
    source_reach_day_offset: int = 0
    # Issue #2051 S3: additiv, optional. Grenzzeit der Ortsschaerfe
    # (`now + LOCATION_SHARPNESS_LIMIT_MIN`) als reines "HH:MM" -- Quelle
    # `project.location_sharpness_display`. `None` heisst "weder Beginn
    # noch Ende liegen jenseits der Grenze" -- keine zweite Schwellpruefung
    # hier (sonst zwei Wahrheiten, Muster AC-20).
    location_sharpness_limit_time: str | None = None
    location_sharpness_limit_day_offset: int = 0
    # Issue #2051 S2a: raeumliche Ausdehnung des Regenereignisses entlang der
    # Reststrecke — eigenes Feld, weil `km_from`/`km_to` die Segment-Lage
    # bleiben (#2017 Known Limitation 5): zwei Bedeutungen, zwei Namen (AC-7).
    # Gesetzt NUR vom Trip-Onset-Pfad; der Ortsvergleich hat kein
    # Streckenkonzept und laesst das Feld leer (AC-15). Die km-Zahlen
    # erscheinen im Text erst, wenn `km_measured` gesetzt ist (AC-8).
    rain_zones: tuple["RainZone", ...] = ()


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
    # Issue #2036: additiv, Default aus. `True` NUR, wenn `km_from`/`km_to`
    # aus echter GPX-Wegstrecke stammen (`TripSegment.distance_measured`).
    # Erst dann darf die Ortsangabe die km-Spanne statt der Segmentnummer
    # zeigen -- eine aus Luftlinie geschaetzte Zahl nie (AC-13).
    km_measured: bool = False
    # Issue #2020 Scheibe 2: additiv, defaultet (Muster `AlertEvent` oben).
    # Tagesversatz und Vergangenheit des NEUEN Beginns (`to_time`) -- eine
    # nackte Uhrzeit sagt nicht, ob der Beginn noch bevorsteht oder laengst
    # verstrichen ist, und genau das war der Vorwurf aus #2020.
    to_day_offset: int = 0
    to_is_past: bool = False


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
    # Issue #2036 (Adversary F001): additiv, optional -- dieselbe Bauart wie
    # `AlertEvent.segment_id` (#1744 A1). OHNE sie kann der Renderer bei einer
    # unvermessenen Etappe gar keinen Ort nennen und faellt zwangslaeufig auf
    # die Luftlinien-km zurueck, genau das verbietet AC-13. Gesetzt vom
    # Trip-Korridor-Pfad (`project.to_corridor_events`); Altdaten ohne Kennung
    # behalten den km-Rueckfall (#1744 AC-7).
    segment_id: str | None = None
    # Issue #2036: additiv, Default aus. `True` NUR, wenn `km_from`/`km_to`
    # aus echter GPX-Wegstrecke stammen (`TripSegment.distance_measured`).
    # Erst dann darf die Ortsangabe die km-Spanne statt der Segmentnummer
    # zeigen -- eine aus Luftlinie geschaetzte Zahl nie (AC-13).
    km_measured: bool = False


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
    # Issue #2018: additiv, optional. Gesetzt NUR, wenn
    # `check_event_identity_gate` diese Meldung als NACHTRAG zu einer bereits
    # zugestellten AMTLICHEN Warnung einstuft. Traegt die AUSFORMULIERTE
    # Bezugszeile ("Ergaenzung zur amtlichen Warnung von 16:15") fuer E-Mail
    # und Voll-Telegram; der SMS-Renderer liest nur die Praesenz (nicht den
    # Inhalt) fuer sein Kompakt-Token -- der Satz passt nicht ins SMS-Budget.
    addendum_reference: str | None = None


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
