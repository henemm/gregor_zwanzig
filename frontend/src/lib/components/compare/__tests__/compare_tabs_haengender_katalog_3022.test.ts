// TDD RED — Issue #3022: Orts-Vergleich, Reiter Zustellung und Wetter erscheinen sofort, auch wenn der
// Metrik-Katalog haengt (Trip/Orte-Paritaet, ADR-0097).
// Spec: docs/specs/modules/fix_3022_zustellung_laedt.md — AC-1, AC-2, AC-3 (AC-4 siehe unten).
//
// Geprueft wird dort, wo es WIRKT: die ECHTE `compare/CompareTabs.svelte`, serverseitig gerendert
// (svelte/server), mit gespeichertem Orts-Vergleich (Preset) und einem echten SaveStatus-Controller.
// Kein Mock, keine String-Ersetzung im Produktcode: die Hydrations-Flags bleiben bei ihrem
// Quelltext-Startwert `false`.
//
// Hängender Katalog: `globalThis.fetch` ist fuer die Dauer des Tests ein Protokollant, dessen Antwort NIE
// aufloest (Katalog `/api/metrics`, `/api/compare/metrics`, Profil — alles bleibt offen). Im SSR-Render
// laufen ohnehin weder onMount noch $effect; der Render bildet damit genau den Zustand „Katalog noch nicht
// da“ ab, in dem die Hydrations-Effekte (`loadCompareSelectionEntries`) nie fertig werden. Heute (vor dem
// Fix) steht in beiden Reitern deshalb nur der Sperr-Kopf (`.hub-kopf-sperre`); nach dem Fix mounten die
// Reiter wie im Trip allein nach aktivem Reiter.
//
// AC-3 „kein PUT beim blossen Oeffnen“: der Protokollant zaehlt jeden Schreibaufruf (Methode ≠ GET), auch
// solche, die beim Aufbau der Speicherer synchron oder per Zeitgeber kurz danach ausgeloest wuerden
// (Wartezeit nach dem Render). Die Felder muessen den Werten des gespeicherten Presets entsprechen.
//
// AC-4 (Briefing-Zeit aendern → genau ein Speicheraufruf, uebrige Felder unveraendert): im SSR-Pruefstand
// laufen keine Ereignisse; eine Nutzergeste ist hier nicht ausloesbar. AC-4 ist durch den UNVERAENDERTEN
// Speicherer bewacht: shared/zustellung-tab/__tests__/zustellungSpeicherung.test.ts
// (`ac4_ac32_vergleich_nur_morgenzeit_0645`, `ac32_nur_morgenzeit_ein_put_fremdfelder_unveraendert` gegen den
// Go-Merge-Pruefstand). Dessen Basis ist `startStand` aus dem Preset — derselbe Stand, den AC-3 hier im
// gerenderten Reiter als Anzeige nachweist. #3022 aendert am Speicherweg nichts.
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/compare_tabs_haengender_katalog_3022.test.ts

import { test, describe, before, after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const KOMP = path.resolve(HERE, '../..');
const reg = (p: string) => register(pathToFileURL(p).href, pathToFileURL(FRONTEND + '/').href);
reg(path.join(FRONTEND, 'src/routes/account/__tests__/app-navigation-stub-hooks.mjs'));
reg(path.join(KOMP, 'shared/__tests__/svelteTsModulHook.mjs'));
reg(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));

const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { createSaveStatus } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/stores/saveStatusStore.svelte.ts')).href);
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = import('../../shared/hub-kopf/__tests__/htmlBaum.ts').Knoten;

const VERGLEICH_HUB = path.join(KOMP, 'compare', 'CompareTabs.svelte');

// ── Haengender Katalog: fetch-Protokollant, der nie aufloest ───────────────────────────
type Aufruf = { url: string; methode: string };
const aufrufe: Aufruf[] = [];
const echtesFetch = globalThis.fetch;
before(() => {
	globalThis.fetch = ((input: unknown, init?: { method?: string }) => {
		const url = typeof input === 'string' ? input : String((input as { url?: string })?.url ?? input);
		aufrufe.push({ url, methode: String(init?.method ?? 'GET').toUpperCase() });
		return new Promise(() => {}); // haengt fuer immer
	}) as typeof fetch;
});
after(() => {
	globalThis.fetch = echtesFetch;
});
afterEach(() => locale.set('de'));

// ── Gespeicherter Orts-Vergleich (Werte bewusst abseits der Standardwerte) ─────────────
const LOCS = [
	{ id: 'l1', name: 'Ort A', lat: 47.1, lon: 11.1 },
	{ id: 'l2', name: 'Ort B', lat: 47.2, lon: 11.2 }
];
const PRESET = {
	id: 'p3022',
	name: 'Vergleich 3022',
	location_ids: ['l1', 'l2'],
	display_config: {},
	morning_enabled: true,
	morning_time: '06:45',
	evening_enabled: true,
	evening_time: '19:30',
	send_email: true,
	send_telegram: true,
	send_sms: false,
	send_premium_sms: false,
	alert_quiet_from: '21:15',
	alert_quiet_to: '05:45',
	alert_cooldown_minutes: 90
};

const entity = (s: string) =>
	s.replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (k: Knoten) => entity(rohText(k));
const mitTestid = (b: Knoten, id: string) => alle(b, (n) => n.attrs['data-testid'] === id);
const mitAbschnitt = (b: Knoten, a: string) => alle(b, (n) => n.attrs['data-abschnitt'] === a);
const mitKlasse = (b: Knoten, k: string) => alle(b, (n) => String(n.attrs['class'] ?? '').split(/\s+/).includes(k));

