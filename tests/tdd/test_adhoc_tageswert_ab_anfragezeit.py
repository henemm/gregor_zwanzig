"""
TDD RED — Ad-hoc-Abruf: der Tageswert fuer „heute" gilt AB dem Anfragezeitpunkt.

SPEC: docs/specs/modules/feat_2186_tagesaggregat_ab_jetzt.md v1.0 (Issue #2186)
Deckt AC-1, AC-2, AC-4, AC-5, AC-10, AC-11, AC-12.

Beweist aus Nutzersicht ueber den ECHTEN Befehlspfad
(``TripCommandProcessor.process()`` mit echtem Trip und echtem, auf Platte
persistiertem Snapshot — kein Mock), dass ein Abruf am Nachmittag den bereits
vergangenen Vormittag nicht mehr mitrechnet, waehrend „morgen" unberuehrt
bleibt.

Diese Tests MUESSEN initial fehlschlagen:
  * ``WeatherExtractor.timeline()`` kennt den Parameter ``from_time`` noch
    nicht, und ``_handle_query()`` reicht ``received_at`` nicht durch — der
    Nachmittags-Abruf liefert deshalb heute noch den Vormittagsregen.

Zahlenwahl: alle Niederschlagswerte sind binaer exakt darstellbar (5.0 und
0.25 mm/h), damit die Summen ohne Toleranz verglichen werden koennen.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.loader import save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from services.weather_snapshot import WeatherSnapshotService

HEUTE = date(2026, 2, 14)
MORGEN = date(2026, 2, 15)
TRIP_ID = "tour-2186-adhoc"
TRIP_NAME = "Tour 2186 Adhoc"

# London im Februar ist GMT — Ortszeit == UTC. Der Ortstag deckt sich damit
# mit dem UTC-Tag; AC-12 prueft den entfernten Fall separat.
LAT, LON = 51.5, -0.13

FRUEH_ABRUF = datetime(2026, 2, 14, 8, 0, tzinfo=timezone.utc)
SPAET_ABRUF = datetime(2026, 2, 14, 14, 0, tzinfo=timezone.utc)

# Vormittag: Dauerregen, Gewitterneigung, Sturm. Nachmittag: ruhig.
STUNDE_FRUEH = dict(
    t2m_c=5.0, wind10m_kmh=45.0, gust_kmh=70.0, precip_1h_mm=5.0, pop_pct=95,
    cape_jkg=1800.0, cloud_total_pct=95, cloud_low_pct=90,
    thunder_level=ThunderLevel.MED,
)
STUNDE_SPAET = dict(
    t2m_c=15.0, wind10m_kmh=8.0, gust_kmh=15.0, precip_1h_mm=0.25, pop_pct=20,
    cape_jkg=300.0, cloud_total_pct=35, cloud_low_pct=30,
)


# ---------------------------------------------------------------------------
# Aufbau — echter Trip, echter Snapshot auf Platte
# ---------------------------------------------------------------------------

def _waypoint(wp_id: str, lat: float = LAT, lon: float = LON) -> Waypoint:
    return Waypoint(id=wp_id, name=f"WP {wp_id}", lat=lat, lon=lon, elevation_m=120)


def _trip(lat: float = LAT, lon: float = LON) -> Trip:
    return Trip(
        id=TRIP_ID,
        name=TRIP_NAME,
        stages=[
            Stage(id="T1", name="Etappe heute", date=HEUTE,
                  waypoints=[_waypoint("W1", lat, lon)]),
            Stage(id="T2", name="Etappe morgen", date=MORGEN,
                  waypoints=[_waypoint("W2", lat, lon)]),
        ],
    )


def _punkte(start: datetime, anzahl: int, profil: dict) -> list[ForecastDataPoint]:
    from datetime import timedelta

    return [
        ForecastDataPoint(ts=start + timedelta(hours=i), **profil)
        for i in range(anzahl)
    ]


def _segment(
    segment_id: int,
    start: datetime,
    ende: datetime,
    *,
    aggregiert: SegmentWeatherSummary,
    stunden: list[ForecastDataPoint],
    lat: float = LAT,
    lon: float = LON,
) -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=100.0),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=180.0),
        start_time=start,
        end_time=ende,
        duration_hours=(ende - start).total_seconds() / 3600.0,
        distance_km=7.0,
        ascent_m=300.0,
        descent_m=250.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0,
            ),
            data=stunden,
        ),
        aggregated=aggregiert,
        fetched_at=datetime(2026, 2, 14, 5, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _utc(tag: date, stunde: int) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, 0, tzinfo=timezone.utc)


def _segmente_london() -> list[SegmentWeatherData]:
    """Zwei Etappen heute (Vormittag nass, Nachmittag ruhig) + eine morgen.

    Die gespeicherten Aggregate entsprechen dem VOLLEN Segmentfenster — genau
    das, was der Snapshot heute enthaelt und was ein Abruf am Nachmittag
    bislang unveraendert weiterreicht.
    """
    vormittag = _segment(
        1, _utc(HEUTE, 6), _utc(HEUTE, 10),
        aggregiert=SegmentWeatherSummary(
            temp_min_c=5.0, temp_max_c=5.0, wind_max_kmh=45.0, gust_max_kmh=70.0,
            precip_sum_mm=20.0, pop_max_pct=95, cape_max_jkg=1800.0,
            thunder_level_max=ThunderLevel.MED,
        ),
        stunden=_punkte(_utc(HEUTE, 6), 4, STUNDE_FRUEH),
    )
    nachmittag = _segment(
        2, _utc(HEUTE, 10), _utc(HEUTE, 16),
        aggregiert=SegmentWeatherSummary(
            temp_min_c=15.0, temp_max_c=15.0, wind_max_kmh=8.0, gust_max_kmh=15.0,
            precip_sum_mm=1.5, pop_max_pct=20, cape_max_jkg=300.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        stunden=_punkte(_utc(HEUTE, 10), 6, STUNDE_SPAET),
    )
    morgen = _segment(
        3, _utc(MORGEN, 8), _utc(MORGEN, 12),
        aggregiert=SegmentWeatherSummary(
            temp_min_c=9.0, temp_max_c=12.0, wind_max_kmh=18.0, gust_max_kmh=30.0,
            precip_sum_mm=3.0, pop_max_pct=60, cape_max_jkg=500.0,
            thunder_level_max=ThunderLevel.LOW,
        ),
        stunden=_punkte(_utc(MORGEN, 8), 4, STUNDE_SPAET),
    )
    return [vormittag, nachmittag, morgen]


@pytest.fixture
def umgebung(tmp_path: Path, monkeypatch) -> Path:
    """Lenkt das Datenverzeichnis auf tmp_path — echte Datei-I/O, kein Mock."""
    def _ziel(user_id: str = "default") -> Path:
        return tmp_path / user_id

    monkeypatch.setattr("app.loader.get_data_dir", _ziel)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", _ziel)
    return tmp_path


def _lege_an(trip: Trip, segmente: list[SegmentWeatherData]) -> None:
    save_trip(trip, "default")
    WeatherSnapshotService("default").save(trip.id, segmente, HEUTE)


def _abruf(body: str, received_at: datetime, *, channel: str = "telegram") -> CommandResult:
    return TripCommandProcessor().process(InboundMessage(
        trip_name=TRIP_NAME, body=body, sender="123",
        channel=channel, received_at=received_at, user_id="default",
    ))


def _tagesaggregat(received_at: datetime, tag: date, *, trip: Trip | None = None) -> dict | None:
    """Das Tages-Aggregat, wie es der Abruf zu ``received_at`` bilden wuerde.

    Geht ueber DIESELBE Kette wie ``_handle_query``: gefensterte Timeline ->
    ``_aggregate_day``. ``_aggregate_day`` ist eine der fuenf Ausgabestellen
    aus AC-10 und wird hier direkt an ihrem Ergebnis gemessen.
    """
    from services.trip_day import display_tz
    from services.weather_extractor import WeatherExtractor

    trip = trip or _trip()
    timeline = WeatherExtractor(user_id="default").timeline(
        TRIP_ID, from_time=received_at,
    )
    return TripCommandProcessor()._aggregate_day(timeline, tag, display_tz(trip, tag))


# ---------------------------------------------------------------------------
# AC-1 / AC-4 / AC-5 — die Fensterung selbst
# ---------------------------------------------------------------------------

class TestTageswertAbAnfragezeit:
    def test_ac1_nachmittags_abruf_zeigt_den_vormittagsregen_nicht_mehr(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN einen Vormittag mit 20 mm Regen und einen ruhigen Nachmittag,
        WHEN ``glance`` um 14:00 abgerufen wird,
        THEN enthaelt der Tageswert fuer „heute" den Vormittagsregen nicht mehr
             — nur noch die 0,5 mm der beiden verbleibenden Stunden.
        """
        _lege_an(_trip(), _segmente_london())

        agg = _tagesaggregat(SPAET_ABRUF, HEUTE)

        assert agg is not None
        assert agg["precip"] == 0.5, (
            f"Tageswert traegt noch vergangene Stunden: {agg['precip']}"
        )
        assert agg["precip"] != 21.5, "der volle Tag wurde unveraendert durchgereicht"

    def test_ac4_teilweise_vergangenes_segment_wird_beschnitten_neu_gerechnet(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN das Nachmittags-Segment 10-16 Uhr, das um 14:00 zur Haelfte
              vergangen ist,
        WHEN die Tages-Aggregation laeuft,
        THEN traegt es die Werte des Fensters [14:00, 16:00) — 0,5 mm statt
             der gespeicherten 1,5 mm ueber das volle Segment.
        """
        _lege_an(_trip(), _segmente_london())
        from services.weather_extractor import WeatherExtractor

        timeline = WeatherExtractor(user_id="default").timeline(
            TRIP_ID, from_time=SPAET_ABRUF,
        )

        heute_punkte = [p for p in timeline.points if p.arrival_time.date() == HEUTE]
        assert len(heute_punkte) == 1, (
            f"erwartet: nur das laufende Segment, bekommen: "
            f"{[p.label for p in heute_punkte]}"
        )
        assert heute_punkte[0].metrics.precip_sum_mm == 0.5

    def test_ac5_vollstaendig_vergangenes_segment_verschwindet_aus_den_wegpunkten(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN das Vormittags-Segment 06-10 Uhr, das um 14:00 vollstaendig
              vergangen ist,
        WHEN die Wegpunkte fuer „heute" gebildet werden,
        THEN erscheint dieses Segment nicht mehr — waehrend es beim frueheren
             Abruf um 08:00 noch da war.
        """
        _lege_an(_trip(), _segmente_london())
        from services.weather_extractor import WeatherExtractor

        extractor = WeatherExtractor(user_id="default")
        frueh = extractor.timeline(TRIP_ID, from_time=FRUEH_ABRUF)
        spaet = extractor.timeline(TRIP_ID, from_time=SPAET_ABRUF)

        assert "1" in [str(p.label) for p in frueh.points], (
            "das Vormittags-Segment fehlte schon beim fruehen Abruf"
        )
        assert "1" not in [str(p.label) for p in spaet.points], (
            "das vollstaendig vergangene Segment steht noch in den Wegpunkten"
        )


# ---------------------------------------------------------------------------
# AC-2 — „morgen" bleibt unberuehrt
# ---------------------------------------------------------------------------

class TestMorgenBleibtUnberuehrt:
    def test_ac2_morgen_ist_bei_frueh_und_spaet_abruf_wertgleich(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN zwei Abrufe am selben Tag (08:00 und 14:00),
        WHEN beide die Zeile „morgen" lesen,
        THEN sind die Werte fuer „morgen" wertgleich — „ab jetzt" veraendert
             den Folgetag nicht.
        """
        _lege_an(_trip(), _segmente_london())

        morgen_frueh = _tagesaggregat(FRUEH_ABRUF, MORGEN)
        morgen_spaet = _tagesaggregat(SPAET_ABRUF, MORGEN)

        assert morgen_frueh is not None and morgen_spaet is not None
        assert morgen_frueh == morgen_spaet, (
            "die Fensterung hat den Folgetag veraendert"
        )
        # Gegenprobe: fuer HEUTE unterscheiden sich dieselben beiden Abrufe —
        # sonst wuerde die Gleichheit oben auch eine wirkungslose Fensterung
        # bestehen.
        assert _tagesaggregat(FRUEH_ABRUF, HEUTE) != _tagesaggregat(SPAET_ABRUF, HEUTE)

    def test_ac2_morgen_zeile_im_glance_body_ist_bei_beiden_abrufen_gleich(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN zwei ``glance``-Abrufe zu unterschiedlichen Uhrzeiten,
        WHEN die ausgegebenen Bodies verglichen werden,
        THEN ist die „morgen"-Zeile identisch, die „heute"-Zeile aber nicht.
        """
        _lege_an(_trip(), _segmente_london())

        frueh = _abruf("### query: glance", FRUEH_ABRUF).confirmation_body
        spaet = _abruf("### query: glance", SPAET_ABRUF).confirmation_body

        def _zeile(body: str, marker: str) -> str:
            # Nur die DATENzeile, die mit dem Tageswort beginnt — die
            # Kopfzeile „🗓 Glance — heute & morgen" enthaelt beide Woerter
            # und wuerde einen Vergleich sonst gegen sich selbst fuehren.
            treffer = [z for z in body.splitlines() if z.lower().startswith(marker)]
            assert treffer, f"Datenzeile fuer {marker!r} fehlt in: {body!r}"
            return treffer[0]

        assert _zeile(frueh, "morgen") == _zeile(spaet, "morgen")
        assert _zeile(frueh, "heute") != _zeile(spaet, "heute")


# ---------------------------------------------------------------------------
# AC-10 — alle fuenf Ausgabestellen
# ---------------------------------------------------------------------------

class TestAlleAusgabestellenSindGefenstert:
    def test_ac10_aggregate_day_traegt_nur_das_restfenster(self, umgebung: Path) -> None:
        """_aggregate_day (1/5): der Tageswert selbst."""
        _lege_an(_trip(), _segmente_london())

        agg = _tagesaggregat(SPAET_ABRUF, HEUTE)

        assert agg["precip"] == 0.5
        assert agg["pop"] == 20
        assert agg["wind_max"] == 8.0
        assert agg["thunder"] == ThunderLevel.NONE, (
            "die Gewitterstufe des Vormittags steht noch im Tageswert"
        )

    def test_ac10_glance_meldet_am_nachmittag_nicht_mehr_den_vormittag(
        self, umgebung: Path,
    ) -> None:
        """_fmt_glance (2/5)."""
        _lege_an(_trip(), _segmente_london())

        frueh = _abruf("### query: glance", FRUEH_ABRUF).confirmation_body
        spaet = _abruf("### query: glance", SPAET_ABRUF).confirmation_body

        assert frueh != spaet, "glance zeigt am Nachmittag unveraendert den Vormittag"

    def test_ac10_gewitter_ausgabe_verliert_die_vergangene_stufe(
        self, umgebung: Path,
    ) -> None:
        """_fmt_gewitter (3/5): die MED-Stufe lag ausschliesslich am Vormittag."""
        _lege_an(_trip(), _segmente_london())

        frueh = _abruf("### query: heute_gewitter", FRUEH_ABRUF).confirmation_body
        spaet = _abruf("### query: heute_gewitter", SPAET_ABRUF).confirmation_body

        assert frueh != spaet, (
            "die Gewitter-Ausgabe meldet am Nachmittag noch die Vormittagsstufe"
        )

    def test_ac10_timeline_zeigt_nur_noch_die_verbleibenden_wegpunkte(
        self, umgebung: Path,
    ) -> None:
        """_fmt_timeline (4/5)."""
        _lege_an(_trip(), _segmente_london())

        frueh = _abruf("### query: timeline_heute", FRUEH_ABRUF).confirmation_body
        spaet = _abruf("### query: timeline_heute", SPAET_ABRUF).confirmation_body

        assert len(spaet.splitlines()) < len(frueh.splitlines()), (
            "die Timeline listet den vergangenen Wegpunkt noch mit"
        )

    def test_ac10_drilldown_buttons_folgen_dem_restfenster(self, umgebung: Path) -> None:
        """_timeline_buttons (5/5).

        Am Vormittag ueberschreiten Gewitter (MED), Wind (45 km/h) und
        Niederschlag (1,5 mm) ihre Schwellen; im Restfenster ab 14:00 keiner
        davon. Bleiben die Buttons stehen, ist die Fensterung an dieser
        Ausgabestelle nicht angekommen.
        """
        _lege_an(_trip(), _segmente_london())

        frueh = _abruf("### query: timeline_heute", FRUEH_ABRUF).reply_markup
        spaet = _abruf("### query: timeline_heute", SPAET_ABRUF).reply_markup

        def _drilldowns(markup) -> list[str]:
            return [
                b["text"]
                for reihe in markup["inline_keyboard"]
                for b in reihe
                if str(b.get("callback_data", "")).startswith("dd_")
            ]

        assert _drilldowns(frueh), "am Vormittag fehlen die Drilldown-Buttons"
        assert _drilldowns(spaet) == [], (
            f"Drilldown-Buttons ueberdauern das Restfenster: {_drilldowns(spaet)}"
        )


# ---------------------------------------------------------------------------
# AC-11 — Telegram- und E-Mail-Freitext wirken gleich
# ---------------------------------------------------------------------------

class TestKanalparitaet:
    @pytest.mark.parametrize("freitext", ["glance", "gewitter"])
    def test_ac11_bare_keyword_wirkt_in_telegram_und_email_identisch(
        self, umgebung: Path, freitext: str,
    ) -> None:
        """
        GIVEN denselben Freitext-Befehl ueber ``_BARE_KEYWORD_MAP``,
        WHEN er zum selben Zeitpunkt per Telegram und per E-Mail eintrifft,
        THEN ist die Fensterung in beiden Kanaelen identisch wirksam.
        """
        _lege_an(_trip(), _segmente_london())

        per_telegram = _abruf(freitext, SPAET_ABRUF, channel="telegram")
        per_email = _abruf(freitext, SPAET_ABRUF, channel="email")

        assert per_telegram.success and per_email.success
        assert per_telegram.confirmation_body == per_email.confirmation_body

        # Und beide sind tatsaechlich gefenstert, nicht nur gleich falsch.
        frueh = _abruf(freitext, FRUEH_ABRUF, channel="telegram").confirmation_body
        assert per_telegram.confirmation_body != frueh, (
            f"{freitext!r} zeigt am Nachmittag unveraendert den Vormittag"
        )


# ---------------------------------------------------------------------------
# AC-12 — entfernte Ortszeitzone
# ---------------------------------------------------------------------------

class TestEntfernteZeitzone:
    """Neuseeland (UTC+13 im Februar): der Ortstag 14.02. laeuft von
    13.02. 11:00 UTC bis 14.02. 11:00 UTC. Ein Schnitt, der am UTC-Tag statt
    am Ortstag ansetzt, wuerde hier in den falschen Tag greifen."""

    NZ_LAT, NZ_LON = -41.29, 174.78
    # Ortszeit 14.02. 15:00 == 14.02. 02:00 UTC
    ABRUF_NZ = datetime(2026, 2, 14, 2, 0, tzinfo=timezone.utc)

    def _segmente_nz(self) -> list[SegmentWeatherData]:
        vormittag = _segment(  # Ortszeit 14.02. 08:00-12:00
            1, datetime(2026, 2, 13, 19, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 13, 23, 0, tzinfo=timezone.utc),
            aggregiert=SegmentWeatherSummary(
                temp_min_c=5.0, temp_max_c=5.0, wind_max_kmh=45.0,
                precip_sum_mm=20.0, pop_max_pct=95,
                thunder_level_max=ThunderLevel.MED,
            ),
            stunden=_punkte(
                datetime(2026, 2, 13, 19, 0, tzinfo=timezone.utc), 4, STUNDE_FRUEH,
            ),
            lat=self.NZ_LAT, lon=self.NZ_LON,
        )
        nachmittag = _segment(  # Ortszeit 14.02. 13:00-17:00
            2, datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 14, 4, 0, tzinfo=timezone.utc),
            aggregiert=SegmentWeatherSummary(
                temp_min_c=15.0, temp_max_c=15.0, wind_max_kmh=8.0,
                precip_sum_mm=1.0, pop_max_pct=20,
                thunder_level_max=ThunderLevel.NONE,
            ),
            stunden=_punkte(
                datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc), 4, STUNDE_SPAET,
            ),
            lat=self.NZ_LAT, lon=self.NZ_LON,
        )
        return [vormittag, nachmittag]

    def test_ac12_fensterung_schneidet_nicht_in_den_falschen_ortstag(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN eine Tour in Neuseeland und einen Abruf um 15:00 Ortszeit,
        WHEN die Tages-Aggregation laeuft,
        THEN bleibt die Zuordnung „heute" auf dem Ortstag 14.02., das
             vollstaendig vergangene Vormittags-Segment entfaellt, und der
             verbleibende Wegpunkt rutscht in keinen Nachbartag.
        """
        trip = _trip(self.NZ_LAT, self.NZ_LON)
        _lege_an(trip, self._segmente_nz())

        agg = _tagesaggregat(self.ABRUF_NZ, HEUTE, trip=trip)

        assert agg is not None, "der Ortstag 14.02. hat gar keine Wegpunkte mehr"
        assert agg["precip"] == 0.5, (
            f"Restfenster falsch geschnitten: {agg['precip']}"
        )
        assert agg["thunder"] == ThunderLevel.NONE, (
            "der vergangene Vormittag traegt die Gewitterstufe noch bei"
        )

        # Kein Wegpunkt darf in einen Nachbartag gerutscht sein.
        from services.trip_day import display_tz
        from services.weather_extractor import WeatherExtractor

        timeline = WeatherExtractor(user_id="default").timeline(
            TRIP_ID, from_time=self.ABRUF_NZ,
        )
        tz = display_tz(trip, HEUTE)
        ortstage = {p.arrival_time.astimezone(tz).date() for p in timeline.points}
        assert ortstage == {HEUTE}, f"Wegpunkte in fremden Ortstagen: {ortstage}"


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-10 am ZWEITEN Datenweg — der datierte Rueckfall
#
# Der undatierte Anker ``{trip_id}.json`` traegt strukturell nur EINEN Tag
# (``_write_briefing_anchor`` ueberschreibt ihn je Briefing-Lauf). Fuer den
# fehlenden Tag zieht ``_mit_datiertem_rueckfall`` den datierten Snapshot
# ``{trip_id}_{YYYY-MM-DD}.json``. Eine Fensterung, die nur am Anker greift,
# zeigt nach dem Abend-Briefing wieder den Vormittag — dieselbe Frage,
# dieselbe Uhrzeit, anderer Wert, je nachdem welche Datei gerade traegt.
# ---------------------------------------------------------------------------

def _datenzeile(body: str, marker: str) -> str:
    """Die DATENzeile eines Glance-Bodies, die mit dem Tageswort beginnt.

    Die Kopfzeile „🗓 Glance — heute & morgen" enthaelt beide Woerter und
    wuerde einen Vergleich sonst gegen sich selbst fuehren.
    """
    treffer = [z for z in body.splitlines() if z.lower().startswith(marker)]
    assert treffer, f"Datenzeile fuer {marker!r} fehlt in: {body!r}"
    return treffer[0]


def _lege_datiert_an(tag: date, segmente: list[SegmentWeatherData]) -> None:
    WeatherSnapshotService("default").save_dated(TRIP_ID, tag, segmente)


class TestDatierterRueckfallIstEbenfallsGefenstert:
    def test_ac1_rueckfall_auf_den_datierten_snapshot_zeigt_den_vormittag_nicht_mehr(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN einen undatierten Anker, der fuer „heute" NICHTS traegt (Lage
              nach dem Abend-Briefing), und einen datierten Snapshot fuer
              heute mit nassem Vormittag und ruhigem Nachmittag,
        WHEN ``glance`` um 14:00 abgerufen wird,
        THEN ist die „heute"-Zeile dieselbe wie ueber den Anker-Weg — die
             Fensterung haengt an der FRAGE, nicht an der Quelle.
        """
        vormittag, nachmittag, morgen = _segmente_london()

        # 1. Rueckfall-Weg: Anker traegt nur morgen, heute kommt datiert.
        _lege_an(_trip(), [morgen])
        _lege_datiert_an(HEUTE, [vormittag, nachmittag])
        ueber_rueckfall = _abruf("### query: glance", SPAET_ABRUF).confirmation_body

        # 2. Anker-Weg: derselbe Bestand, aber im undatierten Anker. Dessen
        #    Fensterung ist durch AC-1 bereits bewiesen — er ist hier der
        #    Massstab, kein zweiter Pruefling.
        _lege_an(_trip(), [vormittag, nachmittag, morgen])
        ueber_anker = _abruf("### query: glance", SPAET_ABRUF).confirmation_body

        assert _datenzeile(ueber_rueckfall, "heute") == _datenzeile(ueber_anker, "heute"), (
            "der datierte Rueckfall liefert einen anderen Tageswert als der "
            "Anker — die Fensterung greift nur an einer der beiden Quellen"
        )

    def test_ac10_rueckfall_am_nachmittag_unterscheidet_sich_vom_vormittag(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN denselben datierten Rueckfall fuer „heute",
        WHEN ``glance`` einmal um 08:00 und einmal um 14:00 abgerufen wird,
        THEN unterscheidet sich die „heute"-Zeile — sonst ist die Fensterung
             auf diesem Weg wirkungslos und die Gleichheit oben nur „beide
             gleich falsch".
        """
        vormittag, nachmittag, morgen = _segmente_london()
        _lege_an(_trip(), [morgen])
        _lege_datiert_an(HEUTE, [vormittag, nachmittag])

        frueh = _abruf("### query: glance", FRUEH_ABRUF).confirmation_body
        spaet = _abruf("### query: glance", SPAET_ABRUF).confirmation_body

        assert _datenzeile(frueh, "heute") != _datenzeile(spaet, "heute"), (
            "der datierte Rueckfall zeigt am Nachmittag unveraendert den Vormittag"
        )

    def test_ac2_morgen_aus_dem_datierten_rueckfall_bleibt_wertgleich(
        self, umgebung: Path,
    ) -> None:
        """
        GIVEN einen Anker, der nur „heute" traegt (Lage nach dem
              Morgen-Briefing), und „morgen" aus dem datierten Snapshot,
        WHEN zu zwei Uhrzeiten desselben Tages abgerufen wird,
        THEN ist die „morgen"-Zeile wertgleich — der Zweig „Anfragezeit vor
             Segmentstart" haelt auch auf diesem Weg.
        """
        vormittag, nachmittag, morgen = _segmente_london()
        _lege_an(_trip(), [vormittag, nachmittag])
        _lege_datiert_an(MORGEN, [morgen])

        frueh = _abruf("### query: glance", FRUEH_ABRUF).confirmation_body
        spaet = _abruf("### query: glance", SPAET_ABRUF).confirmation_body

        assert _datenzeile(frueh, "morgen") == _datenzeile(spaet, "morgen"), (
            "die Fensterung hat den Folgetag ueber den datierten Rueckfall veraendert"
        )
        # Gegenprobe: „heute" unterscheidet sich sehr wohl — sonst bestuende
        # die Gleichheit oben auch bei einer voellig wirkungslosen Fensterung.
        assert _datenzeile(frueh, "heute") != _datenzeile(spaet, "heute")
