// Issue #2655 (i18n F6, Epic #2644) — AC-5: die ENGLISCHEN Hinweistexte des
// Versand-Reiters bewerten keinen Kanal (Gegenstueck zum deutschen Waechter
// vtBriefingChannelsTextNoJudgement.test.ts, Spec fix_1719_s3 AC-5a).
// Geprueft wird der ERZEUGTE Text der reinen Funktionen vtBriefingLeadText und
// vtBriefingSubTexts in beiden Kontexten und beiden Telegram-Stilen, nachdem
// die Sprache OHNE Neuladen von de auf en umgeschaltet wurde. Die Wortliste
// laeuft zuerst gegen bekannt wertende Saetze (Gegenprobe, nicht vakuum-gruen).
// Spec: docs/specs/modules/i18n_f6_versand_tab_2655.md (AC-5)
//
//   cd frontend && npm test -- src/lib/components/shared/versand-tab/__tests__/versand_texte_ohne_wertung_en.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, trFor } from '../../../../i18n/index.ts';
import { vtBriefingLeadText, vtBriefingSubTexts } from '../vtBriefingChannelsText.ts';

const WERTUNG_EN = [
	/\bflat\b/i,
	/\bbad\b/i,
	/\bbetter\b/i,
	/\bworse\b/i,
	/\bbest\b/i,
	/\bshould\b/i,
	/\bonly the essentials\b/i,
	/\bmost important\b/i,
	/\bcritical\b/i,
	/\bpoor\b/i,
	/\bsimplified\b/i
];

const wertungen = (text: string) => WERTUNG_EN.filter((r) => r.test(text)).map(String);

afterEach(() => locale.set('de'));

describe('Gegenprobe: die Wortliste erkennt wertende Saetze', () => {
	test('flat, better, should, only the essentials', () => {
		assert.deepEqual(wertungen('SMS runs flat'), ['/\\bflat\\b/i']);
		assert.deepEqual(wertungen('Email is better'), ['/\\bbetter\\b/i']);
		assert.deepEqual(wertungen('You should use email'), ['/\\bshould\\b/i']);
		assert.deepEqual(wertungen('Only the essentials go by SMS'), ['/\\bonly the essentials\\b/i']);
		assert.deepEqual(wertungen('Layout · no grid, 160 characters'), []);
	});
});

describe('AC-5: englische Einleitung und Unterzeilen ohne Wertung', () => {
	for (const context of ['route', 'vergleich'] as const) {
		for (const stil of ['rich', 'kurzform'] as const) {
			test(`${context} / ${stil}`, () => {
				locale.set('de');
				const de = [vtBriefingLeadText(context), ...Object.values(vtBriefingSubTexts(context, stil))];
				locale.set('en');
				const en = [vtBriefingLeadText(context), ...Object.values(vtBriefingSubTexts(context, stil))];
				// Wirklich englisch (sonst waere die Pruefung vakuum): kein Text gleich dem deutschen.
				en.forEach((t, i) => assert.notEqual(t, de[i], `noch deutsch: ${t}`));
				assert.ok(en[0].startsWith(context === 'route' ? 'The trip briefing' : 'The location comparison'), en[0]);
				for (const t of en) assert.deepEqual(wertungen(t), [], t);
			});
		}
	}

	test('auch die uebrigen englischen Hinweise des Reiters (Premium-SMS, Zeitplan, Kurzstil) ohne Wertung', () => {
		const keys = [
			'versand.premium_sms.hinweis.nicht_verfuegbar',
			'versand.premium_sms.hinweis.gelernt',
			'versand.premium_sms.hinweis.verfallen',
			'versand.premium_sms.hinweis.nie_gemeldet',
			'versand.zeitplan.kein_kanal_text',
			'versand.zeitplan.vergleich_intro',
			'telegram_kurzstil.hinweis_aktiv',
			'telegram_kurzstil.hinweis_inaktiv'
		] as const;
		for (const k of keys) assert.deepEqual(wertungen(trFor('en', k)), [], k);
	});
});
