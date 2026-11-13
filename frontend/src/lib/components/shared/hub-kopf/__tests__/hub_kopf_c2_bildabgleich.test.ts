// TDD RED — Issue #2980, Fix-Loop Bildabgleich Runde 1 der Scheibe c2 (#2913, Epic #2791).
// Spec: docs/specs/modules/feat_2913_c2_seitenkopf.md — Abschnitt „Fix-Loop Bildabgleich Runde 1
// (#2980)“, AC-16 bis AC-28 (Unit-Anteil); Implementation Details Punkt 7.
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html Z. 34–71 (CSS Kopfband,
// Kopf, Meta, Pill, Btn, Reiter, Abschnittskopf), 90–92 (Vorlage/Picker), 228–245 (Leiste),
// 326 (PILL-Zuordnung), 442 (Wetter-Abschnittskopf), 508–512 (Vorlage-Karte).
//
// Geprüft wird dort, wo es WIRKT: die echten Detailseiten /trips/[id] und /compare/[id]
// (serverseitig gerendert über die Prüfstände f9Pruefstand.ts / f10Pruefstand.ts, Ruhe- und
// Handy-Variante), die echte VorlageKarte und der echte WetterTabInhalt. Die Optik ist CSS:
// cssKaskade.ts rechnet für die gerenderten Elemente den berechneten Stil aus den echten
// Stilquellen nach (app.css + kompiliertes Komponenten-CSS der im Markup vorkommenden
// Komponenten + Inline-Stile; Handy = 390 px, Desktop = 1280 px; Hell/Dunkel), Tokens auf ihre
// Werte aufgelöst. Kein Mock, kein Quelltext-Grep auf Klassen-Namen. Die Messung im echten
// Browser folgt in frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts (AC-30).
// doc-compliance-test
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
// Alles im geteilten Baustein (ADR-0097), nur Tokens (Wächter bausteine_waechter*); testids bleiben.
// AC-16 Knopf `subscription-hub-send`: Btn mit data-variant="accent" (Btn variant="accent"), Fläche
//        aus app.css [data-slot="btn"][data-variant="accent"] = --g-accent-deep (NICHT --g-accent),
//        Schrift --g-on-accent; Kontrast ≥ 4,5:1 hell UND dunkel. Gilt Desktop und Handy, Trip und Orte.
// AC-17/18 MTabBar (mobile/MTabBar.svelte): Handy-@media (max-width: 899px) ohne Pillen —
//        jeder Reiter: background transparent, kein Rahmen oben/links/rechts, kein Radius-Kasten;
//        inaktiv color --g-ink-3, font-weight 500; aktiv color --g-ink, 600, border-bottom 2px solid
//        --g-accent; Grundlinie an der Wurzel .mtabbar border-bottom 1px solid --g-rule (auch Handy);
//        Schrift 13 px auf beiden Breiten. Am Desktop identisch (inaktiv heute --g-ink ⇒ --g-ink-3).
//        Handy weiterhin: Wurzel overflow-x auto|scroll, Reiter min-height ≥ 44 px (#2284).
// AC-19 TripHeader: Snippet `unten` mit `trip-header-mobile-metrics` (Etappe · Briefing · Start in)
//        entfällt ersatzlos; kein Text „START IN“/„STARTS IN“ im Kopf; Meta-Zeile bleibt.
// AC-20 `hub-kopf-meta`: font-family --g-font-mono, 13 px, color --g-ink-3 (Desktop und Handy).
// AC-21/22 StatusSchild (shared/status-schild/StatusSchild.svelte) → Pill (data-slot="pill"):
//        OHNE data-outlined, kein Rahmen (alle Seiten border-style none oder Breite 0),
//        Mono 11 px, text-transform uppercase per CSS, DOM-Text = Katalogtext (nicht groß
//        geschrieben), data-status bleibt. Ton: active ⇒ color --g-good auf Grund
//        rgba(61,107,58,α) mit 0<α≤0,2 (Mockup .pill.good); draft/paused/archived/finished ⇒
//        color --g-ink-3 (im Dunkeln ersatzweise --g-ink-2 zulässig) auf --g-paper-deep.
//        Kontrast Schrift/Grund (Grund über --g-paper gemischt) ≥ 4,5:1 hell und dunkel.
//        StatusSchild TONE_MAP: active: 'good', alle anderen 'neutral' (StatusSchild.atomic.test.ts).
//        Achtung: Pill bildet tone="good"/"neutral" heute auf success/default ab (TONE_ALIAS) —
//        gemessen wird das ERGEBNIS der Kaskade; wie die Pill den Mockup-Ton erreicht (Alias,
//        Attribut, Regel in app.css), ist frei — andere Pill-Konsumenten dürfen sich nicht ändern.
//        Gilt auch für data-status="planned" (neutral), siehe status_schild.test.ts.
// AC-23 Kopfband: `hub-kopf-breadcrumb` font-family --g-font-mono, 11 px, text-transform
//        uppercase, color --g-ink-3 (Elternlink erbt); der Name steht als eigenes Element im
//        Breadcrumb (direkter Text = Name) mit color --g-ink, font-weight 500; `hub-kopf-leiste`
//        border-bottom 1px solid --g-rule-soft. Desktop und Handy.
// AC-24 Breadcrumb-Name = voller Name (Trip: trip.name, nie trip.shortcode); kein Element mit
//        Klasse/testid `back-mobil`, kein Zurück-Link (BackLink) in der Leiste — genau EIN Link
//        (Elternteil); am Handy: Name umbrechend — overflow-wrap anywhere (oder break-word),
//        white-space nicht nowrap, text-overflow nicht ellipsis (am Breadcrumb und am Namen).
// AC-25 Kebab `subscription-kebab`: background transparent, Rahmen auf allen Seiten solid
//        --g-rule (Desktop UND Handy; Inline-Stile zählen mit), am Handy Höhe und Breite ≥ 44 px;
//        im DOM vor `subscription-hub-send`.
// AC-26 VorlageKarte `wetter-vorlage-picker`: Rahmen (alle Seiten) solid --g-rule, Grund
//        --g-paper, font-size 15 px, font-weight 600 (Name erbt); Zusatz-Element mit „▾“ (heute
//        <small>) samt `wetter-vorlage-status`: Mono (--g-font-mono), 11 px, color --g-ink-3.
// AC-27 Karte [data-abschnitt="vorlage"]: align-items center (Desktop und Handy).
// AC-28 WetterTabInhalt Kopf (Elternelement von `wetter-tab-titel`, heute header.wt-kopf):
//        border-bottom 1px solid --g-rule-soft, padding-bottom 12 px; `wetter-tab-erklaer`:
//        max-width 68ch, font-size 13 px, color --g-ink-3.
// ─────────────────────────────────────────────────────────────────────────────────────
//
// Pfadregel #1409: Prüflinge relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_bildabgleich.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { baum, alle, einzig, mitTestid, text, type Knoten } from './htmlBaum.ts';
import { ladeQuellen, stil, herkunft, token, farbe, ueber, kontrast, px, DESKTOP, HANDY, type Kontext, type Theme } from './cssKaskade.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> hub-kopf -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
const KOMP = path.resolve(HERE, '../../..');

const T = await import('../../../trip-detail/__tests__/f9Pruefstand.ts');
const C = await import('../../../compare/__tests__/f10Pruefstand.ts');
const { locale, trFor } = T;
const { render } = await import('svelte/server');
const Q = await ladeQuellen(FRONTEND);

afterEach(() => locale.set('de'));

type Lang = 'de' | 'en';
type Art = 'route' | 'vergleich';
const SPRACHEN: Lang[] = ['de', 'en'];
const ARTEN: Art[] = ['route', 'vergleich'];
const BREITEN: Array<[string, Kontext]> = [['Desktop 1280', DESKTOP], ['Handy 390', HANDY]];
const dunkel = (ctx: Kontext): Kontext => ({ ...ctx, theme: 'dunkel' });

function mitSprache<R>(lang: Lang, f: () => R): R {
	locale.set(lang);
	try {
		return f();
	} finally {
		locale.set('de');
	}
}

// ── Fixtures ────────────────────────────────────────────────────────────────────────
const wp = (id: string, lat: number, ele: number) => ({ id, name: id, lat, lon: 2.7 + lat / 100, elevation_m: ele });
const VIER_ETAPPEN = [
	{ id: 'm1', name: 'Sant Elm – Estellencs', date: '2026-07-01', waypoints: [wp('a', 39.58, 20), wp('b', 39.65, 420)] },
	{ id: 'm2', name: 'Estellencs – Esporles', date: '2026-07-02', waypoints: [wp('c', 39.66, 380), wp('d', 39.67, 1100)] },
	{ id: 'm3', name: 'Esporles – Valldemossa', date: '2026-07-03', waypoints: [wp('e', 39.7, 900), wp('f', 39.71, 1350)] },
	{ id: 'm4', name: 'Valldemossa – Deià', date: '2026-07-04', waypoints: [wp('g', 39.74, 400), wp('h', 39.75, 900)] }
];
const tripMallorca = (extra: Record<string, unknown> = {}) =>
	T.tripLaufend({ id: 'gd-mallorca', name: 'GR221 Mallorca', shortcode: undefined, region: 'Mallorca', stages: VIER_ETAPPEN, ...extra });
const TRIP_ZUSTAENDE: Record<string, () => Record<string, unknown>> = {
	draft: () => tripMallorca({ stages: [{ id: 'd1', name: 'E1', waypoints: [] }] }),
	active: () => tripMallorca(),
	paused: () => tripMallorca({ paused_at: '2026-06-20T08:00:00Z' }),
	archived: () => tripMallorca({ archived_at: '2026-07-01T00:00:00Z' }),
	finished: () => tripMallorca({ stages: VIER_ETAPPEN.map((s, i) => ({ ...s, date: `2026-05-0${i + 1}` })) })
};
const VERGLEICH_ZUSTAENDE: Record<string, () => Record<string, unknown>> = {
	draft: () => C.vergleichEntwurf(),
	active: () => C.vergleichAktiv(),
	paused: () => C.vergleichAktiv({ schedule: 'manual', previous_schedule: 'daily', paused_at: '2026-10-20T08:00:00Z' }),
	archived: () => C.vergleichAktiv({ archived_at: '2026-10-25T00:00:00Z' }),
	finished: () => C.vergleichAktiv({ end_date: '2026-10-01' })
};
const ZUSTAENDE = ['draft', 'active', 'paused', 'archived', 'finished'] as const;

/** Seite rendern; Handy-Kontext nutzt die Handy-Variante der Seite (mobil = true). */
function seite(art: Art, ctx: Kontext, lang: Lang = 'de', daten?: Record<string, unknown>): Knoten {
	const fall = ctx.breite < 900 ? 'mobil' : 'ruhe';
	return mitSprache(lang, () =>
		baum(art === 'route' ? T.seiteRendern(fall, (daten ?? tripMallorca()) as never) : C.seiteRendern(fall, daten ?? C.vergleichAktiv()))
	);
}

// ── Mess-Helfer ─────────────────────────────────────────────────────────────────────
const s = (k: Knoten, prop: string, ctx: Kontext) => stil(Q, k, prop, ctx);
function gleich(k: Knoten, prop: string, ctx: Kontext, soll: string, was: string): void {
	const ist = s(k, prop, ctx);
	assert.equal(ist, soll, `${was}: ${prop} ist „${ist}“, Soll „${soll}“ — Kaskade: ${herkunft(Q, k, prop, ctx)}`);
}
/** Länge in px (px oder rem à 16 px). */
function laenge(v: string | undefined): number {
	if (!v) return NaN;
	const m = /^([\d.]+)rem$/.exec(v);
	return m ? Number(m[1]) * 16 : px(v);
}
function laengeGleich(k: Knoten, prop: string, ctx: Kontext, soll: number, was: string): void {
	const ist = s(k, prop, ctx);
	assert.equal(laenge(ist), soll, `${was}: ${prop} ist „${ist}“, Soll ${soll}px — Kaskade: ${herkunft(Q, k, prop, ctx)}`);
}
function hintergrund(k: Knoten, ctx: Kontext): string {
	return s(k, 'background-color', ctx) ?? 'transparent';
}
function transparent(k: Knoten, ctx: Kontext, was: string): void {
	const bg = hintergrund(k, ctx);
	const f = farbe(bg);
	assert.ok(f && f[3] === 0, `${was}: Hintergrund „${bg}“ statt transparent — Kaskade: ${herkunft(Q, k, 'background-color', ctx)}`);
}
function rahmenSeite(k: Knoten, seite: string, ctx: Kontext): { breite: number; stil: string; farbe: string | undefined } {
	const st = s(k, `border-${seite}-style`, ctx) ?? 'none';
	const br = s(k, `border-${seite}-width`, ctx) ?? 'medium';
	return { breite: st === 'none' || st === 'hidden' ? 0 : br === 'medium' ? 3 : br === 'thin' ? 1 : laenge(br), stil: st, farbe: s(k, `border-${seite}-color`, ctx) };
}
function ohneRahmen(k: Knoten, seiten: string[], ctx: Kontext, was: string): void {
	for (const seite of seiten) {
		const r = rahmenSeite(k, seite, ctx);
		assert.equal(r.breite, 0, `${was}: Rahmen ${seite} ${r.breite}px ${r.stil} ${r.farbe} — Kaskade: ${herkunft(Q, k, `border-${seite}-style`, ctx)}`);
	}
}
function rahmen(k: Knoten, seite: string, ctx: Kontext, breite: number, farbToken: string, was: string): void {
	const r = rahmenSeite(k, seite, ctx);
	assert.equal(r.stil, 'solid', `${was}: Rahmen ${seite} Stil „${r.stil}“ statt solid — Kaskade: ${herkunft(Q, k, `border-${seite}-style`, ctx)}`);
	assert.equal(r.breite, breite, `${was}: Rahmen ${seite} ${r.breite}px statt ${breite}px — Kaskade: ${herkunft(Q, k, `border-${seite}-width`, ctx)}`);
	assert.equal(r.farbe, token(Q, farbToken, ctx.theme), `${was}: Rahmen ${seite} Farbe „${r.farbe}“ statt ${farbToken} — Kaskade: ${herkunft(Q, k, `border-${seite}-color`, ctx)}`);
}
const MONO = (theme: Theme = 'hell') => token(Q, '--g-font-mono', theme);
const tok = (name: string, ctx: Kontext) => token(Q, name, ctx.theme);
/** Kontrast Schrift gegen (ggf. halbtransparenten) Grund, gemischt über --g-paper des Modus. */
function kontrastAuf(k: Knoten, ctx: Kontext): number {
	const papier = farbe(tok('--g-paper', ctx))!;
	const vg = farbe(s(k, 'color', ctx));
	const hg = farbe(hintergrund(k, ctx));
	assert.ok(vg && hg, `Messaufbau: Farben nicht lesbar (color ${s(k, 'color', ctx)}, background ${hintergrund(k, ctx)})`);
	return kontrast(ueber(vg!, ueber(hg!, papier)), ueber(hg!, papier));
}

// ═══ Messaufbau ═══════════════════════════════════════════════════════════════════════

describe('#2980 Messaufbau', () => {
	test('Kaskade kennt die Komponenten der Seite (Scope-Klassen im Markup = kompiliertes CSS)', () => {
		const w = seite('route', DESKTOP);
		const leiste = einzig(w, 'hub-kopf-leiste');
		const hash = (leiste.attrs.class ?? '').split(/\s+/).find((c) => c.startsWith('svelte-'));
		assert.ok(hash && Q.komponenten.has(hash), `Scope-Klasse der Leiste (${hash}) nicht im kompilierten CSS gefunden`);
		assert.match(Q.komponenten.get(hash!)!.datei, /HubKopf\.svelte$/);
		assert.match(token(Q, '--g-accent-deep'), /^#[0-9a-f]{6}$/);
		assert.notEqual(token(Q, '--g-ink-3', 'hell'), token(Q, '--g-ink-3', 'dunkel'), 'Dunkel-Tokens nicht gelesen');
		// Gegenprobe der Kaskade: der Breadcrumb ist heute schon Mono 11 px in --g-ink-3.
		const krumen = einzig(w, 'hub-kopf-breadcrumb');
		gleich(krumen, 'font-family', DESKTOP, MONO(), 'Messaufbau Breadcrumb');
		laengeGleich(krumen, 'font-size', DESKTOP, 11, 'Messaufbau Breadcrumb');
	});
});

// ═══ AC-16: „Test schicken ▾“ als Akzent-Knopf mit Fläche --g-accent-deep ═════════════

for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		for (const lang of SPRACHEN) {
			test(`AC-16 (${art}, ${breite}, ${lang}): Knopf subscription-hub-send ist Btn accent, Fläche --g-accent-deep, Kontrast ≥ 4,5 hell und dunkel`, () => {
				const w = seite(art, ctx, lang);
				const knopf = einzig(w, 'subscription-hub-send');
				assert.equal(knopf.attrs['data-slot'], 'btn', 'Knopf ist kein Btn-Baustein');
				assert.equal(knopf.attrs['data-variant'], 'accent', `Knopf trägt Variante „${knopf.attrs['data-variant']}“ statt accent (heute Ink/primary)`);
				for (const c of [ctx, dunkel(ctx)]) {
					const flaeche = hintergrund(knopf, c);
					assert.equal(flaeche, tok('--g-accent-deep', c), `${c.theme}: Knopf-Fläche „${flaeche}“ statt --g-accent-deep — Kaskade: ${herkunft(Q, knopf, 'background-color', c)}`);
					assert.notEqual(flaeche, c.theme === 'hell' ? tok('--g-accent', c) : '', 'Fläche ist das Mockup-Orange --g-accent (AA verfehlt)');
					const k = kontrastAuf(knopf, c);
					assert.ok(k >= 4.5, `${c.theme}: Kontrast Schrift/Fläche ${k.toFixed(2)}:1 < 4,5`);
				}
			});
		}
	}
}

