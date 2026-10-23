// Mobile-UX-Audit (#2601): alle Routen in drei Smartphone-Profilen auf
// Erreichbarkeit und Bedienbarkeit prüfen. Je Route (und je Detail-Tab):
//   (a) page-level horizontaler Overflow
//   (b) überstehende Elemente (overflow-x weder auto noch scroll)
//   (c) interaktive Elemente, die horizontal aus dem Viewport ragen
//   (d) interaktive Elemente, die am Seitenende unter fixen/sticky Leisten
//       liegen (nicht antippbar)
//   (e) Tap-Ziele < 24px (hart) bzw. < 40px (Hinweis)
//   (f) Texte < 11px; Eingabefelder < 16px (iOS-Auto-Zoom)
//   (g) abgeschnittene overflow-hidden-Container, scrollbare Mini-Bereiche
//   (h) Viewport-Meta
// Befunde werden nach jeder Route in test-results/mobile-ux/report-<projekt>
// .json/.md geschrieben; Screenshots je Route/Tab daneben.
//
// Assertion-Politik: ohne GZ_AUDIT_STRICT nur Report (Ist-Aufnahme). Mit
// GZ_AUDIT_STRICT=1 schlagen (a), (c), (d) und Tap-Ziele < 24px fehl.

import { test, expect, type Page } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const OUT_ROOT = 'test-results/mobile-ux';
const STRICT = process.env.GZ_AUDIT_STRICT === '1';

type Box = { x: number; y: number; w: number; h: number };
type Item = { selector: string; text: string; box: Box; [k: string]: unknown };
interface LayoutResult {
	pageOverflowPx: number;
	overflowingElements: Item[];
	offscreenInteractive: Item[];
	coveredInteractive: Item[];
	tinyTargets: Item[];
	smallTargets: Item[];
	smallText: { selector: string; fontSize: number; text: string }[];
	smallInputs: Item[];
	clippedContainers: Item[];
	scrollableRegions: Item[];
	viewportMeta: string | null;
	viewport: { width: number; height: number; dpr: number; scrollHeight: number };
}
interface Finding extends Partial<LayoutResult> {
	route: string;
	view: string;
	skipped?: string;
	error?: string;
}

