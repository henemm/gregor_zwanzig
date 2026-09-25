// Ratsche fuer Issue #2276 Scheibe S6a (Epic #2345) — AC-2 und AC-3.
// Spec: docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md
//
// ZWECK
// -----
// Friert die Zahl UND die Fundorte der `context ===`/`context !==`-
// Verzweigungen unter `frontend/src/lib/components/shared/` als benannte
// `Datei:Zeile`-Liste ein. Erst damit laesst sich in S6b–S6f nachweisen, dass
// eine HERKUNFT-Verzweigung wirklich ENTFERNT statt nur verschoben wurde —
// eine bloße Zahl wuerde ein Verschieben nicht von einem Entfernen
// unterscheiden.
//
// KEIN VERZEICHNIS-SCAN FUER DIE SOLL-SEITE. Die Soll-Liste unten ist
// eingefrorene Literal-Daten. Wuerde der Waechter seine Soll-Menge zur
// Laufzeit selbst aus dem Verzeichnis herleiten, waere er vakuum-gruen: ein
// versehentliches Leeren der Ist-Liste wuerde ihn nicht scheitern lassen
// (bekanntes Muster, Memory
// `ratsche_leeren_macht_den_abhaengigen_test_vakuum_gruen`). Gemessen wird
// deshalb Soll (Literal) gegen Ist (echter Zaehlbefehl) — in BEIDEN
// Richtungen.
//
// 🔴 STAND S6c (Issue #2276): der Zeilenzahl-Vertrag unten gilt fuer
// `AlarmeTab.svelte` in DIESER Scheibe NICHT — dort werden 14 Eintraege bewusst
// gestrichen und 4 auf neue Zeilennummern nachgefuehrt. Begruendung und genaue
// Auflage: Kommentar an `EINGEFROREN` weiter unten.
//
// 🔴 STAND S6d (Issue #2276): dieselbe Ausnahme gilt ZUSAETZLICH fuer
// `corridor-editor/CorridorEditor.svelte` und
// `corridor-editor/CorridorEditorMobile.svelte` — dort werden 6 Eintraege
// gestrichen und 22 auf neue Zeilennummern nachgefuehrt, per
// `BLEIBT_MIT_INHALT` inhaltlich gefesselt.
//
// 🔴 STAND S6e (Issue #2276, Spec `rework_2276_s6e_versand.md`,
// Design-Entscheidung 5): die Ausnahme gilt ZUSAETZLICH fuer
// `VersandTab.svelte` — mit ANDERER Bilanz als S6c/S6d: 0 Eintraege werden
// gestrichen, genau die drei in RED unter `VersandTab.svelte:284/294/330`
// gefuehrten Eintraege (der Wirkort-Guard des Selbst-Speicher-Effekts und die
// Markup-Weiche `{#if context === 'route'} … {:else if context ===
// 'vergleich'}` selbst) sind in GREEN gemessen auf `:348/358/394`
// nachgefuehrt und per `BLEIBT_MIT_INHALT` inhaltlich gefesselt. Grund: der
// Umbau auf Wertprops fuegt im SCRIPT-Teil
// (acht Wertprops + drei Legacy-Lesewerte + neun Rueckrufe) mehr Zeilen hinzu,
// als er entfernt — die drei Zeilennummern verschieben sich nach unten, ohne
// dass sich an der Bedingung selbst etwas aendert. TDD RED (diese Scheibe)
// setzt NUR diese Vertragserweiterung; die neu gemessenen Zeilennummern samt
// `BLEIBT_MIT_INHALT`-Eintraegen traegt GREEN nach (Muster S6d). Deshalb bleibt
// `EINGEFROREN_SOLL_ANZAHL` unveraendert bei 47 — anders als bei S6c/S6d
// aendert S6e die Gesamtzahl nicht.
//
// 🔴 STAND S6g (Issue #2276, Spec `rework_2276_s6g_wetter_metriken_wertprops.md`,
// Design-Entscheidung 8): die Ausnahme gilt ZUSAETZLICH fuer
// `WeatherMetricsTab.svelte` — Bilanz wie S6e: 0 Eintraege werden gestrichen,
// die fuenf bestehenden Eintraege `WeatherMetricsTab.svelte:545/560/589/602/1323`
// (die `context === 'route'`/`context === 'vergleich'`-Bedingungen und die
// Markup-Gabelung) werden in GREEN auf ihre neu gemessenen Zeilennummern
// nachgefuehrt und per `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext
// inhaltlich gefesselt. Grund: die zehn Wertprops + neun Rueckrufe im
// SCRIPT-Teil liegen alle OBERHALB dieser Zeilen — ihre Verschiebung nach
// unten ist eine reine Positionsfolge, kein Verhaltensbefund. TDD RED (diese
// Scheibe) setzt NUR diese Vertragserweiterung; die neuen Zeilennummern samt
// `BLEIBT_MIT_INHALT`-Eintraegen traegt GREEN nach (Muster S6d/S6e).
// `weather-metrics-tab/weatherMetricsCompareSave.ts:534` bleibt AUF SEINER
// ZEILE (alter, positionsbasierter Vertrag); die Textaenderung dort
// (`!!p.wiz` -> `!!p.zustand`) bekommt bewusst KEINE Fesselung (Spec,
// Design-Entscheidung 6/9). `EINGEFROREN_SOLL_ANZAHL` bleibt bei 47.
//
// TDD RED (Stand `73f504c9`)
// -------------------------
// Beim Stand vor S6a liefert der Zaehlbefehl 69 Fundstellen. Die eingefrorene
// Soll-Liste hat 68 Eintraege: `WeatherMetricsTab.svelte:577` fehlt darin
// absichtlich, weil AC-1 dieser Scheibe genau diese TOTE Bedingung entfernt
// (`(context === 'vergleich' || context === 'route')` ist fuer beide Werte des
// Union-Typs wahr). Der Test ist deshalb VOR der Implementierung ROT mit
// „Ist-Eintrag zusaetzlich: WeatherMetricsTab.svelte:577" und wird GRUEN,
// sobald der Rueckbau erfolgt ist.
//
// 🔴 VERTRAG AN DIE IMPLEMENTIERUNG (S6a, /50): Die Kommentar-Bereinigung der
// sieben `buildHubPutPayload`-Nennungen ist eine ERSETZUNG AN ORT UND STELLE,
// NIEMALS ein Loeschen von Zeilen. Dasselbe gilt fuer den Kommentarblock
// oberhalb der toten Bedingung in `WeatherMetricsTab.svelte` und fuer die
// Ersetzung der toten Bedingung selbst (eine Zeile -> eine Zeile). Grund:
// unterhalb dieser Stellen liegen weitere eingefrorene Fundstellen
// (`WeatherMetricsTab.svelte:589/602/1273/1323`,
// `weather-metrics-tab/weatherMetricsCompareSave.ts:534`,
// `versandVergleichSpeicherung.ts:221`,
// `corridor-editor/wertebereicheVergleichSpeicherung.ts:200`), deren
// Zeilennummern sonst verrutschen. Wird dieser Waechter waehrend `/50` rot:
// die Zeilenzahl der bearbeiteten Datei wiederherstellen — NICHT die
// eingefrorene Liste nachziehen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Wurzel der Messflaeche — relativ zur EIGENEN Testdatei aufgeloest, nie
 *  ueber einen festen Hauptrepo-Pfad (sonst falsches Gruen aus dem Worktree). */
