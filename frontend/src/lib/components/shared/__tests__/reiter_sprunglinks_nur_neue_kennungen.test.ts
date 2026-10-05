// TDD RED — Feature #2287 (Epic #2345, Etappe P2 „eine Reiterleiste"):
// Sprunglinks, Schnellaktionen und Hub-Weiterleitungen erzeugen NUR neue Kennungen
// (AC-9, AC-10, AC-11) — und die drei Bestandsfehler sind weg:
//   (1) Home-Schnellaktion „Vorschau" eines Ortsvergleichs (`?tab=preview` → Uebersicht),
//   (2) Trip-Liste „Wetter" (`#weather`, Hash wurde nie gelesen),
//   (3) WeatherSummaryCard (`#weather`).
//
// Spec: docs/specs/modules/feat_2287_tab_kennungen.md — AC-9, AC-10, AC-11
//
// Messweise: wo ein Funktionsaufruf moeglich ist, wird die ECHTE Funktion der
// Komponente (Instanz-Skript via `umgebungFuer`) gegen gesaete Props aufgerufen und
// die erzeugte Ziel-URL gemessen (Aufzeichnung von `goto` ersetzt nur das Browser-API).
// Hartkodierte href-/Handler-Literale im Markup haben keinen Funktionsaufruf — dafuer
// Quelltext-Scan (doc-compliance-test, ausdruecklich als solcher gekennzeichnet).
//
// Nur im Browser messbar (Playwright, /e2e-verify): dass der Klick auf die Schnellaktion
// den Reiter wirklich oeffnet (AC-10 „landet im richtigen Reiter").
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/reiter_sprunglinks_nur_neue_kennungen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, type Knoten } from './svelteInstanzPruefstand.ts';
import { subscriptionTabs } from '../subscriptionTabs.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SRC = join(FRONTEND, 'src');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const TRIP_IDS = subscriptionTabs('trip').map((t) => t.id);
const VERGLEICH_IDS = subscriptionTabs('vergleich').map((t) => t.id);

const datei = (rel: string) => join(SRC, rel);
const tabAus = (url: string): string | null => new URL(url, 'http://localhost/x').searchParams.get('tab');

/** Aufzeichnung der `goto`-Ziele. */
function gotoRekorder(): { ziele: string[]; goto: (u: string) => Promise<void> } {
	const ziele: string[] = [];
	return {
		ziele,
		goto: (u: string) => {
			ziele.push(u);
			return Promise.resolve();
		}
	};
}

// ── Funktionsaufrufe: erzeugte Ziel-URLs ────────────────────────────────────────

describe('AC-10 (Verhalten): Home-Schnellaktion „Trip einrichten" fuehrt in neue Kennungen', () => {
	const schritte = (offen: number) => [0, 1, 2, 3, 4].map((i) => ({ label: `s${i}`, done: i !== offen }));

	for (const [offen, erwartet] of [
		[1, 'etappen'],
		[2, 'wetter-metriken'],
		[3, 'versand'],
		[4, 'versand']
	] as Array<[number, string]>) {
		test(`erster offener Schritt ${offen} → ?tab=${erwartet}`, async () => {
			const { u } = await umgebungFuer(datei('routes/+page.svelte'), {
				nextPlanned: { id: 'khw' },
				setupStepsTrip: schritte(offen)
			}, { jsAlsTs: true });
			const href = (u.buildTripCtaHref as () => string)();
			assert.equal(href.startsWith('/trips/khw?tab='), true, href);
			assert.equal(tabAus(href), erwartet);
		});
	}

	test('alles erledigt → Uebersicht (neue Kennung)', async () => {
		const { u } = await umgebungFuer(datei('routes/+page.svelte'), {
			nextPlanned: { id: 'khw' },
			setupStepsTrip: [0, 1, 2, 3, 4].map((i) => ({ label: `s${i}`, done: true }))
		}, { jsAlsTs: true });
		assert.equal(tabAus((u.buildTripCtaHref as () => string)()), 'uebersicht');
	});
});

describe('AC-10 (Verhalten): Trip-Liste — „Vorschau" und „Wetter" (Bestandsfehler #weather)', () => {
	for (const [key, erwartet] of [
		['preview', 'vorschau'],
		['weather', 'wetter-metriken']
	] as Array<[string, string]>) {
		test(`onTripAction('${key}') → /trips/<id>?tab=${erwartet}, kein Hash`, async () => {
			const rek = gotoRekorder();
			const { u } = await umgebungFuer(datei('routes/trips/+page.svelte'), { goto: rek.goto }, { jsAlsTs: true });
			(u.onTripAction as (k: string, r: unknown) => void)(key, { id: 'khw' });
			assert.equal(rek.ziele.length, 1, JSON.stringify(rek.ziele));
			assert.equal(rek.ziele[0].includes('#'), false, 'Hash-Anker wird nie gelesen (Bestandsfehler)');
			assert.equal(rek.ziele[0].startsWith('/trips/khw?tab='), true, rek.ziele[0]);
			assert.equal(tabAus(rek.ziele[0]), erwartet);
		});
	}
});

