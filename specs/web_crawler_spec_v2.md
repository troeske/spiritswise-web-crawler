# **Web Crawler Architecture Specification: Whiskey & Port Wine Database**

Version: 2.3.0 (Comprehensive/Resilient)

Date: 2025-12-27

Status: Approved for Implementation

Author: AI Enhancement Engine Team

## **Executive Summary**

This document specifies the architecture for a state-of-the-art web crawler system designed to build the world's most comprehensive whiskey and port wine database. It addresses specific industry challenges such as age verification gates, anti-bot protections, and the legal preservation of editorial content.

**Key Architectural Decisions:**

1. **Hybrid Push-Pull Discovery:** Combines standard crawling with active "Prestige-Led" discovery (hunting for award winners).  
2. **Smart Access Layer:** A multi-tiered fetching strategy (Cookies \-\> Headless \-\> API) to handle age gates cost-effectively.  
3. **Content Resilience:** A "Summarize, Archive & Link" strategy to mitigate link rot for editorial content.  
4. **Data Separation:** Strict separation between structured "Product Data" (facts) and unstructured "Article Data" (narrative).

---

## **1\. Architecture Overview**

### **1.1 System Context Diagram**

The architecture is designed as a pipeline that ingests URLs from multiple discovery sources, routes them through the appropriate fetching engine, and processes the content into two distinct data streams: Products and Articles.

graph TD
    subgraph "External World"
        A[Retailers & Aggregators]
        B[Producer Websites]
        C[Competition Results]
    end

    subgraph "Discovery Layer"
        D[SerpAPI / Google]
        E[Link Graph Mapper]
    end

    subgraph "Web Crawler Layer"
        Fhttps://redis.io/docs/latest/get-started/
        G[Smart Router]
        H[Fetching Engines]
        I[httpx - Cookies]
        J[Playwright - Headless]
        K[ScrapingBee - API]
    end

    subgraph "Preservation & AI"
        L[AI Extraction - LLM]
        M[Wayback Machine - Archive]
        N[cold Storage TBD]
    end

    subgraph "Storage"
        O[PostgreSQL Database]
    end

    %% Connections
    A & B & C --> D
    A --> E
    D --> F
    E --> F
    F --> G
    
    %% Router Logic
    G --> H
    H --> I
    H --> J
    H --> K

    %% Data Flow
    I & J & K --> L
    L --> N
    L --> M
    L --> O

### **1.2 Design Principles**

1. **Cookie-First Entry:** Always attempt to bypass age gates via HTTP headers before resorting to resource-intensive headless browsers.  
2. **Prestige-First Discovery:** Prioritize crawling bottles that have won awards, as these are high-value targets for users.  
3. **Backlink Discovery:** Use major retailers (Hubs) to discover Producer Official Sites (Spokes).  
4. **Content Separation:** Strictly separate "Products" (facts/specs) from "Articles" (reviews/history) to manage copyright and data structure effectively.

---

## **2\. Age Verification & Compliance Strategy**

95% of target sites enforce an "Age Gate" (overlay or separate page). Standard crawlers will fail here.

### **2.1 Level 1: Cookie Injection (The 70% Solution)**

Most sites check for a specific cookie to allow access. We inject these into every request header.

* **Strategy:** Middleware applies a dictionary of known bypass cookies.  
* **Implementation:** We inject keys like "age\_verified": "true", "dob": "1990-01-01", "birth\_date": "1990-01-01", "legal\_drinking\_age": "1", "over18": "1".

### **2.2 Level 2: Semantic Interaction (The 30% Solution)**

For sites requiring active clicking (e.g., "Enter Site" buttons), we use a lightweight Playwright script.

* **Trigger:** If the fetched content length is less than 500 characters OR contains keywords like "Legal Drinking Age".  
* **Solver:**  
  1. Scan DOM for buttons/links.  
  2. Match text against whitelist: "Yes", "Enter", "I am 18+", "Confirm", "Agree".  
  3. Click and wait for navigation.  
  4. **Persist:** Save the resulting session cookies to Redis for future requests to this domain.

---

## **3\. Technology Stack & Services**

### **3.1 Fetching Engines (Hybrid Approach)**

We use a tiered approach to balance cost and capability.

**Tier 1 (Base)**

* **Technology:** httpx \+ http2  
* **Use Case:** Static sites, blogs, open APIs.  
* **Cost:** Free

**Tier 2 (Headless)**

