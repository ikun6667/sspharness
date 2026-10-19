import { useState, useEffect, useRef, useCallback } from 'react'
import {
  sendMessage, getSession, listFiles, readFile,
  listTasks, createTask, loadTask, saveTask, getContextLength, stopTask
} from './api'
import Chat from './components/Chat'
import FileTree from './components/FileTree'
import ToolLog from './components/ToolLog'
import TaskList from './components/TaskList'
import ContextBar from './components/ContextBar'
import MCPManager from './components/MCPManager'

function App() {
  const [messages, setMessages] = useState([])
  const [files, setFiles] = useState([])
  const [toolEvents, setToolEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [contextLength, setContextLength] = useState({ tokens: 0, percentage: 0 })
  const [showTaskList, setShowTaskList] = useState(true)
  const [showMCPManager, setShowMCPManager] = useState(false)
  const [currentTaskId, setCurrentTaskId] = useState(null)
  const [currentPath, setCurrentPath] = useState('.')
  const [responseTime, setResponseTime] = useState(null)
  const [elapsed, setElapsed] = useState(null)

  const abortRef = useRef(null)
  const timerRef = useRef(null)
  const startRef = useRef(null)

  useEffect(() => {
    loadSession()
    loadFiles()
    updateContextLength()
  }, [])

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  async function loadSession() {
    try {
      const session = await getSession()
      setMessages(session.messages || [])
      setToolEvents(session.tool_events || [])
    } catch (e) {
      console.error('Failed to load session:', e)
    }
  }

  async function loadFiles(path = '.') {
    try {
      const entries = await listFiles(path)
      setFiles(entries)
    } catch (e) {
      console.error('Failed to load files:', e)
    }
  }

  async function updateContextLength() {
    try {
      const length = await getContextLength()
      setContextLength(length)
    } catch (e) {
      console.error('Failed to get context length:', e)
    }
  }

  function startTimer() {
    startRef.current = Date.now()
    setElapsed(0)
    timerRef.current = setInterval(() => {
      setElapsed((Date.now() - startRef.current) / 1000)
    }, 100)
  }

  function stopTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (startRef.current) {
      const duration = ((Date.now() - startRef.current) / 1000).toFixed(2)
      setResponseTime(duration)
    }
    setElapsed(null)
  }

  async function handleSend(message) {
    setLoading(true)
    setResponseTime(null)
    startTimer()
    setMessages(prev => [...prev, { type: 'human', content: message }])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await sendMessage(message, controller.signal)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'message') {
              setMessages(prev => [...prev, data.data])
            } else if (data.type === 'tool_result') {
              setToolEvents(prev => [...prev, data.data])
            } else if (data.type === 'done') {
              stopTimer()
              setLoading(false)
              abortRef.current = null
              updateContextLength()
              if (currentTaskId) {
                await saveTask()
              }
            } else if (data.type === 'error') {
              console.error('Agent error:', data.data)
              stopTimer()
              setLoading(false)
              abortRef.current = null
            } else if (data.type === 'stopped') {
              stopTimer()
              setLoading(false)
              abortRef.current = null
            }
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        // User cancelled
        stopTimer()
        setLoading(false)
        abortRef.current = null
      } else {
        console.error('Failed to send message:', e)
        stopTimer()
        setLoading(false)
        abortRef.current = null
      }
    }
  }

  async function handleStop() {
    // Abort the fetch request on frontend
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    // Notify backend to stop
    if (currentTaskId) {
      try {
        await stopTask(currentTaskId)
      } catch (e) {
        console.error('Failed to stop task:', e)
      }
    }
    stopTimer()
    setLoading(false)
  }

  async function handleFileClick(file) {
    if (file.is_dir) {
      setCurrentPath(file.path)
      loadFiles(file.path)
    } else {
      try {
        const result = await readFile(file.path)
        setSelectedFile(file.path)
        setFileContent(result.content)
      } catch (e) {
        console.error('Failed to read file:', e)
      }
    }
  }

  async function handleNavigate(path) {
    setCurrentPath(path)
    await loadFiles(path)
  }

  async function handleLoadTask(taskId, result) {
    // Allow free task switching - just switch the view
    try {
      setCurrentTaskId(taskId)
      setResponseTime(null)
      setElapsed(null)
      if (result && result.session) {
        setMessages(result.session.messages || [])
        setToolEvents(result.session.tool_events || [])
        setCurrentPath('.')
        await loadFiles()
        updateContextLength()
      } else {
        await loadSession()
        await loadFiles()
        updateContextLength()
      }
    } catch (e) {
      console.error('Failed to load task:', e)
    }
  }

  async function handleCreateTask(subject) {
    try {
      const task = await createTask(subject, '.')
      setCurrentTaskId(task.id)
      await loadSession()
      await loadFiles()
    } catch (e) {
      console.error('Failed to create task:', e)
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-lg font-bold text-gray-800">LangGraph Harness</h1>
          <div className="flex space-x-2 mt-2">
            <button
              onClick={() => setShowTaskList(!showTaskList)}
              className="text-xs text-blue-500 hover:text-blue-700"
            >
              任务列表
            </button>
            <button
              onClick={() => setShowMCPManager(!showMCPManager)}
              className="text-xs text-blue-500 hover:text-blue-700"
            >
              MCP
            </button>
          </div>
        </div>

        {showTaskList && (
          <TaskList
            onLoad={handleLoadTask}
            onCreate={handleCreateTask}
            currentTaskId={currentTaskId}
          />
        )}

        {showMCPManager && (
          <MCPManager />
        )}

        <div className="flex-1 overflow-y-auto">
          <FileTree
            files={files}
            onFileClick={handleFileClick}
            currentPath={currentPath}
            onNavigate={handleNavigate}
          />
          <ToolLog events={toolEvents} />
        </div>

        <ContextBar contextLength={contextLength} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        <Chat
          messages={messages}
          onSend={handleSend}
          onStop={loading ? handleStop : null}
          loading={loading}
          responseTime={responseTime}
          elapsed={elapsed}
        />

        {selectedFile && (
          <div className="border-t border-gray-200 bg-white p-4 max-h-64 overflow-y-auto">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-gray-600">{selectedFile}</span>
              <button
                onClick={() => setSelectedFile(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                
              </button>
            </div>
            <pre className="text-sm bg-gray-50 p-3 rounded overflow-x-auto">
              {fileContent}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
