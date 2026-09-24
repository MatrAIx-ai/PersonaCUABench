"""Real-Chrome regression for Health's visible links and eleven-tab requirement.

Uses static local HTML, with no model calls or task-site requests.
Run separately from the browser-free test_pipeline.py:
    .venv/bin/python odyssey/test_browser.py
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from run import Browser


def main():
    artifacts = Path(__file__).resolve().parent.parent / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="browser-test-", dir=artifacts) as profile:
        browser = Browser(
            headless=True, nav_timeout_ms=5000, profile_dir=profile, max_tabs=11
        )
        try:
            # These static fixtures have no network or asynchronous SPA content.
            browser._settle = lambda page: page.wait_for_load_state("domcontentloaded")
            html = """
                <title>Browser regression fixture</title>
                <button style="display:none"
                    onclick="document.getElementById('status').innerText='hidden-clicked'">
                    Schedule
                </button>
                <button onclick="document.getElementById('status').innerText='visible-clicked'">
                    Schedule
                </button>
                <p id="status">pending</p>
            """
            browser.open_tab("data:text/html," + quote(html))
            browser.click(1, "Schedule")
            assert browser._page(1).locator("#status").inner_text() == "visible-clicked"
            class UnreadyFrame:
                def get_by_text(self, *args, **kwargs):
                    raise AssertionError("Do not search an unready frame after finding a page control")

            original_frames = browser._visible_frames
            browser._visible_frames = lambda page: [page.main_frame, UnreadyFrame()]
            assert browser.click(1, "Schedule").startswith("clicked")
            browser._visible_frames = original_frames
            browser._page(1).set_content("""
                <p>Outer page</p>
                <iframe srcdoc='<p>Embedded class: Tuesday 10am</p>
                    <a href="https://example.org/classes">Real schedule</a>
                    <input id="title" aria-label="Document title">
                    <div contenteditable="true" id="editor"></div>'></iframe>
                <iframe style="display:none" srcdoc="<p>Hidden secret</p>"></iframe>
            """)
            browser._page(1).frame_locator("iframe").first.locator("#title").wait_for()
            assert "Embedded class: Tuesday 10am" in browser.read_page(1)
            assert "Hidden secret" not in browser.read_page(1)
            assert "https://example.org/classes" in browser.inspect_page(1)
            browser.type_text(1, "#title", "Test title")
            browser.type_text(1, "#editor", "Test document")
            browser.press_key(1, "#editor", "End")
            frame = browser._page(1).frames[1]
            assert frame.locator("#title").input_value() == "Test title"
            assert frame.locator("#editor").inner_text() == "Test document"
            for i in range(10):
                browser.open_tab("data:text/html," + quote(
                    f"<title>Source {i}</title><p>Source fixture {i}</p>"
                ))
            assert len(browser.open_tabs()) == 11
            assert "tab limit 11 reached" in browser.open_tab("data:text/html,extra")
        finally:
            browser.close()
    print("Chrome regression OK: visible links, embedded read/write, eleven tabs")


if __name__ == "__main__":
    main()
