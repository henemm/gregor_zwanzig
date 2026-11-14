// E2E — Issue #2347 S3b (Epic #2345, Etappe P6): Aufbau des Versand-Abschnitts — EINE Zusicherung
// für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3b_paritaets_e2e.md § AC-6 (VA-1..VA-4)
//
// Ersetzt aus versand-tab-vergleich.spec.ts (#1232 S2b, nur Vergleich, Regel-2-Altlast):
//   AC-1  feste Reihenfolge, keine Alarm-Stufen je Metrik     → VA-1 (je kind)
//   AC-4  Cooldown nur im Alarm-Teil, Stufen je Metrik nur im Reiter Wetter → VA-2 (je kind)
//   AC-7  alle Kanäle aus ⇒ Hinweis statt stiller Leere       → VA-3 (je kind; bestätigte
//         Adresse über testMitZustellbaremZiel, ohne `{force: true}`, ohne Admin-Profil-Änderung)
//   AC-10 mobil ohne horizontales Scrollen                    → VA-4 (je kind)
// Übrige Fälle der Altdatei: AC-2 → hub-versand-autosave-chip AC-1, AC-3/AC-3b →
// hub-versand-speichert-selbst VS-7/VS-8, AC-6 → compare-editor-slice3,
// Staging-F001 → hub-wetter-metriken-speichert-selbst MS-2.
//
// #2795 S3b Teilschritt 1b (feat_2795_s3b_teil1_zustellung.md): der Versand-Abschnitt ist durch den
// Reiter „Zustellung“ abgelöst. VA-1 prüft dessen Reihenfolge (Spec §1: Kopf · Briefing-Zeiten ·
// Laufzeit · Kanäle · Stille Stunden · Übergangsblock), VA-2 „jede Funktion genau einmal im Hub“
// (AC-31: Cooldown im Reiter Zustellung, „Alarm ab“ je Metrik nur im Reiter Wetter), VA-3 die
// Briefing-Warnbox bei 0 Kanälen (AC-11), VA-4 den mobilen Aufbau samt Kanal-Tabelle.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh). Aufräumen im finally.

import { test, expect, type Page } from '@playwright/test';
import {
	createTestLocation,
	HUB_KINDS,
	HUB_SEL,
	openHub,
	seedHub,
	testMitZustellbaremZiel,
	type HubKind
} from './helpers';
import { MARKER, ZT, cooldownFeld } from './s3b2795-zustellung.helpers';

/** kind-Tabelle: Seed mit aktiver, alarmfähiger Metrik. */
const VA_SEL: Record<HubKind, { metrikSeed: Record<string, unknown> }> = {
	// Böen → wind_gust ist alarmfähig (Muster hub-alarme-wertprops.spec.ts AW, Trip-Seed).
	route: { metrikSeed: { display_config: { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] } } },
	vergleich: { metrikSeed: { display_config: { active_metrics: ['wind_max_kmh'] } } }
};

const abschnitt = (page: Page) => page.locator('[data-testid="zustellung-tab"]:visible');

async function oeffneVersand(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'zustellung', hash: 'versand' });
	await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
	await expect(abschnitt(page).getByTestId(ZT.tabelle)).toBeVisible({ timeout: 10_000 });
}

/** Alarm-Stufen je Metrik (alt: Level-Tabelle, neu: „Alarm ab“ im Reiter Wetter). */
const STUFEN_JE_METRIK = '[data-testid="alert-metric-level-table"], [data-testid^="wetter-alarm-ab-"], [data-testid^="alert-level-"]';

