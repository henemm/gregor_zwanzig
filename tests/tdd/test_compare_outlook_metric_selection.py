"""TDD RED — 3-Tages-Ausblick der Vergleichs-Mail: waehlbare Spalten.

Issues #1361 (Befund 2) + #1368, S3 Scheibe A von Epic #1372.
SPEC: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md
      AC-1, AC-2, AC-5, AC-8, AC-9, AC-10
KONTEXT: docs/context/fix-1361-1368-ausblick-konfigurierbar.md

Kern-Schicht, deterministisch: KEINE Mocks/patch()/MagicMock, kein Netz.
Echte ForecastDataPoint-/SavedLocation-/LocationResult-/ComparisonResult-DTOs
und der echte Renderpfad ``render_compare_email()`` (liefert HTML UND Klartext
DESSELBEN Aufrufs — der Pflicht-Validator liest nur HTML und ist im Klartext
blind, s. #1366). Geprueft wird, was in der gerenderten Mail steht, nicht
welche Funktion aufgerufen wurde. Kein Dateiinhalt-Check.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup

TARGET_DATE = date(2026, 7, 20)
TZ_NAME = "Europe/Vienna"

# Eindeutiger Marker der Ausblick-Tabelle (nur auf dieser einen Tabelle gesetzt,
# identisch zu tests/tdd/test_shared_outlook_renderer.py).
_OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"

# --- #2136 / ADR-0068 ------------------------------------------------------
# Die sieben festen Spaltenkuerzel des Standardfall-Ausblicks (Pfad 1,
# `outlook.py` thead) waren bis #2136 eine EIGENE, handgepflegte Namensliste:
# "N D R PR Wind Böen Gew" -- dieselbe Groesse hiess in der Stunden-/
# Etappentabelle derselben Mail anders ("Temp Rain Rain% Wind Gust Thdr").
# ADR-0068 stellt beide Ausblick-Renderpfade auf `MetricDefinition.col_label`
# um, dieselbe Quelle, aus der die Stundentabelle ihre Koepfe zieht
# (`get_col_defs()` -> `visible_cols()`).
#
# 🔴 Die Soll-Kopfzeile wird deshalb ABGELEITET, nie getippt. Ein zweites
# Literal hier waere genau die Doppelpflege, die der Fix abschafft -- und die
# Mutations-Gegenprobe (AC-8, tests/tdd/test_outlook_col_label_collision.py)
# haette eine zweite Stelle, an der sie haengenbleibt.
#
# (Kennung, Auswertung | None) je Wert-Spalte, in der unveraenderten
# Reihenfolge des festen Zweiges. Die beiden Temperatur-Spalten sind der
# statische Kollisionsfall aus AC-7: eine nackte `col_label`-Ersetzung ergaebe
# zweimal "Temp", deshalb traegt jede ihr Auswertungs-Suffix
# (`aggregation_label_de`, dieselbe Wortquelle wie die Duplikat-Aufloesung in
# `outlook_columns()`).
_PFAD1_WERTSPALTEN = (
    ("temperature", "min"),      # bisher "N"
    ("temperature", "max"),      # bisher "D"
    ("precipitation", None),     # bisher "R"
    ("rain_probability", None),  # bisher "PR"
    ("wind", None),              # bisher "Wind"
    ("gust", None),              # bisher "Böen"
    ("thunder", None),           # bisher "Gew"
)

# Auswahl im Speicherformat von ``display_config.outlook_metrics``: seit
# #1848 A2 die reine KENNUNG (vorher Groesse + Auswertung, #1373). Welche
# Auswertungen eine Kennung zeigt, leitet der Katalog ab -- fuer
# ``temperature`` sind das Tief UND Hoch in einer Spannen-Zelle.
SEL_TEMPERATUR = "temperature"
SEL_NIEDERSCHLAG = "precipitation"

# Was die Ueberschrift einer gewaehlten Spalte lauten DARF: die Beschriftungen
# der beiden Kataloge, aus denen die Spec sie speist (`col_label`/`label_de` aus
# `app.metric_catalog`, `label` aus `compare_metric_catalog`). Der Test schreibt
# keine der drei Varianten vor — er verlangt nur eine lesbare Katalog-
# Beschriftung statt der Kuerzel N/D/R/PR.
_ALLOWED_LABELS = {
    "temperature": {"Temp", "Temperatur"},
    "precipitation": {"Rain", "Niederschlag"},
}

# Ausblick-Ueberschriften im Klartext: der Ist-Zustand ("Nächste Etappen",
# Trip-Wortlaut) UND der Soll-Zustand. Der Block-Ableser unten muss beide
# kennen, damit ein RED-Lauf den Block ueberhaupt findet und inhaltlich (statt
# mit "Block nicht gefunden") scheitert.
_PLAIN_OUTLOOK_HEADINGS = ("3-Tages-Ausblick", "Nächste Etappen")


# ---------------------------------------------------------------------------
# Helpers — echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _day_points(day: date, temp_lo: float, temp_hi: float, precip_total: float):
    """Vier Stundenpunkte eines Kalendertages (UTC 02/08/14/20 = Ortszeit
    04/10/16/22 in Europe/Vienna — derselbe Kalendertag, kein Tagesuebergang)."""
    from app.models import ForecastDataPoint, ThunderLevel

    temps = [temp_lo, (temp_lo + temp_hi) / 2, temp_hi, (temp_lo + temp_hi) / 2]
    return [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0, tzinfo=timezone.utc),
            t2m_c=t, wind10m_kmh=15.0, gust_kmh=25.0,
            precip_1h_mm=precip_total / 4, pop_pct=55, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, visibility_m=20000,
        )
        for h, t in zip((2, 8, 14, 20), temps)
    ]


def _location(name: str = "Innsbruck"):
    """Ort mit Stundendaten fuer TARGET_DATE und Ausblickdaten fuer drei
    Kalendertage. Tag 2 traegt die Unterscheidungswerte 27 °C / 4.4 mm."""
    from app.user import LocationResult, SavedLocation

    day_specs = [
        (TARGET_DATE, 6.0, 18.0, 0.4),
        (TARGET_DATE + timedelta(days=1), 9.0, 27.0, 4.4),
        (TARGET_DATE + timedelta(days=2), 11.0, 23.0, 0.0),
    ]
    all_points: list = []
    for day, lo, hi, precip in day_specs:
        all_points.extend(_day_points(day, lo, hi, precip))
    today_points = [p for p in all_points if p.ts.date() == TARGET_DATE]

    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=47.27, lon=11.40,
                               elevation_m=574, timezone=TZ_NAME),
        score=50,
        hourly_data=today_points,
        outlook_hourly_data=all_points,
    )


def _result():
    from app.user import ComparisonResult

    return ComparisonResult(
        locations=[_location()], time_window=(9, 16),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )


def _render_mail(*, outlook_enabled: bool = True, outlook_metrics=None):
    """Echter Compare-Renderpfad. Kennt der Renderer den Auswahl-Parameter
    nicht, wird der TypeError in eine inhaltliche Aussage uebersetzt (statt in
    einen nichtssagenden Signaturfehler)."""
    from output.renderers.comparison import render_compare_email

    try:
        return render_compare_email(
            _result(),
            outlook_enabled=outlook_enabled,
            outlook_metrics=outlook_metrics,
        )
    except TypeError as exc:
        raise AssertionError(
            "Die Vergleichs-Mail kennt keine Ausblick-Spaltenauswahl: "
            "render_compare_email() nimmt den Parameter `outlook_metrics` nicht "
            "entgegen, der 3-Tages-Ausblick zeigt daher unveraenderlich dieselben "
            f"sieben Groessen fuer jeden Nutzer (AC-1/AC-2). Urspruenglicher Fehler: {exc}"
        ) from exc


def _outlook_tables(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return [t for t in soup.find_all("table")
            if _OUTLOOK_TABLE_MARKER in str(t.get("style", ""))]


def _headers(table) -> list[str]:
    return [th.get_text(strip=True) for th in table.find_all("th")]


def _body_rows(table) -> list[list[str]]:
    return [[td.get_text(strip=True) for td in tr.find_all("td")]
            for tr in table.find("tbody").find_all("tr")]


def _plain_outlook_blocks(text: str) -> list[tuple[str, list[str]]]:
    """(Ueberschrift, Datenzeilen) je Ausblick-Block im Klartext."""
    blocks: list[tuple[str, list[str]]] = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() in _PLAIN_OUTLOOK_HEADINGS:
            body: list[str] = []
            for follow in lines[i + 1:]:
                if not follow.strip():
                    break
                body.append(follow)
            blocks.append((line.strip(), body))
    return blocks


def _preset(**display_config) -> dict:
    return {
        "id": "cp-outlook-selection",
        "name": "Ausblick-Auswahl",
        "location_ids": ["innsbruck"],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
        "display_config": dict(display_config),
    }


def _resolved_outlook_metrics(preset: dict):
    """`CompareRenderOptions.outlook_metrics` — das Feld, ueber das die
    gespeicherte Auswahl den Versand- und den Vorschau-Pfad erreicht."""
    from services.report_config_resolver import resolve_compare_render_options

    opts = resolve_compare_render_options(preset)
    sentinel = object()
    value = getattr(opts, "outlook_metrics", sentinel)
    assert value is not sentinel, (
        "Die aufgeloesten Compare-Render-Optionen tragen kein Feld "
        "`outlook_metrics` — eine gespeicherte Ausblick-Auswahl erreicht damit "
        "weder Versand noch Vorschau, der Ausblick bleibt fest verdrahtet "
        f"(Spec Punkt 2). Vorhandene Felder: {sorted(vars(opts))}"
    )
    return value


# ---------------------------------------------------------------------------
# #2136 / ADR-0068 — geteilte Soll-Ableitung und Pruefbloecke
#
# Die beiden `pruefe_*`-Bloecke sind bewusst Funktionen und keine Testkoerper:
# die Mutations-Gegenprobe (AC-8) ruft GENAU diese Bloecke mit verfaelschtem
# Katalog-`col_label` erneut auf. Waeren sie dort nachgebaut, pruefte AC-8
# seine eigene Nachbildung statt des Prueflings.
# ---------------------------------------------------------------------------

def col_label(metric_id: str) -> str:
    """Tabellenueberschrift der Groesse aus dem ZENTRALEN Register — dieselbe
    Quelle, aus der `get_col_defs()` die Stundentabellen-Koepfe speist."""
    from app.metric_catalog import get_metric

    return get_metric(metric_id).col_label


def erwartete_pfad1_kopfzeile() -> list[str]:
    """Soll-Kopfzeile des Standardfall-Ausblicks (AC-2 + AC-7), abgeleitet."""
    from app.metric_catalog import aggregation_label_de

    kopf = ["Tag"]
    for metric_id, aggregation in _PFAD1_WERTSPALTEN:
        label = col_label(metric_id)
        if aggregation is not None:
            label = f"{label} {aggregation_label_de(aggregation)}"
        kopf.append(label)
    return kopf


def _stundentabelle_kopf(html: str) -> list[str]:
    """Spaltenkoepfe der Stundentabelle DERSELBEN Mail (Vergleichsanker für
    AC-1: dieselbe Groesse, derselbe Name, eine Mail)."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        kopf = [th.get_text(strip=True) for th in table.find_all("th")]
        if kopf and kopf[0] == "Zeit":
            return kopf
    return []


