import os
import pydicom
import numpy as np
import pandas as pd
from scipy import interpolate
from pydicom.errors import InvalidDicomError
from dicompylercore import dvhcalc
import matplotlib.pyplot as plt
from collections import namedtuple

RTStructDosePair = namedtuple("RTStructDosePair", ["rtstruct", "rtdose", "identifier"])

class DicomPatient:
    def __init__(self, patient_name, data_path, logger_instance=None):
        self.patient_name = patient_name
        self.data_path = data_path
        self.logger = logger_instance if logger_instance else self._get_default_logger()

        self.CT = []
        self.RTStructs = []
        self.RTDoses = []
        self.RTPlan = None
        self.ROIs = []

        self._load_dicom_data()
        if self.RTStructs:
            self._process_rtstructs()

    def _get_default_logger(self):
        import logging
        logger = logging.getLogger(self.patient_name)
        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _load_dicom_data(self):
        self.logger.info(f"Loading DICOM data from: {self.data_path}")
        if not os.path.isdir(self.data_path):
            self.logger.error(f"Data path does not exist or is not a directory: {self.data_path}")
            return

        for root, _, files in os.walk(self.data_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(file_path, force=True)
                    modality = ds.get("Modality", "").upper()

                    if modality == "CT":
                        self.CT.append(ds)
                    elif modality == "RTSTRUCT":
                        self.RTStructs.append(ds)
                        self.logger.info(f"Loaded RTSTRUCT: {file_path}")
                    elif modality == "RTDOSE":
                        self.RTDoses.append(ds)
                        self.logger.info(f"Loaded RTDOSE: {file_path}")
                    elif modality == "RTPLAN":
                        if self.RTPlan is None:
                            self.RTPlan = ds
                            self.logger.info(f"Loaded RTPLAN: {file_path}")
                        else:
                            self.logger.warning(f"Multiple RTPLAN files found. Using first one: {self.RTPlan.filename}. Ignoring: {file_path}")

                except InvalidDicomError:
                    self.logger.debug(f"Skipping non-DICOM or invalid file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error reading DICOM file {file_path}: {e}")

        if self.CT:
            self.CT.sort(key=lambda x: float(x.ImagePositionPatient[2]))
            self.logger.info(f"Loaded {len(self.CT)} CT slices.")
        if not self.RTStructs:
            self.logger.warning("No RTSTRUCT file found.")
        if not self.RTDoses:
            self.logger.warning("No RTDOSE file found.")

    def _process_rtstructs(self):
        self.ROIs = []
        for rtstruct in self.RTStructs:
            self._process_rtstruct(rtstruct)

    def _process_rtstruct(self, rtstruct):
        if not rtstruct:
            return
        self.logger.info(f"Processing RTSTRUCT {os.path.basename(rtstruct.filename)} to extract ROIs...")
        if hasattr(rtstruct, 'StructureSetROISequence') and \
           hasattr(rtstruct, 'ROIContourSequence'):
            for roi_item in rtstruct.StructureSetROISequence:
                roi_data = {
                    'id': roi_item.ROINumber,
                    'name': roi_item.ROIName,
                    'contour_present': False
                }
                for contour_item in rtstruct.ROIContourSequence:
                    if contour_item.ReferencedROINumber == roi_item.ROINumber:
                        if hasattr(contour_item, 'ContourSequence') and len(contour_item.ContourSequence) > 0:
                            roi_data['contour_present'] = True
                        break
                self.ROIs.append(roi_data)
            self.logger.info(f"Found {len(self.ROIs)} ROIs in RTSTRUCT.")
        else:
            self.logger.warning("RTSTRUCT does not contain StructureSetROISequence or ROIContourSequence.")

    def set_verbose_level(self, verbose=True):
        self.verbose = verbose

    def get_available_interpolation_resolutions(self):
        available_resolutions = {}
        
        for rtdose in self.RTDoses:
            filename = os.path.basename(rtdose.filename)
            
            if hasattr(rtdose, 'PixelSpacing'):
                original_spacing = float(rtdose.PixelSpacing[0])
                
                resolutions = []
                for n in range(6):
                    new_resolution = original_spacing / (2**n)
                    if new_resolution >= 0.1:
                        resolutions.append(round(new_resolution, 4))
                
                available_resolutions[filename] = {
                    'original_spacing': original_spacing,
                    'available_resolutions': resolutions
                }
                
                self.logger.info(f"Available interpolation resolutions for {filename}: {resolutions}")
        
        return available_resolutions

    def _validate_interpolation_resolution(self, interpolation_resolution):
        if interpolation_resolution is None:
            return True
        
        for rtdose in self.RTDoses:
            if hasattr(rtdose, 'PixelSpacing'):
                original_spacing = float(rtdose.PixelSpacing[0])
                
                if original_spacing <= 0:
                    continue
                    
                ratio = original_spacing / interpolation_resolution
                
                if ratio > 0:
                    ratio_int = round(ratio)
                    
                    if ratio_int > 0 and (ratio_int & (ratio_int - 1)) == 0 and abs(ratio - ratio_int) < 1e-6:
                        continue
                    else:
                        n = round(np.log2(ratio))
                        suggested_resolution = original_spacing / (2**n)
                        
                        self.logger.error(f"Invalid interpolation resolution {interpolation_resolution}mm. "
                                        f"For original spacing {original_spacing}mm, try {suggested_resolution:.4f}mm instead.")
                        return False
                else:
                    self.logger.error(f"Invalid interpolation resolution {interpolation_resolution}mm. Must be positive.")
                    return False
        
        return True
    
    def get_dose_grid_info(self):
        dose_info = {}
        
        for rtdose in self.RTDoses:
            filename = os.path.basename(rtdose.filename)
            
            if hasattr(rtdose, 'PixelSpacing'):
                pixel_spacing = rtdose.PixelSpacing
                dose_info[filename] = {
                    'pixel_spacing_x': float(pixel_spacing[0]),
                    'pixel_spacing_y': float(pixel_spacing[1]),
                    'pixel_spacing_unit': 'mm'
                }
            
            if hasattr(rtdose, 'GridFrameOffsetVector'):
                slice_thickness = None
                offsets = rtdose.GridFrameOffsetVector
                if len(offsets) > 1:
                    slice_thickness = abs(float(offsets[1]) - float(offsets[0]))
                dose_info[filename]['slice_thickness'] = slice_thickness
                
            if hasattr(rtdose, 'DoseGridScaling'):
                dose_info[filename]['dose_scaling'] = float(rtdose.DoseGridScaling)
                
            if hasattr(rtdose, 'Rows') and hasattr(rtdose, 'Columns'):
                dose_info[filename]['matrix_size'] = (rtdose.Rows, rtdose.Columns)
                
            self.logger.info(f"Dose grid info for {filename}: {dose_info[filename]}")
        
        return dose_info

    def generate_dvh_plot(self, roi_id, output_dir, interpolation_resolution=None, figsize=(12, 9), dpi=150):
        os.makedirs(output_dir, exist_ok=True)
        
        if not self._validate_interpolation_resolution(interpolation_resolution):
            return None
        
        self.logger.info(f"Generating DVH plot for ROI ID {roi_id}")
        
        dvh_data = self.get_dvh_objects(roi_id, interpolation_resolution=interpolation_resolution)

        if not dvh_data:
            self.logger.error("Failed to get DVH object from patient")
            return None

        roi_name = next((roi['name'] for roi in self.ROIs if roi['id'] == roi_id), f"ROI {roi_id}")

        fig, ax = plt.subplots(figsize=figsize)

        for rtdose_filename, calculated_dvh in dvh_data:
            if calculated_dvh:
                volume_cc = calculated_dvh.volume

                doses = calculated_dvh.cumulative.relative_volume.bincenters
                volumes = calculated_dvh.cumulative.relative_volume.counts

                interp_label = f" (interp: {interpolation_resolution}mm)" if interpolation_resolution else " (original)"
                ax.plot(doses, volumes, linewidth=2, 
                       label=f"{roi_name} ({os.path.basename(rtdose_filename)}{interp_label})")

                self.logger.info(f"Plotted DVH for {rtdose_filename}: "
                               f"Min: {calculated_dvh.min:.1f} Gy, "
                               f"Mean: {calculated_dvh.mean:.1f} Gy, "
                               f"Max: {calculated_dvh.max:.1f} Gy, "
                               f"Volume: {volume_cc:.2f} cc")
            else:
                self.logger.error(f"Failed to get DVH object for {rtdose_filename}")

        title = f'Cumulative DVH - {roi_name}'
        if interpolation_resolution:
            title += f' (Interpolation: {interpolation_resolution}mm)'
        plt.title(title, fontsize=14)
        
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.xlabel('Dose (Gy)', fontsize=12)
        plt.ylabel('Volume (%)', fontsize=12)
        plt.ylim(0, 100)

        if hasattr(self, 'RTPlan') and self.RTPlan and hasattr(self.RTPlan, "DoseReferenceSequence"):
            for ref in self.RTPlan.DoseReferenceSequence:
                if hasattr(ref, "TargetPrescriptionDose"):
                    ref_dose = float(ref.TargetPrescriptionDose)
                    ax.axvline(x=ref_dose, color='r', linestyle='--', alpha=0.5, 
                              label=f'Prescription Dose: {ref_dose:.1f} Gy')
                    break

        plt.legend()
        plt.tight_layout()
        
        filename = f"dvh_roi_{roi_id}"
        if interpolation_resolution:
            filename += f"_interp_{interpolation_resolution}mm"
        filename += ".png"
        
        output_path = os.path.join(output_dir, filename)
        
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        self.logger.info(f"Saved DVH plot to {output_path}")
        plt.close(fig)
        
        return output_path

    def get_dvh_data_frame(self, roi_id, volume_resolution=0.1, interpolation_resolution=None):
        if not self._validate_interpolation_resolution(interpolation_resolution):
            return None
        
        dvh_data_dict = {}
        
        for rtdose in self.RTDoses:
            dvh = self._calculate_dvh(roi_id, rtdose, interpolation_resolution=interpolation_resolution)
            if dvh:
                doses = dvh.cumulative.relative_volume.bincenters
                volumes = dvh.cumulative.relative_volume.counts
                
                rtdose_filename = os.path.basename(rtdose.filename)
                interp_suffix = f"_interp_{interpolation_resolution}mm" if interpolation_resolution else "_original"
                dvh_data_dict[rtdose_filename + interp_suffix] = {
                    'volumes': volumes,
                    'doses': doses
                }
                self.logger.info(f"Extracted DVH data for {rtdose_filename}: {len(volumes)} points")
            else:
                self.logger.warning(f"Could not calculate DVH for {os.path.basename(rtdose.filename)}")

        if not dvh_data_dict:
            self.logger.error("No DVH data available.")
            return None

        all_volumes = []
        for data in dvh_data_dict.values():
            all_volumes.extend(data['volumes'])
        
        min_volume = min(all_volumes)
        max_volume = max(all_volumes)
        
        common_volume_grid = np.arange(min_volume, max_volume + volume_resolution, volume_resolution)
        
        self.logger.info(f"Created common volume grid: {min_volume:.1f}% to {max_volume:.1f}% with {len(common_volume_grid)} points")
        
        interpolated_data = {}
        
        for rtdose_filename, data in dvh_data_dict.items():
            volumes = data['volumes']
            doses = data['doses']
            
            sorted_indices = np.argsort(volumes)
            sorted_volumes = volumes[sorted_indices]
            sorted_doses = doses[sorted_indices]
            
            unique_volumes, unique_indices = np.unique(sorted_volumes, return_index=True)
            unique_doses = sorted_doses[unique_indices]
            
            if len(unique_volumes) > 1:
                interp_func = interpolate.interp1d(
                    unique_volumes, 
                    unique_doses, 
                    kind='linear', 
                    bounds_error=False, 
                    fill_value='extrapolate'
                )
                
                interpolated_doses = interp_func(common_volume_grid)
                interpolated_data[rtdose_filename] = interpolated_doses
                
                self.logger.info(f"Interpolated {rtdose_filename} from {len(unique_volumes)} to {len(common_volume_grid)} points")
            else:
                self.logger.warning(f"Not enough data points for interpolation in {rtdose_filename}")
                interpolated_data[rtdose_filename] = np.full(len(common_volume_grid), np.nan)

        df = pd.DataFrame(interpolated_data, index=common_volume_grid)
        df.index.name = 'Volume (%)'
        
        self.logger.info(f"Created DVH DataFrame with shape {df.shape}")
        return df

    def get_dvh_objects(self, roi_id, interpolation_resolution=None):
        if not self._validate_interpolation_resolution(interpolation_resolution):
            return []
        
        dvh_objects = []
        for rtdose in self.RTDoses:
            dvh = self._calculate_dvh(roi_id, rtdose, interpolation_resolution=interpolation_resolution)
            if dvh:
                dvh_objects.append((os.path.basename(rtdose.filename), dvh))
        return dvh_objects

    def _calculate_dvh(self, roi_id, rtdose, interpolation_resolution=None):
        if rtdose is None or self.RTStructs is None or not self.RTStructs:
            self.logger.error("Missing RTDOSE or RTSTRUCT, cannot calculate DVH.")
            return None

        roi_name = "Unknown ROI"
        found_roi = False
        for r in self.ROIs:
            if r['id'] == roi_id:
                roi_name = r['name']
                if not r['contour_present']:
                    self.logger.warning(f"ROI {roi_name} (ID: {roi_id}) has no contour data in RTSTRUCT. DVH may be empty or incorrect.")
                found_roi = True
                break

        if not found_roi:
            self.logger.error(f"ROI ID {roi_id} not found in RTSTRUCT.")
            return None

        interp_info = f" with interpolation {interpolation_resolution}mm" if interpolation_resolution else " (original grid)"
        self.logger.info(f"Calculating DVH for ROI: {roi_name} (ID: {roi_id}) using dicompyler-core{interp_info}.")
        
        try:
            calculated_dvh = dvhcalc.get_dvh(
                self.RTStructs[0],
                rtdose,
                roi_id,
                calculate_full_volume=True,
                use_structure_extents=False,
                interpolation_resolution=interpolation_resolution,
                interpolation_segments_between_planes=0
            )

            if calculated_dvh:
                calculated_dvh.name = roi_name
                self.logger.info(f"ROI {roi_name} (ID: {roi_id}) volume: {calculated_dvh.volume:.4f} cc")
            else:
                self.logger.error(f"DVH calculation returned None for ROI {roi_name} (ID: {roi_id}).")

            return calculated_dvh

        except Exception as e:
            self.logger.error(f"Error calculating DVH for ROI {roi_name} (ID: {roi_id}) with dicompyler-core: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    def list_rois_info(self):
        return [{'id': roi['id'], 'name': roi['name']} for roi in self.ROIs if roi['contour_present']]