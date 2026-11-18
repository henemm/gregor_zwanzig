"""Tabelle "Was steht wo": gespeichertes Format, Aufloesung, Umrechnung (#3122).

ADR-0124, Spec ``docs/specs/modules/feat_3122_was_steht_wo.md`` Teil A.
``display_config.placements`` (Trip und Orte gleich)::

    {"version": 1,
     "rows": [{"metric_id": "wind",
               "places": {"email": true, "sms": false, ...},
               "formats": {"email": "simplified", ...}}],
     "outlook_reports": ["evening"]}

Reine Funktionen: kein I/O, keine Mutation der Eingaben. Gelesen wird
robust (Nr. 1): unbekannte Metriken, Stellen, Formate und falsche Typen haben
keine Wirkung und werfen nicht; bei doppelter ``metric_id`` zaehlt die erste
Zeile. ``placements_from_legacy`` ist die EINZIGE Umrechnung der Altfelder
(Nr. 8); sie liest den bisherigen Pfad des Kanal-Listen-Resolvers.

Festlegungen beim Lesen:

* Eine gespeicherte Tabelle liegt vor, sobald ``rows`` eine Liste ist. Auch
  ``rows: []`` oder eine Liste nur mit unlesbaren Eintraegen ist eine Tabelle
  ohne Zeilen: alle Metriken der Grundauswahl stehen hinten, ueberall
  angehakt (Nr. 3.2). Kein Objekt oder keine Liste = Altbestand.
* ``outlook_reports`` mit ausschliesslich unbekannten Werten ist leer =
  Ausblick aus. Die Vorbelegung (Nr. 6) greift nur bei fehlendem Schluessel
  (oder falschem Typ).
* ``version`` wird derzeit nicht ausgewertet (geschrieben wird ``1``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from app.metric_catalog import (
    _METRICS_BY_ID, SMS_FORMAT_MODE_METRIC_IDS, standard_form, stellen_sperre,
    zwei_formen_stellen,
)

VERSION = 1
STELLEN = ("email", "telegram", "sms", "hourly", "outlook")
STELLEN_TRIP = ("email", "telegram", "sms", "outlook")
FORMAT_STELLEN = ("email", "telegram", "hourly", "outlook")
FORMATE = ("raw", "simplified")
BRIEFINGS = ("morning", "evening")

# Arten bewusster Ausgabe-Aenderungen der Umrechnung (Spec Nr. 8: die vier
# ersten; danach Folgen weiterer Festlegungen, s. placements_from_legacy).
REIHENFOLGE_WIE_SMS = "reihenfolge_wie_sms"
OHNE_EMAIL_ENTFAELLT = "ohne_email_entfaellt"
NUR_TEXT_FOLGT_HTML = "nur_text_folgt_html"
SMS_WOLKENFORM_ENTFAELLT = "sms_wolkenform_entfaellt"
AUSWERTUNGEN_GEKOPPELT = "auswertungen_gekoppelt"
AUSSERHALB_GRUNDAUSWAHL = "ausserhalb_grundauswahl"
MORGEN_FOLGT_ABEND = "morgen_folgt_abend"
PREMIUM_FOLGT_SMS = "premium_folgt_sms"
# Altzeile an einer Stelle ohne eigene Ausgabe (Nr. 5), z. B. Nachttief in der
# Stundentabelle der Trip-Mail: sie zeigte dort nichts und entfaellt.
GESPERRTE_STELLE_ENTFAELLT = "gesperrte_stelle_entfaellt"
# Nacht-/Tagesgroesse ohne eigene Spalte (Trip-Mail): sie folgt der
# Grundauswahl und ist in der E-Mail-Spalte nicht abwaehlbar; eine Kanal-Liste,
# die sie weggelassen hatte, verliert diese Wirkung (#3122 Fix-Loop B1b).
OHNE_SPALTE_FOLGT_GRUNDAUSWAHL = "ohne_spalte_folgt_grundauswahl"
UNERKLAERT = "unerklaert"


def stellen_fuer(surface: str) -> tuple[str, ...]:
    """Stellen der Tabelle je Flaeche; Stundenverlauf nur bei Orten."""
    return STELLEN_TRIP if surface == "trip" else STELLEN


# ---------------------------------------------------------------------------
# Gespeichertes Format lesen und schreiben
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StoredRow:
    """Eine gespeicherte Zeile, nur mit gueltigen Eintraegen."""
    metric_id: str
    places: tuple[tuple[str, bool], ...] = ()
    formats: tuple[tuple[str, str], ...] = ()

    def place(self, stelle: str) -> Optional[bool]:
        return dict(self.places).get(stelle)

    def format(self, stelle: str) -> Optional[str]:
        return dict(self.formats).get(stelle)


@dataclass(frozen=True)
class StoredPlacements:
    rows: tuple[StoredRow, ...]
    outlook_reports: Optional[tuple[str, ...]]  # None = Schluessel fehlt


def _read_row(entry: object) -> Optional[StoredRow]:
    if not isinstance(entry, dict):
        return None
    metric_id = entry.get("metric_id")
    definition = _METRICS_BY_ID.get(metric_id) if isinstance(metric_id, str) else None
    if definition is None or not definition.selectable:
        return None
    places, formats = entry.get("places"), entry.get("formats")
    return StoredRow(
        metric_id,
        tuple((s, v) for s, v in places.items() if s in STELLEN and isinstance(v, bool))
        if isinstance(places, dict) else (),
        tuple((s, v) for s, v in formats.items() if s in FORMAT_STELLEN and v in FORMATE)
        if isinstance(formats, dict) else (),
    )


def _read_reports(raw: object) -> Optional[tuple[str, ...]]:
    if not isinstance(raw, list):
        return None
    return tuple(r for r in BRIEFINGS if r in raw)


def read_placements(raw: object) -> Optional[StoredPlacements]:
    """``display_config["placements"]`` -> gepruefter Stand, oder ``None``,
    wenn es keine lesbare Zeilenliste gibt (dann gilt der Altbestand)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        return None
    rows: list[StoredRow] = []
    for entry in raw["rows"]:
        row = _read_row(entry)
        if row is not None and all(r.metric_id != row.metric_id for r in rows):
            rows.append(row)
    return StoredPlacements(tuple(rows), _read_reports(raw.get("outlook_reports")))


