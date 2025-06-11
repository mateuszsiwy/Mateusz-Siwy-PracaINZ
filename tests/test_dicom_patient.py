import unittest
import tempfile
import os
import shutil
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import pydicom
from pydicom.dataset import Dataset

# Import the class to test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dvh_analyzer.dicom_patient import DicomPatient


class TestDicomPatient(unittest.TestCase):
    
    def setUp(self):
        
        self.test_dir = tempfile.mkdtemp()
        self.patient_name = "TestPatient"
        
        self.mock_logger = Mock()
        
        self.mock_ct = self._create_mock_ct()
        self.mock_rtstruct = self._create_mock_rtstruct()
        self.mock_rtdose = self._create_mock_rtdose()
        self.mock_rtplan = self._create_mock_rtplan()
    
    def tearDown(self):
        
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_mock_ct(self):
        
        ct = Dataset()
        ct.Modality = "CT"
        ct.ImagePositionPatient = [0, 0, 0]
        ct.filename = "ct_slice_001.dcm"
        return ct
    
    def _create_mock_rtstruct(self):
        
        rtstruct = Dataset()
        rtstruct.Modality = "RTSTRUCT"
        rtstruct.filename = "rtstruct.dcm"
        
        roi1 = Dataset()
        roi1.ROINumber = 1
        roi1.ROIName = "PTV"
        
        roi2 = Dataset()
        roi2.ROINumber = 3
        roi2.ROIName = "odbytnica"
        
        rtstruct.StructureSetROISequence = [roi1, roi2]
        
        contour1 = Dataset()
        contour1.ReferencedROINumber = 1
        contour1.ContourSequence = [Dataset()]  # Non-empty sequence
        
        contour2 = Dataset()
        contour2.ReferencedROINumber = 3
        contour2.ContourSequence = [Dataset()]  # Non-empty sequence
        
        rtstruct.ROIContourSequence = [contour1, contour2]
        
        return rtstruct
    
    def _create_mock_rtdose(self):
        
        rtdose = Dataset()
        rtdose.Modality = "RTDOSE"
        rtdose.filename = "rtdose.dcm"
        rtdose.PixelSpacing = [2.5, 2.5]
        rtdose.GridFrameOffsetVector = [0.0, 2.5, 5.0]
        rtdose.DoseGridScaling = 0.001
        rtdose.Rows = 100
        rtdose.Columns = 100
        return rtdose
    
    def _create_mock_rtplan(self):
        
        rtplan = Dataset()
        rtplan.Modality = "RTPLAN"
        rtplan.filename = "rtplan.dcm"
        
        dose_ref = Dataset()
        dose_ref.TargetPrescriptionDose = 60.0
        rtplan.DoseReferenceSequence = [dose_ref]
        
        return rtplan
    
    @patch('pydicom.dcmread')
    @patch('os.walk')
    def test_init_successful_loading(self, mock_walk, mock_dcmread):
        
        mock_walk.return_value = [
            (self.test_dir, [], ['ct.dcm', 'rtstruct.dcm', 'rtdose.dcm', 'rtplan.dcm'])
        ]
        
    def test_get_available_interpolation_resolutions(self):
        
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTDoses = [self.mock_rtdose]
        
        resolutions = patient.get_available_interpolation_resolutions()
        
        self.assertIn('rtdose.dcm', resolutions)
        self.assertEqual(resolutions['rtdose.dcm']['original_spacing'], 2.5)
        expected_resolutions = [2.5, 1.25, 0.625, 0.3125, 0.1562]  
        self.assertEqual(resolutions['rtdose.dcm']['available_resolutions'], expected_resolutions)
    
    def test_validate_interpolation_resolution_valid(self):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTDoses = [self.mock_rtdose]
        
        self.assertTrue(patient._validate_interpolation_resolution(None))
        self.assertTrue(patient._validate_interpolation_resolution(2.5))
        self.assertTrue(patient._validate_interpolation_resolution(1.25))
        self.assertTrue(patient._validate_interpolation_resolution(0.625))
    
    def test_validate_interpolation_resolution_invalid(self):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTDoses = [self.mock_rtdose]
        
        self.assertFalse(patient._validate_interpolation_resolution(1.0))
        self.assertFalse(patient._validate_interpolation_resolution(3.0))
        self.assertFalse(patient._validate_interpolation_resolution(-1.0))
    
    def test_get_dose_grid_info(self):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTDoses = [self.mock_rtdose]
        
        dose_info = patient.get_dose_grid_info()
        
        self.assertIn('rtdose.dcm', dose_info)
        info = dose_info['rtdose.dcm']
        self.assertEqual(info['pixel_spacing_x'], 2.5)
        self.assertEqual(info['pixel_spacing_y'], 2.5)
        self.assertEqual(info['slice_thickness'], 2.5)
        self.assertEqual(info['dose_scaling'], 0.001)
        self.assertEqual(info['matrix_size'], (100, 100))
    
    @patch('dvh_analyzer.dicom_patient.dvhcalc.get_dvh')
    def test_calculate_dvh_success(self, mock_get_dvh):
        
        mock_dvh = Mock()
        mock_dvh.volume = 50.67
        mock_dvh.name = None
        mock_get_dvh.return_value = mock_dvh
        
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTStructs = [self.mock_rtstruct]
        patient.ROIs = [{'id': 3, 'name': 'odbytnica', 'contour_present': True}]
        
        result = patient._calculate_dvh(3, self.mock_rtdose)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'odbytnica')
        mock_get_dvh.assert_called_once()
    
    @patch('dvh_analyzer.dicom_patient.dvhcalc.get_dvh')
    def test_calculate_dvh_roi_not_found(self, mock_get_dvh):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTStructs = [self.mock_rtstruct]
        patient.ROIs = [{'id': 1, 'name': 'PTV', 'contour_present': True}]
        
        result = patient._calculate_dvh(999, self.mock_rtdose)
        
        self.assertIsNone(result)
        mock_get_dvh.assert_not_called()
    
    @patch('dvh_analyzer.dicom_patient.dvhcalc.get_dvh')
    def test_get_dvh_objects(self, mock_get_dvh):
        
        mock_dvh = Mock()
        mock_dvh.volume = 50.67
        mock_get_dvh.return_value = mock_dvh
        
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTStructs = [self.mock_rtstruct]
        patient.RTDoses = [self.mock_rtdose]
        patient.ROIs = [{'id': 3, 'name': 'odbytnica', 'contour_present': True}]
        
        dvh_objects = patient.get_dvh_objects(3)
        
        self.assertEqual(len(dvh_objects), 1)
        self.assertEqual(dvh_objects[0][0], 'rtdose.dcm')  
        self.assertEqual(dvh_objects[0][1], mock_dvh)  
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('os.makedirs')
    def test_generate_dvh_plot_success(self, mock_makedirs, mock_close, mock_savefig):
        
        mock_dvh = Mock()
        mock_dvh.volume = 50.67
        mock_dvh.min = 0.0
        mock_dvh.mean = 30.5
        mock_dvh.max = 65.2
        mock_dvh.cumulative.relative_volume.bincenters = np.array([0, 10, 20, 30, 40, 50, 60])
        mock_dvh.cumulative.relative_volume.counts = np.array([100, 90, 70, 50, 30, 10, 0])
        
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTStructs = [self.mock_rtstruct]
        patient.RTDoses = [self.mock_rtdose]
        patient.ROIs = [{'id': 3, 'name': 'odbytnica', 'contour_present': True}]
        
        with patch.object(patient, 'get_dvh_objects', return_value=[('rtdose.dcm', mock_dvh)]):
            result = patient.generate_dvh_plot(3, self.test_dir)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith('.png'))
        mock_makedirs.assert_called_once()
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()
    
    def test_generate_dvh_plot_invalid_interpolation(self):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTDoses = [self.mock_rtdose]
        
        result = patient.generate_dvh_plot(3, self.test_dir, interpolation_resolution=1.0)
        
        self.assertIsNone(result)
    
    def test_get_dvh_data_frame_invalid_interpolation(self):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.RTDoses = [self.mock_rtdose]
        
        result = patient.get_dvh_data_frame(3, interpolation_resolution=1.0)
        
        self.assertIsNone(result)
    
    def test_list_rois_info(self):
        patient = DicomPatient(self.patient_name, self.test_dir, self.mock_logger)
        patient.ROIs = [
            {'id': 1, 'name': 'PTV', 'contour_present': True},
            {'id': 2, 'name': 'OAR1', 'contour_present': False},
            {'id': 3, 'name': 'odbytnica', 'contour_present': True}
        ]
        
        roi_info = patient.list_rois_info()
        
        self.assertEqual(len(roi_info), 2)  
        roi_ids = [roi['id'] for roi in roi_info]
        self.assertIn(1, roi_ids)
        self.assertIn(3, roi_ids)
        self.assertNotIn(2, roi_ids)
    
    @patch('os.path.isdir')
    def test_invalid_data_path(self, mock_isdir):
        mock_isdir.return_value = False
        
        patient = DicomPatient(self.patient_name, "/non/existent/path", self.mock_logger)
        
        self.assertEqual(len(patient.CT), 0)
        self.assertEqual(len(patient.RTStructs), 0)
        self.assertEqual(len(patient.RTDoses), 0)


