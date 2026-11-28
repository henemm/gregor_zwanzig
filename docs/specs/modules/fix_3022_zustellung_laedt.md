---
entity_id: fix_3022_zustellung_laedt
type: bugfix
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: fix-3022-zustellung-laedt
tags: [orts-vergleich, compare-tabs, zustellung, wetter, hydration]
---

# Orts-Vergleich: Reiter Zustellung und Wetter erscheinen sofort (Issue #3022)

## Approval

- [ ] Approved

## Purpose

Im Orts-Vergleich-Hub bleiben die Reiter Zustellung und Wetter leer (nur ein Sperr-Kopf), solange die Katalog-Abrufe hängen; der Trip zeigt dieselben Reiter sofort. Die Hydrations-Gates in `CompareTabs.svelte` schützen nichts mehr, weil beide Reiter ihren Stand selbst aus dem Preset bzw. eigenem Laden beziehen. Sie entfallen, damit Orts-Vergleich und Trip gleich mounten (nur aktiver Reiter).

## Source

- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
- **Identifier:** Mount-Bedingungen vor `<WetterTab>` und `<ZustellungTab>` (`wetterMetrikenLayoutHydrationBereit`, `versandHydrated`, `alarmeHydrated`), Sperr-Kopf-Zweige, CSS `.hub-kopf-sperre*`

> **Schicht:** reines Frontend (SvelteKit). Keine Änderung an Go-API oder Python-Core.
>
> **Trip/Ortsvergleich-Teilung:** Die Änderung stellt Parität her; Mount-Bedingung wie `trip-detail/TripTabs.svelte` (nur `activeTab`). Reiter-Code bleibt geteilt (`shared/zustellung-tab/`, `organisms/wetter-tab/`), kein neuer Baustein.
>
> **Mandantentrennung:** kein neuer Datenpfad, kein neuer Endpoint; Isolation unverändert (`user_id` aus Auth-Kontext). Nutzerdaten werden nicht anders gelesen oder geschrieben.
>
> **Kanäle:** Briefing-/Alarm-Inhalt aller vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) unverändert; nur die Anzeige der Kanal-Tabelle im Hub wird früher sichtbar.

## Estimated Scope

- **LoC:** ca. -40 Quelle, dazu angepasste Tests und -62 Einträge Besitzerliste
- **Files:** 1 Quelldatei, 3 Tests angepasst, 1 neuer Render-Test, 1 JSON
- **Effort:** low

## Scope

