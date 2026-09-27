import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS, TIPS, pageIdFor } from "./guideContent";

const GuideContext = createContext(null);
export const useGuide = () => useContext(GuideContext);

function readStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}
function writeStored(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be unavailable (private mode); the guide still works.
  }
}

function isVisible(el) {
  return el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
}

function findGuideTarget(key) {
  return [...document.querySelectorAll(`[data-guide="${key}"]`)].find(isVisible) || null;
}

export default function GuideProvider({ children }) {
  const { pathname } = useLocation();
  const { user, profile } = useAuth();
  const signedIn = Boolean(user);
  const pageId = pageIdFor(pathname);
  const [tipsOn, setTipsOn] = useState(() => readStored("nv_guide_tips", true));
  const [panelOpen, setPanelOpen] = useState(false);
  const [visited, setVisited] = useState(() => readStored("nv_guide_visited", []));
  const [lastCaseId, setLastCaseId] = useState(() => readStored("nv_guide_case", null));
  const [active, setActive] = useState(null);

  useEffect(() => writeStored("nv_guide_tips", tipsOn), [tipsOn]);

  // Signed-out visits don't count: "/" briefly renders before the redirect
  // to /login and would otherwise tick off the dashboard.
  useEffect(() => {
    if (!signedIn) return;
    setVisited((prev) => {
      if (prev.includes(pageId)) return prev;
      const next = [...prev, pageId];
      writeStored("nv_guide_visited", next);
      return next;
    });
    const caseMatch = pathname.match(/^\/cases\/([^/]+)/);
    if (caseMatch) {
      setLastCaseId(caseMatch[1]);
      writeStored("nv_guide_case", caseMatch[1]);
    }
  }, [signedIn, pageId, pathname]);

  const resetProgress = useCallback(() => {
    setVisited([pageId]);
    writeStored("nv_guide_visited", [pageId]);
  }, [pageId]);

  // Hover / focus engine: one delegated listener finds the nearest
  // [data-guide] ancestor. Once a tip is showing, moving to the next
  // element swaps instantly instead of waiting out the delay again.
  const warmUntil = useRef(0);
  useEffect(() => {
    if (!tipsOn) {
      setActive(null);
      return undefined;
    }
    let timer;
    let current = null;
    // After a click, keep that element's tip hidden until the pointer leaves it.
    let suppressed = null;
    function show(el) {
      const tip = TIPS[el.dataset.guide];
      if (!tip || !el.isConnected) return;
      setActive({ el, tip });
      warmUntil.current = Infinity;
    }
    function target(el) {
      if (el !== suppressed) suppressed = null;
      else if (el) return;
      if (!el) {
        clearTimeout(timer);
        current = null;
        warmUntil.current = Date.now() + 400;
        setActive(null);
        return;
      }
      if (el === current) return;
      clearTimeout(timer);
      current = el;
      const delay = Date.now() < warmUntil.current ? 40 : 450;
      if (delay > 40) setActive(null);
      timer = setTimeout(() => show(el), delay);
    }
    const onOver = (e) => target(e.target.closest?.("[data-guide]") || null);
    const onFocus = (e) => {
      if (e.target.matches?.(":focus-visible")) target(e.target.closest?.("[data-guide]") || null);
    };
    const hide = () => target(null);
    const onDown = () => {
      const clicked = current;
      hide();
      suppressed = clicked;
    };
    const onKey = (e) => e.key === "Escape" && hide();
    // Pinned tips (from "Show me") follow their element while it scrolls.
    const onScroll = () => {
      clearTimeout(timer);
      current = null;
      setActive((a) => (a?.pinned ? { ...a, tick: Date.now() } : null));
    };
    document.addEventListener("mouseover", onOver);
    document.addEventListener("focusin", onFocus);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", hide);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mouseover", onOver);
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", hide);
    };
  }, [tipsOn]);

  // Route changes remove the hovered element; drop its tip with it.
  useEffect(() => setActive(null), [pathname]);

  const showMe = useCallback((key) => {
    const el = findGuideTarget(key);
    if (!el) return false;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.setAttribute("data-guide-flash", "");
    setTimeout(() => el.removeAttribute("data-guide-flash"), 2600);
    setTimeout(() => {
      if (TIPS[key] && el.isConnected) setActive({ el, tip: TIPS[key], pinned: true });
    }, 450);
    return true;
  }, []);

  const value = useMemo(
    () => ({
      pageId,
      role: profile?.role,
      tipsOn,
      setTipsOn,
      panelOpen,
      setPanelOpen,
      visited,
      resetProgress,
      lastCaseId,
      showMe,
    }),
    [pageId, profile?.role, tipsOn, panelOpen, visited, resetProgress, lastCaseId, showMe],
  );

  return (
    <GuideContext.Provider value={value}>
      {children}
      {active ? <HoverTip {...active} role={profile?.role} onDone={() => setActive(null)} /> : null}
    </GuideContext.Provider>
  );
}

function HoverTip({ el, tip, role, pinned, tick, onDone }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);

  useLayoutEffect(() => {
    const r = el.getBoundingClientRect();
    const box = ref.current.getBoundingClientRect();
    const gap = 10, margin = 8;
    const below = r.bottom + gap + box.height <= window.innerHeight - margin;
    const top = below ? r.bottom + gap : Math.max(margin, r.top - gap - box.height);
    const left = Math.min(
      Math.max(margin, r.left + r.width / 2 - box.width / 2),
      window.innerWidth - box.width - margin,
    );
    const arrow = Math.min(Math.max(14, r.left + r.width / 2 - left), box.width - 14);
    setPos({ top, left, arrow, below });
  }, [el, tip, tick]);

  useEffect(() => {
    el.setAttribute("data-guide-hover", "");
    return () => el.removeAttribute("data-guide-hover");
  }, [el]);

  useEffect(() => {
    if (!pinned) return undefined;
    const t = setTimeout(onDone, 4200);
    return () => clearTimeout(t);
  }, [pinned, onDone]);

  const restricted = tip.roles && !tip.roles.includes(role);
  return (
    <div
      ref={ref}
      role="tooltip"
      className={`guide-tip ${pos ? (pos.below ? "below" : "above") : ""}`}
      style={pos ? { top: pos.top, left: pos.left, "--arrow-x": `${pos.arrow}px` } : { visibility: "hidden" }}
    >
      <strong>{tip.title}</strong>
      <p>{tip.body}</p>
      {tip.roles ? (
        <span className={`guide-tip-roles ${restricted ? "restricted" : ""}`}>
          {restricted ? "Not available to your role · " : "For "}
          {tip.roles.map((r) => ROLE_LABELS[r]).join(", ")}
        </span>
      ) : null}
    </div>
  );
}
