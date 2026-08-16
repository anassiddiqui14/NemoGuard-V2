import { Sun, Moon, ShieldCheck, ShieldOff, Bell } from 'lucide-react';
import { motion } from 'framer-motion';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuthGate } from '../../contexts/AuthGateContext';
import { useCurrentUser } from '../../hooks/useCurrentUser';

function SettingRow({ icon, title, subtitle, control }: { icon: React.ReactNode; title: string; subtitle: string; control: React.ReactNode }) {
    return (
        <div className="flex items-center justify-between gap-4 py-4 border-b border-white/[0.05] last:border-b-0">
            <div className="flex items-start gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-white/[0.03] ring-1 ring-white/[0.06] flex items-center justify-center flex-shrink-0 text-text-secondary">
                    {icon}
                </div>
                <div>
                    <div className="text-[13px] font-medium text-text-primary">{title}</div>
                    <div className="text-[11.5px] text-text-muted mt-0.5">{subtitle}</div>
                </div>
            </div>
            <div className="flex-shrink-0">{control}</div>
        </div>
    );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
    return (
        <button
            role="switch"
            aria-checked={checked}
            onClick={() => onChange(!checked)}
            className={`relative w-10 h-5.5 rounded-full transition-colors ${checked ? 'bg-primary' : 'bg-white/[0.12]'}`}
        >
            <motion.span
                layout
                className="absolute top-0.5 left-0.5 w-4.5 h-4.5 rounded-full bg-white shadow"
                animate={{ x: checked ? 18 : 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
        </button>
    );
}

export function SettingsPage() {
    const { theme, toggleTheme } = useTheme();
    const { devLoginEnabled, credentialLoginEnabled } = useAuthGate();
    const user = useCurrentUser();

    return (
        <div className="h-full overflow-y-auto p-6 max-w-xl mx-auto">
            <div className="mb-6">
                <h1 className="text-xl font-semibold text-text-primary tracking-tight">Settings</h1>
                <p className="text-[13px] text-text-muted mt-1">Preferences for your Command Center experience.</p>
            </div>

            <div className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06] mb-5">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-2">Account</div>
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-agent-active to-primary flex items-center justify-center text-[13px] font-semibold text-white">
                        {user.initials}
                    </div>
                    <div>
                        <div className="text-[13px] font-medium text-text-primary">{user.displayName}</div>
                        <div className="text-[11.5px] text-text-muted">{user.email}</div>
                    </div>
                </div>
            </div>

            <div className="glass-panel rounded-2xl px-5 ring-1 ring-white/[0.06]">
                <SettingRow
                    icon={theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                    title="Theme"
                    subtitle={`Currently using ${theme} mode`}
                    control={
                        <button
                            onClick={toggleTheme}
                            className="text-[12px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] ring-1 ring-white/[0.06] transition text-text-secondary"
                        >
                            Switch to {theme === 'dark' ? 'light' : 'dark'}
                        </button>
                    }
                />
                <SettingRow
                    icon={credentialLoginEnabled ? <ShieldCheck className="w-4 h-4" /> : <ShieldOff className="w-4 h-4" />}
                    title="Authentication mode"
                    subtitle={
                        credentialLoginEnabled
                            ? 'Real operator accounts are provisioned. Sign-in requires a valid email and password.'
                            : devLoginEnabled
                                ? 'Development mode — no operator accounts are provisioned yet. Run scripts/create_user.py before going to production.'
                                : 'No operator accounts are provisioned. Run scripts/create_user.py to enable sign-in.'
                    }
                    control={
                        <span
                            className={`text-[11px] font-semibold px-2.5 py-1 rounded-full ring-1 ${credentialLoginEnabled
                                ? 'bg-healthy/10 text-healthy ring-healthy/25'
                                : 'bg-warning/10 text-warning ring-warning/25'
                                }`}
                        >
                            {credentialLoginEnabled ? 'Production accounts' : devLoginEnabled ? 'Development' : 'Not configured'}
                        </span>
                    }
                />
                <SettingRow
                    icon={<Bell className="w-4 h-4" />}
                    title="SLA breach notifications"
                    subtitle="Notify when an incident is close to breaching its SLA."
                    control={<Toggle checked={true} onChange={() => { }} />}
                />
            </div>
        </div>
    );
}
