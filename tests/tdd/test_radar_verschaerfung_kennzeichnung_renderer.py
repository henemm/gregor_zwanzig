"""TDD RED — Issue #2848: Verschaerfungs-Hinweis im geteilten Alarm-Renderer.

SPEC: docs/specs/modules/fix_2848_radar_verschaerfung_kennzeichnen.md
(AC-5 Laenge/GSM-7, AC-6 zweisprachig + Katalog-Paritaet; Renderer-Haelfte
von AC-3/AC-8: ohne Kennzeichen byte-gleich zum Bestand).

Vertrag fuer /50-implement (Spec, Arbeitstitel):

* ``AlertMessage.verschaerfung: tuple[float, float] | None = None`` —
  Wertepaar ``(basis_mm, menge_mm)``, additiv; ``None`` -> byte-identisch.
* E-Mail (HTML + Klartext) und Telegram-Langform: Satz aus dem Katalog
  ``alarm.json`` — DE „Dasselbe Ereignis, jetzt stärker: 7,3 statt 3,1 mm",
  EN „Same event, now stronger: 7.3 instead of 3.1 mm".
* SMS / Premium-SMS / Telegram-Kurzform (ein Text, ``render_sms``):
  Token ``UP 3.1>7.3`` direkt nach dem Ortskopf, vor dem Radar-Token, nie
  uebersetzt; Laenge vom Limit reserviert (Muster ``_ADDENDUM_SMS_PREFIX``),
  Zusatz-Token (Zonen, Marker) weichen zuerst.

Grenzen (gemessen am Code, nicht angenommen): der Alarm-Versand rendert die
SMS mit ``limit=140`` (`notification_service._dispatch_alert_message`); die
Premium-SMS-Grenze ist ``CHANNEL_LIMITS["premium_sms"]`` = 153
(`docs/reference/premium_sms_format.md`); die absolute SMS-Grenze 160.

Die neuen Felder werden bewusst IN den Testfunktionen gesetzt — vor der
Implementierung scheitert jeder Kennzeichnungs-Test einzeln (TypeError am
unbekannten Feld), nicht die ganze Datei beim Sammeln.

Mock-frei: echte ``AlertMessage``/``OnsetEvent``-Objekte, echte Renderer.
"""
from __future__ import annotations

import logging
import re
from dataclasses import replace

import pytest

from app.ampel import resolve_ampel
from i18n.catalog import MESSAGES_DIR, parity_errors
from output.renderers.alert.model import AlertMessage
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from services.rain_extent import RainZone

from tests.helpers.alarm_fixture import (
    _onset, als_text, golden_pfad, nachricht, render_fall,
)
from tests.tdd._gsm7_charset import assert_gsm7_clean

SMS_LIMIT_ALARM = 140      # notification_service._dispatch_alert_message
PREMIUM_SMS_LIMIT = 153    # CHANNEL_LIMITS["premium_sms"]
SMS_LIMIT_ABSOLUT = 160

SATZ_DE = "Dasselbe Ereignis, jetzt stärker: 7,3 statt 3,1 mm"
SATZ_EN = "Same event, now stronger: 7.3 instead of 3.1 mm"
TOKEN = "UP 3.1>7.3"
_HINWEIS_RE = re.compile(r"Dasselbe Ereignis|Same event|\bUP \d")
_DEUTSCHE_HINWEISWOERTER = ("Dasselbe", "Ereignis", "stärker", "staerker", " statt ")


def _trip_radar(**extra) -> AlertMessage:
    """Trip-Radar-Erstalarm (Bauform wie Golden-Fall `regen_einzel`, ohne
    Kennzeichen)."""
    e = _onset(**extra)
    return AlertMessage(
        trip_short="GR20 Golden", stand_at="06:00", events=(e,),
        source="Radar (DWD)", cooldown_display="2 Stunden",
        ampel=resolve_ampel(None),
    )


