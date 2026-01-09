"""
Content Preprocessing Service for AI Token Cost Reduction.

Phase 2.5 of V2 Architecture: Implements intelligent content preprocessing
to reduce AI token costs by approximately 93% through clean text extraction.

Processing Pipeline:
1. Extract headings for context preservation
2. Detect list/category pages that need structure preservation
3. Extract content (clean text or structured HTML)
4. Estimate token count
5. Truncate oversized content while preserving boundaries

Uses trafilatura for clean text extraction with BeautifulSoup fallback.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Optional dependency: trafilatura for clean text extraction
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not available, will use basic text extraction")

# Optional dependency: BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup, Comment
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("bs4 not available, structured HTML cleaning disabled")


class ContentType(str, Enum):
    """Content type returned by preprocessor."""
    CLEANED_TEXT = "cleaned_text"       # Main content extracted, minimal tokens
    STRUCTURED_HTML = "structured_html"  # Structure preserved for list pages
    RAW_HTML = "raw_html"               # Fallback when extraction fails


@dataclass
class PreprocessedContent:
    """Result of content preprocessing."""
    content_type: ContentType
    content: str
    token_estimate: int
    original_length: int
    headings: List[str] = field(default_factory=list)
    truncated: bool = False


class ContentPreprocessor:
    """
    Content preprocessing for AI token cost reduction.

    Uses trafilatura for clean text extraction (~93% token savings).
    Detects list pages and preserves structure when needed.
    Estimates tokens and truncates oversized content.
    """

    DEFAULT_MAX_TOKENS = 16000
    CHARS_PER_TOKEN_TEXT = 4
    CHARS_PER_TOKEN_HTML = 2

    # URL patterns indicating list/category pages
    LIST_PAGE_URL_PATTERNS = [
        r'/products?/',
        r'/category/',
        r'/categories/',
        r'/collection/',
        r'/collections/',
        r'/search/',
        r'/browse/',
        r'/catalog/',
        r'/shop/',
        r'/all-',
        r'\?.*page=',
        r'\?.*sort=',
        r'\?.*filter=',
    ]

    # Tags to remove completely during structured HTML cleaning
    REMOVE_TAGS = [
        'script', 'style', 'noscript', 'nav', 'footer', 'aside',
        'header', 'iframe', 'form', 'svg', 'canvas', 'video', 'audio',
    ]

    # Attributes to preserve during structured HTML cleaning
    PRESERVE_ATTRIBUTES = ['href', 'src', 'alt', 'title', 'data-product-id', 'data-sku']

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS):
        """
        Initialize ContentPreprocessor.

        Args:
            max_tokens: Maximum tokens to send to AI (default 16000)
        """
        self.max_tokens = max_tokens

    def preprocess(self, html_content: str, url: str = "") -> PreprocessedContent:
        """
        Main preprocessing method.

        Processes HTML content through the preprocessing pipeline:
        1. Extract headings for context
        2. Determine if structure should be preserved
        3. Extract content (clean text or structured HTML)
        4. Estimate tokens
        5. Truncate if needed

        Args:
            html_content: Raw HTML content to preprocess
            url: Optional URL for list page detection heuristics

        Returns:
            PreprocessedContent with appropriate content type
        """
        if not html_content:
            return PreprocessedContent(
                content_type=ContentType.RAW_HTML,
                content="",
                token_estimate=0,
                original_length=0,
                headings=[],
                truncated=False,
            )

        original_length = len(html_content)

        try:
            headings = self._extract_headings(html_content)
            preserve_structure = self._should_preserve_structure(html_content, headings, url)

            if preserve_structure:
                content = self._clean_structured_html(html_content)
                content_type = ContentType.STRUCTURED_HTML
            else:
                content = self._extract_clean_text(html_content, headings)
                content_type = ContentType.CLEANED_TEXT

            if not content or len(content.strip()) < 50:
                logger.warning("Content extraction produced minimal output, using fallback")
                content = self._basic_text_extract(html_content)
                content_type = ContentType.RAW_HTML

            token_estimate = self.estimate_tokens(content, content_type)
            truncated = False

            if token_estimate > self.max_tokens:
                content, truncated = self._truncate_content(content, content_type, self.max_tokens)
                token_estimate = self.estimate_tokens(content, content_type)

            return PreprocessedContent(
                content_type=content_type,
                content=content,
                token_estimate=token_estimate,
                original_length=original_length,
                headings=headings,
                truncated=truncated,
            )

        except Exception as e:
            logger.warning("Content preprocessing failed: %s, using fallback", str(e))
            fallback_content = self._basic_text_extract(html_content)
            fallback_content, truncated = self._truncate_content(
                fallback_content, ContentType.RAW_HTML, self.max_tokens
            )
            return PreprocessedContent(
                content_type=ContentType.RAW_HTML,
                content=fallback_content,
                token_estimate=self.estimate_tokens(fallback_content, ContentType.RAW_HTML),
                original_length=original_length,
                headings=[],
                truncated=truncated,
            )

    def _extract_headings(self, html: str) -> List[str]:
        """
        Extract h1, h2, h3 headings from HTML.

        Args:
            html: Raw HTML content

        Returns:
            List of heading text strings
        """
        headings = []

        if BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup.find_all(['h1', 'h2', 'h3']):
                    text = tag.get_text(separator=' ', strip=True)
                    if text and len(text) < 200:
                        headings.append(text)
            except Exception as e:
                logger.debug("BeautifulSoup heading extraction failed: %s", str(e))
        else:
            heading_pattern = re.compile(r'<h[123][^>]*>(.*?)</h[123]>', re.IGNORECASE | re.DOTALL)
            for match in heading_pattern.finditer(html):
                text = re.sub(r'<[^>]+>', ' ', match.group(1))
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) < 200:
                    headings.append(text)

        return headings[:20]

    def _should_preserve_structure(self, html: str, headings: List[str], url: str = "") -> bool:
        """
        Detect if this is a list/category page needing structure preservation.

        Uses heuristics:
        - Multiple h2/h3 headings (product listings)
        - Multiple table rows
        - Multiple list items with similar structure
        - URL patterns like /category/, /products/, /search/

        Args:
            html: Raw HTML content
            headings: Pre-extracted headings
            url: Optional URL for pattern matching

        Returns:
            True if structure should be preserved
        """
        if url:
            for pattern in self.LIST_PAGE_URL_PATTERNS:
                if re.search(pattern, url, re.IGNORECASE):
                    logger.debug("URL pattern match for list page: %s", pattern)
                    return True

        h2_h3_count = len([h for h in headings if h])
        if h2_h3_count > 5:
            logger.debug("Multiple headings detected (%d), preserving structure", h2_h3_count)
            return True

        tr_count = len(re.findall(r'<tr[^>]*>', html, re.IGNORECASE))
        if tr_count > 10:
            logger.debug("Multiple table rows detected (%d), preserving structure", tr_count)
            return True

        li_count = len(re.findall(r'<li[^>]*>', html, re.IGNORECASE))
        if li_count > 15:
            product_li_pattern = r'<li[^>]*>.*?(?:price|add.?to.?cart|\$|buy|shop).*?</li>'
            product_li_count = len(re.findall(product_li_pattern, html, re.IGNORECASE | re.DOTALL))
            if product_li_count > 5:
                logger.debug("Product list items detected (%d), preserving structure", product_li_count)
                return True

        product_card_patterns = [
            r'class=["\'][^"\']*product[^"\']*card[^"\']*["\']',
            r'class=["\'][^"\']*item[^"\']*product[^"\']*["\']',
            r'data-product-id',
            r'data-sku',
        ]
        product_card_count = 0
        for pattern in product_card_patterns:
            product_card_count += len(re.findall(pattern, html, re.IGNORECASE))
        if product_card_count > 5:
            logger.debug("Product cards detected (%d), preserving structure", product_card_count)
            return True

        return False

    def _extract_clean_text(self, html: str, headings: List[str]) -> str:
        """
        Extract clean text using trafilatura.

        Includes title/h1 if trafilatura output is missing them.
        Falls back to _basic_text_extract if trafilatura fails.

        Args:
            html: Raw HTML content
            headings: Pre-extracted headings for context

        Returns:
            Clean text content
        """
        if not TRAFILATURA_AVAILABLE:
            return self._basic_text_extract(html)

        try:
            extracted = trafilatura.extract(
                html,
                include_links=False,
                include_images=False,
                include_tables=True,
                output_format="txt",
            )

            if not extracted:
                logger.debug("trafilatura returned empty, using fallback")
                return self._basic_text_extract(html)

            prefix_parts = []
            if headings:
                first_heading = headings[0]
                if first_heading and first_heading.lower() not in extracted.lower()[:500]:
                    prefix_parts.append(first_heading)

            if BS4_AVAILABLE:
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    title_tag = soup.find('title')
                    if title_tag:
                        title_text = title_tag.get_text(separator=' ', strip=True)
                        if title_text and title_text not in prefix_parts:
                            if title_text.lower() not in extracted.lower()[:500]:
                                prefix_parts.insert(0, title_text)
                except Exception:
                    pass

            if prefix_parts:
                extracted = "\n".join(prefix_parts) + "\n\n" + extracted

            return extracted.strip()

        except Exception as e:
            logger.warning("trafilatura extraction failed: %s", str(e))
            return self._basic_text_extract(html)

    def _clean_structured_html(self, html: str) -> str:
        """
        Clean HTML while preserving structure for list pages.

        Removes:
        - script, style, noscript tags
        - nav, footer, aside, header (navigation)
        - comments
        - unnecessary attributes (onclick, style, class except structural)

        Preserves:
        - Product list structure
        - Links (for product URLs)
        - Essential semantic structure

        Args:
            html: Raw HTML content

        Returns:
            Cleaned structured HTML
        """
        if not BS4_AVAILABLE:
            cleaned = html
            for tag in self.REMOVE_TAGS:
                cleaned = re.sub(
                    rf'<{tag}[^>]*>.*?</{tag}>',
                    '',
                    cleaned,
                    flags=re.IGNORECASE | re.DOTALL
                )
            cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.strip()

        try:
            soup = BeautifulSoup(html, 'html.parser')

            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            for tag in soup.find_all(True):
                attrs_to_remove = []
                for attr in tag.attrs:
                    if attr not in self.PRESERVE_ATTRIBUTES:
                        if attr.startswith('on'):
                            attrs_to_remove.append(attr)
                        elif attr in ['style', 'class', 'id']:
                            if attr == 'class':
                                classes = tag.get('class', [])
                                useful_classes = [
                                    c for c in classes
                                    if any(kw in c.lower() for kw in ['product', 'item', 'card', 'price', 'name', 'title'])
                                ]
                                if useful_classes:
                                    tag['class'] = useful_classes
                                else:
                                    attrs_to_remove.append(attr)
                            else:
                                attrs_to_remove.append(attr)

                for attr in attrs_to_remove:
                    del tag[attr]

            cleaned = str(soup)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.strip()

        except Exception as e:
            logger.warning("BeautifulSoup cleaning failed: %s, using regex fallback", str(e))
            cleaned = html
            for tag in self.REMOVE_TAGS:
                cleaned = re.sub(
                    rf'<{tag}[^>]*>.*?</{tag}>',
                    '',
                    cleaned,
                    flags=re.IGNORECASE | re.DOTALL
                )
            cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.strip()

    def _basic_text_extract(self, html: str) -> str:
        """
        Fallback text extraction when trafilatura fails.

        Strips all tags, normalizes whitespace.

        Args:
            html: Raw HTML content

        Returns:
            Plain text content
        """
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#\d+;', '', text)
        text = re.sub(r'&\w+;', '', text)
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def estimate_tokens(self, content: str, content_type: ContentType) -> int:
        """
        Estimate token count for content.

        Uses different ratios for text vs HTML:
        - Clean text: ~4 characters per token
        - HTML: ~2 characters per token (more markup overhead)

        Args:
            content: Content to estimate tokens for
            content_type: Type of content

        Returns:
            Estimated token count
        """
        if not content:
            return 0

        if content_type == ContentType.CLEANED_TEXT:
            chars_per_token = self.CHARS_PER_TOKEN_TEXT
        else:
            chars_per_token = self.CHARS_PER_TOKEN_HTML

        return len(content) // chars_per_token

    def _truncate_content(
        self,
        content: str,
        content_type: ContentType,
        max_tokens: int
    ) -> Tuple[str, bool]:
        """
        Truncate content to max tokens.

        For text: tries to preserve complete sentences
        For HTML: truncates at tag boundaries

        Args:
            content: Content to truncate
            content_type: Type of content
            max_tokens: Maximum tokens allowed

        Returns:
            Tuple of (truncated_content, was_truncated)
        """
        if not content:
            return content, False

        current_tokens = self.estimate_tokens(content, content_type)
        if current_tokens <= max_tokens:
            return content, False

        if content_type == ContentType.CLEANED_TEXT:
            chars_per_token = self.CHARS_PER_TOKEN_TEXT
        else:
            chars_per_token = self.CHARS_PER_TOKEN_HTML

        target_chars = max_tokens * chars_per_token
        truncation_marker = "\n\n[Content truncated...]"
        marker_chars = len(truncation_marker)
        available_chars = target_chars - marker_chars

        if available_chars <= 0:
            return truncation_marker, True

        if content_type == ContentType.CLEANED_TEXT:
            truncated = content[:available_chars]
            sentence_end = max(
                truncated.rfind('. '),
                truncated.rfind('! '),
                truncated.rfind('? '),
                truncated.rfind('.\n'),
                truncated.rfind('!\n'),
                truncated.rfind('?\n'),
            )
            if sentence_end > available_chars // 2:
                truncated = truncated[:sentence_end + 1]
            return truncated.strip() + truncation_marker, True

        else:
            truncated = content[:available_chars]
            last_close_tag = truncated.rfind('>')
            if last_close_tag > available_chars // 2:
                truncated = truncated[:last_close_tag + 1]
            return truncated + truncation_marker, True


_preprocessor_instance: Optional[ContentPreprocessor] = None


def get_content_preprocessor(max_tokens: int = 16000) -> ContentPreprocessor:
    """
    Get or create ContentPreprocessor singleton.

    Args:
        max_tokens: Maximum tokens for preprocessing (only used on first call)

    Returns:
        ContentPreprocessor singleton instance
    """
    global _preprocessor_instance
    if _preprocessor_instance is None:
        _preprocessor_instance = ContentPreprocessor(max_tokens)
    return _preprocessor_instance


def reset_content_preprocessor() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _preprocessor_instance
    _preprocessor_instance = None