const SHARED = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Eingefrorener Zaehlbefehl aus der Spec, Abschnitt „Eingefrorener
 *  Zaehlbefehl" — wortgleich. Wird mit `SHARED` als cwd ausgefuehrt. */
const ZAEHLBEFEHL =
	`grep -rn 'context ===\\|context !==' . --include='*.svelte' --include='*.ts'` +
	` | grep -v __tests__ | grep -vE ':\\s*(\\*|//|/\\*)'`;

/**
 * Eingefrorene Soll-Liste (47 Fundstellen) — Zielzustand NACH S6a (Totcode),
 * S6b (Guard-Rueckbau) UND S6c (Alarme-Flaeche auf Wertprops). Die Kategorien
 * HERKUNFT/FACHLICH/DARSTELLUNG stehen im Spec-Anhang, nicht hier — diese
 * Ratsche misst Fundorte, nicht Absichten.
 *
 * TDD RED (S6c): solange die 14 in der Schicksals-Tabelle als FAELLT markierten
 * AlarmeTab-Zweige im Quelltext stehen, meldet der Mengenvergleich sie als
 * „zusaetzlich" — das ist der rote Ausgangszustand dieser Scheibe. Gruen wird
 * er, wenn der Vergleichs-Zweig auf Wertprops steht und /50 die vier
 * verbliebenen Eintraege auf ihre NEUEN Zeilennummern nachgefuehrt hat.
 *
 * 🔴 VERTRAG AN S6c /50 — er ERSETZT den Zeilenzahl-Vertrag von S6a/S6b fuer
 * DIESE Scheibe (Spec `rework_2276_s6c_alarme.md`, Design-Entscheidung 1):
 * In `AlarmeTab.svelte` entstehen rund 24 neue Prop-Zeilen OBERHALB aller
 * eingefrorenen Eintraege. Zeilenzahl-Wiederherstellung waere hier Verrenkung,
 * nicht Sorgfalt — deshalb gilt ausnahmsweise:
 *   * die 14 FAELLT-Eintraege werden BEWUSST gestrichen (Begruendung je
 *     Eintrag in der Commit-Nachricht, im selben Commit wie der Rueckbau),
 *   * die 4 BLEIBT-Eintraege werden auf ihre neu gemessenen Zeilennummern
 *     nachgefuehrt — geprueft wird, dass der BEDINGUNGSTEXT derselbe ist
 *     (siehe Kommentar an der Liste), nicht die Position,
 *   * `alarme-tab/alarmeTabSections.ts:27/:38/:42` bleiben unberuehrt; ihre
 *     Zeilennummern duerfen sich NICHT verschieben.
 *
 * 🔴 VERTRAG AN S6d /50 (Spec `rework_2276_s6d_wertebereiche.md`,
 * Design-Entscheidung 5): der Zeilenzahl-Vertrag gilt ZUSAETZLICH NICHT fuer
 * `corridor-editor/CorridorEditor.svelte` und
 * `corridor-editor/CorridorEditorMobile.svelte`. Der Umbau auf Wertprops legt
 * rund 30 Prop-Zeilen OBERHALB aller eingefrorenen Eintraege dieser beiden
 * Dateien an; Zeilenzahl-Wiederherstellung waere hier Verrenkung, nicht
 * Sorgfalt. Deshalb gilt fuer sie:
 *   * die 6 FAELLT-Eintraege (3 Desktop/Mobil-Paare: der `getContext`-Zugriff
 *     selbst und die beiden reinen Quellenwahlen `originalLevels` und
 *     `originalActiveMetricKeys`) werden BEWUSST gestrichen,
 *   * die 22 BLEIBT-Eintraege werden auf ihre neu gemessenen Zeilennummern
 *     nachgefuehrt und sind ALLE in `BLEIBT_MIT_INHALT` gefesselt — geprueft
 *     wird der Bedingungstext, nicht die Position,
 *   * `corridor-editor/corridorEditorState.ts:297` und
 *     `corridor-editor/wertebereicheVergleichSpeicherung.ts:200` bleiben AUF
 *     IHRER ZEILE; fuer sie gilt weiterhin der alte, positionsbasierte
 *     Vertrag. Die Textaenderung an :200 (`!!p.ws` -> `!!p.zustand`) bekommt
 *     bewusst KEINE Fesselung (Spec, Design-Entscheidung 3).
 * 🔴 VERTRAG AN S6e /50 (Spec `rework_2276_s6e_versand.md`, Design-Entscheidung
 * 5): der Zeilenzahl-Vertrag gilt ZUSAETZLICH NICHT fuer `VersandTab.svelte`.
 * Anders als S6c (14/4) und S6d (6/22) aendert sich hier die Gesamtzahl NICHT:
 *   * 0 Eintraege werden gestrichen,
 *   * die drei bestehenden Eintraege (in RED `VersandTab.svelte:284/294/330`,
 *     in GREEN gemessen `:348/358/394` — der Wirkort-Guard des
 *     Selbst-Speicher-Effekts und die Markup-Weiche `{#if context === 'route'}
 *     … {:else if context === 'vergleich'}` selbst) sind auf ihre neu
 *     gemessenen Zeilennummern nachgefuehrt und in `BLEIBT_MIT_INHALT`
 *     gefesselt — geprueft wird der Bedingungstext, nicht die Position,
 *   * `versandVergleichSpeicherung.ts:221` bleibt AUF SEINER ZEILE; fuer sie
 *     gilt weiterhin der alte, positionsbasierte Vertrag. Die Textaenderung an
 *     :221 (`!!p.wiz` -> `!!p.zustand`) bekommt bewusst KEINE Fesselung (Spec,
 *     Design-Entscheidung 4/6).
 * 🔴 VERTRAG AN S6g /50 (Spec `rework_2276_s6g_wetter_metriken_wertprops.md`,
 * Design-Entscheidung 8): der Zeilenzahl-Vertrag gilt ZUSAETZLICH NICHT fuer
 * `WeatherMetricsTab.svelte`. Bilanz wie S6e, die Gesamtzahl bleibt 47:
 *   * 0 Eintraege werden gestrichen,
 *   * die fuenf bestehenden Eintraege (in RED `WeatherMetricsTab.svelte:545/
 *     560/589/602/1323`) werden auf ihre in GREEN neu gemessenen Zeilennummern
 *     nachgefuehrt und in `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext
 *     gefesselt — geprueft wird der Bedingungstext, nicht die Position,
 *   * `weather-metrics-tab/weatherMetricsCompareSave.ts:534` bleibt AUF SEINER
 *     ZEILE; fuer sie gilt weiterhin der alte, positionsbasierte Vertrag. Die
 *     Textaenderung an :534 (`!!p.wiz` -> `!!p.zustand`) bekommt bewusst KEINE
 *     Fesselung (Spec, Design-Entscheidung 6/9).
 *
 * Fuer alle Dateien AUSSERHALB von `AlarmeTab.svelte`, den beiden
 * Corridor-Bausteinen, `VersandTab.svelte` UND `WeatherMetricsTab.svelte` gilt
 * der alte Vertrag unveraendert weiter: verschobene Zeilennummer = Befund, kein
 * Nachtrag.
 */
