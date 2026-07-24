"""Orts-Reihenfolge im Ortsvergleich (Issue #1359, Scheibe 2).

Die im Orte-Tab per Drag&Drop eingestellte ORTS-Reihenfolge muss identisch in
HTML-Vergleichsmatrix, Klartext-Teil, den Orts-Abschnitten unterhalb der
Matrix, der Telegram-Nachricht und der SMS ankommen -- nicht alphabetisch,
nicht nach Wetter-Score. Heute erzwingt der geteilte Sortier-Helfer
``sort_locations_alphabetically`` (compare_html.py:1014, aufgerufen in
compare_html.py:1092 und comparison.py:154,379,551) eine alphabetische
Reihenfolge in allen Ausgabepfaden.

SPEC: docs/specs/modules/compare_location_order.md

Alle Tests sind reine Renderer-Aufrufe mit fest gebauten ComparisonResult-
Objekten: kein Netz, keine Mails, kein Mock/patch (CLAUDE.md Test-Politik,
Schicht "Kern (deterministisch)"). Geprueft wird ausschliesslich die
REIHENFOLGE der Orte, nicht der Zahleninhalt.

AC-Zuordnung (Kern-Anteile; die Live-E2E-Anteile von AC-1/AC-2 deckt der
Mail-Validator in der Deploy-Phase gegen eine echt zugestellte Staging-Mail):
- AC-4: alle vier Ausgabe-Oberflaechen folgen der Eingabe-Reihenfolge   -> RED
- AC-2: dieselben Orte in zwei Reihenfolgen -> zwei verschiedene Ausgaben -> RED
- AC-5: der nach Score "schlechteste" Ort bleibt vorne, wenn konfiguriert -> RED
- AC-6: ein bereits alphabetisch konfigurierter Vergleich rendert gleich  -> GRUEN (Charakterisierung)
- AC-8: die SMS zeigt die VORDERSTEN Orte der Reihenfolge, "+k" stimmt    -> RED
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.models import ForecastDataPoint
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import (
    render_comparison_text, render_compare_sms, render_compare_telegram,
)
from output.renderers.email.compare_html import render_compare_html

# ---------------------------------------------------------------------------
# Fixtures (fest, ohne Netz). Drei Orte in BEWUSST nicht-alphabetischer
# Reihenfolge (Zillertal, Innsbruck, Stubai) -- AC verlangt mindestens drei.
# Die Namen sind so gewaehlt, dass die konfigurierte Reihenfolge WEDER
# alphabetisch (I < S < Z) NOCH zufaellig gleich ist.
# ---------------------------------------------------------------------------

# (id, Name) in konfigurierter, nicht-alphabetischer Reihenfolge.
ORDER_A = [("z", "Zillertal"), ("i", "Innsbruck"), ("s", "Stubai")]
# Andere Reihenfolge derselben Orte-MENGE fuer die Gegenprobe (AC-2).
ORDER_B = [("i", "Innsbruck"), ("s", "Stubai"), ("z", "Zillertal")]
# Alphabetisch = das, was der heutige Helfer aus JEDER Eingabe macht.
ALPHABETICAL = ["Innsbruck", "Stubai", "Zillertal"]

NAMES_A = [name for _, name in ORDER_A]
NAMES_B = [name for _, name in ORDER_B]


def _dp(hour: int) -> ForecastDataPoint:
    """Minimaler Stunden-Datenpunkt, damit die HTML-Orts-Abschnitte unterhalb
    der Matrix (Stundenverlauf) ueberhaupt rendern (fail-soft ohne hourly_data
    laesst sie weg)."""
    return ForecastDataPoint(
        ts=datetime(2026, 7, 24, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=20.0, cloud_total_pct=50, wind_chill_c=13.0,
    )


def _loc_result(loc_id: str, name: str, score: int = 1) -> LocationResult:
    return LocationResult(
        location=SavedLocation(id=loc_id, name=name, lat=47.0, lon=11.0,
                               elevation_m=600),
        score=score,
        temp_max=20.0, temp_min=10.0, wind_max=15.0, gust_max=25.0,
        cloud_avg=40, sunny_hours=5,
        hourly_data=[_dp(h) for h in range(9, 14)],
    )


def _result(order: list[tuple[str, str]]) -> ComparisonResult:
    return ComparisonResult(
        locations=[_loc_result(i, n) for i, n in order],
        time_window=(0, 23),
        target_date=date(2026, 7, 24),
        created_at=datetime(2026, 7, 24, 4, 0),
    )


# ---------------------------------------------------------------------------
# Auslese-Helfer: Orts-Reihenfolge aus dem jeweiligen Render-Ergebnis. Da die
# drei Ortsnamen einmalig und ueberschneidungsfrei sind, ist die Reihenfolge
# ihres ERSTEN Auftretens im Ausgabe-String die Render-Reihenfolge.
# ---------------------------------------------------------------------------

def _order_of(text: str, names: list[str]) -> list[str]:
    idx = {n: text.find(n) for n in names}
    return [n for n in sorted(names, key=lambda n: idx[n]) if idx[n] >= 0]


def _html_matrix_region(html: str) -> str:
    """Nur die UEBERSICHTS-Matrix (min-width:760px .. </tbody></table>) --
    ihre <th>-Kopfzellen tragen die Ortsnamen als Spalten."""
    start = html.index("min-width:760px")
    end = html.index("</tbody></table>", start) + len("</tbody></table>")
    return html[start:end]


def _html_below_matrix(html: str) -> str:
    """Alles UNTERHALB der Matrix -- dort stehen die Orts-Abschnitte
    (Stundenverlauf je Ort). Dieser Bereich vertritt den in der Spec unter
    AC-4 genannten 'Zusammenfassungs-Textblock unter der Matrix'; der
    eigentliche Ort-Zusammenfassungsblock wurde mit #1300 zurueckgebaut
    (s. tests/unit/test_compare_mail_blocks.py) und existiert in der
    zugestellten Mail nicht mehr -- die per-Ort-Abschnitte sind die reale
    orts-geordnete Ausgabe unter der Matrix."""
    end = html.index("</tbody></table>") + len("</tbody></table>")
    return html[end:]


# ---------------------------------------------------------------------------
# AC-4 — RED: jede der vier Ausgabe-Oberflaechen folgt der Eingabe-Reihenfolge
# ---------------------------------------------------------------------------

class TestAC4RenderersFollowLocationOrder:
    """Heute liefern alle vier Pfade alphabetisch (Innsbruck, Stubai,
    Zillertal), weil ``sort_locations_alphabetically`` die uebergebene
    ``result.locations``-Reihenfolge ueberschreibt."""

    def test_html_matrix_columns_follow_input_order(self):
        html = render_compare_html(_result(ORDER_A))
        assert _order_of(_html_matrix_region(html), NAMES_A) == NAMES_A, (
            "Die Matrix-Spalten muessen der konfigurierten Orts-Reihenfolge "
            f"folgen ({NAMES_A}), nicht alphabetisch ({ALPHABETICAL})."
        )

    def test_plaintext_follows_input_order(self):
        text = render_comparison_text(_result(ORDER_A))
        assert _order_of(text, NAMES_A) == NAMES_A, (
            f"Der Klartext-Teil muss {NAMES_A} zeigen.\nText:\n{text}"
        )

    def test_telegram_follows_input_order(self):
        msg = render_compare_telegram(_result(ORDER_A))
        assert _order_of(msg, NAMES_A) == NAMES_A, (
            f"Die Telegram-Nachricht muss {NAMES_A} zeigen.\nNachricht:\n{msg}"
        )

    def test_html_below_matrix_sections_follow_input_order(self):
        html = render_compare_html(_result(ORDER_A))
        assert _order_of(_html_below_matrix(html), NAMES_A) == NAMES_A, (
            "Die Orts-Abschnitte unterhalb der Matrix muessen der "
            f"konfigurierten Reihenfolge folgen ({NAMES_A})."
        )

    def test_all_four_surfaces_agree_within_one_mail(self):
        """AC-4 Kern: es darf nicht zwei verschiedene Orts-Sortierungen
        innerhalb derselben Auslieferung geben."""
        result = _result(ORDER_A)
        html = render_compare_html(result)
        matrix = _order_of(_html_matrix_region(html), NAMES_A)
        below = _order_of(_html_below_matrix(html), NAMES_A)
        text = _order_of(render_comparison_text(result), NAMES_A)
        tg = _order_of(render_compare_telegram(result), NAMES_A)
        assert matrix == below == text == tg == NAMES_A, (
            f"Uneinheitlich: Matrix={matrix} Abschnitte={below} "
            f"Klartext={text} Telegram={tg}, erwartet {NAMES_A}."
        )


# ---------------------------------------------------------------------------
# AC-2 — RED (Gegenprobe): dieselben Orte, zwei Reihenfolgen -> zwei Ausgaben
# ---------------------------------------------------------------------------

class TestAC2OrderFlipsWithInput:
    """Heute liefern beide Reihenfolgen dieselbe alphabetische Ausgabe -- die
    Mail 'kippt' nicht mit der Einstellung mit."""

    def test_html_matrix_flips_with_reversed_order(self):
        a = _order_of(_html_matrix_region(render_compare_html(_result(ORDER_A))), NAMES_A)
        b = _order_of(_html_matrix_region(render_compare_html(_result(ORDER_B))), NAMES_A)
        assert a != b, (
            "Dieselbe Orte-MENGE in zwei Reihenfolgen muss zwei verschiedene "
            f"Matrix-Spaltenfolgen ergeben, ergab aber beide Male {a}."
        )
        assert a == NAMES_A and b == NAMES_B, (
            f"Erwartet A={NAMES_A}/B={NAMES_B}, war A={a}/B={b}."
        )

    def test_plaintext_flips_with_reversed_order(self):
        a = _order_of(render_comparison_text(_result(ORDER_A)), NAMES_A)
        b = _order_of(render_comparison_text(_result(ORDER_B)), NAMES_A)
        assert a != b and a == NAMES_A and b == NAMES_B, (
            f"Klartext muss mitkippen: A={a}, B={b}."
        )

    def test_telegram_flips_with_reversed_order(self):
        a = _order_of(render_compare_telegram(_result(ORDER_A)), NAMES_A)
        b = _order_of(render_compare_telegram(_result(ORDER_B)), NAMES_A)
        assert a != b and a == NAMES_A and b == NAMES_B, (
            f"Telegram muss mitkippen: A={a}, B={b}."
        )


# ---------------------------------------------------------------------------
# AC-5 — RED: keine unsichtbare Neusortierung nach Wetter-Score
# ---------------------------------------------------------------------------

class TestAC5ScoreDoesNotReorderRenderedOutput:
    """Die Score-Sortierung sitzt im Engine-Kern (comparison_engine.py:278),
    der pro Ort ``fetch_forecast_for_location`` -> Open-Meteo aufruft und
    deshalb NICHT netzfrei im Kern testbar ist (s. Modul-Docstring / Bericht).
    Geprueft wird stattdessen die Ebene DARUNTER -- der Renderer -- mit einem
    fertigen ``ComparisonResult``: der Renderer darf die Reihenfolge nicht nach
    ``LocationResult.score`` umstellen. Der konfiguriert erste Ort traegt hier
    absichtlich den SCHLECHTESTEN Score; er muss trotzdem vorne bleiben.

    Heute RED, weil der alphabetische Sortier-Helfer den (score-schlechten,
    aber konfiguriert ersten) 'Zillertal' ans Ende schiebt."""

    def _scored_result(self) -> ComparisonResult:
        # Konfigurierte Reihenfolge Zillertal, Innsbruck, Stubai; Score so
        # gesetzt, dass Score-absteigend (Innsbruck 90) UND alphabetisch
        # (Innsbruck) einen ANDEREN ersten Ort ergaeben als die Konfiguration.
        return ComparisonResult(
            locations=[
                _loc_result("z", "Zillertal", score=10),   # schlechtester Score, konfiguriert vorne
                _loc_result("i", "Innsbruck", score=90),
                _loc_result("s", "Stubai", score=50),
            ],
            time_window=(0, 23),
            target_date=date(2026, 7, 24),
            created_at=datetime(2026, 7, 24, 4, 0),
        )

    def test_worst_score_location_stays_first_when_configured_first(self):
        result = self._scored_result()
        html_first = _order_of(_html_matrix_region(render_compare_html(result)), NAMES_A)[0]
        text_first = _order_of(render_comparison_text(result), NAMES_A)[0]
        assert html_first == "Zillertal" and text_first == "Zillertal", (
            "Der konfiguriert erste Ort ('Zillertal', schlechtester Score) muss "
            f"vorne bleiben; war HTML={html_first}, Klartext={text_first}."
        )


# ---------------------------------------------------------------------------
# AC-6 — GRUEN (Charakterisierung): ein bereits alphabetischer Vergleich
# rendert vor und nach der Aenderung dieselbe Orts-Reihenfolge.
# ---------------------------------------------------------------------------

class TestAC6AlphabeticalPresetUnchanged:
    """CHARAKTERISIERUNGS-/REGRESSIONSTEST (kein RED-Test).

    Ein Vergleich, dessen konfigurierte Orts-Reihenfolge zufaellig BEREITS
    alphabetisch ist, muss vor und nach dieser Aenderung zeichengleich
    aussehen -- fuer ihn aendert sich nichts Sichtbares, obwohl der
    Mechanismus (Eingabe-Reihenfolge statt Sortierung) ein anderer ist.

    Die eingefrorene Erwartung ist die alphabetische Reihenfolge; sie bleibt
    vor der Aenderung (Sortierung liefert sie) UND nach der Aenderung
    (Eingabe IST bereits alphabetisch) gueltig."""

    # Bewusst alphabetisch KONFIGURIERTER Fall.
    ALPHA_ORDER = [("aa", "Aachen"), ("bb", "Bremen"), ("cc", "Chemnitz")]
    FROZEN = ["Aachen", "Bremen", "Chemnitz"]

    def _alpha_result(self) -> ComparisonResult:
        return ComparisonResult(
            locations=[_loc_result(i, n) for i, n in self.ALPHA_ORDER],
            time_window=(0, 23),
            target_date=date(2026, 7, 24),
            created_at=datetime(2026, 7, 24, 4, 0),
        )

    def test_html_alphabetical_input_order_frozen(self):
        html = render_compare_html(self._alpha_result())
        assert _order_of(_html_matrix_region(html), self.FROZEN) == self.FROZEN
        assert _order_of(_html_below_matrix(html), self.FROZEN) == self.FROZEN

    def test_plaintext_and_telegram_alphabetical_input_frozen(self):
        result = self._alpha_result()
        assert _order_of(render_comparison_text(result), self.FROZEN) == self.FROZEN
        assert _order_of(render_compare_telegram(result), self.FROZEN) == self.FROZEN

    def test_sms_alphabetical_input_frozen(self):
        msg = render_compare_sms(self._alpha_result())
        assert _order_of(msg, self.FROZEN) == self.FROZEN
        assert len(msg) <= 140


# ---------------------------------------------------------------------------
# AC-8 — RED: die SMS zeigt die VORDERSTEN Orte der Reihenfolge; "+k" stimmt.
# ---------------------------------------------------------------------------

# Sechs laengere Ortsnamen in nicht-alphabetischer Reihenfolge, sodass die SMS
# am 140-Zeichen-Budget kappen MUSS (nur die vordersten passen, Rest als "+k").
SMS_ORDER_A = ["Zermatt", "Oberstdorf", "Garmisch", "Innsbruck", "Kitzbuehel", "Bregenz"]
SMS_ORDER_B = list(reversed(SMS_ORDER_A))


def _sms_result(names: list[str]) -> ComparisonResult:
    return ComparisonResult(
        locations=[_loc_result(n.lower(), n) for n in names],
        time_window=(0, 23),
        target_date=date(2026, 7, 24),
        created_at=datetime(2026, 7, 24, 4, 0),
    )


def _sms_named_and_plus(msg: str, names: list[str]) -> tuple[list[str], int]:
    """(genannte Orte in Render-Reihenfolge, k aus dem '+k'-Suffix)."""
    named = _order_of(msg, names)
    plus = 0
    marker = msg.rsplit("+", 1)
    if len(marker) == 2 and marker[1].strip().isdigit():
        plus = int(marker[1].strip())
    return named, plus


class TestAC8SmsFollowsLocationOrder:
    """Heute nennt die SMS unabhaengig von der Konfiguration die alphabetisch
    ersten Orte (Bregenz, Garmisch, Innsbruck) -- die Reihenfolge entscheidet
    aber, WELCHE Orte der Nutzer unterwegs ueberhaupt zu sehen bekommt."""

    def test_sms_names_front_locations_of_configured_order(self):
        msg = render_compare_sms(_sms_result(SMS_ORDER_A))
        named, plus = _sms_named_and_plus(msg, SMS_ORDER_A)
        assert named == SMS_ORDER_A[: len(named)], (
            "Die SMS muss die VORDERSTEN konfigurierten Orte nennen "
            f"({SMS_ORDER_A[:len(named)]}), nannte aber {named}.\nSMS:\n{msg}"
        )
        assert plus == len(SMS_ORDER_A) - len(named), (
            f"'+{plus}' passt nicht zu {len(named)} genannten von "
            f"{len(SMS_ORDER_A)} Orten.\nSMS:\n{msg}"
        )

    def test_sms_selection_flips_with_reversed_order(self):
        named_a, _ = _sms_named_and_plus(
            render_compare_sms(_sms_result(SMS_ORDER_A)), SMS_ORDER_A)
        named_b, _ = _sms_named_and_plus(
            render_compare_sms(_sms_result(SMS_ORDER_B)), SMS_ORDER_A)
        assert named_a != named_b, (
            "Zwei Reihenfolgen muessen zwei verschiedene SMS-Auswahlen ergeben, "
            f"ergaben aber beide {named_a}."
        )
        assert named_a == SMS_ORDER_A[: len(named_a)], f"A: {named_a}"
        assert named_b == SMS_ORDER_B[: len(named_b)], f"B: {named_b}"

    def test_sms_stays_within_budget(self):
        """Begleitschutz (bleibt GRUEN): die Reihenfolge-Aenderung darf das
        140-Zeichen-Budget in keinem Fall sprengen."""
        for names in (SMS_ORDER_A, SMS_ORDER_B, NAMES_A):
            msg = render_compare_sms(_sms_result(names))
            assert len(msg) <= 140, f"SMS zu lang ({len(msg)}):\n{msg}"
