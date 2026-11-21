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

from dataclasses import dataclass
from html import escape as _html_escape
from typing import Iterable, Optional

from app.metric_catalog import get_metric
from app.models import PrecipType, ThunderLevel

# Beide ThunderLevel-Skalen wohnen seit der #1196-Nacharbeit in der
# Domaenenschicht (app/thunder_scale.py) -- der Zeitplaner braucht sie, darf
# aber keine Darstellungsschicht importieren (Waechter #1365). Re-Export hier
# haelt alle bestehenden `from output.metric_format import ...`-Stellen
# gueltig; die privaten Dicts _THUNDER_ORDER/_THUNDER_LABEL_VALUE ziehen mit.
#
# Issue #1680 S5b: `union_of_max_carriers` (S2) und `thunder_signal_label`/
# `THUNDER_SIGNAL_LABEL_DE` (S1) sind aus DEMSELBEN Grund nachgezogen -- die
# Gewitter-Vorschau baut ihren Herkunfts-Zusatz im Zeitplaner. Der Re-Export
# bindet DIESELBEN Objekte (insbesondere DIESELBE Dict-Instanz), keine Kopie:
# eine in-place-Mutation von `THUNDER_SIGNAL_LABEL_DE` wirkt deshalb ueber
# beide Modulnamen gleich.
from app.thunder_scale import (  # noqa: F401  (Re-Export, s.o.)
    _THUNDER_LABEL_VALUE,
    _THUNDER_ORDER,
    THUNDER_LABEL_DE,
    THUNDER_SIGNAL_LABEL_DE,
    thunder_label_value,
    thunder_low_statement,
    thunder_low_statement_sentence,
    thunder_ordinal,
    thunder_signal_label,
    union_of_max_carriers,
)

__all__ = [
    "NO_VALUE",
    "format_value",
    "severity_for",
    "severity_from_thresholds",
    "escalate_pair_watch",
    "label",
    "cloud_emoji",
    "thunder_ordinal",
    "thunder_label_value",
    "thunder_level_from_signals",
    # Issue #2176: Re-Export der LOW-Aussage aus der Domaenenschicht.
    "thunder_low_statement",
    "thunder_low_statement_sentence",
    "THUNDER_LABEL_DE",
    "PRECIP_TYPE_LABEL_DE",
    "thunder_ampel_band",
    "max_thunder",
    # Issue #3260 S1b: die EINE Darstellung je Zelle.
    "Zelle",
    "darstellung",
    "stunden_marke_erlaubt",
]

# Issue #1670: EIN "kein Wert"-Platzhalter fuer Trip- UND Compare-Mail.
NO_VALUE = "–"  # U+2013 EN DASH — Platzhalter bei fehlendem Wert
_NO_VALUE = NO_VALUE  # modulinterner Alt-Name (Bestandsaufrufer unten)

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


def severity_for(metric_id: str, value: Optional[float], *, ampel: dict) -> Optional[str]:
    """Kanonisches Ampel-Band ``green/yellow/orange/red`` (oder ``None``).

    Issue #2792 S1c-1: liest die Schwellen aus dem durchgereichten,
    aufgeloesten Ampel-Objekt (``resolve_ampel(sub)``) statt aus dem Katalog.
    ``ampel`` ist Pflicht ohne Default: ein vergessenes Durchreichen soll laut
    scheitern statt still „allgemein" zu faerben. Die Band-Auswertung bleibt
    ``severity_from_thresholds`` (SSoT, Issue #1377 Scheibe A).
    """
    from app.ampel import schwellen_aus_ampel
    return severity_from_thresholds(schwellen_aus_ampel(ampel, metric_id), value)


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


