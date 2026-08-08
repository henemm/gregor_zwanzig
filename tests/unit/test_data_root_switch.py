"""Prueft das Umschalt-Werkzeug fuer die Datenwurzel (Issue #1595, Scheibe 1).

Dieses Werkzeug verschiebt Live-Datenbaeume. Bevor es Staging anfasst, muss es
selbst geprueft sein — und zwar an einem Wegwerf-Baum, nie an echten Daten.

Kein Netz, keine Mocks: echte Dateisystem-Operationen unter ``tmp_path``. Das
Verhalten, um das es geht, IST Dateisystem-Verhalten; ein Mock davon wuerde nur
die eigene Annahme zurueckspiegeln.
"""

import os
from pathlib import Path

import pytest

from scripts.data_root_switch import (
    compare_fingerprints,
    detect_regrowth,
    fingerprint,
    rollback,
    switch,
)


def _make_tree(root: Path) -> None:
    """Legt einen Baum an, der die echte Struktur nachbildet."""
    (root / "users" / "alice").mkdir(parents=True)
    (root / "users" / "bob").mkdir(parents=True)
    (root / "cache").mkdir(parents=True)
    (root / "users" / "alice" / "user.json").write_text('{"id":"alice"}')
    (root / "users" / "bob" / "user.json").write_text('{"id":"bob"}')
    (root / "cache" / "wetter.json").write_text("[]")


# --- AC-5: Unversehrtheits-Nachweis, beide Richtungen -----------------------
#
# Ein Pruefer, der immer "veraendert" meldet, ist genauso wertlos wie einer,
# der immer Entwarnung gibt. Deshalb wird BEIDES geprueft.


def test_fingerprint_meldet_keine_abweichung_wenn_nichts_passiert(tmp_path):
    """GIVEN unveraenderter Baum / WHEN zweimal erfasst / THEN keine Abweichung."""
    root = tmp_path / "data"
    _make_tree(root)

    assert compare_fingerprints(fingerprint(root), fingerprint(root)) == []


def test_fingerprint_erkennt_geaenderten_inhalt(tmp_path):
    """GIVEN erfasster Baum / WHEN Dateiinhalt geaendert / THEN Abweichung gemeldet."""
    root = tmp_path / "data"
    _make_tree(root)
    vorher = fingerprint(root)

    (root / "users" / "alice" / "user.json").write_text('{"id":"alice","tier":"free"}')

    abweichungen = compare_fingerprints(vorher, fingerprint(root))
    assert abweichungen, "geaenderter Inhalt wurde nicht bemerkt"
    assert any("users/alice/user.json" in a for a in abweichungen)


def test_fingerprint_erkennt_neue_datei(tmp_path):
    """GIVEN erfasster Baum / WHEN Datei ergaenzt / THEN Abweichung gemeldet."""
    root = tmp_path / "data"
    _make_tree(root)
    vorher = fingerprint(root)

    (root / "users" / "carol").mkdir(parents=True)
    (root / "users" / "carol" / "user.json").write_text('{"id":"carol"}')

    abweichungen = compare_fingerprints(vorher, fingerprint(root))
    assert any("users/carol/user.json" in a for a in abweichungen)


def test_fingerprint_erkennt_geloeschte_datei(tmp_path):
    """GIVEN erfasster Baum / WHEN Datei geloescht / THEN Abweichung gemeldet."""
    root = tmp_path / "data"
    _make_tree(root)
    vorher = fingerprint(root)

    (root / "users" / "bob" / "user.json").unlink()

    abweichungen = compare_fingerprints(vorher, fingerprint(root))
    assert any("users/bob/user.json" in a for a in abweichungen)


@pytest.mark.skipif(os.geteuid() == 0, reason="root darf alles lesen — Test waere wirkungslos")
def test_fingerprint_scheitert_laut_bei_unlesbarer_datei(tmp_path):
    """GIVEN eine unlesbare Datei / WHEN erfasst / THEN Fehler statt stiller Luecke.

    Der Fehler vom 2026-08-07 in Reinform: Ein Werkzeug, das unlesbare Dateien
    ueberspringt, liefert ein unvollstaendiges Ergebnis, das wie ein
    vollstaendiges aussieht. Genau so entstuende eine Sicherung, die den
    entscheidenden Datensatz nicht enthaelt.
    """
    root = tmp_path / "data"
    _make_tree(root)
    gesperrt = root / "users" / "alice" / "user.json"
    gesperrt.chmod(0o000)

    try:
        with pytest.raises(PermissionError):
            fingerprint(root)
    finally:
        gesperrt.chmod(0o600)


