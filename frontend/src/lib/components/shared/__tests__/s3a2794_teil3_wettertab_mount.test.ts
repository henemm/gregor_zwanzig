// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: Mount-Stellen des neuen Reiters.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-38, Implementation Details §4 (Mount-Stellen, Teil-2-Lehre F012)
//
// Soll:
//   - TripTabs.svelte mountet im Reiter `wetter` genau EINEN `WetterTab` (organisms/wetter-tab/) mit context="route"
//     per if-Kette; CompareTabs.svelte genau einen mit context="vergleich", NUR unter der bestehenden
//     Bedingung `wetterMetrikenLayoutHydrationBereit`.
//   - Im Reiter `wetter` der Hubs haengt KEIN WetterMetrikenVersandPanel, kein WeatherMetricsTab und kein
//     CorridorEditor/CorridorEditorMobile mehr (Alt-Code bleibt bis Teil-PR 4 im Repo, wird dort nicht gemountet).
//   - TripNewEditor/CompareNewEditor mounten `WetterTab` im Schritt `wetter` (sichtbar nur dort), nie zwei
//     Instanzen zugleich.
//   - Jeder WMT-Traeger (WeatherMetricsTab, WetterMetrikenVersandPanel) in den vier Dateien hat nur noch
//     bereich="zustellung" — genau ein Speicherer je Reiter (AC-38); kein Mount irgendwo mit bereich="wetter".
//   - WetterTab und seine Bausteine betten selbst keinen zweiten Speicherer (WMT/Panel/CorridorEditor) ein.
//
// Messweise: AST nach Repo-Muster (s3a2794Ast.ts), keine Textsuche.
// RED heute: organisms/wetter-tab/WetterTab.svelte fehlt, die Hubs/Editoren mounten noch Panel + CorridorEditor.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_teil3_wettertab_mount.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
	svelteAst,
	existiert,
	einbettungenMitWeichen,
	reiterVon,
	schliessenSichAus,
	attribut,
	displayAusdruck,
	propNamen,
	type Einbettung
} from './s3a2794Ast.ts';
import { werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const WETTER_TAB_ORDNER = join(KOMP, 'organisms', 'wetter-tab');

const DATEI = {
	tripHub: join(KOMP, 'trip-detail', 'TripTabs.svelte'),
	vergleichHub: join(KOMP, 'compare', 'CompareTabs.svelte'),
	tripNeu: join(KOMP, 'trip-new', 'TripNewEditor.svelte'),
	vergleichNeu: join(KOMP, 'compare-new', 'CompareNewEditor.svelte'),
	wetterTab: join(WETTER_TAB_ORDNER, 'WetterTab.svelte')
};

const ALT_IM_REITER_WETTER = ['WetterMetrikenVersandPanel', 'WeatherMetricsTab', 'CorridorEditor', 'CorridorEditorMobile'];
const WMT_TRAEGER = ['WeatherMetricsTab', 'WetterMetrikenVersandPanel'];

const beschreibe = (e: Einbettung, quelle: string) =>
	`${e.name}@${quelle.slice(0, e.knoten.start).split('\n').length} [${e.weichen.map((w) => `${w.zweig}:${w.test}`).join(' > ')}]`;

function wetterTabs(datei: string): { e: Einbettung[]; quelle: string } {
	const { ast, quelle } = svelteAst(datei);
	return { e: einbettungenMitWeichen(ast, quelle, ['WetterTab']), quelle };
}

/** Der Import von WetterTab zeigt auf organisms/wetter-tab/WetterTab.svelte (kein Pendant). */
function importQuelle(datei: string, name: string): string | null {
	const { ast } = svelteAst(datei);
	for (const s of (ast.instance?.content?.body ?? []) as Array<Record<string, any>>) {
		if (s.type !== 'ImportDeclaration') continue;
		if ((s.specifiers as Array<Record<string, any>>).some((sp) => sp.local?.name === name)) return s.source.value as string;
	}
	return null;
}

/** Sichtbar im Schritt `schritt`? if-Kette ODER style:display-Huelle (Muster #932/#941). */
function sichtbarIm(e: Einbettung, quelle: string, schritt: string): boolean {
	const r = reiterVon(e);
	if (r.length > 0) return r.includes(schritt);
	const d = displayAusdruck(e, quelle);
	assert.ok(d, `${beschreibe(e, quelle)}: weder an einer Reiter-Weiche noch in einer style:display-Huelle`);
	return werte(d!, { activeTab: schritt }) === '';
}

describe('WetterTab: organisms/wetter-tab/WetterTab.svelte mit context-Prop', () => {
	test('s3a2794_t3_wettertab_existiert_mit_context', () => {
		assert.ok(existiert(DATEI.wetterTab), 'TDD RED: organisms/wetter-tab/WetterTab.svelte fehlt');
		const { ast } = svelteAst(DATEI.wetterTab);
		assert.ok(propNamen(ast).includes('context'), `WetterTab: keine Prop context (Props: ${propNamen(ast).join(', ')})`);
	});

	test('s3a2794_t3_wettertab_bettet_keinen_zweiten_speicherer_ein', () => {
		assert.ok(existiert(WETTER_TAB_ORDNER), 'TDD RED: Ordner organisms/wetter-tab/ fehlt');
		const dateien = readdirSync(WETTER_TAB_ORDNER)
			.filter((f) => f.endsWith('.svelte'))
			.map((f) => join(WETTER_TAB_ORDNER, f))
			.filter((f) => statSync(f).isFile());
		assert.ok(dateien.length > 0, 'TDD RED: keine .svelte-Datei unter organisms/wetter-tab/');
		for (const d of dateien) {
			const { ast, quelle } = svelteAst(d);
			const fremd = einbettungenMitWeichen(ast, quelle, [...ALT_IM_REITER_WETTER, 'ZustellungTab']);
			assert.deepEqual(fremd.map((x) => beschreibe(x, quelle)), [], `${d}: bettet einen zweiten Speicherer ein`);
		}
	});
});

for (const [kind, datei, ctx] of [
	['trip', DATEI.tripHub, 'route'],
	['vergleich', DATEI.vergleichHub, 'vergleich']
] as const) {
	describe(`AC-38 Hub ${kind}: Reiter wetter = genau ein WetterTab, kein Alt-Speicherer`, () => {
		test(`s3a2794_t3_hub_${kind}_genau_ein_wettertab_im_reiter_wetter`, () => {
			const { e, quelle } = wetterTabs(datei);
			assert.equal(e.length, 1, `TDD RED: erwartet genau einen WetterTab im ${kind}-Hub, gefunden ${e.length}`);
			assert.deepEqual(reiterVon(e[0]), ['wetter'], `${beschreibe(e[0], quelle)} haengt nicht (nur) am Reiter wetter`);
			assert.equal(attribut(e[0].knoten, quelle, 'context')?.literal, ctx, `WetterTab im ${kind}-Hub: context ≠ ${ctx}`);
			const q = importQuelle(datei, 'WetterTab');
			assert.ok(q && /organisms\/wetter-tab\/WetterTab\.svelte$/.test(q), `WetterTab wird nicht aus organisms/wetter-tab/ importiert: ${q}`);
		});

		test(`s3a2794_t3_hub_${kind}_kein_alt_baustein_im_reiter_wetter`, () => {
			const { ast, quelle } = svelteAst(datei);
			const alt = einbettungenMitWeichen(ast, quelle, ALT_IM_REITER_WETTER).filter((x) => reiterVon(x).includes('wetter'));
			assert.deepEqual(alt.map((x) => beschreibe(x, quelle)), [], `AC-38: im Reiter wetter haengt noch ein Alt-Baustein`);
		});

		test(`s3a2794_t3_hub_${kind}_wmt_traeger_nur_noch_bereich_zustellung`, () => {
			const { ast, quelle } = svelteAst(datei);
			for (const x of einbettungenMitWeichen(ast, quelle, WMT_TRAEGER)) {
				assert.equal(attribut(x.knoten, quelle, 'bereich')?.literal, 'zustellung', `${beschreibe(x, quelle)}: bereich ≠ 'zustellung'`);
			}
		});
	});
}

describe('AC-38 / F012: Vergleich-Hub mountet WetterTab erst nach der Layout-Hydration', () => {
	test('s3a2794_t3_vergleich_wettertab_unter_wetterMetrikenLayoutHydrationBereit', () => {
		const { e, quelle } = wetterTabs(DATEI.vergleichHub);
		assert.equal(e.length, 1, `TDD RED: erwartet genau einen WetterTab im Vergleich-Hub, gefunden ${e.length}`);
		const w = e[0].weichen.find((x) => x.zweig === 'dann' && /\bwetterMetrikenLayoutHydrationBereit\b/.test(x.test));
		assert.ok(w, `${beschreibe(e[0], quelle)}: steht nicht im dann-Zweig einer Weiche mit wetterMetrikenLayoutHydrationBereit`);
		assert.equal(Boolean(werte(w!.test, { wetterMetrikenLayoutHydrationBereit: false, activeTab: 'wetter' })), false, 'mountet vor der Hydration');
		assert.equal(Boolean(werte(w!.test, { wetterMetrikenLayoutHydrationBereit: true, activeTab: 'wetter' })), true, 'mountet nach der Hydration nicht');
	});
});

for (const [kind, datei, ctx] of [
	['trip', DATEI.tripNeu, 'route'],
	['vergleich', DATEI.vergleichNeu, 'vergleich']
] as const) {
	describe(`AC-38 Anlegen ${kind}: WetterTab im Schritt wetter`, () => {
		test(`s3a2794_t3_neu_${kind}_wettertab_nur_im_schritt_wetter_sichtbar`, () => {
			const { e, quelle } = wetterTabs(datei);
			assert.ok(e.length >= 1, `TDD RED: kein WetterTab im ${kind}-Anlegen`);
			for (const x of e) {
				assert.equal(attribut(x.knoten, quelle, 'context')?.literal, ctx, `${beschreibe(x, quelle)}: context ≠ ${ctx}`);
				assert.equal(sichtbarIm(x, quelle, 'wetter'), true, `${beschreibe(x, quelle)}: im Schritt wetter nicht sichtbar`);
				for (const s of ['zustellung', kind === 'trip' ? 'route' : 'orte']) {
					assert.equal(sichtbarIm(x, quelle, s), false, `${beschreibe(x, quelle)}: auch im Schritt ${s} sichtbar`);
				}
			}
		});

		test(`s3a2794_t3_neu_${kind}_nie_zwei_wettertabs_zugleich`, () => {
			const { e, quelle } = wetterTabs(datei);
			assert.ok(e.length >= 1, `TDD RED: kein WetterTab im ${kind}-Anlegen`);
			for (let i = 0; i < e.length; i++) {
				for (let j = i + 1; j < e.length; j++) {
					assert.ok(schliessenSichAus(e[i], e[j]), `zwei WetterTab zugleich: ${beschreibe(e[i], quelle)} / ${beschreibe(e[j], quelle)}`);
				}
			}
		});

		test(`s3a2794_t3_neu_${kind}_wmt_traeger_nur_noch_bereich_zustellung`, () => {
			const { ast, quelle } = svelteAst(datei);
			const t = einbettungenMitWeichen(ast, quelle, WMT_TRAEGER);
			for (const x of t) {
				assert.equal(attribut(x.knoten, quelle, 'bereich')?.literal, 'zustellung', `${beschreibe(x, quelle)}: bereich ≠ 'zustellung' (Wetter-Felder haetten zwei Speicherer)`);
			}
		});
	});
}

describe('AC-38: nirgends mehr ein WMT-Traeger mit bereich="wetter"', () => {
	test('s3a2794_t3_kein_mount_mit_bereich_wetter_in_components', () => {
		const funde: string[] = [];
		(function lauf(ordner: string): void {
			for (const n of readdirSync(ordner)) {
				const p = join(ordner, n);
				if (n === '__tests__' || n === 'node_modules') continue;
				if (statSync(p).isDirectory()) lauf(p);
				else if (n.endsWith('.svelte')) {
					const { ast, quelle } = svelteAst(p);
					for (const x of einbettungenMitWeichen(ast, quelle, WMT_TRAEGER)) {
						if (attribut(x.knoten, quelle, 'bereich')?.literal === 'wetter') funde.push(`${p.slice(KOMP.length + 1)}: ${beschreibe(x, quelle)}`);
					}
				}
			}
		})(KOMP);
		assert.deepEqual(funde, [], 'WMT/Panel noch mit bereich="wetter" gemountet');
	});
});
