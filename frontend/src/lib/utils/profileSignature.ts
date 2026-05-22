// Issue #238 — Profil-Signaturen im Design-System.
//
// Liefert pro ActivityProfile eine visuelle Signatur (Akzentfarbe als
// CSS-Variablen-Referenz, Unicode-Icon, Eyebrow-Label). Zentrale Quelle fuer
// Frontend-Cards und Mail-Renderer.
//
// Bei unbekannter oder leerer Eingabe wird die Signatur von `allgemein`
// zurueckgegeben (Fallback, kein Throw).
//
// Spec: docs/specs/modules/issue_238_profile_signatures.md

import type { ActivityProfile } from '$lib/types';

export type ProfileSignature = {
	accent: string;          // CSS-Variablen-Referenz: var(--g-profile-...)
	icon: string;            // Unicode-Glyph
	eyebrow: string;         // Sichtbares Label
};

const SIGNATURES: Record<ActivityProfile, ProfileSignature> = {
	wintersport: {
		accent: 'var(--g-profile-wintersport)',
		icon: '❄',          // Schneeflocke
		eyebrow: 'Wintersport',
	},
	wandern: {
		accent: 'var(--g-profile-wandern)',
		icon: '\u{1F97E}',       // Wanderschuh
		eyebrow: 'Wandern',
	},
	summer_trekking: {
		accent: 'var(--g-profile-summer-trekking)',
		icon: '\u{1F3D4}',       // Berg-Symbol
		eyebrow: 'Sommer-Trekking',
	},
	allgemein: {
		accent: 'var(--g-profile-allgemein)',
		icon: '◯',          // Kreis
		eyebrow: 'Allgemein',
	},
};

export function profileSignature(profile: ActivityProfile | string | null | undefined): ProfileSignature {
	if (profile == null) return SIGNATURES.allgemein;
	return SIGNATURES[profile as ActivityProfile] ?? SIGNATURES.allgemein;
}
