---
entity_id: rework_2276_s6b_wetter_metriken
type: refactor
created: 2026-09-21
updated: 2026-09-21
status: draft
version: "1.0"
tags: [compare, wetter-metriken, wertprops, ratsche, refactor]
---

# Stundenverlauf-Bedienfläche auf Wertprops (Issue #2276, Scheibe S6b, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Scheibe **S6b** von #2276 (Epic #2345) stellt `CompareHourlyLayoutControls.svelte`
vom Zustandsobjekt `wiz` (Compare-Wizard-Bus) auf reine **Wertprops +
Änderungs-Rückrufe** um — Weg (c) der S6-Analyse, exakt nach dem Muster des
bereits live gesetzten Geschwisters `CompareOutlookLayoutControls.svelte`
(#1720 S1). Zusätzlich fällt die stromabwärts liegende Redundanz
`WeatherMetricsTab.svelte:1273`, wodurch die 68er-HERKUNFT-Ratsche
(`docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md`) auf 67 sinkt.
`WeatherMetricsTab` selbst behält `wiz` — das ist eine andere Scheibe.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte`,
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`,
  `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`,
  `frontend/src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts`,
  `frontend/e2e/compare-stundenverlauf-wertprops.spec.ts` (neu),
  `.github/ci_e2e_specs.txt`
- **Identifier:** `CompareHourlyLayoutControls` (Props `metricKeys`, `enabled`,
  Rückrufe `onMetricKeys`, `onEnabledChange`; tote Prop `onHourlyCommit`
  entfällt), `WeatherMetricsTab.svelte:1466-1476` (Mount-Block),
  `WeatherMetricsTab.svelte:1273` (`$effect`-Guard, wird verkürzt)

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`). Kein Go-API- und kein Python-Core-Code in
dieser Scheibe.

## Nicht in dieser Scheibe

- **`WeatherMetricsTab` behält `wiz`.** Die Umstellung des Elternteils ist
  eine andere Scheibe — dort liegen ~30 `wiz`-Zugriffe über fünf Belange
  (`activeMetricKeys`, `outlook*`, `officialAlertsEnabled`, `dayWindow*`,
  Speicherweg). Alle zugleich zu heben ist keine Scheibe, sondern das Epic.
- Die HERKUNFT-Zweige **#23** (`WeatherMetricsTab.svelte:545`), **#24**
  (`:560`), **#26** (`:589`) und **#27** (`:602`) bleiben: #23/#24 sind
  trip-seitig (Vorbefüllung, Katalog-Fetch über `load()`) und fallen nur mit
  der Trip-Hälfte; #26/#27 sind vergleich-seitige **Ladepfad**-Zweige mit
  trip-seitigem Zwillingspaar (#24/#27 füllen dasselbe Feld `catalog` aus
  unterschiedlichen Quellen) — eines allein zu entfernen ändert Verhalten,
  beide zu vereinheitlichen fasst die Trip-Hälfte an.
- **#67 (`weatherMetricsCompareSave.ts:534`) bleibt bewusst.** Er ist durch
  die freigegebene **AC-13 aus S4** geschützt
  (`weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts:74-82`,
  Testname „die Kontext-Prüfung allein entscheidet";
  `docs/specs/modules/rework_2276_s4_wetter_metriken.md:296-305`,
  Mutations-Gegenprobe dort: „Kontext-Prüfung entfernen ⇒ Test rot"). Die
  Kontext-Prüfung im Prädikat ist keine Redundanz, sondern eine bewusst
  gesetzte **zweite Barriere** gegen kontextfremde Speicherung — dieselbe
  Risikoklasse, die CLAUDE.md unter Mandanten-/Datenisolation führt. Wer sie
  aufheben will, braucht ein Nachfolge-ADR bzw. eine ersetzende AC, keinen
  Refactoring-Nebeneffekt. S6b räumt sie **nicht** ab.
- Die fachlichen Zweige **#29** (`WeatherMetricsTab.svelte:1323`,
  Markup-Gabelung) und **#68**/**#69**
  (`weather-metrics-tab/weatherMetricsTabSections.ts:72/73`) bleiben —
  echter Sachunterschied, nicht Eigentum.
- Der Speicherweg von `/compare/new` wird nicht angefasst (kein Vorgriff auf
  #2277).
- Die `activeMetricKeys`-Teilung zwischen `WeatherMetricsTab`,
  `CorridorEditor(+Mobile)` und `AlarmeTab` liegt außerhalb — der
  Aufrufgraph zeigt, dass `CompareHourlyLayoutControls` dieses Feld
  nirgends anfasst (nur `hourlyMetricKeys`/`hourlyEnabled`).

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte` | MODIFY | `wiz` raus, Wertprops (`metricKeys`, `enabled`) + Rückrufe (`onMetricKeys`, `onEnabledChange`) rein, nach dem Muster von `CompareOutlookLayoutControls.svelte`; tote Prop `onHourlyCommit` (`:59`) entfällt |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Mount-Block `:1466-1476` liefert die Wertprops aus `wiz` (Adapter analog `:1226-1238`, Bauform des Outlook-Mounts `:1487-1505`); `$effect`-Guard `:1273` zeilentreu auf `if (!vergleichSpeicherung) return;` verkürzt; Prädikat-Aufruf `:1261` unverändert |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | `WeatherMetricsTab.svelte:1273` **bewusst** aus `EINGEFROREN` streichen, `EINGEFROREN_SOLL_ANZAHL` 68 → 67, Begründung in der Commit-Nachricht — im selben Commit wie der Rückbau von `:1273` |
| `frontend/src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts` | MODIFY | Zeile 1084-1093: einzige `wiz`-Fixture des Kindes (`wiz: { hourlyMetricKeys: null }`), auf die neuen Wertprops umstellen |
| `frontend/e2e/compare-stundenverlauf-wertprops.spec.ts` | CREATE | Verhaltensnachweis der Wertprop-Verdrahtung im Browser (Metrikauswahl, Ein/Aus-Schalter, Speichern) |
| `.github/ci_e2e_specs.txt` | MODIFY | Aufnahme **nur** der neuen Spec, mit Filter-B-Beleg — ohne Eintrag läuft die Spec nicht in der CI-Ampel (`e2e` ist positivgelistet) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Ratschen-Zahl 68 → 67 dokumentarisch nachführen |

## Estimated Scope

- **LoC:** ~+120/−60 (Kind ~60 Zeilen Umbau, Elternteil ~30 Adapter/Mount,
  Ratsche + Fixture-Anpassung ~30). Netto ~+90 produktiv.
- **Files:** 2 produktive Svelte-Dateien
  (`frontend/src/lib/components/`), plus Ratschen-Test, Fixture-Test,
  eine neue E2E-Spec und die CI-Positivliste (alles Testdateien, zählen
  nicht gegen das LoC-Limit).
- **Effort:** low–medium.
- **Risk Level:** MITTEL. Nach unten: exakter, lebender Präzedenzfall im
  selben Block derselben Datei; kein Speicherweg, kein Datenmodell, keine
  Mandantentrennung berührt; keine Signaturänderung nach außen (alle
  Wertprops sind compare-intern, keine neue Pflicht-Prop an
  `WeatherMetricsTab`, die vier Trip-Mounts bleiben unangetastet). Nach
  oben: die Wirkorte sind `$effect`/Prop-Verdrahtung, die der SSR-Harness
  (`generate: 'server'`, kein DOM) nicht sieht — ohne die bestellte
  E2E-Spec wäre die Scheibe nur scheinbar bewiesen.
- 🔴 **Kein LoC-Override nötig.** Das LoC-Limit zählt nur produktive
  Spec-Dateien; `workflow.py status` steht beim Zuschnitt dieser Scheibe bei
  `+0`. Eine frühere Kontext-Warnung „LoC-Limit wird sicher gerissen"
  stammte aus der Fassung vor der Verengung des Schnitts (Elternteil
  unangetastet) und ist überholt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareOutlookLayoutControls.svelte` (#1720 S1) | component | Lebender Präzedenzfall für Weg (c) — Kunstgriffe „Prop da → Bedienelement da" und Vokabular-Normalisierung, hier direkt übernommen |
| `weatherMetricsCompareSave.ts:534` (Prädikat #67) | function | Bleibt bewusst unangetastet — geschützt durch AC-13 aus S4, erzeugt `vergleichSpeicherung`, auf dem der verkürzte Guard `:1273` aufbaut |
| `docs/specs/modules/rework_2276_s4_wetter_metriken.md` (AC-13) | spec | Begründet, warum #67 keine Redundanz ist — Voraussetzung für AC-4 dieser Spec |
| `shared/__tests__/compare_hourly_layout_controls_structure.test.ts:458-474` | test | AST-Wächter: genau eine Einbettung + `compareCatalog`-Attribut — harte Randbedingung für den Mount-Umbau |
| `shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts:196-210` | test | AST-Wächter: `catalog`-Attribut am Mount — zweite harte Randbedingung |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | test | Die 68er-Ratsche selbst, wird in dieser Scheibe auf 67 nachgeführt |
| `docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md` | spec | Ratschen-Vertrag: „eine Zeile → eine Zeile", Streich-Pflicht statt automatischem Nachzug (`docs/reference/gates_und_ratschen.md:326-330`) |

## Implementation Details

### Design-Entscheidungen

1. 🔴 **Zwei getrennte Wirkungen, zwei getrennte ACs — niemals koppeln.**
   Die Umstellung des Kindes `CompareHourlyLayoutControls.svelte` auf
   Wertprops bewegt die 68er-Ratsche **um null**, weil das Kind null
   `context`-Verzweigungen besitzt. Nur der Rückbau der stromabwärts
   liegenden Redundanz `WeatherMetricsTab.svelte:1273` bewegt sie um eins
   (68 → 67). Eine AC, die beides verknüpft („die Umstellung senkt die
   Ratsche auf 67"), ist sachlich falsch und bricht im Adversary — deshalb
   sind AC-1 (Wertprop-Umstellung) und AC-5 (Ratschen-Nachführung) getrennte
   Zusicherungen mit getrennten Mutationen.
2. `CompareHourlyLayoutControls` wird nach dem Muster von
   `CompareOutlookLayoutControls` umgebaut; die beiden Kunstgriffe des
   Präzedenzfalls werden übernommen: **„Prop da → Bedienelement da"** statt
   Herkunfts-Zweig (Vorbild `CompareOutlookLayoutControls.svelte:211-227`)
   und die Vokabular-Normalisierung im Inneren, falls Kennungen zwischen
   Compare-Katalog und Trip-Nomenklatur zu übersetzen sind.
3. Im Elternteil werden die zwei Adapterfunktionen ergänzt (Muster
   `:1226-1238`) und der Mount-Block `:1466-1476` auf die Bauform des
   Outlook-Blocks `:1487-1505` gebracht. Das `&& wiz` im `{#if}` wird zum
   Prop-da-Guard.
4. Erst danach, als **eigener** Schritt mit eigener AC (AC-4/AC-5):
   `:1273` zeilentreu verkürzen und die Ratsche im **selben** Commit von 68
   auf 67 nachführen, mit Begründung in der Commit-Nachricht. Das ist
   **kein** „Nachziehen" im Sinne des Verbots — Nachziehen wäre, die Liste
   aus dem Verzeichnis neu zu erzeugen; hier wird ein einzelner, belegt
   beseitigter Eintrag bewusst gestrichen
   (`docs/reference/gates_und_ratschen.md:326-330`).

### Zwei AST-Wächter über dem Mount-Block (harte Randbedingung für `/50`)

- `shared/__tests__/compare_hourly_layout_controls_structure.test.ts:458-474`
  fordert **genau eine** Einbettung von `CompareHourlyLayoutControls` in
  `WeatherMetricsTab` **und** das Attribut `compareCatalog`.
- `shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts:196-210`
  fordert ebenfalls das `catalog`-Attribut am Mount.

Der Umbau von `WeatherMetricsTab.svelte:1466-1476` muss also
`catalog={compareCatalog}` erhalten und darf keine zweite Einbettung
erzeugen. Die Adapter-Props treten **zusätzlich** hinzu — genau wie der
Outlook-Mount `:1496-1505` es vormacht. Beide Wächter bleiben unter dieser
Bauform grün.

## Expected Behavior

- **Input:** Im Stundenverlauf-Reiter des Ortsvergleichs werden Metriken
  aus- und abgewählt und der Ein/Aus-Schalter bedient — wie heute.
- **Output:** Dieselbe sichtbare Auswahl, dieselbe Speicherung; keine
  Nutzer-sichtbare Verhaltensänderung. Intern liest/schreibt das Kind keine
  `wiz`-Referenz mehr, sondern ausschließlich die neuen Wertprops und
  Rückrufe.
- **Side effects:** Der Guard `WeatherMetricsTab.svelte:1273` prüft
  Kontext/Wizard-Vorhandensein nicht mehr direkt, sondern ausschließlich
  über `vergleichSpeicherung` (Prädikat #67) — semantisch identisch, weil
  `vergleichSpeicherung` bereits `null` ist, sobald eine der Bedingungen
  fehlt.

## Acceptance Criteria

- **AC-1 (Kind ist wertprop-rein):** Given `CompareHourlyLayoutControls.svelte`
  hat heute 5 `wiz`-Zugriffsstellen (`:82`, `:97-98`, `:108`, `:176`, `:194`)
  und die tote Prop `onHourlyCommit` (`:59`) / When die Komponente auf reine
  Wertprops (`metricKeys`, `enabled`) + Rückrufe (`onMetricKeys`,
  `onEnabledChange`) umgestellt wird, nach dem Kunstgriff „Prop da →
  Bedienelement da" / Then enthält die Komponente keine `wiz`-Referenz mehr,
  `onHourlyCommit` ist entfernt, und der Ein/Aus-Schalter wird nur
  gerendert, wenn `onEnabledChange` übergeben wird.
  - Nachweisschicht: Kern (Build/Typecheck bleibt grün; bestehender
    Struktur-Wächter `compare_hourly_layout_controls_structure.test.ts`
    bleibt grün) — die Rendering-Bedingung selbst ist nur im Browser
    messbar, siehe AC-2.
  - Mutations-Gegenprobe: Rückruf `onEnabledChange` im Mount weglassen ⇒
    die neue Spec `compare-stundenverlauf-wertprops.spec.ts` (AC-2) wird
    rot, weil der Ein/Aus-Schalter im DOM fehlt; kein Kern-Test fängt das,
    weil der SSR-Harness (`generate: 'server'`, kein DOM) diesen Wirkort
    nie sieht.

- **AC-2 (Verhaltensgleichheit im Browser):** Given vor der Umstellung
  wirken Metrik-Auswahl/-Abwahl und Ein/Aus-Schalter im Stundenverlauf-Tab
  des Ortsvergleichs und werden gespeichert / When derselbe Ablauf nach der
  Umstellung im Browser gegen Staging durchgeführt wird / Then bleibt das
  Verhalten unverändert: Metriken lassen sich wählen/abwählen, der Schalter
  wirkt, die Auswahl übersteht Speichern/Reload.
  - Nachweisschicht: Live-E2E (**neue Spec**
    `frontend/e2e/compare-stundenverlauf-wertprops.spec.ts`, Eintrag in
    `.github/ci_e2e_specs.txt` mit Filter-B-Beleg — ohne Eintrag läuft die
    Spec nicht in der CI-Ampel, `e2e` ist positivgelistet).
  - Mutations-Gegenprobe: Rückruf `onMetricKeys` im Mount-Block weglassen ⇒
    genau diese neue Spec wird rot (Metrikauswahl bleibt ohne Wirkung); kein
    Kern-Test bemerkt es, weil kein Kern-Test den Mount-Block im Browser
    ausführt.

- **AC-3 (Mount-Block bleibt wächterkonform):** Given die zwei bestehenden
  AST-Wächter `compare_hourly_layout_controls_structure.test.ts:458-474`
  (genau eine Einbettung + Attribut `compareCatalog`) und
  `weather_metrics_tab_compare_catalog_fetch.test.ts:196-210` (Attribut
  `catalog`) / When der Mount-Block `WeatherMetricsTab.svelte:1466-1476` auf
  die neuen Wertprops umgebaut wird (Adapter analog Outlook-Mount
  `:1487-1505`) / Then bleibt `catalog={compareCatalog}` erhalten, es
  entsteht keine zweite Einbettung, beide Wächter bleiben grün.
  - Nachweisschicht: Kern (`node --test` auf beide genannten Testdateien).
  - Mutations-Gegenprobe: `catalog={compareCatalog}` aus dem Mount-Block
    entfernen ⇒ `weather_metrics_tab_compare_catalog_fetch.test.ts` wird
    rot; eine zweite Einbettung von `CompareHourlyLayoutControls` einfügen
    ⇒ `compare_hourly_layout_controls_structure.test.ts` wird rot.

- **AC-4 (Rückbau `:1273` zeilentreu):** Given
  `WeatherMetricsTab.svelte:1273` lautet heute
  `if (context !== 'vergleich' || !wiz || !vergleichSpeicherung) return;`,
  wobei `vergleichSpeicherung` ausschließlich über das durch AC-13 (S4)
  geschützte Prädikat #67 entsteht und `null` ist, sobald eine seiner
  Bedingungen fehlt / When die Zeile zeilentreu (eine Zeile → eine Zeile) zu
  `if (!vergleichSpeicherung) return;` verkürzt wird / Then ist das
  Verhalten des Speicherpfads unverändert, weil `context` und `wiz` bereits
  im Prädikat geprüft werden, das `vergleichSpeicherung` erzeugt.
  - Nachweisschicht: Live-E2E (dieselbe Spec wie AC-2 deckt den Speicherpfad
    ab — der Guard wirkt im Speicherpfad, der SSR-Harness sieht ihn nicht)
    + Kern (bestehende Speicher-Tests aus S4,
    `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts`, bleiben
    grün).
  - Mutations-Gegenprobe: `:1273` auf `if (false) return;` verfälschen ⇒
    die AC-2-Spec (Speichern nach Metrikwahl) wird rot, weil dann nie
    gespeichert wird; kein Kern-Test fängt das, weil die Zusicherung an der
    Stelle wirkt, an der sie greift (Speicherpfad), nicht dort, wo der
    Guard-Quelltext steht.

- **AC-5 (Ratsche 68 → 67, bewusst gepflegt):** Given
  `context_herkunft_zweige_eingefroren.test.ts` hält heute `EINGEFROREN` mit
  68 Einträgen, `EINGEFROREN_SOLL_ANZAHL = 68`, und
  `'WeatherMetricsTab.svelte:1273'` steht in der Liste (Zeile 101) / When der
  Eintrag im **selben** Commit wie der Rückbau (AC-4) bewusst aus
  `EINGEFROREN` gestrichen und `EINGEFROREN_SOLL_ANZAHL` auf 67 gesetzt
  wird, mit Begründung in der Commit-Nachricht / Then ist der Ratschen-Test
  grün, und kein zweiter Eintrag musste angefasst werden.
  - Nachweisschicht: Kern (`node --test` auf
    `context_herkunft_zweige_eingefroren.test.ts`).
  - Mutations-Gegenprobe: Einen weiteren, nicht in AC-4 beseitigten Eintrag
    zusätzlich aus `EINGEFROREN` streichen ⇒ der reale Zählbefehl liefert
    diesen Eintrag weiterhin, der Mengenvergleich schlägt fehl (Ist-Menge
    enthält einen Eintrag, der nicht in der Soll-Liste steht) — Beleg
    dafür, dass „eine Zeile → eine Zeile" verletzt wurde.

- **AC-6 (Außen-Baseline hält — strukturelle Ratsche, kein
  Verhaltensnachweis):** Given der Zählbefehl
  `grep -rn 'context ===\|context !==' frontend/src --include='*.svelte' --include='*.ts' | grep -v '/shared/' | grep -v __tests__ | grep -vE ':\s*(\*|//|/\*)'`
  liefert heute 3 Treffer, alle in
  `lib/components/organisms/MetricsEditorContextBar.svelte:53/60/94`, und
  **null** in `compare/`/`compare-new/` / When die Umstellung abgeschlossen
  ist / Then liefert derselbe Befehl unverändert 3 Treffer gesamt und
  weiterhin **null** in `compare/`/`compare-new/`.
  - Nachweisschicht: Kern (Zählbefehl als Testschritt ausgeführt). 🔴 Diese
    AC ist eine **strukturelle Ratsche**, kein Verhaltensnachweis — sie
    stellt sicher, dass die Umstellung keine `context`-Verzweigung ins
    Elternteil oder an eine Mount-Stelle verschiebt. Der Verhaltensbeleg für
    die Umstellung selbst ist AC-2.
  - Mutations-Gegenprobe: Im Mount-Block von `WeatherMetricsTab` künstlich
    `context === 'vergleich'` als Bedingung für eine der neuen
    Adapterfunktionen einfügen ⇒ der Zählbefehl liefert einen zusätzlichen
    Treffer in `compare/` ⇒ diese AC schlägt fehl (Baseline verletzt).

## Known Limitations

- **Doppelquelle als Dauerzustand ist verboten.** „Wertprop wenn da, sonst
  `wiz`" ist genau das Anti-Muster, das S6 beseitigen soll — nur unter
  neuem Namen. Die Umstellung ist vollständig oder unterbleibt.
- **Der Präzedenzfall verschiebt `wiz`-Zugriffe nachweislich ins
  Elternteil, wo die 68er-Ratsche nicht misst** (sie zählt nur `shared/`,
  nicht `compare/`/`compare-new/`). Deshalb ist die Außen-Baseline aus
  AC-6 Pflicht, nicht optional.
- **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`
  zurück** — `/70-deploy` überspringt dann die gesamte
  Staging-Validierung. Nach **jedem** Commit dieser Scheibe gegenlesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Weg (c) (Wertprops statt `wiz`) ist mit
  `CompareOutlookLayoutControls` (#1720 S1) bereits entschieden und seitdem
  live — diese Scheibe wendet dasselbe, bereits akzeptierte Muster auf ein
  zweites, strukturell identisches Kind an und trifft keine neue
  Architekturentscheidung.

## Changelog

- 2026-09-21: Initial spec created (Scheibe S6b von #2276, Epic #2345)
