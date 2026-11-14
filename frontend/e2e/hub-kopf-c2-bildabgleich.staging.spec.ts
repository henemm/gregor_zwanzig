// Abnahme — Issue #2980, Fix-Loop Bildabgleich Runde 1 der Scheibe c2 (#2913): Seitenkopf, Reiter,
// Vorlage-Karte und Abschnittskopf Wetter nach Mockup (Trip + Orts-Vergleich).
// Spec: docs/specs/modules/feat_2913_c2_seitenkopf.md — AC-16 bis AC-18, AC-20, AC-21, AC-23 bis AC-28
// und Nachtrag #3003 AC-32 bis AC-34 (gemessene Geometrie, Bedienart Maus/Finger)
// (berechnete Stile im echten Browser) und AC-30 (Aufnahmen für den `mockup-bildpruefer`, Runde 2).
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html.
//
// Acht Zustände: Trip/Orte × DE/EN × 1280×900/390×844, jeweils Reiter Wetter. Aufnahmen landen in
// docs/artifacts/feature-2980-c2-bildabgleich-r1/ (oder $BILD_DIR): mockup-<ctx>-de-<breite>.png
// (Mockup nur Deutsch, per file://) und staging-<ctx>-<lang>-<breite>.png.
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste.
// Config (legt der Developer an, Vorlage playwright.2913-c2-seitenkopf.staging.config.ts mit
// testMatch /hub-kopf-c2-bildabgleich\.staging\.spec\.ts/):
//   cd frontend && npx playwright test --config playwright.2980-c2-bildabgleich.staging.config.ts
//
// Unit-Gegenstück (Kaskade aus den echten CSS-Quellen): src/lib/components/shared/hub-kopf/__tests__/
// hub_kopf_c2_bildabgleich.test.ts — dort steht der VERTRAG (testids, Regeln).
// Farbwerte Hellmodus (app.css): --g-ink #1a1a18, --g-ink-3 #6b675c, --g-accent #c45a2a,
// --g-accent-deep #8c3e1a, --g-rule #d8d3c2, --g-rule-soft #e7e2d3, --g-paper #f6f4ee,
// --g-paper-deep #ecead9, --g-good #3d6b3a.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { HUB_KINDS, HUB_KOPF_SEL, type HubKind } from './helpers';
import { DESKTOP, MOBIL, WT, oeffneWetter, seedWetter } from './s3a2794-teil3.helpers';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const MOCKUP = 'file://' + path.resolve(HIER, '..', '..', 'docs', 'context', 'einstellungen_neu', 'seiten', 'mockup-hub-fassung3.html');
const ARTEFAKTE = path.resolve(HIER, '..', '..', 'docs', 'artifacts', 'feature-2980-c2-bildabgleich-r1');

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];
const VIEWPORTS = [
	['desktop', DESKTOP],
	['mobil', MOBIL]
] as const;

const RGB = {
	ink: 'rgb(26, 26, 24)',
	ink3: 'rgb(107, 103, 92)',
	accent: 'rgb(196, 90, 42)',
	accentDeep: 'rgb(140, 62, 26)',
	rule: 'rgb(216, 211, 194)',
	ruleSoft: 'rgb(231, 226, 211)',
	paper: 'rgb(246, 244, 238)',
	paperDeep: 'rgb(236, 234, 217)',
	good: 'rgb(61, 107, 58)'
};
const LANG_NAME: Record<HubKind, string> = {
	route: 'GR221 Mallorca – Ruta de Pedra en Sec von Port d’Andratx bis Pollença über Deià und Lluc',
	vergleich: 'Skitouren Tirol – Zillertaler und Tuxer Alpen mit Gerlospass, Hochfügen und Kühtai'
};
const KTX: Record<HubKind, 'trip' | 'orte'> = { route: 'trip', vergleich: 'orte' };

test.describe.configure({ mode: 'serial' });

// ── Werkzeuge ────────────────────────────────────────────────────────────────

