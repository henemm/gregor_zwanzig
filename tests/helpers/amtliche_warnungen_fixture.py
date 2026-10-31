"""Deterministische Fixture der amtlichen Warnungen (Issue #2668, Epic #2644).

SPEC: docs/specs/modules/i18n_p6_amtliche_warnungen_2668.md

Feste Warn-Objekte (keine Netz-Abrufe), feste Zeit ``2026-10-29T06:00+02:00``
(Stand ``06:00``), Nutzer ``golden-de``. ``render_fall(name, lang)`` liefert je
Fall ``(html, txt)``: alle E-Mail-, Telegram- und SMS-Ausgaben des echten
Renderers, mit ``TRENNER`` verbunden. ``lang=None`` ruft die Renderer OHNE
``lang`` auf (Bestandsaufrufer, so entstand die deutsche Golden-Ausgabe vor
der Umstellung). Die SMS bekommt nie ``lang`` (PO-Korrektur 2026-10-31).

Erzeugung der Golden-Dateien: ``uv run python -m tests.helpers.amtliche_warnungen_fixture de``
(bzw. ``en``).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "amtliche_warnungen"
TRENNER = "\n\n===== ✂ =====\n\n"
TZ = ZoneInfo("Europe/Paris")
STAND = "06:00"
PREFIX = "GR20 Golden"
UTC = timezone.utc
FAELLE = ("einzelne_warnung", "gemischte_stufen", "ortsvergleich_nur",
          "lawinen_lagebericht", "entwarnung", "quelltext_franzoesisch")
ORTE = {"o1": "Toulon", "o2": "Hyères", "o3": "Bastia"}


def _kw(lang: str | None) -> dict:
    return {} if lang is None else {"lang": lang}


def golden_pfad(name: str) -> Path:
    return GOLDEN_DIR / name


def _zeit(tag: int, stunde: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, tag, stunde, minute, tzinfo=UTC)


def meteoalarm_eintraege(*bloecke: tuple[str, str]) -> list[dict]:
    """Info-Bloecke EINER MeteoAlarm-Gewitterwarnung (Stufe 3) je Sprache."""
    return [{
        "lang": sprache, "event": text, "headline": None,
        "onset": "2026-10-29T10:00:00+00:00", "expires": "2026-10-29T19:00:00+00:00",
        "area_desc": "Lienz", "level_raw": "3; orange; Moderate",
        "type_raw": "3; Thunderstorm",
    } for sprache, text in bloecke]


def meteoalarm_gewitter():
    """Echter Gruppier-Pfad (``_group_and_map_info_entries``) mit de- und en-Block."""
    from services.official_alerts.meteoalarm import _group_and_map_info_entries

    return _group_and_map_info_entries(meteoalarm_eintraege(
        ("de-DE", "Mäßige Gewitterwarnung"), ("en-GB", "Moderate thunderstorm warning"),
    ))[0]


def meteoalarm_franzoesisch():
    """Einziger Sprachblock Franzoesisch, Label mit Detail-Trenner (AC-2)."""
    from services.official_alerts.meteoalarm import _group_and_map_info_entries

    return _group_and_map_info_entries(meteoalarm_eintraege(("fr-FR", "Orages — Chablais")))[0]


def _alert(**kw):
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(**kw)


def waldbrand():
    return _alert(source="meteo_forets", hazard="wildfire_risk", level=3,
                  label="Waldbrand-Gefahr — Stufe 3", region_label="Haute-Corse")


def zugangssperre():
    return _alert(source="massif_closure", hazard="access_ban", level=4,
                  label="Zugang gesperrt — Monts Toulonnais", dedup_id="massif-83-1")


def hitze():
    return _alert(source="vigilance", hazard="extreme_heat", level=2, label="Extreme Hitze",
                  valid_from=_zeit(29, 0), valid_to=datetime(2026, 10, 29, 23, 59, tzinfo=TZ),
                  region_label="Var")


def lagebericht():
    return _alert(source="slf_bulletin:CH-4241", hazard="avalanche_bulletin", level=3,
                  label="Lawinenstufe 3", scale="eaws", native_level=3, level_modifier="+",
                  elevation_value="Waldgrenze", elevation_direction="above",
                  problems=("wind_slab", "persistent_weak_layers"), time_of_day="earlier",
                  valid_from=_zeit(29, 15), valid_to=_zeit(30, 15),
                  region_label="Saastal", url="https://www.slf.ch/de/lawinenbulletin")


def _trip_notices(alerts_segs, lang, trip=None):
    from output.renderers.alert import official_alerts as oa

    return oa.build_official_alert_notices(trip, alerts_segs, **_kw(lang))


def _compare_notices(alerts_orte, lang):
    from output.renderers.alert import official_alerts as oa

    return oa.build_compare_official_alert_notices(list(ORTE), ORTE, alerts_orte, **_kw(lang))


def notices_fuer(fall: str, lang: str | None):
    """Die Notices eines Falls (Trip- bzw. Ortsvergleich-Builder)."""
    voll = SimpleNamespace(all_waypoints=[0, 1, 2])  # Segmente 1, 2, Ziel
    if fall == "einzelne_warnung":
        return _trip_notices([(meteoalarm_gewitter(), ["1", "2", "Ziel"])], lang, voll)
    if fall == "gemischte_stufen":
        return _compare_notices([(waldbrand(), ["o3"]), (zugangssperre(), ["o1"]),
                                 (hitze(), ["o1", "o2", "o3"])], lang)
    if fall == "ortsvergleich_nur":
        sturm = _alert(source="geosphere_warn", hazard="wind_gust", level=3, label="Sturm",
                       valid_from=_zeit(29, 22), valid_to=_zeit(30, 3), region_label="Var")
        regen = _alert(source="geosphere_warn", hazard="rain", level=3, label="Starkregen",
                       valid_from=_zeit(30, 6), valid_to=_zeit(30, 12), region_label="Var")
        return _compare_notices([(sturm, ["o2"]), (regen, ["o2"])], lang)
    if fall == "lawinen_lagebericht":
        return _trip_notices([(lagebericht(), ["2"])], lang)
    if fall == "quelltext_franzoesisch":
        return _trip_notices([(meteoalarm_franzoesisch(), ["1"])], lang)
    raise KeyError(fall)


def _quelle(notices, lang):
    from output.renderers.alert import official_alerts as oa

    return " · ".join(dict.fromkeys(oa.official_alert_source_label(n.alert.source, **_kw(lang))
                                    for n in notices))


def _warn_kanaele(notices, lang):
    from output.renderers.alert import official_alerts as oa

    kw = _kw(lang)
    quelle = _quelle(notices, lang)
    url = notices[0].alert.url
    entries = [(n.alert.region_label or "", [n.alert]) for n in notices]
    html = [
        oa.render_warn_block(notices, variant="standalone", source_label=quelle, source_url=url,
                             stand_at=STAND, tz=TZ, context_label=PREFIX, **kw),
        oa.render_warn_block(notices, variant="embedded", source_label=quelle, source_url=url,
                             tz=TZ, **kw),
        oa.render_official_alerts_html(entries, **kw),
    ]
    txt = [
        oa.render_official_alert_subject(notices, prefix=PREFIX, tz=TZ, **kw),
        oa.render_official_alert_mail_plain(notices, source_label=quelle, stand_at=STAND, tz=TZ,
                                            context_label=PREFIX, source_url=url, **kw),
        oa.render_official_alert_telegram(notices, prefix=PREFIX, source_label=quelle, tz=TZ, **kw),
        oa.render_official_alert_sms(notices, tz=TZ),
        "\n".join(oa.render_official_alert_notice_plain([(n.alert, []) for n in notices], TZ, **kw)),
        "\n".join(oa.render_official_alerts_plain(entries, **kw)),
    ]
    return html, txt


def allclears(lang: str | None):
    """Zwei Entwarnungen: Gewitter Stufe 3 -> 1 (Segment 1) und Hitze 3 -> beendet."""
    from output.renderers.alert import official_alerts as oa

    gewitter = _alert(source="geosphere_warn", hazard="thunderstorm", level=1, label="Gewitter",
                      region_label="Innsbruck-Land")
    roh = [
        SimpleNamespace(kind="lowered", alert=gewitter, scope_ids=["1"], old_rank=3, new_rank=1,
                        old_level=3, new_level=1),
        SimpleNamespace(kind="ended", alert=hitze(), scope_ids=[], old_rank=3, new_rank=0,
                        old_level=3, new_level=0),
    ]
    return oa.build_official_allclear_notices(roh, **_kw(lang))


def _entwarnung_kanaele(lang):
    from output.renderers.alert import official_alerts as oa

    kw = _kw(lang)
    ac = allclears(lang)
    warn = notices_fuer("ortsvergleich_nur", lang)
    quelle = "GeoSphere Austria"
    html = [
        oa.render_official_allclear_mail_html(ac, stand_at=STAND, source_label=quelle,
                                              context_label=PREFIX, **kw),
        oa.render_warn_block(warn, variant="standalone", source_label=quelle, stand_at=STAND,
                             tz=TZ, context_label=PREFIX,
                             allclear_html=oa.render_official_allclear_html(ac, **kw), **kw),
    ]
    txt = [
        oa.render_official_allclear_subject_part(ac, **kw),
        oa.render_official_allclear_mail_plain(ac, stand_at=STAND, source_label=quelle,
                                               context_label=PREFIX, **kw),
        oa.render_official_allclear_telegram(ac, prefix=PREFIX, **kw),
        oa.render_official_allclear_telegram(ac, **kw),
        oa.render_official_allclear_sms_block(ac),
        oa.render_official_alert_mail_plain(warn, source_label=quelle, stand_at=STAND, tz=TZ,
                                            context_label=PREFIX,
                                            allclear_lines=oa.render_official_allclear_plain(ac, **kw),
                                            **kw),
        oa.render_official_alert_sms_with_allclears(warn, ac, tz=TZ)[0],
    ]
    return html, txt


def render_fall(fall: str, lang: str | None) -> tuple[str, str]:
    if fall == "entwarnung":
        html, txt = _entwarnung_kanaele(lang)
    else:
        html, txt = _warn_kanaele(notices_fuer(fall, lang), lang)
    return TRENNER.join(html), TRENNER.join(txt)


def sms_texte(lang: str | None) -> list[str]:
    """Alle SMS-Ausgaben aller Faelle (der letzte bzw. vorletzte txt-Abschnitt)."""
    out = []
    for fall in FAELLE:
        txt = render_fall(fall, lang)[1].split(TRENNER)
        out += [txt[4], txt[6]] if fall == "entwarnung" else [txt[3]]
    return out


def schreibe(lang: str) -> list[Path]:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    pfade = []
    for fall in FAELLE:
        html, txt = render_fall(fall, None if lang == "de" else lang)
        for endung, inhalt in (("html", html), ("txt", txt)):
            pfad = GOLDEN_DIR / f"{fall}.{lang}.{endung}"
            pfad.write_text(inhalt, encoding="utf-8")
            pfade.append(pfad)
    return pfade


if __name__ == "__main__":
    for p in schreibe(sys.argv[1] if len(sys.argv) > 1 else "de"):
        print(p)
