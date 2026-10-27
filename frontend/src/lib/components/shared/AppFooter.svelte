<script lang="ts">
	// Issue #2268 (S1 von #2146, Epic #2138) — app-weites Chrome mit den zwei
	// Rechtstext-Links. Die Ziele liegen auf henemm.com, Gregor betreibt keine
	// eigene Rechtstext-Route. Wortlaut und URLs sind PO-Vorgabe: Aenderung nur
	// mit neuer Freigabe. Eine Quelle der Wahrheit fuer beide Ziele:
	const IMPRESSUM_URL = 'https://www.henemm.com/footer-information/imprint/';
	const DATENSCHUTZ_URL = 'https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/';

	// target=_blank + rel: die App laeuft als PWA (Standalone) — ein Wechsel im
	// selben Tab nahme dem Nutzer den Rueckweg in die App.
	// min-height 44px ist die Mindest-Tippflaeche; `inline-flex` ist dafuer
	// notwendig, weil ein reines Inline-Element `min-height` ignoriert. Die Farbe
	// erbt der Link vom <footer>, damit kein Browser-Blau die Lesbarkeit
	// unterlaeuft.
	const LINK_STIL =
		'display: inline-flex; align-items: center; min-height: 44px; padding: 0 4px; color: inherit; text-decoration: underline;';
</script>

<!-- --g-ink-3 (#6b675c): 5.13:1 auf --g-paper, 5.65:1 auf Weiss, also WCAG-AA —
     NICHT --g-ink-4 (2.85:1, nur Placeholder/Disabled). Kein fixed/sticky, keine
     erzwungene Hoehe, kein eigener Hintergrund: der Footer scrollt mit, erbt
     Papier bzw. Weiss und legt kein neues festes Element an den unteren Rand
     (Vorrangregel #2316 AC-7). -->
<footer style="color: var(--g-ink-3); font-size: 14px; padding: 24px 0 8px;">
	<nav
		aria-label="Rechtliches"
		style="display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 24px;"
	>
		<a href={IMPRESSUM_URL} target="_blank" rel="noopener noreferrer" style={LINK_STIL}>Impressum</a>
		<a href={DATENSCHUTZ_URL} target="_blank" rel="noopener noreferrer" style={LINK_STIL}>
			Datenschutz
		</a>
	</nav>
</footer>
