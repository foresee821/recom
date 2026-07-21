const els = {
  screen: document.querySelector("#mobile-screen"),
  scroller: document.querySelector("#content-scroller"),
  recommendView: document.querySelector("#recommend-view"),
  searchView: document.querySelector("#search-view"),
  recommendGrid: document.querySelector("#recommend-grid"),
  searchGrid: document.querySelector("#search-grid"),
  nearGrid: document.querySelector("#near-grid"),
  nearSection: document.querySelector("#near-section"),
  exactHeading: document.querySelector("#exact-heading"),
  exactCount: document.querySelector("#exact-count"),
  searchLabel: document.querySelector("#search-label"),
  searchTip: document.querySelector("#search-tip"),
  subtitle: document.querySelector("#recommend-subtitle"),
  intentStrip: document.querySelector("#intent-strip"),
  intentChips: document.querySelector("#intent-chips"),
  onboarding: document.querySelector("#onboarding"),
  voiceSheet: document.querySelector("#voice-sheet"),
  voiceTitle: document.querySelector("#voice-title"),
  voiceHint: document.querySelector("#voice-hint"),
  voiceKeywordOrbit: document.querySelector("#voice-keyword-orbit"),
  clearAllIntents: document.querySelector("#clear-all-intents"),
  voiceClose: document.querySelector("#voice-close"),
  holdButton: document.querySelector("#hold-button"),
  wave: document.querySelector("#wave"),
  transcript: document.querySelector("#transcript"),
  fallbackForm: document.querySelector("#fallback-form"),
  fallbackInput: document.querySelector("#fallback-input"),
  examples: document.querySelector("#examples"),
  toast: document.querySelector("#toast"),
};

const state = {
  bootstrap: null,
  products: new Map(),
  scene: "recommend",
  sessionIntent: [],
  recommendationIds: [],
  searchIds: [],
  nearIds: [],
  previous: null,
  recognition: null,
  listening: false,
  recognitionPending: false,
  recognitionStarted: false,
  recognitionFailed: false,
  submitOnEnd: false,
  stopAfterStart: false,
  cancelOnStart: false,
  ignoreNextAbort: false,
  transcript: "",
  homeCatalogProducts: [],
  homeCatalogRound: 0,
  homeCatalogMaxRounds: 0,
  homeCatalogLoading: false,
  homeCatalogComplete: false,
  homeRecommendationIds: [],
  homeCatalogPreloadRound: -1,
  homeCatalogPreloadImages: [],
  intentCatalogCache: new Map(),
  activeIntentProductIds: [],
};

const productSpritePanels = {
  "fresh-01": "sprite-p1",
  "home-02": "sprite-p2",
  "fresh-02": "sprite-p3",
  "fresh-03": "sprite-p4",
  "home-01": "sprite-p5",
  "home-06": "sprite-p5",
  "home-08": "sprite-p5",
  "run-01": "sprite-p6",
  "run-02": "sprite-p6",
  "run-03": "sprite-p6",
  "run-04": "sprite-p6",
  "shoe-01": "sprite-p6",
  "shoe-02": "sprite-p6",
  "shoe-03": "sprite-p6",
  "shoe-04": "sprite-p6",
  "shoe-05": "sprite-p6",
  "shoe-06": "sprite-p6",
  "shoe-07": "sprite-p6",
  "shoe-08": "sprite-p6",
  "fresh-04": "sprite-p6",
  "beauty-01": "catalog-p1",
  "beauty-02": "catalog-p1",
  "earbuds-01": "catalog-p2",
  "earbuds-02": "catalog-p2",
  "phone-01": "catalog-p3",
  "phone-02": "catalog-p3",
  "coffee-01": "catalog-p4",
  "coffee-02": "catalog-p4",
  "snack-01": "catalog-p5",
  "snack-02": "catalog-p5",
  "pet-01": "catalog-p6",
  "pet-02": "catalog-p6",
  "baby-01": "catalog-p7",
  "baby-02": "catalog-p7",
  "outdoor-01": "catalog-p8",
  "outdoor-02": "catalog-p8",
  "bag-01": "catalog-p9",
  "bag-02": "catalog-p9",
  "office-01": "catalog-p10",
  "office-02": "catalog-p10",
  "car-01": "catalog-p11",
  "car-02": "catalog-p11",
  "skincare-01": "catalog-p12",
  "skincare-02": "catalog-p12",
  "dress-01": "catalog-p13",
  "dress-02": "catalog-p13",
  "fruit-01": "catalog-p14",
  "fruit-02": "catalog-p14",
  "book-01": "catalog-p15",
  "book-02": "catalog-p15",
  "perfume-01": "catalog-p16",
  "perfume-02": "catalog-p16",
};

