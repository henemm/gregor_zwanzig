// TDD RED — #1895 S3b1 AC-61: die festgelegten Block-Texte (`alarme.kanaele.*`) existieren in DE
// und EN. Parität/Hardcode/Verwender bewachen die bestehenden Ratschen (paritaet_de_en,
// keine_hartkodierten_nutzertexte, hardcode_allowlist_leer, katalog_schluessel_haben_verwender).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { de } from '../messages/de/index.ts';
import { en } from '../messages/en/index.ts';

const KANAELE_SCHLUESSEL = [
	'alarme.kanaele.ueberschrift', // Überschrift „Kanäle je Wettergröße"
	'alarme.kanaele.wie_abo', // Umschalter-Zustand „wie Abo-Kanäle" (erbt)
	'alarme.kanaele.eigene_wahl', // Umschalter-Zustand „eigene Wahl"
	'alarme.kanaele.nicht_im_abo', // AC-51 Hinweis „Kanal im Abo nicht aktiv"
	'alarme.kanaele.metrikfrei_hinweis', // AC-52 Radar-/Regen-Alarme + amtliche Warnungen über Abo-Kanäle
	'alarme.kanaele.wind_hinweis', // AC-48 Windänderung folgt Böen- oder Wind-Zeile
	'alarme.kanaele.nicht_verfuegbar' // AC-49 Endpunkt nicht ladbar
] as const;

test('AC-61: jeder Text des Kanal-Blocks steht in DE und EN im Katalog', () => {
	const fehlend: string[] = [];
	for (const k of KANAELE_SCHLUESSEL) {
		for (const [sprache, katalog] of [['de', de], ['en', en]] as const) {
			const text = (katalog as Record<string, unknown>)[k];
			if (typeof text !== 'string' || text.trim() === '') fehlend.push(`${sprache}:${k}`);
		}
	}
	assert.deepStrictEqual(fehlend, [], `fehlende Katalogtexte: ${fehlend.join(', ')}`);
	const d = de as Record<string, string>, e = en as Record<string, string>;
	assert.notStrictEqual(d['alarme.kanaele.metrikfrei_hinweis'], e['alarme.kanaele.metrikfrei_hinweis'], 'EN nur kopiert');
});
