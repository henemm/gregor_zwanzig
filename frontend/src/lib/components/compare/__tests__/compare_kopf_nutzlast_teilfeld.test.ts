// TDD RED — Issue #2375, löst #2381 mit (Epic #2345): die Kopf-Edits der
// Ortsvergleich-Seite (Name, Region, Aktivitätsprofil) senden NUR ihr eigenes
// Feld — nie `{ ...currentPreset, … }`. Die Seite hält eine ZWEITE, eigene
// `currentPreset`-Kopie, die Reiter-Speicherungen desselben Tabs nicht
// mitbekommt; der Voll-Spread schrieb deshalb schon im SELBEN Tab gerade
// gespeicherte Reiter-Werte zurück (#2381).
//
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
//   Test 3 / AC-9 — Body exakt { name } / { display_config: { region } } / { profil }
//   AC-5         — ein zuvor gespeicherter Reiter-Wert bleibt nach dem Kopf-Edit
//
// Wo die Zusicherung wirkt: `onSaveField` (#2284 S1, vormals saveName/saveRegion/saveProfil) steht im
// Instanz-Skript von `routes/compare/[id]/+page.svelte`. Ausgeführt wird der
// ECHTE Funktionskörper (svelteInstanzPruefstand.ts) mit dem ECHTEN `api`
// gegen einen Ersatz-Server, der wie Go mergt — kein Test auf einen losen
// Helfer, der unverdrahtet grün bliebe.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_kopf_nutzlast_teilfeld.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SEITE = join(FRONTEND, 'src/routes/compare/[id]/+page.svelte');

// `$lib/x.js`-Importe der Seite (SvelteKit-Konvention) auf die .ts-Dateien
// auflösen — sonst fehlen ihre Bindungen im Prüfstand und der Test scheitert
// am Aufbau statt an der Zusicherung.
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-2375-kopf';
let server: GoMergeServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
});
afterEach(() => server.restore());

async function seite(): Promise<Knoten> {
	// `createSaveStatus` (Runen) ist im Pruefstand nicht herleitbar — der Hub-Controller
	// wird gesaet, wie die Seite ihn haelt (#1433: Kopf-412 geht an ihn).
	const { u } = await umgebungFuer(SEITE, { data: { preset: vollerVergleich(ID) }, hubSaveCtl: createController(ID) });
	for (const f of ['onSaveField']) {
		assert.equal(typeof u[f], 'function', `Messaufbau: \`${f}\` aus +page.svelte nicht herleitbar`);
	}
	assert.equal(typeof (u.api as Knoten)?.put, 'function', 'Messaufbau: das echte `api` fehlt in der Umgebung');
	return u;
}

function letzterPut(): Record<string, unknown> {
	const r = server.putRuempfe();
	assert.equal(r.length, 1, `Messaufbau: genau EIN PUT erwartet, gesehen ${r.length}`);
	return r[0];
}

type SaveField = (field: string, value: string, schliessen: () => void) => Promise<void>;

const KOPF_EDITS: Array<{ was: string; ausfuehren: (u: Knoten) => Promise<void>; soll: Record<string, unknown> }> = [
	{
		was: "onSaveField('name')",
		ausfuehren: async (u) => {
			await (u.onSaveField as SaveField)('name', 'Neuer Name', () => {});
		},
		soll: { name: 'Neuer Name' }
	},
	{
		was: "onSaveField('region')",
		ausfuehren: async (u) => {
			await (u.onSaveField as SaveField)('region', 'Wallis', () => {});
		},
		soll: { display_config: { region: 'Wallis' } }
	},
	{
		was: "onSaveField('profile')",
		ausfuehren: async (u) => {
			await (u.onSaveField as SaveField)('profile', 'wintersport', () => {});
		},
		soll: { profil: 'wintersport' }
	}
];

describe('Test 3 / AC-9: Kopf-Edits senden nur ihr eigenes Feld', () => {
	for (const k of KOPF_EDITS) {
		test(`${k.was}: PUT-Rumpf ist exakt ${JSON.stringify(k.soll)}`, async () => {
			const u = await seite();
			await k.ausfuehren(u);
			assert.deepEqual(
				letzterPut(),
				k.soll,
				`${k.was} darf nichts aus currentPreset mitsenden — sonst überschreibt der Kopf fremde und eigene Reiter-Werte`
			);
		});
	}
});

describe('AC-5 (#2381): ein im selben Tab gespeicherter Reiter-Wert überlebt den Kopf-Edit', () => {
	for (const k of KOPF_EDITS) {
		test(`${k.was} nach Reiter-Speicherung: Korridore und Radar-Alarm bleiben auf dem Server`, async () => {
			const u = await seite();
			// Der Reiter (CompareTabs, eigene currentPreset-Kopie) hat soeben
			// gespeichert — die Seiten-Kopie weiß davon nichts.
			server.fremdSchreiben(ID, { corridors: [], radar_alert_enabled: true });
			await k.ausfuehren(u);
			const stand = server.stand(ID);
			assert.deepEqual(stand.corridors, [], `${k.was} hat die zuvor gespeicherten Korridore zurückgeschrieben (#2381)`);
			assert.equal(stand.radar_alert_enabled, true, `${k.was} hat den zuvor gespeicherten Radar-Alarm zurückgeschrieben (#2381)`);
		});
	}
});
