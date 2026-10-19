import { useState, useEffect } from 'react'
import { listTasks, createTask, loadTask } from '../api'

function TaskList({ onLoad, onCreate, currentTaskId }) {
  const [tasks, setTasks] = useState([])
  const [newTaskSubject, setNewTaskSubject] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadTasks()
  }, [])

  async function loadTasks() {
    try {
      const list = await listTasks()
      setTasks(list)
    } catch (e) {
      console.error('Failed to load tasks:', e)
    }
  }

  async function handleCreate() {
    if (!newTaskSubject.trim()) return

    setLoading(true)
    try {
      const task = await createTask(newTaskSubject.trim(), '.')
      setNewTaskSubject('')
      await loadTasks()
      // Auto-load the new task
      await handleLoad(task.id)
    } catch (e) {
      console.error('Failed to create task:', e)
    } finally {
      setLoading(false)
    }
  }

  async function handleLoad(taskId) {
    try {
      const result = await loadTask(taskId)
      // Pass the full result so App can access session data
      onLoad(taskId, result)
    } catch (e) {
      console.error('Failed to load task:', e)
    }
  }

  function getStatusIcon(status) {
    switch (status) {
      case 'completed': return '✓'
      case 'in_progress': return '▶'
      default: return '○'
    }
  }

  function getStatusColor(status) {
    switch (status) {
      case 'completed': return 'text-green-600'
      case 'in_progress': return 'text-blue-600'
      default: return 'text-gray-400'
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now - date

    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
    return date.toLocaleDateString('zh-CN')
  }

  return (
    <div className="p-4 border-b border-gray-200 bg-gray-50">
      <h3 className="text-sm font-semibold text-gray-700 mb-2"> 任务列表</h3>

      {/* Create new task */}
      <div className="flex space-x-2 mb-3">
        <input
          type="text"
          value={newTaskSubject}
          onChange={(e) => setNewTaskSubject(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleCreate()}
          placeholder="新任务..."
          className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded"
        />
        <button
          onClick={handleCreate}
          disabled={loading}
          className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
        >
          创建
        </button>
      </div>

      {/* Task list */}
      {tasks.length > 0 ? (
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {tasks.map((task) => {
            const isSelected = task.id === currentTaskId
            return (
              <button
                key={task.id}
                onClick={() => handleLoad(task.id)}
                className={`w-full text-left px-2 py-2 text-xs rounded border transition-colors ${
                  isSelected
                    ? 'bg-blue-50 border-blue-300 text-blue-900'
                    : 'bg-white hover:bg-gray-100 border-gray-200 text-gray-700'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-1">
                      <span className={`${getStatusColor(task.status)} font-bold`}>
                        {getStatusIcon(task.status)}
                      </span>
                      <span className={`font-medium truncate ${isSelected ? 'text-blue-900' : 'text-gray-800'}`}>
                        {task.subject}
                      </span>
                      {isSelected && (
                        <span className="text-xs text-blue-600 ml-auto">当前</span>
                      )}
                    </div>
                    <div className="text-gray-500 text-xs mt-0.5 ml-4">
                      {task.workspace !== '.' && (
                        <span className="mr-2">📁 {task.workspace}</span>
                      )}
                      <span>{formatDate(task.created_at)}</span>
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      ) : (
        <div className="text-xs text-gray-500 text-center py-2">
          暂无任务，创建一个开始吧
        </div>
      )}
    </div>
  )
}

export default TaskList
