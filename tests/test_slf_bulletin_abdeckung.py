"""SLF-Lagebericht: Zustaende, Zustaendigkeit, Abruf, Egress, Registry (#1441 S3, AC-8 bis AC-17).

SPEC: docs/specs/modules/feat_1441_s3_slf.md -- AC-8 .. AC-17, Implementation Details 2-4, 8, 9
HELPER: tests/helpers/slf_support.py (Fixtures: tests/fixtures/slf/, README dort)

Kein Mock-Theater: die ECHTE ``SlfSource`` bekommt den ``SlfFixtureTransport`` (echter
``httpx.BaseTransport`` mit aufgezeichneten SLF-Antworten, zaehlt jeden Zugriff) und eine
``FakeClock`` fuer Cache-TTL und Gueltigkeit. Abgefragt wird ueber den echten Registry-Pfad
``get_official_alerts_with_status``; ``monkeypatch`` nur fuer die Registry (Helper).

Vakuum-Schutz: jede "kein Abruf / leer / kein Hinweis"-Aussage steht neben einer positiven
Vorbedingung (Abruf fand statt, Region liefert sonst DIE Warnung, ``slf_bulletin`` ist registriert),
die ohne SLF-Quelle scheitert.

Pruefling-Importe (``services.official_alerts.slf``) stehen ausschliesslich in den Tests bzw. im
Helper -- ein fehlendes Modul macht den einzelnen Test rot, nicht das Sammeln.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.helpers.slf_support import (
    ABEND_FOLGETAG_FRUEH,
    DEZEMBER,
    FEBRUAR,
    FEHLERARTEN,
    LEER,
    MORGEN_UPDATE,
    P_AOSTA,
    P_BREGENZ,
    P_FELDBERG,
    P_INNSBRUCK,
    P_TIROL_AT_07_05,
    P_ZUERICH,
    SLF_API_HOST,
    SLF_API_PATH,
    SLF_REGISTRY_NAME,
    WINTER_MORGEN,
    FakeClock,
    SlfFixtureTransport,
    alerts_with_status,
    call_log,
    ch_regions_at,
    http_503,
    interior_point,
    make_slf_source,
    only_slf,
    only_source,
    region_ids_in,
    registered_names,
    registry_replacing,
    registry_without,
    slf_doc,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[1]
SLF_MODULE = REPO_ROOT / "src" / "services" / "official_alerts" / "slf.py"

WINTER_NOW = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)           # Morgen-Ausgabe 07:00Z-16:00Z gilt
AUSSER_SAISON = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)      # Aufzeichnungstag von leer.json

P_GRAUBUENDEN = interior_point("CH-5123")      # Davos
P_WALLIS = interior_point("CH-4222")           # Zermatt
P_BERNER_OBERLAND = interior_point("CH-1243")  # Grindelwald
P_MUENSTERTAL = interior_point("CH-7231")
P_MITTELLAND_CH_9211 = interior_point("CH-9211")


# ------------------------------------------------------------------ lokale Hilfen
def _quelle(reply, now: datetime):
    transport = SlfFixtureTransport(reply)
    clock = FakeClock(now)
    return transport, clock, make_slf_source(transport, clock)


def _slf_alerts(alerts: list) -> list:
    return [a for a in alerts if str(a.source).split(":", 1)[0] == SLF_REGISTRY_NAME]


def _slf_journal_rows() -> list[dict]:
    """Zeilen des Warn-Dienst-Journals (#1422) fuer den SLF-Host -- unabhaengig vom Dienstnamen."""
    return [r for r in call_log() if r.get("host") == SLF_API_HOST]


def _mit_quellen_journal(lat: float, lon: float, now: datetime):
    """Registry-Abruf mit Status UND Pro-Quelle-Ergebnis (``collect_source_queries``)."""
    from services.official_alerts.base import collect_source_queries

    sink: list = []
    with collect_source_queries(sink):
        alerts, unavailable = alerts_with_status(lat, lon, now)
    assert sink, "Voraussetzung: der Registry-Abruf hat sein Pro-Quelle-Ergebnis abgelegt"
    return alerts, unavailable, sink[-1].sources


def _assert_abruf_ohne_active_at(transport: SlfFixtureTransport) -> None:
    assert transport.calls, "Voraussetzung: es fand ein Abruf statt"
    for url in transport.calls:
        parsed = httpx.URL(url)
        assert parsed.host == SLF_API_HOST and parsed.path == SLF_API_PATH, url
        assert "activeAt" not in parsed.params, f"Abruf darf kein activeAt senden: {url}"
        assert "activeat" not in url.lower(), f"Abruf darf kein activeAt senden: {url}"


# ================================================================== AC-8: Gueltigkeit
def test_ac8_abend_ausgabe_gilt_am_folgetag_um_06_uhr_und_liefert_die_warnung(monkeypatch):
    """AC-8 Given die Abend-Ausgabe (gueltig 03-01 16:00Z bis 03-02 16:00Z) / When um 03-02 06:00Z
    abgerufen wird / Then gilt sie: genau eine Warnung fuer CH-7231 mit Ende 16:00Z."""
    now = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)
    transport, clock, source = _quelle(ABEND_FOLGETAG_FRUEH, now)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_MUENSTERTAL, now)

    slf = _slf_alerts(alerts)
    assert [(a.source, a.native_level) for a in slf] == [("slf_bulletin:CH-7231", 3)]
    assert slf[0].valid_from == datetime(2026, 3, 1, 16, 0, tzinfo=UTC)
    assert slf[0].valid_to == datetime(2026, 3, 2, 16, 0, tzinfo=UTC)
    assert unavailable is False
    assert transport.count == 1


