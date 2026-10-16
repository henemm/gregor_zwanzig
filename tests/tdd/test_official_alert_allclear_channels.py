"""TDD RED -- Entwarnung bei amtlichen Warnungen: Versand ueber vier Kanaele in
zwei Flaechen, Dringlichkeit an der Wirkstelle, gemeinsame Nachricht,
Darstellung (Issue #1441 Scheibe S2).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md -- AC-3, AC-4, AC-12, AC-16
      (Erkennung/Gedaechtnis: test_official_alert_allclear.py)

Beobachtet wird, WAS TATSAECHLICH HINAUSGEHT: die vier Ausgangs-Klassen
(E-Mail, Telegram, SMS, Premium-SMS) sind durch den geteilten Aufzeichner
ersetzt (`tests/helpers/transport_mitschrift.py`). Die Kanalauswahl und die
Kanal-Schwelle fallen weiter im Produktivcode (`split_by_threshold` im Trip-
bzw. Ortsvergleich-Pfad) -- geprueft wird an ihrer Wirkstelle, nicht am
Rueckgabewert von `urgency_from_official_transition`.

Kuerzel: aus dem Katalog (`hazard_symbols.sms_symbol_for`) -- Gewitter ist
`TS`, Hitze `HT`, Lawinen-Lagebericht `AV` (die Spec schreibt beispielhaft
`+TH:H>L`; die Token-FORM `+{Kuerzel}:{alt}>{neu}` bzw. `+AV{alt}>{neu}` ist
das, was hier geprueft wird).

RED heute: keine Entwarnung wird erkannt oder versendet.
"""
from __future__ import annotations

import re

import pytest

from output.tokens.hazard_symbols import sms_symbol_for
from tests.helpers.transport_mitschrift import ALLE_KANAELE, aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    EMPFEHLUNGS_WOERTER, FLAECHEN, Szenario, basis_jetzt,
    entwarnungs_sendungen, lauf_erstwarnung, quellen,
)

VIER_AUF_ZWEI = re.compile(r"4\s*(?:→|->|>)\s*2")
HT = sms_symbol_for("extreme_heat")  # "HT"
TS = sms_symbol_for("thunderstorm")  # "TS"
#: Renderer-Grenzen (Spec v1.1): Standalone-SMS 140, Premium-SMS 153 (channel_layout).
_LIMIT = {"sms": 140, "premium_sms": 153}


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


def _text(sendung: dict) -> str:
    return " ".join(str(sendung.get(f) or "") for f in ("subject", "body", "plain_text_body"))


# ═══════════════════════════ AC-3 ═══════════════════════════════════════════


