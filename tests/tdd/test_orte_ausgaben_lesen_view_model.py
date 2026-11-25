"""Orte-Ausgaben lesen allein das View-Model (Issue #3122, Scheibe B1b).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md (Teil A Nr. 6, 7, 8),
ADR-0124 Nr. 6, 8, 11.

Ergaenzt die Kettentests in ``test_einstellung_gleich_mail_orte_tabelle.py``
um die Naht selbst: die Block-Schalter des Altbestands (``outlook_enabled``,
``hourly_enabled``) entscheidet der Resolver; der Validator-Render geht durch
dieselbe Aufloesung wie der Versand; der Orte-Alarm liest die Grundauswahl
ueber die Resolver-Hilfe und bleibt von der Tabelle unberuehrt. Kein Mock.
"""
from __future__ import annotations

from types import SimpleNamespace

from services.channel_list_resolver import resolve_channel_lists

ALT = {"active_metrics": [{"metric_id": "temperature", "aggregation": "max"},
                          {"metric_id": "gust", "aggregation": "max"}]}


# ---------------------------------------------------------------------------
# Resolver: Block-Schalter des Altbestands
# ---------------------------------------------------------------------------

def test_altbestand_outlook_enabled_false_heisst_block_entfaellt():
    """#3277: der Abo-Schalter ``outlook_enabled`` ist entfallen (ADR-0124
    Nr. 6); "Ausblick aus" heisst Tabelle ohne Briefing in
    ``outlook_reports`` -> ``outlook == ()`` (Block entfaellt). Ohne Tabelle
    bleibt die Liste der Grundauswahl wie bisher."""
    from tests.helpers.tabelle_aus_wunsch import tabelle

    aus = {**ALT, "placements": tabelle(ALT, "compare", outlook_reports=[])}
    assert resolve_channel_lists(aus, "compare").outlook == ()
    bisher = resolve_channel_lists(ALT, "compare")
    assert [z.metric_id for z in bisher.outlook] == ["temperature", "gust"]


def test_altbestand_hourly_enabled_false_heisst_block_entfaellt():
    assert resolve_channel_lists(ALT, "compare", hourly_enabled=False).hourly == ()
    an = resolve_channel_lists(ALT, "compare", hourly_enabled=True)
    assert an.hourly == resolve_channel_lists(ALT, "compare").hourly != ()


def test_altbestand_ausblick_in_jedem_slot():
    """Abos ohne ``placements``: #3237 (ADR-0124 Nr. 3, bewusste Aenderung)
    -- ohne Tabelle gilt die Tabelle aus der Grundauswahl samt Vorbelegung
    des Ausblicks; ist nur das Morgen-Briefing an, steht der Ausblick im
    Morgen-Briefing und nicht im Abend-Briefing (frueher: in jedem Slot)."""
    morgen = resolve_channel_lists(ALT, "compare", "morning", enabled_reports=["morning"])
    assert [z.metric_id for z in morgen.outlook] == ["temperature", "gust"]
    abend = resolve_channel_lists(ALT, "compare", "evening", enabled_reports=["morning"])
    assert abend.outlook == ()


# ---------------------------------------------------------------------------
# Render-Optionen: Briefing-Typ wirkt, Block-Entscheidung aus dem View-Model
# ---------------------------------------------------------------------------

def _tabelle(**dc) -> dict:
    return {"id": "p", "morning_enabled": True, "morning_time": "07:00:00",
            "evening_enabled": True, "evening_time": "18:00:00",
            "display_config": {**ALT, "placements": {"version": 1, "rows": [
                {"metric_id": "gust", "places": {"email": True},
                 "formats": {"outlook": "simplified"}}], **dc}}}


def test_render_optionen_ausblick_je_briefing_typ():
    from services.report_config_resolver import resolve_compare_render_options

    abend = resolve_compare_render_options(_tabelle(), report_type="evening")
    assert abend.outlook_enabled is True
    assert abend.outlook_metrics == ["gust", "temperature"]
    assert abend.outlook_metric_formats == {"gust": True}
    morgen = resolve_compare_render_options(_tabelle(), report_type="morning")
    assert morgen.outlook_enabled is False


def test_render_optionen_nur_morgen_eingeschaltet_vorbelegung_morgen():
    from services.report_config_resolver import resolve_compare_render_options

    p = _tabelle()
    p["evening_enabled"] = False
    assert resolve_compare_render_options(p, report_type="morning").outlook_enabled is True
    assert resolve_compare_render_options(p, report_type="evening").outlook_enabled is False


def test_render_optionen_altbestand_outlook_enabled_false():
    """#3277: ein gespeichertes Altfeld ``outlook_enabled: false`` wirkt nicht
    mehr (Prod: alle Werte ``true``); es gilt die Grundauswahl-Tabelle."""
    from services.report_config_resolver import resolve_compare_render_options

    alt = resolve_compare_render_options({"id": "p", "display_config": ALT,
                                          "outlook_enabled": False})
    sauber = resolve_compare_render_options({"id": "p", "display_config": ALT})
    assert sauber.outlook_enabled is True
    assert (alt.outlook_enabled, alt.outlook_metrics) == (
        sauber.outlook_enabled, sauber.outlook_metrics)


