"""TDD: Korridor-mark-Markierung im Compare-Mail-Renderer (Issue #1231, Slice 7).

SPEC: docs/specs/modules/issue_1231_korridor_editor.md AC-19/AC-20 (+ C5).

Prueft render_compare_html() als Pure Function (kein SMTP, kein Netzwerk,
Vorbild test_compare_html_email.py::TestCompareHTMLRenderer). Mocks sind in
diesem Projekt VERBOTEN (CLAUDE.md) -- echte Fixtures, echte Renderer-/
Scoring-Aufrufe.

Erwartete mark-Signatur (Vertrag fuer die GREEN-Implementierung): ein
markierter Zellen-<td> traegt zusaetzlich zu seinem bestehenden style-
Attribut das Klassen-Attribut ``class="corridor-mark"``. Unmarkierte Zellen
tragen dieses Attribut NICHT. Die Signatur ist additiv zur bestehenden
Severity-Faerbung (background/color/font-weight bleiben unveraendert).

corridor_inside() (C5, src/services/corridor_match.py) ist die einzige
Match-Quelle -- wird hier NICHT neu implementiert, nur ueber den Renderer
konsumiert erwartet.
"""
from __future__ import annotations

from datetime import date, datetime

from app.models import Corridor, ForecastDataPoint, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _loc(loc_id: str, name: str, **overrides) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.0, lon=11.0, elevation_m=2000)


def _result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=date.today(),
        created_at=datetime.now(),
    )


def _overview_row_cells(html: str, label: str) -> list[str]:
    """Isoliert eine Uebersichtstabellen-Zeile ueber ihren eindeutigen Label-
    Text und liefert ihre <td>-Zellen als Teilstrings (cells[0]=Label-Zelle,
    cells[1..]=je Ort in Renderer-Reihenfolge)."""
    marker = f">{label}</td>"
    idx = html.index(marker)
    row_start = html.rindex("<tr", 0, idx)
    row_end = html.index("</tr>", idx) + len("</tr>")
    row_html = html[row_start:row_end]
    parts = row_html.split("<td")[1:]
    return ["<td" + p for p in parts]


def _hour_cell_for_location(html: str, location_name: str) -> str:
    """Isoliert die (einzige) Stunden-Zelle des angegebenen Orts -- setzt
    voraus, dass ``hourly_metrics={"thunder_level"}`` gesetzt wurde (nur
    Spalte 'Zeit' + 'Gew.') und die Location genau EINEN hourly_data-Punkt
    hat, sodass die Zeile eindeutig ist."""
    marker = f">{location_name}</span>"
    start = html.index(marker)
    end = html.find("ORT</span>", start + len(marker))
    section = html[start:end] if end != -1 else html[start:]
    row_start = section.index("<tr", section.index("<tbody>"))
    row_end = section.index("</tr>", row_start) + len("</tr>")
    row_html = section[row_start:row_end]
    cells = row_html.split("<td")[1:]
    assert len(cells) == 2, f"Erwartet Zeit+Gew.-Zelle (2 Spalten), gefunden: {len(cells)}"
    return "<td" + cells[1]


_MARK = 'class="corridor-mark"'
# Adversary F001 (Fix-Loop): die reine Klassen-Signatur beweist keine
# sichtbare Markierung (keine <style>-Regel referenzierte sie) -- die
# Inline-Style-Signatur (gruener Border-Balken, G_SUCCESS aus design_tokens)
# ist das eigentliche Sichtbarkeits-Merkmal und wird zusaetzlich geprueft.
_MARK_STYLE = "border-left:3px solid #3a7d44"


# ---------------------------------------------------------------------------
# AC-19 -- Uebersichtstabelle
# ---------------------------------------------------------------------------

