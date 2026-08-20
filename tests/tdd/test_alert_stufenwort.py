"""TDD RED — Issue #1948 Scheibe S6: Der Änderungs-Alarm spricht die Stufe
als Wort (`THUNDER_LABEL_DE`), nicht mehr als nackte Ordinalzahl (0-3).

Spec: docs/specs/modules/fix_1948_s6_alarm_stufenwort.md (AC-1 bis AC-7,
AC-13 bis AC-17). Kontext: docs/context/feat-1948-s6-telegram-paritaet.md.

Leitunterscheidung der Spec: `value_from`/`value_to`/Korridor-`bound`/`value`
sind POSITIONEN auf der Gewitter-Leiter -> Wort. `threshold` und
`abs(value_to-value_from)` sind ABSTAENDE -> Zahl + Einheit "Stufe(n)"
(AC-6 ist der Wächter dagegen, dass beide Sorten verwechselt werden).

Alles echte Renderer-Aufrufe (render_subject/render_email/render_telegram/
render_sms) mit echten AlertEvent/AlertMessage/CorridorEvent-Objekten. Kein
Mock, keine Dateiinhalt-Checks. Wörter werden aus `THUNDER_LABEL_DE`
(SSoT) abgeleitet, nicht als Literal kopiert (Mutations-Gegenprobe 1 der
Spec zielt auf genau diese SSoT-Bindung).

AC-14 und AC-15 sind Regressionswächter und dürfen bereits jetzt (ohne
Implementierung) grün sein -- das ist beabsichtigt, s. jeweiligen Docstring.
Alle übrigen Tests hier müssen vor der Implementierung ROT sein.
"""
from __future__ import annotations

from app.models import ThunderLevel
from output.metric_format import THUNDER_LABEL_DE
from output.renderers.alert.model import AlertEvent, AlertMessage, CorridorEvent
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)

W_NONE = THUNDER_LABEL_DE[ThunderLevel.NONE]
W_LOW = THUNDER_LABEL_DE[ThunderLevel.LOW]
W_MED = THUNDER_LABEL_DE[ThunderLevel.MED]
W_HIGH = THUNDER_LABEL_DE[ThunderLevel.HIGH]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _single_thunder_msg(
    *, value_from: float, value_to: float, threshold: float,
    trip_short: str = "KHW 403", stand_at: str = "09:30",
    occurred_at: str | None = "15:00", km_from: float = 0.0, km_to: float = 4.0,
) -> AlertMessage:
    e = AlertEvent(
        metric_id="thunder", value_from=value_from, value_to=value_to,
        threshold=threshold, cmp="über", occurred_at=occurred_at,
        km_from=km_from, km_to=km_to,
    )
    return AlertMessage(trip_short=trip_short, stand_at=stand_at, events=(e,), source=None)


def _multi_thunder_visibility_msg() -> AlertMessage:
    """thunder (Stufen-Metrik) + visibility (Mess-Metrik) über Schwelle,
    keine segment_id -> Multi-Metrik-Zeile ohne Ort-/Zeit-Zusatz."""
    e_thunder = AlertEvent(
        metric_id="thunder", value_from=2.0, value_to=3.0, threshold=1.0,
        cmp="über", occurred_at=None, km_from=0.0, km_to=4.0,
    )
    e_vis = AlertEvent(
        metric_id="visibility", value_from=1400.0, value_to=280.0, threshold=500.0,
        cmp="unter", occurred_at=None, km_from=8.0, km_to=8.0,
    )
    return AlertMessage(trip_short="KHW 403", stand_at="09:00", events=(e_thunder, e_vis), source=None)


def _first_plain_data_line(plain: str) -> str:
    """Erste Datenzeile im Plain-Text des Ein-Event-Zweigs von render_email():
    [h1, "", verdict, "", ROW1, row2, row3, ...] -> Index 4."""
    return plain.split("\n")[4]


# ===========================================================================
# AC-1: E-Mail-Datenzeile, Einzelereignis
# ===========================================================================

