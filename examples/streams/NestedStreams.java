package streams;

import java.util.*;

public class NestedStreams {

    public static void main(String[] args) {
        List<Integer> a = Arrays.asList(1,2,3);
        List<Integer> b = Arrays.asList(4,5,6);

        a.stream()
            .flatMap(x -> b.stream().map(y -> x + y))
            .forEach(System.out::println);
    }
}