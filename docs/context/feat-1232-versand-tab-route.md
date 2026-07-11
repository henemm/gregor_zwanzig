# Context: feat-1232-versand-tab-route (Scheibe 1/3 von Issue #1232)

**Issue:** #1232 — Phase 4 Editor-Konsolidierung (Sub-Issue von Epic #1230/#29).
**Scheibe 1:** Geteilter Organism `VersandTab` mit `context="route"` im Trip-Editor.
FE-only, kein neues Datenmodell (C4), bestehende `data-testid` bleiben erhalten (C6).

## Verbindliche Design-Quelle (1:1, kein Nachbau)

- `claude-code-handoff/current/jsx/versand-tab.jsx` (Stand 2026-07-11) — kanonischer JSX-Snapshot.
- Soll-Screenshots: `.github/issue-assets/soll-29b-desktop-versand-route.png`, `soll-29b-mobile.png`.
- Issue-Body: `claude-code-handoff/issue-bodies/body-29b-editor-konsolidierung.md`.

Sektionen route (Reihenfolge fix): 1) Briefing-Kanäle (an/aus, Layout-Subtexte)
→ 2) Briefing-Zeitplan (Karten mit editierbarer Uhrzeit `<input type="time">`,
Kein-Kanal-Warnbox) → 3) Laufzeit (read-only aus Etappen, „Etappen öffnen →")
→ 4) Alert-Zustellung (Kanäle + Cooldown + Stille Stunden + Beispiel-Warnung).

## IST (Trip-Editor, frontend/src)

| Baustein | Datei | Relevanz |
|---|---|---|
| Tab-Gerüst | `lib/components/trip-detail/TripTabs.svelte` (327 LoC) | Tabs overview/stages/weather/briefings/alerts/preview; testids `trip-detail-tab-*`, `trip-detail-panel-*` |
| Briefings-Tab | `lib/components/trip-detail/BriefingScheduleTab.svelte` (123 LoC) | Wrapper um EditReportConfigSection; Auto-Save via `saveController`, PUT `/api/trips/{id}` (`report_config`), keepalive-Fix F002 |
| Formular-Monolith | `lib/components/edit/EditReportConfigSection.svelte` (540 LoC) | Morgen/Abend-Karten (`morning_enabled`, `morning_time`, quickpicks, trend), Kanäle (`send_email/telegram/sms` + Gating `briefingChannelGating.ts` + premium-sms-Hinweis), Mail-Inhalt (`email_format`, `show_*`-Module) |
| Alerts-Tab | `lib/components/alerts-tab/AlertsTab.svelte` (~175 LoC) | Heading, Onboarding, `AlertMetricLevelTable`, `AlertCooldownCard`, `AlertQuietHoursCard`, 2× `ChannelToggle`, `AlertPreviewCard` |

Datenmodell (`lib/types.ts` → `ReportConfig`): `morning_enabled/evening_enabled`,
`morning_time/evening_time`, `send_email/send_telegram/send_sms`,
`multi_day_trend_morning/evening` (+ Legacy `multi_day_trend_reports[]`).
**Es gibt KEINE per-Briefing-Kanalauswahl** (nur globale `send_*`-Flags) und
**keine eigene Trend-Uhrzeit** (Trend hängt am Morgen-/Abend-Briefing).

## Abgeleitete Scope-Entscheidungen (Scheibe 1)

1. **Neuer Organism** `lib/components/shared/VersandTab.svelte`, Prop
   `context: 'route' | 'vergleich'` (Scheibe 1 implementiert nur `route`;
   `vergleich` folgt Scheibe 2). Sub-Bausteine als eigene Dateien unter
   `lib/components/shared/versand-tab/` (VT_-Namensraum analog JSX).
2. **Datenbindung ohne neues Modell:** Karten-Switch = `*_enabled`,
   Uhrzeit = `*_time`; Sektion Kanäle = `send_*`. Die per-Karte-Kanal-Chips des
   JSX-Seeds haben kein Backend-Feld → **entfallen in Scheibe 1** (Known
   Limitation, kein Fake-UI). Trend-Karte: statt eigener Uhrzeit zwei Chips
   „Morgens/Abends" = `multi_day_trend_morning/evening` (Known Limitation).
3. **Alert-Zustellung zieht um:** bestehende Komponenten (`ChannelToggle`,
   `AlertCooldownCard`, `AlertQuietHoursCard`, `AlertPreviewCard`) werden im
   VersandTab **wiederverwendet** (kein Neubau), testids unverändert.
   `AlertsTab` reduziert auf Heading + Onboarding + Level-Tabelle
   (Korridor-Editor-Vorstufe; #29a/#1231 ist noch nicht implementiert).
4. **Mail-Inhalt-Sektion** (`report-mail-content`: email_format + show_*-Module)
   ist NICHT Teil des VersandTab-Designs → bleibt unverändert unterhalb des
   VersandTab im Briefings-Tab (Umzug ggf. Scheibe 3 / LayoutTab).
5. **Auto-Save-Pfad unverändert:** `saveController` + PUT `report_config`
   (bzw. Alert-Felder wie bisher im AlertsTab-Pfad).

## Risiken / Constraints

- FE hat keine Component-Test-Infra (Befund #1223) → Nachweis über
  Playwright-Staging (`/60-validate`) + mark-red-Mechanismus für RED-Phase.
- Playwright: testids doppelt im DOM (Mobile+Desktop) → `:visible` nutzen.
- LoC-Limit 250/Workflow wird durch die 1:1-Übersetzung (JSX 427 Zeilen)
  voraussichtlich überschritten → Override 500 nur mit PO-Erlaubnis.
- E9/C1 betreffen LayoutTab/Vergleich → Scheibe 2/3, hier nicht berührt.
