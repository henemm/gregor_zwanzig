// TDD RED — Feature #2287 (Epic #2345, Etappe P2), AC-13: die Anlege-Seiten
// `/trips/new` und `/compare/new` fuehren fuer ihre gemeinsame Schwanz-Kette DIESELBEN
// Kennungen: wetter-metriken · wertebereiche · alarme · versand (Punkte-Reiter
// `etappen` bzw. `orte`); `tailUnlocked` bekommt in beiden Seiten identische `TailIds`.
//
// Spec: docs/specs/modules/feat_2287_tab_kennungen.md — E6, AC-13
//
// Messweise:
//   - Trip: die ECHTEN Funktionen `unlockedTabs`/`doneTabs` (tripNewLogic.ts) mit allen
//     Besuchs-Flags — die Menge der freigeschalteten Reiter-IDs IST die TailIds-Wirkung.
//   - Vergleich: ECHTES SSR-Rendering von CompareNewEditor.svelte (Muster
//     compare_new_lock_engine_wirkstelle.test.ts); die Reiterleiste traegt `compare-editor-tab-<id>`.
//
// Grenze: der gerenderte Trip-Anlege-Reiter hat kein id-testid; die Trip-Kennungen werden
// ueber die Logik gemessen, der Anlege-Flow mit neuen testids ist Playwright (/e2e-verify).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/anlege_reiter_kennungen_gleich.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

import { unlockedTabs, doneTabs } from '../../trip-new/tripNewLogic.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(HERE, '../../trip-new/__tests__/ssrRunesHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const Editor = (await import(pathToFileURL(path.join(HERE, '../../compare-new/CompareNewEditor.svelte')).href)).default;

const SCHWANZ = ['wetter-metriken', 'wertebereiche', 'alarme', 'versand'];
const ALT_ANLEGE = ['metriken', 'idealwerte'];

function vergleichHtml(activeTab: string, alleFlags: boolean): string {
	const wiz = { name: 'X', region: '', profile: 'wandern', pickedIds: ['a', 'b', 'c'] };
	return render(Editor, {
		props: {
			stateOverride: {
				activeTab,
				isMobileViewport: false,
				metrikenVisited: alleFlags,
				idealsVisited: alleFlags,
				alarmeVisited: alleFlags,
				versandVisited: alleFlags
			}
		},
		context: new Map([['compare-wizard-state', wiz]])
	}).body;
}

function vergleichReiterIds(html: string): string[] {
	return [...html.matchAll(/data-testid="compare-editor-tab-([a-z-]+)"/g)].map((m) => m[1]);
}

describe('AC-13 Trip-Anlegen: Schwanz-Kette traegt die gemeinsamen Kennungen', () => {
	test('alle Besuchs-Flags: freigeschaltet sind wetter-metriken, wertebereiche, alarme, versand', () => {
		const u = unlockedTabs('GR20', '2026-07-01', true, true, true, true, true) as Set<string>;
		for (const id of SCHWANZ) assert.ok(u.has(id), `'${id}' nicht freigeschaltet: ${[...u].join(',')}`);
		for (const alt of ALT_ANLEGE) assert.ok(!u.has(alt), `Alt-Kennung '${alt}' im Trip-Anlegen`);
	});

	test('Freischalt-Reihenfolge unveraendert: Wertebereiche erst nach Wetter-Metriken, Alarme nach Wertebereichen, Versand nach Alarmen', () => {
		const frei = (wt: boolean, wb: boolean, al: boolean) =>
			unlockedTabs('GR20', '2026-07-01', true, wt, wb, al, false) as Set<string>;
		assert.equal(frei(false, false, false).has('wertebereiche'), false);
		assert.equal(frei(true, false, false).has('wertebereiche'), true);
		assert.equal(frei(true, false, false).has('alarme'), false);
		assert.equal(frei(true, true, false).has('alarme'), true);
		assert.equal(frei(true, true, false).has('versand'), false);
		assert.equal(frei(true, true, true).has('versand'), true);
	});

	test('erledigt-Menge benutzt dieselben Kennungen', () => {
		const d = doneTabs('GR20', '2026-07-01', true, true, true, true, true) as Set<string>;
		for (const id of ['wetter-metriken', 'alarme', 'versand']) assert.ok(d.has(id), `'${id}' nicht erledigt`);
	});

	test('Punkte-Reiter heisst etappen; wegpunkte bleibt kind-eigen', () => {
		const u = unlockedTabs('GR20', '2026-07-01', true, false, false, false, false) as Set<string>;
		assert.ok(u.has('etappen') && u.has('wegpunkte') && u.has('route'));
	});
});

describe('AC-13 Vergleich-Anlegen: Reiterleiste traegt dieselben Kennungen (gerenderte testids)', () => {
	test('Reiter: vergleich, orte, wetter-metriken, wertebereiche, alarme, versand — keine Alt-Kennung', () => {
		const ids = vergleichReiterIds(vergleichHtml('vergleich', true));
		assert.deepEqual(ids, ['vergleich', 'orte', ...SCHWANZ]);
	});

	test('alle Flags gesetzt: kein Schwanz-Reiter gesperrt', () => {
		const html = vergleichHtml('vergleich', true);
		for (const id of SCHWANZ) {
			const m = html.match(new RegExp(`data-testid="compare-editor-tab-${id}"[^>]*?data-locked="(true|false)"`));
			assert.ok(m, `Reiter ${id} fehlt`);
			assert.equal(m![1], 'false', `Reiter ${id} gesperrt`);
		}
	});

	test('Freischalt-Reihenfolge unveraendert: ohne Besuch ist Wertebereiche gesperrt', () => {
		const html = vergleichHtml('vergleich', false);
		const m = html.match(/data-testid="compare-editor-tab-wertebereiche"[^>]*?data-locked="(true|false)"/);
		assert.ok(m, 'Reiter wertebereiche fehlt');
		assert.equal(m![1], 'true');
	});

	test('Weiter-Knopf des Metriken-Reiters: compare-editor-continue-wertebereiche (E5)', () => {
		const html = vergleichHtml('wetter-metriken', true);
		assert.ok(html.includes('data-testid="compare-editor-continue-wertebereiche"'), 'continue-wertebereiche fehlt');
		assert.ok(!html.includes('compare-editor-continue-idealwerte'), 'Alt-testid continue-idealwerte');
	});
});

describe('AC-13 Paritaet: beide Seiten fuehren dieselben Schwanz-Kennungen', () => {
	test('Trip-Freischaltmenge ∩ Schwanz == Vergleich-Reiterleiste ∩ Schwanz', () => {
		const trip = [...(unlockedTabs('GR20', '2026-07-01', true, true, true, true, true) as Set<string>)]
			.filter((i) => SCHWANZ.includes(i))
			.sort();
		const vergleich = vergleichReiterIds(vergleichHtml('vergleich', true)).filter((i) => SCHWANZ.includes(i)).sort();
		assert.deepEqual(trip, [...SCHWANZ].sort());
		assert.deepEqual(vergleich, trip);
	});
});