// ═══ AC-17/AC-18: Reiterleiste als Text-Reiter mit Unterstrich, auch am Handy ═════════

const REITER_PREFIX: Record<Art, string> = { route: 'trip-detail-tab', vergleich: 'compare-detail-tab' };
for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		test(`AC-17${ctx === HANDY ? '/AC-18' : ''} (${art}, ${breite}): Reiter ohne Pillen — inaktiv --g-ink-3/500, aktiv --g-ink/600 mit 2px-Unterstrich --g-accent, Grundlinie --g-rule`, () => {
			const w = seite(art, ctx);
			const wurzel = alle(w, (n) => n.attrs.role === 'tablist' && (n.attrs.class ?? '').includes('mtabbar'));
			assert.equal(wurzel.length, 1, `MTabBar-Wurzel ${wurzel.length}×`);
			const tabs = alle(wurzel[0], (n) => n.attrs.role === 'tab');
			assert.ok(tabs.length >= 4, `Reiter: ${tabs.length}`);
			assert.ok(tabs.every((t) => (t.attrs['data-testid'] ?? '').startsWith(REITER_PREFIX[art])), 'Reiter ohne erwartete testid');
			const aktiv = tabs.find((t) => t.attrs['data-state'] === 'active')!;
			const inaktiv = tabs.find((t) => t.attrs['data-state'] !== 'active')!;
			rahmen(wurzel[0], 'bottom', ctx, 1, '--g-rule', 'Grundlinie der Leiste');
			for (const [t, was] of [[aktiv, 'aktiver Reiter'], [inaktiv, 'inaktiver Reiter']] as const) {
				transparent(t, ctx, `${was} (Pillen-Hintergrund?)`);
				ohneRahmen(t, ['top', 'left', 'right'], ctx, `${was} (Pillen-Rahmen?)`);
				laengeGleich(t, 'font-size', ctx, 13, was);
			}
			gleich(inaktiv, 'color', ctx, tok('--g-ink-3', ctx), 'inaktiver Reiter');
			gleich(inaktiv, 'font-weight', ctx, '500', 'inaktiver Reiter');
			gleich(aktiv, 'color', ctx, tok('--g-ink', ctx), 'aktiver Reiter');
			gleich(aktiv, 'font-weight', ctx, '600', 'aktiver Reiter');
			rahmen(aktiv, 'bottom', ctx, 2, '--g-accent', 'Unterstrich aktiver Reiter');
			if (ctx === HANDY) {
				// AC-18: wischbar und 44-px-Tippfläche bleiben (#2284 AC-13).
				const ox = s(wurzel[0], 'overflow-x', ctx);
				assert.ok(ox === 'auto' || ox === 'scroll', `AC-18: Leiste nicht seitlich scrollbar (overflow-x ${ox})`);
				for (const t of tabs) {
					const h = Math.max(laenge(s(t, 'min-height', ctx)) || 0, laenge(s(t, 'height', ctx)) || 0);
					assert.ok(h >= 44, `AC-18: Reiter ${t.attrs['data-value']} Tippfläche ${h}px < 44`);
				}
			}
		});
	}
}

