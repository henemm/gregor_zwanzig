---
entity_id: issue_584_trip_wizard_design_fidelity
type: module
created: 2026-06-04
updated: 2026-06-04
status: implemented
version: 1.0.0
---

# Spec: Trip-Wizard Design-Fidelity 1:1 nach screen-trip-wizard.jsx

**Issue:** #584  
**Typ:** Rework / Design-Compliance  
**Quelle:** `claude-code-handoff/current/jsx/screen-trip-wizard.jsx`  
**SOLL-Screenshots:** `claude-code-handoff/current/soll/I-wizard-step1..5-*.png`

---

## Kontext

Der Trip-Wizard (TripWizardShell + Steps 1–5 + Stepper) weicht visuell vom JSX-Design-Template ab.
Issue #578 (Molecules + Organisms) und alle Schwester-Issues #579–#583 sind abgeschlossen.
#584 bringt den letzten Screen auf Stand.

**Implementierungsregel:** Inline-Styles aus JSX 1:1 übernehmen. Nur `var(--g-*)` Tokens.
KEINE eigenen Design-Entscheidungen. KEINE Abweichungen vom JSX.

---

## Acceptance Criteria

**AC-1:** Given die Shell-Komponente, When sie gerendert wird, Then ist der Content-Container `max-width: 1180px`, `padding: 32px 80px 60px`, `margin: 0 auto` und die `TopoBg`-Opacity ist `0.16` (statt 0.4).

**AC-2:** Given der Stepper auf Desktop, When ein Schritt als `done` angezeigt wird, Then zeigt der Dot `background: var(--g-paper)`, `border: 1.5px solid var(--g-ink-3)` und den Text „✓" (kein CheckIcon); When er `active` ist: `border: 2px solid var(--g-accent)`, Zahl in `font-family: var(--g-font-mono)`; When `upcoming`: `border: 1.5px solid var(--g-rule)`, `color: var(--g-ink-4)`. Die Verbindungslinien zwischen den Dots sind `flex: 1, height: 1px` (volle Breite, kein festes `w-6`).

**AC-3:** Given Step 1 ohne GPX, When die Drop-Zone gerendert wird, Then hat sie `border: 1.5px dashed var(--g-accent)`, `background: var(--g-accent-tint)`, `padding: 44px 24px`, `text-align: center`. Das Upload-Icon ist das WizUploadGlyph-SVG (Pfeil nach oben + Tray, stroke `var(--g-accent-deep)`, 36×36).

**AC-4:** Given Step 1 mit geladenem GPX (gpxLoaded=true), When der GPX-Bereich angezeigt wird, Then gibt es eine Card (`background: var(--g-card)`, `border: 1px solid var(--g-rule)`, `padding: 18px 22px`) mit GPX-Badge (`background: var(--g-accent-tint)`, `color: var(--g-accent-deep)`, Mono-Font) und einem „Andere Datei wählen"-Button.

**AC-5:** Given Step 3, When die Aktivitätsprofil-Sektion gerendert wird, Then ist das Layout ein 2-Spalten-Grid (`gridTemplateColumns: "260px 1fr"`, `gap: 32`) mit dem Dropdown links und einem Beschreibungstext rechts (`font-size: 13, color: var(--g-ink-2), lineHeight: 1.55`).

**AC-6:** Given Step 3 Metrik-Gruppen-Header, When sie gerendert werden, Then haben sie `background: var(--g-card-alt)`, `borderBottom: 1px solid var(--g-rule-soft)`, `position: sticky, top: 0`. Die Metrik-Rows zeigen `background: var(--g-card)` wenn enabled, `opacity: 0.55` wenn disabled.

**AC-7:** Given Step 4, When die Channel-Tabs gerendert werden, Then ist der Container ein `grid` mit `gridTemplateColumns: repeat(4, 1fr)`, `border: 1px solid var(--g-rule)`, `borderRadius: var(--g-r-2)`, kein gap. Aktiver Tab hat `background: var(--g-card)`, `borderBottom: 2px solid var(--g-accent)`.

**AC-8:** Given Step 4, When das Body-Layout gerendert wird, Then ist es ein 2-Spalten-Grid (`gridTemplateColumns: "1fr 380px"`, `gap: 28`). Die rechte Vorschau-Spalte ist `position: sticky, top: 24`.

**AC-9:** Given Step 5, When die drei Report-Cards gerendert werden, Then ist jede Card ein `<Card padding={18}>` mit `minHeight: 280, display: flex, flexDirection: column`. Die Abend-Card zeigt den Titel „Vor dem Schlafen", Sub-Text „Plan & Vorhersage für morgen." Die Morgen-Card: „Vor Etappenstart" / „Aktuelle Bedingungen für heute." Die Warnungs-Card: „Sofort, wenn nötig" / „Alert, sobald eine Alarmregel überschritten wird."

**AC-10:** Given Step 5 Abend/Morgen-Card mit aktivem Report, When die Uhrzeit angezeigt wird, Then ist sie als große Mono-Zahl dargestellt: `fontSize: 22, fontWeight: 600, fontFamily: mono`, daneben „24h" in klein (`fontSize: 11, color: var(--g-ink-4)`), plus ein „Ändern"-Ghost-Button.

**AC-11:** Given Step 5 Trend-Toggle in der Abend-Card, When er gerendert wird, Then ist er in einem eigenen Block mit `background: var(--g-card-alt)`, `border: 1px solid var(--g-rule-soft)`, `borderRadius: var(--g-r-2)`, `padding: 10px 12px`, Switch-Atom links + Labeltext rechts.

**AC-12:** Given Step 5 Kanal-Chips pro Card, When sie gerendert werden, Then sind es `<span>`-Chips (kein Checkbox-Label) mit: aktiver Chip = `border: 1px solid var(--g-accent)`, `background: var(--g-accent-tint)`, `color: var(--g-accent-deep)`; inaktiver Chip = `border: 1px solid var(--g-rule)`, `color: var(--g-ink-4)`. Feste Kanalreihenfolge: Email, Signal, Telegram, SMS.

**AC-13:** Given der Wizard-Footer, When er gerendert wird, Then ist er ein `grid` mit `gridTemplateColumns: "1fr auto 1fr"`, `gap: 12`, `paddingTop: 20`, `borderTop: 1px solid var(--g-rule)`, `marginTop: 36`. Zurück-Button (linke Spalte): `variant="ghost"`, Label „← Zurück". Extra-Slot (mittlere Spalte): in Step 2 ein „+ Pausentag einfügen"-Ghost-Button. Speichern-Label: „Tour speichern" (statt „Trip speichern").

**AC-14:** Given alle bestehenden Tests (node:test), When `uv run pytest` und Frontend-Tests laufen, Then sind alle grün (keine Regression).

---

## Abhängigkeiten

- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
- `frontend/src/lib/components/trip-wizard/Stepper.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte`
- `claude-code-handoff/current/jsx/screen-trip-wizard.jsx` (Quell-Wahrheit)
- `claude-code-handoff/current/jsx/tokens.css` (Token-Referenz)

## Nicht in Scope

- Step 2 Etappen: StageRow-Spalten-Struktur — die DnD-Logik bleibt unverändert; nur die Template-Picker-Spaltenbreite (320px) wird angeglichen
- Keine funktionalen Änderungen (State, API-Calls, Wizard-Logic)
- Keine neuen Tests — bestehende Tests müssen weiterhin grün sein