def test_ac8_dieselbe_abend_ausgabe_um_17_uhr_ist_leer_ohne_ausfallhinweis(monkeypatch):
    """AC-8 Given dieselbe (nun abgelaufene) Antwort / When um 03-02 17:00Z abgerufen wird / Then
    ist das Ergebnis leer, ``unavailable=False`` -- und die Quelle selbst filtert (nicht erst das
    Zeitfenster der Registry)."""
    now = datetime(2026, 3, 2, 17, 0, tzinfo=UTC)
    transport, clock, source = _quelle(ABEND_FOLGETAG_FRUEH, now)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_MUENSTERTAL, now)

    assert _slf_alerts(alerts) == []
    assert unavailable is False, "abgelaufenes Bulletin ist kein Ausfall"
    assert transport.count == 1, "Voraussetzung: die Antwort wurde wirklich geliefert"
    assert source.fetch(*P_MUENSTERTAL) == [], "die Quelle selbst muss das Ablaufdatum pruefen"


def test_ac8_gueltigkeitsgrenze_16_uhr_gilt_noch_eine_sekunde_danach_nicht_mehr():
    """AC-8 Given die Abend-Ausgabe / When genau um 16:00:00Z bzw. 16:00:01Z abgerufen wird / Then
    gilt sie an der Grenze noch (``endTime >= now``) und eine Sekunde spaeter nicht mehr."""
    ende = datetime(2026, 3, 2, 16, 0, tzinfo=UTC)
    _t, _c, vorher = _quelle(ABEND_FOLGETAG_FRUEH, ende)
    _t, _c, nachher = _quelle(ABEND_FOLGETAG_FRUEH, ende + timedelta(seconds=1))

    assert len(vorher.fetch(*P_MUENSTERTAL)) == 1
    assert nachher.fetch(*P_MUENSTERTAL) == []


def test_ac8_morgen_update_um_08_uhr_traegt_seine_eigene_gueltigkeit(monkeypatch):
    """AC-8 Given das Morgen-Update 03-02 / When um 08:00Z abgerufen wird / Then liefert es die
    Warnung mit seiner eigenen Gueltigkeit 07:00Z-16:00Z (nicht die der Abend-Ausgabe)."""
    now = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)
    transport, clock, source = _quelle(MORGEN_UPDATE, now)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_MUENSTERTAL, now)

    slf = _slf_alerts(alerts)
    assert len(slf) == 1 and slf[0].native_level == 3
    assert slf[0].valid_from == datetime(2026, 3, 2, 7, 0, tzinfo=UTC)
    assert slf[0].valid_to == datetime(2026, 3, 2, 16, 0, tzinfo=UTC)
    assert unavailable is False


