"""Amtliche-Warnung-Dedup: Zeitraum als Identitaetsbestandteil (Issue #1245).

SPEC: docs/specs/modules/issue_1245_official_alert_dedup_timespan.md (AC-1..AC-7)
KONTEXT: docs/context/fix-1245-alert-dedup-timespan.md

RED (reproduziert den Bug, muss VOR dem Fix fehlschlagen):
- AC-1: zwei Perioden gleicher Region+Gefahr+Stufe, verschiedener Zeitraum ->
  `dedupe_official_alerts` verwirft heute die zweite Periode still.
- AC-4: Trip-Trigger erkennt eine echte neue Periode (gleiche Region+Gefahr,
  anderer Zeitraum) im Folgelauf nicht, weil sie schon in der Dedup verschluckt wird.
- AC-5: zwei verschiedene Massiv-Sperren (unterschiedliche dedup_id,
  region_label=None) teilen sich heute denselben Trigger-State-Key
  ("official_alert:None:access_ban") -> gegenseitige Ueberschreibung.
- AC-6: die kompakten Renderer (Badge/Plain) zeigen zwei Perioden derselben
  Region+Gefahr+Stufe heute textidentisch (kein Zeitraum-Zusatz).

Non-Regression (JETZT SCHON GRUEN, muss nach dem Fix gruen bleiben):
- AC-2: identischer Zeitraum + unterschiedliche Stufe -> Kollaps zum hoechsten Level.
- AC-3: Massiv-Eskalation (dedup_id konstant, None/None-Zeitraum) kollabiert weiter.
- AC-7: Warnung ohne Zeitraum bekommt keinen Zeit-Zusatz/Platzhalter im Renderer.

Mock-frei: echte `OfficialAlert`-DTOs, echte `dedupe_official_alerts`/Renderer-
Aufrufe, echte `TripAlertService`-Laeufe mit registrierten Fake-Quellen
(strukturelles Protocol-Subtyping, kein Mock()/patch()), echte alert_state-
Persistenz unter data/users/<frischer-user>/ (Projektkonvention, s.
test_issue_1088_official_alert_triggers.py).
"""
from __future__ import annotations

import html as html_module
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from output.renderers.alert.official_alerts import (
    dedupe_official_alerts,
    render_official_alerts_html,
    render_official_alerts_plain,
)
from services.official_alerts.models import OfficialAlert

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"
LAT, LON = 47.0, 11.0


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1245-{prefix}-{uuid.uuid4().hex[:6]}"


def _registered_sources_backup():
    import services.official_alerts.base as oa_base
    return oa_base, list(oa_base._REGISTERED_SOURCES)


def _massif_alert(level: int, *, dedup_id: str = "ESTEREL-MASSIF-ID") -> OfficialAlert:
    """Wie massif_closure._niveau_to_alert (nach #1217/#1218): region_label=None,
    Stufe im Label-Text codiert, stabile stufen-unabhaengige dedup_id.
    Reproduziert exakt die Fixture-Form aus test_mail_alert_dedup.py:202-211."""
    wording = {3: "Zugang eingeschränkt", 4: "Zugang gesperrt"}[level]
    return OfficialAlert(
        source="massif_closure", hazard="access_ban", level=level,
        label=f"{wording} — Massif de l'Esterel", region_label=None,
        dedup_id=dedup_id,
    )


def _segment(segment_id: int | str = 1, *, lat: float = LAT, lon: float = LON) -> TripSegment:
    start = datetime(2026, 7, 8, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=lat + 0.1, lon=lon + 0.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, *, lat: float = LAT, lon: float = LON, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id, lat=lat, lon=lon),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _minimal_trip(trip_id: str, **trip_kwargs) -> Trip:
    """Trip ohne aktive Wetter-Delta-Regeln, official_warnings=None (Bestands-
    trip-Fallback, analog test_issue_1088_official_alert_triggers._minimal_trip)."""
    trip_kwargs.setdefault("official_warnings", None)
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 7, 8),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Dedup-Zeitraum-Trip", stages=[stage], **trip_kwargs)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _save_cached(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), cached)


