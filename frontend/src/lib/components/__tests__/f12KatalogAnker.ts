// Issue #2661 (i18n F12) — feste Literal-Anker fuer JEDEN neuen Katalogwert des
// Pakets: Schluessel -> de | en, Platzhalter als <name>. Die deutschen Literale
// sind der Wortlaut VOR der Umstellung (Basis e574fd9ed) in BrandIcon,
// BrandWordmark, AppFooter, LocationForm, WeatherConfigDialog und +layout.svelte.
// NICHT aus dem Katalog nachziehen: eine Abweichung ist ein Befund.
// Verwendet in f12_reste_sprache.test.ts und deutsch_unveraendert.test.ts (NEU_IN_F12).

export const F12_ANKER: [schluessel: string, de: string, en: string][] = [
	// ── Marke (unuebersetzt, Eigenname) ──
	['bausteine.marke.name', 'Gregor Zwanzig', 'Gregor Zwanzig'],
	['bausteine.marke.gregor', 'gregor', 'gregor'],
	['bausteine.marke.zwanzig', 'zwanzig', 'zwanzig'],
	// ── AppFooter ──
	['nav.footer.rechtliches', 'Rechtliches', 'Legal'],
	['nav.footer.impressum', 'Impressum', 'Legal notice'],
	['nav.footer.datenschutz', 'Datenschutz', 'Privacy policy'],
	// ── +layout.svelte: Systemhinweise ──
	['nav.hinweis.update_fehlgeschlagen', 'Aktualisieren fehlgeschlagen — bitte erneut versuchen.', 'Update failed — please try again.'],
	['nav.hinweis.update_verfuegbar', 'Neue Version verfügbar. Wird erst auf Antippen geladen.', 'New version available. It loads only when you tap.'],
	['nav.hinweis.spaeter', 'Später', 'Later'],
	['nav.hinweis.aktualisieren', 'Aktualisieren', 'Update'],
	['nav.hinweis.ios', 'Auf den Startbildschirm legen: unten „Teilen“ antippen, dann „Zum Home-Bildschirm“.', 'Add to your home screen: tap “Share” at the bottom, then “Add to Home Screen”.'],
	['nav.hinweis.schliessen', 'Schließen', 'Close'],
	['nav.hinweis.passkey', 'Nächstes Mal ohne Passwort anmelden: Passkey auf diesem Gerät einrichten.', 'Sign in without a password next time: set up a passkey on this device.'],
	['nav.hinweis.nicht_jetzt', 'Nicht jetzt', 'Not now'],
	['nav.hinweis.einrichten', 'Jetzt einrichten', 'Set up now'],
	// ── LocationForm ──
	['listen.orte.form.name_platzhalter', 'Name der Location', 'Location name'],
	['listen.orte.form.dms', 'Google Maps Koordinaten (DMS)', 'Google Maps coordinates (DMS)'],
	['listen.orte.form.dms_platzhalter', 'z.B. 47°16\'11.1"N 11°50\'50.2"E', 'e.g. 47°16\'11.1"N 11°50\'50.2"E'],
	['listen.orte.form.lat', 'Breitengrad (Lat)', 'Latitude (lat)'],
	['listen.orte.form.lon', 'Längengrad (Lon)', 'Longitude (lon)'],
	['listen.orte.form.hoehe', 'Höhe (m)', 'Elevation (m)'],
	['listen.orte.form.region', 'Region (optional)', 'Region (optional)'],
	['listen.orte.form.region_platzhalter', 'z.B. AT-07-23-02', 'e.g. AT-07-23-02'],
	['listen.orte.form.bergfex', 'Bergfex Slug (optional)', 'Bergfex slug (optional)'],
	['listen.orte.form.bergfex_platzhalter', 'z.B. hochfuegen', 'e.g. hochfuegen'],
	['listen.orte.form.profil', 'Aktivitätsprofil', 'Activity profile'],
	['listen.orte.form.gruppe', 'Gruppe (optional)', 'Group (optional)'],
	['listen.orte.form.keine_gruppe', 'Keine Gruppe', 'No group'],
	['listen.orte.form.name_fehlt', 'Name ist erforderlich', 'Name is required'],
	['listen.orte.form.koordinaten_null', 'Koordinaten dürfen nicht beide 0 sein', 'Coordinates must not both be 0'],
	// ── WeatherConfigDialog ──
	['listen.orte.metriken.frage', 'Welche Metriken sollen im Report angezeigt werden?', 'Which metrics should the report show?'],
	['listen.orte.metriken.template', 'Template laden', 'Load template'],
	['listen.orte.metriken.kein_template', '-- Kein Template --', '-- No template --'],
	['listen.orte.metriken.fehler_laden', 'Fehler beim Laden der Metriken', 'Failed to load metrics'],
	['listen.orte.metriken.speichert', 'Speichern…', 'Saving…']
];
