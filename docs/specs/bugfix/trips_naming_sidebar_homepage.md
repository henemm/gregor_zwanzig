---
entity_id: trips_naming_sidebar_homepage
type: bugfix
created: 2026-05-05
updated: 2026-05-05
status: draft
version: "1.0"
tags: [frontend, sveltekit, naming, ui, issue-126]
---

# Bug #126 — Begriff "Touren"/"Tour" durch "Trips"/"Trip" ersetzen

## Approval

- [ ] Approved

## Purpose

Vereinheitlichung der UI-Begriffe in Sidebar und Startseite. Der kanonische
Begriff im Projekt ist **Trip** (siehe `docs/reference/api_contract.md` —
Datenmodell, Routing `/trips`, API `/api/trips`). Die deutschen Übersetzungen
"Touren" und "Tour" tauchen aktuell nur an fünf Stellen in zwei Frontend-Dateien
auf und brechen die sonst durchgehende Trip-Terminologie.

## Source

- `frontend/src/routes/+layout.svelte` — Sidebar-Navigation
- `frontend/src/routes/+page.svelte` — Startseite (Empty-State und Listings)

## Root Cause

Zwei Frontend-Dateien wurden in einer früheren Übersetzungsrunde auf "Touren"
gesetzt; nirgendwo sonst (URL, API, Wizard, Listing-Seite, Datenmodell, Specs,
Tests) wird "Tour" verwendet.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `frontend/src/routes/+layout.svelte` | Zu ändern | Sidebar-Label |
| `frontend/src/routes/+page.svelte` | Zu ändern | Startseite mit Empty-State und Trip-Liste |

## Implementation Details

Fünf String-Ersetzungen, exakte Liste:

| Datei | Zeile | Vorher | Nachher |
|---|---|---|---|
| `+layout.svelte` | 81 | `'Meine Touren'` | `'Meine Trips'` |
| `+page.svelte` | 53 | `Leg deine erste Tour oder deinen ersten Orts-Vergleich an.` | `Leg deinen ersten Trip oder deinen ersten Orts-Vergleich an.` |
| `+page.svelte` | 56 | `Erste Tour anlegen` | `Ersten Trip anlegen` |
| `+page.svelte` | 67 | `Meine Touren` | `Meine Trips` |
| `+page.svelte` | 131 | `Neue Tour` | `Neuer Trip` |

Keine anderen Code-Pfade oder Komponenten betroffen.

## Expected Behavior

- **Input:** Authentifizierter Aufruf von `/` und beliebige Seite mit Sidebar
- **Output:** UI zeigt durchgängig "Trip" / "Trips", kein "Tour" / "Touren" mehr
- **Side effects:** keine Datenmodell-, URL- oder API-Änderungen

## Test Plan

**Datei:** `tests/tdd/test_trips_naming.py`

Tests laufen gegen den deployed Frontend-Server (Default Staging, via
`GZ_TEST_BASE_URL` überschreibbar). KEINE MOCKS — echte HTTP-Requests gegen
SSR-HTML.

```python
import os
import httpx

BASE_URL = os.getenv("GZ_TEST_BASE_URL", "https://staging.gregor20.henemm.com").rstrip("/")
TIMEOUT = 10.0


def _login_session() -> httpx.Client:
    """Authentifizierte httpx-Session für Auth-pflichtige Routen."""
    user = os.getenv("GZ_TEST_USER", "default")
    pw = os.getenv("GZ_TEST_PASS")
    assert pw, "GZ_TEST_PASS env var required for naming tests"
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, follow_redirects=True)
    r = client.post("/api/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, f"Login failed: {r.status_code}"
    return client


def test_sidebar_uses_trips_label() -> None:
    """Sidebar-Label muss 'Meine Trips' heißen, nicht 'Meine Touren'."""
    with _login_session() as client:
        r = client.get("/")
        assert r.status_code == 200
        html = r.text
        assert "Meine Trips" in html, "Sidebar-Label 'Meine Trips' fehlt"
        assert "Meine Touren" not in html, "Altes Label 'Meine Touren' noch in HTML"


def test_homepage_uses_trip_terminology() -> None:
    """Startseite darf keine 'Tour'/'Touren'-Vorkommen mehr enthalten."""
    with _login_session() as client:
        r = client.get("/")
        assert r.status_code == 200
        html = r.text
        # Negative: kein altes Vokabular
        for forbidden in ("Erste Tour anlegen", "Neue Tour", "deine erste Tour"):
            assert forbidden not in html, f"Veraltetes Wording {forbidden!r} noch im HTML"
        # Positive: neues Vokabular vorhanden in mindestens einem Empty-State-Pfad
        # (Empty-State zeigt "Ersten Trip anlegen", Non-Empty zeigt "Meine Trips" + "Neuer Trip")
        new_tokens = ("Ersten Trip anlegen", "Neuer Trip", "Meine Trips")
        assert any(t in html for t in new_tokens), (
            f"Keine der neuen Trip-Bezeichnungen {new_tokens!r} im HTML"
        )
```

**RED:** Vor dem Fix schlagen beide Tests fehl, weil "Meine Touren" / "Neue Tour"
im HTML enthalten sind.
**GREEN:** Nach dem Fix sind beide Tests grün.

## Known Limitations

- Tests setzen einen authentifizierten User voraus (Sidebar wird nur eingeloggt
  gerendert). `GZ_TEST_PASS` als Env-Var oder Override nötig — passt zum Pattern
  aus `external_validator_auth`.
- Andere Sprachen sind nicht im Repo (UI ist deutschsprachig). Falls später
  i18n eingeführt wird, gehört "Trip"/"Tour"-Mapping in die Übersetzungsdateien.

## Success Criteria

- [ ] `curl https://gregor20.henemm.com/` (eingeloggt) enthält "Meine Trips", nicht "Meine Touren"
- [ ] Startseite (Empty-State) zeigt "Ersten Trip anlegen"
- [ ] Startseite (mit Trips) zeigt "Neuer Trip" statt "Neue Tour"
- [ ] `git grep -i "Tour\|Touren" frontend/src` liefert keine UI-Treffer mehr
- [ ] User-Verifikation in Safari Mac

## Bezug

- GitHub Issue #126
- Memory: `feedback_terminology_consistency` (Trip / Etappe / Wegpunkt — nicht mischen)
- Verwandt: Issue #125 (vorhergehender Frontend-Fix in derselben Sitzung)

## Changelog

- 2026-05-05: Initial spec für Naming-Vereinheitlichung Sidebar + Startseite.
