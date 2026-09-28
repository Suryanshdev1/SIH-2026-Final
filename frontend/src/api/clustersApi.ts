import type { ThermalCluster } from '@/types/cluster';
import { mockClusters } from '@/mock/clusters';
import { toThermalClusters, type ThermalMapResponse, type BackendErrorResponse } from './adapters';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
const NETWORK_DELAY_MS = 550;

// 🚀 GLOBAL CACHE & PROMISE TRACKER
let globalClustersCache: ThermalCluster[] | null = null;
let lastFetchTime = 0;
const CACHE_DURATION_MS = 3000; 
let fetchPromise: Promise<ThermalCluster[]> | null = null; // In-flight request tracker

function delay<T>(value: T, ms = NETWORK_DELAY_MS): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

function assertNotBackendError(
  body: ThermalMapResponse | BackendErrorResponse,
): asserts body is ThermalMapResponse {
  const err = body as BackendErrorResponse;
  if (err.error || err.status === 'error') {
    throw new Error(`Backend error: ${err.error ?? err.message ?? 'unknown'}`);
  }
}

export async function fetchClusters(): Promise<ThermalCluster[]> {
  if (USE_MOCK) return delay(mockClusters);

  // Background fetch logic
  const backgroundFetch = async () => {
    if (fetchPromise) return fetchPromise;
    
    fetchPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/thermal-map`);
        if (!res.ok) throw new Error(`Failed to fetch clusters: ${res.status}`);
        
        const body = (await res.json()) as ThermalMapResponse | BackendErrorResponse;
        assertNotBackendError(body);
        
        const clusters = toThermalClusters(body);
        globalClustersCache = clusters;
        lastFetchTime = Date.now();
        return clusters;
      } finally {
        fetchPromise = null;
      }
    })();
    return fetchPromise;
  };

  // ⚡ SUPER FAST LOAD: Agar cache memory mein hai, toh page INSTANTLY (0s) load kardo
  if (globalClustersCache) {
    const isStale = Date.now() - lastFetchTime > CACHE_DURATION_MS;
    if (isStale) {
      backgroundFetch(); // Purana data dikhao, naya chup-chaap background mein laao
    }
    return globalClustersCache;
  }

  // Sirf pehli baar (First ever load) wait karega
  return backgroundFetch();
}

export async function fetchClusterById(
  clusterId: string,
): Promise<ThermalCluster | null> {
  if (USE_MOCK) {
    const found = mockClusters.find((c) => c.cluster_id === clusterId) ?? null;
    return delay(found);
  }

  const clusters = await fetchClusters();
  return clusters.find((c) => c.cluster_id === clusterId) ?? null;
}