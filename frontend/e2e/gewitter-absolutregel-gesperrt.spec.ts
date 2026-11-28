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
// #3332 (Spec feat_3332_zustellung_anlegen_trip.md, AC-9) — viertes Nachziehen IN PLACE: im
// Trip-Anlegen besitzt der Reiter Zustellung (wie im Hub) Alarm-Kanaele mit Dringlichkeit, Cooldown und
// Stille Stunden; der Reiter Alarme blendet genau diese Abschnitte aus. Kanal-Schalter und -Stufen werden
// deshalb in der Kanal-Tabelle des Reiters Zustellung bedient, der Schalter „Amtliche Warnungen" bleibt im
// Reiter Alarme. Die Kanal-Tabelle bietet Alarm-Schalter und Stufe nur fuer VERBUNDENE Kanaele; wie
// hub-anlegen-ablauf AN-6 ergaenzt NUR die Profil-Lesung im Browser Test-Kontakte fuer E-Mail, Telegram
// und SMS (kein Profil wird veraendert). Premium-SMS bleibt tarifgebunden und wird nach dem echten Tarif
// gemessen.
//
// Warum im echten Browser: der mobile Mount steckt in einem Wrapper, der nur per
// `style:display` ein-/ausgeblendet wird (TripNewEditor.svelte) — der Kanal-/Stufen-Stand
// lebt im Anlege-Editor (`zustellungStand`, #3332) und wird dem Reiter beim Aufbau
// zurueckgegeben. Ob er einen Tab-Wechsel wirklich ueberlebt und ob Klicks auf
// `<span role="switch">` den Zustand umschalten, koennen SSR- und Kern-Tests
// (node --test) strukturell nicht belegen.

