// Issue #2317 AC-7 (Ortsvergleich): scheitert der Idealwerte-PUT im Hub, muss der
// Fehlschlag beim Speicher-Takt ankommen — sonst meldet der SaveStatus
// „gespeichert", und „Aktualisieren" laedt trotz verlorener Eingabe neu.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § AC-7
//
// Issue #2276 S3: umgehaengt von der alten Hub-Commit-Funktion auf den heute
// einzigen Speicherweg des Wertebereiche-Reiters
// (`shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`). Die
// Zusicherungen an den Speicher-Takt bleiben unveraendert; entfallen ist nur
// der Fall „Oberflaechen-Geste ohne Speicher-Takt" — diesen zweiten Weg gibt es
// nicht mehr (Spec rework_2276_s3_wertebereiche, Design Punkt 3).
//
// Pruefstand: ECHTE SaveStatus-Instanz, ECHTE Hub-Warteschlange, ECHTE
// Anmeldestelle (`erzeugeSpeicherAnmeldestelle`), ECHTE Orchestrierung. Nur der
// Transport ist ein aufzeichnendes Doppel (liefert eine Antwort bzw. wirft wie
// `api` offline).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/compare/__tests__/hub_idealwerte_fehlschlag_erreicht_speichertakt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { erzeugeSpeicherAnmeldestelle } from '../../../stores/aktiveSpeicherung.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../compareHubPersistenz.ts';
import { erstelleWertebereicheVergleichSpeicherung } from '../../shared/corridor-editor/wertebereicheVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWs,
	korridor,
	makePreset,
	wertebereicheBedienung
} from '../../shared/corridor-editor/__tests__/wertebereicheVergleichPruefstand.ts';

const OFFLINE = 'Ohne Verbindung lässt sich nichts speichern — die Änderung wurde nicht abgeschickt.';

/** Hub mit einer Idealwerte-Eingabe (Wind max 40 → 55); `transport` entscheidet ueber den PUT. */
function hub(transport: (url: string, body: unknown, init?: RequestInit) => Promise<ComparePreset>) {
	let preset = makePreset('cp-alpen');
	const ws = hydrierterWs(preset);
	const ctl = createController('cp-alpen');
	const queue = createPutQueue();
	const puts: Array<{ url: string; init?: RequestInit }> = [];
	const speicherung = erstelleWertebereicheVergleichSpeicherung({
		client: {
			put: <T>(url: string, body: unknown, init?: RequestInit) => {
				puts.push({ url, init });
				return transport(url, body, init) as Promise<T>;
			}
		},
		zustand: ws,
		preset: () => preset,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p) => {
			preset = p;
		},
		saveController: ctl
	});
	wertebereicheBedienung(ws).patch('wind_max_kmh', { max: 55 });
	speicherung.aenderungMelden();
	return { ctl, ws, puts, speicherung, preset: () => preset };
}

describe('Issue #2317 AC-7 (Ortsvergleich): gescheiterter Idealwerte-PUT erreicht den Speicher-Takt', () => {
	test('offline im Speicher-Takt (schedule → flush): Zustand „error" mit Meldung, Rollback, Aktualisieren NICHT freigegeben', async () => {
		const h = hub(async () => {
			throw Object.assign(new Error(OFFLINE), { status: 0 });
		});
		const stelle = erzeugeSpeicherAnmeldestelle();
		stelle.anmelden(h.ctl);

		// WHEN: der Nutzer tippt „Aktualisieren"
		const freigabe = await stelle.wartenAufAusstehendeSpeicherung();

		assert.equal(h.puts.length, 1, 'Vorbedingung: der PUT wurde versucht');
		assert.equal(h.ctl.state, 'error', 'der Fehlschlag muss beim SaveStatus ankommen — nicht „gespeichert"');
		assert.equal(h.ctl.error, OFFLINE, 'die bestehende Fehlermeldung bleibt sichtbar (genau diese, keine zweite)');
		assert.equal(h.ctl.savedAt, null, 'ein gescheiterter PUT darf keinen Gespeichert-Zeitstempel setzen');
		assert.equal(freigabe, false, 'ohne gesicherte Speicherung darf die App die neue Fassung nicht laden (AC-7)');
		assert.deepEqual(korridor(h.ws, 'wind_max_kmh')?.range, [0, 40], 'Rollback auf den zuletzt gespeicherten Stand wie bisher');

		// Die Baseline darf nach einem Fehlschlag nicht vorruecken: dieselbe Eingabe
		// erneut gemeldet muss wieder einen Speichervorgang einplanen.
		wertebereicheBedienung(h.ws).patch('wind_max_kmh', { max: 55 });
		h.speicherung.aenderungMelden();
		assert.equal(h.ctl.hasPending, true, 'die Baseline ist nach dem Fehlschlag vorgerueckt');
		h.ctl.cancel();
	});

	test('Gegenprobe Erfolg: Zustand idle, Preset und Baseline uebernommen, keepalive erreicht den PUT, Aktualisieren freigegeben', async () => {
		const h = hub(async (_url, body) => ({ ...(body as ComparePreset) }));
		const stelle = erzeugeSpeicherAnmeldestelle();
		stelle.anmelden(h.ctl);

		await h.ctl.flush({ keepalive: true });

		assert.equal(h.puts[0]?.init?.keepalive, true, 'die Entlade-Option muss den PUT erreichen');
		assert.equal(h.ctl.state, 'idle');
		assert.deepEqual(korridor(h.preset(), 'wind_max_kmh')?.range, [0, 55], 'die Basis folgt der Server-Antwort');
		h.speicherung.aenderungMelden();
		assert.equal(h.ctl.hasPending, false, 'die Baseline muss nach Erfolg vorgerueckt sein');
		assert.equal(await stelle.wartenAufAusstehendeSpeicherung(), true);
	});
});
