"""DWD ICON-EU als Gewitter-Lueckenfueller fuer Rest-Europa (#1457 S2c).

Dritte und letzte Scheibe von #1457 (Konzept #1419, Schritt S2). ICON-EU
(~6,5 km Maschenweite) liefert das Blitzpotenzial `lpi_con_max` fuer alle
Gebiete, die weder Meteo-France (S2a, FR/Korsika) noch ICON-D2 (S2b,
DE/Alpen/Oesterreich) abdecken.

SPEC: docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md

WARUM EINE EIGENE DATEI statt Parametrisierung von `dwd.py` (Spec
"Implementation Details" 1): `dwd.py` ist komplett auf ICON-D2 verdrahtet
(BASE_URL, PARAMS, `_build_url` mit fest interpoliertem `icon-d2_germany_`)
und wurde in S2b durch mehrere Adversary-Fix-Loops gehaertet. Derselbe
Schnitt wie zwischen `meteofrance.py` (`fr_direct`) und `dwd.py`
(`de_direct`) wird hier fuer den dritten Provider fortgesetzt.

DIESER PROVIDER LIEFERT NUR GEWITTERSIGNALE — keine Grundvorhersage. Fuer
Temperatur/Wind/Niederschlag bleibt die bestehende Quellenwahl
(`providers.region_routing`) zustaendig; die Gewitter-Zustaendigkeit ist
bewusst eine ZWEITE, groessenabhaengige Tabelle
(`providers.thunder_routing`, ADR-0041 Muster C).

EMPIRISCHE VERMESSUNG DES ECHTEN DIENSTES (2026-08-04, opendata.dwd.de) —
nichts davon ist aus ICON-D2 uebernommen, weil die Analogie bei S2a
(`echotop` -> -999.0) und S2b (vermutete -999.0, tatsaechlich 9999.0)
zweimal in Folge falsch war:

- ABRUFNAME: unter `.../icon-eu/grib/<HH>/` existiert der Ordner
  `lpi_con_max`. Ein Hagel-Pendant zu ICON-D2s `grau_gsp` gibt es NICHT
  (Spec Known Limitation 3) — `hail_potential_grau_gsp` bleibt fuer
  Rest-Europa dauerhaft leer, das ist beabsichtigt.
- DATEINAMEN-SCHEMA: `icon-eu_europe_regular-lat-lon_single-level_
  <YYYYMMDDHH>_<TTT>_LPI_CON_MAX.grib2.bz2` — also `icon-eu_europe_` statt
  `icon-d2_germany_` und ein GROSSGESCHRIEBENES Parameter-Suffix statt
  `_2d_<param>` in Kleinbuchstaben. `dwd._build_url` traegt hier NICHT.
- GITTER: left=-23,53 bottom=29,47 right=62,53 top=70,53 bei 0,0625 Grad,
  657 x 1377 Bildpunkte, float64. Zeitschritte 000..048 stuendlich.
- FEHLWERT: es gibt KEINEN — `dataset.nodata` ist `None`, die Maske leer,
  kein Wert ausserhalb 0..269. ICON-D2s Sentinel 9999.0 wird deshalb
  ausdruecklich NICHT uebernommen; stattdessen wird generisch geprueft, ob
  die Antwort selbst einen Bildpunkt als Fehlwert MARKIERT (Spec AC-2).
- `lpi_con_max` ist laut GRIB-Kopf ein MAXIMUM ueber die letzten 60 Minuten
  (statistischer Prozess 2, Dauer 60 min) — KEIN kumulierter Wert. Die
  Differenzbildung, die `grau_gsp` in S2b braucht, darf hier nicht
  angewandt werden, sonst verschwaende jedes stehende Gewitter.
"""
from __future__ import annotations

import bz2
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

import httpx
from rasterio.io import MemoryFile
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from app.config import Location

logger = logging.getLogger("dwd_eu")

BASE_URL = "https://opendata.dwd.de/weather/nwp/icon-eu/grib/"
TIMEOUT = 30.0

RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2   # seconds
RETRY_WAIT_MAX = 60  # seconds
RETRY_STATUS_CODES = {500, 502, 503, 504}