const caseSpriteSources = {
  rental: "assets/case-rental-products-v1.png",
  concert: "assets/case-concert-products-v1.png",
  happy: "assets/case-happiness-products-v1.png",
  sunscreen: "assets/case-sunscreen-products-v1.png",
  dressbase: "assets/case-diverse-dresses-v1.png",
  dresskorean: "assets/case-korean-dark-dresses-v1.png",
  dresscase: "assets/case-korean-dresses-v1.png",
  fitcase: "assets/case-fitness-products-v1.png",
  wow: "assets/case-eye-catching-products-v1.png",
};

const hiddenHomepageProductIds = new Set([
  "item-158364675",
]);

function caseSpriteFor(productId) {
  const match = /^(rental|concert|happy|sunscreen|dressbase|dresskorean|dresscase|fitcase|wow)-(\d{2})$/.exec(productId);
  if (!match) return null;
  const index = Number(match[2]) - 1;
  const column = index % 4;
  const row = Math.floor(index / 4);
  return {
    image: caseSpriteSources[match[1]],
    position: `${column * 33.333}% ${row * 50}%`,
  };
}

const commonSpriteGroups = [
  "laundry", "tissue", "toothbrush", "shampoo", "dryer",
  "robotvac", "ricecooker", "airfryer", "bedding", "pillow",
  "umbrella", "tablet", "laptop", "smartwatch", "speaker",
  "camera", "jeans", "shirt", "jacket", "slippers",
  "underwear", "mask", "formula", "toy", "fishing",
];

