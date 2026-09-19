"""TDD RED — Issue #1983 (Gewitter S6 aus Epic #1419), Modelllauf-Mehrheit.

SPEC: docs/specs/modules/feat_1983_gewitter_modelllauf_mehrheit.md
AC-2..AC-13 (AC-1 ist Text-only, kein Test noetig).

Echter Fixture-Befund (19.09.2026, gemessen in /40 gegen die ECHTE
Ensemble-API-Antwort `tests/fixtures/openmeteo_ensemble/
wolayersee_2026-09-19_weather_code.json`, 48h, 217 Spalten):
Die Antwort-Suffixe sind NICHT die Anfrage-Modellnamen. Je Stunde gibt es
- 40 ICON-Spalten: `weather_code_icon_seamless_eps` (Kontrolllauf) +
  `weather_code_member01_icon_seamless_eps` .. `member39_icon_seamless_eps`
- 31 GEFS-Spalten: `weather_code_ncep_gefs_seamless` (Kontrolllauf) +
  `weather_code_member01_ncep_gefs_seamless` .. `member30_ncep_gefs_seamless`
- `weather_code_ecmwf_ifs04` existiert, ist aber in der GESAMTEN Aufzeichnung
  durchgehend `null` -- MUSS von der Mehrheits-Berechnung ausgeschlossen
  werden (spec Implementierung-Abruf Punkt 1).
=> 71 potenziell gueltige Codes/Stunde (40+31). In der Aufzeichnung ist der
Gewitteranteil ueberall 0% (Codes 0/1/2/3/51) -- ein Implementierer, der
z.B. `endswith("icon_seamless")` filtert (ohne "_eps"-Suffix), trifft NULL
Member; diese Tests laufen mit den ECHTEN Schluesselnamen und wuerden das
fangen.

Zwei Testschichten:
- Abrufschicht (`OpenMeteoProvider._fetch_ensemble_spread`): Fixture-basiert
  ueber `httpx.MockTransport` (Replay der echten Aufzeichnung, Werte fuer
  Schwellenfaelle gezielt veraendert -- Schema/Schluesselnamen bleiben echt).
- Anwendungsschicht (`_apply_ensemble_spreads` in trip_report_scheduler.py):
  direkt mit konstruierten `EnsembleHourStats`-Werten (die Zwei Schichten
  sind laut Spec-Architekturbefund bewusst entkoppelt -- der Ensemble-Abruf
  laeuft NACH der Fusion, s. Spec "Architektur-Befund").

KEINE MOCKS/patch()/MagicMock -- echte Dataclasses, echter
`httpx.MockTransport` (Netzersatz, kein Verhaltens-Mock), echte Renderer.
"""
from __future__ import annotations

import copy
import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.config import Location
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

_TZ = ZoneInfo("Europe/Berlin")

# Repo-relativ zur eigenen Testdatei (#1409-Pfadregel), nie ueber den
# Hauptrepo-Pfad.
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "openmeteo_ensemble"
    / "wolayersee_2026-09-19_weather_code.json"
)

_WOLAYERSEE = Location(latitude=46.61, longitude=12.87, name="Wolayersee", elevation_m=1950)


# ---------------------------------------------------------------------------
# Fixture-Helfer (Abrufschicht)
# ---------------------------------------------------------------------------


def _load_base_payload() -> dict:
    return json.loads(_FIXTURE_PATH.read_text())


def _member_keys(hourly: dict) -> List[str]:
    """Alle 71 echten Member-/Kontrolllauf-Schluessel fuer `weather_code`,
    OHNE `weather_code_ecmwf_ifs04` (liefert keine Member, spec Punkt 1).
    Sortiert fuer deterministische Zuordnung."""
    return sorted(
        k for k in hourly.keys()
        if k.startswith("weather_code") and "ecmwf" not in k
    )


def _set_hour_share(
    payload: dict, hour_index: int, n_valid: int, n_thunder: int,
    *, poison_ecmwf_with_thunder_code: bool = False,
) -> None:
    """Setzt fuer `hour_index` GENAU `n_valid` der 71 echten Member-Spalten
    auf einen gueltigen Code (`n_thunder` davon auf 95, der Rest auf 0) und
    den Rest auf `None` (Teilantwort-Simulation). `weather_code_ecmwf_ifs04`
    bleibt/wird `None` (spiegelt die echte Aufzeichnung) -- AUSSER
    `poison_ecmwf_with_thunder_code=True`: dann traegt die ecmwf-Spalte
    einen Gewittercode (95), OBWOHL sie in `n_valid`/`n_thunder` NICHT
    mitgezaehlt wurde. Eine Implementierung, die den Ausschluss von
    `weather_code_ecmwf_ifs04` (Spec Punkt 1) vergisst, zaehlt sie
    faelschlich als 72. gueltigen (Gewitter-)Wert mit -- unterscheidbar vom
    korrekten Ergebnis (spec-treue Implementierung ignoriert die Spalte,
    beide Ergebnisse weichen zahlenmaessig voneinander ab).

    Aendert `payload["hourly"]` IN-PLACE (der Aufrufer arbeitet auf einer
    deepcopy der Basis-Fixture).
    """
    assert 0 <= n_thunder <= n_valid <= 71
    hourly = payload["hourly"]
    keys = _member_keys(hourly)
    assert len(keys) == 71, f"Erwartet 71 echte Member-Schluessel, gefunden {len(keys)}"
    for i, k in enumerate(keys):
        if i < n_thunder:
            hourly[k][hour_index] = 95
        elif i < n_valid:
            hourly[k][hour_index] = 0
        else:
            hourly[k][hour_index] = None
    if "weather_code_ecmwf_ifs04" in hourly:
        hourly["weather_code_ecmwf_ifs04"][hour_index] = (
            95 if poison_ecmwf_with_thunder_code else None
        )


