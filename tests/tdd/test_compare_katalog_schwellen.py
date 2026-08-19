"""TDD RED — Issue #1377 Scheibe B, Lieferung B2 (Ortsvergleichs-Matrix).

Scheibe A (`dbbb30fb`) hat den zentralen Metrik-Katalog zur alleinigen Quelle
aller Warnschwellen gemacht, Scheibe B1 (`506c25f4`) hat die Trip-Renderer
(html.py/outlook.py/helpers.py) darauf umgestellt. Diese Datei zeigt, dass
die Vergleichsmatrix (`compare_html._sev_*`) noch nicht ueberall denselben
Katalog liest -- `_sev_wind`/`_sev_cape` sind bereits migriert (Vorlage),
`_sev_temp`/`_sev_rain`/`_sev_uv`/`_sev_pop`/`_sev_visibility` fuehren noch
eigene, vom Katalog abweichende Schwellen.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz.
Echte Funktionsaufrufe + ein echter `render_compare_html`-Durchlauf mit
echten ForecastDataPoint/LocationResult/ComparisonResult-Objekten. Kein
Dateiinhalt-Check.

SPEC: docs/specs/modules/ampel_schwellen_renderer.md AC-1 (Vergleichs-Teil),
AC-3 (Vergleichs-Teil), AC-4 (Vergleichs-Teil), AC-5 (Vergleichs-Zell-Teil),
AC-7 (Vergleichs-Teil)
KONTEXT: docs/context/fix-1377-scheibe-b.md

NICHT Teil dieser Datei (B1, bereits gruen in `506c25f4`): `html.py`,
`outlook.py`, `helpers.py`, AC-9 (Golden-Regenerierung, erst nach B2
vollstaendig).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.metric_catalog import get_metric
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    ThunderLevel,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.metric_format import severity_for
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.email.compare_html import (
    CV2_METRICS, HOUR_METRICS, _sev_gust, _sev_pop, _sev_rain, _sev_temp,
    _sev_thunder, _sev_uv, _sev_visibility, render_compare_html,
)
from services.weather_metrics import WeatherMetricsService

TARGET_DATE = date(2026, 7, 8)
_TAGS = re.compile(r"<[^>]+>")

# Kanonisches Vokabular (severity_for) -> Compare-lokales Vokabular. Lokal
# hier definiert statt aus `compare_html._CANONICAL_TO_COMPARE` importiert --
# die Spec sieht das Loeschen dieses internen Dicts in B2 ausdruecklich vor
# (Implementation Details Punkt 4), unsere Erwartungs-Grundlage darf davon
# nicht abhaengen.
_LEVEL_TO_COMPARE = {"green": "ok", "yellow": "caution", "orange": "warn", "red": "danger"}


# ===========================================================================
# Full-Matrix-Renderpfad (Vorlage: test_compare_cape_severity_ampel.py)
# ===========================================================================

def _dp(hour: int, **overrides) -> ForecastDataPoint:
    base = dict(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, wind_direction_deg=270, gust_kmh=15.0,
        precip_1h_mm=0.0, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        pop_pct=10, humidity_pct=55, uv_index=3.0, visibility_m=20000,
        wind_chill_c=14.0, cape_jkg=100.0, freezing_level_m=2500,
    )
    base.update(overrides)
    return ForecastDataPoint(**base)


def _hourly(**overrides) -> list[ForecastDataPoint]:
    return [_dp(h, **overrides) for h in range(9, 18)]


def _timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    return NormalizedTimeseries(meta=meta, data=hourly)


def _location(name: str, **overrides) -> LocationResult:
    hourly = _hourly(**overrides)
    s = WeatherMetricsService().compute_basis_metrics(_timeseries(hourly), tz=None)
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=39.76, lon=2.71, elevation_m=200),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c,
        wind_max=s.wind_max_kmh, gust_max=s.gust_max_kmh,
        cloud_avg=s.cloud_avg_pct, sunny_hours=4,
        hourly_data=hourly,
    )


def _result(**overrides) -> ComparisonResult:
    return ComparisonResult(
        locations=[_location("Andermatt", **overrides)],
        time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


def _overview_row_html(html: str, label_substr: str) -> str:
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        label_match = re.search(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        if not label_match:
            continue
        label = _TAGS.sub("", label_match.group(1)).strip()
        if label_substr.lower() in label.lower():
            return row_html
    raise AssertionError(f"Keine {label_substr!r}-Zeile in der Uebersichts-Matrix gefunden:\n{html}")


# ===========================================================================
# Migrations-Tests je Groesse: heutiger Wert vs. Katalog-Wert
# ===========================================================================

def test_sev_pop_35_pct_becomes_caution():
    """Given 35% Regenwahrscheinlichkeit / When `_sev_pop` ausgewertet wird /
    Then 'caution' (Katalog-Schwelle 30/60/80) -- heute 'ok' (eigene
    Schwelle ab 40%)."""
    expected = severity_for("rain_probability", 35.0)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 35% 'yellow'"
    result = _sev_pop(35.0)
    assert result == "caution", (
        f"_sev_pop(35.0) liefert {result!r}, erwartet 'caution' (Katalog-"
        f"Schwelle ab 30%). Heutige hartcodierte Schwelle (>=40%) liefert 'ok'."
    )


def test_sev_rain_4_5mm_becomes_caution():
    """Given 4,5 mm Regen / When `_sev_rain` ausgewertet wird / Then
    'caution' (Katalog-Schwelle 1/5/10 mm) -- heute 'warn' (eigene Schwelle
    >4 mm)."""
    expected = severity_for("precipitation", 4.5)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 4,5mm 'yellow'"
    result = _sev_rain(4.5)
    assert result == "caution", (
        f"_sev_rain(4.5) liefert {result!r}, erwartet 'caution' (Katalog-"
        f"Schwelle 1/5/10mm). Heutige hartcodierte Schwelle (>4mm) liefert 'warn'."
    )


def test_sev_visibility_1500m_becomes_caution():
    """AC-4 (Vergleichs-Teil, Spec-Wert): Given 1500 m Sicht / When
    `_sev_visibility` ausgewertet wird / Then 'caution' (Katalog-Schwelle
    <2000/<1000/<500m) -- heute 'warn' (eigene Schwelle <3000m). Die
    Trip-Zelle (B1, bereits gruen) zeigt fuer denselben Wert bereits 'yellow'
    -- dies ist der noch fehlende Vergleichsmatrix-Teil von AC-4."""
    expected = severity_for("visibility", 1500.0)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 1500m 'yellow'"
    result = _sev_visibility(1500.0)
    assert result == "caution", (
        f"_sev_visibility(1500.0) liefert {result!r}, erwartet 'caution' "
        f"(Katalog-Schwelle <2000m). Heutige hartcodierte Schwelle (<3000m) "
        f"liefert 'warn'. Damit stimmt AC-4 zwischen Trip-Zelle ('yellow', "
        f"B1 bereits gruen) und Vergleichsmatrix noch nicht ueberein."
    )


def test_sev_visibility_4000m_becomes_ok():
    """Groesste Abweichung (Kontext-Vorgabe): Given 4000 m Sicht / When
    `_sev_visibility` ausgewertet wird / Then 'ok' (Katalog-Schwelle greift
    erst unter 2000m) -- heute 'caution' (eigene Schwelle <5000m)."""
    expected = severity_for("visibility", 4000.0)
    assert expected == "green", "Erwartungs-Grundlage: Katalog liefert fuer 4000m 'green'"
    result = _sev_visibility(4000.0)
    assert result == "ok", (
        f"_sev_visibility(4000.0) liefert {result!r}, erwartet 'ok' (Katalog "
        f"faerbt erst unter 2000m). Heutige hartcodierte Schwelle (<5000m) "
        f"liefert 'caution'."
    )


def test_sev_gust_exact_30_becomes_caution():
    """ABWEICHUNG von der Spec-Behauptung 'Werte bereits deckungsgleich' --
    die ZAHLEN (30/45/60) stimmen, aber die GRENZ-INKLUSIVITAET nicht: heutige
    `_sev_gust` prueft exklusiv `> 30`, der Katalog (via `severity_for`,
    `>=`) faerbt bereits AB 30. Given genau 30 km/h Boeen / When `_sev_gust`
    ausgewertet wird / Then 'caution' -- heute 'ok'."""
    expected = severity_for("gust", 30.0)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer genau 30 km/h 'yellow'"
    result = _sev_gust(30.0)
    assert result == "caution", (
        f"_sev_gust(30.0) liefert {result!r}, erwartet 'caution' (Katalog "
        f"wertet ab EINSCHLIESSLICH 30 km/h). Heutige hartcodierte Schwelle "
        f"ist EXKLUSIV (>30) und laesst genau 30 km/h noch als 'ok' durch. "
        f"Die Spec (Implementation Details Punkt 4) behauptet '_sev_gust "
        f"bleibt unveraendert (Werte bereits deckungsgleich zum Katalog)' -- "
        f"das gilt nur fuer die drei Zahlenwerte, nicht fuer die Grenz-"
        f"Inklusivitaet an der Schwelle selbst."
    )


def test_sev_temp_cold_minus6c_becomes_warn():
    """Given -6 Grad (Kaelte-Seite, im Katalog neu: 0/-5/-15) / When
    `_sev_temp` ausgewertet wird / Then 'warn' (orange) -- heute 'ok', weil
    `_sev_temp` bislang ausschliesslich die Hitze-Seite (>=28/31/34) kennt
    und keine Kaelte-Seite hat."""
    expected = severity_for("temperature", -6.0)
    assert expected == "orange", "Erwartungs-Grundlage: Katalog liefert fuer -6 Grad 'orange' (Kaelte-Seite)"
    result = _sev_temp(-6.0)
    assert result == "warn", (
        f"_sev_temp(-6.0) liefert {result!r}, erwartet 'warn' (Katalog-"
        f"Kaelteschwelle orange_lt=-5 Grad). Heutige `_sev_temp` kennt keine "
        f"Kaelte-Seite und liefert 'ok'."
    )


def test_sev_temp_hot_32c_already_matches_catalog():
    """Regressionsschutz -- bereits GRUEN: die Hitze-Seite von `_sev_temp`
    (>=28/31/34) ist bereits identisch zum Katalog; AC-5 nennt 32 Grad, aber
    dieser Wert war schon vor B2 korrekt ('warn'). Nur die Kaelte-Seite
    (s.o.) ist der tatsaechliche B2-Migrationsfall fuer diese Funktion."""
    expected = severity_for("temperature", 32.0)
    assert expected == "orange"
    assert _sev_temp(32.0) == "warn"


def test_sev_uv_regression_already_matches_catalog():
    """Regressionsschutz -- bereits GRUEN: `_sev_uv` (>=3/6/8) ist bereits
    deckungsgleich zum Katalog (3/6/8). Bleibt nach B2 unveraendert korrekt."""
    for value, expected_canonical, expected_compare in [
        (2.5, "green", "ok"), (3.0, "yellow", "caution"),
        (6.5, "orange", "warn"), (8.0, "red", "danger"),
    ]:
        assert severity_for("uv_index", value) == expected_canonical
        assert _sev_uv(value) == expected_compare, (
            f"_sev_uv({value}) liefert {_sev_uv(value)!r}, erwartet "
            f"{expected_compare!r} -- Regression, war schon vor B2 korrekt."
        )


def test_sev_thunder_regression_unchanged():
    """AC-7 (Regressionsschutz, Vergleichs-Teil): Gewitter ist ausdruecklich
    NICHT Teil der Umstellung (kein `display_thresholds` im Katalog fuer
    `thunder`). `_sev_thunder` bleibt unveraendert bei seinem eigenen
    MED/HIGH-Vokabular."""
    assert _sev_thunder(ThunderLevel.HIGH) == "danger"
    assert _sev_thunder(ThunderLevel.MED) == "warn"
    assert _sev_thunder(ThunderLevel.NONE) is None
    assert get_metric("thunder").display_thresholds == {}, (
        "Erwartungs-Grundlage: Katalog fuehrt fuer 'thunder' keine Schwellen -- "
        "Gewitter bleibt bewusst aussen vor (Known Limitations)."
    )


# ===========================================================================
# "Verbotenes Muster" (Kontext-Vorgabe): fehlende SCHWELLEN duerfen in der
# Vergleichsmatrix nie als "ok" erscheinen. Regressionsschutz -- bereits
# GRUEN: kein registrierter "sev"-Eintrag zeigt heute auf eine Groesse ohne
# Katalog-Schwellen. Der Test sichert genau das fuer die Zukunft ab, damit
# eine neue "sev"-Zuordnung nicht versehentlich das Muster
# `_CANONICAL_TO_COMPARE.get(severity_for(...), "ok")` auf eine schwellenlose
# Groesse anwendet (das wuerde "keine Aussage" in ein stilles Gruen
# uebersetzen).
# ===========================================================================

def test_no_sev_wired_to_metric_without_catalog_thresholds():
    for registry_name, registry in [("CV2_METRICS", CV2_METRICS), ("HOUR_METRICS", HOUR_METRICS)]:
        for row in registry:
            sev_fn = row.get("sev")
            metric_id = row.get("metric_id")
            if sev_fn is None or metric_id is None or metric_id == "thunder":
                continue
            thresholds = get_metric(metric_id).display_thresholds
            assert thresholds, (
                f"{registry_name} Zeile key={row['key']!r} hat eine 'sev'-"
                f"Funktion fuer metric_id={metric_id!r}, aber der Katalog "
                f"fuehrt dafuer KEINE display_thresholds. Das verbotene "
                f"Muster '_CANONICAL_TO_COMPARE.get(severity_for(...), "
                f"\"ok\")' wuerde eine fehlende Aussage in ein stilles 'ok' "
                f"(Gruen) uebersetzen statt keine Faerbung zu zeigen."
            )


# ===========================================================================
# Kern des Issues: gleiche Vorhersage -> gleiche Stufe in Trip UND Vergleich
# ===========================================================================

def test_kern_pop_35_pct_full_matrix_render_shows_yellow_not_green():
    """Kern des Issues: Given 35% Regenwahrscheinlichkeit (Trip-Zelle zeigt
    dafuer bereits 'yellow', B1) / When die Uebersichts-Matrix gerendert
    wird / Then ist die 'Regenwahrscheinlichkeit'-Zeile ebenfalls gelb
    getoent (background:#fdf4cd, Fix #1801 S2) -- heute bleibt sie ungetoent
    (transparent), weil die eigene Compare-Schwelle (ab 40%) 35% nicht
    erfasst."""
    result = _result(pop_pct=35)
    enabled = resolve_enabled_metrics(["pop_max_pct"])
    html = render_compare_html(result, enabled_metrics=enabled)
    row_html = _overview_row_html(html, "Regenwahrscheinlichkeit")

    assert "#fdf4cd" in row_html, (
        f"Regenwahrscheinlichkeits-Zeile zeigt fuer 35% (Katalog-Schwelle "
        f"ab 30%, sollte 'yellow'/background:#fdf4cd sein) keine Ampel-"
        f"Faerbung -- heutige Schwelle (ab 40%) laesst 35% ungefaerbt: "
        f"{row_html}"
    )


def test_kern_visibility_4000m_full_matrix_render_shows_no_tint():
    """Kern des Issues (Gegenrichtung): Given 4000 m Sicht / When die
    Uebersichts-Matrix gerendert wird / Then bleibt die 'Sicht min'-Zeile
    UNGEFAERBT (Katalog faerbt erst unter 2000m) -- heute zeigt sie gelb
    (background:#fbeeb8, eigene Schwelle <5000m)."""
    result = _result(visibility_m=4000)
    enabled = resolve_enabled_metrics(["visibility_min_m"])
    html = render_compare_html(result, enabled_metrics=enabled)
    row_html = _overview_row_html(html, "Sichtweite")

    assert "#fbeeb8" not in row_html and "#fad6b8" not in row_html and "#f6c5bf" not in row_html, (
        f"'Sicht min'-Zeile zeigt fuer 4000m noch eine Ampel-Faerbung, "
        f"erwartet KEINE (Katalog faerbt erst unter 2000m): {row_html}"
    )
