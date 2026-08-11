"""TDD RED — #1724: Briefing-Fälligkeit je Trip in seiner Ortszone.

Spec: docs/specs/modules/fix_1724_faelligkeit_in_der_ortszone.md
ADR-0051 (Zone an den Daten), ADR-0044 (Kalendertag folgt der Ortszeit)

RED-Ursache vor dem Fix: `_collect_due_trips(current_hour: int)` vergleicht die
konfigurierte Stunde gegen eine GLOBAL vorberechnete Stunde
(`datetime.now(ZoneInfo("Europe/Vienna")).hour`, `api/routers/scheduler.py:34`).
Ein Trip in Auckland ist damit fällig, wenn es in Wien 07:00 ist — dort ist es
dann 17:00. Nach dem Fix nimmt die Funktion einen ZEITPUNKT und löst die Stunde
je Trip in dessen eigener Zone auf.

Zeit wird durchgehend als Parameter hereingereicht (Regel 3 aus ADR-0051) —
kein Patch auf die Systemuhr. Die Tests bewachen damit dieselbe Eigenschaft,
die der Produktivcode zusichert.

Keine Mocks auf Geschäftslogik: echte Trip-Dateien über den isolierten
Daten-Root, echter Loader, echter Scheduler-Aufruf.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

# Koordinaten je Zone — echte Orte, damit TimezoneFinder sie auflöst.
ZONEN = {
    "Europe/Paris": (42.30, 8.93),          # Korsika, GR20
    "Pacific/Auckland": (-36.85, 174.76),   # Auckland
    "America/Los_Angeles": (34.05, -118.24),
    "Asia/Kathmandu": (27.72, 85.32),       # +5:45, halbstündiger Versatz
}


def _trip_json(trip_id: str, lat: float, lon: float, tage: list[date],
               morning: str | None = "07:00:00",
               evening: str | None = None) -> dict:
    """Trip mit je einer Etappe pro Datum, alle am selben Wegpunkt."""
    report_config: dict = {"enabled": True}
    if morning is not None:
        report_config["morning_time"] = morning
    if evening is not None:
        report_config["evening_time"] = evening
    return {
        "id": trip_id,
        "name": f"Trip {trip_id}",
        "stages": [
            {
                "id": f"{trip_id}-s{i}",
                "name": f"Etappe {i}",
                "date": d.isoformat(),
                "waypoints": [
                    {"id": f"{trip_id}-wp{i}a", "name": "Start",
                     "lat": lat, "lon": lon, "elevation_m": 800},
                    {"id": f"{trip_id}-wp{i}b", "name": "Ziel",
                     "lat": lat + 0.05, "lon": lon + 0.05, "elevation_m": 1200},
                ],
            }
            for i, d in enumerate(tage)
        ],
        "report_config": report_config,
    }


def _schreibe(user_id: str, trips: list[dict]) -> None:
    from app.loader import get_briefings_dir

    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    for t in trips:
        (ordner / f"{t['id']}.json").write_text(json.dumps(t), encoding="utf-8")


def _scheduler(user_id: str):
    from services.trip_report_scheduler import TripReportSchedulerService

    return TripReportSchedulerService(user_id=user_id)


def _faellig(scheduler, now_utc: datetime) -> set[tuple[str, str]]:
    """Fällige (trip_id, report_type)-Paare zum Zeitpunkt `now_utc`.

    Ruft die Fälligkeitssammlung mit einem ZEITPUNKT auf — vor dem Fix nimmt
    sie eine vorberechnete Stunde und schlägt hier fehl.

    Issue #1725: die Sammlung liefert seither ein DRITTES Element (den Ortstag
    des Laufs, Teil des Idempotenz-Schlüssels). Die Tests dieser Datei fragen
    unverändert nur nach Trip und Slot — deshalb wird hier nur der Kopf des
    Tupels ausgewertet, statt die Stelligkeit festzunageln.
    """
    return {(eintrag[0].id, eintrag[1]) for eintrag in scheduler._collect_due_trips(now_utc)}


def _scheduler_ohne_netz(user_id: str):
    """Echter Scheduler, bei dem AUSSCHLIESSLICH die Naht zum Netz ersetzt ist
    — kein Mock, eine echte Unterklasse mit echter Implementierung.

    Issue #1725: Fälligkeit ist seither ein FENSTER von drei Ortsstunden, und
    die Einmaligkeit entsteht durch den Vermerk `(trip_id, ortstag, slot)`, der
    erst beim VERSAND geschrieben wird. Wer nur sammelt, sieht deshalb drei
    Treffer statt einem — die Tests unten fahren die vollständige Kette
    (`_lauf`), und dafür darf der Versand nicht ins Netz gehen.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    class _OhneNetz(TripReportSchedulerService):
        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            return "sent"

    return _OhneNetz(user_id=user_id)


