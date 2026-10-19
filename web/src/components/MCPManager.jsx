import { useState, useEffect } from 'react'
import { listMCPServers, addMCPServer, removeMCPServer } from '../api'

function MCPManager() {
  const [servers, setServers] = useState([])
  const [showAddForm, setShowAddForm] = useState(false)
  const [newServer, setNewServer] = useState({
    name: '',
    transport: 'stdio',
    command: '',
    args: '',
    url: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadServers()
  }, [])

  async function loadServers() {
    try {
      const list = await listMCPServers()
      setServers(list)
      setError(null)
    } catch (e) {
      console.error('Failed to load MCP servers:', e)
      setError('加载失败')
    }
  }

  async function handleAdd() {
    if (!newServer.name.trim()) {
      setError('请输入服务器名称')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const config = {
        name: newServer.name.trim(),
        transport: newServer.transport,
      }

      if (newServer.transport === 'stdio') {
        if (!newServer.command.trim()) {
          setError('请输入命令')
          setLoading(false)
          return
        }
        config.command = newServer.command.trim()
        config.args = newServer.args.split(' ').filter(a => a.trim())
      } else if (newServer.transport === 'sse') {
        if (!newServer.url.trim()) {
          setError('请输入URL')
          setLoading(false)
          return
        }
        config.url = newServer.url.trim()
      }

      const result = await addMCPServer(config)

      if (result.status === 'connected') {
        setNewServer({ name: '', transport: 'stdio', command: '', args: '', url: '' })
        setShowAddForm(false)
        await loadServers()
      } else {
        setError(result.error || '连接失败')
      }
    } catch (e) {
      setError('添加失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRemove(name) {
    if (!confirm(`确定要断开 ${name} 吗？`)) return

    setLoading(true)
    try {
      await removeMCPServer(name)
      await loadServers()
    } catch (e) {
      setError('删除失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 border-b border-gray-200 bg-gray-50">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-semibold text-gray-700"> MCP 服务器</h3>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="text-xs px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          {showAddForm ? '取消' : '添加'}
        </button>
      </div>

      {error && (
        <div className="text-xs text-red-600 mb-2 p-2 bg-red-50 rounded">
          {error}
        </div>
      )}

      {showAddForm && (
        <div className="mb-3 p-2 bg-white rounded border border-gray-200 space-y-2">
          <input
            type="text"
            value={newServer.name}
            onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
            placeholder="服务器名称..."
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
          />

          <select
            value={newServer.transport}
            onChange={(e) => setNewServer({ ...newServer, transport: e.target.value })}
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
          >
            <option value="stdio">Stdio (本地命令)</option>
            <option value="sse">SSE (远程URL)</option>
          </select>

          {newServer.transport === 'stdio' ? (
            <>
              <input
                type="text"
                value={newServer.command}
                onChange={(e) => setNewServer({ ...newServer, command: e.target.value })}
                placeholder="命令 (如: npx, python)..."
                className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
              />
              <input
                type="text"
                value={newServer.args}
                onChange={(e) => setNewServer({ ...newServer, args: e.target.value })}
                placeholder="参数 (空格分隔)..."
                className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
              />
            </>
          ) : (
            <input
              type="text"
              value={newServer.url}
              onChange={(e) => setNewServer({ ...newServer, url: e.target.value })}
              placeholder="SSE URL (如: http://localhost:3001/sse)..."
              className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
            />
          )}

          <button
            onClick={handleAdd}
            disabled={loading}
            className="w-full px-3 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300"
          >
            {loading ? '连接中...' : '连接'}
          </button>
        </div>
      )}

      {servers.length > 0 ? (
        <div className="space-y-1">
          {servers.map((server) => (
            <div
              key={server.name}
              className="flex justify-between items-center px-2 py-1 text-xs bg-white rounded border border-gray-200"
            >
              <div className="flex-1">
                <div className="font-medium text-gray-800">{server.name}</div>
                <div className="text-gray-500">
                  {server.transport}
                  {server.connected && (
                    <span className="ml-2 text-green-600">● 已连接</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleRemove(server.name)}
                disabled={loading}
                className="text-red-500 hover:text-red-700 disabled:text-gray-300"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-gray-500 text-center py-2">
          暂无 MCP 服务器
        </div>
      )}
    </div>
  )
}

export default MCPManager
