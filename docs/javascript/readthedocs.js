// Replace Material for MkDocs version selector data with RTD versions.
// Material creates the .md-version component (via extra.version.provider: mike),
// but can't load versions.json on RTD. This script fills in the actual data.
// HTML structure matches Material's native renderVersionSelector output.

const MAX_VISIBLE = 10;

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
      <a href="${version.urls.documentation}" class="md-version__link">
        ${version.slug}
      </a>
    </li>`;
}

document.addEventListener(
  "readthedocs-addons-data-ready",
  function (event) {
    const config = event.detail.data();
    const versions = latestPatchOnly(
      config.versions.active.filter((v) => !v.hidden)
    );
    const current = config.versions.current;

    const visible = versions.slice(0, MAX_VISIBLE);
    const older = versions.slice(MAX_VISIBLE);

    let olderToggle = "";
    const olderItems = older.map(renderVersionItem).join("\n");

    if (older.length > 0) {
      olderToggle = `
        <li class="md-version__item">
          <span class="md-version__link md-version__show-older">
            older versions…
          </span>
        </li>`;
    }

    const versioning = `
      <div class="md-version">
        <button class="md-version__current" aria-label="Select version">
          ${current.slug}
        </button>
        <ul class="md-version__list">
          ${visible.map(renderVersionItem).join("\n")}
          ${olderToggle}
        </ul>
      </div>`;

    // Remove existing selector (Material's empty one or previous from instant loading)
    const existing = document.querySelector(".md-version");
    if (existing !== null) {
      existing.remove();
    }
    document
      .querySelector(".md-header__topic")
      .insertAdjacentHTML("beforeend", versioning);

    // "older versions…" expands the list inline
    const toggle = document.querySelector(".md-version__show-older");
    if (toggle) {
      toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        const li = toggle.closest(".md-version__item");
        li.insertAdjacentHTML("afterend", olderItems);
        li.remove();
      });
    }
  }
);
