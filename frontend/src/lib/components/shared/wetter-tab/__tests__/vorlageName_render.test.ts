// Issue #2981 (Epic #2913, ADR-0104), Fix-Loop Adversary M4–M11: die Verdrahtung des
// Helfers vorlageAnzeigename in den Komponenten wird dort geprueft, wo sie WIRKT — im
// Server-Render (svelte/server) von VorlageKarte und WeatherV2PresetBar, mit dem echten
// locale-Store und dem echten Katalog. Kein Mock.
//
// Zweige, die erst nach einem Klick erscheinen (offenes Menue, Rueckfrage), rendert der
// Test ueber startzustandHook.mjs: die ECHTE Datei mit anderem $state-Startwert
// (pickerOffen/wahl). Das Markup bleibt das der Produktivdatei. Nicht im SSR pruefbar ist
// nur der Wechsel der Sprache im laufenden Browser ohne Neuladen (AC-6): nur auf Staging.
// Spec: docs/specs/modules/fix_2981_vorlage_name_en.md (AC-1 bis AC-5, AC-7)
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/vorlageName_render.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale } from '../../../../i18n/index.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> wetter-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
const COMPONENTS = path.join(FRONTEND, 'src', 'lib', 'components');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(
	pathToFileURL(path.join(COMPONENTS, 'organisms', '__tests__', 'startzustandHook.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
const { render } = await import('svelte/server');

const KARTE = pathToFileURL(path.join(COMPONENTS, 'organisms', 'wetter-tab', 'VorlageKarte.svelte')).href;
const LEISTE = pathToFileURL(path.join(COMPONENTS, 'shared', 'weather-metrics-tab', 'WeatherV2PresetBar.svelte')).href;

async function lade(url: string, start: [string, string][] = []): Promise<any> {
	const abfrage = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(url + abfrage)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) =>
	h
		.replace(/<[^>]*>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
const noop = () => {};

/** Element mit dieser Testid samt Inhalt (bis zum passenden Schluss-Tag gleichen Namens). */
function elementMitTestid(h: string, testid: string): string {
	const m = h.match(new RegExp(`<([a-z]+)\\b[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m && m.index !== undefined, `Element ${testid} fehlt`);
	const name = m[1];
	const re = new RegExp(`<${name}\\b|</${name}>`, 'g');
	re.lastIndex = m.index + m[0].length;
	let tiefe = 1;
	for (let x = re.exec(h); x; x = re.exec(h)) {
		tiefe += x[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return h.slice(m.index, x.index + x[0].length);
	}
	assert.fail(`Element ${testid} nicht geschlossen`);
}
/** Oeffnender Tag des Elements mit dieser Testid. */
function tagMitTestid(h: string, testid: string): string {
	const m = h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m, `Element ${testid} fehlt`);
	return m[0];
}

afterEach(() => locale.set('de'));

// Server-Labels wie /api/templates (deutsch, src/app/metric_catalog.py).
const LISTE = [
	{ id: 'wandern', label: 'Wandern', anzahl: 6, stichworte: [] },
	{ id: 'skitouren', label: 'Skitouren', anzahl: 7, stichworte: [] },
	{ id: 'gletscher-neu', label: 'Gletschertour', anzahl: 5, stichworte: [] }
];
const EIGENE = [{ id: 'eigen-7f3a', name: 'Mein Wochenende', ampel: {} }];
const props = (abweichungen: number) => ({
	context: 'route',
	vorlageId: 'wandern',
	liste: LISTE,
	eigene: EIGENE,
	abweichungen,
	metrikName: (id: string) => id,
	aboAmpel: {},
	onUebernehmen: noop,
	onEigene: noop,
	onZuruecksetzen: noop,
	onGespeichert: noop
});
const MENUE_OFFEN: [string, string] = ['let pickerOffen = $state(false);', 'let pickerOffen = $state(true);'];
const WAHL = 'let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(null);';
const mitWahl = (w: string): [string, string] => [WAHL, `let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(${w});`];

describe('VorlageKarte: Kopfzeile (AC-1, AC-3)', () => {
	test('EN: Kopfzeile zeigt „Hiking“, nicht „Wandern“', async () => {
		locale.set('en');
		const picker = text(elementMitTestid(html(await lade(KARTE), props(0)), 'wetter-vorlage-picker'));
		assert.match(picker, /Hiking/);
		assert.doesNotMatch(picker, /Wandern/);
	});
	test('DE: Kopfzeile zeigt „Wandern“', async () => {
		locale.set('de');
		const picker = text(elementMitTestid(html(await lade(KARTE), props(0)), 'wetter-vorlage-picker'));
		assert.match(picker, /Wandern/);
		assert.doesNotMatch(picker, /Hiking/);
	});
});

describe('VorlageKarte: Zurücksetzen-Knopf (AC-2, AC-3)', () => {
	test('EN: „Reset to “Hiking”“', async () => {
		locale.set('en');
		const knopf = text(elementMitTestid(html(await lade(KARTE), props(2)), 'wetter-vorlage-zuruecksetzen'));
		assert.equal(knopf, 'Reset to “Hiking”');
	});
	test('DE: „Auf „Wandern“ zurücksetzen“', async () => {
		locale.set('de');
		const knopf = text(elementMitTestid(html(await lade(KARTE), props(2)), 'wetter-vorlage-zuruecksetzen'));
		assert.equal(knopf, 'Auf „Wandern“ zurücksetzen');
	});
});

describe('VorlageKarte: Auswahlliste und eigene Vorlage (AC-2, AC-4, AC-5)', () => {
	test('EN: Optionen englisch, unbekannte ID mit Server-Label, eigene Vorlage unverändert', async () => {
		locale.set('en');
		const h = html(await lade(KARTE, [MENUE_OFFEN]), props(0));
		const opt = (id: string) => text(elementMitTestid(h, `wetter-vorlage-option-${id}`));
		assert.match(opt('wandern'), /^Hiking\b/);
		assert.match(opt('skitouren'), /^Ski touring\b/);
		assert.doesNotMatch(opt('wandern'), /Wandern/);
		assert.match(opt('gletscher-neu'), /^Gletschertour\b/);
		assert.equal(text(elementMitTestid(h, 'wetter-vorlage-eigene-eigen-7f3a')), 'Mein Wochenende');
	});
	test('DE: Optionen deutsch, eigene Vorlage unverändert', async () => {
		locale.set('de');
		const h = html(await lade(KARTE, [MENUE_OFFEN]), props(0));
		assert.match(text(elementMitTestid(h, 'wetter-vorlage-option-wandern')), /^Wandern\b/);
		assert.equal(text(elementMitTestid(h, 'wetter-vorlage-eigene-eigen-7f3a')), 'Mein Wochenende');
	});
});

describe('VorlageKarte: Rückfrage {neu} und Verlust-Text (AC-2, AC-4)', () => {
	test('EN: Wechsel auf Systemvorlage nennt „Ski touring“, Verlust-Text „Hiking“', async () => {
		locale.set('en');
		const V = await lade(KARTE, [MENUE_OFFEN, mitWahl("{ id: 'skitouren', name: 'Skitouren', eigen: false }")]);
		const frage = text(elementMitTestid(html(V, props(2)), 'wetter-vorlage-wechsel-dialog'));
		assert.match(frage, /Use ‘Ski touring’\?/);
		assert.match(frage, /from ‘Hiking’ will be lost/);
		assert.doesNotMatch(frage, /Skitouren|Wandern/);
	});
	test('EN: Wechsel auf eigene Vorlage nennt den Nutzernamen unverändert', async () => {
		locale.set('en');
		const V = await lade(KARTE, [MENUE_OFFEN, mitWahl("{ id: 'eigen-7f3a', name: 'Mein Wochenende', eigen: true }")]);
		const frage = text(elementMitTestid(html(V, props(0)), 'wetter-vorlage-wechsel-dialog'));
		assert.match(frage, /Use ‘Mein Wochenende’\?/);
	});
});

describe('WeatherV2PresetBar: Chip-Text und Tooltip (AC-7)', () => {
	const barProps = {
		selectedTemplate: 'wandern',
		dirty: false,
		templates: [
			{ id: 'wandern', label: 'Wandern', metrics: [] },
			{ id: 'gletscher-neu', label: 'Gletschertour', metrics: [] }
		],
		userPresets: [],
		onSelectPreset: noop,
		onOpenSaveDialog: noop
	};
	test('EN: Chip und title „Hiking“; unbekannte ID mit Server-Label', async () => {
		locale.set('en');
		const h = html(await lade(LEISTE), barProps);
		assert.equal(text(elementMitTestid(h, 'weather-preset-pill-wandern')), 'Hiking');
		assert.match(tagMitTestid(h, 'weather-preset-pill-wandern'), /\stitle="Hiking"/);
		assert.equal(text(elementMitTestid(h, 'weather-preset-pill-gletscher-neu')), 'Gletschertour');
	});
	test('DE: Chip und title „Wandern“', async () => {
		locale.set('de');
		const h = html(await lade(LEISTE), barProps);
		assert.equal(text(elementMitTestid(h, 'weather-preset-pill-wandern')), 'Wandern');
		assert.match(tagMitTestid(h, 'weather-preset-pill-wandern'), /\stitle="Wandern"/);
	});
});
