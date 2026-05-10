(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const formSection = $("form-section");
  const progressSection = $("progress-section");
  const resultSection = $("result-section");
  const errorSection = $("error-section");

  const form = $("book-form");
  const submitBtn = $("submit-btn");
  const progressFill = $("progress-fill");
  const progressPct = $("progress-pct");
  const progressMessage = $("progress-message");
  const resultTitle = $("result-title");
  const resultStats = $("result-stats");
  const downloadMd = $("download-md");
  const downloadDocx = $("download-docx");
  const errorMessage = $("error-message");

  let pollTimer = null;
  let savedApiKey = sessionStorage.getItem("gemini_api_key") || "";
  if (savedApiKey) {
    $("api_key").value = savedApiKey;
  }

  function show(el) { el.classList.remove("hidden"); }
  function hide(el) { el.classList.add("hidden"); }

  function setProgress(pct, message) {
    progressFill.style.width = `${pct}%`;
    progressPct.textContent = `${pct}%`;
    if (message) progressMessage.textContent = message;
  }

  function reset() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    submitBtn.disabled = false;
    submitBtn.textContent = "本を作成する";
    setProgress(0, "準備中…");
    show(formSection);
    hide(progressSection);
    hide(resultSection);
    hide(errorSection);
  }

  async function startGeneration(payload) {
    const fd = new FormData();
    Object.entries(payload).forEach(([k, v]) => fd.append(k, v));
    const res = await fetch("/generate", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "送信に失敗しました" }));
      throw new Error(err.detail || "送信に失敗しました");
    }
    return res.json();
  }

  async function pollStatus(jobId) {
    const res = await fetch(`/status/${jobId}`);
    if (!res.ok) throw new Error("状態取得に失敗しました");
    return res.json();
  }

  function showResult(jobId, result) {
    resultTitle.textContent = `『${result.title}』 ── ${result.subtitle}`;
    resultStats.textContent = `全 ${result.chapter_count} 章 ／ 約 ${result.char_count.toLocaleString()} 文字`;
    downloadMd.href = `/download/${jobId}/book_full.md`;
    downloadMd.download = "book_full.md";
    downloadDocx.href = `/download/${jobId}/book_full.docx`;
    downloadDocx.download = "book_full.docx";
    hide(progressSection);
    show(resultSection);
  }

  function showError(message) {
    errorMessage.textContent = message;
    hide(progressSection);
    show(errorSection);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      theme: $("theme").value.trim(),
      target_layer: $("target_layer").value,
      author: $("author").value.trim(),
      api_key: $("api_key").value.trim(),
    };
    if (!payload.theme || !payload.author || !payload.api_key) {
      alert("未入力の項目があります。");
      return;
    }
    sessionStorage.setItem("gemini_api_key", payload.api_key);

    submitBtn.disabled = true;
    submitBtn.textContent = "送信中…";

    try {
      const { job_id } = await startGeneration(payload);
      hide(formSection);
      show(progressSection);
      setProgress(2, "送信しました。生成を開始します…");

      pollTimer = setInterval(async () => {
        try {
          const state = await pollStatus(job_id);
          if (state.status === "running") {
            setProgress(state.progress || 0, state.message || "生成中…");
          } else if (state.status === "done") {
            clearInterval(pollTimer);
            pollTimer = null;
            setProgress(100, state.message || "完了しました。");
            setTimeout(() => showResult(job_id, state.result), 600);
          } else if (state.status === "error") {
            clearInterval(pollTimer);
            pollTimer = null;
            showError(state.message || "エラーが発生しました。");
          }
        } catch (err) {
          // 一時的な通信エラーは無視
          console.warn(err);
        }
      }, 2000);
    } catch (err) {
      showError(err.message || "送信に失敗しました。");
      submitBtn.disabled = false;
      submitBtn.textContent = "本を作成する";
    }
  });

  $("reset-btn").addEventListener("click", reset);
  $("retry-btn").addEventListener("click", reset);
})();
