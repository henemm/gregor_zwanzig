"""Skalenwoerter der Mail folgen der Nutzersprache (Issue #2750, Epic #2644).

SPEC: docs/specs/modules/fix_2750_skalenwoerter_lang.md

Nutzersicht: eine ENGLISCHE Trip-Briefing-Mail (Stundentabelle, Modus
"Einfach") und eine ENGLISCHE Ortsvergleichs-Mail (3-Tages-Ausblick, Einfach)
zeigten die Wortstufen deutsch ("mäßig", "trocken", "wahrscheinlich" ...),
weil ``helpers.fmt_val`` und ``compare_outlook_metric_ids`` das ``lang`` nicht
an die Skalenwort-Funktionen (``services.weather_metrics``) weiterreichten.

Kern-Schicht: echte Renderer, deterministische Fixtures, kein Netz, keine
Mocks. Erwartete Woerter kommen aus dem Katalog (``i18n``), nie getippt.
Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen.
"""
from __future__ import annotations
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

_SKALEN = ("wind", "niederschlag", "regen", "sonne")


def _woerter(lang: str) -> set[str]:
    from i18n import catalog

    texte = catalog.get_catalog().texte[lang]
    return {
        v for k, v in texte.items()
        if any(k.startswith(f"api.skala.{s}.") for s in _SKALEN)
    }


def _nur_deutsch() -> set[str]:
    """Deutsche Skalenwoerter, die es im Englischen nicht gibt."""
    return _woerter("de") - _woerter("en")


def _deutsche_treffer(text: str) -> list[str]:
    return sorted(
        w for w in _nur_deutsch()
        if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)
    )


def _englische_treffer(text: str) -> list[str]:
    return sorted(
        w for w in _woerter("en")
        if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)
    )


# --- Trip-Briefing: Stundentabelle im Modus "Einfach" ------------------------

def _golden_modul():
    pfad = REPO_ROOT / "tests" / "golden" / "email" / "regenerate.py"
    spec = importlib.util.spec_from_file_location("golden_regen_2750", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _briefing_plain(lang: str) -> str:
    from app.metric_catalog import build_default_display_config
    from output.renderers.trip_report import TripReportFormatter

    gm = _golden_modul()
    dc = build_default_display_config()
    for mc in dc.metrics:
        if mc.metric_id in ("wind", "gust", "precipitation"):
            mc.format_mode = "simplified"
    seg = gm._build_seg_weather(1, 9, 12, precip_total=2.5)
    report = TripReportFormatter().format_email(
        [seg], "GR20", "evening", display_config=dc, stage_name="E3",
        tz=gm._TZ_CORSICA, lang=lang,
    )
    return report.email_plain


def _stundentabelle(plain: str) -> str:
    start = plain.find("━━ Segment 1")
    assert start >= 0, f"Stundentabelle fehlt in der Mail:\n{plain}"
    ende = plain.find("\n\n", start)
    return plain[start:ende]


def test_ac1_englisches_briefing_zeigt_englische_skalenwoerter():
    """AC-1: Given ein Trip mit Wind/Boeen/Niederschlag im Modus "Einfach"
    und Nutzersprache Englisch / When die Briefing-Mail (Klartext) gerendert
    wird / Then zeigt die Stundentabelle die englischen Wortstufen aus dem
    Katalog und kein deutsches Skalenwort."""
    tabelle = _stundentabelle(_briefing_plain("en"))
    assert not _deutsche_treffer(tabelle), (
        f"Deutsche Skalenwoerter {_deutsche_treffer(tabelle)} in der "
        f"englischen Briefing-Mail:\n{tabelle}"
    )
    assert {"moderate", "dry"} <= set(_englische_treffer(tabelle)), (
        f"Englische Wortstufen fehlen in der Stundentabelle:\n{tabelle}"
    )


def test_ac2_deutsches_briefing_bleibt_deutsch():
    """AC-2: Given derselbe Trip mit Nutzersprache Deutsch / When die
    Briefing-Mail gerendert wird / Then stehen die deutschen Wortstufen
    unveraendert in der Stundentabelle."""
    tabelle = _stundentabelle(_briefing_plain("de"))
    assert {"mäßig", "trocken"} <= set(_deutsche_treffer(tabelle)), tabelle


# --- Ortsvergleich: 3-Tages-Ausblick im Modus "Einfach" ----------------------

_AUSBLICK_IDS = ["wind", "gust", "precipitation", "rain_probability", "sunshine"]


def _vergleich_ausblick(lang: str) -> tuple[str, str]:
    from freezegun import freeze_time

    from app.profile import ActivityProfile
    from output.renderers.comparison import render_compare_email
    from tests.helpers.vergleichs_mail_fixture import (
        JETZT_UTC, _hourly_keys, build_result,
    )

    with freeze_time(JETZT_UTC):
        html, text = render_compare_email(
            build_result(), profile=ActivityProfile.WANDERN,
            enabled_metrics=None, hourly_metrics=_hourly_keys(),
            hourly_enabled=True, preset_name="Golden-Vergleich",
            outlook_enabled=True, outlook_metrics=_AUSBLICK_IDS,
            outlook_metric_formats={i: True for i in _AUSBLICK_IDS},
            lang=lang, preset=PRESET_ALLGEMEIN,
        )
    return html, text


def _ausblick_bloecke(text: str, titel: str) -> str:
    teile = []
    pos = text.find(titel)
    while pos >= 0:
        ende = text.find("\n\n", pos)
        teile.append(text[pos:ende if ende >= 0 else None])
        pos = text.find(titel, pos + 1)
    assert teile, f"Kein Ausblick-Block {titel!r} in der Mail:\n{text[-2000:]}"
    return "\n".join(teile)


def test_ac3_englischer_vergleich_ausblick_zeigt_englische_skalenwoerter():
    """AC-3: Given ein Ortsvergleich mit Ausblick-Groessen im Modus "Einfach"
    und Nutzersprache Englisch / When die Vergleichs-Mail gerendert wird /
    Then zeigen Klartext UND HTML im 3-Tages-Ausblick englische Wortstufen
    und kein deutsches Skalenwort."""
    from i18n import t

    html, text = _vergleich_ausblick("en")
    block = _ausblick_bloecke(text, t("vergleich.ausblick.titel", "en"))
    assert not _deutsche_treffer(block), (
        f"Deutsche Skalenwoerter {_deutsche_treffer(block)} im englischen "
        f"Ausblick:\n{block}"
    )
    assert len(_englische_treffer(block)) >= 3, block
    assert not _deutsche_treffer(html), (
        f"Deutsche Skalenwoerter {_deutsche_treffer(html)} in der englischen "
        "HTML-Vergleichsmail."
    )


def test_ac4_deutscher_vergleich_ausblick_bleibt_deutsch():
    """AC-4: Given derselbe Ortsvergleich mit Nutzersprache Deutsch / When
    die Vergleichs-Mail gerendert wird / Then stehen im Ausblick die
    deutschen Wortstufen."""
    from i18n import t

    _html, text = _vergleich_ausblick("de")
    block = _ausblick_bloecke(text, t("vergleich.ausblick.titel", "de"))
    assert len(_deutsche_treffer(block)) >= 3, block


# --- Trip-Briefing: 3-Tages-Ausblick am echten Versandpfad -------------------

def _trip_mail_fuer_nutzer(user_id: str, profil: dict) -> tuple[str, str]:
    """Echter Versandlauf (Zeitplaner) fuer einen Nutzer mit ``profil`` im
    ``user.json``; liefert (HTML, Klartext) der zugestellten Mail. Ersetzt
    wird nur der Transport (echte Unterklasse, kein Mock)."""
    import json
    import uuid

    import services.notification_service as ns_mod
    from app.loader import get_data_dir
    from tests.helpers.trip_outlook_channels import _settings, trip
    from tests.tdd.test_trip_outlook_dispatch_mail import (
        _fixture_scheduler_klasse,
    )

    user_id = f"{user_id}-{uuid.uuid4().hex[:6]}"
    pfad = get_data_dir(user_id) / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "mail_to": "gregor-test@henemm.com", "is_test_user": True, **profil,
    }))

    gesendet: list[dict] = []
    original = ns_mod.EmailOutput

    class _Aufzeichnung(original):  # echte Subklasse, kein Mock
        def send(self, subject, body, **kwargs):
            gesendet.append({"html": body, **kwargs})
            return None

    t = trip(outlook_metrics=["gust", "precipitation"],
             outlook_metric_formats={"gust": True, "precipitation": True},
             email_format="full")
    ns_mod.EmailOutput = _Aufzeichnung
    try:
        scheduler = _fixture_scheduler_klasse()(
            settings=_settings(user_id), user_id=user_id)
        ergebnis = scheduler._send_trip_report_outcome(t, "evening", on_demand=True)
    finally:
        ns_mod.EmailOutput = original
    assert ergebnis == "sent" and gesendet, f"Kein Versand ({ergebnis!r})."
    return gesendet[0]["html"], gesendet[0].get("plain_text_body") or ""


