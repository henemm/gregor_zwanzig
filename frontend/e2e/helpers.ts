import { type Page } from '@playwright/test';
import * as path from 'node:path';

/**
 * Login helper — authenticates via the login form and returns the page
 * with a valid session cookie set.
 */
export async function login(page: Page) {
	await page.goto('/');
	if (!page.url().includes('/login')) return;
	await page.fill('input[name="username"]', 'admin');
	await page.fill('input[name="password"]', 'test1234');
	await page.click('button[type="submit"]');
	await page.waitForURL('/');
}

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 1 (Sub-Spec #161 §9).
 * Wiederverwendet in `trip-wizard-step1.spec.ts` und `trip-wizard-shell.spec.ts`.
 */
export interface Step1Input {
	activity: 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';
	name: string;
	shortcode?: string;
	startDate: string; // 'YYYY-MM-DD'
}

/**
 * Fuellt die drei Pflicht- und das optionale Feld in Step 1 des Trip-Wizards.
 * Quelle: docs/specs/modules/epic_136_step1_profile.md §9.
 */
export async function fillStep1(page: Page, input: Step1Input): Promise<void> {
	await page.getByTestId(`trip-wizard-step1-chip-${input.activity}`).click();
	await page.getByTestId('trip-wizard-step1-name').fill(input.name);
	if (input.shortcode !== undefined) {
		await page.getByTestId('trip-wizard-step1-shortcode').fill(input.shortcode);
	}
	await page.getByTestId('trip-wizard-step1-startdate').fill(input.startDate);
}

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 2 (Sub-Spec #162 §11.2).
 * Default-Files: `['test-trip.gpx']` aus `frontend/e2e/fixtures/`.
 */
export interface Step2Input {
	files?: string[];
}

/**
 * Laedt eine oder mehrere GPX-Dateien in den Step-2-Drop-Bereich
 * und triggert anschliessend "Etappen anlegen" — wartet auf erscheinen
 * der ersten Stage-Row.
 *
 * Voraussetzung: Wizard ist auf Step 2 (TripWizardShell hat Step2Stages gemountet).
 */
export async function fillStep2(page: Page, input?: Step2Input): Promise<void> {
	const files = (input?.files ?? ['test-trip.gpx']).map((f) =>
		path.resolve('./e2e/fixtures', f)
	);
	const fileInput = page.locator('input[type="file"][accept=".gpx"]');
	await fileInput.setInputFiles(files);
	// Pending-Region erwartet — Bulk-Commit-Button erscheint nach setInputFiles.
	const commit = page.getByTestId('trip-wizard-step2-bulk-commit');
	await commit.waitFor({ state: 'visible' });
	await commit.click();
	// Erste Stage-Row muss sichtbar werden.
	await page.getByTestId('trip-wizard-step2-stage-row-0').waitFor({ state: 'visible' });
}

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 3 (Sub-Spec #163 §10).
 * Default-Verhalten: keine Aktion — alle Waypoints bleiben suggested
 * (canAdvanceStep3 = true), nur Weiter-Klick.
 */
export interface Step3Input {
	confirmAll?: boolean;
	rejectByName?: string[];
}

/**
 * Step-3-Helper: optional Bestaetigen/Verwerfen, dann Weiter-Klick.
 * Voraussetzung: Wizard ist auf Step 3 (Step3Waypoints gemountet).
 */
export async function fillStep3(page: Page, input: Step3Input = {}): Promise<void> {
	await page.getByTestId('trip-wizard-step3-container').waitFor({ state: 'visible' });

	if (input.confirmAll) {
		// Solange ein Confirm-Button sichtbar ist, ersten klicken — nach Klick
		// verschwindet der Button und folgende Indizes ruecken nicht (kein Reorder),
		// aber `first()` greift immer den ersten verbliebenen Button.
		const confirmBtns = page.getByTestId(/^trip-wizard-step3-confirm-/);
		// Sicherheits-Cap, falls etwas schief laeuft.
		for (let i = 0; i < 50; i++) {
			const count = await confirmBtns.count();
			if (count === 0) break;
			await confirmBtns.first().click();
		}
	}

	if (input.rejectByName && input.rejectByName.length > 0) {
		for (const name of input.rejectByName) {
			const row = page.locator('[data-testid^="trip-wizard-step3-waypoint-row-"]', {
				hasText: name
			});
			const idx = await row.getAttribute('data-waypoint-index');
			if (idx) {
				await page.getByTestId(`trip-wizard-step3-reject-${idx}`).click();
			}
		}
	}

	await page.getByTestId('trip-wizard-next').click();
}