def test_ac1_email_erste_datenzeile_zeigt_stufenwort_nicht_ordinalzahl():
    """AC-1: GIVEN ein Änderungs-Alarm mit einem einzelnen thunder-Ereignis
    von Stufe 2 auf Stufe 3, WHEN die E-Mail gerendert wird, THEN enthält die
    erste Datenzeile 'mittel ↑ hoch' und an keiner Stelle der Zeile die
    Ziffernfolge '2 ↑ 3'."""
    msg = _single_thunder_msg(value_from=2.0, value_to=3.0, threshold=1.0)
    html, plain = render_email(msg)
    first_line = _first_plain_data_line(plain)
    expected = f"{W_MED} ↑ {W_HIGH}"
    assert expected in first_line, (
        f"Stufenwort fehlt in der ersten Datenzeile: erwartet {expected!r} in {first_line!r}"
    )
    assert "2 ↑ 3" not in first_line, (
        f"Rohe Ordinalzahl '2 ↑ 3' darf in der ersten Datenzeile nicht mehr vorkommen: {first_line!r}"
    )
    assert expected in html, f"Stufenwort fehlt im HTML: erwartet {expected!r} in {html!r}"
    assert "2 ↑ 3" not in html, f"Rohe Ordinalzahl im HTML gefunden: {html!r}"


# ===========================================================================
# AC-2: Telegram-Metrikzeile, Einzelereignis
# ===========================================================================

def test_ac2_telegram_metrikzeile_einzelereignis_exaktes_literal():
    """AC-2: GIVEN derselbe Alarm, WHEN der ausführliche Telegram-Text
    gerendert wird, THEN lautet die Metrik-Zeile exakt
    'Gewitter · Schwelle 1 Stufe · mittel ↑ hoch · Änderung über'."""
    msg = _single_thunder_msg(value_from=2.0, value_to=3.0, threshold=1.0)
    tg = render_telegram(msg)
    metric_line = tg.split("\n")[1]
    expected = f"Gewitter · Schwelle 1 Stufe · {W_MED} ↑ {W_HIGH} · Änderung über"
    assert metric_line == expected, (
        f"Telegram-Metrikzeile weicht ab.\n  erwartet: {expected!r}\n  bekommen: {metric_line!r}"
    )


# ===========================================================================
# AC-3: Telegram-Metrikzeile, mehrere Ereignisse (Stufenwort vs. Messzahl)
# ===========================================================================

def test_ac3_telegram_multi_metrik_zeile_stufenwort_andere_metrik_unveraendert():
    """AC-3: GIVEN ein Änderungs-Alarm mit mehreren Ereignissen, darunter
    thunder von Stufe 2 auf Stufe 3, WHEN der ausführliche Telegram-Text
    gerendert wird, THEN steht in der Metrik-Zeile 'mittel→hoch' und nicht
    '2→3', während Nicht-Stufen-Metriken unverändert ihre Messzahl mit
    Einheit behalten (hier: '1.400→280 m')."""
    msg = _multi_thunder_visibility_msg()
    tg = render_telegram(msg)
    metric_line = tg.split("\n")[1]
    assert f"{W_MED}→{W_HIGH}" in metric_line, (
        f"Stufenwort fehlt in der Multi-Metrik-Zeile: {metric_line!r}"
    )
    assert "2→3" not in metric_line, (
        f"Rohe Ordinalzahl '2→3' darf nicht mehr vorkommen: {metric_line!r}"
    )
    assert "1.400→280 m" in metric_line, (
        f"Nicht-Stufen-Metrik 'Sicht' soll unveraendert ihre Messzahl mit Einheit zeigen: {metric_line!r}"
    )


# ===========================================================================
# AC-4: E-Mail-Datenzeile, mehrere Ereignisse
# ===========================================================================

def test_ac4_email_multi_event_gewitterzeile_wort_und_stufen_einheit():
    """AC-4: GIVEN denselben Mehr-Ereignis-Alarm, WHEN die E-Mail gerendert
    wird, THEN trägt die Gewitter-Zeile 'mittel ↑ hoch' als Wertteil und
    'Änderung 1 Stufe · Schwelle 1 Stufe' im Labelteil."""
    msg = _multi_thunder_visibility_msg()
    html, plain = render_email(msg)
    assert "Änderung 1 Stufe · Schwelle 1 Stufe" in plain, (
        f"Labelteil (Abstand als Zahl+Einheit) fehlt: {plain!r}"
    )
    assert f"{W_MED} ↑ {W_HIGH}" in plain, (
        f"Wertteil (Position als Wort) fehlt: {plain!r}"
    )
    assert "2 ↑ 3" not in plain, f"Rohe Ordinalzahl darf nicht mehr vorkommen: {plain!r}"


# ===========================================================================
# AC-5: Betreff — ein Ereignis und mehrere Ereignisse
# ===========================================================================

