<script lang="ts">
	// Issue #189 — Email-Vorschau im iframe.
	// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
	// Issue #2283: inhaltsgetrieben — das HTML kommt aus dem geteilten Lader
	// (shared/previewLoader.ts), der Baustein ruft selbst nichts mehr ab.
	// `view` waehlt die Ansicht Desktop/Mobil (data-email-view am Rahmen).

	interface Props { html: string; view?: 'desktop' | 'mobile'; }
	let { html, view = 'desktop' }: Props = $props();
</script>

<div class="email-frame email-frame-{view}" data-testid="email-iframe-wrapper" data-email-view={view}>
	<iframe srcdoc={html} sandbox="allow-same-origin" title="Email-Vorschau" data-testid="email-iframe"></iframe>
</div>

<style>
	.email-frame {
		background: var(--g-paper, #f6f4ee);
		border-radius: var(--g-r-3, var(--g-radius-lg, 0.75rem));
		box-shadow: var(--g-shadow-1, var(--g-elev-1, 0 1px 3px rgba(26, 26, 24, 0.08)));
		padding: 0.5rem;
	}
	.email-frame-desktop { max-width: 680px; }
	.email-frame-mobile { max-width: 390px; }
	iframe { min-height: 600px; width: 100%; border: 0; display: block; }
</style>
