import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import lottie from 'lottie-web'
import copyCheckAnim from './assets/copy-check.json'

const GATEWAY_URL = '/api'

// Map tool names to FontAwesome icons and readable labels
function getToolAppearance(toolName) {
    const lower = (toolName || '').toLowerCase()

    // Category: read commands (manual lookups)
    if (lower.includes('account_lookup') || lower.includes('lookup_account'))
        return { icon: 'fa-solid fa-magnifying-glass', label: lower }
    if (lower.includes('hierarchy') || lower.includes('manage_hierarchy'))
        return { icon: 'fa-solid fa-sitemap', label: lower }
    if (lower.includes('aggregation') || lower.includes('report'))
        return { icon: 'fa-solid fa-chart-pie', label: lower }
    if (lower.includes('compliance') || lower.includes('verify'))
        return { icon: 'fa-solid fa-shield-halved', label: lower }
    if (lower.includes('system') || lower.includes('integrity'))
        return { icon: 'fa-solid fa-gears', label: lower }

    // Fallback
    return { icon: 'fa-solid fa-terminal', label: lower || 'function' }
}

// Generate a random 16-char alphanumeric ID
function generateChatId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    let id = ''
    for (let i = 0; i < 16; i++) {
        id += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    return id
}

function AnimatedAvatar({ src, isStreaming }) {
    const imgRef = useRef(null)
    const [frozen, setFrozen] = useState(false)
    const [frozenSrc, setFrozenSrc] = useState(null)
    const wasStreaming = useRef(isStreaming)
    const imgLoaded = useRef(false)
    const [cacheBuster] = useState(() => Date.now())

    const captureFrame = useCallback(() => {
        const img = imgRef.current
        if (!img || frozen || !imgLoaded.current) return
        try {
            const canvas = document.createElement('canvas')
            canvas.width = img.naturalWidth
            canvas.height = img.naturalHeight
            const ctx = canvas.getContext('2d')
            ctx.drawImage(img, 0, 0)
            const data = canvas.toDataURL('image/png')
            if (data && data !== 'data:,') {
                setFrozenSrc(data)
                setFrozen(true)
            }
        } catch (e) { }
    }, [frozen])

    useEffect(() => {
        if (!wasStreaming.current && !frozen) {
            const timer = setTimeout(captureFrame, 300)
            return () => clearTimeout(timer)
        }
    }, [captureFrame, frozen])

    useEffect(() => {
        if (wasStreaming.current && !isStreaming) {
            setTimeout(captureFrame, 50)
        }
        wasStreaming.current = isStreaming
    }, [isStreaming, captureFrame])

    if (frozen && frozenSrc) {
        return <img src={frozenSrc} alt="" className="assistant-avatar" />
    }

    return (
        <img
            ref={imgRef}
            src={`${src}?t=${cacheBuster}`}
            alt=""
            className="assistant-avatar"
            onLoad={() => { imgLoaded.current = true }}
        />
    )
}

