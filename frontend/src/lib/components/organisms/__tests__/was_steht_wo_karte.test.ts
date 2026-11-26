// TDD RED — Issue #3122 Scheibe B3b: Organismus „Was steht wo“ im Reiter Wetter (Trip und Orte, EIN Code).
// Spec docs/specs/modules/feat_3122_was_steht_wo.md Teil B Nr. 10 bis 12; AC-22, AC-25 bis AC-28, AC-31, AC-33, AC-37.
// Soll-Bild docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html, Wortlaut einstellungen_neu.md §5 Punkt 8.
//
// Server-Render der ECHTEN Datei organisms/wetter-tab/WasStehtWoKarte.svelte. Die Antwort des Endpoints
// (GET /api/briefings/{id}/placements) setzt startzustandHook.mjs als Startwert des `$state` (der Server-Render
// führt kein onMount aus); Namen, Beispielwerte und SMS-Text stehen nur in diesen Antworten, nie im Code.
// Bedienung, Speichern, Neuladen, 390 px und Kontrast: frontend/e2e/was-steht-wo-karte.spec.ts.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
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
async function karte(a: J, props: Record<string, unknown>, phase?: string): Promise<string> {
	assert.ok(existsSync(DATEI), 'TDD RED: organisms/wetter-tab/WasStehtWoKarte.svelte fehlt');
	g.__wswAntwort = a;
	g.__wswPhase = phase;
	// Der Startwert wird beim Erzeugen der Komponente gelesen (nicht beim Laden des Moduls): ein Modul genügt.
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

type Element = { auf: string; innen: string };
function elemente(h: string, merkmal: string): Element[] {
	const aus: Element[] = [];
	const auf = /<([a-z][a-z0-9]*)\b[^>]*>/g;
	for (let m = auf.exec(h); m; m = auf.exec(h)) {
		if (!m[0].includes(merkmal)) continue;
		const name = m[1];
		if (m[0].endsWith('/>') || ['input', 'img', 'br'].includes(name)) {
			aus.push({ auf: m[0], innen: '' });
			continue;
		}
		const re = new RegExp(`<${name}\\b[^>]*>|</${name}>`, 'g');
		re.lastIndex = m.index + m[0].length;
		let tiefe = 1;
		for (let t = re.exec(h); t; t = re.exec(h)) {
			if (t[0].startsWith('</')) tiefe--;
			else if (!t[0].endsWith('/>')) tiefe++;
			if (tiefe === 0) {
				aus.push({ auf: m[0], innen: h.slice(m.index + m[0].length, t.index) });
				break;
			}
		}
	}
	return aus;
}
const eins = (h: string, merkmal: string): Element => {
	const e = elemente(h, merkmal);
	assert.equal(e.length, 1, `erwartet genau ein Element mit ${merkmal}, gefunden ${e.length}`);
	return e[0];
};
const attr = (auf: string, name: string) => auf.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;
const zelle = (h: string, metrik: string, stelle: string) => eins(eins(h, `data-metrik="${metrik}"`).innen, `data-stelle="${stelle}"`);
const kopfStellen = (h: string) => elemente(eins(h, 'data-slot="et-kopf"').innen, 'data-slot="et-kopf-stelle"');
const hatKnopf = (h: string, metrik: string, stelle: string) => elemente(zelle(h, metrik, stelle).innen, 'data-slot="roh-einfach"').length > 0;
const kaestchen = (h: string, metrik: string, stelle: string) => elemente(zelle(h, metrik, stelle).innen, 'type="checkbox"')[0]?.auf ?? '';

// ── Antworten des Endpoints (Form laut docs/reference/api_contract.md) ─────────────────────────
const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
const LEGENDE_FEST = [
	['@14', 'zeit_ab_gelb'], ['!TS:H@14', 'amtliche_warnung'], ['L', 'stufe_gelb'], ['M', 'stufe_orange'], ['H', 'stufe_rot'],
	['WG', 'warnung_wind'], ['RA', 'warnung_starkregen'], ['AV4', 'lawinenstufe'], ['X?', 'warnquelle_nicht_erreichbar']
].map(([token, key]) => ({ token, key }));

function trip(extra: J = {}): J {
	return {
		kind: 'route', lang: 'de', stored: true, placements: { version: 1, rows: [] }, location_count: null,
		columns: [
			{ stelle: 'email', subtitle: 'stundentabelle', block_off: false, rests: null },
			{ stelle: 'telegram', subtitle: 'nachricht', block_off: false, rests: null },
			{ stelle: 'sms', subtitle: 'und_premium_sms', block_off: false, rests: null },
			{ stelle: 'outlook', subtitle: 'email_und_telegram', block_off: false, rests: null }
		],
		fixed_rows: [{ id: 'amtliche_warnungen', position: { email: 'first', telegram: 'first', sms: 'last' } }],
		rows: [
			{ metric_id: 'temperature_night', name: 'Nachtwert-T', position: 0, parent: null, cells: {
				email: z('locked', { reason: 'keine_eigene_spalte' }), telegram: z('on'), sms: z('on', { example: 'N14' }), outlook: z('locked', { reason: 'kein_tageswert' }) } },
			{ metric_id: 'gust', name: 'Boe-T', position: 1, parent: null, cells: {
				email: z('on', { format: 'simplified', ampel: 'yellow' }), telegram: z('on', { format: 'raw', example: 'G 26-59@15', mark: 'nur_tageswert' }),
				sms: z('on', { format: 'raw', example: 'G32@6(59@15)', mark: 'passt_nicht_mehr' }), outlook: z('on', { format: 'raw', example: '85 km/h' }) } },
			{ metric_id: 'wind', name: 'Wind-T', position: 2, parent: null, cells: {
				email: z('off', { format: 'simplified' }), telegram: z('off', { format: 'raw' }), sms: z('on', { mark: 'passt_nicht_mehr' }), outlook: z('not_in_email', { format: 'raw' }) } }
		],
		sms_example: { text: 'Etappe-X: N14 W30', length: 17, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', outlook: { morning: false, evening: true } },
		legend: { metrics: [{ metric_id: 'temperature_night', kuerzel: 'N', meaning: 'Nacht-Bedeutung' }, { metric_id: 'gust', kuerzel: 'G', meaning: null }], fixed: LEGENDE_FEST },
		example_version: 1, ...extra
	};
}
function orte(anzahl: number, extra: J = {}): J {
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
				email: z('on', { format: 'raw', example: '43 km/h' }), telegram: z('on', { format: 'raw', example: 'Wind 43 km/h' }), sms: z('on', { example: 'W43@16' }),
				hourly: z('on', { format: 'raw', example: '28' }), outlook: z('on', { format: 'raw', example: '60 km/h' }) } },
			{ metric_id: 'sunshine', name: 'Sonne-O', position: 1, parent: null, cells: {
				email: z('on', { format: 'raw', example: '5.0 h' }), telegram: z('on', { format: 'raw' }), sms: z('on', { mark: 'passt_nicht_mehr' }),
				hourly: z('locked', { reason: 'kein_stundenwert' }), outlook: z('off', { format: 'raw' }) } },
			{ metric_id: 'uv_index', name: 'UV-O', position: 2, parent: null, cells: {
				email: z('on', { example: '7' }), telegram: z('on'), sms: z('locked', { reason: 'kein_kuerzel' }), hourly: z('on'), outlook: z('off') } }
		],
		sms_example: anzahl > 1
			? { text: 'O1 W43@16 O2 W44@16 O3 W45@16', length: 29, max_length: 160 }
			: { text: 'O1 W43@16', length: 9, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { hourly: true, telegram_style: 'rich', outlook: { morning: false, evening: true } },
		legend: { metrics: [{ metric_id: 'wind', kuerzel: 'W', meaning: 'Wind km/h' }, { metric_id: 'sunshine', kuerzel: 'SU', meaning: 'Sonne-Bedeutung' }], fixed: LEGENDE_FEST },
		example_version: 1, ...extra
	};
}

