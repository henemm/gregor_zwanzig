// E2E (Staging) — Issue #2406 (S3 aus #2153, Epic #2138), AC-17: der
// vollstaendige SMS-Bestaetigungsablauf einmal durch den Browser.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-17.
//
// 🔴 Laeuft NUR gegen Staging und NUR nach dem Deploy dieser Scheibe: sie
// braucht (a) die neuen Endpunkte /api/auth/sms/{verify,staging-code} und
// (b) GZ_ENV=staging fuer den Testweg (router.go). Im CI-`e2e`-Lauf gegen den
// lokalen Stack existiert beides nicht — die Datei gehoert deshalb NICHT in
// .github/ci_e2e_specs.txt.
//
// Wegwerfkonto statt Sonderkonto (Muster fix-2271-email-verify-gate.spec.ts):
// jeder Lauf legt ein frisches Konto an, damit kein echtes Profil (und keine
// echte Rufnummer) beruehrt wird. Die Nummer ist eine Test-Nummer; ein echter
// SMS-Versand entsteht nicht, weil Staging den seven.io-Sandbox-Zugang fuehrt
// (#1336) — und der Klartext-Code kommt ohnehin ueber den Testweg, nicht per
// SMS.
//
// Ausfuehren (aus frontend/):
//   npx playwright test e2e/feat-2406-sms-verify.spec.ts --config playwright.config.ts
// (mit PLAYWRIGHT_BASE_URL auf https://staging.gregor20.henemm.com, Muster
// fix-2271-email-verify-gate.spec.ts)

import { test, expect, type Browser, type Page } from '@playwright/test';

const PASSWORT = 'test1234';
const NUMMER = '+491511000406';
const NEUE_NUMMER = '+491512000406';

/** Frisches Wegwerfkonto, ueber den Staging-Testweg sofort e-mail-bestaetigt. */
async function frischesKonto(page: Page): Promise<string> {
	const kennung = `e2e2406sms${Date.now()}`;
	const reg = await page.request.post('/api/auth/register', {
		data: { username: kennung, password: PASSWORT, email: `${kennung}@example.com` }
	});
	expect([200, 201].includes(reg.status()), `Registrierung fehlgeschlagen: ${reg.status()}`).toBeTruthy();

	// E-Mail-Gate (#2271) oeffnen — sonst kann sich das Konto nicht anmelden.
	const tokenAntwort = await page.request.post('/api/auth/verify-email/staging-token', {
		data: { username: kennung }
	});
	expect(
		tokenAntwort.ok(),
		`Staging-Testweg (E-Mail) antwortet ${tokenAntwort.status()} — laeuft das Ziel mit GZ_ENV=staging?`
	).toBeTruthy();
	const { token } = await tokenAntwort.json();
	const bestaetigt = await page.request.post('/api/auth/verify-email', {
		data: { user: kennung, token }
	});
	expect(bestaetigt.ok(), `E-Mail-Bestaetigung fehlgeschlagen: ${bestaetigt.status()}`).toBeTruthy();
	return kennung;
}

/** Eigener Browser-Kontext OHNE die Fixture-Sitzung, im Konto angemeldet. */
async function angemeldeterGast(browser: Browser, kennung: string) {
	const ctx = await browser.newContext({ storageState: undefined });
	const seite = await ctx.newPage();
	await seite.goto('/login');
	await seite.fill('input[name="username"]', kennung);
	await seite.fill('input[name="password"]', PASSWORT);
	await seite.click('button[type="submit"]');
	await expect(seite).not.toHaveURL(/\/login/);
	return { ctx, seite };
}

