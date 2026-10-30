---
entity_id: i18n_f7_alarme_tab_2656
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2656, frontend, model-haiku]
---

# i18n F7: Katalog-Migration Alarme-Tab und alerts-tab-Bausteine

**Issue:** #2656 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend, `metricLabel`), 4 (Wettergrößen-Tabelle), 8

## Approval

- [ ] Approved

## Purpose

Die Alarm-Konfiguration (Abweichungs-Alarme, Regen-/Radar-Alarm, amtliche Warnungen, Schwellen und Empfindlichkeit, Kanäle je Alarm, Stille Stunden, Cooldown, Beispiel-Warnung) ist für englischsprachige Nutzer vollständig englisch. Schwellenwerte, Einheiten und Vergleichssymbole bleiben unverändert; Metrik-Namen kommen aus dem Register über `metricLabel`/`metricAlertLabel`. Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte`, `frontend/src/lib/components/shared/AlertChannelPicker.svelte`, `frontend/src/lib/components/shared/alarme-tab/**`, `frontend/src/lib/components/alerts-tab/**`, `frontend/src/lib/utils/alertMetricLabels.ts`
- **Identifier:** `ALERT_METRIC_LABELS`, `SEVERITY_LABEL_DE`, `alertMetricLabel` (neu), `PREMIUM_SMS_ALARM_HINT_NO_TIER` (premiumSmsAlarmGate.ts), `thresholdTitle` (alertMetricTable.ts), `activeAlertMetricsFromCatalog`, Katalog-Namensraum `alarme.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Alarm-Kurzformen (`alert_label`, ca. 10 Zeichen) und ihre englischen Gegenstücke (`alert_label_en`) kommen aus dem Backend-Register (P1), nicht aus dem Frontend-Katalog. Kein Python-/Go-Code.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/alarme.json` | MODIFY | Texte der Alarm-Konfiguration (wörtlich) |
| `frontend/src/lib/i18n/messages/en/alarme.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | `label=`-Texte, Eyebrows, Beispiel-Warnung, Hinweise |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte` | MODIFY | „Alert-Kanäle", „Dringlichkeits-Schwelle", Hinweis (Annahme A1: gehört zur Alarm-Konfiguration) |
| `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts` | MODIFY | `PREMIUM_SMS_ALARM_HINT_NO_TIER` verwendet den Schlüssel `versand.premium_sms.hinweis.nicht_verfuegbar` aus F6 |
| `frontend/src/lib/components/shared/alarme-tab/{activeAlertMetricsFromCatalog,tripAlertMetricsFromCatalog,alertChannelState,alarmeTabSections,alarmeDeliveryPayload}.ts` | MODIFY | nur Nutzertexte und Anzeigenamen (`metricLabel`); Logik, IDs, Payload unverändert |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | MODIFY | Überschriften, Leerzustand |
| `frontend/src/lib/components/alerts-tab/AlertCard.svelte` | MODIFY | „Melde ab Änderung:", „Kanal:" |
| `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte` | MODIFY | Preset-Namen, Tabelle „Schwellwerte nach Preset", `aria-label`, Zeilen-Bezeichnungen |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte` | MODIFY | Spaltenköpfe, „Alle Metriken auf:" |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte` | MODIFY | Titel/Optionen |
| `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` | MODIFY | Schweregrad-Optionen, Metrik-Name über `alertMetricLabel` |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | MODIFY | Eyebrows „Metrik", „Absoluter Schwellwert" |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | MODIFY | „Stille Stunden", Hinweis mit `{zonen_bezug}` |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | MODIFY | „Cooldown", Einheit „Minuten" |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | MODIFY | Hinweise, Links, `title` |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY | `thresholdTitle` („Richtwert — wird je Wettermodell und Gebiet umgerechnet") über `tr()`; Formeln (`Δ ≥ X`, `< X`) unverändert |
| `frontend/src/lib/utils/alertMetricLabels.ts` | MODIFY | `label_en` je Eintrag von `ALERT_METRIC_LABELS`, `alertMetricLabel(metric, lang)`, Schweregrad-Namen über Katalog (Annahme A2) |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `shared/AlarmeTab*`, `components/alerts-tab`, `shared/AlertChannelPicker`, `shared/alarme-tab` entfernen |
| `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` | CREATE | Tab de/en, Labels, zwei Nutzer, Golden |
| `tests/golden/f7_alarme_tab/*.de.html` | CREATE | Golden der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** `AlarmeTab.svelte` ist der geteilte Baustein (`context="route"|"vergleich"`); `alerts-tab/**` wird von beiden benutzt. Kein Nachbau; kontextabhängige Sätze haben zwei Schlüssel.
> - **Mandantentrennung:** Alarm-Regeln und Kanäle gehören dem angemeldeten Nutzer (`user_id` aus Auth-Kontext, unverändert). Anzeige-Texte dürfen nie in die gespeicherte Nutzlast gelangen. Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Alarme erreichen alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS); die Alarm-Kanal-Zeilen werden in beiden Sprachen mit demselben Inhalt beschriftet, Kanalnamen bleiben Eigennamen.

## Estimated Scope

- **LoC:** ca. 180 Code-Zeilen (ohne Katalog und Tests): ca. 100 Textstellen in `alerts-tab/`, ca. 35 in `AlarmeTab`/`AlertChannelPicker`, ca. 25 in `alertMetricLabels.ts`, ca. 20 Hilfsdateien.
- **Files:** 20 Code-/Katalogdateien plus 1 Test plus Golden
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2654 (F5) | Paket (vorher) | `metricLabel`, `metricAlertLabel` in `$lib/i18n/metricLabel.ts`, Schlüssel `wertebereiche.auswertung.*` |
| #2655 (F6) | Paket (vorher) | Schlüssel `versand.premium_sms.hinweis.nicht_verfuegbar` (kein zweiter Schlüssel für denselben Satz) |
| #2662 (P1) | Paket | `alert_label_en` im Register (alle ≤ 12 Zeichen) |
| #2647 (S2), #2649 (S4) | Pakete | Katalogkern, Ratsche, Allowlist |
| `docs/reference/i18n_glossar.md` | Doku | Alarm = alert, amtliche Warnung = official warning, Regen-/Radar-Alarm = rain alert (radar), Schwelle = threshold, Stufe = level |
| ADR-0104, ADR-0042 | adr | Alarm-Kurzform (`alert_label`) ist Klasse 2 und sprachabhängig, Platzgrenze ca. 10 Zeichen |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/alarme.json` bearbeiten. Platzhalter in beiden Sprachen gleich (`{zonen_bezug}`, `{wert}`, `{einheit}`).

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `alarme.tab.titel` | Sofort-Meldung zwischen den Briefings | Instant notifications between briefings |
| `alarme.tab.leer` | Keine Alerts konfiguriert. | No alerts configured. |
| `alarme.karte.melde_ab_aenderung` | Melde ab Änderung: | Notify from change of: |
| `alarme.karte.kanal` | Kanal: | Channel: |
| `alarme.stille_stunden.titel` | Stille Stunden | Quiet hours |
| `alarme.stille_stunden.hinweis` | In diesem Zeitraum keine Alerts senden (Ortszeit {zonen_bezug}) — gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit. | Do not send alerts in this period (local time {zonen_bezug}) — queued alerts go out with the next morning briefing. |
| `alarme.cooldown.einheit` | Minuten | minutes |
| `alarme.amtlich.label` | Amtliche Warnungen lösen Alert aus | Official warnings trigger an alert |
| `alarme.radar.label` | Radar-Alarm | Rain alert (radar) |
| `alarme.beispiel_warnung` | Beispiel-Warnung | Example warning |
| `alarme.tabelle.empfindlichkeit` | Empfindlichkeit | Sensitivity |
| `alarme.tabelle.schwellwert` | Schwellwert | Threshold |
| `alarme.preset.entspannt` | Entspannt | Relaxed |
| `alarme.preset.deaktiviert` | Deaktiviert | Off |
| `alarme.stufe.warning` | Warnung | Warning |
| `alarme.stufe.critical` | Kritisch | Critical |
| `alarme.kanaele.titel` | Alert-Kanäle | Alert channels |

**3. Metrik-Namen.** `ALERT_METRIC_LABELS` bekommt je Eintrag `label_en`; die Anzeige geht über `alertMetricLabel(metric, lang)` (neu, in derselben Datei). Werte (de bleibt wörtlich): `wind_gust` Böen → Wind gusts; `precipitation_sum` Niederschlag → Precipitation; `thunder_level` Gewitter → Thunderstorm; `snow_line` Schneefallgrenze → Snow line; `temperature_min` Temperatur (Minimum) → Temperature (minimum); `temperature_max` Temperatur (Maximum) → Temperature (maximum); `temperature_change` Temperatur (Änderung) → Temperature (change); `wind_change` Wind (Änderung) → Wind (change); `precipitation_change` Niederschlag (Änderung) → Precipitation (change); `fresh_snow` Neuschnee → Fresh snow; `cape` Gewitterenergie (CAPE) → Thunderstorm energy (CAPE); `visibility` Sichtweite → Visibility; `humidity` Luftfeuchtigkeit → Humidity; `freezing_level` Nullgradgrenze → Freezing level; `thunder_onset` Gewitter (Beginn) → Thunderstorm (onset); `precipitation_heavy_onset` Starkregen (Beginn) → Heavy rain (onset). `unit` und `comparison` bleiben unverändert. Für Katalog-abgeleitete Zeilen (`activeAlertMetricsFromCatalog.ts:56-66`) gilt `metricLabel(e, lang)`, die Auswertung in Klammern kommt aus `wertebereiche.auswertung.<id>` (F5).

**4. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte:32` — vorher `<Eyebrow>Stille Stunden</Eyebrow>`, nachher `<Eyebrow>{$t('alarme.stille_stunden.titel')}</Eyebrow>`.
- `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte:39` — vorher der Satz mit `{zonen_bezug}` im Markup, nachher `{$t('alarme.stille_stunden.hinweis', { zonen_bezug })}` (kein zusammengesetzter Satz).
- `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte:53` — vorher `{info?.label_de ?? metric}`, nachher `{alertMetricLabel(metric, $locale)}` (Fallback auf die Kennung bleibt).
- `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte:103-105` — vorher `<option value="info">Info</option> … Warnung … Kritisch`, nachher `{$t('alarme.stufe.warning')}` usw.; die `value`-Attribute bleiben.
- `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte:34-37` — die Preset-Namen (`Deaktiviert`, `Entspannt`, `Standard`, `Sensibel`) werden zu `$t('alarme.preset.<id>')`; die Zeilen-Tabelle (Böen, Niederschlag, Tiefsttemperatur …) bekommt je Zeile den Schlüssel `alarme.preset.zeile.<id>`, weil ihre deutschen Namen (z. B. „Tiefsttemperatur") von `ALERT_METRIC_LABELS` abweichen und byte-gleich bleiben müssen. Die Zahlen und Einheiten bleiben.
- `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts:28` — vorher die Konstante mit deutschem Satz, nachher `tr('versand.premium_sms.hinweis.nicht_verfuegbar')` (derselbe Satz wie im Versand-Tab).

**5. Nicht übersetzen.** Alarm-Kurzformen als Anzeige-Token der Mails (`alert_label` kommt aus dem Register über `metricAlertLabel`), Schwellenzahlen, Einheiten, Vergleichssymbole (`>`, `≥`, `<`, `Δ`), Kanalnamen, Metrik-IDs, `value`-Attribute, `data-testid`.

**6. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen (laut Issue `shared/AlarmeTab*`, `components/alerts-tab`).

**7. Golden-Fixture.** Vor der Umstellung den Tab für Nutzer `golden-de` im Trip-Kontext (mit Radar-Alarm und amtlichen Warnungen) und im Vergleichs-Kontext per SSR nach `tests/golden/f7_alarme_tab/<fall>.de.html` schreiben; danach byte-gleich vergleichen. `*.en.html` zur Review einchecken.

## Expected Behavior

- **Input:** Alarme-Reiter im Trip- und Ortsvergleich-Hub und beim Anlegen, Nutzer mit `language=en` oder `de`, Katalog mit oder ohne `label_en`/`alert_label_en`.
- **Output:** Alle Beschriftungen in der Nutzersprache; Schwellenwerte, Einheiten, Vergleichssymbole identisch; Metrik-Namen in der Nutzersprache, Fallback deutsch.
- **Side effects:** Keine. Gespeicherte Alarm-Regeln und Kanalwahl sind in beiden Sprachen identisch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch / When der Alarme-Tab im Trip-Hub und im Ortsvergleich-Hub lädt / Then sind alle Beschriftungen englisch („Quiet hours", „Rain alert (radar)", „Official warnings trigger an alert", „Alert channels"), und Schwellenwerte, Einheiten und Vergleichssymbole stehen unverändert.
  - Test: `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` — Render beider Kontexte mit `locale.set('en')`, Prüfung über `tr()`-Werte; Zahlen und Einheiten Gleichheit zur deutschen Ausgabe.

- **AC-2:** Given die Alarm-Metriken aus `ALERT_METRIC_LABELS` / When `alertMetricLabel` in Englisch und in Deutsch aufgerufen wird / Then liefert Englisch z. B. „Wind gusts", „Temperature (minimum)", „Thunderstorm energy (CAPE)", Deutsch weiterhin wörtlich „Böen", „Temperatur (Minimum)", „Gewitterenergie (CAPE)", und `unit` sowie `comparison` sind in beiden Sprachen gleich.
  - Test: `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` — Tabelle Metrik → Name für beide Sprachen; die vorhandenen Tests `alertMetricTable.test.ts` bleiben grün.

- **AC-3:** Given ein Katalog-Eintrag ohne `alert_label_en` oder `label_en` / When der Alarme-Tab in Englisch angezeigt wird / Then steht der deutsche Name, nie ein leerer Text, und zwei Zeilen mit gleichem Namen werden wie heute durch die Auswertung in Klammern unterschieden („Temperature (Maximum)" und „Temperature (Minimum)" bleiben getrennt).
  - Test: `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` — `activeAlertMetricsFromCatalog` mit fehlendem `label_en`, Doppelnamen-Fall.

- **AC-4:** Given Nutzer A (Englisch) und Nutzer B (Deutsch) mit denselben Alarm-Regeln / When beide den Alarme-Tab öffnen, eine Schwelle ändern und speichern / Then ist die gespeicherte Nutzlast bei beiden identisch (keine Anzeige-Texte darin), und jeder sieht nur seine Regeln in seiner Sprache.
  - Test: `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` — zwei Nutzer in einem Lauf, Vergleich der Speicher-Nutzlast (`rowStateToAlertRules`, `alarmeDeliveryPayload`).

- **AC-5:** Given der Hinweis „Premium-SMS ab Level Premium verfügbar" im Alarme-Tab und im Versand-Tab / When beide in Englisch angezeigt werden / Then stammen sie aus demselben Katalogschlüssel und lauten gleich („Premium SMS is available from the Premium level").
  - Test: `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` — Gleichheit von `premiumSmsAlarmGate` und `premiumSmsChannelState`-Hinweis in beiden Sprachen.

- **AC-6:** Given die deutsche Oberfläche / When der Alarme-Tab mit der Fixture `golden-de` gerendert wird / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f7_alarme_tab/*.de.html`.
  - Test: `frontend/src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-7:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keinen Eintrag mehr für `shared/AlarmeTab*` und `components/alerts-tab`, und `alarme` hat in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** `AlertChannelPicker.svelte` und `shared/alarme-tab/` stehen nicht in der Issue-Liste, gehören aber zur Alarm-Konfiguration und wären sonst ohne Besitzer.
- **A2 (Annahme):** `lib/utils/alertMetricLabels.ts` liegt im Allowlist-Bereich von F11 (`lib/utils`). Hat F11 die Datei schon angefasst und `label_en` bzw. Schweregrad-Schlüssel ergänzt, werden diese wiederverwendet, nicht verdoppelt; sonst ergänzt F7 sie.
- Die deutsche Preset-Tabelle nennt „Tiefsttemperatur"/„Höchsttemperatur", die Metrik-Tabelle „Temperatur (Minimum)/(Maximum)". Beide Wortlaute bleiben (byte-gleich), englisch jeweils „Low temperature"/„High temperature" bzw. „Temperature (minimum)/(maximum)".
- Die Alarm-Seite der Trip-Detail-Hub-Karte (`trip-detail/AlertsPreviewCard`, `AlarmeScheduleTab`) und `compare/alarmePropsAus.ts` gehören zu F9 bzw. F10.
- Texte der Alarm-Mails und -Nachrichten sind Python-Schicht (P5), nicht dieses Paket.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Die Alarm-Kurzform ist eine sprachabhängige Namensform mit Platzgrenze, Schwellen und Einheiten sind Daten und bleiben unverändert.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