# Issue #1927 Wiedereroeffnung (Spec fix_1927_risk_dot_kombi_regel S2,
# Revision v1.1): drei fest definierte, fachlich begruendete Metrik-Paare.
# Jedes Tupel-Element ist entweder ein einzelner Schluessel oder ein Tupel
# von Alternativ-Schluesseln (mind. einer davon muss "yellow" sein). Bewusst
# NICHT von den `col_key`-Namen aus metric_catalog.py abgeleitet -- eigenes,
# an dieser Stelle gepflegtes Vokabular (s. Spec Implementation Details).
# v1.1 (PO-Scope-Entscheid nach Adversary-Verdict BROKEN): das Nullgradgrenze-
# Paar (`freezing_level` ohne display_thresholds, strukturell trip-relativ)
# und die Schneehoehe-Alternative im dritten Paar (`snow_depth` ohne
# belegbare Ampel-Absolutschwelle) entfallen ersatzlos, siehe Spec Non-Goals.
_PAIR_WATCH_ESCALATIONS: tuple[tuple[object, object], ...] = (
    ("precipitation", "temperature"),
    ("thunder", ("wind", "gust")),
    ("visibility", "fresh_snow"),
)


def _side_is_yellow(severities: dict, side) -> bool:
    keys = side if isinstance(side, tuple) else (side,)
    return any(severities.get(key) == "yellow" for key in keys)


def escalate_pair_watch(severities: dict) -> Optional[str]:
    """Eskaliert eine Zeile von 'yellow' auf 'orange', wenn beide Partner
    eines der drei fest definierten Metrik-Paare gleichzeitig 'yellow' sind.

    ``severities`` ist ein Dict ``{metrik_schluessel: severity_string_oder_None}``.
    Liefert "orange" bei Treffer, sonst None -- keine weitere Eskalationsstufe
    (Spec Non-Goals, `fix_1927_risk_dot_kombi_regel.md`).
    """
    for left, right in _PAIR_WATCH_ESCALATIONS:
        if _side_is_yellow(severities, left) and _side_is_yellow(severities, right):
            return "orange"
    return None


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
    return _wolken_stufe(pct)[1]


def _wolken_stufe(pct: float) -> tuple:
    """Zeile der Katalog-Skala ``WOLKEN_STUFEN`` (#3260: EINE Skala fuer
    Wolken-Symbol und ASCII-Wortstufe)."""
    from app.metric_catalog import WOLKEN_STUFEN

    return next(s for s in WOLKEN_STUFEN if s[0] is None or pct <= s[0])


# ---------------------------------------------------------------------------
# Issue #3260 S1b: Ampelpunkt-Markup und die EINE Darstellungsfunktion
# ---------------------------------------------------------------------------

# Issue #759: 4-stufiger Ampelpunkt fuer Wind/Boen/Regen/Regenwahrscheinlichkeit.
# Issue #1222: Kreis-Emojis durch gestylte CSS-Dots ersetzt (kein Emoji mehr
# in E-Mails). Palette (fill, ring) je Level, Ring an _risk_dot (html.py)
# angelehnt, um Gelb/Amber erweitert. Fix #1801 S2: groesserer Punktabstand
# orange<->rot (Karminrot statt Violett, PO-Entscheid 2026-08-14).
# #3260: zog aus ``email/helpers.py`` hierher; helpers re-exportiert.
_AMPEL_DOT_COLORS = {
    "green":  ("#15803d", "rgba(21,128,61,0.18)"),
    "yellow": ("#d69500", "rgba(214,149,0,0.20)"),
    "orange": ("#d4530a", "rgba(212,83,10,0.20)"),
    "red":    ("#a8104a", "rgba(168,16,74,0.22)"),
}

# Issue #1475 Nachbesserung (Punkt 2b): Farbe des zweiten, aeusseren Rings, der
# ausschliesslich Hagel kennzeichnet. Bewusst Violett (G_ALERT_L4) — die einzige
# Farbe der Palette, die in KEINER Ampelstufe vorkommt.
_HAIL_RING_COLOR = "rgba(109,40,217,0.55)"


def _ampel_dot_css(level: str, hail: bool = False) -> str:
    """CSS-Dot (Ring-Optik) fuer eine Ampelstufe — Vorbild `_risk_dot` (html.py).

    Issue #1475 Nachbesserung: bei ``hail=True`` bekommt der Punkt EINEN
    zusaetzlichen, aeusseren box-shadow-Layer (Doppelring) — rein deskriptives
    Hagel-Kennzeichen, ohne Handlungsempfehlung (ADR-0007). Bei ``hail=False``
    bleibt die Ausgabe zeichengleich zum bisherigen Stand.
    """
    fill, ring = _AMPEL_DOT_COLORS[level]
    shadow = f"0 0 0 3px {ring}"
    if hail:
        shadow = f"{shadow}, 0 0 0 6px {_HAIL_RING_COLOR}"
    return (
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{fill};'
        f'box-shadow:{shadow};"></span>'
    )


