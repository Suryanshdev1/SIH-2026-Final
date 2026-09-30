import type { SosAlert, NotificationState } from '@/types/alert';
import type { ThermalCluster } from '@/types/cluster';
import { mockAlerts } from '@/mock/alerts';
import { toSosAlerts, type BackendAlert } from './alertsAdapters';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
// 🔥 FIX: Hamesha API call karega, mock completely disable kar diya
const USE_MOCK = false;

const NETWORK_DELAY_MS = 450;

// 🚀 ALERTS CACHE & PROMISE TRACKER
let globalAlertsCache: SosAlert[] | null = null;
let lastAlertsFetchTime = 0;
let alertsFetchPromise: Promise<SosAlert[]> | null = null;

// 🚀 NOTIFICATIONS CACHE & PROMISE TRACKER
let globalNotificationCache: NotificationState | null = null;
let lastNotificationFetchTime = 0;
let notificationFetchPromise: Promise<NotificationState> | null = null;

const CACHE_DURATION_MS = 3000; // 3 seconds

function delay<T>(value: T, ms = NETWORK_DELAY_MS): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export async function fetchAlerts(clusters: ThermalCluster[]): Promise<SosAlert[]> {
  if (USE_MOCK) return delay(mockAlerts);

  // Background fetch logic (0s delay par chalega)
  const backgroundFetch = async () => {
    if (alertsFetchPromise) return alertsFetchPromise;
    alertsFetchPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/alerts`);
        if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`);
        
        const body = (await res.json()) as BackendAlert[];
        const alerts = toSosAlerts(body, clusters);
        
        globalAlertsCache = alerts;
        lastAlertsFetchTime = Date.now();
        
        return alerts;
      } finally {
        alertsFetchPromise = null;
      }
    })();
    return alertsFetchPromise;
  };

  // ⚡ SUPER FAST LOAD: Agar cache hai toh instantly page dikhao
  if (globalAlertsCache) {
    if (Date.now() - lastAlertsFetchTime > CACHE_DURATION_MS) {
      backgroundFetch(); // Naya data chupke se laao
    }
    return globalAlertsCache;
  }

  return backgroundFetch();
}

export async function fetchNotificationState(): Promise<NotificationState> {
  if (USE_MOCK) {
    const activeCritical = mockAlerts.filter((a) => a.status === 'active').length;
    return delay({ hasUnread: activeCritical > 0, unreadCount: activeCritical });
  }

  const backgroundFetch = async () => {
    if (notificationFetchPromise) return notificationFetchPromise;
    notificationFetchPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/alerts/notifications`);
        if (!res.ok) throw new Error(`Failed to fetch notification state: ${res.status}`);
        
        const data = await res.json();
        
        globalNotificationCache = data;
        lastNotificationFetchTime = Date.now();
        
        return data;
      } finally {
        notificationFetchPromise = null;
      }
    })();
    return notificationFetchPromise;
  };

  if (globalNotificationCache) {
    if (Date.now() - lastNotificationFetchTime > CACHE_DURATION_MS) {
      backgroundFetch();
    }
    return globalNotificationCache;
  }

  return backgroundFetch();
}