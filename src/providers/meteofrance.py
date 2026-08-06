"""
Météo-France AROME Direct Provider (#1143, Slice 2/4 von Epic #1127).

Echter `fr_direct`-Provider für den Cross-Provider-Fallback (#1141): ruft die
öffentliche Météo-France-WCS-API für das AROME-HIGHRES-Modell (0,01 Grad
Frankreich) direkt ab und liest die GRIB2-Antworten mit dem bereits im
Projekt vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue Dependency).

SPEC: docs/specs/modules/provider_meteofrance.md v1.0
Vorlage: src/providers/geosphere.py (Retry-Muster, Vektor->Speed-Formel).

WCS-Eigenheiten (empirisch verifiziert 2026-07-22 gegen die Live-API):
- `subset=time(...)` akzeptiert NUR einen einzelnen Zeitwert pro Aufruf
  ("Slicing on time is mandatory: only a 2D coverage can be downloaded") —
  ein Multi-Zeitschritt-Request in einem Call ist technisch nicht möglich,
  anders als in der Spec zunächst angenommen. Der Provider ruft daher pro
  Parameter und Zeitschritt einen eigenen `GetCoverage`-Request ab, begrenzt
  auf `FORECAST_HOURS` (bounded: 24h-Horizont, 4 Parameter x 24 Zeitschritte
  = 96 Calls pro Fetch — ausschließlich im Totalausfall-Fallback-Pfad,
  PO-Entscheidung 2026-07-23, Nachfolger von zuvor 6h/~24 Calls).
- TOTAL_PRECIPITATION-Semantik EMPIRISCH GEMESSEN UND KORRIGIERT (Adversary
  #1143 F003, Runde 2, 2026-07-23, gegen die Live-API, Coverage
  `TOTAL_PRECIPITATION__GROUND_OR_WATER_SURFACE___<run>_PT1H`): das GRIB-
  GDAL-Tag `GRIB_UNIT` = `[kg/(m^2*s)]` ist ein generisches Fehletikett —
  die tatsaechliche Semantik ergibt sich aus dem GRIB-PDS-Feld
  `typeOfStatisticalProcessing=1` ("Accumulation") mit
  `lengthOfTimeRange=1h`: der Rohwert IST bereits die 1h-Regenmenge in
  kg/m^2 (= mm), KEINE Rate. Beweis: Alpenzelle 44.04N/7.84E,
  2026-07-23T15:00Z, Rohwert `5.178` — `5.178 * 3600` = 18641,6 mm/h
  (physikalisch unmoeglich, waere ein katastrophaler Starkregen um den
  Faktor >1000 zu hoch), Direktwert `5.178` mm/h (plausibel, entspricht
  kraeftigem Gewitterregen). Konsequenz: `precip_1h_mm` wird DIREKT aus dem
  Rohwert uebernommen (gerundet, floor 0.0), OHNE `* 3600`. Die zuvor als
  AC-7-Hilfsfunktion vorgehaltene `_precip_1h_from_cumulative`
  (Differenzbildung ueber eine kumulierte Reihe) traf auf diese Coverage
  NICHT zu und wurde als toter Code entfernt (nie aus `fetch_forecast`
  aufgerufen).
"""
from __future__ import annotations

import logging
import math
import os
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
from providers import thunder_routing
from providers.base import ProviderRequestError, ThunderSourceUnavailableError
# Zustaendigkeit der GRUNDVORHERSAGE. Fuer die Gewitter-Anreicherung BEWUSST
# NICHT mehr befragt (Spec AC-12): dort entscheidet `thunder_routing`, weil die
# Zustaendigkeit groessenabhaengig ist (Oesterreich: Schnee von GeoSphere,
# Gewitter vom DWD). Der Import bleibt als Anker der Gegenprobe: der Test setzt
# ihn auf "nirgends zustaendig" und weist nach, dass trotzdem abgerufen wird.
from providers.region_routing import direct_provider_for  # noqa: F401
from providers.thunder_window_cache import get_shared_thunder_window_cache

if TYPE_CHECKING:
    from app.config import Location

logger = logging.getLogger("meteofrance")

BASE_URL = (
    "https://public-api.meteofrance.fr/public/arome/1.0/wcs/"
    "MF-NWP-HIGHRES-AROME-001-FRANCE-WCS/"
)
TIMEOUT = 30.0

RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2   # seconds
RETRY_WAIT_MAX = 60  # seconds
# 500 ergaenzt (Adversary #1143 F002): der Spike dokumentierte sporadische
# 500 ("backend error") als reales Live-Symptom des WCS-Backends, das ohne
# Aufnahme in diese Menge 0 statt 5 Retries ausgeloest haette.
RETRY_STATUS_CODES = {500, 502, 503, 504}

# Gesamt-Zeitbudget je fetch_forecast (Adversary #1143 F004): ohne Deadline
# waeren bis zu 96 sequentielle Calls x bis zu 5 Retries x 2-60s Backoff
# theoretisch >90 Min moeglich. Minimal gehalten: einfache Wall-Clock-Grenze,
# bei Ueberschreitung sofortiger Abbruch mit ProviderRequestError statt
# endlos weiterer Calls.
FETCH_DEADLINE_SECONDS = 180.0