@dataclass(frozen=True)
class Zelle:
    """Eine dargestellte Zelle (Spec feat_3260_s1b Nr. 2)."""

    text: str               # Klartext-/Telegram-/ASCII-taugliche Fassung
    html: str               # fertiger HTML-Zellinhalt (escaped Text oder Punkt)
    form: str               # zahl | wort | symbol | ampelpunkt | kompass
    stufe: Optional[str]    # green|yellow|orange|red aus der Abo-Ampel


def _als_zahl(wert) -> Optional[float]:
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def _stufe(metric_id: str, wert, *, ampel: Optional[dict]) -> Optional[str]:
    """Ampelstufe aus der Abo-Ampel; Gewitter ueber ``thunder_color``. Ohne
    Ampel (``None``, reine Textfassung) keine Stufe."""
    from app.ampel import thunder_color

    if ampel is None:
        return None
    if metric_id == "thunder":
        try:
            return thunder_color(None if wert is None else ThunderLevel(wert), ampel)
        except ValueError:
            return None
    return severity_for(metric_id, _als_zahl(wert), ampel=ampel)


def _wortskalen() -> dict:
    """Name aus ``metric_catalog.WORTSKALA`` -> Wortfunktion ``(wert, lang)``."""
    from i18n import t
    from services import weather_metrics as wm

    from app.thunder_scale import thunder_label

    return {
        "wind_strength": lambda v, lang: wm.format_wind_strength(_als_zahl(v), lang=lang),
        "precip_intensity": lambda v, lang: wm.format_precip_intensity(_als_zahl(v), lang=lang),
        "precip_daily_sum": lambda v, lang: wm.format_precip_daily_sum(_als_zahl(v), lang=lang),
        "rain_probability": lambda v, lang: wm.format_rain_probability_scale(
            _als_zahl(v), lang=lang),
        "sunshine": lambda v, lang: wm.format_sunshine_scale(_als_zahl(v), lang=lang),
        "wolken": lambda v, lang: t(_wolken_stufe(_als_zahl(v))[2], lang),
        "gewitter": lambda v, lang: thunder_label(v, lang=lang),
    }


def _wort(metric_id: str, wert, wertart: str, lang: str) -> str:
    from app.metric_catalog import WORTSKALA

    skalen = WORTSKALA.get(metric_id, {})
    name = skalen.get(wertart) or next(iter(skalen.values()), None)
    if name is None:
        return _zahl_text(metric_id, wert)
    return _wortskalen()[name](wert, lang)


def _symbol(metric_id: str, wert, wertart: str, lang: str) -> str:
    from app.metric_catalog import WORTSKALA

    if WORTSKALA.get(metric_id, {}).get(wertart) == "wolken":
        return cloud_emoji(_als_zahl(wert))
    from services.weather_metrics import get_weather_emoji

    return get_weather_emoji(is_day=None, dni_wm2=_als_zahl(wert), wmo_code=None, cloud_pct=None)


def _kompass(metric_id: str, wert, wertart: str, lang: str) -> str:
    from utils.geo import degrees_to_compass

    return degrees_to_compass(_als_zahl(wert)) or str(wert)


def _zahl_text(metric_id: str, wert, wertart: str = "stunde", lang: str = "de") -> str:
    zahl = _als_zahl(wert)
    return str(wert) if zahl is None else format_value(metric_id, zahl, style="plain")


_FORM_TEXT = {"zahl": _zahl_text, "wort": _wort, "symbol": _symbol, "kompass": _kompass,
              "ampelpunkt": _wort}


