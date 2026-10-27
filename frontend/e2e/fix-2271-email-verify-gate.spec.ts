// E2E (Staging) — Issue #2271 (S2 aus #2146, Epic #2138): Scharfschaltung des
// Login-Gates bei unbestätigter E-Mail-Adresse.
// Spec: docs/specs/modules/email_verify_scharfschaltung_2271.md — AC-12..AC-15.
//
// 🔴 Diese Datei läuft NUR gegen Staging und NUR nach dem Deploy der Scheibe:
// sie braucht (a) das scharfe Gate und (b) den staging-only Testweg
// `/api/auth/verify-email/staging-token` (GZ_ENV == "staging", router.go:80).
// Im CI-`e2e`-Lauf gegen den isolierten lokalen Stack existiert beides nicht —
// die Datei gehört deshalb NICHT in .github/ci_e2e_specs.txt.
//
// Wegwerfkonten statt Sonderkonten: jeder Lauf erzeugt einen neuen Nutzer mit
// Laufzeit-Suffix. Genau diese Klasse von Konten kann kein Backfill erreichen —
// deshalb holt der Testweg das Token.
//
// 🔴 Der Testweg ist anmeldepflichtig, das Wegwerfkonto ist aber genau das,
// was sich nicht anmelden kann. Das Token holt deshalb die ANGEMELDETE
// Fixture-Sitzung (`page`, storageState des Projekts) für das fremde Konto —
// der Handler nimmt die Kennung aus der Nutzlast (staging_verify_token.go:34).
//
// Ausführen (gegen Staging, aus frontend/):
//   npx playwright test e2e/fix-2271-email-verify-gate.spec.ts --config playwright.config.ts

import { test, expect, type Browser, type Page } from '@playwright/test';

const PASSWORT = 'test1234';

/** Legt ein frisches, unbestätigtes Wegwerfkonto an und liefert die Kennung. */
async function registriereWegwerfkonto(page: Page, marke: string): Promise<string> {
	const kennung = `e2e2271${marke}${Date.now()}`;
	const reg = await page.request.post('/api/auth/register', {
		data: { username: kennung, password: PASSWORT, email: `${kennung}@example.com` }
	});
	expect([200, 201].includes(reg.status()), `Registrierung fehlgeschlagen: ${reg.status()}`).toBeTruthy();
	return kennung;
}

/** Browser-Kontext OHNE die Fixture-Sitzung — sonst startete der "Gast" als admin. */
async function gastKontext(browser: Browser) {
	const ctx = await browser.newContext({ storageState: undefined });
	return { ctx, seite: await ctx.newPage() };
}

// AC-15: beide Zweige des Gates in EINEM Lauf mit DEMSELBEN Konto — erst 403,
// nach der Bestätigung 200. Ein Test, der nur den Deny-Zweig prüfte, bliebe
// auch dann grün, wenn das Gate niemanden mehr durchließe.
test('AC-15: Wegwerfkonto wird vor der Bestätigung abgewiesen und danach angenommen', async ({
	page,
	browser
}) => {
	const kennung = await registriereWegwerfkonto(page, 'gate');
	const { ctx, seite: gast } = await gastKontext(browser);

	try {
		// (1) Vor der Bestätigung: 403 mit dem Grund, kein Session-Cookie.
		const ersterVersuch = await gast.request.post('/api/auth/login', {
			data: { username: kennung, password: PASSWORT }
		});
		expect(
			ersterVersuch.status(),
			`Login vor der Bestätigung muss 403 sein, ist ${ersterVersuch.status()}`
		).toBe(403);
		expect((await ersterVersuch.json()).error).toBe('email_not_verified');

		// (2) Token über den staging-only Testweg — mit der angemeldeten
		// Fixture-Sitzung, nicht mit der (nicht existierenden) des Wegwerfkontos.
		const tokenAntwort = await page.request.post('/api/auth/verify-email/staging-token', {
			data: { username: kennung }
		});
		expect(
			tokenAntwort.ok(),
			`Staging-Testweg antwortet ${tokenAntwort.status()} — läuft das Ziel mit GZ_ENV=staging?`
		).toBeTruthy();
		const { token } = await tokenAntwort.json();
		expect(token, 'Testweg lieferte kein Token').toBeTruthy();

		// (3) Regulärer Verifikations-Endpunkt — der Testweg setzt selbst nichts.
		const bestaetigung = await gast.request.post('/api/auth/verify-email', {
			data: { user: kennung, token }
		});
		expect(
			bestaetigung.ok(),
			`Bestätigung fehlgeschlagen: ${bestaetigung.status()} ${await bestaetigung.text()}`
		).toBeTruthy();

		// (4) Nach der Bestätigung: derselbe Login gelingt.
		const zweiterVersuch = await gast.request.post('/api/auth/login', {
			data: { username: kennung, password: PASSWORT }
		});
		expect(
			zweiterVersuch.status(),
			`Login nach der Bestätigung muss 200 sein, ist ${zweiterVersuch.status()}`
		).toBe(200);
	} finally {
		await ctx.close();
	}
});

