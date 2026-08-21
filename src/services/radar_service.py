"""
Radar Nowcasting Service.

Provides short-term precipitation forecasts ("fängt es in den nächsten
~20 Minuten an zu regnen?") as compact German text.

Sources (coordinate-based, automatic):
- BrightSky (RADOLAN) for Germany
- GeoSphere INCA for Austria
- ARPAE ICON-2I (via Open-Meteo) for Italy (incl. Corsica coverage)
- Météo-France AROME-HD (via Open-Meteo) for France/Benelux
- Open-Meteo minutely_15 for global/fallback

Feature: Issue #656
SPEC: docs/specs/modules/radar_nowcast.md
"""
from __future__ import annotations

import bisect
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from services import alert_input_capture

logger = logging.getLogger("radar_service")

# RADOLAN bounding box (DE)
_RADOLAN_LAT_MIN = 47.0
_RADOLAN_LAT_MAX = 55.1
_RADOLAN_LON_MIN = 5.8
_RADOLAN_LON_MAX = 15.1

# INCA bounding box (AT)
_INCA_LAT_MIN = 46.3
_INCA_LAT_MAX = 49.1
_INCA_LON_MIN = 9.5
_INCA_LON_MAX = 17.2

# AROME-HD bounding box (FR — incl. Corsica, FR-Alps, Pyrenees, Benelux, NW-Italy)
_AROME_FR_LAT_MIN = 41.0
_AROME_FR_LAT_MAX = 51.5
_AROME_FR_LON_MIN = -5.5
_AROME_FR_LON_MAX = 10.0

# Italien-Radar bounding box (IT — Zustaendigkeitsgebiet, kein Anbietername:
# Werte aus #1162 uebernommen, seit #1648 bedient von ARPAE ICON-2I)
_ITALY_RADAR_LAT_MIN = 36.0
_ITALY_RADAR_LAT_MAX = 47.5
_ITALY_RADAR_LON_MIN = 6.5
_ITALY_RADAR_LON_MAX = 19.0

# ICON-D2 bounding box (Central Europe / Alps — DWD ICON-D2 ~2 km, Issue #761)
# Conservative rectangle; exact (rotated) grid fidelity comes from the all-None guard.
_ICON_D2_LAT_MIN = 44.0
_ICON_D2_LAT_MAX = 58.0
_ICON_D2_LON_MIN = 2.0
_ICON_D2_LON_MAX = 19.0

# Onset threshold: frames within 180 min from now considered "nowcast"
# Issue #1945: 180 statt 60 — die GeoSphere-INCA-Quelle liefert live 3 Stunden
# im 15-Min-Raster; der alte 60-Min-Deckel liess den Alarm praktisch immer erst
# beim naechsten Rasterpunkt (~8 Min Vorlauf) ausloesen.
_NOWCAST_HORIZON_MIN = 180
# Issue #1439: oeffentlicher Alias, damit der Scheduler-Zeitfenster-Guard
# dieselbe Zahl referenziert statt eine zweite Kopie zu pflegen.
NOWCAST_HORIZON_MIN = _NOWCAST_HORIZON_MIN

# Issue #2020: extrahierte Schwelle -- war Inline-Literal in intensity_to_text().
# Dieselbe Zahl, die die Ueberholungs-Pruefung in trip_alert.py als
# Relevanz-Untergrenze auf max_rate_mm_h referenziert (keine zweite,
# unabhaengige Zahl).
HEAVY_RAIN_THRESHOLD_MM_H = 4.0

# Issue #2020: eigenes, auf eine Stunde begrenztes Vergleichsfenster fuer die
# Mengen-Ueberholungspruefung -- bewusst NICHT _NOWCAST_HORIZON_MIN (180 Min),
# sonst wuerde ein Drei-Stunden-Wert gegen einen Ein-Stunden-Briefingwert
# verglichen (precip_1h_mm).
_OVERTAKE_COMPARE_WINDOW_MIN = 60

# Issue #2020 Fix-Loop 2 (Adversary-Runde 2, F006/F007): feste Obergrenze fuer
# die Deckung EINES Frames im Vergleichsfenster -- ersetzt die globale
# Kadenz-Schaetzung (_infer_frame_cadence, entfernt). 15 Minuten ist das
# GROEBSTE in Produktion vorkommende Raster (INCA, AROME-FR, ICON-D2, ARPAE,
# `minutely_15`); RADOLAN liefert 5 Minuten. Ein Frame darf nie fuer mehr Zeit
# einstehen, als das groebste Raster hergibt -- unabhaengig davon, was andere
# Frames irgendwo in der Liste an Abstaenden aufweisen (das war die Schwaeche
# jeder globalen Schaetzung, ob Minimum oder Median: ferne Frames konnten die
# Deckung naher Frames nach oben oder unten verfaelschen).
_MAX_FRAME_COVERAGE = timedelta(minutes=15)

