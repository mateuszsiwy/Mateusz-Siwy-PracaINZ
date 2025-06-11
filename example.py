from dvh_analyzer.dicom_patient import DicomPatient
import pandas as pd

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