def pruefe_pfad1_kopfzeile_html() -> list[str]:
    """AC-2/AC-7-Pruefblock: Standardfall-Ausblick ohne jede Auswahl."""
    html, _text = _render_mail(outlook_metrics=None)
    tabellen = _outlook_tables(html)
    assert tabellen, "Ohne Auswahl muss der 3-Tages-Ausblick erscheinen"

    kopf = _headers(tabellen[0])
    erwartet = erwartete_pfad1_kopfzeile()
    assert kopf == erwartet, (
        f"Der Standardfall-Ausblick (Pfad 1) traegt die Kopfzeile {kopf!r} "
        f"statt der aus dem Metrik-Katalog abgeleiteten {erwartet!r}. Die "
        "sieben Kuerzel stehen als zweite, handgepflegte Namensliste im "
        "`thead` von src/output/renderers/email/outlook.py — dieselbe Groesse "
        "heisst in der Stundentabelle derselben Mail anders (AC-2/AC-7, "
        "ADR-0068)."
    )
    return kopf


def pruefe_pfad2_kopfzeile_html(metric_ids) -> list[str]:
    """AC-1-Pruefblock: konfigurierbarer Ausblick mit gesetzter Auswahl."""
    metric_ids = list(metric_ids)
    html, _text = _render_mail(outlook_metrics=metric_ids)
    tabellen = _outlook_tables(html)
    assert tabellen, "Kein 3-Tages-Ausblick in der HTML-Mail gefunden"

    kopf = _headers(tabellen[0])
    erwartet = ["Tag"] + [col_label(m) for m in metric_ids]
    assert kopf == erwartet, (
        f"Der konfigurierbare Ausblick (Pfad 2) traegt die Kopfzeile {kopf!r} "
        f"statt {erwartet!r}. `outlook_columns()` speist die Beschriftung "
        "weiterhin aus `compare_metric_catalog['label']` (deutscher Langname) "
        "statt aus `MetricDefinition.col_label` (AC-1, ADR-0068)."
    )

    stunden = _stundentabelle_kopf(html)
    assert stunden, (
        "Die Stundentabelle derselben Mail ist nicht auffindbar — ohne sie "
        "kann der Test die Gleichheit der Beschriftungen nicht belegen."
    )
    fehlend = [k for k in kopf[1:] if k not in stunden]
    assert not fehlend, (
        f"Die Ausblick-Spalten {fehlend!r} tragen einen Namen, den die "
        f"Stundentabelle DERSELBEN Mail nicht kennt ({stunden!r}). Genau das "
        "ist der gemeldete Befund: eine Groesse, zwei Namen in einer Mail "
        "(AC-1)."
    )
    return kopf


