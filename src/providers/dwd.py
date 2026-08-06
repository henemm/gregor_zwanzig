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

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from providers.base import ProviderRequestError, ThunderSourceUnavailableError

if TYPE_CHECKING:
    from app.config import Location

logger = logging.getLogger("dwd")

BASE_URL = "https://opendata.dwd.de/weather/nwp/icon-d2/grib/"
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
# Einzelwert-Pflichtteil des Protokolls liefert.
THUNDER_PARAMS = ("lpi", "grau_gsp")

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
THUNDER_FETCH_DEADLINE_SECONDS = 90.0

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


def _is_retryable_error(exception: BaseException) -> bool:
    """1:1-Muster meteofrance.py: retryable bei 500/502/503/504 +
    Connection-Errors."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


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


def _read_point_value(compressed: bytes, lat: float, lon: float) -> Optional[float]:
    """Entpackt eine `.grib2.bz2`-Antwort und liest den Pixelwert von Band 1
    an (lat, lon) — Muster meteofrance._read_point_value, ergänzt um den
    `bz2.decompress`-Schritt (ICON-D2 liefert komprimiert, AROME-WCS nicht).

    #1354: Der Fuellwert ausserhalb des Modellgebiets wird hier ZENTRAL zu
    `None` — sonst stuende er als echter Messwert in der Vorhersage. Quelle
    der Wahrheit ist `dataset.nodata`; ist es nicht gesetzt, traegt der
    bekannte Sentinel. Vergleich `>=`: echte Messwerte erreichen diese
    Groessenordnung nie."""
    try:
        raw = bz2.decompress(compressed)
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            row = min(max(row, 0), dataset.height - 1)
            col = min(max(col, 0), dataset.width - 1)
            wert = float(dataset.read(1)[row, col])
            sentinel = (
                float(dataset.nodata)
                if dataset.nodata is not None
                else THUNDER_FILL_VALUE
            )
            return None if wert >= sentinel else wert
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


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


class DwdDirectProvider:
    """Issue #1144: `de_direct`-Direktprovider (ICON-D2-Open-Data), direkt
    in der Registry (`providers.base._load_providers`) registriert —
    ersetzt den bisherigen `RegionalStubProvider`."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def name(self) -> str:
        return "de_direct"

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(self, url: str) -> bytes:
        """GET-Request mit Retry-Logik (500/502/503/504 + Connection-Errors,
        5 Versuche, 2-60s Backoff, ADR-0018: 4xx bleibt sichtbar)."""
        response = self._client.get(url)
        if response.status_code in RETRY_STATUS_CODES:
            response.raise_for_status()  # loest Retry via HTTPStatusError aus
        response.raise_for_status()  # nicht-retryable Fehler (4xx)
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
            raw = self._request(url)
            values[offset] = _read_point_value(raw, lat, lon)
        return values

    def _thunder_point(
        self, param: str, lat: float, lon: float, ziel: datetime,
        kandidaten: List[datetime], zustand: Dict[str, object],
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
            zustand["versucht"] = int(zustand["versucht"]) + 1
            try:
                raw = self._request(_build_url(lauf, ttt, param))
            except httpx.HTTPStatusError as e:
                weiterer_kandidat = (
                    e.response.status_code == 404
                    and not zustand["bestaetigt"]
                    and int(zustand["index"]) < len(kandidaten) - 1
                )
                if not weiterer_kandidat:
                    zustand["fehlgeschlagen"] = int(zustand["fehlgeschlagen"]) + 1
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
                zustand["fehlgeschlagen"] = int(zustand["fehlgeschlagen"]) + 1
                logger.warning(
                    "Gewittersignal '%s' +%dh nicht abrufbar: %s", param, ttt, e
                )
                return None
            zustand["bestaetigt"] = True
            wert = _read_point_value(raw, lat, lon)
            # AC-2: "keine Aussage" ist nicht "keine Gefahr" — der Fuellwert
            # ausserhalb des Modellgebiets wird NIE durchgereicht und NIE 0.
            # Seit #1354 filtert ihn `_read_point_value` zentral zu None.
            if wert is None:
                return None
            return wert

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
            # Zeitgrenze fest, nicht rollend (Lehre #1448): EINMAL je Abruf
            # gebildet, dann vor JEDEM Einzel-Call geprueft.
            deadline_at = time.monotonic() + THUNDER_FETCH_DEADLINE_SECONDS
            for param in THUNDER_PARAMS:
                kumuliert = param in THUNDER_CUMULATIVE_PARAMS
                # Anker der Differenzbildung: der kumulierte Stand eine Stunde
                # VOR dem ersten angefragten Zeitschritt. Nur wenn `base`
                # tatsaechlich auf dem Lauf sitzt, ist dieser Stand 0 (nichts
                # kumuliert). Sonst — dem Regelfall, weil der Bezugszeitpunkt
                # praktisch immer Stunden nach dem Lauf liegt — wird er echt
                # abgerufen: EIN zusaetzlicher Call je kumuliertem Signal.
                # Ohne ihn traegt die erste gelieferte Stunde die gesamte
                # Kumulation seit Laufbeginn und ist systematisch zu hoch.
                anker: Optional[float] = 0.0
                if kumuliert and offsets and base > run:
                    if _thunder_budget_erschoepft(deadline_at):
                        break
                    anker = self._thunder_point(
                        param, lat, lon, base, kandidaten, zustand,
                    )
                roh: Dict[int, Optional[float]] = {}
                erschoepft = False
                for offset in offsets:
                    if _thunder_budget_erschoepft(deadline_at):
                        erschoepft = True
                        break
                    roh[offset] = self._thunder_point(
                        param, lat, lon, base + timedelta(hours=offset),
                        kandidaten, zustand,
                    )
                ergebnis[param] = (
                    _precip_series_from_cumulative(roh, ndigits=4, vorwert=anker)
                    if kumuliert else roh
                )
                if erschoepft:
                    break
        except Exception:
            logger.warning("Gewitter-Abruf fehlgeschlagen", exc_info=True)
        # #1492 S2a Implementation Details Punkt 3: NACH dem try/except, damit
        # der neue Ausnahmetyp nicht vom generischen `except Exception:`
        # darueber verschluckt wird -- er soll zum Aufrufer (thunder_enrichment)
        # durchschlagen.
        versucht = int(zustand["versucht"])
        fehlgeschlagen = int(zustand["fehlgeschlagen"])
        if versucht > 0 and fehlgeschlagen == versucht:
            raise ThunderSourceUnavailableError(self.name, versucht)
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
