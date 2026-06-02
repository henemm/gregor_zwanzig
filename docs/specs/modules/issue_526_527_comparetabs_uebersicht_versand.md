---
entity_id: issue_526_527_comparetabs_uebersicht_versand
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [frontend, compare, svelte, ui, redesign, grid, card]
---

# Issues #526 + #527 — CompareTabs: Übersicht-Tab 2×2-Grid + Versand-Tab 2-Spalten-Layout

## Approval

- [ ] Approved

## Summary

Issue #526 ersetzt den off-white Monitoring-Streifen und den einfachen Summary-Text im Übersicht-Tab durch ein 2×2-SummaryCard-Grid (Orte / Idealwerte / Layout / Versand) plus eine accent-linke Hinweis-Box für den Vorschau-Aufruf. Issue #527 baut den Versand-Tab von einer `<dl>`-Liste zu einem 2-Spalten-Grid um: links Rhythmus-Card + Kanäle-Card, rechts Aktivierungs-Card mit Pause-/Aktivieren-Button. Beide Änderungen betreffen ausschließlich `CompareTabs.svelte`.

## Scope

- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
- **Identifier:** `CompareTabs` (Svelte-Komponente, Issue #517)
- **LoC:** ~+120 (Netto nach Umbau), ~−40 (entfallende `<dl>`, Strip, Summary-Text)
- **Files:** 1
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Card` | Svelte-Atom (`atoms/Card.svelte`) | Weiße Karten für SummaryCards, Monitoring, Kanäle, Aktivierung; `accent={true}` für Hinweis-Box |
| `Switch` | Svelte-Atom (`atoms/Switch.svelte`) | Kanal-Toggles in Kanäle-Card; immer `disabled={true}` |
| `Dot` | Svelte-Atom | Status-Dot in Monitoring-Card und Aktivierungs-Card; `tone: good/neutral/bad` |
| `Btn` | Svelte-Atom | „Bearbeiten →"-Links, „Pausieren", „Aktivieren", „Test-Briefing jetzt senden" |
| `Eyebrow` | Svelte-Atom | Abschnittsüberschriften innerhalb der Cards |
| `Pill` | Svelte-Atom | Empfänger-Adress-Pills in Kanäle-Card (Email-Zeile) |
| `DetailRow` | Svelte-Molecule (`molecules/DetailRow.svelte`) | Rhythmus-Zeilen (Zeitplan / Zeitfenster / Nächster Versand) |
| `deriveStatusFromPreset` | Helper (`compare/subscriptionHelpers.js`) | Liefert `'active' | 'paused' | 'draft'` |
| `presetScheduleLabel` | Helper (`compare/subscriptionHelpers.js`) | Erzeugt Schedule-Label (z.B. „Täglich 06–18 Uhr") |
| `formatLastSent` | Helper (`compare/subscriptionHelpers.js`) | Erzeugt lesbares Datum für letzten Versand |
| `STATUS_MAP` | Konstante (`compare/subscriptionHelpers.js`) | Label + Dot-Style pro Status |
| `api` | Utility (`$lib/api.js`) | PUT (Pause/Aktivieren) + POST (Test-Briefing senden) |
| `ComparePreset` | Typ (`$lib/types.js`) | Props-Typ; `schedule`, `empfaenger`, `location_ids`, `display_config`, `profil` |
| `Location` | Typ (`$lib/types.js`) | Auflösung von `location_ids` → Namen |

## Acceptance Criteria

**AC-1:** Given eine Compare-Hub-Detailseite, When der Tab „Übersicht" aktiv ist, Then erscheint ein 2×2-Grid mit vier SummaryCards (Orte, Idealwerte, Layout, Versand) — jede mit einem Titel, einem Kennwert und einem „Bearbeiten →"-Button.
- Test: (populated after /tdd-red)

**AC-2:** Given ein SummaryCard mit „Bearbeiten →"-Button, When der User auf den Button klickt, Then wechselt der aktive Tab auf den entsprechenden Edit-Tab (`?tab=orte`, `?tab=idealwerte`, `?tab=layout`, `?tab=versand`) per `handleValueChange()` ohne Seitennavigation.
- Test: (populated after /tdd-red)

**AC-3:** Given die Monitoring-Daten (Status-Dot, Nächster Versand, Zuletzt), When der Übersicht-Tab geladen wird, Then erscheinen die Monitoring-Infos in einer weißen `Card`-Atom (nicht mehr im `.monitoring-strip` mit `background: var(--g-paper)`).
- Test: (populated after /tdd-red)

**AC-4:** Given den Hinweis-Bereich am Ende des Übersicht-Tabs, When der Tab geladen wird, Then erscheint eine `Card` mit `accent={true}` (linke accent-Border) mit dem Text „Gelesen wird das Briefing unterwegs im Postfach. Tab Vorschau dient nur zum Prüfen der Konfiguration." und einem Button „Vorschau prüfen →", der `handleValueChange('vorschau')` aufruft.
- Test: (populated after /tdd-red)

**AC-5:** Given der Versand-Tab, When er geladen wird, Then erscheint ein 2-Spalten-Grid: linke Spalte mit Rhythmus-Card (oben) und Kanäle-Card (unten), rechte Spalte mit Aktivierungs-Card.
- Test: (populated after /tdd-red)

**AC-6:** Given die Kanäle-Sektion in der Kanäle-Card, When der Tab geladen wird, Then wird für jeden der vier Kanäle (Email / Signal / Telegram / SMS) eine Zeile mit Status-Dot + Name + Verbunden-Status-Text + `Switch`-Atom (`disabled={true}`) angezeigt — Email mit Status „verifiziert" wenn `empfaenger.length > 0`, die übrigen mit Status „nicht verbunden" (statisch).
- Test: (populated after /tdd-red)

**AC-7:** Given ein aktives Preset (`status === 'active'`), When der Versand-Tab angezeigt wird, Then zeigt die Aktivierungs-Card: grüner Dot + Label „Aktiv" + Text „Läuft automatisch" + Button „Pausieren", der `api.put('/api/compare/presets/${preset.id}', {...preset, schedule: 'manual'})` aufruft und `localSchedule` auf `'manual'` setzt.
- Test: (populated after /tdd-red)

**AC-8:** Given ein Entwurf-Preset (`status === 'draft'`), When der Versand-Tab angezeigt wird, Then zeigt die Aktivierungs-Card: neutraler Dot + Label „Entwurf" + Text „Noch nicht aktiv" + Button „Aktivieren" (primary), der `api.put` mit `schedule: 'daily'` aufruft.
- Test: (populated after /tdd-red)

**AC-9:** Given ein pausiertes Preset (`status === 'paused'`), When der Versand-Tab angezeigt wird, Then zeigt die Aktivierungs-Card: neutraler Dot + Label „Pausiert" + Button „Aktivieren" (primary), der `api.put` mit `schedule: 'daily'` aufruft.
- Test: (populated after /tdd-red)

**AC-10:** Given der Button „Test-Briefing jetzt senden" unter der Aktivierungs-Card, When der User klickt, Then wird `POST /api/compare/presets/${preset.id}/send` aufgerufen; bei Erfolg erscheint ein Toast/Inline-Erfolgstext, bei Fehler ein Fehlertext.
- Test: (populated after /tdd-red)

## Implementation Notes

### #526 — Übersicht-Tab

**Monitoring-Card (ersetzt `.monitoring-strip`):**

Umbauen des bestehenden `.monitoring-strip`-Div zu einer `<Card>`-Atom (weißer Hintergrund, `padding={16}`). Inhalt bleibt: Status-Dot + Label, Nächster Versand, Zuletzt gesendet, Kanal-Anzahl.

**2×2-SummaryCard-Grid:**

```svelte
<div class="summary-grid">
  <!-- Karte Orte -->
  <Card padding={20}>
    <Eyebrow>Orte</Eyebrow>
    <p class="summary-value">{preset.location_ids.length} Kandidaten</p>
    <p class="summary-sub">{resolvedLocations[0]?.loc?.name ?? '—'}</p>
    <Btn variant="ghost" size="sm" onclick={() => handleValueChange('orte')}>Bearbeiten →</Btn>
  </Card>

  <!-- Karte Idealwerte -->
  <Card padding={20}>
    <Eyebrow>Idealwerte</Eyebrow>
    <p class="summary-value">{preset.profil}</p>
    <p class="summary-sub">{Object.keys(idealRanges ?? {}).length} Metriken konfiguriert</p>
    <Btn variant="ghost" size="sm" onclick={() => handleValueChange('idealwerte')}>Bearbeiten →</Btn>
  </Card>

  <!-- Karte Layout -->
  <Card padding={20}>
    <Eyebrow>Layout</Eyebrow>
    <p class="summary-value">{channels.join(', ')}</p>
    <Btn variant="ghost" size="sm" onclick={() => handleValueChange('layout')}>Bearbeiten →</Btn>
  </Card>

  <!-- Karte Versand -->
  <Card padding={20}>
    <Eyebrow>Versand</Eyebrow>
    <p class="summary-value">{presetScheduleLabel(preset)}</p>
    <Btn variant="ghost" size="sm" onclick={() => handleValueChange('versand')}>Bearbeiten →</Btn>
  </Card>
</div>
```

CSS: `display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;`

**Hinweis-Box:**

```svelte
<Card accent={true} padding={20}>
  <p>Gelesen wird das Briefing unterwegs im Postfach. Tab Vorschau dient nur zum Prüfen der Konfiguration.</p>
  <Btn variant="ghost" size="sm" onclick={() => handleValueChange('vorschau')}>Vorschau prüfen →</Btn>
</Card>
```

Der bestehende `.summary`-Div und das `.monitoring-strip`-Div werden entfernt.

---

### #527 — Versand-Tab

**Script-Block-Ergänzungen:**

```ts
let localSchedule = $state(preset.schedule ?? 'manual');

async function handleToggleActive() {
  const nextSchedule = localSchedule === 'daily' ? 'manual' : 'daily';
  await api.put(`/api/compare/presets/${preset.id}`, { ...preset, schedule: nextSchedule });
  localSchedule = nextSchedule;
}
```

`localSchedule` bestimmt den angezeigten Zustand (statt `status` direkt), damit die UI nach dem PUT-Call sofort reagiert ohne Seiten-Reload.

**2-Spalten-Layout:**

```svelte
<div class="versand-grid">
  <!-- Linke Spalte -->
  <div class="versand-left">
    <!-- Rhythmus & Vorausschau Card -->
    <Card padding={20}>
      <Eyebrow>Rhythmus & Vorausschau</Eyebrow>
      <DetailRow label="Zeitplan" value={presetScheduleLabel(preset)} />
      <DetailRow label="Zeitfenster" value="{preset.hour_from}–{preset.hour_to} Uhr" />
      <DetailRow label="Nächster Versand" value={...} />
    </Card>

    <!-- Kanäle Card -->
    <Card padding={20}>
      <Eyebrow>Kanäle</Eyebrow>
      <!-- 4 Zeilen: Email / Signal / Telegram / SMS -->
      <div class="channel-row">
        <Dot tone={preset.empfaenger.length > 0 ? 'good' : 'neutral'} />
        <span>Email</span>
        <span class="channel-status">{preset.empfaenger.length > 0 ? 'verifiziert' : 'nicht verbunden'}</span>
        <Switch checked={preset.empfaenger.length > 0} disabled={true} />
      </div>
      <!-- Signal / Telegram / SMS: tone='neutral', Status 'nicht verbunden', checked=false, disabled -->
    </Card>
  </div>

  <!-- Rechte Spalte -->
  <div class="versand-right">
    <Card padding={20}>
      <Eyebrow>Aktivierung</Eyebrow>
      <!-- Status-abhängiger Inhalt via localSchedule -->
      {#if localSchedule === 'daily'}
        <Dot tone="good" /> <span>Aktiv</span>
        <p>Läuft automatisch</p>
        <Btn variant="quiet" onclick={handleToggleActive}>Pausieren</Btn>
      {:else if status === 'draft'}
        <Dot tone="neutral" /> <span>Entwurf</span>
        <p>Noch nicht aktiv</p>
        <Btn variant="primary" onclick={handleToggleActive}>Aktivieren</Btn>
      {:else}
        <Dot tone="neutral" /> <span>Pausiert</span>
        <Btn variant="primary" onclick={handleToggleActive}>Aktivieren</Btn>
      {/if}
    </Card>

    <!-- Test-Briefing senden (bestehender handleSend()-Code, verschieben aus Vorschau-Tab) -->
    <Btn variant="quiet" onclick={handleSend}>Test-Briefing jetzt senden</Btn>
  </div>
</div>
```

CSS: `display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; align-items: start;`

**Hinweis zu `handleSend`:** Die bestehende `handleSend()`-Funktion und die zugehörigen States (`sendLoading`, `sendQueued`, `sendError`) bleiben im Script-Block erhalten. Im Versand-Tab wird der Button ebenfalls angebunden. Im Vorschau-Tab verbleibt das Test-Briefing-UI unverändert (Issue #514 — nicht anfassen).

---

### Imports

`Card`, `Switch` zu den bestehenden Atom-Imports in `CompareTabs.svelte` hinzufügen. `DetailRow` aus `$lib/components/molecules/DetailRow.svelte` importieren.

## Expected Behavior

- **Input:** `ComparePreset`-Objekt mit `location_ids`, `profil`, `display_config.ideal_ranges`, `empfaenger`, `schedule`, `hour_from`, `hour_to`, `letzter_versand`; dazu `locations: Location[]`
- **Output:** Übersicht-Tab zeigt weißes Monitoring-Panel + 2×2-Grid + accent-Hinweis-Box; Versand-Tab zeigt 2-Spalten-Grid mit Rhythmus-, Kanäle- und Aktivierungs-Card
- **Side effects:** PUT an `/api/compare/presets/{id}` bei Pause/Aktivieren; POST an `/api/compare/presets/{id}/send` bei Test-Briefing; lokale State-Variable `localSchedule` spiegelt Änderung sofort wider

## Out of Scope

- **Kanal-Persistenz für Signal / Telegram / SMS:** Das Backend-Datenmodell (`ComparePreset`) kennt nur `empfaenger: string[]` für E-Mail. Es gibt kein Feld für Signal-, Telegram- oder SMS-Empfänger. Die Switch-Toggles für diese drei Kanäle sind daher rein visuell (`disabled={true}`) und führen keinen API-Call durch. Backend-Persistenz ist ein separates Issue.
- **Empfänger-Verwaltung in der Kanäle-Card:** Das Hinzufügen und Entfernen von E-Mail-Adressen bleibt im Versand-Tab (Pill-Liste), nicht in der neuen Kanäle-Card. Die Kanäle-Card zeigt nur den Verbunden-Status.
- **Vorschau-Tab:** Kein Umbau; der bestehende `handleSend`-Code im Vorschau-Tab (Issue #514) bleibt unverändert.
- **Mobile Responsive:** Kein explizites Mobile-Breakpoint für die neuen Grids in diesem Issue — bereits bestehende `.tab-panel`-CSS-Regeln gelten weiterhin.

## Known Limitations

- `localSchedule` wird aus `preset.schedule` initialisiert. Wenn `preset.schedule` `undefined` ist, fällt der Fallback auf `'manual'` zurück, was den Zustand als „pausiert" anzeigt — korrekt, da ein Preset ohne definierten Schedule nicht aktiv sein kann.
- Nach dem PUT-Call wird `preset.schedule` nicht rückgeschrieben (kein Reaktiv-Binding auf Prop). Die UI nutzt `localSchedule` als Single Source of Truth für die aktuelle Sitzung. Ein Page-Reload lädt den Server-State neu.

## Changelog

- 2026-06-02: Initial spec created (Issues #526 + #527)
