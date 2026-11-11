// Issue #2913 Scheibe (c) (AC-2, AC-3): Zeilen der Karte „Amtliche Warnungen & Radar" als reine Daten —
// je Zeile Testid, Katalogschlüssel, Zustand und der Handler, der beim Umlegen gerufen wird. Die
// Komponente WarnungenRadarKarte rendert nur diese Liste; die Zuordnung Schalter → Handler ist damit
// ohne DOM prüfbar. Die Radar-Zeile gibt es nur mit `mitRadar` (Orts-Briefing; Trip folgt mit S8 #2800).
// Kein Svelte-/Browser-Import, lauffähig unter node --experimental-strip-types.

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