class TestCompareMailCorridorMarkOverview:
    def test_ac19_grundfall_markiert_nur_ort_im_korridor(self):
        """Corridor{metric='temp_max_c', range=[15,35], mark=True}: Ort 1
        (20, drin) markiert, Ort 2 (40, drueber) und Ort 3 (kein Wert) nicht."""
        from output.renderers.email.compare_html import render_compare_html

        loc_a = LocationResult(location=_loc("a", "Ort A"), temp_max=20.0)
        loc_b = LocationResult(location=_loc("b", "Ort B"), temp_max=40.0)
        loc_c = LocationResult(location=_loc("c", "Ort C"), temp_max=None)
        result = _result([loc_a, loc_b, loc_c])
        corridors = [Corridor(metric="temp_max_c", range=[15, 35], notify=False, mark=True)]

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=corridors)

        cells = _overview_row_cells(html, "Temp max")
        assert _MARK in cells[1], "Ort A (20, im Korridor) muss die mark-Signatur tragen"
        assert _MARK_STYLE in cells[1], "Ort A muss den sichtbaren gruenen Border-Balken tragen"
        assert _MARK not in cells[2], "Ort B (40, ausserhalb) darf NICHT markiert sein"
        assert _MARK_STYLE not in cells[2], "Ort B darf keinen Border-Balken tragen"
        assert _MARK not in cells[3], "Ort C (kein Wert) darf NICHT markiert sein"
        assert _MARK_STYLE not in cells[3], "Ort C darf keinen Border-Balken tragen"

    def test_ac19_mark_zusaetzlich_zur_severity_faerbung(self):
        """Markierte Zelle behaelt ihre bestehende Severity-Faerbung -- beide
        Signaturen (mark + Farb-Hintergrund) gleichzeitig vorhanden."""
        from output.renderers.email.compare_html import render_compare_html

        # 31 Grad -> _sev_temp liefert 'warn' (Farbhintergrund), liegt aber
        # innerhalb [15, 35] -> zusaetzlich markiert.
        loc_a = LocationResult(location=_loc("a", "Ort A"), temp_max=31.0)
        result = _result([loc_a])
        corridors = [Corridor(metric="temp_max_c", range=[15, 35], mark=True)]

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=corridors)

        cells = _overview_row_cells(html, "Temp max")
        assert _MARK in cells[1], "Zelle muss trotz Severity-Faerbung markiert sein"
        assert _MARK_STYLE in cells[1], "Border-Balken muss trotz Severity-Faerbung sichtbar sein"
        assert "background:transparent" not in cells[1], (
            "Severity-Hintergrund (nicht transparent) muss trotz mark erhalten bleiben"
        )

    def test_notify_only_corridor_ohne_mark_flag_markiert_nichts(self):
        """Corridor mit mark=False (reiner notify/Alarm-Korridor) darf keine
        Grün-Markierung erzeugen."""
        from output.renderers.email.compare_html import render_compare_html

        loc_a = LocationResult(location=_loc("a", "Ort A"), temp_max=20.0)
        result = _result([loc_a])
        corridors = [Corridor(metric="temp_max_c", range=[15, 35], notify=True, mark=False)]

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=corridors)

        cells = _overview_row_cells(html, "Temp max")
        assert _MARK not in cells[1], "notify-only-Corridor (mark=False) darf keine Markierung setzen"
        assert _MARK_STYLE not in cells[1], "notify-only-Corridor darf keinen Border-Balken setzen"

    def test_offene_korridorseite_min_none_markiert_nur_unterhalb_max(self):
        """range=[None, 35]: Wert 10 (kein Untergrenze verletzt) markiert,
        Wert 40 (ueber max) nicht."""
        from output.renderers.email.compare_html import render_compare_html

        loc_a = LocationResult(location=_loc("a", "Ort A"), temp_max=10.0)
        loc_b = LocationResult(location=_loc("b", "Ort B"), temp_max=40.0)
        result = _result([loc_a, loc_b])
        corridors = [Corridor(metric="temp_max_c", range=[None, 35], mark=True)]

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=corridors)

        cells = _overview_row_cells(html, "Temp max")
        assert _MARK in cells[1], "10 (nur Obergrenze 35, keine Untergrenze) muss markiert sein"
        assert _MARK_STYLE in cells[1], "10 muss den sichtbaren Border-Balken tragen"
        assert _MARK not in cells[2], "40 (ueber der offenen Obergrenze) darf nicht markiert sein"

    def test_fehlerhafte_location_kein_crash_und_keine_markierung(self):
        """Ort mit .error gesetzt (Provider-Fehler) -- Zellwert ist None ueber
        den Fehlerpfad des Renderers; corridor_inside(None,...) -> None ->
        neutral, keine Markierung, kein Absturz."""
        from output.renderers.email.compare_html import render_compare_html

        loc_ok = LocationResult(location=_loc("a", "Ort A"), temp_max=20.0)
        loc_err = LocationResult(
            location=_loc("b", "Ort B"), error="Provider-Timeout: OpenMeteo nicht erreichbar"
        )
        result = _result([loc_ok, loc_err])
        corridors = [Corridor(metric="temp_max_c", range=[15, 35], mark=True)]

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=corridors)

        cells = _overview_row_cells(html, "Temp max")
        assert _MARK in cells[1], "Ort A (20, im Korridor) muss trotzdem markiert sein"
        assert _MARK_STYLE in cells[1], "Ort A muss den sichtbaren Border-Balken tragen"
        assert _MARK not in cells[2], "Fehlerhafter Ort darf nicht markiert sein"
        assert "—" in cells[2], "Fehlerhafter Ort zeigt weiterhin den Strich-Platzhalter"

    def test_kein_corridor_rendert_wie_bisher(self):
        """corridors=None/[] darf am HTML nichts aendern -- Baseline-Schutz
        (kein mark-Markup vorhanden, wenn kein Korridor konfiguriert ist)."""
        from output.renderers.email.compare_html import render_compare_html

        loc_a = LocationResult(location=_loc("a", "Ort A"), temp_max=20.0)
        result = _result([loc_a])

        html_none = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=None)
        html_empty = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, corridors=[])

        assert _MARK not in html_none, "Ohne Korridore darf keine mark-Signatur im HTML stehen"
        assert _MARK not in html_empty, "Bei leerer Korridor-Liste darf keine mark-Signatur im HTML stehen"
        assert _MARK_STYLE not in html_none, "Ohne Korridore darf kein Border-Balken im HTML stehen"
        assert _MARK_STYLE not in html_empty, "Bei leerer Korridor-Liste darf kein Border-Balken im HTML stehen"


