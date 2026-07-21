# Spec: fix-1256-s8b-preview-channel-switch — Hub-Vorschau: Kanal-Umschalter reparieren

**Created:** 2026-07-14
**Issue:** #1256 (Rest-Inventur R1, PO-Entscheid „Plan komplett abarbeiten" 2026-07-14)
**ADR-Nr.:** keine

## Problem

Der Kanal-Umschalter im Hub-Vorschau-Tab ist funktional tot: `CompareTabs.svelte:943`
übergibt `onchange` (klein), `CompareChannelSwitch.svelte` (molecules) erwartet
`onChange` — Svelte-5-Props sind case-sensitiv, der Klick-Handler kommt nie an.
Zusätzlich ist die Kanal-Liste hart `['email','sms']` (Telegram fehlt immer,
Soll: konfigurierte Kanäle, `screen-compare-detail.jsx:351`) und der
„Kanal nicht konfiguriert"-Hinweis (JSX:365-369) fehlt.

## Scope

Nur `frontend/src/lib/components/compare/CompareTabs.svelte` (Vorschau-Tab,
Z. ~472 `previewChannel`-Typ + Z. ~940-991) plus Tests. KEINE Änderung an
`CompareChannelSwitch.svelte` (Komponente ist korrekt), keine Backend-Änderung,
keine neuen PUT-Pfade.

## Acceptance Criteria

- **AC-1:** Given den Hub-Vorschau-Tab eines Presets mit mindestens zwei
  konfigurierten Kanälen / When der Nutzer im Kanal-Umschalter einen anderen
  konfigurierten Kanal anklickt / Then wechselt die Vorschau sichtbar auf diesen
  Kanal (`previewChannel` ändert sich, Render-Fläche zeigt den Kanal-Zweig) —
  der `onChange`-Handler ist korrekt verdrahtet (Prop-Name case-sensitiv).
  - Test: Source-Wächter (Prop `onChange=` am `CompareChannelSwitch` im
    Vorschau-Tab, kein `onchange=`) + Live-E2E Playwright-Klickpfad gegen
    Staging (Klick auf „SMS" → SMS-Hinweis sichtbar, Klick zurück auf
    „Email" → iframe/E-Mail-Zweig sichtbar).

- **AC-2:** Given ein Preset mit konfiguriertem Telegram-Kanal / When der
  Vorschau-Tab gerendert wird / Then bietet der Umschalter Telegram als aktiv
  wählbaren Kanal an (Kanal-Liste kommt aus der Preset-Konfiguration — dieselbe
  Ableitungsquelle wie `channelNamesLabel`, S3 AC-6 — statt hart
  `['email','sms']`), und die Wahl von Telegram zeigt die Render-Fläche im
  Telegram-Zweig (analog SMS-Zweig: `CompareBriefingPreview` mit
  `channel="telegram"`, plus Hinweis solange keine dedizierte
  Telegram-Vorschau existiert).
  - Test: Source-Wächter — Kanal-Liste wird aus dem Preset abgeleitet (kein
    Literal `['email', 'sms']` im Vorschau-Tab); `previewChannel`-Typ umfasst
    `'telegram'`.

- **AC-3:** Given ein Preset, bei dem ein Kanal NICHT konfiguriert ist / When
  der Nutzer diesen (grau dargestellten) Kanal im Umschalter anklickt / Then
  zeigt die Render-Fläche den Hinweis-Zustand „Kanal nicht konfiguriert"
  (Soll: `screen-compare-detail.jsx:365-369`, Copy sinngemäß übernehmen)
  statt einer leeren oder stalen Vorschau.
  - Test: Source-Wächter — Hinweis-Zweig existiert und hängt an „gewählter
    Kanal ∉ konfigurierte Kanäle"; Live-E2E deckt den Klickpfad ab, sofern
    das Staging-Test-Preset einen unkonfigurierten Kanal hat.

## Was darf sich nicht ändern

- E-Mail-Zweig: Desktop-Inbox/iPhone-Mail-Umschalter und Validator-iframe
  (`/api/_validator/compare-email-preview`) bleiben unverändert (AC-19 der
  Programm-Spec, Regressionsnachweis).
- `CompareChannelSwitch.svelte` (molecules) bleibt unangetastet.
- Keine Schreibpfade, hubPutQueue unberührt.

## Test Plan

1. Source-Wächter in bestehender Suite `compare_mobile_shared_hub.test.ts`
   NICHT erweitern — eigene kleine Datei `compare_preview_channel_switch.test.ts`
   (verhaltensbenannt) mit den drei Source-Assertions (RED vor Fix).
2. Playwright: neuer Test in `compare-mobile-vervollstaendigung.spec.ts` oder
   eigener Spec-Abschnitt (Desktop-Viewport reicht — der Bug ist viewport-
   unabhängig): Kanal-Klick wechselt sichtbar.
3. Frontend-Vollsuite bleibt 100 % grün.

## Changelog

- 2026-07-16: Issue #1270 — der in AC-2 offen formulierte Vorbehalt „plus
  Hinweis solange keine dedizierte Telegram-Vorschau existiert" ist eingelöst:
  Telegram (und SMS) haben jetzt eine echte, aus den Preset-Orten gerenderte
  Vorschau (`POST /api/preview/compare/{preset_id}`,
  `docs/specs/modules/compare_channel_preview_dispatch.md`). AC-Wortlaut oben
  unverändert (beschreibt weiterhin korrekt den Zustand vor #1270).
