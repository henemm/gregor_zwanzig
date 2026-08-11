// TDD RED — Issue #1719 Scheibe S3, AC-5: die Kanal-Hinweistexte hoeren auf,
// dem Nutzer zu sagen, was wichtig ist, behaupten aber weiterhin die
// gemessenen, echten Platzgrenzen.
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-5.
//
// 🔴 Spec-Korrektur 1 (Commit 3da43cad, 2026-08-11): die Erstfassung dieser
// Datei verbot "kein Raster" und "nur Fließtext" — beides ist WAHR
// (src/output/renderers/channel_layout.py:48, max_table_cols = 0 fuer SMS).
// Ein Verbot haette eine korrekte, neutrale Formulierung unmoeglich gemacht.
// Die PO-Regel trennt jetzt nach WERTUNG und UNWAHRHEIT, nicht nach
// Wortklang — mit einer ausdruecklichen Erlaubt-Liste, damit die
// Verbotsliste nicht wieder zu breit wird.
//
// 🔴 Spec-Korrektur 2 (Commit 6403c57a, 2026-08-11): "140" ist NICHT pauschal
// unwahr — es gibt DREI SMS-Zeichengrenzen, nicht zwei, je nach Ausgabeweg:
//   Trip-Briefing:       160  (trip_report.py:446, ltCapNoteText hier getestet)
//   Vergleichs-Briefing: 153  (channel_layout.py:48, VTBriefingChannels/CompareSmsPreview)
//   Alarm:               140  (alert/render.py:621, AlertChannelPicker — NICHT
//                               Teil dieser Datei, `ltCapNoteText` rendert nur
//                               Briefing-Kanal-Reiter, nie den Alarm-Pfad)
// Diese Datei prueft ausschliesslich `ltCapNoteText` (Briefing-Kanal-Reiter,
// Trip UND Vergleich) — "140" bleibt dort in JEDEM Fall falsch, weil
// `ltCapNoteText` den Alarm-Pfad nie rendert. Trotzdem steht "140" NICHT
// mehr in der generischen BANNED_UNWAHR-Liste (das wuerde eine Zahl pauschal
// verbieten, die anderswo im Produkt korrekt ist) — stattdessen prueft der
// SMS-Testfall unten die Abwesenheit von "140" explizit UND mit Begruendung,
// warum das hier (nicht ueberall) gilt.
//
// Geprueft wird der ERZEUGTE TEXT einer ableitenden Funktion (kein
// read_text()-Dateiinhalt-Check — im Projekt verboten). Heute steckt diese
// Logik als `$derived.by`-Block direkt in LTCapNote.svelte (`text`,
// LTCapNote.svelte:29-36) und ist damit ohne Svelte-Renderharness nicht als
// reine Funktion aufrufbar.
//
// Kontrakt fuer GREEN: `ltCapNoteText` wird aus LTCapNote.svelte in
// `../ltChannels.ts` extrahiert (reine Funktion, analog `ltBadgeForLimit`
// aus channelLimitModel.test.ts) — existiert dort heute NICHT -> Import
// wirft Modul-Resolve-Fehler, die Tests, die `ltCapNoteText` aufrufen,
// scheitern (RED). Der Canary-Test unten prueft NUR die Erlaubt-Liste
// gegen die Verbots-Pruefung selbst (kein Aufruf von `ltCapNoteText`) und
// ist bewusst schon jetzt gruen — er bewacht die Testdatei selbst, nicht
// das noch fehlende Produktivverhalten (s. Kommentar dort).
//
//   ltCapNoteText(params: {
//     channel: ChannelId;
//     limit: LtLimit;
//     colCount: number;
//     subject: string;
//     hasLabelColumn: boolean;
//   }): string
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/layout-tab/__tests__/channelHintTextNoJudgement.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const { ltCapNoteText } = await import('../ltChannels.ts');

// Verbotsliste laut Spec AC-5 (Commit 3da43cad) — ZWEI getrennte Gruende,
// case-insensitiv geprueft.
const BANNED_WERTUNG = [
	'entscheidungskritisch',
	'nur das wesentliche',
	'nur die wichtigsten',
	'läuft flach',
	'wird flach'
];

// "140" steht ABSICHTLICH NICHT hier (Spec-Korrektur 2, Commit 6403c57a):
// im Alarm-Pfad (AlertChannelPicker, alert/render.py:621) ist 140 der
// gemessene, korrekte Wert. Eine Zahl ist nur dort verboten, wo sie dem
// Code des JEWEILIGEN Ausgabewegs widerspricht — ein pauschales Verbot
// wuerde die Alarm-Oberflaeche in eine Unwahrheit zwingen. Fuer die
// Briefing-Texte, die diese Datei prueft, bleibt "140" trotzdem falsch;
// das prueft der SMS-Testfall unten scoped, nicht die generische Liste.
const BANNED_UNWAHR = ['kennt keine spalten-reihenfolge', 'keine reihenfolge', 'max 8 spalten'];

