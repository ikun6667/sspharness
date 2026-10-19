"""LangGraph Harness — 精美前端 (DeepSeek Harness 风格)

Run:
    cd langgraph-harness
    streamlit run ui/app.py
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import streamlit as st

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(_project_root))

from ui.agent_runner import AgentRunner, InterruptInfo


# 持久化事件循环
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def get_runner() -> AgentRunner:
    if "runner" not in st.session_state:
        st.session_state.runner = AgentRunner(workspace=".")
    return st.session_state.runner


@st.dialog("⚠️ 权限确认")
def permission_dialog(info: InterruptInfo):
    st.markdown(f"**{info.message}**")
    st.json({"工具": info.tool_name, "输入": info.tool_input})
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 允许执行", use_container_width=True, type="primary"):
            st.session_state.permission_decision = True
            st.rerun()
    with col2:
        if st.button("❌ 拒绝执行", use_container_width=True):
            st.session_state.permission_decision = False
            st.rerun()


def render_sidebar(runner: AgentRunner):
    """左侧边栏：文件树 + 工具日志"""
    with st.sidebar:
        st.markdown("### 📁 文件浏览器")
        
        current_path = st.session_state.get("browse_path", ".")
        entries = runner.get_file_tree(current_path)
        
        # 返回上级
        if current_path != ".":
            if st.button("⬆️ 返回上级", use_container_width=True):
                parent = str(Path(current_path).parent)
                st.session_state.browse_path = parent if parent != "." else "."
                st.rerun()
        
        # 文件列表
        for entry in entries:
            icon = "📂" if entry["is_dir"] else "📄"
            label = f"{icon} {entry['name']}"
            if st.button(label, use_container_width=True, key=f"file_{entry['path']}"):
                if entry["is_dir"]:
                    st.session_state.browse_path = entry["path"]
                else:
                    st.session_state.selected_file = entry["path"]
                st.rerun()
        
        st.divider()
        st.markdown("### 🔨 工具调用记录")
        
        if runner.tool_events:
            for te in runner.tool_events:
                status = "" if te.status == "pending" else "✅" if te.output else "❌"
                with st.expander(f"{status} {te.tool_name}", expanded=False):
                    st.markdown("**输入:**")
                    st.json(te.tool_input)
                    if te.output:
                        st.markdown("**输出:**")
                        st.code(te.output[:500], language="text")
        else:
            st.caption("暂无工具调用")
        
        st.divider()
        st.markdown("### ⚙️ 设置")
        new_workspace = st.text_input("工作目录", value=st.session_state.get("workspace", "."))
        if new_workspace != st.session_state.get("workspace"):
            st.session_state.workspace = new_workspace
            st.session_state.runner = AgentRunner(workspace=new_workspace)
            st.rerun()
        
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.runner = AgentRunner(workspace=st.session_state.get("workspace", "."))
            st.rerun()


def render_file_viewer(runner: AgentRunner):
    """文件查看器"""
    selected = st.session_state.get("selected_file")
    if not selected:
        return
    
    with st.container():
        col1, col2 = st.columns([5, 1])
        with col1:
            st.caption(f"📄 {selected}")
        with col2:
            if st.button("✕ 关闭", key="close_file"):
                st.session_state.selected_file = None
                st.rerun()
        
        content = runner.read_file(selected)
        ext = Path(selected).suffix.lstrip(".")
        st.code(content, language=ext or "text")


def render_chat(runner: AgentRunner):
    """主聊天区域"""
    st.markdown("## 💬 LangGraph 智能助手")
    st.caption(f"会话 ID: `{runner.thread_id}` | 工作目录: `{runner.workspace}`")
    
    # 显示历史消息
    for msg in runner.messages:
        role = "user" if hasattr(msg, "type") and msg.type == "human" else "assistant"
        with st.chat_message(role):
            content = msg.content if hasattr(msg, "content") else str(msg)
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            st.markdown(block["text"])
                        elif block.get("type") == "tool_use":
                            st.code(f"工具：{block['name']}\n输入：{block.get('input', '')}", language="json")
                    else:
                        st.markdown(str(block))
            elif content:
                st.markdown(content)
    
    # 权限确认弹窗
    if runner.pending_interrupt:
        permission_dialog(runner.pending_interrupt)
        
        if "permission_decision" in st.session_state:
            decision = st.session_state.pop("permission_decision")
            
            async def do_resume():
                events = []
                async for event in runner.resume(decision):
                    events.append(event)
                return events
            
            with st.chat_message("assistant"):
                with st.spinner("处理中..." if decision else "已拒绝..."):
                    events = run_async(do_resume())
                    for event in events:
                        if event["type"] == "token":
                            st.markdown(event["content"])
            st.rerun()
    
    # 输入框
    if prompt := st.chat_input("输入消息..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        async def do_send():
            events = []
            async for event in runner.send_message(prompt):
                events.append(event)
            return events
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                events = run_async(do_send())
                
                full_response = ""
                for event in events:
                    if event["type"] == "token":
                        full_response += event["content"]
                    elif event["type"] == "tool_start":
                        st.info(f" 调用工具 `{event['name']}`")
                    elif event["type"] == "tool_end":
                        st.success(f"✅ `{event['name']}` 执行完成")
                    elif event["type"] == "interrupt":
                        st.warning(f"⏸️ {event['info'].message}")
                
                if full_response:
                    st.markdown(full_response)
        st.rerun()


def main():
    runner = get_runner()
    
    # 页面配置
    st.set_page_config(
        page_title="LangGraph Harness",
        page_icon="🔧",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # 布局：左侧边栏 + 主区域
    render_sidebar(runner)
    
    # 主区域：文件查看器 + 聊天
    render_file_viewer(runner)
    render_chat(runner)


if __name__ == "__main__":
    main()
