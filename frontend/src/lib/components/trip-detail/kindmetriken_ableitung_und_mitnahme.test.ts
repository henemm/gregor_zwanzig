// TDD RED — Bug #2454: Kurzform zeigt die gewaehlte gefuehlte Temperatur
// nie an (Editor friert fehlende Kind-Eintraege beim Speichern ein).
//
// Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md
// AC-1, AC-2, AC-4. Kontext: docs/context/bug-2454-kurzform-gefuehlte-temperatur.md
//
// `deriveMissingChildMetrics()`/`moveWithDerivedChildren()` existieren in
// `metricsEditor.ts` NOCH NICHT (Implementierungsauftrag Abschnitt 1+2) --
// dynamischer Import statt statischem, damit ein fehlender Export NICHT die
// ganze Datei beim Linken sterben laesst (Vorgabe der Entwickler-Aufgabe),
// sondern jeder Testfall EINZELN mit einer sprechenden Meldung rot wird.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/kindmetriken_ableitung_und_mitnahme.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { move, type Buckets } from './metricsEditor.ts';

const MODULE_SPECIFIER = './metricsEditor.ts';

const KIND_IDS = [
	'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night',
	'temperature_day_low', 'temperature_day_high', 'temperature_night',
];

async function requireFn(name: string): Promise<(...args: never[]) => unknown> {
	const mod = (await import(MODULE_SPECIFIER)) as Record<string, unknown>;
	const fn = mod[name];
	assert.equal(
		typeof fn, 'function',
		`Bug #2454: '${name}' fehlt in metricsEditor.ts -- ohne diese Funktion ` +
		`friert der Editor fehlende Kind-Eintraege (FD/FL/FN) beim Speichern ein.`,
	);
	return fn as (...args: never[]) => unknown;
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-1 — deriveMissingChildMetrics() ergaenzt fehlende Kind-Eintraege
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-1: deriveMissingChildMetrics() ergaenzt fehlende Kind-Eintraege beim Laden', () => {
	test('Teilfall 1: fehlendes Kind wird ergaenzt, Bucket/Order vom Elter uebernommen', async () => {
		const derive = await requireFn('deriveMissingChildMetrics');
		const input = [
			{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 12 },
		];
		const out = derive(input as never) as Array<{ metric_id: string; enabled: boolean; bucket?: string; order?: number }>;

		const kinder = out.filter((m) => m.metric_id.startsWith('wind_chill_'));
		assert.equal(
			kinder.length, 3,
			`Erwartet 3 ergaenzte wind_chill-Kinder (day_low/day_high/night), erhalten: ${JSON.stringify(kinder)}`,
		);
		for (const k of kinder) {
			assert.equal(k.enabled, true, `${k.metric_id}: enabled muss vom aktiven Elter uebernommen werden`);
			assert.equal(k.bucket, 'primary', `${k.metric_id}: bucket muss vom Elter uebernommen werden`);
			assert.equal(k.order, 12, `${k.metric_id}: order muss vom Elter uebernommen werden`);
		}
	});

	test('Teilfall 2: ein bereits vorhandener expliziter enabled:false-Kind-Eintrag bleibt unveraendert stehen', async () => {
		const derive = await requireFn('deriveMissingChildMetrics');
		const explicit = { metric_id: 'wind_chill_day_low', enabled: false };
		const input = [
			{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 12 },
			explicit,
		];
		const out = derive(input as never) as Array<Record<string, unknown>>;

		const treffer = out.filter((m) => m.metric_id === 'wind_chill_day_low');
		assert.equal(treffer.length, 1, 'deriveMissingChildMetrics darf keinen zweiten wind_chill_day_low-Eintrag erfinden');
		assert.deepEqual(
			treffer[0], explicit,
			'ein bereits expliziter Kind-Eintrag (auch enabled:false) muss BYTE-IDENTISCH erhalten bleiben (DEC-6)',
		);
	});

	test('Teilfall 3: ein Kanal-Layout leitet aus dem KANAL-EIGENEN Elter ab, nicht aus der globalen Liste', async () => {
		const derive = await requireFn('deriveMissingChildMetrics');
		// SMS-Kanal hat wind_chill SELBST deaktiviert (der Reiter zeigt den
		// Elter aus), obwohl er global aktiv sein koennte -- der Loader
		// (_append_derived_metrics) leitet je Kanal-Liste eigenstaendig ab,
		// der Editor muss dasselbe tun.
		const smsLayout = [
			{ metric_id: 'wind_chill', enabled: false, order: 0 },
		];
		const out = derive(smsLayout as never) as Array<{ metric_id: string; enabled: boolean }>;

		const kinder = out.filter((m) => m.metric_id.startsWith('wind_chill_'));
		assert.equal(kinder.length, 3);
		for (const k of kinder) {
			assert.equal(
				k.enabled, false,
				`${k.metric_id}: muss aus dem KANAL-eigenen (ausgeschalteten) Elter ableiten, nicht aus einer globalen Liste`,
			);
		}
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-2 — moveWithDerivedChildren() nimmt mitgelaufene Kinder beim Umschalten mit
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-2: moveWithDerivedChildren() nimmt mitgelaufene Kinder beim Verschieben des Elters mit', () => {
	test('Teilfall "laeuft mit": Kinder im selben Bucket wie der Elter werden bei der Einwahl mitgenommen, direkt hinter dem Elter', async () => {
		// Bruecken-Cast rein typseitig auf die echte moveWithDerivedChildren-
		// Signatur (Praezedenz #2276 S4) -- requireFn() bleibt generisch
		// ((...args: never[]) => unknown), ein Mehr-Argument-Aufruf mit
		// String-Literalen braucht sonst 'never' fuer jedes Argument
		// (svelte-check CI-Baseline). Keine Aenderung an Testlogik/Assertions.
		const moveDerived = (await requireFn('moveWithDerivedChildren')) as unknown as (
			b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets,
		) => Buckets;
		const buckets: Buckets = {
			primary: [],
			secondary: [],
			off: ['wind_chill', 'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'],
		};

		const next = moveDerived(buckets as never, 'wind_chill', 'off', 'primary') as Buckets;

		assert.deepEqual(
			next.primary, ['wind_chill', 'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'],
			'die drei Kinder muessen direkt hinter dem Elter im neuen Bucket stehen (verhindert #1947-Wiederholung)',
		);
		assert.deepEqual(next.off, [], 'off darf keines der mitgenommenen Kinder mehr enthalten');
	});

	test('Teilfall "bereits individuell abweichend": ein vom Nutzer schon verschobenes Kind bleibt unangetastet', async () => {
		// Bruecken-Cast rein typseitig auf die echte moveWithDerivedChildren-
		// Signatur (Praezedenz #2276 S4) -- requireFn() bleibt generisch
		// ((...args: never[]) => unknown), ein Mehr-Argument-Aufruf mit
		// String-Literalen braucht sonst 'never' fuer jedes Argument
		// (svelte-check CI-Baseline). Keine Aenderung an Testlogik/Assertions.
		const moveDerived = (await requireFn('moveWithDerivedChildren')) as unknown as (
			b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets,
		) => Buckets;
		const buckets: Buckets = {
			primary: ['wind_chill_day_low'], // Nutzer hat dieses Kind VORHER schon einzeln verschoben
			secondary: [],
			off: ['wind_chill', 'wind_chill_day_high', 'wind_chill_night'],
		};

		const next = moveDerived(buckets as never, 'wind_chill', 'off', 'primary') as Buckets;

		assert.ok(
			next.primary.includes('wind_chill_day_low'),
			'ein bereits individuell verschobenes Kind darf nicht aus primary verschwinden',
		);
		assert.equal(
			next.primary.filter((id) => id === 'wind_chill_day_low').length, 1,
			'wind_chill_day_low darf nicht verdoppelt werden',
		);
		assert.deepEqual(
			next.off, [],
			'die beiden mitgelaufenen Kinder (day_high, night) muessen dennoch mitgenommen werden',
		);
	});

	test('Teilfall "globale Abwahl nimmt mitgelaufene Kinder aus dem Kanal-Override mit"', async () => {
		// Bruecken-Cast rein typseitig auf die echte moveWithDerivedChildren-
		// Signatur (Praezedenz #2276 S4) -- requireFn() bleibt generisch
		// ((...args: never[]) => unknown), ein Mehr-Argument-Aufruf mit
		// String-Literalen braucht sonst 'never' fuer jedes Argument
		// (svelte-check CI-Baseline). Keine Aenderung an Testlogik/Assertions.
		const moveDerived = (await requireFn('moveWithDerivedChildren')) as unknown as (
			b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets,
		) => Buckets;
		// Spiegelbild der Global-Abwahl-Durchschreibung in einen Kanal-Override
		// (WeatherMetricsTab.svelte:~821-833): der Elter wird global abgewaehlt,
		// die Durchschreibung ruft moveWithDerivedChildren(override.buckets, id,
		// 'primary', 'off') statt des rohen move() auf.
		const overrideBuckets: Buckets = {
			primary: ['wind_chill', 'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'],
			secondary: [],
			off: [],
		};

		const next = moveDerived(overrideBuckets as never, 'wind_chill', 'primary', 'off') as Buckets;

		assert.deepEqual(
			next.off, ['wind_chill', 'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'],
			'die globale Abwahl muss die mitgelaufenen Kinder im Kanal-Override in denselben Ziel-Bucket (off) mitnehmen',
		);
		assert.deepEqual(next.primary, []);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-4 — individuelle Rueck-Abwahl eines mitgenommenen Kindes bleibt stehen
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-4: individuelle Rueck-Abwahl eines automatisch mitgenommenen Kindes bleibt beim naechsten Laden erhalten (DEC-6)', () => {
	test('Mitnahme, dann individuelle Rueck-Abwahl, dann erneutes Laden OHNE zwischenzeitlichen Elter-Aus/Ein-Zyklus', async () => {
		// Bruecken-Cast rein typseitig auf die echte moveWithDerivedChildren-
		// Signatur (Praezedenz #2276 S4) -- requireFn() bleibt generisch
		// ((...args: never[]) => unknown), ein Mehr-Argument-Aufruf mit
		// String-Literalen braucht sonst 'never' fuer jedes Argument
		// (svelte-check CI-Baseline). Keine Aenderung an Testlogik/Assertions.
		const moveDerived = (await requireFn('moveWithDerivedChildren')) as unknown as (
			b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets,
		) => Buckets;
		const derive = await requireFn('deriveMissingChildMetrics');

		let buckets: Buckets = {
			primary: [],
			secondary: [],
			off: ['wind_chill', 'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'],
		};
		// Schritt 1: Elter wird eingewaehlt, Kinder laufen mit (AC-2).
		buckets = moveDerived(buckets as never, 'wind_chill', 'off', 'primary') as Buckets;
		assert.ok(buckets.primary.includes('wind_chill_day_low'), 'Vorbedingung: Mitnahme muss stattgefunden haben');

		// Schritt 2: Nutzer waehlt wind_chill_day_low individuell wieder ab.
		buckets = move(buckets, 'wind_chill_day_low', 'primary', 'off');
		assert.ok(!buckets.primary.includes('wind_chill_day_low'));

		// Simulierte Speichern-Payload aus diesem Zustand: der Elter und die
		// beiden mitgenommenen Kinder aktiv, wind_chill_day_low explizit aus.
		const gespeichert = [
			{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 0 },
			{ metric_id: 'wind_chill_day_low', enabled: false },
			{ metric_id: 'wind_chill_day_high', enabled: true, bucket: 'primary', order: 1 },
			{ metric_id: 'wind_chill_night', enabled: true, bucket: 'primary', order: 2 },
		];

		// Schritt 3: erneutes Laden derselben (gespeicherten) Liste, OHNE dass
		// der Elter zwischenzeitlich aus- und wieder eingeschaltet wurde.
		const reloaded = derive(gespeichert as never) as Array<{ metric_id: string; enabled: boolean }>;
		const dayLow = reloaded.find((m) => m.metric_id === 'wind_chill_day_low');
		const dayHigh = reloaded.find((m) => m.metric_id === 'wind_chill_day_high');

		assert.ok(dayLow, 'wind_chill_day_low muss im geladenen Ergebnis vorkommen');
		assert.equal(
			dayLow!.enabled, false,
			'DEC-6: die explizite individuelle Abwahl muss beim naechsten Laden respektiert werden -- ' +
			'deriveMissingChildMetrics() darf einen VORHANDENEN expliziten Eintrag nicht ueberschreiben',
		);
		assert.equal(dayHigh!.enabled, true, 'das nicht abgewaehlte Geschwister-Kind bleibt aktiv');
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-5 (Regressionswaechter) — deriveMissingChildMetrics() erfindet keine
// Trip-Kind-IDs, wenn eine Liste mit COMPARE-eigenen Metrik-Schluesseln
// (nicht 'temperature'/'wind_chill') gefuettert wird. Kein Ersatz fuer einen
// echten Test des context="vergleich"-Ladepfads von WeatherMetricsTab.svelte
// -- siehe Bericht: es existiert keine SSR-/Rendering-Harness, um den
// echten Aufrufort zu pruefen (nur source-inspizierende Tests, z.B.
// day_window_card.test.ts). Dieser Test sichert die reine Funktion ab.
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-5 (Regressionswaechter): deriveMissingChildMetrics() erfindet keine Trip-Kind-IDs aus Ortsvergleichs-Schluesseln', () => {
	test('eine compare-typische Liste (wind_chill_min_c statt wind_chill) loest keine der sechs Trip-Kind-IDs aus', async () => {
		const derive = await requireFn('deriveMissingChildMetrics');
		const compareShaped = [
			{ metric_id: 'wind_chill_min_c', enabled: true },
			{ metric_id: 'temp_max_c', enabled: true },
		];
		const out = derive(compareShaped as never) as Array<{ metric_id: string }>;

		for (const id of KIND_IDS) {
			assert.ok(
				!out.some((m) => m.metric_id === id),
				`deriveMissingChildMetrics hat ${id} erfunden, obwohl kein Trip-Elter ('temperature'/'wind_chill') ` +
				`in der Ortsvergleichs-Liste stand.`,
			);
		}
	});
});
