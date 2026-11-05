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

from i18n import Lang, t

if TYPE_CHECKING:  # pragma: no cover - nur fuer Typpruefer
    from app.models import ForecastMeta


# --- Quellenkennung -> (Klartext, grobe Aufloesung?) -----------------------
# Wertebereich gemessen an allen Schreibstellen in ``src/providers/``
# (``openmeteo.py:1055/1077/1167``, ``region_routing.py:33-36``,
# ``thunder_enrichment.py:287``). ``icon_seamless`` steht bewusst NICHT hier:
# es ist nie ein Fallback-Wert, nur ``meta.model``. Die Namen sind Eigennamen
# der Anbieter und bleiben in jeder Sprache; der Zusatz "gröbere Auflösung"
# kommt aus dem Katalog (``mail.fallback.groeber``, #2751).
_MODELL_KLARTEXT: dict[str, Tuple[str, bool]] = {
    "eu_direct": ("DWD Europa", True),
    "de_direct": ("DWD Deutschland", False),
    "fr_direct": ("Météo-France", False),
    "at_direct": ("GeoSphere Österreich", False),  # i18n-fest: Eigenname des Anbieters
    "icon_eu": ("DWD Europa", True),
    "icon_d2": ("DWD Deutschland", False),
    "meteofrance_arome": ("Météo-France", False),
    "metno_nordic": ("MET Norway", False),
    "ecmwf_ifs04": ("ECMWF", True),
}

# --- Metrikkennungen mit Klartext im Katalog --------------------------------
# ``fallback_metrics`` mischt ZWEI Namenssysteme (Kontext-Doc): Open-Meteo-
# Parameternamen (``OpenMeteoProvider._PARAM_TO_FIELD``, 18 Eintraege) bei
# Metrik-Luecke/Modell-5xx, Datenpunkt-Feldnamen bei Schnee- und
# Gewitter-Anreicherung. Beide sind hier abgebildet.
#
# Die Klartexte stehen im Katalog (``mail.fallback.metrik.<kennung>``, #2665);
# die deutschen sind 1:1 aus ``app/metric_catalog.py`` (``label_de``)
# uebernommen, damit derselbe Begriff im Produkt nicht zweimal verschieden
# heisst. Bewusst NICHT mechanisch daran gekoppelt: der Katalog ist mit
# Metrik-IDs geschluesselt, diese Liste mit Parameter-/Feldnamen — die
# Bruecke waere eine eigene, fehleranfaellige Abbildung (Spec, Known
# Limitations). Die Gewitter-Feldnamen (letzte drei) erscheinen wegen R4 NIE
# in der Wetterzeile — sie loesen die Gewitterzeile aus.
_METRIK_KENNUNGEN: frozenset[str] = frozenset({
    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
    "dewpoint_2m", "pressure_msl", "cloud_cover", "cloud_cover_low",
    "cloud_cover_mid", "cloud_cover_high", "wind_speed_10m",
    "wind_direction_10m", "wind_gusts_10m", "precipitation",
    "precipitation_probability", "visibility", "cape",
    "freezing_level_height", "uv_index", "weather_code", "snow_depth",
    "swe_tot",
    "lightning_density_per_km2_3h", "lightning_potential_lpi_jkg",
    "hail_potential_grau_gsp",
})

# Deutscher Referenzwert; die Zeilen kommen sprachabhaengig aus dem Katalog
# (``mail.fallback.*``, Issue #2665). Quellennamen sind Eigennamen und bleiben.
_GEWITTER_OHNE_QUELLE = t("mail.fallback.gewitter_ohne_quelle", "de")


def _metrik_text(metrik: str, lang: Lang) -> str:
    """Klartext einer Metrikkennung; unbekannte Kennung roh (R7)."""
    if metrik not in _METRIK_KENNUNGEN:
        return metrik
    # i18n-dynamic: mail.fallback.metrik.
    return t(f"mail.fallback.metrik.{metrik}", lang)


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


def _quelle_klartext(model: str) -> Tuple[str, bool]:
    """(Klartext, grobe Aufloesung?) — unbekannte Kennung erscheint roh (R7)."""
    return _MODELL_KLARTEXT.get(model, (model, False))


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


def build_fallback_lines(meta: Optional["ForecastMeta"], *, lang: Lang = "de") -> list:
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
            lines.append(t("mail.fallback.gewitter_ohne_quelle", lang))
        else:
            name, grob = _quelle_klartext(modell)
            klammer = " (%s)" % t("mail.fallback.groeber", lang) if grob else ""
            lines.append(t("mail.fallback.gewitter_quelle", lang, name=name) + klammer)

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
            klartext = _metrik_text(m, lang)  # R7: Rohwert statt KeyError
            if klartext not in rest:
                rest.append(klartext)
        name, _grob = _quelle_klartext(modell)
        # R4/#1145 — leere Restliste: Klammer entfaellt ERSATZLOS. Kein "()",
        # kein " : "-Artefakt, kein Doppelpunkt ohne Inhalt.
        klammer = " (%s)" % ", ".join(rest) if rest else ""
        lines.append(t("mail.fallback.wetter_modell", lang, name=name) + klammer)

    return lines


def build_compare_fallback_lines(location_results, *, lang: Lang = "de") -> list:
    """Mehrort-Huelle fuer den Ortsvergleich (Issue #1563, Spec R2).

    Je betroffenem Ort die Zeilen aus ``build_fallback_lines(meta, lang=)``,
    mit dem Ortsnamen vorangestellt (Muster ``mail.fallback.compare_zeile``).
    Formulierung bleibt EINZIG in ``build_fallback_lines`` (Trip/Compare-
    Teilung). Fehlerorte und Orte ohne Markierung liefern keine Zeile;
    Reihenfolge = Reihenfolge der uebergebenen Liste (Vergleichstabelle).
    ``[]`` wenn kein Ort betroffen ist.
    """
    zeilen: list = []
    for lr in location_results or []:
        if getattr(lr, "error", None) is not None:
            continue
        ort = lr.location.name
        for text in build_fallback_lines(getattr(lr, "forecast_meta", None), lang=lang):
            zeilen.append(t("mail.fallback.compare_zeile", lang, ort=ort, text=text))
    return zeilen
