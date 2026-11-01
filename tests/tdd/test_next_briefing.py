"""TDD RED — #1969: „Nächstes Briefing" — EINE Ableitung des echten
Versandzeitpunkts je Trip und Ortsvergleich.

Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-1 … AC-11, AC-15)
ADR-0051 (Zone an den Daten, Kürzel sichtbar), ADR-0044 (Ortstag)

Prüfling (existiert vor GREEN nicht): ``services.next_briefing`` mit
``next_trip_briefing(trip, now_utc, slot_store, strict_after=False)`` und
``next_compare_briefing(preset, locations, now_utc, strict_after=False)``.
Der Import steht bewusst IN jedem Test (``_nb()``), damit vor GREEN jede AC
einzeln als FAILED erscheint statt als ein Collection-Error.

Zeit kommt ausschließlich als Parameter ``now_utc`` herein (ADR-0051 Regel 3),
kein freezegun, keine Mocks. Echte Trip-Objekte über den echten Loader
(``load_trip_from_dict`` bzw. Datei + ``load_all_trips``), echter
``BriefingSlotStore`` im per Test isolierten Daten-Root (autouse-Fixture
``_isolate_data_root`` in ``tests/conftest.py``) — DERSELBE Speicher, den das
Scheduler-Prädikat ``trip_briefing_due_at`` intern über ``user_id`` öffnet.
Nur so befragen Anzeige und Orakel in AC-11 dieselbe Welt.

Ortsvergleich: ``preset`` ist das rohe Preset-Dict, ``locations`` ein
``{location_id: SavedLocation}`` — genau die Formen, die
``compare_slot_scheduler.presets_due_for_hour`` konsumiert.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

# Koordinaten je Zone — echte Orte, damit TimezoneFinder sie auflöst
# (Vorbild: tests/tdd/test_briefing_faelligkeit_ortszone.py).
PARIS = (42.30, 8.93)            # Korsika, GR20 -> Europe/Paris
AUCKLAND = (-36.85, 174.76)      # -> Pacific/Auckland
LOS_ANGELES = (34.05, -118.24)   # -> America/Los_Angeles

PARIS_TZ = ZoneInfo("Europe/Paris")
AUCKLAND_TZ = ZoneInfo("Pacific/Auckland")
LA_TZ = ZoneInfo("America/Los_Angeles")

# Freitag, 23.10.2026 — zwei Tage vor der Herbst-Umstellung (So 25.10.2026,
# Europe/Paris CEST +02:00 -> CET +01:00).
D23, D24, D25, D26, D27 = (date(2026, 10, d) for d in (23, 24, 25, 26, 27))

UID = "nb-user"

ERLAUBTE_FELDER = {
    "at", "local_date", "local_time", "tz", "tz_abbr", "slot",
    "skipped", "overdue", "reason", "paused_until",
}
TERMIN_PFLICHTFELDER = {"at", "local_date", "local_time", "tz", "tz_abbr", "slot"}
GRUENDE = {"manual", "paused", "disabled", "ended", "none"}


# ═══════════════════════════════ Helfer ═══════════════════════════════


def _nb():
    """Import des Prüflings — IN jedem Test, nicht auf Modulebene."""
    from services import next_briefing

    return next_briefing


def _lokal(zone: ZoneInfo, tag: date, stunde: int, minute: int = 0) -> datetime:
    """Ortsmoment -> UTC-Zeitpunkt (DST-Versatz DIESES Tages)."""
    return datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=zone).astimezone(
        timezone.utc,
    )


def _trip_dict(
    trip_id: str,
    tage: list[date],
    coords: tuple[float, float] | None = PARIS,
    *,
    morning: str | None = "07:00:00",
    evening: str | None = "18:00:00",
    morning_enabled: bool | None = None,
    evening_enabled: bool | None = None,
    enabled: bool = True,
    paused_until: str | None = None,
    skip_next: bool = False,
    paused_at: str | None = None,
) -> dict:
    """Trip-JSON im Bestandsschema: eine Etappe je Datum, alle am selben Ort.
    ``coords=None`` = Etappen OHNE Wegpunkte (Zone nicht bestimmbar)."""
    rc: dict = {"enabled": enabled, "skip_next": skip_next}
    if morning is not None:
        rc["morning_time"] = morning
    if evening is not None:
        rc["evening_time"] = evening
    if morning_enabled is not None:
        rc["morning_enabled"] = morning_enabled
    if evening_enabled is not None:
        rc["evening_enabled"] = evening_enabled
    if paused_until is not None:
        rc["paused_until"] = paused_until
    # ``coords`` als Liste = je Etappe eigene Koordinaten (Trip über Zonen).
    je_etappe = coords if isinstance(coords, list) else [coords] * len(tage)
    stages = []
    for i, d in enumerate(tage):
        if je_etappe[i] is None:
            wps: list = []
        else:
            lat, lon = je_etappe[i]
            wps = [
                {"id": f"{trip_id}-wp{i}a", "name": "Start",
                 "lat": lat, "lon": lon, "elevation_m": 800},
                {"id": f"{trip_id}-wp{i}b", "name": "Ziel",
                 "lat": lat + 0.05, "lon": lon + 0.05, "elevation_m": 1200},
            ]
        stages.append({
            "id": f"{trip_id}-s{i}", "name": f"Etappe {i}",
            "date": d.isoformat(), "waypoints": wps,
        })
    data = {
        "id": trip_id, "name": f"Trip {trip_id}",
        "stages": stages, "report_config": rc,
    }
    if paused_at is not None:
        data["paused_at"] = paused_at
    return data


def _trip(trip_id: str, tage: list[date], coords=PARIS, **kw):
    from app.loader import load_trip_from_dict

    return load_trip_from_dict(_trip_dict(trip_id, tage, coords, **kw))


def _store():
    """Echter Vermerk-Speicher — derselbe Pfad, den ``trip_briefing_due_at``
    über ``BriefingSlotStore(user_id)`` öffnet (isolierter Daten-Root)."""
    from services.briefing_slots import BriefingSlotStore

    return BriefingSlotStore(UID)


def _at(ergebnis: dict) -> datetime | None:
    roh = ergebnis.get("at")
    if roh is None:
        return None
    wert = datetime.fromisoformat(roh)
    assert wert.tzinfo is not None, f"`at` ohne Offset: {roh!r}"
    return wert


def _termin(ergebnis: dict, erwartet_utc: datetime, zone: ZoneInfo, slot: str) -> None:
    """Prüft die Termin-Felder gegen einen erwarteten UTC-Zeitpunkt in ``zone``."""
    vor_ort = erwartet_utc.astimezone(zone)
    at = _at(ergebnis)
    assert at is not None, f"Kein Termin, erwartet {vor_ort.isoformat()}: {ergebnis!r}"
    assert at == erwartet_utc, f"`at` {at.isoformat()} != erwartet {vor_ort.isoformat()}"
    assert at.utcoffset() == vor_ort.utcoffset(), (
        f"`at` trägt Offset {at.utcoffset()}, die Ortszone an diesem Tag "
        f"{vor_ort.utcoffset()}"
    )
    assert ergebnis["local_date"] == vor_ort.date().isoformat()
    assert ergebnis["local_time"] == vor_ort.strftime("%H:00")
    assert ergebnis["tz"] == zone.key
    assert ergebnis["tz_abbr"] == vor_ort.tzname()
    assert ergebnis["slot"] == slot
    assert "reason" not in ergebnis, f"`reason` bei gesetztem `at`: {ergebnis!r}"


def _ort(loc_id: str, coords):
    from app.user import SavedLocation

    lat, lon = coords
    return SavedLocation(id=loc_id, name=loc_id, lat=lat, lon=lon, elevation_m=500)


def _preset(**overrides) -> dict:
    """Rohes Compare-Preset-Dict (Bestandsschema, vgl.
    tests/tdd/test_compare_preset_slot_dispatch.py)."""
    preset = {
        "id": "preset-nb",
        "kind": "vergleich",
        "name": "Korsika-Vergleich",
        "schedule": "daily",
        "weekday": None,
        "location_ids": ["ort-paris"],
        "archived_at": None,
        "morning_enabled": True,
        "morning_time": "07:00:00",
        "evening_enabled": True,
        "evening_time": "18:00:00",
    }
    preset.update(overrides)
    return preset


def _orte_paris() -> dict:
    return {"ort-paris": _ort("ort-paris", PARIS)}


# ═══════════════════════════════ AC-1 ═══════════════════════════════


def test_ac1_morgen_slot_heute_in_pariser_ortszeit_mit_allen_feldern():
    """AC-1: Paris, Morgen 07:00 / Abend 18:00, Etappe heute, now = 05:00
    Ortszeit ⇒ heute 07:00, tz Europe/Paris, CEST, morning, Offset +02:00."""
    nb = _nb()
    trip = _trip("ac1", [D23, D24])
    now = _lokal(PARIS_TZ, D23, 5)

    r = nb.next_trip_briefing(trip, now, _store())

    assert r["at"] is not None
    assert datetime.fromisoformat(r["at"]) == datetime(2026, 10, 23, 7, tzinfo=PARIS_TZ)
    assert datetime.fromisoformat(r["at"]).utcoffset() == timedelta(hours=2)
    assert r["local_date"] == "2026-10-23"
    assert r["local_time"] == "07:00"
    assert r["tz"] == "Europe/Paris"
    assert r["tz_abbr"] == "CEST"
    assert r["slot"] == "morning"
    assert "reason" not in r
    assert not r.get("overdue")
    assert "skipped" not in r
    json.dumps(r)  # JSON-serialisierbar


# ═══════════════════════════════ AC-2 ═══════════════════════════════


def test_ac2_mittags_ist_der_abend_slot_der_naechste():
    """AC-2: now = 12:00 Ortszeit, Morgen-Slot vermerkt ⇒ heute 18:00 evening."""
    nb = _nb()
    trip = _trip("ac2a", [D23, D24])
    store = _store()
    store.record_outcome(trip.id, "morning", D23, "sent")

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 12), store)

    _termin(r, _lokal(PARIS_TZ, D23, 18), PARIS_TZ, "evening")
    assert not r.get("overdue")


def test_ac2_vermerkter_morgen_slot_erscheint_um_0730_nicht_als_naechster():
    """AC-2: Morgen-Slot im echten BriefingSlotStore vermerkt, now = 07:30 ⇒
    nächster = Abend; derselbe Fall OHNE Vermerk ⇒ Morgen 07:00 überfällig."""
    nb = _nb()
    trip = _trip("ac2b", [D23, D24])
    now = _lokal(PARIS_TZ, D23, 7, 30)

    ohne_vermerk = nb.next_trip_briefing(trip, now, _store())
    _termin(ohne_vermerk, _lokal(PARIS_TZ, D23, 7), PARIS_TZ, "morning")
    assert ohne_vermerk.get("overdue") is True

    store = _store()
    store.record_outcome(trip.id, "morning", D23, "sent")
    mit_vermerk = nb.next_trip_briefing(trip, now, store)
    _termin(mit_vermerk, _lokal(PARIS_TZ, D23, 18), PARIS_TZ, "evening")
    assert not mit_vermerk.get("overdue")


# ═══════════════════════════════ AC-3 ═══════════════════════════════


@pytest.mark.parametrize(
    ("stunde", "minute", "erwartet_stunde", "slot", "overdue"),
    [
        (6, 59, 7, "morning", False),
        (7, 0, 7, "morning", None),      # Fensterbeginn: overdue nicht gepinnt
        (8, 30, 7, "morning", True),
        (9, 59, 7, "morning", True),
        (10, 0, 18, "evening", False),   # Fenster zu
    ],
    ids=["0659", "0700", "0830", "0959", "1000"],
)
def test_ac3_nachholfenster_kante(stunde, minute, erwartet_stunde, slot, overdue):
    """AC-3: Fensterkante ``stunde <= ortsstunde < stunde+3`` — Morgen-Slot
    07:00 nicht vermerkt; 08:30/09:59 ⇒ 07:00 mit overdue, 10:00 ⇒ 18:00."""
    nb = _nb()
    trip = _trip(f"ac3-{stunde}{minute}", [D23, D24])

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, stunde, minute), _store())

    _termin(r, _lokal(PARIS_TZ, D23, erwartet_stunde), PARIS_TZ, slot)
    if overdue is True:
        assert r.get("overdue") is True
    elif overdue is False:
        assert not r.get("overdue")


# ═══════════════════════════════ AC-4 ═══════════════════════════════


def test_ac4_auckland_ortstag_statt_utc_tag():
    """AC-4: Etappen in Pacific/Auckland; 23.10. 12:00 UTC = 24.10. 01:00 NZDT ⇒
    local_date = 24.10. (nicht der UTC-Tag), Auckland-Offset; Gegenprobe Paris
    am selben UTC-Moment ergibt ein anderes local_date."""
    nb = _nb()
    now = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    assert now.astimezone(AUCKLAND_TZ).date() == D24  # Testaufbau diskriminiert

    auckland = _trip("ac4-nz", [D23, D24, D25], AUCKLAND)
    r_nz = nb.next_trip_briefing(auckland, now, _store())
    _termin(r_nz, _lokal(AUCKLAND_TZ, D24, 7), AUCKLAND_TZ, "morning")
    assert r_nz["local_date"] == "2026-10-24"
    assert r_nz["local_date"] != now.date().isoformat()

    paris = _trip("ac4-fr", [D23, D24, D25], PARIS)
    r_fr = nb.next_trip_briefing(paris, now, _store())
    _termin(r_fr, _lokal(PARIS_TZ, D23, 18), PARIS_TZ, "evening")
    assert r_fr["local_date"] != r_nz["local_date"]


# ═══════════════════════════════ AC-5 ═══════════════════════════════


def test_ac5_dst_offset_und_kuerzel_je_kandidatentag():
    """AC-5: Umstellung Europe/Paris am 25.10.2026. Morgen-only-Trip.
    now = 24.10. 05:00 CEST ⇒ 24.10. 07:00 +02:00 CEST;
    now = 24.10. 20:00 CEST (ein Aufruf ÜBER die Umstellung) ⇒
    25.10. 07:00 +01:00 CET — Offset/Kürzel des KANDIDATEN-Tages, nicht von now."""
    nb = _nb()
    trip = _trip("ac5", [D24, D25], morning_enabled=True, evening_enabled=False)

    vor = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D24, 5), _store())
    assert datetime.fromisoformat(vor["at"]).utcoffset() == timedelta(hours=2)
    assert vor["tz_abbr"] == "CEST"
    assert vor["local_time"] == "07:00"
    assert vor["local_date"] == "2026-10-24"

    ueber = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D24, 20), _store())
    assert datetime.fromisoformat(ueber["at"]).utcoffset() == timedelta(hours=1), (
        f"Kandidat 25.10. muss +01:00 tragen (CET), bekam {ueber['at']!r}"
    )
    assert ueber["tz_abbr"] == "CET"
    assert ueber["local_time"] == "07:00"
    assert ueber["local_date"] == "2026-10-25"
    assert datetime.fromisoformat(ueber["at"]) == datetime(2026, 10, 25, 6, tzinfo=timezone.utc)


def test_ac5_zone_je_kandidatentag_bei_zonenwechsel_zwischen_etappen():
    """AC-5 (Zone je Kandidatentag): Etappe 23.10. in Paris, Etappe 24.10. in
    Los Angeles, nur Morgen-Slot, now = 23.10. 12:00 CEST ⇒ 24.10. 07:00 PDT
    (= 14:00 UTC). Eine Ableitung, die die Zone des Start-/now-Tages für alle
    Kandidaten nimmt, landet bei 07:00 Paris (05:00 UTC) — rot."""
    nb = _nb()
    trip = _trip("ac5-zonen", [D23, D24], [PARIS, LOS_ANGELES],
                 morning_enabled=True, evening_enabled=False)

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 12), _store())

    _termin(r, _lokal(LA_TZ, D24, 7), LA_TZ, "morning")
    assert datetime.fromisoformat(r["at"]) == datetime(2026, 10, 24, 14, tzinfo=timezone.utc)
    assert r["tz"] == "America/Los_Angeles"
    assert r["tz_abbr"] == "PDT"


# ═══════════════════════════════ AC-6 ═══════════════════════════════


def test_ac6_skip_next_zeigt_uebernaechsten_termin_und_verbraucht_nichts():
    """AC-6: skip_next=true, now = 05:00 ⇒ at = heute 18:00, skipped = heute
    07:00 morning; skip_next bleibt am Objekt UND in der Datei true."""
    from app.loader import get_briefings_dir, load_all_trips

    nb = _nb()
    data = _trip_dict("ac6", [D23, D24], skip_next=True)
    ordner = get_briefings_dir(UID)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "ac6.json").write_text(json.dumps(data), encoding="utf-8")
    trip = next(t for t in load_all_trips(UID) if t.id == "ac6")
    assert trip.report_config.skip_next is True

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    _termin(r, _lokal(PARIS_TZ, D23, 18), PARIS_TZ, "evening")
    assert r["skipped"] == {
        "local_date": "2026-10-23", "local_time": "07:00", "slot": "morning",
    }
    assert trip.report_config.skip_next is True, "Ableitung hat skip_next am Objekt verändert"
    frisch = next(t for t in load_all_trips(UID) if t.id == "ac6")
    assert frisch.report_config.skip_next is True, "Ableitung hat skip_next persistiert verbraucht"
    assert json.loads((ordner / "ac6.json").read_text(encoding="utf-8"))[
        "report_config"]["skip_next"] is True


# ═══════════════════════════════ AC-7 ═══════════════════════════════


def test_ac7_paused_at_ergibt_reason_paused():
    """AC-7: Trip-Pause (paused_at) ⇒ at=null, reason=paused, kein paused_until."""
    nb = _nb()
    trip = _trip("ac7a", [D23, D24], paused_at="2026-10-22T10:00:00+00:00")

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    assert r["at"] is None
    assert r["reason"] == "paused"
    assert r.get("paused_until") is None


def test_ac7_paused_until_in_drei_tagen_traegt_das_datum():
    """AC-7: paused_until in 3 Tagen ⇒ at=null, reason=paused,
    paused_until = "2026-10-26"."""
    nb = _nb()
    trip = _trip("ac7b", [D23, D24, D25, D26, D27],
                 paused_until="2026-10-26T10:00:00+00:00")

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    assert r["at"] is None
    assert r["reason"] == "paused"
    assert r["paused_until"] == "2026-10-26"


@pytest.mark.parametrize(
    "kw",
    [
        {"enabled": False},
        {"morning_enabled": False, "evening_enabled": False},
    ],
    ids=["gesamtschalter-aus", "beide-slots-aus"],
)
def test_ac7_kein_aktiver_slot_ergibt_reason_disabled(kw):
    """AC-7: kein aktiver Slot ⇒ at=null, reason=disabled."""
    nb = _nb()
    trip = _trip("ac7c", [D23, D24], **kw)

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    assert r["at"] is None
    assert r["reason"] == "disabled"


def test_ac7_alle_etappen_vorbei_ergibt_reason_ended():
    """AC-7: alle Etappen in der Vergangenheit ⇒ at=null, reason=ended."""
    nb = _nb()
    trip = _trip("ac7d", [date(2026, 10, 10), date(2026, 10, 11)])

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    assert r["at"] is None
    assert r["reason"] == "ended"


def test_ac7_pausiert_und_beendet_ergibt_paused_reihenfolge():
    """AC-7: pausiert UND Trip beendet ⇒ paused (Reihenfolge paused vor ended)."""
    nb = _nb()
    trip = _trip("ac7e", [date(2026, 10, 10)], paused_at="2026-10-09T10:00:00+00:00")

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    assert r["at"] is None
    assert r["reason"] == "paused"


def test_ac7_abgeschaltet_und_beendet_ergibt_disabled_reihenfolge():
    """AC-7: Slots aus UND Trip beendet ⇒ disabled (disabled vor ended)."""
    nb = _nb()
    trip = _trip("ac7f", [date(2026, 10, 10)], enabled=False)

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 5), _store())

    assert r["at"] is None
    assert r["reason"] == "disabled"


# ═══════════════════════════════ AC-8 ═══════════════════════════════


def test_ac8_zukunfts_trip_erstes_briefing_ist_der_vorabend():
    """AC-8: erste Etappe in drei Tagen (26.10.) ⇒ erstes Briefing ist der
    Abend-Slot am Vortag (25.10. 18:00, nach der Umstellung CET)."""
    nb = _nb()
    trip = _trip("ac8a", [D26, D27])

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 12), _store())

    _termin(r, _lokal(PARIS_TZ, D25, 18), PARIS_TZ, "evening")


def test_ac8_etappenluecke_wird_uebersprungen():
    """AC-8: Etappen 23.10. und 25.10. (Lücke 24.10.), nur Morgen-Slot,
    now = 23.10. 12:00 ⇒ 25.10. 07:00 (der Lückentag liefert nichts)."""
    nb = _nb()
    trip = _trip("ac8b", [D23, D25], morning_enabled=True, evening_enabled=False)

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 12), _store())

    _termin(r, _lokal(PARIS_TZ, D25, 7), PARIS_TZ, "morning")


def test_ac8_etappenluecke_abend_vor_dem_naechsten_etappentag():
    """AC-8: Lücke 24.10., beide Slots ⇒ 23.10. 18:00 entfällt (keine Etappe am
    24.), 24.10. 07:00 entfällt (keine Etappe), 24.10. 18:00 gilt (Etappe 25.)."""
    nb = _nb()
    trip = _trip("ac8c", [D23, D25])

    r = nb.next_trip_briefing(trip, _lokal(PARIS_TZ, D23, 12), _store())

    _termin(r, _lokal(PARIS_TZ, D24, 18), PARIS_TZ, "evening")


# ═══════════════════════════════ AC-9 ═══════════════════════════════


def _compare_store():
    """Vermerk-Speicher des Ortsvergleichs (Issue #1777, Spec fix_1777
    „Design" Variante B): dieselbe Klasse wie beim Trip, eigene Datei
    ``briefing_slots_compare.json``, Eintragsfeld ``preset_id``."""
    from services.briefing_slots import BriefingSlotStore

    return BriefingSlotStore(
        UID, filename="briefing_slots_compare.json", entity_type="compare", id_key="preset_id",
    )


def test_ac9_compare_daily_im_nachholfenster_ohne_vermerk_ist_ueberfaellig():
    """AC-9 (abgelöst durch #1777 AC-20): daily 07:00/18:00, now = 08:30
    Ortszeit, kein Vermerk ⇒ 07:00 heute, ``overdue`` — die Anzeige folgt dem
    Fälligkeitsfenster wie beim Trip. Früher galt hier „exakte Slot-Stunde,
    kein Nachholfenster" (⇒ 18:00); ADR-0051 erklärt Stundengleichheit für
    Fälligkeit für unzulässig (Spec fix_1777, „Abgelöste Festlegungen" 1)."""
    nb = _nb()
    r = nb.next_compare_briefing(_preset(), _orte_paris(), _lokal(PARIS_TZ, D23, 8, 30))

    _termin(r, _lokal(PARIS_TZ, D23, 7), PARIS_TZ, "morning")
    assert r.get("overdue") is True, r


def test_ac9_compare_daily_mit_vermerk_zeigt_den_abend_slot():
    """#1777 AC-20: derselbe Fall, der Morgen-Slot ist aber bereits vermerkt
    (``sent``) ⇒ 18:00 heute, nicht überfällig. Der Speicher wird nur gelesen."""
    nb = _nb()
    store = _compare_store()
    store.record_outcome("preset-nb", "morning", D23, "sent")

    r = nb.next_compare_briefing(
        _preset(), _orte_paris(), _lokal(PARIS_TZ, D23, 8, 30), slot_store=store,
    )

    _termin(r, _lokal(PARIS_TZ, D23, 18), PARIS_TZ, "evening")
    assert not r.get("overdue")


def test_ac9_compare_weekly_naechster_passender_wochentag():
    """AC-9: weekly, Wochentag Montag (0), now = Fr 23.10. 08:30 ⇒ Mo 26.10.
    07:00 (CET nach der Umstellung)."""
    nb = _nb()
    preset = _preset(schedule="weekly", weekday=0, evening_enabled=False)

    r = nb.next_compare_briefing(preset, _orte_paris(), _lokal(PARIS_TZ, D23, 8, 30))

    _termin(r, _lokal(PARIS_TZ, D26, 7), PARIS_TZ, "morning")
    assert r["tz_abbr"] == "CET"


@pytest.mark.parametrize(
    ("overrides", "now_stunde", "erwartet"),
    [
        ({"end_date": "2026-10-22"}, 5, "ended"),
        # #1777: 10:30 statt 08:30 — um 08:30 läge der 07:00-Slot noch im
        # Fälligkeitsfenster (überfällig statt „ended"); gemeint ist „letzter
        # Slot vorbei".
        ({"end_date": "2026-10-23", "evening_enabled": False}, 10, "ended"),
        ({"schedule": "manual"}, 5, "manual"),
        ({"paused_at": "2026-10-22T10:00:00+00:00"}, 5, "paused"),
        ({"archived_at": "2026-10-22T10:00:00+00:00"}, 5, "ended"),
        ({"morning_enabled": False, "evening_enabled": False}, 5, "disabled"),
        ({"schedule": "manual", "paused_at": "2026-10-22T10:00:00+00:00"}, 5, "manual"),
        ({"paused_at": "2026-10-22T10:00:00+00:00",
          "archived_at": "2026-10-22T10:00:00+00:00"}, 5, "paused"),
    ],
    ids=["end_date-vorbei", "end_date-heute-letzter-slot-vorbei", "manual",
         "paused", "archiviert", "disabled", "manual-vor-paused", "paused-vor-ended"],
)
def test_ac9_compare_gruende_und_vorrang(overrides, now_stunde, erwartet):
    """AC-9: end_date vorbei ⇒ ended; manual ⇒ manual; paused_at ⇒ paused;
    archived_at ⇒ ended; Vorrang manual → paused → disabled → ended."""
    nb = _nb()
    preset = _preset(**overrides)

    r = nb.next_compare_briefing(preset, _orte_paris(), _lokal(PARIS_TZ, D23, now_stunde, 30))

    assert r["at"] is None
    assert r["reason"] == erwartet


def test_ac9_compare_altdaten_ohne_slots_nutzen_den_0600_rueckfall():
    """AC-9: Alt-Preset ohne Slot-Felder ⇒ resolve_preset_slots (06:00 Morgen)."""
    nb = _nb()
    preset = _preset()
    for key in ("morning_enabled", "morning_time", "evening_enabled", "evening_time"):
        preset.pop(key)

    r = nb.next_compare_briefing(preset, _orte_paris(), _lokal(PARIS_TZ, D23, 5, 30))

    _termin(r, _lokal(PARIS_TZ, D23, 6), PARIS_TZ, "morning")


# ═══════════════════════════════ AC-10 ═══════════════════════════════


def test_ac10_ohne_wegpunkte_ehrlicher_utc_rueckfall():
    """AC-10: Trip ohne Wegpunkte ⇒ tz=UTC, tz_abbr=UTC, Offset +00:00."""
    nb = _nb()
    trip = _trip("ac10", [D23, D24], coords=None)
    now = datetime(2026, 10, 23, 5, 0, tzinfo=timezone.utc)

    r = nb.next_trip_briefing(trip, now, _store())

    assert r["at"] is not None
    at = datetime.fromisoformat(r["at"])
    assert at == datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc)
    assert at.utcoffset() == timedelta(0)
    assert r["tz"] == "UTC"
    assert r["tz_abbr"] == "UTC"
    assert r["local_date"] == "2026-10-23"
    assert r["local_time"] == "07:00"
    assert r["slot"] == "morning"


# ═══════════════════════════════ AC-11 ═══════════════════════════════
#
# Orakel = die BESTEHENDE öffentliche Scheduler-Fälligkeit:
#   Trip:    services.trip_report_scheduler.trip_briefing_due_at(trip, m, user_id=)
#   Compare: services.compare_slot_scheduler.presets_due_for_hour([p], orte, m)
# Äquivalenz für jeden Matrix-Zeitpunkt ``now``:
#   * Orakel fällig zu ``now`` ⇒ Anzeige nennt den laufenden Slot
#     (at <= now < at + Fenster, overdue bzw. Fensterbeginn).
#   * sonst ⇒ ``at`` ist der ERSTE volle Stundentakt nach ``now``, zu dem das
#     Orakel „fällig" meldet; kein früherer Takt ist fällig.
#   * ``at is None`` ⇒ in den nächsten Tagen ist kein Takt fällig
#     (Ausnahme ``paused_until`` in der Zukunft: AC-7 verlangt at=null, obwohl
#     der Scheduler nach Ablauf wieder versendet — dort nur „jetzt nicht
#     fällig" + at=null).
# skip_next ist bewusst nicht in der Matrix: das Prädikat ignoriert ihn
# (Docstring trip_briefing_due_at), die Anzeige berücksichtigt ihn (AC-6).

_FENSTER = timedelta(hours=3)
_SCAN_TAGE = 4


def _takte(von: datetime, bis: datetime):
    """Volle UTC-Stunden strikt nach ``von`` und strikt vor ``bis``. Für die
    Matrix-Zonen (Paris, Auckland, Los Angeles, UTC) fallen volle UTC- und
    volle Ortsstunden zusammen."""
    m = von.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while m < bis:
        yield m
        m += timedelta(hours=1)


def _pruefe_trip_aequivalenz(trip, now: datetime, *, pause_in_zukunft: bool = False) -> None:
    from services.trip_report_scheduler import trip_briefing_due_at

    nb = _nb()
    r = nb.next_trip_briefing(trip, now, _store())

    def faellig(m: datetime) -> bool:
        return trip_briefing_due_at(trip, m, user_id=UID)

    at = _at(r)
    if faellig(now):
        assert at is not None, f"Scheduler fällig zu {now}, Anzeige ohne Termin: {r!r}"
        assert at <= now < at + _FENSTER, (
            f"Scheduler fällig zu {now}, Anzeige nennt {at} — nicht der laufende Slot"
        )
        assert at.minute == 0 and at.astimezone(timezone.utc).minute == 0
        if at < now:
            assert r.get("overdue") is True
        return

    if pause_in_zukunft:
        assert at is None and r.get("reason") == "paused", r
        return

    if at is None:
        assert r.get("reason") in GRUENDE, r
        bis = now + timedelta(days=_SCAN_TAGE)
        treffer = next((m for m in _takte(now, bis) if faellig(m)), None)
        assert treffer is None, (
            f"Anzeige: kein Termin ({r.get('reason')}), Scheduler versendet aber zu "
            f"{treffer.isoformat()}"
        )
        return

    assert at > now, f"`at` {at} liegt nicht nach now {now}, obwohl jetzt nichts fällig ist"
    assert faellig(at), f"Anzeige nennt {at.isoformat()}, der Scheduler versendet dann NICHT"
    frueher = next((m for m in _takte(now, at) if faellig(m)), None)
    assert frueher is None, (
        f"Anzeige nennt {at.isoformat()}, der Scheduler versendet aber schon "
        f"{frueher.isoformat()}"
    )


_TRIP_MATRIX = [
    # (id, tage, coords, trip-kw, now, vermerke[(slot, ortstag)], pause_in_zukunft)
    ("paris-0659", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 6, 59), [], False),
    ("paris-0700", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 7), [], False),
    ("paris-0959", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 9, 59), [], False),
    ("paris-1000", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 10), [], False),
    ("paris-0730-vermerkt", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 7, 30),
     [("morning", D23)], False),
    ("paris-1900-abend-vermerkt", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 19),
     [("evening", D23)], False),
    ("paris-paused-at", [D23, D24], PARIS,
     {"paused_at": "2026-10-22T10:00:00+00:00"}, _lokal(PARIS_TZ, D23, 5), [], False),
    ("paris-paused-until-zukunft", [D23, D24, D25], PARIS,
     {"paused_until": "2026-10-24T12:00:00+00:00"}, _lokal(PARIS_TZ, D23, 5), [], True),
    ("paris-paused-until-abgelaufen", [D23, D24], PARIS,
     {"paused_until": "2026-10-23T01:00:00+00:00"}, _lokal(PARIS_TZ, D23, 5), [], False),
    ("paris-abend-braucht-etappe-morgen", [D24], PARIS, {}, _lokal(PARIS_TZ, D23, 12), [], False),
    ("paris-letzte-etappe-heute", [D23], PARIS, {}, _lokal(PARIS_TZ, D23, 12), [], False),
    ("paris-dst-ueber-nacht", [D24, D25], PARIS,
     {"morning_enabled": True, "evening_enabled": False}, _lokal(PARIS_TZ, D24, 20), [], False),
    ("zonenwechsel-paris-la", [D23, D24], [PARIS, LOS_ANGELES],
     {"morning_enabled": True, "evening_enabled": False}, _lokal(PARIS_TZ, D23, 12), [], False),
    ("auckland-datumsgrenze", [D23, D24, D25], AUCKLAND, {},
     datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc), [], False),
    ("auckland-im-fenster-vermerkt", [D23, D24, D25], AUCKLAND, {},
     _lokal(AUCKLAND_TZ, D24, 8), [("morning", D24)], False),
    ("la-im-fenster", [D23, D24], LOS_ANGELES, {}, _lokal(LA_TZ, D23, 8), [], False),
    ("la-abend-0900-slot", [D23, D24], LOS_ANGELES,
     {"morning": "09:00:00", "evening": "20:00:00"}, _lokal(LA_TZ, D23, 12), [], False),
    ("utc-ohne-wegpunkte", [D23, D24], None, {},
     datetime(2026, 10, 23, 11, 0, tzinfo=timezone.utc), [], False),
]