# Issue #2009: einzige Quelle der Onset-Alarmschwelle, ersetzt die bisher
# doppelt gepflegten Literale in trip_alert.py und compare_radar_alert.py
# (ADR-0021 — Trip und Ortsvergleich teilen den Code). Wert 55: am Cron-Takt
# `7,22,37,52` und dem 15-Min-Datenraster sind nur die Onset-Werte
# 8/23/38/53/68/83 ... erreichbar; 55 liegt knapp oberhalb von 53, laesst also
# bis zu ~53 Min Vorlauf durch und schliesst 68+ aus (jenseits ~60 Min sinkt
# die Ortsschaerfe des INCA-Extrapolationsprodukts deutlich).
#
# BEWUSST NUR EIN NAME — kein privates `_RADAR_ONSET_THRESHOLD_MIN` daneben
# (anders als beim Nachbarn `NOWCAST_HORIZON_MIN` oben, der einen echten
# modulinternen Leser hat; hier gab es nie einen). Ein zweiter, privater Name
# laedt dazu ein, ihn zu benutzen — und wer ihn benutzt, bindet den Wert beim
# Import und umgeht damit den Laufzeit-Drift-Schutz aus AC-1: die Aufrufer in
# trip_alert.py/compare_radar_alert.py lesen absichtlich ueber die
# MODUL-Referenz (`radar_service_mod.RADAR_ONSET_THRESHOLD_MIN`), damit ein
# Auseinanderlaufen der beiden Pfade auffaellt statt still zu bleiben.
RADAR_ONSET_THRESHOLD_MIN = 55
_DRY_THRESHOLD_MM_H = 0.1

# Issue #1461 S3a: benannte Intensitaets-Label-Konstanten statt Inline-Strings
# in intensity_to_text() -- alert_urgency.py vergleicht gegen diese Konstanten
# statt gegen Zeichenketten-Duplikate (E3). Wortlaut unveraendert.
INTENSITY_CONVECTIVE = "Starker Hagel/Gewitter"
INTENSITY_HEAVY = "Starker Regen"
INTENSITY_MODERATE = "Mäßiger Regen"
INTENSITY_LIGHT = "Leichter Regen"
INTENSITY_DRY = "Kein Niederschlag"

HTTPX_TIMEOUT = 8.0


@dataclass
class NowcastResult:
    """Result of a nowcast query."""
    onset_minutes: Optional[int]   # minutes until first wet frame, None if none
    intensity_label: str            # human-readable intensity
    source: str                     # "radar", "INCA", "AROME-FR", "minutely_15"
    frames: list = field(default_factory=list)
    is_convective: bool = False     # True when nowcast indicates thunderstorm/hail
    convective_checked: bool = True  # False when INCA sidecar convective-check failed
    throttled: bool = False        # True when no frames due to budget throttling,
                                    # not "genuinely dry" (Issue #1329 C2, AC-6).
                                    # Pure observability signal -- radar_alert_due()
                                    # treats onset_minutes=None identically either way
                                    # (safe: a missed poll beats a quota outage).
    data_unavailable: bool = False  # True when no frames due to a real upstream
                                     # failure (HTTP error/timeout), distinct from
                                     # both "genuinely dry" and `throttled`
                                     # (Issue #1628 S1). Pure observability signal --
                                     # radar_alert_due() treats onset_minutes=None
                                     # identically either way.
    max_rate_mm_h: float = 0.0      # Issue #2020: Spitzenrate im 60-Min-
                                     # Vergleichsfenster (compare_window, s.
                                     # _OVERTAKE_COMPARE_WINDOW_MIN) -- NICHT
                                     # das 180-Min-Nowcast-Fenster (Adversary-
                                     # Fund F001, 2026-08-21: ein spaeter,
                                     # unabhaengiger Starkregen-Ausbruch darf
                                     # eine Ueberholung fuer ganz anderen,
                                     # schwachen Nahregen nicht legitimieren).
                                     # BEWUSST beschreibend (F008, PO-Entscheid
                                     # 2026-08-21): die Ueberholungsregel in
                                     # trip_alert.py liest dieses Feld NICHT
                                     # mehr -- ihre Relevanz-Untergrenze haengt
                                     # jetzt an window_precip_mm
                                     # (_OVERTAKE_MIN_ABSOLUTE_MM), weil eine
                                     # Spitzenrate anhaltenden, nicht-spitzen
                                     # Regen strukturell aussperrte. Das Feld
                                     # bleibt fuer Beobachtbarkeit/Tests
                                     # (intensity_label-Nachbarwert) erhalten,
                                     # absichtlich ohne Regel-Leser -- kein
                                     # vergessener Anschluss.
    window_precip_mm: float = 0.0   # Issue #2020: akkumulierte Menge in der ERSTEN
                                     # STUNDE ab jetzt (eigenes Fenster, s.
                                     # _OVERTAKE_COMPARE_WINDOW_MIN) -- vergleichbar
                                     # mit precip_1h_mm im Briefing.


def _offline_fixture_active() -> bool:
    """True wenn GZ_TEST_FIXTURE_DIR gesetzt ist (Issue #1329 C2) -- identische
    Aktivierungsregel wie providers/base.py:144. EIN Schalter fuer den
    gesamten Radar-Pfad, kein separater Radar-Env-Var (ADR-0033 Punkt 3)."""
    return bool(os.environ.get("GZ_TEST_FIXTURE_DIR", "").strip())


