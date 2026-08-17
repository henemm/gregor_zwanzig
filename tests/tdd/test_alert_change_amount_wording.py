"""TDD RED — Issue #1935/#1779: Alarm-Datenzeile nennt den Änderungsbetrag,
nicht den Messwert.

SPEC: docs/specs/modules/fix_1935_1779_alarm_nachricht_klarheit.md
      (AC-1 bis AC-4, AC-11)
KONTEXT: docs/context/fix-1935-1779-alarm-nachricht-klarheit.md

Die zweite Datenzeile der Abweichungs-Mail (`Alarm-Schwelle 1.000 m: jetzt
darüber ✗`) behauptet etwas ueber den MESSWERT, obwohl `threshold` per
ADR-0013 (#958) immer eine Δ-Auslöseschwelle ist. Diese Suite prueft die
Umstellung auf einen Änderungsbetrag-Wortlaut — ausschliesslich ueber echte
Renderer-Aufrufe (`render_email`/`render_subject`/`render_telegram`) mit
echten `AlertEvent`/`AlertMessage`-Objekten (Vorbild: `_delta_message()` in
`test_alert_location_vocabulary.py:99-146`). Kein Mock, keine
Dateiinhalt-Checks — Zeilen werden aus dem gerenderten Text extrahiert
(zeilenweise), nicht per Substring-Suche im Volltext.

Pfadregel #1409: der Pruefling wird relativ zur Testdatei aufgeloest (uebliche
`pythonpath`-Konfiguration in `pyproject.toml`, kein fester Hauptrepo-Pfad).
"""
from __future__ import annotations

import re

from app.metric_catalog import format_metric_value, get_metric
from output.renderers.alert.model import AlertEvent, AlertMessage, side_label
from output.renderers.alert.render import render_email, render_subject, render_telegram

# ---------------------------------------------------------------------------
# Fixtures — echte AlertEvent/AlertMessage (Fall aus #1935: Sicht 1.400→280 m)
# ---------------------------------------------------------------------------


def _single_event(*, value_from: float, value_to: float, threshold: float = 1000.0) -> AlertEvent:
    return AlertEvent(
        metric_id="visibility", value_from=value_from, value_to=value_to,
        threshold=threshold, cmp="unter", occurred_at=None,
        km_from=8.0, km_to=8.0, segment_id="Ziel",
    )


def _single_msg(*, value_from: float, value_to: float, threshold: float = 1000.0) -> AlertMessage:
    e = _single_event(value_from=value_from, value_to=value_to, threshold=threshold)
    return AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(e,))


def _multi_msg() -> AlertMessage:
    """Böen 20→80, Schwelle 40, Δ=60 — dasselbe Fixture-Muster wie
    `test_978_deviation_line_readability.py::_multi_msg` (nur ein Event
    genuegt hier, weil der Multi-Zweig ab >=2 Events greift)."""
    e_gust = AlertEvent(
        metric_id="gust", value_from=20.0, value_to=80.0, threshold=40.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    e_thunder = AlertEvent(
        metric_id="thunder", value_from=20.0, value_to=90.0, threshold=40.0,
        cmp="über", occurred_at="11:30", km_from=1.0, km_to=4.0,
    )
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:30", events=(e_gust, e_thunder), source=None,
    )


# ---------------------------------------------------------------------------
# Extraktion — zeilenweise, kein Substring-Scan im Volltext
# ---------------------------------------------------------------------------


def _second_data_line_plain(plain: str) -> str:
    """Zweite Datenzeile (Label: Wert) des Einzel-Ereignis-Datenblocks —
    direkt VOR der 'Wo & wann: '-Zeile (render.py:_datablock_single, feste
    3-Zeilen-Struktur row1/row2/row3)."""
    lines = plain.splitlines()
    hits = [i for i, ln in enumerate(lines) if ln.startswith("Wo & wann: ")]
    assert len(hits) == 1, f"Genau eine 'Wo & wann'-Zeile erwartet: {lines!r}"
    idx = hits[0]
    assert idx >= 1, f"Keine Zeile vor 'Wo & wann': {lines!r}"
    return lines[idx - 1]


