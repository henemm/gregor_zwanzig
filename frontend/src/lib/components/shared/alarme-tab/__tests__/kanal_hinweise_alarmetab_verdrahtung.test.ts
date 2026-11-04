// #1895 S3b2 Fix-Loop 1 (Adversary F001): der Draht AlarmeTab → AlertMetricChannelsBlock für die
// Hinweise. Ausgewertet werden die ECHTEN Einbettungs-Ausdrücke `profil={…}` und `schwellen={…}`
// (svelteInstanzPruefstand, kein Quelltext-Grep); damit wird der Block per SSR gerendert.
// Spec alert_metric_channels.md AC-63, AC-67, AC-70, AC-73, AC-74.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { register } from 'node:module';
import { umgebungFuer, findeKomponenten, attributAusdruck, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TAB = join(HIER, '..', '..', 'AlarmeTab.svelte');
const BLOCK = join(HIER, '..', '..', '..', 'alerts-tab', 'AlertMetricChannelsBlock.svelte');
const FRONTEND = join(HIER, '..', '..', '..', '..', '..', '..');
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const Block = (await import(pathToFileURL(BLOCK).href)).default;

const TG = { email: false, telegram: true, sms: false, premium_sms: false };
const SCHLUESSEL = { keys: { thunder_level: ['thunder'] }, accepted: ['thunder'] };
const MIT_CHAT = { premium_sms_allowed: true, telegram_chat_id: '42' };
const OHNE_CHAT = { premium_sms_allowed: true, telegram_chat_id: '' };
const untrack = (fn: () => unknown) => fn();

const routeSaat = (over: Knoten) => ({
	// channelThresholds fehlt im Trip (lokaler Zustand aus existingChannelThresholds) ⇒ explizit undefined.
	context: 'route', trip: { id: 't-1', display_config: {} }, existingAlertMetricChannels: { thunder: TG }, channelThresholds: undefined,
	activeMetrics: ['thunder_level'], baueTripSpeicherung: () => async () => {}, saveController: { schedule: () => {} }, ...over
});
const vergleichSaat = (over: Knoten) => ({
	context: 'vergleich', trip: undefined, catalog: [], activeMetrics: ['thunder_level'],
	alertMetricChannels: { thunder: TG }, onAlertMetricChannelChange: () => {},
	channelThresholds: { email: 'LOW', telegram: 'LOW', sms: 'LOW', premium_sms: 'LOW' }, ...over
});

/** AlarmeTab mit Saat; rendert den Block mit den Props der EINEN echten Einbettung (eintraege fest TG). */
async function hinweiseAusTab(saat: Knoten): Promise<string> {
	const env = await umgebungFuer(TAB, { untrack, metricLevels: {}, existingChannels: null,
		existingChannelThresholds: null, createMode: undefined, activeMetricKeys: undefined, ...saat });
	const block = findeKomponenten(env.ast, 'AlertMetricChannelsBlock');
	assert.strictEqual(block.length, 1, 'AlarmeTab bettet den Block nicht genau einmal ein');
	const attr = (name: string) => {
		const a = attributAusdruck(block[0], env.quelle, name);
		assert.ok(a, `Einbettung reicht \`${name}\` nicht an den Block`);
		return werte(a, env.u);
	};
	const props = Object.fromEntries(['aboKanaele', 'premiumSmsGate', 'profil', 'schwellen'].map((n) => [n, attr(n)]));
	return render(Block, { props: { ...props, aktiveMetriken: ['thunder_level'], eintraege: { thunder: TG },
		schluesselOverride: SCHLUESSEL, onChange: () => {} } }).body;
}
const hat = (h: string, id: string) => h.includes(`data-testid="${id}"`);

test('AC-63/AC-73: Profil aus AlarmeTab erreicht den Block — B (kein Chat) mit, A (Chat) ohne Hinweis', async () => {
	for (const saat of [routeSaat, vergleichSaat]) {
		const b = await hinweiseAusTab(saat({ profileOverride: OHNE_CHAT }));
		assert.ok(hat(b, 'kanal-hinweis-kein-empfaenger-telegram'), 'B ohne Chat: Hinweis fehlt');
		const a = await hinweiseAusTab(saat({ profileOverride: MIT_CHAT }));
		assert.ok(!hat(a, 'kanal-hinweis-kein-empfaenger-telegram'), 'A mit Chat: Hinweis darf nicht erscheinen');
		const b2 = await hinweiseAusTab(saat({ profileOverride: OHNE_CHAT }));
		assert.ok(hat(b2, 'kanal-hinweis-kein-empfaenger-telegram'), 'B nach A: Stand von A darf B nicht beeinflussen');
	}
});

test('AC-67: Profil unbekannt (null) ⇒ AlarmeTab reicht null durch, kein Empfänger-Hinweis', async () => {
	const h = await hinweiseAusTab(routeSaat({ profileOverride: null }));
	assert.ok(!h.includes('kanal-hinweis-kein-empfaenger-'));
});

test('AC-70 Trip: gespeicherte Telegram-Schwelle HIGH erreicht den Block; alle LOW ⇒ kein Hinweis', async () => {
	const hoch = await hinweiseAusTab(routeSaat({ profileOverride: MIT_CHAT, existingChannelThresholds: { telegram: 'HIGH' } }));
	assert.ok(hat(hoch, 'kanal-hinweis-schwelle-telegram'), 'Schwellen-Hinweis fehlt (schwellen nicht verdrahtet?)');
	const niedrig = await hinweiseAusTab(routeSaat({ profileOverride: MIT_CHAT, existingChannelThresholds: { telegram: 'LOW' } }));
	assert.ok(!niedrig.includes('kanal-hinweis-schwelle-'));
});

test('AC-70 Ortsvergleich: Wertprop channelThresholds Telegram HIGH erreicht den Block; alle LOW ⇒ kein Hinweis', async () => {
	const low = { email: 'LOW', telegram: 'LOW', sms: 'LOW', premium_sms: 'LOW' };
	const hoch = await hinweiseAusTab(vergleichSaat({ profileOverride: MIT_CHAT, channelThresholds: { ...low, telegram: 'HIGH' } }));
	assert.ok(hat(hoch, 'kanal-hinweis-schwelle-telegram'), 'Schwellen-Hinweis fehlt (schwellen nicht verdrahtet?)');
	const niedrig = await hinweiseAusTab(vergleichSaat({ profileOverride: MIT_CHAT, channelThresholds: low }));
	assert.ok(!niedrig.includes('kanal-hinweis-schwelle-'));
});
