import { useState, useEffect, useRef } from 'react'

function Chat({ messages, onSend, onStop, loading, responseTime, elapsed }) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, elapsed])

  function handleSubmit(e) {
    e.preventDefault()
    if (input.trim() && !loading) {
      onSend(input.trim())
      setInput('')
    }
  }

  function formatTime(seconds) {
    if (seconds < 60) return `${seconds.toFixed(1)}秒`
    const m = Math.floor(seconds / 60)
    const s = (seconds % 60).toFixed(0)
    return `${m}分${s}秒`
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-lg">开始对话吧</p>
            <p className="text-sm mt-2">输入消息，Agent 会调用工具帮你完成任务</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.type === 'human' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] rounded-lg px-4 py-2 ${
                msg.type === 'human'
                  ? 'bg-blue-500 text-white'
                  : 'bg-white border border-gray-200 text-gray-800'
              }`}
            >
              {msg.content && (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}
              {msg.tool_calls && msg.tool_calls.length > 0 && (
                <div className="mt-2 text-sm opacity-75">
                  ️ 调用工具：{msg.tool_calls.map(tc => tc.name || tc.function?.name).filter(Boolean).join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start items-center space-x-2">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
              <div className="flex space-x-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
            {elapsed !== null && (
              <span className="text-xs text-gray-400 font-mono">
                {formatTime(elapsed)}
              </span>
            )}
            {onStop && (
              <button
                onClick={onStop}
                className="text-xs px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
              >
                停止
              </button>
            )}
          </div>
        )}

        {!loading && responseTime && (
          <div className="flex justify-start">
            <div className="text-xs text-gray-400 px-4 py-1">
              ️ 响应时间：{responseTime}秒
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white p-4">
        <form onSubmit={handleSubmit} className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={loading ? 'Agent 正在处理...' : '输入消息...'}
            disabled={loading}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
          />
          {loading ? (
            <button
              type="button"
              onClick={onStop}
              className="px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
            >
              停止
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              发送
            </button>
          )}
        </form>
      </div>
    </div>
  )
}

export default Chat
