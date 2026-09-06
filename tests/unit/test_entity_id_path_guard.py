"""Entitaets-Kennung darf im Python-Kern keinen Pfad aus dem eigenen
Nutzerverzeichnis herausfuehren — Python-Pendant zu AC-8 (Issue #2140
Scheibe 2).

SPEC: docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md, AC-8
("der Guard sitzt im Store, nicht nur im Handler") und AC-7
(Zwei-Nutzer-Nachweis nach ADR-0003).

Die Go-Seite hat diesen Nachweis in internal/store/entity_id_test.go. Der
Python-Kern hat drei eigene Stellen, die aus einer client-gesetzten Kennung
einen Dateipfad bauen — alle drei werden hier UNTER UMGEHUNG VON HTTP
aufgerufen, weil genau das der Punkt ist: der Schutz der HTTP-Routen ist eine
Eigenschaft von Starlettes Router (Dot-Segment-Aufloesung vor dem Routing),
keine Zusicherung dieses Systems (Spec, Abschnitt "Nachtrag aus der RED-Phase",
Absatz "Der Guard gehoert trotzdem an alle diese Stellen").

Gedeckte Stellen:
  1. services.scheduler_dispatch_service.save_compare_preset_status  -> stilles return
  2. services.scheduler_dispatch_service.save_compare_preset_pause   -> stilles return
  3. services.preview_service.PreviewService._load_trip              -> ValueError
  4. api.routers.validator._load_trip_raw                            -> None

Bauart (bewusst ohne Mock): echtes ``users/alice/`` und ``users/bob/`` unter
der isolierten Datenwurzel (tests/conftest.py::_isolate_data_root), echte
``user.json`` fuer bob, und nach jedem Aufruf der rekursive Verzeichnis-Diff
plus Byte- und mtime-Vergleich. Kein SMTP, keine Mail — die Guards liegen vor
jedem Versandpfad.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app import loader

# Die Kennung ist NICHT frei gewaehlt: briefings/ liegt ZWEI Ebenen unter
# <root>/users/, deshalb kappt "../../" genau "briefings" und "alice" und
# landet bei <root>/users/bob/user.json. Ein einfaches "../bob/user" bliebe
# im EIGENEN Verzeichnis und ergaebe einen Test, der auch ohne Guard gruen
# waere (Spec-Praeambel zu den ACs). Nachgerechnet wird das unten in
# ``_positivkontrolle`` — nicht angenommen.
ATTACK_ID = "../../bob/user"

# Marker im Inhalt von Bobs Datei: taucht er je in einer Antwort oder
# Fehlermeldung auf, ist fremder Inhalt nach aussen gelangt.
BOB_SECRET = "bobs-echter-passwort-hash-2140"


def _repo_root() -> Path:
    """Wurzel DIESES Arbeitsverzeichnisses, aufgeloest relativ zur eigenen
    Testdatei — nie ueber einen festen Hauptrepo-Pfad. Sonst pruefte ein Lauf
    im Worktree den Code des Hauptordners und meldete falsches Gruen."""
    return Path(__file__).resolve().parents[2]


def _snapshot(verzeichnis: Path) -> dict[str, tuple[str, int]]:
    """Rekursiver Abzug: relativer Pfad -> (Inhalt, mtime_ns)."""
    abzug: dict[str, tuple[str, int]] = {}
    for pfad in sorted(verzeichnis.rglob("*")):
        if pfad.is_file():
            st = pfad.stat()
            abzug[str(pfad.relative_to(verzeichnis))] = (
                pfad.read_text(encoding="utf-8"),
                st.st_mtime_ns,
            )
    return abzug


@pytest.fixture
def zwei_nutzer():
    """Legt zwei ECHTE Nutzer an und liefert (root, bob_user_json, bob_dir).

    ``alice`` ist der Angreifer (ihr ``briefings/`` muss existieren, sonst
    laesst das Dateisystem die ``..``-Traversierung gar nicht erst zu),
    ``bob`` das Opfer mit einer realen ``user.json``.
    """
    root = loader.get_data_root()

    alice_briefings = loader.get_briefings_dir("alice")
    alice_briefings.mkdir(parents=True, exist_ok=True)

    bob_dir = loader.get_data_dir("bob")
    bob_dir.mkdir(parents=True, exist_ok=True)
    bob_user_json = bob_dir / "user.json"
    bob_user_json.write_text(
        json.dumps({"id": "bob", "password_hash": BOB_SECRET}),
        encoding="utf-8",
    )
    return root, bob_user_json, bob_dir


@pytest.fixture
def bob_unveraendert(zwei_nutzer):
    """Nimmt VOR dem Angriff den Bezugszustand auf und prueft ihn danach —
    Zwei-Nutzer-Nachweis nach ADR-0003 (Pendant zu AC-7 auf der Go-Seite):
    Byte-Inhalt UND mtime der ``user.json``, plus rekursiver Diff von Bobs
    komplettem Nutzerordner.
    """
    _root, bob_user_json, bob_dir = zwei_nutzer
    vorher_datei = bob_user_json.read_bytes()
    vorher_mtime = bob_user_json.stat().st_mtime_ns
    vorher_ordner = _snapshot(bob_dir)

    yield

    assert bob_user_json.exists(), "Bobs user.json ist durch den Angriff verschwunden"
    assert bob_user_json.read_bytes() == vorher_datei, (
        "Bobs user.json wurde inhaltlich veraendert"
    )
    assert bob_user_json.stat().st_mtime_ns == vorher_mtime, (
        "Bobs user.json wurde neu geschrieben (mtime veraendert), auch wenn der "
        "Inhalt zufaellig gleich blieb"
    )
    assert _snapshot(bob_dir) == vorher_ordner, (
        "Bobs Nutzerordner hat sich veraendert (rekursiver Diff)"
    )


def _aufgeloeste_angriffsdatei() -> Path:
    """Rechnet aus, wohin ``<alice-briefings>/<ATTACK_ID>.json`` zeigt."""
    alice_briefings = loader.get_briefings_dir("alice")
    return Path(os.path.normpath(alice_briefings / f"{ATTACK_ID}.json"))


# ---------------------------------------------------------------------------
# Positivkontrolle — PFLICHT: belegt, dass die Kennung ohne Guard tatsaechlich
# in fremdem Gebiet landet. Ohne diesen Nachweis waeren alle Tests unten
# moeglicherweise auch ohne Fix gruen (sie pruefen ein AUSBLEIBEN).
# ---------------------------------------------------------------------------

def test_positivkontrolle_kennung_zeigt_wirklich_auf_bobs_user_json(zwei_nutzer):
    """Given die Ablage aus der Fixture / When der Pfadbau
    ``<alice-briefings>/<ATTACK_ID>.json`` lexikalisch aufgeloest wird / Then
    ist das Ergebnis exakt Bobs echte ``user.json`` — die Kennung ist also
    potent, und ein Test auf ihr Ausbleiben prueft etwas."""
    _root, bob_user_json, _bob_dir = zwei_nutzer

    ziel = _aufgeloeste_angriffsdatei()

    assert ziel == bob_user_json, (
        f"Die Ausbruchs-Kennung {ATTACK_ID!r} zeigt auf {ziel}, nicht auf "
        f"Bobs user.json {bob_user_json} — der Test waere sonst wirkungslos"
    )
    assert ziel.exists(), "Zieldatei existiert nicht — Angriff liefe ins Leere"
    assert BOB_SECRET in ziel.read_text(encoding="utf-8"), (
        "Zieldatei traegt nicht Bobs Inhalt — falsche Ablage"
    )


def test_prueflinge_stammen_aus_diesem_arbeitsverzeichnis():
    """Given ein moeglicherweise parallel bestehender Hauptordner / When die
    drei Prueflinge importiert werden / Then liegen ihre Quelldateien unter
    DERSELBEN Wurzel wie diese Testdatei — sonst pruefte der Lauf fremden
    Code und meldete falsches Gruen."""
    import api.routers.validator as validator_modul
    import services.preview_service as preview_modul
    import services.scheduler_dispatch_service as dispatch_modul

    wurzel = _repo_root()
    for modul in (dispatch_modul, preview_modul, validator_modul):
        quelle = Path(modul.__file__).resolve()
        assert wurzel in quelle.parents, (
            f"{modul.__name__} wurde aus {quelle} geladen, nicht aus {wurzel}"
        )


# ---------------------------------------------------------------------------
# 1 + 2 — scheduler_dispatch_service: Read-Modify-WRITE auf briefings/<id>.json
# ---------------------------------------------------------------------------

def test_save_compare_preset_status_schreibt_nicht_in_fremdes_verzeichnis(
    zwei_nutzer, bob_unveraendert
):
    """Given zwei echte Nutzer / When ``save_compare_preset_status`` direkt —
    unter Umgehung von HTTP — mit der Ausbruchs-Kennung aufgerufen wird /
    Then kehrt es still zurueck und Bobs Verzeichnis bleibt unangetastet."""
    from services.scheduler_dispatch_service import save_compare_preset_status

    root, _bob_user_json, _bob_dir = zwei_nutzer

    ergebnis = save_compare_preset_status(
        "alice", ATTACK_ID, "Angreifer-Ort", data_root=str(root),
    )

    assert ergebnis is None, "Guard darf keinen Wert und keine Ausnahme liefern"


def test_save_compare_preset_pause_schreibt_nicht_in_fremdes_verzeichnis(
    zwei_nutzer, bob_unveraendert
):
    """Given dieselbe Ausgangslage / When ``save_compare_preset_pause`` direkt
    mit der Ausbruchs-Kennung aufgerufen wird / Then kehrt es still zurueck
    und Bobs Verzeichnis bleibt unangetastet."""
    from services.scheduler_dispatch_service import save_compare_preset_pause

    root, _bob_user_json, _bob_dir = zwei_nutzer

    ergebnis = save_compare_preset_pause(
        "alice", ATTACK_ID, str(root), "2026-09-06T12:00:00Z",
    )

    assert ergebnis is None, "Guard darf keinen Wert und keine Ausnahme liefern"


# ---------------------------------------------------------------------------
# 3 — PreviewService._load_trip: Lesepfad hinter GET /api/preview/{id}/…
# ---------------------------------------------------------------------------

def test_preview_service_load_trip_lehnt_ausbruchs_kennung_ab(
    zwei_nutzer, bob_unveraendert
):
    """Given zwei echte Nutzer / When ``PreviewService._load_trip`` direkt mit
    der Ausbruchs-Kennung aufgerufen wird / Then scheitert es mit einem
    ValueError, der die Kennung als ungueltig benennt, und traegt keinerlei
    Inhalt aus Bobs Datei nach aussen.

    Die Erwartung ist bewusst eng gefasst: ``LoaderError`` (die Ausnahme, die
    ein ungeschuetzter Lauf auf Bobs user.json ausloest) erbt von
    ``Exception``, nicht von ``ValueError`` — eine entfernte Sperre faellt
    hier also auf.
    """
    from services.preview_service import PreviewService

    with pytest.raises(ValueError) as fehler:
        PreviewService()._load_trip(ATTACK_ID, user_id="alice")

    meldung = str(fehler.value)
    assert "invalid trip_id" in meldung, (
        f"Erwartet wurde die Kennungs-Ablehnung, bekam: {meldung!r}"
    )
    assert BOB_SECRET not in meldung, "Fremder Dateiinhalt steht in der Fehlermeldung"


# ---------------------------------------------------------------------------
# 4 — validator._load_trip_raw: Rohleser hinter POST /trips/{id}/alert-preview
# ---------------------------------------------------------------------------

def test_validator_load_trip_raw_liefert_keinen_fremden_inhalt(
    zwei_nutzer, bob_unveraendert
):
    """Given zwei echte Nutzer / When ``_load_trip_raw`` direkt mit der
    Ausbruchs-Kennung aufgerufen wird / Then liefert es None statt des
    Roh-Dicts aus Bobs ``user.json``.

    Ohne Guard ist dieser Aufruf ein echtes Leck: Bobs ``user.json`` ist
    gueltiges JSON und ein Dict — der Rohleser gaebe sie unveraendert zurueck.
    """
    from api.routers.validator import _load_trip_raw

    ergebnis = _load_trip_raw("alice", ATTACK_ID)

    assert ergebnis is None, (
        f"Fremder Dateiinhalt wurde zurueckgeliefert: {ergebnis!r}"
    )