* **Technology:** Playwright (Python)  
* **Use Case:** JS-rendered sites, complex age gates.  
* **Cost:** Server CPU

**Tier 3 (Premium)**

* **Technology:** ScrapingBee  
* **Use Case:** Evasive sites (Cloudflare, Akamai), IP bans.  
* **Cost:** $49/mo  
* **Decision:** Selected because it handles proxies, headless browsing, and CAPTCHA solving in a single API call, reducing engineering overhead.

### **3.2 3rd Party Services**

* **SerpAPI:** Google Search API. Essential for finding producer sites and new releases ($75/mo).  
* **Wayback Machine API:** For public archiving of editorial content (Free).  
* **OpenAI API (GPT-4o-mini):** For cost-effective extraction and summarization (\~$60/mo).

### **3.3 Core Python Libraries**

* httpx\[http2\]==0.27.0 (Async HTTP client)  
* playwright==1.40.0 (Headless browser automation)  
* beautifulsoup4==4.12.3 (HTML parsing)  
* scrapingbee-python==1.1.2 (Tier 3 fetching)  
* waybackpy==3.0.6 (Archiving interface)  
* langchain==0.1.0 (Structured extraction logic)  
* tenacity==8.2.3 (Retry logic)  
* celery==5.3.6 (Distributed task queue)

---

## **4\. Source Discovery & Configuration**

Finding all relevant sites requires a proactive, multi-channel approach.

### **4.1 Method A: The "Hub & Spoke" (Retailer Driven)**

We crawl "Hubs" (Aggregators/Large Retailers) to find "Spokes" (Producers).

