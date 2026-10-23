// TDD RED — Issue #1743 (Spec feat_1743_reiter_aufraeumen §3, AC-6, AC-8): EIN geteilter
// Baustein `shared/WetterMetrikenVersandPanel.svelte` fuer „Wetter-Metriken + Versand" in
// Trip-Hub, Ortsvergleich-Hub, `/trips/new` und `/compare/new`.
//
// Messweise:
//   (1) Parität aus dem GERENDERTEN Baustein (svelte/server, kein Quelltext-Lesen): je context
//       wird die Abschnittsfolge aus dem HTML gelesen — erst der Wetter-Metriken-Inhalt
//       (Wurzelklasse `metrics-tab` von WeatherMetricsTab, in jedem Ladezustand vorhanden,
//       auch im SSR), darunter `<section id="versand" data-testid="versand-abschnitt">`
//       mit dem Versand-Inhalt (`versand-tab`). Beide contexts muessen dieselbe Folge liefern.
//   (2) Einsatz: die vier Flaechen mounten DENSELBEN Baustein (Template-AST via Svelte-Compiler,
//       Importquelle shared/), mit dem passenden context — keine zweite Kombination.
//
// Bewusst NICHT festgelegt (steht weder in Spec noch in red-schnittstellen.md): der Prop-Name, ueber
// den die Aktivierungs-Karte (Pausieren/Aktivieren) in den Baustein kommt. Gepinnt ist in
// compare/__tests__/versand_panel_ohne_wrapper_div.test.ts: der Vergleichs-Hub reicht das Snippet
// `hubActivationCard`, der Trip-Hub nicht, der VersandTab im Abschnitt bekommt `activation`.
// Die Wirkung von Pausieren/Aktivieren misst Playwright (/50); den Flush davor
// compare_hub_pausieren_flusht_vorher.test.ts (Regressionswaechter).
//
// RED heute: der Baustein existiert nicht → jeder Test meldet das per assert.fail (kein Lade-Abbruch).
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei.
//
// Ausfuehren (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/__tests__/wetter_metriken_versand_panel_paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const COMPONENTS = join(SHARED, '..');
const FRONTEND = resolve(HIER, '../../../../..');
const PANEL = join(SHARED, 'WetterMetrikenVersandPanel.svelte');

register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');

type Context = 'route' | 'vergleich';

async function ladePanel(): Promise<unknown> {
	if (!existsSync(PANEL)) {
		return assert.fail('#1743 AC-8: shared/WetterMetrikenVersandPanel.svelte existiert nicht — der geteilte Baustein fehlt');
	}
	try {
		return (await import(pathToFileURL(PANEL).href)).default;
	} catch (e) {
		return assert.fail(`#1743 AC-8: WetterMetrikenVersandPanel laesst sich nicht laden: ${(e as Error).message.split('\n')[0]}`);
	}
}

/** Minimaler Speicher-Controller — SSR fuehrt keine Speicherung aus. */
const controllerStub = {
	state: 'idle',
	hasPending: false,
	schedule() {},
	flush: async () => {},
	cancel() {},
	markPristine() {},
	setDirty() {}
};

const TRIP = {
	id: 't-1743',
	name: 'Paritaet',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-23', waypoints: [] }],
	report_config: { morning_enabled: true, morning_time: '06:00', evening_enabled: false },
	display_config: { metrics: [] }
};

const PRESET = {
	id: 'cp-1743',
	name: 'Paritaet',
	location_ids: ['loc-a', 'loc-b', 'loc-c'],
	schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 9,
	empfaenger: [],
	created_at: '2026-01-01T00:00:00Z',
	hourly_enabled: true,
	outlook_enabled: true,
	day_window_start_hour: 4,
	day_window_end_hour: 19,
	display_config: {
		active_metrics: ['wind_max_kmh'],
		channel_active_metrics: {},
		hourly_metrics: ['wind_max_kmh'],
		outlook_metrics: ['wind_max_kmh'],
		outlook_metric_formats: {}
	}
};

/** Props, die die Hubs heute an WeatherMetricsTab bzw. VersandTab/BriefingScheduleTab reichen. */
function props(context: Context): Record<string, unknown> {
	if (context === 'route') {
		return { context, trip: TRIP, onTripUpdate: () => {}, saveController: controllerStub };
	}
	return {
		context,
		preset: PRESET,
		saveController: controllerStub,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		onCompareUpdate: () => {},
		activeMetricKeys: ['wind_max_kmh'],
		channelActiveMetricKeys: { email: null, telegram: null, sms: null },
		officialAlertsEnabled: true,
		hourlyMetricKeys: ['wind_max_kmh'],
		hourlyEnabled: true,
		outlookMetricKeys: ['wind_max_kmh'],
		outlookMetricFormats: {},
		outlookEnabled: true,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19
	};
}

async function html(context: Context): Promise<string> {
	const Panel = await ladePanel();
	return render(Panel as never, { props: props(context) as never }).body.replace(/<!--.*?-->/g, '');
}

