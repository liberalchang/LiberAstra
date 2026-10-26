import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api, type WorkflowInputSpec } from "@/api/client";
import { AspectSelect, ASPECT_OPTIONS, CUSTOM_RATIO, type AspectOption } from "@/components/ui/aspect-select";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { useTx } from "@/i18n/tx";

interface Props {
  inputs: Record<string, WorkflowInputSpec>;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  /** 已有专用表单字段的参数名（prompt、width 等），不再重复渲染 */
  exclude?: string[];
  /** ComfyUI Provider id：带 options_from 的参数据此拉取模型列表渲染下拉框 */
  providerId?: number;
  /** 视频包帧率：给了它，length/frames 帧数参数按"时长（秒）"设置，自动换算帧数 */
  fps?: number | null;
  /** 窄容器（如画布属性面板）强制单列，避免两列挤压截断 */
  singleColumn?: boolean;
}

/** 常见参数名的中文兜底（manifest 未写 label 时使用）。 */
const KEY_LABELS: Record<string, string> = {
  prompt: "提示词",
  negative_prompt: "负面提示词",
  ckpt_name: "Checkpoint 模型",
  model_name: "模型",
  unet_name: "UNET 模型",
  vae_name: "VAE 模型",
  clip_name: "CLIP 模型",
  lora_name: "LoRA 模型",
  seed: "随机种子",
  steps: "步数",
  cfg: "CFG 强度",
  denoise: "降噪强度",
  width: "宽度",
  height: "高度",
  batch_size: "张数",
  fps: "帧率",
  frames: "帧数",
};

function labelOf(key: string, spec: WorkflowInputSpec): string {
  return spec.label ?? KEY_LABELS[key] ?? key;
}

/** 从默认文件名提取家族关键词（wan、minimax_h3、qwen_image 等），用于下拉推荐排序。 */
function familyTokens(defaultStr: string): string[] {
  const base = defaultStr.split(/[\\/]/).pop() ?? defaultStr;
  return base
    .toLowerCase()
    .replace(/\.(safetensors|ckpt|pt|pth|bin|gguf)$/, "")
    .split(/[^a-z0-9]+/)
    .filter(
      (t) =>
        t.length >= 2 &&
        !/^(fp\d+|bf16|int\d+|nvfp4|awq|scaled|pruned|convrot|e4m3fn|master|model|v\d+)$/.test(t),
    );
}

