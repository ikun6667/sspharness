const API_BASE = '/api'

export async function sendMessage(message, signal) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })
  return res
}

export async function getSession() {
  const res = await fetch(`${API_BASE}/session`)
  return res.json()
}

export async function listFiles(path = '.') {
  const res = await fetch(`${API_BASE}/files?path=${path}`)
  return res.json()
}

export async function readFile(path) {
  const res = await fetch(`${API_BASE}/files/${path}`)
  return res.json()
}

export async function handlePermission(approved) {
  const res = await fetch(`${API_BASE}/permission`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved }),
  })
  return res.json()
}

export async function listProjects() {
  const res = await fetch(`${API_BASE}/projects`)
  return res.json()
}

export async function saveProject(name, workspace) {
  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, workspace }),
  })
  return res.json()
}

export async function loadProject(name) {
  const res = await fetch(`${API_BASE}/projects/load`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  return res.json()
}

export async function getContextLength() {
  const res = await fetch(`${API_BASE}/context-length`)
  return res.json()
}

export async function listMCPServers() {
  const res = await fetch(`${API_BASE}/mcp/servers`)
  return res.json()
}

export async function addMCPServer(config) {
  const res = await fetch(`${API_BASE}/mcp/servers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  return res.json()
}

export async function removeMCPServer(name) {
  const res = await fetch(`${API_BASE}/mcp/servers/${name}`, {
    method: 'DELETE',
  })
  return res.json()
}

export async function listTasks() {
  const res = await fetch(`${API_BASE}/tasks`)
  return res.json()
}

export async function createTask(subject, workspace = '.') {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, workspace }),
  })
  return res.json()
}

export async function loadTask(taskId) {
  const res = await fetch(`${API_BASE}/tasks/load`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: taskId }),
  })
  return res.json()
}

export async function saveTask() {
  const res = await fetch(`${API_BASE}/tasks/save`, {
    method: 'POST',
  })
  return res.json()
}

export async function stopTask(taskId) {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/stop`, {
    method: 'POST',
  })
  return res.json()
}
