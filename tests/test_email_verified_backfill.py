"""TDD RED — Issue #2304 (S1 aus #2271/#2146, Epic #2138): Nachtrag-Skript,
das Bestandskonten ohne `email_verified_at` als bestaetigt nachtraegt.

Spec: docs/specs/modules/email_verify_vorbereitung_2304.md — AC-1, AC-2, AC-3.

Geprueft wird das ECHTE Skript `scripts/backfill_2271_email_verified.py` als
eigener Prozess gegen einen echten Dateibaum unter `tmp_path`. Keine Mocks,
keine Stellvertreter: was der Test misst, ist der Dateibestand vor und nach dem
Lauf.

RED heute: das Skript existiert noch nicht -> `returncode != 0`. Genau deshalb
prueft JEDER Test zuerst den Rueckgabewert. Ohne diese Reihenfolge waere
besonders AC-3 ("nichts veraendert") trivial gruen, solange gar nichts
passiert — ein Test, der das Fehlen der Funktion als Erfolg verbucht.

Das Skript wird relativ zur eigenen Testdatei aufgeloest, nie ueber einen
festen Hauptrepo-Pfad — sonst gruente der Test aus dem falschen Checkout.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKRIPT = REPO_ROOT / "scripts" / "backfill_2271_email_verified.py"


def _profil(uid: str, **overrides) -> dict:
    """Ein reichhaltiges Profil — Trips, Empfaenger, Passwort-Hash und ein dem
    Skript unbekanntes Feld. Letzteres faengt ein Replace statt eines
    Read-Modify-Write-Merge."""
    profil = {
        "id": uid,
        "display_name": f"Konto {uid}",
        "email": f"{uid}@beispiel.de",
        "mail_to": f"{uid}-empfang@beispiel.de",
        "password_hash": "$2a$10$abcdefghijklmnopqrstuv.WXYZ0123456789abcdefghijklmn",
        "tier": "standard",
        "telegram_chat_id": "123456789",
        "trips": ["gr20-2026", "khw-2026"],
        "empfaenger": [f"{uid}@beispiel.de", "zweit@beispiel.de"],
        "created_at": "2025-11-03T08:15:00Z",
        "dem_skript_unbekanntes_feld": {"tief": ["verschachtelt", 42]},
    }
    profil.update(overrides)
    return profil


def _zusatzdateien(uid: str) -> dict[str, str]:
    """Alles, was ein echtes Konto ausser `user.json` unter seinem Verzeichnis
    traegt — in Produktion nachgewiesen: `trips/`, `briefings/`, `gpx/`.

    Der Inhalt traegt die Konto-ID, damit eine Sicherung auffaellt, die zwar
    Dateien mitnimmt, sie aber vertauscht oder aus einem anderen Konto
    befuellt.
    """
    return {
        "trips/gr20-2026.json": json.dumps(
            {"id": "gr20-2026", "owner": uid, "stages": [{"name": "Calenzana"}]},
            indent=2,
        ),
        "briefings/2026-08-24.txt": f"Briefing fuer {uid} am 2026-08-24\nGewitter ab 14 Uhr.\n",
        "gpx/etappe-01.gpx": f'<?xml version="1.0"?>\n<gpx creator="{uid}"><trk/></gpx>\n',
    }


def _konto_anlegen(root: Path, uid: str, **overrides) -> Path:
    pfad = root / uid / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(_profil(uid, **overrides), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    for rel, inhalt in _zusatzdateien(uid).items():
        datei = root / uid / rel
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(inhalt, encoding="utf-8")
    return pfad


def _lauf(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SKRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )


def _erfolg(ergebnis: subprocess.CompletedProcess, ac: str) -> None:
    assert ergebnis.returncode == 0, (
        f"{ac}: das Nachtrag-Skript {SKRIPT} muss mit 0 enden, "
        f"Rueckgabewert {ergebnis.returncode}.\nstdout:\n{ergebnis.stdout}\nstderr:\n{ergebnis.stderr}"
    )


def _laden(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


# --- AC-1 -------------------------------------------------------------------


def test_execute_traegt_bestaetigung_nach_und_laesst_alles_andere_unveraendert(tmp_path):
    """AC-1: `email_verified_at` kommt hinzu, ALLE uebrigen Felder stehen
    danach feldweise unveraendert da — verglichen wird das vollstaendige
    restliche Profil-Dict, nicht eine Handvoll ausgewaehlter Felder."""
    root = tmp_path / "users"
    pfad = _konto_anlegen(root, "henning")
    vorher = _laden(pfad)
    assert "email_verified_at" not in vorher, "AC-1 Ausgangslage: Feld darf noch nicht existieren"

    ergebnis = _lauf(root, "--execute")
    _erfolg(ergebnis, "AC-1")

    nachher = _laden(pfad)
    assert nachher.get("email_verified_at"), (
        "AC-1: nach dem --execute-Lauf muss das Konto einen email_verified_at-Zeitstempel tragen, "
        f"Profil ist aber: {nachher}"
    )

    rest = {k: v for k, v in nachher.items() if k != "email_verified_at"}
    assert rest == vorher, (
        "AC-1: alle uebrigen Felder muessen unveraendert bleiben (Read-Modify-Write-Merge).\n"
        f"vorher:  {vorher}\nnachher: {rest}"
    )


# --- AC-2 -------------------------------------------------------------------


def test_zweiter_execute_lauf_laesst_zeitstempel_wertgleich(tmp_path):
    """AC-2: Idempotenz. Geprueft wird der WERT des Zeitstempels, nicht bloss
    'ist weiterhin gesetzt'.

    Die Beweislast traegt Konto B: es haelt bereits einen weit
    zurueckliegenden Zeitstempel, ein stilles Ueberschreiben faellt dort
    sofort auf — unabhaengig davon, wann der Test laeuft. Konto A prueft
    denselben Wert ueber beide Laeufe hinweg mit; es traegt den Nachweis
    bewusst NICHT allein, weil das Skriptvorbild sekundengenau stempelt und
    zwei Laeufe innerhalb derselben Sekunde denselben String ergaeben. Eine
    Wartezeit als Ausgleich waere ein Test, dessen Aussage an der Uhr haengt
    (vgl. #2186).
    """
    root = tmp_path / "users"
    pfad_a = _konto_anlegen(root, "henning")
    alt = "2020-01-01T00:00:00Z"
    pfad_b = _konto_anlegen(root, "steffi", email_verified_at=alt)

    erster = _lauf(root, "--execute")
    _erfolg(erster, "AC-2 (erster Lauf)")
    nach_erstem = _laden(pfad_a).get("email_verified_at")
    assert nach_erstem, f"AC-2: erster Lauf muss henning stempeln, Profil: {_laden(pfad_a)}"

    zweiter = _lauf(root, "--execute")
    _erfolg(zweiter, "AC-2 (zweiter Lauf)")

    nach_zweitem = _laden(pfad_a).get("email_verified_at")
    assert nach_zweitem == nach_erstem, (
        "AC-2: ein zweiter --execute-Lauf darf einen bereits gesetzten Zeitstempel nicht "
        f"veraendern: nach Lauf 1 {nach_erstem!r}, nach Lauf 2 {nach_zweitem!r}"
    )
    assert _laden(pfad_b).get("email_verified_at") == alt, (
        "AC-2: ein vorbestehender Zeitstempel muss wertgleich erhalten bleiben, "
        f"erwartet {alt!r}, gefunden {_laden(pfad_b).get('email_verified_at')!r}"
    )


# --- AC-3 -------------------------------------------------------------------


_ZU_AENDERN = re.compile(r"^\s*Zu aktualisieren \((\d+)\): (\[.*\])\s*$", re.MULTILINE)
_UEBERSPRUNGEN = re.compile(r"^\s*Uebersprungen \((\d+)\): (\[.*\])\s*$", re.MULTILINE)


def _plan_aus_stdout(stdout: str) -> tuple[set[str], set[str]]:
    """Liest die beiden Plan-Listen GETRENNT aus der Ausgabe des Skripts.

    Warum nicht einfach `uid in stdout`: ein blosser Vorkommens-Test kann die
    beiden Listen nicht auseinanderhalten. Ein Skript, das ein zu aenderndes
    Konto faelschlich als uebersprungen meldet, benennt es ja trotzdem — es
    bestuende den Test, waehrend genau dieser Probelauf die
    Entscheidungsgrundlage fuer den echten Lauf gegen die Produktivdaten ist.
    Geprueft wird deshalb die ZUORDNUNG Konto -> Liste.

    Gemessen wird gegen die Struktur, die das Skript ohnehin ausgibt
    (`  Zu aktualisieren (N): [...]` / `  Uebersprungen (N): [...]`,
    `backfill_2271_email_verified.py:101-103`) — das Skript wird nicht
    umgebaut, damit der Test bequemer wird.

    Uebersprungene Eintraege tragen eine Begruendung in Klammern
    (`"steffi (email_verified_at bereits gesetzt)"`); zurueckgegeben wird nur
    die Konto-ID davor, damit beide Mengen vergleichbar sind.
    """
    mengen: list[set[str]] = []
    for name, muster in (("Zu aktualisieren", _ZU_AENDERN), ("Uebersprungen", _UEBERSPRUNGEN)):
        treffer = muster.search(stdout)
        assert treffer is not None, (
            f"AC-3: die Ausgabe muss eine Zeile '{name} (N): [...]' enthalten — nur so ist die "
            f"Zuordnung Konto -> Liste ueberhaupt ablesbar.\nstdout:\n{stdout}"
        )
        eintraege = ast.literal_eval(treffer.group(2))
        assert len(eintraege) == int(treffer.group(1)), (
            f"AC-3: die genannte Anzahl der Liste '{name}' passt nicht zu ihrem Inhalt: "
            f"{treffer.group(1)} angekuendigt, {len(eintraege)} aufgezaehlt.\nstdout:\n{stdout}"
        )
        mengen.append({str(e).split(" (", 1)[0] for e in eintraege})
    return mengen[0], mengen[1]


def test_dry_run_veraendert_keine_datei_und_ordnet_die_konten_richtig_zu(tmp_path):
    """AC-3: ohne `--execute` wird keine einzige Datei veraendert, und die
    Ausgabe ordnet jedes Konto der RICHTIGEN Liste zu.

    Der Nachweis haengt an der Zuordnung, nicht am blossen Vorkommen des
    Namens: die drei unbestaetigten Konten muessen in der 'Zu aktualisieren'-
    Liste stehen und in KEINER der beiden anderen Rollen auftauchen, das
    bereits bestaetigte Konto genau umgekehrt. Beide Mengen werden vollstaendig
    verglichen — so faellt auch ein zusaetzlicher oder fehlender Eintrag auf.
    """
    root = tmp_path / "users"
    unbestaetigt = ["henning", "steffi", "m-aabbccdd"]
    bereits = "m-99ffeedd"
    schon_gestempelt = "2020-01-01T00:00:00Z"
    pfade = {uid: _konto_anlegen(root, uid) for uid in unbestaetigt}
    pfade[bereits] = _konto_anlegen(root, bereits, email_verified_at=schon_gestempelt)
    vorher_bytes = {uid: p.read_bytes() for uid, p in pfade.items()}

    ergebnis = _lauf(root)
    _erfolg(ergebnis, "AC-3")

    # Keine Datei angefasst — auch nicht die des uebersprungenen Kontos.
    for uid, p in pfade.items():
        assert p.read_bytes() == vorher_bytes[uid], (
            f"AC-3: der Probelauf hat {p} veraendert — ohne --execute darf keine Datei angefasst werden"
        )
    for uid in unbestaetigt:
        assert "email_verified_at" not in _laden(pfade[uid]), (
            f"AC-3: der Probelauf hat {uid} gestempelt"
        )
    assert _laden(pfade[bereits]).get("email_verified_at") == schon_gestempelt, (
        f"AC-3: der Probelauf hat den vorbestehenden Zeitstempel von {bereits} veraendert"
    )

    zu_aendern, uebersprungen = _plan_aus_stdout(ergebnis.stdout)
    assert zu_aendern == set(unbestaetigt), (
        "AC-3: die 'Zu aktualisieren'-Liste muss genau die Konten ohne email_verified_at nennen — "
        f"erwartet {sorted(unbestaetigt)}, gemeldet {sorted(zu_aendern)}.\nstdout:\n{ergebnis.stdout}"
    )
    assert uebersprungen == {bereits}, (
        f"AC-3: uebersprungen werden darf allein das bereits bestaetigte Konto {bereits!r} — "
        f"gemeldet {sorted(uebersprungen)}.\nstdout:\n{ergebnis.stdout}"
    )


# --- Spec "Side effects": tar.gz-Sicherung ----------------------------------
#
# Die Sicherung ist das Netz unter einem Lauf, der genau zweimal stattfindet:
# einmal gegen Produktion, einmal gegen 63 Staging-Konten (CLAUDE.md,
# "Daten-Schema-Reworks (PFLICHT!)" / BUG-DATALOSS-GR221 #102). Ein Waechter,
# der nur die EXISTENZ des Archivs prueft, wuerde eine nach der Aenderung
# geschriebene Sicherung durchwinken — die waere wertlos, weil sie genau den
# Stand konserviert, vor dem sie schuetzen soll. Geprueft wird deshalb der
# INHALT: das Archiv muss den Baum tragen, wie er VOR dem Lauf aussah.


def _archiv_profile(archiv: Path) -> dict[str, dict]:
    """Liest alle `<root>/<uid>/user.json` aus dem tar.gz — Rueckgabe uid -> Profil.

    Gelesen wird der volle Mitgliedspfad, nicht nur sein Ende: eine Sicherung,
    die statt des ganzen Baums nur das geaenderte Konto einpackt, traegt andere
    Mitgliedspfade und faellt damit auf.
    """
    profile: dict[str, dict] = {}
    with tarfile.open(archiv, "r:gz") as tar:
        for member in tar.getmembers():
            teile = Path(member.name).parts
            if len(teile) != 3 or teile[2] != "user.json":
                continue
            datei = tar.extractfile(member)
            assert datei is not None, f"Archivmitglied {member.name} ist nicht lesbar"
            profile[f"{teile[0]}/{teile[1]}"] = json.loads(datei.read().decode("utf-8"))
    return profile


def _baum_bytes(root: Path) -> dict[str, bytes]:
    """Jede regulaere Datei unterhalb von `root`, Schluessel wie der
    Mitgliedspfad im Archiv (`<root.name>/<uid>/...`), Wert der volle Inhalt."""
    return {
        str(p.relative_to(root.parent)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _archiv_bytes(archiv: Path) -> dict[str, bytes]:
    """Dasselbe Bild aus dem tar.gz — Mitgliedspfad -> tatsaechlich
    gespeicherter Inhalt. Nicht nur die Namen: ein Archiv, das die Pfade
    fuehrt, sie aber leer speichert, faellt hier auf."""
    gelesen: dict[str, bytes] = {}
    with tarfile.open(archiv, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isreg():
                continue
            datei = tar.extractfile(member)
            assert datei is not None, f"Archivmitglied {member.name} ist nicht lesbar"
            gelesen[member.name] = datei.read()
    return gelesen


def test_execute_sichert_den_stand_vor_der_aenderung(tmp_path):
    """Spec 'Side effects': ein `--execute`-Lauf mit Arbeit legt genau eine
    tar.gz-Sicherung an, und deren Inhalt traegt den Stand VOR dem Lauf.

    Konto A (wird geaendert) muss im Archiv noch OHNE `email_verified_at`
    liegen; Konto B (wird uebersprungen) muss wertgleich mit seinem
    vorbestehenden Zeitstempel darin liegen. Beide Profile werden vollstaendig
    gegen den Ausgangszustand verglichen.

    Positivkontrolle: nach dem Lauf traegt A im Dateibaum einen Zeitstempel.
    Ohne sie waere 'im Archiv fehlt das Feld' fuer ein Skript, das ueberhaupt
    nichts tut, trivial gruen.
    """
    root = tmp_path / "users"
    alt = "2020-01-01T00:00:00Z"
    pfad_a = _konto_anlegen(root, "henning")
    pfad_b = _konto_anlegen(root, "steffi", email_verified_at=alt)
    vorher_a = _laden(pfad_a)
    vorher_b = _laden(pfad_b)
    vorher_baum = _baum_bytes(root)
    zusatz = sorted(k for k in vorher_baum if not k.endswith("/user.json"))
    assert zusatz, (
        "Testvoraussetzung: die Konten muessen Inhalte ausserhalb von user.json tragen "
        "(trips/, briefings/, gpx/) — sonst prueft die Archiv-Gegenprobe unten nur "
        "Profile, und eine Verengung der Sicherung auf */user.json bliebe unentdeckt."
    )
    backup_dir = tmp_path / "sicherungen"

    ergebnis = _lauf(root, "--backup-dir", str(backup_dir), "--execute")
    _erfolg(ergebnis, "Side effects (Sicherung)")

    # Positivkontrolle: der Lauf hat wirklich gearbeitet.
    assert _laden(pfad_a).get("email_verified_at"), (
        "Positivkontrolle: der --execute-Lauf muss henning gestempelt haben, "
        f"Profil ist aber: {_laden(pfad_a)}"
    )
    assert _laden(pfad_b).get("email_verified_at") == alt, (
        "Positivkontrolle: steffis vorbestehender Zeitstempel muss unangetastet bleiben"
    )

    archive = sorted(backup_dir.glob("*.tar.gz"))
    assert len(archive) == 1, (
        "Side effects: ein --execute-Lauf mit Arbeit muss genau EINE tar.gz-Sicherung "
        f"in {backup_dir} anlegen, gefunden: {[p.name for p in archive]}.\n"
        f"stdout:\n{ergebnis.stdout}"
    )

    gesichert = _archiv_profile(archive[0])
    assert set(gesichert) == {f"{root.name}/henning", f"{root.name}/steffi"}, (
        "Side effects: die Sicherung muss den vollstaendigen --root-Baum tragen "
        f"(erwartet beide Konten unter {root.name}/), gefunden: {sorted(gesichert)}"
    )

    profil_a = gesichert[f"{root.name}/henning"]
    assert "email_verified_at" not in profil_a, (
        "Side effects: die Sicherung muss den Stand VOR dem Lauf tragen — henning liegt "
        "darin aber bereits gestempelt. Eine nach der Aenderung geschriebene Sicherung "
        f"schuetzt vor nichts. Archiviertes Profil: {profil_a}"
    )
    assert profil_a == vorher_a, (
        "Side effects: das gesicherte Profil muss dem Ausgangszustand entsprechen.\n"
        f"vorher:    {vorher_a}\ngesichert: {profil_a}"
    )
    assert gesichert[f"{root.name}/steffi"] == vorher_b, (
        "Side effects: auch das uebersprungene Konto muss unveraendert in der Sicherung "
        f"liegen.\nvorher:    {vorher_b}\ngesichert: {gesichert[f'{root.name}/steffi']}"
    )

    # Der ganze Baum, nicht nur die Profile: ein echtes Konto traegt Trips,
    # Briefings und GPX-Spuren. Eine Sicherung, die davon nichts (oder nur
    # leere Huellen) enthaelt, waere im Ernstfall wertlos — deshalb wird der
    # Archivinhalt byteweise gegen den Stand vor dem Lauf gestellt, statt nur
    # Pfadnamen abzuhaken. Die Erwartung wird vom Dateibaum abgelesen, nie als
    # Literal gesetzt.
    archiviert = _archiv_bytes(archive[0])
    assert archiviert == vorher_baum, (
        "Side effects: die Sicherung muss den VOLLEN --root-Baum inhaltlich tragen "
        "(Trips, Briefings, GPX — nicht nur user.json).\n"
        f"nur im Baum:   {sorted(set(vorher_baum) - set(archiviert))}\n"
        f"nur im Archiv: {sorted(set(archiviert) - set(vorher_baum))}\n"
        "inhaltlich abweichend: "
        f"{sorted(k for k in set(vorher_baum) & set(archiviert) if vorher_baum[k] != archiviert[k])}"
    )


def test_dry_run_legt_keine_sicherung_an(tmp_path):
    """Spec 'Side effects' (Kehrseite): ein Probelauf schreibt keine Sicherung —
    weder in das angegebene noch in das Standard-Verzeichnis. Sonst wuerde jeder
    Probelauf das Backup-Verzeichnis zumuellen."""
    root = tmp_path / "users"
    _konto_anlegen(root, "henning")
    _konto_anlegen(root, "steffi")
    backup_dir = tmp_path / "sicherungen"
    standard_dir = root.parent / ".backups"

    ergebnis = _lauf(root, "--backup-dir", str(backup_dir))
    _erfolg(ergebnis, "Side effects (Dry-Run)")

    for verzeichnis in (backup_dir, standard_dir):
        gefunden = sorted(verzeichnis.glob("*.tar.gz")) if verzeichnis.is_dir() else []
        assert not gefunden, (
            f"Side effects: ein Probelauf darf keine Sicherung anlegen, in {verzeichnis} "
            f"liegt aber: {[p.name for p in gefunden]}"
        )
