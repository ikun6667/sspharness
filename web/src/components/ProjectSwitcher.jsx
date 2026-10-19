import { useState, useEffect } from 'react'
import { listProjects } from '../api'

function ProjectSwitcher({ onLoad, onSave }) {
  const [projects, setProjects] = useState([])
  const [newProjectName, setNewProjectName] = useState('')

  useEffect(() => {
    loadProjects()
  }, [])

  async function loadProjects() {
    try {
      const list = await listProjects()
      setProjects(list)
    } catch (e) {
      console.error('Failed to load projects:', e)
    }
  }

  function handleSave() {
    if (newProjectName.trim()) {
      onSave(newProjectName.trim())
      setNewProjectName('')
      loadProjects()
    }
  }

  return (
    <div className="p-4 border-b border-gray-200 bg-gray-50">
      <h3 className="text-sm font-semibold text-gray-700 mb-2"> 项目管理</h3>

      {/* Save new project */}
      <div className="flex space-x-2 mb-3">
        <input
          type="text"
          value={newProjectName}
          onChange={(e) => setNewProjectName(e.target.value)}
          placeholder="新项目名..."
          className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded"
        />
        <button
          onClick={handleSave}
          className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          保存
        </button>
      </div>

      {/* Project list */}
      {projects.length > 0 && (
        <div className="space-y-1">
          {projects.map((project) => (
            <button
              key={project.name}
              onClick={() => onLoad(project.name)}
              className="w-full text-left px-2 py-1 text-xs text-gray-700 hover:bg-gray-200 rounded flex justify-between"
            >
              <span>{project.name}</span>
              <span className="text-gray-400">{project.workspace}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default ProjectSwitcher