# Bounded, konstante Anzahl Zeitschritte (24h-Horizont, wie ICON-D2 und der
# FR-MVP) — ein Vorhersagefenster darueber hinaus fragt niemand ab.
FORECAST_HOURS: List[int] = list(range(1, 25))

# Abrufname beim echten Dienst verifiziert (s. Modul-Docstring). Steht
# bewusst als KONSTANTE hier, damit der Live-Test (Spec AC-6) ihn von hier
# liest, statt ihn zu wiederholen — genau diese Naht fehlte bei S2a, wo
# `LITOTA3` beim Dienst gar nicht existierte und trotzdem 24 aufgezeichnete
# Tests gruen blieben.
# #1531: drei Energiegroessen ergaenzt (Spec Implementation Details Punkt 2)
# -- `cape_con` wird abgerufen, aber bewusst KEINEM Modellfeld zugeordnet
# (kein Eintrag in `thunder_enrichment._SIGNAL_ZU_FELD`).
THUNDER_PARAMS = ("lpi_con_max", "cape_ml", "cape_con", "cin_ml")

# Abrufname beim Dienst -> INTERNER Signalname des gemeinsamen Protokolls.
# `lpi_con_max` ist der externe Parametername; nach aussen liefert dieser
# Provider unter demselben Signalschluessel `lpi` wie ICON-D2, weil es
# fachlich dieselbe Groesse (Blitzpotenzial in J/kg) ist. Dadurch greift die
# bestehende Zeile in `thunder_enrichment._SIGNAL_ZU_FELD` unveraendert und
# der gemeinsame Anschluss muss fuer S2c NICHT angefasst werden (Spec AC-9).
# `cape_ml`/`cape_con`/`cin_ml` behalten ihren Abrufnamen 1:1 als Signalname
# -- keine Umbenennung noetig, weil es dieselben Groessen wie bei ICON-D2 sind.
_SIGNAL_KEYS: Dict[str, str] = {
    "lpi_con_max": "lpi",
    "cape_ml": "cape_ml",
    "cape_con": "cape_con",
    "cin_ml": "cin_ml",
}

# Eigenes Zeitbudget der Gewitter-Anreicherung (Spec AC-4). HERGELEITET,
# nicht von den Nachbarn uebernommen (ICON-D2 90 s, Meteo-France 45 s):
#   - Abrufzahl: EIN Signal (`lpi_con_max`), kein Hagel, kein
#     Kumulations-Anker => hoechstens 24 Abrufe. ICON-D2 kommt mit zwei
#     Signalen plus Anker auf bis zu 49, also gut die doppelte Zahl.
#   - Gemessene Latenz je Datei (2026-08-04, 6 kalte Abrufe): 0,043-0,069 s
#     Download (~100-180 KB) + 0,035 s bz2-Entpacken/rasterio = ~0,085 s.
#   - Regelfall damit 24 x 0,085 s ~ 2,0 s.
#   - Sicherheitsfaktor 10 fuer schlechte Netzlage/langsame Gegenstelle:
#     24 x 0,85 s ~ 20 s, plus 5 s Puffer fuer eine Retry-Runde.
# Fest, nicht rollend (Lehre #1448): EINMAL je Abruf gebildet, dann vor
# JEDEM Einzel-Call geprueft. Getrennt vom Budget der Grundvorhersage, die
# dieser Provider ohnehin nicht liefert — die Anreicherung ist best effort
# und darf fremde Budgets weder teilen noch anknabbern.
THUNDER_FETCH_DEADLINE_SECONDS = 25.0

# Sicherheitsabstand zum juengsten Lauf. GEMESSEN 2026-08-04 07:32 UTC: der
# 03Z-Lauf war veroeffentlicht (~4,5 h alt), der 06Z-Lauf noch nicht (~1,5 h);
# der 00Z-Lauf war um 03:37 UTC vollstaendig (~3,6 h). ICON-EU braucht damit
# 3,6-4,5 h — deutlich laenger als ICON-D2 (~1,4 h), dessen 3 h Abstand hier
# NICHT reichen. Weil Laeufe nur alle 3 h existieren, ist der naechste
# tragfaehige Rasterwert oberhalb von 4,5 h die 6. Der Rueckfall unten
# federt den Rest ab (Spec AC-7).
THUNDER_RUN_SAFETY_HOURS = 6

