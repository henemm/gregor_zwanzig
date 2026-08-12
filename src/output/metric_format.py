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

# Beide ThunderLevel-Skalen wohnen seit der #1196-Nacharbeit in der
# Domaenenschicht (app/thunder_scale.py) -- der Zeitplaner braucht sie, darf
# aber keine Darstellungsschicht importieren (Waechter #1365). Re-Export hier
# haelt alle bestehenden `from output.metric_format import ...`-Stellen
# gueltig; die privaten Dicts _THUNDER_ORDER/_THUNDER_LABEL_VALUE ziehen mit.
from app.thunder_scale import (  # noqa: F401  (Re-Export, s.o.)
    _THUNDER_LABEL_VALUE,
    _THUNDER_ORDER,
    thunder_label_value,
    thunder_ordinal,
)

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
    "thunder_ampel_band",
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
    """Daempft eine CAPE-Stufe anhand der Konvektionshemmung CIN (Issue #1679).

    Vier belegte Baender (Penn State/COMET, SPC -- Gesamtkonzept 3.7 Schritt 2):
    schwacher Deckel (Betrag < 25) laesst die Leiter voll zaehlen, moderat
    (25 <= Betrag < 50) nimmt genau eine Stufe, grosser Deckel
    (50 <= Betrag <= 100) deckelt auf LOW, darueber traegt CAPE nichts mehr bei.
    Ein Grenzwert gehoert dabei immer ins staerker daempfende Band.

    Unbekanntes CIN (``None``, strukturell der Fall bei Meteo-France/AROME;
    ebenso der DWD-Fehlwert -999,9 "kein Ausloesepunkt gefunden", der VOR
    dieser Funktion zu ``None`` gefiltert wird, `dwd.py:206`/`:240`,
    `dwd_eu.py:261`) faellt auf die Bestands-Notbremse "hoechstens LOW"
    zurueck -- NICHT auf "kein Deckel": eine fehlende Hemmungsangabe ist
    keine schwache Hemmung.

    Vorzeichen der Eingabe ist MODELLABHAENGIG, GRIB2 (Parameter 0/7/7 der
    WMO-Registry) legt keines fest -- nur Name und Einheit (J/kg) sind
    standardisiert. Der DWD (ICON-D2/ICON-EU) liefert ``cin_ml`` als
    POSITIVEN Betrag: ICON-Quellcode
    `src/atm_phy_nwp/mo_opt_nwp_diagnostics.f90:3957-3958`, Kommentar
    ``! make CIN positive``, gefolgt von ``ABS(...)``. GFS/US-Modelle
    liefern dagegen negativ -- die US-Literatur (Penn State/SPC), aus der
    die vier Baender oben stammen, bezieht sich auf **MLCIN ueber 100 hPa**
    negativ gezaehlt. Deshalb vergleicht diese Funktion den BETRAG der
    Hemmung, nicht ihr Vorzeichen (Issue #1760) -- ein reiner
    Vorzeichenvergleich (``cin_jkg > -25``) waere fuer JEDEN positiven
    ICON-Wert immer wahr und die Daempfung wuerde nie feuern.

    🔴 Bekannte Einschraenkung (Issue #1760 Known Limitations): die Baender
    selbst sind fuer ICON NICHT geeicht. ICON mischt CIN ueber **50 hPa**
    (ICON-Code Z. 2701-2702, "Depth of mixed surface layer: 50hPa following
    Huntrieser, 1997"), reversibel, ohne Entrainment (ECMWF TM 852,
    Groenemeijer et al. 2019) -- eine andere Rechnung als die US-MLCIN, aus
    der -25/-50/-100/-200 stammen. Die Schwellen liegen in der richtigen
    Groessenordnung, sind aber keine ICON-Eichung (Feineichung: #1678).

    CIN ist Ausloese-Filter, kein Schweremass (Rasmussen & Blanchard 1998) --
    diese Funktion daempft deshalb ausschliesslich und hebt nie an.
    """
    if cin_jkg is None:
        return min(basis, ThunderLevel.LOW, key=thunder_ordinal)
    betrag = abs(cin_jkg)
    if betrag < 25:
        return basis
    if betrag < 50:
        return _THUNDER_JE_ORDINAL[max(thunder_ordinal(basis) - 1, 0)]
    if betrag <= 100:
        return min(basis, ThunderLevel.LOW, key=thunder_ordinal)
    return ThunderLevel.NONE