function bildOrdner(): string {
	const d = process.env.BILD_DIR ?? ARTEFAKTE;
	mkdirSync(d, { recursive: true });
	return d;
}

/** Ganzseitenaufnahme trotz `.h-screen`/`main.overflow-auto` (Muster fix2913-metrikliste-mockup.staging.spec.ts). */
async function ganzseite(page: Page, datei: string): Promise<void> {
	await page.evaluate(() => {
		const ziele = [document.documentElement, document.body, ...Array.from(document.querySelectorAll<HTMLElement>('.h-screen, main'))];
		for (const el of ziele) {
			el.dataset.gzAufnahme = el.getAttribute('style') ?? '';
			el.style.setProperty('height', 'auto', 'important');
			el.style.setProperty('max-height', 'none', 'important');
			el.style.setProperty('overflow', 'visible', 'important');
		}
	});
	try {
		await page.screenshot({ path: datei, fullPage: true });
	} finally {
		await page.evaluate(() => {
			for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-gz-aufnahme]'))) {
				const alt = el.dataset.gzAufnahme ?? '';
				if (alt) el.setAttribute('style', alt);
				else el.removeAttribute('style');
				delete el.dataset.gzAufnahme;
			}
		});
	}
}

const sichtbar = (page: Page | Locator, id: string): Locator => page.locator(`[data-testid="${id}"]:visible`).first();

type Stil = Record<string, string>;
const stil = (l: Locator, props: string[]): Promise<Stil> =>
	l.evaluate((el, ps) => {
		const c = getComputedStyle(el);
		const r = el.getBoundingClientRect();
		const aus: Record<string, string> = { _hoehe: String(r.height), _breite: String(r.width), _mitteY: String(r.top + r.height / 2) };
		for (const p of ps) aus[p] = c.getPropertyValue(p);
		return aus;
	}, props);

