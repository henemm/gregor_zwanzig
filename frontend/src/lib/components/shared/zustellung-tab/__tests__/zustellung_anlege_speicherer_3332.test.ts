// TDD RED — Issue #3332 (Teil D1 von #3307, Epic #3122): Anlege-Speicherer des Reiters „Zustellung“.
// Spec docs/specs/modules/feat_3332_zustellung_anlegen_trip.md, Test Plan Nr. 1 (AC-2, AC-3, AC-5).
//
// FESTGELEGTE SCHNITTSTELLE (shared/zustellung-tab/zustellungSpeicherung.ts):
//   erstelleZustellungAnlegeSpeicherer({ context, basis, anlegen })
//       context: 'route' | 'vergleich'
//       basis:   ZustellungStand                     // Anlege-Startstand des Reiters
//       anlegen: (m: { stand: ZustellungStand; nutzlast: ZustellungNutzlast }) => void
//     -> { aenderungMelden(jetzt: ZustellungStand): void }
//   `aenderungMelden(jetzt)` ruft `anlegen` sofort genau einmal mit dem gemeldeten Stand und
//   `nutzlast = zustellungNutzlast(context, basis, jetzt)` — dieselbe reine Funktion wie im Hub, kein
//   zweiter Nutzlast-Baustein. Das Delta gilt immer gegen den Anlege-Start (nicht gegen die letzte
//   Meldung), denn im Anlegen wird nichts gespeichert. Kein PUT, kein Netz, kein saveController.
//
// Echte Funktionen, keine Doubles; `anlegen` ist der Rückkanal selbst (sammelt nur, was ankommt).
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/zustellung_anlege_speicherer_3332.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import * as S from '../zustellungSpeicherung.ts';
import { standAusPreset, standAusTrip, type ZustellungStand } from '../zustellungModell.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/** Eintrittstrip wie im Anlegen: kein gespeicherter Stand, nur der Neuanlage-Rahmen. */
const START_TRIP: J = { id: '__new__', name: 'Neu', stages: [], display_config: {}, report_config: undefined };
const START_PRESET: J = { id: '__new__', name: 'Neu', location_ids: [] };

function speicherer(context: 'route' | 'vergleich', basis: ZustellungStand) {
	const f = (S as J).erstelleZustellungAnlegeSpeicherer;
	assert.equal(typeof f, 'function', 'zustellungSpeicherung.ts exportiert keinen Anlege-Speicherer `erstelleZustellungAnlegeSpeicherer`');
	const meldungen: J[] = [];
	const sp = f({ context, basis, anlegen: (m: J) => meldungen.push(m) });
	assert.equal(typeof sp?.aenderungMelden, 'function', 'Anlege-Speicherer ohne aenderungMelden');
	return { sp, meldungen };
}

const klon = <T>(v: T): T => JSON.parse(JSON.stringify(v));

