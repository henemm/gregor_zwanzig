// Issue #2961 (ADR-0115), Fix-Runde F-D: das Passkey-Angebot im Layout darf bei
// fehlendem Nachweis nicht still scheitern. Echte Module: $lib/passkey (nur die
// globale fetch-Funktion liefert die Server-Antwort) und $lib/passkeyAngebot.
//
//   cd frontend && npm test -- src/lib/passkeyAngebotNachweis.test.ts

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { angebotFehlerFolge, passkeyEinrichtenAngefordert, KONTO_PASSKEY_EINRICHTEN } = (await import(
	pathToFileURL(path.join(HERE, 'passkeyAngebot.ts')).href
)) as {
	angebotFehlerFolge: (e: unknown) => 'nachweis' | 'abgebrochen' | 'fehler';
	passkeyEinrichtenAngefordert: (s: URLSearchParams) => boolean;
	KONTO_PASSKEY_EINRICHTEN: string;
};
const { registerPasskey } = (await import(pathToFileURL(path.join(HERE, 'passkey.ts')).href)) as {
	registerPasskey: (label: string) => Promise<unknown>;
};

let antwort = { status: 200, koerper: '{}' };
const echterFetch = globalThis.fetch;
globalThis.fetch = async () =>
	new Response(antwort.koerper, { status: antwort.status, headers: { 'Content-Type': 'application/json' } });
after(() => {
	globalThis.fetch = echterFetch;
});

async function einrichtenFehler(): Promise<unknown> {
	return registerPasskey('Dieses Gerät').then(
		() => null,
		(e: unknown) => e
	);
}

test('fehlender Nachweis beim Einrichten fuehrt zur Konto-Seite, nicht ins Leere', async () => {
	antwort = { status: 403, koerper: JSON.stringify({ code: 'reauth_required', error: 'reauth_required' }) };
	assert.equal(angebotFehlerFolge(await einrichtenFehler()), 'nachweis');
	const ziel = new URL(KONTO_PASSKEY_EINRICHTEN, 'http://localhost');
	assert.equal(ziel.pathname, '/account');
	assert.equal(passkeyEinrichtenAngefordert(ziel.searchParams), true, 'die Konto-Seite erkennt das Merkmal');
});

test('andere Fehler bleiben sichtbar Fehler, Abbruch ist Abbruch', async () => {
	antwort = { status: 500, koerper: '{}' };
	assert.equal(angebotFehlerFolge(await einrichtenFehler()), 'fehler');
	assert.equal(angebotFehlerFolge(Object.assign(new Error('x'), { name: 'NotAllowedError' })), 'abgebrochen');
	assert.equal(angebotFehlerFolge(null), 'fehler');
});

test('ohne Merkmal oeffnet die Konto-Seite keinen Nachweis-Dialog', () => {
	assert.equal(passkeyEinrichtenAngefordert(new URLSearchParams('')), false);
	assert.equal(passkeyEinrichtenAngefordert(new URLSearchParams('passkey=irgendwas')), false);
});
