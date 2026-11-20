// TDD RED — Issue #3212: Tippfläche in der Karte „Was steht wo“ (Roh/Einfach, E-Mail-Format).
// Spec: docs/specs/modules/fix_3212_was_steht_wo_tippflaeche.md — Test Plan Test 1/2, AC-1 bis AC-3, AC-6.
//
// Vertrag:
//   atoms/RohEinfachKnopf.svelte  Knopf trägt data-tap="true" (der Wächter AC-40 misst dann die 44×44-Trefferpunkte
//                                 statt der 32×22-Box); eine NICHT an @media gebundene Regel `.rek::before` zieht die
//                                 unsichtbare Tippfläche auf max(100%, var(--g-tap-min)) — Desktop UND Mobil.
//   organisms/wetter-tab/WasStehtWoKarte.svelte  Segmented „E-Mail: Format“ rendert data-variant="kompakt"
//                                 (Mockup `.seg`, Tippfläche per ::before), nicht mehr data-size="sm".
//
// Server-Render der ECHTEN Dateien (svelte/server) und echte Compiler-Ausgabe (svelte/compiler) für die CSS-Regel.
// Ecken-Treffer und 44-px-Messung live: frontend/e2e/s3a2794-teil3-design.spec.ts AC-40.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/organisms/__tests__/fix_3212_was_steht_wo_tippflaeche.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> organisms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const KARTE = path.resolve(HERE, '..', 'wetter-tab', 'WasStehtWoKarte.svelte');
const KNOPF = path.resolve(HERE, '..', '..', 'atoms', 'RohEinfachKnopf.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { compile } = await import('svelte/compiler');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const g = globalThis as J;

const START: [string, string][] = [
	['let antwort = $state<PlacementsAntwort | null>(null);', 'let antwort = $state<PlacementsAntwort | null>(globalThis.__wswAntwort);'],
	["let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');", "let phase = $state<'laedt' | 'fehler' | 'bereit'>(globalThis.__wswPhase ?? 'bereit');"]
];
async function karte(a: J, props: Record<string, unknown>): Promise<string> {
	g.__wswAntwort = a;
	g.__wswPhase = 'bereit';
	const url = pathToFileURL(KARTE).href + `?start=${encodeURIComponent(JSON.stringify(START))}`;
	const K = (await import(url)).default;
	return render(K, { props: { id: 'abo-1', ...props } }).body.replace(/<!--[\s\S]*?-->/g, '');
}
const attr = (auf: string, name: string) => auf.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;
/** Alle öffnenden Tags, die das Merkmal tragen. */
const tags = (h: string, merkmal: string) => [...h.matchAll(/<[a-z][a-z0-9]*\b[^>]*>/g)].map((m) => m[0]).filter((t) => t.includes(merkmal));

// ── Antworten des Endpoints (Form laut docs/reference/api_contract.md, wie was_steht_wo_karte.test.ts) ──
const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
function trip(): J {
	return {
		kind: 'route', lang: 'de', stored: true, placements: { version: 1, rows: [] }, location_count: null,
		columns: [
			{ stelle: 'email', subtitle: 'stundentabelle', block_off: false, rests: null },
			{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
			{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
			{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
		],
		fixed_rows: [],
		rows: [
			{ metric_id: 'gust', name: 'Boe-T', position: 0, parent: null, cells: {
				email: z('on', { format: 'simplified' }), telegram: z('on', { format: 'raw', example: 'G 26-59@15' }),
				sms: z('on', { example: 'G32@6' }), outlook: z('on', { format: 'raw', example: '85 km/h' }) } }
		],
		sms_example: { text: 'Etappe-X: G32@6', length: 15, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', outlook: { morning: false, evening: true } },
		legend: { metrics: [{ metric_id: 'gust', kuerzel: 'G', meaning: null }], fixed: [] },
		example_version: 1
	};
}
function orte(): J {
	return {
		kind: 'vergleich', lang: 'de', stored: false, placements: { version: 1, rows: [] }, location_count: 2,
		columns: [
			{ stelle: 'email', subtitle: 'uebersicht', block_off: false, rests: null },
			{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
			{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
			{ stelle: 'hourly', subtitle: 'nur_email', block_off: false, rests: null },
			{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
		],
		fixed_rows: [],
		rows: [
			{ metric_id: 'wind', name: 'Wind-O', position: 0, parent: null, cells: {
				email: z('on', { format: 'raw', example: '43 km/h' }), telegram: z('on', { format: 'simplified' }), sms: z('on', { example: 'W43@16' }),
				hourly: z('on', { format: 'raw', example: '28' }), outlook: z('on', { format: 'raw', example: '60 km/h' }) } }
		],
		sms_example: { text: 'O1 W43@16 O2 W44@16', length: 19, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { hourly: true, telegram_style: 'rich', outlook: { morning: false, evening: true } },
		legend: { metrics: [{ metric_id: 'wind', kuerzel: 'W', meaning: 'Wind km/h' }], fixed: [] },
		example_version: 1
	};
}

describe('Test 1 / AC-1, AC-2, AC-6: Roh/Einfach-Knopf meldet seine 44-px-Tippfläche (data-tap)', () => {
	test('einzelner Knopf (raw und simplified) trägt data-tap="true"', async () => {
		const K = (await import(pathToFileURL(KNOPF).href)).default;
		for (const wert of ['raw', 'simplified']) {
			const h = render(K, { props: { wert, name: 'Wind in E-Mail', testid: 'rek' } }).body;
			const knopf = tags(h, 'data-slot="roh-einfach"');
			assert.equal(knopf.length, 1);
			assert.equal(attr(knopf[0], 'data-tap'), 'true', `TDD RED: Roh/Einfach-Knopf (${wert}) ohne data-tap — der Wächter misst nur die 32×22-Pille`);
		}
	});
	for (const [kontext, antwort] of [['route', trip], ['vergleich', orte]] as const) {
		test(`Karte im Kontext ${kontext}: jeder Roh/Einfach-Knopf trägt data-tap="true"`, async () => {
			locale.set('de');
			const h = await karte(antwort(), { context: kontext });
			const knoepfe = tags(h, 'data-slot="roh-einfach"');
			assert.ok(knoepfe.length >= 2, `erwartet mehrere Roh/Einfach-Knöpfe, gefunden ${knoepfe.length}`);
			for (const k of knoepfe) assert.equal(attr(k, 'data-tap'), 'true', `TDD RED: Knopf ohne data-tap: ${k}`);
		});
	}
});

describe('AC-1/AC-2: unsichtbare Tippfläche per ::before auf ALLEN Breiten', () => {
	// Echte Compiler-Ausgabe des Atoms (gescopte CSS), nicht der Quelltext: Regeln innerhalb von @media
	// gelten nur schmal/Touch und zählen für Desktop nicht.
	test('eine Regel .rek…::before außerhalb jeder @media-Bedingung nutzt max(100%, var(--g-tap-min)) für Breite und Höhe', () => {
		const out = compile(readFileSync(KNOPF, 'utf8'), { generate: 'server', filename: KNOPF });
		const css = (out.css?.code ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
		const ohneMedia = css.replace(/@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, '');
		const regeln = [...ohneMedia.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter((m) => /\.rek\b[^,{]*::before/.test(m[1]));
		assert.ok(regeln.length > 0, 'TDD RED: keine ::before-Regel am Roh/Einfach-Knopf für alle Breiten (Desktop ohne Tippfläche)');
		const koerper = regeln.map((m) => m[2]).join(';');
		assert.match(koerper, /(^|;)\s*width:\s*max\(100%,\s*var\(--g-tap-min\)\)/, 'TDD RED: ::before-Breite nicht max(100%, --g-tap-min)');
		assert.match(koerper, /(^|;)\s*height:\s*max\(100%,\s*var\(--g-tap-min\)\)/, 'TDD RED: ::before-Höhe nicht max(100%, --g-tap-min)');
		assert.match(koerper, /position:\s*absolute/);
		const knopf = [...ohneMedia.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter((m) => /\.rek\.svelte-[a-z0-9]+\s*$/.test(m[1].trim()) || /^\s*\.rek(\.svelte-[a-z0-9]+)?\s*$/.test(m[1]));
		assert.ok(knopf.some((m) => /position:\s*relative/.test(m[2])), 'TDD RED: Knopf .rek nicht position: relative (::before hätte keinen Bezug)');
	});
});

describe('Test 2 / AC-3: Segmented „E-Mail: Format“ in Mockup-Variante kompakt', () => {
	test('Trip-Karte: Segmented was-steht-wo-email-format hat data-variant="kompakt" und kein data-size="sm"', async () => {
		locale.set('de');
		const h = await karte(trip(), { context: 'route' });
		const seg = tags(h, 'data-slot="segmented"').filter((t) => t.includes('data-testid="was-steht-wo-email-format"'));
		assert.equal(seg.length, 1, `erwartet genau ein E-Mail-Format-Segmented, gefunden ${seg.length}`);
		assert.equal(attr(seg[0], 'data-variant'), 'kompakt', 'TDD RED: E-Mail-Format-Segmented nicht kompakt (Tippfläche 19 px Desktop / 36 px Mobil)');
		assert.equal(attr(seg[0], 'data-size'), null, 'TDD RED: E-Mail-Format-Segmented noch data-size="sm"');
		// Beide Segmente bleiben da, Rolle radio unverändert.
		assert.equal(tags(h, 'data-testid="was-steht-wo-email-format-full"').length, 1);
		assert.equal(tags(h, 'data-testid="was-steht-wo-email-format-compact"').length, 1);
	});
});
