// TDD RED — Issue #1256 Scheibe 3: Kanäle-Stat-Fidelity im Übersicht-Tab.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 3 (AC-6)
//
// Ist (vor dieser Scheibe): CompareTabs.svelte:270-282 zeigt
// `channelCountLabel(preset.empfaenger.length)` ("2 Kanäle") in der
// "Kanäle"-Stat des Übersicht-Monitoring-Streifens.
// Soll (`screen-compare-detail.jsx:147-150`): Kanal-NAMEN durch " · "
// getrennt ("Email · Telegram"), kein Count. `presetChannels()` liefert
// bereits die richtigen Namen (Email/Telegram/SMS, NIE Signal — PO #610),
// wird aber aktuell nur von der Kachel-Liste konsumiert (CompareTile.svelte),
// nicht vom Hub-Monitoring-Streifen.
//
// `channelNamesLabel()` existiert in subscriptionHelpers.ts noch nicht —
// der Import schlägt heute fehl (RED), bis Phase 6 sie ergänzt (dünner
// Wrapper um presetChannels(), der die "—"-Leerfall-Regel aus dem JSX
// übernimmt: `sub.channels.length === 0 ? "—" : ... .join(" · ")`).
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung, KEIN DOM-Rendering — im Projekt existiert keine
// Svelte-Rendering-Harness, s. Präzedenz corridorEditorMobile.test.ts).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/channel_names_label.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';

const { channelNamesLabel } = await import('../subscriptionHelpers.ts');

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: [],
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		display_config: {},
		...overrides
	};
}

describe('AC-6: channelNamesLabel — Kanal-Namen statt Kanal-Anzahl', () => {
	test('empfaenger=[email] + channel_layouts.telegram → "Email · Telegram" (nicht "2 Kanäle")', () => {
		const preset = makePreset({
			empfaenger: ['urlauber@example.com'],
			display_config: { channel_layouts: { telegram: { columns: ['temp'] } } }
		});
		const label = channelNamesLabel(preset);
		assert.equal(label, 'Email · Telegram', `erwartet "Email · Telegram", war aber "${label}"`);
		assert.doesNotMatch(label, /Kanäle|Kanal\b/, 'darf keine Zahlen-Anzeige ("N Kanäle") mehr sein');
	});

	test('nur E-Mail-Empfänger → "Email" (kein Trennzeichen ohne zweiten Kanal)', () => {
		const preset = makePreset({ empfaenger: ['urlauber@example.com'], display_config: {} });
		const label = channelNamesLabel(preset);
		assert.equal(label, 'Email');
	});

	test('keine Kanäle (leere empfaenger, keine Layouts) → "—" (Soll-Leerfall aus JSX)', () => {
		const preset = makePreset({ empfaenger: [], display_config: {} });
		const label = channelNamesLabel(preset);
		assert.equal(
			label,
			'—',
			`bei 0 Kanälen muss "—" erscheinen (JSX: sub.channels.length === 0 ? "—" : …), war aber "${label}"`
		);
	});

	test('SMS-Layout ohne E-Mail-Empfänger → "SMS" (kein führender/verwaister Trennpunkt)', () => {
		const preset = makePreset({ empfaenger: [], display_config: { channel_layouts: { sms: { columns: [] } } } });
		const label = channelNamesLabel(preset);
		assert.equal(label, 'SMS');
	});

	test('delegiert an presetChannels — Signal-Key im Layout taucht NIEMALS im Label auf (PO #610)', () => {
		const preset = makePreset({
			empfaenger: [],
			display_config: { channel_layouts: { signal: { columns: [] } } }
		});
		const label = channelNamesLabel(preset);
		assert.ok(!label.includes('Signal'), `Label darf "Signal" nie enthalten, war aber "${label}"`);
	});
});
