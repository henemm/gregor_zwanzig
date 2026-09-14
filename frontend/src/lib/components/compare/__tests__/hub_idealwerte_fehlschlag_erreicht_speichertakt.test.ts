// Issue #2317 AC-7 (Ortsvergleich): scheitert der Idealwerte-PUT im Hub, muss der
// Fehlschlag beim Speicher-Takt ankommen — sonst meldet der SaveStatus
// „gespeichert", und „Aktualisieren" laedt trotz verlorener Eingabe neu.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § AC-7
//
// Pruefstand: ECHTE SaveStatus-Instanz (Prototype-Methoden schedule/flush/doSave),
// ECHTE Hub-Warteschlange (`createPutQueue`), ECHTE Anmeldestelle
// (`erzeugeSpeicherAnmeldestelle`) und die ECHTE Commit-Funktion aus
// `korridorCommit.ts`, die CompareTabs.svelte verdrahtet. Nur der Transport ist
// ein aufzeichnendes Doppel (liefert eine Antwort bzw. wirft wie `api` offline).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/hub_idealwerte_fehlschlag_erreicht_speichertakt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { erzeugeSpeicherAnmeldestelle } from '../../../stores/aktiveSpeicherung.ts';
import { createPutQueue } from '../compareHubWizardBridge.ts';
import { baueKorridorCommit } from '../korridorCommit.ts';

type Stand = { min: number };
type Preset = { id: string; min: number };

function createTestInstance(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const fields = inst as unknown as Record<string, unknown>;
	fields.state = 'idle';
	fields.savedAt = null;
	fields.error = null;
	fields._timer = null;
	fields._pendingFn = null;
	fields._inflight = null;
	fields._lastFailed = null;
	fields._unresolvedError = null;
	return inst;
}

const OFFLINE = 'Ohne Verbindung lässt sich nichts speichern — die Änderung wurde nicht abgeschickt.';

/** Hub mit einer Idealwerte-Eingabe 30 → 45; `transport` entscheidet ueber den PUT. */
function hub(transport: (url: string, body: unknown, init?: RequestInit) => Promise<Preset>) {
	const ctl = createTestInstance();
	const ui: Stand = { min: 45 };
	let zuletzt: Stand | null = { min: 30 };
	let preset: Preset = { id: 'cp-alpen', min: 30 };
	const puts: Array<{ url: string; init?: RequestInit }> = [];
	const commit = baueKorridorCommit<Stand, Preset>({
		bereit: () => true,
		ctl: () => ctl,
		queue: createPutQueue(),
		put: (url, body, init) => {
			puts.push({ url, init });
			return transport(url, body, init);
		},
		snapshot: () => ({ ...ui }),
		zuletztGespeichert: () => zuletzt,
		merkeGespeichert: (s) => {
			zuletzt = s;
		},
		payload: (aktuell, vorher) =>
			vorher && vorher.min === aktuell.min ? null : { url: `/api/compare/presets/${preset.id}`, body: { ...preset, min: aktuell.min } },
		zuruecksetzen: (vorher) => {
			ui.min = vorher.min;
		},
		uebernehmen: (p) => {
			preset = p;
		}
	});
	return { ctl, ui, puts, commit, preset: () => preset, zuletzt: () => zuletzt };
}

describe('Issue #2317 AC-7 (Ortsvergleich): gescheiterter Idealwerte-PUT erreicht den Speicher-Takt', () => {
	test('offline im Speicher-Takt (schedule → flush): Zustand „error" mit Meldung, Rollback, Aktualisieren NICHT freigegeben', async () => {
		// GIVEN: der Hub hat eine Eingabe im Speicher-Takt (wie CorridorEditor: schedule(init => onCompareCommit(init)))
		const h = hub(async () => {
			throw Object.assign(new Error(OFFLINE), { status: 0 });
		});
		const stelle = erzeugeSpeicherAnmeldestelle();
		stelle.anmelden(h.ctl);
		h.ctl.schedule(async (init) => {
			await h.commit(init);
		});

		// WHEN: der Nutzer tippt „Aktualisieren"
		const freigabe = await stelle.wartenAufAusstehendeSpeicherung();

		// THEN
		assert.equal(h.puts.length, 1, 'Vorbedingung: der PUT wurde versucht');
		assert.equal(h.ctl.state, 'error', 'der Fehlschlag muss beim SaveStatus ankommen — nicht „gespeichert"');
		assert.equal(h.ctl.error, OFFLINE, 'die bestehende Fehlermeldung bleibt sichtbar (genau diese, keine zweite)');
		assert.equal(h.ctl.savedAt, null, 'ein gescheiterter PUT darf keinen Gespeichert-Zeitstempel setzen');
		assert.equal(freigabe, false, 'ohne gesicherte Speicherung darf die App die neue Fassung nicht laden (AC-7)');
		assert.equal(h.ui.min, 30, 'Rollback auf den zuletzt gespeicherten Stand wie bisher');
		assert.deepEqual(h.zuletzt(), { min: 30 }, 'die Baseline darf nach einem Fehlschlag nicht vorruecken');
	});

	test('Oberflaechen-Geste (direkter Aufruf, ohne Speicher-Takt): Fehleranzeige gesetzt, der Aufruf lehnt ab', async () => {
		const h = hub(async () => {
			throw Object.assign(new Error(OFFLINE), { status: 0 });
		});

		await assert.rejects(h.commit(), (e: Error) => e.message === OFFLINE, 'der Fehlschlag muss beim Aufrufer ankommen');
		assert.equal(h.ctl.state, 'error');
		assert.equal(h.ctl.error, OFFLINE);
	});

	test('Gegenprobe Erfolg: Zustand idle, Preset und Baseline uebernommen, keepalive erreicht den PUT, Aktualisieren freigegeben', async () => {
		const h = hub(async (url, body) => ({ ...(body as Preset) }));
		const stelle = erzeugeSpeicherAnmeldestelle();
		stelle.anmelden(h.ctl);
		h.ctl.schedule(async (init) => {
			await h.commit(init);
		});

		await h.ctl.flush({ keepalive: true });

		assert.equal(h.puts[0]?.init?.keepalive, true, 'die Entlade-Option muss den PUT erreichen');
		assert.equal(h.ctl.state, 'idle');
		assert.deepEqual(h.preset(), { id: 'cp-alpen', min: 45 });
		assert.deepEqual(h.zuletzt(), { min: 45 });
		assert.equal(await stelle.wartenAufAusstehendeSpeicherung(), true);
	});
});