# Die vier Zutaten der Fusion, deutsch beschriftet (Issue #1680 S1). Die
# Einfuegereihenfolge in `_signal_levels()` ist zugleich die Nenn-Reihenfolge
# der Herkunft -- deterministisch, ohne zweites Sortier-Vokabular.
# NICHT zu verwechseln mit `thunder_enrichment._SIGNAL_ZU_FELD`: das ist das
# Rohwert-Routing der Quellen (`"lpi"`, `"cin_ml"`, ...), eine andere Ebene.
THUNDER_SIGNAL_LABEL_DE: dict[str, str] = {
    "wettercode": "Wettercode",
    "blitzdichte": "Blitzdichte",
    "cape": "CAPE",
    "blitzpotenzial": "Blitzpotenzial",
}


def thunder_signal_label(name: str) -> str:
    """Deutsche Beschriftung EINER Fusions-Zutat (Issue #1680 S1).

    Exakt-Treffer zuerst, sonst der rohe Name selbst -- nie ein erfundener
    Ersatztext (Muster ``official_alert_source_label``, ADR-0007). Ohne
    Heuristik-Stufe, weil die Signalmenge geschlossen ist (vier feste
    Schluessel, kein Namensraum mit Praefix-Varianten).
    """
    return THUNDER_SIGNAL_LABEL_DE.get(name, name)


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


def union_of_max_carriers(
    pairs: Iterable[tuple[Optional[ThunderLevel], Optional[list[str]]]],
) -> Optional[list[str]]:
    """Vereinigt die Traeger DERJENIGEN Paare, die die Hoechststufe erreichen
    (Issue #1680 S2).

    Die EINE Stelle, an der die Aggregationsregel
    ``"thunder_level_max_signals": "union_of_max_carriers"`` (deklariert in
    ``WeatherMetricsService.compute_basis_metrics()``) tatsaechlich gerechnet
    wird. Herausgeloest aus ``_compute_thunder_level_signals()``, damit die
    unabhaengigen Aggregationswege (Stunden, Wegpunkte, spaeter Segmente) sie
    IMPORTIEREN statt sie zu kopieren — dieselbe Fehlerklasse, gegen die #1480
    laeuft. Muster: ``hail_priority()`` unten.

    Genannt wird JEDE Zutat, die die Hoechststufe traegt (PO-Auslegung (ii),
    Scheibe 1) — es wird kein Gewinner gekuert, ein Paar unterhalb des Maximums
    steuert NICHTS bei. Dedupliziert unter Erhalt der ERSTauftrittsreihenfolge;
    da jede einzelne Traegerliste aus ``thunder_signal_carriers()`` bereits in
    der Katalogreihenfolge von ``THUNDER_SIGNAL_LABEL_DE`` steht, bleibt die
    Nennreihenfolge deterministisch — ohne zweites Sortier-Vokabular.

    ``None`` (nicht ``[]``) heisst "keine Aussage": kein Paar nennt eine Stufe
    (z.B. leere Auswahl) ODER kein Paar am Maximum nennt einen Traeger (z.B.
    ein Alt-Schnappschuss ohne das Feld). Eine Stufe ``NONE`` ist dabei eine
    ECHTE Stufe und kein Ausstiegsgrund — sie fuehrt ueber den leeren
    Traegerbestand auf ``None``, weil "kein Gewitter" keine Herkunft hat.

    Rueckgabe ist bewusst eine ``list``, NIE ein ``set``: das Ergebnis landet
    ueber ``SegmentWeatherSummary.thunder_level_max_signals`` im Wetter-
    Schnappschuss, und ein ``set`` braeche dort ``json.dumps`` — der Fehler
    wird still geschluckt, der GESAMTE Schnappschuss waere weg (#1405).
    """
    paare = list(pairs)
    stufen = [s for s, _ in paare if s is not None]
    if not stufen:
        return None
    top = max_thunder(stufen)
    traeger: list[str] = []
    for stufe, liste in paare:
        if stufe != top:
            continue
        for name in liste or []:
            if name not in traeger:
                traeger.append(name)
    return traeger or None


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


def format_hail_note(hail_flag: Optional[bool]) -> Optional[str]:
    """Der EINE gemeinsame Anzeige-Textbaustein fuer das Hagel-Kennzeichen
    (Trip-/Compare-Mail-Renderer UND ``GEWITTER``-Kommando, #1481 DRY-Pflicht).

    Rein deskriptiv, ohne Handlungsempfehlung (ADR-0007, Spec AC-8). Bei
    "unbekannt"/"nein" gibt es KEINEN Zusatztext (kein Rauschen).
    """
    if hail_flag is True:
        return "Hagel: ja"
    return None