1. **Crawl Hub:** Visit sites like [thewhiskyexchange.com/brands](https://www.google.com/search?q=https://thewhiskyexchange.com/brands), whiskybase.com, masterofmalt.com.  
2. **Extract:** Parse the list of Brand Names and any "External Links" to producer sites.  
3. **Search:** If no link exists, query SerpAPI: "{Brand Name} official site whisky".  
4. **Verify & Store:** Validate the domain and add it to the CrawlerSource database.

### **4.2 Method B: Prestige-Led Discovery (Competition Driven)**

**Rationale:** Award-winning bottles are high-signal and high-demand. We actively hunt for them.

**The Workflow:**

1. **Ingest Results:** Systematically crawl results pages of major competitions (IWSC, SFWSC, World Whiskies Awards) for the last 5 years.  
2. **Extract Winners:** Parse lists to get specific bottle names (e.g., "Glendronach 15 Year Old Revival").  
3. **Check Database:**  
   * If exists: Tag product with the award details.  
   * If missing: Create a "Skeleton Product" record.  
4. Active Search Loop (The "Hunter"):  
   For every "Skeleton Product", the system triggers 3 targeted searches via SerpAPI:  
   * **Buying:** "{Product Name} price buy online" \-\> Finds Retailers.  
   * **Tasting:** "{Product Name} review tasting notes" \-\> Finds Blogs/Articles.  
   * **Official:** "{Product Name} official site" \-\> Finds Producer Page.  
5. **Queue Sources:** The top results are added to the URL Frontier with **High Priority**.

### **4.3 Source Categories**

We classify sources to apply the correct extraction logic.

* **Retailer:** Focus on Price, Stock Status, ABV, Bottle Volume.  
* **Producer:** Focus on Official Notes, History, Production Specs, Heritage.  
* **Article/Review:** Focus on **High-Fidelity Taste Profiles**, Narrative, Sentiment.  
  * *Note:* Editorial articles are a primary source for "Taste" data. Extraction must look for sensory keywords (Nose, Palate, Finish) within long-form text blocks.

---

## **5\. Database Models**

### **5.1 Crawler Source Configuration**

The CrawlerSource model includes specific fields for age verification:

* **age\_gate\_type:** Choices include 'none', 'cookie', 'click', 'form'.  
* **age\_gate\_cookies:** A JSON field to store specific cookies (e.g., {'dob': '1990-01-01'}).  
* **discovery\_method:** Tracks how we found the source ('hub', 'search', 'manual').

### **5.2 Article Model (New)**

Dedicated storage for editorial content to support the preservation strategy:

* **source:** ForeignKey to CrawlerSource.  
* **original\_url:** The URL of the article.  
* **summary\_bullets:** JSON field for the AI-generated summary (Public Safe).  
* **tags:** JSON field for detected topics/flavors.  
* **s3\_snapshot\_path:** Path to the raw HTML stored privately in S3.  
* **wayback\_url:** The permanent Archive.org link.  
* **is\_live:** Boolean to track if the original link is still valid.

---

## **6\. Pipeline Architecture**

### **6.1 The "Smart Router" Flow**

The fetch\_content task dynamically selects the best tool for the job.

1. **Check Difficulty:** Look up domain difficulty in CrawlerSource.  
2. **Attempt Tier 1:** Try httpx with injected cookies.  
   * If Success: Return content.  
   * If Fail (403/Redirect): Escalate to Tier 2\.  
3. **Attempt Tier 2:** Try Playwright with click-solver logic.  
   * If Success: Return content & save cookies.  
   * If Fail (Timeout/Block): Escalate to Tier 3\.  
4. **Attempt Tier 3:** Use ScrapingBee API.  
   * If Success: Return content.  
   * *Note:* Mark domain as "Requires Tier 3" to skip lower tiers next time.

### **6.2 The "Hunter" Loop (Active Discovery)**

A specialized Celery worker queue for "Prestige-Led" discovery tasks.

* **Input:** List of Award-Winning Product Names.  
* **Process:**  
  1. Perform 3x SerpAPI queries per product.  
  2. Filter results (ignore known blocklists like Wikipedia/Amazon).  
  3. Push valid URLs to the generic URL Frontier with **Priority \= 10** (Highest).  
* **Outcome:** Rapid population of high-value bottle data.

---

## **7\. Link Rot Mitigation Strategy**

We cannot legally host scraped articles, and linking directly is fragile. We use a **"Summarize, Archive & Link"** strategy.

### **7.1 Preservation Pipeline**

1. **Fetch & Snapshot:** Download HTML and immediately upload to a private S3 bucket (Cold Storage). This ensures we always have the raw text for AI processing, even if the site dies tomorrow.  
2. **Public Archiving (Async):** Submit the URL to the Internet Archive's "Save Page Now" API via waybackpy.  
3. **Display Layer:** The frontend displays an "Article Card" containing:  
   * Metadata (Title, Source, Date).  
   * AI Summary (3-5 bullet points).  
   * **"Read Original"** button (Target: original\_url).  
   * **"View Archived Copy"** button (Target: wayback\_url \- only shown if original is dead).

### **7.2 Link Health Monitor**

A weekly Celery task (check\_dead\_links) iterates through CrawledArticle entries:

1. Sends a HEAD request to original\_url.  
2. If 404 or 500:  
   * Set is\_live \= False.  
   * Frontend automatically swaps the primary action to the Archive Link.

---

## **8\. Scalability & Cost**

### **8.1 3rd Party Cost Analysis**

* **SerpAPI:** $75/mo (Discovery \- Essential for finding new producer sites and specific award winners).  
* **ScrapingBee:** $49/mo (Hard Scraping \- Cheaper than engineering custom bypasses for 500+ unique age gates).  
* **OpenAI API:** \~$60/mo (Extraction \- Batch processing of tasting notes & summaries).  
* **S3 / MinIO:** \~$5/mo (Snapshots \- Cheap storage for HTML snapshots).  
* **Hetzner VPS:** $7/mo (Hosting \- Existing infrastructure).  
* **Total:** \~$196/mo

### **8.2 Scale Targets**

* **Phase 1:** 2,000 Producer Sites, 10,000 Articles.  
* **Throughput:** \~10,000 requests/day (polite rate limiting).

---

## **9\. Implementation Roadmap**

### **Phase 1: Foundation** 

* \[ \] Setup Django \+ Celery \+ Redis infrastructure.  
* \[ \] Implement Age Gate Middleware (Cookie injection).  
* \[ \] Integrate SerpAPI client.

### **Phase 2: Prestige Discovery** 

* \[ \] Crawl Competition Results: IWSC, SFWSC.  
* \[ \] Implement "The Hunter": Build the active search loop.  
* \[ \] Seed DB with award-winning "Skeleton Products".

### **Phase 3: Content & Archiving** 

* \[ \] Implement CrawledArticle model and pipeline.  
* \[ \] Integrate waybackpy for archiving.  
* \[ \] Setup S3 bucket for private snapshots.

### **Phase 4: AI & UI** 

* \[ \] Connect fetched content to AI Summarizer.  
* \[ \] Build Frontend "Article Card" with Archive fallbacks.  
* \[ \] Verify "Taste Profile" extraction accuracy from long-form articles.

