# Manažerské shrnutí: Blunit FX Netter

---

## 1. Co systém dělá (Business Model)

Místo posílání každé klientské směny na externí trh (do banky) funguje systém jako **vlastní interní směnárna**:
- Klient A prodává EUR $\rightarrow$ systém od něj EUR koupí levněji (kurz Bid).
- Klient B nakupuje EUR $\rightarrow$ systém mu EUR prodá dráž (kurz Ask).
- **Zisk tvoří marže (spread 0,40 %)**, kterou inkasujeme z každé klientské transakce.

---

## 2. Kde je riziko a jak ho řídíme (Auto-Hedging)

- **Riziko nerovnováhy:** Pokud klienti v daný moment více nakupují než prodávají, vzniká na sběrném účtu otevřená pozice (**NOP - Net Open Position**). Kdyby v tu chvíli tržní kurz prudce vyskočil, vznikla by tržní ztráta.
- **Automatická pojistka:** Systém neustále hlídá limit rizika (výchozí **10 000 EUR** v základním modelu, škálovatelný na **25 000 EUR**). Jakmile je limit překročen, systém přebytek okamžitě dorovná na externím trhu za velkoobchodní kurz. Tím tržní riziko okamžitě **vynuluje nebo zredukuje na bezpečnou rezervu**.

---

## 3. Výsledky testů na reálných datech: Porovnání let 2023 a 2025

Strategie byla otestována na reálných datech EUR/CZK v H4 časovém rámci ve dvou samostatných letech:

| Metrika | Rok 2023 | Rok 2025 (`fxdata/backtest_2025.csv`) | Manažerský význam |
| :--- | :--- | :--- | :--- |
| **Klientský obrat** | 3,57 mil. EUR (85,5 mil. CZK) | **3,52 mil. EUR** (86,7 mil. CZK) | Objem klientských směn (~1 540 pokynů/rok). |
| **Zpracované H4 svíčky** | 1 560 svíček | **1 537 svíček** | Celoroční kontinuální provoz. |
| **Míra internalizace** | **76,76 %** | **76,73 %** | **Více než 3/4 objemu** se vyrovnalo uvnitř firmy bez nutnosti externího trhu. |
| **Externí hedge obchody** | 75 transakcí | **74 transakcí** | Na mezibankovní trh šlo pouze ~4,8 % pokynů. |
| **Hedgovaný objem** | 828 850 EUR | **817 850 EUR** | Pouze nezbytné objemy pro vynulování rizika. |
| **Inkasovaný hrubý spread** | 171 055 CZK | **173 463 CZK** | Celkový vybraný klientský spread. |
| **Čistý zisk (Mark-to-Market)** | **+170 379 CZK** (~6 909 EUR) | **+171 418 CZK** (~7 074 EUR) | **Čistý výsledek** po započtení všech pohybů trhu a hedgingu. |

---

## 4. Klíčové závěry pro vedení

1. **Mimořádná stabilita a konzistence:**
   - Dva odlišné roky s rozdílným vývojem kurzu přinesly **téměř identické výsledky**: míra internalizace 76,7 % a čistý roční zisk přes 171 000 CZK.
2. **Dramatická úspora nákladů:**
   - Z 3,5 mil. EUR ročního obratu se 2,7 mil. EUR vyrovnalo uvnitř účtu. To šetří jak poplatky externím zprostředkovatelům, tak požadavky na kapitál.
3. **Plná kontrola nad rizikem:**
   - Při limitu 10 000 EUR bylo tržní riziko bezpečně řízeno v automatickém režimu bez lidského zásahu.
4. **Škálovatelnost:**
   - S růstem počtu klientských transakcí roste míra přirozeného nettingu i vybraný spread, zatímco frekvence externích hedge obchodů relativně klesá.

---

## 5. Optimalizovaný model: Škálování limitu a cenové vychylování

Na základě kvantitativní analýzy 10letých tržních dat EUR/CZK (2017–2026, historická volatilita pouhých 3,44 % p.a.) byl engine rozšířen o institucionální mechanismy:
1. **Navýšení limitu NOP na 25 000 EUR:** Využití přirozeně nízké volatility trhu.
2. **Částečný hedging (50 % buffer):** Dorovnání pouze přebytku pro zachování kapacity pro okamžitý přirozený netting dalších pokynů.
3. **Cenové vychylování (Inventory Skewing):** Algoritmický posun klientských kurzů o 5 bps k přirozenému rebalancingu bez banky.
4. **Třízónový systém řízení rizik (Basel III):** Zelená zóna (0–15k EUR), Žlutá zóna (15–25k EUR, aktivní skewing), Červená zóna (>25k EUR, auto-hedge).

