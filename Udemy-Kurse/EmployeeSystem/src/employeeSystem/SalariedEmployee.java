package employeeSystem;

public class SalariedEmployee extends Employee implements Displayable {
	private double _salary;
	private double _bonus;
	private double _deductions;

	// ----Constructor----

	/**
	 * @param name
	 * @param ssn
	 * @param adress
	 * @param sex
	 * @param _salary
	 * @param _bonus
	 * @param _deductions
	 */
	public SalariedEmployee(String name, int ssn, String adress, Gender sex, double _salary, double _bonus,
			double _deductions) {
		super(name, ssn, adress, sex);
		this._salary = _salary;
		this._bonus = _bonus;
		this._deductions = _deductions;
	}

	/**
	 * Empty Constructor
	 */
	public SalariedEmployee() {
	}

	// ----Properties----
	/**
	 * @return the _salary
	 */
	public double get_salary() {
		return _salary;
	}

	/**
	 * @param _salary the _salary to set
	 */
	public void set_salary(double _salary) {
		this._salary = _salary;
	}

	/**
	 * @return the _bonus
	 */
	public double get_bonus() {
		return _bonus;
	}

	/**
	 * @param _bonus the _bonus to set
	 */
	public void set_bonus(double _bonus) {
		this._bonus = _bonus;
	}

	/**
	 * @return the _deductions
	 */
	public double get_deductions() {
		return _deductions;
	}

	/**
	 * @param _deductions the _deductions to set
	 */
	public void set_deductions(double _deductions) {
		this._deductions = _deductions;
	}

	// ----Methods----
	@Override
	public double Earning() {
		return (_salary + _bonus) - _deductions;
	}

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
	public String toString() {
		return "SalariedEmployee [_salary=" + _salary + ", _bonus=" + _bonus + ", _deductions=" + _deductions + "]";
	}

}
