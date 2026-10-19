function ToolLog({ events }) {
  if (events.length === 0) {
    return (
      <div className="p-4 border-t border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">🔨 工具调用</h3>
        <p className="text-xs text-gray-400">暂无工具调用</p>
      </div>
    )
  }

  return (
    <div className="p-4 border-t border-gray-200">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">🔨 工具调用</h3>
      <div className="space-y-2">
        {events.map((event, i) => (
          <div key={i} className="text-xs bg-gray-50 p-2 rounded">
            <div className="font-medium text-gray-700">
              {event.type === 'tool' ? '🛠️' : ''} {event.name || event.type}
            </div>
            {event.content && (
              <div className="mt-1 text-gray-600 truncate">
                {typeof event.content === 'string' ? event.content.slice(0, 100) : '...'}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default ToolLog
