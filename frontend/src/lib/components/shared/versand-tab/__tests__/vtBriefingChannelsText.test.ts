// Issue #2455 AC-3: Telegram-Unterzeile im Versand-Reiter folgt dem Telegram-Stil.
// Ausfuehren: cd frontend && npm test -- src/lib/components/shared/versand-tab/__tests__/vtBriefingChannelsText.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { vtBriefingSubTexts } from '../vtBriefingChannelsText.ts';

describe('#2455 AC-3: vtBriefingSubTexts telegramStyle', () => {
	for (const ctx of ['route', 'vergleich'] as const) {
		test(`${ctx}: kurzform verweist auf die SMS-Auswahl`, () => {
			const s = vtBriefingSubTexts(ctx, 'kurzform');
			assert.equal(s.telegram, 'folgt der SMS-Auswahl');
			assert.doesNotMatch(s.telegram, /Spalten/);
		});
		test(`${ctx}: rich bleibt Layout · N Spalten`, () => {
			assert.match(vtBriefingSubTexts(ctx, 'rich').telegram, /^Layout · \d+ Spalten$/);
		});
		test(`${ctx}: ohne Parameter wie rich; E-Mail/SMS unveraendert`, () => {
			assert.deepEqual(vtBriefingSubTexts(ctx), vtBriefingSubTexts(ctx, 'rich'));
			assert.equal(vtBriefingSubTexts(ctx, 'kurzform').email, 'Layout · volle Tabelle');
			assert.equal(vtBriefingSubTexts(ctx, 'kurzform').sms, vtBriefingSubTexts(ctx, 'rich').sms);
		});
	}
});
