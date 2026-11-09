// Regressionswaechter — Issue #2794 S3a, Teil-PR 2 (Adversary-Finding F012).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md (§3 Uebergangsreiter Zustellung)
//
// Warum: der Reiter Zustellung im Vergleich-Hub (CompareTabs.svelte) bettet ZustellungTab ein,
// der Metrik-Zustellungsbloecke, Versand-Abschnitt UND AlarmeTab traegt. Er darf erst mounten,
// wenn ALLE drei Domaenen hydriert sind: Wetter-Metriken/Layout
// (wetterMetrikenLayoutHydrationBereit), Versand (versandHydrated, #1743 AC-9) und Alarme
// (alarmeHydrated, wie zuvor der Alarme-Reiter). Mountet er frueher, entstehen die Speicherer
// gegen Platzhalterwerte (Baseline unvollstaendig, Gefahr des Ueberschreibens mit Leerstand).
// Mutation (Adversary): `alarmeHydrated` aus der Mount-Bedingung entfernt -> blieb gruen.
//
// Messweise: AST der echten Komponente (svelte/compiler.parse, Helfer s3a2794Ast.ts). Die
// Weichen, unter denen ZustellungTab steht, werden zur Gesamtbedingung verknuepft
// ({#if}-Zweig = Bedingung, {:else}-Zweig = Negation) und fuer alle Kombinationen der drei
// Hydrations-Flags ausgewertet (activeTab = 'zustellung'). Keine Textmuster-Suche.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { svelteAst, einbettungenMitWeichen, reiterVon } from './s3a2794Ast.ts';
import { werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const VERGLEICH_HUB = join(KOMP, 'compare', 'CompareTabs.svelte');

const FLAGS = ['wetterMetrikenLayoutHydrationBereit', 'versandHydrated', 'alarmeHydrated'] as const;

function zustellungEinbettung() {
	const { ast, quelle } = svelteAst(VERGLEICH_HUB);
	const z = einbettungenMitWeichen(ast, quelle, ['ZustellungTab']);
	assert.equal(z.length, 1, `Messaufbau: erwartet genau eine ZustellungTab-Einbettung im Vergleich-Hub, gefunden ${z.length}`);
	assert.deepEqual(reiterVon(z[0]), ['zustellung'], 'Messaufbau: ZustellungTab haengt nicht am Reiter zustellung');
	return z[0];
}

/** Ist ZustellungTab bei diesen Flag-Werten gemountet? (Gesamtbedingung aller Weichen) */
function gemountet(flags: Record<string, boolean>): boolean {
	const z = zustellungEinbettung();
	const u = { activeTab: 'zustellung', ...flags };
	return z.weichen.every((w) => {
		const ergebnis = Boolean(werte(w.test, u));
		return w.zweig === 'dann' ? ergebnis : !ergebnis;
	});
}

describe('F012: ZustellungTab im Vergleich mountet erst nach Metrik-, Versand- UND Alarm-Hydration', () => {
	test('s3a2794_f012_zustellung_vergleich_wartet_auf_alarme_hydration', () => {
		assert.equal(
			gemountet({ wetterMetrikenLayoutHydrationBereit: true, versandHydrated: true, alarmeHydrated: false }),
			false,
			'F012: ZustellungTab mountet, obwohl die Alarme noch nicht hydriert sind (alarmeHydrated fehlt in der Mount-Bedingung)'
		);
	});

	test('s3a2794_f012_zustellung_vergleich_wartet_auf_versand_hydration', () => {
		assert.equal(
			gemountet({ wetterMetrikenLayoutHydrationBereit: true, versandHydrated: false, alarmeHydrated: true }),
			false,
			'F012: ZustellungTab mountet, obwohl der Versand noch nicht hydriert ist (versandHydrated fehlt in der Mount-Bedingung)'
		);
	});

	test('s3a2794_f012_zustellung_vergleich_mountet_genau_wenn_alle_drei_hydriert', () => {
		for (let maske = 0; maske < 1 << FLAGS.length; maske++) {
			const flags = Object.fromEntries(FLAGS.map((f, i) => [f, Boolean(maske & (1 << i))]));
			const alle = FLAGS.every((f) => flags[f]);
			assert.equal(gemountet(flags), alle, `F012: Mount-Zustand falsch bei ${JSON.stringify(flags)}`);
		}
	});
});
