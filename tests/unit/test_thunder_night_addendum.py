"""#1651: Gewitter AUSSERHALB des Tagesfensters wird in der Mail genannt.

Spec: docs/specs/modules/fix_1651_vorschau_zeitfenster.md (Version 2.0)
Kontext: docs/context/fix-1651-vorschau-tagesentwarnung.md

Ausgangslage (echt zugestellte Staging-Mail): die "⚡ Gewitter-Vorschau"
sagte fuer den 10.08.2026 "Kein Gewitter erwartet", waehrend die
"Nacht am Ziel"-Tabelle DERSELBEN Mail fuer 00:00 "hoch" zeigte -- das
Gewitter lag ausserhalb des Tagesfensters 04-19 (Klemmung aus
#1498/#1530) und wurde dadurch verschwiegen.

Diese Datei prueft die Fliesstext-Seite: der Satz nennt das Nachtgewitter
angehaengt, mit exakter Uhrzeit UND Stufe; die Tages-Aussage bleibt
unveraendert (rein additiv). Geprueft werden BEIDE Bauwege -- Trend-Weg
(trip_report_scheduler.py:1838-1848) und Fetch-Weg (:2034-2041); sie sind
wortgleich, aber unabhaengiger Code.

KEINE Mocks: reale Model-Objekte, echte Scheduler-Methoden. Die Fixtures
``_dp``/``_segment`` kommen aus tests/unit/test_thunder_forecast_day_window.py
-- derselbe Pruefling, dieselben Daten, EINE Quelle statt einer Kopie.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import ThunderLevel
from tests.unit.test_thunder_forecast_day_window import _dp, _segment

_UTC = ZoneInfo("UTC")
_TODAY = date(2026, 7, 3)
_TOMORROW = date(2026, 7, 4)
_DAY_AFTER = date(2026, 7, 5)

# Wortschatz des Nacht-Zusatzes (Spec, Implementation Details 3). Bewusste
# Abweichung vom Tagestext: MED traegt hier ein Adjektiv, weil der Halbsatz
# fuer sich lesbar sein muss.
_ADD_LOW = ", nachts leichtes Gewitter ab "
_ADD_MED = ", nachts mittleres Gewitter ab "
_ADD_HIGH = ", nachts starkes Gewitter ab "


def _day_points(day: date, thunder_by_hour):
    """Voller Kalendertag, Gewitter nur in den genannten Stunden."""
    return [
        _dp(day, h, thunder_by_hour.get(h, ThunderLevel.NONE))
        for h in range(0, 24)
    ]


def _trend_row(thunder_by_hour, level_max, fc_date: date = _TOMORROW):
    """Eine echte ``multi_day_trend``-Zeile ueber den geteilten Baustein
    ``build_outlook_row`` -- kein handgeschriebenes Dict."""
    from output.renderers.email.outlook import build_outlook_row

    points = _day_points(fc_date, thunder_by_hour)
    seg = _segment(points, thunder_level_max=level_max)
    row = build_outlook_row(seg.aggregated, points, "Sa", _UTC)
    row["date"] = fc_date
    return row


def _night_series(thunder_by_hour, night_of: date = _TOMORROW, evening_by_hour=None):
    """``night_weather`` wie ``segment_weather.fetch_night_weather()`` es
    liefert: Ankunft am Vortag 15:00 bis 06:00 des ``night_of``-Tages.

    ``thunder_by_hour`` bezieht sich auf die Stunden NACH Mitternacht, also
    auf ``night_of`` selbst -- genau die Stunden, fuer die auch die
    "Nacht am Ziel"-Tabelle derselben Mail zustaendig ist.

    ``evening_by_hour`` (optional) belegt dagegen die Abendstunden des
    ANKUNFTSTAGS (15:00-23:00, also den Tag VOR ``night_of``). Die Reihe
    deckt beide Kalendertage ab -- wer sie ohne Datumsbezug auswertet,
    verwechselt sie (siehe ``test_nachtquelle_vom_ankunftstag_...``).
    """
    from app.models import ForecastMeta, NormalizedTimeseries, Provider

    evening_by_hour = evening_by_hour or {}
    arrival_day = night_of - timedelta(days=1)
    data = [
        _dp(arrival_day, h, evening_by_hour.get(h, ThunderLevel.NONE))
        for h in range(15, 24)
    ]
    data += [
        _dp(night_of, h, thunder_by_hour.get(h, ThunderLevel.NONE))
        for h in range(0, 7)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(_TODAY.year, _TODAY.month, _TODAY.day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0,
    )
    return NormalizedTimeseries(meta=meta, data=data)


def _entry_from_trend(row, *, night_weather=None, key="+1"):
    """Vorschau-Eintrag ueber den PRIMAEREN Bauweg (Trend-Zeile)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    kwargs = {}
    if night_weather is not None:
        kwargs["night_weather"] = night_weather
    fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        None, _TODAY, _UTC, multi_day_trend=[row], **kwargs,
    )
    return (fc or {}).get(key)