def _mit_verschaerfung(msg: AlertMessage, basis: float, menge: float) -> AlertMessage:
    # `replace` ruft den Dataclass-Konstruktor: vor der Implementierung
    # scheitert genau hier ein TypeError (unbekanntes Feld) — der RED-Grund.
    return replace(msg, verschaerfung=(basis, menge))


def _kopf_und_radar_token(sms: str) -> tuple[str, str]:
    kopf, rest = sms.split(": ", 1)
    return kopf, rest.split(" ", 1)[0]


def _zonen_token(sms: str) -> str:
    m = re.search(r" km[\d,\-]+", sms)
    return m.group(0) if m else ""


# ─────────────────────────────── AC-5 ────────────────────────────────────────


def _extremfall(**ueberschreiben) -> AlertMessage:
    """Ende-Angabe (Untergrenze), Schaerfe-Marker, Luecken-Marker, Gewitter-
    pruefung ausgefallen, Etappen-Praefix, zweistellige Menge und VIELE
    vermessene Regenzonen, deren Kuerzel das Budget ausschoepfen."""
    zonen = tuple(
        RainZone(km_from=10.0 + 4 * i, km_to=12.0 + 4 * i, onset_minutes=25,
                 event_end_minutes=90)
        for i in range(30)
    )
    basis = dict(
        km_measured=True, event_end_time="00:40", event_end_day_offset=1,
        event_end_weekday="Fr", event_ongoing_beyond_horizon=True,
        location_sharpness_limit_time="07:30", rain_zones=zonen, gap_km=(16.0,),
        convective_checked=False, stage_number=12, onset_precip_mm=27.5,
        onset_day_offset=1, onset_weekday="Fr",
    )
    basis.update(ueberschreiben)
    return _trip_radar(**basis)


_EXTREMFAELLE = {
    "ziel_mit_zonen": {},
    "langer_ortsname": {
        "location_label": "Refuge de la Sega sous le Capu Tafunatu Hochpass",
        "segment_id": None,
    },
    "gewitter": {"is_convective": True, "intensity_label": "Starker Hagel/Gewitter"},
}


@pytest.mark.parametrize("limit", [SMS_LIMIT_ALARM, PREMIUM_SMS_LIMIT, SMS_LIMIT_ABSOLUT])
@pytest.mark.parametrize("fall", sorted(_EXTREMFAELLE))
def test_ac5_sms_mit_hinweis_haelt_die_grenze_und_behaelt_kopf_token_und_radar(fall, limit):
    """AC-5. GIVEN ein Verschaerfungs-Alarm (12,4 -> 27,5 mm) mit Extrem-
    Eingaben, WHEN die SMS (= Premium-SMS-Text) mit der Grenze des Kanals
    gerendert wird, THEN ist sie <= Grenze, GSM-7-rein und beginnt mit
    `<Ortskopf>: UP 12.4>27.5 <Radar-Token>` — Kopf, Hinweis und Radar-Token
    bleiben vollstaendig, gekuerzt werden nur Zusatz-Token."""
    ohne = _extremfall(**_EXTREMFAELLE[fall])
    basis_sms = render_sms(ohne, limit=limit)
    kopf, radar = _kopf_und_radar_token(basis_sms)

    sms = render_sms(_mit_verschaerfung(ohne, 12.4, 27.5), limit=limit)

    assert len(sms) <= limit, f"AC-5: {len(sms)} > {limit}: {sms!r}"
    assert len(sms) <= SMS_LIMIT_ABSOLUT
    assert_gsm7_clean(sms, f"AC-5 {fall} limit={limit}")
    erwartet = f"{kopf}: UP 12.4>27.5 {radar}"
    assert sms.startswith(erwartet), (
        f"AC-5: Kopf, Hinweis-Token und Radar-Token muessen vollstaendig und in "
        f"dieser Reihenfolge stehen. Erwartet Anfang {erwartet!r}, war {sms!r} "
        f"(ohne Hinweis: {basis_sms!r})"
    )


