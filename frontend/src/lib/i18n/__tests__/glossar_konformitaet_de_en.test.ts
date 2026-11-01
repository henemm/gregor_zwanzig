// doc-compliance-test (liest Katalog und Glossar als DATEN: Konsistenzpruefung)
//
// Issue #2651 (i18n F2, Epic #2644) — AC-3: enthaelt ein deutscher Katalogtext
// einen Produktbegriff des Glossars, steht im englischen Text derselben
// Schluessel die Glossar-Form (Gross-/Kleinschreibung egal, Plural-s erlaubt).
// Geprueft werden alle 17 Frontend-Bereiche. Zusaetzlich: jede Zeile der
// festen Liste steht so im Glossar docs/reference/i18n_glossar.md (die Liste
// ist keine zweite, abweichende Wahrheit).
// Spec: docs/specs/modules/i18n_f2_hilfe_infobox_2651.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/glossar_konformitaet_de_en.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HIER = dirname(fileURLToPath(import.meta.url));
const MESSAGES = join(HIER, '..', 'messages');
// __tests__ -> i18n -> lib -> src -> frontend -> Repo
const GLOSSAR = readFileSync(join(HIER, '..', '..', '..', '..', '..', 'docs', 'reference', 'i18n_glossar.md'), 'utf-8');

/** Stamm (deutsch, klein) -> englische Glossar-Form (klein). */
const BEGRIFFE: [string, string][] = [
	['etappe', 'stage'],
	['ortsvergleich', 'location comparison'],
	['wertebereich', 'target range'],
	['verlässlichkeit', 'confidence'],
	['briefing', 'briefing'],
	['alarm', 'alert'],
	['versand', 'delivery'],
	['korridor', 'corridor'],
	['standardwerte', 'defaults']
];

/**
 * Begruendete Ausnahmen (Schluessel -> Stamm). Nur Faelle, in denen das deutsche
 * Wort NICHT der Produktbegriff ist:
 *  - `fehler.versand.*`: „Versand" ist dort der Sendevorgang („Versand läuft
 *    bereits" = *Sending is already in progress*), nicht der Reiter Versand/Delivery.
 *  - `start.alarm.src`: Bildpfad, kein Text.
 */
const AUSNAHMEN: Record<string, string> = {
	'fehler.versand.unklar': 'versand',
	'fehler.versand.laeuft_bereits': 'versand',
	'fehler.versand.fehlgeschlagen': 'versand',
	'fehler.versand.abgelehnt': 'versand',
	'start.alarm.src': 'alarm'
};

type Katalog = Record<string, string>;
const lade = (lang: string, datei: string): Katalog => JSON.parse(readFileSync(join(MESSAGES, lang, datei), 'utf-8'));
const BEREICHE = readdirSync(join(MESSAGES, 'de')).filter((f) => f.endsWith('.json'));

/** Englische Form (optional mit Plural-s) im Text? */
function enthaeltForm(text: string, form: string): boolean {
	return text.toLowerCase().includes(form);
}

/** Verstoesse `bereich:schluessel | stamm -> form | de || en` fuer die gegebenen Kataloge. */
function verstoesse(de: Katalog, en: Katalog, ausnahmen: Record<string, string> = AUSNAHMEN): string[] {
	const aus: string[] = [];
	for (const [k, wert] of Object.entries(de)) {
		for (const [stamm, form] of BEGRIFFE) {
			if (!wert.toLowerCase().includes(stamm) || ausnahmen[k] === stamm) continue;
			if (!enthaeltForm(en[k] ?? '', form)) aus.push(`${k} | ${stamm} -> ${form} | ${wert} || ${en[k]}`);
		}
	}
	return aus;
}

/** Glossar-Tabellenzeilen als [deutsch, englisch]. */
function glossarZeilen(): [string, string][] {
	return GLOSSAR.split('\n')
		.filter((z) => /^\|[^-]/.test(z))
		.map((z) => z.split('|').slice(1, 3).map((s) => s.trim()) as [string, string]);
}

describe('AC-3: Produktbegriffe erscheinen im Englischen in der Glossar-Form', () => {
	test('Messaufbau: alle 17 Bereiche, je de und en', () => {
		assert.equal(BEREICHE.length, 17, BEREICHE.join(', '));
	});
	test('jeder Katalogschluessel mit Produktbegriff im Deutschen traegt die Glossar-Form im Englischen', () => {
		const alle: string[] = [];
		let geprueft = 0;
		for (const datei of BEREICHE) {
			const de = lade('de', datei);
			const en = lade('en', datei);
			geprueft += Object.values(de).filter((v) => BEGRIFFE.some(([s]) => v.toLowerCase().includes(s))).length;
			alle.push(...verstoesse(de, en).map((v) => `${datei}: ${v}`));
		}
		assert.ok(geprueft > 30, `Messaufbau: nur ${geprueft} Texte mit Produktbegriff gefunden`);
		assert.deepEqual(alle, []);
	});
	test('Hilfe, Begriffserklaerungen und Infoboxen: Beispiele aus der Spec', () => {
		const en = { ...lade('en', 'hilfe.json'), ...lade('en', 'bausteine.json') };
		assert.match(en['tip.wertebereiche'], /target range/i);
		assert.match(en['info.wertebereiche.route'], /target ranges/i);
		assert.match(en['hilfe.befehle.heute.text'], /stage/i);
		assert.match(en['hilfe.briefing.morgens'], /location comparison/i);
		assert.match(en['info.alarme.route'], /alerts/i);
		assert.match(en['hilfe.briefing.abends'], /Delivery/);
	});
	test('Gegenprobe: falsche Uebersetzung und Ausnahme werden erkannt', () => {
		assert.deepEqual(verstoesse({ 'x.a': 'Etappe 1' }, { 'x.a': 'Leg 1' }), ['x.a | etappe -> stage | Etappe 1 || Leg 1']);
		assert.deepEqual(verstoesse({ 'x.a': 'Alarme' }, { 'x.a': 'Alerts' }), []);
		assert.deepEqual(verstoesse({ 'x.a': 'Wertebereiche' }, { 'x.a': 'Value ranges' }).length, 1);
		assert.deepEqual(verstoesse({ 'x.a': 'Versand läuft' }, { 'x.a': 'Sending' }, { 'x.a': 'versand' }), []);
		assert.deepEqual(verstoesse({ 'x.a': 'Ortsvergleich' }, {}).length, 1);
	});
	test('Ausnahmen sind nicht veraltet: jeder Ausnahme-Schluessel existiert mit dem Stamm', () => {
		const de: Katalog = Object.assign({}, ...BEREICHE.map((d) => lade('de', d)));
		for (const [k, stamm] of Object.entries(AUSNAHMEN)) {
			assert.ok(de[k]?.toLowerCase().includes(stamm), `Ausnahme ${k} (${stamm}) ist veraltet`);
		}
	});
});

describe('AC-3: die feste Liste stimmt mit dem Glossar ueberein', () => {
	test('jede Zeile der Liste steht im Glossar mit derselben englischen Form', () => {
		const zeilen = glossarZeilen();
		assert.ok(zeilen.length > 50, 'Messaufbau: Glossar-Tabellen nicht gefunden');
		for (const [stamm, form] of BEGRIFFE) {
			const zeile = zeilen.find(([d]) => [stamm, `${stamm}e`].includes(d.toLowerCase()));
			assert.ok(zeile, `Glossar ohne Zeile fuer ${stamm}`);
			assert.ok(zeile![1].toLowerCase().startsWith(form), `Glossar: ${zeile![0]} = ${zeile![1]}, Liste: ${form}`);
		}
	});
});
