"""
Integration Test Configuration.

API credentials and endpoints for true end-to-end testing.
"""
import os

# ScrapingBee Configuration - Task 3 fix: Use environment variable instead of hardcoded key
SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY', '')
SCRAPINGBEE_BASE_URL = "https://app.scrapingbee.com/api/v1/"

# AI Enhancement Service Configuration (VPS)
AI_SERVICE_HOST = "167.235.75.199"
AI_SERVICE_PORT = 8002  # External port via nginx
AI_SERVICE_BASE_URL = f"http://{AI_SERVICE_HOST}:{AI_SERVICE_PORT}"
AI_SERVICE_USERNAME = "integration_test"
AI_SERVICE_PASSWORD = "testpass123"

# Rate Limiting
SCRAPINGBEE_REQUESTS_PER_HOUR = 3000
REQUEST_DELAY_SECONDS = 1.5  # Conservative delay between requests

# Test Sources - Using The Whisky Exchange for reliable URLs
IWSC_WHISKEY_SOURCES = [
    # The Whisky Exchange - verified working product URLs
    {"name": "Ardbeg 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/66/ardbeg-10-year-old", "medal": "gold"},
    {"name": "Lagavulin 16 Year Old", "url": "https://www.thewhiskyexchange.com/p/72/lagavulin-16-year-old", "medal": "gold"},
    {"name": "Laphroaig 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/68/laphroaig-10-year-old", "medal": "gold"},
    {"name": "Talisker 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/75/talisker-10-year-old", "medal": "gold"},
    {"name": "Highland Park 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/128/highland-park-12-year-old", "medal": "silver"},
    {"name": "Glenmorangie Original 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/207/glenmorangie-the-original-10-year-old", "medal": "silver"},
    {"name": "Glenfiddich 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/104/glenfiddich-12-year-old", "medal": "silver"},
    {"name": "Macallan 12 Year Old Sherry Oak", "url": "https://www.thewhiskyexchange.com/p/1150/the-macallan-12-year-old-sherry-oak", "medal": "silver"},
    {"name": "Balvenie 12 Year Old DoubleWood", "url": "https://www.thewhiskyexchange.com/p/79/the-balvenie-12-year-old-doublewood", "medal": "silver"},
    {"name": "Oban 14 Year Old", "url": "https://www.thewhiskyexchange.com/p/167/oban-14-year-old", "medal": "gold"},
    {"name": "Bunnahabhain 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/191/bunnahabhain-12-year-old", "medal": "gold"},
    {"name": "Bruichladdich The Classic Laddie", "url": "https://www.thewhiskyexchange.com/p/23856/bruichladdich-the-classic-laddie", "medal": "silver"},
    {"name": "Dalmore 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/94/the-dalmore-12-year-old", "medal": "silver"},
    {"name": "Aberlour 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/77/aberlour-12-year-old-double-cask", "medal": "silver"},
    {"name": "Springbank 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/177/springbank-10-year-old", "medal": "gold"},
    {"name": "Caol Ila 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/88/caol-ila-12-year-old", "medal": "gold"},
    {"name": "Bowmore 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/84/bowmore-12-year-old", "medal": "silver"},
    {"name": "Kilchoman Machir Bay", "url": "https://www.thewhiskyexchange.com/p/20091/kilchoman-machir-bay", "medal": "silver"},
    {"name": "Craigellachie 13 Year Old", "url": "https://www.thewhiskyexchange.com/p/30671/craigellachie-13-year-old", "medal": "silver"},
    {"name": "Glenallachie 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/45911/glenallachie-10-year-old", "medal": "gold"},
    {"name": "Benriach The Twelve", "url": "https://www.thewhiskyexchange.com/p/51321/benriach-the-twelve", "medal": "silver"},
    {"name": "Glen Scotia 15 Year Old", "url": "https://www.thewhiskyexchange.com/p/27981/glen-scotia-15-year-old", "medal": "gold"},
    {"name": "Tobermory 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/180/tobermory-12-year-old", "medal": "silver"},
    {"name": "Cragganmore 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/91/cragganmore-12-year-old", "medal": "silver"},
    {"name": "Glendronach 12 Year Old", "url": "https://www.thewhiskyexchange.com/p/107/the-glendronach-12-year-old", "medal": "gold"},
]

