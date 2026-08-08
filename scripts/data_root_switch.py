"""Umschalt-Werkzeug fuer die Datenwurzel (Issue #1595, Scheibe 1).

Verschiebt einen Datenbaum an einen neuen Ort, laesst den alten Ort wahlweise
leer (Stufe A) oder als Sperrdatei zurueck (Stufe B), und misst die
Unversehrtheit ueber Pruefsummen.
"""

import hashlib
import shutil
from pathlib import Path

SPERRDATEI_INHALT = "Datenwurzel umgezogen (Issue #1595, Stufe B). Zugriff hierher ist ein Befund.\n"


def fingerprint(root: Path) -> dict[str, str]:
    """Erfasst jede Datei unter ``root`` als relativer Pfad -> Pruefsumme.

    Muss bei einer unlesbaren Datei LAUT scheitern statt sie zu ueberspringen —
    ein uebersprungener Eintrag erzeugt ein unvollstaendiges Ergebnis, das wie
    ein vollstaendiges aussieht. Deshalb faengt hier nichts Lesefehler ab.
    """
    erfassung: dict[str, str] = {}
    for pfad in sorted(root.rglob("*")):
        if not pfad.is_file():
            continue
        # Bewusst ungeschuetzt: ein PermissionError muss nach aussen dringen.
        pruefsumme = hashlib.sha256(pfad.read_bytes()).hexdigest()
        erfassung[pfad.relative_to(root).as_posix()] = pruefsumme
    return erfassung


def compare_fingerprints(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Menschenlesbare Abweichungen zwischen zwei Erfassungen. Leer = identisch."""
    abweichungen: list[str] = []
    for pfad in sorted(set(before) | set(after)):
        if pfad not in after:
            abweichungen.append(f"geloescht: {pfad}")
        elif pfad not in before:
            abweichungen.append(f"neu: {pfad}")
        elif before[pfad] != after[pfad]:
            abweichungen.append(f"geaendert: {pfad}")
    return abweichungen


def detect_regrowth(old_root: Path) -> list[str]:
    """Relative Pfade, die am alten Ort (wieder) entstanden sind. Leer = nichts.

    Liest bewusst KEINE Inhalte: gefragt ist nur, WELCHE Pfade entstanden sind.
    So meldet der Detektor auch eine unlesbare nachgewachsene Datei — ein
    besonders interessanter Befund — statt die 24-Stunden-Messung abstuerzen zu
    lassen. Die Strenge von ``fingerprint`` bleibt davon unberuehrt: dort zaehlt
    Vollstaendigkeit, hier Robustheit.

    Gemeldet wird JEDER Eintrag, ohne Typ-Filter: auch ein Symlink (der auf ein
    Verzeichnis zeigende ebenso wie der kaputte) und ein leeres Verzeichnis. Ein
    Symlink am alten Ort ist ein manueller Handgriff, ein leeres Verzeichnis der
    Store, der anlegt bevor er schreibt — beides sind Zugriffe auf den alten
    Pfad. Uebersaehe der Detektor sie, meldete er ``[]`` und waere nicht mehr von
    "nichts passiert" zu unterscheiden.
    """
    if not old_root.is_dir():
        return []
    befunde = []
    for pfad in old_root.rglob("*"):
        if pfad.is_symlink():  # vor is_dir/is_file: beide folgen dem Verweis
            art = "Symlink"
        elif pfad.is_dir():
            art = "Verzeichnis"
        else:
            art = "Datei"
        befunde.append(f"{pfad.relative_to(old_root).as_posix()} ({art})")
    return sorted(befunde)


def _move_onto(baum: Path, ziel: Path) -> None:
    """Verschiebt ``baum`` AUF ``ziel`` — nie HINEIN.

    ``shutil.move`` legt den Baum in ein bereits vorhandenes Verzeichnis hinein;
    alles laege dann eine Ebene zu tief und kein Dienst faende etwas. Auf Staging
    ist genau das der Normalfall, weil systemd (``StateDirectory``) den Zielordner
    bei jedem Dienststart anlegt.

    Symlinks werden auf beiden Seiten abgelehnt: ``shutil.move`` verschoebe nur
    den Verweis, der reale Datenbaum bliebe liegen — der Aufruf saehe erfolgreich
    aus, ohne dass etwas umgezogen ist. Ab Scheibe 4 liegt am alten Ort
    ausdruecklich ein Symlink als Rueckfahrkarte; diese Lage tritt also real ein.
    """
    if baum.is_symlink():
        raise ValueError(
            f"{baum} ist ein Symlink — Abbruch: es wuerde nur der Verweis verschoben, "
            "die Daten blieben liegen."
        )
    if ziel.is_symlink():
        raise ValueError(
            f"Ziel {ziel} ist ein Symlink — Abbruch: der Baum landete woanders als angegeben."
        )
    if ziel.is_dir():
        if any(ziel.iterdir()):
            raise FileExistsError(
                f"Ziel {ziel} ist nicht leer — Abbruch, sonst wuerden zwei Datenbestaende vermischt."
            )
        ziel.rmdir()
    elif ziel.exists():
        raise FileExistsError(f"Ziel {ziel} existiert und ist kein Verzeichnis — Abbruch.")
    else:
        ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(baum), str(ziel))


def switch(source: Path, target: Path, mode: str = "absent") -> None:
    """Verschiebt ``source`` nach ``target``.

    mode="absent": alter Ort bleibt leer — Schreiber legen dort neu an (Stufe A).
    mode="file":   alter Ort wird eine DATEI — jeder Zugriff auf ``source/...``
                   scheitert mit NotADirectoryError, also laut (Stufe B).
    """
    _move_onto(source, target)
    if mode == "file":
        source.write_text(SPERRDATEI_INHALT)


def rollback(source: Path, target: Path) -> None:
    """Stellt den Ausgangszustand her: Baum zurueck, Sperrdatei weg, Ziel geraeumt."""
    if source.is_file():
        source.unlink()
    _move_onto(target, source)
