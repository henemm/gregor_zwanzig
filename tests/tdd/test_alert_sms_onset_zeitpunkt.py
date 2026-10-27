"""TDD RED — Issue #1948 Scheibe S4: die Nowcast-/Onset-Kurznachricht nennt
einen ZEITPUNKT (`TH@15:40`) statt eines Countdowns (`TH!8`) und spricht im
Kopf dieselbe Ortssprache wie Betreff/E-Mail (`format_alert_location`:
Ortsname -> Segment -> km-Rueckfall) statt der selbstgebauten `km8-8`-Notation.

SPEC: docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md (AC-1 bis AC-11)

Betrifft AUSSCHLIESSLICH `_render_sms_onset` (der Onset-Zweig von
`render_sms`, `render.py:422`) und die Marker-Konstante `COMPARE_RADAR_SOURCE`
in `project.py`. E-Mail-, Telegram- und Betreff-Rendering des Onset-Zweigs
bleiben unveraendert (AC-10) — bis auf die kanalabhaengige fuehrende Null,
die AUSSCHLIESSLICH die Kurznachricht kuerzt (AC-11).

Kein Mock, keine Dateiinhalt-Asserts: echte `OnsetEvent`/`AlertMessage`-
Objekte bzw. der echte Konstruktor `to_multi_location_onset_alert_message`
durch die echten Renderer. Alle `onset_time`-Werte sind FEST gesetzt, wo der
Aufbau es zulaesst; wo der Konstruktor die Zeit selbst aus `datetime.now()`
ableitet (Compare-Buendel), wird auf Struktur statt auf einen Goldstring
geprueft (Wanduhr-Ratsche #1940).
"""
from __future__ import annotations

import ast
import inspect
import re
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)

# Zeitpunkt-Token: 1-2 Buchstaben-Kuerzel + '@' + H:MM oder HH:MM.
_ZEITPUNKT_TOKEN_RE = re.compile(r"\b(TH|R)@(\d{1,2}):(\d{2})\b")
# Countdown-Token des Alt-Formats (`TH!8` / `R!25`) — darf nirgends mehr stehen.
_COUNTDOWN_TOKEN_RE = re.compile(r"\b(TH|R)!\d+")
# FORTGESCHRIEBEN (Issue #2046, AC-1/AC-5/AC-11): dieselbe Zusicherung, aber
# mit optionalem Mengen-Zwischenteil. Nur der ECHTE Einspeiseweg unten leitet
# eine Menge aus den Frames ab und nennt sie im Token (`R0.6@17:32`); alle
# Goldstring-Faelle dieser Datei setzen `onset_precip_mm` nicht und bleiben
# unveraendert zahlenlos — genau die Regressions-Invariante aus AC-11.
_ZEITPUNKT_TOKEN_MIT_MENGE_RE = re.compile(r"\b(TH|R)(?:\d+\.\d)?@(\d{1,2}):(\d{2})\b")


