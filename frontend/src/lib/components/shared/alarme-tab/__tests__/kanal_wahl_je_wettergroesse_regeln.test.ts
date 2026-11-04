// TDD RED — #1895 S3b1, Helper `../alertMetricChannels.ts` (fehlt noch ⇒ Import rot).
// Spec alert_metric_channels.md AC-41/42/44–51/60. API-Vertrag: ladeKanalSchluessel(fetchFn)
// (Modul-Promise-Cache; Fehler ⇒ null oder Reject, nie gecacht), _resetKanalSchluesselCache(),
// kanalZeilen(aktiveMetriken, keys, accepted) (sortiert, ohne Dubletten), normalisiereEintrag(flags)
// (vier Flags oder null), baueDiff(hydriert, aktuell) (nur abweichende Schlüssel aus `aktuell`,
// fehlend = null), hinweise(eintrag, aboSatz): Kanäle der Wahl, die im Abo aus sind.

import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ladeKanalSchluessel, _resetKanalSchluesselCache, kanalZeilen, normalisiereEintrag, baueDiff, hinweise } from '../alertMetricChannels.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(HIER, '..', '..', '..', '..', '..', '..', '..', 'tests', 'fixtures', 'alert_metric_channels_nutzlast_beispiel.json');

// Gemessene S3a-Endpunkt-Antwort (Auszug) plus fremder Schlüssel `humidity` (accepted filtert).
const ANTWORT = {
	keys: { wind_gust: ['gust'], thunder_level: ['thunder'], wind_change: ['gust', 'wind'], thunder_onset: ['thunder'], cape: ['cape', 'humidity'] },
	accepted: ['cape', 'freezing_level', 'gust', 'precipitation', 'snowfall_limit', 'temperature', 'thunder', 'wind']
};
const NUR_TG = { email: false, telegram: true, sms: false, premium_sms: false };
const NUR_MAIL = { email: true, telegram: false, sms: false, premium_sms: false };

/** fetch-Double mit echtem Verhalten: zählt Aufrufe, liefert echte Responses je Reihenfolge. */
function fetchDouble(folge: Array<'ok' | 500 | 'netz'>) {
	const aufrufe: string[] = [];
	const fn = async (url: unknown): Promise<Response> => {
		aufrufe.push(String(url));
		const art = folge[Math.min(aufrufe.length - 1, folge.length - 1)];
		if (art === 'netz') throw new TypeError('Failed to fetch');
		if (art === 500) return new Response('{"error":"x"}', { status: 500 });
		return new Response(JSON.stringify(ANTWORT), { status: 200, headers: { 'Content-Type': 'application/json' } });
	};
	return { fn: fn as unknown as typeof fetch, aufrufe };
}

beforeEach(() => _resetKanalSchluesselCache());

test('AC-41: wind_change ergibt die zwei Zeilen gust und wind — kein humidity, kein snowfall_limit', () => {
	assert.deepStrictEqual(kanalZeilen(['wind_change'], ANTWORT.keys, ANTWORT.accepted), ['gust', 'wind']);
	assert.deepStrictEqual(
		kanalZeilen(['wind_gust', 'wind_change', 'thunder_level', 'thunder_onset', 'cape'], ANTWORT.keys, ANTWORT.accepted),
		['cape', 'gust', 'thunder', 'wind'],
		'Vereinigung sortiert, ohne Dubletten, nur accepted (humidity raus)'
	);
	assert.deepStrictEqual(kanalZeilen([], ANTWORT.keys, ANTWORT.accepted), []);
});

test('AC-44: eine Teilwahl wird zu einem Eintrag mit allen vier Flags', () => {
	assert.deepStrictEqual(normalisiereEintrag({ telegram: true }), NUR_TG);
	assert.deepStrictEqual(
		Object.keys(normalisiereEintrag({ premium_sms: true, sms: true }) ?? {}).sort(),
		['email', 'premium_sms', 'sms', 'telegram']
	);
});

