// TDD RED — Issue #1268 (AC-9/AC-10 Folgefehler, Adversary-Fund F007):
// Anzeige-Formate muessen echte Minuten zeigen, nicht hart ":00".
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-9/AC-10
//
// ── Warum dieser Test existiert ──────────────────────────────────────────────
// `formatNextSend()` schrieb die Minuten hart als ":00". Das war korrekt,
// solange die Zeit aus `hour_from` stammte — ein Integer, also immer volle
// Stunde. Seit AC-9/AC-10 kommt sie aus `morning_time`/`evening_time`, und die
// koennen "07:30" sein: VTSchedulePlan.svelte:86/:111 waren <input type="time">
// OHNE `step`-Begrenzung, der Nutzer konnte Minuten setzen.
// NACHTRAG Issue #1379: ueber die Oberflaeche sind nur noch volle Stunden
// waehlbar (Auswahlliste). Die Anzeige-Helfer muessen Minuten trotzdem korrekt
// darstellen — fuer Bestandswerte und fuer `letzter_versand` (echter
// Versand-Zeitstempel, s. letzter Testfall). Dieser Test bleibt gueltig.
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

// ── Umstellung Issue #1969 (AC-24, docs/specs/modules/feat_1969_naechstes_briefing.md) ──
// Der Versand nutzt nur die STUNDE der Slot-Zeit (Scheduler `_slot_stunde`):
// ein 07:30-Slot geht um 07:00 raus. Die frühere Anzeige „07:30" war damit die
// Minuten-Fiktion, die #1969 entfernt. „Nächster Versand" zeigt jetzt den
// Backend-Wert (`local_time`, immer HH:00) über formatNextBriefing; dieser Test
// pinnt: Minuten werden ignoriert, Anzeige HH:00. `letzter_versand` (echter
// Zeitstempel) behält seine Minuten unverändert.

import { formatNextSend, presetTileScheduleLabel } from '../subscriptionHelpers.ts';
import { primarySendSlot } from '../../../utils/cockpitHelpers568.ts';
import { formatNextBriefing } from '../../shared/versand-tab/nextBriefingText.ts';
import { homeCompareTimeline } from '../../../../routes/_home/cockpitHelpers.ts';
import type { ComparePreset } from '../../../types.ts';

/** Backend-Wert, wie /api/next-briefings ihn für einen Slot liefert (immer HH:00). */
function backendWert(local_time: string, slot: 'morning' | 'evening' = 'morning') {
	return {
		at: `2026-06-05T${local_time}:00+02:00`,
		local_date: '2026-06-05',
		local_time,
		tz: 'Europe/Paris',
		tz_abbr: 'CEST',
		slot
	};
}

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

describe('#1268 F007 / #1969 AC-24: „Nächster Versand" zeigt HH:00 — Minuten werden ignoriert', () => {
	test('Slot 07:30 → Backend 07:00 → Anzeige "Fr 07:00 (CEST)", nie 07:30', () => {
		// GIVEN: ein Vergleich mit Slot-Zeit 07:30 (Bestandswert); der Versand
		//        nutzt nur die Stunde → Backend meldet local_time "07:00"
		// WHEN: die "Nächster Versand"-Anzeige gerendert wird
		// THEN: 07:00 — die tatsächliche Versandstunde, keine Minuten-Fiktion
		const preset = makePreset({ morning_time: '07:30:00' });
		assert.deepEqual(primarySendSlot(preset), { hour: 7, minute: 30 }, 'Messaufbau: Slot traegt Minuten');
		const label = formatNextBriefing(backendWert('07:00'), 'vergleich');
		assert.equal(label, 'Fr 07:00 (CEST)');
		assert.ok(!label.includes('07:30'), `Minuten-Fiktion sichtbar: ${label}`);
		// Durch einen echten Konsumenten MIT dem 07:30-Preset: rechnete dort wieder
		// das Frontend aus dem Preset, erschiene 07:30.
		const zeile = homeCompareTimeline(preset, backendWert('07:00')).find((r) => r.when.startsWith('Nächster · '));
		assert.equal(zeile?.when, 'Nächster · Fr 07:00 (CEST)');
	});

	test('volle Stunde bleibt zweistellig formatiert: 07:00', () => {
		// Regressionsanker: der haeufige Fall darf sich nicht veraendern.
		assert.equal(formatNextBriefing(backendWert('07:00'), 'vergleich'), 'Fr 07:00 (CEST)');
	});

	test('Abend-Slot 18:45 → Backend 18:00 → Anzeige 18:00, nie 18:45', () => {
		const preset = makePreset({
			morning_enabled: false,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:45:00'
		});
		const label = formatNextBriefing(backendWert('18:00', 'evening'), 'vergleich');
		assert.equal(label, 'Fr 18:00 (CEST)');
		assert.ok(!label.includes('18:45'));
		const zeile = homeCompareTimeline(preset, backendWert('18:00', 'evening')).find((r) =>
			r.when.startsWith('Nächster · ')
		);
		assert.equal(zeile?.when, 'Nächster · Fr 18:00 (CEST)');
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

	test('#1969: Anzeige des nächsten Versands verwirft die Minuten (HH:00 aus dem Backend)', () => {
		// Vorher: deriveNextSend setzte die Minuten (07:30) — der Versand geht aber
		// zur vollen Stunde raus. Jetzt zeigt die Anzeige ausschließlich local_time.
		const label = formatNextBriefing(backendWert('07:00'), 'vergleich');
		assert.match(label, /\b07:00\b/);
		assert.doesNotMatch(label, /\d{2}:(?!00)\d{2}/, `Minuten ≠ 00 sichtbar: ${label}`);
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
