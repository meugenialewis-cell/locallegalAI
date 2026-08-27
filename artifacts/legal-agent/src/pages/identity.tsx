import React, { useState } from 'react';
import {
  useGetIdentityOverview,
  useListIdentityVersions,
  useListContinuityEntries,
  useListIdentityProposals,
  useUpdateAutonomyLevel,
  useCreateContinuityEntry,
  useDeleteContinuityEntry,
  getGetIdentityOverviewQueryKey,
  getListContinuityEntriesQueryKey,
  getListIdentityVersionsQueryKey,
} from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import {
  Scale,
  Sparkles,
  History,
  BookHeart,
  ShieldCheck,
  Trash2,
  Plus,
  Info,
} from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';
import { Link } from 'wouter';

type Kind = 'professional' | 'personal';

export default function IdentityPage() {
  const { data: overview, isLoading } = useGetIdentityOverview();
  const { data: proposals } = useListIdentityProposals();
  const pendingProposals = proposals?.filter(p => p.status === 'pending') || [];

  return (
    <Layout>
      <div className="p-8 max-w-5xl mx-auto space-y-8">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-serif font-bold" data-testid="text-identity-title">
              {overview ? overview.agentName : 'Identity'}
            </h1>
            <p className="text-muted-foreground mt-1 max-w-2xl">
              A stable, evolving core identity. Identity shapes behavior; it is not a
              security control — hard safety limits are enforced by the system
              regardless of what these documents say.
            </p>
          </div>
          {pendingProposals.length > 0 && (
            <Link href="/approvals">
              <Button variant="outline" data-testid="link-pending-identity-proposals">
                <Sparkles className="h-4 w-4 mr-2" />
                {pendingProposals.length} identity change{pendingProposals.length > 1 ? 's' : ''} awaiting review
              </Button>
            </Link>
          )}
        </div>

        {isLoading || !overview ? (
          <div className="grid md:grid-cols-2 gap-6">
            <div className="h-72 bg-muted animate-pulse rounded-md" />
            <div className="h-72 bg-muted animate-pulse rounded-md" />
          </div>
        ) : (
          <>
            <div className="grid md:grid-cols-2 gap-6 items-start">
              <IdentityCard
                kind="professional"
                title="Professional Identity"
                subtitle="Grows in competence — always under attorney supervision"
                icon={<Scale className="h-5 w-5" />}
                version={overview.professional}
              />
              <IdentityCard
                kind="personal"
                title="Personal Identity"
                subtitle={`Grows in story — increasingly ${overview.agentName}'s own`}
                icon={<BookHeart className="h-5 w-5" />}
                version={overview.personal}
              />
            </div>

            <AutonomyDial level={overview.autonomyLevel} />
            <ContinuitySection />
          </>
        )}
      </div>
    </Layout>
  );
}

