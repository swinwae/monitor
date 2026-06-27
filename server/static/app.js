// 每 10 秒刷新概览数字(简单整页轮询;DOM 局部更新留待后续增强)
async function refresh() {
  try {
    const ov = await (await fetch("/api/overview")).json();
    const s = ov.summary;
    document.title = `概览(${s.up}↑/${s.down}↓)· Monitor`;
  } catch (e) { /* 忽略瞬时网络错误 */ }
}
setInterval(refresh, 10000);
