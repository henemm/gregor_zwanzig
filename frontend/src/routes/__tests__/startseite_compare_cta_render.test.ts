// Fix-Loop 1 (F005) — AC-16: das Ziel des Aufruf-Knopfs der Orts-Vergleich-
// Setup-Karte (+page.svelte, SetupResumeCard ctaHref) wird dort gemessen, wo es
// WIRKT: im gerenderten HTML der echten Startseite. Die reine Funktion
// buildCompareCtaHref bewacht _home/__tests__/compare_cta_ziel.test.ts; hier
// wird bewiesen, dass die Seite sie fuer den Knopf auch benutzt.
//
// Mutation, die hier rot werden MUSS: ctaHref der Orts-Vergleich-Karte auf
// einen anderen Wert (z. B. tripCtaHref oder "/compare") umstellen.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderStartseite, aktiverVergleich, links, teilbaum } from './onboardingSsr.ts';

// Pausierter (manueller) Vergleich ohne Ideal-Werte = angefangen, kein aktiver Hero.
const angefangen = (id: string) => ({ ...aktiverVergleich(id), schedule: 'manual' });

describe('AC-16: Aufruf-Knopf der Orts-Vergleich-Karte', () => {
	test('angefangener Vergleich => "Setup fortsetzen" fuehrt auf dessen Hub /compare/<id>', () => {
		const html = renderStartseite({ trips: [], presets: [angefangen('cmp-ssr-7')] });
		const aufruf = links(html).filter((l) => /Setup fortsetzen/.test(l.text));
		assert.ok(aufruf.length >= 1, `kein "Setup fortsetzen"-Knopf gerendert: ${JSON.stringify(links(html))}`);
		for (const l of aufruf) {
			assert.equal(l.href, '/compare/cmp-ssr-7', `Aufruf-Knopf: ${l.text} -> ${l.href}`);
		}
	});
});

// Rauchprobe, dass der Helfer wirklich etwas rendert (sonst waere oben "kein Knopf" die einzige Aussage).
test('Positivkontrolle: Startseite rendert mit angefangenem Vergleich', () => {
	const html = renderStartseite({ trips: [], presets: [angefangen('cmp-ssr-7')] });
	assert.ok(html.includes('cmp-ssr-7'), 'Vergleichs-ID taucht im HTML nicht auf');
	assert.equal(teilbaum(html, 'empty-state'), null, 'Leerzustand darf mit Vergleich nicht erscheinen');
});
