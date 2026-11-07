
package workshop {

	private import MachineLibrary::*;
	private import MaintenanceLibrary::*;
	private import SI::hour;

	part matsuura : Maschine {

		action cleanProtectiveGlass : PreventativeMaintenanceActivity :> maintenanceActivities {
			:>> timeInterval = 30 [hour];
		}
		
	}
}