class _MultiPeriodOfficialAlertSource:
    """Echte Quelle (kein Mock) mit veraenderbarer Alert-Liste — modelliert,
    dass Météo-France im naechsten Lauf eine echte zweite Periode meldet
    (#1245 AC-4)."""

    def __init__(self, lat: float, lon: float, alerts: list[OfficialAlert]) -> None:
        self._lat = lat
        self._lon = lon
        self.alerts = list(alerts)

    @property
    def name(self) -> str:
        return "test-1245-multi-period"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        return list(self.alerts)


class _SingleMassifOfficialAlertSource:
    """Echte Quelle fuer EIN Massiv (eigene Koordinate, eigene dedup_id,
    steuerbares Level) — analog `MassifClosureSource`, die je Massiv nur an
    dessen eigener Koordinate zustaendig ist (`covers()`). Zwei Instanzen an
    zwei verschiedenen Koordinaten reproduzieren #1245 AC-5 (State-Key-
    Kollision zweier Massive), OHNE den unabhaengigen Cross-Source-Hazard-
    Kollaps von `get_official_alerts_for_location()` (base.py:80-96) faelschlich
    mitanzustossen — der greift nur INNERHALB eines einzelnen (lat, lon)-Rufs."""

    def __init__(self, lat: float, lon: float, dedup_id: str, label_prefix: str) -> None:
        self._lat = lat
        self._lon = lon
        self._dedup_id = dedup_id
        self._label_prefix = label_prefix
        self.level = 3

    @property
    def name(self) -> str:
        return f"test-1245-massif-{self._dedup_id}"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        return [OfficialAlert(
            source="test-1245-massif", hazard="access_ban", level=self.level,
            label=f"{self._label_prefix} Stufe {self.level} (#1245 AC-5)",
            dedup_id=self._dedup_id,
        )]


class TestAC1TwoPeriodsSameRegionHazardStaySeparate:
    def test_two_periods_same_region_hazard_stay_separate(self):
        """AC-1 (RED — Ur-Reproduktion aus dem Issue): Vigilance Hitze Stufe 3,
        Mo 04:00-22:00 UTC und Mo 22:00-Di 22:00 UTC, gleiche Region+Gefahr+Stufe
        -> beide Perioden muessen erhalten bleiben."""
        region = "Cévennes"
        hazard = "extreme_heat"
        period_a_from = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
        period_a_to = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
        period_b_from = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
        period_b_to = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)

        alert_a = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=period_a_from, valid_to=period_a_to,
        )
        alert_b = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=period_b_from, valid_to=period_b_to,
        )

        result = dedupe_official_alerts([(alert_a, []), (alert_b, [])])

        assert len(result) == 2, (
            f"Zwei Perioden mit unterschiedlichem Zeitraum duerfen nicht still "
            f"kollabieren, erhalten: {result!r}"
        )
        valid_tos = {a.valid_to for a, _ in result}
        assert valid_tos == {period_a_to, period_b_to}, (
            f"Beide Zeitraeume muessen im Ergebnis erhalten bleiben, erhalten: {valid_tos!r}"
        )


class TestAC2SamePeriodDifferentLevelCollapsesToHighest:
    def test_same_period_different_level_collapses_to_highest(self):
        """AC-2 (Non-Regression, MUSS SCHON GRUEN sein): identische Identitaet+
        Gefahr+Zeitraum, unterschiedliche Stufe -> Kollaps zum hoechsten Level."""
        region = "Cévennes"
        hazard = "extreme_heat"
        vf = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
        vt = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)

        alert_level3 = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=vf, valid_to=vt,
        )
        alert_level4 = OfficialAlert(
            source="meteo-france", hazard=hazard, level=4,
            label="Vigilance Hitze Stufe Rouge", region_label=region,
            valid_from=vf, valid_to=vt,
        )

        result = dedupe_official_alerts([(alert_level3, []), (alert_level4, [])])

        assert len(result) == 1, f"Gleicher Zeitraum muss weiterhin kollabieren, erhalten: {result!r}"
        assert result[0][0].level == 4, "Der hoechste Level (4) muss ueberleben"


