// TDD RED — Issue #3036: Karte „Was steht wo“ bekommt unter „Ganze Blöcke ein- und ausschalten“ zwei Schalter
// Kurz-Zusammenfassung (show_compact_summary) und Großwetterlage (show_stability), nur im Trip.
// Spec docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md, AC-1, AC-4, AC-6.
//
// Server-Render der ECHTEN Datei organisms/wetter-tab/WasStehtWoKarte.svelte; die Antwort des Endpoints
// (GET /api/briefings/{id}/placements) setzt startzustandHook.mjs als Startwert (wie was_steht_wo_karte.test.ts).
// Kennungen: data-testid="was-steht-wo-show_compact_summary", data-testid="was-steht-wo-show_stability".
// Texte: Katalog-Keys wetter.wsw.bloecke.kurz, .kurz_hinweis, .grosswetterlage, .grosswetterlage_hinweis
// (Wortlaut steht nur im Katalog; der Test liest ihn von dort).
// RED heute: beide Schalter fehlen, die Keys fehlen im Katalog.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/rework_3036_bloecke_schalter.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const DATEI = path.resolve(HERE, '..', 'wetter-tab', 'WasStehtWoKarte.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { de } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/messages/de/index.ts')).href);
const { en } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/messages/en/index.ts')).href);
after(() => locale.set('de'));

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const g = globalThis as J;
const KATALOG: Record<'de' | 'en', Record<string, string>> = { de, en };

const START: [string, string][] = [
	['let antwort = $state<PlacementsAntwort | null>(null);', 'let antwort = $state<PlacementsAntwort | null>(globalThis.__wswAntwort);'],
	["let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');", "let phase = $state<'laedt' | 'fehler' | 'bereit'>(globalThis.__wswPhase ?? 'bereit');"]
];
async function karte(a: J, context: 'route' | 'vergleich'): Promise<string> {
	g.__wswAntwort = a;
	g.__wswPhase = undefined;
	const url = pathToFileURL(DATEI).href + `?start=${encodeURIComponent(JSON.stringify(START))}`;
	const K = (await import(url)).default;
	return render(K, { props: { id: 'abo-1', context } }).body.replace(/<!--[\s\S]*?-->/g, '');
}
const text = (h: string) =>
	h.replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
/** Öffnendes Tag des Elements mit genau dieser testid (alle Vorkommen). */
const tags = (h: string, testid: string) => h.match(new RegExp(`<[a-z][^>]*data-testid="${testid}"[^>]*>`, 'g')) ?? [];
const attr = (auf: string, name: string) => auf.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;
/** Katalogtext; fehlt der Key, ist das selbst der rote Befund. */
function k(lang: 'de' | 'en', key: string): string {
	assert.ok(Object.hasOwn(KATALOG[lang], key), `Katalog ${lang}: Key ${key} fehlt`);
	return KATALOG[lang][key];
}