# ---------------------------------------------------------------------------
# AC-1: HTML-Ausblick zeigt genau die gewaehlten Spalten
# ---------------------------------------------------------------------------

def test_html_outlook_shows_only_selected_columns():
    """AC-1: Given ein Preset mit der Auswahl "Temperatur max" + "Niederschlag"
    / When die Vergleichs-Mail erzeugt wird / Then zeigt der HTML-Ausblick
    genau diese zwei Wert-Spalten in Auswahlreihenfolge mit lesbaren
    Katalog-Ueberschriften — nicht die sieben festen Spalten mit den Kuerzeln
    N/D/R/PR/Wind/Böen/Gew.
    """
    html, _text = _render_mail(outlook_metrics=[SEL_TEMPERATUR, SEL_NIEDERSCHLAG])

    tables = _outlook_tables(html)
    assert tables, "Kein 3-Tages-Ausblick in der HTML-Mail gefunden"

    headers = _headers(tables[0])
    assert len(headers) == 3, (
        "Der Ausblick zeigt nicht die zwei gewaehlten Groessen (plus Tag-Spalte), "
        f"sondern {len(headers)} Spalten: {headers}. Erwartet: Tag + Temperatur max "
        "+ Niederschlag (AC-1)."
    )
    assert headers[0] == "Tag", f"Erste Spalte soll der Wochentag bleiben: {headers}"
    assert headers[1] in _ALLOWED_LABELS["temperature"], (
        f"Zweite Spalte traegt {headers[1]!r} statt einer lesbaren Katalog-"
        f"Beschriftung fuer Temperatur max {sorted(_ALLOWED_LABELS['temperature'])}"
    )
    assert headers[2] in _ALLOWED_LABELS["precipitation"], (
        f"Dritte Spalte traegt {headers[2]!r} statt einer lesbaren Katalog-"
        f"Beschriftung fuer Niederschlag {sorted(_ALLOWED_LABELS['precipitation'])}"
    )

    body = _body_rows(tables[0])
    assert len(body) == 3, f"Erwartet drei Ausblick-Tageszeilen, erhalten: {body}"
    day2 = body[1]
    assert len(day2) == 3, f"Datenzeile hat nicht drei Zellen: {day2}"
    # #1848 A2: die Kennung 'temperature' zeigt Tief UND Hoch in EINER Zelle.
    # Schaerfer als der frueher geprueft "27 kommt vor": beide Tagesenden.
    assert day2[1] == "9/27", (
        f"Temperatur-Zelle des zweiten Ausblick-Tages zeigt {day2[1]!r}, "
        "erwartet die Tagesspanne '9/27' (Tief 9 °C, Hoch 27 °C)"
    )
    assert "4.4" in day2[2], (
        f"Niederschlags-Zelle des zweiten Ausblick-Tages zeigt {day2[2]!r}, "
        "erwartet die Tagessumme 4.4 mm"
    )


