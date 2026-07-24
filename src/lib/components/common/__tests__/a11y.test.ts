/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach } from 'vitest';
import axe from 'axe-core';

async function expectNoViolations(
	html: string,
	rules?: axe.RuleObject
): Promise<axe.AxeResults> {
	const container = document.createElement('div');
	container.innerHTML = html;
	document.body.appendChild(container);

	const options: axe.RunOptions = rules ? { rules } : {};
	const results = await axe.run(container, options);

	expect(results.violations).toEqual([]);
	document.body.removeChild(container);
	return results;
}

beforeEach(() => {
	document.body.innerHTML = '';
});

// ---------------------------------------------------------------------------
// Images
// ---------------------------------------------------------------------------
describe('Image accessibility', () => {
	it('img elements must have alt text', async () => {
		const html = '<img src="photo.jpg" alt="A descriptive alt text" />';
		await expectNoViolations(html);
	});

	it('flags an img without alt attribute as a violation', async () => {
		const container = document.createElement('div');
		container.innerHTML = '<img src="photo.jpg" />';
		document.body.appendChild(container);

		const results = await axe.run(container);
		document.body.removeChild(container);

		const imageViolations = results.violations.filter((v) =>
			v.id.includes('image')
		);
		expect(imageViolations.length).toBeGreaterThan(0);
	});
});

// ---------------------------------------------------------------------------
// Buttons
// ---------------------------------------------------------------------------
describe('Button accessibility', () => {
	it('button with visible text has no violations', async () => {
		const html = '<button type="button">Submit</button>';
		await expectNoViolations(html);
	});

	it('icon-only button needs an accessible label (aria-label)', async () => {
		const html =
			'<button type="button" aria-label="Close"><svg aria-hidden="true"><use href="#icon-close" /></svg></button>';
		await expectNoViolations(html);
	});

	it('flags a button without accessible name', async () => {
		const container = document.createElement('div');
		container.innerHTML = '<button type="button"></button>';
		document.body.appendChild(container);

		const results = await axe.run(container);
		document.body.removeChild(container);

		const nameViolations = results.violations.filter(
			(v) => v.id === 'button-name'
		);
		expect(nameViolations.length).toBeGreaterThan(0);
	});
});

// ---------------------------------------------------------------------------
// Form inputs
// ---------------------------------------------------------------------------
describe('Form input accessibility', () => {
	it('input with associated label has no violations', async () => {
		const html = `
			<label for="email">Email address</label>
			<input id="email" type="email" />
		`;
		await expectNoViolations(html);
	});

	it('input wrapped in a label has no violations', async () => {
		const html = '<label>Search <input type="search" /></label>';
		await expectNoViolations(html);
	});

	it('flags an input without an associated label', async () => {
		const container = document.createElement('div');
		container.innerHTML = '<input type="text" />';
		document.body.appendChild(container);

		const results = await axe.run(container);
		document.body.removeChild(container);

		const labelViolations = results.violations.filter(
			(v) => v.id === 'label'
		);
		expect(labelViolations.length).toBeGreaterThan(0);
	});

	it('select with label has no violations', async () => {
		const html = `
			<label for="country">Country</label>
			<select id="country">
				<option value="">Choose...</option>
				<option value="kr">South Korea</option>
			</select>
		`;
		await expectNoViolations(html);
	});

	it('textarea with label has no violations', async () => {
		const html = `
			<label for="bio">Biography</label>
			<textarea id="bio" rows="3"></textarea>
		`;
		await expectNoViolations(html);
	});
});

// ---------------------------------------------------------------------------
// Links
// ---------------------------------------------------------------------------
describe('Link accessibility', () => {
	it('link with visible text has no violations', async () => {
		const html = '<a href="/dashboard">Dashboard</a>';
		await expectNoViolations(html);
	});

	it('icon-only link needs an accessible label', async () => {
		const html =
			'<a href="/home" aria-label="Home"><svg aria-hidden="true"><use href="#icon-home" /></svg></a>';
		await expectNoViolations(html);
	});
});

// ---------------------------------------------------------------------------
// ARIA landmark & heading structure
// ---------------------------------------------------------------------------
describe('Document structure', () => {
	it('page with landmark regions and headings has no violations', async () => {
		const html = `
			<header role="banner">
				<h1>BCGPT WebUI</h1>
				<nav aria-label="Main navigation">
					<a href="/chat">Chat</a>
					<a href="/settings">Settings</a>
				</nav>
			</header>
			<main>
				<h2>Dashboard</h2>
				<p>Welcome to the dashboard.</p>
			</main>
			<footer role="contentinfo">
				<p>&copy; 2026 BC Card</p>
			</footer>
		`;
		await expectNoViolations(html);
	});

	it('lists are structured correctly', async () => {
		const html = `
			<ul>
				<li>Item one</li>
				<li>Item two</li>
				<li>Item three</li>
			</ul>
		`;
		await expectNoViolations(html);
	});
});

// ---------------------------------------------------------------------------
// ARIA attributes
// ---------------------------------------------------------------------------
describe('ARIA attribute usage', () => {
	it('dialog with proper ARIA attributes has no violations', async () => {
		const html = `
			<div role="dialog" aria-labelledby="dialog-title" aria-modal="true">
				<h2 id="dialog-title">Confirm Action</h2>
				<p>Are you sure you want to proceed?</p>
				<button type="button">Confirm</button>
				<button type="button">Cancel</button>
			</div>
		`;
		await expectNoViolations(html);
	});

	it('aria-hidden on decorative SVG alongside an aria-label on the button', async () => {
		// Mirrors the pattern used in Checkbox.svelte
		const html = `
			<button type="button" aria-label="Toggle checkbox">
				<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24">
					<path stroke="currentColor" d="m5 12 4.7 4.5 9.3-9" />
				</svg>
			</button>
		`;
		await expectNoViolations(html);
	});

	it('tooltip trigger with aria-describedby has no violations', async () => {
		// Mirrors the pattern used in Tooltip.svelte
		const html = `
			<div>
				<button type="button" aria-describedby="tooltip-1">Hover me</button>
				<div id="tooltip-1" role="tooltip">Tooltip content</div>
			</div>
		`;
		await expectNoViolations(html);
	});
});

// ---------------------------------------------------------------------------
// Comprehensive page-level scan
// ---------------------------------------------------------------------------
describe('Full page scan', () => {
	it('renders a minimal accessible page without violations', async () => {
		const html = `
			<!DOCTYPE html>
			<html lang="en">
			<head><title>Test Page</title></head>
			<body>
				<header role="banner">
					<nav aria-label="Primary">
						<a href="/">Home</a>
						<a href="/about">About</a>
					</nav>
				</header>
				<main>
					<h1>Welcome</h1>
					<section aria-labelledby="features-heading">
						<h2 id="features-heading">Features</h2>
						<form>
							<label for="search-input">Search</label>
							<input id="search-input" type="search" />
							<button type="submit">Go</button>
						</form>
					</section>
				</main>
				<footer role="contentinfo">
					<p>&copy; 2026 BC Card</p>
				</footer>
			</body>
			</html>
		`;
		// Disable color-contrast: not supported in jsdom
		await expectNoViolations(html, {
			'color-contrast': { enabled: false }
		} as axe.RuleObject);
	});
});
