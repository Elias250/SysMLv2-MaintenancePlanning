// Document files compile to Svelte components. The editor's shadow project
// supplies these declarations even when a workspace has no types/ directory.
declare module '*.md' {
	import type {Component} from 'svelte';
	const component: Component<Record<string, unknown>>;
	export default component;
	export const metadata: Record<string, unknown>;
}
declare module '*.rst' {
	import type {Component} from 'svelte';
	const component: Component<Record<string, unknown>>;
	export default component;
	export const metadata: Record<string, unknown>;
}
declare module '*.svx' {
	import type {Component} from 'svelte';
	const component: Component<Record<string, unknown>>;
	export default component;
	export const metadata: Record<string, unknown>;
}
