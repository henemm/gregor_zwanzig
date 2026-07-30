"""MeteoAlarmSource — amtliche Warnungen Österreich/Italien (Issue #1086, Slice 2).

Zweite Nicht-Frankreich-Quelle für die #1034-Official-Alerts-Registry. Ruft
die amtliche OGC-EDR-API ``api.meteoalarm.org`` ab (Länder-Index -> exakte
Fläche via ``geometry``-Link -> Punkt-in-Fläche-Filter -> CAP-XML via
``hubLink``) und bringt Italien erstmals in die amtlichen Warnungen sowie
Österreich redundant zu ``GeoSphereWarnSource``. Cross-Source-Dedup pro
einzelnem Punkt in ``get_official_alerts_for_location()`` (``base.py``,
Issue #1086 Adversary-Korrektur F002) -- ``dedup_id`` bleibt ``None``.

Fail-soft: fehlende ENV ``GZ_METEOALARM_APIKEY`` oder jeder HTTP-/Parse-Fehler
(Index-JSON, geometry-Link, CAP-XML) -> ``fetch()`` liefert ``[]`` bzw.
überspringt das betroffene Feature/Land, wirft nie.

SPEC: docs/specs/modules/issue_1086_meteoalarm_source.md
"""
from __future__ import annotations

import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import httpx

from services.official_alerts import warn_egress
from services.official_alerts.department_mapper import lookup_department
from services.official_alerts.meteoalarm_budget import MeteoAlarmBudgetGate
from services.official_alerts.models import OfficialAlert
from services.radar_service import (
    _DPC_LAT_MAX,
    _DPC_LAT_MIN,
    _DPC_LON_MAX,
    _DPC_LON_MIN,
    _INCA_LAT_MAX,
    _INCA_LAT_MIN,
    _INCA_LON_MAX,
    _INCA_LON_MIN,
)

logger = logging.getLogger("meteoalarm")

METEOALARM_BASE_URL = "https://api.meteoalarm.org/edr/v1"
TIMEOUT = 8.0
# Issue #1348: Erfolgs-/Failure-TTL aus dem geteilten Egress-Kern (1800s/60s).
# Attributname + Rolle im Cache-Eintrag bleiben, der Wert steigt auf 1800s.
CACHE_TTL = warn_egress.WARN_SUCCESS_TTL  # 1800.0 — Erfolgs-Fenster (30 min)
FAILURE_CACHE_TTL = warn_egress.WARN_FAILURE_TTL  # 60.0 — kurzes Failure-Fenster
# Issue #1397: Flaeche (geometry-Link) und CAP-Dokument einer Warnung sind
# unveraenderlich -- Aenderungen kommen als neue alertId, keine neue Fassung
# unter derselben OBJECTID/alertId. Lange Erfolgs-TTL (6h) statt der
# warngerechten 30 Minuten, damit die frueher URL-basierten Caches (die bei
# jeder Index-Erneuerung wegen rotierender Presigned-Signatur verwaisten)
# tatsaechlich ueber mehrere Index-Zyklen hinweg greifen.
GEOMETRY_CAP_TTL = 6 * 3600.0
# Adversary F001 (Issue #1397 Fix-Loop): real gemessen wurden 17-21 Seiten,
# eine aufgezeichnete Antwort (index_at.json) trug sogar total_pages=79 --
# 50 kappte also aktiv echte Warnlagen weg. 200 gibt Luft; wird die Grenze
# TROTZDEM ueberschritten, gilt der Index als unvollstaendig -> Ausfall
# (s. _resolve_total_pages), NIE stilles Kappen. Seiten sind 30 Minuten
# gecacht und werden ueber alle Punkte/Nutzer geteilt -- der Mehrverbrauch
# bei 200 statt 50 Seiten bleibt beherrscht.
_MAX_INDEX_PAGES = 200
_BBOX_MARGIN_DEG = 0.01

# Issue #1397 Scheibe S1b: die API bremst Index-Seiten kurzzeitig aus
# (Messung 2026-07-27 gegen api.meteoalarm.org/edr/v1/.../AT: ~1 Anfrage/4s,
# danach HTTP 429 ohne ``Retry-After``, aber mit ``x-ratelimit-reset`` als
# Unix-Sekunden). Seite 2 von S1s vollstaendigem Blaettern traf das sofort
# und liess IN PRODUKTION alle MeteoAlarm-Warnungen ausfallen (vorher kam
# wenigstens Seite 1 durch) -- diese Konstanten steuern die zwei
# Gegenmassnahmen: 429-Wiederholung (``_RATE_LIMIT_RETRY``) und vorbeugender
# Abstand vor jedem Folgeseiten-Abruf (``_throttle_before_next_page``).
# Injizierbar fuer Tests (kein echtes Warten in der Kern-Schicht).
_SLEEP_FN: Callable[[float], None] = time.sleep
_WALL_CLOCK_FN: Callable[[], float] = time.time
_PAGE_THROTTLE_DEFAULT_SECONDS = 4.0  # Messung: Bremse greift ~alle 4s
_PAGE_THROTTLE_MAX_SECONDS = 8.0  # Deckel, falls x-ratelimit-reset weit weg liegt


def _rate_limit_retry_policy() -> warn_egress.RateLimitRetryPolicy:
    """Baut die Policy bei JEDEM Aufruf frisch aus den aktuellen (ggf. in
    Tests monkeygepatchten) Modul-Funktionen ``_SLEEP_FN``/``_WALL_CLOCK_FN``."""
    return warn_egress.RateLimitRetryPolicy(
        sleep_fn=_SLEEP_FN,
        wall_clock_fn=_WALL_CLOCK_FN,
    )


def _throttle_before_next_page(last_reset_ts: Optional[float]) -> None:
    """Vorbeugender Abstand vor dem naechsten Seiten-Abruf, damit die
    Ratenbremse nicht bei jeder zweiten Seite ausgeloest wird. Bevorzugt aus
    ``x-ratelimit-reset`` der letzten Antwort abgeleitet (warten bis exakt
    dahin, gedeckelt); ohne verwertbaren Header ein fester Abstand in der
    Groessenordnung der Messung."""
    if last_reset_ts is not None:
        wait = last_reset_ts - _WALL_CLOCK_FN()
        wait = max(0.0, min(wait, _PAGE_THROTTLE_MAX_SECONDS))
    else:
        wait = _PAGE_THROTTLE_DEFAULT_SECONDS
    if wait > 0:
        _SLEEP_FN(wait)


