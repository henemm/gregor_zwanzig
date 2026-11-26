// Issue #2913 Scheibe (c) (AC-2, AC-3): Zeilen der Karte „Amtliche Warnungen & Radar" als reine Daten —
// je Zeile Testid, Katalogschlüssel, Zustand und der Handler, der beim Umlegen gerufen wird. Die
// Komponente WarnungenRadarKarte rendert nur diese Liste; die Zuordnung Schalter → Handler ist damit
// ohne DOM prüfbar. Die Radar-Zeile gibt es nur mit `mitRadar` (Orts-Briefing und seit #2800 S8 Trip).
// Kein Svelte-/Browser-Import, lauffähig unter node --experimental-strip-types.

/** #2800: Katalogschlüssel für `{orte}` im Radar-Hinweis — Trip „deine Etappe", Orts-Briefing „deine Orte". */
export type RadarZiel = 'wetter.radar.deine_orte' | 'wetter.radar.deine_etappe' | 'wetter.radar.dein_ort';

/** #3430: Ziel je Kontext; im Orts-Briefing mit genau einem Ort „deinen Ort“ (ADR-0124 Nr. 10). */
const RADAR_ZIEL: Record<'route' | 'vergleich', (ortAnzahl: number | undefined) => RadarZiel> = {
	route: () => 'wetter.radar.deine_etappe',
	vergleich: (n) => (n === 1 ? 'wetter.radar.dein_ort' : 'wetter.radar.deine_orte')
};

/** #3430: reine Auswahl des Radar-Ziels — Trip immer „deine Etappe", Orte bei genau einem Ort „deinen Ort", sonst „deine Orte". */
export function radarZiel(kontext: 'route' | 'vergleich', ortAnzahl: number | undefined): RadarZiel {
	return RADAR_ZIEL[kontext](ortAnzahl);
}

export interface SchalterZeile {
	testid: 'wetter-warnungen-schalter' | 'wetter-radar-schalter';
	titel: 'wetter.warnungen.titel' | 'wetter.radar.titel';
	hinweis: 'wetter.warnungen.beschreibung' | 'wetter.radar.beschreibung';
	an: boolean;
	umlegen: (an: boolean) => void;
}

export interface ZeilenEingabe {
	warnungenAn: boolean;
	radarAn: boolean;
	mitRadar: boolean;
	onWarnungen: (an: boolean) => void;
	onRadar: (an: boolean) => void;
}

export function schalterZeilen(e: ZeilenEingabe): SchalterZeile[] {
	const zeilen: SchalterZeile[] = [
		{ testid: 'wetter-warnungen-schalter', titel: 'wetter.warnungen.titel', hinweis: 'wetter.warnungen.beschreibung', an: e.warnungenAn, umlegen: e.onWarnungen }
	];
	if (e.mitRadar) {
		zeilen.push({ testid: 'wetter-radar-schalter', titel: 'wetter.radar.titel', hinweis: 'wetter.radar.beschreibung', an: e.radarAn, umlegen: e.onRadar });
	}
	return zeilen;
}
