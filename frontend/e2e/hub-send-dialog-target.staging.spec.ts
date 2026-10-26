// E2E (Staging) — Issue #2347 S2 (Epic #2345, Etappe P6): geteilter Sende-Dialog
// aus der Liste — EINE Zusicherung für Trip-Liste UND Ortsvergleich-Liste per
// Schleife über HUB_KINDS. Bleibt Staging-Spec, steht NICHT in der Ratsche.
//
// Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md § „hub-send-dialog-target.staging.spec.ts (SD)", AC-7.
// Ersetzt: compare-send-dialog-target.staging.spec.ts (Issue #1471; Zuordnung Zeilen 42-43).
// Änderungen gegenüber der Vorlage: Eigen-Seed je kind statt `.first()` irgendeines
// Staging-Eintrags; Bildschirmfotos und Konsolen-Ausgaben entfallen (keine Zusicherungen);
// die feste 1,5-s-Pause durch ein `expect.poll`-Stabilitätsfenster ersetzt.
//
// Wovon die Sperre abhängt (sendTargetLabel.ts): E-Mail ist immer Teil des Versands;
// „Senden" ist nur gesperrt, wenn das KONTO keine bzw. keine bestätigte Adresse hat.
// Der Eigen-Seed (keine Empfänger, keine Zusatzkanäle) kann das Ziel also nicht
// unzustellbar machen — das Staging-Konto muss es sein. Das prüft eine harte
// Vorbedingung über GET /api/auth/profile (kein skip).
//
// Kein echter Versand: jeder Sende-Abruf wird per page.route abgefangen und
// abgebrochen (zählt zugleich) — selbst wenn die Sperre bräche, ginge nichts hinaus.
//
// Ausführen (gegen Staging, aus frontend/, NACH Push+Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.hub-send-dialog-target.staging.config.ts

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, createTestLocation, seedHub, type HubKind, type SeededHub } from './helpers';

test.use({ viewport: { width: 1280, height: 900 } });

interface Seed {
	hub: SeededHub;
	aufraeumen(): Promise<void>;
}

/**
 * Eigen-Seed OHNE zustellbares Ziel. Kind-Zweig nur für den Seed (Begründung: der
 * Vergleich braucht einen Ort, sonst ist er ein Entwurf ohne „Senden" im Menü; die
 * CI-Seed-Orte aus global.setup.ts gibt es auf Staging nicht). `schedule: 'manual'`
 * (pausiert) — der Listen-Menüeintrag „Senden" steht auch dort, und der Seed löst
 * selbst nie einen geplanten Versand aus.
 */
async function seedOhneZiel(request: APIRequestContext, kind: HubKind): Promise<Seed> {
	if (kind === 'route') {
		const hub = await seedHub(request, kind);
		return { hub, aufraeumen: () => hub.aufraeumen() };
	}
	const ort = await createTestLocation(request, { name: `SD Ort ${Date.now()}` });
	try {
		const hub = await seedHub(request, kind, {
			extra: {
				location_ids: [ort.id],
				schedule: 'manual',
				empfaenger: [],
				send_telegram: false,
				send_sms: false,
				send_premium_sms: false
			}
		});
		return {
			hub,
			aufraeumen: async () => {
				await hub.aufraeumen();
				await request.delete(`/api/locations/${ort.id}`).catch(() => {});
			}
		};
	} catch (e) {
		await request.delete(`/api/locations/${ort.id}`).catch(() => {});
		throw e;
	}
}

/** Harte Vorbedingung: das Konto hat kein zustellbares Ziel (sonst ist E-Mail immer zustellbar). */
async function kontoOhneZiel(request: APIRequestContext): Promise<void> {
	const res = await request.get('/api/auth/profile');
	expect(res.ok(), `GET /api/auth/profile HTTP ${res.status()}`).toBeTruthy();
	const profil = (await res.json()) as { mail_to?: string; email_verified?: boolean };
	expect(
		!profil.mail_to || profil.email_verified !== true,
		'Vorbedingung: Staging-Konto ohne (bestätigte) E-Mail-Adresse — nur dann ist kein Ziel zustellbar'
	).toBe(true);
}

/** Fängt jeden Sende-Abruf für diesen Eintrag ab (bricht ab) und zählt ihn. */
async function sendeAbrufe(page: Page, id: string): Promise<{ anzahl: () => number }> {
	let n = 0;
	await page.route(`**/api/briefings/${encodeURIComponent(id)}/send**`, async (route) => {
		if (route.request().method() === 'POST') n++;
		await route.abort();
	});
	return { anzahl: () => n };
}

/** Stabilitätsfenster statt Schlaf: die Zahl muss 1,5 s lang bei 0 bleiben. */
async function bleibtOhneSendeAbruf(abrufe: { anzahl: () => number }, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				if (abrufe.anzahl() !== 0) {
					seit = 0;
					return abrufe.anzahl();
				}
				seit ||= Date.now();
				return Date.now() - seit >= 1_500 ? 'stabil' : 0;
			},
			{ message, timeout: 6_000, intervals: [200] }
		)
		.toBe('stabil');
}

