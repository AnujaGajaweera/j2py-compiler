package mixed;

import java.util.*;
import java.util.concurrent.*;
import java.util.stream.*;

public class UltimateStressTest<T extends Comparable<T>> {

    List<T> data = new ArrayList<>();

    public synchronized void process() {
        data.stream()
            .filter(x -> x != null)
            .sorted()
            .map(x -> transform(x))
            .forEach(x -> {
                new Thread(() -> {
                    System.out.println(x);
                }).start();
            });
    }

    private T transform(T x) {
        return x;
    }

    public CompletableFuture<List<T>> asyncProcess() {
        return CompletableFuture.supplyAsync(() -> {
            return data.stream().map(this::transform).toList();
        });
    }
}