@pytest.mark.parametrize(
    ("tid", "tage", "coords", "kw", "now", "vermerke", "pause_in_zukunft"),
    _TRIP_MATRIX,
    ids=[z[0] for z in _TRIP_MATRIX],
)
def test_ac11_trip_anzeige_gleich_scheduler_praedikat(
    tid, tage, coords, kw, now, vermerke, pause_in_zukunft,
):
    """AC-11 (Trip): Anzeige nennt X ⇔ ``trip_briefing_due_at`` meldet X als
    ersten fälligen Takt — Fensterkante, Vermerk, Pause, Abend=Etappe am
    Folgetag, DST, Auckland, Los Angeles, UTC-Rückfall."""
    trip = _trip(f"ac11-{tid}", tage, coords, **kw)
    store = _store()
    for slot, tag in vermerke:
        store.record_outcome(trip.id, slot, tag, "sent")

    _pruefe_trip_aequivalenz(trip, now, pause_in_zukunft=pause_in_zukunft)


def _pruefe_compare_aequivalenz(preset: dict, orte: dict, now: datetime) -> None:
    from services.compare_slot_scheduler import presets_due_for_hour

    nb = _nb()
    r = nb.next_compare_briefing(preset, orte, now)

    def faellig(m: datetime) -> bool:
        return bool(presets_due_for_hour([preset], orte, m))

    at = _at(r)
    # #1777 AC-20: Fenster wie beim Trip — ist der Scheduler JETZT fällig,
    # nennt die Anzeige den laufenden Slot (überfällig, wenn er schon begann).
    if faellig(now):
        assert at is not None, f"Scheduler fällig zu {now}, Anzeige ohne Termin: {r!r}"
        assert at <= now < at + _FENSTER, (
            f"Scheduler fällig zu {now}, Anzeige nennt {at} — nicht der laufende Slot"
        )
        if at < now:
            assert r.get("overdue") is True, r
        return
    if at is None:
        assert r.get("reason") in GRUENDE, r
        treffer = next(
            (m for m in _takte(now, now + timedelta(days=9)) if faellig(m)), None,
        )
        assert treffer is None, (
            f"Anzeige: kein Termin ({r.get('reason')}), Scheduler versendet aber zu "
            f"{treffer.isoformat()}"
        )
        return
    assert at > now, f"`at` {at} liegt nicht nach now {now}"
    assert faellig(at), f"Anzeige nennt {at.isoformat()}, der Scheduler versendet dann NICHT"
    frueher = next((m for m in _takte(now, at) if faellig(m)), None)
    assert frueher is None, (
        f"Anzeige nennt {at.isoformat()}, der Scheduler versendet aber schon "
        f"{frueher.isoformat()}"
    )


