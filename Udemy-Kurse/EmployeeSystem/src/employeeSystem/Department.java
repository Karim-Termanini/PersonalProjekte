package employeeSystem;

import java.util.ArrayList;

public class Department {
	int dNu;
	String dName;
	ArrayList<Employee> emplist;

	// ----Constructor----

	/**
	 * Empty Constructor
	 */
	public Department() {
	}

	/**
	 * @param dNu
	 * @param dName
	 * @param emplist
	 */
	public Department(int dNu, String dName) {
		this.dNu = dNu;
		this.dName = dName;
		this.emplist = new ArrayList<Employee>();
	}

	// ----Properties----

	/**
	 * @return the dNu
	 */
	public int getdNu() {
		return dNu;
	}

	/**
	 * @param dNu the dNu to set
	 */
	public void setdNu(int dNu) {
		this.dNu = dNu;
	}

	/**
	 * @return the dName
	 */
	public String getdName() {
		return dName;
	}

	/**
	 * @param dName the dName to set
	 */
	public void setdName(String dName) {
		this.dName = dName;
	}

	// ----Methods----
	public void addEmployee(Employee e) {
		emplist.add(e);
	}

	public void removeEmployee(int e) {
		emplist.remove(e);
	}

	public int getEmployeeCount() {
		return emplist.size();
	}

	public void printBasicData() {
		for (int i = 0; i < emplist.size(); i++) {
			System.out.println("==> " + emplist.get(i).get_name() + "\n -" + emplist.get(i).get_sex() + "\n -"
					+ emplist.get(i).get_adress() + "\n -" + emplist.get(i).get_ssn());
		}
		System.out.println();
	}

	public void printAllDetails() {
		for (int i = 0; i < emplist.size(); i++) {
			if (emplist.get(i) instanceof SalariedEmployee)
				((SalariedEmployee) emplist.get(i)).DisplayAllDetails();

			if (emplist.get(i) instanceof HourlyEmployee) {
				((HourlyEmployee) emplist.get(i)).DisplayAllDetails();
			}
			if (emplist.get(i) instanceof CommissionEmployee) {
				((CommissionEmployee) emplist.get(i)).DisplayAllDetails();
			}
		}
	}

}
