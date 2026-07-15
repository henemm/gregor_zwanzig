// TDD GREEN (war RED, Phase 6 implementiert) — Issue #1256 Scheibe 4:
// Editor-Tab "Layout" konsumiert den geteilten LayoutTab-Organism
// (context="vergleich") DIREKT statt über die Step4Layout-Hülle;
// Step3Idealwerte.svelte (Totcode) und Step4Layout.svelte (redundante
// Hülle, KL-4) sind entfernt.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 4 (AC-8–AC-11)
// Soll-Wiring (JSX): claude-code-handoff/current/jsx/screen-compare-editor.jsx:337
//   <LayoutTab context="vergleich" pickedIds={pickedIds}/>
//
// IST-BEFUND aus der RED-Phase (Spec-Phase-Annahme war stale, s. Bericht):
// der geteilte Organism war NICHT unverdrahtet — Step4Layout.svelte mountete
// ihn bereits intern. Der tatsächliche Rest-Gap war daher kleiner als
// "Scheibe 4 Verifizierte Ausgangslage" behauptete: CompareEditor.svelte
// überspringt die Step4Layout-Hülle jetzt (mountet LayoutTab direkt über ein
// gemeinsames {#snippet ltLayoutSection()}, Muster `versandActivationBanner`
// weiter oben in derselben Datei), der Organism selbst wurde nicht neu
// gebaut. AC-9/AC-10 sind daher als Regressionsanker unten separat markiert
// — sie sichern die Datenanbindung (pickedIds/idealRanges) ab.
//
// Source-Inspection-Tests (KEIN Mock, KEIN jsdom-Mount — Projekt-Idiom, siehe
// corridorEditorMobile.test.ts / issue_683_wizard_remove.test.ts / StageDateField.test.ts):
// Svelte-5-Komponenten mit Snippet-Props sind ohne @testing-library/svelte
// (nicht in package.json) in diesem Test-Setup nicht mountbar — echtes DOM-
// Verhalten wird ergänzend über Playwright (compare-flow-navigation.spec.ts)
// gegen Staging abgesichert.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_editor_layout_tab_wiring.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> compare
const COMPARE_DIR = join(here, '..');
// __tests__ -> compare -> components -> lib -> src
const SRC_DIR = join(here, '..', '..', '..', '..');

const COMPARE_EDITOR = join(COMPARE_DIR, 'CompareEditor.svelte');
const STEP3_FILE = join(COMPARE_DIR, 'steps', 'Step3Idealwerte.svelte');
const STEP4_FILE = join(COMPARE_DIR, 'steps', 'Step4Layout.svelte');
const LT_COMPARE_PREVIEW = join(
	SRC_DIR,
	'lib',
	'components',
	'shared',
	'layout-tab',
	'LTComparePreview.svelte'
);

function readCompareEditor(): string {
	return readFileSync(COMPARE_EDITOR, 'utf-8');
}

function readLtComparePreview(): string {
	return readFileSync(LT_COMPARE_PREVIEW, 'utf-8');
}

/** Extrahiert die beiden {:else if activeTab === 'layout'}…-Branches (Desktop + Mobile).
 *
 * Issue #1258 Scheibe S4: seit die Station "alarme" ZWEI weitere
 * `{:else if activeTab === 'layout'}`-Vorkommen im Floating-CTA-Label-Block
 * (Desktop-Fuß-Btn + Mobile-Btn-Label-Kette) um ein `{:else if activeTab ===
 * 'alarme'}` ergänzt hat, matcht die reine "gefolgt von {:else if}"-Heuristik
 * dort ungewollt mit (vorher terminierten diese Ketten in `{/if}`, jetzt in
 * einem weiteren `{:else if}`). Die zusätzliche Filterung auf tatsächliche
 * Layout-Tab-PANEL-Branches (rendern `ltLayoutSection` direkt oder via
 * `<LayoutTab context="vergleich">`) grenzt die CTA-Label-Ketten korrekt aus —
 * das ist der eigentliche AC-8-Prüfgegenstand ("Layout-Tab-Branches" im Sinne
 * von "Panel, das den LayoutTab-Organism mountet"), keine Aufweichung. */
