"""TDD RED — Issue #1944, AC-4: mehrfacher Abruf je ``fetch()``-Aufruf.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-4)

Zwei Zusicherungen:

1. ``massif_closure`` bindet die Kennung waehrend der EIGENEN Iteration --
   die gewinnende Meldung traegt die Kennung IHRES Abrufs, unabhaengig von
   der Iterationsreihenfolge.
2. Eine generische Quelle mit zwei ``cached_fetch()``-Aufrufen unter der
   ``base.py``-Naht (Stellvertreter fuer die stillgelegte ``meteoalarm.py``)
   liefert Alerts mit ``capture_id=None`` -- lieber keine Zuordnung als eine
   falsche.

🔴 NEGATIVE PROBE (der Kern dieses Tests): Iterationsreihenfolge und
Gewinner-Reihenfolge fallen AUSEINANDER. Der ZUERST abgerufene Massiv-Treffer
gewinnt (hoechstes Niveau), der ZULETZT abgerufene verliert. Ein naives
„letzter gewinnt" haenge die Kennung des NICHT gewaehlten Abrufs an -- genau
das faengt die Gegenprobe unten.

RED-Grund: ``OfficialAlert`` hat kein Feld ``capture_id``.

Mock-frei: echte Massiv-Polygone (Sainte-Baume liegt real in DEPT 83 UND 13,
Beleg ``tests/tdd/test_issue_1037_massif_closure.py::test_f009_...``), echte
``httpx.Response``-Objekte ueber die Netz-Naht ``httpx.get``, echte
Mitschnitt-Dateien strukturell per ``json.loads`` gelesen.
"""
from __future__ import annotations

import json

import httpx

# Punkt im ueberlappenden Sainte-Baume-Polygon (83 UND 13), per
# ``massifs_at()`` verifiziert -- kein Raten.
LAT, LON = 43.314, 5.700


def _capture_records() -> list[dict]:
    from app.loader import get_data_root

    verzeichnis = get_data_root() / "debug" / "alert_input" / "official_alert"
    return [json.loads(p.read_text()) for p in sorted(verzeichnis.glob("*.json"))]


def _kennung_fuer_cache_key(cache_key: str) -> str:
    treffer = [
        r for r in _capture_records()
        if r.get("payload", {}).get("cache_key") == cache_key
    ]
    assert len(treffer) == 1, (
        f"Erwartet genau EINEN Mitschnitt fuer cache_key={cache_key!r}, "
        f"gefunden {len(treffer)}."
    )
    return treffer[0]["capture_id"]


def test_ac4_massiv_gewinner_traegt_die_kennung_seines_eigenen_abrufs(monkeypatch, tmp_path):
    """AC-4 (negative Probe): GIVEN zwei ueberlappende Massive mit
    unterschiedlichem Niveau und unterschiedlichen Antworten, deren
    Iterationsreihenfolge NICHT der Gewinner-Reihenfolge entspricht, WHEN
    ``fetch()`` die strengste Meldung waehlt, THEN traegt sie die
    ``capture_id`` des Abrufs, der SIE erzeugt hat -- nicht die der zuletzt
    ausgefuehrten Iteration."""
    from services.official_alerts import massif_closure, warn_egress
    from services.official_alerts.massif_zones import massifs_at

    treffer = massifs_at(LAT, LON)
    assert len(treffer) >= 2, "Testpunkt muss mindestens zwei Massive treffen."
    gewinner, verlierer = treffer[0], treffer[-1]
    assert gewinner.src != verlierer.src, (
        "Gewinner und Verlierer muessen verschiedene Source-DEPTs haben, sonst "
        "waere der zweite Abruf nur ein Cache-Treffer."
    )

    # Gewinner: Niveau 5 (strengste Sperre) -- er wird ZUERST iteriert.
    # Verlierer: Niveau 3 -- er wird ZULETZT iteriert. Damit faellt die
    # Iterationsreihenfolge nachweislich mit der Gewinner-Reihenfolge
    # auseinander.
    niveaus = {t.src: {t.massif_id: [3, 3, 3]} for t in treffer}
    niveaus[gewinner.src] = {gewinner.massif_id: [5, 5, 5]}

    monkeypatch.setattr(massif_closure, "_cache", {})
    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    def _fake_get(url: str, **kwargs) -> httpx.Response:
        # URL-Form: .../static/{src}/import_data/{ymd}.json
        src = url.split("/static/")[1].split("/")[0]
        return httpx.Response(200, json={"massifs": niveaus[src]})

    monkeypatch.setattr(httpx, "get", _fake_get)

    alerts = massif_closure.MassifClosureSource().fetch(LAT, LON)

    assert len(alerts) == 1, f"Genau eine gewinnende Meldung erwartet: {alerts!r}"
    best = alerts[0]
    assert best.level == 5, f"Strengstes Niveau muss gewinnen, war {best.level}"

    erwartet = _kennung_fuer_cache_key(gewinner.src)
    zuletzt = _kennung_fuer_cache_key(verlierer.src)
    assert erwartet != zuletzt, "Voraussetzung: unterscheidbare Kennungen je Abruf."
    assert best.capture_id == erwartet, (
        f"Die gewinnende Meldung muss die Kennung IHRES Abrufs tragen "
        f"(src={gewinner.src}): capture_id={best.capture_id!r}, "
        f"erwartet={erwartet!r}, Kennung der letzten Iteration={zuletzt!r}"
    )
    assert best.capture_id != zuletzt, (
        "Die Kennung des NICHT gewaehlten (zuletzt iterierten) Abrufs darf nie "
        "an der gewinnenden Meldung haengen."
    )


