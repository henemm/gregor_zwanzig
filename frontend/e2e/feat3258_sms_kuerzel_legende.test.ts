// Issue #3258 (Epic #2913): SMS-Kürzel-Legende „Kürzel erklärt“ im Mockup Fassung 4 (Option C).
// Spec: docs/specs/modules/feat_3258_sms_kuerzel_legende.md (AC-1, AC-2, AC-3, AC-4; Test Plan).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3258_sms_kuerzel_legende.test.ts
//
// Geprüft werden Daten, die der Generator erzeugt bzw. der Abgleich-Lauf liest:
//   - die ERZEUGTE Elementliste (docs/context/einstellungen_neu/elementliste.json) führt im Abschnitt
//     `was-steht-wo` (Reiter Wetter, Zustand normal, ctx trip und orte) den Block „Kürzel erklärt“: Titel,
//     je aktiver SMS-Metrik Kürzel und Bedeutung, danach die festen Einträge mit Soll-Text DE/EN aus dem
//     Katalog wetter.wsw.legende.* (AC-1, AC-2);
//   - die Gegenrichtung des Abgleichs (findeZusaetzliche + wendeBesitzerAn mit echter Elementliste,
//     Ausnahmen und Besitzerliste) lässt keinen Text der Legende und keinen SMS-Beispielwert mehr
//     herrenlos (AC-3, AC-4); `{zahl}` erklärt dabei nur Zahlen (Gegenprobe mit Buchstaben).
//
// Herkunft der Live-Texte (Testerwartung, keine erfundenen Werte):
//   - Staging-Abgleich `--scope wetter`, DE und EN, Trip und Orte, abgelegt als
//     docs/artifacts/fix-3192-wetter-dialog-abgleich/abgleich-{de,en}-2.json (Feld `zusaetzlich`,
//     Besitzer leer). Daraus stammen die Legenden-Texte (Kürzel, Bedeutungen, feste Einträge) und die
//     SMS-Beispielwerte FN12, FD12/16, „TF- FN12 FD12/16“ und die ganze Trip-SMS-Zeile.
//   - Metrik-Bedeutungen: Server-Katalog `kuerzel_bedeutung_de/en` (src/app/metric_catalog.py), den
//     die Live-Antwort `legend.metrics[].meaning` liefert (src/services/placements_view_service.py
//     `_legende`). Ein lesender Abruf GET /api/briefings/{id}/placements mit dem Staging-Prüfkonto am
//     22.11.2026 fand keinen Datensatz (Trips/Vergleiche leer, 404); die Werte oben stimmen mit dem
//     Katalog überein (z. B. FN „N gefühlt“, FD „D gefühlt“, W „Wind km/h“, CT „Bewölkung gesamt“).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const leseText = (rel: string) => readFileSync(join(REPO, rel), 'utf-8');
const lese = (rel: string) => JSON.parse(leseText(rel));

type Eintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	muster: string | null;
	i18n_key: string | null;
	text_en: string | null;
	luecke?: boolean;
};

const LISTE_PFAD = 'docs/context/einstellungen_neu/elementliste.json';
const BESITZER_PFAD = 'docs/context/einstellungen_neu/elementliste_besitzer.json';
const LISTE: { elemente: Eintrag[] } = lese(LISTE_PFAD);
const KAT_DE: Record<string, string> = lese('frontend/src/lib/i18n/messages/de/wetter.json');
const KAT_EN: Record<string, string> = lese('frontend/src/lib/i18n/messages/en/wetter.json');
const BESITZER_ROH: { besitzer: Array<Record<string, string | undefined>> } = lese(BESITZER_PFAD);

const ABSCHNITT = 'was-steht-wo';
const TITEL_DE = KAT_DE['wetter.wsw.legende.titel'];
const TITEL_EN = KAT_EN['wetter.wsw.legende.titel'];
const ENDE_DE = KAT_DE['wetter.wsw.bloecke.titel'] ?? 'Ganze Blöcke ein- und ausschalten';

