---
entity_id: refactor_1286_shared_versandzeit
type: refactor
created: 2026-07-17
updated: 2026-07-17
status: draft
workflow: refactor-1286-shared-versandzeit
---

# Spec: Geteilte Versandzeit-Komponente im Anlege-Assistenten

- **Workflow:** refactor-1286-shared-versandzeit
- **Issue:** #1286
- **created:** 2026-07-17
- **Typ:** Frontend-Wartbarkeits-Refactor (eine bewusste UX-Änderung: Wizard-Zeitplan-Optik wird an den Trip-Detail-Versand-Tab angeglichen)
- **ADR-Nr.:** keine (folgt bestehender Teilungs-Invariante / Epic #1230, keine neue Architekturentscheidung)

## Approval

- [ ] Approved

## Purpose

Der Anlege-Assistent (`TripNewEditor`) ist der letzte verbliebene Live-Ort, der den
Morgen-/Abend-Zeitplan-Block (Uhrzeit, Master-Switch, Quick-Pick-Chips, Trend) mit
eigenem Markup rendert, statt die bereits existierende geteilte `VTSchedulePlan`
zu nutzen — die der Trip-Detail-Tab „Versand" und der Ortsvergleich-Editor schon
verwenden. Diese Duplikation ist der strukturelle Grund für Issue #1280 (Stunden-
Raster musste an zwei Stellen gepflegt werden). Ziel: den Inline-Zeitplan-Block in
`EditReportConfigSection.svelte` durch `<VTSchedulePlan context="route" .../>`
ersetzen, sodass künftig genau EIN Ort Zeitplan-Markup pflegt.

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
- **Identifier:** Zeitplan-Block Z. 232–344 (`{#if showSchedule}` … Morgen-/Abend-`Card.Root`), State-Felder Z. 46–51, Read-Modify-Write `$effect` Z. 174–216, Quick-Pick-Handler Z. 218–228
- **Ziel-Komponente:** `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` (bereits live in `VersandTab.svelte` für `context="route"` und `context="vergleich"`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `VTSchedulePlan.svelte` | component | Geteilte Ziel-UI für Morgen-/Abend-Zeitplan + Trend-Karte, controlled (Callback-Props) |
| `EditReportConfigSection.svelte` | component | Wirt-Komponente im Wizard-Tab „Briefing-Zeitplan"; behält State-Ownership + Read-Modify-Write |
| `VersandTab.svelte` (`context="route"`/`"vergleich"`) | component | Referenzmuster für Verdrahtung: `makeToggleHandler`/`makeTimeHandler`-Factories (Z. 160–169), Aufruf-Stelle Z. 215–229 (route) und Z. 250–269 (vergleich) |
| `toHHMMSS` (`$lib/utils/time`) | util | Serialisiert `HH:MM` → `HH:MM:SS` beim Schreiben in `reportConfig` |
| `ReportConfig` (`$lib/types`) | type | Datenmodell, bleibt unverändert |
| `CompareWizardState` (`wiz`) | state | Ortsvergleich-Ziel-Felder `morningTime`/`eveningTime`/`morningEnabled`/`eveningEnabled` |
| `briefingChannelGating.ts` (`syncSendFlags`, `hasNoActiveChannel`) | util | Bestehendes Kanal-Gating in EditReportConfigSection, bleibt unangetastet |

## Estimated Scope

- **LoC:** ~ −110 / +50 (Inline-Block raus, Einbindung + Callbacks + Chip-Erweiterung in VTSchedulePlan rein)
- **Files:** 2 Kern-Dateien (`EditReportConfigSection.svelte`, `VTSchedulePlan.svelte`) + Test-Dateien
- **Effort:** medium
- **Risk:** medium (State-Ownership-Bruch controlled/stateful; Read-Modify-Write darf nicht kollidieren)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | MODIFY | Zeitplan-Block Z. 232–344 durch `<VTSchedulePlan context="route" .../>` ersetzen; bestehende `$state`-Felder + Read-Modify-Write-`$effect` bleiben unverändert, werden nur an VTSchedulePlan-Callback-Props verdrahtet; `hasActiveChannel` wird lokal aus `send_email`/`send_telegram`/`send_sms` abgeleitet |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` | MODIFY | Quick-Pick-Chips (`report-morning-quickpick-07/-18`, `report-evening-quickpick-07/-18`) ergänzen, context-agnostisch, gleiche `onMorningTime`/`onEveningTime`-Callbacks wie das Zeit-Input |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | Keine Verdrahtungsänderung nötig für `route`; für `vergleich` müssen ggf. Chip-Callbacks (`onMorningTime`/`onEveningTime`) bereits vorhandene `makeTimeHandler`-Props nutzen — falls VTSchedulePlan die Chips intern über dieselben Props feuert, ist hier keine Änderung nötig; nur verifizieren |
| Playwright/Vitest-Testdateien für Wizard-Zeitplan + VTSchedulePlan-Chips | CREATE/MODIFY | Neue/angepasste Tests für die drei Kontexte (Assistent, Trip-Detail, Ortsvergleich) |

## Implementation Details

**Technischer Ansatz (aus Analyse, PO-bestätigt 2026-07-17):**

1. In `EditReportConfigSection.svelte` wird der Markup-Block Z. 232–344 (zwei
   `Card.Root`-Blöcke mit Master-Switch, Uhrzeit-Input, Quick-Pick-Chips, Trend-
   Checkbox) entfernt und durch einen Aufruf von `<VTSchedulePlan context="route" .../>`
   ersetzt, analog zur Verdrahtung in `VersandTab.svelte` Z. 215–229 (Faktory-
   Funktionen `makeToggleHandler`/`makeTimeHandler` statt `bind:value`).
2. Die bestehenden internen `$state`-Felder (`morning_enabled`, `morning_time`,
   `evening_enabled`, `evening_time`, `multi_day_trend_morning`,
   `multi_day_trend_evening`) und der Read-Modify-Write-`$effect` (Z. 174–216)
   bleiben **komplett unverändert** — es gibt weiterhin genau EINEN Schreiber pro
   Feld. Die Umstellung betrifft nur, WIE der State in die UI gerendert wird
   (VTSchedulePlan statt Inline-Markup), nicht WER ihn hält.
3. `hasActiveChannel` (Pflicht-Prop von VTSchedulePlan) wird lokal aus
   `send_email || send_telegram || send_sms` abgeleitet — analog
   `activeChannelCount` in `VersandTab.svelte` Z. 132–134.
4. `VTSchedulePlan.svelte` bekommt zusätzlich die vier Quick-Pick-Chips (Morgens
   07:00 / Abends 18:00, je Karte), 1:1 aus dem Markup von
   `EditReportConfigSection.svelte` Z. 258–276/314–332 übernommen, aber mit den
   bestehenden `onMorningTime`/`onEveningTime`-Callback-Props verdrahtet (Chip-
   Klick ruft denselben Callback wie das Uhrzeit-Feld mit dem Chip-Zeitwert auf —
   kein neuer Callback-Typ nötig).
5. Damit bekommen automatisch auch der Trip-Detail-Versand-Tab
   (`BriefingScheduleTab` → `VersandTab context="route"`) und der Ortsvergleich
   (`VersandTab context="vergleich"`, schreibt in `wiz.morningTime`/`wiz.eveningTime`)
   die Chips, ohne dass diese Dateien selbst Zeitplan-Markup duplizieren.

**Ausdrücklich NICHT angefasst:** Kanäle-Block (Z. 349–439) und E-Mail-Inhalt-
Block (Z. 444–523) in `EditReportConfigSection.svelte` bleiben unverändert
inklusive `weatherChannels`-Kanal-Gating und dem dort bereits vorhandenen
`briefings-channel-empty`-Leerzustand.

## Expected Behavior

- **Input:** User öffnet den Anlege-Assistenten (`/trips/new`), Tab „Briefing-
  Zeitplan" (Desktop Z. 765 / Mobile Z. 990 in `TripNewEditor.svelte`).
- **Output:** Zeitplan-UI ist funktionsgleich zu vorher (Master-Switches, Uhrzeit,
  Quick-Pick-Chips, Trend), aber visuell identisch zum Trip-Detail-Versand-Tab
  (atoms-`Card`-Styling, separate „Mehrtages-Trend"-Karte statt Trend inline).
- **Side effects:** `reportConfig` wird wie bisher per Read-Modify-Write in
  `EditReportConfigSection` geschrieben (kein neuer Schreibpfad). Kein Backend-
  Aufruf ändert sich, kein neues Feld in `ReportConfig`.

## Acceptance Criteria

- **AC-1:** Given ich öffne den Anlege-Assistenten und den Tab „Briefing-
  Zeitplan" / When die Seite gerendert ist / Then sehe ich Morgen- und Abend-
  Briefing-Karten mit den Testids `morning-master-switch`, `report-morning-time`,
  `evening-master-switch`, `report-evening-time`, `report-morning-trend`,
  `report-evening-trend` — gerendert durch `VTSchedulePlan`, nicht mehr durch
  eigenes Markup in `EditReportConfigSection`.
  - Test: Playwright öffnet `/trips/new`, klickt zum Tab „Briefing-Zeitplan",
    prüft Sichtbarkeit aller sechs Testids.

- **AC-2:** Given ich bin im Zeitplan-Tab des Anlege-Assistenten / When ich das
  Uhrzeit-Feld `report-morning-time` per Pfeiltasten/Scroll in Stundenschritten
  bediene / Then springt der Wert in vollen Stunden (`step={3600}`, Issue #1280)
  — identisch zum Verhalten im Trip-Detail-Versand-Tab.
  - Test: Playwright prüft das `step`-Attribut beider Zeit-Inputs (`report-
    morning-time`, `report-evening-time`) auf `3600`.

- **AC-3:** Given ich bin im Zeitplan-Tab (Anlege-Assistent, `context="route"`)
  / When ich auf den Chip `report-morning-quickpick-07` bzw.
  `report-morning-quickpick-18` klicke / Then übernimmt `report-morning-time`
  sofort `07:00` bzw. `18:00`, sichtbar im Feld und im persistierten
  `reportConfig.morning_time`. Analog für `report-evening-quickpick-07/-18` und
  `report-evening-time`.
  - Test: Playwright klickt jeden der vier Chips einzeln, liest den Zeit-Input
    danach aus und prüft den erwarteten Wert.

- **AC-4:** Given ich bin im Trip-Detail-Tab „Versand" (`context="route"`, via
  `BriefingScheduleTab`) ODER im Ortsvergleich-Editor (`context="vergleich"`)
  / When ich dort die gleichen vier Quick-Pick-Chips anklicke / Then wirkt der
  Klick über denselben `onMorningTime`/`onEveningTime`-Callback wie im Anlege-
  Assistenten — im Ortsvergleich landet der Wert korrekt in
  `wiz.morningTime`/`wiz.eveningTime`.
  - Test: Playwright-Läufe für Trip-Detail-Versand-Tab UND Ortsvergleich-Editor
    Step „Versand", je Klick auf einen Chip + Wert-Verifikation.

- **AC-5:** Given eine der beiden Karten ist deaktiviert (Master-Switch aus)
  / When ich das zugehörige Uhrzeit-Feld ansehe / Then ist es `disabled` und der
  zugehörige Quick-Pick-Chip ebenfalls `disabled` — Wert bleibt dabei erhalten
  (kein Datenverlust beim Wiedereinschalten).
  - Test: Playwright schaltet `morning-master-switch` aus, prüft `disabled` auf
    `report-morning-time` und `report-morning-quickpick-07`, schaltet wieder ein,
    prüft dass der zuvor gesetzte Zeitwert unverändert ist.

- **AC-6:** Given ich ändere im Anlege-Assistenten Uhrzeit oder Chip-Wert eines
  Briefings / When der Trip danach gespeichert und aus der API neu geladen wird
  / Then sind `morning_time`/`evening_time` als `HH:MM:SS` persistiert (via
  `toHHMMSS`) UND alle client-unbekannten Felder aus dem ursprünglich geladenen
  `reportConfig`-Blob (z. B. `change_threshold_*`) sind byte-identisch erhalten —
  Read-Modify-Write bleibt der einzige Schreibpfad, keine Doppel-Schreiber-
  Kollision zwischen `EditReportConfigSection` und `VTSchedulePlan`.
  - Test: Vitest/Playwright-Fixture mit einem `reportConfig`-Blob, der ein
    unbekanntes Feld (`change_threshold_wind: 5`) enthält; nach Chip-Klick +
    Read wird geprüft, dass das Feld weiterhin vorhanden und unverändert ist.

- **AC-7:** Given der Anlege-Assistent lädt / When man `ReportConfig`-Typ und
  alle API-Aufrufe des Zeitplan-Pfads vergleicht / Then sind sie unverändert —
  kein neues Feld, kein neuer Endpunkt, keine Backend-Änderung; die Umstellung
  betrifft ausschließlich `frontend/src`.
  - Test: Diff-Review der PR zeigt keine Änderungen außerhalb
    `frontend/src/lib/components/edit/EditReportConfigSection.svelte`,
    `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` und
    zugehörigen Testdateien.

- **AC-8:** Given der Anlege-Assistent, Tab „Briefing-Zeitplan" / When ich die
  Kanäle-Sektion (`channel-email`, `channel-telegram`, `channel-sms`) und die
  E-Mail-Inhalt-Sektion (`report-mail-content`, `report-email-format-full/
  -compact`, Inhalts-Checkboxen) bediene / Then verhalten sie sich exakt wie vor
  dem Refactor, inklusive Kanal-Gating-Leerzustand (`briefings-channel-empty`
  bei leerem `weatherChannels`) — diese Blöcke wurden nicht angefasst.
  - Test: Bestehende Playwright-Suite für Kanäle + Mail-Inhalt läuft unverändert
    grün gegen den refactorierten Assistenten.

- **AC-9:** Given kein einziger Briefing-Kanal (`send_email`/`send_telegram`/
  `send_sms`) ist im Anlege-Assistenten aktiv, aber `weatherChannels` erlaubt
  mindestens einen Kanal (Kanal-Gating greift NICHT) / When ich den Zeitplan-Tab
  ansehe / Then erscheint GENAU EINE „Kein Kanal aktiv"-Warnbox (aus
  `VTSchedulePlan`, da `hasActiveChannel=false`) — nicht doppelt mit dem
  Kanal-Gating-Leerzustand der Kanäle-Sektion, falls beide Testid
  `briefings-channel-empty` verwenden würden.
  - Test: Playwright deaktiviert alle drei Kanal-Checkboxen bei aktivem
    `weatherChannels`, zählt sichtbare Elemente mit Testid
    `briefings-channel-empty` — erwartet genau 1 (nicht 0, nicht 2).

- **AC-10:** Given die Implementierung ist fertig / When man
  `EditReportConfigSection.svelte` durchsieht / Then enthält die Datei kein
  eigenes Zeitplan-Card-Markup mehr (kein `Card.Root` mit Morgen-/Abend-Uhrzeit-
  Input) — nur noch den `<VTSchedulePlan context="route" .../>`-Aufruf. Künftige
  Zeitplan-Änderungen (z. B. ein neues Stunden-Raster analog #1280) sind dadurch
  nur noch an einer Stelle nötig.
  - Test: Code-Review/Diff-Nachweis (kein automatisierter Playwright-Test nötig)
    — kein `data-testid="report-morning-time"` außerhalb von
    `VTSchedulePlan.svelte` im gesamten `frontend/src`-Baum (Grep-Check).

- **AC-11:** Given die Umstellung ist live / When Fresh-Eyes-Inspector und PO
  Screenshots des Anlege-Assistenten-Zeitplan-Tabs vor und nach dem Refactor
  vergleichen / Then ist die neue Optik (atoms-`Card`-Styling, separate
  „Mehrtages-Trend"-Karte statt Trend inline je Report-Karte) bewusst und
  gewünscht — identisch zum Trip-Detail-Versand-Tab. Dies ist KEINE Regression,
  sondern die spezifizierte sichtbare Änderung dieses Refactors.
  - Test: Fresh-Eyes-Inspector-Screenshot-Vergleich + PO-Freigabe der
    Bildschirmaufnahme (kein automatisierter Pixel-Diff nötig, da bewusste
    Design-Angleichung).

## Known Limitations

- **KL-1 · Leerzustand-Kollisionsrisiko:** `EditReportConfigSection` hat bereits
  einen Kanal-Gating-Leerzustand mit Testid `briefings-channel-empty`
  (`weatherChannels`-basiert, Z. 353–362). `VTSchedulePlan` bringt einen zweiten,
  unabhängig bedingten Leerzustand mit **demselben Testid**
  (`hasActiveChannel`-basiert). Beide Bedingungen können gleichzeitig zutreffen
  (typischerweise wenn beide auf denselben Zustand — kein Kanal aktiv —
  zurückgehen), was zu doppeltem DOM-Element mit identischem Testid führen kann.
  AC-9 macht das Verhalten prüfbar (genau 1 sichtbares Element); die konkrete
  Auflösung (z. B. Testid-Differenzierung in VTSchedulePlan oder bedingtes
  Unterdrücken eines der beiden Blöcke) obliegt der Implementierung.
- **KL-2 · Toter Code bleibt unangetastet:** `BriefingsTab.svelte`,
  `TripEditView.svelte` und die Route `/trips/[id]/edit` sind laut Analyse toter
  Code (nie live gerendert) und werden in diesem Refactor NICHT bereinigt —
  separates Cleanup, ggf. Sammel-Eintrag #1199 oder eigenes Issue.
- **KL-3 · Keine volle VersandTab-Migration des Wizards:** `VersandTab` bündelt
  Laufzeit + Alert-Zustellung, aber keinen Mail-Inhalt. Der Wizard-Tab „Briefing-
  Zeitplan" behält deshalb `EditReportConfigSection` als Wirt-Komponente für
  Kanäle + Mail-Inhalt; nur der Zeitplan-Teilbaum wird ausgetauscht.
- **KL-4 · Sichtbare Design-Änderung ist beabsichtigt:** Siehe AC-11 — keine
  Limitation im engeren Sinne, aber ausdrücklich festgehalten, damit Fresh-Eyes
  die neue Optik nicht fälschlich als Regression meldet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dieser Refactor führt kein neues Architekturmuster ein. Er
  wendet die bereits etablierte und dokumentierte Teilungs-Invariante
  (CLAUDE.md „Trip/Ortsvergleich-Code-Teilung", Anti-Pattern-Referenz #1170) auf
  den letzten verbliebenen Nicht-konformen Pfad an, unter Wiederverwendung des in
  Epic #1230 / Issue #1232 bereits spezifizierten und live ausgerollten
  `VTSchedulePlan`-Musters (`docs/specs/modules/versand_tab_route.md`). Es
  entsteht keine neue Komponente, kein neues Datenmodell, kein neuer
  Context-Wert — lediglich eine zusätzliche Aufrufstelle einer bestehenden,
  bereits context-fähigen Komponente.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Kein Kanal aktiv (Assistent) | VTSchedulePlan zeigt Leerzustand statt Zeitplan-Karten (AC-9), Kollisionsrisiko mit Kanal-Gating-Leerzustand siehe KL-1 |
| Karte deaktiviert | Uhrzeit-Feld UND Quick-Pick-Chip disabled, Wert bleibt erhalten (AC-5) |
| Unbekannte `reportConfig`-Felder (`change_threshold_*`) | Bleiben durch Read-Modify-Write erhalten (AC-6) |
| Ortsvergleich ohne `wiz`-Objekt (Edge-Case aus VersandTab-Bestand) | Fallback-Defaults (`?? '07:00'` etc.) unverändert, nicht Teil dieses Refactors |
| Testids doppelt im DOM (Mobile+Desktop-Duplikat des Wizard-Layouts) | Playwright nutzt `:visible` (bestehende Konvention) |

## Out of Scope

- Bereinigung des toten Codes `BriefingsTab.svelte`/`TripEditView.svelte`/Route
  `/trips/[id]/edit` (KL-2).
- Volle Migration des Wizard-Tabs auf `VersandTab` (Kanäle/Mail-Inhalt bleiben
  in `EditReportConfigSection`).
- Backend-, Go-API- oder Datenmodell-Änderungen jeder Art.
- Änderungen an `WeatherMetricsTab.svelte` (`showSchedule={false}`, nicht
  betroffen).

## Changelog

- 2026-07-17: Initial spec created
