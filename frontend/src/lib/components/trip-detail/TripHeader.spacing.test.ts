// Bug #335 — fehlendes Leerzeichen vor dem Trip-Namen in der H1.
// Spec: docs/specs/modules/issue_335_h1_spacing.md
//
// Bug damals: die H1 rendert „KHW ·Karnischer Höhenweg" — Svelte trimmt das
// Leerzeichen hinter „·" direkt vor einem Block-Ende. Soll: „KHW · Karnischer
// Höhenweg" (Leerzeichen beidseits), ohne Shortcode genau der Name.
//
// Issue #2284 S2 (AC-1, AC-17, Entscheidung 2): Der Shortcode-Präfix wandert als
// Snippet `namePrefix` in den Baustein `SubscriptionHeader` und steht dort INNERHALB
// der Überschrift `trip-detail-h1`. Früher Quelltext-Grep auf die Zeile mit
// `h1-shortcode` und `{/if}`; jetzt VERHALTEN: der Text der gerenderten Überschrift
// (svelte/server, echte Komponente). Damit fängt der Test das Trimmen, egal in
// welcher Datei die Markup-Zeile künftig steht.
// Inventar: docs/artifacts/feat-2284-s2-trip-kopf/ac17-zusicherungs-inventar.md (C).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && npm test -- src/lib/components/trip-detail/TripHeader.spacing.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const PRUEFLING = path.join(HERE, 'TripHeader.svelte');

const TRIP = {
	id: 't-335',
	name: 'Karnischer Höhenweg',
	region: 'Karnische Alpen',
	activity: 'trekking',
	stages: [{ id: 'T1', name: 'E1', date: '2026-10-10', waypoints: [] }]
};

/** Roher Text der Überschrift `trip-detail-h1` (Kommentare und Tags entfernt,
 *  Whitespace NICHT normalisiert — genau darum geht es hier). */
async function h1Text(trip: Record<string, unknown>): Promise<string> {
	const Komponente = (await import(pathToFileURL(PRUEFLING).href)).default;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const body = render(Komponente as any, { props: { trip, now: new Date(2026, 9, 2, 10, 0) } }).body;
	const m = /<h1[^>]*data-testid="trip-detail-h1"[^>]*>([\s\S]*?)<\/h1>/.exec(body);
	assert.ok(m, 'Überschrift trip-detail-h1 fehlt');
	return m[1].replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, '');
}

const normal = (s: string): string => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim();

test('AC-1: mit Shortcode lautet die Überschrift „KHW · Karnischer Höhenweg" (Leerzeichen beidseits des ·)', async () => {
	assert.equal(normal(await h1Text({ ...TRIP, shortcode: 'KHW' })), 'KHW · Karnischer Höhenweg');
});

test('AC-1: nach dem · folgt nie direkt der Name („·Karnischer")', async () => {
	const roh = await h1Text({ ...TRIP, shortcode: 'KHW' });
	assert.ok(!/·\S/.test(roh), `getrimmtes Leerzeichen hinter dem Mittelpunkt: ${JSON.stringify(roh)}`);
	assert.ok(!/\S·/.test(roh), `fehlendes Leerzeichen vor dem Mittelpunkt: ${JSON.stringify(roh)}`);
});

test('AC-1 / #2284 S2: der Shortcode steht INNERHALB der Überschrift vor dem Namen', async () => {
	const roh = await h1Text({ ...TRIP, shortcode: 'KHW' });
	assert.ok(roh.indexOf('KHW') >= 0 && roh.indexOf('KHW') < roh.indexOf('Karnischer Höhenweg'), JSON.stringify(roh));
});

test('AC-2: ohne Shortcode ist die Überschrift genau der Name (kein sichtbares führendes Zeichen)', async () => {
	const roh = await h1Text({ ...TRIP, shortcode: undefined });
	assert.ok(!/^[\s]*[ ·]/.test(roh), `sichtbares Zeichen vor dem Namen: ${JSON.stringify(roh)}`);
	assert.equal(roh.trim(), 'Karnischer Höhenweg');
});
