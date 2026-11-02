// Issue #2654 (i18n F5, Epic #2644) — AC-1, AC-3, AC-4, AC-5: der geteilte
// Wertebereiche-/Wetter-Metriken-Reiter (Trip UND Ortsvergleich, EIN Baustein)
// spricht die Sprache des angemeldeten Nutzers. Echte SSR-Renders (svelte/server,
// Pruefstand f5Pruefstand.ts):
//   * AC-5: Deutsch ist byte-gleich (Leerraum normalisiert) zur Ausgabe VOR der
//     Umstellung (tests/golden/f5_wertebereiche/*.de.html, funktionen.de.txt),
//   * AC-1: Metrik-Namen in voller Form englisch aus dem Register (label_en),
//     Kurzform (col_label) und Kuerzel daneben unveraendert; alle Beschriftungen englisch,
//   * AC-4: beide Kontexte mit demselben Baustein englisch,
//   * AC-3: zwei Nutzer (en/de) durch den ECHTEN Layout-Loader (+layout.server.ts),
//     gespeicherte Nutzlast ueber den echten Speicherweg identisch (ersetzt ist nur
//     die Netzgrenze: fetch je Sitzungs-Cookie).
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en: eine
// Mutation $t/tr -> trFor('de', …) macht ihn rot. Englische und deutsche Texte sind
// als feste Literale verankert (f5KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	FRONTEND,
	WMT,
	SHARED,
	GOLDEN_DIR,
	SMS_SYMBOLE,
	REGISTER_NAMEN,
	BUCKETS_GOLDEN,
	VERGLEICH_KATALOG,
	locale,
	trFor,
	loader,
	katalogMitRegister,
	resolveTripMetricsOverviewState,
	routeRendern,
	vergleichRendern,
	bausteineRendern,
	htmlFaelle,
	funktionsTabelle,
	schreibeGolden,
	tripFuer
} from './f5Pruefstand.ts';
import { F5_ANKER } from './f5KatalogAnker.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.server.ts')).href)).load;
const { api } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/api.ts')).href);
const { baueWetterMetrikenSpeicherung } = await import(pathToFileURL(path.join(SHARED, 'tripSpeicherung.ts')).href);
const { buildGlobalMetricsForSave } = await import(pathToFileURL(path.join(WMT, 'weatherMetricsSavePayload.ts')).href);
const { toggleGlobalMetric } = await import(pathToFileURL(path.join(WMT, 'channelMetricLayouts.ts')).href);

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen. Sonst byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 4000)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);
const attr = (html: string, name: string) => [...html.matchAll(new RegExp(`\\s${name}="([^"]*)"`, 'g'))].map((m) => m[1]);

/** Erst de rendern, dann OHNE Neuladen auf en schalten. */
function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

/** Entfernt ein Element (samt Inhalt) mit `data-testid="<id>"` — fuer Bloecke ANDERER Pakete. */
function ohneBlock(html: string, testid: string): string {
	for (;;) {
		const i = html.indexOf(`data-testid="${testid}"`);
		if (i < 0) return html;
		const start = html.lastIndexOf('<', i);
		const tag = /^<([a-zA-Z0-9-]+)/.exec(html.slice(start))![1];
		const re = new RegExp(`<${tag}[\\s>]|</${tag}>`, 'g');
		re.lastIndex = start;
		let tiefe = 0;
		let ende = html.length;
		for (let m = re.exec(html); m; m = re.exec(html)) {
			tiefe += m[0].startsWith('</') ? -1 : 1;
			if (tiefe === 0) {
				ende = m.index + m[0].length;
				break;
			}
		}
		html = html.slice(0, start) + html.slice(ende);
	}
}

/** Nur die Flaechen DIESES Pakets: Ausblick/Stundenverlauf (OutlookLayoutControls,
 *  CompareHourlyLayoutControls) und Mail-Inhalt (MailInhaltCard) gehoeren F8 bzw. dem
 *  Ortsvergleich-Paket; Gefahren-Namen der Warnungs-Legende kommen aus /api/sms-symbols. */
