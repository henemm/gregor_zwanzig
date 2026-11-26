# Context: feature-2990-kanal-ableitung (Issue #2990)

## Request Summary

Folge-Issue aus der Paritäts-Bestandsaufnahme #1986 (Eintrag NEU-9): Trip (`reportChannels`) und
Ortsvergleich (`presetChannels`) leiten die aktiven Versandkanäle getrennt ab. Ziel: EIN Baustein,
den beide Kontexte nutzen (Code-Teilungs-Vorgabe, CLAUDE.md „Trip/Ortsvergleich-Code-Teilung").

## Befund: drei Kopien derselben Ableitung, eine inhaltlich falsch

| Funktion | Ort | Quelle | Ausgabe | E-Mail-Regel |
|---|---|---|---|---|
| `reportChannels(rc)` | `frontend/src/routes/_home/cockpitHelpers.ts:130` | `ladeReportZustand(report_config)` → `leseBriefingStartwerte` | Schlüssel `email`/`telegram`/`sms`/`premium-sms` | `send_email !== false` |
| `heroKanaele(rc)` | `frontend/src/routes/_home/cockpitHelpers.ts:143` | dito, zusätzlich Slot-Regel (kein Slot aktiv → `[]`) | Anzeigenamen `Email`/`Telegram`/`SMS`/`Premium-SMS` | `send_email !== false` |
| `presetChannels(preset)` | `frontend/src/lib/components/compare/subscriptionHelpers.ts:284` | Top-Level-Felder des Presets | Anzeigenamen | **immer `Email`** (Kommentar „E-Mail ohne Opt-out (KL-6)") |

**Latenter Fehler:** Seit #2795 hat der Ortsvergleich `send_email` (fehlt = true, `types.ts:744`,
`compare_preset.go:92`), im Anlegen-Weg und Zustellungs-Reiter abwählbar (#3333, `zustellungModell`
`standAusPreset` liest `send_email`). `presetChannels` ignoriert das Feld → Liste, Detail-Hub-Stat
(`channelNamesLabel`), Startseiten-Kachel und `CompareStatusRow` zeigen „Email" auch bei
abgeschalteter Orts-Mail. Der Trip-Pfad tut das nicht. Die Zusammenführung behebt das mit.

## Related Files

- `frontend/src/lib/components/shared/briefingStartwerte.ts` — `leseBriefingStartwerte(rc)`: die
  bereits geteilte Lese-Regel der vier Kanal-Flags (#2987). Natürlicher Ort/Grundlage des Bausteins;
  pure, importiert nur aus `utils/` (node-testbar, keine Importzyklen).
- `frontend/src/lib/components/compare/subscriptionHelpers.ts` — `presetChannels`, `channelNamesLabel`.
- `frontend/src/routes/_home/cockpitHelpers.ts` — `reportChannels`, `heroKanaele`, `plannedBriefings` (nutzt Schlüssel für `ChannelChip kind=`).
- `frontend/src/routes/_home/SubscriptionKachel.svelte:25-36` — eigene `KANAL_NAME`-Abbildung Schlüssel → Anzeigename (vierte Kopie der Namenstabelle).
- Konsumenten `presetChannels`: `molecules/CompareStatusRow.svelte:27`, `organisms/SubscriptionCard.svelte:105`, `routes/compare/+page.svelte:95`, `SubscriptionKachel.svelte:35`.

## Existing Patterns

- #2987/#2989: „eine Quelle"-Refactors, Lesefunktion in `shared/`, alte Funktionen als dünne Wrapper.
- `channelNamesLabel` ist bereits dünner Wrapper um `presetChannels`.

## Tests (Wächter)

- `routes/_home/__tests__/subscription_kachel_paritaet.test.ts`, `home_hero_paritaet.test.ts` — Paritätswächter Trip↔Vergleich.
- `compare/__tests__/issue_582_list_helpers.test.ts`, `compare_preset_channels.test.ts`, `compare_preset_channels_premium_sms.test.ts` — `presetChannels`-Verhalten (kein Signal, Opt-in, leer → `['Email']`; bleibt gültig, da `send_email` fehlt = an).
- `utils/__tests__/report_slot_aktiv.test.ts:186` — `reportChannels`-Defaults.
- `molecules/issue_578_molecules_organisms.test.ts:195` — Quelltext-Regex `presetChannels(preset)` in CompareStatusRow (Dateiinhalt-Check; bleibt erfüllt, wenn der Name bleibt).
- Ausführung: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`.

## Dependencies / Dependents

Nur Frontend-Anzeige; Versand/Backend unberührt (Python entscheidet Versand selbst). Kein Schema-Eingriff.

## Risks

- Ausgabeformat unterscheidet sich (Schlüssel vs. Anzeigenamen): gemeinsamer Baustein muss beide bedienen, ohne Konsumenten zu brechen (`ChannelChip kind=` erwartet Schlüssel? — in Analyse klären).
- Verhaltensänderung beim Vergleich (`send_email:false` → kein „Email") ist gewollt (folgt PO-Entscheidung #2795), muss rot nachgewiesen werden.
- Kommentar „E-Mail ohne Opt-out (KL-6)" ist veraltet und wird mitkorrigiert.

## Analysis

**Type:** Feature (Refactor auf eine Quelle) mit Verhaltenskorrektur beim Ortsvergleich (`send_email:false`).
Kombinierter Durchgang Context+Analyse (Intake-Summe 1); `ChannelChip` normalisiert per
`toLowerCase().startsWith(...)`, akzeptiert also Schlüssel UND Anzeigenamen — die Ausgabeform ist
für die Chips unkritisch, nur für Text-Ausgaben (Kachel, `channelNamesLabel`, Listen-Pills) relevant.

### Affected Files

| Datei | Change | Inhalt |
|---|---|---|
| `frontend/src/lib/components/shared/aktiveKanaele.ts` | CREATE | `KANAL_ANZEIGENAME` (Schlüssel → Name), `aktiveKanaele(quelle)` → Schlüssel, `aktiveKanalNamen(quelle)` → Namen; Flags ausschließlich über `leseBriefingStartwerte` (E-Mail `!== false`, übrige `=== true`). Pure, importiert nur `briefingStartwerte.ts`. |
| `frontend/src/routes/_home/cockpitHelpers.ts` | MODIFY | `reportChannels` = `aktiveKanaele(rc)`; `heroKanaele` = Slot-Regel + `aktiveKanalNamen(rc)`. |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY | `presetChannels` = `aktiveKanalNamen(preset)` (Preset trägt die Flags top-level); veralteten KL-6-Kommentar korrigieren. Name bleibt (vier Konsumenten + Quelltext-Wächter #578). |
| `frontend/src/routes/_home/SubscriptionKachel.svelte` | MODIFY | lokale `KANAL_NAME`-Tabelle entfällt; Trip-Zweig nutzt `aktiveKanalNamen(report_config)`. |
| `frontend/src/lib/components/shared/__tests__/aktive_kanaele_2990.test.ts` | CREATE | Verhalten aus Nutzersicht: gleiche Flags → gleiche Kanäle für Trip-`report_config` und Ortsvergleich-Preset; `send_email:false` beim Preset → kein „Email" (RED heute). |

### Scope / Risk

5 Dateien, ca. 80–110 LoC inkl. Test. Risiko niedrig: nur Anzeige, Versand unberührt, kein Schema.
Bestehende `presetChannels`-Tests bleiben gültig (fehlendes `send_email` = an).

### Technical Approach

Eine Lese-Regel (existiert: `leseBriefingStartwerte`, #2987) + eine Kanalliste in fester Reihenfolge
Email · Telegram · SMS · Premium-SMS. Alte Funktionen bleiben als dünne Wrapper (Muster #2987/#2989),
damit Konsumenten nicht angefasst werden müssen. Paritätswächter (`subscription_kachel_paritaet`,
`home_hero_paritaet`) bleiben als Regressionswächter.

Verworfen: Ablage in `briefingStartwerte.ts` (Datei ist bewusst „Startwerte"; eigene Datei hält
Zuständigkeit klar) · Konsumenten auf neue Namen umstellen (mehr Dateien, kein Nutzen).

### Dependencies

`briefingStartwerte.ts` → `utils/reportSlotAktiv.ts`; keine Zyklen (shared importiert nicht aus compare/_home).

### Open Questions

Keine. Die Verhaltenskorrektur (abgeschaltete Orts-Mail nicht als Kanal zeigen) folgt der PO-Entscheidung #2795.
