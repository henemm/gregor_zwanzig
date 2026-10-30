---
entity_id: i18n_f11_bausteine_ts_2660
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2660, frontend, model-haiku]
---

# i18n F11: Bausteine (ui, molecules, organisms, atoms, mobile) und TypeScript-Texte (utils, stores, api.ts) zweisprachig

**Issue:** #2660 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 3 (Ratsche Frontend, Erweiterung auf `*.ts`)

## Approval

- [ ] Approved

## Purpose

Wer Englisch eingestellt hat, soll auch in den kleinen, überall wiederverwendeten Bausteinen (Dialog-Knöpfe, Rücksprung-Links, Listenmenüs, Karten) und in Meldungen, die direkt aus dem Code kommen (Versand-Ergebnis, Verbindungs- und Speicherfehler, Ort-löschen-Sperre), nur Englisch sehen. Dazu wandern die deutschen Texte dieser Bausteine und der TypeScript-Hilfsmodule in den Katalog (`bausteine`, `fehler`, ergänzend `aktionen`), und Server-Fehler mit bekanntem `code` werden im Frontend über `fehler.code.<code>` in der Nutzersprache angezeigt. Die Ratsche gegen hartkodierte Nutzertexte wird auf `*.ts` in `lib/utils`, `lib/stores` und `lib/api.ts` ausgedehnt. Die deutsche Anzeige bleibt wortgleich.

## Source

- **File:** `frontend/src/lib/api.ts`, `frontend/src/lib/stores/saveStatusStore.svelte.ts`, `frontend/src/lib/utils/sendOutcome.ts`, `frontend/src/lib/components/{ui,molecules,organisms,atoms,mobile}/**`, `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`
- **Identifier:** `zeitlimitFehler`, `request`, `downloadUserDataExport`, `extractMessage`, `classifySendResponse`, `ortInUseHinweis`, `computeHorizonSummary`, `profileSignature`, `tr`, `fehlerTextFuerCode` (neu)