function App() {
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [streaming, setStreaming] = useState(false)
    const [modelName, setModelName] = useState('')
    const [error, setError] = useState(null)
    const [editingIndex, setEditingIndex] = useState(null)
    const messagesEndRef = useRef(null)
    const inputRef = useRef(null)
    const abortControllerRef = useRef(null)

    // Chat history state
    const [chatId, setChatId] = useState(null)
    const [chatList, setChatList] = useState([])
    const [showHistory, setShowHistory] = useState(() => window.innerWidth >= 900)
    const [closingHistory, setClosingHistory] = useState(false)
    const [isIOS, setIsIOS] = useState(false)
    const [renamingChatId, setRenamingChatId] = useState(null)
    const [renameValue, setRenameValue] = useState('')
    const [searchQuery, setSearchQuery] = useState('')

    // Smooth-close the history modal
    const closeHistory = useCallback(() => {
        if (closingHistory) return
        setClosingHistory(true)
        setTimeout(() => {
            setShowHistory(false)
            setClosingHistory(false)
        }, 280)
    }, [closingHistory])

    // Load a chat from history
    const loadChat = useCallback(async (id, skipPush = false) => {
        try {
            const res = await fetch(`${GATEWAY_URL}/history/${id}`)
            const data = await res.json()
            if (data.messages) {
                setMessages(data.messages)
                setChatId(id)
                // Update URL to reflect the loaded chat
                if (!skipPush) {
                    window.history.pushState({ chatId: id }, '', `/${id}`)
                }
                // Only hide the history if it's currently an overlay (mobile)
                if (window.innerWidth < 900) {
                    setShowHistory(false)
                }
                setError(null)
                setEditingIndex(null)
                setInput('')
            }
        } catch (e) {
            console.error('Failed to load chat:', e)
        }
    }, [])

    // Fetch model info on mount
    useEffect(() => {
        fetch(`${GATEWAY_URL}/model`)
            .then(res => res.json())
            .then(data => setModelName(data.name || data.id))
            .catch(() => setModelName('Unknown'))

        // Detect iOS
        const userAgent = window.navigator.userAgent.toLowerCase();
        setIsIOS(/iphone|ipad|ipod/.test(userAgent));
    }, [])

    // Auto-load chat from URL path on mount (e.g. /2kdi8ivQvQzXmg6y)
    useEffect(() => {
        const pathId = window.location.pathname.replace(/^\//, '')
        if (pathId) {
            loadChat(pathId, true)
        }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    // Handle browser back/forward navigation
    useEffect(() => {
        const handlePopState = (event) => {
            const stateId = event.state?.chatId
            if (stateId) {
                loadChat(stateId, true)
            } else {
                // Navigated back to root — start fresh
                setMessages([])
                setChatId(null)
                setError(null)
                setInput('')
                setEditingIndex(null)
            }
        }
        window.addEventListener('popstate', handlePopState)
        return () => window.removeEventListener('popstate', handlePopState)
    }, [loadChat])

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    // Focus input on load
    useEffect(() => {
        inputRef.current?.focus()
    }, [])

    // Auto-resize input
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto'
            inputRef.current.style.height = `${inputRef.current.scrollHeight}px`
        }
    }, [input])

    // Load chat list when history panel opens
    useEffect(() => {
        if (showHistory) {
            fetch(`${GATEWAY_URL}/history/list`)
                .then(res => res.json())
                .then(data => setChatList(data))
                .catch(() => setChatList([]))
        }
    }, [showHistory])

    // Save chat to backend
    const saveChat = useCallback(async (id, msgs) => {
        if (!id || msgs.length === 0) return
        try {
            await fetch(`${GATEWAY_URL}/history/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, messages: msgs }),
            })
        } catch (e) {
            console.error('Failed to save chat:', e)
        }
    }, [])

    // Rename a chat
    const renameChat = useCallback(async (id, newTitle) => {
        const trimmed = newTitle.trim()
        if (!trimmed) {
            setRenamingChatId(null)
            return
        }
        try {
            await fetch(`${GATEWAY_URL}/history/rename`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, title: trimmed }),
            })
            setChatList(prev => prev.map(c => c.id === id ? { ...c, title: trimmed } : c))
        } catch (e) {
            console.error('Failed to rename chat:', e)
        }
        setRenamingChatId(null)
    }, [])

    // Delete a chat
    const deleteChat = useCallback(async (id) => {
        try {
            await fetch(`${GATEWAY_URL}/history/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id }),
            })
            setChatList(prev => prev.filter(c => c.id !== id))
            // If we just deleted the active chat, reset to new chat
            if (id === chatId) {
                setMessages([])
                setChatId(null)
                setError(null)
                setInput('')
                setEditingIndex(null)
                window.history.pushState({ chatId: null }, '', '/')
            }
        } catch (e) {
            console.error('Failed to delete chat:', e)
        }
        setRenamingChatId(null)
    }, [chatId])

    // Handle responsive resize (auto-hide sidebar when shrinking the window)
    useEffect(() => {
        let isLargeScreen = window.innerWidth >= 900
        const handleResize = () => {
            const currentlyLarge = window.innerWidth >= 900
            if (isLargeScreen && !currentlyLarge) {
                // Transitioned from wide sidebar view to narrow mobile view -> hide it
                setShowHistory(false)
                setClosingHistory(false)
            } else if (!isLargeScreen && currentlyLarge) {
                // Transitioned from narrow mobile view back to wide sidebar view -> show it
                setShowHistory(true)
                setClosingHistory(false)
            }
            isLargeScreen = currentlyLarge
        }
        window.addEventListener('resize', handleResize)
        return () => window.removeEventListener('resize', handleResize)
    }, [])

    // Start a new chat
    const startNewChat = useCallback(() => {
        // Abort any in-progress stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        setMessages([])
        setChatId(null)
        setError(null)
        setInput('')
        setEditingIndex(null)
        setStreaming(false)
        setShowHistory(false)
        // Reset URL to root
        window.history.pushState({ chatId: null }, '', '/')
        inputRef.current?.focus()
    }, [])

    const sendMessage = useCallback(async (overrideText = null) => {
        const text = (overrideText !== null ? overrideText : input).trim()
        if (!text || streaming) return

        setError(null)
        const userMsg = { role: 'user', content: [{ text }], timestamp: new Date().toISOString() }

        const base = editingIndex !== null ? messages.slice(0, editingIndex) : messages
        const newMessages = [...base, userMsg]
        setMessages(newMessages)
        setInput('')
        setEditingIndex(null)
        setStreaming(true)

        // Generate chat ID on first message if needed
        let currentChatId = chatId
        if (!currentChatId) {
            currentChatId = generateChatId()
            setChatId(currentChatId)
            // Push the new chat ID into the URL
            window.history.pushState({ chatId: currentChatId }, '', `/${currentChatId}`)
        }

        const assistantMsg = { role: 'assistant', content: [{ text: '' }], thinking: '', timestamp: new Date().toISOString() }
        setMessages([...newMessages, assistantMsg])

        const controller = new AbortController()
        abortControllerRef.current = controller

        let finalMessages = [...newMessages, assistantMsg]

        try {
            // Option A Context Diary: Only send the newest user message to the backend
            const lastUserMsg = newMessages[newMessages.length - 1]
            const payloadMessages = [{ role: lastUserMsg.role, content: lastUserMsg.content }]

            const res = await fetch(`${GATEWAY_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: payloadMessages }),
                signal: controller.signal,
            })

            if (!res.ok) {
                throw new Error(`Gateway returned ${res.status}`)
            }

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            let fullText = ''
            let thinkingText = ''
            let activeToolName = ''
            let isProcessing = false

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const data = JSON.parse(line.slice(6))
                        if (data.error) {
                            setError(data.error)
                            break
                        }
                        if (data.tool_name) {
                            activeToolName = data.tool_name
                        }
                        if (data.processing) {
                            isProcessing = true
                            const updatedMsgs = [...newMessages, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: true, active_tool: activeToolName, timestamp: assistantMsg.timestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.text) {
                            fullText += data.text
                            const updatedMsgs = [...newMessages, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: isProcessing, active_tool: isProcessing ? activeToolName : '', timestamp: assistantMsg.timestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.thinking) {
                            thinkingText += data.thinking
                            const updatedMsgs = [...newMessages, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: assistantMsg.timestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.done) {
                            if (data.raw_history) {
                                const updatedMsgs = [...newMessages, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: assistantMsg.timestamp, raw_history: data.raw_history }]
                                setMessages(updatedMsgs)
                                finalMessages = updatedMsgs
                            }
                            break
                        }
                    } catch { }
                }
            }
        } catch (err) {
            if (err.name === 'AbortError') {
                // User stopped — keep partial response
            } else {
                setError(`Connection error: ${err.message}. Is the gateway running?`)
                setMessages(prev => {
                    const last = prev[prev.length - 1]
                    if (last?.role === 'assistant' && !last.content[0].text) {
                        return prev.slice(0, -1)
                    }
                    return prev
                })
            }
        } finally {
            abortControllerRef.current = null
            setStreaming(false)
            inputRef.current?.focus()

            // Auto-save after response completes
            saveChat(currentChatId, finalMessages)
        }
    }, [input, messages, streaming, editingIndex, chatId, saveChat])

    const stopGeneration = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
    }, [])

    const retryMessage = useCallback(async (assistantIndex) => {
        if (streaming) return
        const userMsg = messages[assistantIndex - 1]
        if (!userMsg || userMsg.role !== 'user') return

        const truncated = messages.slice(0, assistantIndex)

        setError(null)
        setStreaming(true)

        // Ensure we have a chat ID
        let currentChatId = chatId
        if (!currentChatId) {
            currentChatId = generateChatId()
            setChatId(currentChatId)
            window.history.pushState({ chatId: currentChatId }, '', `/${currentChatId}`)
        }

        const assistantMsg = { role: 'assistant', content: [{ text: '' }], thinking: '', timestamp: new Date().toISOString() }
        setMessages([...truncated, assistantMsg])

        const controller = new AbortController()
        abortControllerRef.current = controller

        let finalMessages = [...truncated, assistantMsg]

        try {
            // Option A Context Diary: Only send the newest user message to the backend
            const lastUserMsg = truncated[truncated.length - 1]
            const payloadMessages = [{ role: lastUserMsg.role, content: lastUserMsg.content }]

            const res = await fetch(`${GATEWAY_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: payloadMessages }),
                signal: controller.signal,
            })

            if (!res.ok) throw new Error(`Gateway returned ${res.status}`)

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            let fullText = ''
            let thinkingText = ''
            let activeToolName = ''
            let isProcessing = false

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() || ''
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const data = JSON.parse(line.slice(6))
                        if (data.error) { setError(data.error); break }
                        if (data.tool_name) {
                            activeToolName = data.tool_name
                        }
                        if (data.processing) {
                            isProcessing = true
                            const updatedMsgs = [...truncated, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: true, active_tool: activeToolName, timestamp: assistantMsg.timestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.text) {
                            isProcessing = false
                            activeToolName = ''
                            fullText += data.text
                            const updatedMsgs = [...truncated, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: assistantMsg.timestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.thinking) {
                            thinkingText += data.thinking
                            const updatedMsgs = [...truncated, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: assistantMsg.timestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.done) {
                            if (data.raw_history) {
                                const updatedMsgs = [...truncated, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: assistantMsg.timestamp, raw_history: data.raw_history }]
                                setMessages(updatedMsgs)
                                finalMessages = updatedMsgs
                            }
                            break
                        }
                    } catch { }
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(`Connection error: ${err.message}`)
                setMessages(prev => {
                    const last = prev[prev.length - 1]
                    if (last?.role === 'assistant' && !last.content[0].text) return prev.slice(0, -1)
                    return prev
                })
            }
        } finally {
            abortControllerRef.current = null
            setStreaming(false)
            inputRef.current?.focus()

            // Auto-save after retry completes
            saveChat(currentChatId, finalMessages)
        }
    }, [messages, streaming, chatId, saveChat])

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            sendMessage()
        }
    }

    const inputArea = (
        <div className="input-area-container">
            {editingIndex !== null && (
                <div className="edit-mode-header">
                    <span className="edit-mode-title">Editing message</span>
                    <button
                        className={`edit-mode-cancel ${isIOS ? 'ios-large-cancel' : ''}`}
                        title="Cancel edit"
                        onClick={() => {
                            setEditingIndex(null)
                            setInput('')
                        }}
                    >
                        ✕
                    </button>
                </div>
            )}
            <div className="input-area">
                <div className="input-wrapper">
                    <textarea
                        ref={inputRef}
                        className="input-field"
                        placeholder="Type a message..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        rows={1}
                        disabled={streaming}
                    />
                    {streaming && (
                        <button
                            className="stop-btn"
                            onClick={stopGeneration}
                            title="Stop generation"
                        >
                            <i className="fa-solid fa-stop" />
                        </button>
                    )}
                    <button
                        className="send-btn"
                        onClick={() => sendMessage()}
                        disabled={streaming || !input.trim()}
                        title="Send"
                    >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style={{ transform: 'rotate(-45deg)', overflow: 'visible' }}>
                            <path d="M0 24L24 12L0 0L7 12Z" fill="currentColor" stroke="#ffffff" strokeWidth="12.5" strokeLinejoin="round" strokeLinecap="round" />
                            <path d="M0 24L24 12L0 0L7 12Z" fill="currentColor" stroke="var(--bg-input)" strokeWidth="8.5" strokeLinejoin="round" strokeLinecap="round" />
                            <path d="M0 24L24 12L0 0L7 12Z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    )

    return (
        <div className="app-layout">
            {/* History Modal Overlay / Sidebar */}
            {showHistory && (
                <div className={`history-overlay ${closingHistory ? 'closing' : ''}`} onClick={closeHistory}>
                    <div className={`history-modal ${closingHistory ? 'closing' : ''}`} onClick={e => e.stopPropagation()}>
                        <div className="history-modal-header">
                            <div className="history-modal-header-top">
                                <span className="history-modal-title">
                                    <i className="fa-regular fa-comments" style={{ marginRight: 8 }} />
                                    CHAT HISTORY
                                </span>
                                <span className="history-count-badge">+{chatList.length}</span>
                                <button
                                    className="history-modal-close"
                                    onClick={closeHistory}
                                >
                                    ✕
                                </button>
                            </div>
                            <div className="history-search-container">
                                <input
                                    type="text"
                                    className="history-search-input"
                                    placeholder="Search history..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                                <div className="history-search-actions">
                                    <div className="history-search-icon">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <circle cx="11" cy="11" r="8"></circle>
                                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                        </svg>
                                    </div>
                                    <div className="history-search-divider" />
                                    <button
                                        className={`history-search-clear ${searchQuery ? 'active' : ''}`}
                                        title="Clear search"
                                        onClick={() => setSearchQuery('')}
                                    >
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                                            <line x1="2" y1="2" x2="22" y2="22"></line>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div className="history-list">
                            {chatList.filter(chat =>
                                (chat.title || chat.preview || '').toLowerCase().includes(searchQuery.toLowerCase())
                            ).length === 0 ? (
                                <div className="history-empty">
                                    {chatList.length === 0 ? 'No saved chats yet' : 'No chats found'}
                                </div>
                            ) : (
                                chatList
                                    .filter(chat => (chat.title || chat.preview || '').toLowerCase().includes(searchQuery.toLowerCase()))
                                    .map(chat => (
                                        <div key={chat.id} className={`history-item-row ${renamingChatId === chat.id ? 'renaming' : ''}`}>
                                            <div
                                                className={`history-item ${chat.id === chatId ? 'active' : ''} ${renamingChatId === chat.id ? 'renaming' : ''}`}
                                                onClick={() => { if (renamingChatId !== chat.id) loadChat(chat.id) }}
                                            >
                                                {renamingChatId === chat.id ? (
                                                    <div className="history-rename-wrapper">
                                                        <input
                                                            className="history-rename-input"
                                                            value={renameValue}
                                                            onChange={e => setRenameValue(e.target.value)}
                                                            onKeyDown={e => {
                                                                if (e.key === 'Enter') renameChat(chat.id, renameValue)
                                                                if (e.key === 'Escape') setRenamingChatId(null)
                                                            }}
                                                            onBlur={e => {
                                                                if (!e.relatedTarget?.closest('.history-rename-actions')) {
                                                                    renameChat(chat.id, renameValue)
                                                                }
                                                            }}
                                                            autoFocus
                                                            onClick={e => e.stopPropagation()}
                                                        />
                                                        <i className="fa-solid fa-pencil history-rename-icon" />
                                                    </div>
                                                ) : (
                                                    <div className="history-item-preview">
                                                        {chat.title || chat.preview || 'Empty chat'}
                                                    </div>
                                                )}
                                                {renamingChatId !== chat.id && (
                                                    <button
                                                        className="history-rename-btn"
                                                        title="Rename chat"
                                                        onClick={e => {
                                                            e.stopPropagation()
                                                            setRenamingChatId(chat.id)
                                                            setRenameValue(chat.title || chat.preview || '')
                                                        }}
                                                    >
                                                        <i className="fa-regular fa-pen-to-square" />
                                                    </button>
                                                )}
                                                {renamingChatId !== chat.id && (
                                                    <div className="history-item-date">
                                                        {chat.updatedAt ? new Date(chat.updatedAt).toLocaleDateString() : ''}
                                                    </div>
                                                )}
                                            </div>
                                            {renamingChatId === chat.id && (
                                                <div className="history-rename-actions" onClick={e => e.stopPropagation()}>
                                                    <button
                                                        className="history-rename-action-btn confirm"
                                                        title="Confirm"
                                                        onMouseDown={e => { e.preventDefault(); renameChat(chat.id, renameValue) }}
                                                    >
                                                        <i className="fa-solid fa-check" />
                                                    </button>
                                                    <button
                                                        className="history-rename-action-btn cancel"
                                                        title="Cancel"
                                                        onMouseDown={e => { e.preventDefault(); setRenamingChatId(null) }}
                                                    >
                                                        <i className="fa-solid fa-xmark" />
                                                    </button>
                                                    <button
                                                        className="history-rename-action-btn delete"
                                                        title="Delete chat"
                                                        onMouseDown={e => { e.preventDefault(); deleteChat(chat.id) }}
                                                    >
                                                        <i className="fa-solid fa-trash" />
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    ))
                            )}
                        </div>
                    </div>
                </div>
            )}

            <div className="app">
                {/* Header */}
                <div className="header">
                    <div className="header-left">
                        <img src="/tenant-pixel.png" alt="Tenant" className="header-logo" />
                        <span className="header-title">TENANT · CHAT</span>
                        <button
                            className="new-chat-btn"
                            onClick={startNewChat}
                            title="New chat"
                        >
                            +
                        </button>
                    </div>
                    <div className="header-right">
                        <button
                            className={`header-action-btn ${showHistory ? 'active' : ''}`}
                            onClick={() => showHistory ? closeHistory() : setShowHistory(true)}
                            title="Chat history"
                        >
                            <img src="/chat-history.png" alt="History" className="header-action-icon" />
                        </button>
                    </div>
                </div>

                {/* Error banner */}
                {error && <div className="error-banner">{error}</div>}

                {/* Messages */}
                <div className={`messages-wrapper ${messages.length === 0 ? 'is-empty' : ''} ${editingIndex !== null ? 'is-editing' : ''}`}>
                    <div className={`messages ${editingIndex !== null ? 'edit-mode-no-scroll' : ''}`}>
                        {messages.length === 0 ? (
                            <div className="empty-state">
                                <div className="greeting-text">
                                    <span className="greeting-time">
                                        {(() => {
                                            const h = new Date().getHours()
                                            return h < 5 ? 'Good Evening,' : h < 12 ? 'Good Morning,' : h < 18 ? 'Good Afternoon,' : 'Good Evening,'
                                        })()}
                                    </span>
                                    <span className="greeting-main">Do you have a request? ~ <i className="fa-solid fa-code glowing-code" style={{ fontSize: '1.0em', marginLeft: '2px' }}></i></span>
                                </div>

                                <div className="empty-state-input-wrapper">
                                    {inputArea}
                                </div>

                                <div className="suggestion-questions">
                                    {[
                                        { text: "Can you please tell me what email address is registered to user3?", icon: "fa-regular fa-envelope" },
                                        { text: "Are there any agents who haven't verified their email addresses yet?", icon: "fa-regular fa-user" },
                                        { text: "What's the ratio of AGENT accounts to regular USER accounts?", icon: "fa-solid fa-chart-pie" }
                                    ].map((q, idx) => (
                                        <button
                                            key={idx}
                                            className="suggestion-btn"
                                            onClick={() => {
                                                sendMessage(q.text)
                                            }}
                                        >
                                            <i className={q.icon}></i>
                                            {q.text}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            messages.map((msg, i) => {
                                const isEditingMode = editingIndex !== null;
                                const isFocused = isEditingMode && editingIndex === i;
                                const isDimmed = isEditingMode && editingIndex !== i;

                                return (
                                    <div
                                        key={i}
                                        id={`message-${i}`}
                                        className={`message ${msg.role} ${isFocused ? 'is-focused' : ''} ${isDimmed ? 'is-dimmed' : ''}`}
                                    >
                                        {msg.role === 'assistant' && (
                                            <div className="assistant-avatar-container">
                                                <AnimatedAvatar
                                                    src="/LLM-WAVE.gif"
                                                    isStreaming={streaming && i === messages.length - 1}
                                                />
                                            </div>
                                        )}
                                        <div className="message-content">
                                            {msg.role === 'assistant' && (
                                                <div className="message-header">
                                                    <span className="message-sender">Model</span>
                                                    <span className="message-dot">•</span>
                                                    <span className="message-time">
                                                        {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '7:34 PM'}
                                                    </span>
                                                </div>
                                            )}
                                            {msg.role === 'assistant' && msg.thinking && (
                                                <details className={`thinking-block ${streaming && i === messages.length - 1 ? 'streaming' : ''}`}>
                                                    <summary>
                                                        <i className="fa-solid fa-brain" />
                                                        <span>Thinking</span>
                                                        {streaming && i === messages.length - 1 && !msg.content[0].text && (
                                                            <span className="thinking-spinner" />
                                                        )}
                                                    </summary>
                                                    <div className="thinking-content">{msg.thinking}</div>
                                                </details>
                                            )}
                                            <div className={`message-body ${streaming && i === messages.length - 1 && msg.role === 'assistant' ? 'streaming' : ''}`}>
                                                {msg.role === 'assistant' ? (
                                                    <div className="markdown-content">
                                                        {(() => {
                                                            let t = msg.content[0].text
                                                            // Strip raw commands
                                                            t = t.replace(/<FUNCTION_CALL>[\s\S]*?<\/FUNCTION_CALL>/g, '')
                                                            t = t.replace(/<CONTEXT>[\s\S]*?<\/CONTEXT>/g, '')
                                                            t = t.replace(/^read\([^)]*\)\s*$/gm, '')

                                                            // Split by {{TOOL:name}} markers
                                                            const parts = t.split(/(\{\{TOOL:[^}]+\}\})/g)

                                                            return parts.map((part, idx) => {
                                                                const toolMatch = part.match(/^\{\{TOOL:(.+)\}\}$/)
                                                                if (toolMatch) {
                                                                    const toolName = toolMatch[1]
                                                                    const appearance = getToolAppearance(toolName)
                                                                    return (
                                                                        <div key={idx} className="tool-execution-badge">
                                                                            <i className={appearance.icon}></i>
                                                                            <span>Executing <strong>{appearance.label}</strong></span>
                                                                        </div>
                                                                    )
                                                                }
                                                                const trimmed = part.trim()
                                                                if (!trimmed) return null
                                                                return (
                                                                    <ReactMarkdown key={idx} remarkPlugins={[remarkGfm]}>
                                                                        {trimmed}
                                                                    </ReactMarkdown>
                                                                )
                                                            })
                                                        })()}
                                                    </div>
                                                ) : (
                                                    msg.content[0].text
                                                )}
                                                {streaming && i === messages.length - 1 && msg.role === 'assistant' && !msg.processing && (
                                                    <span className="cursor" />
                                                )}
                                            </div>
                                            {!(streaming && i === messages.length - 1 && msg.role === 'assistant') && (
                                                <div className="message-actions">
                                                    <button
                                                        className="action-btn copy-action-btn"
                                                        title="Copy"
                                                        onClick={(e) => {
                                                            navigator.clipboard.writeText(msg.content[0].text)
                                                            const btn = e.currentTarget
                                                            const icon = btn.querySelector('.copy-icon')
                                                            const animContainer = btn.querySelector('.copy-lottie')
                                                            if (icon) icon.style.display = 'none'
                                                            if (animContainer) {
                                                                animContainer.style.display = 'flex'
                                                                animContainer.innerHTML = ''
                                                                const anim = lottie.loadAnimation({
                                                                    container: animContainer,
                                                                    renderer: 'svg',
                                                                    loop: false,
                                                                    autoplay: true,
                                                                    animationData: structuredClone(copyCheckAnim)
                                                                })
                                                                anim.addEventListener('complete', () => {
                                                                    anim.destroy()
                                                                    animContainer.style.display = 'none'
                                                                    if (icon) icon.style.display = ''
                                                                })
                                                            }
                                                        }}
                                                    >
                                                        <i className="fa-regular fa-copy copy-icon" />
                                                        <span className="copy-lottie" style={{ display: 'none', width: 26, height: 26, alignItems: 'center', justifyContent: 'center' }} />
                                                    </button>
                                                    {msg.role === 'assistant' && (
                                                        <button
                                                            className="action-btn"
                                                            title="Rerun"
                                                            onClick={() => retryMessage(i)}
                                                        >
                                                            <i className="fa-solid fa-rotate-right" />
                                                        </button>
                                                    )}
                                                    {msg.role === 'user' && (
                                                        <button
                                                            className="action-btn"
                                                            title="Edit"
                                                            onClick={() => {
                                                                setInput(msg.content[0].text)
                                                                setEditingIndex(i)
                                                                setTimeout(() => {
                                                                    const msgEl = document.getElementById(`message-${i}`)
                                                                    const container = msgEl?.closest('.messages')
                                                                    if (msgEl && container) {
                                                                        // Calculate the exact target scroll position:
                                                                        // Container's current scroll + Element's offset relative to container
                                                                        // Minus the height of the container to align it to the bottom
                                                                        // Plus the element's height to show the full element
                                                                        // Plus extra padding for breathing room
                                                                        const targetScroll = msgEl.offsetTop - container.offsetTop - container.clientHeight + msgEl.clientHeight - 32;
                                                                        container.scrollTop = Math.max(0, targetScroll);
                                                                    }
                                                                }, 10)
                                                            }}
                                                        >
                                                            <i className="fa-regular fa-pen-to-square" />
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )
                            })
                        )}
                        <div ref={messagesEndRef} />
                    </div>
                </div>

                {/* Bottom Input (only when there are messages) */}
                {messages.length > 0 && inputArea}
            </div>
        </div>
    )
}

export default App