function layoutTabBranches(src: string): string[] {
	const all = [...src.matchAll(/activeTab === 'layout'\}([\s\S]*?)\{:else if/g)].map((m) => m[1]);
	return all.filter((b) => /ltLayoutSection|<LayoutTab\b/.test(b));
}

/**
 * Löst `{@render <name>()}`-Indirektion auf: Desktop- und Mobile-Branch
 * dürfen (DRY, Muster `versandActivationBanner`-Snippet weiter oben in
 * derselben Datei) auf ein GEMEINSAMES Top-Level-Snippet verweisen statt das
 * Markup zu duplizieren. Für die Wiring-Prüfung zählt der TATSÄCHLICHE
 * Inhalt des referenzierten Snippets, nicht nur der Branch-Text selbst.
 */
function resolveRenderedContent(src: string, branch: string): string {
	const renderMatch = branch.match(/\{@render\s+(\w+)\(\)\}/);
	if (!renderMatch) return branch;
	const snippetName = renderMatch[1];
	const snippetMatch = src.match(
		new RegExp(`\\{#snippet ${snippetName}\\(\\)\\}([\\s\\S]*?)\\{\\/snippet\\}`)
	);
	return snippetMatch ? snippetMatch[1] : branch;
}

function collectSourceFiles(dir: string): string[] {
	const results: string[] = [];
	if (!existsSync(dir)) return results;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		const st = statSync(full);
		if (st.isDirectory()) {
			results.push(...collectSourceFiles(full));
		} else if (/\.(svelte|ts|js)$/.test(entry)) {
			results.push(full);
		}
	}
	return results;
}

// =============================================================================
// AC-8: CompareEditor mountet <LayoutTab context="vergleich"> statt <Step4Layout/>
// (Desktop UND Mobile, CompareEditor.svelte:741/912)
// =============================================================================

describe('AC-8: Editor-Tab "Layout" (Desktop + Mobile) mountet LayoutTab context="vergleich" direkt', () => {
	test('genau 2 Layout-Tab-Branches gefunden (Desktop + Mobile)', () => {
		const branches = layoutTabBranches(readCompareEditor());
		assert.equal(
			branches.length,
			2,
			'Erwartet genau 2 Vorkommen von "activeTab === \'layout\'" (Desktop-Zweig + Mobile-Zweig)'
		);
	});

	test('KEIN Branch verwendet mehr <Step4Layout/>', () => {
		const branches = layoutTabBranches(readCompareEditor());
		const offenders = branches.filter((b) => /<Step4Layout\b/.test(b));
		assert.equal(
			offenders.length,
			0,
			`${offenders.length} von ${branches.length} Layout-Tab-Branches mounten noch <Step4Layout/> — muss durch direktes <LayoutTab context="vergleich"> ersetzt werden`
		);
	});

	test('BEIDE Branches mounten <LayoutTab context="vergleich"> direkt oder via gemeinsamem Snippet', () => {
		const src = readCompareEditor();
		const branches = layoutTabBranches(src);
		const withOrganism = branches.filter((b) =>
			/<LayoutTab\s+context="vergleich"/.test(resolveRenderedContent(src, b))
		);
		assert.equal(
			withOrganism.length,
			2,
			`Erwartet 2 Branches mit <LayoutTab context="vergleich"> (direkt oder via {@render}-Snippet), gefunden: ${withOrganism.length}`
		);
	});
});

// =============================================================================
// AC-8/AC-9 Datenanbindung: der Layout-Tab-Branch muss wiz.pickedIds
// (Orte-Auswahl) weiterreichen — sonst zeigt die Vorschau nach dem Wegfall
// der Step4Layout-Hülle stille Dummy-Daten statt der echten Auswahl.
// =============================================================================

