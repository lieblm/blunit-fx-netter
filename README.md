# Blunit FX Netter (PoC)

Proof of Concept (PoC) pro interní Netting & Market Maker engine směny měnového páru EUR/CZK.

Systém demonstruje vnitřní netting a internalizaci klientských FX směn na sběrném účtu (omnibus account) bez nutnosti odesílat každý klientský pokyn na externí trh. Zisk tvoří vybraný spread z klientských transakcí. Tržní riziko je řízeno sledováním čisté otevřené pozice (**Net Open Position - NOP**) a automatickým zajišťováním (**Auto-Hedging**) na mezibankovním/externím trhu při dosažení stanoveného limitu.

Systém podporuje jak rychlou syntetickou simulaci, tak **plný backtest na skutečných historických kurzech EUR/CZK** (4hodinové svíčky H4) s možností volby počátku a konce testu a exportem výsledků do CSV.

---

## Klíčové vlastnosti

1. **Reálná tržní data (H4 svíčky):**
   - Podpora načítání historických kotací z CSV (`fxdata/eurczk-h4-bid-2017-01-02-2026-10-15.csv`).
   - Přesná časová filtrace podle počátku (`--start-date`) a konce testu (`--end-date`).
2. **Dynamický Pricing Model:**
   - Každý obchod se oceňuje podle aktuálního tržního kurzu dané svíčky v čase exekuce.
   - Klientský spread (`spread_pct`, výchozí 0.40 %, tj. půl-spread 0.20 % na každé straně).
   - Klient nakupuje EUR za Ask (`mid * (1 + spread/2)`), prodává EUR za Bid (`mid * (1 - spread/2)`).
3. **Interní netting pokynů:**
   - Klientské toky jsou uspokojovány ze sběrného účtu a přirozeně se vzájemně nettingují.
4. **Auto-Hedging (Risk Management):**
   - Jakmile absolutní hodnota `|NOP| >= HEDGE_LIMIT` (výchozí 10 000 EUR), engine provede hedge obchod na externím trhu za aktuální tržní kurz dané svíčky, čímž vynuluje NOP na 0 EUR.
5. **Detailní ledger & CSV export:**
   - Každá klientská i hedge transakce zaznamenává přesný čas, objem, kurz, vybraný spread, zůstatky obou měn, NOP a průběžné Mark-to-Market PnL.
   - Možnost exportu do CSV souboru i přímého výpisu do konzole.

---

## Architektura projektu

```text
blunit-fx-netter/
├── fxdata/
│   ├── eurczk-h4-bid-2017-01-02-2026-10-15.csv  # Skutečná historická data EUR/CZK
│   ├── backtest_2025.csv                         # Výsledky backtestu za rok 2025
│   └── simulation_results.csv                    # Vygenerovaný detailní CSV výstup
├── src/
│   └── blunit_fx/
│       ├── __init__.py      # Exportované API balíčku
│       ├── data_loader.py   # Načítání a filtrace historických svíček z CSV
│       ├── models.py        # Datové třídy (ClientOrder, TradeRecord, HedgeTrade, AccountState)
│       ├── pricing.py       # PricingModel (dynamické bid/ask kurzy a spread)
│       ├── engine.py        # NetterEngine (omnibus účet, NOP, hedging, ledger)
│       └── simulator.py     # SimulationRunner s podporou historických svíček a CSV exportu
├── tests/
│   ├── __init__.py
│   └── test_engine.py       # Kompletní testovací sada (unittest)
├── scripts/
│   ├── build_h4_dataset.py  # Skript pro stažení/sestavení kompletního H4 datasetu
│   └── fetch_all_data.py    # Pomocný skript pro stahování dat
├── main.py                  # CLI vstupní bod simulátoru
├── pyproject.toml           # Konfigurace balíčku
├── requirements.txt         # Volitelné závislosti (pandas)
├── MANAZERSKE_SHRNUTI.md    # Manažerské shrnutí srovnání 2023 vs 2025
├── .gitignore
├── GEMINI_ blunit-fx-netter.md # Směrnice asistenta
└── README.md                # Tato dokumentace

```

