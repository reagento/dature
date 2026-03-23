// Build a version selector from RTD API data and inject it into the Material header.
// HTML structure matches Material's native renderVersionSelector output.

const MAX_VISIBLE = 10;

function escapeHtml(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

function sanitizeUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return escapeHtml(parsed.href);
    }
  } catch {
    // invalid URL
  }
  return "#";
}

// Keep only the latest patch for each major.minor group.
// Non-semver slugs (stable, latest, branches) are always kept.
function latestPatchOnly(versions) {
  const semverRe = /^v?(\d+)\.(\d+)\.(\d+)$/;
  const best = new Map();

  for (const v of versions) {
    const m = v.slug.match(semverRe);
    if (!m) continue;
    const key = `${m[1]}.${m[2]}`;
    const patch = parseInt(m[3], 10);
    const prev = best.get(key);
    if (!prev || patch > prev.patch) {
      best.set(key, { version: v, patch });
    }
  }

  const kept = new Set(Array.from(best.values()).map((e) => e.version.slug));
  return versions.filter((v) => !semverRe.test(v.slug) || kept.has(v.slug));
}

function renderVersionItem(version) {
  return `
    <li class="md-version__item">
      <a href="${sanitizeUrl(version.urls.documentation)}" class="md-version__link">
        ${escapeHtml(version.slug)}
      </a>
    </li>`;
}

// Cached HTML fragments, built once from RTD data
let versioningHtml = "";
let olderItemsHtml = "";

function injectVersionSelector() {
  if (versioningHtml === "") {
    return;
  }

  const topic = document.querySelector(".md-header__topic");
  if (topic === null) {
    return;
  }

  // Remove existing selector (previous from instant loading)
  const existing = topic.querySelector(".md-version");
  if (existing !== null) {
    existing.remove();
  }
  topic.insertAdjacentHTML("beforeend", versioningHtml);

  // "older versions…" expands the list inline
  const toggle = topic.querySelector(".md-version__show-older");
  if (toggle !== null) {
    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      const li = toggle.closest(".md-version__item");
      li.insertAdjacentHTML("afterend", olderItemsHtml);
      li.remove();
    });
  }
}

document.addEventListener("readthedocs-addons-data-ready", function (event) {
  const config = event.detail.data();
  const versions = latestPatchOnly(
    config.versions.active.filter((v) => !v.hidden)
  );
  const current = config.versions.current;

  const visible = versions.slice(0, MAX_VISIBLE);
  const older = versions.slice(MAX_VISIBLE);

  let olderToggle = "";
  olderItemsHtml = older.map(renderVersionItem).join("\n");

  if (older.length > 0) {
    olderToggle = `
        <li class="md-version__item">
          <span class="md-version__link md-version__show-older">
            older versions…
          </span>
        </li>`;
  }

  versioningHtml = `
      <div class="md-version">
        <button class="md-version__current" aria-label="Select version">
          ${escapeHtml(current.slug)}
        </button>
        <ul class="md-version__list">
          ${visible.map(renderVersionItem).join("\n")}
          ${olderToggle}
        </ul>
      </div>`;

  injectVersionSelector();
});

// Re-inject after Material instant navigation replaces the DOM
document.addEventListener("DOMContentLoaded", function () {
  if (typeof document.body.dataset.mdColorScheme === "undefined") {
    return;
  }
  new MutationObserver(function () {
    const topic = document.querySelector(".md-header__topic");
    if (topic !== null && topic.querySelector(".md-version") === null) {
      injectVersionSelector();
    }
  }).observe(document.querySelector(".md-header__topic") || document.body, {
    childList: true,
    subtree: true,
  });
});
