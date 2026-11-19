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

#3172 (ADR-0125): die Zellform ``Kuerzel Wert`` ist abgeloest -- die Orte-SMS
schreibt die Token-Zeile der Trip-SMS (``D6/16 W- HU-``), gekuerzt still vom
Listenende (kein ``+N``). Die Zusicherungen dieser Datei (Budget, nie mitten
im Token geschnitten, Nutzer-Reihenfolge, keine leere SMS, Werte, ein Kuerzel
je Auswertung) gelten unveraendert, jetzt gegen die Token-Zeile.

Test-Politik (CLAUDE.md, Schicht "Kern"): rein deterministisch, KEINE Mocks
(kein Mock()/patch()/MagicMock), kein Netz, kein Versand. Alle Pruefungen
lesen den GERENDERTEN SMS-Text (Nutzersicht), nicht den Code-Pfad. Werte/
Kuerzel werden ueber dieselben Produktions-Bausteine berechnet, die die Spec
fuer die Implementierung vorschreibt (`get_sms_code`, `_metric_value`,
`_PLAIN_ROWS`) -- keine zweite, im Test erfundene Formatierungsquelle.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import date, datetime

from app.ampel import resolve_ampel
from app.metric_catalog import kurzform_kuerzel
from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.channel_layout import CHANNEL_LIMITS
from output.renderers.comparison import _RENDERER_TO_CATALOG_METRIC_ID, render_compare_sms
from output.renderers.compare_metric_catalog import get_compare_metric_catalog
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.orte_sms import orte_kuerzel_je_metrik, orte_token_reihen

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
#
# Issue #1585: Quelle ist die AUSGELIEFERTE Katalogantwort
# (`get_compare_metric_catalog()`), NICHT mehr der rohe `COMPARE_METRIC_CATALOG`.
# Der Rohkatalog behaelt seine `cape_max_jkg`-Zeile bewusst (Modul-Import-Assert
# gegen `FRONTEND_TO_RENDERER_METRIC_ID`), liefert sie aber nicht mehr aus --
# wer ihn hier laese, versuchte eine Groesse zu rendern, die nirgends mehr
# ankommt (`KeyError: 'cape_max'`). Ueber die Auslieferung faellt sie
# automatisch heraus, ohne hartkodierte Ausnahme.
_METRIC_ID_BY_FRONTEND_KEY = {
    entry["key"]: entry["metric_id"] for entry in get_compare_metric_catalog()
}
RENDERER_TO_METRIC_ID: dict[str, str] = {
    renderer_id: _METRIC_ID_BY_FRONTEND_KEY[frontend_key]
    for frontend_key, renderer_id in FRONTEND_TO_RENDERER_METRIC_ID.items()
    if frontend_key in _METRIC_ID_BY_FRONTEND_KEY
}
ALL_RENDERER_IDS = tuple(RENDERER_TO_METRIC_ID)
assert len(ALL_RENDERER_IDS) == 25, (
    f"Erwartet 25 ausgelieferte Compare-Renderer-IDs (26 Katalogzeilen minus "
    f"cape_max_jkg, #1585), gefunden {len(ALL_RENDERER_IDS)} -- Testgrundlage "
    "fuer AC-8 pruefen (compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID / "
    "compare_metric_catalog.get_compare_metric_catalog)."
)


def _loc(loc_id: str, name: str, *, lat: float = 47.0, lon: float = 11.0) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=600)


def _daily_points(
    *, dewpoint_c: float | None = None, pressure_msl_hpa: float | None = None,
    humidity_pct: int | None = None, cape_jkg: float | None = None,
    freezing_level_m: int | None = None, snowfall_limit_m: int | None = None,
    uv_index: float | None = None, pop_pct: int | None = None,
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
            snowfall_limit_m=snowfall_limit_m, uv_index=uv_index, pop_pct=pop_pct,
        ))
    return points


def _result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations, time_window=(0, 23), target_date=TARGET_DATE,
        created_at=CREATED_AT,
    )


