"""Issue #3258 (Fix-Loop 1, F002): Drift-Test für den Schnappschuss der Kürzel-Bedeutungen.

Spec: docs/specs/modules/feat_3258_sms_kuerzel_legende.md (AC-2, Legende „Kürzel erklärt“).

Die Legende zeigt live je Metrik-Kürzel die Bedeutung aus dem Server-Katalog (``legend.metrics[].meaning``
= ``kuerzel_bedeutung_de/en`` in ``src/app/metric_catalog.py``) und für Orte den festen Eintrag O1
(``vergleich.sms.ort_nummer`` im Server-Katalog ``src/i18n/messages``). Der Elementlisten-Generator
(TypeScript) liest dafür den Schnappschuss ``docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json``,
statt zur Laufzeit Python aufzurufen; dieser Test hält Schnappschuss und Katalog gleich (kein Mock).

    uv run pytest tests/test_3258_kuerzel_bedeutung_schnappschuss.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

from app.metric_catalog import _METRICS

REPO = Path(__file__).resolve().parent.parent
SCHNAPPSCHUSS = REPO / "docs" / "context" / "einstellungen_neu" / "daten" / "kuerzel_bedeutung.json"
I18N = REPO / "src" / "i18n" / "messages"
QUELLE = [
    "src/app/metric_catalog.py (kuerzel_bedeutung_de/en)",
    "src/i18n/messages/{de,en}/vergleich.json (vergleich.sms.ort_nummer)",
]


def erwartet() -> dict:
    """Schnappschuss aus dem echten Katalog: DE-Bedeutung → EN-Bedeutung, Katalog-Reihenfolge, je DE einmal."""
    paare: dict[str, str] = {}
    for m in _METRICS:
        for k, de in m.kuerzel_bedeutung_de.items():
            paare.setdefault(de, m.kuerzel_bedeutung_en[k])
    lies = lambda sprache: json.loads((I18N / sprache / "vergleich.json").read_text(encoding="utf-8"))
    paare.setdefault(lies("de")["vergleich.sms.ort_nummer"], lies("en")["vergleich.sms.ort_nummer"])
    return {"quelle": QUELLE, "bedeutungen": [{"de": de, "en": en} for de, en in paare.items()]}


def lade() -> dict:
    assert SCHNAPPSCHUSS.exists(), f"Schnappschuss fehlt: {SCHNAPPSCHUSS.relative_to(REPO)}"
    return json.loads(SCHNAPPSCHUSS.read_text(encoding="utf-8"))


def test_schnappschuss_entspricht_dem_katalog():
    assert lade() == erwartet()


def test_jede_de_bedeutung_hat_genau_eine_en_bedeutung():
    """Eindeutig: dieselbe DE-Bedeutung meint im Katalog überall dieselbe EN-Bedeutung."""
    je_de: dict[str, set[str]] = {}
    for m in _METRICS:
        for k, de in m.kuerzel_bedeutung_de.items():
            je_de.setdefault(de, set()).add(m.kuerzel_bedeutung_en.get(k))
    mehrdeutig = {de: en for de, en in je_de.items() if len(en) != 1 or None in en}
    assert mehrdeutig == {}


def test_legenden_beispiele_der_spec():
    paare = {p["de"]: p["en"] for p in lade()["bedeutungen"]}
    assert paare["N gefühlt"] == "N feels like"
    assert paare["D gefühlt"] == "D feels like"
    assert paare["Böen"] == "gusts"
    assert paare["Ort 1 in der Reihenfolge des Abos"] == "Location 1 in the order of the subscription"
