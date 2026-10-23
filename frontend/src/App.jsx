
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity,
  ArrowUpRight,
  Bell,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  Home,
  Mic,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  Settings2,
  Sparkles,
  Target,
  Volume2,
  Zap,
  ChevronDown,
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
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      "Cannot connect to the backend. Check the Render service and CORS settings."
    );
  }

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }

  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("The backend returned an unexpected response.");
  }

  return response.json();
}

function normalizeTask(task) {
  return {
    id: task.id,
    title: task.title || "Untitled task",
    description: task.description || "Personal task",
    due: task.due_date || task.due || "No deadline",
    priority: task.priority || "Medium",
    completed:
      task.completed === true ||
      task.done === true ||
      String(task.status || "").toLowerCase() === "completed",
  };
}

const suggestions = [
  "What should I focus on today?",
  "Help me prioritize my assignments",
  "Plan my day around my classes",
];

const schedule = [
  {
    time: "10:00 AM",
    title: "Machine Learning lecture",
    details: "10:00–11:30 · Campus",
  },
  {
    time: "2:00 PM",
    title: "Design & Society seminar",
    details: "2:00–3:00 · Arts 112",
  },
  {
    time: "4:00 PM",
    title: "Linear regression review",
    details: "4:00–5:15 · Study session",
  },
  {
    time: "6:00 PM",
    title: "Finish the ML lab report",
    details: "6:00 PM · Study session",
  },
];

