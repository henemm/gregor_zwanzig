// doc-compliance-test
//
// Issue #1260 Scheibe S5 — AC-11: Der Kurzstil-Schalter „Telegram im SMS-
// Kurzstil" ist EINE geteilte Komponente (shared/TelegramKurzstilToggle.svelte),
// die in BEIDEN Editor-Kontexten mit demselben Baustein + derselben Beschriftung
// gerendert wird:
//   - context="route"     → shared/versand-tab/VTBriefingChannels.svelte (Trip)
//   - context="vergleich" → shared/AlarmeTab.svelte (amtliche Compare-Warnungen)
//
// SCHICHT-EINORDNUNG (Test-Politik, CLAUDE.md): Dies ist eine STRUKTURELLE
// INVARIANTEN-Pruefung (eine geteilte Komponente, kein Compare-Nachbau) via
// Source-Inspection — KEIN Verhaltensnachweis. Deshalb der Marker
// `doc-compliance-test` oben (Ausnahme zur Datei-Grep-Regel). Der eigentliche
// VERHALTENS-Nachweis fuer AC-11 laeuft:
//   - fuer den Hub-Alarme-Kurzstil-Pfad: als echter node:test in
//     shared/__tests__/compare_hub_alarme_bridge.test.ts (#1260-Block,
//     hydrateAlarmFieldsFromPreset + flushPendingAlarmSave aus
//     shared/alarmeVergleichSpeicherung.ts gegen ein Preset-Objekt, #2276 S2)
//   - fuer den End-to-End-Klickpfad beider Kontexte: in der Staging-E2E
//     (Playwright, kein jsdom-Mount moeglich — Svelte-5-Komponenten sind ohne
//     @testing-library/svelte in diesem Setup nicht mountbar).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/telegram_kurzstil_shared_toggle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { register } from 'node:module';
// Issue #2293 S2 (AC-11, Mutations-Gegenprobe (e)): der geteilte Organismus
// liest im Vergleich reine Wertprops — dasselbe Buendel wie die Produktiv-
// Mounts (Vorbild alarme_tab_premium_sms_channel_row_render.test.ts).
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared
const SHARED_DIR = join(here, '..');
// __tests__ -> shared -> components -> lib -> src
const SRC_DIR = join(here, '..', '..', '..', '..');

const SHARED_TOGGLE = join(SHARED_DIR, 'TelegramKurzstilToggle.svelte');
const VT_BRIEFING_CHANNELS = join(SHARED_DIR, 'versand-tab', 'VTBriefingChannels.svelte');
const ALARME_TAB = join(SHARED_DIR, 'AlarmeTab.svelte');

const LABEL = 'Telegram im SMS-Kurzstil';
// Beide Mount-Stellen importieren aus DERSELBEN Modul-Spezifikation.
const IMPORT_SPECIFIER = '$lib/components/shared/TelegramKurzstilToggle.svelte';

function read(path: string): string {
	return readFileSync(path, 'utf-8');
}

function collectSvelteFiles(dir: string): string[] {
	const results: string[] = [];
	if (!existsSync(dir)) return results;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) results.push(...collectSvelteFiles(full));
		else if (entry.endsWith('.svelte')) results.push(full);
	}
	return results;
}

describe('AC-11: geteilte Komponente existiert und traegt die eine Beschriftung', () => {
	test('shared/TelegramKurzstilToggle.svelte existiert', () => {
		assert.ok(existsSync(SHARED_TOGGLE), `Erwartet geteilte Komponente unter ${SHARED_TOGGLE}`);
	});

	test('Komponente traegt die Beschriftung „Telegram im SMS-Kurzstil"', () => {
		assert.ok(read(SHARED_TOGGLE).includes(LABEL), `Label „${LABEL}" fehlt in der Komponente`);
	});

	test('Komponente unterstuetzt BEIDE Kontexte (route + vergleich) als Prop', () => {
		const src = read(SHARED_TOGGLE);
		assert.match(
			src,
			/context\?:\s*'route'\s*\|\s*'vergleich'/,
			'context-Prop muss beide Kontext-Literale zulassen (gemeinsamer Baustein)'
		);
	});
});

describe('AC-11: DIESELBE Komponente wird in route UND vergleich eingebunden', () => {
	test('route: VTBriefingChannels importiert + mountet TelegramKurzstilToggle', () => {
		const src = read(VT_BRIEFING_CHANNELS);
		assert.ok(src.includes(IMPORT_SPECIFIER), 'VTBriefingChannels muss die geteilte Komponente importieren');
		assert.match(src, /<TelegramKurzstilToggle\b/, 'VTBriefingChannels muss <TelegramKurzstilToggle> rendern');
	});

	test('vergleich: AlarmeTab importiert + mountet TelegramKurzstilToggle mit context="vergleich"', () => {
		const src = read(ALARME_TAB);
		assert.ok(src.includes(IMPORT_SPECIFIER), 'AlarmeTab muss die geteilte Komponente importieren');
		assert.match(
			src,
			/<TelegramKurzstilToggle[\s\S]*?context="vergleich"/,
			'AlarmeTab muss <TelegramKurzstilToggle context="vergleich"> rendern'
		);
	});

	test('beide Mount-Stellen referenzieren die IDENTISCHE Modul-Spezifikation (keine Divergenz)', () => {
		assert.ok(read(VT_BRIEFING_CHANNELS).includes(IMPORT_SPECIFIER));
		assert.ok(read(ALARME_TAB).includes(IMPORT_SPECIFIER));
	});
});

