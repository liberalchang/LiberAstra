export type PluginApi = {
  registerImageGenerationProvider: (provider: Record<string, unknown>) => void;
};

export type PluginEntry = {
  id: string;
  name: string;
  description: string;
  register: (api: PluginApi) => void;
};

/** 无宿主时的轻量包装；OpenClaw 安装环境可解析官方同名 API */
export function definePluginEntry<T extends PluginEntry>(entry: T): T {
  return entry;
}
