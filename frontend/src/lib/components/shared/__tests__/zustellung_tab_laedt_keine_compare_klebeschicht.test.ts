// Issue #3020 R1 (G17): der geteilte Reiter „Zustellung“ lädt zur Laufzeit NICHT die Compare-Hub-Klebeschicht
// (`compare/compareHubPersistenz.ts`, `compare/compareHubHydration.ts`). Muster
// alarme_tab_laedt_keine_compare_klebeschicht.test.ts: gemessen wird der Ladegraph (Auflösungs-Haken), nicht der
// Dateiinhalt; `import type` taucht darin nicht auf.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/zustellung_tab_laedt_keine_compare_klebeschicht.test.ts

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

const ORDNER = path.join(FRONTEND, 'src/lib/components/shared/zustellung-tab');
const PRUEFLING = path.join(ORDNER, 'ZustellungTab.svelte');
const { render } = await import('svelte/server');
const ZustellungTab = (await import(pathToFileURL(PRUEFLING).href)).default;
/** Eingefroren, BEVOR die Gegenprobe die Klebeschicht absichtlich nachlädt. */
const HAUPTGRAPH = [...geladen];

const KLEBESCHICHT = ['/src/lib/components/compare/compareHubPersistenz.ts', '/src/lib/components/compare/compareHubHydration.ts'];
const PRESET = { id: 'cp-3020-graph', name: 'Ortsvergleich Graph', location_ids: ['loc-a'], schedule: 'daily', profil: 'wandern', display_config: {} };

describe('#3020 G17: ZustellungTab lädt keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext lädt keine Compare-Klebeschicht', () => {
		const { body } = render(ZustellungTab as never, { props: { context: 'vergleich', preset: PRESET, onCompareUpdate: () => {} } } as never);
		assert.ok(body.includes('data-testid="zustellung-tab"'), 'Vorbedingung: der Reiter muss rendern');
		for (const datei of ['zustellungSpeicherung.ts', 'zustellungModell.ts'])
			assert.ok(HAUPTGRAPH.some((u) => u.endsWith(`/shared/zustellung-tab/${datei}`)), `Vorbedingung: der Protokoll-Haken muss ${datei} sehen`);
		// #3458: BeispielAlarm aus der Liste entfernt (Organismus geloescht).
		for (const organ of ['BriefingZeiten', 'LaufzeitKarte', 'KanalTabelle', 'StilleStunden'])
			assert.ok(HAUPTGRAPH.some((u) => u.endsWith(`/organisms/zustellung-tab/${organ}.svelte`)), `Vorbedingung: ${organ} im Ladegraphen`);
		for (const pfad of KLEBESCHICHT) assert.ok(existsSync(path.join(FRONTEND, pfad)), `Vakuum-Schutz: ${pfad} muss existieren`);
		assert.deepEqual(
			HAUPTGRAPH.filter((u) => KLEBESCHICHT.some((pfad) => u.endsWith(pfad))),
			[],
			'ZustellungTab (oder ein von ihm geladenes Modul) lädt die Compare-Klebeschicht zur Laufzeit'
		);
	});

	test('Gegenprobe: ein eingeschleuster Import aus compareHubHydration wird gesehen', async () => {
		// Kopie des echten Prüflings neben ihm (relative Importe unverändert) mit EINEM zusätzlichen Wert-Import.
		const kopie = path.join(ORDNER, '__tests__', '__gegenprobe_zustellung_tab.svelte');
		try {
			const quelle = readFileSync(PRUEFLING, 'utf-8')
				.replace(/from '\.\.\//g, "from '@@GZ@@/")
				.replace(/from '\.\//g, "from '../")
				.replace(/from '@@GZ@@\//g, "from '../../");
			writeFileSync(
				kopie,
				quelle.replace(
					'<script lang="ts">',
					`<script lang="ts">\n\timport { hydrateAlarmFieldsFromPreset } from '../../../compare/compareHubHydration.ts';\n\tvoid hydrateAlarmFieldsFromPreset;`
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