# ---------------------------------------------------------------------------
# AC-2: Klartext derselben Mail zeigt dieselbe Auswahl (Validator-blinder Teil)
# ---------------------------------------------------------------------------

def test_plain_outlook_shows_same_selection_as_html():
    """AC-2: Given dasselbe Preset und dieselbe erzeugte Mail / When der
    KLARTEXT-Teil betrachtet wird / Then zeigt auch er ausschliesslich die
    gewaehlten Groessen — identisch zum HTML-Teil derselben Mail. Der
    Pflicht-Validator liest nur HTML und ist hier blind (#1366).
    """
    html, text = _render_mail(outlook_metrics=[SEL_TEMPERATUR, SEL_NIEDERSCHLAG])

    blocks = _plain_outlook_blocks(text)
    assert blocks, (
        "Im Klartext-Teil ist kein Ausblick-Block auffindbar "
        f"(gesucht: {_PLAIN_OUTLOOK_HEADINGS}).\n{text}"
    )
    _heading, body = blocks[0]
    assert len(body) >= 2, f"Ausblick-Block im Klartext hat zu wenige Zeilen: {body}"

    day2_line = body[1]
    assert "27" in day2_line, (
        f"Klartext-Ausblick zeigt den gewaehlten Tageshoechstwert 27 nicht: {day2_line!r}"
    )
    assert "4.4" in day2_line, (
        f"Klartext-Ausblick zeigt die gewaehlte Tagessumme 4.4 mm nicht: {day2_line!r}"
    )

    joined = "\n".join(body)
    # #1848 A1 AC-9: neuer Trenner "/" statt "–" -- Negativprobe muss gegen
    # den AKTUELLEN Altform-Trenner pruefen, sonst waere sie gegen einen
    # bereits abgeloesten Trenner trivial wahr.
    assert "9/27°C" not in joined, (
        "Der Klartext-Ausblick zeigt weiterhin den festen Temperatur-Spannen-Token "
        f"der abgewaehlten Sieben-Spalten-Form: {day2_line!r} (AC-2)"
    )
    assert "⚡" not in joined, (
        "Der Klartext-Ausblick zeigt weiterhin die abgewaehlte Gewitter-Spalte: "
        f"{joined!r} (AC-2)"
    )

    # Gegenprobe: dieselbe Mail, derselbe Umfang — HTML und Klartext duerfen
    # nicht auseinanderlaufen (Fehlerklasse #1366).
    html_headers = _headers(_outlook_tables(html)[0])
    assert len(html_headers) - 1 == 2, html_headers