class RadarNowcastService:
    """
    Coordinate-aware nowcasting service.

    DI-seam: pass frame_source=callable(lat,lon)->list[RadarFrame]
    for test injection (real data, no mocks).
    """

    def __init__(
        self,
        frame_source: Optional[Callable[[float, float], list]] = None,
        cache: Optional["RadarNowcastCacheService"] = None,  # noqa: F821 (lazy import below)
        now_fn: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._frame_source = frame_source
        self._convective_checked = True
        # Issue #1329 C2: injizierbare Uhr fuer deterministische
        # Onset-Recompute-/TTL-Tests ohne sleep. Default = echte Uhr,
        # Produktionsverhalten unveraendert.
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        if cache is None:
            from services.radar_cache import get_shared_radar_cache
            cache = get_shared_radar_cache()
        self._cache = cache
        self._openmeteo_unavailable_this_call = False
        self._budget_throttled_this_call = False
        self._inca_unavailable_this_call = False
        self._priority = "user_briefing"
        self._budget_gate = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def intensity_to_text(self, mm_per_h: float, is_convective: bool = False) -> str:
        """Map mm/h rate to German intensity label.

        Convective flag (thunderstorm/hail WMO 95/96/99) overrides all rate-based
        stages — even at very low precipitation rates.
        """
        if is_convective:
            return INTENSITY_CONVECTIVE
        # Guard: NaN or non-numeric input → treat as dry
        if not isinstance(mm_per_h, (int, float)) or mm_per_h != mm_per_h:
            return INTENSITY_DRY
        if mm_per_h < _DRY_THRESHOLD_MM_H:
            return INTENSITY_DRY
        if mm_per_h < 1.0:
            return INTENSITY_LIGHT
        if mm_per_h < HEAVY_RAIN_THRESHOLD_MM_H:
            return INTENSITY_MODERATE
        return INTENSITY_HEAVY

    def _is_convective_weathercode(self, code) -> bool:
        """Return True if WMO weather code indicates convective activity (thunderstorm/hail)."""
        return code in (95, 96, 99)

    def get_nowcast(
        self, lat: float, lon: float, elevation_m: Optional[int] = None,
        priority: str = "user_briefing",
    ) -> NowcastResult:
        """
        Fetch frames (cache-first) and derive nowcast result.

        If frame_source is injected, uses it (test DI seam) on a cache miss.
        Otherwise uses the coordinate-based source chain on a cache miss.

        Issue #1329 C2: `priority` steuert die Drosselung des internen
        open-meteo-Funnels ueber den geteilten `ForecastBudgetGate`
        ("polling" fuer Scheduler-Checks, "user_briefing" -- Default, nie
        gedrosselt -- fuer Nutzeraktionen wie `/jetzt`). Der Cache-Lookup
        selbst ist von `priority` unabhaengig; die Ableitung
        (`_derive_result`) laeuft bei Cache-Hit UND -Miss immer frisch
        relativ zur aktuellen (bzw. injizierten) Zeit -- der Cache liefert
        nie ein fertiges Ergebnis (Lehre aus Adversary-Fund F001, Scheibe C).
        """
        self._convective_checked = True
        self._openmeteo_unavailable_this_call = False
        self._budget_throttled_this_call = False
        self._inca_unavailable_this_call = False
        self._priority = priority
        from services.forecast_budget import ForecastBudgetGate
        self._budget_gate = ForecastBudgetGate()
        now = self._now_fn()

        # Adversary-Fund F001 (Issue #1329 C2, BROKEN-Verdict behoben): der
        # Region-Bucket ist Bestandteil des Cache-Schluessels, damit zwei
        # Koordinaten beidseits einer harten Routing-Grenze (die auf
        # denselben gerundeten Koordinaten-Wert fallen koennen) sich NIE
        # faelschlich einen Eintrag der jeweils anderen Region teilen.
        region = _region_bucket(lat, lon)

        cached = self._cache.get(lat, lon, region, now=now, elevation_m=elevation_m)
        if cached is not None:
            self._budget_gate.record_cache_hit()
            _capture_nowcast_frames(lat, lon, cached.frames, cached.source)
            return self._derive_result(cached.frames, cached.source, now=now)

        self._budget_gate.record_cache_miss()

        if self._frame_source is not None:
            frames = self._frame_source(lat, lon)
            source = "radar"
        else:
            frames, source = self._fetch_frames_with_fallback(lat, lon, elevation_m)

        if frames:
            self._cache.put(lat, lon, region, frames, source, now=now, elevation_m=elevation_m)

        _capture_nowcast_frames(lat, lon, frames, source)
        result = self._derive_result(frames, source, now=now)

        # Issue #1581 Scheibe 2: Health-Journal des Nowcast-Pfades. Der Aufruf
        # steht bewusst HIER im Miss-Zweig und NICHT in `_derive_result()` --
        # das laeuft bei Cache-Treffer UND -Fehltreffer, ein dort platzierter
        # Aufruf buchte jeden Treffer als lebendigen Abruf und liesse einen aus
        # dem Cache weiterbedienten Dauerausfall gesund aussehen (Spec AC-9).
        # Die Unterscheidung throttled (eigene Budget-Drosselung) vs.
        # data_unavailable (echter Anbieterausfall) existiert bereits im
        # Feldpaar von NowcastResult und wird hier nur abgebildet -- eine
        # Vermengung liesse das externe Auswertungsskript einen selbst
        # gewaehlten Rueckzug als Fremdausfall eskalieren (AC-8/AC-10).
        from providers.enrichment_health import (
            OUTCOME_FALLBACK, OUTCOME_OK, OUTCOME_SELF_THROTTLED,
            OUTCOME_UNAVAILABLE, PATH_RADAR_NOWCAST, log_enrichment_call,
        )
        if result.throttled:
            log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_SELF_THROTTLED)
        elif result.data_unavailable:
            log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_UNAVAILABLE)
        elif self._inca_unavailable_this_call:
            log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_FALLBACK, source)
        else:
            log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_OK)
        return result

    # Human-readable source labels (single source of truth — used by
    # format_now_text and by the body-builder in trip_alert.check_radar_alerts).
    _SOURCE_LABELS: dict[str, str] = {
        "radar": "Radar (DWD)",
        "INCA": "INCA (GeoSphere AT)",
        "AROME-FR": "Météo-France AROME (1,5 km)",
        "ICON-D2": "DWD ICON-D2 (2 km)",
        "ARPAE-2I": "ARPAE ICON-2I (2 km, Italien)",
        "minutely_15": "Open-Meteo (global)",
    }

    def source_label(self, source: str) -> str:
        """Return human-readable label for a raw source key.

        Falls back to the raw key if not found (forward-compatible).
        Used by format_now_text and by external callers (e.g. trip_alert).
        """
        return self._SOURCE_LABELS.get(source, source)

    def format_now_text(
        self,
        result: NowcastResult,
        *,
        tz: Optional[ZoneInfo] = None,
        include_source: bool = True,
    ) -> str:
        """Format nowcast result as German text.

        Issue #822: optionaler ``tz``-Parameter (Tour-Zeitzone aus tz_for_coords).
        Wenn gesetzt, wird die Onset-Zeit in dieser TZ formatiert statt in der
        Server-TZ. Default tz=None bewahrt das bisherige Verhalten.

        ``include_source=False`` unterdrückt die „Quelle:"-Zeile — nützlich wenn
        der Caller die Quelle selbst an anderer Stelle im Body platziert (z.B.
        check_radar_alerts, um Duplizierung zu vermeiden). Default True = bisheriges
        Verhalten, alle anderen Caller bleiben unberührt.
        """
        lines: list[str] = []

        if result.onset_minutes is None:
            if result.data_unavailable:
                # Issue #1628 S3: bei einem echten Fetch-Fehler ist
                # `intensity_label` (frames=[] -> "Kein Niederschlag") und der
                # Folgesatz gleichermassen eine falsche Entwarnung -- beide
                # Zeilen werden durch einen ehrlichen "nicht geprueft"-Hinweis
                # ersetzt, statt zu behaupten es sei trocken (R5).
                lines.append("Regen-Kurzfristprüfung aktuell nicht möglich.")
                lines.append("Bitte selbst beobachten.")
            else:
                lines.append(result.intensity_label + ".")
                lines.append("In den nächsten 2 Stunden kein Regen erwartet.")
        else:
            now = datetime.now(tz=timezone.utc)
            onset_time = now + timedelta(minutes=result.onset_minutes)
            if tz is not None:
                # Issue #1402: local_dt() statt rohem .astimezone(tz) --
                # geht ueber den zentralen Naiv-Guard (hier zwar bereits
                # aware, aber konsistent mit dem EINEN Umrechner).
                from utils.timezone import local_dt

                time_str = local_dt(onset_time, tz).strftime("%H:%M")
            else:
                # Kein tz uebergeben (Fail-soft-Pfad, Wächter-abgesichert
                # fuer Produktivcode) -- onset_time ist bereits UTC-aware,
                # NICHT das argumentlose .astimezone() nutzen (deutet sonst
                # die Prozess-Zeitzone des Servers statt ehrlich UTC).
                time_str = onset_time.strftime("%H:%M")
            lines.append(
                f"{result.intensity_label} ab ca. {time_str}"
                f" (in ~{result.onset_minutes} Min)."
            )

        if result.convective_checked is False:
            lines.append("Gewitter-Check nicht verfügbar.")

        if include_source:
            lines.append(f"Quelle: {self.source_label(result.source)}.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_frames_with_fallback(
        self, lat: float, lon: float, elevation_m: Optional[int] = None
    ) -> tuple[list, str]:
        """Try source chain; return (frames, source_label)."""
        if _within_radolan(lat, lon):
            frames = self._fetch_brightsky(lat, lon)
            if frames:
                return frames, "radar"

        if _within_inca(lat, lon):
            frames = self._fetch_geosphere_inca(lat, lon, elevation_m)
            if frames:
                return frames, "INCA"

        if _within_italy_radar(lat, lon):
            frames = self._fetch_italy_arpae(lat, lon, elevation_m)
            if frames:
                return frames, "ARPAE-2I"

        if _within_arome_france(lat, lon):
            frames = self._fetch_arome_france_hd(lat, lon, elevation_m)
            if frames:
                return frames, "AROME-FR"

        if _within_icon_d2(lat, lon):
            frames = self._fetch_icon_d2(lat, lon, elevation_m)
            if frames:
                return frames, "ICON-D2"

        frames = self._fetch_openmeteo_minutely15(lat, lon, elevation_m)
        return frames, "minutely_15"

    def _fetch_brightsky(self, lat: float, lon: float) -> list:
        if _offline_fixture_active():
            # Issue #1329 C2 Abschnitt 8: kein Netz zu BrightSky im Offline-Modus.
            return []
        try:
            from providers.brightsky import BrightSkyProvider
            provider = BrightSkyProvider()
            return provider.fetch_radar(lat, lon)
        except Exception as e:
            logger.warning(f"BrightSky failed, falling back: {e}")
            return []

    def _fetch_geosphere_inca(
        self, lat: float, lon: float, elevation_m: Optional[int] = None
    ) -> list:
        if _offline_fixture_active():
            # Issue #1329 C2 Abschnitt 8: kein Netz zu GeoSphere im Offline-Modus
            # (auch der Sidecar-open-meteo-Call unten wird dadurch nie erreicht).
            return []
        try:
            from providers.geosphere import GeoSphereProvider
            from providers.brightsky import RadarFrame
            provider = GeoSphereProvider()
            ts = provider.fetch_nowcast(lat, lon)
            if not ts or not ts.data:
                return []
            frames = []
            for dp in ts.data:
                raw = dp.precip_1h_mm
                # Convert mm/interval to mm/h (INCA is 15-min steps); None -> dry frame
                mm_h = float(raw) * 4.0 if raw is not None else 0.0
                ts_val = dp.ts if dp.ts.tzinfo else dp.ts.replace(tzinfo=timezone.utc)
                frames.append(RadarFrame(timestamp=ts_val, precip_mm_h=mm_h))
            # Convective sidecar: INCA carries no thunderstorm/hail field, so reuse the
            # global Open-Meteo best_match nowcast solely for the is_convective flag.
            sidecar = self._fetch_openmeteo_15(lat, lon, elevation_m=elevation_m)
            if sidecar:
                self._merge_convective(frames, sidecar)
            else:
                # ADR-0018: do not silently pass a failed check off as "no thunderstorm".
                self._convective_checked = False
            return frames
        except Exception as e:
            logger.warning(f"GeoSphere INCA failed, falling back: {e}")
            self._inca_unavailable_this_call = True
            return []

    def _merge_convective(self, inca_frames: list, sidecar_frames: list) -> None:
        """Merge is_convective from nearest sidecar frame (<=5 min) into INCA frames."""
        tolerance = timedelta(minutes=5)
        for frame in inca_frames:
            nearest = min(
                sidecar_frames, key=lambda s: abs(s.timestamp - frame.timestamp)
            )
            if abs(nearest.timestamp - frame.timestamp) <= tolerance:
                frame.is_convective = nearest.is_convective

    def _fetch_openmeteo_minutely15(
        self, lat: float, lon: float, elevation_m: Optional[int] = None
    ) -> list:
        return self._fetch_openmeteo_15(lat, lon, elevation_m=elevation_m)

    def _fetch_arome_france_hd(
        self, lat: float, lon: float, elevation_m: Optional[int] = None
    ) -> list:
        """Fetch AROME-HD (1.5 km) minutely_15 nowcast via Open-Meteo. Fail-soft -> []."""
        return self._fetch_openmeteo_15(lat, lon, models="arome_france_hd", elevation_m=elevation_m)

    def _fetch_icon_d2(
        self, lat: float, lon: float, elevation_m: Optional[int] = None
    ) -> list:
        """Fetch DWD ICON-D2 (~2 km) minutely_15 nowcast via Open-Meteo. Fail-soft -> []."""
        return self._fetch_openmeteo_15(lat, lon, models="icon_d2", elevation_m=elevation_m)

    def _fetch_italy_arpae(
        self, lat: float, lon: float, elevation_m: Optional[int] = None
    ) -> list:
        """Fetch ARPAE ICON-2I (2 km) minutely_15 nowcast via Open-Meteo. Fail-soft -> []."""
        return self._fetch_openmeteo_15(
            lat, lon, models="italia_meteo_arpae_icon_2i", elevation_m=elevation_m
        )

    def _fetch_openmeteo_15(
        self, lat: float, lon: float, models: Optional[str] = None,
        elevation_m: Optional[int] = None,
    ) -> list:
        """Shared Open-Meteo minutely_15 fetch/parse. Optional explicit model. Fail-soft -> [].

        Issue #1329 C2: EINZIGER Funnel, durch den JEDER open-meteo-Zweig
        laeuft (AROME-FR, ICON-D2, ARPAE, finaler minutely_15-Fallback, UND
        der INCA-Sidecar-Aufruf aus _fetch_geosphere_inca) --
        ein Gate-Einbau hier deckt Budget UND Doppelverbrauch-Fix UND
        Offline-Fixture fuer den gesamten open-meteo-Anteil ab.
        """
        if self._openmeteo_unavailable_this_call:
            # Root Cause 3 (Doppelverbrauch-Fix): nach einem ECHTEN
            # Fehlschlag/einer Drosselung in DIESEM get_nowcast()-Aufruf kein
            # zweiter Versuch -- unabhaengig davon, welcher Zweig als
            # naechstes in der Kette folgt. Der bestehende All-None-Guard
            # (unten) setzt dieses Flag NICHT, faellt also weiterhin sauber
            # zum naechsten Modell durch.
            return []
        if _offline_fixture_active():
            return self._load_radar_fixture_frames()
        if not self._budget_gate.allow(self._priority):
            self._budget_throttled_this_call = True
            self._openmeteo_unavailable_this_call = True
            return []
        try:
            import httpx
            from providers.brightsky import RadarFrame
            # Issue #1991 (N1-Nachbesserung): Query-Koordinaten/-Hoehe ueber
            # den EINZIGEN produktiven Erbauer aus openmeteo.py -- kein
            # eigener Dict-/Zuweisungs-Aufbau mehr an dieser Stelle
            # (AST-Waechter tests/test_openmeteo_callsite_elevation_guard.py).
            from providers.openmeteo import _koordinaten_params

            query = _koordinaten_params(lat, lon, elevation_m)
            if models:
                query["models"] = models
            query["minutely_15"] = "precipitation,weather_code"
            query["timezone"] = "UTC"
            query["forecast_minutely_15"] = 96
            url = "https://api.open-meteo.com/v1/forecast?" + urlencode(query)
            self._budget_gate.record_call()  # unmittelbar vor dem echten Fetch
            with httpx.Client(timeout=HTTPX_TIMEOUT) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            m15 = data.get("minutely_15", {})
            times = m15.get("time", [])
            precip_vals = m15.get("precipitation", [])
            wcodes = m15.get("weather_code", [])
            # All-None guard: an explicit regional model (models set) returns
            # precipitation=[None, ...] for points outside its (rotated) grid — no
            # interpolation. Fall through to the global best_match instead of emitting
            # fake-zero frames. Global best_match (models=None) interpolates and never
            # returns all-None for land coords -> unchanged behavior (no regression).
            if models and precip_vals and all(v is None for v in precip_vals):
                return []
            frames = []
            for i, t_str in enumerate(times):
                dt = datetime.fromisoformat(t_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                raw = precip_vals[i] if i < len(precip_vals) else None
                if raw is None:
                    raw = 0.0
                # precipitation is mm per 15 min -> mm/h
                mm_h = float(raw) * 4.0
                code = wcodes[i] if i < len(wcodes) else None
                is_convective = self._is_convective_weathercode(code)
                frames.append(RadarFrame(timestamp=dt, precip_mm_h=mm_h, is_convective=is_convective))
            return frames
        except Exception as e:
            logger.warning(f"Open-Meteo minutely_15 (models={models}) failed: {e}")
            # Root Cause 3: ein ECHTER Fehlschlag (nicht der All-None-Guard
            # oben, der vor diesem except-Block returnt) sperrt weitere
            # open-meteo-Versuche fuer den Rest DIESES get_nowcast()-Aufrufs.
            self._openmeteo_unavailable_this_call = True
            return []

    def _load_radar_fixture_frames(self) -> list:
        """Issue #1329 C2 Abschnitt 8: laedt fixtures/radar/minutely_15.json
        und stempelt die Zeitstempel relativ zu self._now_fn() um (Muster
        FixtureProvider.fetch_forecast: `providers/fixture.py:110-117`).

        Pfad hergeleitet als Geschwister-Verzeichnis von GZ_TEST_FIXTURE_DIR
        (kein neuer Env-Var, derselbe Wurzelpfad wie der Forecast-Fixture-
        Ordner). Fail-soft: fehlende/kaputte Datei -> [] (setzt
        _openmeteo_unavailable_this_call, kein Absturz) -- degradiert zum
        regulaeren "keine Frames -> kein Alarm"-Pfad (Known Limitation a).
        """
        fixture_dir = os.environ.get("GZ_TEST_FIXTURE_DIR", "").strip()
        if not fixture_dir:
            self._openmeteo_unavailable_this_call = True
            return []
        path = Path(fixture_dir).resolve().parent / "radar" / "minutely_15.json"
        try:
            import json
            from providers.brightsky import RadarFrame

            raw = json.loads(path.read_text())
            entries = raw.get("frames") or []
            if not entries:
                raise ValueError("fixture has no frames")
            base = self._now_fn()
            frames = []
            for entry in entries:
                offset_min = entry.get("offset_min", 0)
                precip = entry.get("precip_mm_h", 0.0)
                code = entry.get("weather_code")
                ts = base + timedelta(minutes=offset_min)
                is_convective = self._is_convective_weathercode(code)
                frames.append(
                    RadarFrame(timestamp=ts, precip_mm_h=float(precip), is_convective=is_convective)
                )
            return frames
        except Exception as e:
            logger.warning(f"Radar-Fixture nicht ladbar ({path}): {e}")
            self._openmeteo_unavailable_this_call = True
            return []

    def _derive_result(self, frames: list, source: str, now: Optional[datetime] = None) -> NowcastResult:
        """Derive onset_minutes and intensity_label from frames.

        Issue #1329 C2: `now` optional injizierbar (Default = self._now_fn())
        -- laeuft bei JEDEM Aufruf frisch, egal ob frames aus dem Cache oder
        einem frischen Fetch stammen (Cache liefert nie ein fertiges Ergebnis).
        """
        now = now or self._now_fn()
        horizon = now + timedelta(minutes=_NOWCAST_HORIZON_MIN)

        # Filter to nowcast window
        window = [
            f for f in frames
            if f.timestamp >= now and f.timestamp <= horizon
        ]

        # onset_minutes: first frame with precip >= threshold
        onset_minutes: Optional[int] = None
        for frame in sorted(window, key=lambda f: f.timestamp):
            if frame.precip_mm_h >= _DRY_THRESHOLD_MM_H:
                delta = (frame.timestamp - now).total_seconds() / 60.0
                onset_minutes = max(0, round(delta))
                break

        # Max rate im 180-Min-Nowcast-Fenster -- speist NUR intensity_label
        # (Anzeige). NICHT die Ueberholungspruefung: das NowcastResult-Feld
        # max_rate_mm_h wird weiter unten separat aus dem 60-Min-Vergleichs-
        # fenster gebildet (Adversary-Fund F001, 2026-08-21), damit Raten-
        # und Mengenfenster deckungsgleich sind.
        max_rate = max((f.precip_mm_h for f in window), default=0.0)

        # Convective flag: any wet frame in window with convective indicator
        is_convective = any(
            f.is_convective for f in window if f.precip_mm_h >= _DRY_THRESHOLD_MM_H
        )

        intensity_label = self.intensity_to_text(max_rate, is_convective=is_convective)

        # Issue #1329 C2 AC-6: throttled=True nur wenn KEINE Frames geliefert
        # wurden UND die Ursache eine Budget-Drosselung war (nicht "echt kein
        # Regen"). Beobachtbarkeits-Signal -- radar_alert_due() behandelt
        # onset_minutes=None ohnehin gleich (kein Alarm bei Drosselung).
        throttled = bool(getattr(self, "_budget_throttled_this_call", False)) and not frames

        # Issue #1628 S1: data_unavailable=True nur bei einem ECHTEN
        # Fetch-Fehlschlag (HTTP-Fehlerstatus, Timeout, Verbindungsfehler) --
        # ausdruecklich NICHT bei einer reinen Budget-Drosselung (die setzt
        # _openmeteo_unavailable_this_call zusaetzlich als
        # Doppelverbrauch-Sperre, s. _fetch_openmeteo_15:431-433), sonst
        # waeren Drosselung und echter Ausfall vermengt (AC-5, R4).
        data_unavailable = (
            bool(getattr(self, "_openmeteo_unavailable_this_call", False))
            and not bool(getattr(self, "_budget_throttled_this_call", False))
            and not frames
        )

        # Issue #2020: eigenes 60-Min-Vergleichsfenster fuer die Mengen-
        # Ueberholungspruefung (NICHT das 180-Min-Nowcast-Fenster oben -- das
        # waere ein 3h-Wert gegen einen 1h-Briefingwert). Dauer JE Frame aus
        # seiner UNMITTELBAREN NACHBARSCHAFT in der VOLLSTAENDIGEN Frame-Liste
        # (Adversary-Runde 2, F006/F007, 2026-08-21: eine GLOBALE Kadenz-
        # Schaetzung -- ob Minimum oder Median -- laesst sich immer durch
        # Frames ausserhalb des Vergleichsfensters verfaelschen, in beide
        # Richtungen. Ein Frame darf daher nur ueber seinen eigenen naechsten
        # Nachbarn hinausreichen, NIE ueber eine globale Kennzahl). Zusaetzlich
        # gedeckelt auf `_MAX_FRAME_COVERAGE` (groebstes Produktivraster) UND
        # NIE ueber das Fensterende (compare_horizon) hinaus: ein einzelner
        # Frame nach Datenausfall/Drosselung darf nicht bis zum vollen
        # Fensterende gestreckt werden -- sonst wuerde ein einziges Radarbild
        # zu einem hochgerechneten Alarm. Fehlende Frames machen die Menge
        # dadurch eher zu klein als zu gross (bewusst konservative Richtung,
        # Spec "Known Limitations").
        compare_horizon = now + timedelta(minutes=_OVERTAKE_COMPARE_WINDOW_MIN)
        all_ts_sorted = sorted({f.timestamp for f in frames})
        compare_window = sorted(
            (f for f in frames if f.timestamp >= now and f.timestamp < compare_horizon),
            key=lambda f: f.timestamp,
        )

        # Issue #2020 Adversary-Runde 3, F010: eine Providerwiederholung
        # oder ein Sidecar-Merge (siehe Kommentar zu _MAX_FRAME_COVERAGE
        # oben -- exakt diese Ursache) kann zwei Frames mit IDENTISCHEM
        # Zeitstempel liefern. `all_ts_sorted` ist ein Set und dedupliziert
        # bereits, die Akkumulationsschleife lief bisher aber ueber ALLE
        # (nicht deduplizierten) Frames: bisect_right liefert fuer beide
        # Duplikate denselben next_ts_full, also bekaeme JEDER der beiden
        # unabhaengig die VOLLE Deckung bis dahin -- derselbe Zeitabschnitt
        # wuerde zweimal gezaehlt. Vor der Summierung deshalb auf einen
        # Eintrag je Zeitstempel reduziert. Bei widerspruechlichen Werten
        # zum selben Zeitpunkt gewinnt bewusst der HOEHERE Regenwert: es ist
        # derselbe Zeitabschnitt, er wird genau einmal gezaehlt, und unter
        # widerspruechlichen Messwerten ist der hoehere Wert derjenige,
        # dessen Verlust wehtaete -- dieses Ticket existiert, weil eine
        # Warnung zu spaet kam.
        compare_window_by_ts: dict[datetime, float] = {}
        for frame in compare_window:
            existing = compare_window_by_ts.get(frame.timestamp)
            if existing is None or frame.precip_mm_h > existing:
                compare_window_by_ts[frame.timestamp] = frame.precip_mm_h

        window_precip_mm = 0.0
        for ts, rate in sorted(compare_window_by_ts.items()):
            next_idx = bisect.bisect_right(all_ts_sorted, ts)
            next_ts_full = (
                all_ts_sorted[next_idx] if next_idx < len(all_ts_sorted)
                else compare_horizon
            )
            frame_end = min(next_ts_full, ts + _MAX_FRAME_COVERAGE, compare_horizon)
            duration_h = max(0.0, (frame_end - ts).total_seconds() / 3600.0)
            window_precip_mm += rate * duration_h

        # Issue #2020 Adversary-Fund F001: max_rate_mm_h fuer die
        # Ueberholungspruefung MUSS aus demselben Fenster stammen wie
        # window_precip_mm (60 Min compare_window), sonst legitimiert ein
        # spaeter, voellig unabhaengiger Starkregen-Ausbruch (z. B. bei
        # +150 Min, weit ausserhalb des Vergleichsfensters) die Ueberholung
        # fuer ganz anderen, schwachen Nahregen. `max_rate` oben (180 Min)
        # bleibt unveraendert fuer intensity_label -- NUR dieses Feld
        # wechselt das Fenster.
        compare_window_max_rate_mm_h = max(
            (f.precip_mm_h for f in compare_window), default=0.0
        )

        return NowcastResult(
            onset_minutes=onset_minutes,
            intensity_label=intensity_label,
            source=source,
            frames=frames,
            is_convective=is_convective,
            convective_checked=self._convective_checked,
            throttled=throttled,
            data_unavailable=data_unavailable,
            max_rate_mm_h=compare_window_max_rate_mm_h,
            window_precip_mm=window_precip_mm,
        )


def _within_radolan(lat: float, lon: float) -> bool:
    return (
        _RADOLAN_LAT_MIN <= lat <= _RADOLAN_LAT_MAX
        and _RADOLAN_LON_MIN <= lon <= _RADOLAN_LON_MAX
    )


def _within_inca(lat: float, lon: float) -> bool:
    return (
        _INCA_LAT_MIN <= lat <= _INCA_LAT_MAX
        and _INCA_LON_MIN <= lon <= _INCA_LON_MAX
    )


def _within_italy_radar(lat: float, lon: float) -> bool:
    return (
        _ITALY_RADAR_LAT_MIN <= lat <= _ITALY_RADAR_LAT_MAX
        and _ITALY_RADAR_LON_MIN <= lon <= _ITALY_RADAR_LON_MAX
    )


def _within_arome_france(lat: float, lon: float) -> bool:
    return (
        _AROME_FR_LAT_MIN <= lat <= _AROME_FR_LAT_MAX
        and _AROME_FR_LON_MIN <= lon <= _AROME_FR_LON_MAX
    )


def _within_icon_d2(lat: float, lon: float) -> bool:
    return (
        _ICON_D2_LAT_MIN <= lat <= _ICON_D2_LAT_MAX
        and _ICON_D2_LON_MIN <= lon <= _ICON_D2_LON_MAX
    )


def _region_bucket(lat: float, lon: float) -> str:
    """Primaere Regions-Klassifikation einer Koordinate -- reine,
    deterministische Funktion der Koordinaten, DIESELBE Reihenfolge wie die
    tatsaechliche Quellenkette in `_fetch_frames_with_fallback`. Bestandteil
    des Radar-Cache-Schluessels (Adversary-Fund F001, Issue #1329 C2,
    BROKEN-Verdict behoben): ohne Region im Schluessel konnten zwei
    Koordinaten beidseits einer harten Routing-Grenze (z.B. RADOLAN-Rand
    bei lat=47.0, nur ~1m auseinander) auf denselben gerundeten
    Koordinaten-Schluessel fallen und sich faelschlich einen Cache-Eintrag
    der jeweils ANDEREN Region/Quelle teilen.

    Bildet bewusst die PRIMAER gewaehlte Region ab (den ersten Treffer in
    der Bounding-Box-Kette), NICHT die nach evtl. Fallback tatsaechlich
    resolvte Quelle (z.B. AROME-FR-Fehlschlag -> minutely_15-Fallback) --
    das ist konsistent, weil der Cache-Lookup VOR dem Fetch passiert und
    den finalen resolvten Wert prinzipiell noch nicht kennen kann. Der
    tatsaechlich resolvte Wert wird weiterhin unveraendert als `source`-
    Metadatum im Cache-Eintrag mitgefuehrt (nicht als Schluesselbestandteil).
    """
    if _within_radolan(lat, lon):
        return "radolan"
    if _within_inca(lat, lon):
        return "inca"
    if _within_italy_radar(lat, lon):
        return "italy_radar"
    if _within_arome_france(lat, lon):
        return "arome_france"
    if _within_icon_d2(lat, lon):
        return "icon_d2"
    return "global"


def _nowcast_source_key(lat: float, lon: float) -> str:
    """Korrelations-Schluessel fuer Zweig c (#1948, AC-4) -- dieselbe
    Koordinaten+Region-Formel wie `RadarNowcastCacheService._key`, EINMAL
    hier definiert fuer Schreib- (`get_nowcast`) und Lesepfad
    (`trip_alert.py`-Lookup)."""
    return f"{round(lat, 4)}_{round(lon, 4)}_{_region_bucket(lat, lon)}"


def _capture_nowcast_frames(lat: float, lon: float, frames: list, source: str) -> None:
    """Roher Eingangs-Datensatz VOR `_derive_result` (#1948, AC-3)."""
    try:
        alert_input_capture.capture_system(
            branch="nowcast", source_key=_nowcast_source_key(lat, lon),
            payload={
                "source": source,
                "frames": [
                    {"timestamp": f.timestamp.isoformat(), "precip_mm_h": f.precip_mm_h,
                     "is_convective": f.is_convective}
                    for f in frames
                ],
            },
        )
    except Exception as e:
        logger.warning("radar_service: Eingangs-Mitschnitt fehlgeschlagen: %s", e)
