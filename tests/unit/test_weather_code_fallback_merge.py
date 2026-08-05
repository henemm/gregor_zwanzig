"""
Unit tests: weather_code ueberlebt den Model-Metric-Fallback (WEATHER-05b).

Fehlt dem Primaermodell `weather_code`, wird der Rohcode zwar per Ersatzmodell
abgerufen, beim Merge aber heute still verworfen -- `weather_code` fehlt in
`OpenMeteoProvider._PARAM_TO_FIELD`. Diese Suite deckt AC-1 bis AC-5 der Spec
ab: der gemergte Rohcode (`wmo_code`) UND die daraus nachgeleiteten Felder
`thunder_level`/`hail_flag`.

Fuenf Testklassen, je AC eine, pure In-Memory-Objekte, kein Netz.

SPEC: docs/specs/modules/fix_1492_s1_wettercode_fallback.md v1.0
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(model: str = "meteofrance_arome") -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model=model,
        run=datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="grid_point",
    )


def _make_dp(
    hour: int,
    wmo_code: int | None = None,
    thunder_level: ThunderLevel | None = None,
    hail_flag: bool | None = None,
) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 2, 17, hour, 0, tzinfo=timezone.utc),
        t2m_c=10.0,
        wind10m_kmh=15.0,
        gust_kmh=25.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        humidity_pct=60,
        wmo_code=wmo_code,
        thunder_level=thunder_level,
        hail_flag=hail_flag,
    )


def _make_timeseries(data: list[ForecastDataPoint], model: str = "meteofrance_arome") -> NormalizedTimeseries:
    return NormalizedTimeseries(meta=_make_meta(model), data=data)


# ---------------------------------------------------------------------------
# AC-1: Wirkungsnachweis ueber den produktiv verdrahteten Merge-Pfad
# ---------------------------------------------------------------------------

class TestMergeFallbackFillsWeatherCode:
    """AC-1: derselbe Aufruf, den fetch_forecast bei jeder Metrik-Luecke
    produktiv ausfuehrt (openmeteo.py:1142) -- kein neuer, unverdrahteter
    Pfad. Erwartet ROT: `weather_code` fehlt heute in `_PARAM_TO_FIELD`,
    `_derive_thunder_fields` existiert nicht -- alle drei Felder bleiben
    `None` statt gefuellt zu werden."""

    def test_fills_wmo_code_and_derives_thunder_and_hail_from_fallback(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        primary_dp = _make_dp(8)  # thunder_level/wmo_code/hail_flag alle None
        fallback_dp = _make_dp(8, wmo_code=96)  # Gewitter mit Hagel

        primary = _make_timeseries([primary_dp])
        fallback = _make_timeseries([fallback_dp], model="icon_eu")

        provider = OpenMeteoProvider()
        filled = provider._merge_fallback(primary, fallback, ["weather_code"])

        assert "weather_code" in filled
        assert primary.data[0].wmo_code == 96
        assert primary.data[0].thunder_level == ThunderLevel.HIGH
        assert primary.data[0].hail_flag is True


# ---------------------------------------------------------------------------
# AC-2: Ueberschreib-Invariante, allgemein
# ---------------------------------------------------------------------------

class TestMergeFallbackDoesNotOverwriteAlreadySetFields:
    """AC-2: ein bereits (aus einer anderen Quelle) gesetzter Datenpunkt
    bleibt unangetastet -- nur der echte Luecken-Datenpunkt derselben Reihe
    wird veraendert. Gegenprobe: prueft die Implementierung nur global
    (z.B. `if filled: ...` ohne `is None`-Check pro Feld), wird dieser Test
    rot, weil der bereits gesetzte Datenpunkt aus seinem EIGENEN wmo_code
    (1, kein Gewittercode) auf ThunderLevel.NONE neu abgeleitet wuerde,
    obwohl thunder_level bereits auf HIGH gesetzt war."""

    def test_already_set_datapoint_untouched_only_gap_filled(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        # Bereits gesetzt (z.B. aus einer Direktquelle) -- wmo_code=1 (kein
        # Gewittercode) wuerde bei Neuableitung NONE ergeben, nicht HIGH.
        already_set = _make_dp(8, wmo_code=1, thunder_level=ThunderLevel.HIGH, hail_flag=None)
        gap = _make_dp(9)  # echte Luecke: alle drei Felder None

        primary = _make_timeseries([already_set, gap])

        fb_already = _make_dp(8, wmo_code=96)  # abweichender Ersatzwert
        fb_gap = _make_dp(9, wmo_code=96)
        fallback = _make_timeseries([fb_already, fb_gap], model="icon_eu")

        provider = OpenMeteoProvider()
        provider._merge_fallback(primary, fallback, ["weather_code"])

        # bereits gesetzter Datenpunkt: exakt unveraendert
        assert primary.data[0].wmo_code == 1
        assert primary.data[0].thunder_level == ThunderLevel.HIGH
        assert primary.data[0].hail_flag is None

        # Luecken-Datenpunkt: aus dem Ersatzmodell gefuellt
        assert primary.data[1].wmo_code == 96
        assert primary.data[1].thunder_level == ThunderLevel.HIGH
        assert primary.data[1].hail_flag is True

    def test_already_set_hail_flag_survives_merged_code_without_hail(self) -> None:
        """F001-Nachbesserung: der `hail_flag`-Schutz in `_derive_thunder_fields`
        (``if dp.hail_flag is None:``) ist von den bisherigen AC-2-Faellen NICHT
        bewacht -- entfernt man dort nur die Zeile, bleiben alle bisherigen Tests
        gruen, weil der dort verwendete `already_set`-Datenpunkt einen EIGENEN
        `wmo_code=1` traegt: `_parse_hail_flag(1)` liefert selbst schon `None`,
        eine Neuableitung waere von der geschuetzten Fassung nicht zu
        unterscheiden.

        Konstitutiv fuer DIESEN Test:
        - `wmo_code=None` beim bereits gesetzten Datenpunkt (fehlt), NICHT ein
          eigener Rohcode -- sonst erreicht ihn der (fill-only) Merge gar nicht,
          und die Frage nach der Neuableitung stellt sich nie.
        - Der gemergte Ersatzcode ist `95` (Gewitter OHNE Hagel-Zusatzcode),
          bewusst NICHT `96`. Mit `96` waere `_parse_hail_flag(96) == True` --
          identisch zum bereits gesetzten Wert, und eine fehlerhafte
          Neuableitung faellt nicht auf. Erst mit `95` ergibt eine ungeschuetzte
          Neuableitung `None` und ueberschreibt das gesetzte `True` sichtbar.

        NICHT "vereinfachen" indem hier ein eigener `wmo_code` oder ein
        Ersatzcode `96` verwendet wird -- das macht den Test wirkungslos, ohne
        dass er dabei anders aussieht (Mutations-Gegenprobe 2026-08-05: ohne
        den Schutz ``if dp.hail_flag is None:`` blieb dieser Test bei `96` bzw.
        eigenem Rohcode faelschlich gruen)."""
        from providers.openmeteo import OpenMeteoProvider

        # hail_flag bereits gesetzt (z.B. aus einer Direktquelle), eigener
        # wmo_code fehlt -- der Merge fuellt ihn frisch aus dem Ersatzmodell.
        already_set = _make_dp(8, wmo_code=None, thunder_level=None, hail_flag=True)
        gap = _make_dp(9)  # echte Luecke, unbeteiligt

        primary = _make_timeseries([already_set, gap])

        # Ersatzcode 95: Gewitter OHNE Hagel-Zusatzcode -- _parse_hail_flag(95)
        # liefert selbst None, wuerde also das gesetzte True ueberschreiben.
        fb_already = _make_dp(8, wmo_code=95)
        fb_gap = _make_dp(9, wmo_code=95)
        fallback = _make_timeseries([fb_already, fb_gap], model="icon_eu")

        provider = OpenMeteoProvider()
        provider._merge_fallback(primary, fallback, ["weather_code"])

        # der Rohcode wird gefuellt -- nur die Ableitung bleibt geschuetzt
        assert primary.data[0].wmo_code == 95
        assert primary.data[0].hail_flag is True


# ---------------------------------------------------------------------------
# AC-3: Nicht-Gewitter-Code ist eine geprüfte Entwarnung, kein Loch (#1474 AC-4)
# ---------------------------------------------------------------------------

class TestMergeFallbackPreservesCheckedNoneLevel:
    """AC-3 (#1474 AC-4): ThunderLevel.NONE ist die geprüfte Entwarnung, NICHT
    Python None -- darf weder auf None zurueckgesetzt noch durch den
    Ersatzwert ueberschrieben werden.

    WICHTIG fuer spaetere Leser: der geprueft-entwarnte Datenpunkt MUSS mit
    fehlendem eigenem `wmo_code` (None) konstruiert werden, NICHT mit einem
    eigenen Rohcode wie `1`. Der Merge ist fill-only und ersetzt einen
    bereits vorhandenen `wmo_code` nie -- ein Datenpunkt mit eigenem Rohcode
    `1` wuerde vom Ersatzwert `96` also gar nicht erreicht, und eine
    Nachableitung aus `1` ergibt ohnehin wieder `NONE`. Ein Test mit eigenem
    Rohcode kann dann eine fehlerhafte Implementierung nicht von einer
    richtigen unterscheiden (Mutations-Gegenprobe 2026-08-05: mit eigenem
    Rohcode blieb die Mutation `in (None, ThunderLevel.NONE)` faelschlich
    gruen). Erst wenn der Rohcode selbst fehlt und der Merge ihn frisch aus
    dem Ersatzmodell fuellt (hier `96`, ein Gewittercode), kann die Mutation
    ueberhaupt zuschlagen -- und tut es auch (`NONE` -> `HIGH`, rot).
    NICHT "vereinfachen" indem `wmo_code` wieder gesetzt wird -- das macht
    den Test wirkungslos, ohne dass er dabei anders aussieht.

    Gegenprobe: ein Check `if dp.thunder_level in (None, ThunderLevel.NONE):`
    statt `is None` wuerde diesen Datenpunkt faelschlich mit dem frisch
    gemergten Gewittercode 96 auf HIGH ueberschreiben."""

    def test_checked_none_level_survives_untouched(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        # wmo_code=None ist konstitutiv -- siehe Klassen-Docstring.
        checked = _make_dp(8, wmo_code=None, thunder_level=ThunderLevel.NONE, hail_flag=None)
        gap = _make_dp(9)

        primary = _make_timeseries([checked, gap])

        fb_checked = _make_dp(8, wmo_code=96)
        fb_gap = _make_dp(9, wmo_code=96)
        fallback = _make_timeseries([fb_checked, fb_gap], model="icon_eu")

        provider = OpenMeteoProvider()
        provider._merge_fallback(primary, fallback, ["weather_code"])

        # der Rohcode wird sehr wohl gefuellt -- nur die Einstufung bleibt
        # unangetastet; das ist der Kern der Zusicherung.
        assert primary.data[0].wmo_code == 96
        # geprüfte Entwarnung bleibt exakt NONE -- weder None noch HIGH
        assert primary.data[0].thunder_level == ThunderLevel.NONE
        assert primary.data[0].thunder_level is not None

        # Luecken-Datenpunkt derselben Reihe wird ganz normal gefuellt
        assert primary.data[1].thunder_level == ThunderLevel.HIGH


# ---------------------------------------------------------------------------
# AC-4: Fail-soft, beide Modelle ohne Wert
# ---------------------------------------------------------------------------

class TestMergeFallbackFailsSoftWithoutWeatherCode:
    """AC-4: liefert weder Primaer- noch Ersatzmodell fuer einen Zeitpunkt
    einen weather_code, bleiben alle drei Felder None -- kein Absturz, keine
    Ausnahme. Der zweite Datenpunkt derselben Reihe hat einen echten Treffer,
    damit `_derive_thunder_fields` ueberhaupt laeuft (sonst landet
    "weather_code" nie in `filled` und der Fail-soft-Zweig wird gar nicht
    durchlaufen)."""

    def test_datapoint_without_any_weather_code_stays_none_no_crash(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        both_missing = _make_dp(8)  # weder primaer noch Ersatz liefert etwas
        hit = _make_dp(9)  # anderer Zeitpunkt: Ersatz liefert einen Wert

        primary = _make_timeseries([both_missing, hit])

        fb_both_missing = _make_dp(8)  # auch hier kein wmo_code
        fb_hit = _make_dp(9, wmo_code=95)
        fallback = _make_timeseries([fb_both_missing, fb_hit], model="icon_eu")

        provider = OpenMeteoProvider()
        filled = provider._merge_fallback(primary, fallback, ["weather_code"])  # wirft nicht

        assert primary.data[0].wmo_code is None
        assert primary.data[0].thunder_level is None
        assert primary.data[0].hail_flag is None

        # Regelfall am zweiten Zeitpunkt: dort greift der Fallback normal
        assert "weather_code" in filled
        assert primary.data[1].wmo_code == 95
        assert primary.data[1].thunder_level == ThunderLevel.HIGH


# ---------------------------------------------------------------------------
# AC-5: Erkennungs-Vorbedingung -- schliesst die Kette am schwaechsten Glied
# ---------------------------------------------------------------------------

class TestWeatherCodeDetectionPrecondition:
    """AC-5: prueft die Erkennungs-/Auswahlkette VOR `_merge_fallback` --
    ohne die landet `weather_code` gar nicht erst in `missing_params`, und
    AC-1 bis AC-4 wuerden nie erreicht (sie bekommen `missing_params`
    synthetisch vorgegeben, pruefen also nicht diese Vorbedingung).

    BEIDE Tests dieser Klasse sind bereits vor der Implementierung dieser
    Scheibe GRUEN: `weather_code` steht schon heute in `PROBE_PARAMS`
    (openmeteo.py:214) und `_find_fallback_model` (openmeteo.py:399) filtert
    keine Metrik gezielt aus. Das ist erwartet und in Ordnung -- diese Tests
    sind Regressions-Waechter fuer eine BESTEHENDE Vorbedingung, kein neues
    Verhalten dieser Scheibe. Sie bleiben in der Suite, damit ein spaeterer
    Umbau (z.B. eine neue Ausschlussliste in `_find_fallback_model`) sofort
    auffiele."""

    def test_weather_code_is_a_probe_param(self) -> None:
        from providers.openmeteo import PROBE_PARAMS

        assert "weather_code" in PROBE_PARAMS

    def test_find_fallback_model_treats_weather_code_like_any_other_metric(
        self, tmp_path, monkeypatch
    ) -> None:
        import providers.openmeteo as om

        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        from providers.openmeteo import OpenMeteoProvider

        cache = {
            "probe_date": date.today().isoformat(),
            "models": {
                "meteofrance_arome": {"available": ["temperature_2m"], "unavailable": ["weather_code"]},
                "icon_eu": {"available": ["temperature_2m", "weather_code"], "unavailable": []},
            },
        }
        fake_cache.write_text(json.dumps(cache))

        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["weather_code"])

        assert result is not None
        fb_model_id, _fb_grid_res_km, _fb_endpoint = result
        assert fb_model_id == "icon_eu"
