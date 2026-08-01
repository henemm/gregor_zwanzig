// TDD RED — Feature #1435 Etappe E3a: `+page.server.ts` lädt `GET /api/metrics`
// parallel zum Trip-Fetch, fail-soft (`.catch(() => null)`), OHNE den
// bestehenden Trip-Fehlerzweig zu berühren.
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md
// Implementation Details Punkt 3, AC-4 (Loader-Teil), AC-5 (Loader-Teil).
//
// doc-compliance-test (Quelltext-Prüfung). ABWEICHUNG vom generischen
// Testplan-Stil: `+page.server.ts` importiert `$lib/server/apiBase.js`, das
// seinerseits `$env/dynamic/private` importiert — ein virtuelles SvelteKit-
// Modul, das außerhalb von Vite unter `node --test` nicht auflösbar ist.
// Vorbild: pageServerEtagPassthrough.test.ts (dieselbe Begründung dort).
//
// RED heute: load() hat weder Promise.all noch einen /api/metrics-Fetch noch
// `metricsCatalog` im Rückgabewert.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     "src/routes/trips/[id]/__tests__/pageServerMetricsCatalogFailSoft.test.ts"

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '+page.server.ts'), 'utf-8');

describe('AC-4 (Loader-Teil): Katalog-Fetch ist parallel und fail-soft, Trip-Fehlerzweig bleibt unberührt', () => {
	test('load() ruft Trip- und Katalog-Fetch parallel über Promise.all auf', () => {
		assert.match(
			src,
			/await\s+Promise\.all\(/,
			'load() ruft den Trip- und den Katalog-Fetch nicht parallel über Promise.all auf.'
		);
	});

	test('Der Katalog-Fetch (/api/metrics) trägt ein .catch(() => null)', () => {
		assert.match(
			src,
			/fetch\(\s*`\$\{API\(\)\}\/api\/metrics`[\s\S]*?\.catch\(\s*\(\)\s*=>\s*null\s*\)/,
			'Der Katalog-Fetch (/api/metrics) trägt kein .catch(() => null) — ein Netzwerkfehler würde ' +
				'die ganze Seite zum Kippen bringen (AC-4, Expected Behavior Input D).'
		);
	});

	test('Der bestehende Trip-Fehlerzweig (404 und !ok) bleibt unverändert erhalten', () => {
		assert.match(src, /throw error\(404,/, 'der 404-Fehlerzweig für den Trip-Fetch fehlt');
		assert.match(src, /throw error\(\s*\w+\.status\s*,/, 'der allgemeine !ok-Fehlerzweig für den Trip-Fetch fehlt');
	});

	test('Der Katalog-Fetch-Ausdruck selbst wirft NICHT wie der Trip-Fetch', () => {
		// Der Trip-Fehlerzweig nutzt `throw error(...)`. Der Katalog-Fetch-Ausdruck
		// darf das nicht enthalten — sonst kippt bei einem Katalog-Ausfall die
		// ganze Seite mit, statt nur den neuen Block ohne Datengrundlage zu lassen.
		const metricsExpr = src.match(/fetch\(\s*`\$\{API\(\)\}\/api\/metrics`[\s\S]*?\)\s*;/);
		assert.ok(metricsExpr, 'Katalog-Fetch-Ausdruck (fetch(`${API()}/api/metrics` ...);) nicht gefunden');
		assert.doesNotMatch(
			metricsExpr![0],
			/throw error\(/,
			'Der Katalog-Fetch-Ausdruck enthält throw error(...) — ein Katalog-Ausfall darf die Seite nicht zum Kippen bringen.'
		);
	});

	test('metricsCatalog landet neben trip/etag im Rückgabewert von load()', () => {
		assert.match(
			src,
			/return\s*\{[^}]*\btrip\b[^}]*\betag\b[^}]*\bmetricsCatalog\b[^}]*\}/,
			'load() gibt metricsCatalog nicht zusammen mit trip und etag zurück.'
		);
	});
});

describe('AC-5 (Loader-Teil): der Katalog ist beim ersten Rendern bereits vollständig geladen', () => {
	test('Promise.all (inkl. Katalog-Fetch) wird VOR dem return awaitet — kein Ladefenster', () => {
		// Fehlerklasse #1320 (E1a-2, Befund F001): ein Ladefenster, in dem der Block
		// „Noch nicht eingestellt" zeigt, obwohl tatsächlich eine Auswahl existiert.
		// Server-Load statt Client-Fetch verhindert das strukturell, sofern der
		// Katalog-Fetch Teil desselben awaiteten Promise.all ist wie der Trip-Fetch.
		const promiseAllIdx = src.search(/await\s+Promise\.all\(/);
		const returnIdx = src.search(/return\s*\{[^}]*\btrip\b/);
		assert.ok(promiseAllIdx >= 0, 'Promise.all(...) nicht gefunden');
		assert.ok(returnIdx >= 0, 'return {...trip...} nicht gefunden');
		assert.ok(
			promiseAllIdx < returnIdx,
			'Promise.all(...) steht nicht vor dem return-Statement — der Katalog könnte dann noch offen sein, ' +
				'wenn die Seite bereits rendert.'
		);
	});
});