def _onset_event(**kw) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern (keine Wanduhr)."""
    fields = dict(
        onset_minutes=8, onset_time="15:40", km_from=8.0, km_to=8.0,
        is_convective=True, intensity_label="Gewitter mit Hagel",
        source_label="Radar (ICON-D2)",
    )
    fields.update(kw)
    return OnsetEvent(**fields)


def _onset_msg(event: OnsetEvent, *, trip_short: str = "KHW 403",
               source: str = "radar") -> AlertMessage:
    """`source is not None` routet `render_sms` in den Onset-Zweig."""
    return AlertMessage(
        trip_short=trip_short, stand_at="10:00", events=(event,), source=source,
    )


def _kopf(sms: str) -> str:
    """Der Kopf-Anteil vor dem ': ' — die Ortsangabe der Kurznachricht."""
    assert ": " in sms, f"Kurznachricht hat keinen '<Ort>: <Token>'-Aufbau: {sms!r}"
    return sms.split(": ", 1)[0]


def _nowcast(minutes: int = 30, *, convective: bool = False):
    from services.radar_service import NowcastResult
    return NowcastResult(
        onset_minutes=minutes, intensity_label="leichter Regen",
        source="radar", is_convective=convective,
    )


# ---------------------------------------------------------------------------
# AC-1 — konvektives Ereignis: Zeitpunkt-Token statt Countdown
# ---------------------------------------------------------------------------


def test_ac1_konvektiver_onset_traegt_zeitpunkt_token_statt_countdown():
    """AC-1: Given ein Trip-Onset-Alarm mit konvektivem Ereignis
    (`onset_time="15:40"`, ohne `location_label`, ohne Segment) / When
    `render_sms` ueber den Onset-Zweig rendert / Then steht `TH@15:40` im
    Text und nirgends mehr ein `TH!`-Countdown."""
    sms = render_sms(_onset_msg(_onset_event()))

    assert "TH@15:40" in sms, f"Zeitpunkt-Token 'TH@15:40' fehlt: {sms!r}"
    assert "TH!" not in sms, f"Alt-Countdown 'TH!' steht noch im Text: {sms!r}"
    assert not _COUNTDOWN_TOKEN_RE.search(sms), (
        f"Kurznachricht traegt noch eine Countdown-Minutenzahl: {sms!r}"
    )
    assert sms == "km 8-8: TH@15:40", (
        f"Erwartet 'km 8-8: TH@15:40' (km-Rueckfall + Zeitpunkt), "
        f"bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Regen-Anmarsch: gespiegelt zu AC-1
# ---------------------------------------------------------------------------


def test_ac2_regen_onset_traegt_zeitpunkt_token_statt_countdown():
    """AC-2: Given denselben Aufbau wie AC-1, aber `is_convective=False` und
    `onset_time="14:35"` / When `render_sms` erneut rendert / Then steht
    `R@14:35` im Text und nirgends mehr ein `R!`-Countdown."""
    event = _onset_event(
        is_convective=False, onset_time="14:35", onset_minutes=25,
        intensity_label="Maessiger Regen",
    )
    sms = render_sms(_onset_msg(event))

    assert "R@14:35" in sms, f"Zeitpunkt-Token 'R@14:35' fehlt: {sms!r}"
    assert "R!" not in sms, f"Alt-Countdown 'R!' steht noch im Text: {sms!r}"
    assert not _COUNTDOWN_TOKEN_RE.search(sms), (
        f"Kurznachricht traegt noch eine Countdown-Minutenzahl: {sms!r}"
    )
    assert sms == "km 8-8: R@14:35", (
        f"Erwartet 'km 8-8: R@14:35', bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Segment-Sprache im Kopf
# ---------------------------------------------------------------------------


def test_ac3_segment_kennung_erscheint_als_kopf_der_kurznachricht():
    """AC-3: Given ein Trip-Onset-Alarm mit `segment_id="Ziel"` / When die
    SMS gerendert wird / Then lautet der Kopf exakt `Ziel: TH@15:40` —
    dieselbe Segment-Sprache, die `format_alert_location` Stufe 2 auch dem
    Betreff liefert.

    ABWEICHUNG VON DER SPEC (Testweg, nicht Zusicherung): Die Spec nennt als
    Test den Endpunkt-Weg `POST /api/trips/{trip_id}/alert-preview` mit
    `nowcast_frames`. Dieser Weg kann den Fall STRUKTURELL nicht herstellen:
    weder `NowcastFramesPayload` (`api/routers/validator.py:259-264`) noch die
    `OnsetEvent`-Konstruktion im Preview (`validator_render_service.py:110-118`)
    kennen ein `segment_id`-Feld, und `onset_time` leitet der Replay aus
    `datetime.now()` ab — ein exakter Goldstring `Ziel: TH@15:40` ist dort
    also weder erzeugbar noch wanduhrfest. Die Zusicherung wird deshalb hier
    als Unit-Test gefuehrt; den Endpunkt-Weg deckt der Test darunter
    (Token-Form + km-Kopf ueber den echten Einspeiseweg) ab.
    """
    sms = render_sms(_onset_msg(_onset_event(segment_id="Ziel")))

    assert sms == "Ziel: TH@15:40", (
        f"Erwartet den Segment-Kopf 'Ziel: TH@15:40', bekam {sms!r}"
    )


@pytest.mark.real_data_root
def test_ac3_endpunkt_replay_liefert_zeitpunkt_token_ueber_den_echten_einspeiseweg():
    """AC-3 (Endpunkt-Anteil): Given ein Frame-Mitschnitt mit Regen-Onset am
    S2-Einspeiseweg / When `POST /api/trips/{id}/alert-preview` gerendert
    wird / Then traegt das `sms`-Feld ein `R@HH:MM`-Zeitpunkt-Token und den
    km-Rueckfall-Kopf in `format_alert_location`-Schreibweise — kein
    `R!<Minuten>`-Countdown, keine `km2-6`-Notation.

    Wanduhrfest: der Replay leitet `onset_time` aus `datetime.now()` ab,
    deshalb Struktur- statt Goldstring-Pruefung (Muster
    `test_alert_preview_nowcast_replay.py`).
    """
    import json
    import shutil

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import validator

    user_id = f"test_1948s4_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-s4"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "S4 Trip", "stages": [],
    }))
    try:
        app = FastAPI()
        app.include_router(validator.router)
        client = TestClient(app)
        now = datetime.now(timezone.utc)
        body = {"nowcast_frames": {
            "source": "radar",
            "frames": [
                {"timestamp": (now + timedelta(minutes=5)).isoformat(),
                 "precip_mm_h": 0.0, "is_convective": False},
                {"timestamp": (now + timedelta(minutes=20)).isoformat(),
                 "precip_mm_h": 2.5, "is_convective": False},
            ],
            "km_from": 2.0, "km_to": 6.0,
        }}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        sms = resp.json()["sms"]
    finally:
        shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)

    match = _ZEITPUNKT_TOKEN_MIT_MENGE_RE.search(sms)
    assert match, f"Endpunkt-SMS traegt kein '<Kuerzel>@HH:MM'-Token: {sms!r}"
    assert match.group(1) == "R", (
        f"Nicht-konvektiver Frame muss ein 'R@'-Token liefern: {sms!r}"
    )
    assert not _COUNTDOWN_TOKEN_RE.search(sms), (
        f"Endpunkt-SMS traegt noch das Countdown-Format: {sms!r}"
    )
    assert _kopf(sms) == "km 2-6", (
        f"Endpunkt-SMS muss den km-Rueckfall in "
        f"format_alert_location-Schreibweise fuehren, bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — km-Rueckfall ohne Segment-Kennung
# ---------------------------------------------------------------------------


def test_ac4_ohne_segment_kennung_bleibt_der_km_rueckfall():
    """AC-4: Given ein Onset-Ereignis ohne Segment-Kennung (Altdaten-Fall,
    km 5-18) / When die SMS gerendert wird / Then nennt der Kopf die km-Spanne
    in `format_alert_location`-Schreibweise (`km 5–18`, nach ASCII-Faltung
    `km 5-18`) — keine Segment-Sprache."""
    event = _onset_event(segment_id=None, km_from=5.0, km_to=18.0)
    sms = render_sms(_onset_msg(event))

    assert _kopf(sms) == "km 5-18", (
        f"Kopf muss der km-Rueckfall 'km 5-18' sein, bekam {sms!r}"
    )
    assert sms == "km 5-18: TH@15:40", (
        f"Erwartet 'km 5-18: TH@15:40', bekam {sms!r}"
    )
    assert "Segment" not in sms, f"Segment-Sprache im km-Fall: {sms!r}"


# ---------------------------------------------------------------------------
# AC-5 — Ortsvergleich-Buendel (>1 Ort): Ortsname als Kopf
# ---------------------------------------------------------------------------


def test_ac5_compare_buendel_kopf_nennt_nur_den_ortsnamen():
    """AC-5: Given ein Ortsvergleich-Buendel-Onset mit ZWEI Orten (das
    fuehrende Event traegt `location_label="Zermatt"`) / When die SMS
    gerendert wird / Then beginnt der Kopf mit `Zermatt: `, ohne `+N`-Suffix
    und ohne `km0-0`-Spanne.

    Wanduhrfest: `to_multi_location_onset_alert_message` leitet `onset_time`
    aus `datetime.now()` ab -> Strukturpruefung des Tokens, exakter Vergleich
    nur am Kopf."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    msg = to_multi_location_onset_alert_message(
        [("Zermatt", _nowcast()), ("Chamonix", _nowcast())],
        tz=timezone.utc, stand_at="10:00",
    )
    sms = render_sms(msg)

    assert sms.startswith("Zermatt: "), (
        f"Buendel-Kopf muss der Ortsname des fuehrenden Events sein, "
        f"bekam {sms!r}"
    )
    assert "+" not in sms, f"Kurznachricht traegt einen '+N'-Zaehler: {sms!r}"
    assert "km0" not in sms and "km 0" not in sms, (
        f"Kurznachricht traegt noch die sinnlose km0-Spanne: {sms!r}"
    )
    assert _ZEITPUNKT_TOKEN_RE.search(sms), (
        f"Buendel-SMS traegt kein '<Kuerzel>@HH:MM'-Token: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Ortsvergleich mit GENAU einem Ort: Name aus `trip_short`
# ---------------------------------------------------------------------------


def test_ac6_ein_ort_compare_nennt_den_ortsnamen_aus_trip_short():
    """AC-6: Given ein Ortsvergleich-Onset mit GENAU einem Ort (Invariante:
    `location_label is None`, Ortsname nur in `msg.trip_short`) / When die SMS
    gerendert wird / Then nennt der Kopf den Ortsnamen statt der bisherigen
    `km0-0`-Spanne."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    msg = to_multi_location_onset_alert_message(
        [("Zermatt", _nowcast())], tz=timezone.utc, stand_at="10:00",
    )

    # Invariante des Konstruktors — Grundlage der Fallunterscheidung.
    assert msg.events[0].location_label is None, (
        "Bei genau einem Ort muss `location_label` None bleiben"
    )
    assert msg.trip_short == "Zermatt"

    sms = render_sms(msg)

    assert _kopf(sms) == "Zermatt", (
        f"Ein-Ort-Compare muss den Ortsnamen aus trip_short zeigen, "
        f"bekam {sms!r}"
    )
    assert "km0" not in sms and "km 0" not in sms, (
        f"Ein-Ort-Compare zeigt noch die km0-0-Spanne: {sms!r}"
    )
    assert _ZEITPUNKT_TOKEN_RE.search(sms), (
        f"Ein-Ort-Compare-SMS traegt kein '<Kuerzel>@HH:MM'-Token: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Waechter: die Weiche haengt an der Konstante
# ---------------------------------------------------------------------------


def test_ac7_abweichender_source_wert_faellt_auf_die_km_spanne_zurueck():
    """AC-7 (Waechter): Given dieselbe Nachricht wie AC-6, aber mit einem
    `source`-Wert, der NICHT der Compare-Radar-Konstante entspricht / When die
    SMS gerendert wird / Then faellt der Kopf auf `km 0-0` zurueck statt den
    Ortsnamen zu zeigen.

    Beweist, dass die Fallunterscheidung an der benannten Konstante haengt und
    nicht an einer zufaelligen String-Uebereinstimmung: driften Setz- und
    Lesestelle auseinander, schlaegt entweder dieser Test oder AC-6 rot.

    Lazy import: `COMPARE_RADAR_SOURCE` existiert vor der Implementierung noch
    nicht — der Import steht deshalb IN der Funktion, damit nur DIESER Test
    daran scheitert und nicht die ganze Datei am Sammeln.
    """
    from output.renderers.alert.project import (
        COMPARE_RADAR_SOURCE, to_multi_location_onset_alert_message,
    )

    msg = to_multi_location_onset_alert_message(
        [("Zermatt", _nowcast())], tz=timezone.utc, stand_at="10:00",
    )
    # Setzstelle liest dieselbe Konstante wie die Lesestelle im Renderer.
    assert msg.source == COMPARE_RADAR_SOURCE, (
        f"Der Compare-Onset-Konstruktor muss COMPARE_RADAR_SOURCE setzen, "
        f"setzte {msg.source!r}"
    )

    fremd = replace(msg, source=COMPARE_RADAR_SOURCE + "-abweichend")
    sms = render_sms(fremd)

    assert _kopf(sms) == "km 0-0", (
        f"Ohne die Compare-Radar-Konstante muss der Kopf auf die km-Spanne "
        f"zurueckfallen, bekam {sms!r}"
    )
    assert "Zermatt" not in sms, (
        f"Ortsname darf ohne die Konstante nicht erscheinen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — GSM-7-Reinheit: Piktogramm entfernt, Wort bleibt
# ---------------------------------------------------------------------------


def test_ac8_ziel_segment_bleibt_ohne_piktogramm_und_gsm7_rein():
    """AC-8: Given ein Onset-Alarm mit Segment-Kennung "Ziel"
    (`format_alert_location` liefert `🏁 Ziel`) / When die SMS gerendert wird /
    Then steht dort das Wort "Ziel", aber weder `🏁` noch dessen
    Transliteration `:checkered_flag:` — die Ausgabe ist ASCII-rein."""
    sms = render_sms(_onset_msg(_onset_event(segment_id="Ziel")))

    assert "Ziel" in sms, (
        f"Das Segment-Wort 'Ziel' muss stehenbleiben: {sms!r}"
    )
    assert "\U0001F3C1" not in sms, f"Piktogramm 🏁 steht in der SMS: {sms!r}"
    assert ":checkered_flag:" not in sms, (
        f"Piktogramm wurde transliteriert statt entfernt: {sms!r}"
    )
    assert sms.isascii(), f"Kurznachricht ist nicht ASCII-rein: {sms!r}"
    assert len(sms) <= 140, f"Kurznachricht ist {len(sms)} Zeichen lang: {sms!r}"


# ---------------------------------------------------------------------------
# AC-9 — Vergleich: nur der Ortsvergleich traegt einen Ortsnamen
# ---------------------------------------------------------------------------


def test_ac9_nur_das_compare_ergebnis_traegt_den_ortsnamen():
    """AC-9: Given zwei strukturell identische Onset-Nachrichten — eine
    Trip-Radar-Nachricht (kein Ortsname) und eine Ortsvergleich-Buendel-
    Nachricht (Ortsname gesetzt) / When beide gerendert werden / Then traegt
    NUR das Compare-Ergebnis den Ortsnamen im Kopf; das Trip-Ergebnis nennt
    die aufgeloeste Ortsangabe ohne Namenspraefix.

    Die Zusicherung ist der VERGLEICH beider Ergebnisse."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    trip_sms = render_sms(_onset_msg(
        _onset_event(is_convective=False, onset_time="14:35", km_from=0.0,
                     km_to=0.0, intensity_label="leichter Regen"),
    ))
    compare_sms = render_sms(to_multi_location_onset_alert_message(
        [("Zermatt", _nowcast()), ("Chamonix", _nowcast())],
        tz=timezone.utc, stand_at="10:00",
    ))

    trip_kopf, compare_kopf = _kopf(trip_sms), _kopf(compare_sms)

    assert compare_kopf == "Zermatt", (
        f"Compare-Kopf muss der Ortsname sein, bekam {compare_sms!r}"
    )
    assert trip_kopf == "km 0-0", (
        f"Trip-Kopf muss die aufgeloeste Ortsangabe ohne Namen sein, "
        f"bekam {trip_sms!r}"
    )
    assert trip_kopf != compare_kopf, (
        f"Trip- und Compare-Kopf duerfen nicht zusammenfallen: "
        f"{trip_sms!r} / {compare_sms!r}"
    )
    assert "Zermatt" not in trip_sms, (
        f"Trip-SMS darf keinen Ortsnamen tragen: {trip_sms!r}"
    )
    # Beide sprechen dieselbe Token-Sprache — nur der Kopf unterscheidet sie.
    for sms in (trip_sms, compare_sms):
        assert _ZEITPUNKT_TOKEN_RE.search(sms), (
            f"Beide Nachrichten muessen ein Zeitpunkt-Token tragen: {sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-10 — E-Mail/Telegram/Betreff bleiben unberuehrt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("segment_id, ort", [(None, "km 8–8"), ("Ziel", "🏁 Ziel")])
def test_ac10_email_telegram_betreff_bleiben_am_countdown_format(segment_id, ort):
    """AC-10: Given dieselben Eingaben wie AC-1/AC-3 / When zusaetzlich
    Betreff, E-Mail und Telegram gerendert werden / Then bleiben deren
    Ausgaben unveraendert: `_km_str_onset`-Sprache (`km 8–8` mit Gedankenstrich
    bzw. `🏁 Ziel` mit Piktogramm) und Countdown-Formulierung "in 8 Min".

    Nicht-Beruehrungs-Nachweis: dieser Test ist vor UND nach S4 gruen."""
    msg = _onset_msg(_onset_event(segment_id=segment_id))

    subject = render_subject(msg)
    telegram = render_telegram(msg)
    _html, plain = render_email(msg)

    assert subject == f"[KHW 403] {ort} · Gewitter in 8 Min", (
        f"Betreff hat sich veraendert: {subject!r}"
    )
    assert telegram == (
        f"<b>KHW 403 · {ort} · Gewitter in 8 Min</b>\n"
        f"15:40 · Gewitter mit Hagel · Radar (ICON-D2)"
    ), f"Telegram hat sich veraendert: {telegram!r}"
    assert "Gewitter in 8 Min" in plain, (
        f"E-Mail hat die Countdown-Ueberschrift verloren: {plain!r}"
    )
    assert f"Wo & wann: {ort} · ab 15:40" in plain, (
        f"E-Mail hat die 'Wo & wann'-Zeile veraendert: {plain!r}"
    )
    assert "TH@" not in plain and "TH@" not in telegram and "TH@" not in subject, (
        "Das SMS-Zeitpunkt-Token darf in keinen anderen Kanal auslaufen"
    )


def test_ac10_render_modul_importiert_day_window_nicht():
    """AC-10 (struktureller Nicht-Beruehrungs-Nachweis, kein
    Verhaltensnachweis): `render.py` importiert `app.day_window` /
    `display_end_time()` nicht — die #1599-Leitplanke bleibt ausserhalb der
    Onset-Aufrufkette.

    Der Prueflings-Quelltext wird ueber das IMPORTIERTE Modul aufgeloest
    (`inspect.getsource`), nie ueber einen festen Repo-Pfad — sonst pruefte
    der Test aus einem Worktree heraus die falsche Datei."""
    from output.renderers.alert import render as render_module

    # Nachweis, dass der Prueling aus DIESEM Arbeitsbaum stammt.
    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )

    baum = ast.parse(inspect.getsource(render_module))
    module_namen: set[str] = set()
    for node in ast.walk(baum):
        if isinstance(node, ast.Import):
            module_namen.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_namen.add(node.module)

    verletzungen = {m for m in module_namen if m.endswith("day_window")}
    assert not verletzungen, (
        f"render.py importiert day_window: {sorted(verletzungen)}"
    )


