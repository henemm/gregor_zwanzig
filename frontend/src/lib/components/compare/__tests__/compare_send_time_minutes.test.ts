// TDD RED — Issue #1268 (AC-9/AC-10 Folgefehler, Adversary-Fund F007):
// Anzeige-Formate muessen echte Minuten zeigen, nicht hart ":00".
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-9/AC-10
//
// ── Warum dieser Test existiert ──────────────────────────────────────────────
// `formatNextSend()` schrieb die Minuten hart als ":00". Das war korrekt,
// solange die Zeit aus `hour_from` stammte — ein Integer, also immer volle
// Stunde. Seit AC-9/AC-10 kommt sie aus `morning_time`/`evening_time`, und die
// koennen "07:30" sein: VTSchedulePlan.svelte:86/:111 sind <input type="time">
// OHNE `step`-Begrenzung, der Nutzer kann Minuten setzen.
//
// Folge (der Widerspruch, den wir selbst gebaut haben): die Zeitplan-Kachel
// zeigt "07:30", die "Nächster Versand"-Kachel direkt daneben zeigt "07:00".
//
// Zweiter, VORBESTEHENDER Fehler derselben Zeile (nicht von #1268 verursacht):
// `formatNextSend` wird in `_home/cockpitHelpers.ts:223` auch fuer
// `letzter_versand` benutzt — einen ECHTEN Versand-Zeitstempel, der praktisch
// nie auf einer vollen Stunde liegt. Die "Zuletzt"-Zeile behauptete also schon
// immer ":00". Wird durch denselben Fix mitbehoben.
//
// Luecke, die das durchrutschen liess: saemtliche AC-9/AC-10-Fixtures nutzten
// nur volle Stunden. Dieser Test nimmt deshalb bewusst 07:30-Fixtures.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { formatNextSend, presetTileScheduleLabel } from '../subscriptionHelpers.ts';
import { deriveNextSend, primarySendSlot } from '../../../utils/cockpitHelpers568.ts';
import type { ComparePreset } from '../../../types.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-1268-min',
		name: 'Skigebiet Vergleich',
		location_ids: ['loc-1'],
		schedule: 'daily',
		empfaenger: ['test@henemm.com'],
		profil: 'winter_skiing' as never,
		created_at: '2026-01-01T00:00:00Z',
		...overrides
	} as ComparePreset;
}

describe('#1268 F007: formatNextSend zeigt echte Minuten', () => {
	test('Versand 07:30 → "5.6. 07:30", nicht "5.6. 07:00"', () => {
		// GIVEN: ein Vergleich mit Versandzeit 07:30 (per <input type="time"> setzbar)
		// WHEN: die "Nächster Versand"-Anzeige gerendert wird
		// THEN: sie zeigt 07:30 — dieselbe Zeit wie die Zeitplan-Kachel daneben
		// RED vor Fix: "07:00" — Widerspruch zur Zeitplan-Kachel.
		const now = new Date('2026-06-05T04:00:00');
		const preset = makePreset({ morning_time: '07:30:00' });

		const label = formatNextSend(deriveNextSend(preset, now));

		assert.equal(label, '5.6. 07:30', 'Minuten muessen aus dem Slot stammen, nicht hart ":00" sein');
	});

	test('volle Stunde bleibt zweistellig formatiert: 07:00', () => {
		// Regressionsanker: der haeufige Fall darf sich nicht veraendern.
		const now = new Date('2026-06-05T04:00:00');
		const preset = makePreset({ morning_time: '07:00:00' });
		assert.equal(formatNextSend(deriveNextSend(preset, now)), '5.6. 07:00');
	});

	test('Abend-Slot 18:45 → 18:45', () => {
		const now = new Date('2026-06-05T04:00:00');
		const preset = makePreset({
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:45:00'
		});
		assert.equal(formatNextSend(deriveNextSend(preset, now)), '5.6. 18:45');
	});

	test('null → "manuell" (unveraendert)', () => {
		assert.equal(formatNextSend(null), 'manuell');
	});

	test('VORBESTEHEND (nicht #1268): letzter_versand mit echten Minuten wird nicht mehr auf :00 gerundet', () => {
		// formatNextSend wird in _home/cockpitHelpers.ts:223 auch fuer die
		// "Zuletzt"-Zeile benutzt — mit einem echten Versand-Zeitstempel.
		// Der ":00"-Hardcode hat diesen Wert schon vor #1268 falsch dargestellt.
		const echterVersand = new Date('2026-06-04T06:03:00');
		assert.equal(
			formatNextSend(echterVersand),
			'4.6. 06:03',
			'ein echter Versand-Zeitstempel darf nicht auf die volle Stunde gerundet angezeigt werden'
		);
	});
});

describe('#1268 F007: primarySendSlot traegt die Minuten (Quelle der Anzeige)', () => {
	test('morning_time 07:30 → { hour: 7, minute: 30 }', () => {
		assert.deepEqual(primarySendSlot(makePreset({ morning_time: '07:30:00' })), {
			hour: 7,
			minute: 30
		});
	});

	test('deriveNextSend setzt die Minuten im Zeitstempel', () => {
		const now = new Date('2026-06-05T04:00:00');
		const next = deriveNextSend(makePreset({ morning_time: '07:30:00' }), now)!;
		assert.equal(next.getHours(), 7);
		assert.equal(next.getMinutes(), 30, 'deriveNextSend darf die Minuten nicht verwerfen');
	});

	test('Slot-Vergleich beachtet Minuten: 07:30 vs 07:15 → 07:15 gewinnt', () => {
		// Waechter fuer primarySendSlot/earliest: rein stundenbasiertes Vergleichen
		// wuerde hier den falschen Slot waehlen.
		const preset = makePreset({
			morning_enabled: true,
			morning_time: '07:30:00',
			evening_enabled: true,
			evening_time: '07:15:00'
		});
		assert.deepEqual(primarySendSlot(preset), { hour: 7, minute: 15 });
	});
});

// ── Bekannte, bewusst NICHT geaenderte Format-Abweichung (an den PO gemeldet) ──
// presetTileScheduleLabel ist per Design stundengranular ("tägl. HH", #582 AC-5).
// Bei einem 07:30-Slot zeigt die Kachel "tägl. 07". Das ist eine Vergroeberung,
// aber keine Falschaussage im selben Sinn wie das alte formatNextSend ":00" —
// jenes behauptete Minuten-Genauigkeit und log dabei. Eine Aenderung des
// Kachel-Formats waere eine sichtbare UI-Aenderung ausserhalb der Spec
// (AC-10 fordert woertlich "Label nennt 07"), daher hier nur festgeschrieben,
// damit sie sichtbar bleibt und nicht unbemerkt driftet.
describe('#1268: Kachel-Label bleibt stundengranular (dokumentiert, nicht geaendert)', () => {
	test('Slot 07:30 → "tägl. 07" (bewusste Vergroeberung, s. Kommentar)', () => {
		assert.equal(presetTileScheduleLabel(makePreset({ morning_time: '07:30:00' })), 'tägl. 07');
	});
});
