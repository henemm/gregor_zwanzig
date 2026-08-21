"""TDD RED — Issue #2020, Scheibe 2: jede Zeitangabe nennt ihre Groesse und
ihren Tagesbezug.

SPEC: docs/specs/modules/fix_2020_alarm_blickrichtung.md (AC-8 .. AC-14),
      Abschnitt "Teil 3 — Zeitangaben benennen ihre Groesse und ihren Tagesbezug"

GEMESSENER IST-STAND (2026-08-21, dieser Branch):

1. Die Zeile "Wo & wann" nennt eine NACKTE Uhrzeit (`_datablock_single`,
   render.py:721 -> "🏁 Ziel · 17:00"). Ob das der Zeitpunkt des staerksten
   Werts ist, ob er bevorsteht oder laengst vorbei ist, und an welchem Tag er
   liegt, steht nirgends.
2. `_onset_time_label()` (render.py:367-374) loest den Tagesversatz nur ueber
   den WAHRHEITSWERT auf (`f"morgen …" if e.onset_day_offset else …`) — jeder
   Versatz ungleich null wird "morgen", auch `-1`. Im Nowcast-Vorwaertsfenster
   unerreichbar, im Abweichungsalarm der Normalfall.
3. Weder `AlertEvent` noch `OnsetShiftEvent` fuehren einen Tagesversatz oder
   ein Vergangenheits-Kennzeichen, und `to_alert_message()` kennt keine
   Referenzzeit `now_utc`, aus der sich beides ableiten liesse.

PRUEFORT = WIRKORT. Tagesversatz und Vergangenheit entstehen laut Spec in der
PROJEKTION aus der Referenzzeit (`day_offset(now_utc, …)`), der Renderer setzt
nur die Worte. Deshalb faehrt jeder Test die echte Kette
`WeatherChangeDetectionService.detect_changes()` -> `to_alert_message()` ->
Kanal-Renderer, statt sich fertige Modell-Felder von Hand zu setzen: nur so
ist geprueft, dass der Versatz aus der REFERENZZEIT kommt und nicht aus der
Systemuhr (AC-13).

KEIN MOCK-THEATER (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`/
`MagicMock`, kein Dateiinhalt-Check als Verhaltensnachweis, kein Netz.
`freeze_time` friert ausschliesslich die SYSTEMUHR ein — genau die Groesse,
von der das Ergebnis laut AC-13 NICHT abhaengen darf.

ZEITZONE/KALENDER. Die Etappe haengt auf Island (`Atlantic/Reykjavik`,
ganzjaehrig UTC+0): Ortszeit == Weltzeit, die Uhrzeit-Literale stehen damit
unverfaelscht im Test. Der Ereignistag 2026-08-20 ist ein DONNERSTAG — das
Kuerzel "Do" fuer AC-10 wird ueber `_de_weekday_short()` aus dem Bestand
abgeleitet, nicht geraten.

Pfadregel #1409: der Prueling wird RELATIV ZU DIESER DATEI aufgeloest (ueber
`tests/conftest.py`, das `<repo>/src` an `sys.path` haengt), nie ueber den
festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.day_window import resolve_configured_window, window_end_utc_exclusive
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)
from output.renderers.alert.model import OnsetEvent, OnsetShiftEvent
from output.renderers.alert.official_alerts import _de_weekday_short, _tag_hour
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    _onset_time_label, render_email, render_sms, render_telegram,
)
from services.weather_change_detection import WeatherChangeDetectionService
from utils.timezone import local_fmt

ISLAND_LAT, ISLAND_LON = 64.13, -21.90
TZ = ZoneInfo("Atlantic/Reykjavik")
TAG = date(2026, 8, 20)          # Donnerstag (s. Modul-Docstring)
FENSTER = (4, 19)                # Default-Tagesfenster, ADR-0035

# Die Niederschlags-Reihe der Spec (AC-1): Spitze um 15:00.
REIHE_REGEN = {13: 8.0, 15: 10.0, 16: 3.0, 17: 1.0}
SUMME_REGEN = 22.0
ANGEKUENDIGT = 5.0


# --------------------------------------------------------------------------
# Fixture-Bausteine (dieselbe Bauart wie test_alert_restmenge_und_ende.py --
# Fenstergrenzen aus den produktiven Funktionen, nicht getippt)
# --------------------------------------------------------------------------

def _segment() -> TripSegment:
    start_h, end_h = resolve_configured_window(*FENSTER)
    beginn = (
        datetime.combine(TAG, time(start_h))
        .replace(tzinfo=TZ)
        .astimezone(timezone.utc)
    )
    ende = window_end_utc_exclusive(TAG, end_h, TZ)
    return TripSegment(
        segment_id="Ziel",
        start_point=GPXPoint(lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=800.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=ISLAND_LAT + 0.1, lon=ISLAND_LON + 0.1,
                           elevation_m=900.0, distance_from_start_km=9.0),
        start_time=beginn, end_time=ende,
        duration_hours=(ende - beginn).total_seconds() / 3600.0,
        distance_km=9.0, ascent_m=100.0, descent_m=100.0,
    )


def _punkte(*, regen: dict[int, float] | None = None, boeen_spitze: int | None = None):
    """24-Stunden-Reihe. `boeen_spitze` legt die Stunde der staerksten Boee."""
    regen = regen or {}
    return [
        ForecastDataPoint(
            ts=datetime(TAG.year, TAG.month, TAG.day, h, 0),
            t2m_c=12.0, wind10m_kmh=20.0,
            gust_kmh=70.0 if h == boeen_spitze else 25.0,
            precip_1h_mm=regen.get(h, 0.0),
        )
        for h in range(24)
    ]


def _data(punkte, **summary) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(temp_max_c=12.0, **summary),
        fetched_at=datetime(TAG.year, TAG.month, TAG.day, 6, 0,
                            tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _aenderungen(punkte, feld: str, *, alt: float, neu: float):
    """Der PRODUKTIVE Vergleichslauf (Alarm-Pfad, `include_absolute=False`)."""
    changes = WeatherChangeDetectionService().detect_changes(
        _data(punkte, **{feld: alt}), _data(punkte, **{feld: neu}),
        include_absolute=False,
    )
    treffer = [c for c in changes if c.metric == feld]
    assert treffer, (
        f"Der Detektor muss eine Aenderung an {feld} liefern; "
        f"bekam {[c.metric for c in changes]}"
    )
    return treffer, [_data(punkte, **{feld: neu})]


def _uhr(tag: date, stunde: int, minute: int = 0) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, minute,
                    tzinfo=timezone.utc)


def _nachricht(changes, segmente, *, now_utc: datetime):
    """Projektion MIT Referenzzeit.

    RED-Zustand: `to_alert_message()` kennt `now_utc` noch nicht. Der Aufruf
    faellt dann auf die Bestandsform zurueck, damit die Tests unten an der
    fehlenden AUSSAGE scheitern und nicht an der Signatur.
    """
    kwargs = dict(tz=TZ, stand_at=local_fmt(now_utc, TZ))
    # 🔴 RED-ONLY (#2020 Scheibe 2, Phase 5): Dieser Fallback MUSS mit dem
    # GREEN-Commit entfernt werden. Er existiert AUSSCHLIESSLICH, damit die
    # Wortlaut-ACs an inhaltlichen Assertions scheitern statt am fehlenden
    # Parameter `now_utc`. Bleibt er stehen, verdeckt er kuenftig das Fehlen
    # von `now_utc`, statt es rot zu machen — eine eingebaute Erosionsstelle.
    try:
        return to_alert_message(changes, segmente, "Test-Trip",
                                now_utc=now_utc, **kwargs)
    except TypeError as exc:  # pragma: no cover - faellt mit dem Fix weg
        if "now_utc" not in str(exc):
            raise
        return to_alert_message(changes, segmente, "Test-Trip", **kwargs)


def _texte(msg) -> dict[str, str]:
    html, plain = render_email(msg)
    return {"email_html": html, "email_plain": plain,
            "telegram": render_telegram(msg), "sms": render_sms(msg, 160)}


def _langform(texte) -> list[tuple[str, str]]:
    return [("email_plain", texte["email_plain"]), ("telegram", texte["telegram"])]


def _boeen_nachricht(*, spitze: int, now_utc: datetime):
    """Boeen-Aenderung (Nicht-Niederschlags-Metrik) mit Spitze zur Stunde
    `spitze` — der Fall, fuer den der Kopf "staerkste Stunde" gilt."""
    changes, segmente = _aenderungen(
        _punkte(boeen_spitze=spitze), "gust_max_kmh", alt=30.0, neu=70.0,
    )
    return _nachricht(changes, segmente, now_utc=now_utc)


def _regen_nachricht(*, now_utc: datetime):
    changes, segmente = _aenderungen(
        _punkte(regen=REIHE_REGEN), "precip_sum_mm",
        alt=ANGEKUENDIGT, neu=SUMME_REGEN,
    )
    return _nachricht(changes, segmente, now_utc=now_utc)


def _nur_bekannte_felder(cls, **felder):
    """Konstruiert ein Modell mit den Feldern, die es HEUTE schon kennt.

    Die neuen Felder dieser Spec (`to_is_past`, `to_day_offset`) fallen im
    RED-Zustand weg — der Test scheitert dadurch an der fehlenden AUSSAGE im
    gerenderten Text statt an der Konstruktion, und wird gruen, sobald die
    Felder existieren UND der Renderer sie ausspricht.
    """
    bekannt = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in felder.items() if k in bekannt})


def _onset_shift(*, to_is_past: bool) -> OnsetShiftEvent:
    return _nur_bekannte_felder(
        OnsetShiftEvent,
        metric_id="precipitation", from_time="19:00", to_time="15:00",
        shift_text="4 h früher", km_from=0.0, km_to=9.0, segment_id="Ziel",
        to_day_offset=0, to_is_past=to_is_past,
    )


def _onset_shift_nachricht(*, to_is_past: bool):
    from output.renderers.alert.model import AlertMessage
    return AlertMessage(
        trip_short="Test-Trip", stand_at="15:30", events=(),
        onset_shift_events=(_onset_shift(to_is_past=to_is_past),),
    )


# --------------------------------------------------------------------------
# AC-8: vergangener Beginn wird als vergangen ausgewiesen
# --------------------------------------------------------------------------

def test_bereits_verstrichener_beginn_wird_als_vergangen_ausgewiesen():
    """AC-8.

    GIVEN ein Abweichungsalarm, dessen Niederschlagsbeginn zum
          Versandzeitpunkt bereits verstrichen ist, aber am selben
          Kalendertag liegt (Beginn 15:00, Versand 15:30 Ortszeit)
    WHEN  die Alarm-Nachricht gerendert wird
    THEN  weist die Beginn-Zeile den Zeitpunkt als vergangen aus
          ("19:00 → seit 15:00 (4 h früher)") statt ihn als bevorstehend zu
          formulieren; die Gegenprobe mit kuenftigem Beginn traegt "seit" nicht.
    """
    vergangen = _texte(_onset_shift_nachricht(to_is_past=True))
    kuenftig = _texte(_onset_shift_nachricht(to_is_past=False))

    for kanal, text in _langform(vergangen):
        assert "19:00 → seit 15:00" in text, (
            f"{kanal}: Ein bereits verstrichener Beginn muss als vergangen "
            f"formuliert sein ('→ seit 15:00'); bekam:\n{text}"
        )
    for kanal, text in _langform(kuenftig):
        assert "seit" not in text, (
            f"{kanal}: Ein noch bevorstehender Beginn darf NICHT als vergangen "
            f"formuliert sein; bekam:\n{text}"
        )


# --------------------------------------------------------------------------
# AC-9: Tagesbezug in der Langform
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "versandtag, erwartet, verboten",
    [
        (TAG + timedelta(days=1), "gestern 17:00", "morgen"),
        (TAG + timedelta(days=2), "vor 2 Tagen 17:00", "morgen"),
        (TAG - timedelta(days=1), "morgen 17:00", "gestern"),
    ],
    ids=["versatz_minus_1", "versatz_minus_2", "versatz_plus_1"],
)
def test_zeitangabe_nennt_den_tag_beim_namen(versandtag, erwartet, verboten):
    """AC-9.

    GIVEN ein Abweichungsalarm, dessen Zeitpunkt (17:00 Ortszeit am
          2026-08-20) auf einem anderen Kalendertag liegt als der Versandtag
    WHEN  die Nachricht in E-Mail oder Telegram gerendert wird
    THEN  nennt die Zeitangabe den Tag in der Hausnotation aus
          `format_reference_at`: -1 -> "gestern 17:00", -2 -> "vor 2 Tagen
          17:00", +1 -> "morgen 17:00". Der -1- und -2-Fall duerfen unter
          KEINEN Umstaenden "morgen" ergeben (Regression zur Wahrheitswert-
          Pruefung in render.py:374).
    """
    texte = _texte(_boeen_nachricht(spitze=17, now_utc=_uhr(versandtag, 9)))

    for kanal, text in _langform(texte):
        assert erwartet in text, (
            f"{kanal}: Versandtag {versandtag} -> erwartet {erwartet!r}; "
            f"bekam:\n{text}"
        )
        assert verboten not in text, (
            f"{kanal}: {verboten!r} ist hier falsch — der Tagesversatz muss "
            f"EXAKT aufgeloest werden, nicht ueber seinen Wahrheitswert; "
            f"bekam:\n{text}"
        )


def test_nowcast_tageswort_loest_den_exakten_versatz_auf():
    """AC-9 (Gegenprobe im Nowcast-Pfad).

    GIVEN denselben gemeinsamen Tageswort-Baustein, auf den
          `_onset_time_label()` laut Spec umgestellt wird
    WHEN  er mit Versatz -1 bzw. +1 aufgerufen wird
    THEN  ergibt -1 "gestern 15:00" und NICHT "morgen 15:00"; +1 bleibt
          "morgen 15:00" (Bestandsverhalten, Regressions-Invariante).
    """
    def _onset(offset: int) -> OnsetEvent:
        return _nur_bekannte_felder(
            OnsetEvent, onset_minutes=30, onset_time="15:00", km_from=0.0,
            km_to=9.0, is_convective=False, intensity_label="mäßig",
            source_label="Radar (DWD)", onset_day_offset=offset,
        )

    gestern = _onset_time_label(_onset(-1))
    morgen = _onset_time_label(_onset(1))

    assert gestern == "gestern 15:00", (
        f"Versatz -1 muss 'gestern 15:00' ergeben; bekam {gestern!r} — die "
        f"Wahrheitswert-Pruefung macht daraus faelschlich 'morgen'"
    )
    assert morgen == "morgen 15:00", (
        f"Versatz +1 bleibt 'morgen 15:00'; bekam {morgen!r}"
    )


# --------------------------------------------------------------------------
# AC-10: Tagesbezug in der Kurzform
# --------------------------------------------------------------------------

def test_kurzform_klebt_das_wochentagskuerzel_vor_die_stunde():
    """AC-10.

    GIVEN denselben Fall wie AC-9 (Ereigniszeit 15:00 am Donnerstag
          2026-08-20, Versand am Folgetag), gerendert in SMS/Premium-SMS
    WHEN  die Kurznachricht gebaut wird
    THEN  klebt das Wochentagskuerzel vor die Stunde des Tokens ("@Do15") —
          kein Kanal faellt auf ein Zahlensuffix ("@15-1"/"@15+-1") zurueck.
    """
    kuerzel = _de_weekday_short(datetime(TAG.year, TAG.month, TAG.day, 15, 0))
    assert kuerzel == "Do", (
        f"Fixture-Selbstkontrolle: {TAG} muss ein Donnerstag sein, "
        f"bekam {kuerzel!r}"
    )

    sms = render_sms(_regen_nachricht(now_utc=_uhr(TAG + timedelta(days=1), 9)), 160)

    assert f"@{kuerzel}15" in sms, (
        f"Erwartet das Wochentagskuerzel direkt vor der Stunde ('@{kuerzel}15'); "
        f"bekam {sms!r}"
    )
    for zahlensuffix in ("@15-1", "@15+-1", "15:00-1"):
        assert zahlensuffix not in sms, (
            f"Zahlensuffix {zahlensuffix!r} ist verworfen ('-' ist in der "
            f"Kurzform dreifach belegt); bekam {sms!r}"
        )
    assert len(sms) <= 160, f"160-Zeichen-Grenze gerissen: {sms!r}"


# --------------------------------------------------------------------------
# AC-11/AC-12: jede Zeitangabe benennt ihre Groesse
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "versandstunde, erwartet",
    [(12, "stärkste Stunde 17:00"), (18, "stärkste Stunde war 17:00")],
    ids=["zeitpunkt_steht_bevor", "zeitpunkt_ist_vorbei"],
)
def test_boeen_zeitangabe_nennt_die_staerkste_stunde(versandstunde, erwartet):
    """AC-11.

    GIVEN eine Wertaenderung EINER Nicht-Niederschlags-Metrik (Windboee) mit
          Spitzenwert um 17:00 Ortszeit
    WHEN  die Nachricht vor bzw. nach diesem Zeitpunkt gerendert wird
    THEN  benennt die Zeile "Wo & wann" die Uhrzeit ausdruecklich als
          Zeitpunkt des staerksten Werts ("stärkste Stunde 17:00" bzw.
          "stärkste Stunde war 17:00") — fuer diese Metrikart bleibt die
          Kopfform bestehen, eine "Restmenge" ergibt fuer Wind keinen Sinn.
    """
    texte = _texte(_boeen_nachricht(spitze=17, now_utc=_uhr(TAG, versandstunde)))

    for kanal, text in _langform(texte):
        assert erwartet in text, (
            f"{kanal}: erwartet {erwartet!r}; bekam:\n{text}"
        )
        assert "Ab jetzt: noch" not in text, (
            f"{kanal}: Eine Restmengen-Aussage ergibt fuer Boeen keinen Sinn; "
            f"bekam:\n{text}"
        )


def test_reine_beginn_zeile_traegt_kein_staerkste_stunde():
    """AC-11 (Gegenprobe).

    GIVEN eine reine Beginn-Verschiebung ohne Wertaenderung
    WHEN  die Nachricht gerendert wird
    THEN  kommt sie weiterhin OHNE das Wort "stärkste Stunde" aus — der
          Beginn ist keine Spitze.
    """
    texte = _texte(_onset_shift_nachricht(to_is_past=True))

    for kanal, text in _langform(texte):
        assert "stärkste Stunde" not in text, (
            f"{kanal}: Eine Beginn-Zeile darf das Spitzen-Wort nicht tragen; "
            f"bekam:\n{text}"
        )
        assert "-Beginn:" in text, (
            f"{kanal}: Die Beginn-Zeile muss ihre Groesse weiterhin als "
            f"Beginn benennen; bekam:\n{text}"
        )


def test_wertaenderung_und_beginn_verschiebung_bleiben_unterscheidbar():
    """AC-12.

    GIVEN ein Abweichungsalarm, der GLEICHZEITIG eine Wertaenderung (Boeen-
          Spitze 17:00) und eine Beginn-Verschiebung (auf 15:00) traegt —
          der Fall aus #2020, bisher von keinem Test abgedeckt
    WHEN  die Nachricht gerendert wird
    THEN  stehen beide Zeitangaben mit unterscheidbarer Bedeutung in
          derselben Nachricht: die eine als "stärkste Stunde", die andere als
          "-Beginn" — eine Spitzen-Aussage neben einem Beginn um 15:00 ist
          damit nicht als Widerspruch lesbar.
    """
    msg = _boeen_nachricht(spitze=17, now_utc=_uhr(TAG, 12))
    msg = dataclasses.replace(
        msg, onset_shift_events=(_onset_shift(to_is_past=False),),
    )
    texte = _texte(msg)

    for kanal, text in _langform(texte):
        assert "stärkste Stunde 17:00" in text, (
            f"{kanal}: Die Wertaenderung muss ihre Groesse benennen; bekam:\n{text}"
        )
        assert "-Beginn: 19:00 → 15:00" in text, (
            f"{kanal}: Die Beginn-Verschiebung muss daneben stehen und ihre "
            f"eigene Groesse benennen; bekam:\n{text}"
        )


# --------------------------------------------------------------------------
# AC-13: Referenzzeit entscheidet, nicht die Systemuhr
# --------------------------------------------------------------------------

def test_ergebnis_haengt_an_der_referenzzeit_nicht_an_der_systemuhr():
    """AC-13.

    GIVEN identische Wetterdaten
    WHEN  dieselbe Nachricht (a) unter ZWEI verschiedenen eingefrorenen
          Systemzeiten mit derselben expliziten Referenzzeit und (b) mit ZWEI
          verschiedenen Referenzzeiten gerendert wird
    THEN  ist (a) byte-identisch — die Systemuhr entscheidet nirgends mit —
          und (b) unterschiedlich in Tagesbezug UND Restmenge.
    """
    # BEIDE Laeufe bekommen dieselbe Referenzzeit — damit ist auch `stand_at`
    # identisch (es wird in `_nachricht()` aus genau dieser Referenzzeit
    # abgeleitet, nicht aus der Systemuhr). Der Gesamttext-Vergleich unten ist
    # deshalb erfuellbar und misst allein die Unabhaengigkeit von der Systemuhr.
    with freeze_time("2026-09-01 03:00:00"):
        frueh = _texte(_regen_nachricht(now_utc=_uhr(TAG, 14, 30)))
    with freeze_time("2027-01-15 22:00:00"):
        spaet = _texte(_regen_nachricht(now_utc=_uhr(TAG, 14, 30)))

    for kanal in ("email_plain", "telegram", "sms"):
        assert frueh[kanal] == spaet[kanal], (
            f"{kanal}: Bei identischer Referenzzeit darf die Systemuhr das "
            f"Ergebnis nicht veraendern.\n{frueh[kanal]!r}\n{spaet[kanal]!r}"
        )

    heute = _texte(_regen_nachricht(now_utc=_uhr(TAG, 14, 30)))
    morgen = _texte(_regen_nachricht(now_utc=_uhr(TAG + timedelta(days=1), 9)))

    for kanal, text in _langform(heute):
        assert "Ab jetzt: noch ~14 mm" in text, (
            f"{kanal}: Referenzzeit 14:30 am Ereignistag -> 14 mm Restmenge; "
            f"bekam:\n{text}"
        )
        assert "gestern" not in text, (
            f"{kanal}: Am Ereignistag gibt es keinen Tagesbezug; bekam:\n{text}"
        )
    for kanal, text in _langform(morgen):
        assert "gestern" in text, (
            f"{kanal}: Referenzzeit am Folgetag -> Tagesbezug 'gestern'; "
            f"bekam:\n{text}"
        )
        assert "noch ~14 mm" not in text, (
            f"{kanal}: Am Folgetag ist von der Restmenge nichts mehr uebrig; "
            f"bekam:\n{text}"
        )


# --------------------------------------------------------------------------
# AC-14: Waechter gegen Formkollision in der Kurzform
# --------------------------------------------------------------------------

def test_tagesbezug_und_fensterform_der_amtlichen_warnung_bleiben_unterscheidbar():
    """AC-14.

    GIVEN zwei Kurzform-Ausschnitte, die im selben Kanal nebeneinander
          vorkommen koennen: die Tagesbezug-Form dieses Alarms ("@Do15") und
          die Fensterform der amtlichen Warnung ("Do12-22" bzw. "15:20-17"
          aus `_tag_hour`)
    WHEN  ein Waechter beide aus dem ECHTEN Renderer-Code zieht und
          gegenueberstellt
    THEN  sind sie strukturell unterscheidbar — und eine spaetere Aenderung
          der Fensterform (z.B. Umstellung auf HH:MM-HH:MM) macht diesen Test
          sofort rot, bevor die Verwechselbarkeit erneut in Produktion landet.
    """
    tag = datetime(TAG.year, TAG.month, TAG.day, 12, 0)
    # Bestandsform der amtlichen Warnung, aus dem echten Code gezogen.
    fenster_voll = f"{_de_weekday_short(tag)}{_tag_hour(tag)}-{_tag_hour(tag.replace(hour=22))}"
    fenster_minuten = (
        f"{_tag_hour(tag.replace(hour=15, minute=20))}-{_tag_hour(tag.replace(hour=17))}"
    )
    assert (fenster_voll, fenster_minuten) == ("Do12-22", "15:20-17"), (
        "Die Fensterform der amtlichen Warnung hat sich geaendert. Damit ist "
        "die Kollisionsanalyse dieser Spec (verworfenes Zahlensuffix '17:00-1') "
        "neu zu fuehren, BEVOR die Kurzform angepasst wird. "
        f"Bekam {fenster_voll!r} / {fenster_minuten!r}"
    )

    sms = render_sms(_regen_nachricht(now_utc=_uhr(TAG + timedelta(days=1), 9)), 160)
    tagesbezug = [t for t in sms.split() if "@" in t]
    assert tagesbezug, f"Kein Zeit-Token in der Kurznachricht: {sms!r}"

    for token in tagesbezug:
        stunde = token.split("@", 1)[1]
        assert stunde.startswith("Do"), (
            f"Der Tagesbezug klebt als Wochentagskuerzel vor die Stunde; "
            f"bekam {token!r} in {sms!r}"
        )
        assert "-" not in stunde, (
            f"Der Tagesbezug darf keine Bindestrich-Form tragen — sie waere "
            f"von der Fensterform {fenster_minuten!r} nicht mehr zu "
            f"unterscheiden; bekam {token!r}"
        )
        assert stunde not in (fenster_voll, fenster_minuten), (
            f"Tagesbezug {stunde!r} und Fensterform sind formgleich geworden"
        )