def darstellung(
    metric_id: str, wert, *, stelle: str, ausgabeart: str, fmt: Optional[str],
    ampel: Optional[dict], wertart: str = "stunde", lang: str = "de",
) -> Zelle:
    """Die EINE Darstellung eines Metrik-Werts (ADR-0127 Nr. 2, #3260 S1b).

    Die Form kommt allein aus ``metric_catalog.form(metric_id, stelle,
    ausgabeart, fmt, wertart)`` (Sonnenstunden: Stundenwert Symbol, Tageswert
    Wort), die Stufe aus der uebergebenen Abo-Ampel (``resolve_ampel``), das
    Wort aus ``WORTSKALA`` je Wertart. Kein Aufrufer waehlt die Form selbst;
    ``Zelle.text`` traegt bei einem Ampelpunkt die Wortstufe (Textfassung
    derselben Aussage).

    ``ampel=None`` ist nur fuer reine Textfassungen ohne Stufe erlaubt
    (``Zelle.stufe`` bleibt ``None``). Verlangt der Katalog an dieser Stelle
    einen Ampelpunkt und fehlt die Ampel, scheitert der Aufruf absichtlich laut
    mit ``ValueError`` -- kein stiller Rueckfall auf eine Vorgabe-Ampel und
    keine farblose Zelle (ADR-0106, „kein stilles allgemein")."""
    from app.metric_catalog import form as katalog_form

    form = katalog_form(metric_id, stelle, ausgabeart, fmt, wertart)
    if form == "ampelpunkt" and ampel is None:
        raise ValueError(f"darstellung({metric_id!r}): Ampelpunkt braucht die Abo-Ampel")  # i18n-log
    if wert is None:
        return Zelle(_NO_VALUE, _NO_VALUE, form, None)
    stufe = _stufe(metric_id, wert, ampel=ampel)
    text = _FORM_TEXT[form](metric_id, wert, wertart, lang)
    if form == "ampelpunkt":
        html = _ampel_dot_css(stufe) if stufe else _NO_VALUE
    else:
        html = _html_escape(text)
    return Zelle(text, html, form, stufe)


def stunden_marke_erlaubt(metric_id: object) -> bool:
    """Traegt Einfach im Orte-Telegram die Stunden-Marke ``@h``? (Katalog
    ``STUNDEN_MARKE``)."""
    from app.metric_catalog import STUNDEN_MARKE

    return metric_id in STUNDEN_MARKE




# THUNDER_LABEL_DE liegt seit #2176 in `app/thunder_scale.py` (Domaenenschicht)
# und wird oben unveraendert re-exportiert -- `thunder_low_statement()` haengt
# das Stufenwort an und darf dafuer keine Darstellungsschicht importieren.


# Geteilte deutsche Beschriftung der Niederschlagsart (Issue #2134, analog zu
# THUNDER_LABEL_DE). Der Ad-hoc-Abruf einer Groesse mit ``dp_field ==
# "precip_type"`` liefert sonst den internen Enum-Bezeichner (``SNOW``), der
# fuer einen Wanderer keine Aussage ist. Schluessel ist das Enum-Mitglied;
# weil ``PrecipType`` ein ``str``-Enum mit Name == Wert ist, findet auch ein
# roher String aus dem Snapshot-Roundtrip ("SNOW") seinen Eintrag.
PRECIP_TYPE_LABEL_DE: dict[PrecipType, str] = {
    PrecipType.RAIN: "Regen",
    PrecipType.SNOW: "Schnee",
    PrecipType.MIXED: "Schneeregen",
    PrecipType.FREEZING_RAIN: "gefrierender Regen",
}


# Issue #3139: EINE Wortquelle fuer die Niederschlagsart in Trip-Mail,
# Telegram und Orts-Vergleich (Katalog ``vergleich.niederschlagsart.*``).
_PRECIP_TYPE_KEYS = frozenset({"RAIN", "SNOW", "MIXED", "FREEZING_RAIN"})


def precip_type_label(v, *, lang: str = "de") -> str:
    """Niederschlagsart (Enum oder roher String) -> Wort in ``lang``.

    ``None`` oder unbekannter Wert liefert ``NO_VALUE``."""
    if v is None:
        return NO_VALUE
    key = (v.value if hasattr(v, "value") else str(v)).upper()
    if key not in _PRECIP_TYPE_KEYS:
        return NO_VALUE
    from i18n import t
    return t(f"vergleich.niederschlagsart.{key.lower()}", lang)