def _orte_auckland() -> dict:
    return {"ort-nz": _ort("ort-nz", AUCKLAND)}


_COMPARE_MATRIX = [
    # now bewusst auf HH:30. Seit #1777 (AC-20) gilt das Fenster wie beim
    # Trip: ist der Scheduler zu ``now`` fällig (07:30, 18:30), nennt die
    # Anzeige den laufenden Slot als überfällig statt den nächsten.
    ("daily-0530", {}, "paris", _lokal(PARIS_TZ, D23, 5, 30)),
    ("daily-0730-im-fenster", {}, "paris", _lokal(PARIS_TZ, D23, 7, 30)),
    ("daily-1830", {}, "paris", _lokal(PARIS_TZ, D23, 18, 30)),
    ("weekly-montag", {"schedule": "weekly", "weekday": 0}, "paris",
     _lokal(PARIS_TZ, D23, 8, 30)),
    ("weekly-heute-abend", {"schedule": "weekly", "weekday": 4}, "paris",
     _lokal(PARIS_TZ, D23, 8, 30)),
    ("end_date-heute", {"end_date": "2026-10-23"}, "paris", _lokal(PARIS_TZ, D23, 8, 30)),
    ("end_date-vorbei", {"end_date": "2026-10-22"}, "paris", _lokal(PARIS_TZ, D23, 8, 30)),
    ("paused", {"paused_at": "2026-10-22T10:00:00+00:00"}, "paris",
     _lokal(PARIS_TZ, D23, 5, 30)),
    ("manual", {"schedule": "manual"}, "paris", _lokal(PARIS_TZ, D23, 5, 30)),
    ("altdaten-0600", {"morning_time": None}, "paris", _lokal(PARIS_TZ, D23, 4, 30)),
    ("dst-ueber-nacht", {"evening_enabled": False}, "paris", _lokal(PARIS_TZ, D24, 20, 30)),
    ("auckland-datumsgrenze", {}, "auckland",
     datetime(2026, 10, 23, 12, 30, tzinfo=timezone.utc)),
    ("ohne-orte-utc", {"location_ids": []}, "keine",
     datetime(2026, 10, 23, 9, 30, tzinfo=timezone.utc)),
]


