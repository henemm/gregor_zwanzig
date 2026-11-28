// Regressionswaechter — Issue #3022 (vormals #2794 S3a F012, umgekehrt).
// Spec: docs/specs/modules/fix_3022_zustellung_laedt.md (AC-1, AC-3)
//
// Frueheres Soll (#2794 S3a F012, #1743 AC-9): ZustellungTab im Vergleich-Hub mountete erst nach
// Metrik-, Versand- UND Alarm-Hydration, weil der Reiter damals `wizardState`-Felder bediente und
// seine Speicherer sonst gegen Platzhalterwerte entstanden waeren.
//
// Neues Soll (#3022): der Reiter bedient keinen `wizardState` mehr. Sein Stand kommt direkt aus dem
// Preset (`standAusPreset`), die Speicher-Basis ist `startStand` aus dem Preset; das Profil laedt
// er selbst. Die Hydrations-Flags haengen am Metrik-Katalog — haengt der, blieb der Reiter leer
// (nur Sperr-Kopf), der Trip zeigte sofort alles. Deshalb mountet ZustellungTab jetzt wie im Trip
// (`trip-detail/TripTabs.svelte`) allein nach aktivem Reiter, bei JEDER Flag-Kombination.
//
// Messweise: AST der echten Komponente (svelte/compiler.parse, Helfer s3a2794Ast.ts). Die
// Weichen, unter denen ZustellungTab steht, werden zur Gesamtbedingung verknuepft
// ({#if}-Zweig = Bedingung, {:else}-Zweig = Negation) und fuer alle Kombinationen der drei
// Hydrations-Flags ausgewertet. Keine Textmuster-Suche.
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

/** Ist ZustellungTab bei diesem Reiter und diesen Flag-Werten gemountet? (Gesamtbedingung aller Weichen) */
function gemountet(activeTab: string, flags: Record<string, boolean>): boolean {
	const z = zustellungEinbettung();
	const u = { activeTab, ...flags };
	return z.weichen.every((w) => {
		const ergebnis = Boolean(werte(w.test, u));
		return w.zweig === 'dann' ? ergebnis : !ergebnis;
	});
}

function alleKombinationen(): Record<string, boolean>[] {
	const out: Record<string, boolean>[] = [];
	for (let maske = 0; maske < 1 << FLAGS.length; maske++) out.push(Object.fromEntries(FLAGS.map((f, i) => [f, Boolean(maske & (1 << i))])));
	return out;
}

describe('#3022: ZustellungTab im Vergleich mountet allein nach aktivem Reiter (wie im Trip)', () => {
	test('i3022_zustellung_vergleich_mountet_bei_haengender_hydration', () => {
		assert.equal(
			gemountet('zustellung', { wetterMetrikenLayoutHydrationBereit: false, versandHydrated: false, alarmeHydrated: false }),
			true,
			'#3022: ZustellungTab mountet nicht, solange die Hydration (Metrik-Katalog) haengt — der Reiter bleibt leer'
		);
	});

	test('i3022_zustellung_vergleich_mountet_bei_jeder_flag_kombination', () => {
		for (const flags of alleKombinationen()) {
			assert.equal(gemountet('zustellung', flags), true, `#3022: ZustellungTab nicht gemountet bei ${JSON.stringify(flags)}`);
		}
	});

	test('i3022_zustellung_vergleich_nicht_gemountet_in_anderem_reiter', () => {
		for (const tab of ['uebersicht', 'orte', 'wetter']) {
			for (const flags of alleKombinationen()) {
				assert.equal(gemountet(tab, flags), false, `#3022: ZustellungTab gemountet im Reiter ${tab} bei ${JSON.stringify(flags)}`);
			}
		}
	});
});
