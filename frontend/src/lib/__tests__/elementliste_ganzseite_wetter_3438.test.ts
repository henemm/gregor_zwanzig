// TDD RED — Issue #3438 (Epic #2913): Mockup Fassung 4 und Elementliste nach der Zuordnung der
// Bildprüfer-Befunde (Knopffarbe, Meta-Zeile Orte, Besitzer-/Freigabe-Konsistenz).
// Spec: docs/specs/modules/fix_3438_wetter_ganzseite.md — AC-8 (Knopf „Test schicken ▾“ im Mockup mit
// Fläche --g-accent-deep, Abweichung nicht mehr offen), AC-6 (Besitzer-Einträge zu „Vergleichstabelle“
// entfallen), AC-10 (keine Besitzer-/Freigabe-Zeile verweist auf eine entfallene Element-ID).
//
// doc-compliance-test — der Knopf-Teil liest die Mockup-Datei als Daten: Das Mockup ist hier selbst das
// Prüfobjekt (Soll-Bild des Bildprüfers und Quelle der Elementliste), nicht Ersatz für Produktverhalten.
// Die Produkt-Fläche prüft hub_kopf_c2_bildabgleich.test.ts (Kaskade am gerenderten Knopf) und auf
// Staging hub-kopf-c2-bildabgleich.staging.spec.ts. Der Elementlisten-Hash steht in elementliste_aktuell.test.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_ganzseite_wetter_3438.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const KONTEXT = join(FRONTEND, '..', 'docs/context/einstellungen_neu');
const MOCKUP = readFileSync(join(KONTEXT, 'seiten/mockup-hub-fassung4.html'), 'utf8');

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const LISTE: Json[] = JSON.parse(readFileSync(join(KONTEXT, 'elementliste.json'), 'utf8')).elemente;
const BESITZER: Json = JSON.parse(readFileSync(join(KONTEXT, 'elementliste_besitzer.json'), 'utf8'));
const FREIGABEN: Json[] = JSON.parse(readFileSync(join(KONTEXT, 'elementliste_freigaben.json'), 'utf8')).freigaben;

// ── Mockup-CSS: Fläche eines Elements aus den einfachen Klassen-/ID-Regeln des <style>-Blocks ──────────
interface Regel { teile: string[]; spez: number; ordnung: number; decls: Record<string, string> }

