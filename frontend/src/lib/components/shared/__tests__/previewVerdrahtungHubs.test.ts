// Issue #2283 Fix-Loop (Adversary F003, F006b, F008, F009): die Alarm-Vorschau-Zusicherungen
// werden dort geprueft, wo sie WIRKEN — an der Verdrahtung im Alarme-Reiter (AlarmeTab →
// AlertPreviewCard) —, nicht nur am Baustein.
// Spec: docs/specs/modules/shared_preview_tab.md (AC-20).
//
// #1743 (Spec feat_1743_reiter_aufraeumen AC-28, AC-29, AC-33): der Hub-Reiter „Vorschau"
// (PreviewTab, previewLoader) entfaellt ersatzlos. Die Briefing-Vorschau-Faelle F001, F002,
// F004 und „Telegram-Blasen" (renderten den entfallenden PreviewTab) sind entfernt. Der
// Alarm-Vorschau-Teil (POST /api/briefings/{id}/alert-preview) BLEIBT unveraendert
// (AC-29, Regressionswaechter). Neu: kein Hub bettet einen Vorschau-Reiter mehr ein.
//
// Testart (Kern, kein Netz): Die Suite ist SSR-only, onMount und Klicks laufen
// dort nie. Deshalb zweierlei, beides am ECHTEN Code:
//   * svelteInstanzPruefstand: wertet das Instanz-Skript mit gesaeten Props aus und liest
//     die Attribut-Ausdruecke der ECHTEN Einbettung (<AlertPreviewCard …>). Der Abruf der
//     Karte (`loadPreview`) wird gegen das echte api.ts ausgefuehrt; gezaehlt wird am
//     Netz-Ausgang `globalThis.fetch`.
//   * svelte/server: der echte AlarmeTab wird gerendert — geprueft wird das Ergebnis.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/previewVerdrahtungHubs.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, findeKomponenten, ohneTypen, werte, type Knoten } from './svelteInstanzPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';

