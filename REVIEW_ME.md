# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] **id:1a30 — eml password-scan heuristic.** The self-draining decryption
  queue recovers a PDF password from the originating `.eml` by matching a
  labelled token: `(pdf )?(password|passwort|kennwort|pin|code|passcode)
  (is|ist|lautet|:|=|->|→) <token>`, where `<token>` is the first run of
  non-space/non-quote/bracket chars, trimmed of trailing sentence punctuation.
  Judgment calls to confirm: (a) **labelled-only, no unlabelled guessing** —
  intentional (a false positive can't mis-import, only waste a decrypt try; a
  miss just leaves the item pending) — is that the right safety bias? (b) the
  label vocabulary (EN+DE: password/Passwort/Kennwort/PIN/code/passcode) —
  enough, or add more languages/labels? (c) token boundary stops at quotes and
  brackets and strips trailing `.,;:!?` — correct for passwords that legitimately
  contain punctuation? No key store / no config was added per the owner
  directive; flag here if a user-supplied-password path is now wanted.
