// TDD RED -- Issue #3423 (Punkt 4): Pruefkonto-Specs sollen vom iMac ueber
// `ssh henemm-pruefen spec-run` ohne Handarbeit laufen. Der Helfer
// e2e/pruefkontoZugang.ts waehlt Pruefkonto, Zweitkonto und Seed-IDs selbst.
//
// Spec: docs/specs/modules/feat_3423_pruefkonto_zugang_e2e.md, AC-1 bis AC-4, AC-7.
//
// Getestet wird das Verhalten der Auswahl mit Klartext-Umgebungen und einer
// aufzeichnenden API-Attrappe (reines Test-Double, keine Annahme ueber den
// Pruefling) -- kein Dateiinhalt-Check.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --experimental-test-module-mocks --test \
//     e2e/pruefkontoZugang.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
	pruefkontoZugang,
	zweitkontoZugang,
	vergleichAusPresets,
	seedIds,
	SEED_TRIP_ID,
	SEED_VERGLEICH_NAME
} from './pruefkontoZugang.ts';

const SEED_HINWEIS = /staging_pruefkonto_mockupdaten\.py[\s\S]*staging_pruefkonto_seed\.md|staging_pruefkonto_seed\.md[\s\S]*staging_pruefkonto_mockupdaten\.py/;

interface Antwort {
	status: number;
	body: unknown;
}

/** Aufzeichnende API-Attrappe: liefert feste Antworten je Pfad, merkt sich die Aufrufe. */
function apiAttrappe(antworten: Record<string, Antwort>) {
	const aufrufe: string[] = [];
	const api = {
		async get(pfad: string) {
			aufrufe.push(pfad);
			const a = antworten[pfad] ?? { status: 404, body: null };
			return {
				status: () => a.status,
				ok: () => a.status >= 200 && a.status < 300,
				json: async () => a.body
			};
		}
	};
	return { api, aufrufe };
}

// --- AC-1 / AC-7: Pruefkonto-Wahl -----------------------------------------

test('AC-1/AC-7: GZ_PRUEFKONTO_* hat Vorrang vor abweichendem GZ_AUTH_* (z. B. EN-Konto bei --lang en)', () => {
	const env = {
		GZ_PRUEFKONTO_USER: 'pruef',
		GZ_PRUEFKONTO_PASS: 'pruef-pw',
		GZ_AUTH_USER: 'en-konto',
		GZ_AUTH_PASS: 'en-pw'
	};
	assert.deepEqual(pruefkontoZugang(env), { user: 'pruef', pass: 'pruef-pw' });
});

test('AC-1: ohne GZ_PRUEFKONTO_* gilt GZ_AUTH_* (Server-Weg)', () => {
	const env = { GZ_AUTH_USER: 'pruef', GZ_AUTH_PASS: 'pruef-pw' };
	assert.deepEqual(pruefkontoZugang(env), { user: 'pruef', pass: 'pruef-pw' });
});

test('AC-1: leere Prüfkonto-Variablen zählen als nicht gesetzt', () => {
	const env = { GZ_PRUEFKONTO_USER: '', GZ_PRUEFKONTO_PASS: '', GZ_AUTH_USER: 'a', GZ_AUTH_PASS: 'b' };
	assert.deepEqual(pruefkontoZugang(env), { user: 'a', pass: 'b' });
});

test('AC-1: fehlen beide Variablenpaare, bricht die Wahl mit klarer Meldung ab', () => {
	assert.throws(() => pruefkontoZugang({}), /GZ_PRUEFKONTO_USER[\s\S]*GZ_AUTH_USER/);
});

// --- AC-2: Zweitkonto -----------------------------------------------------

test('AC-2: GZ_ZWEITKONTO_* wird genommen, wenn gesetzt', () => {
	const env = {
		GZ_PRUEFKONTO_USER: 'pruef',
		GZ_PRUEFKONTO_PASS: 'p',
		GZ_ZWEITKONTO_USER: 'zweit',
		GZ_ZWEITKONTO_PASS: 'z',
		GZ_AUTH_USER: 'default',
		GZ_AUTH_PASS: 'd'
	};
	assert.deepEqual(zweitkontoZugang(env), { user: 'zweit', pass: 'z' });
});

test('AC-2: ohne GZ_ZWEITKONTO_* gilt GZ_AUTH_*, wenn es nicht das Prüfkonto ist (iMac-Weg)', () => {
	const env = { GZ_PRUEFKONTO_USER: 'pruef', GZ_PRUEFKONTO_PASS: 'p', GZ_AUTH_USER: 'default', GZ_AUTH_PASS: 'd' };
	assert.deepEqual(zweitkontoZugang(env), { user: 'default', pass: 'd' });
});