def _token_texte(loc_result: LocationResult, renderer_ids: list[str]) -> list[str]:
    """Erwartete Token der Token-Zeile fuer genau diese Auswahl, aus dem
    Produktiv-Baustein ``orte_sms.orte_token_reihen`` (alle Listenzeilen) --
    keine zweite, im Test erfundene Formatierungsquelle (#3172, ADR-0125)."""
    tokens = orte_token_reihen(loc_result, renderer_ids, None, ampel=resolve_ampel({}))[0]
    return [t.render() for t in tokens if t.category in ("forecast", "wintersport")]


def _sms_cell_text(loc_result: LocationResult, renderer_id: str) -> str | None:
    """Token EINER Groesse (``D16``, ``HU-``, ``FZ1200@2``); ``None`` = kein
    Wert an diesem Ort (``?``) oder kein Token. Das Kuerzel kommt aus den
    Symboltabellen der Trip-SMS (``D``/``L``, ``FD``/``FL``, #2232)."""
    texte = _token_texte(loc_result, [renderer_id])
    if len(texte) != 1 or texte[0].endswith("?"):
        return None
    return texte[0]


def _kuerzel(token: str) -> str:
    """Kuerzel eines Tokens -- laengstes passendes Symbol der Orte-SMS."""
    return max((s for s in orte_kuerzel_je_metrik() if token.startswith(s)), key=len)


def _location_part(sms: str, name: str) -> str:
    """Teiltext EINES Ortes ``{Name}: {Token}`` innerhalb der flachen,
    Semikolon-getrennten Compare-SMS -- bis zum naechsten '; ' bzw.
    Stringende (analog tests/tdd/test_compare_sms_official_alerts.py).

    #3122 B5: bei genau einem Ort steht der Name im Kopf (``{Ort} TT.MM.: …``)
    statt vor den Werten -- hier wieder als ``{Ort}: …`` gelesen."""
    kopf = re.match(rf"{re.escape(name)} \d\d\.\d\d\.:(?: |$)", sms)
    if kopf:
        rest = sms[kopf.end():]
        return f"{name}: {rest}" if rest else name
    idx = sms.index(name)
    rest = sms[idx:]
    end = rest.find("; ")
    return rest if end == -1 else rest[:end]


