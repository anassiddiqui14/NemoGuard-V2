import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { LogOut, Settings, ShieldCheck } from 'lucide-react';
import { useCurrentUser } from '../../hooks/useCurrentUser';

export function UserMenu() {
    const user = useCurrentUser();
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        const onClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, []);

    const handleSignOut = () => {
        localStorage.removeItem('nemoguard_token');
        setOpen(false);
        navigate('/login');
    };

    const primaryRole = user.roles[0] || 'viewer';

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen((o) => !o)}
                className="w-8 h-8 rounded-full bg-gradient-to-br from-agent-active to-primary flex items-center justify-center text-[11px] font-semibold text-white cursor-pointer shadow-md press-scale"
            >
                {user.initials}
            </button>

            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ opacity: 0, y: -8, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -8, scale: 0.97 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-full mt-2 w-72 glass-panel rounded-xl shadow-2xl overflow-hidden z-50 ring-1 ring-white/[0.08]"
                    >
                        <div className="px-4 py-3.5 border-b border-white/[0.06]">
                            <div className="text-[13px] font-semibold text-text-primary truncate">{user.displayName}</div>
                            <div className="text-[11.5px] text-text-muted truncate">{user.email}</div>
                            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                                <span className="text-[9.5px] font-bold px-2 py-0.5 rounded-full bg-primary/15 text-primary uppercase tracking-wide">
                                    {primaryRole}
                                </span>
                                <span className="text-[10px] font-mono text-text-muted">{user.tenantId}</span>
                            </div>
                        </div>
                        <div className="py-1.5">
                            <button
                                onClick={() => {
                                    setOpen(false);
                                    navigate('/app/settings');
                                }}
                                className="w-full text-left px-4 py-2.5 hover:bg-white/[0.04] transition-colors flex items-center gap-2.5 text-[12.5px] text-text-secondary"
                            >
                                <Settings className="w-3.5 h-3.5" /> Settings
                            </button>
                            <div className="w-full text-left px-4 py-2.5 flex items-center gap-2.5 text-[12.5px] text-text-secondary">
                                <ShieldCheck className="w-3.5 h-3.5 text-text-muted" />
                                Authenticated session
                            </div>
                        </div>
                        <div className="border-t border-white/[0.06] py-1.5">
                            <button
                                onClick={handleSignOut}
                                className="w-full text-left px-4 py-2.5 hover:bg-critical/10 transition-colors flex items-center gap-2.5 text-[12.5px] text-critical"
                            >
                                <LogOut className="w-3.5 h-3.5" /> Sign out
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
