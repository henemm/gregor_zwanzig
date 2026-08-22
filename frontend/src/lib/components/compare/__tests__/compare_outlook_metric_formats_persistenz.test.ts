// Issue #2049 (Adversary Runde 2, F004/F005) — Speicherpfad der Roh/Einfach-
// Umschaltung im Ortsvergleichs-Editor.
//
// Warum diese Datei: die Umschaltung war bis #2049 eine Attrappe. Der Fix
// verdrahtet sie, aber ZWEI Zusicherungen des Speicherwegs waren unbewacht --
// beide sind aus Nutzersicht genau derselbe Bug wie vorher, nur eine Ebene
// tiefer:
//
//   F004 (Datenverlust): `buildComparePresetSavePayload` merged die bestehende
//        `display_config` (Read-Modify-Write). Ersetzt man das Merge durch ein
//        Replace, gingen beim Umschalten alle anderen Felder des Ortsvergleichs
//        verloren -- die Fehlerklasse BUG-DATALOSS-GR221 (#102), die dieses
//        Projekt schon einmal vier Etappen gekostet hat. Der Code trug das
//        Risiko als Kommentar, kein Test hat es eingeloest.
//
//   F005 (folgenlose Umschaltung): `flushPendingLayoutSave` liefert `null`,
//        wenn sich der Snapshot nicht geaendert hat. Kennt der Diff-Waechter
//        `outlookMetricFormats` nicht, gilt eine REINE Umschaltung als "nichts
//        geaendert", es wird nie ein PUT gesendet -- der Schalter laesst sich
//        umlegen und bleibt folgenlos.
//
// Reine Verhaltenstests, kein Mock: echte ComparePreset-Objekte durch die
// echten Pure Functions, geprueft wird der erzeugte PUT-Payload.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/compare_outlook_metric_formats_persistenz.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import { flushPendingLayoutSave, type LayoutSnapshot } from '../compareHubWizardBridge.ts';
import type { ComparePreset } from '../../../types.ts';

/** Ortsvergleich mit MEHREREN gesetzten `display_config`-Feldern -- nur so
 *  kann ein Replace ueberhaupt auffallen. */
function makePreset(): ComparePreset {
	return {
		id: 'preset-2049-formats',
		name: 'Ortsvergleich Karnischer Hoehenweg',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 3,
		profil: 'wandern',
		hour_from: 6,
		hour_to: 20,
		empfaenger: ['gregor-test@henemm.com'],
		forecast_hours: 72,
		created_at: '2026-08-01T08:00:00Z',
		hourly_enabled: true,
		outlook_enabled: true,
		display_config: {
			region: 'Karnischer Hauptkamm',
			active_metrics: ['temp_max', 'wind_max'],
			hourly_metrics: ['temp_c'],
			outlook_metrics: ['gust', 'sunshine'],
			metric_alert_levels: { wind_max_kmh: 'sensibel' },
			telegram_style: 'kurzform'
		}
	} as ComparePreset;
}

/** Die Felder, die eine reine Roh/Einfach-Umschaltung NICHT anfassen darf. */
const UNBETEILIGTE_FELDER: Record<string, unknown> = {
	active_metrics: ['temp_max', 'wind_max'],
	hourly_metrics: ['temp_c'],
	outlook_metrics: ['gust', 'sunshine'],
	metric_alert_levels: { wind_max_kmh: 'sensibel' },
	telegram_style: 'kurzform'
};

