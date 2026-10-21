// Issue #2283 Fix-Loop (Adversary F001–F004, F006b): die Vorschau-Zusicherungen
// werden dort geprueft, wo sie WIRKEN — an der Verdrahtung in den Hubs
// (TripTabs, CompareTabs, AlarmeTab) und am Einhaengepunkt des Reiters —, nicht
// nur am Baustein.
// Spec: docs/specs/modules/shared_preview_tab.md (AC-8, AC-9, AC-12, AC-15, AC-20).
//
// Testart (Kern, kein Netz): Die Suite ist SSR-only, onMount und Klicks laufen
// dort nie. Deshalb zweierlei, beides am ECHTEN Code:
//   * svelteInstanzPruefstand: wertet das Instanz-Skript des Hubs mit gesaeten
//     Props aus und liest die Attribut-Ausdruecke der ECHTEN Einbettung
//     (<PreviewTab …>, <AlertPreviewCard …>, {#key …}). Der Einhaengepunkt
//     (`onMount(...)` in PreviewTab) und der Abruf der Karte (`loadPreview`)
//     werden gegen den echten Lader / das echte api.ts ausgefuehrt; gezaehlt
//     wird am Netz-Ausgang `globalThis.fetch`.
//   * svelte/server: die so gewonnenen Props speisen den echten PreviewTab bzw.
//     AlarmeTab — geprueft wird das gerenderte Ergebnis.
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
const PREVIEW_TAB = join(HIER, '..', 'PreviewTab.svelte');
const TRIP_HUB = join(HIER, '..', '..', 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = join(HIER, '..', '..', 'compare', 'CompareTabs.svelte');
const ALARME_TAB = join(HIER, '..', 'AlarmeTab.svelte');
const KARTE = join(HIER, '..', '..', 'alerts-tab', 'AlertPreviewCard.svelte');

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(HIER, 'svelteTsModulHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const { createPreviewLoader } = await import('../previewLoader.ts');
const { alarmePropsAus } = await import('../../compare/alarmePropsAus.ts');
const PreviewTab = (await import(pathToFileURL(PREVIEW_TAB).href)).default;
const AlarmeTab = (await import(pathToFileURL(ALARME_TAB).href)).default;

const BUENDEL = {
	subject: '[KHW 403] Morgen',
	email_html: '<html><body><p>Etappe 3</p></body></html>',
	sms: { text: 'KHW_03: N3 D11 W35 G52', char_count: 22 },
	telegram: { body: 'Etappe 3 — Wind 35 km/h' }
};

let buendel: Record<string, unknown> = BUENDEL;

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
		const daten = url.includes('/alert-preview') ? alarmAntwort : buendel;
		return Promise.resolve(
			new Response(JSON.stringify(daten), { status: 200, headers: { 'Content-Type': 'application/json' } })
		);
	};
});
after(() => {
	(globalThis as Knoten).fetch = alt.fetch;
	(globalThis as Knoten).window = alt.window;
});

const flush = () => new Promise((r) => setImmediate(r));
const tid = (t: string) => `data-testid="${t}"`;
const vorschauAbrufe = () => aufrufe.filter((a) => /\/api\/briefings\/[^/]+\/preview/.test(a.url));

/** Die EINE Einbettung `name` im Markup samt ihrer umschliessenden Bloecke. */
function einbettungMitVorfahren(ast: Knoten, name: string): { knoten: Knoten; vorfahren: Knoten[] } {
	const treffer: { knoten: Knoten; vorfahren: Knoten[] }[] = [];
	function lauf(n: unknown, kette: Knoten[]): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach((k) => lauf(k, kette));
		const k = n as Knoten;
		if (k.type === 'Component' && k.name === name) treffer.push({ knoten: k, vorfahren: kette });
		const weiter = typeof k.type === 'string' ? [...kette, k] : kette;
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key], weiter);
	}
	lauf(ast.fragment, []);
	assert.equal(treffer.length, 1, `erwartet genau eine <${name}>-Einbettung, gefunden ${treffer.length}`);
	return treffer[0];
}

/** Wert eines Attributs an einer Einbettung: Ausdruck ausgewertet, statischer Text als String. */
function attribut(einbettung: Knoten, quelle: string, name: string, u: Knoten): unknown {
	const a = ((einbettung.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	assert.ok(a, `Attribut ${name} fehlt an <${einbettung.name}>`);
	if (a!.value === true) return true;
	if (a!.value?.type === 'ExpressionTag') return werte(ohneTypen(quelle, a!.value.expression), u);
	const teile = (Array.isArray(a!.value) ? a!.value : [a!.value]) as Knoten[];
	return teile.map((t) => (t.type === 'Text' ? t.data : werte(ohneTypen(quelle, t.expression), u))).join('');
}

/** Alle Props einer Einbettung, ausgewertet gegen die Hub-Umgebung. */
function propsVon(einbettung: Knoten, quelle: string, u: Knoten): Record<string, unknown> {
	const p: Record<string, unknown> = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type === 'Attribute') p[a.name] = attribut(einbettung, quelle, a.name, u);
	}
	return p;
}

