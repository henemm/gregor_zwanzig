"""Katalogeintrag ``wind_chill_night`` (#1660 Scheibe A) -- waehlbar in der
Temperatur-Kategorie, aber in KEINER Stundentabelle, KEINEM
Kanal-Spaltenlayout und KEINEM Alarm-Mapping.

Spec: docs/specs/modules/fix_1660a_temp_trennung.md — AC-12, Source Punkt 1
(Katalogeintrag) und Punkt 7 (vier Sonderbehandlungs-Stellen, Muster
``temperature_night``/#1484).

Kern-Schicht, deterministisch: kein Mock, kein Netz. ``metrics_client``-
Fixture 1:1 aus ``test_night_temp_own_metric_selection.py`` (Vorbild #1484)
uebernommen.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import MetricConfig, UnifiedWeatherDisplayConfig

NIGHT_METRIC = "wind_chill_night"


@pytest.fixture
def metrics_client() -> TestClient:
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-12 — Katalog & API
# ---------------------------------------------------------------------------

class TestCatalogAndApi:

    def test_catalog_offers_felt_night_metric_as_selectable(self):
        from app.metric_catalog import get_all_metrics

        ids = {m.id for m in get_all_metrics()}
        assert NIGHT_METRIC in ids, (
            "„Gefuehlte Nacht-Tiefsttemperatur“ fehlt im waehlbaren Katalog."
        )

    def test_api_metrics_exposes_felt_night_next_to_wind_chill(self, metrics_client):
        resp = metrics_client.get("/api/metrics")
        assert resp.status_code == 200
        catalog = resp.json()

        by_id = {m["id"]: (cat, m) for cat, ms in catalog.items() for m in ms}
        assert NIGHT_METRIC in by_id, (
            f"GET /api/metrics liefert {sorted(by_id)} — die gefuehlte "
            f"Nachtgroesse fehlt."
        )
        night_cat, night = by_id[NIGHT_METRIC]
        wc_cat, _ = by_id["wind_chill"]
        assert night_cat == wc_cat, (
            f"Die gefuehlte Nachtgroesse steht in Kategorie {night_cat!r}, "
            f"„Gefuehlte Temperatur“ in {wc_cat!r} — beide gehoeren zusammen."
        )
        assert "Nacht" in night["label"], (
            f"Editor-Beschriftung muss den Nachtbezug tragen: {night['label']!r}"
        )

    def test_felt_night_metric_has_no_alert_declaration(self):
        """Der Kaeltealarm bleibt bei ``temperature_cold`` (#914), der
        gefuehlte Risikowert bei ``wind_chill`` -- der neue Eintrag deklariert
        keine eigene Alarm-Identitaet (sonst regeneriert
        ``alert_metric_mapping.generated.json`` einen unerwuenschten
        Eintrag, s. Spec Punkt 8)."""
        from app.metric_catalog import get_metric

        metric = get_metric(NIGHT_METRIC)  # raises KeyError, solange fehlend
        assert not metric.alert_metrics, (
            f"„Gefuehlte Nacht-Tiefsttemperatur“ darf keine alert_metrics "
            f"deklarieren: {metric.alert_metrics!r}"
        )


# ---------------------------------------------------------------------------
# AC-12 — Nachtfenster-Skalar: keine Stundenspalte, kein Alarm-Mapping
# ---------------------------------------------------------------------------

class TestFeltNightIsNeverAnHourlyColumn:

    def test_trip_channel_layout_excludes_felt_night_from_columns(self):
        """Trip-Mail-Seite: ``NO_HOURLY_COLUMN_METRIC_IDS`` (email/helpers.py)
        muss den neuen Eintrag fuehren -- sonst erscheint eine
        Tabellenspalte „Gefuehlte Nacht“ mit Stundenwerten, die es gar
        nicht gibt."""
        from output.renderers.email.helpers import NO_HOURLY_COLUMN_METRIC_IDS

        assert NIGHT_METRIC in NO_HOURLY_COLUMN_METRIC_IDS, (
            f"{NIGHT_METRIC!r} fehlt in NO_HOURLY_COLUMN_METRIC_IDS "
            f"({sorted(NO_HOURLY_COLUMN_METRIC_IDS)})."
        )

    def test_render_for_channel_never_places_felt_night_in_a_bucket(self):
        """Wirkungs-Nachweis (nicht nur Konfiguration): ein Trip mit
        aktivierter ``wind_chill_night`` darf im E-Mail-Layout weder eine
        primary- noch eine secondary-Spalte fuer die Groesse erzeugen --
        analog zum Filter, den ``render_for_channel`` heute schon fuer
        ``temperature_night`` anwendet (channel_layout.py:88)."""
        from output.renderers.channel_layout import render_for_channel

        dc = UnifiedWeatherDisplayConfig(
            trip_id="i1660a-hourly",
            metrics=[
                MetricConfig(metric_id=NIGHT_METRIC, enabled=True,
                             bucket="secondary"),
                MetricConfig(metric_id="precipitation", enabled=True),
            ],
        )
        layout = render_for_channel("email", dc, "evening")

        assert NIGHT_METRIC not in layout.table_columns, (
            f"{NIGHT_METRIC!r} erscheint als Tabellenspalte: "
            f"{layout.table_columns!r}"
        )
        assert NIGHT_METRIC not in layout.detail_metrics, (
            f"{NIGHT_METRIC!r} erscheint als Detail-Zeile: "
            f"{layout.detail_metrics!r} -- channel_layout.py:88 filtert "
            f"bisher nur „temperature_night“ aus der Menge heraus."
        )

    def test_compare_hourly_excludes_felt_night_with_reason(self):
        """Ortsvergleich-Seite: ``HOURLY_EXCLUDED_METRIC_IDS`` +
        ``HOURLY_EXCLUSION_REASON`` (compare_hourly_metric_ids.py:59/70-73)
        muessen den neuen Eintrag ebenfalls fuehren -- sonst zeigt der
        Vergleichs-Stundenverlauf eine Geisterspalte, die kein Test
        bemerkt."""
        from output.renderers.compare_hourly_metric_ids import (
            HOURLY_EXCLUDED_METRIC_IDS, HOURLY_EXCLUSION_REASON,
        )

        assert NIGHT_METRIC in HOURLY_EXCLUDED_METRIC_IDS, (
            f"{NIGHT_METRIC!r} fehlt in HOURLY_EXCLUDED_METRIC_IDS "
            f"({sorted(HOURLY_EXCLUDED_METRIC_IDS)})."
        )
        reason = HOURLY_EXCLUSION_REASON.get(NIGHT_METRIC)
        assert reason and len(reason) >= 15, (
            f"HOURLY_EXCLUSION_REASON fuehrt keine (oder eine zu kurze) "
            f"Begruendung fuer {NIGHT_METRIC!r}: {reason!r}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