describe('Aufbau und Spalten je Kontext (AC-22)', () => {
	test('Trip: Abschnitt-Marker, Kartentext, vier Spalten mit Unterzeile, kein Stundenverlauf, keine Premium-SMS-Spalte', async () => {
		locale.set('de');
		const h = await karte(trip(), { context: 'route' });
		const wurzel = eins(h, 'data-abschnitt="was-steht-wo"');
		assert.equal(attr(wurzel.auf, 'data-context'), 'route');
		assert.match(text(h), /Was steht wo Eine Tabelle für alles\. .*die drei Kanäle und der 3-Tages-Ausblick\. Der Ausblick gibt es nur/);
		const k = kopfStellen(h);
		assert.deepEqual(k.map((x) => attr(x.auf, 'data-stelle')), ['email', 'telegram', 'sms', 'outlook']);
		assert.deepEqual(k.map((x) => text(x.innen)), [
			'E-Mail E-Mail Stundentabelle', 'Telegram Telegram Nachricht', 'SMS SMS und Premium-SMS', '3-Tages-Ausblick Ausbl. E-Mail und Telegram'
		]);
		assert.doesNotMatch(text(h), /Stundenverlauf/);
	});
	test('Orte: fünf Spalten, E-Mail „Übersicht“, Stundenverlauf „nur E-Mail“, Telegram im engen Raster „Telegr.“', async () => {
		const h = await karte(orte(3), { context: 'vergleich' });
		const k = kopfStellen(h);
		assert.deepEqual(k.map((x) => attr(x.auf, 'data-stelle')), ['email', 'telegram', 'sms', 'hourly', 'outlook']);
		assert.equal(text(k[0].innen), 'E-Mail E-Mail Übersicht');
		assert.equal(text(k[1].innen), 'Telegram Telegr. Nachricht');
		assert.equal(text(k[3].innen), 'Stundenverlauf Std. nur E-Mail');
		assert.match(text(h), /die drei Kanäle, der Stundenverlauf und der 3-Tages-Ausblick\. Stundenverlauf und Ausblick gibt es nur/);
	});
	// #3020 R1 (E025 bis E027, E030): die Regel „ein Kanal kann nur abwählen“ (#2438, ADR-0050) steht im Kartentext.
	const ABWAHL_REGEL = {
		de: ['Jede Zeile ist eine Metrik aus der Auswahl oben.', 'Hier wählst du nur ab.', 'Neue Metriken kommen oben über „+“ dazu.'],
		en: ['Each row is a metric from the selection above.', 'Here you only deselect.', 'New metrics are added above via “+”.']
	};
	for (const context of ['route', 'vergleich'] as const) {
		for (const sprache of ['de', 'en'] as const) {
			test(`Kartentext nennt die Abwahl-Regel: Zeilen aus der Grundauswahl, hier nur abwählen (${context}, ${sprache})`, async () => {
				locale.set(sprache);
				try {
					const h = await karte(context === 'route' ? trip() : orte(3), { context });
					const t = text(eins(h, 'data-abschnitt="was-steht-wo"').innen);
					for (const satz of ABWAHL_REGEL[sprache]) assert.ok(t.includes(satz), `Kartentext ohne „${satz}“`);
				} finally {
					locale.set('de');
				}
			});
		}
	}
	test('Zeilen in der Folge der Antwort mit Namen aus der Antwort', async () => {
		const h = await karte(trip(), { context: 'route' });
		const zeilen = elemente(h, 'data-slot="et-zeile"');
		assert.deepEqual(zeilen.map((x) => attr(x.auf, 'data-metrik')), ['temperature_night', 'gust', 'wind']);
		assert.match(text(zeilen[1].innen), /^Boe-T/);
	});
});

describe('Feste Zeile „Amtliche Warnungen“ (AC-18, Oberflächen-Teil)', () => {
	test('steht da, wenn die Antwort sie liefert; mit festem Haken in E-Mail, Telegram, SMS', async () => {
		const h = await karte(trip(), { context: 'route' });
		const fest = eins(h, 'data-slot="et-fest"');
		assert.match(text(fest.innen), /^Amtliche Warnungen immer dabei: in E-Mail und Telegram zuerst, in der SMS am Ende/);
		assert.equal(elemente(fest.innen, 'data-zustand="fest"').length, 3);
	});
	test('fehlt ohne Eintrag in fixed_rows', async () => {
		const h = await karte(orte(3), { context: 'vergleich' });
		assert.equal(elemente(h, 'data-slot="et-fest"').length, 0);
	});
});

describe('Zustände der Zellen (AC-26)', () => {
	test('gesperrt mit Grundtext je reason, nicht in der E-Mail, ab', async () => {
		const t = await karte(trip(), { context: 'route' });
		assert.match(text(zelle(t, 'temperature_night', 'email').innen), /keine eigene Spalte/);
		assert.match(text(zelle(t, 'temperature_night', 'outlook').innen), /kein Tageswert/);
		assert.equal(attr(zelle(t, 'wind', 'outlook').auf, 'data-zustand'), 'not_in_email');
		assert.match(zelle(t, 'wind', 'outlook').innen, /nicht in der E-Mail/);
		assert.doesNotMatch(kaestchen(t, 'wind', 'email'), /\schecked/);
		const o = await karte(orte(3), { context: 'vergleich' });
		assert.match(text(zelle(o, 'sunshine', 'hourly').innen), /kein Stundenwert/);
		assert.match(text(zelle(o, 'uv_index', 'sms').innen), /kein Kürzel/);
	});
	test('Spalte eines ausgeschalteten Blocks ist nicht bedienbar (Stundenverlauf aus, Ausblick in keinem Briefing)', async () => {
		const o = await karte(orte(3, { blocks: { hourly: false, telegram_style: 'rich', outlook: { morning: false, evening: false } }, outlook_reports: [] }), { context: 'vergleich' });
		assert.match(kaestchen(o, 'wind', 'hourly'), /\sdisabled/);
		assert.match(kaestchen(o, 'wind', 'outlook'), /\sdisabled/);
		assert.doesNotMatch(kaestchen(o, 'wind', 'email'), /\sdisabled/);
	});
});

