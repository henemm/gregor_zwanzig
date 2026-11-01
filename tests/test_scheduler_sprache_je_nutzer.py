"""Sprache je Nutzer im selben Lauf (Issue #2672, AC-1, AC-2, AC-5).

SPEC: docs/specs/modules/i18n_p9b_scheduler_orchestrierung_2672.md

Zwei Nutzer, ``de`` und ``en``, im SELBEN Prozess: jede Dienstinstanz liest die
Sprache ihres Nutzers aus ``user.json`` (``resolve_user_lang``) und haelt sie
als Attribut. Geprueft wird am Draht (``KanalRig``) bzw. an der
``mail_sink``-Naht des Alarmdienstes -- Erwartungen aus dem Katalog, kein
Spiegel der Sprache. PO-Korrektur 2026-10-31: SMS bleibt in jeder Sprache
byte-gleich.
"""
from __future__ import annotations

import json

import pytest
from freezegun import freeze_time

from i18n import t, tn
from i18n.format import fmt_date_numeric
from tests.helpers import scheduler_sprache_fixture as fx
from tests.helpers.versand_fixture import rig_starten


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _teilausfall_hinweis(lang: str) -> str:
    ziel = t("versand.scheduler.abschnitt", lang, id=t("alarm.segment.ziel", lang))
    return t("versand.scheduler.teilausfall", lang, abschnitte=ziel)


def _briefing(rig, svc, trip) -> dict:
    rig.zaehler_leeren()
    assert svc._send_trip_report_outcome(trip, "morning") == "sent"
    return fx.kanaele(rig)


def test_ac1_zwei_nutzer_im_selben_lauf_reihenfolge_de_en_de(rig, monkeypatch, tmp_path):
    """AC-1: beide Dienstobjekte existieren gleichzeitig; bedient werden
    ``de``, ``en``, ``de``. Jede Mail traegt Hinweis, Betreff-Typwort und
    ``X-GZ-Lang`` ihres Nutzers; der zweite ``de``-Lauf ist byte-gleich zum
    ersten (kein Zustand wandert vom ``en``-Nutzer herueber)."""
    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen("golden-de", "de")
        fx.nutzer_anlegen("golden-en", "en")
        trips = {u: fx.trip_anlegen(u, [fx.INNSBRUCK, fx.INNSBRUCK, fx.STUBAI])
                 for u in ("golden-de", "golden-en")}
        fx.wetter(monkeypatch, tmp_path, "teil")
        dienste = {u: fx.scheduler(rig, u) for u in trips}
        laeufe = [(u, _briefing(rig, dienste[u], trips[u]))
                  for u in ("golden-de", "golden-en", "golden-de")]
    for user_id, k in laeufe:
        lang = user_id.removeprefix("golden-")
        assert k["mail"]["lang"] == lang
        assert k["mail"]["plain"].startswith(_teilausfall_hinweis(lang) + "\n\n")
        assert k["telegram"][0].startswith(_teilausfall_hinweis(lang) + "\n\n")
        assert k["mail"]["betreff"].endswith(" — " + ("Morgen" if lang == "de" else "Morning"))
    (_, de1), (_, en), (_, de2) = laeufe
    assert de1 == de2
    assert en["sms"] == de1["sms"], "PO-Korrektur 2026-10-31: SMS in en byte-gleich de"


def test_ac1_sprache_wird_je_dienstobjekt_gelesen_nicht_global(rig, monkeypatch, tmp_path):
    """Die Sprache gilt ab dem naechsten Dienstobjekt (Known Limitation):
    aendert der Nutzer sie nach dem Bau, spricht das laufende Objekt weiter
    seine Sprache, ein neues die neue -- kein Modul-/Prozesszustand."""
    from app.loader import get_data_dir

    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen("golden-en", "en")
        trip = fx.trip_anlegen("golden-en", [fx.INNSBRUCK, fx.INNSBRUCK, fx.STUBAI])
        fx.wetter(monkeypatch, tmp_path, "teil")
        alt = fx.scheduler(rig, "golden-en")
        pfad = get_data_dir("golden-en") / "user.json"
        profil = json.loads(pfad.read_text())
        profil["language"] = "de"
        pfad.write_text(json.dumps(profil))
        laufend = _briefing(rig, alt, trip)
        neu = _briefing(rig, fx.scheduler(rig, "golden-en"), trip)
    assert laufend["mail"]["lang"] == "en"
    assert laufend["mail"]["plain"].startswith(_teilausfall_hinweis("en"))
    assert neu["mail"]["lang"] == "de"
    assert neu["mail"]["plain"].startswith(_teilausfall_hinweis("de"))


