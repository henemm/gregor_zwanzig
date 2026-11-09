// E2E — Issue #2794 S3a, Teil-PR 2 „Leiste und Umleitung" (Epic #2791), aus Nutzersicht.
//
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md
// Abgedeckt (Browser-Hälfte; die Kern-Schicht steht in src/lib/components/shared/__tests__/s3a2794_*):
//   AC-1/AC-2 — Hub-Leiste je Art: genau Übersicht · Etappen|Orte · Wetter · Zustellung, DE und EN
//               (EN über einen Zweitnutzer mit Sprache en, Admin bleibt unberührt); Orte-Badge = 3.
//   AC-3      — Desktop: genau EINE Grundlinie, aktiver Reiter 600 mit 2px-Unterstrich in Akzentfarbe,
//               Badge neutral Mono 10 px (kein Accent, kein Kreis), kein data-slot="segmented" an der Leiste.
//   AC-36     — Desktop ≥ 1024 px: h1 30–38 px in beiden Kontexten (Regressionswächter, heute 38 px).
//   AC-4      — Mobil 390 px: Pill-Form bleibt, alle vier Reiter antippbar, Panel wechselt.
//   AC-5      — Tabelle Alt-Kennungen je Trip und Vergleich: richtiger Reiter aktiv, Adresszeile danach
//               mit der neuen Kennung (#versand-Anker bleibt erhalten).
//   AC-6      — Anlege-Schritte /trips/new und /compare/new.
// Nicht hier: AC-7/AC-8 (Inventar und Speicherweg) stehen in s3a2794-zustellung-inventar-speicherweg.spec.ts
// (gleiche Config); AC-2.T1/T3/T4 Request-Vergleich in /e2e-verify.
//
// Daten: nur Wegwerf-Trips/-Vergleiche/-Orte (Präfix E2E-GZ-), Aufräumen im finally.
// Kein fester Schlaf, kein networkidle. NIE gegen Produktion (prodUrlGuard im Setup-Projekt).
//
// Ausführen gegen Staging (Zugangsdaten aus /home/hem/gregor_zwanzig_staging/.env):
//   cd frontend && npx playwright test --config playwright.2794-s3a2.staging.config.ts [-g "AC-1|AC-5"]

import { test, expect, type APIRequestContext, type Page, type Locator } from '@playwright/test';
import { createTestLocation, HUB_KINDS, HUB_SEL, seedHub, testMitZustellbaremZiel, type HubKind, type SeededHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };
const AKZENT = 'rgb(196, 90, 42)';

const SOLL_IDS: Record<HubKind, string[]> = {
	route: ['uebersicht', 'etappen', 'wetter', 'zustellung'],
	vergleich: ['uebersicht', 'orte', 'wetter', 'zustellung']
};
const SOLL_LABEL: Record<'de' | 'en', [string, string]> = { de: ['Wetter', 'Zustellung'], en: ['Weather', 'Delivery'] };

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

