// Issue #2652 (i18n F3) — Pruefhelfer: welche deutschen Katalogtexte des
// Pakets (home.*, listen.*) stehen noch im sichtbaren Text einer englischen
// Ausgabe? Verglichen wird gegen die ECHTEN Katalogwerte (de vs. en), nie
// gegen Literale. Texte mit Platzhaltern werden an den Platzhaltern zerlegt;
// geprueft werden die festen Teilstuecke mit mindestens vier Buchstaben.

import { de } from '../../lib/i18n/messages/de/index.ts';
import { en } from '../../lib/i18n/messages/en/index.ts';

const DE = de as Record<string, string>;
const EN = en as Record<string, string>;
const B = 'A-Za-zÄÖÜäöüß';

export function sichtbarerText(html: string): string {
	return html
		.replace(/<style[\s\S]*?<\/style>/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Beschriftende Attributwerte (title, aria-label, placeholder, alt). */
export function attributText(html: string): string {
	return [...html.matchAll(/\s(?:title|aria-label|placeholder|alt)="([^"]*)"/g)].map((m) => m[1]).join(' | ');
}

/** Deutsche Teilstuecke der F3-Schluessel, die im Text vorkommen (leer = alles englisch). */
export function deutscheReste(text: string, praefixe = ['home.', 'listen.']): string[] {
	const reste = new Set<string>();
	for (const [k, wert] of Object.entries(DE)) {
		if (!praefixe.some((p) => k.startsWith(p)) || k.startsWith('home.monat') || EN[k] === wert) continue;
		const enTeile = new Set(EN[k].split(/\{[a-z0-9_]+\}/).map((s) => s.trim()));
		for (const teil of wert.split(/\{[a-z0-9_]+\}/).map((s) => s.trim())) {
			if ((teil.match(new RegExp(`[${B}]`, 'g')) ?? []).length < 4 || enTeile.has(teil)) continue;
			const muster = teil.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
			if (new RegExp(`(^|[^${B}])${muster}([^${B}]|$)`).test(text)) reste.add(`${k}: ${teil}`);
		}
	}
	return [...reste].sort();
}
