// Issue #1360 (Scheibe S1a von Epic #1372) — der Reiter „Layout" des
// Ortsvergleichs ist aufgelöst; die Stundenverlauf-Steuerung wohnt im Reiter
// „Wetter-Metriken".
//
// Spec: docs/specs/modules/compare_layout_tab_dissolution.md § AC-1, AC-3, AC-6
//
// Diese Datei löst zwei gelöschte Bestands-Suiten inhaltlich ab:
//   - `compare_hub_layout_hourly_access.test.ts` (#1299/C2) prüfte, dass die
//     Stundenverlauf-Steuerung im Layout-PANEL hängt. Das Panel existiert nicht
//     mehr; die Aussage „sie ist im Hub erreichbar UND ihr Speicherweg hängt
//     dran" bleibt aber wertvoll und wird hier auf die neue Heimat gezogen.
//   - `compare_layout_named_chips.test.ts` / `compare_layout_row_named_chips.
//     test.ts` prüften die Attrappen-Zeile `CompareLayoutRow` — ersatzlos weg.
//
// --- Warum AST statt DOM-Mount (übernommen aus der abgelösten Suite) ---
// Dieses Repo hat KEIN vitest/jsdom/@testing-library/svelte (package.json:
// "test": "node --import ./test-lib-loader.mjs --experimental-strip-types
// --test"). Ein echter DOM-Mount ist strukturell nicht möglich. Statt eines
// Text-Greps über den Dateiinhalt (laut CLAUDE.md als Verhaltensnachweis
// verboten) parst dieser Test die Komponenten mit dem ECHTEN Svelte-5-Compiler
// und inspiziert den Template-AST. Der echte Klick-/Speicher-Pfad wird
// zusätzlich auf Staging bewiesen (frontend/e2e/compare-layout-tab-
// dissolution.spec.ts, AC-1..AC-6).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_layout_tab_dissolution.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { COMPARE_TABS, COMPARE_TAB_VALUES, resolveCompareTab } from '../compareTabsResolve.ts';
import { weatherMetricsTabSections } from '../../shared/weather-metrics-tab/weatherMetricsTabSections.ts';
import {
	unlockedTabs,
	doneTabs,
	progressCount,
	type CompareNewProgress
} from '../../compare-new/compareNewLogic.ts';

const here = dirname(fileURLToPath(import.meta.url));
const HUB = join(here, '..', 'CompareTabs.svelte');
const NEW_EDITOR = join(here, '..', '..', 'compare-new', 'CompareNewEditor.svelte');
const METRICS_TAB = join(here, '..', '..', 'shared', 'WeatherMetricsTab.svelte');

function ast(file: string): unknown {
	return parse(readFileSync(file, 'utf-8'), { modern: true });
}

/** Findet das IfBlock-Fragment für `activeTab === '<tabValue>'` (Top-Level-
 *  Tab-Panel-Verzweigung) und liefert dessen `consequent`-Fragment, sonst null. */
