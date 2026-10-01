// TDD RED — Issue #2422 Scheibe S6, AC-8 (Editor-Haelfte): der SMS-Reiter des
// Trip-Editors bietet Roh/Einfach NUR fuer Groessen mit `sms_format_capable`
// (Endpoint-Feld `GET /api/metrics`, Quelle Backend-Konstante
// `SMS_FORMAT_MODE_METRIC_IDS`) — nicht mehr fuer thunder, wind_direction,
// sunshine, wind, gust, rain_probability, precipitation. Telegram- und E-Mail-
// Reiter behalten ihren Umschalter unveraendert (`indicatorCapable`).
//
// Spec: docs/specs/modules/fix_2422_s6_register_leeren.md (AC-8)
//
// WAS HIER GEMESSEN WIRD: Die Kernsuite ist SSR-only (`node --test`,
// `svelte/server`, kein DOM). Gemessen wird die ECHTE Verdrahtung am Aufruf der
// Kanal-Reihenfolge in `WeatherMetricsTab.svelte`: der Attribut-Ausdruck
// `modeCapable` der `<WeatherV2Reihenfolge>`-Einbettung des Trip-Kanal-Reiters
// wird (AST, kein Text-Grep) gelesen und gegen einen gesaeten Metrik-Katalog
// (`metricById` mit `sms_format_capable`) fuer die Kanaele sms/telegram/email
// ausgewertet. Der Baustein allein (`WeatherV2Reihenfolge`, Default
// `modeCapable = indicatorCapable`) reicht als Nachweis NICHT — er war schon
// vorher gruen und beweist die Verdrahtung nicht.
//
// RED-Grund (heute): die Einbettung uebergibt kein `modeCapable` — der SMS-Reiter
// bietet Roh/Einfach fuer alle `indicatorCapable`-Groessen (thunder, sunshine,
// wind ... verspricht mehr, als die SMS liefert: dieselbe Fehlerklasse wie #2422).
//
// Drift Katalog-Konstante <-> Endpoint-Feld: Python-Test
// `tests/tdd/test_sms_einfach_roh_je_metrik.py::test_ac8_endpoint_feld_...`.
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/weather-metrics-tab/__tests__/sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	umgebungFuer,
	werte,
	findeKomponenten,
	attributAusdruck,
	type Knoten
} from '../../__tests__/svelteInstanzPruefstand.ts';
import { INDICATOR_MAP, indicatorCapable } from '../../../trip-detail/metricsEditor.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TAB = join(HIER, '..', '..', 'WeatherMetricsTab.svelte');

/** Spec AC-8 WORTGLEICH (nicht aus dem Produkt gelesen). */
const SMS_MIT_FORM = ['cloud_total', 'cloud_low', 'cloud_mid', 'cloud_high', 'cape'];
const SMS_OHNE_FORM = [
	'thunder',
	'wind_direction',
	'sunshine',
	'wind',
	'gust',
	'rain_probability',
	'precipitation'
];

function katalog(capable: string[]): Record<string, Knoten> {
	const k: Record<string, Knoten> = {};
	for (const id of [...SMS_MIT_FORM, ...SMS_OHNE_FORM]) {
		k[id] = {
			id,
			label: id,
			unit: '',
			category: 'atmosphere',
			default_enabled: false,
			has_friendly_format: true,
			sms_format_capable: capable.includes(id)
		};
	}
	return k;
}

/** Der Attribut-Ausdruck `modeCapable` der Trip-Kanal-Reihenfolge — die
 *  Einbettung, die `metricById` (Trip-Katalog) bekommt, nicht `compareMetricById`. */
