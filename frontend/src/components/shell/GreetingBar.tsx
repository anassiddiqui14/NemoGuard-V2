import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { useGreeting } from '../../hooks/useGreeting';
import { useCurrentUser } from '../../hooks/useCurrentUser';

const SESSION_KEY = 'nemoguard_greeting_collapsed';

interface Props {
    activeCount: number;
    approvalCount: number;
}

export function GreetingBar({ activeCount, approvalCount }: Props) {
    const greeting = useGreeting();
    const user = useCurrentUser();
    const [collapsed, setCollapsed] = useState(() => sessionStorage.getItem(SESSION_KEY) === 'true');

    useEffect(() => {
        sessionStorage.setItem(SESSION_KEY, String(collapsed));
    }, [collapsed]);

    const statusLine =
        activeCount === 0
            ? 'All clear — no active incidents right now.'
            : approvalCount > 0
                ? `${activeCount} active incident${activeCount !== 1 ? 's' : ''}, ${approvalCount} awaiting your approval.`
                : `${activeCount} active incident${activeCount !== 1 ? 's' : ''}.`;

    return (
        <div className="px-5 pt-4">
            <button
                onClick={() => setCollapsed((v) => !v)}
                className="w-full flex items-center justify-between text-left group"
            >
                <div>
                    <h2 className="text-[15px] font-semibold text-text-primary tracking-tight">
                        {greeting}, <span className="text-gradient">{user.displayName}</span>
                    </h2>
                    <AnimatePresence>
                        {!collapsed && (
                            <motion.p
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="text-[12px] text-text-muted mt-0.5 overflow-hidden"
                            >
                                {statusLine}
                            </motion.p>
                        )}
                    </AnimatePresence>
                </div>
                <span className="text-text-muted group-hover:text-text-secondary transition-colors flex-shrink-0">
                    {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                </span>
            </button>
        </div>
    );
}