---

## Požadavky a instalace

- **Python 3.10+**
- Jádro systému využívá **čistou standardní knihovnu Pythonu** (žádné povinné externí knihovny).

---

## Příklady spuštění simulace

### 1. Spuštění na reálných datech s definovaným počátkem a koncem testu
```bash
python3 main.py --start-date 2023-01-01 --end-date 2023-12-31
```

### 2. Spuštění s výpisem jednotlivých obchodů a zůstatků do formátu CSV
```bash
python3 main.py --start-date 2024-01-01 --end-date 2024-01-31 --print-csv --csv-limit 30
```

### 3. Vlastní exportní soubor a parametry hedge limitu
```bash
python3 main.py --start-date 2025-01-01 --end-date 2025-12-31 --hedge-limit 10000 --export-csv fxdata/backtest_2025.csv
```

---

## Dostupné CLI argumenty

| Přepínač | Výchozí hodnota | Popis |
| :--- | :--- | :--- |
| `--data-file` | `fxdata/eurczk-h4-bid-2017-01-02-2026-10-15.csv` | Cesta k souboru s reálnými historickými kurzy |
| `--start-date` | `None` (celé období) | **Počátek testu** (např. `2023-01-01` nebo `2023-01-01 00:00:00`) |
| `--end-date` | `None` (celé období) | **Konec testu** (např. `2023-12-31`) |
| `--orders-per-candle` | `1` | Počet generovaných klientských objednávek na jednu svíčku |
| `--spread` | `0.004` | Klientský spread (0.004 = 0.40 %, půl-spread 0.20 %) |
| `--hedge-limit` | `10000.0` | Limit NOP v EUR pro spuštění auto-hedgingu |
| `--export-csv` | `fxdata/simulation_results.csv` | Cesta pro uložení kompletního CSV výstupu |
| `--print-csv` | `False` | Vypíše CSV výstup přímo do konzole |
| `--csv-limit` | `None` (vše) | Maximální počet řádků vypsaných do konzole při `--print-csv` |
| `--seed` | `42` | Seed náhodného generátoru |
| `-v`, `--verbose` | `False` | Podrobné logování průběhu v reálném čase |

---

## Formát CSV výstupu (Sloupce)

Vygenerovaný CSV soubor (`fxdata/simulation_results.csv`) obsahuje chronologický záznam všech transakcí:

| Sloupec | Typ | Popis |
| :--- | :--- | :--- |
| `trade_id` | Text | Identifikátor pokynu klienta (`ORD-000001`) nebo zajištění (`HEDGE-0001`) |
| `timestamp` | ISO Datetime | Časové razítko exekuce obchodu |
| `event_type` | `CLIENT` / `HEDGE` | Typ události: klientský obchod nebo externí tržní hedge |
| `side` | `BUY` / `SELL` | Směr transakce v EUR z pohledu protistrany |
| `volume_eur` | Float | Objem transakce v EUR |
| `execution_rate` | Float | Realizovaný kurz (klientský Ask/Bid nebo tržní Mid pro hedge) |
| `volume_czk` | Float | Objem transakce v CZK |
| `spread_profit_czk` | Float | Zisk ze spreadu z tohoto obchodu v CZK (u hedge = 0) |
| `balance_eur` | Float | Zůstatek EUR sběrného účtu po provedení obchodu |
| `balance_czk` | Float | Zůstatek CZK sběrného účtu po provedení obchodu |
| `nop_eur` | Float | Aktuální Net Open Position v EUR po obchodu |
| `market_rate` | Float | Převládající tržní středový kurz v době obchodu |
| `running_pnl_czk` | Float | Průběžné Mark-to-Market PnL v CZK (`balance_czk + balance_eur * market_rate`) |
| `running_pnl_eur` | Float | Průběžné Mark-to-Market PnL v přepočtu na EUR |

---

## Spuštění unit testů

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```
Testy ověřují pricing, klientské toky, automatický hedging, integritu datového loaderu, správnost výpočtu zůstatků a generování CSV.