/** Trip mit drei Etappen bzw. Vergleich mit drei EIGENEN Orten (auch für Zweitnutzer gültig). */
async function seedDrei(request: APIRequestContext, kind: HubKind): Promise<SeededHub & { orte: string[] }> {
	if (kind === 'route') {
		const hub = await seedHub(request, kind, {
			extra: {
				stages: [
					{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
					{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
					{ id: 's3', name: 'Tag 3', date: '2027-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
				]
			}
		});
		return { ...hub, orte: [] };
	}
	const orte: string[] = [];
	for (let i = 0; i < 3; i++) orte.push((await createTestLocation(request, { lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 })).id);
	const hub = await seedHub(request, kind, { extra: { location_ids: orte } });
	return {
		...hub,
		orte,
		aufraeumen: async () => {
			await hub.aufraeumen();
			for (const o of orte) await request.delete(`/api/locations/${o}`).catch(() => {});
		}
	};
}

const hubPfad = (kind: HubKind, id: string) => `${HUB_SEL[kind].liste.url}/${id}`;

/** Reiter der Hub-Leiste in DOM-Reihenfolge (nur sichtbare, Scope Reiterliste). */
const leistenReiter = (page: Page, kind: HubKind): Locator =>
	page.getByTestId(HUB_SEL[kind].reiterListe).getByRole('tablist').first().getByRole('tab');

async function reiterIds(page: Page, kind: HubKind): Promise<string[]> {
	const tabs = leistenReiter(page, kind);
	await expect(tabs.first()).toBeVisible({ timeout: 15_000 });
	const out: string[] = [];
	for (let i = 0; i < (await tabs.count()); i++) {
		out.push(((await tabs.nth(i).getAttribute('data-testid')) ?? '').replace(`${HUB_SEL[kind].reiter}-`, ''));
	}
	return out;
}

const reiter = (page: Page, kind: HubKind, id: string) => page.locator(`[data-testid="${HUB_SEL[kind].reiter}-${id}"]:visible`).first();
const panel = (page: Page, kind: HubKind, id: string) => page.locator(`[data-testid="${HUB_SEL[kind].panel}-${id}"]:visible`).first();

async function oeffne(page: Page, kind: HubKind, id: string, suffix = ''): Promise<void> {
	await page.goto(`${hubPfad(kind, id)}${suffix}`);
	await expect(page.getByTestId(HUB_SEL[kind].reiterListe)).toBeVisible({ timeout: 15_000 });
}

// ─── AC-1 / AC-2: Reiterliste DE ─────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-1/AC-2 (${kind}): Hub-Leiste genau ${SOLL_IDS[kind].join(' · ')} (DE), Punkte-Badge 3`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffne(page, kind, hub.id);
			expect(await reiterIds(page, kind)).toEqual(SOLL_IDS[kind]);
			await expect(reiter(page, kind, 'wetter')).toContainText(SOLL_LABEL.de[0]);
			await expect(reiter(page, kind, 'zustellung')).toContainText(SOLL_LABEL.de[1]);
			for (const alt of ['wetter-metriken', 'wertebereiche', 'alarme']) {
				await expect(page.locator(`[data-testid="${HUB_SEL[kind].reiter}-${alt}"]`)).toHaveCount(0);
			}
			await expect(reiter(page, kind, HUB_SEL[kind].punkteReiter)).toContainText('3');
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-1 / AC-2: Reiterliste EN (Zweitnutzer, Sprache per Profil) ──────────

for (const kind of HUB_KINDS) {
	testMitZustellbaremZiel(`AC-1/AC-2 (${kind}): Hub-Leiste auf Englisch — Weather · Delivery`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
			expect(res.ok(), `Sprache en setzen: HTTP ${res.status()}`).toBeTruthy();
			await oeffne(page, kind, hub.id);
			expect(await reiterIds(page, kind)).toEqual(SOLL_IDS[kind]);
			await expect(reiter(page, kind, 'wetter')).toHaveText(new RegExp(`^\\s*${SOLL_LABEL.en[0]}\\s*$`));
			await expect(reiter(page, kind, 'zustellung')).toHaveText(new RegExp(`^\\s*${SOLL_LABEL.en[1]}\\s*$`));
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
		}
	});
}

// ─── AC-3: Leistenoptik am Desktop (gemessen) ────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-3 (${kind}): eine Grundlinie, aktiv 600 + 2px Akzent, Badge neutral Mono 10px, kein Segmented`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffne(page, kind, hub.id, '?tab=uebersicht');
			const liste = page.getByTestId(HUB_SEL[kind].reiterListe);
			await expect(liste.locator('[data-slot="segmented"]'), 'Segmented-Box an der Leiste').toHaveCount(0);
			expect(await liste.evaluate((el) => el.matches('[data-slot="segmented"]'))).toBe(false);

			// Genau EINE sichtbare waagerechte Linie: Leistenwurzel + alle Nachfahren ausser dem aktiven Reiter.
			const linien = await liste.evaluate((root) => {
				const sichtbar = (cs: CSSStyleDeclaration) =>
					parseFloat(cs.borderBottomWidth) > 0 && cs.borderBottomStyle !== 'none' && !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)|transparent/.test(cs.borderBottomColor);
				const alle = [root, ...Array.from(root.querySelectorAll('*'))].filter(
					(el) => el.getAttribute('aria-selected') !== 'true' && !el.closest('[aria-selected="true"]') && !el.closest('[role="tabpanel"], [data-testid*="-panel-"]')
				);
				return alle.filter((el) => sichtbar(getComputedStyle(el))).map((el) => `${el.tagName}.${el.className}`);
			});
			expect(linien, `sichtbare Unterlinien: ${JSON.stringify(linien)}`).toHaveLength(1);

			const aktiv = reiter(page, kind, 'uebersicht');
			await expect(aktiv).toHaveAttribute('aria-selected', 'true');
			const a = await aktiv.evaluate((el) => {
				const cs = getComputedStyle(el);
				return { w: cs.fontWeight, bw: cs.borderBottomWidth, bc: cs.borderBottomColor };
			});
			expect(a.w, 'aktiver Reiter nicht 600').toBe('600');
			expect(a.bw, 'Unterstrich nicht 2px').toBe('2px');
			expect(a.bc, 'Unterstrich nicht Akzent').toBe(AKZENT);

			const badge = reiter(page, kind, HUB_SEL[kind].punkteReiter).locator('span', { hasText: /^\s*3\s*$/ }).last();
			await expect(badge).toBeVisible();
			const b = await badge.evaluate((el) => {
				const cs = getComputedStyle(el);
				return { bg: cs.backgroundColor, fam: cs.fontFamily, size: cs.fontSize };
			});
			expect(b.bg, 'Badge Akzent-gefüllt').not.toBe(AKZENT);
			expect(b.fam, 'Badge nicht Mono').toMatch(/JetBrains Mono|mono/i);
			expect(b.size, 'Badge nicht 10px').toBe('10px');
			// „keine orangen Kreise": Farbe ist die Aussage (oben), die Form legt das Atomic-Design-Soll fest
			// (Fresh-Eyes-Abgleich gegen current/soll/*.png in /e2e-verify), daher hier kein Form-Festwert.
			expect(b.bg, 'Badge-Grund nicht neutral (--g-paper-deep)').toBe('rgb(236, 234, 217)');
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-36: Seitenüberschrift am Desktop (Regressionswächter) ────────────────

