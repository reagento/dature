// Replace Material for MkDocs version selector data with RTD versions.
// Material creates the .md-version component (via extra.version.provider: mike),
// but can't load versions.json on RTD. This script fills in the actual data.
document.addEventListener(
  "readthedocs-addons-data-ready",
  function (event) {
    const config = event.detail.data();

    // Find "stable" version or fall back to current
    const stableVersion = config.versions.active.find(
      (v) => v.slug === "stable"
    );
    const displayName = stableVersion ? "stable" : config.versions.current.slug;

    const versioning = `
      <div class="md-version">
        <button class="md-version__current" aria-label="Select version">
          ${displayName}
        </button>
        <ul class="md-version__list">
          ${config.versions.active
            .filter((version) => !version.hidden)
            .map(
              (version) => `
              <li class="md-version__item">
                <a href="${version.urls.documentation}" class="md-version__link">
                  ${version.slug}
                </a>
              </li>`
            )
            .join("\n")}
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
  }
);