def _trip_ausblick_zellen(html: str, lang: str) -> str:
    """Textzellen der HTML-Ausblick-Tabelle (Anker: Eyebrow in ``lang``)."""
    from i18n import t

    anker = html.find(t("mail.ausblick.eyebrow", lang))
    if anker == -1:
        return ""
    start = html.find("<tbody>", anker)
    ende = html.find("</tbody>", start)
    zellen = re.findall(r"<td[^>]*>(.*?)</td>", html[start:ende], re.DOTALL)
    return " | ".join(re.sub(r"<[^>]+>", "", z).strip() for z in zellen)


def test_ac5_englischer_trip_ausblick_zeigt_englische_skalenwoerter():
    """AC-5: Given ein Nutzer mit Sprache Englisch und Trip-Ausblick mit
    Boeen/Niederschlag im Modus "Einfach" / When der Zeitplaner das Briefing
    versendet / Then zeigt die zugestellte Mail (HTML und Klartext) die
    englischen Wortstufen und kein deutsches Skalenwort; ein Nutzer ohne
    Sprachfeld erhaelt dieselbe Mail mit deutschen Wortstufen."""
    html_en, plain_en = _trip_mail_fuer_nutzer("tdd-2750-en", {"language": "en"})
    zellen_en = _trip_ausblick_zellen(html_en, "en")
    assert zellen_en, "Der Ausblick fehlt in der englischen Trip-Mail."
    for teil, text in (("HTML", html_en), ("Klartext", plain_en)):
        assert not _deutsche_treffer(text), (
            f"{teil}: deutsche Skalenwoerter {_deutsche_treffer(text)} in der "
            "englischen Trip-Mail."
        )
    assert _englische_treffer(zellen_en), (
        f"Keine englische Wortstufe im Ausblick: {zellen_en!r}"
    )

    html_de, _ = _trip_mail_fuer_nutzer("tdd-2750-de", {})
    zellen_de = _trip_ausblick_zellen(html_de, "de")
    assert _deutsche_treffer(zellen_de), (
        f"Deutscher Nutzer: keine deutsche Wortstufe im Ausblick: {zellen_de!r}"
    )