def _ts_for_hour(payload: dict, hour_index: int) -> datetime:
    """Reproduziert exakt die Zeitstempel-Normalisierung von
    `_fetch_ensemble_spread` (naive ISO-String -> UTC-aware)."""
    time_str = payload["hourly"]["time"][hour_index]
    ts = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _handler(payload: dict, seen: List[httpx.Request]):
    def _respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)
    return _respond


def _provider_with_payload(payload: dict, monkeypatch, tmp_path, seen: Optional[List[httpx.Request]] = None):
    from providers.openmeteo import OpenMeteoProvider

    if seen is None:
        seen = []
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    provider = OpenMeteoProvider()
    provider._client = httpx.Client(transport=httpx.MockTransport(_handler(payload, seen)))
    return provider, seen


# ---------------------------------------------------------------------------
# Helfer (Anwendungsschicht)
# ---------------------------------------------------------------------------


def _make_segment(lat: float = 46.61, lon: float = 12.87) -> TripSegment:
    base = datetime(2026, 9, 19, 6, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1950),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, elevation_m=2100),
        start_time=base,
        end_time=base + timedelta(hours=8),
        duration_hours=8.0,
        distance_km=10.0,
        ascent_m=400,
        descent_m=100,
    )


def _dp(ts: datetime, level: Optional[ThunderLevel], signals: Optional[List[str]]) -> ForecastDataPoint:
    return ForecastDataPoint(ts=ts, thunder_level=level, thunder_level_signals=signals)


def _weather_item(dps: List[ForecastDataPoint], segment: Optional[TripSegment] = None) -> SegmentWeatherData:
    seg = segment or _make_segment()
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0)
    ts = NormalizedTimeseries(meta=meta, data=dps)
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_scheduler():
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
    svc._user_id = "default"
    return svc


def _apply(dp: ForecastDataPoint, share_pct: Optional[int]):
    """Baut ein Ein-Punkt-`weather_data`, wendet `_apply_ensemble_spreads()`
    mit einem `EnsembleHourStats`-Eintrag fuer `dp.ts` an (oder mit `{}`,
    wenn `share_pct is None` den Ausfallfall simulieren soll)."""
    from providers.openmeteo import EnsembleHourStats  # RED: existiert noch nicht

    item = _weather_item([dp])
    now_utc = datetime.now(timezone.utc)
    ts_naive = dp.ts.replace(tzinfo=None) if dp.ts.tzinfo else dp.ts
    if share_pct is None:
        spreads_naive = {}
    else:
        spreads_naive = {
            ts_naive: EnsembleHourStats(
                spread_t2m_k=1.0, spread_precip_mm=0.5,
                thunder_member_share_pct=share_pct,
            )
        }
    svc = _make_scheduler()
    svc._apply_ensemble_spreads([item], spreads_naive, now_utc)
    return item


# ===========================================================================
# AC-2: >=60% hebt an, Signal "modelllauf" mit Label "Modellläufe"
# ===========================================================================


def test_ac2_65_prozent_hebt_med_auf_high_mit_modelllauf_signal():
    """GIVEN eine Stunde mit 65% Gewittercode-Anteil (13/20 echten Membern,
    ueber die Fixture-Abrufschicht ermittelt) und Ausgangsstufe MED(["cape"])
    / WHEN die Stunde fusioniert (angewendet) wird / THEN traegt sie HIGH,
    "modelllauf" ist Traeger UND deutsch beschriftet "Modellläufe".

    RED heute: `providers.openmeteo.EnsembleHourStats` existiert nicht.
    """
    dp = _dp(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc), ThunderLevel.MED, ["cape"])
    item = _apply(dp, share_pct=65)

    assert item.timeseries.data[0].thunder_level == ThunderLevel.HIGH, (
        f"65% Anteil muss auf HIGH anheben, war {item.timeseries.data[0].thunder_level!r}"
    )
    assert "modelllauf" in (item.timeseries.data[0].thunder_level_signals or []), (
        f"'modelllauf' fehlt in thunder_level_signals: "
        f"{item.timeseries.data[0].thunder_level_signals!r}"
    )
    from app.thunder_scale import THUNDER_SIGNAL_LABEL_DE, thunder_signal_label
    assert THUNDER_SIGNAL_LABEL_DE["modelllauf"] == "Modellläufe"
    assert thunder_signal_label("modelllauf") == "Modellläufe"


def test_ac2_fetch_ensemble_spread_liefert_65_prozent_aus_echter_fixture(monkeypatch, tmp_path):
    """GIVEN eine ECHTE Ensemble-Antwort (Fixture), bei der fuer eine Stunde
    20 der 71 echten Member-Spalten gueltig sind, 13 davon Gewittercode 95
    tragen / WHEN `_fetch_ensemble_spread()` sie parst / THEN liefert sie
    `thunder_member_share_pct == 65` fuer GENAU diese Stunde -- UND die
    abgesetzte Anfrage traegt `weather_code` im `hourly`-Parameter.

    RED heute: `_fetch_ensemble_spread()` liefert ein 2-Tupel, kein
    `EnsembleHourStats` mit `.thunder_member_share_pct` -> AttributeError.
    """
    payload = _load_base_payload()
    hour_index = 5
    _set_hour_share(payload, hour_index, n_valid=20, n_thunder=13)  # 65%
    expected_ts = _ts_for_hour(payload, hour_index)

    provider, seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    assert seen, "kein Ensemble-Request beobachtet"
    from urllib.parse import parse_qs
    query = parse_qs(seen[0].url.query.decode())
    assert "weather_code" in query.get("hourly", [""])[0], (
        f"Die Anfrage muss 'weather_code' im hourly-Parameter tragen, war "
        f"{query.get('hourly')!r}"
    )

    stats = result.get(expected_ts)
    assert stats is not None, f"Keine Statistik fuer Stunde {expected_ts} gefunden: {list(result)[:3]}..."
    assert stats.thunder_member_share_pct == 65, (
        f"Erwartet 65% Gewittercode-Anteil, erhalten {stats.thunder_member_share_pct!r}"
    )


