---
entity_id: issue_179_alert_konfigurator_modus_toggle
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
issue: 179
tags: [alert-rules, alert-konfigurator, modus-toggle, mode-card, frontend, svelte, issue-179]
---

# Issue #179 — Alert-Konfigurator: Modus-Toggle (Δ / Absolut / Beides)

## Approval

- [ ] Approved

## Purpose

`AlertRuleRow` erlaubt derzeit keine Auswahl von `AlertRule.kind` ('absolute' | 'delta') — der Modus ist im Datenmodell vorhanden, aber in der UI weder sichtbar noch änderbar. Dieses Feature führt eine neue `ModeCard`-Komponente ein, die im Edit-Modus jeder Regel drei Optionen als Radio-Gruppe zeigt: **Absolut** (fester Schwellwert), **Änderung (Δ)** (Veränderung gegenüber Vortag) und **Beides** (beim Speichern werden zwei separate Rules erzeugt — eine absolute und eine delta). Die Erweiterung ist backward-kompatibel: `AlertRuleKind` bleibt unverändert ('absolute' | 'delta'), Bestandsdaten mit gemischten kinds werden korrekt angezeigt.

## Source

- **NEU:** `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte`
  — Einzelne Karte für eine Modus-Option (Absolut / Δ / Beides)
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`
  — Edit-Modus zeigt drei ModeCards als erste Zeile; View-Modus zeigt kind als Badge
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte`
  — `updateRule(index, updated)` → `updateRules(index, updated[])` für "Beides"-Expansion
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts`
  — Neue Tests für ModeCard-Logik und "Beides"-Expansion

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRule` | TS-Interface (`frontend/src/lib/types.ts`) | Datenmodell einer Alarmregel inkl. `kind: AlertRuleKind` |
| `AlertRuleKind` | TS-Type (`frontend/src/lib/types.ts`) | `'absolute' \| 'delta'` — bleibt unverändert; kein neuer 'both'-Wert |
| `AlertMetric` | TS-Type (`frontend/src/lib/types.ts`) | Metriken-Enum; Delta-Metriken (`temperature_change`, `wind_change`, `precipitation_change`) dürfen keine absolute Rule bekommen |
| `AlertRuleRow.svelte` | Svelte-Komponente | Konsumiert `ModeCard`; Signatur `onUpdate` wird zu `onSave(rules: AlertRule[])` |
| `AlertRulesEditor.svelte` | Svelte-Komponente | Ersetzt eine Rule durch 1–2 Rules im Array via `updateRules()` |
| `alertRuleDefaults.ts` | TS-Modul | `newDefaultRule()` — bleibt unverändert (kind='absolute' als sinnvoller Default) |
| `ALERT_METRIC_LABELS` | TS-Konstante (`alertMetricLabels.ts`) | Labels, Units, Vergleichs-Symbole; wird im View-Modus für Badge genutzt |
| `Pill` | Svelte-Komponente (`$lib/components/ui/pill`) | Badge-Anzeige in View-Modus für "Abs" / "Δ" |
| Issue #223 (AlertRulesEditor) | Upstream-Feature | Baut AlertRuleRow und AlertRulesEditor — beide done |
| Issue #224 (Wizard-Umstellung) | Upstream-Feature | Integriert AlertRulesEditor in Wizard Step 4 — done |

## Implementation Details

### 1. `ModeCard.svelte` — NEU, ~40 LoC

Neue Komponente für eine einzelne Modus-Option. Wird als Radio-Karte gerendert.

```typescript
// Props
let {
  mode,       // 'absolute' | 'delta' | 'both'
  selected,   // boolean — ob diese Card aktiv ist
  onSelect    // () => void — Callback bei Klick
}: {
  mode: 'absolute' | 'delta' | 'both';
  selected: boolean;
  onSelect: () => void;
} = $props();
```

Inhalt pro Card (statisch, in der Komponente hinterlegt):

| mode | Eyebrow | Title | Beschreibung | Beispiel |
|------|---------|-------|--------------|---------|
| `absolute` | Absolut | Schwellwert | Alarm wenn Wert Schwelle überschreitet | Wind > 50 km/h |
| `delta` | Änderung | Δ Differenz | Alarm bei starker Veränderung zum Vortag | Temperatur sinkt > 8 °C |
| `both` | Kombiniert | Beides | Erzeugt zwei Regeln: Absolut + Änderung | Wind > 50 km/h oder Δ > 20 km/h |