@pytest.mark.parametrize("kanal", ALLE_KANAELE)
@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac3_entwarnung_kommt_in_jeder_flaeche_ueber_jeden_kanal_an(monkeypatch, mit, flaeche, kanal):
    """AC-3 [Matrix 4 Kanaele x 2 Flaechen] -- Premium-SMS ausdruecklich auch
    im Ortsvergleich.
    GIVEN eine per Alarm gemeldete Hitzewarnung Stufe 4 (alle vier Alarmkanaele
          eingeschaltet, Premium-Tarif) sinkt bei gesunder Quelle auf Stufe 2
    WHEN  der Alarmlauf (Trip bzw. Ortsvergleich) sie versendet
    THEN  kommt die Entwarnung auf dem Kanal `kanal` an -- mit Gefahr, Ort und
          alt -> neu in kanalgerechter Form (Mail/Telegram: "Entwarnung" +
          "4 -> 2"; SMS/Premium-SMS: GSM-7-Block `+HT:H>L`).
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)  # Vorbedingung: Lauf 1 erreichte ALLE vier Kanaele
        sz.x.alerts = [sz.warnung(2)]
        snap = sz.lauf(15)

    ew = entwarnungs_sendungen(snap, kanal)
    assert len(ew) == 1, f"AC-3 [{flaeche}/{kanal}]: genau eine Entwarnung erwartet -- {snap!r}"
    text = _text(ew[0])
    ort = "Segment 1" if flaeche == "trip" else "Innsbruck"
    if kanal in ("sms", "premium_sms"):
        assert f"+{HT}:H>L" in ew[0]["body"], f"AC-3 [{flaeche}/{kanal}]: Block `+{HT}:H>L` fehlt: {ew[0]['body']!r}"
    else:
        assert "Entwarnung" in text and VIER_AUF_ZWEI.search(text), (
            f"AC-3 [{flaeche}/{kanal}]: 'Entwarnung' + '4 -> 2' fehlt: {text[:600]!r}")
        assert "Hitze" in text, f"AC-3 [{flaeche}/{kanal}]: Gefahr fehlt: {text[:600]!r}"
        assert ort in text, f"AC-3 [{flaeche}/{kanal}]: Ort fehlt: {text[:600]!r}"


# ═══════════════════════════ AC-4 ═══════════════════════════════════════════


_SCHWELLEN = {"email": "LOW", "telegram": "LOW", "sms": "LOW", "premium_sms": "HIGH"}


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac4_entwarnung_von_hoch_erreicht_premium_sms_nach_alter_stufe(monkeypatch, mit, flaeche):
    """AC-4 [Dringlichkeit nach ALTER Stufe, an der Wirkstelle].
    GIVEN Premium-SMS hat die Schwelle "hoch", die anderen Kanaele "gering";
          eine Warnung Stufe 4 ("hoch") sinkt auf Stufe 2 ("gering")
    WHEN  die Entwarnung versendet wird
    THEN  erreicht sie die Kanaele, die fuer "hoch" gelten -- einschliesslich
          Premium-SMS. (Mutation "Dringlichkeit aus der NEUEN Stufe" -> LOW ->
          Premium-SMS faellt weg -> dieser Test wird rot.)
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt(), schwellen=_SCHWELLEN)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        snap = sz.lauf(15)

    bedient = {k for k in ALLE_KANAELE if entwarnungs_sendungen(snap, k)}
    assert bedient == set(ALLE_KANAELE), (
        f"AC-4 [{flaeche}]: Entwarnung von 'hoch' muss alle vier Kanaele inkl. Premium-SMS "
        f"erreichen, bedient: {sorted(bedient)} -- {snap!r}")


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac4_entwarnung_von_gering_erreicht_premium_sms_nicht(monkeypatch, mit, flaeche):
    """AC-4 (Gegenrichtung).
    GIVEN dieselben Schwellen; eine Warnung Stufe 2 ("gering") wurde gemeldet
          (ohne Premium-SMS, Schwelle "hoch") und endet vorzeitig
    WHEN  die Entwarnung "beendet" nach zwei Laeufen versendet wird
    THEN  erreicht sie E-Mail, Telegram und SMS, NICHT aber Premium-SMS.
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt(), level=2, schwellen=_SCHWELLEN)
    with quellen(sz.x):
        erst = lauf_erstwarnung(sz, kanaele=("email", "telegram", "sms"))
        assert not erst.sendungen("premium_sms"), (
            f"Vorbedingung: die Schwelle 'hoch' fuer Premium-SMS wirkt (Stufe-2-Warnung ohne Premium-SMS): {erst!r}")
        sz.x.alerts = []
        sz.lauf(15)
        snap = sz.lauf(30)

    bedient = {k for k in ALLE_KANAELE if entwarnungs_sendungen(snap, k)}
    assert bedient == {"email", "telegram", "sms"}, (
        f"AC-4 [{flaeche}]: Entwarnung von 'gering' -> E-Mail/Telegram/SMS, nicht Premium-SMS; "
        f"bedient: {sorted(bedient)} -- {snap!r}")


# ═══════════════════════════ AC-12 ══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac12_neue_warnung_und_entwarnung_in_einer_nachricht(monkeypatch, mit, flaeche):
    """AC-12 [Gemeinsam mit neuer Warnung].
    GIVEN im selben Lauf liegen eine NEUE Sturmwarnung Stufe 3 ("mittel") und
          eine Entwarnung der Hitzewarnung 4 -> 2 vor; Premium-SMS-Schwelle "hoch"
    WHEN  die Nachricht erzeugt wird
    THEN  ist es EINE Nachricht je Kanal, die Warnung steht VOR dem
          Entwarnungs-Abschnitt (Betreff: Warnung zuerst, dann "Entwarnung"),
          und die Dringlichkeit ist das Maximum aus beiden ("hoch" -> auch
          Premium-SMS wird bedient; aus der neuen Warnung allein waere es
          "mittel" und Premium-SMS bliebe stumm).
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt(), schwellen=_SCHWELLEN)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sturm = sz.warnung(3, hazard="wind_gust", label="Sturmwarnung")
        sz.x.alerts = [sz.warnung(2), sturm]
        snap = sz.lauf(15)

    for kanal in ALLE_KANAELE:
        assert len(snap.sendungen(kanal)) == 1, f"AC-12 [{flaeche}]: EINE Nachricht auf {kanal}: {snap!r}"
        assert entwarnungs_sendungen(snap, kanal), f"AC-12 [{flaeche}]: Entwarnung fehlt auf {kanal}: {snap!r}"
    mail = snap.sendungen("email")[0]
    plain = str(mail.get("plain_text_body") or "")
    assert "Sturm" in plain and "Entwarnung" in plain, f"AC-12: Warnung + Entwarnung im Klartext: {plain!r}"
    assert plain.index("Sturm") < plain.index("Entwarnung"), f"AC-12: Warnung muss zuerst stehen: {plain!r}"
    betreff = mail["subject"]
    assert "Entwarnung" in betreff and "Sturm" in betreff, f"AC-12: Betreff: {betreff!r}"
    assert betreff.index("Sturm") < betreff.index("Entwarnung"), f"AC-12: Betreff-Reihenfolge: {betreff!r}"
    sms = snap.sendungen("sms")[0]["body"]
    assert sms.index("!") < sms.index("+"), f"AC-12: `!`-Block vor `+`-Block: {sms!r}"