> **Schicht-Hinweis:** Reines SvelteKit-Frontend (`frontend/src/...`). Kein Go-, kein Python-Code, keine neue Abhängigkeit. Das Go-Fehlerformat `{"code","message"}` und die Codeliste liefert G1 (#2675, `docs/reference/api_contract.md`); F11 liest nur.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Alle Bausteine hier sind bereits geteilt (`SendConfirmDialog`, `ConfirmDialog`, `ListActionsMenu`, `BackLink`, `SubscriptionCard`). Es entsteht kein neuer Baustein und kein Pendant; Texte, die auf beiden Flächen gleich lauten, liegen einmal in `aktionen.*` (zum Beispiel `aktionen.weitere` für „Weitere Aktionen“, bisher viermal getippt). Nie zwei Schlüssel für denselben Text.
> - **Mandantentrennung:** Es werden keine Nutzerdaten gelesen oder geschrieben. Die Sprache kommt aus `data.lang` (S2), nicht aus einem Fallback; Texte werden bei jedem Aufruf aufgelöst, nie beim Import eingefroren (kein Zustand, der von Nutzer A zu Nutzer B wandert).
> - **Kanäle:** Berührt keinen Briefing- oder Alarm-Inhalt. Kanalnamen (E-Mail, Telegram, SMS, Premium-SMS) sind Eigennamen und bleiben in `ChannelChip`, `ChannelRow` und `SubscriptionCard` unverändert.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/bausteine.json`, `.../en/bausteine.json` | MODIFY | Texte der Bausteine (Namensraum `bausteine.*`) |
| `frontend/src/lib/i18n/messages/de/fehler.json`, `.../en/fehler.json` | MODIFY | Fehler- und Hinweistexte aus TypeScript (`fehler.*`, `fehler.code.<code>`) |
| `frontend/src/lib/i18n/messages/de/aktionen.json`, `.../en/aktionen.json` | MODIFY | nur Texte, die auf Trip- und Ortsvergleich-Flächen gleich lauten (`aktionen.abbrechen`, `aktionen.weitere`, `aktionen.zurueck_zu`) |
| `frontend/src/lib/i18n/fehlerCode.ts` | CREATE | `fehlerTextFuerCode(code)`: Katalogtext zu `fehler.code.<code>` oder `null` |
| `frontend/src/lib/api.ts` | MODIFY | `zeitlimitFehler()` (Z. 90–97), Sitzung abgelaufen (Z. 187), Schreibsperre (Z. 232–234), Download-Fehler (Z. 352); Fehlerobjekt behält `code` |
| `frontend/src/lib/types.ts` | MODIFY | `ApiError` (Z. 425) um `code?: string` und `message?: string` ergänzen (additiv) |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | `extractMessage()` (Z. 49–57): bekannter `code` → Katalog, sonst Server-Text, sonst `fehler.speichern.allgemein` |
| `frontend/src/lib/stores/nachEntladenNachladen.ts` | MODIFY | Z. 136: interner Invarianten-Wurf, nur Entwicklerdiagnose, Zeilenmarker `// i18n-log` |
| `frontend/src/lib/utils/sendOutcome.ts` | MODIFY | Konstanten Z. 14–17 und Meldung Z. 149 → `tr()` zur Aufrufzeit |
| `frontend/src/lib/utils/ortLoeschenSperre.ts` | MODIFY | Z. 19 Hinweistext → `tr()` mit `{namen}` |
| `frontend/src/lib/utils/horizonHelpers.ts` | MODIFY | `computeHorizonSummary()` Z. 58–62 → `tr()` mit `{anzahl}` |
| `frontend/src/lib/utils/profileSignature.ts` | MODIFY | Eyebrow-Texte (Z. 24–39) → `tr()` zur Aufrufzeit |
| `frontend/src/lib/utils/rightColumn.ts` | MODIFY | Z. 34–36 Profil-Standard-Beschriftungen |
| `frontend/src/lib/utils/cockpitHelpers568.ts` | MODIFY | Checklisten-Beschriftungen Z. 66–73 und Z. 117–121 |
| `frontend/src/lib/utils/stageRisk.ts` | MODIFY | Z. 20–22 Risiko-Beschriftungen |
| `frontend/src/lib/components/atoms/BackLink.svelte` | MODIFY | `aria-label` Z. 29 und Z. 39 (`Zurück: …`) |
| `frontend/src/lib/components/molecules/ConfirmDialog.svelte` | MODIFY | Standard-Beschriftung `cancelLabel` (Z. 38) |
| `frontend/src/lib/components/molecules/SendConfirmDialog.svelte` | MODIFY | Titel „Briefing senden?“ (Z. 36), `aria-label` „Berichtsart“ (Z. 50) |
| `frontend/src/lib/components/molecules/SubscriptionKebab.svelte` | MODIFY | „Weitere Aktionen“ (Z. 29–30) |
| `frontend/src/lib/components/organisms/ListActionsMenu.svelte` | MODIFY | Standard `label = 'Weitere Aktionen'` (Z. 29) |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` | MODIFY | „Weitere Aktionen“ (Z. 208–209), „noch keine Kanäle“ (Z. 253) |
| `frontend/src/lib/components/organisms/OutboxCard.svelte`, `AlertsCard.svelte`, `PresetRail.svelte`, `MetricOffShelf.svelte`, `MetricsEditorContextBar.svelte` | MODIFY | Eyebrows, Pillen, Knöpfe (bestätigte Zeilen siehe Implementation Details) |
| `frontend/src/lib/components/mobile/StageCardM.svelte` | MODIFY | „Pausentag“ (Z. 106) |
| weitere Kandidaten laut Ratsche (Grep-Treffer 2026-10-30, evtl. nur Kommentar): `molecules/{CompareStatusRow,HorizonChips,ScoreToggle}.svelte`, `ui/{segmented/Segmented,horizon-chip/HorizonChip,wordmark/Wordmark}.svelte`, `mobile/{MTabBar,Sheet,Drawer,MBtn}.svelte`, `atoms/{PageHeader,Stat,Card}.svelte` | MODIFY | nur wenn die Ratsche oder ein Grep nach deutschem Text in `{…}`-Ausdrücken sie meldet |
| `frontend/src/lib/utils/sendOutcome.test.ts`, `frontend/src/lib/utils/__tests__/send_url_einheitlich.test.ts`, `frontend/src/routes/compare/__tests__/compare_hub_versand_neuer_endpunkt.test.ts` | MODIFY | importieren die entfallenden Konstanten `SEND_*`; stattdessen `tr('fehler.versand.…')` |
| `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | MODIFY | Ratsche um `*.ts`-Scan erweitern |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Allowlist-Einträge siehe Implementation Details |
| `frontend/src/lib/stores/__tests__/fehlermeldung_code_und_sprache.test.ts` | CREATE | Test zu AC-1 |
| `frontend/src/lib/__tests__/api_fehlertexte_sprache.test.ts` | CREATE | Test zu AC-2 |
| `frontend/src/lib/utils/__tests__/versand_ergebnis_sprache.test.ts` | CREATE | Test zu AC-3 |
| `frontend/src/lib/components/__tests__/bausteine_sprache.test.ts` | CREATE | SSR-Render-Test zu AC-4 und AC-5 |
| `docs/reference/i18n_glossar.md` | MODIFY | Zeile „Pausentag → rest day“ ergänzen (Glossar vor Katalog) |

## Estimated Scope

- **LoC:** ca. 280 Code ohne Katalogdaten und Tests (Ratschen-Erweiterung ~70, `fehlerCode.ts` ~15, Umstellungen ~190). Das Workflow-Limit von 250 LoC kann berührt werden: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** ca. 45 (davon 8 Katalogdateien, 5 Tests, ~32 Quelldateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2647 S2 | Paket | Katalog je Bereich, `t`, `tn`, `tr`, `locale`, `MessageKey`, Paritätstest |
| #2649 S4 | Paket | Ratsche `keine_hartkodierten_nutzertexte.test.ts`, Allowlist, Verwender-Test |
| #2675 G1 | Paket | Fehlerobjekt `{"code","message"}` und Codeliste in `docs/reference/api_contract.md` |
| `$lib/i18n/index.ts` (`tr`, `MessageKey`), `$lib/i18n/format.ts` (`fmtTime`) | module | Zugriff auf Texte und Uhrzeit-Format |
| `docs/reference/i18n_glossar.md` | doc | bindende Wortliste; Verbot das im Glossar verbotene Produktwort ist untersagt |
| ADR-0104 | adr | Sprache am Nutzer, Katalog je Schicht |

## Implementation Details

**Katalog-Namensraum.** `bausteine.*` (Texte einzelner Bausteine), `fehler.*` (Meldungen aus TypeScript), `fehler.code.<code>` (eine Zeile je Go-Fehlercode aus `api_contract.md`, mindestens `etag_mismatch`), `aktionen.*` (nur Texte, die auf Trip- und Ortsvergleich-Flächen gleich lauten). Nur diese Dateien anfassen. Die englischen Texte folgen dem Glossar, Sentence case, keine Ausrufezeichen.

**Beispiel-Schlüssel (de / en):**

| Schlüssel | de | en |
|---|---|---|
| `aktionen.abbrechen` | Abbrechen | Cancel |
| `aktionen.weitere` | Weitere Aktionen | More actions |
| `aktionen.zurueck_zu` | Zurück: {ziel} | Back: {ziel} |
| `fehler.verbindung.zeitlimit` | Die Verbindung ist zu langsam — der Server hat nicht rechtzeitig geantwortet. | The connection is too slow — the server did not respond in time. |
| `fehler.sitzung.abgelaufen` | Sitzung abgelaufen — bitte neu anmelden. | Session expired — please sign in again. |
| `fehler.verbindung.schreiben_offline` | Ohne Verbindung lässt sich nichts speichern — die Änderung wurde nicht abgeschickt. | Nothing can be saved without a connection — the change was not sent. |
| `fehler.speichern.allgemein` | Fehler beim Speichern | Error while saving |
| `fehler.versand.unklar` | Ergebnis unklar — Versand kann noch laufen, nicht erneut senden | Result unclear — the send may still be running, do not send again |
| `fehler.versand.fehlgeschlagen` | Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen. | Sending failed — server error, please try again later. |
| `fehler.versand.orte_fehlten` | Test-Briefing gesendet, aber Orte fehlten (gelöscht, {anzahl}): {orte}. Ersetze die Orte im Ortsvergleich. | Test briefing sent, but locations were missing (deleted, {anzahl}): {orte}. Replace the locations in the location comparison. |
| `bausteine.profil.summer_trekking` | Sommer-Trekking | Summer trekking |
| `bausteine.horizont.nur_morgen_uebermorgen` | {anzahl} nur morgen + übermorgen | {anzahl} tomorrow + day after tomorrow only |

Die übrigen Texte (Versand-Meldungen `laeuft_bereits` und `abgelehnt`, Profil-Eyebrows, Horizont-Gruppen, Checklisten, Risiko-Labels, Cockpit-Karten) folgen demselben Muster; die deutschen Werte werden aus dem Quelltext **wortgleich** übernommen (auch wenn sie sich ungewöhnlich lesen), die englischen aus dem Glossar.

**Beispiel-Umstellung 1 (Svelte, Attribut mit Ausdruck).** `frontend/src/lib/components/atoms/BackLink.svelte` Z. 29 und Z. 39. Die Ratsche S4 entfernt `{…}`-Ausdrücke vor der Prüfung und sieht diesen deutschen Text deshalb nicht; er wird trotzdem umgestellt:

```svelte
<!-- vorher -->
aria-label={ariaLabel ?? `Zurück: ${label}`}
<!-- nachher -->
aria-label={ariaLabel ?? $t('aktionen.zurueck_zu', { ziel: label })}
```

Ebenso `ConfirmDialog.svelte` Z. 38: der Standardwert `cancelLabel = 'Abbrechen'` entfällt (kein Standard im Destrukturieren), im Markup Z. 59 steht `{cancelLabel ?? $t('aktionen.abbrechen')}`. Ein Standardwert im `$props()` würde die Sprache beim Erzeugen einfrieren.

**Beispiel-Umstellung 2 (TypeScript, Fehlermeldung mit Code).** `frontend/src/lib/stores/saveStatusStore.svelte.ts` `extractMessage()` Z. 49–57. Die Reihenfolge `detail`, `error`, `message` bleibt unverändert; neu davor steht nur der bekannte Code:

```ts
// vorher
return 'Fehler beim Speichern';
// nachher (Kopf der Funktion und Rückfall)
const bekannt = fehlerTextFuerCode((e as { code?: unknown } | null)?.code);
if (bekannt) return bekannt;
// ... detail / error / message wie bisher ...
return tr('fehler.speichern.allgemein');
```

`fehlerTextFuerCode` (neu, `frontend/src/lib/i18n/fehlerCode.ts`) prüft, ob `fehler.code.<code>` im Katalog steht, und gibt dann `tr(...)` zurück, sonst `null` (dann zeigt der Aufrufer wie heute den Server-Text). Die dynamische Schlüsselbildung trägt den Kommentar `// i18n-dynamic: fehler.code.`.

**Beispiel-Umstellung 3 (Konstanten werden Aufrufe).** `frontend/src/lib/utils/sendOutcome.ts` Z. 14–17 sind Modul-Konstanten und würden die Sprache beim Import einfrieren. Sie entfallen; `classifySendResponse()` (Z. 19–31) und Z. 95 rufen `tr('fehler.versand.unklar')`, `tr('fehler.versand.laeuft_bereits')`, `tr('fehler.versand.fehlgeschlagen')`, `tr('fehler.versand.abgelehnt')` bei jedem Aufruf. Die drei Tests, die `SEND_*` importieren (Tabelle oben), vergleichen künftig mit `tr(...)`. Gleiches Muster für `profileSignature.ts`: die Tabelle `SIGNATURES` hält Schlüssel (`eyebrowKey`), `profileSignature()` liefert `eyebrow: tr(eyebrowKey)`.

**Bestätigte Textstellen in Bausteinen (Grep 2026-10-30).** `SubscriptionKebab.svelte:29-30`, `SubscriptionCard.svelte:208-209`, `ListActionsMenu.svelte:29` → ein Schlüssel `aktionen.weitere`; `OutboxCard.svelte:36` „Versand · heute“ (en: Delivery · today), `:47` „Alle Kanäle ok“ (All channels OK); `AlertsCard.svelte:36` „Alerts · letzte 24 h“ (Alerts · last 24 h), `:47` „Schwellen →“ (Thresholds →); `PresetRail.svelte:41` „Wetter-Profil“ (Weather profile), `:109` „Eigenes Profil“ (Custom profile); `MetricOffShelf.svelte:66` „Nicht im Briefing“ (Not in briefing), `:69` „aktuell aus“ (currently off), `:107` „+ Spalte“ (+ Column), `:108` „+ Detail“; `ListTable.svelte:79` bleibt (F3-Eintrag); `StageCardM.svelte:106` „Pausentag“ (Rest day, Glossar-Zeile mitliefern).

**Ratsche für TypeScript.** In `keine_hartkodierten_nutzertexte.test.ts` kommt eine zweite Prüfung hinzu: für jede `*.ts` (auch `*.svelte.ts`) unter `frontend/src/lib/utils`, `frontend/src/lib/stores` und die Datei `frontend/src/lib/api.ts` (ohne `*.test.ts`, `__tests__/`, `*.d.ts`) werden Kommentare entfernt, dann alle String-Literale (einfach, doppelt, statische Teile von Template-Literalen) geprüft. Treffer sind Literale mit Umlaut oder ß oder mit einem der Signalwörter `nicht`, `bitte`, `fehlgeschlagen`, `gespeichert`. Eine Zeile mit abschließendem `// i18n-log` (Log- oder Diagnoseausgabe) ist ausgenommen. Meldung: `Datei:Zeile`. Allowlist-Einträge sind Pfad-Präfixe.

**Allowlist-Eintrag, der entfernt wird.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` verschwinden `frontend/src/lib/components/ui`, `.../molecules`, `.../organisms`, `.../atoms`, `.../mobile`, `frontend/src/lib/utils`, `frontend/src/lib/stores`, `frontend/src/lib/api.ts`. Weil F11 vor F2, F3 und F4 läuft, bleiben Dateien anderer Pakete über ihre schmaleren Präfixe erlaubt: `molecules/Infobox` und `molecules/BegriffErklaerung` (F2), `organisms/ListTable*`, `*Kachel*`, `HomeHero*` (F3), `ui/sidebar` (F4). Meldet die Ratsche danach noch eine Datei eines anderen Pakets, wird sie als **eigener, engerer** Eintrag eingetragen (nie das alte breite Präfix behalten): erwartet sind `frontend/src/lib/components/ui/SaveIndicator.svelte` (F4), `frontend/src/lib/utils/tripHero.ts` und `frontend/src/lib/utils/schedulerTime.ts` (F3), `frontend/src/lib/utils/alertMetricLabels.ts` (F7). Die Allowlist schrumpft dadurch netto.

**Sprache zur Aufrufzeit.** `tr()` nie auf Modulebene aufrufen und nie als Standardwert in `$props()`; in `.svelte` immer `$t(...)` im Markup. Statuswerte wie `aktiv`, `pausiert`, `draft` in `tripStatus.ts` sind Protokollwerte, keine Anzeigetexte, und bleiben unübersetzt. Der Fehlerpfad `GPX parse failed:` in `api.ts` Z. 388 ist heute englisch und bleibt in beiden Sprachen unverändert.

**Manuelle Nachsuche.** Die Ratsche sieht Texte in `{…}`-Ausdrücken und `<script>` nicht. Zusätzlich im Umfang per Grep nach deutschen Wörtern in Backtick- und Anführungszeichen-Literalen suchen und Treffer umstellen.

## Expected Behavior

- **Input:** Nutzersprache `en` oder `de` (aus `data.lang`), ein fehlgeschlagener API-Aufruf mit oder ohne `code`, ein Versand-Ergebnis, ein gerenderter Baustein.
- **Output:** Bei `en` englische Texte aus dem Katalog, bei `de` wortgleich der heutige Text. Fehler mit bekanntem `code` erscheinen in der Nutzersprache, Fehler mit unbekanntem oder fehlendem `code` mit dem Server-Text unverändert.
- **Side effects:** Keine Schreibzugriffe, keine API-Änderung. Die Ratsche schlägt rot an, wenn ein neuer deutscher Nutzertext in `lib/utils`, `lib/stores` oder `lib/api.ts` auftaucht.

## Acceptance Criteria

- **AC-1:** Given Sprache Englisch und ein fehlgeschlagener API-Aufruf / When die Fehlermeldung angezeigt wird / Then erscheint ohne `code` die Server-Meldung unverändert, mit bekanntem `code` der englische Katalogtext und mit unbekanntem `code` wieder die Server-Meldung.
  - Test: `frontend/src/lib/stores/__tests__/fehlermeldung_code_und_sprache.test.ts` — `extractMessage()` mit echten Fehlerobjekten unter `locale.set('en')` und `locale.set('de')`; der bekannte Code wird aus dem Katalog gelesen, nicht hartkodiert.

- **AC-2:** Given Sprache Englisch / When ein Abruf in das Zeitlimit läuft, ein Schreibversuch ohne Verbindung abgewiesen wird oder die Sitzung abgelaufen ist / Then lautet die Fehlermeldung englisch, bei Deutsch wortgleich wie heute.
  - Test: `frontend/src/lib/__tests__/api_fehlertexte_sprache.test.ts` — echte `api`-Aufrufe mit `setzeStandardZeitlimit`, gesperrtem Schreibpfad und 401-Antwort; geprüft wird `Error.message` in beiden Sprachen.

- **AC-3:** Given dasselbe Modul `sendOutcome` ist geladen / When zuerst unter `de`, dann nach `locale.set('en')` ohne Neuladen klassifiziert wird (409, 502, Netzfehler, 500, fehlende Orte) / Then folgt jede Meldung der Sprache zum Zeitpunkt des Aufrufs, und nichts bleibt aus dem Import eingefroren.
  - Test: `frontend/src/lib/utils/__tests__/versand_ergebnis_sprache.test.ts` — `classifySendResponse()` und die Test-Briefing-Auswertung zweimal hintereinander mit wechselnder Sprache.

- **AC-4:** Given Sprache Englisch / When `BackLink`, `ConfirmDialog` ohne eigenes `cancelLabel`, `SendConfirmDialog`, `ListActionsMenu`, `SubscriptionKebab`, `OutboxCard` und `PresetRail` gerendert werden / Then steht in Beschriftungen und `aria-label` kein deutsches Wort (zum Beispiel `Back: …`, `Cancel`, `More actions`), und Trip- und Ortsvergleich-Verwendung zeigen denselben Text.
  - Test: `frontend/src/lib/components/__tests__/bausteine_sprache.test.ts` — echter SSR-Render (`svelte/server`) der genannten Bausteine; geprüft werden gerenderte Texte gegen `tr()`-Werte, keine Dateiinhalts-Prüfung.

- **AC-5:** Given Sprache Deutsch / When dieselben Bausteine und Meldungen gerendert bzw. ausgelöst werden / Then ist der Text wortgleich zur Ausgabe vor der Umstellung (Golden-Literale aus dem bisherigen Quelltext, zum Beispiel `Zurück: Trips`, `Abbrechen`, `Weitere Aktionen`, `Versand läuft bereits`, `Fehler beim Speichern`, `Sommer-Trekking`).
  - Test: `frontend/src/lib/components/__tests__/bausteine_sprache.test.ts` und `frontend/src/lib/utils/__tests__/versand_ergebnis_sprache.test.ts` — Vergleich der gerenderten bzw. gelieferten Texte mit den vor der Umstellung festgehaltenen Literalen.

- **AC-6:** Given die erweiterte Ratsche / When in `lib/utils`, `lib/stores` oder `lib/api.ts` ein Literal mit Umlaut oder Signalwort außerhalb von Kommentaren und ohne `// i18n-log` steht / Then schlägt der Test mit `Datei:Zeile` rot an, und mit `// i18n-log` bleibt er grün; die Allowlist enthält die acht F11-Präfixe nicht mehr.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` — Ratschen-Test über den echten Quellbaum plus Selbsttest mit einer temporären Beispiel-Datei (`# doc-compliance-test`: Ratschen-/Paritätstest, kein Verhaltensnachweis).

- **AC-7:** Given die Kataloge `bausteine`, `fehler` und `aktionen` / When der Paritätstest und der Verwender-Test laufen / Then haben alle drei Bereiche in `de` und `en` dieselben Schlüssel und Platzhalter, jeder neue Schlüssel hat einen Verwender, und `svelte-check` meldet keinen unbekannten Schlüssel.
  - Test: Paritäts- und Verwender-Test aus S2/S4 (`frontend/src/lib/i18n/__tests__/`) sowie `npm run check` (`# doc-compliance-test`).

## Known Limitations

- Annahme: Der Locale-Standard in Node-Tests ist `de` (S2); Bestandstests, die deutschen Quelltext prüfen, bleiben ohne `locale.set` gültig. Bestandstests, die den Quelltext statt des Verhaltens prüfen und durch die Umstellung brechen, werden auf SSR-Render oder `tr()`-Vergleich umgestellt, nicht gelöscht.
- Annahme: `ui/SaveIndicator.svelte` gehört nach F4 (Schlüssel `nav.gespeichert`), `tripHero.ts` und `schedulerTime.ts` nach F3, `alertMetricLabels.ts` nach F7; F11 fasst sie nicht an und trägt sie als engere Allowlist-Einträge ein.
- Annahme: `aktionen.json` wird von F11 mit den ersten Gemeinschaftstexten befüllt, weil F11 in der Reihenfolge vor F2–F10 läuft; spätere Pakete verwenden diese Schlüssel wieder.
- Annahme: Der Verwender-Test aus S4 erkennt `tr('…')`-Aufrufe; erkennt er nur `t(`, ergänzt F11 diese Erkennung minimal.
- Der Sprach-Store `locale` ist modulglobal; die Zwei-Nutzer-Sicherheit im Server-Render verantwortet S2. F11 stellt nur sicher, dass nichts beim Import aufgelöst wird.
- Die Codeliste `fehler.code.<code>` ist so vollständig wie `api_contract.md` zum Zeitpunkt der Umsetzung; spätere Codes zeigen bis zur Ergänzung den Server-Text.
- Metrik-Namen in `alertMetricLabels.ts` und Hilfstypen für `label_en` liefern F5 und F7.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Eine Sprache je Nutzer, ein Katalog je Schicht, Texte erst beim Aufruf aufgelöst; Protokollwerte und Eigennamen bleiben unübersetzt.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
