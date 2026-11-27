// TDD RED — Issue #3332 (Teil D1 von #3307, Epic #3122): jede Alarm-Einstellung hat beim Trip-Anlegen
// genau eine Bedienstelle. Spec docs/specs/modules/feat_3332_zustellung_anlegen_trip.md, Test Plan Nr. 5 (AC-9).
//
// Im Trip-Anlegen besitzt der Reiter Zustellung Alarm-Kanäle (mit Dringlichkeit), Stille Stunden und Cooldown.
// Der Reiter Alarme blendet dort genau diese drei Abschnitte aus; amtliche Warnungen, Metrik-Alarmstufen und
// der Beispiel-Alarm bleiben. Im Hub bleibt die Liste vollständig; das Ortsvergleich-Anlegen folgt seit D2 (#3333).
//
// FESTGELEGTE SCHNITTSTELLE:
//   alarmeTabSections(context, ohneZustellung?: boolean): string[]   (shared/alarme-tab/alarmeTabSections.ts)
//     ohneZustellung = true lässt 'channels', 'cooldown', 'quiet-hours' weg; sonst unverändert.
//   AlarmeTab.svelte reicht `createMode && context === 'route'` als ohneZustellung an die Liste.
//
// Gemessen an der reinen Liste UND am echten serverseitigen Render des Reiters (svelte/server), dort, wo die
// Abschnitte als `alarme-section-<id>` erscheinen — kein Quelltext-Grep.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_tab_ohne_zustellung_3332.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { alarmeTabSections } from '../alarme-tab/alarmeTabSections.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const AlarmeTab = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href)).default;

const ZUSTELLUNG = ['channels', 'cooldown', 'quiet-hours'];
// #3458: Abschnitt 'sample' (Beispiel-Warnung) entfernt — bleibt nicht mehr, fehlt.
const BLEIBEN = ['official-warnings', 'metric-levels'];

const TRIP = { id: '__new__', name: 'Neu-3332', stages: [], alert_rules: [], display_config: {}, report_config: undefined };

function wizStub(): Record<string, unknown> {
	return {
		officialWarningsEnabled: true, radarAlertEnabled: false, activeMetricKeys: null, metricAlertLevels: {},
		sendTelegram: true, sendSms: false, sendPremiumSms: false, channelThresholds: {}, telegramStyle: 'rich',
		alertCooldownMinutes: 30, alertQuietFrom: '22:00', alertQuietTo: '07:00'
	};
}

function abschnitte(html: string): string[] {
	return [...html.matchAll(/data-testid="alarme-section-([a-z-]+)"/g)].map((m) => m[1]);
}
function renderRoute(createMode: boolean): string {
	return render(AlarmeTab, {
		props: { context: 'route', trip: TRIP, createMode, activeMetrics: [], metricLevels: {}, profileOverride: { premium_sms_allowed: true } }
	}).body;
}
function renderVergleich(createMode: boolean): string {
	return render(AlarmeTab, {
		props: { context: 'vergleich', ...alarmePropsAus(wizStub() as never), createMode, catalog: [], profileOverride: { premium_sms_allowed: true } }
	}).body;
}

describe('#3332 Test 5 (AC-9): Abschnittsliste mit und ohne Zustellungs-Abschnitte', () => {
	test('route, ohneZustellung: channels, cooldown, quiet-hours fehlen; Rest in unveränderter Reihenfolge', () => {
		const mit = alarmeTabSections('route');
		const ohne = (alarmeTabSections as (c: 'route' | 'vergleich', o?: boolean) => string[])('route', true);
		assert.deepEqual(ohne, mit.filter((s) => !ZUSTELLUNG.includes(s)), `ohneZustellung liefert ${JSON.stringify(ohne)}`);
		assert.deepEqual(ohne, BLEIBEN);
	});

	test('ohne den Parameter bzw. mit false: Liste unverändert (Hub, Ortsvergleich)', () => {
		const f = alarmeTabSections as (c: 'route' | 'vergleich', o?: boolean) => string[];
		assert.deepEqual(f('route', false), ['official-warnings', 'metric-levels', 'channels', 'cooldown', 'quiet-hours']);
		assert.deepEqual(f('vergleich', false), ['official-warnings', 'radar', 'metric-levels', 'channels', 'cooldown', 'quiet-hours']);
		assert.deepEqual(f('route'), f('route', false));
	});
});

describe('#3332 Test 5 (AC-9): Wirkort — der gerenderte Reiter Alarme', () => {
	test('Trip-Anlegen (route, createMode): keine Abschnitte Kanäle, Cooldown, Stille Stunden; Warnungen und Metrik-Stufen bleiben', () => {
		const ids = abschnitte(renderRoute(true));
		assert.ok(ids.length > 0, 'Messaufbau: keine Abschnitte gerendert');
		for (const s of ZUSTELLUNG) assert.ok(!ids.includes(s), `Trip-Anlegen: Abschnitt "${s}" hat eine zweite Bedienstelle (Reiter Zustellung besitzt ihn) — gerendert: ${JSON.stringify(ids)}`);
		for (const s of BLEIBEN) assert.ok(ids.includes(s), `Trip-Anlegen: Abschnitt "${s}" fehlt`);
		assert.ok(!ids.includes('sample'), `Trip-Anlegen: Abschnitt "sample" (Beispiel-Warnung) noch da (#3458)`);
		assert.equal((renderRoute(true).match(/data-testid="alert-channel-threshold-telegram-HIGH"/g) ?? []).length, 0, 'alte Dringlichkeit-Wahl im Trip-Anlegen');
	});

	test('Trip-Hub (route, ohne createMode): Liste vollständig', () => {
		assert.deepEqual(abschnitte(renderRoute(false)), alarmeTabSections('route'));
	});

	// #3333 (D2, AC-10) löst die D1-Zusicherung „Ortsvergleich-Anlegen vollständig“ ab: dort blendet der Reiter
	// Alarme jetzt dieselben drei Abschnitte aus (Details: alarme_tab_ohne_zustellung_3333.test.ts).
	test('Ortsvergleich-Anlegen (vergleich, createMode): seit D2 (#3333) ohne Kanäle, Cooldown, Stille Stunden', () => {
		assert.deepEqual(abschnitte(renderVergleich(true)), alarmeTabSections('vergleich', true));
	});

	test('Ortsvergleich-Hub (vergleich, ohne createMode): Liste vollständig', () => {
		assert.deepEqual(abschnitte(renderVergleich(false)), alarmeTabSections('vergleich'));
	});
});
