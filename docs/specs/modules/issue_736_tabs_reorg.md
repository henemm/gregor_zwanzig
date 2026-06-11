---
entity_id: issue_736_tabs_reorg
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [frontend, ui-cleanup, tab-reorg, weather-metrics, briefing-schedule, channels]
---

<!-- Issue #736 — Reiter-Reorganisation "Inhalt" vs. "Versand" -->

# Issue 736 — Reiter-Reorganisation "Inhalt" vs. "Versand"

## Approval

- [ ] Approved

## Purpose

Die zwei Reiter "Wetter-Metriken" und "Briefing-Zeitplan" im Trip-Editor haben keine klare Zuständigkeitstrennung: Kanal-Konfiguration liegt auf beiden Reitern gleichzeitig (als Master-Toggle in Reiter 1 und als Versand-Checkboxen in Reiter 2), und der E-Mail-Inhalt-Bereich steckt im Zeitplan-Reiter statt beim übrigen Inhalt. Dieses Spec reorganisiert die beiden Reiter zu "Inhalt" (alles was den Report-Inhalt steuert) und "Versand" (alles was bestimmt wann und wohin gesendet wird), sodass jeder Reiter eine kohärente, selbsterklärende Zuständigkeit hat und die doppelte Kanal-Konfiguration zu einem einzigen Abschnitt zusammengeführt wird.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripTabs.svelte` — Tab-Labels ändern (`'Wetter-Metriken'` → `'Inhalt'`, `'Briefing-Zeitplan'` → `'Versand'`; value-Schlüssel `weather`/`briefings` bleiben unverändert)
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — Abschnitt 04 "Kanäle" (`display_config.channels`-Toggle) entfernen; E-Mail-Inhalt-Karte hierher übernehmen
- **File:** `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` — E-Mail-Inhalt-Karte entfernen; `weatherChannels`-Prop entfällt (Kanal-Merge im Versand-Reiter reicht)
- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` — Kanal-Abschnitt zu einem zusammengeführten Abschnitt umbauen, der `display_config.channels` UND `report_config.send_*` gleichzeitig setzt; Abschnitt "SMS-Schwellwerte" → "Schwellwerte" umbenennen mit Hinweis "Gelten für E-Mail, Telegram und SMS"
- **Identifier:** `WeatherMetricsTab`, `BriefingScheduleTab`, `EditReportConfigSection` (Svelte-Komponenten)

## Estimated Scope

