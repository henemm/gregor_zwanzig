// TDD RED — Issue #2276 Scheibe S5 (Epic #2345): die neue Versand-Speicherung
// von VersandTab wird NUR im Ortsvergleich-Hub erzeugt — nicht auf der
// Anlege-Seite `/compare/new` (AC-9) und nicht im Trip (AC-12).
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-9, AC-12
//
// Messbar gemacht über die Erzeugungs-Bedingung als exportiertes Prädikat —
// Muster AlarmeTab.svelte (S2) / CorridorEditor.svelte (S3) /
// WeatherMetricsTab.svelte (S4, `wetterMetrikenVergleichSpeicherungAktiv`):
// `untrack(() => context === 'vergleich' && wiz && preset && saveController
// ? erstelle…(…) : null)`. `$effect`/Ereignisse laufen in diesem Prüfstand
// nicht; das Prädikat ist die Stelle, an der die Kontext-Prüfung WIRKT, wenn
// VersandTab es für seine `untrack()`-Konstruktion benutzt.
//
// 🔴 In RED festgelegte Schnittstellen-Entscheidung: die Spec nennt die
// Aktivierungsbedingung im Fließtext (Affected Files, VersandTab-Zeile), führt
// aber keinen eigenen Export dafür auf. Ohne exportiertes Prädikat sind AC-9
// und AC-12 in einer SSR-only-Harness NICHT messbar (ein Dateiinhalt-Grep auf
// die `untrack`-Zeile wäre kein Verhaltensnachweis). S4-Präzedenz übernommen.
//
// Zielschnittstelle (existiert noch NICHT → RED per fehlendem Modul):
//   versandVergleichSpeicherungAktiv({ context, wiz, preset, saveController }): boolean
//
// Mutations-Gegenprobe (Spec AC-9): Aktivierungs-Bedingung entfernen ⇒ die
// Anlege-Seite (ohne preset/saveController) würde einen PUT auslösen ⇒ rot.
// Mutations-Gegenprobe (Spec AC-12): Kontext-Prüfung entfernen ⇒ der
// route-Fall mit sonst vollständigen Props wird true ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_speicherung_nur_im_vergleich_hub.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { versandVergleichSpeicherungAktiv } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset } from './versandVergleichPruefstand.ts';

const preset = makePreset('cp-2276-s5-kontext');
const wiz = hydrierterWiz(preset);
const saveController = createController('cp-2276-s5-kontext');

describe('Positivfall: Ortsvergleich-Hub', () => {
	test('vergleich + Wizard-Zustand + preset + saveController → Versand-Speicherung aktiv', () => {
		assert.equal(versandVergleichSpeicherungAktiv({ context: 'vergleich', wiz, preset, saveController }), true);
	});
});

describe('AC-9: Anlege-Seite (/compare/new) — neuer Zweig bleibt inaktiv', () => {
	test('vergleich OHNE preset und OHNE saveController (Mount der Anlege-Seite) → inaktiv', () => {
		assert.equal(
			versandVergleichSpeicherungAktiv({
				context: 'vergleich',
				wiz,
				preset: undefined,
				saveController: undefined
			}),
			false,
			'auf der Anlege-Seite darf kein zwischenzeitlicher PUT entstehen — Speichern nur über wiz.saveNewPreset()'
		);
	});

	test('vergleich mit saveController, aber ohne preset → inaktiv (keine Basis für einen PUT)', () => {
		assert.equal(
			versandVergleichSpeicherungAktiv({ context: 'vergleich', wiz, preset: undefined, saveController }),
			false
		);
	});

	test('vergleich mit preset, aber ohne Wizard-Zustand → inaktiv', () => {
		assert.equal(
			versandVergleichSpeicherungAktiv({ context: 'vergleich', wiz: undefined, preset, saveController }),
			false
		);
	});
});

describe('AC-12: Trip-Seite (route) — Vergleichs-Speicherung wird nie ausgelöst', () => {
	test('route-Kontext mit sonst VOLLSTÄNDIGEN Props → inaktiv (die Kontext-Prüfung allein entscheidet)', () => {
		assert.equal(
			versandVergleichSpeicherungAktiv({ context: 'route', wiz, preset, saveController }),
			false,
			'der route-Zweig darf die Vergleichs-Orchestrierung nicht auslösen — er speichert über scheduleAutoSave/scheduleReportConfigOnlySave'
		);
	});

	test('route-Kontext wie in BriefingScheduleTab gemountet (ohne wiz/preset) → inaktiv', () => {
		assert.equal(
			versandVergleichSpeicherungAktiv({ context: 'route', wiz: undefined, preset: undefined, saveController }),
			false
		);
	});
});