# Rueckfall auf hoechstens zwei weitere, je 3h aeltere Laeufe (Spec AC-7).
THUNDER_RUN_FALLBACK_STAGES = 2

# Groesster Zeitschritt, den ICON-EU stuendlich veroeffentlicht (gemessen:
# 000..048; darueber nur noch dreistuendig, was fuer Stundenwerte nichts
# taugt). Darueber hinaus wird gar nicht erst abgerufen.
THUNDER_MAX_TIMESTEP = 48


def _is_retryable_error(exception: BaseException) -> bool:
    """Muster `dwd._is_retryable_error`: retryable bei 500/502/503/504 +
    Verbindungsfehlern. 4xx bleibt sichtbar (ADR-0018) — insbesondere 404,
    das den Lauf-Rueckfall ausloest und nie durch Retries verzoegert werden
    darf."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


def _latest_run(now: datetime, safety_hours: int = THUNDER_RUN_SAFETY_HOURS) -> datetime:
    """Juengster ICON-EU-Lauf (alle 3 h) mit Sicherheitsabstand, damit die
    Antwort tatsaechlich schon veroeffentlicht ist (s.
    `THUNDER_RUN_SAFETY_HOURS`)."""
    floored_hour = (now.hour // 3) * 3
    run = now.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    return run - timedelta(hours=safety_hours)


def _thunder_run_candidates(now: datetime) -> List[datetime]:
    """Kandidaten-Laeufe, juengster zuerst (Spec AC-7). Antwortet Index 0 mit
    404, wird auf bis zu `THUNDER_RUN_FALLBACK_STAGES` weitere, je 3 h
    aeltere Laeufe zurueckgefallen. Der Nullpunkt der Stunden-Offsets bleibt
    davon UNBERUEHRT — er haengt am gewuenschten Zeitfenster, nicht am Lauf
    (sonst stuende ein Gewitter beim Rueckfall Stunden zu frueh)."""
    primaer = _latest_run(now)
    return [
        primaer - timedelta(hours=3 * stufe)
        for stufe in range(THUNDER_RUN_FALLBACK_STAGES + 1)
    ]


def _as_utc(ts: datetime) -> datetime:
    """Zeitstempel auf UTC-bewusst bringen; naive Werte gelten als UTC."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _thunder_offsets(base: datetime, end: Optional[datetime]) -> List[int]:
    """Abzurufende Stunden-Offsets ab `base` (Muster `dwd._thunder_offsets`).

    Ohne `end` bleibt es beim vollen 24h-Horizont. Liegt `end` vor `base`,
    ist nichts abzurufen — fuer vergangene Stunden gibt es keine
    Vorhersage."""
    if end is None:
        return list(FORECAST_HOURS)
    spanne_h = (_as_utc(end) - base).total_seconds() / 3600.0
    if spanne_h <= 0:
        return []
    letzter = min(math.ceil(spanne_h), FORECAST_HOURS[-1])
    return list(range(1, letzter + 1))


def _build_url(run: datetime, offset: int, param: str) -> str:
    """URL-Template ICON-EU (gemessen, s. Modul-Docstring):
    <BASE_URL><HH>/<param>/icon-eu_europe_regular-lat-lon_single-level_
    <YYYYMMDDHH>_<TTT>_<PARAM>.grib2.bz2

    Das Parameter-Suffix steht GROSS — anders als bei ICON-D2, wo es
    `_2d_<param>` klein heisst. Wird es hier klein geschrieben, antwortet
    der Dienst mit 404 und jeder Abruf laeuft lautlos ins Leere."""
    hh = f"{run.hour:02d}"
    run_str = run.strftime("%Y%m%d%H")
    ttt = f"{offset:03d}"
    return (
        f"{BASE_URL}{hh}/{param}/icon-eu_europe_regular-lat-lon_"
        f"single-level_{run_str}_{ttt}_{param.upper()}.grib2.bz2"
    )


