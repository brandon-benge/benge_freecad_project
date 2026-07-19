import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Build and start the local 3D viewer UI server.",
  args: {
    port: tool.schema.number().default(8080).describe("HTTP port for the UI server"),
    build: tool.schema.boolean().default(true).describe("Run python-cad build first"),
  },
  async execute({ port, build }, context) {
    const root = context.worktree || context.directory
    const python = process.platform === "win32" ? "python" : "python3"

    if (build) {
      const b = await Bun.$`python-cad build --project-root ${root}`.nothrow().quiet()
      if (b.exitCode !== 0) throw new Error(`Build failed:\n${b.stderr}`)
    }

    const proc = Bun.spawn([
      python, "-m", "python_cad_tools.cli", "serve",
      "--project-root", root,
      "--port", String(port),
    ], { stdout: "pipe", stderr: "pipe" })

    const reader = proc.stdout.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value)
      const match = text.match(/READY\s+(\S+)/)
      if (match) return `UI running at ${match[1]}`
    }

    const errText = await new Response(proc.stderr).text()
    throw new Error(`Server failed:\n${errText}`)
  },
})