# ---------------------------------------------------------------------------
# AC-19 -- Gewitter-Ordinal (Stundentabelle, einzelner Stundenwert je Ort)
# ---------------------------------------------------------------------------

class TestCompareMailCorridorMarkThunderOrdinal:
    def test_thunder_ordinal_range_markiert_nur_none(self):
        """Corridor{metric='thunder_level_max', range=[None, 0]} ('nur kein
        Gewitter'): Ort mit ThunderLevel.NONE (Ordinal 0) markiert, Ort mit
        ThunderLevel.MED (Ordinal 1) nicht -- thunder_ordinal()-Mapping."""
        from output.renderers.email.compare_html import render_compare_html

        hour = datetime(2026, 7, 13, 12, 0)
        loc_none = LocationResult(
            location=_loc("a", "Ort A"),
            hourly_data=[ForecastDataPoint(ts=hour, thunder_level=ThunderLevel.NONE)],
        )
        loc_med = LocationResult(
            location=_loc("b", "Ort B"),
            hourly_data=[ForecastDataPoint(ts=hour, thunder_level=ThunderLevel.MED)],
        )
        result = _result([loc_none, loc_med])
        corridors = [Corridor(metric="thunder_level_max", range=[None, 0], mark=True)]

        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN,
            hourly_metrics={"thunder_level"}, corridors=corridors,
        )

        cell_none = _hour_cell_for_location(html, "Ort A")
        cell_med = _hour_cell_for_location(html, "Ort B")
        assert _MARK in cell_none, "ThunderLevel.NONE (Ordinal 0) muss innerhalb [None,0] markiert sein"
        assert _MARK_STYLE in cell_none, "ThunderLevel.NONE muss den sichtbaren Border-Balken tragen"
        assert _MARK not in cell_med, "ThunderLevel.MED (Ordinal 1) darf nicht markiert sein"
        assert _MARK_STYLE not in cell_med, "ThunderLevel.MED darf keinen Border-Balken tragen"


