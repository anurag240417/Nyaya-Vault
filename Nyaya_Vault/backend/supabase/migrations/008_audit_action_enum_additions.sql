alter type public.audit_action add value if not exists 'TIMELINE_STATEMENT_ADDED';
alter type public.audit_action add value if not exists 'TIMELINE_CONFLICT_DETECTED';
alter type public.audit_action add value if not exists 'TIMELINE_SUGGESTIONS_GENERATED';
alter type public.audit_action add value if not exists 'TIMELINE_SUGGESTION_CONFIRMED';
alter type public.audit_action add value if not exists 'TIMELINE_SUGGESTION_REJECTED';
alter type public.audit_action add value if not exists 'AI_ASSISTANT_QUESTION_ASKED';
alter type public.audit_action add value if not exists 'AI_ASSISTANT_SUMMARY_GENERATED';
alter type public.audit_action add value if not exists 'AI_ASSISTANT_LEGAL_SECTIONS_SUGGESTED';