let netz: string[] = [];
const echtesFetch = globalThis.fetch;
beforeEach(() => {
	netz = [];
	globalThis.fetch = (async (url: unknown, init?: { method?: string }) => {
		netz.push(`${init?.method ?? 'GET'} ${String(url)}`);
		throw new Error('kein Netz im Anlegen');
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = echtesFetch;
});

describe('#3332 Test 1 (AC-2, AC-3, AC-5): Anlege-Speicherer meldet {stand, nutzlast} statt zu speichern', () => {
	test('Trip: Zeiten, Kanäle, Dringlichkeit, Stille, Cooldown geändert — eine Meldung, Nutzlast nur Geändertes, kein Netz', () => {
		const basis = standAusTrip(START_TRIP);
		const { sp, meldungen } = speicherer('route', basis);
		const jetzt: ZustellungStand = {
			...klon(basis),
			morgenZeit: '06:45',
			abendAn: false,
			briefing: { ...basis.briefing, telegram: true },
			alarme: { ...basis.alarme, sms: true },
			dringlichkeit: { ...basis.dringlichkeit, telegram: 'HIGH' },
			stilleAn: true,
			stilleVon: '22:30',
			stilleBis: '06:15',
			cooldown: 45
		};
		sp.aenderungMelden(jetzt);
		assert.equal(meldungen.length, 1, 'genau eine Meldung je Änderung');
		assert.deepEqual(meldungen[0].stand, jetzt, 'gemeldeter Stand weicht vom bedienten ab');
		assert.deepEqual(meldungen[0].nutzlast, S.zustellungNutzlast('route', basis, jetzt), 'Nutzlast nicht aus derselben reinen Funktion');
		// Gegenprobe an Werten (nicht nur Gleichheit zweier Aufrufe derselben Funktion):
		const v = meldungen[0].nutzlast.versand?.report_config;
		assert.equal(v?.morning_time, '06:45:00');
		assert.equal(v?.evening_enabled, false);
		assert.equal(v?.send_telegram, true);
		assert.equal('send_email' in (v ?? {}), false, 'unverändertes Feld in der Nutzlast');
		const a = meldungen[0].nutzlast.alarme;
		assert.equal(a?.alert_channel_thresholds?.telegram, 'HIGH');
		assert.equal(a?.alert_channels?.sms, true);
		assert.equal(a?.alert_quiet_from, '22:30');
		assert.equal(a?.alert_quiet_to, '06:15');
		assert.equal(a?.alert_cooldown_minutes, 45);
		assert.deepEqual(netz, [], 'Anlege-Speicherer greift aufs Netz zu');
	});

	test('nur Geändertes: eine Uhrzeit allein ergibt nur den Versand-Teil, Alarme null', () => {
		const basis = standAusTrip(START_TRIP);
		const { sp, meldungen } = speicherer('route', basis);
		sp.aenderungMelden({ ...klon(basis), abendZeit: '19:15' });
		assert.deepEqual(meldungen[0].nutzlast, { versand: { report_config: { evening_time: '19:15:00' } }, alarme: null });
	});

	test('Delta immer gegen den Anlege-Start, nicht gegen die letzte Meldung (im Anlegen wird nichts gespeichert)', () => {
		const basis = standAusTrip(START_TRIP);
		const { sp, meldungen } = speicherer('route', basis);
		sp.aenderungMelden({ ...klon(basis), morgenZeit: '06:45' });
		sp.aenderungMelden({ ...klon(basis), morgenZeit: '06:45', cooldown: 30 });
		assert.equal(meldungen.length, 2);
		assert.equal(meldungen[1].nutzlast.versand?.report_config?.morning_time, '06:45:00', 'zweite Meldung verliert die erste Änderung');
		assert.equal(meldungen[1].nutzlast.alarme?.alert_cooldown_minutes, 30);
	});

	test('zurück auf den Start: Meldung mit leerer Nutzlast (kein Rest der früheren Änderung)', () => {
		const basis = standAusTrip(START_TRIP);
		const { sp, meldungen } = speicherer('route', basis);
		sp.aenderungMelden({ ...klon(basis), cooldown: 30 });
		sp.aenderungMelden(klon(basis));
		assert.deepEqual(meldungen.at(-1).nutzlast, { versand: null, alarme: null });
		assert.deepEqual(meldungen.at(-1).stand, basis);
	});

	test('rasterfremde Uhrzeit (06:50): Stand wird gemeldet, die Nutzlast trägt keine Uhrzeit (AC-7)', () => {
		const basis = standAusTrip(START_TRIP);
		const { sp, meldungen } = speicherer('route', basis);
		sp.aenderungMelden({ ...klon(basis), morgenZeit: '06:50' });
		assert.equal(meldungen[0].stand.morgenZeit, '06:50');
		assert.equal(meldungen[0].nutzlast.versand, null, 'rasterfremde Uhrzeit in der Nutzlast');
	});

	test('die Meldung hängt nicht am Objekt des Aufrufers (spätere Mutation ändert die Meldung nicht)', () => {
		const basis = standAusTrip(START_TRIP);
		const { sp, meldungen } = speicherer('route', basis);
		const jetzt = { ...klon(basis), cooldown: 30 };
		sp.aenderungMelden(jetzt);
		jetzt.cooldown = 99;
		assert.equal(meldungen[0].stand.cooldown, 30, 'Meldung teilt das Objekt mit dem Aufrufer');
	});

	test('Ortsvergleich (vorbereitet für D2): Felder top-level, gleiche reine Funktion', () => {
		const basis = standAusPreset(START_PRESET);
		const { sp, meldungen } = speicherer('vergleich', basis);
		const jetzt = { ...klon(basis), morgenZeit: '06:30', briefing: { ...basis.briefing, email: false } };
		sp.aenderungMelden(jetzt);
		assert.deepEqual(meldungen[0].nutzlast, S.zustellungNutzlast('vergleich', basis, jetzt));
		assert.equal(meldungen[0].nutzlast.versand?.morning_time, '06:30:00');
		assert.equal(meldungen[0].nutzlast.versand?.send_email, false);
		assert.deepEqual(netz, []);
	});
});
