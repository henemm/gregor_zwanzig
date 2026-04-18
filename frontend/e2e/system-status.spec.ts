import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F75: System-Status → Mein Service', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/settings');
	});

	// --- Sektion 1: Deine Reports ---

	test('shows "Deine Reports" section', async ({ page }) => {
		await expect(page.getByText('Deine Reports')).toBeVisible();
	});

	test('shows next morning report time', async ({ page }) => {
		await expect(page.getByText('Morgen-Report')).toBeVisible();
	});

	test('shows next evening report time', async ({ page }) => {
		await expect(page.getByText('Abend-Report')).toBeVisible();
	});

	test('shows trip checks status', async ({ page }) => {
		await expect(page.getByText('Trip-Checks')).toBeVisible();
	});

	test('does NOT show internal job names', async ({ page }) => {
		await expect(page.getByText('Inbound Command Poll')).not.toBeVisible();
		await expect(page.getByText('Alert Checks')).not.toBeVisible();
	});

	// --- Sektion 2: Dein Account ---

	test('shows "Dein Account" section', async ({ page }) => {
		await expect(page.getByText('Dein Account')).toBeVisible();
	});

	test('shows trip count with link', async ({ page }) => {
		const section = page.locator('[data-testid="account-section"]');
		await expect(section.getByText('Trips')).toBeVisible();
		await expect(section.locator('a[href="/trips"]')).toBeVisible();
	});

	test('shows subscription count with link', async ({ page }) => {
		const section = page.locator('[data-testid="account-section"]');
		await expect(section.getByText('Abos')).toBeVisible();
		await expect(section.locator('a[href="/subscriptions"]')).toBeVisible();
	});

	test('shows location count with link', async ({ page }) => {
		const section = page.locator('[data-testid="account-section"]');
		await expect(section.getByText('Locations')).toBeVisible();
		await expect(section.locator('a[href="/locations"]')).toBeVisible();
	});

	test('shows notification channels', async ({ page }) => {
		// At least one channel indicator should be visible (E-Mail, Signal, or Telegram)
		const section = page.locator('[data-testid="account-section"]');
		const channels = section.locator('[data-testid="channels"]');
		await expect(channels).toBeVisible();
	});

	test('shows weather model per location', async ({ page }) => {
		const section = page.locator('[data-testid="account-section"]');
		const models = section.locator('[data-testid="weather-models"]');
		await expect(models).toBeVisible();
		// Should show provider name (GeoSphere or OpenMeteo)
		await expect(models.getByText(/GeoSphere|OpenMeteo/)).toBeVisible();
	});

	// --- Sektion 3: Verfuegbarkeit ---

	test('shows "Verfügbarkeit" section with single status indicator', async ({ page }) => {
		await expect(page.getByText('Verfügbarkeit')).toBeVisible();
		// Single status — should show one of these
		await expect(page.getByText(/System läuft|Eingeschränkt|Nicht erreichbar/)).toBeVisible();
	});

	test('shows version number', async ({ page }) => {
		await expect(page.getByText(/v\d+\.\d+\.\d+/)).toBeVisible();
	});

	// --- Entfernte Inhalte ---

	test('does NOT show old config table', async ({ page }) => {
		await expect(page.getByText('Aktive Konfiguration des Backends')).not.toBeVisible();
		await expect(page.getByText('Debug-Level')).not.toBeVisible();
		await expect(page.getByText('Breitengrad')).not.toBeVisible();
	});

	test('does NOT show Go/Python health split', async ({ page }) => {
		await expect(page.getByText('API (Go)')).not.toBeVisible();
		await expect(page.getByText('Python Core')).not.toBeVisible();
	});

	test('does NOT show old "Zeitplaner" heading', async ({ page }) => {
		await expect(page.getByText('Geplante Jobs und deren letzter Ausführungsstatus')).not.toBeVisible();
	});
});