- **LoC:** ~80 (−120 verschieben/entfernen, +40 merged Kanal-Abschnitt + Label-Anpassungen)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripTabs.svelte` — `TABS`-Array | Svelte-Konstante | Definiert Tab-Labels und value-Schlüssel; nur Labels ändern, value-Schlüssel sind URL-kanonisch und dürfen nicht geändert werden |
| `WeatherMetricsTab.svelte` — `channels`-State | Lokaler $state | Hält `display_config.channels` (Master-Toggle); wird aus Reiter 1 entfernt und durch Props an `EditReportConfigSection` ersetzt |
| `BriefingScheduleTab.svelte` — `weatherChannels` | Props-Ableitung | Leitet aktuell `display_config.channels` in `EditReportConfigSection` durch; entfällt nach Merge |
| `EditReportConfigSection.svelte` — `send_email`/`send_telegram`/`send_sms` | Lokaler $state | Hält `report_config.send_*`; wird im zusammengeführten Kanal-Abschnitt erweitert um `display_config.channels`-Sync |
| `EditReportConfigSection.svelte` — `syncSendFlags` | Helper-Import | Synchronisiert `report_config.send_*` mit `display_config.channels`; nach Merge: Kanal-Toggle setzt beide Felder direkt |
| `briefingChannelGating.ts` — `visibleChannels`, `activeChannelLabels`, `hasNoActiveChannel` | Helper-Funktionen | Steuern den Warnzustand "Kein Kanal aktiv"; bleiben erhalten, Aufrufer ändert sich |
| `display_config.channels` (Go/Python Persistenz) | Datenfeld | Master-Toggle für Kanal-Aktivierung pro Trip; wird aus `WeatherMetricsTab` entfernt, aber weiterhin über `EditReportConfigSection` geschrieben |
| `report_config.send_email`/`send_telegram`/`send_sms` | Datenfelder | Feingranulare Versand-Flags in `ReportConfig`; bleiben erhalten, werden im zusammengeführten Toggle synchron gesetzt |
| GET/PUT `/api/trips/{id}` (Go-API) | Endpunkt | Liest und schreibt `display_config` pro Trip; kein Backend-Eingriff nötig |
| GET/PUT `/api/auth/profile` (Go-API) | Endpunkt | Liest und schreibt `report_config` pro Nutzer; kein Backend-Eingriff nötig |
| Playwright (`frontend/e2e/`) | Testtool | E2E-Tests gegen Staging als eingeloggter Nutzer |

## Implementation Details

### Schritt 1: TripTabs.svelte — Tab-Labels umbenennen

```typescript
// frontend/src/lib/components/trip-detail/TripTabs.svelte
// VORHER:
{ value: 'weather',   label: 'Wetter-Metriken' },
{ value: 'briefings', label: 'Briefing-Zeitplan' },
// NACHHER:
{ value: 'weather',   label: 'Inhalt' },
{ value: 'briefings', label: 'Versand' },
```

Die value-Schlüssel `weather` und `briefings` sind URL-kanonisch (`?tab=weather`, `?tab=briefings`) und bleiben unverändert. Der Kommentar zu Issue #529 wird aktualisiert.

### Schritt 2: WeatherMetricsTab.svelte — Kanal-Abschnitt entfernen, E-Mail-Inhalt hinzufügen

Entfernen:
- Den lokalen `channels`-State (`$state` Zeile ~65) und alle Ableitungen (`availableChannels`, Kanal-bezogene Snapshot-Einträge)
- Die `onChannelsChange`-Prop und das Create-Modus-Kanal-Propagations-Pattern (Issue #622)
- Den Kanal-Abschnitt im HTML (WeatherChannels-Komponente oder äquivalenter Block, Abschnitt 04)
- Die `channels`-Aufnahme in den Snapshot und den Write-Back-Payload

Hinzufügen:
- `import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';`
- Die `EditReportConfigSection`-Karte am Ende der linken Spalte, `mode="edit"`, ohne `weatherChannels`-Prop (Kanal-Gating entfällt im "Inhalt"-Reiter)
- Wenn `WeatherMetricsTab` eine `reportConfig`-Prop noch nicht hat: ergänzen analog zur bestehenden `BriefingScheduleTab`-Nutzung

### Schritt 3: BriefingScheduleTab.svelte — E-Mail-Inhalt entfernen

```svelte
<!-- VORHER -->
<script>
  import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
  ...
  const weatherChannels = ...
</script>
<EditReportConfigSection bind:reportConfig mode="edit" {weatherChannels} />

<!-- NACHHER: EditReportConfigSection nur noch ohne E-Mail-Inhalt-Anteil -->
<!-- Kanal-Abschnitt bleibt, E-Mail-Inhalt-Card wird konditionell ausgeblendet oder Props steuern -->
```

Konkret: `EditReportConfigSection` erhält eine neue Prop `showMailContent: boolean = true`. Im `BriefingScheduleTab` wird sie mit `showMailContent={false}` übergeben; im `WeatherMetricsTab` mit `showMailContent={true}` (Default). Damit ist kein Duplizieren von Markup nötig.

### Schritt 4: EditReportConfigSection.svelte — Merged Kanal-Abschnitt + neue Prop

**Neue Prop `showMailContent`:**
```typescript
interface Props {
    reportConfig?: ReportConfig;
    mode?: 'create' | 'edit';
    weatherChannels?: ChannelConfig;
    showMailContent?: boolean;  // NEU — steuert ob E-Mail-Inhalt-Card gerendert wird
}
let { reportConfig = $bindable(), mode = 'create', weatherChannels, showMailContent = true }: Props = $props();
```

