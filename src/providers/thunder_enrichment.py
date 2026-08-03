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
    """
    if not reihe.data:
        return
    # Fill-only (Muster `_enrich_snow`): traegt die Reihe schon Gewittersignale,
    # gibt es nichts zu holen.
    if any(dp.lightning_density_per_km2_3h is not None for dp in reihe.data):
        return

    try:
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
        sammeln = getattr(provider, "fetch_thunder_signals_multi", None)
        if callable(sammeln):
            gesammelt = sammeln([location], von, bis) or {}
            # Ein Ort rein, ein Eintrag raus — der Schluessel gehoert der
            # Quelle, deshalb wird er hier nicht nachgebaut.
            signale: Dict[int, Optional[float]] = (
                next(iter(gesammelt.values())) if len(gesammelt) == 1 else {}
            )
        else:
            signale = provider.fetch_thunder_signals(location, von, bis)
        if not signale:
            return

        nach_ts = {_naiv_utc(dp.ts): dp for dp in reihe.data}
        gefuellt = 0
        for offset, wert in signale.items():
            if wert is None:
                continue  # AC-2: leer bleibt leer, nie 0
            dp = nach_ts.get(basis + timedelta(hours=offset))
            if dp is None:
                continue
            dp.lightning_density_per_km2_3h = wert
            gefuellt += 1
        if gefuellt:
            logger.info(
                "Gewittersignale von '%s': %d Zeitpunkte gefuellt", quelle, gefuellt
            )
    except Exception:
        logger.warning("Gewitter-Anreicherung fehlgeschlagen", exc_info=True)
