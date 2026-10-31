"""Abweichungs- und Radar-Alarme zweisprachig (Issue #2667, Epic #2644).

SPEC: docs/specs/modules/i18n_p5_abweichungs_radar_alarme_2667.md (AC-1, AC-3,
AC-4, AC-7; Ratsche verhaltensbasiert, Zwei-Nutzer-Test).

Echter Renderer (``render_subject``/``render_email``/``render_telegram``/
``render_sms``) auf der deterministischen Fixture ``tests.helpers.alarm_fixture``.
Erwartete Texte kommen aus dem Katalog (``t``/``tn``), dem Metrik-Register und
``fmt_weekday`` -- keine getippten Nutzertexte. PO-Korrektur 2026-10-31: die
SMS (und damit Premium-SMS und Telegram-Kurzstil) ist in jeder Sprache
byte-gleich zur deutschen. Kern-Schicht, kein Netz.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.metric_catalog import format_metric_value, get_alert_label, get_metric
from i18n import fmt_weekday, resolve_user_lang, t, tn
from tests.helpers.alarm_fixture import (
    FAELLE, JETZT, TRENNER, TZ, _gust, _verschiebung, golden_pfad, nachricht, render_fall,
)

KATALOG = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"
LANGFORM = ("betreff", "html", "klartext", "telegram")


def _deutsche_fragmente() -> set[str]:
    """Feste Textstuecke der deutschen ``alarm.*``-Texte, die der englische
    Text desselben Schluessels nicht enthaelt (z. B. 'stärkste Stunde')."""
    de = json.loads((KATALOG / "de" / "alarm.json").read_text(encoding="utf-8"))
    en = json.loads((KATALOG / "en" / "alarm.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for key, wert in de.items():
        for teil in re.split(r"\{[a-z_]+\}", wert):
            teil = teil.strip(" :·~().,")
            if len(teil) >= 4 and teil not in en[key]:
                out.add(teil)
    return out


def deutsch_treffer(text: str) -> list[str]:
    """Umlaute/ß und deutsche Katalog-Bruchstuecke im Text (Ratsche)."""
    treffer = re.findall(r"\w*[äöüÄÖÜß]\w*", text)
    return treffer + [f for f in _deutsche_fragmente() if re.search(rf"(?<!\w){re.escape(f)}(?!\w)", text)]


def _golden_sms(fall: str) -> str:
    text = golden_pfad(fall, "de", "txt").read_text(encoding="utf-8")
    return text.split(TRENNER % "sms", 1)[1]


# --------------------------------------------------------------------------- #
# Ratsche (verhaltensbasiert): englische Langform ohne deutschen Katalogtext
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fall", FAELLE)
@pytest.mark.parametrize("kanal", LANGFORM)
def test_ratsche_englische_langform_ohne_deutsch(fall, kanal):
    assert deutsch_treffer(render_fall(fall, "en")[kanal]) == []


@pytest.mark.parametrize("fall", FAELLE)
def test_ratsche_gegenprobe_deutsch_wird_erkannt(fall):
    k = render_fall(fall, "de")
    assert any(deutsch_treffer(k[kanal]) for kanal in LANGFORM)


# --------------------------------------------------------------------------- #
# AC-1: Abweichungs-Alarm Böen englisch
# --------------------------------------------------------------------------- #
def test_ac1_abweichung_boeen_englisch():
    k = render_fall("abweichung_wind", "en")
    gusts = get_metric("gust").alert_label_for("en")
    for kanal in LANGFORM:
        assert gusts in k[kanal], kanal
    erwartet_h1 = t("alarm.abweichung.h1", "en", label=gusts,
                    von=format_metric_value("km/h", 45, lang="en"),
                    bis=format_metric_value("km/h", 72, lang="en"))
    assert k["klartext"].splitlines()[0] == erwartet_h1
    morgen = t("alarm.abweichung.staerkste_stunde", "en",
               zeit=t("alarm.zeit.morgen", "en", zeit="15:00"))
    assert morgen in k["klartext"] and morgen in k["telegram"]
    referenz = t("alarm.zeit.gestern_uhr", "en", zeit="17:03")
    assert t("alarm.mail.verglichen", "en", referenz=referenz) in k["telegram"]
    assert t("alarm.abweichung.urteil", "en", pfeil="↑", seite=t("alarm.abweichung.ueber", "en"),
             schwelle=format_metric_value("km/h", 20, lang="en")) in k["klartext"]
    assert t("alarm.abweichung.betroffen", "en", von="13:00", bis="18:00") in k["html"]
    assert t("mail.herkunft.abweichungs_alarm", "en") in k["klartext"]


def test_ac1_wochentag_der_langform_englisch():
    """Die Langform nennt den Wochentag nur jenseits der Guete-Grenze
    ('ab Fr15:40'); dort steht er in der Nutzersprache."""
    freitag = date(2026, 10, 30)
    for lang in ("de", "en"):
        k = render_fall("regen_spaet", lang)
        ab = t("alarm.zeit.ab", lang, zeit=f"{fmt_weekday(freitag, lang)}15:40")
        kopf = f"{t('alarm.radar.intensitaet.gewitter', lang)} {ab}"
        assert kopf in k["betreff"] and kopf in k["telegram"]
        assert k["klartext"].splitlines()[0] == kopf


def test_ac1_mehrfach_englisch_mit_zahlenformat():
    k = render_fall("abweichung_mehrfach", "en")
    assert t("alarm.abweichung.h1_mehrere", "en", n=5) == k["klartext"].splitlines()[0]
    assert f"↑ {t('alarm.abweichung.ueber_schwelle', 'en', n=4)}" in k["klartext"]
    assert f"↑ {t('alarm.abweichung.ueber_schwelle', 'en', n=4)}: " in k["betreff"]
    assert "2,400 ↓ 1,850 m" in k["klartext"] and "4→12.5 mm" in k["telegram"]
    assert "2.400 ↓ 1.850 m" in render_fall("abweichung_mehrfach", "de")["klartext"]
    stufen = f"{t('alarm.abweichung.aenderung', 'en', wert='2 ' + tn('alarm.einheit.stufe', 2, 'en'))}"
    assert stufen in k["klartext"]
    assert t("alarm.abweichung.schwelle", "en", wert="1 " + tn("alarm.einheit.stufe", 1, "en")) in k["klartext"]
    assert f"{get_alert_label('temperature', 'en')} · 🏁 {t('alarm.segment.ziel', 'en')}" in k["klartext"]
    assert t("alarm.abweichung.unter_schwelle", "en") in k["html"]
    vor = t("alarm.zeit.war", "en", zeit=t("alarm.zeit.vor_tagen", "en", n=3, zeit="12:00"))
    assert vor in k["klartext"] and t("alarm.zeit.in_tagen", "en", n=2, zeit="09:00") in k["telegram"]
    assert t("alarm.abweichung.mehr_regen", "en") in k["telegram"]
    assert f"{t('alarm.abweichung.luftmasse', 'en')}" not in k["klartext"]


def test_mehrfach_unter_schwelle_englisch_ohne_treffer():
    msg = nachricht("abweichung_mehrfach", "en")
    from output.renderers.alert.render import render_email, render_subject, render_telegram

    leise = replace(msg, events=tuple(replace(e, threshold=10_000.0) for e in msg.events),
                    onset_shift_events=())
    erwartet = t("alarm.abweichung.aenderungen", "en", n=5)
    assert erwartet in render_subject(leise, lang="en")
    assert erwartet in render_telegram(leise, lang="en")
    assert erwartet in render_email(leise, lang="en")[1]


def test_luftmasse_englisch():
    from output.renderers.alert.model import AlertMessage
    from output.renderers.alert.render import render_subject

    e = _gust(metric_id="thunder", value_from=0.0, value_to=1.0, threshold=1.0)
    msg = AlertMessage(trip_short="T", stand_at="06:00", events=(e,))
    assert t("alarm.abweichung.luftmasse", "en") in render_subject(msg, lang="en")


def test_niederschlag_zeilen_englisch_alle_zweige():
    from output.renderers.alert.model import AlertMessage
    from output.renderers.alert.render import render_email, render_telegram

    regen = nachricht("abweichung_mehrfach", "en").events[1]
    faelle = {
        "noch": regen,
        "fensterende": replace(regen, remaining_until_time=None, window_end_time="21:00",
                               window_end_day_offset=1),
        "kein_weiterer": replace(regen, remaining_until_time=None),
    }
    for key, e in faelle.items():
        msg = AlertMessage(trip_short="T", stand_at="06:00", events=(e,))
        plain = render_email(msg, lang="en")[1]
        assert t("alarm.niederschlag.bis_jetzt", "en") in plain
        assert t("alarm.niederschlag.ab_jetzt", "en") in render_telegram(msg, lang="en")
        assert t("alarm.niederschlag.gefallen", "en", mm="6", angekuendigt="4") in plain
        zeit = {"noch": t("alarm.zeit.morgen", "en", zeit="20:00"),
                "fensterende": t("alarm.zeit.morgen", "en", zeit="21:00")}.get(key)
        assert t(f"alarm.niederschlag.{key}", "en", mm="6", zeit=zeit or "") in plain, key
        assert deutsch_treffer(plain) == []


def test_tagesworte_gestern_und_seit_englisch():
    from output.renderers.alert.model import AlertMessage
    from output.renderers.alert.render import render_email, render_telegram

    e = _gust(occurred_day_offset=-1, occurred_is_past=True)
    msg = AlertMessage(trip_short="T", stand_at="06:00", events=(e,))
    gestern = t("alarm.zeit.war", "en", zeit=t("alarm.zeit.gestern", "en", zeit="15:00"))
    assert gestern in render_email(msg, lang="en")[1]
    oe = replace(_verschiebung(), to_is_past=True)
    nur = AlertMessage(trip_short="T", stand_at="06:00", events=(), onset_shift_events=(oe,))
    assert t("alarm.zeit.seit", "en", zeit="11:30") in render_telegram(nur, lang="en")


def test_beginn_verschiebung_allein_englisch():
    from output.renderers.alert.model import AlertMessage
    from output.renderers.alert.render import render_email, render_subject, render_telegram

    oe = _verschiebung()
    msg = AlertMessage(trip_short="T", stand_at="06:00", events=(), onset_shift_events=(oe,))
    label = get_alert_label("precipitation", "en")
    frueher = t("alarm.beginn.frueher", "en", betrag="2.5")
    html, plain = render_email(msg, lang="en")
    assert plain.splitlines()[0] == t("alarm.beginn.verschiebt", "en", label=label)
    zeile = f"{t('alarm.beginn.label', 'en', label=label)}: 14:00 → 11:30 ({frueher} · Segment 3)"
    assert zeile in plain and zeile in render_telegram(msg, lang="en")
    assert f"{t('alarm.beginn.label', 'en', label=label)} · Segment 3" in html
    assert f"({frueher})" in html and t("alarm.mail.stand", "en", stand="06:00") in plain
    assert render_subject(msg, lang="en") == (
        f"[T] Segment 3 · {t('alarm.beginn.label', 'en', label=label)} 11:30 ({frueher})")
    zwei = replace(msg, onset_shift_events=(oe, oe))
    assert t("alarm.beginn.mehrere", "en", n=2) in render_telegram(zwei, lang="en")
    spaeter = replace(oe, shift_seconds=7200.0)
    assert t("alarm.beginn.spaeter", "en", betrag="2") in render_telegram(
        replace(msg, onset_shift_events=(spaeter,)), lang="en")
    for text in (html, plain, render_subject(msg, lang="en"), render_telegram(msg, lang="en")):
        assert deutsch_treffer(text) == []


# --------------------------------------------------------------------------- #
# AC-3: Regen-Alarm englisch (Cooldown-Plural, Intensitaet, Buendel)
# --------------------------------------------------------------------------- #
def _cooldown(dauer: str) -> str:
    return t("alarm.regen.cooldown", "en", praefix=t("alarm.radar.cooldown_praefix", "en"), dauer=dauer)


@pytest.mark.parametrize("fall, dauer", [
    ("regen_spaet", tn("alarm.dauer.stunden", 1, "en")),
    ("regen_einzel", tn("alarm.dauer.stunden", 2, "en")),
    ("regen_buendel", t("alarm.dauer.minuten", "en", count=90)),
])
def test_ac3_cooldown_satz_englisch(fall, dauer):
    k = render_fall(fall, "en")
    assert _cooldown(dauer) in k["klartext"] and _cooldown(dauer) in k["html"]


def test_ac3_cooldown_plural_formen():
    from services.compare_radar_alert import _format_cooldown_display
    from services.radar_alert_service import cooldown_text

    assert cooldown_text(60, lang="en") == tn("alarm.dauer.stunden", 1, "en") != tn("alarm.dauer.stunden", 2, "en")
    assert cooldown_text(120, lang="en") == tn("alarm.dauer.stunden", 2, "en")
    assert cooldown_text(90, lang="en") == t("alarm.dauer.minuten", "en", count=90)
    assert _format_cooldown_display(120, lang="en") == tn("alarm.dauer.stunden", 2, "en")
    assert _format_cooldown_display(120) == "2 Stunden" and cooldown_text(60) == "1 Stunde"


def test_ac3_intensitaet_und_buendel_englisch():
    from services.radar_service import INTENSITY_HEAVY, INTENSITY_MODERATE, intensity_text

    k = render_fall("regen_einzel", "en")
    stark = intensity_text(INTENSITY_HEAVY, "en")
    assert stark == t("alarm.radar.intensitaet.stark", "en") != INTENSITY_HEAVY
    assert f"{t('alarm.mail.intensitaet', 'en')}: {stark}" in k["klartext"]
    assert stark in k["telegram"] and t("alarm.regen.badge", "en") in k["html"]
    assert t("alarm.zeit.in_minuten", "en", min=25) in k["betreff"]
    zeiten = {"mindestens_bis": t("alarm.zeit.morgen", "en", zeit="00:40"),
              "reichweite": "08:55", "unscharf": "07:30"}
    for key, zeit in zeiten.items():
        assert t(f"alarm.regen.{key}", "en", zeit=zeit) in k["telegram"], key
    assert t("alarm.regen.nass", "en", spannen="km 2-4, km 9-11") in k["telegram"]
    assert t("alarm.regen.luecke", "en") in k["klartext"] and t("alarm.regen.ungeprueft", "en") in k["betreff"]
    b = render_fall("regen_buendel", "en")
    assert b["betreff"] == f"[Innsbruck, Lienz] {t('alarm.regen.buendel', 'en', n=2)}"
    assert b["klartext"].splitlines()[0] == t("alarm.regen.buendel", "en", n=2)
    assert intensity_text(INTENSITY_MODERATE, "en") in b["klartext"]
    assert t("alarm.regen.gewitter_hagel", "en") in b["html"]
    assert f"{t('alarm.regen.laeuft', 'en')}: {t('alarm.regen.laeuft', 'en')}" in b["klartext"]
    assert t("alarm.mail.quelle", "en", quelle="INCA, Radar (DWD)") in b["klartext"]
    assert t("alarm.regen.letzter", "en", zeit="07:40") in b["telegram"]


def test_ac3_nachtrag_und_quelle_englisch():
    k = render_fall("nachtrag", "en")
    assert t("alarm.nachtrag.amtlich", "en") in k["telegram"]
    assert f"{t('alarm.mail.quelle_label', 'en')}: Radar (DWD)" in k["klartext"]
    assert f"{t('alarm.mail.wo_wann', 'en')}: 🏁 {t('alarm.segment.ziel', 'en')} · " \
           f"{t('alarm.zeit.ab', 'en', zeit='06:25')}" in k["klartext"]
    assert t("mail.herkunft.radar_alarm", "en") in k["klartext"]


def test_briefing_kontext_zeile_englisch():
    from output.renderers.alert.render import render_email

    msg = nachricht("nachtrag", "en")
    msg = replace(msg, events=(replace(msg.events[0], briefing_context="E3 07:00"),))
    assert f"{t('alarm.mail.briefing', 'en')}: E3 07:00" in render_email(msg, lang="en")[1]


# --------------------------------------------------------------------------- #
# AC-4 (PO-Korrektur 2026-10-31): SMS in jeder Sprache byte-gleich
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fall", FAELLE)
def test_ac4_sms_in_jeder_sprache_byte_gleich(fall):
    golden = _golden_sms(fall)
    for lang in (None, "de", "en"):
        sms = render_fall(fall, lang)["sms"]
        assert sms.encode("utf-8") == golden.encode("utf-8")
        assert len(sms) <= 140


@pytest.mark.parametrize("limit", [140, 60, 30])
def test_ac4_sms_gekuerzt_unabhaengig_von_der_sprache(limit):
    from output.renderers.alert.render import render_sms

    for fall in FAELLE:
        de, en = render_sms(nachricht(fall, None), limit=limit), render_sms(nachricht(fall, "en"), limit=limit)
        assert de == en and len(en) <= limit


def test_ac4_render_sms_kennt_keine_sprache():
    from output.renderers.alert.render import render_sms

    with pytest.raises(TypeError):
        render_sms(nachricht("abweichung_wind", "en"), lang="en")


# --------------------------------------------------------------------------- #
# AC-7: kein Zustand zwischen Nutzern; Zwei-Nutzer-Test
# --------------------------------------------------------------------------- #
def _golden(fall: str, lang: str) -> tuple[bytes, bytes]:
    from tests.helpers.alarm_fixture import als_text

    k = render_fall(fall, lang)
    return k["html"].encode(), als_text(k).encode()


@pytest.mark.parametrize("fall", FAELLE)
def test_ac7_reihenfolge_en_de_en(fall):
    soll = {lang: (golden_pfad(fall, lang, "html").read_bytes(),
                   golden_pfad(fall, lang, "txt").read_bytes()) for lang in ("de", "en")}
    for lang in ("en", "de", "en"):
        assert _golden(fall, lang) == soll[lang]


def test_zwei_nutzer_eigene_sprache(tmp_path):
    for uid, sprache in (("nutzer-en", "en"), ("nutzer-de", "de")):
        (tmp_path / "users" / uid).mkdir(parents=True)
        (tmp_path / "users" / uid / "user.json").write_text(json.dumps({"language": sprache}))
    for uid in ("nutzer-en", "nutzer-de", "nutzer-en"):
        lang = resolve_user_lang(uid, data_dir=tmp_path)
        k = render_fall("abweichung_wind", lang)
        assert k["html"].encode() == golden_pfad("abweichung_wind", lang, "html").read_bytes()
        assert (deutsch_treffer(k["klartext"]) == []) is (uid == "nutzer-en")


# --------------------------------------------------------------------------- #
# Geteilte Bausteine: Default de byte-gleich, en mit englischer Form
# --------------------------------------------------------------------------- #
def test_format_metric_value_englisch_und_deutsch():
    assert format_metric_value("m", 12240) == "12.240 m"
    assert format_metric_value("m", 12240, lang="en") == "12,240 m"
    assert format_metric_value("mm", 1.5) == "1,5 mm"
    assert format_metric_value("mm", 1.5, lang="en") == "1.5 mm"
    assert format_metric_value("°C", -2.5, signed=True, lang="en") == "−2.5 °C"
    assert format_metric_value("km/h", 72, lang="en") == "72 km/h"


def test_format_reference_at_englisch():
    from utils.timezone import format_reference_at

    vorgestern = datetime(2026, 10, 26, 16, 3, tzinfo=timezone.utc)
    assert format_reference_at(vorgestern, TZ, now=JETZT, lang="en") == t(
        "alarm.zeit.vor_tagen_uhr", "en", n=3, zeit="17:03")
    assert format_reference_at(vorgestern, TZ, now=JETZT) == "vor 3 Tagen 17:03 Uhr"
    heute = datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc)
    assert format_reference_at(heute, TZ, now=JETZT, lang="en") == "04:00"


def test_segment_bezug_englisch():
    from output.renderers.alert.segments import format_alert_location, format_segment_reference

    assert format_segment_reference(["1", "2", "3", "4", "5"], lang="en") == t("alarm.segment.anzahl", "en", n=5)
    assert format_segment_reference(["1", "2", "3", "4", "5"]) == "5 Segmente"
    assert format_segment_reference(["2", "Ziel"], lang="en") == (
        f"{t('alarm.segment.liste', 'en', liste='2')}, 🏁 {t('alarm.segment.ziel', 'en')}")
    assert format_alert_location(None, ["Ziel"], 0, 0, lang="en") == f"🏁 {t('alarm.segment.ziel', 'en')}"
    assert format_alert_location(None, ["Ziel"], 0, 0) == "🏁 Ziel"


def test_legacy_abweichung_englisch():
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.render import render_deviation_alert

    ch = WeatherChange(metric="temp_max_c", old_value=18.0, new_value=28.5, delta=10.5,
                       threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
                       segment_id="1")
    html, plain = render_deviation_alert([ch], [], "GR20", tz=TZ, sent_at=JETZT, lang="en")
    assert plain.splitlines()[0] == t("alarm.abweichung.legacy_kopf", "en")
    assert t("alarm.mail.verglichen", "en", referenz=t("alarm.mail.letztes_briefing", "en")) in plain
    assert "28.5 °C" in plain and t("alarm.abweichung.legacy_kopf", "en") in html
    _h, plain_de = render_deviation_alert([ch], [], "GR20", tz=TZ, sent_at=JETZT)
    assert "28,5 °C" in plain_de and plain_de.splitlines()[0] == t("alarm.abweichung.legacy_kopf", "de")


def test_legacy_abweichung_englisch_stand_und_alter_wert():
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.render import render_deviation_alert
    from utils.timezone import local_fmt

    ch = WeatherChange(metric="temp_max_c", old_value=18.5, new_value=28.5, delta=10.0,
                       threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
                       segment_id="1")
    _html, plain = render_deviation_alert([ch], [], "GR20", tz=TZ, sent_at=JETZT, lang="en")
    assert t("alarm.mail.stand", "en", stand=local_fmt(JETZT, TZ)) in plain
    assert "18.5 °C" in plain


# --------------------------------------------------------------------------- #
# Mutations-Gegenprobe: Werte, deren de/en-Form sich unterscheidet
# (Dezimalkomma, Stufenwort, Ziel, Tagesbezug), an JEDER Ausgabestelle
# --------------------------------------------------------------------------- #
def _einzel(**extra):
    from output.renderers.alert.model import AlertMessage

    return AlertMessage(trip_short="T", stand_at="06:00", events=(_gust(**extra),))


def _alle_langform(msg) -> dict[str, str]:
    from output.renderers.alert.render import render_email, render_subject, render_telegram

    html, plain = render_email(msg, lang="en")
    return {"betreff": render_subject(msg, lang="en"), "html": html, "klartext": plain,
            "telegram": render_telegram(msg, lang="en")}


def _gewitter_wort(stufe: str) -> str:
    from app.models import ThunderLevel
    from app.thunder_scale import THUNDER_LABEL_EN

    return THUNDER_LABEL_EN[ThunderLevel[stufe]]


def _hagel(lang: str) -> str:
    from app.thunder_scale import format_hail_note

    return format_hail_note(True, lang=lang)


def test_einzelwert_mit_dezimalen_englisch_an_jeder_stelle():
    msg = _einzel(metric_id="precipitation", value_from=4.5, value_to=12.5, threshold=5.5,
                  hours=(), hours_range=None)
    k = _alle_langform(msg)
    von, bis = format_metric_value("mm", 4.5, lang="en"), format_metric_value("mm", 12.5, lang="en")
    schwelle = format_metric_value("mm", 5.5, lang="en")
    label = get_alert_label("precipitation", "en")
    assert k["betreff"].endswith(f"{label}: {von}→{bis}")
    assert k["klartext"].splitlines()[0] == t("alarm.abweichung.h1", "en", label=label, von=von, bis=bis)
    assert f"{label} · {t('alarm.abweichung.schwelle', 'en', wert=schwelle)} · {von} ↑ {bis} · " in k["telegram"]
    assert f"{label} · mm: {von} ↑ {bis}" in k["klartext"]
    assert t("alarm.abweichung.aenderung", "en", wert=format_metric_value("mm", 8.0, lang="en")) in k["klartext"]
    assert t("alarm.abweichung.seite_schwelle", "en", seite=t("alarm.abweichung.ueber", "en"),
             schwelle=schwelle, mark="✗") in k["html"]
    assert f"({schwelle})" in k["klartext"]
    for text in k.values():
        assert not re.search(r"\d,\d", text), text


def test_einzelwert_stufenmetrik_englisch():
    msg = _einzel(metric_id="thunder", value_from=1.0, value_to=3.0, threshold=1.0, hail_flag=True,
                  hours=(), hours_range=None)
    k = _alle_langform(msg)
    leicht, hoch = _gewitter_wort("LOW"), _gewitter_wort("HIGH")
    assert f"{leicht} ↑ {hoch} · {_hagel('en')}" in k["telegram"]
    assert f"{leicht} ↑ {hoch} · {_hagel('en')}" in k["klartext"]
    assert f"{leicht}→{hoch}" in k["betreff"]
    stufe = "1 " + tn("alarm.einheit.stufe", 1, "en")
    assert f"({stufe})" in k["klartext"] and t("alarm.abweichung.schwelle", "en", wert=stufe) in k["telegram"]
    assert t("alarm.abweichung.aenderung", "en", wert="2 " + tn("alarm.einheit.stufe", 2, "en")) in k["html"]
    for text in k.values():
        assert deutsch_treffer(text) == []


def test_mehrfach_unter_schwelle_zeilen_englisch():
    from output.renderers.alert.model import AlertMessage

    ohne = dict(hours=(), hours_range=None)
    evs = (
        _gust(),
        _gust(value_from=50.0, value_to=55.0, threshold=20.0, segment_id="4"),
        _gust(metric_id="precipitation", value_from=4.5, value_to=5.5, threshold=5.0, **ohne),
        _gust(metric_id="thunder", value_from=1.0, value_to=2.0, threshold=2.0, hail_flag=True, **ohne),
        _gust(metric_id="precipitation", value_from=1.0, value_to=9.0, threshold=2.5, **ohne),
    )
    k = _alle_langform(AlertMessage(trip_short="T", stand_at="06:00", events=evs))
    unter = t("alarm.abweichung.unter_schwelle", "en")
    assert f"{get_alert_label('gust', 'en')} · Segment 4 · " in k["klartext"]
    assert f"· {unter}: 50 → 55 km/h" in k["klartext"]
    assert "4.5 → 5.5 mm" in k["klartext"]
    assert f"→ {_gewitter_wort('MED')} · {_hagel('en')}" in k["klartext"]
    assert t("alarm.abweichung.schwelle", "en", wert="2.5") in k["klartext"]
    for text in k.values():
        assert deutsch_treffer(text) == []


def test_beginn_verschiebung_am_ziel_morgen_englisch():
    from output.renderers.alert.model import AlertMessage

    oe = replace(_verschiebung(), segment_id="Ziel", to_day_offset=1)
    ziel = f"🏁 {t('alarm.segment.ziel', 'en')}"
    morgen = t("alarm.zeit.morgen", "en", zeit="11:30")
    label = t("alarm.beginn.label", "en", label=get_alert_label("precipitation", "en"))
    frueher = t("alarm.beginn.frueher", "en", betrag="2.5")
    zeile = f"{label}: 14:00 → {morgen} ({frueher} · {ziel})"
    for evs in ((), (_gust(),)):
        k = _alle_langform(AlertMessage(trip_short="T", stand_at="06:00", events=evs,
                                        onset_shift_events=(oe,)))
        assert zeile in k["klartext"] and zeile in k["telegram"]
        assert f"{label} · {ziel}" in k["html"] and f"14:00 → {morgen} ({frueher})" in k["html"]
        assert t("mail.herkunft.abweichungs_alarm", "en") in k["klartext"]
        for text in k.values():
            assert deutsch_treffer(text) == []
    nur = _alle_langform(AlertMessage(trip_short="T", stand_at="06:00", events=(), onset_shift_events=(oe,)))
    assert nur["betreff"] == f"[T] {ziel} · {label} 11:30 ({frueher})"


def test_radar_reichweite_und_unschaerfe_morgen_englisch():
    basis = nachricht("regen_einzel", "en")
    e = replace(basis.events[0], source_reach_day_offset=1, location_sharpness_limit_day_offset=1)
    k = _alle_langform(replace(basis, events=(e,)))
    for kanal in LANGFORM:
        assert t("alarm.regen.reichweite", "en", zeit=t("alarm.zeit.morgen", "en", zeit="08:55")) in k[kanal]
        assert t("alarm.regen.unscharf", "en", zeit=t("alarm.zeit.morgen", "en", zeit="07:30")) in k[kanal]
