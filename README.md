# Mateusz-Siwy-PracaINZ

## Opis

Projekt zawiera narzędzia do analizy danych DICOM. Umożliwia wczytywanie, przetwarzanie i analizowanie plików DICOM, generowanie histogramów dawki objętości (DVH) oraz eksport danych do formatu DataFrame oraz CSV.

## Funkcjonalności

*   **Wczytywanie danych DICOM:** Obsługa plików CT, RTSTRUCT, RTDOSE i RTPLAN.
*   **Analiza struktur:** Wyświetlanie dostępnych struktur (ROI) z plików RTSTRUCT.
*   **Obliczanie DVH:** Generowanie histogramów DVH dla wybranych ROI z uwzględnieniem różnych rozdzielczości interpolacji.
*   **Wykresy DVH:** Tworzenie i zapisywanie wykresów DVH do plików PNG.
*   **Eksport danych:** Zapisywanie danych DVH do plików DataFrame i CSV.
*   **Interfejs CLI:** Dostęp do funkcjonalności poprzez interfejs linii komend.

## Użycie

### Przykład użycia w kodzie (example.py)

```python
from dvh_analyzer.dicom_patient import DicomPatient

patient = DicomPatient("Patient1", "data/dicom/patient")

dvh_df = patient.get_dvh_data_frame(roi_id=3)

if dvh_df is not None:
    print(dvh_df)
    dvh_df.to_csv("dvh_data.csv")
else:
    print("Could not retrieve DVH data.")

resolutions = [None, 1.25, 0.625]

for res in resolutions:
    output_path = patient.generate_dvh_plot(
        roi_id=3, 
        output_dir="./comparison_dvh", 
        interpolation_resolution=res
    )
    print(f"Generated plot: {output_path}")

```

### Obliczenie DVH dla ROI o ID 3 i zapisanie wykresu do katalogu "output":
python -m dvh_analyzer.cli --path "data/dicom/patient" --roi-id 3 --dvh --output "./output_dvh"

### Obliczenie DVH dla ROI o ID 3, interpolacja do 1.25mm i zapisanie wykresu do katalogu "output":
python -m dvh_analyzer.cli --path "data/dicom/patient" --roi-id 3 --dvh --output "./output_dvh" --interpolation-resolution 1.25

### Wyświetlenie dostępnych ROI:
python dvh_analyzer/cli.py --path data/dicom/patient --list-rois