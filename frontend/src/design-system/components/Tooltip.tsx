import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

/*
 * NemoGuard design-system Tooltip primitive.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 73):
 * The spec explicitly calls for tooltips on "collapsed rail icons" and
 * other icon-only/ambiguous controls. Checked GlobalNavRail.tsx's
 * collapsed state -- it only sets a native HTML `title` attribute, which
 * is the browser's own slow (~1s delay), unstyled, inconsistent-across-
 * browsers tooltip. This provides a themed, fast, consistent tooltip that
 * matches the rest of the app's floating-surface language (menu-panel
 * background, same shadow/border treatment).
 */
export function Tooltip({ label, children, side = 'right' }: { label: string; children: React.ReactNode; side?: 'right' | 'top' | 'bottom' }) {
    const [visible, setVisible] = useState(false);

    const positionClasses =
        side === 'right'
            ? 'left-full top-1/2 -translate-y-1/2 ml-2'
            : side === 'top'
                ? 'bottom-full left-1/2 -translate-x-1/2 mb-2'
                : 'top-full left-1/2 -translate-x-1/2 mt-2';

    return (
        <div
            className="relative inline-flex"
            onMouseEnter={() => setVisible(true)}
            onMouseLeave={() => setVisible(false)}
            onFocus={() => setVisible(true)}
            onBlur={() => setVisible(false)}
        >
            {children}
            <AnimatePresence>
                {visible && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.1 }}
                        role="tooltip"
                        className={`absolute z-[80] whitespace-nowrap px-2 py-1 rounded-md text-[11px] font-medium pointer-events-none menu-panel ${positionClasses}`}
                    >
                        {label}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
