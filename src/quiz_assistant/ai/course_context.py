"""Curated, static study context supplied with the application.

This is intentionally concise and version controlled. It is not a runtime file import,
RAG index, or a source that may override the question visible in a screenshot.
"""

COURSE_CONTEXT_VERSION = "category-fp-js-pl-v1"

# Allowance used only by the local budget reservation. It is deliberately rounded up;
# billing is reconciled later from the provider's actual usage when available.
COURSE_CONTEXT_TOKEN_RESERVE = 3_000

COURSE_CONTEXT = """POMOCNICZY KONTEKST KURSU — TEORIA KATEGORII I FP W JAVASCRIPT

Zasady użycia:
- To skrót pojęć, nie treść bieżącego zadania. Treść, definicje, kod i konwencje
  widoczne na obrazie mają pierwszeństwo.
- Nie dopowiadaj zachowania nieznanej biblioteki. W JavaScript nazwy map, chain,
  flatMap, fold i ap mogą zależeć od implementacji.
- Nie nazywaj tej notatki źródłem ani nie cytuj jej w odpowiedzi.

Teoria kategorii:
- Kategoria składa się z obiektów i morfizmów między nimi. Każdy obiekt A ma
  identyczność id_A. Morfizmy można składać, gdy zgadzają się dziedzina i
  przeciwdziedzina; składanie jest łączne, a identyczności są neutralne.
- Przykłady: Set — zbiory i funkcje; Grp — grupy i homomorfizmy grup; Ab — grupy
  abelowe; Ring/Rng — pierścienie i właściwe homomorfizmy; Vect — przestrzenie
  wektorowe i przekształcenia liniowe; Top — przestrzenie topologiczne i funkcje
  ciągłe; Met — przestrzenie metryczne z morfizmami zależnymi od przyjętej definicji.
- Izomorfizm f: A -> B ma odwrotność g: B -> A taką, że g∘f=id_A i f∘g=id_B.
- Produkt A×B to obiekt P z projekcjami p1: P->A i p2: P->B. Dla każdych
  f: X->A i g: X->B istnieje dokładnie jeden h: X->P, dla którego p1∘h=f i
  p2∘h=g. W Set jest to iloczyn kartezjański.
- Funktor F: C->D mapuje obiekty i morfizmy, zachowując identyczności oraz
  składanie. Funktor kowariantny zachowuje kierunek; kontrawariantny odwraca
  kierunek i kolejność składania. Endofunktor ma tę samą kategorię jako domenę
  i kodomenę.
- Transformacja naturalna η: F=>G między równoległymi funktorami przypisuje
  każdemu A morfizm η_A: F(A)->G(A), a kwadraty naturalności komutują:
  G(f)∘η_A = η_B∘F(f).
- Monoid algebraiczny to zbiór M z łącznym działaniem <> i elementem neutralnym e.
  Przykłady: liczby z dodawaniem i 0, liczby z mnożeniem i 1, napisy z konkatenacją
  i pustym napisem. Każdy monoid można przedstawić jako kategorię z jednym obiektem;
  nie oznacza to, że definicja algebraiczna brzmi „rodzaj kategorii”. Semigrupa ma
  działanie łączne, ale nie musi mieć elementu neutralnego.
- Monada na kategorii to endofunktor T wraz z unit η: Id=>T i multiplication
  μ: T²=>T, spełniający prawa monady. W kodzie równoważnie spotyka się of/pure
  i flatMap/chain (albo map plus join). Obowiązują lewa i prawa tożsamość oraz
  łączność. Monada nie jest po prostu pudełkiem, z którego zawsze można wyjąć wartość.

Programowanie funkcyjne w JavaScript:
- Funkcje są wartościami pierwszej klasy: można je przypisywać, przekazywać,
  zwracać i przechowywać w obiektach lub tablicach. Funkcja wyższego rzędu przyjmuje
  funkcję lub ją zwraca. Funkcje strzałkowe są wyrażeniami funkcyjnymi o leksykalnym
  this; nie są zamiennikiem zwykłej funkcji w każdej sytuacji.
- Domknięcie łączy funkcję z jej środowiskiem leksykalnym, więc funkcja może używać
  zmiennych z zewnętrznego zakresu także po zakończeniu tego wywołania.
- Funkcja czysta dla tych samych argumentów daje ten sam wynik i nie ma obserwowalnych
  efektów ubocznych. Odczyt zmiennego stanu zewnętrznego również łamie czystość.
- Currying zamienia funkcję wielu argumentów w łańcuch funkcji jednoargumentowych.
  Częściowa aplikacja wiąże część argumentów. Pojęcia są powiązane, ale nie identyczne.
  Ramda R.curry pozwala m.in. podawać argumenty partiami aż do osiągnięcia arności.
- map przekształca wartość w kontekście bez zmiany struktury kontekstu. Funktor musi
  zachowywać identyczność i składanie. Samo nazwanie metody fmap nie dowodzi praw.
- flatMap/chain mapuje funkcją zwracającą ten sam rodzaj kontekstu i spłaszcza wynik.
  join spłaszcza M(M(a)) do M(a). ap zwykle aplikuje funkcję w kontekście do wartości
  w kontekście. fold eliminuje strukturę do zwykłej wartości, ale dokładna sygnatura
  zależy od typu lub biblioteki.
- Maybe opisuje opcjonalność: Just/Some przechowuje wartość, Nothing/None oznacza jej
  brak. map/chain na Nothing zwykle propaguje Nothing. Maybe nie jest pełnym
  odpowiednikiem try/catch, bo samo z siebie nie przechowuje opisu błędu.
- Either ma rozłączne warianty Left i Right. Zwyczajowo Right oznacza sukces, a Left
  błąd wraz z informacją; map/chain działają po prawej stronie.
- IO opisuje obliczenie z efektem ubocznym jako wartość do kontrolowanego uruchomienia.
  Task (np. data.task) opisuje leniwe obliczenie asynchroniczne z sukcesem lub błędem;
  dokładne metody i sposób uruchomienia zależą od biblioteki.
- Memoizacja buforuje wyniki według klucza. Jest bezpieczna znaczeniowo głównie dla
  funkcji czystych, lecz poprawność zależy też od kompletnego i stabilnego klucza.
- Generator function* zwraca iterator. yield wstrzymuje wykonanie, a next() je wznawia
  i zwraca obiekt {value, done}; zachowany jest stan wykonania generatora.

Przy analizie kodu licz dokładny wynik zgodnie z JavaScript i kodem z obrazu. Zwracaj
uwagę na coercion, === kontra ==, mutacje, kolejność efektów, zakres leksykalny,
obsługę null/undefined, leniwość oraz to, czy pokazana metoda faktycznie zwraca wartość.
"""
