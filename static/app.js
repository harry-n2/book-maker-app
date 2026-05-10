(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const formSection = $("form-section");
  const titlePickSection = $("title-pick-section");
  const progressSection = $("progress-section");
  const resultSection = $("result-section");
  const errorSection = $("error-section");
  const form = $("book-form");
  const submitBtn = $("submit-btn");
  const titleCards = $("title-cards");
  const titlePickSummary = $("title-pick-summary");
  const confirmTitleBtn = $("confirm-title-btn");
  const backBtn = $("back-btn");
  const progressFill = $("progress-fill");
  const progressPct = $("progress-pct");
  const progressMessage = $("progress-message");
  const progressReferences = $("progress-references");
  const resultTitle = $("result-title");
  const resultStats = $("result-stats");
  const downloadMd = $("download-md");
  const downloadDocx = $("download-docx");
  const downloadTitles = $("download-titles");
  const downloadDescription = $("download-description");
  const downloadNotebookLM = $("download-notebooklm");
  const errorMessage = $("error-message");
  const projectList = $("project-list");

  const PROJECT_STORE_KEY = "book_maker_projects_v3";
  const API_KEY_STORE = "gemini_api_key";
  const MAX_FILES_PER_KIND = 10;

  let currentJobId = null;
  let currentCandidates = [];
  let selectedIndex = -1;
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
    currentJobId = null;
    currentCandidates = [];
    selectedIndex = -1;
    submitBtn.disabled = false;
    submitBtn.textContent = "タイトル候補10選を作る";
    setProgress(0, "準備中…");
    show(formSection);
    hide(titlePickSection);
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
    } catch (e) { return []; }
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
      currentJobId = p.last_job_id;
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
    $("file-counter").textContent = "0 / 10 ファイル選択中";
    $("image-counter").textContent = "0 / 10 画像選択中";
    $("file-counter").classList.remove("over-limit");
    $("image-counter").classList.remove("over-limit");
    renderProjects();
    reset();
  }

  // -------------------------------------------------------------------
  // ファイル選択UI
  // -------------------------------------------------------------------
  function bindFileList(inputId, listId, counterId, kindLabel) {
    const input = $(inputId);
    const counter = $(counterId);
    input.addEventListener("change", (e) => {
      const files = Array.from(e.target.files);
      const ul = $(listId);
      ul.innerHTML = "";
      files.forEach((f) => {
        const li = document.createElement("li");
        li.textContent = `📎 ${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
        ul.appendChild(li);
      });
      counter.textContent = `${files.length} / ${MAX_FILES_PER_KIND} ${kindLabel}選択中`;
      if (files.length > MAX_FILES_PER_KIND) {
        counter.classList.add("over-limit");
        counter.textContent += `  ⚠ 上限を超えています（${kindLabel}は最大${MAX_FILES_PER_KIND}個まで）`;
      } else {
        counter.classList.remove("over-limit");
      }
    });
  }
  bindFileList("files", "file-list", "file-counter", "ファイル");
  bindFileList("images", "image-list", "image-counter", "画像");

  // -------------------------------------------------------------------
  // タイトル候補10選 描画
  // -------------------------------------------------------------------
  function renderTitleCandidates(candidates) {
    titleCards.innerHTML = "";
    selectedIndex = -1;
    confirmTitleBtn.disabled = true;
    candidates.forEach((c, i) => {
      const li = document.createElement("li");
      li.className = "title-card";
      li.dataset.index = i;
      li.innerHTML = `
        <input type="radio" name="title_pick" value="${i}" id="title_radio_${i}">
        <div class="title-card-body">
          <span class="title-card-rank">${c.rank || i + 1}位</span>
          <p class="title-card-title">${escapeHtml(c.title || "")}</p>
          <p class="title-card-subtitle">${escapeHtml(c.subtitle || "")}</p>
          <p class="title-card-meta">フック型：${escapeHtml(c.hook_type || "")}</p>
          <p class="title-card-meta">採用理由：${escapeHtml(c.reason || "")}</p>
        </div>
      `;
      li.addEventListener("click", () => selectTitle(i));
      titleCards.appendChild(li);
    });
  }
  function selectTitle(i) {
    selectedIndex = i;
    Array.from(titleCards.children).forEach((card, idx) => {
      const radio = card.querySelector('input[type="radio"]');
      if (idx === i) {
        card.classList.add("selected");
        if (radio) radio.checked = true;
      } else {
        card.classList.remove("selected");
        if (radio) radio.checked = false;
      }
    });
    confirmTitleBtn.disabled = false;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  // -------------------------------------------------------------------
  // 通信
  // -------------------------------------------------------------------
  async function startTitleGeneration(payload) {
    const fd = new FormData();
    Object.entries(payload).forEach(([k, v]) => fd.append(k, v));
    Array.from($("files").files).forEach((f) => fd.append("files", f));
    Array.from($("images").files).forEach((f) => fd.append("images", f));
    const res = await fetch("/generate-titles", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "送信に失敗しました" }));
      throw new Error(err.detail || "送信に失敗しました");
    }
    return res.json();
  }
  async function confirmTitle(jobId, adoptedIndex) {
    const fd = new FormData();
    fd.append("adopted_index", String(adoptedIndex));
    const res = await fetch(`/confirm-title/${jobId}`, { method: "POST", body: fd });
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
    resultStats.textContent = `本編 ${result.chapter_count} 章 ／ 約 ${result.char_count.toLocaleString()} 文字${refStr}`;
    downloadMd.href = `/download/${jobId}/book_full.md`;
    downloadMd.download = "book_full.md";
    downloadDocx.href = `/download/${jobId}/book_full.docx`;
    downloadDocx.download = "book_full.docx";
    downloadTitles.href = `/download/${jobId}/title_candidates.md`;
    downloadTitles.download = "title_candidates.md";
    downloadDescription.href = `/download/${jobId}/book_description.md`;
    downloadDescription.download = "book_description.md";
    downloadNotebookLM.href = `/notebooklm-export/${jobId}`;
    downloadNotebookLM.download = "book_for_notebooklm.md";
    hide(progressSection);
    show(resultSection);
  }
  function showError(message) {
    errorMessage.textContent = message;
    hide(progressSection);
    hide(titlePickSection);
    show(errorSection);
  }

  // -------------------------------------------------------------------
  // submit（Step 1：タイトル候補10選）
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
    if ($("files").files.length > MAX_FILES_PER_KIND) {
      alert(`添付ファイルは最大 ${MAX_FILES_PER_KIND} 個まで`);
      return;
    }
    if ($("images").files.length > MAX_FILES_PER_KIND) {
      alert(`添付画像は最大 ${MAX_FILES_PER_KIND} 個まで`);
      return;
    }
    sessionStorage.setItem(API_KEY_STORE, payload.api_key);

    submitBtn.disabled = true;
    submitBtn.textContent = "タイトル候補を生成中…";

    try {
      const { job_id, candidates, reference_count } = await startTitleGeneration(payload);
      currentJobId = job_id;
      currentCandidates = candidates;
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
        candidates: candidates,
        created_at: new Date().toISOString(),
      });
      renderTitleCandidates(candidates);
      titlePickSummary.textContent = reference_count
        ? `参照ソース ${reference_count} 件を取り込みました。お好きな1案をお選びください。`
        : `候補が ${candidates.length} 件揃いました。お好きな1案をお選びください。`;
      hide(formSection);
      show(titlePickSection);
    } catch (err) {
      showError(err.message || "送信に失敗しました。");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "タイトル候補10選を作る";
    }
  });

  // -------------------------------------------------------------------
  // タイトル確定（Step 2：本編生成開始）
  // -------------------------------------------------------------------
  confirmTitleBtn.addEventListener("click", async () => {
    if (selectedIndex < 0 || !currentJobId) return;
    confirmTitleBtn.disabled = true;
    confirmTitleBtn.textContent = "本編生成を開始しています…";
    try {
      await confirmTitle(currentJobId, selectedIndex);
      hide(titlePickSection);
      show(progressSection);
      setProgress(5, "構造の生成を開始します…");
      const jobId = currentJobId;
      pollTimer = setInterval(async () => {
        try {
          const state = await pollStatus(jobId);
          if (state.status === "running") {
            setProgress(state.progress || 0, state.message || "生成中…");
          } else if (state.status === "done") {
            clearInterval(pollTimer);
            pollTimer = null;
            setProgress(100, "完了しました。");
            const projects = loadProjects();
            const me = projects.find((p) => p.id === currentProjectId);
            if (me) {
              me.result = state.result;
              saveProjects(projects);
              renderProjects();
            }
            setTimeout(() => showResult(jobId, state.result), 600);
          } else if (state.status === "error") {
            clearInterval(pollTimer);
            pollTimer = null;
            showError(state.message || "エラーが発生しました。");
          }
        } catch (err) { console.warn(err); }
      }, 2000);
    } catch (err) {
      showError(err.message || "送信に失敗しました。");
      confirmTitleBtn.disabled = false;
      confirmTitleBtn.textContent = "このタイトルで本を作る →";
    }
  });

  backBtn.addEventListener("click", () => {
    hide(titlePickSection);
    show(formSection);
  });

  $("reset-btn").addEventListener("click", reset);
  $("retry-btn").addEventListener("click", reset);
  $("new-project-btn").addEventListener("click", newProject);

  const savedKey = sessionStorage.getItem(API_KEY_STORE) || "";
  if (savedKey) $("api_key").value = savedKey;
  renderProjects();
})();
