// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Kanal-Tabelle, Warnboxen, Dringlichkeit, send_email, Profil.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-11, AC-12, AC-13, AC-14, AC-17, AC-18, AC-23, AC-36
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich). Erwartungen zum Verbindungsstatus werden aus
// dem Profil des angemeldeten Kontos abgeleitet (GET /api/auth/profile) — kein fester Kontozustand angenommen.
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-kanaele

import { test, expect } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, openHub } from './helpers';
import {
	DESKTOP,
	KANAELE,
	ZT,
	oeffneZustellung,
	profil,
	schalte,
	seedZustellung,
	sendebereit,
	stand,
	warteAufSpeichern,
	type Json
} from './s3b2795-zustellung.helpers';

const NAME = { email: 'E-Mail', telegram: 'Telegram', sms: 'SMS', premium_sms: 'Premium-SMS' } as const;
const kn = (n: number) => (n === 1 ? 'Kanal' : 'Kanäle');

/** Alle Briefing- und Alarm-Kanaele aus (fuer die Warnboxen). */
function allesAus(kind: 'route' | 'vergleich'): Json {
	const alarme = { alert_channels: { email: false, telegram: false, sms: false, premium_sms: false } };
	if (kind === 'route') {
		return {
			...alarme,
			report_config: { enabled: true, morning_enabled: true, evening_enabled: true, morning_time: '07:00:00', evening_time: '18:00:00', send_email: false, send_telegram: false, send_sms: false, send_premium_sms: false }
		};
	}
	return { ...alarme, send_email: false, send_telegram: false, send_sms: false, send_premium_sms: false };
}