# ================================================================== AC-9: leere Saison
def test_ac9_leere_saison_ist_leer_ohne_ausfallhinweis_und_im_journal_erfolgreich(monkeypatch):
    """AC-9 Given ``leer.json`` (HTTP 200, ``{"bulletins":[]}``) / When ein Punkt in Graubuenden
    abgefragt wird / Then leer, ``unavailable=False``, im Warn-Dienst-Journal (#1422) eine
    erfolgreiche Antwort (200, ok) -- und das Pro-Quelle-Ergebnis der Entwarnung (S2) ist NICHT
    ``ok`` (Spec Abschnitt 10: leere Saison = "nicht zustaendig", sonst Schein-Entwarnung, AC-29b)."""
    transport = SlfFixtureTransport(LEER)
    only_slf(monkeypatch, transport, FakeClock(AUSSER_SAISON))

    alerts, unavailable, sources = _mit_quellen_journal(*P_GRAUBUENDEN, AUSSER_SAISON)

    assert alerts == []
    assert unavailable is False, "leere Saison ist kein Ausfall"
    assert transport.count == 1, "Voraussetzung: der SLF-Host wurde wirklich abgefragt"
    assert sources.get(SLF_REGISTRY_NAME) == (False, []), (
        f"leere Saison darf fuer die Entwarnung nicht als gesunde Quelle zaehlen: {sources}"
    )
    echte = [r for r in _slf_journal_rows() if r["cache_hit"] is False]
    assert len(echte) == 1 and echte[0]["ok"] is True and echte[0]["status"] == 200, echte


def test_ac9_abruf_url_hat_kein_active_at():
    """AC-9 / Spec Abschnitt 2: Given der Abruf / Then geht er an ``aws.slf.ch/api/bulletin/caaml/
    de/json`` OHNE ``activeAt`` (die API liefert dann genau die gerade gueltige Ausgabe)."""
    transport, clock, source = _quelle(LEER, AUSSER_SAISON)

    source.fetch(*P_GRAUBUENDEN)

    _assert_abruf_ohne_active_at(transport)


def test_ac9_leere_antwort_bleibt_hoechstens_1800_sekunden_im_cache():
    """AC-9 Given ``leer.json`` / When 1799 s spaeter erneut abgefragt wird / Then Cache-Treffer
    (kein zweiter Abruf); 1801 s nach dem ersten Abruf / Then neue Anfrage -- und ein inzwischen
    erschienenes Bulletin ist sofort sichtbar (nicht 24 h unsichtbar)."""
    start = datetime(2026, 3, 1, 7, 10, tzinfo=UTC)
    transport, clock, source = _quelle(LEER, start)

    assert source.fetch(*P_GRAUBUENDEN) == []
    assert transport.count == 1

    clock.advance(1799)
    assert source.fetch(*P_GRAUBUENDEN) == []
    assert transport.count == 1, "innerhalb von 1800 s kein zweiter Abruf"

    transport.set(WINTER_MORGEN)
    clock.advance(2)                          # 1801 s nach dem ersten Abruf
    neu = source.fetch(*P_GRAUBUENDEN)

    assert transport.count == 2, "die leere Antwort darf nicht laenger als 1800 s gecacht werden"
    assert [(a.source, a.native_level) for a in neu] == [("slf_bulletin:CH-5123", 3)]


