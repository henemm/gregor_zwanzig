"""
TDD RED Tests fuer #1708 Scheibe B1 -- stillgelegte Tests am toten
`trips/`-Pfad reaktivieren.

Jeder Test mappt auf ein AC aus
docs/specs/modules/fix_1708_b1_tote_fixture_befunde.md und muss HEUTE rot
sein. Kein Mock/patch/MagicMock, keine Dateiinhalt-Checks als
Verhaltensnachweis -- alle Subprozess-Laeufe verankern sich relativ zur
eigenen Testdatei, nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ac1_bug338_wird_im_standardlauf_gesammelt():
    """AC-1: test_bug_338_openmeteo_call_counter.py traegt heute einen
    modul-weiten @pytest.mark.live-Marker (:24) -- ein Standardlauf
    deselektiert dadurch alle 6 Tests. Nach dem Marker-Split auf
    Funktionsebene muss die Datei im Standardlauf (normale addopts, kein
    Marker-Override) erscheinen.
    """
    target = REPO_ROOT / "tests" / "tdd" / "test_bug_338_openmeteo_call_counter.py"
    proc = subprocess.run(
        ["uv", "run", "pytest", str(target), "--collect-only", "-q"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180,
    )
    match = re.search(r"test_bug_338_openmeteo_call_counter\.py:\s*(\d+)", proc.stdout)
    collected = int(match.group(1)) if match else 0

    if not match:
        # Heute (Modul-`live`-Marker aktiv) deselektiert der Standardlauf ALLE
        # 6 Tests -- pytest liefert dafuer exit 5 ("no tests collected") und
        # unterdrueckt unter dem doppelten -q (addopts bringt bereits eines
        # mit) sogar die Zusammenfassungszeile, stdout bleibt leer. Das ist
        # der erwartete RED-Grund. Jeder ANDERE returncode bei leerem stdout
        # waere ein Werkzeugfehler (uv/pytest nicht startbar) statt einer
        # Aussage ueber den Marker -- getrennt gemeldet, damit die naechste
        # Sitzung beide Faelle sofort auseinanderhalten kann.
        assert proc.returncode == 5, (
            "Kein Kollektionsergebnis im stdout UND unerwarteter Exit-Code -- "
            "das deutet auf einen Werkzeugfehler (uv/pytest nicht startbar) "
            f"hin, nicht auf den Marker-Defekt. returncode={proc.returncode}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    assert collected > 0, (
        "AC-1 verletzt: Standardlauf sammelt keinen einzigen Test aus der "
        f"Datei (Modul-`live`-Marker deselektiert alles, returncode="
        f"{proc.returncode}). stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_ac5_issue346_kein_test_skippt_mangels_trip_bestand():
    """AC-5: `_find_test_trip()` (test_issue_346_fixture_provider.py:24-32)
    sucht im toten `trips/`-Pfad und findet unter der isolierten
    Datenwurzel nie etwas -- AC-6 der Datei skippt deshalb bei jedem Lauf
    (`:121`). Nach dem Fix (Fixture selbst unter get_briefings_dir()
    anlegen) darf kein Test der Datei mehr skippen.
    """
    target = REPO_ROOT / "tests" / "tdd" / "test_issue_346_fixture_provider.py"
    proc = subprocess.run(
        ["uv", "run", "pytest", str(target), "-q", "-rs"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180,
    )
    assert "SKIPPED" not in proc.stdout, (
        f"AC-5 verletzt: ein Test der Datei skippt mangels Trip-Bestand:\n{proc.stdout}"
    )


def test_ac3_alarm_segment_eigenschaft_ist_zeitunabhaengig():
    """AC-3: Die vom Alarm-Pfad (src/services/trip_alert.py:1247-1249)
    gepruefte Eigenschaft -- `segment.end_time > now_utc` UND
    `segment.start_time.date() <= now_utc.date()` -- muss fuer das von
    `_make_segment()` gebaute Segment zu JEDER Tageszeit gelten, nicht nur
    vormittags. `_make_segment()` baut das Fenster heute fest auf
    06:00-14:00 UTC; um 23:00 UTC ist end_time bereits verstrichen -> rot.

    Zwei feste, eingefrorene Zeitpunkte -- der Test selbst darf nicht
    zeitabhaengig sein, das ist genau der Defekt, den wir beheben.
    """
    from tests.tdd.test_bug_338_openmeteo_call_counter import _make_segment

    for frozen in ("2026-08-16T02:00:00+00:00", "2026-08-16T23:00:00+00:00"):
        with freeze_time(frozen):
            now_utc = datetime.now(timezone.utc)
            segment = _make_segment()
            assert segment.end_time > now_utc, (
                f"AC-3 verletzt bei {frozen}: end_time {segment.end_time} liegt "
                f"nicht nach now_utc {now_utc} -- trip_alert.py:1248 wuerde das "
                "Segment ueberspringen"
            )
            assert segment.start_time.date() <= now_utc.date(), (
                f"AC-3 verletzt bei {frozen}: start_time.date() "
                f"{segment.start_time.date()} liegt nach now_utc.date() "
                f"{now_utc.date()}"
            )


def test_ac6_isolationssonde_uebersteht_wegfall_von_get_trips_dir(tmp_path):
    """AC-6: Die Isolationssonde in test_issue_1133_testdata_cleanup.py
    (:57-75) muss den Wegfall von get_trips_dir() in Scheibe B2 ueberstehen
    -- das gelingt nur, wenn sie stattdessen get_briefings_dir() befragt.

    Gewaehlter Weg (gleichwertig zur im Auftrag skizzierten
    Subprozess/`-p`-Variante -- ein conftest-freies Vorschalt-Skript waere
    hier fragiler als der direkte Verhaltensbeweis, und conftest.py selbst
    ruft an mehreren Stellen get_trips_dir() zur Session-Fixture-Zeit, was
    ein sauberes Vorschalten erschweren wuerde): get_trips_dir() wird per
    monkeypatch.delattr aus app.loader entfernt, danach wird die betroffene
    Sondenfunktion direkt aufgerufen. Heute wirft das AttributeError, weil
    Teil A der Sonde (:61-69) get_trips_dir() direkt aufruft -> rot.
    """
    import app.loader as loader
    from tests.tdd.test_issue_1133_testdata_cleanup import (
        test_ac1_fixture_isolation_path_resolution_and_roundtrip as sonde,
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.delattr(loader, "get_trips_dir", raising=False)
        with pytest.MonkeyPatch.context() as sonde_mp:
            try:
                sonde(tmp_path, sonde_mp)
            except (AttributeError, ImportError) as exc:
                pytest.fail(
                    "AC-6 verletzt: die Isolationssonde bricht ab, sobald "
                    f"get_trips_dir() fehlt (Scheibe B2) -- {exc}"
                )


def test_ac7_subprozess_wrapper_ist_blind_fuer_uebersprungene_zieltests(tmp_path):
    """AC-7: Der Subprozess-Wrapper (test_ac3_existing_six_tests_still_green)
    prueft heute nur returncode == 0 und ist damit blind fuer einen
    uebersprungenen Zieltest -- ein Skip liefert ebenfalls Exit 0.

    Nachweis: eine winzige, garantiert skippende Testdatei wird exakt wie
    der heutige Wrapper (`-o addopts=`) im Subprozess ausgefuehrt; das
    liefert HEUTE returncode == 0 trotz Skip. Die gewuenschte Zukunft
    prueft eine noch fehlende Hilfsfunktion
    `subprozess_lauf_ist_beweiskraeftig(proc)`, die einen solchen Lauf
    ablehnen soll. Sie existiert in test_issue_338_go_geosphere_counter.py
    noch nicht -> ImportError -> legitimes RED.
    """
    from tests.tdd.test_issue_338_go_geosphere_counter import (
        subprozess_lauf_ist_beweiskraeftig,
    )

    skip_datei = tmp_path / "test_garantiert_skip.py"
    skip_datei.write_text(
        "import pytest\n\n"
        "def test_der_immer_skippt():\n"
        "    pytest.skip('absichtlicher Skip fuer AC-7-Nachweis')\n"
    )

    proc = subprocess.run(
        ["uv", "run", "pytest", str(skip_datei), "-q", "-o", "addopts="],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, (
        "Praebedingung verletzt: heutige Wrapper-Logik sollte bei einem Skip "
        f"Exit 0 liefern, bekam {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    )
    assert "skipped" in proc.stdout.lower(), (
        f"Praebedingung verletzt: Subprozess-Ausgabe sollte einen Skip melden:\n{proc.stdout}"
    )

    assert not subprozess_lauf_ist_beweiskraeftig(proc), (
        "AC-7 verletzt: die Wrapper-Pruefung haette diesen skip-only Lauf als "
        "NICHT beweiskraeftig ablehnen muessen"
    )
