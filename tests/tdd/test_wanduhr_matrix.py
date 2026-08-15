"""Selbsttests fuer das Messwerkzeug ``tests/helpers/wanduhr_matrix.py``
(#1709 AC-3, AC-4) — das Werkzeug existiert noch nicht, dieser Testlauf ist
zunaechst ROT.

Warum ueberhaupt ein Messwerkzeug
----------------------------------
Ob eine Fixture indirekt von der Wanduhr abhaengt, laesst sich nicht durch
Lesen entscheiden — die Zeitabhaengigkeit entsteht erst im Pruefling. Sie
laesst sich aber MESSEN: dieselbe Testdatei zu zwei kuenstlich verschiedenen
Uhrzeiten laufen lassen und die Ergebnisse vergleichen. Nur die DIFFERENZ ist
auswertbar, nie ein einzelner Lauf (docs/specs/modules/
fix_1709_wallclock_ratsche_indirekt.md, Abschnitt "Messwerkzeug").

Erwarteter Vertrag (von diesen Tests erzwungen, nicht von der Spec
vorgeschrieben — die Funktionsnamen sind Teil dieses RED-Entwurfs):

``helpers.wanduhr_matrix.lauf_bei_uhrzeit(testdatei: Path, uhrzeit: datetime)``
    Fuehrt ``testdatei`` EINMAL, in einem FRISCHEN Betriebssystem-Prozess, mit
    gestellter Wanduhr ``uhrzeit`` aus (ein Datenpunkt).

``helpers.wanduhr_matrix.matrix_differenz(testdatei: Path,
                                          uhrzeiten: Sequence[datetime]) -> frozenset[str]``
    Misst ``testdatei`` zu jeder Uhrzeit (je ein frischer Prozess) und gibt
    die Menge der Test-Nodeids zurueck, deren Ergebnis (bestanden /
    fehlgeschlagen) nicht bei ALLEN Uhrzeiten identisch ist. Bei zwei
    Uhrzeiten derselben Seite einer Kippkante ist das Ergebnis leer.

Drei Fallen, die dieser Vertrag bewusst ausschliesst (Kontext-Dokument,
Abschnitt "Drei Fallen im Messaufbau"):

1. Mehrere Datenpunkte im selben Prozess ergaben eine Matrix, die sich bei
   frischen Prozessen nicht reproduzieren liess — Zustand sickert durch.
2. Sitzungsweites ``freezegun`` zerstoert pydantic-v1-Importe und erzeugt
   Falsch-Positive — deshalb zaehlt nur die Differenz, nie eine absolute
   Fehlerzahl.
3. Uhrzeiten muessen in der ORTSZONE der Fixture gewaehlt werden, nicht in
   UTC — hier irrelevant (die Attrappen unten rechnen selbst in UTC), aber
   fuer die Verwendung des Werkzeugs auf echten Fixtures zentral.

Spec: docs/specs/modules/fix_1709_wallclock_ratsche_indirekt.md
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

# Wurzel DIESES Checkouts (#1409) — hier nur fuer Konsistenz mit dem Vorbild
# gehalten, diese Tests lesen selbst nichts vom Hauptrepo-Pfad.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _attrappe(tmp_path: Path, quelltext: str, name: str = "test_attrappe.py") -> Path:
    """Echte Testdatei-Attrappe auf die Platte schreiben (kein Mock)."""
    f = tmp_path / name
    f.write_text(quelltext, encoding="utf-8")
    return f


# Eine Attrappe mit einer bekannten Kippkante bei 2026-01-01 12:00 UTC: gruen
# davor, rot danach. ``datetime.now`` wird NICHT selbst gestellt — das ist
# genau die Aufgabe des Messwerkzeugs (freezegun o.ae.).
_KANTEN_FALL = '''\
from datetime import datetime, timezone

GRENZE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_vor_der_grenze():
    """Gruen, solange die gestellte Wanduhr vor GRENZE liegt."""
    jetzt = datetime.now(timezone.utc)
    assert jetzt < GRENZE, f"jetzt={jetzt.isoformat()} liegt nicht mehr vor der Grenze"
'''

# Eine Attrappe ohne jede Zeitabhaengigkeit — Kontrollfall dafuer, dass
# matrix_differenz bei einem gesunden Testfall wirklich schweigt.
_STABILER_FALL = '''\
def test_immer_gruen():
    assert 1 + 1 == 2
'''

# Eine Attrappe, die ihre eigene Prozess-ID in eine Datei im selben Ordner
# schreibt (AC-4). ANHAENGEND (Modus "a"), damit zwei Laeufe desselben
# Messwerkzeugs beide Aufzeichnungen erhalten bleiben und miteinander
# verglichen werden koennen.
_PID_FALL = '''\
import os
from pathlib import Path

_PID_DATEI = Path(__file__).parent / "beobachtete_pids.txt"


def test_schreibt_die_eigene_prozess_id():
    with _PID_DATEI.open("a", encoding="utf-8") as f:
        f.write(f"{os.getpid()}\\n")
    assert True
'''


def test_matrix_findet_die_kante(tmp_path):
    """AC-3: eine Attrappe, die bei gestellter Uhr vor 2026-01-01 12:00 UTC
    gruen und danach rot ist -> die Differenz enthaelt GENAU diesen Testfall."""
    from helpers.wanduhr_matrix import matrix_differenz

    testdatei = _attrappe(tmp_path, _KANTEN_FALL)
    vor = datetime(2025, 12, 31, 23, 0, tzinfo=timezone.utc)
    nach = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)

    diff = matrix_differenz(testdatei, [vor, nach])

    assert any("test_vor_der_grenze" in eintrag for eintrag in diff), (
        f"die bekannte Kippkante wurde nicht in der Differenz gefunden: "
        f"{sorted(diff)}"
    )


def test_matrix_meldet_nichts_ohne_kante(tmp_path):
    """Gegenprobe zu AC-3: zwei Uhrzeiten derselben Seite der Grenze ergeben
    eine LEERE Differenz. Ein Werkzeug, das nie etwas findet, ist von einem
    sauberen Bestand nicht unterscheidbar — ohne diesen Test waere unklar, ob
    matrix_differenz ueberhaupt zwischen "gefunden" und "nichts da"
    unterscheidet (statt z.B. immer eine leere Menge zurueckzugeben)."""
    from helpers.wanduhr_matrix import matrix_differenz

    testdatei = _attrappe(tmp_path, _KANTEN_FALL)
    a = datetime(2025, 12, 31, 20, 0, tzinfo=timezone.utc)
    b = datetime(2025, 12, 31, 22, 0, tzinfo=timezone.utc)

    diff = matrix_differenz(testdatei, [a, b])

    assert diff == frozenset(), f"Falsch-Positiv ohne Kippkante: {sorted(diff)}"


def test_matrix_schweigt_bei_einem_stabilen_testfall(tmp_path):
    """Zweite Gegenprobe: ein voellig zeitunabhaengiger Testfall bleibt zu
    JEDER gestellten Uhrzeit gleich -> leere Differenz."""
    from helpers.wanduhr_matrix import matrix_differenz

    testdatei = _attrappe(tmp_path, _STABILER_FALL)
    a = datetime(2020, 1, 1, tzinfo=timezone.utc)
    b = datetime(2030, 6, 15, 12, 0, tzinfo=timezone.utc)

    diff = matrix_differenz(testdatei, [a, b])

    assert diff == frozenset(), f"Falsch-Positiv bei stabilem Testfall: {sorted(diff)}"


def test_matrix_nutzt_je_datenpunkt_einen_eigenen_prozess(tmp_path):
    """AC-4: frischer Prozess je Datenpunkt ist ERZWUNGEN, nicht empfohlen.
    Nachweis: die Attrappe schreibt ihre eigene ``os.getpid()`` in eine Datei;
    zwei Messungen muessen zwei verschiedene, vom Messprozess verschiedene
    PIDs hinterlassen. Ein Kommentar "bitte frischen Prozess nehmen" waere
    keine Zusicherung, sondern eine Bitte."""
    from helpers.wanduhr_matrix import lauf_bei_uhrzeit

    testdatei = _attrappe(tmp_path, _PID_FALL)
    zeitpunkt_a = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    zeitpunkt_b = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    lauf_bei_uhrzeit(testdatei, zeitpunkt_a)
    lauf_bei_uhrzeit(testdatei, zeitpunkt_b)

    pid_datei = tmp_path / "beobachtete_pids.txt"
    aufgezeichnet = [
        int(zeile) for zeile in pid_datei.read_text(encoding="utf-8").splitlines()
        if zeile.strip()
    ]

    assert len(aufgezeichnet) == 2, (
        f"erwartet 2 aufgezeichnete Prozess-IDs (eine je Lauf), bekommen: "
        f"{aufgezeichnet}"
    )
    assert len(set(aufgezeichnet)) == 2, (
        f"beide Datenpunkte liefen im SELBEN Prozess: {aufgezeichnet} — genau "
        "die Falle aus dem Kontext-Dokument (Zustand sickert zwischen "
        "Laeufen im selben Prozess durch)"
    )
    assert os.getpid() not in aufgezeichnet, (
        f"die Attrappe lief im MESSPROZESS ({os.getpid()}) statt in einem "
        f"eigenen Kindprozess: {aufgezeichnet}"
    )
