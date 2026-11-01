// TDD RED — Issue #2682 (Epic #2345): Trip-Uebersicht ohne Attrappen und mit
// der geteilten Kennzahlen-Leiste.
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
//   Entscheidung 1/2/4/7, AC-1, AC-5, AC-8, AC-9, AC-10, AC-11, AC-15
//
// Echter SSR-Render (svelte/server, kein DOM, kein Mock):
//   (a) trip-detail/HubOverview.svelte — Karte „Briefings laufen": je Zeile die
//       ECHTEN Kanaele statt fest ['email','telegram'] / ['email'] / ['telegram'];
//       Karte „Alerts (letzte 7 Tage)" samt „Alle Alerts →" entfaellt.
//   (b) trip-detail/ChannelDot.svelte — vierter Kanal Premium-SMS.
//   (c) shared/hub-uebersicht/HubUebersicht.svelte mit context="route" — das, was
//       TripTabs kuenftig einbindet. JE TEST dynamisch importiert, damit in RED
//       jeder Fall mit eigener Meldung scheitert.
//
// Kanal-Erkennung: ChannelDot rendert `title={kind}`. Gelesen werden die
// title-Attribute JE ReportLine-Zeile, normalisiert (klein, ohne -/_), damit
// 'premium_sms' (Vokabular von alert_channels / Briefing-Log) und eine
// sprechende Beschriftung „Premium-SMS" gleich zaehlen. VERTRAG: ChannelDot
// behaelt ein title-Attribut je Kanal.
//
// VERTRAG HubUebersicht (route), Props:
//   context: 'route' | 'vergleich'; trip?: Trip (route); preset?, locations? (vergleich);
//   onJump?: (tab: string, anchor?: 'versand') => void; children?: Snippet (Hauptflaeche).
//   Wert-Knoten tragen die testids aus dem Modell (hubUebersichtModell.ts):
//   hub-uebersicht-stat-kanaele, hub-uebersicht-stat-zuletzt-raus, Knopf hub-uebersicht-versand-edit.
//   Im SSR laeuft kein $effect: „Zuletzt raus" ist „—" (AC-7, nie erfunden),
//   isMobileViewport ist false ⇒ Desktop-Zweig mit fuenf Kennzahlen.
//
// Kanal-Flags stehen NUR in report_config; die flachen Felder trip.send_*
// tragen bewusst das GEGENTEIL (types.ts: report_config ist die einzige Wahrheit).
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/hub_uebersicht_trip_ssr.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'Europe/Berlin';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-detail -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const COMPONENTS = path.resolve(HERE, '../..');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/__tests__/svelteTsModulHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const HubOverview = (await import(pathToFileURL(path.join(COMPONENTS, 'trip-detail/HubOverview.svelte')).href)).default;
const ChannelDot = (await import(pathToFileURL(path.join(COMPONENTS, 'trip-detail/ChannelDot.svelte')).href)).default;
const TripStatusBadge = (await import(pathToFileURL(path.join(COMPONENTS, 'trip-detail/TripStatusBadge.svelte')).href)).default;
const BAUSTEIN = path.join(COMPONENTS, 'shared/hub-uebersicht/HubUebersicht.svelte');

// ── Fixtures ────────────────────────────────────────────────────────────────

const ETAPPEN_GEPLANT = [
	{ id: 's1', name: 'E1', date: '2099-07-01', waypoints: [] },
	{ id: 's2', name: 'E2', date: '2099-07-02', waypoints: [] }
];
const ETAPPEN_AKTIV = [
	{ id: 's1', name: 'E1', date: '2000-01-01', waypoints: [] },
	{ id: 's2', name: 'E2', date: '2099-12-31', waypoints: [] }
];
const ETAPPEN_ENTWURF = [{ id: 's1', name: 'E1', waypoints: [] }];

