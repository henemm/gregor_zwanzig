// TDD RED — Issue #3333 (Teil D2 von #3307, Epic #3122): jede Alarm-Einstellung hat beim Ortsvergleich-Anlegen
// genau eine Bedienstelle. Spec docs/specs/modules/feat_3333_zustellung_anlegen_orte.md, Test Plan Nr. 5 (AC-10).
// Pendant zu alarme_tab_ohne_zustellung_3332.test.ts (D1, Trip).
//
// Im Orte-Anlegen besitzt der Reiter Zustellung Alarm-Kanäle (mit Dringlichkeit), Stille Stunden und Cooldown.
// Der Reiter Alarme blendet dort genau diese drei Abschnitte aus; amtliche Warnungen, Radar, Metrik-Alarmstufen
// und der Beispiel-Alarm bleiben. Im Hub (beide Kontexte) und im Trip-Anlegen bleibt alles wie nach D1.
//
// FESTGELEGTE SCHNITTSTELLE (shared/alarme-tab/alarmeTabSections.ts):
//   ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT = { route: true, vergleich: true }
//   AlarmeTab.svelte reicht `createMode && ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT[context]` als ohneZustellung.
//
// Gemessen an der Tabelle UND am echten serverseitigen Render des Reiters (svelte/server), dort, wo die
// Abschnitte als `alarme-section-<id>` erscheinen — kein Quelltext-Grep.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_tab_ohne_zustellung_3333.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { alarmeTabSections, ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT } from '../alarme-tab/alarmeTabSections.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const AlarmeTab = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href)).default;

const ZUSTELLUNG = ['channels', 'cooldown', 'quiet-hours'];
// #3458: Abschnitt 'sample' (Beispiel-Warnung) entfernt — bleibt nicht mehr, fehlt.
const BLEIBEN_VERGLEICH = ['official-warnings', 'radar', 'metric-levels'];
const TRIP = { id: '__new__', name: 'Neu-3333', stages: [], alert_rules: [], display_config: {}, report_config: undefined };

function wizStub(): Record<string, unknown> {
	return {
		officialWarningsEnabled: true, radarAlertEnabled: true, activeMetricKeys: null, metricAlertLevels: {},
		sendTelegram: true, sendSms: false, sendPremiumSms: false, channelThresholds: {}, telegramStyle: 'rich',
		alertCooldownMinutes: 30, alertQuietFrom: '22:00', alertQuietTo: '07:00'
	};
}
function abschnitte(html: string): string[] {
	return [...html.matchAll(/data-testid="alarme-section-([a-z-]+)"/g)].map((m) => m[1]);
}
function renderVergleich(createMode: boolean): string {
	return render(AlarmeTab, {
		props: { context: 'vergleich', ...alarmePropsAus(wizStub() as never), createMode, catalog: [], profileOverride: { premium_sms_allowed: true } }
	}).body;
}
function renderRoute(createMode: boolean): string {
	return render(AlarmeTab, {
		props: { context: 'route', trip: TRIP, createMode, activeMetrics: [], metricLevels: {}, profileOverride: { premium_sms_allowed: true } }
	}).body;
}

describe('#3333 Test 5 (AC-10): Tabelle und Abschnittsliste', () => {
	test('ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT: im Orte-Anlegen ausgelagert, Trip unverändert', () => {
		assert.deepEqual({ ...ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT }, { route: true, vergleich: true });
	});

	test('vergleich, ohneZustellung: channels, cooldown, quiet-hours fehlen; Radar und Rest in unveränderter Reihenfolge', () => {
		const ohne = alarmeTabSections('vergleich', ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT.vergleich);
		assert.deepEqual(ohne, BLEIBEN_VERGLEICH, `Orte-Anlegen: ${JSON.stringify(ohne)}`);
	});

	test('Hub-Listen (ohne ohneZustellung) unverändert', () => {
		assert.deepEqual(alarmeTabSections('vergleich'), ['official-warnings', 'radar', 'metric-levels', 'channels', 'cooldown', 'quiet-hours']);
		assert.deepEqual(alarmeTabSections('route'), ['official-warnings', 'metric-levels', 'channels', 'cooldown', 'quiet-hours']);
	});
});

describe('#3333 Test 5 (AC-10): Wirkort — der gerenderte Reiter Alarme', () => {
	test('Orte-Anlegen (vergleich, createMode): keine Abschnitte Kanäle, Cooldown, Stille Stunden; Warnungen, Radar, Metrik-Stufen bleiben, Beispiel fehlt (#3458)', () => {
		const html = renderVergleich(true);
		const ids = abschnitte(html);
		assert.ok(ids.length > 0, 'Messaufbau: keine Abschnitte gerendert');
		for (const s of ZUSTELLUNG) assert.ok(!ids.includes(s), `Orte-Anlegen: Abschnitt "${s}" hat eine zweite Bedienstelle (Reiter Zustellung besitzt ihn) — gerendert: ${JSON.stringify(ids)}`);
		for (const s of BLEIBEN_VERGLEICH) assert.ok(ids.includes(s), `Orte-Anlegen: Abschnitt "${s}" fehlt (keine andere Bedienstelle)`);
		assert.ok(!ids.includes('sample'), 'Orte-Anlegen: Abschnitt "sample" (Beispiel-Warnung) noch da (#3458)');
		assert.equal((html.match(/data-testid="alert-channel-threshold-telegram-HIGH"/g) ?? []).length, 0, 'alte Dringlichkeit-Wahl im Orte-Anlegen');
	});

	test('Orts-Hub (vergleich, ohne createMode): Liste vollständig', () => {
		assert.deepEqual(abschnitte(renderVergleich(false)), alarmeTabSections('vergleich'));
	});

	test('Trip-Anlegen und Trip-Hub unverändert wie nach D1 (AC-15)', () => {
		assert.deepEqual(abschnitte(renderRoute(true)), ['official-warnings', 'metric-levels']);
		assert.deepEqual(abschnitte(renderRoute(false)), alarmeTabSections('route'));
	});
});
