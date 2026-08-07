"""Klartext-Formulierung der Herkunfts-Vertretung (Issue #1492 Scheibe 2b).

SPEC: docs/specs/modules/feat_1492_s2b_fallback_sichtbarkeit.md (R1-R8)

EIN Modul, drei Verpackungen (R6): diese Datei liefert fertige Textzeilen,
die Renderer entscheiden nur noch ueber die Huelle (HTML-``div``,
Plaintext-Zeile, Telegram-Zeile). Vorher lag dieselbe Formulierung zweimal
im Code (``email/html.py`` spiegelte ``email/plain.py`` per Kommentar) —
eine dritte Kopie fuer Telegram waere ein Verstoss gegen die Projektregel
zur Code-Teilung.

Die Ablage liegt bewusst eine Ebene UEBER ``email/`` und ``narrow.py``:
Telegram importiert heute nichts aus dem E-Mail-Zweig, und das soll so
bleiben.

Der Name traegt bewusst kein ``trip_``/``compare_``-Praefix (``pendant_gate``
blockiert praefigierte Neuanlagen unter ``src/output/renderers/**``) — es ist
ohnehin kein Trip/Compare-Pendant-Fall.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - nur fuer Typpruefer
    from app.models import ForecastMeta


# --- Uebersetzung: Quellenkennung -> (Klartext, Zusatz) ---------------------
# Wertebereich gemessen an allen Schreibstellen in ``src/providers/``
# (``openmeteo.py:1055/1077/1167``, ``region_routing.py:33-36``,
# ``thunder_enrichment.py:287``). ``icon_seamless`` steht bewusst NICHT hier:
# es ist nie ein Fallback-Wert, nur ``meta.model``.
_MODELL_KLARTEXT: dict[str, Tuple[str, str]] = {
    "eu_direct": ("DWD Europa", "gröbere Auflösung"),
    "de_direct": ("DWD Deutschland", ""),
    "fr_direct": ("Météo-France", ""),
    "at_direct": ("GeoSphere Österreich", ""),
    "icon_eu": ("DWD Europa", "gröbere Auflösung"),
    "icon_d2": ("DWD Deutschland", ""),
    "meteofrance_arome": ("Météo-France", ""),
    "metno_nordic": ("MET Norway", ""),
    "ecmwf_ifs04": ("ECMWF", "gröbere Auflösung"),
}

# --- Uebersetzung: Metrikkennung -> Klartext --------------------------------
# ``fallback_metrics`` mischt ZWEI Namenssysteme (Kontext-Doc): Open-Meteo-
# Parameternamen (``OpenMeteoProvider._PARAM_TO_FIELD``, 18 Eintraege) bei
# Metrik-Luecke/Modell-5xx, Datenpunkt-Feldnamen bei Schnee- und
# Gewitter-Anreicherung. Beide sind hier abgebildet.
#
# Die Klartext-Labels sind 1:1 aus ``app/metric_catalog.py`` (``label_de``)
# uebernommen, damit derselbe Begriff im Produkt nicht zweimal verschieden
# heisst. Bewusst NICHT mechanisch daran gekoppelt: der Katalog ist mit
# Metrik-IDs geschluesselt, diese Liste mit Parameter-/Feldnamen — die
# Bruecke waere eine eigene, fehleranfaellige Abbildung (Spec, Known
# Limitations).
_METRIK_KLARTEXT: dict[str, str] = {
    "temperature_2m": "Temperatur",
    "apparent_temperature": "gefühlte Temperatur",
    "relative_humidity_2m": "Luftfeuchtigkeit",
    "dewpoint_2m": "Taupunkt",
    "pressure_msl": "Luftdruck",
    "cloud_cover": "Bewölkung",
    "cloud_cover_low": "Tiefe Wolken",
    "cloud_cover_mid": "Mittelhohe Wolken",
    "cloud_cover_high": "Hohe Wolken",
    "wind_speed_10m": "Wind",
    "wind_direction_10m": "Windrichtung",
    "wind_gusts_10m": "Böen",
    "precipitation": "Niederschlag",
    "precipitation_probability": "Niederschlagswahrscheinlichkeit",
    "visibility": "Sicht",
    "cape": "Gewitterenergie",
    "freezing_level_height": "0°C-Grenze",
    "uv_index": "UV-Index",
    "weather_code": "Wetterlage",
    "snow_depth": "Schneehöhe",
    "swe_tot": "Wasseräquivalent Schnee",
    # Gewitter-Feldnamen: nur der Vollstaendigkeit halber uebersetzt. Sie
    # erscheinen wegen R4 NIE in der Wetterzeile — sie loesen die
    # Gewitterzeile aus.
    "lightning_density_per_km2_3h": "Blitzdichte",
    "lightning_potential_lpi_jkg": "Blitzpotenzial",
    "hail_potential_grau_gsp": "Hagelsignal",
}

_GEWITTER_OHNE_QUELLE = "Gewitterdaten von einer Ersatzquelle (gröbere Auflösung)"


def _gewitter_felder() -> Optional[frozenset]:
    """Die Gewitter-Feldnamen aus der EINZIGEN Quelle der Wahrheit (R1).

    Bewusst kein Hartkodieren: waechst ``_SIGNAL_ZU_FELD`` um eine vierte
    Gewittergroesse, erkennt diese Funktion sie automatisch. Der Import liegt
    absichtlich in der Funktion — die Renderer-Schicht soll beim Laden nicht
    den Provider-Zweig mitziehen.

    Rueckgabe ``None`` heisst „nicht ermittelbar" und ist bewusst NICHT
    dasselbe wie das leere ``frozenset`` („ermittelt, es gibt keine"): nur mit
    dieser Unterscheidung kann der Aufrufer eine falsche Zuschreibung
    vermeiden (F003). Eine Rueckfall-Konstante mit den drei bekannten
    Feldnamen waere hier eine ZWEITE Wahrheitsquelle und wuerde genau die
    Eigenschaft aufweichen, wegen der diese Funktion existiert.

    Schlaegt der Import fehl, entfaellt die Gewitterzeile und das Briefing
    rendert weiter. Begruendung: ADR-0047 Entscheidung 3 haelt fest, dass ein
    Ausfall der Gewitterquelle die Grundvorhersage nie kippen darf — fuer den
    Anzeigeweg gilt dasselbe Prinzip. Die Herleitung der Feldnamen aus dem
    Produktivcode (SSoT) bleibt im Normalfall unveraendert erhalten; sie
    entfaellt nur im Fehlerfall.
    """
    try:
        from providers.thunder_enrichment import _EINZELWERT_FELD, _SIGNAL_ZU_FELD
    except ImportError:
        return None

    return frozenset({*_SIGNAL_ZU_FELD.values(), _EINZELWERT_FELD})


def _quelle_klartext(model: str) -> Tuple[str, str]:
    """(Klartext, Zusatz) — unbekannte Kennung erscheint roh (R7)."""
    return _MODELL_KLARTEXT.get(model, (model, ""))


def select_fallback_meta(segments) -> Optional["ForecastMeta"]:
    """Das erste ``meta`` mit einer Fallback-Markierung — ueber ALLE Segmente.

    EINE Auswahlregel fuer alle vier Ausgaben (HTML-, Plain-, Kompakt-Mail und
    Telegram-Langform). Vorher gab es zwei: die Mail-Renderer lasen starr
    ``segments[0]``, ``narrow.py`` das erste fehlerfreie Segment mit
    Zeitreihe. Beide verschweigen eine Vertretung, die erst eine spaetere
    Etappe betraf — und zwar still, was ADR-0018/ADR-0047 („Fallback ohne
    Kaschieren") widerspricht.

    Ein Segment ohne Zeitreihe (Abruffehler) wird UEBERSPRUNGEN, nicht als
    Abbruch behandelt: sein fehlendes ``meta`` sagt nichts ueber die
    Vertretung der uebrigen Etappen aus.

    Known Limitation (Spec): tragen mehrere Segmente unterschiedliche
    Vertretungen, gewinnt die erste gefundene. Die Aussage lautet „hier wurde
    ausgewichen", nicht „auf Etappe N wurde ausgewichen" — eine
    etappengenaue Zuordnung waere eine eigene Produktentscheidung.
    """
    for sd in segments or []:
        ts = getattr(sd, "timeseries", None)
        if ts is None:
            continue
        meta = getattr(ts, "meta", None)
        if meta is None:
            continue
        if getattr(meta, "fallback_model", None) or getattr(meta, "fallback_metrics", None):
            return meta
    return None


def build_fallback_lines(meta: Optional["ForecastMeta"]) -> list:
    """Liefert 0, 1 oder 2 fertige Klartext-Zeilen zur Herkunfts-Vertretung.

    Reine Funktion, kein Rendering-Format -- die drei Renderer entscheiden
    selbst ueber Verpackung (HTML/Plain/Telegram).

    R1 — zwei UNABHAENGIGE Zeilen:

    1. Gewitterzeile, wenn ``fallback_metrics`` einen Gewitter-Feldnamen
       traegt. Warum nicht ``fallback_model`` (R2): der Merge-Schutz aus 2a
       (``thunder_enrichment.py:286-288``) setzt die Singularfelder nur,
       solange sie ``None`` sind — hat ein Grundvorhersage-Fallback zuvor
       geschrieben, steht dort dessen Modellname, obwohl eine
       Gewitter-Vertretung stattfand. ``fallback_metrics`` ist davon nicht
       betroffen (immer ``extend``).
    2. Wetterzeile, wenn ``fallback_model`` gesetzt ist UND
       ``fallback_reason != "thunder_source_unavailable"``.
    """
    if meta is None:
        return []

    metriken = list(getattr(meta, "fallback_metrics", None) or [])
    modell = getattr(meta, "fallback_model", None)
    grund = getattr(meta, "fallback_reason", None)

    # Der Provider-Import laeuft NUR, wenn er gebraucht wird: ohne
    # ``fallback_metrics`` gibt es keine Gewitterzeile zu bilden. Sonst
    # haenge im Normalfall (der weitaus haeufigste) die gesamte Mail- und
    # Telegram-Rendering-Kette an der Importierbarkeit des Gewitter-Zweigs.
    ermittelt = _gewitter_felder() if metriken else frozenset()
    # F003 — ``None`` heisst: die beiden Herkuenfte sind NICHT trennbar.
    trennbar = ermittelt is not None
    gewitter_felder = ermittelt or frozenset()
    hat_gewitter = any(m in gewitter_felder for m in metriken)
    hat_wetter = bool(modell) and grund != "thunder_source_unavailable"

    lines = []

    if hat_gewitter:
        # R3 — Kollisionsfall: laeuft die Wetterzeile ebenfalls, dann ist
        # ``fallback_model`` vom Grundvorhersage-Mechanismus belegt und waere
        # hier der Name der FALSCHEN Ersatzquelle. Dann lieber keinen Namen.
        # Eine Ableitung ueber Koordinaten/``thunder_routing`` waere eigene
        # Fachlogik im Ausgabe-Kanal (ADR-0025-Verstoss) und unterbleibt.
        if hat_wetter or not modell:
            lines.append(_GEWITTER_OHNE_QUELLE)
        else:
            name, zusatz = _quelle_klartext(modell)
            klammer = " (%s)" % zusatz if zusatz else ""
            lines.append("Gewitterdaten von Ersatzquelle: %s%s" % (name, klammer))

    if hat_wetter:
        # R4 — Metrikliste ABZUEGLICH der Gewitter-Feldnamen: die stehen dort
        # nur, weil beide Mechanismen in dieselbe Liste schreiben, und
        # gehoeren fachlich zur Gewitterzeile (AC-8).
        #
        # F003 — sind die Feldnamen nicht ermittelbar (Importfehler), kann der
        # Abzug nicht stattfinden. Dann bliebe ein Gewitter-Feldname in dieser
        # Klammer stehen und waere dem Ersatzmodell der GRUNDVORHERSAGE
        # zugeschrieben, das mit den Blitzdaten nichts zu tun hat. Lieber gar
        # keine Werte nennen als falsche: die Klammer entfaellt komplett.
        rest = []
        for m in metriken if trennbar else []:
            if m in gewitter_felder:
                continue
            klartext = _METRIK_KLARTEXT.get(m, m)  # R7: Rohwert statt KeyError
            if klartext not in rest:
                rest.append(klartext)
        name, _zusatz = _quelle_klartext(modell)
        # R4/#1145 — leere Restliste: Klammer entfaellt ERSATZLOS. Kein "()",
        # kein " : "-Artefakt, kein Doppelpunkt ohne Inhalt.
        klammer = " (%s)" % ", ".join(rest) if rest else ""
        lines.append("Einzelne Wetterwerte von Ersatzmodell: %s%s" % (name, klammer))

    return lines
