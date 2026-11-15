---
entity_id: fix_2954_speicherhinweis_kopfleiste
type: bugfix
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: fix-2954-speicherhinweis-kopfleiste
tags: [frontend, hub-kopf, save-indicator, a11y, adr-0119]
---

# Speicherhinweis in der Kopfleiste (Issue #2954)

## Approval

- [ ] Approved

## Purpose

Der Speicherhinweis („Gespeichert", „Speichere …", Fehler, Konflikt) schwebt heute als festes Overlay unten rechts über dem Inhalt aller Hub-Reiter und verdeckt dort Bedienelemente (Messung #2913: bei 1024 px 16 von 15 bis 11 von 10 Scroll-Positionen betroffen, bei 390 px 9 von 6). Er wandert als schlichter Text in die Kopfleiste, links vor das Drei-Punkte-Menü und den Hauptknopf, so wie im Mockup Fassung 3 — ohne etwas zu überdecken.

## Source

- **File:** `frontend/src/lib/components/ui/SaveIndicator.svelte`
- **Identifier:** `SaveIndicator` (Atom), Mount in `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`

> Schicht: Frontend (SvelteKit). Keine Go-/Python-Änderung.
> Trip/Ortsvergleich-Teilung: ein Atom, ein Mount im geteilten `HubKopf` (ADR-0110), kein Pendant-Bauteil (#1170).
> Mandantentrennung/Kanäle: nicht berührt (reine Anzeige, keine Nutzerdaten bewegt, kein Briefing-/Alarm-Inhalt).

## Estimated Scope

- **LoC:** Produktiv ca. +60/-60, Tests/Doku ca. +250
- **Files:** 3 Produktiv, ca. 10 Tests, ADR, Spec
- **Effort:** medium (Risiko MEDIUM: zentrales Element auf allen Hub-Reitern, viele E2E-Specs hängen am Testid)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveStatusStore.svelte.ts` (`SaveStatus`) | store | Zustand (idle/dirty/saving/conflict/error), `savedAt`; unverändert |
| `Dot` | UI-Atom | Zustandspunkt im Hinweis |
| i18n-Katalog `nav.*` | Katalog | Texte gespeichert/speichere/nicht_gespeichert/konflikt/nochmal_speichern/speicherfehler; keine neuen Texte |
| `HubKopf.svelte` | shared | neuer Mount-Ort in `.hub-actions` |
| `SubscriptionHeader.svelte` | shared | bisheriger Mount, wird entfernt |
| `TripHeader.svelte`, `compare/[id]/+page.svelte` | Aufrufer | übergeben `saveController`, unverändert |
| ADR-0110, ADR-0111, ADR-0118 | ADR | geteilter Kopf, Mockup Fassung 3 als Maßstab, Kopfleiste |
| `feat_880_autosave_overlay.md`, `feat_2284_s1_subscription_header.md` | Spec | Entscheidungen, die für den Hub abgelöst werden |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | Inline-Text statt `position:fixed`-Chip: kein Hintergrund, 12,5 px, Erfolg `--g-good`, Fehler/Konflikt `--g-danger-fg`, `aria-live="polite"`, JS-Timer (5 s) für den Erfolgstext, `gz-save-fade` und `white-space:nowrap` entfallen, Element bleibt im DOM, `data-testid`/`data-state` unverändert |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | Mount als erstes Kind in `.hub-actions` (vor Kebab), in beiden Sendemodi (Senden / Setup abschließen) |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | Mount entfernen; `saveController`-Prop bleibt für den Speicherweg |
| `docs/adr/0119-speicherhinweis-in-der-kopfleiste.md` | CREATE | löst #880 „fixes Overlay, nie unsichtbar" und #2284 AC-10 für den Hub ab |
| `docs/adr/README.md` | MODIFY | Index-Eintrag ADR-0119 (und „Abgelöst durch" bei den betroffenen Einträgen) |
| `frontend/e2e/fix-2954-speicherhinweis-kopfleiste.spec.ts` | CREATE | neue E2E-Spec (siehe Test Plan) |
| `frontend/e2e/feat-880-autosave-overlay.spec.ts` (:84–91, :207–213) | MODIFY | „position: fixed" → „in der Kopfleiste vor dem Kebab" |
| `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` (:915–960) | MODIFY | AC-10 „fixed, unten rechts" → „in der Kopfleiste" |
| `frontend/e2e/issue-758-save-indicator.spec.ts` (:111), `frontend/e2e/hub-save-chip.spec.ts` (:118), `frontend/e2e/epic-138-metriken-editor.spec.ts` (:114), `frontend/e2e/design-system-trip-vergleich.spec.ts` (:1129) | MODIFY | Prüfung „Gespeichert sichtbar beim Öffnen" → `data-state="idle"` und im DOM; Text erst nach echtem Speichern |
| `speicheranzeige_ruhe_kontrast.test.ts` | MODIFY | Kontrast neu: `--g-good` und `--g-danger-fg` gegen Kopfgrund, hell/dunkel, mindestens 4,5:1 |
| `subscription_header_einmal_gerendert.test.ts`, `subscription_header_kontextneutral.test.ts`, `saveIndicatorConflictBranch.test.ts`, `navigation_und_speicheranzeige_sprache.test.ts`, `bausteine_waechter_regeln.ts`, `harte_farben_waechter.test.ts` | MODIFY/CHECK | Mount-Ort-Wechsel nachziehen, Atom-Eintrag und Farben prüfen |

### Estimated Changes

- Files: ca. 16
- LoC: +310/-80

## Implementation Details

1. **Ort:** `HubKopf` `.hub-actions`, erstes Kind. Die Gruppe ist rechtsbündig (`justify-content:flex-end`); erscheinender oder verschwindender Text wächst nach links, Kebab und Senden-/Setup-Knopf bleiben an ihrer Stelle. Keine reservierte Mindestbreite (kostet am Handy Platz). Reicht der Platz nicht, bricht der Hinweis innerhalb der Aktionen um (bestehendes Verhalten, #2837 AC-8).
2. **Erfolg:** „Gespeichert" in `--g-good`, 12,5 px. Ein `$effect` auf `savedAt` und `state` startet einen 5-s-Timer, leert den Text und räumt den Timer bei jedem neuen Speichern und beim Abbau auf (jeder Speichervorgang startet neu; ein CSS-Animations-Ansatz startet bei idle zu idle nicht neu und entfällt).
3. **Zwischenzustände:** `dirty` („nicht gespeichert") und `saving` („Speichere …") sind sichtbar, solange der Zustand gilt.
4. **Fehler/Konflikt:** dauerhaft sichtbar in `--g-danger-fg` (Konflikt mit Knopf „Nochmal speichern"). Bewusste Abweichung vom Mockup (dort leert Zeile 679 auch den Fehler nach 5 s), weil ein Speicherfehler sonst unbemerkt bliebe (#880 AC-4 bleibt gültig).
5. **Beim Öffnen leer:** Text erscheint erst nach echtem Speichern (`savedAt` gesetzt); „Gespeichert" ohne Speichern wäre eine unwahre Aussage. Mockup-Toast startet ebenfalls leer.
6. **Barrierefreiheit:** Element ist eine stabile Region mit `aria-live="polite"` und bleibt immer im DOM; nur der Inhalt wechselt (Ansage statt Dauer-Anzeige). Das ersetzt die #880-Regel „nie unsichtbar".
7. **Farben:** nur Tokens, keine Hartwerte; `--g-bad` existiert nur im Mockup, Produktion nutzt `--g-danger-fg`.

## Expected Behavior

- **Input:** Speichervorgang im Trip-Hub oder Ortsvergleich-Hub (Autosave oder Knopf).
- **Output:** kurzer Statustext in der Kopfleiste links vor dem Menü; Erfolg verschwindet nach 5 s, Fehler/Konflikt bleiben.
- **Side effects:** Das feste Overlay unten rechts entfällt vollständig; kein Element im Inhalt wird mehr verdeckt.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Hub oder Ortsvergleich-Hub ist geöffnet und eine Einstellung wurde gerade gespeichert / When der Nutzer die Seite bei 390, 1024 und 1280 px Breite an jeder Scroll-Position durchgeht / Then liegt der Speicherhinweis an keiner Position über einem Bedienelement im Inhalt (`elementFromPoint` an jedem Bedienelement liefert das Element selbst, nie den Hinweis).
  - Test: E2E über Trip und Orte, drei Breiten, mehrere Scroll-Positionen; Messung wie in #2913, Original-Zusicherung neu geschrieben (Artefakt verloren).

- **AC-2:** Given ein Trip-Hub oder Ortsvergleich-Hub ist geöffnet / When der Nutzer speichert / Then erscheint der Hinweis genau einmal in der Kopfleiste, links vor dem Drei-Punkte-Menü und vor „Test schicken" bzw. (Vergleich-Entwurf) „Setup abschließen", in Trip und Orten gleich über den geteilten Kopf.
  - Test: E2E zählt `[data-testid="save-indicator"]` (genau 1), prüft per Boundingbox: Hinweis liegt innerhalb der Kopfleiste und links vom Kebab, in Trip, Orte und Vergleich-Entwurf.

- **AC-3:** Given eine Einstellung wurde erfolgreich gespeichert / When der Speichervorgang abgeschlossen ist / Then zeigt die Kopfleiste „Gespeichert" in Farbe `--g-good` mit 12,5 px Schrift, der Text verschwindet 5 Sekunden nach dem Speichern, und jeder neue Speichervorgang startet die 5 Sekunden neu.
  - Test: E2E prüft Farbe und Schriftgröße per `getComputedStyle`, Text nach ca. 4 s noch da, nach ca. 6 s weg; zweites Speichern nach 3 s hält den Text bis 5 s nach dem zweiten Speichern.

- **AC-4:** Given der Nutzer öffnet einen Hub, ohne etwas zu speichern / When die Seite fertig geladen ist / Then steht in der Kopfleiste kein Hinweistext, und die Region ist leer.
  - Test: E2E öffnet Trip und Ort, erwartet leeren Textinhalt bei `data-state="idle"`.

- **AC-5:** Given eine Änderung ist noch nicht gespeichert oder wird gerade gespeichert / When der Nutzer die Kopfleiste ansieht / Then ist „nicht gespeichert" bzw. „Speichere …" sichtbar, solange dieser Zustand gilt, ohne Zeitablauf.
  - Test: E2E verzögert die Speicher-Antwort, prüft Text und `data-state` (`dirty`/`saving`) über mehr als 5 s.

- **AC-6:** Given das Speichern schlägt fehl oder es liegt ein Konflikt vor / When der Nutzer wartet (länger als 5 s) / Then bleibt der Fehler- bzw. Konflikttext dauerhaft in `--g-danger-fg` sichtbar, beim Konflikt mit dem Knopf „Nochmal speichern", bis der Zustand behoben ist.
  - Test: E2E erzwingt Fehler (HTTP 500) und Konflikt (409), wartet 7 s, Text und Knopf noch da, Farbe aus `--g-danger-fg`; Klick auf „Nochmal speichern" löst erneutes Speichern aus. Abweichung vom Mockup ist begründet (siehe Implementation Details 4).

- **AC-7:** Given der Hinweis erscheint oder verschwindet / When der Nutzer das Drei-Punkte-Menü und „Test schicken" ansieht / Then ändern diese ihre Position nicht (rechtsbündig), und bei 390 px läuft die Kopfleiste nicht horizontal über (Umbruch innerhalb der Aktionen ist erlaubt).
  - Test: E2E misst Boundingbox von Kebab und Hauptknopf vor, während und nach dem Hinweis (Abweichung 0 px); bei 390 px `scrollWidth <= clientWidth` am Dokument.

- **AC-8:** Given ein Screenreader-Nutzer arbeitet im Hub / When sich der Speicherstatus ändert / Then wird die Änderung höflich angesagt (`aria-live="polite"`), die Region bleibt dauerhaft im DOM, und `data-testid="save-indicator"` sowie `data-state` bleiben mit dem Zustand des Controllers erhalten.
  - Test: E2E prüft Attribut `aria-live="polite"`, Region auch bei leerem Text im DOM, `data-state` folgt allen Zuständen (idle/dirty/saving/conflict/error); die rund 35 bestehenden Specs über Testid laufen unverändert weiter.

- **AC-9:** Given der Hinweis steht in Erfolgs- oder Fehlerfarbe auf dem Kopfgrund / When Hell- und Dunkelmodus geprüft werden / Then erreichen `--g-good` und `--g-danger-fg` gegen den Kopfgrund jeweils mindestens 4,5:1.
  - Test: Unit-Test `speicheranzeige_ruhe_kontrast.test.ts` rechnet WCAG-Kontrast aus den echten Token-Werten, hell und dunkel; E2E bestätigt die berechneten Farben im Browser.

- **AC-10:** Given die bisherige Entscheidung „fixes Overlay, nie unsichtbar" (#880) und #2284 AC-10 / When die Änderung ausgeliefert wird / Then liegt ADR-0119 vor, das beide für den Hub ablöst, und der Index in `docs/adr/README.md` führt es konsistent.
  - Test: `tests/test_adr_index_drift.py` grün (Index-Konsistenz); Dokumentations-Prüfung ausschließlich über diesen Wächter (`# doc-compliance-test`).

## Definition of Done

- AC-1 bis AC-10 grün, die neue Verdeckungs-Zusicherung war vor der Umsetzung rot und ist danach grün (Trip und Orte, 390/1024/1280 px).
- Adversary VERIFIED; die Mutationen aus dem Test Plan werden jeweils von mindestens einem Test gefangen.
- ADR-0119 im Index; ein PR mit allen 6 CI-Checks grün gemergt; Staging-Prüfung bestanden, Prod-Deploy mit Selftest-Exit 0.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Neue E2E `frontend/e2e/fix-2954-speicherhinweis-kopfleiste.spec.ts`: GIVEN Trip- und Orte-Hub bei 390/1024/1280 px WHEN gespeichert und durchgescrollt THEN kein Bedienelement vom Hinweis verdeckt (rot gegen heutiges Overlay); Hinweis liegt in der Kopfleiste vor dem Kebab; „Gespeichert" verschwindet nach 5 s, Neustart bei erneutem Speichern; Fehler/Konflikt bleiben; beim Öffnen leer; Kebab/Senden verschieben sich nicht; kein horizontaler Überlauf bei 390 px.
- [ ] `speicheranzeige_ruhe_kontrast.test.ts`: GIVEN Token-Werte hell/dunkel WHEN Kontrast gegen Kopfgrund berechnet wird THEN `--g-good` und `--g-danger-fg` ≥ 4,5:1.
- [ ] Bestehende Specs anpassen (Positions- und Beim-Öffnen-Zusicherungen): `feat-880-autosave-overlay.spec.ts`, `trip-hub-kopf-region-aktivitaet.spec.ts`, `issue-758-save-indicator.spec.ts`, `hub-save-chip.spec.ts`, `epic-138-metriken-editor.spec.ts`, `design-system-trip-vergleich.spec.ts`.
- [ ] Unit-Wächter nachziehen: `subscription_header_einmal_gerendert.test.ts` (genau eine Instanz im geteilten Kopf), `subscription_header_kontextneutral.test.ts`, `saveIndicatorConflictBranch.test.ts`, `navigation_und_speicheranzeige_sprache.test.ts`, `bausteine_waechter_regeln.ts`, `harte_farben_waechter.test.ts`.
- [ ] Mutations-Gegenprobe (Adversary): z. B. Timer auf 50 s, Fehler mit Timer leeren, Mount zurück an SubscriptionHeader oder `position:fixed` wiederherstellen; jede Verfälschung muss von mindestens einem Test gefangen werden.

## Known Limitations

- Kein reservierter Platz für den Text: bei 390 px kann der Hinweis (vor allem der Konflikt mit Knopf) innerhalb der Aktionen umbrechen und die Leiste leicht erhöhen; die Aktionen selbst bleiben stehen.
- Nach 5 s trägt nur noch die Region den Status; wer „Gespeichert" verpasst, sieht keinen Dauerhinweis (bewusst, wie Mockup).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0119 (neu, „Speicherhinweis in der Kopfleiste")
- **Rationale:** #880 hat ein festes, nie unsichtbares Overlay entschieden und #2284 AC-10 den Mount unter dem Titelblock; beides widerspricht dem Mockup Fassung 3 (ADR-0111) und verdeckt Bedienelemente. Eine Entscheidung wird nie still rückgängig gemacht, daher neues ADR mit „Abgelöst durch" für den Hub. Inhalt: Ort Kopfleiste, 5 s für Erfolg, Fehler/Konflikt dauerhaft, `aria-live`-Region statt Dauer-Sichtbarkeit.

## Changelog

- 2026-11-15: Initial spec created (Workflow fix-2954-speicherhinweis-kopfleiste)
- 2026-11-15: ADR-Nummer: Die in AC-10 und den Affected Files genannte ADR-0119 erscheint als **ADR-0120** (`docs/adr/0120-speicherhinweis-in-der-kopfleiste.md`), weil #3039 die Nummer 0119 parallel belegt hat (`0119-vergleich-channel-layouts.md`). Inhalt unverändert.
