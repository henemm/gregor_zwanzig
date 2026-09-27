// TDD -- Issue #2422 S2a, AC-6: TS -- alle Kanaele im Speichern-Payload
// (fuer Goldens MIT eigenem Layout je Kanal) -- UND Gegenprobe fuer Golden C
// (Kaskadenquelle 'global'): ein NIE editierter Reiter darf KEINEN eigenen
// Kanal-Eintrag bekommen, sonst kippt die Kaskadenquelle faelschlich von
// 'global' auf 'per_channel' und der B9-Fall waere durch den Speichervorgang
// selbst zerstoert.
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-6).
//
// Beide Haelften sind bereits HEUTE gruen -- `mergeAllChannelLayoutsForSave`
// (channelMetricLayouts.ts:117-129) ist unveraendert korrekt: `channelBuckets
// [ch] === null` laesst den Bestandswert aus `prevLayouts` unangetastet (weder
// geloescht noch neu erzeugt). Diese Datei ist ein REGRESSIONS-Waechter, kein
// RED-Beweis -- ein Fix-Loop, der bei Golden C faelschlich einen eigenen
// SMS-Eintrag sendet (um AC-6 "alle Kanaele" pauschal auf Golden C
// anzuwenden), macht GENAU den zweiten Testfall rot.
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/speichern_sendet_alle_kanaele.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { mergeAllChannelLayoutsForSave, type ChannelOverride } from '../channelMetricLayouts.ts';
import type { ChannelId } from '../../layout-tab/ltChannels.ts';

const leereUeberschreibung: ChannelOverride = {
	buckets: { primary: ['wind'], secondary: [], off: [] },
	friendlyMap: {},
};
const buildMetrics = () => [{ metric_id: 'wind', enabled: true, use_friendly_format: false, horizons: { today: true, tomorrow: true, day_after: true }, bucket: 'primary' as const, order: 0 }];

describe('AC-6: Kanal-Vollstaendigkeit im Speichern-Payload', () => {
	test('Golden A/B (alle drei Kanaele im Bestand): nur email bearbeitet, telegram/sms bleiben erhalten', () => {
		const prevLayouts = {
			email: [{ metric_id: 'wind', enabled: true }],
			telegram: [{ metric_id: 'gust', enabled: true }],
			sms: [{ metric_id: 'rain_probability', enabled: true }],
		} as never;
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: leereUeberschreibung, telegram: null, sms: null,
		};

		const next = mergeAllChannelLayoutsForSave(prevLayouts, channelBuckets, buildMetrics);

		assert.deepEqual(
			Object.keys(next).sort(),
			['email', 'sms', 'telegram'],
			`AC-6: alle drei Kanaele muessen im gesendeten Payload stehen, auch wenn nur ` +
				`email bearbeitet wurde: ${JSON.stringify(Object.keys(next))}`,
		);
	});

	test('Golden C (Kaskadenquelle global, kein sms-Layout): unbearbeiteter SMS-Reiter bekommt KEINEN eigenen Eintrag', () => {
		// Nur "email" im Bestand -- wie golden_c.json (kein sms/telegram-Schluessel).
		const prevLayouts = {
			email: [{ metric_id: 'wind', enabled: true }],
		} as never;
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: leereUeberschreibung, telegram: null, sms: null,
		};

		const next = mergeAllChannelLayoutsForSave(prevLayouts, channelBuckets, buildMetrics);

		assert.deepEqual(
			Object.keys(next).sort(),
			['email'],
			`AC-6/B9-Schutz: ein NIE editierter SMS-Reiter (Kaskadenquelle 'global') darf ` +
				`beim Speichern KEINEN eigenen channel_layouts.sms-Eintrag bekommen -- sonst ` +
				`kippt die Kaskadenquelle faelschlich auf 'per_channel' und der B9-Fall (Golden ` +
				`C) waere durch das Speichern selbst zerstoert. Erhalten: ` +
				`${JSON.stringify(Object.keys(next))}`,
		);
	});
});
