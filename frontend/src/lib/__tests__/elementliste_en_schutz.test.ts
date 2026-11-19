// Issue #2913, Fix-Loop 1 (Adversary F006) — Schutzregeln des Elementlisten-Generators gegen
// erfundenes EN (AC-11). Ohne Browser, gegen den echten i18n-Katalog; je Regel ein Fall, der ohne
// die Regel falsch zugeordnet würde. Synthetische Mini-Kataloge nur dort, wo der echte Katalog den
// Fall heute nicht enthält (leerer EN-Wert, reiner Platzhalter, nicht füllbarer EN-Platzhalter).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_en_schutz.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ladeKatalog, ermittleEn } from '../../../../scripts/elementliste_aus_mockup.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..', '..');
const katalog = ladeKatalog(join(REPO, 'frontend/src/lib/i18n/messages'));

describe('F006: EN-Schutzregeln des Generators', () => {
	test('Wortlaut-Hälfte: „°C · vor der Etappe“ passt nicht zufällig auf „{count} Etappe“', () => {
		// #2968: „vor der Etappe“ steht inzwischen exakt im Katalog (wetter.hinweis.temperature_night) und
		// trifft als Segment (Regel b). Der Schutz gilt dem Muster „{count} Etappe“; darum hier eine Kopie des
		// echten Katalogs OHNE den Wert „vor der Etappe“ — dann bleibt nur „{count} Etappe“, und das darf nie greifen.
		const ohne: typeof katalog = { de: {}, en: {} };
		for (const [k, v] of Object.entries(katalog.de)) {
			if (v.replace(/\s+/g, ' ').trim() === 'vor der Etappe') continue;
			ohne.de[k] = v;
			ohne.en[k] = katalog.en[k];
		}
		// Vorbedingung: das kurze Muster existiert im echten Katalog (sonst wäre der Fall wertlos).
		assert.ok(Object.values(ohne.de).includes('{count} Etappe'), 'Muster „{count} Etappe“ fehlt im Katalog');
		const r = ermittleEn('°C · vor der Etappe', ohne);
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
		// Mit dem Ist-Katalog trifft das Segment, aber nie über „{count} Etappe“.
		const ist = ermittleEn('°C · vor der Etappe', katalog);
		assert.notEqual(ist.muster, '{count} Etappe');
		assert.doesNotMatch(ist.text_en ?? '', /\{count\}/);
	});
	test('Wortlaut-Hälfte erlaubt echte Muster („Etappe T3 auswählen“)', () => {
		// #2913 Fix-Loop 2 (C5): EN bleibt Muster mit Platzhalter, kein DE-Wert eingesetzt.
		assert.equal(ermittleEn('Etappe T3 auswählen', katalog).text_en, 'Select stage {code}');
	});
	test('Wertlänge: eingesetzter Wert über 40 Zeichen ⇒ Lücke; bis 40 Zeichen ⇒ Treffer', () => {
		// #2794 Teil-PR 4a: das fruehere Muster `layout.korridor.pflicht` ist mit dem
		// Korridor-Editor entfallen — gleichartiges Muster (Wortlaut + Platzhalter am Ende).
		const vor = 'Letzter Lauf fehlgeschlagen: ';
		const kurz = ermittleEn(vor + 'Wind, Böen', katalog);
		assert.equal(kurz.i18n_key, 'konto.reports.lauf_fehlgeschlagen_mit');
		// C5: die deutschen Werte landen nicht im EN-Text — EN bleibt das Katalog-Muster.
		assert.equal(kurz.text_en, 'Last run failed: {fehler}');
		assert.doesNotMatch(kurz.text_en ?? '', /Böen/);
		const lang = ermittleEn(vor + 'Wind, Böen, Regen, Gewitter, Temperatur, Schneefallgrenze', katalog);
		assert.equal(lang.luecke, true, JSON.stringify(lang));
	});
	test('Normalisierung: Leerraum am Rand und doppelte Leerzeichen hindern den exakten Treffer nicht', () => {
		assert.equal(ermittleEn('  Zustellung \n', katalog).text_en, 'Delivery');
	});
	test('leerer EN-Wert ist kein Treffer (exakt und Muster)', () => {
		const k = { de: { a: 'Hallo Welt', b: 'Gruß an {name} heute' }, en: { a: '', b: '  ' } };
		assert.equal(ermittleEn('Hallo Welt', k).luecke, true);
		assert.equal(ermittleEn('Gruß an Anna heute', k).luecke, true);
	});
	test('reines Platzhalter-Muster passt nicht auf alles (Mindest-Wortlaut)', () => {
		const k = { de: { a: '{name}', b: '{x} {y}' }, en: { a: '{name}', b: '{x} {y}' } };
		assert.equal(ermittleEn('Beliebiger Text', k).luecke, true);
		// Fall, den die Wortlaut-Hälfte allein durchließe (Wortlaut „: “ ist die Hälfte von „x: y“):
		const kurz = { de: { a: '{a}: {b}' }, en: { a: '{a}: {b}' } };
		assert.equal(ermittleEn('x: y', kurz).luecke, true);
	});
	test('EN mit Platzhalter, den DE nicht liefert, wird nicht verwendet (nichts erfinden)', () => {
		const k = { de: { a: 'Etappe {code} wählen' }, en: { a: 'Select stage {code} of {total}' } };
		const r = ermittleEn('Etappe T3 wählen', k);
		assert.equal(r.luecke, true, JSON.stringify(r));
	});
});
