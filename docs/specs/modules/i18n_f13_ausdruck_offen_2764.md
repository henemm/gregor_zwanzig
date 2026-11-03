---
entity_id: i18n_f13_ausdruck_offen_2764
type: module
created: 2026-11-03
updated: 2026-11-03
status: approved
version: "1.0"
tags: [i18n, epic-2644, epic-2730, issue-2764, frontend]
---

# i18n F13: `AUSDRUCK_OFFEN` der Frontend-Ratsche abbauen

**Issue:** #2764 · **Epics:** #2730, #2644 · **Konventionen:** `docs/reference/i18n_konventionen.md` Abschnitte 3, 4, 6

## Approval

- [x] Approved (PO-Freigabe 2026-11-03, an Claude delegiert)

## Purpose

Die Erweiterung der Frontend-Ratsche um Literale in Markup-Ausdrücken (#2661, F12) hat 16 Treffer in einer offenen Liste `AUSDRUCK_OFFEN` geparkt, ohne Entscheidung. Dieses Paket entscheidet jeden Treffer: echte Nutzertexte gehen in den Katalog (Deutsch byte-gleich, Englisch nach Glossar bzw. Metrik-Register), sprachneutrale Fälle tragen am Fundort einen begründeten Marker. Danach ist `AUSDRUCK_OFFEN` leer und bleibt es.

## Source

- **File:** `frontend/src/lib/i18n/__tests__/hardcode_scan.ts` (Marker, leere Liste), betroffene Svelte-Dateien unten
- **Identifier:** `scanneAusdruecke`, `AUSDRUCK_OFFEN`, `symbolZeilenName`

### Entscheidung je Treffer

| Datei | Literal | Entscheidung |
|---|---|---|
| `organisms/SubscriptionCard.svelte` | `(ohne Namen)` | Katalog `bausteine.karte.ohne_namen` (de „(ohne Namen)", en „(no name)" wie `listen.vergleiche.ohne_namen`) |
| `shared/WeatherMetricsTab.svelte` | acht deutsche Rückfall-Namen in `symbolName(...)` | Name kommt weiter aus dem Metrik-Register (`metricLabel`); der Rückfall ohne Register-Eintrag ist ein Katalogschlüssel `wertebereiche.symbolzeile.<id>`, en = `label_en` des Python-Registers (`_ENGLISH_NAMES`) |
| `shared/WeatherMetricsTab.svelte` | `temperature` | Marker: Metrik-Kennung, kein Text |
| `shared/WeatherMetricsTab.svelte` | `TH:H` | Marker: SMS-Protokoll-Token, nie übersetzt (ADR-0104) |
| `weather-metrics-tab/WeatherV2Reihenfolge.svelte` | `Telegram` | Marker: Kanal-Eigenname |
| `trip-new/TripNewEditor.svelte` | `GPX` | Marker: Dateiformat-Name |
| `routes/+page.svelte` | `gregor · zwanzig` | Katalog: bestehende Schlüssel `bausteine.marke.gregor`/`.zwanzig` (F12) |
| `routes/trips/[id]`, `routes/compare/[id]` | `— Gregor Zwanzig` | Katalog: bestehender Schlüssel `bausteine.marke.name` (F12) |

### Marker

`/* i18n-neutral: <Begründung> */` als Kommentar im Svelte-Ausdruck nimmt die Literale dieses Ausdrucks aus. Die Begründung hat mindestens 8 Zeichen. Ein Literal mit Umlaut/ß oder Signalwort bleibt trotz Marker ein Treffer (sprachneutraler Text ist nie deutsch).

### Affected Files

| Datei | CREATE/MODIFY |
|---|---|
| `frontend/src/lib/i18n/__tests__/hardcode_scan.ts` | MODIFY |
| `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | MODIFY |
| `frontend/src/lib/components/__tests__/f13_ausdruck_offen_sprache.test.ts` | CREATE |
| Svelte-Dateien der Tabelle, `wertebereicheAnzeige.ts`, Katalog `bausteine.json`/`wertebereiche.json` (de, en), `f5KatalogAnker.ts`, `deutsch_unveraendert.test.ts` | MODIFY |

## Acceptance Criteria

**AC-1:** Given die Frontend-Ratsche, When `keine_hartkodierten_nutzertexte.test.ts` läuft, Then ist `AUSDRUCK_OFFEN` leer und kein Ausdrucks-Literal unter `frontend/src` ist ein Treffer ohne Eintrag.

**AC-2:** Given ein Svelte-Ausdruck mit einem Literal, When er den Marker `/* i18n-neutral: <Begründung> */` mit mindestens 8 Zeichen Begründung trägt, Then ist das Literal kein Treffer; ohne Begründung oder bei einem Literal mit Umlaut bleibt es ein Treffer.

**AC-3:** Given eine Karte (`SubscriptionCard`) ohne Namen, When sie mit Sprache `en` gerendert wird, Then steht „(no name)" im Render; mit `de` steht byte-gleich „(ohne Namen)".

**AC-4:** Given eine Mehrfach-Symbol-Zeile ohne Register-Eintrag, When `symbolZeilenName` mit `en` aufgerufen wird, Then liefert sie den englischen Registernamen (z. B. „Feels-like temperature"); mit `de` den bisherigen deutschen Rückfall byte-gleich; mit Register-Eintrag gewinnt weiterhin der Registername.

**AC-5:** Given Startseite, Trip-Hub und Vergleichs-Hub, When die Marke ausgegeben wird, Then stammt sie aus `bausteine.marke.*`, und der deutsche Wortlaut („gregor · zwanzig", „<Name> — Gregor Zwanzig") ist unverändert.

## Changelog

- 2026-11-03: Erstfassung (#2764).
