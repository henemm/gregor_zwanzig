// TDD RED — Issue #3196 (Workflow feat-3196-trip-tempo-etappen)
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md — AC-1, AC-4, AC-7, AC-9
//
// Echte Komponenten, serverseitig gerendert (svelte/server, Hooks aus dem F9-Prüfstand):
//   - shared/TempoKarte.svelte: vier Fortbewegungs-Chips + Zahlenfeld Grundtempo,
//     Hinweis „Gilt für alle Etappen.“, Auf-/Abstieg nirgends sichtbar, DE/EN.
//     Vertrag: props { tempo: Tempo, onchange?: (t: Tempo) => void }
//     Testids: tempo-karte, tempo-fortbewegung-<fuss|rad|mtb|ski> (aria-pressed),
//              tempo-grundtempo (input type=number)
//   - trip-detail/TripHeader.svelte: keine Aktivitäts-Chips und kein Aktivitäts-Zusatz mehr.
//   - Katalog DE/EN: neue Schlüssel vollständig in beiden Sprachen.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/trip-detail/__tests__/tempo_karte_3196.test.ts

import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const { render } = await import('svelte/server');
const { locale } = T;
const TempoKarte = (await import(pathToFileURL(path.join(T.KOMP, 'shared', 'TempoKarte.svelte')).href)).default;
const TripHeader = (await import(pathToFileURL(path.join(T.TD, 'TripHeader.svelte')).href)).default;

afterEach(() => locale.set('de'));

function html(komp: unknown, props: Record<string, unknown>): string {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(komp as any, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
}

function tagMit(h: string, testid: string): string {
	const m = new RegExp(`<[^>]*data-testid="${testid}"[^>]*>`).exec(h);
	assert.ok(m, `[data-testid=${testid}] fehlt`);
	return m[0];
}

test('AC-1: Karte zeigt Rad gewählt und 20 km/h', () => {
	const h = html(TempoKarte, { tempo: { fortbewegung: 'rad', grundtempo_kmh: 20 } });
	tagMit(h, 'tempo-karte');
	for (const f of ['fuss', 'rad', 'mtb', 'ski']) {
		const chip = tagMit(h, `tempo-fortbewegung-${f}`);
		const gedrueckt = /aria-pressed="true"/.test(chip);
		assert.equal(gedrueckt, f === 'rad', `Chip ${f}: aria-pressed falsch (${chip})`);
	}
	const feld = tagMit(h, 'tempo-grundtempo');
	assert.match(feld, /type="number"/);
	assert.match(feld, /value="20"/);
});

test('AC-9 DE: Fortbewegung, Grundtempo, Hinweis; kein Aufstieg/Abstieg sichtbar', () => {
	locale.set('de');
	const h = html(TempoKarte, { tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 } });
	assert.match(h, /Fortbewegung/);
	assert.match(h, /Grundtempo/);
	assert.match(h, /Gilt für alle Etappen\./);
	assert.match(h, /zu Fuß/);
	assert.doesNotMatch(h, /Aufstieg|Abstieg|Hm\/h/);
	assert.doesNotMatch(h, /überschreibbar/, 'Zusatz „je Etappe überschreibbar“ erst mit #3197');
});

test('AC-9 EN: Mode of travel, Base pace', () => {
	locale.set('en');
	const h = html(TempoKarte, { tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 } });
	assert.match(h, /Mode of travel/);
	assert.match(h, /Base pace/);
	assert.doesNotMatch(h, /Fortbewegung|Grundtempo/);
	assert.doesNotMatch(h, /ascent|descent/i);
});

test('AC-1: TripHeader zeigt keine Aktivitäts-Chips und keinen Aktivitäts-Zusatz', () => {
	const trip = {
		id: 't', name: 'Kopf-Trip', region: 'Korsika', activity: 'hochtour',
		stages: [{ id: 'S1', name: 'D1', date: '2026-07-01', waypoints: [] }]
	};
	for (const mobil of [false, true]) {
		const h = html(TripHeader, { trip, now: T.JETZT, mobil });
		for (const label of ['Trekking', 'Skitour', 'Hochtour', 'Klettersteig', 'Fahrrad']) {
			assert.ok(!h.includes(label), `mobil=${mobil}: Aktivitäts-Text „${label}“ noch im Kopf`);
		}
	}
});

test('AC-9: Katalog DE/EN vollständig für die Tempo-Schlüssel', () => {
	const lies = (lang: string) =>
		JSON.parse(readFileSync(path.join(T.FRONTEND, 'src/lib/i18n/messages', lang, 'trip.json'), 'utf-8'));
	const de = lies('de');
	const en = lies('en');
	const deKeys = Object.keys(de).filter((k) => k.startsWith('trip.tempo.'));
	assert.ok(deKeys.length >= 7, `zu wenige trip.tempo.*-Schlüssel in DE: ${deKeys.join(', ')}`);
	for (const k of deKeys) assert.ok(typeof en[k] === 'string' && en[k] !== '', `EN fehlt: ${k}`);
	const enKeys = Object.keys(en).filter((k) => k.startsWith('trip.tempo.'));
	assert.deepEqual(enKeys.sort(), deKeys.sort());
});
