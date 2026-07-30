"""TDD RED -- Compare-SMS bedient die volle Metrik-Auswahl kuerzelgekuerzt
(Scheibe S5b, #1362/#1399).

Spec: docs/specs/modules/compare_kanal_metriken.md -- AC-3, AC-4 (SMS-Teil),
AC-5 (SMS-Teil), AC-7 (SMS-Teil), AC-8. Der Telegram-Teil dieser ACs steckt
bereits (committet) in tests/tdd/test_compare_kanal_metriken.py (Scheibe S5a)
-- diese Datei ist deren SMS-Pendant, keine Kopie.

Ist-Zustand (comparison.py:389-391, 461-482, 686-723):
- `_SMS_METRICS_PER_LOCATION = 2` kappt die SMS-Zellen je Ort HART auf zwei,
  unabhaengig vom tatsaechlichen 140-Zeichen-Budget und unabhaengig von der
  Groesse der Nutzerauswahl.
- `_channel_metric_cells()` filtert ausserdem ueber die Schnittmenge mit der
  festen Sechserliste `_CHANNEL_METRICS` -- jede Groesse ausserhalb davon
  verschwindet unabhaengig von Reihenfolge/Auswahlgroesse komplett.
- Zellen tragen die Telegram-Vollform-Bezeichnung ("Temp 16°C"), nicht das
  Katalog-Kuerzel ("D 16°C").
- 10 der 24 zugrundeliegenden Katalog-Groessen fuehren noch kein `sms_code`
  (AC-8).

Test-Politik (CLAUDE.md, Schicht "Kern"): rein deterministisch, KEINE Mocks
(kein Mock()/patch()/MagicMock), kein Netz, kein Versand. Alle Pruefungen
lesen den GERENDERTEN SMS-Text (Nutzersicht), nicht den Code-Pfad. Werte/
Kuerzel werden ueber dieselben Produktions-Bausteine berechnet, die die Spec
fuer die Implementierung vorschreibt (`get_sms_code`, `_metric_value`,
`_PLAIN_ROWS`) -- keine zweite, im Test erfundene Formatierungsquelle.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.metric_catalog import get_sms_code
from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.metric_format import format_value
from output.renderers.channel_layout import CHANNEL_LIMITS
from output.renderers.comparison import (
    _PLAIN_ROWS_BY_ID, _sms_aggregation_sign, _sms_gsm7_safe, render_compare_sms,
)
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.compare_html import _metric_value

TARGET_DATE = date(2026, 7, 27)
CREATED_AT = datetime(2026, 7, 27, 8, 0)
# Issue #1362 S5b, Adversary-Fund Runde 5 (PO-Entscheidung 2026-07-30): das
# SMS-Zeichenbudget ist von 140 (Byte-Grenze, verwechselt mit Zeichengrenze)
# auf 153 (verkettungssicherer GSM-7-Wert) gestiegen -- gegen die KONSTANTE
# pruefen, nicht gegen den alten Literalwert 140 (sonst faellt genau diese
# Anhebung unbemerkt durch, s. test_compare_sms_gsm7_charset.py::
# test_sms_char_budget_matches_gsm7_concatenated_derivation fuer die Herleitung).
SMS_LIMIT = CHANNEL_LIMITS["sms"]["max_chars"]

# ---------------------------------------------------------------------------
# Renderer-ID (Compare-Vokabular, wie in enabled_metrics) -> zentrale
# Katalog-Metrik-ID (wie von get_sms_code() erwartet). Abgeleitet aus den
# ZWEI bestehenden Uebersetzungstabellen -- KEIN sechstes, im Test
# hand-getipptes Vokabular (analog compare_metric_catalog.py Kopfkommentar
# "Vier inkompatible Metrik-Vokabulare"). Bricht laut, wenn eine der beiden
# Quelltabellen jemals eine Compare-ID entfernt, auf die sich diese Datei
# stuetzt.
# ---------------------------------------------------------------------------
_METRIC_ID_BY_FRONTEND_KEY = {
    entry["key"]: entry["metric_id"] for entry in COMPARE_METRIC_CATALOG
}
RENDERER_TO_METRIC_ID: dict[str, str] = {
    renderer_id: _METRIC_ID_BY_FRONTEND_KEY[frontend_key]
    for frontend_key, renderer_id in FRONTEND_TO_RENDERER_METRIC_ID.items()
}
ALL_26_RENDERER_IDS = tuple(RENDERER_TO_METRIC_ID)
assert len(ALL_26_RENDERER_IDS) == 26, (
    f"Erwartet 26 Compare-Renderer-IDs (Spec: '26 Compare-Groessen'), "
    f"gefunden {len(ALL_26_RENDERER_IDS)} -- Testgrundlage fuer AC-8 pruefen "
    "(compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID / "
    "compare_metric_catalog.COMPARE_METRIC_CATALOG)."
)


def _loc(loc_id: str, name: str, *, lat: float = 47.0, lon: float = 11.0) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=600)


def _daily_points(
    *, dewpoint_c: float | None = None, pressure_msl_hpa: float | None = None,
    humidity_pct: int | None = None, cape_jkg: float | None = None,
    freezing_level_m: int | None = None, snowfall_limit_m: int | None = None,
) -> list[ForecastDataPoint]:
    """24 Stundenpunkte mit neutralen Basiswerten -- Traeger fuer die
    Klasse-B-Aggregate (Luftfeuchtigkeit/Taupunkt/Luftdruck/CAPE/Nullgrad-
    grenze/Schneefallgrenze), die `_metric_value()` NUR live aus
    `hourly_data` ableitet (kein direktes `LocationResult`-Feld dafuer,
    analog `test_compare_kanal_metriken.py::_daily_points`)."""
    points = []
    for hour in range(24):
        points.append(ForecastDataPoint(
            ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
            t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=15.0, precip_1h_mm=0.0,
            cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
            visibility_m=10000, dewpoint_c=dewpoint_c,
            pressure_msl_hpa=pressure_msl_hpa, humidity_pct=humidity_pct,
            cape_jkg=cape_jkg, freezing_level_m=freezing_level_m,
            snowfall_limit_m=snowfall_limit_m,
        ))
    return points


def _result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations, time_window=(0, 23), target_date=TARGET_DATE,
        created_at=CREATED_AT,
    )


def _sms_cell_text(loc_result: LocationResult, renderer_id: str) -> str | None:
    """Erwartete SMS-Zelle ("Kuerzel[+/-] Wert") fuer `renderer_id`, berechnet
    ueber DIESELBEN Bausteine, die die Spec (Implementation Details Punkt 3)
    fuer die Implementierung vorschreibt: `get_sms_code()` fuer das Kuerzel,
    `_PLAIN_ROWS`/`_metric_value` fuer Wert+Formatierung (identisch zum
    Klartext-Teil derselben Mail -- keine zweite Werte-/Formatierungsquelle).
    Das Auswertungszeichen (Adversary-Fund Runde 3, PO-Entscheidung
    2026-07-29: `+`/`-` bei Groessen mit mehr als einer Auswertung im
    Ortsvergleich, z.B. `temp_max`/`temp_min`) kommt ueber die PRODUKTIONS-
    Funktion `_sms_aggregation_sign`. Der Wert wird ueber die PRODUKTIONS-
    Funktion `_sms_gsm7_safe` GSM-7-saniert (Adversary-Fund Runde 4,
    PO-Entscheidung 2026-07-30: kein Grad-Zeichen im SMS-Pfad) -- kein
    zweites, im Test erratenes Zeichen-/Sanitierungs-Vokabular. `None` = kein
    Wert ODER kein Kuerzel vorhanden (Zelle entfaellt)."""
    metric_id = RENDERER_TO_METRIC_ID[renderer_id]
    code = get_sms_code(metric_id)
    if not code:
        return None
    _, _label, fmt = _PLAIN_ROWS_BY_ID[renderer_id]
    value = _metric_value(loc_result, renderer_id)
    if value is None:
        return None
    sign = _sms_aggregation_sign(renderer_id)
    return f"{code}{sign} {_sms_gsm7_safe(fmt(value))}"


def _location_part(sms: str, name: str) -> str:
    """Teiltext EINES Ortes innerhalb der flachen, Semikolon-getrennten
    Compare-SMS -- bis zum naechsten '; ' bzw. Stringende (analog
    tests/tdd/test_compare_sms_official_alerts.py::_location_part)."""
    idx = sms.index(name)
    rest = sms[idx:]
    end = rest.find("; ")
    return rest if end == -1 else rest[:end]


def _valid_prefix_candidates(name: str, cells: list[str]) -> set[str]:
    """Jede STRUKTURELL gueltige Auspraegung des Ortsteils: der Ortsname,
    gefolgt von einem PRAEFIX der Zellenliste (0..alle Zellen, in Reihenfolge,
    ohne Luecke -- ganze Zellen, nie ein Teil-Kuerzel/-Wert), optional gefolgt
    von einem `+N`-Ueberlaufhinweis, wobei N EXAKT die Zahl der nicht mehr
    gezeigten Zellen ist (Spec Implementation Details Punkt 3: `"Andermatt D
    16°C W 15km/h +2"`). Jede andere Auspraegung (abgeschnittenes Kuerzel/
    Wert, uebersprungene Zelle, falsche Zaehlung) ist ungueltig.

    Bewusst OHNE Annahme ueber den internen Zeichen-Budget-Grenzwert von
    `_sms_location_part` -- das ist Implementierungsdetail (die "Naht"), die
    Pruefung ist strukturell und budget-agnostisch."""
    candidates = {name}
    running = name
    for i, cell in enumerate(cells):
        running = f"{running} {cell}"
        candidates.add(running)
        remaining = len(cells) - (i + 1)
        if remaining > 0:
            candidates.add(f"{running} +{remaining}")
    if cells:
        candidates.add(f"{name} +{len(cells)}")
    return candidates


# ---------------------------------------------------------------------------
# AC-3 -- SMS bleibt unter 140 Zeichen, kuerzt nie mitten in Kuerzel/Wert
# ---------------------------------------------------------------------------

def test_sms_cuts_whole_metrics_not_mid_token_when_selection_exceeds_budget():
    """AC-3: eine grosse Metrik-Auswahl (16 Groessen, die HEUTE bereits ein
    Katalog-Kuerzel haben -- die 10 AC-8-Fund-Luecken bewusst aussen vor, um
    AC-3 unabhaengig von AC-8 zu pruefen) fuer EINEN Ort ergibt zusammen mit
    dem Ortsnamen weit mehr als das SMS_LIMIT-Budget der ganzen SMS. Erwartet:
    die SMS bleibt <=SMS_LIMIT Zeichen UND der Ortsteil ist irgendein
    STRUKTURELL gueltiger Praefix der Zellenliste (s.
    `_valid_prefix_candidates`).

    Ist-Zustand: `_SMS_METRICS_PER_LOCATION = 2` kappt hart auf zwei Zellen,
    unabhaengig vom Zeichenbudget, UND die Zellen tragen noch die alte
    Telegram-Vollform-Bezeichnung statt des Katalog-Kuerzels -- der Ortsteil
    matcht deshalb heute KEINEN der konstruierten Kandidaten."""
    # Etwas laengerer Ortsname (statt "Andermatt") -- reine Budget-Reserve,
    # damit die volle, ungekuerzte Darstellung sicher > SMS_LIMIT Zeichen
    # ergibt (s. Testaufbau-Guard unten). Adversary-Fund Runde 5 (PO-
    # Entscheidung 2026-07-30): SMS_LIMIT stieg von 140 auf 153 -- die
    # urspruenglichen 14 Groessen reichten dafuer nicht mehr (145 Zeichen,
    # unter dem neuen Budget), deshalb zwei weitere (dewpoint_avg,
    # pressure_avg) ergaenzt.
    name = "Andermatt Talstation"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=16.4, wind_max=15.0, gust_max=20.0, snow_depth_cm=20.0,
        snow_new_cm=4.0, precip_sum_mm=5.0, pop_max_pct=30,
        thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
        uv_index_max=5.0,
        hourly_data=_daily_points(
            humidity_pct=70, cape_jkg=1500.0, freezing_level_m=1200,
            snowfall_limit_m=1300, dewpoint_c=8.0, pressure_msl_hpa=1013.0,
        ),
    )
    enabled = [
        "temp_max", "wind_max", "gust_max", "precip_sum", "pop_max",
        "thunder_max", "visibility_min", "uv_max", "snow_depth_cm",
        "snow_new_cm", "humidity_avg", "cape_max", "freezing_level",
        "snowfall_limit", "dewpoint_avg", "pressure_avg",
    ]
    cells = [c for c in (_sms_cell_text(loc, mid) for mid in enabled) if c is not None]
    assert len(cells) == len(enabled), (
        f"Testaufbau defekt: erwartet einen Wert fuer alle {len(enabled)} "
        f"gewaehlten Groessen, erhalten {len(cells)} Zellen ({cells!r}) -- "
        "Fixture pruefen (fehlt ein sms_code oder ein Wert?)."
    )
    full_length_estimate = len(name) + sum(len(c) + 1 for c in cells)
    assert full_length_estimate > SMS_LIMIT, (
        f"Testaufbau defekt: die volle, ungekuerzte Darstellung waere nur "
        f"{full_length_estimate} Zeichen lang -- das erzwingt keinen "
        "Ueberlauf. Mehr/laengere Groessen waehlen, damit AC-3 echt greift."
    )

    sms = render_compare_sms(_result([loc]), enabled_metrics=enabled)

    assert len(sms) <= SMS_LIMIT, (
        f"Compare-SMS ueberschreitet das {SMS_LIMIT}-Zeichen-Budget: "
        f"{len(sms)} Zeichen ({sms!r})."
    )
    part = _location_part(sms, name)
    candidates = _valid_prefix_candidates(name, cells)
    assert part in candidates, (
        f"Ortsteil {part!r} ist kein gueltiger Praefix der erwarteten "
        f"Kuerzel-Zellenliste {cells!r} (mit optionalem korrektem "
        "`+N`-Ueberlaufhinweis) -- entweder wurde mitten in einem Kuerzel/"
        "Wert geschnitten, eine Zelle uebersprungen, oder es wird noch die "
        "alte Telegram-Vollform statt des Katalog-Kuerzels verwendet "
        "(Ist-Zustand: `_SMS_METRICS_PER_LOCATION = 2` kappt hart auf 2 "
        f"Zellen mit Vollform-Labels). Ganze SMS: {sms!r}"
    )


# ---------------------------------------------------------------------------
# Adversary-Fund (QA-Runde 2, #1362 S5b): Metrik-Ueberlauf (je Ortsblock,
# neu) und Orts-Ueberlauf (Nachrichtenende, bestehend seit #1269) treffen
# zusammen -- beide Zahlen muessen zuordenbar bleiben.
# ---------------------------------------------------------------------------

def test_metric_overflow_and_location_overflow_are_both_present_and_distinguishable():
    """Adversary-Fund: trifft der neue Metrik-Ueberlauf (`+N` im Ortsblock,
    Zellen ohne Wortzusatz -- aus dem Zusammenhang lesbar) auf den
    bestehenden Orts-Ueberlauf (`+k` am Nachrichtenende, #1269), ergibt
    `"...+3 +4"` zwei Zahlen ohne erkennbaren Bezug. Der Orts-Ueberlauf
    traegt deshalb den Wortzusatz " Orte"; der Metrik-Ueberlauf bleibt ohne.

    Fixture: zwei Orte mit einer grossen 14-Groessen-Auswahl (Vorlaeufer der
    AC-3-Auswahl, absichtlich VOR deren Runde-5-Erweiterung eingefroren --
    diese Kombination braucht bereits bei 14 Groessen beide Ueberlaeufe
    gleichzeitig, s. Testaufbau-Guard unten) -- der erste Ortsteil allein
    braucht bereits Metrik-Kuerzung, UND der zweite Ort passt daneben nicht
    mehr ins SMS_LIMIT-Zeichen-Budget (Orts-Ueberlauf). Zusaetzliche
    Regressionsschutz-Absicherung (Runde-2-Fund):
    OHNE Budget-Reserve fuer den Orts-Ueberlauf-Hinweis wurde der bereits
    sauber gekuerzte erste Ortsteil verworfen und stattdessen per
    Wortgrenzen-Kuerzung MITTEN in einer Kuerzel/Wert-Zelle abgeschnitten
    (z.B. `"...HU... +1 Orte"`) -- das darf nicht mehr vorkommen."""
    name_a = "Andermatt Talstation"
    name_b = "Zermatt"
    loc_a = LocationResult(
        location=_loc("a", name_a),
        temp_max=16.4, wind_max=15.0, gust_max=20.0, snow_depth_cm=20.0,
        snow_new_cm=4.0, precip_sum_mm=5.0, pop_max_pct=30,
        thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
        uv_index_max=5.0,
        hourly_data=_daily_points(
            humidity_pct=70, cape_jkg=1500.0, freezing_level_m=1200,
            snowfall_limit_m=1300,
        ),
    )
    loc_b = LocationResult(
        location=_loc("b", name_b),
        temp_max=16.4, wind_max=15.0, gust_max=20.0, snow_depth_cm=20.0,
        snow_new_cm=4.0, precip_sum_mm=5.0, pop_max_pct=30,
        thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
        uv_index_max=5.0,
        hourly_data=_daily_points(
            humidity_pct=70, cape_jkg=1500.0, freezing_level_m=1200,
            snowfall_limit_m=1300,
        ),
    )
    enabled = [
        "temp_max", "wind_max", "gust_max", "precip_sum", "pop_max",
        "thunder_max", "visibility_min", "uv_max", "snow_depth_cm",
        "snow_new_cm", "humidity_avg", "cape_max", "freezing_level",
        "snowfall_limit",
    ]
    cells = [c for c in (_sms_cell_text(loc_a, mid) for mid in enabled) if c is not None]
    assert len(cells) == len(enabled), "Testaufbau defekt (s. AC-3-Zwilling)"

    sms = render_compare_sms(_result([loc_a, loc_b]), enabled_metrics=enabled)

    assert len(sms) <= SMS_LIMIT, (
        f"SMS-Budget verletzt: {len(sms)} Zeichen ({sms!r})."
    )

    # Der zweite Ort muss vollstaendig entfallen sein -- sonst greift dieser
    # Test den Doppel-Ueberlauf-Fall nicht (Testaufbau-Guard).
    assert name_b not in sms, (
        f"Testaufbau defekt: {name_b!r} erscheint noch in der SMS -- kein "
        f"Orts-Ueberlauf ausgeloest. SMS: {sms!r}"
    )

    # Orts-Ueberlauf: EIN Ort entfallen, mit Wortzusatz "Orte" am Nachrichtenende.
    location_overflow = re.search(r" \+(\d+) Orte$", sms)
    assert location_overflow is not None, (
        f"Kein wortbasierter Orts-Ueberlauf-Hinweis (' +k Orte') am "
        f"Nachrichtenende gefunden: {sms!r}"
    )
    assert int(location_overflow.group(1)) == 1, (
        f"Orts-Ueberlauf muss genau 1 (Zermatt) zaehlen, war "
        f"{location_overflow.group(1)}: {sms!r}"
    )

    # Metrik-Ueberlauf: der ERSTE (einzige gezeigte) Ortsteil ist ein
    # gueltiger, nie mitten im Kuerzel/Wert geschnittener Praefix der
    # Zellenliste (identischer Nachweis wie AC-3) -- OHNE den Orts-Ueberlauf-
    # Zusatz, der separat am Nachrichtenende steht (deshalb bis
    # `location_overflow.start()` geschnitten, nicht bis Stringende).
    name_a_idx = sms.index(name_a)
    part = sms[name_a_idx:location_overflow.start()]
    candidates = _valid_prefix_candidates(name_a, cells)
    assert part in candidates, (
        f"Ortsteil {part!r} (nach Abzug des Orts-Ueberlauf-Zusatzes) ist "
        f"kein gueltiger Praefix der Zellenliste {cells!r} -- Metrik-Kuerzung "
        f"und Orts-Ueberlauf-Hinweis sind nicht sauber getrennt. Ganze SMS: {sms!r}"
    )
    # Die zwei Zahlen muessen unterscheidbar sein: der Metrik-Ueberlauf im
    # ersten Ortsteil traegt KEIN "Orte" (sonst waeren beide ununterscheidbar).
    assert not part.endswith("Orte"), (
        f"Metrik-Ueberlauf im Ortsteil {part!r} traegt faelschlich den "
        "Orts-Ueberlauf-Wortzusatz -- beide Zaehler waeren dann nicht mehr "
        f"unterscheidbar. Ganze SMS: {sms!r}"
    )
    # Testaufbau-Guard (robust gegen kuenftige SMS_LIMIT-Aenderungen, s.
    # Adversary-Fund Runde 5): der Metrik-Ueberlauf selbst MUSS auftreten --
    # sonst prueft dieser Test nur noch den Orts-Ueberlauf allein, nicht mehr
    # das Zusammentreffen beider Zaehler.
    assert re.search(r" \+\d+$", part), (
        f"Testaufbau defekt: Ortsteil {part!r} zeigt keinen Metrik-Ueberlauf "
        "mehr -- die Fixture braucht mehr/laengere Groessen, damit dieser "
        f"Test beide Ueberlaeufe gleichzeitig pruefen kann. Ganze SMS: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 (SMS-Teil) -- Nutzer-Reihenfolge wirkt
# ---------------------------------------------------------------------------

def test_user_order_governs_sms_cell_sequence_including_new_metric():
    """AC-4 (SMS-Teil): zwei Auswahlen mit denselben zwei Groessen in
    umgekehrter Reihenfolge (Luftfeuchtigkeit -- ausserhalb der alten
    Sechserliste `_CHANNEL_METRICS` -- und Temp max) -> die Zellfolge im
    Ortsteil unterscheidet sich entsprechend.

    Ist-Zustand: `_channel_metric_cells()` bildet die Schnittmenge mit der
    festen Sechserliste -- Luftfeuchtigkeit ist darin nicht enthalten und
    verschwindet unabhaengig von der Reihenfolge komplett."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name), temp_max=16.4,
        hourly_data=_daily_points(humidity_pct=70),
    )
    order_a = ["humidity_avg", "temp_max"]
    order_b = ["temp_max", "humidity_avg"]
    cell_hu = _sms_cell_text(loc, "humidity_avg")
    cell_temp = _sms_cell_text(loc, "temp_max")
    assert cell_hu and cell_temp, (
        "Testaufbau defekt: sowohl Luftfeuchtigkeit als auch Temp max "
        "muessen an diesem Ort einen Wert UND ein Katalog-Kuerzel haben."
    )

    sms_a = render_compare_sms(_result([loc]), enabled_metrics=order_a)
    sms_b = render_compare_sms(_result([loc]), enabled_metrics=order_b)
    part_a = _location_part(sms_a, name)
    part_b = _location_part(sms_b, name)

    expected_a = f"{name} {cell_hu} {cell_temp}"
    expected_b = f"{name} {cell_temp} {cell_hu}"
    assert part_a == expected_a, (
        f"Reihenfolge A (Luftfeuchtigkeit zuerst) liefert Ortsteil {part_a!r}, "
        f"erwartet {expected_a!r}."
    )
    assert part_b == expected_b, (
        f"Reihenfolge B (Temp zuerst) liefert Ortsteil {part_b!r}, erwartet "
        f"{expected_b!r}."
    )
    assert part_a != part_b, (
        f"Beide Reihenfolgen liefern denselben Ortsteil {part_a!r} -- die "
        "Nutzer-Reihenfolge wirkt sich im SMS-Kanal nicht aus."
    )


