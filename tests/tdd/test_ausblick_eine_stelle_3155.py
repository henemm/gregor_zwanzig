"""Eine steuernde Stelle fuer den 3-Tages-Ausblick, ein Name (Issue #3155, B4).

SPEC: docs/specs/modules/feat_3155_ein_name_ausblick.md (AC-3, AC-4, AC-8,
AC-10, AC-13; Entscheidungen 1, 5, 6). Ober-Spec:
docs/specs/modules/feat_3122_was_steht_wo.md (AC-8, AC-9, AC-12, AC-34).

Kern-Schicht, ohne Netz, ohne Mock: echte Loader, echter
``resolve_report_render_options`` (die Entscheidung, nach der der Zeitplaner
die Ausblick-Daten baut), echte Tabellen-Antwort ``build_placements_view``
(die Karte "Was steht wo") und echte Renderer. Die Falllisten-Treiber
(``test_einstellung_gleich_mail_{trip,orte}.py``, Faelle ``*-b4-*``) pruefen
dieselben Regeln an der zugestellten Ausgabe je Briefing, Ausgabe und Sprache.
"""
from __future__ import annotations

import copy
import json

import pytest

from tests.helpers.ausblick_name import NAME, alte_namen_in, html_textknoten
from tests.helpers.einstellung_gleich_mail_orte import (
    html_ausblick as orte_html_ausblick,
    klartext_ausblick as orte_klartext_ausblick,
    kennungen,
    orte_anlegen,
    preset_dict,
    profil_anlegen,
    sende_orte_mail,
)
from tests.tdd._einstellung_gleich_mail_trip_fixtures import frisches_profil, trip_json

BRIEFINGS = ("morning", "evening")
_GRUND = ["gust", "temperature", "wind"]


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def _trip(rc: dict, **kw) -> dict:
    return trip_json(_GRUND, report_config={"send_email": True, **rc},
                     outlook_metrics=kw.pop("outlook_metrics", ["gust", "temperature"]), **kw)


def _geladen(data: dict):
    from app.loader import load_trip

    t = load_trip(copy.deepcopy(data), user_id=frisches_profil())
    assert t is not None
    return t


def _gate(data: dict) -> dict[str, bool]:
    """Je Briefing: baut der Zeitplaner den Ausblick?
    (``resolve_report_render_options(...).show_multi_day_trend``, dieselbe
    Entscheidung wie ``trip_briefing_aufbau``)."""
    from services.report_config_resolver import resolve_report_render_options

    t = _geladen(data)
    return {rt: resolve_report_render_options(t.report_config, t.display_config, rt)
            .show_multi_day_trend for rt in BRIEFINGS}


def _abo_ablegen(uid: str, abo: dict) -> None:
    """Abo-Datei UNVERAENDERT ins Nutzerverzeichnis (``briefings/<id>.json``)."""
    from app.loader import get_data_dir

    ordner = get_data_dir(uid) / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{abo['id']}.json").write_text(json.dumps(abo, ensure_ascii=False), encoding="utf-8")


def _karte_trip(data: dict) -> dict[str, bool]:
    """Schalter "Ausblick im Morgen-/Abend-Briefing" der Karte (Tabellen-
    Antwort ``build_placements_view``) fuer einen Trip dieses Nutzers."""
    from services.placements_view_service import build_placements_view

    uid = frisches_profil()
    _abo_ablegen(uid, data)
    antwort = build_placements_view("route", data["id"], uid)
    return dict(antwort["blocks"]["outlook"])


# ---------------------------------------------------------------------------
# Backend-Weiche Trip (Entscheidung 1): Altpfad ueber die eine Regel
# ---------------------------------------------------------------------------

def test_altpfad_show_outlook_aus_ausfuehrlich_kein_ausblick_in_beiden_briefings():
    """AC-3/AC-4: Bestands-Trip ohne Tabelle, ``show_outlook: false``, Format
    ausfuehrlich, ``multi_day_trend_reports`` morgens und abends -> der
    Zeitplaner baut in KEINEM Briefing einen Ausblick (sonst stuende er in
    Telegram und Kompakt trotz ausgeschaltetem Schalter)."""
    data = _trip({"show_outlook": False, "multi_day_trend_reports": ["morning", "evening"]})
    assert _gate(data) == {"morning": False, "evening": False}


def test_altpfad_show_outlook_aus_steuert_weiter_die_grosswetterlage():
    """AC-5: ``show_outlook`` bleibt als Schalter der Grosswetterlage erhalten
    (die Optionen tragen ihn unveraendert an die Renderer)."""
    from services.report_config_resolver import resolve_report_render_options

    t = _geladen(_trip({"show_outlook": False}))
    for rt in BRIEFINGS:
        assert resolve_report_render_options(t.report_config, t.display_config, rt).show_outlook is False


