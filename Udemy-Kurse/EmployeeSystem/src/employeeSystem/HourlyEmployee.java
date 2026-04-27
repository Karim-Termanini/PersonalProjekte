package employeeSystem;

public class HourlyEmployee extends Employee implements Displayable {
	private double _hourRate;
	private int _numbersOfHours;

	// ----Constructor----

	/**
	 * @param name
	 * @param ssn
	 * @param adress
	 * @param sex
	 * @param _hourRate
	 * @param _numbersOfHours
	 */
	public HourlyEmployee(String name, int ssn, String adress, Gender sex, double _hourRate, int _numbersOfHours) {
		super(name, ssn, adress, sex);
		this._hourRate = _hourRate;
		this._numbersOfHours = _numbersOfHours;
	}

	/**
	 * Empty Constructor
	 */
	public HourlyEmployee() {

	}

	// ----Properties----

	/**
	 * @return the _hourRate
	 */
	public double get_hourRate() {
		return _hourRate;
	}

	/**
	 * @param _hourRate the _hourRate to set
	 */
	public void set_hourRate(double _hourRate) {
		this._hourRate = _hourRate;
	}

	/**
	 * @return the _numbersOfHours
	 */
	public int get_numbersOfHours() {
		return _numbersOfHours;
	}

	/**
	 * @param _numbersOfHours the _numbersOfHours to set
	 */
	public void set_numbersOfHours(int _numbersOfHours) {
		this._numbersOfHours = _numbersOfHours;
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
		return _hourRate * _numbersOfHours;
	}

	@Override
	public String toString() {
		return "HourlyEmployee [_hourRate=" + _hourRate + ", _numbersOfHours=" + _numbersOfHours + "]";
	}

}