for (const kind of HUB_KINDS) {
	test(`AC-13/AC-14/AC-18 (${kind}): vier Zeilen mit Status, Kopf zaehlt nur „an und verbunden“, Legende`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const p = await profil(page.request);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const tabelle = reiter.getByTestId(ZT.tabelle);
			await expect(tabelle.locator('th')).toHaveText(['Kanal', 'Briefing', 'Alarme', 'Alarm schon ab Dringlichkeit']);
			for (const k of KANAELE) {
				const zeile = reiter.getByTestId(ZT.zeile(k));
				await expect(zeile).toContainText(NAME[k]);
				await expect(zeile.getByTestId(ZT.status(k))).toBeVisible();
				if (sendebereit(p, k)) await expect(zeile.getByTestId(ZT.konto(k)), `${k}: verbunden ohne Konto-Link`).toHaveCount(0);
				else await expect(zeile.getByTestId(ZT.konto(k)), `${k}: gesperrt mit Konto-Link`).toHaveText(/^Im Konto (verbinden|bestätigen|prüfen) →$/);
			}
			// Seed: Briefing nur E-Mail, Alarme nur E-Mail (zaehlt nur, wenn verbunden)
			const n = sendebereit(p, 'email') ? 1 : 0;
			await expect(reiter.getByTestId(ZT.kanaeleKopf)).toHaveText(`Briefings über ${n} ${kn(n)} · Alarme über ${n} ${kn(n)}`);
			await expect(reiter.getByTestId(ZT.kanaeleUnterzeile)).toHaveText('Ein Kanal ohne Verbindung ist gesperrt, bis du ihn im Konto einrichtest.');
			await expect(reiter.getByTestId(ZT.legende)).toHaveText(
				/^Die SMS kostet wenig und bekommt deshalb schon Alarme ab [„‚]mittel[“‘]\. Die Premium-SMS geht über Satellit und meldet sich nur bei [„‚]hoch[“‘]\.$/
			);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-11/AC-12 (${kind}): Warnboxen bei 0 Kanaelen, getrennt, verschwinden nach Einschalten`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const p = await profil(page.request);
		test.skip(!sendebereit(p, 'email'), 'Staging-Konto ohne E-Mail-Adresse — Einschalten nicht moeglich');
		const hub = await seedZustellung(page.request, kind, allesAus(kind));
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const wb = reiter.getByTestId(ZT.warnBriefing);
			const wa = reiter.getByTestId(ZT.warnAlarme);
			await expect(wb).toHaveAttribute('role', 'alert');
			await expect(wb).toHaveText(/Kein Kanal für Briefings an\.\s*So kommt kein Briefing bei dir an\. Schalte unten mindestens einen Kanal ein\./);
			await expect(wa).toHaveAttribute('role', 'alert');
			await expect(wa).toHaveText(/Kein Kanal für Alarme an\.\s*Alarme gehen nirgends hin\./);
			await expect(reiter.getByTestId(ZT.kanaeleKopf)).toHaveText('Briefings über 0 Kanäle · Alarme über 0 Kanäle');

			const s1 = warteAufSpeichern(page, kind, hub.id);
			await schalte(reiter.getByTestId(ZT.briefing('email')), true);
			await s1;
			await expect(wb).toHaveCount(0);
			await expect(wa, 'Alarm-Warnbox ist unabhaengig').toBeVisible();

			const s2 = warteAufSpeichern(page, kind, hub.id);
			await schalte(reiter.getByTestId(ZT.alarm('email')), true);
			await s2;
			await expect(wa).toHaveCount(0);
			await expect(reiter.getByTestId(ZT.kanaeleKopf)).toHaveText('Briefings über 1 Kanal · Alarme über 1 Kanal');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-17 (${kind}): Dringlichkeit „–“ bei Alarm aus, Segment bei Alarm an, Wahl gespeichert als MODERATE`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const p = await profil(page.request);
		const k = (['telegram', 'sms', 'email'] as const).find((x) => sendebereit(p, x));
		test.skip(!k, 'Staging-Konto ohne verbundenen Kanal');
		const kanal = k!;
		const hub = await seedZustellung(page.request, kind, { alert_channels: { email: false, telegram: false, sms: false, premium_sms: false } });
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const zelle = reiter.getByTestId(ZT.dringlichkeit(kanal));
			await expect(zelle).toHaveText('–');
			const s1 = warteAufSpeichern(page, kind, hub.id);
			await schalte(reiter.getByTestId(ZT.alarm(kanal)), true);
			await s1;
			await expect(zelle.getByTestId(ZT.dringlichkeitOption(kanal, 'LOW'))).toHaveText('gering');
			await expect(zelle.getByTestId(ZT.dringlichkeitOption(kanal, 'MODERATE'))).toHaveText('mittel');
			await expect(zelle.getByTestId(ZT.dringlichkeitOption(kanal, 'HIGH'))).toHaveText('hoch');
			const s2 = warteAufSpeichern(page, kind, hub.id);
			await zelle.getByTestId(ZT.dringlichkeitOption(kanal, 'MODERATE')).click();
			const rumpf = await s2;
			expect(Object.keys(rumpf), 'nur Dringlichkeit geaendert ⇒ nur alert_channel_thresholds gesendet (AC-32)').toEqual(['alert_channel_thresholds']);
			expect((await stand(page.request, kind, hub.id)).alert_channel_thresholds[kanal]).toBe('MODERATE');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-36 (${kind}): Reiter laedt das Profil genau einmal`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			await openHub(page, kind, hub.id, { tab: 'uebersicht' });
			let anfragen = 0;
			page.on('request', (r) => {
				if (r.method() === 'GET' && new URL(r.url()).pathname === '/api/auth/profile') anfragen++;
			});
			await page.locator(`[data-testid="${HUB_SEL[kind].reiter}-zustellung"]:visible`).first().click();
			const reiter = page.locator(`[data-testid="${HUB_SEL[kind].panel}-zustellung"]:visible`).first().getByTestId(ZT.tab);
			await expect(reiter.getByTestId(ZT.status('premium_sms'))).toBeVisible({ timeout: 15_000 });
			await expect(reiter.getByTestId(ZT.uebergang)).toBeVisible();
			await expect.poll(() => anfragen, { message: 'GET /api/auth/profile je Reiter-Aufruf' }).toBe(1);
		} finally {
			await hub.aufraeumen();
		}
	});
}

test('AC-23 (vergleich): E-Mail-Briefing aus ⇒ send_email false, nach Neuladen aus, wieder an ⇒ true; andere Felder unveraendert', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const p = await profil(page.request);
	test.skip(!sendebereit(p, 'email'), 'Staging-Konto ohne E-Mail-Adresse');
	const hub = await seedZustellung(page.request, 'vergleich');
	try {
		const vorher = await stand(page.request, 'vergleich', hub.id);
		const reiter = await oeffneZustellung(page, 'vergleich', hub.id);
		await expect(reiter.getByTestId(ZT.briefing('email')), 'Alt-Preset ohne send_email: an').toHaveAttribute('aria-checked', 'true');
		const s1 = warteAufSpeichern(page, 'vergleich', hub.id);
		await schalte(reiter.getByTestId(ZT.briefing('email')), false);
		expect(await s1).toEqual({ send_email: false });
		const aus = await stand(page.request, 'vergleich', hub.id);
		expect(aus.send_email).toBe(false);
		const ohne = (x: Json) => {
			const k = { ...x };
			for (const f of ['send_email', 'updated_at', 'etag']) delete k[f];
			return k;
		};
		expect(ohne(aus), 'andere Preset-Felder unveraendert').toEqual(ohne(vorher));

		await page.reload();
		const neu = await oeffneZustellung(page, 'vergleich', hub.id);
		await expect(neu.getByTestId(ZT.briefing('email'))).toHaveAttribute('aria-checked', 'false');
		const s2 = warteAufSpeichern(page, 'vergleich', hub.id);
		await schalte(neu.getByTestId(ZT.briefing('email')), true);
		await s2;
		expect((await stand(page.request, 'vergleich', hub.id)).send_email).toBe(true);
	} finally {
		await hub.aufraeumen();
	}
});
