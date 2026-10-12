# Raport stabilizacji — 2026-10-12

Status: implementacja do odbioru użytkownika. Bez płatnych testów API i bez instalatora.

## Sprawdzone automatycznie

Ostatni pełny przebieg: **153 testy zaliczone**, Python 3.13, Windows, Qt offscreen.

- Runtime bez klucza, komunikat błędu zależności, launcher niezależny od katalogu terminala.
- Blokada instancji, aktywowanie pierwszego okna, błąd blokady/listen, restart po zamknięciu i nagłym wyjściu własnego procesu testowego.
- Faktyczny przepływ w wątkach Qt z atrapą przechwytywania i asynchronicznego API.
- Jedna operacja, ignorowanie powtórzeń, anulowanie przed capture, podczas capture i API; brak spóźnionego panelu; zamykanie bez blokowania GUI.
- Deadline obejmujący kodowanie obrazów; przerwanie transportu w atrapach; brak retry.
- Usage odpowiedzi odrzuconej/spóźnionej/anulowanej, nieznany koszt, idempotentne rozliczenie, skalowanie rezerwy.
- Paczka do 6 obrazów, kolejność, usuwanie, czyszczenie; jeden request z uporządkowanymi obrazami.
- Brak kontroli aktualnego ekranu. Zmiana ekranu po zapisaniu ujęcia nie wpływa na wynik.
- Mapowanie DPI 100/125/150/200% i ujemne współrzędne; rozmiar i bufor z atrapy MSS; PNG w RAM.
- Wszystkie typy pól, błędne referencje, częściowa walidacja, niewidoczne opcje, mieszane zadania/pytania.
- Negacje, wielkość liter, operatory, literały i formatowanie kodu.
- 48 ręcznie opracowanych pytań FP/teorii kategorii przez atrapę API.
- Tekstowe odpowiedniki zgłoszonych zadań: kod szafki, pierwiastki, kule, suma. Sprawdzono kontrakt i renderowanie oczekiwanych odpowiedzi, NIE odczyt obrazów przez model.
- PlainText w panelu, pełny tekst w oknie, oznaczone skróty, flagi Qt wejścia/fokusu, nieprzezroczystość tekstu.
- Wygląd, presety, zapis ustawień, zachowanie budżetu przy migracji i błędzie konfiguracji.
- Magazyn klucza na atrapie; brak klucza w QSettings. Rotacja dziennika, oddzielenie loggerów HTTP.
- Rejestracja/wycofanie skrótów na atrapie Win32.

Przegląd wizualny: syntetyczne okno główne, panel jasny/ciemny i ustawienia wyglądu wyrenderowane i obejrzane w Qt offscreen. Podgląd nie zawiera obrazu pulpitu i nie trafia do repozytorium.

## Nieprzetestowane — nie traktować jako zaliczone

- Trafność, czytanie symboli/kodu ze screenshotów, wykrywanie różnych pytań i realny czas Sol/Luna.
- Dostępność modeli na konkretnym koncie, rzeczywisty koszt i żywe API.
- Nowa wersja w Edge/Chrome: zwykłe okno, maksymalizacja, F11, 20 wywołań, kliknięcia/scroll/klawiatura pod panelem.
- Win32 fokus i click-through na rzeczywistym pulpicie; przytrzymanie skrótu.
- Rzeczywisty kadr MSS, monitor po lewej i przełączanie DPI na sprzęcie użytkownika.
- Instalacja na czystym Windows, uszkodzony magazyn Windows i systemowe zamknięcie sesji.
- Brak obrazów w systemowym swap/crash dump; aplikacja nie kontroluje tych mechanizmów.

## Ręczna brama odbioru

1. Zakończ poprzednią wersję. Uruchom nową dwuklikiem; powtórz — ma pojawić się to samo okno.
2. Otwórz symulator, ustaw kadr z pytaniem i opcjami, wróć do strony, wyczyść rejestr.
3. Podgląd wyglądu nie wymaga AI. Pokaż panel i wróć do symulatora. Pokazanie/chowanie samego panelu nie powinno dodawać blur/visibilitychange. Wejście do ustawień zmienia fokus i nie liczy się jako błąd panelu.
4. Klikaj, przewijaj i pisz pod panelem. Powtórz w Edge i Chrome, normalnie, zmaksymalizowane i F11.
5. Dopiero po decyzji użytkownika testuj płatne odpowiedzi: pojedyncze pytanie oraz paczkę po przewinięciu/rozwinięciu listy. Porównuj treść, nie samą literę.
6. Sprawdź anulowanie oraz Zakończ podczas analizy: brak starego wyniku i pozostawionego workera.
7. Sprawdź zmianę DPI/monitora, ponownie ustaw obszar. Niedostępne konfiguracje oznacz „nieprzetestowane”.

Instalator dopiero po akceptacji prób. Nie gwarantujemy bezbłędnych odpowiedzi modelu.