def _valid_prefix_candidates(name: str, cells: list[str]) -> set[str]:
    """Jede STRUKTURELL gueltige Auspraegung des Ortsteils: der Ortsname,
    gefolgt von einem PRAEFIX der Token-Liste (0..alle Token, in Reihenfolge,
    ohne Luecke -- ganze Token, nie ein Teil-Kuerzel/-Wert). #3172 (ADR-0125):
    ohne Zaehler ``+N`` (Kuerzung still vom Listenende wie im Trip).

    Bewusst OHNE Annahme ueber den internen Zeichen-Budget-Grenzwert -- die
    Pruefung ist strukturell und budget-agnostisch."""
    candidates = {name}
    for i in range(1, len(cells) + 1):
        candidates.add(f"{name}: " + " ".join(cells[:i]))
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
    # #3172: die Token-Zeile ist kuerzer als die alte Zellform -- ein langer
    # Ortsname haelt die volle Darstellung ueber dem Budget.
    name = "Andermatt Talstation an der Oberalppass-Strasse, Nordportal"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=16.4, temp_min=6.2, wind_max=15.0, gust_max=20.0,
        snow_depth_cm=20.0, snow_new_cm=4.0, precip_sum_mm=5.0, pop_max_pct=30,
        thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
        uv_index_max=5.0, cloud_avg=55, sunny_hours=4.5,
        hourly_data=_daily_points(
            humidity_pct=70, freezing_level_m=1200,
            snowfall_limit_m=1300, dewpoint_c=8.0, pressure_msl_hpa=1013.0,
            # #3172: UV und Regenwahrscheinlichkeit kommen aus den Stundenwerten.
            uv_index=5.0, pop_pct=30,
        ),
    )
    enabled = [
        # Issue #1585: "cape_max" entfaellt (nicht mehr ausgeliefert). Damit die
        # Auswahl den SMS-Ueberlauf weiterhin ERZWINGT -- der eigentliche
        # Pruefgegenstand von AC-3 --, treten "temp_min", "cloud_avg" und
        # "sunny_hours" an seine Stelle; ohne Ersatz waere die volle
        # Darstellung nur noch 150 Zeichen lang und der Test liefe leer.
        "temp_max", "temp_min", "wind_max", "gust_max", "precip_sum", "pop_max",
        "thunder_max", "visibility_min", "uv_max", "snow_depth_cm",
        "snow_new_cm", "humidity_avg", "freezing_level", "cloud_avg",
        "sunny_hours", "snowfall_limit", "dewpoint_avg", "pressure_avg",
    ]
    cells = _token_texte(loc, enabled)
    # Tiefst- und Hoechstwert stehen als EIN Bereichs-Token ``D6/16`` (#3172).
    assert len(cells) == len(enabled) - 1 and not any(c.endswith("?") for c in cells), (
        f"Testaufbau defekt: erwartet einen Wert fuer alle {len(enabled)} "
        f"gewaehlten Groessen, erhalten {len(cells)} Token ({cells!r}) -- "
        "Fixture pruefen (fehlt ein Wert?)."
    )
    full_length_estimate = len(name) + 2 + sum(len(c) + 1 for c in cells)
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
        f"Token-Liste {cells!r} -- entweder wurde mitten in einem Token "
        f"geschnitten oder ein Token uebersprungen. Ganze SMS: {sms!r}"
    )
    assert part != f"{name}: " + " ".join(cells), "Testaufbau: kein Ueberlauf"


# ---------------------------------------------------------------------------
# Adversary-Fund (QA-Runde 2, #1362 S5b): Metrik-Ueberlauf (je Ortsblock,
# neu) und Orts-Ueberlauf (Nachrichtenende, bestehend seit #1269) treffen
# zusammen -- beide Zahlen muessen zuordenbar bleiben.
# ---------------------------------------------------------------------------

