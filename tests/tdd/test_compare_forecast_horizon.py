"""TDD RED — Issue #1305 (Scheibe A4 von Epic #1301): Vorhersagehorizont fuer
den Ortsvergleich wird von 48h auf 96h (COMPARE_FORECAST_HOURS) angehoben; die
hartkodierte Horizont-Kachel in der Vergleichs-Mail entfaellt ersatzlos.

Spec: docs/specs/modules/compare_forecast_horizon.md

AC-Test-Mapping:
  AC-1 -> TestCompareForecastHorizonDispatch.test_dispatch_always_requests_96h_regardless_of_preset_value
  AC-2 -> TestCompareForecastHorizonParity.test_ac2_preview_and_dispatch_request_same_horizon
  AC-3 -> TestCompareForecastHorizonParity.test_ac3_preview_horizon_covers_target_date_plus_3_days
  AC-4 -> TestCompareForecastHorizonMailHeader.test_ac4_header_has_no_horizont_tile
  AC-5 -> KEIN neuer Test. Wird von der Bestandssuite abgedeckt:
          tests/tdd/test_compare_dispatch_fixed_window.py (time_window-Regression)
          und tests/tdd/test_compare_html_email.py::TestCompareMailWithoutTimeWindow
          (Zieldatum heute/morgen bleibt inhaltlich unveraendert, da mehr
          Stunden nur den Datumsbereich erweitern, nicht die Auswertungslogik
          fuer Tage innerhalb des ALTEN 48h-Fensters aendern).

Wichtig: `COMPARE_FORECAST_HOURS` existiert in `services.comparison_engine`
NOCH NICHT (wird erst in der GREEN-Phase eingefuehrt) — dieser Testmodul
importiert die Konstante daher bewusst NICHT, sondern verwendet den Literal-
wert 96 in den Assertions. Ein Import wuerde die Modul-Collection fuer ALLE
Tests hier mit ImportError abbrechen, statt einzelne Tests kontrolliert rot
laufen zu lassen.

KEINE Mocks (CLAUDE.md): Wiederverwendung der etablierten Boundary-Recorder
aus den Schwesterdateien (echte Subklassen von ComparisonEngine, kein
Mock()/patch()/MagicMock):
  - tests/tdd/test_compare_dispatch_fixed_window.py (_capture_engine_call,
    Sentinel-Exception-Abbruch VOR Netzwerk/SMTP)
  - tests/tdd/test_compare_preview_service.py (_install_recording_engine,
    monkeypatch-basiert, baut ein echtes ComparisonResult aus den
    uebergebenen Orten)
  - tests/tdd/test_compare_html_email.py (_make_result, reine Renderer-Fixture)
Die Helper werden hier per Import wiederverwendet statt dupliziert
(Aliase, weil beide Schwesterdateien eine eigene `_preset`/`_EngineCalls`
mit unterschiedlicher Signatur besitzen).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.profile import ActivityProfile

from tests.tdd.test_compare_dispatch_fixed_window import (
    _capture_engine_call as _dp_capture_engine_call,
    _fresh_user as _dp_fresh_user,
    _preset as _dp_preset,
    _resolvable_location as _dp_resolvable_location,
)
from tests.tdd.test_compare_html_email import _make_result
from tests.tdd.test_compare_preview_service import (
    _EngineCalls as _PvEngineCalls,
    _install_recording_engine as _pv_install_recording_engine,
    _location as _pv_location,
    _preset as _pv_preset,
    _seed as _pv_seed,
    compare_env,  # noqa: F401 - Fixture-Import, von pytest per Name aufgeloest
)

import pytest


# ---------------------------------------------------------------------------
# AC-1 — Versand fordert unabhaengig vom Preset-Altwert 96h an
# ---------------------------------------------------------------------------


class TestCompareForecastHorizonDispatch:
    """AC-1: `send_one_compare_preset` reicht unabhaengig vom (deprecateten,
    #1268) Preset-Wert `forecast_hours` einen festen Horizont von 96h an
    `ComparisonEngine.run` durch."""

    @pytest.mark.parametrize("legacy_forecast_hours", [0, 24, 48, 72])
    def test_dispatch_always_requests_96h_regardless_of_preset_value(
        self, tmp_path, legacy_forecast_hours
    ):
        """GIVEN ein Bestands-Preset mit einem beliebigen (auch veralteten)
              gespeicherten forecast_hours-Wert (0/24/48/72)
        WHEN der reguläre Versand (send_one_compare_preset) laeuft
        THEN fordert ComparisonEngine.run in JEDEM Fall forecast_hours=96 an
             — unabhaengig vom Preset-Altwert.

        AC-1. RED vor Fix: scheduler_dispatch_service.py:351 reicht heute
        fest 48 durch (Spec Dependencies), unabhaengig vom hier variierten
        Preset-Wert — der Test erwartet 96 und schlaegt daher fehl.
        """
        user_id = _dp_fresh_user()
        loc_id = f"loc-1305-{legacy_forecast_hours}"
        loc = _dp_resolvable_location(loc_id)
        preset = _dp_preset(
            f"cp-1305-{legacy_forecast_hours}",
            loc_id=loc_id,
            forecast_hours=legacy_forecast_hours,
            _user_id=user_id,
        )

        recorded = _dp_capture_engine_call(preset, loc, tmp_path)

        assert recorded.forecast_hours == 96, (
            f"RED: Preset-Altwert forecast_hours={legacy_forecast_hours} ergab "
            f"tatsaechlich angeforderten Horizont {recorded.forecast_hours}h, "
            "erwartet 96h (Spec AC-1: geteilte Konstante COMPARE_FORECAST_HOURS, "
            "unabhaengig vom Preset)."
        )


# ---------------------------------------------------------------------------
# AC-2 / AC-3 — Vorschau == Versand, und beide decken heute+3 ab
# ---------------------------------------------------------------------------


class TestCompareForecastHorizonParity:
    """AC-2 (Vorschau == Versand) und AC-3 (Horizont deckt heute+3)."""

    def test_ac2_preview_and_dispatch_request_same_horizon(
        self, compare_env, monkeypatch, tmp_path
    ):
        """GIVEN dasselbe Ortsvergleichs-Preset (identische Konfiguration)
        WHEN einmal die Vorschau (ComparePreviewService) und einmal der
             reguläre Versand (send_one_compare_preset) fuer dieses Preset
             ausgeloest werden
        THEN fordern beide Pfade denselben Vorhersage-Horizont an, und dieser
             betraegt 96h (Anti-#1297: Vorschau- und Versandpfad duerfen
             strukturell nicht auseinanderlaufen koennen).

        Reihenfolge bewusst Dispatch-ZUERST, dann Vorschau: `_capture_engine_call`
        patcht/restauriert `ComparisonEngine` manuell (nicht ueber `monkeypatch`)
        und geht dabei von einem unveraenderten Ausgangszustand aus. Liefe die
        Vorschau zuerst (die via `monkeypatch` patcht), wuerde der Dispatch-Helper
        faelschlich die bereits gepatchte Vorschau-Engine als "Original" ansehen.

        RED vor Fix: beide Pfade liefern 48 statt 96 -> der Gleichheits-Assert
        auf 96 schlaegt fehl (Spec Dependencies: scheduler_dispatch_service.py:351
        und compare_preview_service.py:152 sind beide fest auf 48 verdrahtet).
        """
        user_id = compare_env
        preset_id = "cp-1305-ac2"
        loc_id = "loc-1305-ac2"
        loc = _pv_location(loc_id, "Innsbruck", 47.27, 11.39)
        _pv_seed(user_id, [loc], _pv_preset(preset_id, user_id, [loc_id]))

        # 1) Dispatch-Pfad zuerst (eigenstaendiges Patch/Restore, s. Docstring)
        dispatch_preset = _dp_preset(
            preset_id, loc_id=loc_id, _user_id=f"{user_id}-dispatch"
        )
        dispatch_recorded = _dp_capture_engine_call(dispatch_preset, loc, tmp_path)
        dispatch_forecast_hours = dispatch_recorded.forecast_hours

        # 2) Vorschau-Pfad danach (monkeypatch, automatisch am Testende restauriert)
        preview_calls = _PvEngineCalls()
        _pv_install_recording_engine(monkeypatch, preview_calls)
        from services.compare_preview_service import ComparePreviewService

        ComparePreviewService().render_all_channels(
            preset_id, user_id=user_id, target_date=date.today().isoformat()
        )
        preview_forecast_hours = preview_calls.kwargs_seen[0].get("forecast_hours")

        assert preview_forecast_hours == dispatch_forecast_hours == 96, (
            f"RED: Vorschau forderte {preview_forecast_hours}h an, Versand "
            f"{dispatch_forecast_hours}h an — erwartet beide == 96 "
            "(COMPARE_FORECAST_HOURS, Anti-#1297)."
        )

    def test_ac3_preview_horizon_covers_target_date_plus_3_days(
        self, compare_env, monkeypatch
    ):
        """GIVEN ein Ortsvergleichs-Preset mit Zieldatum heute+3 Tage
        WHEN die Vorschau aufgerufen und der tatsaechlich angeforderte
             `forecast_hours`-Wert (via Recording-Engine, wie AC-2) erfasst
             wird
        THEN erfuellt dieser Wert das Deckungskriterium fuer den Zieltag:
             now + timedelta(hours=forecast_hours) >= Start des Tages NACH
             dem Zieldatum.

        Herleitung des Kriteriums (zeitpunktunabhaengig, kein echter Fetch
        noetig): `now` liegt irgendwo im aktuellen Tag D zur Stunde h in
        [0, 24). Der erreichbare Zeitpunkt ist reach = now + forecast_hours.
          - Mit forecast_hours=48: reach = (D+2 Tage) + h Stunden. Fuer JEDES
            h in [0, 24) gilt reach < (D+4) 00:00 Uhr (Start von Zieltag+1,
            da Zieltag = D+3) — der Zieltag D+3 wird NIE erreicht.
          - Mit forecast_hours=96: reach = (D+4 Tage) + h Stunden. Fuer JEDES
            h in [0, 24) gilt reach >= (D+4) 00:00 Uhr — der gesamte Zieltag
            D+3 liegt vollstaendig innerhalb des Horizonts.
        Das Kriterium haengt damit nachweislich nicht von der Tageszeit des
        Testlaufs ab.

        AC-3. RED vor Fix: compare_preview_service.py:152 fordert fest 48h an
        (Spec Dependencies) -> das Deckungskriterium ist False -> Assertion
        schlaegt fehl. Fachlich: die Vorschau fuer ein Zieldatum heute+3 lief
        vorher leer, weil ausserhalb des 48h-Fensters (Spec "Side effects").
        """
        user_id = compare_env
        preset_id = "cp-1305-ac3"
        loc_id = "loc-1305-ac3"
        loc = _pv_location(loc_id, "Innsbruck", 47.27, 11.39)
        target_date = date.today() + timedelta(days=3)
        _pv_seed(user_id, [loc], _pv_preset(preset_id, user_id, [loc_id]))

        preview_calls = _PvEngineCalls()
        _pv_install_recording_engine(monkeypatch, preview_calls)
        from services.compare_preview_service import ComparePreviewService

        now_reference = datetime.now()
        ComparePreviewService().render_all_channels(
            preset_id, user_id=user_id, target_date=target_date.isoformat()
        )

        forecast_hours = preview_calls.kwargs_seen[0].get("forecast_hours")
        assert forecast_hours is not None, (
            "Der Engine-Aufruf der Vorschau muss forecast_hours als Keyword-"
            "Argument enthalten"
        )

        reach = now_reference + timedelta(hours=forecast_hours)
        day_after_target = datetime.combine(
            target_date + timedelta(days=1), datetime.min.time()
        )
        covered = reach >= day_after_target

        assert covered, (
            f"RED: angeforderter Horizont von {forecast_hours}h deckt das "
            f"Zieldatum {target_date.isoformat()} (heute+3) nicht ab "
            f"(reach={reach.isoformat()}, benoetigt >= "
            f"{day_after_target.isoformat()}). Vorher lief die Vorschau mit "
            "48h fest und damit fuer Zieldaten > heute+2 leer (Spec "
            "'Side effects')."
        )


# ---------------------------------------------------------------------------
# AC-4 — Kopfzeile der Vergleichs-Mail zeigt keine Horizont-Kachel mehr
# ---------------------------------------------------------------------------


class TestCompareForecastHorizonMailHeader:
    """AC-4: Die Kopfzeile der Vergleichs-Mail (Desktop- und Mobile-Tabelle)
    enthaelt weder das Wort "Horizont" noch einen Wert wie "+48h"/"+96h";
    Profil/Orte/Erstellt bleiben als Kacheln sichtbar."""

    def test_ac4_header_has_no_horizont_tile(self):
        """GIVEN ein beliebiges ComparisonResult
        WHEN render_compare_html() die Kopfzeile baut
        THEN fehlen sowohl das Wort "Horizont" als auch die Werte "+48h" und
             "+96h" vollstaendig aus dem gerenderten HTML; die Kacheln
             "Profil", "Orte" und "Erstellt" bleiben vorhanden.

        AC-4. RED vor Fix: compare_html.py (`_render_header`, um Zeile
        684-717) baut weiterhin eine vierte Kachel mit
        `horizont_val = "+48h"` in Desktop- UND Mobile-Tabelle (Spec
        Implementation Details).
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_result()
        html = render_compare_html(result, profile=ActivityProfile.WINTERSPORT)

        assert "Horizont" not in html, (
            "RED: Kopfzeile enthaelt weiterhin das Wort 'Horizont' — die "
            "Kachel soll ersatzlos entfallen (Spec AC-4)."
        )
        assert "+48h" not in html, (
            "RED: Kopfzeile enthaelt weiterhin den alten Horizont-Wert '+48h'."
        )
        assert "+96h" not in html, (
            "Kopfzeile darf auch keinen neuen Horizont-Wert '+96h' zeigen — "
            "die Kachel entfaellt komplett statt einen neuen Wert zu zeigen "
            "(Spec 'Known Limitations')."
        )

        for expected in ("Profil", "Orte", "Erstellt"):
            assert expected in html, (
                f"Kachel-Label '{expected}' muss weiterhin sichtbar sein "
                "(nur die Horizont-Kachel entfaellt)."
            )
