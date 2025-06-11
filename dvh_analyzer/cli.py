#!/usr/bin/env python
"""
Command line interface for DICOM patient data processing.
Provides functionality for loading, processing, and analyzing DICOM files.
"""
import os
import sys
import argparse
from pathlib import Path
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.insert(0, root_dir)

from dvh_analyzer.utils.logger import G4RTLogger
from dvh_analyzer.dicom_patient import DicomPatient

logger = G4RTLogger("DicomCLI").get_logger()

# def list_rtstructs(patient):
#     rtstructs = patient.list_available_rtstructs()
#     print("\nAvailable RT Structure Sets:")
#     print("---------------------------")
#     for struct in rtstructs:
#         status = "* ACTIVE" if struct['current'] else ""
#         print(f"[{struct['index']}] {os.path.basename(struct['path'])} {status}")
#     return rtstructs

def list_rois(patient):
    print("\nAvailable ROIs:")
    print("--------------")
    for roi in patient.ROIs:
        print(f"ID: {roi['id']}, Name: {roi['name']}")

def process_patient(args):
    try:
        patient = DicomPatient(args.name, args.path)
        patient.set_verbose_level(args.verbose)

        print(patient)

        if args.list_rtstructs:
            list_rtstructs(patient)
            return

        if args.select_rtstruct is not None:
            success = patient.select_rtstruct(args.select_rtstruct)
            if not success:
                logger.error(f"Failed to select RTStruct with index {args.select_rtstruct}")
                return

        if args.list_rois:
            list_rois(patient)
            return

        if args.dvh:
            if args.roi_id is None:
                logger.info("Calculating DVH for all ROIs")
            else:
                logger.info(f"Calculating DVH for ROI ID {args.roi_id}")

                if args.output is not None:
                    interpolation_resolution = args.interpolation_resolution if args.interpolation_resolution else None
                    
                    dvh_data = patient.get_dvh_objects(args.roi_id, interpolation_resolution=interpolation_resolution)

                    if dvh_data:
                        roi_name = next((roi['name'] for roi in patient.ROIs if roi['id'] == args.roi_id), f"ROI {args.roi_id}")

                        fig, ax = plt.subplots(figsize=(12, 9))

                        for rtdose_filename, calculated_dvh in dvh_data:
                            if calculated_dvh:
                                volume_cc = calculated_dvh.volume

                                doses = calculated_dvh.cumulative.relative_volume.bincenters
                                volumes = calculated_dvh.cumulative.relative_volume.counts

                                interp_label = f" (interp: {interpolation_resolution}mm)" if interpolation_resolution else " (original)"
                                ax.plot(doses, volumes, linewidth=2, 
                                       label=f"{roi_name} ({os.path.basename(rtdose_filename)}{interp_label})")

                                stats_text = f"Min: {calculated_dvh.min:.1f} Gy\n"
                                stats_text += f"Mean: {calculated_dvh.mean:.1f} Gy\n"
                                stats_text += f"Max: {calculated_dvh.max:.1f} Gy"
                            else:
                                logger.error(f"Failed to get DVH object for {rtdose_filename}")

                        title = f'Cumulative DVH - {roi_name}'
                        if interpolation_resolution:
                            title += f' (Interpolation: {interpolation_resolution}mm)'
                        plt.title(title, fontsize=14)
                        
                        plt.grid(True, linestyle='--', alpha=0.7)
                        plt.xlabel('Dose (Gy)', fontsize=12)
                        plt.ylabel('Volume (%)', fontsize=12)
                        plt.ylim(0, 100)

                        if hasattr(patient, 'RTPlan') and patient.RTPlan and hasattr(patient.RTPlan, "DoseReferenceSequence"):
                            for ref in patient.RTPlan.DoseReferenceSequence:
                                if hasattr(ref, "TargetPrescriptionDose"):
                                    ref_dose = float(ref.TargetPrescriptionDose)
                                    ax.axvline(x=ref_dose, color='r', linestyle='--', alpha=0.5)
                                    break

                        plt.legend()
                        plt.tight_layout()
                        
                        filename = f"dvh_roi_{args.roi_id}"
                        if interpolation_resolution:
                            filename += f"_interp_{interpolation_resolution}mm"
                        filename += ".png"
                        
                        output_path = os.path.join(args.output, filename)
                        plt.savefig(output_path, dpi=150)
                        logger.info(f"Saved DVH plot to {output_path}")
                        plt.close(fig)
                    else:
                        logger.error("Failed to get DVH object from patient")
    except Exception as e:
        logger.error(f"Error processing patient data: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description='DICOM Patient CLI Tool')
    parser.add_argument('--path', '-p', type=str, required=True,
                        help='Path to DICOM files directory')
    parser.add_argument('--name', '-n', type=str, default="Patient",
                        help='Patient name')
    parser.add_argument('--verbose', '-v', type=int, choices=[0, 1, 2, 3], default=1,
                        help='Verbose level (0-3)')
    parser.add_argument('--list-rtstructs', action='store_true',
                        help='List available RT Structure Sets')
    parser.add_argument('--select-rtstruct', type=int,
                        help='Select RT Structure Set by index')
    parser.add_argument('--list-rois', action='store_true',
                        help='List available ROIs')
    parser.add_argument('--roi-id', type=int,
                        help='ID of ROI to process')
    parser.add_argument('--dvh', action='store_true',
                        help='Calculate DVH for specified ROI or all ROIs')
    parser.add_argument('--output', '-o', type=str,
                        help='Output directory for results')
    parser.add_argument('--interpolation-resolution', '-ir', type=float,
                        help='Interpolation resolution in mm (e.g., 1.0 for 1mm, 2.5 for 2.5mm). If not specified, uses original dose grid.')

    args = parser.parse_args()

    if args.output:
        os.makedirs(args.output, exist_ok=True)

    process_patient(args)

if __name__ == '__main__':
    main()