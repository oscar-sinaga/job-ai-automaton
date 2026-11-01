// The 7 V1 screens (docs/01_PRD.md §7, master spec §25). Kept in one place so
// the layout nav and any breadcrumb/title logic can't drift out of sync.
export interface NavItem {
	href: string;
	label: string;
}

export const NAV_ITEMS: NavItem[] = [
	{ href: '/', label: 'Dashboard' },
	{ href: '/jobs', label: 'Job Inbox' },
	{ href: '/career-profile', label: 'Career Profile' },
	{ href: '/analytics', label: 'Analytics' },
	{ href: '/settings', label: 'Settings' }
];
