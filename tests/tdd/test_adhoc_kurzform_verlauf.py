"""TDD RED — Issue #2207 (Epic #2133, Scheibe S5): Ad-hoc-Verlauf einer
Einzelgroesse erreicht Premium-SMS/sms in KURZFORM statt der Langform.

SPEC: docs/specs/modules/feat_2207_kurzform_verlauf.md (AC-1..AC-14)

Warum diese Datei existiert: ``_format_drilldown`` liefert heute fuer ALLE
Kanaele denselben ausgeschriebenen Text (Wortlabel, ``HH:MM``-Uhrzeiten, kein
Laengenbudget). Auf dem Satellitengeraet (Premium-SMS) ist das teuer und
teils gar nicht darstellbar. Diese Scheibe gibt Premium-SMS/``sms`` eine
eigene, kurzformtaugliche Fassung derselben Aussage: Katalog-Kuerzel statt
Woertern, dieselben Wechselpunkte (geteilter Gruppierungs-Helfer, AC-14),
eine 160-Zeichen-Grenze und eine Kuerzungsregel, die eine Luecke NENNT statt
sie zu verschweigen.

Erwarteter, noch NICHT existierender Produktiv-Baustein (Source-Sektion der
Spec): ``TripCommandProcessor._format_drilldown_kurzform(res, metric, tz, *,
folgetag=False) -> str`` neben ``_format_drilldown``. Ruft ihn heute jemand,
gibt es ``AttributeError`` — das IST der RED-Zustand dieser Datei.

Mock-frei: echte ``DrilldownPoint``/``DrilldownResult``-Dataclasses (Vorbild
``tests/tdd/test_adhoc_verlauf_wechselpunkte.py``, S2/#2185), echte
``TripCommandProcessor``, echter Katalog. Der Draht-Messpunkt fuer AC-1/AC-10
ist das echte ``PremiumSmsOutput.send`` (Klassen-Ersetzung, Vorbild
``tests/tdd/test_premium_sms_kommandopfad.py``, S4/#2184) — kein
``Mock()``/``patch()``.

Warum feste lokale Uhrzeiten statt ``datetime.now()``: mehrere Tests pruefen
EXAKTE Stunden-Tokens (``@14``, ``@8`` ...) und muessen deshalb
tageszeitunabhaengig sein (Lehre aus #2186: ein Test, der je nach Tageszeit
gruen/rot wird, ist eine Zeitbombe). Punkte werden direkt mit
``tzinfo=Europe/Paris`` konstruiert (``_pt``), nicht ueber einen
UTC-Offset — so ist die angezeigte Ortsstunde unabhaengig von Sommer-/
Winterzeit exakt die, die im Test steht.

AC-8/AC-9 brauchen eine praezise 160-Zeichen-Bytebudget-Grenze bei GENAU
sieben Wechselpunkt-Gruppen (Spec-Testvorgabe). Weil ein Kurzform-Token
(``{wert}@{h}``) strukturell nur wenige Zeichen breit ist, braucht es dafuer
befristet aufgeblaehte Nachkommastellen (``katalog_eintrag_ersetzt(...,
decimals=22)`` aus ``tests/helpers/adhoc_metrik_fixtures.py``) — die
Basiswerte (0.3..15.5 km) bleiben physikalisch plausibel, nur die
Nachkommastellen sind ein reines Testwerkzeug, um den Grenzfall
deterministisch zu treffen, ohne von der realen Tageszeit abzuhaengen.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.metric_catalog import get_metric
from app.models import PrecipType, ThunderLevel
from output.channels.premium_sms import PremiumSmsOutput
from output.metric_format import format_value
from services.notification_service import NotificationService
from services.trip_command_processor import TripCommandProcessor, _metric_formatter
from services.weather_extractor import DrilldownPoint, DrilldownResult
from services.weather_snapshot import WeatherSnapshotService
from tests.helpers.adhoc_metrik_fixtures import (
    TRIP_TZ,
    katalog_eintrag_ersetzt,
    lege_trip_an,
    segmente,
    sende,
    standard_felder,
)
from tests.helpers.verlauf_abdeckung import grenzen
from tests.tdd._gsm7_charset import assert_gsm7_clean
from utils.ascii_fold import fold_ascii

# ---------------------------------------------------------------------------
# Feste Bezugspunkte
# ---------------------------------------------------------------------------

TZ = ZoneInfo("Europe/Paris")
TAG = 10  # 2026-09-10, Europe/Paris (CEST) -- beliebig, nur fest

VIS = get_metric("visibility")            # sms_code "VS", decimals=1, km
TEMP = get_metric("temperature")          # sms_code "D", decimals=0, °C
NIGHT = get_metric("temperature_night")   # sms_code "" -> col_label "Night"
DAYMAX = get_metric("temperature_day_high")  # sms_code "" -> col_label "DayMax"
WDIR = get_metric("wind_direction")       # sms_code "WD", nicht-numerisch (Grad -> Kuerzel)
THDR = get_metric("thunder")              # sms_code "TH", is_level (Stufe -> Buchstabe)
PTYPE = get_metric("precip_type")         # sms_code "PT", Enum-Wert (kein Zahlwert)


def _pt(stunde: int, wert, *, tag: int = TAG) -> DrilldownPoint:
    """Ein Datenpunkt an einer FESTEN Ortsstunde (Europe/Paris)."""
    return DrilldownPoint(ts=datetime(2026, 9, tag, stunde, tzinfo=TZ), value=wert)


def _res(werte, *, start_stunde: int = 8, metric_field: str = "visibility_m") -> DrilldownResult:
    """``DrilldownResult`` aus einer Werteliste ab ``start_stunde``, stuendlich."""
    return DrilldownResult(
        trip_id="tdd-2207", metric=metric_field,
        points=[_pt(start_stunde + i, v) for i, v in enumerate(werte)],
        available=True,
    )


def _res_paare(paare, *, metric_field: str = "visibility_m") -> DrilldownResult:
    """``DrilldownResult`` aus ``(stunde, wert)``-Paaren — erlaubt, eine Stunde
    GANZ auszulassen (AC-12, zweiter Fall)."""
    return DrilldownResult(
        trip_id="tdd-2207", metric=metric_field,
        points=[_pt(h, v) for h, v in paare],
        available=True,
    )


def _kurzform(res: DrilldownResult, metric, *, tz=TZ, folgetag: bool = False) -> str:
    """Ruft den ECHTEN (noch zu bauenden) Kurzform-Formatierer.

    RED heute: ``TripCommandProcessor`` hat noch keine
    ``_format_drilldown_kurzform`` — jeder Aufruf wirft ``AttributeError``.
    """
    return TripCommandProcessor()._format_drilldown_kurzform(
        res, metric, tz, folgetag=folgetag,
    )


def _kuerzel(body: str) -> str:
    """Erstes Wort der Kurzform-Zeile (das Kuerzel, ggf. mit ``+``)."""
    return body.split(" ", 1)[0]


#: Ein Kurzform-Token: ``{wert}@{stunde}`` oder ``{wert}@{stunde}-{stunde}``.
#: ``wert`` darf auch ``?`` sein (AC-12, praesenter aber leerer Punkt).
TOKEN = re.compile(r"(?P<wert>[^\s@]+)@(?P<h1>\d{1,3})(?:-(?P<h2>\d{1,3}))?")


def _tokens(body: str) -> list[tuple[str, str, str | None]]:
    """Alle Kurzform-Tokens in Reihenfolge, als ``(wert, h1, h2)``-Tupel."""
    return [
        (m.group("wert"), m.group("h1"), m.group("h2"))
        for m in TOKEN.finditer(body)
    ]


def _stelle_gesendetes(monkeypatch) -> list[dict]:
    """Ersetzt ``PremiumSmsOutput.send`` an der KLASSE (Draht-Messpunkt,
    Vorbild ``test_premium_sms_kommandopfad.py``). Liefert die Liste, in die
    jeder Sendeaufruf gebucht wird."""
    gesendet: list[dict] = []

    def _send(self, subject, body) -> None:
        gesendet.append({"subject": subject, "body": body})

    monkeypatch.setattr(PremiumSmsOutput, "send", _send)
    return gesendet


def _dummy_settings() -> Settings:
    """Settings, mit denen ``PremiumSmsOutput(...)`` konstruierbar ist, ohne
    dass je echt gesendet wird (``.send`` ist an der Klasse ersetzt)."""
    return Settings(_env_file=None, seven_api_key="dummy-not-real")


# ═══════════════════════════ AC-1 ════════════════════════════════════════


def test_ac1_premium_sms_und_sms_erhalten_kurzform_am_draht(monkeypatch):
    """AC-1.

    GIVEN ein Ad-hoc-Verlaufsabruf ('wind') ueber die Kanaele premium_sms
          und sms
    WHEN  die Antwort erzeugt und (fuer premium_sms) ueber den echten
          Versandpfad ``send_command_reply_premium_sms`` bis zum echten
          ``PremiumSmsOutput.send`` geschickt wird
    THEN  traegt der am DRAHT ankommende Text Katalog-Kuerzel + @-Notation,
          keine ausgeschriebenen Woerter/HH:MM-Uhrzeiten; derselbe Verlauf
          liefert ueber channel="sms" dieselbe Bauform.
    """
    fix = lege_trip_an("2207-ac1")

    result_premium = sende(fix, "wind", channel="premium_sms")
    result_sms = sende(fix, "wind", channel="sms")

    assert result_premium.success and result_sms.success, (
        f"Vorbedingung: 'wind' muss Werte liefern.\n"
        f"premium_sms={result_premium}\nsms={result_sms}"
    )

    for label, body in (
        ("premium_sms", result_premium.confirmation_body),
        ("sms", result_sms.confirmation_body),
    ):
        assert not re.search(r"\d{2}:\d{2}", body), (
            f"AC-1 ({label}): Kurzform darf KEINE HH:MM-Uhrzeit tragen, "
            f"erhalten:\n{body!r}"
        )
        assert "Verlauf" not in body, (
            f"AC-1 ({label}): Kurzform hat keine Langform-Kopfzeile "
            f"'... — Verlauf', erhalten:\n{body!r}"
        )
        assert _kuerzel(body) == "W", (
            f"AC-1 ({label}): erwartetes Katalog-Kuerzel 'W' (Wind), "
            f"erhalten {_kuerzel(body)!r} in {body!r}"
        )
        assert _tokens(body), (
            f"AC-1 ({label}): erwarte mindestens ein Wert@Stunde-Token, "
            f"erhalten:\n{body!r}"
        )

    assert result_premium.confirmation_body == result_sms.confirmation_body, (
        "AC-1: premium_sms und sms muessen dieselbe Kurzform-Bauform liefern.\n"
        f"premium_sms={result_premium.confirmation_body!r}\n"
        f"sms={result_sms.confirmation_body!r}"
    )

    # Draht-Messpunkt (nicht der Formatierer): echtes PremiumSmsOutput.send.
    gesendet = _stelle_gesendetes(monkeypatch)
    settings = _dummy_settings()
    NotificationService(settings=settings).send_command_reply_premium_sms(
        result_premium, settings,
    )

    assert len(gesendet) == 1, (
        f"AC-1: genau EIN Sendeaufruf am echten PremiumSmsOutput.send "
        f"erwartet, gesehen {len(gesendet)}: {gesendet!r}"
    )
    draht_body = gesendet[0]["body"]
    assert draht_body == result_premium.confirmation_body, (
        "AC-1: der am Draht ankommende Text muss unveraendert die "
        "confirmation_body sein."
    )
    assert not re.search(r"\d{2}:\d{2}", draht_body), (
        f"AC-1: der am DRAHT gemessene Text darf keine HH:MM-Uhrzeit tragen, "
        f"erhalten: {draht_body!r}"
    )
    assert _kuerzel(draht_body) == "W"


def test_ac1_strukturierter_token_ueber_handle_drilldown_erhaelt_kurzform():
    """AC-1 — der ZWEITE Aufrufort (``_handle_drilldown``).

    GIVEN derselbe Verlauf, aber ueber den strukturierten Token
          ``dd_wind_today`` abgerufen — der laeuft laut ``result.command``
          durch ``_handle_drilldown``, NICHT durch
          ``_handle_metric_drilldown`` (das getippte Katalog-Wort 'wind'
          liefert ``metrik_wind``)
    WHEN  er ueber premium_sms bzw. sms abgerufen wird
    THEN  kommt die Kurzform (Katalog-Kuerzel + @-Notation, kein HH:MM,
          keine Langform-Kopfzeile); ueber telegram/email bleibt es die
          Langform.

    Warum eigener Test: die Spec nennt in ihrer Source-Sektion AUSDRUECKLICH
    BEIDE Aufrufstellen (``_handle_drilldown`` und
    ``_handle_metric_drilldown``). Der Adversary-Durchlauf (F001) hat den
    Kurzform-Zweig in ``_handle_drilldown`` deaktiviert und die gesamte
    Suite blieb gruen — die Zusicherung war an DIESER Stelle ungeprueft.
    """
    fix = lege_trip_an("2207-ac1-dd")
    token = "### query: dd_wind_today"

    kurz = {k: sende(fix, token, channel=k) for k in ("premium_sms", "sms")}
    lang = {k: sende(fix, token, channel=k) for k in ("telegram", "email")}

    for kanal, result in {**kurz, **lang}.items():
        assert result.command == "dd_wind_today", (
            f"Vorbedingung ({kanal}): der Token muss ueber "
            f"``_handle_drilldown`` laufen (command 'dd_wind_today'), "
            f"erhalten {result.command!r} — sonst misst dieser Test den "
            f"falschen Aufrufort."
        )
        assert result.success, (
            f"Vorbedingung ({kanal}): dd_wind_today muss Werte liefern, "
            f"erhalten: {result.confirmation_body!r}"
        )

    for kanal, result in kurz.items():
        body = result.confirmation_body
        assert not re.search(r"\d{2}:\d{2}", body), (
            f"AC-1 ({kanal}, _handle_drilldown): Kurzform darf KEINE "
            f"HH:MM-Uhrzeit tragen, erhalten:\n{body!r}"
        )
        assert "Verlauf" not in body, (
            f"AC-1 ({kanal}, _handle_drilldown): Kurzform hat keine "
            f"Langform-Kopfzeile '... — Verlauf', erhalten:\n{body!r}"
        )
        assert _kuerzel(body) == "W", (
            f"AC-1 ({kanal}, _handle_drilldown): erwartetes Katalog-Kuerzel "
            f"'W' (Wind), erhalten {_kuerzel(body)!r} in {body!r}"
        )
        assert _tokens(body), (
            f"AC-1 ({kanal}, _handle_drilldown): erwarte mindestens ein "
            f"Wert@Stunde-Token, erhalten:\n{body!r}"
        )

    assert (
        kurz["premium_sms"].confirmation_body == kurz["sms"].confirmation_body
    ), (
        "AC-1 (_handle_drilldown): premium_sms und sms muessen dieselbe "
        "Kurzform-Bauform liefern.\n"
        f"premium_sms={kurz['premium_sms'].confirmation_body!r}\n"
        f"sms={kurz['sms'].confirmation_body!r}"
    )

    # Gegenprobe am selben Aufrufort: telegram/email bleiben Langform.
    for kanal, result in lang.items():
        body = result.confirmation_body
        assert re.search(r"\d{2}:\d{2}", body), (
            f"AC-1/AC-2 ({kanal}, _handle_drilldown): die Langform muss "
            f"HH:MM-Uhrzeiten tragen, erhalten:\n{body!r}"
        )
        assert "Verlauf" in body, (
            f"AC-1/AC-2 ({kanal}, _handle_drilldown): die Langform muss "
            f"ihre Kopfzeile '... — Verlauf' behalten, erhalten:\n{body!r}"
        )
        assert not _tokens(body), (
            f"AC-1/AC-2 ({kanal}, _handle_drilldown): die Langform darf "
            f"KEINE Kurzform-@-Notation tragen, erhalten:\n{body!r}"
        )


# ═══════════════════════════ AC-2 ════════════════════════════════════════


def test_ac2_langform_email_und_telegram_bleiben_zeichengleich_WAECHTER():
    """AC-2 — REGRESSIONSWAECHTER, bewusst von Anfang an GRUEN (kein
    RED-Test): der Erwartungstext ist der HEUTIGE Stand, wörtlich am
    Stand VOR dieser Scheibe abgenommen (2026-09-08, s. Modul-Docstring
    dieser Datei) — genau das Spec-Beispiel aus
    ``feat_2207_kurzform_verlauf.md``.

    GIVEN dieselbe feste DrilldownResult-Fixtur (Sichtweite 0.3/5.0/42.5 km
          ueber acht Stunden, 14:00-21:00 Ortszeit)
    WHEN  die Langform fuer channel=email (with_emoji=False) und
          channel=telegram (with_emoji=True) erzeugt wird
    THEN  bleibt der Text in BEIDEN Faellen exakt zeichengleich zum
          heutigen Stand — die Kurzform-Aenderung wirkt sich auf diese
          beiden Kanaele nicht aus.
    """
    werte = [300.0, 300.0, 300.0, 5000.0, 42500.0, 42500.0, 42500.0, 42500.0]
    res = _res(werte, start_stunde=14)

    erwartet = (
        "Sichtweite — Verlauf\n"
        "14:00–16:00  0.3 km\n"
        "17:00  5.0 km\n"
        "18:00–21:00  42.5 km"
    )

    tcp = TripCommandProcessor()
    fmt = _metric_formatter(VIS)
    email = tcp._format_drilldown(res, VIS.label_de, fmt, TZ, with_emoji=False)
    telegram = tcp._format_drilldown(res, VIS.label_de, fmt, TZ, with_emoji=True)

    assert email == erwartet, (
        f"AC-2: E-Mail-Langform hat sich veraendert.\n"
        f"Erwartet: {erwartet!r}\nErhalten: {email!r}"
    )
    assert telegram == erwartet, (
        f"AC-2: Telegram-Langform hat sich veraendert.\n"
        f"Erwartet: {erwartet!r}\nErhalten: {telegram!r}"
    )


# ═══════════════════════════ AC-3 ════════════════════════════════════════


def test_ac3_kuerzel_ist_sms_code_oder_bei_leerem_sms_code_col_label():
    """AC-3.

    GIVEN eine Groesse mit gesetztem sms_code (visibility, 'VS') sowie die
          beiden Ausnahmen temperature_night/temperature_day_high, deren
          sms_code bewusst leer ist
    WHEN  die Kurzform fuer sie erzeugt wird
    THEN  steht bei visibility 'VS' vorn, bei den beiden Ausnahmen der
          col_label ('Night' bzw. 'DayMax') — keine zweite, eigene
          Abkuerzung.
    """
    assert VIS.sms_code == "VS", "Vorbedingung: visibility.sms_code muss 'VS' sein."
    assert NIGHT.sms_code == "" and NIGHT.col_label == "Night", (
        "Vorbedingung: temperature_night muss leeren sms_code und "
        "col_label='Night' tragen."
    )
    assert DAYMAX.sms_code == "" and DAYMAX.col_label == "DayMax", (
        "Vorbedingung: temperature_day_high muss leeren sms_code und "
        "col_label='DayMax' tragen."
    )

    res_vis = _res([5000.0])
    res_night = _res([18.0], metric_field="t2m_c")
    res_day = _res([18.0], metric_field="t2m_c")

    kuerzel_vis = _kuerzel(_kurzform(res_vis, VIS))
    kuerzel_night = _kuerzel(_kurzform(res_night, NIGHT))
    kuerzel_day = _kuerzel(_kurzform(res_day, DAYMAX))

    assert kuerzel_vis == "VS", f"Erwartet 'VS', erhalten {kuerzel_vis!r}"
    assert kuerzel_night == "Night", f"Erwartet 'Night', erhalten {kuerzel_night!r}"
    assert kuerzel_day == "DayMax", f"Erwartet 'DayMax', erhalten {kuerzel_day!r}"


# ═══════════════════════════ AC-4 ════════════════════════════════════════


def test_ac4_gleiche_folgestunden_werden_bereich_luecke_bricht_ab():
    """AC-4.

    GIVEN drei gleichwertige Folgestunden (8-10 Uhr), eine Einzelstunde mit
          ANDEREM Wert (11 Uhr), eine ausgelassene Stunde (12 Uhr fehlt
          GANZ) und danach wieder der ALTE Wert (13 Uhr)
    WHEN  die Kurzform erzeugt wird
    THEN  ergeben sich genau drei Tokens: ein Bereich 8-10, eine Einzelstunde
          11, eine Einzelstunde 13 — die Luecke wird NICHT ueberbrueckt,
          obwohl 13 Uhr denselben Wert wie 8-10 traegt.
    """
    res = _res_paare([
        (8, 5000.0), (9, 5000.0), (10, 5000.0),
        (11, 300.0),
        (13, 5000.0),
    ])
    body = _kurzform(res, VIS)

    assert _tokens(body) == [
        ("5.0", "8", "10"),
        ("0.3", "11", None),
        ("5.0", "13", None),
    ], f"AC-4: unerwartete Tokenfolge:\n{body!r}"


# ═══════════════════════════ AC-5 ════════════════════════════════════════


def test_ac5_werte_ohne_einheit_stunde_ohne_fuehrende_null_rundung_nach_katalog():
    """AC-5.

    GIVEN ein Sichtweiten-Wert 5000 m (= 5.0 km) an einer EINSTELLIGEN
          Stunde (8 Uhr) sowie ein Temperaturwert 9.7°C
    WHEN  die Kurzform erzeugt wird
    THEN  erscheint der Wert OHNE Einheit ('5.0' nicht '5.0 km'), die Stunde
          OHNE fuehrende Null ('8' nicht '08'), Temperatur ganzzahlig
          gerundet ('10' fuer 9.7).
    """
    res_vis = _res_paare([(8, 5000.0)])
    body_vis = _kurzform(res_vis, VIS)
    assert body_vis == "VS 5.0@8", f"Erwartet 'VS 5.0@8', erhalten {body_vis!r}"

    res_temp = _res_paare([(8, 9.7)], metric_field="t2m_c")
    body_temp = _kurzform(res_temp, TEMP)
    assert body_temp == "D 10@8", f"Erwartet 'D 10@8', erhalten {body_temp!r}"


def test_ac5_windrichtung_kurzform_zeigt_himmelsrichtung_langform_unveraendert():
    """AC-5 (Schaerfung, nicht-numerische Groesse Nr. 1).

    GIVEN ein Windrichtungs-Verlauf in GRAD (270/270/315) — eine Groesse, die
          ``format_value`` nicht kennt und die deshalb bisher roh als Zahl
          ('270') in der Kurzform stand: laenger als die Langform ('W') und
          ausserhalb der Kurzform-Grammatik (``sms_format.md`` §3.2a/§5a)
    WHEN  derselbe Verlauf einmal in Kurzform und einmal in Langform
          (E-Mail ohne Emoji, Telegram mit Emoji) erzeugt wird
    THEN  traegt die Kurzform das Himmelsrichtungs-Kuerzel ('WD W@8-9 NW@10')
          UND die Langform zeigt unveraendert ihr bisheriges Wort ('W'/'NW'
          mit HH:MM-Zeiten) — die Umrechnung ist dieselbe
          (``degrees_to_compass``), nur die Darstellung unterscheidet sich.
    """
    res = _res_paare(
        [(8, 270.0), (9, 270.0), (10, 315.0)], metric_field="wind_direction_deg",
    )

    kurz = _kurzform(res, WDIR)
    assert kurz == "WD W@8-9 NW@10", (
        f"AC-5: Windrichtung muss in der Kurzform das Himmelsrichtungs-"
        f"Kuerzel tragen (nicht die Gradzahl), erhalten {kurz!r}"
    )

    erwartet_lang = (
        "Windrichtung — Verlauf\n"
        "08:00–09:00  W\n"
        "10:00  NW"
    )
    tcp = TripCommandProcessor()
    fmt = _metric_formatter(WDIR)
    for label, with_emoji in (("email", False), ("telegram", True)):
        lang = tcp._format_drilldown(res, WDIR.label_de, fmt, TZ, with_emoji=with_emoji)
        assert lang == erwartet_lang, (
            f"AC-5/AC-2 ({label}): die Langform darf sich durch die "
            f"Kurzform-Korrektur NICHT aendern.\n"
            f"Erwartet: {erwartet_lang!r}\nErhalten: {lang!r}"
        )


def test_ac5_gewitterstufen_kurzform_zeigt_stufenbuchstaben_langform_unveraendert():
    """AC-5 (Schaerfung, nicht-numerische Groesse Nr. 2).

    GIVEN ein Gewitter-Verlauf ueber alle vier Stufen (NONE/LOW/MED/HIGH) —
          eine Stufengroesse, die bisher mit dem rohen Enum-Namen ('HIGH') in
          der Kurzform stand: laenger als die Langform ('hoch') und nicht der
          Stufenbuchstabe, den ``sms_format.md`` §3.2/§4 fuer ``TH:`` fuehrt
    WHEN  derselbe Verlauf einmal in Kurzform und einmal in Langform
          (E-Mail ohne Emoji) erzeugt wird
    THEN  traegt die Kurzform je Stufe den Buchstaben ('-'/'L'/'M'/'H') UND
          die Langform zeigt unveraendert ihre bisherigen Woerter
          ('kein'/'leicht'/'mittel'/'hoch') — dieselbe Skala
          (``thunder_label_value`` + ``tokens/metrics.LEVELS``), die auch das
          Briefing-Token ``TH:`` benutzt.
    """
    res = _res_paare(
        [
            (8, ThunderLevel.NONE), (9, ThunderLevel.LOW),
            (10, ThunderLevel.MED), (11, ThunderLevel.HIGH),
        ],
        metric_field="thunder_level",
    )

    kurz = _kurzform(res, THDR)
    assert kurz == "TH -@8 L@9 M@10 H@11", (
        f"AC-5: jede Gewitterstufe muss in der Kurzform ihren "
        f"Stufenbuchstaben tragen (nicht den Enum-Namen), erhalten {kurz!r}"
    )
    assert _tokens(kurz) == [
        ("-", "8", None), ("L", "9", None), ("M", "10", None), ("H", "11", None),
    ], f"AC-5: unerwartete Tokenfolge fuer die Gewitterstufen:\n{kurz!r}"

    erwartet_lang = (
        "Gewitter — Verlauf\n"
        "08:00  kein\n"
        "09:00  leicht\n"
        "10:00  mittel\n"
        "11:00  hoch"
    )
    tcp = TripCommandProcessor()
    lang = tcp._format_drilldown(
        res, THDR.label_de, _metric_formatter(THDR), TZ, with_emoji=False,
    )
    assert lang == erwartet_lang, (
        f"AC-5/AC-2: die Langform darf sich durch die Kurzform-Korrektur "
        f"NICHT aendern.\nErwartet: {erwartet_lang!r}\nErhalten: {lang!r}"
    )


def _mit_niederschlagsart(i: int) -> dict:
    """Stundenpunkt der Standard-Fixtur, zusaetzlich mit Niederschlagsart.

    Die Art wechselt stuendlich zwischen RAIN und SNOW. Dadurch liegen in
    JEDEM Tagesfenster mindestens zwei verschiedene Auspraegungen, egal zu
    welcher Tageszeit der Lauf startet — der Test prueft deshalb den INHALT
    der Tokens, nie eine feste Stundenzahl (Zeitbomben-Lehre aus #2186).
    """
    felder = standard_felder(i)
    felder["precip_type"] = (PrecipType.RAIN, PrecipType.SNOW)[i % 2]
    return felder


def test_ac5_niederschlagsart_kurzform_ueber_kommandopfad_nennt_die_art(monkeypatch):
    """AC-5 (Schaerfung, nicht-numerische Groesse Nr. 3: der Enum-Rueckfall).

    GIVEN ein Trip, dessen Stundenpunkte eine Niederschlagsart (RAIN/SNOW)
          tragen — eine im Katalog gefuehrte, ueber das getippte Wort 'PType'
          erreichbare Groesse, deren Werte KEINE Zahlen sind: ``format_value``
          scheitert an ihnen (Vorbedingung unten misst das)
    WHEN  der Verlauf ueber den echten Kommandopfad mit channel="premium_sms"
          abgerufen wird
    THEN  antwortet die Kurzform mit dem Katalog-Kuerzel 'PT' und der ART als
          Token ('PT RAIN@14 SNOW@15 ...') — und der Abruf stuerzt
          AUSDRUECKLICH NICHT ab.

    Warum eigener Test: die beiden AC-5-Nachbarn oben decken nur die zwei
    NAMENTLICH gefuehrten Sonderzweige ab (Windrichtung, Stufengroesse). Der
    allgemeine Rueckfall fuer alles uebrige Nicht-Numerische (das
    ``try/except`` um ``format_value`` in ``_kurzform_wert``) war von keinem
    Test gedeckt: entfernt man ihn, bleiben alle anderen Tests gruen, waehrend
    dieser reale Abruf mit ``ValueError: could not convert string to float``
    abbricht (Adversary-Finding F005).
    """
    assert PTYPE.sms_code == "PT", (
        "Vorbedingung: precip_type.sms_code muss 'PT' sein."
    )
    with pytest.raises((TypeError, ValueError)):
        format_value(PTYPE.id, PrecipType.RAIN, style="bare")

    fix = lege_trip_an("2207-ac5-ptype", felder=_mit_niederschlagsart)
    result = sende(fix, "PType", channel="premium_sms")
    body = result.confirmation_body or ""

    assert result.command == "metrik_precip_type", (
        f"Vorbedingung: 'PType' muss den Niederschlagsart-Verlauf ausloesen, "
        f"erhalten {result.command!r} — sonst misst dieser Test die falsche "
        f"Groesse."
    )
    assert result.success, (
        f"AC-5: der Abruf einer nicht-numerischen Groesse muss eine Antwort "
        f"liefern (kein Absturz, kein 'no data'), erhalten: {body!r}"
    )
    assert _kuerzel(body) == "PT", (
        f"AC-5: erwartetes Katalog-Kuerzel 'PT', erhalten {_kuerzel(body)!r} "
        f"in {body!r}"
    )

    werte = [wert for wert, _h1, _h2 in _tokens(body)]
    assert werte, f"AC-5: erwarte Art@Stunde-Tokens, erhalten:\n{body!r}"
    assert set(werte) == {"RAIN", "SNOW"}, (
        f"AC-5: jedes Token muss die Niederschlagsart als Wort tragen "
        f"(erwartet genau RAIN und SNOW, stuendlich wechselnd), erhalten "
        f"{werte} in {body!r}"
    )
    assert "PrecipType" not in body, (
        f"AC-5: der Klassenname der Auspraegung darf nicht im Text stehen, "
        f"erhalten:\n{body!r}"
    )
    assert "?" not in body, (
        f"AC-5: jede Stunde traegt eine Art — es darf kein '?'-Platzhalter "
        f"entstehen:\n{body!r}"
    )
    assert_gsm7_clean(body, "Kurzform-Verlauf Niederschlagsart (AC-5)")

    # Draht-Gegenprobe: derselbe Text kommt unveraendert beim echten
    # PremiumSmsOutput.send an.
    gesendet = _stelle_gesendetes(monkeypatch)
    settings = _dummy_settings()
    NotificationService(settings=settings).send_command_reply_premium_sms(
        result, settings,
    )
    assert gesendet and gesendet[0]["body"] == body, (
        f"AC-5: der am Draht ankommende Text muss unveraendert die Kurzform "
        f"sein, gesehen: {gesendet!r}"
    )


# ═══════════════════════════ AC-6 ════════════════════════════════════════


def test_ac6_folgetag_traegt_plus_am_kuerzel():
    """AC-6.

    GIVEN derselbe Verlauf
    WHEN  die Kurzform einmal fuer den laufenden Tag (folgetag=False) und
          einmal fuer den Folgetag (folgetag=True) erzeugt wird
    THEN  traegt NUR das Kuerzel im Folgetag-Fall ein '+' ('VS+' statt
          'VS'); die Tokens selbst bleiben identisch.
    """
    res = _res([5000.0], start_stunde=8)
    heute = _kurzform(res, VIS, folgetag=False)
    morgen = _kurzform(res, VIS, folgetag=True)

    assert _kuerzel(heute) == "VS", f"Erwartet Kuerzel ohne '+': {heute!r}"
    assert _kuerzel(morgen) == "VS+", f"Erwartet Kuerzel mit '+': {morgen!r}"
    assert _tokens(heute) == _tokens(morgen), (
        f"AC-6: nur das Kuerzel darf sich unterscheiden, nicht die Tokens:\n"
        f"heute={heute!r}\nmorgen={morgen!r}"
    )


# ─────────── gemeinsame Fixtur fuer AC-7/AC-8/AC-9/AC-10 ─────────────────

#: Sieben Einzelstunden-Gruppen mit deutlich unterschiedlichen Werten (kein
#: Merge). Werte in Metern, Anzeige in km: 0.3/5.0/12.5/8.2/3.1/9.9/15.5.
_GROSSE_WERTE_M = [300.0, 5000.0, 12500.0, 8200.0, 3100.0, 9900.0, 15500.0]
_GROSSE_STUNDEN = [10, 11, 12, 13, 14, 15, 16]


# ═══════════════════════════ AC-7 ════════════════════════════════════════


def test_ac7_ausgelieferter_text_ueberschreitet_niemals_160_zeichen():
    """AC-7.

    GIVEN ein Verlauf mit vielen Wechselpunkten (40 paarweise
          unterschiedliche Stundenwerte — deutlich mehr, als 160 Zeichen
          im Kurzform-Format darstellen koennen)
    WHEN  die Kurzform erzeugt wird
    THEN  ueberschreitet der GSM-7-normalisierte Text nie 160 Zeichen.
    """
    start = datetime(2026, 9, 10, 0, tzinfo=TZ)
    res = DrilldownResult(
        trip_id="tdd-2207", metric="wind10m_kmh",
        points=[
            DrilldownPoint(ts=start + timedelta(hours=i), value=10.0 + i)
            for i in range(40)
        ],
        available=True,
    )
    body = _kurzform(res, get_metric("wind"))
    gefaltet = fold_ascii(body)

    assert len(gefaltet) <= 160, (
        f"AC-7: GSM-7-normalisierter Text ueberschreitet 160 Zeichen: "
        f"{len(gefaltet)}:\n{gefaltet!r}"
    )


#: Ein bewusst umlautreiches ``col_label`` (22 Zeichen, davon acht Umlaute).
#: ``fold_ascii()`` macht daraus 30 Zeichen — die Faltung VERLAENGERT den Text
#: also um acht Zeichen. Genau das ist der Hebel, mit dem der Test unten eine
#: Zeile baut, die roh unter, gefaltet aber ueber der Grenze liegt. Wie bei
#: ``test_ac11_...`` ist das kein Wort aus dem echten Katalog, sondern eine
#: Testfixtur fuer den Faltungspfad.
_FALTUNGS_LABEL = "NäächtküühlüngsPrüfmäß"


def test_ac7_grenze_misst_den_gefalteten_text_nicht_den_rohen(monkeypatch):
    """AC-7/AC-11 — die Reihenfolge "zuerst falten, DANN kuerzen".

    GIVEN eine Groesse mit leerem ``sms_code`` (also col_label als Kuerzel,
          AC-3), deren col_label acht Umlaute traegt, und 24 stuendlich
          verschiedene Werte — zusammen eine Zeile, die ROH 156 Zeichen lang
          ist (also unter der Grenze), nach ``fold_ascii()`` aber 164
          (``ä``->``ae`` verlaengert den Text)
    WHEN  die Kurzform erzeugt wird
    THEN  ueberschreitet der AUSGELIEFERTE, GSM-7-normalisierte Text
          trotzdem nie 160 Zeichen — es wurde zusaetzlich gekuerzt.

    Warum eigener Test (Adversary-Finding F001): ``_format_drilldown_kurzform``
    faltet heute VOR der Laengenmessung (``trip_command_processor.py:1385``).
    Vertauscht man die beiden Schritte, sodass die Grenze auf der UNGEFALTETEN
    Zeile geprueft wird, bleiben alle uebrigen Tests gruen — die Zusicherung
    war an dieser Stelle unbewacht. Der Grund: ``fold_ascii()`` verlaengert
    nur nicht-ASCII-Text, und im echten Katalog entsteht kein umlautbehaftetes
    Kuerzel (die beiden Groessen mit leerem ``sms_code`` sind reines ASCII,
    und ``0°Line`` traegt ``sms_code="FZ"`` und benutzt seinen col_label nie).
    Die Fixtur stellt genau diesen Fall her; formatiert wird vom ECHTEN
    Formatierer.
    """
    assert NIGHT.sms_code == "", (
        "Vorbedingung: temperature_night muss leeren sms_code tragen, sonst "
        "kommt der col_label gar nicht als Kuerzel zum Zug (AC-3)."
    )

    stunden = list(range(24))
    werte = [10.0 + i for i in stunden]

    with katalog_eintrag_ersetzt(
        monkeypatch, "temperature_night",
        col_label=_FALTUNGS_LABEL, decimals=0,
    ) as metric:
        res = _res_paare(list(zip(stunden, werte)), metric_field="t2m_c")
        body = _kurzform(res, metric)

        roh = " ".join([
            _FALTUNGS_LABEL,
            *(
                f"{format_value('temperature_night', v, style='bare')}@{h}"
                for h, v in zip(stunden, werte)
            ),
        ])

    assert len(roh) <= 160, (
        f"Vorbedingung verletzt: die ungekuerzte Zeile muss ROH unter die "
        f"Grenze passen ({len(roh)} Zeichen) — sonst wuerde auch eine "
        f"Pruefung VOR der Faltung kuerzen und der Test unterschiede die "
        f"beiden Reihenfolgen nicht:\n{roh!r}"
    )
    assert len(fold_ascii(roh)) > 160, (
        f"Vorbedingung verletzt: dieselbe Zeile muss GEFALTET ueber die "
        f"Grenze laufen ({len(fold_ascii(roh))} Zeichen), sonst gaebe es "
        f"nichts zu kuerzen:\n{fold_ascii(roh)!r}"
    )

    assert len(fold_ascii(body)) <= 160, (
        f"AC-7: der ausgelieferte, GSM-7-normalisierte Text ueberschreitet "
        f"160 Zeichen ({len(fold_ascii(body))}). Die Laengengrenze wurde "
        f"offenbar auf der UNGEFALTETEN Zeile gemessen (roh {len(roh)} "
        f"Zeichen, gefaltet {len(fold_ascii(roh))}) — bindend ist "
        f"sms_format.md:66 'zuerst falten, dann kuerzen':\n{body!r}"
    )
    assert len(body) <= 160, (
        f"AC-7: der ausgelieferte Text selbst ueberschreitet 160 Zeichen "
        f"({len(body)}):\n{body!r}"
    )
    assert_gsm7_clean(body, "Kurzform-Verlauf Faltungsgrenze (AC-7/AC-11)")

    # Gegenprobe, dass wirklich die Faltung die Kuerzung ausgeloest hat: die
    # Antwort nennt die weggefallenen Stunden (AC-9) und traegt das gefaltete
    # Kuerzel.
    assert "not shown" in body, (
        f"AC-7/AC-9: die Zeile musste gekuerzt werden — dann muss sie die "
        f"Luecke auch NENNEN:\n{body!r}"
    )
    assert _kuerzel(body) == fold_ascii(_FALTUNGS_LABEL), (
        f"Gegenprobe: das Kuerzel muss der gefaltete col_label sein, "
        f"erhalten {_kuerzel(body)!r} in {body!r}"
    )


# ═══════════════════════════ AC-8 ════════════════════════════════════════


def test_ac8_kuerzung_entfernt_nur_hintere_ganze_gruppen(monkeypatch):
    """AC-8.

    GIVEN sieben Wechselpunkt-Gruppen, deren Dezimalstellen befristet auf
          22 gesetzt sind (reines Testwerkzeug fuer den exakten
          160-Zeichen-Grenzfall, s. Modul-Docstring) — dadurch passen
          GENAU die ersten fuenf unter die Grenze
    WHEN  die Kurzform erzeugt wird
    THEN  stehen die ersten fuenf Gruppen VOLLSTAENDIG, UNVERAENDERT und in
          UNVERAENDERTER Reihenfolge; Gruppen sechs und sieben fehlen GANZ —
          keine Gruppe aus der Mitte fehlt.
    """
    with katalog_eintrag_ersetzt(monkeypatch, "visibility", decimals=22) as metric:
        res = _res_paare(list(zip(_GROSSE_STUNDEN, _GROSSE_WERTE_M)))
        body = _kurzform(res, metric)

        erwartete_tokens = [
            f"{format_value('visibility', v, style='bare')}@{h}"
            for h, v in zip(_GROSSE_STUNDEN, _GROSSE_WERTE_M)
        ]
        voll = f"{_kuerzel(body)} " + " ".join(erwartete_tokens)
        assert len(voll) > 160, (
            f"Vorbedingung verletzt: die volle (ungekuerzte) Zeile waere "
            f"nur {len(voll)} Zeichen lang — keine Kuerzung noetig, dieser "
            f"Test prueft dann nichts:\n{voll!r}"
        )
        assert len(body) <= 160, (
            f"AC-7-Vorbedingung: die ausgelieferte Zeile selbst "
            f"ueberschreitet 160 Zeichen: {len(body)}:\n{body!r}"
        )

        for token in erwartete_tokens[:5]:
            assert token in body, (
                f"AC-8: erwartete Gruppe {token!r} fehlt oder wurde "
                f"veraendert:\n{body!r}"
            )
        for token in erwartete_tokens[5:]:
            assert token not in body, (
                f"AC-8: Gruppe {token!r} (eine der hinteren zwei) darf "
                f"NICHT mehr in der gekuerzten Antwort stehen:\n{body!r}"
            )

        gefundene_reihenfolge = [
            m.group(0) for m in re.finditer(r"\S+@\d{1,3}(?:-\d{1,3})?", body)
        ]
        assert gefundene_reihenfolge == erwartete_tokens[:5], (
            f"AC-8: Vollstaendigkeit/Reihenfolge der ersten fuenf Gruppen "
            f"verletzt (keine darf aus der MITTE fehlen) — erhalten "
            f"{gefundene_reihenfolge}, erwartet {erwartete_tokens[:5]}:\n"
            f"{body!r}"
        )


# ═══════════════════════════ AC-9 ════════════════════════════════════════


def test_ac9_gekuerzte_antwort_traegt_anhang_ungekuerzte_nicht(monkeypatch):
    """AC-9.

    GIVEN dieselbe gekuerzte Antwort aus AC-8 (zwei weggefallene
          Einzelstunden-Gruppen = 2 Stunden) sowie eine ZWEITE, deutlich
          kleinere Antwort, die gar nicht gekuerzt werden muss
    WHEN  beide Antworten erzeugt werden
    THEN  traegt NUR die gekuerzte Antwort den englischen Anhang mit der
          KORREKTEN Stundenzahl ('+2h not shown'); die ungekuerzte traegt
          KEINEN Anhang.
    """
    with katalog_eintrag_ersetzt(monkeypatch, "visibility", decimals=22) as metric:
        res = _res_paare(list(zip(_GROSSE_STUNDEN, _GROSSE_WERTE_M)))
        gekuerzt = _kurzform(res, metric)

    assert "+2h not shown" in gekuerzt, (
        f"AC-9: erwarte den Anhang '+2h not shown' (zwei weggefallene "
        f"Einzelstunden-Gruppen bei den Stunden {_GROSSE_STUNDEN[5:]}), "
        f"erhalten:\n{gekuerzt!r}"
    )

    kleiner_res = _res_paare([(14, 5000.0), (15, 300.0)])
    ungekuerzt = _kurzform(kleiner_res, VIS)
    assert "not shown" not in ungekuerzt, (
        f"AC-9: eine ungekuerzte Antwort darf KEINEN Kuerzungs-Anhang "
        f"tragen:\n{ungekuerzt!r}"
    )


# ═══════════════════════════ AC-10 ═══════════════════════════════════════


def test_ac10_uebergrosser_verlauf_loest_genau_einen_sendeaufruf_aus(monkeypatch):
    """AC-10.

    GIVEN ein echter Kommandolauf ('wind' ueber premium_sms) auf einen
          Trip, dessen Wind-Dezimalstellen befristet stark aufgeblaeht sind
          (deterministisch ueber-160-Zeichen, unabhaengig von der realen
          Tageszeit)
    WHEN  die Antwort ueber den echten Versandpfad
          ``send_command_reply_premium_sms`` verschickt wird
    THEN  geht GENAU EIN Sendeaufruf am echten PremiumSmsOutput.send heraus
          — Zaehlung am Transport, nicht am Rueckgabetyp.
    """
    with katalog_eintrag_ersetzt(monkeypatch, "wind", decimals=60):
        fix = lege_trip_an("2207-ac10")
        result = sende(fix, "wind", channel="premium_sms")
        assert result.success, f"Vorbedingung: 'wind' muss liefern: {result}"
        assert len(result.confirmation_body) <= 160, (
            f"Vorbedingung (AC-7): die Kurzform muss selbst bei stark "
            f"aufgeblaehten Dezimalstellen unter 160 Zeichen bleiben, "
            f"erhalten {len(result.confirmation_body)} Zeichen."
        )

        gesendet = _stelle_gesendetes(monkeypatch)
        settings = _dummy_settings()
        NotificationService(settings=settings).send_command_reply_premium_sms(
            result, settings,
        )

    assert len(gesendet) == 1, (
        f"AC-10: auf einen uebergrossen Verlauf darf GENAU EIN Sendeaufruf "
        f"erfolgen, gesehen {len(gesendet)}: {gesendet!r}"
    )
    assert gesendet[0]["body"] == result.confirmation_body, (
        "AC-10: der gesendete Text muss die unveraenderte confirmation_body "
        "sein."
    )


# ═══════════════════════════ AC-11 ═══════════════════════════════════════


def test_ac11_kurzform_text_enthaelt_ausschliesslich_gsm7_zeichen(monkeypatch):
    """AC-11.

    GIVEN eine Groesse, deren col_label (der Kuerzel-Ersatz bei leerem
          sms_code, AC-3) Gedankenstrich, Mittelpunkt, Gradzeichen und
          Umlaute traegt
    WHEN  die Kurzform-Antwort erzeugt wird
    THEN  enthaelt der ausgelieferte Text ausschliesslich GSM-7-taugliche
          Zeichen — fold_ascii() muss auf den Kurzform-Pfad wirken.
    """
    schmutzig = "Käl–t°Mittelpunkt·Ü"
    assert any(ch in schmutzig for ch in "äöüÄÖÜß–·°"), (
        "Vorbedingung: die Testfixtur muss tatsaechlich unsaubere Zeichen "
        "tragen, sonst prueft dieser Test nichts."
    )

    with katalog_eintrag_ersetzt(
        monkeypatch, "temperature_night", col_label=schmutzig,
    ) as metric:
        res = _res_paare([(8, 18.0)], metric_field="t2m_c")
        body = _kurzform(res, metric)

    for ch in "äöüÄÖÜß–·°":
        assert ch not in body, (
            f"AC-11: verbotenes Zeichen {ch!r} steht noch im ausgelieferten "
            f"Kurzform-Text:\n{body!r}"
        )
    assert_gsm7_clean(body, "Kurzform-Verlauf (AC-11)")


# ═══════════════════════════ AC-12 ═══════════════════════════════════════


def test_ac12_praesenter_leerer_wert_zeigt_fragezeichen_fehlender_punkt_bricht_bereich():
    """AC-12.

    GIVEN (Fall A) die Stunde 9 ist PRAESENT, traegt aber ``value=None``;
          (Fall B) dieselbe Stunde 9 FEHLT stattdessen GANZ aus den Punkten
    WHEN  die Kurzform fuer beide Faelle erzeugt wird
    THEN  zeigt Fall A an Stunde 9 explizit '?' (drei Einzeltokens); Fall B
          zeigt dort GAR KEIN Token — der Bereich bricht einfach, ohne '?'.
    """
    res_praesent = _res_paare([(8, 5000.0), (9, None), (10, 5000.0)])
    body_praesent = _kurzform(res_praesent, VIS)
    assert _tokens(body_praesent) == [
        ("5.0", "8", None), ("?", "9", None), ("5.0", "10", None),
    ], (
        f"AC-12 (Fall A, praesent aber leer): erwarte drei Einzeltokens "
        f"mit '?' bei Stunde 9, erhalten:\n{body_praesent!r}"
    )

    res_fehlend = _res_paare([(8, 5000.0), (10, 5000.0)])
    body_fehlend = _kurzform(res_fehlend, VIS)
    assert _tokens(body_fehlend) == [
        ("5.0", "8", None), ("5.0", "10", None),
    ], (
        f"AC-12 (Fall B, Zeitpunkt fehlt ganz): erwarte zwei Einzeltokens "
        f"OHNE '?'-Token, erhalten:\n{body_fehlend!r}"
    )
    assert "?" not in body_fehlend, (
        f"AC-12 (Fall B): ein GANZ fehlender Zeitpunkt darf KEIN "
        f"'?'-Token erzeugen:\n{body_fehlend!r}"
    )


# ═══════════════════════════ AC-13 ═══════════════════════════════════════


def test_ac13_komplett_ungefuellte_groesse_meldet_das_ausdruecklich():
    """AC-13.

    GIVEN ein Trip, dessen Stundenpunkte fuer 'visibility_m' komplett
          UNBEFUELLT sind (kein einziger Wert im Fenster)
    WHEN  die Kurzform-Antwort ueber premium_sms abgerufen wird
    THEN  meldet sie das AUSDRUECKLICH — kein Schweigen, keine leere oder
          falsch interpretierbare Kurzform-Zeile ('gefuehrt != gefuellt').
    """
    fix = lege_trip_an(
        "2207-ac13",
        felder=lambda i: {
            "t2m_c": 10.0, "wind10m_kmh": 20.0, "precip_1h_mm": 0.0,
            "thunder_level": ThunderLevel.NONE,
            # visibility_m bleibt bewusst UNGESETZT -> alle Punkte None.
        },
    )
    result = sende(fix, "visib", channel="premium_sms")
    body = result.confirmation_body or ""

    assert body.strip(), "AC-13: die Antwort darf nicht leer sein."
    assert not TOKEN.search(body), (
        f"AC-13: keine @-Notation, wenn die Groesse gar nicht befuellt "
        f"ist — sonst taeuscht die Antwort Daten vor, die es nicht gibt:\n"
        f"{body!r}"
    )
    assert re.search(r"no data|not available", body, re.IGNORECASE), (
        f"AC-13: erwarte eine erkennbare 'keine Daten'-Aussage (Spec "
        f"Implementation Details Punkt 5: kurzer englischer Text), "
        f"erhalten:\n{body!r}"
    )


# ═══════════════════════════ AC-14 ═══════════════════════════════════════


def test_ac14_langform_und_kurzform_teilen_dieselbe_gruppierung():
    """AC-14.

    GIVEN dieselbe DrilldownResult (mit Bereich, Einzelstunde und Luecke)
    WHEN  sie einmal an ``_format_drilldown`` (Langform) und einmal an die
          neue Kurzform-Formatierung uebergeben wird
    THEN  stimmen Anzahl und Zeitgrenzen der erkannten Wechselpunkt-Gruppen
          UEBEREIN — nur die Textdarstellung unterscheidet sich. Die
          Gruppengrenzen koennen dadurch strukturell nie auseinanderlaufen
          (geteilter Gruppierungs-Helfer, Spec-Mutations-Gegenprobe).

    Die Fixtur traegt bewusst BEIDE Lueckenarten (Adversary-Fix F002):
    eine Luecke mit UNTERSCHIEDLICHEM Wert davor/danach (Stunde 12) und —
    entscheidend — eine Luecke mit IDENTISCHEM Wert unmittelbar davor und
    danach (Stunde 15, gleicher Wert bei 14 und 16). Nur der zweite Fall
    macht eine abweichende Lueckentoleranz sichtbar: ein Duplikat des
    Gruppierungs-Helfers mit 2h-Toleranz wuerde 13-14 und 16 zu EINER
    Gruppe verschmelzen, waehrend die Langform bei zwei Gruppen bliebe.
    Ohne diesen Fall bewachte AC-14 seine eigene Zusicherung nicht.
    """
    res = _res_paare([
        (8, 5000.0), (9, 5000.0), (10, 5000.0),
        (11, 300.0),
        (13, 5000.0), (14, 5000.0),
        (16, 5000.0),
    ])
    tcp = TripCommandProcessor()
    fmt = _metric_formatter(VIS)
    langform = tcp._format_drilldown(res, VIS.label_de, fmt, TZ, with_emoji=False)
    kurzform = _kurzform(res, VIS)

    lang_grenzen = [
        (int(von.split(":")[0]), int(bis.split(":")[0]) if bis else None)
        for von, bis in grenzen(langform)
    ]
    kurz_grenzen = [
        (int(m.group("h1")), int(m.group("h2")) if m.group("h2") else None)
        for m in TOKEN.finditer(kurzform)
    ]

    assert lang_grenzen == kurz_grenzen, (
        f"AC-14: Gruppengrenzen laufen zwischen Lang- und Kurzform "
        f"auseinander:\nlangform={lang_grenzen} ({langform!r})\n"
        f"kurzform={kurz_grenzen} ({kurzform!r})"
    )

    # Der Fall, der eine abweichende Lueckentoleranz ueberhaupt erst
    # sichtbar macht: gleicher Wert bei 14 und 16, Stunde 15 fehlt. Bei
    # korrekter 1h-Toleranz sind das ZWEI Gruppen; eine lockerere Toleranz
    # verschmilzt sie zu einer und behauptet damit einen Wert fuer die
    # ungemessene Stunde 15.
    assert (13, 14) in kurz_grenzen and (16, None) in kurz_grenzen, (
        f"AC-14: die Luecke bei Stunde 15 muss die Gruppe brechen — "
        f"erwartet ein Bereich 13-14 UND ein Einzeltoken 16, erhalten "
        f"{kurz_grenzen} ({kurzform!r})"
    )
    assert langform != kurzform, (
        "Gegenprobe: nur die Textdarstellung darf sich unterscheiden — "
        "waeren beide Texte identisch, priefte der Vergleich oben nichts."
    )


# ══════ Verdrahtungs-Waechter am Kommandopfad (Adversary-Runde 2) ════════
#
# Beide Tests messen am AUFRUFORT ``_handle_drilldown`` (strukturierter Token
# ``dd_METRIC_DAY``), nicht am Formatierer: dort WIRKT die Zusicherung.


def _ohne_windwerte(i: int) -> dict:
    """Stundenpunkt, dessen Windfeld gefuehrt, aber UNBEFUELLT ist."""
    return {
        "t2m_c": 10.0 + i,
        "precip_1h_mm": 0.0,
        "thunder_level": ThunderLevel.NONE,
        # wind10m_kmh bleibt bewusst ungesetzt -> alle Punkte tragen None.
    }


def test_ac13_strukturierter_token_ohne_werte_meldet_no_data(monkeypatch):
    """AC-13 am ZWEITEN Aufrufort (``_handle_drilldown``).

    GIVEN ein Trip, dessen Windfeld ueber das ganze Fenster komplett
          unbefuellt ist (Punkte liegen vor, tragen aber keinen Wert)
    WHEN  der Verlauf ueber den strukturierten Token ``dd_wind_today`` mit
          channel="premium_sms" abgerufen wird
    THEN  sagt die Kurzform das ausdruecklich ("W no data") — sie liefert
          KEINE Zeile voller Fragezeichen.

    Warum eigener Test: der Adversary hat am unveraenderten Code gemessen,
    dass dieselbe Datenlage ueber den getippten Weg 'no data' liefert, ueber
    den Token-Weg aber 'W ?@21-8' — zwei verschiedene Antworten auf dieselbe
    Lage, je nach Abrufweg (Finding F003).
    """
    fix = lege_trip_an("2207-ac13-dd", felder=_ohne_windwerte)
    result = sende(fix, "### query: dd_wind_today", channel="premium_sms")
    body = result.confirmation_body or ""

    assert result.command == "dd_wind_today", (
        f"Vorbedingung: der Token muss ueber ``_handle_drilldown`` laufen, "
        f"erhalten {result.command!r} — sonst misst dieser Test den falschen "
        f"Aufrufort."
    )
    assert body.strip(), "AC-13: die Antwort darf nicht leer sein."
    assert not TOKEN.search(body), (
        f"AC-13 (_handle_drilldown): keine @-Notation, wenn die Groesse "
        f"gar nicht befuellt ist — eine Zeile voller '?' taeuscht eine "
        f"Messung vor, die es nicht gibt:\n{body!r}"
    )
    assert re.search(r"\bno data\b", body, re.IGNORECASE), (
        f"AC-13 (_handle_drilldown): erwarte die englische 'no data'-Aussage "
        f"mit Kuerzel ('W no data'), erhalten:\n{body!r}"
    )

    # Gegenprobe am Draht: derselbe Text kommt unveraendert beim echten
    # PremiumSmsOutput.send an.
    gesendet = _stelle_gesendetes(monkeypatch)
    settings = _dummy_settings()
    NotificationService(settings=settings).send_command_reply_premium_sms(
        result, settings,
    )
    assert gesendet and gesendet[0]["body"] == body, (
        f"AC-13: der am Draht ankommende Text muss die 'no data'-Aussage "
        f"sein, gesehen: {gesendet!r}"
    )


def _ortsmitternacht(tag) -> datetime:
    """Ortsmitternacht (Europe/Paris) des Tages ``tag``, als UTC-Zeitpunkt."""
    return datetime(tag.year, tag.month, tag.day, tzinfo=TRIP_TZ).astimezone(
        timezone.utc,
    )


def _snapshot_zwei_ortstage(fix) -> None:
    """Stundenpunkte ab Ortsmitternacht HEUTE **und** ab Ortsmitternacht MORGEN.

    Die Standard-Fixtur legt 24 Punkte ab ``now`` an; das Morgen-Fenster
    beginnt aber erst an der naechsten Ortsmitternacht. Je nach Tageszeit des
    Laufs faende ``dd_wind_tomorrow`` darin nur wenige oder gar keine Punkte —
    genau die Zeitbombe aus #2186. Zwei volle Ortstage machen den Test
    tageszeitunabhaengig.
    """
    heute = fix.now.astimezone(TRIP_TZ).date()
    WeatherSnapshotService(fix.user_id).save(
        fix.trip_id,
        segmente(_ortsmitternacht(heute), standard_felder)
        + segmente(_ortsmitternacht(heute + timedelta(days=1)), standard_felder),
        fix.now.date(),
    )


def test_ac6_folgetag_verdrahtung_am_kommandopfad():
    """AC-6 — die VERDRAHTUNG ``day_token`` -> ``folgetag``.

    GIVEN derselbe Trip mit Stundenwerten fuer heute UND morgen
    WHEN  der Verlauf einmal als ``dd_wind_tomorrow`` und einmal als
          ``dd_wind_today`` ueber channel="premium_sms" abgerufen wird
    THEN  traegt NUR die Morgen-Antwort ein '+' am Kuerzel ('W+' gegen 'W').

    Warum eigener Test: ``test_ac6_folgetag_traegt_plus_am_kuerzel`` ruft den
    Formatierer direkt mit explizitem ``folgetag=``-Argument und prueft damit
    nur die Formatierung. Setzt man die Uebersetzung an den beiden
    Aufrufstellen auf ``folgetag=False``, bleibt sie gruen (Finding F004) —
    die Kennzeichnung koennte produktiv NIE mehr erscheinen.
    """
    fix = lege_trip_an("2207-ac6-dd")
    _snapshot_zwei_ortstage(fix)

    morgen = sende(fix, "### query: dd_wind_tomorrow", channel="premium_sms")
    heute = sende(fix, "### query: dd_wind_today", channel="premium_sms")

    for tag, result in (("morgen", morgen), ("heute", heute)):
        assert result.success, (
            f"Vorbedingung ({tag}): der Abruf muss Windwerte liefern, "
            f"erhalten: {result.confirmation_body!r}"
        )
        assert _tokens(result.confirmation_body), (
            f"Vorbedingung ({tag}): erwarte Wert@Stunde-Tokens, erhalten: "
            f"{result.confirmation_body!r}"
        )

    assert _kuerzel(morgen.confirmation_body) == "W+", (
        f"AC-6: ein Verlauf fuer den Folgetag muss das '+' am Kuerzel tragen "
        f"— ohne es waeren die Stundenzahlen zwischen heute und morgen "
        f"mehrdeutig. Erhalten: {morgen.confirmation_body!r}"
    )
    assert _kuerzel(heute.confirmation_body) == "W", (
        f"AC-6 Gegenprobe: der Verlauf fuer den laufenden Tag darf KEIN '+' "
        f"tragen, erhalten: {heute.confirmation_body!r}"
    )
