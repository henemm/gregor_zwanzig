// Invarianten-Test — Issue #1268 (AC-3): Bestandsdaten-Schutz.
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-3
//       + "Was darf sich NICHT aendern" Invariante 1
//
// #1268 entfernt die Zeitfenster-/Horizont-Eingabefelder aus dem Editor. Damit
// schickt das Frontend `hourFrom`/`hourTo`/`forecastHours` nicht mehr in den
// `edits`. Die 158 Bestands-Presets tragen diese Felder aber weiter in ihrer
// Persistenz — sie duerfen beim Speichern NICHT auf 0/null fallen oder
// verschwinden. Traeger dieser Garantie ist der `{ ...original, ... }`-Spread
// in buildComparePresetSavePayload().
//
// Dies ist ein INVARIANTEN-Test, kein Bug-Repro: er ist schon jetzt gruen, weil
// der Round-Trip-Spread bereits existiert. Sein Zweck ist, GRUEN zu BLEIBEN —
// er faengt, wenn die Implementierung die Felder nicht nur aus `edits`, sondern
// versehentlich auch aus dem Body/Spread entfernt (= Datenverlust). Ohne ihn
// waere der Bestandsschutz beim Aufraeumen ungesichert.
//
// KEIN Mock: echte Pure-Function, echtes Preset-Fixture, echter Payload.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_save_deprecated_fields_roundtrip.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import type { CompareEditorEdits } from '../compareEditorSave.ts';
import type { ComparePreset } from '../../../types.ts';

/** Bestands-Preset, wie es aus data/users/<user>/compare_presets.json kommt:
 *  mit gespeichertem Zeitfenster 10–14 Uhr und Horizont 72 h. */
function bestandsPreset(): ComparePreset {
	return {
		id: 'cp-1268-bestand',
		name: 'Alpen vs Voralpen',
		location_ids: ['ort-a', 'ort-b'],
		schedule: 'daily',
		profil: 'SUMMER_TREKKING' as ComparePreset['profil'],
		hour_from: 10,
		hour_to: 14,
		forecast_hours: 72,
		empfaenger: ['gregor-test@henemm.com'],
		created_at: '2026-01-01T00:00:00Z',
		display_config: { region: 'Tirol', top_n: 3 }
	};
}

/** `edits` nach dem Fix: OHNE hourFrom/hourTo/forecastHours — die Felder
 *  existieren im Editor nicht mehr, also kann sie niemand mehr setzen. */
function editsOhneZeitfenster(): CompareEditorEdits {
	return {
		name: 'Alpen vs Voralpen',
		activityProfile: null,
		pickedIds: ['ort-a', 'ort-b'],
		region: 'Tirol',
		idealRanges: {},
		topN: 3
	};
}

describe('#1268 AC-3: Bestandsdaten-Schutz beim Speichern ohne Zeitfenster-Felder', () => {
	test('AC-3: hour_from/hour_to round-trippen unveraendert aus dem Original-Preset', () => {
		// GIVEN: ein Bestands-Preset mit gespeichertem Zeitfenster 10–14 Uhr
		// WHEN: der Nutzer speichert, ohne dass der Editor hourFrom/hourTo mitschickt
		// THEN: der PUT-Body traegt weiterhin hour_from: 10, hour_to: 14
		const { body } = buildComparePresetSavePayload(bestandsPreset(), editsOhneZeitfenster());

		assert.equal(body.hour_from, 10, 'hour_from wurde nicht aus dem Original round-getrippt — Datenverlust');
		assert.equal(body.hour_to, 14, 'hour_to wurde nicht aus dem Original round-getrippt — Datenverlust');
	});

	test('AC-3: forecast_hours round-trippt unveraendert aus dem Original-Preset', () => {
		// GIVEN: ein Bestands-Preset mit gespeichertem Horizont 72 h
		// WHEN: der Nutzer speichert, ohne dass der Editor forecastHours mitschickt
		// THEN: der PUT-Body traegt weiterhin forecast_hours: 72 (kein Nullen)
		const { body } = buildComparePresetSavePayload(bestandsPreset(), editsOhneZeitfenster());

		assert.equal(
			body.forecast_hours,
			72,
			'forecast_hours wurde nicht aus dem Original round-getrippt — Datenverlust bei 158 Bestands-Presets'
		);
	});

	test('AC-3: die deprecateten Keys werden nicht geloescht oder auf 0/null gesetzt', () => {
		// GIVEN: Bestands-Preset + edits ohne die drei Felder
		// WHEN: der Payload gebaut wird
		// THEN: die Keys sind vorhanden (nicht undefined) und tragen echte Werte —
		//       sonst wuerde der Go-Read-Modify-Write sie zwar retten, aber der
		//       Editor haette den Bestand bereits im Body genullt.
		const { body } = buildComparePresetSavePayload(bestandsPreset(), editsOhneZeitfenster());

		for (const key of ['hour_from', 'hour_to', 'forecast_hours'] as const) {
			assert.ok(
				Object.prototype.hasOwnProperty.call(body, key),
				`Key "${key}" fehlt im PUT-Body — Bestandswert ginge verloren`
			);
			assert.notEqual(body[key], 0, `"${key}" wurde auf 0 genullt statt round-getrippt`);
			assert.notEqual(body[key], null, `"${key}" wurde auf null gesetzt statt round-getrippt`);
		}
	});

	test('AC-3: unbeteiligte Bestandsfelder bleiben ebenfalls unveraendert', () => {
		// GIVEN: ein Bestands-Preset mit Empfaengern und created_at
		// WHEN: gespeichert wird
		// THEN: der Round-Trip-Spread traegt sie mit — Beleg, dass der Spread
		//       (und nicht ein Zufall) die Zeitfenster-Felder oben rettet.
		const { body, url } = buildComparePresetSavePayload(bestandsPreset(), editsOhneZeitfenster());

		assert.equal(url, '/api/compare/presets/cp-1268-bestand');
		assert.deepEqual(body.empfaenger, ['gregor-test@henemm.com']);
		assert.equal(body.created_at, '2026-01-01T00:00:00Z');
	});
});
