// E2E — Issue #2276 Scheibe S5 (Epic #2345): der Reiter „Versand" im
// Ortsvergleich-Hub speichert SELBST über den Speicher-Controller der Seite —
// ohne den historischen Wrapper-Div `.hub-versand-wrap` mit seinen drei
// Sammel-Ereignissen (`onchange`/`onfocusout`/`onclick`). Nachweis am Wirkort.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md
//   AC-1 (Speicherweg über den Controller, genau ein PUT), AC-4 (Reiterwechsel
//   verliert nichts), AC-5 („Bis auf Weiteres" ohne change-/focusout-Ereignis),
//   AC-6 (412 → „Nochmal speichern"), AC-7 (Pausieren flusht die ausstehende
//   Änderung), AC-11 (übrige Einstellungen bleiben unverändert)
//
// Warum E2E: die Frontend-Unit-Harness ist SSR-only (node --test +
// svelte/server), `$effect`/Ereignisse laufen dort nie. Die Verdrahtung — der
// reaktive `$effect` in VersandTab.svelte, die neuen Props am Mount in
// CompareTabs.svelte, der listenbasierte Flush-Guard in handleValueChange, der
// Flush vor handleToggleActive, der Wegfall des Wrapper-Divs — ist nur im
// echten Browser messbar. Die Modul-Zusicherungen stehen in
// src/lib/components/shared/__tests__/versand_*.test.ts.
//
// Getestet wird über Uhrzeit/Enddatum/SMS-Kanal, NICHT über Telegram: der
// Telegram-Schalter braucht auf Staging eine chat-id-Sonderbehandlung
// (compare-hub-versand-inline.spec.ts:17-22), die mit dem Speicherweg nichts
// zu tun hat.
//
// #2375: der erste PUT nach SSR-Laden geht ohne If-Match durch — für den
// 412-Fall (AC-6) speichert dieser Test deshalb ZUERST selbst, bevor er den
// Konflikt provoziert (Muster compare-wetter-metriken-speichert-selbst.spec.ts).
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// gespeicherten storageState aus global.setup.ts. Presets tragen das Präfix
// E2E-GZ-, damit global.teardown.ts Reste räumt; afterEach löscht sie direkt.
// Aufnahme in .github/ci_e2e_specs.txt macht die Implementierung.

import { test, expect, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX } from './helpers';

let angelegt: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of angelegt) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Aufräumen ist nicht testkritisch */
		}
	}
	angelegt = [];
});

