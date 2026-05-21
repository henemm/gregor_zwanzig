<div class="empty">
	<h2 class="empty__title">Willkommen bei Gregor 20</h2>
	<p class="empty__sub">Leg deine erste Tour an oder starte einen Orts-Vergleich.</p>
	<div class="empty__actions">
		<a href="/trips/new" class="empty__btn empty__btn--primary">+ Neue Tour</a>
		<a href="/compare" class="empty__btn empty__btn--outline">+ Neuer Vergleich</a>
	</div>
</div>

<style>
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}
	.empty__title {
		font-size: var(--g-text-2xl);
		font-weight: 600;
		margin: 0;
	}
	.empty__sub {
		color: var(--g-ink-muted);
		max-width: 36ch;
		margin: 0;
	}
	.empty__actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		justify-content: center;
	}
	.empty__btn {
		padding: 0.5rem 1.25rem;
		border-radius: var(--g-radius-lg);
		font-size: 14px;
		font-weight: 500;
		text-decoration: none;
		transition: opacity 120ms;
	}
	.empty__btn:hover { opacity: 0.85; }
	.empty__btn--primary {
		background: var(--g-accent);
		color: #fff;
	}
	.empty__btn--outline {
		border: 1px solid var(--g-ink-faint);
		color: var(--g-ink);
	}
</style>
