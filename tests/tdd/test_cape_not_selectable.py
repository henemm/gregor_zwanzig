"""
TDD RED — Issue #1585: CAPE ist keine wählbare Wetter-Metrik mehr.

SPEC: docs/specs/modules/feat_1585_cape_selectable_false.md v1.0

PO-Regel (2026-08-10, "volle Parität"): CAPE (`cape_jkg`) ist fachlich nur
eine interne Zutat der Gewitterstufen-Fusion (`thunder_level`) — analog zu
ADR-0005/#710 (`confidence`). `MetricDefinition(id="cape").selectable` wird
`False`, und ZWEI zusätzliche Pfade, die den zentralen `selectable`-Flag
heute NICHT respektieren, werden mitgezogen: SMS/Trip-Telegram
(`_filter_metrics_by_report_type`) und Ortsvergleich
(`get_compare_metric_catalog`/`resolve_enabled_metrics`).

AC-1: /api/metrics und der Katalog enthalten 'cape' nicht mehr.
AC-2: E-Mail-Tabelle zeigt für Bestandstrips keine CAPE-Spalte mehr.
AC-3: SMS-Kürzel 'CP' verschwindet für Bestandstrips.
AC-4: Ortsvergleich-Katalog (Backend-Hälfte) enthält 'cape_max_jkg' nicht mehr.
AC-5: Ortsvergleich-Ausgabe (Preset-Auflösung) verwirft 'cape_max_jkg'.
AC-6: GET /api/templates referenziert 'cape' nicht mehr für die 3 betroffenen Profile.
AC-7: Bestandsdaten mit aktiviertem cape laden weiterhin ohne Datenverlust (Baseline).
AC-8: thunder_level_from_signals() bleibt strukturell unverändert (Baseline).

PHASE: TDD RED — die AC-1/2/3/4/5/6-Tests MÜSSEN mit dem aktuellen Code
SCHEITERN (cape ist heute selectable=True und wird überall ausgeliefert).
AC-7/AC-8 sind Regressions-Baselines (bestehen bereits jetzt, dürfen es
nach der Änderung weiterhin tun) — kein Mock, echte Katalog-/Renderer-Logik.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def metrics_client() -> TestClient:
    """Echter FastAPI-TestClient für den config-Router (liefert /api/metrics, /api/templates)."""
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: cape darf nicht im user-sichtbaren Metrik-Katalog erscheinen
# ---------------------------------------------------------------------------

class TestApiMetricsExcludesCape:
    """AC-1: /api/metrics und der Katalog bieten 'cape' nicht als wählbare Metrik an."""

    def test_api_metrics_endpoint_excludes_cape(self, metrics_client: TestClient):
        """AC-1 (Verhalten): Echter GET /api/metrics liefert in KEINER Kategorie id=='cape'."""
        resp = metrics_client.get("/api/metrics")
        assert resp.status_code == 200, f"/api/metrics antwortete {resp.status_code}"
        catalog = resp.json()

        offending: list[str] = []
        for category, metrics in catalog.items():
            for m in metrics:
                if m.get("id") == "cape":
                    offending.append(f"{category}: {m.get('label')!r}")

        assert not offending, (
            "Issue #1585: 'cape' (Gewitterenergie) wird noch als wählbare Metrik "
            f"von /api/metrics ausgeliefert: {offending}. CAPE ist nur eine Zutat "
            "der Gewitterstufe, keine eigene wählbare Größe (PO-Regel #1585)."
        )

    def test_catalog_helper_excludes_cape_from_selection(self):
        """AC-1 (Quelle): get_all_metrics() (speist /api/metrics) enthält 'cape' nicht."""
        from app.metric_catalog import get_all_metrics

        selectable_ids = [m.id for m in get_all_metrics()]
        assert "cape" not in selectable_ids, (
            "Issue #1585: 'cape' steht noch im wählbaren Metrik-Katalog "
            "(get_all_metrics). Sie muss aus der Auswahl entfernt werden."
        )


# ---------------------------------------------------------------------------
# AC-2: E-Mail-Stundentabelle zeigt für Bestandstrips keine CAPE-Spalte mehr
# ---------------------------------------------------------------------------

def _legacy_dc_with_cape():
    """Bestands-display_config mit cape enabled=True (wie bei den 3 PO-Trips)."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id="legacy-1585",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="cape", enabled=True),
            MetricConfig(metric_id="wind", enabled=True),
        ],
    )


