// TDD RED — Issue #1250 Scheibe 0: Legacy-CompareSubscription-Stack stilllegen (#1131).
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md § AC-3
//
// AC-3 (#1250): `save()`/`toggleEnabled()` der früheren Anlege-Zustandsklasse waren FE-Totcode —
// sie schrieben in den Legacy-Store `/api/subscriptions`, der mit Scheibe 0 abgeschafft wurde.
//
// Umgebaut für Issue #2727 (Epic #2345, DoD-1) — Spec
// docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md, AC-22: die Klasse ist gelöscht,
// die Zusicherung bleibt AM NEUEN ORT erhalten, und zwar als Verhalten statt als Prototype-Inspektion:
//   (1) Anlegen im ECHTEN Anlege-Editor (Instanz-Prüfstand, ohne Context) sendet keinen einzigen
//       Request an `/api/subscriptions` — Positivkontrolle: der POST an `/api/compare/presets` kommt an.
//   (2) Der Feldsatz, den Editor und Hub halten (`compareFeldsatzStandard()`), trägt keine
//       Speicher-Methoden (`save`, `toggleEnabled`, `saveNewPreset`) — er ist reine Daten.
//
// Warum heute rot: der Editor bekommt seinen Zustand nur über getContext (ohne Context leer),
// `compareFeldsatzStandard` fehlt.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/wizard_state_no_legacy_save.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { neuerFeldsatz } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';
import {
	VERTRAG_FEHLT_EDITOR,
	fetchMitschnitt,
	vergleichEditor
} from '../../shared/__tests__/compareNeuEditorPruefstand.ts';

describe('#1250 AC-3 (am neuen Ort, #2727): kein Legacy-Save gegen /api/subscriptions', () => {
	test('Anlegen im echten Anlege-Editor sendet nichts an /api/subscriptions, nur POST /api/compare/presets', async () => {
		const netz = fetchMitschnitt('cmp-legacy');
		try {
			const e = await vergleichEditor({
				stateOverride: {
					activeTab: 'alarme',
					isMobileViewport: false,
					metrikenVisited: true,
					idealsVisited: true,
					alarmeVisited: true,
					name: 'Legacy-Gegenprobe',
					pickedIds: ['loc-a', 'loc-b']
				}
			});
			assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
			await e.u.handleActivate();
			assert.equal(netz.presetPosts().length, 1, 'Positivkontrolle: POST /api/compare/presets fehlt');
			const legacy = netz.anfragen.filter((a) => a.url.includes('/api/subscriptions'));
			assert.deepEqual(legacy.map((a) => `${a.methode} ${a.url}`), [], 'Legacy-Store /api/subscriptions wird noch beschrieben');
		} finally {
			netz.abbauen();
		}
	});

	test('der Feldsatz trägt keine Speicher-Methoden (save, toggleEnabled, saveNewPreset)', () => {
		const f = neuerFeldsatz();
		assert.ok('name' in f && 'pickedIds' in f, 'Positivkontrolle: Feldsatz ist bestückt');
		for (const methode of ['save', 'toggleEnabled', 'saveNewPreset']) {
			assert.ok(!(methode in f), `Feldsatz trägt ${methode}()`);
		}
	});
});
