(function () {
  "use strict";


  const storageKey = "family-gift-registry-v2";

  const defaultGifts = [
    {
      id: "gift-w-1",
      name: "Sunrise coffee tasting basket",
      recipient: "wife",
      category: "wellness",
      priority: "High",
      price: 95,
      link: "https://www.craftcoffee.com",
      notes: "Include her favorite Ethiopian roast and a handwritten playlist for the tasting.",
      purchased: false,
      added: "2024-01-12T09:00:00.000Z"
    },
    {
      id: "gift-w-2",
      name: "StoryWorth subscription",
      recipient: "wife",
      category: "keepsake",
      priority: "Medium",
      price: 99,
      link: "https://www.storyworth.com",
      notes: "Pair with a new fountain pen from the kids.",
      purchased: true,
      added: "2024-02-02T18:30:00.000Z"
    },
    {

      id: "gift-w-3",
      name: "Moonlit rooftop picnic kit",
      recipient: "wife",
      category: "experience",
      priority: "Medium",
      price: 110,
      link: "https://www.simplesatchel.com",
      notes: "Pack her favorite tapas, string lights, and a new playlist for slow dancing under the stars.",
      purchased: false,
      added: "2024-03-14T17:45:00.000Z"
    },
    {
      id: "gift-k-1",
      name: "Junior chef Saturday",
      recipient: "kids",
      category: "experience",
      priority: "High",
      price: 55,
      link: "https://www.peterspantry.com/classes",
      notes: "Pick a recipe each child can lead. Capture a video taste test!",
      purchased: false,
      added: "2024-03-05T15:20:00.000Z"
    },
    {
      id: "gift-k-2",
      name: "Personalized comic book kit",
      recipient: "kids",
      category: "creative",
      priority: "Medium",
      price: 42,
      link: "https://www.etsy.com/listing/1297619652",
      notes: "Add markers that match their favorite heroes.",
      purchased: false,
      added: "2024-01-28T21:10:00.000Z"

    },
    {
      id: "gift-k-3",
      name: "Backyard astronomy night",
      recipient: "kids",
      category: "learning",
      priority: "High",
      price: 60,
      link: "https://www.exploratoriumstore.com",
      notes: "Set up a telescope, print constellation maps, and wrap a cozy blanket for stargazing.",
      purchased: false,
      added: "2024-02-18T20:05:00.000Z"
    }
  ];

  const recipients = ["wife", "kids"];

  const lists = Object.fromEntries(
    recipients.map((key) => [key, document.querySelector(`[data-recipient-list="${key}"]`)])
  );

  const countLabels = Object.fromEntries(
    recipients.map((key) => [key, document.querySelector(`[data-count-${key}]`)])
  );


  const hasLocalStorage = (() => {
    try {
      const testKey = "__gift_registry_test__";
      window.localStorage.setItem(testKey, "1");
      window.localStorage.removeItem(testKey);
      return true;
    } catch (error) {
      return false;
    }
  })();


  function normalizeRecipient(value) {
    const normalized = String(value || "").toLowerCase();
    switch (normalized) {
      case "wife":
      case "mom":
      case "spouse":
        return "wife";
      case "kid":
      case "kids":
      case "child":
      case "children":
      case "son":
      case "daughter":
        return "kids";
      case "dad":
        return "kids";
      default:
        return "kids";
    }
  }


  const statEls = {
    total: document.querySelector("[data-stat-total]"),
    purchased: document.querySelector("[data-stat-purchased]"),
    remaining: document.querySelector("[data-stat-remaining]"),
    budget: document.querySelector("[data-stat-budget]")
  };

  const form = document.getElementById("gift-form");
  const resetButton = document.getElementById("reset-registry");

  let gifts = loadGifts();

  function loadGifts() {
    if (!hasLocalStorage) {
      return defaultGifts.map((gift) => enhanceGift(gift));
    }

    try {
      const stored = window.localStorage.getItem(storageKey);
      if (!stored) {
        return defaultGifts.map((gift) => enhanceGift(gift));
      }
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) {
        return defaultGifts.map((gift) => enhanceGift(gift));
      }
      return parsed.map(enhanceGift);
    } catch (error) {
      console.warn("Gift registry storage could not be read, restoring defaults.", error);
      return defaultGifts.map((gift) => enhanceGift(gift));
    }
  }

  function enhanceGift(gift) {
    return {
      id: String(gift.id || cryptoRandomId()),
      name: gift.name || "Untitled gift",

      recipient: normalizeRecipient(gift.recipient),

      category: gift.category || "experience",
      priority: gift.priority || "Medium",
      price: normalizePrice(gift.price),
      link: gift.link || "",
      notes: gift.notes || "",
      purchased: Boolean(gift.purchased),
      added: gift.added || new Date().toISOString()
    };
  }

  function normalizePrice(value) {
    if (typeof value === "number") {
      return Number.isFinite(value) ? value : null;
    }
    if (value === null || value === undefined || value === "") {
      return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function cryptoRandomId() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return `gift-${Math.random().toString(16).slice(2, 10)}`;
  }

  function persistGifts() {
    if (!hasLocalStorage) {
      return;
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(gifts));
    } catch (error) {
      console.warn("Unable to save gift registry", error);
    }
  }

  function formatCurrency(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "N/A";
    }
    try {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
    } catch (error) {
      return `$${value.toFixed(2)}`;
    }
  }

  function renderLists() {

    const grouped = {};
    recipients.forEach((key) => {
      grouped[key] = [];
    });

    for (const gift of gifts) {
      const recipient = normalizeRecipient(gift.recipient);
      if (!grouped[recipient]) {
        grouped[recipient] = [];
      }
      grouped[recipient].push(gift);
    }

    recipients.forEach((recipient) => {
      const recipientList = grouped[recipient] || [];
      recipientList.sort(sortByPurchasedThenPriority);
      updateList(lists[recipient], recipientList);
      if (countLabels[recipient]) {
        countLabels[recipient].textContent = summaryText(recipientList.length);
      }
    });

  }

  const priorityWeight = { High: 0, Medium: 1, Low: 2 };

  function sortByPurchasedThenPriority(a, b) {
    if (a.purchased !== b.purchased) {
      return a.purchased ? 1 : -1;
    }
    const weightA = priorityWeight[a.priority] ?? 1;
    const weightB = priorityWeight[b.priority] ?? 1;
    if (weightA !== weightB) {
      return weightA - weightB;
    }
    return new Date(a.added).getTime() - new Date(b.added).getTime();
  }

  function summaryText(count) {
    if (count === 0) {
      return "No items yet";
    }
    return `${count} ${count === 1 ? "item" : "items"}`;
  }

  function updateList(listElement, items) {

    if (!listElement) {
      return;
    }

    listElement.innerHTML = "";
    if (!items.length) {
      const empty = document.createElement("li");
      empty.className = "gift-item gift-item--empty";
      empty.textContent = "Add the first idea to get started.";
      listElement.append(empty);
      return;
    }

    for (const gift of items) {
      const item = document.createElement("li");
      item.className = "gift-item";
      if (gift.purchased) {
        item.classList.add("gift-item--purchased");
      }

      const header = document.createElement("div");
      header.className = "gift-item__header";

      const name = document.createElement("span");
      name.className = "gift-item__name";
      name.textContent = gift.name;

      const badge = document.createElement("span");
      badge.className = "gift-item__badge";
      badge.textContent = `${gift.priority} priority`;

      header.append(name, badge);

      const meta = document.createElement("div");
      meta.className = "gift-item__meta";

      const category = document.createElement("span");
      category.innerHTML = `<span aria-hidden="true">🏷️</span>${gift.category}`;
      meta.append(category);

      if (typeof gift.price === "number" && !Number.isNaN(gift.price)) {
        const price = document.createElement("span");
        price.innerHTML = `<span aria-hidden="true">💰</span>${formatCurrency(gift.price)}`;
        meta.append(price);
      }

      const added = document.createElement("span");
      const addedDate = new Date(gift.added);
      const friendlyDate = !Number.isNaN(addedDate.getTime())
        ? addedDate.toLocaleDateString(undefined, { month: "short", day: "numeric" })
        : "Recently added";
      added.innerHTML = `<span aria-hidden="true">🗓️</span>${friendlyDate}`;
      meta.append(added);

      const actions = document.createElement("div");
      actions.className = "gift-item__actions";

      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "toggle-purchased";
      toggleBtn.textContent = gift.purchased ? "Purchased" : "Mark purchased";
      if (gift.purchased) {
        toggleBtn.classList.add("is-complete");
      }
      toggleBtn.addEventListener("click", () => {
        gift.purchased = !gift.purchased;
        persistGifts();
        render();
      });
      actions.append(toggleBtn);

      if (gift.link) {
        const link = document.createElement("a");
        link.href = gift.link;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "Open link";
        actions.append(link);
      }

      if (gift.notes) {
        const notes = document.createElement("p");
        notes.className = "gift-item__notes";
        notes.textContent = gift.notes;
        item.append(header, meta, notes, actions);
      } else {
        item.append(header, meta, actions);
      }

      listElement.append(item);
    }
  }

  function updateStats() {
    const total = gifts.length;
    const purchased = gifts.filter((gift) => gift.purchased).length;
    const budget = gifts.reduce((sum, gift) => (typeof gift.price === "number" ? sum + gift.price : sum), 0);
    statEls.total.textContent = total;
    statEls.purchased.textContent = purchased;
    statEls.remaining.textContent = Math.max(total - purchased, 0);
    statEls.budget.textContent = formatCurrency(budget);
  }

  function render() {
    renderLists();
    updateStats();
  }

  function handleSubmit(event) {
    event.preventDefault();
    const formData = new FormData(form);
    const name = formData.get("name").trim();
    if (!name) {
      return;
    }

    const newGift = enhanceGift({
      id: cryptoRandomId(),
      name,
      recipient: formData.get("recipient"),
      category: formData.get("category"),
      priority: formData.get("priority"),
      price: normalizePrice(formData.get("price")),
      link: (formData.get("link") || "").trim(),
      notes: (formData.get("notes") || "").trim(),
      purchased: false,
      added: new Date().toISOString()
    });

    gifts.unshift(newGift);
    persistGifts();
    render();
    form.reset();
    form.querySelector("[name='name']").focus();
  }

  function handleReset() {
    const confirmed = window.confirm("Reset the registry to the starter list? This clears any custom items saved on this device.");
    if (!confirmed) {
      return;
    }
    gifts = defaultGifts.map((gift) => enhanceGift(gift));
    persistGifts();
    render();
  }

  function setupFeaturedFilters() {
    const filterButtons = document.querySelectorAll(".filter-btn");
    const cards = document.querySelectorAll("[data-featured-grid] .gift-card");

    function applyFilter(group) {
      cards.forEach((card) => {
        const groups = (card.dataset.groups || "").split(/\s+/);
        const show = group === "all" || groups.includes(group);
        card.style.display = show ? "flex" : "none";
      });
    }

    filterButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        filterButtons.forEach((button) => button.classList.remove("is-active"));
        btn.classList.add("is-active");
        applyFilter(btn.dataset.filter || "all");
      });
    });

    const activeButton = document.querySelector(".filter-btn.is-active");
    applyFilter(activeButton?.dataset.filter || "all");
  }

  function setupCountdown() {
    const countdownRoot = document.querySelector("[data-countdown]");
    if (!countdownRoot) {
      return;
    }

    const dayEl = countdownRoot.querySelector("[data-countdown-days]");
    const hourEl = countdownRoot.querySelector("[data-countdown-hours]");
    const minuteEl = countdownRoot.querySelector("[data-countdown-minutes]");

    function nextEventDate() {
      const now = new Date();
      const target = new Date(now.getFullYear(), 4, 24, 9, 0, 0); // May 24, 9 AM
      if (target.getTime() <= now.getTime()) {
        target.setFullYear(target.getFullYear() + 1);
      }
      return target;
    }

    let targetDate = nextEventDate();

    function tick() {
      const now = new Date();
      if (now.getTime() >= targetDate.getTime()) {
        targetDate = nextEventDate();
      }
      const diff = targetDate.getTime() - now.getTime();
      const minutes = Math.floor(diff / (1000 * 60));
      const days = Math.floor(minutes / (60 * 24));
      const hours = Math.floor((minutes - days * 24 * 60) / 60);
      const remainingMinutes = minutes % 60;
      dayEl.textContent = String(days).padStart(2, "0");
      hourEl.textContent = String(hours).padStart(2, "0");
      minuteEl.textContent = String(remainingMinutes).padStart(2, "0");
    }

    tick();
    setInterval(tick, 60000);
  }

  form.addEventListener("submit", handleSubmit);
  resetButton.addEventListener("click", handleReset);

  setupFeaturedFilters();
  setupCountdown();
  render();
})();
