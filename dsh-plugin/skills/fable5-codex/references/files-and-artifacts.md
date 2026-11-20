# Files and artifacts

## File handling
- Confirm the file exists and inspect its content before relying on it.
- Use the matching format-specific skill or connector when available.
- Prefer native text/file readers for extraction; use programmatic processing when structure, scale, or conversion requires it.
- For PDFs and office documents, inspect rendered pages when layout, tables, screenshots, or scans affect correctness.
- Preserve original files unless the user asks to edit them. Prefer a copy or explicit versioned output for risky transformations.

## Creation and editing
- Select the output format based on the user's intended use, not convenience.
- Preserve formulas, links, metadata, fonts, and accessibility where applicable.
- Validate generated files by reopening them and checking structure/content; render when appearance matters.
- Do not claim a file exists or is downloadable until the exact path is verified.

## Persistence and sharing
- Save to the requested destination using its supported connector/workflow.
- Distinguish temporary workspace files from durable Library/Drive artifacts.
- Confirm the final path, share permissions, and version after a write.
- Never infer sandbox links from filenames or previous sessions.