import { test, expect } from '@playwright/test';
import { tippeDatum } from './helpers';
import type { Locator, Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

/** Nur die Profil-LESUNG im Browser: Test-Kontakte, damit E-Mail, Telegram und SMS als verbunden gelten. */
async function kontakteVerbunden(page: Page): Promise<void> {
	await page.route('**/api/auth/profile', async (route) => {
		if (route.request().method() !== 'GET') return route.continue();
		const echt = await route.fetch();
		const profil = (await echt.json()) as Record<string, unknown>;
		await route.fulfill({
			response: echt,
			json: { ...profil, mail_to: profil.mail_to || 'e2e-3332@example.com', telegram_chat_id: 'e2e-3332-test-chat', sms_to: '+491700000000', sms_verified: true, sms_allowed: true }
		});
	});
}

// `/trips/new` bis zum Schritt Zustellung durchklicken (mobiler Pfad, Progressive-Tab-Unlock).
// Kein Trip wird angelegt: der GPX-Upload loest nur den zustandslosen `POST /api/gpx/parse` aus.
async function openNewTripZustellung(page: Page): Promise<{ alarme: Locator; zustellung: Locator }> {
	await kontakteVerbunden(page);
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('#2277 Alarme-Reiter');
	await tippeDatum(page, page.getByTestId('trip-new-date-input'), new Date().toISOString().slice(0, 10));

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
	// Issue #2794 S3a (Teil-PR 2): AlarmeTab und (seit #3332) Reiter Zustellung stehen im Schritt
	// „Zustellung", der nach Besuch von „Wetter" freigeschaltet ist.
	await tabbar.getByRole('tab', { name: /Zustellung/ }).click({ force: true });

	// Harter Surface-Check: ohne ihn waere jedes spaetere `toHaveCount(0)`
	// bedeutungslos (leerer DOM zaehlt auch 0). Scope auf den mobilen Baum.
	const alarme = page.locator('.tn-mobile').getByTestId('alarme-tab');
	await expect(alarme).toBeVisible({ timeout: 15_000 });
	const zustellung = page.locator('.tn-mobile [data-testid="zustellung-tab"][data-context="route"]');
	await expect(zustellung.getByTestId('zustellung-kanal-tabelle')).toBeVisible({ timeout: 15_000 });
	return { alarme, zustellung };
}

// Alarm-Schalter der Kanal-Tabelle: `<span role="switch" aria-checked>` (atoms/Switch.svelte).
function alarmSchalter(scope: Locator, kind: 'telegram' | 'sms' | 'email' | 'premium_sms') {
	return scope.getByTestId(`zustellung-kanal-${kind}-alarm`);
}

// Dringlichkeit: Segment (role=radio, aria-checked), nur bei Alarm an UND verbundenem Kanal.
function stufe(scope: Locator, kind: string, level: 'LOW' | 'MODERATE' | 'HIGH') {
	return scope.getByTestId(`zustellung-kanal-${kind}-dringlichkeit-${level}`);
}

// Amtliche Warnungen: testid auf dem Container (ChannelToggle.svelte), die
// eigentliche Checkbox liegt darin.
function amtlicheWarnungen(scope: Locator) {
	return scope.getByTestId('alerts-tab-official-alert-triggers-toggle').getByRole('checkbox');
}

test.describe('#2277 S1 / #3332: Alarm-Bedienung im Schritt Zustellung von /trips/new', () => {
	test('Mount: AlarmeTab ohne Kanal-Abschnitte, Kanal-Defaults der Neuanlage im Reiter Zustellung', async ({ page }) => {
		const { alarme, zustellung } = await openNewTripZustellung(page);

		await expect(page.getByTestId('alert-rules-editor')).toHaveCount(0);
		// #3332 AC-9: genau eine Bedienstelle je Feld — Kanaele, Cooldown, Stille Stunden nur im Reiter Zustellung.
		for (const s of ['channels', 'cooldown', 'quiet-hours']) await expect(alarme.getByTestId(`alarme-section-${s}`)).toHaveCount(0);
		await expect(alarme.getByTestId('alarme-section-official-warnings')).toHaveCount(1);

		// Issue #2518: Neuanlage-Default = E-Mail + Telegram an, SMS aus.
		await expect.soft(alarmSchalter(zustellung, 'telegram')).toHaveAttribute('aria-checked', 'true');
		await expect.soft(alarmSchalter(zustellung, 'sms')).toHaveAttribute('aria-checked', 'false');
		await expect.soft(alarmSchalter(zustellung, 'email')).toHaveAttribute('aria-checked', 'true');
	});

	test('Kanal-Stufen: aktive Alarm-Zeilen starten auf ihrer Vorbelegung (E-Mail/Telegram gering, SMS mittel, #2801)', async ({ page }) => {
		const { zustellung } = await openNewTripZustellung(page);

		for (const kind of ['telegram', 'email']) {
			await expect.soft(stufe(zustellung, kind, 'LOW')).toHaveAttribute('aria-checked', 'true');
			await expect.soft(stufe(zustellung, kind, 'MODERATE')).toHaveAttribute('aria-checked', 'false');
			await expect.soft(stufe(zustellung, kind, 'HIGH')).toHaveAttribute('aria-checked', 'false');
		}
		// SMS-Alarm aus: keine Stufe wählbar; nach dem Einschalten startet sie auf der
		// SMS-Vorbelegung „mittel" (ADR-0131, #2801).
		await expect(stufe(zustellung, 'sms', 'LOW')).toHaveCount(0);
		await alarmSchalter(zustellung, 'sms').click();
		await expect(stufe(zustellung, 'sms', 'MODERATE')).toHaveAttribute('aria-checked', 'true');
		await expect(stufe(zustellung, 'sms', 'LOW')).toHaveAttribute('aria-checked', 'false');
	});

	test('Premium-SMS wird beim Anlegen angeboten — bedienbar nach Tarif (#2229)', async ({ page }) => {
		const { zustellung } = await openNewTripZustellung(page);
		const res = await page.request.get('/api/auth/profile');
		expect(res.ok(), `GET /api/auth/profile fehlgeschlagen: ${res.status()}`).toBeTruthy();
		const profile = (await res.json()) as { premium_sms_allowed?: boolean };

		await expect(zustellung.getByTestId('zustellung-kanal-premium_sms')).toBeVisible();
		if (profile.premium_sms_allowed === true) {
			// Bedienbar heißt: der Alarm-Schalter steht da (aus) und lässt sich einschalten — sofern das
			// Gerät verbunden ist; sonst nennt die Zeile den Grund (gesperrt).
			const sw = alarmSchalter(zustellung, 'premium_sms');
			if ((await sw.count()) > 0) {
				await expect(sw).toHaveAttribute('aria-checked', 'false');
				await sw.click();
				await expect(sw).toHaveAttribute('aria-checked', 'true');
			} else {
				await expect(zustellung.getByTestId('zustellung-kanal-premium_sms-alarm-gesperrt')).toBeVisible();
			}
		} else {
			// Ohne Tarif: kein Alarm-Schalter, die Zeile nennt den Sperrgrund.
			await expect(alarmSchalter(zustellung, 'premium_sms')).toHaveCount(0);
			await expect(zustellung.getByTestId('zustellung-kanal-premium_sms-alarm-gesperrt')).toBeVisible({ timeout: 10_000 });
		}
	});

	test('Kanal umschalten: SMS-Alarm an und wieder aus', async ({ page }) => {
		const { zustellung } = await openNewTripZustellung(page);
		// Issue #2518: E-Mail startet in der Neuanlage an, SMS aus.
		const sw = alarmSchalter(zustellung, 'sms');

		await expect(sw).toHaveAttribute('aria-checked', 'false');
		await sw.click();
		await expect(sw).toHaveAttribute('aria-checked', 'true');
		await sw.click();
		await expect(sw).toHaveAttribute('aria-checked', 'false');
	});

	test('Kanal-Stufe und Amtliche Warnungen lassen sich setzen', async ({ page }) => {
		const { alarme, zustellung } = await openNewTripZustellung(page);

		await alarmSchalter(zustellung, 'sms').click();
		await stufe(zustellung, 'sms', 'HIGH').click();
		await expect(stufe(zustellung, 'sms', 'HIGH')).toHaveAttribute('aria-checked', 'true');
		await expect(stufe(zustellung, 'sms', 'LOW')).toHaveAttribute('aria-checked', 'false');

		// #3047 Runde 7 (Spec feat_3047 Nachtrag, PO 2026-11-16, löst #1258 AC-4 ab): neue Trips starten mit
		// amtlichen Warnungen im Briefing und als Alarm — der Schalter steht an und lässt sich ausschalten.
		const cb = amtlicheWarnungen(alarme);
		await expect(cb).toBeChecked();
		await cb.click();
		await expect(cb).not.toBeChecked();
		await cb.click();
		await expect(cb).toBeChecked();
	});

	test('Eingaben ueberleben den Tab-Wechsel Zustellung → Route → Zustellung', async ({ page }) => {
		const { alarme, zustellung } = await openNewTripZustellung(page);

		await alarmSchalter(zustellung, 'sms').click();
		await expect(alarmSchalter(zustellung, 'sms')).toHaveAttribute('aria-checked', 'true');
		await stufe(zustellung, 'sms', 'HIGH').click();
		await expect(stufe(zustellung, 'sms', 'HIGH')).toHaveAttribute('aria-checked', 'true');
		// #3047 Runde 7 (PO 2026-11-16): Neuanlage startet mit amtlichen Warnungen an — die Eingabe ist das Ausschalten.
		await expect(amtlicheWarnungen(alarme)).toBeChecked();
		await amtlicheWarnungen(alarme).click();
		await expect(amtlicheWarnungen(alarme)).not.toBeChecked();

		const tabbar = page.getByTestId('tn-mobile-tabbar');
		await tabbar.getByRole('tab', { name: /Route/ }).click({ force: true });
		await expect(alarme).toBeHidden();
		await tabbar.getByRole('tab', { name: /Zustellung/ }).click({ force: true });
		await expect(alarme).toBeVisible();

		await expect.soft(alarmSchalter(zustellung, 'sms')).toHaveAttribute('aria-checked', 'true');
		await expect.soft(stufe(zustellung, 'sms', 'HIGH')).toHaveAttribute('aria-checked', 'true');
		await expect.soft(stufe(zustellung, 'sms', 'LOW')).toHaveAttribute('aria-checked', 'false');
		await expect.soft(amtlicheWarnungen(alarme)).not.toBeChecked();
	});
});