- **Drin:** Mount-Bedingung von Reiter Wetter und Reiter Zustellung im Orts-Vergleich-Hub (nur noch aktiver Reiter, wie im Trip), Entfernen der Sperr-Kopf-Zweige samt CSS, Anpassung der drei Alt-Tests mit Gate-Pflicht, neuer Render-Test mit hängendem Katalog, Entfernen der 62 `#3022`-Einträge aus der Besitzerliste.
- **Nicht drin:** Rückbau des toten `wizardState`-Feldsatzes und der Hydrations-Effekte (Folge-Issue #3495), Trip-Hub, Backend, Speicherpfade.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/zustellung-tab/ZustellungTab.svelte` | component | liest Stand direkt aus `preset`, Speicher-Basis `startStand` (unverändert) |
| `organisms/wetter-tab/WetterTabInhalt.svelte` | component | eigener Ladezustand „Lade Metriken …“ (unverändert) |
| `trip-detail/TripTabs.svelte` | component | Referenz für Mount-Bedingung |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | data | Besitzer-Einträge mit verweis `#3022` |
| Elementlisten-Abgleich (`--abnahme`) | tool | Live-Nachweis auf Staging |

## Implementation Details

1. `CompareTabs.svelte`: `{#if activeTab === 'wetter'}` mountet `WetterTab`, `{#if activeTab === 'zustellung'}` mountet `ZustellungTab`, ohne weitere Hydrations-Bedingung. Die Sperr-Kopf-Zweige (`{:else}`) und die CSS-Regeln `.hub-kopf-sperre*` werden entfernt.
2. Die Hydrations-Effekte und das `wizardState`-Feldset bleiben vorerst unverändert stehen (harmlos, ohne Leser).
3. Bestehende Tests, die die Gate-Pflicht erzwingen, werden umgekehrt: die Reiter bedienen keine `wizardState`-Felder mehr, ihr Stand kommt aus dem Preset bzw. eigenem Ladezustand. Betroffen: `s3a2794_zustellung_vergleich_mount_hydration.test.ts` (F012), `s3a2794_teil3_wettertab_mount.test.ts`, `compare_versand_hydration_unter_wetter_metriken.test.ts` (Template-Gate #1743 AC-9). `bereichskopf_3006.test.ts`, `listenzeile_3007.test.ts`, `s3a2794_flush_hydration_kette.test.ts` und `compare_wetter_reiter_hydration_nach_preset_sync_3298.test.ts` werden geprüft und nur angepasst, wenn sie rot werden.
4. Neuer Render-Test der echten `CompareTabs`-Komponente mit hängendem Katalog (Promise, die nie auflöst); kein Mock-Theater.
5. `elementliste_besitzer.json`: die 62 Einträge mit verweis `#3022` (59 `orte.zustellung.laedt.*`, 3 `orte.wetter.laedt.*`) werden entfernt.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount-Gates, Sperr-Kopf-Zweige und `.hub-kopf-sperre*`-CSS entfernen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 62 Einträge `#3022` entfernen |
| `frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts` | MODIFY | F012 umkehren: Mount bei jeder Flag-Kombination, sobald Reiter aktiv |
| `frontend/src/lib/components/shared/__tests__/s3a2794_teil3_wettertab_mount.test.ts` | MODIFY | WetterTab mountet ohne Hydrations-Flag |
| `frontend/src/lib/components/compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts` | MODIFY | Template-Gate-Pflicht umkehren |
| `frontend/src/lib/components/compare/__tests__/compare_tabs_haengender_katalog_3022.test.ts` | CREATE | Render-Test mit hängendem Katalog |

## Expected Behavior

- **Input:** Orts-Vergleich-Hub, Katalog-Abrufe (`GET /api/metrics`, `GET /api/compare/metrics`) hängen oder sind langsam.
- **Output:** Reiter Zustellung zeigt Kopf, Briefing-Zeiten, Laufzeit, Kanal-Tabelle und Stille Stunden; Reiter Wetter zeigt Abschnittskopf und „Lade Metriken …“.
- **Side effects:** keine; insbesondere kein Speicheraufruf durch bloßes Öffnen eines Reiters.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN Katalog-Abrufe hängen WHEN Reiter Zustellung aktiv THEN Briefing-Zeiten, Laufzeit, Kanal-Tabelle, Stille Stunden sind gerendert (rot vor Fix wegen Sperr-Kopf).
- [ ] GIVEN Katalog hängt WHEN Reiter Wetter aktiv THEN `data-abschnitt="abschnittskopf"` und „Lade Metriken …“ sind sichtbar.
- [ ] GIVEN hängender Katalog WHEN Reiter Zustellung geöffnet, keine Nutzergeste THEN kein PUT auf den Orts-Vergleich.
- [ ] GIVEN geöffneter Reiter Zustellung WHEN Briefing-Zeit geändert THEN genau ein Speicheraufruf, Kanäle, Stille Stunden, Laufzeit unverändert gegenüber dem gespeicherten Stand.
- [ ] Angepasste Alt-Tests (F012, WetterTab-Mount, Template-Gate) laufen grün im neuen Soll.
- [ ] Live: Elementlisten-Abgleich auf Staging für `orte.zustellung.laedt` und `orte.wetter.laedt` ohne Abweichung.

## Acceptance Criteria

- **AC-1:** Given die Katalog-Abrufe im Orts-Vergleich hängen / When der Nutzer den Reiter Zustellung öffnet / Then erscheinen sofort Kopf, Briefing-Zeiten, Laufzeit, Kanal-Tabelle und Stille Stunden, gleich wie im Normalzustand und im Trip.
  - Test: Render der echten `CompareTabs` mit nie auflösender Katalog-Abfrage, Reiter Zustellung zeigt alle fünf Abschnitte statt nur eines Sperr-Kopfes.

- **AC-2:** Given der Metrik-Katalog hängt im Orts-Vergleich / When der Nutzer den Reiter Wetter öffnet / Then zeigt der Reiter den Abschnittskopf und den Hinweis „Lade Metriken …“ wie im Trip.
  - Test: Render der echten `CompareTabs` mit hängendem Katalog, Element `data-abschnitt="abschnittskopf"` und Ladetext sind vorhanden; kein Sperr-Kopf.

- **AC-3:** Given ein gespeicherter Orts-Vergleich und hängender Katalog / When der Nutzer den Reiter Zustellung nur öffnet, ohne etwas zu ändern / Then wird nichts gespeichert (kein PUT) und die angezeigten Werte entsprechen dem gespeicherten Orts-Vergleich.
  - Test: Render mit protokolliertem Speicherweg und bekanntem Preset; nach dem Mount null Schreibaufrufe, Felder gleich Preset.

- **AC-4:** Given der Reiter Zustellung ist offen / When der Nutzer eine Briefing-Zeit ändert / Then wird gespeichert und Kanäle, Stille Stunden und Laufzeit behalten ihren bisherigen Wert (kein Überschreiben mit Platzhaltern).
  - Test: Zeit ändern im gerenderten Reiter, der Speicher-Payload enthält die neue Zeit und alle übrigen Felder unverändert aus dem Preset.

- **AC-5:** Given die Besitzerliste des Elementlisten-Abgleichs / When der Abgleich auf Staging für die Zustände `orte.zustellung.laedt` und `orte.wetter.laedt` läuft / Then meldet er keine Abweichung, und die Liste enthält keinen Eintrag mit verweis „#3022“ mehr.
  - Test: Abgleich auf Staging mit Prüfkonto grün; Auszählung der Besitzerliste ergibt 0 Einträge mit „#3022“.

- **AC-6:** Given zwei verschiedene Nutzer mit je eigenem Orts-Vergleich / When beide den Reiter Zustellung öffnen / Then sieht jeder nur seine eigenen Werte, da kein neuer Datenpfad entsteht.
  - Test: im Staging-Abgleich zwei Konten; Werte je Konto entsprechen dem eigenen gespeicherten Stand.

## Definition of Done

- AC-1 bis AC-4 durch Render-Tests der echten Komponente grün belegt, vorher rot nachgewiesen.
- AC-5 und AC-6 per Elementlisten-Abgleich auf Staging belegt.
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe.
- PR mit allen CI-Checks grün gemergt, Prod-Deploy mit Selftest Exit 0, Issue #3022 mit Ergebnis-Kommentar geschlossen.

## Known Limitations

- Der tote `wizardState`-Feldsatz und die Hydrations-Effekte bleiben vorerst bestehen; Rückbau ist ein eigenes Folge-Issue (Nebenbefund).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerbehebung zur Herstellung der Trip/Orte-Parität (ADR-0097) ohne neue Entscheidungsfläche; es wird keine bestehende Entscheidung geändert.

## Changelog

- 2026-11-28: Initial spec created
