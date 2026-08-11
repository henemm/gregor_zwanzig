---
entity_id: fix_1719_s3_aus_ist_ein_zustand
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [frontend, metrik-kaskade, editor, adr-0050, issue-1719]
---

# #1719 Scheibe S3 — Der Editor: „Aus" ist ein Zustand, und die Zahlen sagen die Wahrheit

## Approval

- [x] Approved — PO, 2026-08-11 („go"). Schließt die Anhebung des LoC-Limits auf 2600 ein.

## Purpose

Der Editor löst die in **ADR-0050 Regel 4** bereits getroffene Zusage ein: eine im Kanal
abgewählte Metrik **bleibt sichtbar und wieder einschaltbar**, statt aus der Liste zu
verschwinden. Gleichzeitig hören die Kanal-Hinweise auf, dem Nutzer zu sagen, was wichtig
ist, und fangen an, die echten Platzgrenzen zu nennen. Die Live-Vorschau „So kommt es an"
entfällt ersatzlos.

**S2 hat die Wirkung abgefangen, S3 repariert die Ursache.** Der Backend-Schnitt verhindert,
dass ein Widerspruch zwischen Grundauswahl und Kanal-Ebene *ausgeliefert* wird; der Editor
**erzeugt** ihn bis heute bei jedem Speichern.

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** `onToggleMetric`, `onRemove`, `channelView`, `buildWeatherPayload`
- **Schicht:** **Frontend** (SvelteKit). Kein Go, kein Python — der Backend-Schnitt aus S2
  bleibt unverändert, `src/app/loader.py:836-875` wird nicht angefasst.

## Estimated Scope

- **LoC:** ~2400–2600 berührte Zeilen, davon **~1250 reine Löschung**
- **Files:** 20–23 (10 geändert, 6 gelöscht, 4–7 Tests neu/geändert)
- **Effort:** high
- **🔴 LoC-Override:** Das im Intake freigegebene Limit **1800 reicht nicht**. Die
  Messung hat die Vorschau-Löschung als Umbau entlarvt (Pflicht-Snippet-Vertrag,
  zwei zusätzliche E2E-Dateien). **Benötigt: 2600.** Ohne Freigabe dieser Zahl muss die
  Scheibe geteilt werden.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| ADR-0050 | Zusage | Regeln 1–4; Regel 4 ist der Kern dieser Scheibe |
| ADR-0049 | Zusage | Kanalliste; Premium-SMS erbt SMS transitiv |
| `models.py::_clip_to_global_maximum()` | Backend (S2) | schneidet beim Lesen — bleibt unverändert |
| `src/output/renderers/channel_layout.py:45-54` | Backend | Quelle der echten Platzgrenzen |
| `internal/handler/config_merge.go` | Go | ersetzt `channel_layouts` als GANZES ⇒ Client muss vollständig senden |

## Implementation Details

### 1. Die Naht zur geteilten Zeilen-Komponente

`WeatherV2Reihenfolge.svelte` hat **vier** Einbettungen; der ADR-0050-Grund greift nur an
**einer** (`WeatherMetricsTab.svelte:1280`, Trip-Kanal-Reiter). Die drei Vergleichs-Stellen
arbeiten auf einem flachen Array und haben über der Liste bereits eine Checkbox als Rückweg.

```ts
// WeatherV2Reihenfolge.svelte — neue Props, OHNE Vorgabewert
interface Props {
	// ... bestehende ...
	offColumns?: string[];              // undefined = Bauteil verhält sich exakt wie bisher
	onRestore?: (id: string) => void;
}
```

**Verzweigung auf `offColumns !== undefined`, nicht auf `.length`.** Ein Vorgabewert `[]`
würde „nicht übergeben" und „explizit leer" ununterscheidbar machen — dann argumentiert die
Spec mit Anwesenheit und der Code prüft Inhalt.

### 2. Darstellung von „Aus"

Aktive Metriken bleiben in der bestehenden `SortableList`. Abgewählte erscheinen **darunter**
in einer eigenen, nicht sortierbaren Gruppe „Aus in diesem Kanal", jede Zeile mit demselben
Namen/Kürzel-Aufbau und einem `Ein`-Knopf.

**Bewusste Abweichung vom Wortlaut „die Zeile bleibt stehen":** Eine inaktive Metrik hat im
Datenmodell keine Position (`buckets.off` ist ungeordnet, `buildWeatherConfigMetrics` setzt
`order: 0`). Innerhalb der sortierbaren Liste bekäme sie eine Positionsnummer und einen
Ziehgriff, die nichts bedeuten. Der **Zweck** der Regel — laut ADR-0050 Zeile 70-72: „sonst
ist die Metrik im Kanal-Reiter unerreichbar" — ist mit der sichtbaren Gruppe erfüllt.

### 3. Welche Metriken die Kanal-Liste zeigt

```
aktiv  = channelView(ch).buckets.primary
aus    = buckets.primary (GLOBAL)  minus  aktiv
```

Damit erscheinen global abgewählte Metriken **nirgends** im Kanal-Reiter — ADR-0050 Regel 1
und 2 sind allein durch die Anzeige erfüllt, ohne Sonderlogik.

### 4. Durchschreibung — und der Persistenz-Fix

`onToggleMetric` schiebt bei **Abwahl** die Metrik in **allen** vorhandenen
`channelBuckets`-Einträgen nach `off` (Regel 3). Bei **Anwahl** bleiben die Kanal-Zustände
unangetastet — die Zeile ist ab S3 im Kanal-Reiter sichtbar, der Nutzer entscheidet dort
(Grundsatz „keine Bevormundung").

🔴 **Ohne den folgenden Fix käme die Durchschreibung nie am Server an:**

```ts
// heute — schreibt NUR den aktiven Kanal, alle anderen kommen aus dem Server-Stand
mergeChannelLayoutsForSave(trip!.display_config?.channel_layouts, activeChannel, metrics)
```

`buildWeatherPayload` muss **jeden** nicht-`null`-Eintrag aus `channelBuckets` serialisieren.
Sonst gilt: Nutzer steht im E-Mail-Reiter, SMS hat einen Override, globale Abwahl → Ansicht
stimmt, gespeichert wird nur E-Mail, nach dem Neuladen ist der Widerspruch zurück. Das wäre
**eine neue Verletzung von ADR-0050 Regel 3**, eingebaut von der Scheibe, die sie beheben soll.

Der Datenverlust-Schutz aus #1575 (`config_merge.go` ersetzt `channel_layouts` als Ganzes)
bleibt dabei gewahrt — es werden **mehr** Kanäle gesendet, nie weniger.

### 5. Platzgrenzen ehrlich modellieren

Der Sentinel `CHANNEL_COL_BUDGET.sms = 0` wird **nicht durch eine Zahl ersetzt** — er ist als
Spaltenzahl korrekt (`src/output/renderers/channel_layout.py:48`, SMS hat kein Raster). Falsch ist die Prosa, die
daraus eine Ordnungsaussage macht. Modelliert wird die **Einheit**:

```ts
type LtLimit =
	| { kind: 'none' }
	| { kind: 'columns'; value: number }
	| { kind: 'chars'; value: number };
```

| Kanal | Limit | Beleg |
|---|---|---|
| E-Mail | `{kind:'none'}` | `src/output/renderers/channel_layout.py:46` |
| Telegram | `{kind:'columns', value: 7}` | `src/output/renderers/channel_layout.py:110` `metric_slots = limit - 1` |
| SMS | `{kind:'chars', value: …}` | `src/output/renderers/trip_report.py:446` (160, Trip) / `src/output/renderers/channel_layout.py:48` (153, Vergleich) |

Der Zeichenwert kommt **vom Aufrufer**, nicht aus der Konstante — genau wie `hasLabelColumn`
bei `LTCapNote.svelte:23`. Eine einzige geteilte Zahl wäre in einer der beiden Richtungen
nachweislich falsch.

**Überlauf für `kind:'chars'` wird ausdrücklich NICHT berechnet.** Dafür bräuchte der Editor
die fertig gebaute SMS-Zeile; die Kürzel sind 2–17 Zeichen lang und die Kürzung arbeitet
kategorienweise (`sms_format.md` §6). Eine Schätzzahl wäre die zweite falsche Behauptung an
derselben Stelle. `ltBadge` zeigt für `chars` die Zeichenzahl, `ltOverflow` liefert für
`chars` keinen Eintrag.

### 6. Telegram 7 statt 8

`metricsEditor.ts:224-232` verspricht 8 Metrik-Spalten „Uhrzeit NICHT mitgezählt"; das
Backend liefert 7 (die 8. Spalte **ist** die Uhrzeit). Drei unabhängige Quellen sagen 7:
`src/output/renderers/channel_layout.py:110`, `src/output/renderers/narrow.py:148` (`headers = ["Zt"] + …`) und
`WeatherMetricsTab.svelte:1120-1121` (Vergleichs-Zweig umgeht die Konstante bereits genau
deswegen). Die Kapplinie rutscht damit um eine Position nach oben.

### 7. Was gelöscht wird

| Datei | Zeilen | Grund |
|---|---|---|
| `shared/weather-metrics-tab/WeatherV2MailPreview.svelte` | 597 | PO-Entscheid |
| `trip-detail/smsFidelityPreview.ts` | 45 | einziger Verwender war die Vorschau |
| `…/__tests__/weather_v2_mail_preview_sms_fidelity.test.ts` | 225 | testet Gelöschtes |
| `shared/__tests__/weather_metrics_tab_vergleich_no_sms_preview.test.ts` | 82 | testet Abwesenheit der Vorschau |
| `trip-detail/__tests__/sms_fidelity_preview_fetch.test.ts` | 84 | testet Gelöschtes |
| `e2e/fix-923b-wire-live-sms-preview.staging.spec.ts` | 213 | prüft ausschließlich die Vorschau |

`frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` verliert die rechte
Spalte: `preview: Snippet<…>` (`:28`) ist heute
**Pflicht**-Prop, die Hülle ein Zwei-Spalten-Raster mit eigener Überschrift „So kommt es an"
(`:44-56`). Dazu entfallen `mailSheetOpen` (`:221`), der Mobile-FAB (`:1568`) und der
`Sheet`-Wrapper (`:1572-1574`) in `WeatherMetricsTab.svelte`.

## Expected Behavior

- **Input:** Nutzer bedient den Reiter „Wetter-Metriken" eines Trips — Grundauswahl
  (Abschnitt 02) und Kanal-Reiter (Abschnitt 03, E-Mail/Telegram/SMS).
- **Output:** Der Kanal-Reiter zeigt **alle** Metriken der Grundauswahl, getrennt in „aktiv"
  (sortierbar) und „aus" (wieder einschaltbar). Kanal-Hinweise nennen Platzgrenzen ohne
  Wertung. Keine Live-Vorschau mehr.
- **Side effects:** Ein Speichern schreibt ab jetzt **alle** angefassten Kanal-Ebenen, nicht
  nur die aktive. Trips, deren Kanal-Ebene eine global abgewählte Metrik führte, verlieren
  diesen Eintrag beim nächsten Speichern — das ist die von ADR-0050 gewollte Wirkung.

## Acceptance Criteria

### Block A — Die Live-Vorschau ist weg

- **AC-1:** Given ein Trip mit aktiven Metriken / When der Nutzer den Reiter
  „Wetter-Metriken" öffnet / Then existiert weder die Vorschau-Spalte („So kommt es an")
  noch der Mobile-Knopf, der sie öffnet — auf Desktop- **und** Mobil-Breite.
  - Test: Playwright-Klickpfad gegen Staging, beide Viewports; `wm2-mail-preview` und
    `mobile-mail-fab` sind nicht im DOM.

- **AC-2:** Given der Reiter ohne Vorschau / When der Nutzer den Kanal wechselt und eine
  Metrik zieht / Then bleiben Kanal-Wähler, Reihenfolge-Liste und Kappungs-Hinweis vollständig
  bedienbar, und die Seite scrollt nicht horizontal.
  - Test: Playwright-Klickpfad; Reihenfolge nach Reload unverändert, `scrollWidth <= clientWidth`.

### Block B — Die Zahlen und Texte sagen die Wahrheit

- **AC-3:** Given ein Trip mit 9 aktiven Metriken / When der Nutzer den Telegram-Reiter öffnet
  / Then sitzt die Kapplinie **nach der siebten** Metrik und der Überlauf-Chip nennt **2**.
  - Test: Playwright-Klickpfad; Position der Kapplinie und Chip-Zahl abgelesen.

- **AC-4:** Given der SMS-Reiter / When der Nutzer ihn öffnet / Then nennt die Oberfläche die
  **Zeichengrenze des Trip-Pfads (160)** — nicht „—", nicht „140" — und behauptet nirgends eine
  Spaltengrenze für SMS.
  - Test: Playwright-Klickpfad liest Chip und Hinweistext; Unit-Test auf das Limit-Modell.

- **AC-5:** Given einen beliebigen Kanal-Reiter / When der Nutzer die Hinweistexte liest /
  Then enthält keiner davon eine **Wertung** darüber, welche Werte wichtig sind, und keiner
  eine **unwahre Behauptung** über die Fähigkeiten des Kanals.
  - Test: Unit-Test über die erzeugten Texte aller drei Kanäle gegen zwei getrennte Listen.
  - **Verboten (Wertung):** „entscheidungskritisch", „nur das Wesentliche", „nur die
    wichtigsten", „läuft flach"/„wird flach".
  - **Verboten (unwahr):** „140" als Zeichengrenze, „kennt keine Spalten-Reihenfolge",
    „keine Reihenfolge", „max 8 Spalten" für Telegram.
  - **Ausdrücklich ERLAUBT:** „kein Raster", „keine Tabelle", „Fließtext", „160 Zeichen",
    „max 7 Spalten". Das sind gemessene Tatsachen, keine Bevormundung.

  > 🔴 **Spec-Korrektur nach RED-Befund (2026-08-11).** Die Erstfassung führte „kein Raster"
  > und „nur Fließtext" als verbotene Wendungen. Beides ist **wahr**
  > (`src/output/renderers/channel_layout.py:48`, `max_table_cols = 0`) — das Verbot hätte eine
  > korrekte, neutrale Formulierung unmöglich gemacht. Die PO-Regel lautet wörtlich:
  > *„Platzgrenzen nennen ist erlaubt …, Wertungen nicht."* Getrennt wird also nach
  > **Wertung** und **Unwahrheit**, nicht nach Wortklang. Gefunden vom Developer in der
  > RED-Phase.

- **AC-6:** Given den Ortsvergleich / When der Nutzer Versand-Reiter, Alarme-Reiter und
  SMS-Vorschau öffnet / Then nennen auch dort die Kanal-Hinweise die echte Zeichengrenze und
  keine Wertung.
  - Test: Playwright-Klickpfad im Ortsvergleich über `VTBriefingChannels`,
    `AlertChannelPicker`, `CompareSmsPreview`.

### Block C — „Aus" ist ein Zustand

- **AC-7:** Given der SMS-Reiter mit einer aktiven Metrik X / When der Nutzer X abwählt /
  Then verschwindet X nicht, sondern erscheint in der Gruppe „Aus in diesem Kanal" und lässt
  sich von dort wieder einschalten — auch nach einem Neuladen der Seite.
  - Test: **Playwright-Klickpfad** — abwählen, neu laden, X in der Aus-Gruppe finden,
    einschalten, X ist wieder aktiv.

- **AC-8:** Given eine Metrik Y, die in der **Grundauswahl** abgewählt ist / When der Nutzer
  einen beliebigen Kanal-Reiter öffnet / Then erscheint Y **weder** in der aktiven **noch** in
  der Aus-Gruppe — ein Kanal kann sie nicht zurückholen (ADR-0050 Regel 1/2).
  - Test: Playwright-Klickpfad + Unit-Test auf die Listenbildung.

- **AC-9:** Given der SMS-Reiter wurde geöffnet (Kanal-Ebene existiert) und Metrik Z ist dort
  aktiv / When der Nutzer Z in der **Grundauswahl** abwählt / Then zeigt der SMS-Reiter Z
  sofort nicht mehr als aktiv (ADR-0050 Regel 3).
  - Test: Playwright-Klickpfad ohne Neuladen.

- **AC-10:** Given denselben Ablauf wie AC-9, aber der Nutzer steht beim Abwählen im
  **E-Mail**-Reiter / When er speichert und die Seite neu lädt / Then ist Z auch im
  **SMS**-Reiter abgewählt, und die zugestellte Kurzform enthält Z nicht.
  - Test: **Playwright-Klickpfad gegen Staging** + Abruf der echt gerenderten Kurzform über
    `/api/preview/{trip}/sms`. Dies ist der Nachweis für den Persistenz-Fix.

- **AC-11:** Given Metrik W ist im SMS-Reiter bewusst abgewählt und global aktiv / When der
  Nutzer W in der Grundauswahl aus- und wieder einschaltet / Then bleibt W im SMS-Reiter
  abgewählt — die Anwahl schreibt nicht durch.
  - Test: Playwright-Klickpfad.

- **AC-12:** Given der Telegram-Reiter mit abgewählten Metriken in der Aus-Gruppe / When die
  Kapplinie gezeichnet wird / Then zählt sie **nur aktive** Zeilen, nicht die Aus-Gruppe.
  - Test: Unit-Test auf die Zählung + Ablesen im Klickpfad.

### Block D — Der Ortsvergleich bleibt unberührt

- **AC-13:** Given die drei Vergleichs-Einbettungen der Reihenfolge-Liste (Übersicht,
  Ausblick, Stundenverlauf) / When dort „Aus" geklickt wird / Then verhält sich die Liste
  **exakt wie vor dieser Scheibe** — die Zeile verschwindet, es entsteht keine Aus-Gruppe.
  - Test: `compare-outlook-metric-selection.staging.spec.ts:421-429` und `:608` bleiben
    **unverändert** grün. Das ist der Lackmustest der Abgrenzung.

## Mutations-Gegenproben (PFLICHT)

| # | Verfälschung | MUSS rot werden |
|---|---|---|
| M1 | in `buildWeatherPayload` wieder nur `activeChannel` serialisieren | **AC-10** (und nur AC-10) |
| M2 | Durchschreibung bei Abwahl entfernen | AC-9 **und** AC-10 |
| M3 | Durchschreibung auch bei **Anwahl** ausführen | AC-11 |
| M4 | Aus-Gruppe aus der Grundauswahl statt aus dem globalen Maximum speisen | AC-8 |
| M5 | `offColumns` an einer Vergleichs-Einbettung durchreichen | **AC-13** |
| M6 | Telegram-Limit zurück auf 8 | AC-3 |
| M7 | Kapplinie zählt Aus-Zeilen mit | AC-12 |

Wird eine Verfälschung von **keinem** Test gefangen, ist das ein Befund — kein Grund, den
Test nachträglich passend zu machen.

## Known Limitations

- **Eine wieder eingeschaltete Metrik landet am Ende der Reihenfolge**, nicht an ihrer
  früheren Position. `buckets.off` ist ungeordnet und `buildWeatherConfigMetrics` schreibt
  `order: 0` für inaktive Einträge — die alte Position existiert im Datenmodell nicht mehr.
  Sie wieder herzustellen wäre eine Datenmodell-Änderung und gehört nicht in diese Scheibe.
- **Für SMS gibt es keine Überlauf-Warnung**, nur die genannte Zeichengrenze (Abschnitt 5).
  Mit der Live-Vorschau entfällt auch die einzige Stelle, die die Zeichenzahl je kannte.
  Bewusst: eine geschätzte Zahl wäre die nächste Behauptung, die still veraltet.
- **Premium-SMS bekommt keinen eigenen Reiter.** `ChannelId` kennt drei Kanäle; Premium-SMS
  teilt sich `report.sms_text` und erbt die SMS-Ebene transitiv (S2-Entscheid D7, ADR-0049).
  Benannte Grenze, keine Auslassung.
- **Toter Code wird nicht mitgelöscht.** `LTComparePreview.svelte`, `WeatherV2Kanaele.svelte`,
  `AboutOutputLayout.svelte`, `OutputLayoutEditor.svelte` (+`BucketSection`,
  `ChannelLimitMarkers`) tragen ebenfalls die falschen Zahlen, sind aber nirgends eingebunden.
  Eigener Aufräum-PR, sonst verwischt der Nachweis dieser Scheibe.
- **`/api/_validator/sms-fidelity-preview` und `render_sms_fidelity_preview` werden mit der
  Vorschau toter Backend-Code.** Nicht Teil dieser Scheibe.
- **Der Ortsvergleich hat weiterhin keine Kanal-eigene Metrik-Auswahl** — bewusst gesperrt
  (`weatherMetricsTabSharing.test.ts` AC-8, #1351). Fällt diese Sperre, muss die Naht aus
  Abschnitt 1 neu bewertet werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0050 (bestehend, wird eingelöst — **kein neues ADR**)
- **Rationale:** Regel 4 („Aus ist ein Zustand") wurde in S1 ausdrücklich als
  Frontend-Aufgabe für S3 vermerkt. Diese Scheibe ändert keine Entscheidungsfläche, sie setzt
  eine getroffene Entscheidung um. Die Modellierung der Platzgrenzen (Abschnitt 5) ist eine
  Umsetzungsfrage innerhalb von ADR-0049, keine neue Kanal-Entscheidung.

## Testauflage (PO, wörtlich „Das ist KRITISCH!!!!!")

Die ACs 1, 2, 3, 4, 6, 7, 8, 9, 10, 11 werden über **echte Browserläufe mit Klickpfad** unter
`frontend/e2e/` nachgewiesen. Das Deploy-Gate #1558 lädt sechs Seiten und prüft
Konsolenfehler — es klickt keinen AC durch und genügt **nicht**.

**Zuordnung der Klickpfad-Bündel** (je `*.staging.spec.ts` + `*.staging.setup.ts` +
`playwright.*.staging.config.ts`):

| Bündel | ACs |
|---|---|
| `wetter-metriken-vorschau-entfernt` | AC-1, AC-2 |
| `kanal-grenzen-und-hinweise` | AC-3, AC-4, AC-8 (Trip) |
| `kanal-grenzen-ortsvergleich` | AC-6 (`VTBriefingChannels`, `AlertChannelPicker`, `CompareSmsPreview`) |
| `kanal-abwahl-bleibt-reversibel` | AC-7, AC-9, AC-11 |
| `metrik-abwahl-schreibt-alle-kanaele-durch` | AC-10 |

> 🔴 **Nachgetragen nach RED-Befund (2026-08-11).** Die Erstfassung nannte die
> Playwright-Pflicht für AC-3, AC-4, AC-6 und AC-8 im Abschnitt „Testauflage", ohne dass die
> AC-Einträge selbst ein Bündel benannten — die Lücke wäre erst beim Adversary aufgefallen.
> Gefunden vom Developer in der RED-Phase.

**Bewusst umzudrehende Bestandstests** (sie kodieren das von ADR-0050 verworfene Verhalten):
`e2e/layout-tab-route.spec.ts:239-255` (AC-5) und `:418-464` (AC-2/AC-3) erwarten heute
`toHaveCount(0)` nach „Aus". Zwei weitere Tests derselben Datei (`:158-179`, `:258-281`) fallen
mit der Vorschau, zwei (`:181-217`, `:324-388`) brauchen Operation. Außerdem:
`ltChannels.test.ts` (vier Assertions auf `8`, je eine auf `ltBadge(0)`),
`metricsEditor.test.ts` (`sms === 0`) und
`molecules/issue_578_molecules_organisms.test.ts:310-313` (erzwingt `/140/` im Quelltext von
`CompareSmsPreview.svelte`).

## Changelog

- 2026-08-11: Initial spec created (Scheibe S3 von #1719)
