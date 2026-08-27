import React from 'react';
import { useGetSystemSettings, useUpdateSystemSettings, getGetSystemSettingsQueryKey } from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { Shield, Server, Lock, HardDrive, AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

export default function Settings() {
  const { data: settings, isLoading } = useGetSystemSettings();
  const updateSettings = useUpdateSystemSettings();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [formData, setFormData] = React.useState<any>(null);

  React.useEffect(() => {
    if (settings && !formData) {
      setFormData(settings);
    }
  }, [settings, formData]);

  const handleSave = () => {
    updateSettings.mutate({ 
      data: {
        runtime: formData.runtime,
        endpoint: formData.endpoint,
        model: formData.model,
        offlineOnly: formData.offlineOnly,
        approvalRequired: formData.approvalRequired
      }
    }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetSystemSettingsQueryKey() });
        toast({ title: 'Settings saved', description: 'Workstation configuration updated safely.' });
      }
    });
  };

  if (isLoading || !formData) {
    return (
      <Layout>
        <div className="p-8 space-y-6">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-64" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="p-8 max-w-4xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-serif font-bold">Workstation Settings</h1>
          <p className="text-muted-foreground mt-1">Configure local runtime and privacy guardrails.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-8">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2 text-primary">
                  <Server className="h-5 w-5" />
                  <CardTitle>Local LLM Runtime</CardTitle>
                </div>
                <CardDescription>Configure the engine driving the local model.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Runtime Engine</Label>
                  <select 
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={formData.runtime}
                    onChange={e => setFormData({ ...formData, runtime: e.target.value })}
                  >
                    <option value="mlx">Apple MLX (Optimized for Mac)</option>
                    <option value="llamacpp">llama.cpp</option>
                    <option value="ollama">Ollama</option>
                    <option value="lmstudio">LM Studio</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>API Endpoint</Label>
                  <Input 
                    value={formData.endpoint}
                    onChange={e => setFormData({ ...formData, endpoint: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Model Name / Path</Label>
                  <Input 
                    value={formData.model}
                    onChange={e => setFormData({ ...formData, model: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">Currently: <span className="font-medium text-foreground">{settings?.modelStatus}</span></p>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-8">
            <Card className="border-primary/20">
              <CardHeader>
                <div className="flex items-center gap-2 text-primary">
                  <Shield className="h-5 w-5" />
                  <CardTitle>Privacy Guardrails</CardTitle>
                </div>
                <CardDescription>Strict enforcement policies for the agent.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">Offline Only Mode</Label>
                    <p className="text-sm text-muted-foreground">Block all external network requests by the agent.</p>
                  </div>
                  <Switch 
                    checked={formData.offlineOnly}
                    onCheckedChange={c => setFormData({ ...formData, offlineOnly: c })}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base flex items-center gap-2">
                      Approval Required
                      <AlertTriangle className="h-3.5 w-3.5 text-warning" />
                    </Label>
                    <p className="text-sm text-muted-foreground">Require human review before tool execution.</p>
                  </div>
                  <Switch 
                    checked={formData.approvalRequired}
                    onCheckedChange={c => setFormData({ ...formData, approvalRequired: c })}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center gap-2 text-primary">
                  <HardDrive className="h-5 w-5" />
                  <CardTitle>Hardware Profile</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="bg-muted p-4 rounded-md flex items-start gap-4">
                  <Lock className="h-8 w-8 text-muted-foreground mt-1" />
                  <div>
                    <p className="font-medium text-sm">Encrypted Local Storage</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Data is sealed using <strong>{settings?.storageEncryption}</strong> encryption. 
                      Detected hardware profile: <span className="font-mono">{settings?.hardwareProfile}</span>
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t">
          <Button 
            size="lg" 
            onClick={handleSave} 
            disabled={updateSettings.isPending}
          >
            {updateSettings.isPending ? 'Saving...' : 'Save Configuration'}
          </Button>
        </div>
      </div>
    </Layout>
  );
}
