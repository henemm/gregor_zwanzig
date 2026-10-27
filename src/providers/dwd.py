"""
DWD ICON-D2 Direct Provider (#1144, Slice 3/4 von Epic #1127).

Echter `de_direct`-Provider für den Cross-Provider-Fallback (#1141): ruft die
öffentliche ICON-D2-Open-Data-API (`opendata.dwd.de`, 2,2-km-Gitter,
Deutschland) direkt ab und liest die entpackten GRIB2-Antworten mit dem
bereits im Projekt vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue
Dependency, #1143).

SPEC: docs/specs/modules/provider_dwd.md v1.0
Vorlage: src/providers/meteofrance.py (Retry-Muster, Vektor->Speed-Formel,
GRIB2-Pixel-Lookup).

ICON-D2-Open-Data-Eigenheiten (empirisch verifiziert 2026-07-23):
- Anders als bei AROME-WCS (#1143) gibt es KEINEN serverseitigen Punkt-Query
  — pro Parameter/Zeitschritt wird eine eigene, volle Rasterdatei
  (`.grib2.bz2`) geladen, 1 GET-Request je Datei. Bounded: 24h-Horizont
  (PO-Entscheidung 2026-07-23), 4 Parameter x 24 Zeitschritte = ~96 Calls
  pro Fetch — ausschließlich im Total-Ausfall-Fallback-Pfad.
- `t_2m`-Rohwert ist bereits °C, KEINE Kelvin-Umrechnung (GDAL-Tag
  `GRIB_UNIT=[C]`, empirisch bestätigt: München-Rohwert 18.11 an einem
  Sommerabend — als Kelvin wäre das -255°C, physikalisch unmöglich).
- `tot_prec` ist seit Laufbeginn kumuliert (wachsende `lengthOfTimeRange`
  0/60/120min stützt die Kumulations-Annahme). `precip_1h_mm` wird daher
  als Differenz aufeinanderfolgender Zeitschritte gebildet, NICHT wie bei
  AROME (#1143 F003) direkt übernommen — dort war der Rohwert bereits die
  1h-Regenmenge, hier nicht. Beweis (Ostsee-Küstenzelle 53.70N/14.94E,
  Lauf 2026-07-22T21Z): prev(+3h)=3.14, curr(+4h)=15.49, Differenz=12.35mm
  (kräftiger Landregen, plausibel).
"""
from __future__ import annotations

import bz2
import logging
import math
import threading
import time
import contextvars
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import httpx
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import rowcol
from rasterio.windows import Window
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from providers.base import ProviderRequestError, ThunderSourceUnavailableError
from providers.enrichment_health import (
    OUTCOME_FALLBACK,
    OUTCOME_OK,
    PATH_THUNDER_BUDGET,
    log_enrichment_call,
)
from providers.http import (
    capped_timeout_or_raise,
    make_deadline_before_hook,
    stop_at_deadline,
)

if TYPE_CHECKING:
    from app.config import Location

logger = logging.getLogger("dwd")

BASE_URL = "https://opendata.dwd.de/weather/nwp/icon-d2/grib/"
# #2439: Produktionswert, festgehalten fuer die Test-Naht des Vorwaermens
# (Kernsuite mit Fixture-Verzeichnis und unveraendertem BASE_URL: kein Netz).
PRODUKTIV_BASE_URL = BASE_URL
TIMEOUT = 30.0

RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2   # seconds
RETRY_WAIT_MAX = 60  # seconds
RETRY_STATUS_CODES = {500, 502, 503, 504}

# Gesamt-Zeitbudget je fetch_forecast (analog meteofrance.py F004): bis zu
# 96 sequentielle Calls x bis zu 5 Retries x 2-60s Backoff wären ohne
# Deadline theoretisch sehr lange möglich.
FETCH_DEADLINE_SECONDS = 180.0

# Bounded, konstante Anzahl Zeitschritte je Parameter (24h-Horizont,
# PO-Tech-Lead-Entscheidung 2026-07-23, analog dem FR-MVP-Vorbild).
FORECAST_HOURS: List[int] = list(range(1, 25))

PARAMS = ("t_2m", "u_10m", "v_10m", "tot_prec")

# --- Gewittersignale (#1457 S2b) ------------------------------------------
# Abrufnamen beim echten Dienst verifiziert (2026-08-03): unter
# `.../icon-d2/grib/<HH>/` existieren die Ordner `lpi` und `grau_gsp`, das
# Dateinamensmuster ist identisch zu den vier Basis-Parametern oben. Sie
# stehen bewusst als KONSTANTE hier, damit der Live-Test (Spec AC-6) sie von
# hier liest, statt sie zu wiederholen — genau diese Naht fehlte bei S2a
# (`LITOTA3` existierte beim Dienst nicht, jeder Abruf lief lautlos in 404).
# Reihenfolge = Reihenfolge der Signale; Index 0 ist das Signal, das der
# Einzelwert-Pflichtteil des Protokolls liefert. Reihenfolge = Ausfallreihen-
# folge bei Budget-Ende (#1531, Spec AC-7): `lpi`, `grau_gsp`, `cin_ml` stehen
# vorn, damit sie bei erschoepftem Budget sicher schon abgerufen sind.
# `uh_max_med` steht bewusst vor `uh_max`/`uh_max_low` -- die einzigen
# publizierten Schwellen (SPC 75/150 m^2/s^2) beziehen sich auf die Schicht
# 2-5 km, also auf `uh_max_med` (Spec Implementation Details Punkt 2).
THUNDER_PARAMS = (
    "lpi", "grau_gsp", "cin_ml", "sdi_2", "cape_ml", "lpi_max",
    "uh_max_med", "uh_max", "uh_max_low",
)

# `grau_gsp` ist seit Laufbeginn KUMULIERT (empirisch 2026-08-03, Zelle
# 45,94N/7,86O: ab +8h konstant 3,3035 ueber +12/+16/+20/+24h) — exakt wie
# `tot_prec`. Der Rohwert ist damit kein Stunden-Signal und wird ueber
# `_precip_series_from_cumulative` zurueckgerechnet. `lpi` ist ein
# Momentanwert und bleibt unveraendert.
THUNDER_CUMULATIVE_PARAMS = ("grau_gsp",)

