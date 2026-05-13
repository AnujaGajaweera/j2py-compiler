package concurrency;

public class ThreadStorm {

    public static void main(String[] args) {
        for (int i = 0; i < 100; i++) {
            int id = i;
            new Thread(() -> {
                System.out.println("Thread " + id);
            }).start();
        }
    }
}