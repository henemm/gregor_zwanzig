// Bausteintests — #1895 Schritt 1: der Alarmregel-Editor kennt nur noch
// Änderungsregeln. Die Modus-Auswahl „Änderung/Absolut/Beides" faellt weg.
//
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (AC-2, AC-3, AC-7)
//
// Diese Datei ersetzt `deltaOnlyMetricsAbsolutGesperrt.test.ts` (#1488 Scheibe A):
// dessen Zusicherung „Delta-only-Metriken duerfen nie kind='absolute' werden" ist
// gegenstandslos, sobald es den Absolut-Zweig fuer KEINE Metrik mehr gibt.
//
// Warum eine Datei unter `__tests__/` und nicht co-lokiert: der Edit-Gate laesst in
// der RED-Phase nur Testverzeichnisse zu (openspec.yaml -> strict_code_gate).
//
// WAS DIESE DATEI NICHT BEWEIST: die Verdrahtung der `.svelte`-Komponente. Dass die
// Modus-Karten aus der Edit-Card verschwinden und die Kanal-Chips darin stehen
// bleiben, ist nur im Browser messbar — `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`.
//
// Ausfuehrung:
//   cd frontend && npm test -- \
//     src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newDefaultRule, expandRules } from '../alertRuleDefaults.ts';
// Die PRODUKTIVE Metrikliste, keine abgeschriebene Kopie: eine lokale Liste wuerde
// beim naechsten neuen Metrik-Schluessel still veralten und die neue Metrik
// ungeprueft lassen (genau die Drift aus #1488).
import { ALERT_METRIC_LABELS } from '$lib/utils/alertMetricLabels';
import type { AlertMetric, AlertRule } from '$lib/types';

const ALLE_METRIKEN = Object.keys(ALERT_METRIC_LABELS) as AlertMetric[];

// Nach dem Rueckbau traegt expandRules() keinen Modus- und keinen Absolut-Parameter
// mehr (Spec „Implementation Details" Punkt 1): expandRules(rule, deltaThreshold, deltaWindow).
function basisRegel(over: Partial<AlertRule> = {}): AlertRule {
	return {
		id: 'regel-fest-1895',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 42,
		unit: 'km/h',
		severity: 'warning',
		enabled: true,
		...over
	} as AlertRule;
}

// ── AC-7: Vorgabe einer frisch hinzugefuegten Regel ─────────────────────────
test('#1895 AC-7 — newDefaultRule() liefert eine Aenderungsregel (Variante A)', () => {
	const r = newDefaultRule();

	assert.equal(r.kind, 'delta', 'neue Regel muss eine Aenderungsregel sein, sonst zeigt die Zeile weiter „Abs"');
	assert.equal(r.threshold, 20, 'Δ-Schwelle 20 — der bisher im Editor vorbelegte Wert (Variante A)');
	assert.equal(r.delta_window, '6h', 'Zeitfenster 6h — der bisher im Editor vorbelegte Wert');
	assert.equal(r.metric, 'wind_gust', 'Metrik-Vorgabe bleibt Boeen');
	assert.equal(r.enabled, true, 'neue Regel ist aktiv');
	assert.strictEqual(r.pair_id, undefined, 'es gibt keine Paar-Regeln mehr');
});