# Fuellwert ausserhalb des Modellgebiets, gemessen (rasterio `dataset.nodata`)
# — 9999.0, NICHT -999.0 (der `echotop`-Analogieschluss traegt hier nicht).
# Das ausgelieferte `regular-lat-lon`-Rechteck ist rund 17 % groesser als das
# Modellgebiet; ohne diese Abbildung stuende 9999 als Blitzpotenzial in der
# Vorhersage — eine erfundene Extremlage (Spec AC-2).
THUNDER_FILL_VALUE = 9999.0

# Eigenes Zeitbudget der Gewitter-Anreicherung (Spec AC-4), BEWUSST getrennt
# von FETCH_DEADLINE_SECONDS: die Anreicherung ist best effort und darf das
# Budget der Grundvorhersage weder teilen noch anknabbern. Herleitung analog
# meteofrance.py:114 — dort 180s fuer 96 Calls, also ~1,9s je Call; fuer die
# bis zu 48 zusaetzlichen Calls hier ergibt das 90s. Fest, nicht rollend
# (Lehre #1448): EINMAL je Abruf gebildet, dann vor jedem Einzel-Call geprueft.
# #1531: 9 statt 2 Signale x 24h ergibt bis zu 216 Abrufe (Regelfall ~52s,
# gemessen 0,24s je Abruf) -- auf 150s angehoben (PO-Entscheid 2026-08-08),
# damit auch ein langsamer Lauf traegt.
THUNDER_FETCH_DEADLINE_SECONDS = 150.0

# Rueckfall auf hoechstens zwei aeltere Laeufe (je 3h), macht bis zu 6h
# zurueck ab dem bereits 3h zurueckgesetzten `_latest_run` (Spec AC-7). Ein
# GROESSERER Grundabstand ist beim DWD nicht noetig (gemessen 2026-08-03: der
# Lauf 15:00Z war um 16:22 UTC vollstaendig veroeffentlicht, ~1h22); der
# Rueckfall federt aber den unguenstigsten Fall ab, in dem `_latest_run` nur
# 3h Abstand haelt und eine Verzoegerung beim DWD ihn aufzehrt.
THUNDER_RUN_FALLBACK_STAGES = 2

# Groesster Zeitschritt, den ICON-D2 je Lauf veroeffentlicht (gemessen:
# 000..048, stuendlich). Darueber hinaus wird gar nicht erst abgerufen.
THUNDER_MAX_TIMESTEP = 48

# #2554: Gewitter-Downloads bekommen einen eigenen, strengeren Abrufweg -- bei
# langsamem DWD (Stoerung 12.10.: 151-170s je Abruf) verbrannte der Grund-
# Timeout (30s, 5 Versuche) das 150s-Budget nach 1-2 Zeitpunkten. Ein haengender
# Einzelabruf kostet hoechstens THUNDER_REQUEST_TIMEOUT, ein ReadTimeout wird
# NICHT wiederholt. Je Zeitpunkt laufen bis zu THUNDER_PARALLEL_DOWNLOADS
# Downloads gleichzeitig (Reihenfolge der Groessen bleibt, #1531 AC-7).
THUNDER_REQUEST_TIMEOUT = 10.0
THUNDER_RETRY_ATTEMPTS = 2
THUNDER_PARALLEL_DOWNLOADS = 5
# #2439: Vorwaermen der Tagesfenster (hoechstens so viele FENSTER gleichzeitig,
# jedes Fenster nutzt intern weiter THUNDER_PARALLEL_DOWNLOADS) und Gesamtfrist.
THUNDER_PREWARM_PARALLEL_WINDOWS = 2
THUNDER_PREWARM_DEADLINE_SECONDS = 40.0


def _is_retryable_error(exception: BaseException) -> bool:
    """1:1-Muster meteofrance.py: retryable bei 500/502/503/504 +
    Connection-Errors."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


def _is_thunder_retryable_error(exception: BaseException) -> bool:
    """#2554: wie `_is_retryable_error`, aber OHNE ReadTimeout -- ein Server,
    der THUNDER_REQUEST_TIMEOUT lang geschwiegen hat, erholt sich innerhalb des
    Abrufs selten; ein zweiter Versuch wuerde den Haenger verdoppeln."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    return isinstance(exception, httpx.ConnectError)


def _vector_to_speed_kmh(u: float, v: float) -> float:
    """AC-6: U/V-Windkomponenten (m/s) -> Betrag in km/h, ident zu
    meteofrance._vector_to_speed_kmh."""
    speed_ms = math.sqrt(u**2 + v**2)
    return round(speed_ms * 3.6, 1)