async function oeffneMenuepunkt(page: Page, kind: HubKind, id: string, punkt: string): Promise<void> {
	const zeile = page.getByTestId(HUB_SEL[kind].liste.zeile(id));
	await expect(zeile).toBeVisible({ timeout: 15_000 });
	await zeile.getByTestId(HUB_SEL[kind].liste.menue).click();
	const menue = page.getByRole('menu');
	await expect(menue).toBeVisible();
	await menue.getByRole('menuitem', { name: punkt, exact: true }).click();
}

/**
 * Titel des Lösch-Dialogs je kind. Kind-Zweig nur für den Text (Begründung: der
 * Bestätigungstitel ist je Seite formuliert — Trip „Trip löschen", Vergleich
 * „Vergleich löschen?"); die Zusicherung „eigener Text, nicht der Sende-Dialog" ist identisch.
 */
const loeschTitel = (kind: HubKind) => (kind === 'route' ? 'Trip löschen' : 'Vergleich löschen?');

/** Der gesperrte Dialog nennt das tatsächliche (fehlende) Ziel — nie „0 Empfänger". */
const GESPERRT_TEXT = /es (kann|wird) nichts (gesendet|zugestellt)/;

for (const kind of HUB_KINDS) {
	test(`SD-1 (${kind}): Lösch-Dialog behält eigenen Text; Sende-Dialog nennt das echte Ziel, „Senden" gesperrt, erzwungener Klick sendet nicht`, async ({
		page
	}) => {
		await kontoOhneZiel(page.request);
		const seed = await seedOhneZiel(page.request, kind);
		try {
			const id = seed.hub.id;
			const abrufe = await sendeAbrufe(page, id);
			await page.goto(HUB_SEL[kind].liste.url);

			// Regression: Lösch-Dialog behält seinen eigenen Text — nur prüfen, abbrechen.
			await oeffneMenuepunkt(page, kind, id, 'Löschen');
			const loeschDialog = page.getByRole('alertdialog').or(page.getByRole('dialog'));
			await expect(loeschDialog.getByText(loeschTitel(kind), { exact: true })).toBeVisible();
			await expect(loeschDialog).not.toContainText('Briefing senden');
			await loeschDialog.getByRole('button', { name: 'Abbrechen' }).click();
			await expect(loeschDialog).toBeHidden();

			// Sende-Dialog: echtes Ziel, gesperrt.
			await oeffneMenuepunkt(page, kind, id, 'Senden');
			const sendeDialog = page.getByTestId('send-confirm-dialog');
			await expect(sendeDialog).toBeVisible();
			await expect(page.locator('body')).not.toContainText('0 Empfänger');
			await expect(sendeDialog).toContainText(GESPERRT_TEXT);
			const senden = sendeDialog.getByTestId('send-confirm-yes');
			await expect(senden).toBeVisible();
			await expect(senden).toBeDisabled();

			await senden.click({ force: true }).catch(() => {});
			await bleibtOhneSendeAbruf(abrufe, 'gesperrter „Senden"-Knopf darf keinen Sende-Abruf auslösen');
			await expect(sendeDialog).toBeVisible();

			await sendeDialog.getByTestId('send-confirm-cancel').click();
			await expect(sendeDialog).toBeHidden();
		} finally {
			await seed.aufraeumen();
		}
	});
}

for (const kind of HUB_KINDS) {
	test(`SD-2 (${kind}): Stress — zweimal Menü → Senden → Abbrechen, dann fünf erzwungene Klicks auf den gesperrten Knopf ⇒ kein Sende-Abruf, Dialog stabil`, async ({
		page
	}) => {
		await kontoOhneZiel(page.request);
		const seed = await seedOhneZiel(page.request, kind);
		try {
			const id = seed.hub.id;
			const abrufe = await sendeAbrufe(page, id);
			await page.goto(HUB_SEL[kind].liste.url);
			const sendeDialog = page.getByTestId('send-confirm-dialog');

			for (let i = 0; i < 2; i++) {
				await oeffneMenuepunkt(page, kind, id, 'Senden');
				await expect(sendeDialog).toBeVisible();
				await sendeDialog.getByTestId('send-confirm-cancel').click();
				await expect(sendeDialog).toBeHidden();
			}

			await oeffneMenuepunkt(page, kind, id, 'Senden');
			await expect(sendeDialog).toBeVisible();
			const senden = sendeDialog.getByTestId('send-confirm-yes');
			await expect(senden).toBeDisabled();
			for (let i = 0; i < 5; i++) {
				await senden.click({ force: true }).catch(() => {});
			}
			await bleibtOhneSendeAbruf(abrufe, 'fünf erzwungene Klicks auf den gesperrten Knopf dürfen nichts senden');
			await expect(sendeDialog).toBeVisible();
			await expect(senden).toBeDisabled();

			await sendeDialog.getByTestId('send-confirm-cancel').click();
			await expect(sendeDialog).toBeHidden();
		} finally {
			await seed.aufraeumen();
		}
	});
}