test('AC-17: Nummer eintragen, Code eingeben, Nummer gilt als bestätigt', async ({
	page,
	browser
}) => {
	const kennung = await frischesKonto(page);
	const { ctx, seite } = await angemeldeterGast(browser, kennung);

	try {
		// (a) Nummer im Profil eintragen.
		await seite.goto('/account');
		await seite.fill('input[name="sms_to"]', NUMMER);
		await seite.getByRole('button', { name: 'Speichern' }).first().click();

		// Der Pending-Hinweis erscheint: die Nummer ist eingetragen, aber unbestätigt.
		const hinweis = seite.getByTestId('sms-pending-notice');
		await expect(hinweis).toBeVisible();
		await expect(hinweis).toContainText(NUMMER);

		// (b) Klartext-Code ueber den staging-only Testweg fuer das EIGENE Konto.
		const codeAntwort = await seite.request.post('/api/auth/sms/staging-code', { data: {} });
		expect(
			codeAntwort.ok(),
			`Staging-Testweg (SMS) antwortet ${codeAntwort.status()} — laeuft das Ziel mit GZ_ENV=staging?`
		).toBeTruthy();
		const { code } = await codeAntwort.json();
		expect(code, 'Testweg lieferte keinen Code').toBeTruthy();

		// (c) Code in der Kontoseite eintragen und bestaetigen.
		await seite.getByTestId('sms-code-input').fill(code);
		await seite.getByRole('button', { name: /bestätigen/i }).first().click();

		// Danach: Nummer gilt als bestaetigt, der Pending-Hinweis ist weg.
		await expect(seite.getByTestId('sms-pending-notice')).toHaveCount(0);
		const profil = await seite.request.get('/api/auth/profile');
		const daten = await profil.json();
		expect(daten.sms_verified, `Profil nach Bestätigung: ${JSON.stringify(daten)}`).toBe(true);
		expect(daten.sms_to).toBe(NUMMER);
		expect(daten.pending_sms_to ?? '').toBe('');
	} finally {
		await ctx.close();
	}
});

test('AC-17/AC-3: eine neue Nummer wird erst nach der Bestätigung wirksam', async ({
	page,
	browser
}) => {
	const kennung = await frischesKonto(page);
	const { ctx, seite } = await angemeldeterGast(browser, kennung);

	try {
		// Erste Nummer bestaetigen (Ausgangslage).
		await seite.goto('/account');
		await seite.fill('input[name="sms_to"]', NUMMER);
		await seite.getByRole('button', { name: 'Speichern' }).first().click();
		await expect(seite.getByTestId('sms-pending-notice')).toBeVisible();
		let { code } = await (await seite.request.post('/api/auth/sms/staging-code', { data: {} })).json();
		await seite.getByTestId('sms-code-input').fill(code);
		await seite.getByRole('button', { name: /bestätigen/i }).first().click();
		await expect(seite.getByTestId('sms-pending-notice')).toHaveCount(0);

		// Zweite Nummer eintragen: die erste bleibt wirksam, die zweite wartet.
		await seite.reload();
		await seite.fill('input[name="sms_to"]', NEUE_NUMMER);
		await seite.getByRole('button', { name: 'Speichern' }).first().click();
		await expect(seite.getByTestId('sms-pending-notice')).toContainText(NEUE_NUMMER);

		const zwischen = await (await seite.request.get('/api/auth/profile')).json();
		expect(zwischen.sms_to, 'AC-3: die bestätigte Nummer bleibt bis zur Bestätigung wirksam').toBe(NUMMER);
		expect(zwischen.pending_sms_to).toBe(NEUE_NUMMER);

		({ code } = await (await seite.request.post('/api/auth/sms/staging-code', { data: {} })).json());
		await seite.getByTestId('sms-code-input').fill(code);
		await seite.getByRole('button', { name: /bestätigen/i }).first().click();
		await expect(seite.getByTestId('sms-pending-notice')).toHaveCount(0);

		const danach = await (await seite.request.get('/api/auth/profile')).json();
		expect(danach.sms_to).toBe(NEUE_NUMMER);
		expect(danach.sms_verified).toBe(true);
	} finally {
		await ctx.close();
	}
});
