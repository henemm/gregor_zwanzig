"""Abweichungszaehler der Vorlage gegen die Abo-Ampel (Issue #2794 S3a, AC-28).

Spec: docs/specs/modules/feat_2794_s3a_reiter_wetter.md §6 „Abweichungszaehler".
Python-Referenz ``app.ampel.deviation_count`` zaehlt neben Grenzen und
Gewitterfarbe auch ``enabled``, ``alarm_ab`` und Metrik hinzugefuegt/entfernt
gegenueber der Vorlage; eine Aenderung zurueck auf den Vorlagenwert zaehlt nicht.

Paritaet: dieselbe JSON-Fixture ``tests/fixtures/ampel_deviation_cases.json``
liest spaeter der Frontend-Spiegel per ``node --test``. Annahme (in der Fixture
dokumentiert): je betroffener Metrik hoechstens eine Abweichung, auch wenn an ihr
mehrere Aenderungsarten zusammenkommen; die Gewitterfarbe zaehlt einmal.

Kein Mock: echte Vorlagen aus ``app.ampel_templates``, Pruefling relativ zur
Testdatei.
"""

import json
from pathlib import Path

from app.ampel import deviation_count

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ampel_deviation_cases.json"

# Jede in der Spec genannte Aenderungsart muss in der Fixture vorkommen.
PFLICHT_FAELLE = {
    "grenze_geaendert", "enabled_geaendert_aus", "alarm_ab_geaendert",
    "metrik_hinzugefuegt_in_vorlage_aus", "metrik_entfernt", "gewitterfarbe_geaendert",
    "zurueck_auf_vorlagenwert", "kombination",
}


def _faelle() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def test_ac28_python_referenz_liefert_fuer_jeden_fixture_fall_die_erwartete_zahl():
    faelle = _faelle()
    assert PFLICHT_FAELLE <= {f["name"] for f in faelle}, "Fixture deckt nicht alle Aenderungsarten ab"
    abweichend = {
        f["name"]: (deviation_count(f["ampel"]), f["expected"])
        for f in faelle
        if deviation_count(f["ampel"]) != f["expected"]
    }
    assert abweichend == {}, f"(ist, soll) je Fall: {abweichend}"
