'use client';

type DeviceCardProps = {
  device_id?: string;
};

export function DeviceCard(props: DeviceCardProps) {
  const hasDeviceId = !!props.device_id;

  return (
    <div
      className={`rounded-xl border border-dashed p-4 transition ${
        hasDeviceId
          ? 'border-border bg-primary/5 hover:bg-primary/10'
          : 'border-border/30 opacity-50'
      }`}
    >
      <p className="text-sm font-medium">DEVICE</p>
    </div>
  );
}

