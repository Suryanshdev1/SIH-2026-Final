import { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, Marker, Popup } from 'maplibre-gl';
import { createRoot, type Root } from 'react-dom/client';
import type { ThermalCluster } from '@/types/cluster';
import { riskDotColor } from '@/components/risk/RiskBadge';
import { HoverCard } from './HoverCard';
import { SATELLITE_TERRAIN_STYLE } from '@/lib/mapStyle';

interface MapViewProps {
  clusters: ThermalCluster[];
  selectedClusterId: string | null;
  onSelectCluster: (clusterId: string) => void;
}

export function MapView({ clusters, selectedClusterId, onSelectCluster }: MapViewProps) {
  console.log("📡 Frontend Map Clusters:", clusters); // YEH NAYI LINE DAAL
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Map<string, Marker>>(new Map());
  const popupRef = useRef<Popup | null>(null);
  const popupRootRef = useRef<Root | null>(null);
  const [mapReady, setMapReady] = useState(false);

  // Initialize the map once.
  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_TERRAIN_STYLE,
      center: [20, 15],
      zoom: 1.6,
      minZoom: 1,
      maxZoom: 18,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }));

    map.on('load', () => {
      setMapReady(true);
    });

    mapRef.current = map;
    const markers = markersRef.current;

    return () => {
      markers.forEach((m) => m.remove());
      markers.clear();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Sync markers whenever the filtered cluster list changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const currentIds = new Set(clusters.map((c) => c.cluster_id));

    // Remove markers no longer present.
    markersRef.current.forEach((marker, id) => {
      if (!currentIds.has(id)) {
        marker.remove();
        markersRef.current.delete(id);
      }
    });

    clusters.forEach((cluster) => {
      const existing = markersRef.current.get(cluster.cluster_id);
      const isSelected = cluster.cluster_id === selectedClusterId;
      
      // ✅ Check if this is our dummy ESP32 ground node
      const isGroundNode = cluster.cluster_id === 'NODE_SMB_01';
      const markerColor = isGroundNode ? '#3b82f6' : riskDotColor(cluster.risk_level);

      if (existing) {
        const el = existing.getElement();
        el.style.setProperty('--marker-color', markerColor);
        el.classList.toggle('is-selected', isSelected);
        if (isGroundNode) el.classList.add('is-ground-node');
        return;
      }

      const el = document.createElement('button');
      el.type = 'button';
      el.setAttribute('aria-label', `Cluster ${cluster.cluster_id}, ${cluster.risk_level} risk`);
      el.className = 'ts-marker';
      el.style.setProperty('--marker-color', markerColor);
      
      if (isSelected) el.classList.add('is-selected');
      if (isGroundNode) el.classList.add('is-ground-node'); // ✅ Blue marker class

      el.addEventListener('mouseenter', () => {
        showHoverPopup(map, popupRef, popupRootRef, cluster);
      });
      el.addEventListener('mouseleave', () => {
        closeHoverPopup(popupRef, popupRootRef);
      });
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        onSelectCluster(cluster.cluster_id);
      });

      // ✅ Use lat/lon directly for ground node, otherwise use centroid
      const lng = cluster.centroid.lon;
      const lat = cluster.centroid.lat;

      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([lng, lat])
        .addTo(map);

      markersRef.current.set(cluster.cluster_id, marker);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusters, mapReady, selectedClusterId]);

  // Smoothly fly to the selected cluster.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !selectedClusterId) return;

    const target = clusters.find((c) => c.cluster_id === selectedClusterId);
    if (!target) return;
    
    // YAHAN FIX KIYA HAI: 'cluster' ki jagah 'target' use karna hai
    const isGroundNode = target.cluster_id === 'NODE_SMB_01';
    
    const lng = target.centroid.lon;
    const lat = target.centroid.lat;

    map.flyTo({
      center: [lng, lat],
      zoom: Math.max(map.getZoom(), 4.5),
      speed: 0.9,
      curve: 1.4,
      essential: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClusterId, mapReady]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      <style>{`
        .ts-marker {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          background-color: var(--marker-color, #f97316);
          border: 2px solid #ffffff;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
          cursor: pointer;
          padding: 0;
          transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .ts-marker:hover {
          transform: scale(1.4);
        }
        .ts-marker.is-selected {
          box-shadow: 0 0 0 3px rgba(230, 57, 70, 0.4);
          transform: scale(1.3);
        }
        /* ✅ Special styling for ESP32 Ground Node */
        .ts-marker.is-ground-node {
          border: 2px solid #ffffff;
          box-shadow: 0 0 8px rgba(59, 130, 246, 0.8), 0 0 0 3px rgba(59, 130, 246, 0.3);
          animation: pulse-blue 2s infinite;
        }
        .ts-marker.is-ground-node.is-selected {
          box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.5);
        }
        @keyframes pulse-blue {
          0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
          70% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
          100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
        }
      `}</style>
    </div>
  );
}

function closeHoverPopup(
  popupRef: React.MutableRefObject<Popup | null>,
  popupRootRef: React.MutableRefObject<Root | null>
) {
  popupRef.current?.remove();
  popupRef.current = null;
  const rootToUnmount = popupRootRef.current;
  popupRootRef.current = null;
  if (rootToUnmount) {
    setTimeout(() => rootToUnmount.unmount(), 0);
  }
}

function showHoverPopup(
  map: MapLibreMap,
  popupRef: React.MutableRefObject<Popup | null>,
  popupRootRef: React.MutableRefObject<Root | null>,
  cluster: ThermalCluster
) {
  closeHoverPopup(popupRef, popupRootRef);

  const isGroundNode = cluster.cluster_id === 'NODE_SMB_01';
  const lng = cluster.centroid.lon;
  const lat = cluster.centroid.lat;

  const container = document.createElement('div');
  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 14 })
    .setLngLat([lng, lat])
    .setDOMContent(container)
    .addTo(map);

  popupRootRef.current = createRoot(container);
  popupRootRef.current.render(<HoverCard cluster={cluster} />);
  popupRef.current = popup;
}