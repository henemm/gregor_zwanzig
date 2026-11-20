// Issue #3194 (Workflow feat-3194-elementliste-en-zusammengesetzt): Regel g „zusammengesetzt“ im EN-Zuordner
// des Elementlisten-Erzeugers (scripts/elementliste_aus_mockup.ts).
// Das Mockup zeigt Wetter-Dialogtexte so, wie die App sie aus mehreren Katalogschlüsseln zusammensetzt
// (GrenzenEditor: Titel `_1`+`_2` ohne Fuge, Hinweis + „Abweichend …“; VorlageKarte: Rumpf `ersetzt_*` + `bleibt`).
// Sollwerte werden IMMER aus dem echten EN-Katalog gelesen, nie im Test erfunden.
// Ohne Browser, ohne Mocks, gegen den echten i18n-Katalog.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_zusammengesetzt_3194.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as gen from '../../../../scripts/elementliste_aus_mockup.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..', '..');
const katalog = gen.ladeKatalog(join(REPO, 'frontend/src/lib/i18n/messages'));

const de = (k: string): string => {
	const v = katalog.de[k];
	assert.equal(typeof v, 'string', `DE-Katalogschlüssel fehlt: ${k}`);
	return v;
};
const en = (k: string): string => {
	const v = katalog.en[k];
	assert.equal(typeof v, 'string', `EN-Katalogschlüssel fehlt: ${k}`);
	return v;
};
const mitVorlage = (s: string, name: string) => s.replace('{vorlage}', name);

const G = 'wetter.grenzen.';
const V = 'wetter.vorlage.';
const KEINS = 'wetter.gewitter.keins_gruen';

/** Erwartung: Treffer, EN exakt aus dem Katalog, erster Schlüssel der Folge. */
function erwarteTreffer(textDe: string, sollEn: string, ersterKey: string) {
	const r = gen.ermittleEn(textDe, katalog);
	assert.equal(r.luecke, false, `Lücke statt Zuordnung für „${textDe}“`);
	assert.equal(r.text_en, sollEn);
	assert.equal(r.i18n_key, ersterKey);
	return r;
}

function erwarteLuecke(textDe: string, k: gen.Katalog = katalog) {
	const r = gen.ermittleEn(textDe, k);
	assert.equal(r.luecke, true, `„${textDe}“ wurde zugeordnet (${r.i18n_key} ⇒ ${r.text_en}), erwartet Lücke`);
	assert.equal(r.text_en, null);
}

// ------------------------------------------------------------------ AC-1: Muster A bis D

test('#3194 AC-1 A1: „obenzu viel“ ⇒ EN = oben_1 + oben_2 ohne Fuge (aus dem Katalog)', () => {
	const textDe = de(G + 'oben_1') + de(G + 'oben_2');
	assert.equal(textDe, 'obenzu viel', 'Mockup-Text muss die DE-Folge ohne Fuge sein');
	erwarteTreffer(textDe, en(G + 'oben_1') + en(G + 'oben_2'), G + 'oben_1');
});

test('#3194 AC-1 A2: „untenzu wenig“ ⇒ EN = unten_1 + unten_2 ohne Fuge (aus dem Katalog)', () => {
	const textDe = de(G + 'unten_1') + de(G + 'unten_2');
	assert.equal(textDe, 'untenzu wenig');
	erwarteTreffer(textDe, en(G + 'unten_1') + en(G + 'unten_2'), G + 'unten_1');
});

test('#3194 AC-1 B: Grünhinweis + „Abweichend von der Vorlage „Allgemein““ ⇒ EN-Hinweis + EN-abweichend', () => {
	const textDe = de(G + 'hinweis') + ' ' + mitVorlage(de(G + 'abweichend'), 'Allgemein');
	const r = erwarteTreffer(textDe, en(G + 'hinweis') + ' ' + en(G + 'abweichend'), G + 'hinweis');
	assert.equal(r.muster, de(G + 'hinweis') + ' ' + de(G + 'abweichend'), 'muster = DE-Gesamtmuster mit {vorlage}');
});

test('#3194 AC-1 C: „keins“-Hinweis + „Abweichend …“ ⇒ EN keins_gruen + EN-abweichend', () => {
	const textDe = de(KEINS) + ' ' + mitVorlage(de(G + 'abweichend'), 'Allgemein');
	const r = erwarteTreffer(textDe, en(KEINS) + ' ' + en(G + 'abweichend'), KEINS);
	assert.equal(r.muster, de(KEINS) + ' ' + de(G + 'abweichend'));
});

test('#3194 AC-1 D1: Bestätigungs-Rumpf Trip ⇒ ersetzt_route + bleibt', () => {
	const textDe = de(V + 'ersetzt_route') + ' ' + de(V + 'bleibt');
	erwarteTreffer(textDe, en(V + 'ersetzt_route') + ' ' + en(V + 'bleibt'), V + 'ersetzt_route');
});

