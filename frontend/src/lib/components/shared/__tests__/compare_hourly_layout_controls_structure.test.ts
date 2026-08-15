// TDD RED — Issue #1406 Scheibe B (Epic #1372 / Etappe E2 von #1435).
//
// Der Stundenverlauf-Auswahlblock (`CompareHourlyLayoutControls.svelte`) zeigt
// heute die flache Zehnerliste `{#each ALL_HOURLY_METRICS as metric}` aus dem
// Compare-eigenen Vokabular. Er soll dieselbe Bauart bekommen wie Uebersicht
// (#1411) und Ausblick (#1406 Scheibe A): eine Zeile je Wettergroesse aus
// `groupCompareCatalog(catalog)`, gespeist aus derselben Katalogantwort
// (GET /api/compare/metrics).
//
// Spec: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md
//   § Implementation Details 2+4, AC-1
// Vorbild dieses Umschriebs: compare_outlook_metric_selection_structure.test.ts
// (Scheibe A). Die Vorfassung dieser Datei (Epic #1301 F2a AC-7 + #1401b AC-2)
// wies die alte Schleife nach und bricht mit dieser Scheibe strukturell — sie
// wird umgeschrieben, nicht geloescht (Spec Known Limitations).
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst die Komponenten mit dem ECHTEN
// Svelte-5-Compiler und inspiziert Template-/Instance-Script-AST statt eines
// verbotenen Dateiinhalt-Vergleichs.
//
// Die Zahl der Zeilen (24 Wettergroessen aus 26 Katalog-Eintraegen) ist hier
// strukturell nicht beweisbar — der Katalog kommt zur Laufzeit vom Server.
// Sie wird in der Python-Haelfte behauptet und geprueft
// (tests/unit/test_compare_hourly_catalog_columns.py::
// test_hour_columns_cover_every_catalog_metric_except_the_merge_signal).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/compare_hourly_layout_controls_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', 'CompareHourlyLayoutControls.svelte');
const OVERVIEW_COMPONENT = join(here, '..', 'WeatherMetricsTab.svelte');

function parseComponent(path: string): any {
	const src = readFileSync(path, 'utf-8');
	return parse(src, { modern: true });
}

// ─── generische AST-Helfer (uebernommen aus compare_outlook_metric_selection_structure.test.ts) ───