function slug(route: string): string {
	return route === '/' ? 'root' : route.replace(/^\//, '').replace(/[/?=&]/g, '_');
}

// Läuft im Browser. Scrollt für Check (d) ans Seitenende und wieder zurück.
const LAYOUT_CHECK = (overlay?: boolean): LayoutResult => {
	const doc = document.documentElement;
	const vw = window.innerWidth;
	const vh = window.innerHeight;
	const visible = (el: Element) => {
		const cs = getComputedStyle(el);
		if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
		const r = el.getBoundingClientRect();
		return r.width > 0 && r.height > 0;
	};
	const selOf = (el: Element) => {
		const dt = el.closest('[data-testid]');
		const own = el.getAttribute('data-testid');
		if (own) return `[data-testid="${own}"]`;
		const cls = (el.getAttribute('class') ?? '').trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.');
		const base = el.id ? `#${el.id}` : cls ? `${el.tagName.toLowerCase()}.${cls}` : el.tagName.toLowerCase();
		return dt ? `[data-testid="${dt.getAttribute('data-testid')}"] ${base}` : base;
	};
	const snip = (el: Element, n = 50) =>
		((el as HTMLElement).innerText ?? el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, n) ||
		(el.getAttribute('aria-label') ?? el.getAttribute('title') ?? el.getAttribute('placeholder') ?? '').slice(0, n);
	const box = (el: Element): Box => {
		const r = el.getBoundingClientRect();
		return { x: Math.round(r.x), y: Math.round(r.y + window.scrollY), w: Math.round(r.width), h: Math.round(r.height) };
	};
	const item = (el: Element, extra: Record<string, unknown> = {}): Item => ({ selector: selOf(el), text: snip(el), box: box(el), ...extra });
	const INTERACTIVE =
		'a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [role="tab"], [role="link"], [role="menuitem"], [role="checkbox"], [role="switch"], [role="option"], [tabindex]:not([tabindex="-1"])';
	const interactive = Array.from(doc.querySelectorAll(INTERACTIVE)).filter(visible);
	const inFixed = (el: Element | null): Element | null => {
		for (let e = el; e && e !== doc; e = e.parentElement) {
			const p = getComputedStyle(e).position;
			if (p === 'fixed' || p === 'sticky') return e;
		}
		return null;
	};

	// App-Shell: <main class="mobile-scroll-pad"> ist der eigentliche
	// Scroll-Container (overflow:auto in einem h-screen-Flex), nicht das Fenster.
	const mainEl = document.querySelector('main.mobile-scroll-pad') as HTMLElement | null;
	const se = mainEl && mainEl.scrollHeight > mainEl.clientHeight ? mainEl : (document.scrollingElement ?? doc);
	const pageOverflowPx = Math.max(0, (document.scrollingElement ?? doc).scrollWidth - vw, mainEl ? mainEl.scrollWidth - mainEl.clientWidth : 0);

	const all = Array.from(doc.querySelectorAll('body *'));
	const overflowingElements: Item[] = [];
	const scrollableRegions: Item[] = [];
	const clippedContainers: Item[] = [];
	for (const el of all) {
		if (overflowingElements.length + scrollableRegions.length + clippedContainers.length > 40) break;
		const cs = getComputedStyle(el);
		const scrollX = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
		if (el.scrollWidth > el.clientWidth + 1 && visible(el)) {
			if (scrollX) {
				if (scrollableRegions.length < 12) scrollableRegions.push(item(el, { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth }));
			} else if (cs.overflowX !== 'hidden' && cs.overflowX !== 'clip') {
				// sichtbares Überstehen (hidden/clip schneidet ab, dafür (c))
				const r = el.getBoundingClientRect();
				if (r.left + el.scrollWidth > vw + 1 && overflowingElements.length < 12)
					overflowingElements.push(item(el, { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth }));
			}
		}
		if (cs.overflowY === 'hidden' && el.scrollHeight > el.clientHeight + 4 && visible(el) && clippedContainers.length < 12) {
			if (el.closest('[aria-hidden="true"]')) continue;
			clippedContainers.push(item(el, { scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));
		}
	}

	// (c) interaktiv, horizontal aus dem Viewport ragend.
	const offscreenInteractive: Item[] = [];
	for (const el of interactive) {
		const r = el.getBoundingClientRect();
		if (r.right > vw + 1 || r.left < -1) {
			if (el.closest('[aria-hidden="true"]')) continue;
			// Elemente in horizontal scrollbaren Containern sind erreichbar.
			let scrollable = false;
			for (let p = el.parentElement; p && p !== doc; p = p.parentElement) {
				const cs = getComputedStyle(p);
				if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && p.scrollWidth > p.clientWidth) { scrollable = true; break; }
			}
			if (!scrollable && offscreenInteractive.length < 12) offscreenInteractive.push(item(el, { right: Math.round(r.right), left: Math.round(r.left) }));
		}
	}

	// (e) Tap-Ziele.
	const tinyTargets: Item[] = [];
	const smallTargets: Item[] = [];
	for (const el of interactive) {
		const r = el.getBoundingClientRect();
		if (el.closest('[aria-hidden="true"]')) continue;
		// Inline-Links im Fließtext sind ausgenommen (WCAG 2.5.8, Ausnahme „inline").
		if (el.tagName === 'A' && getComputedStyle(el).display === 'inline') continue;
		// Unsichtbar vergrößerte Trefferfläche per ::after (inset: -Npx) zählt mit.
		let w = r.width;
		let h = r.height;
		const after = getComputedStyle(el, '::after');
		if (after.content !== 'none' && after.position === 'absolute') {
			const px = (v: string) => (v.endsWith('px') ? parseFloat(v) : 0);
			w += -px(after.left) - px(after.right);
			h += -px(after.top) - px(after.bottom);
		}
		const min = Math.min(w, h);
		// Checkbox/Radio: das Label vergrößert die Fläche — klickbares Label suchen.
		if ((el as HTMLInputElement).type === 'checkbox' || (el as HTMLInputElement).type === 'radio') {
			const lab = (el as HTMLInputElement).labels?.[0] ?? el.closest('label');
			if (lab) {
				const lr = lab.getBoundingClientRect();
				if (Math.min(lr.width, lr.height) >= 24) continue;
			}
		}
		if (min < 24 && tinyTargets.length < 15) tinyTargets.push(item(el, { w: Math.round(r.width), h: Math.round(r.height) }));
		else if (min < 40 && smallTargets.length < 20) smallTargets.push(item(el, { w: Math.round(r.width), h: Math.round(r.height) }));
	}

	// (f) Texte & Inputs.
	const smallText: { selector: string; fontSize: number; text: string }[] = [];
	const walker = document.createTreeWalker(doc, NodeFilter.SHOW_TEXT);
	let node: Node | null;
	while ((node = walker.nextNode())) {
		const text = (node.textContent ?? '').trim();
		if (!text) continue;
		const el = node.parentElement;
		if (!el || el.closest('svg, script, style, noscript, [aria-hidden="true"]')) continue;
		const fs = parseFloat(getComputedStyle(el).fontSize);
		if (fs > 0 && fs < 11 && visible(el) && smallText.length < 15) smallText.push({ selector: selOf(el), fontSize: fs, text: text.slice(0, 50) });
	}
	const smallInputs: Item[] = [];
	for (const el of Array.from(doc.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="range"]), select, textarea'))) {
		if (!visible(el)) continue;
		const fs = parseFloat(getComputedStyle(el).fontSize);
		if (fs < 16 && smallInputs.length < 15) smallInputs.push(item(el, { fontSize: fs }));
	}

	// (d) am Seitenende: welche interaktiven Elemente liegen unter fixen Leisten?
	const coveredInteractive: Item[] = [];
	const prevY = se.scrollTop;
	if (overlay) {
		// Sheet/Dialog offen: der Backdrop deckt die Seite absichtlich.
	} else {
	se.scrollTop = se.scrollHeight;
	window.scrollTo(0, document.documentElement.scrollHeight);
	const fixedBars = all.filter((el) => {
		const cs = getComputedStyle(el);
		return (cs.position === 'fixed' || cs.position === 'sticky') && visible(el) && el.getBoundingClientRect().height >= 20;
	});
	for (const el of interactive) {
		if (inFixed(el)) continue;
		const r = el.getBoundingClientRect();
		if (r.bottom < 0 || r.top > vh) continue; // nicht im Viewport
		const cx = Math.min(vw - 1, Math.max(0, r.x + r.width / 2));
		const cy = Math.min(vh - 1, Math.max(0, r.y + r.height / 2));
		const hit = document.elementFromPoint(cx, cy);
		if (!hit || hit === el || el.contains(hit) || hit.contains(el)) continue;
		const bar = inFixed(hit);
		if (bar && fixedBars.includes(bar) && coveredInteractive.length < 12) {
			coveredInteractive.push(item(el, { coveredBy: selOf(bar), yInViewport: Math.round(r.y), vh }));
		}
	}
	se.scrollTop = prevY;
	window.scrollTo(0, 0);
	}

	const vp = document.querySelector('meta[name="viewport"]')?.getAttribute('content') ?? null;
	return {
		pageOverflowPx, overflowingElements, offscreenInteractive, coveredInteractive, tinyTargets, smallTargets,
		smallText, smallInputs, clippedContainers, scrollableRegions, viewportMeta: vp,
		viewport: { width: vw, height: vh, dpr: window.devicePixelRatio, scrollHeight: se.scrollHeight },
	};
};

