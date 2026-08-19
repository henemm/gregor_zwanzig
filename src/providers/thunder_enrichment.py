"""DER gemeinsame Anschluss fuer Gewittersignale (#1457 S2a, Konzept #1419).

Dies ist die EINZIGE Stelle, an der Gewittersignale in eine Vorhersage
gelangen. Sie kennt bewusst KEINE Quelle namentlich und keine Groessen-Kennung
einer Quelle — sie schlaegt in `providers.thunder_routing` die zustaendige
Quelle nach, ruft das gemeinsame Protokoll
(`providers.base.ThunderSignalProvider`) und legt die Werte an den Datenpunkt.

WARUM so streng (Spec AC-8, PO-Vorgabe "keine Einzelloesungen"): Ohne diese
Regel bekaeme jedes Gebiet seinen eigenen Anschluss — einer fuer Korsika,
einer fuer die Alpen, einer fuer den Rest — und die driften auseinander. Eine
neue Quelle wird stattdessen allein dadurch wirksam, dass sie das Protokoll
erfuellt und in der Zustaendigkeitstabelle steht. Diese Datei wird dabei nicht
angefasst.

Muster: `OpenMeteoProvider._enrich_snow` (openmeteo.py) — best effort,
fail-soft, mutiert in-place, wirft nie.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from app.config import Location
    from app.models import NormalizedTimeseries

logger = logging.getLogger("thunder_enrichment")

# Signalname -> Modellfeld (#1457 S2b). Das EINZIGE Vokabular, das dieser
# Anschluss kennt: keine Quelle, kein Providername, nur Signale. Eine neue
# Quelle wird dadurch wirksam, dass sie das Protokoll erfuellt, in der
# Zustaendigkeitstabelle steht und ihr Signal hier EINE Zeile bekommt — der
# Dispatch unten wird dabei nie angefasst (Spec AC-9).
_SIGNAL_ZU_FELD: Dict[str, str] = {
    "lpi": "lightning_potential_lpi_jkg",
    "grau_gsp": "hail_potential_grau_gsp",
    # #1531: sieben neue Signale (ICON-D2 + ICON-EU-Energiegroessen). Je
    # Groesse ein eigenes Feld (Spec Implementation Details Punkt 4).
    # `cape_con` (ICON-EU) bekommt BEWUSST keinen Eintrag -- wird abgerufen,
    # aber keinem Feld zugeordnet (Spec Scope-Abgrenzung).
    "sdi_2": "supercell_index_sdi2_1s",
    "cin_ml": "convective_inhibition_jkg",
    "cape_ml": "cape_ml_jkg",
    "lpi_max": "lightning_potential_max_lpi_jkg",
    "uh_max": "updraft_helicity_max_m2s2",
    "uh_max_med": "updraft_helicity_max_med_m2s2",
    "uh_max_low": "updraft_helicity_max_low_m2s2",
    # #1758: GeoSphere AROME (Oesterreich) liefert cape/cin additiv zum DWD.
    # Eigene Felder (Modul-Docstring `app.models` erklaert warum) -- daher
    # eigene Signalnamen statt der DWD-Eintraege "cin_ml"/"cape_ml".
    "cape": "cape_geosphere_jkg",
    "cin": "convective_inhibition_geosphere_jkg",
}

# Feld der bestehenden Einzelwert-Quelle (S2a). Es steht NICHT in der Tabelle
# oben, weil jene Quelle ihr Signal nicht benennt.
_EINZELWERT_FELD = "lightning_density_per_km2_3h"


def _bekannte_felder() -> tuple:
    """Alle Felder, die dieser Anschluss ueberhaupt befuellen kann.

    Wird bei JEDEM Aufruf frisch aus der Tabelle abgeleitet, damit eine neue
    Zeile dort automatisch auch vom Fuell-Waechter gesehen wird — sonst muesste
    beim Eintragen einer neuen Quelle daran gedacht werden, und genau das wird
    vergessen (Spec AC-5).
    """
    return (_EINZELWERT_FELD, *_SIGNAL_ZU_FELD.values())


def _naiv_utc(ts: datetime) -> datetime:
    """Zeitstempel auf naive UTC bringen — Vorhersagereihen mischen naive
    (Open-Meteo) und zeitzonenbehaftete (Direktquellen) Zeitstempel."""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(timezone.utc).replace(tzinfo=None)


def _bezugszeitpunkt(reihe: "NormalizedTimeseries") -> datetime:
    """Nullpunkt der Stunden-Offsets.

    Zwei Festlegungen:
    1. Gezaehlt wird ab dem ersten Datenpunkt, aber nie aus der Vergangenheit
       heraus. Ein Briefing enthaelt oft schon abgelaufene Stunden; wuerde man
       von dort zaehlen, gingen die Abrufe ins Leere (fuer vergangene Stunden
       gibt es keine Vorhersage) und der nutzbare Teil bliebe leer.
    2. Der Nullpunkt liegt eine Stunde VOR dem ersten gewuenschten Zeitpunkt,
       weil die Offsets bei 1 beginnen. Sonst bliebe die erste Stunde des
       Zeitraums systematisch leer.
    """
    erster = min(_naiv_utc(dp.ts) for dp in reihe.data)
    jetzt_volle_stunde = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    )
    return max(erster, jetzt_volle_stunde) - timedelta(hours=1)


def _blitzpotenzial_wert(dp) -> Optional[float]:
    """Waehlt den EINEN Blitzpotenzial-Wert, den die Fusion sieht (Issue #1757,
    Variante A, PO-Entscheid 2026-08-19).

    VORRANGREGEL: das Stundenmaximum ``lightning_potential_max_lpi_jkg``
    (ICON-D2/DE_ALPEN, abgerufen seit #1531) schlaegt den Momentanwert
    ``lightning_potential_lpi_jkg``. Grund: der Backtest vom 2026-08-11 hat
    fuer den Momentanwert einen Recall von 5,6 % gemessen (1 von 18 echten
    Gewitterstunden) -- der Momentanwert am Stundenrand verfehlt Gewitter
    systematisch.

    RUECKFALL, NICHT ERSATZLOS: ``lightning_potential_max_lpi_jkg`` wird
    ausschliesslich von ICON-D2 befuellt. Faellt der Rueckfall auf den
    Momentanwert weg, verloere JEDES Gebiet ausserhalb DE_ALPEN das
    Blitzpotenzial-Signal ersatzlos -- eine stille Regression. Ausserhalb der
    Alpen ist der "Momentanwert" ohnehin schon ein Stundenmaximum: die dortige
    ICON-EU-Groesse wird unter dem Signalnamen ``lpi`` eingehaengt (Nachweis:
    ``src/providers/dwd_eu.py``). Ihr Abrufname steht hier BEWUSST NICHT --
    diese Datei ist der gemeinsame, quellenblinde Anschlussweg und darf keinen
    providerspezifischen Groessennamen kennen (#1457 S2a/S2c AC-8, bewacht von
    ``test_thunder_enrichment_shared_path.py``
    ``::test_ac8_anschlussweg_kennt_keinen_providernamen``). Wer den Namen zur
    Verdeutlichung nachtragen will: nicht hier, sondern in ``dwd_eu.py``.

    ``0.0``-FALLE -- NICHT zu ``a or b`` kuerzen: ``0.0`` heisst "in dieser
    Stunde kein Blitzpotenzial" und ist ein gueltiger Messwert, in Python aber
    unwahr. Mit ``or`` fiele die Auswahl bei exakt 0,0 still auf den
    Momentanwert zurueck und meldete Gewitter, wo das Stundenmaximum keines
    sieht. Deshalb die ausdrueckliche ``is not None``-Pruefung; der Wachhund
    dagegen ist
    ``tests/tdd/test_thunder_fusion_prefers_hourly_max.py::test_ac2_stundenmaximum_null_komma_null_gilt_und_faellt_nicht_zurueck``.

    Die Auswahl wohnt HIER beim Aufrufer, nicht in ``metric_format.py``: die
    Fusion bekommt EINE Zahl und EINE Leiter und bleibt statistik-blind
    (ADR-0025). Die Schwellenleiter ``LPI_THRESHOLDS_JKG`` bleibt unveraendert
    -- dieselben Sprossen, gegen eine andere Statistik gemessen (Spec
    Known Limitations).
    """
    if dp.lightning_potential_max_lpi_jkg is not None:
        return dp.lightning_potential_max_lpi_jkg
    return dp.lightning_potential_lpi_jkg


def _fuse_thunder_levels(
    data: list,
    cape_ladder: Optional[Tuple[float, float, float]],
    lpi_thresholds: Optional[Tuple[float, float, float]],
) -> None:
    """Issue #1474 Abschnitt 3: ergaenzt ``dp.thunder_level`` je Datenpunkt um
    Blitzdichte-, CAPE- und Blitzpotenzial-Signale (``thunder_level_from_signals()``,
    ``metric_format.py`` -- dort wohnt die Skala, ADR-0025). Blitzpotenzial
    seit Issue #1474c; Hagel (``hail_potential_grau_gsp``) bleibt bewusst
    aussen vor (S5/#1475).

    ``cape_ladder`` -- die geeichte, modell-/gebietsabhaengige
    (low, med, high)-CAPE-Leiter (Issue #1592 C1, seit Issue #1679 dreisprossig
    statt einer einzelnen Schwelle), EINMAL je Reihe in ``enrich_thunder()``
    aufgeloest und hier unveraendert durchgereicht. BEWUSST OHNE Default
    (PO-Korrektur 2026-08-08): "kein stiller Rueckfall" (Spec Abschnitt 3,
    ADR-0025) gilt auf der GANZEN Kette, nicht nur an der oeffentlichen
    Grenze ``thunder_level_from_signals()`` -- jeder Aufrufer, auch ein
    Test, der nur die Blitzdichte-/Blitzpotenzial-/Hagel-Fusion pruefen
    will, muss den Parameter ausdruecklich nennen.

    Die Konvektionshemmung CIN kommt dagegen NICHT je Reihe, sondern je
    Datenpunkt (``dp.convective_inhibition_jkg``, Issue #1531) -- sie ist ein
    Rohwert der Vorhersage, keine Kalibrierungskonstante des Gebiets.

    ``lpi_thresholds`` -- die gebietsabhaengige (low, med, high)-Leiter des
    Blitzpotenzials (Issue #1679, ``model_registry.lpi_thresholds_jkg()``),
    ebenso EINMAL je Reihe aufgeloest und BEWUSST OHNE Default, aus demselben
    Grund. ``None`` (Gebiet unbekannt oder ohne Kalibrierung, z.B. FR) heisst
    "kein LPI-Signal", nicht "Ersatzschwelle".

    Ueberschreibt NUR, wenn die Fusion ein Ergebnis liefert -- liefert sie
    ``None`` ("keine Aussage"), bleibt ein bereits vorhandener Wert an
    ``dp.thunder_level`` erhalten (s. Spec Abschnitt 3, letzter Absatz).

    Issue #1757: welche der beiden Blitzpotenzial-Zahlen einfliesst, entscheidet
    ``_blitzpotenzial_wert()`` (Stundenmaximum vor Momentanwert) -- die Fusion
    selbst bleibt statistik-blind.

    Issue #1680 S1: zusaetzlich wird festgehalten, WELCHE Zutaten die Stufe
    tragen (``dp.thunder_level_signals``) -- aus DEMSELBEN Argumentsatz und
    unter DERSELBEN Ueberschreib-Bedingung, damit Stufe und Herkunft nie aus
    zwei verschiedenen Rechnungen stammen koennen.
    """
    from output.metric_format import thunder_level_from_signals, thunder_signal_carriers

    cape_low, cape_med, cape_high = cape_ladder or (None, None, None)
    lpi_low, lpi_med, lpi_high = lpi_thresholds or (None, None, None)
    for dp in data:
        werte = (dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg,
                 _blitzpotenzial_wert(dp))
        leitern = dict(
            cape_threshold_jkg=cape_low,
            cape_med_min=cape_med, cape_high_min=cape_high,
            cin_jkg=dp.convective_inhibition_jkg,
            lpi_low_min=lpi_low, lpi_med_min=lpi_med, lpi_high_min=lpi_high,
        )
        fused = thunder_level_from_signals(*werte, **leitern)
        if fused is not None:
            dp.thunder_level = fused
            dp.thunder_level_signals = thunder_signal_carriers(*werte, **leitern)


def _schwellen_fuer_reihe(
    reihe: "NormalizedTimeseries", location: "Location",
) -> Tuple[
    Optional[Tuple[float, float, float]], Optional[Tuple[float, float, float]]
]:
    """Loest die beiden gebietsabhaengigen Schwellenleitern der Fusion EINMAL
    je Reihe auf: die geeichte CAPE-Leiter (Issue #1592 C1 / #1679,
    Modell x Gebiet) und die Blitzpotenzial-Leiter (Issue #1679, Gebiet).
    BEIDE haengen am SELBEN Gebiets-Nachschlag -- kein zweiter
    Aufloesungs-Ort.

    Wohnt bewusst NEBEN ``enrich_thunder()`` statt darin: der Kern-Dispatch
    dort darf keinen einzelnen Signalnamen im Quelltext tragen (Waechter
    ``test_thunder_named_signals_enrichment.py::test_ac9_...``, #1457 S2b
    AC-9), und der Name der Nachschlag-Funktion traegt ihn.
    """
    from app.model_registry import (
        cape_ladder_thresholds_jkg, effective_cape_model_id, lpi_thresholds_jkg,
    )
    from providers.thunder_routing import thunder_region_for

    region = thunder_region_for(location.latitude, location.longitude)
    return (
        cape_ladder_thresholds_jkg(effective_cape_model_id(reihe.meta), region),
        lpi_thresholds_jkg(region),
    )


def enrich_thunder(
    reihe: "NormalizedTimeseries",
    location: "Location",
    bereits_befragt: Optional[str] = None,
) -> None:
    """Gewittersignale der zustaendigen Quelle in die Reihe legen (in-place).

    Args:
        reihe: Vorhersagereihe, wird in-place ergaenzt
        location: Ort der Reihe
        bereits_befragt: Name einer Quelle, die diese Reihe geliefert und dabei
            selbst schon nach Gewittersignalen gefragt hat. Ist sie zugleich
            die zustaendige Gewitterquelle, wird nicht erneut abgerufen — sonst
            entstuende ein Doppelabruf derselben Stunden, und zwar ausgerechnet
            dann, wenn die Quelle nichts geliefert hat.

    Fail-soft (Spec AC-3): Jede Ausnahme wird geschluckt — die Felder bleiben
    dann `None`. Ein Ausfall der Gewitterquelle darf die Vorhersage nie kippen.

    Fehlender Wert bleibt `None` und wird NIE 0 (Spec AC-2): "keine Aussage"
    ist nicht "keine Gefahr".

    Issue #1457 S2b: Quellen, die mehrere Signale getrennt und benannt liefern
    (DWD: Blitzpotenzial/Hagelsignal), fuellen ueber ``_SIGNAL_ZU_FELD`` eigene
    Rohwert-Felder. Das Blitzpotenzial geht seit #1474c zusaetzlich in die
    Stufen-Fusion unten ein (S2b AC-8 ist damit fuer dieses Signal
    aufgehoben). Das Hagelsignal bleibt weiterhin aussen vor -- das ist
    S5/#1475.

    Issue #1474 (AC-9), erweitert um #1474c: nach dem Fuellen von
    ``lightning_density_per_km2_3h`` wird zusaetzlich ``dp.thunder_level`` mit
    dem ueber Wettercode, Blitzdichte, CAPE UND Blitzpotenzial fusionierten
    Ergebnis ueberschrieben -- EIN gemeinsamer Anschluss, kein Sonderweg je
    Aufrufer (Trip/Ortsvergleich). Die Fusion laeuft auch, wenn kein
    Gewitter-Anbieter fuer diesen Ort zustaendig ist (dann bleibt die
    Blitzdichte leer, CAPE kann trotzdem "leicht" ausloesen).
    """
    if not reihe.data:
        return
    # #1758 Scheibe B: der frueher HIER stehende globale Fill-Waechter
    # ("traegt die Reihe schon IRGENDEIN bekanntes Signal, ganz abbrechen")
    # ist in `_fetch_lightning_density()` gewandert und gilt dort NUR noch
    # fuer die PRIMAERE Quelle -- sonst kaeme eine additive Zusatzquelle
    # (GeoSphere fuer AT) nie zum Zug, sobald die primaere geliefert hat
    # (Spec AC-7). Die Fusion unten laeuft deshalb immer.
    try:
        _fetch_lightning_density(reihe, location, bereits_befragt)
    except Exception:
        logger.warning("Gewitter-Anreicherung fehlgeschlagen", exc_info=True)

    cape_leiter, potenzial_leiter = _schwellen_fuer_reihe(reihe, location)

    # Laeuft IMMER (auch ausserhalb eines Zustaendigkeitsgebiets oder bei
    # Abruf-Fehlschlag) -- CAPE steht unabhaengig von der Blitzdichte-Quelle
    # an jedem Datenpunkt und kann allein schon "leicht" ausloesen.
    _fuse_thunder_levels(reihe.data, cape_leiter, potenzial_leiter)


def _hole_eintraege(
    quelle_name: str, location: "Location", von: datetime, bis: datetime,
) -> list:
    """Ruft `quelle_name` ab und liefert `[(Feld, Werte)]`. Frisch ermittelt
    bei JEDEM Aufruf, ob die Quelle `fetch_thunder_signals_named`/`_multi`/die
    Einzelwert-Methode anbietet -- eine Vertretung schreibt dadurch
    strukturell in die Felder, die SIE SELBST benennt (#1492 S2a Spec
    Implementation Details Punkt 4), kein Sonderfall-Code noetig. Kann
    `providers.base.ThunderSourceUnavailableError` werfen (Vertrag des
    Providers, s. dort) -- das faengt die aufrufende Stelle ab."""
    from providers.base import ThunderSignalProvider, get_provider

    provider = get_provider(quelle_name)
    if not isinstance(provider, ThunderSignalProvider):
        # Wer das Protokoll nicht erfuellt, liefert nichts — kein Fehler.
        logger.debug("Quelle '%s' liefert keine Gewittersignale", quelle_name)
        return []

    # Benannter Abruf hat Vorrang (Spec AC-9, #1457 S2b): Quellen, die
    # MEHRERE Signale getrennt liefern, sagen selbst, wie ihre Signale
    # heissen; welches Modellfeld dazu gehoert, steht allein in der Tabelle
    # oben. Wer den benannten Weg nicht hat, bleibt unveraendert auf dem
    # Einzelwert-/Sammelweg vollwertig. Sammelabruf bevorzugt (Spec AC-9):
    # Quellen, die mehrere Orte aus EINEM Abfragefenster bedienen koennen,
    # werden auch hier darueber gerufen — auch bei nur einem Ort.
    benannt = getattr(provider, "fetch_thunder_signals_named", None)
    sammeln = getattr(provider, "fetch_thunder_signals_multi", None)
    if callable(benannt):
        benannte = benannt(location, von, bis) or {}
        return [
            (feld, benannte.get(signalname) or {})
            for signalname, feld in _SIGNAL_ZU_FELD.items()
        ]
    if callable(sammeln):
        gesammelt = sammeln([location], von, bis) or {}
        # Ein Ort rein, ein Eintrag raus — der Schluessel gehoert der
        # Quelle, deshalb wird er hier nicht nachgebaut.
        signale: Dict[int, Optional[float]] = (
            next(iter(gesammelt.values())) if len(gesammelt) == 1 else {}
        )
    else:
        signale = provider.fetch_thunder_signals(location, von, bis)
    return [(_EINZELWERT_FELD, signale or {})]


def _wende_eintraege_an(
    reihe: "NormalizedTimeseries", eintraege: list, basis: datetime,
) -> int:
    """Traegt `[(Feld, Werte)]` an die Datenpunkte der Reihe ein (dieselbe
    Offset-Konvention wie `_bezugszeitpunkt`: Nullpunkt = `basis`, Offsets
    beginnen bei 1) und liefert die Anzahl gesetzter Werte. Geteilter
    Schreibweg fuer Primaer- UND Zusatzquellen (#1758) -- EIN Anschluss, kein
    zweiter."""
    nach_ts = {_naiv_utc(dp.ts): dp for dp in reihe.data}
    gefuellt = 0
    for feld, werte in eintraege:
        for offset, wert in werte.items():
            if wert is None:
                continue  # AC-2: leer bleibt leer, nie 0
            dp = nach_ts.get(basis + timedelta(hours=offset))
            if dp is None:
                continue
            setattr(dp, feld, wert)
            gefuellt += 1
    return gefuellt


def _primaerquelle_bereits_gefuellt(reihe: "NormalizedTimeseries") -> bool:
    """Fill-only-Waechter der PRIMAEREN Quelle (Muster `_enrich_snow`,
    unveraendert seit #1457 S2b): traegt die Reihe schon IRGENDEIN bekanntes
    Gewittersignal, gibt es fuer die Primaerquelle nichts zu holen -- die
    Fusion lief dann bereits in einem frueheren Aufruf. Bewusst ueber ALLE
    bekannten Felder (Spec AC-5 des Vorgaenger-Moduls #1457 S2b) — waere der
    Waechter auf das Feld der Einzelwert-Quelle festgenagelt, griffe er fuer
    jede Quelle, die dieses Feld nie befuellt, ueberhaupt nicht.

    Gilt seit #1758 NUR fuer die Primaerquelle. Zusatzquellen fuehren KEINEN
    eigenen feldbasierten Waechter (Spec Implementation Details Punkt 6) --
    sie werden stattdessen bei JEDEM Aufruf versuchtund sind dafuer PRO
    Quelle fail-soft (s. `_fetch_lightning_density`)."""
    felder = _bekannte_felder()
    return any(getattr(dp, feld, None) is not None
               for dp in reihe.data for feld in felder)


def _fetch_primaerquelle(
    reihe: "NormalizedTimeseries",
    location: "Location",
    quelle: str,
    bereits_befragt: Optional[str],
    basis: datetime,
    von: datetime,
    bis: datetime,
) -> None:
    """Primaerquellen-Pfad -- UNVERAENDERTES #1492-S2a-Verhalten (Vertretung
    bei echtem Ausfall, ADR-0047). Extrahiert aus `_fetch_lightning_density`,
    damit additive Zusatzquellen (#1758) denselben Schreibweg
    (`_wende_eintraege_an`) nutzen koennen, OHNE die Vertretungslogik zu
    erben -- GeoSphere bekommt bewusst KEINEN Vertretungs-Eintrag (Spec
    Scope-Abgrenzung).

    #1492 S2a: faellt die Primaerquelle ECHT aus
    (`ThunderSourceUnavailableError`, Spec ADR-0047), wird die benannte
    Vertretung (`thunder_vertretung_for`) EINMAL nachgefragt -- mit ihrem
    eigenen vollen Zeitbudget, keine Restzeit-Weitergabe (Known Limitations
    1). Scheitert sie selbst auch, propagiert die Ausnahme zum bestehenden
    aeusseren Fang in `enrich_thunder()` (Spec AC-5)."""
    from providers.base import ThunderSourceUnavailableError
    from providers.thunder_routing import thunder_vertretung_for

    aktive_quelle = quelle
    try:
        eintraege = _hole_eintraege(quelle, location, von, bis)
    except ThunderSourceUnavailableError:
        ersatz = thunder_vertretung_for(quelle)
        if ersatz is None or ersatz == bereits_befragt:
            return
        aktive_quelle = ersatz
        eintraege = _hole_eintraege(ersatz, location, von, bis)

    if not any(werte for _feld, werte in eintraege):
        return

    gefuellt = _wende_eintraege_an(reihe, eintraege, basis)
    if not gefuellt:
        return

    if aktive_quelle == quelle:
        logger.info(
            "Gewittersignale von '%s': %d Zeitpunkte gefuellt", quelle, gefuellt
        )
        return

    # #1492 S2a AC-4: Herkunft vermerken. Merge-Schutz (Known Limitations 3):
    # `fallback_model`/`fallback_reason` nur setzen, wenn noch unbesetzt --
    # ein Grundvorhersage-Fallback (#1115) darf nicht ueberschrieben werden.
    # `fallback_metrics` bleibt davon unberuehrt, immer append-faehig.
    reihe.meta.fallback_metrics.extend(
        sorted({feld for feld, werte in eintraege if werte})
    )
    if reihe.meta.fallback_model is None:
        reihe.meta.fallback_model = aktive_quelle
        reihe.meta.fallback_reason = "thunder_source_unavailable"
    logger.warning(
        "Gewittersignale von Ersatzquelle '%s' statt '%s' "
        "(nicht erreichbar): %d Zeitpunkte gefuellt",
        aktive_quelle, quelle, gefuellt,
    )


def _fetch_lightning_density(
    reihe: "NormalizedTimeseries",
    location: "Location",
    bereits_befragt: Optional[str],
) -> None:
    """Ruft ALLE fuer diesen Ort zustaendigen Quellen ab (#1758, ADR-0057:
    additiv, first-match-wins-Region kann mehrere Quellen tragen) und fuellt
    deren Signalfelder in-place: ``dp.lightning_density_per_km2_3h``
    (Einzelwert-Quelle) bzw. die Felder aus ``_SIGNAL_ZU_FELD`` (benannte
    Quelle, #1457 S2b). Extrahiert aus ``enrich_thunder()``, damit dessen
    frueher ``return`` bei fehlender Zustaendigkeit/leerer Antwort die
    nachfolgende Fusion (``_fuse_thunder_levels``) nicht mehr uebersprungen
    wird.

    Erste Quelle aus ``thunder_providers_for()`` ist die PRIMAERE (unveraen-
    dertes #1492-S2a-Verhalten inkl. Vertretung, s. ``_fetch_primaerquelle``);
    alle weiteren sind additive Zusatzquellen (Spec AC-6/AC-7), die IMMER
    versucht werden -- der Fill-only-Waechter (``_primaerquelle_bereits_
    gefuellt``) gilt seit #1758 nur noch fuer die Primaerquelle, sonst kaeme
    eine Zusatzquelle nie zum Zug, sobald die Primaerquelle geliefert hat.
    """
    from providers.thunder_routing import thunder_providers_for

    quellen = thunder_providers_for(location.latitude, location.longitude)
    if not quellen:
        return  # Spec AC-6: kein Abruf ausserhalb eines Zustaendigkeitsgebiets
    primaer, *zusatz = quellen

    basis = _bezugszeitpunkt(reihe)
    letzter = max(_naiv_utc(dp.ts) for dp in reihe.data)
    von = basis.replace(tzinfo=timezone.utc)
    bis = letzter.replace(tzinfo=timezone.utc)

    if primaer != bereits_befragt and not _primaerquelle_bereits_gefuellt(reihe):
        _fetch_primaerquelle(reihe, location, primaer, bereits_befragt, basis, von, bis)

    # #1758 Scheibe B: Zusatzquellen sind additiv und werden IMMER versucht,
    # sobald sie zustaendig sind (Spec AC-7) -- fail-soft PRO Quelle, damit
    # eine scheiternde Zusatzquelle weder die Primaerquelle noch andere
    # Zusatzquellen mitreisst. Keine Vertretung fuer Zusatzquellen (Scope-
    # Abgrenzung).
    for quelle in zusatz:
        if quelle == bereits_befragt:
            continue
        try:
            eintraege = _hole_eintraege(quelle, location, von, bis)
        except Exception:
            logger.warning("Zusatzquelle '%s' fehlgeschlagen", quelle, exc_info=True)
            continue
        if not any(werte for _feld, werte in eintraege):
            continue
        gefuellt = _wende_eintraege_an(reihe, eintraege, basis)
        if gefuellt:
            logger.info(
                "Gewittersignale von Zusatzquelle '%s': %d Zeitpunkte gefuellt",
                quelle, gefuellt,
            )
