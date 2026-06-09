from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PageElement(BaseModel):
    ref: str
    role: str
    name: str
    tag: str = ""
    attributes: dict[str, str] = {}


class FormField(BaseModel):
    ref: str
    field_type: str
    name: str
    label: str
    value: str = ""
    options: list[str] = []
    required: bool = False
    placeholder: str = ""


class LinkInfo(BaseModel):
    ref: str
    text: str
    href: str


class PageContent(BaseModel):
    url: str
    title: str
    text_content: str
    elements: list[PageElement]
    forms: list[FormField]
    links: list[LinkInfo]
    meta: dict[str, str] = {}
    # Parsed JSON-LD blobs (<script type="application/ld+json">) — e-commerce
    # pages embed clean Product/Offer price + rating data here even when the
    # visible DOM is messy. See core/page_parser.py.
    structured_data: list[Any] = []
    timestamp: datetime