def test_metric_overflow_and_location_overflow_are_both_present_and_distinguishable():
    """Adversary-Fund: Metrik-Kuerzung (im Ortsblock) und Orts-Ueberlauf (`+k
    Orte` am Nachrichtenende, #1269) treffen zusammen. #3172 (ADR-0125): die
    Metrik-Kuerzung zaehlt nicht mehr (kein `+N`), der Orts-Ueberlauf traegt
    weiter den Wortzusatz " Orte"; Orte entfallen erst, wenn je Ort nur noch
    die erste Listenzeile steht.

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
        # Issue #1585: "cape_max" entfaellt -- die Groesse wird nicht mehr
        # ausgeliefert und hat im SMS-Pfad keine Zelle mehr.
        "snow_new_cm", "humidity_avg", "freezing_level",
        "snowfall_limit",
    ]
    cells = _token_texte(loc_a, enabled)
    assert len(cells) == len(enabled), "Testaufbau defekt (s. AC-3-Zwilling)"

    # #3047 Runde 7 p8 (AC-23, Tech-Lead-Entscheidung ADR-0095): zwei Orte
    # passen jetzt beide (ihre Zellen werden zuerst gekuerzt). Der Orts-
    # Ueberlauf braucht deshalb so viele Orte, dass selbst ihre erste
    # Listenzeile nicht mehr fuer alle reicht: Zermatt plus sieben weitere.
    weitere = [
        dataclasses.replace(loc_b, location=_loc(f"b{i}", f"{name_b} Gornergrat {i}"))
        for i in range(7)
    ]
    sms = render_compare_sms(_result([loc_a, loc_b, *weitere]), enabled_metrics=enabled)

    assert len(sms) <= SMS_LIMIT, (
        f"SMS-Budget verletzt: {len(sms)} Zeichen ({sms!r})."
    )

    # Der letzte Ort muss vollstaendig entfallen sein -- sonst greift dieser
    # Test den Doppel-Ueberlauf-Fall nicht (Testaufbau-Guard).
    assert weitere[-1].location.name not in sms, (
        f"Testaufbau defekt: der letzte Ort erscheint noch in der SMS -- kein "
        f"Orts-Ueberlauf ausgeloest. SMS: {sms!r}"
    )

    # Orts-Ueberlauf mit Wortzusatz "Orte" am Nachrichtenende; er zaehlt genau
    # die nicht gezeigten Orte.
    location_overflow = re.search(r" \+(\d+) Orte$", sms)
    assert location_overflow is not None, (
        f"Kein wortbasierter Orts-Ueberlauf-Hinweis (' +k Orte') am "
        f"Nachrichtenende gefunden: {sms!r}"
    )
    gezeigt = sms[:location_overflow.start()].split(": ", 1)[1].split("; ")
    assert len(gezeigt) + int(location_overflow.group(1)) == 9, (
        f"Orts-Ueberlauf zaehlt falsch: {sms!r}"
    )
    # Orte entfallen erst, wenn je Ort nur noch die erste Listenzeile steht.
    for teil in gezeigt:
        assert len(teil.split(": ", 1)[1].split(" ")) == 1, f"mehr als eine Zeile: {sms!r}"

    # Metrik-Ueberlauf: der ERSTE (einzige gezeigte) Ortsteil ist ein
    # gueltiger, nie mitten im Kuerzel/Wert geschnittener Praefix der
    # Zellenliste (identischer Nachweis wie AC-3) -- OHNE den Orts-Ueberlauf-
    # Zusatz, der separat am Nachrichtenende steht (deshalb bis
    # `location_overflow.start()` geschnitten, nicht bis Stringende).
    part = gezeigt[0]
    assert part.startswith(name_a), sms
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
    # Testaufbau-Guard: die Metrik-Kuerzung selbst MUSS auftreten -- sonst
    # prueft dieser Test nur noch den Orts-Ueberlauf allein.
    assert part != f"{name_a}: " + " ".join(cells), (
        f"Testaufbau defekt: Ortsteil {part!r} zeigt alle Token -- keine "
        f"Metrik-Kuerzung. Ganze SMS: {sms!r}"
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

    expected_a = f"{name}: {cell_hu} {cell_temp}"
    expected_b = f"{name}: {cell_temp} {cell_hu}"
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
        snow_depth_cm=30.0, snow_new_cm=4.0, hourly_data=_daily_points(),
    )
    enabled = [
        "temp_max", "wind_max", "sunny_hours", "cloud_avg", "snow_depth_cm",
        "snow_new_cm",
    ]
    sms = render_compare_sms(_result([loc]), enabled_metrics=enabled)
    part = _location_part(sms, name)

    # #3172 (ADR-0125): Token-Zeile -- die Tageswerte der Mail stehen
    # unveraendert als Zahl am Kuerzel (gerundet, ohne Einheit), Wind und
    # Bewoelkung kommen wie im Trip aus den Stundenwerten.
    expected_values = ["D16", "SU5", "SD30", "NS24+4", "W-"]
    for value in expected_values:
        assert value in part.split(" "), (
            f"Ortsteil {part!r} enthaelt den erwarteten Token {value!r} nicht "
            "-- AC-7 verlangt unveraenderte WERTE fuer die heutigen sechs "
            "Groessen auch im SMS-Kanal."
        )
    assert re.search(r" CT50@\d+", part), part


# ---------------------------------------------------------------------------
# AC-8 -- Kuerzel kommen ausschliesslich aus dem Katalog, fuer alle 26 Groessen
# ---------------------------------------------------------------------------

def test_every_compare_metric_has_nonempty_sms_code():
    """AC-8: jede der 26 Compare-Groessen liefert ueber `kurzform_kuerzel()`
    (angewandt auf ihre zugrundeliegende Katalog-Metrik-ID) ein NICHT-LEERES
    Kuerzel -- keine Groesse soll ihr Kuerzel je aus einer zur Laufzeit
    abgeleiteten Bezeichnung gewinnen muessen.

    Ist-Zustand: 10 der 24 zugrundeliegenden Katalog-Groessen fuehren noch
    kein `sms_code` (`src/app/metric_catalog.py`): wind_chill, dewpoint,
    wind_direction, precip_type, cloud_low, cloud_mid, cloud_high,
    cloud_total, pressure, sunshine (Spec Implementation Details Punkt 3,
    Tabelle)."""
    # Issue #2232: gemessen wird die Kennung, die das Kuerzel TATSAECHLICH
    # traegt (`kuerzel_metric_id ?? metric_id`) -- fuer die Temperatur-Familie
    # ist das seit dieser Scheibe eine andere als die Auflösungs-Kennung.
    missing = [
        (renderer_id, _RENDERER_TO_CATALOG_METRIC_ID[renderer_id])
        for renderer_id in RENDERER_TO_METRIC_ID
        if not kurzform_kuerzel(_RENDERER_TO_CATALOG_METRIC_ID[renderer_id])
    ]
    assert not missing, (
        f"{len(missing)} von {len(RENDERER_TO_METRIC_ID)} Compare-Renderer-"
        f"IDs liefern kein Katalog-Kuerzel ueber kurzform_kuerzel(): {missing!r} "
        "-- jede der 26 Groessen muss ein nicht-leeres Kuerzel liefern "
        "(AC-8)."
    )


# ---------------------------------------------------------------------------
# AC-1/AC-2 (#2232) -- Hoechst- und Tiefstwert tragen EIGENE Kuerzel
#
# Vorgeschichte: bis 2026-09-09 trug der Ortsvergleich fuer beide Richtungen
# dasselbe Register-Kuerzel und unterschied sie ueber ein angehaengtes
# `+`/`-` (`_sms_aggregation_sign`, PO-Entscheidung 2026-07-29). Die Trip-SMS
# sendete fuer dieselben Groessen laengst `D`/`L` bzw. `FD`/`FL`. Zwei Kanaele,
# zwei Kuerzel fuer dieselbe Groesse -- der Empfaenger konnte sie nicht als
# dieselbe Groesse erkennen. Ab #2232 loest der Vergleich ueber
# `kuerzel_metric_id` auf und sendet dieselben Kuerzel wie der Trip; das
# Vorzeichen entfaellt ersatzlos (es kostete zusaetzlich SMS-Budget).
# ---------------------------------------------------------------------------

def test_ac1_hoechst_und_tiefsttemperatur_tragen_d_und_l_ohne_vorzeichen():
    """AC-1: Tageshoechst und -tiefst stehen unter `D`/`L` -- seit #3172 wie im
    Trip als EIN Bereich `D9/24` (Tiefst/Hoechst) -- nie `D+24`/`D-9`."""
    name = "Innsbruck"
    loc = LocationResult(
        location=_loc("a", name), temp_max=24.0, temp_min=9.0,
    )
    sms = render_compare_sms(
        _result([loc]), enabled_metrics=["temp_max", "temp_min"],
    )
    part = _location_part(sms, name)

    assert part == f"{name}: D9/24", (
        f"Der Ortsteil {part!r} zeigt Tiefst/Hoechst nicht als Bereich "
        f"`D9/24`. Ganze SMS: {sms!r}"
    )
    for verboten in ("D+", "D-"):
        assert verboten not in part, (
            f"Das Auswertungszeichen {verboten!r} steht noch im Ortsteil "
            f"{part!r} -- es ist mit #2232 ersatzlos entfallen."
        )


def test_ac2_gefuehlte_hoechst_und_tiefsttemperatur_tragen_fd_und_fl():
    """AC-2: die gefuehlten Werte tragen `FD`/`FL` (seit #3172 als Bereich
    `FD7/21` wie im Trip), niemals `TF+`/`TF-`."""
    name = "Innsbruck"
    loc = LocationResult(
        location=_loc("a", name), wind_chill_max=21.0, wind_chill_min=7.0,
    )
    sms = render_compare_sms(
        _result([loc]), enabled_metrics=["wind_chill_max", "wind_chill_min"],
    )
    part = _location_part(sms, name)

    assert part == f"{name}: FD7/21", (
        f"Der Ortsteil {part!r} zeigt die gefuehlten Werte nicht als "
        f"`FD7/21`. Ganze SMS: {sms!r}"
    )
    for verboten in ("TF+", "TF-", "TF "):
        assert verboten not in part, (
            f"Das alte Kuerzel/Zeichen {verboten!r} steht noch im Ortsteil "
            f"{part!r}. `TF` bleibt ausschliesslich dem Alarm-Pfad vorbehalten "
            "(Stundenwert-Schwelle), nicht der Tagesauswertung."
        )


def test_ac1_ac2_beide_richtungen_bleiben_unterscheidbar():
    """Regressionsschutz zum ersetzten Vorzeichen-Test: der Grund fuer `+`/`-`
    war, dass `D 24 D 9` nicht zuordenbar waere. Mit eigenen Kuerzeln bleibt
    die Unterscheidbarkeit erhalten -- ohne Zeichen und ohne Budget-Kosten."""
    loc = LocationResult(
        location=_loc("a", "Innsbruck"), temp_max=33.0, temp_min=17.0,
        wind_chill_max=30.0, wind_chill_min=14.0,
    )
    zellen = [
        _sms_cell_text(loc, mid)
        for mid in ("temp_max", "temp_min", "wind_chill_max", "wind_chill_min")
    ]
    assert all(zellen), f"Testaufbau defekt: nicht alle Zellen haben Werte ({zellen!r})"
    kuerzel = [_kuerzel(z) for z in zellen]
    assert len(set(kuerzel)) == 4, (
        f"Die vier Zellen tragen nur {len(set(kuerzel))} verschiedene Kuerzel "
        f"({kuerzel!r}) -- Hoechst- und Tiefstwert waeren nicht zuordenbar."
    )


def test_single_aggregation_metrics_carry_no_sign():
    """Regressionsschutz: Groessen mit GENAU EINER Auswertung im Ortsvergleich
    (z.B. UV-Index, Regensumme, Nullgradgrenze) tragen kein Zeichen -- dort war
    nie etwas mehrdeutig. Seit #2232 gilt das fuer JEDE Groesse; dieser Test
    haelt den Fall fest, der schon vorher zeichenfrei war.

    Issue #1585: Traeger-Groesse von "cape_max" auf "freezing_level"
    gewechselt -- CAPE wird nicht mehr ausgeliefert. Beide haben genau eine
    Auswertung, der Pruefgegenstand ist unveraendert."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name), uv_index_max=7.0, precip_sum_mm=0.3,
        hourly_data=_daily_points(freezing_level_m=1200, uv_index=7.0),
    )
    enabled = ["uv_max", "precip_sum", "freezing_level"]
    cells = [_sms_cell_text(loc, mid) for mid in enabled]
    assert all(cells), f"Testaufbau defekt: erwartet Werte fuer alle drei Groessen ({cells!r})"

    sms = render_compare_sms(_result([loc]), enabled_metrics=enabled)
    part = _location_part(sms, name)

    for cell in cells:
        # ``R-`` ist der Leerwert der Token-Zeile (Regen unter Gelb), kein Zeichen.
        assert "+" not in cell and "-" not in cell.rstrip("-"), (
            f"Groesse mit nur einer Auswertung traegt faelschlich ein "
            f"Auswertungszeichen: {cell!r}."
        )
        assert cell in part, f"Ortsteil {part!r} enthaelt {cell!r} nicht."
