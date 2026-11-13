"""#2795 S3b Teil 1a, Fix-Runde 3 nach Adversary-Runde 3 (F013 bis F015).

Findings: docs/artifacts/feature-2795-s3b-teil1-zustellung/adversary-dialog.md

* F013  Orts-Briefing 06:45: Zeitplan-Versand scheitert, der Nachholversand um
        10:00 scheitert ebenfalls, danach erholt => der neue Vermerk traegt
        weiter Minute 45 und der Hinweis nennt 06:45 (nicht 06:00).
* F014  Nachholversand ohne Wetterdaten (``no_weather``): der wiederholte
        Vermerk behaelt Minute 45.
* F015  Unlesbare Minute im Vermerk faellt auf die volle Stunde zurueck, statt
        den Nachholversand abzubrechen.

Kein Mock: echter stuendlicher Compare-Lauf mit schaltbar gestoertem
Transport (Haus-Fixture aus #2587), echte Ablage-Dateien.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from i18n import t
from services.pending_briefings import dispatch_error_hint, slot_uhrzeit
from tests.tdd import _handversand_fixtures as hv
# ruff: noqa: F811  (aus = geteilte Fixture als Testparameter)
from tests.tdd.test_compare_briefing_nachholen import (  # noqa: F401  (aus = Fixture)
    D, _ablage_schreiben, _lauf, _nutzer, _pid, _utc, _vergleich, _vergleich_vermerke,
    _vermerk, aus,
)

_MINUTE_45 = timedelta(minutes=45)


def _hinweis(stunde: str) -> str:
    return t("versand.scheduler.zustellung_fehlgeschlagen", "de", stunde=stunde)


def _einzige_mail(aus_) -> str:
    mails = aus_.mit.sendungen("email")
    assert len(mails) == 1, f"genau eine nachgeholte Mail erwartet: {aus_.mit!r}"
    return mails[0]["plain_text_body"] or ""


# ───────────────────────────── F013 ─────────────────────────────


def test_f013_zweiter_fehlschlag_des_nachholers_behaelt_0645(aus):
    """06:45 gestoert => Vermerk (6, 45); Nachholversuch 10:00 gestoert => frischer
    Vermerk, weiter (6, 45); 11:00 erholt => Hinweis nennt 06:45."""
    uid = _nutzer()
    _vergleich(uid, _pid("f013"), morgen="06:45:00")
    aus.stoerung.add("email")

    _lauf(uid, _utc(D, 6) + _MINUTE_45)
    erster = _vergleich_vermerke(uid)
    assert [(v.get("slot_hour"), v.get("slot_minute")) for v in erster] == [(6, 45)], erster

    versuche_vorher = aus.versuche["email"]
    _lauf(uid, _utc(D, 10))
    assert aus.versuche["email"] > versuche_vorher, "Vorbedingung: kein Nachholversuch um 10:00"
    zweiter = _vergleich_vermerke(uid)
    assert len(zweiter) == 1, zweiter
    assert (zweiter[0].get("slot_hour"), zweiter[0].get("slot_minute")) == (6, 45), (
        f"F013: der zweite Fehlschlag verliert die Minute: {zweiter[0]!r}"
    )

    aus.stoerung.clear()
    _lauf(uid, _utc(D, 11))
    plain = _einzige_mail(aus)
    assert plain.startswith(_hinweis("06:45")), f"F013: Hinweis nennt nicht 06:45: {plain[:160]!r}"
    assert _vergleich_vermerke(uid) == [], "Nach Zustellung kein Vermerk mehr"


# ───────────────────────────── F014 ─────────────────────────────


def test_f014_nachholer_ohne_wetterdaten_behaelt_minute_45(aus, monkeypatch):
    """Vermerk 06:45, Nachholversand um 10:00 endet mit ``no_weather`` => der
    Vermerk bleibt fuer die naechste Stunde und traegt weiter Minute 45."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f014"), morgen="06:45:00")
    alt = _vermerk(pid, "morning", D, 6, attempts=1)
    alt["slot_minute"] = 45
    _ablage_schreiben(uid, [alt])
    hv.wetter_fehlt_je_ort(monkeypatch)

    _lauf(uid, _utc(D, 10))

    assert aus.mit.kanaele == [], aus.mit
    vermerke = _vergleich_vermerke(uid)
    assert len(vermerke) == 1, vermerke
    v = vermerke[0]
    assert v.get("attempts") == 2, f"Vorbedingung: no_weather-Zweig nicht getroffen: {v!r}"
    assert (v.get("slot_hour"), v.get("slot_minute")) == (6, 45), (
        f"F014: no_weather-Wiederholung verliert die Minute: {v!r}"
    )


# ───────────────────────────── F015 ─────────────────────────────


@pytest.mark.parametrize("minute", ["abc", "", [45], {"m": 45}, None])
def test_f015_unlesbare_minute_ergibt_volle_stunde(minute):
    """Unlesbare oder fehlende Minute => ``06:00``, keine Ausnahme."""
    assert slot_uhrzeit(6, minute) == "06:00"
    assert dispatch_error_hint(6, minute, lang="de") == _hinweis("06:00")


def test_f015_nachholversand_mit_unlesbarer_minute_laeuft_durch(aus):
    """Vermerk mit Minute ``"abc"`` => der Nachholversand geht hinaus, der
    Hinweis nennt die volle Stunde 06:00, der Vermerk ist danach weg."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f015"), morgen="06:45:00")
    kaputt = _vermerk(pid, "morning", D, 6)
    kaputt["slot_minute"] = "abc"
    _ablage_schreiben(uid, [kaputt])

    _lauf(uid, _utc(D, 11))

    plain = _einzige_mail(aus)
    assert plain.startswith(_hinweis("06:00")), plain[:160]
    assert _vergleich_vermerke(uid) == [], "Nach Zustellung kein Vermerk mehr"
