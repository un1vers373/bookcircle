// Небольшие улучшения: подтверждение опасных действий и индикатор загрузки.
(function () {
  var body = document.body;

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      e.preventDefault();
      return;
    }
    body.classList.add("loading");
    // блокируем кнопки после отправки, чтобы не отправить форму дважды
    setTimeout(function () {
      form.querySelectorAll("button[type=submit]").forEach(function (b) {
        if (!b.disabled) { b.disabled = true; b.dataset.lock = "1"; }
      });
    }, 0);
  });

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || a.target === "_blank" || e.metaKey || e.ctrlKey) return;
    var href = a.getAttribute("href");
    if (href && href.charAt(0) !== "#" && href.indexOf("javascript:") !== 0) body.classList.add("loading");
  });

  // при возврате по кнопке «Назад» страница берётся из кэша — снимаем блокировки
  window.addEventListener("pageshow", function () {
    body.classList.remove("loading");
    document.querySelectorAll("button[data-lock]").forEach(function (b) {
      b.disabled = false; delete b.dataset.lock;
    });
  });
})();
