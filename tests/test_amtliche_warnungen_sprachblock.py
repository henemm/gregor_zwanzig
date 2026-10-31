"""Sprachblock-Wahl der amtlichen Warnungen und Mandantentrennung
(Issue #2668, AC-1, AC-2, AC-6).

SPEC: docs/specs/modules/i18n_p6_amtliche_warnungen_2668.md

Die Warnungen liegen prozessweit im Cache, deshalb faellt die Sprachwahl erst
beim Darstellen: ``_group_and_map_info_entries`` sammelt alle Sprachbloecke,
der Renderer waehlt. Erwartungen kommen aus dem Katalog (``t(key, lang)``).
"""
from __future__ import annotations

import html as _html
import json
import re

from i18n import resolve_user_lang, t
from output.renderers.alert import official_alerts as oa
from services.official_alerts.meteoalarm import _group_and_map_info_entries
from services.official_alerts.meteoalarm_feed import _info_entries_from_alert
from tests.helpers.amtliche_warnungen_fixture import (
    PREFIX, STAND, TZ, meteoalarm_eintraege, meteoalarm_franzoesisch, meteoalarm_gewitter,
)

DE_TEXT, EN_TEXT = "Mäßige Gewitterwarnung", "Moderate thunderstorm warning"


def sichtbar(html: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", "\n", html))


def _notices(alert, lang):
    return oa.build_official_alert_notices(None, [(alert, ["1"])], lang=lang)


def kanaele(alert, lang) -> dict[str, str]:
    """Warnmail (HTML sichtbar + Klartext), Telegram und SMS in ``lang``."""
    notices = _notices(alert, lang)
    quelle = oa.official_alert_source_label(alert.source, lang=lang)
    kw = dict(source_label=quelle, stand_at=STAND, tz=TZ, context_label=PREFIX, lang=lang)
    return {
        "html": sichtbar(oa.render_warn_block(notices, variant="standalone", **kw)),
        "plain": oa.render_official_alert_mail_plain(notices, **kw),
        "telegram": oa.render_official_alert_telegram(
            notices, prefix=PREFIX, source_label=quelle, tz=TZ, lang=lang),
        "subject": oa.render_official_alert_subject(notices, prefix=PREFIX, tz=TZ, lang=lang),
        "sms": oa.render_official_alert_sms(notices, tz=TZ),
    }


def test_gruppierung_sammelt_alle_sprachbloecke_label_bleibt_deutsch():
    alert = meteoalarm_gewitter()
    assert dict(alert.label_by_lang) == {"de": DE_TEXT, "en": EN_TEXT}
    assert alert.label == DE_TEXT and alert.label_lang == "de"


def test_feed_weg_liefert_die_sprache_je_block():
    """JSON-Feed (``meteoalarm_feed``) traegt ``language`` je Info-Block."""
    def info(sprache, text):
        return {"language": sprache, "event": text, "onset": "2026-10-29T10:00:00+00:00",
                "expires": "2026-10-29T19:00:00+00:00",
                "parameter": [{"valueName": "awareness_level", "value": "3; orange; Moderate"},
                              {"valueName": "awareness_type", "value": "3; Thunderstorm"}],
                "area": [{"areaDesc": "Lienz"}]}

    entries = _info_entries_from_alert({"info": [info("it-IT", "Temporali"), info("en-GB", EN_TEXT)]})
    alert = _group_and_map_info_entries(entries)[0]
    assert dict(alert.label_by_lang) == {"it": "Temporali", "en": EN_TEXT}
    assert alert.label == EN_TEXT and alert.label_lang == "en"


def test_erster_block_je_sprache_gewinnt_leerer_zaehlt_nicht():
    alert = _group_and_map_info_entries(meteoalarm_eintraege(
        ("en-GB", ""), ("de-AT", DE_TEXT), ("de-DE", "Gewitter Deutschland"), ("en-US", EN_TEXT),
    ))[0]
    assert dict(alert.label_by_lang) == {"de": DE_TEXT, "en": EN_TEXT}


def test_en_block_ohne_typwort_zeigt_das_typwort():
    """en-Blocktext ohne Gefahrenwort ("Severe weather") -> englisches Typ-Wort."""
    alert = _group_and_map_info_entries(meteoalarm_eintraege(
        ("de-DE", DE_TEXT), ("en-GB", "Severe weather warning")))[0]
    plain = kanaele(alert, "en")["plain"]
    assert "Severe weather warning" not in plain
    assert f"{t('warnung.zeile.gefahr', 'en')}: {t('warnung.gefahr.thunderstorm', 'en')}" in plain


def test_ac1_englisch_rahmen_und_en_block():
    k = kanaele(meteoalarm_gewitter(), "en")
    for kanal in ("html", "plain", "telegram"):
        assert EN_TEXT in k[kanal], kanal
        assert DE_TEXT not in k[kanal], kanal
        assert t("warnung.stufe.orange", "en") in k[kanal], kanal
    assert t("warnung.kopf.warnstufe", "en") in k["telegram"]
    assert t("warnung.kopf.warnstufe", "en") in k["plain"] and t("warnung.kopf.warnstufe", "en") in k["html"]
    for wort in (t("warnung.gueltig", "en"), t("warnung.quelle", "en")):
        assert f"{wort}:" in k["plain"] and wort in k["html"]
    assert EN_TEXT in k["subject"]


def test_ac1_deutsch_waehlt_den_de_block():
    k = kanaele(meteoalarm_gewitter(), "de")
    for kanal in ("html", "plain", "telegram", "subject"):
        assert DE_TEXT in k[kanal] and EN_TEXT not in k[kanal], kanal
    assert t("warnung.kopf.warnstufe", "de") in k["telegram"]


def test_ac1_nur_en_block_in_deutsch_zeigt_das_typwort():
    """Ohne de-Block bleibt Deutsch beim Bestand: englisches Roh-Label -> Typ-Wort."""
    alert = _group_and_map_info_entries(meteoalarm_eintraege(("en-GB", EN_TEXT)))[0]
    k = kanaele(alert, "de")
    assert EN_TEXT not in k["plain"]
    assert f"{t('warnung.zeile.gefahr', 'de')}: {t('warnung.gefahr.thunderstorm', 'de')}" in k["plain"]
    assert EN_TEXT in kanaele(alert, "en")["plain"]


def _hinweis_fr() -> str:
    return t("warnung.hinweis.quelltext_sprache", "en", sprache=t("warnung.sprache.fr", "en"))


def test_ac2_franzoesischer_behoerdentext_mit_hinweis_in_mail_und_telegram():
    k = kanaele(meteoalarm_franzoesisch(), "en")
    hinweis = _hinweis_fr()
    assert hinweis == "Source text in French"
    for kanal in ("html", "plain", "telegram"):
        assert "Orages — Chablais" in k[kanal], kanal
        assert hinweis in k[kanal], kanal
        assert t("warnung.stufe.orange", "en") in k[kanal], kanal
    assert hinweis not in k["sms"] and "Source" not in k["sms"]
    assert k["sms"] == kanaele(meteoalarm_franzoesisch(), "de")["sms"]


def test_ac2_kein_hinweis_wenn_nur_das_typwort_erscheint():
    alert = _group_and_map_info_entries(meteoalarm_eintraege(("fr-FR", "Orages violents")))[0]
    k = kanaele(alert, "en")
    assert "Orages" not in k["plain"]
    assert t("warnung.gefahr.thunderstorm", "en") in k["plain"]
    assert "Source text" not in k["plain"] + k["telegram"] + k["html"]


def test_ac2_hinweis_nennt_unbekannte_sprache_als_code():
    alert = _group_and_map_info_entries(meteoalarm_eintraege(("nl-NL", "Onweer — Zeeland")))[0]
    assert t("warnung.hinweis.quelltext_sprache", "en", sprache="NL") in kanaele(alert, "en")["plain"]


def test_ac2_deutsch_bleibt_ohne_hinweis():
    """Deutsch byte-gleich: kein neuer Hinweis in der deutschen Ausgabe."""
    k = kanaele(meteoalarm_franzoesisch(), "de")
    assert t("warnung.hinweis.quelltext_sprache", "de", sprache=t("warnung.sprache.fr", "de")) not in k["plain"]


def _nutzer(tmp_path, user_id: str, sprache: str) -> None:
    pfad = tmp_path / "users" / user_id
    pfad.mkdir(parents=True)
    (pfad / "user.json").write_text(json.dumps({"id": user_id, "language": sprache}), encoding="utf-8")


def test_ac6_zwei_nutzer_auf_demselben_cache_objekt(tmp_path):
    _nutzer(tmp_path, "golden-en", "en")
    _nutzer(tmp_path, "golden-de", "de")
    cache_alert = meteoalarm_gewitter()  # EIN Objekt, wie im prozessweiten Cache
    vorher = (repr(cache_alert), cache_alert.label, oa.official_alert_state_key(cache_alert))

    ergebnisse = []
    for user_id in ("golden-en", "golden-de", "golden-en"):
        lang = resolve_user_lang(user_id, data_dir=tmp_path)
        ergebnisse.append((lang, kanaele(cache_alert, lang)))

    assert [lang for lang, _ in ergebnisse] == ["en", "de", "en"]
    for lang, k in ergebnisse:
        erwartet, fremd = (EN_TEXT, DE_TEXT) if lang == "en" else (DE_TEXT, EN_TEXT)
        assert erwartet in k["plain"] and fremd not in k["plain"], lang
        assert t("warnung.kopf.warnstufe", lang) in k["telegram"], lang
    assert ergebnisse[0][1] == ergebnisse[2][1]
    assert (repr(cache_alert), cache_alert.label, oa.official_alert_state_key(cache_alert)) == vorher
    assert ergebnisse[0][1]["sms"] == ergebnisse[1][1]["sms"]
