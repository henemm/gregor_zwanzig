# Zählstellen #3389 — Ist gegen Soll (Spec rework_3389_tote_exporte.md v1.1)

Gemessen am Arbeitsstand nach der Löschung (GREEN, vor dem Commit).

| Zählstelle | Soll (Spec „Neu“) | Ist | Messung | Ergebnis |
|---|---|---|---|---|
| `context_herkunft_zweige_eingefroren.test.ts` `EINGEFROREN_SOLL_ANZAHL` | 8 | 8 | Literal im Test; Einträge im Array `EINGEFROREN` gezählt: 8 | gleich |
| Einträge `versandVergleichSpeicherung.ts:236`, `weather-metrics-tab/weatherMetricsCompareSave.ts:364` | entfernt | entfernt | grep im Array: 0 Treffer | gleich |
| `ac2_endbilanz_deckt_alle_47_ab.test.ts` Positiv-Kontrolle | 8 | 8 | Literal und Testtitel „genau 8 Eintraege“ | gleich |
| ac2 Spec-Kategorien FACHLICH / DARSTELLUNG / HERKUNFT / Summe | 5 / 2 / 1 / 8 | 5 / 2 / 1 / 8 | Tabellenzeilen je `### <Kategorie> (`-Abschnitt in `rework_2276_s6h_ac2_endbilanz.md` | gleich |
| `rework_2276_s6h_ac2_endbilanz.md` Anhang-Überschrift, HERKUNFT-Überschrift, Summenzeile | „alle 8“, „HERKUNFT (1 …)“, „#3389: 5 / 2 / 1 = 8“ | wie Soll | Textstand | gleich |
| `fallliste_editor.json` Fall `D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend` `test` | `editor_standard_gleich_ausgabe_3020.test.ts::frontend_seite_orte_vergleichstabelle_gespeichert gespeichert_kanal_totalschnitt` | wie Soll | JSON gelesen | gleich |
| Fallliste: Status des Falls / Anzahl `ausnahme` | `ausnahme` / 14 | `ausnahme` / 14 | JSON gezählt | gleich |
| Fallliste: Verweise auf Löschkandidaten-Dateien | 0 | 0 | JSON-Suche | gleich |
| `totcode_rueckbau_speicherweg.test.ts` Positivkontrolle Versand / Weather | `hydrateVersandFieldsFromPreset` / `hydrateWeatherMetricsFromPreset` | wie Soll | Liste `speicherModule` | gleich |
| `feat3298_vergleich_ohne_altfelder.test.ts` dynamischer Import des Weather-Moduls | unverändert | unverändert | Fall „Lese-Naht channel_active_metrics ist entfernt“ unverändert, grün | gleich |
| `waisen_waechter.test.ts` `BEKANNTE_WAISEN` / `OBERGRENZE_WAISEN` | leer / 0 | leer / 0 | Datei unverändert gegenüber `origin/main` | gleich |
| `bausteine_waechter_regeln.ts` `BESTAND_OBERGRENZE` | 162 | 162 | Datei unverändert | gleich |
| `ein_katalog_ausnahmen.json` `hoechststand` / `HOECHSTSTAND` | 421 / 421 | 421 / 421 | Dateien unverändert | gleich |
| `.github/workflows/ci.yml` `E2E_MIN_SPECS` / `E2E_MIN_EXECUTED_HAUPT` / `_PWA` | 85 / unverändert | 85 / 757 / 65 | `git diff --quiet origin/main -- frontend/e2e .github .claude/hooks` Exit 0 | gleich |
| `rework_3020_umfang.ts` `BLEIBT` (`weatherMetricsCompareSave.ts`), `RESTBESTAND_ANZAHL`, `SPEC_ANZAHL`, `DURCH_WAISEN_ENTFERNT` | unverändert (19 / 42 / 23) | 19 / 42 / 23, `BLEIBT` enthält das Modul | Datei unverändert | gleich |
| `rework_3020_rote_liste.ts` | unverändert | unverändert | Datei unverändert | gleich |
| `trip_pfad_altfeld_loeschnachweis_3297.test.ts` `ERHALTEN`, `ERHALTEN_3383` | unverändert | unverändert | nur der Block `#3389` kam dazu | gleich |
| Wächter `#3389`: Namen / Testdateien | 23 / 21 (+ Prüfstand) | 23 / 21 (+ Prüfstand) | Test „Löschliste #3389 hat genau 23 Namen …“ grün | gleich |
| Exportmenge Versand / Weather | 1 / 4 | 1 / 4 | Wächter-Fall „Exportmenge“ grün | gleich |

Alle in der Spec geführten Zählstellen stimmen mit dem Soll überein.

## ABWEICHUNG: Zählstelle außerhalb der Spec (nicht angepasst, gemeldet)

| Zählstelle | Spec | Ist im Code | Messwert nach Löschung |
|---|---|---|---|
| `frontend/src/lib/components/shared/__tests__/endbilanz_summenzeile_stimmt.test.ts:57` `assert.equal(herkunft.zeilen.length, 3)` (Testtitel „HERKUNFT 3 seit #3297“, Z. 55/63) | nicht geführt | 3 (fest) | 1 → Test rot |

Folgerichtiger Wert wäre 1 (gleich der Spec-Zählstelle ac2 HERKUNFT 1). Nach Auftrag nicht
eigenmächtig geändert; braucht einen Spec-Nachtrag.

### Erledigt mit Spec v1.2 (Nachtrag)

| Zählstelle | Soll (v1.2) | Ist | Ergebnis |
|---|---|---|---|
| `endbilanz_summenzeile_stimmt.test.ts:57` `herkunft.zeilen.length` | 1 | 1 | gleich |
| Testtitel | „… (HERKUNFT 1 seit #3389)“ | wie Soll | gleich |
| Kommentar | „#3389: 3 → 1 (die beiden …SpeicherungAktiv-Weichen mit den toten Exporten gelöscht)“ | wie Soll | gleich |

Folge der Titeländerung: der Beleg `E023` in `docs/specs/modules/rework_3020_testtabelle.md`
nannte den alten Titel und wurde wie `E017`/`E018` auf den neuen Titel nachgezogen (keine
Zahl der `rework_3020_*`-Ratschen ändert sich). Gesamte Frontend-Suite danach: 0 rot.

## Nicht in der Spec geführte Belegstelle (gemeldet)

`docs/specs/modules/rework_3020_testtabelle.md` (vom lebenden `rework_3020_rueckbau_waechter.test.ts`
gelesen) führte drei Belege auf Testtitel bzw. -dateien, die diese Scheibe laut Spec ändert:
`G38` (Beleg auf die gelöschte Datei `wetter_metriken_nutzlast_verliert_keine_daten.test.ts`),
`E017`/`E018` (Titel der ac2-Endbilanz mit den alten Zahlen 10 bzw. 5/2/3). Das Kontext-Dokument
hatte die Datei als „kein Verweis“ eingestuft. Nachgezogen wie bei #3385: `E017`/`E018` auf die
neuen Titel (8 bzw. 5/2/1), `G38` auf denselben Ersatz-Test wie die Fallliste. Keine Zahl der
`rework_3020_*`-Ratschen ändert sich.
