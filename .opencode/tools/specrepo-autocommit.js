import { tool } from "@opencode-ai/plugin"
import { fileURLToPath } from "node:url"

const script = fileURLToPath(new URL("./specrepo-autocommit.py", import.meta.url))

export default tool({
  description: "Save verified changes through SpecRepo autocommit; callable only by the save agent.",
  args: {
    summary: tool.schema.string().trim().min(1).describe("What changed and why"),
  },
  async execute({ summary }, context) {
    if (context.agent !== "save") {
      throw new Error("specrepo-autocommit is restricted to the save agent.")
    }
    const python = process.platform === "win32" ? "python" : "python3"
    const result = await Bun.$`${python} ${script} ${summary}`
      .cwd(context.worktree || context.directory)
      .nothrow()
      .quiet()
    const output = `${result.stdout}${result.stderr}`.trim()

    if (result.exitCode !== 0) throw new Error(output)
    return output || "Autocommit completed successfully."
  },
})