# ================================================================== AC-10: Abruffehler
@pytest.mark.parametrize("art", sorted(FEHLERARTEN), ids=sorted(FEHLERARTEN))
def test_ac10_abruffehler_macht_die_quelle_nicht_abrufbar(monkeypatch, art):
    """AC-10 Given Netzfehler / HTTP 503 / kaputtes JSON / 200 ohne ``bulletins`` / When ein Punkt
    in Graubuenden abgefragt wird / Then ``unavailable=True`` (keine zweite Quelle zustaendig),
    keine Warnung, Pro-Quelle-Ergebnis nicht ``ok``."""
    transport = SlfFixtureTransport(FEHLERARTEN[art]())
    only_slf(monkeypatch, transport, FakeClock(WINTER_NOW))

    alerts, unavailable, sources = _mit_quellen_journal(*P_GRAUBUENDEN, WINTER_NOW)

    assert transport.count >= 1, "Voraussetzung: der Abruf wurde versucht"
    assert alerts == []
    assert unavailable is True, f"{art}: ein Abruffehler MUSS als 'nicht abrufbar' sichtbar werden"
    assert sources.get(SLF_REGISTRY_NAME, (None, None))[0] is False, sources


# ================================================================== AC-11: ein Abruf fuer ganz CH
def test_ac11_drei_mikroregionen_teilen_sich_genau_einen_abruf(monkeypatch):
    """AC-11 Given drei Punkte in Graubuenden, Wallis, Berner Oberland / When sie innerhalb des
    Cache-Zeitraums nacheinander abgefragt werden / Then genau ein HTTP-Abruf an ``aws.slf.ch``,
    und jeder Punkt bekommt die Warnung SEINER Mikroregion."""
    transport = SlfFixtureTransport(WINTER_MORGEN)
    clock = FakeClock(WINTER_NOW)
    only_slf(monkeypatch, transport, clock)
    erwartet = {"CH-5123": 3, "CH-4222": 2, "CH-1243": 2}     # aus at_2026-03-01T08:00:00Z.json

    ergebnis = {}
    for rid, punkt in (("CH-5123", P_GRAUBUENDEN), ("CH-4222", P_WALLIS),
                       ("CH-1243", P_BERNER_OBERLAND)):
        assert ch_regions_at(*punkt) == [rid], "Voraussetzung: Punkt liegt in genau dieser Region"
        alerts, unavailable = alerts_with_status(*punkt, clock.now())
        assert unavailable is False
        ergebnis[rid] = [(a.source, a.native_level) for a in _slf_alerts(alerts)]
        clock.advance(60)

    assert ergebnis == {rid: [(f"slf_bulletin:{rid}", lvl)] for rid, lvl in erwartet.items()}
    assert transport.count == 1, f"ganz CH = ein Abruf, gezaehlt: {transport.calls}"
    _assert_abruf_ohne_active_at(transport)


# ================================================================== AC-12: Polygon statt BBox
AUSLAND = [P_INNSBRUCK, P_BREGENZ, P_AOSTA, P_FELDBERG]
AUSLAND_IDS = ["innsbruck", "bregenz", "aosta", "feldberg"]


def test_ac12_covers_ist_nur_fuer_den_schweizer_punkt_wahr():
    """AC-12 Given Innsbruck, Bregenz, Aosta, Feldberg und ein Punkt in CH-7231 / When ``covers()``
    befragt wird / Then nur der Schweizer Punkt ist zustaendig; ``covers()`` beruehrt nie das Netz."""
    transport, clock, source = _quelle(WINTER_MORGEN, WINTER_NOW)

    assert source.name == SLF_REGISTRY_NAME
    assert source.covers(*P_MUENSTERTAL) is True
    assert {name: source.covers(*p) for name, p in zip(AUSLAND_IDS, AUSLAND)} == {
        name: False for name in AUSLAND_IDS
    }
    assert transport.calls == [], "covers() darf nie das Netz beruehren"


