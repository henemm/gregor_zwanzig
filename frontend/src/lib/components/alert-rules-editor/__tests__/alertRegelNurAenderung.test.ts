// Bausteintests — #1895: der Alarmregel-Editor kennt nur noch Änderungsregeln
// (Schritt 1) und reicht Δ-Schwelle und Zeitfenster unveraendert durch, weil
// beide Eingaben aus der Karte gefallen sind (Schritt 2).
//
// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md (AC-2, AC-3, AC-7)
// Spec: docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md (AC-3, AC-7)
//
// Diese Datei ersetzt `deltaOnlyMetricsAbsolutGesperrt.test.ts` (#1488 Scheibe A):
// dessen Zusicherung „Delta-only-Metriken duerfen nie kind='absolute' werden" ist
// gegenstandslos, sobald es den Absolut-Zweig fuer KEINE Metrik mehr gibt.
//
// Warum eine Datei unter `__tests__/` und nicht co-lokiert: der Edit-Gate laesst in
// der RED-Phase nur Testverzeichnisse zu (openspec.yaml -> strict_code_gate).
//
// WAS DIESE DATEI NICHT BEWEIST: die Verdrahtung der `.svelte`-Komponente. Dass
// Δ-Schwelle und Zeitfenster aus der Edit-Card verschwinden und die Kanal-Chips
// darin stehen bleiben, ist nur im Browser messbar —
// `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`. Ebenso ungeschuetzt
// bleiben die zwei Zeilen in `AlertRuleRow.svelte`, die `draft` und `synced`
// zusammenbauen (Spec „Restrisiko Verdrahtung", Sichtpruefung im Adversary-Lauf).
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

// Die Zeitfenster-Liste, die der Editor bis Schritt 2 als Auswahl anbot
// (AlertRuleRow.svelte `alert-rule-delta-window`). Sie beschreibt jetzt den
// Wertebereich, den eine Bestandsregel in `delta_window` tragen kann und den
// expandRules() unveraendert durchreichen muss.
const ALLE_ZEITFENSTER = ['1h', '3h', '6h', '12h', '24h'] as const;

// Nach dem Rueckbau von Schritt 2 traegt expandRules() ueberhaupt keine
// Zusatzargumente mehr (Spec E-2): expandRules(rule).
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

// ── AC-7 (Schritt 2): der Weg einer NEUEN Regel durch expandRules() ─────────
// Seit Schritt 2 zeigt die Karte 20/'6h' nirgends mehr an; im Browser ist der
// Wert nicht mehr messbar. Diese Ebene ist damit die einzig moegliche Stelle,
// an der „eine neue Regel behaelt ihre Vorgabewerte ueber das Speichern hinweg"
// noch geprueft werden kann.
test('#1895 S2 AC-7 — eine neue Regel behaelt 20/6h, wenn sie expandRules() durchlaeuft', () => {
	const ergebnis = expandRules(newDefaultRule());

	assert.equal(ergebnis.length, 1, 'genau eine Regel');
	assert.equal(ergebnis[0].kind, 'delta');
	assert.equal(ergebnis[0].threshold, 20, 'die Vorgabe-Schwelle 20 ueberlebt das Speichern');
	assert.equal(ergebnis[0].delta_window, '6h', 'das Vorgabe-Zeitfenster 6h ueberlebt das Speichern');
});

// ── AC-2: keine Regel geht verloren, keine kommt hinzu ──────────────────────
// Der Fixture-Wert ist mit Absicht 42/'12h' und nicht 20/'6h': eine Regel mit
// den Vorgabewerten wuerde auch von einer hart einprogrammierten Konstante
// erfuellt und waere als Nachweis wertlos (Spec AC-3).
test('#1895 AC-2 — expandRules() liefert fuer JEDE Metrik genau eine Aenderungsregel', () => {
	// Anti-Vakuum: eine leergelaufene Metrikliste wuerde die Schleife ueberspringen
	// und der Test waere grün, ohne etwas gemessen zu haben.
	assert.ok(
		ALLE_METRIKEN.length >= 9,
		`produktive Metrikliste unerwartet kurz (${ALLE_METRIKEN.length}) — Schleife misst nichts`
	);

	for (const metric of ALLE_METRIKEN) {
		for (const enabled of [true, false]) {
			const eingabe = basisRegel({
				metric,
				enabled,
				channels: ['email', 'telegram'],
				kind: 'delta',
				threshold: 42,
				delta_window: '12h'
			});
			const ergebnis = expandRules(eingabe);

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
			assert.equal(r.threshold, 42, `"${metric}": die Schwelle der Bestandsregel wird durchgereicht`);
			assert.equal(
				r.delta_window,
				'12h',
				`"${metric}": das Zeitfenster der Bestandsregel wird durchgereicht, nicht auf 6h gesetzt`
			);
			assert.strictEqual(r.pair_id, undefined, `"${metric}": pair_id darf nicht ueberleben`);
		}
	}
});

