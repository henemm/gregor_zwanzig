"""Gewitter-Signalherkunft aus der Archiv-Rekonstruktion (#2181 Scheibe S2c).

Kalibrier-Abgleich gegen den Mitschnitt, Ablation der Signalherkunft (T1),
CAPE-Zeitverlauf und Ereignisfenster (T3) sowie Stufe-Niederschlag-Paarung
(T4) auf stuendlichen Archiv-Zeilen eines Punktes. Reine Funktionen: kein
Netz, kein Dateizugriff.

ADR-0025: Es entsteht KEINE zweite Gewitter-Fusion. Die Ablation ruft
``thunder_level_from_signals()``/``thunder_signal_carriers()`` aus
``output.metric_format`` mit rekonstruierten Rohwerten auf; die Schwellen
kommen vom Aufrufer (``app.model_registry``), die Stufenordnung aus
``app.thunder_scale`` — hier steht kein eigener Zahlenwert.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models import ThunderLevel
from app.thunder_scale import thunder_ordinal, union_of_max_carriers
from output.metric_format import thunder_level_from_signals, thunder_signal_carriers
from providers.openmeteo import THUNDER_CODES


def wettercode_stufe(weather_code: Optional[int]) -> Optional[ThunderLevel]:
    """Der Wettercode-Ast, wie ``OpenMeteoProvider._parse_thunder_level()``.

    ``None`` ist "keine Aussage" und darf nicht zur geprueeften Entwarnung
    ``ThunderLevel.NONE`` kollabieren (AC-8)."""
    if weather_code is None:
        return None
    return ThunderLevel.HIGH if weather_code in THUNDER_CODES else ThunderLevel.NONE


def kalibrier_abgleich_kurzvorlauf_cape(
    mitschnitt_tageswerte_primaer: dict[str, dict],
    archiv_cape_tagesmaximum: dict[str, Optional[float]],
    toleranz_jkg: float,
) -> dict[str, dict]:
    """Je Tag: liegt das Archiv-CAPE-Tagesmaximum im Toleranzband um den
    kurzvorlauf-naechsten Mitschnitt-Wert?

    ``toleranz_jkg`` ist eine Entscheidung des AUFRUFERS (empfohlen: halbe
    LOW-Sprosse der CAPE-Leiter) — kein Zahlenwert dieses Moduls. Fehlt einer
    der beiden Werte, ist der Tag "kein_vergleichswert" und traegt keine
    Differenz (AC-2)."""
    ergebnis: dict[str, dict] = {}
    for tag in sorted(set(mitschnitt_tageswerte_primaer) | set(archiv_cape_tagesmaximum)):
        mitschnitt_cape = mitschnitt_tageswerte_primaer.get(tag, {}).get("cape_max_jkg")
        archiv_cape = archiv_cape_tagesmaximum.get(tag)
        if mitschnitt_cape is None or archiv_cape is None:
            ergebnis[tag] = {"kategorie": "kein_vergleichswert", "differenz_jkg": None}
            continue
        differenz = abs(archiv_cape - mitschnitt_cape)
        ergebnis[tag] = {
            "kategorie": "im_toleranzband" if differenz <= toleranz_jkg else "abweichend",
            "differenz_jkg": differenz,
        }
    return ergebnis


def ablation_je_stunde(
    stundenzeile: dict,
    cape_ladder: tuple[float, float, float],
    lpi_thresholds: tuple[float, float, float],
) -> dict:
    """Stufe UND tragende Signale EINER Archiv-Stunde.

    Stufe und Herkunft stammen aus derselben kanonischen Fusion (ADR-0025),
    aufgerufen mit den rekonstruierten Rohwerten der Stunde. Die Blitzdichte
    ist strukturell abwesend (FR-only), nicht "null gemessen"."""
    cape_low, cape_med, cape_high = cape_ladder
    lpi_low, lpi_med, lpi_high = lpi_thresholds
    signale = (
        wettercode_stufe(stundenzeile["weather_code"]),
        None,
        stundenzeile["cape"],
        stundenzeile["lightning_potential"],
    )
    leitern = {
        "cape_threshold_jkg": cape_low,
        "cape_med_min": cape_med,
        "cape_high_min": cape_high,
        "cin_jkg": stundenzeile["convective_inhibition"],
        "lpi_low_min": lpi_low,
        "lpi_med_min": lpi_med,
        "lpi_high_min": lpi_high,
    }
    return {
        "stufe": thunder_level_from_signals(*signale, **leitern),
        "traeger": thunder_signal_carriers(*signale, **leitern),
    }


def ablation_tagesmaximum(
    stundenzeilen_tag: list[dict],
    cape_ladder: tuple[float, float, float],
    lpi_thresholds: tuple[float, float, float],
) -> dict:
    """Hoechststufe des Tages und die VEREINIGTE Traegermenge aller Stunden,
    die genau diese Stufe erreichen (AC-6) — nicht nur der ersten."""
    stunden = [ablation_je_stunde(s, cape_ladder, lpi_thresholds) for s in stundenzeilen_tag]
    stufen = [e["stufe"] for e in stunden if e["stufe"] is not None]
    paare = [(e["stufe"], e["traeger"]) for e in stunden]
    return {
        "stufe": max(stufen, key=thunder_ordinal) if stufen else None,
        "traeger": union_of_max_carriers(paare) or [],
    }


def vergleiche_ablation_mit_mitschnitt(
    ablation_tag: dict, mitschnitt_stufe: Optional[ThunderLevel],
) -> dict:
    """Stellt Ablation und Mitschnitt nebeneinander und weist ein Zurueck-
    bleiben als EIGENE Kategorie aus, statt es einem der Aeste zuzuschlagen.

    Der Radar-Override ist im Mitschnitt eingerechnet, aus der Rekonstruktion
    aber strukturell unsichtbar (Known Limitations) — ein ``False`` hier ist
    kein Fehler der Ablation."""
    return {
        "mitschnitt_stufe": mitschnitt_stufe,
        "ablation_stufe": ablation_tag["stufe"],
        "traeger": ablation_tag["traeger"],
        "ablation_erreicht_mitschnitt_stufe":
            thunder_ordinal(ablation_tag["stufe"]) >= thunder_ordinal(mitschnitt_stufe),
    }


def cape_verlauf_und_ereignisfenster(stundenzeilen_tag: list[dict]) -> dict:
    """CAPE-Zeitverlauf, CAPE-Maximum und Abstand zur ersten Ereignisstunde.

    Ohne Ereignisstunde bleiben ``erste_ereignisstunde`` und
    ``vorlauf_stunden`` ``None`` (AC-10). Es wird nur gerechnet, kein
    Sollwert geprueft."""
    sortiert = sorted(stundenzeilen_tag, key=lambda s: datetime.fromisoformat(s["time"]))
    stundenwerte = [(s["time"], s["cape"]) for s in sortiert]
    mit_cape = [p for p in stundenwerte if p[1] is not None]
    cape_maximum = max(mit_cape, key=lambda p: p[1]) if mit_cape else None
    ereignisstunden = [s["time"] for s in sortiert if s["weather_code"] in THUNDER_CODES]
    erste_ereignisstunde = ereignisstunden[0] if ereignisstunden else None
    vorlauf_stunden = None
    if erste_ereignisstunde is not None and cape_maximum is not None:
        abstand = (datetime.fromisoformat(erste_ereignisstunde)
                   - datetime.fromisoformat(cape_maximum[0]))
        vorlauf_stunden = abstand.total_seconds() / 3600
    return {
        "stundenwerte": stundenwerte,
        "cape_maximum": cape_maximum,
        "erste_ereignisstunde": erste_ereignisstunde,
        "vorlauf_stunden": vorlauf_stunden,
    }


def niederschlag_tagessumme(stundenzeilen_tag: list[dict]) -> dict:
    """Tagessummen fuer Niederschlag und Schauer aus den Archiv-Stunden."""
    return {
        "niederschlag_mm": sum(s["precipitation"] for s in stundenzeilen_tag),
        "schauer_mm": sum(s["showers"] for s in stundenzeilen_tag),
    }


def stufe_gegen_niederschlag(
    mitschnitt_tageswerte: dict[str, dict],
    archiv_niederschlag_je_tag: dict[str, dict],
) -> dict[str, dict]:
    """Je Tag NUR das rohe Tripel Stufe/Niederschlag/Schauer (AC-11).

    Kein Interpretationsfeld ("nahe null" o.ae.) — die Bewertung entsteht im
    Bericht ausserhalb des Repos. Eine fehlende Mitschnitt-Stufe bleibt
    ``None`` und kollabiert nicht zu ``ThunderLevel.NONE`` (AC-12)."""
    ergebnis: dict[str, dict] = {}
    for tag in sorted(set(mitschnitt_tageswerte) | set(archiv_niederschlag_je_tag)):
        stufe = mitschnitt_tageswerte.get(tag, {}).get("thunder_level_max")
        niederschlag = archiv_niederschlag_je_tag.get(tag, {})
        ergebnis[tag] = {
            "stufe": None if stufe is None else ThunderLevel(stufe),
            "niederschlag_mm": niederschlag.get("niederschlag_mm"),
            "schauer_mm": niederschlag.get("schauer_mm"),
        }
    return ergebnis