def _lauf(scheduler, now_utc: datetime) -> set[tuple[str, str, date]]:
    """Ein vollständiger Sammellauf: sammeln, dann jedes fällige Element über
    `_dispatch_due_item` abarbeiten — genau die Kette, die
    `run_briefing_dispatch` fährt (`collect_due` → Schleife über
    `dispatch_one`), ohne die 2s-Pause und ohne `pre_pass`.

    Rückgabe ist die GESAMMELTE Menge, jeweils mit dem ORTSTAG des Laufs als
    drittem Glied (Issue #1725) — nur mit ihm lässt sich ein Treffer dem
    Ortstag zuordnen, zu dem er gehört.
    """
    gesammelt = list(scheduler._collect_due_trips(now_utc))
    for trip, report_type, ortstag in gesammelt:
        scheduler._dispatch_due_item(trip, report_type, ortstag)
    return {(t.id, rt, tag) for t, rt, tag in gesammelt}


def _slots(scheduler, now_utc: datetime) -> set[tuple[str, str]]:
    """`_lauf` ohne den Ortstag — für die Tests, die genau EINE Zone messen und
    deshalb ohnehin nur Zeitpunkte eines einzigen Ortstags durchlaufen."""
    return {(trip_id, rt) for trip_id, rt, _ in _lauf(scheduler, now_utc)}


def _ortstag_schritte(zone: "ZoneInfo | timezone", tag: date) -> list[datetime]:
    """Stündliche UTC-Zeitpunkte, die den ORTSTAG `tag` in `zone` abdecken —
    von Ortsmitternacht zu Ortsmitternacht.

    Issue #1725: gezählt wird über den ORTSTAG, nicht mehr über den UTC-Tag.
    Der Produktivcode entscheidet über Ortstage (ADR-0044), und die
    Einmaligkeit gilt je Ortstag — ein UTC-Tag deckt bei jedem Zonen-Versatz
    Teile ZWEIER Ortstage ab (bei Kathmandu +5:45 beginnt er um 05:45
    Ortszeit) und zählte dann zwei völlig korrekte Treffer AUS ZWEI ORTSTAGEN
    als Dopplung. Wer hier auf eine Iteration über den UTC-Tag zurückdreht
    (die frühere Fassung `_stunden_eines_tages`, mit dieser Änderung
    entfallen), misst wieder am falschen Maßstab.

    Die Länge des Ortstags wird BERECHNET (ADR-0044): beide Ortsmitternachte
    werden erst nach UTC gebracht, dort verglichen. Ein Vergleich der beiden
    Wanduhr-Werte mit identischem `tzinfo` ergäbe an JEDEM Tag 24,0 h und
    verschluckte die Umstellungstage.
    """
    start = datetime(tag.year, tag.month, tag.day, 0, 0, tzinfo=zone)
    ende = start + timedelta(days=1)  # Wanduhr-Addition -> nächste Ortsmitternacht
    t = start.astimezone(timezone.utc)
    grenze = ende.astimezone(timezone.utc)
    schritte = []
    while t < grenze:
        schritte.append(t)
        t += timedelta(hours=1)
    return schritte


# ---------------------------------------------------------------------------
# AC-1 — Kernwirkung: Ankunft zur Ortsstunde, in keiner anderen
# ---------------------------------------------------------------------------

