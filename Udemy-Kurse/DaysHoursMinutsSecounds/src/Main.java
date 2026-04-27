import java.util.Scanner;

public class Main {

	public static void main(String[] args) {
		Scanner in = new Scanner(System.in);
		double days = in.nextInt();
		double hours = in.nextInt();
		double minuts = in.nextInt();
		double secound = in.nextInt();
		System.out.println("---- Days " + days + " ----");

		System.out.println("days in hours: " + (days * 24));
		System.out.println("days in minuts: " + (days * 24 * 60));
		System.out.println("Days in secounds: " + (days * 24 * 60 * 60));
		System.out.println();
		System.out.println("---- Hours  " + hours + "----");
		System.out.println("Hours in days: " + (hours / 24));
		System.out.println("Hours in minuts: " + (hours * 60));
		System.out.println("Hours in secounds: " + (hours * 60 * 60));
		System.out.println();
		System.out.println("---- Minuts " + minuts + "----");
		System.out.println("Minuts in days: " + (minuts / 60 / 24));
		System.out.println("Minuts in Hours: " + (minuts / 60));
		System.out.println("Minuts in secounds: " + (minuts * 60));
		System.out.println();
		System.out.println("---- Secounds " + secound + "----");
		System.out.println("Secounds in days: " + (secound / 60 / 60 / 24));
		System.out.println("Secound in Hours: " + (secound / 60 / 60));
		System.out.println("Secounds in minuts: " + (secound / 60));
	}

}