describe('Roh/Einfach nur wo erlaubt (AC-25)', () => {
	test('Knopf nur bei Haken und zwei Formen, nie in der SMS-Spalte', async () => {
		const t = await karte(trip(), { context: 'route' });
		assert.equal(hatKnopf(t, 'gust', 'email'), true);
		assert.equal(hatKnopf(t, 'gust', 'outlook'), true);
		assert.equal(hatKnopf(t, 'gust', 'sms'), false, 'SMS-Spalte hat nie einen Knopf, auch wenn die Antwort ein Format nennt');
		assert.equal(hatKnopf(t, 'wind', 'email'), false, 'kein Knopf ohne Haken');
		assert.equal(hatKnopf(t, 'temperature_night', 'telegram'), false, 'kein Knopf ohne zwei Formen');
	});
	test('Ampelpunkt aus der Antwort mit Farbwort', async () => {
		const t = await karte(trip(), { context: 'route' });
		const punkt = eins(zelle(t, 'gust', 'email').innen, 'data-slot="et-ampel"');
		assert.equal(attr(punkt.auf, 'data-farbe'), 'yellow');
		assert.equal(attr(punkt.auf, 'aria-label'), 'gelb');
	});
});

describe('Marken und SMS-Beispiel (AC-27, AC-28)', () => {
	test('Trip: „nur Tageswert“, „passt nicht mehr“, Zeile mit max_length und Hinweissatz für Trip', async () => {
		const t = await karte(trip(), { context: 'route' });
		assert.match(text(zelle(t, 'gust', 'telegram').innen), /nur Tageswert/);
		assert.match(text(zelle(t, 'gust', 'sms').innen), /passt nicht mehr/);
		const sms = text(eins(t, 'data-testid="was-steht-wo-sms"').innen);
		assert.equal(sms, 'SMS-Beispiel: Etappe-X: N14 W30 · 17 von 160 Zeichen Die letzten 2 Metriken passen nicht mehr in die SMS. Zieh nach oben, was dir in der SMS wichtig ist.');
	});
	// #3385 AC-6 (Spec rework_3385_waisen_s3.md): Nachfolger von versand_telegram_je_kontext.test.ts für den
	// Fallliste-Fall E-R8-F3N-VERSAND-TRIP. Die Grenze (7 Zeilen) rechnet das Backend; die Karte zeigt die
	// Marke je Zeile aus der Antwort (ADR-0124 Nr. 3).
	test('Trip mit neun Zeilen: Telegram-Marke „nur Tageswert“ erst ab der achten Zeile', async () => {
		locale.set('de');
		const ids = ['temperature', 'gust', 'wind', 'precipitation', 'rain_probability', 'cloud_cover', 'humidity', 'uv_index', 'sunshine'];
		const rows = ids.map((metric_id, i) => ({
			metric_id, name: `Zeile-${i + 1}`, position: i, parent: null, cells: {
				email: z('on'), telegram: z('on', i >= 7 ? { mark: 'nur_tageswert' } : {}), sms: z('on'), outlook: z('off')
			}
		}));
		const t = await karte(trip({ rows }), { context: 'route' });
		assert.deepEqual(elemente(t, 'data-slot="et-zeile"').map((x) => attr(x.auf, 'data-metrik')), ids);
		const mitMarke = ids.filter((id) => /nur Tageswert/.test(text(zelle(t, id, 'telegram').innen)));
		assert.deepEqual(mitMarke, ['uv_index', 'sunshine'], 'nur Tageswert genau in den Telegram-Zellen der Zeilen 8 und 9');
		for (const id of ids) {
			for (const stelle of ['email', 'sms', 'outlook']) {
				assert.doesNotMatch(text(zelle(t, id, stelle).innen), /nur Tageswert/, `${id}/${stelle} trägt keine Telegram-Marke`);
			}
		}
	});
	test('drei Orte: Grenze aus der Antwort (160), Fassung für mehrere Orte ohne „+N“ je Ort (#3172)', async () => {
		const o = await karte(orte(3), { context: 'vergleich' });
		const sms = text(eins(o, 'data-testid="was-steht-wo-sms"').innen);
		assert.match(sms, /^SMS-Beispiel: O1 W43@16 O2 W44@16 O3 W45@16 · 29 von 160 Zeichen /);
		assert.match(sms, /Bei 3 Orten passt die letzte Metrik nicht mehr in die SMS\. Zieh nach oben/);
		// #3172: die Orte-SMS kennt keinen Rest-Zähler „+N“ je Ort mehr -- kein Satz dazu.
		assert.doesNotMatch(sms, /je Ort/);
	});
	test('ein Ort: Fassung wie Trip, SMS beginnt mit O1 (keine Ortsnamen, #3172)', async () => {
		const o = await karte(orte(1), { context: 'vergleich' });
		const sms = text(eins(o, 'data-testid="was-steht-wo-sms"').innen);
		assert.match(sms, /^SMS-Beispiel: O1 W43@16 · 9 von 160 Zeichen /);
		assert.match(sms, /Die letzte Metrik passt nicht mehr in die SMS\./);
		assert.doesNotMatch(sms, /Orten/);
	});
	test('ohne SMS-Beispiel keine Zeile', async () => {
		const o = await karte(orte(0, { sms_example: null }), { context: 'vergleich' });
		assert.equal(elemente(o, 'data-testid="was-steht-wo-sms"').length, 0);
	});
	test('Kurzstil: Telegram-Spalte „Kurzstil: wie SMS“, Haken nicht bedienbar, keine Marke', async () => {
		const t = await karte(trip({ blocks: { ...trip().blocks, telegram_style: 'kurzform' } }), { context: 'route' });
		assert.equal(text(kopfStellen(t)[1].innen), 'Telegram Telegram Kurzstil: wie SMS');
		assert.match(kaestchen(t, 'gust', 'telegram'), /\sdisabled/);
		assert.doesNotMatch(text(zelle(t, 'gust', 'telegram').innen), /nur Tageswert/);
	});
});