// AC-12 / AC-13: die Bedien-Fläche. Der 403 darf im Frontend nicht im
// pauschalen `!resp.ok`→"Invalid credentials"-Mapping verschwinden
// (+page.server.ts:35-37), und der Nutzer braucht einen Ausweg, nicht nur
// einen Text.
test('AC-12/AC-13: Login-Seite erklärt den 403 und bietet den erneuten Versand an', async ({
	page,
	browser
}) => {
	const kennung = await registriereWegwerfkonto(page, 'ui');
	const { ctx, seite: gast } = await gastKontext(browser);

	try {
		await gast.goto('/login');
		await gast.fill('input[name="username"]', kennung);
		await gast.fill('input[name="password"]', PASSWORT);
		await gast.click('button[type="submit"]');

		// AC-12: verständlicher deutscher Hinweis — NICHT der bisherige Text.
		const hinweis = gast.getByTestId('login-error-email-not-verified');
		await expect(hinweis).toBeVisible();
		await expect(hinweis).toContainText(/bestätig/i);
		await expect(gast.locator('body')).not.toContainText('Benutzername oder Passwort nicht korrekt.');

		// AC-13: das Resend-Formular löst die Aktion aus und quittiert sie.
		// Beobachtet wird der Aufruf der SvelteKit-Action (?/resend) — der
		// Aufruf von POST /api/auth/verify-email/resend selbst geschieht
		// serverseitig und ist im Browser strukturell nicht sichtbar.
		const aktion = gast.waitForRequest(
			(req) => req.method() === 'POST' && req.url().includes('/resend')
		);
		await gast.getByTestId('login-resend-submit').click();
		await aktion;

		await expect(gast.getByTestId('login-resend-confirmed')).toBeVisible();
	} finally {
		await ctx.close();
	}
});

// AC-14: Nach der Registrierung darf die Login-Seite nicht mehr zur sofortigen
// Anmeldung auffordern — die ist nach der Scharfschaltung nicht mehr möglich.
test('AC-14: Nach der Registrierung weist die Login-Seite auf die Bestätigungsmail hin', async ({
	browser
}) => {
	const { ctx, seite: gast } = await gastKontext(browser);

	try {
		const kennung = `e2e2271reg${Date.now()}`;
		await gast.goto('/register');
		await gast.fill('input[name="username"]', kennung);
		await gast.fill('input[name="email"]', `${kennung}@example.com`);
		await gast.fill('input[name="password"]', PASSWORT);
		await gast.fill('input[name="confirmPassword"]', PASSWORT);
		await gast.click('button[type="submit"]');

		await gast.waitForURL(/\/login/);
		const hinweis = gast.getByTestId('login-registered-hint');
		await expect(hinweis).toBeVisible();
		await expect(hinweis).toContainText(/bestätig/i);
		await expect(hinweis).not.toContainText('Bitte melde dich an');
	} finally {
		await ctx.close();
	}
});