const EINGEFROREN: readonly string[] = [
	// S6c: von 18 AlarmeTab-Eintraegen bleiben genau diese VIER (Schicksals-
	// Tabelle der Spec). Ihre Zeilennummern verschieben sich durch den Umbau —
	// /50 misst die neuen und traegt sie HIER ein (Bedingungstext woertlich
	// daneben, damit am Inhalt geprueft werden kann, nicht an der Position):
	//   :256  `context === 'vergleich'` — Ableitung `unalertableSelectedMetricNames`
	//         (FACHLICH: route liefert strukturell immer `[]`, #1435 AC-7)
	//   :514  `{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}`
	//         (Anzeige-Zwilling der fachlichen Zusicherung aus :256)
	//   :533  `{#if context === 'vergleich'}` — Kurzstil-Schalter
	//         (DARSTELLUNG: im Trip steht derselbe Schalter im Versand-Reiter, #1260 S5)
	//   :566  `{#if context === 'vergleich'}` — Beispielwarnung
	//         (FACHLICH: Ort- statt Etappen-Subjekt, zwei verschiedene Komponenten)
	'AlarmeTab.svelte:256',
	'AlarmeTab.svelte:514',
	'AlarmeTab.svelte:533',
	'AlarmeTab.svelte:566',
	// S6e: alle DREI VersandTab-Eintraege bleiben (0 gestrichen) — sie sind
	// Wirkort-/Darstellungs-Weichen, kein `wiz`-Symptom. Ihre Zeilennummern
	// verschoben sich durch die elf neuen Prop-Zeilen im Skript-Teil; die neuen
	// sind gemessen und unten in BLEIBT_MIT_INHALT inhaltlich gefesselt.
	'VersandTab.svelte:348',
	'VersandTab.svelte:358',
	'VersandTab.svelte:394',
	'versandVergleichSpeicherung.ts:221',
	'WeatherMetricsTab.svelte:590',
	'WeatherMetricsTab.svelte:605',
	'WeatherMetricsTab.svelte:634',
	'WeatherMetricsTab.svelte:647',
	'WeatherMetricsTab.svelte:1439',
	'versand-tab/vtBriefingChannelsText.ts:21',
	'versand-tab/vtBriefingChannelsText.ts:26',
	// S6d: von 14 Corridor-Paaren bleiben elf (Schicksals-Tabelle der Spec).
	// Ihre Zeilennummern verschieben sich durch den Wertprop-Umbau — die neuen
	// sind gemessen und unten in BLEIBT_MIT_INHALT inhaltlich gefesselt.
	'corridor-editor/CorridorEditorMobile.svelte:144',
	'corridor-editor/CorridorEditorMobile.svelte:172',
	'corridor-editor/CorridorEditorMobile.svelte:197',
	'corridor-editor/CorridorEditorMobile.svelte:252',
	'corridor-editor/CorridorEditorMobile.svelte:279',
	'corridor-editor/CorridorEditorMobile.svelte:342',
	'corridor-editor/CorridorEditorMobile.svelte:355',
	'corridor-editor/CorridorEditorMobile.svelte:358',
	'corridor-editor/CorridorEditorMobile.svelte:363',
	'corridor-editor/CorridorEditorMobile.svelte:375',
	'corridor-editor/CorridorEditorMobile.svelte:496',
	'corridor-editor/CorridorEditor.svelte:141',
	'corridor-editor/CorridorEditor.svelte:184',
	'corridor-editor/CorridorEditor.svelte:216',
	'corridor-editor/CorridorEditor.svelte:285',
	'corridor-editor/CorridorEditor.svelte:313',
	'corridor-editor/CorridorEditor.svelte:347',
	'corridor-editor/CorridorEditor.svelte:360',
	'corridor-editor/CorridorEditor.svelte:363',
	'corridor-editor/CorridorEditor.svelte:369',
	'corridor-editor/CorridorEditor.svelte:390',
	'corridor-editor/CorridorEditor.svelte:519',
	'corridor-editor/corridorEditorState.ts:297',
	'versand-tab/VTSchedulePlan.svelte:55',
	'versand-tab/VTSchedulePlan.svelte:83',
	'alarme-tab/alarmeTabSections.ts:27',
	'alarme-tab/alarmeTabSections.ts:38',
	'alarme-tab/alarmeTabSections.ts:42',
	'corridor-editor/wertebereicheVergleichSpeicherung.ts:200',
	'weather-metrics-tab/weatherMetricsTabSections.ts:72',
	'weather-metrics-tab/weatherMetricsTabSections.ts:73',
	'weather-metrics-tab/weatherMetricsCompareSave.ts:534',
];