test('#3194 AC-1 D2: Bestätigungs-Rumpf Orte ⇒ ersetzt_vergleich + bleibt, keine Vermischung mit Trip', () => {
	const textDe = de(V + 'ersetzt_vergleich') + ' ' + de(V + 'bleibt');
	const r = erwarteTreffer(textDe, en(V + 'ersetzt_vergleich') + ' ' + en(V + 'bleibt'), V + 'ersetzt_vergleich');
	assert.ok(!String(r.text_en).startsWith(en(V + 'ersetzt_route')), 'Orte-Rumpf bekam den Trip-Text');
});

test('#3194 AC-1: Reihenfolge bleibt — EN beginnt mit dem EN des ersten Schlüssels', () => {
	const r = gen.ermittleEn(de(G + 'oben_1') + de(G + 'oben_2'), katalog);
	assert.ok(String(r.text_en).startsWith(en(G + 'oben_1')), `vertauschte Folge: ${r.text_en}`);
	assert.notEqual(r.text_en, en(G + 'oben_2') + en(G + 'oben_1'));
	assert.notEqual(r.text_en, en(G + 'oben_1') + ' ' + en(G + 'oben_2'), 'EN-Fuge muss der DE-Fuge folgen (keine)');
});

// ------------------------------------------------------------------ AC-2: Platzhalter {vorlage}

test('#3194 AC-2: zwei Vorlagennamen treffen dasselbe EN-Muster, der Name wird nicht ins EN kopiert', () => {
	for (const [kopf, key] of [
		[de(G + 'hinweis'), G + 'hinweis'],
		[de(KEINS), KEINS]
	] as const) {
		const a = gen.ermittleEn(kopf + ' ' + mitVorlage(de(G + 'abweichend'), 'Allgemein'), katalog);
		const b = gen.ermittleEn(kopf + ' ' + mitVorlage(de(G + 'abweichend'), 'Alpen-Trekking'), katalog);
		assert.equal(a.luecke, false, `${key}: „Allgemein“ blieb Lücke`);
		assert.equal(b.luecke, false, `${key}: „Alpen-Trekking“ blieb Lücke`);
		assert.equal(a.text_en, b.text_en);
		assert.ok(String(a.text_en).includes('{vorlage}'), `Platzhalter fehlt: ${a.text_en}`);
		assert.ok(!String(a.text_en).includes('Allgemein') && !String(b.text_en).includes('Alpen-Trekking'));
	}
});

// ------------------------------------------------------------------ AC-3: Negativproben

test('#3194 AC-3: falsche Fuge, fehlender Teil, fremder Zusatz, vertauschte oder gemischte Folge ⇒ Lücke', () => {
	const hinweis = de(G + 'hinweis');
	const abw = mitVorlage(de(G + 'abweichend'), 'Allgemein');
	const faelle = [
		de(G + 'oben_1') + ' ' + de(G + 'oben_2'), // Fuge Leerzeichen statt keiner
		de(G + 'oben_2') + de(G + 'oben_1'), // vertauscht
		de(G + 'oben_1') + de(G + 'unten_2'), // gemischte Folge („obenzu wenig“)
		de(G + 'oben_1') + de(G + 'oben_2') + ' extra', // fremder Zusatz
		hinweis + abw, // B ohne Fuge
		hinweis + '  ' + abw.replace('Abweichend', 'abweichend'), // B mit verfälschtem zweiten Teil
		hinweis + ' ' + abw + ' Noch ein Satz.', // B mit Zusatz
		abw + ' ' + hinweis, // B vertauscht
		de(V + 'ersetzt_route') + de(V + 'bleibt'), // D ohne Fuge
		de(V + 'ersetzt_route') + ' ' + de(G + 'hinweis') // D mit fremdem zweiten Teil
	];
	for (const t of faelle) erwarteLuecke(t);
});

test('#3194 AC-3: Schlüssel ohne EN-Wert ⇒ Lücke, kein EN ohne Katalogquelle', () => {
	// Gegenprobe: mit vollständigem Katalog ist es ein Treffer …
	const textDe = de(G + 'oben_1') + de(G + 'oben_2');
	assert.equal(gen.ermittleEn(textDe, katalog).luecke, false, 'Vorbedingung: vollständiger Katalog trifft');
	// … fehlt EN für EINEN Schlüssel der Folge, bleibt es Lücke.
	for (const fehlt of [G + 'oben_2', G + 'oben_1']) {
		const enOhne = { ...katalog.en };
		delete enOhne[fehlt];
		erwarteLuecke(textDe, { de: { ...katalog.de }, en: enOhne });
	}
	const enLeer = { ...katalog.en, [G + 'abweichend']: '' };
	erwarteLuecke(de(G + 'hinweis') + ' ' + mitVorlage(de(G + 'abweichend'), 'Allgemein'), { de: { ...katalog.de }, en: enLeer });
});

