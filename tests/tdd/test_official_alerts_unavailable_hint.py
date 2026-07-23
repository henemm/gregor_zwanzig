"""TDD RED — Issue #1348-Rest: Briefing-Hinweis "amtliche Warnungen nicht abrufbar".

SPEC: docs/specs/modules/warn_unavailable_hint.md (AC-1 … AC-6)

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

PO-Entscheid 2026-07-23 (STRENG): `unavailable = (es gibt abdeckende Quellen)
AND (mindestens EINE davon ist beim Fetch fehlgeschlagen)` — NICHT "alle
fehlgeschlagen". Der Mischfall-Test unten ist der Kern dieser Entscheidung.
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

    def test_mischfall_streng_one_fail_one_empty_is_unavailable(self):
        """KERN DER PO-ENTSCHEIDUNG (STRENG): eine deckende Quelle wirft, eine
        deckende Quelle liefert erfolgreich [] -> unavailable=True.

        Schon EINE ausgefallene abdeckende Quelle genuegt — sie haette eine
        Warnung tragen koennen, die die andere Quelle nicht abdeckt. Die frueher
        diskutierte "alle muessen fehlschlagen"-Variante wuerde hier faelschlich
        unavailable=False liefern; genau das schliesst dieser Test aus.
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
            assert unavailable is True, (
                "STRENG (PO-Entscheid 2026-07-23): eine ausgefallene abdeckende "
                "Quelle genuegt fuer unavailable=True, auch wenn eine andere "
                "abdeckende Quelle erfolgreich [] liefert."
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

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
