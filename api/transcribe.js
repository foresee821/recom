const MAX_AUDIO_BYTES = 4 * 1024 * 1024;

module.exports = async function handler(request, response) {
  const allowedOrigin = request.headers.origin === "https://foresee821.github.io"
    ? request.headers.origin
    : "https://recom-tau.vercel.app";
  response.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  response.setHeader("Vary", "Origin");
  response.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (request.method === "OPTIONS") return response.status(204).end();
  if (request.method !== "POST") {
    response.setHeader("Allow", "POST");
    return response.status(405).json({ error: "仅支持 POST 请求" });
  }
  if (!process.env.OPENAI_API_KEY) {
    return response.status(503).json({ error: "服务端尚未配置 OPENAI_API_KEY" });
  }

  try {
    const { audio, mimeType = "audio/webm" } = request.body || {};
    if (!audio || typeof audio !== "string") {
      return response.status(400).json({ error: "没有收到录音" });
    }
    const bytes = Buffer.from(audio, "base64");
    if (!bytes.length) return response.status(400).json({ error: "录音内容为空" });
    if (bytes.length > MAX_AUDIO_BYTES) {
      return response.status(413).json({ error: "录音时间过长，请控制在 20 秒内" });
    }

    const extension = mimeType.includes("mp4") ? "m4a" : "webm";
    const form = new FormData();
    form.append("file", new Blob([bytes], { type: mimeType }), `voice.${extension}`);
    form.append("model", "gpt-4o-mini-transcribe");
    form.append("language", "zh");
    form.append("response_format", "json");
    form.append("prompt", "这是中文电商购物语音。常见词包括：淘宝、跑鞋、运动鞋、连衣裙、韩式、通勤、防晒霜、出租屋、演唱会、幸福感。请使用简体中文和自然标点。");

    const upstream = await fetch("https://api.openai.com/v1/audio/transcriptions", {
      method: "POST",
      headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
      body: form,
      signal: AbortSignal.timeout(22000),
    });
    const result = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      console.error("OpenAI transcription failed", upstream.status, result?.error?.type);
      const insufficientQuota = result?.error?.code === "insufficient_quota"
        || result?.error?.type === "insufficient_quota";
      return response.status(upstream.status === 429 ? 429 : 502).json({
        error: insufficientQuota
          ? "语音 API 额度不足，请补充额度后重试"
          : upstream.status === 429
            ? "语音服务繁忙，请稍后重试"
            : "语音识别失败，请稍后重试",
      });
    }
    return response.status(200).json({ text: String(result.text || "").trim() });
  } catch (error) {
    console.error("Transcription handler error", error);
    const timedOut = error?.name === "TimeoutError" || error?.name === "AbortError";
    return response.status(timedOut ? 504 : 500).json({
      error: timedOut ? "语音识别超时，请稍后重试" : "语音识别服务异常",
    });
  }
};