function findTabPanelFragment(node: unknown, tabValue: string): unknown {
	let found: unknown = null;
	function visit(cur: unknown): void {
		if (found !== null || cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (
			n.type === 'IfBlock' &&
			n.test?.type === 'BinaryExpression' &&
			n.test.operator === '===' &&
			n.test.left?.type === 'Identifier' &&
			n.test.left.name === 'activeTab' &&
			n.test.right?.value === tabValue
		) {
			found = n.consequent;
			return;
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(node);
	return found;
}

/** Findet jede Svelte-Komponenten-Instanz mit dem gegebenen Namen im Subtree. */
function findComponents(subtree: unknown, componentName: string): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'Component' && n.name === componentName) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Findet jedes Element mit der gegebenen CSS-Klasse (statisches class-Attribut). */
function findElementsWithClass(subtree: unknown, className: string): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'RegularElement') {
			for (const attr of n.attributes ?? []) {
				if (attr.type !== 'Attribute' || attr.name !== 'class') continue;
				const raw = Array.isArray(attr.value)
					? attr.value.map((v: any) => v.raw ?? '').join(' ')
					: (attr.value?.raw ?? '');
				if (raw.split(/\s+/).includes(className)) found.push(n);
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

/** Sammelt alle sichtbaren Text-Knoten im Subtree. */
function renderedTexts(subtree: unknown): string[] {
	const found: string[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'Text' && typeof n.data === 'string' && n.data.trim().length > 0) {
			found.push(n.data.trim());
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

// ── AC-1: sieben Reiter, kein „Layout" ──────────────────────────────────────

describe('AC-1: Reiterleiste des Ortsvergleichs', () => {
	test('genau sieben Reiter, keiner heißt „Layout"', () => {
		assert.deepEqual(
			COMPARE_TABS.map((t) => t.label),
			['Übersicht', 'Orte', 'Wetter-Metriken', 'Wertebereiche', 'Alarme', 'Versand', 'Vorschau'],
			'Soll aus Spec § Expected Behavior'
		);
		assert.equal(COMPARE_TABS.length, 7);
		assert.ok(!COMPARE_TAB_VALUES.includes('layout'), "'layout' darf kein gültiger Reiter mehr sein");
	});

	test('das Layout-Panel ist aus dem Hub verschwunden', () => {
		assert.equal(
			findTabPanelFragment(ast(HUB), 'layout'),
			null,
			"CompareTabs.svelte hat noch ein `activeTab === 'layout'`-Panel — es darf per " +
				'Deep-Link nicht doch noch erreichbar sein'
		);
	});
});

// ── AC-3: alter Deep-Link landet in Wetter-Metriken ─────────────────────────

describe('AC-3: Umleitung des alten Layout-Deep-Links', () => {
	test("resolveCompareTab('layout') → 'wetter-metriken'", () => {
		assert.equal(
			resolveCompareTab('layout'),
			'wetter-metriken',
			'Ein Lesezeichen auf ?tab=layout muss dort landen, wo die Einstellung jetzt ' +
				"liegt — nicht im generischen Fallback 'uebersicht'"
		);
	});

	test('gültige Reiter bleiben unverändert, Unbekanntes fällt weiter auf Übersicht', () => {
		for (const value of COMPARE_TAB_VALUES) {
			assert.equal(resolveCompareTab(value), value);
		}
		assert.equal(resolveCompareTab('gibtsnicht'), 'uebersicht');
		assert.equal(resolveCompareTab(''), 'uebersicht');
	});
});

// ── AC-2-Fundament: neue Heimat samt Speicherweg ────────────────────────────

describe('Stundenverlauf-Steuerung: neue Heimat + Speicherweg', () => {
	test("der Abschnitt 'stundenverlauf' liegt im Vergleich zwischen Reihenfolge und Amtlichen Warnungen", () => {
		const sections = weatherMetricsTabSections('vergleich');
		assert.ok(sections.includes('stundenverlauf'), `Abschnitt fehlt: ${sections.join(', ')}`);
		assert.ok(
			sections.indexOf('reihenfolge') < sections.indexOf('stundenverlauf'),
			'erst welche Tageswerte und in welcher Folge, dann der Stundenverlauf'
		);
		assert.ok(
			sections.indexOf('stundenverlauf') < sections.indexOf('official_alerts'),
			"'stundenverlauf' muss VOR 'official_alerts' liegen (Spec § Implementation Details 2)"
		);
	});

	test('der Trip bekommt in dieser Scheibe keinen Stundenverlauf', () => {
		assert.ok(
			!weatherMetricsTabSections('route').includes('stundenverlauf'),
			'Spec § Known Limitations: geteilt vorbereitet, aber nur im Vergleich aktiv'
		);
	});

	test('WeatherMetricsTab hängt die GETEILTE Steuerung ein (kein Compare-Eigenbau)', () => {
		const mounts = findComponents(ast(METRICS_TAB), 'CompareHourlyLayoutControls');
		assert.equal(
			mounts.length,
			1,
			'WeatherMetricsTab.svelte muss genau EINE <CompareHourlyLayoutControls>-Instanz ' +
				'mounten (Trip/Compare-Teilungs-Invariante: geteilt ist die Steuerung)'
		);
	});

	test('im Hub liegt die Steuerung im Wetter-Metriken-Panel — MIT ihrem Bubble-Wrapper', () => {
		// Das ist die eigentliche Umzugs-Falle (Spec § Implementation Details 3):
		// wandert `.hub-layout-hourly-wrap` nicht mit, speichert die Steuerung
		// stumm nicht mehr — im selben Tab sieht alles korrekt aus.
		const panel = findTabPanelFragment(ast(HUB), 'wetter-metriken');
		assert.notEqual(panel, null, "Panel `activeTab === 'wetter-metriken'` nicht gefunden");

		const wrappers = findElementsWithClass(panel, 'hub-layout-hourly-wrap');
		assert.equal(
			wrappers.length,
			1,
			'Im Wetter-Metriken-Panel muss genau EIN `.hub-layout-hourly-wrap` liegen — ' +
				'der Speicherweg des Stundenverlaufs (flushPendingLayoutSave → ' +
				'buildComparePresetSavePayload, Round-Trip-Spread) haengt daran'
		);

		const handlers = (wrappers[0].attributes ?? [])
			.filter((a: any) => a.type === 'Attribute')
			.map((a: any) => a.name);
		for (const evt of ['onchange', 'onfocusout', 'onclick']) {
			assert.ok(
				handlers.includes(evt),
				`Der Wrapper braucht ${evt} in der Bubble-Phase (SF-1-Erkenntnis): ` +
					`vorhanden ${JSON.stringify(handlers)}`
			);
		}

		// Und die Steuerung muss innerhalb dieses Panels tatsächlich gemountet
		// werden — über den geteilten WeatherMetricsTab.
		assert.equal(
			findComponents(panel, 'WeatherMetricsTab').length,
			1,
			'Das Panel mountet den geteilten WeatherMetricsTab (context="vergleich")'
		);
	});
});

// ── AC-4: keine Orts-Kappungs-Behauptung mehr im Hub ────────────────────────

describe('AC-4: keine Behauptung einer Orts-Kappung je Kanal', () => {
	test('die Attrappen-Texte des Layout-Reiters sind aus dem Hub verschwunden', () => {
		const texts = renderedTexts(ast(HUB));
		const forbidden = [
			/Telegram\s*·\s*max\s*\d+/i,
			/kappt\s+je\s+Kanal/i,
			/Spalten\s+pro\s+Kanal/i,
			/Übersicht\s+pro\s+Kanal/i
		];
		for (const pattern of forbidden) {
			const hit = texts.find((t) => pattern.test(t));
			assert.equal(
				hit,
				undefined,
				`CompareTabs.svelte zeigt weiterhin "${hit}" (${pattern}). Belegte ` +
					'Renderer-Regel: alle drei Kanäle geben ALLE Orte aus.'
			);
		}
	});

	test('die Attrappen-Zeile CompareLayoutRow wird nicht mehr gemountet', () => {
		assert.equal(findComponents(ast(HUB), 'CompareLayoutRow').length, 0);
	});
});

// ── AC-6: Anlege-Seite zieht identisch mit ──────────────────────────────────

describe('AC-6: Anlege-Seite (/compare/new)', () => {
	test('kein Layout-Panel mehr', () => {
		assert.equal(
			findTabPanelFragment(ast(NEW_EDITOR), 'layout'),
			null,
			"CompareNewEditor.svelte hat noch ein `activeTab === 'layout'`-Panel"
		);
	});

	test('sechs Reiter — und der Alarme-Reiter ist erreichbar', () => {
		// Die eigentliche Gefahr: die Lock-Kette verlangte den Besuch des
		// Layout-Reiters, den es nicht mehr gibt → Alarme (und damit Versand und
		// „Briefing aktivieren") wären unerreichbar.
		const progress: CompareNewProgress = {
			name: 'Testvergleich',
			pickedCount: 2,
			metrikenVisited: true,
			idealsVisited: true,
			alarmeVisited: false,
			versandVisited: false
		};
		const unlocked = unlockedTabs(progress);
		assert.ok(
			unlocked.has('alarme'),
			'Nach Name + 2 Orten + Wetter-Metriken + Wertebereiche MUSS Alarme offen sein — ' +
				`offen: ${[...unlocked].join(', ')}`
		);
		assert.ok(!unlocked.has('layout' as never), "'layout' darf kein Reiter mehr sein");

		const allVisited: CompareNewProgress = {
			...progress,
			alarmeVisited: true,
			versandVisited: true
		};
		const done = doneTabs(allVisited);
		assert.ok(done.has('versand'), 'Versand muss erreichbar und abschließbar sein');
		assert.equal(progressCount(done), 6, 'Fortschrittszähler jetzt 6 statt 7');
	});

	test('kein Lock-Hinweis verweist mehr auf den Layout-Reiter', () => {
		const texts = renderedTexts(ast(NEW_EDITOR));
		const hit = texts.find((t) => /erst Layout/i.test(t));
		assert.equal(hit, undefined, `Verwaister Lock-Hinweis gefunden: "${hit}"`);
	});
});
