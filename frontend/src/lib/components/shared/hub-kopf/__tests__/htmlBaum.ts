// Prüfstand-Helfer #2837 S1 (Hub-Kopf): baut aus dem SSR-Output (svelte/server)
// einen schlichten Element-Baum, damit die Tests LAGE-Zusicherungen prüfen können
// („Status-Badge steht in derselben Zeile wie die Überschrift", „Senden sitzt in der
// Leiste", „Kind des Breadcrumbs ist kein Link") statt Text-Greps über Quelltext.
// Kein DOM, kein jsdom: das SSR-Markup ist wohlgeformt (Svelte schließt jedes Element),
// Void-Elemente werden gesondert behandelt, Kommentare vorher entfernt.
//
// Pfadregel #1409: Aufrufer lösen Prüflinge relativ zur EIGENEN Datei auf.

export interface Knoten {
	tag: string;
	attrs: Record<string, string>;
	kinder: Knoten[];
	eltern: Knoten | null;
	/** Text direkt in diesem Element (ohne Kinder-Elemente), in Dokumentreihenfolge. */
	texte: string[];
	/** fortlaufende Nummer in Dokumentreihenfolge (öffnende Tags) */
	nr: number;
}

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);

function entity(s: string): string {
	return s
		.replace(/&nbsp;/g, ' ')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/&amp;/g, '&');
}

function attribute(roh: string): Record<string, string> {
	const out: Record<string, string> = {};
	for (const m of roh.matchAll(/([^\s=/"'>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g)) {
		out[m[1]] = entity(m[2] ?? m[3] ?? m[4] ?? '');
	}
	return out;
}

/** SSR-HTML -> Wurzelknoten (tag '#root'). Style-/Script-Inhalte werden übersprungen. */
export function baum(html: string): Knoten {
	const quelle = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(style|script)\b[\s\S]*?<\/\1>/g, '');
	const wurzel: Knoten = { tag: '#root', attrs: {}, kinder: [], eltern: null, texte: [], nr: -1 };
	let akt = wurzel;
	let nr = 0;
	const re = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:"[^"]*"|'[^']*'|[^'">])*)>|([^<]+)/g;
	for (const m of quelle.matchAll(re)) {
		if (m[4] !== undefined) {
			akt.texte.push(entity(m[4]));
			continue;
		}
		const zu = m[1] === '/';
		const tag = m[2].toLowerCase();
		if (zu) {
			// bis zum passenden offenen Element hochlaufen (robust gegen Unregelmäßigkeiten)
			let k: Knoten | null = akt;
			while (k && k.tag !== tag) k = k.eltern;
			if (k && k.eltern) akt = k.eltern;
			continue;
		}
		const roh = m[3] ?? '';
		const knoten: Knoten = { tag, attrs: attribute(roh.replace(/\/\s*$/, '')), kinder: [], eltern: akt, texte: [], nr: nr++ };
		akt.kinder.push(knoten);
		if (!VOID.has(tag) && !/\/\s*$/.test(roh)) akt = knoten;
	}
	return wurzel;
}

export function alle(k: Knoten, pred: (n: Knoten) => boolean): Knoten[] {
	const out: Knoten[] = [];
	(function lauf(n: Knoten) {
		if (n.tag !== '#root' && pred(n)) out.push(n);
		n.kinder.forEach(lauf);
	})(k);
	return out;
}

export const mitTestid = (k: Knoten, id: string): Knoten[] => alle(k, (n) => n.attrs['data-testid'] === id);

/** Genau ein Element mit dieser testid, sonst sprechender Fehler. */
export function einzig(k: Knoten, id: string): Knoten {
	const t = mitTestid(k, id);
	if (t.length !== 1) throw new Error(`data-testid="${id}" steht ${t.length}× im Render (erwartet genau 1)`);
	return t[0];
}

/** Sichtbarer Text eines Elements samt Kindern, Leerraum normalisiert. */
export function text(k: Knoten): string {
	const teile: string[] = [];
	(function lauf(n: Knoten) {
		// Texte und Kinder liegen getrennt; für Lesbarkeit reicht: eigene Texte, dann Kinder.
		// Für genaue Reihenfolge s. textInOrdnung.
		teile.push(...n.texte);
		n.kinder.forEach(lauf);
	})(k);
	return teile.join(' ').replace(/\s+/g, ' ').trim();
}

export function vorfahren(k: Knoten): Knoten[] {
	const out: Knoten[] = [];
	for (let n = k.eltern; n && n.tag !== '#root'; n = n.eltern) out.push(n);
	return out;
}

/** true, wenn `innen` (echt) unterhalb von `aussen` liegt. */
export const liegtIn = (innen: Knoten, aussen: Knoten): boolean => vorfahren(innen).includes(aussen);

/** Pfad von `von` (ausschließlich) bis `k` als Tag-Folge mit Positionsindex (Lagevergleich). */
export function lage(k: Knoten, von: Knoten): string {
	const teile: string[] = [];
	for (let n: Knoten | null = k; n && n !== von; n = n.eltern) {
		const i = n.eltern ? n.eltern.kinder.indexOf(n) : 0;
		teile.unshift(`${n.tag}[${i}]`);
	}
	return teile.join('>');
}

export const klassen = (k: Knoten): string[] => (k.attrs.class ?? '').split(/\s+/).filter(Boolean);
