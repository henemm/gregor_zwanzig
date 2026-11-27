"""Vergleichsmail: Stundenzellen, Stunden-Ueberschrift und Legende aus einem
Baustein (Issue #3425, TDD RED).

SPEC: docs/specs/modules/rework_3425_compare_bausteine.md (AC-1 bis AC-6).

Kern-Schicht, deterministisch, ohne Netz: echte ``ForecastDataPoint``-/
``LocationResult``-Objekte, echte Renderer-Aufrufe ueber
``render_compare_email`` (liefert HTML UND Klartext derselben Mail).
Kein ``Mock``/``patch``/``MagicMock``.

Geplante oeffentliche Bausteine in ``output.renderers.email.compare_html``:
``hour_cell_texts``, ``hourly_block_visible``, ``legend_visible``. Wo ein Test
sie importiert, geschieht das NACH der Verhaltenspruefung -- der Import ist der
Nachweis "eine Quelle", das Verhalten der Nachweis "wirkt in beiden Fassungen".
"""
from __future__ import annotations

import html as _html
import re
from datetime import date, datetime

import pytest

from app.user import ComparisonResult, LocationResult, SavedLocation
from i18n import t, tn
from output.renderers.comparison import render_compare_email
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN
from tests.helpers.vergleichs_mail_fixture import _dp, build_result

LANGS = ["de", "en"]

# Stundenauswahl mit Hagel-Traeger (Gewitter) und zusammengelegter
# Windrichtung (Wind + Merge-Signal Windrichtung).
HOURLY = ["t2m_c", "wind10m_kmh", "wind_direction_deg", "gust_kmh",
          "thunder_level", "precip_1h_mm"]

_TAGS = re.compile(r"<[^>]+>")


def _render(result, *, lang="de", hourly_enabled=True, outlook_enabled=True,
            enabled_metrics=None, hourly=HOURLY) -> tuple[str, str]:
    return render_compare_email(
        result, hourly_metrics=hourly, hourly_enabled=hourly_enabled,
        outlook_enabled=outlook_enabled, enabled_metrics=enabled_metrics,
        preset=PRESET_ALLGEMEIN, lang=lang,
    )


def _plain_text(s: str) -> str:
    return _html.unescape(_TAGS.sub("", s)).strip()


# ---------------------------------------------------------------------------
# Ableser: Stundenzeilen je Ort in HTML und Klartext
# ---------------------------------------------------------------------------

def _html_hour_tables(html: str, lang: str) -> list[tuple[list[str], list[list[str]]]]:
    """(Kopfzeile, Zeilen) je Stundentabelle; erkannt an der Zeit-Spalte."""
    zeit = t("vergleich.stunden.zeit", lang)
    out = []
    for head, body in re.findall(r"<thead>(.*?)</thead><tbody>(.*?)</tbody>", html, re.S):
        cols = [_plain_text(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
        if not cols or cols[0] != zeit:
            continue
        rows = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            rows.append([_plain_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)])
        out.append((cols, rows))
    return out


_PLAIN_HOUR = re.compile(r"^   (\d{2}:\d{2})  (.*)$")


def _plain_hour_blocks(text: str) -> list[list[tuple[str, str]]]:
    """(Zeitlabel, Zellkette) je Stundenzeile, gruppiert je Ortsblock."""
    blocks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] | None = None
    for line in text.splitlines():
        m = _PLAIN_HOUR.match(line)
        if m:
            if current is None:
                current = []
                blocks.append(current)
            current.append((m.group(1), m.group(2)))
        else:
            current = None
    return blocks


def _html_has_hourly_heading(html: str, n_locations: int, lang: str) -> bool:
    return _html.escape(tn("vergleich.stunden.titel", n_locations, lang)) in html


def _plain_has_hourly_heading(text: str, lang: str) -> bool:
    return t("vergleich.stunden.klartext_titel", lang) in text.splitlines()