test('AC-2: ist GZ_AUTH_* das Prüfkonto, bricht die Zweitkonto-Wahl ab', () => {
	const env = { GZ_PRUEFKONTO_USER: 'pruef', GZ_PRUEFKONTO_PASS: 'p', GZ_AUTH_USER: 'pruef', GZ_AUTH_PASS: 'p' };
	assert.throws(() => zweitkontoZugang(env), /Zweitkonto/);
});

test('AC-2: auch GZ_ZWEITKONTO_* gleich dem Prüfkonto wird abgelehnt', () => {
	const env = { GZ_PRUEFKONTO_USER: 'pruef', GZ_PRUEFKONTO_PASS: 'p', GZ_ZWEITKONTO_USER: 'pruef', GZ_ZWEITKONTO_PASS: 'p' };
	assert.throws(() => zweitkontoZugang(env), /Zweitkonto/);
});

test('AC-2: Server-Weg ohne GZ_PRUEFKONTO_* und ohne GZ_ZWEITKONTO_* (GZ_AUTH_* = Prüfkonto) bricht ab', () => {
	const env = { GZ_AUTH_USER: 'pruef', GZ_AUTH_PASS: 'p' };
	assert.throws(() => zweitkontoZugang(env), /Zweitkonto/);
});

// --- AC-3 / AC-4: Vergleichs-Auswahl --------------------------------------

test('AC-3: Vergleich „Münsterland" wird per Name aus der Preset-Liste gewählt', () => {
	assert.equal(SEED_VERGLEICH_NAME, 'Münsterland');
	const liste = [
		{ id: 'a1', name: 'Alpen' },
		{ id: 'm7', name: 'Münsterland' },
		{ id: 'x9', name: 'Münsterland-Kopie' }
	];
	assert.equal(vergleichAusPresets(liste), 'm7');
});

test('AC-4: ohne „Münsterland" bricht die Auswahl mit Seed-Skript- und Runbook-Hinweis ab', () => {
	assert.throws(() => vergleichAusPresets([{ id: 'a1', name: 'Alpen' }]), SEED_HINWEIS);
	assert.throws(() => vergleichAusPresets([]), SEED_HINWEIS);
});

// --- AC-3 / AC-4: seedIds -------------------------------------------------

test('AC-3: gesetzte ELEMENTLISTE_* gelten ohne jeden API-Aufruf', async () => {
	const { api, aufrufe } = apiAttrappe({});
	const ids = await seedIds(api, { ELEMENTLISTE_TRIP_ID: 't-env', ELEMENTLISTE_ORTE_ID: 'o-env' });
	assert.deepEqual(ids, { route: 't-env', vergleich: 'o-env' });
	assert.deepEqual(aufrufe, []);
});

test('AC-3: ohne ELEMENTLISTE_* werden Trip und Vergleich lesend gefunden', async () => {
	assert.equal(SEED_TRIP_ID, 'gz2967-gr221-mallorca');
	const { api, aufrufe } = apiAttrappe({
		'/api/trips/gz2967-gr221-mallorca': { status: 200, body: { id: 'gz2967-gr221-mallorca' } },
		'/api/compare/presets': { status: 200, body: [{ id: 'v1', name: 'Andere' }, { id: 'v2', name: 'Münsterland' }] }
	});
	const ids = await seedIds(api, {});
	assert.deepEqual(ids, { route: 'gz2967-gr221-mallorca', vergleich: 'v2' });
	assert.ok(aufrufe.includes('/api/trips/gz2967-gr221-mallorca'), 'Trip-Existenz muss geprüft werden');
});

test('AC-4: Trip-Lookup mit 404 bricht mit Seed-Skript- und Runbook-Hinweis ab', async () => {
	const { api } = apiAttrappe({
		'/api/compare/presets': { status: 200, body: [{ id: 'v2', name: 'Münsterland' }] }
	});
	await assert.rejects(() => seedIds(api, {}), SEED_HINWEIS);
});

test('AC-4: fehlender Vergleich bricht mit Seed-Hinweis ab, statt mit leerer ID weiterzulaufen', async () => {
	const { api } = apiAttrappe({
		'/api/trips/gz2967-gr221-mallorca': { status: 200, body: { id: 'gz2967-gr221-mallorca' } },
		'/api/compare/presets': { status: 200, body: [] }
	});
	await assert.rejects(() => seedIds(api, {}), SEED_HINWEIS);
});