def _second_data_row_html(html: str) -> tuple[str, str]:
    """Label/Wert der zweiten `<table>`-Zeile im HTML-Datenblock."""
    tds = re.findall(r"<td[^>]*>(.*?)</td>", html)
    assert len(tds) >= 4, f"Weniger als zwei Tabellenzeilen im HTML: {html!r}"
    return tds[2], tds[3]


def _verdict_line_plain(plain: str) -> str:
    """Verdict-Chip-Zeile (`_verdict_single`) — dritte Zeile des Plain-Texts
    (h1, '', verdict, ...)."""
    lines = plain.splitlines()
    assert len(lines) >= 3, f"Zu wenige Zeilen fuer einen Verdict-Chip: {lines!r}"
    return lines[2]


def _multi_line_for(plain: str, label: str) -> str:
    """Die Multi-Ereignis-Datenzeile fuer ein bestimmtes Label — zeilenweise
    gesucht (`label + ' ·'` als Zeilenanfang), nicht per Volltext-Substring.

    Korrektur (RED-Vertrag-Praezisierung, Issue #1935/#1779 E2): der
    Multi-Ereignis-Datenblock baut die Zeile als `f"{k}: {v}"`, wobei `k`
    (das eigentliche Label, z.B. "Böen · Änderung 60 · Schwelle 40") SELBST
    Änderungsbetrag UND Schwelle traegt (spec-pseudocode E2) -- anders als im
    Einzel-Ereignis-Datenblock, wo der Aenderungsbetrag im `k`-Anteil UND die
    Schwelle im `v`-Anteil eines eigenen row2-Tupels stehen. Ein Abschneiden
    hinter dem ersten ": " wuerde deshalb genau den Teil verwerfen, den AC-4
    pruefen soll -- die volle Zeile ist die richtige Datenbasis."""
    lines = plain.splitlines()
    data_hits = [ln for ln in lines if ln.startswith(f"{label} · ")]
    assert len(data_hits) == 1, (
        f"Genau eine Datenzeile fuer {label!r} erwartet, gefunden: {lines!r}"
    )
    return data_hits[0]


# ---------------------------------------------------------------------------
# AC-1 — Über-Schwelle-Fall (#1935-Fall)
# ---------------------------------------------------------------------------


def test_ac1_datenzeile_nennt_aenderungsbetrag_statt_messwert_ueber_schwelle():
    """AC-1: Änderung 1.120 m: über Alarm-Schwelle 1.000 m ✗ — weder 'jetzt'
    noch die Einheit direkt am Schwellwert-Label; in `plain` UND `html`."""
    msg = _single_msg(value_from=1400.0, value_to=280.0, threshold=1000.0)
    html, plain = render_email(msg)

    row2 = _second_data_line_plain(plain)
    assert row2 == "Änderung 1.120 m: über Alarm-Schwelle 1.000 m ✗", (
        f"Datenzeile 2 (plain): {row2!r}"
    )
    assert "jetzt" not in row2, f"'jetzt' zeigt weiterhin auf den Messwert: {row2!r}"

    label_html, value_html = _second_data_row_html(html)
    assert label_html == "Änderung 1.120 m", f"HTML-Label: {label_html!r}"
    assert value_html == "über Alarm-Schwelle 1.000 m ✗", f"HTML-Wert: {value_html!r}"


# ---------------------------------------------------------------------------
# AC-2 — Unter-Schwelle-Fall (Symmetrie)
# ---------------------------------------------------------------------------


