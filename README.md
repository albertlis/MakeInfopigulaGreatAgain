<div align="center">
  <h1>Make Infopiguła Great Again  nostalgic_face:</h1>
  <p><strong>Przywróć cotygodniowy newsletter Infopiguły, na który czekałeś!</strong></p>
  <p>
    <a href="https://www.python.org/downloads/release/python-380/"><img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8+-blue.svg"></a>
    <a href="https://github.com/microsoft/playwright-python"><img alt="Built with Playwright" src="https://img.shields.io/badge/built%20with-Playwright-2EAD33?logo=playwright"></a>
    <a href="https://astral.sh/blog/uv"><img alt="Managed with uv" src="https://img.shields.io/badge/managed%20with-uv-purple.svg?logo=python&labelColor=gray"></a>
  </p>
</div>

## 💡 Dlaczego ten projekt powstał?

Kiedyś Infopiguła była synonimem cotygodniowego, starannie przygotowanego newslettera, który w zwięzłej formie podsumowywał najważniejsze wydarzenia. To była prawdziwa "piguła" informacyjna, na którą czekało się cały tydzień.

Od kiedy Infopiguła stała się portalem z codziennymi aktualizacjami, jej pierwotny, unikalny charakter nieco się zatarł. Ten projekt to odpowiedź na tęsknotę za "starą" Infopigułą. Zamiast codziennie odwiedzać stronę, możesz ponownie cieszyć się cotygodniowym, automatycznym podsumowaniem, które symuluje oryginalne działanie serwisu.

## ⚙️ Jak to działa?

Skrypt działa w tle, wykonując w pełni zautomatyzowany cykl pracy:

1.  **Codzienny Scraper (Zbieranie danych)**: Każdego dnia o 10:00 skrypt uruchamia przeglądarkę, wchodzi na `infopigula.pl` i pobiera najnowsze wiadomości z kategorii "Polska" i "Świat". Zebrane artykuły są zapisywane lokalnie w pliku `data.json`.

2.  **Cotygodniowy Newsletter (Wysyłka maila)**: W każdą sobotę o 12:00 skrypt zbiera wszystkie wiadomości zgromadzone w ciągu tygodnia, formatuje je w czytelny e-mail HTML i wysyła na wskazany przez Ciebie adres. Po wysyłce, lokalna baza danych jest czyszczona.

## ⭐ Kluczowe funkcje

-   ✅ **Pełna Automatyzacja**: Skonfiguruj raz i zapomnij. Skrypt sam zbiera dane i wysyła podsumowania.
-   ✅ **Symulacja Oryginalnego Newslettera**: Otrzymujesz jedno, skondensowane podsumowanie tygodnia.
-   ✅ **Czysty Format Email**: Wiadomości są sformatowane w przejrzysty HTML z podziałem na kategorie.
-   ✅ **Łatwa Konfiguracja**: Wszystkie ustawienia znajdują się w jednym pliku `.env`.
-   ✅ **Niezawodność**: Wbudowane logowanie do pliku `scraper.log` pozwala na monitorowanie pracy skryptu.
-   ✅ **Elastyczność**: Możliwość wyboru przeglądarki (Chromium, Edge, Vivaldi) do procesu scrapingu.

## 📋 Wymagania

-   Python 3.8+
-   `uv` (ultraszybki instalator pakietów od Astral)
-   Konto e-mail (np. Gmail) do wysyłania podsumowań (zalecane jest użycie hasła do aplikacji).

## 🛠️ Instalacja i konfiguracja

1.  **Sklonuj repozytorium:**
    ```bash
    git clone https://github.com/twoj-uzytkownik/MakeInfopigulaGreatAgain.git
    cd MakeInfopigulaGreatAgain
    ```

2.  **Zainstaluj `uv` (jeśli jeszcze go nie masz):**
    ```bash
    # Na macOS / Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Na Windows
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
    *Więcej metod instalacji znajdziesz w [oficjalnej dokumentacji uv](https://astral.sh/docs/uv#installation).*

3.  **Zainstaluj zależności:**
    ```bash
    uv sync
    ```


4.  **Zainstaluj przeglądarki dla Playwright:**
    ```bash
    python -m playwright install
    ```

5.  **Skonfiguruj zmienne środowiskowe:**
    Utwórz plik `.env` w głównym katalogu projektu (możesz skopiować `example.env`). Następnie uzupełnij go swoimi danymi.

    ```dotenv
    # .env

    # --- USTAWIENIA EMAIL ---
    SRC_MAIL="twoj.email@gmail.com"
    SRC_PWD="twoje_haslo_do_aplikacji"
    DST_MAIL="odbiorca@example.com"
    SMTP_PORT=587

    # --- USTAWIENIA SCRAPERA ---
    BROWSER_TYPE="chromium" # chromium, edge, lub vivaldi
    VIVALDI_PATH="C:/Path/To/Vivaldi/Application/vivaldi.exe" # Wymagane dla Vivaldi
    ```
    > **Ważne:** W przypadku Gmaila, ze względów bezpieczeństwa, zaleca się wygenerowanie "Hasła do aplikacji" zamiast używania głównego hasła do konta. [Instrukcja Google](https://support.google.com/accounts/answer/185833)

## ▶️ Uruchomienie

Aby uruchomić skrypt, który będzie działał w tle i wykonywał zaplanowane zadania, po prostu wykonaj polecenie:

```bash
python main.py
```

Skrypt natychmiast wykona pierwsze zbieranie danych, a następnie będzie działał zgodnie z harmonogramem. Aby go zatrzymać, użyj `Ctrl+C`.

Zaleca się uruchomienie skryptu na serwerze lub komputerze, który jest stale włączony, aby zapewnić ciągłość działania (np. przy użyciu `screen` lub jako usługa systemowa).
