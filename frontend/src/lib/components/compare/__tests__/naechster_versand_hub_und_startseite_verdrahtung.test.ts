// TDD RED — Issue #1969 (Nächstes Briefing), AC-23 / AC-24 (Verdrahtung).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// VERDRAHTUNGS-Prüfung, KEIN Verhaltensbeweis: CompareTabs.svelte und
// routes/+page.svelte sind im SSR-only-Harness nicht sinnvoll renderbar
// (Hub-Zustand, Viewport, Seitendaten). Gemessen wird mit dem ECHTEN
// Svelte-5-Compiler (AST, kein Text-Grep, Muster aktionsmodellAst.ts), dass
// beide den Backend-Wert über formatNextBriefing anzeigen und keine eigene
// Rechnung (deriveNextSend) mehr aufrufen. Das Verhalten des Formatierers
// bewacht naechstes_briefing_text.test.ts, die Startseiten-Helfer
// routes/_home/__tests__/naechster_versand_aus_backend.test.ts; den echten
// Anzeige-Pfad Staging (Vergleichsliste/Startseite = Versand-Reiter).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/naechster_versand_hub_und_startseite_verdrahtung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { ladeSvelte, aufrufe, aufrufArgumente } from '../../shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> compare -> components -> lib -> src
const SRC = path.resolve(HERE, '../../../..');
const COMPARE_TABS = path.join(SRC, 'lib/components/compare/CompareTabs.svelte');
const HUB_UEBERSICHT = path.join(SRC, 'lib/components/shared/hub-uebersicht/HubUebersicht.svelte');
const MODELL = path.join(SRC, 'lib/components/shared/hub-uebersicht/hubUebersichtModell.ts');
const HOME = path.join(SRC, 'routes/+page.svelte');

// Issue #2682: die Hub-Stat „Nächster Versand" steht im geteilten Baustein
// shared/hub-uebersicht/HubUebersicht.svelte; formatiert wird im Modell
// (hubUebersichtModell.ts, Verhalten: hub_uebersicht_modell.test.ts). Geprüft wird hier
// die Verdrahtung: Lader-Wert → Ableiter → formatNextBriefing, keine eigene Rechnung.
describe('AC-23/AC-24: Ortsvergleich-Hub (CompareTabs → HubUebersicht) liest den Backend-Wert', () => {
	const ast = ladeSvelte(COMPARE_TABS);
	const hu = ladeSvelte(HUB_UEBERSICHT);
	test('keine eigene Rechnung: deriveNextSend wird weder in CompareTabs noch im Baustein aufgerufen', () => {
		assert.equal(aufrufe(ast, 'deriveNextSend').length, 0, 'CompareTabs rechnet noch selbst (deriveNextSend)');
		assert.equal(aufrufe(hu, 'deriveNextSend').length, 0, 'HubUebersicht rechnet selbst (deriveNextSend)');
	});
	test('Anzeige über formatNextBriefing: der Baustein reicht den Lader-Wert an den Ableiter, der formatiert', () => {
		const args = aufrufArgumente(hu, 'deriveVergleichKennzahlen');
		assert.equal(args.length, 1, `genau ein Aufruf erwartet: ${JSON.stringify(args)}`);
		assert.equal(args[0][2], 'naechstesBriefing.wert', `Ableiter bekommt nicht den Lader-Wert: ${args[0].join(', ')}`);
		assert.match(
			readFileSync(MODELL, 'utf-8'),
			/formatNextBriefing\(briefing, 'vergleich'\)/,
			'hubUebersichtModell formatiert den Vergleichs-Wert nicht über formatNextBriefing'
		);
	});
});

describe('AC-23/AC-24: Startseite (routes/+page.svelte) liest den Backend-Wert', () => {
	const ast = ladeSvelte(HOME);
	test('keine eigene Rechnung: deriveNextSend wird nicht aufgerufen', () => {
		assert.equal(aufrufe(ast, 'deriveNextSend').length, 0, 'Startseite rechnet noch selbst (deriveNextSend)');
	});
	// Issue #2346 S3: der Hero formatiert nicht mehr selbst, sondern bekommt homeHeroProps(kind, sub,
	// nextBriefings) gereicht (-> kachelVersand -> formatNextBriefing; Verhalten bewacht
	// routes/_home/__tests__/home_hero_verdrahtung.test.ts). Hier: beide Heros reichen den Backend-Wert.
	test('Hero „Nächster Versand" aus dem Backend-Wert (homeHeroProps mit nextBriefings)', () => {
		const args = aufrufArgumente(ast, 'homeHeroProps');
		assert.equal(args.length, 2, `Trip- und Vergleichs-Hero erwartet: ${JSON.stringify(args)}`);
		for (const a of args) assert.equal(a[2], 'nextBriefings', `homeHeroProps(${a.join(', ')}) bekommt nicht den Backend-Wert`);
	});
	test('homeCompareTimeline bekommt den Backend-Wert, nicht die Browser-Uhr `now`', () => {
		const args = aufrufArgumente(ast, 'homeCompareTimeline');
		assert.ok(args.length > 0, 'Messaufbau: homeCompareTimeline wird nicht mehr aufgerufen');
		for (const a of args) assert.notEqual(a[1], 'now', `homeCompareTimeline(${a.join(', ')}) rechnet noch mit now`);
	});
});