# Eigenes Zeitbudget der Gewitter-Anreicherung (#1457 S2a, AC-4). BEWUSST
# getrennt von FETCH_DEADLINE_SECONDS: die Anreicherung ist best-effort und
# darf das Budget der Grundvorhersage weder teilen noch anknabbern — ein
# fehlendes Gewittersignal ist harmlos, eine fehlende Grundvorhersage nicht.
#
# Herleitung der 45s:
# - gegen die 180s der Grundvorhersage (oben): dort 96 Calls, also ~1,9s je
#   Call. Dieselbe Zuteilung fuer die 24 zusaetzlichen Calls ergibt 45s. Die
#   Worst-Case-Gesamtlaufzeit waechst damit um hoechstens ein Viertel.
# - gegen die 90s des Alarm-Laufs (ALERT_RUN_DEADLINE_SECONDS,
#   services/trip_alert.py:44): dort ist dieser Provider NICHT der Regelweg,
#   sondern nur der Totalausfall-Fallback (der Regelweg openmeteo.py:74 hat
#   60s und bleibt unter den 90s). Wird der Fallback im Alarm-Lauf
#   ueberhaupt erreicht, sprengt bereits die Grundvorhersage mit ihren 180s
#   das Alarm-Budget — ein Bestandszustand, den diese Scheibe weder
#   verursacht noch behebt. Die 45s sind bewusst KEIN weiterer Aufschlag auf
#   einen ohnehin zu grossen Wert, sondern greifen unabhaengig davon.
# Zeitgrenze fest, nicht rollend (Lehre #1448): sie wird EINMAL je Abruf
# gebildet und dann vor jedem Einzel-Call geprueft.
THUNDER_FETCH_DEADLINE_SECONDS = 45.0

# Bounded, konstante Anzahl Zeitschritte je Parameter (siehe Modul-Docstring
# zur "nur ein Zeitwert pro Call"-Einschränkung der Live-API). 24h-Horizont
# (PO-Entscheidung 2026-07-23, Nachfolger von zuvor 1..6).
FORECAST_HOURS: List[int] = list(range(1, 25))

# Groesste erlaubte Kantenlaenge des GEMEINSAMEN Abfrage-Rechtecks der
# Gewitter-Anreicherung, in Grad (#1457 S2a, AC-9).
#
# Warum es das Rechteck ueberhaupt gibt: Meteo-France begrenzt pro MINUTE
# (Annahme 100/min seit Januar 2026, Ueberschreitung -> HTTP 429). Ein Abruf
# je Ort und Stunde (8 Orte x 24 Stunden = 192) sprengt das Limit um das
# Doppelte. Die WCS-Schnittstelle nimmt aber ein beliebig grosses Rechteck
# entgegen, aus dem alle Orte gelesen werden koennen.
#
# Warum genau 8 Grad (live gemessen 2026-08-02 gegen die API):
#   0,1° (ein Punkt) 0,49 s / 445 B  ·  2° (Korsika ganz) 0,43 s / 81 KB
#   8° (Suedost-FR)  0,65 s / 1,3 MB ·  18° (ganz FR)     0,91 s / 3,9 MB
# 8° deckt jedes reale Wandergebiet in einem Stueck ab (Korsika ~1,5°, GR20
# ~0,9°, Pyrenaeen ~5°) — echte Laeufe brauchen also nie mehr als eine
# Gruppe. Die Antwort bleibt bei 1,3 MB, ueber 24 Stunden ~31 MB je Lauf.
# Ganz Frankreich waere mit 3,9 MB das Dreifache (~94 MB je Lauf) fuer einen
# Fall, den es praktisch nicht gibt: Orte 18° auseinander sind keine Tour.
# Ueberschreitung fuehrt daher NICHT zum Abbruch, sondern zur Aufteilung in
# mehrere Gruppen — lieber ein zweiter Satz Abrufe als ein Datenverlust.
#
# Gilt fuer die Orte einer Gruppe. Das tatsaechlich abgefragte Rechteck wird
# anschliessend auf das Kachelgitter unten aufgerundet und kann dadurch je
# Achse um bis zu eine Kachel groesser ausfallen. Bewusst in Kauf genommen:
# der Zugewinn (Orte fallen ueber Aufrufe hinweg auf dasselbe Rechteck) wiegt
# schwerer als ein Rechteck am oberen Rand der gemessenen Groessen.
THUNDER_BOX_MAX_DEGREES = 8.0

# Kleiner Rand um das Rechteck, damit ein Ort nie genau auf der Kante liegt
# (identisch zum bisherigen Punkt-Kaestchen von ±0,05°).
THUNDER_BOX_MARGIN_DEGREES = 0.05

