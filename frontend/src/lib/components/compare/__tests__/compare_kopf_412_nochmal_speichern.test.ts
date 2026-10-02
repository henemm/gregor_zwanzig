// TDD RED — Issue #1433 Fix-Loop (CI-Befund PR #2486): die Kopf-Edits der
// Ortsvergleich-Seite (Name, Region, Aktivitaetsprofil) schreiben per `api.put` mit
// Registry-If-Match, aber am Controller vorbei. Seit #1433 bleibt nach einem 412 das
// alte If-Match stehen, bis „Nochmal speichern" laeuft — ohne Meldung an den
// Controller war der Kopf eine Sackgasse: nur „Speichern fehlgeschlagen", kein Knopf,
// jeder weitere Versuch wieder 412.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 (3/4/6), AC-10,
//       AC-18, AC-19, AC-20 (Paritaet Ortsvergleich).
//
// Gemessen am ECHTEN Instanz-Skript von `routes/compare/[id]/+page.svelte`
// (svelteInstanzPruefstand.ts), echtem `api`, echtem SaveStatus (Kennung
// `vergleich`) und dem Go-treuen Ersatz-Server — gelesen wird der SERVER-STAND.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_kopf_412_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { api } from '../../../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import type { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
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

register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-1433-kopf-412';
const PFAD = `/api/compare/presets/${ID}`;
const FREMD = { radar_alert_enabled: true, corridors: [] as unknown[] };

let server: GoMergeServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	// Seitenaufbau: die Seite kennt den Stempel dieses Standes
	await api.get(PFAD);
	// ein anderes Geraet hat inzwischen geschrieben — der Stempel der Seite ist veraltet
	server.fremdSchreiben(ID, FREMD);
});
afterEach(() => server.restore());

async function seite(): Promise<{ u: Knoten; ctl: SaveStatus }> {
	const ctl = createController(ID);
	const { u } = await umgebungFuer(SEITE, { data: { preset: vollerVergleich(ID) }, hubSaveCtl: ctl });
	for (const f of ['saveName', 'saveRegion', 'saveProfil']) {
		assert.equal(typeof u[f], 'function', `Messaufbau: \`${f}\` aus +page.svelte nicht herleitbar`);
	}
	assert.equal(u.hubSaveCtl, ctl, 'Messaufbau: die Seite muss den gesaeten Controller benutzen');
	return { u, ctl };
}

const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');

interface KopfFall {
	was: string;
	fehlerFeld: string;
	ausfuehren: (u: Knoten) => Promise<void>;
	soll: Record<string, unknown>;
	pruefe: (stand: Record<string, unknown>) => void;
}

const FAELLE: KopfFall[] = [
	{
		was: 'saveName',
		fehlerFeld: 'nameSaveError',
		ausfuehren: async (u) => {
			u.editName = 'Name von B';
			await (u.saveName as () => Promise<void>)();
		},
		soll: { name: 'Name von B' },
		pruefe: (s) => assert.equal(s.name, 'Name von B')
	},
	{
		was: 'saveRegion',
		fehlerFeld: 'regionSaveError',
		ausfuehren: async (u) => {
			u.editRegion = 'Wallis';
			await (u.saveRegion as () => Promise<void>)();
		},
		soll: { display_config: { region: 'Wallis' } },
		pruefe: (s) => assert.equal((s.display_config as Record<string, unknown>).region, 'Wallis')
	},
	{
		was: 'saveProfil',
		fehlerFeld: 'profilSaveError',
		ausfuehren: async (u) => {
			await (u.saveProfil as (v: string) => Promise<void>)('wintersport');
		},
		soll: { profil: 'wintersport' },
		pruefe: (s) => assert.equal(s.profil, 'wintersport')
	}
];

