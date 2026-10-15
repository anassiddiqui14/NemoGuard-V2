import { useNavigate } from 'react-router-dom';
import { LogOut, Settings, ShieldCheck } from 'lucide-react';
import { useCurrentUser } from '../../hooks/useCurrentUser';
import { Dropdown } from '../../design-system/components/Dropdown';

/*
 * UI MODERNIZATION (spec Section 20 -- consolidate duplicated UI
 * patterns): previously hand-rolled its own click-outside handling,
 * AnimatePresence, and positioning markup, duplicating logic already
 * centralized in the Dropdown primitive (originally built for exactly
 * this "button opens floating menu" shape but never actually wired up
 * anywhere). Refactored to use it directly -- same visual result,
 * one less place for click-outside/animation bugs to independently
 * drift.
 */
export function UserMenu() {
    const user = useCurrentUser();
    const navigate = useNavigate();

    const handleSignOut = () => {
        localStorage.removeItem('nemoguard_token');
        navigate('/login');
    };

    const primaryRole = user.roles[0] || 'viewer';

    return (
        <Dropdown
            width="w-72"
            trigger={
                <button className="w-8 h-8 rounded-full bg-gradient-to-br from-agent-active to-primary flex items-center justify-center text-[11px] font-semibold text-white cursor-pointer shadow-md press-scale">
                    {user.initials}
                </button>
            }
            header={
                <div className="px-4 py-3.5 border-b border-white/[0.06]">
                    <div className="text-[13px] font-semibold text-text-primary truncate">{user.displayName}</div>
                    <div className="text-[11.5px] text-text-muted truncate">{user.email}</div>
                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                        <span className="text-[9.5px] font-bold px-2 py-0.5 rounded-full bg-primary/15 text-primary uppercase tracking-wide">
                            {primaryRole}
                        </span>
                        <span className="text-[10px] font-mono text-text-muted">{user.tenantId}</span>
                    </div>
                    <div className="mt-2.5 flex items-center gap-2 text-[12px] text-text-secondary">
                        <ShieldCheck className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                        Authenticated session
                    </div>
                </div>
            }
            items={[
                { label: 'Settings', icon: <Settings className="w-3.5 h-3.5" />, onClick: () => navigate('/app/settings') },
                { label: 'Sign out', icon: <LogOut className="w-3.5 h-3.5" />, onClick: handleSignOut, destructive: true },
            ]}
        />
    );
}
