
library package 'MachineLibrary' {

	private import MaintenanceLibrary;
	private import MaintenanceLibrary::MaintenanceActivity;
	private import MaintenanceLibrary::PreventativeMaintenanceActivity;
	private import SI::hour;

	part def PhysicalObject {
		
	}

	part def Maschine :> PhysicalObject {

		action maintenanceActivities : MaintenanceActivity [0..*];
		action setupActivities [0..*];
		action workOrderActivities [0..*];

		

	}

	
}