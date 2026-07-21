# Spec: Signal app-weit als Kanal entfernen — Frontend (#610, Schritt 1/2)

**Status:** In Arbeit
**Created:** 2026-06-05
**Issue:** #610
**Kontext:** Fundament für das Paket „Trip bearbeiten" (config-change-flow). Eine frühere Runde (#590) entfernte Signal nur teilweise. Kanäle danach app-weit: **Email · Telegram · SMS**. Backend folgt in Schritt 2/2.

## Scope

Entfernen aller **Signal-Kanal**-Vorkommen in der Svelte-Oberfläche — Typen, Kanal-Listen, Vorschauen, Erklärtexte, Wizard-/Compare-Layout-Schritte, Cockpit-Anzeige. **Nicht** angefasst: `AbortSignal`/`signal:`-Aborts. **Nicht** in diesem Schritt: Backend-Datenmodell `send_signal`, Renderer, `channel_layout.py` (Schritt 2/2). **Nicht** in diesem Schritt: Telegram-Budget auf 8 (gehört zu #587).

Betroffene Bereiche (aus Analyse): `ChannelPreviewBlock`, `ChannelPreviewCard`, `ChannelFidelityBubble`, `ChannelLimitMarkers`, `ChannelRow`, `ChannelDot`, `ReportLine`, `BucketSection`, `AboutOutputLayout`, `HubOverview`, `metricsEditor.ts` (`CHANNEL_COL_BUDGET`), `previewHelpers.ts`, `OutputLayoutEditor`, `CompareBriefingPreview`, `CompareChatBubble`, `trip-wizard/steps/Step4Layout`, `Step5Reports`, `compare/steps/Step4Layout`, `routes/+page.svelte`, `_home/cockpitHelpers.ts`.

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet den Trip-Editor-Tab mit der Kanal-Vorschau, When die Seite lädt, Then ist die Vorschau standardmäßig auf einem existierenden Kanal (Telegram oder Email) — niemals auf „Signal" — und es gibt keinen „Signal"-Umschalter.

**AC-2:** Given irgendein Kanal-Auswahl- oder Vorschau-Element im Frontend (Trip-Editor, Trip-Wizard, Orts-Vergleich-Wizard), When es gerendert wird, Then erscheint ausschließlich Email · Telegram · SMS und kein „Signal"-Eintrag, kein „▲ Signal", keine „Signal · max 6"-Erklärung.

**AC-3:** Given ein Report-Config-Datensatz hat (alt) noch ein gesetztes `send_signal`-Flag, When Startseite/Cockpit die aktiven Kanäle anzeigt, Then wird daraus **kein** „Signal" mehr abgeleitet oder angezeigt.

**AC-4:** Given die TypeScript-Kanal-Typen und Budget-Tabellen im Frontend, When der Code typgeprüft und gebaut wird, Then enthält keine Kanal-Union mehr `'signal'` und `CHANNEL_COL_BUDGET` hat keinen `signal`-Schlüssel; der Build (`npm run build`/`check`) ist grün.

**AC-5:** Given der Orts-Vergleich-Wizard (Layout-Schritt) und die Compare-Vorschau, When ein Nutzer sie durchläuft, Then funktioniert die Kanal-Auswahl mit Email · Telegram · SMS ohne Fehler und ohne Signal-Reste in Bubble/Limit-Markierungen.

**AC-6:** Given die bestehende Test-Suite (Frontend), When sie nach der Änderung läuft, Then sind alle Tests grün; Signal-bezogene Test-Erwartungen sind auf den 3-Kanal-Stand angepasst, keine verbleibende Signal-Assertion.

## Verifikation (mock-frei)

- Playwright-E2E gegen Staging als eingeloggter Nutzer: Trip-Editor-Vorschau (AC-1), Wizard-/Compare-Layout-Schritt (AC-2, AC-5), Cockpit-Kanal-Anzeige (AC-3).
- `npm run check` + Build grün (AC-4).
- Frontend-Test-Suite grün (AC-6).

## Out of Scope (Folge-Schritte)
- Backend-Signal-Entfernung `send_signal` + Renderer + `channel_layout.py` (#610 Schritt 2/2)
- Telegram-Budget/PRIMARY_SLOTS auf 8 (#587)
