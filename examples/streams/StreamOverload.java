package streams;

import java.util.*;
import java.util.stream.*;

public class StreamOverload {

    public static void main(String[] args) {
        List<Integer> list = Arrays.asList(1,2,3,4,5,6,7,8,9,10);

        List<Integer> result =
            list.stream()
                .filter(x -> x % 2 == 0)
                .map(x -> x * 10)
                .filter(x -> x > 20)
                .sorted()
                .toList();

        System.out.println(result);
    }
}