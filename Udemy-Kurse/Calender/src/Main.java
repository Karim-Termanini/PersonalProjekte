import java.util.Scanner;

public class Main {

	public static void main(String[] args) {
		Scanner in = new Scanner(System.in);
		System.out.println("Geben Sie das ganze Jahr ein: ");
		int jahr = in.nextInt();

		System.out.println("Geben Sie den Monat als Zahl zwischen 1 und 12 ein: ");
		int monat = in.nextInt();

		Kalender k = new Kalender(monat, monat);
		k.kalenderDrucken(jahr, monat);
	}

}
