"""TDD RED — #2422 S3: die EINE Slot-Regel am Prädikat des Alarm-Vorlaufs und am
Loader (AC-5, AC-21) sowie an der Modulfunktion ``slot_aktiv``.

SPEC: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md — AC-5, AC-21,
„Semantik der Slot-Prüfung", Mutationen M3 und M5.

Alle drei Tests lesen dieselbe geteilte Fallzeilen-Tabelle wie der Go- und der
TS-Test (``tests/fixtures/report_config_slot_faelle.json``, relativer Pfad):

* ``test_alarm_vorlauf_folgt_derselben_slot_regel`` (AC-5) ruft
  ``trip_briefing_due_at`` DIREKT — dort, wo die Slot-Prüfung WIRKT. Der
  Sammellauf-Test (``test_kanal_an_aus_kette.py``) läuft über
  ``_get_active_trips`` und bleibt grün, wenn die Prüfung im Prädikat fehlt
  (M5): ein Alarm würde dann für ein Briefing schweigen, das nie kommt.
* ``test_loader_roundtrip_und_flache_felder_folgen_der_tabelle`` (AC-21) prüft
  die Per-Slot-Felder über DATEI und flache Trip-Felder, nicht über neue
  Attribute am Modell.
* ``test_slot_aktiv_folgt_der_tabelle`` prüft die Modulfunktion, die die Spec
  namentlich vorschreibt (``app.models.slot_aktiv`` und die beiden
  Attribute ``morning_enabled``/``evening_enabled``). ImportError ist dort ein
  gültiges RED.

Keine Mocks: echter ``load_trip``, echter ``save_trip``, echtes Prädikat,
echter Vermerk-Speicher. Die Bezugszeit ist FEST (kein ``datetime.now()``).
Nutzerkennungen tragen bewusst KEIN „test"/„tdd" (Herkunftssperre #2406).
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import load_trip, save_trip  # noqa: E402
from services.trip_report_scheduler import trip_briefing_due_at  # noqa: E402

TABELLE = Path(__file__).resolve().parents[1] / "fixtures" / "report_config_slot_faelle.json"
FAELLE = json.loads(TABELLE.read_text(encoding="utf-8"))["faelle"]
FALL_IDS = [f["name"] for f in FAELLE]


def test_geteilte_fallzeilen_tabelle_ist_vollstaendig():
    """Adversary F004: leere/gekuerzte Tabelle darf die parametrisierten Faelle
    nicht still SKIPPEN (Exit 0) -- Laengenwaechter wie Go/TS (>= 12)."""
    assert len(FAELLE) >= 12, (
        f"report_config_slot_faelle.json hat {len(FAELLE)} Faelle, erwartet >= 12 "
        f"(Datei gekuerzt?)"
    )

#: Innsbruck — Ortszone Europe/Vienna (Juli: UTC+2).
LAT, LON = 47.2692, 11.4041
ORT = ZoneInfo("Europe/Vienna")

#: Feste Bezugstage. Etappe 1 = „heute" (Morgen-Slot-Zieltag), Etappe 2 =
#: „morgen" (Abend-Slot-Zieltag). Kein Systemdatum.
HEUTE, MORGEN = "2026-07-20", "2026-07-21"

#: Die Fallzeilen setzen keine Zeiten -> Standardzeiten 07:00 / 18:00, Fenster
#: je drei Stunden (``NACHHOL_FENSTER_STUNDEN``): Morgen 07-10, Abend 18-21.
#: 08:00 und 19:00 Ortszeit liegen mittig in genau EINEM Fenster.
IM_MORGEN_FENSTER = datetime(2026, 7, 20, 8, 0, tzinfo=ORT).astimezone(timezone.utc)
IM_ABEND_FENSTER = datetime(2026, 7, 20, 19, 0, tzinfo=ORT).astimezone(timezone.utc)


def _kennung() -> str:
    """Nutzerkennung OHNE „test"/„tdd" (Herkunftssperre #2406)."""
    return f"slotfaelle-{uuid.uuid4().hex[:8]}"


def _trip_dict(trip_id: str, report_config) -> dict:
    """Trip im PERSISTENZFORMAT (so liegt er in ``briefings/<id>.json``)."""
    def etappe(nr: int, tag: str) -> dict:
        return {
            "id": f"T{nr}", "name": f"Etappe {nr}", "date": tag,
            "waypoints": [
                {"id": f"G{nr}a", "name": "Start", "lat": LAT, "lon": LON,
                 "elevation_m": 600},
                {"id": f"G{nr}b", "name": "Ziel", "lat": LAT + 0.02,
                 "lon": LON + 0.02, "elevation_m": 900},
            ],
        }

    d: dict = {
        "id": trip_id, "name": "Slot-Faelle Trip",
        "stages": [etappe(1, HEUTE), etappe(2, MORGEN)],
        "official_alerts_enabled": False,
    }
    if report_config is not None:
        d["report_config"] = json.loads(json.dumps(report_config))
    return d


def _datei_ablegen(data_dir: Path, user_id: str, d: dict) -> Path:
    """Persistenzformat-Datei genau dort, wo ``load_trip(id, data_dir=...)`` sie sucht."""
    ordner = data_dir / "users" / user_id / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{d['id']}.json"
    pfad.write_text(json.dumps({**d, "kind": "route"}, indent=2), encoding="utf-8")
    return pfad


def _laden(data_dir: Path, user_id: str, d: dict):
    _datei_ablegen(data_dir, user_id, d)
    trip = load_trip(d["id"], data_dir=data_dir, user_id=user_id)
    assert trip is not None, f"Vorbedingung: Trip {d['id']} liess sich nicht laden"
    return trip


# ════════════════════════════ AC-5 ═══════════════════════════════════════════


@pytest.mark.parametrize("fall", FAELLE, ids=FALL_IDS)
def test_alarm_vorlauf_folgt_derselben_slot_regel(tmp_path, fall):
    """AC-5: das Faelligkeits-Praedikat des Alarm-Vorlaufs haelt fuer einen
    abgeschalteten Slot NICHTS zurueck.

    GIVEN ein Trip mit der ``report_config`` einer Tabellenzeile (ueber den
          echten ``load_trip`` aus einem Persistenzformat-JSON geladen).
    WHEN  ``trip_briefing_due_at`` fuer einen Zeitpunkt im ABEND-Fenster und
          fuer einen im MORGEN-Fenster gefragt wird (echte ``user_id``).
    THEN  ist es im Abend-Fenster genau dann faellig, wenn ``slot_evening``,
          und im Morgen-Fenster genau dann, wenn ``slot_morning`` — bei
          ``enabled=false`` in keinem Fenster.

    Faengt Mutation M5 (Slot-Pruefung im Praedikat entfernt, Master-Test davor
    bleibt): dort steht die Zusicherung, nicht im Sammellauf.
    """
    user_id = _kennung()
    d = _trip_dict(f"slot-{uuid.uuid4().hex[:8]}", fall["report_config"])
    trip = _laden(tmp_path, user_id, d)

    abend = trip_briefing_due_at(trip, IM_ABEND_FENSTER, user_id=user_id)
    morgen = trip_briefing_due_at(trip, IM_MORGEN_FENSTER, user_id=user_id)

    assert abend == fall["slot_evening"], (
        f"AC-5 [{fall['name']}] report_config={fall['report_config']!r}: im "
        f"ABEND-Fenster ist das Praedikat {abend}, erwartet "
        f"{fall['slot_evening']} — "
        + ("der Alarm schwiege fuer ein Abend-Briefing, das nie kommt."
           if abend and not fall["slot_evening"] else
           "der Alarm wuerde nicht schweigen, obwohl ein Briefing kommt.")
    )
    assert morgen == fall["slot_morning"], (
        f"AC-5 [{fall['name']}] report_config={fall['report_config']!r}: im "
        f"MORGEN-Fenster ist das Praedikat {morgen}, erwartet "
        f"{fall['slot_morning']} — "
        + ("der Alarm schwiege fuer ein Morgen-Briefing, das nie kommt."
           if morgen and not fall["slot_morning"] else
           "der Alarm wuerde nicht schweigen, obwohl ein Briefing kommt.")
    )


# ════════════════════════════ AC-21 ══════════════════════════════════════════

_SLOT_SCHLUESSEL = ("morning_enabled", "evening_enabled")


@pytest.mark.parametrize("fall", FAELLE, ids=FALL_IDS)
def test_loader_roundtrip_und_flache_felder_folgen_der_tabelle(tmp_path, fall):
    """AC-21: der Loader liest und schreibt die Per-Slot-Schalter verlustfrei;
    die flachen Felder des geladenen Trips folgen der Tabelle.

    Zwei Varianten je Zeile, weil ``save_trip`` gegen eine VORHANDENE Datei
    mergt (``_deep_merge_preserve_unknown``) und dort auch ohne Loader-Support
    alle Schluessel stehen liessen — nur der Lauf in ein FRISCHES Verzeichnis
    beweist, dass der Schreibweg die Werte selbst schreibt:

    (a) Dict -> ``load_trip`` -> ``save_trip`` in ein frisches ``data_dir``:
        gesetzte ``bool``-Werte stehen danach genau so in der Datei; alles
        andere (fehlend, ``null``, ``"ja"``) steht NICHT als Schluessel da
        (kein ``null``-Eintrag).
    (b) Datei vorlegen -> per id laden -> in dieselbe Datei speichern:
        gesetzte Werte bleiben, fehlende Schluessel bleiben fehlend (kein
        neuer ``null``-Eintrag), ein dem Modell unbekannter Schluessel
        bleibt erhalten.

    Beide: ``trip.morning_enabled``/``evening_enabled`` des geladenen Trips ==
    ``flat_morning``/``flat_evening`` (bei ``null``: ``None``), auch nach dem
    Wiederladen der zurueckgeschriebenen Datei.
    """
    rc_roh = fall["report_config"]
    user_id = _kennung()
    trip_id = f"slot-{uuid.uuid4().hex[:8]}"
    flach = (fall["flat_morning"], fall["flat_evening"])

    # ── (a) frisches data_dir: schreibt der Writer die Werte selbst? ──────
    d_a = _trip_dict(trip_id, rc_roh)
    trip_a = load_trip(d_a)
    assert trip_a is not None
    assert (trip_a.morning_enabled, trip_a.evening_enabled) == flach, (
        f"AC-21 [{fall['name']}] (a): flache Felder des geladenen Trips sind "
        f"({trip_a.morning_enabled!r}, {trip_a.evening_enabled!r}), erwartet "
        f"{flach!r} — report_config={rc_roh!r}"
    )
    frisch = tmp_path / "frisch"
    pfad_a = save_trip(trip_a, user_id, data_dir=frisch)
    gespeichert_a = json.loads(pfad_a.read_text(encoding="utf-8"))
    rc_a = gespeichert_a.get("report_config")
    if rc_roh is None:
        assert rc_a is None, f"(a) ohne report_config darf keiner entstehen: {rc_a!r}"
    else:
        assert rc_a is not None
        for schluessel in _SLOT_SCHLUESSEL:
            roh = rc_roh.get(schluessel)
            if isinstance(roh, bool):
                assert rc_a.get(schluessel) is roh, (
                    f"AC-21 [{fall['name']}] (a): {schluessel}={roh!r} steht "
                    f"nach dem Roundtrip NICHT in der Datei "
                    f"(Datei: {rc_a.get(schluessel, '<fehlt>')!r}) — der "
                    f"Schreibweg verliert den gesetzten Per-Slot-Wert."
                )
            else:
                assert schluessel not in rc_a, (
                    f"AC-21 [{fall['name']}] (a): {schluessel} war {roh!r} "
                    f"(nicht gesetzt/kein bool) und darf nicht als "
                    f"{rc_a.get(schluessel)!r} in die Datei geschrieben werden."
                )
    nachgeladen_a = load_trip(trip_id, data_dir=frisch, user_id=user_id)
    assert nachgeladen_a is not None
    assert (nachgeladen_a.morning_enabled, nachgeladen_a.evening_enabled) == flach, (
        f"AC-21 [{fall['name']}] (a): nach dem Wiederladen sind die flachen "
        f"Felder ({nachgeladen_a.morning_enabled!r}, "
        f"{nachgeladen_a.evening_enabled!r}), erwartet {flach!r}"
    )

    # ── (b) vorhandene Datei: Erhalt, kein null-Eintrag, unbekannter Schluessel ─
    d_b = _trip_dict(trip_id, rc_roh)
    if d_b.get("report_config") is not None:
        d_b["report_config"]["zukunftsfeld_der_ui"] = {"bleibt": [1, 2, 3]}
    d_b["top_level_unbekannt"] = "bleibt"
    vorhanden = tmp_path / "vorhanden"
    trip_b = _laden(vorhanden, user_id, d_b)
    assert (trip_b.morning_enabled, trip_b.evening_enabled) == flach, (
        f"AC-21 [{fall['name']}] (b): flache Felder des per id geladenen Trips "
        f"sind ({trip_b.morning_enabled!r}, {trip_b.evening_enabled!r}), "
        f"erwartet {flach!r}"
    )
    pfad_b = save_trip(trip_b, user_id, data_dir=vorhanden)
    gespeichert_b = json.loads(pfad_b.read_text(encoding="utf-8"))
    assert gespeichert_b.get("top_level_unbekannt") == "bleibt"
    rc_b = gespeichert_b.get("report_config")
    if d_b.get("report_config") is not None:
        assert rc_b is not None
        assert rc_b.get("zukunftsfeld_der_ui") == {"bleibt": [1, 2, 3]}, (
            f"AC-21 [{fall['name']}] (b): ein dem Modell unbekannter "
            f"report_config-Schluessel ging beim Speichern verloren: {rc_b!r}"
        )
        for schluessel in _SLOT_SCHLUESSEL:
            if schluessel not in d_b["report_config"]:
                assert schluessel not in rc_b, (
                    f"AC-21 [{fall['name']}] (b): {schluessel} fehlte in der "
                    f"Datei und ist nach dem Speichern als "
                    f"{rc_b.get(schluessel)!r} da — fehlend muss fehlend bleiben."
                )
            elif isinstance(d_b["report_config"][schluessel], bool):
                assert rc_b.get(schluessel) is d_b["report_config"][schluessel], (
                    f"AC-21 [{fall['name']}] (b): {schluessel} hat den "
                    f"Roundtrip nicht unveraendert ueberstanden: "
                    f"{rc_b.get(schluessel, '<fehlt>')!r}"
                )
    nachgeladen_b = load_trip(trip_id, data_dir=vorhanden, user_id=user_id)
    assert nachgeladen_b is not None
    assert (nachgeladen_b.morning_enabled, nachgeladen_b.evening_enabled) == flach


# ════════════════════════ slot_aktiv (Modulfunktion) ═════════════════════════


@pytest.mark.parametrize("fall", FAELLE, ids=FALL_IDS)
def test_slot_aktiv_folgt_der_tabelle(fall):
    """Die Spec schreibt ``app.models.slot_aktiv(rc, report_type)`` und die
    Attribute ``TripReportConfig.morning_enabled``/``evening_enabled``
    namentlich vor. Gegen die Tabelle: ``slot_aktiv`` liefert je Zeile
    ``slot_morning``/``slot_evening``.

    ``report_config=None`` -> ``slot_aktiv(None, ...)`` (Trip ohne
    report_config: Bestandsverhalten, beide Slots aktiv). Ein Nicht-``bool``
    (``"ja"``) reicht der Loader als ``None`` durch (AC-21) — das Modell wird
    hier deshalb mit ``None`` an dessen Stelle gebaut.

    RED heute: ``slot_aktiv`` existiert nicht (ImportError) — von der Spec
    ausdruecklich vorgeschrieben, deshalb gueltig.
    """
    from app.models import TripReportConfig, slot_aktiv  # ImportError = RED

    roh = fall["report_config"]
    if roh is None:
        rc = None
    else:
        kw = {"enabled": roh.get("enabled", True)}
        for schluessel in _SLOT_SCHLUESSEL:
            wert = roh.get(schluessel)
            kw[schluessel] = wert if isinstance(wert, bool) else None
        rc = TripReportConfig(trip_id="slot-faelle", **kw)

    assert slot_aktiv(rc, "morning") is fall["slot_morning"], (
        f"slot_aktiv [{fall['name']}] morning: erwartet "
        f"{fall['slot_morning']} bei report_config={roh!r}"
    )
    assert slot_aktiv(rc, "evening") is fall["slot_evening"], (
        f"slot_aktiv [{fall['name']}] evening: erwartet "
        f"{fall['slot_evening']} bei report_config={roh!r}"
    )
