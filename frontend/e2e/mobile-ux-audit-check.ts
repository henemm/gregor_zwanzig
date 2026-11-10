// Mobile-UX-Audit (#2601): Prüflogik als eigenes Modul, damit der Audit
// (mobile-ux-audit.spec.ts) und sein Selbsttest (mobile-ux-audit-selbsttest.spec.ts)
// dieselbe Funktion ausführen. Spec: docs/specs/modules/mobile_ux_audit_2601.md (v1.1).
//
// LAYOUT_CHECK läuft per page.evaluate im Browser und muss daher selbstgenügsam bleiben
// (keine Bezüge auf Modul-Variablen; Typen werden beim Übersetzen entfernt).
//
// Runde 2 (Audit-Härtung, AC-15):
//   - tinyTargets  : ALLE Tap-Ziele < 24 px, ungekappt (früher bei 15 gekappt, der Rest
//                    rutschte in die weiche Liste)
//   - smallTargets : nur 24 ≤ min < 40 px
//   - tapEquivalent: Ziele < 24 px mit data-tap-equivalent (WCAG 2.5.8 „equivalent",
//                    z. B. Höhenprofil-Etappenrechtecke, AC-11) — Hinweis, nie hart
//   - pageOverflowPx: größter waagerechter Überlauf über Fenster UND jedes sichtbare <main>
//   - harte Listen (offscreen, verdeckt) ebenfalls ungekappt

export type Box = { x: number; y: number; w: number; h: number };
export type Item = { selector: string; text: string; box: Box; [k: string]: unknown };
export interface LayoutResult {
	pageOverflowPx: number;
	overflowingElements: Item[];
	offscreenInteractive: Item[];
	coveredInteractive: Item[];
	tinyTargets: Item[];
	smallTargets: Item[];
	tapEquivalent: Item[];
	smallText: { selector: string; fontSize: number; text: string }[];
	smallInputs: Item[];
	clippedContainers: Item[];
	scrollableRegions: Item[];
	viewportMeta: string | null;
	viewport: { width: number; height: number; dpr: number; scrollHeight: number };
}

// Läuft im Browser. Scrollt für Check (d) ans Seitenende und wieder zurück.
export const LAYOUT_CHECK = (overlay?: boolean): LayoutResult => {
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
	// (a) Fenster UND jedes sichtbare <main> (auch innere ohne Klasse, Befund /compare Runde 2).
	const mainOverflows = Array.from(document.querySelectorAll('main'))
		.filter(visible)
		.map((m) => m.scrollWidth - m.clientWidth);
	const pageOverflowPx = Math.max(0, (document.scrollingElement ?? doc).scrollWidth - vw, ...mainOverflows);

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

	// (c) interaktiv, horizontal aus dem Viewport ragend — hart, daher ungekappt.
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
			if (!scrollable) offscreenInteractive.push(item(el, { right: Math.round(r.right), left: Math.round(r.left) }));
		}
	}

	// (e) Tap-Ziele — ungekappt; < 24 px immer hart, 24–39 px weich.
	const tinyTargets: Item[] = [];
	const smallTargets: Item[] = [];
	const tapEquivalent: Item[] = [];
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
		const eintrag = item(el, { w: Math.round(r.width), h: Math.round(r.height) });
		if (min < 24) {
			// WCAG 2.5.8 „equivalent": gleichwertige Bedienung anderswo — Hinweis, nie hart.
			if (el.closest('[data-tap-equivalent]')) tapEquivalent.push(eintrag);
			else tinyTargets.push(eintrag);
		} else if (min < 40) smallTargets.push(eintrag);
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
		if (fs > 0 && fs < 11 && visible(el)) smallText.push({ selector: selOf(el), fontSize: fs, text: text.slice(0, 50) });
	}
	const smallInputs: Item[] = [];
	for (const el of Array.from(doc.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="range"]), select, textarea'))) {
		if (!visible(el)) continue;
		const fs = parseFloat(getComputedStyle(el).fontSize);
		if (fs < 16) smallInputs.push(item(el, { fontSize: fs }));
	}

	// (d) am Seitenende: welche interaktiven Elemente liegen unter fixen Leisten? — hart, ungekappt.
	const coveredInteractive: Item[] = [];
	const prevY = se.scrollTop;
	if (!overlay) {
		// (Bei offenem Sheet/Dialog deckt der Backdrop die Seite absichtlich.)
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
			if (bar && fixedBars.includes(bar)) coveredInteractive.push(item(el, { coveredBy: selOf(bar), yInViewport: Math.round(r.y), vh }));
		}
		se.scrollTop = prevY;
		window.scrollTo(0, 0);
	}

	const vp = document.querySelector('meta[name="viewport"]')?.getAttribute('content') ?? null;
	return {
		pageOverflowPx, overflowingElements, offscreenInteractive, coveredInteractive, tinyTargets, smallTargets, tapEquivalent,
		smallText, smallInputs, clippedContainers, scrollableRegions, viewportMeta: vp,
		viewport: { width: vw, height: vh, dpr: window.devicePixelRatio, scrollHeight: se.scrollHeight },
	};
};