/** WCAG-Kontrast zweier rgb()-Werte (deckend). */
function kontrast(a: string, b: string): number {
	const lum = (s: string) => {
		const [r, g, bl] = (s.match(/[\d.]+/g) ?? []).slice(0, 3).map((x) => Number(x) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
	};
	const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
	return (x + 0.05) / (y + 0.05);
}

async function seed(page: Page, kind: HubKind) {
	return seedWetter(page.request, kind, {
		extra: kind === 'route' ? { name: LANG_NAME.route, shortcode: 'MLC', region: 'Mallorca' } : { name: LANG_NAME.vergleich }
	});
}

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang}: HTTP ${res.status()}`).toBeTruthy();
}

test.afterAll(async ({ request }) => {
	await request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
});

// ── Berechnete Stile je Zustand (AC-16 … AC-28 ohne AC-19/22/29/31) ──────────

for (const kind of HUB_KINDS) {
	for (const lang of SPRACHEN) {
		for (const [vp, groesse] of VIEWPORTS) {
			test(`#2980 ${kind} ${lang} ${vp}: Kopf, Reiter, Vorlage-Karte, Abschnittskopf nach Mockup (berechnete Stile)`, async ({ page }) => {
				await page.setViewportSize(groesse);
				await sprache(page, lang);
				const hub = await seed(page, kind);
				try {
					const reiter = await oeffneWetter(page, kind, hub.id);
					const leiste = sichtbar(page, HUB_KOPF_SEL.leiste);

					// AC-16: Knopf „Test schicken ▾“ Akzent mit Fläche --g-accent-deep, Kontrast ≥ 4,5
					const knopf = sichtbar(leiste, 'subscription-hub-send');
					await expect(knopf).toHaveAttribute('data-variant', 'accent');
					const k = await stil(knopf, ['background-color', 'color']);
					expect(k['background-color'], 'AC-16: Fläche --g-accent-deep').toBe(RGB.accentDeep);
					expect(kontrast(k.color, k['background-color']), 'AC-16: Kontrast Schrift/Fläche').toBeGreaterThanOrEqual(4.5);

					// AC-25: Kebab ghost, Rahmen --g-rule, Handy ≥ 44 px, vor dem Knopf
					const kebab = sichtbar(leiste, 'subscription-kebab');
					const kb = await stil(kebab, ['background-color', 'border-top-color', 'border-top-width', 'border-top-style']);
					expect(kb['background-color'], 'AC-25: Kebab transparent').toBe('rgba(0, 0, 0, 0)');
					expect([kb['border-top-style'], kb['border-top-width'], kb['border-top-color']], 'AC-25: Kebab-Rahmen --g-rule').toEqual(['solid', '1px', RGB.rule]);
					if (vp === 'mobil') {
						expect(Number(kb._hoehe), 'AC-25: Kebab-Höhe').toBeGreaterThanOrEqual(44);
						expect(Number(kb._breite), 'AC-25: Kebab-Breite').toBeGreaterThanOrEqual(44);
					}
					const reihenfolge = await leiste.evaluate((el) => {
						const alle = Array.from(el.querySelectorAll('[data-testid="subscription-kebab"], [data-testid="subscription-hub-send"]')).filter((x) => (x as HTMLElement).offsetParent !== null);
						return alle.map((x) => x.getAttribute('data-testid'));
					});
					expect(reihenfolge, 'AC-25: Kebab vor „Test schicken“').toEqual(['subscription-kebab', 'subscription-hub-send']);

					// AC-23/AC-24: Kopfband
					const krumen = sichtbar(page, HUB_KOPF_SEL.breadcrumb);
					const kr = await stil(krumen, ['font-family', 'font-size', 'text-transform', 'color', 'text-overflow', 'white-space']);
					expect(kr['font-family'], 'AC-23: Brotkrumen Mono').toMatch(/mono/i);
					expect([kr['font-size'], kr['text-transform'], kr.color], 'AC-23: 11 px, uppercase, --g-ink-3').toEqual(['11px', 'uppercase', RGB.ink3]);
					expect(kr['text-overflow'], 'AC-24: keine Ellipsis').not.toBe('ellipsis');
					const nameEl = krumen.locator(':scope *').filter({ hasText: LANG_NAME[kind] }).last();
					await expect(nameEl, 'AC-24: voller Name im Breadcrumb').toHaveText(LANG_NAME[kind]);
					await expect(krumen, 'AC-24: kein Kürzel').not.toContainText('MLC');
					const nm = await stil(nameEl, ['color', 'font-weight']);
					expect([nm.color, nm['font-weight']], 'AC-23: Name --g-ink 500').toEqual([RGB.ink, '500']);
					await expect(page.locator('.back-mobil, [data-testid="back-mobil"]'), 'AC-24: kein Zurück-Pfeil').toHaveCount(0);
					await expect(leiste.locator('[aria-label^="Zurück"], [aria-label^="Back"]').filter({ visible: true }), 'AC-24: kein Zurück-Pfeil').toHaveCount(0);
					const ls = await stil(leiste, ['border-bottom-color', 'border-bottom-width']);
					expect([ls['border-bottom-width'], ls['border-bottom-color']], 'AC-23: Linie --g-rule-soft').toEqual(['1px', RGB.ruleSoft]);
					const quer = await page.evaluate(() => {
						const el = document.scrollingElement ?? document.documentElement;
						return el.scrollWidth - el.clientWidth;
					});
					expect(quer, 'AC-24: Seite läuft nicht horizontal über').toBeLessThanOrEqual(0);

					// AC-20: Meta-Zeile
					const meta = await stil(sichtbar(page, 'hub-kopf-meta'), ['font-family', 'font-size', 'color']);
					expect(meta['font-family'], 'AC-20: Meta Mono').toMatch(/mono/i);
					expect([meta['font-size'], meta.color], 'AC-20: 13 px --g-ink-3').toEqual(['13px', RGB.ink3]);

					// AC-21: Status-Pill gefüllt ohne Rahmen
					const pill = sichtbar(page, 'trip-detail-status-badge');
					const status = await pill.getAttribute('data-status');
					const pl = await stil(pill, ['border-top-width', 'background-color', 'color', 'text-transform', 'font-size', 'font-family']);
					expect(pl['border-top-width'], 'AC-21: kein Rahmen').toBe('0px');
					expect([pl['text-transform'], pl['font-size']], 'AC-21: uppercase 11 px').toEqual(['uppercase', '11px']);
					expect(pl['font-family'], 'AC-21: Mono').toMatch(/mono/i);
					if (status === 'active') {
						expect(pl.color, 'AC-21: aktiv --g-good').toBe(RGB.good);
						expect(pl['background-color'], 'AC-21: aktiv hellgrün').toMatch(/^rgba\(61, 107, 58, 0\.\d+\)$/);
					} else {
						expect([pl.color, pl['background-color']], `AC-21: ${status} neutral`).toEqual([RGB.ink3, RGB.paperDeep]);
					}

					// AC-17/AC-18: Reiter als Text-Reiter mit Unterstrich, gleiche Optik auf beiden Breiten
					const band = page.locator('[role="tablist"].mtabbar:visible').first();
					const bd = await stil(band, ['border-bottom-color', 'border-bottom-width', 'overflow-x']);
					expect([bd['border-bottom-width'], bd['border-bottom-color']], 'AC-17: Grundlinie --g-rule').toEqual(['1px', RGB.rule]);
					const aktiv = band.locator('[role="tab"][data-state="active"]').first();
					const inaktiv = band.locator('[role="tab"][data-state="inactive"]').first();
					const ak = await stil(aktiv, ['color', 'font-weight', 'border-bottom-width', 'border-bottom-color', 'background-color', 'border-top-width']);
					const ik = await stil(inaktiv, ['color', 'font-weight', 'background-color', 'border-top-width']);
					expect([ak.color, ak['font-weight'], ak['border-bottom-width'], ak['border-bottom-color']], 'AC-17: aktiv --g-ink 600, 2px --g-accent').toEqual([RGB.ink, '600', '2px', RGB.accent]);
					expect([ik.color, ik['font-weight']], 'AC-17: inaktiv --g-ink-3 500').toEqual([RGB.ink3, '500']);
					for (const [s, was] of [[ak, 'aktiv'], [ik, 'inaktiv']] as const) {
						expect(s['background-color'], `AC-17: ${was} ohne Pillen-Fläche`).toBe('rgba(0, 0, 0, 0)');
						expect(s['border-top-width'], `AC-17: ${was} ohne Pillen-Rahmen`).toBe('0px');
					}
					if (vp === 'mobil') {
						expect(['auto', 'scroll'], 'AC-18: Band wischbar').toContain(bd['overflow-x']);
						for (const t of await band.locator('[role="tab"]').all()) expect(Number((await stil(t, []))._hoehe), 'AC-18: Tippfläche').toBeGreaterThanOrEqual(44);
						const letzter = band.locator('[role="tab"]').last();
						await letzter.scrollIntoViewIfNeeded();
						await expect(letzter, 'AC-18: letzter Reiter per Wischen erreichbar').toBeInViewport();
					}

					// AC-26/AC-27: Vorlage-Karte
					const picker = sichtbar(reiter, WT.picker);
					const pk = await stil(picker, ['border-top-color', 'border-top-style', 'background-color', 'font-size', 'font-weight']);
					expect([pk['border-top-style'], pk['border-top-color']], 'AC-26: Wähler-Rahmen --g-rule').toEqual(['solid', RGB.rule]);
					expect([pk['background-color'], pk['font-size'], pk['font-weight']], 'AC-26: Grund --g-paper, 15 px/600').toEqual([RGB.paper, '15px', '600']);
					const zusatz = sichtbar(reiter, WT.pickerStatus);
					const zs = await stil(zusatz, ['font-family', 'font-size', 'color']);
					expect(zs['font-family'], 'AC-26: Zusatz Mono').toMatch(/mono/i);
					expect([zs['font-size'], zs.color], 'AC-26: Zusatz 11 px --g-ink-3').toEqual(['11px', RGB.ink3]);
					const karte = reiter.locator('[data-abschnitt="vorlage"]:visible').first();
					const kt = await stil(karte, ['align-items']);
					expect(kt['align-items'], 'AC-27: Kartenzeile mittig').toBe('center');
					const speichern = sichtbar(reiter, WT.alsEigene);
					if (vp === 'desktop') {
						const sp = await stil(speichern, []);
						expect(Math.abs(Number(sp._mitteY) - Number(kt._mitteY)), 'AC-27: Speichern-Knopf vertikal mittig zur Karte').toBeLessThanOrEqual(2);
					} else {
						// Handy: die Karte bricht um; der Knopf bleibt ganz im Bild (kein horizontales Überlaufen).
						const rechts = await speichern.evaluate((el) => el.getBoundingClientRect().right);
						expect(rechts, 'AC-27: Speichern-Knopf läuft am Handy nicht über').toBeLessThanOrEqual(groesse.width);
						await expect(speichern).toBeInViewport();
					}

					// AC-28: Abschnittskopf Wetter
					const erklaer = sichtbar(reiter, WT.erklaer);
					const ek = await stil(erklaer, ['max-width', 'font-size', 'color']);
					expect(ek['max-width'], 'AC-28: max-width gesetzt (68ch)').not.toBe('none');
					expect(Number(ek._breite), 'AC-28: Erklärtext ≤ max-width').toBeLessThanOrEqual(parseFloat(ek['max-width']) + 0.5);
					expect([ek['font-size'], ek.color], 'AC-28: 13 px --g-ink-3').toEqual(['13px', RGB.ink3]);
					const kopf = erklaer.locator('xpath=..');
					const kf = await stil(kopf, ['border-bottom-color', 'border-bottom-width', 'padding-bottom']);
					expect([kf['border-bottom-width'], kf['border-bottom-color'], kf['padding-bottom']], 'AC-28: Linie --g-rule-soft, 12 px').toEqual(['1px', RGB.ruleSoft, '12px']);
				} finally {
					await hub.aufraeumen();
				}
			});
		}
	}
}

