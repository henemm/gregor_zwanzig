# Context: #1719 Scheibe S3 — Frontend: „Aus" ist ein Zustand

- **Workflow:** `fix-1719-s3-aus-ist-ein-zustand`
- **Issue:** #1719 (Label `session:metrikauswahl`, `priority:high`)
- **Vorgänger:** S1 gemergt `e230977d` (ADR-0050 + Prüfstand), S2 live `0db5eec6`
  (Kanal-Ebene schneidet die Grundauswahl, Selftest Exit 0)
- **Erstellt:** 2026-08-11
- **Track:** Full Process, LoC-Limit 1800 (PO-Freigabe im Intake)

## 1. Request Summary

Der Editor soll die in **ADR-0050 Regel 4** bereits getroffene Zusage einlösen: „Aus" ist
ein **Zustand**, keine Löschung — die Zeile bleibt mit Zustandsanzeige stehen. Dazu kommen
drei vom PO im Issue-Kommentar 2026-08-11 nachgereichte Aufträge: `CHANNEL_COL_BUDGET.sms`
ehrlich modellieren, die bevormundenden Hinweistexte ersetzen, und die Live-Vorschau
„So kommt es an" ersatzlos entfernen.

**S3 repariert die Ursache. S2 hat nur die Wirkung abgefangen.** Der Backend-Schnitt aus S2
verhindert, dass ein Widerspruch zwischen den Ebenen *ausgeliefert* wird; der Editor
**erzeugt** ihn weiterhin bei jedem Speichern.

## 2. Der gemessene Defekt

### 2.1 Zwei Bedienelemente, zwei Ebenen, kein Abgleich

| Bedienelement | Datei:Zeile | schreibt nach |
|---|---|---|
| Grundauswahl an/aus (`onToggleMetric`) | `WeatherMetricsTab.svelte:662-673` | **global** (`buckets`) |
| „Aus"-Knopf (`onRemove`) | `WeatherMetricsTab.svelte:684-692` | **aktiver Kanal** |
| Roh/Einfach (`onMode`) | `WeatherMetricsTab.svelte:651-658` | **aktiver Kanal** |
| Sortieren (`onDndReorder`) | `WeatherMetricsTab.svelte:697-704` | **aktiver Kanal** |

`channelView()` (`:244-247`) ist **strikt binär**:

```ts
function channelView(ch: ChannelId): ChannelOverride {
	return channelBuckets[ch] ?? { buckets, friendlyMap };
}
```

Existiert ein Kanal-Override, wird die globale Ebene für diesen Kanal **nie mehr gelesen**.
Der Override entsteht per copy-on-write beim ersten Anfassen eines Kanal-Reiters
(`editActiveChannel` `:635-649` → `startChannelOverride`). Ab da ist die Grundauswahl für
diesen Kanal im Editor wirkungslos — genau das, was ADR-0050 Regel 3 verbietet.

**Reproduktion (aus `docs/context/fix-1719-s2-...md:226-241`, K1):** SMS-Reiter öffnen →
zurück zur Grundauswahl → dort abwählen → speichern. `buildWeatherPayload` (`:754-775`)
schickt beide Ebenen unabgeglichen in einem PATCH.

### 2.2 „Aus" ist eine Sackgasse

`onRemove` ruft `move(view.buckets, id, 'primary', 'off')`. `WeatherV2Reihenfolge` bekommt
nur `primaryColumns` — die Komponente kennt die `off`-Liste **gar nicht** und hat kein
Bedienelement zum Zurückholen. Der einzige Rückweg wäre die Grundauswahl, die auf
Kanal-Overrides nicht wirkt (2.1). **Für einen Kanal mit eigener Auswahl gibt es heute
keinen UI-Weg, eine dort abgewählte Metrik zurückzuholen.**

### 2.3 Was NICHT kaputt ist — das Wire-Format

`buildWeatherConfigMetrics` (`metricsEditor.ts:332-373`) emittiert **jede** Katalog-ID mit
`enabled: bucket !== undefined`. Abgewählt heißt also **`enabled:false`**, nie „Eintrag
fehlt" — in `metrics` **und** in jedem `channel_layouts`-Kanal identisch, belegt an
`tests/fixtures/metric_cascade/khw_display_config_widerspruch.json`.

