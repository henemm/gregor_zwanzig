"""Verhaltensnachweis fuer das Commit-Gate „Pendant-Sperre" (#1481 Scheibe B).

Spec: docs/specs/modules/feat_1481b_pendant_gate.md

Eine NEU angelegte Datei in einem einseitigen Bereich (nur Vergleich **oder** nur Trip)
blockiert den Commit — es sei denn, sie liegt im geteilten Bereich oder traegt im Kopf eine
Begruendungszeile `gz-eigenstaendig: <fachlicher Grund>`.

Kern-Schicht, deterministisch: jeder Fall baut ein **Wegwerf-Repository** mit echten Dateien
und ruft den Waechter als echten Unterprozess auf — kein Mock, kein patch(), kein Netz.
Geprueft wird der Exit-Code (2 = blockiert, 0 = durchgelassen) und die Meldung.

Jede Ausnahme wird in BEIDEN Richtungen gemessen: ein Test, der nur den Durchlass prueft, ist
auch dann gruen, wenn der Waechter ueberhaupt nichts blockiert.

Pfadregel #1409: Der Prueflig wird relativ zu DIESER Datei aufgeloest, damit der Test aus einem
Worktree den Worktree-Stand prueft und nicht die Hauptrepo-Kopie.
"""
from __future__ import annotations

import importlib.util as _gz_ilu
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / ".claude" / "hooks"
GATE = HOOKS / "pendant_gate.py"

# Plugin-Sonde (Muster der 9 Hook-Suiten aus #1196 Schnitt 2): pendant_gate.py
# laeuft ueber hook_utils, einen Shim auf das installierte agent-os-openspec-
# Plugin. Ohne Plugin (CI-Runner, Web-Sessions) meldet das Gate fail-open
# "gestoert ... UNGEPRUEFT durchgelassen" (#1307/#1431) — die Block-Tests
# waeren dann strukturell rot. Sauber ueberspringen statt rot; auf dem
# Server (Plugin vorhanden) laeuft die Suite vollstaendig.
_gz_hook_utils = HOOKS / "hook_utils.py"
try:
    _gz_spec = _gz_ilu.spec_from_file_location("_gz_hook_utils_probe", _gz_hook_utils)
    _gz_mod = _gz_ilu.module_from_spec(_gz_spec)
    _gz_spec.loader.exec_module(_gz_mod)
except ImportError as _gz_exc:
    pytest.skip(
        f"agent-os-openspec-Plugin fehlt ({_gz_exc}) — Hook-Suite braucht die "
        "installierten Server-Hooks (#1196)",
        allow_module_level=True,
    )

FE = "frontend/src/lib/components"
RENDERER = "src/output/renderers"
SVELTE = '<script lang="ts">\n</script>\n'
BEGRUENDUNG = (
    "gz-eigenstaendig: Der Orte-Tab hat kein Trip-Gegenstueck, Etappen gibt es dort nicht"
)


# --------------------------------------------------------------------------- Wegwerf-Repo

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _wegwerf_repo(tmp_path: Path, name: str = "repo",
                  bestand: dict[str, str] | None = None) -> Path:
    """Repo mit committetem Ausgangsstand; `bestand` landet im ersten Commit.

    Der echte Commit ist nicht Beiwerk: Der Waechter unterscheidet Neuanlage von Aenderung
    ueber den Vormerk-Stand gegen HEAD. Ohne Ausgangsstand gaebe es nichts zu unterscheiden.
    """
    repo = tmp_path / name
    for ordner in (f"{FE}/compare", f"{FE}/trip-detail", f"{FE}/shared", f"{RENDERER}/email"):
        (repo / ordner).mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("Ausgangsstand\n")
    for pfad, inhalt in (bestand or {}).items():
        ziel = repo / pfad
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")
    return repo


def _neu(repo: Path, pfad: str, inhalt: str = SVELTE) -> None:
    """Neue Datei anlegen und vormerken — genau der Fall, den der Waechter faengt."""
    ziel = repo / pfad
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt)
    _git(repo, "add", "-A")


def _hook(repo: Path, kommando: str = "git commit -m 'x'", gate: Path | None = None,
          umgebung: dict | None = None) -> subprocess.CompletedProcess:
    """Ruft den Waechter wie die Hook-Schicht auf: stdin-JSON, cwd = Wegwerf-Repo."""
    eingabe = json.dumps({"tool_name": "Bash", "tool_input": {"command": kommando}})
    env = dict(os.environ) if umgebung is None else dict(umgebung)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return subprocess.run([sys.executable, str(gate or GATE)], input=eingabe, cwd=str(repo),
                          capture_output=True, text=True, timeout=120, env=env)


def _text(r: subprocess.CompletedProcess) -> str:
    return (r.stderr + r.stdout).lower()


def _blockiert(r: subprocess.CompletedProcess, datei: str, warum: str = "") -> None:
    """Blockade heisst: Exit 2 UND eine Meldung, die die betroffene Datei nennt.

    ⚠️ Exit 2 allein beweist nichts. Fehlt der Waechter, beendet sich der Python-Aufruf selbst
    mit Code 2 („can't open file") — jeder Test, der nur den Code prueft, waere dann gruen,
    obwohl gar nichts geprueft wurde.
    """
    assert r.returncode == 2, f"Sperre haette greifen muessen ({warum}): {r.returncode}\n{r.stderr}"
    assert datei in r.stderr, (
        f"Meldung nennt {datei!r} nicht — ohne sie ist Exit 2 kein Nachweis:\n{r.stderr}")


def _durchlaeuft(r: subprocess.CompletedProcess, warum: str) -> None:
    assert r.returncode == 0, f"Muss durchlaufen ({warum}): Exit {r.returncode}\n{r.stderr}"


# --------------------------------------------------------------------- AC-1/2/3: Grundzusicherung

def test_ac1_neue_einseitige_datei_ohne_begruendung_blockiert(tmp_path):
    """Neue Datei unter `compare/` ohne Begruendungszeile -> Commit bricht ab."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo)
    _blockiert(r, "Ortsliste.svelte", "neue Datei im einseitigen Bereich")
    assert "compare" in _text(r), "Die Meldung muss den Bereich nennen (AC-1):\n" + r.stderr


def test_ac1b_neuer_praefigierter_renderer_blockiert_auch_eine_ebene_tiefer(tmp_path):
    """`renderers/**/compare_*.py` gilt REKURSIV — der bestbelegte Fall liegt tiefer.

    `email/compare_html.py` ist im Code selbst als „analog zu html.py (Trip-Mail)" ausgewiesen.
    Ein Muster, das nur die oberste Renderer-Ebene kennt, verfehlt genau diesen Fall.
    """
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{RENDERER}/email/compare_zusatz.py", "WERT = 1\n")
    _blockiert(_hook(repo), "compare_zusatz.py", "Renderer eine Ebene unter renderers/")


def test_ac2_begruendungszeile_laesst_durch(tmp_path):
    """Dieselbe Datei mit Begruendungszeile im Kopf -> Commit laeuft ohne Rueckfrage."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte",
         f'<script lang="ts">\n  // {BEGRUENDUNG}\n</script>\n')
    _durchlaeuft(_hook(repo), "Begruendungszeile im Kopf")


@pytest.mark.parametrize("zeile", [
    "gz-eigenstaendig: ...",
    "gz-eigenstaendig: kurz",
    # lang, aber ohne einen einzigen sinnvollen Buchstaben: die Pruefung haengt an den
    # Wortzeichen, nicht an der Zeilenlaenge
    "gz-eigenstaendig: ---- .... !!!! ???? ,,,, ;;;; ---- .... !!!! ???? ,,,, ;;;;",
])
def test_ac3_leere_oder_zu_kurze_begruendung_blockiert_weiterhin(tmp_path, zeile):
    """Nur Satzzeichen oder <15 sinnvolle Zeichen zaehlen nicht als Begruendung."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte", f'<script lang="ts">\n  // {zeile}\n</script>\n')
    _blockiert(_hook(repo), "Ortsliste.svelte", f"inhaltsleere Begruendung {zeile!r}")


# ------------------------------------------------- AC-4/5: was den Waechter nichts angeht

@pytest.mark.parametrize("pfad", [
    f"{FE}/shared/NeuerBaustein.svelte",
    # Renderer ohne compare_/trip_-Praefix IST der geteilte Ort — ein `renderers/shared/`
    # gibt es nicht
    f"{RENDERER}/email/spaltenbreite.py",
])
def test_ac4_geteilter_bereich_laesst_jede_neue_datei_durch(tmp_path, pfad):
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, pfad, "WERT = 1\n")
    _durchlaeuft(_hook(repo), f"geteilter Bereich: {pfad}")


def test_ac5_bestandsdatei_bleibt_frei(tmp_path):
    """Vorhandene Datei im einseitigen Bereich aendern -> frei, ohne Begruendung.

    Gegenprobe zu AC-1: gleiche Datei, gleicher Ort — nur eben nicht neu. Ohne diesen Fall
    waere ein Waechter gruen, der jede Beruehrung sperrt und die laufende Arbeit lahmlegt.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/compare/Bestand.svelte": SVELTE})
    (repo / FE / "compare" / "Bestand.svelte").write_text(
        '<script lang="ts">\n  const x = 1;\n</script>\n')
    _git(repo, "add", "-A")
    _durchlaeuft(_hook(repo), "Aenderung an einer Bestandsdatei")


# ------------------------------------------ AC-6: Testdateien haengen an der ENDUNG

def test_ac6_testdatei_direkt_im_bereich_laeuft_durch(tmp_path):
    """Rund die Haelfte der Testdateien liegt direkt neben dem Bauteil, nicht in `__tests__/`."""
    repo = _wegwerf_repo(tmp_path)
    (repo / FE / "compare" / "__tests__").mkdir(parents=True, exist_ok=True)
    _neu(repo, f"{FE}/compare/fooBar.test.ts", "test('x', () => {});\n")
    _durchlaeuft(_hook(repo), "Testdatei direkt im Bereich — eine Ordnerregel wuerde sie sperren")


def test_ac6_gegenprobe_gleiche_datei_ohne_testendung_blockiert(tmp_path):
    """⚠️ Der eigentliche Nachweis: gleicher Ort, gleicher Name, keine Testendung -> 2.

    Ohne diese Gegenprobe waere die Ausnahme auch dann gruen, wenn sie schlicht alles durchliesse.
    """
    repo = _wegwerf_repo(tmp_path)
    (repo / FE / "compare" / "__tests__").mkdir(parents=True, exist_ok=True)
    _neu(repo, f"{FE}/compare/fooBar.ts", "export const wert = 1;\n")
    _blockiert(_hook(repo), "fooBar.ts", "ohne Testendung greift die Ausnahme nicht")


def test_ac6_tests_ordner_bleibt_ebenfalls_ausgenommen(tmp_path):
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/__tests__/hilfen.ts", "export const wert = 1;\n")
    _durchlaeuft(_hook(repo), "__tests__/ ist ausgenommen")


