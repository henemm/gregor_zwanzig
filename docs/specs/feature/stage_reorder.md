---
entity_id: stage_reorder
type: feature
created: 2026-05-05
updated: 2026-05-05
status: draft
version: "1.0"
tags: [frontend, sveltekit, ui, etappen, issue-128]
---

# Feature #128 — Etappen-Reihenfolge per Pfeil-Buttons ändern

## Approval

- [ ] Approved

## Purpose

Im Etappen-Editor der Trip-Komponente bekommt jede Etappe zwei Pfeil-Buttons
(hoch / runter), mit denen User die Reihenfolge ändern können. Damit ist nach
einem GPX-Multi-Import oder dem Anlegen einer Zwischen-Etappe ein einfaches
Umsortieren möglich, ohne Etappen löschen und neu anlegen zu müssen.

## Source

- **File:** `frontend/src/lib/components/wizard/WizardStep2Stages.svelte`
- **Identifier:** `WizardStep2Stages`-Komponente — wird sowohl im Wizard-Modus
  (`/trips/new`) als auch im Edit-Modus (`/trips/[id]/edit` über `TripEditView`)
  eingesetzt; der Fix wirkt damit automatisch in beiden Pfaden.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | Zu ändern | Zwei Move-Funktionen + zwei Buttons pro Etappen-Card |
| `@lucide/svelte/icons/arrow-up`, `arrow-down` | Library | Icons für die neuen Buttons |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Read-only | Konsumiert die Komponente, speichert per `api.put('/api/trips/{id}')` |
| `internal/handler/trip.go::UpdateTripHandler` | Read-only Backend | Read-Modify-Write — erhält Reihenfolge automatisch |

## Implementation Details

### Logik

Zwei neue Funktionen unter den bestehenden `addStage`/`removeStage`:

```ts
function moveStageUp(idx: number) {
    if (idx <= 0) return;
    [stages[idx - 1], stages[idx]] = [stages[idx], stages[idx - 1]];
}

function moveStageDown(idx: number) {
    if (idx >= stages.length - 1) return;
    [stages[idx], stages[idx + 1]] = [stages[idx + 1], stages[idx]];
}
```

### UI

Im Etappen-Card-Header (zwischen Datum-Input und Trash-Button), zwei zusätzliche
Buttons:

```svelte
<Button
    data-testid="stage-move-up-{si}"
    variant="ghost"
    size="icon-sm"
    disabled={si === 0}
    onclick={() => moveStageUp(si)}
    title="Nach oben verschieben"
>
    <ArrowUpIcon class="size-4" />
</Button>
<Button
    data-testid="stage-move-down-{si}"
    variant="ghost"
    size="icon-sm"
    disabled={si === stages.length - 1}
    onclick={() => moveStageDown(si)}
    title="Nach unten verschieben"
>
    <ArrowDownIcon class="size-4" />
</Button>
```

Imports am Datei-Anfang ergänzen:

```ts
import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
import ArrowDownIcon from '@lucide/svelte/icons/arrow-down';
```

### Reaktivität (Svelte 5)

Die Etappen-Liste ist `$bindable()`. Direkte Index-Zuweisung
(`[stages[a], stages[b]] = [stages[b], stages[a]]`) triggert Svelte's
Reaktivität für Array-Items.

## Expected Behavior

| Aktion | Erwartung |
|---|---|
| Klick „hoch" auf Etappe N (N > 0) | Etappe N tauscht mit Etappe N−1; UI rendert sofort neu |
| Klick „hoch" auf Etappe 0 | Button ist `disabled`, kein Click-Handler |
| Klick „runter" auf Etappe N (N < letzte) | Etappe N tauscht mit Etappe N+1 |
| Klick „runter" auf letzte Etappe | Button ist `disabled` |
| Speichern nach Reorder | API `PUT /api/trips/{id}` mit neuer Reihenfolge; nach Reload bleibt Reihenfolge persistent |
| Wegpunkte / Wetter-Konfiguration / Report-Konfiguration | bleiben **vollständig** erhalten — werden nur indiziert verschoben, nicht modifiziert |