# ===========================================================================
# AC-1 — Kernszenario Morgen: das gemessene #1651-Szenario
# ===========================================================================


def test_ac1_trend_nachtgewitter_wird_mit_uhrzeit_genannt():
    """AC-1 (Trend-Weg): Given Default-Fenster 04-19, morgen KEIN Gewitter im
    Fenster, aber HIGH um 00:00 in derselben Nacht-Zeitreihe, die auch die
    "Nacht am Ziel"-Tabelle speist / When der Vorschau-Eintrag gebaut wird /
    Then lautet der Satz "Kein Gewitter erwartet, nachts starkes Gewitter ab
    00:00" statt der bisherigen reinen Entwarnung.
    """
    row = _trend_row({}, ThunderLevel.NONE)
    entry = _entry_from_trend(
        row, night_weather=_night_series({0: ThunderLevel.HIGH}),
    )
    assert entry is not None, "Vorschau-Eintrag fuer morgen fehlt ganz"
    assert entry["text"] == "Kein Gewitter erwartet, nachts starkes Gewitter ab 00:00", (
        f"Der Vorschau-Satz verschweigt das Nachtgewitter um 00:00: {entry['text']!r}"
    )


def test_ac1_fetch_nachtgewitter_wird_mit_uhrzeit_genannt():
    """AC-1 (Fetch-Weg, Morgen-Default ohne Trend): derselbe Satz entsteht am
    zweiten, unabhaengigen Bauweg -- er ist wortgleich, aber eigener Code
    (trip_report_scheduler.py:2034-2041)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    seg = _segment(_day_points(_TOMORROW, {}), thunder_level_max=ThunderLevel.NONE)
    fc = TripReportSchedulerService()._build_thunder_forecast(
        seg, _TODAY, tz=_UTC,
        night_weather=_night_series({0: ThunderLevel.HIGH}),
    )
    entry = (fc or {}).get("+1")
    assert entry is not None, "Vorschau-Eintrag fuer morgen fehlt ganz"
    assert entry["text"] == "Kein Gewitter erwartet, nachts starkes Gewitter ab 00:00", (
        f"Fetch-Weg verschweigt das Nachtgewitter um 00:00: {entry['text']!r}"
    )


def test_ac1_die_tagesklemmung_aus_1498_bleibt_bestehen():
    """AC-1 Gegenprobe: der Zusatz ist ADDITIV. `level`/`hour` -- die Felder,
    aus denen SMS und Ampel die TAGES-Aussage ableiten -- bleiben auf der
    Entwarnung stehen; nur der Fliesstext waechst.

    Ohne diese Pruefung koennte der Fix das Nachtgewitter in die Tages-Aussage
    hochziehen und damit #1498 in der urspruenglichen Richtung wieder
    aufreissen.
    """
    row = _trend_row({}, ThunderLevel.NONE)
    entry = _entry_from_trend(
        row, night_weather=_night_series({0: ThunderLevel.HIGH}),
    )
    assert entry["level"] == ThunderLevel.NONE, (
        f"Nachtgewitter hebt das TAGES-Level an -- #1498 waere zurueck: {entry!r}"
    )
    assert entry["hour"] is None, (
        f"Nachtgewitter setzt die TAGES-Stunde -- #1498 waere zurueck: {entry!r}"
    )


# ===========================================================================
# AC-4 — Tages- und Nachtgewitter gemeinsam
# ===========================================================================


def test_ac4_tag_und_nacht_werden_beide_genannt():
    """AC-4: Given HIGH ab 14:00 INNERHALB und MED um 22:00 AUSSERHALB des
    Fensters am selben Tag / When der Eintrag gebaut wird / Then nennt der
    Satz beide Ereignisse -- die Tages-Aussage unveraendert, die Nacht-Angabe
    angehaengt mit eigener Stufe.

    Quelle der 22:00-Stunde ist die eigene Zeitreihe der Etappe (die
    Nacht-Tabelle reicht nur bis 06:00 und deckt 22:00 des Folgetags nicht ab).
    """
    row = _trend_row(
        {14: ThunderLevel.HIGH, 22: ThunderLevel.MED}, ThunderLevel.HIGH,
    )
    entry = _entry_from_trend(row)
    assert entry is not None
    assert entry["text"] == (
        "Starkes Gewitter erwartet ab 14:00, nachts mittleres Gewitter ab 22:00"
    ), f"Tages- und Nachtgewitter werden nicht beide genannt: {entry['text']!r}"
    assert entry["level"] == ThunderLevel.HIGH, entry
    assert entry["hour"] == 14, entry


# ===========================================================================
# AC-5 — Keine Aenderung ohne Nachtgewitter (Regressionsschutz)
# ===========================================================================


def test_ac5_ohne_nachtgewitter_bleibt_der_satz_unveraendert():
    """AC-5 (Regressionsschutz -- VOR und NACH dem Fix gruen): Given weder im
    Fenster noch ausserhalb ein Gewitter / When der Eintrag gebaut wird /
    Then bleibt "Kein Gewitter erwartet" ohne jeden Zusatz."""
    row = _trend_row({}, ThunderLevel.NONE)
    entry = _entry_from_trend(row)
    assert entry["text"] == "Kein Gewitter erwartet", (
        f"Ohne jedes Gewitter darf kein Nacht-Zusatz entstehen: {entry['text']!r}"
    )


def test_ac5_tagesgewitter_ohne_nachtgewitter_bleibt_unveraendert():
    """AC-5 (Regressionsschutz -- VOR und NACH dem Fix gruen): auch ein reines
    TAGES-Gewitter bekommt keinen Zusatz, sonst haette der Fix jede bestehende
    Vorschau-Zeile veraendert."""
    row = _trend_row({14: ThunderLevel.HIGH}, ThunderLevel.HIGH)
    entry = _entry_from_trend(row)
    assert entry["text"] == "Starkes Gewitter erwartet ab 14:00", (
        f"Reines Tagesgewitter bekam einen Nacht-Zusatz: {entry['text']!r}"
    )


def test_ac5_ruhige_nachtquelle_fuegt_nichts_hinzu():
    """AC-5 an der Merge-Naht: liegt eine Nacht-Zeitreihe vor, die KEIN
    Gewitter meldet, darf sie den Satz nicht veraendern -- der Zusatz haengt
    an gemessenem Gewitter, nicht am blossen Vorhandensein der Quelle."""
    row = _trend_row({}, ThunderLevel.NONE)
    entry = _entry_from_trend(row, night_weather=_night_series({}))
    assert entry["text"] == "Kein Gewitter erwartet", (
        f"Eine ruhige Nacht-Quelle erzeugte einen Zusatz: {entry['text']!r}"
    )


# ===========================================================================
# AC-6 — Uebernaechster Tag ("+2") ohne Nacht-Tabellen-Gegenquelle
# ===========================================================================


def test_ac6_plus2_nennt_nachtgewitter_aus_der_eigenen_zeitreihe():
    """AC-6: Given Gewitter ausserhalb des Fensters am UEBERNAECHSTEN Tag --
    fuer den es in derselben Mail keine "Nacht am Ziel"-Tabelle gibt / When
    der "+2"-Eintrag gebaut wird / Then erscheint die Nacht-Angabe trotzdem,
    aus der fuer diesen Tag ohnehin schon beschafften Zeitreihe.

    Kein `night_weather` im Spiel: die Zeile traegt ihre eigenen, bereits
    ungefilterten Stundenproben -- kein zusaetzlicher Abruf noetig.
    """
    row = _trend_row({23: ThunderLevel.LOW}, ThunderLevel.LOW, fc_date=_DAY_AFTER)
    entry = _entry_from_trend(row, key="+2")
    assert entry is not None, "Vorschau-Eintrag fuer uebermorgen fehlt ganz"
    assert entry["text"] == "Kein Gewitter erwartet, nachts leichtes Gewitter ab 23:00", (
        f'"+2" verschweigt das Gewitter ausserhalb des Fensters: {entry["text"]!r}'
    )


# ===========================================================================
# AC-7 — Mehrere Nachtstunden: frueheste Stunde des HOECHST-Levels
# ===========================================================================


def test_ac7_hoechstes_level_gewinnt_nicht_das_fruehere_ereignis():
    """AC-7: Given MED um 02:00 UND HIGH um 22:00, beide ausserhalb des
    Fensters am selben Tag / When der Satz gebaut wird / Then wird
    ausschliesslich "nachts starkes Gewitter ab 22:00" genannt -- nicht
    02:00, und die Stufe ist die hoehere, nicht die des fruehereren
    Ereignisses.

    Beide Stunden bilden EINEN Pool (00:00-03:59 und 20:00-23:59 zusammen),
    spiegelbildlich zur bestehenden Innerhalb-Fenster-Regel.
    """
    row = _trend_row(
        {2: ThunderLevel.MED, 22: ThunderLevel.HIGH}, ThunderLevel.HIGH,
    )
    entry = _entry_from_trend(row)
    assert entry is not None
    assert entry["text"] == "Kein Gewitter erwartet, nachts starkes Gewitter ab 22:00", (
        f"Nicht das hoechste Level mit seiner fruehesten Stunde: {entry['text']!r}"
    )
    assert "02:00" not in entry["text"], (
        f"Die fruehere, aber schwaechere Stunde wird genannt: {entry['text']!r}"
    )


def test_ac7_nachtquelle_hat_vorrang_vor_der_eigenen_reihe():
    """AC-7 / zentrale #1498-Zusicherung an der Merge-Naht: fuer eine Stunde,
    die BEIDE Quellen abdecken (00:00-06:00 des Folgetags), gewinnt die
    Nacht-Zeitreihe -- sie ist dieselbe Quelle, welche die Nacht-Tabelle
    direkt neben der Vorschau zeigt.

    Hier behauptet die eigene Etappen-Reihe LOW um 02:00, die Nacht-Reihe
    HIGH um 02:00. Genannt werden muss "starkes", sonst widerspraeche der
    Satz der Tabelle in derselben Mail.
    """
    row = _trend_row({2: ThunderLevel.LOW}, ThunderLevel.LOW)
    entry = _entry_from_trend(
        row, night_weather=_night_series({2: ThunderLevel.HIGH}),
    )
    assert entry is not None
    assert entry["text"] == "Kein Gewitter erwartet, nachts starkes Gewitter ab 02:00", (
        "Die Vorschau folgt der eigenen Etappen-Reihe statt der Nacht-Quelle -- "
        f"sie widerspricht damit der Nacht-Tabelle derselben Mail: {entry['text']!r}"
    )


def test_ac7_nachtquelle_hat_vorrang_auch_wenn_sie_ENTWARNT():
    """AC-7/AC-3, Gegenrichtung zum Test darueber (Adversary F001): die
    Nacht-Quelle gewinnt BEDINGUNGSLOS, nicht nur wenn sie das hoehere Level
    meldet.

    Hier behauptet die eigene Etappen-Reihe HIGH um 02:00 (z. B. aus einem
    aelteren Modelllauf), die maessgebliche Nacht-Reihe dagegen LOW. Genannt
    werden muss "leichtes" -- denn genau diese Nacht-Reihe steht als
    "Nacht am Ziel"-Tabelle daneben in derselben Mail und zeigt dort LOW.

    Ohne diesen Test bliebe die Autoritaetsregel halb bewacht: ein
    Maximum-Merge (Nacht gewinnt nur bei >=) liesse alle uebrigen Tests
    gruen und wuerde die Vorschau der Tabelle widersprechen lassen -- der
    #1498-Fehler, in der Richtung, die diese Scheibe verhindern soll.
    """
    row = _trend_row({2: ThunderLevel.HIGH}, ThunderLevel.HIGH)
    entry = _entry_from_trend(
        row, night_weather=_night_series({2: ThunderLevel.LOW}),
    )
    assert entry is not None
    assert entry["text"] == "Kein Gewitter erwartet, nachts leichtes Gewitter ab 02:00", (
        "Die eigene Etappen-Reihe ueberstimmt die Nacht-Quelle nach OBEN -- "
        "die Vorschau behauptet ein staerkeres Gewitter, als die "
        f"Nacht-Tabelle derselben Mail zeigt: {entry['text']!r}"
    )
    assert "starkes" not in entry["text"], entry["text"]


# ===========================================================================
# Datums-Zuordnung der Nacht-Quelle (Adversary F002/F003)
# ===========================================================================


def test_nachtquelle_vom_ankunftstag_gilt_nicht_fuer_morgen():
    """Adversary F002: die Nacht-Reihe deckt ZWEI Kalendertage ab (Ankunft
    heute 15:00 bis 06:00 morgen). Ein Gewitter am ANKUNFTSABEND (heute
    20:00) gehoert zu HEUTE und darf im Vorschau-Satz fuer MORGEN nicht
    auftauchen.

    Wird die Reihe nur nach Stunde-des-Tages statt nach Datum ausgewertet,
    wandert das heutige Abendgewitter in die morgige Vorschau -- eine
    Aussage ueber einen Tag aus den Daten eines anderen. Das ist exakt die
    Fehlerklasse aus #1498, in genau der Funktion, die sie verhindern soll.

    Alles andere ist hier bewusst ruhig: morgen weder im noch ausserhalb des
    Fensters ein Gewitter, die Nachtstunden 00-06 ebenfalls nicht. Ein
    Zusatz KANN damit nur aus der falsch zugeordneten Stunde stammen.
    """
    row = _trend_row({}, ThunderLevel.NONE)
    entry = _entry_from_trend(
        row,
        night_weather=_night_series({}, evening_by_hour={20: ThunderLevel.HIGH}),
    )
    assert entry is not None
    assert entry["text"] == "Kein Gewitter erwartet", (
        "Das Gewitter vom HEUTIGEN Abend (20:00) erscheint im Vorschau-Satz "
        f"fuer MORGEN: {entry['text']!r}"
    )


def test_trend_plus2_ignoriert_die_nachtquelle():
    """Adversary F003 (Trend-Weg): fuer "+2" ist die eigene Zeitreihe die
    ALLEINIGE Quelle -- die Nacht-Reihe gilt dort nicht.

    Begruendung aus der Spec (Punkt 4): zu "+2" gibt es in derselben Mail
    keine "Nacht am Ziel"-Tabelle, also auch keine Gegenquelle, der zu
    folgen waere. Hier traegt die Nacht-Reihe (hypothetisch bis in den
    uebernaechsten Tag reichend) HIGH um 00:00, die eigene "+2"-Reihe LOW um
    23:00. Genannt werden muss die eigene Angabe.

    Ohne diesen Test ist der ``offset == 1``-Waechter unbewacht: in allen
    uebrigen Fixtures endet die Nacht-Reihe vor "+2", der Datumsfilter
    maskiert ihn also.
    """
    row = _trend_row({23: ThunderLevel.LOW}, ThunderLevel.LOW, fc_date=_DAY_AFTER)
    entry = _entry_from_trend(
        row,
        night_weather=_night_series({0: ThunderLevel.HIGH}, night_of=_DAY_AFTER),
        key="+2",
    )
    assert entry is not None, "Vorschau-Eintrag fuer uebermorgen fehlt ganz"
    assert entry["text"] == "Kein Gewitter erwartet, nachts leichtes Gewitter ab 23:00", (
        'Die Nacht-Reihe wurde auch fuer "+2" herangezogen, obwohl es dort '
        f"keine Nacht-Tabelle als Gegenquelle gibt: {entry['text']!r}"
    )


def test_fetch_plus2_ignoriert_die_nachtquelle():
    """Adversary F003 (Fetch-Weg): derselbe Waechter am zweiten Bauweg.

    Der ``offset == 1``-Vorbehalt steht in BEIDEN Bauwegen als eigene Zeile
    (trip_report_scheduler.py) -- eine Kopie, die getrennt brechen kann. Ein
    Test auf nur einem der beiden Wege liesse die andere Zeile unbewacht.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    seg = _segment(
        _day_points(_DAY_AFTER, {23: ThunderLevel.LOW}),
        thunder_level_max=ThunderLevel.LOW,
    )
    fc = TripReportSchedulerService()._build_thunder_forecast(
        seg, _TODAY, tz=_UTC,
        night_weather=_night_series({0: ThunderLevel.HIGH}, night_of=_DAY_AFTER),
    )
    entry = (fc or {}).get("+2")
    assert entry is not None, "Vorschau-Eintrag fuer uebermorgen fehlt ganz"
    assert entry["text"] == "Kein Gewitter erwartet, nachts leichtes Gewitter ab 23:00", (
        'Fetch-Weg: die Nacht-Reihe wurde auch fuer "+2" herangezogen: '
        f"{entry['text']!r}"
    )