@pytest.mark.parametrize("reports", [["evening"], ["morning"], ["morning", "evening"]])
def test_altpfad_kompakt_behaelt_ausblick_nach_multi_day_trend_reports(reports):
    """AC-3 (Ausnahme, Ober-Spec AC-12): im Kompakt-Format war der Schalter
    gesperrt -- trotz ``show_outlook: false`` folgt der Ausblick dort weiter
    ``multi_day_trend_reports``."""
    data = _trip({"show_outlook": False, "email_format": "compact",
                  "multi_day_trend_reports": reports})
    assert _gate(data) == {rt: rt in reports for rt in BRIEFINGS}


def test_altpfad_outlook_metrics_leer_kein_ausblick():
    """AC-4: Bestands-Trip mit ``outlook_metrics: []`` -> der Zeitplaner baut
    in keinem Briefing einen Ausblick (leere Liste = aus, ADR-0124 Nr. 6)."""
    data = _trip({"multi_day_trend_reports": ["morning", "evening"]}, outlook_metrics=[])
    assert _gate(data) == {"morning": False, "evening": False}


@pytest.mark.parametrize("fmt", ["full", "compact"])
@pytest.mark.parametrize("reports", [["evening"], ["morning"], ["morning", "evening"], []])
def test_bestand_mit_show_outlook_an_unveraendert(reports, fmt):
    """AC-13: ein Bestands-Trip mit eingeschaltetem Ausblick-Schalter behaelt
    genau seine Briefings (``multi_day_trend_reports``), in beiden Formaten."""
    data = _trip({"show_outlook": True, "email_format": fmt, "multi_day_trend_reports": reports})
    assert _gate(data) == {rt: rt in reports for rt in BRIEFINGS}


# ---------------------------------------------------------------------------
# AC-4: Ausgabe und Karte "Was steht wo" zeigen dieselben Schalter
# ---------------------------------------------------------------------------

_BESTAND_TRIPS = {
    "show_outlook_aus": ({"show_outlook": False, "multi_day_trend_reports": ["morning", "evening"]}, {}),
    "metriken_leer": ({"multi_day_trend_reports": ["morning", "evening"]}, {"outlook_metrics": []}),
    "beide": ({"multi_day_trend_reports": ["morning", "evening"]}, {}),
    "nur_abend": ({"multi_day_trend_reports": ["evening"]}, {}),
    "kompakt_show_outlook_aus": ({"show_outlook": False, "email_format": "compact",
                                  "multi_day_trend_reports": ["evening"]}, {}),
}


@pytest.mark.parametrize("name", sorted(_BESTAND_TRIPS))
def test_trip_ausgabe_und_karte_zeigen_dieselben_schalter(name):
    """AC-4: fuer Bestands-Trips ohne Tabelle entscheidet die Ausgabe (der
    Zeitplaner) je Briefing genauso wie die Umrechnung, die die Karte "Was
    steht wo" zeigt -- eine Regel, kein zweiter Stand."""
    rc, kw = _BESTAND_TRIPS[name]
    data = _trip({**rc, "send_telegram": True}, **kw)
    assert _gate(data) == _karte_trip(data), name


# ---------------------------------------------------------------------------
# Orte-Anlage-Marke (Entscheidung 5): placements ohne rows
# ---------------------------------------------------------------------------

_ORTE_AUSBLICK = ["precipitation", "wind", "temperature"]


def _orte_abo(placements=None, **top) -> dict:
    p = preset_dict("ac7_ausblick")
    p.update(id="orte-b4-marke", send_telegram=True, morning_enabled=True, evening_enabled=True)
    dc = p["display_config"]
    dc["outlook_metrics"] = list(_ORTE_AUSBLICK)
    dc["outlook_metric_formats"] = {"wind": True}
    if placements is not None:
        dc["placements"] = placements
    p.update(top)
    return p


def _karte_orte(abo: dict) -> dict:
    from services.placements_view_service import build_placements_view

    uid = profil_anlegen()
    orte_anlegen(uid)
    _abo_ablegen(uid, abo)
    return build_placements_view("vergleich", abo["id"], uid)


def _orte_ausgabe(abo: dict, briefing: str) -> dict:
    mail = sende_orte_mail(copy.deepcopy(abo), briefing=briefing)
    ort = next(iter(orte_html_ausblick(mail.html)), None)
    return {
        "html": [kennungen(z) for z in orte_html_ausblick(mail.html).values()],
        "klartext": [kennungen(z) for z in orte_klartext_ausblick(mail.plain).values()],
        "telegram": mail.telegram,
        "erster_ort": ort,
    }


@pytest.mark.parametrize("reports, soll", [
    (["evening"], {"morning": False, "evening": True}),
    (["morning"], {"morning": True, "evening": False}),
    ([], {"morning": False, "evening": False}),
])
def test_orte_marke_ohne_rows_steuert_ausgabe_und_karte_gleich(reports, soll):
    """AC-8: Orte-Abo mit der Anlage-Marke ``placements = {version,
    outlook_reports}`` OHNE ``rows`` -> die Ausgabe zeigt den Ausblick nur in
    den markierten Briefings, und die Tabellen-Antwort der Karte zeigt
    dieselben Schalter."""
    abo = _orte_abo({"version": 1, "outlook_reports": list(reports)})
    karte = _karte_orte(abo)
    assert karte["blocks"]["outlook"] == soll, karte["blocks"]["outlook"]
    assert karte["outlook_reports"] == [rt for rt in BRIEFINGS if soll[rt]]
    for rt in BRIEFINGS:
        aus = _orte_ausgabe(abo, rt)
        da = {"html": bool(aus["html"]), "klartext": bool(aus["klartext"])}
        assert da == {"html": soll[rt], "klartext": soll[rt]}, (rt, da)


