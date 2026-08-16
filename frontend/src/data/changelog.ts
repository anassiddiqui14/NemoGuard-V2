export interface ChangelogEntry {
    version: string;
    date: string;
    title: string;
    tag: 'feature' | 'fix' | 'improvement';
}

export const CHANGELOG: ChangelogEntry[] = [
    {
        version: '1.4.0',
        date: '2026-08-10',
        title: 'Redesigned Command Center workspace with grouped, tabbed sections for a calmer, less cluttered view',
        tag: 'improvement',
    },
    {
        version: '1.4.0',
        date: '2026-08-10',
        title: 'New landing experience, optional Demo Mode, and personalized navigation',
        tag: 'feature',
    },
    {
        version: '1.3.0',
        date: '2026-08-10',
        title: 'Resolved incidents now show accurate time-to-resolve instead of a live-ticking clock',
        tag: 'fix',
    },
    {
        version: '1.3.0',
        date: '2026-08-10',
        title: 'Resolved incidents list is now reliably visible in the incident queue',
        tag: 'fix',
    },
    {
        version: '1.2.0',
        date: '2026-08-01',
        title: 'Live agent event streaming via Server-Sent Events',
        tag: 'feature',
    },
    {
        version: '1.1.0',
        date: '2026-07-20',
        title: 'Role-based access control for plan approval and execution',
        tag: 'feature',
    },
];

export const LATEST_CHANGELOG_VERSION = CHANGELOG[0]?.version ?? '0.0.0';
