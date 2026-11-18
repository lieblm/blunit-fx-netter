# Technické a obchodní zadání (RFP): EU/EEA Hedging Broker / Liquidity Provider (Vrstva B)

## 1. Účel a kontext projektu
Předmětem poptávky je výběr regulovaného evropského FX brokera / poskytovatele likvidity (Liquidity Provider / MTF, dále jen „Broker“) pro provoz automatizovaného zajišťovacího modulu interního multi-měnového FX netting enginu (**Blunit FX Netter**) provozovaného **platební institucí (PI / SPI)** v EU.

* **Vymezení rozsahu (Vrstva B):** Veškeré klientské účty, safeguarding a lokální platební styk s koncovými klienty si platební instituce zajišťuje samostatně mimo Brokera (Vrstva A). Od Brokera poptáváme **výhradně institucionální zajišťovací účet (Hedging / Margin Execution Account)** financovaný z vlastních provozních prostředků instituce pro průběžné řízení kurzového rizika (NOP) a jeho synchronizované rozpouštění při periodickém fyzickém rebalancingu likvidity.
* **Cílové měny:** `EUR`, `CZK`, `USD`, `PLN` (s možností budoucího rozšíření o `GBP`, `CHF`, `HUF`).
* **Požadované měnové páry:**
  * **Primární (Hub & Core) páry:** `EUR/USD`, `EUR/CZK`, `EUR/PLN`, `USD/CZK`, `USD/PLN`.
  * **Doplňkový kříž:** `PLN/CZK` (případně `CZK/PLN`) – přímá kotace nebo syntetická triangulace přes `EUR` (`EUR/PLN` + `EUR/CZK`).
* **Profil toku a provozní logika:**
  * Základní referenční objem klientského toku na hlavním páru činí ~3,5 mil. EUR ročně (s dalším růstem po zapojení `USD` a `PLN`), v nízkofrekvenčním firemním režimu jednotky až desítky obchodů týdně.
  * Engine provádí interní netting na úrovni jednotlivých měnových zůstatků (Currency-Basket Netting) a přes Brokera kryje pouze čistou zbytkovou otevřenou pozici (NOP).

---

## 2. Regulační požadavky a onboarding platební instituce

1. **Regulace a licence Brokera (EU/EEA):**
   * Subjekt regulovaný v EU/EEA (např. ČNB, BaFin, CySEC, CBI, KNF, AMF, MFSA) s platným pasportem pro poskytování investičních služeb v ČR a EU dle **MiFID II / MiFIR**.
   * *Vyloučení:* Mimoevropští brokeři bez regulace a pasportu v EU/EEA (např. licence FMA, FSA apod.) nesplňují regulatorní požadavky platební instituce.
   * Prokazatelná kapitálová přiměřenost a uložení kolaterálu u Tier-1 evropských/mezinárodních bank.
2. **Onboarding platební instituce (Own-Funds Hedging Account):**
   * Schopnost provést KYB/AML onboarding regulované platební instituce pro otevření firemního obchodního účtu dotovaného z **vlastních prostředků instituce (House / Own Capital Account)** za účelem zajišťování měnové expozice.
   * *Bez safeguarding požadavků na Brokera:* Na účtu u Brokera nebudou vedeny oddělené prostředky jednotlivých koncových klientů ani z něj nebudou odcházet platby třetím stranám.
3. **Klientská kategorizace a regulatorní reporting:**
   * Kategorizace jako *Profesionální zákazník* nebo *Způsobilá protistrana (Eligible Counterparty)* dle MiFID II (přístup k institucionální likviditě a maržovým podmínkám bez retailových omezení ESMA).
   * Jasné nastavení a podpora regulatorního reportingu (EMIR / MiFIR, LEI reporting, případně delegovaný reporting).

---

## 3. Kolaterál, financování účtu a vazba na periodický fyzický rebalancing

1. **Financování účtu a platební toky (First-Party Funding):**
   * Vklady a výběry marže/kolaterálu probíhají **výhradně mezi vlastním firemním účtem platební instituce a Brokerem** (First-Party Transfers, žádné vklady/výplaty třetích stran).
   * Podpora standardních evropských a mezinárodních kolejí pro dotaci a výběr kolaterálu: **SEPA Credit Transfer / SEPA Instant** pro `EUR` (ideálně T+0) a **SWIFT** pro `USD`, `PLN`, `CZK` (pokud je využíván multi-měnový kolaterál), bez procentuálních poplatků za vklad/výběr.
2. **Cross-Currency Margining & Zúčtování PnL:**
   * Primární zúčtovací a kolaterálová měna účtu: `EUR`.
   * Požadujeme podporu **Cross-Currency Margining** / **Multi-Currency Collateral** (`EUR`, `USD`, `CZK`, `PLN`) nebo transparentní a nákladově minimální zúčtování realizovaného PnL z ostatních měnových párů do základní měny účtu bez skrytých konverzních přirážek.
   * Jasná pravidla pro úročení drženého volného kolaterálu (Credit/Debit Interest).