function regeln(html: string): Regel[] {
	const css = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n').replace(/\/\*[\s\S]*?\*\//g, '');
	const aus: Regel[] = [];
	let ordnung = 0;
	// Nur Regeln der obersten Ebene (keine @media-Blöcke): der Kopf-Knopf des Mockups auf dem Desktop.
	const oben = css.replace(/@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, '');
	for (const m of oben.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const decls: Record<string, string> = {};
		for (const d of m[2].split(';')) {
			const i = d.indexOf(':');
			if (i > 0) decls[d.slice(0, i).trim()] = d.slice(i + 1).trim();
		}
		for (const sel of m[1].split(',').map((s) => s.trim())) {
			// nur zusammengesetzte einfache Selektoren (.a.b, #id, .a#id) — keine Nachfahren/Pseudo
			if (!/^(?:[.#][\w-]+)+$/.test(sel)) continue;
			const teile = sel.match(/[.#][\w-]+/g)!;
			const spez = teile.reduce((s, t) => s + (t.startsWith('#') ? 100 : 10), 0);
			aus.push({ teile, spez, ordnung: ordnung++, decls });
		}
	}
	return aus;
}

/** Berechneter `background` (bzw. background-color) des Mockup-Elements mit dieser ID. */
function mockupFlaeche(id: string): { wert: string; regel: string } {
	const tag = new RegExp(`<button[^>]*\\bid="${id}"[^>]*>`).exec(MOCKUP);
	assert.ok(tag, `Mockup: Knopf #${id} fehlt`);
	const klassen = (/\bclass="([^"]*)"/.exec(tag[0])?.[1] ?? '').split(/\s+/).filter(Boolean);
	const hat = new Set([...klassen.map((k) => `.${k}`), `#${id}`]);
	const treffer = regeln(MOCKUP)
		.filter((r) => r.teile.every((t) => hat.has(t)) && (r.decls['background'] || r.decls['background-color']))
		.sort((a, b) => a.spez - b.spez || a.ordnung - b.ordnung);
	assert.ok(treffer.length > 0, `Mockup: keine Flächen-Regel für #${id} (${[...hat].join('')})`);
	const r = treffer[treffer.length - 1];
	return { wert: r.decls['background-color'] ?? r.decls['background'], regel: r.teile.join('') };
}

describe('#3438 AC-8: Knopf „Test schicken ▾“ im Mockup mit Fläche --g-accent-deep', () => {
	test('Messaufbau: der Kopf-Knopf #testBtn trägt den Text „Test schicken ▾“', () => {
		assert.match(MOCKUP, /<button[^>]*\bid="testBtn"[^>]*>Test schicken ▾<\/button>/);
	});
	test('Fläche des Kopf-Knopfs ist var(--g-accent-deep) (WCAG-AA, Spec c2 AC-16, ADR-0118)', () => {
		const { wert, regel } = mockupFlaeche('testBtn');
		assert.equal(wert, 'var(--g-accent-deep)', `Mockup-Knopf hat Fläche „${wert}“ aus Regel ${regel} statt var(--g-accent-deep)`);
	});
	test('die Abgleich-Ausnahme „Knopf-Fläche“ für „Test schicken ▾“ ist entfallen (keine offene Abweichung)', () => {
		const offen = (BESITZER.ausnahmen as Json[]).filter((a) => a.text === 'Test schicken ▾' && /accent-deep|Knopf-Fläche/.test(String(a.grund)));
		assert.deepEqual(offen.map((a) => a.grund.slice(0, 80)), [], 'Ausnahme zur Knopf-Fläche steht noch in elementliste_besitzer.json');
	});
});

describe('#3438 AC-6: Besitzer-Einträge zu „Vergleichstabelle“ entfallen', () => {
	test('kein Besitzer-Eintrag nennt „Vergleichstabelle“ / „Comparison table“ (Rückbau-Vermerk #3122 samt Eintrag weg)', () => {
		const treffer = (BESITZER.besitzer as Json[]).filter((b) => /Vergleichstabelle|Comparison table/.test(JSON.stringify(b)));
		assert.deepEqual(
			treffer.map((b) => b.id ?? b.muster),
			[],
			'elementliste_besitzer.json führt noch Einträge zur „Vergleichstabelle“ in der Meta-Zeile'
		);
	});
	test('die Elementliste (Mockup) zeigt in der Meta-Zeile der Orte keine „Vergleichstabelle“', () => {
		const treffer = LISTE.filter((e) => e.ctx === 'orte' && e.abschnitt === 'kopf' && /Vergleichstabelle/.test(String(e.text_de)));
		assert.deepEqual(treffer.map((e) => e.id), []);
	});
});

describe('#3438 AC-10: Besitzer und Freigaben verweisen nur auf vorhandene Elemente', () => {
	const ids = new Set(LISTE.map((e) => e.id));
	const tripel = new Set(LISTE.map((e) => `${e.ctx}|${e.reiter}|${e.abschnitt}`));
	test('jede Element-ID der Besitzerliste steht in der Elementliste (alle Verweise, nicht nur #2913)', () => {
		const verwaist = (BESITZER.besitzer as Json[]).filter((b) => b.art === 'element' && !ids.has(b.id)).map((b) => b.id);
		assert.deepEqual(verwaist, [], 'verwaiste Element-IDs in elementliste_besitzer.json');
	});
	test('jede Freigabe nennt ein vorhandenes Tripel Kontext/Reiter/Abschnitt', () => {
		const verwaist = FREIGABEN.filter((f) => !tripel.has(`${f.ctx}|${f.reiter}|${f.abschnitt}`)).map((f) => `${f.ctx}|${f.reiter}|${f.abschnitt}`);
		assert.deepEqual(verwaist, [], 'verwaiste Freigaben in elementliste_freigaben.json');
	});
});
