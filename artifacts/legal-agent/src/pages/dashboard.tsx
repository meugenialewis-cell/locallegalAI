import React from 'react';
import { useGetDashboard } from '@workspace/api-client-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Shield, ShieldAlert, Lock, CheckCircle, Clock, FileText, Database } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Link } from 'wouter';
import { formatDate } from '@/lib/utils';
import { Layout } from '@/components/layout';

export default function Dashboard() {
  const { data, isLoading, error } = useGetDashboard();

  if (isLoading) {
    return (
      <Layout>
        <div className="p-8 space-y-6">
          <Skeleton className="h-10 w-48" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        </div>
      </Layout>
    );
  }

  if (error || !data) {
    return (
      <Layout>
        <div className="p-8">
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Failed to load workstation status</CardTitle>
            </CardHeader>
            <CardContent>
              <p>Check the system connection and refresh.</p>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="p-8 space-y-8 max-w-6xl mx-auto">
        <div>
          <h1 className="text-3xl font-serif font-bold text-foreground">Workstation Overview</h1>
          <p className="text-muted-foreground mt-1">Secure local deployment prototype.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Active Matters</CardTitle>
              <BriefcaseIcon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.activeMatterCount}</div>
              <p className="text-xs text-muted-foreground mt-1">Isolated by matter</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Indexed Documents</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.indexedDocumentCount}</div>
              <p className="text-xs text-muted-foreground mt-1">Citation-ready demo corpus</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Pending Approvals</CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{data.pendingApprovalCount}</div>
              <p className="text-xs text-muted-foreground mt-1">Actions awaiting review</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-primary" />
                <CardTitle>Safety Posture</CardTitle>
              </div>
              <CardDescription>Current workstation security settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Storage Encryption</span>
                </div>
                <Badge variant="outline" className="font-mono text-xs capitalize">{data.storageMode}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Model Connection</span>
                </div>
                <Badge variant={data.modelStatus === 'connected' ? 'success' : 'destructive'} className="capitalize">
                  {data.modelStatus}
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Matters</CardTitle>
              <CardDescription>Latest active cases</CardDescription>
            </CardHeader>
            <CardContent>
              {data.recentMatters.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No recent matters found.</p>
              ) : (
                <div className="space-y-4">
                  {data.recentMatters.map(matter => (
                    <div key={matter.id} className="flex items-center justify-between">
                      <div>
                        <Link href={`/matters/${matter.id}`} className="font-medium hover:underline">
                          {matter.name}
                        </Link>
                        <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                          <span className="font-mono">{matter.clientReference}</span>
                          <span>•</span>
                          <span className="flex items-center gap-1"><Clock className="h-3 w-3"/> {formatDate(matter.lastActivityAt)}</span>
                        </div>
                      </div>
                      <Badge variant="outline" className="capitalize">{matter.status.replace('_', ' ')}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  );
}

function BriefcaseIcon(props: React.SVGProps<SVGSVGElement>) {
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
      <rect width="20" height="14" x="2" y="7" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  );
}