def test_ac1_auckland_faellig_genau_zur_ortsstunde():
    """Given Trip in Pacific/Auckland, Morgen-Briefing 07:00 / When der Lauf
    über 24 Stunden geht / Then genau eine Fälligkeit, und zwar wenn es an
    den Wegpunkten 07:00 Ortszeit ist."""
    lat, lon = ZONEN["Pacific/Auckland"]
    zone = ZoneInfo("Pacific/Auckland")
    # Etappen über drei Tage, damit an jeder geprüften Stunde eine Etappe
    # zum jeweiligen Ortstag existiert.
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("tz-ac1", [_trip_json("nz", lat, lon, tage)])
    # Issue #1725: vollständige Kette (sammeln + versenden) über den ORTSTAG.
    # Die Fälligkeit ist seither ein Fenster; erst der beim Versand
    # geschriebene Vermerk macht daraus genau einen Treffer.
    scheduler = _scheduler_ohne_netz("tz-ac1")

    treffer = [
        now for now in _ortstag_schritte(zone, date(2026, 8, 20))
        if ("nz", "morning") in _slots(scheduler, now)
    ]

    assert len(treffer) == 1, (
        f"Erwartet genau eine faellige Stunde, gefunden {len(treffer)}: "
        f"{[t.isoformat() for t in treffer]}"
    )
    ortszeit = treffer[0].astimezone(zone)
    assert ortszeit.hour == 7, (
        f"Briefing kommt um {ortszeit:%H:%M} Ortszeit an, konfiguriert war 07:00"
    )


# ---------------------------------------------------------------------------
# AC-2 — beide Vorzeichen und halbstündiger Versatz
# ---------------------------------------------------------------------------

def test_ac2_vier_zonen_je_zur_eigenen_ortsstunde():
    """Given je ein Trip in vier Zonen, alle 07:00 / When derselbe Lauf über
    24 Stunden / Then jeder genau einmal fällig, zu vier VERSCHIEDENEN
    Weltzeit-Stunden."""
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    trips = [
        _trip_json(name.replace("/", "_"), lat, lon, tage)
        for name, (lat, lon) in ZONEN.items()
    ]
    _schreibe("tz-ac2", trips)
    scheduler = _scheduler_ohne_netz("tz-ac2")

    # Issue #1725: EIN gemeinsamer Lauf wie bisher, aber über die VEREINIGUNG
    # der vier Ortstage 2026-08-20 statt über den UTC-Tag — die vier Zonen
    # haben zum selben Zeitpunkt verschiedene Ortstage. Gezählt werden je Trip
    # nur die Treffer, die auf SEINEN Ortstag 2026-08-20 fallen (drittes Glied
    # der Sammlung). Über einen UTC-Tag gezählt fielen bei Kathmandu (+5:45)
    # zwei völlig korrekte Treffer aus ZWEI Ortstagen zusammen.
    ortstag = date(2026, 8, 20)
    schritte = sorted({
        t for zone_name in ZONEN
        for t in _ortstag_schritte(ZoneInfo(zone_name), ortstag)
    })

    ankunft: dict[str, list[datetime]] = {t["id"]: [] for t in trips}
    for now in schritte:
        for trip_id, rt, tag in _lauf(scheduler, now):
            if rt == "morning" and tag == ortstag:
                ankunft[trip_id].append(now)

    for zone_name in ZONEN:
        trip_id = zone_name.replace("/", "_")
        assert len(ankunft[trip_id]) == 1, (
            f"{zone_name}: erwartet genau eine Faelligkeit, "
            f"gefunden {len(ankunft[trip_id])}"
        )
        lokal = ankunft[trip_id][0].astimezone(ZoneInfo(zone_name))
        assert lokal.hour == 7, f"{zone_name}: Ankunft {lokal:%H:%M} statt 07:00"

    weltzeit_stunden = {v[0].hour for v in ankunft.values()}
    assert len(weltzeit_stunden) == 4, (
        "Vier Zonen muessen zu vier verschiedenen Weltzeit-Stunden feuern, "
        f"gefunden: {sorted(weltzeit_stunden)}"
    )