**Folge für den Umfang:** Die Persistenz kann „Aus als Zustand" bereits. Der Defekt sitzt
ausschließlich im **Ansichtsmodell** des Editors. Das verkleinert S3 gegenüber der
Erstschätzung deutlich — es ist keine Datenmodell-Änderung nötig.

Backend-Gegenstelle: `internal/handler/weather_config.go:95-99` →
`mergeConfigMap` (`config_merge.go`). Merge **nur auf oberster Schlüsselebene**; ein
gesendetes `channel_layouts` **ersetzt die gesamte Map**. Deshalb schickt
`mergeChannelLayoutsForSave` immer den vollständigen Stand aller editierten Kanäle mit
(Datenverlust-Schutz, BUG-DATALOSS-GR221-Muster). **Das muss so bleiben.**

## 3. 🔴 Eine Prämisse des Issues ist am Code widerlegt

Der Issue-Kommentar verlangt: *„`CHANNEL_COL_BUDGET.sms` von `0` auf den echten Wert
bringen"*, und markiert das ausdrücklich als **„nachzumessen, nicht behauptet"**.
Nachgemessen:

| Aussage | Befund |
|---|---|
| „SMS hat kein Spalten-Raster" | **wahr und unverändert.** `channel_layout.py:48` — `CHANNEL_LIMITS["sms"]["max_table_cols"] = 0`. SMS ist eine Fließzeile, keine Tabelle |
| „SMS kennt keine Reihenfolge" | **falsch seit #1677.** `trip_report.py:321-332` → `builder.py:472-491` → `dto.py:112-115`; Test `tests/tdd/test_sms_user_metric_order.py:160-169` |

**Die Zahl `0` ist als Spaltenzahl korrekt.** Falsch ist die **Prosa**, die aus einer
Spaltenzahl eine Ordnungsaussage macht — zwei verschiedene Dimensionen, die dieselbe Zahl
gar nicht ausdrücken kann. Ein numerischer „echter Wert" für ein Spaltenbudget existiert
für SMS nicht.

Der PO hat die richtige Richtung selbst benannt: *„Zeichen-, nicht Spaltenbudget — die
Einheit unterscheidet sich von Email/Telegram, das gehört sauber modelliert statt per
Sentinel."* Genau das ist die Aufgabe: **die Einheit modellieren**, nicht eine Zahl tauschen.

### 3.1 Die echten Grenzen, je Kanal gemessen

| Kanal | Echte Grenze | Beleg |
|---|---|---|
| E-Mail | keine | `channel_layout.py:46` (`None`), kein Cap in `email/html.py` — `Infinity` ist korrekt |
| Telegram | **7 Metrik-Spalten** | `channel_layout.py:110` `metric_slots = limit - 1`; `narrow.py:148` stellt „Zt" voran |
| SMS | **160 Zeichen** (Trip-Pfad) | `trip_report.py:446` `max_length=160`, Literal |
| Premium-SMS | erbt SMS transitiv | `premium_sms.py:19-21`, `notification_service.py:410-429` — bitidentisch `report.sms_text` |

### 3.2 Zwei zusätzliche Zahlen-Defekte, die dabei sichtbar werden

