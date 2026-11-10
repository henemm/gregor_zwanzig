// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: Geometrie der Ampel-Leiste einer Zeile.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md §4 (Mockup Fassung 3, `band()`).
//
// Von links nach rechts: unten rot · orange · gelb · gruen · oben gelb · orange · rot. Nur gesetzte
// Grenzen erzeugen ein Segment; der Wertebereich ergibt sich aus den Grenzen selbst (mit Rand),
// es gibt keine Frontend-Kopie fester Skalen. Gewitter: drei Stufen keins · mittel · hoch.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, AmpelMetrik, AmpelSeite } from '../../../types.ts';

export type LeisteFarbe = 'green' | 'yellow' | 'orange' | 'red';
export type LeisteSegment = { farbe: LeisteFarbe; anteil: number };
export type LeisteMarke = { wert: number; pos: number };
export type Leiste = { segmente: LeisteSegment[]; marken: LeisteMarke[] };

type Grenze = [LeisteFarbe, number];

function gesetzt(seite: AmpelSeite | null | undefined, folge: readonly (keyof AmpelSeite)[]): Grenze[] {
	const aus: Grenze[] = [];
	for (const k of folge) {
		const v = seite?.[k];
		if (typeof v === 'number' && Number.isFinite(v)) aus.push([k as LeisteFarbe, v]);
	}
	return aus;
}

/** Leiste einer Zeile mit Grenzen; ohne Grenze ganz gruen. */
export function leisteVon(e: AmpelMetrik | null | undefined): Leiste {
	const unten = gesetzt(e?.lower, ['red', 'orange', 'yellow']);
	const oben = gesetzt(e?.upper, ['yellow', 'orange', 'red']);
	const werte = [...unten, ...oben].map(([, v]) => v);
	if (werte.length === 0) return { segmente: [{ farbe: 'green', anteil: 1 }], marken: [] };
	const lo = Math.min(...werte);
	const hi = Math.max(...werte);
	const rand = Math.max((hi - lo) * 0.3, Math.abs(hi) * 0.1, 1);
	const mn = lo - rand;
	const span = hi + rand - mn;
	const klemm = (v: number) => Math.min(mn + span, Math.max(mn, v));
	const segmente: LeisteSegment[] = [];
	const marken: LeisteMarke[] = [];
	let prev = mn;
	for (const [farbe, v] of unten) {
		const x = Math.max(prev, klemm(v));
		segmente.push({ farbe, anteil: (x - prev) / span });
		marken.push({ wert: v, pos: ((x - mn) / span) * 100 });
		prev = x;
	}
	const gruenEnde = oben.length ? Math.max(prev, klemm(oben[0][1])) : mn + span;
	segmente.push({ farbe: 'green', anteil: (gruenEnde - prev) / span });
	prev = gruenEnde;
	oben.forEach(([farbe, v], i) => {
		marken.push({ wert: v, pos: ((klemm(v) - mn) / span) * 100 });
		const naechste = i + 1 < oben.length ? Math.max(prev, klemm(oben[i + 1][1])) : mn + span;
		segmente.push({ farbe, anteil: (naechste - prev) / span });
		prev = naechste;
	});
	return { segmente, marken };
}

/** Gewitter: keins (immer gruen) · mittel · hoch in den gewaehlten Farben. */
export function gewitterLeiste(thunder: Ampel['thunder']): LeisteSegment[] {
	return [
		{ farbe: 'green', anteil: 1 / 3 },
		{ farbe: thunder?.mittel ?? 'yellow', anteil: 1 / 3 },
		{ farbe: thunder?.hoch ?? 'orange', anteil: 1 / 3 }
	];
}
