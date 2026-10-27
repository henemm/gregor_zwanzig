# Context: fix-1895-s2-alarmkarte-rueckbau

> #1895 Schritt 2, **Variante A** (PO-Entscheid 2026-09-21). Schritt 1 ist live
> (`a928dbce`, PR #2393) — dort fielen Modus-Auswahl und Absolut-Feld.

## Request Summary

Die Alarmregel-Karte im Trip-Editor zeigt weiterhin zwei Eingaben, die keinen Alarm
ausloesen: die Δ-Schwelle und das Zeitfenster. Sie sollen aus **beiden** Ansichten
verschwinden (Bearbeiten-Karte **und** Ansichtskarte); uebrig bleibt Metrik · Kanaele ·
aktiv. Kein Datenmodell-Umbau, kein Backend, keine Migration.

**Offene Zuschnitt-Frage fuer die Spec (AC-Ebene, nicht Aufraeumarbeit):** Die
Ansichtskarte traegt neben dem Schwellenwert eine `<Pill>` mit dem Zeichen „Δ"
(`AlertRuleRow.svelte:184-186`). Verschwindet der Schwellenwert, beschriftet ein blosses
„Δ" neben dem Metrik-Namen nichts mehr. Ob die Pille mitfaellt, entscheidet, was der
Nutzer sieht — gehoert also in die Akzeptanzkriterien. Die E2E-Spec sichert sie heute zu
(`gewitter-absolutregel-gesperrt.spec.ts:237`, `toContainText('Δ')`).

## Warum die beiden Felder nichts bewirken (gemessen 2026-09-21, nicht vermutet)

| Stelle | Aussage |
|---|---|
| `src/services/deviation_alert_engine.py:174-203` | `_select_detector()` speist sich ausschliesslich aus `expand_per_metric_levels(config.metric_alert_levels, …)`. `trip.alert_rules` wird dort nicht gelesen. |
| `src/services/alert_channels.py:86-93` | `_trip_channel_inputs()` liest von der Regel **nur** `enabled` und `channels` — `threshold`/`delta_window` kommen nirgends vor. |
| ADR-0043 | Die Empfindlichkeitsstufe ist der einzige Regler, der ausloest. |

Damit ist der Befund dieselbe Klasse wie der Absolut-Modus aus Schritt 1: eine Eingabe,
die stillschweigend nichts bewirkt.

## Nebenbefund aus dieser Recherche (nicht Teil von Variante A)

`resolve_alert_channels()` (`src/services/alert_channels.py:28-66`) bildet ueber alle
aktiven Regeln die **Union** der Kanaele, und `_send_alert()` fragt
`_effective_alert_channels(trip)` **ohne** die ausloesende Metrik. Die Kanalauswahl an der
Regel ist also auch heute schon **keine Zuordnung je Metrik** — ein Gewitter-Alarm geht an
dieselben Kanaele wie ein Boeen-Alarm. Der Ortsvergleich kennt gar keine Regeln
(`_compare_channel_inputs()` liefert immer `[]`), dort kommt die Kanalwahl trip-weit aus
`alert_channels`. Das ist der Stoff fuer die Varianten B/C und gehoert in den
Datenmodell-Zug #1230 (`status:deferred`) — hier ausdruecklich **nicht** angefasst.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | **Kern.** Edit-Card: `alert-rule-threshold` (Zeile ~120) + `alert-rule-delta-window` (~128). View-Card: `valueText` (~48) und `<span class="threshold">` (~183) rendern den toten Wert, die `<Pill>` daneben das Δ/Abs-Abzeichen. `draftDeltaThreshold`/`draftDeltaWindow` (~40-42) und `startEdit()` (~64-79) fallen mit. |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | `expandRules(rule, deltaThreshold, deltaWindow)` — die beiden Parameter kommen heute aus den Eingabefeldern. |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Rahmen. Berechnet `isPairFollower` aus `rule.pair_id` — seit Schritt 1 erzeugt `expandRules()` nie mehr ein Paar. |
| `frontend/src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts` | Bausteintests aus Schritt 1; pruefen u.a. `r.threshold === 20` / `r.delta_window === '6h'` fuer `newDefaultRule()`. |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | Bestandstests zu `expandRules()`/`newDefaultRule()`. |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` | **Muss gruen bleiben** — Nachweis, dass die Kanalzuordnung den Umbau ueberlebt. |
| `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` | 🔴 **In der CI-Ratsche** (`.github/ci_e2e_specs.txt:246`). Sichert heute ausdruecklich zu, dass Δ-Schwelle und Zeitfenster **sichtbar sind** (Zeilen 101, 122-126, 141, 147, 174, 199-200). Schritt 2 dreht genau diese Zusicherungen um. |

## Existing Patterns

- **Schritt 1 ist die Blaupause** (`docs/specs/modules/fix_1895_alarm_modus_rueckbau.md`):
  UI-Rueckbau ohne Datenmodell-Anfassen, Nachweis „Bestandsdaten unberuehrt" ueber
  `expandRules()`, Bausteintest unter `__tests__/` plus eine Staging-Strecke im Browser.
- **Bausteintests beweisen die `.svelte`-Verdrahtung NICHT** — das steht so im Kopf von
  `alertRegelNurAenderung.test.ts`. Dass ein Feld aus der Karte verschwindet, ist nur im
  Browser messbar.
- Mount-Lage: `AlertRulesEditor` haengt ausschliesslich im Trip
  (`TripNewEditor.svelte:862` und `:1102`; `TripEditView.svelte:205` liegt hinter der seit
  2026-06-07 auf `redirect(307)` stehenden Route `/trips/<id>/edit`, #616).
  **Kein Compare-Mount** — der Ortsvergleich nutzt `shared/AlarmeTab.svelte`.

## Dependencies

- **Upstream:** `$lib/types` (`AlertRule`), `alertMetricLabels` (`info.comparison`,
  `info.unit`), `alertChannels.ts` (`effectiveAlertChannels`, `toggleAlertChannel`).
- **Downstream:** `AlertRulesEditor` → `TripNewEditor` (zwei Mounts). Backend unberuehrt:
  Go-Store und Python-Loader lesen `threshold`/`delta_window` weiter aus der Persistenz,
  nur niemand tippt sie noch ein.

## Existing Specs

- `docs/specs/modules/fix_1895_alarm_modus_rueckbau.md` — Schritt 1, direkte Vorlage
- `docs/specs/modules/issue_223_alert_rules_editor.md` — Ursprungs-Spec des Editors
- `docs/adr/` — ADR-0043 (Empfindlichkeitsstufe als einziger Alarm-Regler)

## Risks & Considerations

1. 🔴 **Zwei verschiedene Dinge, die nicht verschmelzen duerfen:**
   - **Neue Regel** (`newDefaultRule()`): schreibt weiterhin `threshold: 20`,
     `delta_window: '6h'`. Das ist **kein** Risiko, sondern Bestand — AC-7 aus Schritt 1
     und die E2E-Zusicherung `toHaveValue('20')` haengen daran. Hier nichts aendern.
   - **Bestandsregel beim Speichern** (`expandRules()`): muss `rule.threshold` und
     `rule.delta_window` **durchreichen**, nicht auf `20`/`'6h'` hart setzen. Sonst
     schreibt der erste Speichervorgang jede Bestandsregel still um; „Bestandsdaten
     unberuehrt" war der benannte Nachweis aus Schritt 1.
   - **Daraus folgt eine Entscheidung fuer die Spec:** `startEdit()` (`AlertRuleRow.svelte:70-79`)
     setzt heute fuer eine Alt-Regel mit `kind !== 'delta'` bewusst 20/6h, weil deren
     `threshold` eine Absolut-Zahl traegt (z.B. 50 km/h) und als Δ-Schwelle etwas voellig
     anderes aussagen wuerde. Faellt die Eingabe weg und liest `expandRules()` direkt aus
     der Regel, wird aus der 50 stillschweigend eine Δ-Schwelle von 50. Die Spec muss
     sagen, welcher der beiden Wege gilt — das darf nicht als Nebenwirkung des Rueckbaus
     herausfallen.
2. 🔴 **Der Rueckbau muss die Ansichtskarte mit abdecken.** `valueText` zeigt den toten
   Wert (z.B. „> 20 km/h") auf der Ansichtszeile. Nur die Edit-Card zu raeumen, laesst das
   Falschversprechen einen Klick weiter stehen.
3. 🔴 **Die E2E-Spec in der CI-Ratsche kippt — Umschreiben, nicht Nachbessern.**
   `gewitter-absolutregel-gesperrt.spec.ts` laeuft im `e2e`-Check und sichert heute genau
   das Gegenteil zu. Was sich umdreht:
   - Der Testtitel selbst wird falsch: „…**aber Δ-Schwelle und Zeitfenster** (AC-1)"
     (Zeile 101).
   - Zeilen 122-126, 141, 147, 174: `toHaveCount(1)` / `toBeVisible()` auf
     `alert-rule-threshold` und `alert-rule-delta-window` werden zu `toHaveCount(0)`.
   - Zeilen 199-200: `toHaveValue('20')` / `toHaveValue('6h')` verlieren ihr Subjekt.
   - Zeilen 195/237: `toContainText('Δ')` haengt an der offenen Pillen-Frage oben.

   Die Ratsche wird **nicht nachgezogen**, die Spec wird angepasst. Wird die Datei dabei
   umbenannt (ihr Name meint die *Absolut*-Sperre aus Schritt 1, nach Schritt 2 bewacht
   sie mehr), wandert der Eintrag in `.github/ci_e2e_specs.txt:246` **1:1 mit** — ein
   bewusster Ratschen-Edit, kein Leeren. Das gehoert so in die Spec, damit der Adversary
   es als Absicht erkennt.
4. **Was bleiben muss:** Kanal-Chips, Aktiv-Haken, Metrik-Auswahl, `id`, `channels`,
   `enabled`, `kind:'delta'`. Die Kanalzuordnung ist die einzige verbliebene Wirkung der
   Regel — sie darf hier weder erfunden noch verworfen werden (`alertChannels.test.ts`
   ist der Waechter).
5. **Layout:** `.alert-rule-view` definiert 6 Grid-Spalten (`AlertRuleRow.svelte:261-263`).
   Fallen Schwellen-Span und Δ-Pille weg, aendert sich die Spaltenzahl — die Grid-Regel
   muss mitgezogen werden. (Der bekannte Bestandsfehler „7 Kinder bei zwei Kanaelen",
   in #1199 gebucht, entspannt sich dadurch, ist aber nicht Ziel dieser Lieferung.)
6. **Toter Bestand, der mitfallen koennte** — als Frage an die Analyse, nicht als gesetzt:
   `pairFollower`/`pair-indicator` (`AlertRulesEditor.svelte:56-58`, `AlertRuleRow.svelte:172-180`)
   ist seit Schritt 1 unerreichbar. (Die `<Pill>` selbst ist **keine** Aufraeumarbeit —
   sie steht als Zuschnitt-Frage oben in der Request Summary.) Ebenso der
   Alarmregel-Block in `frontend/e2e/helpers.ts:343-355` (`fillStep4`), der auf
   `alert-rule-severity` zielt — ein Testid, das die Karte gar nicht mehr traegt, in einem
   Helfer des abgeschafften 5-Schritt-Wizards (#622); **kein** Spec ruft ihn mit
   `alertRules:` auf. Nach der Nebenbefund-Triage (CLAUDE.md) ist das ein Sammel-Eintrag
   fuer **#1199**, kein Bestandteil dieser Lieferung.

---

# Analysis

> Phase 2, 2026-09-21. **Der Explore-/Bug-Intake-Fan-out aus Step 2a/2b des Skills
> entfaellt bewusst:** das Material liegt vollstaendig oben aus `/10-context` auf der
> Platte. Ergaenzt wurden nur die zwei Messungen, die der Kontext offen liess
> (Compare-Mounts, `expandRules()`-Aufrufstellen) — beide unten belegt.

## Type

**Bugfix** (UI-Rueckbau eines Falschversprechens) — Fortsetzung von #1895 Schritt 1.

## Entscheidungen, die diese Analyse trifft

Der Kontext liess drei Punkte offen. Alle drei sind hier entschieden, damit sie als
Akzeptanzkriterium in die Spec gehen und nicht als Nebenwirkung herausfallen.

### E-1: Die Δ-Pille faellt mit (Zuschnitt-Frage aus der Request Summary)

`AlertRuleRow.svelte:184-186` rendert `rule.kind === 'delta' ? 'Δ' : 'Abs'`. Seit Schritt 1
ist der `'Abs'`-Zweig **unerreichbar** — der Go-Store normalisiert `Kind` bei Load *und*
Save auf `delta` (`internal/store/trip.go:206,238` → `internal/model/trip.go:383`), und der
Editor erzeugt nichts anderes mehr. Die Pille zeigt also auf **jeder** Zeile konstant `Δ`
und unterscheidet nichts. Ihr einziger verbliebener Sinn war, den danebenstehenden
Schwellenwert als Δ-Wert zu beschriften — faellt der Wert, beschriftet sie nichts mehr.

**Entscheidung:** Die `<Pill>` faellt zusammen mit dem Schwellenwert. Uebrig bleibt genau
das, was die Request Summary nennt: Metrik · Kanaele · aktiv. Das ist nutzersichtbar und
gehoert damit in die ACs.

### E-2: 🔴 `expandRules()` muss `delta_window` durchreichen — und das kehrt eine heute aktiv zugesicherte Zusicherung um

Das ist der wichtigste Befund dieser Analyse. Er ist **kein** Nice-to-have, sondern die
Bedingung dafuer, dass Schritt 2 nicht das AC-2-Versprechen aus Schritt 1 bricht
(„alle vom Client nicht gesendeten Felder erhalten — Read-Modify-Write, kein Replace").

**Die Mechanik.** `alertRuleDefaults.ts:51-55` ist asymmetrisch:

```ts
export function expandRules(
    rule: AlertRule,
    deltaThreshold: number = rule.threshold,   // ← liest aus der Regel
    deltaWindow: string = '6h'                 // ← harte Konstante, NICHT rule.delta_window
): AlertRule[]
```

Heute ist dieser Default **nie erreichbar**: `saveEdit()` (`AlertRuleRow.svelte:92`) uebergibt
immer explizit, und `startEdit()` (`:75`) hat das Zeitfenster zuvor mit
`rule.delta_window ?? '6h'` aus der Bestandsregel gelesen. Die Eingabefelder maskieren die
Konstante.

**Faellt die Eingabe weg, wird aus dem nie erreichten Default der einzige Pfad** — und
`expandRules(synced)` schreibt jede Bestandsregel mit z.B. `delta_window:'12h'` beim ersten
Speichern still auf `'6h'` um. Das ist genau die Klasse BUG-DATALOSS-GR221: ein Feld, das
der Client nicht mehr sendet, wird beim Speichern ueberschrieben statt durchgereicht.

**Entscheidung:** `expandRules(rule)` reicht `rule.threshold` und `rule.delta_window ?? '6h'`
durch. Der `'6h'`-Rueckfall bleibt nur fuer Regeln **ohne** Zeitfenster (eine Δ-Regel ohne
Fenster waere unvollstaendig — `alertRuleDefaults.test.ts:84` sichert das zu Recht zu).

**🔴 Das dreht drei gruene Bestandstests um — benannt, nicht stillschweigend:**

| Test | Sichert heute zu | Nach Schritt 2 |
|---|---|---|
| `alertRuleDefaults.test.ts:119-123` | `expandRules(rule mit '12h')` **ohne** Argumente → `'6h'`, Kommentar: „der Signatur-Vorgabewert ist die Konstante 6h" | umgekehrt: → `'12h'` |
| `alertRegelNurAenderung.test.ts:134-139` | `expandRules(rule)` ohne Argumente → `delta_window === '6h'` | Eingangsregel braucht ein eigenes Fenster im Fixture |
| `alertRuleDefaults.test.ts:107-112` (F005) | ein Regel-Zeitfenster „ueberstimmt den Parameter nicht" | **gegenstandslos** — es gibt keinen Parameter mehr |

Diese Tests waren korrekt, solange ein Parameter existierte. Sie zu aendern ist Teil der
Lieferung und muss in der Spec stehen, sonst liest der Adversary es als Regression.

### E-3: Die `kind !== 'delta'`-Vorsichtsregel in `startEdit()` faellt ersatzlos

`AlertRuleRow.svelte:73-79` setzt fuer eine Alt-Regel mit `kind !== 'delta'` bewusst 20/6h,
weil deren `threshold` eine Absolut-Zahl traegt. Mit dem Wegfall der Eingabe faellt
`startEdit()`s Vorbelegung ganz weg — die Frage waere dann, ob `expandRules()` diese
Vorsicht erben muss.

**Entscheidung: nein.** Begruendung, die der Adversary pruefen kann:

1. Eine Regel mit `kind='absolute'` **existiert im Go-Pfad nicht** — `SyncAlertRules` laeuft
   bei Load *und* Save (belegt im Ticket, Kommentar vom 16.08.). Der Zweig ist in Produktion
   bereits unerreichbar.
2. Nach Schritt 2 wird `threshold` weder angezeigt noch bearbeitet. Es unveraendert
   durchzureichen ist die **einzige** Behandlung, die mit AC-2 aus Schritt 1 vertraeglich
   ist; ein Ueberschreiben auf 20 waere aktive Datenaenderung ohne Nutzerhandlung.

## Gegenmessungen dieser Phase

### M-1: Kein Compare-Mount — bestaetigt

```
grep -rn "AlertRulesEditor|AlertRuleRow" frontend/src frontend/e2e  (ohne alert-rules-editor/)
```

Ergebnis: `TripNewEditor.svelte:862` und `:1102` · `TripEditView.svelte:205` (hinter der seit
2026-06-07 auf `redirect(307)` stehenden Route, #616) · `organisms/index.ts` (Kommentar) ·
`shared/__tests__/legacy_wizard_removed.test.ts:100` (**Waechter**, kein Mount).

Unter `shared/` und `routes/` **kein** Treffer. Die drei bekannten Compare-Mounts im
Alarme-Reiter (`shared/AlarmeTab.svelte`) haengen an einem anderen Baustein.

**Folge:** Die Pendant-Sperre ist hier nicht in Betrieb; es braucht **kein** Compare-AC
(anders als AC-4 in Schritt 1, wo die Frage noch offen war). Das gehoert als Satz in die
Spec, damit die Abwesenheit als geprueft erkennbar ist und nicht als Luecke.

### M-2: `expandRules()` hat genau eine produktive Aufrufstelle

`AlertRuleRow.svelte:92` (`saveEdit()`). Alle uebrigen Treffer sind Tests oder Kommentare.
Die Signatur laesst sich also gefahrlos auf `expandRules(rule)` verkuerzen — der Umbau ist
auf eine Zeile Produktivcode plus die Testanpassungen aus E-2 begrenzt.

### M-3: Grid-Spalten — Abzaehlung, kein Heilversuch

`.alert-rule-view` (`AlertRuleRow.svelte:262`) definiert 6 Tracks. Kinder heute:
label · threshold · Pill · N Kanal-Chips · Checkbox · Kebab-div = **5 + N**.
Nach dem Rueckbau (threshold + Pill fallen): **3 + N**.

| Kanaele | Kinder heute / Tracks 6 | Kinder danach / Tracks 4 |
|---|---|---|
| 0 | 5 — passt | 3 — passt |
| 1 | 6 — passt | 4 — passt |
| 2 | 7 — **bricht** (#1199) | 5 — **bricht** |
| 3 | 8 — bricht | 6 — bricht |

**Entscheidung:** Die Tracks werden exakt um die zwei entfallenen reduziert (6 → 4). Der
Ueberlauf ab 2 Kanaelen bleibt damit **unveraendert** Bestand und bleibt in #1199 gebucht.
Ihn hier zu heilen (5 Tracks oder `flex-wrap`) waere Scope-Creep, den der Kontext
ausdruecklich ausschliesst. Das ist ein CSS-Satz fuer die Spec, **kein** AC.

### M-4: E2E-Spec wird umgeschrieben, nicht umbenannt

Der Kontext hielt eine Umbenennung mit 1:1-Ratschen-Umzug offen. **Entscheidung: nicht
umbenennen.** `gewitter-absolutregel-gesperrt.spec.ts` beschreibt weiterhin korrekt die
Zusicherung aus Schritt 1, die gueltig bleibt und weiter bewacht gehoert.
`.github/ci_e2e_specs.txt:246` bleibt **unberuehrt** — ein Ratschen-Edit weniger, den der
Adversary als Absicht akzeptieren muss.

Umzuschreiben sind die inneren Titel und Zusicherungen: Zeile 101 (Titel), 122-126, 141,
147, 174 (`toHaveCount(1)`/`toBeVisible()` → `toHaveCount(0)`), 199-200
(`toHaveValue('20')`/`toHaveValue('6h')` verlieren ihr Subjekt), 195 und 237
(`toContainText('Δ')` — faellt mit E-1).

## Affected Files

| Datei | Change Type | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | MODIFY | Edit-Card: `alert-rule-threshold` + `alert-rule-delta-window` raus, `draftDeltaThreshold`/`draftDeltaWindow` + `startEdit()`-Vorbelegung fallen (E-3). View-Card: `valueText`, `<span class="threshold">`, `<Pill>` raus (E-1). Grid-Tracks 6 → 4 (M-3). |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | MODIFY | `expandRules(rule)` — Parameter entfallen, `delta_window` wird durchgereicht (E-2). `newDefaultRule()` **unveraendert** (20/6h bleibt Bestand). |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | MODIFY | die drei Zusicherungen aus E-2 umdrehen bzw. streichen |
| `frontend/src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts` | MODIFY | Zeile 134-139 auf das Durchreichen umstellen; neuer Fall „Bestandsfenster ueberlebt" |
| `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` | MODIFY | Zusicherungen umdrehen (M-4), Datei behaelt ihren Namen |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` | — | **Muss gruen bleiben**, nicht anfassen — Waechter, dass die Kanalzuordnung den Umbau ueberlebt |
| `docs/reference/frontend_components.md` | MODIFY | Komponenten-Referenz nachziehen (wie in Schritt 1; `tests/tdd/test_issue_316_docs_cleanup.py` haengt daran) |

**Nicht angefasst:** `.github/ci_e2e_specs.txt` (M-4) · Go-Store, Python-Loader, `types.ts`
(`delta_window` bleibt im Datenmodell) · `shared/`, `compare/` (M-1) · `pairFollower`/
`pair-indicator` und `helpers.ts:343-355` → Sammel-Eintrag #1199 (Nebenbefund-Triage).

## Scope Assessment

- **Produktive Dateien fuers LoC-Limit:** 2 (`AlertRuleRow.svelte`, `alertRuleDefaults.ts`)
- **Geschaetztes Delta:** ca. −50 / +10 produktiv, Tests zusaetzlich — deutlich unter 250,
  **kein** `loc_limit_override` noetig (Stand vor Spec: `workflow.py status` zeigt +0)
- **Risiko: MITTEL.** Nicht wegen des Umfangs — der ist klein und rein im Frontend —,
  sondern wegen E-2: die Aenderung beruehrt den **Schreibweg auf Bestandsdaten**. Ein
  uebersehenes Durchreichen schreibt Nutzerdaten still um, und zwar unsichtbar, weil das
  Feld nach dem Rueckbau nirgends mehr angezeigt wird.

## Technical Approach

1. `expandRules()` **zuerst** (E-2) — das Durchreichen muss stehen, bevor die Eingabe faellt.
   Sonst existiert ein Zwischenstand, in dem `saveEdit()` bereits ohne Argumente ruft und
   die Konstante greift.
2. `AlertRuleRow.svelte` Edit-Card raeumen, danach View-Card (E-1), zuletzt das Grid (M-3).
3. Bestandstests aus E-2 umdrehen, E2E-Spec umschreiben (M-4).

## 🔴 Nachweis-Vorgabe fuer die Spec (Testebene)

Ein Bausteintest `expandRules({...rule, delta_window:'12h'})` → `'12h'` faengt die
Konstante — **bleibt aber gruen**, wenn `saveEdit()` weiterhin einen Parameter uebergibt.
Der Kontext sagt es selbst: „Bausteintests beweisen die `.svelte`-Verdrahtung NICHT."

**Darum muss das Durchreichen ein AC auf Verdrahtungsebene sein:** im Staging-Browser eine
Bestandsregel mit einem Zeitfenster ungleich 6h bearbeiten, speichern, neu laden — das
Fenster hat ueberlebt. Nur diese Strecke bewacht das Datenversprechen an der Stelle, an der
es **wirkt**. Der Bausteintest allein ist vakuum-sicher.

## Open Questions

Keine. E-1, E-2, E-3 sind entschieden; M-1 bis M-4 sind gemessen. Die Spec kann direkt
geschrieben werden.

## Nachtrag zu M-4: was mit der 20/6h-Zusicherung passiert

`gewitter-absolutregel-gesperrt.spec.ts:199-200` (`toHaveValue('20')` / `toHaveValue('6h')`)
ist heute die **Browser-Zusicherung fuer `newDefaultRule()`** aus Schritt 1 (AC-7): eine
neu angelegte Regel startet mit Δ 20 / 6 Stunden.

Nach Schritt 2 ist dieser Vorgabewert im Browser **strukturell nicht mehr messbar** — das
Feld, das ihn angezeigt hat, existiert nicht mehr. Das ist **keine Gate-Erosion**, sondern
die unvermeidliche Folge des Rueckbaus: `newDefaultRule()` schreibt 20/6h unveraendert
weiter (siehe „Affected Files": `alertRuleDefaults.ts` — `newDefaultRule()` **unveraendert**).

**Der Nachweis wandert** nach `__tests__/alertRegelNurAenderung.test.ts:54` bzw. `:91`, wo
`r.threshold === 20` und `r.delta_window === '6h'` bereits heute geprueft werden. Die
Bausteinebene ist hier die **einzig moegliche** Ebene, nicht die bequeme — das gehoert so
in die Spec, damit der Adversary die entfallenen E2E-Zeilen als Absicht und nicht als
stillschweigend fallengelassene Zusicherung liest.
