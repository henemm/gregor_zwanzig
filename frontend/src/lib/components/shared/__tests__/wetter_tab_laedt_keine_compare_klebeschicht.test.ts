// Issue #3020 R1 (G56): der geteilte Reiter „Wetter“ samt Organismen und Karte „Was steht wo“ lädt zur Laufzeit NICHT
// die Compare-Hub-Klebeschicht. Muster alarme_tab_laedt_keine_compare_klebeschicht.test.ts (Ladegraph statt
// Dateiinhalt); die vier Logikmodule prüft wertebereiche_logik_laedt_keine_compare_klebeschicht.test.ts.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/wetter_tab_laedt_keine_compare_klebeschicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');

/** Jede URL, die ab hier aufgelöst wird (Ladegraph des Prüflings). */
const geladen = new Set<string>();
registerHooks({
	resolve(specifier, context, nextResolve) {
		const ergebnis = nextResolve(specifier, context);
		geladen.add(ergebnis.url);
		return ergebnis;
	}
});
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const PRUEFLING = path.join(FRONTEND, 'src/lib/components/shared/WetterTab.svelte');
const { render } = await import('svelte/server');
const WetterTab = (await import(pathToFileURL(PRUEFLING).href)).default;
/** Eingefroren, BEVOR die Gegenprobe die Klebeschicht absichtlich nachlädt. */
const HAUPTGRAPH = [...geladen];

const KLEBESCHICHT = ['/src/lib/components/compare/compareHubPersistenz.ts', '/src/lib/components/compare/compareHubHydration.ts'];
const PRESET = { id: 'cp-3020-graph-w', name: 'Ortsvergleich Graph', location_ids: ['loc-a'], schedule: 'daily', profil: 'wandern', display_config: {} };

describe('#3020 G56: WetterTab lädt keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext lädt keine Compare-Klebeschicht', () => {
		const { body } = render(WetterTab as never, { props: { context: 'vergleich', preset: PRESET, onCompareUpdate: () => {} } } as never);
		assert.ok(body.includes('data-testid="wetter-tab"'), 'Vorbedingung: der Reiter muss rendern');
		for (const modul of ['shared/wetter-tab/wetterTabSpeicherung.ts', 'shared/wetter-tab/wasStehtWoSpeicherung.ts', 'organisms/wetter-tab/WetterTabInhalt.svelte', 'organisms/wetter-tab/WasStehtWoKarte.svelte'])
			assert.ok(HAUPTGRAPH.some((u) => u.endsWith(`/src/lib/components/${modul}`)), `Vorbedingung: der Protokoll-Haken muss ${modul} sehen`);
		for (const pfad of KLEBESCHICHT) assert.ok(existsSync(path.join(FRONTEND, pfad)), `Vakuum-Schutz: ${pfad} muss existieren`);
		assert.deepEqual(
			HAUPTGRAPH.filter((u) => KLEBESCHICHT.some((pfad) => u.endsWith(pfad))),
			[],
			'WetterTab (oder ein von ihm geladenes Modul) lädt die Compare-Klebeschicht zur Laufzeit'
		);
	});

	test('Gegenprobe: ein eingeschleuster Import aus compareHubHydration wird gesehen', async () => {
		// Kopie des echten Prüflings in __tests__/ (er importiert nur über $lib) mit EINEM zusätzlichen Wert-Import.
		const kopie = path.join(HERE, '__gegenprobe_wetter_tab.svelte');
		try {
			const quelle = readFileSync(PRUEFLING, 'utf-8');
			assert.ok(!/from '\.\.?\//.test(quelle), 'Messaufbau: relative Importe im Prüfling müssten angehoben werden');
			writeFileSync(
				kopie,
				quelle.replace(
					'<script lang="ts">',
					`<script lang="ts">\n\timport { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';\n\tvoid hydrateAlarmFieldsFromPreset;`
				)
			);
			await import(pathToFileURL(kopie).href);
			assert.ok(
				[...geladen].some((u) => KLEBESCHICHT.some((pfad) => u.endsWith(pfad))),
				'ein echter Laufzeit-Import aus compareHubHydration.ts bleibt unbemerkt — der Test oben bewiese nichts'
			);
		} finally {
			rmSync(kopie, { force: true });
		}
	});
});
