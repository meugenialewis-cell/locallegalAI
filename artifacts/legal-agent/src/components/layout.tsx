import React from 'react';
import { Link, useLocation } from 'wouter';
import { Scale, Briefcase, CheckCircle, BookOpen, Settings, Sparkles, Home } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useHealthCheck } from '@workspace/api-client-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: Scale },
  { href: '/matters', label: 'Matters', icon: Briefcase },
  { href: '/identity', label: 'Identity', icon: Sparkles },
  { href: '/approvals', label: 'Approvals', icon: CheckCircle },
  { href: '/audit', label: 'Audit Ledger', icon: BookOpen },
  { href: '/take-quinn-home', label: 'Take Quinn Home', icon: Home },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const { data: health } = useHealthCheck();

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-sidebar flex flex-col justify-between shrink-0">
        <div>
          <div className="flex items-center h-16 px-6 border-b border-sidebar-border">
            <Scale className="h-6 w-6 text-sidebar-primary mr-2" />
            <span className="font-serif font-semibold text-lg tracking-tight text-sidebar-primary">
              Local Legal AI
            </span>
          </div>
          <nav className="p-4 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location === item.href || (item.href !== '/' && location.startsWith(item.href));
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                    isActive 
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
                      : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                  )}
                  data-testid={`nav-${item.label.toLowerCase()}`}
                >
                  <Icon className="h-4 w-4 mr-3 shrink-0" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        
        <div className="p-4 border-t border-sidebar-border text-xs">
          <div className="flex items-center justify-between px-3 py-2 bg-sidebar-accent/30 rounded-md">
            <span className="text-sidebar-foreground/80">System Status</span>
            <div className="flex items-center gap-1.5">
              <span className={cn(
                "h-2 w-2 rounded-full",
                health?.status === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'
              )} />
              <span className="font-medium text-sidebar-foreground capitalize">
                {health?.status || 'Unknown'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
