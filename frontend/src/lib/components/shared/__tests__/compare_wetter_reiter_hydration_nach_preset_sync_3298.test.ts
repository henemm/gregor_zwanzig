// Issue #3298 (CI-E2E rot, Fix): der Reiter „Wetter“ des Ortsvergleichs blieb nach dem Wegfall der
// Altfelder fuer immer in der Hydrations-Sperre (Tabelle „Was steht wo“ erschien nie).
//
// Ursache: `hydrateLayoutTab()` lief nach #3298 ohne `await` — `layoutHydrated = true` fiel damit in
// den ERSTEN Effektlauf. Der Preset-Sync-Effekt (`currentPreset = snapshotForRollback(preset)`,
// derselbe Mount-Durchlauf, im Quelltext danach) setzt die Flags wieder auf false; Svelte laesst den
// Layout-Effekt im selben Durchlauf erneut laufen, dort stand aber noch die Sperre `layoutHydrating`
// (aufgehoben erst im `finally`-Microtask) — Ergebnis: `layoutHydrated` blieb false, das Gate
// `wetterMetrikenLayoutHydrationBereit` blieb zu.
//
// Gemessen wird, was der Code TUT: die echten $effect-Rumpfe von CompareTabs im Instanz-Pruefstand,
// in der Reihenfolge des Svelte-Mounts (Reiter-Effekte, dann Preset-Sync, dann der synchrone
// Wiederholungslauf der Reiter-Effekte im selben Durchlauf), erst danach Microtasks.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/compare_wetter_reiter_hydration_nach_preset_sync_3298.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';
// Vorab laden, solange `window` noch das echte (leere) globale Objekt ist: der Pruefstand ersetzt
// `window` je Fall durch eine Attrappe, ein erst dann geladenes Modul bliebe im Hub ungebunden.
import '../wetter-tab/compareMetricCatalogLoader.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const VERGLEICH_HUB = join(HIER, '..', '..', 'compare', 'CompareTabs.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

function laufen(effekte: Array<() => void>, fehler: string[]): void {
	for (const e of effekte) {
		try {
			e();
		} catch (err) {
			fehler.push(String(err));
		}
	}
}

async function mountMitPresetSync(tab: string): Promise<{ u: Knoten; fehler: string[] }> {
	const pfad = '/compare/c-1';
	const href = `http://localhost${pfad}?tab=${tab}`;
	(globalThis as Knoten).window = {
		location: { href, search: `?tab=${tab}`, pathname: pfad, hash: '' },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = { state: null, replaceState() {}, pushState() {} };
	const saat: Knoten = {
		initialTab: tab,
		preset: vollerVergleich('c-1'),
		locations: [],
		orteCount: 3,
		goto: () => Promise.resolve(),
		page: { url: new URL(href) }
	};
	const { u, ast, quelle } = await umgebungFuer(VERGLEICH_HUB, saat, { jsAlsTs: true });
	const fehler: string[] = [];
	laufen(effekteVon(ast, quelle, u, 'initialTab'), fehler);
	// Mount-Durchlauf in Quelltext-Reihenfolge: Hydrations-Weichen, danach der Preset-Sync-Effekt …
	laufen(effekteVon(ast, quelle, u, 'activeTab'), fehler);
	laufen(effekteVon(ast, quelle, u, 'snapshotForRollback'), fehler);
	// … der die Flags zuruecksetzt; Svelte laesst die Weichen im SELBEN Durchlauf erneut laufen
	// (vor jedem Microtask), weil sich ihre Abhaengigkeiten geaendert haben.
	laufen(effekteVon(ast, quelle, u, 'activeTab'), fehler);
	for (let i = 0; i < 30; i++) await new Promise((r) => setTimeout(r, 0));
	return { u, fehler };
}

describe('#3298: Reiter Wetter/Zustellung oeffnet die Hydrations-Sperre auch nach dem Preset-Sync', () => {
	for (const tab of ['wetter', 'zustellung']) {
		test(`${tab}: layoutHydrated und Gate stehen nach dem Mount-Durchlauf auf true`, async () => {
			const { u, fehler } = await mountMitPresetSync(tab);
			assert.equal(u.activeTab, tab, `Vorbedingung: Reiter ${tab} offen; ${JSON.stringify(fehler)}`);
			assert.deepEqual(fehler, [], `Effektlauf warf: ${JSON.stringify(fehler)}`);
			assert.equal(u.layoutHydrated, true, `Layout-Hydration nach Preset-Sync nie nachgeholt (Reiter ${tab} bliebe leer)`);
			assert.equal(u.wetterMetrikenHydrated, true, `Metrik-Hydration im Reiter ${tab} nicht gelaufen`);
			const gate = (u.wetterMetrikenHydrationAbgeschlossen as (f: object) => boolean)({
				wetterMetrikenHydrated: u.wetterMetrikenHydrated,
				layoutHydrated: u.layoutHydrated
			});
			assert.equal(gate, true, `Gate wetterMetrikenLayoutHydrationBereit bleibt zu — WetterTab erschiene nie (${tab})`);
		});
	}
});