# ---------------------------------------------------------------------------
# Issue #1397 Scheibe S1c: EIN Aufruf blaettert bei 17-23+ Seiten (AT) selbst
# mit Entzerrung zu lange fuer den synchronen Sendeweg (120s-Client-Timeout
# im Go-Scheduler, s. Bericht). Statt alles in einem Aufruf zu holen, wird
# schrittweise ueber MEHRERE Scheduler-Aufrufe hinweg nachgeladen: das
# Zeitfenster wird auf einen festen 30-Minuten-Rasterpunkt gerundet, damit
# Seiten verschiedener Aufrufe DENSELBEN Cache-Schluessel-Praefix teilen und
# sich zusammensetzen lassen; ein Zeitbudget je Aufruf begrenzt, wie viele
# Seiten EIN Aufruf nachlaedt.
# ---------------------------------------------------------------------------
# Issue #1397 Scheibe S1: Rasterbreite 30 -> 60 Minuten. Bei 30 Minuten wurde
# dasselbe Fenster sechsfach ueberlappend neu geholt (3h-Fenster alle 30 min);
# stuendlich reicht, weil die Rueckschau jetzt aus dem kumulierten Bestand
# kommt und nicht mehr aus der Fensterbreite (s. Block unten).
_SLOT_MINUTES = 60  # Rasterbreite des Auffrischungs-Zeitfensters.
# Laenger als ein Zeitslot (s. _SLOT_MINUTES), damit zuerst geholte Seiten
# noch leben, wenn ein spaeterer Aufruf im SELBEN Slot die letzten Seiten
# nachholt (Slot 60 min + 30 min Reserve; mit dem alten 30-min-Raster waren
# es 45 min aus demselben Grund).
INDEX_PAGE_SUCCESS_TTL = 90 * 60.0  # 5400.0s
# Zeitbudget je Aufruf fuers Blaettern: der Abruf laeuft synchron im
# Sendeweg. Bei ~4s Rasterabstand (Messung) schafft ein Aufruf ~5 Seiten;
# der Scheduler ruft mehrfach pro Viertelstunde auf (mehrere Endpunkte/
# Nutzer) -- der Rest kommt ueber die naechsten Aufrufe im selben Zeitslot
# nach (s. Bericht: typ. 4-5 Aufrufe bis AT komplett ist).
_PAGE_FETCH_BUDGET_SECONDS = 20.0


class _MeteoAlarmBudgetExhausted(Exception):
    """Internes Signal (Issue #1397 S1c-Nachbesserung, Tageskontingent-Fund):
    das eigene Tagesbudget (``MeteoAlarmBudgetGate``) ist erschoepft -- KEIN
    echter Netzwerk-Call wurde ausgeloest. ``warn_egress.cached_fetch()``
    faengt das ueber den generischen Exception-Zweig ab (Fail-soft-Cache,
    Egress-Zeile, ``observe_fetch_failure()``-Markierung) -- exakt derselbe
    Ausfall-Pfad wie fuer jeden anderen fehlgeschlagenen Seiten-Abruf."""


def _meteoalarm_budget_gate() -> MeteoAlarmBudgetGate:
    """Frisch instanziiert je Aufruf (Muster ``ForecastBudgetGate``-Tests) --
    liest/schreibt ueber ``app.loader.get_data_root()``, in Tests durch die
    globale Autouse-Isolation (``tests/conftest.py``, Issue #1133) bereits
    auf einen Temp-Pfad umgelenkt."""
    return MeteoAlarmBudgetGate()


# Issue #1397 Scheibe S1 (2026-07-30): Rueckschau und Abrufaufwand sind
# ENTKOPPELT. Vorher war beides dieselbe Stellschraube -- das Abfragefenster
# war zugleich der gesamte sichtbare Bestand, weil ``_prune_stale_slot_
# entries()`` bei jedem Slot-Wechsel alles bisher Gesehene verwarf. Beide
# Enden dieser Kopplung sind gemessen (tests/tdd/test_meteoalarm_index_
# coverage.py, Profil des Gewittertags 29.07.): 23h-Fenster alle 30 min =
# 844 echte Abrufe/24h (Kontingent gesprengt), 3h-Fenster = 156 Abrufe/24h,
# aber jede laenger als 3h zurueckliegende, weiter gueltige Veroeffentlichung
# fiel aus dem Briefing. Die im S1c-Kommentar offengebliebene Frage ("gibt es
# solche Faelle ueberhaupt?") ist damit beantwortet: der Verlust tritt real
# ein, reproduziert in AC-1.
#
# Jetzt zwei getrennte Groessen:
#   * BESTAND (``_country_store``): kumuliert ueber Zyklen hinweg, ein Eintrag
#     bleibt bis zum Ablauf SEINER GUELTIGKEIT (Rueckfall ohne bekannte
#     Gueltigkeit: ``_STORE_RETENTION_HOURS``) -- das ist, was der Nutzer sieht.
#   * AUFFRISCH-FENSTER (``_index_query_window``): nur der Abstand zur letzten
#     VOLLSTAENDIGEN Auffrischung plus ``_REFRESH_OVERLAP_HOURS`` -- das ist,
#     was wir bezahlen (stuendlich ~2h = doppelte statt sechsfacher
#     Ueberlappung).
# Kaltstart (Neustart/Deploy, keine Fortschrittsmarke): einmalig
# ``DEFAULT_INDEX_WINDOW_HOURS`` breit, damit die Rueckschau sofort steht
# statt sich erst ueber einen Tag aufzubauen.
DEFAULT_INDEX_WINDOW_HOURS = 23.0  # Kaltstart-Breitband (= Rueckschau-Tiefe)
# ACHTUNG, NICHT "mal eben" anheben: die 23 sind keine Vorsichtsmarge, sondern
# die harte Anbieter-Grenze -- der ``datetime``-Bereich ist bei der EDR-API
# Pflicht und MUSS unter 24 Stunden liegen, sonst wird die Anfrage abgelehnt
# (Live-Messung 2026-07-15, Issue #1086). Gilt fuer JEDEN Zweig, auch fuer den
# ENV-Override ``GZ_METEOALARM_WINDOW_HOURS``.
# Ueberlappung im Regelbetrieb: MINDESTENS eine volle Slot-Breite, damit jeder
# Veroeffentlichungszeitpunkt -- auch einer exakt auf der Fenstergrenze -- von
# zwei aufeinanderfolgenden Fenstern erfasst wird (eine spaeter nachgetragene
# Aenderung an einer Warnung, z.B. der Ueberholt-Vermerk, kommt so noch mit).
_REFRESH_OVERLAP_HOURS = 1.0
# Verfall des Bestands -- RUECKFALL fuer Eintraege, deren Gueltigkeit UNBEKANNT
# ist: so lange bleibt ein einmal gesehenes, nicht ueberholtes Feature, ohne in
# einer frischen Antwort erneut aufzutauchen. Fuer Eintraege MIT bekannter
# Gueltigkeit ist nicht mehr der Zeitpunkt des Sehens maßgeblich, sondern der
# Ablauf der Warnung selbst (Adversary F004, Fix-Loop 2 -- s.
# ``_entry_verfallen``).
_STORE_RETENTION_HOURS = 23.0
# Deckel gegen einen Eintrag, der den Bestand wegen einer absurd weit in der
# Zukunft liegenden (fehlerhaften) ``expires``-Angabe dauerhaft belegt --
# grosszuegig ueber der laengsten realen amtlichen Warndauer (mehrtaegige
# Hitze-/Kaeltewarnungen laufen 2-5 Tage).
_STORE_MAX_VALIDITY_HOURS = 7 * 24.0
_STORE_KEY_SUFFIX = ":bestand"
# BEWUSST KEINE "Bestaetigungsfrist" und kein daraus abgeleitetes Ausfall-
# Signal (Fix-Loop 5, ersetzt Fix-Loop 3 UND 4): das Ausfall-Signal
# ("amtliche Warnungen aktuell nicht abrufbar") bleibt echten Stoerungen
# vorbehalten -- fehlgeschlagener Abruf, unvollstaendiger Zyklus, gekappte
# Rueckschau, Ratenbremse. Gemessen: an eine laenger nicht mehr frisch
# gesehene Warnung gekoppelt, stand der Hinweis in 81,9 % aller Zyklen eines
# 3-Tage-Laufs OHNE jede Stoerung -- ein Sicherheitshinweis, der fast immer
# dasteht, wird ueberlesen, und sein Wortlaut waere hier sachlich falsch (die
# Warnung IST abrufbar und wird gezeigt, wir koennen sie nur nicht erneut
# bestaetigen). Was ein Rueckzug ausserhalb des schmalen Auffrisch-Fensters
# kostet, steht als bewusste Abwaegung in den Known Limitations der Spec.


