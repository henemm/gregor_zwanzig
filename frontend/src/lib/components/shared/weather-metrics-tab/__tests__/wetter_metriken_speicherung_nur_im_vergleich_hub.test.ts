// TDD RED — Issue #2276 Scheibe S4 (Epic #2345): die neue kombinierte
// Vergleichs-Speicherung von WeatherMetricsTab wird NUR im Ortsvergleich-Hub
// erzeugt — nicht auf der Anlege-Seite (AC-10) und nicht im Trip (AC-13).
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md
//   AC-10 (Anlege-Seite `/compare/new` unverändert: Mount ohne preset/
//          saveController ⇒ neuer Zweig inaktiv, Speichern bleibt
//          wiz.saveNewPreset())
//   AC-13 (Trip-Seite unverändert: der route-Zweig löst die
//          Vergleichs-Orchestrierung nicht aus)
//
// Messbar gemacht über die Erzeugungs-Bedingung als exportiertes Prädikat —
// Muster AlarmeTab.svelte (S2) / CorridorEditor.svelte (S3):
// `untrack(() => context === 'vergleich' && wiz && preset && saveController
// ? erstelle…(…) : null)`. `$effect`/Ereignisse laufen in diesem Prüfstand
// nicht; das Prädikat ist die Stelle, an der die Kontext-Prüfung WIRKT, wenn
// WeatherMetricsTab es für seine `untrack()`-Konstruktion benutzt.
//
// Zielschnittstelle (existiert noch NICHT → RED per fehlendem Export):
//
//   frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
//   wetterMetrikenVergleichSpeicherungAktiv({ context, wiz, preset, saveController }): boolean
//
// Mutations-Gegenprobe (AC-13): Kontext-Prüfung entfernen ⇒ der route-Fall
// mit sonst vollständigen Props wird true ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { wetterMetrikenVergleichSpeicherungAktiv } from '../weatherMetricsCompareSave.ts';
import { createController, hydrierterWs, makePreset } from './wetterMetrikenVergleichPruefstand.ts';

const preset = makePreset('cp-2276-s4-kontext');
const wiz = hydrierterWs(preset);
const saveController = createController('cp-2276-s4-kontext');

describe('Positivfall: Ortsvergleich-Hub', () => {
	test('vergleich + Wizard-Zustand + preset + saveController → Vergleichs-Speicherung aktiv', () => {
		assert.equal(wetterMetrikenVergleichSpeicherungAktiv({ context: 'vergleich', zustand: wiz, preset, saveController }), true);
	});
});

describe('AC-10: Anlege-Seite (/compare/new) — neuer Zweig bleibt inaktiv', () => {
	test('vergleich OHNE preset und OHNE saveController (Mount der Anlege-Seite) → inaktiv', () => {
		assert.equal(
			wetterMetrikenVergleichSpeicherungAktiv({
				context: 'vergleich',
				zustand: wiz,
				preset: undefined,
				saveController: undefined
			}),
			false,
			'auf der Anlege-Seite darf kein zwischenzeitlicher PUT entstehen — Speichern nur über wiz.saveNewPreset()'
		);
	});

	test('vergleich mit saveController, aber ohne preset → inaktiv (keine Basis für einen PUT)', () => {
		assert.equal(
			wetterMetrikenVergleichSpeicherungAktiv({ context: 'vergleich', zustand: wiz, preset: undefined, saveController }),
			false
		);
	});

	test('vergleich mit preset, aber ohne Wizard-Zustand → inaktiv', () => {
		assert.equal(
			wetterMetrikenVergleichSpeicherungAktiv({ context: 'vergleich', zustand: undefined, preset, saveController }),
			false
		);
	});
});

describe('AC-13: Trip-Seite (route) — Vergleichs-Speicherung wird nie ausgelöst', () => {
	test('route-Kontext mit sonst VOLLSTÄNDIGEN Props → inaktiv (die Kontext-Prüfung allein entscheidet)', () => {
		assert.equal(
			wetterMetrikenVergleichSpeicherungAktiv({ context: 'route', zustand: wiz, preset, saveController }),
			false,
			'der route-Zweig darf die Vergleichs-Orchestrierung nicht auslösen — er speichert über scheduleAutoSave/scheduleReportConfigOnlySave'
		);
	});

	test('route-Kontext wie im Trip-Hub gemountet (ohne wiz/preset) → inaktiv', () => {
		assert.equal(
			wetterMetrikenVergleichSpeicherungAktiv({ context: 'route', zustand: undefined, preset: undefined, saveController }),
			false
		);
	});
});