@pytest.mark.parametrize(
    ("cid", "overrides", "orte_name", "now"),
    _COMPARE_MATRIX,
    ids=[z[0] for z in _COMPARE_MATRIX],
)
def test_ac11_compare_anzeige_gleich_scheduler_praedikat(cid, overrides, orte_name, now):
    """AC-11 (Ortsvergleich): Anzeige nennt X ⇔ ``presets_due_for_hour`` meldet
    X als ersten fälligen Takt — daily/weekly/end_date/Pause/manual/Altdaten,
    DST, Auckland, UTC-Rückfall."""
    preset = _preset(id=f"ac11-{cid}", **overrides)
    if preset.get("morning_time") is None:
        for key in ("morning_enabled", "morning_time", "evening_enabled", "evening_time"):
            preset.pop(key, None)
    orte = {"paris": _orte_paris(), "auckland": _orte_auckland(), "keine": {}}[orte_name]
    if orte_name == "auckland":
        preset["location_ids"] = ["ort-nz"]

    _pruefe_compare_aequivalenz(preset, orte, now)


# ═══════════════════════════════ AC-15 ═══════════════════════════════


def _schema(r: dict, *, skip_next: bool) -> None:
    assert isinstance(r, dict)
    json.loads(json.dumps(r))  # serialisierbar
    unbekannt = set(r) - ERLAUBTE_FELDER
    assert not unbekannt, f"Felder außerhalb des Ausgabeformats: {unbekannt}"
    if r.get("at") is None:
        assert r.get("reason") in GRUENDE, f"at==null ohne gültigen reason: {r!r}"
        if r.get("paused_until") is not None:
            assert r["reason"] == "paused"
            date.fromisoformat(r["paused_until"])
    else:
        assert TERMIN_PFLICHTFELDER <= set(r), f"Pflichtfelder fehlen: {r!r}"
        assert "reason" not in r, f"reason bei at!=null: {r!r}"
        assert "paused_until" not in r
        at = datetime.fromisoformat(r["at"])
        assert at.tzinfo is not None and at.utcoffset() is not None
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)", r["at"]), (
            f"`at` nicht ISO-8601 mit Offset: {r['at']!r}"
        )
        assert re.fullmatch(r"\d{2}:00", r["local_time"]), r["local_time"]
        date.fromisoformat(r["local_date"])
        ZoneInfo(r["tz"])
        assert r["slot"] in {"morning", "evening"}
        if r.get("overdue") is not None:
            assert r["overdue"] is True
    if "skipped" in r:
        assert skip_next, f"skipped ohne skip_next: {r!r}"
        assert set(r["skipped"]) == {"local_date", "local_time", "slot"}
        assert re.fullmatch(r"\d{2}:00", r["skipped"]["local_time"])
    else:
        assert not (skip_next and r.get("at") is not None), (
            f"skip_next aktiv, aber kein skipped: {r!r}"
        )


