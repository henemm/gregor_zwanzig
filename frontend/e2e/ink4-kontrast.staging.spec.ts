// E2E (Staging) — Issue #2371 (Epic #2508 Strang B, ADR-0008): kein Text in den Anlege-Editoren
// und im Archiv ist mit `--g-ink-4` (#9a958a, 2,7:1) gefärbt; gesperrte Tabs und das deaktivierte
// „Speichern" halten WCAG AA (>= 4,5:1); beide Editoren sehen gleich aus.
// Spec: docs/specs/modules/ink4_kontrast_2371.md — AC-1, AC-2, AC-3, AC-5.
//
// Gemessen wird im Browser aus BERECHNETEN Werten (getComputedStyle), inkl. Alpha-Blending über
// alle Vorfahren-Opacities (Logik wie scripts/contrast_audit.py `contrast_ratio`).
//
// Ausführen (gegen Staging, aus frontend/, NACH Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.ink4-kontrast.staging.config.ts
import { test, expect, type Page } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 } });

const INK4 = 'rgb(154, 149, 138)';
const INK3 = 'rgb(107, 103, 92)';

/** Läuft im Browser: misst Kontrast eines Elements inkl. Opacity-Kette. */
async function messeKontrast(page: Page, selector: string, nth = 0) {
	return page.locator(selector).nth(nth).evaluate((el) => {
		const parse = (c: string) => {
			const m = c.match(/rgba?\(([^)]+)\)/);
			if (!m) return [0, 0, 0, 0];
			const p = m[1].split(',').map((x) => parseFloat(x));
			return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
		};
		const lin = (v: number) => {
			const s = v / 255;
			return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
		};
		const lum = (c: number[]) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
		const mix = (fg: number[], a: number, bg: number[]) => [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a));
		// Hintergrund: von außen nach innen übereinanderlegen, Start Weiß
		const kette: Element[] = [];
		for (let e: Element | null = el; e; e = e.parentElement) kette.unshift(e);
		let bg = [255, 255, 255];
		let opazitaet = 1;
		for (const e of kette) {
			const cs = getComputedStyle(e);
			const b = parse(cs.backgroundColor);
			if (b[3] > 0) bg = mix(b, b[3], bg);
			opazitaet *= parseFloat(cs.opacity);
		}
		const fg = parse(getComputedStyle(el).color);
		const textFarbe = mix(fg, fg[3] * opazitaet, bg);
		const l1 = lum(textFarbe);
		const l2 = lum(bg);
		const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
		return { ratio, farbe: getComputedStyle(el).color, opazitaet };
	});
}

/** AC-1: alle sichtbaren Textknoten — Farbe #9a958a außer Placeholder/disabled-Eingaben. */
async function ink4Treffer(page: Page): Promise<string[]> {
	return page.evaluate((ink4) => {
		const treffer: string[] = [];
		const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
		for (let n = walker.nextNode(); n; n = walker.nextNode()) {
			const text = (n.textContent ?? '').trim();
			const el = n.parentElement;
			if (!text || !el) continue;
			const r = el.getBoundingClientRect();
			const cs = getComputedStyle(el);
			if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden' || cs.display === 'none') continue;
			if (el.closest('script,style,svg')) continue;
			if (el.closest(':disabled')) continue;
			if (cs.color === ink4) treffer.push(`${el.tagName.toLowerCase()}: "${text.slice(0, 40)}"`);
		}
		return treffer;
	}, INK4);
}

const SEITEN = ['/compare/new', '/trips/new', '/archiv'];

for (const pfad of SEITEN) {
	test(`AC-1: ${pfad} hat keinen Textknoten in #9a958a`, async ({ page }) => {
		await page.goto(pfad);
		await page.waitForLoadState('networkidle');
		expect(await ink4Treffer(page)).toEqual([]);
	});
}

const TAB_SELEKTOR = '[role="tab"][aria-selected="false"]';

async function gesperrterTab(page: Page, pfad: string) {
	await page.goto(pfad);
	await page.waitForLoadState('networkidle');
	// gesperrt = trägt das Symbol ⊘ (bleibt auch ohne Opacity erkennbar)
	return page.locator(`${TAB_SELEKTOR}:visible`, { hasText: '⊘' }).first();
}

for (const pfad of ['/trips/new', '/compare/new']) {
	test(`AC-2: gesperrter Tab in ${pfad} hat >= 4,5:1 inkl. Opacity`, async ({ page }) => {
		const tab = await gesperrterTab(page, pfad);
		await expect(tab, 'es muss einen gesperrten Tab geben (Symbol ⊘)').toBeVisible();
		const m = await tab.evaluate((el) => {
			let o = 1;
			for (let e: Element | null = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity);
			return o;
		});
		expect(m, 'keine Zusatz-Opacity auf gesperrten Tabs').toBe(1);
		const k = await messeKontrast(page, `${TAB_SELEKTOR}:visible:has-text("⊘")`);
		expect(k.ratio).toBeGreaterThanOrEqual(4.5);
	});
}

