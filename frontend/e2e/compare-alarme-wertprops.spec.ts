// E2E — Issue #2276 Scheibe S6c (Epic #2345): die Alarme-Flaeche des
// Ortsvergleichs arbeitet auf reinen WERTPROPS + Rueckrufen statt auf dem
// Zustandsobjekt `wiz`. Nachweis am Wirkort: Browser.
//
// Spec: docs/specs/modules/rework_2276_s6c_alarme.md
//   AC-2  Verhaltensgleichheit am Hub — Amtliche Warnungen, Metrik-Schwellen,
//         Kanaele, Kanal-Schwellen, Kurzstil, Cooldown, Stille Stunden und
//         Radar-Alarm lassen sich setzen, ueberstehen Speichern und Neuladen,
//         und es entsteht weiterhin genau EIN PUT je Aenderung.
//
// 🔴 CHARAKTERISIERUNG, nicht RED. Eine Umstellung auf Wertprops darf das
// sichtbare Verhalten NICHT aendern — dieser Test ist deshalb schon vor der
// Implementierung gruen und muss es danach bleiben. Sein Wert liegt in den
// Mutations-Gegenproben:
//   * ein Rueckruf fehlt am Hub-Mount   -> die Geste verpufft, nichts wird
//     gespeichert                                                      -> rot
//   * ein Wertprop fehlt am Hub-Mount   -> die Flaeche zeigt nach dem Neuladen
//     den Vorgabewert statt des Standes                                -> rot
//   * `zonenBezug` fehlt                -> die Stillen Stunden nennen die
//     falsche Bezugsgroesse                                            -> rot
// KEIN Kern-Test faengt diese drei: die Kernsuite ist SSR-only
// (`generate: 'server'`, kein DOM), `$effect` und Ereignisse laufen dort nie.
// Die Verdrahtungs-Zusicherungen fuer die beiden UNBEWACHTEN Mounts auf
// `/compare/new` stehen im Kern
// (src/lib/components/shared/__tests__/compare_alarme_wertprops.test.ts,
// AC-3/AC-4) — eine zweite E2E-Spec dafuer waere gegen die Scheiben-Disziplin.
//
// Laeuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung ueber den
// gespeicherten storageState aus global.setup.ts. Presets tragen das Praefix
// E2E-GZ-, damit global.teardown.ts Reste raeumt; afterEach loescht sie direkt.
// Die Aufnahme in .github/ci_e2e_specs.txt macht die Implementierung — sie
// setzt einen frischen Filter-B-Beleg (3x gruen im Zielverbund) voraus.

import { test, expect, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX } from './helpers';

let angelegt: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of angelegt) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Aufraeumen ist nicht testkritisch */
		}
	}
	angelegt = [];
});

async function legeVergleichAn(page: Page): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			// Seed-Orte aus global.setup.ts.
			name: `${E2E_TEST_PREFIX}Alarme Wertprops ${Date.now()}`,
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['alarme-wertprops@example.com'],
			radar_alert_enabled: false,
			send_telegram: false,
			display_config: { active_metrics: ['wind_max_kmh'], telegram_style: 'rich' }
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	angelegt.push(body.id);
	return body.id as string;
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

const dc = (body: Record<string, unknown>) => (body.display_config as Record<string, unknown>) ?? {};

/** Zaehlt die PUTs auf genau diesen Vergleich. */
function zaehlePuts(page: Page, id: string): Request[] {
	const pfad = `/api/compare/presets/${id}`;
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
}

