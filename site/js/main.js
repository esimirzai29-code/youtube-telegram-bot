/* ============================================
   تک‌نوشت | منطق اصلی (مشترک همه صفحات + خانه)
   ============================================ */

/* ---------- ابزارهای ذخیره‌سازی ---------- */
const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem("tak_" + key)) ?? fallback; }
    catch { return fallback; }
  },
  set(key, val) { localStorage.setItem("tak_" + key, JSON.stringify(val)); }
};

const getSaved = () => store.get("saved", []);
const getLiked = () => store.get("liked", []);
const getLikesExtra = () => store.get("likesExtra", {});
const likesOf = (a) => a.baseLikes + (getLikesExtra()[a.id] || 0);

/* ---------- تست ---------- */
function toast(msg, type = "") {
  const wrap = document.getElementById("toastWrap");
  if (!wrap) return;
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "0.3s"; setTimeout(() => el.remove(), 300); }, 2600);
}

/* ---------- تم شب/روز ---------- */
function initTheme() {
  const btn = document.getElementById("themeBtn");
  const saved = store.get("theme", "light");
  document.documentElement.dataset.theme = saved;
  if (btn) btn.textContent = saved === "dark" ? "☀️" : "🌙";
  btn?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    store.set("theme", next);
    btn.textContent = next === "dark" ? "☀️" : "🌙";
    toast(next === "dark" ? "🌙 حالت شب فعال شد" : "☀️ حالت روز فعال شد");
  });
}

/* ---------- منوی موبایل ---------- */
function initMenu() {
  const btn = document.getElementById("menuBtn");
  const nav = document.getElementById("mobileNav");
  btn?.addEventListener("click", () => nav.classList.toggle("open"));
}

/* ---------- جستجو ---------- */
function initSearch() {
  const overlay = document.getElementById("searchOverlay");
  const input = document.getElementById("searchInput");
  const results = document.getElementById("searchResults");
  const openBtn = document.getElementById("searchBtn");
  if (!overlay || !input) return;

  const open = () => { overlay.classList.add("open"); setTimeout(() => input.focus(), 50); };
  const close = () => overlay.classList.remove("open");
  openBtn?.addEventListener("click", open);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
    if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); open(); }
  });

  input.addEventListener("input", () => {
    const q = input.value.trim();
    if (q.length < 2) {
      results.innerHTML = '<div class="search-hint">چند حرف بنویسید تا نتایج نمایش داده شود ✍️</div>';
      return;
    }
    const found = ARTICLES.filter(a =>
      a.title.includes(q) || a.excerpt.includes(q) ||
      a.tags.some(t => t.includes(q)) || getCategory(a.category).name.includes(q)
    );
    if (!found.length) {
      results.innerHTML = '<div class="search-hint">😕 چیزی پیدا نشد. عبارت دیگری را امتحان کنید.</div>';
      return;
    }
    results.innerHTML = found.map(a => `
      <a class="search-item" href="article.html?id=${a.id}">
        <span class="emoji">${a.cover.emoji}</span>
        <div><b>${a.title}</b><span>${getCategory(a.category).name} • ${a.date}</span></div>
      </a>`).join("");
  });
}

/* ---------- دکمه بازگشت به بالا ---------- */
function initBackTop() {
  const btn = document.getElementById("backTop");
  if (!btn) return;
  window.addEventListener("scroll", () => btn.classList.toggle("show", window.scrollY > 500));
  btn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
}

/* ---------- فوتر: دسته‌بندی‌ها ---------- */
function initFooterCats() {
  const ul = document.getElementById("footerCats");
  if (!ul) return;
  ul.innerHTML = CATEGORIES.map(c =>
    `<li><a href="index.html?cat=${c.id}#articles">${c.icon} ${c.name}</a></li>`).join("");
}