# ---------------------------------------------------------------------------
# AC-3 — der Kalendertag folgt mit (offener Rest aus #1697)
# ---------------------------------------------------------------------------

def test_ac3_zieltag_ist_ortstag_nicht_serverdatum():
    """Given Trip in America/Los_Angeles, Zeitpunkt an dem Serverdatum (UTC)
    und Ortsdatum auseinanderfallen / When der Zieltag des Morgen-Briefings
    bestimmt wird / Then ist er der ORTStag."""
    lat, lon = ZONEN["America/Los_Angeles"]
    zone = ZoneInfo("America/Los_Angeles")
    tage = [date(2026, 8, 19), date(2026, 8, 20)]
    _schreibe("tz-ac3", [_trip_json("pct", lat, lon, tage)])
    scheduler = _scheduler("tz-ac3")

    from app.loader import load_all_trips
    trip = load_all_trips(user_id="tz-ac3")[0]

    # 03:00 UTC am 20.08. = 20:00 Ortszeit am 19.08. — die beiden Daten
    # fallen hier garantiert auseinander.
    now = datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc)
    assert now.date() != now.astimezone(zone).date(), "Testaufbau prueft nichts"

    ziel = scheduler._get_target_date("morning", trip, now)
    assert ziel == now.astimezone(zone).date(), (
        f"Zieltag {ziel} folgt der Serveruhr ({now.date()}) statt dem "
        f"Ortstag ({now.astimezone(zone).date()})"
    )


def test_ac3b_aktive_trips_folgen_dem_ortstag():
    """Given Trip in Pacific/Auckland mit Etappe NUR am Ortstag / When die
    aktiven Trips zu einem Zeitpunkt bestimmt werden, an dem das Serverdatum
    noch der Vortag ist / Then ist der Trip aktiv (und wird nicht still
    uebersprungen, weil an `date.today()` keine Etappe liegt)."""
    lat, lon = ZONEN["Pacific/Auckland"]
    zone = ZoneInfo("Pacific/Auckland")
    # 14:00 UTC am 19.08. = 02:00 Ortszeit am 20.08.
    now = datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
    ortstag = now.astimezone(zone).date()
    assert ortstag != now.date(), "Testaufbau prueft nichts"

    _schreibe("tz-ac3b", [_trip_json("nz", lat, lon, [ortstag])])
    scheduler = _scheduler("tz-ac3b")

    aktive = scheduler._get_active_trips("morning", now)
    assert [t.id for t in aktive] == ["nz"], (
        "Trip mit Etappe am Ortstag wurde uebersprungen — die Auswahl haengt "
        "noch am Serverdatum"
    )


# ---------------------------------------------------------------------------
# AC-4 — Bestandsschutz Mitteleuropa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("konfig_stunde", [h for h in range(24) if h not in (0, 1)])
def test_ac4_korsika_unveraendert(konfig_stunde: int):
    """Given Trip auf Korsika mit Briefing zur Stunde H (ausser 00/01) / When
    der Lauf über 24 Stunden geht / Then feuert er zu genau der Weltzeit-
    Stunde, zu der er auch vorher feuerte (Wien == Paris)."""
    lat, lon = ZONEN["Europe/Paris"]
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe(
        f"tz-ac4-{konfig_stunde}",
        [_trip_json("korsika", lat, lon, tage, morning=f"{konfig_stunde:02d}:00:00")],
    )
    scheduler = _scheduler_ohne_netz(f"tz-ac4-{konfig_stunde}")

    # Issue #1725: vollständige Kette über den ORTSTAG (s. `_ortstag_schritte`).
    treffer = [
        now for now in _ortstag_schritte(ZoneInfo("Europe/Paris"), date(2026, 8, 20))
        if ("korsika", "morning") in _slots(scheduler, now)
    ]

    # Vorher: fällig, wenn Wiener Stunde == konfig_stunde. Wien und Paris
    # teilen die Zone, also ist das exakt dieselbe Weltzeit-Stunde.
    erwartet_utc = (konfig_stunde - 2) % 24  # CEST = UTC+2 am 20.08.
    assert [t.hour for t in treffer] == [erwartet_utc], (
        f"Konfig {konfig_stunde:02d}:00 Ortszeit: erwartet Weltzeit "
        f"{erwartet_utc:02d}:00, gefunden {[t.hour for t in treffer]}"
    )