/** Die `onMount(...)`-Rueckrufe eines Instanz-Skripts, gegen `u` registriert (nicht ausgefuehrt). */
function onMountVon(ast: Knoten, quelle: string, u: Knoten): Array<() => unknown> {
	const gesammelt: Array<() => unknown> = [];
	u.onMount = (fn: () => unknown) => gesammelt.push(fn);
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		const c = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (c?.type === 'CallExpression' && c.callee?.type === 'Identifier' && c.callee.name === 'onMount') {
			werte(ohneTypen(quelle, c), u);
		}
	}
	assert.ok(gesammelt.length > 0, 'Messaufbau: PreviewTab registriert keinen onMount-Rueckruf');
	return gesammelt;
}

/** Echter Lader, geladen, Kanal gewaehlt — fuer das SSR-Rendern des echten PreviewTab. */
async function geladen(kind: 'route' | 'vergleich', channel: string) {
	const l = createPreviewLoader({ kind, id: kind === 'route' ? 't-1' : 'cp-1' });
	await l.load();
	l.setChannel(channel as 'sms');
	return l;
}

function trip(id: string, rc: Record<string, unknown>): Knoten {
	return { id, name: 'KHW 403', stages: [], alert_rules: [], display_config: {}, report_config: rc };
}

async function tripHub(t: Knoten) {
	const saat = { trip: t, initialTab: 'vorschau', badges: {}, goto: () => Promise.resolve(), page: { url: new URL('http://localhost/trips/x') } };
	const { ast, quelle, u } = await umgebungFuer(TRIP_HUB, saat, { jsAlsTs: true });
	return { ast, quelle, u };
}

async function vergleichHub(preset: Knoten) {
	const saat = { preset, locations: [], orteCount: 3, initialTab: 'vorschau', goto: () => Promise.resolve(), page: { url: new URL('http://localhost/compare/x') } };
	const { ast, quelle, u } = await umgebungFuer(VERGLEICH_HUB, saat, { jsAlsTs: true });
	return { ast, quelle, u };
}

// ── F001 / AC-9: genau EIN Abruf beim Einhaengen, keiner vorher ──────────────
describe('F001 (AC-9): PreviewTab laedt beim Einhaengen genau einmal — am echten onMount', () => {
	for (const kind of ['route', 'vergleich'] as const) {
		test(`${kind}: Instanz anlegen ruft nichts ab, onMount ruft genau einmal ab, der Zustand kommt an`, async () => {
			aufrufe = [];
			const saat = { context: kind, id: `e-${kind}`, loaderProp: undefined, premiumSms: false, untrack: (f: () => unknown) => f() };
			const { ast, quelle, u } = await umgebungFuer(PREVIEW_TAB, saat, { jsAlsTs: true });
			assert.equal(typeof u.loader?.load, 'function', 'Messaufbau: PreviewTab legt keinen Lader an');
			const mounts = onMountVon(ast, quelle, u);
			await flush();
			assert.equal(vorschauAbrufe().length, 0, 'schon das Anlegen des Reiters hat abgerufen (AC-9: kein Laden vor dem Oeffnen)');
			const abbau = mounts.map((fn) => fn());
			await flush();
			await flush();
			assert.equal(vorschauAbrufe().length, 1, `onMount muss genau EINEN Abruf ausloesen, waren ${vorschauAbrufe().length}`);
			assert.equal(new URL(vorschauAbrufe()[0].url, 'http://l').searchParams.get('kind'), kind);
			assert.equal(u.s.status, 'ready', 'der Reiter sieht den geladenen Zustand nicht (subscribe fehlt)');
			for (const ab of abbau) if (typeof ab === 'function') ab();
		});
	}
});

// ── F002 / AC-15: SMS-Budget je Kontext ─────────────────────────────────────
describe('F002: SMS-Zeichenbudget — Vergleich 153, Trip 160', () => {
	for (const [kind, budget] of [['vergleich', 153], ['route', 160]] as const) {
		test(`${kind}: Zaehler zeigt „N/${budget}"`, async () => {
			const html = render(PreviewTab, { props: { context: kind, id: 'x', loader: await geladen(kind, 'sms') } }).body;
			const m = html.match(/data-testid="sms-char-count"[^>]*>([^<]*)</);
			assert.ok(m, 'sms-char-count fehlt');
			assert.equal(m![1].trim(), `${BUENDEL.sms.char_count}/${budget}`);
		});
	}
});