/* ---------- آمار ---------- */
function initStats() {
  const bar = document.getElementById("statsBar");
  if (!bar) return;
  const totalViews = ARTICLES.reduce((s, a) => s + a.views, 0);
  const totalLikes = ARTICLES.reduce((s, a) => s + likesOf(a), 0);
  const totalRead = ARTICLES.reduce((s, a) => s + a.readTime, 0);
  bar.innerHTML = `
    <div class="stat"><b>${faNum(ARTICLES.length)}</b><span>📝 مقاله منتشرشده</span></div>
    <div class="stat"><b>${faNum(totalViews)}</b><span>👁️ مجموع بازدید</span></div>
    <div class="stat"><b>${faNum(totalLikes)}</b><span>❤️ مجموع لایک</span></div>
    <div class="stat"><b>${faNum(totalRead)} دقیقه</b><span>⏱️ زمان مطالعه</span></div>`;
}

/* =====================================================
   صفحه خانه
   ===================================================== */
let activeCat = "all";
let activeSort = "new";
let activeTag = "";
let visibleCount = 6;
const PAGE_SIZE = 6;

function initHome() {
  const grid = document.getElementById("articlesGrid");
  if (!grid) return;

  // دسته‌بندی از URL (مثلاً از فوتر)
  const params = new URLSearchParams(location.search);
  if (params.get("cat")) activeCat = params.get("cat");
  if (params.get("tag")) activeTag = params.get("tag");

  renderHero();
  renderFilters();
  renderCategoryList();
  renderPopular();
  renderTags();
  renderGrid();

  document.getElementById("sortSelect")?.addEventListener("change", (e) => {
    activeSort = e.target.value;
    visibleCount = PAGE_SIZE;
    renderGrid();
  });
  document.getElementById("loadMoreBtn")?.addEventListener("click", () => {
    visibleCount += PAGE_SIZE;
    renderGrid();
  });
  document.getElementById("newsletterForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = document.getElementById("newsletterEmail").value.trim();
    if (!email || !email.includes("@")) return toast("❌ لطفاً یک ایمیل معتبر وارد کنید", "error");
    const subs = store.get("subs", []);
    if (subs.includes(email)) return toast("شما قبلاً عضو خبرنامه هستید 📬");
    subs.push(email);
    store.set("subs", subs);
    document.getElementById("newsletterEmail").value = "";
    toast("✅ عضویت شما در خبرنامه ثبت شد!", "success");
  });
}

function renderHero() {
  const wrap = document.getElementById("heroGrid");
  if (!wrap) return;
  const feat = ARTICLES.filter(a => a.featured).slice(0, 3);
  const [main, ...side] = feat.length ? feat : ARTICLES.slice(0, 3);
  wrap.innerHTML = `
    <a class="hero-main" href="article.html?id=${main.id}">
      <div class="hero-cover" style="background:${main.cover.gradient}">${main.cover.emoji}</div>
      <div class="hero-content">
        <span class="badge">⭐ ویژه • ${getCategory(main.category).name}</span>
        <h2>${main.title}</h2>
        <div class="hero-meta"><span>✍️ ${main.author.name}</span><span>📅 ${main.date}</span><span>⏱️ ${faNum(main.readTime)} دقیقه</span></div>
      </div>
    </a>
    <div class="hero-side">
      ${side.map(a => `
        <a class="hero-side-card" href="article.html?id=${a.id}">
          <div class="hero-cover" style="background:${a.cover.gradient}">${a.cover.emoji}</div>
          <div class="hero-content">
            <span class="badge">${getCategory(a.category).name}</span>
            <h3>${a.title}</h3>
          </div>
        </a>`).join("")}
    </div>`;
}