function paketText(html: string): string {
	let h = html;
	for (const id of ['weather-metrics-ausblick', 'weather-metrics-stundenverlauf', 'report-mail-content']) h = ohneBlock(h, id);
	let text = sichtbar(h);
	for (const hz of SMS_SYMBOLE.hazards as { label: string }[]) text = text.split(hz.label).join(' ');
	return text;
}

/** Deutsche Festteile (>= 4 Buchstaben, als ganzes Wort) der Paket-Schluessel im englischen Text. */
function deutscheReste(text: string): string[] {
	const reste: string[] = [];
	for (const [k, de, en] of F5_ANKER) {
		if (de === en) continue;
		const enTeile = new Set(en.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 4 || enTeile.has(teil)) continue;
			const wort = new RegExp(`(?<![A-Za-zÄÖÜäöüß])${teil.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![A-Za-zÄÖÜäöüß])`);
			if (wort.test(text)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}

describe('AC-5: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	const FAELLE = htmlFaelle();
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			const { de } = deDannEn(() => FAELLE[fall]());
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
			assert.equal(leerraum(de + '\n'), leerraum(golden));
		});
	}
	test('funktionen.de.txt: Funktionsergebnisse unveraendert (byte-gleich, ohne Normalisierung)', () => {
		const golden = readFileSync(path.join(GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		funktionsTabelle();
		locale.set('de');
		assert.equal(funktionsTabelle() + '\n', golden);
	});
	test('Messaufbau: Golden enthaelt die deutschen Texte aller Bausteine', () => {
		const alle = Object.keys(FAELLE).map((f) => sichtbar(readFileSync(path.join(GOLDEN_DIR, `${f}.de.html`), 'utf-8'))).join(' ');
		for (const s of [
			'01 — Profil', '02 — Grundauswahl', '04 — Schwellwerte', 'Böen (km/h)', 'Sensibel', 'Leicht Mittel Hoch', 'Lädt…', 'Schwellen nicht ladbar',
			'Aus in diesem Kanal', 'Tagesfenster', 'Geht über Mitternacht — endet am Folgetag.', 'Preset anwenden', 'Überschreiben',
			'Auswahl als Preset speichern', 'Metriken aktiv', 'Lade Metriken…', 'Wiederholen', 'Nur angewählte Metriken erscheinen in der Vergleichs-Mail.',
			'Amtliche Warnungen im Bericht', 'rote Gewitterwarnung', 'Gespeichert', 'Ungespeicherte Änderungen', 'Winter / Schnee', 'Eigene',
			'So heißen diese Größen in SMS und Telegram-Kurzform:', 'Temperatur Maximum'
		])
			assert.ok(alle.includes(s), s);
	});
});

