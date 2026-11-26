---
entity_id: fix_3364_nur_morgens_abends
type: bugfix
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: fix-3364-nur-morgens-abends
tags: [wetter-tab, was-steht-wo, bericht-flags, epic-3122, issue-3364]
---

# Reiter Wetter: Größen mit „nur morgens/abends“ korrekt anzeigen, abwählen und kennzeichnen

## Approval

- [ ] Approved

## Purpose

Größen, die nur im Morgen- oder nur im Abend-Briefing stehen (Bericht-Flags `morning_enabled` / `evening_enabled` je Metrik), erscheinen im Reiter Wetter als gewählt, lassen sich mit „−“ vollständig aus beiden Briefings nehmen und werden in der Karte „Was steht wo“ je Zeile gekennzeichnet. Außerdem hakt die Karte den 3-Tages-Ausblick nur an, wenn ein Ausblick-Briefing die Größe wirklich führt (Issue #3364, Nachtrag 25.11., Epic #3122).

## Source

- **File:** `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts`, `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts`, `src/services/placements_view_service.py`, `src/services/placements.py`
- **Identifier:** `tripMetrikEintraege` / `auswahlAus…` (Lesen), `tripMetriken` (Schreiben), `_antwort` (Zeilenfeld), `_heute_ohne_einstellung` / `placements_aus_grundauswahl` (Ausblick-Haken)

> **Schicht-Hinweis:** Frontend (SvelteKit: Lesen, Schreiben, Zeilenmarke, i18n) und Python-Core (`src/services/`: Zeilenfeld, Ausblick-Haken). Go-API nur Erstanlage-Prüfung (`erstanlage_placements`) und bestehende Felderhalt-Tests; keine neue Go-Logik vorgesehen, es sei denn die Prüfung zeigt dort denselben Ausblick-Fehler.
>
> **Trip/Ortsvergleich-Teilung:** Der Vergleich kennt keine Bericht-Flags (`active_metrics`), das Pendant entfällt bewusst. Das neue Zeilenfeld wird nur für `route` (Trip) geliefert; die geteilte Karten-Komponente zeigt die Marke nur, wenn das Feld da ist.
>
> **Mandantentrennung:** Die Änderung bewegt Trip-Konfiguration; Tests laufen mit zwei verschiedenen Nutzern (`user_id` aus Auth-Kontext, nie `"default"`).
>
> **Kanäle:** Der Mail-Pfad `_filter_metrics_by_report_type` (Choke-Point für E-Mail, Telegram, SMS, Premium-SMS) bleibt unverändert; alle vier Kanäle lesen weiter dieselbe Liste. Die Schreibseite sorgt nur dafür, dass die Liste nach „−“ stimmt.

## Scope

**Im Scope:** Reiter Wetter im Trip-Kontext (`route`): Lesen der Auswahl nach Briefing-Semantik, Schreiben bei Ab- und Wiederanwahl (Bericht-Flags entfernen), Zeilenkennzeichnung „nur morgens“/„nur abends“ (DE/EN) in der Karte „Was steht wo“ aus der Python-Antwort, Ausblick-Haken nur bei einem Briefing aus `outlook_reports`, das die Größe führt (Anzeige und Erstanlage).

**Nicht im Scope:** eine Bedienung „nur morgens/abends“ in der Tabelle (feat_3122), der Vergleich-Kontext (keine Bericht-Flags), der Mail-Pfad `_filter_metrics_by_report_type`, eine Datenmigration von Bestands-Trips.

## Estimated Scope

- **LoC:** ~150
- **Files:** ca. 13 (siehe Tabelle, inkl. Tests und Doku)
- **Effort:** medium

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | MODIFY | „Gewählt“ = in mindestens einem Briefing geführt; Kinder (`mitAbgeleiteten`) entsprechend |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts` | MODIFY | Abwahl und Wiederanwahl entfernen die Bericht-Flags des Eintrags |
| `src/services/placements_view_service.py` | MODIFY | neues Zeilenfeld `briefing_only` (nur Trip) |
| `src/services/placements.py` (ggf. `src/services/channel_list_resolver.py`) | MODIFY | Ausblick-Haken nur bei Führung durch ein Briefing aus `outlook_reports` |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts`, `wasStehtWoStand.ts` | MODIFY | Zeilenmarke durchreichen |
| `frontend/src/lib/components/molecules/EinstellTabelle.svelte` | MODIFY | Zeilenmarke anzeigen |
| `frontend/src/lib/i18n/messages/de/*.json`, `frontend/src/lib/i18n/messages/en/*.json` | MODIFY | zwei neue Schlüssel je Sprache |
| `docs/reference/api_contract.md` | MODIFY | neues Antwortfeld `briefing_only` |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts` | MODIFY | drei `todo`-Fälle (Describe „#3020 G44“) scharf schalten |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/aenderungsfaelle_an_der_tabelle_3020.test.ts` | MODIFY | Ausnahme `cloud_low` (~Z.86-90) entfernen |
| `tests/` (neue Python-Testdatei, Name legt der Developer fest) | CREATE | Zeilenfeld und Ausblick-Haken ohne Mocks |
| `docs/specs/modules/rework_3020_testtabelle.md` | MODIFY | G44 und `D-trip_tabellen-nur_ein_bericht_*` auf erledigt |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricConfig` / `_filter_metrics_by_report_type` (`src/app/models.py`) | module | Quelle der Wahrheit der Semantik: Flag wenn gesetzt, sonst `enabled` |
| `tabellen_grundauswahl` (`src/services/channel_list_resolver.py`) | function | liefert die Zeilenmenge je Briefing bereits |
| `wetterZustand.ts` (`standAusAbo`, `ohneMetrik`) | module | Zustand des Reiters, vom Test genutzt |
| `wetterTabSpeicherung.ts` (`tripNutzlast`) | module | Speichernutzlast, Read-Modify-Write |
| `feld_erhalt_ohne_ausnahme.test.ts`, `internal/store/trip_display_config_felderhalt_test.go` | test | Felderhalt muss grün bleiben |
| feat_3122_was_steht_wo, rework_3020_testtabelle, ADR-0124, ADR-0050 Regel 3, ADR-0104 | spec/adr | Vorgaben für Tabelle, Bericht-Flags, i18n |

## Implementation Details

Ursachen (belegt in `docs/context/fix-3364-nur-morgens-abends.md`): Das Lesen wertet nur `enabled`; das Schreiben setzt nur `enabled` und lässt die Flags stehen, sodass der Python-Override die Größe in der Mail hält; die Zeilenkennzeichnung entfiel mit #3297/#3383; der Ausblick-Haken kommt aus Vorgabemengen ohne `outlook_reports`.

Verbindliche Entscheidungen des Tech Leads:

1. Alle vier Teile (Lesen, Schreiben, Kennzeichnung, Ausblick-Haken) in einem Workflow.
2. Abwahl „−“: `enabled:false` setzen und die Schlüssel `morning_enabled` / `evening_enabled` des Eintrags entfernen; andere Felder bleiben (Read-Modify-Write mit Merge).
3. Wiederanwahl „+“: `enabled:true`, Flags entfernt, also in beiden Briefings. Die Tabelle hat keine Bedienung je Briefing (feat_3122 Z.351).
4. Unveränderte Einträge behalten ihre Flags beim Speichern.
5. „Gewählt“ beim Lesen = in mindestens einem Briefing geführt (je Briefing: Flag wenn gesetzt, sonst `enabled`).
6. Kennzeichnung kommt aus Python als Zeilenfeld `briefing_only` (`"morning"`, `"evening"` oder `null`), nur Trip. Regel: je Metrik nach Flags, morgens geführt XOR abends geführt, unabhängig davon, welche Briefings abonniert sind. Anzeige als Zeilenmarke; Texte DE „nur morgens“ / „nur abends“, EN „morning only“ / „evening only“ über den Katalog. Protokoll-Token bleiben unübersetzt.
7. Ausblick-Haken einer Zeile nur, wenn mindestens ein Briefing aus `outlook_reports` die Größe führt; gilt für Anzeige und Erstanlage gleichermaßen.

Nicht im Scope: Bedienung „nur morgens“ in der Tabelle (feat_3122 Z.351), Vergleich-Kontext, Änderung am Mail-Pfad `_filter_metrics_by_report_type`, Änderungen an Gate-Konfiguration.

## Expected Behavior

- **Input:** Trip mit Metrik-Einträgen, die `morning_enabled` / `evening_enabled` tragen; Nutzer öffnet Reiter Wetter, klickt „−“ oder „+“, öffnet Karte „Was steht wo“.
- **Output:** Größe erscheint als gewählt; nach „−“ ist sie in keinem Briefing mehr; Karte zeigt „nur morgens“/„nur abends“ je Zeile; Ausblick-Haken stimmt mit den Briefings überein.
- **Side effects:** Beim Abwählen und Wiederanwählen verlieren genau die Bericht-Flags des betroffenen Eintrags ihren Wert; alle anderen Felder und Einträge bleiben unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Trip mit `cloud_mid: enabled:false, morning_enabled:true` WHEN Reiter-Zustand gelesen THEN Größe ist gewählt (Frontend, `ampelModell`).
- [ ] Test 2: GIVEN gewählte nur-morgens-Größe WHEN „−“ und Speichern THEN Eintrag hat `enabled:false` ohne Flags, übrige Felder identisch, und Python-Mail-Filter führt sie weder morgens noch abends.
- [ ] Test 3: GIVEN zuvor abgewählte Größe WHEN „+“ THEN `enabled:true` ohne Flags, beide Briefings führen sie.
- [ ] Test 4: GIVEN Einträge mit Flags WHEN Speichern ohne Änderung THEN Flags unverändert (`feld_erhalt_ohne_ausnahme.test.ts` und Go-Felderhalt bleiben grün, zwei Nutzer).
- [ ] Test 5: Die drei Fälle `n3_semantik_wie_mail`, `n3_editor_kennzeichnet_je_zeile`, `n3_kennzeichnung_folgt_dem_editorstand` in `was_steht_wo_karte.test.ts` (Describe „#3020 G44“) laufen ohne `todo` und unabgeschwächt grün (DE und EN).
- [ ] Test 6: Python-Test (ohne Mocks): GIVEN Trip-Konfiguration WHEN Karten-Antwort gebaut THEN `briefing_only` ist `"morning"`, `"evening"` oder `null` je Flags; im Vergleich fehlt das Feld.
- [ ] Test 7: Python-Test (ohne Mocks): GIVEN `cloud_low` nur morgens und nur das Abend-Briefing in `outlook_reports` WHEN Karte und Erstanlage berechnet THEN kein Ausblick-Haken; mit führendem Briefing in `outlook_reports` Haken gesetzt.
- [ ] Test 8: `aenderungsfaelle_an_der_tabelle_3020.test.ts` läuft ohne die Ausnahme `cloud_low` grün.
- [ ] Test 9: Testtabelle `rework_3020_testtabelle.md` (G44, `D-trip_tabellen-nur_ein_bericht_*`) ist auf erledigt nachgezogen (doc-compliance-test).

## Acceptance Criteria

- **AC-1:** Given ein Trip, in dem eine Größe nur im Morgen-Briefing oder nur im Abend-Briefing geführt wird (`enabled` aus, Bericht-Flag an) / When der Nutzer den Reiter Wetter öffnet / Then erscheint diese Größe dort als gewählt, so wie die Mail sie führt.
  - Test: Nutzer öffnet den Reiter Wetter eines Trips mit nur-morgens- bzw. nur-abends-Größe und sieht sie als gewählt.

- **AC-2:** Given eine gewählte Größe mit „nur morgens“ oder „nur abends“ / When der Nutzer „−“ klickt und speichert / Then fehlt die Größe im Morgen- und im Abend-Briefing aller Kanäle (E-Mail, Telegram, SMS, Premium-SMS), und der Mail-Pfad bleibt unverändert.
  - Test: Nach „−“ und Speichern enthalten beide Briefings die Größe nicht; zwei verschiedene Nutzer, jeder sieht nur seine eigene Änderung.

- **AC-3:** Given eine zuvor abgewählte Größe, die vorher „nur morgens“ oder „nur abends“ war / When der Nutzer sie wieder anwählt / Then steht sie in beiden Briefings und trägt keine Einschränkung mehr.
  - Test: Nach „+“ und Speichern führen Morgen- und Abend-Briefing die Größe; die Zeile ist nicht mehr gekennzeichnet.

- **AC-4:** Given Größen, die der Nutzer nicht anfasst, mit gesetzten Bericht-Flags / When der Nutzer andere Einstellungen ändert und speichert / Then behalten diese Größen ihre Flags und alle übrigen Felder unverändert.
  - Test: Speichern ohne Änderung an der Größe lässt den gespeicherten Eintrag bytegleich; zwei Nutzer, keine Vermischung der Daten.

- **AC-5:** Given ein Trip mit einer nur-morgens- und einer nur-abends-Größe / When der Nutzer die Karte „Was steht wo“ ansieht / Then trägt die Zeile die Kennzeichnung „nur morgens“ bzw. „nur abends“ (Englisch „morning only“ bzw. „evening only“); im Ortsvergleich erscheint keine solche Kennzeichnung.
  - Test: Karte im Trip zeigt je Zeile die Marke in DE und EN; Karte im Vergleich zeigt keine.

- **AC-6:** Given eine gekennzeichnete Zeile in der Karte / When der Nutzer die Größe abwählt / Then verschwindet die Kennzeichnung und die Zeile verschwindet aus den Briefings.
  - Test: Nach „−“ ist die Marke weg, die Karte folgt dem Editorstand.

- **AC-7:** Given eine nur morgens geführte Größe wie `cloud_low`, bei der nur das Abend-Briefing den 3-Tages-Ausblick führt / When die Karte angezeigt oder der Trip neu angelegt wird / Then ist der Ausblick-Haken der Zeile nur gesetzt, wenn ein Briefing aus den Ausblick-Berichten die Größe führt, in Anzeige und Erstanlage gleich.
  - Test: Karte und frisch angelegter Trip zeigen für `cloud_low` keinen Haken im Ausblick; führt ein Ausblick-Briefing die Größe, ist der Haken gesetzt.

## Definition of Done

- AC-1 bis AC-7 durch die im Test Plan genannten Tests belegt, ohne Mocks, mit zwei Nutzern wo Daten bewegt werden.
- Die drei `todo`-Fälle „#3020 G44“ in `was_steht_wo_karte.test.ts` ohne `todo` und unabgeschwächt grün; die Ausnahme `cloud_low` in `aenderungsfaelle_an_der_tabelle_3020.test.ts` entfernt.
- Felderhalt-Tests (Frontend und Go) grün; Testtabelle `rework_3020_testtabelle.md` (G44) nachgezogen; `api_contract.md` beschreibt das neue Zeilenfeld.
- Staging-Prüfung DE und EN bestanden, ausgeliefert, Issue #3364 geschlossen.

## Known Limitations

- Eine Einschränkung auf „nur morgens/abends“ lässt sich in der Tabelle weiterhin nicht bedienen (feat_3122 Z.351); die Kennzeichnung zeigt nur den Bestand.
- Wiederanwahl hebt eine frühere Einschränkung auf (bewusst, keine unsichtbare Einschränkung).
- Bestandsmessung, wie viele Prod-Trips Flags tragen, erfolgt lesend in Phase 6/7 (`sudo -n -u claude-gregor`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt ADR-0124 (Tabelle „Was steht wo“) und ADR-0050 Regel 3 (Bericht-Flags) um und hebt keine Entscheidung auf; das Zeilenfeld ist eine additive Erweiterung der Karten-Antwort.

## Changelog

- 2026-11-26: Initial spec created (Issue #3364, Epic #3122)
