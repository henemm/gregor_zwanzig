// TDD RED — Issue #3436 (Workflow fix-3436-tempo-abschnitt): Tempo-Karte im Reiter Etappen im Elementlisten-Abgleich.
// Spec: docs/specs/modules/fix_3436_tempo_abschnitt.md — AC-3, AC-4, AC-5.
//
// Kern-Test gegen die ECHTEN Dateien aus docs/context/einstellungen_neu/ (elementliste.json,
// elementliste_freigaben.json, elementliste_besitzer.json) mit der ECHTEN Abgleich-Logik
// (e2e/elementliste_abgleich_logik.ts), in derselben Aufruffolge wie der Staging-Lauf
// (elementliste-abgleich.staging.spec.ts): ladeRegeln → bewerteAbschnitt (Hinrichtung je Abschnitt und Zustand)
// → wendeFreigabenAn; Gegenrichtung findeZusaetzliche mit regeln.ausnahmen. Kein Mock: der Befund ist der
// Live-Text der Tempo-Karte (Katalog trip.tempo.*, Eingabefeld liest den Wert „4“ wie eingabeText), mit Haken.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_tempo_3436_kern.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as logik from '../../../e2e/elementliste_abgleich_logik.ts';
import type { ListenElement } from '../../../e2e/elementliste_abgleich_logik.ts';

// Namespace-Import: fehlende Exporte machen jeden Test einzeln rot statt das ganze Modul zu sprengen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const L = logik as any;

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const KONTEXT = join(FRONTEND, '..', 'docs/context/einstellungen_neu');
const SPEC = 'docs/specs/modules/fix_3436_tempo_abschnitt.md';

const BESITZER_DATEI = join(KONTEXT, 'elementliste_besitzer.json');
const FREIGABEN_DATEI = join(KONTEXT, 'elementliste_freigaben.json');
const ALLE: ListenElement[] = (JSON.parse(readFileSync(join(KONTEXT, 'elementliste.json'), 'utf8')) as { elemente: ListenElement[] }).elemente;
const katalog = (s: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(join(FRONTEND, 'src/lib/i18n/messages', s, 'trip.json'), 'utf8'));

type Sprache = 'de' | 'en';
const SPRACHEN: Sprache[] = ['de', 'en'];
const ZUSTAENDE = ['normal', 'laedt', 'fehler', 'luecken'];

/** Live-Texte der Tempo-Karte in DOM-Reihenfolge (TempoKarteInhalt): Fortbewegung, vier Chips, Grundtempo, Eingabewert, Hinweis. */
function liveTexte(s: Sprache): string[] {
	const k = katalog(s);
	const keys = ['trip.tempo.fortbewegung', 'trip.tempo.fuss', 'trip.tempo.rad', 'trip.tempo.mtb', 'trip.tempo.ski', 'trip.tempo.grundtempo'];
	return [...keys.map((x) => k[x]), '4', k['trip.tempo.hinweis']];
}

const GRUNDTEMPO = { de: 'Grundtempo (km/h)', en: 'Base pace (km/h)' } as const;
const HINWEIS = { de: 'Gilt für alle Etappen, je Etappe überschreibbar.', en: 'Applies to all stages, can be overridden per stage.' } as const;

/** Die fünf Mockup-Elemente, die ADR-0108 Nr. 2 (Anpassung 2026-11-20, #3196/#3197) überholt hat. */
const UEBERHOLT = [
	(e: ListenElement) => e.text_de === 'Tempo flach' && e.i18n_key === null,
	(e: ListenElement) => e.muster === '{zahl} km/h',
	(e: ListenElement) => e.i18n_key === 'trip.etappe.aufstieg',
	(e: ListenElement) => e.muster === '{zahl} Hm/h',
	(e: ListenElement) => e.text_de === 'Gilt für alle Etappen, je Etappe überschreibbar (z.B. Ruhetag, Bergetappe).'
];
const istUeberholt = (e: ListenElement) => UEBERHOLT.some((p) => p(e));

const tempoElemente = (zustand: string) =>
	ALLE.filter((e) => e.ctx === 'trip' && e.reiter === 'etappen' && e.abschnitt === 'tempo' && e.zustand === zustand);

describe('#3436 Messaufbau: echte Dateien und Live-Texte', () => {
	test('elementliste.json führt je Zustand die zehn Tempo-Elemente, davon die fünf überholten', () => {
		for (const z of ZUSTAENDE) {
			const el = tempoElemente(z);
			assert.equal(el.length, 10, `Zustand ${z}: ${el.length} Tempo-Elemente`);
			for (const [i, p] of UEBERHOLT.entries()) assert.equal(el.filter(p).length, 1, `Zustand ${z}: überholtes Element ${i + 1} nicht genau einmal`);
		}
	});
	test('Live-Texte stammen aus dem Katalog (DE/EN)', () => {
		for (const s of SPRACHEN) {
			assert.equal(katalog(s)['trip.tempo.grundtempo'], GRUNDTEMPO[s]);
			assert.equal(katalog(s)['trip.tempo.hinweis'], HINWEIS[s]);
		}
	});
});