class _ZweiAbrufeQuelle:
    """Echte Quelle (strukturelles Subtyping, kein Mock): ruft ``cached_fetch``
    ZWEIMAL je ``fetch()`` auf und liefert EINE Meldung -- strukturell die
    Risikoklasse der stillgelegten ``meteoalarm.py``."""

    def __init__(self) -> None:
        self.cache: dict = {}

    @property
    def name(self) -> str:
        return "test-1944-zwei-abrufe"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        from datetime import datetime, timedelta, timezone

        from services.official_alerts import warn_egress
        from services.official_alerts.models import OfficialAlert

        for schluessel in ("seite-1", "seite-2"):
            warn_egress.cached_fetch(
                cache=self.cache, cache_key=schluessel,
                service="test-1944-zwei-abrufe", host="zwei.invalid",
                request_fn=lambda k=schluessel: httpx.Response(200, json={"seite": k}),
                parse_fn=lambda r: r.json(),
            )
        jetzt = datetime.now(timezone.utc)
        return [OfficialAlert(
            source="test-1944", hazard="wind", level=3, label="Sturmwarnung",
            region_label="Mehrdeutig",
            valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
        )]


def test_ac4_mehrdeutiger_mehrfachabruf_liefert_keine_kennung(monkeypatch, tmp_path):
    """AC-4 (Mehrdeutigkeit): GIVEN eine Quelle ruft ``cached_fetch()``
    mehrfach je ``fetch()`` auf, ohne die Kennung selbst zu binden, WHEN die
    gemeinsame Naht ``get_official_alerts_with_status`` anreichert, THEN
    bleibt ``capture_id`` ``None`` -- eine falsche Zuordnung waere schlimmer
    als keine."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import warn_egress
    from services.official_alerts.base import get_official_alerts_with_status

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    quelle = _ZweiAbrufeQuelle()
    sicherung = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(quelle)
        alerts, unavailable = get_official_alerts_with_status(LAT, LON)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sicherung)

    assert unavailable is False and len(alerts) == 1, (
        f"Voraussetzung: die Quelle liefert genau eine Warnung, war {alerts!r}"
    )
    # Voraussetzung der Messung: es gab wirklich ZWEI unterscheidbare
    # Mitschnitte -- sonst waere "None" auch die Antwort eines einzelnen Abrufs.
    kennungen = {
        r["capture_id"] for r in _capture_records()
        if r.get("payload", {}).get("service") == "test-1944-zwei-abrufe"
    }
    assert len(kennungen) == 2, (
        f"Zwei echte Abrufe muessen zwei Mitschnitte erzeugen, waren {len(kennungen)}."
    )
    assert alerts[0].capture_id is None, (
        f"Bei mehrdeutiger Herkunft darf KEINE Kennung angehaengt werden, war "
        f"{alerts[0].capture_id!r} (eine der beobachteten: {kennungen!r})"
    )


def test_ac4_eindeutiger_einzelabruf_wird_angereichert(monkeypatch, tmp_path):
    """Gegenprobe zur Abwesenheits-Zusicherung oben: bei GENAU EINEM
    beobachteten Abruf reichert dieselbe Naht sehr wohl an. Ohne diesen
    Nachweis waere ``capture_id is None`` auch die Antwort einer Naht, die
    ueberhaupt nie anreichert."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import warn_egress
    from services.official_alerts.base import get_official_alerts_with_status

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    class _EinAbrufQuelle(_ZweiAbrufeQuelle):
        @property
        def name(self) -> str:
            return "test-1944-ein-abruf"

        def fetch(self, lat: float, lon: float):
            from datetime import datetime, timedelta, timezone

            from services.official_alerts.models import OfficialAlert

            warn_egress.cached_fetch(
                cache=self.cache, cache_key="einzige-seite",
                service="test-1944-ein-abruf", host="eins.invalid",
                request_fn=lambda: httpx.Response(200, json={"seite": 1}),
                parse_fn=lambda r: r.json(),
            )
            jetzt = datetime.now(timezone.utc)
            return [OfficialAlert(
                source="test-1944", hazard="wind", level=3, label="Sturmwarnung",
                region_label="Eindeutig",
                valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
            )]

    sicherung = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(_EinAbrufQuelle())
        alerts, _ = get_official_alerts_with_status(LAT, LON)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sicherung)

    erwartet = _kennung_fuer_cache_key("einzige-seite")
    assert alerts[0].capture_id == erwartet, (
        f"Bei eindeutiger Herkunft MUSS die Naht anreichern: "
        f"{alerts[0].capture_id!r} != {erwartet!r}"
    )
