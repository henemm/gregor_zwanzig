// TDD RED — Issue #3059: Format-Schalter „Ausführlich/Kompakt“ auch im Orte-Kontext der Karte „Was steht wo“.
// Spec docs/specs/modules/feat_3059_orte_kompakt_mail.md, AC-5 (Stundenverlauf bei Kompakt gesperrt, Ausblick bedienbar)
// und AC-13 (derselbe Baustein in beiden Kontexten, DE und EN).
//
// Server-Render der ECHTEN Datei organisms/wetter-tab/WasStehtWoKarte.svelte, Startzustand über startzustandHook.mjs
// (gleiche Machart wie was_steht_wo_karte.test.ts). Kein Mock: die Endpoint-Antwort ist Startwert des `$state`.
//
// Hinweis für den Developer: der bestehende Test „drei Orte: … kein E-Mail-Format …“ in was_steht_wo_karte.test.ts
// widerspricht AC-13 und muss mit der Umsetzung angepasst werden (E-Mail-Format gehört künftig auch zu Orten).
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/was_steht_wo_karte_orte_format_3059.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const DATEI = path.resolve(HERE, '..', 'wetter-tab', 'WasStehtWoKarte.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const g = globalThis as J;

const START: [string, string][] = [
	['let antwort = $state<PlacementsAntwort | null>(null);', 'let antwort = $state<PlacementsAntwort | null>(globalThis.__wswAntwort);'],
	["let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');", "let phase = $state<'laedt' | 'fehler' | 'bereit'>(globalThis.__wswPhase ?? 'bereit');"]
];
async function karte(a: J, props: Record<string, unknown>): Promise<string> {
	assert.ok(existsSync(DATEI), 'organisms/wetter-tab/WasStehtWoKarte.svelte fehlt');
	g.__wswAntwort = a;
	g.__wswPhase = undefined;
	const url = pathToFileURL(DATEI).href + `?start=${encodeURIComponent(JSON.stringify(START))}`;
	const K = (await import(url)).default;
	return render(K, { props: { id: 'abo-1', ...props } }).body.replace(/<!--[\s\S]*?-->/g, '');
}
const text = (h: string) =>
	h
		.replace(/<[^>]*>/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
const oeffner = (h: string, merkmal: string): string[] => (h.match(/<[a-z][a-z0-9]*\b[^>]*>/g) ?? []).filter((t) => t.includes(merkmal));
const einOeffner = (h: string, merkmal: string): string => {
	const e = oeffner(h, merkmal);
	assert.equal(e.length, 1, `erwartet genau ein Element mit ${merkmal}, gefunden ${e.length}`);
	return e[0];
};
const attr = (auf: string, name: string) => auf.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;

// ── Antworten des Endpoints (Form wie in was_steht_wo_karte.test.ts) ─────────────────────────
const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
function orte(anzahl: number, blocks: J = {}): J {
	return {
		kind: 'vergleich', lang: 'de', stored: false, placements: { version: 1, rows: [] }, location_count: anzahl,
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
				email: z('on', { format: 'raw', example: '43 km/h' }), telegram: z('on', { format: 'raw' }), sms: z('on', { example: 'W43@16' }),
				hourly: z('on', { format: 'raw' }), outlook: z('on', { format: 'raw' }) } }
		],
		sms_example: { text: 'O1 W43@16', length: 9, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { hourly: true, telegram_style: 'rich', outlook: { morning: false, evening: true }, ...blocks },
		legend: { metrics: [{ metric_id: 'wind', kuerzel: 'W', meaning: 'Wind km/h' }], fixed: [] },
		example_version: 1
	};
}

