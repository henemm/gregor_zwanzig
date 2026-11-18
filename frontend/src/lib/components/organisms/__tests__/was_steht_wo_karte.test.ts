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
				email: z('on', { format: 'raw', example: '43 km/h' }), telegram: z('on', { format: 'raw', example: 'Wind 43 km/h' }), sms: z('on', { example: 'W 43 km/h' }),
				hourly: z('on', { format: 'raw', example: '28' }), outlook: z('on', { format: 'raw', example: '60 km/h' }) } },
			{ metric_id: 'sunshine', name: 'Sonne-O', position: 1, parent: null, cells: {
				email: z('on', { format: 'raw', example: '5.0 h' }), telegram: z('on', { format: 'raw' }), sms: z('on', { mark: 'passt_nicht_mehr' }),
				hourly: z('locked', { reason: 'kein_stundenwert' }), outlook: z('off', { format: 'raw' }) } },
			{ metric_id: 'uv_index', name: 'UV-O', position: 2, parent: null, cells: {
				email: z('on', { example: '7' }), telegram: z('on'), sms: z('locked', { reason: 'kein_kuerzel' }), hourly: z('on'), outlook: z('off') } }
		],
		sms_example: anzahl > 1
			? { text: 'Orte 18.11.: A W 43 km/h +2; B W 44 km/h +2; C W 45 km/h +2', length: 61, max_length: 153 }
			: { text: 'Ortsname-1 18.11.: W 43 km/h', length: 28, max_length: 153 },
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
	test('drei Orte: Grenze aus der Antwort (153), Fassung für mehrere Orte mit „+N“ je Ort', async () => {
		const o = await karte(orte(3), { context: 'vergleich' });
		const sms = text(eins(o, 'data-testid="was-steht-wo-sms"').innen);
		assert.match(sms, /^SMS-Beispiel: Orte 18\.11\.: A W 43 km\/h \+2; B .* · 61 von 153 Zeichen /);
		assert.match(sms, /Bei 3 Orten passt die letzte Metrik nicht mehr in die SMS\. Dafür steht „\+2“ je Ort\. Zieh nach oben/);
	});
	test('ein Ort: Fassung wie Trip, SMS beginnt mit dem Namen des Orts aus der Antwort', async () => {
		const o = await karte(orte(1), { context: 'vergleich' });
		const sms = text(eins(o, 'data-testid="was-steht-wo-sms"').innen);
		assert.match(sms, /^SMS-Beispiel: Ortsname-1 18\.11\.: /);
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
	test('drei Orte: Stundenverlauf „je Ort“, kein E-Mail-Format, keine Trip-Blöcke', async () => {
		const s = text(await karte(orte(3), { context: 'vergleich' }));
		assert.ok(s.includes('Stundenverlauf Stunden-Tabelle je Ort unter der Übersicht, nur in der E-Mail.'));
		assert.ok(s.includes('Tageswerte der nächsten drei Tage'));
		for (const w of ['E-Mail: Format', 'Etappen-Kennzahlen', 'Vortag-Vergleich', 'Nacht-Stundentabelle']) assert.ok(!s.includes(w), `${w} gehört nicht zu Orten`);
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
			for (const w of ['What goes where', 'One table for everything.', 'Email', 'Overview', 'Hourly view', 'email only', 'and Premium SMS', 'SMS example:', '61 of 153 characters',
				'Abbreviations explained', 'Switch whole blocks on and off', 'Settings per channel', 'Premium SMS'])
				assert.ok(s.includes(w), `fehlt: ${w}`);
			for (const w of ['Was steht wo', 'Übersicht', 'Stundenverlauf', 'Zeichen', 'Kürzel erklärt', 'Einstellungen je Kanal']) assert.ok(!s.includes(w), `deutsch: ${w}`);
			assert.ok(s.includes('Wind-O') && s.includes('W Wind km/h'), 'Namen und Kürzel aus der Antwort');
		} finally {
			locale.set('de');
		}
	});
});
