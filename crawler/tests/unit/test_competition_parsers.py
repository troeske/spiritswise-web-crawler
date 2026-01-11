"""
Unit tests for competition parsers validation.

TDD tests for ensuring IWSC parser properly validates product names and
rejects producer/company names that are not actual products.
"""
import pytest

from crawler.discovery.competitions.parsers import IWSCParser


class TestIWSCParserValidation:
    """Tests for IWSC parser product name validation."""

    def test_iwsc_parser_rejects_winery_names(self):
        """Parser should skip entries that are just winery names."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Winery Gurjaani 2024</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-bronze-medal.png" alt="Bronze">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 0, "Winery names should be rejected"

    def test_iwsc_parser_rejects_company_names(self):
        """Parser should skip entries that are company names."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Spirits Company LLC</div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 0, "Company names should be rejected"

    def test_iwsc_parser_accepts_whiskey_products(self):
        """Parser should accept valid whiskey product names."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Glenfiddich 12 Year Old Single Malt Scotch Whisky</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-95-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Valid whiskey products should be accepted"
        assert results[0]["product_name"] == "Glenfiddich 12 Year Old Single Malt Scotch Whisky"

    def test_iwsc_parser_accepts_port_products(self):
        """Parser should accept valid port wine product names."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Taylor's 20 Year Old Tawny Port</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Valid port products should be accepted"
        assert "port" in results[0]["product_name"].lower()


class TestIWSCParserRejectPatterns:
    """Tests for specific rejection patterns."""

    def test_rejects_vineyard_names(self):
        """Parser should reject vineyard names."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Napa Valley Vineyard 2024</div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 0, "Vineyard names should be rejected"

    def test_rejects_distillery_only_names(self):
        """Parser should reject names that are just distillery names without product info."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Highland Distillery Ltd</div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 0, "Distillery-only names should be rejected"

    def test_rejects_inc_company_suffix(self):
        """Parser should reject names with Inc suffix."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Premium Spirits Inc</div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 0, "Inc company names should be rejected"

    def test_rejects_wine_cellar_names(self):
        """Parser should reject wine cellar names."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Old Wine Cellar Estate</div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 0, "Wine cellar names should be rejected"


class TestIWSCParserAcceptPatterns:
    """Tests for accepted MVP product patterns."""

    def test_accepts_bourbon(self):
        """Parser should accept bourbon products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Buffalo Trace Kentucky Straight Bourbon</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Bourbon products should be accepted"

    def test_accepts_scotch(self):
        """Parser should accept scotch products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Lagavulin 16 Year Old Islay Scotch</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Scotch products should be accepted"

    def test_accepts_single_malt(self):
        """Parser should accept single malt products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Highland Park 12 Year Single Malt</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-silver-medal.png" alt="Silver">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Single malt products should be accepted"

    def test_accepts_rye_whiskey(self):
        """Parser should accept rye whiskey products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Bulleit Straight Rye Whiskey</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Rye whiskey products should be accepted"

    def test_accepts_tawny_port(self):
        """Parser should accept tawny port products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Graham's 30 Year Old Tawny</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Tawny port products should be accepted"

    def test_accepts_ruby_port(self):
        """Parser should accept ruby port products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Fonseca Bin 27 Reserve Ruby</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-silver-medal.png" alt="Silver">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Ruby port products should be accepted"

    def test_accepts_vintage_port(self):
        """Parser should accept vintage port products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Dow's 2017 Vintage Port</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Vintage port products should be accepted"

    def test_accepts_lbv_port(self):
        """Parser should accept LBV (Late Bottled Vintage) port products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Taylor's 2016 LBV Port</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "LBV port products should be accepted"

    def test_accepts_colheita(self):
        """Parser should accept colheita port products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Niepoort 1997 Colheita</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Colheita port products should be accepted"

    def test_accepts_blended_whisky(self):
        """Parser should accept blended whisky products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Johnnie Walker Blue Label Blended</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Blended whisky products should be accepted"

    def test_accepts_porto(self):
        """Parser should accept porto products."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Sandeman 20 Year Porto</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Porto products should be accepted"


class TestIWSCParserRealWorldProducts:
    """Tests for real-world IWSC product names that don't contain explicit MVP keywords.

    These tests verify that products like "Glenfiddich 12 Year Old" are accepted
    even though they don't contain "whisky", "scotch", etc. in the name.
    The IWSC URL already filters for spirits (type=3), so we trust the source.
    """

    def test_accepts_glenfiddich_without_whisky_keyword(self):
        """Parser should accept 'Glenfiddich 12 Year Old' without 'whisky' in name."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Glenfiddich 12 Year Old</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Glenfiddich 12 Year Old should be accepted"
        assert results[0]["product_name"] == "Glenfiddich 12 Year Old"

    def test_accepts_macallan_without_whisky_keyword(self):
        """Parser should accept 'Macallan 18' without 'whisky' in name."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Macallan 18</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Macallan 18 should be accepted"

    def test_accepts_lagavulin_without_whisky_keyword(self):
        """Parser should accept 'Lagavulin 16' without 'whisky' in name."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Lagavulin 16</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Lagavulin 16 should be accepted"

    def test_accepts_yamazaki_without_whisky_keyword(self):
        """Parser should accept Japanese whisky 'Yamazaki 12' without 'whisky' in name."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Yamazaki 12</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Yamazaki 12 should be accepted"

    def test_accepts_makers_mark_without_bourbon_keyword(self):
        """Parser should accept 'Maker's Mark' without 'bourbon' in name."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Maker's Mark</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Maker's Mark should be accepted"

    def test_accepts_taylors_10_year_without_port_keyword(self):
        """Parser should accept 'Taylor's 10 Year' without 'port' in name."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Taylor's 10 Year</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        assert len(results) == 1, "Taylor's 10 Year should be accepted"

    def test_accepts_highland_park_12_year(self):
        """Parser should accept 'Highland Park 12 Year' (contains distillery but is valid)."""
        parser = IWSCParser()
        html = '''
        <div class="c-card--listing">
            <div class="c-card--listing__title">Highland Park 12 Year</div>
            <div class="c-card--listing__awards-wrapper">
                <img src="iwsc2024-gold-medal.png" alt="Gold">
            </div>
        </div>
        '''
        results = parser.parse(html, 2024)
        # This should pass because "Highland Park 12 Year" is a product name
        # not a distillery-only name like "Highland Distillery Ltd"
        assert len(results) == 1, "Highland Park 12 Year should be accepted"
