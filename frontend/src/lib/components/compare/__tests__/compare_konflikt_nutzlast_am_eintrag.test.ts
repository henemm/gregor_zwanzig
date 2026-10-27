// Fix-Loop 3, Issue #1433 — F201 (Compare): jeder der vier selbst speichernden
// Ortsvergleich-Reiter meldet bei 412 die GESENDETE Eigenfeld-Nutzlast an den Controller
// (Voraussetzung dafuer, dass der Hub seinen Stand fortschreibt, `registriereAbgelehnt`).
// Pruefling ist der abgelehnte PUT-Rumpf selbst: die gemeldete Nutzlast muss ihm entsprechen.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_konflikt_nutzlast_am_eintrag.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { wendeNutzlastAn } from '../../../stores/nutzlastStand.ts';
import { reiterAufbau, REITER } from '../../shared/__tests__/compareReiterAufbauPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const ID = 'cp-1433-nutzlast';
let server: GoMergeServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	await api.get(`/api/compare/presets/${ID}`);
});
afterEach(() => server.restore());

describe('Compare: die gemeldete Nutzlast ist der abgelehnte PUT-Rumpf', () => {
	for (const reiter of REITER) {
		test(`${reiter}: onAbgelehnt bekommt genau den gesendeten Rumpf; Stand ⊕ Nutzlast aendert den Stand`, async () => {
			server.fremdSchreiben(ID, { name: 'Fremder Name' });
			const start = vollerVergleich(ID) as unknown as ComparePreset;
			const h = reiterAufbau(reiter, start);
			const gemeldet: unknown[] = [];
			h.ctl.registriereAbgelehnt((n) => gemeldet.push(n));

			h.aendern();
			h.speicherung.aenderungMelden();
			await h.ctl.flush();
			const laufend = h.ctl.laufendeSpeicherung;
			if (laufend) await laufend;
			assert.equal(h.ctl.state, 'conflict', 'Vorbedingung: 412');

			const rumpf = server.putRuempfe().at(-1);
			assert.ok(rumpf, 'Messaufbau: ein abgelehnter PUT');
			assert.equal(gemeldet.length, 1, 'genau EINE Nutzlast gemeldet');
			assert.deepEqual(JSON.parse(JSON.stringify(gemeldet[0])), rumpf, 'gemeldet == gesendet');
			const neu = wendeNutzlastAn(start, gemeldet[0]);
			assert.notEqual(neu, start, 'Fortschreiben liefert eine NEUE Referenz (nie in-place)');
			assert.notDeepEqual(JSON.parse(JSON.stringify(neu)), JSON.parse(JSON.stringify(start)), 'und der Stand aendert sich');
		});
	}
});