Layout: Eyebrow (klein, muted) → Title (fett) → Beschreibung (1 Zeile) → Beispiel (italic, muted). Die drei Cards stehen nebeneinander als Radio-Gruppe (`role="radiogroup"`). Aktive Card erhält visuelles Highlight (`border-color: var(--g-primary)`).

### 2. `AlertRuleRow.svelte` — MODIFY, ~+50 LoC

**Neuer interner State:**

```typescript
// Abgeleitet aus rule.kind beim Öffnen des Edit-Modus
let editMode = $state<'absolute' | 'delta' | 'both'>('absolute');

function startEdit() {
  draft = { ...rule };
  editMode = rule.kind; // 'absolute' oder 'delta'; 'both' ist kein gespeicherter Wert
  editing = true;
}
```

**Edit-Modus — ModeCards als erste Zeile:**

```svelte
<!-- Erste Zeile im Edit-Modus: ModeCard-Gruppe -->
<div class="mode-selector" role="radiogroup" aria-label="Alarm-Modus">
  <ModeCard mode="absolute" selected={editMode === 'absolute'} onSelect={() => editMode = 'absolute'} />
  <ModeCard mode="delta"    selected={editMode === 'delta'}    onSelect={() => editMode = 'delta'} />
  <ModeCard mode="both"     selected={editMode === 'both'}     onSelect={() => editMode = 'both'} />
</div>
<!-- Danach: Metric-Select, Threshold, Severity wie bisher -->
```

**Guard für Delta-Metriken bei "Beides":**

Delta-only Metriken (`temperature_change`, `wind_change`, `precipitation_change`) dürfen keine absolute Rule bekommen. Bei `editMode === 'both'` und einer Delta-Metrik: automatisch zu `editMode = 'delta'` zurückfallen und Hinweistext anzeigen ("Diese Metrik misst nur Änderungen — beim Speichern wird nur eine Δ-Regel erzeugt.").

**`saveEdit()` — Signatur-Wechsel `onUpdate` → `onSave`:**

```typescript
// Prop-Typ ändert sich:
// VORHER: onUpdate: (r: AlertRule) => void
// NACHHER: onSave: (rules: AlertRule[]) => void

function saveEdit() {
  const metricInfo = ALERT_METRIC_LABELS[draft.metric];
  const base: AlertRule = {
    ...draft,
    unit: metricInfo?.unit || draft.unit
  };

  if (editMode === 'both') {
    // Delta-Metrik-Guard: nur delta erzeugen wenn Metrik delta-only ist
    const isDeltaOnly = ['temperature_change', 'wind_change', 'precipitation_change'].includes(base.metric);
    if (isDeltaOnly) {
      onSave([{ ...base, kind: 'delta' }]);
    } else {
      onSave([
        { ...base, id: base.id,              kind: 'absolute' },
        { ...base, id: crypto.randomUUID(),  kind: 'delta' }
      ]);
    }
  } else {
    onSave([{ ...base, kind: editMode }]);
  }
  editing = false;
}
```

**View-Modus — kind als Badge:**

```svelte
<!-- In alert-rule-view: Badge nach dem Threshold -->
<Pill tone="default">{rule.kind === 'delta' ? 'Δ' : 'Abs'}</Pill>
```

### 3. `AlertRulesEditor.svelte` — MODIFY, ~+15 LoC

`updateRule(index, updated: AlertRule)` wird zu `updateRules(index, updated: AlertRule[])`:

```typescript
function updateRules(index: number, updated: AlertRule[]) {
  // Ersetzt rules[index] durch 1 oder 2 neue Rules
  rules = [
    ...rules.slice(0, index),
    ...updated,
    ...rules.slice(index + 1)
  ];
}
```

`AlertRuleRow` bekommt `onSave` statt `onUpdate`:

```svelte
<AlertRuleRow
  {rule}
  onSave={(updated) => updateRules(i, updated)}
  onDelete={() => deleteRule(i)}
/>
```

### 4. `alertRuleDefaults.test.ts` — MODIFY, ~+30 LoC

Neue Tests (ergänzend zu bestehenden):

