---
entity_id: feat_1435_e1b_alarm_erklaersatz
type: feature
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [metric-catalog, alerts, compare, trip-compare-sharing, transparency]
workflow: feat-1435-e1b-alarm-erklaersatz
---

# Feature #1435 Etappe E1b — Erklärsatz statt Leerstelle, richtiger Reiter im Leerzustand

## Approval

- [ ] Approved

## Purpose

E1a-1 (`98d1a1f6`) und E1a-2 (`53f88757`, beide live) haben die
Alarm-Zeilen-Tabelle im Alarme-Reiter an das zentrale
Wetter-Namensregister angeschlossen. Diese Etappe schließt zwei kleine,
aber nutzersichtbare Lücken, die dabei bewusst zurückgestellt wurden:
Wettergrößen, die ein Nutzer im Ortsvergleich ausgewählt hat, aber die
keinen Alarm auslösen können, verschwinden bislang **kommentarlos** aus
der Alarm-Tabelle — das widerspricht der Grundregel von #1435, dass keine
Größe still verworfen werden darf. Das gilt auch (und besonders) für den
Sonderfall, dass ein Nutzer ausschließlich nicht-alarmfähige Größen
gewählt hat: dann darf die Oberfläche nicht so tun, als hätte er gar
nichts ausgewählt. Zusätzlich verweist der Leerzustand („keine Metriken
gewählt") auf den falschen Reiter. Alles reine Anzeige-Korrekturen im
bereits geteilten `AlarmeTab.svelte`, keine neue Auswertung.

## Source

> **Schicht-Hinweis:** reine Frontend-Änderung (SvelteKit), keine Go-,
> keine Python-Beteiligung. Das Register und seine Auslieferung
> (`GET /api/compare/metrics`) sind bereits produktiv (E1a-1/E1a-2) und
> werden ausschließlich lesend konsumiert.

- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte`
- **Identifier:** Leerzustand-Text (Zeile 253), neuer `$derived`
  `unalertableSelectedMetricNames` (neben `effectiveActiveMetrics`, Zeilen
  ~116-123), neue Drei-Zweig-Verzweigung im `metric-levels`-Abschnitt
  (Zeilen ~250-261, ersetzt die bisherige Zwei-Zweig-Verzweigung)
- **File:** `frontend/src/lib/components/shared/alarme-tab/activeAlertMetricsFromCatalog.ts`
- **Identifier:** neue Funktion `deriveUnalertableSelectedMetricNames()`,
  Gegenstück zu `deriveActiveAlertMetricsFromCatalog()`

## Estimated Scope

- **LoC:** ~45-58 Produktivcode (1 Textkorrektur, 1 neue reine Funktion
  mit `label`-Häufigkeitszählung über den vollen Katalog + Dokumentations-
  kommentar in `activeAlertMetricsFromCatalog.ts`, 1 neuer `$derived` +
  Drei-Zweig-Markup + 1 neue CSS-Regel in `AlarmeTab.svelte`) + ~200-260
  Testcode (2 neue Testdateien, node:test, AST-/Fixture-basiert; die
  Pure-Function-Testdatei wächst um die Häufigkeits-Regel [AC-2] und die
  Bezugsgrößen-Absicherung [AC-10], die Strukturtestdatei um Zustand 2
  [AC-9]) → **~245-320 Netto-Zeilen gesamt.**
  **Überschreitet das 250-Zeilen-Budget.** Der PO hat diese Überschreitung
  am 2026-07-31 im Zuge der Häufigkeits-Regel-Nachbesserung ausdrücklich
  freigegeben — bei Implementierung ist **kein erneuter Override-Antrag
  nötig**, sofern der Umfang sich im Rahmen dieser Schätzung bewegt. Der
  Überhang ist wie in E1a-2 überwiegend Testcode.
- **Files:** 2 Produktivdateien geändert (`AlarmeTab.svelte`,
  `activeAlertMetricsFromCatalog.ts`), 2 Testdateien neu. **Keine**
  Änderung an `CompareTabs.svelte`, `CompareNewEditor.svelte` oder
  `AlarmeScheduleTab.svelte` — der Katalog fließt an allen drei
  Vergleichs-Einbettungen bereits seit E1a-2 als Prop, der Tour-Container
  bleibt unberührt (s. Known Limitations).
- **Effort:** low.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/shared/alarme-tab/activeAlertMetricsFromCatalog.ts::deriveActiveAlertMetricsFromCatalog` | READ (E1a-2, unverändert) | Referenzmuster für die neue Funktion — dieselben zwei Argumente, dieselbe Quelle |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts::CompareSelectionEntry` | READ | Trägt `label`, `aggregation_label`, `alertMetric` je Katalog-Eintrag — einzige Namensquelle |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts::materializeActiveMetricKeys` | READ (unverändert) | Löst `null` („nie geöffnet") zu Vorgabemenge auf — dieselbe Materialisierung wie `effectiveActiveMetrics`, keine zweite |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (`.option-hint`, Zeilen 927/992/1537-1542) | REFERENZ | Vorbild-Muster für erklärende Hinweise unterhalb einer Auswahl-/Wertefläche |
| `frontend/src/lib/components/compare/CompareTabs.svelte:1422`, `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:412,499` | UNVERÄNDERT | Reichen `catalog` bereits seit E1a-2 durch — diese Etappe braucht dort keine Änderung |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | UNVERÄNDERT | Tour-Container; liefert weder Metrik-Auswahl noch Katalog — Erklärsatz bleibt dort aus (Known Limitations) |
| `docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md` | REFERENZ | Direkter Vorgänger, Beleg-/Teststil-Vorbild |

## Implementation Details

### 1. Leerzustand-Hinweis nennt den richtigen Reiter (beide Kontexte)

`AlarmeTab.svelte:253` ändert sich von „Wähle im Tab „Wertebereiche"
Metriken aus…" zu „Wähle im Tab „Wetter-Metriken" Metriken aus, um
Alarm-Schwellen zu konfigurieren." Reine Textkorrektur, keine
Kontext-Weiche nötig — die Beschriftung des Reiters ist in Tour und
Vergleich identisch (belegt: `compareTabsResolve.ts:13-14`,
`TripTabs.svelte:80-81`).

### 2. Neue Ableitungsfunktion — Klammerzusatz nur bei mehrdeutigem `label`

**PO-Nachbesserung 2026-07-31 (RED-Phasen-Befund):** Die erste Fassung
dieser Spec hängte `aggregation_label` an, sobald es vorhanden war —
das ist bei **allen 26 Katalog-Einträgen** der Fall und hätte den Satz
überladen (z. B. „Sonnenstunden (Summe), Bewölkung (Maximum),
Luftfeuchtigkeit (Maximum)"), im Widerspruch zur schlanken Schreibweise
in „Expected Behavior". **Entschieden:** Der Klammerzusatz erscheint nur
bei Größen, deren `label` im Register **mehrfach vorkommt** — das sind
aktuell genau zwei Fälle: „Temperatur" (Minimum/Maximum) und „Gefühlte
Temperatur" (Minimum/Maximum). Alle übrigen 22 Einträge tragen ein
eindeutiges `label` und erscheinen ohne Klammerzusatz.

**Bezugsgröße ist der volle Katalog, nicht die Auswahl.** Die
Häufigkeitszählung läuft über **alle** Katalog-Einträge, nicht über die
gefilterten/ausgewählten. Begründung: Zählte man nur über die Auswahl
oder über die im Satz genannten Namen, änderte sich die Schreibweise
einer Größe dadurch, dass der Nutzer eine ganz andere Größe dazuwählt —
und sie wiche von der Schreibweise im Reiter *Wetter-Metriken* ab, wo
beide Temperatur-Varianten immer mit Auswertung stehen
(`WeatherMetricsTab.svelte:951`, `CompareOutlookLayoutControls.svelte:121-122`).
Stabilität und Gleichlauf mit der Auswahlfläche schlagen die minimal
kürzere Form (s. AC-10).

Reine Funktion neben `deriveActiveAlertMetricsFromCatalog()` in derselben
Datei, testbar ohne Komponenten-Rendering. Zählt zuerst die `label`-
Häufigkeit über den vollen Katalog, filtert danach auf ausgewählte,
nicht-alarmfähige Einträge (Katalog-Reihenfolge bleibt erhalten) und
hängt den Klammerzusatz nur bei mehrdeutigem `label` an:

```ts
export function deriveUnalertableSelectedMetricNames(
	activeMetricKeys: string[],
	catalog: CompareSelectionEntry[]
): string[] {
	const labelCounts = new Map<string, number>();
	for (const e of catalog ?? []) {
		labelCounts.set(e.label, (labelCounts.get(e.label) ?? 0) + 1);
	}
	const active = new Set(activeMetricKeys ?? []);
	return (catalog ?? [])
		.filter((e) => active.has(e.metric) && !e.alertMetric)
		.map((e) =>
			(labelCounts.get(e.label) ?? 0) > 1 && e.aggregation_label
				? `${e.label} (${e.aggregation_label})`
				: e.label
		);
}
```

`!e.alertMetric` erfasst sowohl `alertMetric: null` (Register sagt
explizit „nicht alarmfähig") als auch ein fehlendes Feld — beide Fälle
bedeuten „kein Alarm möglich". `labelCounts` wird aus dem **ungefilterten**
`catalog`-Parameter gebildet, bevor die Auswahl-Filterung greift — genau
das macht die Schreibweise unabhängig davon, was der Nutzer sonst noch
ausgewählt hat.

### 3. Neuer `$derived` in `AlarmeTab.svelte` (nur `context="vergleich"`)

Direkt neben `effectiveActiveMetrics` (Zeilen ~116-123), dieselbe
Materialisierung, damit die Leerauswahl-Kante (`activeMetricKeys = null`
heißt „nie geöffnet" = Vorgabemenge, `[]` heißt „bewusst leer") konsistent
zur Tabelle bleibt:

```ts
const unalertableSelectedMetricNames = $derived(
	context === 'vergleich'
		? deriveUnalertableSelectedMetricNames(
				materializeActiveMetricKeys(wiz?.activeMetricKeys ?? null),
				catalog ?? []
			)
		: []
);
```

Im Tour-Kontext liefert dieser `$derived` immer `[]` — deshalb bleibt der
Tour-Kontext strukturell bei der bisherigen **Zwei**-Zustands-Logik
(Leerzustand oder Tabelle): Zustand 2 aus Punkt 4 unten kann dort nie
eintreten, ohne dass eine eigene Kontext-Sperre nötig wäre.

### 4. Drei Zustände statt zwei — PO-Nachbesserung 2026-07-31

**Der ursprüngliche Entwurf dieser Spec ging von einer Zwei-Zustands-
Verzweigung aus** (Leerzustand ODER Tabelle+Erklärsatz) und unterschlug
damit genau den Fall, gegen den diese Etappe gebaut wird: Wählt ein
Nutzer im Ortsvergleich **ausschließlich nicht-alarmfähige** Größen (16
der 26 Katalog-Einträge sind es — z. B. nur Bewölkung, UV-Index,
Luftfeuchtigkeit), ist `effectiveActiveMetrics.length === 0`, obwohl der
Nutzer sehr wohl gewählt hat. Der Leerzustand-Text „Wähle Metriken
aus…" wäre dort sachlich falsch — die still verschwundene Größe in
Reinform.

Der `metric-levels`-Abschnitt (Zeilen ~250-261) bekommt daher **drei**
Zweige statt zwei:

```svelte
{#if effectiveActiveMetrics.length === 0 && unalertableSelectedMetricNames.length === 0}
	<p class="alarme-no-metrics-hint" data-testid="alarme-no-metrics">
		Wähle im Tab „Wetter-Metriken" Metriken aus, um Alarm-Schwellen zu konfigurieren.
	</p>
{:else if effectiveActiveMetrics.length === 0}
	<p class="alarme-no-metrics-hint" data-testid="alarme-only-unalertable-hint">
		Keine der gewählten Größen kann einen Alarm auslösen: {unalertableSelectedMetricNames.join(', ')}.
		Sie erscheinen weiterhin im Briefing, lösen aber keine Warnung aus.
	</p>
{:else}
	<AlertMetricLevelTable
		activeMetrics={effectiveActiveMetrics}
		levels={effectiveMetricLevels}
		onLevelChange={handleMetricLevelChange}
	/>
	{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}
		<p class="option-hint alarme-unalertable-hint" data-testid="alarme-unalertable-metrics-hint">
			Für diese Größen gibt es keinen Alarm: {unalertableSelectedMetricNames.join(', ')}.
			Sie erscheinen weiterhin im Briefing, lösen aber keine Warnung aus.
		</p>
	{/if}
{/if}
```

Drei Zustände (Vergleichs-Kontext; Tour bleibt strukturell bei den
äußeren beiden, da `unalertableSelectedMetricNames` dort immer `[]` ist):

1. **Nichts gewählt** (`effectiveActiveMetrics.length === 0` UND
   `unalertableSelectedMetricNames.length === 0`) → Leerzustand-Meldung
   wie bisher, mit dem in AC-6 korrigierten Reiter-Namen. Einzige
   Fläche, in der dieser Text erscheint.
2. **Nur nicht-alarmfähige Größen gewählt**
   (`effectiveActiveMetrics.length === 0` UND
   `unalertableSelectedMetricNames.length > 0`) → **kein** Leerzustand-
   Text, stattdessen der neue Satz „Keine der gewählten Größen kann
   einen Alarm auslösen: …" (eigener, PO-freigegebener Satzanfang,
   NICHT derselbe wie Zustand 3). Keine Tabelle.
3. **Gemischt oder nur alarmfähig** (`effectiveActiveMetrics.length >
   0`) → Tabelle; darunter der Satz „Für diese Größen gibt es keinen
   Alarm: …", sofern `unalertableSelectedMetricNames.length > 0`.

Zustand 2 nutzt bewusst dieselbe CSS-Klasse `alarme-no-metrics-hint` wie
Zustand 1 (Karten-/Rahmen-Optik, kein neuer Stil nötig) — beide Zustände
zeigen KEINE Tabelle, der Hinweistext trägt dort dieselbe visuelle
Prominenz wie der Leerzustand-Text, den er ersetzt. Zustand 3 bleibt beim
`option-hint`-Fußnoten-Look (Satz unterhalb einer bereits sichtbaren
Tabelle). Unterscheidung der beiden inhaltlich verschiedenen Sätze in
Zustand 2 und Zustand 3 über **unterschiedliche Test-IDs**
(`alarme-only-unalertable-hint` vs. `alarme-unalertable-metrics-hint`)
und **unterschiedlichen Satzanfang** — niemals beide gleichzeitig
sichtbar, da sie sich gegenseitig ausschließenden `{#if}`-Zweigen
zugeordnet sind.

### 5. Keine Änderung an den drei Vergleichs-Einbettungen

`CompareTabs.svelte:1422`, `CompareNewEditor.svelte:412` (Desktop) und
`CompareNewEditor.svelte:499` (mobil) reichen `catalog={alarmeCatalog}`
bereits seit E1a-2 durch. Beide neuen Sätze lesen denselben `catalog`-Prop
wie die bestehende Tabelle — an keiner der drei Stellen ist eine
Code-Änderung nötig. Der Nachweis muss trotzdem **jede** Einbettung
einzeln treffen (s. Test-Plan, Fehlerklasse #1320/E1a-2-Adversary-Befund
F001).

### 6. Tour-Kontext — unangetastet

`context="route"` liest weiterhin ausschließlich die `activeMetrics`-Prop
(unverändert seit E1a-2 AC-7). `AlarmeScheduleTab.svelte` bekommt keine
neue Prop, keinen Katalog, keine Metrik-Auswahl-Weitergabe — das ist eine
bewusste Begrenzung dieser Etappe (s. Known Limitations), keine
versehentliche Lücke. Der Tour-Zweig bleibt bei genau zwei sichtbaren
Zuständen (Leerzustand-Meldung oder Tabelle), da `unalertableSelectedMetricNames`
dort strukturell immer `[]` ist.

## Expected Behavior

- **Input A:** Ein Nutzer öffnet im Ortsvergleich den Reiter
  *Wetter-Metriken* und aktiviert „Wind (Maximum)" (alarmfähig) sowie
  „Sonnenstunden", „Bewölkung", „Gefühlte Temperatur (Minimum)" und
  „Gefühlte Temperatur (Maximum)" (alle vier nicht alarmfähig); danach
  öffnet er den Reiter *Alarme*.
- **Output A:** Die Empfindlichkeits-Tabelle zeigt die Zeile für Wind.
  Darunter erscheint der Satz „Für diese Größen gibt es keinen Alarm:
  Sonnenstunden, Bewölkung, Gefühlte Temperatur (Minimum), Gefühlte
  Temperatur (Maximum). Sie erscheinen weiterhin im Briefing, lösen aber
  keine Warnung aus." „Sonnenstunden" und „Bewölkung" tragen keinen
  Klammerzusatz (eindeutiges `label` im Register), beide
  „Gefühlte Temperatur"-Varianten tragen ihn (mehrdeutiges `label`).
  Wählt derselbe Nutzer ausschließlich alarmfähige Größen, bleibt der
  Satz vollständig aus.
- **Input B (Sonderfall):** Ein Nutzer wählt im Ortsvergleich
  ausschließlich nicht-alarmfähige Größen, z. B. nur „Bewölkung",
  „UV-Index" und „Luftfeuchtigkeit"; danach öffnet er den Reiter *Alarme*.
- **Output B:** Er sieht **weder** die Leerzustand-Meldung **noch** eine
  Tabelle, sondern den Satz „Keine der gewählten Größen kann einen Alarm
  auslösen: Bewölkung, UV-Index, Luftfeuchtigkeit. Sie erscheinen
  weiterhin im Briefing, lösen aber keine Warnung aus." Seine Auswahl
  wird an keiner Stelle als „nichts gewählt" dargestellt.
- **Input C:** Ein Nutzer wählt im Ortsvergleich ausschließlich „Gefühlte
  Temperatur (Minimum)" — die zweite Variante bleibt abgewählt.
- **Output C:** Der Satz nennt sie trotzdem als „Gefühlte Temperatur
  (Minimum)", mit Klammerzusatz — weil ihr `label` im Register
  mehrdeutig ist, unabhängig davon, ob die zweite Variante mitgewählt
  wurde (s. AC-10).
- **Input D:** Ein Nutzer öffnet den Alarme-Reiter bei einer Tour, oder im
  Ortsvergleich ohne jede Metrik-Auswahl.
- **Output D:** Er sieht ausschließlich die (jetzt korrekt beschriftete)
  Leerzustand-Meldung — nie einen der beiden Erklärsätze.
- **Side effects:** Keine. Rein lesende Ableitung, kein neuer
  Netzwerk-Request, keine Persistenz-Änderung, kein Backend-, Go- oder
  Mail-Renderer-Eingriff (Renderer-Mail-Gate #811 nicht betroffen).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat im Ortsvergleich sowohl alarmfähige als
  auch nicht-alarmfähige Wetter-Metriken ausgewählt / When er den Reiter
  *Alarme* öffnet / Then erscheint unterhalb der Empfindlichkeits-Tabelle
  ein Satz, der die nicht-alarmfähigen ausgewählten Größen namentlich
  nennt und erklärt, dass sie weiterhin im Briefing erscheinen, aber
  keinen Alarm auslösen.
  - Test: `deriveUnalertableSelectedMetricNames()` gegen ein
    realistisches Katalog-Fixture (Struktur wie
    `REAL_CATALOG_FIXTURE`/`compareMetricSelection.test.ts`, ergänzt um
    `alertMetric`-Werte analog E1a-2) liefert für eine gemischte Auswahl
    genau die Namen der nicht-alarmfähigen Größen, keine der alarmfähigen.

- **AC-2:** Given eine Auswahl enthält sowohl zwei Größen mit demselben,
  im Register mehrfach vorkommenden `label` (z. B. „Gefühlte Temperatur"
  Minimum und Maximum) als auch eine dritte Größe mit einem im Register
  eindeutigen `label` (z. B. „Sonnenstunden") / When der Erklärsatz
  gebildet wird / Then tragen die beiden mehrdeutigen Größen je ihren
  Klammerzusatz mit der Auswertung (z. B. „Gefühlte Temperatur
  (Minimum)"), während die eindeutige Größe ohne Klammerzusatz erscheint
  (z. B. „Sonnenstunden", nicht „Sonnenstunden (Summe)").
  - Test: Fixture mit zwei Katalog-Einträgen gleichen `label`s
    (unterschiedliches `aggregation_label`) und einem dritten Eintrag mit
    eindeutigem `label`, alle drei `alertMetric: null` und aktiv →
    `deriveUnalertableSelectedMetricNames()` liefert die beiden
    mehrdeutigen Namen je mit Klammerzusatz und den dritten Namen ohne.

- **AC-3:** Given ein Nutzer hat ausschließlich alarmfähige Wetter-Metriken
  ausgewählt / When er den Reiter *Alarme* öffnet / Then erscheint kein
  Erklärsatz unterhalb der Tabelle.
  - Test: Fixture, bei der alle aktiven Schlüssel ein `alertMetric` ungleich
    `null` tragen → `deriveUnalertableSelectedMetricNames()` liefert `[]`.

- **AC-4:** Given ein Nutzer hat im Ortsvergleich wirklich keine
  Wetter-Metrik ausgewählt (echter Leerzustand, keine einzige aktive
  Größe) / When er den Reiter *Alarme* öffnet / Then sieht er
  ausschließlich die Leerzustand-Meldung — weder Tabelle noch einen der
  beiden Erklärsätze.
  - Test: Fixture mit leerer aktiver Auswahl (`[]`, bewusst leer, nicht
    `null`) → `effectiveActiveMetrics` UND
    `deriveUnalertableSelectedMetricNames()` liefern beide `[]`;
    struktureller Nachweis, dass in diesem Fall ausschließlich der erste
    der drei Zweige (Leerzustand-Testid `alarme-no-metrics`) rendert.

- **AC-5:** Given eine Auswahl mehrerer nicht-alarmfähiger Größen, die der
  Nutzer in einer bestimmten Reihenfolge angeklickt hat / When der
  Erklärsatz gebildet wird / Then folgt die Reihenfolge der genannten
  Namen der stabilen Katalog-Reihenfolge (derselben, in der die
  Wetter-Metriken-Tabelle die Größen zeigt), nicht der Klick-Reihenfolge
  des Nutzers.
  - Test: aktive Schlüssel in umgekehrter Katalog-Reihenfolge übergeben →
    `deriveUnalertableSelectedMetricNames()` liefert die Namen dennoch in
    Katalog-Reihenfolge.

- **AC-6:** Given ein Nutzer öffnet den echten Leerzustand des
  Alarme-Reiters — im Ortsvergleich oder bei einer Tour / When er den
  Hinweistext liest, der ihn zur Metrik-Auswahl führt / Then nennt der
  Text den Reiter „Wetter-Metriken", nicht mehr „Wertebereiche" — an
  beiden Stellen der Oberfläche identisch formuliert.
  - Test: struktureller Nachweis (Svelte-Compiler-AST, Text-Knoten im
    ersten der drei Zweige, Testid `alarme-no-metrics`), dass der
    angezeigte Text „Wetter-Metriken" enthält und „Wertebereiche" nicht
    mehr vorkommt.

- **AC-7:** Given eine Tour (kein Ortsvergleich) mit ausgewählten
  Wetter-Metriken, von denen manche nicht alarmfähig wären / When der
  Reiter *Alarme* im Tour-Kontext gerendert wird / Then erscheint dort zu
  keinem Zeitpunkt einer der beiden Erklärsätze — diese Etappe ändert am
  Tour-Kontext nichts außer dem in AC-6 beschriebenen Reiter-Namen; der
  Tour-Kontext bleibt strukturell bei genau zwei sichtbaren Zuständen.
  - Test: struktureller Nachweis, dass der Touren-Zweig (`context="route"`)
    im Template keinen Bezug auf `unalertableSelectedMetricNames`,
    `catalog` oder `deriveUnalertableSelectedMetricNames` enthält — analog
    zum bestehenden E1a-2-Regressionstest für `effectiveActiveMetrics`.

- **AC-8:** Given ein Nutzer erreicht den Alarme-Reiter des Ortsvergleichs
  über eine der drei möglichen Flächen (Vergleichs-Hub, `/compare/new`
  Desktop, `/compare/new` mobil) / When dieselbe Auswahl aus alarmfähigen
  und nicht-alarmfähigen Größen aktiv ist / Then zeigt der Erklärsatz an
  jeder der drei Flächen denselben Inhalt — keine Fläche zeigt ihn
  fälschlich nicht oder mit anderem Inhalt (Fehlerklasse #1320,
  E1a-2-Adversary-Befund F001).
  - Test: struktureller Nachweis (AST), dass an allen drei
    `<AlarmeTab context="vergleich">`-Instanzen (`CompareTabs.svelte`,
    `CompareNewEditor.svelte` ×2) derselbe `catalog`-Prop ankommt, den
    beide Erklärsätze lesen — kein neuer Datenpfad, der an einer Stelle
    fehlen könnte; ergänzend eine explizite Zählung, dass alle drei
    Instanzen erfasst werden (keine stillschweigend übersprungene
    Einbettung).

- **AC-9:** Given ein Nutzer hat im Ortsvergleich ausschließlich
  nicht-alarmfähige Wetter-Metriken ausgewählt (z. B. nur Bewölkung,
  UV-Index, Luftfeuchtigkeit — echte Auswahl, aber
  `effectiveActiveMetrics.length === 0`) / When er den Reiter *Alarme*
  öffnet / Then sieht er weder die Leerzustand-Meldung noch eine Tabelle,
  sondern den eigenständig formulierten Satz „Keine der gewählten Größen
  kann einen Alarm auslösen: <Namen>. Sie erscheinen weiterhin im
  Briefing, lösen aber keine Warnung aus." — seine Auswahl wird nicht
  fälschlich als „nichts gewählt" dargestellt (PO-Nachbesserung
  2026-07-31, schließt den zentralen Sonderfall dieser Etappe).
  - Test: Fixture, bei der alle aktiven Schlüssel `alertMetric: null`
    tragen (mindestens zwei Größen) → `effectiveActiveMetrics` liefert
    `[]`, `deriveUnalertableSelectedMetricNames()` liefert die Namen;
    struktureller Nachweis, dass in diesem Fall ausschließlich der
    zweite der drei Zweige (Testid `alarme-only-unalertable-hint`)
    rendert — weder der Leerzustand-Zweig (`alarme-no-metrics`) noch die
    Tabelle noch der Zustand-3-Satz (`alarme-unalertable-metrics-hint`).

- **AC-10:** Given ein Nutzer wählt im Ortsvergleich nur EINE der beiden
  Varianten einer im Register mehrdeutigen Größe (z. B. nur „Gefühlte
  Temperatur (Minimum)", nicht „Gefühlte Temperatur (Maximum)") / When
  der Erklärsatz gebildet wird / Then trägt die gewählte Variante
  trotzdem ihren Klammerzusatz — die Mehrdeutigkeit wird gegen den
  gesamten Katalog geprüft, nicht gegen die aktuelle Auswahl. Die
  Schreibweise einer Größe ändert sich also nicht dadurch, was der
  Nutzer sonst noch (nicht) ausgewählt hat, und bleibt gleichlaufend mit
  der Schreibweise im Reiter *Wetter-Metriken*.
  - Test: `deriveUnalertableSelectedMetricNames()` erhält den **vollen**
    Katalog (mit beiden „Gefühlte Temperatur"-Einträgen), aber eine
    aktive Auswahl, die **nur** den Minimum-Schlüssel enthält →
    liefert „Gefühlte Temperatur (Minimum)" mit Klammerzusatz, nicht das
    bloße `label` „Gefühlte Temperatur" — beweist, dass die
    Häufigkeitszählung nicht (fälschlich) über die gefilterte Auswahl
    statt über den vollen Katalog läuft.

## Known Limitations

- **Kein Erklärsatz im Tour-Kontext.** Die Alarm-Tabelle einer Tour speist
  sich aus `trip.display_config.metric_alert_levels` (bereits gesetzte
  Schwellen), nicht aus der Metrik-Auswahl des Nutzers
  (`AlarmeScheduleTab.svelte:36-39`) — es gibt dort schlicht keine wahre
  Datengrundlage für einen der beiden Erklärsätze. Das ist eine bewusste
  PO-Entscheidung für diese Etappe (2026-07-31), keine übersehene Lücke:
  sie nachzuliefern erfordert, dass der Tour-Container zusätzlich zu den
  Schwellen auch die Metrik-Auswahl und den Katalog durchreicht — ein
  eigener Eingriff mit eigenem Nachweis. Kandidat für eine spätere, noch
  nicht benannte #1435-Etappe. Der Tour-Kontext bleibt deshalb bei der
  ursprünglichen Zwei-Zustands-Logik (Leerzustand oder Tabelle), auch
  nach dieser Nachbesserung.
- **Keine Kontext-Weiche für den Leerzustand-Text.** Die Korrektur „Wähle
  im Tab „Wetter-Metriken"…" gilt identisch für Tour und Vergleich, weil
  beide Reiter-Register denselben Namen verwenden
  (`compareTabsResolve.ts:13-14`, `TripTabs.svelte:80-81`). Ändert sich
  diese Benennung künftig auseinander, muss der Text erneut geprüft
  werden.
- **Die Mehrdeutigkeits-Regel ist datengetrieben, nicht hartkodiert.**
  Die Funktion kennt „Temperatur"/„Gefühlte Temperatur" nicht namentlich
  — sie zählt `label`-Häufigkeiten zur Laufzeit gegen den gelieferten
  Katalog. Kommt künftig ein drittes Register-`label` doppelt vor (oder
  fällt eines der beiden heutigen Duplikate weg), passt sich der
  Klammerzusatz automatisch an, ohne Codeänderung — das ist beabsichtigt
  und kein Regressionsrisiko.
- **Harte Auflage #1435 eingehalten:** `compare_alert.py`,
  `weather_change_detection.py` und `alert_preset.py` werden von dieser
  Etappe nicht verändert. E1b ist reine Anzeige-Arbeit im Frontend.
- **Renderer-Mail-Gate (#811) nicht betroffen:** keine Datei dieser
  Etappe liegt unter `src/output/renderers/email/*.py` o. ä.

## Bewusst nicht Teil dieser Etappe

- **Kreuz-Verdrahtung Wind→Böen und die vier zuvor unerreichbaren
  Größen** — bereits erledigt in E1a-2 (`53f88757`).
- **Stundenverlauf-Darstellung der Alarm-Auslöser** — gehört zu #1406
  Scheibe B, nicht zu #1435.
- **Schwellwert-Konfiguration der vier in E1a-2 neu erreichbaren Größen**
  — gehört zu #1435 Etappe E4.
- **`_ALERT_METRIC_TO_CATALOG_ID` als vierte, weiterhin bestehende
  Zuordnungsliste im Abweichungs-Alert-Subsystem
  (`weather_change_detection.py`)** — bleibt unangetastet, Kandidat für
  eine spätere #1435-Etappe (bereits in der E1a-1/E1a-2-Spec als Known
  Limitation vermerkt, hier nicht erneut angefasst).

## Test Plan

Kern-Schicht (deterministisch, ohne Netz), `node --import
./test-lib-loader.mjs --experimental-strip-types --test <datei>`, analog
zum Vorgänger E1a-2.

| Testdatei (neu) | Belegt | Stil |
|---|---|---|
| `frontend/src/lib/components/shared/alarme-tab/__tests__/unalertableSelectedMetricNames.test.ts` | AC-1, AC-2, AC-3, AC-5, AC-10 | Fixture-basiert, reine Funktion `deriveUnalertableSelectedMetricNames()` gegen ein Katalog-Fixture im Stil von `REAL_CATALOG_FIXTURE` (`compareMetricSelection.test.ts`), ergänzt um `alertMetric`-Werte. Deckt zusätzlich die Häufigkeits-Regel (AC-2) und die Bezugsgrößen-Absicherung gegen den vollen Katalog statt der Auswahl (AC-10) ab. |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_unalertable_hint_structure.test.ts` | AC-4, AC-6, AC-7, AC-8, AC-9 | Svelte-Compiler-AST (`svelte/compiler` `parse`), analog `alarme_tab_catalog_prop_structure.test.ts` — inspiziert die drei sich gegenseitig ausschließenden Template-Zweige (Testids `alarme-no-metrics`, `alarme-only-unalertable-hint`, `alarme-unalertable-metrics-hint`), Text-Knoten und Attribut-Durchreichung, kein Dateiinhalt-Grep auf rohe Strings. |

Beide Dateien lösen ihren Prüfling relativ zu `import.meta.url` auf
(Pfadregel #1409), kein fester Hauptrepo-Pfad. Bestehende E1a-2-Tests
(`alarme_tab_catalog_prop_structure.test.ts`,
`weatherMetricsTabVergleichLabels.test.ts`) bleiben unverändert grün —
kein Regressionsrisiko, da diese Etappe keine bestehende Ableitung
verändert, nur ergänzt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt das in E1a-1/E1a-2 bereits etablierte Prinzip
  „sichtbar statt kommentarlos weglassen" (vgl. `docs/specs/modules/warn_unavailable_hint.md`,
  #1348) auf den Alarme-Reiter fort — keine neue Grundsatzentscheidung im
  Sinne der CLAUDE.md-ADR-Trigger (Kanäle, Provider, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie unberührt).

## Changelog

- 2026-07-31: Initial spec created (Feature #1435 Etappe E1b, Fortsetzung
  von E1a-1/E1a-2). Belegstellen gegen den aktuellen Code verifiziert
  (`AlarmeTab.svelte`, `activeAlertMetricsFromCatalog.ts`,
  `AlarmeScheduleTab.svelte`, `WeatherMetricsTab.svelte`,
  `alarme_tab_catalog_prop_structure.test.ts`), nicht aus dem
  Kontextdokument übernommen.
- 2026-07-31: PO-Nachbesserung 1 — Sonderfall „ausschließlich
  nicht-alarmfähige Größen gewählt" ergänzt (AC-9), AC-4 auf den echten
  Leerzustand präzisiert, Implementation Details Abschnitt 4 von einer
  Zwei- auf eine Drei-Zustands-Verzweigung umgeschrieben, LoC-Schätzung
  nachgezogen.
- 2026-07-31: PO-Nachbesserung 2 (RED-Phasen-Befund) — Klammerzusatz
  erscheint nur noch bei im Register mehrdeutigem `label`, geprüft gegen
  den vollen Katalog statt gegen die Auswahl (AC-2 präzisiert, AC-10 neu).
  LoC-Schätzung nachgezogen, Überschreitung des 250-Zeilen-Budgets vom PO
  ausdrücklich freigegeben.
