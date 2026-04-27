package employeeSystem;

public class CommissionEmployee extends Employee implements Displayable {
	public double _grossSales;
	public double _commissionRate;

	// ----Constructor----

	/**
	 * @param name
	 * @param ssn
	 * @param adress
	 * @param sex
	 * @param _grossSales
	 * @param _commissionRate
	 */
	public CommissionEmployee(String name, int ssn, String adress, Gender sex, double _grossSales,
			double _commissionRate) {
		super(name, ssn, adress, sex);
		this._grossSales = _grossSales;
		this._commissionRate = _commissionRate;
	}

	/**
	 * Empty Constructor
	 */
	public CommissionEmployee() {
	}

	// ----Properties----

	/**
	 * @return the _grossSales
	 */
	public double get_grossSales() {
		return _grossSales;
	}

	/**
	 * @param _grossSales the _grossSales to set
	 */
	public void set_grossSales(double _grossSales) {
		this._grossSales = _grossSales;
	}

	/**
	 * @return the _commissionRate
	 */
	public double get_commissionRate() {
		return _commissionRate;
	}

	/**
	 * @param _commissionRate the _commissionRate to set
	 */
	public void set_commissionRate(double _commissionRate) {
		this._commissionRate = _commissionRate;
	}

	// ----Methods----
	@Override
	public void DisplayAllDetails() {
		System.out.println(super.toString());
		System.out.println(toString());
		System.out.println();
	}

	@Override
	public void DisplayEarning() {
		System.out.println(Earning());
	}

	@Override
	public double Earning() {
		return _grossSales * _commissionRate;
	}

	@Override
	public String toString() {
		return "CommissionEmployee [_grossSales=" + _grossSales + ", _commissionRate=" + _commissionRate + "]";
	}

}
