// E2E — #2277 Scheibe S1: der Alarme-Reiter von `/trips/new` zeigt den geteilten
// `AlarmeTab` (context="route", createMode) statt der Alt-Komponente
// `AlertRulesEditor`.
//
// Spec: docs/specs/modules/fix_2277_s1_alarme_tab_route.md
//
// Diese Datei war bis #1895 der Sperr-Waechter aus #1488 Scheibe A („fuer Gewitter
// ist der Absolut-Modus gesperrt"). Sie wurde in #1895 Schritt 1 IN PLACE zum
// Abwesenheits-Waechter der Modus-Auswahl umgeschrieben und in Schritt 2 — wieder
// IN PLACE — auf den Rueckbau von Δ-Schwelle und Zeitfenster der Alarmregel-Karte
// nachgezogen.
//
// #2277 S1 hat den `AlertRulesEditor`-Mount unter `/trips/new` → Alerts durch den
// geteilten `AlarmeTab` ersetzt. Die Alarmregel-Karte, die Schritt 1 und 2 hier
// bewachten, gibt es an dieser Stelle nicht mehr; ihre Zusicherungen haben kein
// Subjekt mehr und entfallen mit ihr. Die Datei wird darum ein drittes Mal IN
// PLACE umgeschrieben und prueft jetzt das NEUE Bedienfeld: Kanal-Schalter
// (inkl. Premium-SMS), Kanal-Schwellen, Amtliche-Warnungen-Schalter und das
// Ueberleben der Eingaben beim Tab-Wechsel. Der Dateiname bleibt, weil die Datei
// in der E2E-Ratsche `.github/ci_e2e_specs.txt` (Zeile 305) steht und im
// `e2e`-Check der CI-Ampel laeuft. Ein neuer Dateiname haette den
// Ratschen-Eintrag entwertet — „Ratsche leeren macht den abhaengigen Test
// vakuum-gruen".
//
// Warum im echten Browser: der mobile Mount steckt in einem Wrapper, der nur per
// `style:display` ein-/ausgeblendet wird (TripNewEditor.svelte, #2277 S1) — der
// Kanal-/Schwellen-Stand lebt als lokaler State im gemounteten AlarmeTab und im
// Schatten-State der Anlege-Seite. Ob er einen Tab-Wechsel wirklich ueberlebt und
// ob Klicks auf `<span role="switch">` den Zustand umschalten, koennen SSR- und
// Kern-Tests (node --test) strukturell nicht belegen.
//
// Premium-SMS: die Zeile ist beim Anlegen IMMER sichtbar (#2229), der Schalter
// aber tarifgebunden (premiumSmsAlarmGate.ts — nur `premium_sms_allowed === true`
// macht ihn bedienbar). Der Test misst den Tarif des angemeldeten Nutzers ueber
// `/api/auth/profile` und prueft den dazu passenden Zustand — bedienbar ODER
// gesperrt mit Begruendung. Umschalten und Persistenz laufen deshalb ueber den
// tariffreien Kanal E-Mail, damit sie in jeder Umgebung begehbar sind.

import { test, expect } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

// `/trips/new` bis zum Alerts-Tab durchklicken. Uebernommen aus dem bereits
// funktionierenden `issue-776-metrics-toggle.spec.ts::openNewTripZeitplan()`
// (mobiler Pfad, Progressive-Tab-Unlock) — einziger zusaetzlicher Schritt ist der
// Klick auf „Alerts". Kein Trip wird angelegt: der GPX-Upload loest nur den
// zustandslosen `POST /api/gpx/parse` aus.
async function openNewTripAlerts(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('#2277 Alarme-Reiter');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	// IMMER den ersten verbleibenden offenen Datei-Input frisch aufloesen: eine
	// Etappe mit gesetztem GPX verliert ihren Input komplett aus dem DOM
	// (TripNewEditor.svelte `{#if s.gpx}`), ein fixierter Index zeigt danach ins Leere.
	const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
	for (let i = 0; i < stageCount; i++) {
		const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
		await Promise.all([
			page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
			input.setInputFiles(gpx)
		]);
		await page.waitForTimeout(600);
	}

	await tabbar.getByRole('tab', { name: /Wetter/ }).click({ force: true });
	await tabbar.getByRole('tab', { name: /Zeitplan/ }).click({ force: true });
	await tabbar.getByRole('tab', { name: /Alerts/ }).click({ force: true });

	// Harter Surface-Check: ohne ihn waere jedes spaetere `toHaveCount(0)`
	// bedeutungslos (leerer DOM zaehlt auch 0). Scope auf den mobilen Baum.
	const scope = page.locator('.tn-mobile').getByTestId('alarme-tab');
	await expect(scope).toBeVisible({ timeout: 15_000 });
	return scope;
}

// Kanal-Schalter: die testid sitzt auf dem Container, der Schalter selbst ist ein
// `<span role="switch" aria-checked>` (atoms/Switch.svelte) — KEINE Checkbox.
function kanalSchalter(scope: Locator, kind: 'telegram' | 'sms' | 'email' | 'premium_sms') {
	return scope.getByTestId(`alert-channel-toggle-${kind}`).getByRole('switch');
}

function schwelle(scope: Locator, kind: string, level: 'LOW' | 'MODERATE' | 'HIGH') {
	return scope.getByTestId(`alert-channel-threshold-${kind}-${level}`);
}