describe('AC-9 Datenanbindung: Layout-Tab-Branch verdrahtet die echte Orte-Auswahl (wiz.pickedIds) weiter', () => {
	test('mindestens ein Branch referenziert wiz.pickedIds direkt oder via gemeinsamem Snippet', () => {
		const src = readCompareEditor();
		const branches = layoutTabBranches(src);
		const withPickedIds = branches.filter((b) => /wiz\.pickedIds/.test(resolveRenderedContent(src, b)));
		assert.ok(
			withPickedIds.length > 0,
			'Kein Layout-Tab-Branch referenziert wiz.pickedIds direkt — Vorschau würde nach Entfernen der Step4Layout-Hülle die Orte-Auswahl verlieren'
		);
	});
});

// =============================================================================
// AC-11: Step3Idealwerte.svelte (215 LoC Totcode) ist gelöscht
// =============================================================================

describe('AC-11: Step3Idealwerte.svelte (Totcode, seit #1231 Slice 4/5 unbenutzt) ist gelöscht', () => {
	test('Datei existiert nicht mehr (Totcode geloescht, 235 LoC)', () => {
		assert.strictEqual(
			existsSync(STEP3_FILE),
			false,
			`Step3Idealwerte.svelte muss gelöscht sein (Idealwerte laufen vollständig über CorridorEditor context="vergleich"), existiert aber noch: ${STEP3_FILE}`
		);
	});
});

// =============================================================================
// Scheibe-4-Dateiliste + KL-4: Step4Layout.svelte wird NACH erfolgreicher
// Migration gelöscht, sofern kein anderer Konsument mehr existiert (Grep-
// Nachweis vor Löschung — hier als 0-Konsumenten-Test formuliert).
// =============================================================================

describe('KL-4 / Scheibe-4-Dateiliste: Step4Layout.svelte ist nach der Migration gelöscht', () => {
	// KL-4-Grep-Nachweis (vor der Löschung galt: CompareEditor.svelte war der
	// EINZIGE produktive Konsument von Step4Layout.svelte, Import + 2 Tags,
	// Zeilen 31/742/913) — nach der Migration (Phase 6) ist der Nachweis
	// erbracht, daher jetzt als stabiler Regressionstest formuliert: 0
	// Konsumenten. Eine bloße Prosa-Erwähnung in einem Kommentar (z. B.
	// OutputLayoutEditor.svelte:5, stale Referenz auf ein längst entferntes
	// gleichnamiges Trip-Wizard-Pendant) zählt nicht als Konsument (enger
	// gefasst als reine Substring-Suche, Muster issue_683_wizard_remove.test.ts).
	test('0 produktive Konsumenten von Step4Layout.svelte (Migration abgeschlossen, Datei gelöscht)', () => {
		const files = collectSourceFiles(SRC_DIR).filter(
			(f) => !f.includes('__tests__') && !/\.test\.(ts|js)$/.test(f) && f !== STEP4_FILE
		);
		const consumers = files.filter((f) => {
			const content = readFileSync(f, 'utf-8');
			return /import[^;]*Step4Layout\.svelte/.test(content) || /<Step4Layout[\s/>]/.test(content);
		});
		const shortPaths = consumers.map((f) => f.replace(SRC_DIR + '/', ''));
		assert.deepStrictEqual(
			shortPaths,
			[],
			`Erwartet 0 produktive Konsumenten von Step4Layout.svelte nach der Migration, gefunden: ${shortPaths.join(', ')}`
		);
	});

	test('Datei existiert nicht mehr (redundante Huelle geloescht, 387 LoC)', () => {
		assert.strictEqual(
			existsSync(STEP4_FILE),
			false,
			`Step4Layout.svelte muss nach der Direktverdrahtung gelöscht sein (redundante Hülle um LayoutTab), existiert aber noch: ${STEP4_FILE}`
		);
	});
});

// =============================================================================
// Statischer Grep: keine produktiven Importe/Tags der gelöschten Step-Dateien
// mehr (Muster: issue_683_wizard_remove.test.ts — Import-Statement ODER
// JSX/Svelte-Tag, Testdateien ausgenommen).
// =============================================================================

