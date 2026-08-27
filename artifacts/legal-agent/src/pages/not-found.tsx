import { Layout } from '@/components/layout';
import { FileQuestion } from 'lucide-react';
import { Link } from 'wouter';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <Layout>
      <div className="flex flex-col items-center justify-center h-full space-y-4 p-8 text-center max-w-md mx-auto">
        <div className="bg-muted p-6 rounded-full text-muted-foreground mb-4">
          <FileQuestion className="h-12 w-12" />
        </div>
        <h1 className="text-3xl font-serif font-bold text-foreground">Record Not Found</h1>
        <p className="text-muted-foreground pb-4">
          The requested path does not exist in the isolated workstation environment.
        </p>
        <Link href="/">
          <Button variant="default">Return to Dashboard</Button>
        </Link>
      </div>
    </Layout>
  );
}
