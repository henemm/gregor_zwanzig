# doc-compliance-test
"""Drift-Wächter: docs/reference/api_contract.md vs. Go-Code (Issue #1342).

api_contract.md nennt sich „Single Source of Truth" — das Drift-Audit
2026-07-22 fand aber erfundene DTO-Felder, fehlende Endpunkte und veraltete
Fehler-Bodies. Dieser Test erzwingt die zwei billig prüfbaren Invarianten:

1. Jede in internal/router/router.go registrierte /api/-Route steht in
   api_contract.md (Endpunkt-Inventar Sektion 0.5 genügt).
2. Jedes JSON-Tag der Kern-Structs (Trip/Stage/Waypoint/AlertRule/Corridor in
   internal/model/trip.go, ComparePreset in internal/model/compare_preset.go)
   kommt in api_contract.md vor.

Rot heißt IMMER: Doku nachziehen — niemals diesen Test aufweichen.

Regel-Budget: Prüfdatum 2027-01-19 — kein nachweisbarer Fang bis dahin → Rückbau.
(verlängert 2026-10-21 (PO): Doku-Audit fand reale Drift; vorher 2026-10-20)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "reference" / "api_contract.md"
ROUTER = REPO / "internal" / "router" / "router.go"
MODEL_FILES = [
    REPO / "internal" / "model" / "trip.go",
    REPO / "internal" / "model" / "compare_preset.go",
]

ROUTE_RE = re.compile(r'r\.(Get|Post|Put|Delete|Patch)\("(/api/[^"]+)"')
JSON_TAG_RE = re.compile(r'`json:"([a-zA-Z0-9_]+)')


def _contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_every_router_route_is_documented():
    text = _contract_text()
    missing = []
    for line in ROUTER.read_text(encoding="utf-8").splitlines():
        m = ROUTE_RE.search(line)
        if not m:
            continue
        path = m.group(2)
        if path not in text:
            missing.append(f"{m.group(1).upper()} {path}")
    assert not missing, (
        "Routen in internal/router/router.go ohne Eintrag in api_contract.md "
        "(Sektion 0.5 Endpunkt-Inventar nachziehen!):\n  " + "\n  ".join(missing)
    )


def test_every_model_json_tag_is_documented():
    text = _contract_text()
    missing = []
    for model_file in MODEL_FILES:
        for tag in JSON_TAG_RE.findall(model_file.read_text(encoding="utf-8")):
            if f'"{tag}' not in text and f"`{tag}`" not in text and tag not in text:
                missing.append(f"{model_file.name}: {tag}")
    assert not missing, (
        "JSON-Tags in Go-Structs ohne Erwähnung in api_contract.md "
        "(DTO-Sektionen nachziehen!):\n  " + "\n  ".join(missing)
    )


def test_no_phantom_go_json_tags_in_doc():
    """Jedes json-Tag in den ```go-Blöcken der Doku muss im echten Go-Code existieren.

    Fängt erfundene DTO-Felder (Audit 2026-07-22: distance_from_start_km,
    duration_minutes u. a. standen als Go-Felder in der Doku, existierten aber
    in keinem Struct).
    """
    real_tags = set()
    for go_file in (REPO / "internal").rglob("*.go"):
        real_tags.update(JSON_TAG_RE.findall(go_file.read_text(encoding="utf-8")))

    phantoms = []
    text = _contract_text()
    for block in re.findall(r"```go\n(.*?)```", text, flags=re.DOTALL):
        for tag in JSON_TAG_RE.findall(block):
            if tag not in real_tags:
                phantoms.append(tag)
    assert not phantoms, (
        "```go-Blöcke in api_contract.md enthalten json-Tags, die in keinem "
        f"Struct unter internal/ existieren: {sorted(set(phantoms))}"
    )


def _inventory_rows(text: str) -> dict[str, str]:
    """Zeilen des Endpunkt-Inventars (Sektion 0.5): `| `/api/...` | … |` →
    {pfad: ganze Zeile}. Nur echte Tabellenzeilen zaehlen — Fliesstext im
    Changelog (z. B. „/signal entfernt") darf den Test nicht taeuschen."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*`(/api/[^`]+)`\s*\|", line)
        if m:
            rows[m.group(1)] = line
    return rows


def test_inventory_lists_kind_neutral_preview_routes_and_drops_signal():
    """AC-7 (Issue #2283 S1): GIVEN docs/reference/api_contract.md
    WHEN das Endpunkt-Inventar gelesen wird
    THEN stehen dort die kind-neutralen Routen `/api/briefings/{id}/preview`
    und `/api/briefings/{id}/alert-preview` als eigene Zeilen, die Alt-Routen
    sind als Delegates gekennzeichnet, und `/api/preview/{trip_id}/signal`
    ist keine Inventarzeile mehr (Route entfernt, Signal app-weit weg #610)."""
    rows = _inventory_rows(_contract_text())

    missing = [p for p in ("/api/briefings/{id}/preview", "/api/briefings/{id}/alert-preview")
               if p not in rows]
    assert not missing, f"AC-7: Inventarzeilen fehlen: {missing}"

    assert "/api/preview/{trip_id}/signal" not in rows, (
        "AC-7: `/api/preview/{trip_id}/signal` steht noch als Inventarzeile: "
        f"{rows.get('/api/preview/{trip_id}/signal')!r}"
    )

    legacy = [
        "/api/preview/{trip_id}/email", "/api/preview/{trip_id}/sms",
        "/api/preview/{trip_id}/telegram", "/api/preview/compare/{preset_id}",
        "/api/trips/{id}/alert-preview",
    ]
    not_delegate = [p for p in legacy if "delegate" not in rows.get(p, "").lower()]
    assert not not_delegate, (
        f"AC-7: Alt-Routen ohne Delegate-Kennzeichnung im Inventar: {not_delegate}"
    )
