// Unit-Tests — #1488 Scheibe A, AC-3: expandRules() darf fuer eine Delta-only-
// Metrik NIE eine Regel mit kind='absolute' erzeugen, auch nicht im Modus
// 'absolute'.
//
// Spec: docs/specs/modules/fix_1488_sa_gewitter_absolutregel.md (AC-3)
//
// Warum eine eigene Datei statt einer Erweiterung von
// `../alertRuleDefaults.test.ts`: der Edit-Gate laesst in der RED-Phase nur
// Testverzeichnisse zu (`__tests__/`, `tests/`, `e2e/`), keine co-lokierten
// `*.test.ts` unter `src/` (openspec.yaml -> strict_code_gate).
//
// Warum die PRODUKTIVE Menge `DELTA_ONLY_METRICS` importiert statt einer
// abgeschriebenen Liste: `../alertRuleDefaults.test.ts:61-65` fuehrt eine
// lokale Kopie, die `thunder_level` nicht enthaelt — genau die Drift, die
// diesen Bug ueberhaupt erst hat durchrutschen lassen.
//
// Ausfuehrung:
//   cd frontend && npm test -- \
//     src/lib/components/alert-rules-editor/__tests__/deltaOnlyMetricsAbsolutGesperrt.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	newDefaultRule,
	expandRules,
	DELTA_ONLY_METRICS
} from '../alertRuleDefaults.ts';
import type { AlertRule } from '$lib/types';

test('expandRules > mode=absolute + thunder_level → fällt auf delta zurück (Bugfix #1488 AC-3)', () => {
	const base: AlertRule = { ...newDefaultRule(), metric: 'thunder_level', threshold: 2 };
	const result = expandRules(base, 'absolute', 2, 1, '6h');

	assert.equal(result.length, 1, 'thunder_level bei mode=absolute muss genau 1 Regel liefern');
	assert.equal(
		result[0].kind,
		'delta',
		"Gewitter darf nie als kind='absolute' persistiert werden — die absolute " +
			'Schwelle wird vom Alarm-Dienst nie ausgewertet (#1488 Befund 1)'
	);
	assert.equal(result[0].metric, 'thunder_level');
	assert.equal(result[0].threshold, 1, 'Rueckfall muss die Δ-Schwelle nutzen, nicht die Absolut-Schwelle');
	assert.equal(result[0].delta_window, '6h', 'Δ-Regel braucht ein Zeitfenster');
	assert.strictEqual(result[0].pair_id, undefined, 'Rueckfall-Regel darf kein pair_id tragen');
});

test('expandRules > mode=absolute + jede Delta-only-Metrik → nie kind=absolute (Bugfix #1488 AC-3)', () => {
	// Positivkontrolle zuerst: eine NICHT delta-only Metrik behaelt den
	// Absolut-Modus. Ohne sie waere "kind !== 'absolute'" auch dann erfuellt,
	// wenn expandRules() den absolute-Zweig fuer ALLE Metriken verloeren haette.
	const boeen = expandRules({ ...newDefaultRule(), metric: 'wind_gust' }, 'absolute', 80, 20, '6h');
	assert.equal(boeen.length, 1);
	assert.equal(boeen[0].kind, 'absolute', 'wind_gust muss den Absolut-Modus behalten');
	assert.equal(boeen[0].threshold, 80);

	assert.ok(DELTA_ONLY_METRICS.size >= 4, 'DELTA_ONLY_METRICS darf nicht leer laufen');
	for (const metric of DELTA_ONLY_METRICS) {
		const result = expandRules({ ...newDefaultRule(), metric }, 'absolute', 80, 20, '6h');
		assert.equal(result.length, 1, `Delta-only-Metrik "${metric}" muss genau 1 Regel liefern`);
		assert.equal(
			result[0].kind,
			'delta',
			`Delta-only-Metrik "${metric}" darf bei mode=absolute nicht kind='absolute' erzeugen`
		);
		assert.equal(result[0].delta_window, '6h', `Δ-Regel fuer "${metric}" braucht ein Zeitfenster`);
	}
});