function trip(rc: Record<string, unknown>, extra: Record<string, unknown> = {}) {
	const gegenteil = (k: string) => (k in rc ? !rc[k] : undefined);
	return {
		id: 't-2682',
		name: 'Testtrip',
		stages: ETAPPEN_GEPLANT,
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00',
			...rc
		},
		send_email: gegenteil('send_email'),
		send_telegram: gegenteil('send_telegram'),
		send_sms: gegenteil('send_sms'),
		send_premium_sms: gegenteil('send_premium_sms'),
		display_config: {},
		...extra
	};
}

// ── Hilfen ──────────────────────────────────────────────────────────────────

const ohneMarker = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const reinerText = (html: string) => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
const kanalSchluessel = (t: string) => t.toLowerCase().replace(/[^a-z]/g, '');

function hubOverview(t: unknown): string {
	return ohneMarker(render(HubOverview, { props: { trip: t } }).body);
}

/** Kanaele (normalisierte ChannelDot-titles) der ReportLine-Zeile mit Etikett `label`. */
function kanaeleDerZeile(html: string, label: 'Morgen-Briefing' | 'Abend-Briefing' | 'Alert-Trigger'): string[] {
	const etiketten = ['Morgen-Briefing', 'Abend-Briefing', 'Alert-Trigger'];
	const a = html.indexOf(`>${label}</span>`);
	assert.notEqual(a, -1, `Messaufbau: Zeile „${label}" fehlt in „Briefings laufen"`);
	const enden = etiketten
		.filter((e) => e !== label)
		.map((e) => html.indexOf(`>${e}</span>`, a + 1))
		.filter((i) => i > a);
	const zeitplan = html.indexOf('Zeitplan bearbeiten', a);
	if (zeitplan > a) enden.push(zeitplan);
	const ende = enden.length ? Math.min(...enden) : html.length;
	return [...html.slice(a, ende).matchAll(/title="([^"]*)"/g)].map((m) => kanalSchluessel(m[1])).sort();
}

async function ladeBaustein(): Promise<any> {
	assert.ok(
		existsSync(BAUSTEIN),
		'shared/hub-uebersicht/HubUebersicht.svelte fehlt (RED) — Spec „Affected Files": geteilter Baustein context="route"|"vergleich"'
	);
	return (await import(pathToFileURL(BAUSTEIN).href)).default;
}

async function uebersichtRoute(t: unknown): Promise<string> {
	const Baustein = await ladeBaustein();
	return ohneMarker(render(Baustein, { props: { context: 'route', trip: t } }).body);
}

/** Inhalt des Elements mit data-testid (Tiefe ueber denselben Tag-Namen). */
function elementMitTestid(html: string, testid: string): string {
	const re = new RegExp(`<([a-z]+)\\b[^>]*data-testid="${testid}"[^>]*>`);
	const m = re.exec(html);
	assert.ok(m, `testid „${testid}" fehlt im gerenderten HTML`);
	const name = m![1];
	const tag = new RegExp(`<(/?)${name}\\b[^>]*>`, 'g');
	tag.lastIndex = m!.index;
	let tiefe = 0;
	let t: RegExpExecArray | null;
	while ((t = tag.exec(html))) {
		tiefe += t[1] === '/' ? -1 : 1;
		if (tiefe === 0) return html.slice(m!.index, t.index + t[0].length);
	}
	return html.slice(m!.index);
}

// ── (a) HubOverview: Karte „Alerts" entfaellt (AC-11) ───────────────────────

describe('AC-11: keine Alerts-Attrappe in der Trip-Uebersicht', () => {
	test('kein Festtext „Keine aktuellen Alerts.", keine Karte „Alerts (letzte 7 Tage)"', () => {
		const t = reinerText(hubOverview(trip({})));
		assert.ok(!t.includes('Keine aktuellen Alerts.'), 'Festtext ohne Datenquelle noch sichtbar');
		assert.ok(!t.includes('Alerts (letzte 7 Tage)'), 'Karte „Alerts (letzte 7 Tage)" noch sichtbar');
	});

	test('kein Knopf „Alle Alerts →"', () => {
		const t = reinerText(hubOverview(trip({})));
		assert.ok(!t.includes('Alle Alerts'), 'Knopf „Alle Alerts →" noch sichtbar');
	});
});

