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
// #1373 / ADR-0037: `display_config.active_metrics` wird in ZWEI Formen
// gespeichert (Kurzform "wind_max_kmh" und Paar {metric_id, aggregation}).
// Der Vergleich der Nachbar-Einstellungen laeuft deshalb ueber die
// Lesenormalisierung DES PRODUKTS, nicht ueber eigene Zeichenketten-Logik.
import {
	normalizeStoredActiveMetrics,
	toCompareSelectionEntries,
	type CompareSelectionEntry
} from '../src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts';

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

/** Der Metrik-Katalog des Servers — Schluesselbund fuer die Lesenormalisierung
 *  (dieselbe Quelle, aus der die Oberflaeche ihn zieht). */
async function metrikKatalog(page: Page): Promise<CompareSelectionEntry[]> {
	const res = await page.request.get('/api/compare/metrics');
	expect(res.ok(), 'GET /api/compare/metrics HTTP ' + res.status()).toBeTruthy();
	const katalog = toCompareSelectionEntries(await res.json());
	expect(
		katalog.length,
		'Vorbedingung: der Metrik-Katalog ist leer — ohne ihn kann die Paar-Form nicht ' +
			'aufgeloest werden und der Vergleich unten wuerde Formen statt Auswahl pruefen.'
	).toBeGreaterThan(0);
	return katalog;
}

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

		// AlertChannelPicker.svelte:148 rendert in diesem Container das Atom
		// <Switch> (atoms/Switch.svelte: <span role="switch" aria-checked> mit
		// onclick) — KEIN <input type="checkbox">. Deshalb Klick-Geste und
		// aria-checked statt .check()/toBeChecked(). Der Radar-/Kurzstil-Schalter
		// weiter unten benutzt dagegen das Checkbox-Atom und bleibt unveraendert.
		const telegram = page
			.locator('[data-testid="alert-channel-toggle-telegram"]')
			.first()
			.getByRole('switch');
		await expect(
			telegram,
			'Vorbedingung: der Telegram-Kanal startet aus (send_telegram: false bei der Anlage) — ' +
				'ein Klick schaltet ihn sonst AUS statt AN.'
		).toHaveAttribute('aria-checked', 'false');
		await telegram.click();
		await expect(
			telegram,
			'AC-2 FAIL: der Telegram-Schalter nimmt die Geste nicht an.'
		).toHaveAttribute('aria-checked', 'true');
		await warteAufGespeichert(page);
		await expect
			.poll(async () => (await serverStand(page, id)).send_telegram, {
				timeout: 15_000,
				message: 'AC-2 FAIL: der Telegram-Kanal wurde nicht gespeichert.'
			})
			.toBe(true);

		// Kanal-Schwelle: die Stufen-Auswahl steht in derselben Zeile. Die Stufen
		// heissen LOW/MODERATE/HIGH (alarme-tab/alertChannelState.ts:95) — „hoch"
		// ist nur die Beschriftung, nicht der Wert.
		const schwelle = page.locator('[data-testid="alert-channel-threshold-telegram-HIGH"]').first();
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
			.toBe('HIGH');

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
			page
				.locator('[data-testid="alert-channel-toggle-telegram"]')
				.first()
				.getByRole('switch'),
			'AC-2 FAIL: der Telegram-Kanal ist nach dem Neuladen wieder aus.'
		).toHaveAttribute('aria-checked', 'true');
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

		// Empfindlichkeit fuer alle gewaehlten Groessen auf einmal. Die Stufen des
		// Quicksets sind off/entspannt/standard/sensibel (SensLevel, types.ts:73;
		// AlertMetricLevelTable.svelte:19) — „sensibel" ist die scharfe Stufe und
		// weicht vom Startwert ab, die Geste ist also sichtbar.
		await page.locator('[data-testid="alert-quickset-sensibel"]').first().click();
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
			.toContain('sensibel');

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

		// AlertQuietHoursCard.svelte:36 gibt die Testid als Rest-Prop an <Checkbox>,
		// und Checkbox.svelte spreizt sie auf das <input type="checkbox"> selbst —
		// die Testid SITZT also auf dem Eingabefeld, ein Nachkommen-Selektor traefe
		// hier nie.
		const stilleAn = page.locator('[data-testid="alert-quiet-hours-toggle"]').first();
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
				'Prop `zonenBezug` fehlt oder traegt den Trip-Vorgabewert „der Trip".'
		).toContainText('des ersten Orts');
	});

	test('AC-2: eine Alarm-Geste laesst die uebrigen Einstellungen unangetastet', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const katalog = await metrikKatalog(page);
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
		// Metrik-Auswahl SEMANTISCH, nicht byteweise: der Speicherweg fuehrt die
		// Auswahl dabei von der Kurzform ("wind_max_kmh") in die Paar-Form
		// ({metric_id:"wind", aggregation:"max"}) ueber. Das ist die gewollte
		// Lesenormalisierung #1373 / ADR-0037 (alarmeVergleichSpeicherung.ts:68-73,
		// src/app/models.py:864-865: beide Formen bleiben dauerhaft gueltig) — sie
		// existiert, um Datenverlust an der Metrik-Auswahl zu VERHINDERN. Beide
		// Staende laufen deshalb durch dieselbe Normalisierung des Produkts und
		// werden als Auswahl verglichen. Verschwindet ein Eintrag, wird die Auswahl
		// leer oder kommt einer hinzu, faellt das weiterhin auf.
		const auswahlVorher = normalizeStoredActiveMetrics(dc(vorher).active_metrics, katalog) ?? [];
		const auswahlNachher = normalizeStoredActiveMetrics(dc(nachher).active_metrics, katalog) ?? [];
		expect(
			auswahlVorher.length,
			'Vorbedingung: der Ausgangsstand hat eine nicht-leere Metrik-Auswahl — sonst waere ' +
				'der Vergleich unten leer gegen leer und wuerde nichts bewachen.'
		).toBeGreaterThan(0);
		expect(
			auswahlNachher,
			'AC-2 FAIL: die Metrik-Auswahl hat sich durch die Alarm-Geste veraendert.'
		).toEqual(auswahlVorher);
	});
});
