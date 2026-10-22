interface Props {
  label: string
  value: number | string
  sub?: string
  color?: string
}

export function StatCard({ label, value, sub, color = 'text-brand' }: Props) {
  return (
    <div className="card flex flex-col gap-1">
      <p className="text-mute text-xs uppercase tracking-widest">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-mute text-xs">{sub}</p>}
    </div>
  )
}