export default function App() {
  const [page, setPage] = useState("Today");
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [listening, setListening] = useState(false);

  async function loadTasks() {
    setTasksLoading(true);
    setTasksError("");

    try {
      const data = await apiRequest("/tasks");
      const list = Array.isArray(data)
        ? data
        : Array.isArray(data?.tasks)
          ? data.tasks
          : [];

      setTasks(list.map(normalizeTask));
    } catch (error) {
      setTasksError(error.message || "Unable to load tasks.");
    } finally {
      setTasksLoading(false);
    }
  }

  useEffect(() => {
    loadTasks();
  }, []);

  const completedCount = tasks.filter((task) => task.completed).length;
  const progress = tasks.length
    ? (completedCount / tasks.length) * 100
    : 0;

  async function sendMessage(text = message) {
    const prompt = text.trim();

    if (!prompt || chatLoading) return;

    setMessages((current) => [
      ...current,
      { role: "user", text: prompt },
    ]);
    setMessage("");
    setChatError("");
    setChatLoading(true);
    setPage("Assistant");

    try {
      const payload = { message: prompt };

      if (conversationId) {
        payload.conversation_id = conversationId;
      }

      const data = await apiRequest("/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (data?.conversation_id) {
        setConversationId(data.conversation_id);
      }

      // Support common response field names used by FastAPI agents.
      const answer =
        typeof data === "string"
          ? data
          : data?.response_text ??
            data?.response ??
            data?.reply ??
            data?.answer ??
            data?.message;

      if (typeof answer !== "string" || !answer.trim()) {
        throw new Error(
          "The backend did not return an assistant response. Check the /api/chat response in agent/server.py."
        );
      }

      setMessages((current) => [
        ...current,
        { role: "assistant", text: answer },
      ]);
    } catch (error) {
      setChatError(error.message || "Unable to get an assistant response.");
    } finally {
      setChatLoading(false);
    }
  }

  function toggleTask(id) {
    // UI-only until a task update endpoint is implemented on the backend.
    setTasks((current) =>
      current.map((task) =>
        task.id === id
          ? { ...task, completed: !task.completed }
          : task
      )
    );
    setTasksError(
      "Completion changes are currently local to this page and may not persist after refreshing."
    );
  }

  function createTask() {
    setTasksError(
      "Task creation is not connected yet. A task-creation endpoint is needed in the backend."
    );
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(null);
    setChatError("");
    setMessage("");
  }

  function handleMic() {
    setListening((current) => !current);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setPage("Today")}>
          <span className="brand-mark">
            <Activity size={21} />
          </span>
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
            {name === "Tasks" && (
              <span className="nav-count">
                {tasks.filter((task) => !task.completed).length}
              </span>
            )}
          </button>
        ))}

        <div className="nav-label space-label">YOUR SPACE</div>

        <button
          className="space-item"
          onClick={() => setPage("Study plan")}
        >
          <span className="dot purple-dot" />
          Exam week prep
        </button>

        <button
          className="space-item"
          onClick={() => setPage("Study plan")}
        >
          <span className="dot teal-dot" />
          Machine Learning
        </button>

        <div className="sidebar-bottom">
          <div className="sync-card">
            <span className="sync-dot" />
            <strong>Workspace ready</strong>
            <p>Your personal planning space</p>
          </div>

          <button className="profile" onClick={() => setPage("Settings")}>
            <span className="avatar">JD</span>
            <span className="profile-text">
              <strong>Jamie Davis</strong>
              <small>Personal workspace</small>
            </span>
            <Settings2 size={16} />
          </button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            My workspace <span>/</span> <strong>{page}</strong>
          </div>

          <div className="top-actions">
            <span className="today-date">PERSONAL WORKSPACE</span>
            <button className="icon-button" aria-label="Search">
              <Search size={17} />
            </button>
            <button className="icon-button" aria-label="Notifications">
              <Bell size={17} />
            </button>
            <button className="workspace-pill">
              Personal <ChevronDown size={13} />
            </button>
          </div>
        </header>

        {page === "Today" && (
          <section className="page-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <Sparkles size={13} /> YOUR DAY, CONNECTED
                </span>
                <h1>A little clarity for your day.</h1>
                <p>Your life, organized. Your next move, handled.</p>
              </div>
              <button
                className="primary-button"
                onClick={() => setPage("Assistant")}
              >
                <Sparkles size={15} /> Ask LifePilot
              </button>
            </div>

            <div className="hero-card">
              <div className="hero-copy">
                <span className="eyebrow">YOUR PERSONAL AI</span>
                <h2>One focused session. A calmer week.</h2>
                <p>
                  Your ML exam is approaching. Start with linear
                  regression, then make progress on your lab report.
                </p>
                <button
                  className="primary-button"
                  onClick={() => setPage("Study plan")}
                >
                  <Zap size={15} /> Start my focus session
                </button>
              </div>
              <div className="voice-orb">
                <Volume2 size={30} />
              </div>
              <span className="orb-caption">Here when you need me.</span>
            </div>

            <div className="dashboard-grid">
              <section className="panel tasks-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Your next moves</h3>
                    <p>Your tasks, all in one place.</p>
                  </div>
                  <button
                    className="text-link"
                    onClick={() => setPage("Tasks")}
                  >
                    All tasks <ArrowUpRight size={14} />
                  </button>
                </div>

                <div className="task-list">
                  {tasksLoading && (
                    <p className="muted">Loading tasks...</p>
                  )}
                  {tasksError && (
                    <p className="muted" role="alert">{tasksError}</p>
                  )}
                  {!tasksLoading && !tasksError && tasks.length === 0 && (
                    <p className="muted">No tasks found yet.</p>
                  )}
                  {tasks.map((task) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      onToggle={toggleTask}
                    />
                  ))}
                </div>

                <div className="task-footer">
                  <span>
                    {completedCount} of {tasks.length} tasks completed
                  </span>
                  <div className="progress-track">
                    <span style={{ width: `${progress}%` }} />
                  </div>
                </div>
              </section>

              <section className="panel schedule-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Room for what matters</h3>
                    <p><span className="sync-dot" /> Your day at a glance</p>
                  </div>
                  <MoreHorizontal size={18} />
                </div>

                {schedule.slice(0, 3).map((item) => (
                  <div className="timeline-row" key={item.title}>
                    <span className="timeline-time">{item.time}</span>
                    <span className="timeline-line" />
                    <div>
                      <strong>{item.title}</strong>
                      <small>{item.details}</small>
                    </div>
                  </div>
                ))}

                <button
                  className="text-link schedule-link"
                  onClick={() => setPage("Calendar")}
                >
                  Open my schedule <ArrowUpRight size={14} />
                </button>
              </section>
            </div>

            <div className="suggestion-row">
              <span>Need a hand?</span>
              {suggestions.map((item) => (
                <button
                  key={item}
                  disabled={chatLoading}
                  onClick={() => sendMessage(item)}
                >
                  {item}
                </button>
              ))}
            </div>

            <ChatComposer
              value={message}
              onChange={setMessage}
              onSend={() => sendMessage()}
              listening={listening}
              onMic={handleMic}
              disabled={chatLoading}
            />

            <p className="privacy-note">
              Your AI assistant is here to help. You stay in control of
              what gets added.
            </p>
          </section>
        )}

        {page === "Assistant" && (
          <section className="assistant-page">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <Sparkles size={13} /> YOUR PLANNING COPILOT
                </span>
                <h1>Big goals. Manageable steps.</h1>
                <p>
                  A little context is all it takes. Let&apos;s make a plan.
                </p>
              </div>
              <button
                className="secondary-button"
                onClick={startNewConversation}
              >
                <Plus size={15} /> New conversation
              </button>
            </div>

            <div className="chat-layout">
              <div className="chat-main">
                {chatError && (
                  <p className="muted" role="alert">{chatError}</p>
                )}

                {messages.length === 0 ? (
                  <div className="welcome-message">
                    <span className="assistant-avatar">
                      <Sparkles size={18} />
                    </span>
                    <div>
                      <strong>Hi! I&apos;m LifePilot.</strong>
                      <p>
                        Tell me what&apos;s on your mind. We can plan your
                        studies, prioritize assignments, or organize your day.
                      </p>
                    </div>
                  </div>
                ) : (
                  messages.map((item, index) => (
                    <div
                      className={`chat-message ${item.role}`}
                      key={`${item.role}-${index}`}
                    >
                      {item.role === "assistant" && (
                        <span className="assistant-avatar">
                          <Sparkles size={16} />
                        </span>
                      )}
                      <div className="message-bubble">
                        {item.role === "assistant" ? (
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {item.text}
                          </ReactMarkdown>
                        ) : (
                          item.text
                        )}
                      </div>
                    </div>
                  ))
                )}

                {chatLoading && (
                  <p className="muted" role="status">
                    LifePilot is thinking...
                  </p>
                )}

                <div className="chat-suggestions">
                  {suggestions.map((item) => (
                    <button
                      key={item}
                      disabled={chatLoading}
                      onClick={() => sendMessage(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>

                <ChatComposer
                  value={message}
                  onChange={setMessage}
                  onSend={() => sendMessage()}
                  listening={listening}
                  onMic={handleMic}
                  disabled={chatLoading}
                />

                <p className="privacy-note">
                  Connected to your deployed FastAPI assistant.
                </p>
              </div>

              <aside className="chat-side">
                <div className="panel side-hero">
                  <span className="eyebrow">✦ READY WHEN YOU ARE</span>
                  <h3>From conversation to a clear next move.</h3>
                  <p>
                    Share your goals. LifePilot helps turn them into a
                    plan with time set aside.
                  </p>
                  <div className="side-stats">
                    <strong>5<small>study sessions</small></strong>
                    <strong>6h 15m<small>protected time</small></strong>
                  </div>
                  <button
                    className="primary-button"
                    onClick={() => setPage("Study plan")}
                  >
                    Open study plan <ArrowUpRight size={14} />
                  </button>
                </div>

                <div className="panel next-session">
                  <span className="eyebrow">UP FIRST · TODAY</span>
                  <h4>
                    <BookOpen size={15} /> Linear regression &amp; loss
                    functions
                  </h4>
                  <p>
                    <Clock3 size={13} /> 4:00–5:15 PM · 75 minutes
                  </p>
                  <button
                    className="text-link"
                    onClick={() => setPage("Study plan")}
                  >
                    View session <ArrowUpRight size={14} />
                  </button>
                </div>
              </aside>
            </div>
          </section>
        )}

        {page === "Study plan" && (
          <section className="page-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <BookOpen size={13} /> YOUR LEARNING SPACE
                </span>
                <h1>A plan that fits your life.</h1>
                <p>Exam prep, real classes, and enough room to breathe.</p>
              </div>
              <button
                className="primary-button"
                onClick={() =>
                  sendMessage("Help me adjust my study plan around my deadlines.")
                }
              >
                <Sparkles size={15} /> Adjust with AI
              </button>
            </div>

            <div className="study-banner panel">
              <div>
                <span className="eyebrow">ACTIVE PLAN</span>
                <h2>Machine Learning · Exam prep</h2>
                <p>Built around your classes and deadlines.</p>
              </div>
              <div className="study-stat">
                <strong>0 / 5</strong>
                <small>sessions completed</small>
              </div>
              <div className="study-stat">
                <strong>6h 15m</strong>
                <small>study time protected</small>
              </div>
            </div>

            <div className="panel week-panel">
              <div className="panel-heading">
                <div>
                  <h3>Your study week</h3>
                  <p>Illustrative study schedule</p>
                </div>
                <span className="priority">This week</span>
              </div>

              <div className="week-grid">
                {["MON", "TUE", "WED", "THU", "FRI"].map((day, i) => (
                  <div className="day-column" key={day}>
                    <strong>{day}</strong>
                    {[0, 1, 2, 3].map((slot) => {
                      const filled = (slot + i) % 3 === 0;
                      const labels = [
                        "ML lecture",
                        "Practice problems",
                        "Revision",
                      ];

                      return (
                        <div
                          key={slot}
                          className={`study-slot ${filled ? "filled" : ""}`}
                        >
                          {filled ? labels[i % labels.length] : ""}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>

            <div className="dashboard-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h3>Upcoming deadlines</h3>
                    <p>Keep the important things in view.</p>
                  </div>
                </div>
                {tasks.length === 0 && (
                  <p className="muted">No task deadlines available.</p>
                )}
                {tasks.map((task) => (
                  <div className="deadline-row" key={task.id}>
                    <Circle size={14} />
                    <span>{task.title}</span>
                    <small>{task.due}</small>
                  </div>
                ))}
              </section>

              <section className="panel">
                <span className="eyebrow">YOUR NEXT SESSION</span>
                <h3 className="session-title">
                  Linear regression &amp; loss functions
                </h3>
                <p className="muted">
                  75 minutes · Review concepts, practice problems, and recap.
                </p>
                <button
                  className="primary-button"
                  onClick={() => setPage("Assistant")}
                >
                  Ask LifePilot <ArrowUpRight size={14} />
                </button>
              </section>
            </div>
          </section>
        )}

        {page === "Tasks" && (
          <section className="page-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <Target size={13} /> YOUR TASKS
                </span>
                <h1>One step at a time.</h1>
                <p>Make progress without losing sight of what matters.</p>
              </div>
              <button className="primary-button" onClick={createTask}>
                <Plus size={15} /> Add task
              </button>
            </div>

            <section className="panel tasks-panel">
              <div className="panel-heading">
                <div>
                  <h3>All tasks</h3>
                  <p>
                    {tasks.filter((task) => !task.completed).length} tasks
                    remaining
                  </p>
                </div>
                <span className="priority">{completedCount} completed</span>
              </div>

              {tasksLoading && <p className="muted">Loading tasks...</p>}
              {tasksError && <p className="muted" role="alert">{tasksError}</p>}
              {!tasksLoading && tasks.length === 0 && !tasksError && (
                <p className="muted">No tasks yet.</p>
              )}

              {tasks.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onToggle={toggleTask}
                />
              ))}

              <button
                className="text-link"
                onClick={loadTasks}
                disabled={tasksLoading}
              >
                Refresh tasks <ArrowUpRight size={14} />
              </button>
            </section>
          </section>
        )}

        {page === "Calendar" && (
          <section className="page-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <CalendarDays size={13} /> YOUR SCHEDULE
                </span>
                <h1>Make room for what matters.</h1>
                <p>A clearer view of your day, one block at a time.</p>
              </div>
              <button
                className="primary-button"
                onClick={() => setPage("Study plan")}
              >
                View study plan <ArrowUpRight size={14} />
              </button>
            </div>

            <section className="panel">
              <h3>Today's timeline</h3>
              {schedule.map((item) => (
                <div className="calendar-event" key={item.title}>
                  <span>{item.time}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <small>{item.details}</small>
                  </div>
                </div>
              ))}
            </section>
          </section>
        )}

        {page === "Settings" && (
          <section className="page-content">
            <h1>Your workspace settings</h1>
            <p className="muted">Personal workspace · Demo profile</p>
            <section className="panel">
              <h3>Assistant preferences</h3>
              <p className="muted">
                The assistant connects to your deployed FastAPI backend.
                Voice input and persistent task updates need additional
                backend integration.
              </p>
              <p className="muted">API endpoint: {API_BASE}</p>
            </section>
          </section>
        )}

        <footer className="app-footer">
          <span><span className="sync-dot" /> LifePilot workspace ready</span>
          <span>Built for your next move <Sparkles size={12} /></span>
        </footer>
      </main>
    </div>
  );
}

function TaskRow({ task, onToggle }) {
  return (
    <div className={`task-row ${task.completed ? "task-done" : ""}`}>
      <button
        className="check-button"
        onClick={() => onToggle(task.id)}
        aria-label={
          task.completed
            ? `Mark ${task.title} incomplete`
            : `Mark ${task.title} complete`
        }
      >
        {task.completed ? (
          <CheckCircle2 size={17} />
        ) : (
          <Circle size={17} />
        )}
      </button>

      <div className="task-copy">
        <strong>{task.title}</strong>
        <small>{task.description}</small>
      </div>

      <div className="task-meta">
        <span
          className={`priority ${
            ["high", "urgent", "high priority"].includes(
              String(task.priority).toLowerCase()
            )
              ? "high"
              : ""
          }`}
        >
          {task.priority}
        </span>
        <small>{task.due}</small>
      </div>
    </div>
  );
}

function ChatComposer({
  value,
  onChange,
  onSend,
  listening,
  onMic,
  disabled = false,
}) {
  return (
    <form
      className="chat-composer"
      onSubmit={(event) => {
        event.preventDefault();
        onSend();
      }}
    >
      <Plus size={17} className="composer-plus" />

      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={
          listening
            ? "Voice input is not connected yet..."
            : "Ask anything, or tell me what's on your mind..."
        }
        aria-label="Message LifePilot"
        disabled={disabled}
      />

      <button
        type="button"
        className={`mic-button ${listening ? "listening" : ""}`}
        onClick={onMic}
        aria-label="Toggle microphone"
        title="Voice input demo"
      >
        <Mic size={17} />
      </button>

      <button
        type="submit"
        className="send-button"
        aria-label="Send message"
        disabled={disabled || !value.trim()}
      >
        <Send size={16} />
      </button>
    </form>
  );
}
