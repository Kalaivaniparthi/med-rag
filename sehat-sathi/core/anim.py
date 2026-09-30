"""Retrieval animation: question -> bezier curves -> chunk cards -> answer. Pure inline SVG + CSS."""
import html
import re

CSS = """<style>
.rq{max-width:900px;margin:8px auto;font-family:sans-serif}
.rq-q{width:60%;margin:0 auto;padding:12px 18px;border-radius:24px;background:#0e7490;color:#fff;text-align:center;font-weight:600}
.rq svg{width:100%;height:90px;display:block}
.rq-l{fill:none;stroke:#0e7490;stroke-linecap:round;stroke-dasharray:1000;stroke-dashoffset:1000;animation:rq-draw .8s forwards}
.rq-l.done{animation:none;stroke-dashoffset:0}
.rq-g{display:grid;gap:12px;align-items:start}
.rq-c{border:1px solid #94a3b8;border-radius:12px;padding:10px;background:#f8fafc;color:#0f172a;font-size:13px;opacity:.35}
.rq-c summary{cursor:pointer}
.rq-c.lift{animation:rq-lift .4s forwards}
.rq-c.up{opacity:1;transform:translateY(-6px);border-color:#0e7490;box-shadow:0 8px 20px rgba(14,116,144,.35)}
.rq-a{margin-top:18px;padding:14px;border-radius:12px;background:#ecfeff;color:#0f172a;border-left:4px solid #0e7490}
.rq-a.fade{animation:rq-fade .6s}
@keyframes rq-draw{to{stroke-dashoffset:0}}
@keyframes rq-lift{to{opacity:1;transform:translateY(-6px);border-color:#0e7490;box-shadow:0 8px 20px rgba(14,116,144,.35)}}
@keyframes rq-fade{from{opacity:0}to{opacity:1}}
</style>"""


def render_retrieval_animation(question, chunks, answer, stage=4):
    """HTML for one animation frame. stage: 0 faded cards, 1 curves draw, 2 cards lift,
    3 answer fades in, 4 final (static, used for chat history)."""
    n = max(len(chunks), 1)
    xs = [int((2 * i + 1) / (2 * n) * 900) for i in range(len(chunks))]
    lines = "".join(
        f'<path class="rq-l{" done" if stage >= 2 else ""}" vector-effect="non-scaling-stroke" '
        f'stroke-width="{1 + 8 * c["score"]:.1f}" d="M450 0 C450 60 {x} 30 {x} 90"/>'
        for c, x in zip(chunks, xs)) if stage >= 1 else ""
    card_cls = {0: "", 1: "", 2: " lift"}.get(stage, " up")
    cards = "".join(
        f'<div class="rq-c{card_cls}"><details><summary><b>📄 {html.escape(c["source_file"])} · p.{c["page"]}</b>'
        f' · {c["score"]:.0%}<br><small>{html.escape(c["raw_chunk"][:110])}…</small></summary>'
        f'<p>{html.escape(c["raw_chunk"]).replace(chr(10), "<br>")}</p></details></div>' for c in chunks)
    ans = ""
    if stage >= 3:
        body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(answer)).replace("\n", "<br>")
        ans = f'<div class="rq-a{" fade" if stage == 3 else ""}">{body}</div>'
    return (f'{CSS}<div class="rq"><div class="rq-q">🗣️ {html.escape(question)}</div>'
            f'<svg viewBox="0 0 900 90" preserveAspectRatio="none">{lines}</svg>'
            f'<div class="rq-g" style="grid-template-columns:repeat({n},1fr)">{cards}</div>{ans}</div>')
