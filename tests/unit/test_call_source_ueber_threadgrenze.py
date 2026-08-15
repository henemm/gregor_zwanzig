"""AC-4 (#1765 Scheibe B1): die Diagnose-Quelle ueberlebt den Threadwechsel.

Spec: docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md

``resolve_call_source()`` (src/providers/call_log.py:56-64) liest die
Funktionsnamen aus dem Aufruf-Stapel des AUSFUEHRENDEN Threads. Sobald die Orte
eines Vergleichs in eigenen Threads berechnet werden, taucht dort keiner der 11
Bestandsmarker (call_log.py:41-53) mehr auf und das Journal bucht "unbekannt"
(belegt: 7,4 % im Diagnose-Journal, Cluster beim bereits parallelen
stage_weather-Pfad).

RED-Grund: ``providers.call_log.override_call_source`` existiert nicht
(ImportError). Der Name wird hier festgelegt: ein Context-Manager mit
Zuruecksetzen, Vorbild ``official_alerts/warn_egress.py:84-96``.

Geprueft wird die im Journal TATSAECHLICH VERZEICHNETE Quelle je Eintrag --
nicht die Anwesenheit einer Funktion im Quelltext.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

WORKTREE = Path(__file__).resolve().parents[2]
ZEITSCHRANKE = 5.0  # Sekunden
BASIS = "https://api.open-meteo.com/v1/"


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Diagnose-Journal auf eine Wegwerf-Datei umlenken; liefert einen Leser
    (Endpunkt -> verzeichnete Quelle)."""
    from providers import call_log

    # Pfadregel #1409: der Pruefling muss aus DIESEM Checkout stammen.
    assert Path(call_log.__file__).resolve().is_relative_to(WORKTREE), call_log.__file__
    pfad = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(call_log, "DIAGNOSTICS_PATH", pfad)

    def lesen() -> dict[str, str]:
        zeilen = pfad.read_text().splitlines() if pfad.exists() else []
        eintraege = [json.loads(z) for z in zeilen]
        return {e["endpoint"]: e["source"] for e in eintraege}

    return lesen


def test_ac4_gleichzeitige_threads_verzeichnen_ihre_quelle_im_journal(journal):
    """AC-4: Zwei Threads laufen per Treffpunkt-Sperre garantiert gleichzeitig
    und protokollieren je einen Abruf innerhalb des Quellen-Overrides. Beide
    Eintraege muessen "vergleich" tragen -- im Worker-Stack steht keiner der 11
    Bestandsmarker, ohne Override buchte das Journal "unbekannt"."""
    from providers.call_log import log_api_call, override_call_source

    treffpunkt = threading.Barrier(2)

    def ortsberechnung(nummer: int) -> None:
        treffpunkt.wait(timeout=ZEITSCHRANKE)
        with override_call_source("vergleich"):
            log_api_call(f"{BASIS}ort-{nummer}", 200)

    threads = [threading.Thread(target=ortsberechnung, args=(n,)) for n in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=ZEITSCHRANKE * 2)
        assert not t.is_alive(), "Thread haengt -- Treffpunkt nicht aufgeloest?"

    assert journal() == {f"{BASIS}ort-1": "vergleich", f"{BASIS}ort-2": "vergleich"}, (
        f"AC-4: Das Journal verzeichnete {journal()} statt fuer JEDEN Eintrag "
        "'vergleich'. Im Worker-Stack fehlen die 11 Namens-Marker -- die Quelle "
        "muss im jeweiligen Thread gesetzt und VOR der Stapel-Inspektion "
        "geprueft werden."
    )


def test_ohne_override_greifen_die_bestandsmarker_weiter(journal):
    """Rueckwaerts-Vertrag: Threads OHNE eigenen Override verhalten sich
    unveraendert wie heute -- die 11 Namens-Marker bleiben der Rueckfall, ohne
    Marker bleibt es bei "unbekannt". Zusaetzlich geprueft: ein in einem ANDEREN
    Verarbeitungspfad aktiver Override faerbt nicht auf sie ab."""
    from providers.call_log import log_api_call, override_call_source

    def render_email_preview() -> None:  # Bestandsmarker -> "vorschau"
        log_api_call(f"{BASIS}mit-marker", 200)

    def namenloser_pfad() -> None:  # kein Marker -> "unbekannt"
        log_api_call(f"{BASIS}ohne-marker", 200)

    with override_call_source("vergleich"):  # in einem FREMDEN Pfad aktiv
        for ziel in (render_email_preview, namenloser_pfad):
            t = threading.Thread(target=ziel)
            t.start()
            t.join(timeout=ZEITSCHRANKE)
            assert not t.is_alive(), f"Thread {ziel.__name__} haengt"

    assert journal() == {
        f"{BASIS}mit-marker": "vorschau",
        f"{BASIS}ohne-marker": "unbekannt",
    }, (
        f"Das Journal verzeichnete {journal()}. Wer keinen eigenen Override "
        "setzt, muss die Quelle unveraendert ueber die Bestandsmarker "
        "(call_log.py:41-53) bekommen -- ein fremder Override darf nicht "
        "abfaerben."
    )


