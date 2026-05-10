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
  const progressReferences = $("progress-references");
  const resultTitle = $("result-title");
  const resultStats = $("result-stats");
  const downloadMd = $("download-md");
  const downloadDocx = $("download-docx");
  const downloadNotebookLM = $("download-notebooklm");
  const errorMessage = $("error-message");
  const projectList = $("project-list");

  const PROJECT_STORE_KEY = "book_maker_projects_v2";
  const API_KEY_STORE = "gemini_api_key";

  let pollTimer = null;
  let currentProjectId = null;

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

  // -------------------------------------------------------------------
  // プロジェクト管理（localStorage）
  // -------------------------------------------------------------------
  function loadProjects() {
    try {
      return JSON.parse(localStorage.getItem(PROJECT_STORE_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }
  function saveProjects(projects) {
    localStorage.setItem(PROJECT_STORE_KEY, JSON.stringify(projects.slice(0, 50)));
  }
  function upsertProject(project) {
    const projects = loadProjects();
    const idx = projects.findIndex((p) => p.id === project.id);
    if (idx >= 0) projects[idx] = { ...projects[idx], ...project };
    else projects.unshift(project);
    saveProjects(projects);
    renderProjects();
  }
  function renderProjects() {
    const projects = loadProjects();
    projectList.innerHTML = "";
    if (!projects.length) {
      projectList.innerHTML = '<li style="cursor:default;color:#9aa3af;background:transparent;border:none;">（まだプロジェクトがありません）</li>';
      return;
    }
    for (const p of projects) {
      const li = document.createElement("li");
      li.textContent = p.name || p.id;
      li.title = `${p.theme || ""} / ${p.created_at || ""}`;
      if (currentProjectId === p.id) li.classList.add("active");
      li.addEventListener("click", () => loadProjectIntoForm(p));
      projectList.appendChild(li);
    }
  }
  function loadProjectIntoForm(p) {
    currentProjectId = p.id;
    $("theme").value = p.theme || "";
    $("target_layer").value = p.target_layer || $("target_layer").value;
    $("author").value = p.author || "";
    $("ref_urls").value = p.ref_urls || "";
    $("notebooklm_urls").value = p.notebooklm_urls || "";
    renderProjects();
    if (p.last_job_id && p.result) {
      showResult(p.last_job_id, p.result);
    } else {
      reset();
    }
  }
  function newProject() {
    currentProjectId = null;
    $("theme").value = "";
    $("ref_urls").value = "";
    $("notebooklm_urls").value = "";
    $("files").value = "";
    $("images").value = "";
    $("file-list").innerHTML = "";
    $("image-list").innerHTML = "";
    renderProjects();
    reset();
  }

  // -------------------------------------------------------------------
  // ファイル選択時のリスト表示
  // -------------------------------------------------------------------
  function bindFileList(inputId, listId) {
    $(inputId).addEventListener("change", (e) => {
      const ul = $(listId);
      ul.innerHTML = "";
      Array.from(e.target.files).forEach((f) => {
        const li = document.createElement("li");
        li.textContent = `📎 ${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
        ul.appendChild(li);
      });
    });
  }
  bindFileList("files", "file-list");
  bindFileList("images", "image-list");

  // -------------------------------------------------------------------
  // 通信
  // -------------------------------------------------------------------
  async function startGeneration(payload) {
    const fd = new FormData();
    Object.entries(payload).forEach(([k, v]) => fd.append(k, v));
    Array.from($("files").files).forEach((f) => fd.append("files", f));
    Array.from($("images").files).forEach((f) => fd.append("images", f));
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
    resultTitle.textContent = `『${result.title}』 ── ${result.subtitle || ""}`;
    const refStr = result.reference_count ? ` ／ 参照 ${result.reference_count} 件` : "";
    resultStats.textContent = `全 ${result.chapter_count} 章 ／ 約 ${result.char_count.toLocaleString()} 文字${refStr}`;
    downloadMd.href = `/download/${jobId}/book_full.md`;
    downloadMd.download = "book_full.md";
    downloadDocx.href = `/download/${jobId}/book_full.docx`;
    downloadDocx.download = "book_full.docx";
    downloadNotebookLM.href = `/notebooklm-export/${jobId}`;
    downloadNotebookLM.download = "book_for_notebooklm.md";
    hide(progressSection);
    show(resultSection);
  }

  function showError(message) {
    errorMessage.textContent = message;
    hide(progressSection);
    show(errorSection);
  }

  // -------------------------------------------------------------------
  // submit
  // -------------------------------------------------------------------
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const projectId = currentProjectId || (crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Date.now().toString(36));
    const payload = {
      theme: $("theme").value.trim(),
      target_layer: $("target_layer").value,
      author: $("author").value.trim(),
      api_key: $("api_key").value.trim(),
      project_id: projectId,
      project_name: $("theme").value.trim().slice(0, 30),
      ref_urls: $("ref_urls").value.trim(),
      notebooklm_urls: $("notebooklm_urls").value.trim(),
    };
    if (!payload.theme || !payload.author || !payload.api_key) {
      alert("未入力の項目があります（テーマ・著者名・API キー）");
      return;
    }
    sessionStorage.setItem(API_KEY_STORE, payload.api_key);

    submitBtn.disabled = true;
    submitBtn.textContent = "送信中…";

    try {
      const { job_id, reference_count } = await startGeneration(payload);
      currentProjectId = projectId;
      upsertProject({
        id: projectId,
        name: payload.project_name || "未命名",
        theme: payload.theme,
        target_layer: payload.target_layer,
        author: payload.author,
        ref_urls: payload.ref_urls,
        notebooklm_urls: payload.notebooklm_urls,
        last_job_id: job_id,
        created_at: new Date().toISOString(),
      });
      hide(formSection);
      show(progressSection);
      progressReferences.textContent = reference_count
        ? `参照ソース ${reference_count} 件を取り込みました`
        : "";
      setProgress(2, "送信しました。生成を開始します…");

      pollTimer = setInterval(async () => {
        try {
          const state = await pollStatus(job_id);
          if (state.status === "running") {
            setProgress(state.progress || 0, state.message || "生成中…");
          } else if (state.status === "done") {
            clearInterval(pollTimer);
            pollTimer = null;
            setProgress(100, "完了しました。");
            const projects = loadProjects();
            const me = projects.find((p) => p.id === projectId);
            if (me) {
              me.result = state.result;
              saveProjects(projects);
              renderProjects();
            }
            setTimeout(() => showResult(job_id, state.result), 600);
          } else if (state.status === "error") {
            clearInterval(pollTimer);
            pollTimer = null;
            showError(state.message || "エラーが発生しました。");
          }
        } catch (err) {
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
  $("new-project-btn").addEventListener("click", newProject);

  // 起動時
  const savedKey = sessionStorage.getItem(API_KEY_STORE) || "";
  if (savedKey) $("api_key").value = savedKey;
  renderProjects();
})();