# ---------------------------------------------------------------------------
# AC-11 — fuehrende Null nur in der Kurznachricht
# ---------------------------------------------------------------------------


def test_ac11_nur_die_kurznachricht_kuerzt_die_fuehrende_null():
    """AC-11: Given ein Onset-Alarm mit `onset_time="09:05"` / When derselbe
    Alarm ueber SMS, E-Mail und Telegram gerendert wird / Then traegt ALLEIN
    die Kurznachricht die Stunde ohne fuehrende Null (`TH@9:05`), waehrend
    E-Mail und Telegram die volle Form `09:05` behalten. Die Minuten bleiben
    ueberall zweistellig, das Feld `onset_time` selbst bleibt unveraendert.

    Ein Test, der beide Seiten gegeneinanderstellt — eine Kuerzung an der
    falschen Stelle schlaegt hier rot."""
    event = _onset_event(onset_time="09:05", onset_minutes=12)
    msg = _onset_msg(event)

    sms = render_sms(msg)
    telegram = render_telegram(msg)
    _html, plain = render_email(msg)

    assert "TH@9:05" in sms, (
        f"Kurznachricht muss die Stunde ohne fuehrende Null zeigen: {sms!r}"
    )
    assert "09:05" not in sms, (
        f"Kurznachricht traegt noch die fuehrende Null: {sms!r}"
    )
    treffer = _ZEITPUNKT_TOKEN_RE.search(sms)
    assert treffer and treffer.group(3) == "05", (
        f"Die Minuten muessen zweistellig bleiben: {sms!r}"
    )

    assert "09:05" in telegram, (
        f"Telegram muss die volle Form '09:05' behalten: {telegram!r}"
    )
    assert "9:05 ·" not in telegram.replace("09:05 ·", ""), (
        f"Telegram darf die Stunde nicht kuerzen: {telegram!r}"
    )
    assert "ab 09:05" in plain, (
        f"E-Mail muss die volle Form '09:05' behalten: {plain!r}"
    )

    assert event.onset_time == "09:05", (
        "Das Feld onset_time selbst darf nicht veraendert werden — nur seine "
        "Darstellung in der Kurznachricht"
    )
