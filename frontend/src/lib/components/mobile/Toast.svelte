<script lang="ts" module>
	export type ToastKind = 'info' | 'success' | 'warn' | 'error';
</script>

<script lang="ts">
	// Issue #373 — Toast / Snackbar (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Fixierter Hinweis ueber der BottomNav. kind info|success|warn|error rendern
	// je distinct (Token-Farben). Optionaler hint + action-Button. SSR-fest
	// (keine window/document-Zugriffe). Unbekanntes kind -> info.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-4, AC-6)
	interface Props {
		kind?: ToastKind;
		msg: string;
		action?: string;
		hint?: string;
		onaction?: () => void;
	}

	let { kind = 'info', msg, action, hint, onaction }: Props = $props();

	const map = {
		info: { bg: 'var(--g-ink)', fg: 'var(--g-paper)' },
		success: { bg: 'var(--g-good)', fg: '#fff' },
		warn: { bg: 'var(--g-warn)', fg: '#fff' },
		error: { bg: 'var(--g-bad)', fg: '#fff' }
	} as const;

	const t = $derived(map[kind] ?? map.info);
</script>

<div
	role="status"
	data-kind={kind}
	style:position="absolute"
	style:left="16px"
	style:right="16px"
	style:bottom="76px"
	style:background={t.bg}
	style:color={t.fg}
	style:border-radius="var(--g-r-3)"
	style:padding="12px 16px"
	style:display="flex"
	style:align-items="center"
	style:gap="12px"
	style:box-shadow="var(--g-shadow-3)"
	style:z-index="30"
	style:font-size="14px"
	style:line-height="1.4"
>
	<div style:flex="1" style:min-width="0">
		{#if hint}
			<div
				class="mono"
				style:font-size="10px"
				style:letter-spacing="0.1em"
				style:text-transform="uppercase"
				style:opacity="0.7"
				style:margin-bottom="2px"
			>{hint}</div>
		{/if}
		<div>{msg}</div>
	</div>
	{#if action}
		<button
			type="button"
			onclick={onaction}
			style:background="transparent"
			style:border="none"
			style:color={t.fg}
			style:font-size="13px"
			style:font-weight="600"
			style:text-transform="uppercase"
			style:letter-spacing="0.06em"
			style:font-family="var(--g-font-mono)"
			style:cursor="pointer"
			style:min-height="44px"
			style:padding="0 4px"
		>{action}</button>
	{/if}
</div>
