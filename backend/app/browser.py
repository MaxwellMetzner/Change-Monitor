from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image
from playwright.async_api import Browser, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, async_playwright

from .comparator import image_average_hash, normalize_text, text_hash
from .storage import write_bytes_artifact, write_text_artifact


SELECTOR_SCRIPT = """
() => {
  const maxElements = 420;
  const pageArea = Math.max(document.documentElement.scrollWidth * document.documentElement.scrollHeight, 1);

  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\\\$&");
  }

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (style.visibility === "hidden" || style.display === "none" || Number(style.opacity) === 0) return false;
    if (rect.width < 6 || rect.height < 6) return false;
    if (rect.width * rect.height > pageArea * 0.92) return false;
    return true;
  }

  function uniqueCount(selector) {
    try { return document.querySelectorAll(selector).length; }
    catch { return 9999; }
  }

  function selectorFor(el) {
    const attrNames = ["data-testid", "data-test", "data-cy", "aria-label", "name"];
    if (el.id) {
      const selector = `#${cssEscape(el.id)}`;
      if (uniqueCount(selector) === 1) return { selector, count: 1, quality: "strong" };
    }
    for (const attr of attrNames) {
      const value = el.getAttribute(attr);
      if (!value) continue;
      const selector = `${el.tagName.toLowerCase()}[${attr}="${String(value).replaceAll('"', '\\"')}"]`;
      const count = uniqueCount(selector);
      if (count === 1) return { selector, count, quality: "strong" };
    }
    const parts = [];
    let current = el;
    while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.body) {
      let part = current.tagName.toLowerCase();
      if (current.classList.length > 0) {
        part += "." + Array.from(current.classList).slice(0, 2).map(cssEscape).join(".");
      }
      const siblings = Array.from(current.parentElement ? current.parentElement.children : []);
      const sameTag = siblings.filter((item) => item.tagName === current.tagName);
      if (sameTag.length > 1) {
        const index = sameTag.indexOf(current) + 1;
        part += `:nth-of-type(${index})`;
      }
      parts.unshift(part);
      const selector = parts.join(" > ");
      const count = uniqueCount(selector);
      if (count === 1 && parts.length > 1) return { selector, count, quality: parts.length > 4 ? "fragile" : "ok" };
      current = current.parentElement;
    }
    const fallback = parts.join(" > ") || el.tagName.toLowerCase();
    return { selector: fallback, count: uniqueCount(fallback), quality: "fragile" };
  }

  const interestingTags = new Set(["BUTTON", "A", "SELECT", "INPUT", "TEXTAREA", "LABEL", "SUMMARY", "SPAN", "STRONG"]);
  const statusTerms = /stock|available|cart|buy|price|sold|ticket|appointment|reserve|checkout|pre.?order|unavailable|notify/i;
  const elements = Array.from(document.querySelectorAll("body *"))
    .filter(isVisible)
    .map((el) => {
      const text = (el.innerText || el.getAttribute("aria-label") || el.getAttribute("value") || "").replace(/\\s+/g, " ").trim();
      const rect = el.getBoundingClientRect();
      const tag = el.tagName;
      const visibleChildren = Array.from(el.children).filter(isVisible);
      const leaf = visibleChildren.length === 0;
      const interesting = interestingTags.has(tag) || statusTerms.test(text);
      return { el, text, rect, tag, interesting, leaf, area: rect.width * rect.height };
    })
    .filter((item) => item.text.length > 0 && item.text.length < 1200)
    .sort((a, b) => {
      if (a.interesting !== b.interesting) return a.interesting ? -1 : 1;
      if (a.leaf !== b.leaf) return a.leaf ? -1 : 1;
      return a.area - b.area;
    })
    .slice(0, maxElements);

  return elements.map((item) => {
    const selector = selectorFor(item.el);
    const label = item.text.length > 80 ? `${item.text.slice(0, 77)}...` : item.text;
    return {
      selector: selector.selector,
      tag: item.tag.toLowerCase(),
      label,
      text: item.text,
      rect: {
        x: item.rect.left + window.scrollX,
        y: item.rect.top + window.scrollY,
        width: item.rect.width,
        height: item.rect.height
      },
      match_count: selector.count,
      selector_quality: selector.quality
    };
  });
}
"""

VISIBLE_TEXT_SCRIPT = """
() => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  const hiddenSelectors = ["script", "style", "noscript", "template", "svg"];
  for (const selector of hiddenSelectors) {
    document.querySelectorAll(selector).forEach((el) => el.remove());
  }
  return document.body ? document.body.innerText : "";
}
"""


@dataclass
class CaptureTarget:
    monitor_id: int
    url: str
    mode: str
    selector: str | None = None
    wait_ms: int = 1500
    viewport_width: int = 1440
    viewport_height: int = 1200


@dataclass
class SnapshotCapture:
    final_url: str | None
    page_title: str | None
    http_status: int | None
    raw_text_path: str
    normalized_text_path: str
    html_snippet_path: str
    screenshot_path: str
    element_screenshot_path: str | None
    text_hash: str
    visual_hash: str | None
    metadata: dict[str, Any]


