# QuizAi — Asystent quizów dla Windows

Python 3.13 + PySide6: zaznaczony obszar ekranu → obrazy w RAM → jedno żądanie OpenAI Responses API → podpowiedź. Do nauki i pracy za zgodą prowadzącego. Nie klika odpowiedzi, nie wykonuje kodu z obrazów i nie obchodzi zabezpieczeń.

**Wersja 0.2 — do odbioru na docelowym pulpicie, nie gotowy instalator.** Testy offline sprawdzają aplikację, nie trafność modelu. Brak gwarancji poprawnej odpowiedzi albo ukończenia jej w 20 sekund.

## Pierwsze uruchomienie

Wymagane: Windows 11 x64, Python 3.13 z python.org, działający zasobnik systemowy.

1. Pobierz repozytorium.
2. Otwórz PowerShell w jego folderze i wykonaj:

~~~powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
~~~

3. Kliknij dwukrotnie **Uruchom_Asystenta.cmd**. Nie musisz aktywować venv.
4. W oknie głównym przejdź do **Ustawienia i diagnostyka**, zapisz własny klucz API i ustaw obszar pytania.
5. Wróć do strony z pytaniem. Naciśnij **Ctrl+M**.

Krzyżyk chowa okno do zasobnika. Ponowne uruchomienie lub dwuklik ikony otwiera istniejące okno. **Zakończ program** kończy pracę i przerywa żądanie bez blokowania GUI. Po aktualizacji zakończ poprzednią wersję przed uruchomieniem nowej.

Alternatywa diagnostyczna:

~~~powershell
.\.venv\Scripts\python.exe -m quiz_assistant
~~~

Brak środowiska/zależności powoduje komunikat. Jeśli .venv wskazuje usuniętego Pythona, utwórz środowisko ponownie. Nie kopiuj .venv pomiędzy folderami.

## Skróty i paczki

| Skrót | Działanie |
|---|---|
| Ctrl+M | Analizuje paczkę; jeśli pusta, przechwytuje jeden obraz i analizuje |
| Ctrl+Shift+M | Dodaje ujęcie do paczki, bez wysyłania do API |
| Ctrl+B | Pokazuje/chowa istniejący panel |
| Ctrl+Alt+M | Anuluje operację, usuwa wynik i czyści paczkę |

Paczka: maksymalnie **6 ujęć jednego pytania**, do 256 MiB surowych obrazów. Podgląd, kolejność i usuwanie są w zakładce **Ujęcia**. Dla długiego zadania dodaj ujęcie przed i po przewinięciu; dla listy — po rozwinięciu opcji. Paczka jest zużywana przy rozpoczęciu analizy; po błędzie zbierz ją ponownie.

Każda analiza to jedno żądanie, bez automatycznego ponawiania lub zmiany modelu. W czasie pracy dodatkowe wywołania są ignorowane. Po anulowaniu nowa analiza jest dostępna po zakończeniu sprzątania workera.

Wynik dotyczy **zapisanego obrazu**, nie bieżącej strony. Zegar, hover, ruch myszy i późniejsze przewijanie nie odrzucają odpowiedzi. Upewnij się sam, że używasz jej dla właściwego pytania — panel pokazuje fragment pytania, czas zrzutu i generację.

Przed przechwytywaniem aplikacja chowa panel i okno główne oraz synchronizuje kompozytor Windows. Zmiana DPI/geometrii lub utrata monitora wymaga ponownego ustawienia obszaru.

## Odpowiedzi

Kontrakt: pojedynczy/wielokrotny wybór, prawda/fałsz, luki, liczby, listy rozwijane, pary, kolejność, odpowiedzi otwarte, kod i wynik kodu, zadania mieszane.

Każde pole jest walidowane osobno. Niepoprawne pole nie ukrywa poprawnych pozostałych. Dla niewidocznych opcji listy model może podać wyliczoną wartość, ale aplikacja nie wymyśla litery ani pozycji. Rozpoznanie treści i pomieszanych pytań zależy od modelu.

Tekst nie jest interpretowany jako HTML. Kod pozostaje tekstem, z zachowaniem liter, operatorów i wcięć. Pełny wynik jest w zakładce **Pełna odpowiedź**; skróty w panelu są oznaczone.

## Modele, czas i koszty

