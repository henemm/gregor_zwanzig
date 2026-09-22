// TDD RED — Issue #2276 Scheibe S3 (Epic #2345), AC-7: der geteilte
// Wertebereiche-Organismus (CorridorEditor / CorridorEditorMobile) lädt zur
// Laufzeit KEIN Modul aus `compare/compareHubWizardBridge.ts`; seine
// Speicherhelfer kommen aus `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`.
// Ein Laufzeit-Import von `buildComparePresetSavePayload` aus
// `compare/compareEditorSave.ts` bleibt ausdrücklich zulässig (Design Punkt 9).
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md — AC-7
//
// Nachweis über den tatsächlichen Ladegraphen, KEIN Dateiinhalt-/Grep-Check
// (Muster S2: alarme_tab_laedt_keine_compare_klebeschicht.test.ts): ein
// Auflösungs-Haken (`module.registerHooks`, in-thread) protokolliert jede
// Modul-URL, die beim Import + SSR-Render im `vergleich`-Kontext geladen wird.
// `import type` verschwindet beim Übersetzen und bleibt zulässig.
// (Abweichung vom Wortlaut „Mock auf compareHubWizardBridge.ts": ein
// protokollierender Auflösungs-Haken beweist dasselbe, ohne einen Ersatz-Export
// zu erfinden, der die eigene Annahme spiegelt.)
//
// RED HEUTE: der Ladegraph enthält `wertebereicheVergleichSpeicherung.ts` noch
// nicht (das Modul existiert nicht, der Editor bindet es nicht ein).
//
// Mutations-Gegenprobe (Spec): einen Laufzeit-Re-Import der alten
// `flushPendingCorridorSave` aus der Bridge in den Editor (oder in das neue
// Modul) einfügen ⇒ die Bridge erscheint im Ladegraphen ⇒ rot.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/corridor_editor_laedt_keine_compare_klebeschicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> corridor-editor -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

/** Jede URL, die ab hier aufgelöst wird (Ladegraph des Prüflings). */
const geladen = new Set<string>();
registerHooks({
	resolve(specifier, context, nextResolve) {
		const ergebnis = nextResolve(specifier, context);
		geladen.add(ergebnis.url);
		return ergebnis;
	}
});

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const EDITOR_DIR = path.join(FRONTEND, 'src/lib/components/shared/corridor-editor');
const CorridorEditor = (await import(pathToFileURL(path.join(EDITOR_DIR, 'CorridorEditor.svelte')).href)).default;
const CorridorEditorMobile = (await import(pathToFileURL(path.join(EDITOR_DIR, 'CorridorEditorMobile.svelte')).href))
	.default;

const PRESET = {
	id: 'cp-2276-s3-graph',
	name: 'Ortsvergleich Graph',
	location_ids: ['loc-a', 'loc-b', 'loc-c'],
	schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 9,
	empfaenger: [],
	created_at: '2026-01-01T00:00:00Z',
	corridors: [{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true }],
	display_config: { active_metrics: ['wind_max_kmh'], metric_alert_levels: {} }
};

function wsStub(): Record<string, unknown> {
	return {
		isEditMode: true,
		corridors: PRESET.corridors,
		activityProfile: 'wandern',
		idealRanges: { wind_max_kmh: { min: 0, max: 40 } },
		activeMetricKeys: ['wind_max_kmh'],
		metricAlertLevels: {}
	};
}

/** Minimaler Speicher-Controller — nur für den Mount; SSR führt keine Speicherung aus. */
const controllerStub = {
	state: 'idle',
	hasPending: false,
	schedule() {},
	flush: async () => {},
	cancel() {},
	markPristine() {},
	setDirty() {}
};

const BRIDGE = '/src/lib/components/compare/compareHubWizardBridge.ts';
const NEUES_MODUL = '/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts';

function renderVergleich(Komponente: unknown): string {
	const { body } = render(Komponente as never, {
		props: {
			context: 'vergleich',
			saveController: controllerStub,
			preset: PRESET,
			enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
			onCompareUpdate: () => {}
		} as never,
		context: new Map([['compare-wizard-state', wsStub()]])
	});
	return body;
}

describe('AC-7: CorridorEditor(Mobile) lädt zur Laufzeit keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext mit den neuen Speicher-Props (Desktop + Mobile)', () => {
		assert.ok(
			renderVergleich(CorridorEditor).includes('data-testid="corridor-editor-vergleich"'),
			'Vorbedingung: der Desktop-Organismus muss rendern'
		);
		assert.ok(
			renderVergleich(CorridorEditorMobile).includes('corridor-editor'),
			'Vorbedingung: der Mobile-Organismus muss rendern'
		);

		const liste = [...geladen];
		assert.ok(
			liste.some((u) => u.endsWith('/src/lib/components/shared/corridor-editor/corridorEditorState.ts')),
			'Vorbedingung: der Protokoll-Haken muss die Laufzeit-Importe des Editors sehen — sonst beweist „Bridge fehlt" nichts'
		);
		assert.ok(
			liste.some((u) => u.endsWith(NEUES_MODUL)),
			'der Editor muss seine Vergleichs-Speicherhelfer aus shared/corridor-editor/wertebereicheVergleichSpeicherung.ts laden'
		);
		assert.deepEqual(
			liste.filter((u) => u.endsWith(BRIDGE)),
			[],
			'CorridorEditor (oder ein von ihm geladenes Modul) lädt compare/compareHubWizardBridge.ts zur Laufzeit'
		);
	});
});