// ── AC-3 (Schritt 2): jedes Zeitfenster der Auswahlliste ueberlebt ──────────
// Ein Testfall JE Zeitfenster (nicht eine grosse Schleife): node:assert bricht
// beim ersten Fehlschlag ab, ein einziger Fall wuerde nur EINEN AssertionError
// liefern. So steht im Prüfbericht, WELCHES Fenster rot ist — die Spec verlangt
// das ausdruecklich, damit kein Zufallstreffer als Abdeckung zaehlt.
// Der Fall '6h' ist mit Absicht dabei und ist der EINZIGE, der auch von einer
// hart einprogrammierten Konstante erfuellt wuerde — er ist Kontrollgruppe,
// kein Nachweis.
for (const [i, fenster] of ALLE_ZEITFENSTER.entries()) {
	// Schwelle je Fenster verschieden und nie 20: eine auf 20 festgenagelte
	// Schwelle muss in JEDEM dieser Faelle auffliegen.
	const schwelle = 11 + i * 7; // 11, 18, 25, 32, 39 — keiner davon ist 20

	test(`#1895 S2 AC-3 — Zeitfenster '${fenster}' wird fuer jede Metrik durchgereicht (Schwelle ${schwelle})`, () => {
		assert.ok(
			ALLE_METRIKEN.length >= 9,
			`produktive Metrikliste unerwartet kurz (${ALLE_METRIKEN.length}) — Schleife misst nichts`
		);
		assert.notEqual(schwelle, 20, 'die Schwelle darf nicht zufaellig der Vorgabewert 20 sein');

		for (const metric of ALLE_METRIKEN) {
			const ergebnis = expandRules(
				basisRegel({ metric, kind: 'delta', threshold: schwelle, delta_window: fenster })
			);

			assert.equal(ergebnis.length, 1, `"${metric}"/'${fenster}': genau eine Regel`);
			assert.equal(
				ergebnis[0].delta_window,
				fenster,
				`"${metric}": Zeitfenster '${fenster}' muss durchgereicht werden`
			);
			assert.equal(
				ergebnis[0].threshold,
				schwelle,
				`"${metric}": Schwelle ${schwelle} muss durchgereicht werden`
			);
		}
	});
}

test('#1895 AC-2 — eine Alt-Regel mit pair_id verliert nur die Paar-Markierung', () => {
	const eingabe = basisRegel({ pair_id: 'paar-alt-1', channels: ['sms'] });
	const ergebnis = expandRules(eingabe);

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
	const gesetzt = expandRules(basisRegel({ channels: ['sms'] }));
	assert.equal(gesetzt.length, 1, 'genau eine Regel');
	assert.deepEqual(gesetzt[0].channels, ['sms'], 'explizite Kanalliste bleibt exakt erhalten');

	// leer gesetzt — die Vererbung passiert in effectiveAlertChannels(), NICHT hier;
	// expandRules() darf eine leere Liste nicht eigenmaechtig fuellen.
	const leer = expandRules(basisRegel({ channels: [] }));
	assert.equal(leer.length, 1, 'genau eine Regel');
	assert.deepEqual(leer[0].channels, [], 'leere Kanalliste bleibt leer');

	// gar nicht gesetzt
	const fehlt = expandRules(basisRegel());
	assert.equal(fehlt.length, 1, 'genau eine Regel');
	assert.strictEqual(fehlt[0].channels, undefined, 'fehlende Kanalliste wird nicht erfunden');
});

// ── AC-3: Bestandszeitfenster ueberlebt, '6h' nur als Rueckfall ─────────────
// UMGEDREHT gegenueber Schritt 1 („ohne Zusatzargumente gelten rule.threshold
// und das Zeitfenster 6h"): die Konstante '6h' ist kein Vorgabewert der
// Signatur mehr, sondern gilt ausschliesslich fuer eine Regel OHNE Zeitfenster.
test('#1895 S2 AC-3 — Bestandszeitfenster ueberlebt; 6h gilt nur fuer eine Regel ohne Fenster', () => {
	const mitFenster = expandRules(basisRegel({ kind: 'delta', threshold: 33, delta_window: '24h' }));
	assert.equal(mitFenster.length, 1);
	assert.equal(mitFenster[0].kind, 'delta');
	assert.equal(mitFenster[0].threshold, 33, 'die Schwelle der Bestandsregel wird durchgereicht');
	assert.equal(
		mitFenster[0].delta_window,
		'24h',
		'das Zeitfenster der Bestandsregel wird durchgereicht — ein stilles 6h waere Datenverlust'
	);

	// Rueckfall: eine Δ-Regel ohne Zeitfenster waere unvollstaendig, sie bekommt '6h'
	// — und behaelt dabei ihre eigene Schwelle.
	const ohneFenster = expandRules(basisRegel({ kind: 'delta', threshold: 33 }));
	assert.equal(ohneFenster.length, 1);
	assert.equal(ohneFenster[0].delta_window, '6h', 'ohne Zeitfenster greift der Rueckfall 6h');
	assert.equal(ohneFenster[0].threshold, 33, 'der Rueckfall gilt NUR fuer das Zeitfenster');
});
