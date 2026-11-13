// Issue #2961 (FE2e) — `/login?abgemeldet=1` raeumt den Offline-Speicher nur,
// wenn keine gueltige Sitzung mehr besteht.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-12)
//       docs/specs/modules/pwa_installierbar_offline_start.md (AC-11, AC-12)
//
// Zwei Stellen: die load-Funktion der Anmeldeseite fragt die Go-API (hier ein
// echter lokaler HTTP-Server), und `abmeldungLiegtVor` entscheidet daraus mit
// dem Abmelde-Merker im Sitzungsspeicher (echtes In-Memory-Storage-Doppel).
//
//   cd frontend && npm test -- src/routes/login/__tests__/abmelde_merkmal_nur_ohne_sitzung.test.ts

import { test, describe, after, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	installiereSitzungsspeicher,
	entferneSitzungsspeicher
} from '../../../lib/__tests__/sitzungsspeicherDoppel.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

let profilStatus = 200;
let profilAufrufe: string[] = [];
const goApi = createServer((req, res) => {
	profilAufrufe.push(`${req.url} ${req.headers.cookie ?? ''}`);
	res.writeHead(profilStatus, { 'Content-Type': 'application/json' });
	res.end('{}');
});
await new Promise<void>((fertig) => goApi.listen(0, '127.0.0.1', fertig));
process.env.GZ_API_BASE = `http://127.0.0.1:${(goApi.address() as AddressInfo).port}`;
after(() => goApi.close());

const { load } = await import(pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.server.ts')).href);
const { abmeldungLiegtVor, merkeAbmeldung } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/lib/pwa/geraetespeicher.ts')).href
);

async function sitzungAktiv(adresse: string, sitzung?: string): Promise<boolean> {
	profilAufrufe = [];
	const daten = (await load({
		url: new URL(adresse),
		cookies: { get: (n: string) => (n === 'gz_session' ? sitzung : undefined) }
	} as never)) as { sitzungAktiv: boolean };
	return daten.sitzungAktiv;
}

describe('AC-12: die Anmeldeseite stellt fest, ob noch eine Sitzung besteht', () => {
	test('mit Merkmal und von der Go-API bestaetigter Sitzung: aktiv', async () => {
		profilStatus = 200;
		assert.equal(await sitzungAktiv('http://localhost/login?abgemeldet=1', 'u.s.1.sig'), true);
		assert.deepEqual(profilAufrufe, ['/api/auth/profile gz_session=u.s.1.sig']);
	});

	test('mit Merkmal und von der Go-API abgelehnter Sitzung (401): nicht aktiv', async () => {
		profilStatus = 401;
		assert.equal(await sitzungAktiv('http://localhost/login?abgemeldet=1', 'u.s.1.sig'), false);
	});

	test('mit Merkmal ohne Sitzungs-Cookie: nicht aktiv, ohne Anfrage', async () => {
		assert.equal(await sitzungAktiv('http://localhost/login?abgemeldet=1'), false);
		assert.deepEqual(profilAufrufe, []);
	});

	test('Stoerung der Go-API (500): gilt als aktiv, im Zweifel wird nicht geraeumt', async () => {
		profilStatus = 500;
		assert.equal(await sitzungAktiv('http://localhost/login?abgemeldet=1', 'u.s.1.sig'), true);
	});

	// Issue #2961 (F006): ist die Go-API nicht erreichbar (Netzfehler), steht nicht
	// fest, dass die Sitzung fort ist — dann wird NICHT geraeumt.
	test('Go-API nicht erreichbar: gilt als aktiv, die Anmeldeseite raeumt nicht', async () => {
		const zu = createServer();
		await new Promise<void>((fertig) => zu.listen(0, '127.0.0.1', fertig));
		const totePort = (zu.address() as AddressInfo).port;
		await new Promise<void>((fertig) => zu.close(() => fertig()));
		const vorher = process.env.GZ_API_BASE;
		process.env.GZ_API_BASE = `http://127.0.0.1:${totePort}`;
		try {
			const aktiv = await sitzungAktiv('http://localhost/login?abgemeldet=1', 'u.s.1.sig');
			assert.equal(aktiv, true);
			installiereSitzungsspeicher();
			try {
				assert.equal(abmeldungLiegtVor(new URL('http://localhost/login?abgemeldet=1'), aktiv), false);
			} finally {
				entferneSitzungsspeicher();
			}
		} finally {
			process.env.GZ_API_BASE = vorher;
		}
	});

	test('ohne Merkmal wird die Go-API gar nicht gefragt', async () => {
		profilStatus = 200;
		await sitzungAktiv('http://localhost/login', 'u.s.1.sig');
		assert.deepEqual(profilAufrufe, []);
	});
});

describe('AC-12: geraeumt wird nur ohne gueltige Sitzung — ausser nach eigenem Abmelden', () => {
	beforeEach(() => {
		installiereSitzungsspeicher();
	});
	afterEach(() => {
		entferneSitzungsspeicher();
	});

	const MIT_MERKMAL = new URL('http://localhost/login?abgemeldet=1');

	test('Merkmal in der Adresse bei bestehender Sitzung: kein Raeumen', () => {
		assert.equal(abmeldungLiegtVor(MIT_MERKMAL, true), false);
	});

	test('Merkmal in der Adresse ohne Sitzung: Raeumen', () => {
		assert.equal(abmeldungLiegtVor(MIT_MERKMAL, false), true);
	});

	test('eigener Abmelde-Merker dieses Tabs: Raeumen, auch wenn das Cookie noch signiert ist', () => {
		merkeAbmeldung();
		assert.equal(abmeldungLiegtVor(new URL('http://localhost/login?expired=1'), true), true);
	});
});