def _read_point_value(compressed: bytes, lat: float, lon: float) -> Optional[float]:
    """Entpackt eine `.grib2.bz2`-Antwort und liest den Bildpunkt von Band 1
    an (lat, lon).

    Drei Faelle ergeben ausdruecklich `None` statt einer Zahl (Spec AC-2 —
    "keine Aussage" ist nicht "keine Gefahr"):

    1. Der Ort liegt AUSSERHALB des gelieferten Gitters. Anders als
       `dwd._read_point_value` wird hier NICHT auf den Randbildpunkt geklemmt:
       die Gewitter-Zustaendigkeit von ICON-EU ist ein Catch-all fuer den
       ganzen Rest der Welt, und ein geklemmter Randwert waere fuer einen Ort
       ausserhalb Europas eine frei erfundene Messung.
    2. Der Bildpunkt ist von der Antwort selbst als FEHLWERT markiert
       (`dataset.nodata`). Geprueft wird die Markierung, NICHT eine feste
       Zahl: ICON-EU traegt gemessen gar keinen Sentinel, und ICON-D2s
       9999.0 hierher zu uebernehmen waere der dritte Analogieschluss in
       Folge, der sich als falsch erweist.
    3. Der Wert ist NaN.
    """
    try:
        raw = bz2.decompress(compressed)
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            if not (0 <= row < dataset.height and 0 <= col < dataset.width):
                return None
            wert = float(dataset.read(1)[row, col])
            nodata = dataset.nodata
            if math.isnan(wert):
                return None
            if nodata is not None and not math.isnan(nodata) and wert == nodata:
                return None
            return wert
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


def _thunder_budget_erschoepft(deadline_at: float) -> bool:
    """Zeitgrenze der Gewitter-Anreicherung (Spec AC-4), fest gebildet und vor
    JEDEM Einzel-Call geprueft."""
    if time.monotonic() <= deadline_at:
        return False
    logger.warning(
        "ICON-EU-Gewitterbudget (%.0fs) erschoepft — Anreicherung bricht ab, "
        "Grundvorhersage unberuehrt",
        THUNDER_FETCH_DEADLINE_SECONDS,
    )
    return True


