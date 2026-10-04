# Writing style for walkthrough pages

## The reader

A teammate reviewing the PR. Assume they know programming basics but not this part of the codebase,
and that some readers are still learning: every technical word gets a lesson link on its first use,
so a beginner can click and a senior reader can skip. They want to know three things fast: what
changed, why it changed, and where it could break.

## Rules

1. Plain words. Say what the code does. "use", not "utilize" or "leverage"; "help", not "facilitate".
2. Link lessons generously with `[[lesson-id|shown text]]` on a term's first use instead of
   defining it inline. The lessons open in a side panel.
3. Short sentences, one idea each, whole sentences with articles and verbs (not "fails -> exit 2").
4. Active voice: name who does what ("the parser rejects the date", not "the date is rejected").
5. No em dashes or en dashes; use periods, commas or parentheses. Colons only before a list or code.
6. No filler vocabulary: additionally, crucial, delve, enhance, robust, seamless, comprehensive,
   leverage, utilize, pivotal, showcase, landscape, underscore. No "not just X but Y". No padding
   lists of three.
7. Facts and numbers over adjectives. Real names from the code (`retry_after`, `cache.py`) and real
   figures (3 retries, 250 ms, 12 of 14 tests). Never invent outputs or numbers.
8. Separate what the author said from what you infer. Inferred reasoning reads as a reading of the
   code ("this looks meant to ..."), and `thinking.source` says which it is.
9. Sentence case for headings. No emojis. Straight quotes.
10. In chunk notes, say what the lines do in this program and why; a "Check:" line says what a
    reviewer should verify there. Do not restate the code in words line by line.

## Markup in HTML strings

`[[lesson-id|text]]` for lesson links, `<code>` for code words, `<p>`, `<ul><li>` and `<ol><li>` for
structure, `<b>` sparingly. No inline styles or scripts.