/** Feste Einträge in der Reihenfolge der Live-Antwort (`_legende`, `fest`), Token wie live gerendert. */
const FEST: Array<{ token: string; key: string }> = [
	{ token: '@14', key: 'zeit_ab_gelb' },
	{ token: '!TS:H@14', key: 'amtliche_warnung' },
	{ token: 'L', key: 'stufe_gelb' },
	{ token: 'M', key: 'stufe_orange' },
	{ token: 'H', key: 'stufe_rot' },
	{ token: 'WG', key: 'warnung_wind' },
	{ token: 'RA', key: 'warnung_starkregen' },
	{ token: 'AV4', key: 'lawinenstufe' },
	{ token: 'X?', key: 'warnquelle_nicht_erreichbar' },
];

/** Metrik-Kürzel mit Bedeutung (Server-Katalog, live bestätigt), die das Mockup je Kontext mindestens führt. */
const METRIK: Record<string, Array<[string, string]>> = {
	trip: [
		['TF', 'gefühlt'],
		['FN', 'N gefühlt'],
		['FD', 'D gefühlt'],
		['W', 'Wind km/h'],
		['FZ', 'Nullgradgrenze m'],
		['SL', 'Schneefallgrenze m'],
	],
	orte: [
		['W', 'Wind km/h'],
		['R', 'Regen mm'],
		['PR', 'Regenwahrscheinlichkeit %'],
		['CT', 'Bewölkung gesamt'],
	],
};
/** Fester Orte-Eintrag O1 (Server-Katalog vergleich.sms.ort_nummer, live bestätigt). */
const O1 = { token: 'O1', de: 'Ort 1 in der Reihenfolge des Abos' };

const wsw = (ctx: string): Eintrag[] =>
	LISTE.elemente
		.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === 'normal' && e.abschnitt === ABSCHNITT)
		.sort((a, b) => a.ordnung - b.ordnung);

/** Einträge des Blocks „Kürzel erklärt“: nach dem Titel, vor „Ganze Blöcke ein- und ausschalten“. */
function legende(ctx: string): { titel: Eintrag | undefined; eintraege: Eintrag[] } {
	const alle = wsw(ctx);
	const i = alle.findIndex((e) => e.text_de === TITEL_DE);
	if (i < 0) return { titel: undefined, eintraege: [] };
	const ende = alle.findIndex((e, j) => j > i && e.text_de === ENDE_DE);
	return { titel: alle[i], eintraege: alle.slice(i + 1, ende < 0 ? undefined : ende) };
}

/** Index des Paars Kürzel→Bedeutung (Bedeutung steht direkt hinter dem Kürzel), sonst -1. */
function paarIndex(eintraege: Eintrag[], token: string, bedeutung: string): number {
	return eintraege.findIndex((e, i) => e.text_de === token && eintraege[i + 1]?.text_de === bedeutung);
}

describe('#3258 Vorbedingung: Katalog-Sollwerte vorhanden', () => {
	test('Titel und feste Einträge stehen DE/EN im Katalog wetter.wsw.legende.*', () => {
		assert.equal(TITEL_DE, 'Kürzel erklärt');
		assert.equal(TITEL_EN, 'Abbreviations explained');
		for (const f of FEST) {
			assert.ok(KAT_DE[`wetter.wsw.legende.${f.key}`], `de: wetter.wsw.legende.${f.key} fehlt`);
			assert.ok(KAT_EN[`wetter.wsw.legende.${f.key}`], `en: wetter.wsw.legende.${f.key} fehlt`);
		}
	});
});

