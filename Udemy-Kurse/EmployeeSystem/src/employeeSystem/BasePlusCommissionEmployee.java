package employeeSystem;

public class BasePlusCommissionEmployee extends CommissionEmployee {
	public double Base;

	// ----Properties----

	/**
	 * @return the base
	 */
	public double getBase() {
		return Base;
	}

	/**
	 * @param base the base to set
	 */
	public void setBase(double base) {
		Base = base;
	}

	// ----Methods----

	@Override
	public double Earning() {
		return Base + super.Earning();
	}

	@Override
	public void DisplayAllDetails() {
		super.DisplayAllDetails();
		DisplayEarning();
	}

	@Override
	public void DisplayEarning() {
		System.out.println("Earninig " + Earning());
	}

}