# --- AC-6: Rueckbau stellt den Ausgangszustand her --------------------------


def test_rollback_stellt_baum_identisch_wieder_her(tmp_path):
    """GIVEN umgeschalteter Baum / WHEN Rueckbau / THEN Inhalt identisch zu vorher."""
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    vorher = fingerprint(quelle)
    ziel = tmp_path / "var" / "gregor"

    switch(quelle, ziel, mode="absent")
    assert not quelle.exists(), "alter Ort muss nach dem Umschalten weg sein"

    rollback(quelle, ziel)

    assert compare_fingerprints(vorher, fingerprint(quelle)) == []
    assert not ziel.exists(), "Zielort muss nach dem Rueckbau geraeumt sein"


def test_rollback_raeumt_auch_die_sperrdatei_weg(tmp_path):
    """GIVEN Stufe-B-Sperre am alten Ort / WHEN Rueckbau / THEN Baum wieder da."""
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    vorher = fingerprint(quelle)
    ziel = tmp_path / "var" / "gregor"

    switch(quelle, ziel, mode="file")
    assert quelle.is_file(), "Stufe B muss eine DATEI am alten Ort hinterlassen"

    rollback(quelle, ziel)

    assert quelle.is_dir()
    assert compare_fingerprints(vorher, fingerprint(quelle)) == []


# --- AC-2: Stufe B macht Zugriffe laut statt still --------------------------


def test_stufe_b_laesst_zugriff_mit_notadirectory_scheitern(tmp_path):
    """GIVEN Sperrdatei am alten Ort / WHEN Zugriff auf data/... / THEN NotADirectoryError.

    Das ist der ganze Zweck von Stufe B: Ein Leser, der den alten relativen
    Pfad benutzt, soll scheitern statt stillschweigend ein leeres Ergebnis zu
    liefern (Muster "leer != unbekannt", #1492).
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"

    switch(quelle, ziel, mode="file")

    with pytest.raises(NotADirectoryError):
        (quelle / "users" / "alice" / "user.json").read_text()


# --- AC-1: Detektor fuer nachgewachsene Pfade -------------------------------


def test_detektor_meldet_nachgewachsene_dateien_mit_pfad(tmp_path):
    """GIVEN umgeschaltet / WHEN am alten Ort etwas entsteht / THEN mit Pfad gemeldet."""
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    switch(quelle, ziel, mode="absent")

    # Ein Prozess benutzt den relativen Pfad und legt neu an:
    (quelle / "users" / "ghost").mkdir(parents=True)
    (quelle / "users" / "ghost" / "user.json").write_text("{}")

    gefunden = detect_regrowth(quelle)
    assert any("users/ghost/user.json" in g for g in gefunden), (
        f"Detektor hat den nachgewachsenen Pfad nicht gemeldet: {gefunden}"
    )


def test_detektor_schweigt_wenn_nichts_nachwaechst(tmp_path):
    """GIVEN umgeschaltet / WHEN nichts passiert / THEN leere Meldung.

    Gegenprobe zum Test darueber: Ein Detektor, der immer etwas meldet, wuerde
    den 24-Stunden-Lauf wertlos machen.
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    switch(quelle, ziel, mode="absent")

    assert detect_regrowth(quelle) == []


# --- Bereits vorhandenes Ziel: die Wirklichkeit, nicht die bequeme Lage -----
#
# Auf Staging legt systemd (StateDirectory) `/var/lib/gregor-staging` bei JEDEM
# Dienststart an. Das Ziel existiert also praktisch immer schon, bevor
# umgeschaltet wird. Verschiebt das Werkzeug den Baum dann HINEIN statt DARAUF,
# liegt alles eine Ebene zu tief, kein Dienst findet etwas — und der Detektor am
# alten Ort schweigt korrekterweise, weil dort nichts ist. Der Fehlschlag waere
# still. Genau die Fehlerklasse, die diese Scheibe verhindern soll.


