// TDD RED: Epic #138 Phase 2 — Metriken-Editor UI-Komponenten (Issues #174–178)
//
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md
//
// Tests scheitern absichtlich (RED): metricsEditor.ts existiert noch nicht.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/metricsEditor.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	INDICATOR_MAP,
	indicatorCapable,
	buildDirtySnapshot,
	isDirty,
	countActiveInCategory,
	buildPresetSummary,
	selectTableColumns,
} from './metricsEditor.ts';

// TDD RED: Issue #364 (Schritt B von #361) — Bucket-Editor-Logik.
// Spec: docs/specs/modules/issue_364_metrics_editor_buckets.md (AC-1..AC-8).
// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx.
//
// Diese Importe zielen auf NOCH NICHT existierende Exporte aus
// metricsEditor.ts → in der RED-Phase schlägt der Import fehl (undefined),
// jeder #364-Test ist rot. KEINE Mocks (pure functions).
import * as editor from './metricsEditor.ts';

// =============================================================================
// §4 INDICATOR_MAP — 12 Metriken (AC-4)
// =============================================================================

test('INDICATOR_MAP > hat genau 12 Eintraege', () => {
	assert.equal(Object.keys(INDICATOR_MAP).length, 12);
});

test('INDICATOR_MAP > enthaelt die 9 backend-eligible Metriken', () => {
	const backendEligible = [
		'wind_direction', 'thunder', 'cape',
		'cloud_total', 'cloud_low', 'cloud_mid', 'cloud_high',
		'visibility', 'sunshine',
	];
	for (const id of backendEligible) {
		assert.ok(id in INDICATOR_MAP, `${id} fehlt in INDICATOR_MAP`);
	}
});

test('INDICATOR_MAP > enthaelt die 3 frontend-erweiterten Metriken', () => {
	assert.ok('wind' in INDICATOR_MAP, 'wind fehlt');
	assert.ok('gust' in INDICATOR_MAP, 'gust fehlt');
	assert.ok('rain_probability' in INDICATOR_MAP, 'rain_probability fehlt');
});

test('INDICATOR_MAP > wind hat Skala ruhig/maessig/stark/sturm', () => {
	assert.ok(INDICATOR_MAP['wind'].includes('ruhig'), 'erwartet "ruhig" in wind-Skala');
	assert.ok(INDICATOR_MAP['wind'].includes('sturm'), 'erwartet "sturm" in wind-Skala');
});

test('INDICATOR_MAP > temperature ist NICHT enthalten', () => {
	assert.equal('temperature' in INDICATOR_MAP, false);
});

test('INDICATOR_MAP > precipitation ist NICHT enthalten', () => {
	assert.equal('precipitation' in INDICATOR_MAP, false);
});

// =============================================================================
// indicatorCapable — Wrapper ueber INDICATOR_MAP (AC-4)
// =============================================================================

test('indicatorCapable > gibt true fuer wind_direction', () => {
	assert.equal(indicatorCapable('wind_direction'), true);
});

test('indicatorCapable > gibt true fuer wind (frontend-erweitert)', () => {
	assert.equal(indicatorCapable('wind'), true);
});

test('indicatorCapable > gibt false fuer temperature', () => {
	assert.equal(indicatorCapable('temperature'), false);
});

test('indicatorCapable > gibt false fuer unbekannte ID', () => {
	assert.equal(indicatorCapable('nonexistent_metric'), false);
});

// =============================================================================
// dirty-State — buildDirtySnapshot + isDirty (AC-1, AC-2)
// =============================================================================

test('buildDirtySnapshot > serialisiert enabledMap und friendlyMap', () => {
	const enabledMap = { temperature: true, wind: false };
	const friendlyMap = { wind_direction: true };
	const snapshot = buildDirtySnapshot(enabledMap, friendlyMap);
	assert.equal(typeof snapshot, 'string');
	const parsed = JSON.parse(snapshot);
	assert.deepEqual(parsed.enabledMap, enabledMap);
	assert.deepEqual(parsed.friendlyMap, friendlyMap);
});