class TestEmailTableExcludesCapeColumn:
    """AC-2: cape mit enabled=True in Bestands-display_config wird beim
    E-Mail-Rendering still ignoriert — keine CAPE-Spalte in dp_to_row/visible_cols."""

    def test_dp_to_row_excludes_cape_col_key(self):
        """AC-2 (dp_to_row): CAPE col_key 'cape' erscheint NICHT in der Row."""
        from app.models import ForecastDataPoint
        from output.renderers.email.helpers import dp_to_row

        base_ts = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        dp = ForecastDataPoint(ts=base_ts, t2m_c=15.0, wind10m_kmh=12.0, cape_jkg=1200.0)
        dc = _legacy_dc_with_cape()
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Vienna"))

        assert "cape" not in row, (
            "AC-2: CAPE col_key darf nicht in der Row erscheinen — "
            f"Row-Keys: {[k for k in row if not k.startswith('_')]}"
        )
        assert "temp" in row, "temperature muss weiterhin in der Row sein"
        assert "wind" in row, "wind muss weiterhin in der Row sein"

    def test_visible_cols_excludes_cape(self):
        """AC-2 (visible_cols): CAPE-Spalte erscheint nicht in visible_cols."""
        from app.models import ForecastDataPoint
        from output.renderers.email.helpers import dp_to_row, visible_cols

        base_ts = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        dp = ForecastDataPoint(ts=base_ts, t2m_c=15.0, wind10m_kmh=12.0, cape_jkg=1200.0)
        dc = _legacy_dc_with_cape()
        row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Vienna"))
        cols = visible_cols([row])

        col_keys = [k for k, _ in cols]
        assert "cape" not in col_keys, (
            f"AC-2: CAPE-Spalte darf in visible_cols nicht erscheinen — Spalten: {col_keys}"
        )
        assert "temp" in col_keys, "temperature muss in visible_cols sichtbar sein"
        assert "wind" in col_keys, "wind muss in visible_cols sichtbar sein"


# ---------------------------------------------------------------------------
# AC-3: SMS-Kürzel 'CP' verschwindet für Bestandstrips
# ---------------------------------------------------------------------------

class TestSmsExcludesCape:
    """AC-3: cape mit enabled=True darf nicht mehr in der SMS-Kanal-Metrikmenge landen."""

    def test_filter_metrics_by_report_type_excludes_cape(self):
        """AC-3 (Choke-Point): _filter_metrics_by_report_type() lässt cape für
        morning/evening nicht mehr durch, obwohl enabled=True gesetzt ist."""
        from app.models import MetricConfig, _filter_metrics_by_report_type

        metrics = [
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="cape", enabled=True),
        ]
        for report_type in ("morning", "evening"):
            result_ids = {mc.metric_id for mc in _filter_metrics_by_report_type(metrics, report_type)}
            assert "cape" not in result_ids, (
                f"AC-3: cape erscheint noch im Ergebnis von "
                f"_filter_metrics_by_report_type(report_type={report_type!r}): {result_ids}"
            )
            assert "temperature" in result_ids, (
                f"AC-3: temperature darf nicht mit verschwinden (report_type={report_type!r})"
            )

    def test_get_metrics_for_channel_sms_excludes_cape(self):
        """AC-3 (User-Pfad): dc.get_metrics_for_channel('sms', 'evening') — derselbe
        Aufruf, den trip_report.py für das SMS-Kürzel 'CP:' nutzt — enthält cape nicht mehr."""
        dc = _legacy_dc_with_cape()
        sms_ids = {mc.metric_id for mc in dc.get_metrics_for_channel("sms", "evening")}
        assert "cape" not in sms_ids, (
            f"AC-3: cape erscheint noch in der SMS-Kanal-Metrikmenge (CP:-Kürzel): {sms_ids}"
        )
        assert "temperature" in sms_ids, "temperature darf nicht mit verschwinden"
        assert "wind" in sms_ids, "wind darf nicht mit verschwinden"


# ---------------------------------------------------------------------------
# AC-4: Ortsvergleich-Katalog (Backend-Hälfte) — Frontend-Hälfte folgt in Phase 6
# (corridorEditorState.ts ist ein Frontend-co-located Test, in Phase 5 durch
# den edit_gate blockiert — siehe Known Limitations der Spec / Projekt-Präzedenz
# #1107, #1329 B: Go-/Frontend-Co-located-Tests werden erst in Phase 6 zusammen
# mit dem Produktionscode angelegt).
# ---------------------------------------------------------------------------