test('AC-3: deaktiviertes Speichern in /trips/new — >= 4,5:1, aria-disabled, Klick ohne Wirkung', async ({ page }) => {
	await page.goto('/trips/new');
	await page.waitForLoadState('networkidle');
	const speichern = page.locator('[data-testid="tn-mobile-route-cta"] button');
	await expect(speichern).toBeAttached();
	await expect(speichern).toHaveAttribute('aria-disabled', 'true');
	const k = await messeKontrast(page, '[data-testid="tn-mobile-route-cta"] button');
	expect(k.ratio).toBeGreaterThanOrEqual(4.5);
	const anfragen: string[] = [];
	page.on('request', (r) => {
		if (r.method() === 'POST' && r.url().includes('/api/trips')) anfragen.push(r.url());
	});
	const vorher = page.url();
	await speichern.click({ force: true });
	await page.waitForTimeout(500);
	expect(page.url()).toBe(vorher);
	expect(anfragen).toEqual([]);
});

test('AC-5: Trip- und Vergleichs-Editor haben dieselbe Textfarbe und Tab-Behandlung', async ({ page }) => {
	const lies = async (pfad: string) => {
		const tab = await gesperrterTab(page, pfad);
		await expect(tab).toBeVisible();
		const tabStil = await tab.evaluate((el) => {
			const cs = getComputedStyle(el);
			let o = 1;
			for (let e: Element | null = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity);
			return { farbe: cs.color, opazitaet: o, cursor: cs.cursor };
		});
		return tabStil;
	};
	const trip = await lies('/trips/new');
	const vergleich = await lies('/compare/new');
	expect(trip.farbe).toBe(INK3);
	expect(vergleich.farbe).toBe(INK3);
	expect(vergleich).toEqual(trip);
});

// ── Issue #2896 (Folge aus #2371) — Logo-Punkt der Wortmarke und Avatar-Initialen ──────────────
// Spec: docs/specs/modules/fix_2896_kontrast_zierpunkt_avatar.md — AC-1, AC-2, AC-3 (AC-6 = Bestand oben).

/** Punkt-Span der Sidebar-Wortmarke: Kind-Span mit Text genau "." in der Wortmarke. */
const LOGO_PUNKT = '[data-testid="desktop-sidebar"] [data-testid="brand-wordmark"] span:text-is(".")';

test.describe('#2896 AC-1: Logo-Punkt der Desktop-Sidebar (1280x800)', () => {
	test.use({ viewport: { width: 1280, height: 800 } });
	for (const pfad of SEITEN) {
		test(`${pfad}: Wortmarken-Punkt >= 4,5:1 und nicht #9a958a`, async ({ page }) => {
			await page.goto(pfad);
			await page.waitForLoadState('networkidle');
			const punkt = page.locator(LOGO_PUNKT).first();
			await expect(punkt, 'Wortmarken-Punkt in der Desktop-Sidebar').toBeVisible();
			const k = await messeKontrast(page, LOGO_PUNKT);
			expect(k.farbe).not.toBe(INK4);
			expect(k.ratio, `Punkt ${k.farbe}`).toBeGreaterThanOrEqual(4.5);
		});
	}
});

test('#2896 AC-2 + AC-3: Avatar-Initialen in Konto-Kreis und Konto-Blatt >= 4,5:1, ein Muster', async ({ page }) => {
	await page.goto('/archiv');
	await page.waitForLoadState('networkidle');
	const kreis = page.locator('[data-testid="konto-kreis"] .konto-kreis__avatar');
	await expect(kreis).toBeVisible();
	const kKreis = await messeKontrast(page, '[data-testid="konto-kreis"] .konto-kreis__avatar');
	expect(kKreis.ratio, `Konto-Kreis ${kKreis.farbe}`).toBeGreaterThanOrEqual(4.5);
	const bgKreis = await kreis.evaluate((el) => getComputedStyle(el).backgroundColor);

	await page.locator('[data-testid="konto-kreis"]').click();
	const blattAvatar = page.locator('[data-testid="konto-sheet"] .konto__avatar');
	await expect(blattAvatar).toBeVisible();
	const kBlatt = await messeKontrast(page, '[data-testid="konto-sheet"] .konto__avatar');
	expect(kBlatt.ratio, `Konto-Blatt ${kBlatt.farbe}`).toBeGreaterThanOrEqual(4.5);
	const bgBlatt = await blattAvatar.evaluate((el) => getComputedStyle(el).backgroundColor);
	expect(bgBlatt, 'gleicher Avatar-Grund in Kreis und Blatt').toBe(bgKreis);
	expect(kBlatt.farbe).toBe(kKreis.farbe);
});