describe('AC-11: kein unabhaengig gepflegter Compare-Nachbau', () => {
	test('genau EINE .svelte-Datei traegt die Kurzstil-Beschriftung (kein Duplikat)', () => {
		const carriers = collectSvelteFiles(SRC_DIR).filter((f) => read(f).includes(LABEL));
		const short = carriers.map((f) => f.replace(SRC_DIR + '/', ''));
		assert.deepStrictEqual(
			short,
			['lib/components/shared/TelegramKurzstilToggle.svelte'],
			`Erwartet genau die geteilte Komponente als Traeger der Beschriftung, gefunden: ${short.join(', ')}`
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// Issue #2293 Scheibe S2 (AC-11, Mutations-Gegenprobe (e)) — VERHALTENS-
// Nachweis (kein Datei-Grep): im Vergleichs-Kontext muss der `disabled`-
// Zustand des Kurzstil-Schalters am ALARM-Telegram-Zustand haengen
// (`displayChannelState.telegram` bzw. dessen Nachfolger), NICHT an
// `sendTelegram` (ab dieser Scheibe ein reines Briefing-Feld, das mit dem
// Alarm-Kanal auseinanderlaufen kann, Implementation Details Abschnitt 3).
//
// Echtes SSR-Rendering (svelte/server) statt Quelltext-Muster: ein Text-Grep
// auf `sendTelegram` vs. `displayChannelState` würde nur eine Umbenennung
// verlangen, nicht die tatsächliche Entkopplung — Mutation (e) der Spec
// bleibt an einer reinen Textpruefung strukturell unbeobachtbar. Vorbild
// (SSR-Setup, `existingChannels`-Prop, `profileOverride`-Testhaken):
// alarme_tab_premium_sms_channel_row_render.test.ts.
//
// RED-Grund heute (gemessen): AlarmeTab.svelte leitet `displayChannelState`
// im vergleich-Zweig als `sendTelegram === undefined ? routeChannelState :
// {telegram: sendTelegram, ...}` her (Zeile ~296) — ist `sendTelegram`
// gesetzt (Normalfall), gewinnt IMMER der Briefing-Wert, `existingChannels`
// wird vollständig ignoriert. Die Tests unten setzen genau diese beiden
// Werte auseinander.

const HERE_SSR = dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND_SSR = resolve(HERE_SSR, '../../../../..');

register(
	pathToFileURL(join(FRONTEND_SSR, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND_SSR + '/').href
);

const { render: renderSsr } = await import('svelte/server');
const AlarmeTabSsr = (
	await import(pathToFileURL(join(FRONTEND_SSR, 'src/lib/components/shared/AlarmeTab.svelte')).href)
).default;

/** Wizard-Stellvertreter mit den Feldern, die `alarmePropsAus` liest —
 *  identisch zum Vorbild (alarme_tab_premium_sms_channel_row_render.test.ts). */
function wizStubSsr(overrides: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		officialWarningsEnabled: true,
		radarAlertEnabled: false,
		activeMetricKeys: null,
		metricAlertLevels: {},
		sendTelegram: true,
		sendSms: false,
		sendPremiumSms: false,
		channelThresholds: {},
		telegramStyle: 'rich',
		alertCooldownMinutes: 30,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00',
		...overrides
	};
}

function renderVergleichMitAlarmKanaelen(
	existingChannels: { telegram: boolean; sms: boolean; email: boolean; premium_sms: boolean },
	wizOverrides: Record<string, unknown> = {}
): string {
	return renderSsr(AlarmeTabSsr, {
		props: {
			context: 'vergleich',
			...alarmePropsAus(wizStubSsr(wizOverrides)),
			// Design Entscheidung 5: dieselbe Bestands-Prop wie der Trip-Zweig —
			// der Vergleich muss sie ab dieser Scheibe ebenfalls auswerten.
			existingChannels,
			catalog: [],
			profileOverride: {}
		}
	}).body;
}

describe('AC-11 (Mutations-Gegenprobe e): Kurzstil-`disabled` folgt dem ALARM-Telegram-Zustand', () => {
	test('Alarm-Telegram AUS, Briefing-Telegram AN → Kurzstil-Schalter ist deaktiviert', () => {
		const html = renderVergleichMitAlarmKanaelen(
			{ telegram: false, sms: true, email: true, premium_sms: false },
			{ sendTelegram: true }
		);
		assert.ok(
			html.includes('tks-disabled'),
			'AC-11: der Kurzstil-Schalter muss deaktiviert sein, wenn der ALARM-Telegram-Kanal aus ist ' +
				'(existingChannels.telegram=false) — unabhängig vom Briefing-Telegram-Zustand (sendTelegram=true).'
		);
	});

	test('Alarm-Telegram AN, Briefing-Telegram AUS → Kurzstil-Schalter ist aktiv (Gegenprobe)', () => {
		const html = renderVergleichMitAlarmKanaelen(
			{ telegram: true, sms: false, email: true, premium_sms: false },
			{ sendTelegram: false }
		);
		assert.ok(
			!html.includes('tks-disabled'),
			'AC-11 (Gegenprobe): der Kurzstil-Schalter muss aktiv sein, wenn der ALARM-Telegram-Kanal an ist ' +
				'(existingChannels.telegram=true) — auch wenn der Briefing-Telegram-Zustand aus ist (sendTelegram=false). ' +
				'Ohne diese Gegenprobe wäre "immer deaktiviert" ein falsches Grün für den Test oben.'
		);
	});
});