// ═══ AC-19: Kennzahlenzeile am Handy entfällt ═════════════════════════════════════════

const tripGeplant = () => tripMallorca({ stages: VIER_ETAPPEN.map((st, i) => ({ ...st, date: `2026-09-1${i}` })) });
for (const lang of SPRACHEN) {
	for (const [name, daten] of [['geplant', tripGeplant], ['läuft', () => tripMallorca()]] as const) {
		test(`AC-19 (Trip ${name}, Handy, ${lang}): keine Kennzahlenzeile (mobile-metrics), kein „Start in“, Meta-Zeile bleibt`, () => {
			const w = seite('route', HANDY, lang, daten());
			assert.equal(mitTestid(w, 'trip-header-mobile-metrics').length, 0, 'Kennzahlenzeile trip-header-mobile-metrics ist noch da (#416 entfällt)');
			for (const id of ['metric-etappe', 'metric-briefing', 'metric-start']) assert.equal(mitTestid(w, id).length, 0, `Kennzahl ${id} ist noch da`);
			const kopf = alle(w, (n) => (n.attrs.class ?? '').split(/\s+/).includes('hub-kopf'));
			assert.equal(kopf.length, 1, 'Messaufbau: Hub-Kopf nicht gefunden');
			assert.doesNotMatch(text(kopf[0]), /start in|starts in/i, '„Start in“ steht im Kopf');
			assert.equal(mitTestid(w, 'hub-kopf-meta').length, 1, 'Meta-Zeile fehlt');
		});
	}
}
test('AC-19 (Orte, Handy): keine Kennzahlenzeile', () => {
	const w = seite('vergleich', HANDY);
	assert.equal(mitTestid(w, 'trip-header-mobile-metrics').length, 0);
	assert.equal(mitTestid(w, 'hub-kopf-meta').length, 1);
});