/** Erwartete Laenge als zweite, unabhaengige Schranke gegen ein
 *  versehentliches Kuerzen des Literals oben. */
const EINGEFROREN_SOLL_ANZAHL = 47;

/**
 * S6c: die vier ueberlebenden AlarmeTab-Eintraege, GEGEN IHREN INHALT gefesselt.
 *
 * Warum das noetig ist: in S6c verschieben sich ihre Zeilennummern zwangslaeufig
 * (Design-Entscheidung 1 der Spec), die Liste oben wird also nachgefuehrt. Ohne
 * diese Fesselung waere der billigste Weg zu Gruen, einfach die vier Nummern
 * einzutragen, die der Zaehlbefehl gerade ausgibt — dann bewachte die Ratsche
 * nur noch sich selbst. Geprueft wird deshalb: an der eingetragenen Zeile steht
 * WOERTLICH diese Bedingung, und im Fenster darunter steht der Baustein, zu dem
 * sie gehoert. Ein auf eine fremde Verzweigung gesetzter Eintrag faellt damit
 * auf, auch wenn die Mengen stimmen.
 */
const BLEIBT_MIT_INHALT: readonly { eintrag: string; zeile: string; folgt: string }[] = [
	{
		eintrag: 'AlarmeTab.svelte:256',
		zeile: "context === 'vergleich'",
		folgt: 'deriveUnalertableSelectedMetricNames('
	},
	{
		eintrag: 'AlarmeTab.svelte:514',
		zeile: "{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}",
		folgt: 'alarme-unalertable-metrics-hint'
	},
	{
		eintrag: 'AlarmeTab.svelte:533',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'TelegramKurzstilToggle'
	},
	{
		eintrag: 'AlarmeTab.svelte:566',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'VTAlertSample'
	},
	// S6d (Issue #2276): die 22 ueberlebenden Corridor-Eintraege — gemessen am
	// Quelltext NACH dem Wertprop-Umbau. `isFreshCompareCreate` ist der eine
	// Eintrag, dessen TEXT sich mitgeaendert hat (`ws?.isEditMode`/`ws?.corridors`
	// -> Wertprops, Spec Design-Entscheidung 3); die uebrigen zehn Paare tragen
	// ihren Bedingungstext byte-identisch weiter, nur ihre Position verschob sich.
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:141',
		zeile: "const isFreshCompareCreate = context === 'vergleich' && !isEditMode && (corridors ?? []).length === 0;",
		folgt: 'buildComparePrefillRows(profileKey, defs)'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:184',
		zeile: "if (context !== 'vergleich' || compareDefs !== null || compareDefsError) return;",
		folgt: 'loadCompareMetricCatalog()'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:216',
		zeile: "if (context !== 'route' || routeExtraDefs !== null) return;",
		folgt: 'loadRouteExtraMetricDefs()'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:285',
		zeile: "if (context === 'vergleich') {",
		folgt: 'vergleichSpeicherung?.aenderungMelden();'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:313',
		zeile: "const next = context === 'vergleich'",
		folgt: 'addCompareRow(rows, poolLeft'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:347',
		zeile: "{#if context === 'vergleich' && compareDefsError}",
		folgt: 'corridor-editor-vergleich-load-error'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:360',
		zeile: "{:else if context === 'vergleich' && compareDefs === null}",
		folgt: 'corridor-editor-vergleich-loading'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:363',
		zeile: "{:else if context === 'route' && routeExtraDefs === null}",
		folgt: 'corridor-editor-route-loading'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:369',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'class="ce-h2"'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:390',
		zeile: "{#if context === 'route' && routeDefsFailed}",
		folgt: 'corridor-editor-route-load-warning'
	},
	{
		eintrag: 'corridor-editor/CorridorEditor.svelte:519',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'corridor-editor-neutral-hint'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:144',
		zeile: "const isFreshCompareCreate = context === 'vergleich' && !isEditMode && (corridors ?? []).length === 0;",
		folgt: 'buildComparePrefillRows(profileKey, defs)'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:172',
		zeile: "if (context !== 'vergleich' || compareDefs !== null || compareDefsError) return;",
		folgt: 'loadCompareMetricCatalog()'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:197',
		zeile: "if (context !== 'route' || routeExtraDefs !== null) return;",
		folgt: 'loadRouteExtraMetricDefs()'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:252',
		zeile: "if (context === 'vergleich') {",
		folgt: 'vergleichSpeicherung?.aenderungMelden();'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:279',
		zeile: "const next = context === 'vergleich'",
		folgt: 'addCompareRow(rows, poolLeft'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:342',
		zeile: "{#if context === 'vergleich' && compareDefsError}",
		folgt: 'corridor-editor-mobile-vergleich-load-error'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:355',
		zeile: "{:else if context === 'vergleich' && compareDefs === null}",
		folgt: 'corridor-editor-mobile-vergleich-loading'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:358',
		zeile: "{:else if context === 'route' && routeExtraDefs === null}",
		folgt: 'corridor-editor-mobile-route-loading'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:363',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'class="cem-title"'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:375',
		zeile: "{#if context === 'route' && routeDefsFailed}",
		folgt: 'corridor-editor-mobile-route-load-warning'
	},
	{
		eintrag: 'corridor-editor/CorridorEditorMobile.svelte:496',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'corridor-editor-mobile-neutral-hint'
	},
	// S6e (Issue #2276): die drei VersandTab-Eintraege — gemessen am Quelltext
	// NACH dem Wertprop-Umbau. Der Wirkort-Guard im Effekt (:348) traegt seinen
	// Text veraendert weiter (`!wiz` faellt weg, `!vergleichSpeicherung` bleibt);
	// die beiden Markup-Weichen sind byte-identisch, nur nach unten gerutscht.
	// Die `folgt`-Anker unterscheiden die beiden Markup-Zweige bewusst an der
	// E-Mail-Kanalquelle (`send_email` = Trip-$state gegen `sendEmail` =
	// Wertprop): der Rahmen darunter (`versand-tab`-Div, `VTBriefingChannels`)
	// ist in beiden Zweigen gleich und taugte als Anker nicht — ein vertauschtes
	// Paar faende dort seinen Anker und die Fesselung waere wertlos.
	{
		eintrag: 'VersandTab.svelte:348',
		zeile: "if (context !== 'vergleich' || !vergleichSpeicherung) return;",
		folgt: 'versandSnapshotAus(versandZustand);'
	},
	{
		eintrag: 'VersandTab.svelte:358',
		zeile: "{#if context === 'route'}",
		folgt: 'email: send_email,'
	},
	{
		eintrag: 'VersandTab.svelte:394',
		zeile: "{:else if context === 'vergleich'}",
		folgt: 'email: sendEmail ?? false,'
	},
	// S6g (Issue #2276): die fuenf ueberlebenden WeatherMetricsTab-Eintraege —
	// gemessen am Quelltext NACH dem Wertprop-Umbau. Alle fuenf tragen ihren
	// Bedingungstext byte-identisch weiter (Spec Design-Entscheidung 8), nur
	// ihre Position verschob sich nach unten (die zehn neuen Wertprop-Zeilen +
	// neun Rueckruf-Zeilen im Script-Teil liegen oberhalb).
	{
		eintrag: 'WeatherMetricsTab.svelte:590',
		zeile: "if (context === 'route' && trip && catalogLoaded && !isDirty) {",
		folgt: 'normalizeStoredOutlookMetrics('
	},
	{
		eintrag: 'WeatherMetricsTab.svelte:605',
		zeile: "if (context === 'route' && Object.keys(catalog).length === 0) load();",
		folgt: 'Issue #1350 Teil 2: analog dem Route-Guard oben'
	},
	{
		eintrag: 'WeatherMetricsTab.svelte:634',
		zeile: "if (context === 'vergleich' && !smsSymbols) loadSmsSymbols();",
		folgt: '#1401 Scheibe B: der Stundenverlauf beschriftet'
	},
	{
		eintrag: 'WeatherMetricsTab.svelte:647',
		zeile: "if (context === 'vergleich' && Object.keys(catalog).length === 0) {",
		folgt: ".get<MetricCatalog>('/api/metrics')"
	},
	{
		eintrag: 'WeatherMetricsTab.svelte:1439',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'Issue #1311 (C1): Vergleich-Grundauswahl'
	}
];

