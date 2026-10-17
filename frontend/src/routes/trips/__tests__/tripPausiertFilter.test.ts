// TDD RED: Issue #1271 — Trips-Liste braucht einen "Pausiert"-Filter-Tab,
// analog zu Aktiv/Geplant/Fertig (Spec fix_1271_status_zeitformat AC-7).
//
// Hintergrund: Vor diesem Fix kannte tripStatus() (Liste/Cockpit) keinen
// pausierten Zustand — pausierte Trips waren in der mobilen Filterleiste
// unauffindbar und wurden je nach Etappen-Datum fälschlich unter
// Aktiv/Geplant/Fertig einsortiert.
//
// Test-Pattern: Source-Inspection (wie routes/trips/issue_402.test.ts im
// übergeordneten Verzeichnis) — +page.svelte wird nicht kompiliert, daher
// Prüfung auf die Filter-Pill-Datenstruktur im rohen Quelltext.
//
// RED vor Implementierung: die Pills-Liste in +page.svelte enthält nur
// Alle/Aktiv/Geplant/Fertig, keinen Pausiert-Eintrag.
//
// Ausführen:
//   cd frontend && npm test -- src/routes/trips/__tests__/tripPausiertFilter.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const PAGE = join(here, '../+page.svelte');
const source = readFileSync(PAGE, 'utf8');

// Isoliert den Block der mobilen Filter-Pills (Issue #413), damit die
// Prüfung nicht versehentlich auf den Desktop-Zähler-Balken matcht, der laut
// Spec bewusst KEINEN eigenen Pausiert-Zähler bekommt (Known Limitations).
function mobilePillsBlock(src: string): string {
	const marker = '<!-- Mobile Filter-Pills';
	const idx = src.indexOf(marker);
	assert.ok(idx >= 0, '+page.svelte: Mobile-Filter-Pills-Kommentar nicht gefunden.');
	return src.slice(idx, idx + 1200);
}

test('AC-7/#1271: mobile Filter-Pills enthalten einen Eintrag für value "pausiert"', () => {
	const block = mobilePillsBlock(source);
	assert.ok(
		/value:\s*['"]pausiert['"]/.test(block),
		'+page.svelte: mobile Filter-Pills sollen einen Eintrag { value: "pausiert", ... } enthalten — fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-7/#1271: mobile Filter-Pills zeigen das Label "Pausiert"', () => {
	const block = mobilePillsBlock(source);
	assert.ok(
		/label:\s*['"]Pausiert['"]/.test(block),
		'+page.svelte: mobile Filter-Pills sollen ein Label "Pausiert" enthalten — fehlt noch (TDD RED erwartet Fehler).'
	);
});

test('AC-7/#1271: Pausiert-Zähler wird aus tripStatus() === "pausiert" berechnet', () => {
	const block = mobilePillsBlock(source);
	assert.ok(
		/tripStatus\(t,\s*now\)\s*===\s*['"]pausiert['"]/.test(block),
		'+page.svelte: Pausiert-Zähler soll über tripStatus(t, now) === "pausiert" gefiltert werden — fehlt noch (TDD RED erwartet Fehler).'
	);
});

// ---------------------------------------------------------------------------
// Issue #2278 AC-11 (TDD): archivierte Trips sind kein "Fertig" der Trip-LISTE.
// Die Liste blendet Archiviertes aus (Loader-Filter; Zwei-Sessions-Nachweis in
// lib/server/__tests__/profileLoader.test.ts). Das Cockpit bleibt UNVERAENDERT:
// tripStatus() mappt archived weiterhin auf 'fertig' (Guard, heute und danach gruen).
// Hinweis /50: die drei Source-Inspection-Tests oben pruefen die INLINE-Pillen der Seite
// und muessen auf StatusFilterPills umgestellt werden (Spec "Bewusst zu aendernde Tests").
// ---------------------------------------------------------------------------
import { register } from 'node:module';
import { tripStatus } from '../../../lib/utils/tripStatus.ts';

const VERGANGEN = { id: 'a', name: 'A', stages: [{ id: 's', name: 's', date: '2026-01-01', waypoints: [] }] } as any;

test('AC-11 Guard: Cockpit-Status eines archivierten Trips mit vergangenem Datum bleibt "fertig"', () => {
	const jetzt = new Date('2026-10-17T12:00:00Z');
	assert.equal(tripStatus({ ...VERGANGEN, archived_at: '2026-02-01T00:00:00Z' }, jetzt), 'fertig');
	assert.equal(tripStatus(VERGANGEN, jetzt), 'fertig');
});

test('AC-11: die Trip-Liste filtert Archiviertes serverseitig (load() von +page.server.ts)', async () => {
	register(new URL('../../compare/__tests__/server-load-resolve.hooks.mjs', import.meta.url));
	const { load } = (await import('../+page.server.ts')) as any;
	const original = globalThis.fetch;
	globalThis.fetch = (async () =>
		new Response(
			JSON.stringify([
				{ id: 'aktiv', name: 'Aktiv', stages: [], archived_at: null },
				{ id: 'archiviert', name: 'Arch', stages: [], archived_at: '2026-09-01T00:00:00Z' }
			]),
			{ status: 200 }
		)) as unknown as typeof fetch;
	try {
		const r = await load({ cookies: { get: () => 'sess' }, fetch: globalThis.fetch });
		assert.deepEqual((r.trips ?? []).map((t: any) => t.id), ['aktiv']);
	} finally {
		globalThis.fetch = original;
	}
});