for (const kind of HUB_KINDS) {
	for (const breite of [{ width: 1024, height: 800 }, DESKTOP]) {
		test(`AC-36 (${kind}, ${breite.width} px): h1 zwischen 30 und 38 px`, async ({ page }) => {
			await page.setViewportSize(breite);
			const hub = await seedDrei(page.request, kind);
			try {
				await oeffne(page, kind, hub.id);
				const h1 = page.getByRole('heading', { level: 1 }).first();
				await expect(h1).toBeVisible();
				const px = parseFloat(await h1.evaluate((el) => getComputedStyle(el).fontSize));
				expect(px).toBeGreaterThanOrEqual(30);
				expect(px).toBeLessThanOrEqual(38);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

// ─── AC-4: Mobil Pill, alle vier Reiter antippbar ───────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-4 (${kind}): Mobil — vier Reiter, jeder antippbar, Panel wechselt`, async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const hub = await seedDrei(page.request, kind);
		try {
			await oeffne(page, kind, hub.id, '?tab=uebersicht');
			expect(await reiterIds(page, kind)).toEqual(SOLL_IDS[kind]);
			for (const id of [...SOLL_IDS[kind]].reverse()) {
				const r = reiter(page, kind, id);
				await r.scrollIntoViewIfNeeded();
				await r.tap().catch(() => r.click());
				await expect(r).toHaveAttribute('aria-selected', 'true');
				await expect(panel(page, kind, id)).toBeVisible({ timeout: 10_000 });
				const box = await r.boundingBox();
				expect(box!.height, `${id}: Tippfläche`).toBeGreaterThanOrEqual(44);
			}
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-5: Alt-Kennungen (Tabelle je Trip und Vergleich) ─────────────────────

const ALT: Array<[string, 'wetter' | 'zustellung', boolean]> = [
	['wetter-metriken', 'wetter', false],
	['wertebereiche', 'wetter', false],
	['layout', 'wetter', false],
	['alarme', 'zustellung', false],
	['versand', 'zustellung', true]
];

for (const kind of HUB_KINDS) {
	test(`AC-5 (${kind}): alte Adressen landen in Wetter bzw. Zustellung, Adresszeile zeigt die neue Kennung`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedDrei(page.request, kind);
		try {
			const faelle: Array<[string, 'wetter' | 'zustellung', boolean]> = [
				...ALT,
				// „auch #versand": Anker gewinnt gegen die Reiterkennung
				['wetter-metriken#versand', 'zustellung', true]
			];
			for (const [alt, neu, anker] of faelle) {
				await oeffne(page, kind, hub.id, `?tab=${alt}`);
				await expect(reiter(page, kind, neu), `?tab=${alt}: Reiter ${neu} nicht aktiv`).toHaveAttribute('aria-selected', 'true', { timeout: 15_000 });
				await expect(panel(page, kind, neu)).toBeVisible({ timeout: 15_000 });
				await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { message: `?tab=${alt}: Adresszeile` }).toBe(neu);
				if (anker) await expect.poll(() => new URL(page.url()).hash).toBe('#versand');
			}
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-6: Anlege-Schritte ───────────────────────────────────────────────────

async function anlegeSchritte(page: Page): Promise<string[]> {
	const tabs = page.locator('main [role="tab"]:visible, [role="tab"]:visible');
	await expect(tabs.first()).toBeVisible({ timeout: 15_000 });
	const texte = await tabs.allInnerTexts();
	return texte.map((t) => t.replace(/[⊘✓]/g, '').replace(/\boptional\b/i, '').replace(/\s+/g, ' ').trim()).filter(Boolean);
}

test('AC-6 (route): /trips/new — Route · Etappen · Wegpunkte · Wetter · Zustellung', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto('/trips/new');
	const s = await anlegeSchritte(page);
	expect(s.map((x) => x.replace(/ .*$/, ''))).toEqual(['Route', 'Etappen', 'Wegpunkte', 'Wetter', 'Zustellung']);
	for (const alt of ['Wetter-Metriken', 'Wertebereiche', 'Alarme']) expect(s.join('|')).not.toContain(alt);
});

test('AC-6 (vergleich): /compare/new — Vergleich · Orte · Wetter · Zustellung', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto('/compare/new');
	const s = await anlegeSchritte(page);
	expect(s.map((x) => x.replace(/ .*$/, ''))).toEqual(['Vergleich', 'Orte', 'Wetter', 'Zustellung']);
	for (const alt of ['Wetter-Metriken', 'Wertebereiche', 'Alarme']) expect(s.join('|')).not.toContain(alt);
});