describe('#3059 Format-Schalter im Orte-Kontext (AC-13)', () => {
	test('Orte (drei Orte): Format-Schalter mit beiden Optionen, Vorgabe Ausführlich', async () => {
		const h = await karte(orte(3), { context: 'vergleich' });
		const s = text(h);
		for (const w of ['E-Mail: Format', 'Ausführlich (HTML)', 'Kompakt (Nur-Text)']) assert.ok(s.includes(w), `fehlt bei Orten: ${w}`);
		einOeffner(h, 'data-testid="was-steht-wo-email-format"');
		assert.equal(attr(einOeffner(h, 'data-testid="was-steht-wo-email-format-full"'), 'aria-checked'), 'true');
		assert.equal(attr(einOeffner(h, 'data-testid="was-steht-wo-email-format-compact"'), 'aria-checked'), 'false');
	});
	test('Orte (ein Ort): Format-Schalter ebenfalls vorhanden', async () => {
		const h = await karte(orte(1), { context: 'vergleich' });
		einOeffner(h, 'data-testid="was-steht-wo-email-format"');
	});
	test('Orte mit gespeichertem compact: Kompakt ist gewählt', async () => {
		const h = await karte(orte(3, { email_format: 'compact' }), { context: 'vergleich' });
		assert.equal(attr(einOeffner(h, 'data-testid="was-steht-wo-email-format-compact"'), 'aria-checked'), 'true');
		assert.equal(attr(einOeffner(h, 'data-testid="was-steht-wo-email-format-full"'), 'aria-checked'), 'false');
	});
	test('Orte: Trip-Blöcke erscheinen trotz Format-Schalter nicht', async () => {
		const s = text(await karte(orte(3, { email_format: 'compact' }), { context: 'vergleich' }));
		for (const w of ['Etappen-Kennzahlen', 'Vortag-Vergleich', 'Nacht-Stundentabelle']) assert.ok(!s.includes(w), `${w} gehört nicht zu Orten`);
	});
	test('Englisch: Format-Schalter bei Orten mit englischen Texten', async () => {
		locale.set('en');
		try {
			const s = text(await karte({ ...orte(3), lang: 'en' }, { context: 'vergleich' }));
			for (const w of ['Email: format', 'Detailed (HTML)', 'Compact (plain text)']) assert.ok(s.includes(w), `fehlt (EN): ${w}`);
		} finally {
			locale.set('de');
		}
	});
});

describe('#3059 Kompakt sperrt den Stundenverlauf, Ausblick bleibt bedienbar (AC-5)', () => {
	test('Orte + compact: Stundenverlauf-Schalter gesperrt (aria-disabled), gespeicherter Wert bleibt sichtbar', async () => {
		const h = await karte(orte(3, { email_format: 'compact', hourly: true }), { context: 'vergleich' });
		const sw = einOeffner(h, 'data-testid="was-steht-wo-stundenverlauf"');
		assert.equal(attr(sw, 'aria-disabled'), 'true', 'Stundenverlauf muss bei Kompakt gesperrt sein');
		assert.equal(attr(sw, 'aria-checked'), 'true', 'gespeicherter Wert bleibt stehen');
	});
	test('Orte + compact: Ausblick-Schalter Morgen/Abend bleiben bedienbar', async () => {
		const h = await karte(orte(3, { email_format: 'compact' }), { context: 'vergleich' });
		for (const b of ['morning', 'evening']) {
			const sw = einOeffner(h, `data-testid="was-steht-wo-ausblick-${b}"`);
			assert.equal(attr(sw, 'aria-disabled'), null, `Ausblick ${b} darf bei Kompakt nicht gesperrt sein`);
		}
	});
	test('Orte + full: Stundenverlauf bedienbar (Gegenprobe)', async () => {
		const h = await karte(orte(3, { email_format: 'full' }), { context: 'vergleich' });
		assert.equal(attr(einOeffner(h, 'data-testid="was-steht-wo-stundenverlauf"'), 'aria-disabled'), null);
	});
});

describe('#3059 Regression Trip', () => {
	test('Trip-Karte zeigt den Format-Schalter weiterhin genau einmal', async () => {
		const trip = {
			...orte(1),
			kind: 'route',
			location_count: null,
			columns: [
				{ stelle: 'email', subtitle: 'stundentabelle', block_off: false, rests: null },
				{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
				{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
				{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
			],
			blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', outlook: { morning: false, evening: true } }
		};
		const h = await karte(trip, { context: 'route' });
		einOeffner(h, 'data-testid="was-steht-wo-email-format"');
	});
});
