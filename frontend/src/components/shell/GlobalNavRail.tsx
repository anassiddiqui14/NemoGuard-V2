import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LayoutGrid, ListChecks, Cpu, Sparkles, Settings, BrainCircuit } from 'lucide-react';
import { LATEST_CHANGELOG_VERSION } from '../../data/changelog';

interface NavItem {
    to: string;
    label: string;
    icon: React.ReactNode;
    end?: boolean;
    badge?: boolean;
}

interface Props {
    hasUnseenChangelog: boolean;
    collapsed: boolean;
}

/**
 * A persistent, collapsible sidebar rail -- always visible on desktop
 * rather than a hidden overlay drawer that required an extra click to open
 * before every navigation. Collapsing (via the toggle button in TopBar)
 * shrinks it down to an icon-only rail instead of hiding it completely, so
 * the current section is always visible at a glance and switching sections
 * never costs more than a single click.
 */
export function GlobalNavRail({ hasUnseenChangelog, collapsed }: Props) {
    const items: NavItem[] = [
        { to: '/app', label: 'Command Center', icon: <LayoutGrid className="w-4.5 h-4.5" />, end: true },
        { to: '/app/incidents', label: 'Incidents', icon: <ListChecks className="w-4.5 h-4.5" /> },
        { to: '/app/agent-operations', label: 'Agent Operations', icon: <Cpu className="w-4.5 h-4.5" /> },
        { to: '/app/intelligence', label: 'Intelligence', icon: <BrainCircuit className="w-4.5 h-4.5" /> },
        { to: '/app/whats-new', label: "What's New", icon: <Sparkles className="w-4.5 h-4.5" />, badge: hasUnseenChangelog },
        { to: '/app/settings', label: 'Settings', icon: <Settings className="w-4.5 h-4.5" /> },
    ];

    return (
        <motion.aside
            initial={false}
            animate={{ width: collapsed ? 68 : 230 }}
            transition={{ type: 'spring', stiffness: 300, damping: 32 }}
            className="hidden md:flex flex-col flex-shrink-0 h-full border-r border-white/[0.06] bg-black/20 overflow-hidden"
        >
            <nav className={`flex-1 py-3 space-y-1 overflow-y-auto ${collapsed ? 'px-2' : 'px-2.5'}`}>
                {items.map((item) => (
                    <NavLink
                        key={item.to}
                        to={item.to}
                        end={item.end}
                        title={collapsed ? item.label : undefined}
                        className={({ isActive }) =>
                            `relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${collapsed ? 'justify-center' : ''} ${isActive
                                ? 'bg-primary/[0.12] text-primary ring-1 ring-primary/25'
                                : 'text-text-secondary hover:bg-white/[0.04] hover:text-text-primary'
                            }`
                        }
                    >
                        {({ isActive }) => (
                            <>
                                {isActive && (
                                    <motion.div
                                        layoutId="nav-active-rail"
                                        className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-gradient-to-b from-primary to-agent-active"
                                    />
                                )}
                                <span className="flex-shrink-0 relative">
                                    {item.icon}
                                    {item.badge && (
                                        <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-critical ring-2 ring-surface" />
                                    )}
                                </span>
                                {!collapsed && <span className="text-[13px] font-medium whitespace-nowrap">{item.label}</span>}
                            </>
                        )}
                    </NavLink>
                ))}
            </nav>
        </motion.aside>
    );
}

export function useLatestChangelogVersion() {
    return LATEST_CHANGELOG_VERSION;
}
