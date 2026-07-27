// Issue #1395 S3 — die fuenf Umgehungswege am Trichter vorbei.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md — AC-5, AC-10.
//
// `PATCH /api/trips/{id}/state` laeuft an fuenf Stellen per rohem `fetch` am
// Trichter vorbei. Jeder erfolgreiche Aufruf veraendert die Tourdatei und damit
// den Fingerabdruck, liefert aber laut S2 (AC-15) KEINEN neuen ETag. Ohne
// Verwerfen wuerde die Anwendung sich selbst einen Konflikt bauen.
//
// doc-compliance-test: Quelltext-Verhaltenspruefung — im node:test-Setup gibt es
// kein Rendering-Harness fuer Svelte-5-Runen (Praezedenz:
// shared/__tests__/weatherMetricsTabDayWindowSave.test.ts). Geprueft wird nicht
// blosse String-Presence, sondern die POSITION des `discardEtag(...)`-Aufrufs
// relativ zur Erfolgspruefung — nur so ist belegt, dass er nur nach Erfolg laeuft.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const routes = join(here, '..', '..', 'routes');

const TRIP_DETAIL = join(routes, 'trips', '[id]', '+page.svelte');
const TRIP_LIST = join(routes, 'trips', '+page.svelte');
const ARCHIV = join(routes, 'archiv', '+page.svelte');

const tripDetailSrc = readFileSync(TRIP_DETAIL, 'utf-8');
const tripListSrc = readFileSync(TRIP_LIST, 'utf-8');
const archivSrc = readFileSync(ARCHIV, 'utf-8');

/** Isoliert den Koerper von `function <name>(` bzw. `<name> = ... {` per
 * Klammerzaehlung (keine verschachtelten Funktionsdeklarationen in den
 * betroffenen Funktionen — geprueft). */
function functionBody(src: string, name: string): string {
	const sigIdx = src.indexOf(`function ${name}(`);
	assert.ok(sigIdx >= 0, `function ${name}( nicht gefunden`);
	const braceStart = src.indexOf('{', src.indexOf(')', sigIdx));
	let depth = 0;
	for (let i = braceStart; i < src.length; i++) {
		if (src[i] === '{') depth++;
		else if (src[i] === '}') {
			depth--;
			if (depth === 0) return src.slice(braceStart, i + 1);
		}
	}
	throw new Error(`schliessende Klammer fuer ${name} nicht gefunden`);
}

/** Belegt: `discardEtag(...)` steht NACH der Erfolgspruefung, laeuft also nur
 * im Erfolgsfall. */
function assertDiscardAfterOkCheck(body: string, expectedArg: string, label: string): void {
	const okIdx = body.search(/if\s*\(\s*!res\.ok\s*\)/);
	assert.ok(okIdx >= 0, `${label}: die Erfolgspruefung (if (!res.ok)) wurde nicht gefunden`);
	const discardIdx = body.indexOf(`discardEtag(${expectedArg})`);
	assert.ok(
		discardIdx >= 0,
		`${label}: discardEtag(${expectedArg}) fehlt — nach einem erfolgreichen PATCH /state ist der gemerkte Stand veraltet`
	);
	assert.ok(
		discardIdx > okIdx,
		`${label}: discardEtag(${expectedArg}) steht VOR der Erfolgspruefung — es darf nur nach Erfolg verworfen werden`
	);
}

const IMPORT_RE = /import\s*\{[^}]*\bdiscardEtag\b[^}]*\}\s*from\s*'\$lib\/etagRegistry/;

