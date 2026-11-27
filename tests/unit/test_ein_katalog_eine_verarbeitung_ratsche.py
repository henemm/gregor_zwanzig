"""Ratsche „Ein Katalog, eine Verarbeitung“ (ADR-0127, Issue #3260 Schritt 1a).

SPEC: docs/specs/modules/feat_3260_s1a_ratsche_ein_katalog.md — AC-1..AC-6.

Metrik-Wissen steht nur in ``src/app/metric_catalog.py``, Metrik-Verarbeitung
nur in ``src/output/metric_format``. Der heutige Bestand ausserhalb steht je
Datei und Art als Anzahl in ``tests/unit/ein_katalog_ausnahmen.json`` und darf
nur schrumpfen. Der Erkennungs-Kern liegt in
``tests/helpers/katalog_verarbeitung_scan.py``; die Gegenproben schreiben
erfundene Verstoesse in ein temporaeres Verzeichnis, damit die Ratsche nicht
nur am Bestand gruen ist, ohne je etwas geprueft zu haben.

Liste nach einem Abbau neu erzeugen (der Test schreibt nie)::

    uv run python -m tests.helpers.katalog_verarbeitung_scan --schreibe-ausnahmen

Danach ``HOECHSTSTAND`` unten auf den neuen ``hoechststand`` senken.

Regel-Budget: Pruefdatum 2027-02-19 (ersetzt die Entdeckungsstufe der
Metrik-Listen-Ratsche aus #1856).
"""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from tests.helpers.katalog_verarbeitung_scan import (
    ARTEN, FRONTEND_LISTE, FRONTEND_SCHWELLE, GO_LISTE, GO_SCHWELLE, ID_SAMMLUNG,
    ID_VERZWEIGUNG, MAIN_REF, SCHWELLE, VALIDATOR_IMPORT, Fund, lade_ausnahmen,
    lade_main_ausnahmen, scanne_alles, scanne_frontend, scanne_go, scanne_python,
    scanne_validatoren, vergleiche, vergleiche_mit_main,
)

#: Festgeschriebener Hoechststand (Regel d). Wird nur gesenkt, nie erhoeht.
HOECHSTSTAND = 411  # #3458: -1 (alertPreviewHelpers.ts geloescht); #2994: -1 (Handliteral AlertableMetrics in trip.go durch go:embed ersetzt); #3425: -2 (Stundenzellen-Bausteine der Vergleichsmail geteilt); #2992: -1 (RENDERER_TO_TRIP_METRIC_ID geloescht); #2988 S4: -1 (windrichtungUngueltig im Ampel-Spiegel geloescht); #3384 S4: -8 (alertMetricCatalogIds 2, weatherEmoji 6 geloescht); #3383 S1: -3; #3020 R2: -5 (BucketSectionOff 1, TablePreview 4 geloescht)

#: Arten ohne Fund im heutigen Bestand. Ihre Wirksamkeit belegen allein die
#: Gegenproben unten (Go haelt heute keinen festen Messwert-Vergleich).
OHNE_BESTAND = frozenset({GO_SCHWELLE})


@pytest.fixture(scope="module")
def bestand() -> list[Fund]:
    return scanne_alles()


@pytest.fixture(scope="module")
def ausnahmen() -> dict:
    return lade_ausnahmen()


def _schreibe(wurzel: Path, rel: str, text: str) -> Path:
    pfad = wurzel / rel
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")
    return pfad


def _kurz(funde: list[Fund]) -> list[tuple[str, int, str]]:
    return [(f.datei, f.zeile, f.art) for f in funde]


# ------------------------------------------------------------------ AC-1

def test_bestand_entspricht_der_ausnahmeliste(bestand, ausnahmen):
    """AC-1: heutiger Stand + vollstaendige Liste = gruen (Regeln a–d)."""
    befunde = vergleiche(bestand, ausnahmen, HOECHSTSTAND)
    assert not befunde, "Ratsche Ein Katalog (ADR-0127):\n" + "\n".join(befunde)


