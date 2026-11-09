Lighthouse (het reservatiesysteem van het hotel) heeft zijn schermen veranderd. De zelftest van de robot vindt
niet meer alles wat hij nodig heeft. Lees eerst CLAUDE.md en volg die afspraken.

Het bewijs staat in lighthouse-explore/repair/:
- health.json: welk onderdeel niet meer klopt en waarom (reservatielijst, detailpagina of planbord);
- <onderdeel>.html: de nieuwe pagina zoals de robot ze nu ziet.

Opdracht:
1. Vergelijk de nieuwe pagina met wat de code verwacht (src/hotel_checkin/pms/lighthouse.py: self_test, _DETAIL_JS,
   _GENERAL_LOADED, _TRANSACTIONS_LOADED, list_page; src/hotel_checkin/pms/lighthouse_parse.py) en de tests in tests/.
2. Pas de code zo aan dat de robot de nieuwe pagina juist leest. Verander alleen wat nodig is. De robot blijft
   alleen lezen in Lighthouse, behalve de schrijfacties die in CLAUDE.md staan; voeg er geen toe.
3. Voeg een test toe met een stuk van de nieuwe pagina (geen namen, e-mailadressen of telefoonnummers van gasten).
4. Draai pytest -q en ruff check . tot alles slaagt.
5. Schrijf config/repair.json met {"id": "<UTC-tijd JJJJMMDDUUMM>", "summary": "<één zin in het Nederlands voor
   iemand zonder IT-kennis: wat er in Lighthouse veranderde en wat de robot nu anders leest>", "at": "<UTC-tijd ISO>"}.
Commit niets zelf; de workflow doet dat. Kun je het niet oplossen, schrijf dan geen config/repair.json en leg in
je antwoord uit wat je vond.
