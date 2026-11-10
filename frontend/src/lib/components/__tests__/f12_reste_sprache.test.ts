// Issue #2661 (i18n F12, Epic #2644) — AC-1: die letzten Allowlist-Dateien sprechen
// die Nutzersprache. Echter SSR-Render (svelte/server) von BrandIcon, BrandWordmark,
// AppFooter, LocationForm und WeatherConfigDialog:
//   * de: normalisiertes HTML (Kommentare raus, Leerraum = ein Leerzeichen) ist
//     byte-gleich zum Stand VOR der Umstellung (SHA-256 unten, gemessen auf e574fd9ed),
//   * en: die englischen Anker-Texte stehen im Render, kein deutsches Signalwort.
// Die Systemhinweise in +layout.svelte erscheinen nur zur Laufzeit im Browser; ihre
// Texte sichert der Anker-Abgleich (de wortgleich zum Bestand, en fest verankert).
// Spec: docs/specs/modules/i18n_f12_frontend_abschluss_2661.md
//
//   cd frontend && npm test -- src/lib/components/__tests__/f12_reste_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { F12_ANKER } from './f12KatalogAnker.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const LIB = path.resolve(HERE, '../..');
const base = pathToFileURL(FRONTEND + '/').href;
const hook = (p: string) => register(pathToFileURL(p).href, base);
hook(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs'));
hook(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
hook(path.join(LIB, 'components/trip-new/__tests__/ssrRunesHook.mjs'));
hook(path.join(HERE, 'dialogRahmenHook.mjs'));

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(LIB, 'i18n/index.ts')).href);
const lade = async (rel: string) => (await import(pathToFileURL(path.join(LIB, rel)).href)).default;

afterEach(() => locale.set('de'));

const leer = () => {};
const norm = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '').replace(/\s+/g, ' ').trim();
const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const sichtbar = (h: string) => ent(h.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
const attribute = (h: string) => [...h.matchAll(/\s(?:aria-label|placeholder|title)="([^"]*)"/g)].map((m) => ent(m[1]));
const sha = (s: string) => createHash('sha256').update(s).digest('hex').slice(0, 16);
const DEUTSCH = /[äöüÄÖÜß]|\b(Abbrechen|Speichern|Rechtliches|Impressum|Datenschutz|Breitengrad|Gruppe|Keine|Kein|Welche|Metriken|Name der|z\.B\.|gesendet|geplant)\b/;

async function renders(): Promise<Record<string, string>> {
	const [BrandIcon, BrandWordmark, AppFooter, LocationForm, WeatherConfigDialog, Zeile] = await Promise.all([
		lade('brand/BrandIcon.svelte'),
		lade('brand/BrandWordmark.svelte'),
		lade('components/shared/AppFooter.svelte'),
		lade('components/LocationForm.svelte'),
		lade('components/WeatherConfigDialog.svelte'),
		lade('components/molecules/BriefingTimelineRow.svelte')
	]);
	const r = (k: unknown, props: Record<string, unknown>) => norm(render(k as never, { props: props as never }).body);
	return {
		brandIcon: r(BrandIcon, {}),
		wordmarkLeft: r(BrandWordmark, { caption: null }),
		wordmarkNone: r(BrandWordmark, { icon: 'none', caption: null }),
		footer: r(AppFooter, {}),
		locationForm: r(LocationForm, { groups: [], onsave: leer, oncancel: leer }),
		weatherDialog: r(WeatherConfigDialog, { open: true, entityName: 'E2E-Ort', currentConfig: undefined, onsave: leer, onclose: leer }),
		// Fresh-Eyes-Befund #2661: Status-Suffix der Versandkarte im Cockpit.
		zeileGesendet: r(Zeile, { report: { when: '07:00', kind: 'X', channels: ['email'], status: 'sent' } }),
		zeileGeplant: r(Zeile, { report: { when: '18:00', kind: 'X', channels: ['email'], status: 'planned' } })
	};
}

/** de-Render VOR der Umstellung (normalisiertes HTML, SHA-256, 16 Hex). Nie neu schreiben. */
const GOLDEN_DE: Record<string, string> = {
	brandIcon: 'fea18731f8c3e391',
	wordmarkLeft: '1f7d593ed264942b', // #2896: Logo-Punkt --g-ink-4 → --g-ink-3
	wordmarkNone: 'a4629a8d8e332251', // #2896: Logo-Punkt --g-ink-4 → --g-ink-3
	footer: '9c85c44385fe29e2',
	locationForm: 'c04aa5edcee1d89c', // #2881 Lieferung B: Auswahl-Baustein (bits-ui Select) statt nativem <select>
	weatherDialog: 'e00ab9e6247728a3',
	zeileGesendet: '9e87c359f10cb71f',
	zeileGeplant: '73f413bec9e8047c'
};

describe('F12: Reste der Allowlist (AC-1)', () => {
	test('de: jeder Render ist byte-gleich zum Stand vor der Umstellung', async () => {
		locale.set('de');
		const h = await renders();
		assert.deepEqual(Object.fromEntries(Object.entries(h).map(([k, v]) => [k, sha(v)])), GOLDEN_DE);
	});

	test('en: englische Texte stehen im Render, kein deutsches Signalwort', async () => {
		locale.set('en');
		const h = await renders();
		const en = (k: string) => trFor('en', k);
		const erwartet: Record<string, string[]> = {
			brandIcon: [en('bausteine.marke.name')],
			footer: [en('bausteine.footer.rechtliches'), en('bausteine.footer.impressum'), en('bausteine.footer.datenschutz')],
			locationForm: ['Location name', 'Google Maps coordinates (DMS)', 'Latitude (lat)', 'Longitude (lon)', 'Elevation (m)', 'Activity profile', 'Group (optional)', 'No group', '— No profile —', 'Cancel', 'Save', 'e.g. hochfuegen'],
			weatherDialog: ['Weather metrics — E2E-Ort', 'Which metrics should the report show?', 'Cancel', 'Save'],
			zeileGesendet: [`X${en('bausteine.timeline.briefing')}`, en('bausteine.timeline.gesendet')],
			zeileGeplant: [en('listen.status.geplant')]
		};
		for (const [name, texte] of Object.entries(erwartet)) {
			const alles = `${sichtbar(h[name])} | ${attribute(h[name]).join(' | ')}`;
			for (const t of texte) assert.ok(alles.includes(t), `${name}: fehlt „${t}" in ${alles}`);
		}
		for (const [name, html] of Object.entries(h)) {
			const alles = `${sichtbar(html)} | ${attribute(html).join(' | ')}`;
			assert.doesNotMatch(alles, DEUTSCH, `${name}: deutsch in en: ${alles}`);
		}
		assert.match(sichtbar(h.wordmarkLeft), /gregor\s*\.\s*zwanzig/);
	});

	test('Anker: Katalog liefert de wortgleich zum Bestand und en wie verankert', () => {
		for (const [k, de, en] of F12_ANKER) {
			assert.equal(trFor('de', k), de, k);
			assert.equal(trFor('en', k), en, k);
		}
		assert.equal(F12_ANKER.length, new Set(F12_ANKER.map(([k]) => k)).size);
	});
});