# ---------------------------------------------------------------------------
# AC-5 — keine geratene Zone mehr im Briefing-Pfad
# ---------------------------------------------------------------------------

# AC-5, erster Teil (kein festes Zonen-Literal im Briefing-Pfad): ENTFALLEN.
# Der ursprueng­lich hier stehende AST-Scan las Produkt-Quelltext und verletzte
# damit die Hygiene-Regel aus `test_765_backend_hygiene_compliance.py`
# (CLAUDE.md: Dateiinhalt-Checks sind als Verhaltensnachweis verboten). Die
# Regel hat recht: dass keine geratene Zone mehr wirkt, weisen AC-1/AC-2
# bereits am VERHALTEN nach — der Trip in Auckland waere sonst zur falschen
# Stunde faellig. Die dauerhafte Ratsche gegen NEUE Zonen-Literale gehoert in
# den bestehenden Zeitzonen-Waechter und ist als #1723 gebucht.


def test_ac5b_faelligkeitssammlung_nimmt_keinen_stundenwert():
    """Given die Signatur von `_collect_due_trips` / When sie geprueft wird /
    Then nimmt sie einen Zeitpunkt, keine vorberechnete Stunde."""
    import inspect

    from services.trip_report_scheduler import TripReportSchedulerService

    sig = inspect.signature(TripReportSchedulerService._collect_due_trips)
    namen = [p for p in sig.parameters if p != "self"]
    assert namen == ["now_utc"], (
        f"Erwartet Parameter ['now_utc'], gefunden {namen} — eine vorberechnete "
        "Stunde traegt die Zone des Aufrufers, nicht die des Trips"
    )


# ---------------------------------------------------------------------------
# AC-6 — Trip ohne Wegpunkte fällt sichtbar zurück, wird nicht übersprungen
# ---------------------------------------------------------------------------

