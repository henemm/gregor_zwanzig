<script lang="ts" module>
	export type SwitchSize = 'sm' | 'md' | 'lg';
	export type SwitchTone = 'good' | 'accent' | 'info' | 'warn' | 'bad';
</script>

<script lang="ts">
	// Issue #371 — Switch-Atom (kanonisch aus atoms.jsx, Svelte 5).
	//
	// Toggle mit drei Groessen; tone steuert die On-Farbe (Token-basiert).
	// Mobile sollte size="lg" verwenden (Touch-Target >= 44px).
	//
	// Spec: docs/specs/modules/issue_371_atoms.md (AC-2, AC-4)

	interface Props {
		checked?: boolean;
		size?: SwitchSize;
		tone?: SwitchTone;
		disabled?: boolean;
		onchange?: (checked: boolean) => void;
		'aria-label'?: string;
		class?: string;
	}

	let {
		checked = $bindable(false),
		size = 'md',
		tone = 'good',
		disabled = false,
		onchange,
		'aria-label': ariaLabel,
		class: className = ''
	}: Props = $props();

	const sizes = {
		sm: { w: 28, h: 16, knob: 12, pad: 2 },
		md: { w: 36, h: 20, knob: 16, pad: 2 },
		lg: { w: 44, h: 26, knob: 22, pad: 2 }
	} as const;

	const toneColors = {
		good: 'var(--g-success)',
		accent: 'var(--g-accent)', // audit:exempt — Switch-Track-Hintergrund (§1.4.11, kein Text)
		info: 'var(--g-info)',
		warn: 'var(--g-warning)',
		bad: 'var(--g-danger)'
	} as const;

	// Unbekannte size/tone -> Default-Fallback (md/good), kein Crash.
	const s = $derived(sizes[size] ?? sizes.md);
	const onBg = $derived(toneColors[tone] ?? toneColors.good);

	function toggle() {
		if (disabled) return;
		checked = !checked;
		onchange?.(checked);
	}

	function onKeydown(e: KeyboardEvent) {
		if (disabled) return;
		if (e.key === ' ' || e.key === 'Enter') {
			e.preventDefault();
			toggle();
		}
	}
</script>

<span
	role="switch"
	tabindex={disabled ? -1 : 0}
	aria-checked={checked}
	aria-disabled={disabled || undefined}
	aria-label={ariaLabel}
	data-testid="switch"
	data-size={size}
	data-tone={tone}
	class={className}
	onclick={toggle}
	onkeydown={onKeydown}
	style:display="inline-block"
	style:width="{s.w}px"
	style:height="{s.h}px"
	style:background={checked ? onBg : 'var(--g-rule)'}
	style:border-radius="{s.h / 2}px"
	style:position="relative"
	style:cursor={disabled ? 'not-allowed' : 'pointer'}
	style:opacity={disabled ? 0.5 : 1}
	style:transition="background 120ms"
	style:flex-shrink="0"
	style:vertical-align="middle"
>
	<span
		style:position="absolute"
		style:top="{s.pad}px"
		style:left="{checked ? s.w - s.knob - s.pad : s.pad}px"
		style:width="{s.knob}px"
		style:height="{s.knob}px"
		style:background="#fff"
		style:border-radius="50%"
		style:box-shadow="0 1px 2px rgba(0,0,0,0.18)"
		style:transition="left 120ms"
	></span>
</span>
