<script lang="ts">
	// Issue #189 — Email-Vorschau im iframe.
	// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
	import { buildPreviewUrl, friendlyPreviewError, PREVIEW_ERROR_GENERIC, type ReportType } from './previewHelpers';

	interface Props { tripId: string; type: ReportType; date?: string; }
	let { tripId, type, date }: Props = $props();

	let html = $state<string>('');
	let loading = $state<boolean>(true);
	let error = $state<string | null>(null);

	$effect(() => {
		const controller = new AbortController();
		const url = buildPreviewUrl('email', tripId, type, date);
		loading = true; error = null; html = '';
		fetch(url, { credentials: 'same-origin', signal: controller.signal }).then(async (res) => {
			if (!res.ok) {
				error = friendlyPreviewError(res.status, await res.text());
				loading = false; return;
			}
			html = await res.text();
			loading = false;
		}).catch((err: unknown) => {
			if (err instanceof Error && err.name === 'AbortError') return;
			error = PREVIEW_ERROR_GENERIC;
			loading = false;
		});
		return () => controller.abort();
	});
</script>

<div class="email-frame" data-testid="email-iframe-wrapper">
	{#if loading}
		<p class="state-msg">Vorschau wird geladen…</p>
	{:else if error}
		<p class="state-msg error" data-testid="email-iframe-error">{error}</p>
	{:else}
		<iframe srcdoc={html} sandbox="allow-same-origin" title="Email-Vorschau" data-testid="email-iframe"></iframe>
	{/if}
</div>

<style>
	.email-frame {
		background: var(--g-paper, #f6f4ee);
		border-radius: var(--g-r-3, var(--g-radius-lg, 0.75rem));
		box-shadow: var(--g-shadow-1, var(--g-elev-1, 0 1px 3px rgba(26, 26, 24, 0.08)));
		padding: 0.5rem;
	}
	iframe { min-height: 600px; width: 100%; border: 0; display: block; }
	.state-msg { padding: 1rem; color: var(--g-ink, #1a1a18); font-size: 0.875rem; }
	.state-msg.error { color: #b03a2e; }
</style>
