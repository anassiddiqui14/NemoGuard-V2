import { motion } from 'framer-motion';
import { Logomark } from '../../pages/LandingPage/Brand';

export type BrandMarkState = 'idle' | 'active' | 'investigating' | 'completed' | 'warning';

/*
 * NemoGuard signature brand animation (spec Section 75).
 *
 * WHY THIS EXISTS: the app already has several ad-hoc pulse/breathing
 * animations tied to agent/Commander activity (AgentConstellation's
 * running-state ring pulse, CommanderPanel's "live" badge pulse and
 * thinking-bubble spinner), each hand-implemented separately with
 * slightly different timing/easing. The spec explicitly calls for ONE
 * signature brand animation concept built around the NemoGuard mark,
 * reusable across contexts (agent loader, empty states, execution
 * status) -- this is that primitive: the actual Logomark (not a
 * generic spinner) with 5 named states matching real, truthful
 * conditions (never a fabricated "working" state when nothing is
 * actually happening).
 *
 * Deliberately kept subtle per spec Section 74 ("Avoid... constant
 * neon glow... cyberpunk styling") -- a slow breathing ring, not a
 * flashy spin.
 */
export function BrandMark({ state = 'idle', size = 'md' }: { state?: BrandMarkState; size?: 'sm' | 'md' | 'lg' }) {
    const sizeClasses = { sm: 'w-7 h-7', md: 'w-9 h-9', lg: 'w-14 h-14' };
    const iconSizeClasses = { sm: 'w-3.5 h-3.5', md: 'w-4.5 h-4.5', lg: 'w-7 h-7' };

    const stateColors: Record<BrandMarkState, string> = {
        idle: 'text-text-muted bg-white/[0.03] ring-white/[0.08]',
        active: 'text-agent-active bg-agent-active/10 ring-agent-active/30',
        investigating: 'text-primary bg-primary/10 ring-primary/30',
        completed: 'text-healthy bg-healthy/10 ring-healthy/30',
        warning: 'text-warning bg-warning/10 ring-warning/30',
    };

    const isAnimated = state === 'active' || state === 'investigating';

    return (
        <div className={`relative inline-flex items-center justify-center rounded-xl ring-1 ${sizeClasses[size]} ${stateColors[state]}`}>
            {isAnimated && (
                <motion.div
                    className="absolute inset-0 rounded-xl ring-2"
                    style={{ borderColor: 'currentColor' }}
                    animate={{ opacity: [0.5, 0.1, 0.5], scale: [1, 1.08, 1] }}
                    transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                />
            )}
            <Logomark className={iconSizeClasses[size]} />
        </div>
    );
}
