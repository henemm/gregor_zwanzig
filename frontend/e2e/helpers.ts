import { type APIRequestContext, type Page } from '@playwright/test';
import * as path from 'node:path';

/**
 * Login helper — authenticates via the login form and returns the page
 * with a valid session cookie set.
 */
export async function login(page: Page) {
	await page.goto('/');
	if (!page.url().includes('/login')) return;
	const user = process.env.GZ_E2E_USER ?? 'admin';
	const pass = process.env.GZ_E2E_PASS ?? 'test1234';
	await page.fill('input[name="username"]', user);
	await page.fill('input[name="password"]', pass);
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
	// Issue #224: AlertRulesEditor ersetzt Thresholds.
	alertRules?: import('../src/lib/types').AlertRule[];
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

	// --- Alarmregeln (Issue #224 — AlertRulesEditor) --------------------------
	if (input.alertRules) {
		for (const rule of input.alertRules) {
			await page.getByTestId('alert-rules-editor-add').click();
			// Default-Rule wurde hinzugefuegt; auf Edit-Mode wechseln und befuellen.
			const row = page.getByTestId('alert-rule-row').last();
			await row.getByTestId('alert-rule-edit-btn').click();
			const edit = page.getByTestId('alert-rule-edit').last();
			await edit.getByTestId('alert-rule-metric').selectOption(rule.metric);
			await edit.getByTestId('alert-rule-threshold').fill(String(rule.threshold));
			await edit.getByTestId('alert-rule-severity').selectOption(rule.severity);
			await edit.getByTestId('alert-rule-save').click();
		}
	}

	// --- Save ------------------------------------------------------------------
	await page.getByTestId('trip-wizard-save').click();

	if (input.expectSaveSuccess !== false) {
		await page.waitForURL(/\/trips\/[^/]+$/, { timeout: 10000 });
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// #1329 Maßnahme B: geteilter, auto-registrierender E2E-Datenanlage-Helfer.
//
// Spec: docs/specs/modules/fix_1329_e2e_data_hygiene.md
//
// Jede Funktion vergibt einen Namen/ID mit reserviertem Präfix `E2E-GZ-` +
// kollisionsfreiem Zeitstempel/Random-Suffix, ruft die passende REST-API auf
// und registriert die erzeugte ID modul-intern (`registerForCleanup`). Das
// eigentliche Sicherheitsnetz ist `global.teardown.ts` (Präfix-Sweep nach
// Suite-Ende) — `cleanupTracked()` ist ein optionaler Zusatz für Specs, die
// zusätzlich pro Testfall/Datei aufräumen wollen.
// ─────────────────────────────────────────────────────────────────────────────

export const E2E_TEST_PREFIX = 'E2E-GZ-';

type CleanupKind = 'preset' | 'trip' | 'location';

// Reihenfolge referenzierender vor referenzierten Objekten (behebt 409-Waisen,
// AC-3): Presets/Trips referenzieren Orte, nie umgekehrt.
const CLEANUP_ORDER: CleanupKind[] = ['preset', 'trip', 'location'];

const tracked: Record<CleanupKind, Set<string>> = {
	preset: new Set(),
	trip: new Set(),
	location: new Set()
};

function uniqueSuffix(): string {
	return `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

/** Trägt eine ID modul-intern zur späteren Bereinigung ein (s. `cleanupTracked`). */
export function registerForCleanup(kind: CleanupKind, id: string): void {
	tracked[kind].add(id);
}

async function deleteById(request: APIRequestContext, kind: CleanupKind, id: string): Promise<void> {
	const urlPath =
		kind === 'preset'
			? `/api/compare/presets/${id}`
			: kind === 'trip'
				? `/api/trips/${id}`
				: `/api/locations/${id}`;
	try {
		const res = await request.delete(urlPath);
		if (!res.ok() && res.status() !== 404) {
			// DELETE-Fehler werden GELOGGT statt stillschweigend verschluckt
			// (Root Cause #3, Kontext-Dokument #1329) — kein `.catch(() => {})`.
			console.error(`[e2e-cleanup] DELETE ${urlPath} -> HTTP ${res.status()}`);
		}
	} catch (err) {
		console.error(`[e2e-cleanup] DELETE ${urlPath} threw:`, err);
	}
}

/** Löscht alle bislang registrierten Test-Objekte, Reihenfolge Preset/Trip → Ort. */
export async function cleanupTracked(request: APIRequestContext): Promise<void> {
	for (const kind of CLEANUP_ORDER) {
		const ids = Array.from(tracked[kind]);
		tracked[kind].clear();
		for (const id of ids) {
			await deleteById(request, kind, id);
		}
	}
}

export interface TestLocationOpts {
	name?: string;
	lat?: number;
	lon?: number;
	elevation_m?: number;
	region?: string;
	group?: string;
}

export interface TestLocation {
	id: string;
	name: string;
}

/**
 * Stellt sicher, dass ein Name mit dem reservierten Präfix beginnt — idempotent.
 * Aufrufer, die das Präfix selbst schon einbauen (und per exact-Match darauf prüfen),
 * dürfen NICHT doppelt präfixiert werden (`E2E-GZ-E2E-GZ-…`).
 */
function ensureTestPrefix(name: string): string {
	return name.startsWith(E2E_TEST_PREFIX) ? name : `${E2E_TEST_PREFIX}${name}`;
}

/** Legt einen Test-Ort mit reserviertem Präfix an und registriert ihn zur Bereinigung. */
export async function createTestLocation(
	request: APIRequestContext,
	opts: TestLocationOpts = {}
): Promise<TestLocation> {
	const suffix = uniqueSuffix();
	const name = opts.name ? ensureTestPrefix(opts.name) : `${E2E_TEST_PREFIX}Loc-${suffix}`;
	const res = await request.post('/api/locations', {
		data: {
			name,
			lat: opts.lat ?? 47.0 + Math.random() * 0.5,
			lon: opts.lon ?? 11.0 + Math.random() * 0.5,
			...(opts.elevation_m !== undefined ? { elevation_m: opts.elevation_m } : {}),
			...(opts.region !== undefined ? { region: opts.region } : {}),
			...(opts.group !== undefined ? { group: opts.group } : {})
		}
	});
	if (!res.ok()) {
		throw new Error(`createTestLocation fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('location', body.id);
	return { id: body.id, name: body.name };
}

export interface TestComparePresetOpts {
	name?: string;
	locationIds: string[];
	schedule?: 'daily' | 'weekly' | 'manual';
	profil?: string;
	hourFrom?: number;
	hourTo?: number;
	empfaenger?: string[];
}

export interface TestComparePreset {
	id: string;
	name: string;
}

/** Legt ein Test-Compare-Preset mit reserviertem Präfix an und registriert es zur Bereinigung. */
export async function createTestComparePreset(
	request: APIRequestContext,
	opts: TestComparePresetOpts
): Promise<TestComparePreset> {
	const suffix = uniqueSuffix();
	const name = opts.name ? ensureTestPrefix(opts.name) : `${E2E_TEST_PREFIX}Preset-${suffix}`;
	const res = await request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: opts.locationIds,
			schedule: opts.schedule ?? 'daily',
			profil: opts.profil ?? 'wandern',
			hour_from: opts.hourFrom ?? 7,
			hour_to: opts.hourTo ?? 18,
			empfaenger: opts.empfaenger ?? ['urlauber@example.com']
		}
	});
	if (!res.ok()) {
		throw new Error(`createTestComparePreset fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('preset', body.id);
	return { id: body.id, name: body.name };
}

export interface TestTripOpts {
	id?: string;
	name?: string;
	stages?: unknown[];
}

export interface TestTrip {
	id: string;
	name: string;
}

/** Legt einen Test-Trip mit reserviertem Präfix an und registriert ihn zur Bereinigung. */
export async function createTestTrip(request: APIRequestContext, opts: TestTripOpts = {}): Promise<TestTrip> {
	const suffix = uniqueSuffix();
	const id = opts.id ?? `e2e-gz-trip-${suffix}`;
	const name = opts.name ? ensureTestPrefix(opts.name) : `${E2E_TEST_PREFIX}Trip-${suffix}`;
	const res = await request.post('/api/trips', {
		data: { id, name, stages: opts.stages ?? [] }
	});
	if (!res.ok()) {
		throw new Error(`createTestTrip fehlgeschlagen: HTTP ${res.status()} — ${await res.text()}`);
	}
	const body = (await res.json()) as { id: string; name: string };
	registerForCleanup('trip', body.id);
	return { id: body.id, name: body.name };
}
