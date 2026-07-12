"""Konsolidiertes Metrik-Format-Modul (Issue #1214, Scheibe 1).

SPEC: docs/specs/modules/issue_1214_metric_format_slice1_2.md

Buendelt vier reine Zugriffs-/Formatier-Funktionen als Single Source of Truth
statt der 6-8fach duplizierten Metrik-Formatierung/Ampel-Logik/Labels je
Kanal-Renderer:

- ``format_value(metric_id, value, style)`` — formatiert einen Wert anhand der
  Katalog-Definition (``decimals``, ``unit``, ``display_unit``).
- ``severity_for(metric_id, value)`` — kanonisches Ampel-Vokabular
  ``green/yellow/orange/red`` (oder ``None``) aus ``display_thresholds``.
- ``tone_css(level)`` — re-exportiert aus ``design_tokens`` (kanonisches
  Vokabular -> ``(bg, fg)``-Hex-Tupel).
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

# tone_css lebt in design_tokens (naeher an den uebrigen Mail-Farbkonstanten),
# wird hier nur re-exportiert, damit Konsumenten ein einziges Modul brauchen.
from src.output.renderers.email.design_tokens import tone_css

__all__ = [
    "format_value",
    "severity_for",
    "tone_css",
    "label",
    "cloud_emoji",
    "thunder_ordinal",
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

    Liest ``get_metric(metric_id).display_thresholds`` (Keys ``yellow``/
    ``orange``/``red``). ``value is None`` -> ``None``. Fehlen ALLE drei
    Standard-Keys (z.B. ``temperature``: leeres ``display_thresholds``-Dict,
    oder ``visibility``: nur der invertierte ``orange_lt``-Key, kein
    ``orange``) -> ebenfalls ``None`` — es gibt schlicht keine Standard-Ampel
    fuer diese Metrik, "green" waere hier ein irrefuehrender impliziter
    Default (F001-Fix, s. Adversary-Fund: 100m Sicht duerfte niemals als
    gruen/unbedenklich gelten). Invertierte Schwellen (niedriger = kritischer,
    aktuell nur ``visibility.orange_lt``) werden in dieser Scheibe bewusst
    NICHT unterstuetzt — das ist eine dokumentierte Known Limitation von
    Scheibe 1+2, keine stille Luecke; vollstaendige invertierte-Schwellen-
    Unterstuetzung waere mehr Scope als hier sinnvoll (Nachruestung: Scheibe 3+).

    Ansonsten absteigend: ``value >= red`` -> "red", ``>= orange`` ->
    "orange", ``>= yellow`` -> "yellow", sonst "green".

    Bewusst eigenstaendig implementiert (kein Import/Alias von
    ``helpers.ampel_level``), obwohl die Band-Logik identisch ist — die
    Konsolidierung der beiden Implementierungen ist NICHT Teil von Scheibe 1+2
    (s. Spec Known Limitations).
    """
    if value is None:
        return None
    thresholds = get_metric(metric_id).display_thresholds
    red = thresholds.get("red")
    orange = thresholds.get("orange")
    yellow = thresholds.get("yellow")
    if red is None and orange is None and yellow is None:
        # Keine Standard-Ampel-Schwellen fuer diese Metrik (leeres Dict oder
        # ausschliesslich invertierte Keys wie orange_lt) -> None statt eines
        # irrefuehrenden "green"-Defaults.
        return None
    if red is not None and value >= red:
        return "red"
    if orange is not None and value >= orange:
        return "orange"
    if yellow is not None and value >= yellow:
        return "yellow"
    return "green"


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
# app/models.py:33-37). ThunderLevel(str, Enum) hasht/vergleicht identisch zu
# seinem rohen String-Wert, daher funktioniert dieses Dict transparent auch
# mit rohen "NONE"/"MED"/"HIGH"-Strings als Key (day_comparison.py).
_THUNDER_ORDER = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}


def thunder_ordinal(level: Optional[ThunderLevel]) -> int:
    """Kanonisches Sortier-Ordinal fuer ``ThunderLevel`` (NONE=0 < MED=1 < HIGH=2).

    ``None`` sowie unbekannte Werte liefern 0. Nimmt sowohl ``ThunderLevel``-
    Instanzen als auch rohe Strings entgegen (str-Enum-Hash-Aequivalenz).
    """
    if level is None:
        return 0
    return _THUNDER_ORDER.get(level, 0)


def max_thunder(levels: Iterable[ThunderLevel]) -> ThunderLevel:
    """Liefert das hoechste ``ThunderLevel`` aus ``levels`` (kanonische Ordnung).

    Nacktes ``max()`` waere alphabetisch falsch (``"NONE" > "MED" > "HIGH"``).
    """
    return max(levels, key=thunder_ordinal)
