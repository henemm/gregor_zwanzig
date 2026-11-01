// Issue #2653 (i18n F4), seit #2655 (F6) in lib/i18n: Katalogtexte mit hervorgehobenen Werten (<strong>, Link)
// ohne HTML im Katalog. Der Text wird OHNE Parameter geholt und an seinen
// `{platzhalter}`n zerlegt; das Markup setzt an diesen Stellen das Element ein.
// So bleibt die Satzstellung je Sprache im Katalog (keine Satz-Konkatenation).

export type Teil = { text: string; platzhalter: string | null };

export function textTeile(vorlage: string): Teil[] {
	const teile: Teil[] = [];
	let rest = 0;
	for (const m of vorlage.matchAll(/\{([a-z0-9_]+)\}/g)) {
		const pos = m.index ?? 0;
		if (pos > rest) teile.push({ text: vorlage.slice(rest, pos), platzhalter: null });
		teile.push({ text: '', platzhalter: m[1] });
		rest = pos + m[0].length;
	}
	if (rest < vorlage.length) teile.push({ text: vorlage.slice(rest), platzhalter: null });
	return teile;
}