def test_ac12_von_der_sms_kuerzung_verdraengte_entwarnung_gilt_als_nicht_zugestellt(monkeypatch, mit):
    """AC-12 [SMS-Kuerzung].
    GIVEN NUR SMS ist Alarmkanal; im selben Lauf kommen acht neue Warnungen
          (Stufe 3, mit Uhrzeit), die das SMS-Budget allein schon fuellen, und
          die Entwarnung der Hitzewarnung 4 -> 2
    WHEN  die SMS erzeugt wird
    THEN  bleiben die Warnungen erhalten (`!`-Block), die verdraengte
          Entwarnung gilt als NICHT zugestellt -- ihr Gedaechtnis bleibt auf 4 --
          und sie kommt im naechsten Lauf (keine neuen Warnungen mehr).
    """
    nur_sms = {"email": False, "telegram": False, "sms": True, "premium_sms": False}
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), kanaele=nur_sms)
    gefahren = ("thunderstorm", "flood", "rain", "wind_gust", "snow", "black_ice",
                "extreme_cold", "wildfire_risk")
    with quellen(sz.x):
        lauf_erstwarnung(sz, kanaele=("sms",))
        neue = [sz.warnung(3, hazard=h, region=f"Region-{h}") for h in gefahren]
        sz.x.alerts = [sz.warnung(2)] + neue
        voll = sz.lauf(15)
        nach_kuerzung = sz.eintrag()
        naechster = sz.lauf(30)

    assert len(voll.sendungen("sms")) == 1, f"Vorbedingung: EINE SMS mit den neuen Warnungen: {voll!r}"
    text = voll.sendungen("sms")[0]["body"]
    assert "!" in text, f"AC-12: Warnungen haben Vorrang in der SMS: {text!r}"
    assert len(text) <= _LIMIT["sms"], f"AC-12: SMS ueber Renderer-Grenze: {len(text)}"
    assert f"+{HT}" not in text, f"Vorbedingung: Entwarnung durch Kuerzung verdraengt: {text!r}"
    assert nach_kuerzung.get("last_reported_value") == 4.0, (
        f"AC-12: verdraengte Entwarnung darf das Gedaechtnis nicht senken: {nach_kuerzung!r}")
    assert any(f"+{HT}:H>L" in s["body"] for s in naechster.sendungen("sms")), (
        f"AC-12: verdraengte Entwarnung muss im naechsten Lauf kommen: {naechster!r}")


# ═══════════════════════════ AC-16 ══════════════════════════════════════════


def _keine_empfehlung(text: str, wo: str) -> None:
    klein = text.lower()
    treffer = [w for w in EMPFEHLUNGS_WOERTER if w in klein]
    assert not treffer, f"AC-16 [{wo}]: Handlungsempfehlung im Text ({treffer}): {text[:600]!r}"


