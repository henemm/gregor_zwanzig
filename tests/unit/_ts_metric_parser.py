"""Regex-Parser fuer ``compareMetricDefs.ts::ALL_METRICS`` (#1298, B3).

Ersetzt die vormals von Hand gepflegte ID-Kopie in
``test_compare_metric_catalog_consistency.py`` durch einen Parser gegen die
echte Frontend-Quelle -- damit kann der Metrik-Waechter nicht mehr veralten,
wenn eine neue Metrik ergaenzt und die Kopie vergessen wird.

Bewusst regex-basiert, kein vollstaendiger TypeScript-Parser (deckt sich mit
der "kein Cross-Language-Tooling"-Vorgabe, CLAUDE.md Test-Politik). Deckt
exakt das aktuelle Ein-Zeile-pro-Konstante-Format von ``compareMetricDefs.ts``
ab -- s. Spec Known Limitations.

TDD RED (Phase 5): ``parse_all_metrics_ids`` ist bewusst noch NICHT
implementiert (Stub) -- die Implementierung folgt in Phase 6 (GREEN).

SPEC: docs/specs/modules/issue_1298_compare_metric_guard_cape_label.md, AC-2
"""
from __future__ import annotations

import re
from pathlib import Path

COMPARE_METRIC_DEFS_TS = (
    Path(__file__).parent.parent.parent
    / "frontend" / "src" / "lib" / "components" / "compare" / "compareMetricDefs.ts"
)

# Ein-Zeile-pro-Konstante-Format: `const NAME: MetricDef = { ... key: 'xxx' ... };`
_CONST_RE = re.compile(r"const\s+(\w+)\s*:\s*MetricDef\s*=\s*\{[^}]*\bkey:\s*'([^']+)'[^}]*\};")

# `ALL_METRICS: MetricDef[] = [ NAME1, NAME2, ... ];`
_ALL_METRICS_RE = re.compile(r"ALL_METRICS\s*:\s*MetricDef\[\]\s*=\s*\[(.*?)\];", re.S)


def parse_all_metrics_ids(path: Path | str = COMPARE_METRIC_DEFS_TS) -> list[str]:
    """Liest ``compareMetricDefs.ts`` und liefert die Metrik-IDs in der
    Reihenfolge des ``ALL_METRICS``-Arrays.
    """
    text = Path(path).read_text(encoding="utf-8")

    name_to_key = dict(_CONST_RE.findall(text))
    assert name_to_key, (
        f"Kein const NAME: MetricDef = {{ ... key: '...' ... }}; in {path} "
        f"gefunden -- Parser-Format veraltet oder Datei leer (Vakuum-Schutz)."
    )

    array_match = _ALL_METRICS_RE.search(text)
    assert array_match, (
        f"Kein 'ALL_METRICS: MetricDef[] = [...]'-Array in {path} gefunden -- "
        f"Parser-Format veraltet (Vakuum-Schutz)."
    )

    names = re.findall(r"\w+", array_match.group(1))
    return [name_to_key[name] for name in names]