class TestAC3MassifEscalationNonePeriodStillCollapses:
    def test_massif_escalation_none_period_still_collapses(self):
        """AC-3 (Non-Regression, MUSS SCHON GRUEN sein): zwei Massiv-Sperren,
        gleiche dedup_id, region_label=None, kein Zeitraum, Stufe 3 und 4 ->
        weiterhin EIN Eintrag Stufe 4 (#1172/#1200/#1217/#1218)."""
        alert3 = _massif_alert(3)
        alert4 = _massif_alert(4)

        result = dedupe_official_alerts([(alert3, []), (alert4, [])])

        assert len(result) == 1, (
            f"Massiv-Eskalation (dedup_id konstant, kein Zeitraum) muss weiterhin "
            f"kollabieren, erhalten: {result!r}"
        )
        assert result[0][0].level == 4, "Der hoechste Level (4) muss ueberleben"


class TestAC4TriggerNewPeriodFiresIndependently:
    def test_trigger_new_period_fires_independently(self):
        """AC-4 (RED): Periode A bereits im Zustand gespeichert. Im naechsten
        Lauf tritt eine echte neue Periode B (gleiche Region+Gefahr, anderer
        Zeitraum) hinzu -> B muss als neuer Alarm erkannt werden, A darf nicht
        ueberschrieben werden."""
        from services.alert_state import AlertStateService
        from services.official_alerts import register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac4")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = _minimal_trip("trip-1245-ac4")
            _save_cached(user_id, trip.id, [_data(1, precip_sum_mm=2.0)])

            region = "Cevennes-1245-AC4"
            hazard = "extreme_heat"
            period_a_from = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
            period_a_to = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
            period_b_from = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
            period_b_to = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)

            alert_a = OfficialAlert(
                source="test-1245-ac4", hazard=hazard, level=3,
                label="Vigilance Hitze Stufe Orange (Periode A, #1245 AC-4)",
                region_label=region, valid_from=period_a_from, valid_to=period_a_to,
            )
            alert_b = OfficialAlert(
                source="test-1245-ac4", hazard=hazard, level=3,
                label="Vigilance Hitze Stufe Orange (Periode B, #1245 AC-4)",
                region_label=region, valid_from=period_b_from, valid_to=period_b_to,
            )

            source = _MultiPeriodOfficialAlertSource(LAT, LON, [alert_a])
            register_official_alert_source(source)

            svc = TripAlertService(user_id=user_id)

            round1 = svc.check_official_alert_triggers(trip)
            assert len(round1) == 1, f"Periode A muss beim ersten Lauf neu erkannt werden: {round1!r}"
            svc._record_official_alert_state(trip.id, round1)

            source.alerts = [alert_a, alert_b]
            round2 = svc.check_official_alert_triggers(trip)

            period_b_hits = [a for a, _ in round2 if a.valid_to == period_b_to]
            assert len(period_b_hits) == 1, (
                f"Periode B (neuer Zeitraum, gleiche Region+Gefahr) muss als neuer "
                f"Alarm erkannt werden, round2={round2!r}"
            )

            svc._record_official_alert_state(trip.id, round2)
            state = AlertStateService(user_id=user_id).load(trip.id)
            assert len(state) >= 2, (
                f"Periode A und Periode B muessen getrennte State-Keys erhalten "
                f"(A darf nicht durch B ueberschrieben werden), erhalten: {list(state.keys())}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC5TwoDistinctMassifsKeepSeparateState:
    def test_two_distinct_massifs_keep_separate_state(self):
        """AC-5 (RED): zwei verschiedene Massiv-Sperren (unterschiedliche
        dedup_id, region_label=None, je eigene Koordinate/Segment — analog
        `MassifClosureSource`) teilen sich heute den State-Key
        'official_alert:None:access_ban' -> gegenseitige Ueberschreibung."""
        from services.alert_state import AlertStateService
        from services.official_alerts import register_official_alert_source
        from services.trip_alert import TripAlertService

        user_id = _fresh_user("ac5")
        _clean_user(user_id)
        oa_base, backup = _registered_sources_backup()
        oa_base._REGISTERED_SOURCES.clear()
        try:
            trip = _minimal_trip("trip-1245-ac5")
            other_lat, other_lon = LAT + 5.0, LON + 5.0
            _save_cached(user_id, trip.id, [
                _data(1, lat=LAT, lon=LON, precip_sum_mm=2.0),
                _data(2, lat=other_lat, lon=other_lon, precip_sum_mm=2.0),
            ])

            dedup_a, dedup_b = "massif-alpha-1245", "massif-beta-1245"
            source_a = _SingleMassifOfficialAlertSource(LAT, LON, dedup_a, "Massiv Alpha")
            source_b = _SingleMassifOfficialAlertSource(other_lat, other_lon, dedup_b, "Massiv Beta")
            source_a.level = 4
            source_b.level = 2
            register_official_alert_source(source_a)
            register_official_alert_source(source_b)

            svc = TripAlertService(user_id=user_id)
            round1 = svc.check_official_alert_triggers(trip)
            assert len(round1) == 2, f"Beide Massive muessen beim ersten Lauf neu erkannt werden: {round1!r}"
            svc._record_official_alert_state(trip.id, round1)

            state = AlertStateService(user_id=user_id).load(trip.id)
            assert len(state) == 2, (
                f"Zwei verschiedene Massive (dedup_id) muessen zwei getrennte "
                f"State-Keys erhalten, erhalten: {list(state.keys())}"
            )

            # Massiv Beta eskaliert (2->3), Massiv Alpha bleibt unveraendert (4).
            source_b.level = 3
            round2 = svc.check_official_alert_triggers(trip)

            alpha_refired = [a for a, _ in round2 if a.dedup_id == dedup_a]
            beta_escalated = [a for a, _ in round2 if a.dedup_id == dedup_b]
            assert alpha_refired == [], (
                f"Massiv Alpha ist unveraendert und darf NICHT erneut feuern — "
                f"Bug: State-Key-Kollision mit Massiv Beta, round2={round2!r}"
            )
            assert len(beta_escalated) == 1, f"Massiv Beta muss als Eskalation erkannt werden: {round2!r}"
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _clean_user(user_id)


class TestAC6CompactRenderersShowDistinctPeriods:
    def test_compact_renderers_show_distinct_periods(self):
        """AC-6 (RED): zwei Perioden gleicher Region+Gefahr+Stufe muessen sich
        im Badge (`render_official_alerts_html`) UND in der Plain-Zeile
        (`render_official_alerts_plain`) unterscheiden (Zeitraum-Zusatz)."""
        region = "Cévennes"
        hazard = "extreme_heat"
        period_a_from = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
        period_a_to = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
        period_b_from = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
        period_b_to = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)

        alert_a = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=period_a_from, valid_to=period_a_to,
        )
        alert_b = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=period_b_from, valid_to=period_b_to,
        )

        html = render_official_alerts_html([(region, [alert_a, alert_b])])
        badges = [seg + "</div>" for seg in html.split("</div>") if seg.strip()]
        assert len(badges) == 2, f"Erwartet 2 Badges, erhalten {len(badges)}: {html!r}"
        assert badges[0] != badges[1], (
            f"Die zwei Perioden muessen sich im Badge-Text unterscheiden (Zeitraum-"
            f"Zusatz), erhalten identisch: {badges[0]!r}"
        )

        plain_lines = render_official_alerts_plain([(region, [alert_a, alert_b])])
        assert len(plain_lines) == 2, f"Erwartet 2 Plain-Zeilen, erhalten: {plain_lines!r}"
        assert plain_lines[0] != plain_lines[1], (
            f"Die zwei Perioden muessen sich in der Plain-Zeile unterscheiden "
            f"(Zeitraum-Zusatz), erhalten identisch: {plain_lines[0]!r}"
        )

    def test_compact_renderers_distinguish_periods_seven_days_apart_same_weekday_hour(self):
        """Adversary F002 (HOCH, Fix-Loop): zwei Perioden mit GLEICHEM
        Wochentag+Stunde, aber 7 Kalendertagen Abstand, muessen sich trotzdem
        unterscheiden. Das anfangs verwendete SMS-Kurzformat (`_tag_time`,
        nur Wochentag-Kuerzel+Stunde, kein Datum) haette beide Badges/Zeilen
        byte-identisch gerendert -- der Renderer muss ein datumsbehaftetes
        Format nutzen (`_format_validity`)."""
        region = "Cévennes"
        hazard = "extreme_heat"
        period_c_from = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
        period_c_to = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
        period_d_from = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
        period_d_to = datetime(2026, 7, 20, 22, 0, tzinfo=timezone.utc)
        assert period_c_from.strftime("%w %H") == period_d_from.strftime("%w %H"), (
            "Testvoraussetzung verletzt: Wochentag+Stunde muessen identisch sein, "
            "nur das Kalenderdatum darf abweichen (7 Tage)"
        )

        alert_c = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=period_c_from, valid_to=period_c_to,
        )
        alert_d = OfficialAlert(
            source="meteo-france", hazard=hazard, level=3,
            label="Vigilance Hitze Stufe Orange", region_label=region,
            valid_from=period_d_from, valid_to=period_d_to,
        )

        html = render_official_alerts_html([(region, [alert_c, alert_d])])
        badges = [seg + "</div>" for seg in html.split("</div>") if seg.strip()]
        assert len(badges) == 2, f"Erwartet 2 Badges, erhalten {len(badges)}: {html!r}"
        assert badges[0] != badges[1], (
            f"7 Tage auseinanderliegende Perioden mit gleichem Wochentag+Stunde "
            f"muessen sich im Badge-Text unterscheiden (Kalenderdatum im Zusatz), "
            f"erhalten identisch: {badges[0]!r}"
        )

        plain_lines = render_official_alerts_plain([(region, [alert_c, alert_d])])
        assert len(plain_lines) == 2, f"Erwartet 2 Plain-Zeilen, erhalten: {plain_lines!r}"
        assert plain_lines[0] != plain_lines[1], (
            f"7 Tage auseinanderliegende Perioden muessen sich in der Plain-Zeile "
            f"unterscheiden, erhalten identisch: {plain_lines[0]!r}"
        )


