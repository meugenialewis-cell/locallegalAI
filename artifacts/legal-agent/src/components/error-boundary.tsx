import { Component, type ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { Layout } from '@/components/layout';

interface Props {
  children: ReactNode;
  resetKey?: any;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: undefined });
    }
  }

  public render() {
    if (this.state.hasError) {
      return (
        <Layout>
          <div className="flex h-[80vh] w-full items-center justify-center p-6">
            <div className="flex max-w-md flex-col items-center justify-center text-center space-y-4 bg-destructive/10 p-8 rounded-lg border border-destructive/20">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <h2 className="text-xl font-bold text-foreground">Something went wrong</h2>
              <p className="text-sm text-muted-foreground">
                {this.state.error?.message || 'An unexpected error occurred in the workstation.'}
              </p>
              <button
                className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md shadow-sm hover:bg-primary/90 text-sm font-medium"
                onClick={() => this.setState({ hasError: false, error: undefined })}
              >
                Try again
              </button>
            </div>
          </div>
        </Layout>
      );
    }

    return this.props.children;
  }
}
