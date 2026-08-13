// TDD RED — Issue #1719 Scheibe S3, AC-3 + AC-4 (Unit-Anteil): die
// Platzgrenzen werden als EINHEIT modelliert (Spalten vs. Zeichen), nicht
// mehr als eine einzige, kanalübergreifend falsch interpretierte Zahl.
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md
//   Abschnitt 5 ("Platzgrenzen ehrlich modellieren"), Abschnitt 6
//   ("Telegram 7 statt 8"), AC-3, AC-4.
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md
//   Abschnitt 3.1 ("Die echten Grenzen, je Kanal gemessen"),
//   Abschnitt 3.2 Punkt 1 ("Telegram ist um eins zu großzügig").
//
// Befund, den dieser Test rot macht:
//   - `CHANNEL_COL_BUDGET.telegram` (trip-detail/metricsEditor.ts:230) ist
//     heute 8, das Backend liefert aber nur 7 Metrik-Spalten
//     (src/output/renderers/channel_layout.py:110, `metric_slots = limit - 1`).
//   - Fuer SMS gibt es heute nur eine Spaltenzahl (`CHANNEL_COL_BUDGET.sms
//     === 0`, layout-tab/ltChannels.ts:39) — keine Modellierung der
//     tatsaechlichen Einheit (Zeichen, Trip-Pfad 160).
//
// Das hier importierte Modul `../ltChannels.ts` hat die unten verwendeten
// Exporte (`LtLimit`, `TELEGRAM_METRIC_COLUMNS`, `SMS_TRIP_CHAR_LIMIT`,
// `ltLimitForChannel`, `ltBadgeForLimit`, `ltOverflowForLimit`) noch NICHT
// -> der Import wirft einen Modul-Resolve-Fehler und ALLE Tests dieser Datei
// scheitern (RED). Muster: shared/__tests__/channelMetricLayouts.test.ts.
//
// Kontrakt fuer GREEN (reine Funktionen, kein Svelte-State, kein DOM):
//
//   type LtLimit =
//     | { kind: 'none' }
//     | { kind: 'columns'; value: number }
//     | { kind: 'chars'; value: number };
//
//   TELEGRAM_METRIC_COLUMNS: number  // 7 — Beleg: channel_layout.py:110
//   SMS_TRIP_CHAR_LIMIT: number      // 160 — Beleg: trip_report.py:446
//
//   ltLimitForChannel(channel: ChannelId, smsCharLimit: number): LtLimit
//     - email    -> { kind: 'none' }
//     - telegram -> { kind: 'columns', value: TELEGRAM_METRIC_COLUMNS }
//     - sms      -> { kind: 'chars', value: smsCharLimit }  (Wert vom
//       AUFRUFER, NICHT aus einer geteilten Konstante — Spec Abschnitt 5,
//       Praezedenz `hasLabelColumn` bei LTCapNote.svelte:23. Trip-Pfad ruft
//       mit SMS_TRIP_CHAR_LIMIT (160) auf, Vergleichs-Pfad mit 153 — dieser
//       Test prueft nur den Trip-Pfad.)
//
//   ltBadgeForLimit(limit: LtLimit): string
//     - none    -> '∞'
//     - columns -> String(value)
//     - chars   -> String(value)   (AC-4: Chip zeigt die Zeichenzahl, NICHT '—')
//
//   ltOverflowForLimit(limit: LtLimit, count: number): number | undefined
//     - none/chars -> undefined (AC-4: fuer 'chars' wird KEIN Ueberlauf
//       berechnet — Spec Abschnitt 5, "Ueberlauf fuer kind:'chars' wird
//       ausdruecklich NICHT berechnet")
//     - columns -> count - value, wenn count > value, sonst undefined
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/layout-tab/__tests__/channelLimitModel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const {
	TELEGRAM_METRIC_COLUMNS,
	SMS_TRIP_CHAR_LIMIT,
	ltLimitForChannel,
	ltBadgeForLimit,
	ltOverflowForLimit
} = await import('../ltChannels.ts');