- Domyślnie **gpt-6.1-sol / medium**, 6000 tokenów wyjścia, 20 sekund łącznie na przygotowanie obrazów, API i walidację.
- Presety: Sol medium, Sol low i ekonomiczny Luna low. Preset nie zmienia budżetu.
- Model może nie zdążyć. Wynik spóźniony lub anulowany nie jest pokazywany.
- Limit sesji domyślnie 0,50 USD. Rezerwa rośnie z liczbą obrazów i limitem wyjścia.
- Koszt szacujemy na podstawie usage i lokalnej tabeli cen — również gdy odpowiedź odrzucono.
- Bez usage koszt pozostaje **niepewny**, nie zerowy. Anulowanie nie gwarantuje przerwania naliczania po stronie dostawcy.
- Budżet jest lokalny, resetuje się po restarcie i nie jest twardym limitem konta. Ustaw własne limity także po stronie dostawcy.
- Test dostępu sprawdza autoryzację i model; nie wysyła obrazów ani nie generuje odpowiedzi.
- Brak importu materiałów, profili kursów, OCR, MOV, PDF, prezentacji lub wyszukiwania kontekstu.

Konfigurację oparto na [dokumentacji GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) i [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). Dostęp na konkretnym koncie, trafność i rzeczywisty czas nie były sprawdzane płatnymi wywołaniami.

## Wygląd

Ciemny/jasny motyw, widoczność tła 0–100% (domyślnie 95%), jasność, kontrast tekstu, tekst 12–24 px i szerokość 320–720 px. Obwódkę można wyłączyć albo osobno ustawić jej widoczność. Przy tle 0% i wyłączonej obwódce pozostaje sam tekst. Podgląd działa na żywo; anulowanie przywraca poprzedni wygląd. Krycie nie zmienia przezroczystości tekstu.

Panel ma flagi Qt i Win32 zapobiegające aktywacji i przepuszczające wejście. Wymaga to odbioru na docelowym Windows/Edge/Chrome — nie jest deklaracją „niewykrywalności”.

## Klucz API i prywatność

**Każdy użytkownik wpisuje własny klucz. Repozytorium nie zawiera klucza.**

- Zapis przez backend **Windows Credential Manager**, usługa QuizAssistantPoC.OpenAI, użytkownik default. Brak fallbacku do pliku tekstowego.
- QSettings nie zawiera sekretów ani obrazów.
- Opcjonalna zmienna OPENAI_API_KEY ma pierwszeństwo. Jej wartości nie pokazujemy. Gdy jest ustawiona, edycja klucza w oknie jest wyłączona.
- Nie zapisuj klucza w .env w repozytorium, kodzie, dokumentacji, issues ani commitach.
- .gitignore wyklucza typowe pliki sekretów, logi, obrazy przechwyceń i .venv.
- Zrzuty i odpowiedzi pozostają w RAM. Nie zapisujemy ich na dysku; nie gwarantuje to braku kopii w systemowym swap/crash dump Windows.
- Wybrane obrazy wysyłane są do OpenAI przy analizie, z store=false. Nie oznacza to obietnicy zerowej retencji dostawcy. Wybieraj kadr bez danych osobowych.
- Dziennik rotowany (512 kB + 3 kopie) zawiera zdarzenia, typy błędów, wymiary, czas i hash — bez klucza, pytań i obrazów. Otworzysz go w ustawieniach; jest w lokalnym katalogu danych aplikacji użytkownika.
- Magazyn nie chroni przed złośliwym oprogramowaniem działającym na tym samym koncie Windows.

## Testy i odbiór

~~~powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/check_secrets.py
~~~

Testy blokują prawdziwe API i nie wymagają klucza. Zawierają 48 ręcznie opracowanych pytań z FP/teorii kategorii, przypadki wszystkich typów odpowiedzi i tekstowe odpowiedniki zgłoszonych przykładów. Nie mierzą odczytu screenshotów ani wiedzy modelu.

**Raport i próby ręczne: [TEST_REPORT.md](TEST_REPORT.md).**

Symulator (simulator/index.html) ma 10 typów zadań, zegar i rejestr fokusu, widoczności, klawiatury, kliknięć i scrolla. Nie łączy się z API. Instalator Windows będzie oddzielnym etapem po akceptacji stabilności.
