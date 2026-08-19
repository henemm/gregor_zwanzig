"""TDD RED — Issue #1727 S5e (A): Der Sperren-Zwischenspeicher folgt dem Kalendertag.

SPEC: docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md (AC-1, AC-2)

``_get_cached_daily_json(src, ymd)`` (``massif_closure.py:98-112``) uebergibt
``cache_key=src`` an ``warn_egress.cached_fetch`` -- der Tag ``ymd`` steht zwar
in der URL, aber NICHT im Schluessel. Innerhalb der 1800s-Erfolgs-TTL liefert
der Zwischenspeicher darum ueber einen Kalendertagwechsel hinweg die Daten des
VORTAGS: eine ueber Nacht neu verhaengte Zugangssperre bleibt bis zu 30 Minuten
unsichtbar. Vorbild fuer die Loesung ist ``meteoalarm.py:768``
(``f"{country}:{slot}:p{page}"``) -- dort ist der Zeitanteil laengst Teil des
Schluessels.

RED-Gruende (gemessen, nicht vermutet):
- AC-1: zweiter Abruf am Folgetag trifft den Eintrag von ``"83"`` und loest
  keinen zweiten HTTP-Request aus -> ``len(requested_paths) == 1``.
- AC-2: der einzige Schluessel im Zwischenspeicher heisst ``"83"`` und traegt
  keinen Tag -> die Tages-Zuordnung ist von aussen gar nicht pruefbar.

**Warum 10 Minuten und nicht 24 Stunden Abstand:** ``cached_fetch`` misst die
TTL ueber ``time.monotonic`` (``warn_egress.py:431``), dessen Verhalten unter
``freeze_time`` nicht Teil der Zusicherung ist. Ein 24-Stunden-Sprung koennte
die TTL ablaufen lassen und damit den zweiten Request AUCH OHNE Fix erzwingen
-- der Nachweis waere wertlos. Die beiden Zeitpunkte liegen darum nur 10
Minuten auseinander (600s << 1800s TTL) und trotzdem in verschiedenen
PARISER Kalendertagen, weil sie die dortige Mitternacht einschliessen. Damit
kann der zweite Request nur eine Ursache haben: den Tag im Schluessel.

Die Gegenprobe ``test_positivkontrolle_...`` haelt fest, dass der
Zwischenspeicher INNERHALB eines Tages weiterhin greift -- sonst waere AC-1
auch dadurch zu erfuellen, dass man das Zwischenspeichern ganz abschaltet.

Testpolitik (CLAUDE.md "Zwei Schichten"): Kern-Schicht, kein Netz nach aussen.
Der lokale ``http.server``-Sentinel wird aus ``#1727 S5d`` wiederverwendet
statt kopiert. Er liefert fuer JEDEN Pfad denselben Rumpf
(``{"massifs": {"831": [1]}}``) -- der Nachweis laeuft deshalb ueber die
angefragten PFADE, nicht ueber unterschiedliche Inhalte (Spec, "Offene Punkte").
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from freezegun import freeze_time

from tests.tdd.conftest import _anker
from tests.tdd.test_import_und_fremdquellen_folgen_ortstag import (
    TOULON,
    _lokaler_massif_server,
)

# 2026-06-01 21:55 UTC = 23:55 CEST (Pariser Tag 06-01)
# 2026-06-01 22:05 UTC = 00:05 CEST (Pariser Tag 06-02)  -> Tageswechsel
VOR_MITTERNACHT = datetime(2026, 6, 1, 21, 55, 0, tzinfo=timezone.utc)
NACH_MITTERNACHT = datetime(2026, 6, 1, 22, 5, 0, tzinfo=timezone.utc)
TAG_DAVOR = date(2026, 6, 1)
TAG_DANACH = date(2026, 6, 2)

# Zweiter Zeitpunkt am SELBEN Pariser Tag, gleicher Abstand -- Gegenprobe.
SPAETER_AM_SELBEN_TAG = datetime(2026, 6, 1, 22, 5, 0, tzinfo=timezone.utc).replace(
    hour=21, minute=59,
)


def _zwei_abrufe_ohne_leerung(monkeypatch, erster: datetime, zweiter: datetime):
    """Zwei ``fetch()``-Aufrufe gegen denselben lokalen Sentinel, ohne den
    Zwischenspeicher dazwischen zu leeren.

    Das ist die bewusste Umkehrung des Bestands-Helfers
    ``_fetch_gegen_lokalen_server()`` (``test_import_und_fremdquellen_folgen_
    ortstag.py:163-180``), der vor JEDEM Aufruf ``_cache.clear()`` ruft und
    damit genau den Fall umgeht, den diese Scheibe prueft.

    Rueckgabe: (angefragte Pfade, Kopie der Schluessel des Zwischenspeichers).
    """
    from services.official_alerts import massif_closure
    from services.official_alerts.massif_closure import MassifClosureSource

    massif_closure._cache.clear()  # sauberer Start -- NICHT zwischen den Aufrufen
    try:
        with _lokaler_massif_server() as (srv, requested_paths):
            monkeypatch.setattr(
                massif_closure, "_ENDPOINT",
                f"http://127.0.0.1:{srv.server_port}"
                "/static/{src}/import_data/{ymd}.json",
            )
            with freeze_time(erster):
                MassifClosureSource().fetch(*TOULON)
            with freeze_time(zweiter):
                MassifClosureSource().fetch(*TOULON)
            schluessel = sorted(massif_closure._cache.keys())
        return list(requested_paths), schluessel
    finally:
        massif_closure._cache.clear()  # kein Uebersprung in Nachbartests


def test_ac1_zweiter_kalendertag_loest_echten_zweiten_abruf_aus(monkeypatch):
    """AC-1.

    GIVEN fuer dieselbe Massiv-Quelle wurde kurz vor Pariser Mitternacht das
          Tages-JSON abgerufen und liegt innerhalb der 1800s-Erfolgs-TTL im
          Zwischenspeicher,
    WHEN  zehn Minuten spaeter -- nach Mitternacht in Paris, also am naechsten
          Kalendertag des HERAUSGEBERS -- erneut ``fetch()`` laeuft, ohne dass
          der Zwischenspeicher dazwischen geleert wurde,
    THEN  loest der zweite Aufruf einen echten zweiten HTTP-Request aus, und
          dieser fragt den Endpunkt des ZWEITEN Tages ab.

    RED-Grund: ``cache_key=src`` (``massif_closure.py:108``) kennt keinen Tag
    -- der zweite Aufruf trifft den Eintrag des Vortags und schweigt.
    """
    _anker(NACH_MITTERNACHT, "Europe/Paris", TAG_DANACH)
    assert VOR_MITTERNACHT.astimezone(timezone.utc).date() == TAG_DAVOR
    assert (NACH_MITTERNACHT - VOR_MITTERNACHT).total_seconds() == 600, (
        "Testaufbau: die beiden Zeitpunkte muessen INNERHALB der 1800s-TTL "
        "liegen, sonst erzwingt schon der Ablauf den zweiten Request"
    )

    pfade, _ = _zwei_abrufe_ohne_leerung(
        monkeypatch, VOR_MITTERNACHT, NACH_MITTERNACHT,
    )

    erwartet_tag1 = f"/static/83/import_data/{TAG_DAVOR:%Y%m%d}.json"
    erwartet_tag2 = f"/static/83/import_data/{TAG_DANACH:%Y%m%d}.json"
    assert pfade == [erwartet_tag1, erwartet_tag2], (
        f"angefragte Pfade: {pfade!r} -- erwartet genau zwei Abrufe "
        f"({erwartet_tag1}, dann {erwartet_tag2}). Nur ein Pfad bedeutet: der "
        f"Zwischenspeicher hat ueber den Kalendertagwechsel hinweg die Daten "
        f"des Vortags geliefert -- eine ueber Nacht verhaengte Sperre bliebe "
        f"bis zu 30 Minuten unsichtbar."
    )


def test_ac2_zwischenspeicher_behaelt_nur_den_eintrag_des_aktuellen_tages(monkeypatch):
    """AC-2.

    GIVEN der Zwischenspeicher enthaelt nach dem ersten Abruf einen Eintrag
          fuer Quelle 83 und den Pariser Tag 2026-06-01,
    WHEN  der zweite Abruf fuer dieselbe Quelle am Tag 2026-06-02
          abgeschlossen ist,
    THEN  ist der Eintrag des Vortags entfernt und es existiert genau ein
          Schluessel fuer diese Quelle -- der des zweiten Tages.

    Ohne das Aufraeumen wuechse ``_cache`` in einem langlebigen Prozess pro
    Quelle und Kalendertag unbegrenzt: ``warn_egress`` kennt keine
    Invalidierung, Eintraege verfallen nur beim Zugriff auf DENSELBEN
    Schluessel (``warn_egress.py:431-434``).

    RED-Grund: es gibt heute genau einen, tageslosen Schluessel ``"83"``.
    """
    _anker(NACH_MITTERNACHT, "Europe/Paris", TAG_DANACH)

    _, schluessel = _zwei_abrufe_ohne_leerung(
        monkeypatch, VOR_MITTERNACHT, NACH_MITTERNACHT,
    )

    eigene = [k for k in schluessel if k == "83" or k.startswith("83:")]
    assert eigene == [f"83:{TAG_DANACH:%Y%m%d}"], (
        f"Schluessel im Zwischenspeicher fuer Quelle 83: {eigene!r} -- "
        f"erwartet genau einen, naemlich '83:{TAG_DANACH:%Y%m%d}'. Ein "
        f"tagesloser Schluessel '83' kann den Tageswechsel nicht abbilden; "
        f"zwei Schluessel bedeuten, dass der Vortag nicht aufgeraeumt wurde."
    )


def test_positivkontrolle_zwischenspeicher_greift_innerhalb_eines_tages(monkeypatch):
    """Gegenprobe -- KEIN AC, sondern der Waechter gegen die billige Loesung.

    GIVEN zwei Abrufe derselben Quelle liegen zehn Minuten auseinander, aber
          im SELBEN Pariser Kalendertag,
    WHEN  beide ``fetch()``-Aufrufe ohne Leerung des Zwischenspeichers laufen,
    THEN  kommt genau EIN HTTP-Request beim Sentinel an.

    Dieser Test ist heute gruen und muss es bleiben. Er schliesst aus, dass
    AC-1 dadurch erfuellt wird, dass das Zwischenspeichern ueberhaupt
    abgeschaltet oder der Schluessel z.B. auf die Uhrzeit gestuetzt wird --
    beides wuerde den Egress-Schutz aushebeln, den ``cached_fetch`` gerade
    bereitstellt (Issue #1348).
    """
    assert SPAETER_AM_SELBEN_TAG.astimezone(timezone.utc).date() == TAG_DAVOR
    assert (SPAETER_AM_SELBEN_TAG - VOR_MITTERNACHT).total_seconds() == 240

    pfade, _ = _zwei_abrufe_ohne_leerung(
        monkeypatch, VOR_MITTERNACHT, SPAETER_AM_SELBEN_TAG,
    )

    assert pfade == [f"/static/83/import_data/{TAG_DAVOR:%Y%m%d}.json"], (
        f"angefragte Pfade: {pfade!r} -- erwartet genau EINEN Abruf. Zwei "
        f"Abrufe am selben Kalendertag bedeuten, dass der Zwischenspeicher "
        f"nicht mehr greift (Egress-Schutz aus #1348 verloren)."
    )