# ------------------------------------------ AC-7/8/9: Verschieben und Umbenennen

def test_ac7_verschiebung_nach_shared_laeuft_auch_ohne_rename_erkennung_durch(tmp_path):
    """Der erwuenschte Weg darf nie blockieren — auch unter der Aehnlichkeitsschwelle.

    Wird beim Verschieben so viel umgeschrieben, dass git daraus Loeschen+Neuanlegen macht,
    sieht der Waechter eine Neuanlage. Weil das ZIEL geteilt ist, laeuft der Commit trotzdem.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/compare/Regler.svelte": SVELTE})
    (repo / FE / "compare" / "Regler.svelte").unlink()
    (repo / FE / "shared" / "Regler.svelte").write_text(
        '<script lang="ts">\n' + "".join(f"  const w{i} = {i};\n" for i in range(40)) + "</script>\n")
    _git(repo, "add", "-A")
    _durchlaeuft(_hook(repo), "Verschiebung in den geteilten Bereich")


def test_ac8_umbenennung_innerhalb_derselben_seite_blockiert_nicht(tmp_path):
    """`compare/Alt.svelte` -> `compare/Neu.svelte`: kein Seitenwechsel, keine Begruendung noetig."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/compare/Alt.svelte": SVELTE})
    _git(repo, "mv", f"{FE}/compare/Alt.svelte", f"{FE}/compare/Neu.svelte")
    _durchlaeuft(_hook(repo), "reines Umbenennen auf derselben Seite")


def test_ac9_seitenwechsel_ohne_begruendung_blockiert(tmp_path):
    """Von `trip-detail/` nach `compare/` — der bequemste Weg an der Sperre vorbei."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/trip-detail/Karte.svelte": SVELTE})
    _git(repo, "mv", f"{FE}/trip-detail/Karte.svelte", f"{FE}/compare/Karte.svelte")
    _blockiert(_hook(repo), "Karte.svelte", "Wechsel von der Gegenseite = wie eine Neuanlage")


def test_ac9_seitenwechsel_mit_begruendung_laeuft_durch(tmp_path):
    """Gegenrichtung zu AC-9: derselbe Wechsel mit Begruendungszeile kommt durch."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/trip-detail/Karte.svelte": SVELTE})
    _git(repo, "mv", f"{FE}/trip-detail/Karte.svelte", f"{FE}/compare/Karte.svelte")
    (repo / FE / "compare" / "Karte.svelte").write_text(
        f'<script lang="ts">\n  // {BEGRUENDUNG}\n</script>\n')
    _git(repo, "add", "-A")
    _durchlaeuft(_hook(repo), "Seitenwechsel mit Begruendung")


# ------------------------------- AC-10: drei Kommentarformen, Fenster erste 20 Zeilen

# ⚠️ Die dritte Form ist die wichtigste: die Python-Renderer haben gemessen ueberhaupt keine
# `#`-Kommentare im Kopf, nur Modul-Docstrings (trip_metric_ids.py:1, trip_report.py:1). Ein
# Ausdruck, der nur `#` kennt, ist dort wirkungslos.
DOCSTRING = ('"""Spaltenbreiten fuer die Vergleichsmatrix.\n\n'
             f'{BEGRUENDUNG}\n"""\nWERT = 1\n')


@pytest.mark.parametrize("pfad,inhalt", [
    (f"{RENDERER}/email/compare_raute.py", f"# {BEGRUENDUNG}\nWERT = 1\n"),
    (f"{FE}/compare/schraeg.ts", f"// {BEGRUENDUNG}\nexport const wert = 1;\n"),
    (f"{RENDERER}/email/compare_docstring.py", DOCSTRING),
])
def test_ac10_alle_drei_kommentarformen_werden_erkannt(tmp_path, pfad, inhalt):
    """`#`, `//` und die blosse Zeile im Modul-Docstring zaehlen gleichermassen."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, pfad, inhalt)
    _durchlaeuft(_hook(repo), f"Kommentarform in {pfad}")


def test_ac10_begruendung_ab_zeile_21_zaehlt_nicht(tmp_path):
    """Gegenprobe zum Fenster: dieselbe Zeile, nur zu weit unten -> blockiert.

    Ohne sie waere ein Waechter gruen, der die ganze Datei durchsucht — dann steht die
    Begruendung irgendwo statt im Kopf und niemand liest sie im Aenderungssatz.
    """
    repo = _wegwerf_repo(tmp_path)
    fueller = "".join(f"WERT_{i} = {i}\n" for i in range(20))
    _neu(repo, f"{RENDERER}/email/compare_spaet.py", fueller + f"# {BEGRUENDUNG}\n")
    _blockiert(_hook(repo), "compare_spaet.py", "Begruendung erst ab Zeile 21")


# AC-12 wurde 2026-08-04 neu gefasst (PO-Entscheidung nach F010): Der Waechter liest den
# Vormerk-Stand NICHT mehr in einem fremden Ordner. Die frueheren Tests dieser Stelle
# — „`-C` liest den Stand dort", „unaufloesbarer Pfad nennt den Grund", „verkettetes `-C`
# folgt der git-Semantik", „`-C` nur aus dem Commit-Abschnitt" — pruefen ein Verhalten,
# das es absichtlich nicht mehr gibt, und sind ersatzlos entfallen. An ihre Stelle treten
# `test_ac12_commit_in_anderen_ordner_wird_benannt_statt_verschwiegen` und
# `test_ac12_der_normalfall_bleibt_vollstaendig_geprueft` weiter unten.


# ---------------------------------------------------- AC-13: eigene Stoerung blockiert nie

def test_ac13_eigene_stoerung_blockiert_nie(tmp_path):
    """Ohne auffindbares `git` kann nichts gemessen werden -> durchlassen und es sagen.

    Nicht theoretisch: In Scheibe A war genau dieser Pfad der einzige CRITICAL-Fund (F007) —
    und er war falsch herum entschieden.
    """
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, umgebung={"PATH": "", "HOME": os.environ.get("HOME", "/tmp")})
    _durchlaeuft(r, "ein defektes Gate darf nicht die Ursache sein, dass niemand mehr committet")
    assert any(w in _text(r) for w in ("stoer", "stör", "ungeprueft", "ungeprüft",
                                       "nicht messbar", "unbekannt")), (
        f"Die Stoerung muss sichtbar gemeldet werden (AC-13). Ausgabe: {_text(r)!r}")


# ------------------------------------------------------------------ AC-14: Pruefdatum

_PRUEFDATUM = re.compile(r"^([A-Z][A-Z_]*)\s*=\s*date\(\s*\d{4}\s*,\s*\d{1,2}\s*,\s*\d{1,2}\s*\)",
                         re.M)


def _gate_kopie(tmp_path: Path, ersatzdatum: str | None = None) -> Path:
    """Lauffaehige Kopie des Waechters, optional mit zurueckgedrehtem Pruefdatum.

    Es gibt kein `faketime` auf diesem Rechner, und der Waechter bekommt keine Test-Hintertuer:
    Statt das Systemdatum zu faelschen, wird die Pruefdatum-Konstante in einer Kopie ersetzt.
    Das misst genau die Zusicherung — dass diese Konstante das Verhalten wirklich steuert.
    """
    binder = tmp_path / "hookbin"
    binder.mkdir(parents=True, exist_ok=True)
    quelle = GATE.read_text()
    if ersatzdatum is not None:
        quelle, treffer = _PRUEFDATUM.subn(lambda m: f"{m.group(1)} = date({ersatzdatum})",
                                           quelle, count=1)
        assert treffer == 1, (
            "Keine Pruefdatum-Konstante der Form `NAME = date(JJJJ, M, T)` gefunden — das "
            "Regel-Budget verlangt ein Pruefdatum im Waechter (AC-14)")
    ziel = binder / "pendant_gate.py"
    ziel.write_text(quelle)
    shutil.copy2(HOOKS / "hook_utils.py", binder / "hook_utils.py")
    return ziel


def test_ac14_nach_dem_pruefdatum_schaltet_sich_der_waechter_ab(tmp_path):
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, gate=_gate_kopie(tmp_path, ersatzdatum="2020, 1, 1"))
    _durchlaeuft(r, "nach dem Pruefdatum darf ein vergessenes Gate niemanden behindern")
    assert "pruefdatum" in _text(r) or "prüfdatum" in _text(r) or "2020-01-01" in _text(r), (
        f"Die Meldung muss auf das abgelaufene Pruefdatum hinweisen: {_text(r)!r}")


def test_ac14_gegenprobe_dieselbe_kopie_blockiert_vor_dem_pruefdatum(tmp_path):
    """⚠️ Ohne diese Gegenprobe waere AC-14 auch dann gruen, wenn die Kopie schlicht kaputt ist."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, gate=_gate_kopie(tmp_path))
    _blockiert(r, "Ortsliste.svelte", "unveraenderte Kopie muss blockieren")


# ------------------------------------- AC-15/16: die Meldung macht die Begruendung konkret

def test_ac15_meldung_nennt_das_vermutete_gegenstueck(tmp_path):
    """`compare/CompareTabs.svelte` neben vorhandener `trip-detail/TripTabs.svelte`."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/trip-detail/TripTabs.svelte": SVELTE})
    _neu(repo, f"{FE}/compare/CompareTabs.svelte")
    r = _hook(repo)
    _blockiert(r, "CompareTabs.svelte", "namensaehnliches Gegenstueck vorhanden")
    assert f"{FE}/trip-detail/TripTabs.svelte" in r.stderr, (
        "Die Meldung muss das vermutete Gegenstueck nennen, damit die Begruendung eine konkrete "
        "Frage beantwortet statt ins Leere zu schreiben (AC-15):\n" + r.stderr)


def test_ac15_gegenprobe_kein_erfundenes_gegenstueck(tmp_path):
    """⚠️ Ohne Gegenstueck wird KEINES genannt — sonst waere ein Waechter gruen, der immer
    irgendetwas nennt und die Meldung damit wertlos macht.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/trip-detail/TripTabs.svelte": SVELTE})
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo)
    _blockiert(r, "Ortsliste.svelte", "kein namensaehnliches Gegenstueck vorhanden")
    erfunden = re.findall(r"trip-detail/[A-Za-z0-9_.-]+\.(?:svelte|ts|py)", r.stderr)
    assert not erfunden, (
        f"Ohne Gegenstueck darf keine Datei der Gegenseite genannt werden: {erfunden}\n{r.stderr}")