**Merged Kanal-Abschnitt:**
Der bestehende Kanal-Abschnitt (Checkboxen `send_email`/`send_telegram`/`send_sms`) wird erweitert: jedes Toggle-Event setzt sowohl `report_config.send_*` als auch `display_config.channels` über den `onTripUpdate`-Callback (der via `BriefingScheduleTab` nach oben propagiert). Der `syncSendFlags`-Aufruf entfällt, weil die Werte jetzt direkt gesetzt werden.

Da `display_config.channels` am Trip hängt (nicht am Profil), muss `BriefingScheduleTab` den Trip als bindable Prop durchreichen und die `onTripUpdate`-Callback-Kette nutzen — analog zu `WeatherMetricsTab`.

**Abschnitt "SMS-Schwellwerte" umbenennen:**
```svelte
<!-- VORHER -->
<h3 class="text-sm font-semibold">SMS-Schwellwerte</h3>
<!-- NACHHER -->
<h3 class="text-sm font-semibold">Schwellwerte</h3>
<p class="text-xs text-muted-foreground">Gelten für E-Mail, Telegram und SMS</p>
```

**E-Mail-Inhalt-Card konditionell:**
```svelte
{#if showMailContent}
<Card.Root ...>
  <!-- E-Mail-Inhalt (Format + Bausteine) wie bisher -->
</Card.Root>
{/if}
```

### Schritt 5: Backward Compatibility — Keine Datenverluste

Da `display_config.channels` und `report_config.send_*` bisher unabhängig gepflegt wurden, muss der zusammengeführte Toggle beim ersten Öffnen des Versand-Reiters beide Felder auf den jeweils gespeicherten Wert initialisieren und beim Speichern beide gleichzeitig schreiben. Konkret:

```typescript
// Initialisierung (merged):
send_email = weatherChannels?.email ?? trip.display_config?.channels?.email ?? true;
// → report_config.send_email UND display_config.channels.email auf denselben Wert
```

Beim Write-Back: `onTripUpdate` mit `display_config.channels` + `reportConfig`-bindable mit `send_*` gleichzeitig aktualisieren.

## Expected Behavior

- **Input:** Trip mit beliebigem bestehenden `display_config.channels` und `report_config.send_*` (inkl. alter Trips wo nur eines der beiden gesetzt ist)
- **Output:** Tab "Inhalt" zeigt Abschnitte 01–03 (Profil, Metriken, Reihenfolge), Abschnitt "Schwellwerte" und die E-Mail-Inhalt-Karte — kein Kanal-Toggle; Tab "Versand" zeigt Zeitplan-Abschnitte und einen einzigen zusammengeführten Kanal-Abschnitt — keine E-Mail-Inhalt-Karte
- **Side effects:** Toggle im Versand-Reiter schreibt `display_config.channels` UND `report_config.send_*` gleichzeitig; URL-Parameter `?tab=weather`/`?tab=briefings` funktionieren weiterhin (keine Änderung an value-Schlüsseln)

## Acceptance Criteria

- **AC-1:** Given der Trip-Editor ist geöffnet / When der Nutzer den Reiter mit dem Wert `weather` wählt / Then lautet das sichtbare Tab-Label "Inhalt" und der Reiter mit dem Wert `briefings` hat das Label "Versand" — die URL-Parameter `?tab=weather` und `?tab=briefings` aktivieren weiterhin den richtigen Reiter
  - Test: Playwright gegen Staging — `locator('[data-testid="trip-detail-tab-weather"]')` hat Text "Inhalt"; `locator('[data-testid="trip-detail-tab-briefings"]')` hat Text "Versand"; `page.goto('?tab=weather')` aktiviert den Inhalt-Reiter

- **AC-2:** Given der Inhalt-Reiter ("Wetter-Metriken"-Nachfolger) ist aktiv / When die Seite gerendert wird / Then ist kein Kanal-Toggle (`data-testid="channel-email"`, `channel-telegram`, `channel-sms`) im Inhalt-Reiter sichtbar, aber die E-Mail-Inhalt-Karte (`data-testid="report-mail-content"`) ist vorhanden
  - Test: Playwright — Tab `weather` öffnen; `locator('[data-testid="channel-email"]').count()` == 0; `locator('[data-testid="report-mail-content"]')` ist sichtbar

