import type { Esp32Telemetry } from '@/types/cluster';
import { SensorIcon } from '@/components/dashboard/icons';
import { formatTemperature, formatHumidity } from '@/lib/utils';

interface EspTelemetryCardProps {
  esp32: Esp32Telemetry | null;
  espData?: any;
  isGroundNode?: boolean;
}

export function EspTelemetryCard({ esp32, espData, isGroundNode }: EspTelemetryCardProps) {
  const isLive = isGroundNode && espData && espData.temperature !== undefined;

  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5">
        <SensorIcon className="h-3.5 w-3.5 text-ink-400" />
        <span className="font-mono text-[9px] font-bold uppercase tracking-[0.08em] text-ink-400">
          Ground sensor &middot; ESP32 {isLive ? " (LIVE)" : ""}
        </span>
      </div>
      
      {isLive ? (
        <div className="grid grid-cols-3 gap-2">
          {/* Original 6 Parameters */}
          <Stat label="Temperature" value={`${Number(espData.temperature).toFixed(1)}°C`} />
          <Stat label="Humidity" value={`${Number(espData.humidity).toFixed(1)}%`} />
          <Stat label="Flame" value={espData.flame_detected ? 'Yes' : 'No'} />
          <Stat label="PM 2.5" value={`${espData.pm25}`} />
          <Stat label="Wind Speed" value={`${espData.wind_speed} m/s`} />
          <Stat label="Pressure" value={`${espData.pressure} hPa`} />
          
          {/* Newly Added 5 Parameters */}
          <Stat label="PM 10" value={`${espData.pm10}`} />
          <Stat label="Smoke PPM" value={`${espData.smoke_ppm}`} />
          <Stat label="Wind Dir" value={`${espData.wind_direction}`} />
          <Stat label="Rainfall" value={`${espData.rainfall} mm`} />
          <Stat label="Time" value={`${espData.timestamp || 'N/A'}`} />
        </div>
      ) : esp32 ? (
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Temperature" value={formatTemperature(esp32.temperature_c)} />
          <Stat label="Humidity" value={formatHumidity(esp32.humidity_pct)} />
          <Stat label="Smoke level" value={esp32.smoke_level ? String(esp32.smoke_level) : "—"} />
        </div>
      ) : (
        <div className="flex h-12 items-center justify-center rounded-md border border-base-700 bg-base-950 px-2 text-center">
          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-400">
            ESP Not Installed
          </span>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-base-700 bg-base-950 px-2 py-2 text-center">
      <div className="font-mono text-[8px] uppercase leading-[1.3] tracking-[0.06em] text-ink-400">{label}</div>
      <div className="mt-1 font-mono text-[14px] font-bold leading-none text-accent-dark">{value}</div>
    </div>
  );
}