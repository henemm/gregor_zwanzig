# External Validator Report

**Spec:** docs/specs/modules/epic_133_design_system_lauf_a.md
**Datum:** 2026-05-08T11:00:00Z
**Server (Ziel):** https://staging.gregor20.henemm.com
**Lokaler Build:** localhost:4173 (via `npm run preview`)

---

## Methodik

Staging-Server zeigte beim ersten Zugriff **keinen der implementierten Features** (alle --g-* Tokens leer, `body`-Font `system-ui`, Nav-Label `"Meine Trips"`). Daraufhin wurden die E2E-Tests gegen den lokalen Build ausgeführt, der laut Playwright-Konfiguration immer auf `localhost:4173` läuft — nie auf Staging. Alle Befunde werden separat für beide Umgebungen ausgewiesen.

---

## Checklist (Akzeptanzkriterien aus Spec)

| # | Expected Behavior | Lokaler Build | Staging | Gesamturteil |
|---|-------------------|--------------|---------|--------------|
| 1 | `--g-accent`, `--g-paper`, `--g-ink` in `:root` sichtbar | PASS | FAIL | AMBIGUOUS |
| 2 | Inter Tight als Schriftart geladen (Google Fonts) | PASS | FAIL | AMBIGUOUS |
| 3 | Nav-Label `/trips` lautet `'Meine Touren'` | PASS | FAIL | AMBIGUOUS |
| 4 | 7 E2E-Tests in `nav-redesign.spec.ts` grün | PASS (7/7) | — | PASS |
| 5 | Keine visuellen Regressionen (Startseite, Trips, Compare) | PASS | PASS (Altstand) | PASS |

---

## Befunde im Detail

### Befund 1: Staging — Alle --g-*-Tokens fehlen

- **Severity:** CRITICAL (Staging-Deploy nicht erfolgt)
- **Expected:** `--g-accent: #c45a2a`, `--g-paper: #f6f4ee`, `--g-ink: #1a1a18` u.a. in `:root`
- **Actual:** Alle `--g-*`-Properties sind leere Strings (`""`) auf Staging
- **Evidence:** screenshots/01_startseite.png (Staging), JS-Abfrage via `getComputedStyle(document.documentElement)`
  ```
  accent: "", paper: "", ink: "", fontUi: "", elev1: "", wxRain: ""  (alle leer)
  ```

### Befund 2: Staging — Inter Tight nicht geladen

- **Severity:** CRITICAL (Staging-Deploy nicht erfolgt)
- **Expected:** `body { font-family: "Inter Tight", system-ui, sans-serif }` + Google-Fonts-`<link>`-Tags
- **Actual:** `body.fontFamily = "system-ui, -apple-system, sans-serif"` (Altstand), keine `<link rel="stylesheet">` zu fonts.googleapis.com
- **Evidence:** JS-Abfrage, screenshots/01_startseite.png (Staging)

### Befund 3: Staging — Nav-Label "Meine Trips" statt "Meine Touren"

- **Severity:** CRITICAL (Staging-Deploy nicht erfolgt)
- **Expected:** Nav-Link `/trips` mit Label `'Meine Touren'`
- **Actual:** Nav-Link `/trips` zeigt `'Meine Trips'` (Altstand)
- **Evidence:** screenshots/02_trips_seite.png (Staging), JS-Abfrage `nav a` Texte

### Lokaler Build — Alle Features korrekt