def test_hinweiszaehler_aus_der_grundauswahl_auch_mit_tabelle():
    """Zaehler nicht zuordenbarer Eintraege: Grundauswahl zaehlt, eine
    Kanal-Altliste wird nicht gelesen -- #3237: auch ohne Tabelle nicht mehr
    (frueher zaehlte sie dort mit, ``email: 2``)."""
    from services.report_config_resolver import resolve_compare_render_options

    p = _tabelle()
    p["display_config"]["active_metrics"] = ALT["active_metrics"] + ["gibt_es_nicht"]
    p["display_config"]["channel_active_metrics"] = {"email": ["auch_nicht"]}
    opts = resolve_compare_render_options(p, report_type="evening")
    assert opts.unresolved_by_channel == {"email": 1, "telegram": 1, "sms": 1}
    alt = resolve_compare_render_options({"id": "p", "display_config": {
        "active_metrics": p["display_config"]["active_metrics"],
        "channel_active_metrics": {"email": ["auch_nicht"]}}})
    assert alt.unresolved_by_channel == {"email": 1, "telegram": 1, "sms": 1}


# ---------------------------------------------------------------------------
# Validator-Render: dieselbe Aufloesung wie der Versand
# ---------------------------------------------------------------------------

def _body(**extra) -> SimpleNamespace:
    return SimpleNamespace(profile="allgemein", time_window=[9, 16],
                           target_date="2026-07-08", winner_tags=[], **extra)


def test_validator_render_auswahl_ohne_sichtbare_spalte_schaltet_block_ab():
    """Wie im Versand (#1366): eine Stundenauswahl nur aus Merge-Signalen
    (Windrichtung) hat keine Wert-Spalte -- der Block entfaellt."""
    from services.validator_render_service import render_compare_email_preview

    html = render_compare_email_preview(_body(hourly_enabled=True,
                                              hourly_metrics=["wind_direction_deg"]))
    assert "STUNDEN" not in html
    assert "STUNDEN" in render_compare_email_preview(_body(hourly_enabled=True))


def test_validator_render_stundenformate_kommen_durch_den_resolver():
    """Roh/Einfach je Stundenverlauf-Groesse aus dem Body geht durch dieselbe
    Aufloesung wie der Versand: nur echte Booleans, nur Groessen der Auswahl
    (Boeen sind nicht gewaehlt). Wirkung am echten Renderer mit Stundendaten
    (der Stub-Ort der Vorschau hat keine)."""
    from output.renderers.email.compare_html import render_compare_html
    from services.validator_render_service import compare_preview_render_kwargs
    from tests.helpers.vergleichs_mail_fixture import build_result

    auswahl = ["t2m_c", "wind10m_kmh"]
    einfach = compare_preview_render_kwargs(_body(
        hourly_enabled=True, hourly_metrics=auswahl,
        hourly_metric_formats={"wind": True, "gust": True, "temperature": "true"}))
    assert einfach["hourly_metric_formats"] == {"wind": True}
    roh = compare_preview_render_kwargs(_body(hourly_enabled=True, hourly_metrics=auswahl))
    assert roh["hourly_metric_formats"] is None
    assert einfach["hourly_metrics"] == roh["hourly_metrics"] == auswahl
    assert render_compare_html(build_result(), **einfach) != render_compare_html(build_result(), **roh)


# ---------------------------------------------------------------------------
# Orte-Alarm: Grundauswahl ueber die Resolver-Hilfe, Tabelle wirkt nicht
# ---------------------------------------------------------------------------

def _alarm_aktiv(preset: dict) -> dict:
    from services.compare_alert import CompareAlertService

    dc = CompareAlertService._display_config_from_active_metrics(None, preset)
    return None if dc is None else {m.metric_id: m.enabled for m in dc.metrics}


def test_orte_alarm_ignoriert_die_tabelle():
    """ADR-0124 Nr. 11: Boeen ohne E-Mail-Haken bleiben fuer den Alarm aktiv."""
    ohne = _alarm_aktiv({"display_config": ALT})
    mit = _alarm_aktiv({"display_config": {**ALT, "placements": {"version": 1, "rows": [
        {"metric_id": "gust", "places": {"email": False, "telegram": False, "sms": False}}],
        "outlook_reports": []}}})
    assert mit == ohne and ohne["gust"] is True and ohne["wind"] is False


def test_orte_alarm_nie_eingestellt_bleibt_none():
    assert _alarm_aktiv({"display_config": {}}) is None
    assert _alarm_aktiv({}) is None
    assert _alarm_aktiv({"display_config": {"active_metrics": []}})["gust"] is False