def test_jede_art_findet_im_bestand_mindestens_eine_stelle(bestand):
    """AC-1: Nichtstun ist kein Bestehen — jede Erkennung arbeitet im echten Baum."""
    gefunden = {f.art for f in bestand}
    fehlend = [art for art in ARTEN if art not in gefunden and art not in OHNE_BESTAND]
    assert not fehlend, f"Erkennung ohne Fund im Bestand (ausgeschaltet?): {fehlend}"
    assert not (OHNE_BESTAND & gefunden), (
        f"{sorted(OHNE_BESTAND & gefunden)} hat jetzt Bestand: aus OHNE_BESTAND streichen")


def test_liste_waechst_nicht_gegenueber_main(ausnahmen):
    """Regel e: Liste und Konstante gemeinsam anheben ist kein Ausweg."""
    main, grund = lade_main_ausnahmen()
    if main is None:
        pytest.skip(f"Regel e uebersprungen — {grund}")
    befunde = vergleiche_mit_main(ausnahmen, main)
    assert not befunde, "\n".join(befunde)


def test_bekannte_fundstellen_der_bestandsaufnahme_werden_erkannt(bestand):
    """AC-1: Stichproben aus docs/context/3260/ (je Art eine bekannte Stelle)."""
    stellen = {(f.datei, f.art) for f in bestand}
    erwartet = {
        ("frontend/src/lib/components/trip-detail/metricsEditor.ts", FRONTEND_LISTE),
        ("internal/model/trip.go", GO_LISTE),
        ("src/output/renderers/compact_summary.py", SCHWELLE),
        ("src/services/weather_metrics.py", "VERARBEITUNG_AUSSEN"),
        ("src/output/renderers/email/helpers.py", ID_SAMMLUNG),
        ("src/output/renderers/email/helpers.py", ID_VERZWEIGUNG),
        (".claude/hooks/_soll_aus_konfiguration.py", VALIDATOR_IMPORT),
        ("internal/handler/ampel.go", "GO_VERZWEIGUNG"),
        # #2988 S4: die Stelle in ampelModell.ts (Spiegel windrichtungUngueltig) faellt weg.
        ("frontend/src/lib/components/ui/wicon/WIcon.svelte", "FRONTEND_VERZWEIGUNG"),
    }
    assert erwartet <= stellen, f"nicht erkannt: {sorted(erwartet - stellen)}"
    windworte = {f.zeile for f in bestand
                 if f.datei == "src/output/renderers/compact_summary.py" and f.art == SCHWELLE
                 and "speed >" in f.auszug}
    assert len(windworte) == 3, f"Wind-Wortgrenzen 60/35/15 nicht alle erkannt: {windworte}"


# ------------------------------------------------------------ AC-2/AC-3/AC-4

R = "src/output/renderers/neu_renderer.py"


@pytest.mark.parametrize(("text", "zeile", "art"), [
    ('"""Renderer."""\n\nZWEITE = ("wind", "gust")\n', 3, ID_SAMMLUNG),
    ('def zelle(wind_kmh):\n    if wind_kmh > 40:\n        return "stark"\n    return ""\n',
     2, SCHWELLE),
    ('def zelle(wind_kmh):\n    if 40 < wind_kmh:\n        return "stark"\n    return ""\n',
     2, SCHWELLE),
    ('def zelle(wind_kmh):\n    if wind_kmh >= 40.0:\n        return "stark"\n    return ""\n',
     2, SCHWELLE),
    ('def zelle(metric_id):\n    if metric_id == "precipitation":\n        return 1\n',
     2, ID_VERZWEIGUNG),
])
def test_renderer_mit_zweiter_liste_oder_schwelle_meldet_genau_seine_art(
        tmp_path, text, zeile, art):
    """AC-2: genau die eine Art, mit Datei und Zeile."""
    _schreibe(tmp_path, R, text)
    assert _kurz(scanne_python([tmp_path / "src"], tmp_path)) == [(R, zeile, art)]


def test_neuer_verstoss_im_renderer_macht_die_ratsche_rot(tmp_path, bestand, ausnahmen):
    """AC-2: im Gesamtvergleich nennt die Meldung Datei, Zeile und Art."""
    _schreibe(tmp_path, R, 'def zelle(wind_kmh):\n    return wind_kmh > 40\n')
    neu = scanne_python([tmp_path / "src"], tmp_path)
    befunde = vergleiche(bestand + neu, ausnahmen, HOECHSTSTAND)
    assert len(befunde) == 1 and befunde[0].startswith("(a)")
    assert f"{R}:2 [{SCHWELLE}] return wind_kmh > 40" in befunde[0]


