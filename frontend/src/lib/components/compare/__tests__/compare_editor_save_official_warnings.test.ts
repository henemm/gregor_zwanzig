// TDD RED — Issue #1258 Scheibe S4: Compare-Editor-Integration —
// officialWarnings-Verdrahtung im Save-Payload (AC-27).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-27, Abschnitt 10 "S4-Detail-Festlegungen" E3)
// Context: docs/context/feat-1258-s4-compare-editor.md (E3)
//
// ZIELBILD (noch nicht implementiert — RED bis Phase 6):
//   `CompareEditorEdits` bekommt ein optionales Feld `officialWarnings:
//   { enabled: boolean }` (analog dem Round-Trip-Prinzip aller anderen
//   optionalen Edit-Felder in compareEditorSave.ts). Ist es gesetzt,
//   überschreibt es `body.official_warnings.enabled`, während ein bereits
//   vorhandenes `sources`-Array aus `original.official_warnings` erhalten
//   bleibt (Merge, kein Replace) — das FE schreibt `sources` NIE selbst.
//   Ist das Feld in edits NICHT gesetzt, bleibt `official_warnings`
//   unverändert (Round-Trip via `...original`-Spread).
//
// Heutiger IST-Stand: `CompareEditorEdits` kennt `officialWarnings`
// überhaupt nicht — der Body-Bau ignoriert das Feld vollständig, daher
// bleibt `body.official_warnings` in jedem Fall exakt der Spread-Wert aus
// `original` (nie ein von edits abgeleiteter Wert). Beide Tests unten
// reproduzieren das als klaren Assertion-Mismatch (RED).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_editor_save_official_warnings.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import type { ComparePreset } from '../../../types.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'preset-abc-123',
		name: 'Skitouren Hochkönig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		profil: 'skitour',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['a@example.com'],
		created_at: '2026-06-01T08:00:00Z',
		display_config: { region: 'Salzburger Land' },
		...overrides
	};
}

const baseEditFields = {
	name: 'Skitouren Hochkönig',
	activityProfile: 'skitour' as const,
	pickedIds: ['loc-1', 'loc-2'],
	region: 'Salzburger Land',
	idealRanges: {},
	channelLayouts: null
};

describe('buildComparePresetSavePayload — officialWarnings gesetzt (AC-27)', () => {
	test('Edits mit officialWarnings:{enabled:true} landen als official_warnings.enabled im Body, ohne erfundenes sources-Feld; ohne das Edit-Feld fehlt der Key komplett', () => {
		const original = makePreset();

		// Ohne vorhandenes official_warnings auf original UND ohne das Edit-Feld
		// darf der Key im Body gar nicht existieren.
		const withoutField = buildComparePresetSavePayload(original, { ...baseEditFields });
		assert.ok(
			!Object.prototype.hasOwnProperty.call(withoutField.body, 'official_warnings'),
			'official_warnings darf ohne edits-Feld nicht im Body erscheinen'
		);

		// Mit dem Edit-Feld muss der Body official_warnings:{enabled:true} tragen —
		// KEIN sources-Key, da weder original noch edits ihn liefern.
		const withField = buildComparePresetSavePayload(original, {
			...baseEditFields,
			// GREEN (Phase 6): officialWarnings ist jetzt Teil von CompareEditorEdits.
			officialWarnings: { enabled: true }
		});
		assert.deepEqual(
			withField.body.official_warnings,
			{ enabled: true },
			'official_warnings.enabled muss aus edits übernommen werden, sources bleibt weg'
		);
	});
});

describe('buildComparePresetSavePayload — officialWarnings sendet NIE sources, auch bei vorhandenem Bestand (AC-27, Fix-Loop 1 / Adversary F001)', () => {
	// F001 (Adversary, CRITICAL): die vorherige Fassung dieses Tests erwartete
	// `sources: ['vigilance']` im Body — das war exakt der Clobber-Bug: `original`
	// ist ein Mount-Snapshot, `sources` kann serverseitig zwischenzeitlich anders
	// sein. Spec Abschnitt 10 E3 verlangt: das FE sendet `sources` NIE, der
	// Go-RMW (compare_preset.go:331-342) uebernimmt den Bestand-Merge, wenn der
	// Body den Key gar nicht traegt. Dieser Test ist mit einem original-Bestand
	// `sources !== []` bewusst so gebaut, dass er vor dem Fix ROT gewesen waere
	// (Body haette faelschlich `sources` enthalten).
	test('Toggle auf enabled:false überschreibt nur enabled, sources fehlt im Body vollständig', () => {
		const original = makePreset({
			official_warnings: { enabled: true, sources: ['vigilance'] }
		});

		const { body } = buildComparePresetSavePayload(original, {
			...baseEditFields,
			officialWarnings: { enabled: false }
		});

		assert.deepEqual(
			body.official_warnings,
			{ enabled: false },
			'enabled muss auf false wechseln; sources darf NIEMALS im Body erscheinen (F001-Clobber-Schutz)'
		);
		assert.ok(
			!Object.prototype.hasOwnProperty.call(body.official_warnings ?? {}, 'sources'),
			'official_warnings darf keinen sources-Key tragen, auch wenn original.official_warnings.sources gesetzt war'
		);
	});
});
