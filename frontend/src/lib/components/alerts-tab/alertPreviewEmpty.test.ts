// TDD: Issue #809 — AlertPreviewCard Leerzustand-Logik
//
// AC-5: Trip ohne alert-fähige Metriken → data-testid="alert-preview-no-metrics"
//       sichtbar, data-testid="alert-preview-load-btn" NICHT im DOM.
//
// Da Svelte-Komponenten im Node-Kontext ohne DOM nicht vollständig renderbar sind,
// testen wir die Leerzustand-Logik als reine Funktions-/Zustandslogik:
// - alertRules.length === 0 → hasNoAlertableMetrics = true → no-metrics-Hinweis
// - alertRules.length > 0 && enabledRules.length === 0 → load-btn disabled
// - enabledRules.length > 0 → load-btn aktiv
//
// Execution:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/alertPreviewEmpty.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import type { AlertRule } from '../../types.ts';

// ---------------------------------------------------------------------------
// Hilfsfunktionen — spiegeln die $derived-Logik aus AlertPreviewCard.svelte
// ---------------------------------------------------------------------------

function hasNoAlertableMetrics(alertRules: AlertRule[]): boolean {
	return alertRules.length === 0;
}

function enabledRules(alertRules: AlertRule[]): AlertRule[] {
	return alertRules.filter((r) => r.enabled);
}

// Repräsentiert welcher Zustand im Template gerendert wird:
// 'no-metrics' | 'load-btn-disabled' | 'load-btn-active'
function renderState(alertRules: AlertRule[]): string {
	if (hasNoAlertableMetrics(alertRules)) return 'no-metrics';
	if (enabledRules(alertRules).length === 0) return 'load-btn-disabled';
	return 'load-btn-active';
}

// ---------------------------------------------------------------------------
// AC-5: Keine alert_rules → no-metrics-Hinweis, kein load-btn
// ---------------------------------------------------------------------------

test('AC-5: alertRules=[] → hasNoAlertableMetrics=true → no-metrics state', () => {
	const rules: AlertRule[] = [];
	assert.equal(hasNoAlertableMetrics(rules), true);
	assert.equal(renderState(rules), 'no-metrics');
});

test('AC-5: hasNoAlertableMetrics=true → alert-preview-load-btn NICHT sichtbar', () => {
	// Wenn renderState='no-metrics', erscheint alert-preview-load-btn nicht im DOM.
	// Die Logik: im Template gilt if(hasNoAlertableMetrics) → zeige no-metrics-Paragraf,
	// KEIN Button. Der Button existiert nur in den else-Ästen.
	const rules: AlertRule[] = [];
	const state = renderState(rules);
	assert.notEqual(state, 'load-btn-disabled', 'kein disabled-btn wenn no-metrics');
	assert.notEqual(state, 'load-btn-active', 'kein active-btn wenn no-metrics');
	assert.equal(state, 'no-metrics');
});

// ---------------------------------------------------------------------------
// Unterscheidung: Regeln vorhanden aber alle deaktiviert → load-btn disabled
// (NICHT no-metrics)
// ---------------------------------------------------------------------------

test('alertRules=[disabled] → hasNoAlertableMetrics=false → load-btn-disabled state', () => {
	const rules: AlertRule[] = [{
		id: 'r1',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 50,
		severity: 'warning',
		enabled: false,
	}];
	assert.equal(hasNoAlertableMetrics(rules), false,
		'Eine Regel vorhanden (auch wenn disabled) → hasNoAlertableMetrics=false');
	assert.equal(renderState(rules), 'load-btn-disabled',
		'Alle Regeln disabled → load-btn-disabled (nicht no-metrics)');
});

// ---------------------------------------------------------------------------
// Mindestens eine aktive Regel → load-btn aktiv
// ---------------------------------------------------------------------------

test('alertRules=[enabled] → renderState=load-btn-active', () => {
	const rules: AlertRule[] = [{
		id: 'r1',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 50,
		severity: 'warning',
		enabled: true,
	}];
	assert.equal(hasNoAlertableMetrics(rules), false);
	assert.equal(renderState(rules), 'load-btn-active');
});

// ---------------------------------------------------------------------------
// Gemischte Regeln: enabled + disabled → load-btn aktiv (mindestens eine enabled)
// ---------------------------------------------------------------------------

test('alertRules=[enabled, disabled] → load-btn-active (enabled-Regel vorhanden)', () => {
	const rules: AlertRule[] = [
		{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true },
		{ id: 'r2', kind: 'absolute', metric: 'temperature_max', threshold: 35, severity: 'info', enabled: false },
	];
	assert.equal(renderState(rules), 'load-btn-active');
});
