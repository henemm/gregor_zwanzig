---
entity_id: feat_2347_s3b_paritaets_e2e
type: feature
created: 2026-10-28
updated: 2026-10-28
status: draft
version: "1.1"
workflow: feat-2347-s3b-paritaets-e2e
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, versand]
---

# Paritäts-E2E, Scheibe S3b: Versand-Gruppe (#2347)

## Approval

- [ ] Approved

## Purpose

S1 (Helfer, Versand-Uhrzeit, Cross-User-Sperre), S2 (Reiterleiste, Kopf, Listen-Menü, Speicher-Chip, Sende-Dialog) und S3a (Alarme, Wertebereiche, Wetter-Metriken, Autosave-Isolation) sind live. S3b räumt die **Versand-Gruppe** der Compare-only-Altlast: vier Playwright-Specs (`compare-versand-speichert-selbst`, `compare-hub-versand-inline`, `compare-hub-briefing-times`, `versand-tab-vergleich`) plus der Versand-Anteil von `compare-editor-autosave` werden zu **vier geteilten `hub-versand-*`-Specs**, in denen dieselbe Zusicherung per `for (const kind of HUB_KINDS)` für Trip UND Ortsvergleich geprüft wird. Danach gilt für den Versand-Abschnitt (Reiter Wetter-Metriken, `#versand`): Was für den Ortsvergleich bewiesen ist, ist für den Trip bewiesen — und umgekehrt.

Die Altspecs sind das Regressionsnetz für #2276/#2277 (Versand speichert selbst, Lost-Update F004, 412-Behandlung). **Keine Zusicherung darf beim Zusammenführen verloren gehen oder abgeschwächt werden** (Zuordnungstabelle + Mutations-Gegenprobe je kind). Rote oder veraltete Altfälle sind kein Löschgrund: Texte werden am Ist-Stand der Produkt-Komponenten neu formuliert; entfällt eine Zusicherung nachweislich mit dem Produkt (#1743), steht das mit Beleg in der Zuordnung.

Reine Testschicht. Wird ein Trip-Fall rot, ist das eine Produktlücke, die **im selben Ticket** behoben wird (AC-13, Muster S2/S3a).

## Source

- **File:** neue Specs `frontend/e2e/hub-versand-speichert-selbst.spec.ts` (VS), `hub-versand-inline-bearbeiten.spec.ts` (VI), `hub-versand-aufbau.spec.ts` (VA), `hub-versand-briefing-zeiten.spec.ts` (VB); Ergänzungen in `hub-kopf-aufbau.spec.ts` (KA-5b) und `compare-editor-slice3.spec.ts`; Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`; Ratsche `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`
- **Identifier:** `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `testMitZustellbaremZiel` (`frontend/e2e/helpers.ts`) · `ALTLAST`, `ALTLAST_MAX` · `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`
- **Produktcode:** keiner geplant (Regel für Trip-Rotfälle: AC-13).

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** ausschließlich Testschicht (Playwright gegen den CI-Stack, Python-Unit-Wächter, CI-Ratsche, Gate-Doku). Kein Code in `frontend/src/`, `internal/`, `cmd/`, `api/`, `src/` — außer AC-13.
- **Trip/Ortsvergleich-Teilung:** Kern der Spec. Compare-eigene Zweige (`if (kind === 'vergleich')`, je mit Begründungskommentar) sind nur zulässig, wo das Produkt für den Trip **keine** Entsprechung hat (Tabelle „Kind-Kontraste" unten). Wo der Trip dasselbe in anderer Form hat (Laufzeit, Pausieren, „Bearbeiten →", Übersicht-Briefings), gilt das Muster WW-4 aus S3a: jeder Zweig prüft **seine eigene** Zusicherung, kein Zweig wird übersprungen.
- **Mandantentrennung:** Es wird kein neuer Endpunkt eingeführt. Keine neue Spec registriert selbst einen Nutzer: wo ein zustellbares Ziel nötig ist, dient der worker-scoped Fixture `testMitZustellbaremZiel` (Wegwerf-Zweitnutzer, **eine** Registrierung je Worker, Bremse 5/h/IP; `workers: 1`). Weil dieser Nutzer von KA-5, KA-5b, VA-3 und VI-1 geteilt wird, stellt jeder Fall, der sein Profil ändert (VI-1: `telegram_chat_id`), den Ausgangswert im `finally` wieder her (Lesen vor Schreiben, Muster der Alt-Spec `compare-hub-versand-inline.spec.ts:44-49`). Der Admin-Testnutzer wird **nicht** mehr verändert (die Alt-Specs setzten `telegram_chat_id` bzw. `mail_to` im Admin-Profil). Zwei-Nutzer-Test für Datenisolation bleibt in `hub-cross-user-write-block`/`hub-editor-autosave-user-isolation` (S1/S3a), unverändert.
- **Kanäle:** nicht betroffen — es wird nichts versendet; Sende-Abrufe werden per `page.route` abgefangen und selbst beantwortet.

## Gesamtschnitt #2347 (Stand)

| Scheibe | Inhalt | Status |
|---|---|---|
| S1 | Helfer; Versand-Uhrzeit + Chip; Cross-User-Sperre; Wächter (ALTLAST 48) | live |
| S2 | Reiterleiste, Kopf, Listen-Menü, Speicher-Chip, Sende-Dialog (48 → 41) | live |
| S3a | Alarme, Wertebereiche, Wetter-Metriken, Autosave-Isolation (41 → 34) | live (c8bb30d) |
| **S3b (diese Spec)** | **Versand-Gruppe** (4 Altdateien + Versand-Anteil `compare-editor-autosave`) → 4 `hub-versand-*`; ALTLAST 34 → 30 | diese Spec |
| S3c | Konflikt-412 über zwei Kontexte (`compare-konfliktschutz-zwei-kontexte`) — Trip-Pendant erstmals gemessen | folgt |
| S3d | compare-eigener Rest: Radar-Toggle, Stundenverlauf ×2, `compare-hourly-metric-order`, `issue-682` ↔ `issue-661`, Rest `compare-hub-inline-edit` (Orte), Rest `compare-editor-autosave` (Orte, Gesten-Gate, `waitForTimeout`), `.staging`-Specs | folgt |
| S4 | Gruppe ohne Trip-Pendant, #2243-Leichen (u. a. `compare-editor-slice3`, Wizard-Create-Flow), ALTLAST leer | folgt |

Ticket #2347 und Epic #2345 bleiben offen bis S4. Scheiben werden strikt nacheinander gemergt (`ci_e2e_specs.txt` ist Konfliktpunkt). S3c, S3d und S4 sind **nicht** Teil dieser Scheibe und werden nicht abgespalten, sondern als weitere Scheiben desselben Tickets geführt.

## Entscheidungen zu den offenen Fragen aus der Analyse

Alle drei am Code beantwortet; keine Rückfrage an den PO.

### Frage 1 — briefing-times: Welche der „4 roten" Fälle gelten noch?

Der Ratschen-Kommentar (`ci_e2e_specs.txt:143-150`) zitiert Zeilen (:82/:99/:212/:238), die zum heutigen Dateistand nicht mehr passen; die Messung stammt aus einer älteren Fassung. Am Ist-Stand der Produkt-Komponenten, Fall für Fall (die RED-Messung im Stack bestätigt es, ersetzt aber nicht die Entscheidung):

| Alt-Fall | Befund am Produkt | Entscheidung |
|---|---|---|
| **AC-2** Übersicht mobil zeigt die Briefings-Angabe wie Desktop | Der Stat `compare-detail-stat-briefings` steht **nur** im Desktop-Streifen (`CompareTabs.svelte:772-775`, `{:else}`-Zweig von `isMobileViewport`). Mobil rendert ein 4-Kachel-Raster ohne Briefings (`:716-749`); `hub-tab-bar.spec.ts:258-265` sichert das (genau 4 Karten, Stat `count 0`). Dieselbe Angabe steht mobil in der Summary-Zeile „Versand" (`hub-summary-row-title`, `:827-831`). Trip: `TripTabs.svelte:191` rendert `HubOverview` in der Übersicht für beide Breiten (nur Layout per `@media (max-width: 899px)`, `HubOverview.svelte:190`); die Karte „Briefings laufen" ist mobil dieselbe wie am Desktop. | **Gilt weiter, umformuliert:** Zusicherung „mobil ist die Briefing-Angabe sichtbar und gleich der Desktop-Angabe" wird gegen die tatsächliche mobile Stelle geprüft: Ortsvergleich Summary-Zeile „Versand", Trip Karte „Briefings laufen". Wird nicht gelöscht. |
| **AC-4** Versand-Abschnitt zeigt „Briefing-Zeiten", nicht „Rhythmus & Vorausschau"/„Zeitplan"/„Zeitfenster" | Die Überschrift „Briefing-Zeiten" gibt es im Produkt nicht mehr; geteilt (`VTSchedulePlan.svelte:75`) steht „Briefing-Zeitplan" mit Karten „Morgen-Briefing"/„Abend-Briefing" (`:93`, `:140`). Die Negativ-Prüfung auf „Zeitplan" kollidiert damit zwangsläufig und ist **veraltet** (Beleg: `:75`). Die Negativ-Prüfungen auf „Rhythmus & Vorausschau", „Zeitfenster" und den Stundenbereich bleiben gültig. | **Gilt weiter, umformuliert:** positiv „Briefing-Zeitplan" + „Morgen-Briefing"/„Abend-Briefing" (geteilter Baustein, beide kinds); negativ „Rhythmus & Vorausschau", „Zeitfenster"; Stundenbereich „7–16 Uhr" nur im vergleich-Zweig (nur der Vergleichs-Seed trägt `hour_from/hour_to`). Die in der Ratsche genannte Ist-Fläche „Geplantes Briefing · Kanäle" wird im RED gegen den gerenderten Text gelesen; ein Quelltext-`grep` ist nötig, bevor sie als Erwartung übernommen wird. |
| **AC-8** Vorschau-Daten-Text | Im aktuellen Dateistand bereits nur noch ein Kommentar (`:216-218`): Vorschau-Reiter per #1743 ersatzlos entfallen (PO-Entscheid 2026-10-22). Es gibt keinen Fall mehr zu portieren. | **Entfällt mit dem Produkt, mit Beleg.** Die Abwesenheit sichert VB-8 (kein `-tab-vorschau`, kein `-tab-versand`). |
| **AC-10** genau fünf Reiter klickbar, Panel sichtbar; kein Versand-/Vorschau-Reiter | Die Zusicherung stimmt weiter (`REITER_DEFINITION`, `subscriptionTabs.ts:34-43`: Übersicht, Punkte-Reiter, Wetter-Metriken, Wertebereiche, Alarme). Der in der Ratsche genannte Fehler war ein Zeitlimit in `apiRequestContext.delete` (Aufräumen), kein Assertion-Fehler. `hub-tab-bar.spec.ts` deckt 5 Reiter und Vorschau-Abwesenheit je kind (`:115`, `:130-133`), **nicht** die Abwesenheit von `-tab-versand` und nicht „jeden Reiter anklicken, Panel sichtbar". | **Gilt weiter, Lücke wird geschlossen:** VB-8 je kind (Klick-Schleife über alle fünf Reiter, Panel sichtbar, `-tab-versand`/`-tab-vorschau` `toHaveCount(0)`); Anzahl-Prüfung bleibt in `hub-tab-bar`. Aufräumen nutzt `seedHub().aufraeumen()` im `finally`. |
| AC-1, AC-5, AC-6, AC-7, Fix-Loop 1, Draft „—" (grün) | Stat/„Bearbeiten →"/`?tab=`/„Kein Score, kein Ranking" sind Vergleichs-Übersicht (`CompareTabs.svelte:772-775`, `:866`, `:855`); Trip hat „Briefings laufen" und „Zeitplan bearbeiten →" (`HubOverview.svelte:139-147`). | Je kind mit eigenem Zweig bzw. gemeinsam (siehe Zuordnung). |

