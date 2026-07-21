---
entity_id: issue_647_home_fidelity
type: module
created: 2026-06-08
updated: 2026-06-08
status: active
version: "1.0"
tags: [frontend, home, compare, design-compliance, rework]
---

# Spec: #647 Home-Screen Fidelity — Nachzügler aus #579

## Approval

- [x] Approved (PO 'go' 2026-06-08)

## Purpose

Drei bei #579 (Epic #575) bewusst zurückgestellte Home-Screen-Fidelity-Punkte abarbeiten: (3) die Compare-Outbox-Karte zeigt statt eines Platzhalters die echte Versand-Timeline (Zuletzt/Nächster) + der Compare-Hero den echten nächsten Versand; (1) der Planning-Modus wird 1:1 an `screen-home-planning.jsx` angeglichen und live DOM-verifiziert; (2) der Trip-Modus-Empty/Archiv-Bereich wird echt am Staging-DOM bewiesen.

## Source

- **File:** `frontend/src/routes/+page.svelte` (Frontend / User-UI, SvelteKit)
- **File:** `frontend/src/routes/_home/cockpitHelpers.ts` (neuer Pure-Helper `homeCompareTimeline`)
- **Identifier:** Compare-Outbox-Block, Compare-Hero „Nächster Versand", Planning-Archiv-Block

## Quelle der Wahrheit

- `claude-code-handoff/.../jsx/screen-home.jsx` — `homeCompareTimeline(sub)` (Z.27-34), Compare-Hero (Z.85-110)
- `claude-code-handoff/.../jsx/screen-home-planning.jsx` — Planning-Modus, Archiv in `<Card padding={20}>` (Z.133)

## Estimated Scope

- **LoC:** ~70 (Helper ~25, +page.svelte-Wiring ~40, Planning-Card ~6)
- **Files:** 2 Produktiv (+page.svelte, cockpitHelpers.ts) + Tests + Verifikations-Tooling
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `deriveNextSend(preset, now)` | bestehend (cockpitHelpers568.ts) | berechnet nächsten Versand-Timestamp aus schedule/hour_from/weekday |
| `formatNextSend(date)` | bestehend (subscriptionHelpers.ts) | Anzeige-String für nächsten Versand |
| `ComparePreset.letzter_versand` | bestehend (DTO) | ISO-8601 echte Versand-Historie = lastSent |
| `BriefingTimelineRow` | bestehend (molecule) | Zeilen-Render (when/kind/channels/status/etappe) |

## Implementation Details

```
// cockpitHelpers.ts — neuer Pure-Helper (seiteneffektfrei, kein Mock):
homeCompareTimeline(preset, now) -> Report[]
  rows = []
  if preset.letzter_versand:
      rows.push({ when: "Zuletzt · " + formatLast(letzter_versand),
                  kind: "Vergleich", channels: preset.empfaenger,
                  status: "sent",
                  etappe: preset.location_ids.length + " Orte" + (region ? " · "+region : "") })
  next = deriveNextSend(preset, now)
  if next:
      rows.push({ when: "Nächster · " + formatNextSend(next),
                  kind: "Vergleich", channels: preset.empfaenger,
                  status: "planned", etappe: <wie oben> })
  return rows
// KEINE Fake-Zeile: fehlt letzter_versand → nur "Nächster"; fehlt next (manual) → nur "Zuletzt".

// +page.svelte Compare-Outbox (Z.606-608): Platzhalter ersetzen durch
//   {#each homeCompareTimeline(compareHero, now) as r}<BriefingTimelineRow report={r}/>{/each}
//   Leerer Fall (weder lastSent noch next, z.B. manual + nie gesendet) → bestehender Platzhalter bleibt.

// +page.svelte Compare-Hero (Z.498): "—" ersetzen durch
//   {formatNextSend(deriveNextSend(compareHero, now)) ?? '—'}

// Hero-Untertitel (Z.456-461): "Vorhersage {horizon}" wird NICHT ergänzt (PO-Entscheidung
//   2026-06-08: ersatzlos gestrichen, kein ComparePreset.horizon-Feld). Status quo bleibt.

// Planning-Archiv (Z.809-818): Block in <Card padding={20}> wrappen (1:1 screen-home-planning.jsx).
//   Trip-/Compare-Modus-Archiv bleibt ohne Card (#579 AC-6 / screen-home.jsx) — unberührt.
```

## Expected Behavior

- **Input:** `ComparePreset` (mit/ohne `letzter_versand`, schedule daily/weekly/manual), aktuelle Zeit.
- **Output:** 0–2 Timeline-Zeilen; Hero zeigt echten nächsten Versand statt „—".
- **Side effects:** keine. Reine Ableitung aus vorhandenen DTO-Feldern, kein Netz-/Wetter-Abruf.

## Acceptance Criteria