@pytest.mark.parametrize("punkt", AUSLAND, ids=AUSLAND_IDS)
def test_ac12_ausland_punkt_loest_keinen_abruf_und_keinen_hinweis_aus(monkeypatch, punkt):
    """AC-12 Given ein Punkt ausserhalb der Schweiz (in keiner CH-Mikroregion) / When die Registry
    befragt wird / Then kein Abruf, kein Ausfallhinweis -- Vorbedingung: derselbe Aufbau ruft fuer
    den Schweizer Punkt ab und liefert dort die Warnung."""
    assert ch_regions_at(*punkt) == [], "Voraussetzung: Punkt liegt in keiner CH-Mikroregion"
    transport = SlfFixtureTransport(WINTER_MORGEN)
    only_slf(monkeypatch, transport, FakeClock(WINTER_NOW))

    alerts, unavailable = alerts_with_status(*punkt, WINTER_NOW)

    assert alerts == [] and unavailable is False
    assert transport.count == 0, f"es darf KEIN Abruf stattfinden: {transport.calls}"
    assert _slf_journal_rows() == []

    ch_alerts, ch_unavailable = alerts_with_status(*P_MUENSTERTAL, WINTER_NOW)
    assert [a.source for a in _slf_alerts(ch_alerts)] == ["slf_bulletin:CH-7231"]
    assert ch_unavailable is False and transport.count == 1


@pytest.mark.parametrize("punkt", AUSLAND + [P_TIROL_AT_07_05],
                         ids=AUSLAND_IDS + ["tirol-at-07-05"])
def test_ac12_echte_registry_mit_slf_ruft_im_ausland_nie_aws_slf_ch_ab(monkeypatch, punkt):
    """AC-12 Given die ECHTE Standard-Registry, in der ``slf_bulletin`` steht (dort gegen eine
    Instanz mit Fixture-Transport getauscht) / When ein Auslandspunkt abgefragt wird / Then kein
    Abruf an ``aws.slf.ch`` und keine SLF-Warnung; der Schweizer Punkt ruft genau einmal ab."""
    assert SLF_REGISTRY_NAME in registered_names(), "Voraussetzung: slf_bulletin ist registriert"
    transport, clock, source = _quelle(WINTER_MORGEN, WINTER_NOW)
    registry_replacing(monkeypatch, source)

    alerts, _unavailable = alerts_with_status(*punkt, WINTER_NOW)

    assert _slf_alerts(alerts) == []
    assert transport.count == 0, f"Ausland: kein SLF-Abruf erlaubt, gezaehlt {transport.calls}"

    ch_alerts, _ = alerts_with_status(*P_MUENSTERTAL, WINTER_NOW)
    assert [a.source for a in _slf_alerts(ch_alerts)] == ["slf_bulletin:CH-7231"]
    assert transport.count == 1


# ================================================================== AC-13: Mittelland
@pytest.mark.parametrize("punkt", [P_MITTELLAND_CH_9211, P_ZUERICH],
                         ids=["ch-9211-innenpunkt", "zuerich-47.37-8.54-ch-9311"])
def test_ac13_mittelland_ist_leer_ohne_hinweis_und_nicht_zustaendig(monkeypatch, punkt):
    """AC-13 Given ein Punkt im Mittelland (CH-9211 bzw. die Spec-Koordinate 47.37/8.54, die in
    CH-9311 liegt), im Bulletin 2026-03-01 Morgen nicht bewertet / When abgefragt wird / Then leer,
    ``unavailable=False``; Pro-Quelle-Ergebnis "nicht zustaendig" (nicht ``ok``, ohne Ausfall)."""
    regionen = ch_regions_at(*punkt)
    assert len(regionen) == 1, "Voraussetzung: Punkt liegt in genau einer CH-Mikroregion"
    assert regionen[0] not in region_ids_in(slf_doc(WINTER_MORGEN)), "Voraussetzung: nicht bewertet"
    transport = SlfFixtureTransport(WINTER_MORGEN)
    source = only_slf(monkeypatch, transport, FakeClock(WINTER_NOW))

    assert source.covers(*punkt) is True, "Polygon: Mittelland ist zunaechst zustaendig"
    alerts, unavailable, sources = _mit_quellen_journal(*punkt, WINTER_NOW)

    assert alerts == []
    assert unavailable is False, "nicht bewertete Region ist kein Ausfall"
    assert transport.count == 1, "Voraussetzung: der Abruf fand statt (Region erst danach unbekannt)"
    assert sources.get(SLF_REGISTRY_NAME) == (False, []), (
        f"Region nicht im Bulletin => 'nicht zustaendig' (mark_not_covered): {sources}"
    )
    rows = _slf_journal_rows()
    assert rows and all(r["ok"] is True for r in rows), f"Journal: Antwort war erfolgreich: {rows}"


