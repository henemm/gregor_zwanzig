"""Test-Helfer (#3237): eine Einstellung als Tabelle „Was steht wo“ ausdruecken.

Seit #3237 wirken Altfelder (``channel_layouts``, ``outlook_metrics`` …) nicht
mehr; jede Einstellung je Stelle steht in ``display_config.placements``.
Tests, die bisher „Kanal X zeigt nur A, B in dieser Folge“ ueber ein Altfeld
eingestellt haben, stellen dasselbe hier ueber die Tabelle ein -- gleiche
Aussage, neue Quelle.

Ausgang ist die Tabelle einer Neuanlage (``placements_aus_grundauswahl``:
Haken und Form wie ohne Einstellung); ``listen`` ueberschreibt je Stelle
Haken (in der Liste = an, sonst aus) und Form (``einfach``: True/False/None
= bleibt). Die Zeilenfolge ist EINE Folge fuer alle Stellen (ADR-0124): die
Folge der zuerst genannten Liste, dahinter die uebrige Grundauswahl.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence, Union

Eintrag = Union[str, tuple, Mapping]


def _eintraege(liste: Iterable[Eintrag], *, freundlich_einfach: bool = True,
               ) -> list[tuple[str, Optional[bool]]]:
    """``"wind"`` | ``("wind", True)`` | Altfeld-Eintrag ``{"metric_id",
    "enabled", "use_friendly_format"/"format_mode"/"format"}`` -> (id, einfach).
    ``freundlich_einfach=False`` (Trip): ``use_friendly_format: true`` ohne
    ``format_mode`` hiess Katalog-Standard -> ``None`` (Form wie ohne Einstellung)."""
    out: list[tuple[str, Optional[bool]]] = []
    liste = list(liste)
    if liste and all(isinstance(e, Mapping) for e in liste):
        # Altfeld-Eintraege tragen ihre eingestellte Folge in bucket/order.
        rang = {"primary": 0, "secondary": 1}
        liste.sort(key=lambda e: (rang.get(e.get("bucket", "primary"), 2), e.get("order", 0)))
    for e in liste:
        if isinstance(e, str):
            out.append((e, None))
        elif isinstance(e, tuple):
            out.append((e[0], e[1]))
        else:
            if e.get("enabled", True) is False:
                continue
            fm = e.get("format_mode", e.get("format"))
            freundlich = e.get("use_friendly_format")
            if fm is not None:
                einfach = fm != "raw"
            elif freundlich is False or freundlich_einfach:
                einfach = freundlich
            else:
                einfach = None
            out.append((e["metric_id"], einfach))
    return out


def _ids_aus(roh) -> Optional[list]:
    if not isinstance(roh, list):
        return None
    return list(dict.fromkeys(
        e.get("metric_id") if isinstance(e, Mapping) else e for e in roh
        if isinstance(e, str) or (isinstance(e, Mapping) and isinstance(e.get("metric_id"), str))))


def orte_wunsch_als_tabelle(preset: dict) -> dict:
    """Orts-Vergleich: die Einstellung eines Test-Presets (bisher als
    Altfelder ``channel_layouts``/``channel_active_metrics``,
    ``hourly_metrics``/``hourly_metric_formats``, ``outlook_metrics``/
    ``outlook_metric_formats``) als Tabelle; die Altfelder bleiben als
    Beschreibung im JSON stehen und wirken nicht. Eine Liste, die nach dem
    Schnitt mit der Grundauswahl leer waere, aber nicht leer gespeichert ist,
    stellt nichts ein (Tabelle wie Neuanlage). Ohne Marke zeigt der Ausblick
    beide Briefings wie die Orte-Abos ohne Vorbelegung bisher.
    Presets mit ``placements.rows`` bleiben unveraendert. Rein."""
    import copy

    from services.channel_list_resolver import tabellen_grundauswahl

    p = copy.deepcopy(preset)
    dc = p.setdefault("display_config", {})
    roh_tab = dc.get("placements")
    if isinstance(roh_tab, Mapping) and isinstance(roh_tab.get("rows"), list):
        return p
    grund = set(tabellen_grundauswahl(dc, "compare")[0])
    listen: dict = {}

    def setze(stelle, eintraege, formate=None):
        ids = _ids_aus(eintraege)
        if ids is None:
            return
        an = [m for m in ids if m in grund]
        if ids and not an:
            return
        if eintraege and all(isinstance(e, Mapping) for e in eintraege) \
                and any("enabled" in e for e in eintraege):
            # Kanal-Layout: ``enabled: false`` = aus; Groessen der Grundauswahl
            # ohne jeden Eintrag folgen hinten (#3039 AC-14).
            erfasst = {e["metric_id"] for e in eintraege}
            listen[stelle] = [(m, einfach) for m, einfach in _eintraege(eintraege)
                              if m in grund] + [
                m for m in tabellen_grundauswahl(dc, "compare")[0] if m not in erfasst]
            return
        if eintraege and all(isinstance(e, Mapping) for e in eintraege) and any(
                k in e for e in eintraege for k in ("format", "format_mode")):
            # Kanal-Layout mit Form je Eintrag (``format``/``format_mode``), ohne
            # ``enabled``: Teilauswahl in Listenfolge, Form aus dem Eintrag.
            listen[stelle] = [(m, einfach) for m, einfach in _eintraege(eintraege)
                              if m in grund]
            return
        f = formate if isinstance(formate, Mapping) else {}
        listen[stelle] = [(m, f[m] if isinstance(f.get(m), bool) else None) for m in an]

    layouts = dc.get("channel_layouts") if isinstance(dc.get("channel_layouts"), Mapping) else {}
    cam = dc.get("channel_active_metrics") if isinstance(dc.get("channel_active_metrics"), Mapping) else {}
    for stelle in ("email", "telegram", "sms"):
        setze(stelle, layouts.get(stelle) if stelle in layouts else cam.get(stelle))
    setze("hourly", dc.get("hourly_metrics"), dc.get("hourly_metric_formats"))
    setze("outlook", dc.get("outlook_metrics"), dc.get("outlook_metric_formats"))
    for stelle, feld in (("hourly", "hourly_metric_formats"), ("outlook", "outlook_metric_formats")):
        formate = dc.get(feld)
        if stelle in listen or not isinstance(formate, Mapping):
            continue
        basis = tabelle(dc, "compare")
        listen[stelle] = [
            (r["metric_id"], formate[r["metric_id"]] if isinstance(
                formate.get(r["metric_id"]), bool) else None)
            for r in basis["rows"] if r.get("places", {}).get(stelle, True)]
    marke = roh_tab.get("outlook_reports") if isinstance(roh_tab, Mapping) else None
    berichte = marke if isinstance(marke, list) else ["morning", "evening"]
    if p.get("outlook_enabled") is False:
        berichte = []
    dc["placements"] = tabelle(dc, "compare", listen=listen, outlook_reports=berichte,
                               folge=[m for m, *_ in (_eintraege(listen["email"])
                                                       if "email" in listen else [])] or None)
    return p


def trip_wunsch_als_tabelle(trip: dict) -> dict:
    """Trip-JSON: Kanal-Listen aus ``channel_layouts`` (``sms``, ``telegram``,
    ``email``) und ``outlook_metrics``/``outlook_metric_formats`` als Tabelle;
    Zeilenfolge wie bei der frueheren Umrechnung (SMS, dann Telegram, dann
    E-Mail, dann Grundauswahl -- Spec #3122 Nr. 8). Altfelder bleiben als
    Beschreibung stehen. Trips mit ``placements.rows`` bleiben unveraendert. Rein."""
    import copy

    t = copy.deepcopy(trip)
    dc = t.setdefault("display_config", {})
    roh_tab = dc.get("placements")
    if isinstance(roh_tab, Mapping) and isinstance(roh_tab.get("rows"), list):
        return t
    layouts = dc.get("channel_layouts") if isinstance(dc.get("channel_layouts"), Mapping) else {}
    listen = {s: layouts[s] for s in ("sms", "telegram", "email") if isinstance(layouts.get(s), list)}
    ausblick = dc.get("outlook_metrics")
    formate = dc.get("outlook_metric_formats")
    if isinstance(ausblick, list):
        f = formate if isinstance(formate, Mapping) else {}
        listen["outlook"] = [(m, f[m] if isinstance(f.get(m), bool) else None)
                             for m in _ids_aus(ausblick)]
    folge = next(([m for m, _ in _eintraege(listen[s])] for s in ("sms", "telegram", "email")
                  if listen.get(s)), None)
    if folge is None:
        metriken = [mc for mc in dc.get("metrics") or [] if isinstance(mc, Mapping)]
        folge = [e for e, _ in _eintraege(metriken)] or None
    dc["placements"] = tabelle(dc, "trip", listen=listen, folge=folge)
    return t


def tabelle(
    display_config, surface: str, *,
    listen: Optional[Mapping[str, Sequence[Eintrag]]] = None,
    outlook_reports: Optional[Sequence[str]] = None,
    folge: Optional[Sequence[str]] = None,
) -> dict:
    """Speicherform ``placements`` fuer ``display_config`` (dict oder Modell)."""
    from services.placements import FORMAT_STELLEN, placements_aus_grundauswahl

    basis = placements_aus_grundauswahl(display_config, surface)
    zeilen = {r["metric_id"]: {"metric_id": r["metric_id"],
                               "places": dict(r.get("places") or {}),
                               "formats": dict(r.get("formats") or {})}
              for r in basis["rows"]}
    listen = {s: _eintraege(lst, freundlich_einfach=surface != "trip")
              for s, lst in (listen or {}).items()}
    for stelle, lst in listen.items():
        an = dict(lst)
        for mid, z in zeilen.items():
            z["places"][stelle] = mid in an
            einfach = an.get(mid)
            if mid in an and einfach is not None and stelle in FORMAT_STELLEN:
                z["formats"][stelle] = "simplified" if einfach else "raw"
    # Abgeleitete Zeilen (z. B. ``temperature_night``) folgen dem Haken ihrer
    # Eltern-Metrik, wie in der Grundauswahl.
    from services.channel_list_resolver import tabellen_grundauswahl

    eltern = tabellen_grundauswahl(display_config, surface)[1]
    for kind, vater in eltern.items():
        if kind in zeilen and vater in zeilen:
            for stelle in listen:
                zeilen[kind]["places"][stelle] = zeilen[vater]["places"][stelle]
    vorne = list(folge or next((
        [m for m, _ in lst] for lst in listen.values() if lst), []))
    reihen = [m for m in dict.fromkeys(vorne) if m in zeilen]
    reihen += [m for m in zeilen if m not in reihen]
    kinder = {v: [k for k in zeilen if eltern.get(k) == v] for v in set(eltern.values())}
    reihen = [x for m in reihen if m not in eltern or eltern[m] not in zeilen
              for x in [m, *kinder.get(m, [])]]
    out = {**basis, "rows": [zeilen[m] for m in reihen]}
    if outlook_reports is not None:
        out["outlook_reports"] = list(outlook_reports)
    return out


def trip_modell_als_tabelle(dc, *, outlook_reports: Optional[Sequence[str]] = None):
    """Trip-Modell (``UnifiedWeatherDisplayConfig``): die Einstellung der
    Altfelder ``outlook_metrics``/``outlook_metric_formats`` und
    ``per_channel_layouts`` (``sms``/``telegram``/``email``) als Tabelle in
    ``dc.placements`` (Kopie). ``outlook_metrics=None`` und keine Formate:
    Ausblick wie Neuanlage. Eine Ausblick-Liste gilt genau (Metriken ausserhalb
    der Grundauswahl haben keine Zeile, es gibt keinen Rueckfall); ihre Folge
    ist die EINE Zeilenfolge, wenn sie von der Grundauswahl abweicht.
    ``outlook_reports`` (z. B. aus ``multi_day_trend_reports``): Briefings mit
    Ausblick; gesetzt, entsteht immer eine Tabelle.
    Seit #3277 sind die Altfelder keine Modellfelder mehr: gelesen werden
    gewoehnliche Attribute (``WUNSCH_ATTRIBUTE``, ``mit_wunsch``), sie bleiben
    als Beschreibung stehen. Rein."""
    import dataclasses

    listen: dict = {}
    layouts = getattr(dc, "per_channel_layouts", None) or {}
    for stelle in ("sms", "telegram", "email"):
        eintraege = layouts.get(stelle) if isinstance(layouts, Mapping) else None
        if isinstance(eintraege, list):
            # ``MetricConfig`` -> Altfeld-Eintrag (Folge aus bucket/order, Form).
            listen[stelle] = [e if isinstance(e, (str, Mapping)) else {
                "metric_id": e.metric_id, "enabled": e.enabled,
                "bucket": getattr(e, "bucket", "primary"), "order": getattr(e, "order", 0),
                **({"format_mode": e.format_mode} if getattr(e, "format_mode", None) else {}),
            } for e in eintraege]
    ausblick = getattr(dc, "outlook_metrics", None)
    formate = getattr(dc, "outlook_metric_formats", None)
    f = formate if isinstance(formate, Mapping) else {}
    if isinstance(ausblick, list):
        listen["outlook"] = [(m, f[m] if isinstance(f.get(m), bool) else None)
                             for m in _ids_aus(ausblick)]
    elif f:
        basis = tabelle(dc, "trip")
        listen["outlook"] = [
            (r["metric_id"], f[r["metric_id"]] if isinstance(f.get(r["metric_id"]), bool) else None)
            for r in basis["rows"] if r.get("places", {}).get("outlook", True)]
    from services.channel_list_resolver import tabellen_grundauswahl

    grund = tabellen_grundauswahl(dc, "trip")[0]
    folge = grund
    if isinstance(ausblick, list):
        ids = [m for m, _ in listen["outlook"] if m in grund]
        if ids != [m for m in grund if m in ids]:
            folge = ids
    if not listen and outlook_reports is None:
        return dc
    neu = dataclasses.replace(dc, placements=tabelle(
        dc, "trip", listen=listen, outlook_reports=outlook_reports, folge=folge))
    # #3277: die Wunsch-Beschreibung (keine Modellfelder mehr) reist mit, damit
    # ein zweiter Aufruf (z. B. Formate nach der Auswahl) beide kennt.
    for name in WUNSCH_ATTRIBUTE:
        if name in vars(dc):
            setattr(neu, name, vars(dc)[name])
    return neu


#: #3277: Namen der frueheren Modellfelder, die Tests als WUNSCH-Beschreibung
#: an ein ``UnifiedWeatherDisplayConfig`` haengen (gewoehnliche Attribute,
#: keine Datenklassen-Felder). Das Produkt liest sie nicht; wirksam ist allein
#: die daraus gebaute Tabelle (``trip_modell_als_tabelle``).
WUNSCH_ATTRIBUTE = ("outlook_metrics", "outlook_metric_formats", "per_channel_layouts")


def mit_wunsch(dc, **wunsch):
    """Kopie von ``dc`` mit Wunsch-Beschreibung (``WUNSCH_ATTRIBUTE``) und der
    daraus gebauten Tabelle (#3277: ersetzt ``dataclasses.replace`` mit den
    entfernten Modellfeldern)."""
    import copy

    unbekannt = set(wunsch) - set(WUNSCH_ATTRIBUTE)
    assert not unbekannt, f"kein Wunsch-Attribut: {sorted(unbekannt)}"
    neu = copy.copy(dc)
    for name, wert in wunsch.items():
        setattr(neu, name, wert)
    return trip_modell_als_tabelle(neu)