# ---------------------------------------------------------------------------
# AC-5 (SMS-Teil) -- reine Nicht-Sechser-Auswahl bleibt nicht leer
# ---------------------------------------------------------------------------

def test_selection_of_only_new_metrics_does_not_render_empty_sms():
    """AC-5 (SMS-Teil): Auswahl ausschliesslich aus Groessen ausserhalb der
    heutigen Sechserliste (Luftfeuchtigkeit, Boeen) -> beide Werte erscheinen
    im Ortsteil -- heute liefert die Schnittmenge mit `_CHANNEL_METRICS`
    nichts, der Ortsteil zeigt ausser dem Ortsnamen keine einzige Zelle."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name), gust_max=25.0,
        hourly_data=_daily_points(humidity_pct=55),
    )
    cell_hu = _sms_cell_text(loc, "humidity_avg")
    cell_gust = _sms_cell_text(loc, "gust_max")
    assert cell_hu and cell_gust, (
        "Testaufbau defekt: beide Groessen muessen an diesem Ort einen Wert "
        "UND ein Katalog-Kuerzel haben."
    )

    sms = render_compare_sms(
        _result([loc]), enabled_metrics=["humidity_avg", "gust_max"],
    )
    part = _location_part(sms, name)

    assert part != name, (
        f"Ortsteil zeigt ausser dem Ortsnamen keine Zelle: {part!r} -- beide "
        "gewaehlten Groessen (Luftfeuchtigkeit, Boeen) liegen ausserhalb der "
        "Sechserliste und werden von der Schnittmenge verworfen."
    )
    assert cell_hu in part, (
        f"Ortsteil {part!r} enthaelt die erwartete Luftfeuchtigkeit-Zelle "
        f"{cell_hu!r} nicht."
    )
    assert cell_gust in part, (
        f"Ortsteil {part!r} enthaelt die erwartete Boeen-Zelle {cell_gust!r} "
        "nicht."
    )


# ---------------------------------------------------------------------------
# AC-7 (SMS-Teil) -- Regressionsschutz: die heutigen sechs Werte unveraendert
# ---------------------------------------------------------------------------

def test_regression_original_six_metrics_values_unchanged_in_sms():
    """AC-7 (SMS-Teil): eine Auswahl exakt der heutigen sechs Groessen liefert
    unveraenderte WERTE in der SMS (Kuerzel/Label duerfen sich aendern, die
    Zahlen nicht).

    HINWEIS (Abweichung vom Telegram-Pendant in
    test_compare_kanal_metriken.py, das bereits gruen sein DARF): fuer SMS
    ist dieser Test HEUTE ROT, nicht gruen. `_SMS_METRICS_PER_LOCATION = 2`
    zeigt unabhaengig von der Auswahlgroesse IMMER nur die ersten zwei der
    sechs Groessen (in `_CHANNEL_METRICS`-Reihenfolge: Temp, Wind) -- die
    uebrigen vier (Sonne/Wolken/Schneehoehe/Neuschnee) fehlen komplett im
    heutigen SMS-Text. Das ist genau der in dieser Spec zu behebende Fehler
    (feste Zwei-Metriken-Grenze statt Zeichen-Budget-Schleife), kein
    Widerspruch zur Regressionsschutz-Absicht von AC-7 -- nur deren
    erwarteter (roter) Ausgangszustand fuer den SMS-Kanal."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=16.4, wind_max=12.0, sunny_hours=5, cloud_avg=42,
        snow_depth_cm=30.0, snow_new_cm=4.0,
    )
    enabled = [
        "temp_max", "wind_max", "sunny_hours", "cloud_avg", "snow_depth_cm",
        "snow_new_cm",
    ]
    sms = render_compare_sms(_result([loc]), enabled_metrics=enabled)
    part = _location_part(sms, name)

    expected_values = [
        # Adversary-Fund Runde 4 (PO-Entscheidung 2026-07-30): der SMS-Pfad
        # gibt kein Grad-Zeichen aus (GSM-7) -- _sms_gsm7_safe() ist dieselbe
        # Produktionsfunktion, die auch die Implementierung anwendet.
        _sms_gsm7_safe(format_value("temperature", 16.4, style="plain")),
        format_value("wind", 12.0, style="plain"),
        f"{format_value('sunshine', 5, style='bare')}h",
        format_value("cloud_total", 42, style="plain"),
        format_value("snow_depth", 30.0, style="plain"),
        "4 cm",
    ]
    for value in expected_values:
        assert value in part, (
            f"Ortsteil {part!r} enthaelt den erwarteten Wert {value!r} nicht "
            "-- AC-7 verlangt unveraenderte WERTE fuer die heutigen sechs "
            "Groessen auch im SMS-Kanal. Ist-Zustand: SMS zeigt nur die "
            "ersten zwei Zellen (`_SMS_METRICS_PER_LOCATION = 2`)."
        )