SFWSC_WHISKEY_SOURCES = [
    # American Whiskey from The Whisky Exchange - verified URLs
    {"name": "Buffalo Trace", "url": "https://www.thewhiskyexchange.com/p/15620/buffalo-trace-bourbon", "medal": "double_gold"},
    {"name": "Eagle Rare 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/1236/eagle-rare-10-year-old", "medal": "gold"},
    {"name": "Blanton's Original", "url": "https://www.thewhiskyexchange.com/p/2356/blantons-original", "medal": "double_gold"},
    {"name": "Elijah Craig Small Batch", "url": "https://www.thewhiskyexchange.com/p/4411/elijah-craig-small-batch", "medal": "gold"},
    {"name": "Woodford Reserve", "url": "https://www.thewhiskyexchange.com/p/1070/woodford-reserve-bourbon", "medal": "gold"},
    {"name": "Wild Turkey 101", "url": "https://www.thewhiskyexchange.com/p/1057/wild-turkey-101-bourbon", "medal": "gold"},
    {"name": "Four Roses Single Barrel", "url": "https://www.thewhiskyexchange.com/p/3927/four-roses-single-barrel", "medal": "double_gold"},
    {"name": "Maker's Mark", "url": "https://www.thewhiskyexchange.com/p/1036/makers-mark-bourbon", "medal": "gold"},
    {"name": "Bulleit Bourbon", "url": "https://www.thewhiskyexchange.com/p/7109/bulleit-bourbon", "medal": "silver"},
    {"name": "Knob Creek 9 Year Old", "url": "https://www.thewhiskyexchange.com/p/1033/knob-creek-9-year-old", "medal": "gold"},
    {"name": "Michter's US1 Bourbon", "url": "https://www.thewhiskyexchange.com/p/28481/michters-us1-small-batch-bourbon", "medal": "double_gold"},
    {"name": "Rittenhouse Rye", "url": "https://www.thewhiskyexchange.com/p/15657/rittenhouse-straight-rye-100-proof", "medal": "gold"},
    {"name": "Sazerac Rye", "url": "https://www.thewhiskyexchange.com/p/2353/sazerac-straight-rye", "medal": "gold"},
    {"name": "Bulleit Rye", "url": "https://www.thewhiskyexchange.com/p/21451/bulleit-95-rye", "medal": "silver"},
    {"name": "Jack Daniel's Single Barrel", "url": "https://www.thewhiskyexchange.com/p/11389/jack-daniels-single-barrel-select", "medal": "gold"},
    {"name": "Evan Williams Single Barrel", "url": "https://www.thewhiskyexchange.com/p/3928/evan-williams-single-barrel-vintage", "medal": "gold"},
    {"name": "Old Grand-Dad 114", "url": "https://www.thewhiskyexchange.com/p/1034/old-grand-dad-114-bourbon", "medal": "gold"},
    {"name": "Booker's Bourbon", "url": "https://www.thewhiskyexchange.com/p/10091/bookers-bourbon", "medal": "double_gold"},
    {"name": "1792 Small Batch", "url": "https://www.thewhiskyexchange.com/p/9871/1792-small-batch-bourbon", "medal": "gold"},
    {"name": "Angel's Envy", "url": "https://www.thewhiskyexchange.com/p/25511/angels-envy-bourbon", "medal": "double_gold"},
    {"name": "Old Forester 1920", "url": "https://www.thewhiskyexchange.com/p/38681/old-forester-1920-prohibition-style", "medal": "double_gold"},
    {"name": "Russell's Reserve 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/15660/russells-reserve-10-year-old", "medal": "gold"},
    {"name": "Wild Turkey Rare Breed", "url": "https://www.thewhiskyexchange.com/p/1059/wild-turkey-rare-breed", "medal": "gold"},
    {"name": "Jim Beam Double Oak", "url": "https://www.thewhiskyexchange.com/p/26216/jim-beam-double-oak", "medal": "silver"},
    {"name": "Rebel Yell Single Barrel", "url": "https://www.thewhiskyexchange.com/p/43813/rebel-yell-single-barrel-10-year-old", "medal": "gold"},
]

