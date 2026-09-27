import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Compass,
  Crosshair,
  Info,
  MessageCircle,
  Milestone,
  RotateCcw,
  Send,
  X,
} from "lucide-react";
import { useGuide } from "./GuideProvider";
import {
  DEMO_PATH,
  PAGES,
  ROLE_LABELS,
  SUGGESTED_BY_PAGE,
  TIPS,
  answerQuestion,
} from "./guideContent";

const FALLBACK_SUGGESTIONS = [
  "Where should I start?",
  "How is tampering prevented?",
  "What is the Section 63 certificate?",
  "How does contradiction detection work?",
];

function isTyping(el) {
  return el?.closest?.("input, textarea, select, [contenteditable='true']");
}

export default function GuideAssistant() {
  const g = useGuide();
  const nav = useNavigate();
  const panelRef = useRef(null);
  const [tab, setTab] = useState("page");
  // Lives here so the conversation survives switching tabs and pages.
  const [messages, setMessages] = useState([]);
  const [discovered, setDiscovered] = useState(() => {
    try {
      return localStorage.getItem("nv_guide_opened") === "1";
    } catch {
      return false;
    }
  });
  const { panelOpen, setPanelOpen } = g;

  useEffect(() => {
    function onKey(e) {
      if (e.key === "?" && !e.ctrlKey && !e.metaKey && !isTyping(e.target)) {
        e.preventDefault();
        setPanelOpen((v) => !v);
      } else if (e.key === "Escape" && panelRef.current?.contains(document.activeElement)) {
        setPanelOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setPanelOpen]);

  useEffect(() => {
    if (!panelOpen) return;
    panelRef.current?.focus();
    if (!discovered) {
      setDiscovered(true);
      try {
        localStorage.setItem("nv_guide_opened", "1");
      } catch {
        // Only affects the launcher's attention pulse.
      }
    }
  }, [panelOpen, discovered]);

  // On narrow screens the panel covers the page, so step aside before pointing.
  function pointAt(key) {
    if (window.matchMedia("(max-width: 640px)").matches) setPanelOpen(false);
    return g.showMe(key);
  }

  return (
    <>
      {panelOpen ? (
        <section
          ref={panelRef}
          className="guide-panel"
          role="dialog"
          aria-label="Nyaya Guide"
          tabIndex={-1}
        >
          <header className="guide-head">
            <div className="guide-head-title">
              <span className="guide-mark"><Compass size={18} /></span>
              <div>
                <strong>Nyaya Guide</strong>
                <small>{PAGES[g.pageId]?.title}</small>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={g.tipsOn}
              className={`guide-switch ${g.tipsOn ? "on" : ""}`}
              onClick={() => g.setTipsOn((v) => !v)}
            >
              <span className="guide-switch-track"><span /></span>
              Hover tips
            </button>
            <button
              type="button"
              className="guide-icon-btn"
              aria-label="Close guide"
              onClick={() => setPanelOpen(false)}
            >
              <X size={17} />
            </button>
          </header>
          <nav className="guide-tabs" aria-label="Guide sections">
            {[
              ["page", "This page", Info],
              ["path", "Demo path", Milestone],
              ["ask", "Ask", MessageCircle],
            ].map(([id, label, icon]) => {
              const Icon = icon;
              return (
                <button
                  key={id}
                  type="button"
                  aria-pressed={tab === id}
                  className={tab === id ? "active" : ""}
                  onClick={() => setTab(id)}
                >
                  <Icon size={15} /> {label}
                </button>
              );
            })}
          </nav>
          <div className="guide-body">
            {tab === "page" ? <PageTab pointAt={pointAt} /> : null}
            {tab === "path" ? <PathTab nav={nav} /> : null}
            {tab === "ask" ? (
              <AskTab
                pointAt={pointAt}
                nav={nav}
                setTab={setTab}
                messages={messages}
                setMessages={setMessages}
              />
            ) : null}
          </div>
          <footer className="guide-foot">
            Press <kbd>?</kbd> to open or close · <kbd>Esc</kbd> hides a tip
          </footer>
        </section>
      ) : null}
      <button
        type="button"
        data-guide="guide-launcher"
        className={`guide-launcher ${panelOpen ? "open" : ""} ${discovered ? "" : "pulse"}`}
        aria-expanded={panelOpen}
        onClick={() => setPanelOpen((v) => !v)}
      >
        {panelOpen ? <X size={18} /> : <Compass size={18} />}
        <span>{panelOpen ? "Close" : "Guide"}</span>
      </button>
    </>
  );
}

function PageTab({ pointAt }) {
  const { pageId, role } = useGuide();
  const page = PAGES[pageId];
  const [missing, setMissing] = useState({});
  useEffect(() => setMissing({}), [pageId]);
  if (!page) return null;
  return (
    <div className="guide-page">
      <h3>{page.title}</h3>
      <p className="guide-summary">{page.summary}</p>
      <p className="guide-label">Try this</p>
      <ol className="guide-steps">
        {page.steps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      {page.highlights.length ? (
        <>
          <p className="guide-label">What's on this page</p>
          <ul className="guide-spots">
            {page.highlights.map((key) => {
              const tip = TIPS[key];
              const restricted = tip.roles && !tip.roles.includes(role);
              return (
                <li key={key}>
                  <div>
                    <strong>{tip.title}</strong>
                    <span>{tip.body}</span>
                    {missing[key] ? (
                      <em>
                        {restricted
                          ? `Only shown to: ${tip.roles.map((r) => ROLE_LABELS[r]).join(", ")}.`
                          : "Not on screen right now. It may need data first, or sits in another tab."}
                      </em>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="guide-chip-btn"
                    onClick={() => setMissing((m) => ({ ...m, [key]: !pointAt(key) }))}
                  >
                    <Crosshair size={14} /> Show me
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
      <p className="guide-hint">
        Tip: with Hover tips on, rest the pointer on any button or panel to see what it does.
      </p>
    </div>
  );
}

function PathTab({ nav }) {
  const { pageId, visited, lastCaseId, resetProgress } = useGuide();
  const [note, setNote] = useState("");
  const done = DEMO_PATH.filter((s) => visited.includes(s.page)).length;
  const next = DEMO_PATH.find((s) => !visited.includes(s.page));

  function go(stop) {
    setNote("");
    if (stop.to) return nav(stop.to);
    if (!lastCaseId) {
      setNote("Open any case from the register first; the rest of the path continues from that case.");
      return nav("/cases");
    }
    if (stop.needs === "document") {
      setNote("Now click any row in the evidence register to open it.");
      return nav(`/cases/${lastCaseId}/documents`);
    }
    return nav(`/cases/${lastCaseId}/${stop.tab}`);
  }

  return (
    <div className="guide-path">
      <div className="guide-progress">
        <div>
          <strong>{done} of {DEMO_PATH.length}</strong> stops visited
        </div>
        <div className="guide-progress-bar" aria-hidden="true">
          <span style={{ width: `${(done / DEMO_PATH.length) * 100}%` }} />
        </div>
      </div>
      {note ? <p className="guide-note">{note}</p> : null}
      <ol className="guide-stops">
        {DEMO_PATH.map((stop, i) => {
          const isDone = visited.includes(stop.page);
          const here = stop.page === pageId;
          return (
            <li key={stop.page} className={`${isDone ? "done" : ""} ${here ? "here" : ""} ${stop === next ? "next" : ""}`}>
              <span className="guide-stop-mark">{isDone ? <Check size={13} /> : i + 1}</span>
              <div>
                <strong>{stop.title}</strong>
                <span>{here ? "You are here" : stop.detail}</span>
              </div>
              {here ? null : (
                <button type="button" className="guide-chip-btn" onClick={() => go(stop)}>
                  Go <ArrowRight size={14} />
                </button>
              )}
            </li>
          );
        })}
      </ol>
      <button type="button" className="guide-text-btn" onClick={resetProgress}>
        <RotateCcw size={13} /> Reset progress
      </button>
    </div>
  );
}

function AskTab({ pointAt, nav, setTab, messages, setMessages }) {
  const { pageId } = useGuide();
  const [input, setInput] = useState("");
  const [missing, setMissing] = useState({});
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const suggestions = SUGGESTED_BY_PAGE[pageId] || FALLBACK_SUGGESTIONS;

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);
  useEffect(() => inputRef.current?.focus(), []);

  function ask(text) {
    const q = text.trim();
    if (!q) return;
    setInput("");
    const result = answerQuestion(q, pageId);
    setMessages((m) => [
      ...m,
      { from: "user", text: q },
      result
        ? { from: "bot", entry: result.best, related: result.related }
        : { from: "bot", miss: true },
    ]);
  }

  return (
    <div className="guide-chat">
      <div className="guide-messages" ref={listRef} aria-live="polite">
        <div className="guide-msg bot">
          <p>
            Hi! I can explain any part of Nyaya Vault. Ask a question, or pick one below.
          </p>
          <Chips items={suggestions} onPick={ask} />
        </div>
        {messages.map((m, i) =>
          m.from === "user" ? (
            <div key={i} className="guide-msg user"><p>{m.text}</p></div>
          ) : m.miss ? (
            <div key={i} className="guide-msg bot">
              <p>I don't have an answer for that one yet. The team can take it live, or try one of these:</p>
              <Chips items={FALLBACK_SUGGESTIONS} onPick={ask} />
            </div>
          ) : (
            <div key={i} className="guide-msg bot">
              <p className="guide-msg-q">{m.entry.q}</p>
              <p>{m.entry.a}</p>
              <div className="guide-msg-actions">
                {m.entry.show ? (
                  <button
                    type="button"
                    className="guide-chip-btn"
                    onClick={() => setMissing((s) => ({ ...s, [i]: !pointAt(m.entry.show) }))}
                  >
                    <Crosshair size={14} /> Show me
                  </button>
                ) : null}
                {m.entry.to ? (
                  <button type="button" className="guide-chip-btn" onClick={() => nav(m.entry.to)}>
                    {m.entry.toLabel} <ArrowRight size={14} />
                  </button>
                ) : null}
                {m.entry.tab ? (
                  <button type="button" className="guide-chip-btn" onClick={() => setTab(m.entry.tab)}>
                    Open demo path <ArrowRight size={14} />
                  </button>
                ) : null}
              </div>
              {missing[i] ? (
                <p className="guide-msg-missing">
                  "{TIPS[m.entry.show].title}" isn't on this screen right now. The answer above says where to find it.
                </p>
              ) : null}
              {m.related.length ? (
                <>
                  <p className="guide-label">Related</p>
                  <Chips items={m.related.map((r) => r.q)} onPick={ask} />
                </>
              ) : null}
            </div>
          ),
        )}
      </div>
      <form
        className="guide-input"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask how something works…"
          aria-label="Ask the guide"
        />
        <button type="submit" className="guide-icon-btn send" aria-label="Send" disabled={!input.trim()}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

function Chips({ items, onPick }) {
  return (
    <div className="guide-chips">
      {items.map((q) => (
        <button key={q} type="button" onClick={() => onPick(q)}>
          {q}
        </button>
      ))}
    </div>
  );
}