function findEachBlocksOverCall(subtree: unknown, calleeName: string, argName: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'EachBlock' && n.expression?.type === 'CallExpression') {
			const callee = n.expression.callee;
			const args = n.expression.arguments ?? [];
			if (
				callee?.type === 'Identifier' &&
				callee.name === calleeName &&
				args.length >= 1 &&
				args[0]?.type === 'Identifier' &&
				args[0].name === argName
			) {
				found.push(n);
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

function findEachBlocksOverIdentifier(subtree: unknown, identifierName: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (
			n.type === 'EachBlock' &&
			n.expression?.type === 'Identifier' &&
			n.expression.name === identifierName
		) {
			found.push(n);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

function findComponentsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && n.name === name) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

function findAllAttributesNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Attribute' && n.name === name) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

function findAttr(node: any, name: string): any {
	return (node?.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === name);
}

/** Sucht rekursiv im Ausdruck eines Attributwerts. */
function visitAttributeExpressions(attr: any, visitor: (node: unknown) => void): void {
	if (!attr) return;
	const value = attr.value;
	if (Array.isArray(value)) {
		for (const part of value) if (part?.type === 'ExpressionTag') visitor(part.expression);
	} else if (value?.type === 'ExpressionTag') {
		visitor(value.expression);
	}
}

/** Referenziert der Attributwert (in welcher Notation auch immer) den Zugriff
 *  `objectName.propertyName`? */
function attributeReferencesMember(attr: any, objectName: string, propertyName: string): boolean {
	let hit = false;
	function visitExpr(node: unknown): void {
		if (hit || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visitExpr);
			return;
		}
		const n = node as Record<string, any>;
		if (
			n.type === 'MemberExpression' &&
			n.object?.type === 'Identifier' &&
			n.object.name === objectName &&
			n.property?.type === 'Identifier' &&
			n.property.name === propertyName &&
			!n.computed
		) {
			hit = true;
			return;
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent' || key === 'loc') continue;
			visitExpr(n[key]);
		}
	}
	visitAttributeExpressions(attr, visitExpr);
	return hit;
}

function attributeReferencesIdentifier(attr: any, identifierName: string): boolean {
	let hit = false;
	function visitExpr(node: unknown): void {
		if (hit || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visitExpr);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Identifier' && n.name === identifierName) {
			hit = true;
			return;
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent' || key === 'loc') continue;
			visitExpr(n[key]);
		}
	}
	visitAttributeExpressions(attr, visitExpr);
	return hit;
}

function renderedTestids(subtree: unknown): string[] {
	return findAllAttributesNamed(subtree, 'data-testid')
		.concat(findAllAttributesNamed(subtree, 'testid'))
		.map((attr: any) => {
			const value = attr.value;
			return Array.isArray(value)
				? value.map((v: any) => v.raw ?? v.data ?? '{expr}').join('')
				: (value?.raw ?? '{expr}');
		});
}

function instanceBody(ast: any): any[] {
	return (ast?.instance?.content?.body as any[]) ?? [];
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-1: Der Auswahl-Block iteriert den Katalog, nicht die eigene Zehnerliste
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-1: Stundenverlauf-Auswahl kommt aus groupCompareCatalog(catalog)', () => {
	test('CompareHourlyLayoutControls.svelte enthaelt `{#each groupCompareCatalog(catalog) as group}`', () => {
		const ast = parseComponent(COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(
			eachBlocks.length >= 1,
			'AC-1 FAIL (RED): CompareHourlyLayoutControls.svelte iteriert noch nicht ueber ' +
				'`groupCompareCatalog(catalog)` — der Auswahl-Block zeigt weiterhin die flache ' +
				'Zehnerliste aus dem Compare-eigenen Vokabular.'
		);
	});

	test('die alte flache Zehnerliste `{#each ALL_HOURLY_METRICS}` ist verschwunden', () => {
		const ast = parseComponent(COMPONENT);
		const alt = findEachBlocksOverIdentifier(ast.fragment, 'ALL_HOURLY_METRICS');
		assert.equal(
			alt.length,
			0,
			'AC-1 FAIL (RED): die Komponente iteriert weiterhin ueber `ALL_HOURLY_METRICS` — ' +
				'das eigenstaendige Zehner-Vokabular lebt neben dem Katalog weiter.'
		);
	});

	test('Anti-Hand-Kopie: der Instance-Script importiert groupCompareCatalog statt eigener Gruppierung', () => {
		const ast = parseComponent(COMPONENT);
		const imports = instanceBody(ast).filter((stmt) => stmt.type === 'ImportDeclaration');
		const hit = imports.some(
			(imp) =>
				String(imp.source?.value ?? '').includes('compareAggregationGrouping') &&
				(imp.specifiers ?? []).some(
					(s: any) =>
						s.imported?.name === 'groupCompareCatalog' ||
						s.local?.name === 'groupCompareCatalog'
				)
		);
		assert.ok(
			hit,
			'AC-1 FAIL (RED): kein Import von `groupCompareCatalog` aus `compareAggregationGrouping.ts` ' +
				'— Gefahr eines zweiten, eigenen Gruppierungs-Codes statt Wiederverwendung des ' +
				'#1411-Bausteins.'
		);
	});

	test('je Gruppe eine Zeile, die an `group.metric_id` haengt (nicht am Auswertungs-Schluessel)', () => {
		// Der Stundenverlauf speichert die WETTERGROESSE, nicht eine Tages-
		// Auswertung: `group.options[0].key` waere `temp_max_c` und damit ein
		// Schluessel, den der Stunden-Aufloeser gar nicht kennt (Spec
		// Implementation Details 1: alter Kurzschluessel ODER Katalog-ID).
		const ast = parseComponent(COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-1 FAIL (RED): kein groupCompareCatalog-Block (s.o.).');
		if (eachBlocks.length === 0) return;

		const testids = eachBlocks.flatMap((block) =>
			findAllAttributesNamed(block.body, 'data-testid').concat(
				findAllAttributesNamed(block.body, 'testid')
			)
		);
		assert.ok(testids.length >= 1, 'AC-1 FAIL (RED): keine Testids im Gruppierungs-Block.');
		assert.ok(
			testids.some((attr) => attributeReferencesMember(attr, 'group', 'metric_id')),
			'AC-1 FAIL (RED): keine Metrik-Zeile im Gruppierungs-Block, deren Testid auf ' +
				'`group.metric_id` verweist.'
		);
	});

	test('die Beschriftung kommt aus `group.label` (Registername des Katalogs)', () => {
		const ast = parseComponent(COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-1 FAIL (RED): kein groupCompareCatalog-Block (s.o.).');
		if (eachBlocks.length === 0) return;

		const labelAttrs = eachBlocks.flatMap((block) => findAllAttributesNamed(block.body, 'label'));
		const labelTags: any[] = [];
		(function collectExpressionTags(node: unknown): void {
			if (node === null || typeof node !== 'object') return;
			if (Array.isArray(node)) {
				node.forEach(collectExpressionTags);
				return;
			}
			const n = node as Record<string, any>;
			if (n.type === 'ExpressionTag') labelTags.push(n);
			for (const key of Object.keys(n)) {
				if (key === 'parent') continue;
				collectExpressionTags(n[key]);
			}
		})(eachBlocks.map((b) => b.body));

		const viaAttribut = labelAttrs.some((attr) =>
			attributeReferencesMember(attr, 'group', 'label')
		);
		const viaText = labelTags.some(
			(tag) =>
				tag.expression?.type === 'MemberExpression' &&
				tag.expression.object?.name === 'group' &&
				tag.expression.property?.name === 'label'
		);
		assert.ok(
			viaAttribut || viaText,
			'AC-1 FAIL (RED): die Zeilenbeschriftung im Gruppierungs-Block kommt nicht aus ' +
				'`group.label` — sie stammt vermutlich noch aus einer eigenen Uebersetzungstabelle ' +
				'(compareHourlyCatalogIds.ts).'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-11: „Sonnenstunden" steht sichtbar und begruendet als nicht anwaehlbar da
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-11: ausgenommene Groesse ist sichtbar, nicht anwaehlbar und begruendet', () => {
	test('die Zeile wird nicht weggefiltert — es gibt keinen Filter vor dem Gruppierungs-Block', () => {
		// AC-11 verlangt ausdruecklich "nicht kommentarlos fehlend". Ein
		// `.filter(...)` zwischen `groupCompareCatalog(catalog)` und der
		// Schleife wuerde die Zeile verschwinden lassen; der EachBlock-Test
		// oben verlangt deshalb bereits den EXAKTEN Aufruf ohne Zwischenschritt.
		// Hier zusaetzlich die Gegenprobe auf ein `{#if}` im Schleifenkoerper,
		// das die ganze Zeile unterdrueckt.
		const ast = parseComponent(COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-11 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		// Jede Gruppe muss eine Zeile ergeben: es gibt mindestens ein Testid im
		// Schleifenkoerper, das NICHT in einem IfBlock steckt.
		let ausserhalbIf = 0;
		function visit(node: unknown, imIf: boolean): void {
			if (node === null || typeof node !== 'object') return;
			if (Array.isArray(node)) {
				node.forEach((n) => visit(n, imIf));
				return;
			}
			const n = node as Record<string, any>;
			const jetztImIf = imIf || n.type === 'IfBlock';
			if (n.type === 'Attribute' && (n.name === 'data-testid' || n.name === 'testid') && !jetztImIf) {
				ausserhalbIf += 1;
			}
			for (const key of Object.keys(n)) {
				if (key === 'parent') continue;
				visit(n[key], jetztImIf);
			}
		}
		eachBlocks.forEach((block) => visit(block.body, false));
		assert.ok(
			ausserhalbIf >= 1,
			'AC-11 FAIL (RED): jede Zeile des Gruppierungs-Blocks steckt in einem `{#if}` — ' +
				'eine ausgenommene Groesse wuerde dadurch kommentarlos fehlen statt sichtbar ' +
				'und begruendet nicht anwaehlbar zu sein.'
		);
	});

	test('der Zustand „nicht anwaehlbar" kommt je Gruppe aus den Katalogdaten', () => {
		const ast = parseComponent(COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-11 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		const disabledAttrs = eachBlocks.flatMap((block) =>
			findAllAttributesNamed(block.body, 'disabled').concat(
				findAllAttributesNamed(block.body, 'aria-disabled')
			)
		);
		assert.ok(
			disabledAttrs.length >= 1,
			'AC-11 FAIL (RED): keine Zeile im Gruppierungs-Block traegt einen ' +
				'`disabled`/`aria-disabled`-Zustand — „Sonnenstunden" waere anwaehlbar.'
		);
		assert.ok(
			disabledAttrs.some((attr) => attributeReferencesIdentifier(attr, 'group')),
			'AC-11 FAIL (RED): der `disabled`-Zustand haengt nicht an `group` (den ' +
				'Katalogdaten) — er waere entweder pauschal oder im Frontend hartcodiert. ' +
				'Die Ausnahme gehoert ins Register, nicht in die Komponente (AC-10).'
		);
	});

	test('die Begruendung wird je Gruppe aus den Katalogdaten gerendert', () => {
		const ast = parseComponent(COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-11 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		// Ein Ausdruck irgendwo im Schleifenkoerper, der eine ANDERE
		// group-Eigenschaft als metric_id/label/options ausgibt — das ist der
		// Begruendungstext aus der Katalogantwort.
		const bekannt = new Set(['metric_id', 'label', 'options']);
		let begruendung: string | null = null;
		function visit(node: unknown): void {
			if (begruendung || node === null || typeof node !== 'object') return;
			if (Array.isArray(node)) {
				node.forEach(visit);
				return;
			}
			const n = node as Record<string, any>;
			if (
				n.type === 'MemberExpression' &&
				n.object?.type === 'Identifier' &&
				n.object.name === 'group' &&
				n.property?.type === 'Identifier' &&
				!n.computed &&
				!bekannt.has(n.property.name)
			) {
				begruendung = n.property.name;
				return;
			}
			for (const key of Object.keys(n)) {
				if (key === 'parent') continue;
				visit(n[key]);
			}
		}
		eachBlocks.forEach((block) => visit(block.body));

		assert.ok(
			begruendung !== null,
			'AC-11 FAIL (RED): im Gruppierungs-Block wird ausser metric_id/label/options ' +
				'keine weitere `group`-Eigenschaft gelesen — es gibt also weder Zustand noch ' +
				'Begruendungstext aus der Katalogantwort. AC-11 verlangt einen sichtbaren, ' +
				'nicht leeren Hinweis („stuendlich nur als Einstrahlung verfuegbar", Verweis ' +
				'auf Bewoelkung und UV-Index).'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-1: Die Katalogantwort ist DIESELBE wie bei Uebersicht und Ausblick
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-1: der Stundenverlauf wird aus derselben Katalogantwort gespeist', () => {
	test('WeatherMetricsTab.svelte uebergibt CompareHourlyLayoutControls den Compare-Katalog', () => {
		// Heute steht dort `catalog={metricById}` — die Register-Antwort von
		// GET /api/metrics als Objekt, NICHT die flache Compare-Katalogliste,
		// ueber die `groupCompareCatalog()` gruppiert. Ohne diese Umstellung
		// gruppierte der Block ueber die falsche Datenform.
		const ast = parseComponent(OVERVIEW_COMPONENT);
		const mounts = findComponentsNamed(ast.fragment, 'CompareHourlyLayoutControls');
		assert.equal(
			mounts.length,
			1,
			`Erwartet genau eine Einbettung von CompareHourlyLayoutControls, gefunden ${mounts.length}.`
		);
		const catalogAttr = findAttr(mounts[0], 'catalog');
		assert.ok(catalogAttr, 'AC-1 FAIL (RED): der Aufruf uebergibt gar keine `catalog`-Prop.');
		assert.ok(
			attributeReferencesIdentifier(catalogAttr, 'compareCatalog'),
			'AC-1 FAIL (RED): CompareHourlyLayoutControls bekommt nicht `compareCatalog` ' +
				'(GET /api/compare/metrics) uebergeben — dieselbe Quelle, aus der sich Uebersicht ' +
				'und Ausblick speisen.'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// REGRESSIONSSCHUTZ — heute gruen, muss gruen bleiben
// ═══════════════════════════════════════════════════════════════════════════

describe('[REGRESSIONSSCHUTZ] Umgebung des Auswahl-Blocks bleibt unberuehrt', () => {
	test('der "Stundenverlauf ein/aus"-Schalter bleibt erhalten', () => {
		const ast = parseComponent(COMPONENT);
		const ids = renderedTestids(ast.fragment);
		assert.ok(
			ids.includes('compare-layout-hourly-enabled-toggle'),
			`CompareHourlyLayoutControls.svelte rendert "compare-layout-hourly-enabled-toggle" nicht. ` +
				`Gefundene Testids: ${ids.join(', ')}`
		);
	});

	test('der geteilte Reihenfolge-Baustein (WeatherV2Reihenfolge) bleibt genau einmal eingebettet', () => {
		// Spec Implementation Details 4: der Reihenfolge-Block ist ausdruecklich
		// NICHT-UMFANG dieser Scheibe (ADR-0024, bereits geteilt).
		const ast = parseComponent(COMPONENT);
		const rows = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
		assert.equal(
			rows.length,
			1,
			`REGRESSION: erwartet genau einen WeatherV2Reihenfolge-Aufruf, gefunden ${rows.length}.`
		);
	});

	// Issue #1719 S3 (Adversary-Fund F001, BROKEN): "Aus ist ein Zustand" gilt
	// NUR fuer den Trip-Kanal-Reiter (WeatherMetricsTab.svelte, route-Kontext)
	// — diese Einbettung arbeitet auf einem flachen Array ohne Kanal-Ebene und
	// hat bereits einen funktionierenden Rueckweg (Checkbox darueber).
	// `offColumns`/`onRestore` sind OPTIONALE Props ohne Vorgabewert — die
	// Naht ist die PROP-ANWESENHEIT (Spec Abschnitt 1), nicht ein
	// `context`-String. Werden sie hier durchgereicht, entsteht eine
	// ungewollte Aus-Gruppe im Ortsvergleich (AC-13-Verstoss).
	test('WeatherV2Reihenfolge bekommt WEDER offColumns NOCH onRestore uebergeben', () => {
		const ast = parseComponent(COMPONENT);
		const rows = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
		assert.equal(rows.length, 1, `REGRESSION: erwartet genau einen WeatherV2Reihenfolge-Aufruf, gefunden ${rows.length}.`);
		const row = rows[0];
		assert.equal(
			findAttr(row, 'offColumns'),
			undefined,
			'AC-13 FAIL: der Stundenverlauf-Aufruf von WeatherV2Reihenfolge uebergibt jetzt `offColumns` — ' +
				'das erzeugt eine Aus-Gruppe im Ortsvergleich, wo ADR-0050 Regel 4 nicht gilt.'
		);
		assert.equal(
			findAttr(row, 'onRestore'),
			undefined,
			'AC-13 FAIL: der Stundenverlauf-Aufruf von WeatherV2Reihenfolge uebergibt jetzt `onRestore` — ' +
				'siehe offColumns-Befund oben, dieselbe Naht.'
		);
	});

	test('der Hinweis "Erscheint nur in der E-Mail" bleibt stehen', () => {
		const ast = parseComponent(COMPONENT);
		const ids = renderedTestids(ast.fragment);
		assert.ok(
			ids.includes('compare-layout-hourly-email-only-hint'),
			'REGRESSION: der E-Mail-only-Hinweis ist verschwunden (Stundenverlauf erreicht ' +
				'weiterhin nur die E-Mail, Spec Known Limitations).'
		);
	});
});