# Einzige Quelle Stufe -> Ampelband (Issue #1491, ADR-0025). Konsumenten
# (Trip-Stundentabelle und Ortsvergleich) leiten Kreisfarbe UND Zell-Toenung
# aus dieser einen Zuordnung ab statt eigener Kopien.
_THUNDER_AMPEL_BAND: dict[ThunderLevel, str] = {
    ThunderLevel.NONE: "green",
    ThunderLevel.LOW: "yellow",
    ThunderLevel.MED: "orange",
    ThunderLevel.HIGH: "red",
}


def thunder_ampel_band(level: Optional[ThunderLevel]) -> Optional[str]:
    """Ordnet eine ``ThunderLevel``-Stufe ihrem Ampelband zu
    (``green``/``yellow``/``orange``/``red``).

    ``None`` (keine Gewitteraussage) liefert ``None`` — Aufrufer zeigen dafuer
    einen Strich, NIEMALS ein Ampelband ("keine Aussage" != "keine Gefahr",
    Issue #1491 AC-1).
    """
    if level is None:
        return None
    return _THUNDER_AMPEL_BAND.get(level)


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

# Blitzpotenzial-Schwellen: seit Issue #1679 region-abhaengig, siehe
# `app.model_registry.LPI_THRESHOLDS_JKG`/`lpi_thresholds_jkg()`. Keine
# globale Konstante mehr hier -- ein Aufrufer ohne aufgeloeste Region
# bekommt bewusst KEIN Signal statt einer falschen Schwelle.


def _thunder_level_from_ladder(
    value: float, low_min: float, med_min: float, high_min: float,
) -> ThunderLevel:
    """Uebersetzt EINEN Messwert anhand einer Drei-Schwellen-Leiter in ein
    ThunderLevel (>=high_min -> HIGH, >=med_min -> MED, >=low_min -> LOW,
    sonst NONE). Geteilt von Blitzdichte UND Blitzpotenzial (Issue #1474c,
    DRY-Pflicht #1481) -- jedes Signal bringt nur seine eigenen vier
    Schwellenwerte mit, die Leiter selbst existiert genau einmal, damit ein
    kuenftiges fuenftes Signal mit derselben Struktur andockt, ohne eine
    weitere Kopie der if/elif-Kette zu erzeugen."""
    if value >= high_min:
        return ThunderLevel.HIGH
    if value >= med_min:
        return ThunderLevel.MED
    if value >= low_min:
        return ThunderLevel.LOW
    return ThunderLevel.NONE


# Umkehrung der kanonischen Ordnung (thunder_scale.thunder_ordinal) --
# abgeleitet statt handgeschrieben, damit eine kuenftige fuenfte Stufe nicht
# an zwei Stellen gepflegt werden muss.
_THUNDER_JE_ORDINAL = {thunder_ordinal(stufe): stufe for stufe in ThunderLevel}