def test_ac16_meldung_nennt_beide_auswege(tmp_path):
    """Die Blockade-Meldung nennt geteilten Bereich UND Begruendungszeile."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo)
    _blockiert(r, "Ortsliste.svelte", "blockierter Commit")
    assert "shared/" in r.stderr, "Ausweg 'geteilter Bereich' fehlt (AC-16):\n" + r.stderr
    assert "gz-eigenstaendig:" in r.stderr, "Ausweg 'Begruendungszeile' fehlt (AC-16):\n" + r.stderr


# =========================================================================================
# Nachtrag nach dem Adversary-Lauf (VERDICT BROKEN, Protokoll:
# docs/artifacts/feat-1481-pendant-sperre/adversary-dialog.md)
#
# Jeder Test hier bewacht einen Befund, der zuvor UNGEFANGEN durchging. Sie stehen bewusst
# als eigener Block, damit sichtbar bleibt, welche Zusicherungen erst nachtraeglich einen
# Waechter bekommen haben.
# =========================================================================================

# 40 Zeilen Ausgangsstand; die Neufassung behaelt 19 und ersetzt 21 — „>50 % umgeschrieben".
# Gemessen: git meldet das bei der Voreinstellung (`-M`, 50 % Aehnlichkeit) als D+A und
# erst ab `--find-renames=25%` als `R032`. Die Zahl ist der Grund fuer die Schwelle.
_ALT_LANG = '<script lang="ts">\n' + "".join(f"  const w{i} = {i};\n" for i in range(40)) + "</script>\n"
_NEU_LANG = ('<script lang="ts">\n'
             + "".join(f"  const w{i} = {i};\n" for i in range(19))
             + "".join(f"  let anders{i} = 'voellig neuer inhalt {i}';\n" for i in range(21))
             + "</script>\n")


def _umbenennen(repo: Path, von: str, nach: str, inhalt: str) -> None:
    """Umbenennen MIT starker Inhaltsaenderung — unterhalb der git-Voreinstellung."""
    (repo / von).unlink()
    ziel = repo / nach
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt)
    _git(repo, "add", "-A")


def test_ac8_umbenennung_mit_starkem_umschrieb_verlangt_begruendung(tmp_path):
    """Umbenennen MIT starkem Umschreiben blockiert — bewusst in Kauf genommener Fehlalarm.

    Dieser Test prueft seit der PO-Entscheidung vom 2026-08-04 das GEGENTEIL seiner
    ersten Fassung, und zwar aus einem gemessenen Grund: „aehnlicher Inhalt" und
    „dasselbe Bauteil" sind maschinell nicht dasselbe. Eine unverwandte Loeschung plus
    Neuanlage mit gemeinsamem Svelte-Geruest erreicht bis zu 76 % Aehnlichkeit — genauso
    viel wie eine echte Umbenennung, bei der 8 von 40 Zeilen geaendert wurden. Wer die
    Ausnahme grosszuegig haelt, oeffnet damit einen Weg, jede Neuanlage ungeprueft
    durchzubringen (Adversary-Fund F007).

    Die Wahl faellt deshalb auf die Fehlerrichtung Fehlalarm: die Ausnahme greift nur bei
    praktisch unveraendertem Inhalt. Wer beim Umbenennen viel umschreibt, schreibt eine
    Begruendungszeile — laestig, aber folgenlos. Der umgekehrte Fehler waere folgenreich.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/compare/Alt.svelte": _ALT_LANG})
    _umbenennen(repo, f"{FE}/compare/Alt.svelte", f"{FE}/compare/Neu.svelte", _NEU_LANG)
    _blockiert(_hook(repo), "Neu.svelte", "stark umgeschriebene Umbenennung")


# Unverwandtes Paar mit gemeinsamem Geruest: 6 der 8 Zeilen gleich. Gemessen meldet git
# das als `R061` — eine „Umbenennung", die keine ist.
_GERUEST = ['<script lang="ts">', "  export let titel = '';", "</script>", "", "<div>"]
_ZUFALL_ALT = "\n".join(_GERUEST + [f"  const alt{i} = {i};" for i in range(2)]) + "\n"
_ZUFALL_NEU = "\n".join(_GERUEST + [f"  let neu{i} = 'x{i}';" for i in range(2)]) + "\n"


def _status(repo: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-status", "-M"],
                       capture_output=True, text=True)
    return [z.split("\t")[0] for z in r.stdout.splitlines()]


def test_ac8_zufaellige_aehnlichkeit_gilt_nicht_als_umbenennung(tmp_path):
    """⚠️ Die Umgehung, die F007 aufdeckte: eine Neuanlage als „Umbenennung" tarnen.

    Wird im selben Commit irgendeine Datei derselben Seite geloescht, meldet git die
    Neuanlage als Umbenennung, sobald beide zufaellig genug Zeilen teilen — und jedes
    Svelte-Bauteil beginnt gleich. Die gleichseitige Ausnahme uebersprang die Datei dann
    VOLLSTAENDIG: die neue Doppelung wurde nie geprueft.

    Der Test bestaetigt zuerst, dass git hier wirklich eine Umbenennung meldet. Ohne
    diese Zusicherung liefe er ueber den gewoehnlichen Neuanlage-Pfad und wuerde die
    Luecke gar nicht beruehren — er waere auch dann gruen, wenn die Ausnahme wieder
    beliebig weit aufginge.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/compare/Geloescht.svelte": _ZUFALL_ALT})
    (repo / FE / "compare" / "Geloescht.svelte").unlink()
    (repo / FE / "compare" / "Neuanlage.svelte").write_text(_ZUFALL_NEU)
    _git(repo, "add", "-A")
    kennungen = _status(repo)
    assert any(k.startswith("R") for k in kennungen), (
        f"Aufbau taugt nicht mehr: git meldet keine Umbenennung ({kennungen}) — dann "
        "prueft dieser Test die Luecke ueberhaupt nicht")
    _blockiert(_hook(repo), "Neuanlage.svelte",
               "zufaellige Aehnlichkeit ist keine Umbenennung")


# Die FUENF gemessenen Wege, in einen anderen Projektordner zu committen. Der Waechter
# erkannte genau einen davon — der haeufigste (`cd`) lief lautlos durch (F010).
_WEGE_WOANDERS = [
    ("git -C {b} commit -m x", "minus-C"),
    ("cd {b} && git commit -m x", "cd"),
    ("git --git-dir={b}/.git --work-tree={b} commit -m x", "git-dir"),
    ("GIT_DIR={b}/.git GIT_WORK_TREE={b} git commit -m x", "GIT_DIR-Umgebung"),
    ("(cd {b} && git commit -m x)", "cd-in-Klammern"),
]


@pytest.mark.parametrize("vorlage,kennung", _WEGE_WOANDERS,
                         ids=[k for _, k in _WEGE_WOANDERS])
def test_ac12_commit_in_anderen_ordner_wird_benannt_statt_verschwiegen(tmp_path, vorlage,
                                                                       kennung):
    """F010: Der Waechter prueft seinen EIGENEN Ordner — und sagt, wenn er nicht zustaendig ist.

    Vier Runden lang hat er versucht, aus dem Kommando herauszulesen, WO committet wird
    (F002 -> F006 -> F008 -> F010). Gemessen kannte er am Ende einen von fuenf Wegen; der
    haeufigste — schlicht in den Ordner wechseln — lief lautlos durch. Die Frage „wo wird
    committet?" ist nicht zuverlaessig zu beantworten: Aliase, Skripte, Schleifen, es
    kommen immer neue Wege dazu.

    Beantwortbar ist nur „bin ich hier zustaendig?". Deutet ein Anzeichen auf einen
    anderen Ordner, wird durchgelassen UND gesagt. Aus einer stillen Umgehung wird eine
    benannte Grenze.

    ⚠️ Der Rueckgabewert allein beweist nichts: still durchlassen und benannt durchlassen
    liefern beide 0. Erst die Meldung unterscheidet beides — deshalb wird sie mitgeprueft.
    """
    hier = _wegwerf_repo(tmp_path, name="hier")          # sauber, nichts zu beanstanden
    dort = _wegwerf_repo(tmp_path, name="dort")
    _neu(dort, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(hier, kommando=vorlage.format(b=dort))
    _durchlaeuft(r, f"Commit zielt woanders hin ({kennung})")
    assert "anderen ordner" in _text(r), (
        "Die Grenze muss benannt werden, sonst sieht die Umgehung wie eine Pruefung aus: "
        f"{_text(r)!r}")


# Der Normalfall — hier wird committet, hier MUSS geprueft werden. Zwei Fallen stecken
# darin: ein `-C` im Text der Commit-Nachricht und eines, das zu `grep` gehoert (F011).
_NORMALFAELLE = [
    ("git commit -m 'x'", "schlicht"),
    ("git commit -m 'siehe -C fuer Details'", "minus-C-in-Nachricht"),
    ("git -c user.name=x commit -m 'y'", "kleines-c"),
    ("grep -C 3 muster muster.txt && git commit -m 'x'", "grep-minus-C"),
    ("git commit -am 'x'", "am"),
    ("git commit --amend --no-edit", "amend"),
    ("grep -C 3 muster muster.txt ; timeout 30 git commit -m 'x'", "grep-und-timeout"),
    ("sudo git commit -m 'x'", "sudo"),
]


@pytest.mark.parametrize("kommando,kennung", _NORMALFAELLE,
                         ids=[k for _, k in _NORMALFAELLE])
def test_ac12_der_normalfall_bleibt_vollstaendig_geprueft(tmp_path, kommando, kennung):
    """⚠️ Die Gegenprobe zu F010 — ohne sie waere ein Waechter gruen, der nie mehr prueft.

    Ein Anzeichen-Test, der zu breit greift, legt den haeufigsten Fall still, und das
    faellt niemandem auf: ein Waechter, der nichts mehr blockiert, sieht aus wie einer,
    an dem nichts zu beanstanden ist.

    Zwei der Faelle sind die eigentliche Zumutung: `git commit -m 'siehe -C fuer Details'`
    (das `-C` steht im Text) und `grep -C 3 muster datei && git commit` (das `-C` gehoert
    grep, F011). In beiden wird hier committet. Deshalb zaehlen die Anzeichen nur in einem
    Abschnitt, der auch wirklich `git` aufruft — was VOR `git` steht, ist gleichgueltig.
    """
    repo = _wegwerf_repo(tmp_path)
    (repo / "muster.txt").write_text("muster\n" * 8)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    _blockiert(_hook(repo, kommando=kommando), "Ortsliste.svelte", kennung)


def test_ac12_commit_C_ist_kein_verzeichnis(tmp_path):
    """F012: `git commit -C HEAD` uebernimmt eine Nachricht — es ist kein Verzeichnis.

    Frueher wurde `HEAD` als Pfad gedeutet, nicht aufgeloest und der Commit stillschweigend
    durchgelassen. Jetzt gilt das `-C` als Anzeichen: durchgelassen, aber benannt. Die
    Auslassung ist damit sichtbar statt erfunden.
    """
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, kommando="git commit -C HEAD")
    _durchlaeuft(r, "`-C HEAD` ist ein git-Flag, kein Ordner")
    assert "anderen ordner" in _text(r), (
        f"Auch dieser Fall gehoert benannt statt verschwiegen: {_text(r)!r}")


def test_ac13_fehlende_zerleger_namen_blockieren_nicht(tmp_path):
    """F009: Nicht nur „hook_utils fehlt ganz", auch „nur diese zwei Namen fehlen".

    Der Schutz um `_git_segments`/`_git_subcommand_of_segment` war bisher nur im ersten
    Fall beruehrt. Hausinterne Namen koennen aber einzeln verschwinden — dann darf der
    Waechter nicht raten und nicht abstuerzen, sondern durchlassen und es sagen.
    """
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    binder = tmp_path / "ohne_zerleger"
    binder.mkdir()
    (binder / "pendant_gate.py").write_text(GATE.read_text())
    (binder / "hook_utils.py").write_text(
        "import importlib.util\n"
        f"_spec = importlib.util.spec_from_file_location('_echt', {str(HOOKS / 'hook_utils.py')!r})\n"
        "_modul = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(_modul)\n"
        "globals().update({k: v for k, v in vars(_modul).items() if not k.startswith('__')})\n"
        "del _git_segments\n")
    r = _hook(repo, gate=binder / "pendant_gate.py")
    _durchlaeuft(r, "fehlende Zerleger-Namen sind eine Stoerung, kein Befund")
    assert any(w in _text(r) for w in ("stoer", "stör", "ungeprueft", "ungeprüft",
                                       "nicht messbar", "unbekannt")), (
        f"Die Stoerung muss sichtbar gemeldet werden (AC-13): {_text(r)!r}")


def test_ac9_seitenwechsel_mit_starkem_umschrieb_blockiert(tmp_path):
    """⚠️ Gegenprobe zu F003 — und der Waechter ueber die Umbenennungs-Erkennung (M1).

    Dieselbe Aenderungsgroesse, nur ueber die Seitengrenze: git meldet sie als `R032`,
    also mit einer Aehnlichkeit UNTER 100. Eine Erkennung, die nur `R100` kennt, wuerde
    diese Zeile stillschweigend ignorieren — der Seitenwechsel kaeme durch. Ohne diesen
    Fall waere die Absenkung der Schwelle nur in der durchlassenden Richtung geprueft.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/trip-detail/Karte.svelte": _ALT_LANG})
    _umbenennen(repo, f"{FE}/trip-detail/Karte.svelte", f"{FE}/compare/Karte.svelte", _NEU_LANG)
    _blockiert(_hook(repo), "Karte.svelte", "Seitenwechsel unterhalb der Voreinstellung")