# ---------------------------------------------------------------------------
# AC-5: kein leeres 26-Zeichen-Namensfeld im Klartext
# ---------------------------------------------------------------------------

def test_plain_outlook_row_has_no_empty_stage_name_gap():
    """AC-5: Given eine Vergleichs-Mail mit Klartext-Ausblick / When eine
    Ausblick-Zeile betrachtet wird / Then enthaelt sie kein leeres, 26 Zeichen
    breites Namensfeld (Trip-Etappenname-Reservierung) — die Zeile beginnt nach
    dem Wochentag direkt mit den Werten.

    Staging-Fund (Kontext-Dokument): `Mo` + 26 Leerzeichen + Werte.
    """
    import re

    from output.renderers.comparison import render_comparison_text

    # Beleg des Ist-Zustands fuer den RED-Nachweis: schon ohne jede Auswahl
    # steht im Klartext-Ausblick des ORTSVERGLEICHS das nie befuellte
    # 26-Zeichen-Etappenname-Feld (Compare setzt `row["name"]` nicht).
    ist_zustand = _plain_outlook_blocks(
        render_comparison_text(_result(), outlook_enabled=True)
    )
    ist_zeilen = ist_zustand[0][1] if ist_zustand else []

    try:
        _html, text = _render_mail(outlook_metrics=[SEL_TEMPERATUR, SEL_NIEDERSCHLAG])
    except AssertionError as exc:
        raise AssertionError(
            f"{exc}\nIst-Zustand der Klartext-Ausblick-Zeilen im Ortsvergleich "
            "(leeres 26-Zeichen-Namensfeld zwischen Wochentag und erstem Wert):\n"
            + "\n".join(repr(line) for line in ist_zeilen)
        ) from exc

    blocks = _plain_outlook_blocks(text)
    assert blocks, f"Kein Ausblick-Block im Klartext gefunden:\n{text}"
    _heading, body = blocks[0]

    for line in body:
        gap = re.search(r"\S( {10,})\S", line)
        assert gap is None, (
            f"Ausblick-Zeile {line!r} enthaelt eine Leerraum-Luecke von "
            f"{len(gap.group(1))} Zeichen — das leere Trip-Etappenname-Feld "
            "(f\"{name:<26}\") wird im Ortsvergleich nie befuellt (AC-5)."
        )


# ---------------------------------------------------------------------------
# AC-8: bewusst geleerte Auswahl laesst den Ausblick vollstaendig entfallen
# ---------------------------------------------------------------------------

