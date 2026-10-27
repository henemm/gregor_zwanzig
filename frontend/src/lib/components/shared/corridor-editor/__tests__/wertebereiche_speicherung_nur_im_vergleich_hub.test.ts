// TDD RED — Issue #2276 Scheibe S3 (Epic #2345): die neue Vergleichs-Speicherung
// des Wertebereiche-Editors wird NUR im Ortsvergleich-Hub erzeugt — nicht auf
// der Anlege-Seite und nicht im Trip.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md
//   AC-9  (Anlege-Seite `/compare/new` unverändert: Mount ohne preset/
//          saveController ⇒ neuer Zweig inaktiv, Speichern bleibt wiz.saveNewPreset())
//   AC-12 (Trip-Seite unverändert: der `route`-Zweig löst die
//          Vergleichs-Speicherung nicht aus)
//
// Messbar gemacht über die Erzeugungs-Bedingung als exportiertes Prädikat —
// Muster AlarmeTab.svelte (S2): `untrack(() => context === 'vergleich' && wiz
// && preset && saveController ? erstelle…(…) : null)`. `$effect`/Ereignisse
// laufen in diesem Prüfstand nicht; das Prädikat ist die Stelle, an der die
// Kontext-Prüfung WIRKT, wenn der Editor es für seine `untrack()`-Konstruktion
// benutzt. Zielschnittstelle, die dieser Test festschreibt (existiert noch
// NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
//   wertebereicheVergleichSpeicherungAktiv({ context, zustand, preset, saveController }): boolean
//
// Mutations-Gegenprobe (Spec AC-12): Kontext-Prüfung entfernen ⇒ der
// route-Fall mit sonst vollständigen Props wird true ⇒ rot.
//
// Bestehende Regressionsnachweise, die unverändert grün bleiben müssen (im
// RED-Artefakt mitgelaufen): AC-9 — compare/__tests__/compare_new_preset_payload.test.ts,
// compare/__tests__/compare_wizard_save_new_preset_channels.test.ts;
// AC-12 — shared/__tests__/trip_speicherung_reicht_keepalive_durch.test.ts und die
// Korridor-Kern-Tests unter shared/corridor-editor/ (corridorEditorState.test.ts u. a.).
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/wertebereiche_speicherung_nur_im_vergleich_hub.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { wertebereicheVergleichSpeicherungAktiv } from '../wertebereicheVergleichSpeicherung.ts';
import { createController, hydrierterWs, makePreset } from './wertebereicheVergleichPruefstand.ts';

const preset = makePreset('cp-2276-s3-kontext');
const ws = hydrierterWs(preset);
const saveController = createController('cp-2276-s3-kontext');

describe('Positivfall: Ortsvergleich-Hub', () => {
	test('vergleich + Wizard-Zustand + preset + saveController → Vergleichs-Speicherung aktiv', () => {
		assert.equal(wertebereicheVergleichSpeicherungAktiv({ context: 'vergleich', zustand: ws, preset, saveController }), true);
	});
});

describe('AC-9: Anlege-Seite (/compare/new) — neuer Zweig bleibt inaktiv', () => {
	test('vergleich OHNE preset und OHNE saveController (Mount der Anlege-Seite) → inaktiv', () => {
		assert.equal(
			wertebereicheVergleichSpeicherungAktiv({ context: 'vergleich', zustand: ws, preset: undefined, saveController: undefined }),
			false,
			'auf der Anlege-Seite darf kein zwischenzeitlicher PUT entstehen — Speichern nur über wiz.saveNewPreset()'
		);
	});

	test('vergleich mit saveController, aber ohne preset → inaktiv (keine Basis für einen PUT)', () => {
		assert.equal(
			wertebereicheVergleichSpeicherungAktiv({ context: 'vergleich', zustand: ws, preset: undefined, saveController }),
			false
		);
	});

	test('vergleich mit preset, aber ohne Wizard-Zustand → inaktiv', () => {
		assert.equal(
			wertebereicheVergleichSpeicherungAktiv({ context: 'vergleich', zustand: undefined, preset, saveController }),
			false
		);
	});
});

describe('AC-12: Trip-Seite (route) — Vergleichs-Speicherung wird nie ausgelöst', () => {
	test('route-Kontext mit sonst VOLLSTÄNDIGEN Props → inaktiv (die Kontext-Prüfung allein entscheidet)', () => {
		assert.equal(
			wertebereicheVergleichSpeicherungAktiv({ context: 'route', zustand: ws, preset, saveController }),
			false,
			'der route-Zweig darf die Vergleichs-Speicherung nicht auslösen — er speichert über baueTripSpeicherung'
		);
	});

	test('route-Kontext wie im Trip-Hub gemountet (ohne ws/preset) → inaktiv', () => {
		assert.equal(
			wertebereicheVergleichSpeicherungAktiv({ context: 'route', zustand: undefined, preset: undefined, saveController }),
			false
		);
	});
});
