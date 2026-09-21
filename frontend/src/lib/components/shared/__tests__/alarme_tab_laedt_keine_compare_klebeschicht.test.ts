// TDD RED — Issue #2276 Scheibe S2 (Epic #2345), AC-9: der geteilte
// Alarme-Organismus lädt zur Laufzeit NICHT die Compare-Klebeschicht
// (`compare/compareHubWizardBridge.ts`); seine Alarm-Helfer kommen aus
// `shared/alarmeVergleichSpeicherung.ts`.
//
// Spec S2: docs/specs/modules/rework_2276_s2_alarme.md — AC-9, § Modul-Verschiebung
// Spec S6c: docs/specs/modules/rework_2276_s6c_alarme.md — AC-5 (Saat + Gegenprobe)
//
// Nachweis über den tatsächlichen Ladegraphen, KEIN Dateiinhalt-/Grep-Check:
// ein Auflösungs-Haken (`module.registerHooks`, in-thread) protokolliert jede
// Modul-URL, die beim Import + SSR-Render von `AlarmeTab.svelte` im
// `vergleich`-Kontext geladen wird. `import type`-Stellen verschwinden beim
// Übersetzen und tauchen im Ladegraphen nicht auf — sie bleiben zulässig.
//
// 🔴 S6c (AC-5), zwei Änderungen:
//   1. Die Saat ist nicht mehr `wiz: wizStub()`, sondern sind die EINZELNEN
//      Wertprops — der Organismus kennt `wiz` nicht mehr. Solange er es noch
//      liest, scheitert der Render hier (das ist der rote Ausgangszustand).
//   2. Eine GEGENPROBE ist dazugekommen. Ohne sie wäre dieser Test nach dem
//      Umbau vakuum-grün: er bewiese dann nur noch, dass ein Objekt ohne
//      `wiz`-Feld rendert — nicht, dass die Bridge fehlt. Die Gegenprobe
//      schleust einen echten Laufzeit-Import der Bridge in eine Kopie von
//      `AlarmeTab.svelte` ein und verlangt, dass der Protokoll-Haken ihn sieht.
//      Die Kopie liegt in `__tests__/` — dort greift der Zählbefehl der
//      HERKUNFT-Ratsche nicht (`grep -v __tests__`), die Kopie kann ihm also
//      keine Fundstellen unterschieben.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_tab_laedt_keine_compare_klebeschicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
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

const PRUEFLING = path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte');
const { render } = await import('svelte/server');
const AlarmeTab = (await import(pathToFileURL(PRUEFLING).href)).default;
/** Der Ladegraph des PRÜFLINGS — eingefroren, BEVOR die Gegenprobe unten die
 *  Bridge absichtlich nachlädt. Damit ist die Aussage „keine Bridge" von der
 *  Ausführungsreihenfolge der Tests unabhängig. */
const HAUPTGRAPH = [...geladen];

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

/** Issue #2276 S6c: die Alarmfelder kommen als EINZELNE Wertprops + Rückrufe
 *  (Ergebnis von `alarmePropsAus(wiz)` am Mount), nicht mehr als `wiz`. */
function alarmProps(): Record<string, unknown> {
	return {
		officialWarningsEnabled: true,
		onOfficialWarningsChange: () => {},
		metricAlertLevels: {},
		onMetricLevelChange: () => {},
		sendTelegram: true,
		sendSms: false,
		sendPremiumSms: false,
		onChannelToggle: () => {},
		channelThresholds: {},
		onThresholdChange: () => {},
		telegramStyle: 'rich',
		onTelegramStyleChange: () => {},
		cooldownMinutes: 30,
		onCooldownChange: () => {},
		quietFrom: '22:00',
		quietTo: '07:00',
		onQuietHoursChange: () => {},
		radarAlertEnabled: false,
		onRadarAlertChange: () => {},
		zonenBezug: 'des ersten Orts'
	};
}

const BRIDGE = '/src/lib/components/compare/compareHubWizardBridge.ts';
const NEUES_MODUL = '/src/lib/components/shared/alarmeVergleichSpeicherung.ts';

describe('AC-9: AlarmeTab lädt zur Laufzeit keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext mit den neuen Wertprops', () => {
		const { body } = render(AlarmeTab, {
			props: {
				context: 'vergleich',
				...alarmProps(),
				catalog: [],
				preset: PRESET,
				onCompareUpdate: () => {},
				enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
				profileOverride: { premium_sms_allowed: false }
			}
		});
		assert.ok(
			body.includes('data-testid="alarme-tab"'),
			'Vorbedingung: der Organismus muss mit den neuen Wertprops rendern'
		);

		assert.ok(
			HAUPTGRAPH.some((u) =>
				u.endsWith('/src/lib/components/shared/alarme-tab/alarmeTabSections.ts')
			),
			'Vorbedingung: der Protokoll-Haken muss die Laufzeit-Importe von AlarmeTab sehen — sonst beweist „Bridge fehlt" nichts'
		);
		assert.ok(
			HAUPTGRAPH.some((u) => u.endsWith(NEUES_MODUL)),
			'AlarmeTab muss seine Alarm-Speicherhelfer aus shared/alarmeVergleichSpeicherung.ts laden'
		);
		assert.deepEqual(
			HAUPTGRAPH.filter((u) => u.endsWith(BRIDGE)),
			[],
			'AlarmeTab (oder ein von ihm geladenes Modul) lädt compare/compareHubWizardBridge.ts zur Laufzeit'
		);
	});

	test('Gegenprobe: ein eingeschleuster Bridge-Import wird gesehen (kein Vakuum-Grün)', async () => {
		// Eine Kopie des echten Prüflings mit EINEM zusätzlichen Wert-Import der
		// Klebeschicht. Sie liegt in `__tests__/`, deshalb werden ihre relativen
		// Spezifizierer um eine Ebene angehoben. Gemessen wird der Ladegraph, nicht
		// der Dateiinhalt — der Import allein genügt, ein Render ist dafür nicht nötig.
		const kopie = path.join(HERE, '__gegenprobe_alarme_tab.svelte');
		try {
			const quelle = readFileSync(PRUEFLING, 'utf-8')
				.replace(/from '\.\.\//g, "from '@@GZ@@/")
				.replace(/from '\.\//g, "from '../")
				.replace(/from '@@GZ@@\//g, "from '../../");
			writeFileSync(
				kopie,
				quelle.replace(
					'<script lang="ts">',
					'<script lang="ts">\n\timport { hydrateAlarmFieldsFromPreset } from ' +
						"'../../compare/compareHubWizardBridge.ts';\n" +
						'\tvoid hydrateAlarmFieldsFromPreset;'
				)
			);
			const vorher = geladen.size;
			await import(pathToFileURL(kopie).href);
			assert.ok(
				geladen.size > vorher,
				'Messaufbau kaputt: der Protokoll-Haken hat beim Laden der Kopie nichts gesehen.'
			);
			assert.ok(
				[...geladen].some((u) => u.endsWith(BRIDGE)),
				'Gegenprobe FAIL: ein echter Laufzeit-Import von compareHubWizardBridge.ts in ' +
					'AlarmeTab.svelte bleibt unbemerkt. Dann bewiese der Test oben nichts mehr — ' +
					'er zeigte nur, dass ein Objekt ohne `wiz`-Feld rendert.'
			);
		} finally {
			rmSync(kopie, { force: true });
		}
	});
});