1. **Telegram ist um eins zu großzügig.** `metricsEditor.ts:224-232` kommentiert
   *„Uhrzeit NICHT mitgezaehlt, Telegram-Budget = 8"*, das Backend liefert aber nur **7**
   Metrik-Spalten (die 8. wird demoted). Deckt sich mit dem S2-Befund
   („Telegrams Tabelle hat nur 7 Metrik-Slots"). Der Editor verspricht dem Nutzer also
   eine Spalte mehr, als ankommt.
2. **Die „140 Zeichen" stehen an neun Stellen und sind nirgends belegt.**
   `ltChannels.ts:40`, `VTBriefingChannels.svelte:120`, `WeatherV2Kanaele.svelte:29`,
   `AboutOutputLayout.svelte:18`, `OutputLayoutEditor.svelte:111,123`,
   `AlertChannelPicker.svelte:51`, `LTComparePreview.svelte:153`,
   `CompareSmsPreview.svelte:5`. Der Trip-Pfad kürzt bei **160**, der Vergleichs-Pfad bei
   **153** (`channel_layout.py:45-54`, GSM-7/UDH-Rechnung `floor((140-6)*8/7)`).

### 3.3 Der Sentinel hat mehr Leser als im Issue genannt

| Leser | Datei:Zeile | Wirkung von `sms: 0` |
|---|---|---|
| `ltBadge` | `ltChannels.ts:50` | SMS-Chip zeigt `—` statt einer Grenze |
| `ltOverflow` | `ltChannels.ts:63` | SMS wird bei Überlauf **übersprungen** |
| `LTCapNote` | `LTCapNote.svelte:28,31` | eigener Textzweig für `max === 0` |
| `channelOverflow` | `metricsEditor.ts:310-318` | **toter Code** — einziger Leser `ChannelLimitMarkers.svelte` ist über `BucketSection`/`OutputLayoutEditor` nirgends mehr gemountet |

## 4. Die geteilte Zeilen-Komponente: vier Einbettungen, ein Grund

`WeatherV2Reihenfolge.svelte` (266 Z.) wird **viermal** eingebettet — nicht dreimal:

| # | Datei:Zeile | Kontext | „Aus" heute | Weg zurück? |
|---|---|---|---|---|
| A | `WeatherMetricsTab.svelte:1131` | Vergleich, Übersicht | Toggle auf flachem Array | **ja**, Checkbox darüber |
| **B** | **`WeatherMetricsTab.svelte:1280`** | **Trip, Kanal-Reiter** | **`primary → off` im Kanal-Override** | **NEIN** |
| C | `CompareOutlookLayoutControls.svelte:154` | Vergleich, Ausblick | Toggle auf flachem Array | **ja**, Checkbox darüber |
| D | `CompareHourlyLayoutControls.svelte:221` | Vergleich, Stundenverlauf | Toggle auf flachem Array | **ja**, Checkbox darüber |

**Der ADR-0050-Grund greift ausschließlich an B.** A/C/D haben ein anderes Datenmodell (ein
flaches Array je Block, keine Kanal-Ebene) und bereits heute einen funktionierenden
Rückweg. Eine ungegatete Änderung würde dort Verhalten ändern, das ADR-0050 gar nicht
anspricht — und Tests brechen, die nichts Falsches bewachen.

**Die Naht muss die Prop-Anwesenheit sein, nicht ein `context`-String.** Präzedenz für
`context="route"|"vergleich"` existiert (`LayoutTab.svelte:19-20`, `AlarmeTab.svelte:61`,
`VersandTab.svelte:29`) und ist in CLAUDE.md kodifiziert — aber die richtige Trennlinie
verläuft hier **nicht** entlang Trip/Vergleich: A ist Vergleich, B ist Trip, C/D sind
Vergleich, und der Unterschied ist das Datenmodell, nicht der Kontext. In #1717 wurde
genau dieser Fehler gemacht und in der RED-Phase gefangen („AC-1 Prüfort war die falsche
Naht — die Komponente gated über Prop-Anwesenheit, nicht über den `context`-String").

`WeatherV2Reihenfolge` hat heute **kein** `context`/`variant`/`mode`-Prop; die einzige
Verzweigung ist `activeChannel === 'telegram'` für die Cut-Line (`:36`, `:60`).

## 5. Was die Live-Vorschau mitreißt

`WeatherV2MailPreview.svelte` (597 Z.) ist ausschließlich in `WeatherMetricsTab.svelte`
gemountet (`:1293` Desktop, `:1574` Mobile-Sheet).

**Löschbar mit ihr:**

| Datei | Zeilen | Grund |
|---|---|---|
| `WeatherV2MailPreview.svelte` | 597 | der PO-Entscheid selbst |
| `trip-detail/smsFidelityPreview.ts` | 45 | einziger Verwender ist die Vorschau |
| `__tests__/weather_v2_mail_preview_sms_fidelity.test.ts` | 225 | testet die gelöschte Komponente |
| `__tests__/weather_metrics_tab_vergleich_no_sms_preview.test.ts` | 82 | prüft Abwesenheit der Vorschau im Vergleich |
| `trip-detail/__tests__/sms_fidelity_preview_fetch.test.ts` | 84 | testet die gelöschte Datei |
| `e2e/fix-923b-wire-live-sms-preview.staging.spec.ts` | 213 | prüft ausschließlich die Live-Vorschau |

**Nicht mitlöschen:** `highlight`/`diffHighlight`/`applyDiff` (`WeatherMetricsTab.svelte:250-281`)
— geteilt mit `WeatherV2Reihenfolge` und `WeatherV2Grundauswahl`.

**Folgearbeit, nicht S3:** `/api/_validator/sms-fidelity-preview` und
`render_sms_fidelity_preview` (`validator_render_service.py:275-294`) werden damit toter
Backend-Code. (Nebenbei belegt, warum die Vorschau weg muss: sie berücksichtigt `position`
gar nicht — `build_sms_fidelity_specs` `:257-272` baut aus einem `set(metric_ids)`. Sie zeigte
also seit #1677 nachweislich eine andere Reihenfolge als der Versand.)

## 6. Betroffene Tests — vollständig

### Müssen bewusst **umgedreht** werden (sie kodieren das verworfene Verhalten)

| Test | Assertion heute |
|---|---|
| `e2e/layout-tab-route.spec.ts:239-255` (AC-5) | nach „Aus": `toHaveCount(0)` für die Zeile |
| `e2e/layout-tab-route.spec.ts:418-464` (AC-2/AC-3) | nach „Aus" im SMS-Reiter: Zeilenzahl 3 → 2, nach Reload wieder 2 |

### Fallen mit der Vorschau

| Test | Grund |
|---|---|
| `e2e/layout-tab-route.spec.ts:158-179` (AC-1/AC-2) | prüft nur das Umschalten der Vorschau |
| `e2e/layout-tab-route.spec.ts:258-281` (AC-7) | Mobile-FAB öffnet Vorschau-Sheet |
| `e2e/layout-tab-route.spec.ts:181-217` (AC-3) | Teilprüfung `:198` liest Vorschau-Spalten → Operation |
| `e2e/layout-tab-route.spec.ts:324-388` (AC-4) | `:355-358` vergleicht Badge gegen Vorschau-Zahl → Operation |

### Bleiben grün, wenn die Naht stimmt

`compare_outlook_metric_selection_structure.test.ts:388-419` und
`compare_hourly_layout_controls_structure.test.ts:496-505` sind reine Verdrahtungs-Wächter
(AST, keine Laufzeit) — sie brechen nur bei geänderter **Aufrufer**-Signatur.

### Brechen, wenn die Naht NICHT stimmt

`e2e/compare-outlook-metric-selection.staging.spec.ts:421-429` (`toEqual([...])` auf
verbleibende Zeilen) und `:608` (`toHaveCount(0)` nach Abwahl aller). Beide im
Ortsvergleich, wo der ADR-Grund nicht greift. **Diese beiden sind der Lackmustest der
Abgrenzung.**

### Weiter betroffen

`ltChannels.test.ts:40-67` (assertiert `ltBadge(0) === '—'` und dass `ltOverflow` SMS
überspringt), `metricsEditor.test.ts` (assertiert `sms === 0`),
`issue_610_signal_removal_red.test.ts`, `issue_587_weather_tab_v2_red.test.ts`.

## 7. Abhängigkeiten

- **Upstream:** ADR-0050 (die Zusage), ADR-0049 (Kanalliste), S2-Backend-Schnitt
  `models.py::_clip_to_global_maximum()`
- **Downstream:** `LayoutTab`/`LTCapNote`/`LTChannelPicker` (geteilt Trip+Vergleich),
  `WeatherV2Reihenfolge` (vier Einbettungen), `VTBriefingChannels` (Versand-Reiter)
- **Nicht betroffen:** Backend-Renderpfade — S3 ist reines Frontend. `loader.py:836-875`
  parst `channel_layouts` roh und braucht keine Änderung.

## 8. Bestehende Specs

- `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` — Regel 4 ist die Zusage
- `docs/specs/modules/fix_1719_s1_kaskade_pruefstand.md` — S3-Umfang in `:395-402`
- `docs/specs/modules/fix_1719_s2_kaskade_verfeinerung.md` — S3-Umfang in `:476-477`
- `docs/specs/modules/layout_tab_route.md`, `layout_tab_vergleich.md` — der Organism
- `docs/reference/sms_format.md:596` — Changelog 2.24 benennt den falschen Editor-Satz
  bereits als überholt und verweist auf #1719 S3

## 9. Risiken & offene Punkte für die Spec

1. **Abgrenzung der geteilten Komponente** (Abschnitt 4) — Prop-Anwesenheit, nicht
   Kontext-String. Der Beweis, dass es sitzt: die beiden Compare-E2E-Tests aus 6.4 bleiben
   **unverändert** grün.
2. **Welche Metriken erscheinen in der Kanal-Liste?** PO-Wortlaut: „Die Kanal-Liste zeigt
   alle Metriken der **Grundauswahl**". Damit ist die „Aus"-Liste eines Kanals die
   Differenz *global aktiv* minus *im Kanal aktiv* — global abgewählte Metriken erscheinen
   nie, und ADR-0050 Regel 1/2 sind allein durch die Anzeige erfüllt.
3. **Richtung der Durchschreibung.** Regel 3 verlangt: globale Abwahl wirkt **sofort in
   allen Kanälen** — `onToggleMetric` muss die AUS-Richtung in alle vorhandenen
   Kanal-Overrides schreiben. Die EIN-Richtung ist offen; Empfehlung: **nicht**
   durchschreiben, weil die Zeile im Kanal-Reiter ab S3 sichtbar den Zustand „Aus" zeigt
   und der Nutzer dort selbst entscheidet (Grundsatz „keine Bevormundung").
4. **Wo sitzt eine „Aus"-Zeile in der Reihenfolge-Liste?** In-place gedimmt vs. am Ende
   gesammelt. PO sagt „die Zeile bleibt stehen".
5. **Die SMS-Zeichengrenze unterscheidet sich je Kontext** (160 Trip / 153 Vergleich), die
   Konstante ist aber geteilt. Braucht eine Entscheidung, keine dritte Zahl.
6. **Telegram 8 → 7** (Abschnitt 3.2) geht über den Issue-Text hinaus, ist aber derselbe
   Defekttyp in derselben Konstante. Muss als eigenes AC sichtbar sein oder ausdrücklich
   ausgeschlossen werden.
7. **Premium-SMS fehlt im Editor** (`ChannelId` kennt drei Kanäle). Laut S2-Entscheid D7
   bewusst — erbt SMS transitiv. **Benannte Grenze, keine stille Auslassung.**
8. **Kontrast-Nebenbefund:** `LTCapNote.svelte:47` färbt Hilfetext mit `--g-ink-4`; die
   Design-Leitprinzipien erlauben den Token nur für Placeholder/Disabled. Datei wird
   ohnehin angefasst.

## 10. Analyse — Korrekturen aus der strategischen Gegenprobe

Eine unabhängige Gegenprobe hat vier Designentscheidungen angegriffen. Drei halten,
**eine war unvollständig und hätte den Fehler neu eingebaut, den S3 beheben soll.**

### 10.1 🔴 Der Fund, der die Scheibe rettet: die Durchschreibung wäre nicht angekommen

Abschnitt 2.3 sagt „keine Datenmodell-Änderung nötig" — das ist für das **bestehende**
Verhalten korrekt gemessen und wurde von mir unausgesprochen auf die **neue**
Durchschreibung übertragen. Dort gilt es nicht:

```
buildWeatherPayload (WeatherMetricsTab.svelte:754-767):
  mergeChannelLayoutsForSave(
    trip!.display_config?.channel_layouts,  // ← nur der zuletzt PERSISTIERTE Stand
    activeChannel, ...)                     // ← schreibt NUR den aktiven Kanal
```

`mergeChannelLayoutsForSave` (`channelMetricLayouts.ts:25-34`) setzt ausschließlich
`next[activeChannel]`; alle anderen Kanäle kommen aus dem **Server**-Stand, nicht aus
`channelBuckets`. Szenario: Nutzer steht im E-Mail-Reiter, SMS hat bereits einen Override,
Nutzer wählt global ab → die Durchschreibung ändert `channelBuckets.sms` **nur im
Arbeitsspeicher**, gespeichert wird nur `channel_layouts.email`. Nach einem Neuladen steht
der Widerspruch wieder da — genau das, was ADR-0050 Regel 3 („wirkt **sofort** in allen
Kanälen") verbietet, nur subtiler als vorher.

**Kein bestehender Test deckt das ab.** `layout-tab-route.spec.ts:418-464` editiert direkt
im Zielkanal (kein globaler Umschalter, kein zweiter unberührter Kanal);
`channelMetricLayouts.test.ts` prüft `mergeChannelLayoutsForSave` nur mit vorgegebenen
Argumenten.

⇒ **Pflichtbestandteil von S3:** `buildWeatherPayload` muss **alle** nicht-`null`-Einträge
aus `channelBuckets` serialisieren, nicht nur den aktiven. Mit eigenem AC und
Mutations-Gegenprobe.

### 10.2 🔴 Eine Anweisung des Issues ist überholt: `LTCapNote` erreicht den Ortsvergleich nicht mehr

Der PO-Kommentar verlangt: *„`LTCapNote` ist geteilt ⇒ Wirkung im **Ortsvergleich**
mitprüfen."* Gemessen: `LayoutTab` hat genau **eine** Einbettung —
`WeatherMetricsTab.svelte:1272`, `context="route"`. Der **Layout-Reiter des Ortsvergleichs
wurde mit #1360 aufgelöst** (`compare-layout-tab-dissolution.spec.ts`). `LTCapNote` und
`LTChannelPicker` sind weiterhin geteilter Code, aber ihr einziger Einhängepunkt ist heute
der Trip. Der `context === 'vergleich'`-Zweig in `LayoutTab.svelte:51` ist toter Ast.

Die Absicht des PO bleibt richtig, nur die benannte Komponente stimmt nicht mehr. **Der
Ortsvergleich ist sehr wohl betroffen** — über andere Bausteine (10.3).

### 10.3 Die „140 Zeichen" stehen an vier lebenden Stellen, nicht an neun

| Datei | Lebendig? | Sichtbar in |
|---|---|---|
| `ltChannels.ts:40` | ja, via `LayoutTab` | **nur Trip** |
| `VTBriefingChannels.svelte:120` | ja, `VersandTab.svelte:238,274` | **Trip + Vergleich** |
| `AlertChannelPicker.svelte:51` | ja, `AlarmeTab.svelte:355` | **Trip + Vergleich** |
| `CompareSmsPreview.svelte:5` | ja, `CompareTabs.svelte:1579` | **nur Vergleich** |
| `LTComparePreview.svelte:153` | **tot** — kein Importeur | — |
| `WeatherV2Kanaele.svelte:29` | **tot** — seit #736 | — |
| `AboutOutputLayout.svelte:18` | **tot** — kein Importeur | — |
| `OutputLayoutEditor.svelte:111,123` | **tot** — kein Importeur (zieht `BucketSection`, `ChannelLimitMarkers` mit) | — |

Tote Stellen werden **nicht** korrigiert. Ob sie in dieser Scheibe gelöscht werden, ist
eine Umfangsfrage — Empfehlung: nein, eigener Aufräum-PR, sonst verwischt der Nachweis.

### 10.4 Ein Test fehlte in meiner „vollständigen" Liste

`frontend/src/lib/components/molecules/issue_578_molecules_organisms.test.ts:310-313`
(AC-12) erzwingt `/140/` als Pflicht-Zeichenkette im Quelltext von `CompareSmsPreview.svelte`
— einer **live gemounteten** Komponente. Bricht garantiert mit der Zahlenkorrektur und
blockiert sonst den Commit über `touched_tests_gate.py`. Mein Abschnitt 6 behauptete
Vollständigkeit und hielt sie nicht.

### 10.5 Die Vorschau-Löschung ist ein Umbau, keine Löschung

`LayoutTab.svelte:28` deklariert `preview: Snippet<...>` als **Pflicht**-Prop; die Hülle ist
ein Zwei-Spalten-Raster mit eigener Überschrift „So kommt es an · {Kanal}"
(`:44-56`). Mit der Vorschau fällt die rechte Spalte — `LayoutTab` muss umgebaut werden,
nicht nur entkoppelt. Dazu die Mobile-Infrastruktur in `WeatherMetricsTab.svelte`
(`mailSheetOpen` `:221`, FAB `:1568`, `Sheet` `:1572-1574`).

### 10.6 Svelte-5-Präzisierung zur Naht

`offColumns: string[] = []` macht „nicht übergeben" und „explizit `[]`" **ununterscheidbar**.
Die Naht heißt deshalb konkret: **`offColumns?: string[]` ohne Vorgabewert**, Verzweigung
auf `offColumns !== undefined`. Sonst argumentiert die Spec mit Anwesenheit und der Code
prüft Inhalt.

### 10.7 Telegram 8 → 7 ist durch eine dritte, unabhängige Quelle bestätigt

`WeatherMetricsTab.svelte:1120-1121` (Vergleichs-Zweig) kommentiert bereits selbst:
*„echte Compare-Budgets: 7 Metrik-Zellen je Ort im Telegram … nicht 8/0 aus
CHANNEL_COL_BUDGET."* Der Vergleichspfad weiß seit jeher, dass 7 richtig ist, und umgeht
die Konstante deshalb. Damit stimmen Backend-Konstante, Backend-Herleitung und
Vergleichs-Code auf **7** überein; nur `metricsEditor.ts:230` weicht ab.

### 10.8 Geänderte Umsetzungsreihenfolge

Die Gegenprobe widerspricht meiner Reihenfolge mit Beleg: „Hinweistexte" und „Zahlen"
stecken in **denselben String-Literalen** (`ltChannels.ts:40`, `VTBriefingChannels.svelte:112-120`,
`AlertChannelPicker.svelte:51`). Texte zuerst umzuschreiben hieße, die falsche Zahl
überzeugender zu formulieren und dieselbe Zeile zweimal anzufassen.

**Neue Reihenfolge:** Vorschau entfernen → **Budget-Modell und Hinweistexte gemeinsam**
(inkl. Telegram 7) → „Aus ist ein Zustand" inkl. Durchschreibung und Persistenz-Fix.

### 10.9 Risiko

| Teilaufgabe | Risiko | Grund |
|---|---|---|
| Naht (Prop-Anwesenheit) | LOW | ein Aufrufer, AST-Wächter decken die Nachbarn |
| **Durchschreibung + Persistenz** | **HIGH** | 10.1 — ohne den Zusatzfix neue ADR-0050-Verletzung |
| Budget-Modell + Texte | MEDIUM | vier lebende Oberflächen, ein ungelisteter Regex-Test, Zahl je Kontext verschieden |
| Telegram 8 → 7 | MEDIUM | mechanisch, aber sechs Dateien inkl. vier `ltChannels.test.ts`-Assertions |
| Vorschau entfernen | MEDIUM | Pflicht-Snippet-Vertrag erzwingt Umbau der Hülle (10.5) |

## 11. Testauflage (PO, wörtlich „Das ist KRITISCH!!!!!")

Jede Scheibe mit Frontend-Anteil braucht einen **echten Browserlauf mit Klickpfad** unter
`frontend/e2e/`. Das Deploy-Gate #1558 lädt sechs Seiten und prüft Konsolenfehler — es
klickt keinen AC durch und genügt als Nachweis **nicht**. Vorbild und direkter Vorläufer:
`frontend/e2e/metrik-grundauswahl-schneidet-kanal.staging.spec.ts` (S2), dessen Dateikopf
ausdrücklich vermerkt, dass er gegen den **unveränderten** Editor läuft und Regel 4 **nicht**
beweist.