test('isDirty > false wenn enabledMap und friendlyMap unveraendert', () => {
	const enabledMap = { temperature: true, wind: false };
	const friendlyMap = { wind_direction: true };
	const snapshot = buildDirtySnapshot(enabledMap, friendlyMap);
	assert.equal(isDirty(enabledMap, friendlyMap, snapshot), false);
});

test('isDirty > true wenn enabledMap geaendert', () => {
	const orig = { temperature: true, wind: false };
	const origFriendly = { wind_direction: true };
	const snapshot = buildDirtySnapshot(orig, origFriendly);
	const changed = { temperature: false, wind: false }; // temperature geaendert
	assert.equal(isDirty(changed, origFriendly, snapshot), true);
});

test('isDirty > true wenn friendlyMap geaendert', () => {
	const origEnabled = { temperature: true };
	const origFriendly = { wind_direction: true };
	const snapshot = buildDirtySnapshot(origEnabled, origFriendly);
	const changedFriendly = { wind_direction: false }; // false statt true
	assert.equal(isDirty(origEnabled, changedFriendly, snapshot), true);
});

test('isDirty > false bei leerem Snapshot (initialer Zustand)', () => {
	const enabledMap = { temperature: true };
	const friendlyMap = {};
	const snapshot = buildDirtySnapshot(enabledMap, friendlyMap);
	assert.equal(isDirty(enabledMap, friendlyMap, snapshot), false);
});

// =============================================================================
// countActiveInCategory — MetricGroup-Zaehler (AC-3, AC-8)
// =============================================================================

test('countActiveInCategory > zaehlt aktivierte Metriken in einer Kategorie', () => {
	const metricIds = ['temperature', 'wind_chill', 'humidity'];
	const enabledMap = { temperature: true, wind_chill: false, humidity: true };
	assert.equal(countActiveInCategory(metricIds, enabledMap), 2);
});

test('countActiveInCategory > gibt 0 zurueck wenn keine aktiv', () => {
	const metricIds = ['temperature', 'wind_chill'];
	const enabledMap = { temperature: false, wind_chill: false };
	assert.equal(countActiveInCategory(metricIds, enabledMap), 0);
});

test('countActiveInCategory > gibt totalCount zurueck wenn alle aktiv', () => {
	const metricIds = ['temperature', 'wind_chill'];
	const enabledMap = { temperature: true, wind_chill: true };
	assert.equal(countActiveInCategory(metricIds, enabledMap), 2);
});

test('countActiveInCategory > behandelt fehlende Eintraege in enabledMap als false', () => {
	const metricIds = ['temperature', 'wind_chill'];
	const enabledMap = { temperature: true }; // wind_chill nicht in Map
	assert.equal(countActiveInCategory(metricIds, enabledMap), 1);
});

// =============================================================================
// buildPresetSummary — SavePresetDialog-Zusammenfassung (AC-6)
// =============================================================================

test('buildPresetSummary > zaehlt aktive, Rohwert, Indikator korrekt', () => {
	const enabledMap = {
		temperature: true,
		wind: true,
		wind_direction: true,
		precipitation: false,
	};
	const friendlyMap = {
		wind: false,         // Rohwert
		wind_direction: true // Indikator
	};
	const summary = buildPresetSummary(enabledMap, friendlyMap);
	// 3 aktiv (temperature, wind, wind_direction)
	assert.equal(summary.activeCount, 3);
	// wind ist indicatorCapable + friendlyMap[wind]=false → Rohwert
	// wind_direction ist indicatorCapable + friendlyMap[wind_direction]=true → Indikator
	// temperature ist nicht indicatorCapable → weder Roh noch Indikator
	assert.equal(summary.rawCount, 1);
	assert.equal(summary.indicatorCount, 1);
});

test('buildPresetSummary > activeCount 0 bei leerem enabledMap', () => {
	const summary = buildPresetSummary({}, {});
	assert.equal(summary.activeCount, 0);
	assert.equal(summary.rawCount, 0);
	assert.equal(summary.indicatorCount, 0);
});

