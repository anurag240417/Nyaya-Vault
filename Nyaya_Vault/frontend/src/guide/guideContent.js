// Nyaya Guide knowledge base: hover tips, page walkthroughs, the judge demo
// path, and the Q&A answers. Elements opt in to a hover tip with
// data-guide="<key>", where <key> is an entry in TIPS below.

export const ROLE_LABELS = {
  ADMIN: "Administrator",
  INVESTIGATING_OFFICER: "Investigating Officer",
  PROSECUTOR: "Prosecutor",
  JUDGE: "Judge",
  CLERK: "Clerk",
};

const MANAGERS = ["ADMIN", "INVESTIGATING_OFFICER"];

export const TIPS = {
  // Masthead
  brand: { title: "Nyaya Vault home", body: "Returns you to your Dashboard from anywhere in the app." },
  language: { title: "Interface language", body: "Switch between English, Hindi, Marathi, Bengali, Tamil and Telugu. Labels change instantly and your choice is remembered on this device. Evidence files themselves are not translated." },
  "profile-chip": { title: "Your account", body: "Who is signed in and their role. Opens your Profile: clearance level, department and your digital signing key." },
  logout: { title: "Sign out", body: "Ends your session and returns to the sign-in screen." },

  // Sidebar
  "nav-dashboard": { title: "Dashboard", body: "Your duty desk: the cases you can open and the latest entries from the audit ledger." },
  "nav-cases": { title: "Cases", body: "The register of every case you are assigned to. Open one to see its evidence, people, timeline, AI assistant and audit trail." },
  "nav-search": { title: "Search", body: "Search case numbers, titles and text extracted from evidence, by keyword and by meaning. Results respect your clearance." },
  "nav-integrity": { title: "Integrity", body: "Re-computes the audit ledger's hash chain to prove no record has been altered, and checks blockchain anchors." },
  "nav-admin": { title: "Administration", body: "Manage users' roles, clearance and departments, and assign cases to investigating officers.", roles: ["ADMIN"] },
  credential: { title: "Security credential", body: "Your role, clearance level and department. Together they decide what you can see: evidence above your clearance, or tagged for another department, stays hidden from you." },

  // Dashboard
  "dash-open-cases": { title: "Open cases", body: "Jumps to the full case register." },
  "dash-case-count": { title: "Accessible case records", body: "How many cases your account is allowed to open. Cases are private: you only see the ones you are assigned to." },
  "dash-search": { title: "Search shortcut", body: "Opens Search, which looks through case records and the text extracted from uploaded evidence." },
  "dash-case-register": { title: "Case register", body: "Your most recent cases with their status. Click a row to open that case's dossier." },
  "dash-activity": { title: "Recent activity", body: "The latest entries in the tamper-evident audit ledger: who did what, on which case, and whether it succeeded or was denied. The number on the left is the ledger sequence." },
  "case-status": { title: "Case status", body: "Under Investigation, Solved, Unsolved or Closed. Admins and assigned investigating officers can change it from the case's Summary tab." },

  // Cases register
  "cases-new": { title: "New case", body: "Creates a case from a case number, title and description. It appears in your register straight away.", roles: MANAGERS },
  "cases-filter": { title: "Filter cases", body: "Filters this list by case number, title or description as you type. To search inside evidence, use Search in the sidebar." },
  "cases-refresh": { title: "Refresh", body: "Reloads the register to pick up cases assigned to you since this page opened." },
  "case-card": { title: "Case entry", body: "Click the case number or title to open the case dossier." },
  "visibility-pill": { title: "Private case", body: "Cases are never public. Only assigned collaborators and administrators can open them." },

  // Case dossier tabs
  "tab-summary": { title: "Summary", body: "The case record, status control, assigned personnel and the legal notice generator." },
  "tab-documents": { title: "Documents", body: "The evidence register: every file uploaded to this case, with its classification, department and version." },
  "tab-collaborators": { title: "Collaborators", body: "Who has access to this case and who granted it." },
  "tab-timeline": { title: "Timeline", body: "Places people at locations and times from statements, then flags contradictions: someone who could not physically have been in both places, given travel time." },
  "tab-assistant": { title: "Assistant", body: "AI research assistant that answers only from this case's confirmed evidence, plus a gap check, a case briefing and suggested legal sections." },
  "tab-audit": { title: "Audit", body: "Every action taken on this case, hash-chained so that any edit to history can be detected." },

  // Case summary
  "case-control": { title: "Case control", body: "At-a-glance counts of this case's documents, collaborators and audit events." },
  "case-status-select": { title: "Change case status", body: "Updates the status for everyone on the case. The change is recorded in the audit trail.", roles: MANAGERS },
  "legal-notice": { title: "Generate legal notice", body: "Choose a notice type, add the recipient and your own wording, and download a formatted notice that cites the provision it is issued under." },
  "assigned-personnel": { title: "Assigned personnel", body: "People who can access this case. Manage them on the Collaborators tab." },
  "notice-type": { title: "Notice type", body: "Each type is tied to a specific legal provision, shown underneath once selected. Extra fields appear depending on the type." },

  // Evidence register
  "register-evidence": { title: "Register evidence", body: "Upload a PDF, image (JPG, PNG, TIFF) or video (MP4, MOV, WebM) up to 200 MB. The file is SHA-256 fingerprinted and stored as immutable version 1. It can never be silently overwritten." },
  "evidence-row": { title: "Evidence record", body: "Opens the evidence: preview, hash fingerprint, extracted entities, redactions, version history and the Section 63 certificate." },
  "clearance-badge": { title: "Security classification", body: "PUBLIC < RESTRICTED < CONFIDENTIAL < SECRET. Users whose clearance is below this level cannot see the document at all." },
  "department-badge": { title: "Responsible department", body: "Evidence tagged to a department (Police, Forensics, Prosecution, Judiciary) is visible only to users in that department. GENERAL is visible to everyone on the case." },
  "doc-version": { title: "Current version", body: "Updates never replace a file; they add v2, v3 and so on. Every earlier version stays downloadable with its original hash." },
  "upload-doc-type": { title: "Document type", body: "Free text, e.g. FIR, Chargesheet, Statement. A case can have only one primary FIR and one chargesheet; uploading another one becomes a new version of it." },
  "upload-classification": { title: "Security classification", body: "Who may see this file. Pick the lowest level that still protects it; people below this clearance won't see it." },
  "upload-department": { title: "Responsible department", body: "Restricts the file to users of one department. Choose GENERAL to share it with everyone on the case." },
  "upload-file": { title: "Choose file", body: "Its SHA-256 fingerprint is calculated from the exact bytes you upload. That fingerprint is what later proves the file is unchanged." },

  // Collaborators
  "add-collaborator": { title: "Add collaborator", body: "Gives an active user access to this case. You are warned if their clearance is below the case's most sensitive evidence.", roles: MANAGERS },
  "collaborator-row": { title: "Collaborator", body: "Name, role and clearance, plus who granted access and when." },
  "remove-collaborator": { title: "Remove access", body: "Revokes this person's access. Only an admin or the lead investigator can remove people, and only an admin can remove a judge.", roles: MANAGERS },

  // Timeline & contradictions
  "timeline-scan": { title: "Scan documents for candidates", body: "Reads people, places and times from the entities confirmed on this case's documents and proposes timeline statements for you to review." },
  "timeline-add": { title: "Add manually", body: "Enter a person, location and time window yourself, e.g. from a witness statement. It is checked against existing statements immediately." },
  "contradiction-card": { title: "Contradiction", body: "These statements about the same person cannot all be true: no schedule fits them, even letting each window shift, given travel time between the places." },
  "suggestion-confirm": { title: "Confirm", body: "Accepts this system-extracted statement into the timeline. It is checked for contradictions straight away." },
  "suggestion-dismiss": { title: "Dismiss", body: "Rejects this suggestion so it is never used." },
  "confirmed-statements": { title: "Confirmed statements", body: "Human-confirmed placements. Only these are used for contradiction checking." },

  // AI assistant
  "assistant-ask": { title: "Ask the case", body: "Ask in plain language. Answers use only this case's confirmed evidence and cite their source. Verify anything important yourself." },
  "gap-check": { title: "Gap check", body: "Automatically lists what is missing or weak in this case file, ranked High, Medium or Low." },
  "case-summary-btn": { title: "Generate summary", body: "Writes a short briefing of the case from its evidence." },
  "legal-sections-btn": { title: "Suggest sections", body: "Suggests legal sections that may apply, based on the evidence. A starting point for research, not legal advice." },

  // Audit
  "audit-filters": { title: "Department filters", body: "Narrow the trail by the department of the person who acted, or of the evidence they acted on." },
  "audit-result": { title: "Result", body: "SUCCESS, or DENIED when permissions blocked the attempt. Denied attempts are recorded too." },
  "audit-hash": { title: "Entry hash", body: "Click to expand the full SHA-256 of this ledger entry. Each hash includes the previous entry's hash, so altering any past row breaks every row after it." },

  // Evidence record
  "doc-back": { title: "Back to evidence register", body: "Returns to this case's list of documents." },
  "doc-new-version": { title: "New version", body: "Uploads a corrected or updated file as the next version. The current version is kept, unchanged, in Version History." },
  "doc-download": { title: "Download", body: "Downloads the original bytes of the current version, exactly as uploaded." },
  "doc-certificate": { title: "Section 63 certificate", body: "Generates the certificate required for electronic evidence under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023. Part A is filled automatically from stored records; you name the expert for Part B, then download." },
  "doc-tab-overview": { title: "Record", body: "Preview, record details, SHA-256 fingerprint and processing status." },
  "doc-tab-entities": { title: "Extracted entities", body: "Names, places, dates and other details the system found in the text. Each one needs a human to confirm or reject it." },
  "doc-tab-redactions": { title: "Redaction review", body: "Proposed regions to black out (e.g. personal details) before disclosure. Only human-approved regions are used." },
  "doc-tab-versions": { title: "Version history", body: "Every version ever uploaded, each with its own hash and download." },
  "doc-preview": { title: "Source evidence", body: "Inline preview of the original file. The SHA-256 fingerprint is computed from these exact bytes." },
  "doc-hash": { title: "SHA-256 fingerprint", body: "A unique fingerprint of this file. Changing even one byte produces a completely different value, which is how tampering is detected." },
  "doc-provenance": { title: "Processing & provenance", body: "When this version was registered, whether its fingerprint is recorded, and whether text extraction has finished." },
  "doc-run-processing": { title: "Run OCR / NER processing", body: "Extracts text (using OCR for scans) and detects names, places and dates. Results appear under Extracted Entities and Redaction Review for human review." },
  "entity-save": { title: "Save review", body: "Saves your Confirm / Reject decisions. Enabled once you have changed at least one." },
  "entity-decision": { title: "Confirm or reject", body: "Confirm if the extracted value is correct; reject if not. Only confirmed entities feed the timeline and the AI assistant." },
  "redaction-generate": { title: "Generate", body: "Runs processing again to propose redaction regions." },
  "redaction-export": { title: "Export redacted", body: "Downloads a disclosure copy with only the approved regions blacked out. Enabled once at least one region is approved." },
  "redaction-save": { title: "Save review", body: "Saves your Approve / Reject decisions on the proposed regions." },
  "redaction-decision": { title: "Approve or reject", body: "Approve to include this region in the disclosure copy's redactions; reject to leave it visible." },
  "version-download": { title: "Download this version", body: "Downloads this exact historical version. Its hash is shown next to it." },
  "cert-expert": { title: "Expert details (Part B)", body: "The named expert who will sign the certificate before it is filed in court." },

  // Search
  "search-input": { title: "Search box", body: "Type a case number, a name, or a phrase from a document. Search matches exact words and also meaning (semantic search)." },
  "search-submit": { title: "Search", body: "Runs the search. The query is kept in the address bar, so you can share or revisit it." },
  "search-result": { title: "Search result", body: "The matching document, its case and the page the match was found on. Click to open the evidence." },
  "search-score": { title: "Relevance", body: "How strongly this result matched: a text relevance score, or percentage similarity for meaning-based matches." },

  // Integrity
  "integrity-verify": { title: "Verify integrity now", body: "Re-computes every audit-ledger hash from scratch and follows the chain. If any entry was edited or deleted, it reports the first broken sequence number." },
  "integrity-result": { title: "Verification result", body: "How many ledger entries were checked, and the first invalid one if the chain is broken." },
  "anchor-now": { title: "Anchor now", body: "Publishes the ledger's current hash to a public blockchain, so even someone with full database access could not rewrite history unnoticed.", roles: ["ADMIN"] },
  "anchor-verify": { title: "Verify anchor", body: "Checks the ledger against the hash stored on the blockchain for this anchor. Shows Verified on-chain or Tamper detected." },
  "anchor-tx": { title: "Blockchain transaction", body: "The public transaction holding this anchor. Click to inspect it on the network's block explorer." },

  // Administration
  "admin-tab-users": { title: "Personnel register", body: "Every user account, with role, clearance, department and active state.", roles: ["ADMIN"] },
  "admin-tab-cases": { title: "Case assignment register", body: "Every case, its primary investigator and its collaborators.", roles: ["ADMIN"] },
  "admin-role": { title: "Role", body: "Administrator, Investigating Officer, Prosecutor, Judge or Clerk. Decides which actions the user can take.", roles: ["ADMIN"] },
  "admin-clearance": { title: "Clearance", body: "Highest classification this user can read: Public, Restricted, Confidential or Secret.", roles: ["ADMIN"] },
  "admin-department": { title: "Department", body: "Evidence tagged to a department is only visible to users in that department.", roles: ["ADMIN"] },
  "admin-active": { title: "Active / disabled", body: "Disabled users cannot sign in or be assigned to cases.", roles: ["ADMIN"] },
  "admin-save-user": { title: "Save", body: "Applies this row's changes. Changes take effect on the user's next request.", roles: ["ADMIN"] },
  "admin-create-case": { title: "Create & assign case", body: "Creates a case and chooses its primary investigator and collaborators in one step. Needs at least one active investigating officer.", roles: ["ADMIN"] },
  "admin-manage": { title: "Manage assignments", body: "Change the primary investigator and the full collaborator list for this case.", roles: ["ADMIN"] },
  "admin-remove-chip": { title: "Remove collaborator", body: "Removes this person's access to the case.", roles: ["ADMIN"] },

  // Profile
  "profile-signing-key": { title: "Signing key", body: "Your personal digital signing key. Documents you generate are signed with it, and the fingerprint lets anyone verify a signature came from you." },
  "profile-show-key": { title: "Show public key", body: "Displays the full public key (PEM). It is safe to share; the private half never leaves the server." },

  // Sign-in
  "login-submit": { title: "Sign in", body: "Use the demo account details the Nyaya Vault team gave you." },
  "login-toggle": { title: "Create an account", body: "Switches to sign-up. New accounts start with minimal access until an administrator assigns a role and cases." },

  // The guide itself
  "guide-launcher": { title: "Nyaya Guide", body: "Page walkthroughs, a suggested demo path and answers to your questions. Press ? to open or close." },
};

