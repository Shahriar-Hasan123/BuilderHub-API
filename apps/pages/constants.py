ALLOWED_TAGS = [
    # Text
    "p", "br", "span", "strong", "b", "em", "i", "u", "s",
    # Headings
    "h1", "h2", "h3", "h4", "h5", "h6",
    # Lists
    "ul", "ol", "li",
    # Links & Media
    "a", "img",
    # Quotes / Code
    "blockquote", "code", "pre",
    # Tables
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    # Containers
    "div",
    # Horizontal separator
    "hr",
]


ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel",],
    "img": ["src", "alt", "title", "width", "height",],
    "table": ["border",],
    "td": ["colspan", "rowspan",],
    "th": [ "colspan", "rowspan",],
}

ALLOWED_PROTOCOLS = ["http", "https", "data"]