describe('#3436 AC-3: Freigabe deckt die fünf überholten Mockup-Elemente (DE und EN, alle Zustände)', () => {
	for (const s of SPRACHEN) {
		for (const z of ZUSTAENDE) {
			test(`${s}/${z}: Messung mit Haken → wendeFreigabenAn ⇒ fünf „freigegeben“, keines „nicht_pruefbar“`, () => {
				const regeln = L.ladeRegeln({ freigaben: FREIGABEN_DATEI, besitzer: BESITZER_DATEI }, ALLE);
				const liste = tempoElemente(z);
				const gemessen: Map<string, { status: string; grund?: string }> = L.bewerteAbschnitt(liste, { marker: true, texte: liveTexte(s) }, s, 'tempo');
				// Messaufbau: die gebauten Texte sind gefunden, die überholten nicht (abweichend bzw. EN-Lücke).
				for (const e of liste.filter((x) => !istUeberholt(x))) {
					assert.equal(gemessen.get(e.id)?.status, 'gefunden', `Messaufbau ${s}/${z}: „${e.text_de}“ nicht gefunden (${gemessen.get(e.id)?.grund ?? ''})`);
				}
				for (const e of liste.filter(istUeberholt)) {
					assert.ok(['abweichend', 'nicht_pruefbar'].includes(String(gemessen.get(e.id)?.status)), `Messaufbau ${s}/${z}: „${e.text_de}“ ist ${gemessen.get(e.id)?.status}`);
				}
				const nachher: Map<string, { status: string; grund?: string }> = L.wendeFreigabenAn(liste, gemessen, regeln.freigaben);
				const falsch = liste
					.filter(istUeberholt)
					.map((e) => ({ text: e.text_de, erg: nachher.get(e.id) }))
					.filter((x) => x.erg?.status !== 'freigegeben');
				assert.deepEqual(
					falsch.map((x) => `${x.text}: ${x.erg?.status} (${x.erg?.grund ?? ''})`),
					[],
					`${s}/${z}: nicht freigegeben`
				);
				for (const e of liste.filter(istUeberholt)) {
					assert.ok(String(nachher.get(e.id)?.grund).includes(SPEC), `${s}/${z}: Freigabe von „${e.text_de}“ verweist nicht auf ${SPEC}`);
				}
			});
		}
	}

	test('Freigabe ist eng: die gebauten Texte (Fortbewegung, Chips) bleiben ohne Haken „abweichend“', () => {
		const regeln = L.ladeRegeln({ freigaben: FREIGABEN_DATEI, besitzer: BESITZER_DATEI }, ALLE);
		for (const s of SPRACHEN) {
			const liste = tempoElemente('normal');
			const ohneHaken = L.bewerteAbschnitt(liste, { marker: false, texte: liveTexte(s) }, s, 'tempo');
			const nachher: Map<string, { status: string }> = L.wendeFreigabenAn(liste, ohneHaken, regeln.freigaben);
			for (const e of liste.filter((x) => !istUeberholt(x))) {
				assert.equal(nachher.get(e.id)?.status, 'abweichend', `${s}: „${e.text_de}“ ist ${nachher.get(e.id)?.status} (Freigabe zu weit)`);
			}
		}
	});
});

describe('#3436 AC-4: Grundtempo und Hinweis sind keine herrenlosen Zusatztexte', () => {
	for (const s of SPRACHEN) {
		test(`${s}: findeZusaetzliche im Reiter etappen meldet weder „${GRUNDTEMPO[s]}“ noch „${HINWEIS[s]}“`, () => {
			const regeln = L.ladeRegeln({ freigaben: FREIGABEN_DATEI, besitzer: BESITZER_DATEI }, ALLE);
			const zus: Array<{ text: string }> = L.findeZusaetzliche({ ctx: 'trip', reiter: 'etappen', texte: liveTexte(s) }, ALLE, regeln.ausnahmen, [], s);
			const gemeldet = zus.map((z) => z.text).filter((t) => t === GRUNDTEMPO[s] || t === HINWEIS[s]);
			assert.deepEqual(gemeldet, [], `${s}: als zusätzlich gemeldet: ${gemeldet.join(' | ')}`);
		});
	}

	test('Ausnahme gilt nur im Reiter etappen des Trips (anderer Reiter meldet die Texte weiter)', () => {
		const regeln = L.ladeRegeln({ freigaben: FREIGABEN_DATEI, besitzer: BESITZER_DATEI }, ALLE);
		for (const s of SPRACHEN) {
			const zus: Array<{ text: string }> = L.findeZusaetzliche({ ctx: 'trip', reiter: 'uebersicht', texte: [GRUNDTEMPO[s], HINWEIS[s]] }, ALLE, regeln.ausnahmen, [], s);
			assert.deepEqual(zus.map((z) => z.text).sort(), [GRUNDTEMPO[s], HINWEIS[s]].sort(), `${s}: Ausnahme wirkt außerhalb des Reiters etappen`);
		}
	});
});

describe('#3436 AC-5: Besitzer des Abschnitts tempo ist #3436', () => {
	test('Eintrag art abschnitt trip/etappen/tempo verweist auf #3436, keiner mehr auf #2796', () => {
		const text = readFileSync(BESITZER_DATEI, 'utf8');
		const besitzer: Array<Record<string, string>> = L.leseBesitzer(text, ALLE);
		const tempoIds = new Set(ALLE.filter((e) => e.ctx === 'trip' && e.reiter === 'etappen' && e.abschnitt === 'tempo').map((e) => e.id));
		const abschnitt = besitzer.filter((b) => b.art === 'abschnitt' && b.ctx === 'trip' && b.reiter === 'etappen' && b.abschnitt === 'tempo');
		const elemente = besitzer.filter((b) => b.art === 'element' && tempoIds.has(b.id));
		assert.equal(abschnitt.length, 1, `Abschnitt tempo ${abschnitt.length}× in der Besitzerliste (erwartet 1)`);
		assert.equal(abschnitt[0].verweis, '#3436', `Abschnitt tempo verweist auf ${abschnitt[0].verweis}`);
		const alt = [...abschnitt, ...elemente].filter((b) => b.verweis === '#2796');
		assert.deepEqual(alt, [], 'Einträge für den Abschnitt tempo zeigen noch auf das geschlossene #2796');
	});
});
