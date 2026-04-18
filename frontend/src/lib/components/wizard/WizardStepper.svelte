<script lang="ts">
	import CheckIcon from '@lucide/svelte/icons/check';

	interface Props {
		steps: string[];
		current: number;
	}
	let { steps, current }: Props = $props();
</script>

<div data-testid="wizard-stepper" class="flex items-center justify-between mb-8">
	{#each steps as label, i}
		{@const stepNum = i + 1}
		{@const isActive = i === current}
		{@const isCompleted = i < current}
		<div
			data-testid="wizard-step-{stepNum}"
			data-active={isActive ? 'true' : 'false'}
			class="flex flex-col items-center gap-1.5 flex-1"
		>
			<div class="flex items-center w-full">
				{#if i > 0}
					<div class="flex-1 h-0.5 {isCompleted || isActive ? 'bg-primary' : 'bg-muted'}"></div>
				{/if}
				<div
					class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0
						{isActive ? 'bg-primary text-primary-foreground' : ''}
						{isCompleted ? 'bg-primary text-primary-foreground' : ''}
						{!isActive && !isCompleted ? 'border-2 border-muted-foreground/30 text-muted-foreground' : ''}"
				>
					{#if isCompleted}
						<CheckIcon class="size-4" />
					{:else}
						{stepNum}
					{/if}
				</div>
				{#if i < steps.length - 1}
					<div class="flex-1 h-0.5 {isCompleted ? 'bg-primary' : 'bg-muted'}"></div>
				{/if}
			</div>
			<span class="text-xs {isActive ? 'font-semibold text-foreground' : 'text-muted-foreground'}">{label}</span>
		</div>
	{/each}
</div>
