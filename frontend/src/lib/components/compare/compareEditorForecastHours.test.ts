// Compare-Editor — forecast_hours im Save-Payload
//
// Ursprung: Issue #764 (Spec: docs/specs/modules/issue_764_compare_forecast_hours.md)
// Aktualisiert: Issue #1268 (Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md)
//   Der Horizont ist kein Editor-Feld mehr. Die #764-AC-1-Erwartung ("Edit-Wert
//   ueberschreibt den Spread") gilt nicht mehr; die #764-AC-3-Erwartung
//   (Round-Trip ohne Datenverlust) gilt unveraendert weiter und ist jetzt der
//   Bestandsschutz aus #1268 AC-3.
//
// Reine Verhaltenstests auf der Pure-Function `buildComparePresetSavePayload`
// (KEIN Mock, KEINE Dateiinhalt-Prüfung). Sie treiben die Payload-Bildung mit
// echten ComparePreset-Objekten und prüfen das beobachtbare Ergebnis:
//
//   1. GEÄNDERTER Horizont — ein im Editor gewählter forecastHours (z.B. 72)
//      landet im Body als `forecast_hours: 72` und überschreibt den Spread.
//   2. ROUND-TRIP — ohne Horizont-Änderung kommt der gespeicherte Wert aus
//      `original` unverändert durch (kein Reset auf 48).
//
// RED-Erwartung (vor Fix):
//   - `CompareEditorEdits` kennt das Feld `forecastHours` (noch) nicht, und
//     `buildComparePresetSavePayload` setzt `forecast_hours` im Body nicht aus
//     dem Edit-Wert. Übergeben wir forecastHours=72, bleibt im Body der alte
//     Spread-Wert (48) bzw. das Feld fehlt → die 72-Assertion schlägt fehl.
//   - Der TypeScript-Strip-Runner akzeptiert das Zusatzfeld (Strukturtypen);
//     der Verhaltenstest ist der harte RED-Beweis.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorForecastHours.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

// ─── Fixture: echtes ComparePreset mit gespeichertem forecast_hours=72 ───────
function makePreset72(): ComparePreset {
	return {
		id: 'preset-764-xyz',
		name: 'Skitouren Hochkönig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 4,
		profil: 'skitour',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['a@example.com', 'b@example.com'],
		forecast_hours: 72,
		created_at: '2026-06-01T08:00:00Z',
		display_config: { region: 'Salzburger Land' }
	} as ComparePreset;
}

function baseEdits() {
	return {
		name: 'Skitouren Hochkönig',
		activityProfile: 'skitour' as const,
		pickedIds: ['loc-1', 'loc-2'],
		region: 'Salzburger Land',
		idealRanges: {},
	};
}

// ─── Issue #1268: Erwartung gedreht ──────────────────────────────────────────
// Die beiden urspruenglichen AC-1-Tests dieser Datei ("Editor-Horizont 72/24
// landet als forecast_hours im Body") pruefen das #764-Verhalten, das #1268
// bewusst zuruecknimmt: Der Horizont ist kein Editor-Feld mehr, das Frontend
// setzt forecast_hours nicht mehr aus `edits`. Sie sind hier durch den Test
// ersetzt, der die NEUE Erwartung festschreibt — ein etwaiger edits-Wert darf
// den Bestandswert gerade NICHT mehr ueberschreiben.
// Der Round-Trip-Test unten (AC-3) galt vorher wie nachher und bleibt.
describe('buildComparePresetSavePayload — forecast_hours nicht mehr aus dem Editor (#1268 AC-3)', () => {
	test('ein forecastHours-Wert in edits wird ignoriert — Bestandswert bleibt', () => {
		// GIVEN: gespeichertes Preset mit forecast_hours=48
		// WHEN: gespeichert wird (ein Alt-Aufrufer reicht noch forecastHours=72 mit)
		// THEN: der Body traegt den Bestandswert 48 aus dem `...original`-Spread —
		//       der Editor hat keine Hoheit mehr ueber den Horizont (#1268).
		const original = { ...makePreset72(), forecast_hours: 48 } as ComparePreset;
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			forecastHours: 72
		} as Parameters<typeof buildComparePresetSavePayload>[1]);
		assert.equal(
			(body as ComparePreset).forecast_hours,
			48,
			'forecast_hours muss der Bestandswert (48) bleiben — seit #1268 setzt der Editor ihn nicht mehr'
		);
	});
});

describe('buildComparePresetSavePayload — forecast_hours Round-Trip (AC-3)', () => {
	test('ohne Horizont-Änderung kommt der gespeicherte Wert (72) unverändert durch', () => {
		const original = makePreset72(); // forecast_hours=72
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			forecastHours: 72
		});
		assert.equal(
			(body as ComparePreset).forecast_hours,
			72,
			'Round-Trip: gespeicherter 72h-Horizont darf nicht auf 48 zurückfallen'
		);
		// Andere Felder bleiben erhalten (kein Datenverlust)
		assert.deepEqual(body.empfaenger, ['a@example.com', 'b@example.com']);
		assert.equal(body.schedule, 'daily');
	});
});