def test_empty_outlook_selection_removes_the_whole_block():
    """AC-8: Given `display_config.outlook_metrics = []` (bewusste Leerauswahl)
    / When die Vergleichs-Mail erzeugt wird / Then entfaellt der 3-Tages-
    Ausblick fuer alle Orte vollstaendig — weder Ueberschrift noch Tabelle,
    nicht nur eine leere Tabelle mit Wochentag-Spalte.
    """
    from services.report_config_resolver import resolve_compare_render_options

    preset = _preset(outlook_metrics=[])

    assert _resolved_outlook_metrics(preset) == [], (
        "Eine bewusst geleerte Ausblick-Auswahl muss als leere Liste erhalten "
        "bleiben ('leer heisst leer', analog #1366) — nicht als None (= alle)."
    )
    opts = resolve_compare_render_options(preset)
    assert opts.outlook_enabled is False, (
        "Bei leerer Ausblick-Auswahl muesste der Ausblick abgeschaltet sein "
        "(analog der Stundenverlauf-Kopplung, report_config_resolver.py:250-259) "
        f"— aufgeloest wurde outlook_enabled={opts.outlook_enabled}."
    )

    html, text = _render_mail(outlook_enabled=opts.outlook_enabled, outlook_metrics=[])
    assert not _outlook_tables(html), (
        "Trotz bewusst leerer Auswahl steht eine Ausblick-Tabelle in der HTML-Mail"
    )
    assert "3-Tages-Ausblick" not in html, (
        "Trotz bewusst leerer Auswahl steht eine Ausblick-Ueberschrift in der HTML-Mail"
    )
    assert not _plain_outlook_blocks(text), (
        f"Trotz bewusst leerer Auswahl steht ein Ausblick-Block im Klartext:\n{text}"
    )


# ---------------------------------------------------------------------------
# AC-9: Altbestand ohne Auswahl behaelt die bisherigen sieben Groessen
# ---------------------------------------------------------------------------

def test_missing_outlook_selection_uses_the_catalog_col_labels():
    """AC-9 (Auswahl-Aufloesung) + #2136 AC-2/AC-7 (Beschriftung).

    Given ein Preset OHNE `display_config.outlook_metrics` (Feld fehlt,
    Altbestand) / When die Vergleichs-Mail erzeugt wird / Then zeigt der
    3-Tages-Ausblick unveraendert DIESELBEN sieben Groessen in derselben
    Reihenfolge (AC-9, Regressionsschutz) — aber unter der Beschriftung des
    zentralen Metrik-Katalogs statt unter den sieben handgepflegten Kuerzeln.

    ⚠️ NACHGEZOGEN durch #2136/ADR-0068: bis hierher stand an dieser Stelle
    die Literal-Liste `["Tag","N","D","R","PR","Wind","Böen","Gew"]`. Sie war
    der Regressionsschutz gegen einen STILLEN Wechsel — der Wechsel ist jetzt
    beschlossen und die Erwartung wandert auf die abgeleitete Kopfzeile. Die
    Spaltenzahl (acht) und die Reihenfolge bleiben Gegenstand des Tests.
    """
    from services.report_config_resolver import resolve_compare_render_options

    preset = _preset(region="Tirol")  # kein outlook_metrics-Schluessel

    assert _resolved_outlook_metrics(preset) is None, (
        "Ein FEHLENDES Auswahl-Feld muss None ergeben (= kein Filter, "
        "Bestandsverhalten) — nicht [] (= bewusst leer)."
    )
    assert resolve_compare_render_options(preset).outlook_enabled is True, (
        "Ohne Auswahl bleibt der Ausblick sichtbar (Default True)."
    )

    kopf = pruefe_pfad1_kopfzeile_html()
    assert len(kopf) == 8, (
        f"Der Standardfall-Ausblick zeigt {len(kopf)} Spalten statt der "
        f"unveraenderten acht (Tag + 7): {kopf!r}. #2136 aendert ausschliess"
        "lich die Beschriftung, nicht das Layout (AC-7, Abgrenzung)."
    )

    _html, text = _render_mail(outlook_metrics=None)
    assert _plain_outlook_blocks(text), "Ohne Auswahl fehlt der Klartext-Ausblick"


# ---------------------------------------------------------------------------
# #2136 AC-1: konfigurierbarer Ausblick traegt die Etappentabellen-Ueberschrift
# ---------------------------------------------------------------------------

def test_ac1_configured_outlook_header_matches_the_hourly_table_of_the_same_mail():
    """AC-1: Given eine Ortsvergleichs-Mail (HTML) mit konfigurierter
    `outlook_metrics`-Auswahl / When der Ausblick-Block gerendert wird / Then
    traegt jede Spalte denselben `col_label`-Text wie dieselbe Groesse in der
    Stunden-/Etappentabelle DERSELBEN Mail — nicht mehr den deutschen
    Langnamen aus `compare_metric_catalog['label']`.
    """
    pruefe_pfad2_kopfzeile_html([SEL_TEMPERATUR, SEL_NIEDERSCHLAG])


