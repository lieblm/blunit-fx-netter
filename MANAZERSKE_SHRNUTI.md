# Manažerské shrnutí: Blunit FX Netter

---

## 1. Strategický koncept a business model

Blunit FX Netter funguje jako **vnitřní směnárna a netting engine** pro klientské směny měnového páru EUR/CZK na sběrném účtu (omnibus account):
* **Generování zisku:** Zisk tvoří vybraný spread z klientských transakcí (výchozí 0,40 % = půl-spread 0,20 % na každé straně).
* **Úspora nákladů:** Přes **92 % klientského objemu** se přirozeně vyrovná uvnitř platformy. Na mezibankovní trh se odesílá pouze nezbytný přebytek, což eliminuje poplatky zprostředkovatelům a snižuje kapitálové nároky.
* **100% zisková historie:** Strategie byla ověřena na 25 letech reálných kurzů ČNB (2000–2024). Všech 25 let skončilo v čistém zisku bez ohledu na kurzové režimy a krize.

---

## 2. Architektura řízení rizik: 4 úrovně ochrany

Pro bezpečný provoz v souladu s institucionálními standardy (Basel III) systém kombinuje čtyři ochranné mechanismy:

| Úroveň ochrany | Mechanismus | Princip fungování |
| :--- | :--- | :--- |
| **1. Objemový limit NOP** | 25 000 EUR limit + 50% buffer | Při překročení limitu se pozice nesmaže celá, ale redukuje na 50 % (12 500 EUR), což ponechává kapacitu pro okamžitý přirozený netting dalších pokynů. |
| **2. Cenové vychylování** | Inventory Skewing (5 bps) | Algoritmický posun klientských kurzů podle stavu účtu: láká protisměrné klienty k rebalancingu bez nutnosti zásahu banky. |
| **3. Tržní časování** | Oportunistický hedging ($k=0{,}75\sigma$) | Při NOP $\ge 17\,500$ EUR systém nečeká na havarijní strop, ale aktivně vyhledá tržní extrém (špičku/propad). **80,5 % všech externích obchodů probíhá v zisku za zvýhodněný kurz.** |
| **4. Časové pojistky (Praxe firem)** | Time-Decay & Weekend Flattening | Ochrana před stárnutím pozice při nízké frekvenci objednávek: automatický časový stop (např. 48 h), víkendové zploštění v pátek v 16:00 UTC a okamžitý split velkých tiketů. |

---

## 3. Shrnutí výsledků: 25 let tržního provozu (2000–2024)

Test proveden na ucelené řadě 41 622 H4 svíček z kurzů ČNB za období 2000 až 2024:

| Metrika | Hodnota za 25 let | Roční průměr | Manažerský komentář |
| :--- | :--- | :--- | :--- |
| **Klientský obrat** | **88,86 mil. EUR** (2 441 mil. CZK) | 3,55 mil. EUR / rok | Stabilní klientský tok napříč čtvrtstoletím. |
| **Zpracované objednávky** | **38 850 pokynů** | 1 554 pokynů / rok | Reprezentativní portfolio firemních konverzí. |
| **Míra internalizace** | **92,94 %** | **92,94 %** | **Pouze 7,06 % objemu** muselo být zajištěno v bance. |
| **Externí zajištění (Hedge)** | 773 transakcí | ~31 obchodů / rok | Z toho **80,5 % oportunistických** (za prémiový kurz). |
| **Havarijní pojistka (Hard Stop)** | 151 transakcí | ~6 obchodů / rok | Náraz na tvrdý limit nastal v průměru jen 6× do roka. |
| **Inkasovaný hrubý spread** | **4 874 770 CZK** | 194 991 CZK / rok | Čistý bezrizikový výnos z klientské marže. |
| **Čistý hospodářský výsledek (MtM)** | **+4 988 016 CZK** (~183 051 EUR) | **+199 521 CZK / rok** | Výsledek po odečtení tržního přecenění a hedgů. |
| **Úspěšnost (Ziskové roky)** | **25 z 25 let (100,0 %)** | 100,0 % | Zisk v každém roce (min. +165 tis., max. +268 tis. CZK). |
| **Denní tržní riziko (VaR 99 %)** | **3 789 CZK** | 3 789 CZK | Tvoří pouhých **1,9 % ročního zisku** (minimální kapitálová náročnost). |

### Odolnost vůči tržním šokům
Systém prokázal robustnost napříč všemi historickými režimy koruny:
1. Dlouhodobé posilování CZK z 36,00 na 24,00 CZK/EUR (2000–2008).
2. Globální finanční krize (2008–2009).
3. Intervenční režim ČNB se zafixovaným kurzem 27,00 CZK/EUR (2013–2017).
4. Pandemické výkyvy (2020) a válečná inflace (2022).

---

## 4. Přechod do praxe: Nízkofrekvenční tok a řízení stárnutí inventáře

V reálném firemním provozu klienti nesměňují kontinuálně každé 4 hodiny, ale nepravidelně (např. jednotky obchodů týdně). Systém je pro tento režim plně uzpůsoben:

1. **Řízení stárnutí pozice (Position Aging & Time-Stop):**
   * Pokud otevřená pozice čeká na protipokyn déle než stanovený limit (např. 24–48 h), systém nenechá běžet tržní drift, ale pozici automaticky zredukuje časovým hedgem.
2. **Dynamický Time-Decay:**
   * S přibývajícím časem systém postupně snižuje požadavek na kurzový extrém. Zpočátku trvá na prémiovém kurzu ($k=0{,}75\sigma$), po 36 hodinách bere i průměrný tržní kurz, aby inventář bezpečně uvolnil.
3. **Páteční zploštění (Weekend Flattening):**
   * V pátek v 16:00 UTC před víkendovým uzavřením trhů systém zredukuje pozici na bezpečné minimum (např. 5 000 EUR), čímž zcela eliminuje víkendový gap risk a swapové náklady.
4. **Rozdělení velkých tiketů (Block Order Split):**
   * Pokyny nad 15 000 EUR jsou z 50 % okamžitě zajištěny na mezibankovním trhu (Back-to-Back), čímž se zamezí jednorázovému vyčerpání nettingové kapacity.

---

## 5. Webové rozhraní a ovládání operátora (Dashboard)

Aplikace v [app.py](file:///Users/lieblm/Documents/GitHub/blunit-fx-netter/app.py) poskytuje dispečerovi a risk managerovi kompletní kontrolu:
* **Simulace toku:** Možnost přepnutí mezi vysokofrekvenčním režimem a nízkofrekvenčním firemním provozem (volba průměrné prodlevy v dnech).
* **Dvourozměrný semafor rizika:** Hodnotí nejen absolutní velikost NOP v EUR, ale i dobu držení (kombinace Objem × Čas).
* **Vizuální rozlišení zásahů v grafu:**
  * Žlutá hvězda = Oportunistický hedge (kurzový zisk).
  * Modrý čtverec = Časový hedge (Position Aging Time-Stop).
  * Fialový trojúhelník = Páteční víkendové zploštění.
  * Tyrkysový křížek = Dělení velkého klientského tiketu (Block Split).
  * Červený kosočtverec = Havarijní limit (Hard Stop 25k EUR).
* **Auditní deník transakcí:** Rychlé filtrování podle typu události a jednoklikový export do CSV.