def test_ac2_ecmwf_spalte_zaehlt_nicht_zur_mehrheitsberechnung(monkeypatch, tmp_path):
    """GIVEN dieselbe 65%-Stunde (20 gueltige echte Member, 13 Gewittercode)
    UND `weather_code_ecmwf_ifs04` traegt fuer diese Stunde ZUSAETZLICH
    einen Gewittercode (obwohl `ecmwf_ifs04` laut Spec Punkt 1 KEINE Member
    liefert und deshalb ausgeschlossen werden muss) / WHEN
    `_fetch_ensemble_spread()` sie parst / THEN bleibt der Anteil weiterhin
    exakt 65% -- eine Implementierung, die `ecmwf_ifs04` versehentlich
    mitzaehlt, wuerde 14/21 = 67% liefern (unterscheidbares Falsch-Ergebnis).

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    payload = _load_base_payload()
    hour_index = 5
    _set_hour_share(
        payload, hour_index, n_valid=20, n_thunder=13,
        poison_ecmwf_with_thunder_code=True,
    )
    expected_ts = _ts_for_hour(payload, hour_index)

    provider, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    stats = result[expected_ts]
    assert stats.thunder_member_share_pct == 65, (
        f"ecmwf_ifs04 darf NICHT mitgezaehlt werden -- erwartet weiterhin "
        f"65% (20 echte Member, 13 Gewittercode), erhalten "
        f"{stats.thunder_member_share_pct!r} (67% deutet auf faelschliches "
        f"Mitzaehlen von ecmwf_ifs04 als 21. gueltigem Member hin)"
    )


# ===========================================================================
# AC-3: 10-59% traegt "modelllauf" NICHT bei, Stufe unveraendert
# ===========================================================================


def test_ac3_45_prozent_traegt_kein_modelllauf_signal_bei():
    """GIVEN eine Stunde mit 45% Anteil (9/20 echten Membern) und
    Ausgangsstufe MED(["cape"]) / WHEN angewendet / THEN bleibt die Stufe
    MED, KEIN "modelllauf" in den Signalen, `thunder_probability_pct == 45`
    (das rohe Feld wird trotzdem gesetzt, spec Anwendung Punkt 1).

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    dp = _dp(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc), ThunderLevel.MED, ["cape"])
    item = _apply(dp, share_pct=45)
    result_dp = item.timeseries.data[0]

    assert result_dp.thunder_level == ThunderLevel.MED, (
        f"45% liegt im neutralen Band, Stufe muss MED bleiben, war {result_dp.thunder_level!r}"
    )
    assert result_dp.thunder_level_signals == ["cape"], (
        f"Traegerliste darf sich nicht aendern: {result_dp.thunder_level_signals!r}"
    )
    assert "modelllauf" not in (result_dp.thunder_level_signals or [])
    assert result_dp.thunder_probability_pct == 45, (
        f"thunder_probability_pct muss den rohen Anteil tragen, war "
        f"{result_dp.thunder_probability_pct!r}"
    )


# ===========================================================================
# AC-4: <10% daempft um genau eine Stufe, nie unter NONE
# ===========================================================================


