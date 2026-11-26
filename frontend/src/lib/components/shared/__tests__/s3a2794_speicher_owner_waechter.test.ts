// REGRESSIONSWAECHTER — Issue #2794 S3a, Teil-PR 2 (AC-2.T1, AC-8); wiederhergestellt in #3020 R1 (G15) ohne die
// Eintraege der in #3357 geloeschten Dateien.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md
//
// Die Reiter-Kennungen `wetter-metriken`, `versand`, `alarme`, `wertebereiche` entfallen bzw. werden umgeleitet — die
// GLEICHEN Woerter sind aber auch Speicher-Besitzer (Owner) im saveController und im keepalive-Speicherweg. Diese
// duerfen NICHT auf die neuen Reiterkennungen mitumbenannt werden (Speicherweg wie vorher, AC-8).
//
// Messweise: AST der Speicher-Aufrufe (Aufgerufener und letztes String-Argument, kein Textmuster); die Owner der Karte
// „Was steht wo“ stehen als Konstante am Aufruf und werden am ausgefuehrten Speicherer gemessen.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_speicher_owner_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join, relative } from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { svelteAst, tsAst, aufrufe, aufgerufener, letztesStringArgument, type Knoten } from './s3a2794Ast.ts';
import { erstelleFelderSpeicherung, erstelleTabellenSpeicherung, felderAusAntwort } from '../wetter-tab/wasStehtWoSpeicherung.ts';
import { SPEICHERER, WETTER_OWNER } from '../wetter-tab/wetterTabSpeicherung.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');

/** [Datei (relativ zu components/), Aufgerufener, Owner-String, Mindestanzahl] */
const STELLEN: Array<[string, string, string, number]> = [
	// Teil-PR 3 (AC-38): der Reiter Wetter speichert ueber EINEN eigenen Owner (Trip und Orts-Briefing).
	['shared/wetter-tab/wetterTabSpeicherung.ts', 'saveController.schedule', 'wetter-ampel', 2],
	['shared/AlarmeTab.svelte', 'baueTripSpeicherung', 'alarme', 1],
	// #2795 S3b (AC-33): der Reiter Zustellung hat EINEN Speicherer mit zwei Nutzlast-Teilen.
	['shared/zustellung-tab/zustellungSpeicherung.ts', 'saveController.schedule', 'versand', 1],
	['shared/zustellung-tab/zustellungSpeicherung.ts', 'saveController.schedule', 'alarme', 1]
];

function aufrufeIn(datei: string): { liste: Knoten[]; quelle: string } {
	if (datei.endsWith('.svelte')) {
		const { ast, quelle } = svelteAst(datei);
		return { liste: [...aufrufe(ast.instance?.content), ...aufrufe(ast.fragment)], quelle };
	}
	const { programm, quelle } = tsAst(datei);
	return { liste: aufrufe(programm), quelle };
}

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
/** Speicher-Steuerung, die nur mitschreibt: je Planung der Owner und der Konflikt-Schluessel des Vorgangs. */
function mitschrift() {
	const owner: string[] = [];
	const konflikt: string[] = [];
	const saveController = {
		schedule: (fn: J, _ms?: number, o?: string) => {
			owner.push(String(o));
			konflikt.push(String(fn.konfliktSchluessel));
		},
		cancel: () => {}
	};
	return { owner, konflikt, saveController };
}
const client = { get: async () => ({}), put: async () => ({}) } as J;

describe('AC-2.T1 (Regressionswächter): Speicher-Owner-Strings stehen unverändert an ihren Speicher-Aufrufen', () => {
	for (const [rel, callee, owner, min] of STELLEN) {
		const datei = rel.replace(/[^a-zA-Z0-9]+/g, '_');
		test(`s3a2794_t1_owner_${owner}_in_${datei}`, () => {
			const pfad = join(KOMP, rel);
			assert.ok(existsSync(pfad), `${rel} fehlt`);
			const { liste, quelle } = aufrufeIn(pfad);
			const treffer = liste.filter((a) => aufgerufener(a, quelle).endsWith(callee) && letztesStringArgument(a) === owner);
			const vorhanden = liste
				.filter((a) => aufgerufener(a, quelle).endsWith(callee))
				.map((a) => letztesStringArgument(a))
				.filter((x) => x !== null);
			assert.ok(
				treffer.length >= min,
				`AC-2.T1: ${relative(KOMP, pfad)} ruft ${callee}(…, '${owner}') nicht mehr auf — Owner umbenannt? ` +
					`Gefundene Owner an ${callee}: ${JSON.stringify(vorhanden)}`
			);
		});
	}

	test('s3a2794_t1_karte_was_steht_wo_plant_unter_eigenen_ownern', () => {
		for (const kind of ['route', 'vergleich'] as const) {
			const tab = mitschrift();
			erstelleTabellenSpeicherung({ client, kind, id: 'abo', saveController: tab.saveController as J, placements: () => null, uebernehmen: () => {} }).aenderung();
			assert.deepEqual([tab.owner, tab.konflikt], [['was-steht-wo'], ['was-steht-wo']], kind);

			const feld = mitschrift();
			const start = felderAusAntwort({ blocks: {} } as J);
			erstelleFelderSpeicherung({ client, kind, id: 'abo', saveController: feld.saveController as J, start }).melden({ ...start, telegram_style: 'kurzform' });
			assert.deepEqual([feld.owner, feld.konflikt], [['was-steht-wo-schalter'], ['was-steht-wo-schalter']], kind);
		}
	});

	test('s3a2794_t1_reiter_wetter_plant_und_meldet_konflikte_unter_wetter_ampel', () => {
		assert.equal(WETTER_OWNER, 'wetter-ampel');
		for (const kind of ['route', 'vergleich'] as const) {
			const m = mitschrift();
			SPEICHERER[kind]({ client, abo: () => ({ id: 'abo' }), stand: () => ({}), vorlagen: () => ({}), saveController: m.saveController } as J).melden();
			assert.deepEqual([m.owner, m.konflikt], [['wetter-ampel'], ['wetter-ampel']], kind);
		}
	});

	test('s3a2794_t1_kein_owner_auf_neue_reiterkennung_umbenannt', () => {
		// Gegenprobe: kein Speicher-Aufruf traegt die NEUEN Reiter-Kennungen als Owner.
		let geprueft = 0;
		for (const [rel, callee] of STELLEN) {
			const { liste, quelle } = aufrufeIn(join(KOMP, rel));
			for (const a of liste) {
				if (!aufgerufener(a, quelle).endsWith(callee)) continue;
				geprueft++;
				const o = letztesStringArgument(a);
				assert.ok(o !== 'wetter' && o !== 'zustellung', `${rel}: ${callee}(…, '${o}') — Owner wurde auf die Reiterkennung umbenannt`);
			}
		}
		assert.ok(geprueft >= STELLEN.length, 'Vakuum-Schutz: keine Speicher-Aufrufe gefunden');
	});
});
