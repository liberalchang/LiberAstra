/** 把任务错误收成用户能照着改的一句话；原始文本留给详情。 */
export function explainJobError(error: string): { summary: string; detail: string } {
  const detail = error.trim();
  if (/mat1 and mat2|shapes cannot be multiplied|Load CLIP|CLIP Loader/i.test(detail)) {
    return {
      summary: "主模型和文本编码器对不上。打开高级参数，换成同一套模型后再重试。",
      detail,
    };
  }
  if (/无法连接|Server disconnected|ReadError|请求超时|timed? out/i.test(detail)) {
    return {
      summary: "连不上模型服务。到服务提供方确认地址已经打开，然后再重试。",
      detail,
    };
  }
  if (/Required input is missing/i.test(detail)) {
    return {
      summary: "工作流包还缺必填项。打开高级参数补上缺少的字段后再重试。",
      detail,
    };
  }
  const summary = detail.length > 140 ? `${detail.slice(0, 140)}…` : detail;
  return { summary, detail };
}