3. **Provozní vazba na periodický fyzický rebalancing:**
   * **Fáze 1 – Průběžné zajišťování NOP:** Jakmile čistá zůstatková expozice na externích platebních účtech Blunitu překročí stanovený práh (`opportunistic_threshold`, časový limit `Time-Stop`, páteční `Weekend Flattening`, `hedge_limit` nebo rozdělení velkého tiketu `Block Split`), engine automaticky otevře nebo upraví zajišťovací pozici u Brokera.
   * **Fáze 2 – Synchronizované rozpuštění při fyzickém rebalancingu:** Periodicky (např. týdně, měsíčně nebo při naplnění fyzických limitů) provede Blunit reálnou směnu měn na svých externích bankovních/platebních účtech a **ve stejný okamžik API příkazem uzavře nebo částečně zredukuje odpovídající zajišťovací pozici u Brokera**.
   * **Z toho plynoucí požadavky na účet Brokera:**
     * **Nettingový režim účtu (Position Netting Mode):** Nutná podpora čistého započítávání a **částečného uzavírání pozic (Partial Close)** přesným objemem (krok 1 000 jednotek / 0,01 lotu, ideálně 1–50 jednotek) bez restrikcí typu FIFO nebo nuceného držení protichůdných tiketů.
     * **Synchronní exekuce bez Leg-Risku:** Okamžitá `Market` / `IOC` / `FOK` exekuce při rozpouštění hedge v souběhu s externí konverzí.
     * **Absence omezení doby držení:** Žádné sankce za krátkodobé uzavření pozice (intraday rozpuštění při rebalancingu) ani za delší držení (24–48 h v rámci `Time-Stop`), a nulové poplatky za neaktivitu (inactivity fees).
   * *(Volitelně)* V nabídce uveďte, zda vedle maržového režimu případně umožňujete i přímý výběr realizovaných zůstatků v `EUR`/`USD`/`CZK`/`PLN` formou Deliverable Spot FX na firemní účty Blunitu.

---

## 4. Obchodní parametry, likvidita a exekuce

Požadavky vycházejí přímo z parametrů enginu (NOP limit ekvivalent ~25 000 EUR, cílový buffer 50 % = 12 500 EUR, víkendový práh 5 000 EUR, blokové dělení od 15 000 EUR):

1. **Granularita objemů (Min. Trade Size):**
   * Podpora exekuce již od **1 000 jednotek základní měny (0,01 lotu)**, ideálně libovolná částka s přesností na **1 až 50 jednotek** (klíčové pro přesné dorovnání 50% bufferu, víkendového zploštění a synchronizované redukce při fyzickém rebalancingu).
2. **Spready, komise a syntetické křížení:**
   * Institucionální Raw / ECN / STP spready na `EUR/USD` (< 0,5 bps), `EUR/CZK`, `EUR/PLN`, `USD/CZK`, `USD/PLN` (typicky 1–5 bps v likvidních hodinách) a vyjádření k likviditě/spreadu přímého páru `PLN/CZK`.
   * Transparentní struktura komisí (fixní sazba za 1 mil. EUR/USD zobchodovaného objemu bez skrytých mark-upů ve spreadu).
3. **Model exekuce a typy příkazů:**
   * Režim **STP / ECN / MTF** (No Dealing Desk), bez neférových „last look“ odmítnutí příkazů při zvýšené volatilitě.
   * Podpora příkazů **Market**, **IOC (Immediate-or-Cancel)**, **FOK (Fill-or-Kill)** a **Limit** (včetně ESP – Executable Streaming Prices, případně RFQ).
   * Nízká latence umožňující rychlou sekvenční exekuci dvou nohou (Multi-Leg) při syntetické triangulaci `PLN/CZK` přes `EUR` (`EUR/PLN` + `EUR/CZK`) s minimálním *leg riskem*.
4. **Obchodní hodiny a páteční likvidita:**
   * Kontinuální likvidita 24/5 od nedělního otevření minimálně do pátku **16:00–21:00 UTC** na všech uvedených párech (včetně CEE křížů v pátek odpoledne) pro spolehlivé provedení automatického pátečního zploštění (*Weekend Flattening*).
5. **Swapové body / Overnight Rollover:**
   * Při nízké frekvenci klientského toku drží engine pozice do limitu *Position Aging Time-Stop* (typicky 24–48 hodin) nebo do termínu fyzického rebalancingu. Požadujeme transparentní, tržně konkurenceschopné Tom-Next swapové sazby na všech požadovaných párech odrážející reálný úrokový diferenciál dotčených centrálních bank (ECB, Fed, ČNB, NBP).