# ===========================================================================
# AC-8 — SMS-Token bleibt unberuehrt
# ===========================================================================


def test_ac8_sms_token_ignoriert_die_nacht_angabe():
    """AC-8: Given ein Vorschau-Eintrag, dessen `text` die neue Nacht-Angabe
    traegt / When der SMS-Renderer das TH+-Token baut / Then bleibt das Token
    die Entwarnung "TH+:-" -- der SMS-Pfad liest ausschliesslich
    `level`/`hour`, nie den Fliesstext (Platzgrund, PO-Vorgabe: SMS zeigt die
    Angabe nicht).

    RED-Mechanik: die Vorbedingung (Nacht-Angabe steht im `text`) ist heute
    nicht erfuellt -- ohne sie prueft die eigentliche Zusicherung nichts.
    """
    from output.renderers.sms_trip import SMSTripFormatter

    row = _trend_row({22: ThunderLevel.HIGH}, ThunderLevel.HIGH)
    entry = _entry_from_trend(row)
    assert _ADD_HIGH in entry["text"], (
        "Vorbedingung: der Eintrag muss die Nacht-Angabe tragen, sonst prueft "
        f"dieser Test nichts: {entry['text']!r}"
    )

    sms = SMSTripFormatter().format_sms(
        [_segment(_day_points(_TODAY, {}))],
        report_type="morning",
        thunder_forecast={"+1": entry},
    )
    assert "TH+:-" in sms, (
        "Die Nacht-Angabe ist in die Kurznachricht durchgeschlagen -- die SMS "
        f"soll sie nicht zeigen: {sms!r}"
    )
    assert "nachts" not in sms, (
        f"Der Fliesstext der Vorschau steht in der Kurznachricht: {sms!r}"
    )