# ---------------------------------------------------------------------------
# AC-8 -- Kuerzel kommen ausschliesslich aus dem Katalog, fuer alle 26 Groessen
# ---------------------------------------------------------------------------

def test_every_compare_metric_has_nonempty_sms_code():
    """AC-8: jede der 26 Compare-Groessen liefert ueber `get_sms_code()`
    (angewandt auf ihre zugrundeliegende Katalog-Metrik-ID) ein NICHT-LEERES
    Kuerzel -- keine Groesse soll ihr Kuerzel je aus einer zur Laufzeit
    abgeleiteten Bezeichnung gewinnen muessen.

    Ist-Zustand: 10 der 24 zugrundeliegenden Katalog-Groessen fuehren noch
    kein `sms_code` (`src/app/metric_catalog.py`): wind_chill, dewpoint,
    wind_direction, precip_type, cloud_low, cloud_mid, cloud_high,
    cloud_total, pressure, sunshine (Spec Implementation Details Punkt 3,
    Tabelle)."""
    missing = [
        (renderer_id, metric_id)
        for renderer_id, metric_id in RENDERER_TO_METRIC_ID.items()
        if not get_sms_code(metric_id)
    ]
    assert not missing, (
        f"{len(missing)} von {len(RENDERER_TO_METRIC_ID)} Compare-Renderer-"
        f"IDs liefern kein Katalog-Kuerzel ueber get_sms_code(): {missing!r} "
        "-- jede der 26 Groessen muss ein nicht-leeres Kuerzel liefern "
        "(AC-8)."
    )


