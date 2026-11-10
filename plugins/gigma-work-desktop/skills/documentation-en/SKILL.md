---
name: documentation-en
description: Use when editing README files, plans, guides, release notes, project docs, or documentation audits for the Gigma Work repository.
---

# English documentation

Product documentation is English-only. Before merging documentation changes:

1. Scan tracked documentation and Markdown files for CJK ideographs.
2. Translate product text into clear English or remove obsolete product documentation.
3. Preserve code identifiers, URLs, protocol values, and required license attribution.
4. Do not rewrite vendored source code or legal notices merely to change prose language.
5. Run `git diff --check` and the repository identity/documentation scans.

Use concise headings, concrete commands, and paths that exist in the current repository. Historical plan documents should state when a fact is historical instead of presenting it as current behavior.

## Audit command

Use a Unicode-aware scan over `README*`, `docs`, `.github`, `.agents`, and project Markdown files. Review every match manually because code examples and legal text have different handling rules.