// ── F004: Verdrahtung der Hubs (Premium-SMS, Kanalliste, {#key}) ────────────
async function vorschauProps(hub: 'trip' | 'vergleich', eintrag: Knoten) {
	const { ast, quelle, u } = hub === 'trip' ? await tripHub(eintrag) : await vergleichHub(eintrag);
	const { knoten, vorfahren } = einbettungMitVorfahren(ast, 'PreviewTab');
	const key = [...vorfahren].reverse().find((v) => v.type === 'KeyBlock');
	return { props: propsVon(knoten, quelle, u), key: key ? werte(ohneTypen(quelle, key.expression), u) : undefined };
}

async function renderMit(props: Record<string, unknown>, channel: string): Promise<string> {
	const kind = props.context as 'route' | 'vergleich';
	return render(PreviewTab, { props: { ...props, loader: await geladen(kind, channel) } }).body;
}

const PREMIUM_HINWEIS = tid('compare-preview-premium-sms-note');
const NICHT_KONFIGURIERT = tid('preview-channel-not-configured');

describe('F004: TripTabs reicht Premium-SMS und Kanaele aus report_config an den Vorschau-Reiter', () => {
	for (const an of [true, false]) {
		test(`send_premium_sms=${an} ⇒ Premium-SMS-Hinweis ${an ? 'sichtbar' : 'weg'}`, async () => {
			const { props } = await vorschauProps('trip', trip('t-1', { send_sms: true, send_premium_sms: an }));
			assert.equal(props.context, 'route');
			const html = await renderMit(props, 'sms');
			assert.equal(html.includes(PREMIUM_HINWEIS), an);
		});
		test(`send_telegram=${an} ⇒ Telegram ${an ? 'konfiguriert' : 'als nicht konfiguriert markiert'}`, async () => {
			const { props } = await vorschauProps('trip', trip('t-1', { send_telegram: an }));
			const html = await renderMit(props, 'telegram');
			assert.equal(html.includes(NICHT_KONFIGURIERT), !an);
		});
	}
	test('{#key}: der Reiter haengt an der Trip-ID (andere ID ⇒ neue Instanz ⇒ neuer Lader)', async () => {
		const a = await vorschauProps('trip', trip('t-a', {}));
		const b = await vorschauProps('trip', trip('t-b', {}));
		assert.equal(a.key, 't-a', 'PreviewTab steht nicht unter {#key trip.id}');
		assert.equal(b.key, 't-b');
		assert.equal(a.props.id, 't-a');
	});
});

describe('F004: CompareTabs reicht Premium-SMS und Kanaele aus dem Vergleich an den Vorschau-Reiter', () => {
	for (const an of [true, false]) {
		test(`send_premium_sms=${an} ⇒ Premium-SMS-Hinweis ${an ? 'sichtbar' : 'weg'}`, async () => {
			const { props } = await vorschauProps('vergleich', { ...vollerVergleich('cp-1'), send_sms: true, send_premium_sms: an });
			assert.equal(props.context, 'vergleich');
			const html = await renderMit(props, 'sms');
			assert.equal(html.includes(PREMIUM_HINWEIS), an);
		});
		test(`send_telegram=${an} ⇒ Telegram ${an ? 'konfiguriert' : 'als nicht konfiguriert markiert'}`, async () => {
			const { props } = await vorschauProps('vergleich', { ...vollerVergleich('cp-1'), send_telegram: an });
			const html = await renderMit(props, 'telegram');
			assert.equal(html.includes(NICHT_KONFIGURIERT), !an);
		});
	}
	test('{#key}: der Reiter haengt an der Vergleichs-ID', async () => {
		const a = await vorschauProps('vergleich', vollerVergleich('cp-a'));
		const b = await vorschauProps('vergleich', vollerVergleich('cp-b'));
		assert.equal(a.key, 'cp-a', 'PreviewTab steht nicht unter {#key preset.id}');
		assert.equal(b.key, 'cp-b');
	});
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

// ── Telegram-Blasen: bubbles = mehrere Nachrichten = mehrere Blasen ────────
describe('Telegram-Vorschau: je Nachricht eine Chat-Blase', () => {
	async function blasen(telegram: Record<string, unknown>): Promise<string[]> {
		buendel = { ...BUENDEL, telegram };
		try {
			const html = render(PreviewTab, { props: { context: 'route', id: 'x', loader: await geladen('route', 'telegram') } }).body;
			return [...html.matchAll(/data-testid="compare-preview-telegram-text"[^>]*>([^<]*)</g)].map((m) => m[1]);
		} finally {
			buendel = BUENDEL;
		}
	}

	test('bubbles [a, b] ⇒ zwei Blasen mit genau diesen Texten', async () => {
		assert.deepEqual(await blasen({ body: 'a\n---\nb', bubbles: ['a', 'b'] }), ['a', 'b']);
	});

	test('ohne bubbles ⇒ eine Blase mit body', async () => {
		assert.deepEqual(await blasen({ body: 'nur eine' }), ['nur eine']);
	});
});
