---
entity_id: rework_3385_waisen_s3
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
workflow: rework-3385-waisen-s3
version: "1.3"
tags: [frontend, waisen, ratsche, loeschen, "#3385", "#3366", "#3122", "#3384", "#3389"]
---

# Rework #3385: Waisen-Scheibe S3 (versand-tab) und Findings F001/F002 aus #3384

## Approval

- [ ] Approved

## Purpose

Letzte Scheibe der Waisen-Löschung (Nachfolger von #3366, #3383, #3384): die 7 Dateien der Gruppe S3 (`versand-tab`), die heute als einzige in `BEKANNTE_WAISEN` des Waisen-Wächters stehen und keinen Produktionsaufrufer haben, werden gelöscht, samt der Tests, Prüfstand-Teile, Ratschenzahlen, Katalogschlüssel und Verweise, die nur sie betreffen. Danach ist `BEKANNTE_WAISEN` leer und `OBERGRENZE_WAISEN` 0; der Wächter bleibt als Ratsche und wird bei jeder neuen Waise rot. Dazu kommen die Findings F001/F002 des Adversary aus #3384. Für Nutzer ändert sich nichts Sichtbares.

## Source

- **File:** `frontend/src/lib/__tests__/waisen_waechter.test.ts` (Pflege), `frontend/src/lib/components/shared/versand-tab/` (Löschung)
- **Identifier:** Test `Waisen-Wächter` (Liste `BEKANNTE_WAISEN`, Konstante `OBERGRENZE_WAISEN`, Funktion `pruefeRatsche`)

Schicht: ausschließlich Frontend (`frontend/src/...`) plus Testdaten (Goldens f6, Fallliste), Ratschenzahlen und eine Referenz-Spec (`rework_2276_s6h_ac2_endbilanz.md`). Kein Go-, kein Python-Produktionscode, keine Hook-Änderung (`.claude/hooks` bleibt unberührt). Trip/Vergleich-Teilung: es entsteht kein neuer Baustein; Mandantentrennung: keine Nutzerdaten betroffen; Kanäle: kein Briefing- oder Alarm-Inhalt betroffen (der gelöschte Versand-Reiter-Baustein wird von keiner Seite mehr gerendert).

## Zu löschende Dateien (7, genau die Gruppe S3 in `BEKANNTE_WAISEN`)

Alle Pfade unter `frontend/src/lib/components/shared/versand-tab/`.

1. `VTBriefingChannels.svelte`
2. `VTLaufzeitRoute.svelte`
3. `VTLaufzeitVergleich.svelte`
4. `VTNextBriefing.svelte`
5. `VTSchedulePlan.svelte`
6. `channelContactLabel.ts`
7. `vtBriefingChannelsText.ts`

Der Ordner `versand-tab/` besteht weiter, enthält danach aber keine `.svelte`-Datei mehr (lebend bleiben nur die Module `channelConnectionStatus.ts`, `premiumSmsChannelState.ts`, `sendTargetLabel.ts`, `nextBriefingText.ts`, `nextBriefingLoad.ts`, `naechstesBriefingLader.svelte.ts`, `reportConfigPayload.ts`, `mergeReportConfig.ts`, `dayWindowClamp.ts`). Gemessen: Kein Produktionscode importiert eine der 7 Dateien außer `VTBriefingChannels.svelte` selbst (importiert `channelContactLabel.ts` und `vtBriefingChannelsText.ts`); alle übrigen Treffer sind Kommentare oder Tests.

## Estimated Scope

- **LoC:** Löschung ca. -934 Produktionszeilen plus mitgehende Tests, Goldens und Schlüssel (nach dem Löschen messen, nicht schätzen); neu ca. +80 (Wächter-Ergänzungen, Lösch-Nachweis-Block #3385, F002-Fälle, Trip-Karten-Testfall, Mini-Module im Reaktivitäts-Selbsttest)
- **Files:** 7 Produktionsdateien gelöscht, 11 Testdateien gelöscht, 14 Golden-Dateien gelöscht, gekürzte Testdateien laut Tabellen unten (Zahlen werden nach dem Löschen gemessen)
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| 7 Dateien der Liste oben (`frontend/src/lib/components/shared/versand-tab/...`) | DELETE | Waisen ohne Aufrufer |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | MODIFY | `BEKANNTE_WAISEN` leer, `OBERGRENZE_WAISEN` 0, F001 (Kopfkommentar Z. 16), Kopfkommentar-Absatz #3385, Mini-Fall „leere Liste, neue Waise rot“, Testtitel Z. 200 und Zusicherung Z. 205-207 auf 0 |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | MODIFY | neuer Block `#3385`: 7 Pfade (`existsSync === false`) und Importscan über `frontend/src` und `frontend/e2e` |
| `frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts` | MODIFY | F002: Rückrichtung am echten Editor (Schreibweg); Kommentar Z. 41-43 angepasst |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts` | MODIFY | neuer Testfall Trip mit mehr als 7 Zeilen (Telegram-Grenze je Zeile) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` | MODIFY | die 3 Fälle `E-R8-F3N-VERSAND-*` umgehängt (siehe Abschnitt Fallliste) |

**Testdateien, die S3-Dateien importieren oder einlesen (je einzeln entschieden; die Liste ist abschließend):**

| File (unter `frontend/src/lib/`) | Change Type | Grund |
|------|-------------|-------------|
| `components/shared/versand-tab/__tests__/channelContactLabel.test.ts` | DELETE | reiner Waisentest (`channelContactLabel`) |
| `components/shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` | DELETE | reiner Waisentest (rendert `VTBriefingChannels`, importiert `channelContactLabel`) |
| `components/shared/versand-tab/__tests__/vtBriefingChannelsText.test.ts` | DELETE | reiner Waisentest |
| `components/shared/versand-tab/__tests__/vtBriefingChannelsTextNoJudgement.test.ts` | DELETE | reiner Waisentest |
| `components/shared/versand-tab/__tests__/versand_texte_ohne_wertung_en.test.ts` | DELETE | reiner Waisentest (nur `vtBriefingChannelsText`) |
| `components/shared/versand-tab/__tests__/shared_schedule_quickpick.test.ts` | DELETE | reiner Waisentest (`VTSchedulePlan.svelte`) |
| `components/shared/versand-tab/__tests__/vt_schedule_plan_hour_step.test.ts` | DELETE | reiner Waisentest (`VTSchedulePlan.svelte`) |
| `components/shared/versand-tab/__tests__/telegram_unterzeile_render.test.ts` | DELETE | reiner Waisentest (`VTBriefingChannels`) |
| `components/shared/versand-tab/__tests__/naechstes_briefing_baustein_render.test.ts` | DELETE | reiner Waisentest (`VTNextBriefing`) |
| `components/shared/versand-tab/__tests__/versand_telegram_je_kontext.test.ts` | DELETE | reiner Waisentest (rendert `VTBriefingChannels`); die 3 Fallliste-Fälle werden umgehängt |
| `components/edit/__tests__/report_config_uses_shared_schedule.test.ts` | DELETE | beide Fälle prüfen nur `VTSchedulePlan.svelte` |
| `components/shared/versand-tab/__tests__/sms_unbestaetigt_kanalstatus.test.ts` | MODIFY | Fälle, die `VTBriefingChannels` rendern (Z. 168, 183, 211, 223, 233), samt Import raus; die zwei Fälle zu `channelConnectionStatus` (Z. 136, 156) leben |
| `components/shared/versand-tab/__tests__/naechstes_briefing_verdrahtung.test.ts` | MODIFY | Baustein-Anteil (`BAUSTEIN`, Import Z. 46, Render Z. 100 und die Fälle, die ihn rendern) raus; Blöcke (c), (c/F007), (F008), (f) zu HubUebersicht, HubOverview und CompareTabs leben |
| `components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` | MODIFY | Blöcke AC-6 (HTML-Golden-Fälle und „Messaufbau“), AC-1 und `#2869` (rendern gelöschte Bausteine) raus; in AC-4 nur die Text-Zusicherungen am Kanal-Baustein (`a.text`, `b.text`, `deutscheReste`) raus, Sende-Ziel, Dialog und Nutzlast bleiben; AC-2, AC-3, Sperrfälle, Funktionstabelle und Anker leben |
| `components/shared/__tests__/telegram_kurzstil_shared_toggle.test.ts` | MODIFY | Fälle „route: VTBriefingChannels importiert + mountet“ (Z. 87) und „beide Mount-Stellen referenzieren die IDENTISCHE Modul-Spezifikation“ (Z. 103) samt Konstante `VT_BRIEFING_CHANNELS` (Z. 45) raus; `AlarmeTab`-Fall, Beschriftungs-Fall und alle Render-Fälle leben |
| `components/shared/__tests__/s3b2795_zustellung_struktur.test.ts` | bleibt gültig, unverändert (geprüft) | Die Namen `VTBriefingChannels` und `VTSchedulePlan` stehen nur als Zeichenketten in der Liste `VERBOTEN` (Z. 62-63) und verbieten die Rückkehr der gelöschten Bausteine in den Reiter Zustellung; kein Import, kein Dateilesen |
| `components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | `EINGEFROREN`-Liste: Einträge Z. 271, 272 (`vtBriefingChannelsText.ts:22/:29`) und Z. 283 (`VTSchedulePlan.svelte:72`) raus, `EINGEFROREN_SOLL_ANZAHL` 13 auf 10, Kommentar „Soll 13 → 10“ |
| `components/shared/__tests__/ac2_endbilanz_deckt_alle_47_ab.test.ts` | MODIFY | Positiv-Kontrolle 13 auf 10; Kategorien FACHLICH 7 auf 5, DARSTELLUNG 3 auf 2, HERKUNFT 3 bleibt, Summe 10 |
| `i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | MODIFY | F6-Block Z. 371-387: die 5 gelöschten Dateien aus der Liste `F6` raus (bleibt `TelegramKurzstilToggle.svelte`), `.ts`-Block Z. 392: `vtBriefingChannelsText.ts` raus; Zählungen neu gemessen |
| `i18n/__tests__/reaktivitaet_waechter.test.ts` | MODIFY | Selbsttest-Beispiele auf erfundene Mini-Module umgestellt, Bereich F6 und sein Messaufbau-Test gestrichen (siehe Abschnitt Reaktivitäts-Wächter) |
| `i18n/__tests__/deutsch_unveraendert.test.ts`, `i18n/__tests__/paritaet_de_en.test.ts` | MODIFY | Dateilisten und Zählungen nach dem Entfernen der Katalogschlüssel neu gemessen |
| `__tests__/ink4_waechter.test.ts` | MODIFY | Eintrag `VTSchedulePlan.svelte: 1` (Z. 54) raus, Gesamtzahl im selben Test nach Messung gesenkt |
| `__tests__/bausteine_waechter_regeln.ts` | MODIFY | BESTAND-Einträge Z. 588-592 (fünf `.svelte`) raus, `BESTAND_OBERGRENZE` (Z. 710, heute 167) nach Messung gesenkt |
| `components/shared/versand-tab/__tests__/f6VersandSsr.ts` | MODIFY | Prüfstand f6 gekürzt, siehe Abschnitt Prüfstand f6 |
| `components/shared/versand-tab/__tests__/f6KatalogAnker.ts` | MODIFY | Anker der Schlüssel ohne Verwender entfernt |
| `tests/golden/f6_versand_tab/{alles_gekoppelt,nur_email,premium_verfallen}_{route,vergleich}.{de,en}.html` und `bausteine.{de,en}.html` (14 Dateien) | DELETE | rendern nur gelöschte Bausteine |
| `tests/golden/f6_versand_tab/funktionen.de.txt`, `funktionen.en.txt` | MODIFY | mit dem Projektwerkzeug neu erzeugt (nur die 6 Zeilen der gelöschten Funktionen entfallen) |
| `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` | MODIFY | Tabellenzeilen Z. 110, 111 (FACHLICH) und Z. 120 (DARSTELLUNG) raus, Überschriftenzahlen (7 auf 5, 3 auf 2) und Summen nachgezogen (Doku-Spiegel der Ratsche, vom Test oben gelesen) |

Die Liste ist abschließend. Die folgende Regel gilt nur als Auffangregel für einen unerwartet auffallenden Importeur: eine Testdatei, die nach dem Löschen rot wird, weil sie nur Waisen prüft, wird DELETE, sonst MODIFY (nur die Waisen-Fälle und ihre Importe raus); die Einstufung wird im Lösch-Nachweis-Block `#3385` und im Commit dokumentiert, und ob noch ein Import der Löschliste übrig ist, entscheidet allein der Importscan.

**Browser-Specs:** gemessen, dass keine Datei unter `frontend/e2e/` eine der 7 S3-Dateien importiert; die Namen stehen nur in Kommentaren (`hub-versand-briefing-zeiten.spec.ts` Z. 12, `hub-versand-inline-bearbeiten.spec.ts` Z. 210, `versandzeit-stundenwahl.spec.ts` Z. 8). Deshalb ändert sich in dieser Scheibe keine Browser-Spec, `.github/ci_e2e_specs.txt`, `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED_HAUPT` (`.github/workflows/ci.yml`), und die Tests `test_2243_playwright_loeschscheibe.py` und `test_e2e_positivliste_ratschen_bindung.py` bleiben unverändert.

### Reaktivitäts-Wächter `i18n/__tests__/reaktivitaet_waechter.test.ts`

Gelesen: Die Selbsttest-Beispiele rufen `scanneKomponente(quelle, BEISPIEL_DATEI, SRC, …)` auf; der Scanner löst relative Importe auf echte `.ts`-Dateien auf der Platte auf (`aufloesen`, `sprachExporte` lesen die Datei), `$lib/i18n` über `SRC`. Erfundene Mini-Module müssen daher als echte Dateien existieren; sie werden im Test in einem temporären Ordner (`mkdtempSync`, Aufräumen im `after`) angelegt, analog zum Mini-Baum des Waisen-Wächters, und die Beispielquelle trägt einen Dateipfad in diesem Ordner.

- Fall „sprachfreier Export → []“ (Z. 129-134, Aufruf Z. 132): Mini-Modul `sprachfrei.ts` (exportiert `sprachfrei(p)`, liefert eine Zeichenkette ohne Import von `tr`/`$lib/i18n`); `const a = $derived(sprachfrei(p))` ergibt `[]`. Der Import `channelContactLabel` entfällt aus der Zeile `imp` (Z. 130); die zwei übrigen Aufrufe dieses Tests (Z. 131 und Z. 133) bleiben auf dem lebenden `sendTargetLabel.ts` (ruft `tr`, `sendTargetLabel.ts` Z. 68/77/84/96) und behalten ihre Erwartungen `['5 derived']` und `['6 derived']`.
- Fall „tr-Helfer im Startwert → ‚3 eingefroren‘“ (Z. 142-148): Mini-Modul `textHelfer.ts` (importiert `tr` aus `$lib/i18n`, exportiert `leadText()`, das `tr('beispiel.mini.text')` liefert; der Schlüssel ist erfunden, der Scanner prüft keine Schlüssel); die vier Zeilen (`const`, `$state`, `$props`-Standardwert, Funktionsrumpf) rufen `leadText('route')` mit denselben Erwartungen `['3 eingefroren']` (dreimal) und `[]`.
- Erwartungswerte bleiben genau gleich. Die übrigen Selbsttests (Z. 121-127, 135-141) hängen an den lebenden Modulen `premiumSmsChannelState.ts` und `nextBriefingText.ts` und bleiben unverändert.
- Bereich `BEREICHE['F6 #2655 Versand-Reiter']` (Z. 43-46) wird gestrichen, ebenso der Test „Messaufbau: der Versand-Reiter hat sprachabhängige Ableitungen“ (Z. 165-176, Zählung 5). Grund: Der Bereich verweist auf `versand-tab/`, das danach keine `.svelte`-Datei mehr enthält (die Prüfung `dateien.length >= eintraege.length` in Z. 155 würde fehlschlagen), und die fünf `$derived` gehörten zu den gelöschten Bausteinen. `TelegramKurzstilToggle.svelte` braucht keinen eigenen Bereich, weil sie kein `$derived` und keinen `tr()`-Aufruf enthält (gelesen: nur `$props` Z. 37 und die reaktiven `$t(...)`-Texte Z. 57-63) und weil sie von `AlarmeTab.svelte` (Bereich F7, Import Z. 33, Einbettung Z. 576) mit gescannt wird.
- Die Nicht-vakuum-Wächter der übrigen Bereiche (F8 Z. 178-190 mit Zählung 0, F7 Z. 192-206 mit Zählung 2, und der Test „jede Ausnahme trifft noch einen Fund“) bleiben unverändert scharf. Die Zählungen der übrigen Bereiche ändern sich nicht (deren Dateien liegen außerhalb von `versand-tab/`); ergibt der Lauf etwas anderes, ist das ein Befund und wird im Lieferbericht genannt.

### Prüfstand f6

- `versand-tab/__tests__/f6VersandSsr.ts` (MODIFY): Importe der 5 gelöschten Komponenten, von `TelegramKurzstilToggle` (nur dort genutzt, in `bausteineRendern`) und von `vtBriefingChannelsText.ts` raus; Funktionen `kanaeleRendern`, `naechstesBriefingRendern`, `bausteineRendern`, `htmlFaelle` und die Zeilen `vtBriefingLeadText(...)`/`vtBriefingSubTexts(...)` in `funktionsTabelle` entfallen; `PROFILE`, `NB`, `funktionsTabelle` (übrige Zeilen), `schreibeGolden` (nur noch `funktionen.<lang>.txt`) bleiben.
- `tests/golden/f6_versand_tab/`: die 14 HTML-Goldens (siehe Tabelle) sind DELETE. `funktionen.de.txt` und `funktionen.en.txt` sind MODIFY und werden mit dem Projektwerkzeug (`GZ_GOLDEN_SCHREIBEN=de` bzw. `en`) neu erzeugt; vorher/nachher gegengelesen: der Unterschied sind ausschließlich die 6 Zeilen `vtBriefingLeadText(...)`/`vtBriefingSubTexts(...)` (2 Kontexte x 3).
- `f6KatalogAnker.ts` (MODIFY): Anker der Schlüssel, die mit den gelöschten Bausteinen ohne Verwender werden (`versand.*`, laut Analyse 36 Schlüssel, Liste durch `katalog_schluessel_haben_verwender.test.ts` gemessen), entfallen; die `telegram_kurzstil.*`-Anker bleiben. Der Gegencheck in `versand_tab_sprache.test.ts` („Anker-Tabelle == Schlüssel von versand.json + telegram_kurzstil.*“) bleibt grün.
- `frontend/src/lib/i18n/messages/{de,en}/versand.json` (MODIFY): nur Schlüssel entfernt, die weder im Frontend noch im Python-Backend einen Verwender haben (Backend nutzt `versand.*`, Beleg `tests/test_versand_zweisprachig.py`); de und en gleiche Menge. `bausteine.json` ist nicht betroffen: ihre Schlüssel `telegram_kurzstil.*` werden von `TelegramKurzstilToggle.svelte` (lebend, `$t('telegram_kurzstil.checkbox')` Z. 57) benutzt.

### Fallliste `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`

Die drei Fälle `E-R8-F3N-VERSAND-ORTE-DE`, `E-R8-F3N-VERSAND-ORTE-EN`, `E-R8-F3N-VERSAND-TRIP` (Liste `telegram`, Format `editor`, Prüfung `anzeige`) sagen inhaltlich, welche Zeilen in Telegram landen: beim Trip die ersten 7, beim Ortsvergleich alle Zeilen. Sie verweisen heute auf `versand_telegram_je_kontext.test.ts`, das nur den gelöschten `VTBriefingChannels` rendert.

**Befund (die Karte „Was steht wo“, `WasStehtWoKarte.svelte`, gelesen):** Die Karte rechnet keine Zeilengrenze selbst; sie zeigt je Zeile und Kanal die Zelle aus der Antwort des Endpoints (`cells.telegram` mit `state` und `mark`). Beim Trip trägt eine Telegram-Zelle die Marke `nur_tageswert` (Text „nur Tageswert“); damit ist je Zeile erkennbar, ab welcher Zeile Telegram nur den Tageswert führt. Beim Ortsvergleich gibt es keine Telegram-Marke je Zeile und keine zweite Zeile ab Platz 8 in der Karte; ob „alle Zeilen“ in Telegram landen, ist dort nicht je Zeile erkennbar. Daraus folgt:

- `E-R8-F3N-VERSAND-TRIP`: Status `gruen`, umgehängt auf den neuen Testfall in `was_steht_wo_karte.test.ts` mit dem Titel `Trip mit neun Zeilen: Telegram-Marke „nur Tageswert“ erst ab der achten Zeile` (siehe AC-6); `verweis` nennt `#3385` und ADR-0124 Nr. 3.
- `E-R8-F3N-VERSAND-ORTE-DE` und `E-R8-F3N-VERSAND-ORTE-EN`: Status `ausnahme`, `verweis` `#3385` mit dem Grund „Editor zeigt die Telegram-Zeilengrenze nicht mehr“; ein Folge-Issue legt der Tech Lead an. Die Testverweise zeigen auf lebende Tests der Orte-Karte: DE auf `was_steht_wo_karte.test.ts::Orte: fünf Spalten, E-Mail „Übersicht“, Stundenverlauf „nur E-Mail“, Telegram im engen Raster „Telegr.“`, EN auf `was_steht_wo_karte.test.ts::alle Texte englisch, Namen und Kürzel aus der Antwort unverändert`.

Kein Fall verschwindet, alle drei behalten ihre Kennung. `format` ist `editor` (kein Kanal-Format), deshalb ändert sich die Kanal-Abdeckung (Prüfung f) nicht; `tests/tdd/test_einstellung_gleich_mail_fallliste.py` bleibt grün (Verweis auffindbar, Ausnahme trägt `#`-Verweis).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3385-waisen-s3.md`, `docs/context/rework-3366-waisen-loeschen.md` (Abschnitt S3) | doc | Analyse: Dateiliste, Kopplungen f6, `EINGEFROREN`, Fallliste |
| `docs/specs/modules/rework_3384_waisen_s4.md` | spec | Vorlage (geliefert mit PR #3388) |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | test | Wächter, Ratsche, Selbstnachweis |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | test | Lösch-Nachweis, Importscan |
| `frontend/src/lib/i18n/__tests__/reaktivitaet_scan.ts` | test | Scanner des Reaktivitäts-Wächters (`scanneKomponente`, `aufloesen`) |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts`, `tests/test_versand_zweisprachig.py` | test | Katalogschlüssel ohne Verwender (Frontend und Backend) |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | test | Verweis-Wächter der Fallliste |
| `tests/unit/ein_katalog_ausnahmen.json`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` | ratsche | `hoechststand` (heute 422) und `HOECHSTSTAND` (Z. 39) |
| `frontend/src/lib/components/shared/__tests__/compareNeuEditorPruefstand.ts` | test | echter Anlege-Editor für F002 (`vergleichEditor`, `buendelAus`, `fetchMitschnitt`) |
| Golden-Werkzeug des Projekts (`GZ_GOLDEN_SCHREIBEN`) | tooling | `funktionen.*.txt` neu erzeugen, nie von Hand |
| `node --test`, `svelte-check`, Vite-Build | tooling | Nachweis keine sichtbare Änderung |

## Implementation Details

**Reihenfolge.** Zuerst RED: Wächter-Liste auf `[]`, `OBERGRENZE_WAISEN` auf 0 setzen; der Wächter meldet die 7 Dateien als neue Waisen. Lösch-Nachweis-Block `#3385` ist rot, solange die Dateien existieren. Vor dem Löschen wird die svelte-check-Baseline auf dem Branch-Stand gemessen (Fehler und Warnungen) und im Test-Artefakt `docs/artifacts/rework-3385-waisen-s3/svelte-check.md` festgehalten (Zeilen „vorher“ und „nachher“). Dann Löschen, danach die betroffenen Testdateien benannt laufen lassen (nie `uv run pytest` ohne Dateinamen). Zahlen werden nach dem Löschen gemessen und im selben Commit eingetragen.

**Zählstellen (jede einzeln, alle nach dem Löschen gemessen):**
- Wächter: `waisen_waechter.test.ts`, `BEKANNTE_WAISEN` leer, `OBERGRENZE_WAISEN` 0.
- Lösch-Nachweis: `trip_pfad_altfeld_loeschnachweis_3297.test.ts`, Block `#3385`.
- BESTAND: `bausteine_waechter_regeln.ts` (5 Einträge, `BESTAND_OBERGRENZE` heute 167).
- ein_katalog: `ein_katalog_ausnahmen.json` `hoechststand` (heute 422) und `test_ein_katalog_eine_verarbeitung_ratsche.py` `HOECHSTSTAND`, beide identisch auf den gemessenen Wert, im selben Commit (gemessen: kein Ausnahmen-Eintrag nennt eine S3-Datei).
- ink4: `ink4_waechter.test.ts` (Eintrag Z. 54, Gesamtzahl).
- EINGEFROREN: `context_herkunft_zweige_eingefroren.test.ts` (13 auf 10), `ac2_endbilanz_deckt_alle_47_ab.test.ts` (13/7/3/3 auf 10/5/2/3), Spec `rework_2276_s6h_ac2_endbilanz.md`.
- f6: `f6VersandSsr.ts`, `f6KatalogAnker.ts`, Goldens `tests/golden/f6_versand_tab/`.
- Reaktivität: `reaktivitaet_waechter.test.ts` (Bereich F6 und Messaufbau-Zählung 5 gestrichen; F7-Zählung 2 und F8-Zählung 0 unverändert).
- Katalog und i18n: `versand.json` de/en (`bausteine.json` nicht betroffen), `keine_hartkodierten_nutzertexte.test.ts`, `deutsch_unveraendert.test.ts`, `paritaet_de_en.test.ts`.
- E2E-Zählwerte: keine Änderung (siehe Browser-Specs oben, 0 Importe gemessen).

**Wächter (F001).** Der Kopfkommentar Z. 16 lautet bisher „BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN“, die Logik prüft seit #3384 exakte Gleichheit (`pruefeRatsche`, `bekannte.length !== obergrenze`). Der Kommentar wird auf „BEKANNTE_WAISEN.length === OBERGRENZE_WAISEN“ korrigiert. Zusätzlich neuer Mini-Baum-Fall: leere Liste, Obergrenze 0, eine erfundene Datei ohne Aufrufer wird als „neue Waise“ rot gemeldet (Ratsche bleibt nach Leerung wirksam).

**F002.** Die Zusicherung beschränkt sich auf den Schreibweg zum Speichern. Am echten Anlege-Editor `CompareNewEditor` (Block `AC-14` von `hub_geteilte_felder_cooldown_quiet_konsistent.test.ts`): `AlarmeTab` (Bündel `buendelAus(e, 'AlarmeTab')` trägt `onCooldownChange` und `onQuietHoursChange` aus `alarmePropsAus(wiz)`, CompareNewEditor Z. 573/621) schreibt; Messstellen sind das Prop `preset` des `ZustellungTab` (`buendelAus(e, 'ZustellungTab', 'preset')`, Feld `alert_cooldown_minutes`, Z. 570/618) und der POST der Aktivierung (`netz.presetPosts()`). Zwei Fälle: (1) `onCooldownChange(60)` im Alarme-Bündel, danach steht 60 im Prop `preset` und im POST (`alert_cooldown_minutes: 60`); (2) danach `onCooldownChange(undefined)`, danach ist weder im Prop `preset` noch im POST der Wert 60 enthalten. Ebenso für `onQuietHoursChange` (von/bis).

**Trip-Karten-Testfall.** In `was_steht_wo_karte.test.ts` neuer Fall `Trip mit neun Zeilen: Telegram-Marke „nur Tageswert“ erst ab der achten Zeile`: `trip()` mit neun Zeilen (Telegram-Zellen `on`; die Zellen der Zeilen 1 bis 7 ohne `mark`, die der Zeilen 8 und 9 mit `mark: 'nur_tageswert'`); der Render zeigt „nur Tageswert“ genau in den Telegram-Zellen der Zeilen 8 und 9 und in keiner der ersten 7.

**Lösch-Nachweis.** Block `#3385` in `trip_pfad_altfeld_loeschnachweis_3297.test.ts`: die 7 Pfade existieren nicht (`existsSync === false`); Importscan über `frontend/src` und `frontend/e2e` (Kommentare ausgenommen): kein Import-/Export-Spezifizierer, kein dynamisches `import()` und keine Pfad-Zeichenkette in `join`/`resolve`/`path.join`, die auf einen der 7 Basisnamen (mit oder ohne Endung) zeigt; einzige Ausnahme ist die Lösch-Nachweis-Datei selbst, die die Pfade führt.

## Expected Behavior

- **Input:** Quelltext von `frontend/src`.
- **Output:** Wächter grün, solange es keine Waise (ohne `AUSNAHMEN`) gibt; `BEKANNTE_WAISEN` ist leer, `OBERGRENZE_WAISEN` ist 0 und gleicht der Listenlänge; jede neue Datei ohne Aufrufer macht ihn rot. Löschung ohne Funktionsänderung.
- **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen, Katalog und Goldens schrumpfen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter rot vor der Löschung: `waisen_waechter.test.ts` mit leerer Liste und `OBERGRENZE_WAISEN = 0` meldet die 7 S3-Dateien als neue, nicht gelistete Waisen (RED), nach der Löschung grün; Mini-Fall „leere Liste + erfundene Waise“ rot. Mutations-Gegenprobe: eine Datei ohne Aufrufer anlegen (oder einen Eintrag wieder in die Liste setzen) macht den echten Baum rot.
- [ ] Lösch-Nachweis rot vor der Löschung (7 Pfade existieren, Importe vorhanden), grün danach. Mutation: eine gelöschte Datei wiederherstellen bzw. einen Import auf einen der 7 Namen in eine Testdatei schreiben (Kopie mit externer Sicherung, nie `git checkout/stash/reset`) macht den Block rot.
- [ ] F001: doc-compliance-Zusicherung in `waisen_waechter.test.ts` (Datei trägt `# doc-compliance-test`), dass der Kopfkommentar „===“ nennt und kein „<=“ zwischen `BEKANNTE_WAISEN.length` und `OBERGRENZE_WAISEN` steht; Mutation: Kommentar auf „<=“ zurück macht sie rot.
- [ ] F002: Schreibweg-Fälle am echten Editor rot vor dem Umbau, grün danach. Mutationen: im `AlarmeTab`-Bündel `onCooldownChange` auf einen leeren Rückruf ersetzen, oder `zustellungAbo` den Cooldown nicht aus `wiz` übernehmen lassen, macht den jeweiligen Fall rot.
- [ ] Trip-Karten-Testfall rot vor dem Anlegen (Titel fehlt, Fallliste-Verweis nicht auffindbar), grün danach. Mutation: im Fall die Marke `nur_tageswert` auf eine der ersten 7 Zeilen setzen macht ihn rot.
- [ ] Reaktivitäts-Selbsttest mit Mini-Modulen grün; Mutation: `sprachfrei.ts` ruft `tr(...)` auf (erwartet `[]`) bzw. `textHelfer.ts` ohne `tr`-Import (erwartet `3 eingefroren`) macht den jeweiligen Fall rot. Bereich F6 gestrichen: F7- und F8-Messaufbau bleiben grün; Mutation: in einem F7-Bereichsfile `void $locale` entfernen macht den F7-Wächter rot.
- [ ] Fallliste: `tests/tdd/test_einstellung_gleich_mail_fallliste.py` benannt grün; Mutation: einen Verweis auf einen nicht existierenden Testtitel setzen macht `test_testverweise_auffindbar` rot.
- [ ] Prüfstand f6: `versand_tab_sprache.test.ts` grün mit den verbleibenden Blöcken; Mutation: eine Zeile in `funktionen.de.txt` verändern macht den Funktionstabellen-Fall rot; Anker-Gegencheck grün (de/en gleiche Schlüssel).
- [ ] Betroffene Testdateien benannt laufen lassen: alle in der Tabelle genannten Dateien (auch `s3b2795_zustellung_struktur`) sowie `waisen_waechter`, `trip_pfad_altfeld_loeschnachweis_3297`, `was_steht_wo_karte`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert`, `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `keine_hartkodierten_nutzertexte`, `context_herkunft_zweige_eingefroren`, `ac2_endbilanz_deckt_alle_47_ab`.
- [ ] Python (benannt): `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`, `tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `tests/test_versand_zweisprachig.py`.
- [ ] Gesamt: Frontend-Suite (`node --test`), Vite-Build und `svelte-check` grün; die svelte-check-Baseline (Fehler/Warnungen) wird vor dem Löschen gemessen und darf nachher nicht steigen; beide Zahlen stehen im Test-Artefakt `docs/artifacts/rework-3385-waisen-s3/svelte-check.md`.

## Acceptance Criteria

- **AC-1:** Given die 7 Dateien der Gruppe S3 (`VTBriefingChannels.svelte`, `VTLaufzeitRoute.svelte`, `VTLaufzeitVergleich.svelte`, `VTNextBriefing.svelte`, `VTSchedulePlan.svelte`, `channelContactLabel.ts`, `vtBriefingChannelsText.ts`) / When das Dateisystem nach S3 geprüft wird / Then existiert keine der 7 Dateien mehr, kein Produktionscode importiert die gelöschten Basisnamen, und `EinstellTabelle.svelte` besteht weiter.
  - Test: `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (Block `#3385`, `existsSync === false` plus Importscan). Architektur-Wächter über den echten Importgraphen, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-8. Mutations-Gegenprobe: Datei wiederherstellen macht den Block rot.

- **AC-2:** Given `BEKANNTE_WAISEN` geleert und `OBERGRENZE_WAISEN` auf 0 gesetzt / When der Wächter die Erreichbarkeit ab `routes/` und `src/*.ts` berechnet / Then ist die Waisenmenge (ohne `AUSNAHMEN`) leer, `OBERGRENZE_WAISEN` ist die feste Literal-Konstante 0 und gleicht `BEKANNTE_WAISEN.length`, der Test ist grün, und eine neu angelegte Datei ohne Aufrufer macht ihn rot.
  - Test: `waisen_waechter.test.ts` gegen den echten Baum (im RED-Stand vor der Löschung rot mit den 7 Pfaden) und der neue Mini-Baum-Fall „leere Liste, erfundene Waise ist rot“. Mutations-Gegenprobe: einen Eintrag wieder in die Liste setzen oder eine aufruferlose Datei anlegen macht den Test rot.

- **AC-3:** Given der Kopfkommentar von `waisen_waechter.test.ts` zur Ratsche / When er gelesen wird / Then nennt er „BEKANNTE_WAISEN.length === OBERGRENZE_WAISEN“ (exakte Gleichheit, wie die Logik in `pruefeRatsche`) und kein „<=“ zwischen beiden.
  - Test: Finding F001 aus #3384; doc-compliance-Zusicherung in `waisen_waechter.test.ts` (Marker `# doc-compliance-test` steht im Kopf der Datei); Mutations-Gegenprobe: Kommentar auf „<=“ zurücksetzen macht sie rot.

- **AC-4:** Given der echte Anlege-Editor des Ortsvergleichs (`CompareNewEditor` mit `AlarmeTab` und `ZustellungTab`) / When im Reiter Alarme der Cooldown auf 60 gesetzt und danach gelöscht wird (ebenso Stille Stunden) / Then übergibt der Editor dem Reiter Zustellung den Stand im Prop `preset` und speichert ihn im POST der Aktivierung: zuerst mit 60, danach ohne 60.
  - Test: Finding F002 aus #3384; neue Fälle im Block `AC-14` von `hub_geteilte_felder_cooldown_quiet_konsistent.test.ts` am echten Editor (`buendelAus`, `netz.presetPosts()`, Messung nur auf Prop und POST); Mutations-Gegenprobe: `onCooldownChange` im Alarme-Bündel zu einem leeren Rückruf ersetzen macht den Fall rot.

- **AC-5:** Given die drei Fallliste-Fälle `E-R8-F3N-VERSAND-ORTE-DE`, `E-R8-F3N-VERSAND-ORTE-EN`, `E-R8-F3N-VERSAND-TRIP` / When `versand_telegram_je_kontext.test.ts` gelöscht ist / Then bestehen alle drei mit derselben Kennung weiter: `TRIP` als `gruen` auf dem neuen Trip-Karten-Testfall (AC-6), `ORTE-DE` und `ORTE-EN` als `ausnahme` mit `#3385`-Verweis und dem Grund „Editor zeigt die Telegram-Zeilengrenze nicht mehr“ (Befund: die Orte-Karte kennzeichnet Telegram je Zeile nicht), und der Verweis-Wächter der Fallliste ist grün.
  - Test: `tests/tdd/test_einstellung_gleich_mail_fallliste.py` benannt grün; Mutations-Gegenprobe: einen Verweis auf einen nicht existierenden Testtitel setzen macht `test_testverweise_auffindbar` rot.

- **AC-6:** Given die Karte „Was steht wo“ beim Trip mit neun Zeilen, deren Telegram-Zellen ab der achten Zeile die Marke `nur_tageswert` tragen / When die Karte gerendert wird / Then steht „nur Tageswert“ genau in den Telegram-Zellen der Zeilen 8 und 9 und in keiner der ersten 7.
  - Test: neuer Fall `Trip mit neun Zeilen: Telegram-Marke „nur Tageswert“ erst ab der achten Zeile` in `was_steht_wo_karte.test.ts` (echter SSR-Render); Mutations-Gegenprobe: die Marke auf eine der ersten 7 Zeilen setzen macht ihn rot.

- **AC-7:** Given die Löschung / When der Importscan im Lösch-Nachweis über `frontend/src` und `frontend/e2e` läuft und die Zahlenratschen (`BESTAND_OBERGRENZE`, ink4, `hoechststand`/`HOECHSTSTAND` ein_katalog, `EINGEFROREN` mit `EINGEFROREN_SOLL_ANZAHL` und ac2-Endbilanz samt Spec, Zählungen in `keine_hartkodierten_nutzertexte`, Katalogschlüssel de/en) geprüft werden / Then findet der Scan keinen Import der Löschliste mehr, die 11 reinen Waisentests sind gelöscht, die gemischten Tests nur um die Waisen-Fälle gekürzt und grün, die 14 HTML-Goldens von f6 gelöscht, `funktionen.de.txt` und `funktionen.en.txt` mit dem Projektwerkzeug neu erzeugt (Unterschied nur die 6 Zeilen `vtBriefingLeadText`/`vtBriefingSubTexts`), alle Zahlen stimmen mit der Messung nach dem Löschen überein und sind nur gesunken, `hoechststand` (JSON) und `HOECHSTSTAND` (Python) sind identisch, `EINGEFROREN` hat 10 Einträge (FACHLICH 5, DARSTELLUNG 2, HERKUNFT 3), de und en führen dieselbe Schlüsselmenge, kein Schlüssel ohne Verwender bleibt, `bausteine.json` ist unverändert.
  - Test: Importscan im Block `#3385` des Lösch-Nachweises plus `versand_tab_sprache`, `bausteine_waechter`, `ink4_waechter`, `keine_hartkodierten_nutzertexte`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert`, `context_herkunft_zweige_eingefroren`, `ac2_endbilanz_deckt_alle_47_ab`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` und `tests/test_versand_zweisprachig.py` grün. Mutation: einen Import auf einen der 7 Namen in eine Testdatei schreiben, eine Zahl um 1 erhöhen oder `funktionen.de.txt` verändern macht die jeweilige Prüfung rot.

- **AC-8:** Given die Seiten und Ansichten (insbesondere Trip-Editor, Vergleichs-Editor, Hub-Übersicht, Alarme- und Zustellung-Reiter) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die svelte-check-Zahlen (Fehler/Warnungen) wurden vor dem Löschen auf dem Branch-Stand gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
  - Test: Frontend-Suite per `node --test`, `npm run build`, `svelte-check` (beide Zahlen vorher/nachher in `docs/artifacts/rework-3385-waisen-s3/svelte-check.md`); Python-Verweiswächter für `tests/fixtures/einstellung_gleich_mail/` grün. Mutations-Gegenprobe: einen Typfehler in eine geänderte Datei schreiben macht `svelte-check` rot.

- **AC-9:** Given `EinstellTabelle.svelte` samt Test, `.claude/hooks`, alle Browser-Specs unter `frontend/e2e/` (#3374, darunter `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`) und die CI-Positivliste samt `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` / When S3 geliefert ist / Then sind diese Dateien und Werte unverändert.
  - Test: Vergleich gegen `main` zeigt keine Änderung an den genannten Pfaden (Prüfung im Validator-Lauf); `test_2243_playwright_loeschscheibe.py` und `test_e2e_positivliste_ratschen_bindung.py` benannt grün. Mutation: eine beliebige dieser Dateien verändern macht den Vergleich rot.

- **AC-10:** Given der Reaktivitäts-Wächter `reaktivitaet_waechter.test.ts` nach dem Löschen / When er läuft / Then hängt keiner seiner Selbsttests mehr an einem gelöschten Modul (die Fälle „sprachfreier Export → []“ und „tr-Helfer im Startwert → 3 eingefroren“ laufen auf erfundenen Mini-Modulen mit unveränderten Erwartungswerten), der Bereich „F6 #2655 Versand-Reiter“ samt seinem Messaufbau-Test ist gestrichen, die Wächter der übrigen Bereiche (F7 Zählung 2, F8 Zählung 0, „jede Ausnahme trifft noch einen Fund“) sind unverändert grün, und `TelegramKurzstilToggle.svelte` bleibt über den Bereich F7 (`AlarmeTab.svelte`) gescannt.
  - Test: `reaktivitaet_waechter.test.ts` benannt grün; Mutationen: `sprachfrei.ts` ruft `tr(...)` auf, `textHelfer.ts` ohne `tr`-Import, oder `void $locale` in einem F7-Bereichsfile entfernen macht den jeweiligen Test rot.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`)
- [ ] RED-Nachweis: Wächter, Lösch-Nachweis, F002-Fälle und Trip-Karten-Testfall rot vor der Umsetzung, grün danach
- [ ] svelte-check-Baseline vor dem Löschen gemessen, Artefakt `docs/artifacts/rework-3385-waisen-s3/svelte-check.md`
- [ ] 7 S3-Dateien gelöscht, mitgezogene Tests (Tabelle), Prüfstand f6, Goldens, Schlüssel, Ratschen, `EINGEFROREN`, Spec-Spiegel im selben Commit gepflegt
- [ ] `BEKANNTE_WAISEN` leer, `OBERGRENZE_WAISEN` 0, Block `#3385` im Lösch-Nachweis
- [ ] F001 und F002 umgesetzt und je mit Mutations-Gegenprobe als rot nachgewiesen
- [ ] Fallliste: `TRIP` `gruen` umgehängt, `ORTE-DE`/`ORTE-EN` als `ausnahme`, Verweis-Wächter grün
- [ ] Reaktivitäts-Wächter auf Mini-Module umgestellt, Bereich F6 gestrichen
- [ ] Zahlen nach dem Löschen gemessen und eingetragen
- [ ] Frontend-Suite, Build, `svelte-check` und die benannten Python-Tests grün (svelte-check vorher gemessen, nachher nicht höher)
- [ ] Adversary und Mutations-Gegenprobe am Wächter
- [ ] CI (6 Checks) grün, Deploy ohne sichtbare Änderung

## Known Limitations

- Der Wächter ist ein statischer Importgraph: Verwendung über berechnete Zeichenketten oder externe Registries würde er nicht sehen. Die Array-Form von `import.meta.glob` (auch mit Typparameter) bleibt nicht unterstützt und schlägt laut an.
- Die Karte „Was steht wo“ zeigt die Telegram-Zeilengrenze beim Ortsvergleich nicht je Zeile (Befund oben); die Fälle `E-R8-F3N-VERSAND-ORTE-DE` und `-EN` laufen deshalb als `ausnahme` („Editor zeigt die Telegram-Zeilengrenze nicht mehr“), ein Folge-Issue legt der Tech Lead an. Beim Trip belegt die Karte die Grenze nur als Anzeige der Marke aus der Antwort; die Berechnung der Grenze (7 Zeilen) liegt im Backend.
- Der Reaktivitäts-Wächter prüft `.svelte`-Dateien; die `tr()`-nutzenden Module in `versand-tab/` (`sendTargetLabel.ts` u. a.) werden über ihre Verbraucher in den übrigen Bereichen mitgeprüft, nicht mehr über einen eigenen Bereich.
- Die Zahlen (Ratschen, Katalogschlüssel, Golden-Zeilen, Dateizahlen) stehen erst nach der Messung nach dem Löschen fest; die Spec nennt die Stellen, nicht die Werte.

## Out of Scope

- Tote Exporte in `versandVergleichSpeicherung`/`weatherMetricsCompareSave` → #3389.
- #3374 (alle Browser-Specs, Playwright, Staging-Browserprüfungen wie `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`); keine Browser-Spec importiert eine gelöschte Datei (gemessen).
- `EinstellTabelle.svelte` und ihr Test; `.claude/hooks`; Produktionscode außerhalb der Löschmenge; Barrels und `lib/index.ts`.
- Finding F003 aus #3383.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Aufräumarbeit nach bestehender Entscheidung (Löschung von Alt-Editor-Bausteinen, #3297/#3122/#3366/#3383/#3384) nach vorhandenem Muster; keine neue Entscheidungsfläche. Die Fallliste-Umhängung folgt ADR-0124 Nr. 3 (Telegram-Schnittlinie in der Karte „Was steht wo“).

## Changelog

- 2026-11-26: Initial spec created (v1.0)
- 2026-11-26: v1.1 (tote Exporte nach #3389 abgespalten; ACs neu nummeriert)
- 2026-11-26: v1.2 (Fallliste nach Befund zur Karte; AC-Format; s3b2795 „bleibt gültig“; `test_versand_zweisprachig.py`; feste DELETE/MODIFY-Regel; AC-7 über Importscan; Artefaktpfad; F002 auf Schreibweg)
- 2026-11-26: v1.3 (Reaktivitäts-Wächter: Mini-Module statt gelöschter Module, Bereich F6 gestrichen mit Begründung zum Toggle; feste Typen für f6-Prüfstand, Goldens und Katalog; `bausteine.json` nicht betroffen; Liste abschließend, Regel nur Auffangregel; AC-10)
