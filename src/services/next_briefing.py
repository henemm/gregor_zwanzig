"""„Naechstes Briefing" — die EINE Ableitung des echten Versandzeitpunkts je
Trip und Ortsvergleich (Issue #1969).

SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md

Keine eigene Faelligkeitsregel: jeder Kandidat wird vom Scheduler-Praedikat
bestaetigt — Trip ueber ``trip_report_scheduler.trip_slot_due`` (dieselbe Regel
wie ``trip_briefing_due_at``), Ortsvergleich ueber
``compare_slot_scheduler.presets_due_for_hour``. Rein lesend: kein Schreiben in
den ``BriefingSlotStore``, kein Verbrauch von ``skip_next``, keine Persistenz
(ADR-0051 Regel 1). Zeit kommt nur als Parameter herein (ADR-0051 Regel 3).

Ausgabe ist ein reines dict im eingefrorenen Format (Vertrag fuer #2346);
nicht zutreffende Felder fehlen.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterator, Optional

from utils.timezone import UTC, local_dt, to_utc

if TYPE_CHECKING:
    from app.trip import Trip
    from services.briefing_slots import BriefingSlotStore

_SLOTS = ("morning", "evening")
# Ortsvergleich: Obergrenze des Suchfensters (Spec „Ableitung" Punkt 3).
_COMPARE_SUCHTAGE = 14


def _zonenname(tz) -> str:
    return getattr(tz, "key", None) or "UTC"


def _termin(vor_ort: datetime, slot: str) -> dict:
    """Termin-Felder aus EINEM Ortsmoment (Datum, Uhrzeit, Zone, Kuerzel)."""
    return {
        "at": vor_ort.isoformat(),
        "local_date": vor_ort.date().isoformat(),
        "local_time": vor_ort.strftime("%H:00"),
        "tz": _zonenname(vor_ort.tzinfo),
        "tz_abbr": vor_ort.tzname() or "UTC",
        "slot": slot,
    }


def _kein_termin(reason: str, paused_until: Optional[date] = None) -> dict:
    out: dict = {"at": None, "reason": reason}
    if paused_until is not None:
        out["paused_until"] = paused_until.isoformat()
    return out


def _aus_treffer(treffer: tuple) -> dict:
    """``treffer`` = (vor_ort, slot, overdue) -> Termin (``overdue`` nur wenn wahr)."""
    vor_ort, slot, overdue = treffer
    out = _termin(vor_ort, slot)
    if overdue:
        out["overdue"] = True
    return out


# ═══════════════════════════════ Trip ═══════════════════════════════


def _trip_kandidaten(trip: "Trip", now_utc: datetime) -> list:
    """(Ortstag, Slot) je Etappe: Vorabend (evening) + Etappentag (morning)."""
    from services.trip_day import trip_local_now

    heute = trip_local_now(trip, now_utc).date()
    tage = sorted({s.date for s in trip.stages if s.date and s.date >= heute - timedelta(days=1)})
    paare = set()
    for d in tage:
        paare.add((d - timedelta(days=1), "evening"))
        paare.add((d, "morning"))
    return sorted(paare, key=lambda p: (p[0], p[1] == "evening"))


def _trip_kandidat_utc(trip: "Trip", ortstag: date, slot: str) -> datetime:
    """Slot-Stunde am Ortstag in der Zone DIESES Tages (DST-Offset des Tages);
    weicht die Anker-Zone des Scheduler-Praedikats ab, wird in ihr neu gerechnet."""
    from services.trip_day import anchor_tz, display_tz
    from services.trip_report_scheduler import _slot_stunde

    stunde = _slot_stunde(trip, slot)
    zone = display_tz(trip, ortstag)
    kandidat = datetime(ortstag.year, ortstag.month, ortstag.day, stunde, tzinfo=zone)
    anker = anchor_tz(trip, to_utc(kandidat))
    if anker != zone:
        kandidat = datetime(ortstag.year, ortstag.month, ortstag.day, stunde, tzinfo=anker)
    return to_utc(kandidat)


def _trip_treffer(
    trip: "Trip", now_utc: datetime, store: "BriefingSlotStore", strict_after: bool,
) -> Iterator[tuple]:
    """Faellige Slots in Zeitfolge — jeder vom Scheduler-Praedikat bestaetigt."""
    from services.trip_day import trip_local_now
    from services.trip_report_scheduler import _slot_stunde, trip_slot_due

    if not strict_after:
        for slot in _SLOTS:
            if trip_slot_due(trip, slot, now_utc, store=store):
                vor_ort = trip_local_now(trip, now_utc)
                at = vor_ort.replace(hour=_slot_stunde(trip, slot), minute=0, second=0, microsecond=0)
                yield at, slot, at < now_utc
    kandidaten = []
    for ortstag, slot in _trip_kandidaten(trip, now_utc):
        moment = _trip_kandidat_utc(trip, ortstag, slot)
        if moment > now_utc:
            kandidaten.append((moment, slot))
    for moment, slot in sorted(kandidaten, key=lambda k: k[0]):
        if trip_slot_due(trip, slot, moment, store=store):
            yield trip_local_now(trip, moment), slot, False


def _trip_vorab_grund(trip: "Trip", now_utc: datetime) -> Optional[dict]:
    """Gruende, die keine Suche brauchen: paused → disabled."""
    from app.models import slot_aktiv
    from services.trip_day import trip_local_now
    from services.trip_report_scheduler import trip_pausiert

    if trip_pausiert(trip, now_utc):
        rc = trip.report_config
        bis = None
        if trip.paused_at is None and rc is not None and rc.paused_until is not None:
            pu = rc.paused_until if rc.paused_until.tzinfo else rc.paused_until.replace(tzinfo=timezone.utc)
            bis = trip_local_now(trip, pu).date()
        return _kein_termin("paused", bis)
    if not any(slot_aktiv(trip.report_config, s) for s in _SLOTS):
        return _kein_termin("disabled")
    return None


def next_trip_briefing(
    trip: "Trip", now_utc: datetime, slot_store: "BriefingSlotStore",
    strict_after: bool = False,
) -> dict:
    """Naechster tatsaechlich versendeter Briefing-Termin eines Trips.

    ``slot_store`` ist der Vermerk-Speicher des Nutzers
    (``BriefingSlotStore(user_id)``) — nur gelesen. ``strict_after=True``
    blendet den gerade laufenden/ueberfaelligen Slot aus.
    """
    from services.trip_day import trip_local_now

    vorab = _trip_vorab_grund(trip, now_utc)
    if vorab is not None:
        return vorab
    # skip_next nur LESEN: der erste faellige Termin entfaellt, `at` zeigt den
    # uebernaechsten, tatsaechlich versendeten (AC-6, PO 2026-10-23).
    skip = trip.report_config is not None and trip.report_config.skip_next is True
    benoetigt = 2 if skip else 1
    treffer = []
    for eintrag in _trip_treffer(trip, now_utc, slot_store, strict_after):
        treffer.append(eintrag)
        if len(treffer) == benoetigt:
            out = _aus_treffer(eintrag)
            if skip:
                erster = _termin(treffer[0][0], treffer[0][1])
                out["skipped"] = {k: erster[k] for k in ("local_date", "local_time", "slot")}
            return out
    heute = trip_local_now(trip, now_utc).date()
    tage = [s.date for s in trip.stages if s.date]
    return _kein_termin("ended" if tage and max(tage) < heute else "none")


# ═══════════════════════════════ Ortsvergleich ═══════════════════════════════


def _compare_vorab_grund(preset: dict) -> Optional[str]:
    """Vorrang manual → paused → disabled → ended (archiviert)."""
    from services.compare_slot_scheduler import resolve_preset_slots

    if preset.get("schedule") == "manual":
        return "manual"
    if preset.get("paused_at"):
        return "paused"
    try:
        slots = resolve_preset_slots(preset)
    except (ValueError, TypeError):
        return "none"
    if not (slots.morning_enabled or slots.evening_enabled):
        return "disabled"
    if preset.get("archived_at"):
        return "ended"
    return None


def _compare_jetzt_faellig(preset: dict, locations: dict, now_utc: datetime,
                           aktiv: list, zone, slot_store) -> Optional[dict]:
    """#1777 AC-20: liegt ``now`` im Fenster eines noch nicht vermerkten
    Slots, ist DIESER der Termin (ueberfaellig, wenn er schon begann)."""
    from services.compare_slot_scheduler import presets_due_for_hour

    due = presets_due_for_hour([preset], locations, now_utc, store=slot_store)
    for stunde, slot, versatz in aktiv:
        if any(d.tage_ab_ortstag == versatz for d in due):
            at = local_dt(now_utc, zone).replace(hour=stunde, minute=0, second=0, microsecond=0)
            return _aus_treffer((at, slot, at < now_utc))
    return None


def next_compare_briefing(
    preset: dict, locations: dict, now_utc: datetime, strict_after: bool = False,
    slot_store: "Optional[BriefingSlotStore]" = None,
) -> dict:
    """Naechster Versandtermin eines Ortsvergleichs (rohes Preset-Dict,
    ``locations`` = ``{location_id: SavedLocation}``). Seit #1777 Fenster und
    Vermerk wie beim Trip (``slot_store`` nur gelesen); ``strict_after=True``
    schliesst ``now`` und den laufenden Slot aus."""
    from services.compare_slot_scheduler import (
        ABEND_SLOT_VERSATZ, MORGEN_SLOT_VERSATZ, _preset_ortszeit,
        presets_due_for_hour, resolve_preset_slots,
    )

    grund = _compare_vorab_grund(preset)
    if grund is not None:
        return _kein_termin(grund)
    slots = resolve_preset_slots(preset)
    zone = _preset_ortszeit(preset, locations, now_utc).tzinfo or UTC
    heute = local_dt(now_utc, zone).date()
    aktiv = []
    if slots.morning_enabled:
        aktiv.append((slots.morning_time.hour, "morning", MORGEN_SLOT_VERSATZ))
    if slots.evening_enabled:
        aktiv.append((slots.evening_time.hour, "evening", ABEND_SLOT_VERSATZ))
    aktiv.sort()
    if not strict_after:
        jetzt = _compare_jetzt_faellig(preset, locations, now_utc, aktiv, zone, slot_store)
        if jetzt is not None:
            return jetzt
    for i in range(_COMPARE_SUCHTAGE + 1):
        tag = heute + timedelta(days=i)
        for stunde, slot, versatz in aktiv:
            vor_ort = datetime(tag.year, tag.month, tag.day, stunde, tzinfo=zone)
            moment = to_utc(vor_ort)
            if moment < now_utc or (strict_after and moment == now_utc):
                continue
            due = presets_due_for_hour([preset], locations, moment, store=slot_store)
            if any(d.tage_ab_ortstag == versatz for d in due):
                return _termin(local_dt(moment, zone), slot)
    return _kein_termin("ended" if preset.get("end_date") else "none")
