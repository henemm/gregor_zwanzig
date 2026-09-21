// Unit-Tests fuer Issue #223 — newDefaultRule() Helper.
//
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md (Section 2)
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (#1895 Schritt 1)
//
// Ausfuehrung:
//   cd frontend && npm test -- src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newDefaultRule, expandRules, DELTA_ONLY_METRICS } from './alertRuleDefaults.ts';
import type { AlertMetric, AlertRule } from '$lib/types';

test('newDefaultRule: liefert AlertRule mit den Vorgabe-Werten (#1895 Variante A)', () => {
	const rule = newDefaultRule();
	assert.equal(rule.kind, 'delta');
	assert.equal(rule.metric, 'wind_gust');
	assert.equal(rule.threshold, 20);
	assert.equal(rule.delta_window, '6h');
	assert.equal(rule.unit, 'km/h');
	assert.equal(rule.severity, 'warning');
	assert.equal(rule.enabled, true);
});

test('newDefaultRule: liefert eindeutige ID pro Aufruf', () => {
	const a = newDefaultRule();
	const b = newDefaultRule();
	const c = newDefaultRule();
	assert.notEqual(a.id, b.id);
	assert.notEqual(b.id, c.id);
	assert.notEqual(a.id, c.id);
	for (const r of [a, b, c]) {
		assert.equal(typeof r.id, 'string');
		assert.ok(r.id.length > 0);
	}
});

test('newDefaultRule: erzeugt keine geteilten Referenzen (frische Objekte)', () => {
	const a = newDefaultRule();
	const b = newDefaultRule();
	a.threshold = 999;
	assert.equal(b.threshold, 20, 'Mutation an a darf b nicht beeinflussen');
});

// =============================================================================
// #1895 Schritt 1 — expandRules() nach dem Rueckbau der Modus-Auswahl
// =============================================================================
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md
//
// Bis #1895 nahm expandRules() einen Modus ('absolute' | 'delta' | 'both') und
// lieferte je nachdem eine oder zwei Regeln. Die Faelle unten sind die frueheren
// Modus-Faelle aus #179/#297 — auf die einarmige Signatur
// `expandRules(rule, deltaThreshold, deltaWindow)` umgeschrieben, nicht geloescht:
// ohne sie staende die Funktion genau beim Umbau ohne Abdeckung.
//
// Die Breitenabdeckung (jede Metrik, channels, enabled, id) liegt in
// `__tests__/alertRegelNurAenderung.test.ts`. Hier stehen die Zusicherungen, die
// dort NICHT gemessen werden: Parametervorrang, Reinheit, Kollaps der Zweige und
// der Fortbestand von DELTA_ONLY_METRICS.

const basis = (over: Partial<AlertRule> = {}): AlertRule =>
	({
		id: 'regel-basis',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 50,
		unit: 'km/h',
		severity: 'warning',
		enabled: true,
		...over
	}) as AlertRule;

// ex „mode=absolute → eine Rule, kind=absolute (AC-4)" — der Absolut-Zweig ist weg:
// eine Alt-Regel mit kind='absolute' kommt als Aenderungsregel zurueck.
test('expandRules > eine Alt-Regel mit kind=absolute wird zur Aenderungsregel', () => {
	const result = expandRules(basis(), 30, '6h');
	assert.ok(Array.isArray(result), 'Rueckgabe muss Array sein');
	assert.equal(result.length, 1, 'genau eine Regel');
	assert.equal(result[0].kind, 'delta', 'es gibt keinen Absolut-Zweig mehr');
	assert.equal(
		result[0].delta_window,
		'6h',
		'eine Eingangsregel ohne delta_window bekommt eines — eine Δ-Regel ohne Zeitfenster waere unvollstaendig'
	);
});

// ex „mode=delta → eine Rule, kind=delta (AC-4)" + #297 AC-6 (deltaThreshold):
// der uebergebene Δ-Wert gewinnt gegen rule.threshold.
test('expandRules > der uebergebene Δ-Wert gewinnt gegen rule.threshold', () => {
	const result = expandRules(basis({ threshold: 50 }), 30, '6h');
	assert.equal(result.length, 1);
	assert.equal(result[0].threshold, 30, 'die Absolut-Zahl 50 der Alt-Regel darf nicht durchschlagen');
});

// ex #297 AC-7 („delta-Rule traegt delta_window aus Parameter"): das Zeitfenster
// wird durchgereicht und nicht auf den Vorgabewert '6h' festgenagelt.
test('expandRules > das uebergebene Zeitfenster wird durchgereicht', () => {
	const result = expandRules(basis(), 30, '3h');
	assert.equal(result.length, 1);
	assert.equal(result[0].delta_window, '3h', 'nicht auf 6h festgenagelt');
});

// ex #297 F005 („Absolute-Rule darf kein altes delta_window erben"): jetzt in der
// einarmigen Fassung — ein bereits vorhandenes, ABWEICHENDES delta_window auf der
// Eingangsregel darf den Parameter nicht ueberstimmen.
test('expandRules F005 > ein vorhandenes delta_window der Regel ueberstimmt den Parameter nicht', () => {
	const result = expandRules(basis({ kind: 'delta', delta_window: '12h' }), 30, '3h');
	assert.equal(result.length, 1);
	assert.equal(
		result[0].delta_window,
		'3h',
		'F005: der Parameter gewinnt, nicht das alte Feld aus der Eingangsregel'
	);
});

// Vorgabewerte der gefrorenen Signatur: ohne Zusatzargumente gelten
// `rule.threshold` und die Konstante '6h' — NICHT `rule.delta_window`.
test('expandRules > ohne Zusatzargumente gelten rule.threshold und die Konstante 6h', () => {
	const result = expandRules(basis({ kind: 'delta', threshold: 17, delta_window: '12h' }));
	assert.equal(result.length, 1);
	assert.equal(result[0].threshold, 17, 'ohne Δ-Argument faellt die Funktion auf rule.threshold zurueck');
	assert.equal(result[0].delta_window, '6h', 'der Signatur-Vorgabewert ist die Konstante 6h');
});

// ex „mode=both → zwei Rules (AC-5)" / „AC-10 pair-indicator": der Paar-Zweig ist
// fort — es gibt keine Eingabe mehr, die zwei Regeln oder ein pair_id erzeugt.
test('expandRules > kein Eingang erzeugt mehr zwei Regeln oder ein pair_id', () => {
	const eingaben: AlertRule[] = [
		basis(),
		basis({ kind: 'delta' }),
		basis({ pair_id: 'paar-1' }),
		basis({ metric: 'temperature_change' }),
		basis({ metric: 'thunder_level', threshold: 1 }),
		basis({ metric: 'temperature_change', pair_id: 'paar-2' })
	];
	// Anti-Vakuum: eine leergelaufene Liste wuerde die Schleife ueberspringen.
	assert.ok(eingaben.length >= 6, 'Eingabeliste unerwartet kurz — Schleife misst nichts');

	for (const eingabe of eingaben) {
		const result = expandRules(eingabe, 20, '6h');
		assert.equal(result.length, 1, `"${eingabe.metric}": genau eine Regel, nie ein Paar`);
		assert.equal(result[0].kind, 'delta', `"${eingabe.metric}": nur noch Aenderungsregeln`);
		assert.strictEqual(
			result[0].pair_id,
			undefined,
			`"${eingabe.metric}": pair_id darf den Rueckbau nicht ueberleben`
		);
		assert.equal(result[0].id, eingabe.id, `"${eingabe.metric}": die id der Eingangsregel ueberlebt`);
	}
});

// ex „mode=both, delta-only-Metrik → Guard greift (AC-6/AC-8)": der Guard ist
// gegenstandslos, aber die Konstante bleibt exportiert — `alerts-tab/`
// (alertMetricTable.ts, AlertMetricRow.svelte) liest sie weiter.
test('expandRules > DELTA_ONLY_METRICS bleibt exportiert und unveraendert bestueckt', () => {
	const erwartet: AlertMetric[] = [
		'temperature_change',
		'wind_change',
		'precipitation_change',
		'thunder_level'
	];
	assert.equal(DELTA_ONLY_METRICS.size, erwartet.length, 'Umfang der Konstante unveraendert');
	for (const m of erwartet) {
		assert.ok(DELTA_ONLY_METRICS.has(m), `"${m}" muss in DELTA_ONLY_METRICS bleiben`);
	}
	assert.equal(DELTA_ONLY_METRICS.has('wind_gust'), false, 'Boeen sind keine Delta-only-Metrik');
});

// Reinheit: die Eingangsregel bleibt unberuehrt. `AlertRulesEditor` reicht dieselbe
// Regel aus `bind:rules` herein — eine Mutation waere ein stiller Datenschaden.
test('expandRules > mutiert die Eingangsregel nicht', () => {
	const eingabe = basis({ pair_id: 'paar-1', channels: ['email'] });
	const vorher = JSON.stringify(eingabe);
	expandRules(eingabe, 30, '3h');
	assert.equal(JSON.stringify(eingabe), vorher, 'die Eingangsregel darf nicht veraendert werden');
});