export const PAGES = {
  login: {
    title: "Sign in",
    summary: "Nyaya Vault is a secure, tamper-evident evidence locker for Indian criminal cases.",
    steps: [
      "Sign in with the demo account details the team gave you.",
      "Once in, open the Guide again: it follows you page by page.",
    ],
    highlights: ["login-submit", "login-toggle"],
  },
  dashboard: {
    title: "Dashboard",
    summary: "Your duty desk: cases you can open, and the latest actions recorded in the audit ledger.",
    steps: [
      "Look at your security credential: role, clearance and department decide what you can see.",
      "Scan Recent activity: every action, including denied ones, is permanently logged.",
      "Click any case in the register to open its dossier.",
    ],
    highlights: ["credential", "dash-case-register", "dash-activity", "dash-search"],
  },
  cases: {
    title: "Case register",
    summary: "Every case you are assigned to. Cases are private to their collaborators.",
    steps: [
      "Type in the filter box to narrow the list.",
      "Click a case number or title to open its dossier.",
      "Admins and investigating officers can create a new case.",
    ],
    highlights: ["cases-new", "cases-filter", "case-card", "visibility-pill"],
  },
  "case-summary": {
    title: "Case dossier: Summary",
    summary: "The official case record. The tabs across the top lead to everything about this case.",
    steps: [
      "Use the tabs to move between Documents, Collaborators, Timeline, Assistant and Audit.",
      "Try Generate legal notice to produce a formatted notice citing its legal provision.",
      "Admins and assigned officers can change the case status here.",
    ],
    highlights: ["tab-documents", "tab-timeline", "tab-assistant", "legal-notice", "case-status-select"],
  },
  "case-documents": {
    title: "Evidence register",
    summary: "All evidence for this case. Every file is fingerprinted and versioned; nothing is ever overwritten.",
    steps: [
      "Note the classification and department badges: they control who can see each file.",
      "Click any row to open the evidence record.",
      "Register evidence uploads a new file as version 1.",
    ],
    highlights: ["register-evidence", "evidence-row", "clearance-badge", "department-badge", "doc-version"],
  },
  "case-collaborators": {
    title: "Collaborators",
    summary: "Who can access this case, their role and clearance, and who granted access.",
    steps: [
      "Each row shows who added the person and when.",
      "Only admins and assigned officers can add people; only admins can remove a judge.",
    ],
    highlights: ["add-collaborator", "collaborator-row", "remove-collaborator"],
  },
  "case-timeline": {
    title: "Timeline & contradictions",
    summary: "Detects statements that place the same person in two places they could not travel between in time.",
    steps: [
      "Click Scan documents for candidates to pull statements out of confirmed evidence.",
      "Confirm or dismiss each suggestion; confirmed ones are checked automatically.",
      "Or use Add manually to test it: put one person in two distant cities an hour apart.",
    ],
    highlights: ["timeline-scan", "timeline-add", "contradiction-card", "confirmed-statements"],
  },
  "case-assistant": {
    title: "AI research assistant",
    summary: "Answers grounded only in this case's confirmed evidence, with sources cited.",
    steps: [
      "Ask something like \"What evidence do we have so far?\"",
      "Read the Gap check: what the case file is missing, by severity.",
      "Try Generate summary and Suggest sections.",
    ],
    highlights: ["assistant-ask", "gap-check", "case-summary-btn", "legal-sections-btn"],
  },
  "case-audit": {
    title: "Case audit trail",
    summary: "Every action on this case, in order, each entry hash-linked to the one before.",
    steps: [
      "Expand an entry hash to see its full SHA-256.",
      "Filter by the department of the actor or of the evidence.",
      "To prove the whole chain is intact, go to Integrity in the sidebar.",
    ],
    highlights: ["audit-filters", "audit-hash", "audit-result"],
  },
  document: {
    title: "Evidence record",
    summary: "One piece of evidence: its preview, fingerprint, AI extraction, redactions, versions and court certificate.",
    steps: [
      "Check the SHA-256 fingerprint under Record Information.",
      "Open Extracted Entities: AI output is never trusted until a human confirms it.",
      "Click Section 63 certificate to generate the court certificate for this electronic record.",
      "Open Version History to see that earlier files are never overwritten.",
    ],
    highlights: ["doc-certificate", "doc-hash", "doc-tab-entities", "doc-tab-redactions", "doc-tab-versions", "doc-run-processing"],
  },
  search: {
    title: "Search",
    summary: "Search case records and text extracted from evidence, by keyword and by meaning.",
    steps: [
      "Type a name, place or phrase and press Search.",
      "Badges show whether a result matched by keyword, by meaning, or both.",
      "Click a result to open the evidence at its source.",
    ],
    highlights: ["search-input", "search-submit", "search-result", "search-score"],
  },
  integrity: {
    title: "Integrity verification",
    summary: "Proves the audit ledger has not been altered, independently of the database.",
    steps: [
      "Click Verify integrity now to recompute every hash in the chain.",
      "Blockchain anchors publish the chain's hash publicly; Verify checks each one.",
    ],
    highlights: ["integrity-verify", "anchor-now", "anchor-verify", "anchor-tx"],
  },
  admin: {
    title: "Administration",
    summary: "User permissions and case assignment. Visible to administrators only.",
    steps: [
      "Personnel Register: set each user's role, clearance, department and active state, then Save.",
      "Case Assignment Register: create cases and choose who works on them.",
    ],
    highlights: ["admin-tab-users", "admin-tab-cases", "admin-role", "admin-clearance", "admin-create-case"],
  },
  profile: {
    title: "Profile",
    summary: "Your identity, access level and digital signing key.",
    steps: ["Show your public signing key: it verifies documents you generate."],
    highlights: ["profile-signing-key", "profile-show-key"],
  },
  notfound: {
    title: "Page not found",
    summary: "This address doesn't exist.",
    steps: ["Use the Demo path tab or the sidebar to get back on track."],
    highlights: [],
  },
};

