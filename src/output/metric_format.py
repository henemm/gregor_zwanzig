"""Konsolidiertes Metrik-Format-Modul (Issue #1214, Scheibe 1).

SPEC: docs/specs/modules/issue_1214_metric_format_slice1_2.md

Buendelt vier reine Zugriffs-/Formatier-Funktionen als Single Source of Truth
statt der 6-8fach duplizierten Metrik-Formatierung/Ampel-Logik/Labels je
Kanal-Renderer:

- ``format_value(metric_id, value, style)`` — formatiert einen Wert anhand der
  Katalog-Definition (``decimals``, ``unit``, ``display_unit``).
- ``severity_for(metric_id, value)`` — kanonisches Ampel-Vokabular
  ``green/yellow/orange/red`` (oder ``None``) aus ``display_thresholds``.
- ``label(metric_id, style)`` — reiner Katalog-Passthrough fuer Labels.

Koexistenz-Strategie (Tech-Lead-Entscheidung, s. Spec): ``format_value`` ist
eine eigenstaendige, metric_id-gekeyte Implementierung; die bestehende,
unit-gekeyte ``metric_catalog.format_metric_value`` bleibt UNVERAENDERT
bestehen (kein Thin-Wrapper). ``severity_for`` ist bewusst eine eigenstaendige
Neuimplementierung derselben Band-Logik wie ``helpers._level_from_thresholds``
— ``helpers.ampel_level`` bleibt in dieser Scheibe unangetastet.
"""
from __future__ import annotations

from typing import Iterable, Optional

from app.metric_catalog import get_metric
from app.models import ThunderLevel

__all__ = [
    "format_value",
    "severity_for",
    "severity_from_thresholds",
    "label",
    "cloud_emoji",
    "thunder_ordinal",
    "thunder_label_value",
    "thunder_level_from_signals",
    "THUNDER_LABEL_DE",
    "max_thunder",
]

_NO_VALUE = "–"  # U+2013 EN DASH — Platzhalter bei fehlendem Wert

# Einheiten-Konvertierung fuer Metriken mit abweichender Anzeige-Einheit.
# Aktuell nur visibility (unit="m" -> display_unit="km", Faktor 1000).
_UNIT_CONVERSION: dict[tuple[str, str], float] = {
    ("m", "km"): 0.001,
}

# Suffixe ohne Trennleerzeichen (direkt an die Zahl geklebt).
_NO_SPACE_UNITS = ("°C", "%")


def format_value(metric_id: str, value: Optional[float], style: str = "plain") -> str:
    """Formatiere ``value`` fuer die Metrik ``metric_id`` im gegebenen ``style``.

    Regeln (gegen den Katalog verifiziert, s. Spec AC-1):
    - ``value is None`` -> ``"–"``.
    - Sonst: auf ``metric.decimals`` (Default 0) gerundet; ``display_unit``-
      Konvertierung (aktuell nur ``visibility``: m -> km) wird VOR dem Runden
      angewandt.
    - ``style="plain"``: Einheiten-Suffix wird angehaengt (``°C``/``%`` ohne
      Leerzeichen, alle anderen mit Leerzeichen).
    - ``style="bare"`` (Scheibe 3): reine, gerundete Zahl OHNE Einheiten-Suffix
      — fuer ``helpers.fmt_val``, wo die Einheit in der Spalten-Ueberschrift der
      Trip-Briefing-Tabelle steht, nicht in der Zelle. Rundungs-/Konvertierungs-
      Logik ist identisch zu ``style="plain"``, nur das Suffix entfaellt.

    Args:
        metric_id: Katalog-ID (z.B. "temperature", "wind", "visibility").
        value: Numerischer Wert oder None.
        style: Darstellungsstil. ``"plain"`` (mit Einheit) oder ``"bare"``
            (reine Zahl). Unbekannte Werte loesen ``ValueError`` aus (analog
            ``label()``).

    Returns:
        Formatierter String — mit Einheiten-Suffix bei ``"plain"``, ohne bei
        ``"bare"``.
    """
    if style not in ("plain", "bare"):
        raise ValueError(f"Unbekannter format-style: {style!r}")
    if value is None:
        return _NO_VALUE

    metric = get_metric(metric_id)
    decimals = metric.decimals if metric.decimals is not None else 0
    unit = metric.unit
    display_unit = metric.display_unit

    v = float(value)
    if display_unit and display_unit != unit:
        factor = _UNIT_CONVERSION.get((unit, display_unit))
        if factor is not None:
            v = v * factor
        unit = display_unit

    text = f"{v:.{decimals}f}"
    if style == "bare":
        return text
    if not unit:
        return text
    if unit in _NO_SPACE_UNITS:
        return f"{text}{unit}"
    return f"{text} {unit}"


