---
entity_id: feat_3031_inhalt_je_kanal_listen
type: feature
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: feature-3031-inhalt-je-kanal-listen
tags: [einstellungen-neu, wetter-reiter, kanal-inhalt, epic-2795, epic-2791]
---

# Inhalt je Kanal A1 – Listen je Kanal im Reiter Wetter

## Approval

- [ ] Approved

## Purpose

Im Reiter Wetter (Trip und Ortsvergleich, ein gemeinsamer Code) entsteht die Karte "Inhalt je Kanal und Fläche" nach Mockup Fassung 3. Je Kanal (E-Mail, Telegram, SMS, Premium-SMS) gibt es eine Liste der Wetter-Metriken, in der Nutzer Reihenfolge, an/aus und Roh/Einfach festlegen. Heute ist diese Bedienung nur versteckt im Übergangsblock des Reiters Zustellung erreichbar; sie zieht in den fachlich richtigen Reiter um.

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/KanalInhaltKarte.svelte` (neu)
- **Identifier:** `KanalInhaltKarte` (Organismus), Zeilenmodell `KanalZeile` in `kanalInhalt.ts`

> **Schicht:** Frontend (SvelteKit). Go-API und Python-Core werden nicht geändert; sie sind Voraussetzung (#3039) bzw. Leser des bestehenden Feldes `display_config.channel_layouts`.

> **Trip/Ortsvergleich-Teilung:** Ein Code, Parameter `context="route"|"vergleich"`. Nur die Adapter (Laden/Speichern) unterscheiden sich; die Karte kennt nur `KanalZeile[]` je Kanal. Keine einseitige Neuanlage.
>
> **Mandantentrennung:** Es werden Nutzerdaten gespeichert; `user_id` kommt aus dem Auth-Kontext, es gibt keinen Fallback auf "default". Test mit zwei verschiedenen Nutzern.
>
> **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS sind alle benannt. Premium-SMS hat bis S9 (ADR-0049) keine eigene Liste und zeigt die SMS-Liste schreibgeschützt.

## Definition of Done

- AC-1 bis AC-13 erfüllt; alle Tests aus der Abdeckungstabelle grün, die Renderer-Wirkung (Tests 2b, 9, 14) für Trip und Ortsvergleich nachgewiesen.
- #3039 ist vor der Auslieferung dieser Scheibe in Produktion; ohne das wird nicht ausgeliefert.
- Bestandsdaten bleiben erhalten: Vorher/Nachher-Stand aller vier Kanallisten nach Änderung eines Kanals identisch bis auf die Änderung (Trip und Vergleich).
- Abschnitt „Layout je Kanal“ ist aus dem Übergangsblock des Reiters Zustellung entfernt, angepasste Bestandstests grün.
- Elementliste-Besitzer `kanal-inhalt` auf echten Abgleich umgestellt.
- Soll/Ist-Bild (Mockup gegen Staging, Trip und Ortsvergleich) mit zugeordneten Abweichungen an Henning gegangen.
- #3031 erst nach Prod-Selftest Exit 0 geschlossen.

## Estimated Scope

- **LoC:** ca. +700/-80 inklusive Tests (Karte ~200, Modell/Adapter ~120, Beispiele ~60, Speicherung ~100, Tests ~300)
- **Files:** 10-14
- **Effort:** high

**Begründung der Überschreitung des üblichen LoC-Limits:** Die Karte ist ein untrennbarer Block (Liste, Zeilenmodell, Adapter und Speicherung funktionieren nur zusammen; eine halbe Karte würde Daten verlieren oder zwei Bediener desselben Feldes zugleich liefern). Rund 300 LoC sind Tests (Pflicht: Zwei-Nutzer-Test, Wirkung am Renderer). Der Umzug aus dem Übergangsblock wird, wo möglich, als eigener Commit getrennt von der Karte geliefert. Der datenmodellseitige Teil (Vergleich) ist bereits in #3039 ausgelagert, sonst läge der Umfang über 1.000 LoC.

## Scope

### In Scope
Segment E-Mail · Telegram · SMS · Premium-SMS (schreibgeschützt). Pro Liste: Umsortieren, Schalter an/aus, Roh/Einfach mit Beispiel, feste Zeile "Amtliche Warnungen". Entfernen des Abschnitts `layout_kanal` aus dem Übergangsblock des Reiters Zustellung.

### Out of Scope (eigene Issues)
- Schnittlinie, Budget, Legende: #3032 (A2)
- Weitere Einstellungen: #3033 (A3)
- Ausblick: #3034 (A4)
- Stundenverlauf: #3035 (A5)
- Rest des Übergangsblocks: #3036 (A6)
- Eigene Premium-SMS-Liste: S9 / ADR-0049
- Datenmodell und Renderer für den Vergleich: #3039 (Voraussetzung)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/organisms/wetter-tab/KanalInhaltKarte.svelte | CREATE | Organismus: Segmented, SortableList + DragHandle, Zeile mit Name, Roh/Einfach-Segmented mit Beispiel, Switch, feste Warnungs-Zeile |
| frontend/src/lib/components/organisms/wetter-tab/kanalInhalt.ts | CREATE | Zeilenmodell `KanalZeile{id, enabled, format}`, Normalisierung, Adapter Trip/Vergleich |
| frontend/src/lib/components/organisms/wetter-tab/kanalInhaltBeispiele.ts | CREATE | Beispielwerte DE/EN je Metrik (aus Mockup `const EX`) |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | Karte zwischen WarnungenRadarKarte und AnpassenKarte einhängen |
| frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts | MODIFY | voller `channel_layouts`-Stand beim Speichern (Trip und Vergleich), Vergleich zusätzlich `channel_active_metrics`; Signatur erweitert |
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts | MODIFY | Kanal-Layouts laden |
| frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts | MODIFY | Zustand für Kanal-Layouts |
| frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts | REUSE | `startChannelOverride`, `splitChannelMetricsForDisplay`, `mergeAllChannelLayoutsForSave` |
| frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts | MODIFY | `layout_kanal` aus ZUSTELLUNGS_SECTIONS entfernen |
| frontend/src/lib/i18n/messages/de/wetter.json, en/wetter.json | MODIFY | Untertitel, Kopfzeile, Hinweise, "folgt der SMS-Liste", Warnungs-Zeilen |
| frontend/src/lib/components/bausteine_waechter_regeln.ts | MODIFY | neue Dateien in SEITEN_SCOPE (ADR-0112) |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | Besitzer `kanal-inhalt` von "noch nicht gebaut" auf echten Abgleich |
| frontend Bestandstests (s3a2794_bereich_filter, s3b2795_zustellung_struktur AC-30, weatherMetricsTabSharing, compare_layout_tab_dissolution, wetter_metriken_versand_panel_paritaet) | MODIFY | an Umzug anpassen |
| frontend Tests (neu) | CREATE | Zeilenmodell, Adapter, Speichern, Karte, zwei Nutzer, Beispiele gegen Katalog |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3039 (A1-Vorlauf) | Issue / Voraussetzung | Vergleich bekommt `display_config.channel_layouts` wie der Trip, inklusive Resolver und Renderer-Wirkung. Muss VOR Auslieferung dieser Scheibe live sein, sonst geht die Karte beim Vergleich mit halber Parität live. Die Spec darf vorher geschrieben werden. |
| `GET /api/metrics`, `GET /api/compare/metrics` | API | Katalog: `col_label`, `sms_code`, `has_friendly_format`, `format_modes`, `default_format_mode` |
| Go-Merge `internal/handler/config_merge.go` | Modul | Read-Modify-Write je Top-Level-Key; `channel_layouts` wird als Ganzes ersetzt |
| `src/app/loader.py`, Kanal-Renderer (`channel_layout.py`, `trip_report.py`, `sms_trip.py`, Vergleichs-Renderer) | Modul | Leser von `channel_layouts` (Wirkungsnachweis) |
| `shared/dnd/SortableList.svelte`, `DragHandle.svelte` | Baustein | einziger Sortier-Baustein (ADR-0024) |
| `atoms/Segmented`, `Switch`, `Card`, `Eyebrow`, `molecules/Einstellungszeile` | Bausteine | ADR-0112 |
| Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, `elementliste.json` (kanal-inhalt) | Soll-Bild | Abgleich |
| ADR-0049, ADR-0050/0059, ADR-0095, ADR-0104, ADR-0112 | ADR | Premium-SMS, Teilmengen-Regel, Kanal-Parität, i18n, Bausteine |
| Downstream: #3032 (A2), #3036 (A6) | Issues | bauen auf derselben Karte bzw. räumen den Rest |

## Implementation Details

Techn. Ansatz (Designentscheidungen 1-8 aus der Analyse, unverändert übernommen):

1. **Ein Zeilenmodell:** Die Karte kennt nur `KanalZeile[]` je Kanal. Trip- und Vergleichs-Adapter lesen und schreiben dieselbe Struktur `channel_layouts` (`{kanal: [{metric_id, enabled, use_friendly_format}]}`).
2. **Speichern:** immer der volle Stand aller Kanäle (Read-Modify-Write; Go ersetzt den Key ganz, ein Teilstand würde andere Kanäle löschen). Trip über die bestehende 700-ms-Schlange (PUT weather-config), Vergleich über die bestehende If-Match-Schlange (412 führt zu Neuladen). Der Vergleich schreibt zusätzlich `channel_active_metrics` (nur eingeschaltete IDs, geordnet) als Übergang. Meldung nur bei geänderter Signatur.
3. **Aus ist ein Zustand:** eine ausgeschaltete Zeile bleibt mit ihrer Position in der Liste (`enabled:false`); der Renderer zeigt sie nicht.
4. **Neue Wetter-Metrik:** erscheint in bestehenden Kanallisten eingeschaltet am Ende (Normalisierung beim Laden und Speichern). Abwahl im Wetter-Reiter wirkt in allen Kanälen (Teilmengen-Regel ADR-0050 R3): die Liste enthält nur Metriken, die der Wetter-Reiter eingeschaltet hat.
5. **Premium-SMS:** Segment zeigt die SMS-Liste schreibgeschützt mit Hinweis "folgt der SMS-Liste", bis S9/ADR-0049.
6. **Amtliche Warnungen:** feste Anzeigezeile, nicht sortierbar, kein Datenfeld. E-Mail und Telegram: ganz oben; SMS und Premium-SMS: am Ende.
7. **Name:** Katalog `col_label | sms_code` (Temperatur: "Temperatur (Temp | T)", nicht das `D` aus dem Mockup).
8. **Übergangsblock:** `layout_kanal` wird in dieser Scheibe aus dem Übergangsblock des Reiters Zustellung entfernt (Bedienelement zieht um, nichts geht verloren; schließt den Stale-Payload-Weg zweier Bediener desselben Feldes). A6 räumt den Rest.
9. **Beispielwerte** (Roh vs. Einfach) kommen statisch aus `kanalInhaltBeispiele.ts`, DE/EN; ein Test stellt sicher, dass jede Metrik mit `has_friendly_format` einen Eintrag hat.
10. **Texte** ausschließlich über die i18n-Kataloge (ADR-0104); Protokoll-Token (`sms_code`, `col_label`-Kürzel) werden nicht übersetzt.
11. **Daten-Schema-Regel:** Bestandsdaten bleiben erhalten (Read-Modify-Write mit Merge, nie Replace eines Teilstands); Pre-Snapshot-Hook beachten.

### Technische Präzisierungen aus TDD RED (2026-11-15, keine AC-Änderung)

- **Roh/Einfach-Wahl hängt an `format_modes`** (mehr als ein Modus), nicht an `has_friendly_format`: Der Katalog führt Böen, Wind und Niederschlag mit `has_friendly_format: false`, aber `format_modes` `raw`+`simplified`. Ohne diese Präzisierung wären AC-4/Test 9 nicht erfüllbar.
- **Alter Zustellungs-Speicherer schreibt keine Kanallisten mehr:** `channel_active_metrics` aus `WETTER_DISPLAY` in `baueWetterMetrikenNutzlast` und `channel_layouts` aus `WETTER_DISPLAY_KEYS` entfernen, sonst überschreibt er bei jeder Zustellungs-Geste den Stand der Karte mit seiner beim Laden eingefrorenen Kopie (Stale-Payload, Designentscheidung 8 zu Ende gedacht). Bestandstests wie `channelPayloadAllChannels`, `feld_erhalt_ohne_ausnahme`, `wetter_metriken_*` sind dann anzupassen.
- **`layout_kanal` aus allen Bereichen** von `weatherMetricsTabSections` entfernen (wetter, zustellung, alles); die Anlege-Assistenten zeigen die Karte über WetterTab.
- **`order` beim Schreiben** = Listenindex (oder weglassen), nie alte `order`-Werte mitnehmen, sonst wirkt Umsortieren nicht im Renderer.
- **Telegram Böen „Einfach"** hat keine eigene Darstellung (zeigt die Zahl); Test 9 prüft Telegram Roh = Zahl, Mail Einfach = Ampelpunkt.
- Erwartete Schnittstellen (Modul `kanalInhalt.ts`, `kanalInhaltBeispiele.ts`, Karten-Props, `data-testid`-Anker, i18n-Schlüssel `wetter.kanal_inhalt.*`, Speicherer-Option `kanalFormatFuer`) stehen in den Kopfkommentaren der RED-Tests `kanal_inhalt_3031_*.test.ts`.
- **Zwei angepasste Bestandstests liegen nur im Arbeitsordner** (vom Commit-Gate bis zur Implementierung blockiert): `s3a2794_bereich_filter.test.ts` und `weatherMetricsTabSharing.test.ts` (erwarten kein `layout_kanal` mehr). Mit der Implementierung committen.
- E2E-Specs der alten Layout-Oberfläche sind beim Umbau anzupassen: `layout-tab-route`, `s3a2794-zustellung-inventar-speicherweg`, `compare-uebersicht-kanal-bedienung.staging`, `compare-hourly-metric-order`, `kurzform-gefuehlte-temperatur-kind-mitnahme`, `kanal-grenzen-und-hinweise.staging`, `kuerzel-marken-sichtbar.staging`, `wetter-metriken-vorschau-entfernt.staging`.

## Expected Behavior

- **Input:** Nutzer öffnet im Trip bzw. Ortsvergleich den Reiter Wetter, wählt einen Kanal im Segment und sortiert, schaltet Zeilen an/aus oder stellt Roh/Einfach um.
- **Output:** Die Liste spiegelt die Änderung sofort; nach dem Speichern liefern die Kanal-Renderer genau diese Reihenfolge, Auswahl und Darstellung. Nach Neuladen steht derselbe Stand da.
- **Side effects:** Schreibt `display_config.channel_layouts` (voller Stand) und im Vergleich zusätzlich `channel_active_metrics`; der Abschnitt `layout_kanal` verschwindet aus dem Reiter Zustellung.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Wetter-Metriken Temperatur, Böen, Regen / WHEN das Zeilenmodell für einen Kanal ohne Eintrag normalisiert wird / THEN alle Metriken eingeschaltet in Reihenfolge der Wetter-Liste.
- [ ] Test 2: GIVEN gespeicherte Telegram-Liste ohne die neue Metrik "Luftdruck" / WHEN geladen / THEN Luftdruck steht eingeschaltet am Ende; eine im Wetter-Reiter abgewählte Metrik fehlt in allen Kanälen.
- [ ] Test 2b (Wirkung am Renderer, AC-8): GIVEN Trip, Metrik "Luftdruck" im Wetter-Reiter neu eingeschaltet, Kanallisten ohne Eintrag dafür / WHEN gespeichert und Report je Kanal gerendert / THEN erscheint Luftdruck in Mail, Telegram und SMS; nach Abwahl im Wetter-Reiter erscheint er in keinem Kanal.
- [ ] Test 3: GIVEN Karte mit vier Kanälen / WHEN eine Zeile in E-Mail umsortiert wird / THEN speichert der Speicherer alle vier Kanäle (voller `channel_layouts`-Stand), keiner geht verloren (Trip und Vergleich).
- [ ] Test 4: GIVEN Vergleich / WHEN gespeichert / THEN `channel_active_metrics` enthält nur eingeschaltete IDs in Listenreihenfolge; bei 412 wird neu geladen und der Stand nicht überschrieben.
- [ ] Test 5: GIVEN Karte, Segment Premium-SMS / WHEN geöffnet / THEN SMS-Liste mit Hinweis, Schalter, Griff und Roh/Einfach sind deaktiviert.
- [ ] Test 6: GIVEN Karte, Segmente E-Mail, Telegram, SMS und Premium-SMS / WHEN gerendert / THEN "Amtliche Warnungen" steht bei E-Mail und Telegram oben, bei SMS und Premium-SMS am Ende, hat weder Griff noch Schalter und ist nicht ziehbar.
- [ ] Test 7: GIVEN Katalog / WHEN Name gebildet / THEN "Temperatur (Temp | T)"; ohne `has_friendly_format` kein Roh/Einfach-Umschalter; Beispiele je Metrik in DE und EN vorhanden.
- [ ] Test 8: GIVEN zwei verschiedene Nutzer mit eigenen Trips bzw. Ortsvergleichen (beide Speicherwege) / WHEN Nutzer A speichert / THEN bleibt der Stand von Nutzer B unverändert (kein Fallback auf "default").
- [ ] Test 9 (Wirkung am Renderer, Trip und Vergleich): GIVEN Telegram Roh für Böen, E-Mail Einfach für Böen / WHEN Report gerendert / THEN Telegram zeigt die Zahl, die Mail den Ampelpunkt.
- [ ] Test 10: GIVEN Reiter Zustellung / WHEN Übergangsblock gerendert / THEN kein Abschnitt `layout_kanal` mehr; Bestandstests (AC-30 und Sharing-Tests) an Umzug angepasst und grün.
- [ ] Test 12 (AC-12): GIVEN Karte mit Sprache DE und mit Sprache EN / WHEN gerendert / THEN Untertitel, Kopfzeile, Hinweise, Warnungs-Zeilen, „folgt der SMS-Liste“ und Beispiele erscheinen aus dem jeweiligen Katalog (`wetter.json` de/en, gleiche Schlüssel in beiden), das Kürzel `T` bleibt in beiden Sprachen `T`; der Hardcode-Wächter (`hardcode_allowlist.json`) meldet für die neuen Dateien nichts.
- [ ] Test 13 (AC-2): GIVEN Trip bzw. Ortsvergleich mit gespeicherten Listen für E-Mail und Telegram / WHEN in Telegram eine Zeile per Griff an eine andere Stelle gezogen, gespeichert und die Seite neu geladen wird / THEN zeigt Telegram die neue Reihenfolge, die E-Mail-Liste ist Zeile für Zeile unverändert (Vorher/Nachher-Vergleich des geladenen Stands).
- [ ] Test 14 (Wirkung am Renderer, AC-3, Trip und Vergleich): GIVEN Metrik "Böen" in der SMS-Liste ausgeschaltet, in E-Mail und Telegram eingeschaltet / WHEN gespeichert und Report je Kanal gerendert / THEN fehlt Böen in der SMS, steht in Mail und Telegram; in der Karte steht die SMS-Zeile weiterhin an ihrer Position (ausgeschaltet).
- [ ] Test 15 (AC-13, manuell in /e2e-verify): GIVEN die Karte auf Staging, Trip und Ortsvergleich / WHEN Mockup-Bild und Staging-Bild desselben Zustands gegenübergestellt werden / THEN Abweichungsliste mit Zuordnung je Abweichung (Folge-Issue oder Entscheidung), Bild an Henning.
- [ ] Test 11 (Architektur-Wächter, kein Verhaltensnachweis): GIVEN die neuen Dateien der Karte / WHEN die bestehenden Wächtertests `no_native_draggable_guard.test.ts` und die Baustein-Wächter (`bausteine_waechter_regeln.ts`) laufen / THEN Sortieren nur über SortableList + DragHandle, kein natives draggable, Dateien liegen im erlaubten Scope. Das Verhalten (Umsortieren, Schalter, Roh/Einfach) belegen die Tests 1–10.

### Abdeckung AC → Test

| AC | Tests |
|---|---|
| AC-1 | 1, 7 |
| AC-2 | 3, 13 |
| AC-3 | 14 |
| AC-4 | 7, 9 |
| AC-5 | 6 |
| AC-6 | 5 |
| AC-7 | 3, 4 |
| AC-8 | 2, 2b |
| AC-9 | 3, 9, 13, 14 (je Trip und Vergleich) |
| AC-10 | 8 (Trip und Vergleich) |
| AC-11 | 10 |
| AC-12 | 12 |
| AC-13 | 15 |

## Acceptance Criteria

- **AC-1:** Given ein Trip mit mehreren eingeschalteten Wetter-Metriken / When der Nutzer im Reiter Wetter die Karte "Inhalt je Kanal und Fläche" öffnet / Then sieht er ein Segment E-Mail · Telegram · SMS · Premium-SMS und für den gewählten Kanal eine Liste der Metriken mit Namen "Spaltenname (Kürzel)", z. B. "Temperatur (Temp | T)".
  - Test: Nutzer öffnet den Reiter und liest die Liste je Kanal; Namen stimmen mit Katalog überein.

- **AC-2:** Given die Liste eines Kanals / When der Nutzer eine Zeile per Griff an eine andere Stelle zieht / Then ändert sich die Reihenfolge nur in diesem Kanal, und nach Neuladen der Seite steht dieselbe Reihenfolge da.
  - Test: Umsortieren in Telegram; E-Mail-Reihenfolge unverändert; Neuladen zeigt gespeicherten Stand.

- **AC-3:** Given eine eingeschaltete Zeile in der Liste eines Kanals / When der Nutzer den Schalter ausschaltet / Then bleibt die Zeile an ihrer Position stehen, erscheint aber in diesem Kanal nicht mehr im Bericht und in anderen Kanälen weiterhin.
  - Test: Schalter aus in SMS; gerenderte SMS ohne Metrik, E-Mail mit Metrik.

- **AC-4:** Given eine Metrik mit Einfach-Darstellung / When der Nutzer bei einem Kanal Roh oder Einfach wählt / Then zeigt die Zeile ein Beispiel der gewählten Darstellung (in der Sprache des Nutzers), und der Bericht dieses Kanals nutzt genau diese Darstellung, während andere Kanäle ihre eigene behalten.
  - Test: Böen Roh in Telegram und Einfach in E-Mail; Telegram zeigt die Zahl, die Mail den Ampelpunkt, bei Trip und Ortsvergleich.

- **AC-5:** Given die Karte in einem beliebigen Kanal / When sie angezeigt wird / Then steht "Amtliche Warnungen" als feste Zeile ohne Griff und ohne Schalter, bei E-Mail und Telegram ganz oben, bei SMS und Premium-SMS am Ende der Liste.
  - Test: Zeilenposition je Kanal prüfen; Zeile nicht ziehbar.

- **AC-6:** Given das Segment Premium-SMS / When der Nutzer es wählt / Then sieht er die SMS-Liste mit dem Hinweis "folgt der SMS-Liste", und Griff, Schalter und Roh/Einfach lassen sich nicht bedienen.
  - Test: Bedienelemente im Segment Premium-SMS deaktiviert; SMS-Liste unverändert.

- **AC-7:** Given ein Nutzer ändert die Liste eines einzelnen Kanals / When gespeichert wird / Then bleiben die Listen aller anderen Kanäle und alle übrigen Anzeige-Einstellungen unverändert erhalten (kein Datenverlust), im Trip wie im Ortsvergleich.
  - Test: Vorher-/Nachher-Stand aller vier Kanäle nach Änderung in einem Kanal; Vergleich mit If-Match, bei 412 Neuladen ohne Überschreiben.

- **AC-8:** Given eine Wetter-Metrik wird im Reiter Wetter neu eingeschaltet bzw. abgewählt / When der Nutzer die Kanallisten öffnet / Then steht die neue Metrik in jeder bestehenden Kanalliste eingeschaltet am Ende, und eine abgewählte Metrik fehlt in allen Kanallisten.
  - Test: Metrik im Wetter-Reiter ein- und ausschalten, Kanallisten und Bericht prüfen.

- **AC-9:** Given Trip und Ortsvergleich / When der Nutzer die Karte jeweils bedient / Then funktionieren beide identisch (derselbe Code, gleiche Bedienung), und die Änderungen des Vergleichs wirken in dessen Mail, Telegram und SMS (setzt #3039 voraus).
  - Test: dieselbe Bedienfolge in beiden Kontexten; Wirkung am Renderer je Kontext.

- **AC-10:** Given zwei verschiedene Nutzer mit eigenen Trips bzw. Ortsvergleichen / When Nutzer A seine Kanallisten ändert und speichert / Then bleibt der Stand von Nutzer B unverändert, und gespeichert wird immer unter der echten Nutzer-Kennung.
  - Test: Zwei-Nutzer-Test über beide Speicherwege.

- **AC-11:** Given der Reiter Zustellung / When der Nutzer ihn öffnet / Then enthält der Übergangsblock den Abschnitt "Layout je Kanal" nicht mehr, und alle zugehörigen Einstellungen sind ausschließlich im Reiter Wetter bedienbar.
  - Test: Reiter Zustellung öffnen; Abschnitt fehlt; gleiche Einstellung im Wetter-Reiter vorhanden.

- **AC-12:** Given die Oberfläche in Deutsch und in Englisch / When der Nutzer die Karte ansieht / Then erscheinen alle Texte (Untertitel, Hinweise, Warnungs-Zeilen, Beispiele) in der gewählten Sprache, Protokoll-Kürzel (z. B. `T`) bleiben unverändert.
  - Test: Sprache wechseln und Karte prüfen; kein hartcodierter Text.

- **AC-13:** Given die ausgelieferte Karte auf Staging / When Soll-Bild (Mockup Fassung 3, Karte "Inhalt je Kanal und Fläche") und Ist-Bild nebeneinander verglichen werden / Then ist jede Abweichung benannt und einem Folge-Issue (#3032-#3036) oder einer bewussten Entscheidung zugeordnet, und das Bild geht an Henning.
  - Test: Screenshot-Gegenüberstellung Mockup gegen Staging, jeweils Trip und Ortsvergleich, mit Abweichungsliste.

## Known Limitations

- Schnittlinie, Budget und Legende (#3032), Weitere Einstellungen (#3033), Ausblick (#3034), Stundenverlauf (#3035) und der Rest des Übergangsblocks (#3036) fehlen in dieser Scheibe bewusst.
- Premium-SMS ist bis S9 nicht eigenständig bearbeitbar.
- Der Vergleich wirkt erst vollständig, wenn #3039 live ist; Auslieferung davor ist ausgeschlossen.
- `channel_active_metrics` bleibt als Übergangsfeld bestehen, bis alle Leser auf `channel_layouts` umgestellt sind.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (folgt ADR-0049, ADR-0050/0059, ADR-0095, ADR-0104, ADR-0112, ADR-0024)
- **Rationale:** Die Scheibe setzt bestehende Entscheidungen um (Kanal-Parität, Teilmengen-Regel, Bausteine, Sortier-Baustein, i18n). Das Datenmodell des Vergleichs wurde bewusst an den Trip angeglichen (#3039) statt ein Parallelfeld einzuführen, damit pro Zeile nur eine Wahrheit existiert.

## Changelog

- 2026-11-15: Initial spec created
- 2026-11-15: Technische Präzisierungen aus TDD RED ergänzt
