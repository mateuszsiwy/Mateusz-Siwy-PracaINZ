import matplotlib.pyplot as plt
import os

def create_and_save_dvh_plot(dvh_object, roi_name_for_title, volume_cc, output_path_with_filename, rt_plan=None, logger=None):
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)

    if not dvh_object:
        logger.error(f"Cannot plot DVH for {roi_name_for_title}, DVH object is None.")
        return

    try:
        fig, ax = plt.subplots(figsize=(12, 9))

        doses = dvh_object.bincenters
        volumes = dvh_object.counts

        ax.plot(doses, volumes, linewidth=2, label=roi_name_for_title)
        
        ax.set_title(f'Cumulative DVH - {roi_name_for_title} ({volume_cc:.2f}cc)', fontsize=14)
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.set_xlabel('Dose (Gy)', fontsize=12)
        ax.set_ylabel('Volume (%)', fontsize=12)
        ax.set_ylim(0, 100)
        ax.set_xlim(left=0, right=max(doses) * 1.05 if len(doses) > 0 else 100)

        stats_text = ""
        if hasattr(dvh_object, 'min') and dvh_object.min is not None:
             stats_text += f"Min: {dvh_object.min:.1f} Gy\n"
        if hasattr(dvh_object, 'mean') and dvh_object.mean is not None:
            stats_text += f"Mean: {dvh_object.mean:.1f} Gy\n"
        if hasattr(dvh_object, 'max') and dvh_object.max is not None:
            stats_text += f"Max: {dvh_object.max:.1f} Gy"
        
        if stats_text:
            ax.text(0.95, 0.95, stats_text, transform=ax.transAxes,
                    fontsize=10, verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round,pad=0.5', fc='white', alpha=0.8))

        if rt_plan and hasattr(rt_plan, "DoseReferenceSequence"):
            for ref in rt_plan.DoseReferenceSequence:
                if hasattr(ref, "TargetPrescriptionDose") and ref.TargetPrescriptionDose:
                    try:
                        ref_dose = float(ref.TargetPrescriptionDose)
                        ax.axvline(x=ref_dose, color='r', linestyle='--', alpha=0.7, label=f'Rx Dose: {ref_dose} Gy')
                        logger.info(f"Added reference dose line at {ref_dose} Gy.")
                        break 
                    except ValueError:
                        logger.warning(f"Could not parse TargetPrescriptionDose: {ref.TargetPrescriptionDose}")
        
        if roi_name_for_title or (rt_plan and any(hasattr(ref, "TargetPrescriptionDose") for ref in rt_plan.DoseReferenceSequence if hasattr(rt_plan, "DoseReferenceSequence"))):
            ax.legend(loc='best')

        plt.tight_layout()
        
        output_dir = os.path.dirname(output_path_with_filename)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")

        fig.savefig(output_path_with_filename, dpi=150)
        logger.info(f"Saved DVH plot to {output_path_with_filename}")
        plt.close(fig)

    except Exception as e:
        logger.error(f"Error creating/saving DVH plot for {roi_name_for_title}: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())