class TestAC7RendererWithoutPeriodNoSuffix:
    def test_renderer_without_period_no_suffix(self):
        """AC-7 (Non-Regression, MUSS SCHON GRUEN sein): Warnung ohne Zeitraum
        (valid_from/valid_to=None) bekommt KEINEN Zeit-Zusatz und KEIN
        'unbekannt'-Platzhalter."""
        alert = OfficialAlert(
            source="meteo_forets", hazard="wildfire", level=3,
            label="Waldbrand-Gefahr Stufe 3", region_label="Var",
        )
        assert alert.valid_from is None and alert.valid_to is None

        html = render_official_alerts_html([("Var", [alert])])
        assert "unbekannt" not in html.lower(), f"Kein 'unbekannt'-Platzhalter erwartet: {html!r}"
        escaped_label = html_module.escape(alert.label)
        assert f"<span>{escaped_label}</span></div>" in html, (
            f"Zeitlose Warnung darf keinen Zeit-Zusatz im Badge tragen, erhalten: {html!r}"
        )

        plain_lines = render_official_alerts_plain([("Var", [alert])])
        assert plain_lines == [f"Amtliche Warnung: {alert.label}"], (
            f"Zeitlose Warnung muss byte-stabil zum Vorher-Verhalten bleiben, "
            f"erhalten: {plain_lines!r}"
        )