### Porovnání základního a optimalizovaného modelu (rok 2025)

| Metrika | Základní model (10k EUR, 100% hedge) | Optimalizovaný model (25k EUR, 50% hedge, skew) | Přínos / Změna |
| :--- | :--- | :--- | :--- |
| **Míra internalizace** | 76,73 % | **93,93 %** | **+17,20 p.b.** (téměř 94 % objemu uvnitř) |
| **Externí hedge obchody** | 74 transakcí | **16 transakcí** | **Pokles o 78 %** (minimální závislost na bance) |
| **Hedgovaný objem na trhu** | 817 850 EUR | **213 250 EUR** | **Pokles o 74 %** (masivní úspora poplatků) |
| **Čistý zisk (MtM)** | +171 418 CZK | **+178 395 CZK** | **+4,1 %** vyšší čistý zisk |
| **Denní tržní riziko (VaR 99 %)**| 1 455 CZK | **2 376 CZK** | Zůstává zanedbatelné (**1,33 % ročního zisku**) |

---

## 6. Oportunistický hedging: Inteligentní časování zajišťovacích obchodů

### Princip metody (jednoduše a srozumitelně)
Při klasickém hedgingu systém čeká, až otevřená pozice narazí na havarijní strop (např. 25 000 EUR), a v ten moment musí nuceně prodat nebo koupit v bance za jakýkoliv kurz, který zrovna na trhu platí.

**Oportunistický hedging funguje chytřeji:**
* Pokud na účtu vznikne větší přebytek (nad 17 500 EUR), systém **nečeká pasivně na strop**.
* Průběžně sleduje krátkodobé tržní kmitání a vyčkává na okamžik, kdy se kurz pohne **výrazně v náš prospěch**.
* Jakmile trh nabídne nadprůměrný kurz, systém přebytek odprodá dříve a realizuje **dodatečný tržní zisk k vybranému spreadu**.

### Použité indikátory a směrová pravidla
Využívá se statistické pásmo odchylky od klouzavého průměru (Bollingerovo pásmo s parametrem $k = 0{,}75 \times \sigma$ za posledních 20 svíček H4, tj. cca 3,3 dne):

1. **Účet drží přebytek EUR ($+NOP \ge 17\,500\ \text{EUR}$):**
   * *Cíl:* Prodat EUR v bance co nejdráže.
   * *Pravidlo:* Systém čeká na cenovou špičku ($Aktuální\ kurz \ge Průměr + 0{,}75 \times \sigma$). Jakmile nastane, odprodá EUR na trhu za prémiový kurz.
2. **Účet má nedostatek EUR ($-NOP \le -17\,500\ \text{EUR}$):**
   * *Cíl:* Dokoupit EUR v bance co nejlevněji.
   * *Pravidlo:* Systém čeká na cenový propad ($Aktuální\ kurz \le Průměr - 0{,}75 \times \sigma$). Jakmile nastane, dokoupí EUR v propadu.
3. **Pojistka (Hard Stop na 25 000 EUR):**
   * Pokud trh prudce trenduje proti nám a lokální extrém nenastane, při dosažení 25 000 EUR se provede okamžitý havarijní hedge bez ohledu na kurz.

### Výsledky backtestu (rok 2025)

* **Celkový počet hedge obchodů:** 28 transakcí.
* **Oportunistické obchody (za prémiový kurz):** **21 transakcí (75 % všech zásahů)**.
* **Havarijní obchody (Hard Stop):** pouze 7 transakcí.
* **Míra internalizace:** **93,50 %**.
* **Čistý zisk (Mark-to-Market):** **+178 060 CZK**.
* **Manažerský závěr:** Tři čtvrtiny všech externích zásahů byly provedeny z vlastní iniciativy za zvýhodněný tržní kurz, nikoliv z nuceného překročení limitu.

---

## 7. Komplexní historický backtest 2000–2024 (25 let provozu)

Pro otestování robustnosti optimalizovaného modelu a oportunistického hedgingu byl proveden ucelený historický backtest napříč **25 lety tržního vývoje (2000–2024)** na reálných tržních kurzech ČNB a tickových datech. 

