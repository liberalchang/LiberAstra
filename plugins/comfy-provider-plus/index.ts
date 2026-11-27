import { definePluginEntry } from "./src/shims/plugin-entry.js";
import {
  DEFAULT_COMFY_PLUS_MODEL,
  MAX_INPUT_IMAGES,
  PLUGIN_ID,
  PROVIDER_ID,
} from "./src/config/defaults.js";
import { generateComfyPlusImage, isComfyPlusConfigured } from "./src/provider-runtime.js";

/**
 * OpenClaw 宿主若提供 `openclaw/plugin-sdk/plugin-entry`，可在安装环境替换本 shim。
 * 插件契约：id=`comfy-plus`，provider=`comfy-plus`，默认模型 `workflow`。
 */
const comfyPlusPlugin = definePluginEntry({
  id: PLUGIN_ID,
  name: "ComfyUI Provider Plus",
  description:
    "Qwen-Image 2.1 文生图与 1–16 张多图参考编辑（comfy-plus）；调色/换姿默认关闭",
  register(api) {
    api.registerImageGenerationProvider({
      id: PROVIDER_ID,
      label: "ComfyUI Plus",
      defaultModel: DEFAULT_COMFY_PLUS_MODEL,
      models: [DEFAULT_COMFY_PLUS_MODEL],
      defaultTimeoutMs: 600_000,
      isConfigured: ({ cfg }: { cfg?: unknown }) => isComfyPlusConfigured(cfg),
      isConfiguredAsync: async ({ cfg }: { cfg?: unknown }) => isComfyPlusConfigured(cfg),
      capabilities: {
        generate: {
          maxCount: 1,
          supportsSize: true,
          supportsAspectRatio: false,
          supportsResolution: false,
        },
        edit: {
          enabled: true,
          maxCount: 1,
          maxInputImages: MAX_INPUT_IMAGES,
          supportsSize: true,
          supportsAspectRatio: false,
          supportsResolution: false,
        },
      },
      async generateImage(req: {
        prompt: string;
        model?: string;
        cfg?: unknown;
        timeoutMs?: number;
        size?: string;
        inputImages?: Array<{ buffer?: Buffer; mimeType?: string; fileName?: string }>;
        providerOptions?: Record<string, unknown>;
      }) {
        const result = await generateComfyPlusImage(req);
        return {
          images: result.images,
          model: `${PROVIDER_ID}/${result.model}`,
          metadata: result.metadata,
        };
      },
    });
  },
});

export default comfyPlusPlugin;
