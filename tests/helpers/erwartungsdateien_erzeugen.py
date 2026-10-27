"""Erzeugt die eingefrorenen Anzeige-Erwartungsdateien fuer Issue #2422 S2a
(``erwartung_golden_a.json``/``_b.json``/``_c.json``).

SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md
("Wahrheit bleibt das Python-Orakel").

Diese Dateien sind die Wahrheit fuer das TS- und das E2E-Bein -- TypeScript
berechnet dabei KEINE Kaskade nach, es vergleicht nur zwei reine
Datenstrukturen (Memory: das Orakel wird bewusst NICHT nach TS portiert).
Reihenfolge/Auswahl je der drei Editor-Reiter (email/telegram/sms -- sms
deckt Premium-SMS/Telegram-Kurzform mit ab, ADR-0049, da alle drei denselben
Kaskaden-Layoutschluessel ``sms`` lesen) kommt aus ``erwartete_kaskade()``.

**Report-Typ-Sentinel ``ANZEIGE_REPORT_TYPE = "anzeige"`` (KEIN "morning"/
"evening"), PFLICHT fuer diese Datei:** Der Editor selbst ist NICHT nach
Report-Typ gesplittet -- ``WeatherMetricsTab.svelte::initFromTrip()`` baut
die primary/secondary-Buckets ausschliesslich aus dem ROHEN ``m.enabled``
(``savedMetrics.filter((m) => m.enabled && m.bucket === 'primary')``,
Zeilen ~452-459), UNABHAENGIG von ``morning_enabled``/``evening_enabled``
(G4, Golden C). ``erwartete_kaskade(..., report_type="morning"/"evening")``
wuerde eine per-Report-Typ GEFILTERTE Menge liefern (z.B. Golden C: ohne
``cloud_low`` bei 'evening', ohne ``humidity`` bei 'morning') -- das waere
eine Anzeige, die der Editor gar nicht zeigt (AC-3 koennte nie gruen
werden). ``_behalten_fuer_report_typ()`` faellt fuer JEDEN Report-Typ
ausserhalb von {"morning","evening"} auf den reinen ``enabled``-Wert zurueck
(einstellung_auslieferung_orakel.py, letzter ``else``-Zweig) -- exakt das
Editor-Verhalten. Die REPORT-TYP-SPEZIFISCHE Auslieferungs-Gleichheit
(K8/G4, AC-1/AC-5) wird NICHT hier, sondern direkt in
``test_einstellung_gleich_auslieferung.py`` mit ``report_type="morning"``/
``"evening"`` geprueft -- diese Datei ist ausschliesslich die
report-typ-neutrale ANZEIGE-Wahrheit.

Lauf (schreibt/aktualisiert alle drei Dateien):
    uv run python3 -m tests.helpers.erwartungsdateien_erzeugen

Ein Drift-Test (``tests/test_erwartungsdatei_drift_einstellung_gleich_
auslieferung.py``) prueft bei jedem Testlauf, dass die eingefrorenen
Dateien exakt dem AKTUELLEN Orakel-Ergebnis entsprechen.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.einstellung_auslieferung_orakel import erwartete_kaskade

#: Editor-Reiter -> repraesentativer Orakel-Kanal (gleicher Layoutschluessel,
#: siehe ``_LAYOUT_KEY_JE_KANAL`` in einstellung_auslieferung_orakel.py).
_REITER_ZU_ORAKEL_KANAL = {
    "email": "email_html",
    "telegram": "telegram_rich",
    "sms": "sms",
}

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_auslieferung"
#: Report-Typ-neutraler Sentinel fuer die ANZEIGE (siehe Modul-Docstring) --
#: bewusst NICHT "morning"/"evening", damit morning_enabled/evening_enabled
#: (G4) die Editor-Anzeige nicht filtern, so wie es der echte Editor auch
#: nicht tut.
REPORT_TYPE = "anzeige"


def erwartung_fuer_golden(golden: dict) -> dict:
    """Reine Datenstruktur (Auswahl/Reihenfolge/Roh-Einfach je Editor-Reiter)
    aus dem Python-Orakel -- keine Kaskaden-Logik im Ergebnis, nur Daten."""
    kanaele: dict[str, list[dict]] = {}
    for reiter, orakel_kanal in _REITER_ZU_ORAKEL_KANAL.items():
        kanaele[reiter] = [
            {"metric_id": mid, "friendly": friendly}
            for mid, friendly in erwartete_kaskade(golden, orakel_kanal, REPORT_TYPE)
        ]
    return {"report_type": REPORT_TYPE, "channels": kanaele}


def schreibe_erwartungsdatei(name: str, golden: dict) -> Path:
    ziel = GOLDEN_DIR / f"erwartung_{name}.json"
    ziel.write_text(json.dumps(erwartung_fuer_golden(golden), indent=2, ensure_ascii=False) + "\n")
    return ziel


def _golden_dict_ohne_stage_rewrite(name: str) -> dict:
    """Wie ``_einstellung_auslieferung_fixtures.golden_dict``, aber ohne die
    Stage-Datums-Nachbearbeitung -- fuer die Kaskade irrelevant, spart die
    Test-Modul-Abhaengigkeit im Skript-Kontext."""
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text())


def main() -> None:
    for name in ("golden_a", "golden_b", "golden_c"):
        golden = _golden_dict_ohne_stage_rewrite(name)
        ziel = schreibe_erwartungsdatei(name, golden)
        print(f"geschrieben: {ziel}")


if __name__ == "__main__":
    main()