def test_ac9_aus_dem_geteilten_bereich_heraus_blockiert(tmp_path):
    """F005: AC-9 nennt ZWEI Quellen — Gegenseite und geteilter Bereich.

    Aus `shared/` nach `compare/` zu ziehen macht aus geteiltem Code einseitigen; genau
    das soll die Sperre sichtbar machen. Getestet war bisher nur der Weg von der
    Gegenseite.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/shared/Ding.svelte": SVELTE})
    _git(repo, "mv", f"{FE}/shared/Ding.svelte", f"{FE}/compare/Ding.svelte")
    _blockiert(_hook(repo), "Ding.svelte", "geteilt -> einseitig ist wie eine Neuanlage")


def _gate_kopie_mit_ersetzung(tmp_path: Path, ordner: str, alt: str | None = None,
                              neu: str = "", mit_werkzeug: bool = True) -> Path:
    """Lauffaehige Waechter-Kopie, optional mit EINER gezielten Textersetzung."""
    binder = tmp_path / ordner
    binder.mkdir(parents=True, exist_ok=True)
    quelle = GATE.read_text()
    if alt is not None:
        assert alt in quelle, f"Anker {alt!r} nicht mehr im Waechter — Test angleichen"
        quelle = quelle.replace(alt, neu, 1)
    ziel = binder / "pendant_gate.py"
    ziel.write_text(quelle)
    if mit_werkzeug:
        shutil.copy2(HOOKS / "hook_utils.py", binder / "hook_utils.py")
    return ziel


def test_ac13_fehlendes_werkzeugpaket_blockiert_nicht(tmp_path):
    """F001: ohne `hook_utils` gibt es keine Aufrufform-Erkennung -> durchlassen und sagen.

    ⚠️ Der Import stand auf Modulebene, ausserhalb jedes Netzes. Faellt die Aufloesung
    aus, stirbt das Skript mit Rueckgabewert 1, BEVOR das Sicherheitsnetz ueberhaupt
    existiert — und blockiert damit jeden Commit. Genau das verbietet AC-13.

    Ebenso geprueft: es wird NICHT auf eine Wortlaut-Pruefung zurueckgefallen. Ein
    stiller Rueckfall auf `"git commit" in befehl` waere eine Zweitfassung des Defekts,
    den #1431 beseitigt hat.
    """
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    ohne = _gate_kopie_mit_ersetzung(tmp_path, "ohne_werkzeug", mit_werkzeug=False)
    leeres_zuhause = tmp_path / "leeres_zuhause"   # damit auch der Plugin-Shim ins Leere greift
    leeres_zuhause.mkdir()
    r = _hook(repo, gate=ohne, umgebung={"PATH": os.environ.get("PATH", ""),
                                         "HOME": str(leeres_zuhause)})
    assert r.returncode != 1, (
        "Der Waechter ist abgestuerzt statt durchzulassen — genau der Rueckgabewert, der "
        f"jeden Commit blockiert (AC-13):\n{r.stderr}")
    _durchlaeuft(r, "fehlendes Werkzeug-Paket ist eine Stoerung, kein Befund")
    assert any(w in _text(r) for w in ("stoer", "stör", "ungeprueft", "ungeprüft",
                                       "nicht messbar", "unbekannt")), (
        f"Die Stoerung muss sichtbar gemeldet werden (AC-13). Ausgabe: {_text(r)!r}")


def test_ac13_unerwartete_stoerung_landet_im_aeusseren_netz(tmp_path):
    """⚠️ Der Kernbefund F004/M7: das aeusserste Sicherheitsnetz war UNGEPRUEFT.

    Das `try/except` um `main()` liess sich ersatzlos entfernen, ohne dass ein einziger
    Test rot wurde — alle Stoerungstests trafen fruehere, speziellere Zweige (kein `git`,
    unaufloesbarer Pfad, ...). Genau deshalb konnte F001 monatelang unbemerkt entstehen:
    die Zusicherung war dort geprueft, wo der Code STEHT, nicht dort, wo sie WIRKT.

    Dieser Test loest eine Stoerung an einer Stelle aus, die KEIN spezieller Zweig kennt —
    mitten in der Zuschnitt-Pruefung, waehrend echter Arbeit an einem echten Vormerk-Stand.
    """
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    gestoert = _gate_kopie_mit_ersetzung(
        tmp_path, "gestoert",
        alt="    if pfad.endswith(TEST_ENDUNGEN):",
        neu="    raise RuntimeError('kuenstliche Stoerung im Zuschnitt')\n"
            "    if pfad.endswith(TEST_ENDUNGEN):")
    r = _hook(repo, gate=gestoert)
    assert r.returncode != 1, (
        "Die Stoerung ist ungebremst durchgeschlagen — ohne aeusseres Netz blockiert ein "
        f"defekter Waechter jeden Commit (AC-13):\n{r.stderr}")
    _durchlaeuft(r, "ein defektes Gate darf nicht die Ursache sein, dass niemand committet")
    assert any(w in _text(r) for w in ("stoer", "stör", "ungeprueft", "ungeprüft",
                                       "nicht messbar", "unbekannt")), (
        f"Auch die unerwartete Stoerung muss sichtbar werden. Ausgabe: {_text(r)!r}")


# =========================================================================================
# Erweiterte Reichweite: Namenspendants ausserhalb der Ordner-Erkennung
# Spec: docs/specs/modules/feat_2346_cockpit_paritaet.md, Abschnitt „S1 — Pendant-Sperre
# erweitern", AC-2/5/6/7/8.
#
# ⚠️ Alle Pfade dieses Blocks liegen bewusst AUSSERHALB von `FE_BEREICHE` und
# `src/output/renderers` — die alte Ordner-Erkennung faengt sie nicht. Ein Exit 2 hier kann
# also nur von der neuen Namens-Erkennung kommen, ein Exit 0 nicht von einer alten Ausnahme.
# =========================================================================================

MOL = f"{FE}/molecules"
ORG = f"{FE}/organisms"
ROUTES = "frontend/src/routes"
SERVICES = "src/services"
HANDLER = "internal/handler"

_INHALT = {".svelte": SVELTE, ".ts": "export const wert = 1;\n",
           ".py": '"""Modul."""\nWERT = 1\n', ".go": "package handler\n"}
_KOPF = {".svelte": "<!-- {} -->\n", ".ts": "// {}\n", ".py": "# {}\n", ".go": "// {}\n"}


def _endung(pfad: str) -> str:
    return "." + pfad.rsplit(".", 1)[-1]


def _inhalt(pfad: str, kopfzeile: str | None = None) -> str:
    """Lauffaehiger Dateiinhalt passend zur Endung, optional mit Kopfzeile."""
    rumpf = _INHALT[_endung(pfad)]
    return (_KOPF[_endung(pfad)].format(kopfzeile) + rumpf) if kopfzeile else rumpf


# (Kennung, vorhandene Datei = Partner, neue Datei). Deckt alle Namensmuster der Spec ab:
# Praefix CamelCase in beiden Richtungen, Suffix, snake_case (Praefix und Suffix), neutraler
# Partner fuer BEIDE Seiten, lowerCamel und alle vier Wurzeln.
_NAMENSPAARE = [
    ("praefix_compare_neben_trip", f"{MOL}/TripWetterband.svelte", f"{MOL}/CompareWetterband.svelte"),
    ("praefix_trip_neben_compare", f"{MOL}/CompareWetterband.svelte", f"{MOL}/TripWetterband.svelte"),
    ("suffix_compare_neben_trip", f"{ORG}/WetterbandTrip.svelte", f"{ORG}/WetterbandCompare.svelte"),
    ("snake_compare_neben_trip", f"{SERVICES}/trip_wetterlage.py", f"{SERVICES}/compare_wetterlage.py"),
    ("snake_suffix", f"{SERVICES}/wetterlage_trip.py", f"{SERVICES}/wetterlage_compare.py"),
    ("neutral_compare", f"{MOL}/Wetterband.svelte", f"{MOL}/CompareWetterband.svelte"),
    ("neutral_trip_in_routes", f"{ROUTES}/_home/Wetterband.svelte", f"{ROUTES}/_home/TripWetterband.svelte"),
    ("neutral_snake", f"{SERVICES}/wetterlage.py", f"{SERVICES}/compare_wetterlage.py"),
    ("go_handler", f"{HANDLER}/vorschau.go", f"{HANDLER}/compare_vorschau.go"),
    ("lower_camel_ts", f"{ORG}/kanalRaster.ts", f"{ORG}/compareKanalRaster.ts"),
]
_IDS = [k for k, _, _ in _NAMENSPAARE]


def _partner_genannt(r: subprocess.CompletedProcess, partner: str) -> None:
    """Der Partner muss mit vollem Pfad in der Meldung stehen.

    ⚠️ Nur den Dateinamen zu suchen waere vakuum: `Wetterband.svelte` steckt als Teilstring in
    `CompareWetterband.svelte`, `wetterlage.py` in `compare_wetterlage.py` — die Meldung
    naennte dann scheinbar den Partner, obwohl sie nur die neue Datei nennt.
    """
    assert partner in r.stderr, f"Meldung nennt den Partner {partner!r} nicht:\n{r.stderr}"


def _durchlaeuft_sauber(r: subprocess.CompletedProcess, warum: str) -> None:
    """Exit 0 UND kein Stoerungshinweis (Adversary F004).

    ⚠️ Exit 0 allein beweist bei der Namens-Erkennung nichts: Ein im eigenen try/except
    verschluckter Fehler (z. B. KeyError) laesst ebenfalls durch — „sauber" waere dann nur
    ein verschluckter Absturz.
    """
    _durchlaeuft(r, warum)
    assert not any(w in _text(r) for w in _STOERWORTE), (
        f"Durchlass nur wegen einer Stoerung ({warum}):\n{r.stderr}")


@pytest.mark.parametrize("_kennung, partner, neu", _NAMENSPAARE, ids=_IDS)
def test_namenspendant_neuanlage_ohne_begruendung_blockiert_und_nennt_partner(
        tmp_path, _kennung, partner, neu):
    """AC-2: Neue einseitige Datei neben vorhandenem Partner -> Exit 2, Partner genannt."""
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    r = _hook(repo)
    _blockiert(r, neu, f"Namenspendant zu {partner}")
    _partner_genannt(r, partner)


@pytest.mark.parametrize("_kennung, partner, neu", _NAMENSPAARE, ids=_IDS)
def test_namenspendant_mit_begruendungszeile_laeuft_durch(tmp_path, _kennung, partner, neu):
    """AC-2, Ausweg: gueltige `gz-eigenstaendig:`-Kopfzeile -> Exit 0.

    Robustheitswaechter (heute schon gruen): Gegenstueck ist der Blockade-Test oben mit
    denselben Pfaden.
    """
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu, BEGRUENDUNG))
    _durchlaeuft_sauber(_hook(repo), "Begruendungszeile ist der vorgesehene Ausweg")


def test_namenspendant_zu_kurze_begruendung_blockiert(tmp_path):
    """AC-2: Die Kopfzeile braucht >= 15 sinnvolle Zeichen — sonst bleibt es bei Exit 2."""
    partner, neu = f"{MOL}/Wetterband.svelte", f"{MOL}/CompareWetterband.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu, "gz-eigenstaendig: kurz"))
    _blockiert(_hook(repo), neu, "Begruendung unter 15 Zeichen")


def test_namenspendant_meldung_nennt_beide_auswege(tmp_path):
    """Spec S1: Die Meldung nennt Partner UND beide Auswege (shared/neutral bzw. Kopfzeile)."""
    partner, neu = f"{SERVICES}/wetterlage.py", f"{SERVICES}/compare_wetterlage.py"
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    r = _hook(repo)
    _blockiert(r, neu, "Namenspendant")
    assert "shared" in r.stderr, "Ausweg 'geteilt ablegen' fehlt:\n" + r.stderr
    assert "neutral" in _text(r), "Ausweg 'neutral benennen' fehlt:\n" + r.stderr
    assert "gz-eigenstaendig:" in r.stderr, "Ausweg 'Begruendungszeile' fehlt:\n" + r.stderr


def test_namenspendant_partner_im_selben_aenderungssatz_blockiert(tmp_path):
    """Spec S1: Partner zaehlt auch, wenn er im laufenden Aenderungssatz neu hinzukommt."""
    repo = _wegwerf_repo(tmp_path)
    (repo / MOL).mkdir(parents=True, exist_ok=True)
    (repo / f"{MOL}/Wetterband.svelte").write_text(SVELTE)
    _neu(repo, f"{MOL}/CompareWetterband.svelte")
    r = _hook(repo)
    _blockiert(r, f"{MOL}/CompareWetterband.svelte", "Partner im selben Commit")
    _partner_genannt(r, f"{MOL}/Wetterband.svelte")


def test_namenspendant_partner_in_anderem_ordner_blockiert(tmp_path):
    """Spec S1: Partner wird „im Repo" gesucht, nicht nur im selben Ordner."""
    partner, neu = f"{MOL}/Wetterband.svelte", f"{ROUTES}/_home/CompareWetterband.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    r = _hook(repo)
    _blockiert(r, neu, "Partner in anderem Ordner der Reichweite")
    _partner_genannt(r, partner)