def placements_dict(rows: Sequence[StoredRow], outlook_reports: Optional[Sequence[str]]) -> dict:
    """Speicherform (vollstaendiger Stand, JSON-faehig)."""
    out_rows = []
    for row in rows:
        eintrag: dict = {"metric_id": row.metric_id}
        if row.places:
            eintrag["places"] = dict(row.places)
        if row.formats:
            eintrag["formats"] = dict(row.formats)
        out_rows.append(eintrag)
    out: dict = {"version": VERSION, "rows": out_rows}
    if outlook_reports is not None:
        out["outlook_reports"] = list(outlook_reports)
    return out


# ---------------------------------------------------------------------------
# Aufloesung (Spec Nr. 3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlacementCell:
    """``state``: on | off | locked | not_in_email; ``format``: raw |
    simplified | None (None = an dieser Stelle nur eine Form)."""
    state: str
    format: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class PlacementRow:
    metric_id: str
    position: int
    cells: tuple[tuple[str, PlacementCell], ...]

    def cell(self, stelle: str) -> PlacementCell:
        return dict(self.cells)[stelle]


def _cell(row: StoredRow, stelle: str, surface: str, email_on: bool) -> PlacementCell:
    sperre = stellen_sperre(row.metric_id, stelle, surface)
    if sperre:
        return PlacementCell("locked", None, sperre)
    fmt = None
    if stelle in zwei_formen_stellen(row.metric_id):
        fmt = row.format(stelle) or standard_form(row.metric_id)
    if stelle in ("hourly", "outlook") and not email_on:
        return PlacementCell("not_in_email", fmt)
    return PlacementCell("off" if row.place(stelle) is False else "on", fmt)


def _resolved_row(row: StoredRow, position: int, surface: str) -> PlacementRow:
    cells: list[tuple[str, PlacementCell]] = []
    email_on = False
    for stelle in stellen_fuer(surface):
        cell = _cell(row, stelle, surface, email_on)
        if stelle == "email":
            email_on = cell.state == "on"
        cells.append((stelle, cell))
    return PlacementRow(row.metric_id, position, tuple(cells))