async function resolveIds(page: Page): Promise<{ trip: string | null; compare: string | null }> {
	let trip: string | null = null;
	let compare: string | null = null;
	const t = await page.request.get('/api/trips');
	if (t.ok()) {
		const body = (await t.json()) as { id?: string; stages?: unknown[] }[];
		const pick = body.find((x) => x.id === 'mx-audit-tour') ?? body.sort((a, b) => (b.stages?.length ?? 0) - (a.stages?.length ?? 0))[0];
		if (pick?.id) trip = pick.id;
	}
	const c = await page.request.get('/api/compare/presets');
	if (c.ok()) {
		const body = (await c.json()) as { id?: string; location_ids?: string[] }[];
		const pick = body.sort((a, b) => (b.location_ids?.length ?? 0) - (a.location_ids?.length ?? 0))[0];
		if (pick?.id) compare = pick.id;
	}
	return { trip, compare };
}

class Reporter {
	findings: Finding[] = [];
	constructor(private project: string, private suffix: string) {
		fs.mkdirSync(path.join(OUT_ROOT, project), { recursive: true });
	}
	add(f: Finding) {
		this.findings.push(f);
		this.write();
	}
	write() {
		const base = path.join(OUT_ROOT, `report-${this.project}${this.suffix}`);
		fs.writeFileSync(`${base}.json`, JSON.stringify({ project: this.project, generatedAt: new Date().toISOString(), routes: this.findings }, null, 2));
		const lines = [`# Mobile-UX-Report (${this.project}${this.suffix})`, ''];
		for (const f of this.findings) {
			const label = f.view !== 'initial' ? `${f.route} [${f.view}]` : f.route;
			if (f.error) lines.push(`- ❌ ${label}: LADEFEHLER — ${f.error}`);
			else if (f.skipped) lines.push(`- ⏭️ ${label}: ${f.skipped}`);
			else {
				const n = (a?: unknown[]) => a?.length ?? 0;
				const hard = (f.pageOverflowPx ?? 0) > 1 || n(f.offscreenInteractive) + n(f.coveredInteractive) + n(f.tinyTargets) > 0;
				const warn = n(f.overflowingElements) + n(f.smallTargets) + n(f.smallText) + n(f.smallInputs) + n(f.clippedContainers) > 0;
				lines.push(
					`- ${hard ? '❌' : warn ? '⚠️' : '✅'} ${label}: overflow ${f.pageOverflowPx}px · offscreen ${n(f.offscreenInteractive)} · verdeckt ${n(f.coveredInteractive)} · tap<24 ${n(f.tinyTargets)} · tap<40 ${n(f.smallTargets)} · text<11 ${n(f.smallText)} · input<16 ${n(f.smallInputs)} · überstehend ${n(f.overflowingElements)} · clip ${n(f.clippedContainers)} · hscroll ${n(f.scrollableRegions)}`
				);
				const detail = (name: string, arr?: Item[]) => {
					for (const it of (arr ?? []).slice(0, 6)) lines.push(`    - ${name}: \`${it.selector}\` „${it.text}" ${JSON.stringify({ ...it, selector: undefined, text: undefined })}`);
				};
				detail('offscreen', f.offscreenInteractive);
				detail('verdeckt', f.coveredInteractive);
				detail('tap<24', f.tinyTargets);
				detail('tap<40', f.smallTargets);
				detail('input<16', f.smallInputs);
				detail('überstehend', f.overflowingElements);
				for (const it of (f.smallText ?? []).slice(0, 4)) lines.push(`    - text<11: \`${it.selector}\` ${it.fontSize}px „${it.text}"`);
				detail('clip', f.clippedContainers);
			}
		}
		fs.writeFileSync(`${base}.md`, lines.join('\n') + '\n');
	}
	hardFailures(): string[] {
		return this.findings
			.filter((f) => !f.skipped && !f.error && ((f.pageOverflowPx ?? 0) > 1 || (f.offscreenInteractive?.length ?? 0) + (f.coveredInteractive?.length ?? 0) + (f.tinyTargets?.length ?? 0) > 0))
			.map((f) => `${f.route}${f.view !== 'initial' ? `#${f.view}` : ''}`);
	}
}

// Ganzseiten-Screenshot trotz innerem Scroll-Container: <main> und seinen
// h-screen-Rahmen kurz aufklappen, danach zurücksetzen.
async function fullShot(page: Page, file: string) {
	await page.evaluate(() => {
		const m = document.querySelector('main.mobile-scroll-pad') as HTMLElement | null;
		if (!m) return;
		m.dataset.gzPrevOverflow = m.style.overflow;
		m.style.overflow = 'visible';
		// Breite festnageln: sonst weitet überlaufender Inhalt <main> und die
		// Seite würde breiter als der Viewport aufgenommen.
		m.style.flex = `0 0 ${window.innerWidth}px`;
		m.style.width = `${window.innerWidth}px`;
		m.style.maxWidth = `${window.innerWidth}px`;
		const wrap = m.parentElement as HTMLElement | null;
		if (wrap) { wrap.dataset.gzPrevHeight = wrap.style.height; wrap.style.height = 'auto'; }
	});
	await page.screenshot({ path: file, fullPage: true });
	await page.evaluate(() => {
		const m = document.querySelector('main.mobile-scroll-pad') as HTMLElement | null;
		if (!m) return;
		m.style.overflow = m.dataset.gzPrevOverflow ?? '';
		m.style.flex = ''; m.style.width = ''; m.style.maxWidth = '';
		const wrap = m.parentElement as HTMLElement | null;
		if (wrap) wrap.style.height = wrap.dataset.gzPrevHeight ?? '';
	});
}

// Overlays (Sheets, Menüs, Dialoge): öffnen, prüfen, Screenshot, schließen.
const OVERLAYS: { route: RegExp; view: string; open: string; wait: string }[] = [
	{ route: /^\/$/, view: 'konto-sheet', open: '[data-testid="konto-kreis"]', wait: '[data-testid="konto-sheet"]' },
	{ route: /^\/trips$/, view: 'karten-menue', open: '[data-testid^="subscription-card-menu-"]', wait: '[data-testid^="subscription-action-"]' },
	{ route: /^\/compare$/, view: 'karten-menue', open: '[data-testid^="subscription-card-menu-"]', wait: '[data-testid^="subscription-action-"]' },
	{ route: /^\/trips\/[^/]+$/, view: 'sende-dialog', open: '[data-testid="subscription-hub-send"]', wait: '[role="dialog"]' },
	{ route: /^\/compare\/[^/]+$/, view: 'sende-dialog', open: '[data-testid="subscription-hub-send"]', wait: '[role="dialog"]' },
];

async function auditRoute(page: Page, rep: Reporter, route: string, opts: { tabs?: boolean } = {}) {
	const project = rep['project'];
	const shot = (view: string) => path.join(OUT_ROOT, project, `${slug(route)}${view !== 'initial' ? `__${view}` : ''}.png`);
	const settle = async () => {
		await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
		await page.waitForTimeout(350);
	};
	try {
		await page.goto(route, { waitUntil: 'load', timeout: 45_000 });
		await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 0, null, { timeout: 15_000 });
		await settle();
		const landed = new URL(page.url()).pathname;
		if (landed !== route.split('?')[0] && !route.startsWith(landed)) {
			rep.add({ route, view: 'initial', skipped: `Redirect nach ${landed}` });
			return;
		}
		rep.add({ route, view: 'initial', ...(await page.evaluate(LAYOUT_CHECK)) });
		await fullShot(page, shot('initial'));
		if (opts.tabs) {
			const tabs = page.locator('[data-testid^="trip-detail-tab-"]:not([data-testid$="-list"]):not([data-testid*="-badge-"]), [data-testid^="compare-detail-tab-"]:not([data-testid$="-list"]):not([data-testid*="-badge-"])');
			const ids = await tabs.evaluateAll((els) => els.map((e) => e.getAttribute('data-testid') ?? ''));
			for (const id of ids) {
				const btn = page.getByTestId(id).first();
				if (!(await btn.isVisible().catch(() => false))) continue;
				await btn.scrollIntoViewIfNeeded().catch(() => {});
				await btn.click({ timeout: 5_000 }).catch(() => {});
				await settle();
				const view = id.replace(/^(trip|compare)-detail-tab-/, '');
				rep.add({ route, view, ...(await page.evaluate(LAYOUT_CHECK)) });
				await fullShot(page, shot(view));
			}
		}
		for (const ov of OVERLAYS.filter((o) => o.route.test(route))) {
			const trigger = page.locator(ov.open).first();
			if (!(await trigger.isVisible().catch(() => false))) continue;
			await trigger.scrollIntoViewIfNeeded().catch(() => {});
			await trigger.click({ timeout: 5_000 }).catch(() => {});
			const ok = await page.locator(ov.wait).first().waitFor({ state: 'visible', timeout: 5_000 }).then(() => true).catch(() => false);
			await page.waitForTimeout(400);
			rep.add({ route, view: ov.view, ...(await page.evaluate(LAYOUT_CHECK, true)), ...(ok ? {} : { error: `Overlay ${ov.view} nicht sichtbar` }) });
			await page.screenshot({ path: shot(ov.view), fullPage: false });
			await page.keyboard.press('Escape').catch(() => {});
			await page.waitForTimeout(250);
		}
	} catch (err) {
		rep.add({ route, view: 'initial', error: err instanceof Error ? err.message.slice(0, 300) : String(err) });
	}
}