/** Wie viele Zeilen unter dem Zweig nach dem zugehoerigen Baustein gesucht wird. */
const FENSTER = 8;

/** Reines Mengen-Delta in BEIDEN Richtungen. Bewusst als eigene Funktion, weil
 *  AC-3 verlangt, dass ein FEHLENDER Soll-Eintrag den Waechter genauso rot
 *  macht wie ein ZUSAETZLICHER Ist-Eintrag — eine Einbahn-Pruefung
 *  („jeder Ist-Eintrag steht im Soll") waere blind gegen das Leeren der
 *  Ist-Liste. */
export function vergleicheZweigListen(
	soll: readonly string[],
	ist: readonly string[]
): { fehlt: string[]; zusaetzlich: string[] } {
	const sollMenge = new Set(soll);
	const istMenge = new Set(ist);
	return {
		fehlt: soll.filter((e) => !istMenge.has(e)),
		zusaetzlich: ist.filter((e) => !sollMenge.has(e))
	};
}

/** Fuehrt den eingefrorenen Zaehlbefehl aus und normalisiert auf
 *  `Datei:Zeile`. Bricht ab, wenn eine Ausgabezeile nicht dem erwarteten
 *  `grep -rn`-Format entspricht (Format-Drift wuerde sonst als „alles fehlt"
 *  erscheinen). */
