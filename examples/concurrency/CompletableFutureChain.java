package concurrency;

import java.util.concurrent.*;

public class CompletableFutureChain {

    public static void main(String[] args) {
        CompletableFuture.supplyAsync(() -> 10)
            .thenApply(x -> x * 2)
            .thenApply(x -> x + 5)
            .thenAccept(System.out::println);
    }
}