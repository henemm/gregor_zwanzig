// TDD RED — Issue #2283 Scheibe S5 (Epic #2345 P3): echte Alarm-Vorschau auch
// im Ortsvergleich.
// Spec: docs/specs/modules/shared_preview_tab.md — AC-20 (AlarmeTab
// context="vergleich" zeigt die echte AlertPreviewCard statt der statischen
// VTAlertSample; Body-Bau je kind, Ziel POST /api/briefings/{id}/alert-preview
// ?kind=…), AC-21 (VTAlertSample wird nicht mehr geladen; Zeitlimit 40 s —
// das Budget selbst bewacht frontend/src/lib/__tests__/apiZeitlimit.test.ts).
//
// ZIELSCHNITTSTELLE (von diesen Tests festgelegt):
//   * AlertPreviewCard-Wurzel `data-testid="alert-preview-card"` traegt
//     `data-kind="route|vergleich"` — so ist am gerenderten Markup sichtbar,
//     mit welcher Art der Organismus die Karte verdrahtet hat.
//   * `alertPreviewHelpers.ts` exportiert
//       buildAlertPreviewBody('route',     { rules, stages })
//         → identisch zu buildAlertPreviewPayload(rules, stages) (Delegate-Paritaet)
//       buildAlertPreviewBody('vergleich', { rules, locationIds })
//         → { changes: [{ location_id, metric, old_value, new_value, delta,
//                         threshold, severity, direction }, …] }
//           je aktiver Regel × je Ort, Werte wie im Trip-Koerper; KEINE Segment-Felder
//     Querschnitts-Vertrag: gleiche Koerperform wie die S4-Python-Tests
//     (tests/tdd/test_alert_preview_compare_paritaet.py Docstring,
//     tests/integration/test_alert_preview_kind_isolation.py `_compare_body`).
//     Woher AlarmeTab im Vergleich die `rules` bildet (aktive Metriken +
//     Stufen), entscheidet die Implementierung.
//   * Abruf: `alarmVorschau(kind, id, body)` aus api.ts (apiZeitlimit.test.ts).
//
// Testart: echtes serverseitiges Rendern des echten geteilten Organismus
// (svelte/server, Hooks frontend/test-svelte-ssr-hooks.mjs), Modul-Mitschnitt
// am echten Modulgraphen fuer AC-21. Keine Mocks, kein Dateitext.
// Grenze: der Klick „Vorschau laden" (Abruf, Anzeige der Antwort) laeuft nur
// im Browser — Live-Spec gegen Staging.
//
// RED HEUTE: vergleich rendert `versand-alert-sample` (VTAlertSample) statt
// `alert-preview-card`; `data-kind` und `buildAlertPreviewBody` fehlen.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/alertPreviewKind.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { MessageChannel } from 'node:worker_threads';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

// Pfadregel #1409: relativ zu DIESER Datei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const SHARED_TESTS = path.join(FRONTEND, 'src/lib/components/shared/__tests__');
const basis = pathToFileURL(FRONTEND + '/').href;

const geladen = new Set<string>();
const kanal = new MessageChannel();
kanal.port1.on('message', (u: string) => geladen.add(u));
kanal.port1.unref();

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(SHARED_TESTS, 'modulMitschnittHook.mjs')).href, {
	parentURL: basis,
	data: { port: kanal.port2 },
	transferList: [kanal.port2]
});

const { render } = await import('svelte/server');
const { alarmePropsAus } = await import('../../compare/alarmePropsAus.ts');
const { vollerVergleich } = await import(pathToFileURL(path.join(SHARED_TESTS, 'goMergeServerPruefstand.ts')).href);
const helpers: Record<string, unknown> = await import('../alertPreviewHelpers.ts');
const AlarmeTab = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href))
	.default;

const RULES = [
	{ id: 'r1', metric: 'wind_gust', threshold: 60, kind: 'absolute', severity: 'warning', enabled: true },
	{ id: 'r2', metric: 'precipitation_sum', threshold: 10, kind: 'absolute', severity: 'critical', enabled: true },
	{ id: 'r3', metric: 'temperature_min', threshold: 0, kind: 'absolute', severity: 'info', enabled: false }
];
const STAGES = [{ id: 'S1', name: 'Etappe 1', waypoints: [] }];

const TRIP = {
	id: 'trip-2283',
	name: 'KHW 403',
	stages: STAGES,
	alert_rules: RULES,
	display_config: {},
	report_config: { send_email: true, send_telegram: true, send_sms: true }
};

/** Wizard-Stellvertreter (Muster alarme_tab_premium_sms_channel_row_render.test.ts). */
function wizStub(overrides: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		officialWarningsEnabled: true,
		radarAlertEnabled: false,
		activeMetricKeys: null,
		metricAlertLevels: { wind_gust: 'standard' },
		channelThresholds: {},
		telegramStyle: 'rich',
		alertCooldownMinutes: 30,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00',
		...overrides
	};
}

