// TDD RED — Issue #2521 S1, AC-3 (Spec begriff_erklaerung_infobox.md): „Standards
// zusaetzlich gegen die Quell-Konstanten abgeglichen“.
//
// Die Infobox verspricht „Standard: …“. Das stimmt nur, solange der Text mit dem
// uebereinstimmt, was das Produkt beim Anlegen WIRKLICH voreinstellt. Dieser Test
// liest die Vorgaben dort, wo sie entstehen (nicht aus dem Katalog), und prueft,
// dass der ANGEZEIGTE Text (Katalogwert) sie nennt bzw. nicht zu Unrecht nennt:
//   * Trip-Versand:        ladeReportZustand(null)       -> 07:00 / 18:00, E-Mail
//   * Vergleichs-Versand:  CompareWizardState            -> Morgen 07:00 an, Abend AUS, kein Enddatum
//   * Alarme (beide):      alertChannelState + Anlege-Zustand -> E-Mail+Telegram an, SMS/Premium aus,
//                          Schwelle „gering“, amtliche Warnungen aus
// Aendert jemand die Vorgabe (z. B. Abend-Slot im Vergleich an), wird der Text
// zur Luege und dieser Test rot — genau dafuer ist er da.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/infobox_standards_stimmen_mit_den_quellen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { de } from '../../../i18n/messages/de/index.ts';
import { neuerWiz } from './infoboxSsr.ts';
import { ladeReportZustand } from '../versand-tab/reportConfigPayload.ts';
import {
	CHANNEL_THRESHOLD_LABELS,
	resolveAlertChannelThresholds,
	resolveAlertChannels
} from '../alarme-tab/alertChannelState.ts';
import { initialCreateTripAlarmState } from '../../trip-new/tripNewLogic.ts';

const katalog = de as Record<string, string>;
const text = (k: string): string => {
	assert.ok(katalog[k], `Katalogschluessel ${k} fehlt`);
	return katalog[k];
};

describe('AC-3: Versand-Standard der Infobox = Anlege-Vorgabe der Quelle', () => {
	test('Trip: der Text nennt genau die Zeiten und den Kanal aus ladeReportZustand(null)', () => {
		const z = ladeReportZustand(null);
		assert.equal(z.morning_enabled, true, 'Quelle: Morgen-Slot beim Trip nicht mehr Standard an');
		assert.equal(z.evening_enabled, true, 'Quelle: Abend-Slot beim Trip nicht mehr Standard an');
		assert.equal(z.send_email, true);
		assert.equal(z.send_telegram, false);
		const t = text('info.versand.route');
		assert.ok(t.includes(z.morning_time), `Text nennt ${z.morning_time} nicht: ${t}`);
		assert.ok(t.includes(z.evening_time), `Text nennt ${z.evening_time} nicht: ${t}`);
		assert.match(t, /E-Mail/);
		assert.doesNotMatch(t, /Telegram|SMS/);
	});

	test('Ortsvergleich: Morgen-Zeit genannt, Abend-Zeit NICHT (Slot ist aus), „kein Enddatum“ (endDate null)', () => {
		const wiz = neuerWiz();
		assert.equal(wiz.morningEnabled, true, 'Quelle: Morgen-Slot im Vergleich nicht mehr Standard an');
		assert.equal(wiz.eveningEnabled, false, 'Quelle: Abend-Slot im Vergleich ist jetzt Standard an — Text anpassen');
		assert.equal(wiz.endDate, null, 'Quelle: Vergleich hat jetzt ein Standard-Enddatum — Text anpassen');
		assert.equal(wiz.sendEmail, true);
		const t = text('info.versand.vergleich');
		assert.ok(t.includes(wiz.morningTime), `Text nennt ${wiz.morningTime} nicht: ${t}`);
		assert.ok(!t.includes(wiz.eveningTime), `Text nennt die Abend-Zeit ${wiz.eveningTime}, obwohl der Slot aus ist`);
		assert.match(t, /kein Enddatum/);
	});
});

describe('AC-3: Alarm-Standard der Infobox = Anlege-Vorgabe der Quelle (Trip UND Ortsvergleich)', () => {
	const quellen: [string, () => { kanaele: ReturnType<typeof resolveAlertChannels>; schwellen: ReturnType<typeof resolveAlertChannelThresholds>; amtlich: boolean }][] = [
		[
			'route',
			() => {
				const s = initialCreateTripAlarmState();
				return { kanaele: s.channels, schwellen: s.channelThresholds, amtlich: s.officialWarningsEnabled };
			}
		],
		[
			'vergleich',
			() => {
				const wiz = neuerWiz();
				return {
					kanaele: resolveAlertChannels(wiz.channels),
					schwellen: resolveAlertChannelThresholds(wiz.channelThresholds),
					amtlich: wiz.officialWarningsEnabled
				};
			}
		]
	];
	for (const [kontext, quelle] of quellen) {
		test(`${kontext}: Text nennt die an-Kanaele, nicht die aus-Kanaele, die Start-Schwelle und amtliche Warnungen aus`, () => {
			const q = quelle();
			assert.equal(q.kanaele.email, true, 'Quelle: E-Mail ist kein Alarm-Standard mehr');
			assert.equal(q.kanaele.telegram, true, 'Quelle: Telegram ist kein Alarm-Standard mehr');
			assert.equal(q.kanaele.sms, false, 'Quelle: SMS ist jetzt Alarm-Standard — Text anpassen');
			assert.equal(q.kanaele.premium_sms, false, 'Quelle: Premium-SMS ist jetzt Alarm-Standard — Text anpassen');
			const t = text(`info.alarme.${kontext}`);
			assert.match(t, /E-Mail/);
			assert.match(t, /Telegram/);
			assert.doesNotMatch(t, /SMS/, 'Text nennt SMS, obwohl SMS kein Standard ist');
			assert.equal(q.schwellen.email, 'LOW');
			assert.equal(q.schwellen.telegram, 'LOW');
			assert.ok(t.includes(`„${CHANNEL_THRESHOLD_LABELS[q.schwellen.email]}“`), `Text nennt die Start-Schwelle nicht: ${t}`);
			assert.equal(q.amtlich, false, 'Quelle: amtliche Warnungen sind jetzt Standard an — Text anpassen');
			assert.match(t, /amtliche Warnungen aus/);
		});
	}
});
