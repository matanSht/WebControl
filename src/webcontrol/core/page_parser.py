import logging
from datetime import UTC, datetime

from playwright.async_api import Locator, Page

from webcontrol.config import Settings
from webcontrol.core.session_manager import BrowserSession
from webcontrol.models.page import FormField, LinkInfo, PageContent, PageElement
from webcontrol.observability.timing import Timer

logger = logging.getLogger("webcontrol.parser")

INTERACTIVE_SELECTOR = (
    "a[href], button, input, select, textarea, "
    "[role='button'], [role='link'], [role='checkbox'], [role='radio'], "
    "[role='switch'], [role='tab'], [role='menuitem'], [role='option'], "
    "[role='combobox'], [role='searchbox'], [role='slider'], [role='spinbutton']"
)


class PageParser:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def parse(self, session: BrowserSession) -> PageContent:
        with Timer() as t:
            page = session.page
            ref_counter = _RefCounter()
            ref_map: dict[str, Locator] = {}

            elements = await self._extract_interactive_elements(page, ref_counter, ref_map)
            forms = await self._extract_forms(page, ref_counter, ref_map)
            links = await self._extract_links(page, ref_counter, ref_map)
            text_content = await self._extract_text(page)
            title = await page.title()
            meta = await self._extract_meta(page)
            structured_data = await self._extract_structured_data(page)

            session.ref_map = ref_map

        logger.debug(
            "parse url=%s elements=%d forms=%d links=%d refs=%d duration_ms=%.1f",
            page.url, len(elements), len(forms), len(links), len(ref_map), t.elapsed_ms,
        )

        return PageContent(
            url=page.url,
            title=title,
            text_content=text_content,
            elements=elements,
            forms=forms,
            links=links,
            meta=meta,
            structured_data=structured_data,
            timestamp=datetime.now(UTC),
        )

    async def _extract_interactive_elements(
        self,
        page: Page,
        counter: "_RefCounter",
        ref_map: dict[str, Locator],
    ) -> list[PageElement]:
        elements: list[PageElement] = []
        locators = page.locator(INTERACTIVE_SELECTOR)
        count = await locators.count()

        for i in range(min(count, self._settings.max_interactive_elements)):
            el = locators.nth(i)
            try:
                is_visible = await el.is_visible()
                if not is_visible:
                    continue

                info = await el.evaluate(
                    """e => ({
                        tag: e.tagName.toLowerCase(),
                        role: e.getAttribute('role') || '',
                        name: e.getAttribute('aria-label')
                            || e.innerText?.trim().substring(0, 80)
                            || e.getAttribute('title')
                            || e.getAttribute('placeholder')
                            || e.getAttribute('name')
                            || '',
                        type: e.getAttribute('type') || '',
                        href: e.getAttribute('href') || '',
                        value: e.value || '',
                        disabled: e.disabled || false,
                        checked: e.checked,
                    })"""
                )

                role = info["role"] or self._infer_role(info["tag"], info["type"])
                name = info["name"]
                if not name:
                    continue

                ref = counter.next()
                ref_map[ref] = el

                attrs: dict[str, str] = {}
                if info["href"]:
                    attrs["href"] = info["href"][:200]
                if info["type"]:
                    attrs["type"] = info["type"]
                if info["value"]:
                    attrs["value"] = info["value"][:100]
                if info["disabled"]:
                    attrs["disabled"] = "true"
                if info["checked"] is not None and info["checked"] is not False:
                    attrs["checked"] = str(info["checked"]).lower()

                elements.append(PageElement(
                    ref=ref,
                    role=role,
                    name=name,
                    tag=info["tag"],
                    attributes=attrs,
                ))
            except Exception:
                continue

        return elements

    def _infer_role(self, tag: str, type_attr: str) -> str:
        if tag == "a":
            return "link"
        if tag == "button":
            return "button"
        if tag == "select":
            return "combobox"
        if tag == "textarea":
            return "textbox"
        if tag == "input":
            type_map = {
                "checkbox": "checkbox",
                "radio": "radio",
                "submit": "button",
                "button": "button",
                "search": "searchbox",
                "range": "slider",
                "number": "spinbutton",
            }
            return type_map.get(type_attr, "textbox")
        return "generic"

    async def _extract_forms(
        self,
        page: Page,
        counter: "_RefCounter",
        ref_map: dict[str, Locator],
    ) -> list[FormField]:
        fields: list[FormField] = []
        field_locators = page.locator("input, select, textarea")
        count = await field_locators.count()

        for i in range(min(count, self._settings.max_form_fields)):
            el = field_locators.nth(i)
            try:
                is_visible = await el.is_visible()
                if not is_visible:
                    continue

                info = await el.evaluate(
                    """e => {
                        const tag = e.tagName.toLowerCase();
                        let label = '';
                        if (e.labels && e.labels.length) label = e.labels[0].textContent.trim();
                        else if (e.id) {
                            const lbl = document.querySelector('label[for="' + e.id + '"]');
                            if (lbl) label = lbl.textContent.trim();
                        }
                        if (!label) label = e.getAttribute('aria-label') || e.getAttribute('placeholder') || '';
                        return {
                            tag,
                            type: e.getAttribute('type') || (tag === 'select' ? 'select' : 'text'),
                            name: e.getAttribute('name') || '',
                            label,
                            value: tag !== 'select' ? (e.value || '') : '',
                            required: e.required || false,
                            placeholder: e.getAttribute('placeholder') || '',
                            options: tag === 'select' ? Array.from(e.options).map(o => o.textContent.trim()) : [],
                        }
                    }"""
                )

                ref = counter.next()
                ref_map[ref] = el

                fields.append(FormField(
                    ref=ref,
                    field_type=info["type"],
                    name=info["name"],
                    label=info["label"],
                    value=info["value"],
                    options=info["options"],
                    required=info["required"],
                    placeholder=info["placeholder"],
                ))
            except Exception:
                continue

        return fields

    async def _extract_links(
        self,
        page: Page,
        counter: "_RefCounter",
        ref_map: dict[str, Locator],
    ) -> list[LinkInfo]:
        links: list[LinkInfo] = []
        link_locators = page.locator("a[href]")
        count = await link_locators.count()

        for i in range(min(count, self._settings.max_links)):
            el = link_locators.nth(i)
            try:
                is_visible = await el.is_visible()
                if not is_visible:
                    continue

                text = (await el.inner_text()).strip()
                href = await el.get_attribute("href") or ""
                if not text and not href:
                    continue

                ref = counter.next()
                ref_map[ref] = el
                links.append(LinkInfo(ref=ref, text=text[:100], href=href[:200]))
            except Exception:
                continue

        return links

    async def _extract_text(self, page: Page) -> str:
        try:
            text = await page.inner_text("body")
            text = " ".join(text.split())
            return text[: self._settings.max_text_content_chars]
        except Exception:
            return ""

    async def _extract_meta(self, page: Page) -> dict[str, str]:
        try:
            return await page.evaluate(
                """() => {
                    const meta = {};
                    const grab = (sel, key) => {
                        const el = document.querySelector(sel);
                        if (el && el.content) meta[key] = el.content;
                    };
                    grab('meta[name="description"]', 'description');
                    grab('meta[property="og:title"]', 'og:title');
                    grab('meta[property="og:description"]', 'og:description');
                    grab('meta[property="og:type"]', 'og:type');
                    grab('meta[property="og:price:amount"]', 'og:price:amount');
                    grab('meta[property="og:price:currency"]', 'og:price:currency');
                    grab('meta[property="product:price:amount"]', 'product:price:amount');
                    grab('meta[property="product:price:currency"]', 'product:price:currency');
                    // Microdata expressed as meta tags (e.g. <meta itemprop="price" content="9.99">).
                    document.querySelectorAll('meta[itemprop][content]').forEach((m) => {
                        const k = 'itemprop:' + m.getAttribute('itemprop');
                        if (!(k in meta)) meta[k] = m.getAttribute('content');
                    });
                    return meta;
                }"""
            )
        except Exception:
            return {}

    async def _extract_structured_data(self, page: Page) -> list:
        """Collect and parse JSON-LD blobs — clean Product/Offer data many
        e-commerce pages embed even when the visible DOM is hard to scrape."""
        try:
            return await page.evaluate(
                """({ maxBlobs, maxChars }) => {
                    const out = [];
                    const nodes = document.querySelectorAll(
                        'script[type="application/ld+json"]'
                    );
                    for (const n of nodes) {
                        if (out.length >= maxBlobs) break;
                        const raw = n.textContent || '';
                        if (!raw || raw.length > maxChars) continue;
                        try {
                            out.push(JSON.parse(raw));
                        } catch (e) {
                            /* skip malformed JSON-LD */
                        }
                    }
                    return out;
                }""",
                {
                    "maxBlobs": self._settings.structured_data_max_blobs,
                    "maxChars": self._settings.structured_data_max_chars,
                },
            )
        except Exception:
            return []


class _RefCounter:
    def __init__(self) -> None:
        self._count = 0

    def next(self) -> str:
        self._count += 1
        return f"e{self._count}"