def _gedaempft_durch_cin(
    basis: ThunderLevel, cin_jkg: Optional[float]
) -> ThunderLevel:
    """Daempft eine CAPE-Stufe anhand der Konvektionshemmung CIN (#1679;
    Baender auf ICON umgestellt mit #1896).

    Drei Baender aus der ICON-naechsten publizierten Quelle -- ECMWF Technical
    Memorandum No. 852 (Groenemeijer, Pucik, Tsonevsky, Bechtold 2019), Fig. 2:
    *"CIN (hatched areas where CIN > 50 J/kg, contour at CIN = 100 J/kg)"*.
    Betrag < 50 laesst die Leiter voll zaehlen, bis EINSCHLIESSLICH 100 faellt
    genau eine Stufe, darueber greift die STAERKERE von "eine Stufe" und
    "Deckel LOW"; der Grenzwert gehoert immer ins staerker daempfende Band.
    Das oberste Band ist bewusst kein reiner Deckel: ein absoluter Deckel
    neben einem relativen Band ist an der 100er-Naht nicht monoton -- eine
    Basis LOW faellt bei 100 auf NONE und wuerde bei MEHR Hemmung wieder auf
    LOW angehoben (Adversary-Befund F001). Ein Band "CAPE traegt gar nichts
    bei" gibt es NICHT -- dafuer kennt die Quelle keinen Stuetzpunkt.

    Warum 50 nur EINE Stufe nimmt statt auf LOW zu deckeln: TM 852 rechnet
    pseudoadiabatisch, ICON reversibel, und reversible CIN ist betragsmaessig
    GROESSER (TM 852 Abschnitt 4.3.3; Murdzek, Markowski, Richardson, Kumjian
    2021, J. Atmos. Sci. 78(10)) -- ohne festen Umrechnungsfaktor. Die
    1:1-Lesart wuerde zu frueh daempfen; dem begegnet die STRUKTUR der Kaskade.

    Unbekanntes CIN (``None``, strukturell bei Meteo-France/AROME; ebenso der
    DWD-Fehlwert -999,9, VOR dieser Funktion zu ``None`` gefiltert,
    `dwd.py:206`/`:240`, `dwd_eu.py:261`) faellt auf die Notbremse "hoechstens
    LOW" -- NICHT auf "kein Deckel": eine fehlende Hemmungsangabe ist keine
    schwache Hemmung.

    Vorzeichen ist MODELLABHAENGIG, GRIB2 (Parameter 0/7/7 der WMO-Registry)
    legt keines fest. Der DWD (ICON-D2/ICON-EU) liefert ``cin_ml`` POSITIV:
    `src/atm_phy_nwp/mo_opt_nwp_diagnostics.f90:3957-3958`, ``! make CIN
    positive`` gefolgt von ``ABS(...)``; GFS/US-Modelle liefern negativ.
    Deshalb vergleicht diese Funktion den BETRAG (Issue #1760).

    🔴 Verbleibende Einschraenkung (#1896, loest die des #1760 ab): naechste
    belegte Quelle, KEINE ICON-Eichung. TM 852 teilt mit ICON die 50-hPa-
    Mischschicht und den Verzicht auf Entrainment, nicht die Adiabatik --
    Richtung belegt (s.o.), Betrag unbekannt; "ICON rechnet reversibel" fusst
    allein auf TM 852 Table 1. Eigene Eichung fruehestens nach der Saison 2027
    (Archivluecke, s. `fix_1896_cin_baender_icon.md`).

    CIN ist Ausloese-Filter, kein Schweremass (Rasmussen & Blanchard 1998) --
    diese Funktion daempft deshalb ausschliesslich und hebt nie an.
    """
    if cin_jkg is None:
        return min(basis, ThunderLevel.LOW, key=thunder_ordinal)
    betrag = abs(cin_jkg)
    if betrag < 50:
        return basis
    eine_stufe = _THUNDER_JE_ORDINAL[max(thunder_ordinal(basis) - 1, 0)]
    if betrag <= 100:
        return eine_stufe
    return min(eine_stufe, ThunderLevel.LOW, key=thunder_ordinal)


def _signal_levels(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
    lightning_potential_jkg: Optional[float] = None,
    *,
    cape_threshold_jkg: Optional[float],
    cape_med_min: Optional[float],
    cape_high_min: Optional[float],
    cin_jkg: Optional[float],
    lpi_low_min: Optional[float],
    lpi_med_min: Optional[float],
    lpi_high_min: Optional[float],
) -> dict[str, ThunderLevel]:
    """Die EINZELsignale der Fusion, je Zutat unter festem Schluessel
    (Issue #1680 S1). Ein Signal, das nichts beitraegt (Wert fehlt ODER seine
    Leiter ist unkalibriert), erscheint GAR NICHT -- "keine Aussage" ist kein
    Eintrag mit Stufe ``NONE``.

    Ausgelagert aus ``thunder_level_from_signals()``, damit die Stufe UND ihre
    Herkunft aus EINER Rechnung stammen (keine zweite Fusionsregel neben der
    kanonischen, ADR-0025).
    """
    levels: dict[str, ThunderLevel] = {}

    if wettercode_level is not None:
        levels["wettercode"] = wettercode_level

    if lightning_density is not None:
        levels["blitzdichte"] = _thunder_level_from_ladder(
            lightning_density, _LIGHTNING_LOW_MIN, _LIGHTNING_MED_MIN, _LIGHTNING_HIGH_MIN,
        )

    if (cape_jkg is not None
            and cape_threshold_jkg is not None
            and cape_med_min is not None
            and cape_high_min is not None):
        levels["cape"] = _gedaempft_durch_cin(
            _thunder_level_from_ladder(
                cape_jkg, cape_threshold_jkg, cape_med_min, cape_high_min,
            ),
            cin_jkg,
        )

    if (lightning_potential_jkg is not None
            and lpi_low_min is not None
            and lpi_med_min is not None
            and lpi_high_min is not None):
        levels["blitzpotenzial"] = _thunder_level_from_ladder(
            lightning_potential_jkg, lpi_low_min, lpi_med_min, lpi_high_min,
        )

    return levels