def test_ac6_trip_ohne_wegpunkte_verliert_sein_briefing_nicht():
    """Given ein Trip ohne Wegpunkte (Zone nicht aufloesbar) / When der Lauf
    zur UTC-Stunde des konfigurierten Briefings geht / Then ist er faellig —
    dokumentierter UTC-Rueckfall, kein stilles Ueberspringen."""
    trip = _trip_json("ohne-wp", 0.0, 0.0, [date(2026, 8, 20)])
    for stage in trip["stages"]:
        stage["waypoints"] = []
    _schreibe("tz-ac6", [trip])
    scheduler = _scheduler_ohne_netz("tz-ac6")

    # Issue #1725: vollständige Kette über den ORTSTAG. Ortszone dieses Trips
    # ist der dokumentierte UTC-Rückfall aus `trip_day.trip_tz` (keine
    # Wegpunkte), sein Ortstag ist damit der UTC-Tag.
    treffer = [
        now for now in _ortstag_schritte(timezone.utc, date(2026, 8, 20))
        if ("ohne-wp", "morning") in _slots(scheduler, now)
    ]
    assert len(treffer) == 1, (
        f"Trip ohne Wegpunkte verliert sein Briefing (Treffer: {len(treffer)}) — "
        "der UTC-Rueckfall aus trip_day.trip_tz muss greifen"
    )
    assert treffer[0].hour == 7, (
        f"UTC-Rueckfall muss zur UTC-Stunde 07 feuern, gefunden {treffer[0].hour}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Sommerzeit: an beiden Umstellungstagen genau ein Briefing
# ---------------------------------------------------------------------------

def test_ac7_sommerzeit_umstellung_liefert_genau_ein_briefing():
    """Given Trip auf Korsika mit Briefing 02:00 / When der Lauf an den beiden
    Umstellungstagen den Ortstag abschreitet / Then faellt das Briefing an
    BEIDEN Tagen genau einmal: am 29.03. nachgeholt (die Ortsstunde 02
    existiert nicht, Ortsstunde 03 erfuellt `3 >= 2 and 3 < 5`), am 25.10.
    nur beim ERSTEN Durchlauf der doppelten Ortsstunde 02 — der Vermerk
    filtert den zweiten.

    Bis #1725 hielt dieser Test hier das Fehlverhalten fest (0 Treffer am
    29.03., 2 am 25.10.) und sagte in seinem Docstring an, dass er auf das
    Zielverhalten umgeschrieben wird, sobald die Luecke geschlossen ist. Genau
    das ist hier geschehen; die Fallabdeckung selbst (Fenster, Idempotenz-
    Schluessel, Outcome-Matrix) liegt in
    `tests/tdd/test_briefing_slot_idempotenz.py`.

    Der Vermerk entsteht erst beim VERSAND — der Lauf hier ist deshalb die
    vollstaendige Kette aus `run_briefing_dispatch` (sammeln, dann jedes
    faellige Element ueber `_dispatch_due_item` abarbeiten). Ersetzt ist nur
    die Naht zum Netz.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    lat, lon = ZONEN["Europe/Paris"]
    zone = ZoneInfo("Europe/Paris")
    tage = [date(2026, 3, 28), date(2026, 3, 29), date(2026, 3, 30),
            date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 26)]
    _schreibe("tz-ac7", [_trip_json("korsika", lat, lon, tage, morning="02:00:00")])

    class _OhneNetz(TripReportSchedulerService):
        """Echte Unterklasse, die nur den Versand ersetzt — kein Mock."""

        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            return "sent"

    scheduler = _OhneNetz(user_id="tz-ac7")

    def treffer_am(tag: date) -> int:
        # Ortstag von Ortsmitternacht bis Ortsmitternacht abschreiten. Die
        # Laenge wird BERECHNET (ADR-0044): beide Ortsmitternachte erst nach
        # UTC bringen, sonst ergibt die Subtraktion an jedem Tag 24,0 h.
        start = datetime(tag.year, tag.month, tag.day, 0, 0, tzinfo=zone)
        ende = start + timedelta(days=1)
        t = start.astimezone(timezone.utc)
        n = 0
        while t < ende.astimezone(timezone.utc):
            gesammelt = list(scheduler._collect_due_trips(t))
            for trip, report_type, ortstag in gesammelt:
                scheduler._dispatch_due_item(trip, report_type, ortstag)
            if ("korsika", "morning") in [(x.id, rt) for x, rt, _ in gesammelt]:
                n += 1
            t += timedelta(hours=1)
        return n

    assert treffer_am(date(2026, 3, 29)) == 1, (
        "Fruehjahrs-Umstellung: die Ortsstunde 02 existiert nicht — das "
        "Briefing muss trotzdem genau einmal fallen (nachgeholt in Ortsstunde "
        "03). 0 heisst: die Faelligkeit haengt wieder an Stundengleichheit."
    )
    assert treffer_am(date(2026, 10, 25)) == 1, (
        "Herbst-Umstellung: die Ortsstunde 02 existiert zweimal — das Briefing "
        "darf trotzdem nur einmal fallen. 2 heisst: der Idempotenz-Schluessel "
        "(trip_id, ortstag, slot) greift nicht."
    )


# ---------------------------------------------------------------------------
# AC-9 — ein Zeitpunkt für den ganzen Lauf
# ---------------------------------------------------------------------------

def test_ac9_alle_trips_sehen_denselben_jetzt_zeitpunkt():
    """Given mehrere Trips in verschiedenen Zonen / When die Faelligkeit
    ermittelt wird / Then wird `now_utc` genau EINMAL bestimmt und an alle
    Trips durchgereicht — kein Trip sieht eine andere Sekunde.

    Geprueft an der Wirkung: zwei Aufrufe mit demselben Zeitpunkt liefern
    dasselbe Ergebnis, und der Zeitpunkt stammt nachweislich aus dem
    Parameter (nicht aus der Systemuhr).
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    trips = [
        _trip_json(name.replace("/", "_"), lat, lon, tage)
        for name, (lat, lon) in ZONEN.items()
    ]
    _schreibe("tz-ac9", trips)
    scheduler = _scheduler("tz-ac9")

    # Ein Zeitpunkt, zu dem Auckland faellig ist (19:00 UTC am 19.08. =
    # 07:00 Ortszeit am 20.08.).
    now = datetime(2026, 8, 19, 19, 0, tzinfo=timezone.utc)
    erst = _faellig(scheduler, now)
    zweit = _faellig(scheduler, now)
    assert erst == zweit, "Gleicher Zeitpunkt, unterschiedliches Ergebnis"
    assert ("Pacific_Auckland", "morning") in erst, (
        "Zum uebergebenen Zeitpunkt muss Auckland faellig sein — das Ergebnis "
        f"haengt an der Systemuhr statt am Parameter. Gefunden: {sorted(erst)}"
    )


# ---------------------------------------------------------------------------
# Wächter aus der Mutations-Gegenprobe
#
# Die drei folgenden Tests sind NICHT aus den ACs abgeleitet, sondern aus dem
# Befund der Gegenprobe: drei gezielte Verfälschungen der Implementierung
# liessen alle 31 Tests oben gruen. Ein gruener Lauf beweist nur, dass die
# Tests durchlaufen — nicht, dass sie etwas bewachen.
# ---------------------------------------------------------------------------

def test_gegenprobe_zieltag_wird_je_trip_bestimmt_nicht_einmal_fuer_alle():
    """Verfälschung M3: der Zieltag wird EINMAL vor der Schleife bestimmt und
    fuer alle Trips benutzt (der Zustand vor #1724).

    Fangbar nur mit zwei Trips in verschiedenen Zonen, deren Ortstage
    auseinanderfallen UND die nur an ihrem eigenen Ortstag eine Etappe haben.
    Sonst findet der falsche Zieltag zufaellig trotzdem eine Etappe.
    """
    zone_nz = ZoneInfo("Pacific/Auckland")
    zone_us = ZoneInfo("America/Los_Angeles")
    # 09:00 UTC: in Auckland ist es der 20.08. (21:00), in Los Angeles noch
    # der 20.08. (02:00) — hier gleich. Gesucht ist ein Zeitpunkt, an dem sie
    # AUSEINANDERFALLEN: 14:00 UTC am 19.08. -> NZ 20.08., LA 19.08.
    now = datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
    tag_nz = now.astimezone(zone_nz).date()
    tag_us = now.astimezone(zone_us).date()
    assert tag_nz != tag_us, "Testaufbau prueft nichts"

    lat_nz, lon_nz = ZONEN["Pacific/Auckland"]
    lat_us, lon_us = ZONEN["America/Los_Angeles"]
    _schreibe("tz-m3", [
        _trip_json("nz", lat_nz, lon_nz, [tag_nz]),   # Etappe NUR am NZ-Ortstag
        _trip_json("us", lat_us, lon_us, [tag_us]),   # Etappe NUR am US-Ortstag
    ])
    scheduler = _scheduler("tz-m3")

    aktive = {t.id for t in scheduler._get_active_trips("morning", now)}
    assert aktive == {"nz", "us"}, (
        "Beide Trips haben an ihrem EIGENEN Ortstag eine Etappe und muessen "
        f"beide aktiv sein. Gefunden: {sorted(aktive)} — der Zieltag wird "
        "offenbar einmal fuer alle bestimmt statt je Trip."
    )


def test_gegenprobe_ortsvergleich_tag_und_stunde_aus_derselben_zone():
    """Verfälschung M4: der Ortsvergleich holt seinen Kalendertag wieder aus
    `date.today()` (Prozess-Zeitzone) statt aus derselben Zone wie die Stunde.

    AC-8 fordert unveraendertes Compare-Verhalten — unveraendert heisst hier
    ausdruecklich NICHT "egal": Stunde und Tag muessen aus EINER Ableitung
    kommen, sonst fallen sie an der Tagesgrenze auseinander. Genau das war der
    Zustand vor #1724 (Stunde vom Aufrufer, Tag aus `date.today()`).
    """
    from datetime import date as _date

    from services.dispatch_orchestrator import CompareDispatchStrategy
    from utils.timezone import local_dt

    zone = ZoneInfo(CompareDispatchStrategy.NOCH_NICHT_ORTSZEIT_SIEHE_1726)
    # 23:30 UTC: in der Vergleichs-Zone ist bereits der Folgetag.
    now = datetime(2026, 8, 20, 23, 30, tzinfo=timezone.utc)
    vor_ort = local_dt(now, zone)
    assert vor_ort.date() != now.date(), "Testaufbau prueft nichts"

    gesehen: list[tuple[int, _date]] = []

    def _protokollierend(presets, hour, today):
        gesehen.append((hour, today))
        return []

    import services.compare_slot_scheduler as css
    import services.scheduler_dispatch_service as sds

    echte_funktion = css.presets_due_for_hour
    echter_loader = sds._load_presets_for_dispatch
    css.presets_due_for_hour = _protokollierend
    sds._load_presets_for_dispatch = lambda user_id, data_root: [{"id": "p1"}]
    try:
        from app.config import Settings

        strategie = CompareDispatchStrategy(Settings(), "tz-m4", data_root="/tmp")
        strategie.collect_due(now)
    finally:
        css.presets_due_for_hour = echte_funktion
        sds._load_presets_for_dispatch = echter_loader

    assert gesehen == [(vor_ort.hour, vor_ort.date())], (
        f"Stunde und Kalendertag muessen aus derselben Zonen-Ableitung stammen. "
        f"Erwartet {(vor_ort.hour, vor_ort.date())}, gesehen {gesehen}"
    )


def test_gegenprobe_anker_ist_die_etappe_des_weltzeit_tages():
    """Verfälschung M5: die Zone kommt aus der ERSTEN Etappe der Reise statt
    aus der Etappe des Weltzeit-Tages.

    #1470 hat diesen Unterschied gemessen: bei einer Reise Neuseeland →
    Korsika lag der Tageswechsel damit ZEHN Stunden falsch. ADR-0044 hat den
    Anker daraufhin festgelegt. Reisen ueber mehrere Zonen bleiben eine
    bekannte Grenze — die getroffene Anker-Entscheidung soll trotzdem nicht
    still zurueckgedreht werden koennen.
    """
    from services.trip_day import trip_local_now

    lat_nz, lon_nz = ZONEN["Pacific/Auckland"]
    lat_fr, lon_fr = ZONEN["Europe/Paris"]
    now = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    weltzeit_tag = now.date()

    trip = _trip_json("wechsel", lat_nz, lon_nz, [date(2026, 8, 10)])
    # Zweite Etappe am Weltzeit-Tag, aber in Europa.
    trip["stages"].append({
        "id": "wechsel-s9", "name": "Korsika", "date": weltzeit_tag.isoformat(),
        "waypoints": [{"id": "wp-fr", "name": "Start", "lat": lat_fr,
                       "lon": lon_fr, "elevation_m": 900}],
    })
    _schreibe("tz-m5", [trip])

    from app.loader import load_all_trips
    geladen = load_all_trips(user_id="tz-m5")[0]

    ortszeit = trip_local_now(geladen, now)
    erwartet = now.astimezone(ZoneInfo("Europe/Paris"))
    assert ortszeit.utcoffset() == erwartet.utcoffset(), (
        "Die Zone muss von der Etappe des WELTZEIT-Tages kommen (Korsika), "
        f"nicht von der ersten Etappe der Reise (Auckland). "
        f"Gemessener Versatz: {ortszeit.utcoffset()}, erwartet {erwartet.utcoffset()}"
    )
