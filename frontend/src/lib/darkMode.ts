// Issue #2400 — Dunkles Design zur Laufzeit schalten (Umschalter in Sidebar und Konto-Blatt).
// Die Dark-Werte stehen als `:root[data-theme="dark"]` in app.css (eine Quelle). Hier wird nur
// der Modus geschaltet — dieselben drei Dinge wie das Kopf-Skript in app.html vor dem ersten
// Paint: Attribut `data-theme`, `color-scheme` und `<meta name="theme-color">`.

/** theme-color je Modus = --g-paper hell bzw. aus dem Dark-Block von app.css. */
export const THEME_COLOR_HELL = '#f6f4ee';
export const THEME_COLOR_DUNKEL = '#141412';

/** Ausschnitt von `Document`, den das Umschalten braucht (das echte `document` passt). */
export interface DarkModeDocument {
	documentElement: {
		setAttribute(name: string, value: string): void;
		removeAttribute(name: string): void;
		style: { colorScheme: string; removeProperty(name: string): string };
	};
	querySelector(selector: string): { setAttribute(name: string, value: string): void } | null;
}

export function applyDarkMode(doc: DarkModeDocument, dark: boolean): void {
	const el = doc.documentElement;
	if (dark) {
		el.setAttribute('data-theme', 'dark');
		el.style.colorScheme = 'dark';
	} else {
		el.removeAttribute('data-theme');
		el.style.removeProperty('color-scheme');
	}
	doc
		.querySelector('meta[name="theme-color"]')
		?.setAttribute('content', dark ? THEME_COLOR_DUNKEL : THEME_COLOR_HELL);
}
