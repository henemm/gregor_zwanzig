// TDD RED — #1848 A3: der 3-Tages-Ausblick verhaelt sich wie ein Kanal.
//
// Spec: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md
//   Block A (AC-1/AC-2 — die zweite Auswahl verschwindet)
//   Block E (AC-12 — keine Doppelpflege bei der "Aus"-Berechnung)
// Kontext: docs/context/feat-1848-a3-outlook-kanal-modul.md
//   Mutations-Gegenproben M-1 (Schnitt gegen die Grundauswahl entfernt),
//   M-6 (Grundauswahl-Prop nur an einem Mountpunkt).
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Vorbild: compare_outlook_metric_selection_structure.test.ts
// (dieselbe Zieldatei, AC-1..AC-4/AC-8 von #1406/#1848 A2 — die dortigen
// Zusicherungen "die Kaestchenliste existiert und wird so bedient" werden
// durch A3 Block A NICHT durch diese Datei geloescht/geflippt (RED-Auftrag:
// nur die explizit benannte AC-13-Stelle wurde umgedreht), sondern hier
// zusaetzlich durch eine unabhaengige, striktere Anwesenheits-Zusicherung
// ueberholt — s. Abschluss-Bericht des RED-Agenten fuer diesen bekannten,
// von der Spec nicht ausdruecklich adressierten Ueberschneidungs-Konflikt).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/outlook_erbt_grundauswahl_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const OUTLOOK_COMPONENT = join(here, '..', 'CompareOutlookLayoutControls.svelte');
const WEATHER_METRICS_TAB = join(here, '..', 'WeatherMetricsTab.svelte');

function parseComponent(path: string): any {
	const src = readFileSync(path, 'utf-8');
	return parse(src, { modern: true });
}

function walk(node: unknown, visit: (n: Record<string, any>) => void): void {
	if (node === null || typeof node !== 'object') return;
	if (Array.isArray(node)) {
		node.forEach((n) => walk(n, visit));
		return;
	}
	const n = node as Record<string, any>;
	visit(n);
	for (const key of Object.keys(n)) {
		if (key === 'parent') continue;
		walk(n[key], visit);
	}
}

function findElementsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	walk(subtree, (n) => {
		if (n.type === 'RegularElement' && n.name === name) found.push(n);
	});
	return found;
}

function findComponentsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	walk(subtree, (n) => {
		if (n.type === 'Component' && n.name === name) found.push(n);
	});
	return found;
}

function findAttr(node: any, name: string): any {
	return (node?.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === name);
}

function attrIsStaticText(attr: any, expected: string): boolean {
	if (!attr) return false;
	const value = attr.value;
	if (Array.isArray(value)) {
		return value.length === 1 && value[0]?.type === 'Text' && value[0].data === expected;
	}
	return false;
}

function forEachAttributeExpression(attr: any, visit: (expr: unknown) => void): void {
	if (!attr) return;
	const value = attr.value;
	if (Array.isArray(value)) {
		for (const part of value) if (part?.type === 'ExpressionTag') visit(part.expression);
	} else if (value?.type === 'ExpressionTag') {
		visit(value.expression);
	}
}

function attributeReferencesIdentifier(attr: any, identifierName: string): boolean {
	if (!attr) return false;
	let hit = false;
	forEachAttributeExpression(attr, (expr) =>
		walk(expr, (n) => {
			if (n.type === 'Identifier' && n.name === identifierName) hit = true;
		})
	);
	return hit;
}

