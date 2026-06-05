// E2E-Tests fuer Issue #609 — SMS-Rufnummer im Nutzerprofil + Trip/Compare-Kanalauswahl
//
// Spec: docs/specs/modules/issue-609-sms-profil-feld.md
// Acceptance Criteria:
//   - AC-1: Account-Seite zeigt SMS-Eingabefeld mit korrekt vorbefuelltem Wert
//   - AC-5: Trip-Report-Editor zeigt SMS-Checkbox (analog E-Mail/Telegram)
//   - AC-6: Vergleichs-Wizard Step 5 zeigt SMS-Toggle (analog E-Mail/Telegram)
//
// TDD RED-Phase: alle drei Tests MUESSEN fehlschlagen, weil die UI-Elemente
// noch nicht implementiert sind. Nach Implementierung muessen sie GREEN sein.

import { test, expect } from '@playwright/test';

test.describe('Issue #609 — SMS-Profilfeld + Kanalauswahl', () => {
	test.beforeEach(async ({ page }) => {
		// Profil mit gespeicherter SMS-Nummer vorbereiten — auf jede Seite anwendbar
		await page.request.put('/api/auth/profile', {
			data: { sms_to: '+4915199997777' }
		});
	});

	test.afterAll(async ({ request }) => {
		// Cleanup: SMS-Nummer wieder loeschen
		await request.put('/api/auth/profile', { data: { sms_to: '' } });
	});

	test('AC-1: Account-Seite zeigt SMS-Eingabefeld mit gespeichertem Wert', async ({
		page
	}) => {
		await page.goto('/account');
		// Heuristik: Label "Handynummer" oder Input mit type="tel" + name "sms_to"
		const smsInput = page.locator(
			'input[name="sms_to"], input[data-testid="account-sms-to"]'
		);
		await expect(smsInput).toBeVisible();
		await expect(smsInput).toHaveValue('+4915199997777');
	});

	test('AC-5: Trip-Report-Editor zeigt SMS-Checkbox (aktivierbar bei gespeicherter Nummer)', async ({
		page
	}) => {
		// Trip-Detail-Seite mit Report-Konfig oeffnen.
		// Setup-Trip "e2e-cockpit-test" wird in global.setup.ts angelegt.
		await page.goto('/trips/e2e-cockpit-test');
		// Edit-Modus oder Report-Konfig-Bereich oeffnen
		// Hinweis: Konkrete Navigation kann je nach Trip-Detail-Layout variieren —
		// wir suchen direkt nach dem SMS-Channel-Element.
		const smsChannel = page.locator(
			'[data-testid="channel-sms"], [data-testid="report-channel-sms"]'
		);
		await expect(smsChannel).toBeVisible({ timeout: 10_000 });
		// Bei gespeicherter Nummer: NICHT disabled
		const smsCheckbox = smsChannel.locator('input[type="checkbox"]');
		await expect(smsCheckbox).toBeEnabled();
	});

	test('AC-6: Vergleichs-Wizard Step 5 zeigt SMS-Toggle', async ({ page }) => {
		// Compare-Wizard starten — Direkt zu Schritt 5 navigieren
		await page.goto('/compare');
		// "Neuer Vergleich" oder analoger Einstieg
		// Heuristik: data-testid des SMS-Toggles muss in Step5Versand existieren.
		// Wenn Wizard mehrstufig: alle Steps schnell durchklicken oder Direkt-Route nutzen.
		// Fuer RED-Phase reicht: Element exisitiert nicht → Test failed.
		const smsToggle = page.locator(
			'[data-testid="compare-step5-channel-sms"]'
		);
		// Versuch: Wizard navigieren falls noetig
		const newCompareBtn = page.locator(
			'a[href="/compare/new"], button:has-text("Neuer Vergleich")'
		);
		if (await newCompareBtn.count()) {
			await newCompareBtn.first().click();
		}
		// Direkt nach Element suchen (in beliebigem Step / Wizard-Zustand)
		await expect(smsToggle).toBeVisible({ timeout: 15_000 });
	});
});