class _RealGeoSphereLikeSource:
    """Echte Test-Quelle (kein Mock): erfuellt das OfficialAlertSource-Protocol
    strukturell, liefert einen festen Alert mit ECHTEM (nicht None/None)
    Zeitraum -- reproduziert geosphere_warn.py, das reale valid_from/valid_to
    aus der Live-API setzt (Adversary F001)."""

    name = "geosphere_warn"

    def __init__(self, valid_from: datetime, valid_to: datetime, level: int) -> None:
        self._valid_from = valid_from
        self._valid_to = valid_to
        self._level = level

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [OfficialAlert(
            source="geosphere_warn", hazard="extreme_heat", level=self._level,
            label="Hitze", region_label="Villach",
            valid_from=self._valid_from, valid_to=self._valid_to,
        )]


class _RealMeteoAlarmLikeSource:
    """Echte Test-Quelle (kein Mock): analog `_RealGeoSphereLikeSource`,
    reproduziert meteoalarm.py (ebenfalls echter Zeitraum aus CAP onset/expires)."""

    name = "meteoalarm"

    def __init__(self, valid_from: datetime, valid_to: datetime, level: int) -> None:
        self._valid_from = valid_from
        self._valid_to = valid_to
        self._level = level

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [OfficialAlert(
            source="meteoalarm", hazard="extreme_heat", level=self._level,
            label="Hitzewarnung", region_label="Villach (Stadt)",
            valid_from=self._valid_from, valid_to=self._valid_to,
        )]