def _ordered_rows(
    stored: Sequence[StoredRow], grund: list[str], parents: Mapping[str, str],
) -> list[StoredRow]:
    """Nr. 3.1/3.2 und Nr. 2: Zeilen der Grundauswahl in gespeicherter Folge;
    abgeleitete Groessen ohne Zeile direkt hinter ihrer Eltern-Zeile (mit
    deren Haken); jede weitere Metrik der Grundauswahl hinten, ueberall an."""
    erlaubt = set(grund)
    ordered = [r for r in stored if r.metric_id in erlaubt]
    have = {r.metric_id for r in ordered}
    for mid in grund:
        parent = parents.get(mid)
        if mid in have or parent not in have:
            continue
        idx = next(i for i, r in enumerate(ordered) if r.metric_id == parent)
        while idx + 1 < len(ordered) and parents.get(ordered[idx + 1].metric_id) == parent:
            idx += 1
        vorbild = ordered[next(i for i, r in enumerate(ordered) if r.metric_id == parent)]
        ordered.insert(idx + 1, StoredRow(mid, vorbild.places, vorbild.formats))
        have.add(mid)
    ordered.extend(StoredRow(mid) for mid in grund if mid not in have)
    return ordered


def resolve_rows(
    stored: Sequence[StoredRow], grundauswahl: Sequence[str], surface: str,
    *, parents: Optional[Mapping[str, str]] = None,
) -> tuple[PlacementRow, ...]:
    """Tabellen-Zeilen: je Metrik der Grundauswahl (Katalog-IDs, Maximum) die
    Zustaende je Stelle. Leer bleibt leer, es gibt keinen Rueckfall."""
    grund = list(dict.fromkeys(grundauswahl))
    ordered = _ordered_rows(stored, grund, parents or {})
    return tuple(_resolved_row(r, i, surface) for i, r in enumerate(ordered))


#: Sperrgrund ohne Wegfall: die Groesse hat an der Stelle keine eigene Spalte
#: (Nacht-/Tagesgroessen in der Stundentabelle der Trip-Mail), gehoert aber
#: weiter zur Ausgabe (Kurz-Zusammenfassung u. a.) und folgt dort der
#: Grundauswahl. Gesperrt ist nur der Haken (#3122 Fix-Loop B1b).
OHNE_EIGENE_SPALTE = "keine_eigene_spalte"


def bleibt_in_ausgabe(grund: Optional[str]) -> bool:
    """Gesperrte Stelle, an der die Groesse trotzdem zur Ausgabe gehoert."""
    return grund == OHNE_EIGENE_SPALTE


def metrics_at(rows: Sequence[PlacementRow], stelle: str) -> list[tuple[str, Optional[str]]]:
    """(Katalog-ID, Format) der Zeilen, die an ``stelle`` gelten, in Folge;
    dazu Zeilen, deren Stelle nur mangels eigener Spalte gesperrt ist."""
    out = []
    for row in rows:
        cells = dict(row.cells)
        zelle = cells.get(stelle)
        if zelle is not None and (zelle.state == "on" or (
                zelle.state == "locked" and bleibt_in_ausgabe(zelle.reason))):
            out.append((row.metric_id, zelle.format))
    return out


def resolve_outlook_reports(
    stored: Optional[Sequence[str]], enabled_reports: Optional[Sequence[str]] = None,
) -> tuple[str, ...]:
    """Nr. 6: gespeichert, sonst Vorbelegung Abend; ist nur das Morgen-
    Briefing eingeschaltet, Morgen."""
    if stored is not None:
        return tuple(r for r in BRIEFINGS if r in stored)
    if enabled_reports is not None and tuple(
        r for r in BRIEFINGS if r in enabled_reports
    ) == ("morning",):
        return ("morning",)
    return ("evening",)


def outlook_applies(
    rows: Sequence[PlacementRow], outlook_reports: Sequence[str], report_type: Optional[str],
) -> bool:
    """Ausblick gilt fuer den Briefing-Typ genau dann, wenn der Typ in
    ``outlook_reports`` steht und mindestens eine Metrik dort gilt.
    ``report_type=None`` (Aufrufer ohne Typ): irgendein Typ."""
    typ_an = bool(outlook_reports) if report_type is None else report_type in outlook_reports
    return typ_an and bool(metrics_at(rows, "outlook"))


