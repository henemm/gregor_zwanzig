"""`LocationWeatherSource`-Implementierung für Compare-Orte.

Issue #1169 — Scheibe 2/3, Epic #1095.

Baut je Ort ein synthetisches Ein-Punkt-`TripSegment` (`start_point ==
end_point`, minimales Zeitfenster) und nutzt
`SegmentWeatherService.fetch_segment_weather()` +
`TripSegmentWeatherAdapter.to_points()` — damit sind der beim Compare-Report-
Versand geschriebene Anker-Snapshot und das beim 15-Min-Alert-Check gefetchte
fresh-Wetter **durch denselben Code-Pfad** erzeugt (Form-/Provider-Mismatch
strukturell ausgeschlossen, Spec-Abschnitt A1). Provider-Wahl über
`get_provider("openmeteo")` (Epic #1301 A2 — Ortsvergleich holt ueberall
openmeteo). `enrich_ensemble=False`
beim Fetch (Bug #288-Analogon — Alert-Checks duerfen kein API-Kontingent
konsumieren).

SPEC: docs/specs/modules/issue_1169_compare_alert_consumer.md
SPEC: docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md (Tagesfenster)
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import app.day_window as day_window
from app.models import GPXPoint, TripSegment
from services.point_weather import PointWeatherData, TripSegmentWeatherAdapter
from services.segment_weather import SegmentWeatherService
from utils.timezone import local_dt, to_utc

logger = logging.getLogger("compare_location_weather_source")


def _window_bound(local_day: date, hour: int, tz: ZoneInfo) -> datetime:
    """Ortszeit-Stunde eines lokalen Kalendertags -> UTC. Seit #1599 nur noch
    fuer die UNTERgrenze — die Obergrenze baut
    `app.day_window.window_end_utc_exclusive()` (inklusive Endstunde)."""
    return to_utc(
        datetime.combine(local_day, time(hour)).replace(tzinfo=tz)
    )


class CompareLocationWeatherSource:
    """`LocationWeatherSource`-Protocol-Implementierung für Compare-Orte
    (`services/point_weather.py:67-76`)."""

    def fetch(
        self,
        point_id: str,
        lat: float,
        lon: float,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        target_date: Optional[date] = None,
        tage_ab_ortstag: Optional[int] = None,
    ) -> PointWeatherData:
        """Issue #1584 Scheibe C: das synthetische Segment deckt das
        TAGESFENSTER des laufenden lokalen Kalendertags am Ort ab, nicht mehr
        eine Stunde bei `now`. Anker (Report-Versand) und Frisch-Abruf
        (15-Min-Alarm-Check) laufen durch denselben Code — mit dem Tagesfenster
        haben sie dadurch **durch Konstruktion** denselben Zuschnitt, statt
        zwei verschiedene Tagesstunden zu vergleichen.

        `start_hour`/`end_hour` kommen vom Aufrufer aus
        `resolve_compare_time_window(preset)` (ADR-0035, EINE Fensterquelle für
        Anzeige und Bewertung). `None` faellt ueber denselben geteilten
        Aufloeser auf den Default 4/19 zurueck.

        Issue #1661 (B1): Der KALENDERTAG des Fensters laesst sich auf ZWEI
        Arten vorgeben — und die beiden bedeuten bewusst Verschiedenes:

        * `tage_ab_ortstag` (SCHREIBSEITE, Δ-Anker): ein VERSATZ in Tagen
          gegenueber dem ortslokalen Tag (Morgen-Slot 0, Abend-Slot +1). Der
          Kalendertag entsteht dadurch weiterhin aus der ORTSZEIT — genau wie
          vor dieser Scheibe. Ein absoluter Tag vom Aufrufer waere hier
          falsch: der Dispatch-Loop bildet ihn aus `date.today()`
          (Systemzeit = UTC auf dem Server), und fuer jeden Ort ab UTC+6
          oestlich bzw. UTC-7 westlich zeigt dieser UTC-Tag zur Slot-Zeit auf
          einen anderen Ortstag (Adversary-Finding F002).
        * `target_date` (LESESEITE, 15-Minuten-Δ-Check): ein bereits
          aufgeloester, ABSOLUTER Tag, den der Anker traegt. Er muss exakt so
          getroffen werden, damit Anker und Frisch-Abruf denselben Tag
          beschreiben.

        Ohne beides verhaelt sich `fetch()` exakt wie vor #1661 — laufender
        lokaler Tag am Ort, kein Tagesstempel am Ergebnis. Beides gleichzeitig
        ist ein Programmierfehler und scheitert laut (`ValueError`), statt
        still einen der beiden Wege gewinnen zu lassen.

        Der AUFGELOESTE Tag wird auf das Ergebnis gestempelt, damit der
        15-Minuten-Frisch-Abruf spaeter DENSELBEN Tag holen kann.
        """
        if target_date is not None and tage_ab_ortstag is not None:
            raise ValueError(
                "CompareLocationWeatherSource.fetch: `target_date` (absoluter "
                "Tag, Leseseite) und `tage_ab_ortstag` (Versatz gegen den "
                "Ortstag, Schreibseite) schliessen einander aus — es gibt "
                f"sonst zwei Wahrheiten ueber den Kalendertag (Ort {point_id}, "
                f"target_date={target_date}, tage_ab_ortstag={tage_ab_ortstag})."
            )
        from app.day_window import resolve_configured_window
        from providers.base import get_provider
        from utils.timezone import tz_for_coords

        provider = get_provider("openmeteo")
        service = SegmentWeatherService(provider)

        start_hour, end_hour = resolve_configured_window(start_hour, end_hour)
        tz = tz_for_coords(lat, lon)
        now = datetime.now(timezone.utc)
        # Der Kalendertag ist der LOKALE Tag am Ort, nicht der UTC-Tag —
        # sonst verschoebe sich das Fenster bei jedem Ort mit UTC-Versatz
        # (analog `trip_segments.py:264-268`).
        local_today = local_dt(now, tz).date()
        # Issue #1661 (B1): der angeforderte Tag gewinnt gegen den laufenden.
        # Der Versatz wird gegen den ORTSTAG gerechnet (F002) — nie gegen den
        # Systemtag des Aufrufers.
        if tage_ab_ortstag is not None:
            window_day = local_today + timedelta(days=tage_ab_ortstag)
        else:
            window_day = target_date or local_today
        window_start = _window_bound(window_day, start_hour, tz)
        # Issue #1599: Obergrenze INKLUSIV — `end_hour = 19` heisst, die Stunde
        # 19 zaehlt vollstaendig mit; zeitlich endet das Fenster um 20:00
        # Ortszeit (exklusiv). Der Filter in `segment_weather.py` bleibt
        # unveraendert halboffen (`< end_floor`, Bug #806) — er bekommt jetzt
        # nur die richtige Grenze. Dieselbe Umrechnung wie im Trip-Alarmpfad,
        # aus derselben Quelle (`app/day_window.py`).
        window_end = day_window.window_end_utc_exclusive(window_day, end_hour, tz)

        if window_end <= window_start:
            # Tagesfenster ueber Mitternacht (`start > end`, seit #1361
            # gueltig) — ein einzelnes zusammenhaengendes Segment kann das
            # nicht darstellen. Wie beim Ziel-Segment (`trip_segments.py:275`)
            # wird hier NICHT uebersprungen: ein fehlendes Segment liesse den
            # Ortsvergleich still aus der Ueberwachung fallen (genau der
            # #1584-Fehler). Stattdessen ein minimales, aber gueltiges Fenster.
            logger.warning(
                "Compare-Wetterfenster fuer Ort %s: Tagesfenster %d-%d Uhr laeuft "
                "ueber Mitternacht — minimales Fenster von 1 h ab %s wird verwendet",
                point_id, start_hour, end_hour, now.isoformat(),
            )
            window_start = now.replace(minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(hours=1)

        point = GPXPoint(lat=lat, lon=lon, elevation_m=None, distance_from_start_km=0.0)
        segment = TripSegment(
            segment_id=point_id,
            start_point=point,
            end_point=point,
            start_time=window_start,
            end_time=window_end,
            duration_hours=(window_end - window_start).total_seconds() / 3600,
            distance_km=0.0,
            ascent_m=0,
            descent_m=0,
            # Issue #1468 (E2): dasselbe Fenster, das oben schon `window_start`/
            # `window_end` bestimmt hat -- hier bereits ueber
            # `resolve_configured_window()` aufgeloest, also kein zweiter
            # Aufloeser, nur die Weitergabe. Ohne diese Angabe filterte die
            # Beginn-Berechnung zusaetzlich gegen den Default 4-19 und schnitte
            # bei einem WEITEREN Vergleichs-Fenster Stunden weg, die der
            # Ortsvergleich sehr wohl zeigt. Trip und Ortsvergleich verhalten
            # sich damit gleich (Teilungs-Invariante).
            day_window_start_hour=start_hour,
            day_window_end_hour=end_hour,
        )
        segment_weather = service.fetch_segment_weather(
            segment,
            enrich_ensemble=False,
            enrich_snow=False,
            priority="alert_check",  # Issue #1329 Teil 2
        )
        point = TripSegmentWeatherAdapter.to_points([segment_weather])[0]
        # Issue #1661 (B1): den AUFGELOESTEN Tagesbezug mitgeben, wenn einer
        # angefordert wurde — beim Versatz ist das der ortslokal gebildete Tag,
        # nicht der Versatz selbst. Ohne Angabe bleibt das Feld `None`
        # (Bestandsverhalten, Altbestand-Anker, Trip-Pfad).
        if target_date is None and tage_ab_ortstag is None:
            return point
        return replace(point, target_date=window_day)
