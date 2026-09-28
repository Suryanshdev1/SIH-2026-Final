import { useEffect, useState, useCallback } from 'react';
import type { ThermalCluster } from '@/types/cluster';
import { fetchClusters } from '@/api/clustersApi';

export type AsyncStatus = 'loading' | 'success' | 'error';

interface UseClustersResult {
  clusters: ThermalCluster[];
  status: AsyncStatus;
  error: string | null;
  refetch: () => void;
}

export function useClusters(): UseClustersResult {
  const [clusters, setClusters] = useState<ThermalCluster[]>([]);
  const [status, setStatus] = useState<AsyncStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const refetch = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;

    const loadData = (isBackgroundPoll = false) => {
      // Pehli baar loading state dikhayenge, background refresh mein nahi
      if (!isBackgroundPoll) {
        setStatus('loading');
        setError(null);
      }

      fetchClusters()
        .then((data) => {
          if (cancelled) return;
          setClusters(data);
          setStatus('success');
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : 'Failed to load thermal clusters.');
          setStatus('error');
        });
    };

    // 1. Initial fetch (Loading screen ke saath)
    loadData(false);

    // 2. Har 5 second mein live Wokwi data background mein refresh hoga
    const intervalId = setInterval(() => {
      loadData(true);
    }, 5000);

    // 3. Cleanup function
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [reloadKey]);

  return { clusters, status, error, refetch };
}