@pytest.mark.parametrize("bestand", [
    {f"{MOL}/CompareWetterband.svelte": SVELTE},
    {f"{MOL}/TripWetterband.svelte": SVELTE},
    {f"{MOL}/CompareWetterband.svelte": SVELTE, f"{MOL}/TripWetterband.svelte": SVELTE},
    {f"{SERVICES}/compare_wetterlage.py": '"""m."""\n'},
], ids=["neben_compare", "neben_trip", "neben_beiden", "snake_neben_compare"])
def test_neue_neutrale_datei_neben_einseitiger_loest_nichts_aus(tmp_path, bestand):
    """AC-2, Gegenprobe: neues neutrales `Foo` neben `CompareFoo`/`TripFoo` ist Konvergenz.

    Robustheitswaechter (heute gruen): verhindert, dass die Erkennung symmetrisch auf
    jede Namensgleichheit anschlaegt.
    """
    repo = _wegwerf_repo(tmp_path, bestand=bestand)
    neu = (f"{SERVICES}/wetterlage.py" if any(p.endswith(".py") for p in bestand)
           else f"{MOL}/Wetterband.svelte")
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "neutrale Datei ist die gewuenschte Konvergenz")


def test_namenspendant_andere_endung_ist_kein_partner(tmp_path):
    """Spec S1: Partner nur bei GLEICHER Endung. Gegenstueck: `neutral_compare` oben."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.ts": _inhalt("x.ts")})
    _neu(repo, f"{MOL}/CompareWetterband.svelte")
    _durchlaeuft_sauber(_hook(repo), "`.ts` ist kein Partner fuer `.svelte`")


def test_aenderung_bestehender_einseitiger_datei_neben_partner_bleibt_frei(tmp_path):
    """Spec S1: Nur Neuanlagen. Eine Aenderung an `CompareFoo` neben `Foo` loest nichts aus."""
    neu = f"{MOL}/CompareWetterband.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.svelte": SVELTE, neu: SVELTE})
    (repo / neu).write_text(SVELTE + "<p>geaendert</p>\n")
    _git(repo, "add", "-A")
    _durchlaeuft_sauber(_hook(repo), "Aenderung einer Bestandsdatei ist keine Neuanlage")


def test_namenspendant_echte_umbenennung_bleibt_frei(tmp_path):
    """Spec S1: Umbenennung >= 95 % ist keine Neuanlage — auch nicht AUSSERHALB der Bereiche.

    ⚠️ Ausserhalb von `FE_BEREICHE` landet heute jede Umbenennung in `neuzugaenge` und
    entkommt nur, weil `_bereich` None liefert. Eine naive Namens-Erkennung auf derselben
    Liste wuerde diesen Fall blockieren.
    """
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.svelte": SVELTE,
                                            f"{MOL}/Altband.svelte": _ALT_LANG})
    _git(repo, "mv", f"{MOL}/Altband.svelte", f"{MOL}/CompareWetterband.svelte")
    _durchlaeuft_sauber(_hook(repo), "R100-Umbenennung ist kein neues Bauteil")


def test_namenspendant_umbenennung_mit_umschrieb_blockiert(tmp_path):
    """Spec S1: Umbenennung unter 95 % zaehlt als Neuanlage. Gegenstueck zum Test oben."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.svelte": SVELTE,
                                            f"{MOL}/Altband.svelte": _ALT_LANG})
    _umbenennen(repo, f"{MOL}/Altband.svelte", f"{MOL}/CompareWetterband.svelte", _NEU_LANG)
    r = _hook(repo)
    _blockiert(r, f"{MOL}/CompareWetterband.svelte", "stark umgeschriebene Umbenennung")
    _partner_genannt(r, f"{MOL}/Wetterband.svelte")


# ------------------------------------------------------------------- AC-6: Sonderfaelle

@pytest.mark.parametrize("partner, neu", [
    (f"{MOL}/Wetterband.ts", f"{MOL}/CompareWetterband.test.ts"),
    (f"{MOL}/Wetterband.ts", f"{MOL}/CompareWetterband.spec.ts"),
    (f"{MOL}/Wetterband.ts", f"{MOL}/__tests__/CompareWetterband.ts"),
    (f"{SERVICES}/wetterlage.py", f"{SERVICES}/tests/compare_wetterlage.py"),
], ids=["test_ts", "spec_ts", "__tests__", "tests_ordner"])
def test_namenspendant_testdatei_laeuft_durch(tmp_path, partner, neu):
    """AC-6: Testdateien loesen nie aus. Robustheitswaechter; Gegenprobe direkt darunter."""
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "Testdatei")


def test_namenspendant_gegenprobe_gleiche_datei_ohne_testendung_blockiert(tmp_path):
    """AC-6, Gegenprobe: `CompareFoo.ts` neben `Foo.ts` (ohne Testendung) -> Exit 2."""
    partner, neu = f"{MOL}/Wetterband.ts", f"{MOL}/CompareWetterband.ts"
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    r = _hook(repo)
    _blockiert(r, neu, "dieselbe Datei ohne Testendung")
    _partner_genannt(r, partner)


@pytest.mark.parametrize("partner, neu", [
    (f"{MOL}/Trip.svelte", f"{MOL}/Compare.svelte"),
    (f"{SERVICES}/trip.py", f"{SERVICES}/compare.py"),
], ids=["svelte", "snake"])
def test_leerer_kernname_loest_nichts_aus(tmp_path, partner, neu):
    """AC-6: `Compare.svelte` neben `Trip.svelte` — leerer Kernname ist kein Pendant.

    Der Partner liegt bewusst vor: ohne ihn waere der Test auch bei einer Erkennung gruen,
    die leere Kernnamen faelschlich vergleicht.
    """
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "leerer Kernname")