async function legeVergleichAn(page: Page, extra: Record<string, unknown> = {}): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}Versand speichert selbst ${Date.now()}`,
			// Seed-Orte aus global.setup.ts — mit Orten ist der Vergleich „aktiv",
			// die Aktivierungs-Karte bietet dann „Pausieren" an.
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['versand-selbst@example.com'],
			official_alerts_enabled: true,
			radar_alert_enabled: false,
			send_telegram: true,
			send_sms: false,
			morning_enabled: true,
			morning_time: '06:00:00',
			evening_enabled: false,
			evening_time: '18:00:00',
			end_date: '2027-01-15',
			// AC-11: die drei Legacy-Restfelder, die kein Versand-Kontrollelement
			// mutiert — ein Versand-PUT ohne sie würde sie serverseitig nullen.
			alert_cooldown_minutes: 45,
			alert_quiet_from: '22:00',
			alert_quiet_to: '07:00',
			corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
			display_config: {
				region: 'Tirol',
				ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
				active_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			},
			...extra
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	angelegt.push(body.id);
	return body.id as string;
}

/** Zählt die PUTs auf genau diesen Vergleich (Request = abgeschickter Rumpf). */
function zaehlePuts(page: Page, id: string): { puts: Request[]; beantwortet: Request[] } {
	const pfad = `/api/compare/presets/${id}`;
	const puts: Request[] = [];
	const beantwortet: Request[] = [];
	const trifft = (r: Request) => r.method() === 'PUT' && new URL(r.url()).pathname === pfad;
	page.on('request', (r) => {
		if (trifft(r)) puts.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) beantwortet.push(r);
	});
	return { puts, beantwortet };
}

async function oeffneVersand(page: Page, id: string) {
	await page.goto(`/compare/${id}?tab=versand`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
	const tab = page.locator('[data-testid="versand-tab"]:visible');
	await expect(tab).toBeVisible({ timeout: 10_000 });
	await expect(tab.locator('[data-testid="report-morning-time"]')).toBeVisible({ timeout: 10_000 });
	return tab;
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const smsSchalter = (tab: ReturnType<Page['locator']>) =>
	tab.locator('[data-testid="compare-step5-channel-sms"] input[type="checkbox"]');

test.describe('Issue #2276 S5: Reiter „Versand" im Ortsvergleich speichert selbst', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// AC-1 — fängt: der reaktive $effect fehlt oder die Props am Mount fehlen
	// ⇒ gar kein PUT; oder der Wrapper-Div ist zusätzlich aktiv ⇒ mehr als ein PUT.
	test('AC-1: Morgen-Uhrzeit ändern → genau EIN PUT über den Controller, danach „Gespeichert"', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneVersand(page, id);
		expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

		await tab.locator('[data-testid="report-morning-time"]').selectOption('08:00');

		// Der Zustandsweg idle → saving → saved wird am Controller im Kern-Test
		// geprüft (versand_vergleich_speichert_selbst.test.ts); hier zählt der
		// Endzustand — ein Durchgangszustand wäre eine Flake-Quelle in einer
		// geratschten Spec.
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige(page)).toContainText('Gespeichert');
		// kurze Nachfrist: ein zweiter, verspäteter PUT wäre jetzt sichtbar
		await page.waitForTimeout(1_200);

		expect(puts.length, 'eine Geste im Versand-Reiter darf nur EINEN PUT auslösen').toBe(1);
		const stand = await serverStand(page, id);
		expect(stand.morning_time).toBe('08:00:00');
	});

	// AC-5 — fängt: der Wegfall des Wrapper-`onclick` ohne Ersatz. „Bis auf
	// Weiteres" ist ein reiner Button-Klick ohne change-/focusout-Ereignis.
	test('AC-5: „Bis auf Weiteres" (reiner Klick) → Enddatum gelöscht und gespeichert', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const { beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneVersand(page, id);
		await expect(tab.locator('[data-testid="compare-versand-enddate-date"]')).toHaveAttribute(
			'aria-selected',
			'true'
		);

		await tab.locator('[data-testid="compare-versand-enddate-open"]').click();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		const stand = await serverStand(page, id);
		expect(stand.end_date, 'der reine Button-Klick muss ohne Wrapper-Ereignis gespeichert werden').toBe('');

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
		await expect(
			page.locator('[data-testid="compare-versand-enddate-open"]:visible')
		).toHaveAttribute('aria-selected', 'true', { timeout: 10_000 });
	});

	// AC-4 — fängt: 'versand' fehlt in SELBST_SPEICHERNDE_VERGLEICH_REITER ⇒ der
	// Alarm-Vorgang verdrängt die Versand-Änderung vom einen Speicher-Platz.
	test('AC-4: Uhrzeit ändern, sofort zu „Alarme", dort Radar an → BEIDE Änderungen gespeichert', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneVersand(page, id);

		await tab.locator('[data-testid="report-morning-time"]').selectOption('09:00');
		// sofort, innerhalb des Entprell-Fensters, den Reiter wechseln
		await page.locator('[data-testid="compare-detail-tab-alarme"]:visible').click();
		await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
		expect(
			beantwortet.length,
			'die Versand-Änderung war beim Reiterwechsel noch nicht gesendet'
		).toBeGreaterThanOrEqual(1);

		const radar = page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
		await radar.click();
		await expect(radar).toBeChecked();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const stand = await serverStand(page, id);
		expect(stand.morning_time, 'die Versand-Änderung ging beim Reiterwechsel verloren').toBe('09:00:00');
		expect(stand.radar_alert_enabled).toBe(true);
	});

	// AC-6 — fängt: 412 als generischer Fehler (setError statt conflict) bzw.
	// Rollback auch bei 412.
	test('AC-6: fremde Änderung dazwischen → „Nochmal speichern" → gespeichert, Wert bleibt sichtbar', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneVersand(page, id);

		// GIVEN: eigene erste Änderung gespeichert — die Seite kennt jetzt den ETag (#2375)
		await tab.locator('[data-testid="report-morning-time"]').selectOption('08:00');
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		// An der Oberfläche vorbei: fremde Änderung ohne If-Match (anderes Gerät)
		const vorher = await serverStand(page, id);
		const fremd = await page.request.put(`/api/compare/presets/${id}`, {
			data: { ...vorher, name: `${vorher.name} (fremd)` }
		});
		expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

		// WHEN: zweite Änderung auf dem jetzt veralteten Stand
		const sms = smsSchalter(tab);
		await sms.click();

		// THEN: echter 412 → „Nochmal speichern", keine Rücknahme in der Oberfläche
		await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		expect(puts.length, 'Vorbedingung: der zweite PUT wurde gesendet').toBe(2);
		expect((await puts[1].response())?.status(), 'der Server muss den veralteten Stand ablehnen').toBe(412);
		await expect(sms, 'bei 412 darf die Oberfläche nicht zurückspringen').toBeChecked();
		const nochmal = anzeige(page).getByRole('button', { name: 'Nochmal speichern' });
		await expect(nochmal).toBeVisible();

		// WHEN: „Nochmal speichern" → THEN: gespeichert, Wert bleibt sichtbar
		await nochmal.click();
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige(page)).toContainText('Gespeichert');
		expect((await puts[2].response())?.status(), 'der Wiederholungs-PUT muss durchgehen').toBe(200);

		const stand = await serverStand(page, id);
		expect(stand.send_sms, 'der Wiederholungs-PUT muss die Änderung tragen').toBe(true);
	});

	// AC-7 — fängt: der generische saveController.flush() in handleToggleActive
	// greift nicht, weil der Versand-Reiter nicht über schedule() speichert.
	test('AC-7: Uhrzeit ändern und sofort pausieren → die Änderung ist im gespeicherten Stand', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const tab = await oeffneVersand(page, id);
		const cta = page.locator('[data-testid="compare-hub-activation-cta"]:visible');
		await expect(cta).toHaveText('Pausieren');

		// Kein Warten zwischen den beiden Aktionen — die Änderung steht noch im
		// Entprell-Fenster, wenn der Pausier-PUT losgeht.
		await tab.locator('[data-testid="report-morning-time"]').selectOption('10:00');
		await cta.click();

		await expect(cta).toHaveText('Aktivieren', { timeout: 10_000 });
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const stand = await serverStand(page, id);
		expect(stand.schedule, 'Vorbedingung: der Vergleich ist pausiert').toBe('manual');
		expect(stand.morning_time, 'der Pausier-PUT hat die ausstehende Versand-Änderung überschrieben').toBe(
			'10:00:00'
		);
	});

	// AC-11 — fängt: Teil-Nutzlast. Besonders die drei Legacy-Restfelder
	// (alert_cooldown_minutes/alert_quiet_from/alert_quiet_to), die kein
	// Versand-Kontrollelement mutiert und die ein schlanker PUT nullen würde.
	test('AC-11: Uhrzeit ändern → alle übrigen Einstellungen bleiben nach dem Neuladen unverändert', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const vorher = await serverStand(page, id);
		const { beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneVersand(page, id);

		await tab.locator('[data-testid="report-morning-time"]').selectOption('08:00');
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const nachher = await serverStand(page, id);
		expect(nachher.alert_cooldown_minutes, 'der Versand-PUT hat den Cooldown genullt').toBe(45);
		expect(nachher.alert_quiet_from, 'der Versand-PUT hat die Stillen Stunden genullt').toBe('22:00');
		expect(nachher.alert_quiet_to, 'der Versand-PUT hat die Stillen Stunden genullt').toBe('07:00');

		// `display_config` ist bewusst ausgenommen und wird darunter gezielt
		// geprüft: der Voll-Spread schreibt `active_metrics` im Paar-Format
		// (metric_id + Auswertung, #1373/ADR-0037), sobald der Metrik-Katalog im
		// Browser registriert ist. Ein Ganz-Objekt-Vergleich würde diese
		// Schreib-Normalisierung als „Veränderung" melden, obwohl nichts verloren
		// geht (S4-Präzedenz).
		const VERSAND_OBEN = new Set(['morning_time', 'display_config', 'updated_at', 'etag']);
		for (const key of Object.keys(vorher)) {
			if (VERSAND_OBEN.has(key)) continue;
			expect(nachher[key], `Feld „${key}" hat sich durch das Versand-Speichern verändert`).toEqual(
				vorher[key]
			);
		}
		expect(nachher.morning_time, 'nur die Uhrzeit weicht ab').toBe('08:00:00');

		const vdc = (vorher.display_config ?? {}) as Record<string, unknown>;
		const ndc = (nachher.display_config ?? {}) as Record<string, unknown>;
		expect(ndc.region, 'die Region darf beim Versand-Speichern nicht leer werden').toEqual(vdc.region);
		expect(ndc.ideal_ranges, 'die Wertebereiche dürfen nicht verloren gehen').toEqual(vdc.ideal_ranges);
		expect(ndc.telegram_style, 'der Kurzstil darf nicht verloren gehen').toEqual(vdc.telegram_style);
		expect(
			(ndc.active_metrics as unknown[])?.length,
			'die Metrik-Auswahl darf durch das Versand-Speichern nicht leer werden'
		).toBe((vdc.active_metrics as unknown[]).length);
	});
});