export function pageIdFor(pathname) {
  if (pathname.startsWith("/login")) return "login";
  if (pathname.startsWith("/dashboard") || pathname === "/") return "dashboard";
  const caseMatch = pathname.match(/^\/cases\/[^/]+\/?([^/]*)/);
  if (caseMatch) return caseMatch[1] ? `case-${caseMatch[1]}` : "case-summary";
  if (pathname.startsWith("/cases")) return "cases";
  if (pathname.startsWith("/documents/")) return "document";
  if (pathname.startsWith("/search")) return "search";
  if (pathname.startsWith("/integrity")) return "integrity";
  if (pathname.startsWith("/admin")) return "admin";
  if (pathname.startsWith("/profile")) return "profile";
  return "notfound";
}

// `needs: "case"` stops go to the last opened case's tab; `needs: "document"`
// sends the judge to pick evidence from that case.
export const DEMO_PATH = [
  { page: "dashboard", title: "Duty desk", detail: "Your credential and the live audit ledger.", to: "/dashboard" },
  { page: "cases", title: "Case register", detail: "Private cases you are assigned to.", to: "/cases" },
  { page: "case-summary", title: "Open a case", detail: "The dossier and its tabs.", needs: "case", tab: "" },
  { page: "case-documents", title: "Evidence register", detail: "Classification, departments, versions.", needs: "case", tab: "documents" },
  { page: "document", title: "An evidence record", detail: "SHA-256, AI review, Section 63 certificate.", needs: "document" },
  { page: "case-timeline", title: "Contradiction detection", detail: "Who could not have been where.", needs: "case", tab: "timeline" },
  { page: "case-assistant", title: "AI research assistant", detail: "Grounded answers and gap check.", needs: "case", tab: "assistant" },
  { page: "case-audit", title: "Case audit trail", detail: "Hash-linked record of every action.", needs: "case", tab: "audit" },
  { page: "search", title: "Search evidence", detail: "Keyword and semantic search.", to: "/search" },
  { page: "integrity", title: "Verify integrity", detail: "Prove nothing was tampered with.", to: "/integrity" },
];

