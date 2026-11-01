// Issue #2660 (i18n F11, Epic #2644) — AC-2: die Fehlermeldungen, die `api.ts`
// selbst baut (Zeitlimit, Schreibsperre ohne Verbindung, Sitzung abgelaufen,
// Datenexport-Download), folgen der Sprache zum Zeitpunkt des Aufrufs; Deutsch
// bleibt wortgleich (Golden-Literale aus dem Quelltext vor der Umstellung).
//
// Echte `api`-Aufrufe. `window` gibt es unter node:test nicht: ein EventTarget
// mit `location` steht dafuer (api.ts meldet den Abrufausgang per Ereignis und
// lenkt bei 401 auf /login um). Der fetch-Ersatz verhaelt sich wie der Browser
// (lehnt beim Abbruch-Signal ab, liefert echte `Response`-Objekte).
// Spec: docs/specs/modules/i18n_f11_bausteine_ts_2660.md
//
//   cd frontend && npm test -- src/lib/__tests__/api_fehlertexte_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';

const ort = { pathname: '/trips/t1', search: '', href: '' };
const windowStandIn = Object.assign(new EventTarget(), { location: ort });
(globalThis as { window?: unknown }).window = windowStandIn;

type Modul = typeof import('../api.ts');
let modul: Modul;
let i18n: typeof import('../i18n/index.ts');
const echtesFetch = globalThis.fetch;

before(async () => {
	modul = await import('../api.ts');
	i18n = await import('../i18n/index.ts');
});

afterEach(() => {
	(globalThis as { fetch: unknown }).fetch = echtesFetch;
	i18n.locale.set('de');
	modul.setzeStandardZeitlimit(modul.STANDARD_ZEITLIMIT_MS);
	windowStandIn.dispatchEvent(new CustomEvent('gz-schreibsperre', { detail: { gesperrt: false } }));
});

function fetchNie(): void {
	(globalThis as { fetch: unknown }).fetch = (_p: unknown, init?: RequestInit) =>
		new Promise<Response>((_res, rej) => {
			init?.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')), {
				once: true
			});
		});
}

function fetchAntwort(status: number, text: string): void {
	(globalThis as { fetch: unknown }).fetch = async () =>
		new Response(text, { status, headers: { 'Content-Type': 'application/json' } });
}

async function meldung(lauf: () => Promise<unknown>): Promise<string> {
	try {
		await lauf();
	} catch (e) {
		return (e as Error).message;
	}
	assert.fail('Aufruf haette scheitern muessen');
}

const zeitlimit = () => {
	fetchNie();
	modul.setzeStandardZeitlimit(15);
	return meldung(() => modul.api.get('/api/trips/t1'));
};
const gesperrt = () => {
	windowStandIn.dispatchEvent(new CustomEvent('gz-schreibsperre', { detail: { gesperrt: true } }));
	return meldung(() => modul.api.put('/api/trips/t1', { a: 1 }));
};
const abgelaufen = () => {
	fetchAntwort(401, '{"error":"unauthorized"}');
	return meldung(() => modul.api.get('/api/trips'));
};
const download = () => {
	fetchAntwort(500, 'kaputt');
	return meldung(() => modul.downloadUserDataExport());
};

describe('AC-2: Fehlermeldungen aus api.ts in beiden Sprachen', () => {
	test('Deutsch: wortgleich wie vor der Umstellung', { timeout: 2000 }, async () => {
		i18n.locale.set('de');
		assert.equal(await zeitlimit(), 'Die Verbindung ist zu langsam — der Server hat nicht rechtzeitig geantwortet.');
		assert.equal(
			await gesperrt(),
			'Ohne Verbindung lässt sich nichts speichern — die Änderung wurde nicht abgeschickt.'
		);
		assert.equal(await abgelaufen(), 'Sitzung abgelaufen — bitte neu anmelden.');
		assert.equal(await download(), 'Download fehlgeschlagen (500): kaputt');
	});

	test('Englisch: Texte aus dem Katalog, kein deutscher Text', { timeout: 2000 }, async () => {
		i18n.locale.set('en');
		assert.equal(await zeitlimit(), i18n.trFor('en', 'fehler.verbindung.zeitlimit'));
		assert.equal(await gesperrt(), i18n.trFor('en', 'fehler.verbindung.schreiben_offline'));
		assert.equal(await abgelaufen(), i18n.trFor('en', 'fehler.sitzung.abgelaufen'));
		assert.equal(
			await download(),
			i18n.trFor('en', 'fehler.download.fehlgeschlagen', { status: 500, detail: 'kaputt' })
		);
		for (const m of [await zeitlimit(), await gesperrt(), await abgelaufen()]) {
			assert.doesNotMatch(m, /[äöüß]|\b(nicht|bitte|Sitzung|Verbindung)\b/i, m);
		}
	});

	test('Sprachwechsel ohne Neuladen: dieselbe Modulinstanz folgt der neuen Sprache', { timeout: 2000 }, async () => {
		i18n.locale.set('de');
		const vorher = await abgelaufen();
		i18n.locale.set('en');
		const nachher = await abgelaufen();
		assert.notEqual(vorher, nachher);
		assert.equal(nachher, i18n.trFor('en', 'fehler.sitzung.abgelaufen'));
	});

	test('Zeitlimit behaelt Fehlername, Sitzung den Status 401, Sperre den Status 0', { timeout: 2000 }, async () => {
		i18n.locale.set('en');
		fetchNie();
		modul.setzeStandardZeitlimit(15);
		await assert.rejects(modul.api.get('/x'), (e: Error & { status?: number }) => e.name === 'TimeoutError' && e.status === undefined);
		fetchAntwort(401, '{}');
		await assert.rejects(modul.api.get('/x'), (e: { status?: number }) => e.status === 401);
		windowStandIn.dispatchEvent(new CustomEvent('gz-schreibsperre', { detail: { gesperrt: true } }));
		await assert.rejects(modul.api.post('/x', {}), (e: { status?: number }) => e.status === 0);
	});
});