function renderRoute(): string {
	return render(AlarmeTab, {
		props: {
			context: 'route',
			trip: TRIP,
			activeMetrics: ['wind_gust', 'precipitation_sum'],
			metricLevels: {},
			existingChannels: { email: true, telegram: true, sms: true, premium_sms: false },
			profileOverride: { premium_sms_allowed: true }
		}
	}).body;
}

function renderVergleich(): string {
	return render(AlarmeTab, {
		props: {
			context: 'vergleich',
			...alarmePropsAus(wizStub()),
			catalog: [],
			preset: vollerVergleich('cp-2283'),
			profileOverride: { premium_sms_allowed: true }
		}
	}).body;
}

const tid = (t: string) => `data-testid="${t}"`;

function karte(html: string): string {
	const m = html.match(/<[^>]*data-testid="alert-preview-card"[^>]*>/);
	assert.ok(m, `alert-preview-card fehlt im gerenderten Alarme-Reiter. Gefundene Beispiel-Karte: ${html.includes(tid('versand-alert-sample'))}`);
	return m![0];
}

describe('AC-20: AlarmeTab rendert in BEIDEN Kontexten die echte AlertPreviewCard', () => {
	test('vergleich: AlertPreviewCard (data-kind="vergleich") statt statischer VTAlertSample', () => {
		const html = renderVergleich();
		assert.equal(
			html.includes(tid('versand-alert-sample')),
			false,
			'vergleich zeigt noch die statische Beispielkarte VTAlertSample („kein Live-Preview-Datenmodell für Vergleiche")'
		);
		assert.match(karte(html), /data-kind="vergleich"/, 'die Karte im Vergleich ist nicht als kind=vergleich verdrahtet');
	});

	test('route: AlertPreviewCard (data-kind="route") bleibt — gleicher Baustein wie im Vergleich', () => {
		const html = renderRoute();
		assert.match(karte(html), /data-kind="route"/, 'die Karte im Trip ist nicht als kind=route verdrahtet');
		assert.equal(html.includes(tid('versand-alert-sample')), false);
	});
});

describe('AC-20: Body-Bau je kind — Segmente im Trip, Orte im Vergleich', () => {
	type Body = (kind: string, input: Record<string, unknown>) => Record<string, unknown>;
	function body(): Body {
		assert.equal(
			typeof helpers.buildAlertPreviewBody,
			'function',
			'alertPreviewHelpers.ts muss `buildAlertPreviewBody(kind, input)` exportieren (AC-20)'
		);
		return helpers.buildAlertPreviewBody as Body;
	}

	test('route: identisch zum bisherigen Trip-Koerper (Delegate-Paritaet)', () => {
		const alt = (helpers.buildAlertPreviewPayload as (r: unknown, s: unknown) => unknown)(RULES, STAGES);
		assert.deepEqual(body()('route', { rules: RULES, stages: STAGES }), alt);
	});

	test('vergleich: je aktiver Regel und je Ort eine Aenderung mit location_id, keine Segment-Felder', () => {
		const alt = (helpers.buildAlertPreviewPayload as (r: unknown, s: unknown) => { changes: Record<string, unknown>[] })(
			RULES,
			STAGES
		);
		const b = body()('vergleich', { rules: RULES, locationIds: ['loc-a', 'loc-b', 'loc-c'] }) as {
			changes: Record<string, unknown>[];
		};
		assert.deepEqual(Object.keys(b), ['changes'], 'Vergleichs-Koerper: genau `changes` (S4-Vertrag, kein segment_times)');
		// Erwartung: dieselben Werte wie im Trip (Metrik, Schwelle, Schwere, Richtung,
		// alt/neu/delta), nur Ort statt Segment — Reihenfolge Regel fuer Regel, je Ort.
		const erwartet = alt.changes.flatMap((c) =>
			['loc-a', 'loc-b', 'loc-c'].map((location_id) => {
				const { segment_id: _s, ...rest } = c;
				return { ...rest, location_id };
			})
		);
		assert.deepEqual(b.changes, erwartet);
		assert.equal(/segment/.test(JSON.stringify(b)), false, 'der Vergleichs-Koerper darf keine Segment-Semantik tragen');
	});

	test('vergleich ohne aktive Regel: leere Aenderungsliste (die Karte zeigt dann den Leerfall)', () => {
		const b = body()('vergleich', { rules: RULES.map((r) => ({ ...r, enabled: false })), locationIds: ['loc-a'] });
		assert.deepEqual(b, { changes: [] });
	});
});

describe('AC-21: VTAlertSample ist aus dem Alarme-Reiter verschwunden (Modulgraph)', () => {
	test('AlarmeTab laedt VTAlertSample nicht mehr', async () => {
		renderVergleich();
		await new Promise((r) => setTimeout(r, 50));
		assert.ok(
			[...geladen].some((u) => u.endsWith('/shared/AlarmeTab.svelte')),
			'Messaufbau: der Modul-Mitschnitt hat AlarmeTab nicht gesehen'
		);
		const vt = [...geladen].filter((u) => /\/VTAlertSample\.svelte$/.test(u));
		assert.deepEqual(vt, [], 'AlarmeTab importiert noch VTAlertSample (AC-21: entfernt oder ohne Verwendung gelöscht)');
	});
});