def test_zusaetzlicher_fund_in_gelisteter_datei_nennt_alle_stellen(bestand, ausnahmen):
    """Regel a: die Meldung listet JEDE Fundstelle dieser Datei/Art."""
    vorlage = next(f for f in bestand if f.art == SCHWELLE)
    gleich = [f for f in bestand if f.datei == vorlage.datei and f.art == SCHWELLE]
    extra = Fund(vorlage.datei, 99999, SCHWELLE, "if wind > 1:")
    befunde = vergleiche(bestand + [extra], ausnahmen, HOECHSTSTAND)
    assert len(befunde) == 1
    for fund in [*gleich, extra]:
        assert f"{fund.datei}:{fund.zeile} [{SCHWELLE}]" in befunde[0]


def test_frontend_liste_mit_zwei_kennungen_meldet_datei_und_zeile(tmp_path):
    """AC-3 (Frontend)."""
    rel = "frontend/src/lib/neu.ts"
    _schreibe(tmp_path, rel, '// Liste\n\nconst X = ["wind", "gust"];\n')
    assert _kurz(scanne_frontend([tmp_path / "frontend" / "src"], tmp_path)) == [
        (rel, 3, FRONTEND_LISTE)]


def test_go_map_mit_zwei_kennungen_meldet_datei_und_zeile(tmp_path):
    """AC-3 (Go)."""
    rel = "internal/neu/neu.go"
    _schreibe(tmp_path, rel,
              'package neu\n\nvar X = map[string]float64{"wind": 1, "gust": 2}\n')
    assert _kurz(scanne_go([tmp_path / "internal"], tmp_path)) == [(rel, 3, GO_LISTE)]


@pytest.mark.parametrize("zeile", [
    "if (wind_kmh > 40) { x = 1; }",
    "if (40 < wind_kmh) { x = 1; }",
    "if (row.gust_kmh >= -5.5) { x = 1; }",
    "if (row?.precip_mm <= 2) { x = 1; }",
])
def test_frontend_schwelle_auf_messwert_meldet_datei_und_zeile(tmp_path, zeile):
    """F002 (Frontend): fester Vergleich eines Messwerts, beide Seiten, Member-Ausdruck."""
    rel = "frontend/src/lib/neu_schwelle.ts"
    _schreibe(tmp_path, rel, f"// 40 < wind_kmh im Kommentar zaehlt nicht\n\n{zeile}\n")
    assert _kurz(scanne_frontend([tmp_path / "frontend" / "src"], tmp_path)) == [
        (rel, 3, FRONTEND_SCHWELLE)]


def test_svelte_schwelle_im_markup_wird_erkannt(tmp_path):
    rel = "frontend/src/lib/Neu.svelte"
    _schreibe(tmp_path, rel, "<script>\n  let x = 1;\n</script>\n{#if cloud_pct > 80}<b/>{/if}\n")
    assert _kurz(scanne_frontend([tmp_path / "frontend" / "src"], tmp_path)) == [
        (rel, 4, FRONTEND_SCHWELLE)]


@pytest.mark.parametrize("zeile", [
    "\tif windKmh > 40 {\n\t\treturn\n\t}",
    "\tif 40 < s.GustKmh {\n\t\treturn\n\t}",
    "\tif temp <= -5 {\n\t\treturn\n\t}",
])
def test_go_schwelle_auf_messwert_meldet_datei_und_zeile(tmp_path, zeile):
    """F002 (Go): heute ohne Bestand, die Gegenprobe belegt die Erkennung."""
    rel = "internal/neu/schwelle.go"
    _schreibe(tmp_path, rel, f"package neu\n\nfunc f() {{\n{zeile}\n}}\n")
    assert _kurz(scanne_go([tmp_path / "internal"], tmp_path)) == [(rel, 4, GO_SCHWELLE)]


def test_validator_mit_produktimport_meldet_den_import(tmp_path):
    """AC-4: Import einer Produktliste, auch verzoegert in einer Funktion."""
    rel = ".claude/hooks/neu_validator.py"
    _schreibe(tmp_path, rel,
              "from app.metric_catalog import AMPEL_METRIC_IDS\n\n\n"
              "def soll():\n    from output.renderers.email.helpers import fmt_val\n"
              "    return fmt_val\n")
    assert _kurz(scanne_validatoren([tmp_path / ".claude" / "hooks"], tmp_path)) == [
        (rel, 1, VALIDATOR_IMPORT), (rel, 5, VALIDATOR_IMPORT)]


