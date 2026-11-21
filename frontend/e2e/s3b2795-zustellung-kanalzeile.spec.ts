// E2E — Issue #3202 (Epic #2913): Kanalzeile im Reiter Zustellung nach Mockup Fassung 4.
// Spec: docs/specs/modules/feat_3202_kanalzeile_mockup.md — AC-1, AC-2, AC-4, AC-5, AC-6, AC-8
// (AC-7 ist der Ganzseitenvergleich elementliste-abgleich.staging.spec.ts, AC-3 die Kern-Tests der Kürzung).
// Derselbe Test-Code für Trip (route) und Orts-Vergleich (vergleich), Nutzersicht im Browser.
//
//   AC-1/AC-4/AC-5/AC-6: NUR die Profil-Lesung des Browsers wird um erfundene Kanal-Daten ergänzt
//   (Muster hub-anlegen-ablauf AN-6; kein Profil wird verändert), damit die erwarteten Zeilen fest sind.
//   AC-2: weder Trip noch Orts-Vergleich zeigt eine Empfängerzahl, auch wenn preset.empfaenger mit weiteren
//   Adressen gefüllt ist (PO-Korrektur 21.11.2026: das Feld ist seit #1452 wirkungslos).
//   AC-8: zwei echte Konten ohne Umschreibung — jedes sieht nur den gekürzten Lokalteil seiner eigenen Adresse.
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-kanalzeile

import { test, expect, type Page } from '@playwright/test';
import { HUB_KINDS, registriereBestaetigtenZweitnutzer } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, KANAELE, ZT, oeffneZustellung, profil, seedZustellung, type Json, type KanalId } from './s3b2795-zustellung.helpers';

// Erfundene Kanal-Daten (example.com, Fantasienummer, Fantasie-Chat-ID).
const MAIL = 'wanderer-3202@example.com';
const ZWEITE = 'begleitung-3202@example.com';
const DRITTE = 'dritte-3202@example.com';
const NUMMER = '+491711234567';
const CHAT = '3202987654';
const RUECKADRESSE = 'geraet-3202@inreach.example.com';

const NORMAL: Json = {
	mail_to: MAIL,
	email_verified: true,
	telegram_chat_id: CHAT,
	sms_to: NUMMER,
	sms_allowed: true,
	sms_verified: true,
	premium_sms_allowed: true,
	premium_sms_reply_to: RUECKADRESSE,
	premium_sms_reply_at: '2026-11-01T18:04:00Z',
	premium_sms_reply_state: 'fresh'
};
const LUECKEN: Json = { ...NORMAL, telegram_chat_id: '', sms_to: '+49 171 0000000', sms_verified: false, pending_sms_to: '', premium_sms_reply_state: 'stale' };

/** Ergänzt NUR die Profil-Lesung des Browsers (GET) um die erfundenen Kanal-Daten. */
async function profilUmschreiben(page: Page, felder: Json): Promise<void> {
	await page.route('**/api/auth/profile', async (route) => {
		if (route.request().method() !== 'GET') return route.continue();
		const echt = await route.fetch();
		const p = (await echt.json()) as Json;
		await route.fulfill({ response: echt, json: { ...p, ...felder } });
	});
}

async function zeilen(page: Page, kind: 'route' | 'vergleich', id: string): Promise<Record<KanalId, string>> {
	const reiter = await oeffneZustellung(page, kind, id);
	const aus = {} as Record<KanalId, string>;
	for (const k of KANAELE) {
		const el = reiter.getByTestId(ZT.status(k));
		await expect(el).toBeVisible();
		aus[k] = (await el.innerText()).replace(/\s+/g, ' ').trim();
	}
	return aus;
}

function keineRohwerte(z: Record<KanalId, string>): void {
	const alles = Object.values(z).join(' | ');
	for (const roh of [MAIL, NUMMER, '1711234567', '0000000', CHAT, RUECKADRESSE]) expect(alles, `Rohwert ${roh} sichtbar`).not.toContain(roh);
}