@pytest.mark.parametrize("stil", [None, "kurzform"])
def test_ac2_ortsvergleich_zwei_nutzer(rig, monkeypatch, stil):
    """AC-2: Betreff, Mail, Telegram und Kopf je in der Sprache des Nutzers,
    SMS (und Telegram-Kurzform = SMS-Text) in beiden Sprachen byte-gleich."""
    with freeze_time(fx.JETZT):
        fx.vergleich_engine(monkeypatch)
        ergebnis = {}
        for lang in ("de", "en", "de"):
            fx.nutzer_anlegen(f"golden-{lang}", lang)
            ergebnis.setdefault(lang, []).append(
                fx.vergleich_senden(rig, f"golden-{lang}", telegram_stil=stil))
    for lang, laeufe in ergebnis.items():
        k = laeufe[0]
        assert k["mail"]["betreff"] == t("versand.scheduler.vergleich_betreff", lang,
                                         name="Tirol", datum=fmt_date_numeric(fx.TAG, lang))
        assert k["mail"]["lang"] == lang
        assert k["mail"]["plain"].startswith(t("vergleich.kopf.titel", lang) + "\n")
        if stil is None:
            assert k["telegram"][0].startswith(t("vergleich.kopf.titel", lang) + " — Tirol")
    assert ergebnis["de"][0] == ergebnis["de"][1]
    assert ergebnis["en"][0]["sms"] == ergebnis["de"][0]["sms"]
    if stil == "kurzform":
        assert ergebnis["en"][0]["telegram"] == ergebnis["de"][0]["telegram"]


def test_ac2_nachgeholter_ortsvergleich_spricht_die_nutzersprache(rig, monkeypatch):
    """Nachholversand ueber die echte Nachhol-Schleife: Hinweis und Kopf in
    der Sprache des Nutzers (Sprache einmal je Nutzer und Lauf)."""
    with freeze_time(fx.JETZT):
        fx.vergleich_engine(monkeypatch)
        for lang in ("en", "de"):
            fx.nutzer_anlegen(f"golden-{lang}", lang)
            k = fx.vergleich_senden(rig, f"golden-{lang}", catchup=True)
            hinweis = t("versand.scheduler.zustellung_fehlgeschlagen", lang, stunde="06:00")
            assert k["mail"]["lang"] == lang
            assert k["mail"]["plain"].startswith(hinweis + "\n\n")
            assert k["telegram"][0].startswith(hinweis + "\n\n")


def _rumpf(paare: list) -> str:
    werte = dict(paare)
    assert werte["alarm.gesendet"] == "1", werte
    return werte["alarm.0.rumpf"]


@pytest.mark.parametrize("cooldown,dauer", [(120, ("stunden", 2)), (90, ("minuten", 90))])
def test_ac5_radar_alarm_englisch_bestandsnutzer_deutsch(cooldown, dauer):
    """AC-5: Cooldown-Satz, Nachtrag-Bezug und Briefing-Kontext englisch;
    ein Nutzer OHNE ``language`` bekommt im selben Lauf Deutsch, byte-gleich
    zu einem ausdruecklich deutschen Nutzer."""
    with freeze_time(fx.ALARM_JETZT):
        en = _rumpf(fx.radar_alarm("alarm-en", "en", cooldown=cooldown))
        alt = _rumpf(fx.radar_alarm("alarm-alt", None, cooldown=cooldown))
        de = _rumpf(fx.radar_alarm("alarm-de", "de", cooldown=cooldown))
    for lang, text in (("en", en), ("de", de)):
        satz = t("alarm.regen.cooldown", lang, praefix=t("alarm.radar.cooldown_praefix", lang),
                 dauer=tn(f"alarm.dauer.{dauer[0]}", dauer[1], lang))
        assert satz in text
        bezug = t("alarm.nachtrag.amtlich", lang) + t("alarm.nachtrag.von", lang, zeit="11:35")
        assert f"\n{bezug}\n" in text
        kontext = t("alarm.kontext.nicht_angekuendigt", lang)
        assert f"{t('alarm.mail.briefing', lang)}: {kontext}\n" in text
        assert f"{t('alarm.radar.intensitaet.gewitter', lang).lower()}\n" in text
    assert alt == de
    assert "Cooldown: Du erhältst" not in en and "Ergänzung" not in en


def test_ac5_angekuendigter_konvektiver_alarm_nennt_den_kontext():
    """Briefing hatte Regen angekuendigt, Radar meldet Gewitter: dritter
    Zustand „bereits angekuendigt — jetzt akut“ in der Nutzersprache."""
    with freeze_time(fx.ALARM_JETZT):
        texte = {lang: _rumpf(fx.radar_alarm(f"alarm-akut-{lang}", lang, angekuendigt=True))
                 for lang in ("de", "en")}
    for lang, text in texte.items():
        assert f"{t('alarm.mail.briefing', lang)}: {t('alarm.kontext.akut', lang)}\n" in text