def test_ac5_zonen_weichen_zuerst_nie_der_hinweis():
    """AC-5. GIVEN die SMS ohne Hinweis schoepft das 140er-Budget mit
    Zonen-Kuerzeln aus, WHEN der Hinweis dazukommt, THEN verliert sie
    Zonen (Zusatz-Token), nicht den Hinweis — und die verbleibenden Zonen
    sind ein vollstaendiger Anfang der urspruenglichen Liste (nie eine
    angeschnittene Spanne)."""
    ohne = _extremfall()
    basis_sms = render_sms(ohne, limit=SMS_LIMIT_ALARM)
    basis_zonen = _zonen_token(basis_sms)
    assert basis_zonen, f"Testaufbau: die SMS ohne Hinweis muss Zonen tragen: {basis_sms!r}"
    assert len(basis_sms) > SMS_LIMIT_ALARM - len("UP 12.4>27.5 "), (
        f"Testaufbau: ohne Kuerzung muesste der Hinweis die Grenze sprengen "
        f"({len(basis_sms)} Zeichen: {basis_sms!r})"
    )

    sms = render_sms(_mit_verschaerfung(ohne, 12.4, 27.5), limit=SMS_LIMIT_ALARM)
    assert "UP 12.4>27.5" in sms, f"AC-5: der Hinweis darf nie weichen: {sms!r}"
    assert len(sms) <= SMS_LIMIT_ALARM
    zonen = _zonen_token(sms)
    assert len(zonen) < len(basis_zonen), (
        f"AC-5: Platz fuer den Hinweis muss aus den Zonen kommen: vorher "
        f"{basis_zonen!r}, nachher {zonen!r}"
    )
    if zonen:
        spannen, basis_spannen = zonen[3:].split(","), basis_zonen[3:].split(",")
        assert spannen == basis_spannen[: len(spannen)], (
            f"AC-5: verbleibende Zonen muessen ein vollstaendiger Anfang sein: "
            f"{zonen!r} vs. {basis_zonen!r}"
        )


def test_ac5_hinweis_steht_auch_in_der_einfachen_sms_vor_dem_radar_token():
    """AC-5/AC-2 (Renderer). Ohne Zusatz-Token: `<Kopf>: UP 3.1>7.3 R...`;
    Reihenfolge Y>X (zuletzt gemeldet > jetzt) — vertauscht waere es eine
    Abschwaechung."""
    ohne = _trip_radar()
    kopf, radar = _kopf_und_radar_token(render_sms(ohne))
    sms = render_sms(_mit_verschaerfung(ohne, 3.1, 7.3))
    assert sms.startswith(f"{kopf}: {TOKEN} {radar}"), sms
    assert "UP 7.3>3.1" not in sms


# ─────────────────────────────── AC-6 ────────────────────────────────────────


@pytest.mark.parametrize("lang,satz", [("de", SATZ_DE), ("en", SATZ_EN)])
def test_ac6_mail_und_telegram_tragen_den_satz_in_der_nutzersprache(lang, satz):
    """AC-6. Derselbe Verschaerfungs-Alarm (3,1 -> 7,3 mm) — E-Mail (HTML und
    Klartext) und Telegram-Langform tragen den Satz in der Sprache des
    Nutzers mit SEINER Zahlenform (DE Komma, EN Punkt)."""
    msg = _mit_verschaerfung(_trip_radar(), 3.1, 7.3)
    html, plain = render_email(msg, lang=lang)
    telegram = render_telegram(msg, lang=lang)
    assert satz in plain, f"AC-6 {lang}: Klartext ohne {satz!r}: {plain!r}"
    assert satz in html, f"AC-6 {lang}: HTML ohne {satz!r}"
    assert satz in telegram, f"AC-6 {lang}: Telegram ohne {satz!r}: {telegram!r}"


def test_ac6_sms_token_ist_fuer_beide_sprachen_identisch():
    """AC-6. Die Kurzform wird nie uebersetzt: derselbe Alarm ergibt fuer
    DE- und EN-Nutzer dieselbe SMS mit `UP 3.1>7.3` (Punkt, auch fuer DE)."""
    msg = _mit_verschaerfung(_trip_radar(), 3.1, 7.3)
    sms = render_sms(msg)
    assert TOKEN in sms, f"AC-6: SMS ohne {TOKEN!r}: {sms!r}"
    assert "3,1" not in sms and "7,3" not in sms