// Q&A. `keywords` match at the start of a word in the lower-cased question
// ("redact" matches "redaction"); multi-word keywords score higher. `to` adds a navigation button and
// `show` adds a "Show me" button that highlights that data-guide element.
export const FAQ = [
  {
    q: "What is Nyaya Vault?",
    keywords: ["nyaya vault", "purpose", "overview", "what does this", "explain the app", "problem", "this app", "this project"],
    a: "Nyaya Vault is a secure digital evidence locker for criminal cases. Every file is SHA-256 fingerprinted and versioned, access is limited by role, clearance and department, every action goes into a hash-chained audit ledger, and AI helps with extraction, contradictions and research, always with human confirmation.",
  },
  {
    q: "Where should I start?",
    keywords: ["start", "begin", "first", "demo", "tour", "walkthrough", "how to use", "what should i", "guide me", "help"],
    a: "Open the Demo path tab: it lists ten stops in a sensible order and ticks each one off as you visit it. The quickest route: open a case, open one piece of evidence, generate its Section 63 certificate, then check the Timeline and Integrity pages.",
    tab: "path",
  },
  {
    q: "How do I upload evidence?",
    keywords: ["upload", "add evidence", "register evidence", "add document", "new document", "add file", "attach"],
    a: "Open a case, go to the Documents tab and click Register evidence. Give it a title, type, classification and department, then choose a PDF, image or video (up to 200 MB). It is hashed and stored as version 1.",
    show: "register-evidence",
    pages: ["case-documents"],
  },
  {
    q: "How is tampering prevented?",
    keywords: ["tamper", "sha", "hash", "fingerprint", "integrity", "altered", "modify", "proof", "immutable", "chain of custody", "trust"],
    a: "Three layers. 1) Each file gets a SHA-256 fingerprint from its exact bytes, so any change is detectable. 2) Files are never overwritten; updates become new versions. 3) Every action is written to an audit ledger where each entry's hash includes the previous one, and that chain can be anchored to a public blockchain. The Integrity page re-checks all of it.",
    to: "/integrity",
    toLabel: "Open Integrity",
  },
  {
    q: "What is the Section 63 certificate?",
    keywords: ["section 63", "certificate", "65b", "bsa", "sakshya", "admissib", "court", "electronic record"],
    a: "Under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 (which replaced Section 65B of the Evidence Act), electronic evidence must come with a certificate to be admissible. Nyaya Vault fills Part A automatically from the stored hash and records; you name the expert for Part B and download it. Open any evidence record and click Section 63 certificate.",
    show: "doc-certificate",
    pages: ["document"],
  },
  {
    q: "Why can't a file be replaced?",
    keywords: ["version", "overwrite", "replace", "update file", "delete", "edit document", "history"],
    a: "By design. Uploading a changed file creates a new version (v2, v3...) and every earlier version stays downloadable with its original hash, so no one can quietly swap evidence. See the Version History tab on any evidence record.",
    show: "doc-tab-versions",
    pages: ["document"],
  },
  {
    q: "Why only one FIR per case?",
    keywords: ["fir", "chargesheet", "charge sheet", "primary", "singleton", "duplicate"],
    a: "A case has one primary FIR and one primary chargesheet. If you upload another with the same type, Nyaya Vault asks you to add it as a new version of the existing one instead of creating a competing copy.",
  },
  {
    q: "What do clearance levels mean?",
    keywords: ["clearance", "classification", "secret", "confidential", "restricted", "public", "who can see"],
    a: "Evidence is classified PUBLIC < RESTRICTED < CONFIDENTIAL < SECRET, and every user has a clearance level. You only see documents at or below your clearance, even inside a case you're assigned to.",
    show: "credential",
  },
  {
    q: "What do departments do?",
    keywords: ["department", "police", "forensic", "prosecution", "judiciary"],
    a: "Evidence can be tagged to Police, Forensics, Prosecution or Judiciary; only users in that department see it. GENERAL evidence is visible to everyone on the case. Admins set each user's department.",
  },
  {
    q: "What can each role do?",
    keywords: ["role", "judge", "admin", "investigating officer", "prosecutor", "clerk", "permission", "access"],
    a: "Administrators manage users and assign cases. Investigating Officers create cases, upload evidence and manage collaborators on their cases. Judges, Prosecutors and Clerks work within the cases they are assigned to. A judge can only be removed from a case by an administrator.",
  },
  {
    q: "Why can't I see a button?",
    keywords: ["can't see", "can't i see", "cannot see", "missing", "not showing", "where is", "hidden", "don't see", "see a button", "see the button", "no button", "disabled", "greyed out"],
    a: "Some controls only appear for certain roles: New case and Add collaborator for admins and investigating officers, Administration and Anchor now for admins. Some buttons stay disabled until there is something to act on, e.g. Save review until you change a decision. Hover over a disabled button for its tip.",
  },
  {
    q: "How does contradiction detection work?",
    keywords: ["contradiction", "timeline", "alibi", "conflict", "location", "travel", "two places", "inconsistent"],
    a: "Each confirmed statement places a person at a location within a time window. Nyaya Vault checks whether any real schedule, allowing for travel time between those places, fits all of them. If none does, it flags a contradiction and shows the statements involved. Try Add manually on the Timeline tab with one person in two distant cities an hour apart.",
    show: "timeline-add",
    pages: ["case-timeline"],
  },
  {
    q: "What are extracted entities?",
    keywords: ["entit", "ner", "ocr", "extract", "names", "processing", "text extraction"],
    a: "Processing reads the text of a document (using OCR for scans) and picks out names, places, dates and similar details. These are only suggestions: each one must be confirmed or rejected by a person. Confirmed entities feed the Timeline and the AI assistant.",
    show: "doc-tab-entities",
    pages: ["document"],
  },
  {
    q: "How does redaction work?",
    keywords: ["redact", "black out", "disclosure", "privacy", "personal data", "mask"],
    a: "The system proposes regions to hide, such as personal details. A person approves or rejects each one, then Export redacted downloads a disclosure copy with only the approved regions blacked out. The original is untouched.",
    show: "doc-tab-redactions",
    pages: ["document"],
  },
  {
    q: "Is the AI assistant reliable?",
    keywords: ["ai", "assistant", "chatbot", "llm", "hallucinat", "ask question", "research", "summary", "legal section", "gap"],
    a: "The case assistant answers only from that case's confirmed evidence and cites its sources; it is a research aid, not an authority. The same tab has a Gap check (what the file is missing), Generate summary, and Suggest sections for possibly applicable laws. Open any case and choose the Assistant tab.",
    show: "tab-assistant",
    pages: ["case-assistant"],
  },
  {
    q: "What is the audit trail?",
    keywords: ["audit", "log", "ledger", "record of action", "who did", "activity"],
    a: "Every action (views, uploads, reviews, denied attempts) is written to an append-only ledger. Each entry stores a SHA-256 hash that includes the previous entry's hash, so changing any past entry breaks the chain from that point on. Each case has an Audit tab; Integrity checks the whole chain.",
    show: "tab-audit",
  },
  {
    q: "What is blockchain anchoring?",
    keywords: ["blockchain", "anchor", "on-chain", "on chain", "transaction", "public ledger"],
    a: "Periodically, the audit chain's latest hash is published in a public blockchain transaction. Even someone with full database access couldn't then rewrite history without the mismatch showing. On the Integrity page, Verify compares the ledger with each anchor.",
    to: "/integrity",
    toLabel: "Open Integrity",
  },
  {
    q: "How does search work?",
    keywords: ["search", "find", "look for", "semantic", "keyword"],
    a: "Search looks through case numbers, titles and the text extracted from evidence. It matches exact words and also meaning (semantic search), and only returns documents you're cleared to see.",
    to: "/search",
    toLabel: "Open Search",
  },
  {
    q: "How do I generate a legal notice?",
    keywords: ["notice", "legal notice", "summons", "generate notice"],
    a: "Open a case's Summary tab and click Generate legal notice. Pick the notice type (the provision it's issued under is shown), fill in the recipient and your wording, then Generate & download.",
    show: "legal-notice",
    pages: ["case-summary"],
  },
  {
    q: "How do I add or remove people?",
    keywords: ["collaborator", "add people", "add user", "remove", "share case", "give access", "assign"],
    a: "On a case's Collaborators tab, admins and assigned investigating officers can Add collaborator. You're warned if the person's clearance is below the case's most sensitive evidence. Removing access is limited to admins and the lead investigator, and only admins can remove a judge.",
    show: "add-collaborator",
    pages: ["case-collaborators"],
  },
  {
    q: "What is my signing key?",
    keywords: ["signing key", "signature", "public key", "sign", "pem"],
    a: "Each user has a personal digital signing key. Documents you generate are signed with it, and anyone can use your public key's fingerprint to confirm a signature came from you. See it on your Profile.",
    to: "/profile",
    toLabel: "Open Profile",
  },
  {
    q: "Can I use another language?",
    keywords: ["language", "hindi", "tamil", "telugu", "marathi", "bengali", "translate"],
    a: "Yes. Use the language button in the top bar to switch between English, Hindi, Marathi, Bengali, Tamil and Telugu.",
    show: "language",
  },
  {
    q: "Are videos supported?",
    keywords: ["video", "mp4", "cctv", "footage", "audio"],
    a: "Yes: MP4, MOV and WebM are stored and fingerprinted like any other evidence. Their content isn't analysed automatically, so reference what they show via a Timeline statement if it matters for a contradiction check.",
  },
  {
    q: "How do I turn off hover tips?",
    keywords: ["turn off", "disable tip", "hover", "tooltip", "annoying", "hide tip", "stop showing"],
    a: "Use the Hover tips switch at the top of this panel. Press ? anywhere to open or close the Guide.",
  },
];

