---
entity_id: issue_617_briefing_channel_chaining
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [frontend, channels, briefing, trip-edit, epic-575]
---

# Spec: Briefing-Zeitplan — Kanal-Verkettung aus Wetter-Metriken (#617)

## Approval

- [ ] Approved

## Purpose

Der im Wetter-Metriken-Tab gesetzte Kanal-Zustand (`display_config.channels`) wird zur **einen
Quelle** dafür, welche Kanäle im Briefing-Zeitplan-Tab überhaupt zur Auswahl stehen. So muss der
Nutzer Kanäle nur einmal pflegen, und es kann kein „Briefing an SMS" konfiguriert werden, obwohl
SMS gar nicht aktiv ist. Die alten Versand-Flags (`report_config.send_*`) werden synchron gehalten,
damit der echte Versand sofort korrekt funktioniert (kein Potemkin-Schalter).

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (Kanäle-Sektion + Sync)
- **File:** `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` (reicht Wetter-Kanäle durch)
- **Identifier:** neue optionale Prop `weatherChannels?: { email, telegram, sms }`

> **Schicht:** Reines **Frontend / SvelteKit**. Keine Go-/Python-Änderung. `report_config` ist
> backendseitig `map[string]interface{}` (additiv) und `display_config.channels` existiert bereits
> aus #587. Der Versand liest `report_config.send_email/telegram/sms` (`trip_report_scheduler.py`),
> deshalb genügt das Synchronisieren der `send_*`-Flags.

## Estimated Scope