def test_ac6_englischer_alarm_ohne_deutschen_hinweistext_und_ohne_katalog_rueckfall(caplog):
    """AC-6. Im englischen Alarm steht kein deutsches Wort des Hinweises, und
    der Katalog faellt beim Rendern fuer keinen Schluessel auf Deutsch zurueck
    (`i18n fallback`/`missing`-Meldung des echten Katalogs)."""
    msg = _mit_verschaerfung(_trip_radar(), 3.1, 7.3)
    with caplog.at_level(logging.WARNING, logger="i18n"):
        html, plain = render_email(msg, lang="en")
        telegram = render_telegram(msg, lang="en")
        subject = render_subject(msg, lang="en")
    for name, text in (("plain", plain), ("telegram", telegram), ("subject", subject)):
        for wort in _DEUTSCHE_HINWEISWOERTER:
            assert wort not in text, f"AC-6: deutsches {wort!r} im EN-{name}: {text!r}"
    rueckfaelle = [r.getMessage() for r in caplog.records
                   if r.getMessage().startswith(("i18n fallback", "i18n missing"))]
    assert not rueckfaelle, f"AC-6: Katalog-Rueckfall im EN-Alarm: {rueckfaelle!r}"
    assert SATZ_EN in plain, f"AC-6: EN-Satz fehlt: {plain!r}"


def test_ac6_katalog_paritaet_de_en():
    """AC-6 (Waechter, gruen vor und nach der Aenderung). Jeder Schluessel
    beider Sprachen existiert in der anderen, mit denselben Platzhaltern —
    die neuen Hinweis-Schluessel eingeschlossen."""
    assert parity_errors(MESSAGES_DIR) == []


# ────────────────── AC-3 / AC-8: ohne Kennzeichen byte-gleich ─────────────────


def _golden(fall: str, lang: str, endung: str) -> bytes:
    return golden_pfad(fall, lang, endung).read_bytes()


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("fall", ["regen_einzel", "regen_spaet", "nachtrag", "regen_buendel"])
def test_ac3_ac8_ohne_kennzeichen_byte_gleich_zum_bestand(fall, lang):
    """AC-3 (Trip-Erstalarm: `regen_einzel`, `regen_spaet`, Nachtrag) und AC-8
    (Ortsvergleich-Buendel: `regen_buendel`) — WAECHTER. Ohne Kennzeichen
    rendern alle Kanaele byte-gleich zu den Golden-Dateien von VOR dieser
    Aenderung und tragen keinen Hinweis."""
    k = render_fall(fall, lang)
    assert k["html"].encode("utf-8") == _golden(fall, lang, "html"), f"{fall}/{lang} HTML"
    assert als_text(k).encode("utf-8") == _golden(fall, lang, "txt"), f"{fall}/{lang} Text"
    for kanal, text in k.items():
        assert not _HINWEIS_RE.search(text), f"{fall}/{lang}: Hinweis in {kanal}: {text!r}"


@pytest.mark.parametrize("fall", ["regen_einzel", "regen_buendel"])
def test_ac3_ac8_verschaerfung_none_ist_byte_gleich_zum_fehlenden_feld(fall):
    """AC-3/AC-8. Ein ausdruecklich auf `None` gesetztes Kennzeichen rendert
    in allen Kanaelen exakt wie das Bestandsobjekt (Default = kein Hinweis)."""
    msg = nachricht(fall, "de")
    msg_none = replace(msg, verschaerfung=None)
    for render in (render_subject, render_telegram):
        assert render(msg_none, lang="de") == render(msg, lang="de")
    assert render_email(msg_none, lang="de") == render_email(msg, lang="de")
    assert render_sms(msg_none) == render_sms(msg)
