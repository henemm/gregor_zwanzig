"""TDD RED — #2049: Roh/Einfach-Umschalter im 3-Tages-Ausblick wird wirksam.

SPEC: docs/specs/modules/fix_2049_ausblick_darstellungsform.md (14 ACs)

Kern-Schicht: kein Netz, keine Mocks. Echter Versandpfad (analog
``test_outlook_metric_id_all_channels.py``) fuer die Vier-Kanal-Wirkung,
direkte Aufrufe der Renderer-Funktionen fuer Faehigkeitsliste/Wortskalen/
Spannenzellen-Durchreichung.

Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))


# =============================================================================
# T1 — AC-2: Default ist explizit "Roh", kein stiller Rueckfall auf
# default_format_mode (das waere fuer wind_direction/cloud_total/sunshine
# "scale"/"symbol"/"symbol").
# =============================================================================

def test_ac2_ohne_outlook_metric_formats_bleibt_die_ausgabe_roh():
    """AC-2: Given eine Ausblick-Spaltenmenge ohne gesetzte Roh/Einfach-
    Zuordnung / When die Zellen fuer wind_direction, cloud_total und
    sunshine gebaut werden / Then zeigen sie die Rohzahl (Grad/Prozent/
    Stunden) -- NICHT die Katalog-Default-Form (symbol/scale), obwohl genau
    das der ``default_format_mode`` dieser drei Groessen waere."""
    from output.renderers.compare_outlook_metric_ids import (
        format_outlook_value, outlook_columns,
    )

    try:
        columns = outlook_columns(
            ["wind_direction", "cloud_total", "sunshine"], formats=None)
    except TypeError as exc:
        raise AssertionError(
            "outlook_columns() kennt den zweiten Parameter 'formats' noch "
            "nicht (#2049, compare_outlook_metric_ids.py:265). Ohne ihn kann "
            "eine Roh/Einfach-Zuordnung nie an die Spalten ankommen.\n"
            f"Ursprungsfehler: {exc}"
        ) from exc

    by_id = {c["metric_id"]: c for c in columns}
    faelle = {
        "wind_direction": (225, "225 °"),
        "cloud_total": (60, "60 %"),
        "sunshine": (4.2, "4.2 h"),
    }
    for metric_id, (raw, erwartet_roh) in faelle.items():
        column = by_id[metric_id]
        assert column.get("friendly") is not True, (
            f"{metric_id}: die Spalte traegt 'friendly'=True, obwohl keine "
            "Roh/Einfach-Zuordnung uebergeben wurde (AC-2, kein stiller "
            f"Default). Spalte: {column!r}"
        )
        text = format_outlook_value(raw, column)
        assert text == erwartet_roh, (
            f"{metric_id}: Zelle lautet {text!r} statt der Rohform "
            f"{erwartet_roh!r} (AC-2) -- default_format_mode dieser Groesse "
            "waere symbol/scale, der Ausblick-Default muss davon unabhaengig "
            "hart 'Roh' bleiben."
        )


# =============================================================================
# T2 — AC-5: dieselbe Wortstufe in allen vier Ausgabeorten.
#
# Traeger-Metrik: 'gust' statt der vom Tech-Lead vorgeschlagenen
# 'wind_direction' -- die geteilte Tagesfixtur (_summary() in
# tests/helpers/trip_outlook_selection.py) setzt 'wind_direction_avg_deg'
# nirgends UND das Feld steht nicht in ihrem aggregation_config, sodass
# aggregate_stage() es nie befuellt: die Zelle bliebe fuer Roh UND Einfach
# gleichermassen "-" und der Test praefe an dieser Stelle nichts (verletzt
# "Gegenprobe muss den mutierten Zweig erreichen"). 'gust' ist dagegen echt
# befuellt (gust_max_kmh, aggregation "max"); die drei Fixtur-Tage liefern
# 44/52/33 km/h -- format_wind_strength() ergibt dafuer "sehr stark"/
# "sehr stark"/"stark", alle drei ASCII-rein, sodass die ASCII-Faltung der
# Kompaktmail (fold_ascii) keinen fuenften Wert einfuehrt.
# =============================================================================

_WORTSTUFEN = "sehr stark|schwach|mäßig|stark"


def _gust_wortstufe(text, quelle: str) -> str:
    import re

    assert text, (
        f"{quelle}: Der 3-Tages-Ausblick fehlt vollstaendig (AC-5)."
    )
    treffer = re.search(_WORTSTUFEN, text)
    assert treffer, (
        f"{quelle}: Keine Boeen-Wortstufe gefunden -- die Zelle zeigt "
        f"vermutlich weiterhin die km/h-Zahl statt 'Einfach'.\nText:\n{text}"
    )
    return treffer.group(0)


def test_ac5_wind_boeen_zeigt_dieselbe_wortstufe_in_allen_vier_ausgaben():
    """AC-5: Given ``outlook_metric_formats={"gust": True}`` / When das
    Briefing fuer E-Mail (HTML), E-Mail (Klartext), E-Mail (kompakt) und
    Telegram gerendert wird / Then zeigen alle vier Ausgabeorte dieselbe
    Wortstufe statt der km/h-Zahl."""
    from tests.helpers.trip_outlook_channels import (
        compact_outlook_block, telegram_outlook_bubble, trip, versendete_teile,
    )
    from tests.helpers.trip_outlook_selection import (
        html_outlook_body_rows, html_outlook_headers, plain_outlook_block,
    )
    from tests.tdd.test_trip_outlook_dispatch_mail import _zugestellte_teile

    AUSWAHL = ["gust"]
    FORMATE = {"gust": True}

    html, plain = _zugestellte_teile(
        trip(outlook_metrics=AUSWAHL, outlook_metric_formats=FORMATE,
             email_format="full"))
    kompakt_body, bubbles = versendete_teile(
        trip(outlook_metrics=AUSWAHL, outlook_metric_formats=FORMATE,
             email_format="compact"))

    kopf = html_outlook_headers(html)
    zeilen = html_outlook_body_rows(html)
    assert kopf and zeilen, (
        "HTML-Mail: Der 3-Tages-Ausblick fehlt vollstaendig -- die "
        f"Kennungsauswahl {AUSWAHL!r} kam nicht an (AC-5)."
    )
    assert kopf == ["Tag", "Böen"], (
        f"HTML-Mail: Kopfzeile {kopf!r} -- erwartet 'Tag'+'Böen' aus der "
        f"Auswahl {AUSWAHL!r}."
    )

    html_zelle = zeilen[0][1] if len(zeilen[0]) > 1 else ""
    zellen = {
        "HTML-Mail": html_zelle,
        "Klartext": _gust_wortstufe(plain_outlook_block(plain), "Klartext"),
        "Kompaktmail": _gust_wortstufe(
            compact_outlook_block(kompakt_body), "Kompaktmail"),
        "Telegram": _gust_wortstufe(
            telegram_outlook_bubble(bubbles), "Telegram"),
    }

    import re
    assert re.fullmatch(_WORTSTUFEN, zellen["HTML-Mail"] or ""), (
        f"HTML-Mail: Die Boeen-Zelle lautet {zellen['HTML-Mail']!r} statt "
        "einer Wortstufe (AC-5) -- 'Einfach' wirkt hier nicht."
    )
    assert len(set(zellen.values())) == 1, (
        "Die vier Ausgaben zeigen unterschiedliche Boeen-Zellen fuer denselben "
        f"Tag: {zellen!r}. Sie stammen aus derselben Auswahl und muessen "
        "uebereinstimmen (AC-5, #1366-Fehlerklasse)."
    )


# =============================================================================
# T3 — AC-3/AC-4: Faehigkeitsliste ist EINE Quelle fuer Sichtbarkeit UND
# Wirkung; eine nicht-faehige Groesse bleibt wirkungslos.
# =============================================================================

_FAEHIGE_KENNUNGEN = frozenset({
    "wind_direction", "cloud_total", "cloud_low", "cloud_mid", "cloud_high",
    "wind", "gust", "precipitation", "rain_probability", "sunshine",
})
_UNFAEHIGE_KENNUNGEN = ("thunder", "temperature", "wind_chill", "cape",
                        "visibility")


def test_ac3_faehigkeitsliste_enthaelt_exakt_die_zehn_dokumentierten_groessen():
    """AC-3: Given die Ausblick-Faehigkeitsliste / When sie ausgelesen wird
    / Then enthaelt sie exakt die zehn Groessen der Metrik-Matrix -- weder
    mehr (z.B. thunder, das seine Roh-Form bereits als Wort zeigt) noch
    weniger."""
    try:
        from app.metric_catalog import OUTLOOK_FRIENDLY_CAPABLE
    except ImportError as exc:
        raise AssertionError(
            "app.metric_catalog kennt 'OUTLOOK_FRIENDLY_CAPABLE' noch nicht "
            "(#2049) -- ohne diese eine Quelle koennen Sichtbarkeit "
            "(Frontend) und Formatierungsverzweigung (Backend) "
            f"auseinanderlaufen (AC-4).\nUrsprungsfehler: {exc}"
        ) from exc

    ist = frozenset(OUTLOOK_FRIENDLY_CAPABLE)
    assert ist == _FAEHIGE_KENNUNGEN, (
        f"OUTLOOK_FRIENDLY_CAPABLE={sorted(ist)} weicht von der Metrik-Matrix "
        f"ab -- fehlend: {sorted(_FAEHIGE_KENNUNGEN - ist)}, zusaetzlich: "
        f"{sorted(ist - _FAEHIGE_KENNUNGEN)} (AC-3)."
    )


@pytest.mark.parametrize("metric_id", _UNFAEHIGE_KENNUNGEN)
def test_ac3_unfaehige_groessen_melden_false(metric_id):
    """AC-3: Given eine Groesse ohne Einfach-Form im Ausblick / When
    ``outlook_friendly_capable()`` sie prueft / Then liefert sie ``False``."""
    try:
        from app.metric_catalog import outlook_friendly_capable
    except ImportError as exc:
        raise AssertionError(
            "app.metric_catalog kennt 'outlook_friendly_capable()' noch "
            f"nicht (#2049).\nUrsprungsfehler: {exc}"
        ) from exc

    assert outlook_friendly_capable(metric_id) is False, (
        f"outlook_friendly_capable({metric_id!r}) liefert nicht False -- "
        "diese Groesse hat im Ausblick keine Einfach-Form (Metrik-Matrix, "
        "Spec 'Known Limitations')."
    )


def test_ac4_gesetztes_flag_fuer_temperatur_bleibt_wirkungslos():
    """AC-4: Given ``outlook_metric_formats={"temperature": True}`` (eine
    nicht-faehige Groesse) / When die Spalte gebaut und die Spannenzelle
    gerendert wird / Then bleibt sie unveraendert eine Zahlen-Spanne --
    Sichtbarkeit (Frontend) und Wirkung (Backend) haengen an DERSELBEN
    Faehigkeitsliste, ein einseitig gesetztes Flag darf nichts bewirken."""
    from output.renderers.compare_outlook_metric_ids import (
        format_outlook_range_cell, outlook_columns,
    )

    try:
        columns = outlook_columns(["temperature"],
                                   formats={"temperature": True})
    except TypeError as exc:
        raise AssertionError(
            "outlook_columns() kennt den Parameter 'formats' noch nicht "
            f"(#2049).\nUrsprungsfehler: {exc}"
        ) from exc

    assert len(columns) == 1, (
        f"Erwartet genau eine zusammengefuehrte Temperatur-Spalte, erhalten: "
        f"{columns!r}."
    )
    spalte = columns[0]
    assert spalte.get("friendly") is not True, (
        f"Die Temperatur-Spalte traegt 'friendly'=True, obwohl 'temperature' "
        f"nicht in der Faehigkeitsliste steht (AC-4). Spalte: {spalte!r}"
    )
    zelle = format_outlook_range_cell(9, 27, spalte)
    assert zelle == "9/27", (
        f"Die Temperatur-Zelle lautet {zelle!r} statt der unveraenderten "
        "Spanne '9/27' -- das wirkungslose Flag hat trotzdem etwas "
        "veraendert (AC-4)."
    )


# =============================================================================
# T4 — AC-11: _merge_min_max_pairs reicht 'friendly' zusaetzlich durch,
# obwohl die Funktion nur explizit gelistete Schluessel kopiert.
# =============================================================================

def test_ac11_merge_min_max_pairs_reicht_friendly_flag_durch():
    """AC-11: Given zwei Min/Max-Spalten derselben Groesse mit gesetztem
    'friendly'-Flag / When ``_merge_min_max_pairs`` sie zusammenfuehrt /
    Then traegt das zusammengefuehrte Dict 'friendly' weiterhin -- die
    Funktion baut ein NEUES Dict und kopiert bislang nur explizit gelistete
    Schluessel (label/metric_id/field_min/field_max/unit/decimals/kind/
    aggregation_label)."""
    from output.renderers.compare_outlook_metric_ids import _merge_min_max_pairs

    columns = [
        {"label": "Temp", "metric_id": "temperature", "aggregation": "min",
         "field": "temp_min_c", "unit": "°C", "decimals": 0, "kind": "range",
         "aggregation_label": "", "friendly": True},
        {"label": "Temp", "metric_id": "temperature", "aggregation": "max",
         "field": "temp_max_c", "unit": "°C", "decimals": 0, "kind": "range",
         "aggregation_label": "", "friendly": True},
    ]
    merged = _merge_min_max_pairs(columns)
    assert len(merged) == 1, f"Erwartet EINE zusammengefuehrte Spalte, erhalten: {merged!r}"
    assert merged[0].get("friendly") is True, (
        f"Das zusammengefuehrte Dict {merged[0]!r} traegt 'friendly' nicht "
        "(oder nicht True) -- _merge_min_max_pairs baut ein NEUES Dict und "
        "kopiert nur explizit gelistete Schluessel (AC-11); 'friendly' fehlt "
        "in dieser Liste."
    )


# =============================================================================
# T5 — AC-9: Niederschlag-Tagessumme braucht eine EIGENE Skala, nicht die
# Stunden-Schwellen von format_precip_intensity.
# =============================================================================

def test_ac9_niederschlag_tagessumme_nutzt_eigene_skala_nicht_stundenskala():
    """AC-9: Given 4 mm und 12 mm Niederschlag-Tagessumme / When
    ``format_precip_daily_sum`` (neue Tagesskala, <=0/<=5/<=20/>20 mm)
    formatiert / Then lautet der Text 'leicht' bzw. 'maessig' -- NICHT
    'maessig'/'stark', was die STUNDEN-Skala ``format_precip_intensity``
    (<=0/<=2/<=10/>10 mm) fuer dieselben Werte liefert. Kontrast-Assertion
    im selben Test: die alte Skala muss an genau diesen zwei Werten
    ABWEICHEN, sonst koennte jemand sie unbemerkt weiterverwenden."""
    from services.weather_metrics import format_precip_intensity

    try:
        from services.weather_metrics import format_precip_daily_sum
    except ImportError as exc:
        raise AssertionError(
            "services.weather_metrics kennt 'format_precip_daily_sum()' noch "
            f"nicht (#2049, AC-9).\nUrsprungsfehler: {exc}"
        ) from exc

    assert format_precip_daily_sum(4) == "leicht", (
        f"format_precip_daily_sum(4) == {format_precip_daily_sum(4)!r} statt "
        "'leicht' (Tagesskala <=5 mm)."
    )
    assert format_precip_daily_sum(12) == "mäßig", (
        f"format_precip_daily_sum(12) == {format_precip_daily_sum(12)!r} "
        "statt 'mäßig' (Tagesskala <=20 mm)."
    )
    # Kontrast: dieselben Werte auf der STUNDEN-Skala ergeben andere Woerter
    # -- der Beleg, dass hier zwei verschiedene Skalen am Werk sind.
    assert format_precip_intensity(4) == "mäßig", (
        f"Vorbedingung verletzt: format_precip_intensity(4) == "
        f"{format_precip_intensity(4)!r} statt 'mäßig' (Stundenskala)."
    )
    assert format_precip_intensity(12) == "stark", (
        f"Vorbedingung verletzt: format_precip_intensity(12) == "
        f"{format_precip_intensity(12)!r} statt 'stark' (Stundenskala)."
    )


# =============================================================================
# T6 — AC-7: Regenwahrscheinlichkeit-Wortskala.
# =============================================================================

@pytest.mark.parametrize("pct,erwartet", [
    (24, "unwahrscheinlich"), (25, "möglich"),
    (49, "möglich"), (50, "wahrscheinlich"),
    (74, "wahrscheinlich"), (75, "sehr wahrscheinlich"),
    (40, "möglich"), (80, "sehr wahrscheinlich"),
])
def test_ac7_regenwahrscheinlichkeit_wortskala(pct, erwartet):
    """AC-7: Given eine Regenwahrscheinlichkeit von ``pct`` Prozent / When
    Einfach aktiv ist / Then lautet der Text ``erwartet`` -- Grenzwerte
    24/25, 49/50, 74/75 Prozent."""
    try:
        from services.weather_metrics import format_rain_probability_scale
    except ImportError as exc:
        raise AssertionError(
            "services.weather_metrics kennt "
            f"'format_rain_probability_scale()' noch nicht (#2049, AC-7)."
            f"\nUrsprungsfehler: {exc}"
        ) from exc

    text = format_rain_probability_scale(pct)
    assert text == erwartet, (
        f"format_rain_probability_scale({pct}) == {text!r} statt {erwartet!r}."
    )


# =============================================================================
# T7 — AC-8: Sonnenstunden-Wortskala.
# =============================================================================

@pytest.mark.parametrize("stunden,erwartet", [
    (1.9, "trübe"), (2.0, "wechselhaft"),
    (4.9, "wechselhaft"), (5.0, "freundlich"),
    (7.9, "freundlich"), (8.0, "sonnig"),
    (1.5, "trübe"), (9.0, "sonnig"),
])
def test_ac8_sonnenstunden_wortskala(stunden, erwartet):
    """AC-8: Given eine Sonnenstunden-Tagessumme / When Einfach aktiv ist /
    Then lautet der Text ``erwartet`` -- Grenzwerte 1,9/2, 4,9/5, 7,9/8
    Stunden."""
    try:
        from services.weather_metrics import format_sunshine_scale
    except ImportError as exc:
        raise AssertionError(
            "services.weather_metrics kennt 'format_sunshine_scale()' noch "
            f"nicht (#2049, AC-8).\nUrsprungsfehler: {exc}"
        ) from exc

    text = format_sunshine_scale(stunden)
    assert text == erwartet, (
        f"format_sunshine_scale({stunden}) == {text!r} statt {erwartet!r}."
    )


# =============================================================================
# T8 — AC-6: kein Ampelpunkt-Marker im (escaped) HTML-Text; die Ampel
# bleibt allein ueber die Hintergrundtoenung sichtbar.
# =============================================================================

def test_ac6_einfach_zeigt_nur_wort_kein_ampelpunkt_im_text():
    """AC-6: Given Boeen ist auf 'Einfach' umgeschaltet, der Rohwert (44
    km/h) liegt im gelben Ampelband / When die Zelle formatiert wird /
    Then enthaelt der (escapte) Text ausschliesslich die Wortstufe -- kein
    zusaetzliches Ampel-Zeichen -- waehrend ``_metric_column_bg`` fuer
    denselben Rohwert weiterhin eine nicht-leere Toenung liefert."""
    import html as _html

    from output.renderers.email.outlook import _metric_column_bg
    from output.renderers.compare_outlook_metric_ids import format_outlook_value
    from services.weather_metrics import format_wind_strength

    column = {"metric_id": "gust", "kind": "range", "unit": "km/h",
              "decimals": 0, "friendly": True}
    text = format_outlook_value(44, column)
    erwartet = format_wind_strength(44)
    assert text == erwartet, (
        f"format_outlook_value(44, friendly=True) == {text!r} statt der "
        f"Wortstufe {erwartet!r} aus format_wind_strength() (AC-6/AC-10)."
    )

    escaped = _html.escape(text)
    assert escaped == text, (
        f"Der escapte Zellentext {escaped!r} weicht vom Rohtext {text!r} ab "
        "-- er enthaelt Zeichen, die HTML escapen muss (AC-6 verlangt reinen "
        "Wort-/Symboltext)."
    )
    for marker in ("●", "•", "○", "⬤", "🔴", "🟡", "🟢"):
        assert marker not in escaped, (
            f"Der Zellentext {escaped!r} enthaelt einen Ampelpunkt-Marker "
            f"({marker!r}) -- die Ampel darf laut AC-6 ausschliesslich ueber "
            "die Hintergrundtoenung sichtbar sein, nicht im Text."
        )

    bg = _metric_column_bg(column, 44)
    assert bg, (
        "_metric_column_bg(gust, 44) liefert keine Toenung -- 44 km/h liegt "
        "im gelben Ampelband (Schwelle 30/45/60); die Ampel-Information darf "
        "durch das 'Einfach'-Flag nicht verloren gehen (AC-6)."
    )


# =============================================================================
# T9 — AC-10: Wiederverwendung bestehender Helfer, Erwartung ZUR LAUFZEIT aus
# dem Helfer berechnet statt als Literal notiert.
# =============================================================================

def test_ac10_vier_groessen_nutzen_die_bestehenden_helfer_nicht_neue_logik():
    """AC-10: Given Windrichtung, Bewoelkung, Wind und Boeen auf 'Einfach' /
    When der Ausblick-Zellentext gebaut wird / Then stammt er aus
    ``degrees_to_compass``/``cloud_emoji``/``format_wind_strength`` -- die
    Erwartung wird HIER aus dem echten Helfer berechnet, nicht als Literal
    hingeschrieben, damit eine spaeter abdriftende Parallel-Logik rot wird."""
    from output.renderers.compare_outlook_metric_ids import format_outlook_value
    from output.metric_format import cloud_emoji
    from services.weather_metrics import format_wind_strength
    from utils.geo import degrees_to_compass

    faelle = [
        ("wind_direction", 225, degrees_to_compass(225)),
        ("cloud_total", 50, cloud_emoji(50)),
        ("wind", 45, format_wind_strength(45)),
        ("gust", 44, format_wind_strength(44)),
    ]
    for metric_id, raw, erwartet in faelle:
        column = {"metric_id": metric_id, "kind": "range", "unit": "",
                  "decimals": 0, "friendly": True}
        text = format_outlook_value(raw, column)
        assert text == erwartet, (
            f"{metric_id}: format_outlook_value({raw}, friendly=True) == "
            f"{text!r} statt {erwartet!r} (aus dem echten Helfer berechnet, "
            "AC-10) -- entweder fehlt der Einfach-Zweig, oder er ruft nicht "
            "den bestehenden Helfer."
        )


# =============================================================================
# T10 — AC-1: normalize_outlook_metric_formats() ist die Ladepfad-Haelfte der
# Speicherform -- akzeptiert nur {str: bool}, filtert nicht-faehige Kennungen
# heraus, ``None`` bei Nicht-Dict (analog normalize_outlook_metric_ids()).
# =============================================================================

@pytest.mark.parametrize("stored,erwartet", [
    ({"gust": True, "wind": False}, {"gust": True, "wind": False}),
    ({"temperature": True}, {}),
    ({"gust": "ja"}, {}),
    ([], None),
    ("x", None),
    (None, None),
    (42, None),
])
def test_ac1_normalize_outlook_metric_formats(stored, erwartet):
    """AC-1: Given ein gespeicherter Rohwert fuer
    ``display_config.outlook_metric_formats`` / When
    ``normalize_outlook_metric_formats()`` ihn laedt / Then bleibt eine
    faehige, boolesche Zuordnung unveraendert erhalten; eine nicht-faehige
    Kennung (temperature) wird herausgefiltert statt einen wirkungslosen
    Zustand einzuschleppen; ein nicht-boolescher Wert wird verworfen; ein
    Nicht-Dict liefert ``None`` -- dieselbe Drei-Werte-Semantik wie
    ``normalize_outlook_metric_ids()``."""
    try:
        from app.metric_catalog import normalize_outlook_metric_formats
    except ImportError as exc:
        raise AssertionError(
            "app.metric_catalog kennt 'normalize_outlook_metric_formats()' "
            "noch nicht (#2049, AC-1, Ladepfad-Haelfte der Speicherform).\n"
            f"Ursprungsfehler: {exc}"
        ) from exc

    ergebnis = normalize_outlook_metric_formats(stored)
    assert ergebnis == erwartet, (
        f"normalize_outlook_metric_formats({stored!r}) == {ergebnis!r} statt "
        f"{erwartet!r}."
    )