describe('AC-3: Telegram liefert 7 Metrik-Spalten, nicht 8', () => {
	test('TELEGRAM_METRIC_COLUMNS === 7 (Beleg: channel_layout.py:110, metric_slots = limit - 1)', () => {
		assert.equal(
			TELEGRAM_METRIC_COLUMNS,
			7,
			'AC-3 FAIL: Telegram-Budget muss 7 Metrik-Spalten sein (die 8. Spalte ist die Uhrzeit) — ' +
				'metricsEditor.ts verspricht dem Nutzer heute eine Spalte mehr, als tatsaechlich ankommt'
		);
	});

	test("ltLimitForChannel('telegram', ...) traegt value 7", () => {
		const limit = ltLimitForChannel('telegram', SMS_TRIP_CHAR_LIMIT);
		assert.deepEqual(limit, { kind: 'columns', value: 7 });
	});

	test('9 aktive Metriken im Telegram-Reiter: Kapplinie nach der 7., Ueberlauf-Chip nennt 2', () => {
		const limit = ltLimitForChannel('telegram', SMS_TRIP_CHAR_LIMIT);
		const overflow = ltOverflowForLimit(limit, 9);
		assert.equal(
			overflow,
			2,
			'AC-3 FAIL: bei 9 aktiven Metriken im Telegram-Reiter muss der Ueberlauf-Chip 2 nennen (9 - 7)'
		);
	});
});

describe('AC-4: SMS traegt eine Zeichengrenze, keine Spaltengrenze', () => {
	test("ltLimitForChannel('sms', 160) === { kind: 'chars', value: 160 } im Trip-Pfad", () => {
		const limit = ltLimitForChannel('sms', SMS_TRIP_CHAR_LIMIT);
		assert.deepEqual(
			limit,
			{ kind: 'chars', value: 160 },
			"AC-4 FAIL: SMS muss im Trip-Kontext { kind: 'chars', value: 160 } liefern, " +
				"nicht { kind: 'columns', value: 0 } (der heutige Sentinel)"
		);
	});

	test('SMS_TRIP_CHAR_LIMIT === 160 (Beleg: trip_report.py:446, max_length=160, Literal)', () => {
		assert.equal(SMS_TRIP_CHAR_LIMIT, 160);
	});

	test('der Zeichenwert kommt vom Aufrufer, nicht aus einer festen Konstante (Vergleichs-Kontext waere 153)', () => {
		const limit = ltLimitForChannel('sms', 153);
		assert.deepEqual(
			limit,
			{ kind: 'chars', value: 153 },
			'AC-4 FAIL: ltLimitForChannel darf den SMS-Zeichenwert nicht fest verdrahten — ' +
				'Trip (160) und Vergleich (153) unterscheiden sich (channel_layout.py:45-54)'
		);
	});

	test("ltBadgeForLimit zeigt fuer 'chars' die Zeichenzahl, NICHT '—'", () => {
		const badge = ltBadgeForLimit({ kind: 'chars', value: 160 });
		assert.equal(
			badge,
			'160',
			"AC-4 FAIL: der SMS-Chip muss die Zeichengrenze (160) zeigen — " +
				"'—' waere die heutige (falsche) Anzeige fuer den Spalten-Sentinel 0"
		);
	});

	test("ltOverflowForLimit liefert fuer 'chars' KEINEN Eintrag (Spec Abschnitt 5: Ueberlauf nicht berechenbar)", () => {
		const overflow = ltOverflowForLimit({ kind: 'chars', value: 160 }, 25);
		assert.equal(
			overflow,
			undefined,
			'AC-4 FAIL: fuer SMS (kind: chars) darf kein Ueberlauf-Wert entstehen — der Editor kennt ' +
				'die fertig gebaute SMS-Zeile nicht, eine Schaetzzahl waere eine zweite falsche Behauptung'
		);
	});
});