// ── (a) HubOverview: echte Briefing-Kanaele je Zeile (AC-9, AC-15) ──────────

describe('AC-9: „Briefings laufen" zeigt die tatsaechlich eingestellten Briefing-Kanaele', () => {
	test('E-Mail + SMS + Premium-SMS (ohne Telegram) ⇒ Morgen- und Abend-Zeile genau diese drei', () => {
		const html = hubOverview(trip({ send_email: true, send_telegram: false, send_sms: true, send_premium_sms: true }));
		const erwartet = ['email', 'premiumsms', 'sms'];
		assert.deepEqual(kanaeleDerZeile(html, 'Morgen-Briefing'), erwartet, 'Morgen-Zeile: fest eingetragene Kanaele');
		assert.deepEqual(kanaeleDerZeile(html, 'Abend-Briefing'), erwartet, 'Abend-Zeile: fest eingetragene Kanaele');
	});

	test('alle vier Kanaele ⇒ alle vier je Zeile', () => {
		const html = hubOverview(trip({ send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true }));
		const erwartet = ['email', 'premiumsms', 'sms', 'telegram'];
		assert.deepEqual(kanaeleDerZeile(html, 'Morgen-Briefing'), erwartet);
		assert.deepEqual(kanaeleDerZeile(html, 'Abend-Briefing'), erwartet);
	});

	test('nur Premium-SMS (send_email=false) ⇒ nur Premium-SMS', () => {
		const html = hubOverview(trip({ send_email: false, send_telegram: false, send_sms: false, send_premium_sms: true }));
		assert.deepEqual(kanaeleDerZeile(html, 'Morgen-Briefing'), ['premiumsms']);
		assert.deepEqual(kanaeleDerZeile(html, 'Abend-Briefing'), ['premiumsms']);
	});

	test('send_email fehlt ⇒ E-Mail gilt als aktiv', () => {
		const html = hubOverview(trip({ send_telegram: true }));
		assert.deepEqual(kanaeleDerZeile(html, 'Morgen-Briefing'), ['email', 'telegram']);
	});

	test('AC-15: andere Eingabe ⇒ andere Anzeige (Mutation Festwert ⇒ rot)', () => {
		const a = kanaeleDerZeile(hubOverview(trip({ send_email: true, send_telegram: false })), 'Morgen-Briefing');
		const b = kanaeleDerZeile(hubOverview(trip({ send_email: false, send_sms: true })), 'Morgen-Briefing');
		assert.notDeepEqual(a, b, `Anzeige folgt der Einstellung nicht: ${JSON.stringify(a)} vs ${JSON.stringify(b)}`);
	});
});

// ── (a) HubOverview: Alert-Trigger folgt alert_channels (AC-10) ─────────────

describe('AC-10: Zeile „Alert-Trigger" zeigt die Alert-Kanaele des Trips', () => {
	test('alert_channels gesetzt ⇒ genau diese (unabhaengig von den Briefing-Flags)', () => {
		const html = hubOverview(
			trip(
				{ send_email: true, send_telegram: true, send_sms: false, send_premium_sms: false },
				{ alert_channels: { email: false, telegram: false, sms: true, premium_sms: true } }
			)
		);
		assert.deepEqual(kanaeleDerZeile(html, 'Alert-Trigger'), ['premiumsms', 'sms']);
	});

	test('alert_channels fehlt (Altbestand) ⇒ die Briefing-Kanaele', () => {
		const html = hubOverview(trip({ send_email: true, send_telegram: false, send_sms: true, send_premium_sms: false }));
		assert.deepEqual(kanaeleDerZeile(html, 'Alert-Trigger'), ['email', 'sms']);
	});

	test('alert_channels ohne Schluessel premium_sms ⇒ Premium-SMS AUS, auch wenn das Briefing-Flag an ist (types.ts D4)', () => {
		const html = hubOverview(
			trip({ send_premium_sms: true }, { alert_channels: { email: true, telegram: true, sms: false } })
		);
		assert.deepEqual(kanaeleDerZeile(html, 'Alert-Trigger'), ['email', 'telegram']);
	});
});

