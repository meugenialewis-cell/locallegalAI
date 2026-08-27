import React, { useState, useRef, useEffect } from 'react';
import { useRoute } from 'wouter';
import { useGetMatter, useListMatterDocuments, useCreateMatterQuery } from '@workspace/api-client-react';
import { Layout } from '@/components/layout';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { FileText, Search, Shield, Send, FileSignature, CheckCircle2, AlertCircle } from 'lucide-react';
import { formatDate } from '@/lib/utils';

export default function MatterWorkspace() {
  const [, params] = useRoute('/matters/:matterId');
  const matterId = params?.matterId || '';

  const { data: matter, isLoading: loadingMatter } = useGetMatter(matterId);
  const { data: documents, isLoading: loadingDocs } = useListMatterDocuments(matterId);
  
  const queryMutation = useCreateMatterQuery();

  const [query, setQuery] = useState('');
  const [history, setHistory] = useState<any[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, queryMutation.isPending]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || queryMutation.isPending) return;

    const currentQuery = query;
    setQuery('');
    setHistory(prev => [...prev, { role: 'user', content: currentQuery }]);

    queryMutation.mutate({ matterId, data: { question: currentQuery } }, {
      onSuccess: (answer) => {
        setHistory(prev => [...prev, { role: 'agent', ...answer }]);
      },
      onError: () => {
        setHistory(prev => [...prev, { role: 'error', content: 'Failed to retrieve grounded answer.' }]);
      }
    });
  };

  if (loadingMatter) return <Layout><div className="p-8"><Skeleton className="h-10 w-64 mb-4"/><Skeleton className="h-[600px]"/></div></Layout>;
  if (!matter) return <Layout><div className="p-8">Matter not found</div></Layout>;

  return (
    <Layout>
      <div className="flex flex-col h-full">
        {/* Workspace Header */}
        <header className="shrink-0 border-b bg-card px-6 py-4 flex items-center justify-between z-10">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-serif font-bold text-foreground">{matter.name}</h1>
              <Badge variant="outline" className="bg-muted font-mono">{matter.clientReference}</Badge>
            </div>
            <div className="text-sm text-muted-foreground mt-1 flex items-center gap-4">
              <span className="capitalize">{matter.type} Matter</span>
              <span>•</span>
              <span className="flex items-center gap-1"><Shield className="h-3 w-3"/> Isolated Corpus</span>
            </div>
          </div>
          <Badge variant={matter.status === 'active' ? 'success' : 'secondary'} className="capitalize shadow-sm">
            {matter.status.replace('_', ' ')}
          </Badge>
        </header>

        {/* Split Pane */}
        <div className="flex-1 flex overflow-hidden">
          
          {/* Left Panel: Documents */}
          <aside className="w-[340px] border-r bg-muted/10 flex flex-col shrink-0">
            <div className="p-4 border-b">
              <h2 className="font-semibold flex items-center gap-2">
                <FileSignature className="h-4 w-4" />
                Matter Documents
              </h2>
              <div className="mt-3 relative">
                <Search className="h-4 w-4 absolute left-3 top-2.5 text-muted-foreground" />
                <Input placeholder="Filter documents..." className="pl-9 bg-background h-9" />
              </div>
            </div>
            
            <ScrollArea className="flex-1">
              {loadingDocs ? (
                <div className="p-4 space-y-3">
                  {[1,2,3].map(i => <Skeleton key={i} className="h-16 w-full" />)}
                </div>
              ) : documents?.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  No documents indexed yet.
                </div>
              ) : (
                <div className="p-2 space-y-1">
                  {documents?.map(doc => (
                    <div key={doc.id} className="p-3 rounded-md hover:bg-muted/50 cursor-pointer transition-colors group border border-transparent hover:border-border">
                      <div className="flex items-start gap-3">
                        <FileText className="h-8 w-8 text-primary/70 shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate group-hover:text-primary transition-colors" title={doc.name}>
                            {doc.name}
                          </p>
                          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                            <span className="uppercase">{doc.kind}</span>
                            <span>•</span>
                            <span>{doc.pageCount} pgs</span>
                          </div>
                        </div>
                      </div>
                      <div className="mt-3 pt-2 border-t border-border/50 flex items-center justify-between text-[10px] text-muted-foreground">
                        <div className="flex items-center gap-1">
                          {doc.status === 'indexed' ? <CheckCircle2 className="h-3 w-3 text-emerald-500" /> : <AlertCircle className="h-3 w-3 text-amber-500" />}
                          <span className="capitalize">{doc.status}</span>
                        </div>
                        <span className="font-mono uppercase opacity-50" title={doc.integrityHash}>{doc.integrityHash.substring(0,8)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </aside>

          {/* Right Panel: Chat / Query */}
          <main className="flex-1 flex flex-col bg-background relative">
            
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 scroll-smooth" ref={scrollRef}>
              {history.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4 text-muted-foreground">
                  <Shield className="h-12 w-12 text-primary/20" />
                  <h3 className="text-lg font-medium text-foreground">Grounded Legal Query</h3>
                  <p className="text-sm">
                    Ask questions against the {documents?.length || 0} indexed documents in this matter. 
                    All answers are strictly scoped to the provided corpus and heavily cited.
                  </p>
                  <div className="grid grid-cols-1 gap-2 w-full mt-4">
                    <Button variant="outline" className="justify-start h-auto py-3 text-left font-normal text-muted-foreground hover:text-foreground" onClick={() => setQuery('Summarize the main arguments in the latest filing.')}>
                      "Summarize the main arguments in the latest filing."
                    </Button>
                    <Button variant="outline" className="justify-start h-auto py-3 text-left font-normal text-muted-foreground hover:text-foreground" onClick={() => setQuery('List all dates and deadlines mentioned.')}>
                      "List all dates and deadlines mentioned."
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-8 max-w-3xl mx-auto pb-10">
                  {history.map((msg, i) => (
                    <div key={i} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                      
                      {msg.role !== 'user' && (
                        <div className="shrink-0 h-8 w-8 rounded bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
                          <ScaleIcon className="h-4 w-4" />
                        </div>
                      )}
                      
                      <div className={`max-w-[85%] ${msg.role === 'user' ? 'bg-muted text-foreground px-4 py-3 rounded-2xl rounded-tr-sm' : ''}`}>
                        
                        {msg.role === 'user' ? (
                          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                        ) : msg.role === 'error' ? (
                          <div className="bg-destructive/10 text-destructive p-4 rounded-md border border-destructive/20 text-sm">
                            {msg.content}
                          </div>
                        ) : (
                          <div className="space-y-6">
                            <div className="prose prose-sm prose-slate max-w-none">
                              <p className="text-[15px] leading-relaxed text-foreground">{msg.answer}</p>
                            </div>
                            
                            {/* Citations */}
                            {msg.citations?.length > 0 && (
                              <div className="bg-muted/30 border rounded-lg p-4 mt-6">
                                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                                  <FileText className="h-3.5 w-3.5" /> Sources Cited
                                </h4>
                                <div className="space-y-3">
                                  {msg.citations.map((c: any, idx: number) => (
                                    <div key={idx} className="bg-background border rounded-md p-3 text-sm">
                                      <div className="flex justify-between items-start mb-2">
                                        <span className="font-medium text-primary hover:underline cursor-pointer">{c.documentName}</span>
                                        <Badge variant="outline" className="text-[10px]">Page {c.page}</Badge>
                                      </div>
                                      <p className="text-muted-foreground text-xs font-serif italic border-l-2 border-primary/30 pl-3 py-1">
                                        "{c.excerpt}"
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Identity attribution */}
                            {msg.identityVersions && (
                              <p className="text-[11px] text-muted-foreground/70" data-testid="text-identity-attribution">
                                Answered by {msg.identityVersions.agentName} · professional identity v{msg.identityVersions.professionalVersion} · personal identity v{msg.identityVersions.personalVersion}
                              </p>
                            )}

                            {/* Disclaimer */}
                            {msg.disclaimer && (
                              <div className="flex gap-2 text-xs text-muted-foreground bg-amber-500/10 text-amber-700/80 p-3 rounded-md">
                                <AlertCircle className="h-4 w-4 shrink-0" />
                                <p>{msg.disclaimer}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  
                  {queryMutation.isPending && (
                    <div className="flex gap-4">
                      <div className="shrink-0 h-8 w-8 rounded bg-primary/50 text-primary-foreground flex items-center justify-center">
                        <ScaleIcon className="h-4 w-4 animate-pulse" />
                      </div>
                      <div className="bg-card border shadow-sm p-4 rounded-2xl rounded-tl-sm w-64 space-y-3">
                        <div className="flex items-center gap-2 text-sm text-primary font-medium">
                          <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                          Analyzing corpus...
                        </div>
                        <Skeleton className="h-2 w-full" />
                        <Skeleton className="h-2 w-3/4" />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="p-4 bg-background border-t">
              <div className="max-w-3xl mx-auto relative">
                <form onSubmit={handleSubmit} className="relative">
                  <Input
                    className="w-full pl-4 pr-12 py-6 text-[15px] rounded-xl shadow-sm border-input bg-card focus-visible:ring-primary"
                    placeholder="Ask a question about the matter documents..."
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    disabled={queryMutation.isPending}
                  />
                  <Button 
                    type="submit" 
                    size="icon" 
                    className="absolute right-2 top-2 h-8 w-8 rounded-lg"
                    disabled={!query.trim() || queryMutation.isPending}
                  >
                    <Send className="h-4 w-4 ml-0.5" />
                  </Button>
                </form>
                <div className="text-center mt-2">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium flex items-center justify-center gap-1.5">
                    <Shield className="h-3 w-3" /> Local deployment target • Demo corpus in this preview
                  </span>
                </div>
              </div>
            </div>

          </main>
        </div>
      </div>
    </Layout>
  );
}

function ScaleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
      <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
      <path d="M7 21h10" />
      <path d="M12 3v18" />
      <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
    </svg>
  );
}
