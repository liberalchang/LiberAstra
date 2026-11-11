/** 模型原声跨镜音频连续性：上一镜尾音或全片氛围底。 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";

export interface AudioContinuityValue {
  strategy: "native" | "previous_tail" | "global_bed";
  refSeconds: number;
  bedPath: string;
  bedFill: "loop" | "silence";
  bedMode: "mix" | "replace";
  seamFadeMs: number;
}

export function AudioContinuityControl({
  value,
  onChange,
  disabledReason,
}: {
  value: AudioContinuityValue;
  onChange: (patch: Partial<AudioContinuityValue>) => void;
  disabledReason?: string;
}) {
  const tx = useTx();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const { data: bgmList } = useQuery({
    queryKey: ["bgm"],
    queryFn: api.listBgm,
    enabled: value.strategy === "global_bed",
  });

  if (disabledReason) {
    return <p className="text-xs leading-relaxed text-muted-foreground">{disabledReason}</p>;
  }

  const upload = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const item = await api.uploadBgm(file);
      onChange({ bedPath: `bgm/${item.name}` });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setUploading(false);
    }
  };

  const bedName = value.bedPath.startsWith("bgm/") ? value.bedPath.slice(4) : value.bedPath;

  return (
    <div className="flex flex-col gap-3">
      <Field
        label={tx("音频连续性（实验）")}
        hint={tx("只对模型原声生效；参考音频是引导，不是音频锁定。")}
      >
        <Segmented
          ariaLabel={tx("音频连续性")}
          value={value.strategy}
          onChange={(next) =>
            onChange({ strategy: next as AudioContinuityValue["strategy"] })
          }
          options={[
            { value: "native", label: tx("模型原生") },
            { value: "previous_tail", label: tx("上一镜尾音") },
            { value: "global_bed", label: tx("全片氛围底") },
          ]}
        />
      </Field>

      {value.strategy === "previous_tail" && (
        <Field label={tx("参考长度（秒）")} hint={tx("第 1 镜没有参考；之后按顺序生成。")}>
          <Input
            type="number"
            min={2}
            max={15}
            step={1}
            value={value.refSeconds}
            onChange={(e) =>
              onChange({ refSeconds: Math.max(2, Math.min(15, Number(e.target.value) || 5)) })
            }
          />
        </Field>
      )}

      {value.strategy === "global_bed" && (
        <>
          <Field
            label={tx("氛围底音频")}
            hint={tx("按分镜累计时长切片送给 H3；不是成片后的背景音乐。")}
          >
            <select
              className={selectClass}
              value={bedName}
              onChange={(e) => onChange({ bedPath: e.target.value ? `bgm/${e.target.value}` : "" })}
            >
              <option value="">{tx("选择音乐库音频…")}</option>
              {bedName && !bgmList?.some((item) => item.name === bedName) && (
                <option value={bedName}>{bedName}{tx("（已不在库中）")}</option>
              )}
              {bgmList?.map((item) => (
                <option key={item.name} value={item.name}>{item.name}</option>
              ))}
            </select>
            <label className="mt-2 inline-flex cursor-pointer items-center text-xs text-primary underline-offset-4 hover:underline">
              {uploading ? tx("上传中…") : tx("上传音频到音乐库")}
              <input
                type="file"
                accept="audio/*"
                className="hidden"
                disabled={uploading}
                onChange={(e) => void upload(e.target.files?.[0] ?? null)}
              />
            </label>
          </Field>
          <Field
            label={tx("床长不足时")}
            hint={tx("循环会把氛围底接回开头；补静音会让本镜没有参考音频。")}
          >
            <select
              className={selectClass}
              value={value.bedFill}
              onChange={(e) =>
                onChange({ bedFill: e.target.value as AudioContinuityValue["bedFill"] })
              }
            >
              <option value="loop">{tx("循环")}</option>
              <option value="silence">{tx("补静音")}</option>
            </select>
          </Field>
          {!value.bedPath && (
            <p role="alert" className="text-xs text-danger">
              {tx("请选择或上传一段氛围底音频，否则本次按模型原生音频执行。")}
            </p>
          )}
          <Field
            label={tx("成片混音")}
            hint={tx("bed 为主会压低模型环境音；只用 bed 覆盖会移除模型原声。")}
          >
            <select
              className={selectClass}
              value={value.bedMode ?? "mix"}
              onChange={(e) =>
                onChange({ bedMode: e.target.value as AudioContinuityValue["bedMode"] })
              }
            >
              <option value="mix">{tx("bed 为主，模型环境音低音量混入")}</option>
              <option value="replace">{tx("只用 bed 覆盖")}</option>
            </select>
          </Field>
        </>
      )}

      {value.strategy !== "native" && (
        <Field
          label={tx("接缝淡化（毫秒）")}
          hint={tx("只作用于音乐/环境音；0 表示关闭。")}
        >
          <Input
            type="number"
            min={0}
            max={200}
            step={10}
            value={value.seamFadeMs}
            onChange={(e) =>
              onChange({ seamFadeMs: Math.max(0, Math.min(200, Number(e.target.value) || 0)) })
            }
          />
        </Field>
      )}

      {value.strategy === "global_bed" && (
        <p className="text-xs leading-relaxed text-warning">
          {tx("全片氛围底和成片背景音乐是两层；同时设置可能重复音乐，建议只保留一层。")}
        </p>
      )}
      {error && <p role="alert" className="text-xs text-danger">{error}</p>}
    </div>
  );
}