// ── #3003 AC-32 … AC-34: gemessene Geometrie (Vorlagen-Wähler, Handy-Reiterleiste) ─────
// Spec-Nachtrag „Rest Bildabgleich Runde 2 (#3003)“. Bedienart statt Breite (PO 14.11.2026):
// Maus = Desktop-Kontext ohne Touch (pointer: fine), Finger = Kontext mit hasTouch/isMobile
// (pointer: coarse). Gemessen im echten Browser gegen Staging, Trip und Orte, DE und EN.

type Geo = { hoehe: number; oben: number; unten: number; links: number; rechts: number; textOben: number };
/** Rahmen und Inhaltsbox (Vorlagenname + „▾ …“) des Wählers; oben/unten = Abstand Inhalt ↔ Rahmenkante. */
const wahlGeo = (picker: Locator): Promise<Geo> =>
	picker.evaluate((el) => {
		const r = el.getBoundingClientRect();
		const c = getComputedStyle(el);
		const kinder = Array.from(el.children) as HTMLElement[];
		const boxen = kinder.map((k) => {
			const rg = document.createRange();
			rg.selectNodeContents(k);
			return rg.getBoundingClientRect();
		}).filter((b) => b.height > 0);
		const top = Math.min(...boxen.map((b) => b.top));
		const bottom = Math.max(...boxen.map((b) => b.bottom));
		return {
			hoehe: r.height,
			oben: top - r.top,
			unten: r.bottom - bottom,
			links: parseFloat(c.paddingLeft),
			rechts: parseFloat(c.paddingRight),
			textOben: top
		};
	});

