import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface Resource {
  name: string
  count: number
  status: string
}

interface Props {
  resources: Resource[]
}

const COLORS: Record<string, string> = {
  available: '#34D399',
  deployed: '#FBBF24',
}

export function ResourceChart({ resources }: Props) {
  const data = resources.map(r => ({
    name: r.name.length > 18 ? r.name.slice(0, 18) + '…' : r.name,
    count: r.count,
    status: r.status,
  }))

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 4 }}>
        <XAxis dataKey="name" tick={{ fill: '#8D9AB5', fontSize: 10 }} />
        <YAxis tick={{ fill: '#8D9AB5', fontSize: 10 }} />
        <Tooltip
          contentStyle={{ background: '#121A2E', border: '1px solid #223052', borderRadius: 8 }}
          labelStyle={{ color: '#E7ECF6' }}
          itemStyle={{ color: '#E7ECF6' }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={COLORS[entry.status] ?? '#8D9AB5'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
