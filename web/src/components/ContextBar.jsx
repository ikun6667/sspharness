function ContextBar({ contextLength }) {
  const { tokens, percentage } = contextLength
  const isWarning = percentage > 80
  const isCritical = percentage > 95

  return (
    <div className={`p-3 border-t border-gray-200 ${isCritical ? 'bg-red-50' : isWarning ? 'bg-yellow-50' : 'bg-white'}`}>
      <div className="flex justify-between items-center text-xs">
        <span className="text-gray-600"> 上下文长度</span>
        <span className={`font-mono ${isCritical ? 'text-red-600' : isWarning ? 'text-yellow-600' : 'text-gray-700'}`}>
          {tokens.toLocaleString()} tokens
        </span>
      </div>
      <div className="mt-1 w-full bg-gray-200 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${isCritical ? 'bg-red-500' : isWarning ? 'bg-yellow-500' : 'bg-blue-500'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        ></div>
      </div>
      <div className="mt-1 text-xs text-gray-500 text-right">
        {percentage.toFixed(1)}% / 100K
      </div>
    </div>
  )
}

export default ContextBar
