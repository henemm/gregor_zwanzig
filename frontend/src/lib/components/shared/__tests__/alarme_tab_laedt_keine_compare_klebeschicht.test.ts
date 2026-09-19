// TDD RED — Issue #2276 Scheibe S2 (Epic #2345), AC-9: der geteilte
// Alarme-Organismus lädt zur Laufzeit NICHT die Compare-Klebeschicht
// (`compare/compareHubWizardBridge.ts`); seine Alarm-Helfer kommen aus
// `shared/alarmeVergleichSpeicherung.ts`.
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-9, § Modul-Verschiebung
//
// Nachweis über den tatsächlichen Ladegraphen, KEIN Dateiinhalt-/Grep-Check:
// ein Auflösungs-Haken (`module.registerHooks`, in-thread) protokolliert jede
// Modul-URL, die beim Import + SSR-Render von `AlarmeTab.svelte` im
// `vergleich`-Kontext geladen wird. `import type`-Stellen verschwinden beim
// Übersetzen und tauchen im Ladegraphen nicht auf — sie bleiben zulässig.
// (Abweichung vom Wortlaut „Mock auf compareHubWizardBridge.ts": ein
// protokollierender Auflösungs-Haken beweist dasselbe, ohne einen Ersatz-
// Export zu erfinden, der die eigene Annahme spiegelt.)
//
// RED HEUTE: der Ladegraph enthält `shared/alarmeVergleichSpeicherung.ts` noch
// nicht (das Modul existiert nicht, AlarmeTab bindet es nicht ein).
//
// Mutations-Gegenprobe (Spec): einen Laufzeit-Re-Import von
// `flushPendingAlarmSave` aus der alten Bridge in AlarmeTab.svelte einfügen ⇒
// die Bridge erscheint im Ladegraphen ⇒ rot.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_tab_laedt_keine_compare_klebeschicht.test.ts

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
const AlarmeTab = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href)
).default;

const PRESET = {
	id: 'cp-2276-graph',
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
		officialWarningsEnabled: true,
		radarAlertEnabled: false,
		activeMetricKeys: null,
		metricAlertLevels: {},
		sendTelegram: true,
		sendSms: false,
		sendPremiumSms: false,
		channelThresholds: {},
		telegramStyle: 'rich',
		alertCooldownMinutes: 30,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00'
	};
}

const BRIDGE = '/src/lib/components/compare/compareHubWizardBridge.ts';
const NEUES_MODUL = '/src/lib/components/shared/alarmeVergleichSpeicherung.ts';

describe('AC-9: AlarmeTab lädt zur Laufzeit keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext mit den neuen Speicher-Props', () => {
		const { body } = render(AlarmeTab, {
			props: {
				context: 'vergleich',
				wiz: wizStub(),
				catalog: [],
				preset: PRESET,
				onCompareUpdate: () => {},
				enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
				profileOverride: { premium_sms_allowed: false }
			}
		});
		assert.ok(body.includes('data-testid="alarme-tab"'), 'Vorbedingung: der Organismus muss rendern');

		const liste = [...geladen];
		assert.ok(
			liste.some((u) => u.endsWith('/src/lib/components/shared/alarme-tab/alarmeTabSections.ts')),
			'Vorbedingung: der Protokoll-Haken muss die Laufzeit-Importe von AlarmeTab sehen — sonst beweist „Bridge fehlt" nichts'
		);
		assert.ok(
			liste.some((u) => u.endsWith(NEUES_MODUL)),
			'AlarmeTab muss seine Alarm-Speicherhelfer aus shared/alarmeVergleichSpeicherung.ts laden'
		);
		assert.deepEqual(
			liste.filter((u) => u.endsWith(BRIDGE)),
			[],
			'AlarmeTab (oder ein von ihm geladenes Modul) lädt compare/compareHubWizardBridge.ts zur Laufzeit'
		);
	});
});