class DwdEuDirectProvider:
    """`eu_direct`: ICON-EU-Blitzpotenzial fuer alle Gebiete ohne feinere
    Gewitterquelle. Registriert in `providers.base._load_providers`.

    Erfuellt bewusst NUR das Gewittersignal-Protokoll
    (`providers.base.ThunderSignalProvider`) — kein `fetch_forecast`. Wer
    diesen Provider als Grundvorhersage-Quelle einsetzen wollte, bekaeme
    einen AttributeError statt einer stillen Halb-Antwort.
    """

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def name(self) -> str:
        return "eu_direct"

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(self, url: str) -> bytes:
        """GET mit Retry (500/502/503/504 + Verbindungsfehler, 5 Versuche,
        2-60 s Backoff; 4xx bleibt sichtbar, ADR-0018)."""
        response = self._client.get(url)
        if response.status_code in RETRY_STATUS_CODES:
            response.raise_for_status()  # loest Retry via HTTPStatusError aus
        response.raise_for_status()      # nicht-retryable Fehler (4xx)
        return response.content

    def _thunder_point(
        self, param: str, lat: float, lon: float, ziel: datetime,
        kandidaten: List[datetime], zustand: Dict[str, object],
    ) -> Optional[float]:
        """EIN Punktwert zum absoluten Zeitpunkt `ziel`.

        Rueckfall auf einen aelteren Lauf (Spec AC-7) NUR, solange noch kein
        Lauf durch eine erfolgreiche Antwort bestaetigt ist. Danach ist ein
        404 kein "Lauf fehlt", sondern eine einzelne fehlende Stunde — die
        bleibt `None` und darf nicht die ganze Reihe auf einen anderen Lauf
        verschieben (Spec AC-2).
        """
        while True:
            lauf = kandidaten[int(zustand["index"])]
            ttt = int((ziel - lauf).total_seconds() // 3600)
            if ttt < 0 or ttt > THUNDER_MAX_TIMESTEP:
                return None
            try:
                raw = self._request(_build_url(lauf, ttt, param))
            except httpx.HTTPStatusError as e:
                weiterer_kandidat = (
                    e.response.status_code == 404
                    and not zustand["bestaetigt"]
                    and int(zustand["index"]) < len(kandidaten) - 1
                )
                if not weiterer_kandidat:
                    logger.warning(
                        "ICON-EU-Signal '%s' +%dh nicht abrufbar: %s",
                        param, ttt, e,
                    )
                    return None
                zustand["index"] = int(zustand["index"]) + 1
                logger.warning(
                    "ICON-EU-Lauf %s nicht verfuegbar (404) — Rueckfall auf %s",
                    lauf.strftime("%Y%m%d%H"),
                    kandidaten[int(zustand["index"])].strftime("%Y%m%d%H"),
                )
                continue
            except Exception as e:
                logger.warning(
                    "ICON-EU-Signal '%s' +%dh nicht abrufbar: %s", param, ttt, e
                )
                return None
            zustand["bestaetigt"] = True
            return _read_point_value(raw, lat, lon)

    def fetch_thunder_signals_named(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, Dict[int, Optional[float]]]:
        """Blitzpotenzial je Stunden-Offset unter dem Signalnamen `lpi`.

        Best effort, fail-soft — wirft NIE (Spec AC-3): ein Ausfall der
        Gewitterquelle darf die Grundvorhersage nicht kippen.

        Returns:
            `{"lpi": {Stunden-Offset ab `start`: Wert oder None}}`. Ohne
            `start` gilt der gewaehlte Lauf als Bezug. Fehlender Wert bleibt
            `None`, NIE 0 (Spec AC-2).

        Ein Request je Zeitschritt — ICON-EU kennt keinen serverseitigen
        Punkt-Query. Ein Sammelabruf ueber mehrere Orte braucht es nicht:
        jede Datei deckt ohnehin das ganze Modellgebiet ab.

        KEINE Differenzbildung: `lpi_con_max` ist ein Stunden-MAXIMUM, kein
        kumulierter Wert (s. Modul-Docstring).
        """
        ergebnis: Dict[str, Dict[int, Optional[float]]] = {
            _SIGNAL_KEYS[param]: {} for param in THUNDER_PARAMS
        }
        try:
            now = datetime.now(timezone.utc)
            # Nullpunkt der Offsets: das gewuenschte Zeitfenster, nie vor dem
            # Lauf (davor gibt es keine Vorhersage). Bleibt beim Rueckfall auf
            # einen aelteren Lauf unveraendert (Spec AC-7).
            run = _latest_run(now)
            base = run if start is None else max(_as_utc(start), run)
            offsets = _thunder_offsets(base, end)
            kandidaten = _thunder_run_candidates(now)
            lat, lon = location.latitude, location.longitude
            zustand: Dict[str, object] = {"index": 0, "bestaetigt": False}
            deadline_at = time.monotonic() + THUNDER_FETCH_DEADLINE_SECONDS
            for param in THUNDER_PARAMS:
                reihe: Dict[int, Optional[float]] = {}
                for offset in offsets:
                    if _thunder_budget_erschoepft(deadline_at):
                        break
                    reihe[offset] = self._thunder_point(
                        param, lat, lon, base + timedelta(hours=offset),
                        kandidaten, zustand,
                    )
                ergebnis[_SIGNAL_KEYS[param]] = reihe
        except Exception:
            logger.warning("ICON-EU-Gewitterabruf fehlgeschlagen", exc_info=True)
        return ergebnis

    def fetch_thunder_signals(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[int, Optional[float]]:
        """Pflichtteil des Protokolls `base.ThunderSignalProvider`: EIN Signal
        je Stunden-Offset. Duenner Griff in das benannte Ergebnis — EIN
        Abrufweg, der nicht auseinanderdriften kann (Muster
        `dwd.fetch_thunder_signals`)."""
        return self.fetch_thunder_signals_named(location, start, end).get(
            _SIGNAL_KEYS[THUNDER_PARAMS[0]], {}
        )