def test_ac5_betreff_einzelereignis_stufenwort():
    """AC-5 (Einzelereignis-Zweig): Betreff lautet
    '[KHW 403] km 0–4 · ↑ Gewitter: mittel→hoch'."""
    msg = _single_thunder_msg(value_from=2.0, value_to=3.0, threshold=1.0)
    subject = render_subject(msg)
    expected = f"[KHW 403] km 0–4 · ↑ Gewitter: {W_MED}→{W_HIGH}"
    assert subject == expected, f"Betreff weicht ab.\n  erwartet: {expected!r}\n  bekommen: {subject!r}"


def test_ac5_betreff_mehrere_ereignisse_top3_stufenwort():
    """AC-5 (Mehr-Ereignis-Zweig): die Bis-Werte der Top-3-Aufzählung tragen
    die Wörter -- '[KHW 403] Segment 1, 🏁 Ziel · ↑ 2 über Schwelle: Gewitter
    hoch, Gewitter mittel'."""
    e_a = AlertEvent(
        metric_id="thunder", value_from=1.0, value_to=3.0, threshold=1.0,
        cmp="über", occurred_at=None, km_from=0.0, km_to=0.0, segment_id="1",
    )
    e_b = AlertEvent(
        metric_id="thunder", value_from=1.0, value_to=2.0, threshold=1.0,
        cmp="über", occurred_at=None, km_from=0.0, km_to=0.0, segment_id="Ziel",
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="09:00", events=(e_a, e_b), source=None)
    subject = render_subject(msg)
    expected = (
        f"[KHW 403] Segment 1, \U0001f3c1 Ziel · ↑ 2 über Schwelle: "
        f"Gewitter {W_HIGH}, Gewitter {W_MED}"
    )
    assert subject == expected, f"Betreff weicht ab.\n  erwartet: {expected!r}\n  bekommen: {subject!r}"


# ===========================================================================
# AC-6: Wächter — Schwelle/Änderungsbetrag dürfen NIE als Stufenwort erscheinen
# ===========================================================================

def test_ac6_schwelle_erscheint_niemals_als_stufenwort_singular():
    """AC-6 (Wächter, Singular): threshold=1 ('1 Stufe') darf niemals als
    'Schwelle leicht' erscheinen — ein Abstand von 1 ist nicht Stufe 1."""
    msg = _single_thunder_msg(value_from=2.0, value_to=3.0, threshold=1.0)
    html, plain = render_email(msg)
    tg = render_telegram(msg)
    for label, text in (("html", html), ("plain", plain), ("telegram", tg)):
        assert f"Schwelle {W_LOW}" not in text, (
            f"Verbotene Fehlumsetzung 'Schwelle {W_LOW}' in {label} gefunden: {text!r}"
        )
    assert "Schwelle 1 Stufe" in tg, f"Korrekte Zahl+Einheit-Form fehlt in Telegram: {tg!r}"


def test_ac6_schwelle_erscheint_niemals_als_stufenwort_plural():
    """AC-6 (Wächter, Plural): threshold=2 ('2 Stufen') darf niemals als
    'Schwelle mittel' erscheinen."""
    e = AlertEvent(
        metric_id="thunder", value_from=0.0, value_to=3.0, threshold=2.0,
        cmp="über", occurred_at=None, km_from=0.0, km_to=4.0,
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="09:00", events=(e,), source=None)
    html, plain = render_email(msg)
    tg = render_telegram(msg)
    for label, text in (("html", html), ("plain", plain), ("telegram", tg)):
        assert f"Schwelle {W_MED}" not in text, (
            f"Verbotene Fehlumsetzung 'Schwelle {W_MED}' in {label} gefunden: {text!r}"
        )
    assert "Schwelle 2 Stufen" in tg, f"Korrekte Zahl+Einheit-Form (Plural) fehlt in Telegram: {tg!r}"


# ===========================================================================
# AC-7: Grenzwert-/Korridor-Alarm
# ===========================================================================

def test_ac7_korridor_alarm_grenze_und_wert_beide_als_wort():
    """AC-7: GIVEN ein Grenzwert-/Korridor-Alarm auf thunder mit Grenze
    Stufe 1 und aktuellem Wert Stufe 3, WHEN E-Mail oder Telegram gerendert
    werden, THEN lautet die Zeile 'Gewitter: deine Grenze leicht ist
    gerissen — jetzt hoch' -- beide Werte sind Positionen, also beide Wörter."""
    ce = CorridorEvent(
        metric_id="thunder", value=3.0, bound=1.0, direction="above",
        occurred_at=None, km_from=0.0, km_to=4.0,
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(), corridor_events=(ce,))
    html, plain = render_email(msg)
    tg = render_telegram(msg)
    expected_line = f"Gewitter: deine Grenze {W_LOW} ist gerissen — jetzt {W_HIGH} (km 0–4)"
    assert expected_line in plain, f"Korridor-Zeile fehlt im E-Mail-Plaintext: {plain!r}"
    assert expected_line in tg, f"Korridor-Zeile fehlt im Telegram-Text: {tg!r}"
    assert f"Grenze {W_LOW} · jetzt {W_HIGH}" in html, f"Korridor-Wertzelle im HTML fehlt/falsch: {html!r}"