def _window_override_hours() -> Optional[float]:
    """``GZ_METEOALARM_WINDOW_HOURS`` (positive Zahl): erzwingt EINE feste
    Fensterbreite fuer JEDEN Zyklus (Kaltstart wie Auffrischung) -- ohne
    Deploy nachziehbar, analog ``GZ_METEOALARM_DAILY_BUDGET``. Nicht gesetzt,
    unlesbar oder nicht-positiv -> ``None`` (kein Override, fail-soft)."""
    raw = os.environ.get("GZ_METEOALARM_WINDOW_HOURS")
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = 0.0
        if value > 0:
            return value
    return None


def _index_window_hours() -> float:
    """Fensterbreite, wenn KEIN Fortschritt bekannt ist (Kaltstart):
    ENV-Override > ``DEFAULT_INDEX_WINDOW_HOURS``."""
    return _window_override_hours() or DEFAULT_INDEX_WINDOW_HOURS


def _store_retention_hours() -> float:
    """Rueckfall-Aufbewahrung fuer Eintraege ohne bekannte Gueltigkeit
    (Adversary F005, Fix-Loop 2 -- vorher behauptete der Docstring von
    ``_index_query_window()`` "derselbe Wert" wie die Abfragebreite, obwohl
    ``_STORE_RETENTION_HOURS`` ein davon unabhaengiges Literal war und ein
    gesetztes ``GZ_METEOALARM_WINDOW_HOURS`` nur die Abfragebreite verschob).

    Jetzt eine echte Kopplung mit klarer Richtung: MINDESTENS so breit wie das
    Abfragefenster. Kuerzer waere widersinnig -- der Bestand wuerde wegwerfen,
    was ein Zyklus gerade erst geholt hat."""
    return max(_STORE_RETENTION_HOURS, _index_window_hours())