// ═══ AC-20: Meta-Zeile Mono 13 px --g-ink-3 ═══════════════════════════════════════════

for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		for (const lang of SPRACHEN) {
			test(`AC-20 (${art}, ${breite}, ${lang}): Meta-Zeile Mono, 13 px, --g-ink-3`, () => {
				const meta = einzig(seite(art, ctx, lang), 'hub-kopf-meta');
				gleich(meta, 'font-family', ctx, MONO(), 'Meta-Zeile');
				laengeGleich(meta, 'font-size', ctx, 13, 'Meta-Zeile');
				gleich(meta, 'color', ctx, tok('--g-ink-3', ctx), 'Meta-Zeile');
			});
		}
	}
}

// ═══ AC-21/AC-22: Status-Pill gefüllt ohne Rahmen, aktiv = good, sonst neutral ═══════

const GOOD_RGB = [61, 107, 58];
function pillPruefen(p: Knoten, zustand: string, ctx: Kontext, was: string): void {
	assert.ok(!('data-outlined' in p.attrs), `${was}: Pill trägt noch data-outlined (umrandet statt gefüllt)`);
	ohneRahmen(p, ['top', 'right', 'bottom', 'left'], ctx, `${was} (Rahmen)`);
	gleich(p, 'font-family', ctx, MONO(ctx.theme), was);
	laengeGleich(p, 'font-size', ctx, 11, was);
	gleich(p, 'text-transform', ctx, 'uppercase', was);
	const vg = s(p, 'color', ctx);
	const hg = hintergrund(p, ctx);
	if (zustand === 'active') {
		assert.equal(vg, tok('--g-good', ctx), `${was}: aktiv Schrift „${vg}“ statt --g-good — Kaskade: ${herkunft(Q, p, 'color', ctx)}`);
		const f = farbe(hg);
		assert.ok(f && f[0] === GOOD_RGB[0] && f[1] === GOOD_RGB[1] && f[2] === GOOD_RGB[2] && f[3] > 0 && f[3] <= 0.2, `${was}: aktiv Grund „${hg}“ statt hellgrün rgba(61,107,58,≈0,1) — Kaskade: ${herkunft(Q, p, 'background-color', ctx)}`);
	} else {
		const erlaubt = ctx.theme === 'hell' ? [tok('--g-ink-3', ctx)] : [tok('--g-ink-3', ctx), tok('--g-ink-2', ctx)];
		assert.ok(erlaubt.includes(vg!), `${was}: neutral Schrift „${vg}“ statt --g-ink-3 — Kaskade: ${herkunft(Q, p, 'color', ctx)}`);
		assert.equal(hg, tok('--g-paper-deep', ctx), `${was}: neutral Grund „${hg}“ statt --g-paper-deep — Kaskade: ${herkunft(Q, p, 'background-color', ctx)}`);
	}
}
for (const art of ARTEN) {
	for (const zustand of ZUSTAENDE) {
		test(`AC-21 (${art}, ${zustand}): Pill gefüllt ohne Rahmen, Mono 11 px uppercase per CSS, ${zustand === 'active' ? 'good' : 'neutral'}; DOM-Text und data-status unverändert`, () => {
			for (const lang of SPRACHEN) {
				const daten = (art === 'route' ? TRIP_ZUSTAENDE : VERGLEICH_ZUSTAENDE)[zustand]();
				const w = seite(art, DESKTOP, lang, daten);
				const p = einzig(w, 'trip-detail-status-badge');
				assert.equal(p.attrs['data-status'], zustand, 'data-status');
				assert.equal(text(p), trFor(lang, `trip.status.${zustand}` as never), `DOM-Text „${text(p)}“ nicht der Katalogtext (Großschreibung nur per CSS)`);
				pillPruefen(p, zustand, DESKTOP, `Pill ${art}/${zustand}/${lang}`);
			}
		});
	}
}
for (const zustand of ['active', 'draft'] as const) {
	for (const theme of ['hell', 'dunkel'] as const) {
		test(`AC-22 (${zustand === 'active' ? 'good' : 'neutral'}, ${theme}): Pill-Ton nach Mockup und Kontrast Schrift/Grund ≥ 4,5:1`, () => {
			for (const art of ARTEN) {
				const ctx: Kontext = { ...HANDY, theme };
				const daten = (art === 'route' ? TRIP_ZUSTAENDE : VERGLEICH_ZUSTAENDE)[zustand]();
				const p = einzig(seite(art, ctx, 'de', daten), 'trip-detail-status-badge');
				pillPruefen(p, zustand, ctx, `Pill ${art}/${zustand}/${theme}`);
				const k = kontrastAuf(p, ctx);
				assert.ok(k >= 4.5, `${art}/${zustand}/${theme}: Kontrast ${k.toFixed(2)}:1 < 4,5`);
			}
		});
	}
}