@pytest.mark.parametrize("partner, neu", [
    ("frontend/src/lib/utils/Wetterband.ts", "frontend/src/lib/utils/CompareWetterband.ts"),
    ("src/app/wetterlage.py", "src/app/compare_wetterlage.py"),
    ("internal/store/vorschau.go", "internal/store/compare_vorschau.go"),
], ids=["fe_utils", "src_app", "internal_store"])
def test_namenspendant_ausserhalb_der_vier_wurzeln_loest_nichts_aus(tmp_path, partner, neu):
    """AC-6: ausserhalb der vier Wurzeln -> Exit 0.

    Gegenproben mit denselben Namen INNERHALB der Wurzeln: `lower_camel_ts`/`neutral_snake`/
    `go_handler` in `test_namenspendant_neuanlage_ohne_begruendung_blockiert_und_nennt_partner`.
    """
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "ausserhalb der Reichweite")


# ----------------------------------------------------- AC-7: Stoerung blockiert nie

_NAMENS_AUSLOESER = (f"{MOL}/Wetterband.svelte", f"{MOL}/CompareWetterband.svelte")
_STOERWORTE = ("stoer", "stör", "ungeprueft", "ungeprüft", "nicht messbar", "unbekannt",
               "ungueltig", "ungültig")


def _gate_mit_kaputter_namenspendant(tmp_path: Path) -> Path:
    """Kopie, in der `_namenspendant()` bei jedem Aufruf eine Ausnahme wirft.

    Die Neudefinition steht direkt vor `if __name__ == "__main__":` und gewinnt damit zur
    Laufzeit — unabhaengig von der echten Signatur. ⚠️ Vorbedingung: Die Funktion muss im
    Original existieren. Sonst ueberschriebe die Kopie eine Funktion, die niemand aufruft,
    und der Test „Ordner-Erkennung blockiert weiter" waere fuer immer gruen.
    """
    spec = _gz_ilu.spec_from_file_location("_pendant_gate_namenspendant_sonde", GATE)
    modul = _gz_ilu.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert callable(getattr(modul, "_namenspendant", None)), (
        "`_namenspendant()` fehlt im Waechter (Spec #2346 S1) — Namens-Erkennung nicht da")
    return _gate_kopie_mit_ersetzung(
        tmp_path, "kaputte_namenspendant",
        alt='\nif __name__ == "__main__":',
        neu="\ndef _namenspendant(*_a, **_k):\n"
            "    raise RuntimeError('kuenstliche Stoerung in _namenspendant')\n\n\n"
            'if __name__ == "__main__":')


def test_stoerung_in_namenspendant_laesst_durch_und_meldet(tmp_path):
    """AC-7: Ausnahme in `_namenspendant()` -> Exit 0 mit Hinweis auf stderr."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    r = _hook(repo, gate=_gate_mit_kaputter_namenspendant(tmp_path))
    _durchlaeuft(r, "Stoerung der Namens-Erkennung ist kein Befund")
    assert any(w in _text(r) for w in _STOERWORTE), f"Stoerung nicht gemeldet: {_text(r)!r}"


def test_stoerung_in_namenspendant_laesst_ordner_erkennung_weiter_blockieren(tmp_path):
    """AC-7: Die Stoerung darf die alte Ordner-Erkennung NICHT mitreissen.

    ⚠️ Ohne diesen Fall waere „Exit 0 bei Stoerung" auch durch das aeussere Netz erfuellt —
    das liesse dann aber auch den echten Ordner-Befund `compare/Ortsliste.svelte` durch.
    """
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, gate=_gate_mit_kaputter_namenspendant(tmp_path))
    _blockiert(r, "Ortsliste.svelte", "Ordner-Erkennung trotz gestoerter Namens-Erkennung")


def test_fehlendes_werkzeug_mit_namenspendant_laesst_durch(tmp_path):
    """AC-7: ohne `hook_utils` auch bei vorliegendem Namenspendant Exit 0. Robustheitswaechter."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    ohne = _gate_kopie_mit_ersetzung(tmp_path, "ohne_werkzeug_namen", mit_werkzeug=False)
    leer = tmp_path / "leeres_zuhause_namen"
    leer.mkdir()
    r = _hook(repo, gate=ohne, umgebung={"PATH": os.environ.get("PATH", ""), "HOME": str(leer)})
    _durchlaeuft(r, "fehlendes Werkzeug-Paket")
    assert any(w in _text(r) for w in _STOERWORTE), f"Stoerung nicht gemeldet: {_text(r)!r}"


def test_kein_git_mit_namenspendant_laesst_durch(tmp_path):
    """AC-7: ohne `git` auch bei vorliegendem Namenspendant Exit 0. Robustheitswaechter."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    r = _hook(repo, umgebung={"PATH": "", "HOME": os.environ.get("HOME", "/tmp")})
    _durchlaeuft(r, "kein git")
    assert any(w in _text(r) for w in _STOERWORTE), f"Stoerung nicht gemeldet: {_text(r)!r}"


def test_ungueltige_eingabe_laesst_durch_mit_hinweis(tmp_path):
    """AC-7: ungueltige Eingabe -> Exit 0 MIT Hinweis auf stderr (heute: still)."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    r = subprocess.run([sys.executable, str(GATE)], input="{kein json", cwd=str(repo),
                       capture_output=True, text=True, timeout=120)
    _durchlaeuft(r, "ungueltige Eingabe")
    assert any(w in _text(r) for w in _STOERWORTE), (
        f"AC-7 verlangt einen Hinweis auf stderr auch bei ungueltiger Eingabe: {_text(r)!r}")


# ------------------------------------------------------------ AC-8: Pruefdatum 2027-01-21

def _gate_am_tag(tmp_path: Path, tag: str) -> Path:
    """Kopie, die `date.today()` durch einen festen Tag ersetzt — PRUEFDATUM bleibt ECHT.

    Bewusst NICHT `_gate_kopie(ersatzdatum)`: der schreibt PRUEFDATUM selbst um und koennte
    damit nie pruefen, welches Datum im Waechter steht.
    """
    return _gate_kopie_mit_ersetzung(tmp_path, f"tag_{tag.replace(', ', '_')}",
                                     alt="date.today()", neu=f"date({tag})")


def test_pruefdatum_letzter_gueltiger_tag_blockiert(tmp_path):
    """AC-8: Am 2027-01-21 ist das Gate noch scharf (Ordner-Ausloeser -> Exit 2)."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, gate=_gate_am_tag(tmp_path, "2027, 1, 21"))
    _blockiert(r, "Ortsliste.svelte", "letzter Tag vor Ablauf des Pruefdatums 2027-01-21")


def test_pruefdatum_tag_danach_schaltet_ab_und_nennt_datum(tmp_path):
    """AC-8: Am 2027-01-22 schaltet sich das Gate ab und nennt das Pruefdatum 2027-01-21."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    r = _hook(repo, gate=_gate_am_tag(tmp_path, "2027, 1, 22"))
    _durchlaeuft(r, "nach Ablauf des Pruefdatums")
    assert "2027-01-21" in r.stderr, f"Meldung muss das Pruefdatum nennen:\n{r.stderr}"


def test_pruefdatum_konstante_lautet_2027_01_21():
    """AC-8: `PRUEFDATUM` im Waechter lautet 2027-01-21."""
    from datetime import date
    spec = _gz_ilu.spec_from_file_location("_pendant_gate_pruefdatum", GATE)
    modul = _gz_ilu.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.PRUEFDATUM == date(2027, 1, 21), modul.PRUEFDATUM


# doc-compliance-test — die folgenden zwei Tests lesen ausschliesslich die Doku
# docs/reference/gates_und_ratschen.md (AC-8 verlangt Doku-Zeilen), keinen Quelltext.
_GATES_DOKU = REPO / "docs" / "reference" / "gates_und_ratschen.md"


def _doku_abschnitt_pendant_sperre() -> str:
    text = _GATES_DOKU.read_text()
    treffer = re.search(r"^## Pendant-Sperre.*?(?=^## )", text, flags=re.M | re.S)
    assert treffer, "Abschnitt „## Pendant-Sperre“ fehlt in gates_und_ratschen.md"
    return treffer.group(0)


def test_doku_abschnitt_pendant_sperre_nennt_reichweite_ausnahmeliste_und_beleg():
    """AC-8: Abschnitt nennt Reichweite, Ausnahmeliste, Verlaengerung und Beleg."""
    abschnitt = _doku_abschnitt_pendant_sperre()
    for wurzel in ("frontend/src/routes", "src/services", "internal/handler"):
        assert wurzel in abschnitt, f"Reichweite {wurzel!r} fehlt im Abschnitt"
    assert "BEKANNTE_PAARE" in abschnitt, "Ausnahmeliste `BEKANNTE_PAARE` fehlt"
    assert "verlängert 2026-10-23, PO" in abschnitt, "Verlaengerungsvermerk fehlt"
    assert "#2346" in abschnitt, "Verweis auf Spec #2346 fehlt"
    assert "2027-01-21" in abschnitt, "neues Pruefdatum fehlt im Abschnitt"
    # Korrigiert 2026-10-24 auf den nachgemessenen Stand (Adversary F003): 8 statt 7 Paare.
    assert re.search(r"(\b8\b|acht)[^\n]{0,80}au(ß|ss)erhalb", abschnitt), (
        "Beleg „8 Paare ausserhalb der alten Reichweite“ fehlt")


def test_doku_pruefdaten_tabelle_traegt_2027_01_21_mit_beleg():
    """AC-8: Zeile „Pendant-Sperre" der Pruefdaten-Tabelle: neues Datum, Vermerk, Beleg."""
    zeilen = [z for z in _GATES_DOKU.read_text().splitlines() if z.startswith("| Pendant-Sperre")]
    assert len(zeilen) == 1, f"genau eine Tabellenzeile erwartet, gefunden: {zeilen}"
    spalten = [s.strip() for s in zeilen[0].strip("|").split("|")]
    assert "2027-01-21" in spalten[1], spalten
    assert "2026-11-03" not in spalten[1], spalten
    assert "verlängert 2026-10-23, PO" in zeilen[0] and "#2346" in zeilen[0], zeilen[0]
    assert spalten[2] not in ("", "—", "-"), f"Fang-Beleg fehlt weiterhin: {spalten}"


# ------------------------------------------- AC-5: Bestand ohne Fehlalarm (Wegwerf-Repo)