describe('AC-10 (Verhalten): WeatherSummaryCard „Wetter" oeffnet den Reiter Wetter-Metriken', () => {
	test('Klick-Handler → /trips/<id>?tab=wetter-metriken (kein #weather)', async () => {
		const rek = gotoRekorder();
		const { u } = await umgebungFuer(datei('lib/components/edit/WeatherSummaryCard.svelte'), {
			goto: rek.goto,
			tripId: 'khw',
			displayConfig: null
		}, { jsAlsTs: true });
		(u.onOpenWeatherTab as () => void)();
		assert.equal(rek.ziele.length, 1, JSON.stringify(rek.ziele));
		assert.equal(rek.ziele[0].includes('#'), false);
		assert.equal(rek.ziele[0].startsWith('/trips/khw?tab='), true, rek.ziele[0]);
		assert.equal(tabAus(rek.ziele[0]), 'wetter-metriken');
	});
});

describe('AC-9 (Verhalten): VersandTab „Etappen oeffnen →" springt mit der neuen Kennung', () => {
	test("handleOpenStages ruft onJump('etappen')", async () => {
		const aufrufe: string[] = [];
		const { u } = await umgebungFuer(datei('lib/components/shared/VersandTab.svelte'), {
			onJump: (t: string) => aufrufe.push(t)
		}, { jsAlsTs: true });
		(u.handleOpenStages as () => void)();
		assert.deepEqual(aufrufe, ['etappen']);
	});
});

// ── Quelltext-Scan (doc-compliance-test) ────────────────────────────────────────

