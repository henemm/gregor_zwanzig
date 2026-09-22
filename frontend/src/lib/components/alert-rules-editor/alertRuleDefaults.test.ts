// Unit-Tests fuer Issue #223 — newDefaultRule() Helper.
//
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md (Section 2)
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (#1895 Schritt 1)
// Spec: docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md (#1895 Schritt 2, AC-3/AC-7)
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
// #1895 Schritt 2 — expandRules(rule) reicht threshold und delta_window durch
// =============================================================================
// Spec: docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md (E-2, AC-3)
//
// Schritt 1 liess expandRules() noch zwei Zusatzargumente nehmen, weil der Editor
// Δ-Schwelle und Zeitfenster als Eingabefelder anbot und sie explizit uebergab.
// Schritt 2 nimmt beide Eingaben aus der Karte. Damit wird aus dem bis dahin
// toten Signatur-Vorgabewert `deltaWindow = '6h'` der EINZIGE Pfad — und der
// erste Speichervorgang wuerde jede Bestandsregel mit z.B. '12h' still auf '6h'
// umschreiben (Klasse BUG-DATALOSS-GR221). Darum reicht die Funktion ab jetzt
// `rule.threshold` und `rule.delta_window` durch; '6h' gilt nur noch als
// Rueckfall fuer eine Regel OHNE Zeitfenster.
//
// Die Breitenabdeckung (jede Metrik, jedes Zeitfenster, channels, enabled, id)
// liegt in `__tests__/alertRegelNurAenderung.test.ts`. Hier stehen die
// Zusicherungen, die dort NICHT gemessen werden: Reinheit, Kollaps der Zweige
// und der Fortbestand von DELTA_ONLY_METRICS.

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
	const result = expandRules(basis());
	assert.ok(Array.isArray(result), 'Rueckgabe muss Array sein');
	assert.equal(result.length, 1, 'genau eine Regel');
	assert.equal(result[0].kind, 'delta', 'es gibt keinen Absolut-Zweig mehr');
	assert.equal(
		result[0].delta_window,
		'6h',
		'eine Eingangsregel ohne delta_window bekommt eines — eine Δ-Regel ohne Zeitfenster waere unvollstaendig'
	);
});

// UMGEDREHT gegenueber Schritt 1 („der uebergebene Δ-Wert gewinnt gegen
// rule.threshold"): es gibt keinen uebergebenen Wert mehr. Die Schwelle der
// Eingangsregel wird unveraendert durchgereicht — das ist E-3 als Test.
// Ein Ueberschreiben auf 20 waere aktive Datenaenderung ohne Nutzerhandlung.
test('expandRules > rule.threshold wird unveraendert durchgereicht (E-3)', () => {
	const result = expandRules(basis({ threshold: 50 }));
	assert.equal(result.length, 1);
	assert.equal(
		result[0].threshold,
		50,
		'die Schwelle der Eingangsregel darf nicht auf den Vorgabewert 20 zurueckgesetzt werden'
	);
});

// UMGEDREHT gegenueber Schritt 1 („das uebergebene Zeitfenster wird
// durchgereicht"): durchgereicht wird jetzt das Fenster DER REGEL.
test('expandRules > das Zeitfenster der Regel wird durchgereicht, nicht auf 6h festgenagelt', () => {
	const result = expandRules(basis({ kind: 'delta', delta_window: '3h' }));
	assert.equal(result.length, 1);
	assert.equal(result[0].delta_window, '3h', 'nicht auf die Konstante 6h festgenagelt');
});

// GESTRICHEN, nicht vergessen: der Fall „expandRules F005 > ein vorhandenes
// delta_window der Regel ueberstimmt den Parameter nicht" (Schritt 1,
// alertRuleDefaults.test.ts:104-115) ist GEGENSTANDSLOS — es gibt keinen
// Parameter mehr, den das Feld ueberstimmen koennte. Seine Zusicherung ist in
// ihr Gegenteil verkehrt und steht als „das Zeitfenster der Regel wird
// durchgereicht" direkt darueber. Bewusst gestrichen (Spec-Tabelle
// „Bestandstests, die sich umdrehen"), nicht stillschweigend geloescht.

// UMGEDREHT gegenueber Schritt 1 („ohne Zusatzargumente gelten rule.threshold
// und die Konstante 6h"): der Signatur-Vorgabewert '6h' ist fort. Wortwoertliches
// Beispiel aus AC-3 der Spec.
test('expandRules > Bestandsregel mit 17/12h behaelt 17 und 12h (AC-3, Spec-Beispiel)', () => {
	const result = expandRules(basis({ kind: 'delta', threshold: 17, delta_window: '12h' }));
	assert.equal(result.length, 1);
	assert.equal(result[0].threshold, 17, 'die Schwelle 17 der Bestandsregel wird durchgereicht');
	assert.equal(
		result[0].delta_window,
		'12h',
		'das Zeitfenster 12h der Bestandsregel wird durchgereicht — NICHT auf die Konstante 6h zurueckgesetzt'
	);
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
		const result = expandRules(eingabe);
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
	const eingabe = basis({ pair_id: 'paar-1', channels: ['email'], delta_window: '3h' });
	const vorher = JSON.stringify(eingabe);
	expandRules(eingabe);
	assert.equal(JSON.stringify(eingabe), vorher, 'die Eingangsregel darf nicht veraendert werden');
});