async function pruefeWaehler(page: Page, kind: HubKind, lang: Lang, finger: boolean): Promise<void> {
	await sprache(page, lang);
	const hub = await seed(page, kind);
	try {
		const reiter = await oeffneWetter(page, kind, hub.id);
		const zeiger = await page.evaluate(() => (matchMedia('(pointer: coarse)').matches ? 'coarse' : 'fine'));
		expect(zeiger, 'Messaufbau: Bedienart des Kontexts').toBe(finger ? 'coarse' : 'fine');
		const picker = sichtbar(reiter, WT.picker);
		const g = await wahlGeo(picker);
		const wo = `${kind} ${lang} ${finger ? 'Finger' : 'Maus'}`;
		if (finger) expect(g.hoehe, `AC-32 ${wo}: Tippfläche ≥ 44 px`).toBeGreaterThanOrEqual(44);
		else expect(Math.abs(g.hoehe - 38), `AC-32 ${wo}: Höhe ${g.hoehe}px statt Mockup 38 ±2 px`).toBeLessThanOrEqual(2);
		expect(Math.abs(g.oben - g.unten), `AC-32 ${wo}: Inhalt nicht mittig (oben ${g.oben.toFixed(1)} / unten ${g.unten.toFixed(1)} px)`).toBeLessThanOrEqual(2);
		expect([g.links, g.rechts], `AC-32 ${wo}: seitliches Polster 12 px`).toEqual([12, 12]);
		if (finger) {
			// AC-33: Unterkante Eyebrow bis Oberkante Wähler-Text ≥ 12 px, Gap Eyebrow ↔ Wähler bleibt 6 px.
			const eyebrow = reiter.locator('[data-abschnitt="vorlage"] .wt-eyebrow:visible').first();
			const eb = await eyebrow.evaluate((el) => el.getBoundingClientRect().bottom);
			const pickerOben = await picker.evaluate((el) => el.getBoundingClientRect().top);
			expect(Math.abs(pickerOben - eb - 6), `AC-33 ${wo}: Gap Eyebrow ↔ Wähler ${(pickerOben - eb).toFixed(1)} px statt 6`).toBeLessThanOrEqual(1);
			expect(g.textOben - eb, `AC-33 ${wo}: Luft Eyebrow ↔ Wähler-Text`).toBeGreaterThanOrEqual(12);
		}
	} finally {
		await hub.aufraeumen();
	}
}