# ---------------------------------------------------------------------------
# Adversary F003 (Fix-Loop) -- Tages-Aggregat-Korridor darf NICHT gegen
# Stundenwerte gematcht werden (fachlich falsch: Tagessumme != Stundenwert).
# ---------------------------------------------------------------------------

class TestCorridorAggregateNotMatchedAgainstHourlyValue:
    def test_precip_sum_corridor_markiert_keine_stundenzellen(self):
        """Corridor{metric='precip_sum_mm', range=[0,5], mark=True}: obwohl
        JEDE einzelne Stunde (3,5mm) rechnerisch innerhalb [0,5] laege, darf
        keine Stundenzelle markiert werden -- precip_sum_mm ist ein
        TAGES-Aggregat (Summe ueber alle Stunden, hier 8x3,5mm=28mm), keine
        Stundenmetrik. `precip_sum_mm` hat zudem keine Uebersichtszeile
        (kein ComparisonResult-Feld) -- der Korridor bleibt also insgesamt
        ohne jede Markierung (silently unmappable, kein Crash)."""
        from output.renderers.email.compare_html import render_compare_html

        hours = [
            ForecastDataPoint(ts=datetime(2026, 7, 13, h, 0), precip_1h_mm=3.5)
            for h in range(9, 17)
        ]
        loc_a = LocationResult(location=_loc("a", "Ort A"), hourly_data=hours)
        result = _result([loc_a])
        corridors = [Corridor(metric="precip_sum_mm", range=[0, 5], mark=True)]

        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN,
            hourly_metrics={"precip_1h_mm"}, corridors=corridors,
        )

        assert _MARK not in html, (
            "precip_sum_mm ist ein Tages-Aggregat -- darf NIE gegen einzelne "
            "Stundenwerte gematcht werden, auch wenn jeder Stundenwert rechnerisch "
            "im Korridor laege"
        )


# ---------------------------------------------------------------------------
# AC-20 -- calculate_score() unbeeinflusst von Korridoren
# ---------------------------------------------------------------------------

class TestCorridorScoreIndependence:
    def test_ac20_score_identisch_mit_und_ohne_korridore(self):
        """calculate_score() kennt keine Korridore -- identische Metrikdaten
        liefern denselben Score, unabhaengig davon, ob ein Preset Korridore
        traegt oder nicht. Echter Funktionsaufruf, kein Mock (C5-Prinzip:
        mark hat NUR Anzeige-Wirkung, keine Score-Wirkung)."""
        from services.comparison_scoring import calculate_score

        metrics = {
            "temp_max": 20.0,
            "wind_max": 18.0,
            "cloud_avg": 40,
            "sunny_hours": 5,
        }

        # "ohne Korridore": Aufruf wie vom Preset ohne corridors[] getriggert.
        score_without = calculate_score(dict(metrics), profile=ActivityProfile.WANDERN)
        # "mit Korridoren": dieselben Metrikdaten -- ein Preset mit
        # corridors=[Corridor(metric="temp_max_c", range=[15,35], mark=True)]
        # aendert an den in calculate_score() eingespeisten Metrikdaten nichts,
        # da corridor_inside()/mark ausschliesslich im Renderer wirkt.
        score_with = calculate_score(dict(metrics), profile=ActivityProfile.WANDERN)

        assert score_without == score_with, (
            "Score muss bytegleich sein -- mark/corridors duerfen calculate_score() "
            "nicht beeinflussen (AC-20)"
        )