function instanceBody(ast: any): any[] {
	return (ast?.instance?.content?.body as any[]) ?? [];
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-1: keine zweite Kaestchenliste mehr im Ausblick-Auswahl-Block
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-1 [#1848 A3]: CompareOutlookLayoutControls.svelte zeigt keine eigene Metrik-Kaestchenliste mehr', () => {
	test('kein <input type="checkbox"> mehr im Template — sichtbar bleibt ausschliesslich die Reihenfolge-Liste', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const checkboxInputs = findElementsNamed(ast.fragment, 'input').filter((el) =>
			attrIsStaticText(findAttr(el, 'type'), 'checkbox')
		);
		assert.equal(
			checkboxInputs.length,
			0,
			`AC-1 FAIL (RED): CompareOutlookLayoutControls.svelte enthaelt noch ${checkboxInputs.length} ` +
				'checkbox-<input>-Elemente (die Metrik-Auswahlliste, heute :167-182). Nach Block A der Spec ' +
				'entfaellt die zweite Kaestchenliste ersatzlos — abgewaehlt wird ausschliesslich ueber den ' +
				'"Aus"-Knopf der Reihenfolge-Liste (WeatherV2Reihenfolge), exakt wie bei E-Mail/Telegram/SMS.'
		);
	});

	test('die alte Gruppierungs-Iteration `groupCompareCatalog(catalog)` treibt kein Template-Each-Block mehr an', () => {
		// Nicht die Existenz des Imports (der kann fuer andere Zwecke bleiben),
		// sondern der EACH-BLOCK im Fragment ist die Naht: er erzeugt die
		// Kaestchen-Zeilen. Ohne ihn kann die Liste strukturell nicht mehr
		// bestehen (Gegenprobe zum obigen Checkbox-Zaehler).
		const ast = parseComponent(OUTLOOK_COMPONENT);
		let eachOverGroupCompareCatalog = 0;
		walk(ast.fragment, (n) => {
			if (
				n.type === 'EachBlock' &&
				n.expression?.type === 'CallExpression' &&
				n.expression.callee?.type === 'Identifier' &&
				n.expression.callee.name === 'groupCompareCatalog'
			) {
				eachOverGroupCompareCatalog += 1;
			}
		});
		assert.equal(
			eachOverGroupCompareCatalog,
			0,
			'AC-1 FAIL (RED): es existiert weiterhin ein `{#each groupCompareCatalog(...)}`-Block im Template ' +
				'— die abgeschaffte Kaestchenliste (Mutation M-1: "Schnitt gegen die Grundauswahl in der ' +
				'Zeilenliste entfernen" waere hier gar nicht mehr pruefbar, weil die Liste selbst noch existiert).'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-2 / Mutation M-6: BEIDE Mountpunkte reichen die flaechen-eigene
// Grundauswahl durch — keine einseitige Verdrahtung.
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-2 [#1848 A3]: beide Mountpunkte (Trip UND Ortsvergleich) reichen ihre Grundauswahl an CompareOutlookLayoutControls durch', () => {
	test('WeatherMetricsTab.svelte mountet CompareOutlookLayoutControls genau zweimal, BEIDE mit einer `grundauswahl`-Prop', () => {
		// Technical Approach der Spec ("Teil (a) — Liste begrenzen"): EINE Prop
		// `grundauswahl: string[] | null`, zwei Mountpunkte (Ortsvergleich
		// `:1403`, Trip `:1786`) — die Fallunterscheidung liegt allein im
		// uebergebenen Wert, nicht im Bauteil. M-6: wird die Prop nur an EINEM
		// Mount gesetzt, bleibt die andere Flaeche ungeschnitten.
		const ast = parseComponent(WEATHER_METRICS_TAB);
		const mounts = findComponentsNamed(ast.fragment, 'CompareOutlookLayoutControls');
		assert.equal(
			mounts.length,
			2,
			`Erwartet genau zwei CompareOutlookLayoutControls-Mounts (Ortsvergleich + Trip), gefunden ${mounts.length}.`
		);
		const ohneGrundauswahl = mounts.filter((m) => !findAttr(m, 'grundauswahl'));
		assert.equal(
			ohneGrundauswahl.length,
			0,
			`AC-2 FAIL (RED): ${ohneGrundauswahl.length} von ${mounts.length} Mountpunkten uebergeben keine ` +
				'`grundauswahl`-Prop an CompareOutlookLayoutControls — ohne sie bleibt Teil (a) an dieser ' +
				'Flaeche wirkungslos (M-6: "Grundauswahl-Prop nur am Trip-Mount, nicht am Ortsvergleich-Mount").'
		);
	});

	test('der Ortsvergleich-Mount referenziert die COMPARE-Grundauswahl (materializedActiveMetricKeys), der Trip-Mount die TRIP-Grundauswahl (buckets.primary)', () => {
		const ast = parseComponent(WEATHER_METRICS_TAB);
		const mounts = findComponentsNamed(ast.fragment, 'CompareOutlookLayoutControls');
		assert.ok(mounts.length >= 1, 'Vorbedingung: kein CompareOutlookLayoutControls-Mount gefunden.');

		const referenziertCompareGrundauswahl = mounts.some((m) =>
			attributeReferencesIdentifier(findAttr(m, 'grundauswahl'), 'materializedActiveMetricKeys')
		);
		assert.ok(
			referenziertCompareGrundauswahl,
			'AC-2/AC-6 FAIL (RED): kein Mount uebergibt `grundauswahl={materializedActiveMetricKeys}` — die ' +
				'Ortsvergleich-eigene Grundauswahl (dieselbe Quelle wie die Uebersichts-Kopplung, ' +
				'WeatherMetricsTab.svelte:1083).'
		);
		const referenziertTripGrundauswahl = mounts.some((m) =>
			attributeReferencesIdentifier(findAttr(m, 'grundauswahl'), 'buckets')
		);
		assert.ok(
			referenziertTripGrundauswahl,
			'AC-2/AC-3 FAIL (RED): kein Mount uebergibt eine `grundauswahl`-Prop, die `buckets` referenziert ' +
				'(die Trip-Grundauswahl, WeatherMetricsTab.svelte:221/285 `buckets.primary`).'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-12: die "Aus"-Berechnung benutzt splitChannelMetricsForDisplay() — kein
// zweiter Algorithmus.
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-12 [#1848 A3]: die "Aus"-Berechnung des Ausblicks ruft splitChannelMetricsForDisplay()', () => {
	test('CompareOutlookLayoutControls.svelte importiert splitChannelMetricsForDisplay aus channelMetricLayouts.ts', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const imports = instanceBody(ast).filter((stmt) => stmt.type === 'ImportDeclaration');
		const hit = imports.some(
			(imp) =>
				String(imp.source?.value ?? '').includes('channelMetricLayouts') &&
				(imp.specifiers ?? []).some(
					(s: any) =>
						s.imported?.name === 'splitChannelMetricsForDisplay' ||
						s.local?.name === 'splitChannelMetricsForDisplay'
				)
		);
		assert.ok(
			hit,
			'AC-12 FAIL (RED): kein Import von `splitChannelMetricsForDisplay` aus `channelMetricLayouts.ts` im ' +
				'Instance-Script gefunden — Gefahr eines zweiten, eigenen "Aus"-Algorithmus statt der geteilten ' +
				'Kanal-Formel (Mutation-Gegenprobe: "eigene Mengenrechnung einsetzen" muss hier rot werden).'
		);
	});

	test('splitChannelMetricsForDisplay wird im Instance-Script auch tatsaechlich AUFGERUFEN', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		let aufgerufen = false;
		walk(instanceBody(ast), (n) => {
			if (
				n.type === 'CallExpression' &&
				n.callee?.type === 'Identifier' &&
				n.callee.name === 'splitChannelMetricsForDisplay'
			) {
				aufgerufen = true;
			}
		});
		assert.ok(
			aufgerufen,
			'AC-12 FAIL (RED): `splitChannelMetricsForDisplay` wird nirgends aufgerufen — ein reiner Import ' +
				'ohne Aufruf belegt keine geteilte Berechnung.'
		);
	});
});
