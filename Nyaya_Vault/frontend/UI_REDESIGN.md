# Nyaya Vault frontend redesign

The frontend now uses an institutional record system: ink navy, warm ivory,
paper surfaces, judicial maroon accents, compact classification labels, ruled
registers, and restrained serif dossier headings. No external fonts or UI
frameworks were added. No mock records or API responses were introduced.

## Changed files

- `src/styles/app.css`: replaced the previous stylesheet with design tokens,
  shared record styles, responsive registers, and reduced-motion support.
- `src/components/AppShell.jsx`, `Topbar.jsx`, `Sidebar.jsx`: masthead,
  navigation rail, authorization context, and keyboard skip link.
- `src/components/SecurityCredential.jsx`: new reusable credential presentation,
  used in the navigation rail and Case Desk.
- `src/components/DossierTabs.jsx`: replaces `RepoTabs.jsx`; section labels and
  presentation changed, route destinations retained.
- `src/components/Modal.jsx`: dialog semantics, Escape dismissal, focus cycling,
  focus restoration, and background scroll locking.
- `src/components/LoadingState.jsx`, `Toast.jsx`: restrained loading feedback,
  accessible notification roles, and named dismissal controls.
- `src/components/NoticeModal.jsx`, `CertificateModal.jsx`: shared form/error
  styles; request handlers unchanged.
- `src/pages/DashboardPage.jsx`: Case Desk, duty credential, operational search,
  assigned case register, and activity ledger.
- `src/pages/CasesPage.jsx`: contiguous Case Registry with prominent case numbers.
- `src/pages/CasePage.jsx`: dossier cover, summary sheet, evidence register,
  registration form, personnel access, contradiction comparison sheets,
  provisional statements, research records, and audit ledger.
- `src/pages/DocumentPage.jsx`: source preview beside record metadata and
  provenance; human review states, formal certificate action, and version history.
- `src/pages/LoginPage.jsx`, `SearchPage.jsx`, `IntegrityPage.jsx`,
  `AdminPage.jsx`, `ProfilePage.jsx`, `NotFoundPage.jsx`: institutional page
  presentation, terminology, and accessibility improvements.

## Preservation checks

A one-time AST comparison against the original Git HEAD passed for 13
pages/components: 123 event handlers, 51 API/processing calls, route attributes,
form constraints, state initializers, and authorization guard declarations.
The renamed dossier navigation retains its existing route destinations.

The following files were confirmed unchanged: `src/App.jsx`, `src/lib/api.js`,
`src/lib/processor.js`, `src/lib/supabase.js`, `src/lib/hash.js`,
`src/context/AuthContext.jsx`, `src/components/ProtectedRoute.jsx`, and
`src/hooks/useRefreshOnFocus.js`. No backend, database, migration, endpoint,
authentication architecture, or request contract changes were made.

| Workflow | Preserved implementation |
| --- | --- |
| Authentication | Sign-in, registration, username, initial access behavior, sign-out, protected routes |
| Cases | Loading, filtering, creation, status update, permission guards |
| Evidence registration | FIR/chargesheet singleton checks, version confirmation, clearance, department, 200 MB validation, accepted file types |
| Personnel | Candidate loading, assignment/removal, clearance warning, existing management permissions |
| Timeline | Manual statements, document scan, confirmation/dismissal, travel-time conflict results, source excerpts |
| Research | Case questions, grounded answers, computed gap checks, briefing, non-authoritative legal suggestions |
| Evidence records | PDF/image/video preview, object URL cleanup, processing, entity/redaction decisions, review submission, redacted export, immutable versions, download |
| Official actions | Legal notice and Section 63 certificate generation |
| Traceability | Audit sequence, actor, departments, result, hash, timestamp, filters, global integrity verification |
| Administration | User role/clearance/department/account state, case creation, primary investigator, additional collaborators, replacement/removal |
| Search and profile | Existing search requests/ranking and authorization credential data |

## Validation and limits

- Production build: passed (`npm run build`).
- Lint: zero errors, six pre-existing warnings in Badge, AuthContext, and SearchPage.
  The pre-existing Sidebar callback-argument lint error was removed without
  changing its navigation or role condition.
- Browser: inspected login, registration, the shell, and the empty case registry;
  verified sign-in/sign-up switching and unauthenticated protected-route redirect.
  Inspected mobile (390px), tablet (768px), and desktop layouts. Dense record
  containers preserve all fields with horizontal scrolling instead of hiding them.
- Data-dependent end-to-end checks remain unverified: the configured backend
  requests fail with `TypeError: Failed to fetch`. Successful authentication
  submission, populated dossiers, uploads, processing, and administrative writes
  therefore could not be exercised live. Source preservation is not a substitute
  for those live integration checks.

The frontend preview is available locally on port 5173. Once backend connectivity
is restored, exercise the workflows above using authorized existing records.