// ═══ AC-23/AC-24: Kopfband (Brotkrumen) ════════════════════════════════════════════════

const NAME: Record<Art, string> = { route: 'GR221 Mallorca', vergleich: 'Skitouren Tirol' };
function nameElement(krumen: Knoten, name: string): Knoten {
	const kandidaten = alle(krumen, (n) => n.texte.join('').trim() === name);
	assert.equal(kandidaten.length, 1, `Name „${name}“ steht nicht als eigenes Element im Breadcrumb (gefunden ${kandidaten.length}); Breadcrumb-Text „${text(krumen)}“`);
	return kandidaten[0];
}
for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		test(`AC-23 (${art}, ${breite}): Kopfband Mono 11 px uppercase per CSS in --g-ink-3, Name --g-ink 500, Linie --g-rule-soft`, () => {
			for (const lang of SPRACHEN) {
				const w = seite(art, ctx, lang);
				const krumen = einzig(w, 'hub-kopf-breadcrumb');
				gleich(krumen, 'font-family', ctx, MONO(), 'Breadcrumb');
				laengeGleich(krumen, 'font-size', ctx, 11, 'Breadcrumb');
				gleich(krumen, 'text-transform', ctx, 'uppercase', 'Breadcrumb');
				gleich(krumen, 'color', ctx, tok('--g-ink-3', ctx), 'Breadcrumb');
				const link = alle(krumen, (n) => n.tag === 'a')[0];
				gleich(link, 'color', ctx, tok('--g-ink-3', ctx), 'Elternlink im Breadcrumb');
				const name = nameElement(krumen, NAME[art]);
				gleich(name, 'color', ctx, tok('--g-ink', ctx), 'Name im Breadcrumb');
				gleich(name, 'font-weight', ctx, '500', 'Name im Breadcrumb');
				gleich(name, 'text-transform', ctx, 'uppercase', 'Name im Breadcrumb');
				assert.ok(text(krumen).includes(NAME[art]), 'DOM-Text des Breadcrumbs groß geschrieben (nur per CSS erlaubt)');
				rahmen(einzig(w, 'hub-kopf-leiste'), 'bottom', ctx, 1, '--g-rule-soft', 'Unterkante Kopfband');
			}
		});
	}
}

