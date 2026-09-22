// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-8: der geteilte
// Versand-Organismus lädt zur Laufzeit NICHT die Compare-Klebeschicht
// (`compare/compareHubWizardBridge.ts`); seine Versand-Helfer kommen aus
// `shared/versandVergleichSpeicherung.ts`. `buildComparePresetSavePayload`
// aus `compare/compareEditorSave.ts` bleibt ausdrücklich erlaubt.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-8, Design Punkt 10
//
// Nachweis über den tatsächlichen Ladegraphen, KEIN Dateiinhalt-/Grep-Check:
// ein Auflösungs-Haken (`module.registerHooks`, in-thread) protokolliert jede
// Modul-URL, die beim Import + SSR-Render von `VersandTab.svelte` im
// `vergleich`-Kontext geladen wird. `import type`-Stellen verschwinden beim
// Übersetzen und tauchen im Ladegraphen nicht auf — sie bleiben zulässig.
//
// RED HEUTE: der Ladegraph enthält `shared/versandVergleichSpeicherung.ts`
// nicht (das Modul existiert nicht, VersandTab bindet es nicht ein).
//
// Mutations-Gegenprobe (Spec AC-8): einen Laufzeit-Re-Import von
// `buildHubPutPayload` aus der alten Bridge einfügen ⇒ die Bridge erscheint im
// Ladegraphen ⇒ rot.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_tab_laedt_keine_compare_klebeschicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

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
const VersandTab = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/VersandTab.svelte')).href)
).default;

const PRESET = {
	id: 'cp-2276-s5-graph',
	name: 'Ortsvergleich Graph',
	location_ids: ['loc-a', 'loc-b', 'loc-c'],
	schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 9,
	empfaenger: [],
	created_at: '2026-01-01T00:00:00Z',
	display_config: {}
};

function wizStub(): Record<string, unknown> {
	return {
		sendEmail: true,
		sendTelegram: true,
		sendSms: false,
		morningEnabled: true,
		morningTime: '06:30',
		eveningEnabled: false,
		eveningTime: '18:00',
		endDate: '2026-08-01',
		alertCooldownMinutes: 45,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00'
	};
}

const BRIDGE = '/src/lib/components/compare/compareHubWizardBridge.ts';
const NEUES_MODUL = '/src/lib/components/shared/versandVergleichSpeicherung.ts';
const NUTZLAST_BAUSTEIN = '/src/lib/components/compare/compareEditorSave.ts';

describe('AC-8: VersandTab lädt zur Laufzeit keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext mit den neuen Speicher-Props', () => {
		const { body } = render(VersandTab, {
			props: {
				context: 'vergleich',
				wiz: wizStub(),
				preset: PRESET,
				onCompareUpdate: () => {},
				enqueueHubWrite: <T>(fn: () => Promise<T>) => fn()
			}
		});
		assert.ok(body.includes('data-testid="versand-tab"'), 'Vorbedingung: der Organismus muss rendern');

		const liste = [...geladen];
		assert.ok(
			liste.some((u) => u.endsWith('/src/lib/components/shared/versand-tab/mergeReportConfig.ts')),
			'Vorbedingung: der Protokoll-Haken muss die Laufzeit-Importe von VersandTab sehen — sonst beweist „Bridge fehlt" nichts'
		);
		assert.ok(
			liste.some((u) => u.endsWith(NEUES_MODUL)),
			'VersandTab muss seine Versand-Speicherhelfer aus shared/versandVergleichSpeicherung.ts laden'
		);
		assert.deepEqual(
			liste.filter((u) => u.endsWith(BRIDGE)),
			[],
			'VersandTab (oder ein von ihm geladenes Modul) lädt compare/compareHubWizardBridge.ts zur Laufzeit'
		);
		assert.ok(
			liste.some((u) => u.endsWith(NUTZLAST_BAUSTEIN)),
			'der Nutzlast-Baustein buildComparePresetSavePayload bleibt erlaubt und muss geladen werden'
		);
	});
});