# ===========================================================================
# AC-13: Rückfall bei unbekanntem Stufenwert — niemals "kein"
# ===========================================================================

def test_ac13_unbekannter_stufenwert_faellt_auf_zahl_zurueck_nie_auf_kein():
    """AC-13: GIVEN ein thunder-Ereignis mit einem Wert außerhalb 0–3
    (value_to=90, über den Vorschau-Pfad erreichbar), WHEN ein Kanal
    gerendert wird, THEN fällt die Darstellung auf die bisherige Zahlform
    zurück und meldet niemals 'kein' -- eine Entwarnung für einen
    unbekannten Wert wäre eine sicherheitsrelevante Falschaussage. Der
    gültige Von-Wert (2 -> 'mittel') im selben Ereignis zeigt, dass die
    Wort-Umsetzung an dieser Stelle aktiv ist."""
    msg = _single_thunder_msg(value_from=2.0, value_to=90.0, threshold=1.0)
    html, plain = render_email(msg)
    first_line = _first_plain_data_line(plain)
    assert W_MED in first_line, (
        f"Gültiger Von-Wert (2) soll als Wort erscheinen: {first_line!r}"
    )
    assert "90" in first_line, (
        f"Unbekannter Wert (90) soll numerisch zurückfallen: {first_line!r}"
    )
    assert "kein" not in first_line, (
        f"Rückfall auf 'kein' wäre eine sicherheitsrelevante Falsch-Entwarnung: {first_line!r}"
    )


# ===========================================================================
# AC-14: SMS bleibt unverändert (Regressionswächter, bereits grün)
# ===========================================================================

def test_ac14_sms_bleibt_unveraendert_regressionswaechter():
    """AC-14 (bereits grün, Regressionswächter): GIVEN ein thunder-Alarm von
    Stufe 2 auf Stufe 3, WHEN die SMS gerendert wird, THEN lautet sie
    unverändert 'km 0-4: TH:M->H@15' -- S6 ändert an der Kurznachricht
    nichts."""
    msg = _single_thunder_msg(value_from=2.0, value_to=3.0, threshold=1.0)
    sms = render_sms(msg)
    assert sms == "km 0-4: TH:M->H@15", f"SMS weicht vom unveränderten Ist-Stand ab: {sms!r}"


# ===========================================================================
# AC-15: Nicht-Stufen-Metrik bleibt zahlenformatiert (Regressionswächter)
# ===========================================================================

def test_ac15_nicht_stufen_metrik_zahlformat_unveraendert_regressionswaechter():
    """AC-15 (bereits grün, Regressionswächter): GIVEN ein Alarm für eine
    Metrik ohne Stufencharakter (hier: Böen, km/h), WHEN irgendein Kanal
    gerendert wird, THEN bleibt die Zahlformatierung inkl. Einheit
    unverändert gegenüber dem Prod-Stand."""
    e = AlertEvent(
        metric_id="gust", value_from=20.0, value_to=80.0, threshold=40.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="09:30", events=(e,), source=None)
    html, plain = render_email(msg)
    first_line = _first_plain_data_line(plain)
    assert "20 km/h ↑ 80 km/h" in first_line, (
        f"Zahlformat der Nicht-Stufen-Metrik hat sich veraendert: {first_line!r}"
    )
    tg = render_telegram(msg)
    metric_line = tg.split("\n")[1]
    assert "Schwelle 40 km/h" in metric_line and "20 km/h ↑ 80 km/h" in metric_line, (
        f"Telegram-Zahlformat der Nicht-Stufen-Metrik hat sich veraendert: {metric_line!r}"
    )


# ===========================================================================
# AC-16: Ortsvergleich-Alarm zieht ohne eigenen Code mit
# ===========================================================================