describe('AC-1: Metrik-Namen aus dem Register, Kurzform und Kuerzel unveraendert, Reiter englisch', () => {
	test('Trip: erst de, dann ohne Neuladen en — „Temperature" neben „Temp" (Mail) und „T" (Kurzform)', () => {
		const katalog = katalogMitRegister();
		const { de, en } = deDannEn(() => bausteineRendern());
		const deT = sichtbar(de);
		const enT = sichtbar(en);
		hat(deT, '1 Temperatur °C Mail Temp Kurzform T');
		hat(enT, '1 Temperature °C Email Temp Compact T');
		hat(enT, '3 Wind gusts km/h Email Gust Compact G');
		// Kurzform/Kuerzel byte-gleich zur Eingabe
		assert.equal(katalog.temperature[0].col_label, 'Temp');
		assert.equal(katalog.temperature[0].sms_code, 'T');
		const ganz = deDannEn(() => routeRendern({ catalog: katalog, activeChannel: 'telegram', pendingPreset: 'wandern', showSavePresetDialog: true }));
		const enRoute = paketText(ganz.en);
		for (const s of ['Temperature', 'Feels-like temperature', 'Wind gusts', 'Snow line', 'Thunderstorm', 'Cloud cover', 'Humidity']) hat(enRoute, s);
		for (const s of ['Mail Temp', 'Mail Gust', 'Kurzform TF']) hat(paketText(ganz.de), s);
		for (const s of ['Email Temp', 'Email Gust', 'Compact TF']) hat(enRoute, s);
		assert.deepEqual(deutscheReste(enRoute), []);
	});

	test('Trip: alle Beschriftungen des Reiters englisch (Speichern-Leiste, Abschnitte, Schwellen, Dialoge)', () => {
		const { en } = deDannEn(() => routeRendern({ catalog: katalogMitRegister(), pendingPreset: 'wandern', showSavePresetDialog: true }));
		const t = paketText(en);
		for (const s of [
			'Unsaved changes', 'Discard', 'Save', '01 — Profile', 'Custom', 'Changed —', 'save as custom profile', '02 — Basic selection',
			'Which metrics go into the briefing?', '9 active', 'Temperature', 'Atmosphere', 'Winter / snow',
			'Activated metrics appear in section 3, where you set their order and display.', 'Order', '· 9 metrics',
			'left → right in the email table', 'Raw', 'Simple', 'Off', 'Off in this channel', 'Day window', 'From', 'To',
			'04 — Thresholds', 'Apply to SMS tokens, Telegram compact style and the email outlook/trend block', 'Gusts (km/h)',
			'Precipitation (mm)', 'Snow line (m)', 'Sensitive Standard Robust', 'Thunderstorm TH Light Moderate High',
			'Official warnings in the report', 'everything after it is an official warning', 'L = yellow', 'TH:H = red thunderstorm warning',
			'These are the codes for these values in SMS and Telegram compact style:', 'CUSTOM PRESET', 'Save selection as preset',
			'DESCRIPTION · OPTIONAL', 'WILL BE SAVED', 'Active metrics: 9 · raw: 5 · indicator: 0', 'Columns: 9 · detail: 0 · simple: 0',
			'TIME HORIZONS', 'Default for new trips', 'Cancel', 'Save preset', 'Apply preset',
			'You have unsaved changes. The preset overwrites the current selection.', 'Overwrite'
		])
			hat(t, s);
		assert.deepEqual(deutscheReste(t), []);
		// beschriftende Attribute (title, aria-label, placeholder) englisch — ohne die Bloecke
		// anderer Pakete (Ausblick, Mail-Inhalt) und ohne die Bedienhilfe von shared/dnd (eigener Baustein).
		const eigen = ['weather-metrics-ausblick', 'report-mail-content'].reduce(ohneBlock, en);
		const alle = [...attr(eigen, 'title'), ...attr(eigen, 'aria-label'), ...attr(eigen, 'placeholder')]
			.filter((a) => !a.startsWith('Zum Sortieren ziehen'))
			.join(' | ');
		for (const s of ['Short form in the email hourly table', 'Codes in SMS, Premium SMS and Telegram', 'Remove from briefing', 'Close', 'My hiking preset', 'Optimised for day trips', 'Metrics, order'])
			hat(alle, s);
		assert.deepEqual(deutscheReste(alle), []);
		const baustein = deDannEn(() => bausteineRendern()).en;
		hat(attr(baustein, 'title').join(' | '), 'Add back to briefing');
		const bt = sichtbar(baustein);
		for (const s of ['Day window', 'Crosses midnight — ends the next day.', 'Custom', 'Off in this channel', 'On', 'No metric active', 'Telegram'])
			hat(bt, s);
		assert.deepEqual(deutscheReste(bt), []);
	});

	test('Trip: Schwellen-Zustaende (Gewitter laedt / nicht ladbar), Gespeichert, Lade- und Fehlerzustand englisch', () => {
		const z = deDannEn(() => [
			routeRendern({ catalog: katalogMitRegister(), activeChannel: 'telegram', compareCatalogLoaded: false, saveSuccess: true }),
			routeRendern({ catalog: katalogMitRegister(), activeChannel: 'sms', compareCatalogError: 'HTTP 503' }),
			routeRendern({ catalogLoaded: false }),
			routeRendern({ catalogLoaded: false, loadError: 'HTTP 500' })
		].map(paketText));
		hat(z.de[0], 'Lädt…'); // „Gewitter" entfernt paketText (Gefahren-Name aus /api/sms-symbols)
		hat(z.en[0], 'Thunderstorm Loading…');
		hat(z.en[0], 'Saved');
		hat(z.en[1], 'Thunderstorm Thresholds could not be loaded');
		assert.equal(z.en[2], 'Loading metrics…');
		assert.equal(z.en[3], 'HTTP 500 Retry');
		assert.deepEqual(z.en.flatMap(deutscheReste), []);
	});

	test('fehlendes label_en im Register: der Reiter zeigt in en den deutschen Namen (AC-2 im Render)', () => {
		const { en } = deDannEn(() => paketText(routeRendern({ catalog: katalogMitRegister(['gust', 'humidity']) })));
		hat(en, 'Böen');
		hat(en, 'Luftfeuchtigkeit');
		hat(en, 'Gusts (km/h)');
		hatNicht(en, 'Wind gusts');
	});

	test('Trip-Uebersicht: resolveTripMetricsOverviewState liefert die Namen in der aktuellen Sprache', () => {
		const metriken = ['temperature', 'gust', 'snow_depth'].map((id) => ({ metric_id: id, enabled: true }));
		const r = deDannEn(() => resolveTripMetricsOverviewState(metriken, katalogMitRegister()));
		assert.deepEqual(r.de, { kind: 'selected', names: ['Temperatur', 'Böen', 'Schneehöhe'], unknownCount: 0 });
		assert.deepEqual(r.en, { kind: 'selected', names: ['Temperature', 'Wind gusts', 'Snow depth'], unknownCount: 0 });
		const ohne = deDannEn(() => resolveTripMetricsOverviewState(metriken, katalogMitRegister(['gust'])));
		assert.deepEqual(ohne.en, { kind: 'selected', names: ['Temperature', 'Böen', 'Snow depth'], unknownCount: 0 });
	});

	test('Gewitter-Stufen: Kennung und Wert bleiben, nur die Beschriftung wechselt', () => {
		const de = loader.thunderThresholdLevelsFromCatalog(VERGLEICH_KATALOG(), 'de');
		const en = loader.thunderThresholdLevelsFromCatalog(VERGLEICH_KATALOG(), 'en');
		assert.deepEqual(de, [{ id: 'leicht', label: 'Leicht', float: 1 }, { id: 'mittel', label: 'Mittel', float: 2 }, { id: 'hoch', label: 'Hoch', float: 3 }]);
		assert.deepEqual(en, [{ id: 'leicht', label: 'Light', float: 1 }, { id: 'mittel', label: 'Moderate', float: 2 }, { id: 'hoch', label: 'High', float: 3 }]);
		// unbekannte Stufe: Beschriftung wie bisher (grossgeschrieben), kein Schluessel
		assert.deepEqual(loader.deriveThunderThresholdLevels(['kein', 'extrem'], 'en'), [{ id: 'extrem', label: 'Extrem', float: 1 }]);
		assert.equal(loader.ordinalStufeLabel('kein', 'en'), 'None');
		assert.equal(loader.ordinalStufeLabel('mittel', 'de'), 'Mittel');
	});
});