function messeIstListe(): string[] {
	let ausgabe = '';
	try {
		ausgabe = execSync(ZAEHLBEFEHL, {
			cwd: SHARED,
			encoding: 'utf-8',
			shell: '/bin/bash'
		});
	} catch (e) {
		// grep endet mit 1, wenn die Pipeline leer bleibt — dann bleibt `ausgabe`
		// leer und der Mengenvergleich unten schlaegt mit „alles fehlt" fehl.
		ausgabe = (e as { stdout?: string }).stdout ?? '';
	}
	return ausgabe
		.split('\n')
		.filter((z) => z.trim() !== '')
		.map((z) => {
			const m = /^\.\/(.+?):(\d+):/.exec(z);
			assert.ok(m, `Zeile passt nicht zum grep -rn-Format: ${JSON.stringify(z)}`);
			return `${m[1]}:${m[2]}`;
		});
}

describe('AC-2: eingefrorene HERKUNFT-Zweig-Liste deckt sich mit dem Ist-Stand', () => {
	test('Messflaeche ist ueberhaupt erreichbar (Schutz gegen falsches cwd)', () => {
		assert.ok(
			existsSync(join(SHARED, 'AlarmeTab.svelte')),
			`SHARED zeigt nicht auf frontend/src/lib/components/shared (aufgeloest: ${SHARED})`
		);
	});

	test('die eingefrorene Soll-Liste ist unversehrt (47 Eintraege, keine Duplikate)', () => {
		assert.strictEqual(
			EINGEFROREN.length,
			EINGEFROREN_SOLL_ANZAHL,
			'EINGEFROREN wurde gekuerzt oder erweitert, ohne EINGEFROREN_SOLL_ANZAHL nachzufuehren'
		);
		assert.strictEqual(
			new Set(EINGEFROREN).size,
			EINGEFROREN.length,
			'EINGEFROREN enthaelt Duplikate — der Mengenvergleich waere verfaelscht'
		);
	});

	test('Soll und Ist sind mengengleich — kein Eintrag fehlt, keiner kommt hinzu', () => {
		const ist = messeIstListe();
		const { fehlt, zusaetzlich } = vergleicheZweigListen(EINGEFROREN, ist);
		const alsListe = (e: string[]) => (e.length === 0 ? '—' : e.join(', '));
		assert.deepStrictEqual(
			{ fehlt, zusaetzlich },
			{ fehlt: [], zusaetzlich: [] },
			'HERKUNFT-Zweig-Ratsche verletzt.\n' +
				`  Soll (eingefroren): ${EINGEFROREN.length}\n` +
				`  Ist (Zaehlbefehl):  ${ist.length}\n` +
				`  Soll fehlt im Ist (Zeile verschoben oder entfernt): ${alsListe(fehlt)}\n` +
				`  Ist nicht im Soll (neue oder verschobene Verzweigung): ${alsListe(zusaetzlich)}\n` +
				'  Eine ENTFERNTE Verzweigung wird bewusst nachgetragen (Liste kuerzen);\n' +
				'  eine VERSCHOBENE Zeilennummer ist ein Befund, kein Nachtrag.'
		);
	});
});