// =============================================================================
// selectTableColumns — TablePreview Spaltenauswahl (AC-5)
// =============================================================================

test('selectTableColumns > gibt nur aktivierte Metriken zurueck', () => {
	const catalog = {
		temperature: [
			{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, has_friendly_format: false },
			{ id: 'wind_chill', label: 'Gefühlte Temp.', unit: '°C', category: 'temperature', default_enabled: false, has_friendly_format: false },
		],
		wind: [
			{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, has_friendly_format: false },
		],
	};
	const enabledMap = { temperature: true, wind_chill: false, wind: true };
	const cols = selectTableColumns(catalog, enabledMap);
	const ids = cols.map((c: { id: string }) => c.id);
	assert.ok(ids.includes('temperature'), 'temperature sollte enthalten sein');
	assert.ok(ids.includes('wind'), 'wind sollte enthalten sein');
	assert.equal(ids.includes('wind_chill'), false, 'wind_chill sollte nicht enthalten sein');
});

test('selectTableColumns > gibt leeres Array bei leerer enabledMap', () => {
	const catalog = {
		temperature: [
			{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, has_friendly_format: false },
		],
	};
	const cols = selectTableColumns(catalog, { temperature: false });
	assert.equal(cols.length, 0);
});

test('selectTableColumns > respektiert Kategorie-Reihenfolge (temperature vor wind)', () => {
	const catalog = {
		wind: [
			{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, has_friendly_format: false },
		],
		temperature: [
			{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, has_friendly_format: false },
		],
	};
	const enabledMap = { wind: true, temperature: true };
	const cols = selectTableColumns(catalog, enabledMap);
	// temperature (Kategorie index 0) sollte vor wind (index 1) kommen
	assert.equal(cols[0].id, 'temperature');
	assert.equal(cols[1].id, 'wind');
});

// =============================================================================
// Issue #364 (Schritt B) — Bucket-Editor-Logik (AC-1..AC-8)
// =============================================================================
// Funktionen autoAssign/move/reorder/channelOverflow/CHANNEL_COL_BUDGET/
// buildWeatherConfigMetrics existieren noch NICHT → RED.

function m(
	id: string,
	category: string,
	has_friendly_format = false,
): { id: string; label: string; unit: string; category: string; default_enabled: boolean; has_friendly_format: boolean } {
	return { id, label: id, unit: '', category, default_enabled: false, has_friendly_format };
}

// Katalog (kategorie-keyed) mit IDs, deren Backend-Priorität bekannt ist
// (#360 METRIC_PRIORITY): temperature 95, wind 90, gust 88, rain_probability 85,
// precipitation 78, wind_chill 70, cloud_total 65, humidity 25.
function buildCatalog(): editor.MetricCatalog {
	return {
		temperature: [m('temperature', 'temperature'), m('wind_chill', 'temperature'), m('humidity', 'temperature')],
		wind: [m('wind', 'wind'), m('gust', 'wind'), m('wind_direction', 'wind', true)],
		precipitation: [m('precipitation', 'precipitation'), m('rain_probability', 'precipitation', true)],
		atmosphere: [m('cloud_total', 'atmosphere', true)],
	};
}

// ---------- AC-1: autoAssign — Top-5 → primary, Rest aktiv → secondary --------

test('AC-1: autoAssign verteilt Top-5 nach Priorität in primary (Reihenfolge)', () => {
	const catalog = buildCatalog();
	const active = ['cloud_total', 'wind_chill', 'precipitation', 'rain_probability', 'gust', 'wind', 'temperature'];
	const b = editor.autoAssign(active, catalog);
	// Top-5 nach Priorität: temperature(95), wind(90), gust(88), rain_probability(85), precipitation(78)
	assert.deepEqual(b.primary, ['temperature', 'wind', 'gust', 'rain_probability', 'precipitation']);
	// Rest der aktiven (wind_chill 70, cloud_total 65) → secondary
	assert.deepEqual(b.secondary, ['wind_chill', 'cloud_total']);
});