describe('AC-4: Trip und Ortsvergleich englisch mit demselben Baustein', () => {
	test('vergleich: erst de, dann ohne Neuladen en — Namen aus dem Register, Auswertung je Kennung', () => {
		const { de, en } = deDannEn(() => vergleichRendern({ catalog: katalogMitRegister() }));
		const deT = paketText(de);
		const enT = paketText(en);
		hat(deT, 'Wetter-Metriken');
		hat(deT, 'Temperatur Maximum');
		for (const s of [
			'Weather metrics', 'Only selected metrics appear in the comparison email.',
			'Official warnings always come first regardless of this order and are therefore not part of the sortable list.',
			'Temperature Maximum', 'Temperature Minimum', 'Wind gusts', 'Sunshine hours', 'Total', 'Thunderstorm',
			'Order', 'Off in this channel', 'Day window', 'Official warnings in the report'
		])
			hat(enT, s);
		assert.deepEqual(deutscheReste(enT), []);
		// Reihenfolge-Zeilen und Legende: Auswertung als eigenes Element, je Kennung uebersetzt
		const reihe = sichtbar(en.slice(en.indexOf('data-testid="weather-metrics-vergleich-reihenfolge"')));
		hat(reihe, 'Sunshine hours Total Email Sun');
		hat(sichtbar(de.slice(de.indexOf('data-testid="weather-metrics-vergleich-reihenfolge"'))), 'Sonnenstunden Summe Mail Sun');
	});

	test('vergleich ohne label_en im Register (A2): deutscher Name, nie leer', () => {
		const { en } = deDannEn(() => paketText(vergleichRendern({ catalog: katalogMitRegister(['sunshine']) })));
		hat(en, 'Sonnenstunden');
		hat(en, 'Temperature Maximum');
		const leer = deDannEn(() => paketText(vergleichRendern({ catalog: {} })));
		hat(leer.en, 'Temperatur Maximum');
	});

	test('beide Kontexte: dieselben Bausteine, nur das kontextbedingte Nomen unterscheidet sich', () => {
		locale.set('en');
		const route = routeRendern({ catalog: katalogMitRegister(), showSavePresetDialog: true });
		const vergleich = vergleichRendern({ catalog: katalogMitRegister() });
		const r = paketText(route);
		const v = paketText(vergleich);
		for (const s of ['Order', 'Off in this channel', 'Day window', 'From', 'Official warnings in the report', 'everything after it is an official warning'])
			for (const t of [r, v]) hat(t, s);
		for (const id of ['wm2-reihenfolge', 'day-window-control', 'report-show-official-alerts', 'wm2-aus-gruppe'])
			for (const h of [route, vergleich]) assert.ok(h.includes(`data-testid="${id}"`), `${id} fehlt`);
		hat(v, 'comparison email');
		hatNicht(r, 'comparison email');
		hat(r, 'Default for new trips');
		hatNicht(v, 'trip');
		assert.equal(trFor('en', 'wertebereiche.reihenfolge.aus_im_kanal'), 'Off in this channel');
	});
});

