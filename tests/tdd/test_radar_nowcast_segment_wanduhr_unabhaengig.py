"""Bug-Nachweis #1940 aus Nutzersicht: dieselbe Testdatei, dieselben Tests,
UNTERSCHIEDLICHES Ergebnis je nach Wanduhrzeit.

Worum es geht
-------------
``tests/tdd/test_issue_822_radar_nowcast_segment.py`` baut seine Trips ueber
``tests/helpers/arrival_window_fixtures.fenster_minuten``. Liegt *jetzt* nahe
der Ortszeit-Mitternacht des Etappentags, schiebt der Helfer das ganze Fenster
nach vorne; die Abstaende bleiben, das VORZEICHEN eines Versatzes nicht. Ein
Wegpunkt, den der Test bewusst in die Vergangenheit gelegt hat, ist dann noch
aktiv — der Produktivcode waehlt zurecht das erste Segment, und die
Testerwartung (zweites Segment) trifft nicht zu. Ergebnis: die CI-Ampel ist
taeglich 12:00-13:30 UTC rot, unabhaengig vom PR-Inhalt (Issue #1940). Ein
vierter Testfall derselben Datei kippt aus einem zweiten Grund an derselben
Naht (Server- statt Ortsdatum, s. ``IM_SPEC_SCOPE``) und ist taeglich
23:00-00:00 UTC rot.

Dieselbe Klasse ein drittes Mal, in der Schwesterfunktion
``past_window_offsets``: sie stauchte ein nicht mehr passendes
Vergangenheits-Fenster still auf den verfuegbaren Platz, wodurch das
Ziel-Segment noch eine Stunde offen blieb und der Trip gerade NICHT „vorbei"
war. Betroffen ist ``test_issue_818_radar_briefing_integration.py::
test_ac5_...``, taeglich 12:00-16:00 UTC (Spec AC-7) — deshalb wird diese
Datei hier als zweiter Messfall mitgemessen.

Dieser Test misst genau das — er liest den Fehler nicht am Code ab, sondern
laesst die betroffenen Dateien zu mehreren gestellten Uhrzeiten laufen und
vergleicht die Ergebnisse (``tests/helpers/wanduhr_matrix.py``, #1709: ein
FRISCHER Betriebssystem-Prozess je Datenpunkt, nur die DIFFERENZ ist
auswertbar).

Warum der Test selbst NICHT wanduhr-abhaengig ist
-------------------------------------------------
Jeder Datenpunkt laeuft unter einer fest verdrahteten, gestellten Uhr — das
Ergebnis haengt nicht davon ab, wann CI ihn startet. Waere die Uhrzeit "jetzt +
x", reproduzierte dieser Test genau die Fehlerklasse, die er schliessen soll.
Auch das DATUM ist bewusst fest: Neuseeland wechselt Ende September 2026 in die
Sommerzeit und verschiebt das Bruchfenster damit auf 11:00-12:30 UTC. Ein
gestelltes Datum im August haelt 12:30 UTC dauerhaft im Bruchfenster.

Teuer gemessene Voraussetzung: die Prozess-Zeitzone
---------------------------------------------------
``lauf_bei_uhrzeit`` startet ``freeze_time(..., tick=True)`` im Kindprozess,
BEVOR pytest den Root-``conftest.py`` importiert, der die Prozess-Zeitzone auf
``America/St_Johns`` stellt (#1402). Wechselt die Zeitzone waehrend eines
aktiven ``tick=True``-Freeze, verschiebt sich der eingefrorene Zeitpunkt um den
neuen Ortsversatz — nachgemessen: angefordert 12:30 UTC, wirksam 10:00 UTC
(-2:30). Erbt der Kindprozess ``TZ`` dagegen bereits beim Start, ist der
Wechsel wirkungslos und der angeforderte Zeitpunkt trifft zu. Unter pytest ist
das erfuellt (der Root-conftest setzt ``os.environ["TZ"]``, und
``lauf_bei_uhrzeit`` reicht die Umgebung weiter) — deshalb wird es unten
geprueft statt vorausgesetzt. Von Hand aus einer Shell ohne gesetztes ``TZ``
misst dasselbe Werkzeug einen um den Ortsversatz verschobenen Zeitpunkt und
findet nichts.

Pfadregel #1409: die vermessene Datei wird relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.helpers.wanduhr_matrix import lauf_bei_uhrzeit, matrix_differenz

VERMESSENE_DATEI = Path(__file__).resolve().parent / "test_issue_822_radar_nowcast_segment.py"
VERMESSENE_DATEI_818 = (
    Path(__file__).resolve().parent / "test_issue_818_radar_briefing_integration.py"
)

# Zwei Uhrzeiten im Bruchfenster, zwei ausserhalb. 12:30 UTC = 00:30 in
# Neuseeland (UTC+12, August), 23:30 UTC = 00:30 in London (UTC+1, Sommerzeit).
# Beide Londoner Bruchfenster beginnen ausgerechnet 23:00 UTC — nachgemessen,
# nicht angenommen: AC-2 ueber die Ortsminute (< 60 auf dem Etappentag), AC-4
# ueber die Datumsabweichung Ortsdatum/Serverdatum (23:00-00:00 UTC, solange
# Sommerzeit gilt; in der Winterzeit ist London == UTC und AC-4 den ganzen Tag
# gruen). Genau deshalb ist das gestellte Datum im August richtig: es haelt die
# AC-4-Kante ganzjaehrig im Messbereich.
UHRZEITEN = [
    datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc),    # gruen erwartet
    datetime(2026, 8, 18, 12, 30, tzinfo=timezone.utc),  # AC-3 rot erwartet
    datetime(2026, 8, 18, 16, 0, tzinfo=timezone.utc),   # gruen erwartet
    datetime(2026, 8, 18, 23, 30, tzinfo=timezone.utc),  # AC-2 + AC-4 rot erwartet
]
REFERENZZEIT = UHRZEITEN[0]

# Der Spec-Umfang, ZWEI Ursachen:
#
# * Zeile 194/260/406 (AC-1/AC-2/AC-3) brauchen ein bereits VERGANGENES erstes
#   Segment und verlieren es durch die Vorwaertsverschiebung in
#   ``fenster_minuten`` (Spec AC-1 bis AC-5).
# * Zeile 484 (AC-4) nimmt ``datetime.now(timezone.utc).date()`` — das
#   SERVERdatum — statt ``stage_date(lat, lon)``. Ab 23:00 UTC zeigt London
#   (UTC+1, Sommerzeit) auf den Folgetag, Etappendatum und Ankunftszeiten
#   laufen auseinander, die Etappe wird nicht gefunden und es entsteht gar kein
#   Alarm (Spec AC-6). Andere Ursache, dieselbe Klasse: eine Fixture, deren
#   Zusicherung an der Ortszeit-Mitternacht kippt.
IM_SPEC_SCOPE = {
    "test_ac1_segment_helper_roundtrip_bit_identical",
    "test_ac2_segment_selection_by_time",
    "test_ac3_nowcast_called_at_segment_coordinates",
    "test_ac4_mail_body_contains_segment_label_and_cooldown",
}

# Zweiter Messfall (Spec AC-7): dieselbe Fehlerklasse in der Schwesterfunktion
# ``past_window_offsets``, die still auf den verfuegbaren Platz stauchte statt
# laut zu scheitern. In Neuseeland (UTC+12) ist der Etappentag zwischen 12:00
# und 16:00 UTC erst 0-239 Minuten alt — zu jung fuer das verlangte
# 240-Minuten-Fenster. Die Messpunkte umschliessen BEIDE gemessenen Kanten
# minutennah (11:55/12:05 und 15:55/16:05), sonst faende die Messung die
# 12:00-Kante nur zufaellig.
UHRZEITEN_818 = [
    datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc),    # gruen erwartet
    datetime(2026, 8, 18, 11, 55, tzinfo=timezone.utc),  # gruen erwartet
    datetime(2026, 8, 18, 12, 5, tzinfo=timezone.utc),   # vor AC-7 rot
    datetime(2026, 8, 18, 15, 55, tzinfo=timezone.utc),  # vor AC-7 rot
    datetime(2026, 8, 18, 16, 5, tzinfo=timezone.utc),   # gruen erwartet
]
IM_SPEC_SCOPE_818 = {"test_ac5_past_segment_no_alert_guard_test"}

# (Datei, Spec-Umfang, Messpunkte, Referenzzeit) — die Referenzzeit ist der
# gruene Anker der Positivkontrolle.
MESSFAELLE = [
    pytest.param(
        VERMESSENE_DATEI, IM_SPEC_SCOPE, UHRZEITEN, REFERENZZEIT,
        id="822-nowcast-segment",
    ),
    pytest.param(
        VERMESSENE_DATEI_818, IM_SPEC_SCOPE_818, UHRZEITEN_818, UHRZEITEN_818[0],
        id="818-briefing-integration",
    ),
]


def _funktionsnamen(nodeids) -> set[str]:
    """Nur der Testfunktionsname — der Nodeid-Pfad haengt am rootdir des
    Kindprozesses und ist als Vergleichsschluessel unnoetig zerbrechlich."""
    return {nodeid.split("::")[-1].split("[")[0] for nodeid in nodeids}


@pytest.mark.timeout(300)
@pytest.mark.parametrize("datei,spec_umfang,uhrzeiten,referenzzeit", MESSFAELLE)
def test_radar_segment_tests_liefern_zu_jeder_wanduhrzeit_dasselbe_ergebnis(
    datei, spec_umfang, uhrzeiten, referenzzeit
):
    """#1940: die Testfaelle im Spec-Umfang duerfen ihr Ergebnis nicht mit der
    Wanduhr wechseln.

    Vor dem Fix: ``test_ac3_...`` faellt bei 12:30 UTC aus, ``test_ac2_...``
    und ``test_ac4_...`` ab 23:00 UTC, ``test_ac5_past_segment_...`` (zweite
    Datei) zwischen 12:00 und 16:00 UTC; an den uebrigen Messpunkten sind alle
    gruen. Genau diese Differenz ist der Fehler — nicht die absolute
    Fehlerzahl eines einzelnen Laufs (sitzungsweites ``freezegun`` zerstoert
    pydantic-v1-Importe und erzeugt Falsch-Positive, s.
    ``wanduhr_matrix``-Docstring, Punkt 2).
    """
    assert os.environ.get("TZ"), (
        "Die Messung setzt voraus, dass der Kindprozess die Prozess-Zeitzone "
        "schon beim Start erbt (Root-conftest.py, #1402). Ohne gesetztes TZ "
        "verschiebt der Zeitzonenwechsel waehrend des laufenden freeze_time "
        "den eingefrorenen Zeitpunkt um den Ortsversatz und die Messung "
        "trifft ein anderes Zeitfenster als angefordert."
    )

    referenz = lauf_bei_uhrzeit(datei, referenzzeit)
    ergebnis_je_name = {
        nodeid.split("::")[-1].split("[")[0]: ausgang
        for nodeid, ausgang in referenz.items()
    }
    nicht_bestanden = {
        name: ergebnis_je_name.get(name, "nicht gelaufen")
        for name in spec_umfang
        if ergebnis_je_name.get(name) != "passed"
    }
    assert not nicht_bestanden, (
        f"Positivkontrolle {datei.name}: bei {referenzzeit.isoformat()} muessen "
        f"alle {len(spec_umfang)} Testfaelle im Spec-Umfang gruen sein, sind "
        f"aber {nicht_bestanden}. Ohne diesen Anker waere die Differenz unten "
        "auch dann leer, wenn die Tests zu ALLEN Uhrzeiten rot sind."
    )

    abweichend = _funktionsnamen(matrix_differenz(datei, uhrzeiten))
    betroffen = sorted(abweichend & spec_umfang)

    assert not betroffen, (
        f"{datei.name}: {betroffen} liefern je nach gestellter Wanduhrzeit ein "
        f"anderes Ergebnis (gemessen bei {[u.isoformat() for u in uhrzeiten]}). "
        "Die Fixture stellt ihre Voraussetzung nicht zu jeder Ortszeit her — "
        "die Segment-Konstellation (AC-1/2/3, Vorzeichen des Versatzes), den "
        "Etappentag selbst (AC-4, Server- statt Ortsdatum) oder die verlangte "
        "Spanne des vergangenen Fensters (AC-7, stille Stauchung). Issue #1940."
    )
