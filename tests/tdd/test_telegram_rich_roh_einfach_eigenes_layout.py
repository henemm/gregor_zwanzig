"""TDD RED -- #2422 S6, B3 (= #2429): Telegram rich zeigt seine EIGENE Roh/Einfach-
Wahl, nicht die der E-Mail.

SPEC: docs/specs/modules/fix_2422_s6_register_leeren.md (AC-12)

Ursache (heute): ``trip_report.py`` bildet ``self._friendly_keys =
build_friendly_keys(dc)`` NACH der E-Mail-Kollabierung und reicht sie an
``render_telegram_bubbles`` -- Telegram rich liest dadurch die Wahl des E-Mail-
Layouts. Die Testluecke laut #2429 (``test_issue_435_format_modes.py`` kennt keinen
Telegram-Fall) schliesst diese Datei.

Beide Richtungen (E-Mail Roh + Telegram Einfach / E-Mail Einfach + Telegram Roh)
ueber den ECHTEN Loader/Kaskade/Formatter, Naht nur am Transport-Aufzeichner.
Erwartete Zelle: Roh = Zahl (``70``), Einfach = Emoji-Band von ``cloud_emoji``
(abgeleitet, nicht getippt).

RED-Gruende (heute): Telegram rich folgt der E-Mail-Wahl (beide Richtungen rot);
Orakel-Zelle ``cloud_total x telegram_rich x roh_einfach`` ist ohne Register-Eintrag
rot.

GUARD (heute gruen): ``test_ac12_guard_gleiche_wahl_in_beiden_kanaelen`` -- haben
E-Mail und Telegram dieselbe Wahl, stimmt alles (das ist die Konstellation, die
der B3-Fehler verdeckt hat, vgl. ``test_ac9_m3_...``).
"""
from __future__ import annotations

import pytest

from output.metric_format import cloud_emoji
from tests.helpers.einstellung_auslieferung_orakel import (
    _kanal_texte,
    _kurzuebersicht_wert,
    roh_wert_der_metrik,
    rote_zellen_fuer_golden,
)
from tests.tdd._einstellung_auslieferung_fixtures import golden_dict, render_trip_dict

pytestmark = pytest.mark.filterwarnings("ignore")

#: Fixture-Wert der Gesamtbewoelkung (``_voller_datenpunkt``: 70 %).
_PCT = 70


def _variante(email_einfach: bool, telegram_einfach: bool) -> dict:
    """golden_b mit ``cloud_total`` im E-Mail- und im Telegram-Layout in der
    gewuenschten Wahl (``use_friendly_format``; ``format_mode`` bleibt unbelegt)."""
    d = golden_dict("golden_b")
    layouts = d["display_config"]["channel_layouts"]
    for kanal, einfach in (("email", email_einfach), ("telegram", telegram_einfach)):
        eintrag = next(m for m in layouts[kanal] if m["metric_id"] == "cloud_total")
        assert eintrag["enabled"] is True, f"Testaufbau: cloud_total muss im {kanal}-Layout aktiv sein"
        eintrag.pop("format_mode", None)
        eintrag["use_friendly_format"] = einfach
    return d


def _zellen(monkeypatch, email_einfach: bool, telegram_einfach: bool):
    d = _variante(email_einfach, telegram_einfach)
    mit, _ = render_trip_dict(monkeypatch, d, name="s6-b3")
    return d, mit, {
        "email_plain": roh_wert_der_metrik(mit, "email_plain", "cloud_total"),
        "email_html": roh_wert_der_metrik(mit, "email_html", "cloud_total"),
        "telegram_rich": roh_wert_der_metrik(mit, "telegram_rich", "cloud_total"),
    }


_ROH = str(_PCT)
_EINFACH = cloud_emoji(float(_PCT))


