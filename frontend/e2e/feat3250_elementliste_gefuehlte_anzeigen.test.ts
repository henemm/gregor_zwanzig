// Issue #3250 (Epic #2913): Gefühlte Anzeige-Metriken Nacht/Tages-Tief/Tages-Hoch im Mockup Fassung 4.
// Spec: docs/specs/modules/feat_3250_gefuehlte_anzeigen_mockup.md (AC-1, AC-2, AC-3, AC-4, AC-5; Test Plan
// „Elementlisten-Test“, „Reihenfolge-Test“, „Zähler-Test“).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3250_elementliste_gefuehlte_anzeigen.test.ts
//
// Geprüft wird die ERZEUGTE Elementliste (docs/context/einstellungen_neu/elementliste.json), nicht der
// Mockup-Quelltext: Sie entsteht deterministisch per scripts/elementliste_aus_mockup.ts aus dem gerenderten
// Mockup und ist per Prüfsumme an den aktuellen Mockup-Stand gebunden. Was hier steht, zeigt das Mockup
// also wirklich an (Gruppe, Reihenfolge, Zeilentexte, Zähler).
//
// Erwartete Werte kommen aus dem Textkatalog (Metrik-Namen wertebereiche.json, Nur-Anzeige-Texte
// wetter.json), nicht aus einer Kopie: Mockup und App müssen dieselben Wörter zeigen.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const MSG = join(REPO, 'frontend/src/lib/i18n/messages');

type Eintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	i18n_key: string | null;
	text_en: string | null;
};

const LISTE: { elemente: Eintrag[] } = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf-8'));
const kat = (sprache: 'de' | 'en', bereich: string): Record<string, string> =>
	JSON.parse(readFileSync(join(MSG, sprache, `${bereich}.json`), 'utf-8'));
const WB_DE = kat('de', 'wertebereiche');
const WB_EN = kat('en', 'wertebereiche');
const WT_DE = kat('de', 'wetter');
const WT_EN = kat('en', 'wetter');

/** Reihenfolge wie die App (_REITER_WETTER): Nacht, Tages-Tief, Tages-Hoch. */
const NEU = ['wind_chill_night', 'wind_chill_day_low', 'wind_chill_day_high'] as const;
const nameDe = (id: string) => WB_DE[`wertebereiche.symbolzeile.${id}`];
const nameEn = (id: string) => WB_EN[`wertebereiche.symbolzeile.${id}`];

/** Untertitel wie im Mockup: `[Einheit, Hinweis].join(' · ')`, Hinweis = Nur-Anzeige-Hinweis des Katalogs. */
const UNTERTITEL = `°C · ${WT_DE['wetter.untertitel.nur_anzeige']}`;
const MITTE = WT_DE['wetter.zeile.nur_anzeige'];
/** Mockup-Wortlaut des Erklärsatzes (mockup-hub-fassung4.html, why() für Nur-Anzeige-Zeilen), wie #3204. */
const ERKLAER_MOCKUP = 'Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten unter „Was steht wo“ ein.';
/** AC-4: Zählersatz nach der Ergänzung (9 alarmfähige von 18 aktiven, 8 ohne Alarm). */
const ZAEHLER_SOLL = '9 von 18 Metriken lösen einen Alarm aus. 8 können keinen auslösen';

/** Zeilen der Metrikliste eines Kontexts in einem Zustand, in Dokumentreihenfolge. */
const metriken = (ctx: string, zustand = 'normal'): Eintrag[] =>
	LISTE.elemente
		.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === zustand && e.abschnitt === 'metriken')
		.sort((a, b) => a.ordnung - b.ordnung);

/** Die Einträge einer Metrik-Zeile: ab dem Namen bis vor den nächsten Entfernen-Knopf bzw. die nächste Gruppe. */
function zeile(liste: Eintrag[], name: string): Eintrag[] {
	const i = liste.findIndex((e) => e.rolle === 'text' && e.text_de === name);
	assert.ok(i >= 0, `Metrik-Zeile „${name}“ fehlt in der Elementliste (Trip, Reiter Wetter, Metriken). Mockup TRIP_METRICS ergänzen und Elementliste neu erzeugen.`);
	const rest = liste.slice(i + 1);
	const ende = rest.findIndex((e) => e.i18n_key === 'wetter.zeile.entfernen' || e.rolle === 'beschriftung' || e.rolle === 'chip');
	return ende < 0 ? rest : rest.slice(0, ende);
}

