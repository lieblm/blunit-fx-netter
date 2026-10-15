# Role
Jsi expert na Python a algoritmické obchodní systémy. Tvým úkolem je vytvořit počáteční repozitář pro Proof of Concept (PoC) aplikaci "Blunit FX Internalizer".

# Kontext a cíl
Systém funguje jako interní Market Maker pro klientské směny EUR/CZK. Místo toho, aby každou klientskou směnu posílal na externí trh, uspokojuje je z vlastního sběrného účtu (internalizace). Zisk tvoří vybraný spread. Pokud čistá otevřená pozice (Net Open Position - NOP) přesáhne definovaný limit, systém provede zajišťovací obchod (Hedge) na externím trhu pro vyrovnání rizika. 
Cílem PoC je ověřit tuto logiku na nasimulovaných datech s minimem kódu.

# Funkční požadavky (PoC Scope)
1. **Zpracování pokynů:** Vytvoř funkci, která vygeneruje dummy stream klientských objednávek (timestamp, směr nákup/prodej EUR, objem v EUR). 
2. **Pricing model:** Pro jednoduchost použij statický tržní středový kurz (např. 24.50 CZK/EUR). Klientský kurz bude střed ± fixní spread (např. 0.4 %).
3. **Internalizace (Engine):** 
   - Třída, která přijímá objednávky a aktualizuje bilance sběrného účtu.
   - Sleduje aktuální NOP (převis nakoupených nebo prodaných EUR).
   - Inkasuje a sčítá zisk ze spreadu z každého klientského obchodu.
4. **Auto-Hedging:** Pokud absolutní hodnota NOP překročí `HEDGE_LIMIT` (např. 10 000 EUR), engine provede hedge trade na externím trhu za středový kurz (bez spreadu), čímž vynuluje svou NOP.
5. **Výstup:** Jednoduchý report do konzole, který po proběhnutí simulace vypíše celkový objem obchodů, počet hedge transakcí, finální NOP a celkový vygenerovaný zisk.

# Technické požadavky
- Čistý Python 3.10+ (standardní knihovny, maximálně `pandas` pokud to usnadní práci).
- Žádná databáze, stav drž in-memory.
- Jednoduchá a modulární architektura (např. moduly `models.py`, `engine.py`, `simulator.py`, `main.py`).

# Výstup
Vygeneruj kompletní strukturu repozitáře, zdrojové kódy a `README.md` s instrukcemi, jak simulátor spustit. Kód musí být spustitelný ihned. Názvy proměnných a komentáře v kódu piš anglicky.