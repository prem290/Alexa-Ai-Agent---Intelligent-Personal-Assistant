
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity, ArrowUpRight, Bell, BookOpen, CalendarDays,
  Check, CheckCircle2, ChevronDown, Circle, Clock3, Command,
  Home, Mic, MoreHorizontal, Plus, Search, Send, Settings2,
  Sparkles, Target, TrendingUp, Volume2, Zap
} from "lucide-react";
import "./App.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE ||
  "https://alexa-ai-agent-intelligent-personal.onrender.com/api"
).replace(/\/+$/, "");

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error(
      "Cannot connect to the backend. Check the Render service and backend CORS settings."
    );
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }

  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    return text;
  }
  return response.json();
}

function mapBackendTask(task) {
  const priorityLabels = {
    urgent: "Urgent",
    high: "High priority",
    medium: "Medium",
    low: "Low",
  };

  return {
    id: task.id,
    title: task.title,
    category: task.description || "Personal task",
    due: task.due_date || "No deadline",
    priority: priorityLabels[task.priority] || "Medium",
    done: task.status === "completed",
  };
}

const suggestions = [
  "What should I focus on today?",
  "Help me prioritize my assignments",
  "Plan my day around my classes",
];

export default function App() {
  const [page, setPage] = useState("Today");
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [listening, setListening] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadTasks() {
      try {
        setTasksError("");
        const data = await apiRequest("/tasks");
        if (active) setTasks((data.tasks || []).map(mapBackendTask));
      } catch (error) {
        if (active) setTasksError(error.message || "Could not load tasks.");
      } finally {
        if (active) setTasksLoading(false);
      }
    }

    loadTasks();
    return () => { active = false; };
  }, []);

  const completed = tasks.filter((task) => task.done).length;
  const progress = tasks.length ? (completed / tasks.length) * 100 : 0;

  async function sendMessage(text = message) {
    const prompt = text.trim();
    if (!prompt || chatLoading) return;

    setMessages((current) => [...current, { role: "user", text: prompt }]);
    setMessage("");
    setChatError("");
    setChatLoading(true);
    setPage("Assistant");

    try {
      const payload = { message: prompt };
      if (conversationId) payload.conversation_id = conversationId;
      const data = await apiRequest("/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (data.conversation_id) setConversationId(data.conversation_id);
      // Accept the response field used by the current FastAPI schema and common aliases.
      const answer = typeof data === "string"
        ? data
        : data?.response_text ?? data?.response ?? data?.reply ?? data?.answer ?? data?.message;

      if (typeof answer !== "string" || !answer.trim()) {
        throw new Error(
          "The backend returned no assistant response. Check the /api/chat response in agent/server.py."
        );
      }

      setMessages((current) => [...current, { role: "assistant", text: answer }]);
    } catch (error) {
      setChatError(error.message || "Could not connect to the assistant.");
    } finally {
      setChatLoading(false);
    }
  }

  async function toggleTask(id) {
    // Task status changes are kept local until connected to the backend's task tools.
    setTasks((current) => current.map((task) =>
      task.id === id ? { ...task, done: !task.done } : task
    ));
  }

  async function createTask() {
    const title = window.prompt("What task would you like to add?");
    if (!title?.trim()) return;
    setTasksError("Task creation is not connected yet. Use the backend task tools to persist new tasks.");
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(null);
    setChatError("");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setPage("Today")}>
          <span className="brand-mark"><Activity size={21} /></span>
          <span>
            <strong>Alexa + LifePilot</strong>
            <small>YOUR PERSONAL AI</small>
          </span>
        </button>

        <div className="nav-label">YOUR WORKSPACE</div>
        {[
          { name: "Today", icon: Home },
          { name: "Assistant", icon: Sparkles },
          { name: "Study plan", icon: BookOpen },
          { name: "Tasks", icon: CheckCircle2 },
          { name: "Calendar", icon: CalendarDays },
        ].map(({ name, icon: Icon }) => (
          <button
            key={name}
            className={`nav-item ${page === name ? "active" : ""}`}
            onClick={() => setPage(name)}
          >
            <Icon size={17} />
            <span>{name}</span>
            {name === "Tasks" && <span className="nav-count">{tasks.filter(t => !t.done).length}</span>}
          </button>
        ))}

        <div className="nav-label space-label">YOUR SPACE</div>
        <button className="space-item" onClick={() => setPage("Study plan")}>
          <span className="dot purple-dot" /> Exam week prep
        </button>
        <button className="space-item" onClick={() => setPage("Study plan")}>
          <span className="dot teal-dot" /> Machine Learning
        </button>

        <div className="sidebar-bottom">
          <div className="sync-card">
            <span className="sync-dot" />
            <strong>Workspace ready</strong>
            <p>Your personal planning space</p>
          </div>
          <button className="profile" onClick={() => setPage("Settings")}>
            <span className="avatar">JD</span>
            <span className="profile-text"><strong>Jamie Davis</strong><small>Personal workspace</small></span>
            <Settings2 size={16} />
          </button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">My workspace <span>/</span> <strong>{page}</strong></div>
          <div className="top-actions">
            <span className="today-date">PERSONAL WORKSPACE</span>
            <button className="icon-button" aria-label="Search"><Search size={17} /></button>
            <button className="icon-button" aria-label="Notifications"><Bell size={17} /></button>
            <button className="workspace-pill">Personal <ChevronDown size={13} /></button>
          </div>
        </header>

        {page === "Today" && (
          <section className="page-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow"><Sparkles size={13} /> YOUR DAY, CONNECTED</span>
                <h1>A little clarity for your day.</h1>
                <p>Your life, organized. Your next move, handled.</p>
              </div>
              <button className="primary-button" onClick={() => setPage("Assistant")}><Sparkles size={15} /> Ask LifePilot</button>
            </div>

            <div className="hero-card">
              <div className="hero-copy">
                <span className="eyebrow">YOUR PERSONAL AI</span>
                <h2>One focused session. A calmer week.</h2>
                <p>Your ML exam is approaching. Start with linear regression, then make progress on your lab report due Wednesday.</p>
                <button className="primary-button" onClick={() => setPage("Study plan")}><Zap size={15} /> Start my focus session</button>
              </div>
              <div className="voice-orb"><Volume2 size={30} /></div>
              <span className="orb-caption">Here when you need me.</span>
            </div>

            <div className="dashboard-grid">
              <section className="panel tasks-panel">
                <div className="panel-heading">
                  <div><h3>Your next moves</h3><p>Three deadlines this week. A clear place to start.</p></div>
                  <button className="text-link" onClick={() => setPage("Tasks")}>All tasks <ArrowUpRight size={14} /></button>
                </div>
                <div className="task-list">
                  {tasksLoading && <p className="muted">Loading tasks from backend...</p>}
                  {tasksError && <p className="muted" role="alert">{tasksError}</p>}
                  {!tasksLoading && !tasksError && tasks.length === 0 && <p className="muted">No tasks found yet.</p>}
                  {tasks.map((task) => (
                    <div className={`task-row ${task.done ? "task-done" : ""}`} key={task.id}>
                      <button className="check-button" onClick={() => toggleTask(task.id)} aria-label="Toggle task">
                        {task.done ? <CheckCircle2 size={17} /> : <Circle size={17} />}
                      </button>
                      <div className="task-copy"><strong>{task.title}</strong><small>{task.category}</small></div>
                      <div className="task-meta"><span className={`priority ${task.priority === "High priority" ? "high" : ""}`}>{task.priority}</span><small>{task.due}</small></div>
                    </div>
                  ))}
                </div>
                <div className="task-footer"><span>{completed} of {tasks.length} tasks completed today</span><div className="progress-track"><span style={{ width: `${progress}%` }} /></div></div>
              </section>

              <section className="panel schedule-panel">
                <div className="panel-heading"><div><h3>Room for what matters</h3><p><span className="sync-dot" /> Your day at a glance</p></div><MoreHorizontal size={18} /></div>
                {[
                  ["10:00", "Machine Learning lecture", "10:00–11:30 · Campus"],
                  ["14:00", "Design & Society seminar", "14:00–15:00 · Arts 112"],
                  ["16:00", "Linear regression review", "16:00–17:15 · Study session"],
                ].map(([time, title, subtitle]) => (
                  <div className="timeline-row" key={title}><span className="timeline-time">{time}</span><span className="timeline-line" /><div><strong>{title}</strong><small>{subtitle}</small></div></div>
                ))}
                <button className="text-link schedule-link" onClick={() => setPage("Calendar")}>Open my schedule <ArrowUpRight size={14} /></button>
              </section>
            </div>

            <div className="suggestion-row">
              <span>Need a hand?</span>
              {suggestions.map((item) => <button key={item} onClick={() => sendMessage(item)}>{item}</button>)}
            </div>
            <ChatComposer value={message} onChange={setMessage} onSend={() => sendMessage()} listening={listening} onMic={() => setListening(!listening)} />
            <p className="privacy-note">Your AI assistant is here to help. You stay in control of what gets added.</p>
          </section>
        )}

        {page === "Assistant" && (
          <section className="assistant-page">
            <div className="page-heading">
              <div><span className="eyebrow"><Sparkles size={13} /> YOUR PLANNING COPILOT</span><h1>Big goals. Manageable steps.</h1><p>A little context is all it takes. Let's make a plan.</p></div>
              <button className="secondary-button" onClick={startNewConversation}><Plus size={15} /> New conversation</button>
            </div>
            <div className="chat-layout">
              <div className="chat-main">
                {chatError && <p className="muted" role="alert">{chatError}</p>}
                {messages.length === 0 ? (
                  <div className="welcome-message"><span className="assistant-avatar"><Sparkles size={18} /></span><div><strong>Hi! I'm LifePilot.</strong><p>Tell me what's on your mind. We can plan your studies, prioritize assignments, or organize your day.</p></div></div>
                ) : messages.map((item, index) => (
                  <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}>
                    {item.role === "assistant" && <span className="assistant-avatar"><Sparkles size={16} /></span>}
                    <div className="message-bubble">
                      {item.role === "assistant" ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {item.text}
                        </ReactMarkdown>
                      ) : item.text}
                    </div>
                  </div>
                ))}
                <div className="chat-suggestions">{suggestions.map((item) => <button key={item} disabled={chatLoading} onClick={() => sendMessage(item)}>{item}</button>)}</div>
                {chatLoading && <p className="muted" role="status">LifePilot is thinking...</p>}
                <ChatComposer value={message} onChange={setMessage} onSend={() => sendMessage()} listening={listening} onMic={() => setListening(!listening)} />
                <p className="privacy-note">Connected to your FastAPI assistant when the backend is running.</p>
              </div>
              <aside className="chat-side">
                <div className="panel side-hero"><span className="eyebrow">✦ READY WHEN YOU ARE</span><h3>From conversation to a clear next move.</h3><p>Share your goals. LifePilot helps turn them into a plan with time set aside.</p><div className="side-stats"><strong>5<small>study sessions</small></strong><strong>6h 15m<small>protected time</small></strong></div><button className="primary-button" onClick={() => setPage("Study plan")}>Open study plan <ArrowUpRight size={14} /></button></div>
                <div className="panel next-session"><span className="eyebrow">UP FIRST · TODAY</span><h4><BookOpen size={15} /> Linear regression & loss functions</h4><p><Clock3 size={13} /> 4:00–5:15 PM · 75 minutes</p><button className="text-link" onClick={() => setPage("Study plan")}>View session <ArrowUpRight size={14} /></button></div>
              </aside>
            </div>
          </section>
        )}

        {page === "Study plan" && (
          <section className="page-content">
            <div className="page-heading"><div><span className="eyebrow"><BookOpen size={13} /> YOUR LEARNING SPACE</span><h1>A plan that fits your life.</h1><p>Exam prep, real classes, and enough room to breathe.</p></div><button className="primary-button" onClick={() => sendMessage("Help me adjust my study plan around my deadlines.")}><Sparkles size={15} /> Adjust with AI</button></div>
            <div className="study-banner panel"><div><span className="eyebrow">ACTIVE PLAN</span><h2>Machine Learning · Exam prep</h2><p>Exam on Monday · Built around your classes and deadlines</p></div><div className="study-stat"><strong>0 / 5</strong><small>sessions completed</small></div><div className="study-stat"><strong>6h 15m</strong><small>study time protected</small></div></div>
            <div className="panel week-panel"><div className="panel-heading"><div><h3>Your study week</h3><p>Illustrative schedule · October 19–23</p></div><span className="priority">This week</span></div>
              <div className="week-grid">{["MON 19","TUE 20","WED 21","THU 22","FRI 23"].map((day, i) => <div className="day-column" key={day}><strong>{day}</strong>{[0,1,2,3].map((slot) => <div key={slot} className={`study-slot ${((slot + i) % 3 === 0) ? "filled" : ""}`}>{((slot + i) % 3 === 0) ? ["ML lecture","Practice problems","Revision"][i % 3] : ""}</div>)}</div>)}</div>
            </div>
            <div className="dashboard-grid"><section className="panel"><div className="panel-heading"><div><h3>Upcoming deadlines</h3><p>Keep the important things in view.</p></div></div>{tasks.map((t) => <div className="deadline-row" key={t.id}><Circle size={14}/><span>{t.title}</span><small>{t.due}</small></div>)}</section><section className="panel"><span className="eyebrow">YOUR NEXT SESSION</span><h3 className="session-title">Linear regression & loss functions</h3><p className="muted">75 minutes · Review concepts, practice problems, and recap.</p><button className="primary-button" onClick={() => setPage("Assistant")}>Ask LifePilot <ArrowUpRight size={14} /></button></section></div>
          </section>
        )}

        {page === "Tasks" && (
          <section className="page-content">
            <div className="page-heading"><div><span className="eyebrow"><Target size={13} /> YOUR TASKS</span><h1>One step at a time.</h1><p>Make progress without losing sight of what matters.</p></div><button className="primary-button" onClick={createTask}><Plus size={15} /> Add task</button></div>
            <section className="panel tasks-panel">{tasksLoading && <p className="muted">Loading tasks from backend...</p>}{tasksError && <p className="muted" role="alert">{tasksError}</p>}<div className="panel-heading"><div><h3>All tasks</h3><p>{tasks.filter(t => !t.done).length} tasks remaining</p></div><span className="priority">{completed} completed</span></div>{tasks.map((task) => <div className={`task-row ${task.done ? "task-done" : ""}`} key={task.id}><button className="check-button" onClick={() => toggleTask(task.id)}>{task.done ? <CheckCircle2 size={17}/> : <Circle size={17}/>}</button><div className="task-copy"><strong>{task.title}</strong><small>{task.category}</small></div><div className="task-meta"><span className="priority">{task.priority}</span><small>{task.due}</small></div></div>)}</section>
          </section>
        )}

        {page === "Calendar" && (
          <section className="page-content">
            <div className="page-heading"><div><span className="eyebrow"><CalendarDays size={13}/> YOUR SCHEDULE</span><h1>Make room for what matters.</h1><p>A clearer view of your day, one block at a time.</p></div><button className="primary-button" onClick={() => setPage("Study plan")}>View study plan <ArrowUpRight size={14}/></button></div>
            <section className="panel"><h3>Today's timeline</h3>{[["10:00 AM","Machine Learning lecture"],["2:00 PM","Design & Society seminar"],["4:00 PM","Linear regression review"],["6:00 PM","Finish the ML lab report"]].map(([time, title]) => <div className="calendar-event" key={title}><span>{time}</span><div><strong>{title}</strong><small>Planned activity</small></div></div>)}</section>
          </section>
        )}

        {page === "Settings" && <section className="page-content"><h1>Your workspace settings</h1><p className="muted">Personal workspace · Demo profile</p><section className="panel"><h3>Assistant preferences</h3><p className="muted">Your UI is running in local demo mode. Backend and voice integrations can be added next.</p></section></section>}

        <footer className="app-footer"><span><span className="sync-dot" /> LifePilot workspace ready</span><span>Built for your next move <Sparkles size={12}/></span></footer>
      </main>
    </div>
  );
}

function ChatComposer({ value, onChange, onSend, listening, onMic }) {
  return (
    <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); onSend(); }}>
      <Plus size={17} className="composer-plus" />
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={listening ? "Voice input is a UI demo for now..." : "Ask anything, or tell me what's on your mind..."} aria-label="Message LifePilot" />
      <button type="button" className={`mic-button ${listening ? "listening" : ""}`} onClick={onMic} aria-label="Toggle microphone"><Mic size={17} /></button>
      <button type="submit" className="send-button" aria-label="Send message" disabled={!value.trim()}><Send size={16} /></button>
    </form>
  );
}
