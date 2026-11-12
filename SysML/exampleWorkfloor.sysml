
package workshop {

	private import MachineLibrary::*;
	private import MaintenanceLibrary::*;
	private import SI::hour;

	part matsuura : Machine {

		action cleanProtectiveGlass : PreventativeMaintenanceActivity :> maintenanceActivities {
			:>> timeInterval = 30 [hour];
		}

	}
}