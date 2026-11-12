// #2243 AC-5: Ersatz für die gelöschte E2E-Spec issue-264-stage-sort.
// Etappen werden nach Etappenname natürlich sortiert, nicht nach Dateiname
// (Datum-Präfix) und nicht lexikografisch.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { naturalSort, naturalSortKey } from './naturalSort.ts';

type Etappe = { file: string; name: string };

test('KHW-Etappen ordnen sich nach Name, obwohl das Datum-Präfix KHW_03 nach vorn zieht', () => {
	const importiert: Etappe[] = [
		{ file: '2026-07-01_KHW_03.gpx', name: 'KHW_03' },
		{ file: '2026-07-02_KHW_01.gpx', name: 'KHW_01' },
		{ file: '2026-07-03_KHW_00a.gpx', name: 'KHW_00a' }
	];
	const nachDatei = [...importiert].sort((a, b) => a.file.localeCompare(b.file));
	assert.deepEqual(
		nachDatei.map((e) => e.name),
		['KHW_03', 'KHW_01', 'KHW_00a'],
		'Vorbedingung: nach Dateiname stünde KHW_03 vorn'
	);
	assert.deepEqual(
		naturalSort(importiert, (e) => e.name).map((e) => e.name),
		['KHW_00a', 'KHW_01', 'KHW_03']
	);
});

test('KHW_10 kommt nach KHW_2 (natürlich, nicht lexikografisch)', () => {
	assert.deepEqual(
		naturalSort(['KHW_10', 'KHW_2', 'KHW_1'], (s) => s),
		['KHW_1', 'KHW_2', 'KHW_10']
	);
});

test('Groß-/Kleinschreibung spielt keine Rolle, Eingabe bleibt unverändert', () => {
	const eingabe = ['khw_2', 'KHW_10', 'Khw_1'];
	const kopie = [...eingabe];
	assert.deepEqual(naturalSort(eingabe, (s) => s), ['Khw_1', 'khw_2', 'KHW_10']);
	assert.deepEqual(eingabe, kopie);
});

test('Sortierschlüssel zerlegt Ziffernfolgen in Zahlen', () => {
	assert.deepEqual(naturalSortKey('KHW_10'), ['khw_', 10, '']);
	assert.deepEqual(naturalSortKey('KHW_00a'), ['khw_', 0, 'a']);
});
