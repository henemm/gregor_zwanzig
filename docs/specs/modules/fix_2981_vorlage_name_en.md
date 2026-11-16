---
entity_id: fix_2981_vorlage_name_en
type: bugfix
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
tags: [i18n, adr-0104, wetter-reiter, vorlage, epic-2913]
workflow: fix-2981-vorlage-name-en
issue: 2981
---

# Eingebaute Wetter-Vorlagennamen zweisprachig (Bug #2981)

## Approval

- [ ] Approved

## Purpose

Bei Sprache Englisch zeigt die Vorlage-Karte im Reiter Wetter (und der alte Wetter-Metriken-Tab) die sieben eingebauten Vorlagennamen auf Deutsch („Wandern“ statt „Hiking“), weil das Frontend das feste deutsche Label des Servers ungefiltert anzeigt. Die Namen sollen sprachabhängig über den Katalog angezeigt werden (ADR-0104), ohne Server, Protokoll oder gespeicherte Daten zu ändern.

Grundlage: `docs/context/fix-2981-vorlage-name-en.md` (maßgeblich), `docs/reference/i18n_konventionen.md`, Vorbild ID-zu-Katalogschlüssel-Map `PROFILE_LABELS` in `frontend/src/lib/components/compare/subscriptionHelpers.ts`.

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte`, `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte`
- **Identifier:** neuer Helfer `vorlageNameKey(id)` in `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts`; Katalogschlüssel `wetter.vorlage.name.<id>`

> **Schicht-Hinweis:** Reine Frontend-Arbeit (SvelteKit, `frontend/src/...`). Python `WEATHER_TEMPLATES` (`src/app/metric_catalog.py`) und der Go-Namensschutz (`internal/handler/metric_preset.go`) bleiben unberührt; das Server-Label bleibt deutsch und dient als Fallback.
>
> **Trip/Ortsvergleich-Teilung:** Die Vorlage-Karte wird über `WetterTabInhalt` mit `context="route"|"vergleich"` von beiden Kontexten gemeinsam genutzt; die Änderung wirkt daher in beiden, es entsteht keine Compare-eigene Komponente.
>
> **Mandantentrennung:** Keine Nutzerdaten werden bewegt (reine Anzeige), kein neuer Endpoint.
>
> **Kanäle:** Briefing- und Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS) sind nicht berührt; Vorlagennamen erscheinen nur in der Oberfläche.

## Estimated Scope

- **LoC:** ca. +60/−8
- **Files:** 6
- **Effort:** low, Risiko LOW (reine Anzeige)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts` | CREATE | Map der 7 Systemvorlagen-IDs auf `wetter.vorlage.name.<id>`; `vorlageNameKey(id)` liefert für unbekannte ID `null` |
| `frontend/src/lib/i18n/messages/de/wetter.json` | MODIFY | 7 Schlüssel mit den heutigen deutschen Labels (DE unverändert) |
| `frontend/src/lib/i18n/messages/en/wetter.json` | MODIFY | 7 Schlüssel: Alpine trekking, Hiking, Ski touring, Winter sports, Cycling tour, Water sports, General |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | Kopfzeile, Picker-Optionen, Zurücksetzen-Knopf, Verlust-Text und Rückfrage `{neu}` zeigen den Katalognamen, reaktiv per `$t` |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte` | MODIFY | Chip-Text und `title` über denselben Helfer |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/vorlageName.test.ts` | CREATE | Tests (`node --test`) für Helfer und Katalog |

### Out of Scope