def test_ac4_5_prozent_daempft_med_zu_low_high_zu_med_low_zu_none():
    """GIVEN eine Stunde mit 5% Anteil (<10%) und drei Ausgangsstufen
    (MED, HIGH, LOW, jeweils Traeger ["cape"]) / WHEN angewendet / THEN
    sinkt jede um genau eine Stufe (MED->LOW, HIGH->MED, LOW->NONE), die
    Traegerliste bleibt UNVERAENDERT ausser bei NONE (dort geleert).

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    ts = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)

    dp_med = _apply(_dp(ts, ThunderLevel.MED, ["cape"]), share_pct=5).timeseries.data[0]
    assert dp_med.thunder_level == ThunderLevel.LOW, f"MED muss zu LOW werden, war {dp_med.thunder_level!r}"
    assert dp_med.thunder_level_signals == ["cape"], dp_med.thunder_level_signals

    dp_high = _apply(_dp(ts, ThunderLevel.HIGH, ["cape"]), share_pct=5).timeseries.data[0]
    assert dp_high.thunder_level == ThunderLevel.MED, f"HIGH muss zu MED werden, war {dp_high.thunder_level!r}"
    assert dp_high.thunder_level_signals == ["cape"], dp_high.thunder_level_signals

    dp_low = _apply(_dp(ts, ThunderLevel.LOW, ["cape"]), share_pct=5).timeseries.data[0]
    assert dp_low.thunder_level == ThunderLevel.NONE, f"LOW muss zu NONE werden, war {dp_low.thunder_level!r}"
    assert not dp_low.thunder_level_signals, (
        f"Traegerliste muss bei NONE geleert sein (None oder []), war {dp_low.thunder_level_signals!r}"
    )


# ===========================================================================
# AC-5: exakt 10% und exakt 59% bleiben neutral (Grenzen gehoeren zum Band)
# ===========================================================================


def test_ac5_exakt_10_und_exakt_59_prozent_bleiben_neutral(monkeypatch, tmp_path):
    """GIVEN zwei aus der ECHTEN Fixture abgeleitete Stunden mit exakt
    10% (5/50 Membern) bzw. 59% (29/49 Membern, gerundet) Anteil / WHEN
    ueber die Abrufschicht ermittelt und dann angewendet / THEN bleibt die
    Ausgangsstufe MED(["cape"]) in BEIDEN Faellen unveraendert -- 10% gehoert
    NICHT zur Daempfung (AC-4 greift erst darunter), 59% NICHT zur Anhebung
    (AC-2 greift erst ab 60%).

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    payload = _load_base_payload()
    _set_hour_share(payload, 3, n_valid=50, n_thunder=5)    # exakt 10%
    _set_hour_share(payload, 4, n_valid=49, n_thunder=29)   # round(59.18) == 59
    ts_10 = _ts_for_hour(payload, 3)
    ts_59 = _ts_for_hour(payload, 4)

    provider, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    assert result[ts_10].thunder_member_share_pct == 10, result[ts_10].thunder_member_share_pct
    assert result[ts_59].thunder_member_share_pct == 59, result[ts_59].thunder_member_share_pct

    for share in (10, 59):
        dp = _dp(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc), ThunderLevel.MED, ["cape"])
        item = _apply(dp, share_pct=share)
        rdp = item.timeseries.data[0]
        assert rdp.thunder_level == ThunderLevel.MED, (
            f"{share}% liegt im neutralen Band, Stufe muss MED bleiben, war {rdp.thunder_level!r}"
        )
        assert rdp.thunder_level_signals == ["cape"], rdp.thunder_level_signals
        assert rdp.thunder_probability_pct == share


# ---------------------------------------------------------------------------
# Fix-Loop 1 (Adversary-Findings F001/F002, adversary-dialog.md): die
# 59%/10%-Haelfte der AC-5-Grenze war getestet, die Anhebungs-Seite
# ("genau 60% hebt an") NICHT -- Mutation `>=` -> `>` blieb dadurch
# unentdeckt (F001). Ebenso fehlte ein Fall, der `round()` von blosser
# `int()`-Trunkierung unterscheidet (F002). Beide Luecken werden hier
# geschlossen, ohne den Produktivcode zu aendern (der war bereits korrekt).
# ---------------------------------------------------------------------------


def test_ac5_exakt_60_prozent_hebt_an_anwendungsschicht():
    """GIVEN eine Stunde mit GENAU 60% Anteil (die AC-2/AC-5-Grenze selbst,
    nicht nur ein Wert deutlich darueber wie 65%) und Ausgangsstufe
    MED(["cape"]) / WHEN ueber `_apply_ensemble_spreads()` angewendet /
    THEN hebt sie auf HIGH mit "modelllauf" in den Signalen -- AC-5: "genau
    60 % gehoert zur Anhebung (AC-2)".

    Fix-Loop 1 (Finding F001): faengt die Mutation `share_pct >=
    MODELLLAUF_ANHEBUNG_MIN_PCT` -> `>` (Anhebung erst STRIKT ueber 60%),
    die zuvor mit 13/13 gruenen Tests unentdeckt blieb.
    """
    dp = _dp(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc), ThunderLevel.MED, ["cape"])
    item = _apply(dp, share_pct=60)
    result_dp = item.timeseries.data[0]

    assert result_dp.thunder_level == ThunderLevel.HIGH, (
        f"Exakt 60% MUSS anheben (AC-5: 'genau 60% gehoert zur Anhebung'), "
        f"war {result_dp.thunder_level!r}"
    )
    assert "modelllauf" in (result_dp.thunder_level_signals or []), (
        f"'modelllauf' fehlt bei exakt 60%: {result_dp.thunder_level_signals!r}"
    )
    assert result_dp.thunder_probability_pct == 60


def test_ac5_fetch_ensemble_spread_liefert_exakt_60_prozent_und_hebt_an(monkeypatch, tmp_path):
    """GIVEN eine ECHTE Ensemble-Antwort (Fixture) mit einer Stunde, bei der
    GENAU 30 von 50 echten Membern (60%, OHNE Rundungsbedarf) Gewittercode
    tragen / WHEN `_fetch_ensemble_spread()` sie parst UND das Ergebnis
    anschliessend ueber `_apply_ensemble_spreads()` angewendet wird / THEN
    liefert die Abrufschicht `thunder_member_share_pct == 60` UND die
    Anwendungsschicht hebt auf HIGH an -- Ende-zu-Ende-Beleg fuer die exakte
    Grenze, nicht nur isoliert je Schicht (Fix-Loop 1, Finding F001).
    """
    payload = _load_base_payload()
    hour_index = 6
    _set_hour_share(payload, hour_index, n_valid=50, n_thunder=30)  # exakt 60%
    expected_ts = _ts_for_hour(payload, hour_index)

    provider, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    stats = result[expected_ts]
    assert stats.thunder_member_share_pct == 60, (
        f"30/50 muss exakt 60% liefern, erhalten {stats.thunder_member_share_pct!r}"
    )

    dp = _dp(expected_ts, ThunderLevel.MED, ["cape"])
    item = _apply(dp, share_pct=stats.thunder_member_share_pct)
    result_dp = item.timeseries.data[0]
    assert result_dp.thunder_level == ThunderLevel.HIGH, (
        f"Ende-zu-Ende: 60% aus dem echten Abruf muss anheben, war "
        f"{result_dp.thunder_level!r}"
    )