describe('AC-3: zwei Nutzer, zwei Sprachen, eigene Auswahl, gleiche gespeicherte Nutzlast', () => {
	const KATALOG = katalogMitRegister();
	const BEREICH: Record<string, Record<string, unknown>> = {
		A: { '/api/auth/profile': { id: 'anna', mail_to: 'anna@example.org', language: 'en' } },
		B: { '/api/auth/profile': { id: 'bert', mail_to: 'bert@example.org', language: 'de' } }
	};
	const BUCKETS: Record<string, typeof BUCKETS_GOLDEN> = {
		A: { primary: ['temperature', 'gust', 'precipitation', 'humidity'], secondary: [], off: ['wind', 'snow_depth'] },
		B: { primary: ['temperature', 'gust', 'precipitation', 'humidity'], secondary: [], off: ['wind', 'snow_depth'] }
	};
	const puts: { sitzung: string; pfad: string; body: unknown }[] = [];

	/** Ersetzt nur die Netzgrenze: `fetch` antwortet je Sitzungs-Cookie mit eigenen Daten. */
	async function mitApi<T>(sitzung: string, lauf: () => Promise<T>): Promise<T> {
		const echt = globalThis.fetch;
		globalThis.fetch = (async (u: string, init?: { method?: string; body?: string; headers?: Record<string, string> }) => {
			const s = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? sitzung;
			const pfad = new URL(String(u), 'http://core').pathname;
			if ((init?.method ?? 'GET') === 'PUT') {
				puts.push({ sitzung: s, pfad, body: JSON.parse(init?.body ?? 'null') });
				return new Response(JSON.stringify({ id: pfad.split('/')[3] }), { status: 200 });
			}
			const daten = BEREICH[s]?.[pfad];
			return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
		}) as unknown as typeof fetch;
		try {
			return await lauf();
		} finally {
			globalThis.fetch = echt;
		}
	}
	const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });

	/** Echter Layout-Loader (Sprache) → Reiter in dieser Sprache → Umschalten → echter Speicherweg. */
	async function sitzungFuer(sitzung: 'A' | 'B') {
		const lang = await mitApi(sitzung, async () => {
			const layout = await layoutLoad({ locals: { userId: sitzung, lang: 'de' }, cookies: cookies(sitzung) } as never);
			return layout.lang as 'de' | 'en';
		});
		locale.set(lang);
		const text = paketText(routeRendern({ catalog: KATALOG, buckets: BUCKETS[sitzung] }, sitzung));
		const trip = tripFuer(sitzung, BUCKETS[sitzung]);
		// Nutzergeste: „Wind" wieder einschalten — dieselbe Funktion wie onToggleMetric().
		const { buckets } = toggleGlobalMetric(BUCKETS[sitzung], { email: null, telegram: null, sms: null }, 'wind', false);
		const metrics = buildGlobalMetricsForSave(trip.display_config, buckets, {}, {}, KATALOG, {}, ['wind', 'gust']);
		await mitApi(sitzung, () =>
			baueWetterMetrikenSpeicherung(api, trip.id, { metrics, telegram_kurzform: false }, () => ({ report_config: trip.report_config, official_alerts_enabled: true }))()
		);
		return { lang, text };
	}

	test('A englisch, B deutsch: jeder sieht seine Auswahl in seiner Sprache; PUT-Nutzlast ohne Anzeige-Texte und identisch', async () => {
		puts.length = 0;
		const a = await sitzungFuer('A');
		const b = await sitzungFuer('B');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		hat(a.text, '1 Temperature °C');
		hat(a.text, 'Wind gusts');
		hat(a.text, 'Order');
		hat(b.text, '1 Temperatur °C');
		hat(b.text, 'Reihenfolge');
		assert.deepEqual(deutscheReste(a.text), []);
		assert.equal(puts.length, 4, JSON.stringify(puts.map((p) => p.pfad)));
		const von = (s: string) => puts.filter((p) => p.sitzung === s);
		assert.deepEqual(von('A').map((p) => p.pfad), ['/api/trips/trip-A/weather-config', '/api/trips/trip-A']);
		assert.deepEqual(von('B').map((p) => p.pfad), ['/api/trips/trip-B/weather-config', '/api/trips/trip-B']);
		assert.deepEqual(von('A').map((p) => p.body), von('B').map((p) => p.body));
		const roh = JSON.stringify(puts.map((p) => p.body));
		for (const name of Object.values(REGISTER_NAMEN).map((r) => r.label_en).filter((n) => n.length > 3))
			assert.ok(!roh.includes(`"${name}"`), `Anzeige-Text in der Nutzlast: ${name}`);
		for (const name of ['Temperatur', 'Böen', 'Niederschlag']) assert.ok(!roh.includes(name), `Anzeige-Text in der Nutzlast: ${name}`);
		const wind = (von('A')[0].body as { metrics: { metric_id: string; enabled: boolean }[] }).metrics.find((m) => m.metric_id === 'wind');
		assert.equal(wind?.enabled, true, 'Geste nicht in der Nutzlast');
	});
});