def test_ac13_region_aus_februar_fehlt_im_dezember_dieselbe_quelle_liefert_sie_nur_einmal(
    monkeypatch,
):
    """AC-13 Given eine Mikroregion, die in 2026-02-10 bewertet ist und in 2025-12-20 nicht (aus den
    Fixtures bestimmt) / When DIESELBE Quelle zuerst am 12-20, dann am 02-10 abgefragt wird / Then
    im Dezember leer ohne Hinweis, im Februar die Warnung dieser Region."""
    nur_februar = sorted(region_ids_in(slf_doc(FEBRUAR)) - region_ids_in(slf_doc(DEZEMBER)))
    assert nur_februar, "Voraussetzung: die Fixtures unterscheiden sich in den bewerteten Regionen"
    rid = nur_februar[0]
    punkt = interior_point(rid)
    dezember = datetime(2025, 12, 20, 8, 0, tzinfo=UTC)
    februar = datetime(2026, 2, 10, 8, 0, tzinfo=UTC)
    transport = SlfFixtureTransport(DEZEMBER)
    clock = FakeClock(dezember)
    only_slf(monkeypatch, transport, clock)

    alerts_dez, unavailable_dez = alerts_with_status(*punkt, dezember)
    transport.set(FEBRUAR)
    clock.advance((februar - dezember).total_seconds())
    alerts_feb, unavailable_feb = alerts_with_status(*punkt, februar)

    assert alerts_dez == [] and unavailable_dez is False
    assert [a.source for a in _slf_alerts(alerts_feb)] == [f"slf_bulletin:{rid}"]
    assert unavailable_feb is False
    assert transport.count == 2


def test_ac13_quelltext_enthaelt_keine_feste_liste_von_regions_ids():
    # doc-compliance-test
    """AC-13 (nur dieser Teil Doku-Konformitaet, laut Spec erlaubt): Given ``slf.py`` / Then steht
    darin kein String-Literal, das eine CH-Regions-ID ist -- weder als Ausschlussliste noch als
    Einzelvergleich (Docstrings/Kommentare zaehlen nicht)."""
    assert SLF_MODULE.exists(), f"Pruefling fehlt: {SLF_MODULE.relative_to(REPO_ROOT)}"
    tree = ast.parse(SLF_MODULE.read_text(encoding="utf-8"))
    region_id = re.compile(r"^CH-\d{4}$")

    treffer = [
        (node.lineno, node.value) for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and region_id.match(node.value)
    ]

    assert treffer == [], f"hartcodierte Regions-IDs in slf.py: {treffer}"


# ================================================================== AC-14: SLF-Ausfall im Mittelland
def test_ac14_slf_ausfall_im_mittelland_zeigt_den_generischen_ausfallhinweis(monkeypatch):
    """AC-14 (bekannte, ausdruecklich beschriebene Eigenschaft) Given der SLF-Abruf scheitert (503)
    und der Punkt liegt in CH-9211 / When mit Status abgefragt wird / Then ``unavailable=True`` wie
    in Graubuenden -- kein Kompensationspartner zustaendig. Gegenprobe: bei erfolgreicher Antwort
    ohne diese Region ``unavailable=False``."""
    transport = SlfFixtureTransport(http_503())
    only_slf(monkeypatch, transport, FakeClock(WINTER_NOW))

    alerts, unavailable = alerts_with_status(*P_MITTELLAND_CH_9211, WINTER_NOW)

    assert transport.count >= 1, "Voraussetzung: der Abruf wurde versucht"
    assert alerts == [] and unavailable is True

    gegen_transport = SlfFixtureTransport(WINTER_MORGEN)
    only_slf(monkeypatch, gegen_transport, FakeClock(WINTER_NOW))
    alerts_ok, unavailable_ok = alerts_with_status(*P_MITTELLAND_CH_9211, WINTER_NOW)

    assert gegen_transport.count == 1
    assert alerts_ok == [] and unavailable_ok is False


