"""EINE Gehzeit-Fenster-Quelle fuer alle vier Ausgaben.

Spec:  docs/specs/modules/hiking_window_single_source.md (AC-1 bis AC-8)
Issue: #1417 — „Gehzeit darf nicht doppelt berechnet werden" (PO 2026-07-29)

Gemeldeter Fall: dieselbe Etappe, dasselbe Briefing — Mail `13–17°C`,
Kurznachricht `K13 D16`. Ursache sind zwei unabhaengige Berechnungen desselben
Gehzeit-Fensters: die Mail-Kachelzeile zaehlt die Ankunftsstunde des letzten
Etappenteils MIT (Bug #1146: sie ist erlebte Gehzeit), SMS und
E-Mail-Kurzzusammenfassung schneiden sie ab.

**Nachweisform.** Alle vier Kanaele stammen aus EINEM echten
``TripReportFormatter.format_email()``-Lauf; gelesen wird ausschliesslich
gerenderter Text (Kachelzeile, SMS-Zeile, Kurzzusammenfassungssatz,
Telegram-Kurzuebersicht). Die Segment-Aggregate baut nicht der Test, sondern
der Produktivpfad ``SegmentWeatherService._aggregate_for_segment()``. Keine
Mocks, kein ``patch()``, kein Netz, keine Mail.

**Warum Morgenbriefing.** Abends ist die Untergrenze in Kurzzusammenfassung
und Telegram bewusst die NACHT-Tiefsttemperatur am Ziel (DEC-1,
night_temp_evening_only.md) — dort waeren Tiefstwerte gar nicht vergleichbar.
Die Paritaets-Tests laufen deshalb morgens, wo alle vier denselben
Gehzeit-Tiefst- und -Hoechstwert nennen muessen. AC-1 prueft zusaetzlich den
Abend (dort ist der HOECHSTwert vergleichbar — genau der gemeldete Fall),
AC-7 sichert den Nachtwert ab.

Erwarteter Zustand vor dem Fix: AC-1, AC-2, AC-3 ROT; AC-5 teilweise ROT
(die drei Konstellationen mit Extremwert an der Ankunftsstunde); AC-4, AC-6,
AC-7 GRUEN (Bestandsverhalten, das erhalten bleiben muss).
"""
from __future__ import annotations

import re

import pytest

from tests.tdd import _hiking_window_fixtures as F

# #1484: temperature_night mit dabei — der AC-7-Nachtwert haengt an der
# eigenen Groesse; fuer die uebrigen (Morgen-/ohne-Nacht-)Faelle ist sie inert.
# #1660 Scheibe A: dieselbe Eigenstaendigkeit jetzt auch fuer die gefuehlte
# Nachtgroesse ("wind_chill_night") -- sonst faellt der AC-7-Nachwert der
# gefuehlten Seite still auf den Gehzeit-Tiefstwert zurueck.
# #1728 Scheibe 1: die Tages-Token K/D bzw. FK/FD haengen jetzt an eigenen
# Groessen -- ohne sie erzeugte die Kurznachricht ueberhaupt keinen
# Temperaturwert und die Paritaets-Aussage haette keinen Gegenstand mehr.
# Der Pruefgegenstand (EINE Gehzeit-Berechnung fuer alle vier Ausgaben) ist
# unveraendert.
_FELT = (
    "temperature", "temperature_day_low", "temperature_day_high",
    "temperature_night",
    "wind_chill", "wind_chill_day_low", "wind_chill_day_high",
    "wind_chill_night",
)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _report(constellation: F.Constellation, report_type: str = "morning", **kw):
    return F.render_report(
        constellation.segments(), report_type=report_type, metrics=_FELT, **kw
    )