def test_orte_marke_laesst_altpfad_auswahl_und_formate_unveraendert():
    """AC-8: die Marke steuert NUR den Ausblick -- Auswahl und Folge der
    Ausblick-Spalten (Anlege-Assistent) bleiben die des Altpfads, und das Abo
    bleibt ohne gespeicherte Tabelle (``stored`` falsch, keine Zeilen
    ueberschrieben)."""
    mit_marke = _orte_abo({"version": 1, "outlook_reports": ["evening"]})
    ohne_marke = _orte_abo()
    a = _orte_ausgabe(mit_marke, "evening")
    b = _orte_ausgabe(ohne_marke, "evening")
    assert a["html"] and a["html"] == b["html"], (a["html"], b["html"])
    assert a["klartext"] == b["klartext"]
    assert all(spalten == _ORTE_AUSBLICK for spalten in a["html"]), a["html"]
    assert _karte_orte(mit_marke)["stored"] is False


def test_orte_bestand_ohne_marke_unveraendert():
    """AC-13 (Spec Nr. 8): ein Bestands-Orte-Abo ohne Tabelle und ohne Marke
    zeigt den Ausblick weiter in jedem eingeschalteten Briefing."""
    abo = _orte_abo(outlook_enabled=True)
    assert _karte_orte(abo)["blocks"]["outlook"] == {"morning": True, "evening": True}
    for rt in BRIEFINGS:
        assert _orte_ausgabe(abo, rt)["html"], rt


# ---------------------------------------------------------------------------
# Ein Name (Entscheidung 6): Zustandshinweis und Telegram-Kopf
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_zustandshinweis_traegt_den_einen_namen(lang):
    """AC-10: der Zustandshinweis "Ausblick nicht abrufbar" (Stoerungsbox im
    HTML) traegt als Titel denselben Namen wie der Block."""
    from output.renderers.email.outlook_state_hint import (
        OutlookState, render_outlook_state_html,
    )

    knoten = html_textknoten(render_outlook_state_html(OutlookState.UNAVAILABLE, lang=lang))
    assert knoten and knoten[0] == NAME[lang], knoten
    assert not alte_namen_in(knoten), alte_namen_in(knoten)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_trip_mail_mit_zustandshinweis_traegt_den_einen_namen(monkeypatch, lang):
    """AC-10: auch ohne Ausblick-Zeilen (Zustand "nicht abrufbar") heisst der
    Block in der HTML-Mail des Trips "3-Tages-Ausblick"/"3-day outlook" --
    gerendert ueber ``render_html`` mit dem Zustand."""
    from zoneinfo import ZoneInfo

    from output.renderers.email.html import render_html
    from output.renderers.email.outlook_state_hint import OutlookState
    from tests.unit.test_renderers_email import _common_kwargs as basis

    kw = basis()
    html = render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name="Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=None, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None,
        outlook_state=OutlookState.UNAVAILABLE, lang=lang,
    )
    knoten = html_textknoten(html)
    assert any(k.casefold() == NAME[lang].casefold() for k in knoten), [
        k for k in knoten if "usblick" in k or "utlook" in k.casefold()]
    assert not alte_namen_in(knoten), alte_namen_in(knoten)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_klartext_mail_zustandshinweis_traegt_den_einen_namen(lang):
    """AC-10 (Adversary F002, Fix-Loop 1): in der Nur-Text-Mail des Trips
    (ausfuehrlich, Ausblick an, Zustand != FOUND) heisst der Titel des
    Zustandshinweises "3-Tages-Ausblick"/"3-day outlook" -- in BEIDEN Sprachen,
    nie ein Altname ("Nächste Etappen", "Naechste Etappen", "Next stages")."""
    from tests.helpers.ausblick_name import textzeilen
    from tests.helpers.briefing_compact_plain_fixture import render_briefing

    text = render_briefing(lang, email_format="full", variante="zustand").email_plain
    zeilen = textzeilen(text)
    titel = [z for z in zeilen if z.startswith("━━")]
    assert f"━━ {NAME[lang]} ━━" in titel, titel
    # Der Titel steht direkt ueber dem Zustandshinweis (Block, nicht Zufallstreffer).
    i = zeilen.index(f"━━ {NAME[lang]} ━━")
    assert zeilen[i + 1], zeilen[i:i + 3]
    for alt in ("Nächste Etappen", "Naechste Etappen", "Next stages"):
        assert alt.casefold() not in text.casefold(), (alt, titel)
    assert not alte_namen_in(zeilen), alte_namen_in(zeilen)