function commonSpriteFor(productId) {
  const match = /^common-([a-z]+)-\d{2}$/.exec(productId);
  if (!match) return null;
  const index = commonSpriteGroups.indexOf(match[1]);
  if (index < 0) return null;
  const column = index % 5;
  const row = Math.floor(index / 5);
  return {
    image: "assets/common-products-v1.png",
    position: `${column * 25}% ${row * 25}%`,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "请求失败");
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function productReasons(item) {
  const matches = state.sessionIntent.filter((condition) => {
    if (condition.operator === "neq") return false;
    if (condition.name === "price") return item.price <= Number(condition.value);
    if (condition.name === "category") {
      return item.category === condition.value || item.attributes.includes(condition.value) ||
        (condition.value === "家居" && item.category === "收纳");
    }
    if (condition.name === "xcat1") return item.xcat1 === condition.value;
    if (condition.name === "xcat2") return item.xcat2 === condition.value;
    if (condition.name === "style") return item.styles?.includes(condition.value);
    if (condition.name === "audience") return item.audiences?.includes(condition.value);
    if (condition.name === "brand") return item.brand === condition.value;
    return item.attributes.includes(condition.value);
  });
  return matches.slice(0, 2).map((condition) => condition.label);
}

function productCard(item, index, isNear = false) {
  const reasons = productReasons(item);
  const tags = reasons.length ? reasons : item.attributes.slice(0, 1);
  const spritePanel = productSpritePanels[item.id];
  const caseSprite = caseSpriteFor(item.id);
  const commonSprite = commonSpriteFor(item.id);
  const image = caseSprite
    ? `<div class="product-image product-photo case-product" style="--case-image:url('${caseSprite.image}');--case-position:${caseSprite.position}" role="img" aria-label="${escapeHtml(item.title)}"></div>`
    : commonSprite
    ? `<div class="product-image product-photo common-product" style="--common-image:url('${commonSprite.image}');--common-position:${commonSprite.position}" role="img" aria-label="${escapeHtml(item.title)}"></div>`
    : spritePanel
    ? `<div class="product-image product-photo ${spritePanel}" role="img" aria-label="${escapeHtml(item.title)}"></div>`
    : `<img class="product-image" src="${item.image.replace(/^\/assets\//, "assets/")}" alt="${escapeHtml(item.title)}" />`;
  return `
    <article class="product-card is-new card-shape-${index % 4}" style="--delay:${Math.min(index * 55, 330)}ms">
      ${image}
      <div class="product-body">
        <p class="product-title">${isNear ? '<span style="color:#999">近似 · </span>' : ""}${escapeHtml(item.title)}</p>
        <div class="product-reasons">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
        <span class="product-price">¥<strong>${item.price}</strong></span>
        <span class="product-sales">${escapeHtml(item.sales)}</span>
      </div>
    </article>`;
}

function renderGrid(container, ids, isNear = false) {
  const limit = isNear ? 6 : container === els.recommendGrid ? ids.length : 20;
  const uniqueIds = [...new Set(ids)].filter((id) => state.products.has(id)).slice(0, limit);
  container.innerHTML = '<div class="product-column"></div><div class="product-column"></div>';
  uniqueIds.forEach((id, index) => {
    appendProductToShortestColumn(container, state.products.get(id), index, isNear);
  });
}

function appendProductToShortestColumn(container, item, index, isNear = false) {
  const columns = [...container.querySelectorAll(".product-column")];
  const target = columns.reduce((shortest, column) =>
    column.offsetHeight < shortest.offsetHeight ? column : shortest,
  );
  target.insertAdjacentHTML("beforeend", productCard(item, index, isNear));
}

function showHomepageLoading() {
  const placeholder = () => `
    <div class="product-card product-placeholder" aria-hidden="true">
      <div class="placeholder-image"></div>
      <div class="placeholder-line wide"></div>
      <div class="placeholder-line"></div>
      <div class="placeholder-price"></div>
    </div>`;
  els.recommendGrid.innerHTML = `
    <div class="product-column">${placeholder()}${placeholder()}</div>
    <div class="product-column">${placeholder()}${placeholder()}</div>`;
}

function homepageProductsForRound(products, round) {
  const bySecondaryCategory = new Map();
  for (const item of products) {
    const key = item.xcat2 || item.category;
    if (!key) continue;
    if (!bySecondaryCategory.has(key)) bySecondaryCategory.set(key, []);
    bySecondaryCategory.get(key).push(item);
  }
  const selected = [];
  for (const items of bySecondaryCategory.values()) {
    items.sort((left, right) => (right.ordercost || 0) - (left.ordercost || 0));
    selected.push(items[round % items.length]);
  }

  const byPrimaryCategory = new Map();
  for (const item of selected) {
    if (hiddenHomepageProductIds.has(item.id)) continue;
    const key = item.xcat1 || "其他";
    if (!byPrimaryCategory.has(key)) byPrimaryCategory.set(key, []);
    byPrimaryCategory.get(key).push(item);
  }
  const groups = [...byPrimaryCategory.values()]
    .map((items) => items.sort((left, right) => (right.ordercost || 0) - (left.ordercost || 0)))
    .sort((left, right) => (right[0]?.ordercost || 0) - (left[0]?.ordercost || 0));
  const interleaved = [];
  for (let index = 0; groups.some((items) => index < items.length); index += 1) {
    for (const items of groups) if (items[index]) interleaved.push(items[index]);
  }
  return interleaved;
}

function homeCatalogMatchesCondition(item, condition) {
  if (condition.name === "price") return item.price <= Number(condition.value);
  const value = String(condition.value || "");
  if (condition.name === "xcat1") return item.xcat1 === value || item.xcat1.includes(value);
  if (condition.name === "xcat2") return item.xcat2 === value;
  return item.xcat2 === value || item.xcat1 === value ||
    item.attributes.includes(value) || item.title.includes(value);
}

function rankHomeCatalogForIntent(conditions, limit = 60) {
  const catalogConditions = conditions.filter((condition) =>
    ["category", "xcat1", "xcat2", "price"].includes(condition.name),
  );
  if (!catalogConditions.length || !state.homeCatalogProducts.length) return [];
  const matches = state.homeCatalogProducts.filter((item) => !hiddenHomepageProductIds.has(item.id) && catalogConditions.every((condition) => {
    const matched = homeCatalogMatchesCondition(item, condition);
    return condition.operator === "neq" ? !matched : matched;
  }));
  matches.sort((left, right) => (right.ordercost || 0) - (left.ordercost || 0));
  for (const item of matches.slice(0, limit)) state.products.set(item.id, item);
  return matches.slice(0, limit).map((item) => item.id);
}

function homeCatalogCategoryFromTranscript(transcript) {
  const normalized = String(transcript || "").replace(/[\s，。！？、,.!?“”"'：:；;]/g, "");
  const categories = [...new Set(state.homeCatalogProducts.map((item) => item.xcat2).filter(Boolean))]
    .sort((left, right) => right.length - left.length);
  return categories.find((category) => normalized.includes(
    category.replace(/[\s，。！？、,.!?“”"'：:；;]/g, ""),
  )) || null;
}

function applyHomeCatalogIntentFallback(result, transcript) {
  if (result.intent.type !== "unknown") return true;
  const category = homeCatalogCategoryFromTranscript(transcript);
  if (!category) return false;
  const condition = {
    name: "xcat2", operator: "eq", value: category, strength: "soft", label: category,
  };
  result.intent = { type: "pull", mode: "product", modeLabel: "商品意图", slots: [condition] };
  result.sessionIntent = [
    ...state.sessionIntent.filter((item) => !["category", "xcat2"].includes(item.name)),
    condition,
  ];
  result.feedback = `已为你找到${category}商品`;
  return true;
}

async function intentCatalogProductIds(transcript, conditions) {
  const normalized = String(transcript || "").replace(/\s/g, "");
  const isCamping = /(露营|野营|野炊)/.test(normalized) ||
    conditions.some((condition) => condition.sourceKey === "camping");
  if (!isCamping) return [];
  if (!state.intentCatalogCache.has("camping")) {
    const response = await fetch("data/intent-products/camping.json", { cache: "no-store" });
    if (!response.ok) throw new Error("露营商品加载失败");
    const payload = await response.json();
    state.intentCatalogCache.set("camping", payload.products || []);
  }
  const products = state.intentCatalogCache.get("camping");
  for (const item of products) state.products.set(item.id, item);
  return products.map((item) => item.id);
}

function applyIntentCatalogFallback(result, intentCatalogIds) {
  if (result.intent.type !== "unknown" || !intentCatalogIds.length) return;
  const condition = {
    name: "category", operator: "eq", value: "露营", strength: "soft",
    label: "露营好物", sourceMode: "scenario", sourceKey: "camping",
  };
  result.intent = { type: "pull", mode: "scenario", modeLabel: "场景意图", slots: [condition] };
  result.sessionIntent = [
    ...state.sessionIntent.filter((item) => item.sourceKey !== "camping"),
    condition,
  ];
  result.feedback = "已为你准备露营好物";
}

function preloadNextHomepageRound() {
  const round = state.homeCatalogRound;
  if (state.homeCatalogComplete || round === state.homeCatalogPreloadRound) return;
  state.homeCatalogPreloadRound = round;
  state.homeCatalogPreloadImages = homepageProductsForRound(state.homeCatalogProducts, round)
    .map((item) => {
      const image = new Image();
      image.decoding = "async";
      image.src = item.image;
      return image;
    });
}

function appendNextHomepageRound() {
  if (state.homeCatalogLoading || state.homeCatalogComplete || !state.homeCatalogProducts.length) return;
  if (state.scene !== "recommend" || state.sessionIntent.length > 0) return;
  state.homeCatalogLoading = true;
  const selected = homepageProductsForRound(state.homeCatalogProducts, state.homeCatalogRound);
  if (!selected.length) {
    state.homeCatalogComplete = true;
    state.homeCatalogLoading = false;
    return;
  }
  const startIndex = state.homeRecommendationIds.length;
  for (const item of selected) state.products.set(item.id, item);
  state.homeRecommendationIds.push(...selected.map((item) => item.id));
  state.recommendationIds = [...state.homeRecommendationIds];
  state.homeCatalogRound += 1;
  state.homeCatalogComplete = state.homeCatalogRound >= state.homeCatalogMaxRounds;
  if (startIndex === 0) {
    renderGrid(els.recommendGrid, state.recommendationIds);
  } else {
    selected.forEach((item, index) => {
      const productIndex = startIndex + index;
      appendProductToShortestColumn(els.recommendGrid, item, productIndex);
    });
  }
  state.homeCatalogLoading = false;
}

function fillHomepageScrollBuffer() {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const remaining = els.scroller.scrollHeight - els.scroller.scrollTop - els.scroller.clientHeight;
    if (remaining >= 9000 || state.homeCatalogComplete) break;
    appendNextHomepageRound();
  }
}

async function loadHomepageCatalog() {
  const response = await fetch("data/home-products.json", { cache: "no-store" });
  if (!response.ok) throw new Error("首页商品数据加载失败");
  const payload = await response.json();
  state.homeCatalogProducts = Array.isArray(payload.products) ? payload.products : [];
  const categoryCounts = new Map();
  for (const item of state.homeCatalogProducts) {
    const key = item.xcat2 || item.category;
    categoryCounts.set(key, (categoryCounts.get(key) || 0) + 1);
  }
  state.homeCatalogMaxRounds = Math.max(0, ...categoryCounts.values());
  state.homeCatalogRound = 0;
  state.homeCatalogPreloadRound = -1;
  state.homeCatalogPreloadImages = [];
  state.homeCatalogComplete = false;
  state.homeRecommendationIds = [];
  appendNextHomepageRound();
  const schedulePreload = window.requestIdleCallback || ((callback) => setTimeout(callback, 300));
  schedulePreload(preloadNextHomepageRound);
}

function usableResultIds(...groups) {
  for (const ids of groups) {
    const usable = [...new Set(ids || [])].filter((id) => state.products.has(id));
    if (usable.length > 0) return usable;
  }
  return [];
}

function renderProducts() {
  renderGrid(els.recommendGrid, state.recommendationIds);
  renderGrid(els.searchGrid, state.searchIds);
  renderGrid(els.nearGrid, state.nearIds, true);
  const refinedSearch = state.scene === "search" && state.sessionIntent.length > 0;
  els.nearSection.hidden = !refinedSearch || state.nearIds.length === 0;
  els.exactHeading.hidden = !refinedSearch;
  els.exactCount.textContent = `${state.searchIds.length} 件严格匹配`;
  els.searchTip.hidden = refinedSearch;
}

function renderIntents() {
  els.intentStrip.hidden = true;
  els.intentChips.replaceChildren();
  els.screen.classList.remove("has-intents");
}

function scrollProductsToTop() {
  requestAnimationFrame(() => {
    if (typeof els.scroller.scrollTo === "function") {
      els.scroller.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    els.scroller.scrollTop = 0;
  });
}

function renderVoiceKeywords() {
  const keywords = state.sessionIntent
    .map((condition, index) => ({ condition, index }))
    .filter(
      (item, position, all) =>
        all.findIndex((candidate) => candidate.condition.label === item.condition.label) === position,
    )
    .slice(0, 6);

  els.voiceKeywordOrbit.innerHTML = keywords
    .map(
      ({ condition, index }, position) => `
        <span class="voice-keyword-bubble bubble-pos-${position}">
          <span>${escapeHtml(condition.label)}</span>
          <button type="button" data-remove-keyword="${index}" aria-label="删除关键词 ${escapeHtml(condition.label)}">×</button>
        </span>
      `,
    )
    .join("");
  els.clearAllIntents.hidden = state.sessionIntent.length === 0;

  els.voiceKeywordOrbit.querySelectorAll("[data-remove-keyword]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const index = Number(button.dataset.removeKeyword);
      const removed = state.sessionIntent[index];
      if (!removed) return;

      const beforeDelete = snapshot();
      state.previous = beforeDelete;
      state.sessionIntent.splice(index, 1);
      try {
        await rerankCurrentConditions();
      } catch (error) {
        Object.assign(state, {
          sessionIntent: beforeDelete.sessionIntent,
          recommendationIds: beforeDelete.recommendationIds,
          searchIds: beforeDelete.searchIds,
          nearIds: beforeDelete.nearIds,
        });
        state.previous = null;
        renderProducts();
        renderVoiceKeywords();
        showToast(`关键词删除失败：${error.message}`);
        return;
      }
      renderVoiceKeywords();
      scrollProductsToTop();
      els.voiceTitle.textContent = state.sessionIntent.length
        ? "关键词已更新，推荐已刷新"
        : "已清空关键词，恢复默认推荐";
      els.voiceHint.textContent = "可以说具体商品、生活场景，或探索灵感";
      const remainingLabels = state.sessionIntent.map((condition) => condition.label);
      els.transcript.textContent = remainingLabels.length
        ? `当前关键词：${remainingLabels.join(" · ")}`
        : "当前没有关键词";
    });
  });
}

async function clearAllIntents() {
  const result = await api("/api/intent/reset", { method: "POST", body: "{}" });
  state.sessionIntent = [];
  state.recommendationIds = state.homeRecommendationIds.length
    ? [...state.homeRecommendationIds]
    : result.resultIds;
  state.searchIds = result.searchResultIds;
  state.nearIds = [];
  state.previous = null;
  state.activeIntentProductIds = [];
  renderIntents();
  renderProducts();
  renderVoiceKeywords();
  scrollProductsToTop();
  els.voiceTitle.textContent = "已清除全部意图";
  els.voiceHint.textContent = "可以说具体商品、生活场景，或探索灵感";
  els.transcript.textContent = "推荐已恢复，可以重新说出你的想法";
  els.fallbackInput.value = "";
}

function snapshot() {
  return {
    sessionIntent: structuredClone(state.sessionIntent),
    recommendationIds: [...state.recommendationIds],
    searchIds: [...state.searchIds],
    nearIds: [...state.nearIds],
    scrollTop: els.scroller.scrollTop,
  };
}

function switchScene(scene) {
  state.scene = scene;
  els.recommendView.hidden = scene !== "recommend";
  els.searchView.hidden = scene !== "search";
  els.searchLabel.textContent = scene === "search" ? state.bootstrap.searchQuery : "绝美白色短袖 t 恤";
  document.querySelectorAll("[data-tab]").forEach((button) => button.classList.toggle("active", button.dataset.tab === scene));
  els.scroller.scrollTop = 0;
  renderExamples();
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  setTimeout(() => { els.toast.hidden = true; }, 2600);
}

function renderExamples() {
  if (!state.bootstrap) return;
  const examples = state.bootstrap.examples[state.scene];
  els.examples.innerHTML = examples.map((example) => `<button type="button" data-example="${escapeHtml(example)}">“${escapeHtml(example)}”</button>`).join("");
  document.querySelectorAll("[data-example]").forEach((button) => {
    button.addEventListener("click", () => {
      els.transcript.textContent = button.dataset.example;
      state.transcript = button.dataset.example;
      setTimeout(() => applyTranscript(button.dataset.example), 500);
    });
  });
}

function openVoice(autoListen = false) {
  els.onboarding.hidden = true;
  els.voiceSheet.hidden = false;
  els.transcript.textContent = "等待你说话…";
  els.fallbackInput.value = "";
  state.transcript = "";
  els.voiceTitle.textContent = state.sessionIntent.length > 0
    ? "继续说，推荐会再次调整"
    : "说出你此刻想看的";
  els.voiceHint.textContent = "可以说具体商品、生活场景，或探索灵感";
  setListeningUI(false);
  renderExamples();
  renderVoiceKeywords();
  if (autoListen) startListening();
}

function closeVoice() {
  stopListening(false);
  els.voiceSheet.hidden = true;
}

function createRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;
  const recognition = new SpeechRecognition();
  recognition.lang = "zh-CN";
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.onstart = () => {
    state.recognitionPending = false;
    state.recognitionStarted = true;
    state.listening = true;
    if (state.cancelOnStart) {
      state.cancelOnStart = false;
      state.ignoreNextAbort = true;
      state.listening = false;
      state.recognitionStarted = false;
      recognition.abort();
      return;
    }
    setListeningUI(true);
    if (state.stopAfterStart) {
      state.stopAfterStart = false;
      state.submitOnEnd = true;
      els.transcript.textContent = "麦克风已就绪，请说话，再点一次结束";
      return;
    }
    els.transcript.textContent = "我在听…";
  };
  recognition.onresult = (event) => {
    let value = "";
    for (let i = 0; i < event.results.length; i += 1) value += event.results[i][0].transcript;
    state.transcript = value.trim();
    els.transcript.textContent = state.transcript || "我在听…";
  };
  recognition.onerror = (event) => {
    const wasExpectedAbort = event.error === "aborted" && state.ignoreNextAbort;
    const canSubmitTranscript = event.error === "aborted" && state.submitOnEnd && Boolean(state.transcript);
    state.ignoreNextAbort = false;
    state.recognitionFailed = !canSubmitTranscript;
    if (!canSubmitTranscript) state.submitOnEnd = false;
    state.listening = false;
    state.recognitionPending = false;
    state.recognitionStarted = false;
    setListeningUI(false);
    if (event.error === "aborted") {
      state.recognition = null;
      if (!wasExpectedAbort && !canSubmitTranscript) {
        els.transcript.textContent = "刚刚没有录到声音，请重新按住说话";
      }
      return;
    }
    const messages = {
      "not-allowed": "麦克风权限未开放",
      "service-not-allowed": "当前浏览器限制了语音服务",
      network: "语音识别服务暂时无法连接",
      "audio-capture": "没有检测到可用麦克风",
      "no-speech": "没有听清，请再试一次",
    };
    const message = messages[event.error] || `语音识别失败（${event.error || "未知错误"}）`;
    if (["not-allowed", "service-not-allowed", "network", "audio-capture"].includes(event.error)) {
      showSpeechUnavailable(message);
    } else {
      els.transcript.textContent = message;
    }
  };
  recognition.onend = () => {
    const shouldSubmit = state.submitOnEnd && state.transcript && !state.recognitionFailed;
    state.listening = false;
    state.recognitionPending = false;
    state.recognitionStarted = false;
    state.submitOnEnd = false;
    setListeningUI(false);
    if (shouldSubmit) {
      const value = state.transcript;
      setTimeout(() => applyTranscript(value), 500);
    }
  };
  return recognition;
}

function setListeningUI(listening) {
  els.wave.classList.toggle("listening", listening);
  els.holdButton.classList.toggle("is-listening", listening);
  const strong = els.holdButton.querySelector("strong");
  if (listening) {
    strong.textContent = state.submitOnEnd ? "再点一次结束" : "正在聆听";
  } else {
    strong.textContent = "按住或轻点";
  }
}

function setMicrophonePendingUI() {
  els.wave.classList.add("listening");
  els.holdButton.classList.add("is-listening");
  els.holdButton.querySelector("strong").textContent = "等待麦克风";
}

function showSpeechUnavailable(reason) {
  state.listening = false;
  state.recognitionPending = false;
  state.recognitionStarted = false;
  state.stopAfterStart = false;
  state.cancelOnStart = false;
  state.recognition = null;
  setListeningUI(false);
  els.transcript.textContent = `${reason}。请使用 Chrome、Edge 或 Safari，并允许麦克风权限；也可以改用下方文字输入。`;
}

function startListening() {
  if (state.listening || state.recognitionPending) return;
  state.recognition ||= createRecognition();
  if (!state.recognition) {
    showSpeechUnavailable("当前浏览器不支持网页语音识别");
    return;
  }
  state.recognitionPending = true;
  state.recognitionStarted = false;
  state.recognitionFailed = false;
  state.cancelOnStart = false;
  state.stopAfterStart = false;
  setMicrophonePendingUI();
  els.transcript.textContent = "正在连接麦克风…";
  try {
    state.transcript = "";
    state.recognition.start();
  } catch (error) {
    state.listening = false;
    state.recognitionPending = false;
    state.recognitionStarted = false;
    state.recognition = null;
    setListeningUI(false);
    const denied = error?.name === "NotAllowedError" || error?.name === "SecurityError";
    showSpeechUnavailable(denied ? "麦克风权限未开放" : "无法启动麦克风");
  }
}

function stopListening(shouldApply = true) {
  state.submitOnEnd = shouldApply;
  if (state.recognitionPending) {
    if (shouldApply) state.stopAfterStart = true;
    else state.cancelOnStart = true;
    return;
  }
  if (state.recognition && state.listening) {
    state.recognition.stop();
    return;
  }
  if (shouldApply && state.transcript && !state.recognitionFailed) {
    const value = state.transcript;
    setTimeout(() => applyTranscript(value), 500);
  }
  state.listening = false;
  setListeningUI(false);
}

async function applyTranscript(transcript) {
  state.previous = snapshot();
  els.transcript.textContent = `“${transcript}”`;
  try {
    const result = await api("/api/intent/apply", {
      method: "POST",
      body: JSON.stringify({
        scene: state.scene,
        transcript,
        baseQuery: state.bootstrap.searchQuery,
        sessionIntent: state.sessionIntent,
      }),
    });
    const intentCatalogIds = await intentCatalogProductIds(transcript, result.sessionIntent || []);
    applyIntentCatalogFallback(result, intentCatalogIds);
    if (!applyHomeCatalogIntentFallback(result, transcript)) {
      els.transcript.textContent = result.feedback;
      return;
    }
    (result.products || []).forEach((item) => state.products.set(item.id, item));
    state.sessionIntent = result.sessionIntent;
    if (state.scene === "recommend") {
      state.activeIntentProductIds = intentCatalogIds;
      const catalogIds = rankHomeCatalogForIntent(result.sessionIntent);
      state.recommendationIds = usableResultIds(
        intentCatalogIds,
        catalogIds,
        result.resultIds,
        result.nearMatchIds,
        state.previous?.recommendationIds,
        state.bootstrap.initialRecommendations,
      );
      els.subtitle.textContent = "已融合你刚刚表达的即时意图";
    } else {
      state.searchIds = result.resultIds;
      state.nearIds = result.resultIds.length < 3 ? result.nearMatchIds : [];
    }
    closeVoice();
    renderIntents();
    renderProducts();
    renderVoiceKeywords();
    scrollProductsToTop();
    const keywordLabels = result.sessionIntent.map((condition) => condition.label);
    els.voiceTitle.textContent = "已理解，推荐已刷新";
    els.voiceHint.textContent = "可以说具体商品、生活场景，或探索灵感";
    els.transcript.textContent = keywordLabels.length
      ? `已提取关键词：${keywordLabels.join(" · ")}`
      : `“${transcript}”`;
  } catch (error) {
    els.transcript.textContent = error.message;
    showToast(error.message);
  }
}

async function rerankCurrentConditions() {
  if (state.sessionIntent.length === 0) {
    state.activeIntentProductIds = [];
    state.recommendationIds = state.homeRecommendationIds.length
      ? [...state.homeRecommendationIds]
      : [...state.bootstrap.initialRecommendations];
    state.searchIds = [...state.bootstrap.initialSearchResults];
    state.nearIds = [];
    els.subtitle.textContent = "根据你的长期偏好推荐";
    renderProducts();
    return;
  }
  const result = await api("/api/intent/apply", {
    method: "POST",
    body: JSON.stringify({ scene: state.scene, transcript: "保持当前条件", sessionIntent: state.sessionIntent }),
  });
  (result.products || []).forEach((item) => state.products.set(item.id, item));
  if (state.scene === "recommend") {
    const catalogIds = rankHomeCatalogForIntent(state.sessionIntent);
    state.recommendationIds = usableResultIds(
      state.activeIntentProductIds,
      catalogIds,
      result.resultIds,
      result.nearMatchIds,
      state.recommendationIds,
      state.bootstrap.initialRecommendations,
    );
  }
  else {
    state.searchIds = result.resultIds;
    state.nearIds = result.resultIds.length < 3 ? result.nearMatchIds : [];
  }
  renderProducts();
}

function bindLongPress() {
  let timer = null;
  let triggered = false;
  let startX = 0;
  let startY = 0;
  els.scroller.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button, input, .product-card")) return;
    triggered = false;
    startX = event.clientX;
    startY = event.clientY;
    timer = setTimeout(() => {
      triggered = true;
      openVoice(true);
      if (navigator.vibrate) navigator.vibrate(25);
    }, 350);
  });
  els.scroller.addEventListener("pointermove", (event) => {
    if (Math.hypot(event.clientX - startX, event.clientY - startY) > 12) clearTimeout(timer);
  });
  window.addEventListener("pointerup", () => {
    clearTimeout(timer);
    if (triggered) stopListening(true);
    triggered = false;
  });
  els.scroller.addEventListener("pointercancel", () => clearTimeout(timer));
}