test.describe('#3003 Maus 1280×900', () => {
	test.use({ viewport: DESKTOP, hasTouch: false, isMobile: false });
	for (const kind of HUB_KINDS)
		for (const lang of SPRACHEN)
			test(`#3003 AC-32 ${kind} ${lang}: Wähler 38 ±2 px hoch, mittig, Polster 12 px`, async ({ page }) => {
				await pruefeWaehler(page, kind, lang, false);
			});
});

test.describe('#3003 Finger 390×844', () => {
	test.use({ viewport: MOBIL, hasTouch: true, isMobile: true });
	for (const kind of HUB_KINDS)
		for (const lang of SPRACHEN) {
			test(`#3003 AC-32/AC-33 ${kind} ${lang}: Wähler ≥ 44 px, mittig, Luft Eyebrow ↔ Text ≥ 12 px`, async ({ page }) => {
				await pruefeWaehler(page, kind, lang, true);
			});
			test(`#3003 AC-34 ${kind} ${lang}: Handy-Reiter füllen die volle Leistenbreite`, async ({ page }) => {
				await sprache(page, lang);
				const hub = await seed(page, kind);
				try {
					await oeffneWetter(page, kind, hub.id);
					const band = page.locator('[role="tablist"].mtabbar:visible').first();
					const m = await band.evaluate((el) => {
						const r = el.getBoundingClientRect();
						const tabs = Array.from(el.querySelectorAll('[role="tab"]')) as HTMLElement[];
						const letzter = tabs[tabs.length - 1].getBoundingClientRect();
						return { leisteRechts: r.right, letzterRechts: letzter.right, scroll: el.scrollWidth - el.clientWidth, font: getComputedStyle(tabs[0]).fontSize };
					});
					expect(m.scroll, `AC-34 ${kind} ${lang}: Band läuft bei 390 px nicht über`).toBeLessThanOrEqual(0);
					expect(Math.abs(m.leisteRechts - m.letzterRechts), `AC-34 ${kind} ${lang}: letzter Reiter endet ${(m.leisteRechts - m.letzterRechts).toFixed(1)} px vor dem Leistenende`).toBeLessThanOrEqual(2);
					expect(m.font, `AC-34 ${kind} ${lang}: Schrift 13 px`).toBe('13px');
				} finally {
					await hub.aufraeumen();
				}
			});
		}
});