def test_override_geht_dem_bestandsmarker_vor(journal):
    """Vorrang-Regel (Spec: "Pruefung dieses Override-Werts VOR der bisherigen
    Stapel-Inspektion"). Anlass: Adversary-Finding F002 — vertauschte man die
    Reihenfolge, blieb KEINER der 18 Tests rot, weil in keinem Szenario
    gleichzeitig ein Override aktiv UND ein Bestandsmarker im Stapel stand.

    Genau das wird hier hergestellt: der Aufruf laeuft aus einer Funktion
    ``_fetch_weather`` heraus (Bestandsmarker -> "briefing", call_log.py:53).
    Ohne Vorrang gewaenne der Marker und das Journal buchte die parallele
    Vergleichs-Berechnung als "briefing" — eine falsche Herkunft, nicht bloss
    eine fehlende."""
    from providers.call_log import log_api_call, override_call_source, resolve_call_source

    def _fetch_weather(mit_override: bool) -> str:  # Bestandsmarker -> "briefing"
        if not mit_override:
            log_api_call(f"{BASIS}nur-marker", 200)
            return resolve_call_source()
        with override_call_source("vergleich"):
            log_api_call(f"{BASIS}marker-und-override", 200)
            return resolve_call_source()

    assert _fetch_weather(False) == "briefing", (
        "Vorbedingung: ohne Override MUSS der Bestandsmarker '_fetch_weather' "
        "greifen — sonst prueft dieser Test keinen Vorrang, sondern nichts."
    )

    assert _fetch_weather(True) == "vergleich", (
        "Der ausdruecklich gesetzte Override muss VOR der Stapel-Inspektion "
        "geprueft werden — sonst ueberdeckt ein beliebiger Bestandsmarker im "
        "Aufrufstapel die tatsaechliche Herkunft."
    )
    assert journal() == {
        f"{BASIS}nur-marker": "briefing",
        f"{BASIS}marker-und-override": "vergleich",
    }, (
        f"Am Wirkort (Diagnose-Journal) verzeichnet: {journal()}. Der Eintrag "
        "innerhalb des Overrides muss 'vergleich' tragen, obwohl '_fetch_weather' "
        "im Stapel steht."
    )


def test_quelle_wird_nach_dem_bereich_zurueckgesetzt(journal):
    """Ein ``ThreadPoolExecutor`` verwendet seine Threads wieder: bleibt der
    Override nach dem Bereich stehen, erbt eine spaetere, fachlich ANDERE
    Anfrage die Quelle "vergleich". Beide Aufgaben laufen hier nachweislich im
    SELBEN Thread -- ohne diese Vorbedingung bewiese der Test nichts."""
    from providers.call_log import log_api_call, override_call_source

    def mit_override() -> int:
        with override_call_source("vergleich"):
            log_api_call(f"{BASIS}im-bereich", 200)
        return threading.get_ident()

    def danach() -> int:
        log_api_call(f"{BASIS}nach-dem-bereich", 200)
        return threading.get_ident()

    with ThreadPoolExecutor(max_workers=1) as pool:
        erster = pool.submit(mit_override).result(timeout=ZEITSCHRANKE)
        zweiter = pool.submit(danach).result(timeout=ZEITSCHRANKE)

    assert erster == zweiter, "Vorbedingung: beide Aufgaben muessen denselben Thread nutzen"
    eintraege = journal()
    assert eintraege.get(f"{BASIS}im-bereich") == "vergleich"
    assert eintraege.get(f"{BASIS}nach-dem-bereich") == "unbekannt", (
        "Der Override wurde nach dem Bereich nicht zurueckgesetzt -- der "
        "wiederverwendete Thread vererbt "
        f"{eintraege.get(f'{BASIS}nach-dem-bereich')!r} in eine spaetere, "
        "fachlich andere Anfrage (Spec: reset(token), Vorbild warn_egress.py:95)."
    )
