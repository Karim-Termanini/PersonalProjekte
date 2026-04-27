package employeeSystem;

enum Gender {
	male, female
};

public abstract class Employee {
	private String _name;
	private int _ssn;
	private String _adress;
	private Gender _sex;

	// ----Constructor----

	/**
	 * @param _name
	 * @param _ssn
	 * @param _adress
	 * @param _sex
	 */
	public Employee(String name, int ssn, String adress, Gender sex) {
		this._name = name;
		this._ssn = ssn;
		this._adress = adress;
		this._sex = sex;
	}

	/**
	 * Empty Constructor
	 */
	public Employee() {
	}

	// ----Properties----
	/**
	 * @return the _name
	 */
	public String get_name() {
		return _name;
	}

	/**
	 * @param _name the _name to set
	 */
	public void set_name(String name) {
		this._name = name;
	}

	/**
	 * @return the _ssn
	 */
	public int get_ssn() {
		return _ssn;
	}

	/**
	 * @param _ssn the _ssn to set
	 */
	public void set_ssn(int ssn) {
		this._ssn = ssn;
	}

	/**
	 * @return the _adress
	 */
	public String get_adress() {
		return _adress;
	}

	/**
	 * @param _adress the _adress to set
	 */
	public void set_adress(String adress) {
		this._adress = adress;
	}

	/**
	 * @return the _sex
	 */
	public Gender get_sex() {
		return _sex;
	}

	/**
	 * @param _sex the _sex to set
	 */
	public void set_sex(Gender sex) {
		this._sex = sex;
	}

	// ----Methods----
	public abstract double Earning();

	@Override
	public String toString() {
		return "Employee [_name=" + _name + ", _ssn=" + _ssn + ", _adress=" + _adress + ", _sex=" + _sex + "]";
	}
	 
}
