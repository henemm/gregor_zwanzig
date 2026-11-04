// TDD RED — #1895 S3b1: `AlertMetricChannelsBlock.svelte` (fehlt ⇒ Import rot) per SSR
// (Muster alertMetricLevelRowTitleRender.test.ts). AC-41, 43, 48, 49, 51, 52, 53.
// SSR führt onMount nie aus ⇒ Testhaken `schluesselOverride` (Muster profileOverride): Objekt =
// Endpunkt-Antwort, null = Abruf gescheitert. Klick-Abläufe (Umschalten, Vorbelegung mit dem
// Abo-Satz) bleiben für /e2e-verify. Props: aktiveMetriken, eintraege, aboKanaele, premiumSmsGate
// (= derivePremiumSmsAlarmGate), schluesselOverride?, onChange(k, eintrag). Testids: kanal-zeile-<k>,
// kanal-schalter-<k>-<kanal>, kanal-hinweis-wind-<k>, kanal-hinweis-nicht-im-abo-<k>,
// kanal-hinweis-metrikfrei, kanal-nicht-verfuegbar.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { derivePremiumSmsAlarmGate, PREMIUM_SMS_ALARM_HINT_NO_TIER } from '../../shared/alarme-tab/premiumSmsAlarmGate.ts';
import { locale, trFor, type MessageKey } from '../../../i18n/index.ts';
import { umgebungFuer } from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const Block = (await import(pathToFileURL(path.join(HERE, '..', 'AlertMetricChannelsBlock.svelte')).href)).default;

const ANTWORT = {
	keys: { wind_gust: ['gust'], wind_change: ['gust', 'wind'], thunder_level: ['thunder'], cape: ['cape'] },
	accepted: ['cape', 'gust', 'snowfall_limit', 'thunder', 'wind']
};
const TG = { email: false, telegram: true, sms: false, premium_sms: false };
const NUR_MAIL = { email: true, telegram: false, sms: false, premium_sms: false };

const html = (over: Record<string, unknown> = {}): string =>
	render(Block, { props: {
		aktiveMetriken: ['wind_gust', 'wind_change', 'thunder_level'], eintraege: { thunder: TG, snowfall_limit: NUR_MAIL },
		aboKanaele: NUR_MAIL, premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: false }),
		schluesselOverride: ANTWORT, onChange: () => {}, ...over
	} }).body;
const zeilen = (h: string) => [...h.matchAll(/data-testid="kanal-zeile-([a-z_]+)"/g)].map((m) => m[1]);
/** Ausschnitt ab dem Marker bis zum nächsten Zeilen-Marker. */
function ab(h: string, marker: string): string {
	const i = h.indexOf(`data-testid="${marker}"`);
	assert.notEqual(i, -1, `${marker} fehlt im HTML`);
	const n = h.indexOf('data-testid="kanal-zeile-', i + 1);
	return h.slice(i, n === -1 ? h.length : n);
}

test('AC-41/AC-42/AC-48: eine Zeile je Speicherschlüssel, gust und wind getrennt mit Wind-Hinweis, kein snowfall_limit', () => {
	const h = html();
	assert.deepStrictEqual(zeilen(h), ['gust', 'thunder', 'wind']);
	assert.ok(ab(h, 'kanal-zeile-gust').includes('kanal-hinweis-wind-gust'));
	assert.ok(ab(h, 'kanal-zeile-wind').includes('kanal-hinweis-wind-wind'));
	assert.ok(!ab(h, 'kanal-zeile-thunder').includes('kanal-hinweis-wind-'));
});

test('AC-43: ohne Eintrag „wie Abo-Kanäle" ohne Schalter; mit Eintrag vier Kanal-Schalter', () => {
	const h = html();
	const gust = ab(h, 'kanal-zeile-gust');
	assert.ok(!gust.includes('kanal-schalter-gust-'), 'erbende Zeile zeigt keine Kanal-Schalter');
	const thunder = ab(h, 'kanal-zeile-thunder');
	for (const k of ['email', 'telegram', 'sms', 'premium_sms']) {
		assert.ok(thunder.includes(`data-testid="kanal-schalter-thunder-${k}"`), `Schalter ${k} fehlt`);
	}
});

test('AC-51: Telegram gewählt, Abo nur E-Mail ⇒ sichtbarer Hinweis an dieser Zeile', () => {
	assert.ok(ab(html(), 'kanal-zeile-thunder').includes('kanal-hinweis-nicht-im-abo-thunder'));
	assert.ok(!ab(html({ aboKanaele: TG }), 'kanal-zeile-thunder').includes('kanal-hinweis-nicht-im-abo-'));
});

