---
entity_id: i18n_2919_en_restbegriffe
type: module
created: 2026-11-11
updated: 2026-11-11
status: draft
version: "1.0"
tags: [i18n, epic-2730, issue-2919, frontend, bug]
---

# i18n: EN-Restbegriffe (Filterchips, Kartenstatus, Aktionsblatt, Logo-Untertitel)

**Issue:** #2919 · **Epic:** #2730 · **Konventionen:** docs/reference/i18n_konventionen.md · **ADR:** 0104

## Approval

- [ ] Approved

## Purpose

Bei Profilsprache `en` stehen vier deutsche Texte in der Oberfläche (Mobile-UX-Audit Runde 2, #2601): die Filterchips auf /trips und /compare, der Status auf den Trip- und Vergleichskarten, die Überschrift im mobilen Aktionsblatt und der Logo-Untertitel. Sie kommen künftig aus dem Katalog; Deutsch bleibt pixelgleich. Zusätzlich erkennt die Hardcode-Ratsche das Attribut `eyebrow=`, damit die nächste Stelle dieser Art auffällt.

## Source

- **File:** `frontend/src/lib/components/molecules/StatusFilterPills.svelte`, `frontend/src/lib/components/organisms/SubscriptionCard.svelte`, `frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte`, `frontend/src/lib/brand/BrandWordmark.svelte`, Katalog `frontend/src/lib/i18n/messages/{de,en}/`, Ratsche `frontend/src/lib/i18n/__tests__/hardcode_scan.ts`
- **Identifier:** `PILLEN`, `statusText`, `eyebrow`, `caption`

> **Schicht-Hinweis:** reine Frontend-Änderung (SvelteKit). Kein Go-/Python-Code, keine Nutzerdaten.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `molecules/StatusFilterPills.svelte` | MODIFY | `PILLEN` trägt Katalogschlüssel statt Text, Anzeige per `$t(...)`. „Alle" neu `listen.filter.alle`; Aktiv/Geplant/Pausiert/Fertig über vorhandene `trip.status.active/planned/paused/finished`. Filterwerte (`all`, `aktiv` …) und Zähler bleiben |
| `organisms/SubscriptionCard.svelte` | MODIFY | `statusText` bleibt Logikwert; Anzeige über Abbildung Logikwert → `listen.status.*` (aktiv/geplant/pausiert/fertig/draft vorhanden, neu `listen.status.archiviert`). `data-status`, `HomeTripStatus`, `tripStatus()` unverändert |
| `mobile/SubscriptionActionSheet.svelte` | MODIFY | `eyebrow={$t('aktionen.sheet.eyebrow')}` |
| `brand/BrandWordmark.svelte` | MODIFY | Default-Untertitel zur Renderzeit aus `bausteine.wordmark.caption`; `undefined` = Default, explizit `null` = kein Untertitel |
| `i18n/messages/{de,en}/listen.json, aktionen.json, bausteine.json` | MODIFY | 4 neue Schlüssel je Sprache (siehe unten) |
| `i18n/__tests__/hardcode_scan.ts` | MODIFY | Attributliste um `eyebrow` erweitern |
| `i18n/__tests__/deutsch_unveraendert.test.ts` | MODIFY | neue Schlüssel in die DE-Unverändert-Liste |
| Komponententests (u. a. `organisms/__tests__/subscription_card.test.ts`) | MODIFY/CREATE | en-/de-Rendering der vier Stellen |

### Neue Katalogschlüssel

| Schlüssel | de | en |
|---|---|---|
| `listen.filter.alle` | Alle | All |
| `listen.status.archiviert` | archiviert | archived |
| `aktionen.sheet.eyebrow` | AKTIONEN | ACTIONS |
| `bausteine.wordmark.caption` | V0.20 · Wetter-Briefing | V0.20 · Weather briefing |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** Filterchips und Karten sind bereits geteilte Bausteine für /trips und /compare; keine neue Komponente.
- **Mandantentrennung:** nicht berührt.
- **Kanäle:** nicht berührt (Weboberfläche, kein Briefing-/Alarm-Inhalt).

## Scope

- **Im Scope:** vier Anzeigestellen in der Weboberfläche (Filterchips auf /trips und /compare, Kartenstatus, Überschrift des mobilen Aktionsblatts, Logo-Untertitel), vier neue Katalogschlüssel je Sprache, Ratsche um `eyebrow` erweitert.
- **Außerhalb:** siehe „Nicht im Scope“ unten.

## Definition of Done

Mit Profilsprache `en` zeigen Trip-Liste, Vergleichsliste, mobiles Aktionsblatt und alle Seiten mit Logo keine der vier deutschen Restbegriffe mehr; mit `de` sieht alles aus wie heute. AC-1 bis AC-6 sind durch Tests belegt und auf Staging nachgeprüft.

## Estimated Scope

- **LoC:** ca. +60/-15
- **Files:** ca. 8 Quell-/Katalogdateien + 2 Testdateien
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/i18n` (`t`, `locale`) | module | Katalogzugriff, reaktiv bei Sprachwechsel |
| `trip.status.*` | catalog | vorhandene Statusnamen (Vorbild `StatusSchild.svelte`) |
| `deutsch_unveraendert.test.ts`, Paritätstest | test | sichern de unverändert und de/en-Schlüsselgleichheit |
| ADR-0104 | adr | Logik- und Protokollwerte nie übersetzen |

## Implementation Details

- Logikwerte (`aktiv`, `geplant`, `all`, `HomeTripStatus`, `data-status`, Filterwerte) bleiben unverändert; nur die Anzeige läuft über `$t(...)`.
- Deutsch bleibt pixelgleich: Filterchips mit denselben Wörtern wie heute (Groß-/Kleinschreibung), Kartenstatus klein geschrieben mit CSS-uppercase, Eyebrow „AKTIONEN", Untertitel „V0.20 · Wetter-Briefing".
- BrandWordmark: Katalogtext wird beim Rendern reaktiv aufgelöst (kein statischer Prop-Default), sonst kein Sprachwechsel. `caption === undefined` → Katalogtext, `caption === null` → kein Untertitel, sonst der übergebene Text.
- Ratsche: nur `eyebrow` kommt zur Attributliste. Gemessener Startstand außerhalb `_design-system`: genau ein Treffer (SubscriptionActionSheet), der hier behoben wird; die Allowlist bleibt unverändert.
- E2E `hub-list-menu.spec.ts` sucht `· aktiv` (de, klein): bleibt gültig, da der de-Wert unverändert ist. Bestehende Tests, die den Status-Text prüfen, werden bei Bedarf mitgezogen.

## Expected Behavior

- **Input:** Profilsprache des Nutzers (`de` oder `en`) und unveränderte Logikwerte (Filterwert, `HomeTripStatus`, Caption-Prop).
- **Output:** Filterchips, Kartenstatus, Aktionsblatt-Überschrift und Logo-Untertitel in der Profilsprache, Text aus dem Katalog; Deutsch sieht aus wie heute.
- **Side effects:** keine; Logikwerte, `data-status`/`data-testid` und gespeicherte Daten bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given Profilsprache `en`, When die Seiten /trips und /compare die Filterchips zeigen, Then lauten sie „All / Active / Planned / Paused / Finished" mit unveränderten Zählern; bei Profilsprache `de` lauten sie weiterhin „Alle / Aktiv / Geplant / Pausiert / Fertig" mit denselben Zählern.

- **AC-2:** Given eine Trip- bzw. Vergleichskarte mit Status aktiv, geplant, pausiert, fertig, Entwurf oder archiviert, When die Sprache `en` ist, Then zeigt `data-field="status"` „active / planned / paused / finished / draft / archived" (Großschreibung per CSS) und bei `de` unverändert „aktiv / geplant / pausiert / fertig / draft / archiviert"; `data-status`, Filterwerte und `HomeTripStatus` behalten ihre deutschen Logikwerte.

- **AC-3:** Given das mobile Aktionsblatt einer Karte ist geöffnet, When die Sprache `en` ist, Then lautet die Überschrift (Eyebrow) „ACTIONS", bei `de` weiterhin „AKTIONEN".

- **AC-4:** Given eine Seite mit Logo (z. B. /login, Startseite, Seitenleiste) ohne gesetzten Untertitel, When die Sprache `en` ist, Then lautet der Untertitel „V0.20 · Weather briefing", bei `de` „V0.20 · Wetter-Briefing", und er wechselt bei einem Sprachwechsel ohne Neuladen mit; wird `caption` ausdrücklich auf `null` gesetzt, erscheint weiterhin kein Untertitel.

- **AC-5:** Given die Hardcode-Ratsche, When ein Svelte-Markup ein statisches `eyebrow="…"`-Attribut mit mindestens zwei Buchstaben enthält, Then meldet sie einen Treffer (Fixture-Test), und der Lauf über den echten Quellbaum hat nach diesem Fix keinen `eyebrow`-Treffer außerhalb der Allowlist.

- **AC-6:** Given die Kataloge `de` und `en`, When die Tests laufen, Then existieren die vier neuen Schlüssel (`listen.filter.alle`, `listen.status.archiviert`, `aktionen.sheet.eyebrow`, `bausteine.wordmark.caption`) in beiden Sprachen mit den oben genannten Werten, der Paritätstest bleibt grün, und die de-Texte stehen in der DE-Unverändert-Liste.

## Test Plan

Komponententests laufen mit `node --test` (kein Vitest), echtes Rendering mit `locale` `en` und `de`, keine Mocks.

- StatusFilterPills: Chip-Texte und Zähler in en/de (AC-1).
- SubscriptionCard: Status-Text je Logikwert in en/de, `data-status` unverändert (AC-2).
- SubscriptionActionSheet: Eyebrow en/de (AC-3).
- BrandWordmark: Default-Untertitel en/de, Reaktivität beim Sprachwechsel, `caption=null` ohne Untertitel (AC-4).
- Ratsche: Fixture mit `eyebrow="Aktionen"` ergibt Treffer; Repo-Lauf grün (AC-5).
- Katalog-Parität und DE-Unverändert-Test (AC-6).
- Rot-Nachweis vorab: dieselben Tests mit `en` schlagen gegen den heutigen Stand fehl (deutsche Texte).

## Nicht im Scope

- Generische Erkennung von Prop-Defaults und Literalen in Objekt-Arrays in der Ratsche: teuer und fehleranfällig, weil Logikwerte wie `'aktiv'` von Anzeigetexten nicht unterscheidbar sind. Die Abdeckung erfolgt über die Verhaltenstests (en-Rendering der vier Stellen).
- Änderung der Logikwerte von `tripStatus()` oder `HomeTripStatus`.

## Known Limitations

Künftige Anzeigetexte in Prop-Defaults oder Objekt-Literalen erkennt die Ratsche weiterhin nicht automatisch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (Zweisprachigkeit DE/EN), keine neue ADR
- **Rationale:** Anzeigetexte kommen ausschließlich aus dem Katalog, Logik- und Protokollwerte (`aktiv`, `geplant`, Filterwerte) werden nie übersetzt; dieser Fix wendet die bestehende Entscheidung nur auf vier vergessene Stellen an.

## Changelog

- 2026-11-11: Erstfassung (draft)