_SCHEMA_TRIPS = [
    ("ac1", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 5)),
    ("ac3-overdue", [D23, D24], PARIS, {}, _lokal(PARIS_TZ, D23, 8, 30)),
    ("ac4", [D23, D24, D25], AUCKLAND, {}, datetime(2026, 10, 23, 12, tzinfo=timezone.utc)),
    ("ac5", [D24, D25], PARIS, {"evening_enabled": False}, _lokal(PARIS_TZ, D24, 20)),
    ("ac6", [D23, D24], PARIS, {"skip_next": True}, _lokal(PARIS_TZ, D23, 5)),
    ("ac7-paused", [D23], PARIS, {"paused_at": "2026-10-22T10:00:00+00:00"},
     _lokal(PARIS_TZ, D23, 5)),
    ("ac7-paused-until", [D23, D24, D25, D26], PARIS,
     {"paused_until": "2026-10-26T10:00:00+00:00"}, _lokal(PARIS_TZ, D23, 5)),
    ("ac7-disabled", [D23], PARIS, {"enabled": False}, _lokal(PARIS_TZ, D23, 5)),
    ("ac7-ended", [date(2026, 10, 1)], PARIS, {}, _lokal(PARIS_TZ, D23, 5)),
    ("ac8", [D26, D27], PARIS, {}, _lokal(PARIS_TZ, D23, 12)),
    ("ac10", [D23, D24], None, {}, datetime(2026, 10, 23, 5, tzinfo=timezone.utc)),
]