def severity_for(metric_id: str, value: Optional[float]) -> Optional[str]:
    """Kanonisches Ampel-Band ``green/yellow/orange/red`` (oder ``None``).

    Liest ``get_metric(metric_id).display_thresholds`` und delegiert die
    reine Band-Auswertung an ``severity_from_thresholds`` (SSoT, Issue
    #1377 Scheibe A — auch ``helpers._level_from_thresholds`` nutzt sie).
    """
    thresholds = get_metric(metric_id).display_thresholds
    return severity_from_thresholds(thresholds, value)


def severity_from_thresholds(thresholds: dict, value: Optional[float]) -> Optional[str]:
    """Reine Band-Auswertung eines ``display_thresholds``-Dicts.

    Issue #1377 Scheibe A: SSoT fuer ``severity_for`` UND
    ``helpers._level_from_thresholds`` — vorher implementierten beide
    dieselbe Logik zweimal.

    Aufwaerts (Keys ``yellow``/``orange``/``red``): ``value >= red`` ->
    "red", ``>= orange`` -> "orange", ``>= yellow`` -> "yellow".
    Abwaerts/invertiert (Keys ``yellow_lt``/``orange_lt``/``red_lt``):
    ``value < red_lt`` -> "red", ``< orange_lt`` -> "orange",
    ``< yellow_lt`` -> "yellow". Fuehrt eine Metrik beide Richtungen
    (z.B. Temperatur: Hitze UND Kaelte), gewinnt die SCHAERFERE der beiden
    ermittelten Stufen. Trifft keine Grenze: "green".

    ``value is None`` -> ``None``. Fehlen ALLE SECHS Schluessel (z.B.
    "pressure": leeres ``display_thresholds``-Dict) -> ebenfalls ``None`` —
    es gibt schlicht keine Ampel fuer diese Metrik, "green" waere hier ein
    irrefuehrender impliziter Default (F001-Fix, #1214: 100m Sicht duerfte
    niemals als gruen/unbedenklich gelten).
    """
    if value is None:
        return None
    red = thresholds.get("red")
    orange = thresholds.get("orange")
    yellow = thresholds.get("yellow")
    red_lt = thresholds.get("red_lt")
    orange_lt = thresholds.get("orange_lt")
    yellow_lt = thresholds.get("yellow_lt")
    if (
        red is None and orange is None and yellow is None
        and red_lt is None and orange_lt is None and yellow_lt is None
    ):
        # Keine Schwellen in irgendeiner Richtung hinterlegt -> None statt
        # eines irrefuehrenden "green"-Defaults.
        return None

    _STAGES = ("green", "yellow", "orange", "red")

    up_level = "green"
    if red is not None and value >= red:
        up_level = "red"
    elif orange is not None and value >= orange:
        up_level = "orange"
    elif yellow is not None and value >= yellow:
        up_level = "yellow"

    down_level = "green"
    if red_lt is not None and value < red_lt:
        down_level = "red"
    elif orange_lt is not None and value < orange_lt:
        down_level = "orange"
    elif yellow_lt is not None and value < yellow_lt:
        down_level = "yellow"

    return up_level if _STAGES.index(up_level) >= _STAGES.index(down_level) else down_level


def label(metric_id: str, style: str = "label_de") -> str:
    """Reiner Katalog-Passthrough fuer Labels.

    ``style="label_de"`` -> ``metric.label_de``,
    ``style="compact_label"`` -> ``metric.compact_label``,
    ``style="col_label"`` -> ``metric.col_label``.
    """
    metric = get_metric(metric_id)
    if style == "label_de":
        return metric.label_de
    if style == "compact_label":
        return metric.compact_label
    if style == "col_label":
        return metric.col_label
    raise ValueError(f"Unbekannter label-style: {style!r}")


