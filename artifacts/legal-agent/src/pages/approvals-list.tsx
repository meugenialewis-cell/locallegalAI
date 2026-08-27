import React from 'react';
import {
  useListToolProposals,
  useReviewToolProposal,
  getListToolProposalsQueryKey,
  useListIdentityProposals,
  useReviewIdentityProposal,
  getListIdentityProposalsQueryKey,
  getGetIdentityOverviewQueryKey,
} from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Check, X, AlertTriangle, ShieldAlert, Sparkles } from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';

export default function ApprovalsList() {
  const { data: proposals, isLoading } = useListToolProposals();
  const { data: identityProposals } = useListIdentityProposals();

  const pendingProposals = proposals?.filter(p => p.status === 'pending') || [];
  const pastProposals = proposals?.filter(p => p.status !== 'pending') || [];
  const pendingIdentity = identityProposals?.filter(p => p.status === 'pending') || [];
  const pastIdentity = identityProposals?.filter(p => p.status !== 'pending') || [];

  return (
    <Layout>
      <div className="p-8 max-w-5xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-serif font-bold">Tool Approvals</h1>
          <p className="text-muted-foreground mt-1">Review AI model requests to execute tools or access external data.</p>
        </div>

        <section>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            Action Required 
            {pendingProposals.length > 0 && <Badge variant="destructive">{pendingProposals.length}</Badge>}
          </h2>
          {isLoading ? (
            <div className="space-y-4">
              <div className="h-32 bg-muted animate-pulse rounded-md" />
            </div>
          ) : pendingProposals.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Check className="h-12 w-12 text-emerald-500/50 mb-4" />
                <p>No pending tool proposals. You're all caught up.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {pendingProposals.map(proposal => (
                <ApprovalCard key={proposal.id} proposal={proposal} />
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Identity Changes
            {pendingIdentity.length > 0 && <Badge variant="destructive">{pendingIdentity.length}</Badge>}
          </h2>
          {pendingIdentity.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                No identity changes awaiting review. Professional identity changes always
                appear here; personal ones do too unless the autonomy dial is set to
                notify-and-apply.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {pendingIdentity.map(proposal => (
                <IdentityProposalCard key={proposal.id} proposal={proposal} />
              ))}
            </div>
          )}
          {pastIdentity.length > 0 && (
            <div className="space-y-4 opacity-80 mt-4">
              {pastIdentity.map(proposal => (
                <IdentityProposalCard key={proposal.id} proposal={proposal} isPast />
              ))}
            </div>
          )}
        </section>

        {pastProposals.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-4 text-muted-foreground">Past Reviews</h2>
            <div className="space-y-4 opacity-80">
              {pastProposals.map(proposal => (
                <ApprovalCard key={proposal.id} proposal={proposal} isPast />
              ))}
            </div>
          </section>
        )}
      </div>
    </Layout>
  );
}

