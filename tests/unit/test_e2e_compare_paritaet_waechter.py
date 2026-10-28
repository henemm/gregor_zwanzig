# doc-compliance-test
"""Paritaets-Waechter fuer Compare-E2E-Specs (#2347 S1, Epic #2345 Etappe P6).

Konventions-/Ratschenwaechter ueber TESTDATEIEN (`frontend/e2e/*.spec.ts`), kein
Verhaltensnachweis und kein Lesen von Produkt-Quelltext (`src/`/`api/`/`internal/`/
`cmd/`) -- dasselbe Muster wie `test_e2e_positivliste_ratschen_bindung.py`.

Regeln (Spec `docs/specs/modules/feat_2347_s1_paritaets_e2e.md`, AC-3):
- Regel 1: jede `*compare*.spec.ts` hat eine kind-Schleife (`HUB_KINDS` oder das
  Altmuster `for (const ... of ['Trip', 'Vergleich'])`) oder einen
  `gz-eigenstaendig:`-Kopf (erste 30 Zeilen, mind. 15 Zeichen Begruendung).
- Regel 2 (gegen Umgehung per Dateiname): jede andere Spec, die den Compare-Hub-Reiter
  (`compare-detail-tab`) ansteuert und weder `trip-detail-tab` noch `/trips/` noch eine
  kind-Schleife noch einen Kopf enthaelt, ist ein Verstoss.
- Ratschenmodus: `ALTLAST` darf nur schrumpfen -- toter oder inzwischen konformer
  Eintrag ist rot, ebenso `len(ALTLAST) != ALTLAST_MAX` (die Obergrenze muss dem
  echten Stand entsprechen, sonst entsteht unbemerkt Wachstums-Spielraum).

Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
Pruefdatum (Regel-Budget): 2027-01-24 -- kein nachweisbarer Fang => Rueckbau.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
E2E_DIR = REPO / "frontend" / "e2e"

MARKER = "gz-eigenstaendig:"
MIN_BEGRUENDUNG = 15
KOPF_ZEILEN = 30
PRUEFDATUM = date(2027, 1, 24)

# Explizite Altlastliste (nur Dateinamen). Am ENDSTAND von S2 gemessen
# (2026-10-26: 39 x Regel 1, 2 x Regel 2); S3a (2026-10-27): 6 Altdateien in
# hub-*-Specs zusammengefuehrt, compare-editor-slice3 per gz-eigenstaendig:-Kopf
# konform => 32 x Regel 1, 2 x Regel 2 = 34; S3b (2026-10-28): Versand-Gruppe
# (compare-versand-speichert-selbst, compare-hub-versand-inline,
# compare-hub-briefing-times, versand-tab-vergleich) in hub-versand-*-Specs
# zusammengefuehrt => 29 x Regel 1, 1 x Regel 2 = 30; darf nur schrumpfen (S4 leert sie).
ALTLAST: frozenset[str] = frozenset({
    "compare-active-metrics-format.staging.spec.ts",
    "compare-alarm-config.spec.ts",
    "compare-detail-edit-entry.spec.ts",
    "compare-edit-redirect.spec.ts",
    "compare-editor-autosave.spec.ts",
    "compare-editor-fidelity-s8d.spec.ts",
    "compare-editor-slice1.spec.ts",
    "compare-editor-slice4.spec.ts",
    "compare-flow-navigation.spec.ts",
    "compare-hourly-metric-order.spec.ts",
    "compare-hub-fidelity-s8c.spec.ts",
    "compare-hub-inline-edit.spec.ts",
    "compare-konfliktschutz-zwei-kontexte.spec.ts",
    "compare-layout-tab-dissolution.spec.ts",
    "compare-legacy-fields-survive-save.spec.ts",
    "compare-metric-order.spec.ts",
    "compare-neu-kanal-anlegen.staging.spec.ts",
    "compare-new-vorlage.spec.ts",
    "compare-outlook-metric-selection.staging.spec.ts",
    "compare-radar-toggle.spec.ts",
    "compare-stundenverlauf-wertprops.spec.ts",
    "compare-uebersicht-kanal-bedienung.staging.spec.ts",
    "compare-uebersicht-kanal-persistenz.staging.spec.ts",
    "feat-1461-s3b2b-compare-kanal-schwelle.spec.ts",
    "fix-1350-compare-metric-select.staging.spec.ts",
    "fix-1350t3-compare-threshold-source.staging.spec.ts",
    "issue-1080-compare-new-url.spec.ts",
    "issue-1093-compare-layout-crash.spec.ts",
    "issue-682-compare-editor-mobile.spec.ts",
    # Regel 2 (Compare-Hub-Reiter ohne Trip-Gegenstueck, Umgehung per Dateiname)
    "kanal-grenzen-ortsvergleich.staging.spec.ts",
})
# Literal, NICHT len(ALTLAST) -- sonst waechst die Obergrenze mit jedem neuen
# Eintrag mit und die Pruefung waere vakuum (Adversary F002). Darf nur sinken,
# und zwar nur im selben Zug wie eine ALTLAST-Streichung: der Wert muss stets
# gleich len(ALTLAST) sein (#2347 S3a, Adversary F001).
ALTLAST_MAX = 29

_SCHLEIFE_RE = re.compile(
    r"\bHUB_KINDS\b"
    r"|for\s*\(\s*const\s+\w+\s+of\s+\[\s*['\"]Trip['\"]\s*,\s*['\"]Vergleich['\"]\s*\]"
)


def _hat_schleife(text: str) -> bool:
    return bool(_SCHLEIFE_RE.search(text))


def _kopf_begruendung(text: str) -> str | None:
    """Begruendungstext hinter `gz-eigenstaendig:` in den ersten 30 Zeilen, sonst None."""
    for zeile in text.splitlines()[:KOPF_ZEILEN]:
        pos = zeile.find(MARKER)
        if pos >= 0:
            return zeile[pos + len(MARKER):].strip()
    return None


def _verstoss(name: str, text: str) -> str | None:
    """Grund des Verstosses gegen Regel 1/2, None = konform bzw. nicht betroffen."""
    begruendung = _kopf_begruendung(text)
    if begruendung is not None and len(begruendung) < MIN_BEGRUENDUNG:
        return (f"`{MARKER}`-Kopf mit nur {len(begruendung)} Zeichen Begruendung "
                f"(mind. {MIN_BEGRUENDUNG})")
    gedeckt = _hat_schleife(text) or begruendung is not None
    if "compare" in name:
        return None if gedeckt else (
            "Regel 1: Compare-Spec ohne kind-Schleife (HUB_KINDS) und ohne "
            f"`{MARKER}`-Kopf -- Trip-Pendant fehlt")
    if "compare-detail-tab" in text and not gedeckt \
            and "trip-detail-tab" not in text and "/trips/" not in text:
        return ("Regel 2: steuert den Compare-Hub-Reiter (compare-detail-tab) an, "
                "hat aber kein Trip-Gegenstueck, keine kind-Schleife und keinen "
                f"`{MARKER}`-Kopf (Umgehung per Dateiname)")
    return None


def pruefe_compare_specs(dateien: dict[str, str], altlast: frozenset[str]) -> list[str]:
    """Befunde ueber `{dateiname: inhalt}` aller `*.spec.ts`; leer = in Ordnung."""
    befunde: list[str] = []
    for name in sorted(dateien):
        grund = _verstoss(name, dateien[name])
        if grund and name not in altlast:
            befunde.append(f"{name}: {grund}")
    for name in sorted(altlast):
        if name not in dateien:
            befunde.append(f"{name}: ALTLAST-Eintrag zeigt auf keine Datei mehr -- "
                           f"Eintrag entfernen (die Liste darf nur schrumpfen)")
        elif _verstoss(name, dateien[name]) is None:
            befunde.append(f"{name}: ist inzwischen konform -- ALTLAST-Eintrag entfernen")
    return befunde


def _echter_baum() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(E2E_DIR.glob("*.spec.ts"))}


# ─── echter Baum ──────────────────────────────────────────────────────────────

def test_echter_baum_hat_keine_unbegruendete_compare_only_spec():
    befunde = pruefe_compare_specs(_echter_baum(), ALTLAST)
    assert befunde == [], "Paritaets-Verstoesse in frontend/e2e/:\n" + "\n".join(befunde)


def test_altlast_waechst_nicht_ueber_den_einfuehrungsstand():
    assert len(ALTLAST) <= ALTLAST_MAX, (
        f"ALTLAST hat {len(ALTLAST)} Eintraege, erlaubt sind hoechstens {ALTLAST_MAX} "
        f"-- neue Compare-only-Specs brauchen eine kind-Schleife oder einen Kopf")


def test_altlast_obergrenze_entspricht_dem_echten_stand():
    # Ohne Gleichheit liesse ein zu hoch stehendes ALTLAST_MAX stillen Spielraum
    # fuer neue Altlast-Eintraege (Adversary F001).
    assert len(ALTLAST) == ALTLAST_MAX, (
        f"ALTLAST hat {len(ALTLAST)} Eintraege, ALTLAST_MAX steht auf {ALTLAST_MAX} "
        f"-- ALTLAST_MAX muss dem echten Stand entsprechen und darf nur zusammen "
        f"mit einer Streichung aus ALTLAST sinken (nie vorab hoeher stehen lassen)")


def test_echter_baum_ist_nicht_leer():
    # Schutz gegen vakuum-gruen: falscher Pfad => keine Datei => keine Befunde.
    baum = _echter_baum()
    assert len([n for n in baum if "compare" in n]) >= 10, f"E2E-Ordner nicht gefunden: {E2E_DIR}"


# ─── synthetische Selbsttests (AC-3-Mutationen) ───────────────────────────────

KOPF_OK = "// gz-eigenstaendig: Orte-Tab ohne Trip-Pendant (Etappen statt Orte)\n"
SCHLEIFE_ALT = "for (const hub of ['Trip', 'Vergleich'] as const) {\n  test(`x ${hub}`, () => {});\n}\n"
SCHLEIFE_NEU = "import { HUB_KINDS } from './helpers';\nfor (const kind of HUB_KINDS) {}\n"


@pytest.mark.parametrize("inhalt", [KOPF_OK, SCHLEIFE_ALT, SCHLEIFE_NEU], ids=["kopf", "altmuster", "hub_kinds"])
def test_gedeckte_compare_spec_ist_konform(inhalt):
    assert pruefe_compare_specs({"compare-neu.spec.ts": inhalt}, frozenset()) == []


def test_neue_compare_spec_ohne_kopf_ist_rot():
    befunde = pruefe_compare_specs({"compare-neu.spec.ts": "test('x', () => {});\n"}, frozenset())
    assert len(befunde) == 1 and "compare-neu.spec.ts" in befunde[0] and "Regel 1" in befunde[0]


def test_marker_mit_zu_kurzer_begruendung_ist_rot():
    befunde = pruefe_compare_specs({"compare-neu.spec.ts": "// gz-eigenstaendig: zu kurz\n"}, frozenset())
    assert len(befunde) == 1 and "Zeichen Begruendung" in befunde[0]


def test_kurzer_marker_ist_auch_mit_schleife_rot():
    inhalt = "// gz-eigenstaendig: kurz\n" + SCHLEIFE_NEU
    assert len(pruefe_compare_specs({"compare-neu.spec.ts": inhalt}, frozenset())) == 1


def test_marker_hinter_zeile_30_zaehlt_nicht():
    # Literal 30 statt KOPF_ZEILEN -- sonst wuerde eine Aufweitung der Konstante
    # den Selbsttest mitziehen und gruen bleiben (Adversary F003).
    assert KOPF_ZEILEN == 30, "Kopf = erste 30 Zeilen (Muster pendant_gate.py)"
    inhalt = "\n" * 30 + KOPF_OK  # Marker in Zeile 31
    befunde = pruefe_compare_specs({"compare-neu.spec.ts": inhalt}, frozenset())
    assert len(befunde) == 1 and "Regel 1" in befunde[0]


def test_marker_in_zeile_30_zaehlt_noch():
    inhalt = "\n" * 29 + KOPF_OK  # Marker in Zeile 30
    assert pruefe_compare_specs({"compare-neu.spec.ts": inhalt}, frozenset()) == []


def test_umgehung_per_dateiname_ist_rot():
    inhalt = "await page.getByTestId('compare-detail-tab-alarme').click();\n"
    befunde = pruefe_compare_specs({"x-hub.spec.ts": inhalt}, frozenset())
    assert len(befunde) == 1 and "Regel 2" in befunde[0]


@pytest.mark.parametrize("zusatz", [
    "await page.goto(`/trips/${id}`);\n",
    "await page.getByTestId('trip-detail-tab-alarme').click();\n",
    SCHLEIFE_NEU,
    KOPF_OK,
], ids=["trips_url", "trip_tab", "schleife", "kopf"])
def test_hub_spec_mit_trip_gegenstueck_ist_konform(zusatz):
    inhalt = zusatz + "await page.getByTestId('compare-detail-tab-alarme').click();\n"
    assert pruefe_compare_specs({"x-hub.spec.ts": inhalt}, frozenset()) == []


def test_spec_ohne_compare_bezug_ist_nicht_betroffen():
    assert pruefe_compare_specs({"login.spec.ts": "test('x', () => {});\n"}, frozenset()) == []


def test_altlast_deckt_verstoss():
    assert pruefe_compare_specs({"compare-alt.spec.ts": "test('x');\n"},
                                frozenset({"compare-alt.spec.ts"})) == []


def test_toter_altlast_eintrag_ist_rot():
    befunde = pruefe_compare_specs({}, frozenset({"compare-geloescht.spec.ts"}))
    assert len(befunde) == 1 and "keine Datei mehr" in befunde[0]


def test_konformer_altlast_eintrag_ist_rot():
    befunde = pruefe_compare_specs({"compare-alt.spec.ts": SCHLEIFE_NEU},
                                   frozenset({"compare-alt.spec.ts"}))
    assert len(befunde) == 1 and "inzwischen konform" in befunde[0]