def cloud_emoji(pct: Optional[float]) -> str:
    """Kanonisches Wolken-Emoji (Issue #1214 Scheibe 6, PO-Entscheidung 2026-07-12).

    Skala ``<=10 ☀️ / <=30 🌤️ / <=70 ⛅ / <=90 🌥️ / >90 ☁️`` — vormals die
    Mail-Skala aus ``email/helpers.py::fmt_val``; wird mit dieser Scheibe zur
    produktweiten Wahrheit fuer alle Konsumenten (Mail, Kompakt-Zusammenfassung,
    Sonnen-Emoji-Fallback). ``None`` -> ``_NO_VALUE`` ("–"), konsistent mit
    ``format_value``. Aufrufer mit abweichender Alt-Semantik fuer ``None``
    (z.B. ``weather_metrics._cloud_pct_emoji`` -> "?") behalten ihren eigenen
    Guard VOR dem Aufruf dieser Funktion.
    """
    if pct is None:
        return _NO_VALUE
    if pct <= 10:
        return "☀️"
    if pct <= 30:
        return "🌤️"
    if pct <= 70:
        return "⛅"
    if pct <= 90:
        return "🌥️"
    return "☁️"


# Kanonische Ordnungsquelle fuer ThunderLevel (str-Enum ohne eigene Ordnung,
# app/models.py). ThunderLevel(str, Enum) hasht/vergleicht identisch zu
# seinem rohen String-Wert, daher funktioniert dieses Dict transparent auch
# mit rohen "NONE"/"LOW"/"MED"/"HIGH"-Strings als Key (day_comparison.py).
#
# Issue #1474: LOW ist additiv UNTERHALB von MED eingefuegt -- MED wandert von
# Ordinal 1 auf 2, HIGH von 2 auf 3. Jede Stelle, die diese Skala ueber eine
# rohe Zahl anspricht (statt ueber thunder_ordinal(ThunderLevel.X)), meint nach
# dieser Erweiterung etwas anderes als vorher (Spec Abschnitt 1/2).
_THUNDER_ORDER = {
    ThunderLevel.NONE: 0, ThunderLevel.LOW: 1,
    ThunderLevel.MED: 2, ThunderLevel.HIGH: 3,
}


def thunder_ordinal(level: Optional[ThunderLevel]) -> int:
    """Kanonisches Sortier-Ordinal fuer ``ThunderLevel``
    (NONE=0 < LOW=1 < MED=2 < HIGH=3).

    ``None`` sowie unbekannte Werte liefern 0. Nimmt sowohl ``ThunderLevel``-
    Instanzen als auch rohe Strings entgegen (str-Enum-Hash-Aequivalenz).
    """
    if level is None:
        return 0
    return _THUNDER_ORDER.get(level, 0)


# Render-Skala fuer ThunderLevel — zielt exakt auf
# ``src/output/tokens/metrics.LEVELS = {0:'-', 1:'L', 2:'M', 3:'H'}``.
# Issue #1474: LOW belegt endlich den bisher unerreichbaren Render-Platz 1.
# MED/HIGH behalten ihre bisherigen Render-Werte 2/3 (additiv, kein
# Render-Sprung fuer Bestandswerte, Spec AC-1).
_THUNDER_LABEL_VALUE = {
    ThunderLevel.NONE: 0, ThunderLevel.LOW: 1,
    ThunderLevel.MED: 2, ThunderLevel.HIGH: 3,
}


def thunder_label_value(level: Optional[ThunderLevel]) -> int:
    """Kanonischer Render-Wert fuer ``ThunderLevel`` (NONE=0, LOW=1, MED=2, HIGH=3).

    ``None`` sowie unbekannte Werte liefern 0. Nimmt sowohl ``ThunderLevel``-
    Instanzen als auch rohe Strings entgegen (str-Enum-Hash-Aequivalenz).

    Seit Issue #1474 sind Sortier- und Render-Skala fuer alle vier Werte
    zahlenmaessig deckungsgleich ({0,1,2,3} in beiden) — bleiben aber zwei
    separate, benannte Funktionen (ADR-0025, Entscheidung 3). Eine kuenftige
    Aenderung an einer der beiden darf sich nicht auf die andere verlassen:

    * ``thunder_ordinal()``    -> {NONE:0, LOW:1, MED:2, HIGH:3} — **Sortier-/
      Vergleichsordnung**. Nur fuer max()/Vergleiche/Peak-Ermittlung.
    * ``thunder_label_value()`` -> {NONE:0, LOW:1, MED:2, HIGH:3} — **Render-
      Skala** fuer ``tokens/metrics.LEVELS = {0:'-', 1:'L', 2:'M', 3:'H'}``. Nur
      diese Funktion darf Werte fuer ``DailyForecast.thunder_hourly`` bzw.
      ``HourlyValue.value`` auf dem SMS-Token-Pfad erzeugen.
    """
    if level is None:
        return 0
    return _THUNDER_LABEL_VALUE.get(level, 0)