class TestCompareCatalogExcludesCape:
    """AC-4 (Backend): get_compare_metric_catalog() liefert 'cape_max_jkg' nicht mehr."""

    def test_get_compare_metric_catalog_excludes_cape_max_jkg(self):
        from output.renderers.compare_metric_catalog import get_compare_metric_catalog

        catalog = get_compare_metric_catalog()
        keys = [entry["key"] for entry in catalog]
        assert "cape_max_jkg" not in keys, (
            f"AC-4: 'cape_max_jkg' erscheint noch im Ortsvergleich-Katalog: {keys}"
        )
        # Nachbar-Eintrag muss unverändert erhalten bleiben (kein Kollateralschaden).
        assert "freezing_level_m" in keys, (
            "AC-4: benachbarte Katalogzeile 'freezing_level_m' darf nicht mit verschwinden"
        )


# ---------------------------------------------------------------------------
# AC-5: Ortsvergleich-Ausgabe — resolve_enabled_metrics() verwirft cape_max_jkg
# (deckt Preset 4 ab: E-Mail/SMS/Telegram teilen sich diesen Choke-Point)
# ---------------------------------------------------------------------------

class TestCompareResolveExcludesCape:
    """AC-5: eine gespeicherte active_metrics-Auswahl mit cape_max_jkg (z.B. Preset 4)
    liefert cape_max_jkg nach der Auflösung nicht mehr — andere Metriken bleiben."""

    def test_resolve_enabled_metrics_drops_cape_max_jkg(self):
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        resolved = resolve_enabled_metrics(["cape_max_jkg", "temp_max_c", "wind_max_kmh"])
        assert resolved is not None
        assert "cape_max" not in resolved, (
            f"AC-5: 'cape_max' (aufgelöst aus 'cape_max_jkg') erscheint noch im "
            f"Ergebnis von resolve_enabled_metrics: {resolved}"
        )
        assert "temp_max" in resolved and "wind_max" in resolved, (
            f"AC-5: andere aktivierte Metriken dürfen nicht mit verschwinden: {resolved}"
        )


# ---------------------------------------------------------------------------
# AC-6: GET /api/templates referenziert cape nicht mehr für die 3 betroffenen Profile
# (Gegen den Code verifiziert: alpen-trekking, radtour, wassersport — NICHT
# wandern/allgemein, wie eine frühere Formulierung dieser Spec fälschlich sagte.)
# ---------------------------------------------------------------------------

class TestTemplatesExcludeCape:
    """AC-6: die drei Aktivitätsprofile, die heute 'cape' referenzieren, tun das nicht mehr."""

    _AFFECTED_PROFILES = ("alpen-trekking", "radtour", "wassersport")

    def test_api_templates_endpoint_excludes_cape(self, metrics_client: TestClient):
        resp = metrics_client.get("/api/templates")
        assert resp.status_code == 200, f"/api/templates antwortete {resp.status_code}"
        templates = {t["id"]: t for t in resp.json()}

        offending = [
            tid for tid in self._AFFECTED_PROFILES
            if tid in templates and "cape" in templates[tid]["metrics"]
        ]
        assert not offending, (
            f"AC-6: folgende Profile referenzieren 'cape' noch in /api/templates: {offending}"
        )
        # Übrige Metriken jedes betroffenen Profils bleiben erhalten (nur cape entfernt).
        for tid in self._AFFECTED_PROFILES:
            assert tid in templates, f"AC-6: Profil {tid!r} fehlt komplett in /api/templates"
            assert len(templates[tid]["metrics"]) > 0, (
                f"AC-6: Profil {tid!r} darf nicht durch die Filterung leerlaufen"
            )

    def test_get_all_templates_excludes_cape(self):
        """AC-6 (Quelle): get_all_templates() direkt geprüft, ohne HTTP-Layer."""
        from app.metric_catalog import get_all_templates

        templates = {t["id"]: t for t in get_all_templates()}
        offending = [
            tid for tid in self._AFFECTED_PROFILES
            if tid in templates and "cape" in templates[tid]["metrics"]
        ]
        assert not offending, (
            f"AC-6: folgende Profile referenzieren 'cape' noch in get_all_templates(): {offending}"
        )


# ---------------------------------------------------------------------------
# AC-7: Bestandsdaten-Sicherheit — Baseline, muss VOR und NACH der Änderung gelten
# ---------------------------------------------------------------------------