describe('Anker: jeder F5-Katalogwert ist als festes de/en-Literal verankert', () => {
	/** Platzhalter des Literals (<name>) werden als Parameter `<name>` eingesetzt. */
	const params = (literal: string) =>
		Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F5_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}

	test('statischer Gegencheck: Anker-Tabelle == Schluessel von wertebereiche.json (de und en)', () => {
		const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
		for (const lang of ['de', 'en']) {
			const schluessel = Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, 'wertebereiche.json'), 'utf-8')));
			assert.deepEqual([...schluessel].sort(), F5_ANKER.map(([k]) => k).sort(), `${lang}: Schluessel ohne Anker oder Anker ohne Schluessel`);
		}
		assert.equal(new Set(F5_ANKER.map(([k]) => k)).size, F5_ANKER.length, 'doppelte Anker');
	});

	test('Plural exakt: Reihenfolge-Zaehler 1 = singular, sonst plural (en); de wortgleich zum Ist-Stand', () => {
		const n = (lang: 'de' | 'en', c: number) => trFor(lang, `wertebereiche.reihenfolge.anzahl.${c === 1 ? 'one' : 'other'}` as never, { count: c });
		assert.equal(n('en', 1), '· 1 metric');
		assert.equal(n('en', 2), '· 2 metrics');
		assert.equal(n('de', 1), '· 1 Metriken');
		assert.equal(n('de', 9), '· 9 Metriken');
		locale.set('en');
		hat(sichtbar(routeRendern({ catalog: katalogMitRegister(), buckets: { primary: ['temperature'], secondary: [], off: [] } })), 'Order · 1 metric ');
	});
});
