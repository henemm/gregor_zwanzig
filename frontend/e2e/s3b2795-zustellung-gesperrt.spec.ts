// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): gesperrte Kanaele mit Konto-Link.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-15, AC-16, AC-21, AC-13 (gesperrt zaehlt nicht)
//
// Ein frisch registrierter, bestaetigter Zweitnutzer (Tarif free, ohne Telegram, ohne SMS-Nummer, ohne Premium-SMS)
// sieht im Reiter: Telegram gesperrt mit „Im Konto verbinden →“, SMS gesperrt, Premium-SMS-Alarm „gesperrt: … ab Level
// Premium“. Derselbe Test-Code fuer Trip und Orts-Briefing.
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-gesperrt

import { test, expect } from '@playwright/test';
import { HUB_KINDS, registriereBestaetigtenZweitnutzer } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, ZT, oeffneZustellung, profil, seedZustellung } from './s3b2795-zustellung.helpers';

for (const kind of HUB_KINDS) {
	test(`AC-15/AC-16/AC-21 (${kind}): Kanal ohne Verbindung gesperrt, Grund + Konto-Link, Dringlichkeit „–“`, async ({ page, browser }) => {
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		let hub: Awaited<ReturnType<typeof seedZustellung>> | undefined;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2e2795gesperrt${kind}${Date.now()}`, kennwort);
			const p = await profil(gast.request);
			expect(p.telegram_chat_id ?? '', 'Messaufbau: Zweitnutzer ohne Telegram').toBe('');
			// Alarme in der Datei an, damit die Sperre sichtbar wird, obwohl der Wert gespeichert ist.
			hub = await seedZustellung(gast.request, kind, { alert_channels: { email: true, telegram: true, sms: true, premium_sms: true } });
			const seite = await gast.newPage();
			await seite.setViewportSize(DESKTOP);
			const reiter = await oeffneZustellung(seite, kind, hub.id);

			const tg = reiter.getByTestId(ZT.zeile('telegram'));
			await expect(tg.getByTestId(ZT.status('telegram'))).toContainText('nicht verbunden');
			await expect(tg.getByTestId(ZT.hinweis('telegram'))).toContainText('Telegram-Chat fehlt');
			await expect(tg.getByTestId(ZT.konto('telegram'))).toHaveText('Im Konto verbinden →');
			await expect(tg.getByTestId(ZT.briefing('telegram'))).toBeDisabled();
			await expect(tg.getByTestId(ZT.briefing('telegram'))).toHaveAttribute('aria-checked', 'false');
			await expect(tg.getByTestId(ZT.alarm('telegram')), 'gesperrt: kein Alarm-Schalter').toHaveCount(0);
			await expect(tg.getByTestId(ZT.alarmGesperrt('telegram'))).toHaveText(/^gesperrt: \S/);
			await expect(tg.getByTestId(ZT.dringlichkeit('telegram'))).toHaveText('–');

			const sms = reiter.getByTestId(ZT.zeile('sms'));
			await expect(sms.getByTestId(ZT.briefing('sms'))).toBeDisabled();
			await expect(sms.getByTestId(ZT.alarmGesperrt('sms'))).toHaveText(/^gesperrt: \S/);
			await expect(sms.getByTestId(ZT.hinweis('sms'))).toHaveText(/SMS ab Level Standard|Nummer/);

			const pr = reiter.getByTestId(ZT.zeile('premium_sms'));
			await expect(pr.getByTestId(ZT.alarmGesperrt('premium_sms'))).toHaveText(/^gesperrt: .*ab Level Premium/);
			await expect(pr.getByTestId(ZT.briefing('premium_sms'))).toBeDisabled();

			// Nur E-Mail ist an UND verbunden.
			await expect(reiter.getByTestId(ZT.kanaeleKopf)).toHaveText('Briefings über 1 Kanal · Alarme über 1 Kanal');

			await tg.getByTestId(ZT.konto('telegram')).click();
			await expect.poll(() => new URL(seite.url()).pathname, { message: 'Konto-Link fuehrt ins Konto' }).toMatch(/^\/account/);
		} finally {
			await hub?.aufraeumen().catch(() => {});
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
		}
	});
}
