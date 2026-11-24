<script lang="ts">
	// Issue #2520 — oeffentliche Startseite fuer Ausgeloggte. Alle Texte aus dem
	// Katalog ($lib/i18n), Bausteine aus atoms/ui.
	import { Card, Btn, Eyebrow, SectionH } from '$lib/components/atoms';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import SprachUmschalter from '$lib/components/ui/SprachUmschalter.svelte';
	// Issue #3319 (AC-2): Level-Kurzform, Zahlen aus level_grenzen.json.
	import LevelTabelle from '$lib/components/shared/LevelTabelle.svelte';
	import { t } from '$lib/i18n';

	const bilder = $derived([
		{ src: $t('start.mail.src'), alt: $t('start.mail.alt'), caption: $t('start.mail.caption') },
		{ src: $t('start.telegram.src'), alt: $t('start.telegram.alt'), caption: $t('start.telegram.caption') },
		{ src: $t('start.alarm.src'), alt: $t('start.alarm.alt'), caption: $t('start.alarm.caption') }
	]);
</script>

<svelte:head>
	<title>{$t('start.meta.title')}</title>
	<meta name="description" content={$t('start.meta.description')} />
</svelte:head>

<!-- Issue #3319 (AC-11): Logo-Zeile als Seitenkopf AUSSERHALB von <main>
     (Banner-Landmarke; die Markenschrift ist als Logo von der Kontrastpflicht
     ausgenommen, der Inhalt in <main> erfuellt WCAG-AA). -->
<div class="start" data-testid="startseite">
	<header class="kopf">
		<Wordmark size="md" />
		<SprachUmschalter />
	</header>

	<main class="inhalt">
		<section class="hero">
			<Eyebrow>{$t('start.hero.eyebrow')}</Eyebrow>
			<h1>{$t('start.hero.title')}</h1>
			<p class="lead">{$t('start.hero.lead')}</p>
			<div class="cta">
				<Btn variant="primary" size="lg" href="/register">{$t('start.cta.register')}</Btn>
				<Btn variant="outline" size="lg" href="/login">{$t('start.cta.login')}</Btn>
			</div>
		</section>

		<div class="raster">
			<Card>
				<SectionH eyebrow={$t('start.was.eyebrow')} title={$t('start.was.title')} />
				<p>{$t('start.was.text')}</p>
				<p>{$t('start.was.hyperlokal')}</p>
			</Card>

			<Card>
				<SectionH eyebrow={$t('start.ankommt.eyebrow')} title={$t('start.ankommt.title')} />
				<p>{$t('start.ankommt.briefing')}</p>
				<p>{$t('start.ankommt.alarm')}</p>
				<p>{$t('start.ankommt.kanaele')}</p>
			</Card>

			<Card>
				<SectionH eyebrow={$t('start.nutzen.eyebrow')} title={$t('start.nutzen.title')} />
				<p>{$t('start.nutzen.empfang')}</p>
				<p>{$t('start.nutzen.entscheidung')}</p>
			</Card>
		</div>

		<section class="level" data-testid="start-level">
			<Card>
				<SectionH eyebrow={$t('start.level.eyebrow')} title={$t('start.level.title')} />
				<p>{$t('start.level.text')}</p>
				<LevelTabelle umfang="kurz" />
				<p class="wechsel">{$t('start.level.wechsel')}</p>
				<div class="links">
					<a class="mehr" href="/funktionen/level">{$t('start.level.details')}</a>
					<a class="mehr" href="/funktionen">{$t('start.level.mehr')}</a>
				</div>
			</Card>
		</section>

		<section class="bilder">
			{#each bilder as b (b.src)}
				<Card padding={12}>
					<img src={b.src} alt={b.alt} loading="lazy" />
					<p class="caption">{b.caption}</p>
				</Card>
			{/each}
		</section>
		<p class="caption hinweis">{$t('start.footer.hinweis')}</p>
	</main>
</div>

<style>
	.start {
		max-width: 1040px;
		margin: 0 auto;
		padding: var(--g-s-5, 20px) 16px 48px;
		display: flex;
		flex-direction: column;
		gap: 24px;
		overflow-x: hidden;
	}
	.inhalt {
		display: flex;
		flex-direction: column;
		gap: 24px;
		min-width: 0;
	}
	.kopf {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	h1 {
		font-size: clamp(1.7rem, 6vw, 2.6rem);
		line-height: 1.15;
		margin: 8px 0;
		color: var(--g-ink);
	}
	.lead,
	.start :global(p) {
		color: var(--g-ink-2);
		line-height: 1.55;
		margin: 0 0 10px;
	}
	.cta {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
		margin-top: 16px;
	}
	.raster,
	.bilder {
		display: grid;
		grid-template-columns: 1fr;
		gap: 16px;
	}
	img {
		display: block;
		width: 100%;
		height: auto;
		border-radius: 6px;
	}
	.wechsel {
		margin-top: 12px;
	}
	.links {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 20px;
		margin-top: 4px;
	}
	.mehr {
		display: inline-block;
		font-weight: 600;
		color: var(--g-ink);
		text-decoration: underline;
		text-underline-offset: 3px;
	}
	.caption {
		font-size: 13px;
		color: var(--g-ink-2);
		margin: 8px 0 0;
	}
	@media (min-width: 768px) {
		.raster {
			grid-template-columns: repeat(2, 1fr);
		}
		.bilder {
			grid-template-columns: repeat(3, 1fr);
		}
	}
</style>
