// TDD-Begleitung — Issue #1411 (Epic #1372 S4b Scheibe 1), AC-9.
//
// weatherMetricsTabSections.ts selbst aendert sich durch #1411 NICHT
// verhaltensmaessig (kein neuer Abschnitt 'auswertungen' fuer den Vergleich —
// die Mengen-Wahl entsteht INNERHALB 'grundauswahl'). Nur der Code-Kommentar
// an ROUTE_ONLY_SECTIONS wird korrigiert (er verwies bisher auf eine
// ueberholte Vorab-Vermutung "Er zieht mit #1411 nach"). Dieser Test ist
// deshalb bewusst KEIN RED-Nachweis fuer neues Verhalten, sondern die vom
// Test-Plan geforderte eigenstaendige Sections-Funktionsdatei (bisher nur als
// Teil von AC-9 in aggregation_selection.test.ts vorhanden) — er ist heute
// bereits GRUEN und MUSS es bleiben.
//
// Spec: docs/specs/modules/feat_1411_s4b_grundauswahl.md § AC-9
// Kontext: docs/context/feat-1411-s4b-grundauswahl.md
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/weatherMetricsTabSections.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { weatherMetricsTabSections } from '../weatherMetricsTabSections.ts';

describe('#1411 AC-9: Mengen-Wahl bekommt KEINEN eigenen Abschnitt "auswertungen" im Vergleich', () => {
	test("weatherMetricsTabSections('vergleich') enthaelt weiterhin keinen Eintrag 'auswertungen'", () => {
		assert.ok(
			!weatherMetricsTabSections('vergleich').includes('auswertungen'),
			'AC-9 FAIL: der Vergleich zeigt einen dritten Abschnitt "Auswertungen" — die Mengen-Wahl ' +
				'sollte innerhalb von "grundauswahl" entstehen, kein neuer Abschnitt'
		);
	});

	test("'grundauswahl' bleibt fuer beide Kontexte der Ort der Mengen-/Einzelwahl", () => {
		assert.ok(weatherMetricsTabSections('vergleich').includes('grundauswahl'));
		assert.ok(weatherMetricsTabSections('route').includes('grundauswahl'));
	});

	test("'auswertungen' bleibt im Trip-Kontext ('route') bestehen — nur der Vergleich bekommt keinen eigenen Abschnitt", () => {
		assert.ok(weatherMetricsTabSections('route').includes('auswertungen'));
	});
});