async function oeffneAlarme(page: Page, id: string) {
	await page.goto(`/compare/${id}`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
	const reiter = page.locator('[data-testid="alarme-tab"]').first();
	await expect(reiter, 'Der Alarme-Reiter muss erscheinen').toBeVisible({ timeout: 10_000 });
	return reiter;
}

async function warteAufGespeichert(page: Page) {
	const anzeige = page.locator('[data-testid="save-indicator"]');
	await expect(anzeige).toHaveAttribute('data-state', 'idle', { timeout: 15_000 });
}

test.describe('Ortsvergleich · Alarme auf Wertprops (#2276 S6c)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-2: Amtliche Warnungen + Radar-Alarm wirken, genau ein PUT je Aenderung, Stand ueberlebt das Neuladen', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const puts = zaehlePuts(page, id);
		await oeffneAlarme(page, id);
		expect(puts.length, 'Vorbedingung: das Oeffnen des Reiters speichert nichts').toBe(0);

		const amtlich = page
			.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]')
			.first();
		const radar = page
			.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]')
			.first();

		await radar.check();
		await expect(radar, 'AC-2 FAIL: der Radar-Schalter nimmt die Geste nicht an.').toBeChecked();
		await warteAufGespeichert(page);
		expect(puts.length, 'AC-2 FAIL: genau EIN PUT je Alarm-Aenderung').toBe(1);
		expect(
			(await serverStand(page, id)).radar_alert_enabled,
			'AC-2 FAIL: der Radar-Alarm ist nicht gespeichert worden — fehlt der Rueckruf am ' +
				'Mount, verpufft die Geste.'
		).toBe(true);

		const warVorher = await amtlich.isChecked();
		await amtlich.setChecked(!warVorher);
		await warteAufGespeichert(page);
		await expect
			.poll(
				async () =>
					((await serverStand(page, id)).official_warnings as { enabled?: boolean } | undefined)
						?.enabled,
				{ timeout: 15_000, message: 'AC-2 FAIL: „Amtliche Warnungen" wurde nicht gespeichert.' }
			)
			.toBe(!warVorher);

		await page.reload();
		await oeffneAlarme(page, id);
		await expect(
			page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first(),
			'AC-2 FAIL: der Radar-Alarm steht nach dem Neuladen wieder auf „aus" — dann zeigt ' +
				'die Flaeche den Vorgabewert statt des gespeicherten Standes.'
		).toBeChecked();
		await expect(
			page
				.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]')
				.first(),
			'AC-2 FAIL: „Amtliche Warnungen" steht nach dem Neuladen wieder auf dem alten Wert.'
		).toBeChecked({ checked: !warVorher });
	});

	test('AC-2: Kanal, Kanal-Schwelle und Telegram-Kurzstil wirken und ueberstehen das Neuladen', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		await oeffneAlarme(page, id);

		const telegram = page
			.locator('[data-testid="alert-channel-toggle-telegram"] input[type="checkbox"]')
			.first();
		await telegram.check();
		await warteAufGespeichert(page);
		await expect
			.poll(async () => (await serverStand(page, id)).send_telegram, {
				timeout: 15_000,
				message: 'AC-2 FAIL: der Telegram-Kanal wurde nicht gespeichert.'
			})
			.toBe(true);

		// Kanal-Schwelle: die Stufen-Auswahl steht in derselben Zeile.
		const schwelle = page.locator('[data-testid="alert-channel-threshold-telegram-hoch"]').first();
		await schwelle.click();
		await warteAufGespeichert(page);
		await expect
			.poll(
				async () =>
					(
						(await serverStand(page, id)).alert_channel_thresholds as
							| Record<string, string>
							| undefined
					)?.telegram,
				{ timeout: 15_000, message: 'AC-2 FAIL: die Kanal-Schwelle wurde nicht gespeichert.' }
			)
			.toBe('hoch');

		// Kurzstil-Schalter — nur im Vergleich sichtbar, nur mit aktivem Telegram bedienbar.
		const kurzstil = page
			.locator('[data-testid="telegram-kurzstil-toggle"] input[type="checkbox"]')
			.first();
		await expect(
			kurzstil,
			'AC-2 FAIL: der Kurzstil-Schalter fehlt im Alarme-Reiter des Vergleichs.'
		).toBeVisible();
		await kurzstil.check();
		await warteAufGespeichert(page);
		await expect
			.poll(async () => dc(await serverStand(page, id)).telegram_style, {
				timeout: 15_000,
				message: 'AC-2 FAIL: der Telegram-Kurzstil wurde nicht gespeichert.'
			})
			.toBe('kurzform');

		await page.reload();
		await oeffneAlarme(page, id);
		await expect(
			page.locator('[data-testid="alert-channel-toggle-telegram"] input[type="checkbox"]').first(),
			'AC-2 FAIL: der Telegram-Kanal ist nach dem Neuladen wieder aus.'
		).toBeChecked();
		await expect(
			page.locator('[data-testid="telegram-kurzstil-toggle"] input[type="checkbox"]').first(),
			'AC-2 FAIL: der Kurzstil ist nach dem Neuladen wieder aus.'
		).toBeChecked();
	});

	test('AC-2: Empfindlichkeit, Cooldown und Stille Stunden wirken und ueberstehen das Neuladen', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		await oeffneAlarme(page, id);

		// Empfindlichkeit fuer alle gewaehlten Groessen auf einmal.
		await page.locator('[data-testid="alert-quickset-hoch"]').first().click();
		await warteAufGespeichert(page);
		await expect
			.poll(
				async () =>
					Object.values(
						(dc(await serverStand(page, id)).metric_alert_levels as Record<string, string>) ?? {}
					),
				{
					timeout: 15_000,
					message:
						'AC-2 FAIL: die Alarm-Empfindlichkeit wurde nicht gespeichert — fehlt ' +
						'`onMetricLevelChange` am Mount, verpufft die Geste.'
				}
			)
			.toContain('hoch');

		const cooldown = page.locator('[data-testid="alert-cooldown-input"]').first();
		await cooldown.fill('45');
		await cooldown.blur();
		await warteAufGespeichert(page);
		await expect
			.poll(async () => (await serverStand(page, id)).alert_cooldown_minutes, {
				timeout: 15_000,
				message: 'AC-2 FAIL: der Cooldown wurde nicht gespeichert (Funktions-Bindung defekt?).'
			})
			.toBe(45);

		const stilleAn = page
			.locator('[data-testid="alert-quiet-hours-toggle"] input[type="checkbox"]')
			.first();
		if (!(await stilleAn.isChecked())) await stilleAn.check();
		const von = page.locator('[data-testid="alert-quiet-from"]').first();
		const bis = page.locator('[data-testid="alert-quiet-to"]').first();
		await von.fill('23:00');
		await bis.fill('06:00');
		await bis.blur();
		await warteAufGespeichert(page);
		await expect
			.poll(
				async () => {
					const stand = await serverStand(page, id);
					return `${stand.alert_quiet_from ?? '—'}/${stand.alert_quiet_to ?? '—'}`;
				},
				{
					timeout: 15_000,
					message:
						'AC-2 FAIL: die Stillen Stunden wurden nicht gespeichert — die zweiwegige ' +
						'Bindung ist in S6c eine Funktions-Bindung geworden, genau hier faellt ein ' +
						'Fehler darin auf.'
				}
			)
			.toContain('23:00');

		await page.reload();
		const reiter = await oeffneAlarme(page, id);
		await expect(
			page.locator('[data-testid="alert-cooldown-input"]').first(),
			'AC-2 FAIL: der Cooldown steht nach dem Neuladen wieder auf dem Vorgabewert.'
		).toHaveValue('45');
		await expect(
			page.locator('[data-testid="alert-quiet-from"]').first(),
			'AC-2 FAIL: die Stillen Stunden stehen nach dem Neuladen wieder auf dem Vorgabewert.'
		).toHaveValue('23:00');
		await expect(
			reiter.locator('[data-testid="alert-quiet-hours-card"]'),
			'AC-2 FAIL: die Stillen Stunden nennen nicht den Bezug des Ortsvergleichs — die ' +
				'Prop `zonenBezug` fehlt oder traegt den Trip-Vorgabewert „der Tour".'
		).toContainText('des ersten Orts');
	});

	test('AC-2: eine Alarm-Geste laesst die uebrigen Einstellungen unangetastet', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const vorher = await serverStand(page, id);
		await oeffneAlarme(page, id);

		await page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first().check();
		await warteAufGespeichert(page);

		const nachher = await serverStand(page, id);
		expect(nachher.radar_alert_enabled, 'Vorbedingung: die Geste muss gespeichert sein').toBe(true);
		expect(nachher.empfaenger, 'AC-2 FAIL: die Empfaenger haben sich veraendert.').toEqual(
			vorher.empfaenger
		);
		expect(nachher.location_ids, 'AC-2 FAIL: die Orte haben sich veraendert.').toEqual(
			vorher.location_ids
		);
		expect(
			dc(nachher).active_metrics,
			'AC-2 FAIL: die Metrik-Auswahl wurde mitgeschrieben.'
		).toEqual(dc(vorher).active_metrics);
	});
});