test('AC-1: autoAssign legt inaktive Metriken in off', () => {
	const catalog = buildCatalog();
	// nur 3 aktiv; humidity + wind_direction sind im Katalog aber inaktiv → off
	const active = ['temperature', 'wind', 'precipitation'];
	const b = editor.autoAssign(active, catalog);
	assert.ok(b.off.includes('humidity'), 'humidity (inaktiv) muss in off liegen');
	assert.ok(b.off.includes('wind_direction'), 'wind_direction (inaktiv) muss in off liegen');
	// aktive dürfen NICHT in off sein
	assert.equal(b.off.includes('temperature'), false);
});

test('AC-1: autoAssign legt höchstens 5 Metriken in primary (Signal-safe, == Backend)', () => {
	const catalog = buildCatalog();
	const active = ['temperature', 'wind', 'gust', 'rain_probability', 'precipitation', 'wind_chill', 'cloud_total'];
	const b = editor.autoAssign(active, catalog);
	assert.equal(b.primary.length, 5);
});

test('F002: autoAssign dedupliziert doppelte IDs (kein Doppel in primary/secondary)', () => {
	const catalog = buildCatalog();
	const b = editor.autoAssign(['temperature', 'temperature', 'wind'], catalog);
	const all = [...b.primary, ...b.secondary];
	assert.equal(all.filter((id) => id === 'temperature').length, 1, 'temperature genau einmal');
	// und insgesamt nur 2 distinct aktive Metriken
	assert.deepEqual(b.primary, ['temperature', 'wind']);
	assert.deepEqual(b.secondary, []);
});

// ---------- AC-2 / AC-6: move zwischen Buckets --------------------------------

test('AC-2: move primary→secondary entfernt aus primary, fügt zu secondary', () => {
	const b: editor.Buckets = { primary: ['temperature', 'wind'], secondary: ['cloud_total'], off: [] };
	const out = editor.move(b, 'wind', 'primary', 'secondary');
	assert.equal(out.primary.includes('wind'), false, 'wind nicht mehr in primary');
	assert.ok(out.secondary.includes('wind'), 'wind jetzt in secondary');
});

test('AC-6: move off→primary fügt zu primary, entfernt aus off', () => {
	const b: editor.Buckets = { primary: ['temperature'], secondary: [], off: ['humidity'] };
	const out = editor.move(b, 'humidity', 'off', 'primary');
	assert.ok(out.primary.includes('humidity'), 'humidity jetzt in primary');
	assert.equal(out.off.includes('humidity'), false, 'humidity nicht mehr in off');
});

test('AC-6: move off→secondary fügt zu secondary, entfernt aus off', () => {
	const b: editor.Buckets = { primary: [], secondary: ['wind'], off: ['humidity'] };
	const out = editor.move(b, 'humidity', 'off', 'secondary');
	assert.ok(out.secondary.includes('humidity'));
	assert.equal(out.off.includes('humidity'), false);
});

test('F001: move mit ID die NICHT in `from` liegt ist No-Op (keine Phantom-ID)', () => {
	const b: editor.Buckets = { primary: ['temperature'], secondary: ['cloud_total'], off: [] };
	const out = editor.move(b, 'nichtvorhanden', 'primary', 'secondary');
	// Phantom-ID darf NICHT in secondary auftauchen …
	assert.equal(out.secondary.includes('nichtvorhanden'), false);
	// … und die Buckets bleiben inhaltlich unverändert.
	assert.deepEqual(out.primary, ['temperature']);
	assert.deepEqual(out.secondary, ['cloud_total']);
	assert.deepEqual(out.off, []);
});

// ---------- AC-3: reorder ↑/↓ + Ränder als No-Op -----------------------------

test('AC-3: reorder dir=-1 (hoch) vertauscht mit oberem Nachbarn', () => {
	const b: editor.Buckets = { primary: ['a', 'b', 'c'], secondary: [], off: [] };
	const out = editor.reorder(b, 'primary', 'b', -1);
	assert.deepEqual(out.primary, ['b', 'a', 'c']);
});

