// Build a version selector from RTD Addons API data and inject it into the
// shadcn header slot (#dature-version-select, docs/overrides/templates/version_select.html).
// This theme has no SPA instant-navigation, so a single injection on
// "readthedocs-addons-data-ready" is enough — no MutationObserver needed.

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

function renderOption(version, current) {
  const opt = document.createElement("option");
  opt.value = sanitizeUrl(version.urls.documentation);
  opt.textContent = version.slug;
  if (version.slug === current.slug) {
    opt.selected = true;
  }
  return opt;
}

function injectVersionSelector(config) {
  const container = document.getElementById("dature-version-select");
  if (container === null) {
    return;
  }

  const versions = latestPatchOnly(
    config.versions.active.filter((v) => !v.hidden)
  );
  const current = config.versions.current;

  const visible = versions.slice(0, MAX_VISIBLE);
  const older = versions.slice(MAX_VISIBLE);

  const select = document.createElement("select");
  select.setAttribute("aria-label", "Select version");

  if (older.length > 0) {
    const visibleGroup = document.createElement("optgroup");
    visibleGroup.label = "Versions";
    visible.forEach((v) => visibleGroup.appendChild(renderOption(v, current)));
    select.appendChild(visibleGroup);

    const olderGroup = document.createElement("optgroup");
    olderGroup.label = "Older versions";
    older.forEach((v) => olderGroup.appendChild(renderOption(v, current)));
    select.appendChild(olderGroup);
  } else {
    visible.forEach((v) => select.appendChild(renderOption(v, current)));
  }

  select.addEventListener("change", (event) => {
    window.location.href = event.target.value;
  });

  container.replaceChildren(select);
}

document.addEventListener("readthedocs-addons-data-ready", function (event) {
  injectVersionSelector(event.detail.data());
});