IWSC_PORT_WINE_SOURCES = [
    # Port Wine from The Whisky Exchange - verified URLs
    {"name": "Graham's 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18663/grahams-10-year-old-tawny-port", "medal": "gold"},
    {"name": "Graham's 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/81463/grahams-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Graham's 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18665/grahams-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Graham's 40 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18434/grahams-40-year-old-tawny-port", "medal": "gold"},
    {"name": "Taylor's 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18440/taylors-10-year-old-tawny-port", "medal": "gold"},
    {"name": "Taylor's 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18441/taylors-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Dow's 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18403/dows-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Dow's 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18404/dows-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Fonseca 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18406/fonseca-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Fonseca 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18407/fonseca-20-year-old-tawny-port", "medal": "silver"},
    {"name": "Warre's Otima 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18448/warres-otima-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Sandeman 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18431/sandeman-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Sandeman 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18432/sandeman-20-year-old-tawny-port", "medal": "silver"},
    {"name": "Graham's The Tawny", "url": "https://www.thewhiskyexchange.com/p/7682/grahams-the-tawny-port", "medal": "bronze"},
    {"name": "Taylor's Late Bottled Vintage", "url": "https://www.thewhiskyexchange.com/p/18446/taylors-late-bottled-vintage-port-2019", "medal": "silver"},
    {"name": "Dow's Late Bottled Vintage", "url": "https://www.thewhiskyexchange.com/p/18402/dows-late-bottled-vintage-port-2019", "medal": "silver"},
    {"name": "Fonseca Bin 27", "url": "https://www.thewhiskyexchange.com/p/18408/fonseca-bin-no27-port", "medal": "bronze"},
    {"name": "Graham's Six Grapes", "url": "https://www.thewhiskyexchange.com/p/18413/grahams-six-grapes-port", "medal": "gold"},
    {"name": "Croft Pink Port", "url": "https://www.thewhiskyexchange.com/p/16890/croft-pink-port", "medal": "silver"},
    {"name": "Warre's Warrior", "url": "https://www.thewhiskyexchange.com/p/18450/warres-warrior-reserve-port", "medal": "bronze"},
    {"name": "Sandeman Founders Reserve", "url": "https://www.thewhiskyexchange.com/p/18429/sandeman-founders-reserve-port", "medal": "bronze"},
    {"name": "Niepoort Ruby Dum", "url": "https://www.thewhiskyexchange.com/p/18424/niepoort-ruby-dum-port", "medal": "gold"},
    {"name": "Kopke 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18418/kopke-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Kopke 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18419/kopke-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Ramos Pinto Quinta da Ervamoira 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/18427/ramos-pinto-quinta-da-ervamoira-10-year-old-tawny-port", "medal": "silver"},
]

DWWA_PORT_WINE_SOURCES = [
    # More Port Wine from The Whisky Exchange - verified URLs
    {"name": "Graham's 50 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/84158/grahams-50-year-old-tawny-port", "medal": "best_in_show"},
    {"name": "Taylor's 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18442/taylors-30-year-old-tawny-port", "medal": "platinum"},
    {"name": "Taylor's 40 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18443/taylors-40-year-old-tawny-port", "medal": "platinum"},
    {"name": "Dow's 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18405/dows-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Fonseca 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/21553/fonseca-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Fonseca 40 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/21554/fonseca-40-year-old-tawny-port", "medal": "gold"},
    {"name": "Sandeman 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18433/sandeman-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Warre's 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/62281/warres-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Niepoort 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18422/niepoort-10-year-old-tawny-port", "medal": "gold"},
    {"name": "Niepoort 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18423/niepoort-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Niepoort 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/35523/niepoort-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Kopke 30 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18420/kopke-30-year-old-tawny-port", "medal": "gold"},
    {"name": "Kopke 40 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18421/kopke-40-year-old-tawny-port", "medal": "gold"},
    {"name": "Quinta do Noval Late Bottled Vintage", "url": "https://www.thewhiskyexchange.com/p/18426/quinta-do-noval-late-bottled-vintage-port-2018", "medal": "silver"},
    {"name": "Quinta do Vesuvio Vintage 2019", "url": "https://www.thewhiskyexchange.com/p/81464/quinta-do-vesuvio-vintage-2019", "medal": "gold"},
    {"name": "Croft 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18399/croft-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Croft 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18400/croft-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Burmester 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18395/burmester-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Burmester 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18396/burmester-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Churchill's 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18397/churchills-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Churchill's 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18398/churchills-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Quinta do Noval 10 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/18425/quinta-do-noval-10-year-old-tawny-port", "medal": "silver"},
    {"name": "Quinta do Noval 20 Year Old Tawny", "url": "https://www.thewhiskyexchange.com/p/42123/quinta-do-noval-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Ramos Pinto Quinta de Ervamoira 20 Year Old", "url": "https://www.thewhiskyexchange.com/p/18428/ramos-pinto-quinta-de-ervamoira-20-year-old-tawny-port", "medal": "gold"},
    {"name": "Ferreira Quinta do Porto 10 Year Old", "url": "https://www.thewhiskyexchange.com/p/24571/ferreira-quinta-do-porto-10-year-old-tawny-port", "medal": "silver"},
]

# All sources combined
ALL_TEST_SOURCES = {
    "iwsc_whiskey": IWSC_WHISKEY_SOURCES,
    "sfwsc_whiskey": SFWSC_WHISKEY_SOURCES,
    "iwsc_port": IWSC_PORT_WINE_SOURCES,
    "dwwa_port": DWWA_PORT_WINE_SOURCES,
}

TOTAL_PRODUCTS = sum(len(sources) for sources in ALL_TEST_SOURCES.values())