test('AC-3: reorder dir=1 (runter) vertauscht mit unterem Nachbarn', () => {
	const b: editor.Buckets = { primary: ['a', 'b', 'c'], secondary: [], off: [] };
	const out = editor.reorder(b, 'primary', 'b', 1);
	assert.deepEqual(out.primary, ['a', 'c', 'b']);
});

test('AC-3: reorder am oberen Rand ist No-Op', () => {
	const b: editor.Buckets = { primary: ['a', 'b', 'c'], secondary: [], off: [] };
	const out = editor.reorder(b, 'primary', 'a', -1);
	assert.deepEqual(out.primary, ['a', 'b', 'c']);
});

test('AC-3: reorder am unteren Rand ist No-Op', () => {
	const b: editor.Buckets = { primary: ['a', 'b', 'c'], secondary: [], off: [] };
	const out = editor.reorder(b, 'primary', 'c', 1);
	assert.deepEqual(out.primary, ['a', 'b', 'c']);
});

// ---------- AC-5: channelOverflow / CHANNEL_COL_BUDGET ------------------------

test('AC-5: CHANNEL_COL_BUDGET — telegram 7, sms 0, email unbegrenzt (#610: kein signal)', () => {
	assert.equal(editor.CHANNEL_COL_BUDGET.telegram, 7);
	assert.equal(editor.CHANNEL_COL_BUDGET.sms, 0);
	assert.equal(editor.CHANNEL_COL_BUDGET.email, Infinity);
	assert.ok(!('signal' in editor.CHANNEL_COL_BUDGET), 'signal darf nicht in CHANNEL_COL_BUDGET sein');
});

test('AC-5: channelOverflow bei 8 primary → Telegram überschritten', () => {
	const ov = editor.channelOverflow(8);
	assert.equal(ov.telegram, true, 'Telegram-Budget 7 überschritten bei 8 Spalten');
	assert.equal(ov.email, false, 'Email-Budget unbegrenzt');
	assert.ok(!('signal' in ov), 'signal darf nicht in channelOverflow sein');
});

test('AC-5: channelOverflow bei 7 primary → Telegram exakt am Limit (nicht überschritten)', () => {
	const ov = editor.channelOverflow(7);
	assert.equal(ov.telegram, false, '7 == Budget ist noch ok');
	assert.equal(ov.email, false);
});

// ---------- AC-7 / AC-4: buildWeatherConfigMetrics (Round-Trip-Shape) ---------

test('AC-7: buildWeatherConfigMetrics setzt bucket + lückenlosen order je Bucket', () => {
	const buckets: editor.Buckets = {
		primary: ['temperature', 'wind'],
		secondary: ['cloud_total'],
		off: ['humidity'],
	};
	const out = editor.buildWeatherConfigMetrics(buckets, {}, {}, buildCatalog());
	const byId: Record<string, editor.BucketWeatherConfigMetric> =
		Object.fromEntries(out.map((x) => [x.metric_id, x]));

	assert.equal(byId['temperature'].enabled, true);
	assert.equal(byId['temperature'].bucket, 'primary');
	assert.equal(byId['temperature'].order, 0);
	assert.equal(byId['wind'].bucket, 'primary');
	assert.equal(byId['wind'].order, 1);

	assert.equal(byId['cloud_total'].enabled, true);
	assert.equal(byId['cloud_total'].bucket, 'secondary');
	assert.equal(byId['cloud_total'].order, 0); // lückenlos pro Bucket

	assert.equal(byId['humidity'].enabled, false);
});

test('AC-4: buildWeatherConfigMetrics spiegelt use_friendly_format aus friendlyMap', () => {
	const buckets: editor.Buckets = {
		primary: ['wind', 'temperature'],
		secondary: [],
		off: [],
	};
	// wind ist indicatorCapable → friendlyMap greift; temperature nicht.
	const friendlyMap = { wind: false, wind_direction: true };
	const out = editor.buildWeatherConfigMetrics(buckets, friendlyMap, {}, buildCatalog());
	const byId: Record<string, editor.BucketWeatherConfigMetric> =
		Object.fromEntries(out.map((x) => [x.metric_id, x]));
	assert.equal(byId['wind'].use_friendly_format, false, 'wind: friendlyMap=false → Rohwert');
});