const LANG_NAME: Record<Art, string> = {
	route: 'GR221 Mallorca – Ruta de Pedra en Sec von Port d’Andratx bis Pollença über Deià und Lluc',
	vergleich: 'Skitouren Tirol – Zillertaler und Tuxer Alpen mit Gerlospass, Hochfügen und Kühtai'
};
const langeDaten = (art: Art) =>
	art === 'route' ? tripMallorca({ name: LANG_NAME.route, shortcode: 'MLC' }) : C.vergleichAktiv({ name: LANG_NAME.vergleich });
for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		test(`AC-24 (${art}, ${breite}): voller Name im Breadcrumb (kein Kürzel), kein Zurück-Pfeil, Umbruch statt Ellipsis`, () => {
			const w = seite(art, ctx, 'de', langeDaten(art));
			const krumen = einzig(w, 'hub-kopf-breadcrumb');
			const name = nameElement(krumen, LANG_NAME[art]);
			assert.ok(!/\bMLC\b/.test(text(krumen)), `Kürzel (shortcode) steht im Breadcrumb: „${text(krumen)}“`);
			const leiste = einzig(w, 'hub-kopf-leiste');
			const zurueck = alle(w, (n) => (n.attrs.class ?? '').split(/\s+/).includes('back-mobil') || n.attrs['data-testid'] === 'back-mobil');
			assert.equal(zurueck.length, 0, 'Element back-mobil (Zurück-Pfeil) ist noch da');
			const links = alle(leiste, (n) => n.tag === 'a');
			assert.equal(links.length, 1, `Leiste hat ${links.length} Links (erwartet nur den Elternteil): ${links.map((l) => l.attrs['aria-label'] ?? text(l)).join(', ')}`);
			for (const [k, was] of [[krumen, 'Breadcrumb'], [name, 'Name']] as const) {
				const ws = s(k, 'white-space', ctx);
				assert.notEqual(ws, 'nowrap', `${was}: white-space nowrap (kein Umbruch) — Kaskade: ${herkunft(Q, k, 'white-space', ctx)}`);
				const to = s(k, 'text-overflow', ctx);
				assert.notEqual(to, 'ellipsis', `${was}: text-overflow ellipsis (Kürzung) — Kaskade: ${herkunft(Q, k, 'text-overflow', ctx)}`);
			}
			const ow = s(name, 'overflow-wrap', ctx) ?? s(name, 'word-break', ctx);
			assert.ok(ow === 'anywhere' || ow === 'break-word', `Name bricht nicht um (overflow-wrap ${ow}) — Kaskade: ${herkunft(Q, name, 'overflow-wrap', ctx)}`);
		});
	}
}