async function tripKanalModeCapable(): Promise<{ ausdruck: string | null; u: Knoten }> {
	const { ast, quelle, u } = await umgebungFuer(TAB, {});
	const einbettungen = findeKomponenten(ast, 'WeatherV2Reihenfolge');
	const trip = einbettungen.filter((e) => attributAusdruck(e, quelle, 'metricById') === 'metricById');
	assert.equal(
		trip.length,
		1,
		`Testaufbau: genau EINE Trip-Kanal-Reihenfolge erwartet, gefunden ${trip.length}`
	);
	assert.equal(attributAusdruck(trip[0], quelle, 'activeChannel'), 'channel');
	return { ausdruck: attributAusdruck(trip[0], quelle, 'modeCapable'), u };
}

async function modeCapableFuer(
	kanal: string,
	capable: string[],
	ohneAttributGiltDefault = false
): Promise<(id: string) => boolean> {
	const { ausdruck, u } = await tripKanalModeCapable();
	// Die Komponente hat `modeCapable = indicatorCapable` als Default: fehlt das
	// Attribut, gilt im Telegram-/E-Mail-Reiter der bisherige Umschalter (GUARD).
	if (ausdruck === null && ohneAttributGiltDefault) return indicatorCapable;
	assert.ok(
		ausdruck !== null,
		'AC-8: die Trip-Kanal-Reihenfolge uebergibt kein `modeCapable` — der SMS-Reiter ' +
			'bietet Roh/Einfach damit fuer alle indicatorCapable()-Groessen an (auch thunder, ' +
			'sunshine, wind ...), obwohl die SMS dort nur EINE Form hat.'
	);
	u.metricById = katalog(capable);
	u.indicatorCapable = indicatorCapable;
	const fn = werte(ausdruck!, { ...u, channel: kanal }) as (id: string) => boolean;
	assert.equal(typeof fn, 'function', `AC-8: modeCapable ist keine Funktion: ${ausdruck}`);
	return fn;
}

describe('#2422 S6 AC-8: Roh/Einfach-Umschalter im SMS-Reiter nur fuer sms_format_capable', () => {
	test('SMS-Reiter: Umschalter genau fuer die Groessen mit sms_format_capable', async () => {
		const capable = await modeCapableFuer('sms', SMS_MIT_FORM);
		for (const id of SMS_MIT_FORM) {
			assert.equal(capable(id), true, `AC-8: ${id} hat in der SMS zwei Formen — Umschalter fehlt`);
		}
		for (const id of SMS_OHNE_FORM) {
			assert.equal(
				capable(id),
				false,
				`AC-8: ${id} hat in der SMS EINE Form — der SMS-Reiter darf keinen Umschalter anbieten`
			);
		}
	});

	test('SMS-Reiter folgt dem Endpoint-Feld, nicht einer eigenen TS-Liste', async () => {
		// `sunshine` ist indicatorCapable; hier wird es im Katalog als sms_format_capable
		// markiert und MUSS dann den Umschalter bekommen (eine fest verdrahtete TS-Liste
		// wuerde das Feld ignorieren); `cloud_total` wird abgewaehlt und MUSS ihn verlieren.
		const capable = await modeCapableFuer('sms', ['sunshine', 'cloud_low']);
		assert.equal(capable('sunshine'), true, 'AC-8: Umschalter folgt nicht dem Feld sms_format_capable');
		assert.equal(capable('cloud_low'), true);
		assert.equal(capable('cloud_total'), false, 'AC-8: cloud_total ohne Feld darf keinen Umschalter haben');
	});

	for (const kanal of ['telegram', 'email']) {
		test(`${kanal}-Reiter behaelt seinen Umschalter unveraendert (indicatorCapable)`, async () => {
			const capable = await modeCapableFuer(kanal, SMS_MIT_FORM, true);
			for (const id of Object.keys(INDICATOR_MAP)) {
				assert.equal(
					capable(id),
					indicatorCapable(id),
					`AC-8: im ${kanal}-Reiter muss ${id} seinen bisherigen Umschalter behalten`
				);
			}
			assert.equal(capable('thunder'), true);
			assert.equal(capable('sunshine'), true);
		});
	}
});