def _latest_run(now: datetime) -> datetime:
    """Jüngster ICON-D2-Lauf (alle 3h) mit Sicherheitsabstand, damit die
    Antwort tatsächlich veröffentlicht ist (analog meteofrance._latest_run)."""
    floored_hour = (now.hour // 3) * 3
    run = now.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    return run - timedelta(hours=3)


def _thunder_run_candidates(now: datetime) -> List[datetime]:
    """Kandidaten-Laeufe fuer die Gewittersignale, juengster zuerst (Spec
    AC-7). Index 0 ist derselbe Lauf wie fuer die Grundvorhersage; antwortet
    er mit 404, wird auf bis zu `THUNDER_RUN_FALLBACK_STAGES` weitere, je 3h
    aeltere Laeufe zurueckgefallen. Der Nullpunkt der Stunden-Offsets bleibt
    davon unberuehrt — er haengt am gewuenschten Zeitfenster, nicht am Lauf
    (sonst stuende ein Gewitter beim Rueckfall drei Stunden zu frueh)."""
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
    """Abzurufende Stunden-Offsets ab `base` (Muster meteofrance).

    Ohne `end` bleibt es beim vollen 24h-Horizont. Liegt `end` vor `base`,
    ist nichts abzurufen — fuer vergangene Stunden gibt es keine Vorhersage."""
    if end is None:
        return list(FORECAST_HOURS)
    spanne_h = (_as_utc(end) - base).total_seconds() / 3600.0
    if spanne_h <= 0:
        return []
    letzter = min(math.ceil(spanne_h), FORECAST_HOURS[-1])
    return list(range(1, letzter + 1))


def _build_url(run: datetime, offset: int, param: str) -> str:
    """URL-Template (SPEC): <BASE_URL><HH>/<param>/icon-d2_germany_regular-
    lat-lon_single-level_<YYYYMMDDHH>_<TTT>_2d_<param>.grib2.bz2"""
    hh = f"{run.hour:02d}"
    run_str = run.strftime("%Y%m%d%H")
    ttt = f"{offset:03d}"
    return (
        f"{BASE_URL}{hh}/{param}/icon-d2_germany_regular-lat-lon_"
        f"single-level_{run_str}_{ttt}_2d_{param}.grib2.bz2"
    )


CIN_ML_LOWER_SENTINEL = -999.9

def _read_point_value(
    compressed: bytes, lat: float, lon: float, param: Optional[str] = None,
) -> Optional[float]:
    """Entpackt eine `.grib2.bz2`-Antwort und liest den Pixelwert von Band 1
    an (lat, lon) — Muster meteofrance._read_point_value, ergänzt um den
    `bz2.decompress`-Schritt (ICON-D2 liefert komprimiert, AROME-WCS nicht).

    #1354: Der Fuellwert ausserhalb des Modellgebiets wird hier ZENTRAL zu
    `None` — sonst stuende er als echter Messwert in der Vorhersage. Quelle
    der Wahrheit ist `dataset.nodata`; ist es nicht gesetzt, traegt der
    bekannte Sentinel. Vergleich `>=`: echte Messwerte erreichen diese
    Groessenordnung nie.

    #1531 Spec Implementation Details Punkt 3: `cin_ml` traegt einen ZWEITEN
    Fehlwert-Marker nach UNTEN (-999,9, gemessen bei 46 % der Gitterpunkte).
    Die Pruefung ist JE PARAMETER gefuehrt, nicht global -- ein anderer
    Parameter mit einem echten Wert um -999,9 waere sonst faelschlich
    verworfen (Analogieschluss-Warnung dwd_eu.py)."""
    try:
        raw = bz2.decompress(compressed)
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            row = min(max(row, 0), dataset.height - 1)
            col = min(max(col, 0), dataset.width - 1)
            wert = float(dataset.read(1)[row, col])
            return _filtere_fuellwert(wert, _sentinel_of(dataset), param)
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


def _sentinel_of(dataset) -> float:
    """Fuellwert-Grenze: `dataset.nodata`, sonst der bekannte Sentinel (#1354)."""
    return float(dataset.nodata) if dataset.nodata is not None else THUNDER_FILL_VALUE


def _filtere_fuellwert(wert: float, sentinel: float, param: Optional[str]) -> Optional[float]:
    """Gemeinsame Fuellwert-Regeln fuer Direkt- und Fenster-Lesen (#1354, #1531):
    ein Fuellwert wird ZENTRAL zu `None`, nie als Messwert durchgereicht."""
    if wert >= sentinel:
        return None
    if param == "cin_ml" and wert <= CIN_ML_LOWER_SENTINEL:
        return None
    return wert


# --- Punkt-Fenster-Cache (#2465) ---------------------------------------------
# Jede ICON-D2-Rasterdatei deckt das GANZE Modellgebiet ab; die Segmente eines
# Trips unterscheiden sich nur im Pixel. Ohne Cache lud und entpackte jedes
# Segment dieselben ~217 Dateien erneut (gemessen 2026-09-30: 1302 GETs / 866 MB
# je Trip-Lauf bei 217 eindeutigen URLs) — der Alarmlauf riss sein 90-s-Budget
# und pruefte stundenlang nur 2 von 4 Trips.
#
# Gecacht wird NICHT die Datei (komprimiert bis 665 kB, entpackt 7 MB: 217 Stueck
# waeren 144 MB bzw. 1,6 GB), sondern je URL nur ein kleiner Pixel-Ausschnitt
# um den angefragten Punkt (41x41 Pixel float64 = 13,4 kB, gemessen; Obergrenze
# 512 URLs x 8 Ausschnitte = ca. 55 MB). Die URL haengt NICHT vom Standort ab
# (Lauf/Parameter/Zeitschritt), 512 reichen also fuer ~2 Modelllaeufe; die
# Ausschnitte je URL fangen raeumlich getrennte Trips ab (ein Ausschnitt deckt
# ~0,8 Grad, ~90 km). Bei mehr als 8 weit entfernten Gruppen je URL arbeitet der
# Cache gegen die LRU (zyklischer Zugriff) — dann laeuft es wie vor dem Fix.
# float64 bleibt bewusst: nur so sind
# die Werte bit-identisch zum Direktlesen. Das spart Download UND
# Entpacken (gemessen ~59 ms je Datei). Alle Segmente eines Trips liegen im
# selben Gebiet und bedienen sich aus demselben Ausschnitt; ein weit entfernter
# Punkt legt einen zweiten Ausschnitt an. Werte sind bit-identisch zum
# Direktlesen (`_read_point_value`) — dieselben Pixel, dieselben Fuellwert-Regeln.
#
# Nur ERFOLGE werden gecacht (Fehlschlaege/404 nie: ein noch nicht veroeffent-
# lichter Lauf kann spaeter erscheinen). Die URL kodiert Lauf, Parameter und
# Zeitschritt; eine veroeffentlichte Datei aendert sich nicht -> kein TTL noetig,
# alte Laeufe altern ueber die LRU-Begrenzung aus.
_RASTER_WINDOW_HALF = 20
# #2439: 512 -> 2048 URLs (ein Trip braucht ~415 Dateien; parallele Alarm- und
# Ortsvergleichslaeufe duerften den Vorwaerm-Bestand sonst mitten im Lauf
# verdraengen). Ein Ausschnitt je URL ~13,5 kB: 2048 URLs ~ 28 MB. Damit auch
# der Worst Case (8 Ausschnitte je URL) hart begrenzt bleibt, gilt zusaetzlich ein
# Gesamtbudget an Ausschnitten ueber alle URLs: 2800 x 13,5 kB ~ 38 MB (< 40 MB).
_RASTER_CACHE_MAX_URLS = 2048
_RASTER_CACHE_MAX_WINDOWS_PER_URL = 8
_RASTER_CACHE_MAX_WINDOWS_TOTAL = 2800


@dataclass(frozen=True, eq=False)
class _RasterWindow:
    """Pixel-Ausschnitt einer Rasterdatei samt Georeferenz. `eq=False`: Identitaet
    statt Feldvergleich — ein `==` ueber die numpy-Arrays wirft bei unter-
    schiedlichen Formen einen ValueError."""

    array: "np.ndarray"
    row0: int
    col0: int
    transform: object
    height: int
    width: int
    sentinel: float

    def _cell(self, lat: float, lon: float) -> Optional[Tuple[int, int]]:
        """Index im Ausschnitt oder None, wenn der Punkt ausserhalb liegt.
        Gleiche Zuordnung und Randklemmung wie `_read_point_value`."""
        row, col = rowcol(self.transform, lon, lat)
        row = min(max(int(row), 0), self.height - 1)
        col = min(max(int(col), 0), self.width - 1)
        i, j = row - self.row0, col - self.col0
        if 0 <= i < self.array.shape[0] and 0 <= j < self.array.shape[1]:
            return i, j
        return None

    def contains(self, lat: float, lon: float) -> bool:
        return self._cell(lat, lon) is not None

    def value_at(self, lat: float, lon: float, param: Optional[str]) -> Optional[float]:
        cell = self._cell(lat, lon)
        if cell is None:
            return None
        return _filtere_fuellwert(float(self.array[cell]), self.sentinel, param)


def _decode_window(
    compressed: bytes, lat: float, lon: float,
) -> Optional[_RasterWindow]:
    """Entpackt die Datei EINMAL und behaelt nur den Ausschnitt um (lat, lon).
    Parsing-Fehler -> None (nicht cachebar), wie `_read_point_value`."""
    try:
        raw = bz2.decompress(compressed)
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            row = min(max(row, 0), dataset.height - 1)
            col = min(max(col, 0), dataset.width - 1)
            row0 = max(row - _RASTER_WINDOW_HALF, 0)
            col0 = max(col - _RASTER_WINDOW_HALF, 0)
            row1 = min(row + _RASTER_WINDOW_HALF + 1, dataset.height)
            col1 = min(col + _RASTER_WINDOW_HALF + 1, dataset.width)
            array = dataset.read(
                1, window=Window(col0, row0, col1 - col0, row1 - row0)
            )
            return _RasterWindow(
                array=array, row0=row0, col0=col0, transform=dataset.transform,
                height=dataset.height, width=dataset.width,
                sentinel=_sentinel_of(dataset),
            )
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


class _PointWindowCache:
    """Prozessweiter, begrenzter LRU-Cache: URL -> Pixel-Ausschnitte (#2465).
    Thread-sicher (Briefing- und Alarm-Lauf teilen sich den Prozess)."""

    def __init__(
        self,
        max_urls: int = _RASTER_CACHE_MAX_URLS,
        max_windows_per_url: int = _RASTER_CACHE_MAX_WINDOWS_PER_URL,
        max_windows_total: int = _RASTER_CACHE_MAX_WINDOWS_TOTAL,
    ) -> None:
        self._max_urls = max_urls
        self._max_windows = max_windows_per_url
        self._max_total = max_windows_total
        self._lock = threading.Lock()
        self._data: "OrderedDict[str, List[_RasterWindow]]" = OrderedDict()

    def find(self, url: str, lat: float, lon: float) -> Optional[_RasterWindow]:
        with self._lock:
            fenster = self._data.get(url)
            if fenster is None:
                return None
            self._data.move_to_end(url)
            for index, kandidat in enumerate(fenster):
                if kandidat.contains(lat, lon):
                    # Treffer = juengst benutzt: ans Ende, damit die Verdraengung
                    # innerhalb einer URL LRU ist und nicht FIFO.
                    fenster.append(fenster.pop(index))
                    return kandidat
            return None

    def put(self, url: str, window: _RasterWindow) -> None:
        with self._lock:
            liste = self._data.setdefault(url, [])
            # Zwei Laeufe, die gleichzeitig danebengreifen (Briefing + Alarm um
            # :00), legen sonst denselben Ausschnitt doppelt ab und verbrauchen
            # zwei der wenigen Plaetze je URL.
            if any(w.row0 == window.row0 and w.col0 == window.col0 for w in liste):
                self._data.move_to_end(url)
                return
            liste.append(window)
            if len(liste) > self._max_windows:
                del liste[0]
            self._data.move_to_end(url)
            while len(self._data) > self._max_urls or (
                len(self._data) > 1
                and sum(len(w) for w in self._data.values()) > self._max_total
            ):
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


_RASTER_CACHE = _PointWindowCache()


def _precip_series_from_cumulative(
    raw_by_offset: Dict[int, Optional[float]],
    ndigits: int = 1,
    vorwert: Optional[float] = 0.0,
) -> Dict[int, Optional[float]]:
    """AC-5: `tot_prec` ist seit Laufbeginn kumuliert — precip_1h_mm[t] ist
    die Differenz zum vorherigen Zeitschritt.

    `vorwert` ist der kumulierte Stand UNMITTELBAR VOR dem ersten Eintrag in
    `raw_by_offset`. Fuer die Grundvorhersage (`fetch_forecast`) ist das der
    Laufbeginn selbst, also 0.0 — dort faengt die Reihe immer bei Zeitschritt
    1 an. Fuer den Gewitterpfad stimmt diese Annahme NICHT: dort haengt der
    Nullpunkt am gewuenschten Zeitfenster, der erste abgerufene Zeitschritt
    liegt in der Praxis mehrere Stunden nach dem Lauf und traegt schon die
    Kumulation dieser Stunden. Deshalb wird der Anker dort echt abgerufen
    (s. `fetch_thunder_signals_named`).

    `vorwert=None` heisst "der Stand davor ist unbekannt": dann bleibt der
    erste Eintrag `None`, statt eine falsche Differenz zu behaupten (AC-2 —
    keine Aussage ist nicht keine Gefahr). Ab dem zweiten Eintrag rechnet die
    Reihe wieder normal weiter.

    #1457 S2b: dieselbe Rechnung gilt fuer das Hagelsignal `grau_gsp`, das
    ebenfalls seit Laufbeginn kumuliert ist. `ndigits` steuert nur die
    Rundung — der Default 1 haelt das Verhalten fuer den Niederschlag
    unveraendert, das Hagelsignal braucht mehr Stellen, weil dort schon
    Hundertstel eine Aussage tragen und auf eine Stelle gerundet still
    verschwaenden."""
    result: Dict[int, Optional[float]] = {}
    prev_cumulative = vorwert
    for offset in sorted(raw_by_offset):
        raw = raw_by_offset[offset]
        if raw is None:
            result[offset] = None
            continue
        result[offset] = (
            None if prev_cumulative is None
            else max(0.0, round(raw - prev_cumulative, ndigits))
        )
        prev_cumulative = raw
    return result


_BUDGET_ENDE = object()  # Marke: Budget war vor dem Download erschoepft (#2554)


def _thunder_budget_erschoepft(deadline_at: float) -> bool:
    """Zeitgrenze der Gewitter-Anreicherung (Spec AC-4), fest gebildet und vor
    JEDEM Einzel-Call geprueft — auch vor dem Anker-Abruf."""
    if time.monotonic() <= deadline_at:
        return False
    logger.warning(
        "Gewitter-Budget (%.0fs) erschoepft — Anreicherung bricht ab, "
        "Grundvorhersage unberuehrt",
        THUNDER_FETCH_DEADLINE_SECONDS,
    )
    return True


_EINZELFLUG_SPERRE = threading.Lock()
_EINZELFLUG: Dict[str, list] = {}  # URL -> [Lock, Nutzerzahl]
_bilanz = threading.local()  # letzte Fenster-Bilanz des aufrufenden Threads


@contextmanager
def _einzelflug(url: str):
    """#2439 (AC-8): je URL laedt hoechstens EIN Thread; wer wartet, findet danach
    den Cache-Eintrag. Verhindert doppelte Downloads bei ueberlappenden Fenstern."""
    with _EINZELFLUG_SPERRE:
        eintrag = _EINZELFLUG.setdefault(url, [threading.Lock(), 0])
        eintrag[1] += 1
    # Wartezeit begrenzt (F006): haengt der Lader (z. B. ein Vorwaerm-Thread), laedt
    # der Wartende nach hoechstens einer Anfragezeit selbst -- nie unbegrenzt.
    erworben = eintrag[0].acquire(timeout=THUNDER_REQUEST_TIMEOUT)
    try:
        yield
    finally:
        if erworben:
            eintrag[0].release()
        with _EINZELFLUG_SPERRE:
            eintrag[1] -= 1
            if eintrag[1] == 0:
                _EINZELFLUG.pop(url, None)


def _thunder_zaehle(zustand: Dict[str, object], schluessel: str) -> None:
    """#2554: Zaehler `versucht`/`fehlgeschlagen` werden aus mehreren Threads
    erhoeht; `+= 1` ist nicht atomar, deshalb hinter dem Lock des Abrufs."""
    with zustand["lock"]:  # type: ignore[attr-defined]
        zustand[schluessel] = int(zustand[schluessel]) + 1


class DwdDirectProvider:
    """Issue #1144: `de_direct`-Direktprovider (ICON-D2-Open-Data), direkt
    in der Registry (`providers.base._load_providers`) registriert —
    ersetzt den bisherigen `RegionalStubProvider`."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def name(self) -> str:
        return "de_direct"

    def _fetch_deadline_seconds(self) -> float:
        """Fristdauer je ``_request``-Aufruf, gelesen zur AUFRUFZEIT.

        #2302 Scheibe B: der geteilte ``before``-Hook (``providers/http.py``)
        loest ueber den NAMEN dieser Methode auf, nie ueber ihren Wert — so
        wirkt ein Laufzeit-Patch des Modul-Globals unveraendert. Liefert IMMER
        die WEITERE Huelle (``FETCH_DEADLINE_SECONDS``, 180s), NIE
        ``THUNDER_FETCH_DEADLINE_SECONDS`` (150s) — sonst wuerde ein
        vergessenes Durchreichen den Gewitterpfad heimlich verkuerzen statt
        (im schlimmsten Fall) den Grundpfad heimlich zu verlaengern.
        """
        return FETCH_DEADLINE_SECONDS

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS) | stop_at_deadline,
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before=make_deadline_before_hook("_fetch_deadline_seconds"),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(self, url: str, deadline_at: Optional[float] = None) -> bytes:
        """GET-Request mit Retry-Logik (500/502/503/504 + Connection-Errors,
        5 Versuche, 2-60s Backoff, ADR-0018: 4xx bleibt sichtbar).

        #2302 Scheibe B: zusaetzlich durch ``FETCH_DEADLINE_SECONDS`` bzw.
        ``THUNDER_FETCH_DEADLINE_SECONDS`` begrenzt — sowohl der HTTP-Timeout
        jedes einzelnen Versuchs als auch die gesamte Wiederholkette dieses
        Aufrufs sind auf die Restzeit bis ``deadline_at`` gedeckelt.

        Args:
            deadline_at: Absolute monotone Frist. Aufrufer reichen ihre
                bereits lokal gebildete Frist durch (``_fetch_series``, der
                Gewitterpfad ueber ``_thunder_point``); fehlt sie, bildet der
                geteilte ``before``-Hook sie selbst aus
                ``_fetch_deadline_seconds()``.
        """
        request_timeout = capped_timeout_or_raise(
            provider_name=self.name,
            base_timeout=TIMEOUT,
            deadline_at=deadline_at,
            budget_label="FETCH_DEADLINE_SECONDS",
            budget_seconds=FETCH_DEADLINE_SECONDS,
        )
        response = self._client.get(url, timeout=request_timeout)
        if response.status_code in RETRY_STATUS_CODES:
            response.raise_for_status()  # loest Retry via HTTPStatusError aus
        response.raise_for_status()  # nicht-retryable Fehler (4xx)
        return response.content

    @retry(
        stop=stop_after_attempt(THUNDER_RETRY_ATTEMPTS) | stop_at_deadline,
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_thunder_retryable_error),
        before=make_deadline_before_hook("_fetch_deadline_seconds"),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _thunder_request(self, url: str, deadline_at: Optional[float] = None) -> bytes:
        """#2554: GET fuer Gewitter-Raster -- eigener Timeout
        (`THUNDER_REQUEST_TIMEOUT`), `THUNDER_RETRY_ATTEMPTS` Versuche, kein
        Retry bei ReadTimeout. Frist wie `_request` auf `deadline_at` gedeckelt."""
        request_timeout = capped_timeout_or_raise(
            provider_name=self.name,
            base_timeout=THUNDER_REQUEST_TIMEOUT,
            deadline_at=deadline_at,
            budget_label="FETCH_DEADLINE_SECONDS",
            budget_seconds=FETCH_DEADLINE_SECONDS,
        )
        response = self._client.get(url, timeout=request_timeout)
        response.raise_for_status()  # 5xx -> Retry (HTTPStatusError), 4xx sichtbar
        return response.content

    def _fetch_series(
        self, param: str, lat: float, lon: float,
        run: datetime, deadline_at: float,
    ) -> Dict[int, Optional[float]]:
        """Ein Request je Zeitschritt (kein serverseitiger Punkt-Query, s.
        Modul-Docstring). `deadline_at` begrenzt das Gesamt-Zeitbudget des
        uebergeordneten `fetch_forecast`-Aufrufs (Muster meteofrance.py)."""
        values: Dict[int, Optional[float]] = {}
        for offset in FORECAST_HOURS:
            if time.monotonic() > deadline_at:
                raise ProviderRequestError(
                    self.name,
                    f"Gesamt-Zeitbudget ({FETCH_DEADLINE_SECONDS:.0f}s) "
                    "ueberschritten",
                )
            url = _build_url(run, offset, param)
            raw = self._request(url, deadline_at=deadline_at)
            values[offset] = _read_point_value(raw, lat, lon, param)
        return values

    def _thunder_point(
        self, param: str, lat: float, lon: float, ziel: datetime,
        kandidaten: List[datetime], zustand: Dict[str, object],
        deadline_at: Optional[float] = None,
    ) -> Optional[float]:
        """EIN Punktwert eines Gewittersignals zum absoluten Zeitpunkt `ziel`.

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
            _thunder_zaehle(zustand, "versucht")
            url = _build_url(lauf, ttt, param)
            # #2465: Treffer im Punkt-Fenster-Cache — kein Download, kein
            # Entpacken. Die Datei existiert (sonst laege kein Fenster vor),
            # der Lauf gilt damit als bestaetigt.
            gecacht = _RASTER_CACHE.find(url, lat, lon)
            if gecacht is not None:
                _thunder_zaehle(zustand, "cache_treffer")
                zustand["bestaetigt"] = True
                return gecacht.value_at(lat, lon, param)
            try:
                fenster = self._thunder_lade(url, lat, lon, deadline_at, zustand)
            except httpx.HTTPStatusError as e:
                weiterer_kandidat = (
                    e.response.status_code == 404
                    and not zustand["bestaetigt"]
                    and int(zustand["index"]) < len(kandidaten) - 1
                )
                if not weiterer_kandidat:
                    _thunder_zaehle(zustand, "fehlgeschlagen")
                    logger.warning(
                        "Gewittersignal '%s' +%dh nicht abrufbar: %s",
                        param, ttt, e,
                    )
                    return None
                zustand["index"] = int(zustand["index"]) + 1
                logger.warning(
                    "ICON-D2-Lauf %s nicht verfuegbar (404) — Rueckfall auf %s",
                    lauf.strftime("%Y%m%d%H"),
                    kandidaten[int(zustand["index"])].strftime("%Y%m%d%H"),
                )
                continue
            except Exception as e:
                _thunder_zaehle(zustand, "fehlgeschlagen")
                logger.warning(
                    "Gewittersignal '%s' +%dh nicht abrufbar: %s", param, ttt, e
                )
                return None
            zustand["bestaetigt"] = True
            if fenster is None:
                return None  # Parsing-Fehler: nicht cachen
            return fenster.value_at(lat, lon, param)

    def _thunder_lade(
        self, url: str, lat: float, lon: float,
        deadline_at: Optional[float], zustand: Dict[str, object],
    ) -> Optional[_RasterWindow]:
        """Ein Fenster laden und cachen (hoechstens ein Download je URL, AC-8).
        Wirft wie `_thunder_request`; `None` = Parsing-Fehler."""
        with _einzelflug(url):
            gecacht = _RASTER_CACHE.find(url, lat, lon)
            if gecacht is not None:
                _thunder_zaehle(zustand, "cache_treffer")
                return gecacht
            _thunder_zaehle(zustand, "downloads")
            raw = self._thunder_request(url, deadline_at=deadline_at)
            # AC-2: "keine Aussage" ist nicht "keine Gefahr" — der Fuellwert
            # ausserhalb des Modellgebiets wird NIE durchgereicht und NIE 0.
            # Seit #1354 filtert ihn `_filtere_fuellwert` zentral zu None.
            fenster = _decode_window(raw, lat, lon)
            if fenster is not None:
                _RASTER_CACHE.put(url, fenster)
            return fenster

    def fetch_thunder_signals_named(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, Dict[int, Optional[float]]]:
        """#1457 S2b: Blitzpotenzial und Hagel je Stunden-Offset, getrennt
        unter ihrem eigenen Signalnamen. Best effort, fail-soft — wirft NIE
        (Spec AC-3): ein Ausfall der Gewitterquelle darf die Grundvorhersage
        nicht kippen.

        Returns:
            `{Signalname: {Stunden-Offset ab `start`: Wert oder None}}`. Ohne
            `start` gilt der Lauf der Grundvorhersage als Bezug. Fehlender
            Wert bleibt `None`, NIE 0 (Spec AC-2).

        Ein Request je Signal und Zeitschritt — ICON-D2 kennt keinen
        serverseitigen Punkt-Query (s. Modul-Docstring). Ein Sammelabruf ueber
        mehrere Orte braucht es hier nicht: jede Datei deckt ohnehin das ganze
        Modellgebiet ab.
        """
        ergebnis: Dict[str, Dict[int, Optional[float]]] = {
            param: {} for param in THUNDER_PARAMS
        }
        # #1492 S2a: ausserhalb des try/except definiert, damit die
        # Zaehllogik auch dann auswertbar bleibt, wenn im try-Block VOR
        # ihrer Zuweisung schon etwas scheitert -- sonst koennte ein
        # UnboundLocalError den "wirft NIE"-Vertrag dieser Methode brechen.
        zustand: Dict[str, object] = {
            "index": 0, "bestaetigt": False, "versucht": 0, "fehlgeschlagen": 0,
            "lock": threading.Lock(),  # #2554: schuetzt die Zaehler
            "downloads": 0, "cache_treffer": 0,  # #2439: Journalzeile je Fenster
        }
        t_fenster = time.monotonic()
        abgebrochen = False  # Budget-Ende (#2554: auch fuer die Journalzeile)
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
            # Zeitgrenze fest, nicht rollend (Lehre #1448): EINMAL je Abruf
            # gebildet, dann vor JEDEM Einzel-Call geprueft.
            deadline_at = time.monotonic() + THUNDER_FETCH_DEADLINE_SECONDS
            # #2439: ein Vorwaerm-Thread endet spaetestens mit der Vorwaerm-Frist
            # (kein Nachlaeufer, der spaeter in den Cache schreibt).
            frist = getattr(_bilanz, "frist", None)
            if frist is not None:
                deadline_at = min(deadline_at, frist)
            roh_je_param: Dict[str, Dict[int, Optional[float]]] = {
                param: {} for param in THUNDER_PARAMS
            }
            anker_je_param: Dict[str, Optional[float]] = {
                param: 0.0 for param in THUNDER_PARAMS
            }
            # Anker der Differenzbildung je kumuliertem Signal: der kumulierte
            # Stand eine Stunde VOR dem ersten angefragten Zeitschritt. Nur
            # wenn `base` tatsaechlich auf dem Lauf sitzt, ist dieser Stand 0
            # (nichts kumuliert). Sonst -- dem Regelfall, weil der
            # Bezugszeitpunkt praktisch immer Stunden nach dem Lauf liegt --
            # wird er echt abgerufen: EIN zusaetzlicher Call je kumuliertem
            # Signal, VOR dem eigentlichen Zeitschritt-Abruf unten.
            for param in THUNDER_PARAMS:
                if param not in THUNDER_CUMULATIVE_PARAMS or not offsets or not (base > run):
                    continue
                if _thunder_budget_erschoepft(deadline_at):
                    abgebrochen = True
                    break
                anker_je_param[param] = self._thunder_point(
                    param, lat, lon, base, kandidaten, zustand,
                    deadline_at=deadline_at,
                )
            # #1531 AC-7: je ZEITSCHRITT ALLE Signale in THUNDER_PARAMS-
            # Reihenfolge abrufen (nicht je Signal alle Zeitschritte) --
            # sonst wuerde ein knappes Budget allein das VORDERSTE Signal
            # aufzehren, obwohl die Reihenfolge bewusst die kontingent-
            # kritischsten Signale VORN platziert (Spec Implementation
            # Details Punkt 2): die hinteren Signale sollen bei Budget-Ende
            # ausfallen, nicht die hinteren Zeitschritte EINES Signals.
            # #2554: je Zeitpunkt laufen die Groessen parallel (Aufgaben in
            # THUNDER_PARAMS-Reihenfolge, Einsortieren ueber die Groesse). Solange
            # noch kein Lauf bestaetigt ist, wird nacheinander abgerufen, damit
            # der Lauf-Rueckfall (404) nicht zwischen Threads racet.
            def hole(param: str, offset: int) -> Optional[float]:
                if _thunder_budget_erschoepft(deadline_at):
                    return _BUDGET_ENDE
                wert = self._thunder_point(
                    param, lat, lon, base + timedelta(hours=offset),
                    kandidaten, zustand, deadline_at=deadline_at,
                )
                # Ohne Wert erst an/nach der Frist beendet: der Download wurde
                # durch das Budget abgeschnitten (kein 404/Fehler davor).
                if wert is None and time.monotonic() >= deadline_at:
                    return _BUDGET_ENDE
                return wert

            if not abgebrochen:
                with ThreadPoolExecutor(
                    max_workers=THUNDER_PARALLEL_DOWNLOADS
                ) as pool:
                    for offset in offsets:
                        offen = list(THUNDER_PARAMS)
                        while offen and not zustand["bestaetigt"]:
                            param = offen.pop(0)
                            wert = hole(param, offset)
                            if wert is _BUDGET_ENDE:
                                abgebrochen = True
                                break
                            roh_je_param[param][offset] = wert
                        if abgebrochen:
                            break
                        futures = [(p, pool.submit(hole, p, offset)) for p in offen]
                        for param, future in futures:
                            wert = future.result()
                            if wert is _BUDGET_ENDE:
                                # Hintere Groessen dieses Zeitpunkts verwerfen:
                                # nie fehlt eine vordere bei vorhandener hinterer.
                                abgebrochen = True
                                break
                            roh_je_param[param][offset] = wert
                        if abgebrochen:
                            break
            for param in THUNDER_PARAMS:
                kumuliert = param in THUNDER_CUMULATIVE_PARAMS
                ergebnis[param] = (
                    _precip_series_from_cumulative(
                        roh_je_param[param], ndigits=4,
                        vorwert=anker_je_param[param],
                    )
                    if kumuliert else roh_je_param[param]
                )
        except Exception:
            logger.warning("Gewitter-Abruf fehlgeschlagen", exc_info=True)
        # #1492 S2a Implementation Details Punkt 3: NACH dem try/except, damit
        # der neue Ausnahmetyp nicht vom generischen `except Exception:`
        # darueber verschluckt wird -- er soll zum Aufrufer (thunder_enrichment)
        # durchschlagen.
        log_enrichment_call(
            PATH_THUNDER_BUDGET,
            OUTCOME_FALLBACK if abgebrochen else OUTCOME_OK,
            "icon_d2_budget_erschoepft" if abgebrochen else None,
        )
        versucht = int(zustand["versucht"])
        fehlgeschlagen = int(zustand["fehlgeschlagen"])
        # #2439 (AC-2): Abschlusszeile je Fenster, auch beim Totalausfall.
        _bilanz.letzte = (
            int(zustand["downloads"]), int(zustand["cache_treffer"]),
            bool(zustand["bestaetigt"]),
        )
        logger.info(
            "dwd_fenster fenster_s=%.2f downloads=%d cache_treffer=%d",
            time.monotonic() - t_fenster, _bilanz.letzte[0], _bilanz.letzte[1],
        )
        if versucht > 0 and fehlgeschlagen == versucht:
            raise ThunderSourceUnavailableError(self.name, versucht)
        return ergebnis

    def _prewarm_one(self, location: "Location", fenster: tuple, frist: float) -> bool:
        """Ein Tagesfenster laden (Ergebnis verworfen); False = Fehlschlag."""
        _bilanz.letzte = (0, 0, False)
        _bilanz.frist = frist
        try:
            self.fetch_thunder_signals_named(location, fenster[0], fenster[1])
        except Exception:
            return False
        finally:
            _bilanz.frist = None
        return bool(_bilanz.letzte[2])

    def prewarm_windows(
        self,
        location: "Location",
        windows,
        *,
        max_parallel: Optional[int] = None,
    ) -> None:
        """#2439 (AC-6/8/9): laedt die Fenster (start, end) -- GENAU die Argumente
        des spaeteren Hauptabrufs -- mit hoechstens `max_parallel` gleichzeitigen
        Fenstern in den Cache, verwirft das Ergebnis und blockiert bis zum Ende
        (Join, Frist `THUNDER_PREWARM_DEADLINE_SECONDS`). Wirft NIE."""
        fenster_liste = list(windows)
        if not fenster_liste:
            return
        pool = None
        try:
            pool = ThreadPoolExecutor(
                max_workers=max_parallel or THUNDER_PREWARM_PARALLEL_WINDOWS,
                thread_name_prefix="dwd-prewarm",
            )
            frist = time.monotonic() + THUNDER_PREWARM_DEADLINE_SECONDS
            futures = [
                pool.submit(contextvars.copy_context().run, self._prewarm_one, location, f, frist)
                for f in fenster_liste
            ]
            fertig, _offen = wait(futures, timeout=max(frist - time.monotonic(), 0.0))
            gut = sum(1 for f in fertig if f.result())
            if gut < len(fenster_liste):
                logger.warning(
                    "Vorwärmen fehlgeschlagen: %d von %d Fenstern ohne Daten",
                    len(fenster_liste) - gut, len(fenster_liste),
                )
        except Exception:
            logger.warning("Vorwärmen fehlgeschlagen", exc_info=True)
        finally:
            if pool is not None:
                pool.shutdown(wait=False, cancel_futures=True)

    def fetch_thunder_signals(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[int, Optional[float]]:
        """Pflichtteil des Protokolls `base.ThunderSignalProvider`: EIN Signal
        je Stunden-Offset. Duenner Griff in das benannte Ergebnis — EIN
        Abrufweg, der nicht auseinanderdriften kann (Muster
        meteofrance.fetch_thunder_signals)."""
        return self.fetch_thunder_signals_named(location, start, end).get(
            THUNDER_PARAMS[0], {}
        )

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,  # ignored, ICON-D2 hat kein Ensemble-API
        enrich_snow: bool = True,  # ignored, kein Snow-Datensatz in diesem Slice
    ) -> NormalizedTimeseries:
        """SPEC AC-1/AC-3/AC-4: liefert NormalizedTimeseries oder wirft
        ProviderRequestError (httpx-Fehler werden hier uebersetzt, analog
        MeteoFranceDirectProvider.fetch_forecast)."""
        run = _latest_run(datetime.now(timezone.utc))
        lat, lon = location.latitude, location.longitude
        deadline_at = time.monotonic() + FETCH_DEADLINE_SECONDS

        try:
            temps = self._fetch_series("t_2m", lat, lon, run, deadline_at)
            us = self._fetch_series("u_10m", lat, lon, run, deadline_at)
            vs = self._fetch_series("v_10m", lat, lon, run, deadline_at)
            precs_raw = self._fetch_series("tot_prec", lat, lon, run, deadline_at)
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                self.name, f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise ProviderRequestError(self.name, f"Request failed: {e}")

        precs = _precip_series_from_cumulative(precs_raw)

        data_points: List[ForecastDataPoint] = []
        for offset in FORECAST_HOURS:
            t = temps.get(offset)
            u = us.get(offset)
            v = vs.get(offset)
            wind_kmh = _vector_to_speed_kmh(u, v) if u is not None and v is not None else None
            data_points.append(
                ForecastDataPoint(
                    ts=run + timedelta(hours=offset),
                    t2m_c=round(t, 1) if t is not None else None,
                    wind10m_kmh=wind_kmh,
                    precip_1h_mm=precs.get(offset),
                )
            )

        meta = ForecastMeta(
            provider=Provider.DWD,
            model="ICON-D2",
            grid_res_km=2.2,
            interp="grid_point",
        )
        return NormalizedTimeseries(meta=meta, data=data_points)
