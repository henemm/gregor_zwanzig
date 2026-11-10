// TDD RED — Issue #2794 S3a, Teil-PR 2: `bereich`-Darstellungsfilter der Metrik-Oberflaeche.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — Implementation Details §2
// (traegt AC-7 „kein Element verschwindet" und AC-2.T2 „eine WMT-Instanz je Reiter").
//
// `weatherMetricsTabSections(context, bereich)` mit bereich ∈ {wetter, zustellung, alles};
// neue Abschnittsnamen `layout_kanal` (Layout je Kanal, heute Gate `reihenfolge`) und
// `nachtblock` (Nacht-Block, heute ohne Abschnittsnamen, nur route).
//   wetter     = grundauswahl, tagesfenster, sms_schwellen (route), official_alerts
//   zustellung = layout_kanal, stundenverlauf (vergleich), ausblick, report_config (route), nachtblock (route)
// Beide disjunkt, Vereinigung = alles. Ohne zweiten Parameter wie bisher = alles.
// Folge: das bisherige Gate `reihenfolge` heisst `layout_kanal` (exakte Mengen unten).
//
// Reine Funktionsausgabe, keine Mocks. RED heute: der zweite Parameter wird ignoriert,
// `layout_kanal`/`nachtblock` gibt es nicht.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/s3a2794_bereich_filter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { weatherMetricsTabSections } from '../weatherMetricsTabSections.ts';

type Ctx = 'route' | 'vergleich';
type Bereich = 'wetter' | 'zustellung' | 'alles';

const abschnitte = (ctx: Ctx, bereich?: Bereich): string[] =>
	(weatherMetricsTabSections as unknown as (c: Ctx, b?: Bereich) => string[])(ctx, bereich);

// Teil-PR 3 (Spec §6 e): `sms_schwellen` (#624) wandert vom Bereich wetter in den Bereich
// zustellung — der Reiter Wetter traegt keine Metrik-Oberflaeche mehr, die Schwellen bleiben
// erreichbar (Vereinigung = alles, disjunkt; beide Zusicherungen unten unveraendert).
const SOLL: Record<Ctx, Record<'wetter' | 'zustellung', string[]>> = {
	route: {
		wetter: ['grundauswahl', 'tagesfenster', 'official_alerts'],
		zustellung: ['layout_kanal', 'ausblick', 'report_config', 'nachtblock', 'sms_schwellen']
	},
	vergleich: {
		wetter: ['grundauswahl', 'tagesfenster', 'official_alerts'],
		zustellung: ['layout_kanal', 'stundenverlauf', 'ausblick']
	}
};

const sortiert = (a: string[]) => [...a].sort();

for (const ctx of ['route', 'vergleich'] as Ctx[]) {
	describe(`bereich-Filter (${ctx})`, () => {
		test(`s3a2794_bereich_${ctx}_wetter_genau_die_wetter_abschnitte`, () => {
			assert.deepEqual(sortiert(abschnitte(ctx, 'wetter')), sortiert(SOLL[ctx].wetter));
		});

		test(`s3a2794_bereich_${ctx}_zustellung_genau_die_zustellungs_abschnitte`, () => {
			assert.deepEqual(sortiert(abschnitte(ctx, 'zustellung')), sortiert(SOLL[ctx].zustellung));
		});

		test(`s3a2794_bereich_${ctx}_wetter_und_zustellung_disjunkt`, () => {
			const w = abschnitte(ctx, 'wetter');
			const z = abschnitte(ctx, 'zustellung');
			const doppelt = w.filter((s) => z.includes(s));
			assert.deepEqual(doppelt, [], `Abschnitte in beiden Bereichen (zwei Instanzen zeigten dasselbe): ${doppelt.join(', ')}`);
		});

		test(`s3a2794_bereich_${ctx}_vereinigung_ist_alles`, () => {
			const alles = abschnitte(ctx, 'alles');
			assert.deepEqual(
				sortiert([...abschnitte(ctx, 'wetter'), ...abschnitte(ctx, 'zustellung')]),
				sortiert(alles),
				'wetter ∪ zustellung ≠ alles (ein Element wäre in keinem Reiter sichtbar)'
			);
			assert.deepEqual(sortiert(alles), sortiert([...SOLL[ctx].wetter, ...SOLL[ctx].zustellung]));
		});

		test(`s3a2794_bereich_${ctx}_ohne_bereich_wie_alles`, () => {
			assert.deepEqual(sortiert(abschnitte(ctx)), sortiert(abschnitte(ctx, 'alles')));
		});

	});
}