class TestF001CrossSourceCollapseSurvivesTimespanFix:
    def test_cross_source_same_hazard_minutes_apart_still_collapses(self):
        """Adversary F001 (KRITISCH, Fix-Loop): GIVEN zwei ECHTE Quellen
        (GeoSphere-artig + MeteoAlarm-artig, kein Mock) fuer denselben Punkt,
        gleiche Gefahr, ECHTE (nicht None/None) Zeitraeume, die nur um
        Minuten voneinander abweichen (reale Live-API-Realitaet, s.
        `geosphere_warn.py`/`meteoalarm.py`) / WHEN
        `get_official_alerts_for_location()` aufgerufen wird / THEN muessen
        beide weiterhin zu GENAU EINEM Eintrag kollabieren (#1086
        Cross-Source-Dedup darf durch den #1245-Zeitraum-Fix nicht brechen),
        hoechster Level gewinnt."""
        import services.official_alerts.base as oa_base
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        backup_sources = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            vf_geo = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
            vt_geo = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
            # Nur Minuten abweichend -- typische Realitaet zweier unabhaengiger
            # amtlicher Dienste fuer dasselbe Ereignis.
            vf_meteoalarm = datetime(2026, 7, 13, 4, 1, tzinfo=timezone.utc)
            vt_meteoalarm = datetime(2026, 7, 13, 21, 58, tzinfo=timezone.utc)

            register_official_alert_source(_RealGeoSphereLikeSource(vf_geo, vt_geo, level=2))
            register_official_alert_source(
                _RealMeteoAlarmLikeSource(vf_meteoalarm, vt_meteoalarm, level=3)
            )

            alerts = get_official_alerts_for_location(LAT, LON)

            heat_alerts = [a for a in alerts if a.hazard == "extreme_heat"]
            assert len(heat_alerts) == 1, (
                f"Cross-Source (GeoSphere+MeteoAlarm), gleiche Gefahr, minuetig "
                f"abweichende ECHTE Zeitraeume, muss weiterhin zu EINEM Eintrag "
                f"kollabieren (#1086), erhalten: {heat_alerts!r}"
            )
            assert heat_alerts[0].level == 3, "Hoechster Level (MeteoAlarm, 3) muss gewinnen"
            assert heat_alerts[0].source == "meteoalarm"
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup_sources)


class _MultiPeriodGeoSphereLikeSource:
    """Echte Test-Quelle (kein Mock): GeoSphere-artig, meldet MEHRERE
    Same-Source-Perioden derselben Gefahr an einem Punkt -- reproduziert den
    Adversary-F003-Fall (Greedy-Merge verschluckte eine dieser Perioden,
    sobald eine zweite Quelle fuer EINE der Perioden ebenfalls meldete)."""

    name = "geosphere_warn"

    def __init__(self, alerts: list[OfficialAlert]) -> None:
        self._alerts = alerts

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return list(self._alerts)


class _SingleAlertMeteoAlarmLikeSource:
    """Echte Test-Quelle (kein Mock): MeteoAlarm-artig, meldet EINEN Alert
    fuer dieselbe Gefahr wie eine der Perioden der GeoSphere-artigen Quelle
    (niedrigeres Level als die konkurrierende GeoSphere-Meldung)."""

    name = "meteoalarm"

    def __init__(self, alert: OfficialAlert) -> None:
        self._alert = alert

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [self._alert]


