import React, { useState } from 'react';
import { useListMatters, useCreateMatter, getListMattersQueryKey } from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, Search, FileText, Calendar } from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { Link } from 'wouter';
import { useToast } from '@/hooks/use-toast';

export default function MattersList() {
  const { data: matters, isLoading } = useListMatters();
  const [search, setSearch] = useState('');

  const filteredMatters = matters?.filter(m => 
    m.name.toLowerCase().includes(search.toLowerCase()) || 
    m.clientReference.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Layout>
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-serif font-bold">Isolated Matters</h1>
            <p className="text-muted-foreground mt-1">Manage and access sealed case environments.</p>
          </div>
          <CreateMatterDialog />
        </div>

        <div className="flex items-center space-x-4 bg-card border rounded-md px-3 py-2">
          <Search className="h-5 w-5 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Search by matter name or reference..." 
            className="flex-1 bg-transparent outline-none text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1,2,3].map(i => <Card key={i} className="h-40 animate-pulse bg-muted/50" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredMatters?.map(matter => (
              <Card key={matter.id} className="hover:shadow-md transition-shadow group flex flex-col">
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start gap-4">
                    <CardTitle className="text-lg leading-tight group-hover:text-primary transition-colors line-clamp-2">
                      <Link href={`/matters/${matter.id}`} className="hover:underline">
                        {matter.name}
                      </Link>
                    </CardTitle>
                    <Badge variant="secondary" className="capitalize shrink-0">
                      {matter.status.replace('_', ' ')}
                    </Badge>
                  </div>
                  <CardDescription className="font-mono text-xs">{matter.clientReference}</CardDescription>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col justify-end">
                  <div className="flex items-center justify-between text-sm text-muted-foreground border-t pt-3 mt-3">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-4 w-4" />
                      <span>{matter.documentCount} docs</span>
                    </div>
                    <div className="flex items-center gap-1.5" title="Last activity">
                      <Calendar className="h-4 w-4" />
                      <span>{formatDate(matter.lastActivityAt)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {filteredMatters?.length === 0 && (
              <div className="col-span-full py-12 text-center text-muted-foreground">
                No matters found matching your search.
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}

function CreateMatterDialog() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const createMatter = useCreateMatter();
  const { toast } = useToast();
  
  const [formData, setFormData] = useState({ name: '', clientReference: '', type: 'litigation' });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMatter.mutate({ data: formData }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListMattersQueryKey() });
        setOpen(false);
        setFormData({ name: '', clientReference: '', type: 'litigation' });
        toast({ title: 'Matter created', description: 'New isolated environment ready.' });
      },
      onError: () => {
        toast({ title: 'Error', description: 'Failed to create matter.', variant: 'destructive' });
      }
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Plus className="h-4 w-4" /> New Matter
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>Create Isolated Matter</DialogTitle>
            <DialogDescription>
              This will create a new cryptographically separated workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-6">
            <div className="space-y-2">
              <Label htmlFor="name">Matter Name</Label>
              <Input 
                id="name" 
                required 
                value={formData.name}
                onChange={e => setFormData(p => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Smith v. Jones"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clientReference">Client Reference</Label>
              <Input 
                id="clientReference" 
                required 
                value={formData.clientReference}
                onChange={e => setFormData(p => ({ ...p, clientReference: e.target.value }))}
                placeholder="e.g. SMI-001"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="type">Matter Type</Label>
              <select 
                id="type"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={formData.type}
                onChange={e => setFormData(p => ({ ...p, type: e.target.value }))}
              >
                <option value="litigation">Litigation</option>
                <option value="transactional">Transaction</option>
                <option value="advisory">Advisory</option>
                <option value="regulatory">Regulatory</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={createMatter.isPending}>
              {createMatter.isPending ? 'Creating...' : 'Create Matter'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
