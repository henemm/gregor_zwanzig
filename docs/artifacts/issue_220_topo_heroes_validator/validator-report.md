---
spec: docs/specs/modules/issue_220_topo_heroes.md
server: https://staging.gregor20.henemm.com
validated_at: 2026-05-13T20:45:00+02:00
validator: external-validator (isolated session)
---

# External Validator Report — Issue #220 Topo-Heroes

**Spec:** docs/specs/modules/issue_220_topo_heroes.md
**Datum:** 2026-05-13T20:45+02:00
**Server:** https://staging.gregor20.henemm.com
**User:** validator-issue110 (Cookie-Auth)

## Methodik

- Reine Black-Box-Validierung gegen das laufende Staging-System
- Keine Lektüre von `src/`, `git log`, älteren `docs/artifacts/`-Inhalten oder `workflow_state.json`
- Tools: `curl` für DOM-Inspektion, Playwright (headless Chromium, Viewport 1440×900) für Screenshots + DOM-Assertions
- Trip für AC-2: `validator-test-with-dc` (Seed-Trip `e2e-cockpit-test` aus Spec §4 existiert auf Staging nicht; AC-2-Text fordert keinen bestimmten ID — geprüfter Trip erfüllt dieselbe semantische Rolle "Trip-Detail Overview-Tab")

## Checklist

| # | Acceptance Criterion | Beweis | Verdict |
|---|----------------------|--------|---------|
| AC-1 | Cockpit-Topbar auf `/` ist sichtbar, im selben TopoBg-Wrapper liegt `.g-topo` (Opacity 0.3) | DOM-Assertion liefert `{ok:true, depth:1, opacity:"0.3"}`. Screenshot `ac1-cockpit-topbar.png` zeigt das Linien-Muster hinter "Guten Tag" und um die CTAs | **PASS** |
| AC-2 | Trip-Hero auf `/trips/<id>` ist sichtbar, im selben TopoBg-Wrapper liegt `.g-topo` (Opacity 0.4) | DOM-Assertion liefert `{ok:true, depth:1, opacity:"0.4"}`. Screenshot `ac2-trip-hero.png` zeigt deutliche Topo-Linien hinter den Stat-Tiles ("Aktive Etappe", "Nächstes Briefing", "Tage bis Start") | **PASS** |
| AC-3 | Stepper auf `/trips/new` hat einen TopoBg-Ancestor mit `.g-topo`-Descendant (Opacity 0.4) | DOM-Assertion liefert `{ok:true, opacity:"0.4"}`. Screenshot `ac3-wizard-stepper.png` zeigt Topo-Linien zwischen den Step-Kreisen 1–4 | **PASS** |
| AC-4 | `[data-testid="trip-wizard-step1-profile"]` hat KEINEN `.g-topo`-Ancestor (Scope-Guard) | DOM-Assertion: weder ein Ancestor mit Klasse `g-topo` noch ein topo-bg-Wrapper enthält das Element. Manuelles Tracing der HTML-Struktur bestätigt: TopoBg-Wrapper schließt vor `<div class="min-h-[300px] mt-6">`, in dem `step1-profile` sitzt. Screenshot `ac3-wizard-stepper.png`: Eingabe-Bereich darunter ist topo-frei | **PASS** |
| AC-5 | Texte in allen drei Hero-Bereichen bleiben lesbar | Visuelle Sichtprüfung der drei Screenshots: H1 ("Guten Tag", "Mit DisplayConfig", "Neuer Trip"), Eyebrows ("13. Mai 2026", "SCHRITT 1 VON 4"), Stat-Values, Stepper-Labels alle klar lesbar; Topo-Muster ist subtil im Hintergrund | **PASS** |
| AC-6 | Bestehende E2E-Suites bleiben grün | Außerhalb des Validator-Scopes (Test-Pipeline, kein User-sichtbares Verhalten am Laufzeitsystem). Indirekter Indikator: alle drei Pages liefern HTTP 200 mit intakten Test-IDs (`cockpit-topbar`, `trip-hero`, `trip-wizard-stepper`, `trip-wizard-step1-profile` alle auffindbar) | **UNKLAR** |

## DOM-Strukturen (Auszüge)

### Cockpit (`/`)
```
<div class="relative overflow-hidden">                    ← TopoBg outer
  <div data-slot="topo-bg" class="g-topo absolute inset-0"
       style="--g-topo-opacity: 0.3;"></div>             ← Topo layer
  <div class="relative">                                 ← TopoBg inner
    <header data-testid="cockpit-topbar"
            class="flex items-center justify-between gap-4 flex-wrap p-6 rounded-lg">
      ...
    </header>
  </div>
</div>
```

