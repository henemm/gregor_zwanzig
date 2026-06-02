<script lang="ts">
	// Issue #373 — MSwitch (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Toggle mit Label; Gesamt-Hit-Area >= 44px (Zeile mit min-height 44px).
	// a11y: role="switch", aria-checked, Tastatur (Space/Enter). Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-2)

	interface Props {
		checked?: boolean;
		label?: string;
		onchange?: (checked: boolean) => void;
	}

	let { checked = $bindable(false), label, onchange }: Props = $props();

	function toggle() {
		checked = !checked;
		onchange?.(checked);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === ' ' || e.key === 'Enter') {
			e.preventDefault();
			toggle();
		}
	}
</script>

<div
	role="switch"
	tabindex="0"
	aria-checked={checked}
	data-testid="m-switch"
	onclick={toggle}
	onkeydown={onKeydown}
	style:display="flex"
	style:align-items="center"
	style:gap="12px"
	style:cursor="pointer"
	style:min-height="44px"
	style:padding="10px 0"
>
	{#if label}
		<span style:flex="1" style:font-size="15px" style:color="var(--g-ink)">{label}</span>
	{/if}
	<span
		style:width="44px"
		style:height="26px"
		style:border-radius="13px"
		style:background={checked ? 'var(--g-success)' : 'var(--g-rule)'}
		style:position="relative"
		style:flex-shrink="0"
		style:transition="background 120ms"
	>
		<span
			style:position="absolute"
			style:top="3px"
			style:left={checked ? '21px' : '3px'}
			style:width="20px"
			style:height="20px"
			style:background="#fff"
			style:border-radius="50%"
			style:box-shadow="0 1px 2px rgba(0,0,0,0.2)"
			style:transition="left 120ms"
		></span>
	</span>
</div>