class TestF003PartitioningDoesNotSwallowSameSourcePeriod:
    """Adversary F003 (KRITISCH, Fix-Loop 2): der vorherige Greedy-Merge war
    nicht-transitiv und reihenfolgeabhaengig -- er konnte die Montag-Periode
    einer Same-Source-Mehrperioden-Quelle verschlucken, sobald eine ZWEITE
    Quelle fuer die Mittwoch-Periode derselben Gefahr meldete. Die Zwei-Pass-
    Quellen-Partitionierung schliesst das strukturell aus: Pass 1 bestimmt
    GLOBAL (nicht reihenfolgeabhaengig bei echtem Level-Unterschied) genau
    EINE beste Quelle je Gefahr, Pass 2 behaelt ALLE Perioden dieser einen
    Quelle -- keine Karte einer anderen Quelle kann sich dazwischenschieben."""

    @staticmethod
    def _build_alerts() -> tuple["OfficialAlert", "OfficialAlert", "OfficialAlert"]:
        hazard = "extreme_heat"
        mon_from = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
        mon_to = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)
        wed_from = datetime(2026, 7, 15, 4, 0, tzinfo=timezone.utc)
        wed_to = datetime(2026, 7, 15, 22, 0, tzinfo=timezone.utc)

        geo_mon = OfficialAlert(
            source="geosphere_warn", hazard=hazard, level=2,
            label="Hitze Montag", region_label="Villach",
            valid_from=mon_from, valid_to=mon_to,
        )
        geo_wed = OfficialAlert(
            source="geosphere_warn", hazard=hazard, level=4,
            label="Hitze Mittwoch", region_label="Villach",
            valid_from=wed_from, valid_to=wed_to,
        )
        meteoalarm_wed = OfficialAlert(
            source="meteoalarm", hazard=hazard, level=3,
            label="Hitzewarnung Mittwoch", region_label="Villach (Stadt)",
            valid_from=wed_from, valid_to=wed_to,
        )
        return geo_mon, geo_wed, meteoalarm_wed

    def _assert_expected_result(self, alerts: list["OfficialAlert"]) -> None:
        mon_from = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
        wed_from = datetime(2026, 7, 15, 4, 0, tzinfo=timezone.utc)

        heat_alerts = [a for a in alerts if a.hazard == "extreme_heat"]
        assert len(heat_alerts) == 2, (
            f"Erwartet GENAU 2 Eintraege (Montag GeoSphere level 2 + Mittwoch "
            f"GeoSphere level 4, KEINE doppelte Mittwoch-Karte), erhalten "
            f"{len(heat_alerts)}: {[(a.source, a.level, a.valid_from) for a in heat_alerts]}"
        )
        by_from = {a.valid_from: a for a in heat_alerts}
        assert mon_from in by_from, (
            f"Montag-Periode (GeoSphere, level 2) darf NICHT verschwinden -- "
            f"exakt der vom Adversary gefundene Greedy-Merge-Verlust, erhalten: "
            f"{[(a.source, a.level, a.valid_from) for a in heat_alerts]}"
        )
        assert by_from[mon_from].level == 2 and by_from[mon_from].source == "geosphere_warn"
        assert wed_from in by_from
        assert by_from[wed_from].level == 4, (
            "Mittwoch-Karte muss die GeoSphere-Meldung (level 4, beste Quelle) "
            f"sein, nicht MeteoAlarm (level 3), erhalten level={by_from[wed_from].level}"
        )
        assert by_from[wed_from].source == "geosphere_warn"

    def test_cross_source_does_not_swallow_same_source_period(self):
        """F003-Repro (jetzt gruener Nachweis): Produktions-Reihenfolge --
        GeoSphere-artige Quelle zuerst registriert (meldet Montag+Mittwoch),
        dann MeteoAlarm-artige Quelle (meldet nur Mittwoch, niedrigeres
        Level). Erwartung: genau 2 Eintraege, Montag bleibt erhalten, keine
        doppelte Mittwoch-Karte."""
        import services.official_alerts.base as oa_base
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        backup_sources = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            geo_mon, geo_wed, meteoalarm_wed = self._build_alerts()
            register_official_alert_source(_MultiPeriodGeoSphereLikeSource([geo_mon, geo_wed]))
            register_official_alert_source(_SingleAlertMeteoAlarmLikeSource(meteoalarm_wed))

            alerts = get_official_alerts_for_location(LAT, LON)
            self._assert_expected_result(alerts)
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup_sources)

    def test_cross_source_does_not_swallow_same_source_period_reversed_registration_order(self):
        """Determinismus: umgekehrte Registrierungsreihenfolge (MeteoAlarm-
        artige Quelle zuerst, dann GeoSphere-artige Quelle) liefert dasselbe
        Ergebnis -- die Partitionierung ist NICHT reihenfolgeabhaengig, im
        Gegensatz zum vorherigen Greedy-Merge (Adversary F003)."""
        import services.official_alerts.base as oa_base
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )

        backup_sources = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            geo_mon, geo_wed, meteoalarm_wed = self._build_alerts()
            register_official_alert_source(_SingleAlertMeteoAlarmLikeSource(meteoalarm_wed))
            register_official_alert_source(_MultiPeriodGeoSphereLikeSource([geo_mon, geo_wed]))

            alerts = get_official_alerts_for_location(LAT, LON)
            self._assert_expected_result(alerts)
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup_sources)