### Parametry testu
* **Limit otevřené pozice (NOP):** 25 000 EUR
* **Cílový poměr zajištění (Hedge target ratio):** 50 % (buffer 12 500 EUR pro přirozený netting)
* **Cenové vychylování (Inventory Skewing):** 5 bps (posun klientského spreadu podle stavu knihy)
* **Oportunistický hedging:** aktivní od $\pm 17\,500\ \text{EUR}$, parametr $k = 0{,}75 \times \sigma$ (Bollinger 20 period H4)
* **Klientský tok:** simulace identického profilu jako v referenčním roce 2025 (~1 554 objednávek ročně, průměrný objem 2 287 EUR/objednávka)

---

### Agregované statistiky za celé období (2000–2024)

| Metrika | Hodnota za 25 let | Roční průměr |
| :--- | :--- | :--- |
| **Celkový klientský obrat** | **88,86 mil. EUR** (2 441 mil. CZK) | 3,55 mil. EUR / rok |
| **Zpracované objednávky** | **38 850 pokynů** | 1 554 pokynů / rok |
| **Průměrná míra internalizace** | **92,94 %** | min. 92,00 % (2006) – max. 93,79 % (2001) |
| **Celkem externích hedge obchodů** | **773 obchodů** | ~31 obchodů / rok |
| ↳ **Oportunistické (v zisku za prémiový kurz)** | **622 obchodů (80,5 %)** | **~25 obchodů / rok** |
| ↳ **Havarijní pojistka (Hard Stop 25k EUR)** | **151 obchodů (19,5 %)** | ~6 obchodů / rok |
| **Hrubý realizovaný spread** | **4 874 770 CZK** | 194 991 CZK / rok |
| **Čistý kumulativní zisk (Clean MtM PnL)** | **+4 988 016 CZK** (~ +183 051 EUR) | **+199 521 CZK / rok** |
| **Ziskové vs. ztrátové roky** | **25 / 25 ziskových let (100,0 %)** | min. +165 113 CZK – max. +267 922 CZK |
| **Průměrný denní VaR (99 % konfidence)** | **3 789 CZK** | max. 4 598 CZK (v roce 2000) |

---

### Roční přehled výsledků (2000–2024)

