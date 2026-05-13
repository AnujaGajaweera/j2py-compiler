package concurrency;

public class SynchronizedCounter {

    private int x = 0;

    public synchronized void inc() {
        x++;
    }

    public int get() {
        return x;
    }
}