# ---------------------------------------------------------------------------
# AC-1 — Mail und Kurznachricht nennen denselben Hoechstwert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_mail_and_sms_agree_when_arrival_hour_is_extreme(report_type):
    """AC-1: Given eine Etappe, deren waermste Stunde die Ankunftsstunde des
    letzten Teils ist / When Mail und Kurznachricht desselben Briefings
    gerendert werden / Then nennen beide denselben Hoechstwert.

    ROT vor dem Fix: die Mail nennt 22 °C (Ankunftsstunde zaehlt mit), die
    SMS 15 °C (Ankunftsstunde abgeschnitten) — die Gestalt des gemeldeten
    Falls `13–17°C` vs. `K13 D16`.
    """
    c = F.CONSTELLATIONS_BY_NAME["extremwert_an_der_ankunftsstunde"]
    night = (F.night_weather(c.arrival_hour, temp_min=9.0, felt_min=6.0)
             if report_type == "evening" else None)
    report = _report(c, report_type, night=night)

    mail, sms = F.mail_temp(report), F.sms_temp(report)

    assert mail.high is not None, (
        f"[{report_type}] Die Mail-Kachelzeile nennt keinen Hoechstwert.\n"
        f"Kachelzeilen: {F.pill_lines(report)}"
    )
    assert sms.high is not None, (
        f"[{report_type}] Die Kurznachricht nennt keinen Hoechstwert (Token D).\n"
        f"SMS: {sms.raw!r}"
    )
    assert sms.high == mail.high, (
        f"[{report_type}] Mail und Kurznachricht desselben Briefings nennen "
        f"verschiedene Hoechstwerte: Mail {mail.high} °C, Kurznachricht "
        f"{sms.high} °C. Der Tages-Hoechstwert liegt in der Ankunftsstunde "
        f"({c.arrival_hour}:00 Ortszeit) — sie ist erlebte Gehzeit und muss in "
        f"BEIDEN Ausgaben zaehlen.\n"
        f"  Kachelzeile: {mail.raw!r}\n  Kurznachricht: {sms.raw!r}"
    )
    assert mail.high == c.expected_max_c, (
        f"[{report_type}] Der Hoechstwert ist {mail.high} statt "
        f"{c.expected_max_c} — beide Kanaele sind sich einig, aber auf dem "
        f"falschen Wert.\n  Kachelzeile: {mail.raw!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Mail, SMS und Telegram nennen dieselbe gemessene Temperatur
# ---------------------------------------------------------------------------

def test_mail_sms_telegram_agree_measured_temperature():
    """AC-2: Given dieselbe Konstellation wie AC-1 / When Mail-Kachelzeile,
    SMS UND Telegram-Kurzuebersicht aus DEMSELBEN Report erzeugt werden /
    Then zeigen alle drei denselben Tiefst- UND Hoechstwert.

    ROT vor dem Fix: Mail und Telegram nennen 5–22 °C, die SMS 5–15 °C — die
    Telegram-Kurzuebersicht ist eine dritte, unabhaengige Berechnung
    derselben Aussage, die hier zufaellig mit der Mail zusammenfaellt.
    """
    c = F.CONSTELLATIONS_BY_NAME["extremwert_an_der_ankunftsstunde"]
    report = _report(c)
    channels = {n: e for n, e in F.measured_by_channel(report).items()
                if n in ("mail", "sms", "telegram")}

    pairs = {n: e.as_pair() for n, e in channels.items()}
    assert len(set(pairs.values())) == 1, (
        "Mail-Kachelzeile, Kurznachricht und Telegram-Kurzuebersicht nennen "
        "fuer dieselbe Etappe verschiedene Temperaturen — es gibt mehr als "
        "eine Gehzeit-Berechnung.\n" + F.describe(channels)
    )
    for name, ex in channels.items():
        assert ex.as_pair() == (c.expected_min_c, c.expected_max_c), (
            f"{F.CHANNEL_LABELS[name]} nennt {ex.as_pair()} statt "
            f"({c.expected_min_c}, {c.expected_max_c}).\n" + F.describe(channels)
        )


# ---------------------------------------------------------------------------
# AC-3 — alle VIER Kanaele nennen denselben gefuehlten Tiefstwert
# ---------------------------------------------------------------------------

def test_mail_sms_compact_telegram_agree_felt_temperature():
    """AC-3: Given eine Etappe mit aktivierter gefuehlter Temperatur, deren
    kaelteste gefuehlte Stunde die Ankunftsstunde ist / When Mail-Kachelzeile,
    SMS, E-Mail-Kurzzusammenfassung und Telegram-Kurzuebersicht gerendert
    werden / Then zeigen alle vier denselben gefuehlten Tiefstwert.

    Konstellation: die gefuehlte Temperatur faellt zur Ankunft auf -4 °C ab —
    kaelter als jede andere Gehzeit-Stunde. ROT vor dem Fix: Mail und Telegram
    nennen -4 °C, SMS und Kurzzusammenfassung 6 °C.
    """
    arrival_felt_min_c = -4.0
    segments = F.build_segments(
        [(8, 10), (10, 12)],
        {9: 6.0, 11: 22.0},
        {9: 6.0, 11: 17.0, 12: arrival_felt_min_c},
    )
    report = F.render_report(segments, report_type="morning", metrics=_FELT)
    channels = F.felt_by_channel(report)

    lows = {n: e.low for n, e in channels.items()}
    assert len(set(lows.values())) == 1, (
        "Die vier Ausgaben desselben Briefings nennen verschiedene gefuehlte "
        "Tiefstwerte — die kaelteste gefuehlte Stunde ist die Ankunftsstunde "
        "(12:00 Ortszeit) und faellt in einigen Kanaelen unter den Tisch.\n"
        + F.describe(channels)
    )
    for name, ex in channels.items():
        assert ex.low == arrival_felt_min_c, (
            f"{F.CHANNEL_LABELS[name]} nennt als gefuehlten Tiefstwert "
            f"{ex.low} statt {arrival_felt_min_c} (Ankunftsstunde).\n"
            + F.describe(channels)
        )


# ---------------------------------------------------------------------------
# AC-4 — Grenzstunde zweier Teile zaehlt genau einmal (#806/#807)
# ---------------------------------------------------------------------------

def test_shared_boundary_hour_counted_once_across_channels():
    """AC-4 (Regressionsschutz #806/#807): Given zwei aufeinanderfolgende
    Teile mit gemeinsamer Grenzstunde (Ende Teil 1 = Start Teil 2, NICHT die
    Ankunft), an der ein Extremwert liegt / When SMS und Mail-Kachelzeile aus
    demselben Report erzeugt werden / Then zaehlt dieser Wert in beiden
    Ausgaben genau einmal.

    Zwei Nachweise, weil Minimum und Maximum gegen Wiederholung UNEMPFINDLICH
    sind (min(x, x) == min(x)) und ein reiner Spannen-Vergleich die
    Doppelzaehlung daher gar nicht sehen koennte:

    1. Paritaet: an der inneren Grenze nennen alle vier Kanaele denselben Wert.
    2. Empfindlichkeitsprobe: die Mittelwert-Kachel („nur Mittelwert",
       Auswertungswahl aus #1357) ueber die Gehzeit-Stunden 08-12 mit 40 °C in
       der Grenzstunde 10:00 und sonst 10 °C ergibt 16 °C, wenn jede Stunde
       genau einmal zaehlt — und 20 °C, wenn die Grenzstunde doppelt zaehlt.

    GRUEN erwartet: dieses Verhalten besteht heute und muss die Umstellung
    ueberleben.
    """
    # 1. Paritaet an der inneren Grenze.
    c = F.CONSTELLATIONS_BY_NAME["extremwert_an_innerer_segmentgrenze"]
    report = _report(c)
    channels = F.measured_by_channel(report)
    pairs = {n: e.as_pair() for n, e in channels.items()}
    assert len(set(pairs.values())) == 1, (
        "Der Extremwert an der Grenzstunde zweier Etappenteile kommt in den "
        "vier Ausgaben verschieden an.\n" + F.describe(channels)
    )
    assert pairs["mail"] == (c.expected_min_c, c.expected_max_c), (
        f"Die Grenzstunde traegt {c.expected_max_c} °C; die Ausgaben nennen "
        f"{pairs['mail']}.\n" + F.describe(channels)
    )

    # 2. Empfindlichkeitsprobe an der GETEILTEN QUELLE.
    #
    # Issue #1728 Scheibe 1: diese Probe lief bis dahin ueber die
    # Mittelwert-Kachel der Mail (Auswertungswahl „nur Mittelwert", #1357).
    # Die Kachel zeigt seit dieser Scheibe unbedingt die Spanne, es gibt
    # keinen gerenderten Mittelwert mehr -- der bisherige Messpunkt ist
    # ersatzlos entfallen. Gemessen wird deshalb direkt
    # ``collect_hiking_window_points()``, die EINE Quelle, um die es diesem
    # Test von Anfang an geht: eine doppelt gezaehlte Grenzstunde ist dort
    # unmittelbar sichtbar, waehrend Minimum und Maximum sie nie verraten
    # haetten. Der gerenderte Wirkort bleibt durch Teil 1 oben abgedeckt.
    from output.renderers.day_window import collect_hiking_window_points

    boundary_hour, spike_c, base_c = 10, 40.0, 10.0
    temps = {h: base_c for h in range(24)}
    temps[boundary_hour] = spike_c
    felt = {h: base_c - 5.0 for h in range(24)}
    punkte = collect_hiking_window_points(
        F.build_segments([(8, boundary_hour), (boundary_hour, 12)], temps, felt)
    )
    werte = [dp.t2m_c for dp in punkte]
    spitzen = [v for v in werte if v == spike_c]

    counted_once = round((base_c * 4 + spike_c) / 5)          # 16 °C
    counted_twice = round((base_c * 4 + spike_c * 2) / 6)     # 20 °C
    assert len(spitzen) == 1, (
        f"Die Grenzstunde {boundary_hour}:00 kommt {len(spitzen)}-mal im "
        f"Gehzeit-Fenster vor — sie wird von beiden Etappenteilen gezaehlt "
        f"(Bug #806/#807).\nWerte: {werte!r}"
    )
    mittel = round(sum(werte) / len(werte))
    assert mittel != counted_twice, (
        f"Der Mittelwert der Gehzeit-Stunden ist {mittel} °C — genau der "
        f"Wert bei doppelt gezaehlter Grenzstunde.\nWerte: {werte!r}"
    )
    assert mittel == counted_once, (
        f"Der Mittelwert der Gehzeit-Stunden ist {mittel} °C statt "
        f"{counted_once} °C (jede Stunde 08-12 genau einmal).\n"
        f"Werte: {werte!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Einzigkeit der Quelle ueber eine Konstellations-Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "constellation", F.CONSTELLATIONS, ids=[c.name for c in F.CONSTELLATIONS],
)
def test_parity_matrix_across_constellations(constellation):
    """AC-5: Given eine Matrix aus Etappen-Konstellationen (Extremwert an der
    Ankunftsstunde, an einer inneren Segmentgrenze, mitten im Segment, bei
    einem einzelnen Teil, bei drei Teilen) / When fuer JEDE Konstellation alle
    vier Ausgaben aus demselben Report gerendert werden / Then nennen alle
    vier in JEDER Konstellation dieselben Tiefst-/Hoechstwerte.

    Ein Test mit nur EINEM Fall waere auch bei zwei zufaellig
    uebereinstimmenden, aber unabhaengigen Berechnungen gruen. Die Matrix
    enthaelt deshalb drei Konstellationen, in denen die beiden heutigen Regeln
    ZWANGSLAEUFIG auseinanderlaufen (Extremwert genau in der Ankunftsstunde),
    und drei, in denen sie es nicht tun — waeren alle sechs rot, waere der
    Vergleich unbrauchbar, waeren alle sechs gruen, waere er blind.
    """
    report = F.render_report(
        constellation.segments(), report_type="morning", metrics=_FELT,
    )
    expected_measured = (constellation.expected_min_c, constellation.expected_max_c)
    expected_felt = (constellation.expected_felt_min_c,
                     constellation.expected_felt_max_c)

    for kind, channels, expected in (
        ("gemessene Temperatur", F.measured_by_channel(report), expected_measured),
        ("gefuehlte Temperatur", F.felt_by_channel(report), expected_felt),
    ):
        pairs = {n: e.as_pair() for n, e in channels.items()}
        assert len(set(pairs.values())) == 1, (
            f"[{constellation.name}] Die vier Ausgaben nennen fuer die "
            f"{kind} verschiedene Werte — es gibt mehr als eine "
            f"Gehzeit-Berechnung.\n{constellation.note}\n"
            + F.describe(channels)
        )
        for name, ex in channels.items():
            assert ex.as_pair() == expected, (
                f"[{constellation.name}] {F.CHANNEL_LABELS[name]} nennt fuer "
                f"die {kind} {ex.as_pair()} statt {expected}.\n"
                f"{constellation.note}\n" + F.describe(channels)
            )


# ---------------------------------------------------------------------------
# AC-6 — Teilausfall verschlechtert sich nicht
# ---------------------------------------------------------------------------

def test_partial_segment_failure_same_shortened_basis_all_channels():
    """AC-6: Given eine Etappe aus mehreren Teilen, von denen einer wegen
    Provider-Ausfall keine verwertbaren Daten hat / When alle vier Ausgaben
    gerendert werden / Then bilden alle vier denselben Tiefst-/Hoechstwert aus
    derselben verkuerzten Grundlage.

    Der ausgefallene Teil (11:00-13:00) haette 30 °C getragen; dieser Wert
    darf in KEINEM Kanal auftauchen — und keiner darf ganz ohne Wert
    dastehen. GRUEN erwartet (Bestandsverhalten, das die Umstellung nicht
    verschlechtern darf).
    """
    unreachable_c = 30.0
    survivor = F.build_segments(
        [(8, 11)],
        {9: 5.0, 10: 22.0, 12: unreachable_c, 13: unreachable_c},
        {9: 0.0, 10: 17.0, 12: 25.0, 13: 25.0},
    )[0]
    report = F.render_report(
        [survivor, F.failed_segment(2, 11, 13)],
        report_type="morning", metrics=_FELT,
    )
    channels = F.measured_by_channel(report)

    for name, ex in channels.items():
        assert ex.low is not None and ex.high is not None, (
            f"{F.CHANNEL_LABELS[name]} zeigt nach dem Teilausfall gar keinen "
            f"Temperaturwert mehr.\n" + F.describe(channels)
        )
        assert ex.high != unreachable_c, (
            f"{F.CHANNEL_LABELS[name]} nennt {unreachable_c} °C aus dem "
            f"AUSGEFALLENEN Etappenteil.\n" + F.describe(channels)
        )
    pairs = {n: e.as_pair() for n, e in channels.items()}
    assert len(set(pairs.values())) == 1, (
        "Nach dem Teilausfall rechnen die vier Ausgaben auf verschiedenen "
        "Grundlagen.\n" + F.describe(channels)
    )
    assert pairs["mail"] == (5.0, 22.0), (
        f"Die verkuerzte Grundlage (nur der erste Teil, 08:00-11:00) muesste "
        f"5-22 °C ergeben, genannt wird {pairs['mail']}.\n"
        + F.describe(channels)
    )


def test_total_failure_yields_null_form_in_all_channels():
    """AC-6 (zweiter Teil): Given eine Etappe, deren SAEMTLICHE Teile
    ausgefallen sind / When alle vier Ausgaben gerendert werden / Then zeigen
    alle uebereinstimmend die Null-Form und keiner erfindet einen Wert.

    GRUEN erwartet: die SMS zeigt `L-`/`D-` (Fix #1926: vormals `K-`),
    Kachelzeile, Kurzzusammenfassungssatz und Telegram-Zeile nennen keine
    Zahl.
    """
    report = F.render_report(
        [F.failed_segment(1, 8, 10), F.failed_segment(2, 10, 12)],
        report_type="morning", metrics=_FELT,
    )
    channels = F.measured_by_channel(report)

    for name, ex in channels.items():
        assert ex.as_pair() == (None, None), (
            f"{F.CHANNEL_LABELS[name]} nennt einen Temperaturwert, obwohl die "
            f"ganze Etappe ohne Daten ist.\n" + F.describe(channels)
        )
    sms = report.sms_text or ""
    for symbol in ("L", "D"):
        assert F.sms_token_value(sms, symbol) == "-", (
            f"Die Kurznachricht zeigt fuer `{symbol}` nicht die Null-Form "
            f"`{symbol}-`.\nSMS: {sms!r}"
        )
    assert not _NUMBER.search(F.overview_line(report, "T")), (
        "Die Telegram-Kurzuebersicht nennt eine Temperatur, obwohl keine "
        f"Daten vorliegen.\nZeile: {F.overview_line(report, 'T')!r}"
    )


def test_failed_last_part_keeps_survivor_arrival_hour_in_all_channels():
    """AC-6 (Ausfall des LETZTEN Etappenteils): Given eine Etappe, deren
    letzter Teil ausgefallen ist und deren ueberlebender Teil seinen
    Extremwert in der eigenen Endstunde traegt / When alle vier Ausgaben
    gerendert werden / Then nennen alle vier denselben Hoechstwert.

    ROT vor dem Fix. ``_collect_hiking_window_dps`` bestimmt
    ``last_idx = len(segments) - 1`` ueber die ROHLISTE, also einschliesslich
    ausgefallener Teile. Faellt der letzte Teil aus, gilt der ueberlebende
    nicht mehr als „letzter": seine Endstunde (11:00) wird als innere
    Segmentgrenze behandelt und abgeschnitten. ``_extract_hourly_rows``
    (Telegram) nimmt sie dagegen weiter mit — Mail/SMS/Kurzzusammenfassung
    sagen 15 °C, Telegram 22 °C.

    Die verkuerzte Grundlage muss die ANKUNFT des letzten VERWERTBAREN Teils
    einschliessen; sonst bleibt nach der Umstellung eine Divergenz uebrig.
    """
    survivor_arrival_h, extreme_c, felt_extreme_c = 11, 22.0, 17.0
    survivor = F.build_segments(
        [(8, survivor_arrival_h)],
        {9: 5.0, survivor_arrival_h: extreme_c},
        {9: 0.0, survivor_arrival_h: felt_extreme_c},
    )[0]
    report = F.render_report(
        [survivor, F.failed_segment(2, survivor_arrival_h, 13)],
        report_type="morning", metrics=_FELT,
    )

    for kind, channels, expected_high in (
        ("gemessene Temperatur", F.measured_by_channel(report), extreme_c),
        ("gefuehlte Temperatur", F.felt_by_channel(report), felt_extreme_c),
    ):
        highs = {n: e.high for n, e in channels.items()}
        assert len(set(highs.values())) == 1, (
            f"Nach dem Ausfall des letzten Etappenteils nennen die vier "
            f"Ausgaben verschiedene Hoechstwerte fuer die {kind} — die "
            f"Endstunde des ueberlebenden Teils ({survivor_arrival_h}:00, "
            f"jetzt die tatsaechliche Ankunft) faellt in einigen Kanaelen "
            f"unter den Tisch.\n" + F.describe(channels)
        )
        for name, ex in channels.items():
            assert ex.high == expected_high, (
                f"{F.CHANNEL_LABELS[name]} nennt als Hoechstwert der {kind} "
                f"{ex.high} statt {expected_high} (Wert der Ankunftsstunde "
                f"{survivor_arrival_h}:00).\n" + F.describe(channels)
            )


def test_compact_summary_names_temperature_whenever_hiking_points_exist():
    """AC-2/AC-5 (PO-Entscheidung 2026-07-29): Given eine Etappe mit
    verwertbaren Gehzeit-Stunden, deren Etappen-Aggregat aber keine
    Temperatur traegt / When die Mail gerendert wird / Then nennt der
    Kurzzusammenfassungssatz dieselbe Temperatur wie die Kachelzeile
    derselben Mail.

    ROT vor dem Fix: die Mail widerspricht sich selbst — die Kachelzeile sagt
    `5–22°C`, der Satz zwei Zeilen darueber nennt gar keine Temperatur. Der
    Satz haengt heute allein am Etappen-Aggregat und steigt aus, sobald das
    leer ist; die Gehzeit-Punkte, aus denen die Kachel schoepft, liegen
    unveraendert vor.

    Diese Konstellation ist keine Erfindung des Tests: sie ist die Form der
    eingefrorenen Referenz-Fixture ``gr20-summer-evening``
    (``tests/golden/email/regenerate.py``), deren Satz bis heute ohne
    Temperaturteil eingefroren ist, waehrend die Kachel `18–20°C` zeigt.
    """
    segments = F.segments_without_aggregation_config(
        [(8, 10), (10, 12)], {9: 5.0, 11: 22.0}, {9: 0.0, 11: 17.0},
    )
    report = F.render_report(segments, report_type="morning", metrics=_FELT)
    mail, compact = F.mail_temp(report), F.compact_temp(report)

    assert mail.as_pair() != (None, None), (
        "Die Mail-Kachelzeile nennt selbst keine Temperatur — die Fixture "
        f"traegt keine verwertbaren Gehzeit-Punkte.\n"
        f"Kachelzeilen: {F.pill_lines(report)}"
    )
    assert compact.as_pair() != (None, None), (
        "Der Kurzzusammenfassungssatz derselben Mail nennt gar keine "
        f"Temperatur, obwohl die Kachelzeile {mail.raw!r} zeigt — das "
        "Etappen-Aggregat ist leer, die Gehzeit-Stunden liegen aber vor.\n"
        f"  Kachelzeilen:  {F.pill_lines(report)}\n"
        f"  Satzteile:     {F.compact_parts(report)}"
    )
    assert compact.as_pair() == mail.as_pair(), (
        f"Kachelzeile und Kurzzusammenfassung derselben Mail nennen "
        f"verschiedene Temperaturen: {mail.as_pair()} vs. "
        f"{compact.as_pair()}.\n  Kachelzeile: {mail.raw!r}\n"
        f"  Satz:        {compact.raw!r}"
    )


def test_sms_falls_back_to_segment_aggregate_without_timeseries():
    """AC-6 (Fail-soft, Test-Plan-Zeile der Spec): Given ein Etappenteil OHNE
    Stunden-Zeitreihe, aber mit brauchbarem Aggregat (Bug-#398-Rueckfall) /
    When die Kurznachricht und die Kurzzusammenfassung gerendert werden /
    Then zeigen beide weiterhin die Werte aus dem Aggregat.

    GRUEN erwartet — und genau diese Eigenschaft darf die Umstellung auf die
    Rohpunkt-Quelle nicht verlieren: ohne Rohpunkte muss der bisherige Weg
    greifen, statt `K-`/`D-` zu zeigen.
    """
    report = F.render_report(
        [F.aggregate_only_segment(
            1, 8, 12, temp_min=4.0, temp_max=19.0, felt_min=1.0, felt_max=14.0,
        )],
        report_type="morning", metrics=_FELT,
    )
    sms, compact = F.sms_temp(report), F.compact_temp(report)

    assert sms.as_pair() == (4.0, 19.0), (
        "Ohne Stunden-Zeitreihe faellt die Kurznachricht nicht mehr auf das "
        f"Etappen-Aggregat zurueck: {sms.as_pair()} statt (4.0, 19.0).\n"
        f"SMS: {sms.raw!r}"
    )
    assert compact.as_pair() == (4.0, 19.0), (
        "Ohne Stunden-Zeitreihe faellt die Kurzzusammenfassung nicht mehr auf "
        f"das Etappen-Aggregat zurueck: {compact.as_pair()} statt (4.0, 19.0).\n"
        f"Satz: {compact.raw!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Nachtwert bleibt unberuehrt
# ---------------------------------------------------------------------------

def test_night_temperature_unaffected_by_hiking_window_change():
    """AC-7: Given ein Abendbriefing mit Ankunft am Etappenziel und
    vorhandenem Nachtwetter / When SMS, E-Mail-Kurzzusammenfassung und
    Telegram gerendert werden / Then bleibt die Nacht-Tiefsttemperatur exakt
    die echte Nachttemperatur am Ziel.

    Die Nachtwerte (9 °C gemessen, 6 °C gefuehlt) liegen bewusst ZWISCHEN dem
    Gehzeit-Tiefstwert (5 °C) und dem Gehzeit-Hoechstwert (22 °C) — eine
    Verwechslung mit einem der beiden waere sofort sichtbar. GRUEN erwartet.
    """
    night_min_c, night_felt_min_c = 9.0, 6.0
    c = F.CONSTELLATIONS_BY_NAME["extremwert_an_der_ankunftsstunde"]
    report = _report(
        c, "evening",
        night=F.night_weather(c.arrival_hour, temp_min=night_min_c,
                              felt_min=night_felt_min_c),
    )

    night = F.sms_night(report)
    assert night.low == night_min_c, (
        f"Die Kurznachricht nennt als Nacht-Tiefsttemperatur {night.low} "
        f"statt {night_min_c} (echte Nachttemperatur am Ziel).\n"
        f"SMS: {night.raw!r}"
    )
    assert night.high == night_felt_min_c, (
        f"Die Kurznachricht nennt als gefuehlte Nacht-Tiefsttemperatur "
        f"{night.high} statt {night_felt_min_c}.\nSMS: {night.raw!r}"
    )
    assert F.sms_temp(report).low == c.expected_min_c, (
        "Der Gehzeit-Tiefstwert der Kurznachricht wurde vom Nachtwert "
        f"ueberschrieben: {F.sms_temp(report).low} statt {c.expected_min_c}.\n"
        f"SMS: {night.raw!r}"
    )
    assert F.compact_temp(report).low == night_min_c, (
        "Die abendliche Kurzzusammenfassung nennt als Untergrenze "
        f"{F.compact_temp(report).low} statt der echten Nachttemperatur am "
        f"Ziel ({night_min_c}).\nSatz: {F.compact_sentence(report)!r}"
    )
    assert F.telegram_temp(report).low == night_min_c, (
        "Die abendliche Telegram-Kurzuebersicht nennt als Untergrenze "
        f"{F.telegram_temp(report).low} statt der echten Nachttemperatur am "
        f"Ziel ({night_min_c}).\nZeile: {F.overview_line(report, 'T')!r}"
    )
    assert F.telegram_felt(report).low == night_felt_min_c, (
        "Die abendliche Telegram-Kurzuebersicht nennt als gefuehlte "
        f"Untergrenze {F.telegram_felt(report).low} statt "
        f"{night_felt_min_c}.\nZeile: {F.overview_line(report, 'TF')!r}"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