describe('#3250 AC-1/AC-2: Gruppe Temperatur im Mockup (Trip) wie in der App', () => {
	test('Katalog kennt alle drei Namen (Vorbedingung)', () => {
		for (const id of NEU) {
			assert.ok(nameDe(id), `DE-Name ${id} fehlt in wertebereiche.json`);
			assert.ok(nameEn(id), `EN-Name ${id} fehlt in wertebereiche.json`);
		}
	});

	for (const zustand of ['normal', 'luecken']) {
		test(`Reihenfolge der Gruppe Temperatur inkl. gefühlter Anzeige-Zeilen (Zustand ${zustand})`, () => {
			const liste = metriken('trip', zustand);
			const soll = [
				'Temperatur',
				'Tiefsttemperatur Nacht',
				nameDe('temperature_day_low'),
				nameDe('temperature_day_high'),
				nameDe('wind_chill'),
				...NEU.map(nameDe)
			];
			const von = liste.findIndex((e) => e.rolle === 'beschriftung' && e.text_de === 'Temperatur');
			const bis = liste.findIndex((e, i) => i > von && e.rolle === 'beschriftung');
			assert.ok(von >= 0 && bis > von, 'Gruppe Temperatur nicht gefunden');
			const ist = liste.slice(von + 1, bis).filter((e) => e.rolle === 'text' && soll.includes(e.text_de)).map((e) => e.text_de);
			assert.deepEqual(ist, soll, 'Gruppe Temperatur im Mockup weicht von der App-Reihenfolge ab');
		});
	}

	test('Namen tragen die englischen Katalognamen (AC-2, EN-Abgleich)', () => {
		const liste = metriken('trip');
		for (const id of NEU) {
			const e = liste.find((x) => x.rolle === 'text' && x.text_de === nameDe(id));
			assert.ok(e, `„${nameDe(id)}“ fehlt in der Elementliste`);
			assert.equal(e!.text_en, nameEn(id), `EN-Name von ${id}`);
		}
	});
});

describe('#3250 AC-3: Nur-Anzeige-Form wie Windrichtung und #3204', () => {
	for (const id of NEU) {
		test(`${id}: Untertitel „${UNTERTITEL}“, Zeilenmitte, Erklärsatz, ohne Grenzen und Alarm-Auswahl`, () => {
			const z = zeile(metriken('trip'), nameDe(id));
			const texte = z.map((e) => e.text_de);
			assert.ok(texte.includes(UNTERTITEL), `Untertitel fehlt: ${JSON.stringify(texte)}`);
			const mitte = z.find((e) => e.text_de === MITTE);
			assert.ok(mitte, `Zeilenmitte „${MITTE}“ fehlt: ${JSON.stringify(texte)}`);
			assert.equal(mitte!.i18n_key, 'wetter.zeile.nur_anzeige');
			assert.ok(!z.some((e) => e.i18n_key === 'wetter.grenzen.aendern'), '„Grenzen ändern“ in einer Nur-Anzeige-Zeile');
			assert.ok(!z.some((e) => e.rolle === 'option'), 'Alarm-Auswahl in einer Nur-Anzeige-Zeile');

			const satz = z.find((e) => e.text_de.startsWith('Nur Anzeige:'));
			assert.ok(satz, `Erklärsatz fehlt: ${JSON.stringify(texte)}`);
			assert.equal(satz!.text_de, ERKLAER_MOCKUP, 'Erklärsatz im Mockup geändert');
			assert.equal(satz!.i18n_key, 'wetter.erklaer.anzeige', 'Erklärsatz der Elementliste ohne Katalogschlüssel');
			assert.equal(satz!.text_en, WT_EN['wetter.erklaer.anzeige'], 'EN-Text des Erklärsatzes');
		});
	}
});

describe('#3250 AC-4: Zähler über der Metrikliste (Trip)', () => {
	for (const zustand of ['normal', 'luecken']) {
		test(`Zählersatz „${ZAEHLER_SOLL} …“ (Zustand ${zustand})`, () => {
			const z = metriken('trip', zustand).find((e) => e.i18n_key === 'wetter.alarm_ab.zaehler');
			assert.ok(z, 'Zählersatz fehlt in der Elementliste (Trip, Reiter Wetter)');
			assert.ok(z!.text_de.startsWith(ZAEHLER_SOLL), `Zähler lautet „${z!.text_de}“, erwartet Beginn „${ZAEHLER_SOLL}“`);
		});
	}
});

describe('#3250 AC-5: Orts-Vergleich bietet die gefühlten Anzeige-Metriken nicht an (ADR-0011)', () => {
	test('keine Zeile, kein Chip, kein Text der drei Metriken in Orte', () => {
		const orte = LISTE.elemente.filter((e) => e.ctx === 'orte');
		assert.ok(orte.length > 0, 'Orte-Elemente fehlen');
		for (const id of NEU) {
			const treffer = orte.filter((e) => e.text_de.includes(nameDe(id)));
			assert.deepEqual(treffer.map((e) => e.id), [], `${nameDe(id)} erscheint im Orts-Vergleich`);
		}
	});
});