describe('„Kürzel erklärt“ (AC-31)', () => {
	test('beim Öffnen geschlossen; Kürzel der Metriken mit SMS-Haken und feste Einträge; kein Legenden-Satz', async () => {
		const o = await karte(orte(3), { context: 'vergleich' });
		const feld = eins(o, 'data-testid="was-steht-wo-legende"');
		assert.doesNotMatch(feld.auf, /\sopen/);
		const inhalt = text(feld.innen);
		assert.match(inhalt, /^Kürzel erklärt/);
		assert.match(inhalt, /W Wind km\/h/);
		assert.match(inhalt, /SU Sonne-Bedeutung/);
		for (const s of ['@14 ab 14 Uhr gelb oder schlechter', '!TS:H@14 amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr', 'L Stufe gelb', 'M Stufe orange', 'H Stufe rot', 'WG Warnung Wind', 'RA Warnung Starkregen', 'AV4 Lawinenstufe', 'X? Warnquelle nicht erreichbar'])
			assert.ok(inhalt.includes(s), `fehlt: ${s}`);
		assert.doesNotMatch(o, /Legende steht auch am Ende/);
	});
	test('dasselbe Kürzel zweier Zeilen und ein Kürzel gleich einem festen Token rendern ohne Abbruch', async () => {
		const a = orte(3);
		a.legend.metrics = [...a.legend.metrics, { metric_id: 'sunshine', kuerzel: 'W', meaning: 'Wind km/h' }, { metric_id: 'wind', kuerzel: 'L', meaning: 'Tiefstwert' }];
		const o = await karte(a, { context: 'vergleich' });
		assert.equal(elemente(o, 'data-legende="W"').length, 1, 'gleicher Eintrag nur einmal');
		assert.equal(elemente(o, 'data-legende="L"').length, 2, 'L als Metrik-Kürzel und als Stufe gelb');
	});
	test('#3172: fester Eintrag mit Bedeutung aus der Antwort (O1 der Orte-SMS) erscheint, ohne Bedeutung und Schlüssel nicht', async () => {
		const a = orte(3);
		a.legend.fixed = [...a.legend.fixed, { token: 'O1', key: 'ort_nummer', meaning: 'Ort 1 in der Reihenfolge des Abos' }, { token: 'Q9', key: 'unbekannt' }];
		const o = await karte(a, { context: 'vergleich' });
		const inhalt = text(eins(o, 'data-testid="was-steht-wo-legende"').innen);
		assert.ok(inhalt.includes('O1 Ort 1 in der Reihenfolge des Abos'), inhalt);
		assert.equal(elemente(o, 'data-legende="Q9"').length, 0, 'unbekannter Schlüssel ohne Bedeutung bleibt weg');
	});
	test('Kürzel einer Metrik ohne SMS-Haken fehlt; Eintrag ohne Bedeutung zeigt nur das Kürzel', async () => {
		const a = trip();
		a.rows[0].cells.sms = z('off');
		const t = await karte(a, { context: 'route' });
		const inhalt = text(eins(t, 'data-testid="was-steht-wo-legende"').innen);
		assert.doesNotMatch(inhalt, /Nacht-Bedeutung/);
		assert.ok(elemente(t, 'data-legende="G"').length === 1, 'G steht in der Legende');
		assert.equal(text(eins(t, 'data-legende="G"').innen), 'G');
	});
});

describe('Blöcke und Einstellungen je Kanal (AC-29, AC-30, AC-37)', () => {
	test('Trip: Ausblick Morgen/Abend, Etappen-Kennzahlen, Vortag-Vergleich, Nacht-Stundentabelle, E-Mail-Format, Kurzstil, Premium-SMS', async () => {
		const t = await karte(trip(), { context: 'route' });
		const s = text(t);
		for (const w of ['Ganze Blöcke ein- und ausschalten', '3-Tages-Ausblick Tageswerte der nächsten drei Etappen, in E-Mail und Telegram. Vorbelegt: nur im Abend-Briefing.',
			'Etappen-Kennzahlen', 'Vortag-Vergleich', 'Nacht-Stundentabelle', 'Einstellungen je Kanal', 'E-Mail: Format', 'Ausführlich (HTML)', 'Kompakt (Nur-Text)',
			'Telegram: Kurzstil', 'Premium-SMS Bekommt vorerst denselben Text wie die SMS. Eine eigene Auswahl kommt später.'])
			assert.ok(s.includes(w), `fehlt: ${w}`);
		assert.doesNotMatch(s, /Stunden-Tabelle/);
		assert.equal(attr(eins(t, 'data-testid="was-steht-wo-ausblick-morning"').auf, 'aria-checked'), 'false');
		assert.equal(attr(eins(t, 'data-testid="was-steht-wo-ausblick-evening"').auf, 'aria-checked'), 'true');
	});
	// #3020 R1 (E067, E068): jede Zeile der Trip-Karte zeigt Titel und Hinweis IHRES Katalogeintrags, in beiden Sprachen.
	const ZEILEN_3020: { testid: string; titel: string; hinweis: string; name?: string }[] = [
		...[['show_stage_stats', 'etappen'], ['show_yesterday_comparison', 'vortag'], ['show_night_block', 'nacht'], ['show_compact_summary', 'kurz'], ['show_stability', 'grosswetterlage']]
			.map(([feld, k]) => ({ testid: `was-steht-wo-${feld}`, titel: `bloecke.${k}`, hinweis: `bloecke.${k}_hinweis` })),
		{ testid: 'was-steht-wo-ausblick-morning', titel: 'bloecke.ausblick', hinweis: 'bloecke.ausblick_hinweis_route', name: 'bloecke.ausblick_morgen' },
		{ testid: 'was-steht-wo-ausblick-evening', titel: 'bloecke.ausblick', hinweis: 'bloecke.ausblick_hinweis_route', name: 'bloecke.ausblick_abend' },
		{ testid: 'was-steht-wo-email-format', titel: 'kanal.email_format', hinweis: 'kanal.email_format_hinweis' }
	];
	for (const sprache of ['de', 'en'] as const) {
		test(`Trip: alle Blöcke, Ausblick und E-Mail-Format mit Titel und Hinweis aus dem Katalog (${sprache})`, async () => {
			const katalog = async (l: 'de' | 'en') => (await import(pathToFileURL(path.join(FRONTEND, `src/lib/i18n/messages/${l}/index.ts`)).href))[l] as Record<string, string>;
			const [de, en] = [await katalog('de'), await katalog('en')];
			const wert = (k: string) => ({ de, en })[sprache][`wetter.wsw.${k}`];
			locale.set(sprache);
			try {
				const h = await karte(trip(), { context: 'route' });
				for (const z3 of ZEILEN_3020) {
					const zeilen = elemente(h, 'data-slot="einstellungszeile"').filter((x) => x.innen.includes(`data-testid="${z3.testid}"`));
					assert.equal(zeilen.length, 1, `${z3.testid}: genau eine Zeile`);
					const soll = `${wert(z3.titel)} ${wert(z3.hinweis)}`;
					assert.ok(text(zeilen[0].innen).startsWith(soll), `${z3.testid}: „${text(zeilen[0].innen)}“ beginnt nicht mit „${soll}“`);
					assert.equal(attr(eins(zeilen[0].innen, `data-testid="${z3.testid}"`).auf, 'aria-label'), wert(z3.name ?? z3.titel), `${z3.testid}: aria-label`);
					for (const k of [z3.titel, z3.hinweis, z3.name ?? z3.titel])
						assert.notEqual(en[`wetter.wsw.${k}`], de[`wetter.wsw.${k}`], `${k}: englischer Text gleich dem deutschen`);
				}
				for (const [id, k] of [['full', 'ausfuehrlich'], ['compact', 'kompakt']])
					assert.equal(text(eins(h, `data-testid="was-steht-wo-email-format-${id}"`).innen), wert(`kanal.${k}`));
			} finally {
				locale.set('de');
			}
		});
	}
	test('Fix-Loop T2: Kurzstil ohne verbundenes Telegram gesperrt; ein eingeschalteter Kurzstil bleibt abschaltbar (AC-28)', async () => {
		const aus = await karte(trip(), { context: 'route' });
		assert.equal(attr(eins(aus, 'data-testid="was-steht-wo-kurzstil"').auf, 'aria-disabled'), 'true');
		const an = await karte(trip({ blocks: { ...trip().blocks, telegram_style: 'kurzform' } }), { context: 'route' });
		assert.equal(attr(eins(an, 'data-testid="was-steht-wo-kurzstil"').auf, 'aria-disabled'), null);
	});
	// #3059 (AC-13): das E-Mail-Format gehört seither auch zu Orten (Format-Schalter: was_steht_wo_karte_orte_format_3059.test.ts).
	test('drei Orte: Stundenverlauf „je Ort“, E-Mail-Format, keine Trip-Blöcke', async () => {
		const s = text(await karte(orte(3), { context: 'vergleich' }));
		assert.ok(s.includes('Stundenverlauf Stunden-Tabelle je Ort unter der Übersicht, nur in der E-Mail.'));
		assert.ok(s.includes('Tageswerte der nächsten drei Tage'));
		assert.ok(s.includes('E-Mail: Format'), 'E-Mail-Format gehört seit #3059 auch zu Orten');
		for (const w of ['Etappen-Kennzahlen', 'Vortag-Vergleich', 'Nacht-Stundentabelle']) assert.ok(!s.includes(w), `${w} gehört nicht zu Orten`);
	});
	test('ein Ort: „Stunden-Tabelle unter der Übersicht, nur in der E-Mail.“ ohne „je Ort“ (AC-37)', async () => {
		const s = text(await karte(orte(1), { context: 'vergleich' }));
		assert.ok(s.includes('Stunden-Tabelle unter der Übersicht, nur in der E-Mail.'));
		assert.doesNotMatch(s, /je Ort/);
	});
});