# ================================================================== AC-15: Egress
def test_ac15_aws_slf_ch_ist_wie_avalanche_report_klassifiziert():
    """AC-15 Given das Python-Egress-Inventar / Then fuehrt es ``aws.slf.ch`` mit derselben
    Klassifikation wie ``avalanche.report`` (BLOCKED), der Waechter laesst den Host nicht durch,
    und kein weiterer SLF-Host ist hinzugekommen."""
    from app.egress_guard import INVENTORY, IsolationKind, _is_allowed

    assert SLF_API_HOST in INVENTORY, "aws.slf.ch fehlt im Egress-Inventar"
    assert INVENTORY[SLF_API_HOST] is INVENTORY["avalanche.report"]
    assert INVENTORY[SLF_API_HOST] is IsolationKind.BLOCKED
    assert _is_allowed(SLF_API_HOST) is False
    assert sorted(h for h in INVENTORY if "slf" in h) == [SLF_API_HOST]


def test_ac15_echter_abruf_aus_der_testumgebung_wird_blockiert(monkeypatch):
    """AC-15 Given eine ``SlfSource`` OHNE Fixture-Transport (echter httpx-Transport) / When ein
    Punkt in Graubuenden abgefragt wird / Then blockt der Egress-Waechter: keine Warnung,
    ``unavailable=True``, Journal-Zeile fuer ``aws.slf.ch`` mit ``ok=False``."""
    from services.official_alerts.slf import SlfSource

    clock = FakeClock(WINTER_NOW)
    source = SlfSource(cache={}, clock=clock, now_fn=clock.now)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_GRAUBUENDEN, WINTER_NOW)

    assert alerts == [] and unavailable is True
    rows = _slf_journal_rows()
    assert rows and all(r["ok"] is False for r in rows), rows


# ================================================================== AC-16: Registry-Reihenfolge
def test_ac16_slf_steht_unmittelbar_nach_avalanche_report_am_ende_der_registry():
    """AC-16 Given die echte Standard-Registry / When die Quellen aufgelistet werden / Then heisst
    die Quelle ``slf_bulletin``, steht genau einmal unmittelbar nach ``avalanche_report``, und
    beide liegen nach allen uebrigen Quellen."""
    import services.official_alerts  # noqa: F401  (Registrierung beim Import)

    names = registered_names()

    assert names.count(SLF_REGISTRY_NAME) == 1, names
    assert names.index(SLF_REGISTRY_NAME) == names.index("avalanche_report") + 1, names
    assert names[-2:] == ["avalanche_report", SLF_REGISTRY_NAME], names


def test_ac16_registrierter_eintrag_ist_eine_slf_source_mit_polygon_zustaendigkeit():
    """AC-16 Given die echte Registry / Then ist der Eintrag ``slf_bulletin`` eine ``SlfSource``
    (nicht nur ein Name) und liefert fuer Schweizer Punkte Zustaendigkeit per Polygon."""
    import services.official_alerts  # noqa: F401
    from services.official_alerts import base
    from services.official_alerts.slf import SlfSource

    eintraege = [s for s in base._REGISTERED_SOURCES if s.name == SLF_REGISTRY_NAME]

    assert len(eintraege) == 1 and isinstance(eintraege[0], SlfSource)
    assert eintraege[0].covers(*P_GRAUBUENDEN) is True
    assert eintraege[0].covers(*P_INNSBRUCK) is False


# ================================================================== AC-17: abschaltbar
def test_ac17_ohne_registrierungszeile_fehlt_nur_der_slf_eintrag(monkeypatch):
    """AC-17 Given die echte Registry, in der ``slf_bulletin`` steht / When die Registrierung
    entfernt ist / Then fehlt nur dieser Eintrag; die uebrigen Quellen stehen unveraendert in
    derselben Reihenfolge."""
    import services.official_alerts  # noqa: F401

    vorher = registered_names()
    assert SLF_REGISTRY_NAME in vorher, "Voraussetzung: slf_bulletin ist registriert"

    registry_without(monkeypatch)

    assert registered_names() == [n for n in vorher if n != SLF_REGISTRY_NAME]
    assert registered_names()[-1] == "avalanche_report"