test('AC-4: buildWeatherConfigMetrics gibt horizons aus horizonsMap durch', () => {
	const buckets: editor.Buckets = { primary: ['temperature'], secondary: [], off: [] };
	const horizons = { today: true, tomorrow: false, day_after: true };
	const out = editor.buildWeatherConfigMetrics(buckets, {}, { temperature: horizons }, buildCatalog());
	const byId: Record<string, editor.BucketWeatherConfigMetric> =
		Object.fromEntries(out.map((x) => [x.metric_id, x]));
	assert.deepEqual(byId['temperature'].horizons, horizons);
});

// ---------- AC-8: Preset-Wechsel überschreibt Buckets via autoAssign ----------

test('AC-8: autoAssign aus Preset-Metriken liefert frische Buckets (überschreibt)', () => {
	const catalog = buildCatalog();
	// Preset aktiviert genau diese drei.
	const presetActive = ['temperature', 'cloud_total', 'rain_probability'];
	const b = editor.autoAssign(presetActive, catalog);
	// Top-5-Logik bei nur 3 aktiven → alle drei in primary (nach Priorität sortiert)
	assert.deepEqual(b.primary, ['temperature', 'rain_probability', 'cloud_total']);
	assert.deepEqual(b.secondary, []);
	// Nicht im Preset aktive Metriken landen in off.
	assert.ok(b.off.includes('wind'));
	assert.ok(b.off.includes('gust'));
});

// =============================================================================
// Issue #365 (Schritt C von #361) — 4-Kanal-Live-Vorschau (AC-1..AC-4)
// =============================================================================
//
// Spec: docs/specs/modules/issue_365_channel_preview_mobile.md
// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx (Z. 555-667)
//
// applyChannel(primary, secondary, budget) und buildBucketSummary(buckets,
// friendlyMap) existieren noch NICHT → in RED schlägt der Aufruf fehl (undefined
// is not a function). AC-5 (responsive) + AC-6 (Marker-Politur) sind rein
// visuell und werden NICHT hier erzwungen. KEINE Mocks (pure functions).

// ---------- AC-1: applyChannel je Kanal --------------------------------------

test('AC-1: applyChannel Email (Infinity) → inTable==primary, detail==secondary, demoted 0', () => {
	const primary = ['temperature', 'wind', 'gust'];
	const secondary = ['cloud_total', 'humidity'];
	const r = editor.applyChannel(primary, secondary, editor.CHANNEL_COL_BUDGET.email);
	assert.deepEqual(r.inTable, primary);
	assert.deepEqual(r.detail, secondary);
	assert.equal(r.demoted, 0);
});

test('F001: applyChannel Email gibt eine KOPIE von primary zurück (kein Alias)', () => {
	const primary = ['temperature', 'wind'];
	const r = editor.applyChannel(primary, [], editor.CHANNEL_COL_BUDGET.email);
	assert.deepEqual(r.inTable, primary);
	assert.notStrictEqual(r.inTable, primary, 'inTable darf nicht dieselbe Referenz wie primary sein');
});

test('AC-1: applyChannel SMS (0) → inTable==[], detail==alles, demoted==primary.length', () => {
	const primary = ['temperature', 'wind', 'gust'];
	const secondary = ['cloud_total'];
	const r = editor.applyChannel(primary, secondary, editor.CHANNEL_COL_BUDGET.sms);
	assert.deepEqual(r.inTable, []);
	assert.deepEqual(r.detail, ['temperature', 'wind', 'gust', 'cloud_total']);
	assert.equal(r.demoted, primary.length);
});

