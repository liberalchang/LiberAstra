import { Loader2, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { previewTts } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";

/** 本地 TTS（edge_tts）和 API TTS（openai_tts）才提供即时试听。 */
export function supportsTtsPreview(type: string | undefined): boolean {
  return type === "edge_tts" || type === "openai_tts";
}

/** 试听：一句短文本 + 喇叭。点一下用当前音色合成并播放。 */
export function TtsPreview({ providerId, voice }: { providerId: number; voice: string }) {
  const tx = useTx();
  const [text, setText] = useState("你好,这是一段试听语音! ");
  const [pending, setPending] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const busyRef = useRef(false);
  const genRef = useRef(0);

  function release() {
    audioRef.current?.pause();
    audioRef.current = null;
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }

  useEffect(() => {
    setPlaying(false);
    setPending(false);
    busyRef.current = false;
    return () => {
      // 切服务或卸载时丢掉进行中的合成，避免喇叭消失后还在后台播放
      genRef.current += 1;
      release();
    };
  }, [providerId, voice]);

  async function play() {
    if (playing) {
      release();
      setPlaying(false);
      return;
    }
    const sample = text.trim();
    if (!voice.trim()) {
      setError(tx("请先选择音色"));
      return;
    }
    if (!sample) {
      setError(tx("请输入试听文本"));
      return;
    }
    if (sample.length > 200) {
      setError(tx("试听文本请控制在 200 字以内"));
      return;
    }
    if (busyRef.current) return;
    const gen = ++genRef.current;
    busyRef.current = true;
    setError(null);
    setPending(true);
    try {
      const blob = await previewTts({ provider_id: providerId, voice: voice.trim(), text: sample });
      if (gen !== genRef.current) return;
      release();
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        if (gen === genRef.current) setPlaying(false);
      };
      await audio.play();
      if (gen !== genRef.current) {
        release();
        return;
      }
      setPlaying(true);
    } catch (err) {
      if (gen === genRef.current) {
        setError(err instanceof Error ? err.message : tx("试听失败"));
      }
    } finally {
      if (gen === genRef.current) {
        busyRef.current = false;
        setPending(false);
      }
    }
  }

  return (
    <Field label={tx("试听")} hint={tx("输入一句短文本，点喇叭用当前音色试听。")}>
      <div className="flex gap-2">
        <Input
          value={text}
          aria-label={tx("输入试听文本")}
          placeholder={tx("输入试听文本")}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void play();
            }
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="size-11 shrink-0"
          title={playing ? tx("停止试听") : tx("试听")}
          aria-label={playing ? tx("停止试听") : tx("试听")}
          disabled={pending}
          onClick={() => void play()}
        >
          {pending ? <Loader2 className="animate-spin" /> : <Volume2 />}
        </Button>
      </div>
      {error ? (
        <p className="text-xs text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </Field>
  );
}