// ── AC-2: keine Regel geht verloren, keine kommt hinzu ──────────────────────
test('#1895 AC-2 — expandRules() liefert fuer JEDE Metrik genau eine Aenderungsregel', () => {
	// Anti-Vakuum: eine leergelaufene Metrikliste wuerde die Schleife ueberspringen
	// und der Test waere grün, ohne etwas gemessen zu haben.
	assert.ok(
		ALLE_METRIKEN.length >= 9,
		`produktive Metrikliste unerwartet kurz (${ALLE_METRIKEN.length}) — Schleife misst nichts`
	);

	for (const metric of ALLE_METRIKEN) {
		for (const enabled of [true, false]) {
			const eingabe = basisRegel({ metric, enabled, channels: ['email', 'telegram'] });
			const ergebnis = expandRules(eingabe, 20, '6h');

			assert.equal(
				ergebnis.length,
				1,
				`"${metric}" (enabled=${enabled}): genau eine Regel erwartet, nie zwei (Paar) und nie null`
			);
			const r = ergebnis[0];
			assert.equal(r.id, 'regel-fest-1895', `"${metric}": id muss unveraendert bleiben`);
			assert.equal(r.metric, metric, `"${metric}": metric muss unveraendert bleiben`);
			assert.equal(r.enabled, enabled, `"${metric}": enabled muss unveraendert bleiben`);
			assert.deepEqual(
				r.channels,
				['email', 'telegram'],
				`"${metric}": channels muessen unveraendert durchgereicht werden — die Kanalzuordnung ` +
					'ist die einzige verbliebene Wirkung der Regel'
			);
			assert.equal(r.kind, 'delta', `"${metric}": es gibt nur noch Aenderungsregeln`);
			assert.equal(r.threshold, 20, `"${metric}": die uebergebene Δ-Schwelle gewinnt`);
			assert.equal(r.delta_window, '6h', `"${metric}": Δ-Regel braucht ein Zeitfenster`);
			assert.strictEqual(r.pair_id, undefined, `"${metric}": pair_id darf nicht ueberleben`);
		}
	}
});

test('#1895 AC-2 — eine Alt-Regel mit pair_id verliert nur die Paar-Markierung', () => {
	const eingabe = basisRegel({ pair_id: 'paar-alt-1', channels: ['sms'] });
	const ergebnis = expandRules(eingabe, 20, '6h');

	assert.equal(ergebnis.length, 1, 'aus einer Paar-Haelfte wird genau eine Regel');
	assert.strictEqual(ergebnis[0].pair_id, undefined, 'pair_id muss entfallen');
	assert.equal(ergebnis[0].id, 'regel-fest-1895', 'die id ueberlebt');
	assert.equal(ergebnis[0].severity, 'warning', 'severity ueberlebt');
	assert.equal(ergebnis[0].unit, 'km/h', 'unit ueberlebt');
	assert.deepEqual(ergebnis[0].channels, ['sms'], 'channels ueberleben');
});

// ── AC-3 (Bausteinanteil): Kanalzuordnung ueberlebt den Umbau ───────────────
test('#1895 AC-3 — expandRules() reicht channels unveraendert durch', () => {
	// Die Laengen-Zusicherung gehoert in JEDEN Fall: ohne sie liest `[0]` einfach die
	// erste Haelfte eines Regel-Paares, die Kanaele stimmen dort auch — und der Test
	// waere gruen, obwohl aus einer Regel zwei geworden sind.

	// explizit gesetzt
	const gesetzt = expandRules(basisRegel({ channels: ['sms'] }), 20, '6h');
	assert.equal(gesetzt.length, 1, 'genau eine Regel');
	assert.deepEqual(gesetzt[0].channels, ['sms'], 'explizite Kanalliste bleibt exakt erhalten');

	// leer gesetzt — die Vererbung passiert in effectiveAlertChannels(), NICHT hier;
	// expandRules() darf eine leere Liste nicht eigenmaechtig fuellen.
	const leer = expandRules(basisRegel({ channels: [] }), 20, '6h');
	assert.equal(leer.length, 1, 'genau eine Regel');
	assert.deepEqual(leer[0].channels, [], 'leere Kanalliste bleibt leer');

	// gar nicht gesetzt
	const fehlt = expandRules(basisRegel(), 20, '6h');
	assert.equal(fehlt.length, 1, 'genau eine Regel');
	assert.strictEqual(fehlt[0].channels, undefined, 'fehlende Kanalliste wird nicht erfunden');
});

// ── AC-2/AC-7: Vorgabewerte der Signatur ────────────────────────────────────
test('#1895 AC-2 — ohne Zusatzargumente gelten rule.threshold und das Zeitfenster 6h', () => {
	const ergebnis = expandRules(basisRegel({ threshold: 33 }));

	assert.equal(ergebnis.length, 1);
	assert.equal(ergebnis[0].kind, 'delta');
	assert.equal(ergebnis[0].threshold, 33, 'ohne Δ-Schwelle faellt die Funktion auf rule.threshold zurueck');
	assert.equal(ergebnis[0].delta_window, '6h', 'Vorgabe-Zeitfenster ist 6h');
});
