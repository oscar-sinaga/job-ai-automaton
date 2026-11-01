// Plain esbuild, not Vite (deviates from docs/08 §8's original suggestion):
// the four entry points need different output formats -- background.js and
// the popup/options scripts are ES modules, but content.js is injected via
// chrome.scripting.executeScript({files:[...]}) and must run as a classic,
// self-contained script, so it needs IIFE format. esbuild's per-call `format`
// option handles that directly; Vite's dev-server-first, HTML-multi-page
// model fights this without an extra plugin.
import { build } from 'esbuild';
import { cpSync, mkdirSync, rmSync } from 'node:fs';

rmSync('dist', { recursive: true, force: true });
mkdirSync('dist', { recursive: true });

const target = ['chrome110'];

await build({
	entryPoints: ['src/background.ts'],
	outfile: 'dist/background.js',
	bundle: true,
	format: 'esm',
	target
});

await build({
	entryPoints: ['src/content.ts'],
	outfile: 'dist/content.js',
	bundle: true,
	format: 'iife',
	target
});

await build({
	entryPoints: ['src/popup.ts'],
	outfile: 'dist/popup.js',
	bundle: true,
	format: 'esm',
	target
});

await build({
	entryPoints: ['src/options.ts'],
	outfile: 'dist/options.js',
	bundle: true,
	format: 'esm',
	target
});

cpSync('manifest.json', 'dist/manifest.json');
cpSync('popup.html', 'dist/popup.html');
cpSync('options.html', 'dist/options.html');

console.log('Built extension to dist/ -- load it unpacked via chrome://extensions');