- **Side effects:** keine (UI-State-Mutation + bestehender Save-Pfad)
- **Backend-Änderungen:** keine — `UpdateTripHandler` ist bereits Read-Modify-Write

## Test Plan

**Datei:** `tests/tdd/test_stage_reorder.py` — Playwright-E2E-Tests gegen
deployed Frontend (Default Staging, via `GZ_TEST_BASE_URL` überschreibbar).

```python
import os
import asyncio
import httpx
import pytest
from playwright.async_api import async_playwright

BASE_URL = os.getenv("GZ_TEST_BASE_URL", "https://staging.gregor20.henemm.com").rstrip("/")
USER = os.getenv("GZ_TEST_USER", "default")
PASS = os.getenv("GZ_TEST_PASS")


def _create_test_trip(client: httpx.Client) -> str:
    """Legt einen Test-Trip mit 3 Etappen an, gibt Trip-ID zurück."""
    trip = {
        "name": "stage-reorder-test",
        "stages": [
            {"id": "a", "name": "Alpha", "date": "2026-06-01", "waypoints": [
                {"id": "p1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 1000}
            ]},
            {"id": "b", "name": "Bravo", "date": "2026-06-02", "waypoints": [
                {"id": "p2", "name": "Start", "lat": 47.1, "lon": 11.1, "elevation_m": 1100}
            ]},
            {"id": "c", "name": "Charlie", "date": "2026-06-03", "waypoints": [
                {"id": "p3", "name": "Start", "lat": 47.2, "lon": 11.2, "elevation_m": 1200}
            ]},
        ],
    }
    r = client.post("/api/trips", json=trip)
    assert r.status_code in (200, 201), f"Trip create failed: {r.status_code} {r.text}"
    return r.json()["id"]


def _delete_trip(client: httpx.Client, trip_id: str) -> None:
    client.delete(f"/api/trips/{trip_id}")


@pytest.mark.asyncio
async def test_stage_reorder_move_down_persists() -> None:
    """
    GIVEN: Trip mit 3 Etappen [Alpha, Bravo, Charlie] im Edit-Dialog
    WHEN:  User klickt 'runter' bei Alpha (idx 0), dann Speichern
    THEN:  Reihenfolge nach Reload: [Bravo, Alpha, Charlie]
           Wegpunkte aller Etappen unverändert
    """
    if not PASS:
        pytest.fail("GZ_TEST_PASS env var required")

    # Setup via API
    client = httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=10)
    r = client.post("/api/auth/login", json={"username": USER, "password": PASS})
    assert r.status_code == 200
    trip_id = _create_test_trip(client)
    cookie = client.cookies.get("gz_session")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            await ctx.add_cookies([{
                "name": "gz_session", "value": cookie,
                "url": BASE_URL,
            }])
            page = await ctx.new_page()
            await page.goto(f"{BASE_URL}/trips/{trip_id}/edit")
            await page.wait_for_load_state("networkidle")

            # Reihenfolge initial: Alpha, Bravo, Charlie
            initial = await page.eval_on_selector_all(
                'input[placeholder="Etappenname"]',
                'els => els.map(e => e.value)'
            )
            assert initial == ["Alpha", "Bravo", "Charlie"], f"Initial: {initial}"

            # Move-down auf Etappe 0 (Alpha)
            await page.click('[data-testid="stage-move-down-0"]')

            # Reihenfolge im DOM nach Klick
            after_click = await page.eval_on_selector_all(
                'input[placeholder="Etappenname"]',
                'els => els.map(e => e.value)'
            )
            assert after_click == ["Bravo", "Alpha", "Charlie"], f"After click: {after_click}"

            # Speichern
            await page.click('button:has-text("Speichern")')
            await page.wait_for_url(f"{BASE_URL}/trips", timeout=5000)
            await browser.close()

        # Re-Fetch via API: Reihenfolge muss persistent sein
        r = client.get(f"/api/trips/{trip_id}")
        assert r.status_code == 200
        names = [s["name"] for s in r.json()["stages"]]
        assert names == ["Bravo", "Alpha", "Charlie"], f"Persisted: {names}"

        # Wegpunkte je Etappe unverändert (keine Datenverluste)
        wps = {s["name"]: [w["id"] for w in s["waypoints"]] for s in r.json()["stages"]}
        assert wps["Alpha"] == ["p1"]
        assert wps["Bravo"] == ["p2"]
        assert wps["Charlie"] == ["p3"]
    finally:
        _delete_trip(client, trip_id)
        client.close()


@pytest.mark.asyncio
async def test_stage_reorder_disabled_at_edges() -> None:
    """
    GIVEN: Trip mit 3 Etappen
    WHEN:  Edit-Seite gerendert ist
    THEN:  - 'hoch'-Button auf Etappe 0 ist disabled
           - 'runter'-Button auf letzter Etappe ist disabled
    """
    if not PASS:
        pytest.fail("GZ_TEST_PASS env var required")

    client = httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=10)
    r = client.post("/api/auth/login", json={"username": USER, "password": PASS})
    assert r.status_code == 200
    trip_id = _create_test_trip(client)
    cookie = client.cookies.get("gz_session")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            await ctx.add_cookies([{
                "name": "gz_session", "value": cookie,
                "url": BASE_URL,
            }])
            page = await ctx.new_page()
            await page.goto(f"{BASE_URL}/trips/{trip_id}/edit")
            await page.wait_for_load_state("networkidle")

            # Etappe 0: hoch disabled
            up_first = await page.locator('[data-testid="stage-move-up-0"]').is_disabled()
            assert up_first, "Erster 'hoch'-Button muss disabled sein"

            # Letzte Etappe: runter disabled
            down_last = await page.locator('[data-testid="stage-move-down-2"]').is_disabled()
            assert down_last, "Letzter 'runter'-Button muss disabled sein"

            await browser.close()
    finally:
        _delete_trip(client, trip_id)
        client.close()
```

