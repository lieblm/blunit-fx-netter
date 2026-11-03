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
