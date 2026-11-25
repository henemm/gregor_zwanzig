// TDD RED — Issue #1703 Scheibe 8: kanal-eigene Metrik-Auswahl der
// Uebersichtstabelle im Ortsvergleich (AC-S8-10, AC-S8-11, Copy-on-write).
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md
//   Abschnitt 4 ("Neues Frontend-Modul compareChannelMetricLayouts.ts"),
//   Abschnitt 3 ("Persistenz-Format"), AC-S8-10, AC-S8-11,
//   Mutations-Gegenproben M4/M5.
// Kontext: docs/context/feat-1703-s8-compare-kanal-tabs.md Risiken 3 + 4.
//
// Befund, den diese Datei rot macht: der Compare-Speicherweg kennt heute NUR
// eine flache Liste (`compareEditorSave.ts:104-130` droppt `channel_layouts`
// sogar aktiv, #1351). `internal/handler/config_merge.go:11-22` ersetzt jeden
// display_config-Top-Level-Key als GANZES und loescht nie einen Key — wer beim
// Speichern nur den zuletzt sichtbaren Kanal serialisiert, verliert die
// uebrigen (M4), und wer eine geleerte Auswahl als weggelassenen Key sendet,
// bekommt still den alten Stand zurueck (M5).
//
// Das Modul `../weather-metrics-tab/compareChannelMetricLayouts.ts` existiert
// noch NICHT -> der Import wirft einen Modul-Resolve-Fehler, ALLE Tests dieser
// Datei scheitern (RED). Muster: shared/__tests__/channelPayloadAllChannels.test.ts.
//
// Kontrakt fuer GREEN (reine Funktionen, kein Svelte-State, kein DOM):
//
//   compareChannelActiveMetricsFromStored(
//     stored: Record<string, StoredActiveMetric[]> | undefined,
//     catalog: CompareSelectionEntry[],
//   ): Record<ChannelId, string[] | null>
//     - Kanal-Key fehlt -> null (nie editiert, folgt der Grundauswahl)
//     - Kanal-Key vorhanden -> Auswahl-Schluessel, [] bleibt []
//
//   mergeAllCompareChannelActiveMetricsForSave(
//     prevStored: Record<string, StoredActiveMetric[]> | undefined,
//     channelOverrides: Record<ChannelId, string[] | null>,
//     catalog: CompareSelectionEntry[],
//   ): Record<ChannelId, StoredActiveMetric[]>
//     - JEDER Eintrag !== null wird serialisiert, nicht nur der aktive Kanal
//     - null -> Wert aus prevStored bleibt unveraendert; mutiert prevStored nicht
//     - [] -> als leeres Array serialisiert, NICHT als fehlender Key
//
//   startCompareChannelOverride(globalKeys: string[]): string[]
//     - Kopie der globalen Reihenfolge als Startpunkt (nicht leer, nicht geteilt)
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compareChannelMetricLayouts.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
// Issue #3276 (Spec-AC-38): `mergeAllCompareChannelActiveMetricsForSave` ist mit dem Schreiben von
// `channel_active_metrics` entfallen (Altschluessel). Die beiden Bloecke AC-S8-10/AC-S8-11, die nur
// diese Schreib-Naht prueften, sind entfernt; dass der Ortsvergleich den Schluessel weder beim
// Anlegen noch beim Speichern sendet, prueft compare/feat3276_vergleich_ohne_altfelder.test.ts.
const { startCompareChannelOverride } = await import('../weather-metrics-tab/compareChannelMetricLayouts.ts');

// Issue #3298: der Block „Hydration: gespeicherter Stand -> Kanal-Overrides" ist mit der
// Lese-Naht `compareChannelActiveMetricsFromStored` entfallen (Altschluessel, ADR-0124).

describe('Copy-on-write: der erste Kanal-Edit startet als Kopie der Grundauswahl', () => {
	test('startet inhaltlich mit der globalen Reihenfolge und teilt ihr Array nicht', () => {
		const globalKeys = ['temp_max_c', 'wind_max_kmh'];

		const override = startCompareChannelOverride(globalKeys);
		assert.deepEqual(override, globalKeys, 'der erste Kanal-Edit darf nicht leer starten');

		override.push('precip_sum_mm');
		assert.deepEqual(
			globalKeys,
			['temp_max_c', 'wind_max_kmh'],
			'FAIL: der Kanal-Override teilt sein Array mit der Grundauswahl — ein SMS-Edit ' +
				'wuerde damit die globale Auswahl und alle anderen Kanaele veraendern'
		);
	});
});