/** Abschnittsfolge im gerenderten HTML: 'wetter-metriken' | 'versand' in Dokument-Reihenfolge. */
function abschnittsfolge(h: string): string[] {
	const treffer: Array<[number, string]> = [];
	// Wurzel von WeatherMetricsTab traegt in JEDEM Zustand (geladen, Lade-/Fehlerhuelle — SSR
	// laedt keinen Katalog) die Klasse `metrics-tab`; gezaehlt wird ihr ERSTES Auftreten.
	const wm = h.search(/class="metrics-tab\b/);
	if (wm >= 0) treffer.push([wm, 'wetter-metriken']);
	for (const m of h.matchAll(/<section\b[^>]*>/g)) {
		const tag = m[0];
		if (/\bid="versand"/.test(tag)) treffer.push([m.index ?? 0, 'versand']);
	}
	return treffer.sort((a, b) => a[0] - b[0]).map(([, k]) => k);
}

describe('#1743 AC-8 (gerendert): Abschnittsfolge des geteilten Bausteins je context', () => {
	for (const context of ['route', 'vergleich'] as Context[]) {
		test(`${context}: Wetter-Metriken-Inhalt, darunter genau EIN Abschnitt #versand`, async () => {
			const h = await html(context);
			assert.deepEqual(abschnittsfolge(h), ['wetter-metriken', 'versand'], 'erwartet: Wetter-Metriken, dann Versand');
		});

		test(`${context}: Abschnitt #versand traegt data-testid="versand-abschnitt" und enthaelt den Versand-Inhalt`, async () => {
			const h = await html(context);
			const tag = [...h.matchAll(/<section\b[^>]*>/g)].find((m) => /\bid="versand"/.test(m[0]));
			assert.ok(tag, 'kein <section id="versand"> im gerenderten Baustein');
			assert.match(tag[0], /data-testid="versand-abschnitt"/);
			const ab = tag.index ?? 0;
			const ende = h.indexOf('</section>', ab);
			const innen = h.slice(ab, ende === -1 ? undefined : ende);
			assert.match(innen, /data-testid="versand-tab"/, 'der Versand-Inhalt (VersandTab) steht nicht im Abschnitt #versand');
		});
	}

	test('beide contexts liefern DIESELBE Abschnittsfolge (Teilungs-Invariante)', async () => {
		assert.deepEqual(abschnittsfolge(await html('route')), abschnittsfolge(await html('vergleich')));
	});
});

// ── Einsatz: alle vier Flaechen mounten denselben Baustein ───────────────────

function ast(datei: string): any {
	return parse(readFileSync(datei, 'utf-8'), { modern: true });
}

function mounts(knoten: unknown, name: string): any[] {
	const treffer: any[] = [];
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Record<string, any>;
		if (k.type === 'Component' && k.name === name) treffer.push(k);
		for (const key of Object.keys(k)) if (key !== 'parent') lauf(k[key]);
	})(knoten);
	return treffer;
}

/** Importquelle des Namens im Instanz-Skript, sonst null. */
function importQuelle(a: any, name: string): string | null {
	for (const stmt of a.instance?.content?.body ?? []) {
		if (stmt.type !== 'ImportDeclaration') continue;
		if ((stmt.specifiers ?? []).some((s: any) => s.local?.name === name)) return String(stmt.source.value);
	}
	return null;
}

/** context-Wert der Einbettung: statischer Text oder Ausdrucks-Quelltext. */
function contextWert(einbettung: any, quelle: string): string | null {
	const a = (einbettung.attributes ?? []).find((x: any) => x.type === 'Attribute' && x.name === 'context');
	if (!a) return null;
	if (Array.isArray(a.value)) return a.value.map((t: any) => t.data ?? '').join('');
	if (a.value?.type === 'ExpressionTag') return quelle.slice(a.value.expression.start, a.value.expression.end);
	return null;
}

const FLAECHEN: Array<[string, string, string]> = [
	['Trip-Hub', join(COMPONENTS, 'trip-detail/TripTabs.svelte'), 'route'],
	['Ortsvergleich-Hub', join(COMPONENTS, 'compare/CompareTabs.svelte'), 'vergleich'],
	['/trips/new', join(COMPONENTS, 'trip-new/TripNewEditor.svelte'), 'route'],
	['/compare/new', join(COMPONENTS, 'compare-new/CompareNewEditor.svelte'), 'vergleich']
];
/** Die Hubs haben einen festen Kontext — dort ist nur der statische Literalwert zulaessig. */
const FESTER_KONTEXT = new Set(['Trip-Hub', 'Ortsvergleich-Hub']);

describe('#1743 AC-8 (Einsatz): Trip-Hub, Vergleichs-Hub und beide Anlege-Seiten mounten DENSELBEN Baustein', () => {
	for (const [flaeche, datei, ctx] of FLAECHEN) {
		test(`${flaeche}: WetterMetrikenVersandPanel aus shared/, context=${ctx}`, () => {
			const a = ast(datei);
			const quelle = readFileSync(datei, 'utf-8');
			const q = importQuelle(a, 'WetterMetrikenVersandPanel');
			assert.ok(q, `${flaeche} importiert WetterMetrikenVersandPanel nicht`);
			assert.match(q, /(^|\/)shared\/WetterMetrikenVersandPanel\.svelte$/, `Importquelle ist nicht der geteilte Baustein: ${q}`);
			const m = mounts(a.fragment, 'WetterMetrikenVersandPanel');
			assert.ok(m.length >= 1, `${flaeche} bettet WetterMetrikenVersandPanel nicht ein`);
			for (const e of m) {
				const wert = contextWert(e, quelle);
				if (FESTER_KONTEXT.has(flaeche)) {
					assert.equal(wert, ctx, `${flaeche}: context muss statisch "${ctx}" sein`);
				} else {
					assert.ok(wert === ctx || (wert !== null && wert.includes(`'${ctx}'`)) || wert === 'context', `${flaeche}: context=${wert}, erwartet ${ctx}`);
				}
			}
		});
	}
});
