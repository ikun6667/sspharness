import { useState } from 'react'

function FileTree({ files, onFileClick, currentPath, onNavigate }) {
  if (files.length === 0) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">📁 文件浏览器</h3>
        <p className="text-xs text-gray-400">暂无文件</p>
      </div>
    )
  }

  // Calculate parent path for navigation
  const getParentPath = () => {
    if (currentPath === '.') return null
    const parts = currentPath.split('/')
    parts.pop()
    return parts.length === 0 ? '.' : parts.join('/')
  }

  const parentPath = getParentPath()

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-700">📁 文件浏览器</h3>
        {parentPath !== null && (
          <button
            onClick={() => onNavigate(parentPath)}
            className="text-xs text-blue-500 hover:text-blue-700 px-2 py-1 rounded hover:bg-gray-100"
          >
            ← 返回
          </button>
        )}
      </div>

      {currentPath !== '.' && (
        <div className="text-xs text-gray-500 mb-2 px-2 py-1 bg-gray-100 rounded">
          📂 {currentPath}
        </div>
      )}

      <div className="space-y-1">
        {files.map((file) => (
          <button
            key={file.path}
            onClick={() => onFileClick(file)}
            className="w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 rounded flex items-center"
          >
            <span className="mr-2">{file.is_dir ? '📂' : ''}</span>
            <span className="truncate">{file.name}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default FileTree
