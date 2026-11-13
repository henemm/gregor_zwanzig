// Issue #2961 (F010) — die Bearbeiten-Umleitungen /trips/<id>/edit und
// /compare/<id>/edit setzen Kennung und Reiter kodiert in die Zieladresse:
// ein Wert bleibt genau ein Pfadsegment bzw. genau ein Abfragewert.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-2)
// Ruft die ECHTEN load-Funktionen auf; `redirect()` wirft ein Objekt mit
// `status`/`location`.
//
//   cd frontend && npm test -- src/routes/bearbeiten_umleitung_kodiert.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

type Load = (e: { params: { id: string }; url: URL }) => unknown;

async function umleitung(route: string, id: string, suche = ''): Promise<{ status: number; location: string }> {
	const { load } = (await import(fileURLToPath(new URL(route, import.meta.url)))) as { load: Load };
	try {
		await load({ params: { id }, url: new URL(`https://x.invalid/x/edit${suche}`) });
	} catch (e) {
		const r = e as { status?: number; location?: string };
		assert.equal(typeof r.status, 'number', `kein Redirect: ${String(e)}`);
		return { status: r.status!, location: r.location! };
	}
	assert.fail('load leitet nicht um');
}

const TRIP = './trips/[id]/edit/+page.server.ts';
const VERGLEICH = './compare/[id]/edit/+page.server.ts';

describe('AC-2: Bearbeiten-Umleitungen kodieren Kennung und Reiter', () => {
	test('Trip: Kennung mit Leerzeichen, Abfrage- und Trennzeichen bleibt ein Pfadsegment', async () => {
		const r = await umleitung(TRIP, 'a b?x=1/..');
		assert.equal(r.status, 307);
		assert.equal(r.location, '/trips/a%20b%3Fx%3D1%2F..');
		const ziel = new URL(r.location, 'https://x.invalid');
		assert.equal(ziel.pathname, '/trips/a%20b%3Fx%3D1%2F..');
		assert.equal(ziel.search, '');
	});

	test('Trip: der Reiter wird als genau ein Abfragewert uebernommen', async () => {
		const r = await umleitung(TRIP, 'khw', `?tab=${encodeURIComponent('etappen&admin=1#x')}`);
		const ziel = new URL(r.location, 'https://x.invalid');
		assert.equal(ziel.pathname, '/trips/khw');
		assert.deepEqual([...ziel.searchParams.keys()], ['tab']);
		assert.equal(ziel.searchParams.get('tab'), 'etappen&admin=1#x');
		assert.equal(ziel.hash, '');
	});

	test('Vergleich: Kennung mit Abfrage- und Trennzeichen bleibt ein Pfadsegment', async () => {
		const r = await umleitung(VERGLEICH, 'v 1?x=1/../a');
		assert.equal(r.status, 307);
		assert.equal(r.location, '/compare/v%201%3Fx%3D1%2F..%2Fa');
	});

	test('gewoehnliche Kennungen bleiben unveraendert (Gegenprobe)', async () => {
		assert.equal((await umleitung(TRIP, 'khw-2026', '?tab=wertebereiche')).location, '/trips/khw-2026?tab=wertebereiche');
		assert.equal((await umleitung(VERGLEICH, 'cp-1')).location, '/compare/cp-1');
	});
});
