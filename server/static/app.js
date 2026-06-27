// 仅在概览页运行自动刷新(其它页面不存在 #summary 容器,直接跳过)
const _summaryRoot = document.getElementById("summary");
if (_summaryRoot) {
  // 每 10 秒拉取概览数据并局部更新汇总数字
  async function refresh() {
    try {
      const ov = await (await fetch("/api/overview")).json();
      const s = ov.summary;
      // 更新 DOM 中各汇总数字
      const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };
      set("sum-total",   s.total);
      set("sum-up",      s.up);
      set("sum-down",    s.down);
      set("sum-unknown", s.unknown);
      set("sum-errors",  s.errors);
      set("sum-tunnels", ov.tunnels_online);
      // 同步更新页面标题
      document.title = `概览(${s.up}↑/${s.down}↓) · Monitor`;
    } catch (e) { /* 忽略瞬时网络错误 */ }
  }
  setInterval(refresh, 10000);
}

// 切换关注状态,调用 watch API 后刷新页面
async function toggleWatch(btn) {
  const mid = btn.dataset.mid;
  const next = btn.dataset.watched !== "true";
  await fetch(`/api/monitors/${mid}/watch`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({watched: next}),
  });
  location.reload();
}
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("watch-btn")) toggleWatch(e.target);
});
