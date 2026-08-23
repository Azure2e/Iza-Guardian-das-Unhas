(function () {
  var KEY = "encanto-theme";

  function preferred() {
    var saved = localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(mode) {
    document.documentElement.classList.toggle("dark", mode === "dark");
    localStorage.setItem(KEY, mode);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-label", mode === "dark" ? "Ativar modo claro" : "Ativar modo escuro");
      btn.textContent = mode === "dark" ? "☀️" : "🌙";
      btn.title = mode === "dark" ? "Modo claro" : "Modo escuro";
    });
  }

  apply(preferred());

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    var next = document.documentElement.classList.contains("dark") ? "light" : "dark";
    apply(next);
  });

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
    if (!localStorage.getItem(KEY)) apply(e.matches ? "dark" : "light");
  });
})();