### Trip-Detail (`/trips/validator-test-with-dc`)
```
<div class="trip-overview ...">
  <div class="relative overflow-hidden">
    <div data-slot="topo-bg" class="g-topo absolute inset-0"
         style="--g-topo-opacity: 0.4;"></div>
    <div class="relative">
      <div data-testid="trip-hero" class="trip-hero ...">
        <h1 data-testid="trip-hero-title">Mit DisplayConfig</h1>
        ...
      </div>
    </div>
  </div>
</div>
```

### Wizard (`/trips/new`)
```
<div data-testid="trip-wizard-shell" class="max-w-3xl mx-auto py-6 px-4">
  <div class="relative overflow-hidden">                    ← TopoBg outer
    <div data-slot="topo-bg" class="g-topo absolute inset-0"
         style="--g-topo-opacity: 0.4;"></div>
    <div class="relative">
      <div class="p-6 rounded-lg mb-6">
        <header class="space-y-1 mb-4">
          <span data-slot="eyebrow">Schritt 1 von 4</span>
          <h1>Neuer Trip</h1>
        </header>
        <div data-testid="trip-wizard-stepper">...</div>     ← Stepper INNEN
      </div>
    </div>
  </div>                                                    ← TopoBg ENDE
  <div class="min-h-[300px] mt-6">                          ← Step-Slot AUSSEN
    <div data-testid="trip-wizard-step1-profile">...</div>
  </div>
</div>
```

Wrap-Scope ist exakt wie Spec §3 verlangt: `<header>` + `<Stepper>` sind innen, Step-Slot ist außen.

## Findings

Keine Findings.

### Beobachtungen (kein Blocker)

- **AC-6 nicht laufzeit-prüfbar:** Die Forderung "bestehende E2E-Suites bleiben grün" ist eine CI-/Test-Pipeline-Aussage. Validator prüft das laufende System, nicht die Test-Suite. Test-IDs sind intakt; HTTP 200 auf allen drei Routen → starkes Indiz, aber kein direkter Beweis.
- **Spec-Seed-Trip fehlt auf Staging:** `/trips/e2e-cockpit-test` liefert 404. AC-2-Text fordert keine konkrete ID; geprüft mit `/trips/validator-test-with-dc` (semantisch äquivalent: Trip-Detail Overview-Tab mit gerendertem Hero). Falls die E2E-Suite (Spec §4) stur `e2e-cockpit-test` ansteuert, müsste der Seed im Staging-Setup angelegt werden — ist aber ein Test-Setup-Thema, nicht ein Mangel der Implementierung.

## Verdict: **VERIFIED**

### Begründung

Alle vier strukturellen Acceptance Criteria (AC-1 bis AC-4) sind am laufenden Staging-System über DOM-Assertions + Screenshot-Evidence bestätigt:

- **AC-1:** Cockpit-Topbar im TopoBg-Wrapper mit `.g-topo`, Opacity 0.3 ✓
- **AC-2:** Trip-Hero im TopoBg-Wrapper mit `.g-topo`, Opacity 0.4 ✓
- **AC-3:** Wizard-Stepper hat TopoBg-Ancestor mit `.g-topo`, Opacity 0.4 ✓
- **AC-4:** Scope-Guard — Step1-Profile sitzt nachweislich AUSSERHALB des TopoBg-Wrappers (HTML-Struktur + DOM-Assertion + Screenshot) ✓
- **AC-5:** Lesbarkeit visuell bestätigt, keine Text-Kontrast-Probleme ✓
- **AC-6:** Außerhalb des Validator-Scopes, aber alle Test-IDs intakt → Regressionsrisiko niedrig ⚠

Die implementierten Opacity-Werte (0.3 / 0.4 / 0.4) entsprechen exakt der Spec. Die TopoBg-Wrapper-Reihenfolge (`relative overflow-hidden` außen, `.g-topo absolute inset-0` als Geschwister, `.relative` als Content-Container) ist konsistent über alle drei Stellen. Die Wizard-Wrap-Reihenfolge (Stepper innen, Step-Slot außen) erfüllt den kritischen Scope-Guard und ist der heikelste Teil der Spec — er ist korrekt umgesetzt.

## Artefakte (von dieser Validator-Session erzeugt)

- `ac1-cockpit-topbar.png` — 1440×900 Screenshot Startseite, Topo sichtbar
- `ac2-trip-hero.png` — 1440×900 Screenshot Trip-Detail, Topo deutlich sichtbar
- `ac3-wizard-stepper.png` — 1440×900 Screenshot Wizard, Topo um Header+Stepper, Step-Slot topo-frei
