"""TDD RED — Issue #1348-Rest: Briefing-Hinweis "amtliche Warnungen nicht abrufbar".

SPEC: docs/specs/modules/warn_unavailable_hint.md (AC-1 … AC-6)
SPEC: docs/specs/modules/fix_1348_warn_kompensation.md (AC-1 … AC-7, Klasse TestUnavailableSignal)

Diese Tests schlagen JETZT absichtlich fehl — das Feature existiert noch nicht:
- `services.official_alerts.base.get_official_alerts_with_status` -> AttributeError
- Renderer-Helfer `any_official_alerts_unavailable` /
  `render_official_alerts_unavailable_html` /
  `render_official_alerts_unavailable_plain` -> ImportError
- Feld `SegmentWeatherData.official_alerts_unavailable` -> im Renderer kein Hinweis

KEIN Mock-Theater (Projektkonvention): die Test-Quellen sind echte Python-Objekte,
die das `OfficialAlertSource`-Protocol strukturell erfuellen und ueber die echte
Registry (`_REGISTERED_SOURCES`, per backup/clear/restore isoliert) im echten
Codepfad laufen. Kein `Mock()`/`patch()`/`MagicMock`. Kein Live-Netz — die
`fetch()`-Methoden werfen bzw. liefern `[]` kontrolliert.

Vorbild-Muster: tests/tdd/test_issue_1034_official_alerts_foundation.py.

PO-Entscheid 2026-07-30 (loest die STRENGE Regel vom 2026-07-23 ab, Issue
#1348 Restpunkt): `unavailable = (es gibt abdeckende Quellen) AND (ALLE
davon sind beim Fetch fehlgeschlagen)`. Kompensation durch eine andere
erfolgreiche, ebenfalls zustaendige Quelle zaehlt -- ein Sicherheitshinweis,
der auch ohne echte Luecke erscheint, wird ueberlesen (Beleg: Trip "KHW 403",
30.07., GeoSphere lieferte durchgehend erfolgreich, nur MeteoAlarm war
gesperrt, der Hinweis erschien trotzdem). Bei GENAU EINER zustaendigen
Quelle bleibt das Verhalten unveraendert streng (`failed >= covering` ist
dort aequivalent zu `failed >= 1`). Der Mischfall-Test unten ist der Kern
dieser Entscheidung.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Echte Test-Quellen (kein Mock) — erfuellen OfficialAlertSource strukturell.
# ---------------------------------------------------------------------------

class _AllCoveringFailSource:
    """covers=True, fetch() wirft -> eine deckende Quelle ist ausgefallen."""

    @property
    def name(self) -> str:
        return "test-covering-fail"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        raise RuntimeError("simulierter Ausfall der amtlichen Quelle")


class _SuccessEmptySource:
    """covers=True, fetch() liefert erfolgreich [] -> kein Ausfall."""

    @property
    def name(self) -> str:
        return "test-covering-empty"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        return []


class _NonCoveringSource:
    """covers=False -> die Quelle ist fuer den Ort gar nicht zustaendig.

    fetch() WUERDE werfen, darf aber nie aufgerufen werden (keine Coverage ->
    kein Fehlalarm)."""

    @property
    def name(self) -> str:
        return "test-non-covering"

    def covers(self, lat: float, lon: float) -> bool:
        return False

    def fetch(self, lat: float, lon: float):
        raise RuntimeError("darf nie aufgerufen werden")


class _SingleLocationSuccessSource:
    """covers=True, liefert genau einen echten OfficialAlert (Rueckwaertskompat)."""

    def __init__(self, alert) -> None:
        self._alert = alert

    @property
    def name(self) -> str:
        return "test-single-location-success"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        return [self._alert]


# Ort irgendwo — die Test-Quellen ignorieren die Koordinaten (bzw. antworten
# konstant), ein Live-Netzruf findet nicht statt.
_LAT, _LON = 43.7102, 7.2620


# ---------------------------------------------------------------------------
# Signal-Ebene: services.official_alerts.base.get_official_alerts_with_status
# ---------------------------------------------------------------------------

class TestUnavailableSignal:
    """Der Status `unavailable` je nach Quellen-Lage (STRENGE PO-Regel)."""

    def test_all_covering_fail_is_unavailable(self):
        """Eine deckende Quelle wirft beim Fetch -> unavailable=True."""
        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            oa_base._REGISTERED_SOURCES.append(_AllCoveringFailSource())
            alerts, unavailable = get_official_alerts_with_status(_LAT, _LON)
            assert alerts == [], f"Werfende Quelle darf keine Alerts liefern, war {alerts!r}"
            assert unavailable is True, (
                "Eine deckende, beim Fetch ausgefallene Quelle MUSS unavailable=True "
                "ergeben (fail-soft [] darf nicht als 'alles ruhig' durchgehen)."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_success_empty_is_available(self):
        """Deckende Quelle liefert erfolgreich [] -> unavailable=False."""
        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            oa_base._REGISTERED_SOURCES.append(_SuccessEmptySource())
            alerts, unavailable = get_official_alerts_with_status(_LAT, _LON)
            assert alerts == []
            assert unavailable is False, (
                "Ein erfolgreiches leeres Ergebnis ist 'keine Warnungen, alles "
                "ruhig' -> unavailable=False."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_non_covering_is_available(self):
        """Keine deckende Quelle -> unavailable=False (kein Fehlalarm ohne Coverage)."""
        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            oa_base._REGISTERED_SOURCES.append(_NonCoveringSource())
            alerts, unavailable = get_official_alerts_with_status(_LAT, _LON)
            assert alerts == []
            assert unavailable is False, (
                "Ohne deckende Quelle (covers=False) darf kein Nicht-abrufbar-"
                "Hinweis entstehen (AC-4)."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_mischfall_kompensiert_one_fail_one_success_is_available(self):
        """KERN DER PO-KORREKTUR (2026-07-30): eine deckende Quelle wirft, eine
        andere deckende Quelle liefert erfolgreich [] -> unavailable=False.

        Die erfolgreiche zustaendige Quelle KOMPENSIERT die ausgefallene --
        genau der am 30.07. gemeldete Fehlalarm-Fall (GeoSphere ok, nur
        MeteoAlarm gesperrt, Hinweis erschien trotzdem faelschlich). Die
        fruehere STRENGE Variante ("eine ausgefallene Quelle genuegt") ist
        damit abgeloest; dieser Test war vor der Korrektur GRUEN mit
        `unavailable is True` und wird durch den Formel-Fix (`failed >=
        covering` statt `failed >= 1`) auf `unavailable is False` umgedreht.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            oa_base._REGISTERED_SOURCES.append(_AllCoveringFailSource())
            oa_base._REGISTERED_SOURCES.append(_SuccessEmptySource())
            alerts, unavailable = get_official_alerts_with_status(_LAT, _LON)
            assert alerts == [], (
                f"Nur die (werfende) Fail-Quelle deckt ab; die Empty-Quelle liefert "
                f"[] -> Gesamt-Alertliste leer, war {alerts!r}"
            )
            assert unavailable is False, (
                "PO-Entscheid 2026-07-30: eine erfolgreiche zustaendige Quelle "
                "kompensiert eine ausgefallene zustaendige Quelle am selben Ort "
                "-> unavailable=False, kein Fehlalarm mehr."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_beide_covering_quellen_fallen_aus_is_unavailable(self):
        """AC-2: zwei zustaendige Quellen, BEIDE fallen beim Fetch aus ->
        unavailable=True. Keine Kompensation moeglich, wenn nichts uebrig
        bleibt, das kompensieren koennte -- Gegenprobe zu AC-1, damit die
        Formel nicht versehentlich auf 'irgendeine Quelle deckt ab' entartet."""
        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status

        class _SecondCoveringFailSource:
            @property
            def name(self) -> str:
                return "test-covering-fail-2"

            def covers(self, lat: float, lon: float) -> bool:
                return True

            def fetch(self, lat: float, lon: float):
                raise RuntimeError("zweite simulierte Quelle faellt ebenfalls aus")

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            oa_base._REGISTERED_SOURCES.append(_AllCoveringFailSource())
            oa_base._REGISTERED_SOURCES.append(_SecondCoveringFailSource())
            alerts, unavailable = get_official_alerts_with_status(_LAT, _LON)
            assert alerts == []
            assert unavailable is True, (
                "Fallen ALLE zustaendigen Quellen aus, bleibt kein Kompensations-"
                "Partner uebrig -> unavailable=True bleibt bestehen."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_realpath_at_geosphere_erfolg_kompensiert_meteoalarm_blockiert(self):
        """AC-5 REAL-PFAD (PO-Vorfall 30.07., Trip "KHW 403"): die HEUTE in
        Prod registrierten AT-Quellen `GeoSphereWarnSource` (erfolgreich,
        via genuinem Cache-Treffer -- kein Live-Netz) und
        `MeteoAlarmFeedSource("AT")` (real geblockt, `feeds.meteoalarm.org`
        steht im Egress-Waechter auf BLOCKED) fuer einen oesterreichischen
        Punkt -> unavailable=False. Genau der Fehlalarm, den die PO-Korrektur
        beheben sollte, jetzt mit den ECHTEN Quellklassen nachgestellt.

        Kein Mock-Theater, kein Live-Netz: `GeoSphereWarnSource` bekommt einen
        echten, aber MANUELL VORGEFUELLTEN Cache-Treffer (identisches Muster
        zu `tests/tdd/test_warn_services_rest.py::test_cache_hit_kein_call`)
        -- ihr `fetch()` laeuft dadurch ueber den echten Cache-Hit-Zweig von
        `warn_egress.cached_fetch()`, ohne jemals `request_fn()` aufzurufen.
        `MeteoAlarmFeedSource("AT")` faellt ueber den bereits bestehenden,
        real geblockten Host aus (identischer Mechanismus wie im
        Regressionswaechter oben)."""
        import time as time_module

        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status
        from services.official_alerts.geosphere_warn import (
            GeoSphereWarnSource, _cache as _geosphere_cache, _round_coord,
            CACHE_TTL as _GEOSPHERE_CACHE_TTL,
        )
        from services.official_alerts.meteoalarm_feed import (
            MeteoAlarmFeedSource, _cache as _meteoalarm_feed_cache,
        )

        # Innsbruck -- in der GeoSphere-/INCA-Bbox (covers=True fuer beide Quellen).
        at_lat, at_lon = 47.26, 11.39

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        _geosphere_cache.clear()
        _meteoalarm_feed_cache.clear()
        try:
            geosphere = GeoSphereWarnSource()
            meteoalarm_at = MeteoAlarmFeedSource("AT")
            assert geosphere.covers(at_lat, at_lon) is True
            assert meteoalarm_at.covers(at_lat, at_lon) is True

            # Echter Cache-Treffer: GeoSphere "hat gerade erfolgreich leer
            # geantwortet" -- keine Warnungen fuer Innsbruck, ohne Netz.
            # WICHTIG: ``gemeindenr`` MUSS gesetzt sein (formgueltig, laut
            # ``_ist_auswertbare_gemeindenr``) -- ``_zone_for_point_at()``
            # liest dasselbe GeoSphere-Cache-Objekt weiter, um die AT-EMMA-
            # Zone aufzuloesen. OHNE ``gemeindenr`` waere die Zone ``None``
            # ("nicht zustaendig", Fall 1) und ``MeteoAlarmFeedSource("AT")``
            # wuerde ``_get_cached_feed("AT")`` NIE aufrufen -- der geblockte
            # Host bliebe unerreicht, der Test wuerde faelschlich SCHON VOR
            # dem Fix gruen sein (genau dieser Fehler flog beim ersten
            # Testlauf auf: 0 statt 1 ausgefallene Quelle).
            _geosphere_cache[_round_coord(at_lat, at_lon)] = {
                "data": {
                    "properties": {
                        "location": {
                            "properties": {
                                "name": "Innsbruck (Test)",
                                "gemeindenr": "70101",
                            }
                        },
                        "warnings": [],
                    }
                },
                "fetched_at": time_module.monotonic(),
                "ttl": _GEOSPHERE_CACHE_TTL,
            }

            oa_base._REGISTERED_SOURCES.append(geosphere)
            oa_base._REGISTERED_SOURCES.append(meteoalarm_at)

            alerts, unavailable = get_official_alerts_with_status(at_lat, at_lon)
            assert alerts == [], (
                f"Beide Quellen liefern keine aktiven Warnungen, war {alerts!r}"
            )
            assert unavailable is False, (
                "GeoSphere liefert erfolgreich (auch leer), MeteoAlarm ist "
                "geblockt -> die erfolgreiche Quelle kompensiert -> "
                "unavailable=False. Der 30.07.-Fehlalarm ist damit behoben."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _geosphere_cache.clear()
            _meteoalarm_feed_cache.clear()

    def test_realpath_suedtirol_dpc_erfolg_kompensiert_meteoalarm_blockiert(self):
        """AC-6 REAL-PFAD (reale heutige Quellenlage, PO-Entscheid 2026-08-09):
        das im urspruenglichen PO-Kommentar (30.07.) genannte Beispiel
        "fuer Suedtirol ist MeteoAlarm die einzige Quelle" ist seit
        `DpcSource` (2026-07-31, #1427 S2) ueberholt -- ein Suedtirol-Punkt
        wird HEUTE von ZWEI Quellen abgedeckt: `MeteoAlarmFeedSource("IT")`
        und `DpcSource`. Faellt nur MeteoAlarm aus (real geblockter Host),
        kompensiert DpcSource -> unavailable=False.

        Kein Mock-Theater, kein Live-Netz: der DPC-Zonencode fuer den
        Testpunkt wird ueber die ECHTE Zonen-Geometrie (`_zone_at`)
        ermittelt (kein geratener/hartkodierter Code), der Bulletin-Cache
        wird mit einem minimalen, aber vollstaendig REALISTISCH GEFORMTEN
        "NESSUNA ALLERTA"-Datensatz fuer genau diese Zone vorgefuellt
        (identisches Zeilenformat wie `tests/fixtures/dpc`-Fixtures) --
        `DpcSource.fetch()` laeuft dadurch ueber den echten Cache-Hit-Zweig,
        ohne Netz. `MeteoAlarmFeedSource("IT")` faellt ueber den bereits
        bestehenden, real geblockten `feeds.meteoalarm.org`-Host aus."""
        import time as time_module
        from datetime import datetime, timezone

        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status
        from services.official_alerts.dpc import (
            DpcSource, _cache as _dpc_cache, _CACHE_KEY as _DPC_CACHE_KEY,
            _zone_at, CACHE_TTL as _DPC_CACHE_TTL,
        )
        from services.official_alerts.meteoalarm_feed import (
            MeteoAlarmFeedSource, _cache as _meteoalarm_feed_cache,
        )

        # Bozen/Bolzano -- Suedtirol, sicher innerhalb der DPC-Bbox.
        st_lat, st_lon = 46.4983, 11.3548

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        _dpc_cache.clear()
        _meteoalarm_feed_cache.clear()
        try:
            dpc = DpcSource()
            meteoalarm_it = MeteoAlarmFeedSource("IT")
            assert dpc.covers(st_lat, st_lon) is True
            assert meteoalarm_it.covers(st_lat, st_lon) is True

            zone_code = _zone_at(st_lat, st_lon)
            assert zone_code is not None, (
                "Suedtirol muss ueber die echte DPC-Zonen-Geometrie eine "
                "zustaendige Zone finden -- sonst deckt DpcSource den Punkt "
                "gar nicht ab und der Testaufbau ist falsch."
            )

            today = datetime.now(timezone.utc).date()
            _dpc_cache[_DPC_CACHE_KEY] = {
                "data": {
                    "bulletin_date": today,
                    "by_day": {
                        "today": {
                            zone_code: {
                                "Zona_all": zone_code,
                                "Nome_zona": "Test-Zone (Suedtirol)",
                                "Temporali": "1/NESSUNA ALLERTA",
                                "Idrogeo": "1/NESSUNA ALLERTA",
                                "Idraulico": "1/NESSUNA ALLERTA",
                            }
                        }
                    },
                },
                "fetched_at": time_module.monotonic(),
                "ttl": _DPC_CACHE_TTL,
            }

            oa_base._REGISTERED_SOURCES.append(dpc)
            oa_base._REGISTERED_SOURCES.append(meteoalarm_it)

            alerts, unavailable = get_official_alerts_with_status(st_lat, st_lon)
            assert alerts == [], (
                f"Beide Quellen liefern keine aktiven Warnungen, war {alerts!r}"
            )
            assert unavailable is False, (
                "DpcSource liefert erfolgreich (auch leer), MeteoAlarm ist "
                "geblockt -> DpcSource kompensiert -> unavailable=False. "
                "Reflektiert die REALE heutige Zwei-Quellen-Lage fuer "
                "Suedtirol, nicht das seit 2026-07-31 ueberholte "
                "Einzelquellen-Beispiel aus dem PO-Kommentar vom 30.07."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _dpc_cache.clear()
            _meteoalarm_feed_cache.clear()

    def test_real_failsoft_empty_from_blocked_source_is_unavailable(self):
        """REAL-PFAD-REGRESSIONSWAECHTER (Issue #1348 Fix-Loop, der eigentliche
        Punkt): eine ECHTE Quelle (``GeoSphereWarnSource``), deren Host im
        Egress-Waechter BLOCKED ist, faengt den Block intern (``cached_fetch``)
        fail-soft ab und liefert ``[]`` OHNE zu werfen. Genau dieser Pfad — kein
        Throw, aber realer Ausfall — MUSS ``unavailable=True`` ergeben.

        OHNE den Fix ist dieser Test ROT: der alte Code zaehlte ``failed`` NUR
        bei einer geworfenen Exception; die fail-soft-``[]``-Quelle lief als
        "erfolgreich leer" durch -> ``unavailable=False``. Genau diese
        Nicht-Unterscheidbarkeit von "blockiert" und "keine Warnung" war der Bug.

        Kein Mock-Theater: echte ``GeoSphereWarnSource``, echter Egress-Waechter
        (conftest-autouse, ``warnungen.zamg.at`` steht real auf BLOCKED), echte
        ``cached_fetch``-Fail-soft-Kette. Kein gesendetes Byte.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts.base import get_official_alerts_with_status
        from services.official_alerts.geosphere_warn import (
            GeoSphereWarnSource, _cache,
        )

        # Innsbruck — sicher innerhalb der GeoSphere-/INCA-Bbox (covers=True).
        at_lat, at_lon = 47.26, 11.39

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        _cache.clear()  # kein Erfolgs-Cache aus einem Vortest
        try:
            source = GeoSphereWarnSource()
            assert source.covers(at_lat, at_lon) is True, (
                "Testkoordinate muss in der GeoSphere-Bbox liegen (deckende Quelle)."
            )
            oa_base._REGISTERED_SOURCES.append(source)

            alerts, unavailable = get_official_alerts_with_status(at_lat, at_lon)
            assert alerts == [], (
                f"Die geblockte Quelle darf keine Alerts liefern, war {alerts!r}"
            )
            assert unavailable is True, (
                "Eine ECHTE deckende Quelle, deren Host geblockt ist und die intern "
                "fail-soft [] liefert (OHNE zu werfen), MUSS unavailable=True "
                "ergeben — Regressionswaechter gegen genau den #1348-Bug."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
            _cache.clear()

    def test_ac5_wrapper_returns_same_alert_list(self):
        """AC-5 Rueckwaertskompat: get_official_alerts_for_location() liefert bei
        gleicher Fixture-Lage weiter dieselbe reine Alert-Liste (kein Tuple).

        Der neue Status-Weg (get_official_alerts_with_status) und der alte
        Wrapper muessen fuer eine erfolgreiche Quelle dieselbe Liste ergeben.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import (
            OfficialAlert, get_official_alerts_for_location,
        )
        from services.official_alerts.base import get_official_alerts_with_status

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            alert = OfficialAlert(
                source="test-vigilance", hazard="thunderstorm", level=3,
                label="Gewitterwarnung Stufe Orange",
            )
            oa_base._REGISTERED_SOURCES.append(_SingleLocationSuccessSource(alert))

            legacy = get_official_alerts_for_location(_LAT, _LON)
            assert isinstance(legacy, list), (
                f"get_official_alerts_for_location() muss eine reine Liste liefern "
                f"(kein Tuple), war {type(legacy).__name__}"
            )
            assert legacy == [alert], (
                f"Bestandsverhalten muss unveraendert bleiben, war {legacy!r}"
            )

            alerts, unavailable = get_official_alerts_with_status(_LAT, _LON)
            assert alerts == [alert], (
                "get_official_alerts_with_status() muss dieselbe Alert-Liste liefern "
                "wie der Wrapper."
            )
            assert unavailable is False, (
                "Erfolgreiche deckende Quelle -> kein Ausfall."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# Renderer-Ebene: echter render_email / render_compact (kein Quellcode-Check)
# ---------------------------------------------------------------------------

_TZ = ZoneInfo("Europe/Berlin")
_HINT_SUBSTR = "nicht abrufbar"


def _make_dp():
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=0.0,
        pop_pct=10, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        wind_chill_c=20.0, cape_jkg=100.0, visibility_m=20000.0,
    )


def _make_dc():
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    active = {"temperature", "wind", "precipitation"}
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in active
        mc.format_mode = None
        mc.use_friendly_format = True
    return dc


def _make_segment(segment_id: int, *, unavailable: bool = False, alerts=None):
    """Ein echtes SegmentWeatherData. `official_alerts_unavailable` wird als
    Instanz-Attribut gesetzt (das Feld existiert im RED-Stand noch nicht als
    Dataclass-Feld — die Renderer lesen es per getattr; nach der Implementierung
    ist es ein regulaeres additives Feld mit Default False)."""
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    dp = _make_dp()
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=400.0),
        end_point=GPXPoint(lat=_LAT + 0.05, lon=_LON + 0.04, elevation_m=800.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=400.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=15.0, gust_max_kmh=25.0, precip_sum_mm=0.0,
        cloud_avg_pct=30, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=20.0,
    )
    sw = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        official_alerts=list(alerts or []),
    )
    sw.official_alerts_unavailable = unavailable
    return sw


def _render_full(segments):
    """Echter render_email(...) full-HTML/Plain-Aufruf -> (html, plain)."""
    from output.renderers.email import render_email
    from output.renderers.email.helpers import dp_to_row
    from output.tokens.dto import TokenLine

    dc = _make_dc()
    dp = _make_dp()
    seg_tables = [[dp_to_row(dp, dc, tz=_TZ)] for _ in segments]
    tl = TokenLine(trip_name="Hint-Test", report_type="evening", stage_name="Etappe 1")
    return render_email(
        tl, segments=segments, seg_tables=seg_tables, display_config=dc,
        tz=_TZ, friendly_keys=set(), email_format="full",
    )


def _render_compact(segments):
    """Echter render_compact(...)-Aufruf -> ASCII-Text."""
    from output.renderers.email.compact import render_compact

    return render_compact(
        segments=segments, dc=_make_dc(), multi_day_trend=None,
        stability_result=None, tz=_TZ, report_type="evening",
        trip_name="Hint-Test", stage_name=None, stage_stats=None,
    )


def _real_alert():
    from services.official_alerts import OfficialAlert
    return OfficialAlert(
        source="test-vigilance", hazard="thunderstorm", level=3,
        label="Gewitterwarnung Stufe Orange",
    )


class TestUnavailableHintRenderer:
    """Der sichtbare Hinweis in den drei E-Mail-Formaten (echte Render-Aufrufe)."""

    def test_ac1_full_html_zeigt_hinweis_hochkontrastig(self):
        """AC-1: ein Segment mit official_alerts_unavailable=True -> die volle
        HTML-Mail zeigt einen sichtbaren Hinweis "…nicht abrufbar".
        """
        html, _plain = _render_full([_make_segment(1, unavailable=True)])
        assert _HINT_SUBSTR in html.lower(), (
            "AC-1: Bei mindestens einer ausgefallenen abdeckenden Quelle MUSS die "
            "volle HTML-Mail einen sichtbaren Nicht-abrufbar-Hinweis enthalten "
            "(gerendertes Ergebnis, kein Quellcode-Check)."
        )

    def test_ac1_hinweis_box_ist_danger_kein_ink_faint(self):
        """AC-1 (Farb-Token): der Hinweis-Baustein nutzt G_DANGER/G_BOX_DANGER_BG,
        NIE G_INK_FAINT — geprueft am gerenderten Baustein selbst.
        """
        from output.renderers.email.unavailable_hint import (
            render_official_alerts_unavailable_html,
        )
        from output.renderers.email.design_tokens import (
            G_BOX_DANGER_BG, G_DANGER, G_INK_FAINT,
        )

        box = render_official_alerts_unavailable_html()
        assert _HINT_SUBSTR in box.lower(), "Der Baustein muss den Hinweistext tragen."
        assert G_DANGER in box, (
            f"Der Hinweis-Baustein MUSS die Gefahr-Farbe {G_DANGER} (G_DANGER) tragen."
        )
        assert G_BOX_DANGER_BG in box, (
            f"Der Hinweis-Baustein MUSS den Danger-Box-Hintergrund {G_BOX_DANGER_BG} tragen."
        )
        assert G_INK_FAINT not in box, (
            f"Der Hinweis darf NICHT im schwachen Grau {G_INK_FAINT} (G_INK_FAINT) "
            f"stehen — Lesbarkeit unter Zeitdruck (Design-Leitprinzip)."
        )

    def test_ac2_compact_mischfall_zeigt_beide_infos(self):
        """AC-2: Compact-Mischfall — ein Segment unavailable=True, ein anderes mit
        echtem Alert -> BEIDE Informationen erscheinen im ASCII-Output.
        """
        segments = [
            _make_segment(1, unavailable=True),
            _make_segment(2, alerts=[_real_alert()]),
        ]
        text = _render_compact(segments)
        assert text.isascii(), "Compact-Output muss reines ASCII bleiben."
        assert _HINT_SUBSTR in text.lower(), (
            "AC-2: Der Nicht-abrufbar-Hinweis MUSS im Compact-Text erscheinen, "
            "auch wenn zusaetzlich echte Warnungen vorliegen."
        )
        assert "Gewitterwarnung Stufe Orange" in text, (
            "AC-2: Die echte Warnung des zweiten Segments MUSS ebenfalls erscheinen "
            "(die beiden Infos sind orthogonal)."
        )

    def test_ac2_full_plain_zeigt_hinweis(self):
        """AC-2-Anker: der Plain-Teil der vollen Mail traegt den Hinweis ebenfalls."""
        _html, plain = _render_full([_make_segment(1, unavailable=True)])
        assert _HINT_SUBSTR in plain.lower(), (
            "Der Plain-Teil der vollen Mail MUSS den Nicht-abrufbar-Hinweis tragen."
        )

    def test_ac3_ac4_kein_hinweis_wenn_flag_false(self):
        """AC-3/AC-4: alle abdeckenden Quellen erfolgreich (bzw. keine deckende
        Quelle) -> official_alerts_unavailable=False -> KEIN Hinweis in
        HTML/Plain/Compact.
        """
        html, plain = _render_full([_make_segment(1, unavailable=False)])
        compact = _render_compact([_make_segment(1, unavailable=False)])
        assert _HINT_SUBSTR not in html.lower(), "AC-3/4: kein Hinweis im HTML ohne Ausfall."
        assert _HINT_SUBSTR not in plain.lower(), "AC-3/4: kein Hinweis im Plain ohne Ausfall."
        assert _HINT_SUBSTR not in compact.lower(), "AC-3/4: kein Hinweis im Compact ohne Ausfall."

    def test_ac6_regression_keine_warnung_alle_quellen_ok(self):
        """AC-6 Regressionsanker: "keine Warnungen, alle Quellen ok" (Flag False,
        keine official_alerts) -> kein neuer Hinweis, Mail rendert regulaer.
        """
        seg = _make_segment(1, unavailable=False, alerts=[])
        html, plain = _render_full([seg])
        compact = _render_compact([seg])
        for out, fmt in ((html, "html"), (plain, "plain"), (compact, "compact")):
            assert _HINT_SUBSTR not in out.lower(), (
                f"AC-6: Ohne Ausfall darf im {fmt}-Output kein neuer Hinweis stehen."
            )
        # Regulaerer Inhalt bleibt erhalten (Trip-Name im Header).
        assert "Hint-Test" in html
        assert "Hint-Test" in compact

    def test_any_official_alerts_unavailable_helper(self):
        """Signal-Helfer fuer den Trip-weiten Hinweis: any(...) ueber Segmente."""
        from output.renderers.email.unavailable_hint import (
            any_official_alerts_unavailable,
        )

        assert any_official_alerts_unavailable(
            [_make_segment(1, unavailable=False), _make_segment(2, unavailable=True)]
        ) is True
        assert any_official_alerts_unavailable(
            [_make_segment(1, unavailable=False)]
        ) is False