---

## 5. Technické požadavky na API a konektivitu

Engine vyžaduje plně automatizovanou M2M komunikaci napříč všemi sledovanými měnovými páry:

1. **Protokoly pro tržní data a exekuci:**
   * Průmyslový standard **FIX 4.4** (samostatné session pro Market Data a Order Entry) **NEBO** produkční **WebSocket + REST API**.
   * **Multi-Pair Market Data Feed:** Real-time paralelní streamování Bid/Ask kotací pro všechny požadované páry současně (tick-by-tick / sekundové intervaly) pro výpočet křížových kurzů, syntetické triangulace a klouzavých statistik (Bollinger 20×H4 pro *Oportunistický hedging*).
   * **Historická data:** Programový přístup k historickým OHLC svíčkám (`M1`, `H1`, `H4`) pro všechny požadované páry přes API za účelem kalibrace volatility a korelačních matic (Portfolio VaR).
2. **Asynchronní potvrzování a stav účtu (Position & Margin API):**
   * Okamžité asynchronní Execution Reports (`New`, `PartiallyFilled`, `Filled`, `Rejected`, přesná exekuční cena, timestamp v UTC s přesností na ms).
   * Endpointy pro dotazování aktuálních otevřených pozic po jednotlivých párech i čisté měnové expozice (`EUR`, `CZK`, `USD`, `PLN`), použité/volné marže, maržové úrovně a nerealizovaného/realizovaného PnL.
3. **Auditní a účetní exporty:**
   * Automatizovaný denní a měsíční výpis všech exekucí, swapů, komisí a pohybů marže přes API, SFTP nebo strukturovaný CSV/JSON ledger pro plné párování s interním deníkem enginu.
4. **Testovací prostředí (Sandbox / UAT):**
   * Plnohodnotné Demo / UAT API prostředí pokrývající všechny požadované páry (včetně `CZK` a `PLN` křížů) a realistické chování exekucí pro integrační testování.
5. **Bezpečnost a SLA:**
   * Šifrované spojení **TLS 1.2 / 1.3**, autentizace přes **mTLS (klientské certifikáty)** nebo **HMAC-SHA256 / OAuth2**, podpora **IP whitelisting**.
   * Garantovaná dostupnost API **$\ge 99{,}9\,\%$** a definované rate limity pro paralelní správu více párů.

---

## 6. Risk Management a Industry Best Practices

1. **Ochrana před selháním konektivity a chybami (Safeguards):**
   * Funkce **Cancel-on-Disconnect** pro aktivní limitní příkazy při výpadku API spojení.
   * Konfigurovatelné **Pre-trade kontroly** na úrovni účtu/API (`Max Order Size` limit pro jednotlivé páry, `Max Net Exposure` strop).
   * Nouzové **Kill Switch** rozhraní (API endpoint i telefonický 24/5 dealing desk) pro okamžité zastavení obchodování a uzavření všech pozic.
2. **Best Execution & TCA (Transaction Cost Analysis):**
   * Pravidelné (minimálně kvartální) reporty kvality plnění v souladu s **MiFID II Best Execution** rozpadnuté po párech (statistiky slippage – pozitivní vs. negativní skluz, latence exekuce, fill rate).
3. **Margin monitoring:**
   * Jasně definované prahy pro Margin Call a Stop-Out a real-time upozornění přes API/WebSocket/Webhook při přiblížení k maržovým limitům.

---

## 7. Požadovaná struktura nabídky od Brokera

V odpovědi prosím uveďte:
1. Právní entitu, EU/EEA licenci, regulátora a potvrzení možnosti onboardingu regulované **platební instituce (PI)** na vlastní zajišťovací účet (*Own-Funds Corporate Hedging Account*).
2. Podporované měny kolaterálu, pravidla **Cross-Currency Margining**, režim vypořádání a částečného uzavírání pozic (*Position Netting Mode* při synchronizaci s externím fyzickým rebalancingem), a poplatky/lhůty pro vklady a výběry (`SEPA` / `SEPA Instant` / `SWIFT`).
3. Přesné obchodní podmínky (min. objem / granularita, typický spread, komise, Tom-Next swapové sazby, úročení volného kolaterálu) pro páry `EUR/USD`, `EUR/CZK`, `EUR/PLN`, `USD/CZK`, `USD/PLN` a vyjádření k podpoře přímého vs. syntetického `PLN/CZK`.
4. Technickou specifikaci API (`FIX 4.4` / `REST` / `WebSocket`), dostupnost historických svíček (`M1`, `H1`, `H4`), popis Sandbox prostředí a SLA.
5. Vzorové dokumenty KYB checklistu, MiFID II Best Execution / TCA reportingu a API dokumentaci (odkaz / příloha).
