"""Geteilter Zwischenspeicher fuer Gewitter-Abfragefenster (#1457 S2a, AC-9).

WARUM eine Ebene TIEFER als der Aufrufer (PO-Richtlinie "Trip/Ortsvergleich-
Teilung", CLAUDE.md): Trip UND Ortsvergleich rufen beide Ort fuer Ort ueber
`OpenMeteoProvider.fetch_forecast`. Wer die Sammlung in einen der beiden
Aufrufer baut, baut einen Sonderweg fuer eine Seite, waehrend die andere weiter
einzeln abruft — genau der Verstoss, den die Richtlinie benennt. Der
Zwischenspeicher sitzt deshalb unter dem Provider: EIN Abruf laedt ein
Rechteck, jeder weitere Ort INNERHALB dieses Rechtecks wird daraus bedient.
Kein Aufrufer muss geaendert werden, beide Seiten profitieren automatisch.

Vorbild und Infrastruktur: `services/weather_cache.py` (`WeatherCacheService` —
Prozess-Singleton, `Lock`, TTL, LRU), heute schon von Trip und Ortsvergleich
gemeinsam genutzt.

Der Schluessel ist bewusst quellen-neutral (Groesse + Zeitschritt + Rechteck):
S2b (DWD) und S2c koennen denselben Speicher nutzen, ohne dass hier etwas
angefasst wird.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Optional, Tuple

logger = logging.getLogger("thunder_window_cache")

# (min_lat, max_lat, min_lon, max_lon)
Rechteck = Tuple[float, float, float, float]

# TTL 600s — dieselbe Zahl wie `get_shared_weather_cache()` und aus demselben
# Grund: der Go-Cron-Alarmzyklus laeuft alle 15 Minuten, also wird ein Gebiet
# hoechstens einmal je Zyklus geholt, aber nie aelter als 10 Minuten bedient.
# Ein zweiter Schutz liegt ausserhalb des TTL: die Groessen-Kennung enthaelt
# den Modell-Lauf, ein neuer Lauf hat also ohnehin neue Schluessel. Der TTL
# regelt damit nur die Wiederverwendung INNERHALB eines Laufs.
DEFAULT_TTL_SECONDS = 600

# Zwei Schranken, weil eine allein nicht traegt: ein Rechteck kostet je nach
# Kantenlaenge 81 KB (2°) bis 1,3 MB (8°) — eine reine Anzahl-Schranke waere
# im einen Fall zu knapp und im anderen zu grosszuegig. 48 Eintraege sind zwei
# volle 24-Stunden-Fenster; 32 MB deckt auch den 24-Stunden-Lauf ueber ein
# 8°-Rechteck gerade noch ab.
DEFAULT_MAX_ENTRIES = 48
DEFAULT_MAX_BYTES = 32 * 1024 * 1024


@dataclass
class _Eintrag:
    rohdaten: bytes
    geholt_at: datetime


class ThunderWindowCache:
    """Thread-sicherer Speicher fuer ROHE Fenster-Antworten.

    Thread-Sicherheit ist Pflicht und nicht vorsorglich: die Orts-Schleife des
    Ortsvergleichs kann parallelisiert werden, und dann greifen mehrere
    Threads gleichzeitig auf denselben Prozess-Singleton zu.

    Trefferregel: EXAKTES Rechteck, keine "deckt ab"-Suche wie im
    Wetter-Cache. Grund: das Rechteck ist hier bereits auf ein gemeinsames
    Kachelgitter gerundet (`meteofrance._thunder_rechteck`), zwei benachbarte
    Orte ergeben also von sich aus denselben Schluessel — die Ersparnis
    entsteht ueber die Kachelung, nicht ueber eine Suche. Eine Deckungs-Suche
    waere zusaetzlich schaedlich fuer die Messbarkeit: sie wuerde die Kosten
    eines Abrufs davon abhaengig machen, was ein frueherer Aufrufer zufaellig
    geladen hat.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._cache: "OrderedDict[str, _Eintrag]" = OrderedDict()
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._bytes = 0

    @staticmethod
    def _schluessel(groesse: str, zeitschritt: str, rechteck: Rechteck) -> str:
        min_lat, max_lat, min_lon, max_lon = rechteck
        return (
            f"{groesse}|{zeitschritt}|"
            f"{min_lat:.4f},{max_lat:.4f},{min_lon:.4f},{max_lon:.4f}"
        )

    def get(
        self, groesse: str, zeitschritt: str, rechteck: Rechteck
    ) -> Optional[bytes]:
        """Rohe Antwort fuer dieses Fenster, wenn sie frisch vorliegt."""
        key = self._schluessel(groesse, zeitschritt, rechteck)
        with self._lock:
            eintrag = self._cache.get(key)
            if eintrag is None:
                return None
            alter = (datetime.now(timezone.utc) - eintrag.geholt_at).total_seconds()
            if alter >= self._ttl_seconds:
                self._entfernen(key)
                return None
            self._cache.move_to_end(key)
            return eintrag.rohdaten

    def put(
        self, groesse: str, zeitschritt: str, rechteck: Rechteck, rohdaten: bytes
    ) -> None:
        """Rohe Antwort ablegen; aeltester Eintrag weicht bei Ueberlauf (LRU)."""
        key = self._schluessel(groesse, zeitschritt, rechteck)
        with self._lock:
            if key in self._cache:
                self._entfernen(key)
            while self._cache and (
                len(self._cache) >= self._max_entries
                or self._bytes + len(rohdaten) > self._max_bytes
            ):
                self._entfernen(next(iter(self._cache)))
            self._cache[key] = _Eintrag(
                rohdaten=rohdaten, geholt_at=datetime.now(timezone.utc)
            )
            self._bytes += len(rohdaten)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._bytes = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "total_entries": len(self._cache),
                "total_bytes": self._bytes,
                "ttl_seconds": self._ttl_seconds,
            }

    def _entfernen(self, key: str) -> None:
        """Nur unter gehaltenem Lock aufrufen."""
        eintrag = self._cache.pop(key, None)
        if eintrag is not None:
            self._bytes -= len(eintrag.rohdaten)


_shared: Optional[ThunderWindowCache] = None
_shared_lock = Lock()


def get_shared_thunder_window_cache() -> ThunderWindowCache:
    """Prozessweiter Singleton — nur so teilen zwei aufeinanderfolgende
    Vorhersage-Abrufe (Trip: Etappe fuer Etappe, Ortsvergleich: Ort fuer Ort)
    ueberhaupt ein Fenster. Doppelt gepruefte Erzeugung; der Speicher selbst
    ist bereits lock-geschuetzt."""
    global _shared
    if _shared is None:
        with _shared_lock:
            if _shared is None:
                _shared = ThunderWindowCache()
    return _shared


def reset_thunder_window_cache_for_tests() -> None:
    """Nur fuer Tests: Singleton verwerfen (Isolation zwischen Testfaellen)."""
    global _shared
    with _shared_lock:
        _shared = None