// ── (a) HubOverview: Alert-Trigger nur aktiv mit Wetter-Alarm-Quelle (AC-15) ─
//
// ReportLine zeigt „aktiv" ueber die Punktfarbe: aktive Alarm-Zeile var(--g-accent),
// inaktiv var(--g-rule). Gelesen wird der background des Punkts vor dem Etikett.

function punktfarbeDerZeile(html: string, label: 'Morgen-Briefing' | 'Abend-Briefing' | 'Alert-Trigger'): string {
	const a = html.indexOf(`>${label}</span>`);
	assert.notEqual(a, -1, `Messaufbau: Zeile „${label}" fehlt in „Briefings laufen"`);
	const davor = html.slice(0, a);
	const b = davor.lastIndexOf('background:');
	assert.notEqual(b, -1, `Messaufbau: kein Punkt vor „${label}"`);
	return davor.slice(b + 'background:'.length).split(';')[0].trim();
}

describe('AC-15: Zeile „Alert-Trigger" ist nicht fest aktiv', () => {
	test('Trip ohne jede Wetter-Alarm-Quelle ⇒ Alarm-Zeile inaktiv (var(--g-rule))', () => {
		const html = hubOverview(trip({ alert_on_changes: false }, { alert_rules: [], display_config: {} }));
		assert.equal(punktfarbeDerZeile(html, 'Alert-Trigger'), 'var(--g-rule)', 'Alarm-Zeile zeigt „aktiv" ohne Datenquelle');
	});

	test('Trip mit alert_preset ⇒ Alarm-Zeile aktiv (var(--g-accent))', () => {
		const html = hubOverview(trip({ alert_on_changes: false }, { display_config: { alert_preset: 'standard' } }));
		assert.equal(punktfarbeDerZeile(html, 'Alert-Trigger'), 'var(--g-accent)');
	});
});

// ── (b) ChannelDot: vierter Kanal ───────────────────────────────────────────

describe('ChannelDot kennt Premium-SMS (ADR-0095: vier Kanaele gleichrangig)', () => {
	const symbol = (kind: string) => reinerText(ohneMarker(render(ChannelDot, { props: { kind } }).body));

	test('premium_sms wird gerendert — nicht der Rueckfall „?"', () => {
		const s = symbol('premium_sms');
		assert.ok(s.length > 0, 'leeres Symbol');
		assert.notEqual(s, '?', 'Premium-SMS faellt auf das Unbekannt-Symbol zurueck');
	});

	test('premium_sms unterscheidet sich vom SMS-Symbol', () => {
		assert.notEqual(symbol('premium_sms'), symbol('sms'), 'Premium-SMS und SMS sind nicht unterscheidbar');
	});

	test('title nennt den Kanal (Kanal-Erkennung der Uebersicht)', () => {
		const html = ohneMarker(render(ChannelDot, { props: { kind: 'premium_sms' } }).body);
		const m = /title="([^"]*)"/.exec(html);
		assert.ok(m, 'ChannelDot traegt kein title');
		assert.equal(kanalSchluessel(m![1]), 'premiumsms');
	});
});

// ── (c) HubUebersicht context="route" ───────────────────────────────────────

