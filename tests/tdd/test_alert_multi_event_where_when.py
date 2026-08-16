"""
TDD-RED: #1861/#1865 — Abweichungs-Alarm-Mail unterscheidbare Mehrfach-
Ereignisse + verstaendlicher Datenblock-Text.

Spec: docs/specs/modules/fix_1861_1865_alarm_mail_klarheit.md (AC-1, AC-2, AC-4).
AC-3 (Wortlaut-Fix) und der Teil von AC-4, der bestehende Bestandstests grün
haelt, liegen in tests/tdd/test_alert_bundle_958ff.py und
tests/tdd/test_issue_1169_compare_alert_consumer.py (dort angepasst). AC-5
(Compare-Regressionsschutz) liegt unveraendert in
tests/tdd/test_issue_1170_compare_alert_config.py. AC-6 ist der gebuendelte
pytest-Lauf selbst.

KEINE Mocks — echte Renderer-/Modell-Aufrufe.
"""
from __future__ import annotations


def _three_thunder_events_trip_path():
    """3 AlertEvents derselben Metrik ('thunder'), Trip-Pfad (segment_id
    gesetzt auf '4'/'5'/'6', analog dem PO-Bug-Report 'KHW 403 Segment 4-6,
    3x Gewitter'). Alle drei liegen ueber der Schwelle."""
    from output.renderers.alert.model import AlertEvent, AlertMessage

    # over_thr() ist Δ-Semantik (#958): abs(value_to - value_from) >= threshold.
    # Alle drei Deltas liegen bewusst >= 40, damit alle Zeilen denselben
    # Formatierungszweig (ueber Schwelle) durchlaufen und sich NUR durch den
    # #1861-Differenzierer unterscheiden, nicht durch unterschiedliche Zweige.
    # value_to STEIGEND ABFALLEND gewaehlt (90/80/70), damit die severity-
    # absteigende Ausgabereihenfolge (#978/#982, render.py::_sorted) mit der
    # Segmentreihenfolge 4,5,6 uebereinstimmt -- sonst prueft die positionale
    # zip()-Zuordnung in test_ac1_multi_event_email_rows_are_distinguishable_by_segment
    # die falsche Zeile (gefunden vom Developer-Agenten beim Implementieren).
    e4 = AlertEvent(metric_id="thunder", value_from=30.0, value_to=90.0, threshold=40.0,
                     cmp="über", occurred_at="10:00", km_from=6.0, km_to=8.0, segment_id="4")
    e5 = AlertEvent(metric_id="thunder", value_from=30.0, value_to=80.0, threshold=40.0,
                     cmp="über", occurred_at="12:00", km_from=8.0, km_to=10.0, segment_id="5")
    e6 = AlertEvent(metric_id="thunder", value_from=30.0, value_to=70.0, threshold=40.0,
                     cmp="über", occurred_at="14:00", km_from=10.0, km_to=12.0, segment_id="6")
    return AlertMessage(trip_short="KHW 403", stand_at="09:00", events=(e4, e5, e6), source=None)


def _two_same_segment_different_time_events():
    """2 AlertEvents derselben Metrik, DEMSELBEN Segment, aber
    unterschiedlicher Uhrzeit — Differenzierer muss auf occurred_at
    ausweichen, wenn das Segment allein nicht unterscheidet."""
    from output.renderers.alert.model import AlertEvent, AlertMessage

    # Beide Deltas >= 40 (over_thr()-Δ-Semantik, #958) -- beide Zeilen
    # durchlaufen denselben Formatierungszweig, unterscheiden sich also NUR
    # durch die Uhrzeit, nicht durch den Schwellen-Status.
    e_morning = AlertEvent(metric_id="thunder", value_from=30.0, value_to=75.0, threshold=40.0,
                            cmp="über", occurred_at="09:00", km_from=6.0, km_to=8.0, segment_id="4")
    e_afternoon = AlertEvent(metric_id="thunder", value_from=30.0, value_to=85.0, threshold=40.0,
                              cmp="über", occurred_at="13:00", km_from=6.0, km_to=8.0, segment_id="4")
    return AlertMessage(trip_short="KHW 403", stand_at="09:00",
                         events=(e_morning, e_afternoon), source=None)


