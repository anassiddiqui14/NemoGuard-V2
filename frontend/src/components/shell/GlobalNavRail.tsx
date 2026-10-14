import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useNavItems } from '../../hooks/useNavItems';

interface Props {
    collapsed: boolean;
}

/**
 * A persistent, collapsible sidebar rail -- always visible on desktop
 * rather than a hidden overlay drawer that required an extra click to open
 * before every navigation. Collapsing (via the toggle button in TopBar)
 * shrinks it down to an icon-only rail instead of hiding it completely, so
 * the current section is always visible at a glance and switching sections
 * never costs more than a single click.
 *
 * Icons are the bespoke NemoGuard glyph set (NemoIcons.tsx) that shares the
 * perimeter-watch frame from the primary brand mark, rather than generic
 * icon-library glyphs.
 */
export function GlobalNavRail({ collapsed }: Props) {
    const items = useNavItems();

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
                                <span className="flex-shrink-0">{item.icon}</span>
                                {!collapsed && <span className="text-[13px] font-medium whitespace-nowrap">{item.label}</span>}
                            </>
                        )}
                    </NavLink>
                ))}
            </nav>
        </motion.aside>
    );
}
