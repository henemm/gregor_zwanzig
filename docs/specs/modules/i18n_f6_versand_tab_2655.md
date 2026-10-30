---
entity_id: i18n_f6_versand_tab_2655
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2655, frontend, model-haiku]
---

# i18n F6: Katalog-Migration Versand-Tab (Kanäle, Premium-SMS-Zustand, Telegram-Kurzstil, Zeitplan, nächstes Briefing)

**Issue:** #2655 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend), 8

## Approval

- [ ] Approved

## Purpose

Der geteilte Versand-Tab (Trip und Ortsvergleich) ist für englischsprachige Nutzer vollständig englisch: Kanal-Zustände (bestätigt, verbunden, gelernt, verfallen), Hinweise zu Premium-SMS und Telegram-Kurzstil, Briefing-Zeitplan, Laufzeit und die Zeile „Nächstes Briefing". Kanalnamen (E-Mail/Email, Telegram, SMS, Premium-SMS, Garmin inReach) bleiben Eigennamen. Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/lib/components/shared/VersandTab.svelte`, `frontend/src/lib/components/shared/versand-tab/**`, `frontend/src/lib/components/shared/TelegramKurzstilToggle.svelte`, `frontend/src/lib/components/shared/versand-tab/premiumSmsChannelState.ts`
- **Identifier:** `premiumSmsChannelState`, `channelConnectionStatus`, `sendTargetLabel`, `formatNextBriefing`, `vtBriefingLeadText`, `vtBriefingSubTexts`, `grundText`, `wochentag`, Katalog-Namensraum `versand.*` (und der bestehende Bereich `telegram_kurzstil.*`)

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Backend-Felder (`premium_sms_reply_state`, `NextBriefing.reason`) und Protokoll-Werte bleiben unverändert; nur die Anzeige wird übersetzt.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/versand.json` | MODIFY | Texte des Versand-Tabs (wörtlich) |
| `frontend/src/lib/i18n/messages/en/versand.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | nur sichtbare Texte (falls vorhanden) |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | Eyebrow, Hinweis zur Nummernbestätigung, Checkbox-Zusätze |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` | MODIFY | Zeitplan-Texte, Morgen-/Abend-Briefing, Trend |
| `frontend/src/lib/components/shared/versand-tab/VTLaufzeitRoute.svelte` | MODIFY | Laufzeit-Texte Trip |
| `frontend/src/lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte` | MODIFY | Laufzeit-Texte Ortsvergleich |
| `frontend/src/lib/components/shared/versand-tab/VTNextBriefing.svelte` | MODIFY | „Nächstes Briefing" |
| `frontend/src/lib/components/shared/versand-tab/vtBriefingChannelsText.ts` | MODIFY | Einleitung und Unterzeilen über `tr()` |
| `frontend/src/lib/components/shared/versand-tab/premiumSmsChannelState.ts` | MODIFY | Statusworte, Hinweise, „zuletzt gemeldet am" über `tr()` |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts` | MODIFY | Statusworte (bestätigt, verbunden, hinterlegt …) über `tr()` |
| `frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts` | MODIFY | Sende-Ziel-Sätze (Dialog „Geht an …") über `tr()` |
| `frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts` | MODIFY | Gründe, Wochentage, „wird übersprungen", „wird nachgeholt" |
| `frontend/src/lib/components/shared/versand-tab/{nextBriefingLoad,naechstesBriefingLader.svelte,channelContactLabel,reportConfigPayload}.ts` | MODIFY | nur Nutzertexte, falls vorhanden (Kommentare und Logik nicht anfassen) |
| `frontend/src/lib/components/shared/TelegramKurzstilToggle.svelte` | MODIFY | Checkbox-Beschriftung „Telegram im SMS-Kurzstil"; die Hinweise `telegram_kurzstil.hinweis_*` bestehen schon |
| `frontend/src/lib/i18n/messages/en/<Bereichsdatei der telegram_kurzstil-Schlüssel>.json` | MODIFY | englische Texte der beiden bestehenden Schlüssel `telegram_kurzstil.hinweis_aktiv`, `.hinweis_inaktiv` sicherstellen |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `shared/versand-tab`, `shared/TelegramKurzstilToggle`, `shared/versand*`, `shared/VersandTab.svelte` entfernen |
| `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` | CREATE | Versand-Tab de/en, Trip und Vergleich, zwei Nutzer, Golden |
| `frontend/src/lib/components/shared/versand-tab/__tests__/versand_texte_ohne_wertung_en.test.ts` | CREATE | englische Hinweise ohne wertende Wörter |
| `tests/golden/f6_versand_tab/*.de.html` | CREATE | Golden der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Der Versand-Tab ist ein geteilter Baustein (`context="route"|"vergleich"`), `TelegramKurzstilToggle` ebenfalls; es entsteht kein Nachbau. Kontextabhängige Sätze (`vtBriefingLeadText`) bekommen zwei Schlüssel (`versand.briefing.lead.route`, `versand.briefing.lead.vergleich`).
> - **Mandantentrennung:** Die Zustände entstehen aus dem Profil des angemeldeten Nutzers (`user_id` aus Auth-Kontext, unverändert). Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Alle vier Kanäle sind benannt; gleiche Bedeutung in beiden Sprachen. Kanalnamen bleiben Eigennamen. Telegram-Kurzstil und Premium-SMS behalten Kürzel und Befehlswörter (Kurzform ist Platzform, ADR-0042).

## Estimated Scope

- **LoC:** ca. 140 Code-Zeilen (ohne Katalog und Tests): ca. 80 Textstellen in `.ts`-Modulen, ca. 50 in `.svelte`, ca. 10 Wochentags- und Datums-Hilfen.
- **Files:** 17 Code-/Katalogdateien plus 2 Tests plus Golden
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2647 (S2) | Paket | `t`, `tr`, `locale`, `fmtDate`; Katalogbereich `versand` bereits angelegt |
| #2649 (S4) | Paket | Ratsche und Allowlist |
| `docs/reference/i18n_glossar.md` | Doku | Versand = delivery, Kurzstil = compact style, Kopplung = linking, Premium-SMS-Kanalname |
| `docs/reference/premium_sms_format.md` | Doku | Kurzform bleibt unabhängig von der Sprache |
| ADR-0104, ADR-0042 | adr | Kanalnamen und Kurzform sind Platzform, nicht Sprache |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/versand.json` (und die zwei vorhandenen `telegram_kurzstil.*`-Schlüssel in deren Bereichsdatei) bearbeiten. Platzhalter in beiden Sprachen gleich benennen (`{telegram_spalten}`, `{zeichen}`, `{datum}`).

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `versand.kanaele.titel` | Geplantes Briefing · Kanäle | Planned briefing · channels |
| `versand.status.bestaetigt` | bestätigt | confirmed |
| `versand.status.eingetragen_unbestaetigt` | eingetragen, unbestätigt | entered, unconfirmed |
| `versand.premium_sms.nicht_verfuegbar` | nicht verfügbar | not available |
| `versand.premium_sms.hinweis.nicht_verfuegbar` | Premium-SMS ab Level Premium verfügbar | Premium SMS is available from the Premium level |
| `versand.premium_sms.zuletzt_gemeldet` | zuletzt gemeldet am {datum} | last reported on {datum} |
| `versand.briefing.lead.route` | Das Trip-Briefing ist eine Etappen-Tabelle — E-Mail trägt alle Spalten, Telegram die ersten {telegram_spalten}, SMS kein Raster, Fließtext. | The trip briefing is a stage table — email carries all columns, Telegram the first {telegram_spalten}, SMS has no grid, plain text. |
| `versand.briefing.sub.email` | Layout · volle Tabelle | Layout · full table |
| `versand.briefing.sub.sms` | Layout · kein Raster, {zeichen} Zeichen | Layout · no grid, {zeichen} characters |
| `versand.zeitplan.titel` | Briefing-Zeitplan | Briefing schedule |
| `versand.zeitplan.morgen` | Morgen-Briefing | Morning briefing |
| `versand.zeitplan.abend` | Abend-Briefing | Evening briefing |
| `versand.laufzeit.route` | Läuft mit der Trip · endet {ende} | Runs with the trip · ends {ende} |
| `versand.naechstes.titel` | Nächstes Briefing | Next briefing |
| `versand.naechstes.grund.manual` | nur manueller Versand | manual delivery only |
| `versand.naechstes.uebersprungen` | wird übersprungen | is skipped |
| `telegram_kurzstil.checkbox` | Telegram im SMS-Kurzstil | Telegram in SMS compact style |

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/shared/versand-tab/premiumSmsChannelState.ts:71-72` — vorher `statusLabel: 'nicht verfügbar', hint: 'Premium-SMS ab Level Premium verfügbar'`, nachher `statusLabel: tr('versand.premium_sms.nicht_verfuegbar'), hint: tr('versand.premium_sms.hinweis.nicht_verfuegbar')`.
- `frontend/src/lib/components/shared/versand-tab/premiumSmsChannelState.ts:58` — vorher `` `zuletzt gemeldet am ${reportedAt}` ``, nachher `tr('versand.premium_sms.zuletzt_gemeldet', { datum: reportedAt })`; `formatReportedAt` bleibt bei Deutsch `TT.MM.JJJJ`, bei Englisch `fmtDate(d, 'en', 'kurz')` (Annahme A2).
- `frontend/src/lib/components/shared/versand-tab/vtBriefingChannelsText.ts:33-34` — vorher der zusammengesetzte deutsche String, nachher `tr('versand.briefing.lead.route', { telegram_spalten: CHANNEL_COL_BUDGET.telegram })` (keine Satz-Konkatenation).
- `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte:124` — vorher `<Eyebrow …>Geplantes Briefing · Kanäle</Eyebrow>`, nachher `<Eyebrow …>{$t('versand.kanaele.titel')}</Eyebrow>`.
- `frontend/src/lib/components/shared/TelegramKurzstilToggle.svelte:57` — vorher `>Telegram im SMS-Kurzstil</Checkbox>`, nachher `>{$t('telegram_kurzstil.checkbox')}</Checkbox>`; die Zeilen 61/63 nutzen `t(...)` schon — nach S2 als `$t(...)` lesen.
- `frontend/src/lib/components/shared/versand-tab/nextBriefingText.ts:29,55` — `WOCHENTAGE` entfällt zugunsten `versand.wochentag.0` … `.6` (de So Mo Di Mi Do Fr Sa, en Sun Mon Tue Wed Thu Fri Sat); `pausiert bis ${bis}` wird `tr('versand.naechstes.pausiert_bis', { bis })`.

**4. Format-Hinweise.** `nextBriefingText.ts`: der Wochentag wird weiter über `getUTCDay()` ermittelt (zonenfrei, wie heute); die Namen kommen aus `versand.wochentag.<n>`. Das Datum in „pausiert bis" bleibt bei Deutsch `TT.MM.` (String-Zerlegung), bei Englisch `fmtDate(new Date(jahr, monat - 1, tag, 12), 'en', 'kurz')` (z. B. `Wed 28 Oct`). Die Uhrzeit bleibt `HH:MM` mit Zonenkürzel.

**5. Nicht übersetzen.** Kanalnamen und Zusätze (`E-Mail`/`Email`, `Telegram`, `SMS`, `Premium-SMS (Garmin inReach)`), Kontakt-Suffixe ` (adresse)`, Zonenkürzel, `NextBriefing.reason`-Werte, `data-testid`, Kürzel und Befehlswörter. Im englischen Fließtext heißt der Kanal „Premium SMS" (Glossar), in Beschriftungen mit Zusatz bleibt `Premium-SMS (Garmin inReach)`.

**6. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen (laut Issue `shared/versand-tab`, `shared/TelegramKurzstilToggle`, `shared/versand*`).

**7. Golden-Fixture.** Vor der Umstellung für Nutzer `golden-de` mit den Profilen „alles gekoppelt", „Premium-SMS verfallen" und „nur E-Mail" den Tab in beiden Kontexten per SSR nach `tests/golden/f6_versand_tab/<fall>.de.html` schreiben; nach der Umstellung byte-gleich vergleichen, ebenso die reinen Funktionen (`premiumSmsChannelState`, `formatNextBriefing`, `vtBriefingSubTexts`) als Tabelle `Eingabe → Ausgabe`. `*.en.html` zur Review einchecken.

## Expected Behavior

- **Input:** Versand-Reiter im Trip- und im Ortsvergleich-Hub und beim Anlegen, Nutzer mit `language=en` oder `de`, verschiedene Profile (Kanäle gekoppelt oder nicht, Premium-SMS-Zustand `none`/`fresh`/`stale`), Backend-Wert `NextBriefing`.
- **Output:** Alle Beschriftungen und Hinweise in der Nutzersprache; Kanalnamen, Kontakte, Uhrzeiten, Zonenkürzel unverändert.
- **Side effects:** Keine. Die gespeicherte `report_config` ist in beiden Sprachen identisch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch / When der Versand-Tab im Trip-Hub und im Ortsvergleich-Hub lädt / Then sind beide mit demselben Baustein englisch („Planned briefing · channels", „Morning briefing", „Next briefing"), und die Kanalnamen Telegram, SMS und „Premium-SMS (Garmin inReach)" stehen unverändert.
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` — Render beider Kontexte mit `locale.set('en')`, Prüfung über `tr()`-Werte; ein Baustein.

- **AC-2:** Given ein Profil mit Premium-SMS-Zustand `none`, `fresh` und `stale` und ein Profil ohne Premium-Tarif / When `premiumSmsChannelState` in Englisch ausgewertet wird / Then liefert die Funktion die englischen Statuswörter („not connected", „learned", „expired", „not available") und Hinweise, `disabled` und `tone` sind in beiden Sprachen identisch.
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` — Tabelle Zustand → Text für `en` und `de`; `disabled`/`tone` Gleichheit zwischen den Sprachen.

- **AC-3:** Given der Backend-Wert `NextBriefing` mit Grund `paused` (bis 28.10.), `manual`, `ended` sowie mit Termin und übersprungenem Slot / When `formatNextBriefing` in Englisch aufgerufen wird / Then lauten die Texte „paused until Wed 28 Oct", „manual delivery only", „Trip ended" bzw. „Location comparison ended" und „Wed 07:00 (CEST) — Thu 07:00 is skipped"; in Deutsch bleiben sie byte-gleich (z. B. `pausiert bis 28.10.`).
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` — Eingabe/Ausgabe-Tabelle in beiden Sprachen; die vorhandenen Tests `naechstes_briefing_text.test.ts` bleiben grün.

- **AC-4:** Given Nutzer A (Englisch, Telegram gekoppelt) und Nutzer B (Deutsch, nur E-Mail) / When beide den Versand-Tab und den Sende-Dialog öffnen / Then zeigt A englische Sätze mit seinen Kanälen („Goes to …" ohne die Kanäle von B), B deutsche Sätze mit seinen Kanälen, und die gespeicherte `report_config` hat in beiden Sprachen dieselbe Form.
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` — zwei Nutzer in einem Lauf (`sendTargetLabel` mit je eigenem Profil), Vergleich der Nutzlast.

- **AC-5:** Given die englischen Hinweistexte des Tabs / When sie auf wertende Wörter geprüft werden / Then enthalten sie keine Bewertung der Kanäle (z. B. „flat", „bad", „better", „should"), analog zum bestehenden deutschen Wächter `vtBriefingChannelsTextNoJudgement`.
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/versand_texte_ohne_wertung_en.test.ts` — Wortliste auf `vtBriefingLeadText` und `vtBriefingSubTexts` für beide Kontexte.

- **AC-6:** Given die deutsche Oberfläche / When der Versand-Tab mit den Golden-Profilen für Nutzer `golden-de` gerendert wird / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f6_versand_tab/*.de.html`, und die deutschen Funktionsergebnisse entsprechen den bisherigen Werten.
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-7:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keinen Eintrag mehr für `shared/versand-tab` und `shared/TelegramKurzstilToggle`, und `versand` (inkl. `telegram_kurzstil.*`) hat in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** Wo die Schlüssel `telegram_kurzstil.*` nach S2 liegen, bestimmt S2; F6 trägt die fehlenden englischen Texte in der dortigen Bereichsdatei nach.
- **A2 (Annahme):** Das Meldedatum der Premium-SMS-Rückadresse erscheint englisch als `Thu 30 Oct` ohne Jahr (die Rückadresse verfällt nach 30 Tagen, das Jahr ist eindeutig); deutsch bleibt `TT.MM.JJJJ`.
- **A3 (Annahme):** Die Wochentage in „Nächstes Briefing" kommen aus eigenen Katalogschlüsseln statt aus `fmtWeekday`, damit die zonenfreie Berechnung (`getUTCDay`) erhalten bleibt.
- Der Satz „Läuft mit der Trip" ist der heutige Wortlaut und wird nicht korrigiert (Rechtschreibung ist nicht Teil des Epics).
- `formatNextBriefing` wird auch vom Cockpit (F3, `kachelVersand.ts`) benutzt; bis F6 fertig ist, bleibt die Versand-Zeile dort deutsch.
- Kontextlose Basiswörter (Aktiv, Uhrzeit) liegen in `versand.*`; eine Zusammenführung mit `aktionen.*` ist kein Teil dieses Pakets.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Kanalnamen und Kurzform sind Platzform und bleiben, nur Beschriftungen und Hinweise folgen der Nutzersprache.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