test.describe('#3003 Finger 360×780', () => {
	test.use({ viewport: { width: 360, height: 780 }, hasTouch: true, isMobile: true });
	for (const kind of HUB_KINDS)
		test(`#3003 AC-34 ${kind} de: vier DE-Reiter laufen bei 360 px nicht über (#2794 B2)`, async ({ page }) => {
			await sprache(page, 'de');
			const hub = await seed(page, kind);
			try {
				await oeffneWetter(page, kind, hub.id);
				const band = page.locator('[role="tablist"].mtabbar:visible').first();
				const ueber = await band.evaluate((el) => el.scrollWidth - el.clientWidth);
				expect(ueber, `AC-34 ${kind}: Überlauf bei 360 px`).toBeLessThanOrEqual(0);
			} finally {
				await hub.aufraeumen();
			}
		});
});

// ── AC-19: keine Kennzahlenzeile am Handy (Trip) ─────────────────────────────

test('#2980 AC-19: Trip am Handy ohne Kennzahlenzeile „Etappe · Briefing · Start in“', async ({ page }) => {
	await page.setViewportSize(MOBIL);
	for (const lang of SPRACHEN) {
		await sprache(page, lang);
		const hub = await seed(page, 'route');
		try {
			await oeffneWetter(page, 'route', hub.id);
			await expect(page.locator('[data-testid="trip-header-mobile-metrics"]')).toHaveCount(0);
			await expect(page.locator('.hub-kopf').first()).not.toContainText(/start in|starts in/i);
			await expect(sichtbar(page, 'hub-kopf-meta')).toBeVisible();
		} finally {
			await hub.aufraeumen();
		}
	}
});

// ── AC-30: Aufnahmen Mockup ↔ Staging für den Bildprüfer (Runde 2) ───────────

test('#2980 AC-30: Aufnahmen Mockup und Staging — Trip/Orte × DE/EN × 1280/390, Reiter Wetter', async ({ page, browser }) => {
	test.setTimeout(600_000);
	const ordner = bildOrdner();
	for (const [, vp] of VIEWPORTS) {
		const m = await browser.newPage({ viewport: vp });
		try {
			await m.goto(MOCKUP);
			for (const ctx of ['trip', 'orte'] as const) {
				await m.evaluate((c) => document.querySelector<HTMLElement>(`[data-ctx="${c}"]`)?.click(), ctx);
				await ganzseite(m, path.join(ordner, `mockup-${ctx}-de-${vp.width}.png`));
			}
		} finally {
			await m.close();
		}
		await page.setViewportSize(vp);
		for (const lang of SPRACHEN) {
			await sprache(page, lang);
			for (const kind of HUB_KINDS) {
				const hub = await seed(page, kind);
				try {
					await oeffneWetter(page, kind, hub.id);
					await ganzseite(page, path.join(ordner, `staging-${KTX[kind]}-${lang}-${vp.width}.png`));
				} finally {
					await hub.aufraeumen();
				}
			}
		}
	}
});