# Kantenlaenge des gemeinsamen KACHELGITTERS, auf das jedes Abfrage-Rechteck
# aufgerundet wird (#1457 S2a, AC-9 neu gefasst).
#
# Warum ueberhaupt gerundet wird: Trip und Ortsvergleich rufen beide Ort fuer
# Ort ab. Ein Rechteck, das nur den einen Ort umschliesst, nuetzt dem naechsten
# nichts. Erst ein GEMEINSAMES Gitter macht zwei benachbarte Orte zu demselben
# Abfrage-Rechteck — und damit zum selben Schluessel im geteilten
# Zwischenspeicher (`thunder_window_cache`). Kein Aufrufer muss dafuer geaendert
# werden; das ist der Punkt (PO-Richtlinie "Trip/Ortsvergleich-Teilung").
#
# Warum 2°: live gemessen 2026-08-02 kostet ein 2°-Rechteck 0,43 s / 81 KB
# gegen 0,49 s / 445 B fuer einen einzelnen Punkt — die Antwortzeit ist also
# praktisch gleich, nur das Volumen waechst. 2° deckt ein Wandergebiet
# typischerweise in einer einzigen Kachel ab (Korsika ~1,5°, GR20 ~0,9°) und
# haelt den Speicherbedarf bei 24 Stunden im einstelligen MB-Bereich. Groesser
# waere in beide Richtungen schlechter: mehr Volumen je Abruf, ohne dass mehr
# Orte zusammenfielen.
#
# Bekannte Grenze: eine Kachel kann ueber den Rand des Modellgebiets
# hinausragen. Das ist unkritisch — der WCS-Dienst schneidet ein Subset auf
# seine Abdeckung zu, und schlaegt ein einzelner Abruf doch fehl, bleibt es bei
# der Regel "fehlender Wert = None, nie 0" fuer genau diese Stunde.
THUNDER_TILE_DEGREES = 2.0

TEMPERATURE_COVERAGE = "TEMPERATURE__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
U_WIND_COVERAGE = "U_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
V_WIND_COVERAGE = "V_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
PRECIP_COVERAGE = "TOTAL_PRECIPITATION__GROUND_OR_WATER_SURFACE"
# #1457 S2a: erwartete Blitzdichte, Bodenniveau — daher KEIN height-Subset,
# wie beim Niederschlag. Die 3-Stunden-Mittelung steckt bereits im Namen der
# Groesse, kein separates Perioden-Suffix wie beim Niederschlag (`_PT1H`).
# Live gegen die API verifiziert (2026-08-02, GR20 42.22/9.07, Lauf 00Z:
# +12h=0.0, +14h=0.1, +16h=0.2, +18h=0.0). `DescribeCoverage` bestaetigt
# "Average lightning strike density over 3 hours", uom `km-3` — eine DICHTE,
# keine Potenzialgroesse; daher das eigene Feld (s. #1419).
#
# #1457 S2a FIX (2026-08-03, docs/specs/fast/fix-1457-s2a-echte-abrufnamen.md,
# AC-2): der zuvor hier eingetragene Name `LITOTA3__GROUND` existiert beim
# Dienst NICHT — 0 Treffer in `GetCapabilities`, live geprueft. Jeder Abruf
# endete deshalb lautlos in 404 (fail-soft schluckte es). Der Dienst fuehrt
# die Groesse unter der ausgeschriebenen Form unten, OHNE separates
# Hoehen-/Boden-Suffix (das steckt bereits im Namen selbst).
LIGHTNING_COVERAGE = (
    "AVERAGE_LIGHTNING_STRIKE_DENSITY_OVER_3HOURS__GROUND_OR_WATER_SURFACE"
)

# #1457 S2a FIX, AC-3/AC-4: der Sicherheitsabstand fuer die GRUNDVORHERSAGE
# (Temperatur/Wind/Niederschlag, `_latest_run`-Default unten) bleibt bei 3h —
# dafuer war er nie das Problem. Fuer die Blitzdichte-Coverage reichten 3h
# NICHT: live gemessen war um 09:27Z erst der Lauf 03:00Z veroeffentlicht
# (6,5h alt), der nach der alten 3h-Regel errechnete Lauf 06:00Z existierte
# noch nicht. Deshalb ein EIGENER, groesserer Abstand nur fuer die WAHL DES
# GRIB-LAUFS bei der Blitzdichte (s. `_thunder_run_candidates`) — der
# Nullpunkt der Stunden-Offsets bleibt unveraendert der 3h-Lauf, sonst
# driftete die Blitzdichte-Zeitachse relativ zur Grundvorhersage auseinander.
THUNDER_RUN_SAFETY_HOURS = 6
# Rueckfall auf hoechstens zwei aeltere Laeufe bei 404 (je 3h aelter), macht
# bis zu 12h zurueck ab dem geflooreten `now`.
THUNDER_RUN_FALLBACK_STAGES = 2


