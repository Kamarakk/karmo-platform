-- Which tailnet device asked (from `tailscale whois`), so every turn in
-- karmo_turn_trace says who it came from: the first step toward per-person
-- memory and family access (Fable review, 2026-10-11).
BEGIN;
ALTER TABLE public.karmo_turn_trace ADD COLUMN IF NOT EXISTS actor TEXT CHECK (length(actor) <= 200);
COMMIT;