// ═══ AC-25: Kebab ghost mit Rahmen --g-rule, 44 px am Handy, vor „Test schicken“ ═════

for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		test(`AC-25 (${art}, ${breite}): Kebab transparent mit Rahmen --g-rule${ctx === HANDY ? ', ≥ 44 × 44 px' : ''}, vor „Test schicken“`, () => {
			const w = seite(art, ctx);
			const kebab = einzig(w, 'subscription-kebab');
			const senden = einzig(w, 'subscription-hub-send');
			assert.ok(kebab.nr < senden.nr, 'Kebab steht nicht vor „Test schicken“');
			transparent(kebab, ctx, 'Kebab');
			for (const seite of ['top', 'right', 'bottom', 'left']) rahmen(kebab, seite, ctx, 1, '--g-rule', 'Kebab');
			if (ctx === HANDY) {
				for (const [a, b] of [['height', 'min-height'], ['width', 'min-width']]) {
					const v = Math.max(laenge(s(kebab, a, ctx)) || 0, laenge(s(kebab, b, ctx)) || 0);
					assert.ok(v >= 44, `Kebab ${a} ${v}px < 44`);
				}
			}
		});
	}
}

// ═══ AC-26/AC-27: Vorlage-Karte ═══════════════════════════════════════════════════════