# ---------------------------------------------------------------------------
# Adversary-Fund (Runde 3, #1362 S5b): dieselbe Katalog-Groesse in MEHREREN
# Auswertungen (Hoechst-/Tiefstwert) teilt sich sonst ein Kuerzel -- "D 33°C
# D 17°C" ist ohne Zeichen nicht unterscheidbar (im Staging-Nachweis gefunden,
# echte Innsbruck-SMS). PO-Entscheidung 2026-07-29: `+` fuer Hoechst-, `-` fuer
# Tiefstwert, IMMER wenn die Groesse im Ortsvergleich mehr als eine Auswertung
# anbietet -- nicht nur bei gleichzeitiger Auswahl beider.
# ---------------------------------------------------------------------------

def test_max_and_min_of_same_metric_carry_distinguishing_sign():
    """Auswahl mit Hoechst- UND Tiefsttemperatur -> beide Zellen tragen
    dasselbe Kuerzel ('D'), aber unterscheidbare Zeichen ('D+'/'D-') --
    RED-Grund: ohne Zeichen waeren beide Zellen identisch ('D 33°C D 17°C'),
    der Empfaenger kann nicht erkennen, welcher Wert welcher ist."""
    name = "Innsbruck"
    loc = LocationResult(
        location=_loc("a", name), temp_max=33.0, temp_min=17.0,
    )
    sms = render_compare_sms(
        _result([loc]), enabled_metrics=["temp_max", "temp_min"],
    )
    part = _location_part(sms, name)

    cell_max = _sms_cell_text(loc, "temp_max")
    cell_min = _sms_cell_text(loc, "temp_min")
    assert cell_max and cell_min, "Testaufbau defekt: beide Zellen brauchen Werte+Kuerzel"

    assert cell_max != cell_min, (
        f"Hoechst- und Tiefstwert-Zelle sind identisch ({cell_max!r}) -- nicht "
        f"unterscheidbar. Ortsteil: {part!r}"
    )
    assert cell_max.startswith("D+ "), (
        f"Hoechstwert-Zelle muss mit 'D+ ' beginnen, war {cell_max!r}."
    )
    assert cell_min.startswith("D- "), (
        f"Tiefstwert-Zelle muss mit 'D- ' beginnen, war {cell_min!r}."
    )
    assert cell_max in part and cell_min in part, (
        f"Ortsteil {part!r} enthaelt nicht beide unterscheidbaren Zellen "
        f"({cell_max!r}, {cell_min!r})."
    )