**AC-1:** Given ein aktiver ComparePreset mit gesetztem `letzter_versand` und `schedule="daily"`, When `homeCompareTimeline(preset, now)` aufgerufen wird, Then liefert es genau zwei Zeilen — die erste mit `when` beginnend „Zuletzt · " und `status="sent"`, die zweite mit `when` beginnend „Nächster · " und `status="planned"`, beide mit `channels === preset.empfaenger` und `etappe` enthält die Orte-Anzahl.
  - Test: Pure-Function-Unit-Test gegen echte Preset-Fixture (kein Mock), prüft Zeilen-Anzahl, `when`-Präfixe, `status`, `channels`.

**AC-2:** Given ein aktiver ComparePreset **ohne** `letzter_versand` (noch nie gesendet), When `homeCompareTimeline(preset, now)` aufgerufen wird, Then enthält das Ergebnis **keine** „Zuletzt"-Zeile (nur „Nächster") — es werden keine Fake-/Platzhalter-Versanddaten erfunden.
  - Test: Pure-Function-Unit-Test, assert keine Zeile mit `status="sent"`, kein „Zuletzt"-Präfix.

**AC-3:** Given die Home-Seite im Compare-Modus auf Staging (eingeloggt, aktiver Preset mit Historie), When der Nutzer die Outbox-Karte rechts betrachtet, Then sieht er die zwei Timeline-Zeilen mit Kanal-Pills und GESENDET/GEPLANT-Markierung statt des Platzhaltertexts „Versand läuft automatisch gemäß Zeitplan.".
  - Test: staging-validator Playwright-DOM-Proof am echten Compare-Modus.

**AC-4:** Given der Compare-Hero auf Staging, When er gerendert wird, Then zeigt die Kachel „Nächster Versand" einen echten Zeit-/Datumswert (aus `deriveNextSend`) statt „—", **und** der Hero-Untertitel enthält **kein** „Vorhersage {…}" (bleibt „{Region} · N Orte verglichen").
  - Test: staging-validator DOM-Proof — „Nächster Versand"-Kachel ≠ „—", Untertitel enthält nicht „Vorhersage".

**AC-5:** Given der Planning-Modus (Konto ohne aktiven Trip und ohne aktiven Vergleich) auf Staging, When die Seite gerendert wird, Then ist der Archiv-Block in eine Card (`<Card padding={20}>`) eingebettet — 1:1 zu `screen-home-planning.jsx` —, und Banner („Aktuell läuft kein Trip"), „Weiter einrichten", „Schnell anlegen" sind als DOM-Knoten vorhanden.
  - Test: staging-validator Playwright-DOM-Proof in echtem Planning-Daten-Zustand (geseedetes leeres Konto).

**AC-6:** Given der Trip-Modus (Konto mit heute-überspannendem Live-Trip **und** abgeschlossenen Trips) auf Staging, When die Seite gerendert wird, Then ist der Empty/Archiv-Bereich per DOM nachweisbar: Eyebrow „Einrichten", Titel „Frühere Trips", quiet-Button „Alle anzeigen" und mindestens eine Archiv-Karte.
  - Test: staging-validator Playwright-DOM-Proof in echtem Trip-Daten-Zustand (geseedetes Konto mit Live- + Archiv-Trips).

**AC-7:** Given die bestehenden Modi (Trip/Compare/Planning) und die unveränderten Teile der Seite, When die volle pytest/node-Suite läuft, Then bleibt das Verhalten der nicht-betroffenen Bereiche unverändert (keine neue Regression gegenüber `origin/main` — Failure-Mengen-Diff leer).
  - Test: Failure-Mengen-Vergleich (`comm -13`) vor/nach Änderung; Desktop-Render der nicht-Compare-Outbox-Bereiche unverändert.

## Verifikations-Enabler (Implementierungs-Hinweis, nicht-AC)

Der eigentliche #579-Blocker: das Staging-Test-Konto hat aktive Presets → immer Compare-Modus. Für AC-5/AC-6 werden dedizierte mandantengetrennte Staging-Daten-Zustände geseedet (eigene `user_id`, nie `default`): ein leeres Konto (Planning) und ein Konto mit einem Live-Trip (Etappen-Daten überspannen „heute") plus abgeschlossenen Trips (Trip-Modus). Seeding via API; Aufräumen nach der Verifikation.

## Out of Scope

- Neues `ComparePreset.horizon`-Feld (PO-Entscheidung: gestrichen).
- Trip-/Compare-Modus-Archiv-Card (bleibt cardlos per #579 AC-6).
- Änderungen an Topbar/PageHeader (bewusste #579-AC-7-Vereinheitlichung).

## Changelog

### v1.0 (2026-06-08)
- Initiale Spec für #647 Home-Screen Fidelity — Nachzügler aus #579 (Compare-Outbox-Timeline, Compare-Hero „Nächster Versand", Planning-Archiv-Card, Trip-/Planning-Modus DOM-Verifikation).