test('AC-1: applyChannel mit Budget 5 kappt inTable, demoted==overflow', () => {
	const primary = ['temperature', 'wind', 'gust', 'rain_probability', 'precipitation', 'wind_chill'];
	const secondary = ['cloud_total'];
	const r = editor.applyChannel(primary, secondary, 5);
	assert.equal(r.inTable.length, 5);
	assert.deepEqual(r.inTable, ['temperature', 'wind', 'gust', 'rain_probability', 'precipitation']);
	// Overflow (wind_chill) landet VORNE in detail, vor secondary.
	assert.deepEqual(r.detail, ['wind_chill', 'cloud_total']);
	assert.equal(r.demoted, 1);
});

test('AC-1: applyChannel Telegram (7) kappt erst ab der 8. Spalte', () => {
	const primary = ['a', 'b', 'c', 'd', 'e', 'f', 'g']; // genau 7
	const r = editor.applyChannel(primary, [], editor.CHANNEL_COL_BUDGET.telegram);
	assert.equal(r.inTable.length, 7);
	assert.equal(r.demoted, 0);
});

// ---------- AC-2: 7 primary, Budget 5 → 2 demoted vorne in detail -------------

test('AC-2: 7 primary bei Budget 5 → demoted==2, 2 überzählige vorne in detail', () => {
	const primary = ['temperature', 'wind', 'gust', 'rain_probability', 'precipitation', 'wind_chill', 'cloud_total'];
	const secondary = ['humidity'];
	const r5 = editor.applyChannel(primary, secondary, 5);
	assert.equal(r5.inTable.length, 5);
	assert.equal(r5.demoted, 2);
	// Die 2 überzähligen (wind_chill, cloud_total) stehen VOR secondary.
	assert.deepEqual(r5.detail.slice(0, 2), ['wind_chill', 'cloud_total']);
	assert.equal(r5.detail[2], 'humidity');

	// Email zeigt alle 7 ohne Demote.
	const mail = editor.applyChannel(primary, secondary, editor.CHANNEL_COL_BUDGET.email);
	assert.equal(mail.inTable.length, 7);
	assert.equal(mail.demoted, 0);
});

// ---------- AC-3: SMS keine Tabelle, alles flach in detail --------------------

test('AC-3: SMS-Karte hat keine Tabelle (inTable==[]) — alles in detail', () => {
	const primary = ['temperature', 'wind'];
	const secondary = ['cloud_total', 'humidity'];
	const r = editor.applyChannel(primary, secondary, editor.CHANNEL_COL_BUDGET.sms);
	assert.deepEqual(r.inTable, []);
	assert.deepEqual(r.detail, ['temperature', 'wind', 'cloud_total', 'humidity']);
});

// ---------- AC-4: bucket-bewusste Preset-Summary ------------------------------

test('AC-4: buildBucketSummary zählt Spalten, Detail und Skala', () => {
	const buckets: editor.Buckets = {
		primary: ['temperature', 'wind'],      // wind ist indicatorCapable
		secondary: ['cloud_total', 'humidity'], // cloud_total ist indicatorCapable
		off: ['gust'],
	};
	// wind=Skala (true), cloud_total=Skala (true), humidity=Roh (false).
	const friendlyMap = { wind: true, cloud_total: true, humidity: false };
	const s = editor.buildBucketSummary(buckets, friendlyMap);
	assert.equal(s.spalten, 2, '2 Spalten (primary)');
	assert.equal(s.detail, 2, '2 Detail (secondary)');
	// Skala = aktive + indicatorCapable + friendlyMap===true: wind + cloud_total.
	assert.equal(s.skala, 2, 'wind + cloud_total als Skala');
});

test('AC-4: buildBucketSummary ignoriert off-Metriken bei der Skala-Zählung', () => {
	const buckets: editor.Buckets = {
		primary: ['temperature'],
		secondary: [],
		off: ['wind'], // off + indicatorCapable + true → zählt NICHT
	};
	const s = editor.buildBucketSummary(buckets, { wind: true });
	assert.equal(s.spalten, 1);
	assert.equal(s.detail, 0);
	assert.equal(s.skala, 0, 'off-Metrik darf nicht als Skala zählen');
});