- **AC-3:** Given der Versand-Reiter ("Briefing-Zeitplan"-Nachfolger) ist aktiv / When die Seite gerendert wird / Then sind die Kanal-Checkboxen (`channel-email`, `channel-telegram`, `channel-sms`) genau einmal sichtbar und die E-Mail-Inhalt-Karte (`report-mail-content`) ist nicht im DOM
  - Test: Playwright — Tab `briefings` öffnen; `locator('[data-testid="channel-email"]').count()` == 1; `locator('[data-testid="report-mail-content"]').count()` == 0

- **AC-4:** Given ein Trip hat `display_config.channels.email = false` und `report_config.send_email = false` gespeichert / When der Nutzer im Versand-Reiter die E-Mail-Checkbox aktiviert und speichert / Then liefern sowohl GET `/api/trips/{id}` → `display_config.channels.email` als auch GET `/api/auth/profile` → `report_config.send_email` den Wert `true` — beide Felder werden synchron gesetzt
  - Test: Playwright — E-Mail-Checkbox anklicken, `briefings-save` auslösen, dann beide GET-Endpunkte prüfen via `page.evaluate` oder direkten API-Calls

- **AC-5:** Given der Abschnitt mit Schwellwert-Konfiguration im Inhalt-Reiter / When er gerendert wird / Then lautet die Überschrift "Schwellwerte" (nicht "SMS-Schwellwerte") und ein Hinweistext "Gelten für E-Mail, Telegram und SMS" ist sichtbar
  - Test: Playwright — Tab `weather` öffnen; `locator('text=SMS-Schwellwerte').count()` == 0; `locator('text=Schwellwerte')` sichtbar; `locator('text=Gelten für E-Mail, Telegram und SMS')` sichtbar

- **AC-6:** Given ein bestehender Trip mit gespeicherten `report_config.send_email`, `report_config.send_telegram`, `display_config.channels` / When der Versand-Reiter geöffnet wird ohne zu speichern / Then zeigen die Kanal-Checkboxen den jeweils gespeicherten Zustand — kein Datenverlust durch Initialisierungs-Merge der beiden Felder
  - Test: Playwright — Trip mit bekannten Werten aufrufen, Tab `briefings` öffnen, Checkbox-Zustände via `isChecked()` gegen erwartete Werte prüfen (ohne Save)

## Known Limitations

- Der zusammengeführte Kanal-Toggle schreibt `display_config.channels` und `report_config.send_*` synchron. Bei bestehenden Trips, bei denen die beiden Felder historisch voneinander abweichen (z.B. `channels.email=true` aber `send_email=false`), gewinnt der beim ersten Tab-Öffnen gelesene Wert — der andere Wert wird beim nächsten Save überschrieben. Diese Konvergenz ist gewollt und backward-kompatibel.
- `WeatherMetricsTab` hat bisher eine `onChannelsChange`-Prop für den Create-Modus (Issue #622). Da die Kanal-Konfiguration in den Versand-Reiter wandert, muss der Create-Modus-Wizard (`TripNewEditor`) angepasst werden: er zeigt zunächst keinen Kanal-Toggle im Step "Inhalt". Ob der Create-Flow einen eigenen Kanal-Step benötigt, ist nicht Teil dieses Issues — der bestehende Create-Modus-Pfad wird vorläufig beibehalten und die `onChannelsChange`-Prop wird leer durchgereicht bis ein separates Issue den Create-Flow anpasst.
- Der `briefingChannelGating.ts`-Helper und seine Exporte (`visibleChannels`, `activeChannelLabels`, `hasNoActiveChannel`) bleiben im Codebase erhalten, auch wenn der "Kein Kanal aktiv"-Warnzustand nach dem Merge im Versand-Reiter anders gesteuert wird — sie werden erst in einem separaten Cleanup entfernt, wenn keine Referenzen mehr existieren.

## Changelog

- 2026-06-11: Initial spec erstellt — Issue #736, Reiter-Reorganisation "Inhalt" vs. "Versand"
