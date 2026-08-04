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