// Amtliche Warnungen: testid auf dem Container (ChannelToggle.svelte), die
// eigentliche Checkbox liegt darin.
function amtlicheWarnungen(scope: Locator) {
	return scope.getByTestId('alerts-tab-official-alert-triggers-toggle').getByRole('checkbox');
}

test.describe('#2277 S1: AlarmeTab im Alarme-Reiter von /trips/new', () => {
	test('Mount: AlarmeTab statt AlertRulesEditor, Kanal-Defaults der Neuanlage', async ({ page }) => {
		const scope = await openNewTripAlerts(page);

		await expect(page.getByTestId('alert-rules-editor')).toHaveCount(0);

		await expect.soft(kanalSchalter(scope, 'telegram')).toHaveAttribute('aria-checked', 'true');
		await expect.soft(kanalSchalter(scope, 'sms')).toHaveAttribute('aria-checked', 'true');
		await expect.soft(kanalSchalter(scope, 'email')).toHaveAttribute('aria-checked', 'false');
		await expect.soft(kanalSchalter(scope, 'premium_sms')).toHaveAttribute('aria-checked', 'false');
	});

	test('Kanal-Schwellen: jede Zeile startet auf LOW', async ({ page }) => {
		const scope = await openNewTripAlerts(page);

		for (const kind of ['telegram', 'sms', 'email', 'premium_sms']) {
			await expect.soft(schwelle(scope, kind, 'LOW')).toHaveAttribute('aria-pressed', 'true');
			await expect.soft(schwelle(scope, kind, 'MODERATE')).toHaveAttribute('aria-pressed', 'false');
			await expect.soft(schwelle(scope, kind, 'HIGH')).toHaveAttribute('aria-pressed', 'false');
		}
	});

	test('Premium-SMS wird beim Anlegen angeboten — bedienbar nach Tarif (#2229)', async ({ page }) => {
		const scope = await openNewTripAlerts(page);
		const res = await page.request.get('/api/auth/profile');
		expect(res.ok(), `GET /api/auth/profile fehlgeschlagen: ${res.status()}`).toBeTruthy();
		const profile = (await res.json()) as { premium_sms_allowed?: boolean };

		const sw = kanalSchalter(scope, 'premium_sms');
		await expect(scope.getByTestId('alert-channel-row-premium_sms')).toBeVisible();
		await expect(sw).toHaveAttribute('aria-checked', 'false');

		if (profile.premium_sms_allowed === true) {
			await expect(sw).not.toHaveAttribute('aria-disabled', 'true', { timeout: 10_000 });
			await sw.click();
			await expect(sw).toHaveAttribute('aria-checked', 'true');
		} else {
			await expect(scope.getByTestId('alert-channel-disabled-hint-premium_sms')).toContainText(
				'ab Level Premium',
				{ timeout: 10_000 }
			);
			await expect(sw).toHaveAttribute('aria-disabled', 'true');
			await sw.click({ force: true });
			await expect(sw).toHaveAttribute('aria-checked', 'false');
		}
	});

	test('Kanal umschalten: E-Mail an und wieder aus', async ({ page }) => {
		const scope = await openNewTripAlerts(page);
		const sw = kanalSchalter(scope, 'email');

		await expect(sw).toHaveAttribute('aria-checked', 'false');
		await sw.click();
		await expect(sw).toHaveAttribute('aria-checked', 'true');
		await sw.click();
		await expect(sw).toHaveAttribute('aria-checked', 'false');
	});

	test('Kanal-Schwelle und Amtliche Warnungen lassen sich setzen', async ({ page }) => {
		const scope = await openNewTripAlerts(page);

		await schwelle(scope, 'sms', 'HIGH').click();
		await expect(schwelle(scope, 'sms', 'HIGH')).toHaveAttribute('aria-pressed', 'true');
		await expect(schwelle(scope, 'sms', 'LOW')).toHaveAttribute('aria-pressed', 'false');

		const cb = amtlicheWarnungen(scope);
		await expect(cb).not.toBeChecked();
		await cb.click();
		await expect(cb).toBeChecked();
	});

	test('Eingaben ueberleben den Tab-Wechsel Alerts → Route → Alerts', async ({ page }) => {
		const scope = await openNewTripAlerts(page);

		await kanalSchalter(scope, 'email').click();
		await expect(kanalSchalter(scope, 'email')).toHaveAttribute('aria-checked', 'true');
		await schwelle(scope, 'sms', 'HIGH').click();
		await expect(schwelle(scope, 'sms', 'HIGH')).toHaveAttribute('aria-pressed', 'true');
		await amtlicheWarnungen(scope).click();
		await expect(amtlicheWarnungen(scope)).toBeChecked();

		const tabbar = page.getByTestId('tn-mobile-tabbar');
		await tabbar.getByRole('tab', { name: /Route/ }).click({ force: true });
		await expect(scope).toBeHidden();
		await tabbar.getByRole('tab', { name: /Alerts/ }).click({ force: true });
		await expect(scope).toBeVisible();

		await expect.soft(kanalSchalter(scope, 'email')).toHaveAttribute('aria-checked', 'true');
		await expect.soft(schwelle(scope, 'sms', 'HIGH')).toHaveAttribute('aria-pressed', 'true');
		await expect.soft(schwelle(scope, 'sms', 'LOW')).toHaveAttribute('aria-pressed', 'false');
		await expect.soft(amtlicheWarnungen(scope)).toBeChecked();
	});
});