describe('AC-5: Detailseite — sendStateUpdate', () => {
	test('test_tripDetailPage_sendStateUpdate_discardsEtagOnSuccess', () => {
		assert.match(tripDetailSrc, IMPORT_RE, 'trips/[id]/+page.svelte importiert discardEtag nicht');
		const body = functionBody(tripDetailSrc, 'sendStateUpdate');
		assertDiscardAfterOkCheck(body, 'trip.id', 'sendStateUpdate');
	});

	test('test_tripDetailPage_adoptsEtagFromPageDataOnMount', () => {
		// AC-1: der Stempel aus der Server-Naht landet in der Registry.
		assert.match(
			tripDetailSrc,
			/adoptEtagFromPageLoad\(\s*data\.trip\.id\s*,\s*data\.etag\s*\)/,
			'trips/[id]/+page.svelte uebernimmt data.etag nicht ueber adoptEtagFromPageLoad'
		);
		// Kein bedingungsloses Setzen an dieser Stelle — ein erneutes load() neben
		// einem laufenden Speichervorgang wuerde sonst einen aelteren Stand
		// zurueckschreiben (Fehlerklasse F001).
		assert.ok(
			!/setKnownEtag\(/.test(tripDetailSrc),
			'die Server-Naht darf den Stempel nicht bedingungslos setzen'
		);
		// Rueckfallposition: nur wenn ein Stempel da ist (AC-7).
		assert.match(
			tripDetailSrc,
			/if\s*\(\s*data\.etag\s*\)/,
			'die Uebernahme muss auf das Vorhandensein von data.etag pruefen'
		);
	});

	test('test_tripDetailPage_etagAdoptionDoesNotDependOnMutableTripState', () => {
		// Der Uebernahme-Effekt darf NICHT vom lokalen `trip`-$state abhaengen:
		// sendStateUpdate() setzt `trip` neu, der Effekt liefe direkt nach dem
		// discardEtag() dort erneut und legte den veralteten Stempel wieder ab —
		// exakt der selbstgebaute Konflikt, den AC-5 verhindern soll.
		const idx = tripDetailSrc.indexOf('adoptEtagFromPageLoad(');
		assert.ok(idx >= 0, 'adoptEtagFromPageLoad-Aufruf nicht gefunden');
		const effectStart = tripDetailSrc.lastIndexOf('$effect(', idx);
		assert.ok(effectStart >= 0, 'umgebender $effect nicht gefunden');
		const effectEnd = tripDetailSrc.indexOf('});', idx);
		const effectBody = tripDetailSrc.slice(effectStart, effectEnd);
		assert.ok(
			!/(?<!data\.)\btrip\.id\b/.test(effectBody),
			`der Uebernahme-Effekt darf das lokale trip-$state nicht lesen:\n${effectBody}`
		);
	});
});

describe('AC-5/AC-10: Listenseite — drei /state-Aufrufer', () => {
	test('test_tripsListPage_allThreeStateCallers_discardEtagOnSuccess', () => {
		assert.match(tripListSrc, IMPORT_RE, 'trips/+page.svelte importiert discardEtag nicht');

		// 1) Archivierung aufheben
		assertDiscardAfterOkCheck(
			functionBody(tripListSrc, 'handlePrimaryAction'),
			'trip.id',
			'handlePrimaryAction (Dearchivieren)'
		);

		// 2) Archivieren
		const archiveBody = functionBody(tripListSrc, 'handleArchive');
		assertDiscardAfterOkCheck(archiveBody, 'archiveTarget.id', 'handleArchive');
		const discardIdx = archiveBody.indexOf('discardEtag(archiveTarget.id)');
		const resetIdx = archiveBody.indexOf('archiveTarget = null');
		assert.ok(resetIdx >= 0, 'handleArchive setzt archiveTarget nicht mehr zurueck?');
		assert.ok(
			discardIdx < resetIdx,
			'handleArchive: discardEtag(archiveTarget.id) muss VOR "archiveTarget = null" stehen — sonst laeuft es auf null'
		);

		// 3) Pause-Umschalter
		assertDiscardAfterOkCheck(
			functionBody(tripListSrc, 'handlePauseToggle'),
			'trip.id',
			'handlePauseToggle'
		);
	});
});

describe('AC-10: Archivseite — nur der Trip-Zweig', () => {
	test('test_archivPage_tripStateCaller_discardsEtag_compareUnaffected', () => {
		assert.match(archivSrc, IMPORT_RE, 'archiv/+page.svelte importiert discardEtag nicht');
		const body = functionBody(archivSrc, 'makeReactivate');
		assertDiscardAfterOkCheck(body, 'item.id', 'makeReactivate');

		// Der Zwilling fuer Orts-Vergleiche bleibt unberuehrt (S6): der
		// discardEtag-Aufruf MUSS auf item.type === 'trip' eingeschraenkt sein.
		assert.match(
			body,
			/item\.type\s*===\s*'trip'\s*\)\s*discardEtag\(item\.id\)|if\s*\(\s*item\.type\s*===\s*'trip'\s*\)\s*\{[^}]*discardEtag\(item\.id\)/,
			'makeReactivate: discardEtag darf nur fuer item.type === "trip" laufen (Compare-Zweig ist S6)'
		);
		assert.ok(
			body.includes('/api/compare/presets/'),
			'der Compare-Zweig in makeReactivate darf nicht verschwunden sein'
		);
		assert.equal(
			(archivSrc.match(/discardEtag\(/g) ?? []).length,
			1,
			'in archiv/+page.svelte darf es genau einen discardEtag-Aufruf geben (nur der Trip-Zweig)'
		);
	});
});

describe('Vollstaendigkeit: kein sechster Umgehungsweg', () => {
	test('test_exactlyFiveTripStateCallSites_allInCoveredFiles', () => {
		const RE = /\/api\/trips\/\$\{[^}]+\}\/state/g;
		const counts = {
			'trips/[id]/+page.svelte': (tripDetailSrc.match(RE) ?? []).length,
			'trips/+page.svelte': (tripListSrc.match(RE) ?? []).length,
			'archiv/+page.svelte': (archivSrc.match(RE) ?? []).length
		};
		assert.deepEqual(counts, {
			'trips/[id]/+page.svelte': 1,
			'trips/+page.svelte': 3,
			'archiv/+page.svelte': 1
		});
		// Summe = 5. Kommt eine Stelle dazu, faellt dieser Test auf und der
		// zugehoerige discardEtag-Aufruf wird nicht vergessen.
		assert.equal(Object.values(counts).reduce((a, b) => a + b, 0), 5);
	});
});
