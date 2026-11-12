// Issue #2961 (FE2) — Inhaltsspeicher des Service Workers: Mandantenwechsel,
// Lesen nur aus dem Speicher des zuletzt angemeldeten Mandanten, Hoechstalter,
// Raeumen bei echtem 401.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-8 bis AC-11)
//       docs/specs/modules/pwa_offline_ansicht_letzter_stand.md · ADR-0063
//
// Die Regeln laufen gegen einen In-Memory-Gerätespeicher (geraetespeicherDoppel.ts),
// der wirklich speichert und liefert. Der Browser-Nachweis mit echtem Worker
// steht in e2e/pwa-offline-sperre-und-mandant.spec.ts.
//
//   cd frontend && npm test -- src/lib/pwa/__tests__/datenspeicher_mandant_und_hoechstalter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { GeraetespeicherDoppel } from './geraetespeicherDoppel.ts';
import {
	ABLAGE_HEADER,
	DATEN_PRAEFIX,
	HOECHSTALTER_MS,
	INDEX_SCHLUESSEL,
	MANDANT_HEADER,
	aktuellerDatenspeicher,
	alleAbgelaufenenEntfernen,
	datenspeicherLoeschen,
	istAbgelaufen,
	nachMandantRaeumen,
	vorgehalteneAnsichten,
	vorgehalteneAntwort
} from '../datenspeicher.ts';

const JETZT = Date.parse('2026-11-12T12:00:00Z');
const TAG = 24 * 60 * 60 * 1000;
const PROGRAMM = 'gz-1234567890';

function iso(vorMs: number): string {
	return new Date(JETZT - vorMs).toISOString();
}

/** Legt eine Ansicht so ab, wie der Worker es tut (Seite, Daten, Buchfuehrung). */
async function ablegen(
	speicher: GeraetespeicherDoppel,
	mandant: string,
	pfad: string,
	stand: string,
	mitAblageHeader = true
): Promise<void> {
	const cache = await speicher.open(DATEN_PRAEFIX + mandant);
	const kopf = (typ: string): Record<string, string> =>
		mitAblageHeader ? { 'content-type': typ, [ABLAGE_HEADER]: stand } : { 'content-type': typ };
	await cache.put(pfad, new Response(`<html>${pfad}</html>`, { headers: kopf('text/html') }));
	await cache.put(`${pfad}/__data.json`, new Response('{}', { headers: kopf('application/json') }));
	const alt = await cache.match(INDEX_SCHLUESSEL);
	const eintraege = alt ? ((await alt.json()) as unknown[]) : [];
	eintraege.push({ pfad, titel: pfad, stand });
	await cache.put(INDEX_SCHLUESSEL, new Response(JSON.stringify(eintraege)));
}

function antwortVon(mandant: string | null): Response {
	return new Response('<html></html>', {
		headers: mandant ? { [MANDANT_HEADER]: mandant, 'content-type': 'text/html' } : {}
	});
}

describe('AC-8: jede Antwort mit Mandantenkennung raeumt fremde Inhaltsspeicher', () => {
	test('Antwort von B (auch ausserhalb der Positivliste) loescht As Speicher, Programm bleibt', async () => {
		const speicher = new GeraetespeicherDoppel();
		await speicher.open(PROGRAMM);
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));

		await nachMandantRaeumen(speicher, antwortVon('mandant-b'));

		assert.deepEqual(await speicher.keys(), [PROGRAMM]);
	});

	test('Antwort desselben Mandanten laesst seinen Speicher stehen', async () => {
		const speicher = new GeraetespeicherDoppel();
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));
		await nachMandantRaeumen(speicher, antwortVon('mandant-a'));
		assert.deepEqual(await speicher.keys(), [DATEN_PRAEFIX + 'mandant-a']);
	});

	test('Antwort ohne Kennung (abgemeldet, oeffentlich) raeumt nichts', async () => {
		const speicher = new GeraetespeicherDoppel();
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));
		await nachMandantRaeumen(speicher, antwortVon(null));
		assert.deepEqual(await speicher.keys(), [DATEN_PRAEFIX + 'mandant-a']);
	});
});

describe('AC-9: gelesen wird nur aus dem Speicher des zuletzt angemeldeten Mandanten', () => {
	test('liegen zwei Inhaltsspeicher, wird aus keinem geliefert', async () => {
		const speicher = new GeraetespeicherDoppel();
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));
		await ablegen(speicher, 'mandant-b', '/trips/t2', iso(TAG));

		assert.equal(await aktuellerDatenspeicher(speicher), null);
		assert.equal(await vorgehalteneAntwort(speicher, '/trips/t1', JETZT), undefined);
		assert.equal(await vorgehalteneAntwort(speicher, '/trips/t2', JETZT), undefined);
		assert.deepEqual(await vorgehalteneAnsichten(speicher, JETZT), []);
	});

	test('nach dem Raeumen durch Bs Antwort liefert nur noch Bs Speicher', async () => {
		const speicher = new GeraetespeicherDoppel();
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));
		await ablegen(speicher, 'mandant-b', '/trips/t2', iso(TAG));
		await nachMandantRaeumen(speicher, antwortVon('mandant-b'));

		assert.equal(await vorgehalteneAntwort(speicher, '/trips/t1', JETZT), undefined);
		const b = await vorgehalteneAntwort(speicher, '/trips/t2', JETZT);
		assert.equal(await b?.text(), '<html>/trips/t2</html>');
		assert.deepEqual(
			(await vorgehalteneAnsichten(speicher, JETZT)).map((e) => e.pfad),
			['/trips/t2']
		);
	});

	test('ein Treffer im Programm-Speicher wird nie als Inhalt geliefert', async () => {
		const speicher = new GeraetespeicherDoppel();
		const programm = await speicher.open(PROGRAMM);
		await programm.put('/trips/t9', new Response('fremd'));
		assert.equal(await vorgehalteneAntwort(speicher, '/trips/t9', JETZT), undefined);
	});
});