const VK = path.join(KOMP, 'organisms', 'wetter-tab', 'VorlageKarte.svelte');
const VorlageKarte = (await import(pathToFileURL(VK).href)).default;
const LISTE = [
	{ id: 'alpen-trekking', label: 'Alpen-Trekking', anzahl: 14, stichworte: ['thunder', 'gust'] },
	{ id: 'wandern', label: 'Wandern', anzahl: 10, stichworte: ['precipitation'] }
];
function karte(context: Art, lang: Lang, abweichungen: number): Knoten {
	return mitSprache(lang, () =>
		baum(
			render(VorlageKarte as never, {
				props: {
					context, vorlageId: 'alpen-trekking', liste: LISTE, eigene: [], abweichungen,
					metrikName: (id: string) => id, aboAmpel: { metrics: {} },
					onUebernehmen: () => {}, onEigene: () => {}, onZuruecksetzen: () => {}, onGespeichert: () => {}
				}
			} as never).body
		)
	);
}
for (const art of ARTEN) {
	for (const [breite, ctx] of BREITEN) {
		test(`AC-26 (${art}, ${breite}): Wähler Rahmen --g-rule, Grund --g-paper, 15 px/600; „▾ unverändert“ Mono 11 px --g-ink-3`, () => {
			for (const [lang, abw] of [['de', 0], ['en', 2]] as const) {
				const k = karte(art, lang, abw);
				const picker = einzig(k, 'wetter-vorlage-picker');
				for (const seite of ['top', 'right', 'bottom', 'left']) rahmen(picker, seite, ctx, 1, '--g-rule', 'Vorlagen-Wähler');
				gleich(picker, 'background-color', ctx, tok('--g-paper', ctx), 'Vorlagen-Wähler');
				const nameEl = alle(picker, (n) => n.texte.join('').trim() === 'Alpen-Trekking');
				assert.equal(nameEl.length, 1, 'Vorlagenname nicht als eigenes Element im Wähler');
				laengeGleich(nameEl[0], 'font-size', ctx, 15, 'Vorlagenname');
				gleich(nameEl[0], 'font-weight', ctx, '600', 'Vorlagenname');
				const status = einzig(k, 'wetter-vorlage-status');
				const zusatz = alle(picker, (n) => n.texte.join('').includes('▾'));
				assert.equal(zusatz.length, 1, 'Zusatz „▾ …“ nicht als eigenes Element im Wähler');
				for (const [el, was] of [[zusatz[0], 'Zusatz ▾'], [status, 'Zusatz-Status']] as const) {
					gleich(el, 'font-family', ctx, MONO(), was);
					laengeGleich(el, 'font-size', ctx, 11, was);
					gleich(el, 'color', ctx, tok('--g-ink-3', ctx), was);
				}
			}
		});
		test(`AC-27 (${art}, ${breite}): Kartenzeile align-items center (Speichern-Knopf mittig zum Wähler)`, () => {
			const k = karte(art, 'de', 2);
			const zeile = alle(k, (n) => n.attrs['data-abschnitt'] === 'vorlage');
			assert.equal(zeile.length, 1, 'Karte [data-abschnitt="vorlage"] nicht gefunden');
			gleich(zeile[0], 'align-items', ctx, 'center', 'Vorlage-Karte');
			assert.ok(alle(zeile[0], (n) => n.attrs['data-testid'] === 'wetter-vorlage-als-eigene').length === 1, 'Speichern-Knopf nicht in der Karte');
		});
	}
}

// ═══ AC-28: Abschnittskopf Wetter ══════════════════════════════════════════════════════

const WetterTabInhalt = (await import(pathToFileURL(path.join(KOMP, 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte')).href)).default;
for (const [breite, ctx] of BREITEN) {
	for (const lang of SPRACHEN) {
		test(`AC-28 (${breite}, ${lang}): Abschnittskopf Wetter — Erklärtext ≤ 68ch, 13 px, --g-ink-3; Linie --g-rule-soft mit 12 px Abstand`, () => {
			const w = mitSprache(lang, () => baum(render(WetterTabInhalt as never, { props: { context: 'route', trip: { id: 't1', name: 'Trip', stages: [] } } } as never).body));
			const titel = einzig(w, 'wetter-tab-titel');
			const kopf = titel.eltern!;
			const erklaer = einzig(w, 'wetter-tab-erklaer');
			assert.ok(erklaer.eltern === kopf, 'Erklärtext steht nicht im Abschnittskopf');
			rahmen(kopf, 'bottom', ctx, 1, '--g-rule-soft', 'Abschnittskopf');
			laengeGleich(kopf, 'padding-bottom', ctx, 12, 'Abschnittskopf');
			gleich(erklaer, 'max-width', ctx, '68ch', 'Erklärtext');
			laengeGleich(erklaer, 'font-size', ctx, 13, 'Erklärtext');
			gleich(erklaer, 'color', ctx, tok('--g-ink-3', ctx), 'Erklärtext');
		});
	}
}