def test_ac2_datenzeile_nennt_aenderungsbetrag_statt_messwert_unter_schwelle():
    """AC-2: Änderung 100 m: unter Alarm-Schwelle 1.000 m ✓ — dieselbe
    Umstellung fuer den unter-Schwelle-Fall, nicht nur fuer den gemeldeten
    Fehlerfall."""
    msg = _single_msg(value_from=280.0, value_to=380.0, threshold=1000.0)
    html, plain = render_email(msg)

    row2 = _second_data_line_plain(plain)
    assert row2 == "Änderung 100 m: unter Alarm-Schwelle 1.000 m ✓", (
        f"Datenzeile 2 (plain): {row2!r}"
    )

    label_html, value_html = _second_data_row_html(html)
    assert label_html == "Änderung 100 m", f"HTML-Label: {label_html!r}"
    assert value_html == "unter Alarm-Schwelle 1.000 m ✓", f"HTML-Wert: {value_html!r}"


# ---------------------------------------------------------------------------
# AC-3 — Verdict-Chip und Datenzeile widersprechen sich nicht
# ---------------------------------------------------------------------------


def test_ac3_verdict_chip_und_datenzeile_nennen_dieselbe_aenderungsaussage():
    """AC-3: fuer über- UND unter-Schwelle-Fixtures muessen Verdict-Chip
    (`_verdict_single`) und zweite Datenzeile dasselbe `side_label`-Wort und
    denselben formatierten Schwellwert enthalten -- kein isolierter Blick auf
    nur einen der beiden Texte."""
    fixtures = [
        _single_event(value_from=1400.0, value_to=280.0, threshold=1000.0),
        _single_event(value_from=280.0, value_to=380.0, threshold=1000.0),
    ]
    for e in fixtures:
        msg = AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(e,))
        html, plain = render_email(msg)
        verdict = _verdict_line_plain(plain)
        row2 = _second_data_line_plain(plain)

        expected_side = side_label(e)
        expected_threshold = format_metric_value(
            get_metric(e.metric_id).unit, e.threshold,
        )

        assert expected_side in verdict, (
            f"Verdict nennt nicht {expected_side!r}: {verdict!r}"
        )
        assert expected_side in row2, (
            f"Datenzeile 2 nennt nicht {expected_side!r}: {row2!r}"
        )
        # Kein Widerspruch: "jetzt" zeigt zeitlich auf den MESSWERT (Root
        # Cause #1935/#1779) -- die Datenzeile darf es nach dem Fix nicht
        # mehr fuehren, unabhaengig davon, dass "über"/"unter" als Substring
        # auch im alten Wortlaut ("jetzt darüber") vorkam.
        assert "jetzt" not in row2, (
            f"Datenzeile 2 zeigt weiterhin auf den Messwert ('jetzt'): {row2!r}"
        )
        assert expected_threshold in verdict, (
            f"Verdict nennt nicht den Schwellwert {expected_threshold!r}: {verdict!r}"
        )
        assert expected_threshold in row2, (
            f"Datenzeile 2 nennt nicht den Schwellwert {expected_threshold!r}: {row2!r}"
        )


# ---------------------------------------------------------------------------
# AC-4 — Mehr-Ereignis-Zweig: Änderungsbetrag zusätzlich zur Schwelle
# ---------------------------------------------------------------------------


def test_ac4_mehrereignis_zeile_nennt_aenderungsbetrag_und_schwelle():
    """AC-4: die Böen-Datenzeile im Mehr-Ereignis-Zweig enthaelt BEIDE Zahlen
    -- den Änderungsbetrag (60) UND die Schwelle (40) -- als zwei
    unterscheidbare Zahlen in derselben Zeile."""
    msg = _multi_msg()
    _, plain = render_email(msg)

    line = _multi_line_for(plain, "Böen")
    numbers = re.findall(r"\d+", line)
    assert "60" in numbers, f"Änderungsbetrag (60) fehlt in der Böen-Zeile: {line!r}"
    assert "40" in numbers, f"Schwelle (40) fehlt in der Böen-Zeile: {line!r}"
    assert numbers.count("60") >= 1 and numbers.count("40") >= 1 and "60" != "40", (
        f"Änderungsbetrag und Schwelle muessen zwei VERSCHIEDENE Zahlen sein: {line!r}"
    )