test('angemeldete Routen', async ({ page }, testInfo) => {
	const rep = new Reporter(testInfo.project.name, '');
	const { trip, compare } = await resolveIds(page);
	const routes: { route: string; tabs?: boolean }[] = [{ route: '/' }, { route: '/trips' }];
	if (trip) routes.push({ route: `/trips/${trip}`, tabs: true }, { route: `/trips/${trip}/edit` });
	else rep.add({ route: '/trips/[id]', view: 'initial', skipped: 'kein Trip' });
	routes.push({ route: '/trips/new' }, { route: '/compare' });
	if (compare) routes.push({ route: `/compare/${compare}`, tabs: true }, { route: `/compare/${compare}/edit` });
	else rep.add({ route: '/compare/[id]', view: 'initial', skipped: 'kein Vergleich' });
	routes.push({ route: '/compare/new' }, { route: '/locations' }, { route: '/archiv' }, { route: '/account' }, { route: '/admin' }, { route: '/hilfe' }, { route: '/gpx-upload' });
	for (const r of routes) await auditRoute(page, rep, r.route, { tabs: r.tabs });
	const hard = rep.hardFailures();
	if (STRICT) expect(hard, 'harte Mobile-Befunde (siehe report)').toEqual([]);
	else test.info().annotations.push({ type: 'hard-findings', description: hard.join(', ') || 'keine' });
});

test.describe('öffentliche Routen', () => {
	test.use({ storageState: { cookies: [], origins: [] } });
	test('login/register/forgot', async ({ page }, testInfo) => {
		const rep = new Reporter(testInfo.project.name, '-public');
		for (const route of ['/login', '/register', '/forgot-password']) await auditRoute(page, rep, route);
		const hard = rep.hardFailures();
		if (STRICT) expect(hard, 'harte Mobile-Befunde (siehe report)').toEqual([]);
		else test.info().annotations.push({ type: 'hard-findings', description: hard.join(', ') || 'keine' });
	});
});