describe('AC-10: nichts Vorgehaltenes ist aelter als 30 Tage', () => {
	test('Grenze: genau 30 Tage gilt noch, darueber nicht; unlesbar gilt als abgelaufen', () => {
		assert.equal(HOECHSTALTER_MS, 30 * TAG);
		assert.equal(istAbgelaufen(iso(30 * TAG), JETZT), false);
		assert.equal(istAbgelaufen(iso(30 * TAG + 1), JETZT), true);
		assert.equal(istAbgelaufen('kein-datum', JETZT), true);
		assert.equal(istAbgelaufen(null, JETZT), true);
	});

	test('beim Zugriff: eine 31 Tage alte Ansicht wird nicht geliefert und entfernt', async () => {
		const speicher = new GeraetespeicherDoppel();
		await ablegen(speicher, 'mandant-a', '/trips/alt', iso(31 * TAG));
		await ablegen(speicher, 'mandant-a', '/trips/neu', iso(2 * TAG));

		assert.equal(await vorgehalteneAntwort(speicher, '/trips/alt', JETZT), undefined);
		assert.equal(await vorgehalteneAntwort(speicher, '/trips/alt/__data.json', JETZT), undefined);
		assert.ok(await vorgehalteneAntwort(speicher, '/trips/neu', JETZT));
		assert.deepEqual(
			speicher.cache(DATEN_PRAEFIX + 'mandant-a')?.pfade(),
			[INDEX_SCHLUESSEL, '/trips/neu', '/trips/neu/__data.json'].sort()
		);
		assert.deepEqual(
			(await vorgehalteneAnsichten(speicher, JETZT)).map((e) => e.pfad),
			['/trips/neu']
		);
	});

	test('beim Aktivieren: Abgelaufenes faellt in jedem Inhaltsspeicher, Programm bleibt', async () => {
		const speicher = new GeraetespeicherDoppel();
		const programm = await speicher.open(PROGRAMM);
		await programm.put('/_app/x.js', new Response('js'));
		await ablegen(speicher, 'mandant-a', '/compare/c1', iso(40 * TAG));
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));

		await alleAbgelaufenenEntfernen(speicher, JETZT);

		assert.deepEqual(
			speicher.cache(DATEN_PRAEFIX + 'mandant-a')?.pfade(),
			[INDEX_SCHLUESSEL, '/trips/t1', '/trips/t1/__data.json'].sort()
		);
		assert.deepEqual(speicher.cache(PROGRAMM)?.pfade(), ['/_app/x.js']);
	});

	test('Bestand ohne eigenen Ablagezeitpunkt richtet sich nach dem Stand seiner Ansicht', async () => {
		const speicher = new GeraetespeicherDoppel();
		await ablegen(speicher, 'mandant-a', '/trips/frisch', iso(TAG), false);
		await ablegen(speicher, 'mandant-a', '/trips/alt', iso(45 * TAG), false);

		assert.ok(await vorgehalteneAntwort(speicher, '/trips/frisch/__data.json', JETZT));
		assert.equal(await vorgehalteneAntwort(speicher, '/trips/alt/__data.json', JETZT), undefined);
	});

	test('eine Daten-Antwort ohne Zeitpunkt und ohne Ansicht in der Buchfuehrung wird nicht geliefert', async () => {
		const speicher = new GeraetespeicherDoppel();
		const cache = await speicher.open(DATEN_PRAEFIX + 'mandant-a');
		await cache.put('/trips/lose/__data.json', new Response('{}'));
		assert.equal(await vorgehalteneAntwort(speicher, '/trips/lose/__data.json', JETZT), undefined);
	});
});

describe('AC-11: bei echtem 401 fallen die Inhaltsspeicher, das Programm bleibt', () => {
	test('datenspeicherLoeschen entfernt alle gz-daten-*, laesst gz-<version> stehen', async () => {
		const speicher = new GeraetespeicherDoppel();
		await speicher.open(PROGRAMM);
		await ablegen(speicher, 'mandant-a', '/trips/t1', iso(TAG));
		await ablegen(speicher, 'mandant-b', '/trips/t2', iso(TAG));

		await datenspeicherLoeschen(speicher);

		assert.deepEqual(await speicher.keys(), [PROGRAMM]);
	});
});
