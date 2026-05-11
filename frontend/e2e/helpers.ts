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

/**
 * Eingabe-Vertrag fuer Trip-Wizard Step 4 (Sub-Spec #164 §8/§10).
 *
 * Default-Verhalten: keine Aenderungen — alle Toggles/Zeiten/Schwellwerte
 * bleiben auf defaultBriefingConfig. Helper klickt nur den Save-Button und
 * wartet auf Redirect nach `/trips/{id}` (sofern `expectSaveSuccess !== false`).
 *
 * SMS-Channel ist nicht konfigurierbar (disabled in der UI) und daher nicht
 * Teil des Channel-Inputs.
 */
export interface Step4Input {
	channels?: {
		email?: boolean;
		signal?: boolean;
		telegram?: boolean;
		// sms: nicht konfigurierbar (disabled)
	};
	reports?: {
		morning?: { enabled?: boolean; time?: string };
		evening?: { enabled?: boolean; time?: string };
	};
	thresholds?: {
		gust_kmh?: number | null;
		precip_mm?: number | null;
		thunder_level?: 'NONE' | 'MED' | 'HIGH' | null;
		snow_line_m?: number | null;
	};
	/** default: true — wartet auf Redirect nach Save (`/trips/{id}`) */
	expectSaveSuccess?: boolean;
}

/**
 * Step-4-Helper: optional Toggles/Zeiten/Schwellwerte setzen, dann Save klicken.
 * Voraussetzung: Wizard ist auf Step 4 (Step4Briefings gemountet).
 * Wartet zunaechst auf `trip-wizard-step4-container`.
 */
export async function fillStep4(page: Page, input: Step4Input = {}): Promise<void> {
	await page.getByTestId('trip-wizard-step4-container').waitFor({ state: 'visible' });

	// --- Channels --------------------------------------------------------------
	if (input.channels) {
		const channels: Array<['email' | 'signal' | 'telegram', boolean | undefined]> = [
			['email', input.channels.email],
			['signal', input.channels.signal],
			['telegram', input.channels.telegram]
		];
		for (const [ch, target] of channels) {
			if (target === undefined) continue;
			const toggle = page
				.getByTestId(`trip-wizard-step4-channel-${ch}`)
				.locator('input[type="checkbox"]');
			const current = await toggle.isChecked();
			if (current !== target) {
				await toggle.click();
			}
		}
	}

	// --- Report-Toggles + Zeiten ----------------------------------------------
	if (input.reports) {
		const reports: Array<['morning' | 'evening', { enabled?: boolean; time?: string } | undefined]> =
			[
				['morning', input.reports.morning],
				['evening', input.reports.evening]
			];
		for (const [rep, cfg] of reports) {
			if (!cfg) continue;
			if (cfg.enabled !== undefined) {
				const toggle = page.getByTestId(`trip-wizard-step4-report-${rep}-toggle`);
				const current = await toggle.isChecked();
				if (current !== cfg.enabled) {
					await toggle.click();
				}
			}
			if (cfg.time !== undefined) {
				await page.getByTestId(`trip-wizard-step4-report-${rep}-time`).fill(cfg.time);
			}
		}
	}

	// --- Schwellwerte ----------------------------------------------------------
	if (input.thresholds) {
		const { gust_kmh, precip_mm, thunder_level, snow_line_m } = input.thresholds;
		if (gust_kmh !== undefined) {
			await page
				.getByTestId('trip-wizard-step4-threshold-gust')
				.fill(gust_kmh === null ? '' : String(gust_kmh));
		}
		if (precip_mm !== undefined) {
			await page
				.getByTestId('trip-wizard-step4-threshold-precip')
				.fill(precip_mm === null ? '' : String(precip_mm));
		}
		if (thunder_level !== undefined) {
			await page
				.getByTestId('trip-wizard-step4-threshold-thunder')
				.selectOption(thunder_level === null ? '' : thunder_level);
		}
		if (snow_line_m !== undefined) {
			await page
				.getByTestId('trip-wizard-step4-threshold-snow')
				.fill(snow_line_m === null ? '' : String(snow_line_m));
		}
	}

	// --- Save ------------------------------------------------------------------
	await page.getByTestId('trip-wizard-save').click();

	if (input.expectSaveSuccess !== false) {
		await page.waitForURL(/\/trips\/[^/]+$/, { timeout: 10000 });
	}
}