def _multi_msg_mit_fallendem_ereignis() -> AlertMessage:
    """Böen steigend (20→80, Δ=60) UND Sicht FALLEND (1.400→280 m, Δ=1.120),
    beide über Schwelle -- Regressionsschutz gegen Adversary-Finding F001:
    alle bisherigen Mehr-Ereignis-Fixtures (`_multi_msg`) enthalten nur
    steigende Werte, sodass `abs(e.value_to - e.value_from)` an render.py:584
    ungeprueft bliebe. Ein fallendes Ereignis macht das Vorzeichen sichtbar."""
    e_gust = AlertEvent(
        metric_id="gust", value_from=20.0, value_to=80.0, threshold=40.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    e_visibility = AlertEvent(
        metric_id="visibility", value_from=1400.0, value_to=280.0, threshold=1000.0,
        cmp="unter", occurred_at="11:30", km_from=1.0, km_to=4.0,
    )
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:30",
        events=(e_gust, e_visibility), source=None,
    )


def test_ac4_mehrereignis_fallendes_ereignis_zeigt_vorzeichenlosen_aenderungsbetrag():
    """AC-4 Regressionsschutz (Adversary-Finding F001, Issue #1935/#1779):
    ein FALLENDES Ereignis über der Schwelle (Sicht 1.400→280 m) muss
    denselben vorzeichenlosen Änderungsbetrag zeigen wie ein steigendes --
    'Änderung 1.120', NIEMALS 'Änderung -1.120' (der genau die Verwirrung
    waere, die dieser Fix im Einzel-Ereignis-Zweig beseitigt)."""
    msg = _multi_msg_mit_fallendem_ereignis()
    _, plain = render_email(msg)

    line = _multi_line_for(plain, "Sicht")
    assert "Änderung 1.120" in line, (
        f"Änderungsbetrag muss vorzeichenlos '1.120' lauten: {line!r}"
    )
    assert "-1.120" not in line, (
        f"Änderungsbetrag darf kein Minuszeichen fuehren: {line!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 (Regressionsschutz Betreff/Telegram) — Einheit immer am Wert
# ---------------------------------------------------------------------------


def test_ac11_betreff_fuehrt_einheit_bei_nicht_prozent_metrik():
    """AC-11: `render_subject()`s Top-3-Auswahl haengt die Einheit einer
    Nicht-Prozent-Metrik an (z.B. 'Böen 80 km/h' statt 'Böen 80')."""
    subject = render_subject(_multi_msg())
    assert "Böen 80 km/h" in subject, (
        f"Betreff fuehrt die Einheit nicht am Böen-Wert: {subject!r}"
    )


def test_ac11_telegram_fuehrt_einheit_bei_nicht_prozent_metrik():
    """AC-11: `render_telegram()`s Multi-Zeile haengt die Einheit einer
    Nicht-Prozent-Metrik an."""
    tg = render_telegram(_multi_msg())
    metric_line = tg.splitlines()[1]
    assert "80 km/h" in metric_line, (
        f"Telegram-Metrikzeile fuehrt die Einheit nicht am Böen-Wert: {metric_line!r}"
    )


def test_ac11_prozent_metrik_bleibt_unveraendert_mit_prozentzeichen():
    """AC-11 (Regressionsschutz, HEUTE GRUEN): Prozent-Metriken bleiben mit
    angehaengtem '%' -- die Umstellung betrifft nur Nicht-Prozent-Metriken."""
    e_prob = AlertEvent(
        metric_id="rain_probability", value_from=10.0, value_to=90.0, threshold=30.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    e_gust = AlertEvent(
        metric_id="gust", value_from=20.0, value_to=80.0, threshold=40.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="14:30", events=(e_prob, e_gust))
    subject = render_subject(msg)
    assert "90%" in subject or "90 %" in subject, (
        f"Prozent-Metrik verliert ihr '%'-Zeichen: {subject!r}"
    )