# ---------------------------------------------------------------------------
# #2136 AC-3: Klartext des konfigurierbaren Ausblicks
# ---------------------------------------------------------------------------

def test_ac3_configured_plain_outlook_tokens_carry_the_col_label():
    """AC-3: Given dieselbe Mail im KLARTEXT / When der Ausblick-Block
    gerendert wird / Then traegt jedes Werte-Token dasselbe `col_label`-Praefix
    wie die Spalte der Stundentabelle derselben Mail — heute steht dort der
    deutsche Langname ("Temperatur 6/18"), waehrend die Stundenzeile derselben
    Mail "Temp 6°" schreibt.
    """
    gewaehlt = [SEL_TEMPERATUR, SEL_NIEDERSCHLAG]
    _html, text = _render_mail(outlook_metrics=gewaehlt)

    blocks = _plain_outlook_blocks(text)
    assert blocks, f"Kein Ausblick-Block im Klartext gefunden:\n{text}"
    _heading, body = blocks[0]
    assert body, "Der Klartext-Ausblick hat keine Datenzeilen"
    zeile = body[0]

    stundenzeilen = [z for z in text.splitlines()
                     if re.match(r"\s*\d{2}:\d{2}\s", z)]
    assert stundenzeilen, (
        "Die Klartext-Stundentabelle derselben Mail ist nicht auffindbar — "
        "ohne sie kann der Test die Gleichheit der Beschriftungen nicht "
        "belegen."
    )

    for metric_id in gewaehlt:
        marke = col_label(metric_id)
        assert re.search(rf"(?<!\S){re.escape(marke)}\s", zeile), (
            f"Die Klartext-Ausblick-Zeile {zeile!r} fuehrt die Groesse "
            f"{metric_id!r} nicht unter ihrer Tabellenueberschrift {marke!r} "
            "(AC-3, ADR-0068)."
        )
        assert any(re.search(rf"(?<!\S){re.escape(marke)}\s", z)
                   for z in stundenzeilen), (
            f"Die Klartext-Stundentabelle derselben Mail kennt {marke!r} "
            f"nicht: {stundenzeilen[0]!r}. Dann vergleicht der Test zwei "
            "Welten statt einer Mail (AC-3)."
        )


# ---------------------------------------------------------------------------
# #2136 AC-4: Klartext des Standardfall-Ausblicks
# ---------------------------------------------------------------------------

def test_ac4_default_plain_outlook_tokens_carry_the_col_label():
    """AC-4: Given eine Mail OHNE konfigurierte Auswahl (Pfad 1) / When der
    KLARTEXT-Ausblick gerendert wird / Then traegt jedes Werte-Token das
    `col_label`-Praefix seiner Groesse — heute steht dort eine nackte
    Wertreihe ohne jede Beschriftung ("Mo  6/18°C   0.4mm 15    ⚡–"), in der
    kein Leser erkennt, welche Zahl welche Groesse ist.

    🔴 ABWEICHUNG zur Spec-Formulierung von AC-4 ("dieselben sieben ersetzten
    Kuerzel wie AC-2"): der feste Klartext-Zweig rendert nur VIER Tokens
    (Temperatur-Spanne, Niederschlag, Wind, Gewitter) und fuehrt Tief/Hoch
    bereits in EINER Spanne zusammen — Regenwahrscheinlichkeit und Böen kommen
    dort ueberhaupt nicht vor. "Sieben Kuerzel in identischer Reihenfolge zum
    bisherigen festen Format" sind zusammen nicht erfuellbar. Geprueft wird
    deshalb, was die Zusicherung im Klartext bedeuten KANN: jedes tatsaechlich
    gerenderte Token traegt die Katalog-Ueberschrift seiner Groesse. Die
    Temperatur-Spanne traegt folgerichtig `col_label` OHNE Auswertungs-Suffix
    — AC-7 (zwei unterscheidbare Koepfe) ist eine Aussage ueber die HTML-
    Tabelle mit zwei getrennten Spalten, die es hier nicht gibt.
    """
    _html, text = _render_mail(outlook_metrics=None)

    blocks = _plain_outlook_blocks(text)
    assert blocks, f"Kein Ausblick-Block im Klartext gefunden:\n{text}"
    _heading, body = blocks[0]
    assert body, "Der Klartext-Ausblick hat keine Datenzeilen"
    zeile = body[0]

    for metric_id in ("temperature", "precipitation", "wind", "thunder"):
        marke = col_label(metric_id)
        assert re.search(rf"(?<!\S){re.escape(marke)}\s*\S", zeile), (
            f"Die Klartext-Zeile des Standardfall-Ausblicks {zeile!r} fuehrt "
            f"die Groesse {metric_id!r} nicht unter ihrer Tabellen"
            f"ueberschrift {marke!r} (AC-4, ADR-0068)."
        )