def test_ac12_email_roh_telegram_einfach(monkeypatch):
    """AC-12: Given ``cloud_total`` im E-Mail-Layout "Roh" und im Telegram-Layout
    "Einfach", When das Trip-Briefing per E-Mail und Telegram rich gesendet wird,
    Then zeigt die E-Mail die Zahl, Telegram rich das Emoji-Band -- nie die Wahl
    des anderen Kanals.

    Mutation (B3-Zeile zurueck auf ``self._friendly_keys``): Telegram zeigt dann
    die Zahl -> rot."""
    _, _, z = _zellen(monkeypatch, email_einfach=False, telegram_einfach=True)
    assert z["email_plain"] == _ROH and z["email_html"] == _ROH, f"E-Mail Roh: {z}"
    assert z["telegram_rich"] == _EINFACH, (
        f"AC-12: Telegram rich muss SEINE Wahl (Einfach = {_EINFACH!r}) zeigen, "
        f"nicht die der E-Mail (Roh). Zellen: {z}"
    )


def test_ac12_email_einfach_telegram_roh(monkeypatch):
    """AC-12 (Gegenrichtung): E-Mail "Einfach", Telegram "Roh" -> E-Mail zeigt das
    Emoji-Band, Telegram rich die Zahl."""
    _, _, z = _zellen(monkeypatch, email_einfach=True, telegram_einfach=False)
    assert z["email_plain"] == _EINFACH and z["email_html"] == _EINFACH, f"E-Mail Einfach: {z}"
    assert z["telegram_rich"] == _ROH, (
        f"AC-12: Telegram rich muss SEINE Wahl (Roh = {_ROH!r}) zeigen, nicht die "
        f"der E-Mail (Einfach). Zellen: {z}"
    )


def test_ac12_kurzuebersicht_folgt_derselben_telegram_wahl(monkeypatch):
    """AC-12 (Narrow-Pfad, ``narrow.py`` haengt an derselben Quelle): die
    Kurzuebersicht-Bubble nennt die Gesamtbewoelkung in der Telegram-Wahl, nicht in
    der E-Mail-Wahl -- wo sie auftritt, stimmt sie mit der Tabellenzelle ueberein."""
    for email_einfach, telegram_einfach in ((False, True), (True, False)):
        _, mit, z = _zellen(monkeypatch, email_einfach, telegram_einfach)
        bodies, _ = _kanal_texte(mit, "telegram_rich")
        kurz = _kurzuebersicht_wert(bodies, "CT")
        assert kurz is not None, (
            f"Testaufbau: die Kurzuebersicht fuehrt CT nicht: {bodies!r}"
        )
        assert kurz == z["telegram_rich"], (
            f"AC-12: Kurzuebersicht {kurz!r} weicht von der Telegram-Zelle "
            f"{z['telegram_rich']!r} ab (E-Mail einfach={email_einfach}, "
            f"Telegram einfach={telegram_einfach})"
        )


@pytest.mark.parametrize("email_einfach,telegram_einfach", [(False, True), (True, False)])
def test_ac12_orakel_zelle_roh_einfach_ohne_register_eintrag(
    monkeypatch, email_einfach, telegram_einfach,
):
    """AC-12: die Orakel-Dimension "Modus" (``roh_einfach``) ist fuer Telegram rich
    in BEIDEN Richtungen gruen OHNE Register-Eintrag (B3-Eintrag entfernt)."""
    d, mit, _ = _zellen(monkeypatch, email_einfach, telegram_einfach)
    rot, _ = rote_zellen_fuer_golden(d, mit, [])
    modus_rot = {z for z in rot if z[2] == "roh_einfach"}
    assert modus_rot == set(), (
        f"AC-12: roh_einfach-Zellen ungedeckt rot: {sorted(modus_rot)}"
    )


def test_ac12_guard_gleiche_wahl_in_beiden_kanaelen(monkeypatch):
    """AC-12 (GUARD, heute gruen): dieselbe Wahl in beiden Layouts -> beide Kanaele
    zeigen sie. Diese Gleichheit hat B3 bisher verdeckt."""
    for einfach in (False, True):
        _, _, z = _zellen(monkeypatch, einfach, einfach)
        erwartet = _EINFACH if einfach else _ROH
        assert z["email_plain"] == erwartet and z["telegram_rich"] == erwartet, z