def test_ac5_rundung_kreuzt_die_60_prozent_schwelle_25_von_42_membern(monkeypatch, tmp_path):
    """GIVEN eine Stunde mit 25 von 42 echten Membern (59,52...%, OHNE
    Rundung 59%, MIT Rundung 60%) / WHEN `_fetch_ensemble_spread()` sie
    parst / THEN liefert sie GENAU 60% -- `round()` (kaufmaennisch/
    nearest-integer) ist zwingend, eine blosse `int()`-Trunkierung wuerde
    59% liefern und die Anhebung an dieser Stelle verpassen.

    Fix-Loop 1 (Finding F002): faengt die Mutation `int(round(100 *
    n_thunder / n_valid))` -> `int(100 * n_thunder / n_valid)`
    (Trunkierung statt Rundung), die zuvor mit 39/39 gruenen Tests
    unentdeckt blieb -- dieser Bruch (25/42 = 59,523809...%) liegt bewusst
    NICHT auf einer glatten `.5`-Grenze (dort rundet Python
    "round-half-to-even"), sondern eindeutig ueber `.5`, sodass Rundung und
    Trunkierung nachweisbar verschiedene Ergebnisse UND verschiedenes
    Anhebungsverhalten liefern (59% = neutral, 60% = Anhebung).
    """
    payload = _load_base_payload()
    hour_index = 7
    _set_hour_share(payload, hour_index, n_valid=42, n_thunder=25)  # 59,5238...%
    expected_ts = _ts_for_hour(payload, hour_index)

    provider, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    stats = result[expected_ts]
    assert stats.thunder_member_share_pct == 60, (
        f"25/42 = 59,52...% MUSS auf 60 gerundet werden (round(), nicht "
        f"int()-Trunkierung), erhalten {stats.thunder_member_share_pct!r}"
    )


# ===========================================================================
# AC-6: Monotonie -- Ergebnis-Ordinal sinkt nie bei steigendem Anteil
# ===========================================================================


def test_ac6_ordinal_sinkt_nie_wenn_anteil_steigt():
    """GIVEN dieselbe Ausgangsstufe MED(["cape"]) mit drei Anteilen
    (5%, 30%, 70%) / WHEN jeweils angewendet / THEN sind die Ergebnis-
    Ordinale nicht-fallend (NONE=0 < LOW=1 < MED=2 < HIGH=3).

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    from app.thunder_scale import thunder_ordinal

    ts = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    ordinals = []
    for share in (5, 30, 70):
        dp = _dp(ts, ThunderLevel.MED, ["cape"])
        result = _apply(dp, share_pct=share).timeseries.data[0]
        ordinals.append(thunder_ordinal(result.thunder_level))

    assert ordinals == sorted(ordinals), (
        f"Ordinale muessen mit steigendem Anteil nicht-fallend sein: {ordinals} "
        f"(Anteile 5/30/70%)"
    )
    assert ordinals[0] < ordinals[2], (
        "5% (Daempfung) muss ein STRIKT niedrigeres Ordinal liefern als 70% "
        f"(Anhebung): {ordinals}"
    )


# ===========================================================================
# AC-7: Ausfall -- {} bzw. HTTP-Fehler laesst alles unveraendert
# ===========================================================================


def test_ac7_ausfall_laesst_stufe_und_wahrscheinlichkeit_unveraendert(monkeypatch, tmp_path):
    """GIVEN der Ensemble-Abruf schlaegt fehl (HTTP 500) bzw. liefert `{}`
    / WHEN die Etappe trotzdem fusioniert wird / THEN bleibt
    `thunder_probability_pct` `None`, kein "modelllauf"-Signal, keine
    Daempfung -- als Gegenprobe liefert ein ERFOLGREICHER Abruf im selben
    Test einen echten `EnsembleHourStats.thunder_member_share_pct`.

    RED heute: `EnsembleHourStats` existiert nicht (Gegenprobe-Teil).
    """
    from providers.openmeteo import OpenMeteoProvider

    # (a) HTTP 500 -> {}
    def _fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    provider = OpenMeteoProvider()
    provider._client = httpx.Client(transport=httpx.MockTransport(_fail))
    assert provider._fetch_ensemble_spread(_WOLAYERSEE) == {}

    # (b) leere Antwort -> {}
    def _empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    provider._client = httpx.Client(transport=httpx.MockTransport(_empty))
    assert provider._fetch_ensemble_spread(_WOLAYERSEE) == {}

    # (c) Anwendung mit {} laesst Datenpunkt unveraendert
    dp = _dp(datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc), ThunderLevel.MED, ["cape"])
    item = _apply(dp, share_pct=None)
    rdp = item.timeseries.data[0]
    assert rdp.thunder_level == ThunderLevel.MED
    assert rdp.thunder_level_signals == ["cape"]
    assert rdp.thunder_probability_pct is None, (
        f"Ohne Ensemble-Daten muss thunder_probability_pct None bleiben, war "
        f"{rdp.thunder_probability_pct!r}"
    )

    # Gegenprobe: ein ERFOLGREICHER Abruf liefert eine echte Statistik.
    payload = _load_base_payload()
    _set_hour_share(payload, 0, n_valid=20, n_thunder=1)  # 5%
    expected_ts = _ts_for_hour(payload, 0)
    provider2, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider2._fetch_ensemble_spread(_WOLAYERSEE)
    assert result[expected_ts].thunder_member_share_pct == 5


# ===========================================================================
# AC-8: Teilantwort -- nur die betroffene Stunde wird None
# ===========================================================================


def test_ac8_teilantwort_nur_die_15_member_stunde_wird_none(monkeypatch, tmp_path):
    """GIVEN eine Stunde mit nur 15 gueltigen Codes (<20) direkt neben einer
    Stunde mit 40 gueltigen Codes (davon 20 Gewittercode, 50%) / WHEN ueber
    die Abrufschicht ermittelt / THEN ist NUR die 15-Member-Stunde
    `thunder_member_share_pct=None`, die Nachbarstunde traegt 50%.

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    payload = _load_base_payload()
    _set_hour_share(payload, 0, n_valid=15, n_thunder=1)    # < 20 -> None
    _set_hour_share(payload, 1, n_valid=40, n_thunder=20)   # 50%
    ts_partial = _ts_for_hour(payload, 0)
    ts_ok = _ts_for_hour(payload, 1)

    provider, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    assert result[ts_partial].thunder_member_share_pct is None, (
        f"15 gueltige Member (<20) muessen None liefern, war "
        f"{result[ts_partial].thunder_member_share_pct!r}"
    )
    assert result[ts_ok].thunder_member_share_pct == 50, (
        f"Die Nachbarstunde mit 40 gueltigen Membern muss unberuehrt bleiben, "
        f"war {result[ts_ok].thunder_member_share_pct!r}"
    )

    from providers.openmeteo import ENSEMBLE_THUNDER_MIN_MEMBERS
    assert ENSEMBLE_THUNDER_MIN_MEMBERS == 20