describe('S6c/S6d/S6e/S6g: jeder gefesselte Eintrag zeigt auf seine eigene Bedingung', () => {
	for (const { eintrag, zeile, folgt } of BLEIBT_MIT_INHALT) {
		test(`${eintrag} traegt weiterhin \`${zeile}\``, () => {
			assert.ok(
				EINGEFROREN.includes(eintrag),
				`Messaufbau kaputt: \`${eintrag}\` steht nicht mehr in EINGEFROREN. Diese ` +
					'Eintraege BLEIBEN (S6c: AlarmeTab, S6d: die beiden Corridor-Bausteine, ' +
					'S6e: VersandTab) — wer ' +
					'einen davon streicht, entfernt eine fachliche oder darstellerische ' +
					'Verzweigung, keine HERKUNFT-Weiche.'
			);
			const [datei, nr] = eintrag.split(':');
			const zeilen = readFileSync(join(SHARED, datei), 'utf-8').split('\n');
			const index = Number(nr) - 1;
			assert.ok(
				index >= 0 && index < zeilen.length,
				`Ratsche verletzt: ${eintrag} zeigt hinter das Dateiende (${zeilen.length} Zeilen).`
			);
			assert.strictEqual(
				zeilen[index].trim(),
				zeile,
				`Ratsche verletzt: an ${eintrag} steht eine ANDERE Bedingung als die eingefrorene. ` +
					'Wurde die Liste nach einer Zeilenverschiebung nur „nachgezogen", zeigt der ' +
					'Eintrag jetzt auf eine fremde Verzweigung — die Mengen stimmen dann, die ' +
					'Aussage nicht mehr. Nachfuehren heisst: die Zeile suchen, die DIESE Bedingung ' +
					'traegt.'
			);
			const fenster = zeilen.slice(index + 1, index + 1 + FENSTER).join('\n');
			assert.ok(
				fenster.includes(folgt),
				`Ratsche verletzt: unter ${eintrag} steht kein \`${folgt}\` mehr. Der Eintrag ` +
					'gehoert damit nicht mehr zu dem Baustein, fuer den er eingefroren wurde.'
			);
		});
	}
});

