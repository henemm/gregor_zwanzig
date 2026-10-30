// Kern-Test — Issue #2347 S3d (AC-1, Trip-Hälfte; PO-Entscheid: Kern-Test statt E2E).
//
// Ein Trip OHNE gespeichertes `official_warnings` (Bestandsdaten vor der Migration
// #1258 — über die API nicht herstellbar: die Neuanlage setzt bewusst
// `enabled=false`, #1258 AC-4 / PO-Entscheidung F1, `internal/handler/trip.go`; ein
// PUT ohne das Feld lässt es unverändert) zeigt im Reiter Alarme den Auslöser
// „Amtliche Warnungen lösen Alert aus" AN — Legacy-Fallback identisch zur Pipeline
// (`official_alert_triggers_enabled !== false`). Und: das Öffnen allein speichert
// nichts (der Selbst-Speicher-Effekt des Trip-Zweigs bereitet keinen PUT vor).
//
// Die Ortsvergleich-Hälfte von AC-1 (Radar-Alarm AUS, Öffnen speichert nichts)
// prüft weiterhin E2E `hub-alarme-wertprops.spec.ts` AW-2b (vergleich).
//
// Kein DOM in der Kernsuite (`$effect` läuft dort nie von selbst) — Wirkort-
// Prüfstand `svelteInstanzPruefstand.ts`, Muster `alarme_tab_create_mode_guard.test.ts`:
// das ECHTE Instanz-Skript von AlarmeTab.svelte wird mit gesäten Props ausgewertet,
// der `checked`-Ausdruck der ECHTEN ChannelToggle-Einbettung gelesen und der ECHTE
// Speicher-Effekt-Rumpf ausgeführt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/alarme_tab_trip_ohne_amtliche_warnungen_zeigt_an_und_speichert_nicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	umgebungFuer,
	effekteVon,
	findeKomponenten,
	attributAusdruck,
	werte,
	type Knoten
} from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TAB = join(HIER, '..', 'AlarmeTab.svelte');
const AUSLOESER_TESTID = 'alerts-tab-official-alert-triggers-toggle';

/** Saat des Trip-Hub-Zweigs (bestehender Trip, kein Anlege-Modus). `trip` trägt
 *  KEIN `official_warnings` — es sei denn, `tripZusatz` setzt es. */
function baueSaat(tripZusatz: Knoten, spion: (...a: unknown[]) => () => Promise<void>): Knoten {
	return {
		context: 'route',
		trip: { id: 'e2e-gz-bestand', display_config: {}, ...tripZusatz },
		createMode: undefined,
		untrack: (fn: () => unknown) => fn(),
		profileOverride: { premium_sms_allowed: false },
		activeMetrics: [],
		metricLevels: {},
		existingChannels: null,
		existingChannelThresholds: null,
		saveController: undefined,
		officialWarningsEnabled: undefined,
		onOfficialWarningsChange: undefined,
		baueTripSpeicherung: spion
	};
}

interface Messung {
	angezeigt: unknown;
	speicherAufrufeBeimOeffnen: number;
	speicherAufrufeNachGeste: number;
}

async function miss(tripZusatz: Knoten): Promise<Messung> {
	const gebaut: unknown[] = [];
	const spion = (...a: unknown[]) => {
		gebaut.push(a);
		return async () => {};
	};
	const { ast, quelle, u } = await umgebungFuer(TAB, baueSaat(tripZusatz, spion));
	assert.strictEqual(
		u.baueTripSpeicherung,
		spion,
		'Messaufbau kaputt: `baueTripSpeicherung` ist nicht der Spion — der Zähler bliebe immer 0.'
	);

	// Anzeige: der `checked`-Ausdruck der ECHTEN Auslöser-Einbettung, gegen die Instanz ausgewertet.
	const einbettungen = findeKomponenten(ast, 'ChannelToggle').filter((k) =>
		((k.attributes ?? []) as Knoten[]).some(
			(a) =>
				a.type === 'Attribute' &&
				a.name === 'testid' &&
				Array.isArray(a.value) &&
				a.value.map((t: Knoten) => t.data ?? '').join('') === AUSLOESER_TESTID
		)
	);
	assert.strictEqual(einbettungen.length, 1, `Messaufbau kaputt: ${einbettungen.length} ChannelToggle mit testid="${AUSLOESER_TESTID}".`);
	const ausdruck = attributAusdruck(einbettungen[0], quelle, 'checked');
	assert.ok(ausdruck, 'Messaufbau kaputt: der Auslöser-Schalter hat kein `checked`-Attribut.');
	const angezeigt = werte(ausdruck!, u);

	// Öffnen: den Speicher-Effekt einmal laufen lassen, OHNE Geste.
	const rueckrufe = effekteVon(ast, quelle, u, '_prevAlarmeJson');
	assert.strictEqual(rueckrufe.length, 1, `Messaufbau kaputt: ${rueckrufe.length} Trip-Alarm-Speicher-Effekte (erwartet 1).`);
	rueckrufe[0]();
	const speicherAufrufeBeimOeffnen = gebaut.length;

	// Gegenprobe (Messaufbau nicht vakuum): eine echte Geste über den ECHTEN Handler speichert.
	(u.handleOfficialWarningsToggle as (an: boolean) => void)(!angezeigt);
	rueckrufe[0]();
	return { angezeigt, speicherAufrufeBeimOeffnen, speicherAufrufeNachGeste: gebaut.length };
}

describe('AC-1 (Trip): Bestands-Trip ohne official_warnings im Reiter Alarme', () => {
	test('zeigt „Amtliche Warnungen lösen Alert aus" AN und das Öffnen bereitet keinen Speichervorgang vor', async () => {
		const m = await miss({});
		assert.strictEqual(
			m.angezeigt,
			true,
			'AC-1 FAIL: ein Trip ohne official_warnings muss den Auslöser AN zeigen (Legacy-Fallback wie die Pipeline).'
		);
		assert.strictEqual(
			m.speicherAufrufeBeimOeffnen,
			0,
			'AC-1 FAIL: das Öffnen des Reiters ohne Geste bereitet einen PUT vor (der Stand würde verändert).'
		);
		assert.strictEqual(
			m.speicherAufrufeNachGeste,
			1,
			'Messaufbau kaputt: eine echte Geste muss genau einen Speichervorgang vorbereiten — sonst prüft „0 beim Öffnen" nichts.'
		);
	});

	test('Gegenprobe: gespeichertes official_warnings.enabled=false zeigt den Auslöser AUS (die Vorgabe greift nur bei fehlendem Feld)', async () => {
		const m = await miss({ official_warnings: { enabled: false } });
		assert.strictEqual(m.angezeigt, false, 'AC-1 FAIL: ein gespeichertes enabled=false muss AUS zeigen.');
		assert.strictEqual(m.speicherAufrufeBeimOeffnen, 0, 'AC-1 FAIL: das Öffnen ohne Geste bereitet einen PUT vor.');
	});

	test('Gegenprobe: Altfeld official_alert_triggers_enabled=false (ohne official_warnings) zeigt AUS', async () => {
		const m = await miss({ official_alert_triggers_enabled: false });
		assert.strictEqual(
			m.angezeigt,
			false,
			'AC-1 FAIL: der Legacy-Fallback muss das Altfeld beachten (official_alert_triggers_enabled=false ⇒ AUS).'
		);
	});
});