# ---------------------------------------------------------------------------
# Umrechnung des Altbestands (Spec Nr. 8)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OutputChange:
    """Eine bewusste Aenderung der Ausgabe durch die Umrechnung.
    ``metric_id`` im Vokabular der Stelle (Orte-Kanaele: Renderer-Kennung);
    ``None`` bei Reihenfolge-Aenderungen."""
    kind: str
    stelle: str
    metric_id: Optional[str]
    report_type: Optional[str]


@dataclass(frozen=True)
class LegacyConversion:
    placements: dict
    changes: tuple[OutputChange, ...]
    # Trip mit ``show_outlook: false`` (nicht Kompakt): ``show_stability``
    # gehoert auf ``false`` -- die Umrechnung schreibt es nicht.
    show_stability_off: bool = False


def _feld(obj: object, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def heutige_form(surface: str, stelle: str, metric_id: str, fmt: Optional[str]) -> str:
    """Die Form, die der bisherige Pfad an ``stelle`` zeigt (Zeilen-Format ->
    raw|simplified). Fuer die E-Mail zaehlt die HTML-Mail; deren Ampelpunkt
    haengt beim Trip an ``use_friendly_format`` (ohne Angabe: Einfach)."""
    from output.renderers.email.helpers import _AMPEL_CAPABLE_METRIC_IDS

    if fmt == "raw":
        return "raw"
    if fmt is not None:
        return "simplified"
    if stelle in ("outlook", "hourly") or surface != "trip":
        return "raw"
    if stelle == "email" and metric_id in _AMPEL_CAPABLE_METRIC_IDS:
        return "simplified"
    return standard_form(metric_id)


def _legacy_outlook_reports(
    dc: object, surface: str, report_config: object,
    enabled_reports: Optional[Sequence[str]], outlook_enabled: Optional[bool],
) -> tuple[list[str], bool]:
    if surface != "trip":
        if outlook_enabled is False or _feld(dc, "outlook_metrics") == []:
            return [], False
        return [r for r in BRIEFINGS if enabled_reports is None or r in enabled_reports], False
    if _feld(report_config, "show_outlook") is False:
        return [], _feld(report_config, "email_format", "full") != "compact"
    if _feld(dc, "outlook_metrics") == []:
        return [], False
    reports = _feld(report_config, "multi_day_trend_reports")
    if not isinstance(reports, list):
        reports = _feld(dc, "multi_day_trend_reports")
    if not isinstance(reports, list):
        reports = ["evening"] if _feld(dc, "show_multi_day_trend", True) is not False else []
    return [r for r in BRIEFINGS if r in reports], False


def _legacy_rows(dc: object, surface: str) -> list[StoredRow]:
    """Haken und Form je Stelle aus dem bisherigen Pfad; Folge: SMS, dann
    Telegram, E-Mail, Grundauswahl (Abend-Fassung, Morgen nur fuer Metriken,
    die allein morgens in der Grundauswahl stehen)."""
    from services import channel_list_resolver as clr

    listen = {rt: clr.legacy_lists(dc, surface, rt) for rt in BRIEFINGS}
    grund = {rt: clr.grundauswahl(dc, surface, rt).ids for rt in BRIEFINGS}
    abend = grund["evening"]
    alle = abend + [m for m in grund["morning"] if m not in abend]
    folge = list(dict.fromkeys(
        [m for st in ("sms", "telegram", "email") for m in listen["evening"][st]] + alle
    ))
    rows = []
    for mid in (m for m in folge if m in alle):
        quelle = listen["evening" if mid in abend else "morning"]
        places, formats = [], []
        for stelle in stellen_fuer(surface):
            places.append((stelle, mid in quelle[stelle]))
            if stelle in zwei_formen_stellen(mid):
                formats.append((stelle, heutige_form(surface, stelle, mid,
                                                     quelle[stelle].get(mid))))
        rows.append(StoredRow(mid, tuple(places), tuple(formats)))
    return rows


def legacy_placements(
    display_config: object, surface: str, *, report_config: object = None,
    enabled_reports: Optional[Sequence[str]] = None, outlook_enabled: Optional[bool] = None,
) -> tuple[dict, bool]:
    """Umrechnung ohne Aenderungsliste: (placements, show_stability_off)."""
    reports, stabilitaet_aus = _legacy_outlook_reports(
        display_config, surface, report_config, enabled_reports, outlook_enabled)
    return placements_dict(_legacy_rows(display_config, surface), reports), stabilitaet_aus


def placements_from_legacy(
    display_config: object, surface: str, *, report_config: object = None,
    enabled_reports: Optional[Sequence[str]] = None, outlook_enabled: Optional[bool] = None,
) -> LegacyConversion:
    """Altfelder -> ``placements`` (Spec Nr. 8), samt maschinenlesbarer Liste
    der bewussten Ausgabe-Aenderungen je Abo (fuer den Probelauf der
    Migration, B6). Neben den vier Faellen der Spec meldet sie Folgen anderer
    Festlegungen: ``auswertungen_gekoppelt`` (Orte, Zeile = Katalog-ID, Nr. 2),
    ``ausserhalb_grundauswahl`` (Nr. 3.1), ``morgen_folgt_abend`` (Nr. 8,
    Abend-Fassung zaehlt), ``premium_folgt_sms`` (ADR-0124 Nr. 8),
    ``gesperrte_stelle_entfaellt`` (Altzeile an gesperrter Stelle, Nr. 5),
    ``ohne_spalte_folgt_grundauswahl`` (Nacht-/Tagesgroesse der Trip-Mail); was sich
    keiner Art zuordnen laesst, steht als ``unerklaert`` darin.
    Idempotent: ein Abo mit lesbaren ``placements`` wird nicht umgerechnet."""
    vorhanden = read_placements(_feld(display_config, "placements"))
    if vorhanden is not None:
        return LegacyConversion(placements_dict(vorhanden.rows, vorhanden.outlook_reports), ())
    placements, stabilitaet_aus = legacy_placements(
        display_config, surface, report_config=report_config,
        enabled_reports=enabled_reports, outlook_enabled=outlook_enabled)
    changes = _output_changes(display_config, surface, placements)
    return LegacyConversion(placements, changes, stabilitaet_aus)


# ---------------------------------------------------------------------------
# Aenderungsliste: bisheriger Pfad gegen Umrechnung ueber den neuen Eingang
# ---------------------------------------------------------------------------

def _gekoppelt(cid: str) -> bool:
    from output.renderers.compare_metric_ids import _renderer_ids_for_kennung

    return len(_renderer_ids_for_kennung(cid)) > 1


def _art_entfallen(surface, stelle, cid, rt, ctx) -> str:
    if stelle == "premium_sms":
        return PREMIUM_FOLGT_SMS
    if cid not in ctx["grund"]:
        return AUSSERHALB_GRUNDAUSWAHL
    if stelle in ("outlook", "hourly") and cid not in ctx["neu_email"]:
        return OHNE_EMAIL_ENTFAELLT
    return _art_sonst(surface, cid, rt)


def _art_sonst(surface, cid, rt) -> str:
    if surface != "trip" and _gekoppelt(cid):
        return AUSWERTUNGEN_GEKOPPELT
    if surface == "trip" and rt == "morning":
        return MORGEN_FOLGT_ABEND
    return UNERKLAERT


def _art_folge(surface, stelle, ids, rt) -> str:
    if stelle == "premium_sms":
        return PREMIUM_FOLGT_SMS
    if stelle != "sms":
        return REIHENFOLGE_WIE_SMS
    if surface != "trip" and any(_gekoppelt(c) for c in ids):
        return AUSWERTUNGEN_GEKOPPELT
    return MORGEN_FOLGT_ABEND if surface == "trip" and rt == "morning" else UNERKLAERT


def _stelle_changes(surface, stelle, rt, alt, neu, ctx, kid) -> list[OutputChange]:
    """``alt``/``neu``: ``[(zeile, format)]`` mit Zeile = (Katalog-ID,
    Aggregation) -- verglichen wird je Zeile, gemeldet die Katalog-ID (#3101):
    Max/Min-Doppelzeilen fallen in der Meldung auf eine Kennung zusammen."""
    out = []
    a_ids, n_ids = [m for m, _f in alt], [m for m, _f in neu]
    for mid in [m for m in a_ids if m not in n_ids]:
        out.append(OutputChange(_art_entfallen(surface, stelle, kid(mid), rt, ctx), stelle,
                                kid(mid), rt))
    for mid in [m for m in n_ids if m not in a_ids]:
        art = PREMIUM_FOLGT_SMS if stelle == "premium_sms" else _art_sonst(surface, kid(mid), rt)
        if stelle == "email" and bleibt_in_ausgabe(stellen_sperre(kid(mid), stelle, surface)):
            art = OHNE_SPALTE_FOLGT_GRUNDAUSWAHL
        out.append(OutputChange(art, stelle, kid(mid), rt))
    if set(a_ids) == set(n_ids) and a_ids != n_ids:
        out.append(OutputChange(_art_folge(surface, stelle, [kid(m) for m in n_ids], rt),
                                stelle, None, rt))
    alt_form = dict(alt)
    for mid, form in neu:
        c = kid(mid)
        if mid in alt_form and stelle in zwei_formen_stellen(c) and form != heutige_form(
                surface, stelle, c, alt_form[mid]):
            art = MORGEN_FOLGT_ABEND if surface == "trip" and rt == "morning" else UNERKLAERT
            out.append(OutputChange(art, stelle, c, rt))
    return out


def _regel_changes(surface, stelle, rt, alt, neu, kid) -> list[OutputChange]:
    """Die zwei Faelle, die das View-Model nicht als Abweichung zeigt:
    Nur-Text-Mail folgt der HTML-Mail (Trip, Ampel-Groessen auf Einfach) und
    die in der SMS abweichend gewaehlte Wolken-Form."""
    from output.renderers.email.helpers import _AMPEL_CAPABLE_METRIC_IDS

    out = []
    if stelle == "email" and surface == "trip":
        out += [OutputChange(NUR_TEXT_FOLGT_HTML, "email", kid(m), None) for m, f in neu
                if kid(m) in _AMPEL_CAPABLE_METRIC_IDS and f == "simplified"]
    if stelle == "sms":
        for mid, fmt in alt:
            c = kid(mid)
            standard = standard_form(c) if surface == "trip" else "raw"
            # Bisher zwei Formen in der SMS hatte nur die Bewoelkung (#2422 S6).
            if c in SMS_FORMAT_MODE_METRIC_IDS and heutige_form(surface, "sms", c, fmt) != standard:
                out.append(OutputChange(SMS_WOLKENFORM_ENTFAELLT, "sms", c, rt))
    return out


def _output_changes(dc: object, surface: str, placements: dict) -> tuple[OutputChange, ...]:
    from services import channel_list_resolver as clr

    stored = read_placements(placements)
    reports = stored.outlook_reports or ()
    out: list[OutputChange] = []
    for rt in BRIEFINGS:
        alt = clr.vm_lists(clr.legacy_view(dc, surface, rt), surface, paare=True)
        if rt not in reports:
            alt["outlook"] = []
        neu = clr.vm_lists(clr.placements_view(dc, surface, rt, stored), surface, paare=True)

        def kid(zeile):
            return zeile[0]
        ctx = {"grund": set(clr.grundauswahl(dc, surface, rt).ids),
               "neu_email": {kid(m) for m, _f in neu["email"]}}
        for stelle in neu:
            sperr_stelle = "sms" if stelle == "premium_sms" else stelle

            def entfaellt(m, _s=sperr_stelle):
                grund = stellen_sperre(kid(m), _s, surface)
                return bool(grund) and not bleibt_in_ausgabe(grund)

            a = [(m, f) for m, f in alt[stelle] if not entfaellt(m)]
            out += [OutputChange(GESPERRTE_STELLE_ENTFAELLT, stelle, kid(m), rt)
                    for m, _f in alt[stelle] if entfaellt(m)]
            out += _stelle_changes(surface, stelle, rt, a, neu[stelle], ctx, kid)
            out += _regel_changes(surface, stelle, rt, a, neu[stelle], kid)
    return tuple(dict.fromkeys(out))