describe('#3258 AC-1/AC-2: Elementliste führt den Block „Kürzel erklärt“ im Abschnitt was-steht-wo', () => {
	for (const ctx of ['trip', 'orte']) {
		test(`${ctx}: Titel „${TITEL_DE}“ mit Katalog-Schlüssel und EN-Soll „${TITEL_EN}“`, () => {
			const { titel } = legende(ctx);
			assert.ok(titel, `„${TITEL_DE}“ fehlt im Abschnitt „${ABSCHNITT}“ (${ctx}, Wetter, normal)`);
			assert.equal(titel.i18n_key, 'wetter.wsw.legende.titel');
			assert.equal(titel.text_en, TITEL_EN);
			assert.notEqual(titel.luecke, true);
		});

		test(`${ctx}: Legende steht hinter der SMS-Beispielzeile`, () => {
			const alle = wsw(ctx);
			const sms = alle.find((e) => e.text_de.startsWith(KAT_DE['wetter.wsw.sms.beispiel']));
			const { titel } = legende(ctx);
			assert.ok(sms, `SMS-Beispielzeile fehlt (${ctx})`);
			assert.ok(titel, `„${TITEL_DE}“ fehlt (${ctx})`);
			assert.ok(titel.ordnung > sms.ordnung, `„${TITEL_DE}“ (${titel.ordnung}) steht vor der SMS-Zeile (${sms.ordnung})`);
		});

		test(`${ctx}: feste Beispielwarnungen mit Kürzel, DE-Text, Katalog-Schlüssel und EN-Soll aus dem Katalog`, () => {
			const { eintraege } = legende(ctx);
			for (const f of FEST) {
				const key = `wetter.wsw.legende.${f.key}`;
				const de = KAT_DE[key];
				const i = paarIndex(eintraege, f.token, de);
				assert.ok(i >= 0, `Paar „${f.token}“ → „${de}“ fehlt in der Legende (${ctx})`);
				const bedeutung = eintraege[i + 1];
				assert.equal(bedeutung.i18n_key, key, `${ctx}: „${de}“ ohne Katalog-Schlüssel`);
				assert.equal(bedeutung.text_en, KAT_EN[key], `${ctx}: „${de}“ EN-Soll weicht vom Katalog ab`);
				assert.notEqual(bedeutung.luecke, true, `${ctx}: „${de}“ hat eine EN-Lücke`);
			}
		});

		test(`${ctx}: Spec-Beispiele „amtliche Warnung …“, „Warnung Wind“, „Warnung Starkregen“ mit EN-Soll`, () => {
			const { eintraege } = legende(ctx);
			const soll: Array<[string, string]> = [
				['amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr', 'official warning: thunderstorm, level high, from 2 pm'],
				['Warnung Wind', 'wind warning'],
				['Warnung Starkregen', 'heavy rain warning'],
			];
			for (const [de, en] of soll) {
				const e = eintraege.find((x) => x.text_de === de);
				assert.ok(e, `„${de}“ fehlt in der Legende (${ctx})`);
				assert.equal(e.text_en, en);
			}
		});

		test(`${ctx}: Metrik-Kürzel mit Bedeutung wie live (Server-Katalog)`, () => {
			const { eintraege } = legende(ctx);
			for (const [token, bedeutung] of METRIK[ctx]) {
				assert.ok(paarIndex(eintraege, token, bedeutung) >= 0, `Paar „${token}“ → „${bedeutung}“ fehlt in der Legende (${ctx})`);
			}
		});
	}

	test('orte: fester Eintrag O1 mit Bedeutung wie live, nach den Beispielwarnungen', () => {
		const { eintraege } = legende('orte');
		const o1 = paarIndex(eintraege, O1.token, O1.de);
		assert.ok(o1 >= 0, `Paar „${O1.token}“ → „${O1.de}“ fehlt in der Legende (orte)`);
		const letzteFest = paarIndex(eintraege, 'X?', KAT_DE['wetter.wsw.legende.warnquelle_nicht_erreichbar']);
		assert.ok(letzteFest >= 0 && o1 > letzteFest, 'O1 steht nicht hinter den festen Beispielwarnungen');
	});

	test('trip: kein O1-Eintrag (nur die Orte-SMS nummeriert Orte)', () => {
		const { titel, eintraege } = legende('trip');
		assert.ok(titel, `„${TITEL_DE}“ fehlt (trip)`);
		assert.equal(paarIndex(eintraege, O1.token, O1.de), -1);
	});
});