def test_validator_mit_handgeschriebener_erwartung_meldet_nichts(tmp_path):
    """AC-4: das Soll von Hand ist die erlaubte Ausnahme (ADR-0127 Nr. 5)."""
    _schreibe(tmp_path, ".claude/hooks/hand_validator.py",
              'import re\n_AMPEL_SPALTEN = ("wind", "gust", "precipitation")\n\n\n'
              'def pruefe(spalte, wert):\n    return spalte == "wind" and wert > 30\n')
    assert scanne_validatoren([tmp_path / ".claude" / "hooks"], tmp_path) == []


def test_validator_import_zaehlt_nur_metrik_wissen(tmp_path):
    """AC-4 (Tech-Lead-Entscheid): Konfiguration, Texte und Modelle sind kein
    Metrik-Wissen; ``app.*metric*``/``app.*compare*`` und ``services.*`` schon."""
    rel = ".claude/hooks/misch_validator.py"
    _schreibe(tmp_path, rel,
              "from app.config import Settings\nfrom i18n import t\n"
              "from app.models import AlertMetric\nimport app.user\n"
              "from app.compare_metrics import X\nimport services.placements\n")
    assert _kurz(scanne_validatoren([tmp_path / ".claude" / "hooks"], tmp_path)) == [
        (rel, 5, VALIDATOR_IMPORT), (rel, 6, VALIDATOR_IMPORT)]


def test_erlaubte_orte_werden_nicht_gescannt(tmp_path):
    """Katalog und Verarbeitungsmodul duerfen Metrik-Wissen halten."""
    for rel in ("src/app/metric_catalog.py", "src/output/metric_format.py"):
        _schreibe(tmp_path, rel, 'L = ("wind", "gust")\n\n\ndef f(wind):\n'
                                 '    return wind > 40\n')
    assert scanne_python([tmp_path / "src"], tmp_path) == []


# ------------------------------------------------------------------ AC-5

def test_abgebaute_stelle_ohne_verkleinerte_liste_macht_rot(bestand, ausnahmen):
    """AC-5 / Regel b: weniger Funde als gelistet verlangt das Verkleinern."""
    weg = bestand[0]
    befunde = vergleiche(bestand[1:], ausnahmen, HOECHSTSTAND)
    assert len(befunde) == 1 and befunde[0].startswith("(b)")
    assert weg.datei in befunde[0] and "verkleinern" in befunde[0]


def test_erhoehte_anzahl_in_der_liste_macht_rot(bestand, ausnahmen):
    """AC-5 / Regeln b und c: eine Anzahl hochsetzen ist kein Ausweg."""
    erhoeht = copy.deepcopy(ausnahmen)
    datei = next(iter(erhoeht["eintraege"]))
    art = next(iter(erhoeht["eintraege"][datei]))
    erhoeht["eintraege"][datei][art] += 1
    befunde = vergleiche(bestand, erhoeht, HOECHSTSTAND)
    assert any(b.startswith("(b)") and datei in b for b in befunde)
    assert any(b.startswith("(c)") for b in befunde)


def test_erhoehter_hoechststand_macht_rot(bestand, ausnahmen):
    """AC-5 / Regel d: der Hoechststand der Liste steigt nie ueber die Konstante."""
    erhoeht = copy.deepcopy(ausnahmen)
    erhoeht["hoechststand"] = HOECHSTSTAND + 1
    befunde = vergleiche(bestand, erhoeht, HOECHSTSTAND)
    assert befunde == [befunde[0]] and befunde[0].startswith("(d)")


def test_neue_datei_mit_erhoehtem_hoechststand_bleibt_rot(tmp_path, bestand, ausnahmen):
    """AC-5: neuer Eintrag + hoeherer Hoechststand in der Liste — trotzdem rot (d)."""
    _schreibe(tmp_path, R, 'L = ("wind", "gust")\n')
    neu = scanne_python([tmp_path / "src"], tmp_path)
    erweitert = copy.deepcopy(ausnahmen)
    erweitert["eintraege"][R] = {ID_SAMMLUNG: 1}
    erweitert["hoechststand"] += 1
    befunde = vergleiche(bestand + neu, erweitert, HOECHSTSTAND)
    assert [b[:3] for b in befunde] == ["(d)"]