def test_ac16_ortsvergleich_alarm_zeigt_ebenfalls_stufenwort():
    """AC-16: GIVEN ein Ortsvergleich-Änderungsalarm (AlertMessage mit
    gesetztem location_label statt segment_id) mit einem thunder-Ereignis,
    WHEN E-Mail und Telegram gerendert werden, THEN erscheint die Stufe
    ebenso als Wort -- die geteilten Renderer bedienen Trip und
    Ortsvergleich ohne ortsvergleich-eigenen Code."""
    e = AlertEvent(
        metric_id="thunder", value_from=2.0, value_to=3.0, threshold=1.0,
        cmp="über", occurred_at="15:00", km_from=0.0, km_to=0.0,
    )
    msg = AlertMessage(trip_short="Vergleich", stand_at="10:00", events=(e,), location_label="Sixt")
    html, plain = render_email(msg)
    tg = render_telegram(msg)
    expected = f"{W_MED} ↑ {W_HIGH}"
    assert expected in plain, f"Ortsvergleich-E-Mail zeigt kein Stufenwort: {plain!r}"
    assert expected in tg, f"Ortsvergleich-Telegram zeigt kein Stufenwort: {tg!r}"


# ===========================================================================
# AC-17: Rundung — exakt die bisherige Bankersrundung
# ===========================================================================

def test_ac17_rundung_bankers_2_5_ergibt_mittel_nicht_hoch():
    """AC-17: GIVEN ein thunder-Wert mit Nachkommaanteil (2,5), WHEN er in
    ein Wort übersetzt wird, THEN greift exakt die bisherige Rundung
    (round(v, 0), kaufmännisch-gerade Bankersrundung), sodass 2,5 auf 2
    rundet und 'mittel' ergibt -- nicht 'hoch'."""
    msg = _single_thunder_msg(value_from=1.0, value_to=2.5, threshold=1.0)
    html, plain = render_email(msg)
    first_line = _first_plain_data_line(plain)
    assert W_MED in first_line, (
        f"2,5 soll bankers-gerundet auf 2 ({W_MED}) fallen, nicht 3 ({W_HIGH}): {first_line!r}"
    )
    assert W_HIGH not in first_line, (
        f"2,5 darf NICHT auf {W_HIGH} runden: {first_line!r}"
    )


# ===========================================================================
# Mutations-Gegenprobe 1 (Spec): SSoT-Bindung an THUNDER_LABEL_DE
# ===========================================================================

def test_mutation1_ssot_bindung_an_thunder_label_de():
    """Mutations-Gegenprobe 1 der Spec: `render.py` MUSS `THUNDER_LABEL_DE`
    (SSoT, `output/metric_format.py`) importieren, nicht eine wertgleiche
    lokale Kopie halten. Ein Test, der sein Erwartungswort selbst aus
    `THUNDER_LABEL_DE` ableitet (wie alle anderen Tests in dieser Datei via
    `W_MED`/`W_HIGH` usw.), ist gegenueber genau dieser Bindung tautologisch
    -- beide Seiten des Vergleichs kommen aus derselben Quelle. Dieser Test
    mutiert daher den INHALT der echten SSoT-Tabelle zur Laufzeit und prueft,
    dass der Renderer-Output den Marker zeigt.

    Rebinding (`output.metric_format.THUNDER_LABEL_DE = {...neues Dict...}`)
    wuerde NICHT durchschlagen: `render.py` bindet den Namen per
    `from output.metric_format import THUNDER_LABEL_DE` an einen EIGENEN
    Modul-Attribut-Namen, der weiterhin auf das ALTE Dict-Objekt zeigt. Nur
    eine Mutation des Dict-INHALTS (`THUNDER_LABEL_DE[...] = ...`) ist fuer
    beide Module sichtbar -- genau das ist die Bindung, die dieser Test
    beweist. Wiederherstellung ZWINGEND per try/finally, sonst verseucht ein
    haengengebliebener Marker jeden nachfolgenden Test im selben Lauf."""
    marker = "MUTATIONS-MARKER-1948-S6"
    original = THUNDER_LABEL_DE[ThunderLevel.MED]
    THUNDER_LABEL_DE[ThunderLevel.MED] = marker
    try:
        msg = _single_thunder_msg(value_from=2.0, value_to=3.0, threshold=1.0)
        html, plain = render_email(msg)
        tg = render_telegram(msg)
        assert marker in plain, (
            f"E-Mail-Plaintext spiegelt die SSoT-Mutation nicht -- render.py "
            f"haelt vermutlich eine lokale Kopie statt der importierten "
            f"THUNDER_LABEL_DE-Tabelle: {plain!r}"
        )
        assert marker in html, (
            f"E-Mail-HTML spiegelt die SSoT-Mutation nicht: {html!r}"
        )
        assert marker in tg, (
            f"Telegram spiegelt die SSoT-Mutation nicht: {tg!r}"
        )
    finally:
        THUNDER_LABEL_DE[ThunderLevel.MED] = original