function renderFilters() {
  const wrap = document.getElementById("categoryFilters");
  if (!wrap) return;
  const all = [{ id: "all", name: "همه", icon: "🌍" }, ...CATEGORIES];
  wrap.innerHTML = all.map(c =>
    `<button class="chip ${activeCat === c.id ? "active" : ""}" data-cat="${c.id}">${c.icon} ${c.name}</button>`
  ).join("");
  wrap.querySelectorAll(".chip").forEach(ch => ch.addEventListener("click", () => {
    activeCat = ch.dataset.cat;
    activeTag = "";
    visibleCount = PAGE_SIZE;
    renderFilters();
    renderGrid();
  }));
}

function filteredArticles() {
  let list = [...ARTICLES];
  if (activeCat !== "all") list = list.filter(a => a.category === activeCat);
  if (activeTag) list = list.filter(a => a.tags.includes(activeTag));
  if (activeSort === "popular") list.sort((a, b) => b.views - a.views);
  else if (activeSort === "liked") list.sort((a, b) => likesOf(b) - likesOf(a));
  else if (activeSort === "saved") {
    const saved = getSaved();
    list = list.filter(a => saved.includes(a.id));
  } else list.sort((a, b) => b.id - a.id);
  return list;
}

function cardHTML(a) {
  const saved = getSaved().includes(a.id);
  const cat = getCategory(a.category);
  return `
    <article class="card">
      <a href="article.html?id=${a.id}" class="card-cover" style="background:${a.cover.gradient}">
        <span style="font-size:4rem">${a.cover.emoji}</span>
        <button class="bookmark-btn ${saved ? "saved" : ""}" data-save="${a.id}" title="نشان کردن">${saved ? "🔖" : "📑"}</button>
      </a>
      <div class="card-body">
        <div><span class="badge solid">${cat.icon} ${cat.name}</span></div>
        <a href="article.html?id=${a.id}"><h3>${a.title}</h3></a>
        <p>${a.excerpt.slice(0, 110)}...</p>
        <div class="card-meta">
          <span class="author"><span class="avatar">${a.author.name[0]}</span>${a.author.name}</span>
          <span>⏱️ ${faNum(a.readTime)} دقیقه</span>
        </div>
        <div class="card-meta" style="border:none; padding-top:0; margin-top:8px">
          <span>👁️ ${faNum(a.views)} • ❤️ ${faNum(likesOf(a))}</span>
          <a class="read-more" href="article.html?id=${a.id}">ادامه مطلب ←</a>
        </div>
      </div>
    </article>`;
}

function renderGrid() {
  const grid = document.getElementById("articlesGrid");
  const count = document.getElementById("resultCount");
  const moreBtn = document.getElementById("loadMoreBtn");
  const list = filteredArticles();
  const shown = list.slice(0, visibleCount);

  if (count) count.textContent = activeTag
    ? `🏷️ برچسب «${activeTag}» — ${faNum(list.length)} مقاله`
    : `${faNum(list.length)} مقاله`;

  grid.innerHTML = shown.length ? shown.map(cardHTML).join("") : `
    <div class="empty" style="grid-column:1/-1">
      <span class="big">📭</span>
      <p>${activeSort === "saved" ? "هنوز مقاله‌ای را نشان نکرده‌اید. روی دکمه 📑 هر مقاله بزنید!" : "مقاله‌ای در این دسته وجود ندارد."}</p>
    </div>`;

  if (moreBtn) moreBtn.style.display = list.length > visibleCount ? "" : "none";

  grid.querySelectorAll("[data-save]").forEach(btn => btn.addEventListener("click", (e) => {
    e.preventDefault();
    toggleSave(Number(btn.dataset.save));
  }));
}

function toggleSave(id) {
  let saved = getSaved();
  if (saved.includes(id)) {
    saved = saved.filter(x => x !== id);
    toast("🔖 از نشان‌شده‌ها حذف شد");
  } else {
    saved.push(id);
    toast("✅ به نشان‌شده‌ها اضافه شد!", "success");
  }
  store.set("saved", saved);
  renderGrid();
}