describe('AC-3: Rueckdreh-Gegenprobe — ein fehlender Soll-Eintrag macht rot', () => {
	// Diese beiden Tests sind bereits in der RED-Phase gruen. Sie pruefen nicht
	// das Feature, sondern die Schutzwirkung der Ratsche selbst: dass der
	// Mengenvergleich BEIDE Richtungen meldet. Ohne sie koennte ein spaeterer
	// Umbau die `fehlt`-Richtung stillschweigend fallen lassen — und genau dann
	// wuerde ein Leeren der Ist-Liste unbemerkt durchgehen.
	// Der eigentliche AC-3-Nachweis ist der Mutations-Lauf im Adversary-Schritt:
	//   1. eine beliebige Zeile aus `EINGEFROREN` oben entfernen,
	//   2. NUR diese Datei laufen lassen,
	//   3. erwartet: genau dieser Waechter rot, kein anderer.

	test('ein aus dem Soll entfernter Eintrag erscheint als „zusaetzlich" im Ist', () => {
		const ist = [...EINGEFROREN];
		const sollGekuerzt = EINGEFROREN.slice(1);
		const { fehlt, zusaetzlich } = vergleicheZweigListen(sollGekuerzt, ist);
		assert.deepStrictEqual(fehlt, []);
		assert.deepStrictEqual(
			zusaetzlich,
			[EINGEFROREN[0]],
			'Das Entfernen einer Zeile aus der eingefrorenen Liste muss den Waechter rot machen'
		);
	});

	test('eine geleerte Ist-Liste meldet alle Soll-Eintraege als fehlend (kein Vakuum-Gruen)', () => {
		const { fehlt, zusaetzlich } = vergleicheZweigListen(EINGEFROREN, []);
		assert.strictEqual(fehlt.length, EINGEFROREN.length);
		assert.deepStrictEqual(zusaetzlich, []);
	});
});