# Geteilte deutsche Beschriftung (Issue #1474, "geteilte Quelle statt Kopien"
# statt fuenffach dupliziertem Label). NONE fehlt bewusst nicht -- Konsumenten
# mit abweichender NONE-Darstellung (z.B. compare_html.py "—" statt "kein")
# ueberschreiben nur diesen einen Eintrag lokal.
THUNDER_LABEL_DE: dict[ThunderLevel, str] = {
    ThunderLevel.NONE: "kein",
    ThunderLevel.LOW: "leicht",
    ThunderLevel.MED: "mittel",
    ThunderLevel.HIGH: "hoch",
}


def max_thunder(levels: Iterable[ThunderLevel]) -> ThunderLevel:
    """Liefert das hoechste ``ThunderLevel`` aus ``levels`` (kanonische Ordnung).

    Nacktes ``max()`` waere alphabetisch falsch (``"NONE" > "MED" > "LOW" > "HIGH"``).
    """
    return max(levels, key=thunder_ordinal)


# Blitzdichte-Schwellen (Blitze/km²/3h), Beleg: ECMWF Forecast User Guide
# §8.1.13 Lightning (https://confluence.ecmwf.int/spaces/FUG/pages/673550914/
# Section+8.1.13+Lightning). 0,075 ("mittel"->"schwer") ist NICHT publiziert,
# s. Spec Known Limitations.
_LIGHTNING_LOW_MIN = 0.003
_LIGHTNING_MED_MIN = 0.015
_LIGHTNING_HIGH_MIN = 0.075

def _cape_low_min_jkg() -> float:
    """CAPE-Schwelle fuer die Fusion — bewusst ENTKOPPELT von
    ``display_thresholds["cape"]`` (Anzeige-Ampel, Berg-kalibriert). Liest
    ``risk_thresholds["cape"]["medium"]`` (metric_catalog.py, bereits
    produktentschieden) direkt aus dem Katalog statt den Wert zu duplizieren
    -- dieselbe Schwelle, die bereits von der allgemeinen Risiko-Uebersicht
    (``RiskEngine._check_thunder``) genutzt wird.
    """
    return get_metric("cape").risk_thresholds["medium"]


def thunder_level_from_signals(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
) -> Optional[ThunderLevel]:
    """Fusioniert Gewittersignale zu EINEM ``ThunderLevel`` (Issue #1474 Abschnitt 3).

    Jedes Signal wird EIGENSTAENDIG uebersetzt (keine Sonderlogik fuer die
    Blitzdichte, damit ein kuenftiges Signal mit derselben Struktur andockt).
    Die Fusion liefert das schaerfste vorhandene Signal (``max_thunder()``
    ueber die NICHT-``None``-Einzelsignale). Sind ALLE drei Signale ``None``,
    liefert sie ``None`` ("keine Aussage" != "keine Gefahr", Spec AC-7).

    CAPE ist bei ``LOW`` gedeckelt und eskaliert NIE auf ``MED``/``HIGH``
    (misst Energie, kein Ereignis, Spec AC-6).
    """
    signals: list[ThunderLevel] = []

    if wettercode_level is not None:
        signals.append(wettercode_level)

    if lightning_density is not None:
        if lightning_density >= _LIGHTNING_HIGH_MIN:
            signals.append(ThunderLevel.HIGH)
        elif lightning_density >= _LIGHTNING_MED_MIN:
            signals.append(ThunderLevel.MED)
        elif lightning_density >= _LIGHTNING_LOW_MIN:
            signals.append(ThunderLevel.LOW)
        else:
            signals.append(ThunderLevel.NONE)

    if cape_jkg is not None:
        signals.append(ThunderLevel.LOW if cape_jkg >= _cape_low_min_jkg() else ThunderLevel.NONE)

    if not signals:
        return None
    return max_thunder(signals)
