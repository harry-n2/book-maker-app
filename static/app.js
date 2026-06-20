(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const formSection = $("form-section");
  const referencesReviewSection = $("references-review-section");
  const referencesList = $("references-list");
  const referencesWarningBanner = $("references-warning-banner");
  const referencesSummary = $("references-summary");
  const backToFormBtn = $("back-to-form-btn");
  const confirmReferencesBtn = $("confirm-references-btn");
  const titlePickSection = $("title-pick-section");
  const structureGeneratingSection = $("structure-generating-section");
  const structureReviewSection = $("structure-review-section");
  const progressSection = $("progress-section");
  const resultSection = $("result-section");
  const errorSection = $("error-section");
  const form = $("book-form");
  const submitBtn = $("submit-btn");
  const titleCards = $("title-cards");
  const titlePickSummary = $("title-pick-summary");
  const confirmTitleBtn = $("confirm-title-btn");
  const regenTitlesBtn = $("regen-titles-btn");
  const titlesRegenNote = $("titles-regen-note");
  const backBtn = $("back-btn");
  const structureGeneratingMessage = $("structure-generating-message");
  const structureTitleBanner = $("structure-title-banner");
  const structureTree = $("structure-tree");
  const approveStructureBtn = $("approve-structure-btn");
  const regenStructureBtn = $("regen-structure-btn");
  const openModifyBtn = $("open-modify-btn");
  const modifyPanel = $("modify-panel");
  const modifyInstruction = $("modify-instruction");
  const cancelModifyBtn = $("cancel-modify-btn");
  const submitModifyBtn = $("submit-modify-btn");
  const structureRegenNote = $("structure-regen-note");
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
  let currentStructure = null;
  let selectedIndex = -1;
  let pollTimer = null;
  let currentProjectId = null;
  let maxRegenPerStage = 3;
  let titlesRegenCount = 0;
  let structureRegenCount = 0;
  let structureModifyCount = 0;

  // -------------------------------------------------------------------
  // UI helpers
  // -------------------------------------------------------------------
  function show(el) { if (el) el.classList.remove("hidden"); }
  function hide(el) { if (el) el.classList.add("hidden"); }
  function hideAllSections() {
    hide(formSection);
    hide(referencesReviewSection);
    hide(titlePickSection);
    hide(structureGeneratingSection);
    hide(structureReviewSection);
    hide(progressSection);
    hide(resultSection);
    hide(errorSection);
  }
  function setProgress(pct, message) {
    progressFill.style.width = `${pct}%`;
    progressPct.textContent = `${pct}%`;
    if (message) progressMessage.textContent = message;
  }
  function clearPoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }
  function reset() {
    clearPoll();
    currentJobId = null;
    currentCandidates = [];
    currentStructure = null;
    selectedIndex = -1;
    titlesRegenCount = 0;
    structureRegenCount = 0;
    submitBtn.disabled = false;
    submitBtn.textContent = "参照素材を取り込んで次へ →";
    setProgress(0, "準備中…");
    hideAllSections();
    show(formSection);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
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
    $("profile_name").value = p.profile_name || "";
    $("profile_author_bio").value = p.profile_author_bio || "";
    $("profile_tone").value = p.profile_tone || "";
    $("profile_target_keywords").value = p.profile_target_keywords || "";
    $("profile_failure_bank").value = p.profile_failure_bank || "";
    $("profile_voice_types").value = p.profile_voice_types || "";
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
    $("profile_name").value = "";
    $("profile_author_bio").value = "";
    $("profile_tone").value = "";
    $("profile_target_keywords").value = "";
    $("profile_failure_bank").value = "";
    $("profile_voice_types").value = "";
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
  // 参照素材プレビュー 描画
  // -------------------------------------------------------------------
  function renderReferences(refs) {
    referencesList.innerHTML = "";
    if (!refs || refs.length === 0) {
      referencesList.innerHTML = '<p class="note">参照素材は登録されていません。素材なしで進めると著者ハリーの定型本になります。</p>';
      return;
    }
    for (const r of refs) {
      const hasWarn = !!r.warning;
      const item = document.createElement("div");
      item.className = "ref-item" + (hasWarn ? " has-warning" : " ok");
      const label = (r.label || "").slice(0, 80) + ((r.label || "").length > 80 ? "..." : "");
      const lenStr = (r.char_count || 0).toLocaleString();
      const preview = (r.preview || "").trim();
      item.innerHTML = `
        <div class="ref-item-head">
          <span class="ref-item-kind kind-${escapeHtml(r.kind || "")}">${escapeHtml(r.kind || "")}</span>
          <span class="ref-item-label" title="${escapeHtml(r.label || "")}">${escapeHtml(label)}</span>
          <span class="ref-item-len ${hasWarn ? "len-bad" : "len-ok"}">${lenStr} 字</span>
        </div>
        ${hasWarn ? `<div class="ref-item-warning">⚠ ${escapeHtml(r.warning)}</div>` : ""}
        ${preview ? `<div class="ref-item-preview">${escapeHtml(preview)}${preview.length >= 200 ? "..." : ""}</div>` : ""}
      `;
      referencesList.appendChild(item);
    }
  }
  function renderReferencesReview(data) {
    renderReferences(data.references || []);
    const cnt = data.reference_count || 0;
    const warn = !!data.has_warning;
    referencesSummary.textContent =
      cnt === 0
        ? "参照素材なし。素材を追加することを強く推奨します。"
        : warn
        ? `参照素材 ${cnt} 件を取り込みました。⚠ 警告のあるソースがあります。`
        : `参照素材 ${cnt} 件を取り込みました。すべて正常に取得できています。`;
    if (warn) {
      show(referencesWarningBanner);
    } else {
      hide(referencesWarningBanner);
    }
    hideAllSections();
    show(referencesReviewSection);
  }

  // -------------------------------------------------------------------
  // タイトル候補10選 描画
  // -------------------------------------------------------------------
  function renderTitleCandidates(candidates) {
    titleCards.innerHTML = "";
    selectedIndex = -1;
    confirmTitleBtn.disabled = true;
    confirmTitleBtn.textContent = "このタイトルで章立てを作る →";
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
  function updateTitlesRegenNote() {
    const remaining = Math.max(0, maxRegenPerStage - titlesRegenCount);
    titlesRegenNote.textContent =
      remaining > 0
        ? `タイトル再生成は残り ${remaining} 回まで使えます（使用済み: ${titlesRegenCount} / ${maxRegenPerStage}）。`
        : `タイトル再生成は上限（${maxRegenPerStage}回）に達しました。1つ選んで進んでください。`;
    regenTitlesBtn.disabled = remaining <= 0;
  }

  // -------------------------------------------------------------------
  // 章立て 描画
  // -------------------------------------------------------------------
  function renderStructure(structure) {
    if (!structure) {
      structureTree.innerHTML = '<p class="note">章立てがありません。</p>';
      return;
    }
    structureTitleBanner.innerHTML = `
      <p class="structure-banner-title">『${escapeHtml(structure.title || "")}』</p>
      <p class="structure-banner-subtitle">${escapeHtml(structure.subtitle || "")}</p>
      ${structure.note ? `<p class="structure-banner-note">📝 ${escapeHtml(structure.note)}</p>` : ""}
    `;

    const blocks = [];

    const intro = structure.intro || {};
    blocks.push(renderChapterBlock("はじめに", intro));

    (structure.chapters || []).forEach((ch, i) => {
      blocks.push(renderChapterBlock(`第${i + 1}章`, ch));
    });

    const outro = structure.outro || {};
    blocks.push(renderChapterBlock("おわりに", outro));

    structureTree.innerHTML = blocks.join("");
  }
  function renderChapterBlock(label, ch) {
    if (!ch || !ch.title) return "";
    const sections = (ch.sections || [])
      .map((s) => {
        const h3s = (s.subsections || [])
          .map((sub) => `<li class="structure-h3">↳ ${escapeHtml(sub.h3 || "")}</li>`)
          .join("");
        return `
          <li class="structure-h2">
            <span class="structure-h2-title">${escapeHtml(s.h2 || "")}</span>
            ${s.summary ? `<p class="structure-h2-summary">${escapeHtml(s.summary)}</p>` : ""}
            ${h3s ? `<ul class="structure-h3-list">${h3s}</ul>` : ""}
          </li>
        `;
      })
      .join("");
    return `
      <div class="structure-chapter">
        <div class="structure-chapter-head">
          <span class="structure-chapter-label">${escapeHtml(label)}</span>
          <span class="structure-chapter-title">${escapeHtml(ch.title || "")}</span>
        </div>
        <div class="structure-chapter-meta">
          ${ch.voice_type ? `<span class="structure-meta-badge">口調：${escapeHtml(ch.voice_type)}</span>` : ""}
          ${ch.failure_bank ? `<span class="structure-meta-badge">失敗談：${escapeHtml(ch.failure_bank)}</span>` : ""}
        </div>
        ${ch.key_message ? `<p class="structure-key-message">💡 ${escapeHtml(ch.key_message)}</p>` : ""}
        ${sections ? `<ul class="structure-h2-list">${sections}</ul>` : ""}
      </div>
    `;
  }
  function updateStructureRegenNote() {
    const regenRemain = Math.max(0, maxRegenPerStage - structureRegenCount);
    const modifyRemain = Math.max(0, maxRegenPerStage - structureModifyCount);
    structureRegenNote.textContent = `\u69cb\u6210\u518d\u751f\u6210\u306f\u6b8b\u308a ${regenRemain} \u56de / \u90e8\u5206\u4fee\u6b63\u306f\u6b8b\u308a ${modifyRemain} \u56de\uff08\u5404 ${maxRegenPerStage} \u56de\u307e\u3067\uff09`;
    regenStructureBtn.disabled = regenRemain <= 0;
    openModifyBtn.disabled = modifyRemain <= 0;
  }

  // -------------------------------------------------------------------
  // 通信
  // -------------------------------------------------------------------
  async function postJson(url, fd) {
    const res = await fetch(url, { method: "POST", body: fd || new FormData() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "送信に失敗しました" }));
      throw new Error(err.detail || "送信に失敗しました");
    }
    return res.json();
  }
  async function startTitleGeneration(payload) {
    const fd = new FormData();
    Object.entries(payload).forEach(([k, v]) => fd.append(k, v));
    Array.from($("files").files).forEach((f) => fd.append("files", f));
    Array.from($("images").files).forEach((f) => fd.append("images", f));
    return postJson("/generate-titles", fd);
  }
  async function regenerateTitles(jobId) {
    return postJson(`/regenerate-titles/${jobId}`);
  }
  async function confirmTitle(jobId, adoptedIndex) {
    const fd = new FormData();
    fd.append("adopted_index", String(adoptedIndex));
    return postJson(`/confirm-title/${jobId}`, fd);
  }
  async function regenerateStructure(jobId) {
    return postJson(`/regenerate-structure/${jobId}`);
  }
  async function modifyStructure(jobId, instruction) {
    const fd = new FormData();
    fd.append("user_instruction", instruction);
    return postJson(`/modify-structure/${jobId}`, fd);
  }
  async function approveStructure(jobId) {
    return postJson(`/approve-structure/${jobId}`);
  }
  async function pollStatus(jobId) {
    const res = await fetch(`/status/${jobId}`);
    if (!res.ok) throw new Error("状態取得に失敗しました");
    return res.json();
  }
  // サーバーレス対応: 1呼び出し=1工程を進めるワーカー。ポーリングのたびに次工程へ前進する。
  async function advance(jobId) {
    const res = await fetch(`/advance/${jobId}`, { method: "POST" });
    if (!res.ok) throw new Error("生成の進行に失敗しました");
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
    hideAllSections();
    show(resultSection);
  }
  function showError(message) {
    errorMessage.textContent = message;
    hideAllSections();
    show(errorSection);
  }

  // -------------------------------------------------------------------
  // 状態ポーリング（章立て生成・再生成・修正・本編生成のすべて）
  // -------------------------------------------------------------------
  function startPolling(jobId) {
    clearPoll();
    let busy = false; // 前工程が完了するまで次を呼ばない（重複実行防止）
    pollTimer = setInterval(async () => {
      if (busy) return;
      busy = true;
      try {
        const state = await advance(jobId);
        handleStateUpdate(jobId, state);
      } catch (err) {
        console.warn(err);
      } finally {
        busy = false;
      }
    }, 2000);
  }
  function handleStateUpdate(jobId, state) {
    if (typeof state.max_regen_per_stage === "number") maxRegenPerStage = state.max_regen_per_stage;
    if (typeof state.titles_regen_count === "number") titlesRegenCount = state.titles_regen_count;
    if (typeof state.structure_regen_count === "number") structureRegenCount = state.structure_regen_count;
    if (typeof state.structure_modify_count === "number") structureModifyCount = state.structure_modify_count;

    if (state.status === "generating_structure") {
      hideAllSections();
      show(structureGeneratingSection);
      structureGeneratingMessage.textContent = state.message || "章立てを構築中…";
    } else if (state.status === "regenerating_structure") {
      hideAllSections();
      show(structureGeneratingSection);
      structureGeneratingMessage.textContent = state.message || "章立てを更新中…";
    } else if (state.status === "structure_review") {
      // 章立てレビュー画面はユーザー入力待ちの停止状態。ここでポーリングを止めないと、
      clearPoll();
      currentStructure = state.structure || currentStructure;
      hideAllSections();
      show(structureReviewSection);
      renderStructure(currentStructure);
      updateStructureRegenNote();
      hide(modifyPanel);
      modifyInstruction.value = "";
      resetStructureButtons();
    } else if (state.status === "running") {
      hideAllSections();
      show(progressSection);
      setProgress(state.progress || 0, state.message || "生成中…");
    } else if (state.status === "done") {
      clearPoll();
      setProgress(100, "完了しました。");
      const projects = loadProjects();
      const me = projects.find((p) => p.id === currentProjectId);
      if (me) {
        me.result = state.result;
        saveProjects(projects);
        renderProjects();
      }
      setTimeout(() => showResult(jobId, state.result), 400);
    } else if (state.status === "error") {
      clearPoll();
      showError(state.message || "エラーが発生しました。");
    }
  }
  function resetStructureButtons() {
    approveStructureBtn.disabled = false;
    approveStructureBtn.textContent = "1. この章立てで本編を作成 →";
    regenStructureBtn.textContent = "2. さらにベストセラーが取れる構成で再出力";
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
      pasted_text: $("pasted_text").value.trim(),
      profile_name: $("profile_name").value.trim(),
      profile_author_bio: $("profile_author_bio").value.trim(),
      profile_tone: $("profile_tone").value.trim(),
      profile_target_keywords: $("profile_target_keywords").value.trim(),
      profile_failure_bank: $("profile_failure_bank").value.trim(),
      profile_voice_types: $("profile_voice_types").value.trim(),
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
    submitBtn.textContent = "参照素材を取り込み中…";

    try {
      const data = await startTitleGeneration(payload);
      currentJobId = data.job_id;
      currentCandidates = [];
      currentProjectId = projectId;
      titlesRegenCount = 0;
      maxRegenPerStage = data.max_regen_per_stage || 3;
      structureRegenCount = 0;
      upsertProject({
        id: projectId,
        name: payload.project_name || "未命名",
        theme: payload.theme,
        target_layer: payload.target_layer,
        author: payload.author,
        profile_name: payload.profile_name,
        profile_author_bio: payload.profile_author_bio,
        profile_tone: payload.profile_tone,
        profile_target_keywords: payload.profile_target_keywords,
        profile_failure_bank: payload.profile_failure_bank,
        profile_voice_types: payload.profile_voice_types,
        ref_urls: payload.ref_urls,
        notebooklm_urls: payload.notebooklm_urls,
        last_job_id: data.job_id,
        created_at: new Date().toISOString(),
      });
      renderReferencesReview(data);
    } catch (err) {
      showError(err.message || "送信に失敗しました。");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "参照素材を取り込んで次へ →";
    }
  });

  // -------------------------------------------------------------------
  // タイトル再生成（ベストセラー版）
  // -------------------------------------------------------------------
  regenTitlesBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    regenTitlesBtn.disabled = true;
    regenTitlesBtn.textContent = "ベストセラー版で再生成中…";
    try {
      const data = await regenerateTitles(currentJobId);
      currentCandidates = data.candidates;
      titlesRegenCount = data.titles_regen_count;
      renderTitleCandidates(data.candidates);
      titlePickSummary.textContent = `★ベストセラー版で再生成しました（${titlesRegenCount}/${maxRegenPerStage}回目）。お好きな1案をお選びください。`;
      updateTitlesRegenNote();
    } catch (err) {
      alert(err.message || "再生成に失敗しました。");
    } finally {
      if (titlesRegenCount < maxRegenPerStage) {
        regenTitlesBtn.disabled = false;
      }
      regenTitlesBtn.textContent = "★ さらにベストセラー獲得できるタイトル10選を再出力";
    }
  });

  // -------------------------------------------------------------------
  // タイトル確定 → 章立て生成（非同期）
  // -------------------------------------------------------------------
  confirmTitleBtn.addEventListener("click", async () => {
    if (selectedIndex < 0 || !currentJobId) return;
    confirmTitleBtn.disabled = true;
    confirmTitleBtn.textContent = "章立て生成を開始しています…";
    try {
      await confirmTitle(currentJobId, selectedIndex);
      hideAllSections();
      show(structureGeneratingSection);
      structureGeneratingMessage.textContent = "章立てを構築中…（30〜60秒）";
      startPolling(currentJobId);
    } catch (err) {
      showError(err.message || "送信に失敗しました。");
      confirmTitleBtn.disabled = false;
      confirmTitleBtn.textContent = "このタイトルで章立てを作る →";
    }
  });

  backBtn.addEventListener("click", () => {
    hideAllSections();
    show(formSection);
  });

  // -------------------------------------------------------------------
  // 参照素材プレビュー：戻る / 進む
  // -------------------------------------------------------------------
  backToFormBtn.addEventListener("click", () => {
    hideAllSections();
    show(formSection);
  });

  confirmReferencesBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    confirmReferencesBtn.disabled = true;
    confirmReferencesBtn.textContent = "タイトル10選を生成中…（30〜60秒）";
    try {
      const res = await fetch(`/confirm-references/${currentJobId}`, { method: "POST", body: new FormData() });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "送信に失敗しました" }));
        throw new Error(err.detail || "送信に失敗しました");
      }
      const data = await res.json();
      currentCandidates = data.candidates || [];
      titlesRegenCount = data.titles_regen_count || 0;
      maxRegenPerStage = data.max_regen_per_stage || 3;
      const projects = loadProjects();
      const me = projects.find((p) => p.id === currentProjectId);
      if (me) {
        me.candidates = data.candidates;
        saveProjects(projects);
      }
      renderTitleCandidates(data.candidates || []);
      titlePickSummary.textContent = data.reference_count
        ? `参照ソース ${data.reference_count} 件を取り込んだ上で候補が ${(data.candidates || []).length} 件揃いました。`
        : `候補が ${(data.candidates || []).length} 件揃いました。お好きな1案をお選びください。`;
      updateTitlesRegenNote();
      hideAllSections();
      show(titlePickSection);
    } catch (err) {
      showError(err.message || "送信に失敗しました。");
    } finally {
      confirmReferencesBtn.disabled = false;
      confirmReferencesBtn.textContent = "この素材でタイトル10選を作成 →";
    }
  });

  // -------------------------------------------------------------------
  // 章立て：再生成（ベストセラー版）
  // -------------------------------------------------------------------
  openModifyBtn.addEventListener("click", () => {
    show(modifyPanel);
    modifyInstruction.focus();
  });

  cancelModifyBtn.addEventListener("click", () => {
    hide(modifyPanel);
    modifyInstruction.value = "";
  });

  submitModifyBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    const instruction = modifyInstruction.value.trim();
    if (!instruction) {
      alert("\u4fee\u6b63\u6307\u793a\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002");
      return;
    }
    submitModifyBtn.disabled = true;
    submitModifyBtn.textContent = "\u4fee\u6b63\u4e2d...";
    try {
      await modifyStructure(currentJobId, instruction);
      hide(modifyPanel);
      modifyInstruction.value = "";
      startPolling(currentJobId);
    } catch (err) {
      alert(err.message || "\u90e8\u5206\u4fee\u6b63\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002");
      submitModifyBtn.disabled = false;
      submitModifyBtn.textContent = "\u3053\u306e\u6307\u793a\u3067\u4fee\u6b63";
    }
  });

  regenStructureBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    if (!confirm("章立てをベストセラー版で再生成します。現在の章立ては上書きされます。よろしいですか？")) return;
    regenStructureBtn.disabled = true;
    regenStructureBtn.textContent = "再生成中…";
    try {
      await regenerateStructure(currentJobId);
      startPolling(currentJobId);
    } catch (err) {
      alert(err.message || "再生成に失敗しました。");
      regenStructureBtn.disabled = false;
      regenStructureBtn.textContent = "2. さらにベストセラーが取れる構成で再出力";
    }
  });

  approveStructureBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    if (!confirm("この章立てで本編を作成します（5〜10分かかります。Gemini無料枠を数百req消費）。よろしいですか？")) return;
    approveStructureBtn.disabled = true;
    approveStructureBtn.textContent = "本編生成を開始しています…";
    try {
      await approveStructure(currentJobId);
      hideAllSections();
      show(progressSection);
      setProgress(12, "本編の執筆を開始します…");
      startPolling(currentJobId);
    } catch (err) {
      alert(err.message || "送信に失敗しました。");
      approveStructureBtn.disabled = false;
      approveStructureBtn.textContent = "1. この章立てで本編を作成 →";
    }
  });

  // -------------------------------------------------------------------
  // 共通ボタン
  // -------------------------------------------------------------------
  $("reset-btn").addEventListener("click", reset);
  $("retry-btn").addEventListener("click", reset);
  $("new-project-btn").addEventListener("click", newProject);

  const savedKey = sessionStorage.getItem(API_KEY_STORE) || "";
  if (savedKey) $("api_key").value = savedKey;
  renderProjects();
})();
