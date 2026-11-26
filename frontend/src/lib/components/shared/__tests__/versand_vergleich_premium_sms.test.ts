// TDD RED — Issue #2293 Scheibe S2 (AC-8, AC-14 Persistenz-Teil), Epic
// #1374/#2345 — löst #2448 mit auf (eigener Premium-SMS-Schalter im
// Versand-Reiter des Ortsvergleichs).
//
// Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
//   Implementation Details Abschnitt 5, AC-8, AC-14 (Persistenz-Teil).
//
// Vor dieser Scheibe hatte der Versand-Reiter im Vergleichs-Zweig KEINEN
// Premium-SMS-Schalter — `VTBriefingChannels` bekam `onPremiumSmsChange` nur
// vom route-Zweig (VersandTab.svelte:373), im vergleich-Zweig
// (VersandTab.svelte:394-409) blieb die Prop weg und der feste
// "bald verfügbar"-Platzhalter stand. `versandPropsAus`/`VersandSnapshot`
// kannten `sendPremiumSms` gar nicht (Klasse-A-Feld fehlte).
//
// RED-Grund heute (gemessen): `versandPropsAus(wiz).sendPremiumSms` und
// `.onSendPremiumSmsChange` existieren nicht (undefined statt Wert/Funktion);
// `baueVersandNutzlast` sendet kein `send_premium_sms`; `VersandTab.svelte`
// bindet `sendPremiumSms`/`onSendPremiumSmsChange` nicht als Props und reicht
// im vergleich-Zweig kein `onPremiumSmsChange` an `VTBriefingChannels` durch.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei aufgelöst.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/versand_vergleich_premium_sms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { hydrateVersandFieldsFromPreset } from '../versandVergleichSpeicherung.ts';
import { findeKomponenten, attributAusdruck, type Knoten } from './svelteInstanzPruefstand.ts';
import type { ComparePreset } from '../../../types.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const VERSAND_TAB = join(SHARED, 'VersandTab.svelte');

function _preset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-2293-ac8',
		name: 'AC8-Test',
		location_ids: ['loc-a'],
		schedule: 'manual',
		profil: 'ALLGEMEIN',
		hour_from: 8,
		hour_to: 17,
		empfaenger: ['a@example.com'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [],
		...overrides
	} as ComparePreset;
}

// #3384 S4: Block „AC-8: versandPropsAus fuehrt sendPremiumSms“ mit der Waise versandPropsAus.ts gelöscht.

// ─── Persistenzweg: VersandSnapshot/Hydration/Nutzlast ─────────────────────

describe('AC-8/AC-14 (Persistenz): sendPremiumSms laeuft durch den ganzen Versand-Speicherweg', () => {
	test('hydrateVersandFieldsFromPreset liest preset.send_premium_sms', () => {
		const preset = _preset({ send_premium_sms: true } as Partial<ComparePreset>);
		const snap = hydrateVersandFieldsFromPreset(preset) as unknown as Record<string, unknown>;
		assert.strictEqual(
			snap.sendPremiumSms,
			true,
			`AC-8: hydrateVersandFieldsFromPreset muss send_premium_sms in sendPremiumSms uebernehmen, erhalten: ${JSON.stringify(snap.sendPremiumSms)}`
		);
	});

	// #3389: die Fälle zu Snapshot, Rollback und Nutzlast des toten Versand-Speicherers entfallen.
	// `send_premium_sms` im PUT und „Versand sendet nie alert_channels“ belegen
	// zustellungSpeicherung.test.ts (ac33, NIE-Liste) und rework_3020_premium_sms_schaltbar.test.ts.
});

// ─── VersandTab.svelte: Premium-SMS-Schalter im vergleich-Zweig freigeschaltet ─

// #3297/#3020: AC-8 (Quelltext von shared/VersandTab) entfaellt — Datei geloescht.
