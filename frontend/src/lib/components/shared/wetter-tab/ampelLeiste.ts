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

/**
 * #2913 AC-9: Mittelpunkte (px) der Grenzzahlen, sodass sich benachbarte Zahlen nicht überlappen
 * und keine über den Rand der Leiste ragt. Liegen Grenzen eng beieinander (z. B. 27/30/33 °C bei
 * 160 px Mittelspalte), wird die Gruppe um den Mittelwert ihrer Soll-Lagen auseinandergezogen;
 * ohne Konflikt bleibt jede Zahl genau über ihrer Grenze (Mockup-Bild).
 * `pos` in Prozent (wie `LeisteMarke.pos`, aufsteigend), `breiten` und `breite` (Leiste) in px.
 */
export function entzerreMarken(pos: readonly number[], breiten: readonly number[], breite: number, abstand: number): number[] {
	const anker = pos.map((p) => (p / 100) * breite);
	type Gruppe = { von: number; bis: number; links: number };
	/** Abstand der Mittelpunkte von Zahl `von` bis Zahl `j` einer Gruppe (dicht an dicht). */
	const versatz = (von: number, j: number) => {
		let v = 0;
		for (let k = von + 1; k <= j; k++) v += (breiten[k - 1] + breiten[k]) / 2 + abstand;
		return v;
	};
	/** Gruppe so legen, dass der Mittelwert der Lagen dem Mittelwert der Soll-Lagen entspricht, im Rand. */
	const lege = (von: number, bis: number): Gruppe => {
		let summe = 0;
		for (let j = von; j <= bis; j++) summe += anker[j] - versatz(von, j);
		const min = breiten[von] / 2;
		const max = breite - breiten[bis] / 2 - versatz(von, bis);
		return { von, bis, links: Math.max(min, Math.min(max, summe / (bis - von + 1))) };
	};
	const stapel: Gruppe[] = [];
	for (let i = 0; i < anker.length; i++) {
		stapel.push(lege(i, i));
		while (stapel.length > 1) {
			const b = stapel[stapel.length - 1];
			const a = stapel[stapel.length - 2];
			const endeA = a.links + versatz(a.von, a.bis);
			if (b.links - endeA >= (breiten[a.bis] + breiten[b.von]) / 2 + abstand - 1e-6) break;
			stapel.splice(-2, 2, lege(a.von, b.bis));
		}
	}
	const aus: number[] = [];
	for (const g of stapel) for (let j = g.von; j <= g.bis; j++) aus.push(g.links + versatz(g.von, j));
	return aus;
}