- Server (Python, Go), `/api/templates`-Antwort, `vorlagenListe` (Feld `label` bleibt Server-Fallback).
- Übersetzung eigener (Nutzer-)Vorlagen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/i18n` (`t`, Katalog, `MessageKey`) | module | reaktive Übersetzung, Paritätstest DE/EN |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts` (`vorlagenListe`, `VorlageEintrag`) | module | liefert id und Server-Label, unverändert |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` (`PROFILE_LABELS`) | module | Vorbild für die ID-Map |
| `frontend/src/lib/i18n/messages/{de,en}/trip.json` (`trip.aktivitaet.*`) | catalog | Begriffsvorbild für die EN-Namen |
| `frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts` | test | DE-Texte müssen unverändert bleiben |
| `docs/adr/0104-*` | ADR | Zweisprachigkeit, neue Nutzertexte nur über den Katalog |

## Implementation Details

Übersetzung nur in der Anzeige. `vorlageName.ts` hält die Map der sieben IDs (alpen-trekking, wandern, skitouren, wintersport, radtour, wassersport, allgemein) auf je einen Katalogschlüssel. Die Anzeigestellen der Karte lösen den Namen über einen kleinen Helfer auf: ist der Schlüssel bekannt, wird `$t(key)` angezeigt, sonst das Server-Label (`v.label`), bei fehlendem Eintrag wie bisher die ID. Eigene Vorlagen laufen nicht durch die Map und bleiben im Nutzernamen unverändert. Da die Auflösung im Template per `$t` geschieht, wirkt ein Sprachwechsel ohne Neuladen. Die Rückfrage übergibt den bereits aufgelösten Namen als `{neu}`.

## Expected Behavior

- **Input:** Sprache des Nutzers (DE/EN), Systemvorlagen-ID und Server-Label.
- **Output:** Anzeigename der Vorlage in der Sprache des Nutzers; unbekannte ID und eigene Vorlagen unverändert mit Server- bzw. Nutzername.
- **Side effects:** keine; gespeichert wird weiterhin die ID.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Sprache EN WHEN `vorlageNameKey("wandern")` aufgelöst und über den Katalog angezeigt wird THEN „Hiking“ (alle 7 IDs mit erwartetem EN-Namen).
- [ ] Test 2: GIVEN Sprache DE WHEN dieselben 7 IDs aufgelöst werden THEN die heutigen deutschen Namen (z. B. „Wandern“).
- [ ] Test 3: GIVEN unbekannte ID WHEN aufgelöst THEN `null` und die Anzeige fällt auf das Server-Label zurück.
- [ ] Test 4: GIVEN Katalog DE und EN THEN jeder Map-Schlüssel existiert in beiden Sprachen (Parität, keine leeren Werte).
- [ ] Test 5: GIVEN eigene Vorlage mit Nutzername WHEN die Karte sie anzeigt THEN der Name bleibt in beiden Sprachen unverändert.

Die Tests laufen über `node --test` ohne Mock-Theater: echter Katalog, echte Map, echte Auflösungsfunktion. Das Zusammenspiel der Karte wird im Staging-Lauf in der Oberfläche bei Sprache EN geprüft.

## Acceptance Criteria

- **AC-1:** Given der Nutzer hat die Sprache Englisch und öffnet den Reiter Wetter eines Trips mit der Vorlage „wandern“ / When die Vorlage-Karte angezeigt wird / Then die Kopfzeile zeigt „Hiking“ statt „Wandern“.
  - Test: Nutzer mit Sprache EN sieht die Vorlagenkarte mit englischem Namen (alle sieben eingebauten Namen englisch: Alpine trekking, Hiking, Ski touring, Winter sports, Cycling tour, Water sports, General).

- **AC-2:** Given der Nutzer hat die Sprache Englisch und öffnet die Vorlagenauswahl / When die Liste der Systemvorlagen erscheint, eine andere Vorlage gewählt wird und die Rückfrage („Use ‘…’?“, ggf. mit Verlust-Hinweis) sowie der Zurücksetzen-Knopf sichtbar werden / Then Auswahlliste, Rückfrage, Verlust-Text und „Reset to …“ nennen überall den englischen Vorlagennamen.
  - Test: Auswahl öffnen, Vorlage wechseln, Rückfrage und Zurücksetzen-Knopf auf englische Namen prüfen.

- **AC-3:** Given der Nutzer hat die Sprache Deutsch / When er die Vorlage-Karte, die Auswahl, die Rückfrage und den Zurücksetzen-Knopf ansieht / Then erscheinen die deutschen Namen wie bisher unverändert („Wandern“, „Alpen-Trekking“ usw.).
  - Test: DE-Anzeige und `deutsch_unveraendert`-Prüfung bleiben grün, kein deutscher Text hat sich geändert.

- **AC-4:** Given der Nutzer hat eine eigene Vorlage mit selbst gewähltem Namen gespeichert / When die Vorlage-Karte oder die Auswahl in Deutsch oder Englisch angezeigt wird / Then bleibt der selbst gewählte Name in beiden Sprachen unübersetzt stehen.
  - Test: eigene Vorlage „Mein Wochenende“ erscheint bei EN und DE identisch.

- **AC-5:** Given der Server liefert eine Systemvorlage mit einer dem Frontend unbekannten ID / When die Vorlage angezeigt wird / Then erscheint das vom Server gelieferte Label (nie leer, nie ein Platzhalter-Schlüssel).
  - Test: unbekannte ID zeigt das Server-Label in DE und EN.

- **AC-6:** Given der Nutzer sieht die Vorlage-Karte in Deutsch / When er die Sprache auf Englisch umstellt, ohne die Seite neu zu laden / Then wechseln alle sichtbaren Vorlagennamen sofort auf Englisch (und beim Zurückstellen wieder auf Deutsch).
  - Test: Sprachwechsel im laufenden Reiter Wetter ändert die Namen ohne Neuladen.

- **AC-7:** Given der Nutzer hat die Sprache Englisch und legt einen Trip oder Orts-Vergleich an, wo noch der alte Wetter-Metriken-Tab (Vorlagen-Leiste) eingebunden ist / When die Leiste mit den Vorlagen-Chips angezeigt wird / Then zeigen Chip-Text und Tooltip den englischen Vorlagennamen, in Deutsch unverändert den deutschen.
  - Test: Vorlagen-Leiste bei EN zeigt „Hiking“ usw., bei DE „Wandern“ usw.

## Definition of Done

- AC-1 bis AC-7 erfüllt; Test 1–5 aus dem Test Plan grün, Katalog-Parität DE/EN und `deutsch_unveraendert` grün, kein bestehender Test gelöscht.
- Adversary-Verdict VERIFIED: eine Mutation der Map (z. B. ein EN-Name zurück auf Deutsch oder Fallback auf leeren Text) wird von einem Test gefangen.
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden (Sichtprüfung AC-2, AC-6, AC-7 bei Sprache EN), Prod-Deploy mit Selftest-Exit 0.
- Issue #2981 geschlossen; Epic #2913 bleibt offen, solange weitere Kind-Issues offen sind.

## Known Limitations

- Der Namensschutz der Systemvorlagen im Go-Server arbeitet weiter mit den deutschen Namen; ein Nutzer kann daher eine eigene Vorlage nicht „Wandern“ nennen, auch nicht in EN. Das ist gewollt (Server unberührt).
- Eine neue Systemvorlage auf dem Server erscheint bis zur Katalog-Ergänzung mit dem deutschen Server-Label (Fallback).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0104 (Zweisprachigkeit, Nutzertexte nur über den Katalog)
- **Rationale:** Reine Anzeigeübersetzung im Frontend nach bestehendem Muster (`PROFILE_LABELS`); der Server bleibt SSOT für ID und deutsches Label, keine neue Entscheidungsfläche.

## Changelog

- 2026-11-16: Initial spec created (Bug #2981, Teil von Epic #2913)