function bindEvents() {
  document.querySelectorAll("[data-open-voice]").forEach((button) => button.addEventListener("click", () => openVoice(false)));
  document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => switchScene(button.dataset.tab)));
  document.querySelector("#home-logo").addEventListener("click", () => switchScene("recommend"));
  document.querySelector("#back-to-home").addEventListener("click", () => switchScene("recommend"));
  document.querySelector("#dismiss-onboarding").addEventListener("click", () => { els.onboarding.hidden = true; });
  els.clearAllIntents.addEventListener("click", () => {
    clearAllIntents().catch((error) => showToast(`清除失败：${error.message}`));
  });
  els.voiceClose.addEventListener("click", closeVoice);
  els.voiceSheet.querySelector(".voice-backdrop").addEventListener("click", closeVoice);
  let voicePressStartedAt = 0;
  let listeningBeforePress = false;
  els.holdButton.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    voicePressStartedAt = Date.now();
    listeningBeforePress = state.listening || state.recognitionPending;
    if (!listeningBeforePress) startListening();
  });
  els.holdButton.addEventListener("pointerup", (event) => {
    event.preventDefault();
    if (listeningBeforePress || Date.now() - voicePressStartedAt >= 650) {
      stopListening(true);
      return;
    }
    state.submitOnEnd = true;
    if (state.listening) setListeningUI(true);
    if (state.recognitionPending) els.transcript.textContent = "麦克风就绪后开始聆听…";
  });
  els.holdButton.addEventListener("pointercancel", () => stopListening(false));
  els.fallbackForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = els.fallbackInput.value.trim();
    if (!value) return;
    state.transcript = value;
    els.transcript.textContent = `“${value}”`;
    setTimeout(() => applyTranscript(value), 500);
  });
  els.scroller.addEventListener("scroll", () => {
    if (els.scroller.scrollTop > 120) preloadNextHomepageRound();
    fillHomepageScrollBuffer();
  }, { passive: true });
  bindLongPress();
}

async function init() {
  try {
    state.bootstrap = await api("/api/demo/bootstrap");
    state.products = new Map(state.bootstrap.products.map((item) => [item.id, item]));
    state.recommendationIds = [];
    state.searchIds = [...state.bootstrap.initialSearchResults];
    renderProducts();
    showHomepageLoading();
    renderIntents();
    renderExamples();
    bindEvents();
    await loadHomepageCatalog();
  } catch (error) {
    showToast(`Demo 加载失败：${error.message}`);
  }
}

init();
