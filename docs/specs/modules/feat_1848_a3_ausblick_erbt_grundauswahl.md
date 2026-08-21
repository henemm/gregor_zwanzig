---
entity_id: feat_1848_a3_ausblick_erbt_grundauswahl
type: module
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [ausblick, metrik-kaskade, kanal-modul, adr-0050, issue-1848, issue-2029]
---

# #1848 A3 — Der 3-Tages-Ausblick verhält sich wie ein Kanal

## Approval

- [x] Approved — PO-Freigabe 2026-08-21 („go"), 12 ACs auf Deutsch vorgelegt

## Purpose

Der 3-Tages-Ausblick bekommt **exakt** das Bedienverhalten, das E-Mail, Telegram und SMS heute
schon haben: keine eigene Metrik-Auswahl, sondern die Grundauswahl als Ausgangsmenge, aus der über
den „Aus"-Knopf abgewählt und über die „Aus"-Gruppe zurückgeholt wird. Die zweite Kästchenliste
im Abschnitt „3-Tages-Vorschau" (Issue #2029) entfällt ersatzlos.

## Source

- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`
- **Identifier:** Kästchenliste `{#each groupCompareCatalog(catalog)}` (`:167-182`) und der
  `WeatherV2Reihenfolge`-Aufruf (`:196-206`)
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (beide Mountpunkte
  `:1403` Ortsvergleich, `:1786` Trip)
- **File:** `src/output/renderers/compare_outlook_metric_ids.py` (Auflösung + Klemme)
- **File:** `src/output/renderers/email/outlook.py` (Rückfall-Pfad)

## Estimated Scope

- **LoC:** ~230 (Frontend ~90, Backend ~60, Tests ~80)
- **Files:** ~9
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `WeatherV2Reihenfolge.svelte` | Komponente | trägt `offColumns`/`onRestore` bereits (`:47-52, 168-213`) |
| `channelMetricLayouts.splitChannelMetricsForDisplay()` | Funktion | `active = auswahl ∩ grund`, `off = grund \ active` (`:92-101`) |
| `UnifiedWeatherDisplayConfig.allowed_metric_ids_for_report_type()` | Funktion | Grundauswahl des Trips |
| `resolve_enabled_metrics(active_metrics)` | Funktion | Grundauswahl des Ortsvergleichs |
| ADR-0050 | Entscheidung | Regeln 1–4 (Maximum, nur abwählen, sofortige Wirkung, „Aus" ist ein Zustand) |
| ADR-0053 Punkt 1 | Entscheidung | wird durch diese Scheibe **abgelöst** (s. ADR-Abschnitt) |
| `fix_1719_s3_aus_ist_ein_zustand.md` AC-13 | Spec | wird durch diese Scheibe **abgelöst** |

## Implementation Details

### Vorher / Nachher (Bedienfläche)

```
VORHER (Screenshot #2029)          NACHHER (wie SMS/Telegram/E-Mail)
─────────────────────────          ─────────────────────────────────
3-Tages-Vorschau                   3-Tages-Vorschau
  [ ] Schneehöhe   Maximum           Reihenfolge · 7 Metriken
  [ ] Neuschnee    Summe               1 Temperatur    [Aus]
  [x] Wind         Maximum             2 Niederschlag  [Aus]
  ... 23 Kästchen ...                  ...
  Temperatur  [x]Max [x]Min          Aus in diesem Block
                                       Sichtweite      [Ein]
  Reihenfolge · 7 Metriken             UV-Index        [Ein]
    1 Temperatur (Min)  [Aus]
    2 Temperatur (Max)  [Aus]
    ...
```

### Datenfluss

```
Grundauswahl der Fläche          outlook_metrics (gespeicherte Abwahl)
  Trip:    display_config.metrics (enabled)          │
  Vergl.:  display_config.active_metrics             │
        │                                            │
        └──────────► splitChannelMetricsForDisplay ◄──┘
                              │
                     { active, off }
                              │
                     WeatherV2Reihenfolge
                       primaryColumns=active
                       offColumns=off
                       onRestore=…
```

`null` (nie eingestellt) = **nichts abgewählt** ⇒ `active` = ganze Grundauswahl, `off` = leer —
genau wie bei einem Kanal ohne eigenes Layout. Die bisherigen „sieben festen Spalten" entfallen
als Konzept.

## Expected Behavior

- **Input:** Grundauswahl der Fläche + gespeicherte Ausblick-Abwahl (`outlook_metrics`)
- **Output:** Ausblick-Tabelle mit genau den aktiven Größen, in der eingestellten Reihenfolge
- **Side effects:** `outlook_metrics` wird beim Abwählen/Zurückholen/Sortieren geschrieben
  (Kennungsformat seit A2, unverändert)

## Acceptance Criteria

### Block A — Die zweite Auswahl verschwindet

- **AC-1:** Given der Trip-Editor mit geöffnetem Abschnitt „3-Tages-Vorschau" / When die Seite
  geladen ist / Then existiert dort **keine** Kästchenliste der Wettergrößen mehr — sichtbar ist
  nur noch die Reihenfolge-Liste mit „Aus"-Knöpfen, exakt wie im SMS- und Telegram-Reiter.
  - Test: Staging-E2E — `compare-layout-outlook-metric-*`-Kästchen haben `toHaveCount(0)`,
    `wm2-reihenfolge-row` hat `toHaveCount(> 0)`.

- **AC-2:** Given der Ortsvergleich-Editor / When der Abschnitt „3-Tages-Ausblick" geöffnet ist /
  Then gilt AC-1 dort unverändert — dieselbe Komponente, dasselbe Verhalten, kein
  Compare-Sonderweg.
  - Test: eigener Staging-E2E-Lauf im Ortsvergleich (**nicht** summarisch mit dem Trip zusammen,
    sonst fängt er eine einseitige Verdrahtung nicht).

### Block B — Die Grundauswahl ist die Ausgangsmenge

- **AC-3:** Given ein Trip, dessen Grundauswahl 10 darstellbare Größen aktiv hat, und der im
  Ausblick noch nie etwas eingestellt hat / When das Briefing gerendert wird / Then zeigt die
  Ausblick-Tabelle genau diese 10 Größen — nicht die früheren sieben festen Spalten.
  - Test: Unit gegen den echten Renderer, Spaltenköpfe der gerenderten Tabelle auszählen.

- **AC-4:** Given eine Größe ist in der Grundauswahl abgewählt / When der Ausblick gerendert wird /
  Then erscheint sie dort **nicht** — unabhängig davon, was in `outlook_metrics` steht.
  - Test: Unit — Grundauswahl ohne `thunder`, `outlook_metrics` mit `thunder` ⇒ keine
    Gewitter-Spalte im gerenderten Ergebnis.

- **AC-5:** Given eine Größe steht nicht in der Grundauswahl / When der Ausblick-Block im Editor
  angezeigt wird / Then erscheint sie **weder** in der aktiven Liste **noch** in der „Aus"-Gruppe.
  - Test: Staging-E2E, Vorbild `kanal-abwahl-bleibt-reversibel.staging.spec.ts:165-210` (AC-9).

- **AC-6:** Given der Ortsvergleich mit `active_metrics` ohne `humidity` / When sein Ausblick
  gerendert wird / Then erscheint keine Luftfeuchtigkeits-Spalte — die Kopplung gilt in **beiden**
  Flächen gleich.
  - Test: Unit auf dem Compare-Auflösungsweg (`report_config_resolver`), gegen die gerenderte
    Vergleichsmail geprüft, nicht gegen den Rückgabewert.

### Block C — Abwählen und Zurückholen

- **AC-7:** Given der Ausblick zeigt eine Größe / When der Nutzer deren „Aus"-Knopf drückt / Then
  verschwindet sie aus der aktiven Liste, erscheint in der „Aus"-Gruppe, überlebt einen Reload und
  lässt sich dort mit „Ein" zurückholen.
  - Test: Staging-E2E in beiden Flächen, Vorbild `kanal-abwahl-bleibt-reversibel.staging.spec.ts:110-163`.

- **AC-8:** Given eine im Ausblick abgewählte Größe / When der Nutzer sie in der Grundauswahl
  aus- und wieder einschaltet / Then bleibt sie im Ausblick abgewählt — die Anwahl schreibt nicht
  durch.
  - Test: Staging-E2E, Vorbild AC-11 derselben Datei.

- **AC-9:** Given der Nutzer holt eine Größe über „Ein" zurück / When danach die Grundauswahl
  betrachtet wird / Then ist sie dort unverändert — Zurückholen schreibt ausschließlich in
  `outlook_metrics`, nie in die Grundauswahl.
  - Test: Unit auf dem Speicherweg + E2E-Ablesen der Grundauswahl.

### Block D — Der stille Totalausfall wird unmöglich

- **AC-10:** Given eine gespeicherte Ausblick-Auswahl, von der nach dem Schnitt gegen die
  Grundauswahl **nichts** übrig bleibt / When das Briefing gerendert wird / Then erscheint der
  Ausblick mit der vollen Grundauswahl und einer Protokoll-Warnung — **nicht** als verschwundener
  Block.
  - Test: Unit am **gerenderten** Block (Prüfort == Wirkort), nicht am Rückgabewert der Auflösung.

- **AC-11:** Given der Nutzer wählt im Ausblick **jede** Größe ab / When das Briefing gerendert
  wird / Then entfällt der Ausblick-Block vollständig — „bewusst geleert" bleibt vom Fall AC-10
  unterscheidbar.
  - Test: Unit, beide Fälle im selben Test gegenübergestellt.

### Block E — Keine Doppelpflege

- **AC-12:** Given die „Aus"-Berechnung des Ausblicks / When sie ausgeführt wird / Then benutzt sie
  `splitChannelMetricsForDisplay()` — dieselbe Funktion wie die Kanal-Reiter, kein zweiter
  Algorithmus.
  - Test: AST-Wächter auf den Aufruf; Mutation „eigene Mengenrechnung einsetzen" muss rot werden.

## Known Limitations

- **Die Ausblick-Tabelle wird für bestehende Touren breiter.** Wer heute sieben feste Spalten sieht
  und eine Grundauswahl mit mehr darstellbaren Größen hat, bekommt entsprechend mehr Spalten. Das
  ist die gewollte Folge von „exakt die Größen des Trips" (#2029) und über die „Aus"-Knöpfe
  jederzeit korrigierbar. **Kein Bestandsdatum geht verloren** — `outlook_metrics` ist auf Prod und
  Staging nirgends gesetzt (gemessen, 0 Treffer).
- Größen ohne Tagesauswertung (kein Eintrag in `derived_aggregations()`, z. B. `confidence`)
  erscheinen im Ausblick nicht, auch wenn sie in der Grundauswahl aktiv sind — sie haben dort
  keinen darstellbaren Wert. Sie stehen deshalb auch nicht in der „Aus"-Gruppe.
- Die Spaltenköpfe kommen weiterhin aus dem Compare-Katalog (ausgeschriebene deutsche Namen), nicht
  aus den Kürzeln `N/D/R/PR` des alten festen Pfads.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu anzulegen — löst **ADR-0053 Punkt 1** ab (dort: „Ausblick und Stundenverlauf
  bleiben bewusst global, ohne Kaskadenbindung"). Diese Scheibe bindet den Ausblick in **beiden**
  Flächen an die Grundauswahl und wendet damit ADR-0050 Regeln 1–4 auf die Ausgabefläche
  „Ausblick" an. Der Stundenverlauf bleibt unberührt.
- **Rationale:** Die Begründung von ADR-0053 Punkt 1 war ein Scheiben-Schnitt, keine fachliche
  Abgrenzung. Der Zustand danach ist genau das, was ADR-0053 im Kontext-Abschnitt selbst als
  „Attrappe" verwirft: 13 von 23 angebotenen Kästchen im Trip-Ausblick sind wirkungslos (gemessen,
  s. Kontext-Dokument M2). Zusätzlich löst diese Scheibe **AC-13 aus `fix_1719_s3`** ab, deren
  Begründung („der Ausblick hat bereits einen funktionierenden Rückweg über die Checkbox darüber")
  mit dem Wegfall ebendieser Checkboxen entfällt.

## Changelog

- 2026-08-21: Initial spec — PO-Entscheide: Ortsvergleich koppeln · Grundauswahl gilt immer ·
  Verhalten exakt wie E-Mail/Telegram/SMS (keine zweite Auswahl) · `temperature/avg` fällt ersatzlos