def test_ac17_ohne_slf_kein_abruf_keine_warnung_kein_ausfallhinweis_in_graubuenden(monkeypatch):
    """AC-17 Given eine Registry, in der SLF bei einem 503 den Ausfallhinweis fuer Graubuenden
    ausloest (Vorbedingung) / When die SLF-Registrierung entfernt wird / Then keine SLF-Warnung,
    kein weiterer Abruf an ``aws.slf.ch``, kein SLF-Ergebnis und kein Ausfallhinweis."""
    transport = SlfFixtureTransport(http_503())
    only_slf(monkeypatch, transport, FakeClock(WINTER_NOW))

    _a, mit_unavailable, mit_sources = _mit_quellen_journal(*P_GRAUBUENDEN, WINTER_NOW)
    assert mit_unavailable is True and transport.count == 1, "Voraussetzung: SLF loest Hinweis aus"
    assert SLF_REGISTRY_NAME in mit_sources

    registry_without(monkeypatch)
    alerts, unavailable, sources = _mit_quellen_journal(*P_GRAUBUENDEN, WINTER_NOW)

    assert _slf_alerts(alerts) == []
    assert unavailable is False, "ohne SLF darf kein Ausfallhinweis entstehen"
    assert SLF_REGISTRY_NAME not in sources, sources
    assert transport.count == 1, "ohne Registrierung kein Zugriff auf aws.slf.ch"


def test_ac17_tirol_ergebnis_ist_mit_und_ohne_slf_identisch(monkeypatch):
    """AC-17 Given ein Punkt in Tirol (S1-Quelle mit aufgezeichnetem Tirol-Bulletin) / When er
    einmal mit (Fixture-)SLF in der echten Registry und einmal ohne SLF-Registrierung abgefragt wird
    / Then sind Warnungen und Ausfallstatus identisch, und SLF ruft fuer Tirol nie ab (Vorbedingung:
    SLF steht in der Registry, Tirol liefert die AT-Warnung, SLF ruft fuer Graubuenden ab)."""
    import services.official_alerts  # noqa: F401
    from tests.helpers.avalanche_report_support import (
        FixtureTransport, day_file, make_source,
    )
    from tests.helpers.avalanche_report_support import ok as at_ok

    assert SLF_REGISTRY_NAME in registered_names(), "Voraussetzung: slf_bulletin ist registriert"
    transport, clock, source = _quelle(WINTER_MORGEN, WINTER_NOW)
    at_transport = FixtureTransport({"AT-07": at_ok(day_file("2026-03-01"))})
    registry_replacing(monkeypatch, make_source(at_transport, FakeClock(WINTER_NOW)))

    with monkeypatch.context() as m:
        registry_replacing(m, source)
        mit_alerts, mit_unavailable = alerts_with_status(*P_TIROL_AT_07_05, WINTER_NOW)
        assert transport.count == 0, "SLF darf fuer Tirol nicht abrufen"
        assert [a.hazard for a in mit_alerts
                if str(a.source).split(":", 1)[0] == "avalanche_report"] == [
            "avalanche_bulletin"
        ], "Voraussetzung: Tirol liefert die AT-Lageberichts-Warnung"
        ch_alerts, _ = alerts_with_status(*P_GRAUBUENDEN, WINTER_NOW)
        assert [a.source for a in _slf_alerts(ch_alerts)] == ["slf_bulletin:CH-5123"]

    registry_without(monkeypatch)
    ohne_alerts, ohne_unavailable = alerts_with_status(*P_TIROL_AT_07_05, WINTER_NOW)

    def _kern(alerts):
        return sorted((a.source, a.hazard, a.level, a.native_level) for a in alerts)

    assert _kern(ohne_alerts) == _kern(mit_alerts)
    assert ohne_unavailable == mit_unavailable
    assert transport.count == 1
