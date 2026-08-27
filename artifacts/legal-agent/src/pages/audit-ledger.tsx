import React from 'react';
import { useListAuditEvents } from '@workspace/api-client-react';
import { Layout } from '@/components/layout';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';
import { ShieldAlert, Fingerprint } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

export default function AuditLedger() {
  const { data: events, isLoading } = useListAuditEvents({ limit: 50 });

  return (
    <Layout>
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between border-b pb-6">
          <div>
            <h1 className="text-3xl font-serif font-bold">Audit Ledger</h1>
            <p className="text-muted-foreground mt-1">Tamper-evident record of all system actions.</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-primary bg-primary/10 px-3 py-1.5 rounded-md">
            <Fingerprint className="h-4 w-4" />
            <span className="font-medium">Cryptographically Verified</span>
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <div className="border rounded-md bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Timestamp</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead className="text-right">Chain Hash</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events?.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-mono text-xs whitespace-nowrap text-muted-foreground">
                      {formatDate(event.occurredAt)}
                    </TableCell>
                    <TableCell className="font-medium">{event.actor}</TableCell>
                    <TableCell>{event.action}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize text-xs">
                        {event.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant={event.outcome === 'success' ? 'success' : event.outcome === 'denied' ? 'destructive' : 'secondary'}
                        className="capitalize"
                      >
                        {event.outcome}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="font-mono text-xs text-muted-foreground px-2 py-1 bg-muted rounded truncate max-w-[120px] inline-block" title={event.chainHash}>
                        {event.chainHash.substring(0, 12)}...
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
                {events?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                      No audit events recorded yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </Layout>
  );
}
