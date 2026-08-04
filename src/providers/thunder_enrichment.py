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
from typing import TYPE_CHECKING, Dict, Optional

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


def _fuse_thunder_levels(data: list) -> None:
    """Issue #1474 Abschnitt 3: ergaenzt ``dp.thunder_level`` je Datenpunkt um
    Blitzdichte-, CAPE- und Blitzpotenzial-Signale (``thunder_level_from_signals()``,
    ``metric_format.py`` -- dort wohnt die Skala, ADR-0025). Blitzpotenzial
    seit Issue #1474c; Hagel (``hail_potential_grau_gsp``) bleibt bewusst
    aussen vor (S5/#1475).

    Ueberschreibt NUR, wenn die Fusion ein Ergebnis liefert -- liefert sie
    ``None`` ("keine Aussage"), bleibt ein bereits vorhandener Wert an
    ``dp.thunder_level`` erhalten (s. Spec Abschnitt 3, letzter Absatz).
    """
    from output.metric_format import thunder_level_from_signals

    for dp in data:
        fused = thunder_level_from_signals(
            dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg,
            dp.lightning_potential_lpi_jkg,
        )
        if fused is not None:
            dp.thunder_level = fused


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
    # Fill-only (Muster `_enrich_snow`): traegt die Reihe schon IRGENDEIN
    # bekanntes Gewittersignal, gibt es nichts zu holen -- die Fusion lief dann
    # bereits in einem frueheren Aufruf. Bewusst ueber ALLE bekannten Felder
    # (#1457 S2b, Spec AC-5) — waere der Waechter auf das Feld der
    # Einzelwert-Quelle festgenagelt, griffe er fuer jede Quelle, die dieses
    # Feld nie befuellt, ueberhaupt nicht: ein zweiter Aufruf auf dieselbe
    # Reihe loeste dann unbemerkt einen zweiten vollstaendigen Abruf aus.
    felder = _bekannte_felder()
    if any(getattr(dp, feld, None) is not None
           for dp in reihe.data for feld in felder):
        return

    try:
        _fetch_lightning_density(reihe, location, bereits_befragt)
    except Exception:
        logger.warning("Gewitter-Anreicherung fehlgeschlagen", exc_info=True)

    # Laeuft IMMER (auch ausserhalb eines Zustaendigkeitsgebiets oder bei
    # Abruf-Fehlschlag) -- CAPE steht unabhaengig von der Blitzdichte-Quelle
    # an jedem Datenpunkt und kann allein schon "leicht" ausloesen.
    _fuse_thunder_levels(reihe.data)


def _fetch_lightning_density(
    reihe: "NormalizedTimeseries",
    location: "Location",
    bereits_befragt: Optional[str],
) -> None:
    """Ruft die zustaendige Quelle ab und fuellt deren Signalfelder in-place:
    ``dp.lightning_density_per_km2_3h`` (Einzelwert-Quelle) bzw. die Felder aus
    ``_SIGNAL_ZU_FELD`` (benannte Quelle, #1457 S2b). Extrahiert aus
    ``enrich_thunder()``, damit dessen frueher ``return`` bei fehlender
    Zustaendigkeit/leerer Antwort die nachfolgende Fusion
    (``_fuse_thunder_levels``) nicht mehr uebersprungen wird."""
    from providers.thunder_routing import thunder_provider_for

    quelle = thunder_provider_for(location.latitude, location.longitude)
    if quelle is None:
        return  # Spec AC-6: kein Abruf ausserhalb eines Zustaendigkeitsgebiets
    if quelle == bereits_befragt:
        return

    from providers.base import ThunderSignalProvider, get_provider

    provider = get_provider(quelle)
    if not isinstance(provider, ThunderSignalProvider):
        # Wer das Protokoll nicht erfuellt, liefert nichts — kein Fehler.
        logger.debug("Quelle '%s' liefert keine Gewittersignale", quelle)
        return

    basis = _bezugszeitpunkt(reihe)
    letzter = max(_naiv_utc(dp.ts) for dp in reihe.data)
    von = basis.replace(tzinfo=timezone.utc)
    bis = letzter.replace(tzinfo=timezone.utc)
    # Sammelabruf bevorzugt (Spec AC-9): Quellen, die mehrere Orte aus EINEM
    # gemeinsamen Abfragefenster bedienen koennen, werden auch hier darueber
    # gerufen — auch bei nur einem Ort. So gibt es genau EINEN Abrufweg
    # statt zweier, die auseinanderdriften. Wer den Sammelweg nicht hat,
    # wird unveraendert einzeln gefragt; das bleibt Teil des Protokolls und
    # nennt weiterhin keine Quelle beim Namen (AC-8).
    #
    # Benannter Abruf hat Vorrang (Spec AC-9, #1457 S2b): Quellen, die
    # MEHRERE Signale getrennt liefern, sagen selbst, wie ihre Signale
    # heissen; welches Modellfeld dazu gehoert, steht allein in der Tabelle
    # oben. Wer den benannten Weg nicht hat, bleibt unveraendert auf dem
    # Einzelwert-/Sammelweg vollwertig.
    benannt = getattr(provider, "fetch_thunder_signals_named", None)
    sammeln = getattr(provider, "fetch_thunder_signals_multi", None)
    if callable(benannt):
        benannte = benannt(location, von, bis) or {}
        eintraege = [
            (feld, benannte.get(signalname) or {})
            for signalname, feld in _SIGNAL_ZU_FELD.items()
        ]
    else:
        if callable(sammeln):
            gesammelt = sammeln([location], von, bis) or {}
            # Ein Ort rein, ein Eintrag raus — der Schluessel gehoert der
            # Quelle, deshalb wird er hier nicht nachgebaut.
            signale: Dict[int, Optional[float]] = (
                next(iter(gesammelt.values())) if len(gesammelt) == 1 else {}
            )
        else:
            signale = provider.fetch_thunder_signals(location, von, bis)
        eintraege = [(_EINZELWERT_FELD, signale or {})]
    if not any(werte for _feld, werte in eintraege):
        return

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
    if gefuellt:
        logger.info(
            "Gewittersignale von '%s': %d Zeitpunkte gefuellt", quelle, gefuellt
        )