class TestExistingCapeConfigRoundtrip:
    """AC-7 (Baseline): Ein Trip/Preset mit aktiviertem cape lädt fehlerfrei;
    übrige Metriken bleiben erhalten (kein Datenverlust, Read-Modify-Write)."""

    def test_display_config_with_cape_preserves_other_metrics(self):
        """AC-7: display_config mit [temp, cape, wind] → nach Roundtrip bleiben temp & wind."""
        from dataclasses import asdict
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig

        original = _legacy_dc_with_cape()
        restored = UnifiedWeatherDisplayConfig(
            trip_id=original.trip_id,
            metrics=[MetricConfig(**asdict(m)) for m in original.metrics],
        )

        ids = {m.metric_id for m in restored.metrics if m.enabled}
        assert "temperature" in ids and "wind" in ids, (
            f"AC-7: Reguläre Metriken dürfen beim Umgang mit cape nicht verloren gehen: {ids}"
        )
        # cape selbst bleibt in der PERSISTENZ erhalten (kein Datenverlust) —
        # nur die Konsum-/Render-Seite ignoriert es (s. AC-2/AC-3).
        assert "cape" in ids, (
            "AC-7: cape selbst darf beim Laden NICHT aus der Konfiguration entfernt "
            "werden (keine Migration, Read-Modify-Write-Prinzip)"
        )

    def test_resolve_enabled_metrics_does_not_crash_on_cape_max_jkg(self):
        """AC-7 (Compare-Preset 4): eine gespeicherte Auswahl mit cape_max_jkg
        löst ohne Exception auf — läuft schon heute fehlerfrei (Baseline)."""
        from output.renderers.compare_metric_ids import resolve_enabled_metrics

        resolved = resolve_enabled_metrics(["cape_max_jkg", "temp_max_c"])
        assert resolved is not None, "AC-7: darf nicht crashen oder None liefern"
        assert "temp_max" in resolved, "AC-7: andere Metriken bleiben in der Auflösung"


# ---------------------------------------------------------------------------
# AC-8: thunder_level_from_signals() bleibt strukturell unabhängig vom
# Katalog-selectable-Flag — Regressions-Baseline (Fusion liest cape_jkg direkt
# aus den Rohdaten, nicht über MetricDefinition/get_metric()).
# ---------------------------------------------------------------------------

class TestThunderFusionUnaffectedByCapeSelectable:
    """AC-8 (Baseline): CAPE bleibt volle Zutat der Gewitterstufen-Fusion,
    unabhängig davon, ob cape im Katalog selectable ist oder nicht."""

    def test_thunder_level_from_signals_uses_cape_regardless_of_catalog(self):
        from output.metric_format import ThunderLevel, thunder_level_from_signals

        # CAPE über der Schwelle -> mindestens LOW, unabhängig vom Katalog-Flag.
        level = thunder_level_from_signals(
            wettercode_level=None,
            lightning_density=None,
            cape_jkg=1500.0,
            lightning_potential_jkg=None,
            # Issue #1679 (CIN-Teil): rohe NWS-Leiter zur unveraenderten
            # Katalog-Schwelle 1000; `cin_jkg=None` (unbekannte Hemmung) haelt
            # die Deckelung auf LOW aufrecht, unter der AC-8 formuliert wurde.
            cape_threshold_jkg=1000.0, cape_med_min=2500.0, cape_high_min=4000.0,
            cin_jkg=None,
            lpi_low_min=None, lpi_med_min=None, lpi_high_min=None,
        )
        assert level == ThunderLevel.LOW, (
            f"AC-8: CAPE >= Schwelle muss weiterhin mindestens LOW ergeben, war: {level}"
        )

        # CAPE unter der Schwelle -> kein Signal.
        level_below = thunder_level_from_signals(
            wettercode_level=None,
            lightning_density=None,
            cape_jkg=500.0,
            lightning_potential_jkg=None,
            cape_threshold_jkg=1000.0, cape_med_min=2500.0, cape_high_min=4000.0,
            cin_jkg=None,
            lpi_low_min=None, lpi_med_min=None, lpi_high_min=None,
        )
        assert level_below == ThunderLevel.NONE, (
            f"AC-8: CAPE < Schwelle darf kein Signal liefern, war: {level_below}"
        )