function renderCategoryList() {
  const wrap = document.getElementById("categoryList");
  if (!wrap) return;
  wrap.innerHTML = CATEGORIES.map(c => `
    <a class="cat-row" href="#" data-cat="${c.id}">
      <span>${c.icon} ${c.name}</span><span class="count">${faNum(countByCategory(c.id))}</span>
    </a>`).join("");
  wrap.querySelectorAll("[data-cat]").forEach(el => el.addEventListener("click", (e) => {
    e.preventDefault();
    activeCat = el.dataset.cat;
    activeTag = "";
    visibleCount = PAGE_SIZE;
    renderFilters();
    renderGrid();
    document.getElementById("articles")?.scrollIntoView({ behavior: "smooth" });
  }));
}

function renderPopular() {
  const wrap = document.getElementById("popularList");
  if (!wrap) return;
  const top = [...ARTICLES].sort((a, b) => b.views - a.views).slice(0, 4);
  wrap.innerHTML = top.map(a => `
    <a class="mini-post" href="article.html?id=${a.id}">
      <span class="mini-cover" style="background:${a.cover.gradient}">${a.cover.emoji}</span>
      <div><b>${a.title.slice(0, 45)}...</b><span>👁️ ${faNum(a.views)} بازدید</span></div>
    </a>`).join("");
}

function renderTags() {
  const wrap = document.getElementById("tagCloud");
  if (!wrap) return;
  wrap.innerHTML = allTags().map(([t, n]) =>
    `<a class="tag" href="#" data-tag="${t}">#${t} (${faNum(n)})</a>`).join("");
  wrap.querySelectorAll("[data-tag]").forEach(el => el.addEventListener("click", (e) => {
    e.preventDefault();
    activeTag = el.dataset.tag;
    activeCat = "all";
    visibleCount = PAGE_SIZE;
    renderFilters();
    renderGrid();
    document.getElementById("articles")?.scrollIntoView({ behavior: "smooth" });
  }));
}

/* =====================================================
   صفحه درباره ما / تماس
   ===================================================== */
function initTeam() {
  const grid = document.getElementById("teamGrid");
  if (!grid) return;
  const team = [
    { name: "سارا محمدی", role: "تحلیل‌گر فناوری و سردبیر", emoji: "👩‍💻", grad: "linear-gradient(135deg,#6366f1,#a855f7)" },
    { name: "علی رضایی", role: "توسعه‌دهنده ارشد فرانت‌اند", emoji: "👨‍💻", grad: "linear-gradient(135deg,#0ea5e9,#10b981)" },
    { name: "مریم کریمی", role: "متخصص سئو و محتوا", emoji: "👩‍🎨", grad: "linear-gradient(135deg,#ec4899,#f59e0b)" },
  ];
  grid.innerHTML = team.map(m => `
    <div class="widget" style="text-align:center">
      <div style="width:90px;height:90px;border-radius:50%;background:${m.grad};display:grid;place-items:center;font-size:2.8rem;margin:0 auto 12px">${m.emoji}</div>
      <h3>${m.name}</h3>
      <p style="font-size:.88rem;color:var(--text-muted)">${m.role}</p>
    </div>`).join("");
}

function initContact() {
  const form = document.getElementById("contactForm");
  if (!form) return;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("cName").value.trim();
    const email = document.getElementById("cEmail").value.trim();
    const msg = document.getElementById("cMsg").value.trim();
    if (!name || !email || !msg) return toast("❌ لطفاً همه فیلدهای ضروری را پر کنید", "error");
    const msgs = store.get("contactMsgs", []);
    msgs.push({ name, email, subject: document.getElementById("cSubject").value, msg, at: Date.now() });
    store.set("contactMsgs", msgs);
    form.reset();
    toast("✅ پیام شما با موفقیت ارسال شد!", "success");
  });
}

/* ---------- اجرا ---------- */
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initMenu();
  initSearch();
  initBackTop();
  initFooterCats();
  initStats();
  initHome();
  initTeam();
  initContact();
});
