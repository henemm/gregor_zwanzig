// Issue #1474 Nachtrag (PO-Freigabe 2026-08-03/04): Die Gewitter-Erwaehnungs-
// schwelle im Schwellwerte-Reiter (WeatherMetricsTab.svelte, ThresholdMetricRow
// fuer metricId="thunder") bot bislang nur zwei Knoepfe (MED/HIGH, Werte 1.0/2.0)
// -- ein Rest aus der alten Dreier-Skala (NONE/MED/HIGH). Seit #1474 hat
// ThunderLevel vier Stufen (NONE/LOW/MED/HIGH), Ordinal 1 ist jetzt LOW, nicht
// mehr MED. "MED" stellte also seither faelschlich "ab leicht" ein, "HIGH"
// "ab mittel" -- "ab hoch" war gar nicht mehr erreichbar.
//
// Zielzustand: drei Knoepfe "Leicht"/"Mittel"/"Hoch" mit float 1.0/2.0/3.0
// (passend zu thunder_ordinal() in src/output/metric_format.py).
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup -- daher
// source-inspizierender Test (Praezedenz: day_window_card.test.ts), der aber
// NICHT nur auf String-Praesenz prueft, sondern dieselbe Zuordnungslogik wie
// ThresholdMetricRow.svelte (levels.find(l => l.float === currentFloat)) real
// gegen die aus dem Quelltext extrahierten Level-Objekte ausfuehrt -- eine
// vertauschte Zuordnung (z.B. "Leicht" -> 2.0) wird dadurch rot, nicht nur eine
// fehlende Beschriftung.
//
// Spec: docs/specs/modules/... (Bugfix, keine eigene Spec-Datei; PO-Auftrag
// direkt in der Slice fix-1474-gewitterschwelle-cockpit)
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared
const WEATHER_METRICS_TAB = join(here, '..', '..', 'WeatherMetricsTab.svelte');

interface Level {
	id: string;
	label: string;
	float: number;
}

/**
 * Extrahiert die `levels={[...]}` Liste aus dem ThresholdMetricRow-Block mit
 * `metricId="thunder"`. Bricht bewusst hart (kein Fallback), wenn die Struktur
 * sich so weit aendert, dass der Block nicht mehr auffindbar ist -- ein
 * stiller Leerlisten-Fallback wuerde den Test faelschlich gruen lassen.
 */
function extractThunderLevels(source: string): Level[] {
	const blockStart = source.indexOf('metricId="thunder"');
	assert.ok(blockStart >= 0, 'ThresholdMetricRow mit metricId="thunder" nicht gefunden.');

	const levelsStart = source.indexOf('levels={[', blockStart);
	assert.ok(levelsStart >= 0, 'Kein levels={[...]}-Block nach metricId="thunder" gefunden.');

	const levelsEnd = source.indexOf(']}', levelsStart);
	assert.ok(levelsEnd >= 0, 'levels={[...]}-Block wird nie geschlossen (]} fehlt).');

	const block = source.slice(levelsStart, levelsEnd);

	// Jeder Eintrag: { id: 'xyz', label: 'Xyz', float: N }
	const entryRe = /\{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)',\s*float:\s*([0-9.]+)\s*\}/g;
	const levels: Level[] = [];
	let m: RegExpExecArray | null;
	while ((m = entryRe.exec(block)) !== null) {
		levels.push({ id: m[1], label: m[2], float: Number(m[3]) });
	}
	assert.ok(levels.length > 0, `Keine Level-Eintraege im Block extrahierbar: ${block}`);
	return levels;
}

// Repliziert ThresholdMetricRow.svelte Zeile 27f. (levels.find(l => l.float
// === currentFloat)?.id) -- die tatsaechliche Lauflogik, gegen die extrahierte
// Liste angewandt.
function activeLabelFor(levels: Level[], currentFloat: number): string | undefined {
	return levels.find((l) => l.float === currentFloat)?.label;
}

describe('Gewitter-Schwellwert-Knoepfe (#1474 Nachtrag): drei Stufen, korrekte Werte', () => {
	const source = readFileSync(WEATHER_METRICS_TAB, 'utf-8');
	const levels = extractThunderLevels(source);

	test('genau drei Stufen (nicht mehr die alten zwei)', () => {
		assert.equal(levels.length, 3, `Erwartet 3 Stufen, gefunden: ${JSON.stringify(levels)}`);
	});

	test('"leicht" setzt float 1.0', () => {
		const label = activeLabelFor(levels, 1.0);
		assert.ok(label, 'Kein Level mit float 1.0 gefunden.');
		assert.equal(
			label!.toLowerCase(),
			'leicht',
			`float 1.0 muss auf "leicht" zeigen, zeigt aber auf "${label}".`
		);
	});

	test('"mittel" setzt float 2.0', () => {
		const label = activeLabelFor(levels, 2.0);
		assert.ok(label, 'Kein Level mit float 2.0 gefunden.');
		assert.equal(
			label!.toLowerCase(),
			'mittel',
			`float 2.0 muss auf "mittel" zeigen, zeigt aber auf "${label}".`
		);
	});

	test('"hoch" setzt float 3.0 (bisher gar nicht erreichbar)', () => {
		const label = activeLabelFor(levels, 3.0);
		assert.ok(label, 'Kein Level mit float 3.0 gefunden -- "ab hoch" ist nicht waehlbar.');
		assert.equal(
			label!.toLowerCase(),
			'hoch',
			`float 3.0 muss auf "hoch" zeigen, zeigt aber auf "${label}".`
		);
	});

	test('Bestandswert 1.0 wird nach der Aenderung weiterhin korrekt als "leicht" angezeigt', () => {
		// ThresholdMetricRow.svelte:28 -- levels.find(l => l.float === currentFloat).
		// Bestandstrips speichern nur den Zahlenwert (onChange gibt l.float weiter,
		// nie l.id) -- 1.0/2.0 aus alten Trips muessen weiterhin einen Treffer haben.
		assert.equal(activeLabelFor(levels, 1.0)?.toLowerCase(), 'leicht');
	});

	test('Bestandswert 2.0 wird nach der Aenderung weiterhin korrekt als "mittel" angezeigt', () => {
		assert.equal(activeLabelFor(levels, 2.0)?.toLowerCase(), 'mittel');
	});
});
