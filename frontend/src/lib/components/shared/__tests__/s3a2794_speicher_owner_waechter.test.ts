// REGRESSIONSWAECHTER (heute schon GRUEN, muss gruen bleiben) — Issue #2794 S3a, Teil-PR 2.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-2.T1 (Kern-Anteil), AC-8
//
// Die Reiter-Kennungen `wetter-metriken`, `versand`, `alarme`, `wertebereiche` entfallen bzw.
// werden umgeleitet — die GLEICHEN Woerter sind aber auch Speicher-Besitzer (Owner) im
// saveController und im keepalive-Speicherweg. Diese duerfen NICHT mitumbenannt werden
// (Speicherweg wie vorher, AC-8). Ein Suchen-und-Ersetzen beim Testumzug wuerde genau hier
// still den Speicherweg aendern.
//
// Messweise: AST (svelte/compiler bzw. TS ueber denselben Parser), Aufruf mit Aufgerufenem und
// letztem String-Argument — kein Textmuster. Der Request-Vergleich vorher/nachher in zwei Konten
// ist Playwright-Sache (/e2e-verify).
//
// Mutation (Adversary): Owner-String an einer Stelle umbenennen → genau diese Zeile wird rot.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_speicher_owner_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import { svelteAst, tsAst, aufrufe, aufgerufener, letztesStringArgument, type Knoten } from './s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');

/** [Datei (relativ zu components/), Aufgerufener, Owner-String, Mindestanzahl] */
const STELLEN: Array<[string, string, string, number]> = [
	['shared/WeatherMetricsTab.svelte', 'saveController.schedule', 'wetter-metriken', 1],
	['shared/WeatherMetricsTab.svelte', 'saveController.schedule', 'wetter-metriken-report-config', 1],
	['shared/weather-metrics-tab/weatherMetricsCompareSave.ts', 'saveController.schedule', 'wetter-metriken', 1],
	// Teil-PR 3 (AC-38): der Reiter Wetter speichert ueber EINEN eigenen Owner (Trip und Orts-Briefing).
	['shared/wetter-tab/wetterTabSpeicherung.ts', 'saveController.schedule', 'wetter-ampel', 2],
	['trip-detail/BriefingScheduleTab.svelte', 'saveController.schedule', 'versand', 1],
	['shared/versandVergleichSpeicherung.ts', 'saveController.schedule', 'versand', 1],
	['shared/AlarmeTab.svelte', 'baueTripSpeicherung', 'alarme', 1],
	['shared/corridor-editor/CorridorEditor.svelte', 'baueTripSpeicherung', 'wertebereiche', 1],
	['shared/corridor-editor/CorridorEditorMobile.svelte', 'baueTripSpeicherung', 'wertebereiche', 1]
];

function aufrufeIn(datei: string): { liste: Knoten[]; quelle: string } {
	if (datei.endsWith('.svelte')) {
		const { ast, quelle } = svelteAst(datei);
		return { liste: [...aufrufe(ast.instance?.content), ...aufrufe(ast.fragment)], quelle };
	}
	const { programm, quelle } = tsAst(datei);
	return { liste: aufrufe(programm), quelle };
}

describe('AC-2.T1 (Regressionswächter): Speicher-Owner-Strings stehen unverändert an ihren Speicher-Aufrufen', () => {
	for (const [rel, callee, owner, min] of STELLEN) {
		test(`s3a2794_t1_owner_${owner}_in_${rel.replace(/[^a-zA-Z0-9]+/g, '_')}`, () => {
			const datei = join(KOMP, rel);
			const { liste, quelle } = aufrufeIn(datei);
			const treffer = liste.filter((a) => aufgerufener(a, quelle).endsWith(callee) && letztesStringArgument(a) === owner);
			const vorhanden = liste
				.filter((a) => aufgerufener(a, quelle).endsWith(callee))
				.map((a) => letztesStringArgument(a))
				.filter((x) => x !== null);
			assert.ok(
				treffer.length >= min,
				`AC-2.T1: ${relative(KOMP, datei)} ruft ${callee}(…, '${owner}') nicht mehr auf — Owner umbenannt? ` +
					`Gefundene Owner an ${callee}: ${JSON.stringify(vorhanden)}`
			);
		});
	}

	test('s3a2794_t1_kein_owner_auf_neue_reiterkennung_umbenannt', () => {
		// Gegenprobe: kein Speicher-Aufruf traegt die NEUEN Reiter-Kennungen als Owner.
		for (const [rel, callee] of STELLEN) {
			const { liste, quelle } = aufrufeIn(join(KOMP, rel));
			for (const a of liste) {
				if (!aufgerufener(a, quelle).endsWith(callee)) continue;
				const o = letztesStringArgument(a);
				assert.ok(o !== 'wetter' && o !== 'zustellung', `${rel}: ${callee}(…, '${o}') — Owner wurde auf die Reiterkennung umbenannt`);
			}
		}
	});
});