class BrowserService:
    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)

    async def stop(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def browser(self) -> Browser:
        if self._browser is None:
            await self.start()
        if self._browser is None:
            raise RuntimeError("Browser failed to start")
        return self._browser

    async def _new_page(self, viewport_width: int, viewport_height: int):
        browser = await self.browser()
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            user_agent="ChangeMonitor/1.0 (+self-hosted availability watcher)",
        )
        page = await context.new_page()
        return context, page

    async def _goto(self, page, url: str, wait_ms: int):  # type: ignore[no-untyped-def]
        response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_load_state("networkidle", timeout=max(1000, min(wait_ms + 1000, 8000)))
        except PlaywrightTimeoutError:
            pass
        if wait_ms:
            await page.wait_for_timeout(wait_ms)
        return response

    async def load_preview(
        self,
        url: str,
        *,
        wait_ms: int = 1500,
        viewport_width: int = 1440,
        viewport_height: int = 1200,
    ) -> dict[str, Any]:
        context, page = await self._new_page(viewport_width, viewport_height)
        try:
            response = await self._goto(page, url, wait_ms)
            screenshot = await page.screenshot(full_page=True, type="png", animations="disabled")
            image = Image.open(BytesIO(screenshot))
            elements = await page.evaluate(SELECTOR_SCRIPT)
            text = await page.evaluate(VISIBLE_TEXT_SCRIPT)
            return {
                "url": url,
                "final_url": page.url,
                "page_title": await page.title(),
                "http_status": response.status if response else None,
                "screenshot_base64": base64.b64encode(screenshot).decode("ascii"),
                "screenshot_width": image.width,
                "screenshot_height": image.height,
                "elements": elements,
                "captured_text": text[:10000],
            }
        finally:
            await context.close()

    async def select_element(self, url: str, selector: str, *, wait_ms: int = 1500) -> dict[str, Any]:
        context, page = await self._new_page(1440, 1200)
        try:
            await self._goto(page, url, wait_ms)
            try:
                await page.wait_for_selector(selector, state="attached", timeout=max(3000, wait_ms + 1000))
            except PlaywrightTimeoutError:
                pass
            locator = page.locator(selector)
            count = await locator.count()
            if count == 0:
                return {"selector": selector, "text": "", "html": "", "match_count": 0, "rect": None, "screenshot_base64": None}
            element = locator.first
            text = (await element.inner_text(timeout=5000)).strip()
            html = await element.evaluate("(el) => el.outerHTML")
            rect = await element.bounding_box()
            screenshot = await element.screenshot(type="png", animations="disabled")
            return {
                "selector": selector,
                "text": text,
                "html": html[:12000],
                "match_count": count,
                "rect": rect,
                "screenshot_base64": base64.b64encode(screenshot).decode("ascii"),
            }
        finally:
            await context.close()

    async def capture_snapshot(self, target: CaptureTarget) -> SnapshotCapture:
        context, page = await self._new_page(target.viewport_width, target.viewport_height)
        try:
            response = await self._goto(page, target.url, target.wait_ms)
            selector_found = True
            match_count = 0
            html_snippet = ""
            selected_text = ""
            element_screenshot_path = None
            element_visual_hash = None

            if target.selector and target.mode in {"element_text", "element_visual", "bad_state"}:
                try:
                    await page.wait_for_selector(target.selector, state="attached", timeout=max(3000, target.wait_ms + 1000))
                    if target.wait_ms:
                        await page.wait_for_timeout(min(target.wait_ms, 5000))
                except PlaywrightTimeoutError:
                    pass
                locator = page.locator(target.selector)
                match_count = await locator.count()
                selector_found = match_count > 0
                if selector_found:
                    element = locator.first
                    try:
                        await element.scroll_into_view_if_needed(timeout=5000)
                    except PlaywrightError:
                        pass
                    selected_text = (await element.inner_text(timeout=5000)).strip()
                    html_snippet = await element.evaluate("(el) => el.outerHTML")
                    element_bytes = await element.screenshot(type="png", animations="disabled")
                    element_screenshot_path = write_bytes_artifact("elements", target.monitor_id, element_bytes)
                    element_visual_hash = image_average_hash(element_bytes)
            else:
                selected_text = await page.evaluate(VISIBLE_TEXT_SCRIPT)
                html_snippet = await page.evaluate("() => document.body ? document.body.outerHTML.slice(0, 30000) : ''")

            if not selected_text:
                selected_text = await page.evaluate(VISIBLE_TEXT_SCRIPT)
            normalized = normalize_text(selected_text)
            screenshot_bytes = await page.screenshot(full_page=True, type="png", animations="disabled")
            screenshot_path = write_bytes_artifact("pages", target.monitor_id, screenshot_bytes)
            visual_hash = element_visual_hash or image_average_hash(screenshot_bytes)

            raw_text_path = write_text_artifact("raw", target.monitor_id, selected_text)
            normalized_text_path = write_text_artifact("normalized", target.monitor_id, normalized)
            html_snippet_path = write_text_artifact("html", target.monitor_id, html_snippet[:30000], ".html")

            metadata = {
                "selector": target.selector,
                "selector_found": selector_found,
                "match_count": match_count,
                "mode": target.mode,
                "javascript_rendered": True,
            }
            return SnapshotCapture(
                final_url=page.url,
                page_title=await page.title(),
                http_status=response.status if response else None,
                raw_text_path=raw_text_path,
                normalized_text_path=normalized_text_path,
                html_snippet_path=html_snippet_path,
                screenshot_path=screenshot_path,
                element_screenshot_path=element_screenshot_path,
                text_hash=text_hash(normalized),
                visual_hash=visual_hash,
                metadata=metadata,
            )
        finally:
            await context.close()


browser_service = BrowserService()
