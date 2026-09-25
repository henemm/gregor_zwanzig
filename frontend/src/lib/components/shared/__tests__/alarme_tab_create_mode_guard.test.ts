// TDD RED — Issue #2277 Scheibe S1: createMode-Guard für den Selbst-Speicher-
// $effect in AlarmeTab.svelte (route-Zweig). Ohne den Guard löst /trips/new bei
// jeder Kanal-/Schwellen-/Metrik-Stufen-Änderung einen PUT auf
// /api/trips/__new__ aus (stubTrip, Id "__new__" — kein Trip mit dieser Id
// existiert serverseitig).
//
// Spec: docs/specs/modules/fix_2277_s1_alarme_tab_route.md (AC-2)
//
// Kein Mount-/DOM-Test möglich (Kernsuite ist SSR-only, `$effect` läuft dort
// nie von selbst) — Wirkort-Prüfstand `svelteInstanzPruefstand.ts`, Muster
// `compare_alarme_wertprops.test.ts` ("AC-6: Gegenprobe: MIT `trip` plant
// derselbe Rumpf einen Speichervorgang ein").
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/alarme_tab_create_mode_guard.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TAB = join(HIER, '..', 'AlarmeTab.svelte');

/** Minimal-Saat des Trip-Route-Zweigs — Muster `compare_alarme_wertprops.test.ts`
 *  ("Gegenprobe: MIT `trip`"). `saveController: undefined` ist ABSICHTLICH
 *  gesetzt (nicht weggelassen): eine fehlende Prop-Deklaration in der Saat lässt
 *  `with(u)` beim Lesen mit ReferenceError scheitern (Bindungsregel von
 *  `umgebungFuer()`), eine gesetzte mit Wert `undefined` dagegen nicht. */
function baueSaat(zusatz: Knoten): Knoten {
	return {
		context: 'route',
		trip: { id: '__new__', display_config: {} },
		untrack: (fn: () => unknown) => fn(),
		profileOverride: { premium_sms_allowed: false },
		activeMetrics: [],
		metricLevels: {},
		existingChannels: null,
		existingChannelThresholds: null,
		saveController: undefined,
		...zusatz
	};
}

/** Baut die Umgebung, registriert NUR den Alarm-Save-Effekt (Filter
 *  `_prevAlarmeJson` — dieser Bezeichner steht ausschließlich in diesem einen
 *  $effect, nicht im zweiten, unabhängigen vergleich-Speicher-$effect
 *  derselben Datei), mutiert GEZIELT `routeChannelState` (sonst liefert das
 *  JSON-Diff-Gate in AlarmeTab.svelte:416-425 in BEIDEN Fällen 0, weil
 *  `_prevAlarmeJson` aus denselben Saat-Werten berechnet wird wie
 *  `currentJson` — AC-2-Testrezept) und führt den Effekt-Rumpf aus. */
async function baueTripSpeicherungAufrufe(createMode: unknown): Promise<number> {
	const gebaut: unknown[] = [];
	const spion = (...a: unknown[]) => {
		gebaut.push(a);
		return async () => {};
	};
	const { ast, quelle, u } = await umgebungFuer(TAB, baueSaat({ createMode, baueTripSpeicherung: spion }));
	assert.strictEqual(
		u.baueTripSpeicherung,
		spion,
		'Messaufbau kaputt: `baueTripSpeicherung` ist nicht der Spion — der Zähler bliebe immer 0 ' +
			'und der Test wäre vakuum-grün.'
	);
	const rueckrufe = effekteVon(ast, quelle, u, '_prevAlarmeJson');
	assert.strictEqual(
		rueckrufe.length,
		1,
		`Messaufbau kaputt: ${rueckrufe.length} $effect-Rümpfe nennen \`_prevAlarmeJson\` ` +
			'(erwartet: genau einer — der Trip-Alarm-Speicher-Effekt).'
	);
	const routeChannelState = u.routeChannelState as Record<string, boolean>;
	u.routeChannelState = { ...routeChannelState, premium_sms: !routeChannelState.premium_sms };
	gebaut.length = 0;
	rueckrufe[0]();
	return gebaut.length;
}

describe('AC-2: der Selbst-Speicher-Effekt schweigt im Anlege-Modus (createMode)', () => {
	test('createMode=true UND stubTrip (Id "__new__") → baueTripSpeicherung wird NICHT aufgerufen', async () => {
		const zaehler = await baueTripSpeicherungAufrufe(true);
		assert.strictEqual(
			zaehler,
			0,
			'AC-2 FAIL: der Selbst-Speicher-Effekt hat trotz createMode=true einen PUT auf ' +
				'/api/trips/__new__ vorbereitet (baueTripSpeicherung wurde aufgerufen).'
		);
	});

	test('Positiv-Gegenprobe: OHNE createMode bleibt der bestehende Trip-Speicherweg unverändert (1 Aufruf)', async () => {
		const zaehler = await baueTripSpeicherungAufrufe(undefined);
		assert.strictEqual(
			zaehler,
			1,
			'Messaufbau kaputt: ohne createMode muss der bestehende Speicherweg unverändert auf ' +
				'eine Änderung reagieren — sonst prüft der Fall oben (createMode=true) gar nichts.'
		);
	});
});