# (einseitige Datei, Partner) — die acht Bestandspaare ausserhalb der alten Reichweite
# (das achte, trip_forecast/forecast, nachgemessen 2026-10-24, Adversary F003),
# genau die Eintraege von `BEKANNTE_PAARE` (Spec #2346 S1). Die Verhaltenstests nehmen nur
# Paare, deren Dateien es im echten Repo noch gibt — loescht S2/S3 ein Paar, faellt es hier
# von selbst heraus (AC-3: Streichen bleibt gruen).
_BESTANDSPAARE = [
    (f"{ORG}/HomeHeroCompare.svelte", f"{ORG}/HomeHeroTrip.svelte"),
    (f"{ROUTES}/_home/CompareKachel.svelte", f"{ROUTES}/_home/TripKachel.svelte"),
    (f"{SERVICES}/compare_alert.py", f"{SERVICES}/trip_alert.py"),
    (f"{SERVICES}/compare_alert_channels.py", f"{SERVICES}/alert_channels.py"),
    (f"{SERVICES}/compare_preview_service.py", f"{SERVICES}/preview_service.py"),
    (f"{SERVICES}/compare_weather_snapshot.py", f"{SERVICES}/weather_snapshot.py"),
    (f"{FE}/shared/weather-metrics-tab/compareChannelMetricLayouts.ts",
     f"{FE}/shared/weather-metrics-tab/channelMetricLayouts.ts"),
    (f"{SERVICES}/trip_forecast.py", f"{SERVICES}/forecast.py"),
]
# Paare/Dateien, die die alte Ordner-Erkennung bereits kennt, plus die geteilte Datei.
_BESTAND_UEBRIGE = [
    f"{FE}/compare/CompareTabs.svelte", f"{FE}/trip-detail/TripTabs.svelte",
    f"{FE}/compare-new/CompareNewEditor.svelte", f"{FE}/trip-new/TripNewEditor.svelte",
    f"{FE}/shared/CompareOutlookLayoutControls.svelte",
]
_ALLE_BESTAND = [p for paar in _BESTANDSPAARE for p in paar] + _BESTAND_UEBRIGE


def _lebende_bestandspaare() -> list[tuple[str, str]]:
    """Bestandspaare, deren beide Dateien im echten Repo noch existieren."""
    paare = [paar for paar in _BESTANDSPAARE if all((REPO / p).is_file() for p in paar)]
    if not paare:
        pytest.skip("Alle Bestandspaare aufgeloest — nichts mehr auszunehmen")
    return paare


def _bestandsinhalt(pfad: str) -> str:
    """Eindeutiger, laengerer Inhalt je Datei — damit git Umbenennungen nicht verwechselt."""
    kommentar = "#" if pfad.endswith(".py") else "//"
    return "".join(f"{kommentar} Bestand {pfad} Zeile {i}\n" for i in range(12))


def test_bestand_aenderung_loest_keinen_fehlalarm_aus(tmp_path):
    """AC-5: Aenderung aller Bestandsdateien -> Exit 0. Robustheitswaechter."""
    repo = _wegwerf_repo(tmp_path, bestand={p: _bestandsinhalt(p) for p in _ALLE_BESTAND})
    for p in _ALLE_BESTAND:
        (repo / p).write_text(_bestandsinhalt(p) + "// geaendert\n")
    _git(repo, "add", "-A")
    _durchlaeuft_sauber(_hook(repo), "Aenderung von Bestandsdateien")


def test_bestand_verschiebung_loest_keinen_fehlalarm_aus(tmp_path):
    """AC-5: Verschieben aller Bestandsdateien (R100) -> Exit 0. Robustheitswaechter."""
    repo = _wegwerf_repo(tmp_path, bestand={p: _bestandsinhalt(p) for p in _ALLE_BESTAND})
    for p in _ALLE_BESTAND:
        ordner, name = p.rsplit("/", 1)
        (repo / ordner / "verschoben").mkdir(exist_ok=True)
        _git(repo, "mv", p, f"{ordner}/verschoben/{name}")
    _durchlaeuft_sauber(_hook(repo), "Verschiebung mit unveraendertem Inhalt")


@pytest.mark.parametrize("richtung", ["einseitig_neu", "partner_neu"])
def test_bestandspaar_mitglied_mitfuehren_loest_keinen_fehlalarm_aus(tmp_path, richtung):
    """AC-5: Ein Bestandspaar-Mitglied kommt im Commit (wieder) hinzu -> Exit 0.

    Genau dieser Fall wird nur von `BEKANNTE_PAARE` ausgenommen: Fehlt die Liste oder greift
    sie nicht, meldet die Namens-Erkennung jedes dieser Paare. Robustheitswaechter heute;
    Gegenprobe `test_bestand_gegenprobe_unbekanntes_paar_blockiert_selektiv`.

    ⚠️ Wird ein Eintrag aus `BEKANNTE_PAARE` gestrichen, dessen Dateien es noch gibt, wird
    dieser Test absichtlich rot: das waere ein echter Fehlalarm nach AC-5.
    """
    paare = _lebende_bestandspaare()
    vorhanden = [paar[1] if richtung == "einseitig_neu" else paar[0] for paar in paare]
    neu = [paar[0] if richtung == "einseitig_neu" else paar[1] for paar in paare]
    repo = _wegwerf_repo(tmp_path, bestand={p: _bestandsinhalt(p) for p in vorhanden})
    for p in neu:
        _neu(repo, p, _bestandsinhalt(p))
    _durchlaeuft_sauber(_hook(repo), "gelistete Bestandspaare sind ausgenommen")


def test_bestand_gegenprobe_unbekanntes_paar_blockiert_selektiv(tmp_path):
    """AC-5, Gegenprobe: Dieselbe Lage plus ein NICHT gelistetes Paar -> Exit 2, nur dieses.

    Beweist, dass die Ausnahme selektiv wirkt und die Namens-Erkennung in dieser Lage aktiv ist.
    """
    paare = _lebende_bestandspaare()
    vorhanden = [paar[1] for paar in paare] + [f"{SERVICES}/routenlage.py"]
    repo = _wegwerf_repo(tmp_path, bestand={p: _bestandsinhalt(p) for p in vorhanden})
    for p, _ in paare:
        _neu(repo, p, _bestandsinhalt(p))
    _neu(repo, f"{SERVICES}/compare_routenlage.py", _bestandsinhalt("compare_routenlage.py"))
    r = _hook(repo)
    _blockiert(r, f"{SERVICES}/compare_routenlage.py", "nicht gelistetes Namenspaar")
    for p, _ in paare:
        assert p not in r.stderr, f"Gelistetes Bestandspaar {p!r} faelschlich gemeldet:\n{r.stderr}"


# ----------------------------------------------- Fix-Loop 1 (Adversary-Funde F001-F007)

@pytest.mark.parametrize("nachbar, neu", [
    (f"{MOL}/Hoehenprofil.svelte", f"{MOL}/CompareWetterband.svelte"),
    (f"{MOL}/TripHoehenprofil.svelte", f"{MOL}/CompareWetterband.svelte"),
    (f"{SERVICES}/routenlage.py", f"{SERVICES}/compare_wetterlage.py"),
], ids=["neutral_unverwandt", "gegenseite_unverwandt", "snake_unverwandt"])
def test_namenspendant_unverwandter_nachbar_gleicher_endung_loest_nichts_aus(
        tmp_path, nachbar, neu):
    """F001: Nur der gleiche KERNNAME macht ein Paar — nicht Endung und Wurzel allein.

    Gegenstueck: `test_namenspendant_neuanlage_ohne_begruendung_blockiert_und_nennt_partner`.
    Ohne diesen Fall waere „Kernname nicht verglichen" (Dauer-Fehlalarm) unbemerkt.
    """
    repo = _wegwerf_repo(tmp_path, bestand={nachbar: _inhalt(nachbar)})
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "unverwandter Nachbar ist kein Partner")


def test_namenspendant_partner_derselben_seite_ist_kein_pendant(tmp_path):
    """F004: `CompareFoo` neben `CompareFoo` (anderer Ordner) ist keine Trip/Compare-Doppelung."""
    nachbar, neu = f"{MOL}/CompareWetterband.svelte", f"{ORG}/CompareWetterband.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={nachbar: SVELTE})
    _neu(repo, neu)
    _durchlaeuft_sauber(_hook(repo), "Partner derselben Seite")


def test_namenspendant_testdatei_neben_testdatei_laeuft_durch(tmp_path):
    """F005: `CompareFoo.test.ts` neben `Foo.test.ts` — gleiche Endungs-Partition.

    Hier rettet NUR der Testdatei-Ausschluss: die Endung `test.ts` ist auf beiden Seiten gleich.
    """
    partner, neu = f"{MOL}/Wetterband.test.ts", f"{MOL}/CompareWetterband.test.ts"
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt("x.ts")})
    _neu(repo, neu, _inhalt("x.ts"))
    _durchlaeuft_sauber(_hook(repo), "Testdatei neben Testdatei")


def test_namenspendant_umlaut_im_namen_blockiert(tmp_path):
    """F007: git quotet Umlaut-Pfade standardmaessig — das darf nicht still durchlassen."""
    partner, neu = f"{MOL}/Übersicht.svelte", f"{MOL}/CompareÜbersicht.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    r = _hook(repo)
    _blockiert(r, neu, "Umlaut im Dateinamen")
    _partner_genannt(r, partner)


def test_ordner_erkennung_umlaut_im_namen_blockiert(tmp_path):
    """F007, Nebenwirkung des Fixes: auch die Ordner-Erkennung sieht Umlaut-Pfade jetzt."""
    repo = _wegwerf_repo(tmp_path)
    _neu(repo, f"{FE}/compare/Übersicht.svelte")
    _blockiert(_hook(repo), "Übersicht.svelte", "Umlaut im einseitigen Bereich")


def test_ordner_pfad_mit_namenspendant_ergibt_genau_einen_meldungsblock(tmp_path):
    """F002 (a): Pfade der Ordner-Bereiche meldet nur die Ordner-Erkennung — keine Doppelung."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/trip-detail/TripWetterband.svelte": SVELTE})
    _neu(repo, f"{FE}/compare/CompareWetterband.svelte")
    r = _hook(repo)
    _blockiert(r, "CompareWetterband.svelte", "Ordner-Erkennung")
    assert r.stderr.count("PENDANT-SPERRE") == 1, f"Doppelte Meldung:\n{r.stderr}"


def test_mischfall_ordner_und_namens_treffer_zeigt_beide_bloecke(tmp_path):
    """F002 (b): Ordner-Treffer + Namens-Treffer im selben Commit -> beide Meldungen."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.svelte": SVELTE})
    _neu(repo, f"{FE}/compare/Ortsliste.svelte")
    _neu(repo, f"{MOL}/CompareWetterband.svelte")
    r = _hook(repo)
    _blockiert(r, "Ortsliste.svelte", "Ordner-Treffer im Mischfall")
    _blockiert(r, f"{MOL}/CompareWetterband.svelte", "Namens-Treffer im Mischfall")
    _partner_genannt(r, f"{MOL}/Wetterband.svelte")
    assert "#1481 B" in r.stderr and "#2346" in r.stderr, f"Ein Block fehlt:\n{r.stderr}"


# 40 Zeilen; die Neufassung behaelt 28 und ersetzt 12 — git meldet das als R0xx um 70 %.
_MITTEL_NEU = ('<script lang="ts">\n'
               + "".join(f"  const w{i} = {i};\n" for i in range(28))
               + "".join(f"  let anders{i} = 'neu {i}';\n" for i in range(12))
               + "</script>\n")