export const SUGGESTED_BY_PAGE = {
  login: ["What is Nyaya Vault?", "Where should I start?"],
  dashboard: ["Where should I start?", "What do clearance levels mean?", "What is the audit trail?"],
  cases: ["What can each role do?", "Why can't I see a button?"],
  "case-summary": ["How do I generate a legal notice?", "What can each role do?"],
  "case-documents": ["How do I upload evidence?", "Why can't a file be replaced?", "What do departments do?"],
  "case-collaborators": ["How do I add or remove people?", "What do clearance levels mean?"],
  "case-timeline": ["How does contradiction detection work?", "What are extracted entities?"],
  "case-assistant": ["Is the AI assistant reliable?", "What are extracted entities?"],
  "case-audit": ["What is the audit trail?", "How is tampering prevented?"],
  document: ["What is the Section 63 certificate?", "How does redaction work?", "Why can't a file be replaced?"],
  search: ["How does search work?", "What do clearance levels mean?"],
  integrity: ["How is tampering prevented?", "What is blockchain anchoring?"],
  admin: ["What can each role do?", "What do departments do?"],
  profile: ["What is my signing key?"],
  notfound: ["Where should I start?"],
};

const STOP_WORDS = new Set(["the", "a", "an", "is", "are", "do", "does", "i", "me", "my", "to", "of", "in", "on", "it", "this", "that", "how", "what", "why", "can", "and", "or", "for", "with", "be"]);