for (const kind of HUB_KINDS) {
	test(`#3202 AC-1/AC-5 (${kind}): Normalzustand gekürzt, Telegram nur „verbunden“, Premium ohne Rückadresse`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			await profilUmschreiben(page, NORMAL);
			const z = await zeilen(page, kind, hub.id);
			expect(z.email).toBe('bestätigt · wanderer-3202@…');
			expect(z.sms).toBe('bestätigt · +49 171 …');
			expect(z.telegram).toBe('verbunden');
			expect(z.premium_sms).toMatch(/^inReach · Rückadresse gelernt .+ · zuletzt gemeldet .+$/);
			expect(z.premium_sms).not.toContain('@');
			keineRohwerte(z);
		} finally {
			await page.unroute('**/api/auth/profile');
			await hub.aufraeumen();
		}
	});

	test(`#3202 AC-4 (${kind}): Zustand „Lücken“ — unbestätigt gekürzt, Rückadresse verfallen ohne Adresse, nicht verbunden`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			await profilUmschreiben(page, LUECKEN);
			const z = await zeilen(page, kind, hub.id);
			expect(z.sms).toBe('unbestätigt · +49 171 …');
			expect(z.premium_sms).toBe('inReach · Rückadresse verfallen');
			expect(z.telegram).toBe('nicht verbunden');
			keineRohwerte(z);
		} finally {
			await page.unroute('**/api/auth/profile');
			await hub.aufraeumen();
		}
	});

	test(`#3202 AC-6 (${kind}): Englisch aus dem Katalog, Adressen und Nummern unübersetzt`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind, kind === 'vergleich' ? { empfaenger: [MAIL, ZWEITE] } : {});
		try {
			const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
			expect(res.ok(), `Sprache en setzen: HTTP ${res.status()}`).toBeTruthy();
			await profilUmschreiben(page, NORMAL);
			const z = await zeilen(page, kind, hub.id);
			expect(z.email).toBe('confirmed · wanderer-3202@…');
			expect(Object.values(z).join(' | ')).not.toMatch(/recipient|Empfänger/i);
			expect(z.sms).toBe('confirmed · +49 171 …');
			expect(z.telegram).toBe('connected');
			expect(z.premium_sms).toMatch(/^inReach · reply address learned /);
			keineRohwerte(z);
		} finally {
			await page.unroute('**/api/auth/profile');
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
		}
	});
}

test('#3202 AC-2: weder Trip noch Orts-Vergleich mit gefüllter Empfängerliste zeigt eine Empfängerzahl', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const vergleich = await seedZustellung(page.request, 'vergleich', { empfaenger: [MAIL, ZWEITE, DRITTE] });
	const trip = await seedZustellung(page.request, 'route');
	try {
		const gespeichert = (await (await page.request.get(`/api/compare/presets/${vergleich.id}`)).json()) as Json;
		expect(gespeichert.empfaenger, 'Vorbedingung: Empfängerliste des Orts-Vergleichs ist gefüllt').toEqual([MAIL, ZWEITE, DRITTE]);
		await profilUmschreiben(page, NORMAL);
		for (const [kind, id] of [['vergleich', vergleich.id], ['route', trip.id]] as const) {
			const z = await zeilen(page, kind, id);
			expect(z.email, `${kind}: E-Mail-Zeile ohne Zahl`).toBe('bestätigt · wanderer-3202@…');
			const alles = Object.values(z).join(' | ');
			expect(alles, `${kind}: keine Empfängerzahl`).not.toContain('Empfänger');
			expect(alles, `${kind}: weitere Adressen nie sichtbar`).not.toMatch(/begleitung-3202|dritte-3202/);
		}
	} finally {
		await page.unroute('**/api/auth/profile');
		await vergleich.aufraeumen();
		await trip.aufraeumen();
	}
});

for (const kind of HUB_KINDS) {
	test(`#3202 AC-8 (${kind}): zwei Nutzer sehen je nur den gekürzten Lokalteil der eigenen Adresse`, async ({ page, browser }) => {
		await page.setViewportSize(DESKTOP);
		const pA: Json = await profil(page.request);
		const lokalA = String(pA.mail_to ?? '').split('@')[0];
		test.skip(!lokalA, 'Staging-Konto A ohne E-Mail-Adresse');
		const hubA = await seedZustellung(page.request, kind);
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		let hubB: Awaited<ReturnType<typeof seedZustellung>> | undefined;
		try {
			const nameB = `e2e3202kanal${kind}${Date.now()}`;
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, nameB, kennwort);
			const pB: Json = await profil(gast.request);
			const lokalB = String(pB.mail_to ?? '').split('@')[0];
			expect(lokalB, 'Konto B ohne E-Mail-Adresse').toBeTruthy();
			expect(lokalB).not.toBe(lokalA);
			hubB = await seedZustellung(gast.request, kind);

			const zA = await zeilen(page, kind, hubA.id);
			expect(zA.email).toMatch(new RegExp(`^(un)?bestätigt · ${lokalA.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}@…`));
			expect(zA.email, 'A sieht nie die volle eigene Adresse').not.toContain(String(pA.mail_to));
			expect(zA.email, 'A sieht nichts von B').not.toContain(lokalB);

			const seiteB = await gast.newPage();
			await seiteB.setViewportSize(DESKTOP);
			const zB = await zeilen(seiteB, kind, hubB.id);
			expect(zB.email).toMatch(new RegExp(`^(un)?bestätigt · ${lokalB}@…`));
			expect(zB.email, 'B sieht nie die volle eigene Adresse').not.toContain(String(pB.mail_to));
			expect(zB.email, 'B sieht nichts von A').not.toContain(`${lokalA}@`);
			if (pA.sms_to) expect(Object.values(zB).join(' | '), 'B sieht A\'s Nummer nicht').not.toContain(String(pA.sms_to));
		} finally {
			await hubB?.aufraeumen().catch(() => {});
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
			await hubA.aufraeumen();
		}
	});
}