def test_switch_legt_flach_ab_wenn_das_ziel_schon_existiert(tmp_path):
    """GIVEN leeres Ziel existiert bereits / WHEN umgeschaltet / THEN Baum liegt flach darunter."""
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    ziel.mkdir(parents=True)  # wie systemd StateDirectory

    switch(quelle, ziel, mode="absent")

    assert (ziel / "users" / "alice" / "user.json").is_file(), (
        f"Baum liegt nicht direkt unter dem Ziel: {sorted(p.name for p in ziel.iterdir())}"
    )
    assert not (ziel / "data").exists(), "Baum wurde in das Ziel verschachtelt statt darauf gelegt"


def test_rollback_stellt_flach_wieder_her_wenn_die_quelle_schon_existiert(tmp_path):
    """GIVEN alter Ort wurde als leerer Ordner neu angelegt / WHEN Rueckbau / THEN flach."""
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    vorher = fingerprint(quelle)
    ziel = tmp_path / "var" / "gregor"
    switch(quelle, ziel, mode="absent")

    quelle.mkdir()  # ein Prozess hat den alten Ort inzwischen wieder angelegt

    rollback(quelle, ziel)

    assert compare_fingerprints(vorher, fingerprint(quelle)) == []
    assert not ziel.exists(), "Zielort muss nach dem Rueckbau geraeumt sein"


def test_switch_verweigert_ein_nicht_leeres_ziel(tmp_path):
    """GIVEN im Ziel liegt schon etwas / WHEN umgeschaltet / THEN Abbruch statt Vermischung.

    Ein Umzug auf einen Ordner mit Inhalt ist immer ein Bedienfehler. Gelaenge er
    still, waeren zwei Datenbestaende vermischt — nicht mehr trennbar.
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    ziel.mkdir(parents=True)
    (ziel / "fremd.json").write_text("{}")

    with pytest.raises(FileExistsError):
        switch(quelle, ziel, mode="absent")

    assert quelle.is_dir(), "bei Abbruch muss die Quelle unberuehrt bleiben"
    assert (quelle / "users" / "alice" / "user.json").is_file()


def test_switch_verweigert_eine_datei_am_zielort(tmp_path):
    """GIVEN am Zielort liegt eine DATEI / WHEN umgeschaltet / THEN eigener Abbruch.

    Der Abbruch muss aus diesem Werkzeug kommen, nicht zufaellig aus shutil —
    sonst haengt die Zusicherung an einem fremden Implementierungsdetail.
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    ziel.parent.mkdir(parents=True)
    ziel.write_text("ich bin eine Datei")

    with pytest.raises(FileExistsError) as fehler:
        switch(quelle, ziel, mode="absent")

    assert str(ziel) in str(fehler.value) and "Abbruch" in str(fehler.value), (
        f"die Meldung stammt nicht aus diesem Werkzeug, sondern aus shutil: {fehler.value}"
    )
    assert quelle.is_dir(), "bei Abbruch muss die Quelle unberuehrt bleiben"
    assert ziel.read_text() == "ich bin eine Datei", "die fremde Datei darf nicht angetastet werden"


# --- Symlinks: sehen aus wie ein Umzug, sind aber keiner ---------------------
#
# Ist die Quelle ein Symlink, verschiebt shutil nur den Verweis — der reale
# Datenbaum bleibt liegen, und das Ziel ist danach selbst nur ein Verweis
# darauf. Der Aufruf laeuft fehlerfrei durch, der Detektor am alten Ort meldet
# nichts, und trotzdem ist nichts umgezogen. Scheibe 4 sieht am alten Ort
# ausdruecklich einen Symlink als Rueckfahrkarte vor — diese Lage wird also
# real eintreten.


def test_switch_verweigert_eine_symlink_quelle(tmp_path):
    """GIVEN Quelle ist ein Symlink / WHEN umgeschaltet / THEN Abbruch statt Schein-Umzug."""
    echt = tmp_path / "echt"
    _make_tree(echt)
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    quelle.symlink_to(echt, target_is_directory=True)
    ziel = tmp_path / "var" / "gregor"

    with pytest.raises(ValueError):
        switch(quelle, ziel, mode="absent")

    assert (echt / "users" / "alice" / "user.json").is_file(), "der echte Baum muss unberuehrt sein"
    assert not ziel.exists(), "bei Abbruch darf am Zielort nichts entstehen"