describe('AC-10/AC-20: Kopf des Ortsvergleichs — 412 zeigt „Nochmal speichern"', () => {
	for (const k of FAELLE) {
		test(`${k.was}: 412 mit If-Match ⇒ Controller \`conflict\`, kein lokaler Fehlertext, Server unveraendert`, async () => {
			const { u, ctl } = await seite();
			const stand0 = JSON.stringify(server.stand(ID));
			await k.ausfuehren(u);

			assert.equal(puts().length, 1, 'Messaufbau: genau EIN PUT');
			assert.ok(puts()[0].ifMatch, 'AC-18: der Kopf-PUT traegt If-Match');
			assert.equal(puts()[0].status, 412, 'Vorbedingung: der veraltete Stand wird abgelehnt');
			assert.equal(ctl.state, 'conflict', 'AC-10: „Nochmal speichern" muss erscheinen — sonst Sackgasse');
			assert.equal(u[k.fehlerFeld], null, 'Falle 4: der lokale Fehlertext darf die Konfliktanzeige nicht ersetzen');
			assert.equal(JSON.stringify(server.stand(ID)), stand0, 'der Server schreibt nichts');
		});

		test(`${k.was}: „Nochmal speichern" ⇒ Fremdaenderung UND eigene Aenderung auf dem Server, Nutzlast nur Eigenfeld`, async () => {
			const { u, ctl } = await seite();
			await k.ausfuehren(u);
			assert.equal(ctl.state, 'conflict', 'Vorbedingung');
			const serverStempel = server.etagOf(ID);

			await ctl.retryConflict();

			const retry = puts().at(-1)!;
			assert.equal(retry.status, 200, 'der Retry-PUT geht durch');
			assert.equal(retry.ifMatch, serverStempel, 'AC-19: der Retry traegt den Stempel des frisch geholten Standes');
			assert.deepEqual(retry.anfrage, k.soll, 'die Wiederholung sendet nur das Eigenfeld');
			const s = server.stand(ID);
			k.pruefe(s);
			assert.equal(s.radar_alert_enabled, true, 'die Fremdaenderung bleibt');
			assert.deepEqual(s.corridors, [], 'die Fremdaenderung bleibt');
			assert.equal(ctl.state, 'idle', 'die Konfliktanzeige verschwindet');
		});
	}

	test('Name 412, danach Region 412 ⇒ EIN Retry schreibt BEIDE (eigene Eintraege je Kopf-Feld)', async () => {
		const { u, ctl } = await seite();
		await FAELLE[0].ausfuehren(u);
		await FAELLE[1].ausfuehren(u);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');
		assert.equal(puts().at(-1)!.ifMatch, puts()[0].ifMatch, 'AC-18: auch der zweite Versuch traegt das ALTE If-Match');

		await ctl.retryConflict();

		const s = server.stand(ID);
		assert.equal(s.name, 'Name von B', 'die Namensaenderung ging beim Retry verloren');
		assert.equal((s.display_config as Record<string, unknown>).region, 'Wallis');
		assert.equal(s.radar_alert_enabled, true);
		assert.equal(ctl.state, 'idle');
	});

	test('waehrend „Nochmal speichern" ersetzt der Kopf `currentPreset` NICHT (sonst baut der Hub die Reiter ueber offene Eingaben neu)', async () => {
		const { u, ctl } = await seite();
		await FAELLE[0].ausfuehren(u);
		const vorher = u.currentPreset;
		await ctl.retryConflict();
		assert.equal(u.currentPreset, vorher, 'Seiten-Stand erst nach vollem Erfolg ueber den Neuaufbau (\'wiederholt\')');
		assert.equal(u.isEditingName, false, 'das Eingabefeld schliesst nach erfolgreichem Retry');
	});

	test('Gegenprobe ohne Fremdschreiber: Kopf speichert normal, Seite uebernimmt die Antwort', async () => {
		// frischen Stempel holen — kein Konflikt
		await api.get(PFAD);
		const stempel = getKnownEtag(ID);
		const { u, ctl } = await seite();
		await FAELLE[0].ausfuehren(u);
		assert.equal(puts().at(-1)!.ifMatch, stempel);
		assert.equal(puts().at(-1)!.status, 200);
		assert.equal((u.currentPreset as Record<string, unknown>).name, 'Name von B');
		assert.equal(ctl.state, 'idle');
		assert.equal(u.nameSaveError, null);
	});
});