def _current_slot_end(now_dt: datetime) -> datetime:
    """Rundet das Fensterende auf die naechste ``_SLOT_MINUTES``-Rasterzelle
    ab. Innerhalb DESSELBEN Slots sind alle Aufrufe parameter-gleich (Start/
    Ende identisch) -- ihre Seiten lassen sich zusammensetzen, ueber einen
    Slot-Wechsel hinweg NICHT (neue Rand-Warnungen faellig)."""
    floored_minute = (now_dt.minute // _SLOT_MINUTES) * _SLOT_MINUTES
    return now_dt.replace(minute=floored_minute, second=0, microsecond=0)


def _slot_key(slot_end: datetime) -> str:
    return slot_end.strftime("%Y%m%dT%H%MZ")


def _country_store(country: str) -> dict:
    """Kumulierter Bestand + Fortschrittsmarke eines Landes (Issue #1397 S1).

    Liegt bewusst IM ``_index_cache``-Dict unter einem reservierten
    Schluessel (``AT:bestand``, ohne ``:p<n>``-Endung): Bestand und
    Seiten-Cache haben damit GENAU denselben Lebenszyklus -- ein
    Prozess-Neustart und jedes ``_index_cache.clear()`` leeren beides
    zusammen. Zwei getrennte Modul-Dicts waeren zwei Stellen, die man beim
    Leeren vergessen kann, und genau daran haengt die Kaltstart-Erkennung.

    ``features``: Dedup-Schluessel (s. ``_feature_dedup_key``) ->
    ``{"feature": <rohes Index-Feature>, "seen_at": <Wanduhr-Sekunden>,
    "valid_until": <Wanduhr-Sekunden oder None>}``. ``valid_until`` traegt die
    aus dem CAP-Dokument aufgeloeste Gueltigkeit, sofern sie bekannt ist
    (s. ``_remember_validity``); ``None`` = unbekannt.
    ``last_complete``: Slot-Ende des letzten VOLLSTAENDIG geholten Zyklus
    (``None`` = Kaltstart)."""
    return _index_cache.setdefault(
        f"{country}{_STORE_KEY_SUFFIX}", {"features": {}, "last_complete": None}
    )


def _merge_into_store(country: str, features: list[dict], now_ts: float) -> list[dict]:
    """Mischt frisch geholte Features in den Bestand und liefert den GESAMTEN
    gueltigen Bestand zurueck (Issue #1397 S1 -- vorher war das Ergebnis auf
    das Abfragefenster beschraenkt, weshalb die Rueckschau nie weiter reichte
    als eine Fensterbreite).

    Die Aufraeum-Absicht der frueheren Slot-Loeschung bleibt, die Grenze
    wandert von "fremder Slot" auf "ueberholt oder abgelaufen":
    * **ueberholt:** taucht ein Feature mit ``supersededAt``/
      ``supersededByAlertId`` auf, fliegt SEIN Bestands-Eintrag raus (gleicher
      Dedup-Schluessel). Gemessen waren ~98 % aller Features eines
      23h-Fensters ueberholte Fassungen -- ohne dieses sofortige Entfernen
      waere der Bestand fast vollstaendig Ballast. Der Filter in ``fetch()``
      bleibt trotzdem stehen (ein Feature kann bereits ueberholt herein-
      kommen, ohne je unueberholt im Bestand gewesen zu sein).
    * **abgelaufen/zu alt:** die Gueltigkeit der Warnung ist vorbei -- bzw.,
      wo sie unbekannt ist, greift die alte Zeitgrenze als Rueckfall (s.
      ``_entry_verfallen``). Das bleibt die Obergrenze gegen unbegrenztes
      Wachstum."""
    store = _country_store(country)["features"]
    for feature in features:
        key = _feature_dedup_key(feature)
        if _is_superseded(feature):
            store.pop(key, None)
            continue
        # Read-Modify-Write (Projektregel): eine bereits aufgeloeste
        # Gueltigkeit MUSS das Wiedersehen ueberleben -- sonst faellt die
        # Aufbewahrung beim naechsten Zyklus still auf die Zeitgrenze zurueck
        # und der Fund waere nur scheinbar behoben.
        bekannt = store.get(key) or {}
        store[key] = {
            "feature": feature,
            "seen_at": now_ts,
            "valid_until": bekannt.get("valid_until"),
        }
    for key in [k for k, entry in store.items() if _entry_verfallen(entry, now_ts)]:
        del store[key]
    return [entry["feature"] for entry in store.values()]


def _entry_verfallen(entry: dict, now_ts: float) -> bool:
    """Wann ein Bestands-Eintrag den Bestand verlaesst (Adversary F004,
    Fix-Loop 2).

    Maßgeblich ist die **Gueltigkeit** der Warnung, nicht der Zeitpunkt, an dem
    wir sie zuletzt **gesehen** haben. Der Anbieter filtert seinen Index nach
    dem VEROEFFENTLICHUNGS-Zeitpunkt in einem Bereich von unter 24 Stunden (s.
    ``DEFAULT_INDEX_WINDOW_HOURS``) -- "seit 23h nicht mehr im Abfragefenster
    aufgetaucht" heisst deshalb NIE "gilt nicht mehr". Genau daran hing der
    Fund: nach einem Ausfall laenger als 23h verschwand eine VOR dem Ausfall
    gesehene, weiterhin gueltige Warnung lautlos aus dem Bestand und konnte
    ueber den Index nie wieder hereinkommen -- ab dem zweiten Zyklus nach dem
    Wiederanlauf meldete das Briefing wieder "keine Warnung" (unavailable=
    False) bei bestehender Gefahr. Fuer Italien besonders schwer, weil
    MeteoAlarm dort die einzige amtliche Quelle ist.

    Rueckfall auf die Zeitgrenze (``_store_retention_hours()``), wenn die
    Gueltigkeit UNBEKANNT ist: die Index-Features tragen sie nicht (nur
    ``hubTime`` = Veroeffentlichung), sie steht erst im CAP-Dokument -- und das
    wird nur fuer Features geholt, die den bbox-Vorfilter eines echten Ortes
    passieren (s. ``fetch()``). Fuer alles, was nie ueber den Vorfilter hinaus
    aufgeloest wurde, bleibt es damit beim bisherigen Verhalten.

    ``_STORE_MAX_VALIDITY_HOURS`` deckelt eine absurd weit in der Zukunft
    liegende Gueltigkeit, damit ein einzelner Eintrag den Bestand nicht
    unbegrenzt belegen kann."""
    valid_until = entry.get("valid_until")
    if valid_until is not None:
        deckel = entry["seen_at"] + _STORE_MAX_VALIDITY_HOURS * 3600.0
        return now_ts >= min(valid_until, deckel)
    return entry["seen_at"] < now_ts - _store_retention_hours() * 3600.0


def _as_utc(value: datetime) -> datetime:
    """Naiven (tz-losen) CAP-Zeitstempel als UTC lesen -- analog
    ``base._as_aware_utc``, damit ``.timestamp()`` nicht auf die Zeitzone des
    Servers ausweicht und die Aufbewahrung dadurch um Stunden verrutscht."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _remember_validity(country: str, feature: dict, alerts: list[OfficialAlert]) -> None:
    """Haelt die aus dem CAP-Dokument aufgeloeste Gueltigkeit am Bestands-
    Eintrag fest (Adversary F004, Fix-Loop 2). Das ist die EINZIGE Stelle, an
    der sie ueberhaupt bekannt wird: der Laender-Index kennt nur den
    Veroeffentlichungs-Zeitpunkt, das Ende steht im CAP (``expires``). Ohne
    diesen Vermerk faellt die Aufbewahrung auf die Zeitgrenze zurueck (s.
    ``_entry_verfallen``).

    Genommen wird das SPAETESTE ``expires`` aller Warnungen des Dokuments (ein
    CAP kann mehrere ``<info>``-Bloecke tragen) -- der Eintrag darf erst gehen,
    wenn die letzte davon abgelaufen ist. Fehlt jedes ``expires`` (oder ist das
    Feature nicht mehr im Bestand), bleibt die Gueltigkeit unbekannt und der
    Rueckfall greift -- fail-soft, nie ein Fehler."""
    entry = _country_store(country)["features"].get(_feature_dedup_key(feature))
    enden = [a.valid_to for a in alerts if a.valid_to is not None]
    if entry is None or not enden:
        return
    entry["valid_until"] = max(_as_utc(ende) for ende in enden).timestamp()


def _index_query_window(country: str, slot_end: datetime) -> tuple[datetime, datetime, bool]:
    """Zeitfenster EINES Auffrischungs-Zyklus (Issue #1397 S1) plus die Angabe,
    ob die Rueckschau dabei GEKAPPT wurde.

    Regelfall: vom Ende der letzten VOLLSTAENDIGEN Auffrischung minus
    ``_REFRESH_OVERLAP_HOURS`` bis zum aktuellen Slot-Ende. Das deckt jede
    Luecke seit dem letzten Erfolg ab (auch mehrere ausgefallene Zyklen --
    das Fenster waechst dann von selbst mit) plus eine volle Slot-Breite
    Ueberlappung. Kaltstart (keine Fortschrittsmarke) ODER gesetzter
    ENV-Override: feste Breite (s. ``_index_window_hours``). ``min()``
    schuetzt gegen eine rueckwaerts gestellte Uhr -- das Fenster darf nie
    leer oder negativ werden.

    Adversary F001 (Fix-Loop 1): das mitwachsende Fenster hatte KEINE
    Obergrenze. Bleibt die Fortschrittsmarke haengen (kein Zyklus wird je
    vollstaendig -- laut Messung im Modulkopf durch die Ratenbremse real
    moeglich), wuchs es unbegrenzt weiter (gemessen 1057h Breite bei 44 Tagen
    Stillstand) und zog immer mehr Seiten pro Zyklus nach sich, bis KEIN
    Zyklus mehr in ein Zeitbudget passte -- ein sich selbst verstaerkender
    Zustand. Beide Zweige haengen jetzt an DERSELBEN Obergrenze
    (``_index_window_hours()``, ENV-Override eingeschlossen): breiter zu fragen
    holt ohnehin nur Veroeffentlichungen nach, deren Eintrag der Bestand ohne
    bekannte Gueltigkeit nicht laenger haelt (``_store_retention_hours()`` --
    MINDESTENS diese Breite, im ENV-Override-Fall NICHT derselbe Wert, s.
    Adversary F005), und die 23 statt 24 Stunden im Default stehen genau
    dafuer, dass die API den Abfragebereich ihrerseits auf einen Tag begrenzt.

    Drittes Rueckgabefeld ``gekappt``: True, wenn der Rueckstand GROESSER war
    als die Obergrenze -- dann fehlt dem Zyklus ein Stueck Rueckschau, das er
    nie nachholt. Der Aufrufer muss das wie einen abgebrochenen Zyklus
    behandeln (``mark_fetch_incomplete()``), sonst waere genau das der stille
    Ausfall, gegen den #1397 laeuft."""
    override = _window_override_hours()
    last_complete = _country_store(country)["last_complete"]
    frueheste = slot_end - timedelta(hours=_index_window_hours())
    if override is not None or last_complete is None:
        return frueheste, slot_end, False
    gewuenscht = min(last_complete, slot_end) - timedelta(hours=_REFRESH_OVERLAP_HOURS)
    if gewuenscht < frueheste:
        return frueheste, slot_end, True
    return gewuenscht, slot_end, False


def _prune_stale_slot_entries(country: str, current_slot: str) -> None:
    """Entfernt SEITEN-Cache-Eintraege fremder Zeitslots desselben Landes --
    sonst waechst ``_index_cache`` bei jedem Slot-Wechsel unbegrenzt weiter,
    weil abgelaufene Eintraege nur beim naechsten LESE-Zugriff auf GENAU
    diesen Schluessel entdeckt wuerden (der bei einem alten Slot nie wieder
    vorkommt).

    Der kumulierte Bestand (reservierter Schluessel ``<Land>:bestand``, s.
    ``_country_store``) ist ausgenommen: er ist kein Transport-Cache, sondern
    die Datenschicht, und verfaellt nach Gueltigkeit/Ueberholung statt nach
    Slot (s. ``_merge_into_store``). Genau diese Trennung ist der Kern von S1 --
    die geholten SEITEN duerfen beim Slot-Wechsel weg, die gesehenen
    WARNUNGEN nicht.

    Bekannte Grenze (dokumentiert, NICHT behoben): laeuft ein 429-Rueckzug
    gerade, wenn der Slot wechselt, geht er mit dem alten Cache-Schluessel
    verloren -- die erste Seite des neuen Slots wird sofort neu versucht,
    statt den Rueckzug abzuwarten. Direkte Folge der Slot-Schluessel und
    durch die S1b-Wiederholungslogik abgefedert (Adversary-Review #1397)."""
    prefix = f"{country}:"
    keep_prefix = f"{country}:{current_slot}:"
    stale = [
        key for key in _index_cache
        if key.startswith(prefix)
        and not key.startswith(keep_prefix)
        and not key.endswith(_STORE_KEY_SUFFIX)
    ]
    for key in stale:
        del _index_cache[key]


def _index_cache_entries_for(country: str, page: int) -> list[dict]:
    """Test-Hilfsfunktion: findet Cache-Eintraege einer Seite UNABHAENGIG vom
    aktuellen Zeitslot (der Cache-Schluessel enthaelt den Slot, s.
    ``_current_slot_end``/``_slot_key`` -- Tests kennen ihn nicht im Voraus)."""
    suffix = f":p{page}"
    prefix = f"{country}:"
    return [v for k, v in _index_cache.items() if k.startswith(prefix) and k.endswith(suffix)]


# awareness_type (führende Ganzzahl) -> App-hazard. 4 (fog), 7 (coastal-event),
# 9 (avalanche), 11 (flood): keine App-Kategorie, bewusst NICHT gemappt ->
# wird uebersprungen (analog unbekannter warntypid bei GeoSphere, kein Crash).
_TYPE_HAZARD_MAP: dict[int, str] = {
    1: "wind_gust",
    2: "snow",
    3: "thunderstorm",
    5: "extreme_heat",
    6: "extreme_cold",
    8: "wildfire_risk",
    10: "rain",
    12: "rain",
}

# Modul-Level-Caches: Index pro Land, geometry-/CAP-Inhalte pro URL.
_index_cache: dict[str, dict] = {}
_geometry_cache: dict[str, dict] = {}
_cap_cache: dict[str, dict] = {}

_warned_missing_key = False


def _warn_once_missing_key() -> None:
    global _warned_missing_key
    if not _warned_missing_key:
        logger.warning(
            "GZ_METEOALARM_APIKEY nicht gesetzt — MeteoAlarm-Warnungen "
            "werden übersprungen (fail-soft)."
        )
        _warned_missing_key = True


def _local_tag(elem: ET.Element) -> str:
    tag = elem.tag
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _child_text(elem: ET.Element, name: str) -> Optional[str]:
    for child in elem:
        if _local_tag(child) == name:
            text = (child.text or "").strip()
            return text or None
    return None


def _find_parameter(info_elem: ET.Element, value_name: str) -> Optional[str]:
    for child in info_elem:
        if _local_tag(child) != "parameter":
            continue
        if _child_text(child, "valueName") == value_name:
            return _child_text(child, "value")
    return None


def _find_area_desc(info_elem: ET.Element) -> Optional[str]:
    for child in info_elem:
        if _local_tag(child) == "area":
            return _child_text(child, "areaDesc")
    return None


def _leading_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    match = re.match(r"\s*(\d+)", raw)
    return int(match.group(1)) if match else None


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _pick_preferred_entry(entries: list[dict]) -> dict:
    """Bevorzugt ``xml:lang="de*"``, Fallback ``en*``, sonst der erste Eintrag."""
    for entry in entries:
        if entry["lang"].lower().startswith("de"):
            return entry
    for entry in entries:
        if entry["lang"].lower().startswith("en"):
            return entry
    return entries[0]


def _extract_alerts_from_cap(cap_source: "str | bytes") -> list[OfficialAlert]:
    """Wandelt eine CAP-XML-Antwort in eine Liste von ``OfficialAlert`` um.

    Gruppiert die ``<info>``-Sprachvarianten (identische ``awareness_type``/
    ``awareness_level``/``onset``/``expires``/``areaDesc``) zu je EINER
    Warnung, wählt daraus den bevorzugten Sprachblock für den Text. Kaputtes
    XML oder unbekannte/gefilterte Warnungen führen NIE zu einem Crash der
    gesamten Antwort — betroffene Warnungen werden übersprungen.
    """
    text = cap_source.decode("utf-8", errors="replace") if isinstance(cap_source, bytes) else cap_source
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for info in root:
        if _local_tag(info) != "info":
            continue
        try:
            lang = _child_text(info, "language") or ""
            event = _child_text(info, "event")
            headline = _child_text(info, "headline")
            onset = _child_text(info, "onset")
            expires = _child_text(info, "expires")
            area_desc = _find_area_desc(info)
            level_raw = _find_parameter(info, "awareness_level")
            type_raw = _find_parameter(info, "awareness_type")
        except Exception:
            continue
        if not level_raw or not type_raw:
            continue
        key = (type_raw, level_raw, onset, expires, area_desc)
        entry = {"lang": lang, "event": event, "headline": headline}
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(entry)

    alerts: list[OfficialAlert] = []
    for key in order:
        type_raw, level_raw, onset, expires, area_desc = key
        try:
            level = _leading_int(level_raw)
            if level is None or level < 2:
                continue
            hazard = _TYPE_HAZARD_MAP.get(_leading_int(type_raw))
            if hazard is None:
                continue
            preferred = _pick_preferred_entry(groups[key])
            label = preferred.get("event") or preferred.get("headline") or hazard
            alerts.append(
                OfficialAlert(
                    source="meteoalarm",
                    hazard=hazard,
                    level=level,
                    label=label,
                    valid_from=_parse_iso(onset),
                    valid_to=_parse_iso(expires),
                    region_label=area_desc,
                )
            )
        except Exception:
            logger.warning("MeteoAlarm-CAP-Mapping fehlgeschlagen", exc_info=True)
            continue
    return alerts


def _get_cached_index(country: str) -> Optional[dict]:
    """Liefert den KUMULIERTEN Länder-Bestand (Issue #1397 S1), aufgefrischt
    durch einen schrittweise ueber MEHRERE Aufrufe hinweg vervollstaendigten
    Zyklus (S1c). Das Fensterende wird auf einen festen ``_SLOT_MINUTES``-
    Rasterpunkt gerundet, der Start kommt aus ``_index_query_window()``
    (Abstand zur letzten vollstaendigen Auffrischung + Ueberlappung, beim
    Kaltstart breit) -- Seiten aus verschiedenen Aufrufen INNERHALB desselben
    Slots teilen den Cache-Schluessel ``f"{country}:{slot}:p{n}"`` und setzen
    sich zusammen. Der Schluessel enthaelt bewusst NUR den Slot, nicht die
    Fensterbreite: aendert sich die Breite innerhalb eines Slots (erster
    Zyklus Kaltstart-breit, danach schmal), sind die gecachten Seiten eine
    Obermenge des schmaleren Fensters -- brauchbar, kein erneuter Abruf.

    Zurueckgegeben wird IMMER der gesamte Bestand (s. ``_merge_into_store``),
    nicht nur das frisch geholte Fenster -- genau darin liegt die von der
    Fensterbreite entkoppelte Rueckschau.

    ``None`` NUR, wenn schon Seite 1 fehlschlaegt oder ``total_pages`` nicht
    beurteilbar ist (kein einziges verwertbares Feature vorhanden). Ab dann
    gilt: ein erschoepftes Zeitbudget (``_PAGE_FETCH_BUDGET_SECONDS``) ODER
    eine echt fehlgeschlagene Folgeseite liefern die BEREITS geholten
    Features zurueck UND markieren den Aufruf ueber
    ``warn_egress.mark_fetch_incomplete()`` als real fehlgeschlagen, damit
    ``unavailable=True`` bleibt (Issue #1397 Prinzip bleibt gewahrt: verboten
    ist das STILLE Teilergebnis, nicht das gekennzeichnete -- ein
    Kompletter-Ausfall-durch-Zeitbudget waere an Tagen mit vielen Warnungen
    IMMER faellig, gerade wenn sie am wichtigsten sind)."""
    now_dt = datetime.now(timezone.utc)
    slot_end = _current_slot_end(now_dt)
    slot = _slot_key(slot_end)
    window_start, window_end, lookback_gekappt = _index_query_window(country, slot_end)
    start = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    _prune_stale_slot_entries(country, slot)

    # Issue #1397 S1b: haelt den x-ratelimit-reset der zuletzt empfangenen
    # echten Antwort fest (Cache-Hits loesen ``on_response`` NICHT aus) --
    # steuert die vorbeugende Pause vor dem naechsten Seiten-Abruf.
    last_reset_ts: list[Optional[float]] = [None]
    # Ob der ZULETZT ausgefuehrte Fetch ein echter Netzwerk-Call war (True)
    # oder ein Cache-Treffer (False, ``on_response`` wird dann nicht
    # aufgerufen) -- nur nach einem echten Call lohnt die Entzerr-Pause vor
    # der naechsten Seite (S1c: schrittweises Nachladen liest oft laengst
    # gecachte Seiten erneut, dafuer NIE warten).
    was_real_call = [False]

    def _capture_reset(resp: httpx.Response) -> None:
        last_reset_ts[0] = warn_egress.parse_ratelimit_reset(resp.headers)
        was_real_call[0] = True
        # Adversary-Fund (Runde 2, 2026-07-27): sobald ein Tageskontingent-
        # 429 real beobachtet wird, den ECHTEN Reset-Zeitpunkt persistieren
        # -- das ist die einzige verlaessliche Information ueber die
        # Gegenseite (unser eigener Zaehlerstand ist nur eine Schaetzung,
        # s. meteoalarm_budget.py). "now" kommt bewusst aus _WALL_CLOCK_FN(),
        # nicht aus der echten Wanduhr, damit Tests mit einer Fake-Uhr
        # konsistent bleiben (dieselbe Zeitbasis wie reset_ts).
        if resp.status_code == 429 and _rate_limit_retry_policy().is_long_lived(resp.headers):
            reset_ts = last_reset_ts[0]
            if reset_ts is not None:
                observed_now = datetime.fromtimestamp(_WALL_CLOCK_FN(), tz=timezone.utc)
                _meteoalarm_budget_gate().record_observed_reset(reset_ts, now=observed_now)

    def _fetch_page(page: int) -> Optional[dict]:
        # Die EINE Stelle, durch die jeder Index-Abruf laeuft (Tagesbudget-Gate,
        # Typpruefung der Antwort, 429-Wiederholung, Egress-Zeile) -- ein
        # zweiter, eigener Abrufpfad waere ein zweiter, ungehaerteter Pfad.
        def _do_request() -> httpx.Response:
            # Tageskontingent-Fund (S1c-Nachbesserung): VOR jedem echten
            # Netzwerk-Call pruefen, ob unser eigenes Tagesbudget noch Luft
            # hat -- erschoepft heisst KEIN Abruf mehr, nicht erst nach dem
            # naechsten 429. Faellt-offen (MeteoAlarmBudgetGate.allow()):
            # ein kaputter Zaehler blockiert nie.
            gate = _meteoalarm_budget_gate()
            if not gate.allow():
                raise _MeteoAlarmBudgetExhausted(
                    f"MeteoAlarm-Tagesbudget erschoepft ({gate.daily_budget}/Tag) "
                    f"-- Abruf {country} Seite {page} uebersprungen"
                )
            gate.record_call()
            key = os.environ.get("GZ_METEOALARM_APIKEY")
            url = f"{METEOALARM_BASE_URL}/collections/warnings/locations/{country}"
            return httpx.get(
                url,
                params={"datetime": f"{start}/{end}", "page": page},
                headers={"Authorization": f"Bearer {key}"},
                timeout=TIMEOUT,
            )

        def _parse(resp: httpx.Response) -> dict:
            # 204/leerer Body ist der reguläre "keine Warnung"-Fall (z.B. Italien bei
            # gutem Wetter), kein Fehler -- als leeres, gültiges Ergebnis behandeln.
            if resp.status_code == 204 or not resp.content.strip():
                return {"features": []}
            data = resp.json()
            if not isinstance(data, dict):
                # Adversary F002 Runde 3: die GESAMTE Seiten-Antwort kann
                # falsch typisiert sein (z.B. JSON-Liste/Zahl statt Objekt),
                # nicht nur ein Unterwert. Das hier -- die EINE Stelle, durch
                # die jede Seite (erste UND Folgeseiten) laeuft -- ist der
                # richtige Ort dafuer, statt an jeder Zugriffsstelle
                # (first.get(...), page.get(...), metadata.get(...)) einen
                # eigenen isinstance-Flicken zu setzen. warn_egress.
                # cached_fetch() faengt eine hier geworfene Exception als
                # Parse-Fehler ab (Rueckgabe None, Failure-Marker) -- damit
                # gilt exakt derselbe Ausfall-Pfad wie fuer jeden anderen
                # kaputten Seiten-Abruf.
                raise ValueError(f"Index-Antwort ist kein Objekt (type={type(data).__name__})")
            return data

        return warn_egress.cached_fetch(
            cache=_index_cache, cache_key=f"{country}:{slot}:p{page}",
            # Tageskontingent-Fund Punkt 3: Land+Seite muessen im Egress-
            # Zaehler unterscheidbar sein (nicht nur "meteoalarm" pauschal),
            # sonst laesst sich morgen aus warn_service_calls.jsonl nicht
            # ablesen, bei welcher Seite das Tageslimit zuschlug. Nur die
            # Index-Seiten-Abrufe bekommen dieses feinere Label -- Geometrie-/
            # CAP-Nachladen bleibt bei "meteoalarm" (nicht Teil des Funds).
            service=f"meteoalarm:{country}:p{page}",
            host="api.meteoalarm.org", request_fn=_do_request, parse_fn=_parse,
            log=logger,
            success_ttl=INDEX_PAGE_SUCCESS_TTL,
            # Issue #1397 S1b: Index-Seiten duerfen bei 429 wiederholen statt
            # sofort als Ausfall zu gelten (Kurzzeit-Ratenbremse, s. Konstanten
            # oben) -- ausschliesslich hier eingeschaltet, alle vier anderen
            # Warn-Dienste rufen cached_fetch() weiterhin ohne dieses Argument.
            rate_limit_retry=_rate_limit_retry_policy(),
            on_response=_capture_reset,
        )

    first = _fetch_page(1)
    if first is None:
        return None
    features = list(first.get("features") or [])
    total_pages = _resolve_total_pages(first.get("metadata"))
    if total_pages is None:
        # Adversary F001/F002: weder still auf _MAX_INDEX_PAGES kappen (das
        # WAERE genau der Bug, den #1397 behebt) noch bei kaputtem
        # total_pages werfen (reisst sonst die AT/IT-Fail-soft-Schleife in
        # fetch() ab) -- beides ist ein nicht beurteilbarer/unvollstaendiger
        # Index und damit ein Ausfall. Anders als eine fehlgeschlagene
        # FOLGESEITE (s.u.) gibt es hier NICHTS Verwertbares zurueckzugeben.
        #
        # Adversary F001 (S1c-Runde): Seite 1 selbst kam HTTP-sauber und als
        # valides JSON-Objekt durch -- fuer cached_fetch() war das ein
        # ERFOLG, es hat NICHTS markiert. Erst HIER, eine Ebene hoeher,
        # entscheidet sich anhand von total_pages, dass der Index trotzdem
        # unbrauchbar ist. Ohne den expliziten Marker waere das ein
        # kompletter, aber STILLER Ausfall -> unavailable=False, obwohl
        # gar keine Warnung ankam (genau die Fehlerart, gegen die #1397 laeuft).
        warn_egress.mark_fetch_incomplete()
        return None

    call_start = _WALL_CLOCK_FN()
    incomplete = False
    for page_num in range(2, total_pages + 1):
        # Zeitbudget VOR jedem weiteren Abruf pruefen (Issue #1397 S1c) --
        # nicht erst nach einem Fehlschlag, sonst koennte ein einzelner
        # Aufruf beliebig lange blaettern, solange jede Seite gelingt.
        if _WALL_CLOCK_FN() - call_start >= _PAGE_FETCH_BUDGET_SECONDS:
            incomplete = True
            break
        # Vorbeugender Abstand VOR dem Abruf (Issue #1397 S1b) -- nur nach
        # einem echten Netzwerk-Call der Vorseite (s. was_real_call oben),
        # nicht vor einem laengst gecachten Folgeaufruf im selben Slot.
        if was_real_call[0]:
            _throttle_before_next_page(last_reset_ts[0])
        was_real_call[0] = False
        page = _fetch_page(page_num)
        if page is None:
            # Echt fehlgeschlagene Seite (429 nach allen Versuchen, HTTP>=400,
            # Netz-/Parse-Fehler): cached_fetch() hat den Fehlschlag intern
            # bereits ueber observe_fetch_failure() markiert -- bricht HIER
            # trotzdem ab (kein sinnloses Weiterblaettern ueber eine Luecke
            # hinweg) und gibt die bereits geholten Seiten zurueck.
            incomplete = True
            break
        features.extend(page.get("features") or [])

    if incomplete or lookback_gekappt:
        # Zeitbudget-Abbruch macht (anders als eine fehlgeschlagene Seite)
        # KEINEN internen cached_fetch()-Fehlschlag -- ohne diesen expliziten
        # Marker wuerde unavailable=True hier stillschweigend verloren gehen.
        # Dasselbe gilt fuer eine gekappte Rueckschau (Adversary F001,
        # Fix-Loop 1): der Zyklus hat sauber alles geholt, was er GEFRAGT hat,
        # aber weniger gefragt, als sein Rueckstand verlangt haette -- ein
        # Stueck Vergangenheit bleibt ungeprueft. Das Briefing muss dafuer
        # "nicht abrufbar" sagen, nie "keine Warnung".
        warn_egress.mark_fetch_incomplete()
    if not incomplete:
        # Fortschrittsmarke NUR nach einem vollstaendig geholten Zyklus
        # (Issue #1397 S1): nach einem Teil-Zyklus bleibt das naechste Fenster
        # bewusst breit bzw. der Kaltstart offen -- sonst wuerde die Luecke,
        # die der Abbruch hinterlassen hat, dauerhaft unsichtbar bleiben.
        # Eine GEKAPPTE Rueckschau zaehlt hier bewusst als vollstaendig: das
        # gekappte Fenster wurde luecklos geholt, und wuerde die Marke stehen
        # bleiben, fragte jeder Folgezyklus dasselbe gekappte Fenster erneut
        # ab und meldete dauerhaft "nicht abrufbar" -- eine Sackgasse, die
        # nichts zurueckholt (aelter als die Obergrenze faellt ohnehin aus dem
        # Bestand, s. _STORE_RETENTION_HOURS). So bleibt es bei genau EINEM
        # als unvollstaendig gekennzeichneten Zyklus, danach faengt sich der
        # Dienst von selbst.
        _country_store(country)["last_complete"] = slot_end
    _merge_into_store(country, features, _WALL_CLOCK_FN())
    return {"features": [e["feature"] for e in _country_store(country)["features"].values()]}


def _resolve_total_pages(metadata: Optional[dict]) -> Optional[int]:
    """Ermittelt die Gesamtseitenzahl aus der Metadata der ersten Seite.

    Fehlt ``metadata`` ganz ODER fehlt ``total_pages`` darin (z.B. 204/leerer
    Body) -> genau 1 Seite, KEIN Ausfall (Bestandsverhalten). Ist
    ``total_pages`` gesetzt, aber nicht als positive Ganzzahl lesbar, ODER
    ist ``metadata`` selbst vom falschen Typ (Adversary F002 Runde 2 -- z.B.
    ein String statt eines Objekts, ``metadata.get()`` wuerde sonst mit
    ``AttributeError`` werfen), ODER meldet die API mehr Seiten als
    ``_MAX_INDEX_PAGES`` -> die Vollstaendigkeit ist nicht sicherzustellen ->
    ``None`` (Ausfall, Issue #1397 Adversary F001/F002: NIE still kappen und
    mit einem Teil-Ergebnis weitermachen, NIE werfen).

    Die Typvalidierung der GESAMTEN Seiten-Antwort (Adversary F002 Runde 3:
    z.B. eine JSON-Liste statt eines Objekts) passiert eine Ebene hoeher in
    ``_parse()`` innerhalb von ``_get_cached_index()`` -- der ``isinstance``-
    Schutz hier bleibt TROTZDEM bestehen, damit diese Funktion auch direkt
    (ohne den Aufrufkontext) fuer sich robust und einzeln testbar ist."""
    if not metadata:
        return 1
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("total_pages")
    if raw is None:
        return 1
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 1 or value > _MAX_INDEX_PAGES:
        return None
    return value


def _feature_dedup_key(feature: dict) -> tuple:
    props = feature.get("properties") or {}
    return (props.get("alertId"), props.get("indexArea"), props.get("indexInfo"))


def _is_superseded(feature: dict) -> bool:
    """True, wenn dieses Feature durch eine neuere Fassung ersetzt wurde
    (Issue #1397: ~98 % aller Features im urspruenglichen 23h-Publikations-
    fenster waren überholt -- Grund fuer die S1c-Nachbesserung, das
    Standardfenster auf ``DEFAULT_INDEX_WINDOW_HOURS`` zu verkuerzen. Der
    Filter bleibt UNABHAENGIG von der Fensterlaenge noetig -- muss VOR jedem
    Nachlade-Abruf geprüft werden, sonst erscheint dieselbe Warnung mit
    leicht verschobenen Zeiträumen mehrfach)."""
    props = feature.get("properties") or {}
    return bool(props.get("supersededAt") or props.get("supersededByAlertId"))


def _bbox_may_contain(lat: float, lon: float, geometry: Optional[dict]) -> bool:
    """Garantierte OBERMENGE (Issue #1397, KEIN Ray-Casting): min/max der
    Ring-Koordinaten der Index-bbox mit ~0,01°-Marge. Bewusst NICHT
    ``_point_in_geometry()`` -- dessen striktes Ray-Casting schließt
    Kantenpunkte aus und würde denselben stillen Warn-Verlust an der
    bbox-Kante neu erzeugen. Fehlende/unparsbare Geometrie -> True
    (fail-open, Fläche wird sicherheitshalber nachgeladen)."""
    if not geometry:
        return True
    try:
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if gtype == "Polygon":
            rings = coords
        elif gtype == "MultiPolygon":
            rings = [ring for poly in coords for ring in poly]
        else:
            return True
        points = [pt for ring in rings for pt in ring]
        lons = [p[0] for p in points]
        lats = [p[1] for p in points]
        return (min(lons) - _BBOX_MARGIN_DEG <= lon <= max(lons) + _BBOX_MARGIN_DEG
                and min(lats) - _BBOX_MARGIN_DEG <= lat <= max(lats) + _BBOX_MARGIN_DEG)
    except Exception:
        return True


def _fetch_geometry_link(feature: dict) -> Optional[dict]:
    """Lädt die exakte Fläche (``rel="geometry"``-Link), gecacht auf
    ``countryCode:OBJECTID`` (Issue #1397 -- statt der presigned URL, deren
    Signatur pro Index-Antwort rotiert und den Cache sonst nie über eine
    Index-Erneuerung hinaus greifen ließ). Länderpräfix (Adversary F004):
    dass ``OBJECTID`` laenderuebergreifend eindeutig ist, ist eine unbelegte
    Annahme -- der Praefix macht sie ueberfluessig. Fläche ist pro OBJECTID
    unveränderlich -> lange Erfolgs-TTL (``GEOMETRY_CAP_TTL``)."""
    href = next(
        (link.get("href") for link in feature.get("links") or [] if link.get("rel") == "geometry"),
        None,
    )
    if not href:
        return None
    props = feature.get("properties") or {}
    object_id = props.get("OBJECTID")
    # Bekannte Grenze (F004-Rand, PO-akzeptiert): fehlt countryCode, wird der
    # Schluessel "None:<OBJECTID>" -- kein eigener Fix, da OBJECTID laut API-
    # Vertrag ohnehin nur zusammen mit countryCode auftritt.
    cache_key = f"{props.get('countryCode')}:{object_id}" if object_id else href
    return warn_egress.cached_fetch(
        cache=_geometry_cache, cache_key=cache_key, service="meteoalarm",
        host="meteo.fra1.digitaloceanspaces.com",
        request_fn=lambda: httpx.get(href, timeout=TIMEOUT),
        parse_fn=lambda resp: resp.json().get("geometry"),
        success_ttl=GEOMETRY_CAP_TTL,
        log=logger,
    )


def _fetch_cap(url: str, alert_id: Optional[str], country_code: Optional[str] = None) -> Optional[str]:
    """Lädt die CAP-XML (auth-frei), gecacht auf ``countryCode:alertId``
    (Issue #1397 -- statt der presigned URL, s. ``_fetch_geometry_link``;
    Länderpräfix analog Adversary F004). CAP-Inhalt ist pro ``alertId``
    unveränderlich -> lange Erfolgs-TTL."""
    # Bekannte Grenze analog _fetch_geometry_link (F004-Rand, kein Fix).
    cache_key = f"{country_code}:{alert_id}" if alert_id else url
    return warn_egress.cached_fetch(
        cache=_cap_cache, cache_key=cache_key, service="meteoalarm",
        host="meteo.fra1.digitaloceanspaces.com",
        request_fn=lambda: httpx.get(url, timeout=TIMEOUT),
        parse_fn=lambda resp: resp.text,
        success_ttl=GEOMETRY_CAP_TTL,
        log=logger,
    )


def _point_in_ring(lat: float, lon: float, ring: list) -> bool:
    """Ray-Casting gegen einen einzelnen GeoJSON-Ring ([lon, lat]-Paare)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at_lat:
                inside = not inside
        j = i
    return inside


def _point_in_polygon_coords(lat: float, lon: float, coords: list) -> bool:
    if not coords:
        return False
    if not _point_in_ring(lat, lon, coords[0]):
        return False
    return not any(_point_in_ring(lat, lon, hole) for hole in coords[1:])


def _point_in_geometry(lat: float, lon: float, geometry: dict) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return _point_in_polygon_coords(lat, lon, coords)
    if gtype == "MultiPolygon":
        return any(_point_in_polygon_coords(lat, lon, poly) for poly in coords or [])
    return False


class MeteoAlarmSource:
    """MeteoAlarm-Quelle (AT + IT) für die Official-Alerts-Registry (#1086)."""

    @property
    def name(self) -> str:
        return "meteoalarm"

    def covers(self, lat: float, lon: float) -> bool:
        """AT- (INCA-Bbox) ∪ IT-Bbox (DPC) Vorfilter (kein API-Call).

        Issue #1397 S2b: die INCA-Bbox reicht rund 100 km in die Provence
        hinein (Westkante bei lon 9,5 -- Fréjus/Saint-Tropez liegen bei
        lon ~6,6-6,7). Ein einzelner franzoesischer Ort in der Vergleichs-
        matrix wuerde sonst den `unavailable`-Hinweis fuer den gesamten
        Ortsvergleich kippen. Punkte in einem franzoesischen Département
        (`lookup_department()` liefert einen Code statt `None`) werden
        deshalb ausgenommen. Verlaesslich erst seit Issue #1400: davor
        lieferte `lookup_department()` fuer JEDEN Punkt der Erde einen
        Code (Zentroid-Notbehelf ohne Bedingung) -- diese Pruefung haette
        also JEDEN Punkt als Frankreich eingestuft und MeteoAlarm komplett
        abgeschaltet.

        Bekannte Grenze (dokumentiert, NICHT behoben, #1397): Punkte in
        Bayern, Slowenien, der Schweiz oder Ungarn gelten weiterhin als
        abgedeckt -- die INCA-Bbox ist ein reines Grobgatter fuer
        Oesterreich, kein Staatsgrenzen-Polygon. Der exakte Punkt-in-
        Flaeche-Filter laeuft ohnehin erst nach dem Abruf (s. `fetch()`);
        Grenzunschaerfe dort kostet hoechstens einen ueberfluessigen Abruf,
        nie eine verlorene Warnung.
        """
        in_at = _INCA_LAT_MIN <= lat <= _INCA_LAT_MAX and _INCA_LON_MIN <= lon <= _INCA_LON_MAX
        in_it = _DPC_LAT_MIN <= lat <= _DPC_LAT_MAX and _DPC_LON_MIN <= lon <= _DPC_LON_MAX
        if not (in_at or in_it):
            return False
        return lookup_department(lat, lon) is None

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        if not os.environ.get("GZ_METEOALARM_APIKEY"):
            _warn_once_missing_key()
            return []

        alerts: list[OfficialAlert] = []
        for country in ("AT", "IT"):
            index = _get_cached_index(country)
            if index is None:
                continue
            seen_keys: set[tuple] = set()
            for feature in index.get("features") or []:
                try:
                    # Issue #1397: überholte Fassungen VOR jedem Nachlade-Abruf
                    # überspringen (Messgrundlage: 98 % im urspruenglichen
                    # 23h-Fenster -- der Filter bleibt bei jeder Fensterlaenge noetig).
                    if _is_superseded(feature):
                        continue
                    key = _feature_dedup_key(feature)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    # bbox-Obermenge zuerst (kein API-Call) -- spart den
                    # Flächen-Nachlade-Abruf für Features, die den Punkt
                    # garantiert nicht abdecken.
                    if not _bbox_may_contain(lat, lon, feature.get("geometry")):
                        continue
                    geometry = _fetch_geometry_link(feature)
                    if geometry is None or not _point_in_geometry(lat, lon, geometry):
                        continue
                    props = feature["properties"]
                    cap_text = _fetch_cap(props["hubLink"], props.get("alertId"), props.get("countryCode"))
                    if cap_text is None:
                        continue
                    cap_alerts = _extract_alerts_from_cap(cap_text)
                    # Adversary F004 (Fix-Loop 2): hier -- und nur hier -- ist
                    # die Gueltigkeit der Warnung bekannt. Am Bestands-Eintrag
                    # vermerken, damit seine Aufbewahrung an ihrem Ablauf haengt
                    # und nicht daran, wann wir sie zuletzt im Index sahen.
                    _remember_validity(country, feature, cap_alerts)
                    alerts.extend(cap_alerts)
                except Exception:
                    logger.warning(
                        "MeteoAlarm-Feature-Verarbeitung fehlgeschlagen", exc_info=True
                    )
                    continue
        return alerts
