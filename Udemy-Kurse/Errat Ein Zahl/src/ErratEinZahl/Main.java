package ErratEinZahl;

import java.util.Scanner;

public class Main {

	public static void main(String[] args) {

		int Nummer = (int) (Math.random() * 101);
		Scanner in = new Scanner(System.in);
		System.out.println("Errat die magische Zahl zwischen 0 und 100!?");
		int errat = -1;
		while (errat != Nummer) {
			System.out.println("gib deine Vermutung ein:");
			errat = in.nextInt();

			if (errat == Nummer) {
				System.out.println("Super,die Nummer ist: " + Nummer);
			} else if (errat > Nummer) {
				System.out.println("deine schätzung ist zu hoch");
			} else {
				System.out.println("deine Schätzung ist zu niedrig");
			}
		}

	}

}
