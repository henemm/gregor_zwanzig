"""Umrechnung der Altfelder in ``placements`` und Differenztest beider Pfade.

Issue #3122, Scheibe B1a. SPEC: docs/specs/modules/feat_3122_was_steht_wo.md,
Teil A Nr. 6 und Nr. 8, AC-12 (Umrechnung), Vorbereitung AC-11/AC-13.

``placements_from_legacy`` ist die EINZIGE Umrechnung (Resolver ab B3,
Tabelle B2, Migration B6). Der Differenztest haelt bis B3 beide Pfade
zusammen: View-Model des bisherigen Pfads == View-Model aus der Umrechnung
ueber den neuen Eingang, Abweichungen nur in benannten, gemeldeten Faellen.

Kern-Schicht, ohne Netz, ohne Mock. Das Orakel "welche Form erscheint heute"
(``_heutige_form``) und die Pruefung jeder Abweichung stehen hier unabhaengig
von der Implementierung.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"
REPORT_TYPEN = ("morning", "evening")

#: Die vier bewussten Aenderungen aus Spec Teil A Nr. 8.
VIER_FAELLE = {"reihenfolge_wie_sms", "ohne_email_entfaellt", "nur_text_folgt_html",
               "sms_wolkenform_entfaellt"}
#: Folgen anderer Festlegungen der Spec, die die Umrechnung ebenfalls meldet
#: (Nr. 2 Katalog-ID als Zeile, Nr. 3.1 Grundauswahl als Maximum, Nr. 8
#: "zaehlt die Abend-Fassung", ADR-0124 Nr. 8 Premium-SMS = SMS).
WEITERE_FAELLE = {"auswertungen_gekoppelt", "ausserhalb_grundauswahl", "morgen_folgt_abend",
                  "premium_folgt_sms", "gesperrte_stelle_entfaellt",
                  # #3122 Fix-Loop B1b: Nacht-/Tagesgroessen ohne eigene Spalte
                  # gehoeren zur Trip-Mail, folgen der Grundauswahl und sind in
                  # der E-Mail-Spalte nicht abwaehlbar -- eine Kanal-Liste, die
                  # sie weggelassen hatte, verliert diese Wirkung.
                  "ohne_spalte_folgt_grundauswahl"}
#: Faelle, die das View-Model nicht als Mengen-/Folgeabweichung zeigt (sie
#: stehen nach Regel in der Liste, s. eigene Tests oben).
REGEL_FAELLE = {"nur_text_folgt_html", "sms_wolkenform_entfaellt"}


def _umrechnen(dc, surface, **kw):
    from services.placements import placements_from_legacy

    return placements_from_legacy(dc, surface, **kw)


def _resolve(dc, surface, report_type="evening", **kw):
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists(dc, surface, report_type, **kw)


def _zeilen(placements):
    return {r["metric_id"]: r for r in placements["rows"]}


def _arten(umrechnung):
    return {(c.kind, c.stelle, c.metric_id) for c in umrechnung.changes}


def _m(metric_id, i, **kw):
    return {"metric_id": metric_id, "enabled": True, "bucket": "primary", "order": i, **kw}


def _trip(grund, **extra):
    return {"trip_id": "t-3122u", "metrics": [_m(m, i) for i, m in enumerate(grund)], **extra}


# ---------------------------------------------------------------------------
# Reihenfolge: SMS fuehrt, dann Telegram, E-Mail, Grundauswahl
# ---------------------------------------------------------------------------

GRUND6 = ["wind", "gust", "precipitation", "cloud_total", "rain_probability", "uv_index"]
LAYOUTS = {
    "sms": [{"metric_id": "precipitation"}, {"metric_id": "wind"}],
    "telegram": [{"metric_id": "gust"}, {"metric_id": "wind"}, {"metric_id": "cloud_total"}],
    "email": [{"metric_id": "cloud_total"}, {"metric_id": "rain_probability"},
              {"metric_id": "wind"}],
}


def test_reihenfolge_sms_fuehrt_dann_telegram_email_grundauswahl():
    u = _umrechnen(_trip(GRUND6, channel_layouts=copy.deepcopy(LAYOUTS)), "trip")
    assert [r["metric_id"] for r in u.placements["rows"]] == [
        "precipitation", "wind", "gust", "cloud_total", "rain_probability", "uv_index"]
    z = _zeilen(u.placements)
    assert z["precipitation"]["places"] == {"email": False, "telegram": False, "sms": True,
                                            "outlook": True}
    assert z["gust"]["places"] == {"email": False, "telegram": True, "sms": False,
                                   "outlook": True}
    assert z["uv_index"]["places"] == {"email": False, "telegram": False, "sms": False,
                                       "outlook": True}
    assert u.placements["version"] == 1


def test_reihenfolge_abend_fassung_zaehlt():
    dc = _trip(["wind", "gust", "precipitation"], channel_layouts_per_report={
        "evening": {"sms": [{"metric_id": "gust"}, {"metric_id": "wind"}]},
        "morning": {"sms": [{"metric_id": "wind"}]},
    })
    u = _umrechnen(dc, "trip")
    assert [r["metric_id"] for r in u.placements["rows"]] == ["gust", "wind", "precipitation"]
    assert _zeilen(u.placements)["precipitation"]["places"]["sms"] is False


def test_orte_reihenfolge_und_katalog_ids():
    dc = {"active_metrics": ["temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh"],
          "channel_active_metrics": {"sms": ["gust_max_kmh", "temp_max_c", "temp_min_c"]}}
    u = _umrechnen(dc, "compare")
    assert [r["metric_id"] for r in u.placements["rows"]] == ["gust", "temperature", "wind"]
    assert _zeilen(u.placements)["wind"]["places"]["sms"] is False
    assert set(_zeilen(u.placements)["wind"]["places"]) == {
        "email", "telegram", "sms", "hourly", "outlook"}


# ---------------------------------------------------------------------------
# Format: die heute erscheinende Form, ausdruecklich gespeichert
# ---------------------------------------------------------------------------

def test_format_trip_heutige_form_je_stelle():
    dc = _trip(["wind", "gust", "cloud_total", "temperature"],
               outlook_metric_formats={"wind": True})
    dc["metrics"][1]["use_friendly_format"] = False
    z = _zeilen(_umrechnen(dc, "trip").placements)
    # HTML-Mail: Wind ohne Angabe zeigt den Ampelpunkt (Einfach); Telegram die Zahl.
    assert z["wind"]["formats"] == {"email": "simplified", "telegram": "raw",
                                    "outlook": "simplified"}
    assert z["gust"]["formats"] == {"email": "raw", "telegram": "raw", "outlook": "raw"}
    assert z["cloud_total"]["formats"] == {"email": "simplified", "telegram": "simplified",
                                           "outlook": "raw"}
    assert z["temperature"].get("formats", {}) == {}


def test_format_orte_ohne_angabe_ausdruecklich_roh():
    dc = {"active_metrics": ["wind_max_kmh", "gust_max_kmh", "cloud_avg_pct"],
          "channel_layouts": {"email": [{"metric_id": "wind", "use_friendly_format": True}]},
          "hourly_metrics": ["gust", "wind"], "hourly_metric_formats": {"gust": True}}
    z = _zeilen(_umrechnen(dc, "compare").placements)
    assert z["wind"]["formats"] == {"email": "simplified", "telegram": "raw",
                                    "hourly": "raw", "outlook": "raw"}
    assert z["gust"]["formats"] == {"email": "raw", "telegram": "raw", "hourly": "simplified",
                                    "outlook": "raw"}
    assert z["cloud_total"]["formats"] == {"email": "raw", "telegram": "raw",
                                           "hourly": "raw", "outlook": "raw"}


# ---------------------------------------------------------------------------
# Ausblick (Spec Nr. 6/8, AC-12)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_config,erwartet,stabilitaet_aus", [
    ({"show_outlook": False}, [], True),
    # #3154 F003: Kompakt wertet show_outlook nicht aus (Ausblick wie gesendet).
    ({"show_outlook": False, "email_format": "compact"}, ["evening"], False),
    ({"multi_day_trend_reports": ["morning", "evening"]}, ["morning", "evening"], False),
    ({"multi_day_trend_reports": ["morning"]}, ["morning"], False),
    ({}, ["evening"], False),
    (None, ["evening"], False),
])
def test_ac12_trip_ausblick_umrechnung(report_config, erwartet, stabilitaet_aus):
    u = _umrechnen(_trip(["wind", "gust"]), "trip", report_config=report_config)
    assert u.placements["outlook_reports"] == erwartet
    assert u.show_stability_off is stabilitaet_aus


def test_ac12_trip_leere_ausblick_liste_ist_aus_und_display_config_fundort():
    assert _umrechnen(_trip(["wind"], outlook_metrics=[]), "trip").placements[
        "outlook_reports"] == []
    assert _umrechnen(_trip(["wind"], multi_day_trend_reports=["morning"]), "trip").placements[
        "outlook_reports"] == ["morning"]
    # report_config geht vor display_config.
    assert _umrechnen(_trip(["wind"], multi_day_trend_reports=["morning"]), "trip",
                      report_config={"multi_day_trend_reports": ["evening"]}).placements[
        "outlook_reports"] == ["evening"]


def test_ac12_trip_ausblick_morgens_und_abends_wirkt_in_beiden_briefings():
    dc = _trip(["wind", "gust"])
    u = _umrechnen(dc, "trip", report_config={"multi_day_trend_reports": ["morning", "evening"]})
    neu = {**dc, "placements": u.placements}
    for report_type in REPORT_TYPEN:
        assert [z.metric_id for z in _resolve(neu, "trip", report_type).outlook] == ["wind", "gust"]
    aus = _umrechnen(dc, "trip", report_config={"show_outlook": False})
    for report_type in REPORT_TYPEN:
        assert _resolve({**dc, "placements": aus.placements}, "trip", report_type).outlook == ()


@pytest.mark.parametrize("kw,extra,erwartet", [
    ({"outlook_enabled": False}, {}, []),
    ({}, {"outlook_metrics": []}, []),
    ({"enabled_reports": ("morning",)}, {}, ["morning"]),
    ({"enabled_reports": ("morning", "evening")}, {}, ["morning", "evening"]),
    ({}, {}, ["morning", "evening"]),
])
def test_ac12_orte_ausblick_umrechnung(kw, extra, erwartet):
    dc = {"active_metrics": ["wind_max_kmh"], **extra}
    u = _umrechnen(dc, "compare", **kw)
    assert u.placements["outlook_reports"] == erwartet
    assert u.show_stability_off is False


# ---------------------------------------------------------------------------
# Die vier bewussten Aenderungen (Spec Nr. 8), je ein benannter Fall
# ---------------------------------------------------------------------------

def test_fall1_email_und_telegram_uebernehmen_die_sms_reihenfolge():
    u = _umrechnen(_trip(GRUND6, channel_layouts=copy.deepcopy(LAYOUTS)), "trip")
    arten = _arten(u)
    assert ("reihenfolge_wie_sms", "email", None) in arten
    assert ("reihenfolge_wie_sms", "telegram", None) in arten
    ohne = _umrechnen(_trip(GRUND6), "trip")
    assert not {a for a in _arten(ohne) if a[0] == "reihenfolge_wie_sms"}


def test_fall2_ausblick_oder_stundenverlauf_ohne_email_entfaellt():
    trip = _umrechnen(_trip(["wind", "gust"], channel_layouts={"email": [{"metric_id": "wind"}]}),
                      "trip")
    assert ("ohne_email_entfaellt", "outlook", "gust") in _arten(trip)
    assert _zeilen(trip.placements)["gust"]["places"]["outlook"] is True, "Haken bleibt"
    orte = _umrechnen({"active_metrics": ["wind_max_kmh", "gust_max_kmh"],
                       "channel_layouts": {"email": [{"metric_id": "wind"},
                                                     {"metric_id": "gust", "enabled": False}]},
                       "hourly_metrics": ["gust", "wind"]}, "compare")
    assert ("ohne_email_entfaellt", "hourly", "gust") in _arten(orte)
    assert ("ohne_email_entfaellt", "outlook", "gust") in _arten(orte)


def test_fall3_nur_text_mail_folgt_der_html_mail():
    roh = _trip(["wind", "gust"])
    roh["metrics"][1]["use_friendly_format"] = False
    arten = _arten(_umrechnen(roh, "trip"))
    assert ("nur_text_folgt_html", "email", "wind") in arten
    assert not any(a[0] == "nur_text_folgt_html" and a[2] == "gust" for a in arten)
    orte = _umrechnen({"active_metrics": ["wind_max_kmh"], "channel_layouts": {
        "email": [{"metric_id": "wind", "use_friendly_format": True}]}}, "compare")
    assert not any(a[0] == "nur_text_folgt_html" for a in _arten(orte))


def test_fall4_abweichende_wolkenform_der_sms_entfaellt():
    trip = _umrechnen(_trip(["cloud_total", "wind"], channel_layouts={"sms": [
        {"metric_id": "cloud_total", "format_mode": "raw"}, {"metric_id": "wind"}]}), "trip")
    assert ("sms_wolkenform_entfaellt", "sms", "cloud_total") in _arten(trip)
    standard = _umrechnen(_trip(["cloud_total", "wind"]), "trip")
    assert not any(a[0] == "sms_wolkenform_entfaellt" for a in _arten(standard))
    orte = _umrechnen({"active_metrics": ["cloud_avg_pct"], "channel_layouts": {"sms": [
        {"metric_id": "cloud_total", "use_friendly_format": True}]}}, "compare")
    # #3101: gemeldet im einen Vokabular (Katalog-ID).
    assert ("sms_wolkenform_entfaellt", "sms", "cloud_total") in _arten(orte)


# ---------------------------------------------------------------------------
# Idempotenz, Reinheit, Schalter, rows fuer den Altbestand
# ---------------------------------------------------------------------------

def test_idempotent_vorhandene_placements_werden_nicht_umgerechnet():
    dc = _trip(GRUND6, channel_layouts=copy.deepcopy(LAYOUTS))
    erst = _umrechnen(dc, "trip")
    zweit = _umrechnen({**dc, "placements": erst.placements}, "trip")
    assert zweit.placements == erst.placements
    assert zweit.changes == ()
    roh = {"rows": [{"metric_id": "wind", "places": {"sms": False, "fax": True},
                     "formats": {"sms": "raw", "email": "simplified"}}, "kaputt"],
           "outlook_reports": ["evening", "noon"], "x": 1}
    norm = _umrechnen({**dc, "placements": roh}, "trip").placements
    assert norm == {"version": 1, "rows": [{"metric_id": "wind", "places": {"sms": False},
                                            "formats": {"email": "simplified"}}],
                    "outlook_reports": ["evening"]}


def test_umrechnung_mutiert_nicht_und_ist_json_faehig():
    dc = _trip(GRUND6, channel_layouts=copy.deepcopy(LAYOUTS), outlook_metrics=["wind"])
    vorher = copy.deepcopy(dc)
    u = _umrechnen(dc, "trip", report_config={"show_outlook": True})
    assert dc == vorher
    assert json.loads(json.dumps(u.placements)) == u.placements


def test_altbestand_rows_kommen_aus_der_umrechnung_kanaele_aus_dem_bisherigen_pfad():
    from services import channel_list_resolver as clr

    assert clr.ALTBESTAND_UEBER_UMRECHNUNG is False
    dc = _trip(GRUND6, channel_layouts=copy.deepcopy(LAYOUTS))
    alt = _resolve(dc, "trip", with_rows=True)
    neu = _resolve({**dc, "placements": _umrechnen(dc, "trip").placements}, "trip")
    assert alt.rows == neu.rows
    assert alt.outlook_reports == neu.outlook_reports == ("evening",)
    assert [z.metric_id for z in alt.email] == ["cloud_total", "rain_probability", "wind"]
    assert [z.metric_id for z in neu.email] == ["wind", "cloud_total", "rain_probability"]


def test_schalter_umgelegt_altbestand_liest_ueber_die_umrechnung(monkeypatch):
    from services import channel_list_resolver as clr

    dc = _trip(GRUND6, channel_layouts=copy.deepcopy(LAYOUTS))
    neu = _resolve({**dc, "placements": _umrechnen(dc, "trip").placements}, "trip")
    monkeypatch.setattr(clr, "ALTBESTAND_UEBER_UMRECHNUNG", True)
    assert _resolve(dc, "trip") == neu


# ---------------------------------------------------------------------------
# Differenztest: bisheriger Pfad == Umrechnung ueber den neuen Eingang
# ---------------------------------------------------------------------------

AMPEL4 = {"wind", "gust", "precipitation", "rain_probability"}


def _katalog_id(surface, metric_id):
    """Zeilen-Schluessel (Katalog-ID, Aggregation) des View-Models (#3101),
    Trip-Kennung oder Renderer-Kennung (Grundauswahl des Altpfads) ->
    Katalog-ID."""
    if isinstance(metric_id, tuple):
        return metric_id[0]
    if surface == "trip":
        return metric_id
    from output.renderers.compare_outlook_metric_ids import _kennungen_aus_renderer_ids

    return (_kennungen_aus_renderer_ids([metric_id]) or [metric_id])[0]


def _heutige_form(surface, stelle, metric_id, fmt):
    """Orakel: welche Form zeigt der bisherige Pfad heute (Zeilen-Format ->
    raw|simplified). Trip-E-Mail = HTML-Mail (Ampelpunkt haengt an
    ``use_friendly_format``, ohne Angabe also Einfach)."""
    from app.metric_catalog import get_metric

    if fmt == "raw":
        return "raw"
    if fmt is not None:
        return "simplified"
    if stelle in ("outlook", "hourly") or surface == "compare":
        return "raw"
    if stelle == "email" and metric_id in AMPEL4:
        return "simplified"
    return "raw" if get_metric(metric_id).default_format_mode == "raw" else "simplified"


def _orte_standard():
    from output.renderers.email.compare_html import CV2_ZEILEN

    return [z["key"] for z in CV2_ZEILEN if z["key"] != "warn"]


def _schluessel(z):
    """Zeile des View-Models -> Vergleichs-Schluessel: (Katalog-ID,
    Aggregation) -- je Renderer-Zeile genau einer (#3101)."""
    return (z.metric_id, getattr(z, "aggregation", None))


def _ausblick_an_alt(dc, surface, report_type, kw):
    if surface == "compare":
        return kw.get("outlook_enabled", True) is not False and report_type in kw.get(
            "enabled_reports", REPORT_TYPEN)
    rc = kw.get("report_config") or {}
    if rc.get("show_outlook") is False:
        return False
    reports = rc.get("multi_day_trend_reports", dc.get("multi_day_trend_reports", ["evening"]))
    return report_type in reports


def _sperrt(mid: str, stelle: str, surface: str) -> bool:
    """Gesperrt UND ohne Ausgabe; "keine eigene Spalte" (Trip-Mail) laesst die
    Groesse in der Mail (#3122 Fix-Loop B1b)."""
    from app.metric_catalog import stellen_sperre

    grund = stellen_sperre(mid, stelle, surface)
    return bool(grund) and grund != "keine_eigene_spalte"


def _alt_gesperrt(alt, dc, surface, stelle, report_type, kw):
    """Altzeilen an gesperrten Stellen (sie zeigten dort nichts, Nr. 5)."""
    sperr_stelle = "sms" if stelle == "premium_sms" else stelle
    alle = [m for m, _f in _alt_liste(alt, dc, surface, stelle, report_type, kw, sperren=False)]
    return [m for m in alle if _sperrt(_katalog_id(surface, m), sperr_stelle, surface)]


def _alt_liste(alt, dc, surface, stelle, report_type, kw, sperren=True):
    zeilen = getattr(alt, stelle)
    if zeilen is None:
        from tests.helpers.kanal_liste_orakel import alt_katalog_paare

        zeilen = [type("Z", (), {"metric_id": m, "aggregation": a, "format": None})()
                  for m, a in alt_katalog_paare(_orte_standard())]
    if stelle == "outlook" and not _ausblick_an_alt(dc, surface, report_type, kw):
        zeilen = []
    if stelle == "hourly" and kw.get("hourly_enabled", True) is False:
        zeilen = []
    sperr_stelle = "sms" if stelle == "premium_sms" else stelle
    return [(_schluessel(z), z.format) for z in zeilen
            if not (sperren and _sperrt(_katalog_id(surface, z.metric_id), sperr_stelle,
                                        surface))]


def _grund_katalog(dc, surface, report_type):
    from app.loader import _parse_display_config
    from output.renderers.compare_metric_ids import resolve_enabled_metrics

    if surface == "trip":
        modell = _parse_display_config(copy.deepcopy(dc), trip_standard_bei_leer=True)
        return {mc.metric_id for mc in modell.get_metrics_for_report_type(report_type)}
    ids = resolve_enabled_metrics(dc.get("active_metrics"))
    return {_katalog_id("compare", r) for r in (_orte_standard() if ids is None else ids)}


def _begruendet(art, surface, stelle, metric_id, report_type, ctx):
    """Unabhaengige Pruefung, ob eine gemeldete Abweichung zu ihrer Art passt."""
    from output.renderers.compare_metric_ids import _renderer_ids_for_kennung

    kid = None if metric_id is None else _katalog_id(surface, metric_id)
    if art == "reihenfolge_wie_sms":
        return stelle in ("email", "telegram", "outlook", "hourly") and metric_id is None
    if art == "ohne_email_entfaellt":
        return stelle in ("outlook", "hourly") and kid not in ctx["neu_email"]
    if art == "ausserhalb_grundauswahl":
        return kid not in ctx["grund"]
    if art == "auswertungen_gekoppelt":
        return surface == "compare" and (metric_id is None or len(
            _renderer_ids_for_kennung(kid)) > 1)
    if art == "morgen_folgt_abend":
        return surface == "trip" and report_type == "morning"
    if art == "premium_folgt_sms":
        return stelle == "premium_sms"
    if art == "ohne_spalte_folgt_grundauswahl":
        from app.metric_catalog import stellen_sperre

        return (surface == "trip" and stelle == "email" and kid in ctx["grund"]
                and stellen_sperre(kid, "email", surface) == "keine_eigene_spalte")
    return False


def _konv_kw(kw):
    """Abo-Angaben, die die Umrechnung liest (hourly_enabled gehoert zum
    Resolver-Aufruf, nicht zur Umrechnung)."""
    return {k: v for k, v in kw.items()
            if k in ("report_config", "enabled_reports", "outlook_enabled")}


def _differenz(name, dc, surface, kw, fehler, gesehen):
    from app.metric_catalog import zwei_formen_stellen as zwei

    resolver_kw = {k: v for k, v in kw.items() if k in ("enabled_reports", "hourly_enabled")}
    u = _umrechnen(copy.deepcopy(dc), surface, **_konv_kw(kw))
    neu_dc = {**copy.deepcopy(dc), "placements": u.placements}
    gemeldet = {(c.kind, c.stelle, c.metric_id, c.report_type) for c in u.changes}
    for c in u.changes:
        if c.kind not in VIER_FAELLE | WEITERE_FAELLE:
            fehler.append(f"{name}: unbenannte Art {c}")
    stellen = ("email", "telegram", "sms", "premium_sms", "outlook") + (
        ("hourly",) if surface == "compare" else ())
    for rt in REPORT_TYPEN:
        alt = _resolve(copy.deepcopy(dc), surface, rt)
        neu = _resolve(neu_dc, surface, rt, **resolver_kw)
        ctx = {"grund": _grund_katalog(dc, surface, rt),
               "neu_email": {_katalog_id(surface, z.metric_id) for z in neu.email}}
        for stelle in stellen:
            a = _alt_liste(alt, dc, surface, stelle, rt, kw)
            for mid in _alt_gesperrt(alt, dc, surface, stelle, rt, kw):
                if ("gesperrte_stelle_entfaellt", stelle, _katalog_id(surface, mid),
                        rt) not in gemeldet:
                    fehler.append(f"{name}/{rt}/{stelle}: gesperrte Altzeile {mid} ungemeldet")
            n = [(_schluessel(z), z.format) for z in getattr(neu, stelle)]
            a_ids, n_ids = [m for m, _f in a], [m for m, _f in n]
            if a_ids == n_ids:
                gesehen["gleich"] += 1
            for mid in [m for m in a_ids if m not in n_ids] + [m for m in n_ids if m not in a_ids]:
                gesehen["menge"] += 1
                passend = [g for g in gemeldet if g[1] == stelle and g[3] == rt
                           and g[2] == _katalog_id(surface, mid) and g[0] not in REGEL_FAELLE]
                if not passend or not all(
                        _begruendet(g[0], surface, stelle, mid, rt, ctx) for g in passend):
                    fehler.append(f"{name}/{rt}/{stelle}: {mid} alt={a_ids} neu={n_ids} "
                                  f"gemeldet={passend}")
            if set(a_ids) == set(n_ids) and a_ids != n_ids:
                gesehen["folge"] += 1
                passend = [g for g in gemeldet if g[1] == stelle and g[3] == rt and g[2] is None]
                if not passend or not all(
                        _begruendet(g[0], surface, stelle, None, rt, ctx) for g in passend):
                    fehler.append(f"{name}/{rt}/{stelle}: Folge alt={a_ids} neu={n_ids}")
            alt_form = dict(a)
            for mid, form in n:
                if mid not in alt_form or stelle not in zwei(_katalog_id(surface, mid)):
                    continue
                soll = _heutige_form(surface, stelle, _katalog_id(surface, mid), alt_form[mid])
                # Die Form der Morgen-Fassung (channel_layouts_per_report) geht
                # in die Abend-Fassung auf -- nur so gemeldet zulaessig.
                morgen = ("morgen_folgt_abend", stelle, _katalog_id(surface, mid),
                          rt) in gemeldet and _begruendet(
                    "morgen_folgt_abend", surface, stelle, mid, rt, ctx)
                if form != soll and not morgen:
                    fehler.append(f"{name}/{rt}/{stelle}/{mid}: Form {form} != heute {soll}")


def _stichprobe():
    from tests.tdd import test_3057_channel_list_resolver as t57
    from tests.tdd import test_3065_ausblick_stundenverlauf_resolver as t65

    trip_fix = json.loads((FIXTURES / "trip_altbestand.json").read_text())
    yield "fixture-trip", trip_fix["display_config"], "trip", {
        "report_config": trip_fix.get("report_config")}
    for i, (name, dc) in enumerate(t57._trip_kombinationen()):
        if i % 5 == 0:
            yield f"t57-{name}", dc, "trip", {}
    for name, dc in t65._trip_kombinationen():
        yield f"t65-{name}", dc, "trip", {"report_config": {
            "multi_day_trend_reports": ["morning", "evening"]}}
    for name, preset in t57._orte_kombinationen():
        yield f"o57-{name}", preset["display_config"], "compare", {}
    for i, (name, dc) in enumerate(t65._orte_kombinationen()):
        if i % 2 == 0:
            yield f"o65-{name}", dc, "compare", {"hourly_enabled": i % 4 == 0}
    for pfad in sorted(FIXTURES.glob("orte_*.json")):
        preset = json.loads(pfad.read_text())
        reports = tuple(r for r in REPORT_TYPEN if preset.get(f"{r}_enabled", True))
        yield f"fixture-{pfad.stem}", preset.get("display_config") or {}, "compare", {
            "enabled_reports": reports, "outlook_enabled": preset.get("outlook_enabled", True),
            "hourly_enabled": preset.get("hourly_enabled", True)}
    yield from _eigene_varianten()


def _eigene_varianten():
    formen = [_m("wind", 0), _m("gust", 1, use_friendly_format=False),
              _m("cloud_total", 2, format_mode="raw"), _m("cloud_low", 3),
              _m("sunshine", 4), _m("wind_direction", 5), _m("thunder", 6),
              _m("rain_probability", 7), _m("temperature", 8)]
    yield "eigen-trip-formen", {"trip_id": "e", "metrics": formen,
                                "outlook_metric_formats": {"wind": True, "sunshine": True}}, \
        "trip", {"report_config": {"show_outlook": False}}
    yield "eigen-trip-kanal-formen", {
        "trip_id": "e", "metrics": formen,
        "channel_layouts": {
            "telegram": [{"metric_id": "cloud_total", "format_mode": "simplified"},
                         {"metric_id": "wind", "format_mode": "simplified"}],
            "sms": [{"metric_id": "cloud_low", "format_mode": "raw"}, {"metric_id": "wind"}],
            "premium_sms": [{"metric_id": "gust"}]},
        "outlook_metrics": ["gust", "wind"]}, "trip", {}
    yield "eigen-trip-per-report", {
        "trip_id": "e", "metrics": formen,
        "channel_layouts_per_report": {
            "morning": {"email": [{"metric_id": "thunder"}, {"metric_id": "wind"}]},
            "evening": {"sms": [{"metric_id": "sunshine"}, {"metric_id": "gust"}]}}}, \
        "trip", {"report_config": {"multi_day_trend_reports": ["morning"]}}
    yield "eigen-orte-formen", {
        "active_metrics": ["temp_min_c", "wind_max_kmh", "temp_max_c", "gust_max_kmh",
                           "cloud_avg_pct", "sunny_hours_h", "pop_max_pct"],
        "channel_layouts": {"email": [{"metric_id": "cloud_total", "use_friendly_format": True},
                                      {"metric_id": "wind", "format": "simplified"}],
                            "sms": [{"metric_id": "gust"}, {"metric_id": "cloud_total",
                                                            "use_friendly_format": True}]},
        "channel_active_metrics": {"telegram": ["wind_max_kmh", "temp_min_c"]},
        "outlook_metrics": ["sunshine", "wind"], "outlook_metric_formats": {"sunshine": True},
        "hourly_metrics": ["gust", "sunshine", "temperature"],
        "hourly_metric_formats": {"gust": True}}, "compare", {"enabled_reports": ("evening",)}


def test_differenz_bisheriger_pfad_gleich_umrechnung_ueber_neuen_eingang():
    fehler: list[str] = []
    gesehen = {"gleich": 0, "menge": 0, "folge": 0, "faelle": 0}
    for name, dc, surface, kw in _stichprobe():
        gesehen["faelle"] += 1
        _differenz(name, dc, surface, kw, fehler, gesehen)
    assert gesehen["faelle"] > 150 and gesehen["gleich"] > 500, gesehen
    assert gesehen["menge"] and gesehen["folge"], f"Stichprobe ohne Abweichung: {gesehen}"
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:8]}"


def test_differenz_sms_identisch_ohne_gemeldete_ausnahme():
    """Die SMS-Zeilen sind in Menge und Reihenfolge identisch, wo die
    Umrechnung keine SMS-Abweichung meldet."""
    fehler = []
    for name, dc, surface, kw in _stichprobe():
        u = _umrechnen(copy.deepcopy(dc), surface, **_konv_kw(kw))
        neu_dc = {**copy.deepcopy(dc), "placements": u.placements}
        resolver_kw = {k: v for k, v in kw.items() if k in ("enabled_reports", "hourly_enabled")}
        for rt in REPORT_TYPEN:
            if any(c.stelle == "sms" and c.report_type == rt and c.kind != "sms_wolkenform_entfaellt"
                   for c in u.changes):
                continue
            alt = [m for m, _f in _alt_liste(_resolve(copy.deepcopy(dc), surface, rt), dc,
                                             surface, "sms", rt, kw)]
            neu = [_schluessel(z) for z in _resolve(neu_dc, surface, rt, **resolver_kw).sms]
            if alt != neu:
                fehler.append(f"{name}/{rt}: alt={alt} neu={neu}")
    assert not fehler, f"{len(fehler)}: {fehler[:5]}"
