// pymdownx.tabbed (alternate_style) renders a stack of radio inputs, labels
// and content blocks (docs/stylesheets/extra.css has the layout). The theme
// has no tab support, so this drives which label/block is active from the
// checked radio, using plain nth-of-type index matching.

function syncTabs(tabbedSet) {
  const inputs = tabbedSet.querySelectorAll(":scope > input");
  const labels = tabbedSet.querySelectorAll(":scope > .tabbed-labels > label");
  const blocks = tabbedSet.querySelectorAll(":scope > .tabbed-content > .tabbed-block");

  inputs.forEach((input, i) => {
    labels[i]?.classList.toggle("active", input.checked);
    blocks[i]?.classList.toggle("active", input.checked);
  });
}

document.querySelectorAll(".tabbed-set").forEach((tabbedSet) => {
  syncTabs(tabbedSet);
  tabbedSet.addEventListener("change", () => syncTabs(tabbedSet));
});
