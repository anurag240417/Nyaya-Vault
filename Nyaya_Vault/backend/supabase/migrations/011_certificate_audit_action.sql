-- Renumbered from 006 to 011 when reviewing: main had already claimed
-- 006-010 for the timeline feature, suggestion status, the audit_action
-- enum fix, the video-mime-type RPC fix, and department access - none of
-- which existed yet when this branch was written independently.

alter type public.audit_action add value if not exists 'CERTIFICATE_GENERATED';