describe('#3258 Reihenfolge wie live (legendeAus): erst Metriken, dann feste Einträge, jedes Paar einmal', () => {
	for (const ctx of ['trip', 'orte']) {
		test(`${ctx}: Metrik-Kürzel vor den festen Einträgen, feste Einträge in Katalog-Reihenfolge`, () => {
			const { titel, eintraege } = legende(ctx);
			assert.ok(titel, `„${TITEL_DE}“ fehlt (${ctx})`);
			const metrik = METRIK[ctx].map(([t, b]) => paarIndex(eintraege, t, b));
			const fest = FEST.map((f) => paarIndex(eintraege, f.token, KAT_DE[`wetter.wsw.legende.${f.key}`]));
			assert.ok(metrik.every((i) => i >= 0), `Metrik-Paare fehlen (${ctx}): ${JSON.stringify(metrik)}`);
			assert.ok(fest.every((i) => i >= 0), `feste Paare fehlen (${ctx}): ${JSON.stringify(fest)}`);
			assert.ok(Math.max(...metrik) < Math.min(...fest), `Metrik-Kürzel stehen nicht vor den festen Einträgen (${ctx})`);
			for (let i = 1; i < fest.length; i++) {
				assert.ok(fest[i] > fest[i - 1], `fester Eintrag „${FEST[i].key}“ steht vor „${FEST[i - 1].key}“ (${ctx})`);
			}
		});

		test(`${ctx}: jedes Paar Kürzel→Bedeutung nur einmal`, () => {
			const { titel, eintraege } = legende(ctx);
			assert.ok(titel, `„${TITEL_DE}“ fehlt (${ctx})`);
			const paare = [...METRIK[ctx].map(([t, b]) => [t, b]), ...FEST.map((f) => [f.token, KAT_DE[`wetter.wsw.legende.${f.key}`]])];
			for (const [t, b] of paare) {
				const n = eintraege.filter((e, i) => e.text_de === t && eintraege[i + 1]?.text_de === b).length;
				assert.equal(n, 1, `Paar „${t}“ → „${b}“ ${n}× in der Legende (${ctx})`);
			}
		});
	}
});

// --------------------------------------------------------------- Gegenrichtung des Abgleichs (AC-3, AC-4)

type ZusaetzlichRoh = { ctx: string; reiter: string; text: string };
const BERICHT: Record<L.Sprache, { zusaetzlich: ZusaetzlichRoh[] }> = {
	de: lese('docs/artifacts/fix-3192-wetter-dialog-abgleich/abgleich-de-2.json'),
	en: lese('docs/artifacts/fix-3192-wetter-dialog-abgleich/abgleich-en-2.json'),
};

/** Live-Texte der Legende je Sprache und Kontext (aus dem Staging-Bericht; Bereich ab Titel bis Ende der Legende). */
function liveLegende(sprache: L.Sprache, ctx: string): string[] {
	const titel = sprache === 'de' ? TITEL_DE : TITEL_EN;
	const texte = BERICHT[sprache].zusaetzlich.filter((z) => z.ctx === ctx && z.reiter === 'wetter').map((z) => z.text);
	const start = texte.indexOf(titel);
	assert.ok(start >= 0, `Bericht ${sprache}/${ctx}: „${titel}“ fehlt (Quelle geändert?)`);
	// Ende: letzter fester Eintrag (Warnquelle) bzw. bei Orten die O1-Bedeutung.
	const letzte = ctx === 'orte' ? (sprache === 'de' ? O1.de : 'Location 1 in the order of the subscription') : (sprache === 'de' ? KAT_DE : KAT_EN)['wetter.wsw.legende.warnquelle_nicht_erreichbar'];
	const ende = texte.indexOf(letzte, start);
	assert.ok(ende > start, `Bericht ${sprache}/${ctx}: Ende der Legende „${letzte}“ fehlt`);
	return texte.slice(start, ende + 1);
}

/** SMS-Beispielwerte des Prüf-Datensatzes (Trip), live gemessen. */
const SMS_ZEILE =
	"Port d'And D14/18 W30@10(41@15) G35@7(59@15) PR70%@13 R1.0@15 TF- FN12 FD12/16 TH:L@14(M@15) TH+:- VS- FZ3300@4 UV6@12(7@13) SL2900 CL:SCT@15 N14";