**CSS Tokens (Issue #141):**
- `--g-accent: #c45a2a` ✓
- `--g-paper: #f6f4ee` ✓
- `--g-ink: #1a1a18` ✓
- `--g-font-ui: "Inter Tight", system-ui, sans-serif` ✓
- `--g-font-data: "JetBrains Mono", ui-monospace, monospace` ✓
- `--g-elev-1: 0 1px 3px #1a1a1814` ✓ (hex-codiertes rgba — identischer Wert)
- `--g-wx-rain: #4a7fb5` ✓
- `--g-radius-md: .5rem` ✓ (= 0.5rem)
- **Evidence:** screenshots/local_01_startseite.png, JS-Abfrage

**Schriften (Issue #142):**
- Google Fonts Stylesheet: `https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap` ✓
- Preconnect-Links: fonts.googleapis.com + fonts.gstatic.com ✓
- `body.fontFamily`: `"Inter Tight", system-ui, sans-serif` ✓
- **Evidence:** screenshots/local_01_startseite.png, Font-Link-Abfrage

**Sidebar-Extraktion (Issue #145):**
- Nav-Label `/trips`: `"Meine Touren"` ✓
- Sidebar-Struktur (3 Nav-Items + User-Menu): vorhanden ✓
- Mobile Top-Bar: sichtbar und korrekt positioniert (`fixed top-0 ... md:hidden`) ✓
- Active-State `/trips` (Highlighting via `bg-sidebar-accent font-medium`): funktioniert ✓
- Active-State `/` (Startseite): korrekt aktiv ✓
- **Evidence:** screenshots/local_01_startseite.png, local_02_trips.png, local_03_mobile.png

**E2E-Tests:**
```
nav-redesign.spec.ts:      7/7 PASS (tests 2–8 von 8 inkl. setup)
design-system-lauf-a.spec.ts: 8/8 PASS (tests 2–9 von 9 inkl. setup)
Laufzeit: ~3s je Suite
```

### Beobachtung: Inkonsistenz Seiten-Heading vs. Nav-Label

- Startseite zeigt Dashboard-Heading `"Meine Trips"`, Sidebar zeigt `"Meine Touren"`
- **Bewertung:** Diese Inkonsistenz ist spec-konform. Die Spec schreibt explizit `'Meine Touren'` als Bug-Fix *im Nav-Label* (Issue #145) vor, ohne den Dashboard-Heading zu ändern (der aus Issue #126 stammt). Kein Finding.

---

## Screenshots

| Datei | Inhalt |
|-------|--------|
| `screenshots/01_startseite.png` | Staging — Startseite (Altstand, no CSS tokens) |
| `screenshots/02_trips_seite.png` | Staging — Trips (Label "Meine Trips", Altstand) |
| `screenshots/03_compare_seite.png` | Staging — Orts-Vergleich |
| `screenshots/04_mobile_startseite.png` | Staging — Mobile (Altstand) |
| `screenshots/local_01_startseite.png` | Lokal — Startseite mit "Meine Touren" im Nav |
| `screenshots/local_02_trips.png` | Lokal — Trips aktiv, Label "Meine Touren" |
| `screenshots/local_03_mobile.png` | Lokal — Mobile Top-Bar sichtbar |

---

## Verdict: AMBIGUOUS

### Begründung

Die **Implementierung ist inhaltlich vollständig und spec-konform**:
- Alle 28 `--g-*`-CSS-Tokens korrekt in `@layer base :root`
- Inter Tight + JetBrains Mono korrekt eingebunden
- Nav-Label `"Meine Touren"` korrekt gesetzt
- Sidebar-Komponente extrahiert, Mobile-Top-Bar vorhanden
- Active-State funktioniert
- 7/7 nav-redesign E2E-Tests grün
- 8/8 design-system E2E-Tests grün
- Keine visuellen Regressionen erkennbar

**AMBIGUOUS statt VERIFIED**, weil Staging **noch nicht deployed** wurde. Die Änderungen liegen im lokalen Working-Tree (git working tree: modified/untracked), sind aber noch nicht committed und damit nicht auf Staging sichtbar. Das ist ein fehlender Deployment-Schritt, kein Implementierungsfehler.

**Nächste Schritte (Implementierer):**
1. `git add` + `git commit` für die geänderten Dateien
2. `git push origin main`
3. Staging-Auto-Deploy abwarten (~5 Min)
4. Staging-Smoke-Check (HTTP 200, CSS-Token `--g-accent` sichtbar, Nav-Label "Meine Touren")
5. `deploy-gregor-prod.sh` ausführen
6. Validator erneut aufrufen (oder manuellen Staging-Check als ausreichend betrachten)
