
library package 'MaintenanceLibrary' {

	action def MaintenanceActivity {
		action processSteps : MaintenanceProcessStep [0..*];
	}

	action def PreventativeMaintenanceActivity :> MaintenanceActivity {

		attribute timeInterval : ISQ::DurationValue;

	}

	action def MaintenanceProcessStep;

}