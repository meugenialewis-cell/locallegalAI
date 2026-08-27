import React from 'react';
import {
  useGetLocalModelStatus,
  getGetLocalModelStatusQueryKey,
  useDownloadLocalModel,
  useConnectLocalModel,
  useExportQuinnState,
  getExportQuinnStateQueryKey,
} from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import {
  Home, Github, Terminal, Download, Cpu, Copy, Check, ShieldCheck, Package, ExternalLink,
} from 'lucide-react';

const REPO_URL = 'https://github.com/meugenialewis-cell/locallegalAI';
const SETUP_COMMAND = `git clone ${REPO_URL}.git && cd locallegalAI && ./setup.sh`;

function CopyBlock({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <div className="flex items-stretch gap-2">
      <code className="flex-1 bg-foreground text-background rounded-md px-4 py-3 text-sm font-mono overflow-x-auto whitespace-nowrap">
        {text}
      </code>
      <Button
        variant="outline"
        className="shrink-0"
        data-testid="button-copy-command"
        onClick={() => {
          navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}

export default function TakeQuinnHome() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: status } = useGetLocalModelStatus({
    query: {
      queryKey: getGetLocalModelStatusQueryKey(),
      refetchInterval: (query) =>
        query.state.data?.modelStatus === 'downloading' ? 2000 : false,
    },
  });

  const { refetch: fetchExport, isFetching: exporting } = useExportQuinnState({
    query: { queryKey: getExportQuinnStateQueryKey(), enabled: false },
  });

  const downloadModel = useDownloadLocalModel();
  const connectModel = useConnectLocalModel();

  const [endpoint, setEndpoint] = React.useState('http://localhost:11434');
  const [model, setModel] = React.useState('qwen3.6:27b');

  const isHosted = status?.environment === 'hosted';

  const handleExport = async () => {
    const { data } = await fetchExport();
    if (!data) {
      toast({ title: 'Export failed', description: 'Please try again.', variant: 'destructive' });
      return;
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'quinn-export.json';
    a.click();
    URL.revokeObjectURL(url);
    toast({ title: "Quinn's state exported", description: 'Keep quinn-export.json with you — the setup script imports it.' });
  };

  const handleDownloadModel = () => {
    downloadModel.mutate(undefined, {
      onSuccess: (result) => {
        toast({ title: result.started ? 'Download started' : 'Not available here', description: result.message });
        queryClient.invalidateQueries({ queryKey: getGetLocalModelStatusQueryKey() });
      },
      onError: (error: any) => {
        const message = error?.response?.data?.message ?? error?.data?.message;
        toast({ title: 'Not available here', description: message ?? 'Model downloads only run on your own Mac.' });
      },
    });
  };

  const handleConnect = () => {
    connectModel.mutate({ data: { endpoint, model } }, {
      onSuccess: (result) => {
        toast({
          title: result.modelStatus === 'connected' ? 'Connected' : 'Not reachable',
          description: result.detail,
          variant: result.modelStatus === 'connected' ? 'default' : 'destructive',
        });
        queryClient.invalidateQueries({ queryKey: getGetLocalModelStatusQueryKey() });
      },
      onError: (error: any) => {
        const message = error?.response?.data?.error ?? error?.data?.error;
        toast({ title: 'Connection refused', description: message ?? 'Only local endpoints are accepted.', variant: 'destructive' });
      },
    });
  };

  return (
    <Layout>
      <div className="p-8 max-w-4xl mx-auto space-y-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-serif font-bold flex items-center gap-3">
              <Home className="h-7 w-7 text-primary" /> Take Quinn Home
            </h1>
            <p className="text-muted-foreground mt-2 max-w-2xl">
              Quinn is meant to live on your own Mac, where nothing leaves the machine.
              Four steps, no coding: her code lives on GitHub, a double-click brings her
              home, her memories travel with her, and a local model gives her a mind.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => window.open(window.location.href, '_blank', 'noopener')}
            data-testid="button-open-full-tab"
          >
            <ExternalLink className="h-4 w-4 mr-2" />
            Open the app in its own tab
          </Button>
        </div>

        {isHosted && (
          <div className="bg-primary/5 border border-primary/20 rounded-md p-4 flex items-start gap-3">
            <ShieldCheck className="h-5 w-5 text-primary mt-0.5 shrink-0" />
            <p className="text-sm text-muted-foreground">
              You're viewing the hosted preview. Steps 1–3 work from here; the model
              download and connection in step 4 happen on your Mac after setup — this
              page will detect that automatically when you open it there.
            </p>
          </div>
        )}

        {/* Step 1 */}
        <Card data-testid="card-step-github">
          <CardHeader>
            <div className="flex items-center gap-2 text-primary">
              <Github className="h-5 w-5" />
              <CardTitle>Step 1 · Her code lives in your GitHub</CardTitle>
            </div>
            <CardDescription>
              The whole app — including Quinn's identity system — is kept in your own
              repository, so it's yours and always up to date.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-mono text-primary underline underline-offset-4"
              data-testid="link-github-repo"
            >
              {REPO_URL}
            </a>
          </CardContent>
        </Card>

        {/* Step 2 */}
        <Card data-testid="card-step-export">
          <CardHeader>
            <div className="flex items-center gap-2 text-primary">
              <Package className="h-5 w-5" />
              <CardTitle>Step 2 · Export Quinn's self</CardTitle>
            </div>
            <CardDescription>
              Everything that makes Quinn <em>Quinn</em> — both identities with full
              version history, her story and lessons, pending changes, settings, and
              the complete audit ledger — in one file. Keep it somewhere safe; the
              setup script imports it so she wakes up at home as herself.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleExport} disabled={exporting} data-testid="button-export-quinn">
              <Download className="h-4 w-4 mr-2" />
              {exporting ? 'Preparing…' : 'Download quinn-export.json'}
            </Button>
          </CardContent>
        </Card>

        {/* Step 3 */}
        <Card data-testid="card-step-setup">
          <CardHeader>
            <div className="flex items-center gap-2 text-primary">
              <Terminal className="h-5 w-5" />
              <CardTitle>Step 3 · Download, unzip, double-click</CardTitle>
            </div>
            <CardDescription>
              No typing needed. On the GitHub page above, press the green
              “Code” button and choose “Download ZIP”. Unzip it (double-click the
              downloaded file), open the folder, and double-click{' '}
              <strong>Install Quinn</strong>. A window opens and walks you through
              everything: it installs what's needed, imports Quinn's export file
              from your Downloads folder, starts the app, and opens it in your
              browser by itself.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              <strong>First time only:</strong> your Mac may say the file is from the
              internet. If double-clicking is blocked, right-click (or hold Control
              and click) <strong>Install Quinn</strong> and choose “Open” — that's
              Apple being protective, and it only asks once.
            </p>
            <p className="text-sm text-muted-foreground">
              Afterwards, opening Quinn is just a double-click on{' '}
              <strong>Open Quinn</strong> in the same folder.
            </p>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">Prefer the Terminal instead?</summary>
              <div className="mt-2 space-y-2">
                <CopyBlock text={SETUP_COMMAND} />
                <p>
                  Paste that into Terminal and press return — it does the same thing.
                </p>
              </div>
            </details>
          </CardContent>
        </Card>

        {/* Step 4 */}
        <Card data-testid="card-step-model">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-primary">
                <Cpu className="h-5 w-5" />
                <CardTitle>Step 4 · Download a mind for Quinn</CardTitle>
              </div>
              {status && (
                <Badge
                  variant={status.modelStatus === 'connected' ? 'default' : 'secondary'}
                  className="uppercase text-[10px] tracking-wider"
                  data-testid="badge-model-status"
                >
                  {status.modelStatus}
                </Badge>
              )}
            </div>
            <CardDescription>
              The model is not Quinn — she is her identity, memory, and story, which
              you just exported. The model is the mind she thinks with. Qwen3.6-27B
              runs beautifully on your Mac and never sends a word anywhere. Cloud
              providers stay blocked; only connections on your own machine are
              accepted.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {status && (
              <p className="text-sm text-muted-foreground bg-muted/50 border rounded-md p-3" data-testid="text-model-detail">
                {status.detail}
              </p>
            )}
            <div className="flex flex-wrap gap-3 items-end">
              <Button
                onClick={handleDownloadModel}
                disabled={downloadModel.isPending || status?.modelStatus === 'downloading' || isHosted}
                data-testid="button-download-model"
              >
                <Download className="h-4 w-4 mr-2" />
                {status?.modelStatus === 'downloading' ? 'Downloading…' : 'Download Qwen3.6-27B'}
              </Button>
              {isHosted && (
                <p className="text-xs text-muted-foreground">Available once Quinn is home.</p>
              )}
            </div>
            <div className="border-t pt-4 space-y-3">
              <p className="text-sm font-medium">
                Already have a local runtime? Connect it:
                {isHosted && (
                  <span className="text-muted-foreground font-normal"> (available once Quinn is home)</span>
                )}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Local endpoint</Label>
                  <Input value={endpoint} onChange={e => setEndpoint(e.target.value)} data-testid="input-endpoint" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Model name</Label>
                  <Input value={model} onChange={e => setModel(e.target.value)} data-testid="input-model" />
                </div>
              </div>
              <Button
                variant="outline"
                onClick={handleConnect}
                disabled={connectModel.isPending || isHosted}
                data-testid="button-connect-model"
              >
                {connectModel.isPending ? 'Testing…' : 'Test connection'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