**Keine Mocks.** Beide Tests legen einen echten Trip via API an, manipulieren
ihn über die echte UI mit Playwright und prüfen Persistenz und Disabled-State.
Cleanup im `finally` löscht den Test-Trip.

## Known Limitations

- **Playwright-Setup:** Tests benötigen `playwright` als Dev-Dependency (in
  diesem Projekt bereits vorhanden, siehe `tests/test_safari_fix_v2.py`).
- **Test-User-Daten:** Tests legen pro Lauf einen Test-Trip an und löschen ihn
  wieder — kein Risiko, dass Bestandsdaten verändert werden. Cleanup im
  `finally`-Block.
- **Wizard-Modus nicht im Test:** Die gleiche Komponente wird auch im Wizard
  (`/trips/new`) verwendet. Tests decken aber nur den Edit-Pfad ab — die
  Wizard-Funktionalität ergibt sich automatisch aus dem geteilten Code.

## Success Criteria

- [ ] Etappen-Card hat zwei Pfeil-Buttons (hoch + runter) im Header-Bereich
- [ ] Erste Etappe: hoch-Button disabled
- [ ] Letzte Etappe: runter-Button disabled
- [ ] Klick verschiebt die Etappe genau eine Position; UI rendert sofort
- [ ] Speichern + Reload: neue Reihenfolge persistent in `data/users/.../trips/{id}.json`
- [ ] Wegpunkte, Wetter-Konfiguration, Report-Konfiguration bleiben unverändert
- [ ] Real-User-Test in Safari Mac: Reorder funktioniert ohne Cache-Leeren

## Bezug

- GitHub Issue #128
- Memory: `feedback_terminology_consistency` (Trip / Etappe / Wegpunkt)
- Memory: `data_schema_reworks` (Datenverlust verhindern — hier nicht
  riskant, da kein Schema-Change, nur Array-Reorder)

## Changelog

- 2026-05-05: Initial spec für Etappen-Reorder mit Pfeil-Buttons.