function IdentityProposalCard({ proposal, isPast = false }: { proposal: any, isPast?: boolean }) {
  const queryClient = useQueryClient();
  const reviewIdentity = useReviewIdentityProposal();
  const { toast } = useToast();

  const handleReview = (decision: 'approved' | 'denied') => {
    reviewIdentity.mutate({ proposalId: proposal.id, data: { decision } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListIdentityProposalsQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetIdentityOverviewQueryKey() });
        toast({ title: `Identity change ${decision}`, description: 'Your decision has been recorded on the ledger.' });
      }
    });
  };

  return (
    <Card className={isPast ? 'bg-muted/30 border-muted' : 'border-primary/20 shadow-sm'} data-testid={`card-identity-proposal-${proposal.id}`}>
      <CardHeader className="pb-3 border-b bg-card">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <CardTitle className="text-base capitalize">{proposal.identityKind} identity change</CardTitle>
              <Badge variant="secondary" className="uppercase text-[10px] tracking-wider font-bold">
                Proposed by {proposal.author}
              </Badge>
              {isPast && (
                <Badge variant="outline" className="uppercase text-[10px] tracking-wider font-bold">
                  {proposal.status.replace('_', ' ')}
                </Badge>
              )}
            </div>
            <CardDescription>Behavioral layer only — hard safety limits are unaffected.</CardDescription>
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {formatDate(proposal.requestedAt)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div>
          <p className="text-sm font-medium mb-1">Rationale</p>
          <p className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-md border">
            {proposal.rationale}
          </p>
        </div>
        <details className="text-sm">
          <summary className="cursor-pointer font-medium">Proposed text</summary>
          <p className="mt-2 whitespace-pre-wrap font-serif text-muted-foreground bg-muted/30 border rounded-md p-3 max-h-64 overflow-y-auto">
            {proposal.proposedContent}
          </p>
        </details>
      </CardContent>
      {!isPast && (
        <CardFooter className="border-t bg-muted/20 pt-4 flex justify-end gap-2">
          <Button variant="outline" className="text-destructive border-destructive/30 hover:bg-destructive/10"
            onClick={() => handleReview('denied')}
            disabled={reviewIdentity.isPending}
            data-testid="button-deny-identity"
          >
            <X className="h-4 w-4 mr-2" /> Deny
          </Button>
          <Button variant="default" className="bg-primary hover:bg-primary/90"
            onClick={() => handleReview('approved')}
            disabled={reviewIdentity.isPending}
            data-testid="button-approve-identity"
          >
            <Check className="h-4 w-4 mr-2" /> Approve Change
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}

function ApprovalCard({ proposal, isPast = false }: { proposal: any, isPast?: boolean }) {
  const queryClient = useQueryClient();
  const reviewTool = useReviewToolProposal();
  const { toast } = useToast();

  const handleReview = (decision: 'approved' | 'denied') => {
    reviewTool.mutate({ proposalId: proposal.id, data: { decision } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListToolProposalsQueryKey() });
        toast({ title: `Proposal ${decision}`, description: 'Your decision has been recorded on the ledger.' });
      }
    });
  };

  const riskColor = proposal.riskLevel === 'high' ? 'destructive' : proposal.riskLevel === 'medium' ? 'warning' : 'secondary';

  return (
    <Card className={isPast ? 'bg-muted/30 border-muted' : 'border-primary/20 shadow-sm'}>
      <CardHeader className="pb-3 border-b bg-card">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <CardTitle className="text-base">{proposal.toolName}</CardTitle>
              <Badge variant={riskColor} className="uppercase text-[10px] tracking-wider font-bold">
                {proposal.riskLevel} Risk
              </Badge>
              {isPast && (
                <Badge variant="outline" className="uppercase text-[10px] tracking-wider font-bold">
                  {proposal.status}
                </Badge>
              )}
            </div>
            <CardDescription>
              Matter: <span className="font-medium text-foreground">{proposal.matterName}</span>
            </CardDescription>
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {formatDate(proposal.requestedAt)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div>
          <p className="text-sm font-medium mb-1">Summary of Intent</p>
          <p className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-md border">
            {proposal.summary}
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <ShieldAlert className="h-4 w-4" />
            Boundary: <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">{proposal.dataBoundary}</span>
          </div>
          {!proposal.reversible && (
            <div className="flex items-center gap-1.5 text-destructive font-medium">
              <AlertTriangle className="h-4 w-4" />
              Non-reversible Action
            </div>
          )}
        </div>
      </CardContent>
      {!isPast && (
        <CardFooter className="border-t bg-muted/20 pt-4 flex justify-end gap-2">
          <Button variant="outline" className="text-destructive border-destructive/30 hover:bg-destructive/10"
            onClick={() => handleReview('denied')}
            disabled={reviewTool.isPending}
          >
            <X className="h-4 w-4 mr-2" /> Deny Request
          </Button>
          <Button variant="default" className="bg-primary hover:bg-primary/90"
            onClick={() => handleReview('approved')}
            disabled={reviewTool.isPending}
          >
            <Check className="h-4 w-4 mr-2" /> Approve Action
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
