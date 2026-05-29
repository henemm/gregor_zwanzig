# Context: Issue #443 — Orts-Vergleich Wizard Step 5 (Versand + Aktivierung)

## Request Summary

Wizard-Step 5 für den Orts-Vergleich-Wizard implementieren: Versandzeit, Zeitfenster, Horizont und Kanal-Liste konfigurierbar machen, plus Aktivierungs-Banner (nur Create-Modus) und Blocking-Validation wenn alle Kanäle deaktiviert sind.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | **NEU** — Haupt-Komponente (noch nicht vorhanden) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | State-Klasse erweitern: Versand-Felder reaktiv statt hardcoded |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Step-5-Placeholder durch `<Step5Versand />` ersetzen |
| `frontend/src/routes/compare/new/+page.server.ts` | Profil-Laden hinzufügen (analog trips/new) |
| `frontend/src/routes/compare/[id]/edit/+page.server.ts` | Profil-Laden hinzufügen + Sub-Felder ins State |
| `frontend/src/routes/compare/new/+page.svelte` | `setContext('compare-wizard-profile', data.profile)` |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | `setContext('compare-wizard-profile', data.profile)` + State-Prefill |
| `frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte` | Referenz/Wiederverwendung für Kanal-Toggles |
| `frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte` | Referenz-Muster für Kanal-Zeilen + maskPhone-Nutzung |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | `maskPhone()` — wiederverwendbar |
| `internal/handler/auth.go` | `GetProfileHandler` → `/api/auth/profile` liefert mail_to, signal_phone, telegram_chat_id |
| `internal/model/subscription.go` | Backend-Felder: forecast_hours (24/48/72), time_window_start/end, schedule, send_email/signal/telegram |

## Bestehende Patterns

### Profil-Pipeline (Trip-Wizard Referenz)
1. `+page.server.ts` lädt `/api/auth/profile` fail-soft → `data.profile`
2. `+page.svelte` setzt `setContext('compare-wizard-profile', data.profile)`
3. Step-Komponente liest `getContext('compare-wizard-profile')` (null-tolerant)
4. `maskPhone()` aus `wizardHelpers.ts` für Signal-Telefonnummer

### ChannelToggle-Pattern (Step4Briefings / Step5Reports)
- `ChannelToggle.svelte` in `trip-wizard/steps/` — Label, checked, onchange, disabled?, hint?, testid
- Factory-Handler-Muster für Safari-Reaktivität

### WizardState Save-Pattern
- `save()` baut Payload hardcoded — muss auf reaktive State-Felder umgestellt werden
- `toggleEnabled()` ebenfalls hardcoded — gleiche Umstellung
- Beide Methoden: `send_email`, `send_signal`, `send_telegram`, `forecast_hours`, `time_window_start`, `time_window_end`, `schedule` bisher hart als Defaults

### Aktivierungs-Banner
- `var(--g-good)` = `#3d6b3a` (per Issue-Beschreibung)
- Nur Create-Modus (`state.isEditMode === false`)
- CTA-Text im Footer: `Briefing aktivieren →`

## State-Erweiterung

Neue reaktive Felder in `CompareWizardState`:
```typescript
sendEmail = $state(true);
sendSignal = $state(false);
sendTelegram = $state(false);
timeWindowStart = $state(9);   // Stunden, 0–23
timeWindowEnd = $state(16);    // Stunden, 0–23
forecastHours = $state<24 | 48 | 72>(48);  // Horizont
// Versandzeit: aktuell keine eigene Uhrzeit im Backend-Modell (nur schedule-Enum)
// → Mapping: schedule + send_time (HH:MM) wird in display_config gespeichert
// ODER: forecast_hours allein + schedule bleibt daily_morning als Default
// → KLÄRUNG nötig in Spec-Phase
```

## Offene Designfrage (→ Spec-Phase klären)

**Versandzeit-Uhrzeit-Picker:** Das Backend-Modell kennt nur `schedule: 'daily_morning' | 'daily_evening' | 'weekly'` mit festen Zeiten (07:00 / 18:00 per `scheduleLabel()`). Ein freier Uhrzeit-Picker wäre ein neues Backend-Feature.

**Optionen:**
1. Picker mapped nur auf Enum: <12:00 → daily_morning, ≥12:00 → daily_evening (einfach, kein Backend-Change)
2. Exakte Zeit in `display_config.send_time` speichern (Frontend nutzt sie, Scheduler ignoriert sie zunächst)
3. Neues Backend-Feld `send_time_hhmm` (Backend-Change außerhalb dieses Issues)

Empfehlung: Option 1 (Mapping auf Enum) ist am einfachsten und ohne Backend-Change.

## Dependencies

- **Upstream:** `/api/auth/profile` (profile.mail_to, profile.signal_phone, profile.telegram_chat_id)
- **Upstream:** CompareWizardState (save/toggleEnabled Payload)
- **Downstream:** CompareWizard.svelte (rendert Step 5)
- **Downstream:** /compare (Redirect nach Aktivierung)
- **Downstream:** Backend-Validation: forecast_hours ∈ {24, 48, 72} (interner/handler/subscription.go:64)

## Existing Specs

- `docs/specs/modules/issue_439_compare_uebersicht.md` — Übersichtsseite (implementiert, Referenz für Subscription-Flow)
- Kein Spec für Issue #443 bisher vorhanden

## Risiken & Überlegungen

1. **Versandzeit-Semantik:** Kein freier Uhrzeit-Picker im Backend → Spec muss klären ob Enum-Mapping reicht
2. **State-Refactoring:** `save()` und `toggleEnabled()` haben hardcoded Versand-Werte → müssen auf State-Felder umgestellt werden (Vorsicht: Read-Modify-Write für `existingDisplayConfig`)
3. **Edit-Modus Prefill:** Beide Edit-Seiten müssen neue Felder aus `data.subscription` in State laden
4. **Activated-State:** `activated` ist kein Backend-Feld — ergibt sich aus `save()` + Redirect, nicht aus einer separaten Mutation
5. **Profil-Pipeline:** Beide +page.server.ts müssen Profil laden (aktuell fehlt das im Compare-Wizard)
