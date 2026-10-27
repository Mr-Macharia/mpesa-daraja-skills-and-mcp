/**
 * Vercel AI SDK tools (ai >= 5):
 *
 *   import { generateText } from "ai";
 *   import { Daraja } from "mpesa-daraja";
 *   import { mpesaAiTools, INSTRUCTIONS } from "mpesa-daraja/ai";
 *
 *   const daraja = Daraja.fromEnv(process.env, { approve: async (summary) => askHuman(summary) });
 *   await generateText({ model, system: INSTRUCTIONS, tools: mpesaAiTools(daraja), prompt });
 */

import { jsonSchema, type Tool, tool } from "ai";

import type { Daraja } from "./client.ts";
import { type AgentTool, mpesaTools, type ToolOptions } from "./tools.ts";

export { INSTRUCTIONS } from "./tools.ts";

export function toAiTool(t: AgentTool): Tool {
  return tool({
    description: t.description,
    inputSchema: jsonSchema<Record<string, any>>(t.parameters as any),
    execute: (args: Record<string, any>) => t.execute(args),
  });
}

/** The M-Pesa tools keyed mpesa_<name>, ready for generateText / streamText `tools`. */
export function mpesaAiTools(daraja: Daraja, options: ToolOptions = {}): Record<string, Tool> {
  return Object.fromEntries(mpesaTools(daraja, options).map((t) => [`mpesa_${t.name}`, toAiTool(t)]));
}