describe('AC-1/AC-5/AC-8/AC-9: Trip-Uebersicht ueber den geteilten Baustein', () => {
	test('AC-1: Desktop-Leiste mit fuenf Kennzahlen (Status, Naechster Versand, Briefings, Zuletzt raus, Kanaele)', async () => {
		const t = reinerText(await uebersichtRoute(trip({})));
		const reihenfolge = ['Status', 'Nächster Versand', 'Briefings', 'Zuletzt raus', 'Kanäle'].map((l) => t.indexOf(l));
		assert.ok(reihenfolge.every((i) => i >= 0), `Kennzahl fehlt: ${t}`);
		assert.deepEqual([...reihenfolge].sort((a, b) => a - b), reihenfolge, `Reihenfolge falsch: ${t}`);
	});

	test('stabile testids mit Praefix hub-uebersicht-*; kein compare-* im Trip', async () => {
		const html = await uebersichtRoute(trip({}));
		for (const id of ['hub-uebersicht-stat-kanaele', 'hub-uebersicht-stat-zuletzt-raus', 'hub-uebersicht-versand-edit']) {
			assert.equal(html.split(`data-testid="${id}"`).length - 1, 1, `testid ${id} nicht genau einmal`);
		}
		assert.ok(!/data-testid="compare-/.test(html), 'Vergleichs-testid im Trip gerendert');
	});

	test('AC-9: Kanaele-Kennzahl nennt Premium-SMS neben E-Mail, folgt report_config', async () => {
		const mit = reinerText(elementMitTestid(await uebersichtRoute(trip({ send_premium_sms: true })), 'hub-uebersicht-stat-kanaele'));
		assert.match(mit, /Premium-SMS/, mit);
		assert.match(mit, /E-?Mail/i, mit);
		const ohne = reinerText(
			elementMitTestid(await uebersichtRoute(trip({ send_email: false, send_telegram: true })), 'hub-uebersicht-stat-kanaele')
		);
		assert.doesNotMatch(ohne, /E-?Mail/i, `fest eingetragene E-Mail: ${ohne}`);
		assert.match(ohne, /Telegram/, ohne);
	});

	test('AC-7: im SSR (Historie nicht geladen) zeigt „Zuletzt raus" „—", nie ein Datum', async () => {
		const z = reinerText(elementMitTestid(await uebersichtRoute(trip({})), 'hub-uebersicht-stat-zuletzt-raus'));
		assert.equal(z, '—');
	});

	for (const [fall, stages] of [
		['geplant', ETAPPEN_GEPLANT],
		['aktiv', ETAPPEN_AKTIV],
		['entwurf', ETAPPEN_ENTWURF]
	] as const) {
		test(`AC-5: Status-Kennzahl (${fall}) = Text des Status-Badges im Trip-Kopf`, async () => {
			const t = trip({}, { stages });
			const badge = reinerText(ohneMarker(render(TripStatusBadge, { props: { trip: t } }).body));
			assert.ok(badge.length > 0, 'Messaufbau: Badge leer');
			const text = reinerText(await uebersichtRoute(t));
			assert.ok(
				text.includes(`Status ${badge} Nächster Versand`),
				`Status-Kennzahl ≠ Badge „${badge}": ${text.slice(0, 200)}`
			);
		});
	}

	test('AC-8: Entwurf ⇒ Versand-Karte „Noch nicht geplant", Knopf „Bearbeiten →"', async () => {
		const html = await uebersichtRoute(trip({}, { stages: ETAPPEN_ENTWURF }));
		const t = reinerText(html);
		assert.ok(t.includes('Noch nicht geplant'), t);
		assert.equal(reinerText(elementMitTestid(html, 'hub-uebersicht-versand-edit')), 'Bearbeiten →');
	});

	test('AC-8: geplanter Trip ⇒ Versand-Karte nennt die Briefing-Zeit, nicht „Noch nicht geplant"', async () => {
		const t = reinerText(await uebersichtRoute(trip({ morning_time: '09:00:00', evening_enabled: false })));
		assert.ok(!t.includes('Noch nicht geplant'), t);
		assert.match(t, /09:00/, t);
	});

	test('AC-11: Trip-Uebersicht (Baustein) nennt keine Alerts-Attrappe', async () => {
		const t = reinerText(await uebersichtRoute(trip({})));
		assert.ok(!t.includes('Keine aktuellen Alerts'), t);
		assert.ok(!t.includes('Alle Alerts'), t);
	});

	test('AC-13: Versand-Historie kind="route" unter der Hauptflaeche', async () => {
		const html = await uebersichtRoute(trip({}));
		assert.match(html, /data-testid="briefing-history"[^>]*data-kind="route"/);
	});
});
