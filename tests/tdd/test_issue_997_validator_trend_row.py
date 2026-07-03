"""TDD — Issue #997: Trend-/Stats-Tabellenzeilen vergiften Spalten-Checks.

Beweist Verhalten (kein Mock, keine Dateiinhalt-Checks):
Der Briefing-Mail-Validator mappt den Spalten-Index über die th-Reihe. Vor dem
Fix sammelte er th/td GLOBAL über das ganze Dokument. Echte Mails haben aber
mehrere Tabellen mit je eigener th-Reihe: eine oder mehrere Stundentabellen (je
Etappe) plus die 9-spaltige Trend-/Stats-Tabelle (Mail-Redesign #898-901,
src/output/renderers/email/html.py:1148-1157). Global summierten sich die
Spaltenzahlen, der Guard `len(cells) == len(headers)` matchte gegen die GLOBALE
Summe → keine reale Zeile passte → `_column_values()` lieferte `[]` → die
Regen-/Sonnen-Plausibilitätsregeln waren bei jeder realen Full-Mail mit Trend
stumm (False-Negative, der das Renderer-Commit-Gate #811 aushöhlt).

Fix (Spec docs/specs/modules/fix_997_validator_bundle.md): Header/Zeilen pro
`<table>`-Block scopen; nur Blöcke, deren eigene th-Reihe den Spaltennamen führt,
zählen; innerhalb eines Blocks nur Zeilen mit `len(cells) == len(block_headers)`.
Werte über alle passenden Blöcke aggregieren (Mehr-Etappen-Summenverhalten bleibt).
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "briefing_mail_validator.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))  # Sibling-Test-Helfer

# 14-spaltiger Header wie in der live zugestellten Mail (Spec #997, Diagnose
# 2026-07-03). "Rain" liegt an Index 6.
_HEADERS = [
    "Time", "Temp", "Feels", "Wind", "Gust", "WDir",
    "Rain", "Rain%", "Thdr", "Thndr%", "Cloud", "Visib", "Risk", "Time",
]

# Realistische Trend-/Stats-th-Reihe (9 Spalten) — 1:1 wie der echte Renderer
# (html.py:1148-1157). KEINE davon heißt "Rain"; unter korrektem Scoping trägt
# der Trend-Block daher nichts zur Rain-Spalte bei.
_TREND_HEADERS = ["Tag", "N", "D", "R", "PR", "Wind", "Böen", "Gew", "ACC"]

# Trend-Datenzeile mit 9 Zellen: Index 6 trägt den Böen-Wert '35' der Trend-Zeile
# — am selben Spalten-INDEX wie "Rain" der Stundentabelle, aber inhaltlich fremd.
_TREND_ROW_CELLS = ["So", "31°", "37°", "0.0", "0%", "16", "35", "–", ""]


def _load_validator():
    """Lade den Validator als isoliertes Modul (vermeidet sys.modules-Kontamination)."""
    spec = importlib.util.spec_from_file_location("bmv997", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hour_row(hour: str, rain: str = "0.0") -> str:
    """Eine 14-zellige Stundenzeile — Rain-Spalte (idx 6) explizit steuerbar."""
    cells = [hour, "15°C", "14°C", "10", "15", "180", rain, "0%", "0", "0%", "20%", "10km", "1", hour]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def _hourly_table(rain_values: tuple[str, ...]) -> str:
    """14-spaltige Stundentabelle (eigener thead + tbody) mit steuerbaren Rain-Werten."""
    header_row = "".join(f"<th>{h}</th>" for h in _HEADERS)
    rows = "".join(_hour_row(f"{8 + i:02d}:00", r) for i, r in enumerate(rain_values))
    return f"<table><thead><tr>{header_row}</tr></thead><tbody>{rows}</tbody></table>"


def _trend_table_html() -> str:
    """Separate Trend-Tabelle MIT realistischer eigener th-Reihe (9 Spalten,
    wie html.py:1148-1157) und eigenem <tbody>. Genau diese th-Reihe ließ den
    Ist-Code (globale th-Summe) versagen — der Adversary-Beweis (#997)."""
    header_row = "".join(f"<th>{h}</th>" for h in _TREND_HEADERS)
    row = "<tr>" + "".join(f"<td>{c}</td>" for c in _TREND_ROW_CELLS) + "</tr>"
    return f"<table><thead><tr>{header_row}</tr></thead><tbody>{row}</tbody></table>"


def _build_html(hour_rains: tuple[str, str] = ("0.0", "0.0")) -> str:
    """Vollständiges Dokument: 14-spaltige Stundentabelle + realistische
    9-spaltige Trend-Tabelle + 'kein Regen'-Pill, analog zur echten Briefing-Mail."""
    overview = "<div>Metriken-Ueberblick</div><div><span>🌂 kein Regen</span></div>"
    return f"<div>Tag 3 - GR20</div>{_hourly_table(hour_rains)}{_trend_table_html()}{overview}"


def test_ac1_trend_row_does_not_poison_rain_column():
    """AC-1: Die 9-spaltige Trend-Zeile (Wert '35' an Index 6) darf die 'kein
    Regen'-Prüfung NICHT fälschlich brechen, wenn die Stundentabelle durchgehend
    Rain=0.0 zeigt. Die realistische Trend-th-Reihe (9 <th>) ist entscheidend:
    unter globaler th-Summe (14+9) matchte keine Zeile mehr."""
    bmv = _load_validator()
    html = _build_html(hour_rains=("0.0", "0.0"))

    errors = bmv._check_metric_plausibility(html)

    rain_errors = [e for e in errors if "kein Regen" in e]
    assert rain_errors == [], (
        f"'kein Regen'-Prüfung darf durch die 9-spaltige Trend-Zeile nicht "
        f"fälschlich fehlschlagen, errors={rain_errors}"
    )


def test_ac2_real_rain_violation_still_detected():
    """AC-2 (Nicht-Aufweichungs-Beweis): Eine ECHTE Verletzung in der
    Stundentabelle selbst (Rain=0.4 bei 'kein Regen'-Pill) muss weiterhin erkannt
    werden. Der Fix filtert nur Fremd-Zeilen, deaktiviert die Regel nicht.

    Mit realistischer Trend-th-Reihe schlägt DIESER Test auf dem Ist-Code fehl
    (globale th-Summe → _column_values==[] → Verletzung stumm) und ist damit der
    eigentliche Regressions-Anker des Bundles."""
    bmv = _load_validator()
    html = _build_html(hour_rains=("0.0", "0.4"))

    errors = bmv._check_metric_plausibility(html)

    rain_errors = [e for e in errors if "kein Regen" in e]
    assert rain_errors, (
        f"echte Regen-Verletzung (0.4mm bei 'kein Regen'-Pill) muss weiterhin "
        f"gemeldet werden, errors={errors}"
    )


def test_multi_stage_rain_sum_aggregates_across_hourly_tables():
    """Mehr-Etappen-Aggregation: Zwei getrennte Stundentabellen (gleiche Header,
    eigener tbody) mit Rain 0.2 bzw. 0.3 → Σ == 0.5. Das Summenverhalten über
    Etappen (mehrere Stundentabellen in einer Mail) MUSS erhalten bleiben — der
    Scoping-Fix aggregiert bewusst über alle passenden Blöcke."""
    bmv = _load_validator()
    two_tables = _hourly_table(("0.2",)) + _hourly_table(("0.3",))
    html = f"<div>GR20</div>{two_tables}{_trend_table_html()}"

    total = bmv._column_num_sum(html, "Regen", "Rain")

    assert total is not None and abs(total - 0.5) < 1e-9, (
        f"Rain-Summe über zwei Stundentabellen muss 0.2+0.3=0.5 sein, ist {total!r}"
    )


def test_gold_standard_real_render_rain_column_scoped_and_violation_fires():
    """GOLD-STANDARD (Adversary-Muster): echte Mail über den echten Renderpfad
    (render_email, raw-Modus, KEIN Mock) mit numerischer Rain-Spalte UND
    multi_day_trend (eigene 9-spaltige th-Reihe). Prüft am realen Renderer-Output:

      1. `_column_values('Rain')` liefert die Stundenzeilen-Werte (nicht-leer),
         die Trend-Tabellen-Spalte 'R' leakt NICHT hinein.
      2. Bei echter Inkonsistenz ('kein Regen'-Pill, aber Rain-Spalte > 0) meldet
         `_check_metric_plausibility` den Fehler.

    Der Adversary hat bewiesen: auf ECHTER Mail-Struktur lieferte der Ist-Code
    hier `[]` (False-Negative). Dieser Test verankert den realen Renderpfad."""
    import test_issue_811_mode_matrix as M
    import test_issue_898_901_mail_layout as T
    from app.models import ForecastDataPoint, ThunderLevel
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    tz = ZoneInfo("Europe/Berlin")
    # precip 0.1 mm/h: unter der SMS-Erwähnungsschwelle (R=0.2) → 'kein Regen'-Pill,
    # aber die Rain-Spalte zeigt im raw-Modus den echten Wert 0.1 → echte Inkonsistenz.
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=5.0, gust_kmh=10.0, precip_1h_mm=0.1, pop_pct=0,
        cloud_total_pct=40, thunder_level=ThunderLevel.NONE, visibility_m=15000.0,
    )
    dc = M._make_dc(raw=True, enabled={"temperature", "precipitation"})
    row = dp_to_row(dp, dc, tz=tz)
    tl = TokenLine(trip_name="Gold", report_type="evening", stage_name="Etappe 1")
    html, _plain = render_email(
        tl, segments=[M._make_seg_data(dp=dp)], seg_tables=[[row]],
        display_config=dc, tz=tz, friendly_keys=set(), email_format="full",
        changes=None, multi_day_trend=[T._trend_stage("Mo"), T._trend_stage("Di")],
    )

    bmv = _load_validator()

    rain_vals = bmv._column_values(html, "Rain")
    assert rain_vals, (
        "GOLD: _column_values('Rain') muss am echten Renderer-Output nicht-leer "
        "sein (Adversary-Beweis: Ist-Code lieferte hier [] — False-Negative)"
    )
    # Trend-Stufen tragen precip_mm=0.5 in ihrer 'R'-Spalte — darf NICHT einfließen.
    assert all(abs(v - 0.1) < 1e-9 for v in rain_vals), (
        f"GOLD: Rain-Spalte darf nur Stundenzeilen-Werte (0.1) führen, nicht die "
        f"Trend-'R'-Spalte (0.5); ist {rain_vals!r}"
    )

    errors = bmv._check_metric_plausibility(html)
    rain_errors = [e for e in errors if "kein Regen" in e]
    assert rain_errors, (
        f"GOLD: echte Inkonsistenz ('kein Regen'-Pill vs. Rain-Spalte 0.1) muss "
        f"am realen Renderer-Output gemeldet werden, errors={errors}"
    )
