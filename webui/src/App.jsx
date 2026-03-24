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

function AnimatedAvatar({ isStreaming }) {
    const src = isStreaming ? "/LLM-WAVE.gif" : "/LLM-WAVE-IDLE.gif"
    const imgRef = useRef(null)
    const [frozen, setFrozen] = useState(false)
    const [frozenSrc, setFrozenSrc] = useState(null)
    const imgLoaded = useRef(false)

    // Reset freezing state when streaming state changes
    useEffect(() => {
        if (isStreaming) {
            setFrozen(false)
            setFrozenSrc(null)
        } else {
            // We need to capture the idle frame
            setFrozen(false) // Temporarily unfreeze to render the image and capture it
        }
    }, [isStreaming])

    const captureFrame = useCallback(() => {
        const img = imgRef.current
        if (!img || isStreaming || frozen) return
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
    }, [isStreaming, frozen])

    // Wait for image decode/render before capturing frame
    useEffect(() => {
        if (!isStreaming && !frozen) {
            const timer = setTimeout(() => {
                if (imgLoaded.current) {
                    captureFrame()
                }
            }, 50)
            return () => clearTimeout(timer)
        }
    }, [isStreaming, frozen, captureFrame])

    if (frozen && frozenSrc && !isStreaming) {
        return <img src={frozenSrc} alt="" className="assistant-avatar" />
    }

    return (
        <img
            ref={imgRef}
            src={src}
            alt=""
            className="assistant-avatar"
            onLoad={() => { 
                imgLoaded.current = true
                if (!isStreaming && !frozen) {
                    captureFrame()
                }
            }}
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
    const [collapsedGroups, setCollapsedGroups] = useState(new Set())
    const [expandedGroups, setExpandedGroups] = useState(new Set())
    const [selectedDiaryChat, setSelectedDiaryChat] = useState(null)
    const [closingDiary, setClosingDiary] = useState(false)

    // AWS credentials / settings modal state
    const [awsConfigured, setAwsConfigured] = useState(null)
    const [showSettings, setShowSettings] = useState(false)
    const [closingSettings, setClosingSettings] = useState(false)
    const [awsAccessKey, setAwsAccessKey] = useState('')
    const [awsSecretKey, setAwsSecretKey] = useState('')
    const [savingKeys, setSavingKeys] = useState(false)
    const [keysError, setKeysError] = useState('')
    const [keysSaved, setKeysSaved] = useState(false)

    // Smooth-close the history modal
    const closeHistory = useCallback(() => {
        if (closingHistory) return
        setClosingHistory(true)
        setTimeout(() => {
            setShowHistory(false)
            setClosingHistory(false)
        }, 280)
    }, [closingHistory])

    // Smooth-close the diary modal
    const closeDiary = useCallback(() => {
        if (closingDiary) return
        setClosingDiary(true)
        setTimeout(() => {
            setSelectedDiaryChat(null)
            setClosingDiary(false)
        }, 280)
    }, [closingDiary])

    // Smooth-close the settings modal
    const closeSettings = useCallback(() => {
        if (closingSettings) return
        setClosingSettings(true)
        setTimeout(() => {
            setShowSettings(false)
            setClosingSettings(false)
        }, 280)
    }, [closingSettings])

    // Check AWS credentials on mount + poll every 5s to detect deletion
    useEffect(() => {
        const check = () => {
            fetch(`${GATEWAY_URL}/credentials/status`)
                .then(res => res.json())
                .then(data => {
                    setAwsConfigured(prev => {
                        if (prev === true && !data.configured) setShowSettings(true)
                        if (prev === null && !data.configured) setShowSettings(true)
                        return data.configured
                    })
                })
                .catch(() => setAwsConfigured(false))
        }
        check()
        const interval = setInterval(check, 5000)
        return () => clearInterval(interval)
    }, [])

    // Save AWS credentials
    const saveAwsKeys = useCallback(async () => {
        setKeysError('')
        setKeysSaved(false)
        if (!awsAccessKey.trim() || !awsSecretKey.trim()) {
            setKeysError('Both keys are required.')
            return
        }
        setSavingKeys(true)
        try {
            const res = await fetch(`${GATEWAY_URL}/credentials/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    aws_access_key_id: awsAccessKey.trim(),
                    aws_secret_access_key: awsSecretKey.trim(),
                }),
            })
            const data = await res.json()
            if (data.ok) {
                setAwsConfigured(true)
                setKeysSaved(true)
                setAwsAccessKey('')
                setAwsSecretKey('')
                setTimeout(() => closeSettings(), 1200)
            } else {
                setKeysError(data.error || 'Failed to save.')
            }
        } catch (e) {
            setKeysError('Network error. Is the server running?')
        } finally {
            setSavingKeys(false)
        }
    }, [awsAccessKey, awsSecretKey, closeSettings])

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
            const payloadMessages = newMessages.slice(-5).map(m => ({
                role: m.role,
                content: m.content
            }))

            const res = await fetch(`${GATEWAY_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: payloadMessages, chat_id: currentChatId }),
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
            let completedAssistants = []
            let currentTimestamp = assistantMsg.timestamp

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
                        if (data.chain_step) {
                            completedAssistants.push({ role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: currentTimestamp })
                            fullText = ''
                            thinkingText = ''
                            activeToolName = ''
                            isProcessing = false
                            currentTimestamp = new Date().toISOString()
                            const updatedMsgs = [...newMessages, ...completedAssistants, { role: 'assistant', content: [{ text: '' }], thinking: '', processing: false, timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.tool_name) {
                            activeToolName = data.tool_name
                        }
                        if (data.processing) {
                            isProcessing = true
                            const updatedMsgs = [...newMessages, ...completedAssistants, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: true, active_tool: activeToolName, timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.text) {
                            fullText += data.text
                            const updatedMsgs = [...newMessages, ...completedAssistants, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: isProcessing, active_tool: isProcessing ? activeToolName : '', timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.thinking) {
                            thinkingText += data.thinking
                            const updatedMsgs = [...newMessages, ...completedAssistants, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.done) {
                            const doneMsg = { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: currentTimestamp }
                            if (data.total_tokens) doneMsg.total_tokens = data.total_tokens
                            const updatedMsgs = [...newMessages, ...completedAssistants, doneMsg]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
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

        // Walk backwards to find the nearest user message (handles consecutive chain bubbles)
        let userIdx = assistantIndex - 1
        while (userIdx >= 0 && messages[userIdx].role !== 'user') userIdx--
        if (userIdx < 0) return

        // Truncate right after that user message (removes all chain assistant bubbles)
        const truncated = messages.slice(0, userIdx + 1)

        setError(null)
        setStreaming(true)

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
            const payloadMessages = truncated.slice(-5).map(m => ({
                role: m.role,
                content: m.content
            }))

            const res = await fetch(`${GATEWAY_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: payloadMessages, chat_id: currentChatId }),
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
            let completedAssistants = []
            let currentTimestamp = assistantMsg.timestamp

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
                        if (data.chain_step) {
                            completedAssistants.push({ role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: currentTimestamp })
                            fullText = ''
                            thinkingText = ''
                            activeToolName = ''
                            isProcessing = false
                            currentTimestamp = new Date().toISOString()
                            const updatedMsgs = [...truncated, ...completedAssistants, { role: 'assistant', content: [{ text: '' }], thinking: '', processing: false, timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.tool_name) {
                            activeToolName = data.tool_name
                        }
                        if (data.processing) {
                            isProcessing = true
                            const updatedMsgs = [...truncated, ...completedAssistants, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: true, active_tool: activeToolName, timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.text) {
                            fullText += data.text
                            const updatedMsgs = [...truncated, ...completedAssistants, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: isProcessing, active_tool: isProcessing ? activeToolName : '', timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.thinking) {
                            thinkingText += data.thinking
                            const updatedMsgs = [...truncated, ...completedAssistants, { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: currentTimestamp }]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
                        }
                        if (data.done) {
                            const doneMsg = { role: 'assistant', content: [{ text: fullText }], thinking: thinkingText, processing: false, timestamp: currentTimestamp }
                            if (data.total_tokens) doneMsg.total_tokens = data.total_tokens
                            const updatedMsgs = [...truncated, ...completedAssistants, doneMsg]
                            setMessages(updatedMsgs)
                            finalMessages = updatedMsgs
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
                        placeholder={awsConfigured === false ? "Configure AWS keys to start chatting..." : "Type a message..."}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        rows={1}
                        disabled={streaming || awsConfigured === false}
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
                        disabled={streaming || !input.trim() || awsConfigured === false}
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
            {/* Context Diary Modal */}
            {selectedDiaryChat && (
                <div className={`diary-modal-overlay ${closingDiary ? 'closing' : ''}`} onClick={closeDiary}>
                    <div className={`diary-modal ${closingDiary ? 'closing' : ''}`} onClick={e => e.stopPropagation()}>
                        <div className="diary-modal-header">
                            <h3 className="diary-modal-title">
                                <i className="fa-solid fa-book-bookmark" style={{ marginRight: '12px', fontSize: '16px', color: '#ffffff' }} />
                                Context - Memory
                            </h3>
                            <button className="diary-modal-close" onClick={closeDiary}>✕</button>
                        </div>
                        <div className="diary-modal-body">
                            {selectedDiaryChat.context_diary ? (
                                <p className="diary-modal-text">{selectedDiaryChat.context_diary}</p>
                            ) : (
                                <p className="diary-modal-empty">No context diary available for this chat.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Settings / AWS Keys Modal */}
            {showSettings && (
                <div className={`settings-modal-overlay ${closingSettings ? 'closing' : ''}`} onClick={awsConfigured ? closeSettings : undefined}>
                    <div className={`settings-modal ${closingSettings ? 'closing' : ''}`} onClick={e => e.stopPropagation()}>
                        <div className="settings-modal-banner" aria-hidden />
                        <div className="settings-modal-content">
                            <div className="settings-modal-head">
                                <div className="settings-modal-head-text">
                                    <div className="settings-modal-title-row">
                                        <h2 className="settings-modal-title">
                                            {!awsConfigured && !keysSaved ? 'AWS API credentials' : 'Update AWS credentials'}
                                        </h2>
                                        <span className="settings-modal-title-trailing" aria-hidden>
                                            <img
                                                src="/aws-cube.png"
                                                alt=""
                                                className="settings-modal-title-icon"
                                                width={40}
                                                height={40}
                                            />
                                        </span>
                                    </div>
                                    <p className="settings-modal-subtitle">
                                        {!awsConfigured && !keysSaved
                                            ? 'Provide an access key ID and secret access key with permission to invoke Amazon Bedrock. Values are written only to the local credentials file on this host.'
                                            : 'Enter a new access key ID and secret access key to replace the stored values.'}
                                    </p>
                                </div>
                                {awsConfigured && (
                                    <button type="button" className="settings-modal-close" onClick={closeSettings} aria-label="Close">✕</button>
                                )}
                            </div>

                            {keysSaved && (
                                <div className="settings-toast success" role="status">Credentials saved.</div>
                            )}
                            {keysError && (
                                <div className="settings-toast error" role="alert">{keysError}</div>
                            )}

                            <div className="settings-fields">
                                <div className="settings-field">
                                    <label className="settings-label" htmlFor="aws-access-key">Access key ID</label>
                                    <div className="settings-input-wrap">
                                        <i className="fa-solid fa-key settings-input-icon" aria-hidden />
                                        <input
                                            id="aws-access-key"
                                            type="text"
                                            className="settings-input"
                                            placeholder="AKIA9FQ2L7XW3ZC8RMNP"
                                            value={awsAccessKey}
                                            onChange={e => setAwsAccessKey(e.target.value)}
                                            spellCheck={false}
                                            autoComplete="off"
                                        />
                                    </div>
                                </div>
                                <div className="settings-field">
                                    <label className="settings-label" htmlFor="aws-secret-key">Secret access key</label>
                                    <div className="settings-input-wrap">
                                        <i className="fa-solid fa-lock settings-input-icon" aria-hidden />
                                        <input
                                            id="aws-secret-key"
                                            type="password"
                                            className="settings-input"
                                            placeholder="7GfK3pQX9Lm82sZrTYuHiB4WVAJ/ND..."
                                            value={awsSecretKey}
                                            onChange={e => setAwsSecretKey(e.target.value)}
                                            spellCheck={false}
                                            autoComplete="off"
                                        />
                                    </div>
                                </div>
                            </div>

                            <p className="settings-save-hint" role="note">
                                <i className="fa-solid fa-shield-halved settings-save-hint-icon" aria-hidden />
                                <span>
                                    Credentials are saved only to the local AWS credentials file on this device, not in browser storage.
                                </span>
                            </p>

                            <button
                                type="button"
                                className="settings-save-btn"
                                onClick={saveAwsKeys}
                                disabled={savingKeys || (!awsAccessKey.trim() && !awsSecretKey.trim())}
                            >
                                {savingKeys ? (
                                    <><span className="settings-save-spinner" />Saving…</>
                                ) : (
                                    <>
                                        Save credentials
                                        <i className="fa-solid fa-lock settings-save-btn-lock" aria-hidden />
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

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
                            {(() => {
                                const filteredChats = chatList.filter(chat =>
                                    (chat.title || chat.preview || '').toLowerCase().includes(searchQuery.toLowerCase())
                                );

                                if (filteredChats.length === 0) {
                                    return (
                                        <div className="history-empty">
                                            {chatList.length === 0 ? 'No saved chats yet' : 'No chats found'}
                                        </div>
                                    );
                                }

                                // Sort all filtered chats by date descending
                                const sortedChats = [...filteredChats].sort((a, b) => {
                                    const dateA = a.updatedAt ? new Date(a.updatedAt).getTime() : 0;
                                    const dateB = b.updatedAt ? new Date(b.updatedAt).getTime() : 0;
                                    return dateB - dateA;
                                });

                                // Group them by date
                                const groupedChats = [];
                                let currentGroup = null;

                                sortedChats.forEach(chat => {
                                    const date = chat.updatedAt ? new Date(chat.updatedAt) : new Date();
                                    const dateString = date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
                                    
                                    if (!currentGroup || currentGroup.date !== dateString) {
                                        currentGroup = { date: dateString, chats: [] };
                                        groupedChats.push(currentGroup);
                                    }
                                    currentGroup.chats.push(chat);
                                });

                                const getRelativeTime = (dateString) => {
                                    if (!dateString) return '';
                                    const date = new Date(dateString);
                                    const now = new Date();
                                    // Reset time part to compare just dates
                                    const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
                                    const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                                    const diffTime = Math.abs(nowDay - dateDay);
                                    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
                                    
                                    if (diffDays === 0) return 'Today';
                                    if (diffDays === 1) return '1d';
                                    if (diffDays < 7) return `${diffDays}d`;
                                    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w`;
                                    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo`;
                                    return `${Math.floor(diffDays / 365)}y`;
                                };

                                const toggleGroup = (dateString) => {
                                    setCollapsedGroups(prev => {
                                        const next = new Set(prev);
                                        if (next.has(dateString)) next.delete(dateString);
                                        else next.add(dateString);
                                        return next;
                                    });
                                };

                                return groupedChats.map(group => {
                                    const isCollapsed = collapsedGroups.has(group.date);
                                    const isFullyExpanded = expandedGroups.has(group.date);
                                    const visibleChats = isFullyExpanded ? group.chats : group.chats.slice(0, 5);
                                    const hasMore = group.chats.length > 5;

                                    return (
                                    <div key={group.date} className="history-date-group">
                                        <div 
                                            className="history-date-header" 
                                            onClick={() => toggleGroup(group.date)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <i className={`fa-regular ${isCollapsed ? 'fa-folder' : 'fa-folder-open'}`} />
                                            <span>{group.date}</span>
                                            <i 
                                                className={`fa-solid fa-chevron-down history-date-chevron ${isCollapsed ? 'collapsed' : ''}`} 
                                                style={{ marginLeft: 'auto', fontSize: '10px', transition: 'transform 0.2s' }}
                                            />
                                        </div>
                                        <div className={`history-date-collapsible ${isCollapsed ? 'collapsed' : ''}`}>
                                            <div className="history-date-chats">
                                                {visibleChats.map(chat => (
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
                                                                
                                                            </div>
                                                        ) : (
                                                            <div className="history-item-preview">
                                                                {chat.title || chat.preview || 'Empty chat'}
                                                            </div>
                                                        )}
                                                        {renamingChatId !== chat.id && (
                                                            <button
                                                                className="history-diary-btn"
                                                                title="Context Diary"
                                                                onClick={async (e) => {
                                                                    e.stopPropagation()
                                                                    try {
                                                                        const res = await fetch(`${GATEWAY_URL}/history/${chat.id}`)
                                                                        const data = await res.json()
                                                                        setSelectedDiaryChat({ ...chat, context_diary: data.context_diary })
                                                                    } catch (err) {
                                                                        setSelectedDiaryChat(chat)
                                                                    }
                                                                }}
                                                            >
                                                                <i className="fa-solid fa-book-bookmark" />
                                                            </button>
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
                                                                {getRelativeTime(chat.updatedAt)}
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
                                            ))}
                                            {hasMore && !isFullyExpanded && (
                                                <button 
                                                    className="history-see-more-btn"
                                                    onClick={() => {
                                                        setExpandedGroups(prev => {
                                                            const next = new Set(prev);
                                                            next.add(group.date);
                                                            return next;
                                                        });
                                                    }}
                                                >
                                                    <span>Threads +{group.chats.length - 5}</span>
                                                    <img 
                                                        src={`/dot-dive/dotdive-${(Array.from(group.date).reduce((sum, char) => sum + char.charCodeAt(0), 0) % 6) + 1}.png`} 
                                                        alt=""
                                                        className="history-see-more-icon"
                                                    />
                                                </button>
                                            )}
                                        </div>
                                        </div>
                                    </div>
                                    );
                                });
                            })()}
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
                        {chatId && (
                            <button
                                className="header-action-btn"
                                title="Context Diary"
                                onClick={async () => {
                                    try {
                                        const res = await fetch(`${GATEWAY_URL}/history/${chatId}`)
                                        const data = await res.json()
                                        setSelectedDiaryChat({ id: chatId, context_diary: data.context_diary })
                                    } catch (err) {
                                        setSelectedDiaryChat({ id: chatId })
                                    }
                                }}
                            >
                                <i className="fa-solid fa-book-bookmark header-action-icon" style={{ fontSize: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }} />
                            </button>
                        )}
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

                                {awsConfigured === false && (
                                    <div className="aws-lock-banner" onClick={() => setShowSettings(true)}>
                                        <i className="fa-solid fa-lock" />
                                        <span>Click your profile to configure AWS keys and unlock chat.</span>
                                    </div>
                                )}

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
                                            className={`suggestion-btn ${awsConfigured === false ? 'disabled' : ''}`}
                                            onClick={() => {
                                                if (awsConfigured !== false) sendMessage(q.text)
                                            }}
                                        >
                                            <i className={q.icon}></i>
                                            {q.text}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            (() => {
                                // Group consecutive assistant messages into chains
                                const groups = []
                                for (let i = 0; i < messages.length; i++) {
                                    const msg = messages[i]
                                    if (msg.role === 'assistant' && groups.length > 0 && groups[groups.length - 1].role === 'assistant') {
                                        groups[groups.length - 1].msgs.push({ msg, idx: i })
                                    } else {
                                        groups.push({ role: msg.role, msgs: [{ msg, idx: i }] })
                                    }
                                }

                                return groups.map((group) => {
                                    const firstIdx = group.msgs[0].idx
                                    const lastIdx = group.msgs[group.msgs.length - 1].idx
                                    const firstMsg = group.msgs[0].msg
                                    const lastMsg = group.msgs[group.msgs.length - 1].msg
                                    const isEditingMode = editingIndex !== null
                                    const isFocused = isEditingMode && editingIndex === firstIdx
                                    const isDimmed = isEditingMode && editingIndex !== firstIdx
                                    const isLastStreaming = streaming && lastIdx === messages.length - 1

                                    if (group.role === 'user') {
                                        const msg = firstMsg
                                        const i = firstIdx
                                        return (
                                            <div
                                                key={i}
                                                id={`message-${i}`}
                                                className={`message user ${isFocused ? 'is-focused' : ''} ${isDimmed ? 'is-dimmed' : ''}`}
                                            >
                                                <div className="message-content">
                                                    <div className="message-body">
                                                        {msg.content[0].text}
                                                    </div>
                                                    <div className="message-actions" style={{ visibility: streaming ? 'hidden' : 'visible' }}>
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
                                                                            const targetScroll = msgEl.offsetTop - container.offsetTop - container.clientHeight + msgEl.clientHeight - 32;
                                                                            container.scrollTop = Math.max(0, targetScroll);
                                                                        }
                                                                    }, 10)
                                                                }}
                                                            >
                                                                <i className="fa-regular fa-pen-to-square" />
                                                            </button>
                                                        </div>
                                                </div>
                                            </div>
                                        )
                                    }

                                    // Assistant group (single message or chain)
                                    const chainTokens = lastMsg.total_tokens > 0 ? lastMsg.total_tokens : 0

                                    return (
                                        <div
                                            key={firstIdx}
                                            id={`message-${firstIdx}`}
                                            className={`message assistant ${isFocused ? 'is-focused' : ''} ${isDimmed ? 'is-dimmed' : ''}`}
                                        >
                                            <div className="assistant-avatar-container">
                                                <AnimatedAvatar
                                                    isStreaming={isLastStreaming}
                                                />
                                            </div>
                                            <div className="message-content">
                                                <div className="message-header">
                                                    <span className="message-sender">Model</span>
                                                    <span className="message-dot">•</span>
                                                    <span className="message-time">
                                                        {firstMsg.timestamp ? new Date(firstMsg.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '7:34 PM'}
                                                    </span>
                                                    {chainTokens > 0 && (
                                                        <span className="token-badge"><i className="fa-regular fa-comments" />+{chainTokens.toLocaleString()}</span>
                                                    )}
                                                </div>
                                                {group.msgs.map(({ msg, idx }) => (
                                                    <div key={idx} className="chain-step">
                                                        {msg.thinking && (
                                                            <details className={`thinking-block ${streaming && idx === messages.length - 1 ? 'streaming' : ''}`}>
                                                                <summary>
                                                                    <i className="fa-solid fa-brain" />
                                                                    <span>Thinking</span>
                                                                    {streaming && idx === messages.length - 1 && !msg.content[0].text && (
                                                                        <span className="thinking-spinner" />
                                                                    )}
                                                                </summary>
                                                                <div className="thinking-content">{msg.thinking}</div>
                                                            </details>
                                                        )}
                                                        <div className={`message-body ${streaming && idx === messages.length - 1 ? 'streaming' : ''}`}>
                                                            <div className="markdown-content">
                                                                {(() => {
                                                                    let t = msg.content[0].text
                                                                    t = t.replace(/<FUNCTION_CALL>[\s\S]*?<\/FUNCTION_CALL>/g, '')
                                                                    t = t.replace(/<CONTEXT>[\s\S]*?<\/CONTEXT>/g, '')
                                                                    t = t.replace(/^read\([^)]*\)\s*$/gm, '')

                                                                    const parts = t.split(/(\{\{(?:TOOL|READ):[^}]+\}\})/g)

                                                                    return parts.map((part, pidx) => {
                                                                        const toolMatch = part.match(/^\{\{(TOOL|READ):(.+)\}\}$/)
                                                                        if (toolMatch) {
                                                                            const markerType = toolMatch[1]
                                                                            const toolName = toolMatch[2]
                                                                            const appearance = getToolAppearance(toolName)
                                                                            const verb = markerType === 'READ' ? 'Read' : 'Executed'
                                                                            const icon = markerType === 'READ' ? 'fa-solid fa-book-open' : appearance.icon
                                                                            return (
                                                                                <div key={pidx} className="tool-execution-badge">
                                                                                    <i className={icon} style={markerType === 'READ' ? { fontSize: '1.15em' } : undefined}></i>
                                                                                    <span>{verb} <strong>{appearance.label}</strong></span>
                                                                                </div>
                                                                            )
                                                                        }
                                                                        const trimmed = part.trim()
                                                                        if (!trimmed) return null
                                                                        return (
                                                                            <ReactMarkdown key={pidx} remarkPlugins={[remarkGfm]}>
                                                                                {trimmed}
                                                                            </ReactMarkdown>
                                                                        )
                                                                    })
                                                                })()}
                                                            </div>
                                                            {streaming && idx === messages.length - 1 && !msg.processing && (
                                                                <span className="cursor" />
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                                <div className="message-actions" style={{ visibility: isLastStreaming ? 'hidden' : 'visible' }}>
                                                    <button
                                                        className="action-btn copy-action-btn"
                                                        title="Copy"
                                                        onClick={(e) => {
                                                                const allText = group.msgs.map(({ msg }) => msg.content[0].text).join('\n\n')
                                                                navigator.clipboard.writeText(allText)
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
                                                        <button
                                                            className="action-btn"
                                                            title="Rerun"
                                                            onClick={() => retryMessage(lastIdx)}
                                                        >
                                                            <i className="fa-solid fa-rotate-right" />
                                                        </button>
                                                    </div>
                                            </div>
                                        </div>
                                    )
                                })
                            })()
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