// Apostrophes are dropped (so "can't", "can’t" and "cant" agree) and other
// punctuation becomes a space.
function normalize(s) {
  return s
    .toLowerCase()
    .replace(/[‘’']/g, "")
    .replace(/[^\p{L}\p{N}\s-]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const KEYWORD_PATTERNS = new Map(
  FAQ.flatMap((entry) => entry.keywords).map((k) => [
    k,
    new RegExp(`(^|\\s)${normalize(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`),
  ]),
);

const GREETING = {
  q: "Namaste!",
  a: "Namaste! I'm the Nyaya Guide. Ask me what any part of Nyaya Vault does, or open the Demo path tab for a suggested route through the prototype.",
  tab: "path",
};

export function answerQuestion(question, pageId) {
  const text = normalize(question);
  if (/^(hi|hello|hey|namaste|namaskar|thanks|thank you)\b/.test(text) && text.split(" ").length <= 3) {
    return { best: GREETING, related: [] };
  }
  const words = new Set(text.split(" ").filter((w) => w.length > 1 && !STOP_WORDS.has(w)));
  const scored = FAQ.map((entry) => {
    let score = 0;
    for (const keyword of entry.keywords) {
      if (KEYWORD_PATTERNS.get(keyword).test(text)) score += 2 + keyword.split(" ").length;
    }
    for (const w of normalize(entry.q).split(" ")) {
      if (words.has(w)) score += 1;
    }
    if (score && entry.pages?.includes(pageId)) score += 1;
    return { entry, score };
  })
    .filter((s) => s.score >= 3)
    .sort((a, b) => b.score - a.score);
  if (!scored.length) return null;
  return { best: scored[0].entry, related: scored.slice(1, 3).map((s) => s.entry) };
}