describe('Zustände der Karte', () => {
	test('Laden und Fehler mit erneutem Versuch', async () => {
		const l = await karte(null, { context: 'route' }, 'laedt');
		assert.match(text(eins(l, 'data-testid="was-steht-wo-laden"').innen), /Lade die Tabelle/);
		const f = await karte(null, { context: 'route' }, 'fehler');
		const fehler = eins(f, 'data-testid="was-steht-wo-fehler"');
		assert.equal(attr(fehler.auf, 'role'), 'alert');
		assert.match(text(fehler.innen), /Die Tabelle konnte nicht geladen werden\. Erneut laden/);
	});
	test('leere Grundauswahl: sachlicher Leertext statt Tabelle', async () => {
		const h = await karte(orte(3, { rows: [], sms_example: null }), { context: 'vergleich' });
		assert.equal(elemente(h, 'data-slot="einstell-tabelle"').length, 0);
		assert.match(text(eins(h, 'data-testid="was-steht-wo-leer"').innen), /Im Briefing steht keine Metrik/);
	});
});

describe('Englisch (AC-33)', () => {
	test('alle Texte englisch, Namen und Kürzel aus der Antwort unverändert', async () => {
		locale.set('en');
		try {
			const h = await karte(orte(3), { context: 'vergleich' });
			const s = text(h);
			for (const w of ['What goes where', 'One table for everything.', 'Email', 'Overview', 'Hourly view', 'email only', 'and Premium SMS', 'SMS example:', '29 of 160 characters',
				'Abbreviations explained', 'Switch whole blocks on and off', 'Settings per channel', 'Premium SMS'])
				assert.ok(s.includes(w), `fehlt: ${w}`);
			for (const w of ['Was steht wo', 'Übersicht', 'Stundenverlauf', 'Zeichen', 'Kürzel erklärt', 'Einstellungen je Kanal']) assert.ok(!s.includes(w), `deutsch: ${w}`);
			assert.ok(s.includes('Wind-O') && s.includes('W Wind km/h'), 'Namen und Kürzel aus der Antwort');
		} finally {
			locale.set('de');
		}
	});
});

// ── #3283: Optik-Befunde der Bildprüfung (Spec docs/specs/modules/fix_3283_was_steht_wo_optik.md, B1/B2/B6/B7) ──
// Markup per Server-Render der echten Karte (Antwort -> wasStehtWoAnsicht -> EinstellTabelle). Maße und Farben,
// die nur im <style> der echten Dateien stehen, aus dem CSS-Baum des Svelte-Parsers mit aufgelösten Tokens aus
// app.css (doc-compliance-test: CSS-Werte sind im Server-Render nicht sichtbar; die berechneten Stile und das
// Bild prüft frontend/e2e/was-steht-wo-bildabgleich.staging.spec.ts).
const { parse: svelteParse } = await import('svelte/compiler');

/** Werte der Design-Tokens (erste Definition = Hellmodus) aus app.css. */
function tokens(): Map<string, string> {
	const css = readFileSync(path.join(FRONTEND, 'src', 'app.css'), 'utf8');
	const aus = new Map<string, string>();
	for (const m of css.matchAll(/(--g-[\w-]+)\s*:\s*([^;]+);/g)) if (!aus.has(m[1])) aus.set(m[1], m[2].trim());
	return aus;
}
const TOKEN = tokens();
const aufloesen = (wert: string): string => wert.replace(/var\((--g-[\w-]+)\)/g, (_, n: string) => aufloesen(TOKEN.get(n) ?? `?${n}`));
/** Oberste Regeln (nicht in @media) einer Svelte-Datei: Selektor-Text und Deklarationen. */
function regeln(datei: string): { selektor: string; decl: Record<string, string> }[] {
	const quelle = readFileSync(datei, 'utf8');
	const ast: J = svelteParse(quelle, { modern: true });
	return (ast.css?.children ?? [])
		.filter((c: J) => c.type === 'Rule')
		.map((c: J) => ({
			selektor: quelle.slice(c.prelude.start, c.prelude.end).replace(/\s+/g, ' ').trim(),
			decl: Object.fromEntries(c.block.children.filter((d: J) => d.type === 'Declaration').map((d: J) => [d.property, String(d.value).trim()]))
		}));
}
const TABELLE_DATEI = path.resolve(HERE, '..', '..', 'molecules', 'EinstellTabelle.svelte');

