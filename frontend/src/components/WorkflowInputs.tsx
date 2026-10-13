import type { WorkflowInputSpec } from "@/api/client";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

interface Props {
  inputs: Record<string, WorkflowInputSpec>;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  /** 已有专用表单字段的参数名（prompt、width 等），不再重复渲染 */
  exclude?: string[];
}

/** 按工作流包 manifest 动态渲染参数表单。 */
export function WorkflowInputs({ inputs, values, onChange, exclude = [] }: Props) {
  const entries = Object.entries(inputs).filter(
    ([key, spec]) => !exclude.includes(key) && spec.type !== "image",
  );
  if (entries.length === 0) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, spec]) => (
        <Field
          key={key}
          label={`${key}${spec.required ? " *" : ""}`}
          hint={spec.description || "来自工作流包 manifest 的参数"}
        >
          <Input
            type={spec.type === "int" || spec.type === "float" ? "number" : "text"}
            placeholder={spec.default != null ? String(spec.default) : ""}
            value={values[key] ?? ""}
            required={spec.required}
            min={spec.min}
            max={spec.max}
            step={spec.type === "float" ? "0.1" : undefined}
            onChange={(e) => onChange(key, e.target.value)}
          />
        </Field>
      ))}
    </div>
  );
}