# ---------------------------------------------------------------------------
# AC-9 (PO-Entscheidung 2026-08-10, Nachtrag): CAPE bekommt NIRGENDS mehr
# Alarmwirkung — weder neu einrichtbar noch für Bestandsdaten wirksam. Der
# CAPE-Delta-Alarm (#1592) UND der CAPE-Wertebereichs-Korridor laufen beide
# durch is_alert_metric_active() (Trip- UND Compare-Pfad, s.
# deviation_alert_engine.py::_select_detector -> expand_per_metric_levels).
# EIN Funktions-Fix genügt: is_alert_metric_active() lehnt eine AlertMetric
# ab, deren Katalog-Größe nicht mehr selectable ist — unabhängig vom
# enabled-Flag im Bestand.
# ---------------------------------------------------------------------------

class TestAlertEngineExcludesCape:
    """AC-9: is_alert_metric_active() gilt für CAPE nie mehr als aktiv,
    obwohl die Bestands-display_config enabled=True führt (kein Datenverlust,
    die Konfiguration bleibt stehen — nur die Auswertung ignoriert sie)."""

    def test_is_alert_metric_active_false_for_cape_despite_enabled(self):
        from app.models import AlertMetric
        from services.weather_change_detection import is_alert_metric_active

        dc = _legacy_dc_with_cape()  # cape: enabled=True (Bestandsdaten-Fall)
        assert is_alert_metric_active(AlertMetric.CAPE, dc) is False, (
            "AC-9: CAPE darf trotz enabled=True in der Bestands-Config nicht "
            "mehr als alarmfähig gelten (Delta-Alarm #1592 UND Wertebereichs-"
            "Korridor hängen daran)."
        )

    def test_is_alert_metric_active_unaffected_for_other_metrics(self):
        """AC-9 (Kollateralschaden-Wächter): andere Alarmgrößen bleiben aktiv."""
        from app.models import AlertMetric, MetricConfig, UnifiedWeatherDisplayConfig
        from services.weather_change_detection import is_alert_metric_active

        dc = UnifiedWeatherDisplayConfig(
            trip_id="legacy-1585-other",
            metrics=[
                MetricConfig(metric_id="temperature", enabled=True),
                MetricConfig(metric_id="gust", enabled=True),  # AlertMetric.WIND_GUST -> catalog_id "gust"
                MetricConfig(metric_id="cape", enabled=True),
            ],
        )
        assert is_alert_metric_active(AlertMetric.TEMPERATURE_MAX, dc) is True, (
            "AC-9: temperature_max darf durch die CAPE-Änderung nicht mit abgeschaltet werden"
        )
        assert is_alert_metric_active(AlertMetric.WIND_GUST, dc) is True, (
            "AC-9: wind_gust darf durch die CAPE-Änderung nicht mit abgeschaltet werden"
        )


# ---------------------------------------------------------------------------
# AC-10 (automatische Konsequenz von AC-1, gemessen): der CAPE-Wertebereichs-
# Korridor (Ortsvergleich/Trip-Mail-Markierung) wird inert, weil
# resolve_corridor_summary_field() bereits heute über summary_field_for()
# läuft (die selectable bereits vor diesem Issue respektiert hat). Kein
# eigener Code-Fix nötig — nur ein Nachweis + ehrliche Nachführung der 3
# bestehenden Tests in tests/tdd/test_trip_mail_corridor_mark.py.
# ---------------------------------------------------------------------------

class TestCorridorGoesInertForCape:
    """AC-10: ein CAPE-Wertebereichs-Korridor löst nach der Änderung kein
    Summary-Feld mehr auf — die Markierung entfällt (PO-bestätigt 2026-08-10)."""

    def test_resolve_corridor_summary_field_returns_none_for_cape(self):
        from services.corridor_threshold import resolve_corridor_summary_field

        result = resolve_corridor_summary_field("cape_max_jkg")
        assert result is None, (
            f"AC-10: CAPE-Korridor muss nach der Änderung kein Feld mehr auflösen, war: {result!r}"
        )


# ---------------------------------------------------------------------------
# Mutations-Gegenprobe (Adversary Runde 1, F001/F002): die beiden neuen Filter
# müssen gegen `MetricDefinition.selectable` arbeiten, NICHT gegen die
# Zeichenkette "cape" bzw. `AlertMetric.CAPE`. Ohne die folgenden Tests bleibt
# eine hartkodierte Fassung grün — CAPE ist heute die einzige Größe, an der
# sich beide Varianten unterscheiden ließen, und genau deshalb beweist ein
# CAPE-Test die Regel nicht.
#
# Träger ist `confidence`: seit #710/#715 produktiv `selectable=False`, mit
# #1585 nicht verwandt — und bisher in KEINEM Test mit der Kanal-Kaskade bzw.
# der Alarm-Aktivität kombiniert.
# ---------------------------------------------------------------------------

