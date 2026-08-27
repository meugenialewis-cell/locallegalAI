import { type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import Dashboard from '@/pages/dashboard';
import MattersList from '@/pages/matters-list';
import MatterWorkspace from '@/pages/matter-workspace';
import ApprovalsList from '@/pages/approvals-list';
import AuditLedger from '@/pages/audit-ledger';
import IdentityPage from '@/pages/identity';
import TakeQuinnHome from '@/pages/take-quinn-home';
import Settings from '@/pages/settings';

import {
  Route,
  Switch,
  useLocation,
  Router as WouterRouter,
} from 'wouter';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function Router() {
  return (
    <RoutedErrorBoundary>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/matters" component={MattersList} />
        <Route path="/matters/:matterId" component={MatterWorkspace} />
        <Route path="/identity" component={IdentityPage} />
        <Route path="/take-quinn-home" component={TakeQuinnHome} />
        <Route path="/approvals" component={ApprovalsList} />
        <Route path="/audit" component={AuditLedger} />
        <Route path="/settings" component={Settings} />
        <Route component={NotFound} />
      </Switch>
    </RoutedErrorBoundary>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