| Rok | Objednávky | Obrat (EUR) | Internalizace | Zajištěno (EUR) | Hedge celkem | Oportunistické | Hard Stop | Realizovaný spread | Čistý MtM zisk (CZK) | Denní VaR 99% |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2000** | 1 506 | 3 447 900 | 93,17 % | 235 350 | 30 | 25 | 5 | 245 072 CZK | **+244 238 CZK** | 4 598 CZK |
| **2001** | 1 506 | 3 447 900 | 93,79 % | 214 250 | 25 | 17 | 8 | 234 428 CZK | **+215 690 CZK** | 4 135 CZK |
| **2002** | 1 512 | 3 466 500 | 93,60 % | 221 800 | 26 | 19 | 7 | 213 146 CZK | **+194 199 CZK** | 4 464 CZK |
| **2003** | 1 512 | 3 466 500 | 93,14 % | 237 850 | 32 | 27 | 5 | 220 361 CZK | **+207 362 CZK** | 4 553 CZK |
| **2004** | 1 524 | 3 492 050 | 92,92 % | 247 100 | 30 | 26 | 4 | 222 545 CZK | **+214 059 CZK** | 4 273 CZK |
| **2005** | 1 518 | 3 479 700 | 92,38 % | 265 150 | 35 | 30 | 5 | 207 130 CZK | **+234 426 CZK** | 4 151 CZK |
| **2006** | 1 506 | 3 447 900 | 92,00 % | 275 750 | 30 | 22 | 8 | 195 607 CZK | **+198 854 CZK** | 3 962 CZK |
| **2007** | 1 506 | 3 447 900 | 92,03 % | 274 850 | 32 | 23 | 9 | 191 510 CZK | **+182 756 CZK** | 3 655 CZK |
| **2008** | 1 518 | 3 479 700 | 92,51 % | 260 550 | 35 | 29 | 6 | 173 489 CZK | **+182 055 CZK** | 3 465 CZK |
| **2009** | 1 506 | 3 447 900 | 92,38 % | 262 900 | 33 | 27 | 6 | 182 295 CZK | **+184 361 CZK** | 3 707 CZK |
| **2010** | 1 518 | 3 479 700 | 92,96 % | 245 100 | 29 | 23 | 6 | 175 842 CZK | **+188 924 CZK** | 3 504 CZK |
| **2011** | 1 518 | 3 479 700 | 93,03 % | 242 650 | 30 | 24 | 6 | 170 900 CZK | **+203 327 CZK** | 3 688 CZK |
| **2012** | 1 512 | 3 466 500 | 93,23 % | 234 750 | 30 | 23 | 7 | 174 007 CZK | **+195 456 CZK** | 3 475 CZK |
| **2013** | 1 512 | 3 466 500 | 92,91 % | 245 850 | 29 | 21 | 8 | 179 907 CZK | **+189 191 CZK** | 3 822 CZK |
| **2014** | 1 512 | 3 466 500 | 92,35 % | 265 150 | 35 | 32 | 3 | 190 772 CZK | **+196 370 CZK** | 3 775 CZK |
| **2015** | 1 506 | 3 447 900 | 92,57 % | 256 350 | 31 | 26 | 5 | 188 028 CZK | **+194 722 CZK** | 3 892 CZK |
| **2016** | 1 512 | 3 466 500 | 92,60 % | 256 450 | 32 | 29 | 3 | 187 255 CZK | **+192 375 CZK** | 3 565 CZK |
| **2017** | 2 184 | 4 903 050 | 93,66 % | 310 700 | 37 | 27 | 10 | 257 517 CZK | **+267 922 CZK** | 3 454 CZK |
| **2018** | 1 566 | 3 579 700 | 93,17 % | 244 600 | 36 | 34 | 2 | 183 094 CZK | **+193 401 CZK** | 3 440 CZK |
| **2019** | 1 566 | 3 579 700 | 92,69 % | 261 750 | 32 | 26 | 6 | 183 499 CZK | **+184 819 CZK** | 3 542 CZK |
| **2020** | 1 572 | 3 594 950 | 92,87 % | 256 250 | 30 | 20 | 10 | 190 031 CZK | **+204 809 CZK** | 3 683 CZK |
| **2021** | 1 566 | 3 579 700 | 93,21 % | 243 200 | 31 | 26 | 5 | 182 989 CZK | **+194 372 CZK** | 3 385 CZK |
| **2022** | 1 560 | 3 565 950 | 93,42 % | 234 550 | 29 | 24 | 5 | 174 536 CZK | **+174 357 CZK** | 3 458 CZK |
| **2023** | 1 560 | 3 565 950 | 93,59 % | 228 400 | 28 | 23 | 5 | 170 615 CZK | **+165 113 CZK** | 3 440 CZK |
| **2024** | 1 572 | 3 594 950 | 93,39 % | 237 550 | 26 | 19 | 7 | 180 195 CZK | **+184 859 CZK** | 3 627 CZK |

---

### Klíčové manažerské poznatky z 25letého testu

1. **Absolutní stabilita míry internalizace:** Míra vnitřního vypořádání bez nutnosti vstupu na mezibankovní trh se v průběhu čtvrtstoletí držela v extrémně úzkém rozpětí **92,00 % až 93,79 %** bez ohledu na kurzový režim.
2. **Dominance oportunistických zajištění (80,5 %):** Z celkových 773 externích zásahů bylo **622 provedeno proaktivně v lokálních cenových extrémech ve prospěch platformy**, čímž byl čistý zisk navýšen nad úroveň čistého spreadu (Clean MtM PnL 4,99 mil. CZK vs. hrubý spread 4,87 mil. CZK).
3. **100% ziskovost všech 25 let:** Model dosáhl kladného čistého výsledku v každém jednotlivém kalendářním roce (v rozpětí od +165 tis. do +268 tis. CZK), a to i v obdobích:
   * Dlouhodobého posilování koruny z 36,00 na 24,00 CZK/EUR (2000–2008),
   * Globální finanční krize (2008–2009),
   * Intervenčního režimu ČNB s fixním stropem 27,00 CZK/EUR (2013–2017),
   * Pandemických výkyvů a bleskových pohybů (2020),
   * Energetické krize a války na Ukrajině (2022).
4. **Minimální tržní expozice:** Průměrný jednodenní 99% Value at Risk nepřesáhl **3 789 CZK** (cca 1,9 % průměrného ročního čistého zisku), což potvrzuje striktní soulad s regulatorními a kapitálovými požadavky.