def _legacy_dc_with_confidence():
    """Bestands-display_config mit confidence enabled=True."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id="legacy-confidence",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="confidence", enabled=True),
            MetricConfig(metric_id="wind", enabled=True),
        ],
    )


class TestChannelFilterIsGenericNotCapeSpecific:
    """F001: der Filter in `_filter_metrics_by_report_type()` schließt JEDE
    nicht wählbare Größe aus, nicht nur `cape`."""

    def test_filter_metrics_by_report_type_excludes_confidence(self):
        from app.models import _filter_metrics_by_report_type

        dc = _legacy_dc_with_confidence()
        for report_type in ("morning", "evening"):
            result_ids = {
                mc.metric_id
                for mc in _filter_metrics_by_report_type(dc.metrics, report_type)
            }
            assert "confidence" not in result_ids, (
                f"F001: confidence (selectable=False seit #710) erscheint noch im "
                f"Ergebnis für report_type={report_type!r}: {result_ids} — der "
                "Filter prüft offenbar auf die Zeichenkette 'cape' statt auf "
                "MetricDefinition.selectable."
            )
            assert "temperature" in result_ids, "temperature darf nicht mit verschwinden"

    def test_get_metrics_for_channel_excludes_confidence(self):
        """Derselbe Nachweis am Nutzer-Pfad (SMS/Telegram teilen diesen Aufruf)."""
        dc = _legacy_dc_with_confidence()
        for channel in ("sms", "telegram", "email"):
            ids = {mc.metric_id for mc in dc.get_metrics_for_channel(channel, "evening")}
            assert "confidence" not in ids, (
                f"F001: confidence erscheint noch in der Kanal-Metrikmenge "
                f"({channel}): {ids}"
            )
            assert "temperature" in ids and "wind" in ids, (
                f"reguläre Metriken dürfen nicht mit verschwinden ({channel}): {ids}"
            )


class TestAlertActivityIsGenericNotCapeSpecific:
    """F002: `is_alert_metric_active()` legt JEDE Alarm-Größe still, deren
    Katalog-Zuordnung vollständig aus nicht wählbaren Größen besteht — nicht
    nur `AlertMetric.CAPE`."""

    def test_alert_metric_with_only_non_selectable_ids_is_inactive(self, monkeypatch):
        from app.models import AlertMetric
        from services import weather_change_detection as wcd

        dc = _legacy_dc_with_confidence()
        assert wcd._ALERT_METRIC_TO_CATALOG_ID[AlertMetric.VISIBILITY] == ("visibility",), (
            "Vorbedingung: VISIBILITY trägt die erwartete echte Zuordnung"
        )

        # Eine NICHT-CAPE-Alarmgröße bekommt eine vollständig nicht wählbare
        # Zuordnung. Eine hartkodierte Fassung (`if alert_metric ==
        # AlertMetric.CAPE`) antwortet hier weiterhin mit der Alt-Logik und
        # fällt auf: `confidence` ist in der display_config enabled=True.
        monkeypatch.setitem(
            wcd._ALERT_METRIC_TO_CATALOG_ID, AlertMetric.VISIBILITY, ("confidence",),
        )
        assert wcd.is_alert_metric_active(AlertMetric.VISIBILITY, dc) is False, (
            "F002: eine Alarm-Größe, deren Katalog-Zuordnung nur aus nicht "
            "wählbaren Größen besteht, muss inaktiv sein — auch wenn sie nicht "
            "CAPE heißt und die Größe enabled=True trägt."
        )

    def test_partially_selectable_mapping_stays_active(self, monkeypatch):
        """Gegenprobe: enthält die Zuordnung MINDESTENS eine wählbare Größe,
        bleibt die OR-Logik über ALLE Kennungen erhalten — sonst verstummte der
        Min-Temperatur-Alarm, dessen Aktivierungssignal im Ortsvergleich an der
        nicht wählbaren `temperature_cold` hängt."""
        from app.models import AlertMetric
        from services import weather_change_detection as wcd

        dc = _legacy_dc_with_confidence()
        monkeypatch.setitem(
            wcd._ALERT_METRIC_TO_CATALOG_ID,
            AlertMetric.VISIBILITY,
            ("confidence", "temperature"),
        )
        assert wcd.is_alert_metric_active(AlertMetric.VISIBILITY, dc) is True, (
            "F002-Gegenprobe: eine gemischte Zuordnung darf NICHT stillgelegt "
            "werden — `temperature` ist wählbar und in der display_config aktiv."
        )
