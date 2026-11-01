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
// #1743 (Spec feat_1743_reiter_aufraeumen AC-23, AC-25, AC-27): `versand` und `vorschau` sind keine
// Reiter mehr. Versand-Spruenge zielen auf `?tab=wetter-metriken#versand`, Vorschau-Ziele entfallen.
// Die gueltigen Kennungen sind hier FEST eingesetzt (nicht aus subscriptionTabs abgeleitet), damit
// die Erwartung nicht mit dem Pruefling wandert. Die beiden Totcode-Vorschaukarten der Trip-Uebersicht
// sind aus den Tabellen entfernt — sie entfallen (deadTripOverviewComponentsRemoved).
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
import { resolveTab } from '../subscriptionTabs.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SRC = join(FRONTEND, 'src');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
// #2682: das Übersichts-Modell wird echt geladen (endungslose Importe der Helfer).
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

// #1743: fuenf Reiter je Hub — fest eingesetzt.
const TRIP_IDS = ['uebersicht', 'etappen', 'wetter-metriken', 'wertebereiche', 'alarme'];
const VERGLEICH_IDS = ['uebersicht', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme'];

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

	// #1743 AC-23: Layout (3) und Reports (4) liegen unter Wetter-Metriken; der Versand-Schritt
	// (Reports) springt per Anker zum Versand-Abschnitt.
	for (const [offen, erwartet, anker] of [
		[1, 'etappen', ''],
		[2, 'wetter-metriken', ''],
		[3, 'wetter-metriken', null],
		[4, 'wetter-metriken', '#versand']
	] as Array<[number, string, string | null]>) {
		test(`erster offener Schritt ${offen} → ?tab=${erwartet}${anker ?? ''} (loest ohne Legacy auf)`, async () => {
			const { u } = await umgebungFuer(datei('routes/+page.svelte'), {
				nextPlanned: { id: 'khw' },
				setupStepsTrip: schritte(offen)
			}, { jsAlsTs: true });
			const href = (u.buildTripCtaHref as () => string)();
			assert.equal(href.startsWith('/trips/khw?tab='), true, href);
			assert.equal(tabAus(href), erwartet);
			assert.equal(resolveTab('trip', tabAus(href)).legacy, false, `${href}: Kennung laeuft ueber den Legacy-Umweg`);
			// null = Anker fuer diesen Schritt nicht festgelegt
			if (anker !== null) assert.equal(new URL(href, 'http://localhost').hash, anker, href);
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

describe('AC-10 (Verhalten): Trip-Liste — „Wetter" (Bestandsfehler #weather); #1743: keine Vorschau', () => {
	test("#1743 AC-27: onTripAction('preview') navigiert nirgendwohin (Aktion entfaellt)", async () => {
		const rek = gotoRekorder();
		const { u } = await umgebungFuer(datei('routes/trips/+page.svelte'), { goto: rek.goto }, { jsAlsTs: true });
		(u.onTripAction as (k: string, r: unknown) => void)('preview', { id: 'khw' });
		assert.deepEqual(rek.ziele, [], 'die Vorschau-Aktion darf kein Ziel mehr ansteuern');
	});

	for (const [key, erwartet] of [
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

// #1743: 'versand' und 'vorschau' sind seither ebenfalls Alt-Kennungen.
const ALT = ['overview', 'stages', 'weather', 'alerts', 'briefings', 'preview', 'idealwerte', 'layout', 'versand', 'vorschau'];

// doc-compliance-test: hartkodierte href-/Handler-Literale haben keinen Funktionsaufruf.
describe('AC-9 / AC-10 (Quelltext-Scan, doc-compliance-test): Trip-Sprunglinks nur mit neuen Trip-Kennungen', () => {
	const ERWARTET: Record<string, string[]> = {
		'lib/components/trip-detail/AlertsPreviewCard.svelte': ['wertebereiche'],
		'lib/components/alerts-tab/AlertPreviewCard.svelte': ['wetter-metriken']
	};
	for (const [rel, erwartet] of Object.entries(ERWARTET)) {
		test(`${rel.split('/').pop()}: erzeugt genau ${JSON.stringify(erwartet)}`, () => {
			const k = erzeugteKennungen(rel);
			for (const id of k) assert.ok(TRIP_IDS.includes(id), `Kennung '${id}' ist keine neue Trip-Kennung`);
			assert.deepEqual([...k].sort(), [...erwartet].sort());
		});
	}

	// #1743 AC-25/AC-28: kein Sprung auf 'versand'/'vorschau' mehr; der Zeitplan-Sprung samt Anker
	// wird als Verhalten in versand_sprung_auf_wetter_metriken.test.ts gemessen.
	// #2682 (Entscheidung 4/AC-11): der Knopf „Alle Alerts →" (Sprungziel 'wertebereiche') entfaellt
	// mit der Alerts-Attrappe bewusst; die uebrigen Sprungziele bleiben Pflicht.
	test('HubOverview: Sprungkarten nur mit neuen Trip-Kennungen (Etappen, Wetter-Metriken) — keine Versand/Vorschau, kein „Alle Alerts →"', () => {
		const k = erzeugteKennungen('lib/components/trip-detail/HubOverview.svelte');
		for (const id of k) assert.ok(TRIP_IDS.includes(id), `Kennung '${id}' ist keine neue Trip-Kennung`);
		for (const pflicht of ['etappen', 'wetter-metriken']) {
			assert.ok(k.includes(pflicht), `HubOverview springt nicht mehr auf '${pflicht}'`);
		}
		assert.ok(!k.includes('wertebereiche'), 'HubOverview springt noch auf wertebereiche („Alle Alerts →", AC-11)');
	});
});

// #2682: die Sprungziele der Übersicht (Orte, Wertebereiche, Versand) sind Daten des Modells
// (shared/hub-uebersicht/hubUebersichtModell.ts), der Baustein ruft nur `onJump(tab, anchor)`.
// Gemessen am ECHTEN Ableiter je Art — jede Kennung muss ohne Legacy-Umweg aufloesen.
describe('AC-9 / AC-10 (Verhalten, #2682): Sprungziele der geteilten Übersicht', () => {
	async function modelle() {
		const m = await import('../hub-uebersicht/hubUebersichtModell.ts');
		const vergleich = m.deriveVergleichKennzahlen(
			{ id: 'c', name: 'V', location_ids: ['l1'], schedule: 'daily', profil: 'wandern' } as never,
			'active',
			undefined,
			[{ rank: 1, loc: { id: 'l1', name: 'A' } }]
		);
		const route = m.deriveRouteKennzahlen(
			{ id: 't', name: 'T', stages: [], report_config: {} } as never,
			'planned',
			undefined,
			{ zustand: 'geladen', eintraege: [] }
		);
		return { vergleich, route };
	}
	const ziele = (m: Knoten) =>
		[m.orteKarte, m.wertebereicheKarte, m.versandKarte].filter(Boolean).map((k: Knoten) => k.sprungziel);

	test('Vergleich: Orte, Wertebereiche, Versand (#versand) — jede Kennung ist ein Vergleich-Reiter', async () => {
		const z = ziele((await modelle()).vergleich);
		assert.deepEqual(z.map((x) => x.tab), ['orte', 'wertebereiche', 'wetter-metriken']);
		assert.equal(z[2].anchor, 'versand');
		for (const { tab } of z) {
			assert.ok(VERGLEICH_IDS.includes(tab), `'${tab}' ist keine neue Vergleich-Kennung`);
			assert.equal(resolveTab('vergleich', tab).legacy, false, `'${tab}' laeuft ueber den Legacy-Umweg`);
		}
	});

	test('Vergleich: „Bearbeiten →" der Wertebereiche-Karte nutzt die Kennung wertebereiche (nie idealwerte)', async () => {
		assert.equal((await modelle()).vergleich.wertebereicheKarte?.sprungziel.tab, 'wertebereiche');
	});

	test('Trip: nur die Versand-Karte (wetter-metriken#versand) — neue Trip-Kennung', async () => {
		const z = ziele((await modelle()).route);
		assert.deepEqual(z, [{ tab: 'wetter-metriken', anchor: 'versand' }]);
		assert.equal(resolveTab('trip', z[0].tab).legacy, false);
	});

	test('der Baustein springt nur ueber die Sprungziele des Modells (kein Literal im Markup)', () => {
		const k = erzeugteKennungen('lib/components/shared/hub-uebersicht/HubUebersicht.svelte');
		assert.deepEqual(k, [], `HubUebersicht erzeugt eigene Kennungen: ${JSON.stringify(k)}`);
		assert.match(ohneKommentare('lib/components/shared/hub-uebersicht/HubUebersicht.svelte'), /onJump\?\.\(ziel\.tab/);
	});
});

describe('AC-9 / AC-10 (Quelltext-Scan, doc-compliance-test): Vergleich-Sprunglinks nur mit neuen Vergleich-Kennungen', () => {
	for (const rel of ['routes/compare/[id]/+page.svelte', 'routes/compare/+page.svelte']) {
		test(`${rel}: jede erzeugte Kennung ist ein Vergleich-Reiter`, () => {
			const k = erzeugteKennungen(rel);
			assert.ok(k.length > 0, 'Messaufbau kaputt: keine Kennung gefunden');
			for (const id of k) assert.ok(VERGLEICH_IDS.includes(id), `'${id}' ist keine neue Vergleich-Kennung`);
		});
	}

	// #2682: die Übersichts-Sprungknöpfe (Orte/Wertebereiche/Versand) zogen in den geteilten Baustein —
	// ihre Kennungen misst der Verhaltens-Block oben am Modell (nicht leer, Vergleich-Reiter, kein Legacy).
	// CompareTabs selbst darf weiterhin keine fremde Kennung erzeugen.
	test('lib/components/compare/CompareTabs.svelte: jede erzeugte Kennung ist ein Vergleich-Reiter', () => {
		for (const id of erzeugteKennungen('lib/components/compare/CompareTabs.svelte'))
			assert.ok(VERGLEICH_IDS.includes(id), `'${id}' ist keine neue Vergleich-Kennung`);
	});

	// Issue #2278 AC-12: das Hub-Menue ist reiner Lebenszyklus; "Setup abschliessen" bleibt im Hub.
	// #1743 AC-24/AC-27: "Setup abschliessen" zielt auf wetter-metriken (#versand, Verhalten in
	// versand_sprung_auf_wetter_metriken.test.ts); die Liste kennt keine Vorschau mehr.
	test('Vergleich-Detailseite: Setup abschliessen → wetter-metriken; Liste springt Alarme/Wetter-Metriken an, keine Vorschau', () => {
		const hub = erzeugteKennungen('routes/compare/[id]/+page.svelte');
		assert.ok(hub.includes('wetter-metriken'), JSON.stringify(hub));
		assert.ok(!hub.includes('versand'), JSON.stringify(hub));
		const liste = erzeugteKennungen('routes/compare/+page.svelte');
		for (const id of ['alarme', 'wetter-metriken'])
			assert.ok(liste.includes(id), `Vergleich-Liste springt nicht auf '${id}': ${JSON.stringify(liste)}`);
		assert.ok(!liste.includes('vorschau'), `Vergleich-Liste springt noch auf 'vorschau': ${JSON.stringify(liste)}`);
	});

	// #2682: „Bearbeiten →" der Wertebereiche-Karte liegt im Modell (Verhaltens-Block oben, positiv);
	// hier bleibt die Negativ-Zusicherung je Quelle.
	test('CompareTabs und Übersichts-Modell: keine Alt-Kennung idealwerte', () => {
		assert.ok(!erzeugteKennungen('lib/components/compare/CompareTabs.svelte').includes('idealwerte'));
		assert.ok(!/['"`]idealwerte['"`]/.test(ohneKommentare('lib/components/shared/hub-uebersicht/hubUebersichtModell.ts')));
	});
});

describe('AC-10 (Quelltext-Scan, doc-compliance-test): Home-Schnellaktionen', () => {
	const HOME = 'routes/+page.svelte';

	test('Trip-Links (/trips/…?tab=) nutzen nur neue Trip-Kennungen, Vergleich-Links (/compare/…?tab=) nur neue Vergleich-Kennungen', () => {
		const q = ohneKommentare(HOME);
		const trip = [...q.matchAll(/\/trips\/[^"'`\s]*\?tab=([a-z-]+)/g)].map((m) => m[1]);
		const vergleich = [...q.matchAll(/\/compare\/[^"'`\s]*\?tab=([a-z-]+)/g)].map((m) => m[1]);
		assert.ok(trip.length >= 5 && vergleich.length >= 2, `Messaufbau kaputt: trip=${trip.length} vergleich=${vergleich.length}`);
		for (const id of trip) assert.ok(TRIP_IDS.includes(id), `Home: '${id}' ist keine Trip-Kennung`);
		for (const id of vergleich) assert.ok(VERGLEICH_IDS.includes(id), `Home: '${id}' ist keine Vergleich-Kennung`);
	});

	// #1743 AC-23: die Vorschau-Schnellaktion entfaellt (Nachweis: versand_sprung_auf_wetter_metriken.test.ts).
	test('Bestandsfehler: keine Vergleich-Schnellaktion auf ?tab=preview', () => {
		const q = ohneKommentare(HOME);
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
		// #2682: geteilte Übersicht (Baustein + Modell)
		'lib/components/shared/hub-uebersicht/HubUebersicht.svelte',
		'lib/components/shared/hub-uebersicht/hubUebersichtModell.ts',
		'lib/components/trip-detail/AlertsPreviewCard.svelte',
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