def test_single_aggregation_metrics_carry_no_sign():
    """Regressionsschutz: Groessen mit GENAU EINER Auswertung im Ortsvergleich
    (z.B. UV-Index, Regensumme, CAPE) bleiben ohne Zeichen -- dort ist nichts
    mehrdeutig, jedes Zeichen kostet SMS-Budget."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name), uv_index_max=7.0, precip_sum_mm=0.3,
        hourly_data=_daily_points(cape_jkg=820.0),
    )
    enabled = ["uv_max", "precip_sum", "cape_max"]
    cells = [_sms_cell_text(loc, mid) for mid in enabled]
    assert all(cells), f"Testaufbau defekt: erwartet Werte fuer alle drei Groessen ({cells!r})"

    sms = render_compare_sms(_result([loc]), enabled_metrics=enabled)
    part = _location_part(sms, name)

    for cell in cells:
        assert "+" not in cell and "-" not in cell, (
            f"Groesse mit nur einer Auswertung traegt faelschlich ein "
            f"Auswertungszeichen: {cell!r}."
        )
        assert cell in part, f"Ortsteil {part!r} enthaelt {cell!r} nicht."


def test_ambiguous_metrics_derived_from_catalog_are_exactly_temperature_and_wind_chill():
    """Dokumentiert den Code-ermittelten Befund (PO-Auftrag: 'ermittle am Code,
    nicht aus meiner Aufzaehlung'): genau die Katalog-Groessen, die im
    Ortsvergleich MEHR ALS EINE Auswertung anbieten, brauchen ein
    Auswertungszeichen. Bricht laut, wenn eine zukuenftige Katalog-Erweiterung
    eine dritte mehrdeutige Groesse einfuehrt, ohne dass das bewusst
    entschieden wurde."""
    from output.renderers.comparison import _AMBIGUOUS_CATALOG_METRIC_IDS

    assert _AMBIGUOUS_CATALOG_METRIC_IDS == frozenset({"temperature", "wind_chill"}), (
        f"Erwartet genau {{'temperature', 'wind_chill'}} als Katalog-Groessen mit "
        f"mehreren Ortsvergleich-Auswertungen, gefunden: "
        f"{sorted(_AMBIGUOUS_CATALOG_METRIC_IDS)}."
    )
