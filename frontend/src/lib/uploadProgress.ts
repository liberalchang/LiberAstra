/** 全局上传进度：请求层写入，Layout 里的进度条订阅。 */

export type UploadTask = {
  id: number;
  label: string;
  percent: number;
};

let tasks: UploadTask[] = [];
let seq = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function subscribeUploads(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getUploads(): UploadTask[] {
  return tasks;
}

export function startUpload(label: string): number {
  const id = ++seq;
  tasks = [...tasks, { id, label, percent: 0 }];
  emit();
  return id;
}

export function updateUpload(id: number, percent: number): void {
  const next = Math.max(0, Math.min(100, percent));
  tasks = tasks.map((task) =>
    task.id === id ? { ...task, percent: Math.max(task.percent, next) } : task,
  );
  emit();
}

export function finishUpload(id: number): void {
  tasks = tasks.filter((task) => task.id !== id);
  emit();
}