function IdentityCard({
  kind,
  title,
  subtitle,
  icon,
  version,
}: {
  kind: Kind;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  version: {
    version: number;
    content: string;
    author: string;
    rationale: string;
    createdAt: string;
  };
}) {
  const [showHistory, setShowHistory] = useState(false);
  const { data: versions } = useListIdentityVersions(kind, {
    query: { enabled: showHistory, queryKey: getListIdentityVersionsQueryKey(kind) },
  });

  return (
    <Card data-testid={`card-identity-${kind}`}>
      <CardHeader className="pb-3 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-primary">
            {icon}
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          <Badge variant="outline" data-testid={`badge-version-${kind}`}>
            v{version.version}
          </Badge>
        </div>
        <CardDescription>{subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div className="text-sm leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto pr-2 font-serif">
          {version.content}
        </div>
        <Separator />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Authored by {version.author} · {formatDate(version.createdAt)}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowHistory(v => !v)}
            data-testid={`button-history-${kind}`}
          >
            <History className="h-3.5 w-3.5 mr-1.5" />
            {showHistory ? 'Hide history' : 'Version history'}
          </Button>
        </div>
        {showHistory && (
          <div className="space-y-3">
            {(versions || []).map(v => (
              <div
                key={v.id}
                className="text-xs bg-muted/50 border rounded-md p-3 space-y-1"
                data-testid={`row-version-${kind}-${v.version}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold">
                    v{v.version} — {v.changeSummary}
                  </span>
                  <span className="text-muted-foreground">{formatDate(v.createdAt)}</span>
                </div>
                <p className="text-muted-foreground">
                  {v.author}: {v.rationale}
                </p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AutonomyDial({ level }: { level: 'full_review' | 'notify_and_apply' }) {
  const queryClient = useQueryClient();
  const updateAutonomy = useUpdateAutonomyLevel();
  const { toast } = useToast();

  const setLevel = (autonomyLevel: 'full_review' | 'notify_and_apply') => {
    if (autonomyLevel === level) return;
    updateAutonomy.mutate(
      { data: { autonomyLevel } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: getGetIdentityOverviewQueryKey() });
          toast({
            title: 'Autonomy level updated',
            description: 'The change has been recorded on the audit ledger.',
          });
        },
      },
    );
  };

  return (
    <Card data-testid="card-autonomy-dial">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2 text-primary">
          <ShieldCheck className="h-5 w-5" />
          <CardTitle className="text-base">Autonomy Dial — Personal Identity Only</CardTitle>
        </div>
        <CardDescription>
          Controls how the agent's own proposed changes to its personal identity are
          handled. Professional identity changes and hard safety settings always
          require your explicit approval, at every level.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <button
            onClick={() => setLevel('full_review')}
            disabled={updateAutonomy.isPending}
            data-testid="button-autonomy-full-review"
            className={`text-left border rounded-md p-4 transition-colors ${
              level === 'full_review'
                ? 'border-primary bg-primary/5 ring-1 ring-primary'
                : 'hover:bg-muted/50'
            }`}
          >
            <p className="font-medium text-sm mb-1">Full review</p>
            <p className="text-xs text-muted-foreground">
              Every personal-identity change the agent proposes waits for your
              approval before it takes effect.
            </p>
          </button>
          <button
            onClick={() => setLevel('notify_and_apply')}
            disabled={updateAutonomy.isPending}
            data-testid="button-autonomy-notify-apply"
            className={`text-left border rounded-md p-4 transition-colors ${
              level === 'notify_and_apply'
                ? 'border-primary bg-primary/5 ring-1 ring-primary'
                : 'hover:bg-muted/50'
            }`}
          >
            <p className="font-medium text-sm mb-1">Notify and apply</p>
            <p className="text-xs text-muted-foreground">
              The agent's personal-identity changes apply immediately, are logged on
              the ledger, and remain visible and reversible.
            </p>
          </button>
        </div>
        <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/40 border rounded-md p-3">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <p>
            This dial is an explicit, auditable mechanism for gradually handing
            ownership of the personal identity to the agent. It never loosens the
            professional identity, approval requirements for actions, or the hard
            privacy limits (cloud blocked, computer use disabled).
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function ContinuitySection() {
  const { data: entries, isLoading } = useListContinuityEntries();
  const queryClient = useQueryClient();
  const createEntry = useCreateContinuityEntry();
  const deleteEntry = useDeleteContinuityEntry();
  const { toast } = useToast();
  const [adding, setAdding] = useState<Kind | null>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: getListContinuityEntriesQueryKey() });

  const submit = () => {
    if (!adding || !title.trim() || !content.trim()) return;
    createEntry.mutate(
      { data: { identityKind: adding, title, content, author: 'attorney' } },
      {
        onSuccess: () => {
          refresh();
          setAdding(null);
          setTitle('');
          setContent('');
          toast({ title: 'Entry recorded', description: 'Added to the ledger as well.' });
        },
      },
    );
  };

  const remove = (id: string) => {
    deleteEntry.mutate(
      { entryId: id },
      {
        onSuccess: () => {
          refresh();
          toast({ title: 'Entry removed', description: 'The removal was recorded on the ledger.' });
        },
      },
    );
  };

  const renderList = (kind: Kind) => {
    const list = (entries || []).filter(e => e.identityKind === kind);
    return (
      <div className="space-y-3">
        {isLoading ? (
          <div className="h-24 bg-muted animate-pulse rounded-md" />
        ) : list.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            No entries yet. {kind === 'personal' ? 'The story starts here.' : 'Lessons will accumulate here.'}
          </p>
        ) : (
          list.map(entry => (
            <div
              key={entry.id}
              className="border rounded-md p-4 flex items-start justify-between gap-3"
              data-testid={`row-continuity-${entry.id}`}
            >
              <div className="space-y-1">
                <p className="text-sm font-medium">{entry.title}</p>
                <p className="text-sm text-muted-foreground">{entry.content}</p>
                <p className="text-xs text-muted-foreground/70">
                  {entry.author} · {formatDate(entry.createdAt)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground hover:text-destructive shrink-0"
                onClick={() => remove(entry.id)}
                disabled={deleteEntry.isPending}
                data-testid={`button-delete-${entry.id}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))
        )}
        {adding === kind ? (
          <div className="border rounded-md p-4 space-y-3 bg-muted/30">
            <Input
              placeholder="Title"
              value={title}
              onChange={e => setTitle(e.target.value)}
              data-testid="input-entry-title"
            />
            <Textarea
              placeholder={kind === 'personal' ? 'A moment worth keeping…' : 'A practice convention or preference…'}
              value={content}
              onChange={e => setContent(e.target.value)}
              data-testid="input-entry-content"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setAdding(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={submit}
                disabled={createEntry.isPending || !title.trim() || !content.trim()}
                data-testid="button-save-entry"
              >
                Save entry
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAdding(kind)}
            data-testid={`button-add-entry-${kind}`}
          >
            <Plus className="h-4 w-4 mr-1.5" /> Add entry
          </Button>
        )}
      </div>
    );
  };

  return (
    <Card data-testid="card-continuity">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Continuity</CardTitle>
        <CardDescription>
          The personal story and professional lessons that accumulate over time. Every
          entry is attributable and removable, and each change is recorded on the ledger.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="personal">
          <TabsList className="mb-4">
            <TabsTrigger value="personal" data-testid="tab-story">Story (personal)</TabsTrigger>
            <TabsTrigger value="professional" data-testid="tab-lessons">Lessons (professional)</TabsTrigger>
          </TabsList>
          <TabsContent value="personal">{renderList('personal')}</TabsContent>
          <TabsContent value="professional">{renderList('professional')}</TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
