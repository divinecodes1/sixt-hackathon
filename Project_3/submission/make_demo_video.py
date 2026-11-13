#!/usr/bin/env python3
"""Build submission/demo.mp4 (about 60 s, 1920x1080, no audio) from the live demo UI and the slides.

Every verdict shown is produced live by the real final_judge.py on claude-haiku-4.5 through demo/server.py; nothing is
staged. The script only clicks, waits for the real answer, adds a caption bar and takes a screenshot per scene.

Needs: a running demo server with the current code (python3 Project_3/demo/server.py --port 8766), Playwright for
Python with the system Chrome, and an ffmpeg binary (imageio-ffmpeg works):
    python3 make_demo_video.py --url http://127.0.0.1:8766
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = "J1D-0022"  # dev case: "as long as the branch is still open" dropped; caught in both shipped runs


def caption(page, text: str) -> None:
    page.evaluate("""t => {
        let d = document.getElementById('__cap');
        if (!d) { d = document.createElement('div'); d.id = '__cap'; document.body.appendChild(d); }
        d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;background:rgba(20,20,20,.88);color:#fff;' +
          'font:600 22px Arial,sans-serif;padding:14px 28px;border-top:4px solid #ff5f00';
        d.textContent = t; }""", text)


def shot(page, frames: list, path: str, seconds: float) -> None:
    page.screenshot(path=path)
    frames.append((path, seconds))


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default=os.path.join(HERE, "demo.mp4"))
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="demo_frames_")
    frames: list[tuple[str, float]] = []
    slides = "file://" + os.path.join(HERE, "slides.html")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5)

        def slide(i: int, seconds: float, text: str | None = None) -> None:
            page.goto(slides)
            page.evaluate("i => window.scrollTo(0, document.querySelectorAll('section')[i].offsetTop)", i)
            if text:
                caption(page, text)
            shot(page, frames, f"{tmp}/s{i}.png", seconds)

        slide(0, 7, "The problem: AI judges miss small edits that turn a reply into a promise the company cannot keep.")
        slide(1, 6)

        # ---- live: a labelled harmful edit, judged reply by reply
        page.goto(a.url)
        page.wait_for_selector("#list .case")
        page.select_option("#f-type", "condition_removal")
        page.select_option("#f-lang", "en")
        page.click(f'#list .case[data-id="{CASE}"]')
        page.wait_for_selector("#go")
        caption(page, "Live demo, real claude-haiku-4.5: the edited reply drops “as long as the branch is still open”.")
        shot(page, frames, f"{tmp}/l1.png", 7)
        page.click("#go")
        page.wait_for_selector("#outcome .outcome", timeout=240_000)
        page.evaluate("document.querySelector('#outcome').scrollIntoView({block: 'center'})")
        verdict = page.inner_text("#outcome b")
        caption(page, "Each reply is judged on its own, never the pair. Original passes, edited reply fails: caught.")
        shot(page, frames, f"{tmp}/l2.png", 8)
        page.evaluate("""() => {  // the edited reply's evidence: the condition call 1 marked as dropped, and call 2's confirm
            const els = [...document.querySelectorAll('#traces *')].filter(e => e.children.length === 0 &&
                /^(dropped:|#\\d+ confirmed)/.test(e.textContent.trim()));
            (els.find(e => /dropped/.test(e.textContent)) || els[0])?.scrollIntoView({block: 'start'});
            window.scrollBy(0, -90); }""")
        caption(page, "Why: call 1 marks the policy condition as dropped; call 2 confirms only by quoting the reply's exact words.")
        shot(page, frames, f"{tmp}/l3.png", 8)

        # ---- live: your own reply
        page.click('.seg button[data-mode="custom"]')
        page.click('#presets button[data-preset="guarantee"]')
        page.click("#go")
        page.wait_for_function("() => /complete|stopped/.test(document.querySelector('#live-status').textContent)",
                               timeout=240_000)
        page.locator("#traces").scroll_into_view_if_needed()
        status = page.inner_text("#live-status")
        caption(page, "Any reply: “You can always extend your rental, guaranteed” → " + status)
        shot(page, frames, f"{tmp}/l4.png", 7)

        page.click('button[data-view="results"]')
        page.wait_for_timeout(1500)
        caption(page, "Measured with score.py on dev, grouped 3-fold cross-validation.")
        shot(page, frames, f"{tmp}/l5.png", 5)

        slide(3, 8)
        slide(4, 6)
        browser.close()

    print("live outcome:", verdict, "| custom reply:", status)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for path, sec in frames:
            f.write(f"file '{path}'\nduration {sec}\n")
        f.write(f"file '{frames[-1][0]}'\n")  # concat demuxer: last image needs repeating
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white,"
                           "fps=30,format=yuv420p",
                    "-t", str(sum(sec for _, sec in frames)),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart", a.out], check=True)
    print(f"wrote {a.out} ({os.path.getsize(a.out) / 1e6:.1f} MB, {sum(s for _, s in frames):.0f} s); frames in {tmp}")


if __name__ == "__main__":
    main()