/** Quelltext ohne Kommentare (Zeilen-, Block-, HTML-Kommentare). */
function ohneKommentare(rel: string): string {
	return readFileSync(datei(rel), 'utf-8')
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

/** Alle Reiter-Kennungen, die eine Datei erzeugt: ?tab=, makeJumpHandler/handleValueChange/onJump-Literale. */
function erzeugteKennungen(rel: string): string[] {
	const q = ohneKommentare(rel);
	const treffer: string[] = [];
	for (const re of [
		/\?tab=([a-z][a-z-]*)/g,
		/makeJumpHandler\('([a-z][a-z-]*)'\)/g,
		/handleValueChange\('([a-z][a-z-]*)'\)/g,
		/onJump\??\.?\('([a-z][a-z-]*)'\)/g
	]) {
		for (const m of q.matchAll(re)) treffer.push(m[1]);
	}
	return treffer;
}

const ALT = ['overview', 'stages', 'weather', 'alerts', 'briefings', 'preview', 'idealwerte', 'layout'];

// doc-compliance-test: hartkodierte href-/Handler-Literale haben keinen Funktionsaufruf.
describe('AC-9 / AC-10 (Quelltext-Scan, doc-compliance-test): Trip-Sprunglinks nur mit neuen Trip-Kennungen', () => {
	const ERWARTET: Record<string, string[]> = {
		'lib/components/trip-detail/BriefingPreviewCard.svelte': ['versand'],
		'lib/components/trip-detail/AlertsPreviewCard.svelte': ['wertebereiche'],
		'lib/components/trip-detail/PreviewCard.svelte': ['vorschau', 'vorschau'],
		'lib/components/alerts-tab/AlertPreviewCard.svelte': ['wetter-metriken']
	};
	for (const [rel, erwartet] of Object.entries(ERWARTET)) {
		test(`${rel.split('/').pop()}: erzeugt genau ${JSON.stringify(erwartet)}`, () => {
			const k = erzeugteKennungen(rel);
			for (const id of k) assert.ok(TRIP_IDS.includes(id), `Kennung '${id}' ist keine neue Trip-Kennung`);
			assert.deepEqual([...k].sort(), [...erwartet].sort());
		});
	}

	test('HubOverview: fuenf Sprungkarten, alle mit neuer Trip-Kennung (Etappen, Wetter-Metriken, Versand, Vorschau enthalten)', () => {
		const k = erzeugteKennungen('lib/components/trip-detail/HubOverview.svelte');
		assert.equal(k.length, 5, JSON.stringify(k));
		for (const id of k) assert.ok(TRIP_IDS.includes(id), `Kennung '${id}' ist keine neue Trip-Kennung`);
		for (const pflicht of ['etappen', 'wetter-metriken', 'versand', 'vorschau']) {
			assert.ok(k.includes(pflicht), `HubOverview springt nicht mehr auf '${pflicht}'`);
		}
	});
});

describe('AC-9 / AC-10 (Quelltext-Scan, doc-compliance-test): Vergleich-Sprunglinks nur mit neuen Vergleich-Kennungen', () => {
	for (const rel of [
		'lib/components/compare/CompareTabs.svelte',
		'routes/compare/[id]/+page.svelte',
		'routes/compare/+page.svelte'
	]) {
		test(`${rel}: jede erzeugte Kennung ist ein Vergleich-Reiter`, () => {
			const k = erzeugteKennungen(rel);
			assert.ok(k.length > 0, 'Messaufbau kaputt: keine Kennung gefunden');
			for (const id of k) assert.ok(VERGLEICH_IDS.includes(id), `'${id}' ist keine neue Vergleich-Kennung`);
		});
	}

	test('Vergleich-Detailseite: ?tab=vorschau (Weiterleitung) und ?tab=versand (Setup abschliessen) bleiben', () => {
		const k = erzeugteKennungen('routes/compare/[id]/+page.svelte');
		assert.ok(k.includes('vorschau') && k.includes('versand'), JSON.stringify(k));
	});

	test('CompareTabs: „Bearbeiten →"-Sprung auf Wertebereiche nutzt die Kennung wertebereiche', () => {
		const k = erzeugteKennungen('lib/components/compare/CompareTabs.svelte');
		assert.ok(k.includes('wertebereiche'));
		assert.ok(!k.includes('idealwerte'));
	});
});

describe('AC-10 (Quelltext-Scan, doc-compliance-test): Home-Schnellaktionen', () => {
	const HOME = 'routes/+page.svelte';

	test('Trip-Links (/trips/…?tab=) nutzen nur neue Trip-Kennungen, Vergleich-Links (/compare/…?tab=) nur neue Vergleich-Kennungen', () => {
		const q = ohneKommentare(HOME);
		const trip = [...q.matchAll(/\/trips\/[^"'`\s]*\?tab=([a-z-]+)/g)].map((m) => m[1]);
		const vergleich = [...q.matchAll(/\/compare\/[^"'`\s]*\?tab=([a-z-]+)/g)].map((m) => m[1]);
		assert.ok(trip.length >= 5 && vergleich.length >= 3, `Messaufbau kaputt: trip=${trip.length} vergleich=${vergleich.length}`);
		for (const id of trip) assert.ok(TRIP_IDS.includes(id), `Home: '${id}' ist keine Trip-Kennung`);
		for (const id of vergleich) assert.ok(VERGLEICH_IDS.includes(id), `Home: '${id}' ist keine Vergleich-Kennung`);
	});

	test('Bestandsfehler: Vergleich-Schnellaktion „Vorschau" zeigt auf ?tab=vorschau (nicht ?tab=preview)', () => {
		const q = ohneKommentare(HOME);
		assert.ok(/\/compare\/\{compareHero\.id\}\?tab=vorschau/.test(q), 'Vergleich-Vorschau-Link fehlt');
		assert.ok(!/\/compare\/[^"'`\s]*\?tab=preview/.test(q), 'Alt-Kennung preview fuer den Vergleich');
	});
});

describe('AC-10 / AC-15 (Quelltext-Scan, doc-compliance-test): kein Alt-Literal, kein #weather an den betroffenen Stellen', () => {
	const DATEIEN = [
		'routes/+page.svelte',
		'routes/trips/+page.svelte',
		'routes/compare/+page.svelte',
		'routes/trips/[id]/+page.svelte',
		'routes/compare/[id]/+page.svelte',
		'lib/components/edit/WeatherSummaryCard.svelte',
		'lib/components/shared/VersandTab.svelte',
		'lib/components/trip-detail/HubOverview.svelte',
		'lib/components/trip-detail/BriefingPreviewCard.svelte',
		'lib/components/trip-detail/AlertsPreviewCard.svelte',
		'lib/components/trip-detail/PreviewCard.svelte',
		'lib/components/alerts-tab/AlertPreviewCard.svelte'
	];
	for (const rel of DATEIEN) {
		test(`${rel}: weder #weather noch ?tab=<Alt-Kennung> noch Alt-Kennung in Sprung-Literalen`, () => {
			const q = ohneKommentare(rel);
			assert.ok(!q.includes('#weather'), '#weather wird nie gelesen (Bestandsfehler)');
			for (const alt of ALT) {
				assert.ok(!new RegExp(`\\?tab=\\$?\\{?${alt}\\b`).test(q), `?tab=${alt} in ${rel}`);
			}
			for (const id of erzeugteKennungen(rel)) assert.ok(!ALT.includes(id), `Sprung-Literal '${id}' in ${rel}`);
		});
	}

	test("Seiten lesen ?tab= mit neuem Default 'uebersicht' (kein 'overview')", () => {
		for (const rel of ['routes/trips/[id]/+page.svelte', 'routes/compare/[id]/+page.svelte']) {
			assert.ok(!/['"`]overview['"`]/.test(ohneKommentare(rel)), `'overview' in ${rel}`);
		}
	});
});

// ── AC-11 ───────────────────────────────────────────────────────────────────────

describe('AC-11: wertebereicheTabId entfaellt — eine Kennung fuer beide kinds', () => {
	test('weder Export im Modul noch Verwendung im Quelltext', async () => {
		const mod = (await import('../alarme-tab/alarmeTabSections.ts')) as Knoten;
		assert.equal('wertebereicheTabId' in mod, false);
		// doc-compliance-test
		assert.ok(!readFileSync(datei('lib/components/shared/alarme-tab/alarmeTabSections.ts'), 'utf-8').includes('wertebereicheTabId'));
	});

	test("die gemeinsame Tabelle kennt 'wertebereiche' in beiden kinds", () => {
		assert.ok(TRIP_IDS.includes('wertebereiche') && VERGLEICH_IDS.includes('wertebereiche'));
	});
});