def thunder_signal_carriers(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
    lightning_potential_jkg: Optional[float] = None,
    *,
    cape_threshold_jkg: Optional[float],
    cape_med_min: Optional[float],
    cape_high_min: Optional[float],
    cin_jkg: Optional[float],
    lpi_low_min: Optional[float],
    lpi_med_min: Optional[float],
    lpi_high_min: Optional[float],
) -> list[str]:
    """Die Zutaten, die die fusionierte Stufe TRAGEN (Issue #1680 S1).

    Dieselben Argumente wie ``thunder_level_from_signals()`` -- absichtlich
    eine zweite Funktion statt eines Rueckgabetyp-Wechsels, damit die Signatur
    der Fusion unveraendert bleibt.

    Genannt wird JEDE Zutat, die die Hoechststufe erreicht (PO-Entscheidung
    (ii)): es wird kein Gewinner gekuert, die interne Pruefreihenfolge ist
    damit keine Produktaussage. ``NONE`` liefert eine LEERE Liste -- "kein
    Gewitter" hat keine Herkunft ("— · CAPE" waere ein Widerspruch, Spec AC-3).
    """
    levels = _signal_levels(
        wettercode_level, lightning_density, cape_jkg, lightning_potential_jkg,
        cape_threshold_jkg=cape_threshold_jkg, cape_med_min=cape_med_min,
        cape_high_min=cape_high_min, cin_jkg=cin_jkg, lpi_low_min=lpi_low_min,
        lpi_med_min=lpi_med_min, lpi_high_min=lpi_high_min,
    )
    if not levels:
        return []
    top = max_thunder(levels.values())
    if top == ThunderLevel.NONE:
        return []
    return [name for name, stufe in levels.items() if stufe == top]