class TestDicomPatientIntegration(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.patient_name = "IntegrationTestPatient"
    
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('pydicom.dcmread')
    @patch('os.walk')
    @patch('dvh_analyzer.dicom_patient.dvhcalc.get_dvh')
    def test_complete_workflow(self, mock_get_dvh, mock_walk, mock_dcmread):
        
        mock_ct = Dataset()
        mock_ct.Modality = "CT"
        mock_ct.ImagePositionPatient = [0, 0, 0]
        mock_ct.filename = "ct.dcm"
        
        mock_rtstruct = Dataset()
        mock_rtstruct.Modality = "RTSTRUCT"
        mock_rtstruct.filename = "rtstruct.dcm"
        
        roi = Dataset()
        roi.ROINumber = 3
        roi.ROIName = "TestROI"
        mock_rtstruct.StructureSetROISequence = [roi]
        
        contour = Dataset()
        contour.ReferencedROINumber = 3
        contour.ContourSequence = [Dataset()]
        mock_rtstruct.ROIContourSequence = [contour]
        
        mock_rtdose = Dataset()
        mock_rtdose.Modality = "RTDOSE"
        mock_rtdose.filename = "rtdose.dcm"
        mock_rtdose.PixelSpacing = [2.5, 2.5]
        
        mock_walk.return_value = [(self.test_dir, [], ['ct.dcm', 'rtstruct.dcm', 'rtdose.dcm'])]
        
        def mock_dcmread_side_effect(filepath, force=True):
            if 'ct.dcm' in filepath:
                return mock_ct
            elif 'rtstruct.dcm' in filepath:
                return mock_rtstruct
            elif 'rtdose.dcm' in filepath:
                return mock_rtdose
        
        mock_dcmread.side_effect = mock_dcmread_side_effect
        
        mock_dvh = Mock()
        mock_dvh.volume = 25.5
        mock_dvh.cumulative.relative_volume.bincenters = np.array([0, 10, 20, 30])
        mock_dvh.cumulative.relative_volume.counts = np.array([100, 75, 50, 25])
        mock_get_dvh.return_value = mock_dvh
        
        patient = DicomPatient(self.patient_name, self.test_dir)
        
        self.assertEqual(len(patient.RTStructs), 1)
        self.assertEqual(len(patient.RTDoses), 1)
        self.assertEqual(len(patient.ROIs), 1)
        
        resolutions = patient.get_available_interpolation_resolutions()
        self.assertIn('rtdose.dcm', resolutions)
        
        dvh_objects = patient.get_dvh_objects(3)
        self.assertEqual(len(dvh_objects), 1)
        
        with patch.object(patient, '_validate_interpolation_resolution', return_value=True):
            df = patient.get_dvh_data_frame(3)
            self.assertIsNotNone(df)


if __name__ == '__main__':
    test_suite = unittest.TestSuite()
    
    test_suite.addTest(unittest.makeSuite(TestDicomPatient))
    # test_suite.addTest(unittest.makeSuite(TestDicomPatientIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print(f"\nTests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")