def _multi_event_data_lines(plain: str) -> list[str]:
    """Extrahiert die Datenblock-Zeilen (nach der Leerzeile hinter dem
    Verdict-Text, vor der Footer-Leerzeile) aus der Plain-Mail."""
    parts = plain.split("\n\n")
    # Layout: [h1, verdict, datablock..., footer(+corridor)] -- Datenblock ist
    # der dritte Abschnitt (Index 2) bei render_email().
    return [line for line in parts[2].split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# AC-1: Multi-Event-E-Mail unterscheidet gleichnamige Metriken
# ---------------------------------------------------------------------------

def test_ac1_multi_event_email_rows_are_distinguishable_by_segment():
    """AC-1: Given eine deviation-alert-E-Mail mit drei AlertEvents derselben
    Metrik ('thunder'), segment_id gesetzt auf '4'/'5'/'6' (Trip-Pfad,
    Reproduktion PO-Bug-Report #1861 'KHW 403 Segment 4-6, 3x Gewitter') /
    When render_email() den Multi-Event-Datenblock rendert / Then sind die
    drei resultierenden Zeilen paarweise UNTERSCHIEDLICHE Strings UND jede
    Zeile enthaelt den Segment-Bezug ihres jeweiligen Events."""
    from output.renderers.alert.render import render_email

    msg = _three_thunder_events_trip_path()
    _html, plain = render_email(msg)
    lines = _multi_event_data_lines(plain)

    assert len(lines) == 3, f"Erwartet 3 Datenblock-Zeilen, bekommen: {lines!r}"
    assert len(set(lines)) == 3, (
        f"#1861: Zeilen sind NICHT paarweise unterscheidbar (identische Zeilen "
        f"trotz unterschiedlicher Ereignisse): {lines!r}"
    )
    for expected_segment, line in zip(("Segment 4", "Segment 5", "Segment 6"), lines):
        assert expected_segment in line, (
            f"Zeile traegt nicht den erwarteten Segment-Bezug '{expected_segment}': {line!r}"
        )


def test_ac1_same_segment_different_time_still_distinguishable():
    """AC-1 (Zusatz): Given zwei Events derselben Metrik UND desselben
    Segments, aber unterschiedlicher Uhrzeit / When render_email() rendert /
    Then unterscheiden sich die beiden Zeilen dennoch (Uhrzeit als
    Differenzierer, wenn das Segment allein nicht reicht)."""
    from output.renderers.alert.render import render_email

    msg = _two_same_segment_different_time_events()
    _html, plain = render_email(msg)
    lines = _multi_event_data_lines(plain)

    assert len(lines) == 2, f"Erwartet 2 Datenblock-Zeilen, bekommen: {lines!r}"
    assert lines[0] != lines[1], (
        f"Zeilen mit identischem Segment aber unterschiedlicher Uhrzeit sind "
        f"nicht unterscheidbar: {lines!r}"
    )
    assert "09:00" in lines[0] or "09:00" in lines[1], lines
    assert "13:00" in lines[0] or "13:00" in lines[1], lines


# ---------------------------------------------------------------------------
# AC-2: Telegram-Multi-Event zieht mit (Kanalkonsistenz, Issue #978)
# ---------------------------------------------------------------------------

def test_ac2_multi_event_telegram_rows_are_distinguishable_by_segment():
    """AC-2: Given dieselbe Fixture wie AC-1 / When render_telegram() die
    Multi-Event-Metrik-Zeile rendert / Then enthaelt die Zeile fuer jedes
    Event denselben Segment-Bezug wie in der E-Mail UND die drei
    Teilangaben sind paarweise unterscheidbar."""
    from output.renderers.alert.render import render_telegram

    msg = _three_thunder_events_trip_path()
    telegram_text = render_telegram(msg)
    metric_line = telegram_text.split("\n")[-1]

    for segment in ("Segment 4", "Segment 5", "Segment 6"):
        assert segment in metric_line, (
            f"Telegram-Metrik-Zeile traegt nicht '{segment}': {metric_line!r}"
        )


# ---------------------------------------------------------------------------
# AC-4 (Regressionsschutz #958): over_thr()/side_label() unveraendert
# ---------------------------------------------------------------------------

def test_ac4_over_thr_and_side_label_unaffected_by_where_when_fix():
    """AC-4: Given dieselben Events wie in AC-1/AC-2 / When over_thr()/
    side_label() aufgerufen werden / Then liefern sie weiterhin die fachlich
    korrekte Delta-Semantik aus #958 (alle drei Events liegen ueber der
    Schwelle, side_label == 'über') — der #1861-Differenzierer aendert NUR
    den gerenderten Text, nicht diese Berechnung."""
    from output.renderers.alert.model import over_thr, side_label

    msg = _three_thunder_events_trip_path()
    for e in msg.events:
        assert over_thr(e) is True, (
            f"Event segment_id={e.segment_id!r}: over_thr() muss True liefern "
            f"(value_to={e.value_to} > threshold={e.threshold}), bekommen: {over_thr(e)!r}"
        )
        assert side_label(e) == "über", (
            f"Event segment_id={e.segment_id!r}: side_label() muss 'über' liefern, "
            f"bekommen: {side_label(e)!r}"
        )