```typescript
test('ModeCard-Logik: "Beides" erzeugt zwei Rules mit verschiedenem kind', () => {
  // Simuliert saveEdit() bei editMode='both' mit einer nicht-delta-only Metrik
  const base = newDefaultRule(); // kind='absolute', metric='wind_gust'
  const result = expandBothMode(base); // Hilfsfunktion aus saveEdit-Logik extrahieren
  assert.equal(result.length, 2);
  assert.equal(result[0].kind, 'absolute');
  assert.equal(result[1].kind, 'delta');
  assert.notEqual(result[0].id, result[1].id);
  assert.equal(result[0].metric, result[1].metric);
  assert.equal(result[0].threshold, result[1].threshold);
});

test('ModeCard-Logik: "Beides" mit Delta-only-Metrik erzeugt nur eine delta-Rule', () => {
  const base = { ...newDefaultRule(), metric: 'temperature_change' as AlertMetric };
  const result = expandBothMode(base);
  assert.equal(result.length, 1);
  assert.equal(result[0].kind, 'delta');
});

test('ModeCard-Logik: "Absolut" erzeugt eine Rule mit kind=absolute', () => { ... });
test('ModeCard-Logik: "Δ" erzeugt eine Rule mit kind=delta', () => { ... });
```

## Expected Behavior

- **Input:** User öffnet Edit-Modus einer `AlertRule` (kind='absolute' oder kind='delta'), wählt einen Modus aus den drei ModeCards, konfiguriert Metric/Threshold/Severity, klickt Speichern.
- **Output:**
  - Modus "Absolut" → eine Rule mit `kind='absolute'`
  - Modus "Δ" → eine Rule mit `kind='delta'`
  - Modus "Beides" → zwei Rules: `kind='absolute'` (original-ID) + `kind='delta'` (neue UUID), gleiche metric/threshold/severity
  - Modus "Beides" mit delta-only Metrik → eine Rule mit `kind='delta'` + Hinweistext
- **Side effects:**
  - `AlertRulesEditor` passt die `rules`-Liste durch `updateRules()` an — eine Regel kann zu zwei werden.
  - View-Modus jeder Regel zeigt Badge "Abs" bzw. "Δ" — Modus bleibt nach dem Speichern sichtbar.
  - Bestehende Trips mit `kind='delta'` (Legacy-Migration aus `report_config.change_threshold_*`) zeigen korrekt den "Δ"-Badge.
  - `AlertRuleKind = 'absolute' | 'delta'` im Backend (Go + Python) bleibt unverändert — kein Schema-Rework.

## Acceptance Criteria

- **AC-1:** Given AlertRuleRow befindet sich im Edit-Modus / When der User ihn öffnet / Then werden drei ModeCards angezeigt ("Absolut", "Änderung (Δ)", "Beides"), jede mit Eyebrow, Title, Beschreibung und Beispiel-Text.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Rule hat `kind='absolute'` / When der User den Edit-Modus öffnet / Then ist die ModeCard "Absolut" vorausgewählt (selected=true); die anderen Cards sind nicht ausgewählt.
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine Rule hat `kind='delta'` (z. B. Legacy-Migration) / When der User den Edit-Modus öffnet / Then ist die ModeCard "Änderung (Δ)" vorausgewählt.
  - Test: (populated after /tdd-red)

- **AC-4:** Given User wählt Modus "Absolut" oder "Δ" und klickt Speichern / When `saveEdit()` ausgeführt wird / Then ruft `onSave` mit einem Array aus genau einer Rule auf, deren `kind` dem gewählten Modus entspricht.
  - Test: (populated after /tdd-red)

- **AC-5:** Given User wählt Modus "Beides" mit einer nicht-delta-only Metrik (z. B. `wind_gust`) und klickt Speichern / When `saveEdit()` ausgeführt wird / Then ruft `onSave` mit einem Array aus zwei Rules auf: erste hat `kind='absolute'` (original-ID), zweite hat `kind='delta'` (neue UUID); metric, threshold und severity sind identisch.
  - Test: (populated after /tdd-red)