const SMS_WERTE: Record<L.Sprache, string[]> = {
	de: ['FN12', 'FD12/16', SMS_ZEILE],
	en: ['TF- FN12 FD12/16', 'FN12', 'FD12/16', SMS_ZEILE],
};

function regeln() {
	const liste = LISTE.elemente as unknown as L.ListenElement[];
	const text = leseText(BESITZER_PFAD);
	return { liste, ausnahmen: L.leseAusnahmen(text), besitzer: L.leseBesitzer(text, liste) };
}

/** Gegenrichtung wie im Lauf: zusätzliche Texte, dann Besitzer; liefert die herrenlosen Texte. */
function herrenloseTexte(ctx: string, sprache: L.Sprache, texte: string[]): string[] {
	const { liste, ausnahmen, besitzer } = regeln();
	const zus = L.findeZusaetzliche({ ctx, reiter: 'wetter', texte }, liste, ausnahmen, [], sprache);
	const bericht: L.Bericht = {
		eintraege: [],
		zusaetzlich: zus,
		ohne_hub: [],
		zaehler: { gefunden: 0, abweichend: 0, nicht_pruefbar: 0, freigegeben: 0, zusaetzlich: zus.length },
	};
	return L.wendeBesitzerAn(bericht, besitzer)
		.zusaetzlich.filter((z) => !z.besitzer)
		.map((z) => z.text);
}

describe('#3258 AC-4: Texte der Legende sind im Abgleich nicht mehr herrenlos (DE und EN, Trip und Orte)', () => {
	for (const sprache of ['de', 'en'] as const) {
		for (const ctx of ['trip', 'orte']) {
			test(`${sprache}/${ctx}: jeder Live-Text der Legende ist Soll-Eintrag oder hat einen Besitzer`, () => {
				const texte = liveLegende(sprache, ctx);
				assert.ok(texte.length > 10, `Bericht ${sprache}/${ctx}: zu wenige Legenden-Texte (${texte.length})`);
				const rest = herrenloseTexte(ctx, sprache, texte);
				assert.deepEqual(rest, [], `${rest.length} herrenlose Legenden-Texte (${sprache}/${ctx})`);
			});
		}
	}
});

describe('#3258 AC-3: SMS-Beispielwerte als Zahl-Muster, Besitzer #3258', () => {
	for (const sprache of ['de', 'en'] as const) {
		test(`${sprache}/trip: FN12, FD12/16 und die ganze SMS-Zeile sind erklärt; dieselben Texte mit Buchstaben statt Zahlen nicht`, () => {
			const rest = herrenloseTexte('trip', sprache, SMS_WERTE[sprache]);
			assert.deepEqual(rest, [], `herrenlose SMS-Beispielwerte (${sprache}): ${JSON.stringify(rest)}`);
			// Gegenprobe: `{zahl}` erklärt nur Zahl-Text, keinen beliebigen Text.
			const fremd = SMS_WERTE[sprache].map((t) => t.replace(/FN12/, 'FNab').replace(/FD12\/16/, 'FDcd/ef'));
			const fremdRest = herrenloseTexte('trip', sprache, fremd);
			assert.deepEqual(fremdRest.sort(), [...fremd].map(L.normalisiere).sort(), `Muster erklärt Buchstaben statt Zahlen (${sprache})`);
		});
	}

	test('Besitzerliste: mindestens ein Muster-Eintrag mit {zahl}, verweis #3258 und Grund „hängt vom Prüf-Datensatz ab“', () => {
		const eigene = BESITZER_ROH.besitzer.filter((b) => b.art === 'zusaetzlich' && b.verweis === '#3258');
		const muster = eigene.filter((b) => (b.muster ?? '').includes('{zahl}'));
		assert.ok(muster.length > 0, 'kein zusaetzlich-Besitzer mit Muster {zahl} und verweis #3258');
		for (const b of muster) {
			assert.ok((b.grund ?? '').includes('hängt vom Prüf-Datensatz ab'), `Grund ohne Datensatz-Bezug: ${b.grund}`);
			assert.doesNotMatch(b.muster ?? '', /\{(?!zahl\})[^}]*\}/, `Muster mit anderem Platzhalter als {zahl}: ${b.muster}`);
		}
	});
});