// Pfadregel #1409: relativ zu DIESER Datei.
const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const basis = pathToFileURL(FRONTEND + '/').href;
const TRIP_HUB = join(HIER, '..', '..', 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = join(HIER, '..', '..', 'compare', 'CompareTabs.svelte');
const ALARME_TAB = join(HIER, '..', 'AlarmeTab.svelte');
const KARTE = join(HIER, '..', '..', 'alerts-tab', 'AlertPreviewCard.svelte');

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(HIER, 'svelteTsModulHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const { alarmePropsAus } = await import('../../compare/alarmePropsAus.ts');
const AlarmeTab = (await import(pathToFileURL(ALARME_TAB).href)).default;

type Aufruf = { url: string; method: string; body: string | null };
let aufrufe: Aufruf[] = [];
let alarmAntwort: unknown = {};
const alt = { fetch: globalThis.fetch, window: (globalThis as Knoten).window };

before(() => {
	(globalThis as Knoten).window = {
		location: { href: 'http://localhost/x', search: '', pathname: '/x' },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
		addEventListener() {},
		removeEventListener() {},
		dispatchEvent() {
			return true;
		}
	};
	(globalThis as Knoten).fetch = (input: unknown, init?: RequestInit) => {
		const url = String(input);
		aufrufe.push({ url, method: String(init?.method ?? 'GET'), body: (init?.body as string) ?? null });
		return Promise.resolve(
			new Response(JSON.stringify(alarmAntwort), { status: 200, headers: { 'Content-Type': 'application/json' } })
		);
	};
});
after(() => {
	(globalThis as Knoten).fetch = alt.fetch;
	(globalThis as Knoten).window = alt.window;
});

const tid = (t: string) => `data-testid="${t}"`;

/** Wert eines Attributs an einer Einbettung: Ausdruck ausgewertet, statischer Text als String. */
function attribut(einbettung: Knoten, quelle: string, name: string, u: Knoten): unknown {
	const a = ((einbettung.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	assert.ok(a, `Attribut ${name} fehlt an <${einbettung.name}>`);
	if (a!.value === true) return true;
	if (a!.value?.type === 'ExpressionTag') return werte(ohneTypen(quelle, a!.value.expression), u);
	const teile = (Array.isArray(a!.value) ? a!.value : [a!.value]) as Knoten[];
	return teile.map((t) => (t.type === 'Text' ? t.data : werte(ohneTypen(quelle, t.expression), u))).join('');
}

/** Alle Props einer Einbettung, ausgewertet gegen die Umgebung. */
function propsVon(einbettung: Knoten, quelle: string, u: Knoten): Record<string, unknown> {
	const p: Record<string, unknown> = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type === 'Attribute') p[a.name] = attribut(einbettung, quelle, a.name, u);
	}
	return p;
}

// ── #1743 AC-28/AC-33: kein Hub bettet den Briefing-Vorschau-Reiter mehr ein ──
describe('#1743: Trip- und Vergleichs-Hub betten keinen Vorschau-Reiter (PreviewTab) mehr ein', () => {
	for (const [hub, datei, saat] of [
		['TripTabs', TRIP_HUB, { trip: { id: 't-1', stages: [], report_config: {}, display_config: {} }, badges: {} }],
		['CompareTabs', VERGLEICH_HUB, { preset: vollerVergleich('cp-1'), locations: [], orteCount: 3 }]
	] as const) {
		test(`${hub}: keine <PreviewTab>-Einbettung`, async () => {
			const { ast } = await umgebungFuer(datei, { ...saat }, { jsAlsTs: true });
			assert.equal(findeKomponenten(ast, 'PreviewTab').length, 0, `${hub} bettet den entfallenen Vorschau-Reiter noch ein`);
		});
	}
});

// ── F003 / AC-20: AlarmeTab(vergleich) → AlertPreviewCard → abgeschickter Koerper ─
const KATALOG = [{ metric: 'gust_max', label: 'Böen', alertMetric: 'wind_gust' }];

function wizStub(): Record<string, unknown> {
	return {
		officialWarningsEnabled: true,
		radarAlertEnabled: false,
		activeMetricKeys: ['gust_max'],
		metricAlertLevels: { wind_gust: 'standard' },
		channelThresholds: {},
		telegramStyle: 'rich',
		alertCooldownMinutes: 30,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00'
	};
}

function alarmeSaat(preset: Knoten): Record<string, unknown> {
	return { context: 'vergleich', ...alarmePropsAus(wizStub() as never), catalog: KATALOG, preset, profileOverride: { premium_sms_allowed: true } };
}

describe('F003 (AC-20): AlarmeTab im Vergleich verdrahtet die Karte mit kind=vergleich und den echten Orten', () => {
	test('der abgeschickte Koerper geht an ?kind=vergleich und traegt genau die location_ids des Vergleichs', async () => {
		const preset = vollerVergleich('cp-2283');
		const { ast, quelle, u } = await umgebungFuer(ALARME_TAB, alarmeSaat(preset), { jsAlsTs: true });
		const karten = findeKomponenten(ast, 'AlertPreviewCard');
		const vergleich = karten.filter((k) => attribut(k, quelle, 'kind', u) === 'vergleich');
		assert.equal(vergleich.length, 1, 'genau eine Karte mit kind="vergleich" im Alarme-Reiter erwartet');
		const props = propsVon(vergleich[0], quelle, u);
		assert.deepEqual(props.locationIds, preset.location_ids, 'AlarmeTab reicht nicht die Orte des Vergleichs durch');
		assert.equal(props.id, 'cp-2283');
		assert.ok((props.alertRules as unknown[]).length > 0, 'Messaufbau: aus dem Katalog muss mindestens eine Regel entstehen');

		const karte = await umgebungFuer(KARTE, { ...props, stages: undefined }, { jsAlsTs: true });
		assert.equal(typeof karte.u.loadPreview, 'function', 'Messaufbau: loadPreview nicht auswertbar');
		aufrufe = [];
		alarmAntwort = { subject: 'S', email_html: '<p>x</p>', email_plain: 'x', telegram: 't', sms: 's' };
		await karte.u.loadPreview();
		const posts = aufrufe.filter((a) => a.url.includes('/alert-preview'));
		assert.equal(posts.length, 1, `genau ein Alarm-Vorschau-Abruf erwartet: ${JSON.stringify(aufrufe)}`);
		const url = new URL(posts[0].url, 'http://l');
		assert.equal(url.pathname, '/api/briefings/cp-2283/alert-preview');
		assert.equal(url.searchParams.get('kind'), 'vergleich');
		const koerper = JSON.parse(posts[0].body ?? '{}') as { changes: { location_id?: string; segment_id?: string }[] };
		assert.deepEqual(
			[...new Set(koerper.changes.map((c) => c.location_id))],
			preset.location_ids,
			'der Koerper traegt nicht die Orte des Vergleichs'
		);
		assert.equal(JSON.stringify(koerper).includes('segment'), false, 'Vergleichs-Koerper mit Segment-Semantik');
	});
});

// ── F006b: Vergleich ohne Orte ⇒ Hinweis, kein Abruf ────────────────────────
describe('F006b: Alarm-Vorschau im Vergleich ohne Orte zeigt einen Hinweis statt eines Lade-Knopfs', () => {
	test('AlarmeTab(vergleich, location_ids=[]): Hinweis sichtbar, kein „Vorschau laden"', () => {
		const html = render(AlarmeTab, { props: alarmeSaat({ ...vollerVergleich('cp-leer'), location_ids: [] }) }).body;
		assert.ok(html.includes(tid('alert-preview-no-locations')), 'Hinweis „keine Orte" fehlt');
		assert.equal(html.includes(tid('alert-preview-load-btn')), false, 'ohne Orte darf kein Abruf ausloesbar sein (422)');
	});
	test('Gegenprobe: mit Orten erscheint der Lade-Knopf', () => {
		const html = render(AlarmeTab, { props: alarmeSaat(vollerVergleich('cp-voll')) }).body;
		assert.ok(html.includes(tid('alert-preview-load-btn')));
		assert.equal(html.includes(tid('alert-preview-no-locations')), false);
	});
});

// ── F008: Trip-Gegenfall — die Trip-Karte laedt ohne Orte, mit der echten trip.id ─
const REGELN = [
	{ id: 'r1', metric: 'wind_gust', threshold: 60, kind: 'absolute', severity: 'warning', enabled: true }
];
const ALARM_TRIP = {
	id: 'trip-2283',
	name: 'KHW 403',
	stages: [{ id: 'S1', name: 'Etappe 1', waypoints: [] }],
	alert_rules: REGELN,
	display_config: {},
	report_config: { send_email: true }
};

function routeSaat(): Record<string, unknown> {
	return {
		context: 'route',
		trip: ALARM_TRIP,
		activeMetrics: ['wind_gust'],
		metricLevels: {},
		existingChannels: { email: true, telegram: false, sms: false, premium_sms: false },
		profileOverride: { premium_sms_allowed: true }
	};
}

describe('F008: AlarmeTab im Trip — Karte mit kind=route und echter trip.id, laedt ohne Orte', () => {
	test('gerendert: Lade-Knopf sichtbar, kein „keine Orte"-Hinweis, kein Anlege-Hinweis', () => {
		const html = render(AlarmeTab, { props: routeSaat() }).body;
		assert.ok(html.includes(tid('alert-preview-load-btn')), 'die Trip-Karte bietet keinen Abruf an');
		assert.equal(html.includes(tid('alert-preview-no-locations')), false, 'Orte-Guard greift faelschlich im Trip');
		assert.equal(html.includes(tid('alert-preview-unsaved')), false, 'Trip-Karte haelt sich faelschlich fuer ungespeichert');
	});

	test('Abruf geht an /api/briefings/{trip.id}/alert-preview?kind=route mit Segment-Koerper', async () => {
		const { ast, quelle, u } = await umgebungFuer(ALARME_TAB, routeSaat(), { jsAlsTs: true });
		const route = findeKomponenten(ast, 'AlertPreviewCard').filter((k) => attribut(k, quelle, 'kind', u) === 'route');
		assert.equal(route.length, 1, 'genau eine Karte mit kind="route" erwartet');
		const props = propsVon(route[0], quelle, u);
		assert.equal(props.id, 'trip-2283', 'AlarmeTab reicht nicht die echte trip.id an die Karte');

		const karte = await umgebungFuer(KARTE, { ...props, locationIds: undefined }, { jsAlsTs: true });
		aufrufe = [];
		alarmAntwort = { subject: 'S', email_html: '<p>x</p>', email_plain: 'x', telegram: 't', sms: 's' };
		await karte.u.loadPreview();
		const posts = aufrufe.filter((a) => a.url.includes('/alert-preview'));
		assert.equal(posts.length, 1);
		const url = new URL(posts[0].url, 'http://l');
		assert.equal(url.pathname, '/api/briefings/trip-2283/alert-preview');
		assert.equal(url.searchParams.get('kind'), 'route');
		const koerper = JSON.parse(posts[0].body ?? '{}') as { changes: { segment_id?: string }[]; segment_times?: unknown[] };
		// Issue #1737: Segment-Kennung des Tages, nicht die Etappen-Kennung (sonst 422 im Kern).
		assert.equal(koerper.changes[0]?.segment_id, '1');
		assert.ok(Array.isArray(koerper.segment_times), 'Trip-Koerper ohne segment_times');
	});
});

// ── F009: Anlege-Seite (noch keine ID) ⇒ Hinweis, kein Abruf ───────────────
describe('F009: Alarm-Vorschau ohne gespeicherten Eintrag', () => {
	test('AlarmeTab(vergleich) auf der Anlege-Seite (kein preset): Hinweis „nach dem Speichern", kein Lade-Knopf', () => {
		const saat = alarmeSaat(vollerVergleich('egal'));
		delete (saat as Knoten).preset;
		const html = render(AlarmeTab, { props: saat }).body;
		assert.ok(html.includes(tid('alert-preview-unsaved')), 'Hinweis alert-preview-unsaved fehlt');
		assert.equal(html.includes(tid('alert-preview-load-btn')), false, 'ohne ID darf kein Abruf ausloesbar sein');
	});
});
