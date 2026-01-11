flowchart TB
      subgraph Trigger["⏰ Trigger (Celery Beat)"]
          CB[check_due_schedules<br/>every 5 min]
      end

      subgraph Init["🚀 Initialization"]
          QS[Query CrawlSchedule<br/>category=COMPETITION<br/>next_run ≤ now]
          CJ[Create CrawlJob<br/>status=PENDING]
          DJ[Dispatch crawl_source task]
      end

      subgraph Fetch["📥 URL Fetching"]
          LS[Load CrawlerSource config]
          MR[Mark job RUNNING]
          KW[Iterate WHISKEY_KEYWORDS<br/>whisky, bourbon, scotch...]
          BU[Build paginated URLs<br/>/results/search/year/page?q=keyword]
          SR[SmartRouter.fetch<br/>Tier1→Tier2→Tier3]
      end

      subgraph Parse["🔍 Competition Parsing"]
          GP[get_parser by competition_key<br/>IWSC, SFWSC, WWA...]
          BS[BeautifulSoup extract:<br/>• Product name<br/>• Producer/Brand<br/>• Medal type<br/>• Award year<br/>• Category]
          CR[Return CompetitionResult list]
      end

      subgraph Products["📦 Product Creation"]
          SPM[SkeletonProductManager]
          DD[Check duplicates by<br/>fingerprint or name]
          EX{Exists?}
          AE[Add award to existing<br/>ProductAward]
          NP[Create DiscoveredProduct<br/>status=SKELETON<br/>discovery_source=COMPETITION]
          PA[Create ProductAward<br/>medal, year, competition]
      end

      subgraph Complete["✅ Completion"]
          UM[Update metrics:<br/>products_found<br/>products_new<br/>duplicates_skipped]
          UC[Mark job COMPLETED]
          UN[Update next_crawl_at]
      end

      CB --> QS
      QS --> CJ
      CJ --> DJ
      DJ --> LS
      LS --> MR
      MR --> KW
      KW --> BU
      BU --> SR
      SR --> GP
      GP --> BS
      BS --> CR
      CR --> SPM
      SPM --> DD
      DD --> EX
      EX -->|Yes| AE
      EX -->|No| NP
      NP --> PA
      AE --> UM
      PA --> UM
      UM --> UC
      UC --> UN

      subgraph Models["📊 Models Touched"]
          direction LR
          M1[CrawlSchedule<br/>READ, UPDATE]
          M2[CrawlJob<br/>CREATE, UPDATE]
          M3[CrawlerSource<br/>READ]
          M4[DiscoveredProduct<br/>CREATE, READ, UPDATE]
          M5[ProductAward<br/>CREATE]
          M6[CrawledSource<br/>CREATE]
          M7[CrawlError<br/>CREATE]
      end

      subgraph External["🌐 External Services"]
          E1[SmartRouter<br/>Tier1: httpx<br/>Tier2: Playwright<br/>Tier3: ScrapingBee]
      end