describe('E-Mail bleibt unbegrenzt', () => {
	test("ltLimitForChannel('email', ...) === { kind: 'none' }", () => {
		assert.deepEqual(ltLimitForChannel('email', SMS_TRIP_CHAR_LIMIT), { kind: 'none' });
	});

	test("ltBadgeForLimit({kind:'none'}) === '∞'", () => {
		assert.equal(ltBadgeForLimit({ kind: 'none' }), '∞');
	});

	test("ltOverflowForLimit({kind:'none'}, ...) === undefined", () => {
		assert.equal(ltOverflowForLimit({ kind: 'none' }, 999), undefined);
	});
});

// ── TDD RED — Issue #1703 Scheibe 8, AC-S8-12 ──────────────────────────────
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md Abschnitt 7
//   ("Fix B — SMS-Zeichengrenze am Kanal-Tab-Badge"), AC-S8-12, Gegenprobe M7.
//
// Gemessener Widerspruch: `LTChannelPicker.svelte:29,39` iteriert die
// Modul-Konstante `LT_CHANNELS` (ltChannels.ts:71-75), fest gebaut mit
// SMS_TRIP_CHAR_LIMIT (160). Im Ortsvergleich zeigt der SMS-Badge damit "160",
// waehrend der Hinweistext darunter (ltCapNoteText ueber smsCharLimit) korrekt
// "153" nennt — zwei sich widersprechende Kappungs-Aussagen auf einer Seite.
//
// `ltChannelsFor(smsCharLimit)` existiert noch NICHT -> die Zusicherung in
// `channelsFor()` schlaegt fehl (RED).
const { ltChannelsFor, LT_CHANNELS, SMS_COMPARE_CHAR_LIMIT } = await import('../ltChannels.ts');

const channelsFor = (smsCharLimit: number) => {
	assert.equal(
		typeof ltChannelsFor,
		'function',
		'RED: ltChannelsFor(smsCharLimit) fehlt in layout-tab/ltChannels.ts — ohne sie kann ' +
			'LTChannelPicker nur die fest verdrahtete Trip-Liste (160) anzeigen'
	);
	return ltChannelsFor(smsCharLimit);
};
const limitOf = (list: { id: string; limit: unknown }[], id: string) =>
	list.find((c) => c.id === id)?.limit;

describe('AC-S8-12: der SMS-Kanal-Tab des Ortsvergleichs nennt 153, der Trip-Pfad weiter 160', () => {
	test('ltChannelsFor(153) traegt fuer SMS chars:153 — LT_CHANNELS (Trip) unveraendert chars:160', () => {
		assert.equal(SMS_COMPARE_CHAR_LIMIT, 153, 'Beleg: channel_layout.py:45-54, floor((140-6)*8/7)');
		assert.deepEqual(
			limitOf(channelsFor(SMS_COMPARE_CHAR_LIMIT), 'sms'),
			{ kind: 'chars', value: 153 },
			'AC-S8-12 FAIL: der Kanal-Tab-Badge im Ortsvergleich muss 153 Zeichen nennen — ' +
				'M7 (weiterhin LT_CHANNELS direkt importieren) widerspraeche dem Hinweistext darunter'
		);
		assert.deepEqual(
			limitOf(LT_CHANNELS, 'sms'),
			{ kind: 'chars', value: 160 },
			'AC-S8-12 FAIL: die Trip-Kanalliste darf sich dabei NICHT auf 153 mitverschieben ' +
				'(trip_report.py:446, max_length=160)'
		);
	});

	test('Telegram bleibt in beiden Listen columns:7 — nur die SMS-Einheit haengt am Aufrufer', () => {
		assert.deepEqual(limitOf(channelsFor(SMS_COMPARE_CHAR_LIMIT), 'telegram'), {
			kind: 'columns',
			value: 7
		});
		assert.deepEqual(limitOf(LT_CHANNELS, 'telegram'), { kind: 'columns', value: 7 });
	});
});