describe('#2049 F004 — Umschalten darf keine anderen display_config-Felder verlieren', () => {
	test('nur outlookMetricFormats editiert -> alle uebrigen Felder round-trippen unveraendert', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'wandern',
			pickedIds: original.location_ids,
			region: 'Karnischer Hauptkamm',
			idealRanges: {},
			// EINZIGE Aenderung: eine Groesse auf "Einfach".
			outlookMetricFormats: { gust: true }
		});

		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(
			dc.outlook_metric_formats,
			{ gust: true },
			'die umgeschaltete Zuordnung fehlt im Payload'
		);
		for (const [key, wert] of Object.entries(UNBETEILIGTE_FELDER)) {
			assert.deepEqual(
				dc[key],
				wert,
				`display_config.${key} ging beim Umschalten verloren oder wurde veraendert ` +
					'-- Read-Modify-Write verletzt (Fehlerklasse #102/BUG-DATALOSS-GR221). ' +
					`Erhaltene display_config: ${JSON.stringify(dc)}`
			);
		}
	});

	test('eine bestehende Zuordnung wird ueberschrieben, nicht ergaenzt', () => {
		// Gegenprobe zur Merge-Richtung: der Editor sendet IMMER die vollstaendige
		// Zuordnung (Read-Modify-Write passiert in der Bedienflaeche). Ein
		// Server-seitiges Zusammenfuehren mit dem Altstand wuerde ein
		// Zuruecksetzen auf "Roh" unmoeglich machen.
		const original = makePreset();
		(original.display_config as Record<string, unknown>).outlook_metric_formats = {
			gust: true,
			sunshine: true
		};
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'wandern',
			pickedIds: original.location_ids,
			region: 'Karnischer Hauptkamm',
			idealRanges: {},
			outlookMetricFormats: { gust: true, sunshine: false }
		});
		assert.deepEqual((body.display_config as Record<string, unknown>).outlook_metric_formats, {
			gust: true,
			sunshine: false
		});
	});

	test('nicht editiert (undefined) -> der gespeicherte Stand bleibt unangetastet', () => {
		const original = makePreset();
		(original.display_config as Record<string, unknown>).outlook_metric_formats = { gust: true };
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'wandern',
			pickedIds: original.location_ids,
			region: 'Karnischer Hauptkamm',
			idealRanges: {}
		});
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).outlook_metric_formats,
			{ gust: true },
			'ein anderer Reiter hat die Roh/Einfach-Zuordnung geloescht (Round-Trip verletzt)'
		);
	});
});

describe('#2049 F005 — eine reine Umschaltung gilt als Aenderung und wird gesendet', () => {
	const basis: LayoutSnapshot = {
		hourlyMetricKeys: ['temp_c'],
		hourlyEnabled: true,
		outlookMetricKeys: ['gust', 'sunshine'],
		outlookMetricFormats: null,
		outlookEnabled: true
	};

	test('NUR outlookMetricFormats geaendert -> Payload entsteht (kein null)', () => {
		const current: LayoutSnapshot = { ...basis, outlookMetricFormats: { gust: true } };
		const payload = flushPendingLayoutSave(makePreset(), current, basis);

		assert.ok(
			payload,
			'flushPendingLayoutSave meldet "nichts geaendert" fuer eine reine ' +
				'Roh/Einfach-Umschaltung -- der Schalter laesst sich umlegen und wird ' +
				'nie gespeichert (F005, exakt der Bug aus #2049 eine Ebene tiefer).'
		);
		assert.deepEqual(
			(payload.body.display_config as Record<string, unknown>).outlook_metric_formats,
			{ gust: true },
			'der erzeugte PUT traegt die neue Zuordnung nicht'
		);
	});

	test('Zuruecknehmen auf Roh ist ebenfalls eine Aenderung', () => {
		const vorher: LayoutSnapshot = { ...basis, outlookMetricFormats: { gust: true } };
		const jetzt: LayoutSnapshot = { ...basis, outlookMetricFormats: { gust: false } };
		const payload = flushPendingLayoutSave(makePreset(), jetzt, vorher);

		assert.ok(payload, 'das Zuruecksetzen auf "Roh" gilt faelschlich als "nichts geaendert"');
		assert.deepEqual(
			(payload.body.display_config as Record<string, unknown>).outlook_metric_formats,
			{ gust: false }
		);
	});

	test('unveraenderter Snapshot bleibt null (kein PUT ohne Aenderung)', () => {
		const gleich: LayoutSnapshot = { ...basis, outlookMetricFormats: { gust: true } };
		assert.equal(
			flushPendingLayoutSave(makePreset(), gleich, { ...gleich }),
			null,
			'der Waechter feuert einen PUT, obwohl sich nichts geaendert hat'
		);
	});
});