- **AC-6:** Given User wählt Modus "Beides" mit einer Delta-only-Metrik (`temperature_change`, `wind_change` oder `precipitation_change`) / When `saveEdit()` ausgeführt wird / Then ruft `onSave` mit einem Array aus genau einer Rule auf (`kind='delta'`), und ein Hinweistext ist sichtbar ("Modus auf Δ zurückgesetzt").
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine Rule ist im View-Modus / When die Rule hat `kind='absolute'` / Then wird ein Badge "Abs" angezeigt; bei `kind='delta'` wird "Δ" angezeigt.
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Trip hat Bestandsregeln mit `kind='delta'` (Legacy-Migration aus `report_config.change_threshold_*`) / When der AlertRulesEditor diese Regeln anzeigt / Then wird der "Δ"-Badge korrekt gerendert und der Edit-Modus wählt "Δ" vor.
  - Test: (populated after /tdd-red)

## Out of Scope

- **Globaler Modus-Toggle** (alle neuen Regeln erhalten denselben Modus) — der Modus ist pro Regel wählbar; `newDefaultRule()` bleibt unverändert (kind='absolute').
- **Neuer `AlertRuleKind`-Wert 'both'** — "Beides" ist nur eine UI-Geste; im Datenmodell und Backend existiert ausschließlich 'absolute' | 'delta'.
- **Backend-Änderungen** (Go, Python) — `AlertRule.kind` ist überall bereits vorhanden; keine Schema-Änderung nötig.
- **Delta-Metrik-Validierung im Backend** — Guard ist rein im Frontend (`saveEdit()`); Backend akzeptiert alle kinds für alle Metriken.
- **Downstream-Features** (Issue #180 Schwellwert-Tabelle, #181 Cooldown, #182 Alert-Preview) — bauen auf diesem Issue auf, sind aber separater Scope.

## Risiken & Implementierungshinweise

| Risiko | Auswirkung | Gegenmaßnahme |
|--------|------------|---------------|
| `onUpdate` → `onSave`-Signatur-Wechsel | Alle Konsumenten von `AlertRuleRow` (AlertRulesEditor) brechen beim Compile | Synchron in einem Commit ändern: AlertRuleRow + AlertRulesEditor gemeinsam anpassen |
| "Beides" mit Delta-only-Metrik | Absolute Rule für `temperature_change` ergibt semantisch keinen Sinn | Guard in `saveEdit()` + sichtbarer Hinweistext im Edit-Modus |
| Legacy-Trips mit `kind='delta'` | Regeln werden falsch angezeigt oder Edit-Modus wählt falschen Modus vor | `startEdit()` mappt `rule.kind` direkt auf `editMode`; 'both' ist kein gespeicherter Wert |
| Array-Expansion in `updateRules()` | Index-basiertes Ersetzen muss bei zwei Ergebnis-Rules korrekt splizen | `slice(0, index)` + `...updated` + `slice(index + 1)` — explizit testen |

## Known Limitations

- Nach dem Speichern mit "Beides" erscheinen zwei separate Zeilen im AlertRulesEditor — die Verbindung zwischen ihnen ist nicht sichtbar. Eine künftige "Gruppierungs"-Anzeige ist Out of Scope.
- `ModeCard` ist ein neues Komponenten-Pattern, das noch nicht im Design-System dokumentiert ist. Die Card-Styles orientieren sich am GCard-Muster, sind aber spezifisch für Radio-Auswahl.

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | Frontend | NEU — Radio-Karte für Modus-Auswahl | ~40 |
| 2 | `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Frontend | MODIFY — ModeCards im Edit-Modus, Badge im View-Modus, `onUpdate→onSave` | ~+50 |
| 3 | `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Frontend | MODIFY — `updateRule→updateRules`, 1-zu-2-Expansion | ~+15 |
| 4 | `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | Frontend/Test | MODIFY — Tests für Expansion-Logik | ~+30 |

**Gesamt:** ~135 LoC netto, 4 Dateien (1 neu, 3 geändert)

## Changelog

- 2026-05-18: Initial spec für Issue #179 (Modus-Toggle Δ / Absolut / Beides). Pro-Regel-Modus (nicht global), "Beides"-Semantik als zwei separate Rules dokumentiert, Delta-Metrik-Guard, `onUpdate→onSave`-Signaturwechsel als Risiko markiert, 8 Acceptance Criteria im AC-N-Format, Out-of-Scope klar abgegrenzt.