def test_ac16_darstellung_gesenkt_mail_telegram_sms_premium(monkeypatch, mit):
    """AC-16 [Darstellung, gesenkt].
    GIVEN eine Gewitterwarnung Stufe 4 sinkt auf Stufe 2 (Trip)
    WHEN  die Entwarnung versendet wird
    THEN  Mail: Betreff mit "Entwarnung"; HTML UND Klartext mit eigenem Abschnitt
          "Entwarnung", Gefahr ("Gewitter"), Region, "4 -> 2"; Telegram: dieselben
          Angaben; SMS/Premium-SMS: GSM-7-Block `+TS:H>L`, nur ASCII, <= Renderer-Grenze (140/153),
          ohne Emoji; nirgends eine Handlungsempfehlung.
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), hazard="thunderstorm")
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        snap = sz.lauf(15)

    mails = entwarnungs_sendungen(snap, "email")
    assert mails, f"AC-16: keine Entwarnungs-Mail: {snap!r}"
    mail = mails[0]
    assert "Entwarnung" in mail["subject"], f"AC-16: Betreff: {mail['subject']!r}"
    for teil, inhalt in (("HTML", str(mail["body"])), ("Klartext", str(mail["plain_text_body"] or ""))):
        assert "Entwarnung" in inhalt, f"AC-16 [{teil}]: Abschnitt 'Entwarnung' fehlt"
        assert "Gewitter" in inhalt, f"AC-16 [{teil}]: Gefahr fehlt"
        assert "Innsbruck-Land" in inhalt, f"AC-16 [{teil}]: Region fehlt"
        assert VIER_AUF_ZWEI.search(inhalt), f"AC-16 [{teil}]: 'Stufe 4 -> 2' fehlt"
        _keine_empfehlung(inhalt, f"Mail {teil}")
    tg = entwarnungs_sendungen(snap, "telegram")
    assert tg and "Gewitter" in tg[0]["body"] and VIER_AUF_ZWEI.search(tg[0]["body"]), (
        f"AC-16: Telegram ohne Gefahr/Uebergang: {snap.sendungen('telegram')!r}")
    _keine_empfehlung(tg[0]["body"], "Telegram")
    for kanal in ("sms", "premium_sms"):
        ew = entwarnungs_sendungen(snap, kanal)
        assert ew, f"AC-16: keine Entwarnung auf {kanal}: {snap!r}"
        sms = ew[0]["body"]
        assert f"+{TS}:H>L" in sms, f"AC-16 [{kanal}]: Block `+{TS}:H>L` fehlt: {sms!r}"
        assert sms.isascii() and len(sms) <= _LIMIT[kanal], f"AC-16 [{kanal}]: GSM-7/Renderer-Grenze: {sms!r}"
        _keine_empfehlung(sms, kanal)


def test_ac16_darstellung_beendet_und_telegram_kurzform(monkeypatch, mit):
    """AC-16 [Darstellung, beendet; Telegram-Kurzform folgt der SMS-Form].
    GIVEN eine Gewitterwarnung Stufe 4 endet vorzeitig (zwei Laeufe), der Trip
          nutzt den Telegram-Kurzstil
    WHEN  die Entwarnung versendet wird
    THEN  SMS/Premium-SMS tragen `+TS:H>0`, Telegram traegt dieselbe Kurzform,
          die Mail nennt "beendet".
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), hazard="thunderstorm",
                  telegram_stil="kurzform")
    with quellen(sz.x):
        erst = lauf_erstwarnung(sz)
        tg1 = erst.sendungen("telegram")[0]
        assert tg1["parse_mode"] is None and "!" in tg1["body"], (
            f"Vorbedingung: der Kurzstil wirkt schon fuer die Warnung (SMS-Form): {tg1!r}")
        sz.x.alerts = []
        sz.lauf(15)
        snap = sz.lauf(30)

    for kanal in ("sms", "premium_sms", "telegram"):
        ew = entwarnungs_sendungen(snap, kanal)
        assert ew and f"+{TS}:H>0" in ew[0]["body"], f"AC-16 [{kanal}]: `+{TS}:H>0` fehlt: {snap.sendungen(kanal)!r}"
        assert ew[0]["body"].isascii(), f"AC-16 [{kanal}]: nicht ASCII: {ew[0]['body']!r}"
    mail = entwarnungs_sendungen(snap, "email")
    assert mail and "beendet" in str(mail[0]["plain_text_body"] or ""), f"AC-16: Mail ohne 'beendet': {snap!r}"
    _keine_empfehlung(str(mail[0]["plain_text_body"] or ""), "Mail beendet")


def test_ac16_lawinen_lagebericht_traegt_den_numerischen_uebergang(monkeypatch, mit):
    """AC-16 [Lawine, numerische Skala].
    GIVEN ein Lawinen-Lagebericht (EAWS, `native_level`) meldete Stufe 4 und
          senkt auf Stufe 2
    WHEN  die Entwarnung versendet wird
    THEN  tragen SMS/Premium-SMS den Block `+AV4>2`.
    """
    from services.official_alerts.models import AVALANCHE_BULLETIN

    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), hazard=AVALANCHE_BULLETIN,
                  scale="eaws", native_level=4)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2, native_level=2)]
        snap = sz.lauf(15)

    for kanal in ("sms", "premium_sms"):
        ew = entwarnungs_sendungen(snap, kanal)
        assert ew and "+AV4>2" in ew[0]["body"], f"AC-16 [{kanal}]: `+AV4>2` fehlt: {snap.sendungen(kanal)!r}"
