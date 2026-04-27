package employeeSystem;

public class Main {

	public static void main(final String[] args) {
		extracted();
	}

	private static void extracted() {
		final Department department1 = new Department(1, "Information System");

		final SalariedEmployee sEmployee = new SalariedEmployee("karim", 50, "Hameln", Gender.male, 2000, 200, 1200);
		department1.addEmployee(sEmployee);

		final HourlyEmployee hEmployee = new HourlyEmployee("Torsten", 60, "Afferde", Gender.male, 14, 160);
		department1.addEmployee(hEmployee);

		final CommissionEmployee cEmployee = new CommissionEmployee("Alex", 80, "KleinBerkel", Gender.female, 15000,
				0.25);
		department1.addEmployee(cEmployee);

		System.out.println("Employee Count is: " + department1.getEmployeeCount());

		department1.printBasicData();
		department1.printAllDetails();
	}

}