describe('Statischer Grep: 0 produktive Importe/Tags von Step3Idealwerte/Step4Layout', () => {
	test('keine Produktionsdatei importiert oder instanziiert Step3Idealwerte.svelte mehr', () => {
		const files = collectSourceFiles(SRC_DIR);
		const hits: string[] = [];
		for (const f of files) {
			if (f.includes('__tests__') || /\.test\.(ts|js)$/.test(f)) continue;
			const content = readFileSync(f, 'utf-8');
			const hasImport = /import[^;]*Step3Idealwerte\.svelte/.test(content);
			const hasTag = /<Step3Idealwerte[\s/>]/.test(content);
			if (hasImport || hasTag) hits.push(f.replace(SRC_DIR + '/', ''));
		}
		assert.deepStrictEqual(
			hits,
			[],
			`Folgende Produktionsdateien importieren/instanziieren noch Step3Idealwerte:\n  ${hits.join('\n  ')}`
		);
	});

	test('keine Produktionsdatei importiert oder instanziiert Step4Layout.svelte mehr', () => {
		const files = collectSourceFiles(SRC_DIR);
		const hits: string[] = [];
		for (const f of files) {
			if (f.includes('__tests__') || /\.test\.(ts|js)$/.test(f)) continue;
			const content = readFileSync(f, 'utf-8');
			const hasImport = /import[^;]*Step4Layout\.svelte/.test(content);
			const hasTag = /<Step4Layout[\s/>]/.test(content);
			if (hasImport || hasTag) hits.push(f.replace(SRC_DIR + '/', ''));
		}
		assert.deepStrictEqual(
			hits,
			[],
			`Folgende Produktionsdateien importieren/instanziieren noch Step4Layout:\n  ${hits.join('\n  ')}`
		);
	});
});

// =============================================================================
// REGRESSIONSANKER (bereits heute grün): AC-9/AC-10-Inhalt existiert schon in
// LTComparePreview.svelte, weil Step4Layout den Organism intern bereits
// mountet. Diese Tests werden NICHT rot erwartet — sie sichern gegen
// Rückschritt ab, wenn die Step4Layout-Hülle in Scheibe 4 entfernt wird.
// =============================================================================

describe('Regressionsanker AC-9: neutrale Orts-Vergleich-Vorschau bereits vorhanden (Kein Ranking, grüne Idealbereich-Zelle)', () => {
	test('"Kein Ranking"-Copy ist im Vorschau-Markup vorhanden', () => {
		// Whitespace-normalisiert (Template bricht "Kein"/"Ranking." über zwei
		// Zeilen um — im Browser durch HTML-Whitespace-Kollaps ein Leerzeichen,
		// im rohen Quelltext ein Zeilenumbruch, analog StageDateField.test.ts).
		const normalized = readLtComparePreview().replace(/\s+/g, ' ');
		assert.ok(
			normalized.includes('Kein Ranking'),
			'LTComparePreview.svelte muss die Neutralitäts-Copy "Kein Ranking" enthalten (Constraint 1)'
		);
	});

	test('lt-good-cell-Klasse für Idealbereich-Markierung ist vorhanden', () => {
		assert.ok(
			readLtComparePreview().includes('lt-good-cell'),
			'LTComparePreview.svelte muss die grüne Idealbereich-Markierung (lt-good-cell) rendern'
		);
	});

	test('Tabellen-Header rendert Orte als Spalten (th mit lt-th-ort) statt Orte als Zeilen', () => {
		assert.ok(
			readLtComparePreview().includes('lt-th-ort'),
			'LTComparePreview.svelte muss Orte als Tabellen-SPALTEN rendern (kein Zeilen-Layout)'
		);
	});
});

describe('Regressionsanker AC-10: Telegram-Kappungs-Formel "Label + N Orte = X Spalten (max 8)" bereits vorhanden', () => {
	test('Footer-Template enthält exakt die Soll-Formulierung', () => {
		const src = readLtComparePreview();
		assert.ok(
			src.includes('Label + ${realOrteCount} Orte = ${orteCols} Spalten (max ${CHANNEL_COL_BUDGET.telegram})'),
			'LTComparePreview.svelte muss die Telegram-Kappungsformel "Label + N Orte = X Spalten (max 8)" rendern'
		);
	});
});

