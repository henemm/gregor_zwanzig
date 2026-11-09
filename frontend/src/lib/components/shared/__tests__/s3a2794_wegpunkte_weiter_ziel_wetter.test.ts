// Issue #2794 S3a, Teil-PR 2 (Fix-Loop, Adversary-Finding F015).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-6 (Anlege-Kette Trip: kein Schritt
// fuehrt auf einen falschen Reiter; nach den Wegpunkten folgt der Schritt Wetter).
//
// F015 — Wirkstelle: JEDER Weiter-Knopf im Wegpunkte-Schritt des Trip-Anlegens (Desktop: zwei im
// Info-Banner, zwei im Fuss; Mobil: zwei im Sticky-Fuss). Wird das Ziel eines dieser Knoepfe auf
// 'zustellung' umgestellt, uebersprang der Nutzer den Schritt Wetter — bisher fing das kein Test.
// Gemessen wird zur LAUFZEIT: die onclick-Ausdruecke aller Knoepfe in den Zweigen
// `{#if activeTab === 'wegpunkte'}` werden gegen das ECHTE Instanz-Skript des Editors
// (svelteInstanzPruefstand) ausgefuehrt, danach muss `activeTab === 'wetter'` sein.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_wegpunkte_weiter_ziel_wetter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { attribut, type Knoten } from './s3a2794Ast.ts';
import { umgebungFuer, werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const KOMP = join(HIER, '..', '..');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const TRIP_NEU = join(KOMP, 'trip-new', 'TripNewEditor.svelte');
const WEGPUNKTE_WEICHE = /^activeTab\s*===\s*['"]wegpunkte['"]$/;

function kinder(k: Knoten, f: (n: Knoten) => void): void {
	for (const [feld, v] of Object.entries(k)) {
		if (feld === 'parent' || feld === 'loc' || feld === 'metadata') continue;
		if (Array.isArray(v)) v.forEach((x) => x && typeof x === 'object' && f(x));
		else if (v && typeof v === 'object') f(v as Knoten);
	}
}

/** Alle Knoepfe (Element oder Komponente) mit onclick im Inhalt eines Zweigs. */
function knoepfeIn(zweig: Knoten, quelle: string, out: Array<{ wo: string; onclick: string }>): void {
	(function lauf(n: Knoten): void {
		if ((n.type === 'Component' || n.type === 'RegularElement') && Array.isArray(n.attributes)) {
			const oc = attribut(n, quelle, 'onclick');
			if (oc?.ausdruck) out.push({ wo: `${n.name}@${n.start}`, onclick: oc.ausdruck });
		}
		kinder(n, lauf);
	})(zweig);
}

/** Knoepfe aller `{#if|:else if activeTab === 'wegpunkte'}`-Zweige (Desktop-Inhalt, Mobil-Inhalt, Mobil-Fuss). */
function wegpunkteKnoepfe(ast: Knoten, quelle: string): { zweige: number; knoepfe: Array<{ wo: string; onclick: string }> } {
	const knoepfe: Array<{ wo: string; onclick: string }> = [];
	let zweige = 0;
	(function lauf(n: Knoten): void {
		if (n.type === 'IfBlock' && n.test && WEGPUNKTE_WEICHE.test(quelle.slice(n.test.start, n.test.end).trim())) {
			zweige++;
			knoepfeIn(n.consequent, quelle, knoepfe);
		}
		kinder(n, lauf);
	})(ast.fragment);
	return { zweige, knoepfe };
}

describe('AC-6 (F015): Trip-Anlegen — jeder Weiter-Knopf im Schritt Wegpunkte fuehrt auf Wetter', () => {
	test('s3a2794_f015_wegpunkte_weiter_knoepfe_schalten_auf_wetter', async () => {
		const { u, ast, quelle } = await umgebungFuer(
			TRIP_NEU,
			{
				untrack: (f: () => unknown) => f(),
				stateOverride: { activeTab: 'wegpunkte', name: 'GR20', startDate: '2026-07-01' }
			},
			{ jsAlsTs: true }
		);
		const { zweige, knoepfe } = wegpunkteKnoepfe(ast, quelle);
		assert.equal(zweige, 3, `Messaufbau: erwartet 3 Wegpunkte-Zweige (Desktop, Mobil-Inhalt, Mobil-Fuss), gefunden ${zweige}`);
		// Desktop: Banner (Ueberspringen →, Uebernehmen) + Fuss (Ueberspringen, Uebernehmen); Mobil-Fuss: 2.
		assert.ok(knoepfe.length >= 6, `Messaufbau: erwartet mind. 6 Weiter-Knoepfe, gefunden ${knoepfe.length} (${knoepfe.map((k) => k.wo).join(', ')})`);
		for (const { wo, onclick } of knoepfe) {
			u.activeTab = 'wegpunkte';
			u.editorStages = [];
			(werte(onclick, u) as () => void)();
			assert.equal(u.activeTab, 'wetter', `F015: ${wo} (${onclick}) schaltet auf '${u.activeTab}' statt auf 'wetter'`);
		}
	});
});