/** options_from 参数：从 ComfyUI 模型目录拉取选项渲染下拉框，拉取失败回退为文本输入。 */
function ModelFolderField({
  providerId,
  folder,
  spec,
  value,
  onChange,
}: {
  providerId?: number;
  folder: string;
  spec: WorkflowInputSpec;
  value: string;
  onChange: (v: string) => void;
}) {
  const tx = useTx();
  const { data, isError, isLoading } = useQuery({
    queryKey: ["provider-model-folder", providerId, folder],
    queryFn: () => api.fetchProviderModelFolder(providerId!, folder),
    enabled: providerId != null,
    staleTime: 60_000,
  });

  // 节点 combo 可能含重复值（如 EdgeTTS 音色列表），先去重，避免 React key 冲突
  const rawOptions = [...new Set(data ?? [])];
  const defaultStr = spec.default != null ? String(spec.default) : "";
  // 与当前包默认模型同家族的排在前面（推荐），其余仍在列表里
  const tokens = familyTokens(defaultStr);
  const recommended = rawOptions.filter((o) => {
    const low = o.toLowerCase();
    return tokens.some((t) => low.includes(t));
  });
  const rest = rawOptions.filter((o) => !recommended.includes(o));
  const options = [...recommended, ...rest];

  // 列表就绪后：无选中 → 用包默认（在列表中）或第一项；默认文件名变了且旧值不在列表 → 重新落到默认
  useEffect(() => {
    if (isLoading || isError || options.length === 0) return;
    if (!value) {
      onChange(options.includes(defaultStr) ? defaultStr : options[0]);
      return;
    }
    if (defaultStr && value !== defaultStr && !options.includes(value) && options.includes(defaultStr)) {
      onChange(defaultStr);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, isError, options, value, defaultStr]);

  if (providerId == null || isError) {
    return (
      <Input
        type="text"
        placeholder={spec.default != null ? String(spec.default) : ""}
        value={value}
        required={spec.required}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  return (
    <select
      className={selectClass}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading}
    >
      {isLoading && <option value="">{tx("加载模型列表…")}</option>}
      {/* 已保存的值不在列表里时保留显示，避免被静默清空 */}
      {!isLoading && value && !options.includes(value) && (
        <option value={value}>{value}{tx("（不在列表中）")}</option>
      )}
      {recommended.length > 0 && rest.length > 0 ? (
        <>
          <optgroup label={tx("推荐（与当前工作流匹配）")}>
            {recommended.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </optgroup>
          <optgroup label={tx("全部")}>
            {rest.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </optgroup>
        </>
      ) : (
        options.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))
      )}
    </select>
  );
}

/** int 参数用步进器（与文生图一致）；字符串值与数值互转，空值回落到 manifest 默认值。 */
function intValueOf(raw: string | undefined, spec: WorkflowInputSpec): number {
  const n = raw != null && raw !== "" ? Number(raw) : NaN;
  if (Number.isFinite(n)) return n;
  const fallback = Number(spec.default ?? spec.min ?? 0);
  return Number.isFinite(fallback) ? fallback : 0;
}

/** 按工作流包 manifest 动态渲染参数表单。 */
export function WorkflowInputs({ inputs, values, onChange, exclude = [], providerId, fps, singleColumn }: Props) {
  const tx = useTx();
  // 帧数对齐：有效帧数 = align_base × k + align_offset（如 MiniMax 的 17k+5、Wan 的 4k+1）
  const snapFrames = (n: number, spec: WorkflowInputSpec) => {
    if (!spec.align_base) return n;
    const off = spec.align_offset ?? 0;
    const k = Math.max(0, Math.round((n - off) / spec.align_base));
    return spec.align_base * k + off;
  };
  // 已记忆的帧数若不对齐，进入页面时自动吸附一次
  useEffect(() => {
    if (!fps) return;
    for (const [key, spec] of Object.entries(inputs)) {
      if ((key === "length" || key === "frames") && spec.type === "int" && spec.align_base) {
        const f = intValueOf(values[key], spec);
        const snapped = snapFrames(f, spec);
        if (snapped !== f) onChange(key, String(snapped));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fps, inputs]);
  // 宽高同时在场且未被排除时合并为一个宽高比控件，长边对齐包默认尺寸
  const widthSpec = inputs.width;
  const heightSpec = inputs.height;
  const mergeWH =
    !!widthSpec && !!heightSpec &&
    widthSpec.type !== "image" && heightSpec.type !== "image" &&
    !exclude.includes("width") && !exclude.includes("height");
  const entries = Object.entries(inputs).filter(
    ([key, spec]) =>
      !exclude.includes(key) && spec.type !== "image" && !(mergeWH && (key === "width" || key === "height")),
  );
  // 视频潜变量按包声明的倍数压缩（MiniMax 系 32，Wan 系 16）：宽高吸附到该倍数
  const mult = widthSpec?.multiple ?? 16;
  const snapSide = (n: number) => Math.max(mult, Math.round(n / mult) * mult);
  // 已记忆的宽高若不是倍数（如旧版遗留的 752），进入页面时自动吸附一次
  useEffect(() => {
    if (!mergeWH || !widthSpec || !heightSpec) return;
    const w = intValueOf(values.width, widthSpec);
    const h = intValueOf(values.height, heightSpec);
    const sw = snapSide(w);
    const sh = snapSide(h);
    if (sw !== w || sh !== h) {
      onChange("width", String(sw));
      onChange("height", String(sh));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mult, mergeWH]);
  if (entries.length === 0 && !mergeWH) return null;

  let aspectBlock: React.ReactNode = null;
  if (mergeWH) {
    const defW = Number(widthSpec.default ?? 832) || 832;
    const defH = Number(heightSpec.default ?? 480) || 480;
    const long = Math.max(defW, defH);
    const ratioOptions: AspectOption[] = [
      { ratio: "默认", width: snapSide(defW), height: snapSide(defH) },
      ...ASPECT_OPTIONS.map((o) => {
        const scale = long / Math.max(o.width, o.height);
        return { ratio: o.ratio, width: snapSide(o.width * scale), height: snapSide(o.height * scale) };
      }),
    ];
    const curW = intValueOf(values.width, widthSpec);
    const curH = intValueOf(values.height, heightSpec);
    const matched = ratioOptions.find((o) => o.width === curW && o.height === curH);
    aspectBlock = (
      <Field label={tx("宽高比")} hint={tx("按比例一次设置宽高；长边对齐包默认尺寸，两边自动吸附 {mult} 的倍数（视频潜变量要求）。", { mult })} className="sm:col-span-2">
        <AspectSelect
          label={tx("宽高比")}
          options={ratioOptions}
          value={matched ?? { ratio: CUSTOM_RATIO, width: curW, height: curH }}
          onChange={(o) => {
            onChange("width", String(snapSide(o.width)));
            onChange("height", String(snapSide(o.height)));
          }}
        />
      </Field>
    );
  }

  return (
    <div className={singleColumn ? "grid gap-3" : "grid gap-3 sm:grid-cols-2"}>
      {aspectBlock}
      {entries.map(([key, spec]) => {
        // 视频包给了 fps：帧数参数改按"时长（秒）"设置，提交时换算回帧数并按包声明对齐
        const isFramesParam = (key === "length" || key === "frames") && spec.type === "int" && !!fps;
        const framesNow = isFramesParam ? intValueOf(values[key], spec) : 0;
        return (
          <Field
            key={key}
            label={tx(isFramesParam ? tx("时长（秒）") : labelOf(key, spec)) + (spec.required ? " *" : "")}
            hint={
              isFramesParam
                ? tx("帧数 = 秒 × {fps}fps，当前 {frames} 帧", { fps, frames: framesNow }) +
                  (spec.align_base
                    ? tx("，按 {base}k+{off} 对齐", { base: spec.align_base, off: spec.align_offset ?? 0 })
                    : "")
                : tx(spec.description || tx("来自工作流包 manifest 的参数"))
            }
            className={key === "negative_prompt" ? "sm:col-span-2" : undefined}
          >
            {spec.options && spec.options.length > 0 ? (
              <select
                className={selectClass}
                value={values[key] ?? (spec.default != null ? String(spec.default) : "")}
                required={spec.required}
                onChange={(e) => onChange(key, e.target.value)}
              >
                {spec.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {tx(String(opt))}
                  </option>
                ))}
              </select>
            ) : spec.options_from ? (
              <ModelFolderField
                providerId={providerId}
                folder={spec.options_from}
                spec={spec}
                value={values[key] ?? ""}
                onChange={(v) => onChange(key, v)}
              />
            ) : isFramesParam ? (
              <NumberStepper
                ariaLabel={tx("时长（秒）")}
                min={Math.max(1, Math.round((spec.min ?? fps) / fps))}
                max={Math.max(2, Math.round((spec.max ?? 300) / fps))}
                value={Math.max(1, Math.round(framesNow / fps))}
                onChange={(s) => onChange(key, String(snapFrames(s * fps, spec)))}
              />
            ) : spec.type === "int" ? (
              <NumberStepper
                ariaLabel={tx(labelOf(key, spec))}
                min={spec.min}
                max={spec.max}
                value={intValueOf(values[key], spec)}
                onChange={(n) => onChange(key, String(n))}
              />
            ) : spec.type === "float" && spec.min != null && spec.max != null ? (
              <NumberStepper
                ariaLabel={tx(labelOf(key, spec))}
                min={spec.min}
                max={spec.max}
                step={0.1}
                value={intValueOf(values[key], spec)}
                onChange={(n) => onChange(key, String(n))}
              />
            ) : (
              <Input
                type={spec.type === "float" ? "number" : "text"}
                placeholder={spec.default != null ? String(spec.default) : ""}
                value={values[key] ?? ""}
                required={spec.required}
                min={spec.min}
                max={spec.max}
                step={spec.type === "float" ? "0.1" : undefined}
                onChange={(e) => onChange(key, e.target.value)}
              />
            )}
          </Field>
        );
      })}
    </div>
  );
}
