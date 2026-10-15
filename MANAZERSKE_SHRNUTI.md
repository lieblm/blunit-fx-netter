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
- **Automatická pojistka:** Systém neustále hlídá limit rizika (výchozí **10 000 EUR**). Jakmile je limit překročen, systém přebytek okamžitě dorovná na externím trhu za velkoobchodní kurz. Tím tržní riziko okamžitě **vynuluje na 0**.

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
