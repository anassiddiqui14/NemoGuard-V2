import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Wrench, TrendingUp } from 'lucide-react';
import { CHANGELOG, LATEST_CHANGELOG_VERSION } from '../../data/changelog';

const TAG_STYLES: Record<string, { icon: React.ReactNode; cls: string }> = {
    feature: { icon: <Sparkles className="w-3.5 h-3.5" />, cls: 'bg-primary/15 text-primary ring-primary/30' },
    fix: { icon: <Wrench className="w-3.5 h-3.5" />, cls: 'bg-healthy/15 text-healthy ring-healthy/30' },
    improvement: { icon: <TrendingUp className="w-3.5 h-3.5" />, cls: 'bg-agent-active/15 text-agent-active ring-agent-active/30' },
};

export function WhatsNewPage() {
    useEffect(() => {
        localStorage.setItem('nemoguard_last_seen_changelog', LATEST_CHANGELOG_VERSION);
    }, []);

    return (
        <div className="h-full overflow-y-auto p-6 max-w-2xl mx-auto">
            <div className="mb-6">
                <h1 className="text-xl font-semibold text-text-primary tracking-tight">What's New</h1>
                <p className="text-[13px] text-text-muted mt-1">Recent product updates and improvements.</p>
            </div>

            <div className="space-y-3">
                {CHANGELOG.map((entry, idx) => {
                    const style = TAG_STYLES[entry.tag];
                    return (
                        <motion.div
                            key={`${entry.version}-${idx}`}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.04 }}
                            className="glass-panel rounded-xl p-4 ring-1 ring-white/[0.06] flex items-start gap-3"
                        >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${style.cls}`}>
                                {style.icon}
                            </div>
                            <div className="min-w-0">
                                <div className="text-[13px] text-text-primary leading-relaxed">{entry.title}</div>
                                <div className="text-[11px] text-text-muted mt-1 flex items-center gap-2">
                                    <span className="font-mono">v{entry.version}</span>
                                    <span>·</span>
                                    <span>{entry.date}</span>
                                </div>
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </div>
    );
}