# ---------------------------------------------------------------------------
# #2136 AC-5: Spalten-Legende loest auch die Ausblick-Kuerzel auf
# ---------------------------------------------------------------------------

def test_ac5_column_legend_resolves_outlook_only_abbreviations():
    """AC-5: Given eine Mail, deren Ausblick Groessen zeigt, die in der
    Stundentabelle NICHT vorkommen / When die Spalten-Legende gebildet wird /
    Then loest sie zusaetzlich zu den Stundentabellen-Kuerzeln auch die im
    Ausblick sichtbaren Kuerzel auf (`Gust = Böen`, `Thdr = Gewitter`) — heute
    sieht die Legende ausschliesslich die Stundentabelle und laesst die
    Ausblick-Kuerzel unerklaert.

    Die Erwartung wird aus dem Register abgeleitet (`col_label` = Kuerzel,
    `label_de` = ausgeschriebener Name), nicht getippt.
    """
    from app.metric_catalog import get_metric
    from output.renderers.comparison import render_compare_email

    gewaehlt = ["gust", "thunder"]
    html, text = render_compare_email(
        _result(), outlook_enabled=True, outlook_metrics=gewaehlt,
        # Stundentabelle bewusst auf eine ANDERE Groesse verengt: nur so ist
        # messbar, ob die Legende den Ausblick ueberhaupt ansieht.
        hourly_metrics={"temp_max_c"},
    )

    for metric_id in gewaehlt:
        definition = get_metric(metric_id)
        eintrag = f"{definition.col_label} = {definition.label_de}"
        assert eintrag in html, (
            f"Die Spalten-Legende der HTML-Mail loest {eintrag!r} nicht auf, "
            f"obwohl die Spalte im Ausblick sichtbar ist. `build_column_legend"
            "()` sieht nur die Stundentabelle (`visible_cols(seg_tables)`), "
            "nicht die Ausblick-Spalten (AC-5, ADR-0042/ADR-0068)."
        )
        assert eintrag in text, (
            f"Die Spalten-Legende des KLARTEXT-Teils derselben Mail loest "
            f"{eintrag!r} nicht auf (AC-5)."
        )


# ---------------------------------------------------------------------------
# AC-10: unbekannter Auswahl-Eintrag wird verworfen und protokolliert
# ---------------------------------------------------------------------------

def test_unknown_outlook_selection_entry_is_dropped_and_logged(caplog):
    """AC-10: Given eine gespeicherte Auswahl mit einem Eintrag, der auf kein
    bekanntes Groesse-Auswertung-Paar passt / When die Vergleichs-Mail erzeugt
    wird / Then wird dieser Eintrag verworfen UND ueber eine Log-Warnung
    sichtbar gemacht; die restliche, gueltige Auswahl bleibt wirksam, kein
    Absturz.

    Zweiter ungueltiger Eintrag: `confidence` — ADR-0005/#710, keine waehlbare
    Wetter-Groesse und deshalb auch im Ausblick nicht auswaehlbar.
    """
    preset = _preset(outlook_metrics=[
        {"metric_id": "einhorn", "aggregation": "max"},
        SEL_TEMPERATUR,
        {"metric_id": "confidence", "aggregation": "min"},
    ])

    with caplog.at_level(logging.WARNING):
        resolved = _resolved_outlook_metrics(preset)

    assert resolved is not None and len(resolved) == 1, (
        "Von drei gespeicherten Eintraegen ist genau einer gueltig "
        f"(Temperatur max) — aufgeloest wurden {resolved!r}."
    )
    warnings = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
    assert "einhorn" in warnings, (
        "Der unbekannte Auswahl-Eintrag wurde still verworfen — es fehlt die "
        f"Protokollwarnung (#1361 Befund 3). Gesehene Warnungen:\n{warnings}"
    )

    html, _text = _render_mail(outlook_metrics=resolved)
    headers = _headers(_outlook_tables(html)[0])
    assert len(headers) == 2 and headers[1] in _ALLOWED_LABELS["temperature"], (
        f"Nach dem Verwerfen soll genau die gueltige Spalte bleiben: {headers}"
    )