async function hubReiter(tab: 'wetter' | 'zustellung'): Promise<{ panel: Knoten; html: string }> {
	const C = (await import(pathToFileURL(VERGLEICH_HUB).href)).default;
	const saveController = createSaveStatus();
	const html = render(C, { props: { initialTab: tab, preset: PRESET, locations: LOCS, saveController } }).body;
	const b = baum(html);
	const panel = mitTestid(b, `compare-detail-panel-${tab}`);
	assert.equal(panel.length, 1, `Messaufbau: Orte-Reiter ${tab} nicht aktiv gerendert`);
	return { panel: panel[0], html };
}

// ═══ AC-1: Reiter Zustellung zeigt alle Abschnitte trotz haengendem Katalog ══════════════
describe('#3022 AC-1: Reiter Zustellung bei haengendem Katalog', () => {
	test('AC-1: ZustellungTab ist gerendert (data-testid="zustellung-tab"), kein Sperr-Kopf', async () => {
		const { panel } = await hubReiter('zustellung');
		assert.equal(mitTestid(panel, 'zustellung-tab').length, 1, '#3022: Reiter Zustellung zeigt nur den Sperr-Kopf, ZustellungTab fehlt');
		assert.equal(mitKlasse(panel, 'hub-kopf-sperre').length, 0, '#3022: Sperr-Kopf steht noch im Reiter Zustellung');
	});

	test('AC-1: Kopf, Briefing-Zeiten, Laufzeit, Kanal-Tabelle und Stille Stunden sind sichtbar', async () => {
		const { panel } = await hubReiter('zustellung');
		assert.equal(mitAbschnitt(panel, 'abschnittskopf').length, 1, 'Kopf (abschnittskopf) nicht genau einmal');
		for (const a of ['briefing-zeiten', 'laufzeit', 'kanaele', 'stille-stunden']) {
			assert.equal(mitAbschnitt(panel, a).length, 1, `#3022: Abschnitt „${a}“ fehlt im Reiter Zustellung (Katalog haengt)`);
		}
		// Die Kanal-Karte steht; ihre Tabellenzeilen haengen am EIGENEN Profil-Abruf des Reiters (nicht am
		// Katalog, im Trip identisch) — solange der laeuft, zeigt die Karte ihren eigenen Ladehinweis.
		const kanaele = mitAbschnitt(panel, 'kanaele')[0];
		assert.ok(
			mitTestid(kanaele, 'zustellung-kanal-tabelle').length === 1 || alle(kanaele, (n) => n.attrs['role'] === 'status').length === 1,
			'#3022: Kanal-Karte zeigt weder Tabelle noch eigenen Ladehinweis'
		);
		assert.equal(mitTestid(panel, 'zustellung-morgen-karte').length, 1, '#3022: Karte Morgen-Briefing fehlt');
		assert.equal(mitTestid(panel, 'zustellung-abend-karte').length, 1, '#3022: Karte Abend-Briefing fehlt');
	});
});

// ═══ AC-2: Reiter Wetter zeigt Kopf und Ladehinweis ═════════════════════════════════════
describe('#3022 AC-2: Reiter Wetter bei haengendem Katalog', () => {
	test('AC-2: Abschnittskopf und „Lade Metriken …“ sichtbar, kein Sperr-Kopf', async () => {
		const { panel } = await hubReiter('wetter');
		assert.equal(mitKlasse(panel, 'hub-kopf-sperre').length, 0, '#3022: Sperr-Kopf steht noch im Reiter Wetter');
		assert.equal(mitAbschnitt(panel, 'abschnittskopf').length, 1, 'Kopf (abschnittskopf) nicht genau einmal');
		assert.ok(text(panel).includes('Lade Metriken …'), `#3022: Ladehinweis „Lade Metriken …“ fehlt im Reiter Wetter; Text: „${text(panel).slice(0, 200)}“`);
	});
});

// ═══ AC-3: blosses Oeffnen speichert nichts, Anzeige = gespeicherter Stand ══════════════
describe('#3022 AC-3: Reiter Zustellung nur oeffnen', () => {
	test('AC-3: angezeigte Werte entsprechen dem gespeicherten Orts-Vergleich', async () => {
		const { panel } = await hubReiter('zustellung');
		const morgen = mitTestid(panel, 'zustellung-morgen-zeit');
		const abend = mitTestid(panel, 'zustellung-abend-zeit');
		assert.equal(morgen.length, 1, '#3022: Uhrzeitfeld Morgen fehlt (Reiter nicht gemountet)');
		assert.equal(abend.length, 1, '#3022: Uhrzeitfeld Abend fehlt (Reiter nicht gemountet)');
		const ziffern = (k: Knoten) => text(k).replace(/[^0-9]/g, '');
		assert.equal(ziffern(morgen[0]), '0645', `Morgen-Zeit zeigt „${text(morgen[0])}“ statt 06:45 aus dem Preset`);
		assert.equal(ziffern(abend[0]), '1930', `Abend-Zeit zeigt „${text(abend[0])}“ statt 19:30 aus dem Preset`);
	});

	test('AC-3: nach dem Mount kein Schreibaufruf (kein PUT), auch nicht zeitversetzt', async () => {
		aufrufe.length = 0;
		const { panel } = await hubReiter('zustellung');
		await new Promise((r) => setTimeout(r, 1500));
		assert.equal(mitTestid(panel, 'zustellung-tab').length, 1, '#3022: Reiter Zustellung nicht gemountet — „kein PUT“ waere hier nichtssagend');
		const schreib = aufrufe.filter((a) => a.methode !== 'GET');
		assert.deepEqual(schreib, [], `blosses Oeffnen hat geschrieben: ${JSON.stringify(schreib)}`);
	});
});
