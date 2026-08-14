"""Positivlisten-Wachstum, Filter C und Schwellen-Bindung (#1771 Scheibe 3).

Kern-Schicht, deterministisch: die Pruefinge sind Textdateien im Repo -- kein Netz,
kein Playwright-Lauf, kein Mock. Die Begruendung je Zusicherung steht am Testfall,
die volle Herleitung in `docs/specs/modules/fix_1771_s3_e2e_listen_wachstum.md`.

Pfadregel #1409: Pruefinge relativ zu DIESER Datei aufgeloest -- sonst pruefte der
Test aus dem Worktree die unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.

RED (2026-08-14): der Stub `pruefe_schwellen_bindung` (AC-6), 2 fehlende
Listeneintraege (AC-1), 3 Schreibpfade in 2 Dateien im versionierten Baum (AC-5/7).
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
POSITIVLISTE = REPO / ".github" / "ci_e2e_specs.txt"
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
E2E_DIR = REPO / "frontend" / "e2e"
PLAYWRIGHT_CWD = "frontend"  # Arbeitsordner des Playwright-Laufs
MANDANTEN_SPECS = ("e2e/compare-cross-user-write-block.spec.ts",
                   "e2e/compare-editor-autosave-user-isolation.spec.ts")
_PATH_RE = re.compile(r"""path:\s*['"`]([^'"`]+)['"`]""")


def pruefe_schwellen_bindung(ci_yml_text: str, listen_text: str) -> list[str]:
    """AC-6: meldet Divergenzen zwischen `E2E_MIN_SPECS` und Listenlaenge (leer =
    in Ordnung). EXAKTE Gleichheit, nicht `>=`; fehlende Schwelle = Verstoss."""
    raise NotImplementedError("entsteht in /50-implement (#1771 S3, AC-6)")

def _liste_zeilen(text: str) -> list[str]:
    return [z.strip() for z in text.splitlines()
            if z.strip() and not z.strip().startswith("#")]

def _synth_ci_yml(min_specs: int | None) -> str:
    zeile = f"      E2E_MIN_SPECS: {min_specs}\n" if min_specs is not None else ""
    return "  e2e:\n    env:\n" + zeile + "      E2E_MIN_EXECUTED: 173\n"

def _synth_liste(anzahl: int) -> str:
    return "# Kopf\n#\n\n" + "".join(f"e2e/d{i}.spec.ts\n" for i in range(anzahl))

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True, timeout=20)

def _schreibpfade() -> list[tuple[str, int, str]]:
    """Alle `path:`-Schreibpfade des GESAMTEN frontend/e2e-Korpus."""
    return [(d.name, nr, m.group(1))
            for d in sorted(E2E_DIR.rglob("*.spec.ts"))
            for nr, z in enumerate(d.read_text(encoding="utf-8").splitlines(), 1)
            for m in _PATH_RE.finditer(z)]

def _im_versionierten_baum(rohpfad: str) -> tuple[bool, str]:
    """Gemessen: liegt das Schreibziel ausserhalb jeder Ignore-Regel? `check-ignore`
    beachtet den Index (getrackt = nicht ignoriert); rc != 0 = Treffer, fail-closed."""
    ziel = os.path.normpath(os.path.join(PLAYWRIGHT_CWD, rohpfad))
    return _git("check-ignore", "-q", ziel).returncode != 0, ziel

@pytest.mark.parametrize("spec", MANDANTEN_SPECS)
def test_positivliste_enthaelt_mandantentrennungs_spec(spec):
    """AC-1: beide gemessen gruenen Mandanten-Specs stehen auf der Positivliste.

    GIVEN beide im 51er-Diagnoselauf (2026-08-14) vollstaendig gruen, einzige
          Klasse fuer die CLAUDE.md-Pflicht "zwei Nutzer"
    WHEN die Positivliste gelesen wird
    THEN steht der Eintrag darin -- und die Datei existiert wirklich (ein
         Phantom-Name laesst den CI-Job an der Existenzpruefung scheitern).
    """
    assert (REPO / PLAYWRIGHT_CWD / spec).is_file(), f"Spec-Datei fehlt: {spec}"
    gelistet = _liste_zeilen(POSITIVLISTE.read_text(encoding="utf-8"))
    assert spec in gelistet, (
        f"{spec} fehlt auf der Positivliste ({len(gelistet)} Eintraege) -- "
        f"gemessen gruen, aber ungelistet bewacht die Mandantentrennung niemand.")

def test_kein_spec_schreibt_in_den_versionierten_baum():
    """AC-5/AC-7: kein Schreibziel liegt in einem von Git gefuehrten Ordner.

    GIVEN Playwright schreibt relativ zu `frontend/`, `.gitignore:80` greift am Root
    WHEN jeder `path:`-Wert des Korpus aufgeloest und per git gemessen wird
    THEN meldet die Messung kein Ziel -- ein Lauf, der getrackte Dateien aendert,
         ist ein Anti-Pattern.
    """
    assert _git("rev-parse", "--is-inside-work-tree").returncode == 0, (
        "git nicht benutzbar -- ungemessen ist kein Nachweis (fail-closed).")
    verstoesse = [f"{d}:{nr} {p!r} -> {ziel}" for d, nr, p in _schreibpfade()
                  for treffer, ziel in [_im_versionierten_baum(p)] if treffer]
    assert not verstoesse, (
        f"{len(verstoesse)} Schreibpfad(e) landen im versionierten Baum:\n  "
        + "\n  ".join(verstoesse) + "\nAbhilfe: fuehrendes '../' ergaenzen.")

def test_filter_c_kriterium_ist_geeicht():
    """AC-5/AC-7 Gegenprobe: die Messung unterscheidet richtig von falsch.

    GIVEN 24 korrekte `../`-Pfade im Korpus (gemessen 2026-08-14) plus die sonst
          ungemessene Annahme, ein fehlendes `../` schreibe versioniert
    WHEN beides gemessen wird
    THEN faellt keiner der 24 durch (ein Kriterium, das auch die korrekten
         verwirft, macht die Ratsche unbenutzbar), und Git fuehrt unter
         `frontend/docs/artifacts/` wirklich Dateien -- die Praemisse haelt.
    """
    korrekt = [t for t in _schreibpfade() if t[2].startswith("../")]
    assert len(korrekt) >= 24, f"nur {len(korrekt)} korrekte Pfade als Gegenprobe"
    assert not [f"{d}:{n} {p}" for d, n, p in korrekt
                if _im_versionierten_baum(p)[0]], "korrekter Pfad falsch verworfen"
    assert _git("ls-files", "frontend/docs/artifacts").stdout.strip(), (
        "Git fuehrt dort keine Dateien -- dann ist Filter C neu zu begruenden.")
    assert _git("check-ignore", "-q", "docs/artifacts/probe.png").returncode == 0, (
        "Root-'docs/artifacts/' nicht ignoriert -- dann waere auch '../' unsicher.")

@pytest.mark.parametrize("schwelle,eintraege,verstoss,nennt", [
    (36, 38, True, ("36", "38")),          # F006: Liste waechst, Schwelle steht
    (40, 38, True, ()),                    # zu hoch -> blockiert PRs grundlos
    (38, 38, False, ()),                   # gewollter Zustand
    (3, 3, False, ()),                     # Kommentar-/Leerzeilen zaehlen nicht
    (5, 3, True, ()),                      # ... und blaehen die Zahl nicht auf
    (None, 38, True, ("E2E_MIN_SPECS",)),  # fail-closed statt still gruen
])
def test_schwellen_bindung_synthetisch(schwelle, eintraege, verstoss, nennt):
    """AC-6: exakte Bindung in beide Richtungen, mit synthetischen Eingaben.

    GIVEN ein `ci.yml`-Ausschnitt mit (oder ohne) `E2E_MIN_SPECS` und eine Liste
    WHEN `pruefe_schwellen_bindung` darauf laeuft
    THEN meldet sie genau dann einen Verstoss, wenn Schwelle != Eintragszahl:
         `>=` liesse das F006-Loch offen, eine zu hohe Schwelle blockierte jeden
         PR, und stilles Gruen bei fehlender Variable waere der schlimmste Fall.
    """
    ergebnis = pruefe_schwellen_bindung(_synth_ci_yml(schwelle),
                                        _synth_liste(eintraege))
    if not verstoss:
        assert ergebnis == [], f"{schwelle} == {eintraege} Eintraege: {ergebnis}"
        return
    assert ergebnis, f"Schwelle {schwelle} bei {eintraege} Eintraegen muss melden"
    fehlt = [t for t in nennt if t not in " ".join(ergebnis)]
    assert not fehlt, f"Meldung nennt {fehlt} nicht: {ergebnis}"

def test_echte_ci_yml_und_positivliste_sind_exakt_gebunden():
    """AC-6 am Wirkort: die echten Repo-Dateien erfuellen die Bindung.

    GIVEN `ci.yml` und `ci_e2e_specs.txt` im Worktree-Stand (Pfadregel #1409)
    WHEN die Bindung darauf geprueft wird
    THEN meldet sie keinen Verstoss -- der eigentliche Waechter: rot, sobald eine
         PR die Liste erweitert ohne `E2E_MIN_SPECS` nachzuziehen.
    """
    verstoesse = pruefe_schwellen_bindung(CI_YML.read_text(encoding="utf-8"),
                                          POSITIVLISTE.read_text(encoding="utf-8"))
    assert verstoesse == [], "auseinandergelaufen:\n  " + "\n  ".join(verstoesse)