def _legend_marker(lang: str) -> str:
    """Spalten-Legende ('Spalten: ...' / 'Columns: ...') -- Katalogtext."""
    return t("mail.legende.spalten", lang, liste="").strip()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _ort(i: str, name: str) -> SavedLocation:
    return SavedLocation(id=i, name=name, lat=47.0, lon=11.4, elevation_m=600,
                         timezone="Europe/Vienna")


def _ohne_stundendaten_result() -> ComparisonResult:
    """AC-2-Randfall: ein Ort mit Fehler (wie test_compare_mail_ein_platzhalter-
    zeichen), ein Ort ohne Stundendaten, aber mit Ausblick-Daten."""
    ausblick = [_dp(datetime(2026, 10, 30, s, 0), 0, 8 + s // 2) for s in range(0, 24, 3)]
    ohne = LocationResult(location=_ort("o1", "Innsbruck"), temp_max=11.0,
                          official_alerts=[], hourly_data=[],
                          outlook_hourly_data=ausblick)
    fehler = LocationResult(location=_ort("o2", "Brenner"), error="Timeout")
    return ComparisonResult(locations=[ohne, fehler], time_window=(9, 16),
                            target_date=date(2026, 10, 29),
                            created_at=datetime(2026, 10, 29, 4, 0))


# ---------------------------------------------------------------------------
# AC-1: Stundenzellen gleich in Klartext und HTML
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_stundenzellen_gleich_in_klartext_und_html(lang):
    """AC-1: Given eine Vergleichsmail mit Stundenverlauf, in der Stunden Hagel
    und eine zusammengelegte Windrichtung haben / When Klartext- und
    HTML-Fassung gerendert werden (DE und EN) / Then zeigen beide fuer jede
    Stunde dieselben Zellwerte und Beschriftungen, nur Zeitlabel und
    Ampel-Auszeichnung unterscheiden sich -- und beide stammen aus dem
    oeffentlichen Baustein ``hour_cell_texts``."""
    html, plain = _render(build_result(), lang=lang)
    tabellen = _html_hour_tables(html, lang)
    bloecke = _plain_hour_blocks(plain)
    assert len(tabellen) == 3 and len(bloecke) == 3, (len(tabellen), len(bloecke))

    from output.metric_format import format_hail_note

    hagel = format_hail_note(True, lang=lang)
    assert hagel
    hagel_gesehen = richtung_gesehen = False
    for (kopf, zeilen), block in zip(tabellen, bloecke):
        assert len(zeilen) == len(block)
        for zellen, (zeit, kette) in zip(zeilen, block):
            assert zeit[:2] == zellen[0], "Stunde in beiden Fassungen gleich"
            erwartet = "  ".join(f"{lbl} {wert}" for lbl, wert in zip(kopf[1:], zellen[1:]))
            assert kette == erwartet, f"{zeit}: Klartext {kette!r} != HTML {erwartet!r}"
            # Spaltenfolge = HOURLY ohne Merge-Signal: Zeit, Temp, Wind, Gust, Thdr, Rain
            hagel_gesehen |= hagel in zellen[4]
            richtung_gesehen |= bool(re.fullmatch(r"\d+ [NOSW]{1,3}", zellen[2]))
    assert hagel_gesehen, "Fixture ohne Hagel-/Signal-Zelle -- Vakuum"
    assert richtung_gesehen, "Fixture ohne zusammengelegte Windrichtung -- Vakuum"

    # Eine Quelle: der geplante oeffentliche Baustein (RED: existiert noch nicht).
    from output.renderers.email.compare_html import hour_cell_texts  # noqa: F401

    assert callable(hour_cell_texts)


# ---------------------------------------------------------------------------
# AC-2: ohne Stundendaten keine Ueberschrift, Ausblick bleibt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_ohne_stundendaten_keine_ueberschrift_ausblick_bleibt(lang):
    """AC-2: Given Stundenverlauf und Ausblick sind eingeschaltet, aber alle
    Orte haben einen Fehler oder keine Stundendaten / When die Mail gerendert
    wird / Then steht weder in der Klartext- noch in der HTML-Fassung die
    Ueberschrift "Stundenverlauf", und der Ausblick wird in beiden weiterhin
    gezeigt. (RED: HTML zeigt die Ueberschrift heute.)"""
    result = _ohne_stundendaten_result()
    html, plain = _render(result, lang=lang)

    assert not _plain_has_hourly_heading(plain, lang), "Klartext zeigt Stunden-Ueberschrift"
    assert not _html_has_hourly_heading(html, len(result.locations), lang), (
        "HTML zeigt die Ueberschrift "
        f"{tn('vergleich.stunden.titel', len(result.locations), lang)!r} ohne Stundenabschnitt")

    ausblick = t("vergleich.ausblick.titel", lang)
    assert ausblick in plain, "Klartext verliert den Ausblick"
    assert _html.escape(ausblick) in html, "HTML verliert den Ausblick"
    # Ausblickwerte selbst (Tageszeile) stehen in beiden.
    assert re.search(r"^\S{2,3}\s+Temp ", plain, re.M), "Klartext ohne Ausblickzeile"


# ---------------------------------------------------------------------------
# AC-3: Normalfall Ueberschrift in beiden (Guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_normalfall_ueberschrift_in_beiden(lang):
    """AC-3 (Guard): Given mindestens ein Ort hat Stundendaten (ein anderer
    Ort hat einen Fehler) / When die Mail gerendert wird / Then steht die
    Stunden-Ueberschrift wie bisher in Klartext und HTML."""
    result = build_result(mit_fehlerort=True)
    assert any(lr.error for lr in result.locations)
    html, plain = _render(result, lang=lang)
    assert _plain_has_hourly_heading(plain, lang)
    assert _html_has_hourly_heading(html, len(result.locations), lang)


def test_hourly_block_visible_ist_gemeinsames_praedikat():
    """AC-2/AC-3: der geplante Baustein ``hourly_block_visible`` entscheidet
    fuer beide Fassungen -- falsch fuer nur Fehler/leere Orte oder bei
    abgeschaltetem Stundenverlauf, wahr sobald ein Ort Stundendaten hat; und
    die gerenderte Mail folgt ihm in BEIDEN Fassungen."""
    from output.renderers.email.compare_html import hourly_block_visible

    leer = _ohne_stundendaten_result()
    voll = build_result(mit_fehlerort=True)
    assert hourly_block_visible(leer.locations, True) is False
    assert hourly_block_visible(voll.locations, True) is True
    assert hourly_block_visible(voll.locations, False) is False
    nur_fehler = [lr for lr in voll.locations if lr.error]
    assert nur_fehler and hourly_block_visible(nur_fehler, True) is False
    # Adversary F002: Fehler-Ort MIT Stundendaten zaehlt nicht (``error``-Zweig).
    mit_daten = next(lr for lr in voll.locations if not lr.error and lr.hourly_data)
    fehler_mit_daten = LocationResult(location=mit_daten.location, error="x",
                                      hourly_data=list(mit_daten.hourly_data))
    assert hourly_block_visible([fehler_mit_daten], True) is False

    for result in (leer, voll):
        for enabled in (True, False):
            html, plain = _render(result, hourly_enabled=enabled)
            soll = hourly_block_visible(result.locations, enabled)
            assert _plain_has_hourly_heading(plain, "de") is soll
            assert _html_has_hourly_heading(html, len(result.locations), "de") is soll


# ---------------------------------------------------------------------------
# AC-4: Legende in beiden gleich an/aus
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hourly_enabled,outlook_enabled",
                         [(True, True), (True, False), (False, True), (False, False)])
@pytest.mark.parametrize("lang", LANGS)
def test_legende_schalter_in_beiden_gleich(lang, hourly_enabled, outlook_enabled):
    """AC-4: Given alle vier Kombinationen aus Stundenverlauf an/aus und
    Ausblick an/aus / When Klartext und HTML gerendert werden / Then ist die
    Legende in beiden Fassungen jeweils gleichzeitig vorhanden oder
    gleichzeitig abwesend -- entschieden ueber den Baustein ``legend_visible``."""
    html, plain = _render(build_result(), lang=lang, hourly_enabled=hourly_enabled,
                          outlook_enabled=outlook_enabled)
    marker = _legend_marker(lang)
    in_plain = marker in plain
    in_html = _html.escape(marker) in html
    assert in_plain is in_html, f"Klartext {in_plain}, HTML {in_html}"
    assert in_plain is (hourly_enabled or outlook_enabled)

    from output.renderers.email.compare_html import legend_visible

    assert legend_visible(hourly_enabled, outlook_enabled) is in_plain


# ---------------------------------------------------------------------------
# AC-5: Zeitlabel je Medium unveraendert (Guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_zeitlabel_je_medium_unveraendert(lang):
    """AC-5 (Guard): Given eine Stundenzeile / When die Mail gerendert wird /
    Then lautet das Zeitlabel im Klartext ``HH:MM`` und im HTML ``HH``."""
    html, plain = _render(build_result(), lang=lang)
    bloecke = _plain_hour_blocks(plain)
    tabellen = _html_hour_tables(html, lang)
    assert bloecke and tabellen
    for block in bloecke:
        for zeit, _ in block:
            assert re.fullmatch(r"\d{2}:\d{2}", zeit)
    for _, zeilen in tabellen:
        for zellen in zeilen:
            assert re.fullmatch(r"\d{2}", zellen[0]), zellen[0]


# ---------------------------------------------------------------------------
# AC-6: nicht geteilte Teile unveraendert (Guard)
# ---------------------------------------------------------------------------

def _uebersicht_result() -> ComparisonResult:
    result = build_result(mit_fehlerort=True)
    erster = result.locations[0]
    erster.wind_direction_avg = 213
    erster.sunny_hours = 4
    return result


def test_nicht_geteilte_teile_unveraendert():
    """AC-6 (Guard): Given die bewusst nicht geteilten Teile / When die Mail
    gerendert wird / Then bleiben Ort-Abschnittsform samt Ausblick-Ueberschrift,
    Risiko-Legende nur im HTML wie vorher; die Uebersichts-Zellformate sind
    seit #3431 in Klartext und HTML gleich (Format-Katalog)."""
    html, plain = _render(_uebersicht_result(),
                          enabled_metrics=["wind_direction_avg", "sunny_hours"])
    lines = plain.splitlines()

    # Uebersichts-Zellformate (#3431): Klartext == HTML, `213 °`/`4.0 h`/`–`.
    idx = lines.index("Innsbruck")
    block = lines[idx:idx + 3]
    assert any(l.endswith(": 213 °") for l in block), block
    assert any(l.endswith(": 4.0 h") for l in block), block
    text_html = _plain_text(html)
    assert "213 °" in text_html and "4.0 h" in text_html

    # Ort-Abschnittsform im Klartext: "Name (TZ)" direkt ueber den Stunden,
    # Ausblick-Ueberschrift im selben Block.
    kopf = lines.index("Innsbruck (CET)")
    assert _PLAIN_HOUR.match(lines[kopf + 1])
    assert "3-Tages-Ausblick" in lines[kopf + 1:kopf + 15]
    # HTML trennt: Fehlort ohne Stunden traegt "Name · 3-Tages-Ausblick".
    assert "Brenner · 3-Tages-Ausblick" in text_html

    # Risiko-Legende nur im HTML.
    risk = t("mail.legende.risk_gruen", "de")
    assert risk in html and risk not in plain
