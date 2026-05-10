import { type Page } from '@playwright/test';

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
