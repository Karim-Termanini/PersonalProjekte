import type { ContainerRow, NetworkRow } from '@linux-dev-home/shared'
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect } from 'react'

type SchemeProps = {
  containers: ContainerRow[]
  networks: NetworkRow[]
}



function ContainerNode({ data }: { data: ContainerRow }) {
  const isRunning = data.state.toLowerCase() === 'running'
  return (
    <div
      style={{
        background: 'var(--bg-input)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 16,
        width: 260,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: 'var(--accent)' }} />
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            flexShrink: 0,
            marginTop: 4,
            background: isRunning ? 'var(--green)' : 'var(--text-muted)',
          }}
          title={data.state}
        />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 15,
              marginBottom: 4,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={data.name}
          >
            {data.name}
          </div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={data.image}
          >
            {data.image}
          </div>
        </div>
      </div>

      {data.ports !== '—' && (
        <div
          className="mono"
          style={{
            fontSize: 11,
            background: 'var(--bg)',
            padding: '6px 8px',
            borderRadius: 6,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={data.ports}
        >
          {data.ports}
        </div>
      )}
      {data.networks && data.networks.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {data.networks.slice(0, 3).map((n) => (
            <span
              key={n}
              className="mono"
              style={{ fontSize: 10, border: '1px solid var(--border)', borderRadius: 999, padding: '2px 6px' }}
            >
              net:{n}
            </span>
          ))}
        </div>
      ) : null}
      {data.volumes && data.volumes.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {data.volumes.slice(0, 2).map((v) => (
            <span
              key={v}
              className="mono"
              style={{ fontSize: 10, border: '1px solid var(--border)', borderRadius: 999, padding: '2px 6px' }}
            >
              vol:{v}
            </span>
          ))}
        </div>
      ) : null}
      <Handle type="source" position={Position.Bottom} style={{ background: 'var(--accent)' }} />
    </div>
  )
}

function NetworkNode({ data }: { data: NetworkRow }) {
  const isSystem = data.name === 'bridge' || data.name === 'host' || data.name === 'none'
  return (
    <div
      style={{
        background: isSystem ? 'var(--bg-widget)' : 'var(--accent)',
        color: isSystem ? 'var(--text)' : '#fff',
        border: `1px solid ${isSystem ? 'var(--border)' : 'var(--accent)'}`,
        borderRadius: 8,
        padding: '8px 16px',
        fontWeight: 600,
        fontSize: 14,
        textAlign: 'center',
        boxShadow: '0 4px 8px rgba(0,0,0,0.2)',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      {data.name}
      <div style={{ fontSize: 10, opacity: 0.8, marginTop: 2 }}>{data.driver}</div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  )
}

const nodeTypes = {
  containerNode: ContainerNode,
  networkNode: NetworkNode,
}

export function DockerSchemeView({ containers, networks }: SchemeProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    const newNodes: Node[] = []
    const newEdges: Edge[] = []

    const x = 100
    const startY = 50

    // Build Network Nodes
    networks.forEach((net, i) => {
      newNodes.push({
        id: `net-${net.name}`,
        type: 'networkNode',
        position: { x: x + i * 200, y: startY },
        data: net,
      })
    })

    // Build Container Nodes
    containers.forEach((c, i) => {
      newNodes.push({
        id: `cont-${c.id}`,
        type: 'containerNode',
        position: { x: 100 + i * 320, y: startY + 200 },
        data: c,
      })

      // Edges to networks
      if (c.networks) {
        c.networks.forEach((netName) => {
          newEdges.push({
            id: `e-${c.id}-${netName}`,
            source: `net-${netName}`,
            target: `cont-${c.id}`,
            animated: c.state.toLowerCase() === 'running',
            style: { stroke: 'var(--accent)', strokeWidth: 2 },
          })
        })
      }
    })

    setNodes(newNodes)
    setEdges(newEdges)
  }, [containers, networks, setNodes, setEdges])

  return (
    <div style={{ width: '100%', height: 'calc(100vh - 200px)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        colorMode="dark"
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  )
}
