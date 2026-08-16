import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, IdCard, Lock, ShieldCheck, ArrowRight, Cpu, GitBranch, BookOpen, Eye, CheckCircle, AlertCircle } from 'lucide-react';
import { useAuthGate } from '../../contexts/AuthGateContext';

const AGENT_ICONS = [
    { icon: <Eye className="w-4 h-4" />, label: 'Watcher' },
    { icon: <Cpu className="w-4 h-4" />, label: 'RCA' },
    { icon: <GitBranch className="w-4 h-4" />, label: 'Impact' },
    { icon: <BookOpen className="w-4 h-4" />, label: 'Runbook' },
    { icon: <ShieldCheck className="w-4 h-4" />, label: 'Safety' },
    { icon: <CheckCircle className="w-4 h-4" />, label: 'Verifier' },
];

export function LoginPage() {
    const navigate = useNavigate();
    const { credentialLoginEnabled, loading: authGateLoading } = useAuthGate();
    const [portalId, setPortalId] = useState('');
    const [password, setPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setSubmitting(true);
        try {
            const res = await fetch('/api/v2/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: portalId, password }),
            });
            if (!res.ok) {
                setError(res.status === 401 ? 'Invalid Portal ID or password.' : 'Sign-in failed. Please try again.');
                return;
            }
            const data = await res.json();
            localStorage.setItem('nemoguard_token', data.access_token);
            navigate('/app');
        } catch {
            setError('Could not reach the server. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen w-full bg-app-bg flex">
            {/* Left panel — decorative reprise of the agent constellation, no live 3D here */}
            <div className="hidden lg:flex lg:w-[45%] relative overflow-hidden bg-gradient-to-br from-primary/10 via-app-bg to-agent-active/10 items-center justify-center p-12">
                <div
                    className="absolute inset-0 opacity-40"
                    style={{
                        backgroundImage:
                            'radial-gradient(ellipse 60% 50% at 30% 20%, rgba(99,102,241,0.25), transparent), radial-gradient(ellipse 50% 40% at 80% 80%, rgba(192,38,211,0.2), transparent)',
                    }}
                />
                <div className="relative z-10 max-w-sm">
                    <div className="flex items-center gap-2.5 mb-8">
                        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-primary via-indigo-500 to-agent-active shadow-lg shadow-primary/30">
                            <Sparkles className="w-5 h-5 text-white" strokeWidth={2.2} />
                        </div>
                        <div>
                            <div className="font-semibold text-text-primary text-[15px] tracking-tight">NemoGuard</div>
                            <div className="text-[11px] text-text-muted">Command Center</div>
                        </div>
                    </div>

                    <h2 className="text-2xl font-semibold text-text-primary leading-tight mb-3">
                        Agentic incident response, coordinated end to end.
                    </h2>
                    <p className="text-[13px] text-text-muted leading-relaxed mb-8">
                        Six coordinated agents investigate, plan, and recover — with a human always
                        at the risk boundary.
                    </p>

                    <div className="grid grid-cols-3 gap-3">
                        {AGENT_ICONS.map((a, i) => (
                            <motion.div
                                key={a.label}
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.08 }}
                                className="glass-panel rounded-xl p-3 flex flex-col items-center gap-1.5 ring-1 ring-white/[0.06]"
                            >
                                <span className="text-primary">{a.icon}</span>
                                <span className="text-[10px] font-medium text-text-secondary">{a.label}</span>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Right panel — the actual form */}
            <div className="flex-1 flex items-center justify-center p-6 sm:p-10">
                <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="w-full max-w-sm"
                >
                    <div className="lg:hidden flex items-center gap-2.5 mb-8 justify-center">
                        <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-primary via-indigo-500 to-agent-active shadow-lg shadow-primary/30">
                            <Sparkles className="w-4.5 h-4.5 text-white" strokeWidth={2.2} />
                        </div>
                        <div className="font-semibold text-text-primary text-[15px] tracking-tight">NemoGuard</div>
                    </div>

                    <h1 className="text-xl font-semibold text-text-primary mb-1.5">Sign in</h1>
                    <p className="text-[12.5px] text-text-muted mb-6">
                        {authGateLoading
                            ? 'Checking deployment configuration…'
                            : credentialLoginEnabled
                                ? 'Sign in with your NemoGuard operator account.'
                                : 'No operator accounts have been provisioned for this deployment yet. Run scripts/create_user.py to create one.'}
                    </p>

                    <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-6 ring-1 ring-white/[0.08] space-y-4">
                        <div>
                            <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-1.5 block">Portal ID</label>
                            <div className="relative">
                                <IdCard className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                                <input
                                    type="text"
                                    autoComplete="username"
                                    value={portalId}
                                    onChange={(e) => setPortalId(e.target.value)}
                                    placeholder="Enter your Portal ID"
                                    required
                                    disabled={!credentialLoginEnabled}
                                    className="w-full pl-9 pr-3 py-2.5 bg-white/[0.03] border border-white/[0.08] rounded-lg text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/40 transition-all disabled:opacity-50"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-1.5 block">Password</label>
                            <div className="relative">
                                <Lock className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                                <input
                                    type="password"
                                    autoComplete="current-password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    required
                                    disabled={!credentialLoginEnabled}
                                    className="w-full pl-9 pr-3 py-2.5 bg-white/[0.03] border border-white/[0.08] rounded-lg text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/40 transition-all disabled:opacity-50"
                                />
                            </div>
                        </div>

                        {error && (
                            <div className="px-3.5 py-2.5 rounded-lg bg-critical/10 ring-1 ring-critical/25 text-[11.5px] text-critical flex items-center gap-2">
                                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={submitting || !credentialLoginEnabled}
                            className="press-scale w-full flex items-center justify-center gap-2 text-[13.5px] px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white hover:brightness-110 transition font-semibold disabled:opacity-60 shadow-lg shadow-primary/20"
                        >
                            {submitting ? 'Signing in…' : 'Sign in'}
                            {!submitting && <ArrowRight className="w-3.5 h-3.5" />}
                        </button>

                        <div className="flex items-center gap-2 pt-1">
                            <button
                                type="button"
                                disabled
                                title="SSO integration available in enterprise deployments"
                                className="flex-1 text-[11.5px] font-medium py-2 rounded-lg ring-1 ring-white/[0.06] text-text-muted cursor-not-allowed"
                            >
                                SSO with Okta
                            </button>
                            <button
                                type="button"
                                disabled
                                title="SSO integration available in enterprise deployments"
                                className="flex-1 text-[11.5px] font-medium py-2 rounded-lg ring-1 ring-white/[0.06] text-text-muted cursor-not-allowed"
                            >
                                SSO with Google
                            </button>
                        </div>
                    </form>
                </motion.div>
            </div>
        </div>
    );
}