function trip3283(): J {
	const a = trip();
	a.rows = [
		{ metric_id: 'temperature', name: 'Temp-T', position: 0, parent: null, cells: {
			email: z('on', { example: 'Temp 14.4' }), telegram: z('on', { example: 'T 14.3-18.5' }), sms: z('on', { example: 'N14 D14/18' }), outlook: z('on', { example: '12/25' }) } },
		{ metric_id: 'cloud_total', name: 'Wolke-T', position: 1, parent: null, cells: {
			email: z('on', { format: 'simplified', example: '⛅' }), telegram: z('on', { format: 'simplified', example: 'CT ⛅-🌥️@15' }), sms: z('on', { example: 'CT:BKN@15' }), outlook: z('on', { format: 'simplified', example: '⛅' }) } },
		{ metric_id: 'gust', name: 'Boe-T', position: 2, parent: null, cells: {
			email: z('on', { format: 'raw', example: 'Gust 38' }), telegram: z('on', { format: 'raw', example: 'G 26-59@15' }), sms: z('on', { example: 'G32@6(59@15)' }), outlook: z('on', { format: 'raw', example: '85 km/h' }) } }
	];
	return a;
}
const beispiele = (h: string, metrik: string, stelle: string) => elemente(zelle(h, metrik, stelle).innen, 'data-slot="et-beispiel"');
const rasterVon = (h: string) =>
	(attr(eins(h, 'data-slot="et-kopf"').auf, 'style') ?? '')
		.replace(/^.*grid-template-columns:\s*/, '')
		.replace(/;.*$/, '')
		.trim();

describe('#3283 B2: Zusatzspalten zeigen nur Haken und Roh/Einfach, keinen Beispielwert (AC-2)', () => {
	test('Trip: Ausblick ohne Beispielwert, obwohl die Antwort einen liefert; Kanalspalten behalten ihn', async () => {
		locale.set('de');
		const h = await karte(trip3283(), { context: 'route' });
		assert.equal(beispiele(h, 'gust', 'outlook').length, 0, 'Ausblick zeigt „85 km/h“');
		assert.doesNotMatch(text(zelle(h, 'gust', 'outlook').innen), /85 km\/h/);
		assert.equal(hatKnopf(h, 'gust', 'outlook'), true, 'Roh/Einfach bleibt im Ausblick');
		assert.equal(text(beispiele(h, 'gust', 'telegram')[0]?.innen ?? ''), 'G 26-59@15');
		assert.equal(text(beispiele(h, 'temperature', 'sms')[0]?.innen ?? ''), 'N14 D14/18');
	});
	for (const anzahl of [3, 1]) {
		test(`Orte (${anzahl}): Stundenverlauf und Ausblick ohne Beispielwert, E-Mail mit`, async () => {
			const o = await karte(orte(anzahl), { context: 'vergleich' });
			assert.equal(beispiele(o, 'wind', 'hourly').length, 0, 'Stundenverlauf zeigt „28“');
			assert.equal(beispiele(o, 'wind', 'outlook').length, 0, 'Ausblick zeigt „60 km/h“');
			assert.equal(hatKnopf(o, 'wind', 'hourly'), true, 'Roh/Einfach bleibt im Stundenverlauf');
			assert.equal(text(beispiele(o, 'wind', 'email')[0]?.innen ?? ''), '43 km/h');
		});
	}
});

describe('#3283 B1: Spaltenbreiten nach Soll-Bild, kein abgeschnittener Beispielwert (AC-1)', () => {
	const KANAL = 'minmax(var(--g-size-150px), 1fr)';
	const ZUSATZ = 'var(--g-size-118px)';
	const VORN = ['var(--g-size-22px)', 'minmax(var(--g-size-130px), 0.9fr)'];
	test('Trip: drei Kanalspalten mindestens 150 px, Ausblick 118 px', async () => {
		const h = await karte(trip3283(), { context: 'route' });
		assert.equal(rasterVon(h), [...VORN, KANAL, KANAL, KANAL, ZUSATZ].join(' '));
	});
	test('Orte: drei Kanalspalten mindestens 150 px, Stundenverlauf und Ausblick je 118 px', async () => {
		const o = await karte(orte(3), { context: 'vergleich' });
		assert.equal(rasterVon(o), [...VORN, KANAL, KANAL, KANAL, ZUSATZ, ZUSATZ].join(' '));
	});
	test('Tokens 150px/118px existieren; Beispielwert ohne Auslassungspunkte (doc-compliance-test)', () => {
		// doc-compliance-test: Token-Werte und text-overflow sind im Server-Render nicht sichtbar.
		assert.equal(TOKEN.get('--g-size-150px'), '150px');
		assert.equal(TOKEN.get('--g-size-118px'), '118px');
		const r = regeln(TABELLE_DATEI).find((x) => x.selektor === '.et-beispiel');
		assert.ok(r, 'Regel .et-beispiel fehlt');
		assert.notEqual(r.decl['text-overflow'], 'ellipsis', 'Beispielwert wird mit „…“ abgeschnitten');
	});
});

describe('#3283 B6: Einfach-Symbol als E-Mail-Beispiel lesbar (AC-8)', () => {
	test('reines Symbol trägt das Kennzeichen data-art="symbol", Text mit Buchstaben oder Ziffern nicht', async () => {
		const h = await karte(trip3283(), { context: 'route' });
		const wolke = eins(zelle(h, 'cloud_total', 'email').innen, 'data-slot="et-beispiel"');
		assert.equal(text(wolke.innen), '⛅');
		assert.equal(attr(wolke.auf, 'data-art'), 'symbol', 'Symbol ohne Kennzeichen');
		const temp = eins(zelle(h, 'temperature', 'email').innen, 'data-slot="et-beispiel"');
		assert.equal(text(temp.innen), 'Temp 14.4');
		assert.equal(attr(temp.auf, 'data-art'), null, 'Text mit Ziffern ist kein Symbol');
		const tg = eins(zelle(h, 'cloud_total', 'telegram').innen, 'data-slot="et-beispiel"');
		assert.equal(attr(tg.auf, 'data-art'), null, '„CT ⛅-🌥️@15“ enthält Buchstaben');
	});
	test('Symbol in --g-text-sm und --g-ink, Kontrast AA gegen die Karte (doc-compliance-test)', () => {
		// doc-compliance-test: Größe und Farbe stehen nur im <style>; berechnet im Staging-Bildabgleich.
		const r = regeln(TABELLE_DATEI).find((x) => x.selektor.includes('et-beispiel') && x.selektor.includes('symbol'));
		assert.ok(r, 'keine Regel für das Symbol-Beispiel');
		assert.equal(aufloesen(r.decl['font-size'] ?? ''), aufloesen('var(--g-text-sm)'));
		assert.equal(r.decl.color, 'var(--g-ink)');
		const lum = (hex: string) => {
			const [rr, gg, bb] = [1, 3, 5]
				.map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
				.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
			return 0.2126 * rr + 0.7152 * gg + 0.0722 * bb;
		};
		const [hell, dunkel] = [lum(aufloesen('var(--g-card)')), lum(aufloesen('var(--g-ink)'))].sort((a, b) => b - a);
		assert.ok((hell + 0.05) / (dunkel + 0.05) >= 4.5, 'Kontrast unter WCAG AA');
	});
});

