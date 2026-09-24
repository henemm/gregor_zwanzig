// TDD RED — Issue #2276 Scheibe S3 (Epic #2345), AC-5: scheitert ein
// Wertebereiche-Speichervorgang mit einem Speicherkonflikt (412), zeigt der
// Ortsvergleich „Nochmal speichern" (Controller-Zustand `conflict`) statt eines
// generischen Fehlers; „Nochmal speichern" sendet die Änderung erneut, endet in
// „Gespeichert", und der geänderte Wertebereich springt NICHT zurück.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md — AC-5, Design Punkt 5
// (Rollback nur bei Nicht-412, diff-basiert).
//
// Vor S3 setzte die alte Hub-Commit-Funktion bei JEDEM Fehlschlag selbst `setError()` und
// rollte immer zurück — ein 412 endete damit als „Fehler" ohne Wiederholen-Knopf.
//
// Prüfstand: ECHTES `api` gegen `fakeTripServer.ts` (ETag + 412 wie der Go-
// Server), ECHTE SaveStatus-Instanz mit Kennung {typ:'vergleich', id} — sonst
// liefe `retryConflict()` leer.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/wertebereiche_vergleich_konflikt_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import type { PutClient } from '../../tripSpeicherung.ts';
import { erstelleWertebereicheVergleichSpeicherung } from '../wertebereicheVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWs,
	korridor,
	makePreset,
	wertebereicheBedienung
} from './wertebereicheVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s3-konflikt';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau(client: PutClient = api) {
	let basis = makePreset(PRESET_ID);
	const ws = hydrierterWs(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const speicherung = erstelleWertebereicheVergleichSpeicherung({
		client,
		zustand: ws,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { ws, ctl, speicherung, bedienung: wertebereicheBedienung(ws) };
}

describe('AC-5: Speicherkonflikt beim Wertebereiche-Speichern → „Nochmal speichern" → gespeichert', () => {
	test('412 → conflict (nicht error), Wert bleibt stehen; retryConflict sendet erneut → idle, Wert bleibt', async () => {
		// GIVEN: Seite geladen (Stand bekannt), danach ändert „ein anderes Gerät" den Vergleich
		await api.get(PRESET_PFAD);
		await server.handler(PRESET_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd' }) });
		const { ws, ctl, speicherung, bedienung } = aufbau();

		// WHEN: Nutzer zieht den Wind-Korridor auf 55
		bedienung.patch('wind_max_kmh', { max: 55 });
		speicherung.aenderungMelden();
		await ctl.flush();

		// THEN (a): Konflikt, nicht generischer Fehler; keine Rücknahme in der Oberfläche
		assert.equal(puts().at(-1)?.status, 412, 'Vorbedingung: der Server muss den veralteten Stand ablehnen');
		assert.equal(ctl.state, 'conflict', 'ein 412 muss „Nochmal speichern" auslösen, nicht einen generischen Fehler');
		assert.deepEqual(
			korridor(ws, 'wind_max_kmh')?.range,
			[0, 55],
			'bei 412 darf NICHT zurückgerollt werden — die Änderung bleibt sichtbar'
		);

		// WHEN: „Nochmal speichern"
		await ctl.retryConflict();

		// THEN (b): erneut gesendet, gespeichert, Oberfläche unverändert
		const letzter = puts().at(-1)!;
		assert.equal(letzter.status, 200, 'der Wiederholungs-PUT muss durchgehen');
		assert.deepEqual(
			korridor(server.storedBody(PRESET_ID), 'wind_max_kmh')?.range,
			[0, 55],
			'der Wiederholungs-PUT muss den geänderten Korridor tragen'
		);
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date);
		assert.deepEqual(korridor(ws, 'wind_max_kmh')?.range, [0, 55], 'die Oberfläche springt nicht auf den alten Stand zurück');
	});

	test('Gegenprobe: ein Nicht-412-Fehler rollt die Wertebereich-Änderung zurück und endet in error', async () => {
		const kaputt: PutClient = {
			put: async () => {
				throw Object.assign(new Error('Serverfehler'), { status: 500, detail: 'Serverfehler' });
			}
		};
		const { ws, ctl, speicherung, bedienung } = aufbau(kaputt);

		bedienung.patch('wind_max_kmh', { max: 55 });
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(ctl.state, 'error', 'ein 500 ist kein Konflikt');
		assert.deepEqual(
			korridor(ws, 'wind_max_kmh')?.range,
			[0, 40],
			'bei einem Nicht-412-Fehler muss die Wertebereich-Änderung zurückgerollt werden'
		);
	});

	test('Rollback ist diff-basiert: eine während des Flugs geänderte Alarm-Stufe (geteiltes Feld) überlebt den Rollback', async () => {
		let gib = null as (() => void) | null;
		const langsamKaputt: PutClient = {
			put: () =>
				new Promise((_res, rej) => {
					gib = () => rej(Object.assign(new Error('Serverfehler'), { status: 500, detail: 'Serverfehler' }));
				})
		};
		const { ws, ctl, speicherung, bedienung } = aufbau(langsamKaputt);

		bedienung.patch('wind_max_kmh', { max: 55 });
		speicherung.aenderungMelden();
		const lauf = ctl.flush();
		await new Promise((r) => setTimeout(r, 0));
		// Während der PUT unterwegs ist, ändert der Alarme-Reiter dieselbe Karte:
		ws.metricAlertLevels = { ...(ws.metricAlertLevels as Record<string, string>), wind_max_kmh: 'sensibel' };
		assert.ok(gib, 'Vorbedingung: der PUT muss unterwegs sein');
		gib!();
		await lauf;

		assert.equal(ctl.state, 'error');
		assert.equal(
			(ws.metricAlertLevels as Record<string, string>).wind_max_kmh,
			'sensibel',
			'der Rollback hat eine zwischenzeitliche Alarm-Änderung am geteilten Feld überschrieben'
		);
	});
});
