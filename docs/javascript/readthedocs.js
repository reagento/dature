// Inject RTD version selector into Material for MkDocs header.
// Uses the native Material .md-version component for consistent styling.
document.addEventListener(
  "readthedocs-addons-data-ready",
  function (event) {
    const config = event.detail.data();
    const versioning = `
      <div class="md-version">
        <button class="md-version__current" aria-label="Select version">
          ${config.versions.current.slug}
        </button>
        <ul class="md-version__list">
          ${config.versions.active.map(
            (version) => `
              <li class="md-version__item">
                <a href="${version.urls.documentation}" class="md-version__link">
                  ${version.slug}
                </a>
              </li>`
          ).join("\n")}
        </ul>
      </div>`;

    // Remove existing selector (happens with "Instant loading" navigation)
    const currentVersions = document.querySelector(".md-version");
    if (currentVersions !== null) {
      currentVersions.remove();
    }
    document.querySelector(".md-header__topic").insertAdjacentHTML("beforeend", versioning);
  }
);
