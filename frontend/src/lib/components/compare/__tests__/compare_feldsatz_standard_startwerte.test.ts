// TDD RED — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-17 (+ Vertrag 1, Grundlage AC-8/AC-22)
//
// `compare/compareEditorSave.ts` exportiert die reine Daten-Factory `compareFeldsatzStandard()`:
// ein FRISCHES Plain-Objekt mit exakt den Startwerten der bisherigen Klassenfelder (ohne `$state`,
// lauffähig ohne Svelte-Compiler). Hub (`CompareTabs`) und Anlege-Editor machen daraus
// `$state(compareFeldsatzStandard())`. Die vier toten Felder `saveStatus`, `saveError`,
// `metricsManuallyEdited`, `weekday` entfallen.
//
// Die Sollwerte stehen hier als LITERALE (abgelesen aus der Klasse beim Stand 60b932c94,
// compareWizardState.svelte.ts:14–118) — nicht aus der Klasse importiert: eine stille Änderung eines
// Startwerts beim Umbau würde sonst mitwandern (AC-8: Payload bitgleich zum Stand vor dem Umbau).
// AC-17: jeder Aufruf liefert ein NEUES Objekt, auch die Unterobjekte sind frisch — keine
// modulglobale Instanz, die Zustand zwischen Seiten/Nutzern teilt.
//
// Warum heute rot: der Export `compareFeldsatzStandard` fehlt (Namensraum-Import, damit die Datei
// trotzdem lädt; jeder Test scheitert mit „VERTRAG FEHLT").
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/compare/__tests__/compare_feldsatz_standard_startwerte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { feldsatzFabrik } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';

/** Startwerte mit definiertem Wert (Literal-Soll, feldweise). */
const SOLL: Record<string, unknown> = {
	name: '',
	region: '',
	activityProfile: null,
	pickedIds: [],
	isEditMode: false,
	idealRanges: {},
	activeMetricKeys: null,
	channelActiveMetricKeys: { email: null, telegram: null, sms: null },
	corridors: [],
	hourlyMetricKeys: null,
	outlookMetricKeys: null,
	outlookMetricFormats: null,
	sendEmail: true,
	sendTelegram: false,
	sendSms: false,
	sendPremiumSms: false,
	officialAlertsEnabled: true,
	radarAlertEnabled: false,
	hourlyEnabled: true,
	outlookEnabled: true,
	officialAlertTriggersEnabled: true,
	officialWarningsEnabled: false,
	metricAlertLevels: {},
	channelThresholds: {},
	alertMetricChannels: {}, // #1895 S3b1: Kanäle je Wettergröße
	telegramStyle: 'rich',
	schedule: 'daily_morning',
	morningEnabled: true,
	morningTime: '07:00',
	eveningEnabled: false,
	eveningTime: '18:00',
	endDate: null,
	dayWindowStartHour: 4,
	dayWindowEndHour: 19
};

/** Startwert `undefined` („nie gesetzt") — Schlüssel darf fehlen oder `undefined` tragen. */
const SOLL_UNDEFINIERT = ['channels', 'alertCooldownMinutes', 'alertQuietFrom', 'alertQuietTo'];

/** Tote Felder der Klasse — gehören nicht in den Feldsatz. */
const TOT = ['saveStatus', 'saveError', 'metricsManuallyEdited', 'weekday'];

describe('Vertrag 1: compareFeldsatzStandard() — Startwerte feldweise', () => {
	for (const [feld, soll] of Object.entries(SOLL)) {
		test(`${feld} startet mit ${JSON.stringify(soll)}`, () => {
			const f = feldsatzFabrik()();
			assert.ok(feld in f, `Feld ${feld} fehlt im Feldsatz`);
			assert.deepStrictEqual(f[feld], soll);
		});
	}

	for (const feld of SOLL_UNDEFINIERT) {
		test(`${feld} startet als undefined („nie gesetzt")`, () => {
			assert.strictEqual(feldsatzFabrik()()[feld], undefined);
		});
	}

	test('die vier toten Felder fehlen', () => {
		const f = feldsatzFabrik()();
		for (const feld of TOT) assert.ok(!(feld in f), `totes Feld ${feld} steht noch im Feldsatz`);
	});

	test('keine weiteren Felder (exakt der Feldsatz der bisherigen Klasse ohne die toten Felder)', () => {
		const erlaubt = new Set([...Object.keys(SOLL), ...SOLL_UNDEFINIERT]);
		const fremd = Object.keys(feldsatzFabrik()()).filter((k) => !erlaubt.has(k));
		assert.deepEqual(fremd, [], `unbekannte Felder im Feldsatz: ${fremd.join(', ')}`);
	});

	test('reines Daten-Objekt: Plain-Object, keine Methoden (kein saveNewPreset), ohne $state lauffähig', () => {
		assert.equal((globalThis as Record<string, unknown>).$state, undefined, 'Messaufbau: $state darf hier nicht geschimmt sein');
		const f = feldsatzFabrik()();
		assert.equal(Object.getPrototypeOf(f), Object.prototype, 'Feldsatz ist keine Klasseninstanz');
		const funktionen = Object.entries(f).filter(([, v]) => typeof v === 'function').map(([k]) => k);
		assert.deepEqual(funktionen, [], `Feldsatz trägt Funktionen: ${funktionen.join(', ')}`);
	});
});

describe('AC-17: jeder Aufruf liefert einen frischen, unabhängigen Feldsatz', () => {
	test('zwei Aufrufe ⇒ zwei verschiedene Objekte', () => {
		const fabrik = feldsatzFabrik();
		assert.notStrictEqual(fabrik(), fabrik());
	});

	test('auch die Unterobjekte sind frisch (pickedIds, corridors, channelActiveMetricKeys, idealRanges …)', () => {
		const fabrik = feldsatzFabrik();
		const a = fabrik();
		const b = fabrik();
		for (const feld of ['pickedIds', 'corridors', 'channelActiveMetricKeys', 'idealRanges', 'metricAlertLevels', 'channelThresholds']) {
			assert.notStrictEqual(a[feld], b[feld], `${feld} wird zwischen zwei Feldsätzen geteilt`);
		}
	});

	test('Änderungen am einen Feldsatz schlagen nicht auf den nächsten durch (auch nicht verschachtelt)', () => {
		const fabrik = feldsatzFabrik();
		const a = fabrik();
		a.name = 'Nutzer A';
		a.pickedIds.push('loc-a');
		a.channelActiveMetricKeys.telegram = ['wind_kmh'];
		a.idealRanges.wind_kmh = { min: 0, max: 20 };
		const b = fabrik();
		assert.equal(b.name, '');
		assert.deepEqual(b.pickedIds, []);
		assert.deepEqual(b.channelActiveMetricKeys, { email: null, telegram: null, sms: null });
		assert.deepEqual(b.idealRanges, {});
	});
});