@pytest.mark.parametrize(
    ("sid", "tage", "coords", "kw", "now"), _SCHEMA_TRIPS, ids=[z[0] for z in _SCHEMA_TRIPS],
)
def test_ac15_trip_ergebnis_folgt_dem_ausgabeformat(sid, tage, coords, kw, now):
    """AC-15 (Trip): genau die Felder des Ausgabeformats, `at` ISO-8601 mit
    Offset oder null, local_time HH:00, reason Pflicht bei at==null und
    abwesend bei at!=null, skipped nur bei skip_next."""
    nb = _nb()
    trip = _trip(f"ac15-{sid}", tage, coords, **kw)

    r = nb.next_trip_briefing(trip, now, _store())

    _schema(r, skip_next=bool(kw.get("skip_next")))


@pytest.mark.parametrize(
    "overrides",
    [
        {}, {"schedule": "weekly", "weekday": 0}, {"end_date": "2026-10-22"},
        {"schedule": "manual"}, {"archived_at": "2026-10-22T10:00:00+00:00"},
        {"paused_at": "2026-10-22T10:00:00+00:00"},
    ],
    ids=["daily", "weekly", "end_date", "manual", "archiviert", "paused"],
)
def test_ac15_compare_ergebnis_folgt_dem_ausgabeformat(overrides):
    """AC-15 (Ortsvergleich): dasselbe Ausgabeformat wie beim Trip."""
    nb = _nb()
    r = nb.next_compare_briefing(
        _preset(**overrides), _orte_paris(), _lokal(PARIS_TZ, D23, 8, 30),
    )

    _schema(r, skip_next=False)
    assert "skipped" not in r