// ------------------------------------------------------------------ Tabelle

test('#3194: Tabelle ZUSAMMENGESETZT ist exportiert und deklarativ (mind. A1, A2, B, C, D1, D2)', () => {
	const tabelle = (gen as Record<string, unknown>).ZUSAMMENGESETZT;
	assert.ok(Array.isArray(tabelle), 'ZUSAMMENGESETZT fehlt oder ist keine Liste');
	assert.ok(tabelle.length >= 6, `nur ${tabelle.length} Zeilen`);
});

// ------------------------------------------------------------------ AC-1/a–f unverändert

test('#3194 AC-4: Regeln a–f bleiben — Einzelschlüssel weiter exakt, „gelb >“ weiter Regel e', () => {
	const oben = gen.ermittleEn(de(G + 'oben_1'), katalog);
	assert.equal(oben.luecke, false);
	assert.equal(oben.text_en, en(G + 'oben_1'));
	assert.equal(gen.ermittleEn(de(KEINS), katalog).text_en, en(KEINS));
	const abw = gen.ermittleEn(mitVorlage(de(G + 'abweichend'), 'Allgemein'), katalog);
	assert.equal(abw.i18n_key, G + 'abweichend');
	assert.equal(abw.text_en, en(G + 'abweichend'));
});

// ------------------------------------------------------------------ AC-7: Determinismus (ohne Browser)

test('#3194 AC-7: baueElemente zweimal ⇒ byte-identische Ausgabe, zusammengesetzte Texte keine Lücke', () => {
	const gruppen: gen.Rohgruppe[] = [
		{
			ctx: 'trip',
			reiter: 'wetter',
			zustand: 'normal',
			segment: null,
			roh: [
				{ abschnitt: 'dialog', rolle: 'titel', text: de(G + 'oben_1') + de(G + 'oben_2') },
				{ abschnitt: 'dialog', rolle: 'text', text: de(G + 'hinweis') + ' ' + mitVorlage(de(G + 'abweichend'), 'Allgemein') },
				{ abschnitt: 'dialog', rolle: 'text', text: de(V + 'ersetzt_route') + ' ' + de(V + 'bleibt') }
			]
		}
	];
	const liste = (): gen.Elementliste => ({ schema: 1, mockup: 'x', mockup_hash: 'sha256:x', elemente: gen.baueElemente(gruppen, katalog) });
	const a = gen.alsJson(liste());
	const b = gen.alsJson(liste());
	assert.equal(a, b);
	const elemente = liste().elemente;
	assert.deepEqual(elemente.map((e) => e.luecke), [false, false, false]);
});

// ------------------------------------------------------------------ Artefakt: neu erzeugte Elementliste

test('#3194 AC-4/5: erzeugte elementliste.json trägt für A–D keine Lücke mehr, EN aus dem Katalog', () => {
	const liste = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf8')) as gen.Elementliste;
	const soll = new Map<string, string>([
		[de(G + 'oben_1') + de(G + 'oben_2'), en(G + 'oben_1') + en(G + 'oben_2')],
		[de(G + 'unten_1') + de(G + 'unten_2'), en(G + 'unten_1') + en(G + 'unten_2')],
		[de(V + 'ersetzt_route') + ' ' + de(V + 'bleibt'), en(V + 'ersetzt_route') + ' ' + en(V + 'bleibt')],
		[de(V + 'ersetzt_vergleich') + ' ' + de(V + 'bleibt'), en(V + 'ersetzt_vergleich') + ' ' + en(V + 'bleibt')]
	]);
	for (const name of ['Allgemein', 'Alpen-Trekking']) {
		soll.set(de(G + 'hinweis') + ' ' + mitVorlage(de(G + 'abweichend'), name), en(G + 'hinweis') + ' ' + en(G + 'abweichend'));
		soll.set(de(KEINS) + ' ' + mitVorlage(de(G + 'abweichend'), name), en(KEINS) + ' ' + en(G + 'abweichend'));
	}
	const treffer = liste.elemente.filter((e) => soll.has(e.text_de));
	assert.ok(treffer.length >= 100, `nur ${treffer.length} zusammengesetzte Einträge in der Liste`);
	const offen = treffer.filter((e) => e.luecke || e.text_en !== soll.get(e.text_de));
	assert.equal(offen.length, 0, `${offen.length} zusammengesetzte Einträge noch Lücke/falsch, z. B. „${offen[0]?.text_de}“`);
});