describe('#3283 B7: Legende als Raster, Kürzel mono ohne Fettdruck (AC-9)', () => {
	test('dl: Grid auto 1fr, Abstand 4px/14px; dt: Mono, normales Gewicht, keine Mindestbreite (doc-compliance-test)', () => {
		// doc-compliance-test: Raster und Schriftgewicht stehen nur im <style>; berechnet im Staging-Bildabgleich.
		const alle = regeln(DATEI);
		const dl = alle.find((x) => x.selektor === '.wsw-legende');
		assert.ok(dl, 'Regel .wsw-legende fehlt');
		assert.equal(dl.decl.display, 'grid', 'Legende ist kein Grid');
		assert.equal(dl.decl['grid-template-columns'], 'auto 1fr');
		assert.equal(aufloesen(dl.decl.gap ?? ''), '4px 14px');
		const dt = alle.find((x) => x.selektor === '.wsw-legende dt');
		assert.ok(dt, 'Regel .wsw-legende dt fehlt');
		assert.equal(dt.decl['font-family'], 'var(--g-font-mono)');
		assert.ok(!dt.decl['font-weight'] || ['400', 'normal'].includes(dt.decl['font-weight']), `dt fett: ${dt.decl['font-weight']}`);
		assert.equal(dt.decl['min-width'], undefined, 'dt mit Mindestbreite');
		// Eine Hülle je Eintrag darf das Raster nicht brechen.
		const huelle = alle.find((x) => x.selektor === '.wsw-legende-eintrag');
		if (huelle) assert.equal(huelle.decl.display, 'contents', 'Hülle je Eintrag bricht das Raster');
	});
});

// ── #3020 R1: Namen des Ausblicks, Telegram-Grenze, Bericht-Flags an der Karte ──────────────────────────────
describe('#3020 G02: der 3-Tages-Ausblick heißt überall gleich', () => {
	const ALTE_NAMEN = [
		'Mehrtages-Trend', '3-Tages-Vorschau', 'Nächste Etappen', 'Trend-Block', '3–7-Tage-Ausblick',
		'Multi-day trend', '3-day preview', 'Next stages', 'Trend block', '3–7-day outlook'
	];
	test('Ausblick trägt überall den einen Namen, kein alter Name (DE und EN, Trip und Orte)', async () => {
		for (const [sprache, name] of [['de', '3-Tages-Ausblick'], ['en', '3-day outlook']] as const) {
			for (const [context, a] of [['route', trip()], ['vergleich', orte(3)]] as const) {
				locale.set(sprache);
				try {
					const h = await karte(a, { context });
					const kopf = kopfStellen(h).find((x) => attr(x.auf, 'data-stelle') === 'outlook')!;
					assert.ok(text(kopf.innen).startsWith(`${name} `), `${sprache}/${context}: Spaltenkopf ${text(kopf.innen)}`);
					const block = elemente(h, 'data-slot="einstellungszeile"').filter((x) => x.innen.includes('was-steht-wo-ausblick-morning'));
					assert.equal(block.length, 1);
					assert.ok(text(block[0].innen).startsWith(`${name} `), `${sprache}/${context}: Block ${text(block[0].innen)}`);
					// Ganzes Markup: Text, title und aria-label.
					for (const alt of ALTE_NAMEN) assert.ok(!h.toLowerCase().includes(alt.toLowerCase()), `${sprache}/${context}: alter Name „${alt}“`);
				} finally {
					locale.set('de');
				}
			}
		}
	});
});

describe('#3020 G49/G50: die Telegram-Spalte behauptet nur, was Telegram tut', () => {
	// Folge ungleich Katalog- und Alphabetfolge.
	const NEUN = ['uv_index', 'wind', 'thunder', 'gust', 'precipitation', 'cloud_total', 'humidity', 'dewpoint', 'visibility'];
	const GRENZE = /zu breit|too wide|max\.? ?7|limit|[−-]2\b|nur Tageswert|daily value only|passt nicht mehr|no longer fits/i;
	const orteAntwort = (ids: string[]): J => {
		const a = orte(3, { sms_example: null });
		a.rows = ids.map((id, i) => ({
			metric_id: id, name: `Name ${id}`, position: i, parent: null,
			cells: { email: z('on'), telegram: z('on', { format: 'raw', example: `Wert ${i}` }), sms: z('on'), hourly: z('on'), outlook: z('on') }
		}));
		return a;
	};
	const tripAntwort = (ids: string[], marken: (string | null)[]): J => {
		const a = trip({ sms_example: null });
		a.rows = ids.map((id, i) => ({
			metric_id: id, name: `Name ${id}`, position: i, parent: null,
			cells: { email: z('on'), telegram: z('on', { mark: marken[i] }), sms: z('on'), outlook: z('on') }
		}));
		return a;
	};
	const zeilen = (h: string) => elemente(h, 'data-slot="et-zeile"').map((x) => attr(x.auf, 'data-metrik'));
	const marken = (h: string, metrik: string, stelle: string) => elemente(zelle(h, metrik, stelle).innen, 'data-slot="et-marke"').map((x) => text(x.innen));
	async function inSprache(lang: 'de' | 'en', a: J, context: string): Promise<string> {
		locale.set(lang);
		try {
			return await karte(a, { context });
		} finally {
			locale.set('de');
		}
	}

	for (const lang of ['de', 'en'] as const) {
		const orteOhneMarke = async (ids: string[]) => {
			const h = await inSprache(lang, orteAntwort(ids), 'vergleich');
			assert.deepEqual(zeilen(h), ids, 'jede Zeile der Antwort, in ihrer Folge');
			for (const id of ids) {
				assert.equal(attr(zelle(h, id, 'telegram').auf, 'data-zustand'), 'on');
				assert.match(kaestchen(h, id, 'telegram'), /\schecked/);
				assert.doesNotMatch(kaestchen(h, id, 'telegram'), /\sdisabled/);
				assert.deepEqual(marken(h, id, 'telegram'), [], `${id}: Marke in der Telegram-Spalte`);
			}
			assert.doesNotMatch(text(eins(h, 'data-testid="was-steht-wo-tabelle"').innen), GRENZE);
		};
		test(`Orte, ${lang}: neun Metriken stehen alle in der Telegram-Spalte, ohne Marke und ohne Grenz-Text`, () => orteOhneMarke(NEUN));
		test(`Orte, ${lang}: fünf Metriken, keine Marke in der Telegram-Spalte`, () => orteOhneMarke(NEUN.slice(0, 5)));
	}

	test('Orte: die E-Mail-Spalte trägt nie eine Telegram-Marke', async () => {
		const a = orteAntwort(NEUN);
		for (const r of a.rows.slice(7)) r.cells.telegram.mark = 'nur_tageswert';
		const h = await inSprache('de', a, 'vergleich');
		assert.deepEqual(marken(h, NEUN[8], 'telegram'), ['nur Tageswert'], 'Messaufbau: die Marke steht an der Telegram-Zelle');
		for (const id of NEUN) for (const s of ['email', 'sms', 'hourly', 'outlook']) assert.deepEqual(marken(h, id, s), [], `${id}/${s}`);
	});

	for (const lang of ['de', 'en'] as const) {
		test(`Trip, ${lang}: neun Metriken, „nur Tageswert“ genau an Platz 8 und 9, keine Zeile fehlt`, async () => {
			const h = await inSprache(lang, tripAntwort(NEUN, NEUN.map((_, i) => (i > 6 ? 'nur_tageswert' : null))), 'route');
			assert.deepEqual(zeilen(h), NEUN);
			const marke = { de: 'nur Tageswert', en: 'daily value only' }[lang];
			assert.deepEqual(NEUN.map((id) => marken(h, id, 'telegram')), NEUN.map((_, i) => (i > 6 ? [marke] : [])));
			for (const id of NEUN) {
				assert.match(kaestchen(h, id, 'telegram'), /\schecked/);
				assert.doesNotMatch(kaestchen(h, id, 'telegram'), /\sdisabled/);
				for (const s of ['email', 'sms', 'outlook']) assert.deepEqual(marken(h, id, s), [], `${id}/${s}`);
			}
		});
	}
});

