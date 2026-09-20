/* ============================================
   تک‌نوشت | منطق صفحه مقاله
   ============================================ */

document.addEventListener("DOMContentLoaded", () => {
  const main = document.getElementById("articleMain");
  if (!main) return;

  const id = Number(new URLSearchParams(location.search).get("id"));
  const article = getArticle(id);

  if (!article) {
    main.innerHTML = `
      <div class="empty" style="padding:100px 20px">
        <span class="big">😕</span>
        <h2>مقاله پیدا نشد!</h2>
        <p>ممکن است حذف شده باشد یا آدرس اشتباه باشد.</p><br/>
        <a class="btn" href="index.html">🏠 بازگشت به خانه</a>
      </div>`;
    return;
  }

  document.title = article.title + " | تک‌نوشت";
  const cat = getCategory(article.category);
  const saved = getSaved().includes(article.id);
  const liked = getLiked().includes(article.id);

  // ثبت بازدید (شبیه‌سازی‌شده)
  const viewsExtra = store.get("viewsExtra", {});
  viewsExtra[article.id] = (viewsExtra[article.id] || 0) + 1;
  store.set("viewsExtra", viewsExtra);
  const views = article.views + viewsExtra[article.id];

  const related = ARTICLES.filter(a => a.id !== article.id && a.category === article.category)
    .concat(ARTICLES.filter(a => a.id !== article.id && a.category !== article.category))
    .slice(0, 3);

  main.innerHTML = `
    <div class="breadcrumb">
      <a href="index.html">🏠 خانه</a><span>‹</span>
      <a href="index.html?cat=${cat.id}#articles">${cat.icon} ${cat.name}</a><span>‹</span>
      <span>${article.title.slice(0, 30)}...</span>
    </div>

    <div class="article-head">
      <span class="badge solid">${cat.icon} ${cat.name}</span>
      <h1>${article.title}</h1>
      <div class="article-meta">
        <span class="author"><span class="avatar">${article.author.name[0]}</span> ${article.author.name} • ${article.author.role}</span>
        <span>📅 ${article.date}</span>
        <span>⏱️ ${faNum(article.readTime)} دقیقه مطالعه</span>
        <span>👁️ ${faNum(views)} بازدید</span>
      </div>
    </div>

    <div class="article-cover" style="background:${article.cover.gradient}">${article.cover.emoji}</div>

    <div class="article-layout">
      <div>
        <article class="article-body">
          ${article.content}
          <div class="article-tags">
            ${article.tags.map(t => `<a class="tag" href="index.html?tag=${encodeURIComponent(t)}#articles">#${t}</a>`).join("")}
          </div>
          <div class="action-bar">
            <button class="action-btn ${liked ? "liked" : ""}" id="likeBtn">❤️ <span id="likeCount">${faNum(likesOf(article))}</span> لایک</button>
            <button class="action-btn ${saved ? "saved" : ""}" id="saveBtn">${saved ? "🔖 ذخیره شده" : "📑 نشان کردن"}</button>
            <button class="action-btn" id="shareBtn">📤 اشتراک‌گذاری</button>
          </div>
        </article>

        <section class="comments">
          <div class="section-head"><h2>💬 دیدگاه‌ها (<span id="commentCount">۰</span>)</h2></div>
          <div id="commentList"></div>
          <form class="comment-form" id="commentForm">
            <div class="row">
              <input type="text" id="cmName" placeholder="نام شما *" required />
              <input type="email" id="cmEmail" placeholder="ایمیل (نمایش داده نمی‌شود)" />
            </div>
            <textarea id="cmText" rows="3" placeholder="نظر خود را بنویسید... *" required></textarea>
            <button type="submit" class="btn">📝 ثبت دیدگاه</button>
          </form>
        </section>
      </div>

      <aside class="sidebar" style="position:sticky; top:90px">
        <div class="widget">
          <h3>✍️ نویسنده</h3>
          <div style="display:flex; gap:12px; align-items:center">
            <span class="avatar" style="width:52px;height:52px;font-size:1.3rem">${article.author.name[0]}</span>
            <div><b>${article.author.name}</b><br/><span style="font-size:.82rem;color:var(--text-muted)">${article.author.role}</span></div>
          </div>
        </div>
        <div class="widget">
          <h3>📊 اطلاعات مقاله</h3>
          <div class="cat-row"><span>📅 تاریخ انتشار</span><b style="font-size:.82rem">${article.date}</b></div>
          <div class="cat-row"><span>⏱️ زمان مطالعه</span><b>${faNum(article.readTime)} دقیقه</b></div>
          <div class="cat-row"><span>👁️ بازدید</span><b>${faNum(views)}</b></div>
          <div class="cat-row"><span>❤️ لایک</span><b>${faNum(likesOf(article))}</b></div>
        </div>
        <div class="widget">
          <h3>🔥 پربازدیدترین‌ها</h3>
          <div id="artPopular"></div>
        </div>
      </aside>
    </div>

    <section class="related">
      <div class="section-head"><h2>📚 مطالب مرتبط</h2><a class="read-more" href="index.html#articles">همه مقالات ←</a></div>
      <div class="related-grid">
        ${related.map(a => `
          <article class="card">
            <a href="article.html?id=${a.id}" class="card-cover" style="background:${a.cover.gradient}; height:130px"><span style="font-size:3rem">${a.cover.emoji}</span></a>
            <div class="card-body">
              <div><span class="badge solid">${getCategory(a.category).icon} ${getCategory(a.category).name}</span></div>
              <a href="article.html?id=${a.id}"><h3 style="font-size:.95rem">${a.title}</h3></a>
              <div class="card-meta"><span>👁️ ${faNum(a.views)}</span><span>⏱️ ${faNum(a.readTime)} دقیقه</span></div>
            </div>
          </article>`).join("")}
      </div>
    </section>`;

  /* نوار پیشرفت مطالعه */
  const bar = document.getElementById("progressBar");
  window.addEventListener("scroll", () => {
    const h = document.documentElement;
    const pct = h.scrollTop / (h.scrollHeight - h.clientHeight) * 100;
    if (bar) bar.style.width = pct + "%";
  });

  /* لایک */
  document.getElementById("likeBtn").addEventListener("click", function () {
    let likedArr = getLiked();
    const extra = getLikesExtra();
    if (likedArr.includes(article.id)) {
      likedArr = likedArr.filter(x => x !== article.id);
      extra[article.id] = Math.max(0, (extra[article.id] || 1) - 1);
      this.classList.remove("liked");
      toast("💔 لایک شما برداشته شد");
    } else {
      likedArr.push(article.id);
      extra[article.id] = (extra[article.id] || 0) + 1;
      this.classList.add("liked");
      toast("❤️ ممنون از لایک شما!", "success");
    }
    store.set("liked", likedArr);
    store.set("likesExtra", extra);
    document.getElementById("likeCount").textContent = faNum(likesOf(article));
  });

  /* نشان کردن */
  document.getElementById("saveBtn").addEventListener("click", function () {
    let savedArr = getSaved();
    if (savedArr.includes(article.id)) {
      savedArr = savedArr.filter(x => x !== article.id);
      this.classList.remove("saved");
      this.textContent = "📑 نشان کردن";
      toast("🔖 از نشان‌شده‌ها حذف شد");
    } else {
      savedArr.push(article.id);
      this.classList.add("saved");
      this.textContent = "🔖 ذخیره شده";
      toast("✅ به نشان‌شده‌ها اضافه شد!", "success");
    }
    store.set("saved", savedArr);
  });

  /* اشتراک‌گذاری */
  document.getElementById("shareBtn").addEventListener("click", async () => {
    const url = location.href;
    if (navigator.share) {
      try { await navigator.share({ title: article.title, text: article.excerpt, url }); } catch {}
    } else if (navigator.clipboard) {
      await navigator.clipboard.writeText(url);
      toast("🔗 لینک مقاله کپی شد!", "success");
    } else {
      prompt("لینک مقاله را کپی کنید:", url);
    }
  });

  /* پربازدیدترین‌های سایدبار */
  const pop = [...ARTICLES].sort((a, b) => b.views - a.views).slice(0, 4);
  document.getElementById("artPopular").innerHTML = pop.map(a => `
    <a class="mini-post" href="article.html?id=${a.id}">
      <span class="mini-cover" style="background:${a.cover.gradient}">${a.cover.emoji}</span>
      <div><b>${a.title.slice(0, 40)}...</b><span>👁️ ${faNum(a.views)}</span></div>
    </a>`).join("");

  /* دیدگاه‌ها */
  const seedComments = [
    { name: "رضا احمدی", text: "عالی بود! دقیقاً همون چیزی بود که دنبالش می‌گشتم. ممنون از محتوای باکیفیتتون 👏", at: Date.now() - 86400000 * 2 },
    { name: "نگار حسینی", text: "خیلی کاربردی و روان نوشته شده. منتظر مقالات بعدی در این موضوع هستم.", at: Date.now() - 86400000 },
  ];
  const getComments = () => {
    const all = store.get("comments", {});
    if (!all[article.id]) { all[article.id] = seedComments; store.set("comments", all); }
    return all[article.id];
  };
  const renderComments = () => {
    const list = getComments();
    document.getElementById("commentCount").textContent = faNum(list.length);
    document.getElementById("commentList").innerHTML = list.length ? list.map(c => `
      <div class="comment">
        <span class="avatar">${(c.name || "?")[0]}</span>
        <div class="comment-body">
          <b>${c.name}</b><time>${new Date(c.at).toLocaleDateString("fa-IR")}</time>
          <p>${c.text}</p>
        </div>
      </div>`).join("")
      : '<div class="empty"><span class="big">💭</span><p>هنوز دیدگاهی ثبت نشده. اولین نفر باشید!</p></div>';
  };
  renderComments();

  document.getElementById("commentForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("cmName").value.trim();
    const text = document.getElementById("cmText").value.trim();
    if (!name || !text) return toast("❌ نام و متن دیدگاه ضروری است", "error");
    const all = store.get("comments", {});
    (all[article.id] = all[article.id] || []).unshift({ name, text, at: Date.now() });
    store.set("comments", all);
    e.target.reset();
    renderComments();
    toast("✅ دیدگاه شما ثبت شد!", "success");
  });
});
