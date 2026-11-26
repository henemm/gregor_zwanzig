"""Tabelle "Was steht wo": gespeichertes Format, Aufloesung, Grundauswahl-Tabelle (#3122).

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
Zeile. Ein Abo ohne Tabelle liest die Tabelle aus seiner Grundauswahl
(``placements_aus_grundauswahl``, #3237); Altfelder wirken nicht.

Festlegungen beim Lesen:

* Eine gespeicherte Tabelle liegt vor, sobald ``rows`` eine Liste ist. Auch
  ``rows: []`` oder eine Liste nur mit unlesbaren Eintraegen ist eine Tabelle
  ohne Zeilen: alle Metriken der Grundauswahl stehen hinten, ueberall
  angehakt (Nr. 3.2). Kein Objekt oder keine Liste = keine Tabelle.
* ``outlook_reports`` mit ausschliesslich unbekannten Werten ist leer =
  Ausblick aus. Die Vorbelegung (Nr. 6) greift nur bei fehlendem Schluessel
  (oder falschem Typ).
* ``version`` wird derzeit nicht ausgewertet (geschrieben wird ``1``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from app.metric_catalog import (
    _METRICS_BY_ID, AMPEL_METRIC_IDS, standard_form, stellen_sperre, zwei_formen_stellen,
)

VERSION = 1
STELLEN = ("email", "telegram", "sms", "hourly", "outlook")
STELLEN_TRIP = ("email", "telegram", "sms", "outlook")
FORMAT_STELLEN = ("email", "telegram", "hourly", "outlook")
FORMATE = ("raw", "simplified")
BRIEFINGS = ("morning", "evening")

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
# Tabelle aus der Grundauswahl (#3275 B6b-0, #3237)
# ---------------------------------------------------------------------------

def _feld(obj: object, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def anlage_outlook_reports(display_config: object) -> Optional[tuple[str, ...]]:
    """Marke ``placements.outlook_reports`` ohne ``rows`` (#3155); ``None``: keine."""
    roh = _feld(display_config, "placements")
    if not isinstance(roh, dict):
        return None
    return _read_reports(roh.get("outlook_reports"))


def placements_aus_grundauswahl(
    display_config: object, surface: str, *,
    enabled_reports: Optional[Sequence[str]] = None,
) -> dict:
    """Volle Tabelle aus der Grundauswahl (#3237, ADR-0124): je Metrik der
    Tabellen-Grundauswahl eine Zeile in deren Folge, jede Stelle ausdruecklich
    belegt. Haken und Form je Stelle = was HEUTE ohne Einstellung erscheint
    (Spec #3122 Nr. 4, ``_heute_ohne_einstellung``); ``outlook_reports`` nach
    der Vorbelegung Nr. 6 (Marke gilt; das Altfeld des Abo-Schalters wirkt
    seit #3277 nicht mehr).
    EINE Quelle fuer Anlage, Karte und Abos ohne ``rows``; liest keine
    Altfelder, veraendert die Eingabe nicht."""
    from services.channel_list_resolver import tabellen_grundauswahl

    ids, _eltern = tabellen_grundauswahl(display_config, surface)
    reports = resolve_outlook_reports(anlage_outlook_reports(display_config), enabled_reports)
    places, formen = _heute_ohne_einstellung(display_config, surface, ids, reports)
    rows = [StoredRow(mid, tuple((s, mid in places.get(s, (mid,))) for s in stellen_fuer(surface)),
                      tuple((s, f) for s, f in formen.get(mid, {}).items()))
            for mid in dict.fromkeys(ids)]
    return placements_dict(rows, reports)


def heutige_form(surface: str, stelle: str, metric_id: str, fmt: Optional[str]) -> str:
    """Form, die eine Stelle ohne Tabelle zeigte (Zeilen-Format -> raw|simplified):
    Trip-E-Mail-Ampelgroessen Einfach, sonst Katalog-Standard; Orte,
    Ausblick und Stundenverlauf Roh."""
    if fmt == "raw":
        return "raw"
    if fmt is not None:
        return "simplified"
    if stelle in ("outlook", "hourly") or surface != "trip":
        return "raw"
    if stelle == "email" and metric_id in AMPEL_METRIC_IDS:
        return "simplified"
    return standard_form(metric_id)


def _heute_ohne_einstellung(
    display_config: object, surface: str, ids: Sequence[str], reports: Sequence[str] = (),
):
    """(Haken je Stelle, Formen je Metrik) wie ohne Kanal-Einstellung:
    Trip: Form aus dem Grundauswahl-Eintrag (``format_mode``/
    ``use_friendly_format``), Haken ueberall; Ausblick nur fuer Groessen, die
    ein Briefing aus ``reports`` (``outlook_reports``) fuehrt (#3364; ohne
    Ausblick-Briefing bleibt der Haken wie bisher). Orte: Roh; Ausblick und
    Stundenverlauf nur fuer die bisherigen Vorgabemengen (nie eingestellt:
    feste Ausblick-Spalten bzw. ``HOURLY_DEFAULT_METRIC_IDS``).
    Haken: ``{stelle: menge}``, fehlende Stelle = ueberall an."""
    places: dict = {}
    zeile_fmt: dict = {}
    if surface == "trip":
        from services.channel_list_resolver import _trip_model

        dc = _trip_model(display_config)
        if reports:
            places["outlook"] = set()
        for rt in ("evening", "morning"):
            for mc in dc.get_metrics_for_report_type(rt):
                if rt in reports:
                    places["outlook"].add(mc.metric_id)
                fmt = mc.format_mode if mc.format_mode is not None else (
                    None if mc.use_friendly_format else "raw")
                zeile_fmt.setdefault(mc.metric_id, fmt)
    else:
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metric_ids
        from output.renderers.email.helpers import OUTLOOK_FIXED_METRIC_IDS
        from services.channel_list_resolver import grundauswahl

        grund = grundauswahl(display_config, surface, None)
        renderer = None if grund.nie_eingestellt else sorted(grund.renderer or ())
        if grund.nie_eingestellt:
            places["outlook"] = set(OUTLOOK_FIXED_METRIC_IDS)
        places["hourly"] = set(resolve_hourly_metric_ids(None, renderer))
    formen = {mid: {s: heutige_form(surface, s, mid, zeile_fmt.get(mid))
                    for s in stellen_fuer(surface) if s in zwei_formen_stellen(mid)}
              for mid in ids}
    return places, formen


