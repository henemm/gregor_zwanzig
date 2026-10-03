import { test, expect, type Locator } from '@playwright/test';
import { registriereBestaetigtenZweitnutzer } from './helpers';

/**
 * Konto-Löschdialog auf schmalem Bildschirm (Issue #2160, Fix-Loop).
 *
 * Befund auf Staging (390×844): der Dialog „Account löschen" läuft horizontal
 * über — `[role="dialog"]` scrollWidth 445 bei clientWidth 358. Der Knopf
 * „Code an <volle Mailadresse> senden" bricht nicht um und schiebt Text und
 * Eingabefelder über die rechte Kante.
 *
 * Gemessen wird im echten Browser gegen das echte Frontend, an der Stelle, an
 * der der Fehler WIRKT: am Dialog selbst (scrollWidth), an jedem sichtbaren
 * Nachfahren (Element-Rechtecke) UND an den Textzeilen des Code-Knopfs
 * (Range-Rechtecke). Letzteres verhindert, dass ein „Fix" per
 * `overflow:hidden`/`text-overflow:ellipsis` auf dem Knopf als grün durchgeht:
 * dann bliebe das Knopf-Rechteck im Dialog, die Adresse aber unlesbar.
 *
 * Positivkontrolle: derselbe Messhelfer am Dialog „Auf allen Geräten
 * abmelden" ist grün — der Helfer ist also nicht strukturell immer rot.
 */

const MOBIL = { width: 390, height: 844 };

interface Ueberlauf {
	scrollWidth: number;
	clientWidth: number;
	dialogRight: number;
	gemessen: number;
	ueberstehend: string[];
	textUeberstehend: string[];
	knopfScroll: { scrollWidth: number; clientWidth: number } | null;
}

async function warteAufRuhe(dialog: Locator): Promise<void> {
	// Zoom-in-Animation verzerrt Rechtecke per transform — erst abwarten.
	await dialog.evaluate((el) =>
		Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished))
	);
}

async function misstUeberlauf(dialog: Locator, knopfTestId?: string): Promise<Ueberlauf> {
	await warteAufRuhe(dialog);
	return dialog.evaluate((el, testId) => {
		const dialogRight = el.getBoundingClientRect().right;
		const beschreibe = (n: Element, right: number) =>
			`${n.tagName.toLowerCase()}${n.getAttribute('data-testid') ? `[${n.getAttribute('data-testid')}]` : ''} right=${right.toFixed(1)}`;
		const ueberstehend: string[] = [];
		let gemessen = 0;
		for (const n of Array.from(el.querySelectorAll('*'))) {
			const r = n.getBoundingClientRect();
			if (r.width === 0 || r.height === 0) continue;
			gemessen++;
			if (r.right > dialogRight + 1) ueberstehend.push(beschreibe(n, r.right));
		}
		const textUeberstehend: string[] = [];
		let knopfScroll: { scrollWidth: number; clientWidth: number } | null = null;
		if (testId) {
			const knopf = el.querySelector(`[data-testid="${testId}"]`) as HTMLElement | null;
			if (knopf) {
				knopfScroll = { scrollWidth: knopf.scrollWidth, clientWidth: knopf.clientWidth };
				const range = document.createRange();
				range.selectNodeContents(knopf);
				for (const r of Array.from(range.getClientRects())) {
					if (r.width === 0 || r.height === 0) continue;
					if (r.right > dialogRight + 1) textUeberstehend.push(`text right=${r.right.toFixed(1)}`);
				}
			}
		}
		return {
			scrollWidth: el.scrollWidth,
			clientWidth: el.clientWidth,
			dialogRight,
			gemessen,
			ueberstehend,
			textUeberstehend,
			knopfScroll
		};
	}, knopfTestId);
}

function erwarteKeinenUeberlauf(m: Ueberlauf, name: string): void {
	const bericht = `${name}: scrollWidth=${m.scrollWidth} clientWidth=${m.clientWidth} dialogRight=${m.dialogRight.toFixed(1)} ueberstehend=${JSON.stringify(m.ueberstehend)} textUeberstehend=${JSON.stringify(m.textUeberstehend)} knopf=${JSON.stringify(m.knopfScroll)}`;
	// Gegen vakuumes Grün: der Dialog ist gerendert und hat Inhalt.
	expect(m.clientWidth, bericht).toBeGreaterThan(0);
	expect(m.gemessen, bericht).toBeGreaterThan(0);
	expect(m.scrollWidth, bericht).toBeLessThanOrEqual(m.clientWidth);
	expect(m.ueberstehend, bericht).toEqual([]);
	expect(m.textUeberstehend, bericht).toEqual([]);
	if (m.knopfScroll) {
		expect(m.knopfScroll.scrollWidth, bericht).toBeLessThanOrEqual(m.knopfScroll.clientWidth + 1);
	}
}

test.describe('Konto-Löschdialog auf 390 px', () => {
	test('Dialog „Account löschen" mit langer Mailadresse läuft nicht horizontal über', async ({
		page,
		browser
	}) => {
		// Benutzername ≥ 28 Zeichen ⇒ Adresse `<name>@example.com` ≥ 40 Zeichen.
		const username = 'e2eloeschdialogmobil' + Date.now();
		const password = 'Test1234!x';
		const adresse = `${username}@example.com`;
		expect(adresse.length).toBeGreaterThanOrEqual(40);

		const ctx = await browser.newContext({
			storageState: undefined,
			viewport: MOBIL,
			serviceWorkers: 'block'
		});
		const gast = await ctx.newPage();
		let angelegt = false;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, username, password);
			angelegt = true;

			await gast.goto('/account');
			await gast
				.getByTestId('danger-zone-card')
				.getByRole('button', { name: 'Account löschen' })
				.click();
			const dialog = gast.getByRole('dialog', { name: 'Account löschen' });
			await expect(dialog).toBeVisible();

			// Setup-Wache: die volle Adresse steht ungekürzt im Knopftext.
			const knopf = dialog.getByTestId('delete-account-send-code');
			await expect(knopf).toBeVisible();
			expect(await knopf.textContent()).toContain(adresse);

			const m = await misstUeberlauf(dialog, 'delete-account-send-code');
			erwarteKeinenUeberlauf(m, 'Account löschen');
		} finally {
			if (angelegt) {
				await gast.request
					.post('/api/auth/account/delete', { data: { password } })
					.catch(() => {});
			}
			await ctx.close();
		}
	});

	test.describe('Positivkontrolle', () => {
		test.use({ viewport: MOBIL });

		test('Dialog „Auf allen Geräten abmelden" läuft nicht über (Messhelfer ist nicht immer rot)', async ({
			page
		}) => {
			await page.goto('/account');
			await page.getByRole('button', { name: 'Auf allen Geräten abmelden' }).click();
			const dialog = page.getByRole('dialog', { name: 'Auf allen Geräten abmelden' });
			await expect(dialog).toBeVisible();

			const m = await misstUeberlauf(dialog);
			erwarteKeinenUeberlauf(m, 'Auf allen Geräten abmelden');
			await dialog.getByRole('button', { name: 'Abbrechen' }).click();
		});
	});
});