# ------------------------------------------------------------------ AC-6

def test_harmlose_dateien_melden_nichts(tmp_path):
    """AC-6: Laengenvergleich und Liste fremder Woerter sind kein Metrik-Wissen."""
    _schreibe(tmp_path, R, 'def f(items):\n    if len(items) > 2:\n'
                           '        return ("a", "b")\n    return None\n')
    _schreibe(tmp_path, "frontend/src/lib/harmlos.ts",
              'const X = ["a", "b"];\nif (x === "a") {}\n')
    _schreibe(tmp_path, "internal/harmlos/h.go",
              'package harmlos\n\nvar X = map[string]int{"a": 1, "b": 2}\n')
    assert scanne_python([tmp_path / "src"], tmp_path) == []
    assert scanne_frontend([tmp_path / "frontend" / "src"], tmp_path) == []
    assert scanne_go([tmp_path / "internal"], tmp_path) == []


def test_harmlose_vergleiche_in_ts_und_go_melden_nichts(tmp_path):
    """AC-6: Laenge, Zaehler, Fenster, Aufruf und Kanal-Sendung sind keine Schwelle."""
    _schreibe(tmp_path, "frontend/src/lib/h2.ts",
              "if (items.length > 2 && value.length > 0 && attempt < 3) {}\n"
              "if (day_window_start >= 0 && Math.max(a, b) > 3) {}\n"
              "const f = (x: Array<number>) => x;\n")
    _schreibe(tmp_path, "internal/harmlos/h2.go",
              "package harmlos\n\nfunc g(ch chan int, items []int) {\n"
              "\tif len(items) > 2 {\n\t\tch <- 5\n\t}\n}\n")
    assert scanne_frontend([tmp_path / "frontend" / "src"], tmp_path) == []
    assert scanne_go([tmp_path / "internal"], tmp_path) == []


# ------------------------------------------------------------- Regel e (main)

def _main_liste(daten: dict):
    return lambda ref: json.dumps(daten)


def test_regel_e_hoechststand_ueber_main_macht_rot(ausnahmen):
    main = copy.deepcopy(ausnahmen)
    erhoeht = copy.deepcopy(ausnahmen)
    erhoeht["hoechststand"] += 1
    geladen, _ = lade_main_ausnahmen(_main_liste(main))
    assert vergleiche_mit_main(ausnahmen, geladen) == []
    befunde = vergleiche_mit_main(erhoeht, geladen)
    assert len(befunde) == 1 and befunde[0].startswith("(e) hoechststand")


def test_regel_e_hoehere_anzahl_als_main_macht_rot(ausnahmen):
    datei = next(iter(ausnahmen["eintraege"]))
    art = next(iter(ausnahmen["eintraege"][datei]))
    erhoeht = copy.deepcopy(ausnahmen)
    erhoeht["eintraege"][datei][art] += 1
    geladen, _ = lade_main_ausnahmen(_main_liste(ausnahmen))
    befunde = vergleiche_mit_main(erhoeht, geladen)
    assert len(befunde) == 1 and befunde[0].startswith(f"(e) {datei} [{art}]")


def test_regel_e_neuer_eintrag_ohne_main_pendant_bleibt_erlaubt(ausnahmen):
    """Neue Eintraege faengt Regel a/d; e vergleicht nur bestehende Eintraege."""
    erweitert = copy.deepcopy(ausnahmen)
    erweitert["eintraege"]["src/neu.py"] = {SCHWELLE: 1}
    geladen, _ = lade_main_ausnahmen(_main_liste(ausnahmen))
    assert vergleiche_mit_main(erweitert, geladen) == []


def test_regel_e_ohne_git_liefert_grund_statt_stillem_gruen():
    def kein_git(ref):
        raise subprocess.CalledProcessError(128, ["git", "show", ref],
                                            stderr="fatal: invalid object name 'origin/main'")
    geladen, grund = lade_main_ausnahmen(kein_git)
    assert geladen is None and MAIN_REF in grund and "invalid object name" in grund