test('AC-45: alle vier Kanäle abgewählt ⇒ null (erbt), nie {} und nie vier false', () => {
	assert.strictEqual(normalisiereEintrag({ email: false, telegram: false, sms: false, premium_sms: false }), null);
	assert.strictEqual(normalisiereEintrag({}), null);
	assert.strictEqual(normalisiereEintrag(null), null);
});

test('AC-47/AC-42: Diff enthält nur den geänderten Eintrag — snowfall_limit wird nie mitgesendet', () => {
	const hydriert = { gust: NUR_MAIL, thunder: NUR_TG, snowfall_limit: NUR_MAIL };
	const aktuell = { gust: NUR_TG, thunder: NUR_TG, snowfall_limit: NUR_MAIL };
	assert.deepStrictEqual(baueDiff(hydriert, aktuell), { gust: NUR_TG });
	assert.deepStrictEqual(baueDiff(hydriert, { ...hydriert }), {}, 'ohne Änderung: leerer Diff');
	// AC-48: eine Änderung an gust schreibt nur gust, nie zusätzlich wind.
	assert.deepStrictEqual(baueDiff({ gust: null, wind: null }, { gust: NUR_TG, wind: null }), { gust: NUR_TG });
});

test('AC-46: Rückweg auf „wie Abo-Kanäle" sendet {Schlüssel: null}', () => {
	assert.deepStrictEqual(baueDiff({ gust: NUR_TG }, { gust: null }), { gust: null });
	assert.deepStrictEqual(baueDiff({}, { gust: null }), {}, 'fehlend und null sind beides „erbt" — kein Diff');
});

test('AC-51: Telegram gewählt, Abo nur E-Mail ⇒ Hinweis für telegram; erbt ⇒ kein Hinweis', () => {
	assert.deepStrictEqual(hinweise(NUR_TG, NUR_MAIL), ['telegram']);
	assert.deepStrictEqual(hinweise(NUR_MAIL, NUR_MAIL), []);
	assert.deepStrictEqual(hinweise(null, NUR_MAIL), []);
});

test('AC-50: zwei gleichzeitige und ein späterer Aufruf ⇒ genau ein Abruf', async () => {
	const d = fetchDouble(['ok']);
	const [a, b] = await Promise.all([ladeKanalSchluessel(d.fn), ladeKanalSchluessel(d.fn)]);
	const c = await ladeKanalSchluessel(d.fn);
	assert.deepStrictEqual(a, ANTWORT);
	assert.deepStrictEqual([b, c], [ANTWORT, ANTWORT]);
	assert.strictEqual(d.aufrufe.length, 1, `Abrufe: ${d.aufrufe.length}`);
	assert.ok(d.aufrufe[0].includes('/api/alert-metric-channel-keys'), d.aufrufe[0]);
});

test('AC-49/AC-50: Serverfehler und Netzfehler liefern keine Schlüssel und werden nicht gecacht', async () => {
	const d = fetchDouble([500, 'netz', 'ok']);
	const erst = await ladeKanalSchluessel(d.fn).catch(() => null);
	const zweit = await ladeKanalSchluessel(d.fn).catch(() => null);
	assert.strictEqual(erst, null, 'HTTP 500 darf keine (geratenen) Schlüssel liefern');
	assert.strictEqual(zweit, null, 'Netzfehler darf keine Schlüssel liefern');
	const dritt = await ladeKanalSchluessel(d.fn);
	assert.deepStrictEqual(dritt, ANTWORT);
	assert.strictEqual(d.aufrufe.length, 3, 'nach jedem Fehler muss der nächste Aufruf neu laden');
});

test('AC-60 (Frontend-Hälfte): Beispiel-Bedienung erzeugt genau die Nutzlast der gemeinsamen Testdatei', () => {
	const fx = JSON.parse(readFileSync(FIXTURE, 'utf-8'));
	const eintrag = normalisiereEintrag(fx.bedienung.kanaele);
	assert.deepStrictEqual(baueDiff({}, { [fx.bedienung.schluessel]: eintrag }), fx.nutzlast.alert_metric_channels);
});