// ─── VA-1, VA-2, VA-4 (Admin-Sitzung) ───────────────────────────────────────
for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const va = VA_SEL[kind];

	test.describe(`Hub · Versand-Abschnitt Aufbau (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// VA-1 (Alt AC-1) — fängt: fehlender/vertauschter Block bzw. Alarm-Stufen je Metrik im Reiter.
		test(`VA-1 (${kind}): Reiter Zustellung zeigt Kopf → Briefing-Zeiten → Laufzeit → Kanäle → Stille Stunden → Übergang, keine Alarm-Stufen je Metrik`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: va.metrikSeed });
			try {
				await oeffneVersand(page, kind, hub.id);
				const reihe = await abschnitt(page)
					.locator('[data-abschnitt]')
					.evaluateAll((els) => els.map((e) => e.getAttribute('data-abschnitt')));
				expect(reihe, 'Abschnitte in der Reihenfolge des Mockups (Spec §1)').toEqual([...MARKER]);
				for (const m of MARKER) await expect(abschnitt(page).locator(`[data-abschnitt="${m}"]`)).toBeVisible();
				// Der Anker #versand liegt auf den Briefing-Zeiten (Sprungziel „Bearbeiten →“, AC-39).
				await expect(abschnitt(page).locator('#versand')).toHaveAttribute('data-abschnitt', 'briefing-zeiten');
				await expect(abschnitt(page).locator(STUFEN_JE_METRIK), 'keine Alarm-Stufen je Metrik im Reiter Zustellung (AC-31)').toHaveCount(0);
				await expect(abschnitt(page).locator('[data-testid^="alert-metric-channels"]'), 'kein „Kanäle je Wettergröße“ (AC-27)').toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VA-2 (Alt AC-4) — fängt: Cooldown bzw. Alarm-Stufen je Metrik doppelt oder am falschen Ort.
		// Umweg über den Reiter Wetter wie im Alt-Fall (activeMetricKeys hydratisieren dort).
		test(`VA-2 (${kind}): Cooldown nur im Reiter Zustellung, „Alarm ab“ je Metrik nur im Reiter Wetter — keins von beidem doppelt`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: va.metrikSeed });
			try {
				await openHub(page, kind, hub.id);
				await page.locator(`[data-testid="${sel.reiter}-wetter"]:visible`).first().click();
				const wetter = page.locator(`[data-testid="${sel.panel}-wetter"]:visible`).first();
				await expect(wetter).toBeVisible({ timeout: 10_000 });
				await expect
					.poll(() => wetter.locator('[data-testid^="wetter-alarm-ab-"]:visible').count(), {
						timeout: 15_000,
						message: '„Alarm ab“ der aktiven Metrik muss im Reiter Wetter stehen'
					})
					.toBeGreaterThanOrEqual(1);
				await expect(wetter.locator('[data-testid="zustellung-cooldown"], [data-testid="alert-cooldown-input"]'), 'der Reiter Wetter trägt keinen Cooldown').toHaveCount(0);

				await page.locator(`[data-testid="${sel.reiter}-zustellung"]:visible`).first().click();
				await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
				await expect(await cooldownFeld(abschnitt(page)), 'Cooldown im Reiter Zustellung unter „Anpassen“ (AC-26)').toBeVisible();
				await expect(abschnitt(page).locator('[data-testid="zustellung-cooldown"]')).toHaveCount(1);
				await expect(abschnitt(page).locator(STUFEN_JE_METRIK), 'keine Alarm-Stufen je Metrik im Reiter Zustellung (AC-31)').toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VA-4 (Alt AC-10) — fängt: feste Mindestbreite im Reiter.
		test(`VA-4 (${kind}): mobiler Viewport 390×844 — Reiter Zustellung ohne horizontales Scrollen`, async ({ page }) => {
			const hub = await seedHub(page.request, kind);
			try {
				await page.setViewportSize({ width: 390, height: 844 });
				await oeffneVersand(page, kind, hub.id);
				await expect(abschnitt(page).getByTestId(ZT.zeile('email'))).toBeVisible({ timeout: 10_000 });
				await expect(abschnitt(page).getByTestId(ZT.karte('morgen'))).toBeVisible();
				const ohneQuerScroll = await page.evaluate(
					() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
				);
				expect(ohneQuerScroll, 'horizontales Scrollen auf Mobile darf nicht auftreten').toBe(true);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}

// ─── VA-3 (Zweitnutzer mit bestätigter Adresse) ─────────────────────────────
// Vorbedingung „E-Mail-Kanal schaltbar": der E-Mail-Schalter ist nur mit bestätigter Konto-Adresse
// bedienbar (AC-15/AC-16). Der Env-Admin des CI-Stacks hat keine ⇒ bestätigter Zweitnutzer
// (testMitZustellbaremZiel); das Admin-Profil bleibt unberührt, kein `{force: true}`.
for (const kind of HUB_KINDS) {
	// VA-3 (Alt AC-7) — fängt: Warnbox fehlt bzw. erscheint trotz eingeschaltetem Kanal.
	testMitZustellbaremZiel(`VA-3 (${kind}): alle Kanäle aus → Warnbox „Kein Kanal für Briefings an“ statt stiller Leere`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		// Seed-Besonderheit (kind-Zweig nur für den Seed, Muster KA-5): die e2e-loc-* aus
		// global.setup.ts gehören dem Admin — der Zweitnutzer bekommt eigene Orte.
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'VA3-A' }), await createTestLocation(page.request, { name: 'VA3-B' })]
				: [];
		const hub = await seedHub(page.request, kind, orte.length ? { extra: { location_ids: orte.map((o) => o.id) } } : {});
		try {
			await oeffneVersand(page, kind, hub.id);
			const email = abschnitt(page).getByTestId(ZT.briefing('email'));
			// Vorbedingung ausdrücklich (kein `if` — sonst wäre der Fall blind): E-Mail an und
			// bedienbar, die übrigen Kanäle aus, keine Warnbox.
			await expect(email).toBeVisible({ timeout: 10_000 });
			await expect(email).not.toHaveAttribute('aria-disabled', 'true');
			await expect(email).toHaveAttribute('aria-checked', 'true');
			await expect(abschnitt(page).getByTestId(ZT.warnBriefing)).toHaveCount(0);
			for (const k of ['telegram', 'sms', 'premium_sms'] as const) {
				await expect(abschnitt(page).getByTestId(ZT.briefing(k)), `Vorbedingung: ${k} ist aus`).toHaveAttribute('aria-checked', 'false');
			}

			await email.click();
			await expect(email).toHaveAttribute('aria-checked', 'false');

			const warn = abschnitt(page).getByTestId(ZT.warnBriefing);
			await expect(warn).toBeVisible({ timeout: 10_000 });
			await expect(warn).toHaveAttribute('role', 'alert');
			await expect(warn).toContainText('Kein Kanal für Briefings an.');
			await expect(abschnitt(page).getByTestId(ZT.kanaeleKopf)).toContainText('Briefings über 0 Kanäle');
			// Die Zeitkarten bleiben bedienbar (die Warnbox ersetzt sie nicht).
			await expect(abschnitt(page).getByTestId(ZT.karte('morgen'))).toBeVisible();

			await email.click();
			await expect(email).toHaveAttribute('aria-checked', 'true');
			await expect(warn, 'mit einem Briefing-Kanal verschwindet die Warnbox').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}
