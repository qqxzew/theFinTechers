# NÁVRH oznámení o podezřelém obchodu (FAÚ, Metodický pokyn č. 4) – SYNTETICKÁ DATA

## I. Identifikace oznámení (reference)
Interní reference případu: CNB-K000961 (pseudonym klienta c-ade0ffbd). Datum návrhu: 2026-10-19. Stav: NÁVRH – syntetická data, nejde o skutečné oznámení.

## II. Povinná osoba (odesílatel)
Ukázková banka a.s. (SYNTHETIC), IČO: doplní banka, adresa: doplní banka.

## III. Subjekt obchodu
Identifikační údaje subjektu: z KYC banky (v syntetických datech nejsou k dispozici). Pseudonym: c-ade0ffbd.

## IV. Druh podezření
Podezření na legalizaci výnosů z trestné činnosti (kandidátní případ; konečné posouzení provádí odpovědná osoba).

## V. Popis podezřelého obchodu a podstatných okolností
Klient je fyzická osoba vedená v AML riziku high, politicky exponovaná osoba (PEP). Smlouva byla uzavřena osobně 1 950 dnů před 31. červencem 2026. V červenci 2026 přijal klient 30 příchozích transakcí od 29 odesílatelů v celkové výši 371 192,97 Kč; největší jednotlivý příchozí převod činil 58 196,23 Kč. Ve stejném období provedl 50 odchozích transakcí na 48 různých účtů v celkové výši 1 065 797,63 Kč. Celkový červencový objem (součet příchozích a odchozích) činil 1 436 990,60 Kč, přičemž příchozí transakce tvoří 25,83 % tohoto objemu. Spustil se signál R-A (diskrepance s profilem klienta), neboť denní objem přesáhl 25 % projektovaného měsíčního objemu a současně přesáhl trojnásobek průměrného denního objemu v druhém čtvrtletí; projektovaný měsíční objem podle profilu klienta je 625 001,16 Kč. Současně se aktivoval signál R-B (vysokoriziková jurisdikce / PEP), protože klient je PEP a provedl dva odchozí převody vyšší než 100 000 Kč. Z celkové odchozí částky směřovalo 96,54 % k populárním protistranám (účty používané nejméně 100 klienty banky), žádná částka nesměřovala k vzácným protistranám (používaným maximálně 3 klienty), 3,46 % k středně vzácným protistranám; největší jednotlivý příjemce obdržel 13,11 % celkové odchozí částky. Z příchozích prostředků pocházelo 82,34 % od opakovaných nebo populárních plátců a 82,34 % od populárních účtů (institucionální protistrany s vysokým stupněm propojení, konkrétně 10 odesílatelů). Vzájemné transakce (účty vystupující současně jako odesílatel i příjemce) představovaly 9,43 % celkového objemu. Medián retenční míry (podíl příchozí částky, který zůstal na účtu) činil 0,0; medián prodlevy mezi ukončením příchozího cyklu a odchozí transakcí činil 14,28 hodin. Z největšího příchozího převodu bylo 41,98 % odesláno v následujících 24 hodinách; před největším příchozím převodem proběhlo 28 transakcí. Během července byl zaznamenán 19 cyklů příchozí-odchozí transakce; maximální součet příchozích transakcí v jakémkoli 24hodinovém okně činil 63 582,88 Kč. Z celkového POČTU odchozích plateb směřovalo 96 % k populárním protistranám, což naznačuje běžné výdajové vzorce. Exkulpační signál E2 (vysoký podíl výdajů u běžných protistran) vysvětluje signál R-A. Exkulpační signály E3 (zdroj prostředků z opakujících se příjmů) a E4 (institucionální protistrany – zaměstnavatel, pojišťovna, platforma) potvrzují legitimní původ značné části příchozích prostředků. Signál R-B (PEP, velké odchozí transakce) zůstává nevysvětlen a představuje podezření na legalizaci výnosů z trestné činnosti; případ je kandidátem na hlášení.

## VI. Provedení / neprovedení / odklad obchodu
Obchod proveden / neproveden / odložen: DOPLNÍ ČLOVĚK. Návrh systému: neprovádí se žádné rozhodnutí. Pokus o obchod se oznamuje také.

## VII. Výjimka z identifikace a kontroly klienta
Výjimka z identifikace a kontroly klienta: nebyla zaznamenána.

## VIII. Kontaktní osoba povinné osoby
Pověřená osoba (§ 22 zákona č. 253/2008 Sb.); e-mail: aml-contact@example.invalid; telefon: doplní banka.

## IX. Podání oznámení
Způsob a datum podání: DOPLNÍ ČLOVĚK (podání není součástí systému).

## X. Přílohy
Přílohy: (1) strukturovaný JSON případu, hash fda993fee7c5729a; (2) seznam signálů: R-A:K000961, R-B:K000961; (3) hlava auditního řetězce: 35d107de6b1dfae3

## Upozornění kontroly (QA) – k vyřešení člověkem před použitím

- number_not_in_case: number '2026' not supported by case values (věta 1)
- number_not_in_case: number '2026' not supported by case values (věta 2)
- number_not_in_case: number '100 000' not supported by case values (věta 6)
