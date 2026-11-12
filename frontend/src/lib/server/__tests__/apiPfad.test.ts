// Issue #2961 (FE3) — Kennungen und Durchreicher-Pfade zur Go-API.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-2, AC-3)
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/server/__tests__/apiPfad.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	kennungImPfad,
	proxyAnfrageKopfzeilen,
	proxyZielPfad,
	segmentKodieren
} from '../apiPfad.ts';

describe('AC-2: Kennungen bleiben genau ein Pfadsegment', () => {
	test('gewoehnliche Kennungen bleiben unveraendert', () => {
		assert.equal(kennungImPfad('e2e-gz-trip-123_abc'), 'e2e-gz-trip-123_abc');
	});

	test('Umlaute werden kodiert statt abgelehnt (Bestandskennungen)', () => {
		assert.equal(kennungImPfad('mühlbach'), 'm%C3%BChlbach');
	});

	test('Abfrage- und Ankerzeichen werden kodiert und veraendern die Zieladresse nicht', () => {
		const kodiert = kennungImPfad('abc?x=1#y');
		assert.equal(kodiert, 'abc%3Fx=1%23y');
		const ziel = new URL(`http://go.invalid/api/trips/${kodiert}`);
		assert.equal(ziel.search, '');
		assert.equal(ziel.hash, '');
		assert.equal(ziel.pathname, '/api/trips/abc%3Fx=1%23y');
	});

	test('Prozentzeichen werden kodiert (keine Doppel-Dekodierung bei der Go-API)', () => {
		assert.equal(kennungImPfad('a%2Fb'), 'a%252Fb');
	});

	for (const ungueltig of ['', '.', '..', '.versteckt', '../x', 'a/b', 'a\\b', 'a\x00b']) {
		test(`ungueltige Kennung ${JSON.stringify(ungueltig)} ergibt null`, () => {
			assert.equal(kennungImPfad(ungueltig), null);
		});
	}

	test('fehlende Kennung ergibt null', () => {
		assert.equal(kennungImPfad(null), null);
		assert.equal(kennungImPfad(undefined), null);
	});

	test('Pfad-Sonderzeichen wie bei Go url.PathEscape bleiben lesbar', () => {
		assert.equal(segmentKodieren('a:b@c+d,e;f=g$h&i'), 'a:b@c+d,e;f=g$h&i');
		assert.equal(segmentKodieren('a b/c'), 'a%20b%2Fc');
	});
});

describe('AC-3: der Durchreicher bildet nur gueltige Pfade unter /api/', () => {
	test('gewoehnlicher Pfad bleibt erhalten', () => {
		assert.equal(proxyZielPfad('/api/trips/abc/weather-config'), '/api/trips/abc/weather-config');
	});

	test('kodierte Umlaute bleiben dieselben Segmente', () => {
		assert.equal(proxyZielPfad('/api/locations/m%C3%BChlbach'), '/api/locations/m%C3%BChlbach');
	});

	test('ein kodiertes Fragezeichen bleibt Teil des Segments', () => {
		assert.equal(proxyZielPfad('/api/trips/a%3Fb'), '/api/trips/a%3Fb');
	});

	for (const pfad of [
		'/api/trips/..',
		'/api/trips/.',
		'/api/trips/%2e%2e',
		'/api/trips/%2E',
		'/api/trips/..%2Fauth',
		'/api/trips/a%2Fb',
		'/api/trips/a%5Cb',
		'/api/trips/a%00b',
		'/api/trips//abc',
		'/api/trips/',
		'/api/',
		'/api/trips/%E0%A4%A',
		'/apix/trips',
		'/trips/abc'
	]) {
		test(`unzulaessiger Pfad ${pfad} ergibt null`, () => {
			assert.equal(proxyZielPfad(pfad), null);
		});
	}
});

describe('AC-3: der Durchreicher gibt nur Kopfzeilen der Positivliste weiter', () => {
	const eingang = new Headers({
		'content-type': 'application/json',
		accept: 'application/json',
		'accept-language': 'de-DE',
		'if-match': '"v7"',
		'x-real-ip': '203.0.113.9',
		cookie: 'gz_session=fremd; anderes=1',
		authorization: 'Bearer x',
		'x-forwarded-for': '198.51.100.1',
		'x-forwarded-proto': 'http',
		'x-gz-core-auth': 'x',
		'x-gz-lang': 'en',
		host: 'evil.invalid',
		origin: 'https://evil.invalid'
	});

	test('erlaubte Kopfzeilen gehen durch, alle anderen nicht', () => {
		const aus = proxyAnfrageKopfzeilen(eingang, 'sitzung-1');
		assert.deepEqual(
			[...aus.keys()].sort(),
			['accept', 'accept-language', 'content-type', 'cookie', 'if-match', 'x-real-ip']
		);
		assert.equal(aus.get('if-match'), '"v7"');
		assert.equal(aus.get('x-real-ip'), '203.0.113.9');
	});

	test('als Cookie geht ausschliesslich die Sitzung aus dem Cookie-Speicher', () => {
		assert.equal(proxyAnfrageKopfzeilen(eingang, 'sitzung-1').get('cookie'), 'gz_session=sitzung-1');
	});

	test('ohne Sitzung geht gar kein Cookie weiter', () => {
		assert.equal(proxyAnfrageKopfzeilen(eingang, undefined).get('cookie'), null);
	});
});