def _is_retryable_error(exception: BaseException) -> bool:
    """1:1-Muster geosphere.py: retryable bei 502/503/504 + Connection-Errors."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


def _vector_to_speed_kmh(u: float, v: float) -> float:
    """AC-6: U/V-Windkomponenten (m/s) -> Betrag in km/h, ident zu
    geosphere._vector_to_speed_kmh."""
    speed_ms = math.sqrt(u**2 + v**2)
    return round(speed_ms * 3.6, 1)


def _latest_run(now: datetime, safety_hours: int = 3) -> datetime:
    """Jüngster AROME-Lauf (alle 3h) mit Sicherheitsabstand, damit die
    WCS-Antwort tatsächlich veröffentlicht ist (empirisch verifiziert
    2026-07-22: ein ~4-5h alter Lauf war verfügbar).

    Default `safety_hours=3` gilt fuer die GRUNDVORHERSAGE
    (Temperatur/Wind/Niederschlag, unveraendert seit #1143). Fuer die
    Blitzdichte-Coverage reicht das NICHT (#1457 S2a Fix) — dort wird
    `safety_hours=THUNDER_RUN_SAFETY_HOURS` uebergeben, s.
    `_thunder_run_candidates`."""
    floored_hour = (now.hour // 3) * 3
    run = now.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    return run - timedelta(hours=safety_hours)


def _thunder_run_candidates(now: datetime) -> List[datetime]:
    """Kandidaten-Laeufe fuer die Blitzdichte-Coverage, juengster zuerst
    (#1457 S2a Fix, AC-3/AC-4). Index 0 traegt den groesseren
    Sicherheitsabstand `THUNDER_RUN_SAFETY_HOURS`; antwortet er mit 404, wird
    auf bis zu `THUNDER_RUN_FALLBACK_STAGES` weitere, je 3h aeltere Laeufe
    zurueckgefallen."""
    primaer = _latest_run(now, safety_hours=THUNDER_RUN_SAFETY_HOURS)
    return [
        primaer - timedelta(hours=3 * stufe)
        for stufe in range(THUNDER_RUN_FALLBACK_STAGES + 1)
    ]


def _as_utc(ts: datetime) -> datetime:
    """Zeitstempel auf UTC-bewusst bringen; naive Werte gelten als UTC (so
    liefert Open-Meteo sie)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _run_str(run: datetime) -> str:
    """Coverage-ID-Zeitformat, z.B. '2026-07-22T18.00.00Z'."""
    return run.strftime("%Y-%m-%dT%H.%M.%SZ")


def _read_point_value(raw: bytes, lat: float, lon: float) -> Optional[float]:
    """Liest den Pixelwert von Band 1 an (lat, lon) aus GRIB2-Rohbytes."""
    try:
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            row = min(max(row, 0), dataset.height - 1)
            col = min(max(col, 0), dataset.width - 1)
            return float(dataset.read(1)[row, col])
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


def _read_window_values(
    raw: bytes, gruppe: List["Location"]
) -> Dict[str, Optional[float]]:
    """Punktwerte ALLER Orte einer Gruppe aus EINER Fenster-Antwort.

    AC-11: Liegt ein Ort AUSSERHALB der Abdeckung der Antwort, bleibt sein
    Wert `None` — er wird NICHT auf den naechstgelegenen Randbildpunkt
    geklemmt. Genau das tut `_read_point_value` (Adversary-Befund F001): dort
    ist es bei einem 0,1°-Kaestchen um EINEN Ort ein harmloses Auffangnetz, bei
    einem gemeinsamen Fenster ueber viele Orte aber Datenfaelschung — alle acht
    Korsika-Orte trugen so denselben Randbildpunkt einer Paris-Antwort. Werte
    waren da, aber vom falschen Ort.

    Die Abdeckung kommt aus der ANTWORT (`dataset.bounds`), nicht aus dem
    angefragten Rechteck: der Dienst darf ein Subset auf seine eigene
    Abdeckung zuschneiden, und dann gilt sein Zuschnitt.

    Die Antwort wird EINMAL geoeffnet und fuer alle Orte gelesen — bei acht
    Orten x 24 Stunden waeren es sonst 192 Parse-Vorgaenge derselben Daten.
    """
    werte: Dict[str, Optional[float]] = {
        _ort_schluessel(loc): None for loc in gruppe
    }
    try:
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            links, unten, rechts, oben = dataset.bounds
            band = dataset.read(1)
            for loc in gruppe:
                lat, lon = loc.latitude, loc.longitude
                if not (links <= lon <= rechts and unten <= lat <= oben):
                    continue  # AC-11: verwerfen statt klemmen
                row, col = dataset.index(lon, lat)
                if 0 <= row < dataset.height and 0 <= col < dataset.width:
                    werte[_ort_schluessel(loc)] = float(band[row, col])
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
    return werte


def _ort_schluessel(location: "Location") -> str:
    """Schluessel eines Ortes im Sammelergebnis.

    Der Name ist der Vertrag (Spec AC-9); fehlt er, treten die Koordinaten an
    seine Stelle, damit ein namenloser Ort nicht still unter `None`
    verschwindet oder mit einem zweiten namenlosen Ort kollidiert.
    """
    return location.name or f"{location.latitude:.4f},{location.longitude:.4f}"


def _thunder_gruppen(locations: List["Location"]) -> List[List["Location"]]:
    """Orte so gruppieren, dass das umschliessende Rechteck je Gruppe
    `THUNDER_BOX_MAX_DEGREES` in keiner Richtung ueberschreitet (AC-9).

    Bewusst einfach gehalten: nach Breite/Laenge sortieren und gierig
    auffuellen, bis die naechste Aufnahme das Rechteck zu gross machen wuerde.
    Das ist nicht die minimale Gruppenzahl, aber es haelt benachbarte Orte
    zusammen — und der Regelfall (alle Orte einer Tour) ergibt genau eine
    Gruppe.
    """
    gruppen: List[List["Location"]] = []
    aktuell: List["Location"] = []
    for loc in sorted(locations, key=lambda x: (x.latitude, x.longitude)):
        kandidat = aktuell + [loc]
        lats = [x.latitude for x in kandidat]
        lons = [x.longitude for x in kandidat]
        zu_gross = (
            max(lats) - min(lats) > THUNDER_BOX_MAX_DEGREES
            or max(lons) - min(lons) > THUNDER_BOX_MAX_DEGREES
        )
        if aktuell and zu_gross:
            gruppen.append(aktuell)
            aktuell = [loc]
        else:
            aktuell = kandidat
    if aktuell:
        gruppen.append(aktuell)
    return gruppen


def _thunder_rechteck(
    gruppe: List["Location"],
) -> tuple[float, float, float, float]:
    """Umschliessendes Rechteck (min_lat, max_lat, min_lon, max_lon), auf das
    gemeinsame Kachelgitter aufgerundet (AC-9).

    Erst der Rand (damit kein Ort auf der Kante liegt), dann die Rundung auf
    `THUNDER_TILE_DEGREES`. Die Rundung ist das, was zwei nacheinander
    abgerufene Nachbarorte auf DASSELBE Rechteck bringt — und damit auf
    denselben Schluessel im geteilten Zwischenspeicher.
    """
    lats = [x.latitude for x in gruppe]
    lons = [x.longitude for x in gruppe]
    m = THUNDER_BOX_MARGIN_DEGREES
    t = THUNDER_TILE_DEGREES
    return (
        math.floor((min(lats) - m) / t) * t,
        math.ceil((max(lats) + m) / t) * t,
        math.floor((min(lons) - m) / t) * t,
        math.ceil((max(lons) + m) / t) * t,
    )


def _thunder_offsets(base: datetime, end: Optional[datetime]) -> List[int]:
    """Abzurufende Stunden-Offsets aus dem gewuenschten Zeitraum (AC-10).

    Ohne `end` bleibt es beim bisherigen Verhalten (voller 24h-Horizont) —
    das ist der Fall der Grundvorhersage, die alle 24 Stunden bestueckt. Mit
    `end` (z. B. das Ein-Stunden-Fenster des Ortsvergleichs) werden nur die
    tatsaechlich benoetigten Stunden geholt; zuvor waren rund 13 von 24
    Abrufen je Ort verworfene Arbeit.

    Liegt `end` vor dem Bezugszeitpunkt, ist nichts abzurufen: fuer
    vergangene Stunden gibt es keine Vorhersage.
    """
    if end is None:
        return list(FORECAST_HOURS)
    spanne_h = (_as_utc(end) - base).total_seconds() / 3600.0
    if spanne_h <= 0:
        return []
    letzter = min(math.ceil(spanne_h), FORECAST_HOURS[-1])
    return list(range(1, letzter + 1))


class MeteoFranceDirectProvider:
    """Issue #1143: `fr_direct`-Direktprovider (AROME-WCS), direkt in der
    Registry (`providers.base._load_providers`) registriert — keine
    Stub-Adapter-Zwischenschicht mehr wie zuvor bei RegionalStubProvider."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(
            timeout=TIMEOUT,
            headers={"apikey": os.environ.get("GZ_METEOFRANCE_APIKEY", "")},
        )

    @property
    def name(self) -> str:
        return "fr_direct"

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(
        self, coverage_id: str, lat: float, lon: float,
        height: Optional[int], time_str: str,
    ) -> bytes:
        """GetCoverage-Request mit Retry-Logik (SPEC: api_retry.md-Muster,
        502/503/504 + Connection-Errors, 5 Versuche, 2-60s Backoff)."""
        return self._request_once(coverage_id, lat, lon, height, time_str)

    def _request_once(
        self, coverage_id: str, lat: float, lon: float,
        height: Optional[int], time_str: str,
        bbox: Optional[tuple[float, float, float, float]] = None,
        timeout: Optional[float] = None,
    ) -> bytes:
        """Ein einzelner GetCoverage-Request OHNE Retry.

        #1457 S2a: die Gewitter-Anreicherung ruft diesen Weg direkt auf. Mit
        Retry wuerde eine einzige 5xx-Stunde bis zu 5 Versuche x 2-60s Backoff
        kosten und das Anreicherungs-Budget (45s) sofort sprengen — nach
        wenigen Stunden waere die ganze Reihe leer statt nur einer. Die
        Grundvorhersage nutzt unveraendert den geretryten `_request`.

        Args:
            bbox: (min_lat, max_lat, min_lon, max_lon). Ohne Angabe gilt das
                bisherige 0,1°-Kaestchen um (lat, lon). Mit Angabe wird EIN
                Rechteck ueber mehrere Orte geholt (AC-9); `lat`/`lon`
                bestimmen dann nur noch nichts mehr am Ausschnitt.
            timeout: Deckel fuer diesen einen Abruf. Ohne Angabe gilt
                `TIMEOUT`. Die Anreicherung reicht hier ihre RESTZEIT durch
                (Muster #1448 S3, openmeteo.py:600) — sonst koennte ein Abruf,
                der kurz vor der Zeitgrenze startet, noch volle 30s laufen und
                die 45s-Grenze faktisch auf ~75s dehnen.
        """
        if bbox is None:
            min_lat, max_lat = lat - 0.05, lat + 0.05
            min_lon, max_lon = lon - 0.05, lon + 0.05
        else:
            min_lat, max_lat, min_lon, max_lon = bbox
        params: list[tuple[str, str]] = [
            ("service", "WCS"),
            ("version", "2.0.1"),
            ("coverageId", coverage_id),
            ("format", "application/wmo-grib"),
            ("subset", f"long({min_lon:.4f},{max_lon:.4f})"),
            ("subset", f"lat({min_lat:.4f},{max_lat:.4f})"),
        ]
        if height is not None:
            params.append(("subset", f"height({height})"))
        params.append(("subset", f"time({time_str})"))

        request_timeout = TIMEOUT if timeout is None else min(TIMEOUT, timeout)
        response = self._client.get(
            f"{BASE_URL}GetCoverage", params=params, timeout=request_timeout
        )
        if response.status_code in RETRY_STATUS_CODES:
            response.raise_for_status()  # loest Retry via HTTPStatusError aus
        response.raise_for_status()  # nicht-retryable Fehler (4xx)
        return response.content

    def _fetch_series(
        self, coverage_id: str, lat: float, lon: float,
        run: datetime, height: Optional[int], deadline_at: float,
    ) -> Dict[int, Optional[float]]:
        """Ein Request je Zeitschritt (Live-API erlaubt keinen
        Multi-Zeitschritt-Request, s. Modul-Docstring).

        F004 (Adversary #1143): `deadline_at` ist ein `time.monotonic()`-
        Zeitpunkt fuer das Gesamt-Zeitbudget des uebergeordneten
        `fetch_forecast`-Aufrufs; vor jedem Request wird geprueft, ob das
        Budget bereits ausgeschoepft ist (verhindert Worst-Case-Laufzeiten
        ueber viele Dutzend Calls x Retries hinweg)."""
        values: Dict[int, Optional[float]] = {}
        for offset in FORECAST_HOURS:
            if time.monotonic() > deadline_at:
                raise ProviderRequestError(
                    self.name,
                    f"Gesamt-Zeitbudget ({FETCH_DEADLINE_SECONDS:.0f}s) "
                    "ueberschritten",
                )
            time_str = (run + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
            raw = self._request(coverage_id, lat, lon, height, time_str)
            values[offset] = _read_point_value(raw, lat, lon)
        return values

    def fetch_thunder_signals(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[int, Optional[float]]:
        """#1457 S2a: erwartete Blitzdichte je Stunden-Offset (Blitze je km^2
        und 3h, Coverage `LIGHTNING_COVERAGE`). Best effort, fail-soft — wirft NIE.

        Muster: `openmeteo._fetch_ensemble_spread` (openmeteo.py:640-680).

        AC-6: Liegt der Ort nicht im AROME-Gebiet, wird gar nicht erst
        abgerufen — sonst entstuenden sinnlose Abrufe ausserhalb des Modells.

        AC-2: Fehlt der Wert einer Stunde, bleibt der Eintrag `None` und wird
        NIE 0 — "keine Aussage" ist nicht "keine Gefahr" (#1419 Abs. 5). Eine
        einzelne gescheiterte Stunde kippt die Reihe daher nicht.

        Protokoll (`base.ThunderSignalProvider`): Der Schluessel ist der
        Stunden-Offset ab `start`. Ohne `start` gilt der juengste Modell-Lauf
        als Bezug — nur so kann `fetch_forecast` unten seine eigenen,
        lauf-bezogenen Datenpunkte treffen. Der Bezug wird nie VOR den Lauf
        gelegt: Zeitpunkte vor dem Lauf gibt es in der Coverage nicht.

        Fuehrt den Sammelabruf mit einem einzigen Ort aus (AC-9): EIN
        Abrufweg, der nicht auseinanderdriften kann.
        """
        alle = self.fetch_thunder_signals_multi([location], start, end)
        return alle.get(_ort_schluessel(location), {})

    def fetch_thunder_signals_multi(
        self,
        locations: List["Location"],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, Dict[int, Optional[float]]]:
        """#1457 S2a AC-9: Blitzdichte fuer MEHRERE Orte aus EINEM gemeinsamen
        Abfragefenster. Best effort, fail-soft — wirft NIE.

        Warum sammeln (Regelkonformitaet, nicht Geschwindigkeit): Meteo-France
        begrenzt pro Minute (Annahme 100/min, Ueberschreitung -> HTTP 429).
        Ein Abruf je Ort und Stunde ergibt beim 8-Orte-Vergleich 192 Abrufe in
        gut einer Minute — das Doppelte des Erlaubten. Die WCS-Schnittstelle
        nimmt stattdessen ein Rechteck ueber alle Orte entgegen (bei nahezu
        gleicher Antwortzeit), aus dem jeder Ort seinen eigenen Punktwert
        liest. Die Grenzkosten je weiterem Ort sind damit null.

        Das gilt AUCH ueber Aufrufe hinweg (AC-9 neu gefasst): Trip und
        Ortsvergleich rufen beide Ort fuer Ort ab, ein Sammelaufruf mit vielen
        Orten kommt im Produktivcode gar nicht vor. Deshalb wird das Rechteck
        auf ein gemeinsames Kachelgitter gerundet und die Antwort im geteilten
        Zwischenspeicher (`thunder_window_cache`) abgelegt — der naechste Ort
        derselben Kachel wird daraus bedient, ohne dass ein Aufrufer etwas
        davon wissen oder dafuer geaendert werden muss.

        Returns:
            `{Ortsname: {Stunden-Offset ab `start`: Blitzdichte oder None}}`.
            Jeder uebergebene Ort kommt vor — Orte ausserhalb des
            AROME-Gebiets mit leerer Reihe (AC-6: fuer sie wird nicht
            abgerufen). Fehlender Wert bleibt `None`, NIE 0 (AC-2).
        """
        ergebnis: Dict[str, Dict[int, Optional[float]]] = {}
        zustaendig: List["Location"] = []
        for loc in locations:
            ergebnis.setdefault(_ort_schluessel(loc), {})
            # AC-12: die GEWITTER-Tabelle entscheidet, nicht die der
            # Grundvorhersage. Ueber das Modul aufgerufen (nicht als importierter
            # Name), damit die Zustaendigkeit an EINER Stelle bestimmt wird und
            # nicht in einer Kopie im Modul-Namensraum einfriert.
            if thunder_routing.thunder_provider_for(
                loc.latitude, loc.longitude
            ) == self.name:
                zustaendig.append(loc)
        if not zustaendig:
            return ergebnis

        # #1492 S2a: ausserhalb des try/except definiert (Muster dwd.py), damit
        # die Zaehllogik auch dann auswertbar bleibt, wenn im try-Block vor
        # ihrer ersten Verwendung schon etwas scheitert. Ein
        # Zwischenspeicher-Treffer (`speicher.get(...)` liefert nicht `None`)
        # zaehlt NICHT als Versuch -- er ist keine frische Abfrage.
        versucht = 0
        fehlgeschlagen = 0
        try:
            now = datetime.now(timezone.utc)
            # `run` bleibt der 3h-Lauf (unveraendert) und damit der Nullpunkt
            # der Stunden-Offsets — aligned mit der Grundvorhersage, die
            # denselben `_latest_run(now)` nutzt. Nur WELCHER Lauf tatsaechlich
            # abgefragt wird (`lauf_kandidaten` unten), verschiebt sich; die
            # abgefragten absoluten Zeitstempel (`time_str`) bleiben an `base`
            # und damit unberuehrt (#1457 S2a Fix, AC-3/AC-4).
            run = _latest_run(now)
            base = run if start is None else max(_as_utc(start), run)
            offsets = _thunder_offsets(base, end)
            lauf_kandidaten = _thunder_run_candidates(now)
            lauf_index = 0
            coverage_id = f"{LIGHTNING_COVERAGE}___{_run_str(lauf_kandidaten[0])}"
            rueckfall_protokolliert = False  # AC-7: einmal je Lauf, nicht je Stunde
            # Zeitgrenze fest, nicht rollend (Lehre #1448): EINMAL je Abruf
            # gebildet, dann vor jedem Einzel-Call geprueft.
            deadline_at = time.monotonic() + THUNDER_FETCH_DEADLINE_SECONDS
            speicher = get_shared_thunder_window_cache()
            for gruppe in _thunder_gruppen(zustaendig):
                bbox = _thunder_rechteck(gruppe)
                for offset in offsets:
                    time_str = (base + timedelta(hours=offset)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                    # AC-9: Fenster, das ein frueherer Abruf (anderer Ort,
                    # anderer Aufrufer) schon geladen hat, wird wiederverwendet.
                    # Deshalb liegt die Zeitgrenzen-Pruefung UNTER dem
                    # Speicher-Treffer: ein Treffer kostet keine Zeit und darf
                    # den Abbruch nicht ausloesen. Der Lauf steckt IM
                    # Schluessel (`coverage_id`) — ein Rueckfall auf einen
                    # aelteren Lauf kann nie einen Treffer eines anderen Laufs
                    # liefern (AC-8).
                    raw = speicher.get(coverage_id, time_str, bbox)
                    if raw is None:
                        # Zeitgrenze im INNERSTEN Schritt (Lehre #1448): vor
                        # JEDEM Einzelabruf, nicht nur um die Schleife herum.
                        restzeit = deadline_at - time.monotonic()
                        if restzeit <= 0:
                            logger.warning(
                                "Blitzdichte-Budget (%.0fs) erschoepft — "
                                "Anreicherung bricht ab, Grundvorhersage "
                                "unberuehrt",
                                THUNDER_FETCH_DEADLINE_SECONDS,
                            )
                            return ergebnis
                        while True:
                            versucht += 1
                            try:
                                raw = self._request_once(
                                    coverage_id, gruppe[0].latitude,
                                    gruppe[0].longitude, None, time_str,
                                    bbox=bbox, timeout=restzeit,
                                )
                                break
                            except httpx.HTTPStatusError as e:
                                # #1457 S2a Fix, AC-4: der gewaehlte Lauf
                                # existiert (noch) nicht (404) — naechstaelteren
                                # Lauf versuchen, hoechstens
                                # THUNDER_RUN_FALLBACK_STAGES Stufen weit.
                                weiterer_kandidat = (
                                    e.response.status_code == 404
                                    and lauf_index < len(lauf_kandidaten) - 1
                                )
                                if not weiterer_kandidat:
                                    fehlgeschlagen += 1
                                    logger.warning(
                                        "Blitzdichte +%dh nicht abrufbar: %s",
                                        offset, e,
                                    )
                                    raw = None
                                    break
                                if not rueckfall_protokolliert:  # AC-7
                                    logger.warning(
                                        "Lauf %s nicht verfuegbar (404) — "
                                        "Rueckfall bis zu %s",
                                        _run_str(lauf_kandidaten[lauf_index]),
                                        _run_str(lauf_kandidaten[-1]),
                                    )
                                    rueckfall_protokolliert = True
                                lauf_index += 1
                                coverage_id = (
                                    f"{LIGHTNING_COVERAGE}___"
                                    f"{_run_str(lauf_kandidaten[lauf_index])}"
                                )
                                restzeit = deadline_at - time.monotonic()
                                if restzeit <= 0:
                                    logger.warning(
                                        "Blitzdichte-Budget (%.0fs) "
                                        "erschoepft — Anreicherung bricht "
                                        "ab, Grundvorhersage unberuehrt",
                                        THUNDER_FETCH_DEADLINE_SECONDS,
                                    )
                                    return ergebnis
                                continue
                            except Exception as e:
                                fehlgeschlagen += 1
                                logger.warning(
                                    "Blitzdichte +%dh nicht abrufbar: %s",
                                    offset, e,
                                )
                                raw = None
                                break
                        if raw is None:
                            for loc in gruppe:
                                ergebnis[_ort_schluessel(loc)][offset] = None
                            continue
                        speicher.put(coverage_id, time_str, bbox, raw)
                    werte = _read_window_values(raw, gruppe)
                    for loc in gruppe:
                        schluessel = _ort_schluessel(loc)
                        ergebnis[schluessel][offset] = werte[schluessel]
        except Exception:
            logger.warning("Blitzdichte-Abruf fehlgeschlagen", exc_info=True)
            return {schluessel: {} for schluessel in ergebnis}
        # #1492 S2a Implementation Details Punkt 3: NACH dem try/except, damit
        # der neue Ausnahmetyp nicht vom generischen `except Exception:`
        # darueber verschluckt wird -- er soll zum Aufrufer (thunder_enrichment)
        # durchschlagen. Die budgetbedingten Fruehausstiege oben (`return
        # ergebnis`) pruefen bewusst NICHT auf Ausfall (Known Limitations 1).
        if versucht > 0 and fehlgeschlagen == versucht:
            raise ThunderSourceUnavailableError(self.name, versucht)
        return ergebnis

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,  # ignored, AROME hat kein Ensemble-API
        enrich_snow: bool = True,  # ignored, kein Snow-Datensatz in diesem Slice
        enrich_thunder: bool = True,  # #1457 S2a AC-5: Default schaltet EIN
    ) -> NormalizedTimeseries:
        """SPEC AC-1/AC-3/AC-4: liefert NormalizedTimeseries oder wirft
        ProviderRequestError (httpx-Fehler werden hier uebersetzt, analog
        GeoSphereProvider.fetch_forecast)."""
        run = _latest_run(datetime.now(timezone.utc))
        run_str = _run_str(run)
        lat, lon = location.latitude, location.longitude
        deadline_at = time.monotonic() + FETCH_DEADLINE_SECONDS

        try:
            temps = self._fetch_series(f"{TEMPERATURE_COVERAGE}___{run_str}", lat, lon, run, height=2, deadline_at=deadline_at)
            us = self._fetch_series(f"{U_WIND_COVERAGE}___{run_str}", lat, lon, run, height=10, deadline_at=deadline_at)
            vs = self._fetch_series(f"{V_WIND_COVERAGE}___{run_str}", lat, lon, run, height=10, deadline_at=deadline_at)
            precs = self._fetch_series(f"{PRECIP_COVERAGE}___{run_str}_PT1H", lat, lon, run, height=None, deadline_at=deadline_at)
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                self.name, f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise ProviderRequestError(self.name, f"Request failed: {e}")

        # AC-3/AC-4/AC-5: erst NACH den vollstaendigen Grunddaten und mit
        # eigenem Budget — scheitert die Anreicherung, bleibt die Vorhersage
        # unversehrt und nur das Blitzfeld leer.
        # BEWUSST ohne `start`: die Datenpunkte unten zaehlen ab `run`, also
        # muessen es die Gewitter-Offsets auch — sonst laege der Wert einer
        # Stunde an einer anderen. `start`/`end` wirken in dieser Klasse
        # ohnehin nicht auf den Zeitraster der Grundvorhersage.
        # #1492 S2a Adversary F001: `fetch_thunder_signals` delegiert an
        # `fetch_thunder_signals_multi`, die seit dieser Scheibe bei
        # Totalausfall der Gewitterquelle `ThunderSourceUnavailableError`
        # wirft (s. Kommentar oben bei `raise ThunderSourceUnavailableError`).
        # Vor #1492 S2a konnte dieser Aufruf nie werfen ("Best effort,
        # fail-soft"). Ohne dieses Fangen wuerde die oben versprochene
        # Zusage brechen und die GESAMTE Vorhersage (inkl. Grunddaten)
        # verloren gehen, obwohl nur das Blitzfeld betroffen ist.
        try:
            thunder = self.fetch_thunder_signals(location) if enrich_thunder else {}
        except ThunderSourceUnavailableError:
            thunder = {}

        data_points: List[ForecastDataPoint] = []
        for offset in FORECAST_HOURS:
            t = temps.get(offset)
            u = us.get(offset)
            v = vs.get(offset)
            p = precs.get(offset)
            wind_kmh = _vector_to_speed_kmh(u, v) if u is not None and v is not None else None
            # F003 (Adversary #1143 Runde 2): Rohwert ist bereits die
            # 1h-Akkumulation in mm (typeOfStatisticalProcessing=1,
            # lengthOfTimeRange=1h) — KEIN *3600 (s. Modul-Docstring).
            precip_mm = max(0.0, round(p, 1)) if p is not None else None
            data_points.append(
                ForecastDataPoint(
                    ts=run + timedelta(hours=offset),
                    t2m_c=round(t, 1) if t is not None else None,
                    wind10m_kmh=wind_kmh,
                    precip_1h_mm=precip_mm,
                    # AC-2: fehlender Wert -> None, NIEMALS 0.
                    lightning_density_per_km2_3h=thunder.get(offset),
                )
            )

        meta = ForecastMeta(
            provider=Provider.METEOFRANCE,
            model="AROME-HIGHRES",
            grid_res_km=1.3,
            interp="grid_point",
        )
        return NormalizedTimeseries(meta=meta, data=data_points)