const z = (state: string) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null });
function trip(blocks: J = {}, lang = 'de'): J {
	return {
		kind: 'route', lang, stored: true, placements: { version: 1, rows: [] }, location_count: null,
		columns: [
			{ stelle: 'email', subtitle: 'stundentabelle', block_off: false, rests: null },
			{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
			{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
			{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
		],
		fixed_rows: [],
		rows: [{ metric_id: 'wind', name: 'Wind-T', position: 0, parent: null, cells: { email: z('on'), telegram: z('on'), sms: z('on'), outlook: z('off') } }],
		sms_example: null,
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', outlook: { morning: false, evening: true }, ...blocks },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}
function orte(): J {
	return {
		kind: 'vergleich', lang: 'de', stored: true, placements: { version: 1, rows: [] }, location_count: 2,
		columns: [
			{ stelle: 'email', subtitle: 'uebersicht', block_off: false, rests: null },
			{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
			{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
			{ stelle: 'hourly', subtitle: 'nur_email', block_off: false, rests: null },
			{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
		],
		fixed_rows: [],
		rows: [{ metric_id: 'wind', name: 'Wind-O', position: 0, parent: null, cells: { email: z('on'), telegram: z('on'), sms: z('on'), hourly: z('on'), outlook: z('off') } }],
		sms_example: null,
		outlook_reports: ['evening'],
		// selbst wenn der Server die Felder mitliefert: im Orts-Vergleich keine Schalter
		blocks: { hourly: true, telegram_style: 'rich', outlook: { morning: false, evening: true }, show_compact_summary: true, show_stability: true },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}

const SCHALTER = [
	{ feld: 'show_compact_summary', titel: 'wetter.wsw.bloecke.kurz', hinweis: 'wetter.wsw.bloecke.kurz_hinweis' },
	{ feld: 'show_stability', titel: 'wetter.wsw.bloecke.grosswetterlage', hinweis: 'wetter.wsw.bloecke.grosswetterlage_hinweis' }
] as const;

describe('#3036 AC-1: zwei neue Block-Schalter im Trip', () => {
	for (const s of SCHALTER) {
		test(`${s.feld}: genau ein Schalter, Titel und Hinweis aus dem Katalog, fehlendes Feld = an`, async () => {
			locale.set('de');
			const h = await karte(trip(), 'route');
			const t = tags(h, `was-steht-wo-${s.feld}`);
			assert.equal(t.length, 1, `Schalter was-steht-wo-${s.feld} fehlt im Trip`);
			assert.equal(attr(t[0], 'aria-checked'), 'true', 'ohne gespeicherten Wert muss der Schalter an sein');
			assert.equal(attr(t[0], 'aria-disabled'), null, 'bei ausführlicher Mail bedienbar');
			assert.equal(attr(t[0], 'aria-label'), k('de', s.titel));
			const s2 = text(h);
			assert.ok(s2.includes(k('de', s.titel)), 'Titel fehlt');
			assert.ok(s2.includes(k('de', s.hinweis)), 'Hinweis fehlt');
		});
		test(`${s.feld}: gespeichert false → Schalter aus, das andere Feld bleibt an`, async () => {
			const h = await karte(trip({ [s.feld]: false }), 'route');
			assert.equal(attr(tags(h, `was-steht-wo-${s.feld}`)[0] ?? '', 'aria-checked'), 'false');
			const anderes = SCHALTER.find((x) => x.feld !== s.feld)!.feld;
			assert.equal(attr(tags(h, `was-steht-wo-${anderes}`)[0] ?? '', 'aria-checked'), 'true');
		});
	}
	test('Schalter stehen unter „Ganze Blöcke“, vor „Einstellungen je Kanal“', async () => {
		locale.set('de');
		const h = await karte(trip(), 'route');
		const bloecke = h.indexOf(k('de', 'wetter.wsw.bloecke.titel'));
		const kanal = h.indexOf(k('de', 'wetter.wsw.kanal.titel'));
		for (const s of SCHALTER) {
			const i = h.indexOf(`data-testid="was-steht-wo-${s.feld}"`);
			assert.ok(i > bloecke && i < kanal, `${s.feld} nicht im Abschnitt „Ganze Blöcke“`);
		}
	});
	test('Orts-Vergleich: keiner der zwei Schalter, auch wenn blocks sie trägt', async () => {
		const h = await karte(orte(), 'vergleich');
		assert.ok(tags(h, 'was-steht-wo-stundenverlauf').length === 1, 'Messaufbau: Orte-Karte nicht bereit gerendert');
		for (const s of SCHALTER) assert.equal(tags(h, `was-steht-wo-${s.feld}`).length, 0, `${s.feld} gehört nicht zu Orten`);
	});
});

describe('#3036 AC-4: bei E-Mail-Format Kompakt gesperrt mit „nur ausführlich“', () => {
	for (const s of SCHALTER) {
		test(`${s.feld}: aria-disabled, Hinweis um „Wirkt nur in der ausführlichen E-Mail.“ ergänzt, Wert bleibt`, async () => {
			locale.set('de');
			const h = await karte(trip({ email_format: 'compact', [s.feld]: false }), 'route');
			const t = tags(h, `was-steht-wo-${s.feld}`);
			assert.equal(t.length, 1, `Schalter was-steht-wo-${s.feld} fehlt`);
			assert.equal(attr(t[0], 'aria-disabled'), 'true', 'bei Kompakt nicht gesperrt');
			assert.equal(attr(t[0], 'aria-checked'), 'false', 'gespeicherter Wert bleibt sichtbar');
			assert.ok(text(h).includes(`${k('de', s.hinweis)}. ${k('de', 'wetter.wsw.bloecke.nur_ausfuehrlich')}`), 'Hinweis „nur ausführlich“ fehlt');
		});
	}
});

describe('#3036 AC-6: Titel und Hinweis in der Nutzersprache (EN)', () => {
	for (const s of SCHALTER) {
		test(`${s.feld}: englischer Titel/Hinweis aus dem Katalog, verschieden vom deutschen`, async () => {
			locale.set('en');
			try {
				const h = await karte(trip({}, 'en'), 'route');
				assert.notEqual(k('en', s.titel), k('de', s.titel), 'EN-Titel ist nur der deutsche Text');
				const t = tags(h, `was-steht-wo-${s.feld}`);
				assert.equal(t.length, 1, `Schalter was-steht-wo-${s.feld} fehlt (EN)`);
				assert.equal(attr(t[0], 'aria-label'), k('en', s.titel));
				assert.ok(text(h).includes(k('en', s.hinweis)), 'EN-Hinweis fehlt');
			} finally {
				locale.set('de');
			}
		});
	}
});