def thunder_level_from_signals(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
    lightning_potential_jkg: Optional[float] = None,
    *,
    cape_threshold_jkg: Optional[float],
    cape_med_min: Optional[float],
    cape_high_min: Optional[float],
    cin_jkg: Optional[float],
    lpi_low_min: Optional[float],
    lpi_med_min: Optional[float],
    lpi_high_min: Optional[float],
) -> Optional[ThunderLevel]:
    """Fusioniert Gewittersignale zu EINEM ``ThunderLevel`` (Issue #1474 Abschnitt 3,
    erweitert um Issue #1474c, #1592 C1).

    Jedes Signal wird EIGENSTAENDIG uebersetzt (keine Sonderlogik fuer die
    Blitzdichte, damit ein kuenftiges Signal mit derselben Struktur andockt).
    Die Fusion liefert das schaerfste vorhandene Signal (``max_thunder()``
    ueber die NICHT-``None``-Einzelsignale). Sind ALLE vier Signale ``None``,
    liefert sie ``None`` ("keine Aussage" != "keine Gefahr", Spec AC-7).

    ``cape_threshold_jkg`` ist die geeichte, modell-/gebietsabhaengige
    Schwelle (``app.model_registry.cape_threshold_jkg()``) -- KEYWORD-ONLY
    OHNE DEFAULT (Issue #1592 C1): ein Aufrufer, der die Modell-Herkunft
    nicht aufloest und den Parameter vergisst, bricht mit ``TypeError``
    statt still auf Bestandsverhalten zurueckzufallen (kein Anschein von
    "geprueft", wo nichts geprueft wurde). Ist sie ``None`` (Herkunft
    unbekannt ODER keine Kalibrierung fuer die Kombination), traegt CAPE
    KEIN Signal zur Fusion bei -- unabhaengig von seinem Wert ("keine
    Aussage" statt "geprueft, unauffaellig", Spec Abschnitt 3).

    Seit Issue #1679 (CIN-Teil) laeuft CAPE ueber die dreisprossige Leiter
    ``cape_threshold_jkg``/``cape_med_min``/``cape_high_min``
    (``model_registry.cape_ladder_thresholds_jkg()``) und wird anschliessend
    durch die Konvektionshemmung ``cin_jkg`` gedaempft
    (``_gedaempft_durch_cin()``). Alle drei sind ebenso KEYWORD-ONLY OHNE
    DEFAULT; fehlt EINE der drei Sprossen, traegt CAPE KEIN Signal bei --
    dieselbe Alles-oder-nichts-Regel wie beim Blitzpotenzial, kein stiller
    Rueckfall auf eine binaere Ersatzpruefung.

    Damit ist die fruehere pauschale Deckelung "CAPE erreicht hoechstens
    ``LOW``, eskaliert NIE" (Issue #1474, ``feat_1474`` AC-6) auf die beiden
    CIN-Baender "grosser Deckel" und "unbekannt" eingeschraenkt: bei
    schwacher oder moderater Hemmung erreicht CAPE jetzt ``MED``/``HIGH``.

    Das Blitzpotenzial (DWD ICON-D2/ICON-EU LPI, J/kg) ist das vierte Signal
    seit Issue #1474c -- eigene Schwellenleiter, weil es eine andere Groesse
    auf einer anderen Skala ist als die Blitzdichte (#1419 Abs. 3.1,
    ADR-0025). Seit Issue #1679 kommt diese Leiter gebietsabhaengig aus
    ``app.model_registry.lpi_thresholds_jkg()`` und wird als
    ``lpi_low_min``/``lpi_med_min``/``lpi_high_min`` hereingereicht --
    KEYWORD-ONLY OHNE DEFAULT, exakt wie ``cape_threshold_jkg``. Ist auch
    nur eine der drei ``None`` (Gebiet unbekannt ODER keine Kalibrierung,
    z.B. FR), traegt das Blitzpotenzial KEIN Signal zur Fusion bei.

    Issue #1680 S1: die Einzelsignale entstehen seither in ``_signal_levels()``
    -- gleiche Regeln, gleicher Rueckgabewert, nur zusaetzlich unter ihrem
    Signalnamen abrufbar (``thunder_signal_carriers()``).
    """
    signals = _signal_levels(
        wettercode_level, lightning_density, cape_jkg, lightning_potential_jkg,
        cape_threshold_jkg=cape_threshold_jkg, cape_med_min=cape_med_min,
        cape_high_min=cape_high_min, cin_jkg=cin_jkg, lpi_low_min=lpi_low_min,
        lpi_med_min=lpi_med_min, lpi_high_min=lpi_high_min,
    )
    if not signals:
        return None
    return max_thunder(signals.values())


# ---------------------------------------------------------------------------
# Hagel-Kennzeichen (#1475 S5a, Epic #1419)
#
# BEWUSST getrennt von der Gewitterstufe: Hagel ist ein dreiwertiges Flag
# (ja/unbekannt/nein), keine vierstufige Leiter — deshalb KEIN Andocken an
# `_thunder_level_from_ladder` und KEIN Eingang in `thunder_level_from_signals`
# (Spec AC-3).
# ---------------------------------------------------------------------------

def hail_priority(values: Iterable[Optional[bool]]) -> Optional[bool]:
    """Aggregiert Hagel-Kennzeichen nach der Prioritaet ja > unbekannt > nein.

    Erwartet die ROHEN (nicht vorgefilterten) Werte — ein blosses
    ``any()``/``max()`` waere bei einer Mischung aus ``True``/``None``/``False``
    falsch (Spec Known Limitations Punkt 3). Eine leere Liste liefert ``None``
    ("keine Aussage", nicht "nein").
    """
    vals = list(values)
    if any(v is True for v in vals):
        return True
    if any(v is None for v in vals):
        return None
    if vals:
        return False
    return None


# `format_hail_note` wohnt seit #2205 in `app/thunder_scale.py` (Domaenen-
# schicht): der Nacht-Halbsatz der Gewitter-Vorschau (`app/day_window.py`,
# vom Zeitplaner aufgerufen) braucht denselben Wortlaut. Re-Export haelt alle
# bestehenden `from output.metric_format import format_hail_note` gueltig.
from app.thunder_scale import format_hail_note  # noqa: E402,F401
