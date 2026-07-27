// Issue #1395 S3 — Server-Naht: `load()` reicht den ETag-Header durch.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md — AC-1, AC-7.
//
// doc-compliance-test (Quelltext-Pruefung). ABWEICHUNG vom Testplan (dort war
// ein funktionaler `load()`-Aufruf vorgesehen): `+page.server.ts` importiert
// `$lib/server/apiBase.js`, das seinerseits `$env/dynamic/private` importiert —
// ein virtuelles SvelteKit-Modul, das ausserhalb von Vite nicht aufloesbar ist.
// Ein Import unter `node --test` scheitert daher zwingend (verifiziert). Repo-
// Praezedenz: src/routes/page-server.bug395.test.ts, verify-email/page-server.test.ts.
// Dass ein durchgereichter Stempel wirkt, belegt apiTripEtagHeaders.test.ts.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '+page.server.ts'), 'utf-8');

describe('AC-1: die Server-Naht gibt den Stempel weiter', () => {
	test('test_load_passesEtagHeaderIntoPageData', () => {
		// GIVEN/WHEN: der Quelltext von load()
		// THEN: der ETag-Header der Antwort wird gelesen ...
		assert.match(
			src,
			/res\.headers\.get\(\s*'ETag'\s*\)/,
			'load() liest den ETag-Header der Server-Antwort nicht'
		);
		// ... und zusammen mit dem Trip an die Seite gegeben.
		assert.match(
			src,
			/return\s*\{[^}]*\btrip\b[^}]*\betag\b[^}]*\}/,
			'load() gibt den Stempel nicht neben dem Trip zurueck'
		);
	});

	test('test_load_readsEtagOnlyAfterSuccessCheck', () => {
		// Der Header darf erst nach den Fehlerzweigen gelesen werden — sonst
		// wuerde bei 404/5xx ein Stempel einer nicht ausgelieferten Fassung
		// entstehen.
		const errIdx = src.lastIndexOf('throw error(res.status');
		const etagIdx = src.search(/res\.headers\.get\(\s*'ETag'\s*\)/);
		assert.ok(errIdx >= 0, 'der Fehlerzweig von load() wurde nicht gefunden');
		assert.ok(etagIdx > errIdx, 'der ETag wird vor der Fehlerbehandlung gelesen');
	});

	test('test_load_missingEtagHeader_dataEtagIsUndefined', () => {
		// AC-7 (Rueckfallposition): fehlt der Header, muss `etag` `undefined`
		// sein — nicht `null`. `setKnownEtag` wird dann gar nicht aufgerufen und
		// der naechste Schreibvorgang laeuft wie vor S3.
		assert.match(
			src,
			/res\.headers\.get\(\s*'ETag'\s*\)\s*\?\?\s*undefined/,
			'load() muss einen fehlenden ETag-Header auf undefined abbilden (?? undefined)'
		);
	});
});