### Frage 2 — Deckt `hub-send-dialog-target.staging.spec.ts` den #2283-Fall ab?

**Nein.** Die Staging-Spec prüft einen anderen Weg und eine andere Vorbedingung: Öffnen des Sende-Dialogs über das **Listen-Menü** (`liste.url`, `oeffneMenuepunkt`, `hub-send-dialog-target.staging.spec.ts:131-134`) bei einem Objekt **ohne zustellbares Ziel** (`seedOhneZiel`, `:62-75`; SD-1/SD-2 sperren „Senden"). Der #2283-Fall in `compare-hub-versand-inline.spec.ts:384-419` geht über den **Hub-Kopf** (`subscription-hub-send`) mit zustellbarem Ziel.

Die Zusicherung ist aber **zum größten Teil schon geratscht** abgedeckt: `hub-kopf-aufbau.spec.ts` KA-5 (`:315-372`, je kind, über `testMitZustellbaremZiel`) prüft: Versand-Abschnitt ohne `-activation-testsend`/„Test-Briefing" (`:341-342`), Hub-Kopf-„Senden" → Dialog → „Ja", genau **ein** Sende-Abruf, stabil, an diese Objekt-URL (`:344-366`). Zwei Lücken gegenüber dem Alt-Fall bleiben und werden geschlossen:
1. **„Der Sende-Abruf trägt keine Empfänger im Körper"** (`not.toMatch(/@/)`, Alt `:418`) — sichert die Regel „kein systemseitiges ‚an mich'; der Server sendet an die konfigurierten Empfänger dieses Nutzers". Fehlt in KA-5 (es zählt nur URLs).
2. **Desktop-Viewport** (KA-5 läuft mobil).

**Entscheidung:** Alt-Fall wird **gelöscht, nicht neu geschrieben**; stattdessen kommt in `hub-kopf-aufbau.spec.ts` ein Fall `KA-5b (kind)` (Desktop 1280×900, Körper des Sende-Abrufs gesammelt und auf „kein `@`" geprüft; zusätzlich `kind`-Query-Parameter). Kein Volltext-Neuschrieb.

### Frage 3 — Gibt es im Trip-Hub ein Kebab mit Pausieren (Lost-Update F004)?

**Ja.** `trips/[id]/+page.svelte:329-333` mountet `SubscriptionKebab` mit `subscriptionActions('trip', lifecycle, 'hub')` (aktiv: `pause`, `archive`, `delete`; `subscriptionActions.ts:68`); `handleHubAction('pause')` ruft `sendStateUpdate(true, …)` (`:288-290`), und der **flusht zuerst** offene Speichervorgänge (`tripSaveCtl.flush()`, `:181-183`, #1433). F004 („Feld-Edit VOR dem Kebab-Pausieren darf nicht verloren gehen") hat also ein **echtes Trip-Pendant** — kein Compare-Eigenfall. Der Ortsvergleich-Hub hat denselben Kebab (`compare/[id]/+page.svelte:403`, Beschriftungen aus derselben `subscriptionActions`: „Pausieren"/„Fortsetzen").

**Unterschied im Übertragungsweg (Pflicht-Beachtung für die Assertion):** Der Trip pausiert per `PATCH /api/trips/{id}/state` mit `{paused}` (`setPaused('trip', …)`) und führt die Uhrzeit in `report_config.morning_time`; der Ortsvergleich per `PUT` mit `{schedule, previous_schedule}` und `morning_time` (so auch dokumentiert in `hub-alarme-speichert-selbst.spec.ts:19-20, 46, 64, 73-74`). Daraus folgt:
- **Gemeinsam (beide kinds):** Server-Stand nach Neuladen = neue Uhrzeit **und** Status pausiert; Menüpunkt wechselt auf „Fortsetzen"; die Reihenfolge „Feld-Schreibvorgang vor Status-Schreibvorgang" (Reihenfolge der beantworteten Abrufe).
- **Nur wo der Übertragungsweg gleich ist:** „der Pausier-Abruf trägt die zuvor geänderte Uhrzeit im Körper" (Alt `:348-353`) gilt **nur für `vergleich`** (voller PUT). Für `route` gilt stattdessen: Status-Körper trägt **nur** `{paused}` (Muster #2375, wie `hub-alarme-speichert-selbst` AS-3) und die Uhrzeit steht im Server-Stand (Beweis: kein Überschreiben). Ein Trip-Zweig, der den PUT-Körper prüft, wäre falsch.
- **Zwei verschiedene Einstiegspunkte im Ortsvergleich:** Der **Kebab** läuft über `toggleActiveFromParent`, die **Aktivierungs-Karte** (`compare-hub-activation-cta`) über `handleToggleActive` mit eigenem Flush. Die Alt-Fälle `versand-speichert-selbst` AC-7 und `versand-inline` F002 pausieren **über die Karte**; sie werden deshalb als vergleich-Karten-Zweig erhalten (VS-3, VI-5), zusätzlich zum gemeinsamen Kebab-Fall beider kinds. Die Karte gibt es nur im Ortsvergleich (`WetterMetrikenVersandPanel.svelte:26`, `VersandTab.svelte:445`).

## Kind-Kontraste (compare-eigen vs. gemeinsam)

| Fall | route (Trip) | vergleich | Begründung des Zweigs |
|---|---|---|---|
| Laufzeit / Enddatum | `VTLaufzeitRoute`: schreibgeschützt, „Läuft mit der Trip · endet <letztes Etappendatum>", Button „Etappen öffnen →" (`VTLaufzeitRoute.svelte:20-31`); kein PUT beim Öffnen/Klick auf „Etappen öffnen" | `VTLaufzeitVergleich`: „Bis auf Weiteres"/„Bis Datum", editierbar, Sentinel `end_date=""` (`VTLaufzeitVergleich.svelte:44-70`) | Das Datenmodell unterscheidet sich (Enddatum aus Etappen vs. eigenes Feld, Epic #2345 P7 vormals #1230). Beide Zweige prüfen ihre eigene Zusicherung. |
| Pausieren | Kebab (PATCH `/state`); Status-Pille ohne `data-status` (das Attribut gibt es nur an `CompareStatusPill` und `SubscriptionCard`) ⇒ Trip prüft Menüpunkt-Wechsel und Server-Stand | Kebab (PUT) **und** Aktivierungs-Karte `compare-hub-activation-card/-cta` (Status „Aktiv", Copy „bis du pausierst") mit Pille `[data-status]` | Karte ist Slot von `VersandTab` nur im Vergleich-Hub (`CompareTabs.svelte:1035-1045`); beide Wege nutzen denselben Hub-Schreiber, aber verschiedene Einstiegspunkte (Frage 3). |
| Kanal-Testids und Feld | `channel-telegram`/`channel-email`/`channel-sms`; Server-Feld `report_config.send_telegram` (`VersandTab.svelte:163, 372-386`) | `compare-step5-channel-*` (`VersandTab.svelte:421-423`); Server-Feld `send_telegram` am Preset | nur Selektor-/Feldpfad-Tabelle, Verhalten gleich. |
| Übersicht Briefing-Angabe | Karte „Briefings laufen": zwei `ReportLine`-Zeilen „Morgen-Briefing"/„Abend-Briefing", je mit Zeit `HH:00` (ggf. ` (TZ)`) und Punkt (aktiv `--g-good`, inaktiv `--g-rule`); es gibt **keinen** zusammengesetzten Text „Morgen … · Abend …" und keinen „—"-Zustand (`ReportLine.svelte:13-25, 46-53`, `HubOverview.svelte:41-48, 141-142`) | Stat `compare-detail-stat-briefings` mit zusammengesetztem Text „Morgen 07:00 · Abend 18:00" bzw. „—" (`subscriptionHelpers.ts:305-311`); mobil Summary-Zeile „Versand" | beide Hubs rendern die Angabe in eigenen Übersichtskomponenten; ein Angleichen des Trip-Formats an das Vergleichs-Format wäre eine Produktänderung und nicht Gegenstand dieser Scheibe. |
| „Bearbeiten →" Versand | „Zeitplan bearbeiten →" (`HubOverview.svelte:145`) → Reiter Wetter-Metriken + `#versand` | `compare-hub-versand-edit` „Bearbeiten →" (`CompareTabs.svelte:866`) | Selektor-Tabelle, gleicher Zielvertrag. |
| „Kein Score, kein Ranking" (Idealwerte-Karte) | – | Text nur in der Vergleichs-Übersicht (`CompareTabs.svelte:855`) | Ranking-Neutralität betrifft nur den Ortsvergleich; **echtes** Compare-Eigen. |
| Stundenbereich `7–16 Uhr` nicht sichtbar | Trip hat kein `hour_from/hour_to` | Preset-Seed trägt `hour_from=7`, `hour_to=16` | Eine Negativ-Prüfung ohne Vorhandensein des Gegenstands wäre durch keine Mutation fangbar → nur im vergleich-Zweig. |
| Create-Flow-POST `/compare/new` | – | Wizard `CompareEditor` (Alt-Bestand, fällt mit #2243/S4) | siehe AC-11. |
| Stundenverlauf-Schalter (Alt Staging-F001) | – | Layout-Option des Vergleichs-Mailtemplates | **bereits in S3a MS-2** (`hub-wetter-metriken-speichert-selbst.spec.ts:250-273`) — Deckung, kein Neuschrieb. |

## Befunde (am Code gemessen, 2026-10-28)

1. **Vier Neu-Specs statt fünf Altdateien.** Messung Altbestand: `compare-versand-speichert-selbst` 316 Z./5 Fälle (geratscht), `compare-hub-versand-inline` 420 Z./8 Fälle (nicht geratscht, eigener `storageState` `staging-1256-s7.json`, im CI-Stack nicht lauffähig), `compare-hub-briefing-times` 263 Z./9 Fälle (nicht geratscht, Messungstexte veraltet), `versand-tab-vergleich` 313 Z./9 Fälle (nicht geratscht, Regel-2-Altlast), `compare-editor-autosave` 501 Z./12 Fälle (davon 1 reiner Versand-Fall, 1 gemischter). Alle vier zu löschenden Dateien stehen im Worktree in `ALTLAST` (`test_e2e_compare_paritaet_waechter.py:53, 56, 68, 77`); `compare-editor-autosave` bleibt (`:47`).
2. **Nicht geratschte Altfälle werden geteilt UND geratscht neu geschrieben** (Setup über `seedHub`, Anmeldung über `storageState` aus `global.setup.ts`); damit gewinnt das Regressionsnetz (F004 war bisher ungeratscht, siehe Ratschen-Kommentar `ci_e2e_specs.txt:159-160`).
3. **Admin-Profil-Mutation entfällt.** Alt-AC-35 setzt `telegram_chat_id` im Profil des Test-Admins; Alt-AC-7 (`versand-tab-vergleich`) setzt `mail_to` und klickt mit `{force: true}` auf eine gesperrte Checkbox (#1510). Ersatz: `testMitZustellbaremZiel` (bestätigte Adresse ⇒ kein `force`) und `telegram_chat_id` des Wegwerf-Zweitnutzers **mit Wiederherstellung im `finally`**, weil der Nutzer worker-weit geteilt wird (`helpers.ts:265`, bei `workers: 1` eine Registrierung für KA-5, KA-5b, VA-3, VI-1). Seed-Besonderheit wie KA-5: die `e2e-loc-*` gehören dem Admin; der Zweitnutzer legt eigene Orte an (`createTestLocation`).
4. **`waitForTimeout`** in `versand-tab-vergleich.spec.ts:125` (Kommentar: „activeMetricKeys hydratisiert nur lazy beim Wetter-Metriken-Besuch") → beobachtbare Wartebedingung (`expect.poll` auf Sichtbarkeit der `alert-metric-level-table`). Der Umweg über Wetter-Metriken bleibt für beide kinds erhalten (1:1-Abbildung); nur der Schlaf wird ersetzt.
5. **Alt-Verweise:** Staging-Configs `playwright.1256-s7.staging.config.ts` (Zeile 23, einziger Fall `compare-hub-versand-inline`) und `playwright.1229-hub.staging.config.ts` (Zeile 27, einziger Fall `compare-hub-briefing-times`) werden mit ihren Zielen **gegenstandslos**; `playwright.1273-s4c.staging.config.ts` listet `versand-tab-vergleich` (Zeile 37) und `compare-editor-autosave` (Zeile 32).
6. **Quota:** Vergleiche sind pro Nutzer auf 2 aktive begrenzt (409); `seedHub('vergleich')` räumt strikt im `finally`; `workers: 1`.
7. **Keine Parallel-Lieferung** zu #2347 über S3a hinaus auf `origin/main`.

## Abgrenzung

Nicht in S3b: S3c (Konflikt-412 über zwei Kontexte), S3d (Radar, Stundenverlauf ×2, Hourly-Order, 682-Mobile, Rest `compare-hub-inline-edit`/`compare-editor-autosave`, `.staging`-Specs), S4. **VS-2 ist die reiter-lokale 412-Behandlung** aus `versand-speichert-selbst` AC-6 (wie S3a WS-4/MS-5) und gehört deshalb in diese Scheibe; S3c ist die Zwei-Kontexte-Spec `compare-konfliktschutz-zwei-kontexte`. `compare-editor-autosave` **bleibt in `ALTLAST`**: nur sein Versand-Anteil (AC-14 „Versand") wandert; die Orte-/Gesten-Fälle (AC-5/6/7/8/9/10/F001, Wertebereich-Fälle) bleiben unverändert und wandern in S3d. Trip-Dateien mit Dopplungen bleiben unverändert (Sammelposten S4).

## Estimated Scope

- **LoC (Testcode, netto):** ca. +1.250 / −1.350 (4 neue Specs ≈ 1.200; gelöscht: 4 Altdateien = 1.312 Zeilen, plus ≈ 35 Zeilen aus `compare-editor-autosave`; Ergänzungen KA-5b ≈ 40, slice3 ≈ 55). Nur Testcode/Doku. Ob Testdateien in das LoC-Limit 250 zählen, liefert `workflow.py status` (`LoC-Delta`): zählen sie, ist `loc_limit_override` ≥ 1.500 nötig; zählen sie nicht, ist kein Override nötig.
- **Files:** ca. 17 (4 neu, 4 gelöscht, 2 Staging-Configs gelöscht, 1 Staging-Config geändert, `hub-kopf-aufbau`, `compare-editor-slice3`, `compare-editor-autosave`, Wächter, Ratsche, `ci.yml`, Gate-Doku).
- **Effort:** high (1:1-Zuordnung, Neumessung, Mutations-Gegenprobe je Zusicherung und kind, Trip-Pendants erstmals gemessen).
- **Risiko:** MEDIUM — (1) Zusicherungsverlust bei F004/412 (Regressionsnetz #2276/#2277); (2) Trip-Pendants können rot sein (Produktlücke, AC-13); (3) Registrierungsbremse, Quota und geteiltes Zweitnutzer-Profil; (4) Übertragungsweg-Unterschied Pausieren (PATCH `/state` vs. PUT) und zwei Einstiegspunkte im Ortsvergleich verleiten zu falsch-gleichen Assertions; (5) `hub-kopf-aufbau` ist geratscht — die Ergänzung KA-5b darf KA-5 nicht destabilisieren; (6) CI-Zeit `e2e` ≈ 14 min.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/e2e/helpers.ts` (`HubKind`, `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `testMitZustellbaremZiel`, `createTestLocation`) | module | Basis jeder neuen Spec (S1/S2/KA-5) |
| `hub-versand-autosave-chip.spec.ts` (S1), `hub-alarme-speichert-selbst.spec.ts` (S3a, Auslöser-Tabelle Alarm/Pausieren), `hub-kopf-aufbau.spec.ts` (KA-5), `hub-tab-bar.spec.ts` | module | Vorbilder und Deckungsbelege (`zaehlePuts`, `expect.poll`-Stabilitätsfenster) |
| `VersandTab`, `VTSchedulePlan`, `VTBriefingChannels`, `VTLaufzeitRoute`, `VTLaufzeitVergleich`, `WetterMetrikenVersandPanel`, `BriefingScheduleTab`, `CompareTabs.svelte`, `HubOverview.svelte`, `ReportLine.svelte`, `SubscriptionKebab`/`subscriptionActions`, `saveController` | module | geprüfte Bausteine (unverändert, außer AC-13) |
| `frontend/e2e/global.setup.ts` | module | Admin-`storageState`, Seed-Orte |
| `.github/ci_e2e_specs.txt`, `ci.yml` Job `e2e`, `.github/scripts/e2e_gate.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CI | Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | test | `ALTLAST`, `ALTLAST_MAX` |
| `docs/reference/gates_und_ratschen.md` | doc | Wächter-/Ratschen-Doku |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/hub-versand-speichert-selbst.spec.ts` | CREATE | VS: Reiterwechsel-Flush, 412, Pausieren-Flush (Kebab + Karte), Roundtrip, zwei Aktionen, Laufzeit-Kontrast |
| `frontend/e2e/hub-versand-inline-bearbeiten.spec.ts` | CREATE | VI: Kanal-Switch, Uhrzeit inline, Pausieren-Pfade (Kebab, Karte), F004 |
| `frontend/e2e/hub-versand-aufbau.spec.ts` | CREATE | VA: Abschnittsaufbau, Alert-Zustellung nur im Alarme-Reiter, Leerzustand, mobil |
| `frontend/e2e/hub-versand-briefing-zeiten.spec.ts` | CREATE | VB: Übersicht-Briefing-Angabe, Überschriften, Neutralisierung, „Bearbeiten →", `?tab=`, Reiter-Klick-Schleife |
| `frontend/e2e/hub-kopf-aufbau.spec.ts` | MODIFY | neuer Fall KA-5b (Desktop, Körper ohne Empfänger); KA-5 unverändert |
| `frontend/e2e/compare-editor-slice3.spec.ts` | MODIFY | Fall „Create-Flow sendet Slot-Felder + official_warnings" (Alt `versand-tab-vergleich` AC-6) angehängt; `gz-eigenstaendig:`-Kopf um Verweis ergänzt |
| `frontend/e2e/compare-editor-autosave.spec.ts` | MODIFY | nur Fall `AC-14 (Versand)` entfernt; Rest unverändert (S3d) |
| `frontend/e2e/compare-versand-speichert-selbst.spec.ts`, `compare-hub-versand-inline.spec.ts`, `compare-hub-briefing-times.spec.ts`, `versand-tab-vergleich.spec.ts` | DELETE | erst nach grünem Lauf der neuen Specs und 1:1-Abgleich |
| `frontend/playwright.1256-s7.staging.config.ts`, `frontend/playwright.1229-hub.staging.config.ts` (+ zugehörige Setup-Dateien, sofern sonst ungenutzt) | DELETE | Ziele entfallen; per `grep` am Endstand belegen |
| `frontend/playwright.1273-s4c.staging.config.ts` | MODIFY | Zeile `versand-tab-vergleich` entfernen |
| `.github/ci_e2e_specs.txt` | MODIFY | `compare-versand-speichert-selbst` raus, vier `hub-versand-*` rein; Aufnahme-Kommentar mit Filter-A/B/C-Ergebnis, Ratschen-Befundblock (briefing-times/inline) fortschreiben |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_SPECS` (erwartet 71), `E2E_MIN_EXECUTED_HAUPT` neu gemessen |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | vier Namen aus `ALTLAST`, `ALTLAST_MAX` 34 → 30, Docstring-Messzeile |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Wächter-Zahl „S3b: 30" |
| `frontend/e2e/helpers.ts` | MODIFY (optional) | nur Konstanten ohne Assertions, falls mehrere Specs dasselbe brauchen |

### Estimated Changes
- Files: ca. 17
- LoC: +1.250 / −1.350 (Testcode)

## Implementation Details

Jeder Fall läuft als `for (const kind of HUB_KINDS) test(\`<ID> (${kind}): …\`)`; Testtitel tragen `kind`. Setup immer `seedHub(request, kind, { extra })` (flaches Überlagern, `display_config` wird ersetzt, nicht gemergt), Öffnen mit `openHub(page, kind, id, { tab: 'wetter-metriken', hash: 'versand' })`, Aufräumen im `finally`. Wartebedingungen ausschließlich `page.waitForResponse`, `expect.poll`, `toHaveAttribute`, `toHaveCount` — kein `waitForTimeout`, kein `skip`, kein UI-`login()`, kein fester `storageState`-Pfad. Selektor-Unterschiede (Kanal-Testids, Laufzeit-Testids, Übersicht) stehen als kleine lokale kind-Tabelle in der jeweiligen Spec; Gemeinsames kommt aus `HUB_SEL`. „Genau ein PUT" wird als Stabilitätsfenster per `expect.poll` geprüft (Muster `hub-versand-autosave-chip`). Pausieren-Abrufe werden je kind nach Übertragungsweg erkannt (PUT vs. PATCH auf `…/state`, Muster `hub-alarme-speichert-selbst`). **Erwartungswerte stehen in der Spec fest** (aus dem Seed abgeleitet), nie aus dem gerenderten Produkt gelesen; der RED-Lauf prüft nur, ob sie am Ist-Stand stimmen.

### Fälle je neue Spec

**`hub-versand-speichert-selbst.spec.ts` (VS)**
- VS-1 Uhrzeit ändern, sofort Reiter „Alarme", dort Alarm-Änderung (Auslöser-Tabelle aus `hub-alarme-speichert-selbst`: Trip z. B. `alert-cooldown-input`, Vergleich `alarme-radar-toggle`) ⇒ BEIDE Änderungen im Server-Stand; Reiterwechsel hat den Versand-Vorgang bereits abgesendet (Alt `versand-speichert-selbst` AC-4)
- VS-2 Fremde Änderung ohne If-Match dazwischen, zweite Versand-Änderung ⇒ echter 412, Chip `conflict`, Oberfläche springt nicht zurück, „Nochmal speichern" ⇒ idle „Gespeichert", Wiederholungs-Abruf 200, Server-Stand trägt die Änderung (Alt AC-6; Trip-Fremdschreiber `PUT /api/trips/{id}` ohne If-Match)
- VS-3 Uhrzeit ändern und sofort pausieren ⇒ Server-Stand pausiert **und** neue Uhrzeit (Alt AC-7). Beide kinds über den Kebab (Übertragungsweg je kind, Frage 3); **zusätzlich vergleich-Zweig über die Aktivierungs-Karte** (`compare-hub-activation-cta`), weil der Alt-Fall genau diesen Einstiegspunkt (`handleToggleActive`) bewacht
- VS-4 Uhrzeit ändern ⇒ alle übrigen Einstellungen nach Neuladen unverändert (Alt AC-11): Vergleich: Alert-Cooldown 45, Stille Stunden 22:00–07:00, alle Felder außer `morning_time`/`display_config`/`updated_at`/`etag`, plus Region/Wertebereiche/Kurzstil/Metrikanzahl in `display_config`; Trip: `report_config` ohne `morning_time`, Alert-Felder, Etappen, Name
- VS-5 Zwei Versand-Aktionen nacheinander (Uhrzeit, dann Kanal oder Abend-Slot) ⇒ genau zwei PUTs, beide persistent (Versand-Hälfte aus Alt `compare-editor-autosave` AC-6; die gemischte Orte+Versand-Folge bleibt in der Alt-Datei, S3d)
- VS-6 *(route)* Laufzeit schreibgeschützt: Anzeige „endet <letztes Etappendatum>", „Etappen öffnen →" wechselt in den Etappen-Reiter, **kein** PUT beim Öffnen/Klick
- VS-7 *(vergleich)* „Bis auf Weiteres" per reinem Klick bei gesetztem Enddatum: PUT-Körper `end_date === ""`, Chip idle, Server-Stand `end_date` **undefined** (`toBeUndefined`, nie `toBeFalsy`), `aria-selected` nach Neuladen, Hinweis „ohne Enddatum" (vereint Alt AC-5, F001 und `versand-tab-vergleich` AC-3 — die strengste Fassung gilt)
- VS-8 *(vergleich)* „Bis Datum" + Datum setzen ⇒ `end_date` persistiert (Alt `versand-tab-vergleich` AC-3b; Datum relativ zum Lauf in der Zukunft, nicht festes Kalenderdatum)

**`hub-versand-inline-bearbeiten.spec.ts` (VI)**
- VI-1 Telegram-Kanal-Switch im Versand-Abschnitt: Vorbedingung `telegram_chat_id` des Wegwerf-Zweitnutzers **lesen, setzen, im `finally` wiederherstellen**; Schalter enabled und nicht gesetzt, Klick ⇒ sofort gesetzt, PUT ok, Körper trägt den Kanal (Vergleich `send_telegram === true`; Trip `report_config.send_telegram === true`), nach Neuladen gesetzt (Alt AC-35; Selektor `channel-telegram` vs. `compare-step5-channel-telegram`)
- VI-2 Briefing-Uhrzeit inline ändern ⇒ PUT ok, Körper trägt `09:00`, URL bleibt, **kein** `/edit`, nach Neuladen `09:00` (Alt AC-36)
- VI-3 Pausieren über den Kebab: Menüpunkt „Pausieren" ⇒ Menüpunkt wird „Fortsetzen", URL bleibt, kein Redirect, Server-Stand pausiert; *vergleich zusätzlich:* Status-Pille `[data-status]` verlässt `active` (das Attribut existiert im Trip-Hub nicht, dort wird kein Pille-Check gefordert) (gemeinsamer Teil von Alt AC-37/17/18)
- VI-4 *(vergleich)* Aktivierungs-Karte: Status „Aktiv", CTA „Pausieren", Copy „bis du pausierst", kein Enddatum-Feld dort; CTA-Klick ⇒ PUT ok, CTA „Aktivieren", zweiter Klick zurück auf „Pausieren" (Alt AC-37/17/18, Karten-Anteil; Begründung: Karte existiert nur im Vergleich-Hub)
- VI-5 Uhrzeit ändern + sofortiges Pausieren **ohne Wartepunkt**: beide kinds über den Kebab; *vergleich-Zweig zusätzlich über die Karte* (Alt F002, Stresstest für die gemeinsame Schreib-Warteschlange) ⇒ beide persistieren, nach Neuladen Uhrzeit **und** pausiert
- VI-6 Uhrzeit ändern, PUT abwarten, dann Kebab „Pausieren" (F004): Server-Stand nach Neuladen trägt neue Uhrzeit **und** pausiert; *vergleich:* der Pausier-PUT-Körper enthält `schedule === 'manual'` und die zuvor geänderte Uhrzeit; *route:* der Status-Abruf (PATCH `…/state`) trägt nur `{paused}` und überschreibt die Uhrzeit nicht. Aufräumen: Kebab „Fortsetzen" (Alt F004)

**`hub-versand-aufbau.spec.ts` (VA)**
- VA-1 Versand-Abschnitt zeigt Kanäle → Zeitplan (Morgen-Slot-Schalter) → Laufzeit; keine Alert-Zustellung (`alert-cooldown-card` `count 0`); Laufzeit-Block `briefings-laufzeit` (route) bzw. `briefings-laufzeit-vergleich` (vergleich) (Alt AC-1)
- VA-2 Alarme-Reiter enthält Cooldown-Karte und Level-Tabelle (Seed mit aktiver Metrik), Versand-Abschnitt keins von beidem (Alt AC-4; derselbe Umweg über Wetter-Metriken wie im Alt-Fall, aber `waitForTimeout(300)` ersetzt durch Wartebedingung auf die hydratisierte Tabelle)
- VA-3 Alle Kanäle aus ⇒ Leerzustand `briefings-channel-empty` statt Zeitplan-Karten (Alt AC-7; Vorbedingung bestätigte Adresse über `testMitZustellbaremZiel`, **ohne** `{force: true}` und ohne Admin-Profil-Änderung)
- VA-4 Mobiler Viewport 390×844: Versand-Abschnitt ohne horizontales Scrollen (Alt AC-10)

**`hub-versand-briefing-zeiten.spec.ts` (VB)** — Seed: beide Slots aktiv, Morgen 07:00, Abend 18:00 (Erwartung aus dem Seed, nicht aus dem Produkt).
- VB-1 Übersicht Desktop zeigt die Briefing-Angabe: *vergleich:* Stat `compare-detail-stat-briefings` exakt „Morgen 07:00 · Abend 18:00"; *route:* Karte „Briefings laufen" mit Zeile „Morgen-Briefing" und Zeit `07:00` (Muster `^07:00( \(.+\))?$`, `slotZeit` hängt bei bekanntem Briefing die Zeitzone an) und Zeile „Abend-Briefing" mit `18:00`; beide Punkte im aktiven Zustand (Alt AC-1)
- VB-2 Übersicht mobil (390×844): dieselbe Angabe an der **tatsächlichen mobilen Stelle** — *vergleich:* Summary-Zeile „Versand" (Titel `hub-summary-row-title` „Morgen 07:00 · Abend 18:00"), der Desktop-Stat steht **nicht** (Deckung `hub-tab-bar.spec.ts:258-265`); *route:* dieselbe Karte „Briefings laufen" wie am Desktop (`HubOverview` wird in beiden Breiten gerendert, `TripTabs.svelte:191`), Zeilen sichtbar (Alt AC-2, umformuliert)
- VB-3 Versand-Abschnitt: positiv „Briefing-Zeitplan", „Morgen-Briefing", „Abend-Briefing"; negativ „Rhythmus & Vorausschau" und „Zeitfenster"; *vergleich-Zweig:* auch der Stundenbereich „7–16 Uhr" nicht (Alt AC-4, umformuliert; „Zeitplan"-Negativprüfung entfällt mit Beleg `VTSchedulePlan.svelte:75`)
- VB-4 Übersicht-Panel ohne Rhythmus-Sprache: kein „Rhythmus", kein „Zeitfenster"; *vergleich-Zweig:* kein „7–16 Uhr", kein „Zeitplan" (Trip trägt legitim „Zeitplan bearbeiten →", `HubOverview.svelte:145`) (Alt Fix-Loop 1)
- VB-5 „Bearbeiten →" der Versand-Karte (*route* „Zeitplan bearbeiten →", *vergleich* `compare-hub-versand-edit`) wechselt inline auf Wetter-Metriken, `versand-abschnitt` im Sichtfeld, URL bleibt der Hub, keine `/edit`-Route (Alt AC-5)
- VB-6 Unbekannter `?tab=`-Wert ⇒ Übersicht aktiv, kein Absturz; Wiederöffnen ohne `?tab=` ebenfalls (Alt AC-6)
- VB-7 *(vergleich)* Idealwerte-Karte zeigt „Kein Score, kein Ranking", nicht „bestimmen das Ranking" (Alt AC-7; Begründung: Text existiert nur in der Vergleichs-Übersicht)
- VB-8 Alle fünf Reiter (Übersicht, Punkte-Reiter je `HUB_SEL`, Wetter-Metriken, Wertebereiche, Alarme) nacheinander angeklickt, Panel je sichtbar; `-tab-versand` und `-tab-vorschau` `toHaveCount(0)` (Alt AC-10; Anzahl-Prüfung bleibt in `hub-tab-bar`)
- VB-9 Slot-aus-Fall (Alt Edge Case „Draft ohne Slots → —"): beide Slots aus ⇒ *vergleich:* Stat zeigt exakt „—" (nicht leer, kein verwaister Trennpunkt); *route:* die Karte „Briefings laufen" hat **kein „—"**, beide Zeilen bleiben mit ihrer Zeit stehen, und die Punkte beider Zeilen haben die Inaktiv-Farbe (`--g-rule`), die sich von der Aktiv-Farbe (`--g-good`) im Ausgangszustand unterscheidet (berechnete Hintergrundfarbe, Vergleich vorher/nachher am selben Element)
- Alt AC-8: **entfällt** (Vorschau-Reiter ersatzlos, #1743) — kein Fall, Beleg in der Zuordnung.

**Ergänzungen außerhalb der Neu-Specs**
- `hub-kopf-aufbau.spec.ts` KA-5b (je kind, Desktop 1280×900): Hub-Kopf-„Senden" → Dialog → „Ja" ⇒ genau ein Sende-Abruf an `/api/briefings/<id>/send?kind=<kind>…`; **Körper enthält kein `@`** (Alt `versand-inline` #2283, `:418`).
- `compare-editor-slice3.spec.ts`: Fall „Create-Flow sendet die 5 Slot-Felder + `official_warnings` im POST-Body an `/api/compare/presets`" (Alt `versand-tab-vergleich` AC-6, `:225-271`) unverändert in der Zusicherung (`morning_enabled true`, `morning_time 07:00:00`, `evening_enabled false`, `evening_time 18:00:00`, `end_date` fehlt/null, `official_warnings` = `{enabled:false}`). Begründung: gehört zum Alt-Wizard, der mit #2243/S4 ersatzlos fällt; die Datei trägt bereits den `gz-eigenstaendig:`-Kopf. **Übergabe an S4:** Wenn `/compare/new` nach dem Trip-Muster (Progressive-Tab-Anlegeseite) neu gebaut wird, übernimmt die dortige Anlege-Spec diese Zusicherung.

### Wächter, Ratsche, CI

- **Wächter:** `ALTLAST` verliert `compare-versand-speichert-selbst.spec.ts`, `compare-hub-versand-inline.spec.ts`, `compare-hub-briefing-times.spec.ts`, `versand-tab-vergleich.spec.ts`. `compare-editor-autosave.spec.ts` bleibt. `ALTLAST_MAX` Literal 34 → **30**. Docstring-Messzeile und `gates_und_ratschen.md` fortschreiben; Prüfdatum 2027-01-24 unverändert.
- **Ratsche:** `e2e/compare-versand-speichert-selbst.spec.ts` raus, vier `e2e/hub-versand-*`-Zeilen rein (alphabetisch). `E2E_MIN_SPECS` 68 → **71** (−1 +4); muss exakt `grep -c '^e2e/'` entsprechen. Die drei übrigen Alt-Dateien standen nicht auf der Liste.
- **`E2E_MIN_EXECUTED_HAUPT`:** am Endstand per `npx playwright test --list` über die Hauptlauf-Auswahl (ohne `bug-703`) **gemessen, nicht geschätzt**; Begründung im Kommentar fortschreiben. Der Ratschen-Befundblock (`ci_e2e_specs.txt:142-166`) wird für `compare-hub-briefing-times` und `compare-hub-versand-inline` auf „aufgenommen als `hub-versand-*` (#2347 S3b)" umgeschrieben (Zeiger umhängen, nicht löschen).
- **Verweis-Hygiene:** `grep -rn` auf die vier gelöschten Dateinamen und die zwei gelöschten Configs über `frontend`, `.github`, `tests` am Endstand: nur Historie in `docs/` darf bleiben.

### Reihenfolge in /50
1. Altbestand im CI-Stack neu messen (rote Altfälle = Befund; bei `briefing-times`/`versand-inline` Basismessung über die neuen Specs).
2. Neue Specs schreiben, dreimal grün (Filter B).
3. Mutations-Gegenprobe je Zusicherung und kind (Sicherungskopie extern, nur String-Ersetzung, nie `git checkout/stash/reset`).
4. **Erst bei Grün** Altdateien löschen, `compare-editor-autosave` kürzen, `slice3`/`hub-kopf-aufbau` ergänzen, Staging-Configs bereinigen.
5. Ratsche, Wächter, `--list`-Messung, Doku.

## Zuordnung alt → neu (Regressionsnetz, in /50 gegen `grep -c "^\s*test("` je Altdatei vervollständigt)

| Alt (Datei · Zusicherung) | Neu (Spec · Fall) | Anmerkung |
|---|---|---|
| `compare-versand-speichert-selbst` · AC-1 | schon S1 `hub-versand-autosave-chip` AC-1 | im Altfile bereits als ersetzt vermerkt (`:136-137`) |
| · AC-4 Uhrzeit + Reiterwechsel + Radar | VS-1 je kind | Auslöser-Tabelle |
| · AC-5 „Bis auf Weiteres" per Klick | VS-7 (vergleich), VS-6 (route-Kontrast) | `toBeUndefined` bleibt |
| · AC-6 412 + „Nochmal speichern" | VS-2 je kind | Trip im RED gemessen, sonst AC-13 |
| · AC-7 Uhrzeit + sofort pausieren (**über die Karte**) | VS-3 vergleich-Karten-Zweig **und** VS-3 Kebab je kind | beide Einstiegspunkte (Frage 3) |
| · AC-11 Rest unverändert | VS-4 je kind | |
| `compare-hub-versand-inline` · AC-35 | VI-1 je kind | Zweitnutzer mit Wiederherstellung statt Admin-Profil |
| · AC-36 | VI-2 je kind | |
| · AC-37/17/18 | VI-3 je kind + VI-4 (vergleich, Karte) | |
| · F001 | VS-7 (vergleich) | mit Alt AC-5/AC-3 vereint (strengste Fassung) |
| · F002 (**über die Karte**) | VI-5 Karten-Zweig (vergleich) + VI-5 Kebab je kind | |
| · F004 | VI-6 je kind | Lost-Update-Nachweis, jetzt geratscht |
| · #2283 Senden nur im Hub-Kopf | `hub-kopf-aufbau` KA-5 (Deckung) + KA-5b (neu) | `hub-send-dialog-target.staging` deckt es **nicht** (Frage 2) |
| `compare-hub-briefing-times` · AC-1, Draft „—" | VB-1, VB-9 | Trip-Format eigenes Ist-Format |
| · AC-2 (mobil) | VB-2 | umformuliert, Frage 1 |
| · AC-4 | VB-3 | umformuliert, „Zeitplan"-Negativ obsolet |
| · Fix-Loop 1 | VB-4 | |
| · AC-5 | VB-5 je kind | |
| · AC-6 | VB-6 je kind | |
| · AC-7 | VB-7 (vergleich) | compare-eigen |
| · AC-8 | entfällt (#1743) | Beleg `:216-218` |
| · AC-10 | VB-8 je kind + `hub-tab-bar` (Anzahl) | Lücke `-tab-versand` geschlossen |
| `versand-tab-vergleich` · AC-1 | VA-1 je kind | |
| · AC-3 | VS-7 (vergleich) | |
| · AC-3b | VS-8 (vergleich) | |
| · AC-4 | VA-2 je kind | `waitForTimeout` ersetzt |
| · AC-7 | VA-3 je kind | ohne `force` |
| · AC-10 | VA-4 je kind | |
| · AC-2 (Uhrzeit überlebt Reload) | S1 `hub-versand-autosave-chip` AC-1 (Deckung, `:46-70`) | Beleg im RED gelesen |
| · AC-6 Create-Flow | `compare-editor-slice3` (neuer Fall) | Wizard fällt in S4 |
| · Staging-F001 Stundenverlauf | S3a MS-2 (Deckung, `hub-wetter-metriken-speichert-selbst.spec.ts:250-273`) | |
| `compare-editor-autosave` · AC-14 (Versand) | S1 AC-1 + VS-5 | Deckung belegt; Fall aus Altdatei entfernt |
| · AC-6 (Ort + Versand-Zeit, zwei PUTs) | VS-5 (Versand-Hälfte); Fall bleibt in Altdatei (S3d) | gemischt, nicht verändert |
| · AC-5/7/8/9/10/F001, AC-14w, AC-1 (Warnen), F003 | bleiben (S3d) | Orte/Gesten-Gate/Wertebereich |

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Lauf des Wächters.
- **Output:** Versand-Abschnitt, Pausieren-Pfade und Übersicht-Briefing-Angabe werden für Trip und Ortsvergleich durch **dieselben** Specs mit denselben Zusicherungen geprüft (mit begründeten Kind-Kontrasten); die CI bewacht sie. Eine neue Compare-only-Versand-Spec wäre für den Wächter ein Verstoß.
- **Side effects:** Wegwerf-Daten `E2E-GZ-…` (Aufräumen im `finally`, Sicherheitsnetz `global.teardown.ts`); ein Wegwerf-Zweitnutzer über den worker-scoped Fixture (Profil wird nach Änderung wiederhergestellt); keine Produktdaten, kein Versand, keine Änderung am Admin-Profil.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich WHEN die Briefing-Uhrzeit geändert und sofort der Kebab-Punkt „Pausieren" gewählt wird THEN stehen neue Uhrzeit und Status „pausiert" im Server-Stand beider Objekte (`hub-versand-speichert-selbst`, VS-3).
- [ ] Test 2: GIVEN beide Objekte mit veraltetem Stand WHEN die zweite Versand-Änderung den Server erreicht THEN antwortet er 412, der Chip zeigt „Nochmal speichern", und dessen Klick speichert den bestätigten Stand (VS-2).
- [ ] Test 3: GIVEN der Versand-Abschnitt eines Trips und eines Ortsvergleichs WHEN die Übersicht, die Überschriften, „Bearbeiten →" und die Reiter geprüft werden THEN gelten die Ist-Texte beider Hubs (`hub-versand-briefing-zeiten`, VB-1..VB-9).
- [ ] Test 4: GIVEN der Hub-Kopf-Sende-Dialog (Desktop) WHEN „Senden" bestätigt wird THEN geht genau ein Abruf ohne Empfänger im Körper hinaus (`hub-kopf-aufbau`, KA-5b).
- [ ] Test 5: GIVEN der Wächter WHEN der Unit-Test läuft THEN hat `ALTLAST` 30 Einträge und `ALTLAST_MAX` ist 30.
- [ ] Test 6: GIVEN die Positivliste WHEN der Bindungstest läuft THEN entspricht `E2E_MIN_SPECS` (71) der Listenlänge und jede Zeile verweist auf eine vorhandene Datei.

## Acceptance Criteria

- **AC-1:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer im Versand-Abschnitt die Uhrzeit ändert und sofort den Reiter wechselt, die zweite Änderung auf einem veralteten Stand sendet (Server-Konflikt 412), eine zweite Versand-Aktion nachlegt oder die Änderung durch „Übrige Felder unverändert" prüft / Then gilt für Trip UND Ortsvergleich: der Reiterwechsel flusht die ausstehende Änderung, bei 412 zeigt der Chip „Nochmal speichern" ohne Rücksprung der Oberfläche und die Wiederholung speichert den bestätigten Stand, zwei Aktionen lösen genau zwei Speicher-Aufrufe aus, und alle übrigen Einstellungen (Alert-Felder, Metriken, Wertebereiche, Etappen bzw. Orte, Name) bleiben nach dem Neuladen unverändert.
  - Test: `hub-versand-speichert-selbst.spec.ts` (VS-1, VS-2, VS-4, VS-5).
  - Mutation (je kind getrennt): Flush beim Reiterwechsel entfernen → VS-1 rot; 412-Behandlung im Versand-Speicherweg auf generischen Fehler umstellen → VS-2 rot; Teil-Nutzlast statt Voll-Objekt senden (Alert-Legacy-Felder nullen) → VS-4 rot; Speicher-Aufruf doppelt auslösen → VS-5 rot; Trip-Hub: `saveController` des Versand-Wrappers nicht verdrahten → nur Trip-Fälle rot.
- **AC-2:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer die Briefing-Uhrzeit ändert und sofort pausiert (beide kinds über den Kebab, beim Ortsvergleich zusätzlich über die Aktivierungs-Karte), und alternativ zuerst den Speicher-Aufruf abwartet und dann über den Kebab pausiert / Then stehen für Trip UND Ortsvergleich nach dem Neuladen die neue Uhrzeit und der Status „pausiert" im Server-Stand, der Menüpunkt zeigt „Fortsetzen", der Feld-Schreibvorgang liegt vor dem Status-Schreibvorgang, und der Trip-Status-Abruf trägt nur den Status (PATCH `/state`), während der Ortsvergleich-Pausier-Aufruf zusätzlich die zuvor geänderte Uhrzeit im Körper trägt — jeder Zweig prüft den Übertragungsweg und den Einstiegspunkt seines kinds (Lost-Update F004 nicht verloren).
  - Test: `hub-versand-speichert-selbst.spec.ts` (VS-3) und `hub-versand-inline-bearbeiten.spec.ts` (VI-5, VI-6).
  - Mutation: im Trip-Hub `tripSaveCtl.flush()` in `sendStateUpdate` entfernen → VS-3/VI-5/VI-6 (route) rot; im Ortsvergleich den Flush im Karten-Handler (`handleToggleActive`) entfernen → nur die Karten-Zweige VS-3/VI-5 (vergleich) rot; den Flush im Kebab-Einstieg (`toggleActiveFromParent`) entfernen → nur die Kebab-Fälle (vergleich) rot; Pausier-Schreiber mit veralteter Baseline senden lassen → VI-6 (vergleich) rot; Reihenfolge der Schreibvorgänge vertauschen → beide kinds rot.
- **AC-3:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich, der Wegwerf-Zweitnutzer mit eigener, im `finally` wiederhergestellter `telegram_chat_id` / When der Nutzer im Versand-Abschnitt den Telegram-Kanal-Schalter setzt und die Briefing-Uhrzeit inline ändert / Then wirkt der Schalter sofort, ein Speicher-Aufruf geht mit dem gesetzten Kanal hinaus (Ortsvergleich `send_telegram`, Trip `report_config.send_telegram`), die Uhrzeit-Änderung speichert ohne Navigation (kein `/edit` in der Adresse), beide Werte überstehen das Neuladen — für Trip UND Ortsvergleich; das Admin-Profil bleibt unverändert, und das Profil des Zweitnutzers hat nach dem Fall wieder seinen Ausgangswert, sodass KA-5, KA-5b und VA-3 im selben Worker unbeeinflusst laufen.
  - Test: `hub-versand-inline-bearbeiten.spec.ts` (VI-1, VI-2).
  - Mutation: Kanal-Schalter fest `disabled` verdrahten → VI-1 des betroffenen kind rot; Kanalfeld nicht in den Speicher-Aufruf übernehmen → VI-1 rot; Uhrzeit-Handler navigiert nach `/edit` → VI-2 rot; Wiederherstellung im `finally` weglassen → Folgefall mit Telegram-Vorbedingung (VA-3/KA-5) rot bzw. Profil-Prüfung am Fallende rot.
- **AC-4:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer über den Kebab pausiert und fortsetzt, und beim Ortsvergleich zusätzlich über die Aktivierungs-Karte / Then wechselt für beide kinds der Menüpunkt zwischen „Pausieren" und „Fortsetzen" ohne Adresswechsel und der Server-Stand folgt; nur beim Ortsvergleich verlässt zusätzlich die Status-Pille `[data-status]` den Zustand `active`, und die Karte zeigt „Aktiv", „Pausieren", die Copy „bis du pausierst", kein Enddatum-Feld, wobei der CTA-Klick pausiert und wieder aktiviert (Zweig bleibt bestehen, weil Karte und Pille im Trip-Hub nicht existieren; der Trip prüft stattdessen Menüpunkt und Server-Stand).
  - Test: `hub-versand-inline-bearbeiten.spec.ts` (VI-3, VI-4).
  - Mutation: Menüpunkt-Beschriftung nach Pausieren nicht wechseln → VI-3 des kind rot; Karten-CTA ohne PUT → nur VI-4 rot.
- **AC-5:** Given der Hub-Kopf mit zustellbarem Ziel (Wegwerf-Zweitnutzer) / When der Nutzer auf dem Desktop im Kopf „Senden" wählt und bestätigt / Then geht für Trip UND Ortsvergleich genau ein Sende-Abruf an dieses Objekt (richtiger `kind`) hinaus und der Körper enthält **keinen** Empfänger (kein `@`); der Versand-Abschnitt hat kein „Test-Briefing" mehr. Der Alt-Fall aus `compare-hub-versand-inline` entfällt, weil `hub-kopf-aufbau` KA-5 den Rest abdeckt und KA-5b die zwei Lücken (Körper ohne Empfänger, Desktop) schließt; `hub-send-dialog-target.staging` deckt diesen Weg nicht ab (Entscheidung Frage 2).
  - Test: `hub-kopf-aufbau.spec.ts` (KA-5 unverändert, KA-5b neu).
  - Mutation: Client schickt die Adresse im Körper mit → KA-5b rot; Sende-Abruf zweimal absetzen → KA-5/KA-5b rot.
- **AC-6:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Versand-Abschnitt geöffnet, die Alert-Zustellung gesucht, alle Kanäle abgewählt und der Viewport auf mobil gestellt wird / Then zeigt der Abschnitt für beide kinds Kanäle, Zeitplan und Laufzeit ohne Alert-Zustellung; Cooldown-Karte und Level-Tabelle stehen im Alarme-Reiter und nicht im Versand-Abschnitt; ohne aktiven Kanal erscheint der Leerzustand statt der Zeitplan-Karten (ohne erzwungenen Klick, mit bestätigter Adresse); mobil gibt es kein horizontales Scrollen.
  - Test: `hub-versand-aufbau.spec.ts` (VA-1..VA-4); die Wartebedingung ersetzt das `waitForTimeout(300)`.
  - Mutation: Cooldown-Karte im Versand-Abschnitt einblenden → VA-1/VA-2 rot; Leerzustand entfernen → VA-3 rot; feste Mindestbreite im Versand-Abschnitt → VA-4 rot.
- **AC-7:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich mit aktiven Morgen- und Abend-Slots (07:00 und 18:00) / When die Übersicht auf Desktop und mobil geöffnet wird und danach beide Slots abgeschaltet werden / Then zeigt der Ortsvergleich die Briefing-Angabe „Morgen 07:00 · Abend 18:00" (Stat am Desktop, Summary-Zeile „Versand" mobil, der Desktop-Stat steht mobil nicht) und nach dem Abschalten „—"; der Trip zeigt in der Karte „Briefings laufen" die Zeilen „Morgen-Briefing" 07:00 und „Abend-Briefing" 18:00 (in beiden Breiten), und nach dem Abschalten bleiben die Zeilen mit ihrer Zeit stehen, während die Punkte von der Aktiv- auf die Inaktiv-Farbe wechseln. Jeder kind prüft sein eigenes Ist-Format; das Vergleichs-Format wird nicht vom Trip verlangt. Der Alt-Fall „mobil zeigt den Stat" wird auf die tatsächliche mobile Stelle umformuliert (Entscheidung Frage 1), nicht gelöscht.
  - Test: `hub-versand-briefing-zeiten.spec.ts` (VB-1, VB-2, VB-9).
  - Mutation: Slot-Label-Format ändern → VB-1 (vergleich) rot; Summary-Zeile mobil ohne Briefing-Angabe → VB-2 (vergleich) rot; Trip-Karte zeigt feste 06:00/18:00 statt echter Zeiten → VB-1/VB-2 (route) rot; „—"-Zweig entfernen → VB-9 (vergleich) rot; Inaktiv-Farbe des Punktes gleich der Aktiv-Farbe → VB-9 (route) rot.
- **AC-8:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Versand-Abschnitt, die Übersicht, „Bearbeiten →", ein unbekannter `?tab=`-Wert und die Reiterleiste geprüft werden / Then zeigt der Versand-Abschnitt „Briefing-Zeitplan" mit Morgen-/Abend-Briefing und keine Rhythmus-Sprache („Rhythmus & Vorausschau", „Zeitfenster", beim Ortsvergleich auch kein Stundenbereich); „Bearbeiten →" bzw. „Zeitplan bearbeiten →" wechselt ohne Seitenwechsel auf Wetter-Metriken zum Versand-Abschnitt; ein unbekannter `?tab=` landet auf der Übersicht; alle fünf Reiter sind klickbar mit sichtbarem Panel, `-tab-versand` und `-tab-vorschau` existieren nicht. Nur beim Ortsvergleich zusätzlich „Kein Score, kein Ranking" (Idealwerte-Karte; Text existiert nur dort). Die Negativ-Prüfung auf „Zeitplan" entfällt als obsolet (Ist-Überschrift „Briefing-Zeitplan"), der Alt-Fall AC-8 (Vorschau) entfällt mit dem Produkt (#1743).
  - Test: `hub-versand-briefing-zeiten.spec.ts` (VB-3..VB-8).
  - Mutation: Überschrift auf „Rhythmus & Vorausschau" zurücksetzen → VB-3 rot; Sprung „Bearbeiten →" zeigt auf anderen Reiter → VB-5 des kind rot; unbekannten `?tab=` crashen lassen → VB-6 rot; Reiter `versand` wieder einführen → VB-8 rot; Ranking-Text zurück → nur VB-7 rot.
- **AC-9:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer die Laufzeit im Versand-Abschnitt ansieht und bedient / Then gilt je kind seine eigene Zusicherung: beim Trip ist die Laufzeit schreibgeschützt („endet <letztes Etappendatum>"), „Etappen öffnen →" wechselt in den Etappen-Reiter, und es geht kein Speicher-Aufruf hinaus; beim Ortsvergleich löscht „Bis auf Weiteres" per reinem Klick das Enddatum (Körper `end_date=""`, Server-Stand ohne `end_date` gelesen, `aria-selected` und Hinweis „ohne Enddatum" nach Neuladen) und „Bis Datum" speichert das gewählte Datum.
  - Test: `hub-versand-speichert-selbst.spec.ts` (VS-6, VS-7, VS-8).
  - Mutation: Sentinel `""` nicht senden → VS-7 rot; Server-Stand `""` statt fehlend → VS-7 rot (`toBeUndefined`); „Etappen öffnen →" löst PUT aus → VS-6 rot; Datum nicht persistieren → VS-8 rot.
- **AC-10:** Given die vier neuen Specs / When ein Vergleich-only-Zweig (`if (kind === 'vergleich')`) bzw. Trip-only-Zweig in ihnen vorkommt / Then trägt jeder Zweig einen Begründungskommentar und steht in „Kind-Kontraste" dieser Spec; zulässig sind nur die dort genannten (Laufzeit-Kontrast, Pausieren-Karte/Pille, Kanal-Testids, Übersicht-Format, „Kein Score", Stundenbereich, Pausier-Übertragungsweg); ein Zweig, der einen Fall nur für eine Art prüft, obwohl das Produkt ihn für beide kann, ist unzulässig.
  - Test: Adversary-Prüfpunkt, `grep -n "kind === " frontend/e2e/hub-versand-*.spec.ts` gegen die Tabelle.
  - Mutation: keine (Prozess); Findings bei Zweig ohne Kommentar oder ohne Gegenstück.
- **AC-11:** Given der Alt-Wizard `/compare/new` / When Name und zwei Orte gewählt, die Wertebereiche und Alarme besucht und „Aktivieren" gedrückt wird / Then enthält der POST an `/api/compare/presets` `morning_enabled=true`, `morning_time=07:00:00`, `evening_enabled=false`, `evening_time=18:00:00`, kein Enddatum und `official_warnings={enabled:false}`. Der Fall liegt in `compare-editor-slice3.spec.ts` (`gz-eigenstaendig:`-Kopf; Wizard hat kein Trip-Pendant, fällt mit #2243/S4); die Zusicherung wird an S4 übergeben, damit die Nachfolge-Anlegeseite sie übernimmt.
  - Test: `compare-editor-slice3.spec.ts` (neuer Fall), Wächter-Test (Datei bleibt konform).
  - Mutation: `official_warnings` aus dem POST entfernen → Fall rot; Kopf entfernen → Wächter rot.
- **AC-12:** Given die neuen und ergänzten Specs / When sie im Zielverbund (Hauptlauf der Positivliste ohne `bug-703`) dreimal hintereinander laufen / Then sind alle drei Läufe grün (frischer Stack, frische `admin.json`), die Specs enthalten **kein** `waitForTimeout`, kein `skip`/`test.fixme`, keinen `page.screenshot({path})`, keinen Hauptrepo-Pfad, kein `__dirname`, keinen festen `storageState`-Pfad und kein UI-`login()`; datenabhängige `.first()` auf Pool-Einträge sind durch Eigen-Seed ersetzt; Erwartungswerte stammen aus dem Seed, nicht aus dem gerenderten Produkt; jeder Fall räumt seinen `seedHub`-Vergleich im `finally` auf, kein Fall braucht mehr als zwei Vergleiche gleichzeitig (kein 409), es wird höchstens **eine** Registrierung je Worker verbraucht, und `global.teardown.ts` meldet keinen Restbestand `E2E-GZ-`.
  - Test: Filter B (3 Zyklen) + `grep -c "waitForTimeout\|\.skip(\|test\.fixme\|__dirname" frontend/e2e/hub-versand-*.spec.ts` = 0.
  - Mutation: `waitForTimeout` einfügen → Filter-A-Prüfung rot; `finally`-Aufräumen entfernen → Folgefall scheitert mit 409.
- **AC-13:** Given ein Fall der neuen Specs wird für den Trip rot, obwohl er für den Ortsvergleich grün ist (oder umgekehrt) / When die Ursache untersucht wird / Then wird die Produktlücke im **selben Ticket** (#2347) behoben und der Test bleibt unverändert streng; Abschwächen, `test.skip`, ein kind-Zweig, der den Fall nur für eine Art prüft, oder ein „bekannte Abweichung"-Vermerk sind unzulässig. Berührte Produktdateien werden in diese Spec nachgetragen (`updated`/Changelog) und das LoC-Limit bei Bedarf per `loc_limit_override` angehoben. Erwartete Messpunkte für den Trip: 412 im Versand-Reiter (VS-2), Kanal-Switch (VI-1), Pausieren-Flush (VS-3/VI-5), mobile Übersicht-Karte (VB-2). Kein Messpunkt sind Elemente, die der Trip-Hub nie hatte (Status-Pille `[data-status]`, Aktivierungs-Karte, editierbares Enddatum).
  - Test: Prozess-AC; Beleg im Adversary-Protokoll (Liste „rot beim Zusammenführen: ja/nein, wenn ja: Fix-Commit").
  - Mutation: keine (Regel).
- **AC-14:** Given der Paritäts-Wächter / When der Unit-Test läuft / Then enthält `ALTLAST` nur noch **30** Einträge (`compare-versand-speichert-selbst`, `compare-hub-versand-inline`, `compare-hub-briefing-times`, `versand-tab-vergleich` entfernt; `compare-editor-autosave` bleibt), `ALTLAST_MAX` ist das Literal **30**, und die Selbsttests der Wächter-Mutationen bleiben grün.
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei).
  - Mutation: einen der vier Namen in `ALTLAST` stehen lassen → rot; `ALTLAST_MAX` auf 34 lassen → rot; neue `compare-neu.spec.ts` ohne Kopf → rot.
- **AC-15:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` die vier `hub-versand-*`-Namen und nicht mehr `compare-versand-speichert-selbst`, `E2E_MIN_SPECS` entspricht exakt der Listenlänge (erwartet **71**), `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `npx playwright test --list` gemessene Wert mit fortgeschriebener Begründung, jede Listenzeile verweist auf eine vorhandene Datei, die Staging-Configs `playwright.1256-s7` und `playwright.1229-hub` sind entfernt, `playwright.1273-s4c` verweist nicht mehr auf `versand-tab-vergleich`, und `grep -rn` auf die gelöschten Namen über `frontend`, `.github`, `tests` findet nur Historie in `docs/`.
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py`, CI-Job `e2e` (`e2e_gate.py`), `grep`-Prüfung in `/60`.
  - Mutation: Listenzeile auf nicht existierenden Namen → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot.
- **AC-16:** Given ein zusammengeführtes Verhalten aus AC-1 bis AC-9 / When die Implementierung gezielt verfälscht wird (Mutations-Gegenprobe, Sicherungskopie, nur String-Ersetzung) / Then wird für **jedes** zusammengeführte Verhalten und **beide** kinds der jeweils betroffene Test rot, und es wird protokolliert, **welcher** Test rot wurde; eine Verfälschung, die kein Test fängt, ist ein Finding; eine kind-spezifische Verfälschung macht nur den Fall dieser Art rot. Zusätzlich zählt die Ausfallprobe der Zuordnung: ein weggelassener Fall (z. B. VI-6 F004) wird von der Fallzahl-Prüfung (`--list` je Zieldatei ≥ zugeordnete Altfälle je kind) gemeldet, und die Altdateien werden erst nach grünem Lauf gelöscht.
  - Test: Adversary-Dialog in `/50` (Familien: Selektor/Testid, Zähler, Wartebedingung, PUT-/PATCH-Körper, Flush je Einstiegspunkt, 412, Nutzer-Kontext, Übertragungsweg).
  - Mutation: siehe die Mutationszeilen in AC-1 bis AC-9.

## Definition of Done

- [ ] AC-1 bis AC-16 sind per Test und Mutations-Gegenprobe belegt (je Mutation protokolliert, welcher Test rot wurde)
- [ ] Vier neue `hub-versand-*`-Specs laufen für beide `kind`s grün gegen den CI-Stack; Altdateien erst danach gelöscht
- [ ] Zuordnungstabelle vollständig gegen `grep -c "^\s*test("` je Altdatei; Entscheidungen Frage 1–3 im Adversary-Protokoll bestätigt
- [ ] `E2E_MIN_EXECUTED_HAUPT` per `--list` neu gemessen, `E2E_MIN_SPECS` (71) und Positivliste konsistent
- [ ] Wächter `ALTLAST`/`ALTLAST_MAX` auf 30, Wächter-Test grün
- [ ] CI-Ampel (6 Checks) grün, kein Produktcode geändert (oder Produktlücke nach AC-13-Muster dokumentiert)

## Known Limitations

- Trip-Verhalten bei 412 im Versand-Reiter, beim Kanal-Feld, bei der mobilen Übersicht-Karte und bei den Punkt-Farben ist erst im RED messbar; die Spec legt die Zusicherung fest, nicht das Messergebnis.
- Die Zielzahl für `E2E_MIN_EXECUTED_HAUPT` ist erst am Endstand messbar; `E2E_MIN_SPECS` (71) ergibt sich aus der Listenzählung.
- Quota: höchstens 2 aktive Vergleiche pro Nutzer; Registrierungsbremse 5/h/IP (eine Registrierung je Worker über `testMitZustellbaremZiel`).
- Die Create-Flow-Zusicherung (AC-11) bleibt bis S4 an den Alt-Wizard gebunden; ein Nachfolger muss sie bewusst übernehmen.
- Das unterschiedliche Übersicht-Format (Trip: zwei Zeilen, Vergleich: zusammengesetzter Text mit „—") ist Ist-Zustand und wird hier abgebildet, nicht angeglichen; eine Angleichung wäre eine eigene Produktentscheidung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testschicht-Konsolidierung nach bestehender Vorgabe (Trip/Ortsvergleich-Code-Teilung, Epic #2345 P6); keine neue Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth).

## Changelog

- 2026-10-28: Initial spec created (S3b, Versand-Gruppe). Entscheidungen zu den drei offenen Fragen der Analyse am Code getroffen: briefing-times AC-2/AC-4/AC-10 gelten umformuliert weiter, AC-8 entfällt mit #1743; #2283-Fall ist durch `hub-kopf-aufbau` KA-5 + neue Fälle KA-5b abgedeckt (nicht durch `hub-send-dialog-target.staging`); Trip-Hub hat einen Kebab mit Pausieren (F004 gilt für beide kinds, Übertragungsweg verschieden, Karten-Einstieg nur im Ortsvergleich). Wächter 34 → 30, `E2E_MIN_SPECS` 68 → 71 (erwartet).
- 2026-10-28 (/40, Korrektur am Ist-Stand, keine Abschwächung): (1) **VI-6/AC-2/Frage 3 vergleich:** Der Kebab-Pausier-PUT trägt seit #2375 nur den Status (`compareHubPersistenz.ts:40-49`; `hub-alarme-speichert-selbst` AS-3 prüft exakt `['previous_schedule','schedule']`). „Körper trägt die Uhrzeit" ist damit nicht prüfbar; F004 wird in #2375-Form geprüft: Feld-PUT vor Status-Schreibvorgang, Status-Körper nur Status-Schlüssel (Spread aus veralteter Baseline würde rot), Server-Stand nach Neuladen = neue Uhrzeit + pausiert. (2) **VI-1/AC-3:** `telegram_chat_id` ist seit #2141 per Profil-PUT nicht setzbar (`internal/handler/auth.go:1346-1356`); VI-1 ergänzt nur die Profil-Lesung im Browser per `page.route` (Sperre ist clientseitig), Schalter/PUT/Server-Stand/Neuladen bleiben echt; kein Profil wird verändert, „Wiederherstellung im finally" entfällt als Mutation. (3) VS-4 route: abgeleitetes Flachfeld `morning_time` am Trip (`trip.go:172-177`) ausdrücklich auf 08:00 geprüft statt im Gleichheitsvergleich.
- 2026-10-28 (/50 GREEN, Nachtrag — der Abschnitt „Zuordnung alt → neu" ist freigabe-gesperrt, deshalb steht der Abgleich hier): **1:1-Abgleich per `npx playwright test --list` je Altdatei** (Autorität statt `grep -c`): `compare-versand-speichert-selbst` 5 (AC-5, AC-4, AC-6, AC-7, AC-11), `compare-hub-versand-inline` **7** (nicht 8: AC-35, AC-36, AC-37/17/18, F001, F002, F004, #2283; AC-19 steht nur im describe-Titel, Fall mit #1743 entfallen, Alt-Kommentar `:371`), `compare-hub-briefing-times` 9 (AC-1, AC-2, AC-4, Fix-Loop 1, AC-5, AC-6, AC-7, AC-10, Draft „—"; AC-8 war kein Fall mehr, nur Kommentar), `versand-tab-vergleich` 9 (AC-1, AC-3, AC-3b, AC-4, AC-7, AC-10, AC-2, AC-6, Staging-F001), `compare-editor-autosave` **11** (nicht 12; nur AC-14 (Versand) entfernt, Deckung `hub-versand-autosave-chip` AC-1 vergleich + VS-5). Alle 30 Altfälle der vier gelöschten Dateien (5 + 7 + 9 + 9) plus AC-14 (Versand) stehen in der Zuordnungstabelle; keine Zeile fehlt, keine wurde abgeschwächt. **AC-13:** kein Trip-Fall rot beim Zusammenführen (3 Zyklen 80/80 gegen frischen isolierten Stack) ⇒ kein Produktcode geändert. **Zusätzlich berührte Dateien (Verweis-Hygiene, keine Zusicherungsänderung):** `tests/tdd/test_compare_e2e_storagestate_migration.py` (`versand-tab-vergleich.spec.ts` aus `MIGRATED_FILES`, sonst `test`-Job rot durch `read_text` auf die gelöschte Datei und Listen-Prüfung gegen `playwright.1273-s4c`), `frontend/e2e/feat-1256-s7.staging.setup.ts` gelöscht (nur von `playwright.1256-s7` benutzt), `frontend/playwright.1461-s3b2b.staging.config.ts` (Muster-Kommentar auf `playwright.1256-s2` umgehängt), `frontend/e2e/versandzeit-stundenwahl.spec.ts` (Deckungs-Kommentar AC-3 auf `hub-versand-autosave-chip` umgehängt). `frontend/e2e/feat-1231-s6.staging.setup.ts` **bleibt**: nach Löschung von `playwright.1229-hub` funktional unbenutzt, aber als „Muster" von `feat-1256-s2`/`feat-1461-s3b2b`-Setups referenziert (eigenes Ticket #1231). Ratsche: `E2E_MIN_SPECS` 71, `E2E_MIN_EXECUTED_HAUPT` 528 (gemessen: `Total: 528 tests in 71 files`).
- 2026-10-28 (/50 Fix-Loop nach Adversary F001–F004, Abschnitte AC/Zuordnung freigabe-gesperrt, deshalb hier): **F001** VS-1 hält jetzt per `page.clock` die Seiten-Uhr nach dem Öffnen an (`pauseAt`), sodass der 700-ms-Entprell-Timer nie von selbst feuert; ein Speicher-Aufruf beim Reiterwechsel kann nur noch aus einem Flush stammen, zusätzlich `puts.length === 1` vor `clock.resume()` — für beide kinds gleich, kein Zweig. Befund dazu: im Trip-Hub gibt es **zwei** Flush-Wege beim Reiterwechsel — `TripTabs.svelte:164` und den `beforeNavigate`-Wächter der Seite (`trips/[id]/+page.svelte:68-70` → `sichereAusstehendeSpeicherung`), weil `TripTabs` per `goto('?tab=…')` wechselt; die Einzelmutation `:164` ist deshalb eine äquivalente Mutante (bleibt grün), erst beide entfernt ⇒ VS-1 (route) rot. Der Ortsvergleich wechselt per `history.replaceState` (kein `beforeNavigate`), dort trägt `sichereSelbstSpeichererVorReiterwechsel` (`CompareTabs.svelte:181`) allein ⇒ entfernt: VS-1 (vergleich) rot. **F002** VI-5/VI-5k prüfen zusätzlich die Reihenfolge der beantworteten Schreibvorgänge (Feld-PUT mit neuer Uhrzeit, danach Status-Rumpf mit den Status-Schlüsseln des kind). **F003 (AC-3-Wortlaut):** `telegram_chat_id` ist seit #2141 per Profil-PUT nicht setzbar (`internal/handler/auth.go:1346-1356`); VI-1 simuliert deshalb den verknüpften Telegram-Zustand per `page.route` auf den Profil-GET des Browsers (die Sperre ist clientseitig), Schalter, Speicher-Aufruf, Server-Stand und Neuladen bleiben echt; das Profil wird nicht verändert und am Fallende unverändert geprüft — „setzen und im `finally` wiederherstellen" entfällt damit. **F004:** neun Kommentar-Zeiger in `frontend/src/lib/components/{compare,shared}/__tests__/*.test.ts` von der gelöschten `compare-versand-speichert-selbst.spec.ts` auf `hub-versand-speichert-selbst.spec.ts` (VS-1/-2/-3/-3k/-7) bzw. `hub-versand-autosave-chip.spec.ts` (AC-1) umgehängt, keine Logikänderung.
