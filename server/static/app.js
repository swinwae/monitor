// 每 10 秒刷新概览数字(简单整页轮询;DOM 局部更新留待后续增强)
async function refresh() {
  try {
    const ov = await (await fetch("/api/overview")).json();
    const s = ov.summary;
    document.title = `概览(${s.up}↑/${s.down}↓)· Monitor`;
  } catch (e) { /* 忽略瞬时网络错误 */ }
}
setInterval(refresh, 10000);

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