// #3047 N3 (Katalog 35 bis 37): Bericht-Flags. Altbestand: Temperatur nur morgens, Wind aus, aber morgens an, Böen
// nur abends, Niederschlag beide Flags, Gewitter ohne Flags. Soll aus Python (resolve_channel_lists je Briefing-Typ).
describe('#3020 G44: nur morgens / nur abends (Altbestand)', () => {
	const BESTAND = [
		{ metric_id: 'temperature', enabled: true, order: 0, bucket: 'primary', evening_enabled: false },
		{ metric_id: 'wind', enabled: false, order: 0, morning_enabled: true },
		{ metric_id: 'gust', enabled: true, order: 1, bucket: 'primary', morning_enabled: false },
		{ metric_id: 'precipitation', enabled: true, order: 2, bucket: 'primary', morning_enabled: true, evening_enabled: true },
		{ metric_id: 'thunder', enabled: true, order: 3, bucket: 'primary' }
	];
	const EIGENE = BESTAND.map((m) => m.metric_id);
	async function modelle() {
		const wt = path.join(FRONTEND, 'src/lib/components/shared/wetter-tab');
		const lade = (datei: string): Promise<J> => import(pathToFileURL(path.join(wt, datei)).href);
		const [O, D, A, Z, S, G] = await Promise.all(['__tests__/placementsOrakel.ts', '__tests__/wetterTabDaten.ts', 'ampelModell.ts', 'wetterZustand.ts', 'wetterTabSpeicherung.ts', '__tests__/ausgabeOrakel.ts'].map(lade));
		const vorlagen = A.vorlagenAusTemplates(D.live().templates);
		const eig = A.eigenschaftenAusKatalog(D.live().metrics);
		const abo = { id: 'n3', display_config: { metrics: BESTAND } };
		const stand = (x: J) => Z.standAusAbo('route', x, D.aufgeloestVon(x), {}, { eig });
		const speichere = (x: J, s: J) => ({ id: 'n3', display_config: G.ebene1(x.display_config, S.tripNutzlast({ client: null, stand: () => s, vorlagen: () => vorlagen, abo: () => x }).weatherConfig) });
		const orakel = (x: J) => O.placementsOrakel([{ id: 'n3', nutzer: 'n3-a', kind: 'route', abo: x }])[0];
		const eigene = (liste: [string, unknown][]) => liste.map(([m]) => m).filter((m) => EIGENE.includes(m)).sort();
		return { abo, stand, speichere, orakel, eigene, Z };
	}
	const kennzeichen = (h: string, metrik: string) => text(eins(h, `data-metrik="${metrik}"`).innen).match(/nur morgens|nur abends|morning only|evening only/g) ?? [];

	test('n3_semantik_wie_mail', async () => {
		const m = await modelle();
		const o = m.orakel(m.abo);
		const berichte = [...new Set([...m.eigene(o.listen.morning.email), ...m.eigene(o.listen.evening.email)])].sort();
		assert.deepEqual(berichte, [...EIGENE].sort(), 'Messaufbau: jede Größe steht in mindestens einem Briefing');
		// (a) gewählt ist, was mindestens ein Briefing führt
		assert.deepEqual(m.stand(m.abo).auswahl.filter((x: string) => EIGENE.includes(x)).sort(), berichte);
		// (b) „−“ nimmt die Größe aus beiden Briefings
		const ohne = m.orakel(m.speichere(m.abo, m.Z.ohneMetrik(m.stand(m.abo), 'precipitation')));
		for (const rt of ['morning', 'evening']) assert.ok(!m.eigene(ohne.listen[rt].email).includes('precipitation'), `nach „−“ steht die Größe noch im Briefing ${rt}`);
	});
	test('n3_editor_kennzeichnet_je_zeile', async () => {
		const m = await modelle();
		const a = m.orakel(m.abo).antwort;
		for (const [lang, morgens, abends] of [['de', 'nur morgens', 'nur abends'], ['en', 'morning only', 'evening only']] as const) {
			locale.set(lang);
			try {
				const h = await karte(a, { context: 'route' });
				assert.deepEqual(EIGENE.map((id) => kennzeichen(h, id)), [[morgens], [morgens], [abends], [], []], lang);
			} finally {
				locale.set('de');
			}
		}
	});
	test('n3_kennzeichnung_folgt_dem_editorstand', async () => {
		const m = await modelle();
		const vorher = await karte(m.orakel(m.abo).antwort, { context: 'route' });
		assert.deepEqual(kennzeichen(vorher, 'temperature'), ['nur morgens']);
		// Temperatur abgewählt: abends ohnehin aus, morgens folgt jetzt enabled:false — in keinem Briefing, keine Zeile.
		const danach = m.orakel(m.speichere(m.abo, m.Z.ohneMetrik(m.stand(m.abo), 'temperature'))).antwort;
		assert.equal(elemente(await karte(danach, { context: 'route' }), 'data-metrik="temperature"').length, 0);
	});
});
