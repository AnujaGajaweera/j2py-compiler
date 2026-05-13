package core;

public class ControlFlowHell {

    public static void run(int n) {
        for (int i = 0; i < n; i++) {
            if (i % 2 == 0) {
                for (int j = 0; j < i; j++) {
                    if (j % 3 == 0) {
                        if (j % 5 == 0) {
                            System.out.println("A:" + i + ":" + j);
                        } else {
                            System.out.println("B:" + i + ":" + j);
                        }
                    }
                }
            }
        }
    }
}