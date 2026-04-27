
public class Kalender {

	private int monat;
	private int jahr;

	public Kalender(int m, int y) {
		this.monat = m;
		this.jahr = y;
	}

	

	/**
	 * @return the monat
	 */
	public int getMonat() {
		return monat;
	}



	/**
	 * @param monat the monat to set
	 */
	public void setMonat(int monat) {
		this.monat = monat;
	}



	/**
	 * @return the jahr
	 */
	public int getJahr() {
		return jahr;
	}



	/**
	 * @param jahr the jahr to set
	 */
	public void setJahr(int jahr) {
		this.jahr = jahr;
	}



	public void kalenderDrucken(int jahr,int monat) {
		printMonatstitel(jahr, monat);
		monatKörper(jahr, monat);
	}

	void monatKörper(int jahr, int monat) {
		int tagBeginnen = startTag(jahr, monat);
		int tageImMonat = anzahlderTageImMonat(jahr, monat);

		int i = 0;
		for (i = 0; i < tagBeginnen; i++) {
			System.out.print("    ");
		}
		for (i = 1; i <= tageImMonat; i++) {
			System.out.printf("%4d", i);
			if ((i + tagBeginnen) % 7 == 0) {
				System.out.println();
			}
		}
		System.out.println();
	}

	void printMonatstitel(int jahr, int monat) {
		System.out.println("          " + getMonatsname(monat) + " " + jahr);
		System.out.println("-----------------------------");
		System.out.println(" Son Mon Di Mit Do Fr Sam");
	}

	int startTag(int monat, int jahr) {
		final int ANFANG_DES_TAG_JAN_1 = 3;
		int zahlDerTage = gesamtZahlDerTage(jahr, monat);
		return (ANFANG_DES_TAG_JAN_1 + zahlDerTage) % 7;
	}

	int gesamtZahlDerTage(int jahr, int monat) {
		int gesamt = 0;
		for (int i = 1800; i < jahr; i++) {
			if (istSchaltjahr(i)) {
				gesamt += 366;
			} else {
				gesamt += 365;
			}
		}
		for (int i = 1; i < monat; i++) {
			gesamt += anzahlderTageImMonat(jahr, i);
		}
		return gesamt;
	}

	int anzahlderTageImMonat(int jahr, int monat) {

		if (monat == 1 || monat == 3 || monat == 5 || monat == 7 || monat == 8 || monat == 10 || monat == 12) {
			return 31;
		}
		if (monat == 4 || monat == 6 || monat == 9 || monat == 11) {
			return 30;
		}
		if (monat == 2)
			return istSchaltjahr(jahr) ? 29 : 28;
		return 0;

	}

	boolean istSchaltjahr(int jahr) {
		return jahr % 400 == 0 || jahr % 4 == 0 && jahr % 100 != 0;
	}

	String getMonatsname(int monat) {
		String monthName = "";
		switch (monat) {
		case 1:
			monthName = "Januar";
			break;
		case 2:
			monthName = "Februar";
			break;
		case 3:
			monthName = "März";
			break;
		case 4:
			monthName = "April";
			break;
		case 5:
			monthName = "Mai";
			break;
		case 6:
			monthName = "Juni";
			break;
		case 7:
			monthName = "Juli";
			break;
		case 8:
			monthName = "August";
			break;
		case 9:
			monthName = "September";
			break;
		case 10:
			monthName = "Oktober";
			break;
		case 11:
			monthName = "November";
			break;
		case 12:
			monthName = "Dezember";
			break;
		default:
			System.out.println("invalid charachter");
			break;
		}
		return monthName;
	}

}