const BANNED_PHRASES = [...BANNED_WERTUNG, ...BANNED_UNWAHR];

// Ausdruecklich ERLAUBT (Spec AC-5) — gemessene Tatsachen, keine
// Bevormundung. Ein Test, der eine dieser Phrasen verbietet, ist selbst der
// Fehler (genau der Fund, der zur Spec-Korrektur fuehrte).
const ALLOWED_PHRASES = ['kein raster', 'keine tabelle', 'fließtext', '160 zeichen', 'max 7 spalten'];

function assertNoForbidden(text: string, label: string) {
	const lower = text.toLowerCase();
	for (const phrase of BANNED_PHRASES) {
		assert.equal(
			lower.includes(phrase.toLowerCase()),
			false,
			`AC-5 FAIL: Hinweistext (${label}) enthaelt die verbotene Wertung/Unwahrheit "${phrase}": "${text}"`
		);
	}
}

describe('AC-5: Kanal-Hinweistexte enthalten keine Wertung und keine Unwahrheit', () => {
	test('E-Mail (unbegrenzt) — kein verbotener Text', () => {
		const text = ltCapNoteText({
			channel: 'email',
			limit: { kind: 'none' },
			colCount: 5,
			subject: 'Metriken',
			hasLabelColumn: false
		});
		assertNoForbidden(text, 'email');
	});

	test('Telegram unter dem Budget — kein verbotener Text', () => {
		const text = ltCapNoteText({
			channel: 'telegram',
			limit: { kind: 'columns', value: 7 },
			colCount: 5,
			subject: 'Metriken',
			hasLabelColumn: false
		});
		assertNoForbidden(text, 'telegram unter Budget');
	});

	test('Telegram ueber dem Budget (9 von 7) — kein verbotener Text, insbesondere kein "max 8 Spalten"', () => {
		const text = ltCapNoteText({
			channel: 'telegram',
			limit: { kind: 'columns', value: 7 },
			colCount: 9,
			subject: 'Metriken',
			hasLabelColumn: false
		});
		assertNoForbidden(text, 'telegram ueber Budget');
	});

	test('SMS (Trip-Briefing, 160) — kein verbotener Text; "kein Raster"/"Fließtext"/"160 Zeichen" sind erlaubt und duerfen im Text stehen', () => {
		const text = ltCapNoteText({
			channel: 'sms',
			limit: { kind: 'chars', value: 160 },
			colCount: 6,
			subject: 'Metriken',
			hasLabelColumn: false
		});
		assertNoForbidden(text, 'sms trip-briefing');
		// Bewusst KEINE Assertion, dass "kein Raster"/"Fließtext"/"160 Zeichen"
		// FEHLEN duerfen (Regression der Erstfassung) — nur die Verbotspruefung
		// oben gilt.
		//
		// "140" scoped statt generisch geprueft (Spec-Korrektur 2, 6403c57a):
		// `ltCapNoteText` rendert NUR Briefing-Kanal-Reiter (Trip/Vergleich),
		// nie den Alarm-Pfad — hier ist der Trip-Wert 160 der einzig richtige,
		// "140" waere die falsche (Alarm-)Zahl an der falschen Stelle.
		assert.equal(
			text.toLowerCase().includes('140'),
			false,
			`AC-5 FAIL: der Trip-Briefing-Hinweistext (SMS, 160) darf nicht "140" nennen ` +
				`(140 ist die Alarm-Zeichengrenze, alert/render.py:621 — falsch am Briefing-Pfad): "${text}"`
		);
	});
});

describe('AC-5 Erlaubt-Liste: eine positive Zusicherung, dass die Verbotspruefung sie nicht faelschlich trifft', () => {
	// Canary: ein Text, der ALLE erlaubten Begriffe gleichzeitig traegt, muss
	// die Verbotspruefung unveraendert bestehen. Faellt dieser Test irgendwann
	// rot, ist BANNED_PHRASES wieder zu breit geworden — genau der Fehler, der
	// zur Spec-Korrektur (Commit 3da43cad) gefuehrt hat. Bewusst unabhaengig
	// von `ltCapNoteText`, damit dieser Canary auch VOR GREEN schon aussagekraeftig ist.
	test('ein Text mit allen Erlaubt-Begriffen bleibt gruen', () => {
		const canary =
			'SMS: kein Raster, keine Tabelle — nur Fließtext bei 160 Zeichen. Telegram: max 7 Spalten.';
		for (const allowed of ALLOWED_PHRASES) {
			assert.equal(
				canary.toLowerCase().includes(allowed.toLowerCase()),
				true,
				`Test-Aufbaufehler: Canary-Text enthaelt den Erlaubt-Begriff "${allowed}" nicht`
			);
		}
		assertNoForbidden(canary, 'canary (alle Erlaubt-Begriffe)');
	});
});
