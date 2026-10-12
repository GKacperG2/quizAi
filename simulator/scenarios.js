// Local, synthetic scenarios for UI/focus/capture testing. No network and no model calls.
const scenarios = [
  {
    type: "Pojedynczy wybór",
    question: "Która operacja JS zachowuje liczbę elementów zwykłej tablicy?",
    html: '<label class="option"><input type="radio" name="a"> A. map</label><label class="option"><input type="radio" name="a"> B. filter</label>'
  },
  {
    type: "Wielokrotny wybór",
    question: "Zaznacz wymagania monoidu.",
    html: '<label class="option"><input type="checkbox"> Łączność</label><label class="option"><input type="checkbox"> Element neutralny</label><label class="option"><input type="checkbox"> Przemienność</label>'
  },
  {
    type: "Kilka zdań prawda/fałsz",
    question: "Oceń oba stwierdzenia.",
    html: '<p>Każdy izomorfizm jest morfizmem.</p><label><input type="radio" name="tf1"> Prawda</label> <label><input type="radio" name="tf1"> Fałsz</label><p>Każdy morfizm jest izomorfizmem.</p><label><input type="radio" name="tf2"> Prawda</label> <label><input type="radio" name="tf2"> Fałsz</label>'
  },
  {
    type: "Dwie listy rozwijane",
    question: "Wybierz element neutralny dla dwóch działań.",
    html: '<p><label>Dodawanie liczb całkowitych: <select><option></option><option>0</option><option>1</option><option>-1</option></select></label></p><p><label>Mnożenie liczb całkowitych: <select><option></option><option>0</option><option>1</option><option>-1</option></select></label></p>'
  },
  {
    type: "Luka i wartość liczbowa",
    question: "Uzupełnij dwa pola.",
    html: '<p><label>Operacja map i spłaszczenia monady: <input aria-label="Nazwa operacji"></label></p><p><label>Suma [1,2,3] po reduce((a,x)=>a+x,0): <input type="number" aria-label="Suma"></label></p>'
  },
  {
    type: "Dopasowywanie",
    question: "Dopasuj Maybe i Either do opisów w konwencji Left=błąd, Right=sukces.",
    html: '<p>1. Maybe &nbsp; 2. Either</p><p>A. Błąd lub sukces &nbsp; B. Wartość lub brak</p><label>1 → <select><option></option><option>A</option><option>B</option></select></label> <label>2 → <select><option></option><option>A</option><option>B</option></select></label>'
  },
  {
    type: "Ustalanie kolejności",
    question: "Ułóż kroki obliczenia (2 + 3) * 4: A: pomnóż przez 4; B: dodaj 2 i 3.",
    html: '<label>Kolejność: <input placeholder="np. A, B"></label>'
  },
  {
    type: "Kod i wynik wykonania",
    question: "Podaj wynik poniższego kodu JavaScript. Zachowaj wielkość liter.",
    html: '<pre>const value = "A";\nconsole.log(value === "a");\nconsole.log([1, 2].map(x => x * 2));</pre><label>Wynik:<textarea></textarea></label>'
  },
  {
    type: "Odpowiedź otwarta i kod",
    question: "Wyjaśnij funkcję tożsamościową i zapisz ją w JS.",
    html: '<label>Wyjaśnienie:<textarea></textarea></label><label>Kod:<textarea style="font-family:Consolas,monospace"></textarea></label>'
  },
  {
    type: "Długie zadanie — paczka ujęć",
    question: "Jedno zadanie z dwoma polami: oblicz sumę i iloczyn liczb 2 oraz 3.",
    html: '<label>Pole 1 — suma: <input type="number"></label><p style="height:700px">Przewiń, aby zobaczyć drugie pole. To nadal to samo pytanie.</p><label>Pole 2 — iloczyn: <input type="number"></label>'
  }
];
