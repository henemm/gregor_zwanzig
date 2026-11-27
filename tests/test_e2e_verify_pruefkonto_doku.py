"""TDD RED fuer #3423 AC-8 — Doku-Hinweis zu Pruefkonto-Specs ueber ``spec-run``.

Spec: ``docs/specs/modules/feat_3423_pruefkonto_zugang_e2e.md`` (AC-8).

# doc-compliance-test
Prueft bewusst Dateiinhalt: der Abschnitt „Außerhalb des Servers" in
``.claude/commands/e2e-verify.md`` muss sagen, dass Pruefkonto-Specs ueber
``spec-run`` ohne Seed-Variablen (``ELEMENTLISTE_*``) laufen und der Seed einmalig
auf dem Server gelaufen sein muss.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_VERIFY = REPO_ROOT / ".claude" / "commands" / "e2e-verify.md"


def _abschnitt_ausserhalb() -> str:
    text = E2E_VERIFY.read_text(encoding="utf-8")
    start = text.index("## Außerhalb des Servers")
    ende = text.find("\n## ", start + 1)
    return text[start:] if ende == -1 else text[start:ende]


def test_ac8_pruefkonto_specs_ohne_seed_variablen_ueber_spec_run():
    abschnitt = _abschnitt_ausserhalb()
    absaetze = [a for a in abschnitt.split("\n\n") if "Prüfkonto" in a]
    assert absaetze, "Abschnitt nennt Prüfkonto-Specs nicht"
    hinweis = "\n\n".join(absaetze)
    assert "spec-run" in hinweis, "Prüfkonto-Hinweis nennt spec-run nicht"
    assert "ELEMENTLISTE_" in hinweis, "Prüfkonto-Hinweis sagt nicht, dass ELEMENTLISTE_* entfallen"
    assert "einmalig" in hinweis and "Seed" in hinweis, (
        "Prüfkonto-Hinweis sagt nicht, dass der Seed einmalig auf dem Server gelaufen sein muss"
    )
    assert "staging_pruefkonto_seed.md" in hinweis, "Prüfkonto-Hinweis verweist nicht aufs Runbook"
