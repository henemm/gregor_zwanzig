// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Englisch (AC-41).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-41
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich), Sprache `en` am Konto.
//
//   Ueberschrift und Erklaersatz stammen aus dem Katalog en/wetter.json; kein deutscher Text aus
//   de/wetter.json ist im Reiter sichtbar. Sprache wird am Ende auf `de` zurueckgesetzt.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-englisch

import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { HUB_KINDS } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter } from './s3a2794-teil3.helpers';

const KATALOG = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'lib', 'i18n', 'messages');
const laden = (sprache: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(path.join(KATALOG, sprache, 'wetter.json'), 'utf8'));

for (const kind of HUB_KINDS) {
	test(`AC-41 (${kind}): Reiter Wetter auf Englisch — Katalogtexte en, kein deutscher Katalogtext`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const en = laden('en');
		const de = laden('de');
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern' });
		try {
			const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
			expect(res.ok(), `Sprache en setzen: HTTP ${res.status()}`).toBeTruthy();
			const reiter = await oeffneWetter(page, kind, hub.id);

			await expect(reiter.getByTestId(WT.titel)).toHaveText(en['wetter.kopf.titel']);
			await expect(reiter.getByTestId(WT.erklaer)).toHaveText(en['wetter.kopf.erklaerung']);
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText(en['wetter.vorlage.unveraendert']);

			// Deutsche Katalogtexte, die nicht zufaellig auch im englischen Katalog stehen, duerfen nicht erscheinen.
			const text = await reiter.innerText();
			const englischeTexte = new Set(Object.values(en));
			for (const schluessel of ['wetter.kopf.titel', 'wetter.kopf.erklaerung', 'wetter.vorlage.titel', 'wetter.vorlage.eigene', 'wetter.vorlage.unveraendert']) {
				const deutsch = de[schluessel];
				if (!deutsch || englischeTexte.has(deutsch)) continue;
				expect(text, `AC-41: deutscher Text „${deutsch}“ (${schluessel}) im englischen Reiter`).not.toContain(deutsch);
			}
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
		}
	});
}