- **LoC:** ~120–180 (Produktivcode; Tests zusätzlich)
- **Files:** 2 Komponenten + 1 Test-Datei (ggf. kleiner reiner Helper)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `display_config.channels` (#587) | Datenquelle | aktive Kanäle aus dem Wetter-Metriken-Tab |
| `report_config.send_*` | Sync-Ziel | tatsächlich versandsteuernde Flags |
| `EditReportConfigSection` | Komponente | enthält die Kanäle-UI (an 4 Stellen wiederverwendet) |

## Implementation Details

```
EditReportConfigSection bekommt eine NEUE optionale Prop:
    weatherChannels?: { email: boolean; telegram: boolean; sms: boolean }

Verhalten NUR wenn weatherChannels gesetzt ist (sonst byte-gleiches Altverhalten — Backward-Compat):

1. Sichtbarkeit: In der Kanäle-Sektion erscheinen NUR Kanäle mit weatherChannels[x] === true.
   Kanäle mit weatherChannels[x] === false werden komplett ausgeblendet (kein Checkbox, kein Hint).

2. Hinweis-Banner (≥1 aktiver Kanal): Text sinngemäß
   "Nur Kanäle, die du in Wetter-Metriken aktiviert hast, stehen hier zur Auswahl:"
   + Liste der aktiven Kanäle (Email · Telegram · SMS, je nach Aktivierung).

3. Warnzustand (0 aktive Kanäle): statt der Checkboxen ein Warn-Banner
   "Kein Kanal aktiv. Aktiviere zuerst mindestens einen Kanal im Tab Wetter-Metriken."
   + Link/Button zurück zum Wetter-Metriken-Tab (Navigation nach ?tab=weather).

4. Sync der Versand-Flags (Read-Modify-Write im bestehenden $effect-Writeback):
   - Für jeden Kanal x mit weatherChannels[x] === false  → send_x := false (verwaiste Kanäle aus).
   - Für aktive Kanäle bleibt die Nutzerwahl (send_x) erhalten.
   - Alle übrigen report_config-Felder (Zeiten, Trend, change_threshold_*, E-Mail-Elemente …)
     bleiben unverändert (Spread über originalReportConfig wie bisher).

5. Account-Profil-Gating bleibt: ist ein Kanal Wetter-aktiv, aber im Account nicht konfiguriert
   (kein mail_to/telegram_chat_id/sms_to), bleibt die bestehende Disabled-Checkbox + "im Account
   einrichten"-Hint erhalten.

BriefingScheduleTab.svelte:
    Liest trip.display_config.channels (Cast über unknown wie in WeatherMetricsTab) mit Default
    { email: true, telegram: true, sms: false } und reicht sie als weatherChannels durch.
```

## Expected Behavior

- **Input:** `trip.display_config.channels` (aus #587) + bestehende `report_config`.
- **Output:** Briefing-Zeitplan-UI, die nur Wetter-aktive Kanäle anbietet; gespeicherte
  `report_config.send_*` ohne verwaiste (nicht-Wetter-aktive) Kanäle.
- **Side effects:** Beim Speichern werden `send_*`-Flags für nicht-Wetter-aktive Kanäle auf `false`
  gesetzt; sonst keine.

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer hat im Wetter-Metriken-Tab Email und Telegram aktiv und SMS
aus, When er den Briefing-Zeitplan-Tab öffnet, Then erscheinen in der Kanäle-Sektion nur Email und
Telegram als wählbare Optionen und SMS wird gar nicht angezeigt.
  - Test: Playwright-E2E als eingeloggter Nutzer auf Staging; Trip mit `display_config.channels =
    {email:true,telegram:true,sms:false}`; im Briefing-Tab sind `channel-email`/`channel-telegram`
    sichtbar, `channel-sms` nicht im DOM.

**AC-2:** Given mindestens ein Kanal ist im Wetter-Metriken-Tab aktiv, When der Briefing-Zeitplan
lädt, Then erscheint ein Hinweis-Banner „Nur Kanäle, die du in Wetter-Metriken aktiviert hast,
stehen hier zur Auswahl:" mit der Liste der aktiven Kanäle.
  - Test: Playwright-E2E; Banner (`briefings-channel-hint`) ist sichtbar und enthält die Labels der
    aktiven Kanäle (z.B. „Email", „Telegram").

**AC-3:** Given im Wetter-Metriken-Tab ist kein Kanal aktiv, When der Briefing-Zeitplan lädt, Then
erscheint statt der Kanal-Optionen ein Warnzustand, und ein Link/Button führt zurück zum
Wetter-Metriken-Tab (URL wechselt auf `?tab=weather`).
  - Test: Playwright-E2E; Trip mit `display_config.channels={email:false,telegram:false,sms:false}`;
    Warn-Banner (`briefings-channel-empty`) sichtbar, Klick auf den Link navigiert nach `?tab=weather`.

**AC-4:** Given ein Trip hat `report_config.send_sms=true`, aber SMS ist im Wetter-Metriken-Tab nicht
aktiv, When der Nutzer den Briefing-Zeitplan öffnet und speichert, Then ist nach dem Speichern
`report_config.send_sms=false`, während `morning_time`, `evening_time`, `multi_day_trend_*` und alle
übrigen `report_config`-Felder unverändert bleiben (Read-Modify-Write).
  - Test: Playwright-E2E; vor/nach Speichern via `GET /api/trips/:id` prüfen, dass `send_sms`
    umschlägt und ein zuvor gesetztes Feld (z.B. `evening_time`) identisch bleibt.

**AC-5:** Given Email und Telegram sind im Wetter-Metriken-Tab aktiv, When der Nutzer im
Briefing-Zeitplan Telegram abwählt und Email anlässt und speichert, Then bleibt nach erneutem Laden
`send_email=true` und `send_telegram=false` erhalten (innerhalb der aktiven Kanäle ist die Wahl frei).
  - Test: Playwright-E2E; Toggle, Speichern, Reload, DOM-Checkbox-Zustände prüfen.

**AC-6:** Given `EditReportConfigSection` wird ohne `weatherChannels`-Prop verwendet (Bestands-Pfade
wie TripEditView/BriefingsTab), When die Komponente rendert, Then verhält sie sich unverändert: alle
drei Kanäle erscheinen, das Account-Profil-Gating greift wie bisher, kein Hinweis-/Warn-Banner.
  - Test: node:test (Komponenten-Render ohne Prop) ODER Playwright gegen einen Bestands-Pfad; alle
    drei `channel-*` vorhanden, kein `briefings-channel-hint`/`-empty` im DOM.

**AC-7 (Multi-User):** Given zwei verschiedene Nutzer A und B mit je einem Trip und
unterschiedlichen `display_config.channels`, When jeder seinen Briefing-Zeitplan öffnet, Then sieht
jeder ausschließlich die Kanäle seines eigenen Trips (keine Vermischung).
  - Test: Playwright-E2E mit zwei Staging-Accounts; A sieht nur seine Kanäle, B nur seine.

## Out of Scope

- **Alerts-Tab** (Karten-Modell, Severity-Falle, Kanal pro Alert) → **#638**.
- Pro-Briefing-Typ-Kanäle (Morgen/Abend/Trend je eigener Kanalsatz) — bewusst nicht; eine
  trip-weite Kanal-Menge.
- Wetter-Metriken-Tab-Layout selbst (#587) und Mobile (#618).
- Backend-Versand-Logik (liest bereits `report_config.send_*`; wird nur synchronisiert, nicht geändert).
