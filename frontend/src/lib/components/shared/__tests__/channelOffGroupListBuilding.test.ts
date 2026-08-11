// TDD RED — Issue #1719 Scheibe S3, AC-8 + AC-12: welche Metriken der
// Kanal-Reiter in "aktiv" bzw. "Aus in diesem Kanal" zeigt, und dass die
// Kapplinie nur die aktiven Zeilen zaehlt.
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md
//   Abschnitt 3 ("Welche Metriken die Kanal-Liste zeigt"), AC-8, AC-12.
//   Mutations-Gegenprobe M4 ("Aus-Gruppe aus der Grundauswahl statt aus
//   dem globalen Maximum speisen" MUSS AC-8 rot machen), M7 ("Kapplinie
//   zaehlt Aus-Zeilen mit" MUSS AC-12 rot machen).
//
//   aktiv = channelView(ch).buckets.primary
//   aus   = buckets.primary (GLOBAL) minus aktiv
//
// Kontrakt fuer GREEN: `splitChannelMetricsForDisplay` existiert in
// `../weather-metrics-tab/channelMetricLayouts.ts` heute NICHT -> Import
// wirft Modul-Resolve-Fehler, ALLE Tests dieser Datei scheitern (RED).
// Muster: shared/__tests__/channelMetricLayouts.test.ts.
//
//   splitChannelMetricsForDisplay(
//     globalPrimary: string[],   // buckets.primary der GLOBALEN Grundauswahl
//     channelPrimary: string[],  // channelView(ch).buckets.primary
//   ): { active: string[]; off: string[] }
//     - active = channelPrimary, GEFILTERT auf globalPrimary (eine Metrik,
//       die global nicht (mehr) aktiv ist, darf auch als "aktiv im Kanal"
//       nicht durchschlagen — ADR-0050 Regel 1/2)
//     - off = globalPrimary MINUS active (Reihenfolge wie in globalPrimary)
//     - eine global abgewaehlte Metrik (nicht in globalPrimary) erscheint
//       in KEINER der beiden Listen, auch wenn channelPrimary sie noch
//       (stale) fuehrt
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/channelOffGroupListBuilding.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const { splitChannelMetricsForDisplay } = await import(
	'../weather-metrics-tab/channelMetricLayouts.ts'
);

describe('AC-8: Listenbildung "aktiv" / "Aus in diesem Kanal"', () => {
	test('Normalfall: aktiv = Kanal-Auswahl, aus = globale Auswahl minus aktiv', () => {
		const globalPrimary = ['temperature', 'wind', 'precipitation'];
		const channelPrimary = ['temperature', 'precipitation'];

		const { active, off } = splitChannelMetricsForDisplay(globalPrimary, channelPrimary);

		assert.deepEqual(active, ['temperature', 'precipitation']);
		assert.deepEqual(
			off,
			['wind'],
			'AC-8 FAIL: "wind" ist im Kanal abgewaehlt und global weiterhin aktiv — muss in der Aus-Gruppe erscheinen'
		);
	});

	test('eine global abgewaehlte Metrik erscheint WEDER in aktiv NOCH in aus, auch wenn der Kanal sie (stale) noch fuehrt', () => {
		// "thunder" ist NICHT (mehr) in der globalen Grundauswahl -- der
		// Kanal-Override wurde aber vor der globalen Abwahl angelegt (Copy-
		// on-write) und traegt "thunder" noch in seiner primary-Liste.
		const globalPrimary = ['temperature', 'wind'];
		const channelPrimary = ['temperature', 'wind', 'thunder'];

		const { active, off } = splitChannelMetricsForDisplay(globalPrimary, channelPrimary);

		assert.equal(
			active.includes('thunder'),
			false,
			'AC-8 FAIL (M4-Familie): eine global abgewaehlte Metrik darf ueber einen stale ' +
				'Kanal-Override nicht als "aktiv" zurueckgeholt werden (ADR-0050 Regel 1/2)'
		);
		assert.equal(
			off.includes('thunder'),
			false,
			'AC-8 FAIL: eine global abgewaehlte Metrik darf auch NICHT in der Aus-Gruppe auftauchen — ' +
				'ein Kanal kann sie nicht zurueckholen, es gibt fuer sie ueberhaupt keinen Kanal-Eintrag'
		);
		assert.deepEqual(active, ['temperature', 'wind']);
		assert.deepEqual(off, []);
	});

	test('leere Kanal-Auswahl: alles Globale landet in der Aus-Gruppe', () => {
		const globalPrimary = ['temperature', 'wind', 'precipitation'];
		const channelPrimary: string[] = [];

		const { active, off } = splitChannelMetricsForDisplay(globalPrimary, channelPrimary);

		assert.deepEqual(active, []);
		assert.deepEqual(off, ['temperature', 'wind', 'precipitation']);
	});
});

describe('AC-12: die Kapplinie zaehlt nur aktive Zeilen, nicht die Aus-Gruppe', () => {
	test('9 global aktive Metriken, 7 im Telegram-Reiter aktiv, 2 in der Aus-Gruppe -> aktiv-Zaehlung ist 7, nicht 9', () => {
		const globalPrimary = ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9'];
		const channelPrimary = ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7'];

		const { active, off } = splitChannelMetricsForDisplay(globalPrimary, channelPrimary);

		assert.equal(
			active.length,
			7,
			'AC-12 FAIL: die fuer die Kapplinie massgebliche aktiv-Zaehlung muss NUR die aktiven ' +
				'Zeilen umfassen'
		);
		assert.equal(
			off.length,
			2,
			'AC-12 FAIL: die 2 abgewaehlten Metriken muessen in der Aus-Gruppe stehen, NICHT in der aktiv-Zaehlung'
		);
		assert.notEqual(
			active.length + 0,
			9,
			'AC-12 FAIL (M7-Familie): eine Kapplinie, die weiterhin 9 zaehlt, rechnet die Aus-Gruppe mit'
		);
	});
});