describe('Regressionsanker: SMS-Zeichenbudget (≤140) mit Live-Zähler bereits vorhanden', () => {
	test('SMS-Branch zeigt einen echten Zeichenzähler ({smsBody.length} Zeichen)', () => {
		const src = readLtComparePreview();
		assert.ok(
			src.includes('{smsBody.length} Zeichen'),
			'LTComparePreview.svelte muss die SMS-Zeichenzahl live anzeigen'
		);
		assert.ok(
			src.includes('≤ 140 Z.'),
			'LTComparePreview.svelte muss das SMS-Zeichenbudget (≤140) im Eyebrow-Text nennen'
		);
	});
});

// =============================================================================
// Fix-Loop 1 (Adversary F001, HIGH): der Katalog-Fetch (+ der channelLayouts-
// Rewrite-$effect) darf NICHT unbedingt bei jedem Editor-Mount laufen — im
// Original Step4Layout.svelte war onMount an das LAZY MOUNTEN des Tab-Inhalts
// gebunden (feuerte nur bei activeTab === 'layout'). Ein unbedingter
// onMount() im Editor-Top-Level würde bei JEDEM Öffnen eines bestehenden
// Vergleichs (unabhängig vom besuchten Tab) 3 API-Calls auslösen und
// wiz.channelLayouts überschreiben — dessen Server-Roundtrip-JSON weicht
// strukturell von der initial.layouts-Baseline (Zeilen 122/159) ab, was einen
// falschen "Ungespeichert"-Zustand direkt beim Öffnen auslöst (Fund: Adversary
// F001, Code-Timing-Diff gegen HEAD 3e2c17af).
// =============================================================================

describe('Fix-Loop 1 (F001): Katalog-Fetch ist an den Layout-Tab-Besuch gekoppelt, kein unbedingter onMount', () => {
	test('KEIN onMount(async …) mehr für den Katalog-/Templates-/Presets-Fetch', () => {
		const src = readCompareEditor();
		assert.ok(
			!/onMount\(async/.test(src),
			'CompareEditor.svelte darf keinen onMount(async …)-Block mehr enthalten — der Katalog-Fetch lief dort unbedingt bei jedem Mount (F001-Root-Cause)'
		);
	});

	test('/api/metrics wird aus einer eigenständigen async-Funktion (ltLoadCatalog) geladen, nicht direkt in onMount', () => {
		const src = readCompareEditor();
		assert.match(
			src,
			/async function ltLoadCatalog\(\)[^{]*\{[\s\S]{0,400}?\/api\/metrics/,
			'Der Katalog-Fetch muss in einer benannten async-Funktion (ltLoadCatalog) stecken, die gezielt getriggert werden kann'
		);
	});

	test('ein $effect gated ltLoadCatalog() auf activeTab === \'layout\' (einmalig, mit Start-Guard)', () => {
		const src = readCompareEditor();
		assert.match(
			src,
			/\$effect\(\(\) => \{[\s\S]{0,200}?activeTab === 'layout'[\s\S]{0,200}?ltLoadCatalog\(\)/,
			'Es muss einen $effect geben, der ltLoadCatalog() nur bei activeTab === \'layout\' aufruft'
		);
		assert.ok(
			/ltCatalogLoadStarted/.test(src),
			'Ein Start-Guard (z. B. ltCatalogLoadStarted) muss verhindern, dass der Fetch bei jedem erneuten Tab-Wechsel zurück auf "layout" wiederholt wird'
		);
	});

	test('der channelLayouts-Rewrite-$effect bleibt hinter ltLoading gated (unverändert, Regressionsanker)', () => {
		const src = readCompareEditor();
		assert.match(
			src,
			/\$effect\(\(\) => \{\s*\n\s*if \(ltLoading \|\| Object\.keys\(ltCatalog\)\.length === 0\) return;/,
			'Der channelLayouts-Rewrite-Effect muss weiterhin früh zurückkehren, solange der Katalog nicht geladen ist (verhindert Schreiben leerer Buckets)'
		);
	});
});
