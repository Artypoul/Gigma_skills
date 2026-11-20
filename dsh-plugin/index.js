import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const BUNDLED_SKILL_RANK = 600

export const name = 'gigma-skills'
export const inject = ['skills']

const SKILL_NAMES = [
  'fable5-codex',
  'brainstorming',
  'diagnosing-superpowers',
  'dispatching-parallel-agents',
  'executing-plans',
  'finishing-a-development-branch',
  'receiving-code-review',
  'requesting-code-review',
  'subagent-driven-development',
  'systematic-debugging',
  'test-driven-development',
  'using-git-worktrees',
  'using-superpowers',
  'verification-before-completion',
  'writing-plans',
  'writing-skills',
]

function parseFrontmatter(raw) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(raw)
  if (!match) throw new Error('no frontmatter')
  const body = raw.slice(match[0].length).trim()
  const m = /^description:\s*(.+?)\s*$/m.exec(match[1])
  if (!m) throw new Error('no description')
  let description = m[1].trim()
  if (description.startsWith('"') && description.endsWith('"')) {
    description = JSON.parse(description)
  } else if (description.startsWith("'") && description.endsWith("'")) {
    description = description.slice(1, -1).replace(/''/g, "'")
  }
  return { description, body }
}

export function apply(ctx, config = {}) {
  const root = config.assetRoot ?? fileURLToPath(new URL('./skills/', import.meta.url))

  async function readSkill(skillName, signal) {
    const path = join(root, skillName, 'SKILL.md')
    const raw = await readFile(path, { encoding: 'utf8', signal })
    return parseFrontmatter(raw)
  }

  ctx.skills.registerProvider(control => ({
    name: 'gigma-skills',
    async list(options) {
      const candidates = []
      for (const skillName of SKILL_NAMES) {
        try {
          const { description } = await readSkill(skillName, options.signal)
          candidates.push({
            name: skillName,
            description,
            invocation: { modelInvocable: true, userInvocable: true },
            provider: 'gigma-skills',
            source: 'bundled',
            rank: BUNDLED_SKILL_RANK,
            resourceBase: { kind: 'directory', path: join(root, skillName).replace(/\\/g, '/') },
            locator: skillName,
          })
        } catch (error) {
          if (options.signal?.aborted === true) throw error
          ctx.logger.warn(`gigma-skills: skill "${skillName}" unavailable: ${error}`)
        }
      }
      return candidates
    },
    async get(candidate, options) {
      const { rank, locator, ...summary } = candidate
      const { body } = await readSkill(locator, options.signal)
      return { ...summary, content: body }
    },
  }))
}