def test_switch_verweigert_einen_symlink_am_zielort(tmp_path):
    """GIVEN am Zielort liegt ein Symlink / WHEN umgeschaltet / THEN Abbruch.

    Ein Symlink auf ein leeres Verzeichnis sieht wie ein leerer Zielordner aus.
    Der Baum landete dann woanders als angegeben — und GZ_DATA_DIR zeigte auf
    einen Verweis, dessen Ziel niemand nachgehalten hat.
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    woanders = tmp_path / "woanders"
    woanders.mkdir()
    ziel = tmp_path / "var" / "gregor"
    ziel.parent.mkdir(parents=True)
    ziel.symlink_to(woanders, target_is_directory=True)

    with pytest.raises(ValueError):
        switch(quelle, ziel, mode="absent")

    assert quelle.is_dir(), "bei Abbruch muss die Quelle unberuehrt bleiben"
    assert not any(woanders.iterdir()), "in das Symlink-Ziel darf nichts geschrieben worden sein"


# --- Der Detektor muss die 24 Stunden ueberleben ----------------------------


@pytest.mark.skipif(os.geteuid() == 0, reason="root darf alles lesen — Test waere wirkungslos")
def test_detektor_meldet_auch_eine_unlesbare_nachgewachsene_datei(tmp_path):
    """GIVEN nachgewachsen: lesbar UND unlesbar / WHEN erfasst / THEN beide gemeldet.

    Der Detektor beantwortet nur, WELCHE Pfade nachgewachsen sind — dafuer
    braucht er keinen Inhalt. Eine unlesbare nachgewachsene Datei ist sogar ein
    besonders interessanter Befund und darf die 24-Stunden-Messung nicht
    abstuerzen lassen. (Die Strenge von fingerprint bleibt davon unberuehrt.)
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    switch(quelle, ziel, mode="absent")

    (quelle / "users" / "ghost").mkdir(parents=True)
    (quelle / "users" / "ghost" / "user.json").write_text("{}")
    gesperrt = quelle / "users" / "ghost" / "geheim.json"
    gesperrt.write_text("{}")
    gesperrt.chmod(0o000)

    try:
        gefunden = detect_regrowth(quelle)
        assert any("users/ghost/user.json" in g for g in gefunden), gefunden
        assert any("users/ghost/geheim.json" in g for g in gefunden), (
            f"unlesbare nachgewachsene Datei fehlt in der Meldung: {gefunden}"
        )
    finally:
        gesperrt.chmod(0o600)


def test_detektor_meldet_auch_symlinks_und_leere_verzeichnisse(tmp_path):
    """GIVEN nachgewachsen: Symlink, kaputter Symlink, leerer Ordner / THEN alle drei gemeldet.

    Ein Detektor, der etwas uebersieht, meldet `[]` — nicht zu unterscheiden von
    "nichts passiert". Genau das Muster "leer != unbekannt" (#1492), dem diese
    Scheibe gilt. Ein neu angelegter Symlink am alten Ort ist typischerweise ein
    manueller Ops-Handgriff, ein leeres Verzeichnis der Go-Store, der anlegt
    bevor er schreibt — beides sind Zugriffe auf den alten Pfad, also Befunde.
    """
    quelle = tmp_path / "repo" / "data"
    quelle.parent.mkdir(parents=True)
    _make_tree(quelle)
    ziel = tmp_path / "var" / "gregor"
    switch(quelle, ziel, mode="absent")

    woanders = tmp_path / "woanders"
    (woanders / "inhalt").mkdir(parents=True)
    (woanders / "inhalt" / "user.json").write_text("{}")

    (quelle / "users").mkdir(parents=True)
    (quelle / "users" / "verweis").symlink_to(woanders, target_is_directory=True)
    (quelle / "users" / "kaputt").symlink_to(tmp_path / "gibt-es-nicht")
    (quelle / "users" / "leer").mkdir()

    gefunden = detect_regrowth(quelle)

    # Die Art steht mit im Befund — ein als "Verzeichnis" gemeldeter Symlink
    # wuerde beim Auswerten in die falsche Richtung fuehren.
    assert "users/verweis (Symlink)" in gefunden, (
        f"Symlink auf ein Verzeichnis fehlt oder ist falsch benannt: {gefunden}"
    )
    assert "users/kaputt (Symlink)" in gefunden, (
        f"kaputter Symlink fehlt oder ist falsch benannt: {gefunden}"
    )
    assert "users/leer (Verzeichnis)" in gefunden, (
        f"leeres Verzeichnis fehlt oder ist falsch benannt: {gefunden}"
    )