def test_namenspendant_umbenennung_um_70_prozent_blockiert(tmp_path):
    """F002 (c): Umbenennung zwischen git-Schwelle (50 %) und 95 % zaehlt als Neuanlage."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.svelte": SVELTE,
                                            f"{MOL}/Altband.svelte": _ALT_LANG})
    _umbenennen(repo, f"{MOL}/Altband.svelte", f"{MOL}/CompareWetterband.svelte", _MITTEL_NEU)
    status = [s for s in _status(repo) if s.startswith("R")]
    assert status and 50 <= int(status[0][1:]) < 95, f"Vorbedingung R50-R94 verfehlt: {status}"
    r = _hook(repo)
    _blockiert(r, f"{MOL}/CompareWetterband.svelte", "Umbenennung um 70 %")
    _partner_genannt(r, f"{MOL}/Wetterband.svelte")


@pytest.mark.parametrize("nachbar, neu", [
    (f"{MOL}/Index.svelte", f"{MOL}/CompareUVIndex.svelte"),
    (f"{MOL}/Wetter.svelte", f"{MOL}/CompareWetter2.svelte"),
    ("src/servicesalt/wetterlage.py", "src/servicesalt/compare_wetterlage.py"),
    ("src/app/wetterlage.py", f"{SERVICES}/compare_wetterlage.py"),
], ids=["akronym", "ziffer", "wurzel_nur_als_praefix", "partner_ausser_reichweite"])
def test_namenspendant_randfaelle_loesen_nichts_aus(tmp_path, nachbar, neu):
    """F006: Akronym und Ziffer gehoeren zum Kernnamen; Wurzel heisst Ordner, nicht Praefix;
    ein Partner ausserhalb der Reichweite zaehlt nicht."""
    repo = _wegwerf_repo(tmp_path, bestand={nachbar: _inhalt(nachbar)})
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "Randfall")


# ----------------------------------------------- Fix-Loop 2 (Adversary-Funde F009-F015)

def _hundert(geaendert: int) -> str:
    """100 Zeilen, davon die letzten `geaendert` ersetzt. Gemessen (git -M): 4 -> R096, 6 -> R094."""
    return ('<script lang="ts">\n'
            + "".join(f"  const w{i} = {i};\n" for i in range(100 - geaendert))
            + "".join(f"  let x{i} = {i};\n" for i in range(geaendert)) + "</script>\n")


def _umbenennung_neben_partner(tmp_path: Path, geaendert: int) -> tuple[Path, int]:
    neu = f"{MOL}/CompareWetterband.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Wetterband.svelte": SVELTE,
                                            f"{MOL}/Altband.svelte": _hundert(0)})
    _umbenennen(repo, f"{MOL}/Altband.svelte", neu, _hundert(geaendert))
    status = [s for s in _status(repo) if s.startswith("R")]
    assert status, f"git meldet keine Umbenennung: {_status(repo)}"
    return repo, int(status[0][1:])


def test_umbenennung_knapp_ueber_95_prozent_bleibt_frei(tmp_path):
    """F010: R96 (kleine Aenderung beim Verschieben) gilt als echte Umbenennung -> Exit 0.

    Pinnt `ECHTE_UMBENENNUNG` nach oben: jede Grenze > 96 macht diesen Test rot.
    """
    repo, aehnlichkeit = _umbenennung_neben_partner(tmp_path, 4)
    assert 96 <= aehnlichkeit <= 99, f"Vorbedingung R96-R99 verfehlt: R{aehnlichkeit}"
    _durchlaeuft_sauber(_hook(repo), f"Umbenennung R{aehnlichkeit}")


def test_umbenennung_genau_95_prozent_bleibt_frei(tmp_path):
    """F016: R095 liegt AUF der Grenze und gilt noch als echte Umbenennung -> Exit 0."""
    repo, aehnlichkeit = _umbenennung_neben_partner(tmp_path, 5)
    assert aehnlichkeit == 95, f"Vorbedingung R095 verfehlt: R{aehnlichkeit}"
    _durchlaeuft_sauber(_hook(repo), "Umbenennung R095")


def test_ordner_umbenennung_genau_95_prozent_bleibt_frei(tmp_path):
    """F016: dieselbe Grenze in der Ordner-Erkennung — R095 auf derselben Seite -> Exit 0."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{FE}/compare/Alt.svelte": _hundert(0)})
    _umbenennen(repo, f"{FE}/compare/Alt.svelte", f"{FE}/compare/Neu.svelte", _hundert(5))
    status = [s for s in _status(repo) if s.startswith("R")]
    assert status == ["R095"], f"Vorbedingung R095 verfehlt: {_status(repo)}"
    _durchlaeuft_sauber(_hook(repo), "Ordner-Umbenennung R095")


@pytest.mark.parametrize("nachbar, neu", [
    (f"{MOL}/CardList.svelte", f"{MOL}/CompareCard.svelte"),
    (f"{MOL}/Card.svelte", f"{MOL}/CompareCardList.svelte"),
], ids=["kern_ist_teil_des_nachbarn", "nachbar_ist_teil_des_kerns"])
def test_namenspendant_teilstring_des_kernnamens_ist_kein_partner(tmp_path, nachbar, neu):
    """F017: Der Kernname muss GLEICH sein, Enthaltensein in eine Richtung genuegt nicht."""
    repo = _wegwerf_repo(tmp_path, bestand={nachbar: SVELTE})
    _neu(repo, neu)
    _durchlaeuft_sauber(_hook(repo), "Teilstring ist kein Paar")


def test_umbenennung_knapp_unter_95_prozent_blockiert(tmp_path):
    """F010: R94 zaehlt als Neuanlage -> Exit 2. Pinnt die Grenze nach unten (<= 94 rot)."""
    repo, aehnlichkeit = _umbenennung_neben_partner(tmp_path, 6)
    assert 90 <= aehnlichkeit <= 94, f"Vorbedingung R90-R94 verfehlt: R{aehnlichkeit}"
    r = _hook(repo)
    _blockiert(r, f"{MOL}/CompareWetterband.svelte", f"Umbenennung R{aehnlichkeit}")
    _partner_genannt(r, f"{MOL}/Wetterband.svelte")


@pytest.mark.parametrize("partner, neu", [
    (f"{HANDLER}/state_test.go", f"{HANDLER}/compare_state_test.go"),
    (f"{SERVICES}/test_wetterlage.py", f"{SERVICES}/test_wetterlage_compare.py"),
], ids=["go_test", "pytest_konvention"])
def test_namenspendant_go_und_pytest_testdateien_laufen_durch(tmp_path, partner, neu):
    """F009: `*_test.go` und `test_*.py` sind Testdateien. Gegenprobe: `go_handler` oben."""
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    _durchlaeuft_sauber(_hook(repo), "Testdatei nach Go-/pytest-Konvention")


def test_stoerung_vormerk_stand_nicht_lesbar_laesst_durch_und_meldet(tmp_path):
    """F015: kaputter Index -> `git diff --cached` scheitert -> Exit 0 mit Stoerungshinweis."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    (repo / ".git" / "index").write_bytes(b"kein git-index")
    r = _hook(repo)
    _durchlaeuft(r, "Vormerk-Stand nicht lesbar")
    assert "vormerk-stand nicht lesbar" in _text(r), f"Stoerung nicht gemeldet: {_text(r)!r}"


@pytest.mark.parametrize("grund, blockiert", [
    ("abcdefghijklmn", True),     # 14 sinnvolle Zeichen
    ("abcdefghijklmno", False),   # 15
], ids=["14_zeichen", "15_zeichen"])
def test_namenspendant_begruendung_grenze_15_zeichen(tmp_path, grund, blockiert):
    """F011: genau 15 sinnvolle Zeichen genuegen, 14 nicht."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu, _inhalt(neu, f"gz-eigenstaendig: {grund}"))
    r = _hook(repo)
    if blockiert:
        _blockiert(r, neu, "14 Zeichen")
    else:
        _durchlaeuft_sauber(r, "15 Zeichen")


@pytest.mark.parametrize("zeile, blockiert", [(20, False), (21, True)], ids=["zeile_20", "zeile_21"])
def test_namenspendant_begruendung_grenze_kopfzeilen(tmp_path, zeile, blockiert):
    """F011: Kopfzeile in Zeile 20 zaehlt, in Zeile 21 nicht."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    inhalt = "".join(f"<!-- z{i} -->\n" for i in range(1, zeile)) + f"<!-- {BEGRUENDUNG} -->\n"
    _neu(repo, neu, inhalt)
    r = _hook(repo)
    if blockiert:
        _blockiert(r, neu, "Begruendung in Zeile 21")
    else:
        _durchlaeuft_sauber(r, "Begruendung in Zeile 20")


def test_namenspendant_marker_gross_kleinschreibung_egal(tmp_path):
    """F011: Der Marker wird ohne Ruecksicht auf Gross-/Kleinschreibung erkannt (`.lower()`)."""
    partner, neu = _NAMENS_AUSLOESER
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu, _inhalt(neu, BEGRUENDUNG.replace("gz-eigenstaendig:", "GZ-Eigenstaendig:")))
    _durchlaeuft_sauber(_hook(repo), "Marker in Grossschreibung")


def test_namenspendant_akzent_gehoert_zum_kernnamen(tmp_path):
    """F014: `CompareÉtat` neben `Tat` ist kein Paar — das É gehoert zum Kernnamen."""
    repo = _wegwerf_repo(tmp_path, bestand={f"{MOL}/Tat.svelte": SVELTE})
    _neu(repo, f"{MOL}/CompareÉtat.svelte")
    _durchlaeuft_sauber(_hook(repo), "Akzentbuchstabe im Kernnamen")


@pytest.mark.parametrize("partner, neu", [
    (f"{MOL}/WetterUV.svelte", f"{MOL}/WetterUVCompare.svelte"),
    (f"{SERVICES}/wetter2.py", f"{SERVICES}/wetter2compare.py"),
], ids=["akronym_vor_suffix", "ziffer_vor_suffix"])
def test_namenspendant_suffix_nach_akronym_oder_ziffer_blockiert(tmp_path, partner, neu):
    """F006/F014: Wortgrenze auch zwischen Akronym bzw. Ziffer und `Compare`-Suffix."""
    repo = _wegwerf_repo(tmp_path, bestand={partner: _inhalt(partner)})
    _neu(repo, neu, _inhalt(neu))
    r = _hook(repo)
    _blockiert(r, neu, "Suffix nach Akronym/Ziffer")
    _partner_genannt(r, partner)


def test_namenspendant_akzent_gegenprobe_blockiert(tmp_path):
    """F014, Gegenprobe: `CompareÉtat` neben `État` ist ein Paar -> Exit 2."""
    partner, neu = f"{MOL}/État.svelte", f"{MOL}/CompareÉtat.svelte"
    repo = _wegwerf_repo(tmp_path, bestand={partner: SVELTE})
    _neu(repo, neu)
    r = _hook(repo)
    _blockiert(r, neu, "Akzent-Paar")
    _partner_genannt(r, partner)