test('AC-52: Hinweis „metrikfreie Alarme gehen über die Abo-Kanäle" steht im Block', () => {
	assert.ok(html().includes('data-testid="kanal-hinweis-metrikfrei"'));
});

test('AC-53: Premium-SMS-Schalter nach premiumSmsAlarmGate gesperrt bzw. schaltbar', () => {
	const schalter = (h: string) => {
		const i = h.indexOf('data-testid="kanal-schalter-thunder-premium_sms"');
		assert.notEqual(i, -1, 'Premium-SMS-Schalter fehlt');
		return h.slice(i, h.indexOf('</div>', i));
	};
	assert.match(schalter(html()), /\sdisabled/, 'ohne Freigabe gesperrt');
	const frei = html({ premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: true }) });
	assert.doesNotMatch(schalter(frei), /\sdisabled/, 'mit Freigabe schaltbar');
	assert.ok(!html().includes('kanal-schalter-thunder-sms-hint'), 'kein Tarif-Hinweis für SMS');
	assert.match(html(), new RegExp(`kanal-schalter-thunder-premium_sms-hint"[^>]*>\\s*${trFor('de', PREMIUM_SMS_ALARM_HINT_NO_TIER)}`), 'Tarif-Hinweis fehlt');
});

test('AC-41/AC-43 F001: jede Zeile trägt ihren Titel aus dem Katalog — Deutsch und Englisch', () => {
	const soll = (lang: 'de' | 'en', ...m: string[]) => m.map((x) => trFor(lang, `alarme.metrik.${x}` as MessageKey)).join(' / ');
	const titel = (h: string, k: string) => ab(h, `kanal-zeile-${k}`).match(/class="amc-titel[^"]*">([^<]*)</)?.[1];
	try {
		for (const lang of ['de', 'en'] as const) {
			locale.set(lang);
			const h = html();
			assert.strictEqual(titel(h, 'gust'), soll(lang, 'wind_gust', 'wind_change'), `${lang}: gust`);
			assert.strictEqual(titel(h, 'wind'), soll(lang, 'wind_change'), `${lang}: wind`);
			assert.strictEqual(titel(h, 'thunder'), soll(lang, 'thunder_level'), `${lang}: thunder`);
		}
	} finally {
		locale.set('de');
	}
});

// Bedienlogik ohne DOM (svelteInstanzPruefstand): festgelegte Instanzfunktionen des Blocks
// `kanalSetzen(k, kanal, an)` und `eigeneWahl(k, an)`; sie melden Änderungen NUR über onChange.
test('AC-48/43/45/46: Bedienung schreibt nur den eigenen Schlüssel, vorbelegt mit dem Abo-Satz', async () => {
	const rufe: unknown[][] = [];
	const { u } = await umgebungFuer(path.join(HERE, '..', 'AlertMetricChannelsBlock.svelte'), {
		aktiveMetriken: ['wind_change'], eintraege: { gust: TG, wind: null }, aboKanaele: NUR_MAIL,
		premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: true }), schluesselOverride: ANTWORT,
		onChange: (...a: unknown[]) => rufe.push(a)
	});
	const fall = (fn: () => void, soll: unknown[][], was: string) => {
		rufe.length = 0;
		fn();
		assert.deepStrictEqual(rufe, soll, was);
	};
	fall(() => u.kanalSetzen('gust', 'email', true), [['gust', { ...TG, email: true }]], 'AC-48: nur gust, kein wind');
	fall(() => u.kanalSetzen('gust', 'telegram', false), [['gust', null]], 'AC-45: letzter Kanal aus ⇒ null');
	fall(() => u.eigeneWahl('wind', true), [['wind', NUR_MAIL]], 'AC-43: eigene Wahl vorbelegt mit Abo-Satz');
	fall(() => u.eigeneWahl('gust', false), [['gust', null]], 'AC-46: zurück auf „wie Abo-Kanäle"');
});

test('AC-49: Endpunkt nicht ladbar ⇒ „nicht verfügbar", keine geratenen Zeilen', () => {
	const h = html({ schluesselOverride: null });
	assert.ok(h.includes('data-testid="kanal-nicht-verfuegbar"'));
	assert.deepStrictEqual(zeilen(h), []);
});