# ===========================================================================
# AC-9: Radar-Schutz -- ein radar-bestaetigter Punkt wird nicht gedaempft
# ===========================================================================


def test_ac9_radar_traeger_wird_nicht_gedaempft_aber_weiter_angehoben():
    """GIVEN ein Datenpunkt mit `"radar"` in `thunder_level_signals`, Stufe
    MED, Anteil 5% (<10%) / WHEN gedaempft wird / THEN bleibt er MED
    (Beobachtung schlaegt Modell) -- GEGENPROBE im selben Test: ein
    identischer Punkt OHNE "radar" (nur ["cape"]) wird bei 5% SEHR WOHL
    gedaempft (auf LOW). Eine Anhebung (65%) bleibt am radar-Punkt weiterhin
    moeglich.

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    ts = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)

    # Radar-Punkt, 5% -> KEINE Daempfung
    dp_radar = _apply(_dp(ts, ThunderLevel.MED, ["radar"]), share_pct=5).timeseries.data[0]
    assert dp_radar.thunder_level == ThunderLevel.MED, (
        f"Radar-bestaetigter Punkt darf nicht gedaempft werden, war {dp_radar.thunder_level!r}"
    )
    assert dp_radar.thunder_level_signals == ["radar"]

    # Gegenfall OHNE radar, 5% -> MUSS daempfen
    dp_ohne_radar = _apply(_dp(ts, ThunderLevel.MED, ["cape"]), share_pct=5).timeseries.data[0]
    assert dp_ohne_radar.thunder_level == ThunderLevel.LOW, (
        f"Ohne 'radar' MUSS bei 5% gedaempft werden, war {dp_ohne_radar.thunder_level!r}"
    )

    # Anhebung bleibt am Radar-Punkt moeglich (65%)
    dp_radar_hoch = _apply(_dp(ts, ThunderLevel.MED, ["radar"]), share_pct=65).timeseries.data[0]
    assert dp_radar_hoch.thunder_level == ThunderLevel.HIGH, (
        f"Anhebung muss auch am radar-bestaetigten Punkt greifen, war "
        f"{dp_radar_hoch.thunder_level!r}"
    )


# ===========================================================================
# AC-10: alle vier Kanaele zeigen die ERGEBNIS-Stufe (nicht die Ausgangsstufe)
# ===========================================================================


def _ac10_build_item(seg: TripSegment, d: date) -> tuple[SegmentWeatherData, ForecastDataPoint]:
    """9 Stunden, alle MED(["cape"]); liefert das Item UND den 12:00-Punkt,
    der vom Aufrufer optional ueber `_apply_ensemble_spreads()` angehoben
    wird."""
    dps = [ForecastDataPoint(
        ts=datetime(d.year, d.month, d.day, h, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=10.0, precip_1h_mm=0.0,
        cloud_total_pct=50, humidity_pct=55,
        thunder_level=ThunderLevel.MED, thunder_level_signals=["cape"],
    ) for h in range(6, 15)]
    zielpunkt = next(dp for dp in dps if dp.ts.hour == 12)
    item = _weather_item(dps, segment=seg)
    return item, zielpunkt


def test_ac10_alle_vier_kanaele_zeigen_die_angehobene_stufe():
    """GIVEN zwei ansonsten IDENTISCHE Trip-Reports (9 Stunden, durchgehend
    MED(["cape"])) -- der eine unveraendert (baseline), der andere mit der
    12:00-Stunde per `_apply_ensemble_spreads()` (70% Anteil) auf HIGH
    angehoben / WHEN beide fuer E-Mail, Telegram UND SMS (== Premium-SMS,
    D5: beide senden `report.sms_text` unveraendert) gerendert werden /
    THEN zeigt JEDER der drei Kanaele in der angehobenen Fassung ein
    erkennbares Merkmal der HIGH-Stufe, das in der baseline-Fassung FEHLT --
    kein Kanal darf bei der alten MED-Darstellung verharren.

    Die konkreten Textmerkmale sind GEMESSEN (nicht geraten) am echten
    Renderer-Output ueber `TripReportFormatter().format_email()`
    (Scratchpad-Probe 2026-09-19):
    - E-Mail-Klartext:  "gewitter hoch ab 08:00" (baseline: "... mittel ...")
    - Telegram-Bubble:  "TH hoch" in der Kurzuebersicht (baseline: "TH mittel")
    - SMS/Premium-SMS:  Peak-Token traegt zusaetzlich "H@" (baseline hat
      keinen zweiten Peak, da alle Stunden gleich MED sind)

    RED heute: `EnsembleHourStats` existiert nicht.
    """
    from output.renderers.trip_report import TripReportFormatter
    from providers.openmeteo import EnsembleHourStats  # RED: existiert nicht

    d = date(2026, 9, 19)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.61, lon=12.87, elevation_m=1950, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=46.66, lon=12.92, elevation_m=2100, distance_from_start_km=8.0),
        start_time=datetime(d.year, d.month, d.day, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(d.year, d.month, d.day, 14, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=8.0, ascent_m=500.0, descent_m=0.0,
    )

    baseline_item, _ = _ac10_build_item(seg, d)
    elevated_item, zielpunkt = _ac10_build_item(seg, d)

    now_utc = datetime.now(timezone.utc)
    ts_naive = zielpunkt.ts.replace(tzinfo=None)
    spreads_naive = {
        ts_naive: EnsembleHourStats(
            spread_t2m_k=1.0, spread_precip_mm=0.5, thunder_member_share_pct=70,
        )
    }
    svc = _make_scheduler()
    svc._apply_ensemble_spreads([elevated_item], spreads_naive, now_utc)

    assert zielpunkt.thunder_level == ThunderLevel.HIGH, (
        f"Vorbedingung verletzt: Zielpunkt wurde nicht angehoben, war {zielpunkt.thunder_level!r}"
    )

    baseline_report = TripReportFormatter().format_email(
        [baseline_item], "Wolayersee-Trip", "morning", stage_name="Etappe 1", tz=_TZ,
    )
    elevated_report = TripReportFormatter().format_email(
        [elevated_item], "Wolayersee-Trip", "morning", stage_name="Etappe 1", tz=_TZ,
    )

    # E-Mail (Klartext): Tagesspitzenwort im Highlight-Satz.
    assert "gewitter hoch ab 08:00" in elevated_report.email_plain.lower(), (
        f"E-Mail-Klartext zeigt nach der Anhebung nicht 'gewitter hoch ab "
        f"08:00'. Ausschnitt: {elevated_report.email_plain[:400]!r}"
    )
    assert "gewitter hoch ab 08:00" not in baseline_report.email_plain.lower(), (
        "Vorbedingung verletzt: die baseline-E-Mail zeigt bereits 'hoch' -- "
        "der Test kann Anhebung nicht von Ausgangszustand unterscheiden"
    )

    # Telegram: Kurzuebersicht-Zeile "TH <stufe>".
    elevated_telegram = "\n".join(elevated_report.telegram_bubbles)
    baseline_telegram = "\n".join(baseline_report.telegram_bubbles)
    assert "TH hoch" in elevated_telegram, (
        f"Telegram-Bubbles zeigen nach der Anhebung kein 'TH hoch'. "
        f"Bubbles: {elevated_report.telegram_bubbles!r}"
    )
    assert "TH hoch" not in baseline_telegram, (
        "Vorbedingung verletzt: baseline-Telegram zeigt bereits 'TH hoch'"
    )

    # SMS (== Premium-SMS, D5: unveraendert weiterversendeter report.sms_text):
    # der Peak-Token traegt bei gemischten Stunden einen zusaetzlichen
    # "H@<stunde>"-Zusatz, den die durchgehend-MED-Baseline nicht hat.
    assert elevated_report.sms_text, "sms_text ist leer"
    assert "H@" in elevated_report.sms_text, (
        f"SMS-Text (== Premium-SMS-Text) muss nach der Anhebung 'H@' tragen, "
        f"war: {elevated_report.sms_text!r}"
    )
    assert "H@" not in baseline_report.sms_text, (
        f"Vorbedingung verletzt: baseline-SMS-Text traegt bereits 'H@': "
        f"{baseline_report.sms_text!r}"
    )


# ===========================================================================
# AC-11 + AC-12: Anker aus weather_data (letztes Segment), 1 Abruf/Aufruf
# ===========================================================================


def test_ac11_und_ac12_anker_auf_erster_etappe_und_genau_ein_abruf(monkeypatch, tmp_path):
    """GIVEN ein Trip mit 2 Etappen an DEUTLICH verschiedenen Koordinaten,
    aber `weather_data` enthaelt NUR ein Segment der ERSTEN Etappe / WHEN
    `_enrich_ensemble_for_trip` aufgerufen wird / THEN liegt die an den
    Ensemble-Abruf uebergebene Koordinate auf dem `end_point` des letzten
    Segments aus `weather_data` (Etappe 1), NICHT auf dem letzten Wegpunkt
    der GESAMTEN Tour (Etappe 2) -- UND es wird GENAU EIN Ensemble-Request
    abgesetzt (AC-12, Anker-Korrektur aendert die Koordinate, nicht die
    Aufrufzahl).

    RED heute: `_enrich_ensemble_for_trip` verwendet `trip.stages[-1]`
    (Etappe 2, weit entfernt) statt des letzten Segments aus `weather_data`.
    """
    from app.trip import Stage, Trip, Waypoint
    from urllib.parse import parse_qs

    # Etappe 1: Wolayersee (46.61/12.87). Etappe 2: deutlich entfernt (Wien).
    stage1 = Stage(
        id="s1", name="Etappe 1", date=date(2026, 9, 19),
        waypoints=[Waypoint(id="w1", name="Start", lat=46.61, lon=12.87, elevation_m=1950)],
    )
    stage2 = Stage(
        id="s2", name="Etappe 2", date=date(2026, 9, 20),
        waypoints=[Waypoint(id="w2", name="Wien", lat=48.21, lon=16.37, elevation_m=170)],
    )
    trip = Trip(id="anker-test", name="Anker-Test", stages=[stage1, stage2])

    seg1 = _make_segment(lat=46.61, lon=12.87)  # end_point = 46.66/12.92
    weather_data = [_weather_item([_dp(seg1.start_time, ThunderLevel.MED, ["cape"])], segment=seg1)]

    payload = _load_base_payload()
    seen: List[httpx.Request] = []

    from providers.openmeteo import OpenMeteoProvider

    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    replay_provider = OpenMeteoProvider()
    replay_provider._client = httpx.Client(transport=httpx.MockTransport(_handler(payload, seen)))

    monkeypatch.setattr("providers.base.get_provider", lambda name: replay_provider)

    svc = _make_scheduler()
    svc._enrich_ensemble_for_trip(trip=trip, weather_data=weather_data)

    ensemble_requests = [r for r in seen if "ensemble" in r.url.host]
    assert len(ensemble_requests) == 1, (
        f"AC-12: erwartet genau 1 Ensemble-Request je Aufruf, beobachtet "
        f"{len(ensemble_requests)}: {[r.url.host for r in seen]}"
    )

    query = parse_qs(ensemble_requests[0].url.query.decode())
    lat = float(query["latitude"][0])
    lon = float(query["longitude"][0])

    assert lat == pytest.approx(seg1.end_point.lat, abs=0.001), (
        f"AC-11: Anker muss auf dem end_point des letzten Segments aus "
        f"weather_data liegen (Etappe 1, lat={seg1.end_point.lat}), war lat={lat} "
        f"(Verdacht: Anker verwendet weiterhin trip.stages[-1] = Etappe 2/Wien)"
    )
    assert lon == pytest.approx(seg1.end_point.lon, abs=0.001)
    assert lat != pytest.approx(48.21, abs=0.5), (
        "Anker darf NICHT auf Etappe 2 (Wien) liegen"
    )


# ===========================================================================
# AC-13: Spread-Werte und compute_confidence_pct bleiben unveraendert
# ===========================================================================


def test_ac13_spread_werte_bit_identisch_zur_direkten_berechnung(monkeypatch, tmp_path):
    """GIVEN die bestehende Spread-Berechnung (stdev ueber ALLE
    `temperature_2m*`/`precipitation*`-Spalten, >=5 gueltige Werte) / WHEN
    `_fetch_ensemble_spread()` mit dem neuen Rueckgabetyp UND der neuen
    `weather_code`-Abfrage laeuft / THEN liefert sie fuer eine UNVERAENDERTE
    Fixture-Stunde exakt denselben `spread_t2m_k`/`spread_precip_mm` wie eine
    direkte `statistics.stdev()`-Berechnung ueber dieselben Spalten -- UND
    `compute_confidence_pct()` liefert fuer diesen Spread denselben Wert wie
    vor der Typumstellung.

    RED heute: der Rueckgabewert ist ein 2-Tupel ohne `.spread_t2m_k`-Attribut
    -> AttributeError.
    """
    from providers.openmeteo import compute_confidence_pct

    payload = _load_base_payload()  # UNVERAENDERT -- echte Aufzeichnung
    hour_index = 10
    hourly = payload["hourly"]

    temp_keys = [k for k in hourly.keys() if k.startswith("temperature_2m")]
    precip_keys = [k for k in hourly.keys() if k.startswith("precipitation")]
    temp_vals = [
        float(hourly[k][hour_index]) for k in temp_keys
        if hourly[k][hour_index] is not None
    ]
    precip_vals = [
        float(hourly[k][hour_index]) for k in precip_keys
        if hourly[k][hour_index] is not None
    ]
    expected_spread_t = statistics.stdev(temp_vals) if len(temp_vals) >= 5 else None
    expected_spread_p = statistics.stdev(precip_vals) if len(precip_vals) >= 5 else None
    assert expected_spread_t is not None and expected_spread_p is not None, (
        "Testvoraussetzung verletzt: zu wenige gueltige Werte in der Fixture-Stunde"
    )

    expected_ts = _ts_for_hour(payload, hour_index)
    provider, _seen = _provider_with_payload(payload, monkeypatch, tmp_path)
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    stats = result[expected_ts]
    assert stats.spread_t2m_k == pytest.approx(expected_spread_t), (
        f"spread_t2m_k weicht ab: {stats.spread_t2m_k} != {expected_spread_t}"
    )
    assert stats.spread_precip_mm == pytest.approx(expected_spread_p), (
        f"spread_precip_mm weicht ab: {stats.spread_precip_mm} != {expected_spread_p}"
    )

    lead_h = 12.0
    expected_conf = compute_confidence_pct(expected_spread_t, expected_spread_p, lead_h)
    actual_conf = compute_confidence_pct(stats.spread_t2m_k, stats.spread_precip_mm, lead_h)
    assert actual_conf == expected_conf, (
        "compute_confidence_pct() muss fuer identischen Spread-Input bit-"
        f"identisch bleiben: {actual_conf} != {expected_conf}"
    )
