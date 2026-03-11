# Plotter G-code Web App

Lokalna aplikacja webowa do generowania G-code z obrazu albo rysunku odręcznego.

## Co jest w środku

- upload JPG/PNG,
- rysowanie na canvasie,
- konwersja `image -> SVG -> G-code`,
- pobieranie pliku `.gcode`,
- podstawowe strojenie parametrów,
- symulator plotera w przeglądarce dla ostatnio wygenerowanego G-code.

## Struktura projektu

```text
plotter-gcode-webapp/
├── backend/
├── frontend/
├── README.md
└── .gitignore
```

## Wymagania

- Python 3.10+
- `potrace` zainstalowany w systemie
- Visual Studio Code

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install potrace python3-venv
```

### macOS

```bash
brew install potrace
```

### Windows

Najprościej:
- zainstaluj `potrace` i dodaj go do `PATH`, albo
- uruchom backend przez Docker.

## Jak otworzyć w VS Code

1. Rozpakuj folder `plotter-gcode-webapp`.
2. Otwórz cały folder w Visual Studio Code.
3. Uruchom dwa terminale w VS Code.

## Terminal 1 — backend

### Linux / macOS

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Windows PowerShell

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend będzie działał na:

```text
http://localhost:8000
```

Sprawdzenie:

```text
http://localhost:8000/health
```

## Terminal 2 — frontend

### Linux / macOS

```bash
cd frontend
python3 -m http.server 3000
```

### Windows PowerShell

```powershell
cd frontend
python -m http.server 3000
```

Frontend będzie działał na:

```text
http://localhost:3000
```

## Docker dla backendu

```bash
cd backend
docker build -t plotter-backend .
docker run -p 8000:8000 plotter-backend
```

## Jak używać

1. Otwórz `http://localhost:3000`.
2. Wgraj obraz albo narysuj na canvasie.
3. Ustaw parametry.
4. Kliknij `Generuj G-code`.
5. Plik `output.gcode` zostanie pobrany.
6. Ten sam G-code zostanie automatycznie załadowany do symulatora.
7. Kliknij `Start`, żeby obejrzeć przebieg rysowania.

## Jak działa symulator

- szare linie oznaczają wszystkie wykonane ruchy,
- czarne linie oznaczają odcinki rysowane z opuszczonym pisakiem,
- czerwona kropka pokazuje aktualną pozycję głowicy,
- suwak `Prędkość podglądu` przyspiesza animację.

## Parametry startowe dla kolorowanek

- Threshold: `165-175`
- Min component area: `30`
- Potrace turdsize: `4`
- RDP epsilon: `1.5`
- Min path length: `15`

## Uwaga o sterowaniu pisakiem

Domyślnie:

```text
PEN_UP_CMD = M5
PEN_DOWN_CMD = M3 S1000
```

Jeśli masz serwo, zmień w formularzu np. na:

```text
M280 P0 S50
M280 P0 S90
```

## Ograniczenia symulatora

To jest prosty podgląd 2D oparty na parsowaniu `G0/G1` i komend podnoszenia/opuszczania pisaka. Nie symuluje:

- akceleracji,
- bufora firmware,
- dokładnego czasu ruchu,
- łuków `G2/G3`.
